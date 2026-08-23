from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import (
    add_evidence, audit_evidence, build_paper, continue_project, init_project,
    package_paper, project_root, record_experiment, save_plan, set_paused,
    source_add, source_inspect, source_list, source_pin, source_search, source_use, status, verify_project, render_record_paper, finalize_project,
)


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def root_from(args: argparse.Namespace):
    return project_root(getattr(args, "directory", "."))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="howhow", description="HowHow Basic evidence-first research project CLI")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create a project-local filesystem workspace")
    init.add_argument("directory", nargs="?", default=".")
    init.add_argument("--goal", default="")
    src = sub.add_parser("source")
    srcsub = src.add_subparsers(dest="source_command", required=True)
    add = srcsub.add_parser("add")
    add.add_argument("location")
    add.add_argument("--license", default="UNVERIFIED")
    inspect = srcsub.add_parser("inspect")
    inspect.add_argument("source_id")
    pin = srcsub.add_parser("pin")
    pin.add_argument("source_id")
    pin.add_argument("revision")
    use = srcsub.add_parser("use")
    use.add_argument("source_id")
    search = srcsub.add_parser("search")
    search.add_argument("--provider", choices=["arxiv", "openalex"], required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=5)
    srcsub.add_parser("list")
    plan = sub.add_parser("plan")
    plansub = plan.add_subparsers(dest="plan_command", required=True)
    save = plansub.add_parser("save")
    save.add_argument("file")
    plansub.add_parser("show")
    cont = sub.add_parser("continue")
    cont.add_argument("--response-file")
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    pause = sub.add_parser("pause")
    pause.add_argument("reason", nargs="?", default="user requested pause")
    sub.add_parser("resume")
    ev = sub.add_parser("evidence")
    evsub = ev.add_subparsers(dest="evidence_command", required=True)
    ea = evsub.add_parser("add")
    ea.add_argument("file")
    audit = evsub.add_parser("audit")
    audit.add_argument("--strict", action="store_true")
    exp = sub.add_parser("experiment")
    expsub = exp.add_subparsers(dest="experiment_command", required=True)
    er = expsub.add_parser("record")
    er.add_argument("file")
    paper = sub.add_parser("paper")
    papersub = paper.add_subparsers(dest="paper_command", required=True)
    build = papersub.add_parser("build")
    build.add_argument("--strict", action="store_true")
    papersub.add_parser("render")
    papersub.add_parser("finalize")
    package = sub.add_parser("package")
    package.add_argument("--strict", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--profile", choices=["fixture", "project"], default="project")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            emit({"project": str(init_project(args.directory, args.goal)), "state": "NEW"})
            return 0
        root = root_from(args)
        if args.command == "source":
            if args.source_command == "add": emit(source_add(root, args.location, args.license))
            elif args.source_command == "inspect": emit(source_inspect(root, args.source_id))
            elif args.source_command == "pin": emit(source_pin(root, args.source_id, args.revision))
            elif args.source_command == "use": emit(source_use(root, args.source_id))
            elif args.source_command == "list": emit(source_list(root))
            else: emit(source_search(root, args.provider, args.query, args.limit))
        elif args.command == "plan":
            if args.plan_command == "save": emit(save_plan(root, Path(args.file)))
            else: emit(json.loads((root / ".howhow/plan.json").read_text(encoding="utf-8")))
        elif args.command == "continue":
            emit(continue_project(root, Path(args.response_file) if args.response_file else None))
        elif args.command == "status":
            emit(status(root))
        elif args.command == "pause": emit(set_paused(root, True, args.reason))
        elif args.command == "resume": emit(set_paused(root, False))
        elif args.command == "evidence":
            result = add_evidence(root, Path(args.file)) if args.evidence_command == "add" else audit_evidence(root, args.strict)
            emit(result)
            if args.evidence_command == "audit" and args.strict and not result["passed"]: return 1
        elif args.command == "experiment": emit(record_experiment(root, Path(args.file)))
        elif args.command == "paper":
            if args.paper_command == "build":
                result = build_paper(root, args.strict)
                emit(result)
                if args.strict and not result["passed"]: return 1
            elif args.paper_command == "render":
                emit(render_record_paper(root))
            else:
                result = finalize_project(root)
                emit(result)
                if result["state"] not in {"COMPLETE", "READY_FOR_HUMAN_REVIEW"}: return 1
        elif args.command == "package":
            result = package_paper(root, args.strict)
            emit(result)
            if not result.get("validation", {}).get("passed", False): return 1
        elif args.command == "verify":
            result = verify_project(root, args.strict, args.profile)
            emit(result)
            if args.strict and result["verdict"] != "READY_FOR_HUMAN_REVIEW": return 1
        return 0
    except (SystemExit, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, SystemExit) and exc.code == 0: return 0
        print(f"howhow: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
