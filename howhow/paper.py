from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import atomic_json, append_event, canonical, now, read_json, safe_id, sha256_bytes
from .vnext import d, rec, _intact

SECTION_TYPES = (
    "TITLE_AND_CONTRIBUTIONS", "ABSTRACT", "INTRODUCTION", "RELATED_WORK", "QUESTION_HYPOTHESIS",
    "METHODS_SYSTEM", "ANALYSIS_EXPERIMENT_DESIGN", "RESULTS", "ROBUSTNESS_ABLATION_SENSITIVITY",
    "DISCUSSION_COMPETING_EXPLANATIONS", "THREATS", "LIMITATIONS", "ETHICS_RIGHTS_DUAL_USE",
    "REPRODUCIBILITY", "CONCLUSION", "REFERENCES", "APPENDICES",
)
MATERIAL_TYPES = set(SECTION_TYPES) - {"TITLE_AND_CONTRIBUTIONS", "REFERENCES", "APPENDICES"}


def _all(folder: Path) -> list[dict[str, Any]]:
    return [read_json(p) for p in sorted(folder.glob("*.json"))] if folder.exists() else []


def _snapshot(root: Path, folder: str) -> list[dict[str, Any]]:
    return _all(root / ".howhow" / folder)


def create_context(root: Path) -> dict[str, Any]:
    """Freeze a read-only view of currently retained project records."""
    briefs = _snapshot(root, "briefs")
    targets = _snapshot(root, "targets")
    ideas = _snapshot(root, "ideas")
    selections = _snapshot(root, "selections")
    confirmed_briefs = [x for x in briefs if x.get("status") == "CONFIRMED"]
    confirmed_targets = [x for x in targets if x.get("status") == "CONFIRMED"]
    selected_ids = {x.get("idea_id") for x in selections if x.get("status") == "SELECTED"}
    selected = [x for x in ideas if x.get("id") in selected_ids]
    if not confirmed_briefs:
        raise SystemExit("paper context requires a confirmed brief")
    if not confirmed_targets:
        raise SystemExit("paper context requires a confirmed target")
    payload = {
        "context_version": 1,
        "as_of": now(),
        "brief": confirmed_briefs[-1],
        "opinion": {"state": "MISSING" if not (root / "OPINION.md").exists() else ("EMPTY" if not (root / "OPINION.md").read_text(encoding="utf-8") else "PRESENT")},
        "selected_idea": selected[-1] if selected else None,
        "target": confirmed_targets[-1],
        "literature_matrix": _all(root / ".howhow/literature/matrix"),
        "claims": _snapshot(root, "claims"),
        "evidence": _snapshot(root, "evidence"),
        "experiments": _snapshot(root, "experiments"),
        "analysis_plans": _snapshot(root, "analysis"),
        "reviews": _snapshot(root, "reviews"),
    }
    payload["record_hashes"] = {k: [x.get("record_sha256") for x in v if isinstance(x, dict) and x.get("record_sha256")] for k, v in payload.items() if isinstance(v, list)}
    payload["record_hashes"].update({k: [payload[k].get("record_sha256")] for k in ("brief", "selected_idea", "target") if isinstance(payload.get(k), dict) and payload[k].get("record_sha256")})
    identifier = "context-" + str(len(list(d(root, "paper/contexts").glob("*.json"))) + 1)
    return rec(root, "paper/contexts", payload, identifier)


def context_list(root: Path) -> list[dict[str, Any]]:
    return _all(d(root, "paper/contexts"))


def add_section(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemExit("section must be an object")
    identifier = safe_id(value.get("id", ""))
    section_type = value.get("type")
    if section_type not in SECTION_TYPES:
        raise SystemExit("section type must be one of the substantive paper section types")
    paragraphs = value.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        raise SystemExit("section requires a non-empty paragraphs list")
    contexts = context_list(root)
    if not contexts:
        raise SystemExit("section import requires an immutable paper context")
    context_id = value.get("context_id") or contexts[-1].get("id")
    if context_id not in {x.get("id") for x in contexts}:
        raise SystemExit("unknown paper context")
    context = next(x for x in contexts if x.get("id") == context_id)
    context_claims = {x.get("id"): x for x in context.get("claims", [])}
    normalized = []
    for number, paragraph in enumerate(paragraphs, 1):
        if isinstance(paragraph, str):
            paragraph = {"id": "p-" + str(number), "text": paragraph, "claim_ids": []}
        if not isinstance(paragraph, dict) or not isinstance(paragraph.get("text"), str):
            raise SystemExit("each paragraph requires text and claim_ids")
        claim_ids = paragraph.get("claim_ids", [])
        if not isinstance(claim_ids, list) or any(not isinstance(x, str) for x in claim_ids):
            raise SystemExit("paragraph claim_ids must be a list of strings")
        missing = [x for x in claim_ids if x not in context_claims]
        if missing:
            raise SystemExit("unknown claim anchor(s): " + ", ".join(missing))
        normalized.append({"id": paragraph.get("id", "p-" + str(number)), "text": paragraph["text"], "claim_ids": claim_ids, "material": paragraph.get("material", True), "claim_snapshots": {claim_id: context_claims[claim_id] for claim_id in claim_ids}})
    revision_of = value.get("revision_of")
    if revision_of:
        if not (d(root, "paper/sections") / (safe_id(revision_of) + ".json")).exists():
            raise SystemExit("revision_of section does not exist")
    record = {"type": section_type, "paragraphs": normalized, "word_count": sum(len(p["text"].split()) for p in normalized), "status": value.get("status", "DRAFT"), "rationale": value.get("rationale") or value.get("not_applicable_rationale"), "revision_of": revision_of, "context_id": context_id, "manuscript_path": value.get("manuscript_path")}
    if record["status"] not in {"DRAFT", "REVIEW", "FINAL", "NOT_APPLICABLE"}:
        raise SystemExit("section status must be DRAFT, REVIEW, FINAL, or NOT_APPLICABLE")
    return rec(root, "paper/sections", record, identifier)


def section_list(root: Path) -> list[dict[str, Any]]:
    return _all(d(root, "paper/sections"))


def _integrity(records: list[dict[str, Any]], label: str, issues: list[str]) -> None:
    for item in records:
        if not _intact(item, item.get("id", "")):
            issues.append(label + ":" + str(item.get("id")) + " immutable hash failed")


def audit(root: Path) -> dict[str, Any]:
    issues: list[str] = []
    sections = section_list(root)
    contexts = context_list(root)
    current_claims = {x.get("id"): x for x in _snapshot(root, "claims")}
    evidence = {x.get("id"): x for x in _snapshot(root, "evidence")}
    runs = {x.get("id"): x for x in _snapshot(root, "experiments")}
    _integrity(sections, "section", issues); _integrity(contexts, "context", issues)
    context_by_id = {x.get("id"): x for x in contexts}
    by_type = {}
    for section_type in SECTION_TYPES:
        candidates = [x for x in sections if x.get("type") == section_type]
        if len(candidates) > 1:
            ids = {x.get("id") for x in candidates}
            roots = [x for x in candidates if not x.get("revision_of")]
            children = {x.get("revision_of") for x in candidates if x.get("revision_of")}
            if len(roots) != 1 or len(children) != len(candidates) - 1 or not all(x.get("revision_of") in ids for x in candidates if x.get("revision_of")):
                issues.append("duplicate section type requires one explicit revision chain: " + section_type)
            leaves = [x for x in candidates if x.get("id") not in children]
            if len(leaves) == 1:
                by_type[section_type] = leaves[0]
        elif candidates:
            by_type[section_type] = candidates[0]
    checklist = {}
    for section_type in SECTION_TYPES:
        present = by_type.get(section_type)
        na = present and present.get("status") == "NOT_APPLICABLE"
        ok = bool(present) and (not na or bool(present.get("rationale") or present.get("not_applicable_rationale")))
        checklist[section_type] = {"status": "PASS" if ok else "MISSING", "not_applicable": bool(na)}
        if not ok: issues.append("missing substantive section or explicit NOT_APPLICABLE rationale: " + section_type)
    for section in sections:
        context = context_by_id.get(section.get("context_id"))
        if not context:
            issues.append(section.get("id", "?") + ": missing paper context")
        frozen_claims = {x.get("id"): x for x in (context or {}).get("claims", [])}
        frozen_evidence = {x.get("id"): x for x in (context or {}).get("evidence", [])}
        frozen_runs = {x.get("id"): x for x in (context or {}).get("experiments", [])}
        for paragraph in section.get("paragraphs", []):
            if paragraph.get("material", True) and not paragraph.get("claim_ids") and section.get("type") in MATERIAL_TYPES:
                issues.append(section.get("id", "?") + ": material paragraph lacks claim anchor")
            for claim_id in paragraph.get("claim_ids", []):
                claim = frozen_claims.get(claim_id)
                if not claim: issues.append("unknown frozen claim anchor: " + str(claim_id)); continue
                if paragraph.get("claim_snapshots", {}).get(claim_id) != claim or current_claims.get(claim_id) != claim:
                    issues.append(section.get("id", "?") + ": claim snapshot mismatch: " + claim_id)
                ctype = claim.get("type")
                if ctype == "EXTERNAL":
                    ev_ids = claim.get("evidence_ids", [])
                    if not ev_ids or any(not frozen_evidence.get(e) or frozen_evidence[e].get("status") != "VERIFIED" or not frozen_evidence[e].get("source_id") for e in ev_ids):
                        issues.append(claim_id + ": EXTERNAL claim lacks exact retained VERIFIED evidence/source link")
                if ctype == "EMPIRICAL":
                    if not claim.get("run_ids") or any(not frozen_runs.get(r) or not _intact(frozen_runs[r], r) for r in claim.get("run_ids", [])):
                        issues.append(claim_id + ": EMPIRICAL claim lacks intact run")
                if ctype == "OPINION" and claim.get("evidence"):
                    issues.append(claim_id + ": OPINION is improperly treated as evidence")
                if claim.get("status") in {"UNRESOLVED", "UNVERIFIED"} and claim.get("type") not in {"OPINION"} and "unverif" not in paragraph.get("text", "").lower() and "uncertain" not in paragraph.get("text", "").lower():
                    issues.append(claim_id + ": unresolved material is not disclosed as UNVERIFIED")
    all_text = " ".join(p.get("text", "") for s in sections for p in s.get("paragraphs", []))
    normalized_paragraphs = [" ".join(p.get("text", "").lower().split()) for s in sections for p in s.get("paragraphs", []) if p.get("text", "").strip()]
    repeated = len(normalized_paragraphs) - len(set(normalized_paragraphs))
    synthetic_disclosure = "fixture" in all_text.lower() and "uncertainty" in all_text.lower()
    if repeated >= 3 and not synthetic_disclosure:
        issues.append("repeated boilerplate paragraphs undermine substantive section coverage")
    failed = any(x.get("status") in {"FAILED", "INCONCLUSIVE"} for x in runs.values())
    if failed and not any(word in all_text.lower() for word in ("inconclusive", "failed", "failure", "negative", "did not", "null result")):
        issues.append("negative/inconclusive run outcome is not reported")
    if not any(word in all_text.lower() for word in ("uncertain", "uncertainty", "confidence", "caveat")):
        issues.append("uncertainty disclosure is missing")
    if not any(x.get("type") == "METHODS_SYSTEM" and any(k in p.get("text", "").lower() for k in ("input", "seed", "environment", "code", "data")) for x in sections for p in x.get("paragraphs", [])):
        issues.append("methods reproducibility inputs are missing")
    for section_type, keywords in {
        "ETHICS_RIGHTS_DUAL_USE": ("ethic", "right", "consent", "privacy", "dual-use", "risk"),
        "THREATS": ("threat", "attack", "advers", "competing", "alternative", "generaliz"),
        "DISCUSSION_COMPETING_EXPLANATIONS": ("alternative", "competing", "explain", "confound", "caveat"),
    }.items():
        selected = by_type.get(section_type)
        text = " ".join(p.get("text", "") for p in (selected or {}).get("paragraphs", [])).lower()
        if selected and selected.get("status") != "NOT_APPLICABLE" and not any(word in text for word in keywords):
            issues.append(section_type + ": substantive discussion is missing")
        if selected and selected.get("status") == "NOT_APPLICABLE" and len((selected.get("rationale") or "").split()) < 5:
            issues.append(section_type + ": NOT_APPLICABLE rationale is not substantive")
    if contexts and not sections:
        issues.append("paper context is not connected to imported manuscript sections")
    return {"passed": not issues, "checklist": checklist, "issues": issues, "section_count": len(sections), "context_count": len(contexts), "contract": "content contracts; page count and ledger prose cannot satisfy this audit"}
