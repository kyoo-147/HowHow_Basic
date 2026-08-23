from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import (
    add_evidence, audit_evidence, build_paper, continue_project, init_project,
    package_paper, project_root, record_experiment, run_experiment, save_plan, set_paused,
    source_add, source_inspect, source_list, source_pin, source_search, source_use, status, verify_project, render_record_paper, finalize_project,
)
from .reviews import add as add_review, audit as audit_reviews, status as review_status
from .vnext import (brief_confirm, brief_propose, brief_show, capability_inspect, capability_list,
    claim_add, claim_audit, idea_add, idea_rank, idea_select, target_confirm, target_propose)


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
    start = sub.add_parser("start", help="show the bounded conversational Phase A path")
    start.add_argument("--mode", choices=["Manual", "Hybrid", "Auto"], default="Hybrid")
    cont = sub.add_parser("continue")
    cont.add_argument("--response-file")
    cont.add_argument("--mode", choices=["Manual", "Hybrid", "Auto"], default="Hybrid")
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
    run = expsub.add_parser("run", help="run a bounded command from a JSON specification and retain its immutable result")
    run.add_argument("file")
    review = sub.add_parser("review")
    reviewsub = review.add_subparsers(dest="review_command", required=True)
    ra = reviewsub.add_parser("add")
    ra.add_argument("file")
    reviewaudit = reviewsub.add_parser("audit")
    reviewaudit.add_argument("--strict", action="store_true")
    reviewsub.add_parser("status")
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
    cap = sub.add_parser("capability")
    capsub = cap.add_subparsers(dest="capability_command", required=True)
    capsub.add_parser("list")
    ci = capsub.add_parser("inspect"); ci.add_argument("id")
    brief = sub.add_parser("brief")
    bsub = brief.add_subparsers(dest="brief_command", required=True)
    bp = bsub.add_parser("propose"); bp.add_argument("title"); bp.add_argument("--mode", choices=["Manual","Hybrid","Auto"], default="Hybrid")
    bsub.add_parser("show"); bc=bsub.add_parser("confirm"); bc.add_argument("id")
    idea = sub.add_parser("idea"); isub=idea.add_subparsers(dest="idea_command", required=True)
    ia=isub.add_parser("add"); ia.add_argument("file")
    isub.add_parser("rank"); ise=isub.add_parser("select"); ise.add_argument("id")
    target = sub.add_parser("target"); tsub=target.add_subparsers(dest="target_command", required=True)
    tp=tsub.add_parser("propose"); tp.add_argument("idea_id"); tp.add_argument("--words",type=int,default=0); tp.add_argument("--pages",type=int,default=0); tp.add_argument("--figures",type=int,default=0); tp.add_argument("--tables",type=int,default=0); tp.add_argument("--rationale",default="")
    tc=tsub.add_parser("confirm"); tc.add_argument("id"); tc.add_argument("decision")
    claims=sub.add_parser("claim"); csub=claims.add_subparsers(dest="claim_command",required=True); ca=csub.add_parser("add"); ca.add_argument("file"); csub.add_parser("audit")
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
        elif args.command == "start":
            emit({"mode": args.mode, "capabilities": capability_list(root), "sources": json.loads((root / ".howhow/integration-manifest.json").read_text(encoding="utf-8")), "steps": ["inspect capabilities", "propose/confirm brief", "rank 3-5 gated ideas", "select idea and confirm target", "build claim map, then human review"]})
        elif args.command == "continue":
            continuation = continue_project(root, Path(args.response_file) if args.response_file else None)
            continuation.update({"mode": args.mode, "capabilities": capability_list(root)})
            emit(continuation)
        elif args.command == "capability":
            emit(capability_list(root) if args.capability_command == "list" else capability_inspect(root,args.id))
        elif args.command == "brief":
            emit(brief_propose(root,args.title,args.mode) if args.brief_command == "propose" else brief_show(root) if args.brief_command == "show" else brief_confirm(root,args.id))
        elif args.command == "idea":
            emit(idea_add(root,json.loads(Path(args.file).read_text(encoding="utf-8"))) if args.idea_command == "add" else idea_rank(root) if args.idea_command == "rank" else idea_select(root,args.id))
        elif args.command == "target":
            emit(target_propose(root,args.idea_id,args.words,args.pages,args.figures,args.tables,args.rationale) if args.target_command == "propose" else target_confirm(root,args.id,args.decision))
        elif args.command == "claim":
            emit(claim_add(root,json.loads(Path(args.file).read_text(encoding="utf-8"))) if args.claim_command == "add" else claim_audit(root))
        elif args.command == "status":
            emit(status(root))
        elif args.command == "pause": emit(set_paused(root, True, args.reason))
        elif args.command == "resume": emit(set_paused(root, False))
        elif args.command == "evidence":
            result = add_evidence(root, Path(args.file)) if args.evidence_command == "add" else audit_evidence(root, args.strict)
            emit(result)
            if args.evidence_command == "audit" and args.strict and not result["passed"]: return 1
        elif args.command == "experiment":
            result = record_experiment(root, Path(args.file)) if args.experiment_command == "record" else run_experiment(root, Path(args.file))
            emit(result)
            if args.experiment_command == "run" and result["status"] == "FAILED": return 1
        elif args.command == "review":
            if args.review_command == "add": emit(add_review(root, Path(args.file)))
            elif args.review_command == "audit":
                result = audit_reviews(root, args.strict)
                emit(result)
                if args.strict and not result["passed"]: return 1
            else: emit(review_status(root))
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
