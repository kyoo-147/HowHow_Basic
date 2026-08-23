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


if __name__ == "__main__":
    unittest.main()
