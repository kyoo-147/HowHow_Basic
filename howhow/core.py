from __future__ import annotations

import contextlib
import re
import signal

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_SOURCE_BYTES = 8 * 1024 * 1024

def safe_id(value: Any, label: str = "id") -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise SystemExit(f"invalid {label}: use 1-128 letters, digits, '.', '_' or '-'")
    return value

@contextlib.contextmanager
def project_lock(root: Path):
    lock = root / ".howhow" / ".lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = datetime.now().timestamp() + 15
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if datetime.now().timestamp() >= deadline:
                raise SystemExit("project is busy; retry later")
            import time
            time.sleep(0.05)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
TERMINAL = {"COMPLETE", "FAILED", "BLOCKED", "CANCELLED"}
LABELS = {"VERIFIED", "UNVERIFIED", "BLOCKED", "USER ACTION REQUIRED LATER", "SKIP"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temp.write_bytes(canonical(value) + b"\n")
    os.replace(temp, path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def project_root(path: str | Path = ".") -> Path:
    root = Path(path).resolve()
    if (root / ".howhow" / "config.json").exists():
        return root
    current = root
    for parent in [root, *root.parents]:
        if (parent / ".howhow" / "config.json").exists():
            return parent
    raise SystemExit("not a HowHow project: .howhow/config.json was not found")


def event_path(root: Path) -> Path:
    return root / ".howhow" / "events.jsonl"


def state_path(root: Path) -> Path:
    return root / ".howhow" / "state.json"


def append_event(root: Path, event: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    with project_lock(root):
        return _append_event_locked(root, event, data)


def _append_event_locked(root: Path, event: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or {}
    events = event_path(root)
    previous = ""
    if events.exists():
        lines = [line for line in events.read_text(encoding="utf-8").splitlines() if line]
        if lines:
            previous = json.loads(lines[-1]).get("record_sha256", "")
    record = {"schema_version": SCHEMA_VERSION, "event_id": "evt-" + uuid.uuid4().hex[:16], "event": event, "created_at": now(), "previous_record_sha256": previous, "data": data}
    record["record_sha256"] = sha256_bytes(canonical(record))
    events.parent.mkdir(parents=True, exist_ok=True)
    with events.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    state = read_json(state_path(root), {})
    state["last_event_id"] = record["event_id"]
    state["last_event"] = event
    state["updated_at"] = record["created_at"]
    atomic_json(state_path(root), state)
    return record


def fail_record(root: Path, stage: str, error: str, command: list[str] | None = None, inputs: list[str] | None = None, diagnosis: str = "") -> dict[str, Any]:
    item = {"failure_id": "failure-" + uuid.uuid4().hex[:16], "stage": stage, "input_hashes": inputs or [], "command": command or [], "exit_code": 1, "error": error, "diagnosis": diagnosis, "resolution": "open", "created_at": now()}
    item["record_sha256"] = sha256_bytes(canonical(item))
    path = root / ".howhow" / "failures.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = ""
    if path.exists() and path.read_text(encoding="utf-8").strip():
        previous = json.loads(path.read_text(encoding="utf-8").splitlines()[-1]).get("record_sha256", "")
    item["previous_record_sha256"] = previous
    item["record_sha256"] = sha256_bytes(canonical(item))
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n")
    append_event(root, "failure.recorded", {"failure_id": item["failure_id"], "stage": stage})
    return item


def init_project(directory: str, goal: str | None = None) -> Path:
    root = Path(directory).resolve()
    if root.exists() and any(root.iterdir()) and (root / ".howhow" / "config.json").exists():
        return root
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"refusing to overwrite unrelated directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    dirs = ["sources/raw", "sources/records", "evidence/audits", "experiments", "runs", "builds", "verify", "reviews", "paper/figures", "paper/tables", "dist", "phases", "waves", "tasks/queued", "tasks/running", "tasks/done", "tasks/blocked", "attempts"]
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
    config = {"schema_version": SCHEMA_VERSION, "name": root.name, "paper_root": "paper", "build_engine": "pdflatex", "created_at": now()}
    atomic_json(root / ".howhow/config.json", config)
    atomic_json(root / ".howhow/mission.json", {"schema_version": SCHEMA_VERSION, "mission_id": "mission-" + uuid.uuid4().hex[:16], "goal": goal or "", "status": "NEW", "phases": [], "budget": {"wall_seconds": None, "api_requests": None, "storage_bytes": None}})
    atomic_json(root / ".howhow/state.json", {"schema_version": SCHEMA_VERSION, "state": "NEW", "paused": False, "current_task": None, "last_event_id": None})
    atomic_json(root / ".howhow/plan.json", {"schema_version": SCHEMA_VERSION, "objective": goal or "", "tasks": []})
    (root / "HOWHOW.md").write_text("# HowHow Research Project\n\n## Goal\n\n" + (goal or "Add a goal with `howhow plan save`.\n"), encoding="utf-8")
    (root / "paper/main.tex").write_text(r"""\\documentclass{article}
\\usepackage[margin=1in]{geometry}
\\usepackage{booktabs}
\\usepackage{graphicx}
\\title{HowHow Research Report}
\\author{HowHow Basic}
\\date{\\today}
\\begin{document}
\\maketitle
\\begin{abstract}
This manuscript is a generated project scaffold. Replace this text with claims linked to verified evidence and executed runs.
\\end{abstract}
\\section{Introduction}
The project goal and limitations are recorded in the project manifest.
\\section{Reproducibility}
All reported results must be generated from immutable experiment records.
\\bibliographystyle{plain}
\\bibliography{references}
\\end{document}
""".replace("\\\\", "\\"), encoding="utf-8")
    (root / "paper/references.bib").write_text("% Add only verified bibliography records.\n", encoding="utf-8")
    # Phase A files are deliberately local and deterministic; keep opinion empty.
    from .vnext import init_vnext
    init_vnext(root)
    append_event(root, "project.created", {"goal": goal or "", "root": root.name})
    return root


def save_plan(root: Path, source: Path) -> dict[str, Any]:
    plan = read_json(source)
    if not isinstance(plan, dict) or not isinstance(plan.get("tasks"), list):
        raise SystemExit("plan must be a JSON object with a tasks array")
    ids: set[str] = set()
    for task in plan["tasks"]:
        if not isinstance(task, dict) or not task.get("id") or task["id"] in ids:
            raise SystemExit("plan tasks require unique ids")
        safe_id(task["id"], "task id")
        ids.add(task["id"])
        if not isinstance(task.get("acceptance", []), list) or not isinstance(task.get("required_evidence", []), list):
            raise SystemExit(f"invalid acceptance/evidence for task {task['id']}")
    plan["schema_version"] = SCHEMA_VERSION
    atomic_json(root / ".howhow/plan.json", plan)
    state = read_json(state_path(root), {})
    state.update({"state": "READY", "plan_hash": "sha256:" + sha256_bytes(canonical(plan)), "current_task": plan["tasks"][0]["id"] if plan["tasks"] else None, "paused": False})
    atomic_json(state_path(root), state)
    append_event(root, "plan.saved", {"plan_hash": state["plan_hash"], "task_count": len(plan["tasks"])})
    return plan


def source_add(root: Path, location: str, license_name: str = "UNVERIFIED") -> dict[str, Any]:
    parsed = urllib.parse.urlparse(location)
    if parsed.username or parsed.password:
        raise SystemExit("source URL must not contain credentials")
    if parsed.scheme in {"http", "https"}:
        if parsed.hostname not in {"export.arxiv.org", "arxiv.org", "api.openalex.org"}:
            raise SystemExit("source URL host is not on the approved allowlist")
        class ApprovedRedirects(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                target = urllib.parse.urlparse(newurl)
                if target.hostname not in {"export.arxiv.org", "arxiv.org", "api.openalex.org"} or target.username or target.password:
                    raise SystemExit("redirected source URL is not approved")
                return super().redirect_request(req, fp, code, msg, headers, newurl)
        request = urllib.request.Request(location, headers={"User-Agent": "HowHow-Basic/0.1 (+local research tool)"})
        opener = urllib.request.build_opener(ApprovedRedirects)
        with opener.open(request, timeout=30) as response:
            if int(response.headers.get("Content-Length", "0") or 0) > MAX_SOURCE_BYTES:
                raise SystemExit("source exceeds the 8 MiB limit")
            chunks = []
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_SOURCE_BYTES:
                    raise SystemExit("source exceeds the 8 MiB limit")
                chunks.append(chunk)
            payload = b"".join(chunks)
            final_url = response.geturl()
            final = urllib.parse.urlparse(final_url)
            if final.hostname not in {"export.arxiv.org", "arxiv.org", "api.openalex.org"} or final.username or final.password:
                raise SystemExit("redirected source URL is not approved")
            media_type = response.headers.get_content_type()
    else:
        path = Path(location).resolve()
        if not path.is_file():
            raise SystemExit(f"source file not found: {location}")
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise SystemExit("source exceeds the 8 MiB limit")
        with path.open("rb") as source_file:
            payload = source_file.read(MAX_SOURCE_BYTES + 1)
        if len(payload) > MAX_SOURCE_BYTES:
            raise SystemExit("source exceeds the 8 MiB limit")
        final_url, media_type = path.as_uri(), "application/octet-stream"
    digest = sha256_bytes(payload)
    source_id = "src-" + digest[:16]
    target = root / ".howhow/sources/raw" / source_id
    target.mkdir(parents=True, exist_ok=True)
    payload_path = target / "payload"
    if payload_path.exists() and sha256_file(payload_path) != digest:
        raise SystemExit("source identity collision: existing bytes differ")
    if not payload_path.exists():
        temp = target / "payload.tmp"
        temp.write_bytes(payload)
        os.replace(temp, payload_path)
    manifest = {"schema_version": SCHEMA_VERSION, "source_id": source_id, "canonical_url": final_url, "requested_url": location, "retrieved_at": now(), "license": license_name, "media_type": media_type, "byte_length": len(payload), "sha256": digest, "access_status": "retrieved", "provenance": "official-url" if parsed.scheme else "local-file"}
    atomic_json(target / "manifest.json", manifest)
    atomic_json(root / ".howhow/sources/records" / f"{source_id}.json", manifest)
    append_event(root, "source.retrieved", {"source_id": source_id, "sha256": digest, "url": final_url})
    return manifest


def source_search(root: Path, provider: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    if provider == "arxiv":
        url = "https://export.arxiv.org/api/query?search_query=all:" + urllib.parse.quote(query) + f"&start=0&max_results={limit}"
        request = urllib.request.Request(url, headers={"User-Agent": "HowHow-Basic/0.1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8", errors="replace")
        import re
        entries = []
        for block in re.findall(r"<entry>(.*?)</entry>", text, re.S):
            ident = re.search(r"<id>(.*?)</id>", block)
            title = re.search(r"<title>(.*?)</title>", block, re.S)
            summary = re.search(r"<summary>(.*?)</summary>", block, re.S)
            entries.append({"provider": "arxiv", "id": ident.group(1).strip() if ident else "", "title": " ".join((title.group(1) if title else "").split()), "summary": " ".join((summary.group(1) if summary else "").split()), "query": query, "retrieved_at": now()})
        return entries
    if provider == "openalex":
        url = "https://api.openalex.org/works?search=" + urllib.parse.quote(query) + f"&per-page={limit}"
        request = urllib.request.Request(url, headers={"User-Agent": "HowHow-Basic/0.1 (mailto:howhow@example.invalid)"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode())
        return [{"provider": "openalex", "id": item.get("id", ""), "title": item.get("title", ""), "doi": item.get("doi"), "publication_year": item.get("publication_year"), "query": query, "retrieved_at": now()} for item in data.get("results", [])]
    raise SystemExit("provider must be arxiv or openalex")


def source_inspect(root: Path, source_id: str) -> dict[str, Any]:
    safe_id(source_id, "source id")
    manifest = read_json(root / ".howhow/sources/records" / f"{source_id}.json")
    if not manifest:
        raise SystemExit(f"unknown source: {source_id}")
    payload = root / ".howhow/sources/raw" / source_id / "payload"
    manifest["payload_exists"] = payload.exists()
    manifest["payload_path"] = str(payload.relative_to(root))
    return manifest


def source_pin(root: Path, source_id: str, revision: str) -> dict[str, Any]:
    manifest = source_inspect(root, source_id)
    pin = {"schema_version": SCHEMA_VERSION, "source_id": source_id, "revision": revision, "pinned_at": now(), "source_sha256": manifest["sha256"]}
    atomic_json(root / ".howhow/sources/records" / f"{source_id}.pin.json", pin)
    append_event(root, "source.pinned", {"source_id": source_id, "revision": revision})
    return pin


def source_use(root: Path, source_id: str) -> dict[str, Any]:
    manifest = source_inspect(root, source_id)
    if not manifest["payload_exists"] or sha256_file(root / ".howhow/sources/raw" / source_id / "payload") != manifest["sha256"]:
        raise SystemExit("source bytes failed integrity check")
    return {"source_id": source_id, "path": manifest["payload_path"], "sha256": manifest["sha256"], "read_only": True}

def source_list(root: Path) -> list[dict[str, Any]]:
    return [read_json(path) for path in sorted((root / ".howhow/sources/records").glob("*.json")) if not path.name.endswith(".pin.json")]


def add_evidence(root: Path, descriptor: Path) -> dict[str, Any]:
    record = read_json(descriptor)
    if not isinstance(record, dict) or not record.get("id"):
        raise SystemExit("evidence descriptor requires id")
    safe_id(record["id"], "evidence id")
    status = record.get("status", "UNVERIFIED")
    if status not in LABELS:
        raise SystemExit("evidence status must be one of VERIFIED, UNVERIFIED, BLOCKED, USER ACTION REQUIRED LATER, SKIP")
    record["schema_version"] = SCHEMA_VERSION
    record["created_at"] = record.get("created_at", now())
    record["record_sha256"] = sha256_bytes(canonical(record))
    target = root / ".howhow/evidence" / f"{record['id']}.json"
    if target.exists() and read_json(target).get("record_sha256") != record["record_sha256"]:
        raise SystemExit("evidence is immutable; use a new id for corrections")
    atomic_json(target, record)
    append_event(root, "evidence.registered", {"evidence_id": record["id"], "status": status})
    return record


def audit_evidence(root: Path, strict: bool = False) -> dict[str, Any]:
    sources = {item["source_id"]: item for item in source_list(root)}
    transformed = {p.stem: read_json(p) for p in (root / ".howhow/literature/transformed").glob("*.json")}
    records = [read_json(p) for p in sorted((root / ".howhow/evidence").glob("*.json"))]
    issues: list[str] = []
    checked = 0
    for record in records:
        evidence_id = record.get("id")
        digest, unsigned = record.get("record_sha256"), dict(record)
        unsigned.pop("record_sha256", None)
        if not digest or digest != sha256_bytes(canonical(unsigned)):
            issues.append(f"{evidence_id}: evidence record hash mismatch")
        sid = record.get("source_id")
        transformed_id = record.get("transformed_source_id")
        source = sources.get(sid) if sid else None
        derived = transformed.get(transformed_id) if transformed_id else None
        if record.get("status") == "VERIFIED" and ((not source and not derived) or (source and derived) or not record.get("quote") or not isinstance(record.get("locator"), dict)):
            issues.append(f"{record.get('id')}: VERIFIED evidence requires exactly one source/derived source, quote, and locator")
        if record.get("status") == "VERIFIED" and ("claim" in record or "run_id" in record) and not isinstance(record.get("run_id"), str):
            issues.append(f"{record.get('id')}: VERIFIED evidence requires run_id")
        if sid and source:
            payload = root / ".howhow/sources/raw" / sid / "payload"
            if not payload.exists() or sha256_file(payload) != source.get("sha256"):
                issues.append(f"{record.get('id')}: source hash mismatch")
            text = payload.read_bytes().decode("utf-8", errors="replace") if payload.exists() else ""
            locator = record.get("locator", {})
            if record.get("status") == "VERIFIED" and not {"char_start", "char_end"} <= set(locator):
                issues.append(f"{record.get('id')}: VERIFIED evidence requires exact char_start and char_end")
            if "char_start" in locator and "char_end" in locator:
                start, end = locator["char_start"], locator["char_end"]
                if type(start) is not int or type(end) is not int or not (0 <= start <= end <= len(text)):
                    issues.append(f"{record.get("id")}: invalid evidence span")
                    continue
                quote = text[start:end]
                if quote != record.get("quote", ""):
                    issues.append(f"{record.get('id')}: quote does not match source span")
                if record.get("status") == "VERIFIED":
                    checked += 1
        if transformed_id and derived:
            extracted = root / ".howhow/literature" / derived.get("extracted_path", "")
            parent_id = derived.get("parent_source_id")
            parent = sources.get(parent_id)
            raw = root / ".howhow/sources/raw" / str(parent_id) / "payload"
            if not parent or not raw.exists() or sha256_file(raw) != parent.get("sha256") or parent.get("sha256") != derived.get("original_sha256"):
                issues.append(f"{record.get('id')}: transformed parent integrity failed")
            if not extracted.exists() or sha256_file(extracted) != derived.get("extracted_sha256"):
                issues.append(f"{record.get('id')}: transformed text integrity failed")
            locator = record.get("locator", {})
            if record.get("status") == "VERIFIED" and not {"char_start", "char_end"} <= set(locator):
                issues.append(f"{record.get('id')}: derived VERIFIED evidence requires exact char_start and char_end")
            if {"char_start", "char_end"} <= set(locator) and extracted.exists():
                text = extracted.read_bytes().decode("utf-8", errors="replace")
                start, end = locator["char_start"], locator["char_end"]
                if type(start) is not int or type(end) is not int or not (0 <= start <= end <= len(text)) or text[start:end] != record.get("quote", ""):
                    issues.append(f"{record.get('id')}: quote does not match transformed text span")
        if record.get("status") == "VERIFIED" and isinstance(record.get("run_id"), str):
            run_id = record["run_id"]
            try:
                safe_id(run_id, "run id")
            except SystemExit as exc:
                issues.append(f"{record.get('id')}: {exc}")
            else:
                run_path = root / ".howhow/experiments" / f"{run_id}.json"
                if not run_path.exists():
                    issues.append(f"{record.get('id')}: unknown run_id {run_id}")
                else:
                    try:
                        run = read_json(run_path)
                    except (OSError, ValueError):
                        run = None
                    if not isinstance(run, dict):
                        issues.append(f"{record.get('id')}: experiment record unreadable for run_id {run_id}")
                    elif run.get("id") != run_id:
                        issues.append(f"{record.get('id')}: run_id {run_id} does not match retained experiment")
                    else:
                        run_digest, run_unsigned = run.get("record_sha256"), dict(run)
                        run_unsigned.pop("record_sha256", None)
                        if not run_digest or run_digest != sha256_bytes(canonical(run_unsigned)):
                            issues.append(f"{record.get('id')}: experiment integrity check failed for run_id {run_id}")
        if sid and not source:
            issues.append(f"{record.get('id')}: unknown source {sid}")
        if strict and record.get("status") != "VERIFIED":
            issues.append(f"{record.get('id')}: status is not VERIFIED")
    result = {"schema_version": SCHEMA_VERSION, "checked": checked, "records": len(records), "issues": issues, "passed": not issues}
    audit_id = "audit-" + uuid.uuid4().hex[:16]
    atomic_json(root / ".howhow/evidence/audits" / f"{audit_id}.json", result)
    append_event(root, "evidence.audited", {"audit_id": audit_id, "passed": result["passed"], "issues": len(issues)})
    if strict and issues:
        fail_record(root, "evidence_verify", "; ".join(issues), diagnosis="repair evidence or create a new immutable revision")
    return result


EXPERIMENT_REQUIRED_FIELDS = ("id", "hypothesis", "command", "status", "raw_observations", "metrics", "code_revision", "seed")
EXPERIMENT_SPEC_REQUIRED_FIELDS = ("id", "hypothesis", "command", "code_revision", "seed")
MAX_EXPERIMENT_INPUT_BYTES = 8 * 1024 * 1024
MAX_EXPERIMENT_OUTPUT_BYTES = 1024 * 1024
MAX_EXPERIMENT_TIMEOUT_SECONDS = 300
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _experiment_input(root: Path, relative: str) -> tuple[Path, Path]:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise SystemExit("experiment inputs must be non-empty project-relative paths")
    candidate = root / relative
    source = candidate.resolve()
    try:
        destination = source.relative_to(root.resolve())
    except ValueError as exc:
        raise SystemExit(f"experiment input escapes project: {relative}") from exc
    if candidate.is_symlink() or not source.is_file():
        raise SystemExit(f"experiment input must be a regular non-symlink file: {relative}")
    return source, destination


def run_experiment(root: Path, spec_path: Path) -> dict[str, Any]:
    """Execute one declared command in an isolated temporary working directory.

    This is a bounded local runner, not an OS security sandbox: it limits time,
    retained output, working directory contents, and inherited environment, but
    cannot prevent a hostile executable from accessing the host or network.
    """
    spec = read_json(spec_path)
    if not isinstance(spec, dict):
        raise SystemExit("experiment run specification must be a JSON object")
    missing = [key for key in EXPERIMENT_SPEC_REQUIRED_FIELDS if key not in spec]
    if missing:
        raise SystemExit("experiment run specification missing: " + ", ".join(missing))
    experiment_id = safe_id(spec["id"], "experiment id")
    if (root / ".howhow/experiments" / f"{experiment_id}.json").exists():
        raise SystemExit("experiment records are immutable; use a new id")
    command = spec["command"]
    if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
        raise SystemExit("experiment command must be a non-empty array of strings")
    if not isinstance(spec["hypothesis"], str) or not spec["hypothesis"].strip():
        raise SystemExit("experiment hypothesis must be a non-empty string")
    if not isinstance(spec["code_revision"], str) or not spec["code_revision"].strip():
        raise SystemExit("experiment code_revision must be a non-empty string")
    if isinstance(spec["seed"], bool) or not isinstance(spec["seed"], int) or not 0 <= spec["seed"] <= 4294967295:
        raise SystemExit("experiment seed must be an integer from 0 through 4294967295")
    inputs = spec.get("inputs", [])
    outputs = spec.get("outputs", [])
    if not isinstance(outputs, list) or not all(isinstance(item, str) and item and not Path(item).is_absolute() and ".." not in PurePosixPath(item).parts and PurePosixPath(item).name not in {"", "."} for item in outputs):
        raise SystemExit("experiment outputs must be project-relative regular-file paths")
    if not isinstance(inputs, list) or not all(isinstance(item, str) for item in inputs):
        raise SystemExit("experiment inputs must be an array of project-relative paths")
    if len(set(inputs)) != len(inputs):
        raise SystemExit("experiment inputs must be unique")
    timeout = spec.get("timeout_seconds", 60)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > MAX_EXPERIMENT_TIMEOUT_SECONDS:
        raise SystemExit(f"experiment timeout_seconds must be > 0 and <= {MAX_EXPERIMENT_TIMEOUT_SECONDS}")
    declared_env = spec.get("environment", {})
    if not isinstance(declared_env, dict) or not all(
        isinstance(key, str) and ENV_NAME.fullmatch(key) and isinstance(value, str)
        for key, value in declared_env.items()
    ):
        raise SystemExit("experiment environment must map valid variable names to strings")
    reserved = {"HOWHOW_SEED", "PYTHONHASHSEED", "TEMP", "TMP"}
    if reserved.intersection(declared_env):
        raise SystemExit("experiment environment cannot override HOWHOW_SEED, PYTHONHASHSEED, TEMP, or TMP")

    resolved_inputs: list[tuple[Path, Path]] = []
    total_input_bytes = 0
    for item in inputs:
        source, relative = _experiment_input(root, item)
        total_input_bytes += source.stat().st_size
        if total_input_bytes > MAX_EXPERIMENT_INPUT_BYTES:
            raise SystemExit(f"experiment inputs exceed {MAX_EXPERIMENT_INPUT_BYTES} bytes")
        resolved_inputs.append((source, relative))

    with tempfile.TemporaryDirectory(prefix="howhow-experiment-") as temp:
        work = Path(temp)
        input_manifest = []
        for source, relative in resolved_inputs:
            destination = work / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            input_manifest.append({"path": relative.as_posix(), "bytes": destination.stat().st_size, "sha256": sha256_file(destination)})
        stdout_path, stderr_path = work / ".howhow-stdout", work / ".howhow-stderr"
        env = {key: os.environ[key] for key in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC") if key in os.environ}
        env.update(declared_env)
        env.update({"HOWHOW_SEED": str(spec["seed"]), "PYTHONHASHSEED": str(spec["seed"]), "TEMP": temp, "TMP": temp})
        started = time.monotonic()
        timed_out = False
        launch_error = None
        returncode = None
        with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
            try:
                launch_kwargs = {"cwd": work, "env": env, "stdout": stdout_file, "stderr": stderr_file, "shell": False}
                if os.name == "nt":
                    launch_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    launch_kwargs["start_new_session"] = True
                process = subprocess.Popen(command, **launch_kwargs)
                try:
                    returncode = process.wait(timeout=float(timeout))
                except subprocess.TimeoutExpired:
                    timed_out = True
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    else:
                        try: os.killpg(process.pid, signal.SIGKILL)
                        except (OSError, ProcessLookupError): process.kill()
                    returncode = process.wait()
            except OSError as exc:
                launch_error = f"{type(exc).__name__}: {exc}"
        elapsed = time.monotonic() - started
        stdout_size, stderr_size = stdout_path.stat().st_size, stderr_path.stat().st_size
        with stdout_path.open("rb") as stream:
            stdout_bytes = stream.read(MAX_EXPERIMENT_OUTPUT_BYTES)
        with stderr_path.open("rb") as stream:
            stderr_bytes = stream.read(MAX_EXPERIMENT_OUTPUT_BYTES)
        output_overflow = stdout_size > MAX_EXPERIMENT_OUTPUT_BYTES or stderr_size > MAX_EXPERIMENT_OUTPUT_BYTES
        retained_stdout = stdout_bytes.decode("utf-8", errors="replace")
        retained_stderr = stderr_bytes.decode("utf-8", errors="replace")
        status = "SUCCESS" if returncode == 0 and not timed_out and not output_overflow and launch_error is None else "FAILED"
        error = None
        if launch_error:
            error = "command launch failed: " + launch_error
        elif timed_out:
            error = f"command timed out after {timeout} seconds"
        elif output_overflow:
            error = f"command output exceeded {MAX_EXPERIMENT_OUTPUT_BYTES} bytes per stream"
        elif returncode != 0:
            error = f"command exited with status {returncode}"
        record = {
            "id": experiment_id,
            "hypothesis": spec["hypothesis"],
            "command": command,
            "status": status,
            "raw_observations": [{
                "stdout": retained_stdout,
                "stderr": retained_stderr,
                "stdout_truncated": stdout_size > MAX_EXPERIMENT_OUTPUT_BYTES,
                "stderr_truncated": stderr_size > MAX_EXPERIMENT_OUTPUT_BYTES,
                "exit_status": returncode,
                "timed_out": timed_out,
            }],
            "metrics": {
                "elapsed_seconds": round(elapsed, 6),
                "stdout_bytes": stdout_size,
                "stderr_bytes": stderr_size,
            },
            "code_revision": spec["code_revision"],
            "seed": spec["seed"],
            "cwd": spec.get("cwd", "."),
            "inputs": input_manifest,
            "outputs": [{"path": path, "exists": (work / path).is_file(), "sha256": sha256_file(work / path) if (work / path).is_file() else None} for path in spec.get("outputs", []) if isinstance(path, str) and not Path(path).is_absolute() and Path(path).name not in {".", ".."}],
            "cleanup": {"plan": spec.get("cleanup_plan", "temporary work directory"), "validated": True, "mechanism": "TemporaryDirectory", "evidence": "context cleanup is applied after record construction"},
            "environment": declared_env,
            "runner": {
                "kind": "bounded-local-isolated-workdir",
                "timeout_seconds": timeout,
                "max_output_bytes_per_stream": MAX_EXPERIMENT_OUTPUT_BYTES,
                "host_access_prevented": False,
                "network_access_prevented": False,
                "trust_profile": spec.get("trust_profile", "TRUSTED_LOCAL"),
                "limitations": "not sandboxed; host filesystem and network access are not prevented",
            },
        }
        for binding in ("proposal_hash", "grant_id", "trust_profile"):
            if binding in spec:
                record[binding] = spec[binding]
        if error is not None:
            record["error"] = error
        descriptor = work / "record.json"
        atomic_json(descriptor, record)
        return record_experiment(root, descriptor)


def experiment_record_issues(record: Any, expected_id: str | None = None) -> list[str]:
    """Return deterministic validation failures for a retained experiment record."""
    if not isinstance(record, dict):
        return ["record is not a JSON object"]
    issues: list[str] = []
    missing = [key for key in EXPERIMENT_REQUIRED_FIELDS if key not in record]
    if missing:
        issues.append("missing required fields: " + ", ".join(missing))
    experiment_id = record.get("id")
    try:
        safe_id(experiment_id, "experiment id")
    except SystemExit as exc:
        issues.append(str(exc))
    if expected_id is not None and experiment_id != expected_id:
        issues.append(f"filename id {expected_id} does not match record id {experiment_id}")
    status = record.get("status")
    if status not in {"SUCCESS", "FAILED", "INCONCLUSIVE"}:
        issues.append("invalid status")
    if not isinstance(record.get("hypothesis"), str) or not record.get("hypothesis", "").strip():
        issues.append("hypothesis must be a non-empty string")
    command = record.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
        issues.append("command must be a non-empty array of strings")
    if not isinstance(record.get("code_revision"), str) or not record.get("code_revision", "").strip():
        issues.append("code_revision must be a non-empty string")
    observations, metrics = record.get("raw_observations"), record.get("metrics")
    if not isinstance(observations, list):
        issues.append("raw_observations must be an array")
    if not isinstance(metrics, dict):
        issues.append("metrics must be an object")
    if status in {"SUCCESS", "INCONCLUSIVE"} and (not observations or not metrics):
        issues.append(f"{status} requires raw observations and metrics")
    if status == "FAILED" and (not isinstance(record.get("error"), str) or not record.get("error", "").strip()):
        issues.append("FAILED requires a non-empty error")
    digest, unsigned = record.get("record_sha256"), dict(record)
    unsigned.pop("record_sha256", None)
    if not digest or digest != sha256_bytes(canonical(unsigned)):
        issues.append("record hash mismatch")
    return issues


def record_experiment(root: Path, descriptor: Path) -> dict[str, Any]:
    record = read_json(descriptor)
    missing = [key for key in EXPERIMENT_REQUIRED_FIELDS if key not in record]
    if missing:
        raise SystemExit("experiment record missing: " + ", ".join(missing))
    if record["status"] not in {"SUCCESS", "FAILED", "INCONCLUSIVE"}:
        raise SystemExit("experiment status must be SUCCESS, FAILED, or INCONCLUSIVE")
    safe_id(record["id"], "experiment id")
    record["schema_version"] = SCHEMA_VERSION
    record["recorded_at"] = record.get("recorded_at", now())
    record["record_sha256"] = sha256_bytes(canonical(record))
    issues = experiment_record_issues(record, record["id"])
    if issues:
        raise SystemExit("invalid experiment record: " + "; ".join(issues))
    target = root / ".howhow/experiments" / f"{record['id']}.json"
    if target.exists():
        raise SystemExit("experiment records are immutable; use a new id")
    atomic_json(target, record)
    append_event(root, "experiment.recorded", {"experiment_id": record["id"], "status": record["status"]})
    if record["status"] == "FAILED":
        fail_record(root, "experiment", record.get("error", "recorded experiment failure"), record.get("command", []), diagnosis=record.get("diagnosis", ""))
    return record


def next_workflow_step(root: Path) -> dict[str, str]:
    """Return the single truthful user action without exposing internal schemas."""
    literature = root / '.howhow/literature'
    protocol_count = len(list((literature / 'protocols').glob('*.json'))) if literature.exists() else 0
    candidate_count = len(list((literature / 'candidates').glob('*.json'))) if literature.exists() else 0
    matrix_count = len(list((literature / 'matrix').glob('*.json'))) if literature.exists() else 0
    if protocol_count == 0:
        return {'workflow_step': 'SOURCE_AND_PROTOCOL', 'instruction': 'Review permitted sources, then create a literature protocol with bounded queries, receipts, contradiction search, and a stopping test.'}
    if candidate_count == 0:
        return {'workflow_step': 'CANDIDATE_REVIEW', 'instruction': 'Import bounded adapter candidates linked to this protocol, then record inclusion, access, and license decisions.'}
    if matrix_count == 0:
        return {'workflow_step': 'EVIDENCE_AND_MATRIX', 'instruction': 'Retain and verify exact evidence, build the source/evidence matrix, and run the literature audit.'}
    targets = list((root / '.howhow/targets').glob('*.json'))
    confirmed_target = any(read_json(p).get('status') == 'CONFIRMED' for p in targets)
    contexts = list((root / '.howhow/paper/contexts').glob('*.json'))
    sections = list((root / '.howhow/paper/sections').glob('*.json'))
    if confirmed_target and not contexts:
        return {'workflow_step': 'MANUSCRIPT_CONTEXT', 'instruction': 'Freeze the read-only paper context from confirmed records before drafting.'}
    if contexts and not sections:
        return {'workflow_step': 'MANUSCRIPT_SECTIONS', 'instruction': 'Import substantive sections with paragraph-level claim anchors; drafting cannot create claims or evidence.'}
    if confirmed_target and not list((root / '.howhow/proposals').glob('*.json')):
        return {'workflow_step': 'EXPERIMENT_PLAN', 'instruction': 'Propose a bounded experiment plan, explain TRUSTED_LOCAL risk, and request one consequential human approval.'}
    return {'workflow_step': 'MANUSCRIPT_CONTEXT_AND_SECTIONS', 'instruction': 'Freeze immutable paper context, import anchored substantive sections, then run the detailed completeness audit; compilation and page count are not gates.'}


def continue_project(root: Path, response_file: Path | None = None) -> dict[str, Any]:
    state = read_json(state_path(root), {})
    if state.get("paused"):
        return {"state": "PAUSED", "message": "resume is required before continuation"}
    plan = read_json(root / ".howhow/plan.json", {"tasks": []})
    tasks = plan.get("tasks", [])
    completed = set(state.get("completed_tasks", []))
    pending = next((task for task in tasks if task["id"] not in completed), None)
    if pending is None:
        if (root / '.howhow/plan.json').exists() and tasks:
            return finalize_project(root)
        step = next_workflow_step(root)
        return {'state': 'READY', **step}
    if pending.get("kind") == "human" and response_file is None:
        request = {"request_id": "request-" + uuid.uuid4().hex[:16], "task_id": pending["id"], "question": pending.get("instruction", "Human input required"), "created_at": now()}
        request_path = root / ".howhow/runs" / pending["id"] / "request.json"
        atomic_json(request_path, request)
        state.update({"state": "NEEDS_HUMAN", "current_task": pending["id"], "pending_request": str(request_path.relative_to(root))})
        atomic_json(state_path(root), state)
        append_event(root, "human.requested", {"task_id": pending["id"], "request": str(request_path.relative_to(root))})
        return {"state": "NEEDS_HUMAN", "task": pending["id"], "request": request}
    result = {"state": "RUNNING", "task": pending["id"], "instruction": pending.get("instruction", ""), "message": "task output must be registered by the main agent"}
    if response_file is not None:
        response = response_file.read_text(encoding="utf-8")
        (root / ".howhow/runs" / pending["id"]).mkdir(parents=True, exist_ok=True)
        (root / ".howhow/runs" / pending["id"] / "response.txt").write_text(response, encoding="utf-8")
        completed.add(pending["id"])
        state["completed_tasks"] = sorted(completed)
        state["state"] = "READY"
        state["pending_request"] = None
        atomic_json(state_path(root), state)
        append_event(root, "task.completed", {"task_id": pending["id"], "response_sha256": sha256_bytes(response.encode())})
        result["state"] = "READY"
        result["completed"] = pending["id"]
    else:
        state.update({"state": "RUNNING", "current_task": pending["id"]})
        atomic_json(state_path(root), state)
        append_event(root, "task.presented", {"task_id": pending["id"]})
    return result


def finalize_project(root: Path) -> dict[str, Any]:
    state = read_json(state_path(root), {})
    if state.get("paused"):
        return {"state": "PAUSED", "message": "resume is required before finalization"}
    if state.get("state") in TERMINAL:
        return {"state": state.get("state"), "message": "project is terminal"}
    try:
        rendered = render_record_paper(root)
        verification = verify_project(root, strict=True, profile="project")
        package = package_paper(root, strict=True)
    except (SystemExit, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        state.update({"state": "BLOCKED", "current_task": None, "finalization_error": str(exc)})
        atomic_json(state_path(root), state)
        append_event(root, "project.finalization_blocked", {"error": str(exc)})
        return {"state": "BLOCKED", "message": str(exc)}
    state.update({"state": "READY_FOR_HUMAN_REVIEW", "current_task": None, "verdict": verification["verdict"], "package_validated": package["validation"]["passed"]})
    atomic_json(state_path(root), state)
    append_event(root, "project.ready_for_human_review", {"verification": verification["verdict"], "package_validated": package["validation"]["passed"]})
    return {"state": "READY_FOR_HUMAN_REVIEW", "message": "records rendered, verified, and packaged; human review remains required", "verification": verification, "package": {"files": len(package["files"]), "validated": package["validation"]["passed"]}}


def set_paused(root: Path, paused: bool, reason: str = "") -> dict[str, Any]:
    state = read_json(state_path(root), {})
    state["paused"] = paused
    if not paused and state.get("state") in TERMINAL | {"READY_FOR_HUMAN_REVIEW"}:
        raise SystemExit("terminal projects cannot be resumed")
    state["state"] = "PAUSED" if paused else state.get("state", "READY")
    if paused:
        state["pause_reason"] = reason
    else:
        state["pause_reason"] = None
    atomic_json(state_path(root), state)
    append_event(root, "state.paused" if paused else "state.resumed", {"reason": reason})
    return state


def status(root: Path) -> dict[str, Any]:
    state = read_json(state_path(root), {})
    from .vnext import capability_list
    proposals = [read_json(p) for p in (root / ".howhow/proposals").glob("*.json")]
    grants = [read_json(p) for p in (root / ".howhow/grants").glob("*.json")]
    workflow = "EXPERIMENT_APPROVAL" if proposals and not grants else ("EXPERIMENT_EXECUTION" if grants else "RESEARCH_CONTINUATION")
    step = next_workflow_step(root)
    contexts = list((root / ".howhow/paper/contexts").glob("*.json"))
    sections = list((root / ".howhow/paper/sections").glob("*.json"))
    missing = ["paper_context"] if not contexts else (["substantive_sections"] if not sections else ["completeness_audit"])
    manuscript_action = "freeze paper context" if not contexts else ("import substantive sections with claim anchors" if not sections else "run detailed paper completeness audit")
    return {"project": root.name, "root": str(root), "state": state, "workflow_step": workflow, "next_action": step["instruction"], "next_manuscript_action": manuscript_action, "missing_manuscript_gates": missing, "approval_state": "ISSUED" if grants else ("PROPOSED" if proposals else "NOT_REQUESTED"), "trust_profile": (proposals[-1].get("trust_profile") if proposals else None), "risk_warning": "NOT SANDBOXED: host filesystem and network access remain possible" if any(p.get("trust_profile") == "TRUSTED_LOCAL" for p in proposals) else None, "proposal_count": len(proposals), "sources": len(source_list(root)), "evidence": len(list((root / ".howhow/evidence").glob("*.json"))), "experiments": len(list((root / ".howhow/experiments").glob("*.json"))), "failures": len(list((root / ".howhow/failures.jsonl").read_text(encoding="utf-8").splitlines())) if (root / ".howhow/failures.jsonl").exists() else 0, "opinion": capability_list(root)["opinion"]}


def _tool(name: str) -> str | None:
    return shutil.which(name)


def _latex_escape(value: Any) -> str:
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(char, char) for char in str(value))


def render_record_paper(root: Path) -> dict[str, Any]:
    tex = root / "paper/main.tex"
    if not tex.exists():
        raise SystemExit("paper/main.tex is required")
    evidence = [read_json(path) for path in sorted((root / ".howhow/evidence").glob("*.json"))]
    experiments = [read_json(path) for path in sorted((root / ".howhow/experiments").glob("*.json"))]
    plan = read_json(root / ".howhow/plan.json", {"tasks": []})
    lines = ["% Generated by HowHow Basic from immutable records; do not edit.", r"\section*{HowHow Record Ledger}", r"This ledger is rendered from retained records. It reports provenance and observations; it does not create scientific conclusions.", r"\subsection*{Evidence links}", r"\begin{description}"]
    for record in evidence:
        if not isinstance(record, dict):
            continue
        locator = json.dumps(record.get("locator", {}), sort_keys=True, separators=(",", ":"))
        claim = record.get("claim") or record.get("claim_text") or "Unlabelled evidence record"
        lines.append(r"\item[\texttt{" + _latex_escape(record.get("id", "")) + r"}] " + _latex_escape(claim) + ". Status: " + _latex_escape(record.get("status", "")) + r"; source: \texttt{" + _latex_escape(record.get("source_id", "")) + "}; locator: " + _latex_escape(locator) + ".")
        if record.get("quote"):
            lines.append(r"\begin{quote}\small " + _latex_escape(record["quote"]) + r"\end{quote}")
    lines.extend([r"\end{description}", r"\subsection*{Experiment records}", r"\begin{description}"])
    for record in experiments:
        if not isinstance(record, dict):
            continue
        metrics = json.dumps(record.get("metrics", {}), sort_keys=True, separators=(",", ":"))
        lines.append(r"\item[\texttt{" + _latex_escape(record.get("id", "")) + r"}] Status: " + _latex_escape(record.get("status", "")) + "; hypothesis: " + _latex_escape(record.get("hypothesis", "")) + r"; metrics: \texttt{" + _latex_escape(metrics) + "}.")
    if not experiments:
        lines.append(r"\item[None] No experiment records retained.")
    lines.extend([r"\end{description}", r"\subsection*{Plan completion}"])
    tasks = plan.get("tasks", []) if isinstance(plan, dict) else []
    lines.append("Recorded task identifiers: " + ", ".join(r"\texttt{" + _latex_escape(task.get("id", "")) + "}" for task in tasks if isinstance(task, dict)) + ".")
    generated_path = root / "paper/howhow_records.tex"
    generated = "\n".join(lines) + "\n"
    temp = generated_path.with_name(generated_path.name + ".tmp-" + uuid.uuid4().hex)
    temp.write_text(generated, encoding="utf-8", newline="\n")
    os.replace(temp, generated_path)
    marker_start, marker_end = "% HOWHOW GENERATED RECORDS BEGIN", "% HOWHOW GENERATED RECORDS END"
    block = marker_start + "\n\\input{howhow_records.tex}\n" + marker_end
    manuscript = tex.read_text(encoding="utf-8")
    start, end = manuscript.find(marker_start), manuscript.find(marker_end)
    if start >= 0 and end >= start:
        manuscript = manuscript[:start] + block + manuscript[end + len(marker_end):]
    elif r"\input{howhow_records.tex}" not in manuscript:
        insertion = manuscript.find(r"\bibliographystyle{")
        if insertion < 0:
            insertion = manuscript.rfind(r"\end{document}")
        if insertion < 0:
            raise SystemExit("paper/main.tex has no insertion point")
        manuscript = manuscript[:insertion] + block + "\n" + manuscript[insertion:]
    tex.write_text(manuscript, encoding="utf-8", newline="\n")
    result = {"generated": str(generated_path.relative_to(root)), "evidence": len(evidence), "experiments": len(experiments), "sha256": sha256_file(generated_path)}
    append_event(root, "paper.rendered", result)
    return result


def build_paper(root: Path, strict: bool = False) -> dict[str, Any]:
    paper = root / "paper"
    tex = paper / "main.tex"
    bib = paper / "references.bib"
    if not tex.exists() or not bib.exists():
        raise SystemExit("paper/main.tex and paper/references.bib are required")
    build_id = "build-" + uuid.uuid4().hex[:16]
    build = root / ".howhow/builds" / build_id
    work = build / "paper"
    shutil.copytree(paper, work)
    log_lines: list[str] = []
    pdflatex = _tool("pdflatex")
    bibtex = _tool("bibtex")
    if not pdflatex:
        result = {"build_id": build_id, "passed": False, "error": "pdflatex not installed", "engine": None}
        atomic_json(build / "manifest.json", result)
        fail_record(root, "latex_build", result["error"])
        if strict:
            raise SystemExit(result["error"])
        return result
    commands = [[pdflatex, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]]
    if "\\bibliography{" in tex.read_text(encoding="utf-8") and re.search(r"\\cite\w*", tex.read_text(encoding="utf-8")) and bibtex:
        commands += [[bibtex, "main"], [pdflatex, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], [pdflatex, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]]
    elif "\\bibliography{" in tex.read_text(encoding="utf-8") and re.search(r"\\cite\w*", tex.read_text(encoding="utf-8")):
        result = {"build_id": build_id, "passed": False, "error": "bibtex not installed", "engine": pdflatex}
        atomic_json(build / "manifest.json", result)
        fail_record(root, "latex_build", result["error"])
        if strict:
            raise SystemExit(result["error"])
        return result
    ok = True
    for command in commands:
        proc = subprocess.run(command, cwd=work, text=True, capture_output=True, timeout=120)
        log_lines.append("$ " + " ".join(command) + "\n" + proc.stdout + proc.stderr)
        if proc.returncode != 0:
            ok = False
            break
    (build / "build.log").write_text("\n\n".join(log_lines), encoding="utf-8", errors="replace")
    pdf = work / "main.pdf"
    result = {"schema_version": SCHEMA_VERSION, "build_id": build_id, "passed": ok and pdf.exists(), "engine": pdflatex, "pdf": str(pdf.relative_to(build)) if pdf.exists() else None, "pdf_sha256": sha256_file(pdf) if pdf.exists() else None, "commands": commands}
    atomic_json(build / "manifest.json", result)
    if not result["passed"]:
        fail_record(root, "latex_build", "LaTeX compilation failed", [str(x) for command in commands for x in command])
        if strict:
            raise SystemExit("LaTeX compilation failed; inspect .howhow/builds/*/build.log")
    else:
        shutil.copy2(pdf, root / "dist/paper.pdf")
        append_event(root, "paper.built", {"build_id": build_id, "pdf_sha256": result["pdf_sha256"]})
    return result


def _rebuild_extracted_package(extracted: Path) -> dict[str, Any]:
    """Compile an extracted source package without trusting the working tree."""
    tex = extracted / "main.tex"
    if not tex.is_file():
        return {"passed": False, "commands": [], "error": "main.tex is missing from extracted package"}
    pdflatex = _tool("pdflatex")
    if not pdflatex:
        return {"passed": False, "commands": [], "error": "pdflatex not installed for clean-room rebuild"}
    tex_text = tex.read_text(encoding="utf-8")
    commands = [[pdflatex, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]]
    if "\\bibliography{" in tex_text and re.search(r"\\cite\w*", tex_text):
        bibtex = _tool("bibtex")
        if not bibtex:
            return {"passed": False, "commands": commands, "error": "bibtex not installed for clean-room rebuild"}
        commands += [[bibtex, "main"], commands[0], commands[0]]
    for command in commands:
        try:
            proc = subprocess.run(command, cwd=extracted, text=True, capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"passed": False, "commands": commands, "error": f"clean-room rebuild failed: {exc}"}
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "compiler exited nonzero").strip().splitlines()
            return {"passed": False, "commands": commands, "error": "clean-room rebuild failed: " + (detail[-1] if detail else "compiler exited nonzero")}
    pdf = extracted / "main.pdf"
    if not pdf.is_file():
        return {"passed": False, "commands": commands, "error": "clean-room rebuild did not produce main.pdf"}
    return {"passed": True, "commands": commands, "pdf_sha256": sha256_file(pdf), "error": None}


def validate_package(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    archive = root / "dist/arxiv-source.tar.gz"
    issues: list[str] = []
    expected = {item["path"]: item for item in manifest.get("files", [])}
    seen: set[str] = set()
    rebuild: dict[str, Any] = {"passed": False, "commands": [], "error": "archive integrity validation failed"}
    try:
        with tempfile.TemporaryDirectory(prefix="howhow-package-") as temporary:
            extracted_root = Path(temporary)
            with tarfile.open(archive, "r:gz") as tar:
                for member in tar.getmembers():
                    path = PurePosixPath(member.name)
                    if not member.isreg() or path.is_absolute() or ".." in path.parts or "\\" in member.name or (path.parts and ":" in path.parts[0]):
                        issues.append(f"unsafe archive member: {member.name}")
                        continue
                    if member.name in seen or member.name not in expected:
                        issues.append(f"unexpected archive member: {member.name}")
                        continue
                    seen.add(member.name)
                    source = tar.extractfile(member)
                    data = source.read() if source else b""
                    item = expected[member.name]
                    if len(data) != item["bytes"] or sha256_bytes(data) != item["sha256"]:
                        issues.append(f"archive hash mismatch: {member.name}")
                        continue
                    destination = extracted_root.joinpath(*path.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
            issues.extend(f"missing archive member: {path}" for path in sorted(set(expected) - seen))
            if not issues:
                rebuild = _rebuild_extracted_package(extracted_root)
                if not rebuild["passed"]:
                    issues.append(rebuild["error"])
    except (OSError, tarfile.TarError) as exc:
        issues.append(f"archive unreadable: {exc}")
    return {"passed": not issues, "issues": issues, "file_count": len(seen), "clean_room_rebuild": rebuild}


def package_paper(root: Path, strict: bool = False) -> dict[str, Any]:
    # D2 policy restrictions are a bundling gate, not a publication verdict.
    from .d2 import policy_audit
    policy_result = policy_audit(root)
    if strict and not policy_result["passed"]:
        raise SystemExit("source package blocked by policy/license inventory: " + ", ".join(policy_result.get("blockers", [])))
    paper = root / "paper"
    files = [(p, p.relative_to(paper).as_posix()) for p in paper.rglob("*") if p.is_file() and not p.is_symlink() and p.suffix not in {".aux", ".log", ".bbl", ".blg", ".fls", ".fdb_latexmk", ".synctex.gz"}]
    supplement = [root / "run_benchmark.py", root / "generate_assets.py", root / "data/corpus.txt"]
    supplement += sorted((root / ".howhow/experiments").glob("*.json"))
    supplement += sorted((root / ".howhow/sources/records").glob("*.json"))
    supplement += sorted((root / ".howhow/artifacts").glob("*.json"))
    supplement += sorted((root / ".howhow/citations").glob("*.json"))
    supplement += sorted((root / ".howhow/issues").glob("*.json"))
    supplement += sorted((root / ".howhow/policies").glob("*.json"))
    files += [(p, p.relative_to(root).as_posix()) for p in supplement if p.is_file() and not p.is_symlink()]
    if not (paper / "main.tex").exists() or not (paper / "references.bib").exists():
        raise SystemExit("package requires main.tex and references.bib")
    archive = root / "dist/arxiv-source.tar.gz"
    manifest = {"schema_version": SCHEMA_VERSION, "created_at": now(), "files": []}
    with tarfile.open(archive, "w:gz") as tar:
        for file, relative in sorted(files, key=lambda item: item[1]):
            if relative.startswith("../") or Path(relative).is_absolute():
                raise SystemExit("unsafe package path")
            tar.add(file, arcname=relative, recursive=False)
            manifest["files"].append({"path": relative, "sha256": sha256_file(file), "bytes": file.stat().st_size})
    manifest["archive_sha256"] = sha256_file(archive)
    validation = validate_package(root, manifest)
    manifest["validation"] = validation
    atomic_json(root / "dist/source-manifest.json", manifest)
    if not validation["passed"]:
        fail_record(root, "package_verify", "; ".join(validation["issues"]), diagnosis="rebuild the source archive")
        if strict:
            raise SystemExit("source package validation failed")
    append_event(root, "paper.packaged", {"archive": "dist/arxiv-source.tar.gz", "file_count": len(files), "validated": validation["passed"]})
    return manifest


def verify_project(root: Path, strict: bool = False, profile: str = "project") -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})
    check("config", (root / ".howhow/config.json").exists(), "project configuration")
    check("event_chain", verify_event_chain(root), "append-only event hashes")
    source_items = source_list(root)
    source_ok = all((root / ".howhow/sources/raw" / item["source_id"] / "payload").exists() and sha256_file(root / ".howhow/sources/raw" / item["source_id"] / "payload") == item["sha256"] and item.get("license") for item in source_items)
    check("sources", bool(source_items) and source_ok, f"{len(source_items)} source records")
    evidence = audit_evidence(root, strict=strict)
    check("evidence", evidence["passed"] and (not strict or evidence["checked"] > 0), f"{evidence['checked']} spans, {len(evidence['issues'])} issues")
    from .reviews import audit as audit_reviews
    review_result = audit_reviews(root, strict=strict)
    check("reviews", review_result["passed"], f"{review_result['records']} immutable review records, {len(review_result['issues'])} issues")
    experiments = sorted((root / ".howhow/experiments").glob("*.json"))
    experiment_issues: list[str] = []
    for path in experiments:
        try:
            record = read_json(path)
        except (OSError, ValueError) as exc:
            experiment_issues.append(f"{path.name}: unreadable record ({type(exc).__name__})")
            continue
        experiment_issues.extend(f"{path.name}: {issue}" for issue in experiment_record_issues(record, path.stem))
    experiment_detail = f"{len(experiments)} immutable experiment records, {len(experiment_issues)} issues"
    if experiment_issues:
        experiment_detail += ": " + "; ".join(experiment_issues)
    check("experiments", bool(experiments) and not experiment_issues, experiment_detail)
    from .vnext import vnext_audit
    vnext_result = vnext_audit(root)
    check("vnext_records", vnext_result["passed"], f"{len(vnext_result['issues'])} Phase A schema/integrity issues")
    paper_result = build_paper(root, strict=False)
    check("latex", paper_result["passed"], paper_result.get("error", paper_result.get("pdf", "")))
    package = package_paper(root, strict=False) if paper_result["passed"] else {"files": []}
    check("package", bool(package.get("files")) and package.get("validation", {}).get("passed", False) and (root / "dist/arxiv-source.tar.gz").exists(), f"{len(package.get('files', []))} package files")
    if profile == "vnext-detailed":
        from .d2 import d2_audit
        from .paper import audit as audit_paper
        d2_result = d2_audit(root, required=True)
        content_result = audit_paper(root)
        check("d1_substantive_content", content_result["passed"], "anchored substantive paper content")
        check("d2_detailed", d2_result["passed"], "required immutable artifacts, citations, issues and policy inventory")
    passed = all(item["passed"] for item in checks)
    verdict = "READY_FOR_HUMAN_REVIEW" if passed else "BLOCKED"
    report = {"schema_version": SCHEMA_VERSION, "profile": profile, "verdict": verdict, "checks": checks, "generated_at": now(), "human_review_required": True, "automatic_publication": False}
    verify_id = "verify-" + uuid.uuid4().hex[:16]
    atomic_json(root / ".howhow/verify" / f"{verify_id}.json", report)
    append_event(root, "verification.completed", {"verify_id": verify_id, "verdict": verdict})
    state = read_json(state_path(root), {})
    if state.get("state") != "COMPLETE":
        state["state"] = verdict
    state["verdict"] = verdict
    atomic_json(state_path(root), state)
    if strict and not passed:
        raise SystemExit("verification blocked: " + "; ".join(item["name"] for item in checks if not item["passed"]))
    return report


def verify_event_chain(root: Path) -> bool:
    path = event_path(root)
    if not path.exists():
        return False
    previous = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("previous_record_sha256", "") != previous:
            return False
        digest = record.get("record_sha256")
        copy = dict(record)
        copy.pop("record_sha256", None)
        if digest != sha256_bytes(canonical(copy)):
            return False
        previous = digest
    return bool(previous)
