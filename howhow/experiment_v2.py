from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import atomic_json, canonical, now, append_event, _append_event_locked, safe_id, sha256_bytes, sha256_file, read_json, run_experiment, project_lock

PROFILES = {"RECORD_ONLY", "TRUSTED_LOCAL"}
DISABLED_PROFILES = {"OS_ISOLATED", "CONTAINER_ISOLATED"}
MAX_TIMEOUT = 300

def _dir(root: Path, name: str) -> Path:
    p = root / ".howhow" / name
    p.mkdir(parents=True, exist_ok=True)
    return p

def _immutable(root: Path, folder: str, value: dict[str, Any], ident: str) -> dict[str, Any]:
    safe_id(ident)
    value = dict(value); value.update(schema_version=2, id=ident, created_at=now())
    unsigned = dict(value); unsigned.pop("record_sha256", None)
    value["record_sha256"] = sha256_bytes(canonical(unsigned))
    path = _dir(root, folder) / f"{ident}.json"
    if path.exists(): raise SystemExit("immutable record already exists: " + ident)
    atomic_json(path, value); append_event(root, folder.rstrip("s") + ".recorded", {"id": ident})
    return value

def _hash_declared(root: Path, path: str) -> str:
    if not isinstance(path, str) or not path or Path(path).is_absolute(): raise SystemExit("declared file must be project-relative")
    candidate = root / path
    resolved = candidate.resolve()
    try: resolved.relative_to(root.resolve())
    except ValueError as exc: raise SystemExit("declared file escapes project") from exc
    if candidate.is_symlink() or not resolved.is_file(): raise SystemExit("declared file must be a regular file: " + path)
    return sha256_file(resolved)

def proposal_create(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    required = ("id", "idea_id", "brief_id", "command", "cwd", "inputs", "outputs", "seed", "trust_profile", "policy_revision", "cleanup_plan", "evidence_plan", "bounds", "network")
    if not isinstance(value, dict) or any(k not in value for k in required): raise SystemExit("proposal requires: " + ", ".join(required))
    ident = safe_id(value["id"], "proposal id")
    design_level = value.get("design_level", "CONFIRMATORY")
    if design_level not in {"CONFIRMATORY", "EXPLORATORY"}: raise SystemExit("design_level must be CONFIRMATORY or EXPLORATORY")
    if design_level == "CONFIRMATORY":
        analysis_id = value.get("analysis_id")
        analysis = read_json(root / ".howhow/analysis" / f"{safe_id(analysis_id, 'analysis id')}.json") if analysis_id else None
        if not analysis or not _intact(analysis) or not _valid_objective(analysis): raise SystemExit("confirmatory execution requires a valid immutable analysis design")
    else:
        for field in ("baseline", "declared_change", "ablation_plan", "no_progress_policy", "objective_id"):
            if not value.get(field): raise SystemExit(f"exploratory proposal requires {field}")
        objective = read_json(root / ".howhow/analysis" / f"{safe_id(value['objective_id'], 'objective id')}.json")
        if not objective or not _intact(objective) or not _valid_objective(objective): raise SystemExit("exploratory execution requires a valid objective bundle")
    if value["trust_profile"] not in PROFILES: raise SystemExit("unsupported trust profile; OS_ISOLATED and CONTAINER_ISOLATED are disabled contracts")
    if not isinstance(value["command"], list) or not value["command"] or not all(isinstance(x, str) and x for x in value["command"]): raise SystemExit("executable and argv must be a non-empty array")
    if not isinstance(value["inputs"], list) or not isinstance(value["outputs"], list): raise SystemExit("inputs and outputs must be arrays")
    for p in value["inputs"]: _hash_declared(root, p)
    for p in value["outputs"]:
        if not isinstance(p, str) or not p or Path(p).is_absolute() or Path(p).is_symlink() or Path(p).name in {".", ".."}:
            raise SystemExit("outputs must be project-relative regular-file paths")
        resolved = (root / p).resolve()
        try: resolved.relative_to(root.resolve())
        except ValueError as exc: raise SystemExit("output escapes project") from exc
        if resolved.exists() and not resolved.is_file(): raise SystemExit("output must be a regular file path: " + p)
    executable = value["command"][0]
    if Path(executable).is_absolute():
        executable_path = Path(executable).resolve()
        if not executable_path.is_file() or executable_path.is_symlink(): raise SystemExit("absolute executable must be a regular file")
        executable_hash = sha256_file(executable_path)
    else:
        executable_hash = _hash_declared(root, executable)
    lock = value.get("dependency_lock")
    lock_hash = _hash_declared(root, lock) if lock else None
    bounds = value["bounds"]
    if not isinstance(bounds, dict) or not isinstance(bounds.get("timeout_seconds", 60), (int, float)) or bounds.get("timeout_seconds", 60) <= 0 or bounds.get("timeout_seconds", 60) > MAX_TIMEOUT: raise SystemExit("invalid bounded timeout")
    env_names = value.get("environment_names", list(value.get("environment", {}).keys()))
    if not isinstance(env_names, list) or not all(isinstance(x, str) for x in env_names): raise SystemExit("environment_names must be an array")
    if value["trust_profile"] == "TRUSTED_LOCAL": value["trusted_local_warning"] = "NOT SANDBOXED: host filesystem and network access remain possible"
    analysis_hash = None
    if value.get("analysis_id"):
        analysis = read_json(root / ".howhow/analysis" / f"{safe_id(value['analysis_id'], 'analysis id')}.json")
        analysis_hash = analysis.get("record_sha256") if analysis else None
    proposal = dict(value, design_level=design_level, executable_hash=executable_hash, input_hashes={p: _hash_declared(root, p) for p in value["inputs"]}, dependency_lock_hash=lock_hash, analysis_hash=analysis_hash, environment_names=env_names, status="PROPOSED")
    return _immutable(root, "proposals", proposal, ident)

def proposal_list(root: Path) -> list[dict[str, Any]]: return [read_json(p) for p in sorted(_dir(root, "proposals").glob("*.json"))]

def _intact(record: dict[str, Any]) -> bool:
    unsigned = dict(record); digest = unsigned.pop("record_sha256", None)
    return digest == sha256_bytes(canonical(unsigned))

def _valid_objective(value: dict[str, Any]) -> bool:
    return (isinstance(value.get("baseline"), (str, dict)) and bool(value.get("baseline"))
            and isinstance(value.get("primary_metrics"), list) and bool(value["primary_metrics"])
            and isinstance(value.get("outcome_definitions"), (dict, list)) and bool(value["outcome_definitions"])
            and isinstance(value.get("ablation_plan"), (dict, list))
            and isinstance(value.get("repetitions"), int) and not isinstance(value.get("repetitions"), bool) and value["repetitions"] >= 1
            and isinstance(value.get("uncertainty_method"), str) and bool(value["uncertainty_method"])
            and isinstance(value.get("known_confounders"), list)
            and isinstance(value.get("stopping_rules"), (dict, list)) and bool(value["stopping_rules"])
            and isinstance(value.get("no_progress_policy"), str) and bool(value["no_progress_policy"]))

def objective_save(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    required = ("id", "primary_metrics", "baseline", "outcome_definitions", "stopping_rules", "repetitions", "uncertainty_method", "known_confounders")
    if not isinstance(value, dict) or any(k not in value for k in required): raise SystemExit("analysis design is incomplete")
    if not _valid_objective(value): raise SystemExit("analysis design must declare baseline, one change, ablations, repetitions, uncertainty, confounders, and no-progress stopping")
    return _immutable(root, "analysis", dict(value, design_level=value.get("design_level", "CONFIRMATORY")), safe_id(value["id"], "analysis id"))

def grant_issue(root: Path, proposal_id: str, project_id: str, actor: str, expires_at: str, trust_profile: str | None = None, policy_revision: str | None = None) -> dict[str, Any]:
    proposal = read_json(root / ".howhow/proposals" / f"{safe_id(proposal_id)}.json")
    if not proposal or not _intact(proposal): raise SystemExit("proposal missing or tampered")
    if proposal.get("status") != "PROPOSED": raise SystemExit("proposal is not executable")
    if trust_profile and trust_profile != proposal.get("trust_profile"): raise SystemExit("trust profile mismatch")
    if policy_revision and policy_revision != proposal.get("policy_revision"): raise SystemExit("policy revision mismatch")
    ident = "grant-" + uuid.uuid4().hex[:16]
    return _immutable(root, "grants", {"proposal_id": proposal_id, "proposal_hash": proposal["record_sha256"], "project_id": project_id, "actor": actor, "nonce": uuid.uuid4().hex, "issued_at": now(), "expires_at": expires_at, "trust_profile": proposal["trust_profile"], "policy_revision": proposal["policy_revision"], "status": "ISSUED"}, ident)

def _expired(value: str) -> bool:
    try: return datetime.fromisoformat(value.replace("Z", "+00:00")) <= datetime.now(timezone.utc)
    except ValueError: return True

def doctor(root: Path, proposal_id: str) -> dict[str, Any]:
    proposal = read_json(root / ".howhow/proposals" / f"{safe_id(proposal_id)}.json")
    lock = proposal.get("dependency_lock") if proposal else None
    missing = []
    if lock and not (root / lock).is_file(): missing.append(lock)
    return {"proposal_id": proposal_id, "environment": "PREBUILT_ONLY", "missing_requirements": missing, "passed": not missing, "implicit_installation": False}

def run_grant(root: Path, grant_id: str) -> dict[str, Any]:
    grant = read_json(root / ".howhow/grants" / f"{safe_id(grant_id)}.json")
    if not grant or not _intact(grant): raise SystemExit("grant missing or tampered")
    events = root / ".howhow/events.jsonl"
    proposal = read_json(root / ".howhow/proposals" / f"{grant['proposal_id']}.json")
    if not proposal or not _intact(proposal) or proposal.get("record_sha256") != grant.get("proposal_hash"): raise SystemExit("proposal hash mismatch")
    if proposal.get("trust_profile") not in PROFILES: raise SystemExit("unsupported trust profile")
    if proposal.get("executable_hash") and proposal.get("command"):
        executable = Path(proposal["command"][0])
        current_hash = sha256_file(executable.resolve()) if executable.is_absolute() else _hash_declared(root, proposal["command"][0])
        if current_hash != proposal["executable_hash"]: raise SystemExit("executable/script mutation detected")
    for path, digest in proposal.get("input_hashes", {}).items():
        if _hash_declared(root, path) != digest: raise SystemExit("declared input mutation detected: " + path)
    if proposal.get("idea_id") and not any(read_json(p).get("idea_id") == proposal["idea_id"] and read_json(p).get("status") == "SELECTED" for p in _dir(root, "selections").glob("*.json")): raise SystemExit("idea is not selected")
    brief = read_json(root / ".howhow/briefs" / f"{safe_id(proposal.get('brief_id', ''), 'brief id')}.json") if proposal.get("brief_id") else None
    if not brief or brief.get("status") != "CONFIRMED": raise SystemExit("the exact brief must be confirmed")
    if proposal.get("design_level", "CONFIRMATORY") == "CONFIRMATORY":
        analysis = read_json(root / ".howhow/analysis" / f"{safe_id(proposal.get('analysis_id'), 'analysis id')}.json")
        if not analysis or not _intact(analysis) or not _valid_objective(analysis) or analysis.get("record_sha256") != proposal.get("analysis_hash"): raise SystemExit("confirmatory analysis binding mismatch")
    if proposal.get("dependency_lock") and (not doctor(root, proposal["id"])["passed"] or _hash_declared(root, proposal["dependency_lock"]) != proposal.get("dependency_lock_hash")): raise SystemExit("dependency lock missing or mutated")
    # Recheck and consume while holding the project lock; this is the one-shot claim.
    with project_lock(root):
        if events.exists() and any(json.loads(line).get("event") == "grant.consumed" and json.loads(line).get("data", {}).get("grant_id") == grant_id for line in events.read_text(encoding="utf-8").splitlines() if line): raise SystemExit("grant already consumed or unavailable")
        if grant.get("status") != "ISSUED" or _expired(grant.get("expires_at", "")): raise SystemExit("grant already consumed or unavailable")
        _append_event_locked(root, "grant.consumed", {"grant_id": grant_id, "nonce": grant["nonce"], "proposal_hash": grant["proposal_hash"]})
    # The grant remains immutable; the hash-chained consumption event is the source of replay state.
    spec = dict(proposal, id="result-" + uuid.uuid4().hex[:16], hypothesis=proposal.get("hypothesis", proposal.get("idea_id", "experiment")), command=proposal["command"], code_revision=proposal.get("script_hash") or proposal.get("executable_hash") or "declared", seed=proposal["seed"], inputs=proposal["inputs"], environment=proposal.get("environment", {}), timeout_seconds=proposal["bounds"].get("timeout_seconds", 60), proposal_hash=proposal["record_sha256"], grant_id=grant_id, trust_profile=proposal["trust_profile"])
    descriptor = root / ".howhow" / ("v2-spec-" + uuid.uuid4().hex + ".json"); atomic_json(descriptor, spec)
    try: return run_experiment(root, descriptor)
    finally: descriptor.unlink(missing_ok=True)

def experiment_audit(root: Path) -> dict[str, Any]:
    issues=[]
    consumed = set()
    events = root / ".howhow/events.jsonl"
    if events.exists():
        for line in events.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
                if event.get("event") == "grant.consumed": consumed.add(event.get("data", {}).get("grant_id"))
            except ValueError: issues.append("events: unreadable event")
    for folder in ("proposals", "grants", "analysis"):
        for p in _dir(root, folder).glob("*.json"):
            r=read_json(p)
            if p.stem != r.get("id") or not _intact(r): issues.append(f"{folder}/{p.name}: immutable hash mismatch")
    if len(consumed) != len([x for x in consumed if x]): issues.append("grant consumption contains duplicate or missing grant ids")
    return {"passed": not issues, "issues": issues, "consumed_grants": sorted(x for x in consumed if x)}
