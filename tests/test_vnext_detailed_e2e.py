import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from howhow.core import add_evidence, init_project, record_experiment, source_add, verify_project, build_paper, package_paper, render_record_paper
from howhow.vnext import brief_confirm, brief_propose, claim_add, idea_add, idea_rank, idea_select, target_confirm, target_propose
from howhow.literature import add_matrix, create_protocol, decide_candidate, import_candidate
from howhow.experiment_v2 import objective_save
from howhow.paper import add_section, create_context
from howhow.d2 import add_artifact, add_citation, add_issue, add_policy
from howhow.adapters import contracts, export_contract, import_contract


class VNextDetailedE2E(unittest.TestCase):
    """Synthetic product closure, deliberately not a scientific episode."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="howhow-vnext-detailed-"))
        self.root = init_project(self.temp / "synthetic-detailed")
        self.env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}

    def _record_run(self, ident, label, change):
        descriptor = self.temp / (ident + ".json")
        descriptor.write_text(json.dumps({
            "id": ident, "hypothesis": "Synthetic fixture hypothesis; not a scientific claim.",
            "command": ["fixture-only", label], "status": "SUCCESS",
            "raw_observations": [{"fixture_result": label, "scientific_result": "NOT_RECORDED"}],
            "metrics": {"fixture_count": 1}, "code_revision": "synthetic-fixture-revision",
            "seed": 17, "design": "approved bounded baseline-first", "declared_change": change,
            "truth_boundary": "fixture-only result; no scientific correctness or novelty claim",
        }), encoding="utf-8")
        return record_experiment(self.root, descriptor)

    def build_profile(self):
        # Phase A: OPINION remains empty, and every confirmation is append-only.
        self.assertEqual((self.root / "OPINION.md").read_bytes(), b"")
        brief_confirm(self.root, brief_propose(self.root, "Synthetic vNext detailed closure", "Hybrid")["id"])
        gates = {x: True for x in ("safety", "ethics", "license", "data", "evaluator", "resource", "evidence")}
        for ident in ("fixture-idea-a", "fixture-idea-b", "fixture-idea-c"):
            idea_add(self.root, {"id": ident, "title": "Synthetic " + ident, "question": "Which fixture path is retained?", "evidence_plan": "deterministic fixture inspection", "gates": gates})
        idea_rank(self.root)
        idea_select(self.root, "fixture-idea-a")
        target_confirm(self.root, target_propose(self.root, "fixture-idea-a", words=120, pages=2, rationale="Synthetic bounded target", argument_skeleton=["claim-external", "claim-empirical"])["id"], "ACCEPT")

        # Phase B: all literature records are explicit fixture receipts and source bytes.
        source_text = "Synthetic fixture source. This byte span is retained for product verification only."
        source_file = self.root / "synthetic-source.txt"
        source_file.write_text(source_text, encoding="utf-8")
        source = source_add(self.root, str(source_file), "CC0")
        evidence_file = self.temp / "evidence.json"
        start = source_text.index("This byte span")
        evidence_file.write_text(json.dumps({
            "id": "evidence-fixture-1", "status": "VERIFIED", "source_id": source["source_id"],
            "quote": source_text[start:start + len("This byte span is retained")],
            "locator": {"char_start": start, "char_end": start + len("This byte span is retained")},
            "run_id": "run-fixture-baseline",
            "claim": "Synthetic source span; not a scientific finding.",
        }), encoding="utf-8")
        evidence = add_evidence(self.root, evidence_file)
        protocol = create_protocol(self.root, {
            "id": "protocol-fixture-1", "questions": ["Synthetic question"], "claims": ["claim-external"],
            "filters": {"fixture": True}, "date_cutoff": "2099-01-01", "retrieval_timestamp": "SYNTHETIC_FIXTURE",
            "queries": ["synthetic query", "synthetic contradiction query"],
            "query_receipts": [
                {"receipt_id": "query-receipt-1", "provider": "gpt-researcher", "query": "synthetic query", "live": False},
                {"receipt_id": "query-receipt-2", "provider": "gpt-researcher", "query": "synthetic contradiction query", "live": False},
            ], "candidate_result_ids": ["candidate-fixture-1"],
            "saturation": {"result_count": 1, "queries_covered": 2, "stopping_test": "fixture result set exhausted"},
            "contradiction_search": {"queries": ["synthetic contradiction query"], "performed": True, "result_ids": []},
            "stop_rationale": "Synthetic fixture stopping rule; not a coverage or novelty conclusion.",
            "fixture_only": True, "novelty_claim": False,
        })
        request = {"provider": "gpt-researcher", "query": "synthetic query", "limit": 1, "live": False, "provisional": True}
        candidate = import_candidate(self.root, {
            "provider": "gpt-researcher", "query_receipt": {"receipt_id": "query-receipt-1", "provider": "gpt-researcher", "query": "synthetic query"},
            "candidate_id": "candidate-fixture-1", "url": "https://fixture.invalid/synthetic", "title": "Fixture-only source/result",
            "document_id": "fixture-document-1", "retrieved_at": "SYNTHETIC_FIXTURE", "protocol_id": protocol["id"], "adapter_request": request,
        })
        decide_candidate(self.root, candidate["id"], "INCLUDED", "Included only to exercise immutable fixture flow", source["source_id"])
        add_matrix(self.root, {"id": "matrix-fixture-1", "question": "Synthetic question", "role": "FOUNDATIONAL", "source_ids": [source["source_id"]], "evidence_ids": [evidence["id"]], "status": "RETAINED", "fixture_only": True})

        # Phase C: preserved records, not execution of a real experiment.
        baseline = self._record_run("run-fixture-baseline", "baseline", "none")
        attempt = self._record_run("run-fixture-one-change", "one-change", "change-one-declared")
        objective_save(self.root, {"id": "analysis-fixture-1", "primary_metrics": ["fixture_count"], "baseline": "run-fixture-baseline", "outcome_definitions": {"fixture_count": "count of synthetic observations"}, "ablation_plan": {"one_change": "change-one-declared"}, "stopping_rules": {"max_attempts": 1}, "repetitions": 1, "uncertainty_method": "not applicable to synthetic fixture", "known_confounders": ["none assessed"], "no_progress_policy": "stop after one declared change", "truth_boundary": "no scientific result"})
        claims = [
            {"id": "claim-external", "section": "introduction", "paragraph": "p1", "type": "EXTERNAL", "uncertainty": "fixture source span only", "status": "VERIFIED", "source_ids": [source["source_id"]], "evidence_ids": [evidence["id"]]},
            {"id": "claim-empirical", "section": "results", "paragraph": "p1", "type": "EMPIRICAL", "uncertainty": "synthetic observation only", "status": "VERIFIED", "run_ids": [baseline["id"], attempt["id"]]},
            {"id": "claim-interpretive", "section": "discussion", "paragraph": "p1", "type": "INTERPRETIVE", "uncertainty": "interpretation is not validated", "status": "UNVERIFIED"},
            {"id": "claim-hypothesis", "section": "question", "paragraph": "p1", "type": "HYPOTHESIS", "uncertainty": "hypothesis only", "status": "UNVERIFIED"},
            {"id": "claim-limit", "section": "limitations", "paragraph": "p1", "type": "LIMITATION", "uncertainty": "explicit fixture boundary", "status": "VERIFIED"},
            {"id": "claim-opinion", "section": "discussion", "paragraph": "p2", "type": "OPINION", "uncertainty": "preference only", "status": "UNVERIFIED"},
        ]
        for claim in claims:
            claim_add(self.root, claim)

        # D1: freeze context then import all substantive section contracts.
        context = create_context(self.root)
        section_types = ["TITLE_AND_CONTRIBUTIONS", "ABSTRACT", "INTRODUCTION", "RELATED_WORK", "QUESTION_HYPOTHESIS", "METHODS_SYSTEM", "ANALYSIS_EXPERIMENT_DESIGN", "RESULTS", "ROBUSTNESS_ABLATION_SENSITIVITY", "DISCUSSION_COMPETING_EXPLANATIONS", "THREATS", "LIMITATIONS", "ETHICS_RIGHTS_DUAL_USE", "REPRODUCIBILITY", "CONCLUSION", "REFERENCES", "APPENDICES"]
        text = "Synthetic fixture-only record: no scientific finding, no novelty claim, no scientific correctness claim, no human review, and no publication readiness. Uncertainty and limitation are explicit."
        for number, section_type in enumerate(section_types, 1):
            claim_ids = ["claim-external"] if section_type in {"INTRODUCTION", "RELATED_WORK", "REFERENCES"} else ["claim-empirical"] if section_type in {"RESULTS", "METHODS_SYSTEM", "REPRODUCIBILITY", "ANALYSIS_EXPERIMENT_DESIGN"} else ["claim-limit"]
            extra = {"METHODS_SYSTEM": " Inputs, seed, environment, code, and data are declared.", "ETHICS_RIGHTS_DUAL_USE": " Ethics, rights, privacy, consent, dual-use, and risk are not assessed in this fixture.", "THREATS": " Threats, competing explanations, alternative confounds, and generalizability are not assessed.", "DISCUSSION_COMPETING_EXPLANATIONS": " Alternative and competing explanations remain uncertain; confounds are not assessed."}.get(section_type, "")
            add_section(self.root, {"id": "section-fixture-" + str(number), "type": section_type, "context_id": context["id"], "status": "FINAL", "paragraphs": [{"id": "p1", "text": text + extra + " This section is a product fixture.", "claim_ids": claim_ids}]})

        # D2: artifact, identity/support-separated citation, issue/revision/dissent, policy.
        raw = self.root / "paper" / "fixture-input.txt"; raw.write_text("synthetic input", encoding="utf-8")
        script = self.root / "paper" / "fixture-transform.py"; script.write_text("# synthetic transform\n", encoding="utf-8")
        generated = self.root / "paper" / "figures" / "fixture-output.dat"; generated.write_bytes(b"synthetic artifact")
        import hashlib
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        add_artifact(self.root, {"id": "artifact-fixture-1", "kind": "FIGURE", "raw_inputs": [{"path": "paper/fixture-input.txt", "sha256": digest(raw)}], "transformation": {"script": "paper/fixture-transform.py", "script_sha256": digest(script)}, "generated": {"path": "paper/figures/fixture-output.dat", "sha256": digest(generated)}, "units": {"fixture_count": "count"}, "uncertainty": "not applicable; synthetic fixture", "caption_claim_ids": ["claim-empirical"], "accessibility_status": "PASS", "visual_qa_status": "NOT_APPLICABLE", "parents": {"source": [source["source_id"]], "run": [baseline["id"]], "evidence": [evidence["id"]]}, "regeneration_receipt": {"command": ["fixture-only-transform"], "status": "RECEIVED"}})
        add_citation(self.root, {"id": "citation-fixture-1", "citation_key": "fixture-source", "bibliographic_identity": {"title": "Fixture-only source/result", "author": "Synthetic Fixture"}, "identifiers": {"url": "https://fixture.invalid/synthetic"}, "identity_receipts": ["query-receipt-1"], "support": {"claim_ids": ["claim-external"], "evidence_ids": [evidence["id"]], "exact_links": [{"source_id": source["source_id"], "evidence_id": evidence["id"]}]}, "correction_retraction_status": "CLEAR", "access_redistribution": "CC0"})
        add_issue(self.root, {"id": "issue-fixture-dissent", "severity": "DISSENT", "finding": "Synthetic fixture interpretation is not scientific review.", "disposition": "UNRESOLVED", "anchors": {"manuscript": "DISCUSSION_COMPETING_EXPLANATIONS:p1"}, "reviewer": "fixture-reviewer", "review_kind": "MACHINE_ASSISTED", "independent_scientific_review": False, "context": {"kind": "fixture", "revision": "revision-fixture-1"}, "revision_of": "revision-fixture-1", "dissent": "Preserved dissent; no human review claimed.", "execution_contract": {"action": "preserve"}})
        add_policy(self.root, {"id": "policy-fixture", "kind": "SUBMISSION", "state": "ALLOWED", "subject": "synthetic fixture package retention", "disclosure": "Fixture-only package retention is allowed; submission is prohibited and not authorized.", "human_review_boundary": "Human scientific review remains required."})

        # E1: all 13 contracts are exercised as provisional receipts; no live call.
        for contract in contracts():
            payload = {"artifact_id": "fixture-artifact", "cross_links": [], "fixture_only": True}
            if contract["repository"] == "AI-Scientist": payload["enablement"] = {"restricted_use_acknowledged": True, "manuscript_ai_disclosure": True}
            if contract["repository"] == "DeepScientist": payload["restricted_use_acknowledged"] = True
            envelope = export_contract(contract["repository"], contract["operations"][0], payload)
            imported = import_contract(self.root, envelope)
            self.assertEqual(imported["state"], "PROVISIONAL")
        self.assertEqual(len(list((self.root / ".howhow/integrations/receipts").glob("*.json"))), 13)

        # A deterministic, explicitly synthetic manuscript.
        (self.root / "paper" / "main.tex").write_text(r"""\documentclass{article}
\usepackage[margin=1in]{geometry}
\title{Synthetic HowHow vNext Verification Fixture}
\author{HowHow Basic}
\date{2026-08-23}
\begin{document}\maketitle
\begin{abstract}This is a fixture-only product verification package, not a scientific result.\end{abstract}
\section{Synthetic verification boundary}No novelty, correctness, human review, publication readiness, or submission authorization is claimed.
% HOWHOW GENERATED RECORDS BEGIN
\input{howhow_records.tex}
% HOWHOW GENERATED RECORDS END
\end{document}
""", encoding="utf-8")
        (self.root / "paper" / "references.bib").write_text("% fixture-only bibliography\n", encoding="utf-8")
        render_record_paper(self.root)

    def test_complete_detailed_fixture_cli_strict_clean_room_and_tamper(self):
        self.build_profile()
        # The top-level public verification surface is the acceptance oracle.
        verify = subprocess.run([sys.executable, "-m", "howhow", "verify", "--profile", "vnext-detailed", "--strict"], cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual(verify.returncode, 0, verify.stderr)
        report = json.loads(verify.stdout)
        self.assertEqual(report["profile"], "vnext-detailed")
        self.assertEqual(report["verdict"], "READY_FOR_HUMAN_REVIEW")
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        package = subprocess.run([sys.executable, "-m", "howhow", "package", "--strict"], cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual(package.returncode, 0, package.stderr)
        packaged = json.loads(package.stdout)
        self.assertTrue(packaged["validation"]["passed"])
        self.assertTrue(packaged["validation"]["clean_room_rebuild"]["passed"])
        self.assertTrue((self.root / "dist/paper.pdf").read_bytes().startswith(b"%PDF"))
        package_paths = [item["path"] for item in packaged["files"]]
        self.assertIn("main.tex", package_paths)
        self.assertTrue(all(not any(token in path for token in (".aux", ".log", ".blg", ".bbl", ".tmp-")) for path in package_paths))
        status = json.loads(subprocess.check_output([sys.executable, "-m", "howhow", "status", "--json"], cwd=self.root, env=self.env, text=True))
        self.assertEqual(status["next_manuscript_action"], "run detailed paper completeness audit")
        self.assertEqual(status["opinion"], "EMPTY")

        # Late-stage tampering is fail-closed, then the immutable original is restored.
        issue_path = self.root / ".howhow/issues/issue-fixture-dissent.json"
        original = issue_path.read_bytes()
        tampered = json.loads(original); tampered["finding"] = "tampered"
        issue_path.write_text(json.dumps(tampered), encoding="utf-8")
        blocked = subprocess.run([sys.executable, "-m", "howhow", "verify", "--profile", "vnext-detailed", "--strict"], cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(blocked.returncode, 0)
        issue_path.write_bytes(original)
        restored = verify_project(self.root, strict=True, profile="vnext-detailed")
        self.assertEqual(restored["verdict"], "READY_FOR_HUMAN_REVIEW")


if __name__ == "__main__":
    unittest.main()
