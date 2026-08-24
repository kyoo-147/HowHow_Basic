from __future__ import annotations

"""Phase D2 immutable artifact, citation, issue and policy controls."""
import json
from pathlib import Path
from typing import Any
from .core import canonical, sha256_bytes, sha256_file, now, safe_id, read_json, atomic_json, append_event
from .vnext import d, rec, _intact

ARTIFACT_TYPES = {"FIGURE", "TABLE"}
ISSUE_SEVERITIES = {"BLOCKING", "MAJOR", "MINOR", "DISSENT"}
ISSUE_DISPOSITIONS = {"OPEN", "RESOLVED", "REBUTTED", "UNRESOLVED"}
REVIEW_KINDS = {"HUMAN", "MACHINE_ASSISTED", "MACHINE"}
POLICY_KINDS = {"SOURCE", "DATA", "CODE", "MODEL", "FIGURE", "AI_ASSISTANCE", "VENUE", "CITATION", "PLAGIARISM", "SUBMISSION"}
POLICY_STATES = {"ALLOWED", "RESTRICTED", "UNKNOWN", "PROHIBITED", "REVIEW_REQUIRED"}
CITATION_CORRECTION_STATES = {"CLEAR", "RETRACTED", "CORRECTED", "UNKNOWN", "UNDER_REVIEW"}
CITATION_ACCESS_STATES = {"ALLOWED", "CC0", "PUBLIC_DOMAIN", "MIT", "RESTRICTED", "PROHIBITED", "UNKNOWN", "REVIEW_REQUIRED"}
PARENT_FOLDERS = {"source": "sources/records", "run": "experiments", "artifact": "artifacts", "evidence": "evidence", "claim": "claims"}


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parent_errors(root: Path, parents: Any, label: str = "parent") -> list[str]:
    errors = []
    if not isinstance(parents, dict):
        return [f"{label} links must be an object"]
    for kind, ids in parents.items():
        if kind not in PARENT_FOLDERS:
            errors.append(f"unknown {label} type {kind}")
        elif not isinstance(ids, list) or any(not isinstance(x, str) or not x or not _parent_exists(root, kind, x) for x in ids):
            errors.append(f"unknown {kind} {label}")
    return errors


def _artifact_errors(root: Path, item: dict[str, Any]) -> list[str]:
    errors = []
    if item.get("kind") not in ARTIFACT_TYPES: errors.append("invalid artifact kind")
    raw = item.get("raw_inputs")
    if not isinstance(raw, list) or not raw: errors.append("raw_inputs must be a non-empty list")
    else:
        for entry in raw:
            if not isinstance(entry, dict) or not _nonempty_string(entry.get("path")) or not _nonempty_string(entry.get("sha256")):
                errors.append("each raw input requires non-empty path and sha256")
            else: errors += _check_file(root, entry["path"], "raw input", entry["sha256"])
    transform = item.get("transformation")
    if not isinstance(transform, dict) or not _nonempty_string(transform.get("script")) or not _nonempty_string(transform.get("script_sha256")):
        errors.append("transformation requires script and script_sha256")
    else: errors += _check_file(root, transform["script"], "transformation script", transform["script_sha256"])
    generated = item.get("generated")
    if not isinstance(generated, dict) or not _nonempty_string(generated.get("path")) or not _nonempty_string(generated.get("sha256")):
        errors.append("generated requires path and sha256")
    else: errors += _check_file(root, generated["path"], "generated artifact", generated["sha256"])
    units = item.get("units")
    if not isinstance(units, dict) or not units or any(not _nonempty_string(k) or not _nonempty_string(v) for k, v in units.items()): errors.append("units must map non-empty names to non-empty units")
    uncertainty = item.get("uncertainty")
    if not ((_nonempty_string(uncertainty)) or (isinstance(uncertainty, dict) and uncertainty and all(_nonempty_string(k) for k in uncertainty))): errors.append("uncertainty must be a non-empty description or object")
    if item.get("accessibility_status") not in {"PASS", "FAIL", "PENDING", "NOT_APPLICABLE"}: errors.append("invalid accessibility_status")
    if item.get("visual_qa_status") not in {"PASS", "FAIL", "PENDING", "NOT_APPLICABLE"}: errors.append("invalid visual_qa_status")
    claims = item.get("caption_claim_ids")
    claim_ids = {x.get("id") for x in _all(root, "claims")}
    if not isinstance(claims, list) or any(not isinstance(x, str) or not x for x in claims): errors.append("caption_claim_ids must be a list of non-empty strings")
    else: errors += [f"unknown caption claim {x}" for x in claims if x not in claim_ids]
    errors += _parent_errors(root, item.get("parents"))
    receipt = item.get("regeneration_receipt")
    if not isinstance(receipt, dict) or not isinstance(receipt.get("command"), list) or not receipt["command"] or any(not _nonempty_string(x) for x in receipt["command"]) or receipt.get("status") not in {"RECEIVED", "REPRODUCIBLE", "NOT_REGENERATED"}:
        errors.append("invalid regeneration_receipt")
    return errors


def _all(root: Path, folder: str) -> list[dict[str, Any]]:
    return [read_json(p) for p in sorted(d(root, folder).glob("*.json")) if p.is_file()]


def _hash_record(value: dict[str, Any]) -> str:
    unsigned = dict(value); unsigned.pop("record_sha256", None)
    return sha256_bytes(canonical(unsigned))


def _path(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise SystemExit(f"{label} must be a project-relative path")
    p = (root / value).resolve()
    try: p.relative_to(root.resolve())
    except ValueError: raise SystemExit(f"{label} escapes project")
    return p


def _parent_exists(root: Path, parent: str, identifier: str) -> bool:
    folders = {"source": "sources/records", "run": "experiments", "artifact": "artifacts", "evidence": "evidence", "claim": "claims"}
    folder = folders.get(parent)
    return bool(folder and (d(root, folder) / f"{identifier}.json").exists())


def _check_file(root: Path, value: Any, label: str, digest: Any = None) -> list[str]:
    try: p = _path(root, value, label)
    except SystemExit as exc: return [str(exc)]
    if not p.is_file(): return [f"{label} missing: {value}"]
    return [] if digest and sha256_file(p) == digest else ([] if digest is None else [f"{label} hash mismatch: {value}"])


def add_artifact(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict): raise SystemExit("artifact manifest must be an object")
    required = ["id", "kind", "raw_inputs", "transformation", "generated", "units", "uncertainty", "caption_claim_ids", "accessibility_status", "visual_qa_status", "parents", "regeneration_receipt"]
    missing = [x for x in required if x not in value]
    if missing: raise SystemExit("artifact manifest missing: " + ", ".join(missing))
    identifier = safe_id(value["id"], "artifact id")
    errors = _artifact_errors(root, value)
    if errors: raise SystemExit(errors[0])
    return rec(root, "artifacts", value, identifier)


def artifact_audit(root: Path) -> dict[str, Any]:
    issues = []
    for item in _all(root, "artifacts"):
        ident = item.get("id")
        if not _intact(item, ident): issues.append(f"{ident}: immutable hash mismatch")
        issues += [f"{ident}: {x}" for x in _artifact_errors(root, item)]
    result = {"passed": not issues, "records": len(_all(root, "artifacts")), "issues": issues, "truth_boundary": "artifact provenance is not scientific validation"}
    atomic_json(d(root, "artifacts/audits") / ("audit-" + sha256_bytes(canonical(result))[:16] + ".json"), result)
    return result


def add_citation(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    required = ["id", "citation_key", "bibliographic_identity", "identifiers", "identity_receipts", "support", "correction_retraction_status", "access_redistribution"]
    if not isinstance(value, dict): raise SystemExit("citation record must be an object")
    missing = [x for x in required if x not in value]
    if missing: raise SystemExit("citation record missing: " + ", ".join(missing))
    ident = safe_id(value["id"], "citation id")
    errors = _citation_errors(root, value)
    if errors: raise SystemExit(errors[0])
    support = value["support"]
    value = dict(value); value["support_status"] = "VERIFIED" if support["claim_ids"] and support["evidence_ids"] and support.get("exact_links") else "UNVERIFIED"
    return rec(root, "citations", value, ident)


def _citation_errors(root: Path, item: dict[str, Any]) -> list[str]:
    errors = []
    if not _nonempty_string(item.get("citation_key")): errors.append("citation_key is required")
    if not isinstance(item.get("bibliographic_identity"), dict) or not item["bibliographic_identity"]: errors.append("bibliographic_identity must be non-empty")
    identifiers, receipts = item.get("identifiers"), item.get("identity_receipts")
    if not isinstance(identifiers, dict) or not identifiers or any(not _nonempty_string(k) or not _nonempty_string(v) for k, v in identifiers.items()): errors.append("identifiers must contain non-empty strings")
    if not isinstance(receipts, list) or not receipts or any(not _nonempty_string(x) for x in receipts): errors.append("identity_receipts must contain non-empty strings")
    if item.get("correction_retraction_status") not in CITATION_CORRECTION_STATES: errors.append("invalid correction_retraction_status")
    if item.get("access_redistribution") not in CITATION_ACCESS_STATES: errors.append("invalid access_redistribution")
    support = item.get("support")
    if not isinstance(support, dict): return errors + ["support must be an object"]
    claim_ids, evidence_ids, links = support.get("claim_ids"), support.get("evidence_ids"), support.get("exact_links")
    if not isinstance(claim_ids, list) or any(not isinstance(x, str) or not x for x in claim_ids): errors.append("support claim_ids must be non-empty strings")
    if not isinstance(evidence_ids, list) or any(not isinstance(x, str) or not x for x in evidence_ids): errors.append("support evidence_ids must be non-empty strings")
    if not isinstance(links, list) or any(not isinstance(x, (str, dict)) or (isinstance(x, str) and not x.strip()) or (isinstance(x, dict) and not x) for x in (links or [])): errors.append("support exact_links must be a list of links")
    for kind, ids in (("claim", claim_ids or []), ("evidence", evidence_ids or [])):
        errors += [f"unknown {kind} {x}" for x in ids if not _parent_exists(root, kind, x)]
    return errors


def citation_audit(root: Path) -> dict[str, Any]:
    issues = []
    for item in _all(root, "citations"):
        ident = item.get("id")
        if not _intact(item, ident): issues.append(f"{ident}: immutable hash mismatch")
        issues += [f"{ident}: {x}" for x in _citation_errors(root, item)]
        support = item.get("support", {})
        valid = bool(support.get("claim_ids") and support.get("evidence_ids") and support.get("exact_links")) and not _citation_errors(root, item)
        if item.get("support_status") != ("VERIFIED" if valid else "UNVERIFIED"): issues.append(f"{ident}: invalid support status")
        if item.get("correction_retraction_status") in {"RETRACTED", "CORRECTED", "UNKNOWN", "UNDER_REVIEW"}: issues.append(f"{ident}: citation correction/retraction status is not clear")
        if item.get("access_redistribution") in {"RESTRICTED", "PROHIBITED", "UNKNOWN", "REVIEW_REQUIRED"}: issues.append(f"{ident}: citation access/redistribution is not allowed")
    return {"passed": not issues, "records": len(_all(root, "citations")), "issues": issues, "identity_support_separate": True}


def add_issue(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    required = ["id", "severity", "finding", "disposition", "anchors", "reviewer", "review_kind", "context", "execution_contract"]
    if not isinstance(value, dict): raise SystemExit("issue record must be an object")
    missing = [x for x in required if x not in value]
    if missing: raise SystemExit("issue record missing: " + ", ".join(missing))
    ident = safe_id(value["id"], "issue id")
    if value["severity"] not in ISSUE_SEVERITIES or value["disposition"] not in ISSUE_DISPOSITIONS: raise SystemExit("invalid issue severity or disposition")
    if value["review_kind"] not in REVIEW_KINDS: raise SystemExit("invalid review kind")
    if value["review_kind"] in {"MACHINE", "MACHINE_ASSISTED"} and value.get("independent_scientific_review") is True: raise SystemExit("machine review cannot be independent scientific review")
    errors = _issue_errors(root, value, check_links=False)
    if errors: raise SystemExit(errors[0])
    return rec(root, "issues", value, ident)


def _retained_ids(root: Path, folders: tuple[str, ...]) -> set[str]:
    return {p.stem for folder in folders for p in d(root, folder).glob("*.json")}


def _issue_errors(root: Path, item: dict[str, Any], check_links: bool = True) -> list[str]:
    errors = []
    anchors = item.get("anchors")
    if not isinstance(anchors, dict) or not any(anchors.get(k) for k in ("manuscript", "artifact", "evidence")): return ["issue requires an anchor"]
    artifact_ids = _retained_ids(root, ("artifacts",)); evidence_ids = _retained_ids(root, ("evidence",))
    if "artifact" in anchors:
        vals = anchors["artifact"] if isinstance(anchors["artifact"], list) else [anchors["artifact"]]
        errors += [f"unknown artifact anchor {x}" for x in vals if not isinstance(x, str) or x not in artifact_ids]
    if "evidence" in anchors:
        vals = anchors["evidence"] if isinstance(anchors["evidence"], list) else [anchors["evidence"]]
        errors += [f"unknown evidence anchor {x}" for x in vals if not isinstance(x, str) or x not in evidence_ids]
    manuscript = anchors.get("manuscript")
    if manuscript is not None and (not isinstance(manuscript, str) or not manuscript.strip()): errors.append("invalid manuscript anchor")
    if item.get("disposition") in {"RESOLVED", "REBUTTED"}:
        links = item.get("linked_revision_ids", []) if item.get("disposition") == "RESOLVED" else item.get("linked_rebuttal_ids", [])
        if not isinstance(links, list) or not links or any(not isinstance(x, str) or not x for x in links): errors.append("resolved/rebutted issue requires non-empty linked ids")
        folders = ("reviews", "revisions", "rebuttals")
        if check_links:
            retained = _retained_ids(root, folders)
            errors += [f"unknown linked record {x}" for x in links if x not in retained]
    return errors


def issue_audit(root: Path) -> dict[str, Any]:
    issues = []
    for item in _all(root, "issues"):
        ident = item.get("id")
        if not _intact(item, ident): issues.append(f"{ident}: immutable hash mismatch")
        issues += [f"{ident}: {x}" for x in _issue_errors(root, item)]
        if item.get("severity") not in ISSUE_SEVERITIES or item.get("disposition") not in ISSUE_DISPOSITIONS: issues.append(f"{ident}: invalid issue state")
        if item.get("review_kind") in {"MACHINE", "MACHINE_ASSISTED"} and item.get("independent_scientific_review") is True: issues.append(f"{ident}: machine review mislabeled independent")
        if item.get("severity") in {"BLOCKING", "MAJOR"} and item.get("disposition") in {"OPEN", "UNRESOLVED"}: issues.append(f"{ident}: unresolved {item.get('severity')} issue")
    return {"passed": not issues, "records": len(_all(root, "issues")), "issues": issues, "human_review_required": True, "machine_review_is_not_independent": True}


def add_policy(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict): raise SystemExit("policy record must be an object")
    for key in ("id", "kind", "state", "subject", "disclosure", "human_review_boundary"): 
        if key not in value: raise SystemExit("policy record missing: " + key)
    ident = safe_id(value["id"], "policy id")
    if value["kind"] not in POLICY_KINDS or value["state"] not in POLICY_STATES: raise SystemExit("invalid policy kind or state")
    if not isinstance(value["disclosure"], str) or not value["disclosure"].strip(): raise SystemExit("policy disclosure is required")
    return rec(root, "policies", value, ident)


def policy_audit(root: Path) -> dict[str, Any]:
    issues = []
    for item in _all(root, "policies"):
        ident = item.get("id")
        if not _intact(item, ident): issues.append(f"{ident}: immutable hash mismatch")
        if item.get("kind") not in POLICY_KINDS or item.get("state") not in POLICY_STATES: issues.append(f"{ident}: invalid policy")
    blockers = [x.get("id") for x in _all(root, "policies") if x.get("state") in {"UNKNOWN", "RESTRICTED", "PROHIBITED", "REVIEW_REQUIRED"}]
    citation_blockers = [x.get("id") for x in _all(root, "citations") if x.get("correction_retraction_status") != "CLEAR" or x.get("access_redistribution") not in {"ALLOWED", "CC0", "PUBLIC_DOMAIN", "MIT"}]
    blockers += ["citation:" + x for x in citation_blockers]
    if citation_blockers: issues.append("citation-level correction/access restrictions require policy review")
    return {"passed": not issues and not blockers, "records": len(_all(root, "policies")), "issues": issues, "blockers": blockers, "human_review_required": True, "submission_prohibited": True}


def d2_audit(root: Path, required: bool = False) -> dict[str, Any]:
    results = {"artifacts": artifact_audit(root), "citations": citation_audit(root), "issues": issue_audit(root), "policies": policy_audit(root)}
    if required:
        for name in results:
            if results[name]["records"] == 0:
                results[name]["passed"] = False
                results[name]["issues"].append(f"{name}: at least one retained record is required")
    return {"passed": all(x["passed"] for x in results.values()), "results": results, "profile": "vnext-detailed"}


def d2_status(root: Path) -> dict[str, Any]:
    checks = d2_audit(root)
    if not checks["passed"]: action = "resolve D2 artifact, citation, issue, or policy blockers"
    elif not _all(root, "artifacts"): action = "register figure/table provenance artifacts"
    elif not _all(root, "citations"): action = "audit citation identity and claim support"
    elif not _all(root, "issues"): action = "record human review issues and dispositions"
    elif not _all(root, "policies"): action = "record policy and license decisions"
    else: action = "prepare source package after human review"
    return {"next_action": action, "audit": checks, "counts": {k: len(_all(root, k)) for k in ("artifacts", "citations", "issues", "policies")}}
