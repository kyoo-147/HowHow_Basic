from __future__ import annotations

from pathlib import Path
from typing import Any
import uuid
from .core import SCHEMA_VERSION, atomic_json, append_event, canonical, fail_record, now, read_json, safe_id, sha256_bytes, sha256_file, source_inspect

SEVERITIES = {"BLOCKING", "MAJOR", "MINOR", "DISSENT"}

def records(root: Path) -> list[dict[str, Any]]:
    return [read_json(p) for p in sorted((root / ".howhow/reviews").glob("*.json")) if p.parent.name == "reviews"]

def _source_binding_issue(root: Path, record: dict[str, Any]) -> str | None:
    source_id = record.get("source_id")
    try:
        safe_id(source_id, "source id")
        manifest = source_inspect(root, source_id)
    except SystemExit as exc:
        return str(exc)
    except (OSError, TypeError, ValueError):
        return f"source record unreadable for source_id {source_id}"
    locator = record.get("locator")
    if not isinstance(locator, dict) or type(locator.get("char_start")) is not int or type(locator.get("char_end")) is not int:
        return "source-bound review requires exact char_start and char_end"
    payload = root / ".howhow/sources/raw" / source_id / "payload"
    try:
        if not payload.is_file() or sha256_file(payload) != manifest.get("sha256"):
            return "source bytes failed integrity check"
        text = payload.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return "source bytes failed integrity check"
    start, end = locator["char_start"], locator["char_end"]
    if not (0 <= start <= end <= len(text)) or text[start:end] != record.get("quote", ""):
        return "review source span does not match retained source bytes"
    return None


def _run_binding_issue(root: Path, record: dict[str, Any]) -> str | None:
    run_id = record.get("run_id")
    try:
        safe_id(run_id, "run id")
    except SystemExit as exc:
        return str(exc)
    path = root / ".howhow/experiments" / f"{run_id}.json"
    if not path.exists():
        return f"unknown run_id {run_id}"
    try:
        run = read_json(path)
    except (OSError, ValueError):
        return f"experiment record unreadable for run_id {run_id}"
    if not isinstance(run, dict):
        return f"experiment record unreadable for run_id {run_id}"
    if run.get("id") != run_id:
        return f"run_id {run_id} does not match retained experiment"
    digest, unsigned = run.get("record_sha256"), dict(run)
    unsigned.pop("record_sha256", None)
    if not digest or digest != sha256_bytes(canonical(unsigned)):
        return f"experiment integrity check failed for run_id {run_id}"
    return None


def add(root: Path, descriptor: Path) -> dict[str, Any]:
    record = read_json(descriptor)
    required = ["id", "reviewer", "finding", "severity"]
    missing = [k for k in required if k not in record]
    if missing: raise SystemExit("review record missing: " + ", ".join(missing))
    safe_id(record["id"], "review id")
    if not isinstance(record["reviewer"], str) or not record["reviewer"].strip(): raise SystemExit("reviewer is required")
    if not isinstance(record["finding"], str) or not record["finding"].strip(): raise SystemExit("finding is required")
    if record["severity"] not in SEVERITIES: raise SystemExit("review severity must be BLOCKING, MAJOR, MINOR, or DISSENT")
    if not record.get("claim_id") and not record.get("claim"): raise SystemExit("review record requires claim_id or claim")
    source_bound, run_bound = bool(record.get("source_id")), bool(record.get("run_id"))
    if not source_bound and not run_bound: raise SystemExit("review record requires source span and/or experiment run")
    if source_bound:
        issue = _source_binding_issue(root, record)
        if issue: raise SystemExit(issue)
    if run_bound:
        issue = _run_binding_issue(root, record)
        if issue: raise SystemExit(issue)
    record["schema_version"], record["created_at"] = SCHEMA_VERSION, record.get("created_at", now())
    target = root / ".howhow/reviews" / f"{record['id']}.json"
    if target.exists(): raise SystemExit("review records are immutable; use a new id")
    old = records(root)
    record["previous_record_sha256"] = old[-1].get("record_sha256", "") if old else ""
    record["record_sha256"] = sha256_bytes(canonical(record))
    atomic_json(target, record)
    append_event(root, "review.recorded", {"review_id": record["id"], "severity": record["severity"]})
    return record

def audit(root: Path, strict: bool = False) -> dict[str, Any]:
    items, issues, previous = records(root), [], ""
    for record in items:
        if record.get("previous_record_sha256", "") != previous: issues.append(f"{record.get('id')}: review hash chain mismatch")
        digest, copy = record.get("record_sha256"), dict(record)
        copy.pop("record_sha256", None)
        if digest != sha256_bytes(canonical(copy)): issues.append(f"{record.get('id')}: review record hash mismatch")
        if record.get("severity") not in SEVERITIES: issues.append(f"{record.get('id')}: invalid severity")
        if not record.get("claim_id") and not record.get("claim"): issues.append(f"{record.get('id')}: missing claim binding")
        if not record.get("source_id") and not record.get("run_id"): issues.append(f"{record.get('id')}: missing evidence binding")
        if record.get("source_id"):
            issue = _source_binding_issue(root, record)
            if issue: issues.append(f"{record.get('id')}: {issue}")
        if record.get("run_id"):
            issue = _run_binding_issue(root, record)
            if issue: issues.append(f"{record.get('id')}: {issue}")
        previous = digest or ""
    result = {"schema_version": SCHEMA_VERSION, "records": len(items), "issues": issues, "passed": not issues}
    audit_id = "review-audit-" + uuid.uuid4().hex[:16]
    atomic_json(root / ".howhow/reviews/audits" / f"{audit_id}.json", result)
    append_event(root, "reviews.audited", {"audit_id": audit_id, "passed": result["passed"], "issues": len(issues)})
    if strict and issues: fail_record(root, "review_verify", "; ".join(issues), diagnosis="repair review chain or add a new immutable record")
    return result

def status(root: Path) -> dict[str, Any]:
    items = records(root)
    return {"records": len(items), "by_severity": {s: sum(item.get("severity") == s for item in items) for s in sorted(SEVERITIES)}, "human_review_required": True, "publication_decision": "HUMAN_OWNED"}
