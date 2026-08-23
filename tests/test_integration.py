from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliIntegrationTests(unittest.TestCase):
    def test_cli_lifecycle_and_human_boundary(self):
        root = Path(tempfile.mkdtemp()) / "demo"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        def run(*args):
            return subprocess.run([sys.executable, "-m", "howhow", *args], cwd=root if root.exists() else root.parent, env=env, text=True, capture_output=True, check=True)
        run("init", str(root), "--goal", "bounded test")
        plan = root / "plan.json"
        plan.write_text(json.dumps({"objective": "bounded", "tasks": [{"id": "human", "kind": "human", "instruction": "confirm", "acceptance": [], "required_evidence": []}]}), encoding="utf-8")
        run_in_project = lambda *args: subprocess.run([sys.executable, "-m", "howhow", *args], cwd=root, env=env, text=True, capture_output=True, check=True)
        run_in_project("plan", "save", "plan.json")
        pending = json.loads(run_in_project("continue").stdout)
        self.assertEqual(pending["state"], "NEEDS_HUMAN")
        run_in_project("pause", "integration pause")
        state = json.loads(run_in_project("status", "--json").stdout)
        self.assertEqual(state["state"]["state"], "PAUSED")
        run_in_project("resume")
        self.assertTrue((root / ".howhow/events.jsonl").exists())
        runner = root / "runner.py"
        runner.write_text("import os; print('seed=' + os.environ['HOWHOW_SEED'])\n", encoding="utf-8")
        experiment = root / "experiment-run.json"
        experiment.write_text(json.dumps({
            "id": "cli-bounded-run", "hypothesis": "the declared seed is injected",
            "command": [sys.executable, "runner.py"], "code_revision": "integration-fixture", "seed": 23,
            "inputs": ["runner.py"], "timeout_seconds": 5,
        }), encoding="utf-8")
        recorded = json.loads(run_in_project("experiment", "run", "experiment-run.json").stdout)
        self.assertEqual(recorded["status"], "SUCCESS")
        self.assertEqual(recorded["raw_observations"][0]["stdout"].splitlines(), ["seed=23"])
        self.assertTrue((root / ".howhow/experiments/cli-bounded-run.json").is_file())

    @unittest.skipUnless(__import__("shutil").which("pdflatex") and __import__("shutil").which("bibtex"), "LaTeX toolchain required")
    def test_claimledger_full_finalization_rebuilds_source_package(self):
        import shutil

        repository = Path(__file__).resolve().parents[1]
        source = repository / "projects/claimledger"
        root = Path(tempfile.mkdtemp()) / "claimledger"
        shutil.copytree(source, root)
        shutil.rmtree(root / ".howhow/builds", ignore_errors=True)
        shutil.rmtree(root / ".howhow/verify", ignore_errors=True)
        shutil.rmtree(root / "dist", ignore_errors=True)
        (root / ".howhow/builds").mkdir(parents=True)
        (root / ".howhow/verify").mkdir(parents=True)
        (root / "dist").mkdir(parents=True)
        state_path = root / ".howhow/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.update({"state": "READY", "paused": False, "current_task": None})
        state_path.write_text(json.dumps(state), encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repository)
        proc = subprocess.run(
            [sys.executable, "-m", "howhow", "paper", "finalize"],
            cwd=root, env=env, text=True, capture_output=True, timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["state"], "READY_FOR_HUMAN_REVIEW")
        manifest = json.loads((root / "dist/source-manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["validation"]["clean_room_rebuild"]["passed"])
        self.assertTrue((root / "dist/paper.pdf").is_file())
        self.assertTrue((root / "dist/arxiv-source.tar.gz").is_file())


if __name__ == "__main__":
    unittest.main()
