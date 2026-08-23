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
