from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from .core import atomic_json, append_event, canonical, now, safe_id, sha256_bytes, sha256_file

ROLES = {"FOUNDATIONAL", "NEAREST", "SUPPORTING", "CONTRADICTING"}
DECISIONS = {"INCLUDED", "EXCLUDED", "UNRESOLVED"}

def _dir(root: Path, name: str) -> Path:
    path = root / ".howhow" / "literature" / name
    path.mkdir(parents=True, exist_ok=True)
    return path

def _record(root: Path, folder: str, value: dict[str, Any], identifier: str) -> dict[str, Any]:
    safe_id(identifier)
    if (path := _dir(root, folder) / f"{identifier}.json").exists():
        raise SystemExit("immutable literature record already exists: " + identifier)
    value = dict(value); value.update(schema_version=1, id=identifier, created_at=now())
    value["record_sha256"] = sha256_bytes(canonical(value))
    atomic_json(_dir(root, folder) / f"{identifier}.json", value)
    append_event(root, "literature." + folder + ".recorded", {"id": identifier})
    return value

def _load(root: Path, folder: str) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(_dir(root, folder).glob("*.json"))]

def create_protocol(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    required = ("questions", "claims", "date_cutoff", "filters", "stop_rationale")
    if not isinstance(value, dict) or any(k not in value for k in required): raise SystemExit("protocol requires questions, claims, date_cutoff, filters, and stop_rationale")
    if not isinstance(value["questions"], list) or not value["questions"] or not all(isinstance(x, str) and x for x in value["questions"]): raise SystemExit("protocol questions must be non-empty strings")
    if not isinstance(value["claims"], list) or not all(isinstance(x, str) and x for x in value["claims"]): raise SystemExit("protocol claims must be strings")
    if not isinstance(value["filters"], dict) or not isinstance(value["stop_rationale"], str) or not value["stop_rationale"]: raise SystemExit("protocol filters and stop_rationale are required")
    queries = value.get("queries")
    receipts = value.get("query_receipts")
    results = value.get("candidate_result_ids")
    saturation = value.get("saturation")
    if not isinstance(queries, list) or not queries or not all(isinstance(q, str) and q for q in queries): raise SystemExit("protocol requires executed search queries")
    if not isinstance(receipts, list) or not receipts or not all(isinstance(r, dict) and r.get("receipt_id") and r.get("provider") == "gpt-researcher" and r.get("query") in queries for r in receipts): raise SystemExit("protocol query receipts must prove bounded executed queries")
    if not isinstance(results, list) or not all(isinstance(x, str) and x for x in results): raise SystemExit("candidate_result_ids must be a list of IDs")
    if not isinstance(saturation, dict) or saturation.get("result_count") != len(results) or saturation.get("queries_covered") != len(queries) or not isinstance(saturation.get("stopping_test"), str) or not saturation["stopping_test"]: raise SystemExit("protocol saturation requires result_count, query coverage, and a stopping test")
    value.setdefault("providers", ["gpt-researcher"]); value.setdefault("retrieval_timestamp", now())
    value.setdefault("citation_expansion", {"enabled": False, "records": []}); value.setdefault("deduplication", {"identity_fields": ["doi", "provider", "document_id", "version"]})
    value.setdefault("correction_retraction_status", "UNVERIFIED"); value.setdefault("contradiction_search", {"queries": [], "performed": False})
    if value.get("contradiction_search", {}).get("performed") is not True: raise SystemExit("protocol requires an executed contradiction search")
    return _record(root, "protocols", value, safe_id(value.get("id", "protocol-1")))

def import_candidate(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    required = ("provider", "query_receipt", "candidate_id", "url", "protocol_id", "adapter_request")
    if not isinstance(value, dict) or any(not value.get(k) for k in required): raise SystemExit("candidate requires provider, query receipt, candidate ID, URL, protocol ID, and adapter request")
    if value["provider"] != "gpt-researcher" or not isinstance(value["url"], str) or not value["url"].startswith("https://"): raise SystemExit("candidate imports require bounded gpt-researcher HTTPS metadata")
    request = value["adapter_request"]
    if not isinstance(request, dict) or request.get("provider") != "gpt-researcher" or request.get("live") is not False or not isinstance(request.get("query"), str) or not 1 <= request.get("limit", 0) <= 50: raise SystemExit("candidate adapter request is not bounded")
    receipt = value["query_receipt"]
    if not isinstance(receipt, dict) or not receipt.get("receipt_id") or receipt.get("provider") != "gpt-researcher" or receipt.get("query") != request["query"]: raise SystemExit("candidate requires an execution-backed query receipt")
    protocols = {p["id"]: p for p in _load(root, "protocols")}
    protocol = protocols.get(value["protocol_id"])
    if not protocol or value["candidate_id"] not in protocol.get("candidate_result_ids", []) or not any(r.get("receipt_id") == receipt["receipt_id"] and r.get("query") == receipt["query"] for r in protocol.get("query_receipts", [])): raise SystemExit("candidate is not linked to the protocol receipt and result list")
    allowed = {"provider", "query_receipt", "candidate_id", "url", "title", "document_id", "retrieved_at", "protocol_id", "adapter_request"}
    if any(k not in allowed for k in value): raise SystemExit("candidate adapter accepts only bounded provisional retrieval metadata")
    return _record(root, "candidates", value, safe_id(value["candidate_id"]))

def decide_candidate(root: Path, candidate_id: str, decision: str, reason: str, source_id: str | None = None) -> dict[str, Any]:
    safe_id(candidate_id); safe_id(source_id, "source id") if source_id else None
    if decision not in DECISIONS: raise SystemExit("decision must be INCLUDED, EXCLUDED, or UNRESOLVED")
    if not isinstance(reason, str) or not reason: raise SystemExit("inclusion/exclusion reason is required")
    candidates = {x["id"]: x for x in _load(root, "candidates")}
    if candidate_id not in candidates: raise SystemExit("unknown candidate")
    if decision == "INCLUDED":
        if not source_id: raise SystemExit("included candidate requires a retained source_id")
        sources = {p.stem for p in (root / ".howhow/sources/records").glob("*.json") if not p.name.endswith(".pin.json")}
        if source_id not in sources: raise SystemExit("included candidate requires an existing retained source")
    return _record(root, "decisions", {"candidate_id": candidate_id, "decision": decision, "reason": reason, "source_id": source_id, "protocol_id": candidates[candidate_id]["protocol_id"]}, "decision-" + str(len(_load(root, "decisions")) + 1))

def add_matrix(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or (not value.get("question") and not value.get("claim")) or value.get("role") not in ROLES: raise SystemExit("matrix entry requires question or claim and role")
    if not isinstance(value.get("source_ids"), list) or not isinstance(value.get("evidence_ids"), list): raise SystemExit("matrix entry requires source_ids and evidence_ids arrays")
    status = value.get("status", "UNVERIFIED")
    if status not in {"RETAINED", "UNVERIFIED"}: raise SystemExit("matrix status must be RETAINED or UNVERIFIED")
    if status == "RETAINED" and (not value["source_ids"] or not value["evidence_ids"]): raise SystemExit("retained matrix entries require exact source and evidence IDs")
    return _record(root, "matrix", value, safe_id(value.get("id", "matrix-" + str(len(_load(root, "matrix")) + 1))))

def add_transformed(root: Path, value: dict[str, Any], extracted: Path) -> dict[str, Any]:
    required = ("id", "parent_source_id", "extractor", "config_hash", "page_mapping", "locator")
    if not isinstance(value, dict) or any(k not in value for k in required): raise SystemExit("transformed source requires parent, extractor, config_hash, page_mapping, and locator")
    safe_id(value["id"]); safe_id(value["parent_source_id"], "parent source id")
    parent = root / ".howhow/sources/records" / (value["parent_source_id"] + ".json"); payload = root / ".howhow/sources/raw" / value["parent_source_id"] / "payload"
    if not parent.exists() or not payload.exists(): raise SystemExit("transformed source parent is missing")
    manifest = json.loads(parent.read_text(encoding="utf-8"))
    if sha256_file(payload) != manifest.get("sha256"): raise SystemExit("transformed source parent mutated")
    data = extracted.read_bytes()
    mappings = value.get("page_mapping")
    locator = value.get("locator")
    if not isinstance(mappings, list) or not mappings or any(not isinstance(m, dict) or type(m.get("page")) is not int or type(m.get("start")) is not int or type(m.get("end")) is not int or not (0 <= m["start"] <= m["end"] <= len(data)) for m in mappings): raise SystemExit("page mappings must contain bounded page/start/end spans")
    if not isinstance(locator, dict) or type(locator.get("text_start")) is not int or type(locator.get("text_end")) is not int or not (0 <= locator["text_start"] <= locator["text_end"] <= len(data)): raise SystemExit("transformed locator must be bounded to extracted text")
    value.update(original_sha256=manifest["sha256"], extracted_sha256=sha256_bytes(data), extracted_bytes=len(data), extracted_path="extracted/" + value["id"] + ".txt")
    target = _dir(root, "extracted") / (value["id"] + ".txt")
    if target.exists(): raise SystemExit("immutable extracted text already exists")
    target.write_bytes(data)
    return _record(root, "transformed", value, value["id"])

def candidate_adapter_request(provider: str, query: str, limit: int = 10) -> dict[str, Any]:
    if provider != "gpt-researcher" or not isinstance(query, str) or not query or not isinstance(limit, int) or not 1 <= limit <= 50: raise SystemExit("adapter permits bounded gpt-researcher requests only")
    return {"provider": provider, "query": query, "limit": limit, "export": ["query", "limit"], "import": ["provisional URLs", "document IDs", "query receipts"], "verification_owner": "HowHow", "live": False}

def audit(root: Path) -> dict[str, Any]:
    issues: list[str] = []
    for folder in ("protocols", "candidates", "decisions", "matrix", "transformed"):
        for path in _dir(root, folder).glob("*.json"):
            try: record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError): issues.append(path.name + ": unreadable"); continue
            unsigned = dict(record); digest = unsigned.pop("record_sha256", None)
            if path.stem != record.get("id") or digest != sha256_bytes(canonical(unsigned)): issues.append(path.name + ": immutable hash or filename/id mismatch")
    sources = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (root / ".howhow/sources/records").glob("*.json") if not p.name.endswith(".pin.json")}
    evidence = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (root / ".howhow/evidence").glob("*.json")}
    decisions = _load(root, "decisions"); candidate_records = _load(root, "candidates"); candidates = {x["id"]: x for x in candidate_records}
    protocols_by_id = {p["id"]: p for p in _load(root, "protocols")}
    for candidate in candidate_records:
        request = candidate.get("adapter_request", {}); receipt = candidate.get("query_receipt", {})
        protocol = protocols_by_id.get(candidate.get("protocol_id"))
        if candidate.get("provider") != "gpt-researcher" or not str(candidate.get("url", "")).startswith("https://"): issues.append(candidate["id"] + ": unbounded provider or URL")
        if request.get("live") is not False or request.get("provider") != "gpt-researcher" or receipt.get("provider") != "gpt-researcher": issues.append(candidate["id"] + ": adapter provenance is not bounded")
        if not protocol or candidate["id"] not in protocol.get("candidate_result_ids", []) or not any(r.get("receipt_id") == receipt.get("receipt_id") for r in protocol.get("query_receipts", [])): issues.append(candidate["id"] + ": missing protocol receipt binding")
    for decision in decisions:
        if decision.get("candidate_id") not in candidates: issues.append(decision["id"] + ": unknown candidate")
        if decision.get("decision") == "INCLUDED" and decision.get("source_id") not in sources: issues.append(decision["id"] + ": included candidate has unknown source")
    for item in _load(root, "matrix"):
        if item.get("status") == "RETAINED":
            for sid in item.get("source_ids", []):
                if sid not in sources: issues.append(item["id"] + ": unknown retained source " + sid)
            for eid in item.get("evidence_ids", []):
                ev = evidence.get(eid)
                if not ev or ev.get("status") != "VERIFIED": issues.append(item["id"] + ": evidence is not exact retained VERIFIED evidence: " + eid)
                elif ev.get("source_id") not in item.get("source_ids", []) and (not ev.get("transformed_source_id") or next((t.get("parent_source_id") for t in _load(root, "transformed") if t.get("id") == ev.get("transformed_source_id")), None) not in item.get("source_ids", [])): issues.append(item["id"] + ": evidence/source pairing mismatch: " + eid)
    for item in _load(root, "transformed"):
        parent = sources.get(item.get("parent_source_id")); raw = root / ".howhow/sources/raw" / item.get("parent_source_id", "") / "payload"; extracted = _dir(root, "extracted") / (item.get("id", "") + ".txt")
        if not parent or not raw.exists() or sha256_file(raw) != parent.get("sha256") or parent.get("sha256") != item.get("original_sha256"): issues.append(item.get("id", "?") + ": parent hash changed")
        if not extracted.exists() or sha256_file(extracted) != item.get("extracted_sha256"): issues.append(item.get("id", "?") + ": extracted bytes changed or missing")
    protocols = list(protocols_by_id.values())
    if protocols:
        for p in protocols:
            results = set(p.get("candidate_result_ids", [])); actual = {c["id"] for c in candidates.values() if c.get("protocol_id") == p.get("id")}
            if not actual <= results: issues.append(p["id"] + ": candidate is not declared by protocol")
            sat = p.get("saturation", {})
            if sat.get("result_count") != len(results) or sat.get("queries_covered") != len(p.get("queries", [])): issues.append(p["id"] + ": saturation counts do not match protocol")
            if p.get("contradiction_search", {}).get("performed") is not True: issues.append(p["id"] + ": contradiction search not executed")
    return {"passed": not issues, "issues": issues, "counts": {k: len(_load(root, k)) for k in ("protocols", "candidates", "decisions", "matrix", "transformed")}, "novelty_verdict": False, "complete_coverage": False}
