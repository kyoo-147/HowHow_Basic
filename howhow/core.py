from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
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
    if parsed.scheme in {"http", "https"}:
        request = urllib.request.Request(location, headers={"User-Agent": "HowHow-Basic/0.1 (+local research tool)"})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            final_url = response.geturl()
            media_type = response.headers.get_content_type()
    else:
        path = Path(location).resolve()
        if not path.is_file():
            raise SystemExit(f"source file not found: {location}")
        payload, final_url, media_type = path.read_bytes(), path.as_uri(), "application/octet-stream"
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
    records = [read_json(p) for p in sorted((root / ".howhow/evidence").glob("*.json"))]
    issues: list[str] = []
    checked = 0
    for record in records:
        sid = record.get("source_id")
        source = sources.get(sid)
        if sid and source:
            payload = root / ".howhow/sources/raw" / sid / "payload"
            if not payload.exists() or sha256_file(payload) != source.get("sha256"):
                issues.append(f"{record.get('id')}: source hash mismatch")
            locator = record.get("locator", {})
            if "char_start" in locator and "char_end" in locator:
                text = payload.read_bytes().decode("utf-8", errors="replace")
                quote = text[int(locator["char_start"]):int(locator["char_end"])]
                if quote != record.get("quote", ""):
                    issues.append(f"{record.get('id')}: quote does not match source span")
                checked += 1
        elif sid:
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


def record_experiment(root: Path, descriptor: Path) -> dict[str, Any]:
    record = read_json(descriptor)
    required = ["id", "hypothesis", "command", "status", "raw_observations", "metrics", "code_revision", "seed"]
    missing = [key for key in required if key not in record]
    if missing:
        raise SystemExit("experiment record missing: " + ", ".join(missing))
    if record["status"] not in {"SUCCESS", "FAILED", "INCONCLUSIVE"}:
        raise SystemExit("experiment status must be SUCCESS, FAILED, or INCONCLUSIVE")
    record["schema_version"] = SCHEMA_VERSION
    record["recorded_at"] = record.get("recorded_at", now())
    record["record_sha256"] = sha256_bytes(canonical(record))
    target = root / ".howhow/experiments" / f"{record['id']}.json"
    if target.exists():
        raise SystemExit("experiment records are immutable; use a new id")
    atomic_json(target, record)
    append_event(root, "experiment.recorded", {"experiment_id": record["id"], "status": record["status"]})
    if record["status"] == "FAILED":
        fail_record(root, "experiment", record.get("error", "recorded experiment failure"), record.get("command", []), diagnosis=record.get("diagnosis", ""))
    return record


def continue_project(root: Path, response_file: Path | None = None) -> dict[str, Any]:
    state = read_json(state_path(root), {})
    if state.get("paused"):
        return {"state": "PAUSED", "message": "resume is required before continuation"}
    plan = read_json(root / ".howhow/plan.json", {"tasks": []})
    tasks = plan.get("tasks", [])
    completed = set(state.get("completed_tasks", []))
    pending = next((task for task in tasks if task["id"] not in completed), None)
    if pending is None:
        return finalize_project(root)
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
    if state.get("state") == "COMPLETE":
        return {"state": "COMPLETE", "message": "project was already finalized"}
    try:
        rendered = render_record_paper(root)
        verification = verify_project(root, strict=True, profile="project")
        package = package_paper(root, strict=True)
    except (SystemExit, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        state.update({"state": "BLOCKED", "current_task": None, "finalization_error": str(exc)})
        atomic_json(state_path(root), state)
        append_event(root, "project.finalization_blocked", {"error": str(exc)})
        return {"state": "BLOCKED", "message": str(exc)}
    state.update({"state": "COMPLETE", "current_task": None, "verdict": verification["verdict"], "package_validated": package["validation"]["passed"]})
    atomic_json(state_path(root), state)
    append_event(root, "project.completed", {"verification": verification["verdict"], "package_validated": package["validation"]["passed"]})
    return {"state": "COMPLETE", "message": "records rendered, verified, built, and packaged", "verification": verification, "package": {"files": len(package["files"]), "validated": package["validation"]["passed"]}}


def set_paused(root: Path, paused: bool, reason: str = "") -> dict[str, Any]:
    state = read_json(state_path(root), {})
    state["paused"] = paused
    state["state"] = "PAUSED" if paused else "READY"
    if paused:
        state["pause_reason"] = reason
    else:
        state["pause_reason"] = None
    atomic_json(state_path(root), state)
    append_event(root, "state.paused" if paused else "state.resumed", {"reason": reason})
    return state


def status(root: Path) -> dict[str, Any]:
    state = read_json(state_path(root), {})
    return {"project": root.name, "root": str(root), "state": state, "sources": len(source_list(root)), "evidence": len(list((root / ".howhow/evidence").glob("*.json"))), "experiments": len(list((root / ".howhow/experiments").glob("*.json"))), "failures": len(list((root / ".howhow/failures.jsonl").read_text(encoding="utf-8").splitlines())) if (root / ".howhow/failures.jsonl").exists() else 0}


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
    commands = [[pdflatex, "-interaction=nonstopmode", "-halt-on-error", "main.tex"]]
    if "\\bibliography{" in tex.read_text(encoding="utf-8") and bibtex:
        commands += [[bibtex, "main"], [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "main.tex"], [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "main.tex"]]
    elif "\\bibliography{" in tex.read_text(encoding="utf-8"):
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


def validate_package(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    archive = root / "dist/arxiv-source.tar.gz"
    issues: list[str] = []
    expected = {item["path"]: item for item in manifest.get("files", [])}
    seen: set[str] = set()
    try:
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                path = PurePosixPath(member.name)
                if not member.isreg() or path.is_absolute() or ".." in path.parts:
                    issues.append(f"unsafe archive member: {member.name}")
                    continue
                if member.name in seen or member.name not in expected:
                    issues.append(f"unexpected archive member: {member.name}")
                    continue
                seen.add(member.name)
                extracted = tar.extractfile(member)
                data = extracted.read() if extracted else b""
                item = expected[member.name]
                if len(data) != item["bytes"] or sha256_bytes(data) != item["sha256"]:
                    issues.append(f"archive hash mismatch: {member.name}")
    except (OSError, tarfile.TarError) as exc:
        issues.append(f"archive unreadable: {exc}")
    issues.extend(f"missing archive member: {path}" for path in sorted(set(expected) - seen))
    return {"passed": not issues, "issues": issues, "file_count": len(seen)}


def package_paper(root: Path, strict: bool = False) -> dict[str, Any]:
    paper = root / "paper"
    files = [p for p in paper.rglob("*") if p.is_file() and p.suffix not in {".aux", ".log", ".bbl", ".blg", ".fls", ".fdb_latexmk", ".synctex.gz"}]
    if not (paper / "main.tex").exists() or not (paper / "references.bib").exists():
        raise SystemExit("package requires main.tex and references.bib")
    archive = root / "dist/arxiv-source.tar.gz"
    manifest = {"schema_version": SCHEMA_VERSION, "created_at": now(), "files": []}
    with tarfile.open(archive, "w:gz") as tar:
        for file in sorted(files):
            relative = file.relative_to(paper).as_posix()
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
    experiments = list((root / ".howhow/experiments").glob("*.json"))
    exp_ok = True
    for path in experiments:
        record = read_json(path)
        valid_status = record.get("status") in {"SUCCESS", "FAILED", "INCONCLUSIVE"}
        has_payload = bool(record.get("raw_observations")) and bool(record.get("metrics"))
        exp_ok = exp_ok and valid_status and (has_payload or record.get("status") == "FAILED")
    check("experiments", bool(experiments) and exp_ok, f"{len(experiments)} immutable experiment records")
    paper_result = build_paper(root, strict=False)
    check("latex", paper_result["passed"], paper_result.get("error", paper_result.get("pdf", "")))
    package = package_paper(root, strict=False) if paper_result["passed"] else {"files": []}
    check("package", bool(package.get("files")) and package.get("validation", {}).get("passed", False) and (root / "dist/arxiv-source.tar.gz").exists(), f"{len(package.get('files', []))} package files")
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
