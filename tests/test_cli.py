from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from howhow.core import (
    add_evidence, audit_evidence, init_project, record_experiment, save_plan,
    source_add, verify_event_chain, continue_project, render_record_paper,
)


class HowHowProductTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = init_project(str(self.tmp / "project"), "test evidence integrity")

    def test_source_hash_and_span_audit(self):
        source = self.tmp / "source.txt"
        source.write_text("HowHow preserves failures.\n", encoding="utf-8")
        manifest = source_add(self.root, str(source), "CC0")
        descriptor = self.tmp / "evidence.json"
        descriptor.write_text(json.dumps({
            "id": "ev-1", "status": "VERIFIED", "source_id": manifest["source_id"],
            "locator": {"char_start": 0, "char_end": 26},
            "quote": "HowHow preserves failures.",
        }), encoding="utf-8")
        add_evidence(self.root, descriptor)
        self.assertTrue(audit_evidence(self.root, strict=True)["passed"])
        (self.root / ".howhow/sources/raw" / manifest["source_id"] / "payload").write_text("mutated", encoding="utf-8")
        self.assertFalse(audit_evidence(self.root)["passed"])
        self.assertFalse(audit_evidence(self.root)["passed"])

    def test_identifiers_and_spans_fail_closed(self):
        from howhow.core import source_inspect
        with self.assertRaises(SystemExit):
            source_inspect(self.root, "../outside")
        source = self.tmp / "span.txt"
        source.write_text("safe", encoding="utf-8")
        manifest = source_add(self.root, str(source), "CC0")
        descriptor = self.tmp / "bad-evidence.json"
        descriptor.write_text(json.dumps({"id": "ev-bad", "status": "VERIFIED", "source_id": manifest["source_id"], "locator": {"char_start": -1, "char_end": 2}, "quote": "safe"}), encoding="utf-8")
        add_evidence(self.root, descriptor)
        self.assertFalse(audit_evidence(self.root, strict=True)["passed"])

    def test_evidence_audit_revalidates_descriptor_and_run_integrity(self):
        source = self.tmp / "bound-source.txt"
        source.write_text("Bound evidence claim.\n", encoding="utf-8")
        manifest = source_add(self.root, str(source), "CC0")
        for run_id in ("bound-run-1", "bound-run-2"):
            run_descriptor = self.tmp / f"{run_id}.json"
            run_descriptor.write_text(json.dumps({
                "id": run_id, "hypothesis": "fixture", "command": ["fixture"],
                "status": "SUCCESS", "raw_observations": [{"ok": True}],
                "metrics": {"count": 1}, "code_revision": "fixture", "seed": 1,
            }), encoding="utf-8")
            record_experiment(self.root, run_descriptor)
        descriptor = self.tmp / "bound-evidence.json"
        descriptor.write_text(json.dumps({
            "id": "ev-bound", "status": "VERIFIED", "source_id": manifest["source_id"],
            "claim": "Bound claim", "locator": {"char_start": 0, "char_end": 21},
            "quote": "Bound evidence claim.", "run_id": "bound-run-1",
        }), encoding="utf-8")
        add_evidence(self.root, descriptor)
        self.assertTrue(audit_evidence(self.root, strict=True)["passed"])

        evidence_path = self.root / ".howhow/evidence/ev-bound.json"
        original_evidence = evidence_path.read_bytes()
        evidence = json.loads(original_evidence)
        evidence["claim"] = "Tampered claim"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        self.assertTrue(any("evidence record hash mismatch" in issue for issue in audit_evidence(self.root, strict=True)["issues"]))
        evidence_path.write_bytes(original_evidence)

        evidence = json.loads(original_evidence)
        evidence["run_id"] = "bound-run-2"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        run_id_issues = audit_evidence(self.root, strict=True)["issues"]
        self.assertTrue(any("evidence record hash mismatch" in issue for issue in run_id_issues))
        self.assertFalse(any("unknown run_id" in issue for issue in run_id_issues))
        evidence_path.write_bytes(original_evidence)

        run_path = self.root / ".howhow/experiments/bound-run-1.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["metrics"] = {"count": 2}
        run_path.write_text(json.dumps(run), encoding="utf-8")
        self.assertTrue(any("experiment integrity check failed" in issue for issue in audit_evidence(self.root, strict=True)["issues"]))

    def test_verify_project_revalidates_all_experiment_records(self):
        from unittest.mock import patch
        from howhow.core import canonical, sha256_bytes, verify_project

        descriptors = {
            "failed-unlinked": {
                "status": "FAILED", "raw_observations": [], "metrics": {},
                "error": "bounded command exited 1",
            },
            "success-unlinked": {
                "status": "SUCCESS", "raw_observations": [{"ok": True}], "metrics": {"count": 1},
            },
            "inconclusive-unlinked": {
                "status": "INCONCLUSIVE", "raw_observations": [{"signal": "ambiguous"}], "metrics": {"count": 1},
            },
        }
        for run_id, payload in descriptors.items():
            descriptor = self.tmp / f"{run_id}.json"
            descriptor.write_text(json.dumps({
                "id": run_id, "hypothesis": "fixture", "command": ["fixture"],
                "code_revision": "fixture", "seed": 1, **payload,
            }), encoding="utf-8")
            record_experiment(self.root, descriptor)

        with patch("howhow.core.build_paper", return_value={"passed": True}), patch(
            "howhow.core.package_paper", return_value={"files": [{"path": "fixture"}], "validation": {"passed": True}}
        ):
            for run_id in descriptors:
                path = self.root / ".howhow/experiments" / f"{run_id}.json"
                original = path.read_bytes()
                record = json.loads(original)
                record["hypothesis"] = "tampered after recording"
                path.write_text(json.dumps(record), encoding="utf-8")
                report = verify_project(self.root)
                check = next(item for item in report["checks"] if item["name"] == "experiments")
                self.assertFalse(check["passed"], run_id)
                self.assertIn("record hash mismatch", check["detail"])
                path.write_bytes(original)

            contract_mutations = {
                "failed-unlinked": lambda record: record.pop("error"),
                "success-unlinked": lambda record: record.update(raw_observations=[]),
                "inconclusive-unlinked": lambda record: record.update(metrics={}),
            }
            for run_id, mutate in contract_mutations.items():
                path = self.root / ".howhow/experiments" / f"{run_id}.json"
                original = path.read_bytes()
                record = json.loads(original)
                mutate(record)
                record.pop("record_sha256")
                record["record_sha256"] = sha256_bytes(canonical(record))
                path.write_text(json.dumps(record), encoding="utf-8")
                report = verify_project(self.root)
                check = next(item for item in report["checks"] if item["name"] == "experiments")
                self.assertFalse(check["passed"], run_id)
                path.write_bytes(original)

            path = self.root / ".howhow/experiments/success-unlinked.json"
            path = self.root / ".howhow/experiments/success-unlinked.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["id"] = "different-id"
            record["raw_observations"] = []
            record.pop("record_sha256")
            record["record_sha256"] = sha256_bytes(canonical(record))
            path.write_text(json.dumps(record), encoding="utf-8")
            report = verify_project(self.root)
            check = next(item for item in report["checks"] if item["name"] == "experiments")
            self.assertFalse(check["passed"])
            self.assertIn("filename id success-unlinked does not match record id different-id", check["detail"])
            self.assertIn("SUCCESS requires raw observations and metrics", check["detail"])
            with self.assertRaises(SystemExit):
                verify_project(self.root, strict=True)

    def test_source_pin_and_read_only_use(self):
        from howhow.core import source_inspect, source_pin, source_use
        source = self.tmp / "pinned.txt"
        source.write_text("pinned bytes", encoding="utf-8")
        manifest = source_add(self.root, str(source), "CC0")
        self.assertTrue(source_inspect(self.root, manifest["source_id"])["payload_exists"])
        self.assertEqual(source_pin(self.root, manifest["source_id"], "commit-or-version-1")["revision"], "commit-or-version-1")
        self.assertTrue(source_use(self.root, manifest["source_id"])["read_only"])

    def test_immutable_experiment_and_event_chain(self):
        record = self.tmp / "experiment.json"
        record.write_text(json.dumps({
            "id": "run-1", "hypothesis": "one", "command": ["python", "-c", "pass"],
            "status": "SUCCESS", "raw_observations": [{"x": 1}], "metrics": {"accuracy": 1.0},
            "code_revision": "fixture", "seed": 7,
        }), encoding="utf-8")
        record_experiment(self.root, record)
        self.assertTrue(verify_event_chain(self.root))
        with self.assertRaises(SystemExit):
            record_experiment(self.root, record)

    def test_plan_requires_unique_ids(self):
        plan = self.tmp / "plan.json"
        plan.write_text(json.dumps({"objective": "x", "tasks": [{"id": "x", "acceptance": [], "required_evidence": []}, {"id": "x"}]}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            save_plan(self.root, plan)


    def test_record_renderer_links_immutable_records(self):
        source = self.tmp / "source.txt"
        source.write_text("A source claim.\n", encoding="utf-8")
        manifest = source_add(self.root, str(source), "CC0")
        descriptor = self.tmp / "evidence.json"
        descriptor.write_text(json.dumps({
            "id": "ev-render", "status": "VERIFIED", "source_id": manifest["source_id"],
            "claim": "A claim with 100% confidence", "locator": {"char_start": 0, "char_end": 15},
            "quote": "A source claim.",
        }), encoding="utf-8")
        add_evidence(self.root, descriptor)
        result = render_record_paper(self.root)
        generated = (self.root / result["generated"]).read_text(encoding="utf-8")
        manuscript = (self.root / "paper/main.tex").read_text(encoding="utf-8")
        self.assertIn("ev-render", generated)
        self.assertIn(r"\%", generated)
        self.assertIn(r"\input{howhow_records.tex}", manuscript)

    def test_immutable_review_record_binds_claim_and_span(self):
        from howhow.reviews import add, audit, status
        source = self.tmp / "review-source.txt"
        source.write_text("Reviewable claim.\n", encoding="utf-8")
        manifest = source_add(self.root, str(source), "CC0")
        descriptor = self.tmp / "review.json"
        descriptor.write_text(json.dumps({"id": "review-1", "reviewer": "human-1", "finding": "Check claim scope", "severity": "MAJOR", "claim": "Reviewable claim", "source_id": manifest["source_id"], "locator": {"char_start": 0, "char_end": 17}, "quote": "Reviewable claim."}), encoding="utf-8")
        add(self.root, descriptor)
        self.assertTrue(audit(self.root, strict=True)["passed"])
        self.assertEqual(status(self.root)["by_severity"]["MAJOR"], 1)
        with self.assertRaises(SystemExit):
            add(self.root, descriptor)

    def test_review_audit_revalidates_source_and_run_bindings(self):
        from howhow.reviews import add, audit
        source = self.tmp / "review-target-source.txt"
        source.write_text("Bound review target.\n", encoding="utf-8")
        manifest = source_add(self.root, str(source), "CC0")
        run_descriptor = self.tmp / "review-target-run.json"
        run_descriptor.write_text(json.dumps({
            "id": "review-target-run", "hypothesis": "fixture", "command": ["fixture"],
            "status": "SUCCESS", "raw_observations": [{"ok": True}], "metrics": {"count": 1},
            "code_revision": "fixture", "seed": 1,
        }), encoding="utf-8")
        record_experiment(self.root, run_descriptor)
        review_descriptor = self.tmp / "review-target.json"
        review_descriptor.write_text(json.dumps({
            "id": "review-target", "reviewer": "human-1", "finding": "Check retained targets",
            "severity": "MAJOR", "claim": "Bound target", "source_id": manifest["source_id"],
            "locator": {"char_start": 0, "char_end": 20}, "quote": "Bound review target.",
            "run_id": "review-target-run",
        }), encoding="utf-8")
        add(self.root, review_descriptor)
        self.assertTrue(audit(self.root, strict=True)["passed"])

        payload = self.root / ".howhow/sources/raw" / manifest["source_id"] / "payload"
        original_payload = payload.read_bytes()
        payload.write_text("mutated", encoding="utf-8")
        self.assertIn("source bytes failed integrity check", audit(self.root)["issues"][0])
        payload.write_bytes(original_payload)

        run_path = self.root / ".howhow/experiments/review-target-run.json"
        original_run = run_path.read_bytes()
        run_path.unlink()
        self.assertTrue(any("unknown run_id review-target-run" in issue for issue in audit(self.root)["issues"]))
        run_path.write_bytes(original_run)
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["metrics"] = {"count": 2}
        run_path.write_text(json.dumps(run), encoding="utf-8")
        self.assertTrue(any("experiment integrity check failed" in issue for issue in audit(self.root)["issues"]))
        self.assertFalse(audit(self.root, strict=True)["passed"])

    def test_verify_project_audits_immutable_reviews(self):
        from unittest.mock import patch
        from howhow.reviews import add
        source = self.tmp / "review-audit-source.txt"
        source.write_text("Auditable claim.\n", encoding="utf-8")
        manifest = source_add(self.root, str(source), "CC0")
        review = self.tmp / "review-audit.json"
        review.write_text(json.dumps({
            "id": "review-audit-1", "reviewer": "human-1", "finding": "Check claim",
            "severity": "MAJOR", "claim": "Auditable claim", "source_id": manifest["source_id"],
            "locator": {"char_start": 0, "char_end": 16}, "quote": "Auditable claim.",
        }), encoding="utf-8")
        add(self.root, review)
        record = self.tmp / "review-audit-run.json"
        record.write_text(json.dumps({
            "id": "review-audit-run", "hypothesis": "fixture", "status": "SUCCESS", "raw_observations": [{"ok": True}],
            "metrics": {"count": 1}, "command": ["fixture"], "code_revision": "fixture", "seed": 1,
        }), encoding="utf-8")
        record_experiment(self.root, record)
        review_path = self.root / ".howhow/reviews/review-audit-1.json"
        broken = json.loads(review_path.read_text(encoding="utf-8"))
        broken["finding"] = "Tampered finding"
        review_path.write_text(json.dumps(broken), encoding="utf-8")
        with patch("howhow.core.build_paper", return_value={"passed": True}), patch("howhow.core.package_paper", return_value={"files": [], "validation": {"passed": True}}):
            report = __import__("howhow.core", fromlist=["verify_project"]).verify_project(self.root)
            self.assertFalse(next(check for check in report["checks"] if check["name"] == "reviews")["passed"])
            with self.assertRaises(SystemExit):
                __import__("howhow.core", fromlist=["verify_project"]).verify_project(self.root, strict=True)

    def test_continue_blocks_without_strict_verification(self):
        plan = self.tmp / "empty-plan.json"
        plan.write_text(json.dumps({"objective": "x", "tasks": []}), encoding="utf-8")
        save_plan(self.root, plan)
        result = continue_project(self.root)
        self.assertEqual(result["state"], "BLOCKED")
        state = json.loads((self.root / ".howhow/state.json").read_text(encoding="utf-8"))
        self.assertNotEqual(state["state"], "COMPLETE")


if __name__ == "__main__":
    unittest.main()
