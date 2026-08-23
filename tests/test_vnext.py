import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from howhow.core import init_project, record_experiment, source_add
from howhow.vnext import (idea_add, idea_rank, idea_select, claim_add, claim_audit,
                          brief_propose, brief_confirm, target_propose, target_confirm,
                          capability_list)


class VNextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = init_project(str(self.tmp / 'p'))

    def idea(self, identifier, ok=True):
        return idea_add(self.root, {'id': identifier, 'title': identifier, 'question': 'q', 'evidence_plan': 'e',
            'gates': {x: ok for x in ('safety', 'ethics', 'license', 'data', 'evaluator', 'resource', 'evidence')}})

    def select_one(self):
        self.idea('a'); self.idea('b'); self.idea('c')
        idea_rank(self.root)
        idea_select(self.root, 'a')

    def test_empty_opinion_pins_and_manifest_capabilities(self):
        self.assertEqual((self.root / 'OPINION.md').stat().st_size, 0)
        self.assertEqual(len(json.loads((self.root / '.howhow/integration-manifest.json').read_text())['integrations']), 13)
        self.assertEqual(len(capability_list(self.root)['capabilities']), 13)

    def test_hard_gate_before_three_to_five_ranking(self):
        self.idea('bad', False); self.idea('a'); self.idea('b')
        with self.assertRaises(SystemExit): idea_rank(self.root)
        self.idea('c'); ranking = idea_rank(self.root)
        self.assertEqual(len(ranking['items']), 3)
        self.assertEqual(idea_select(self.root, 'a')['user_selected'], True)

    def test_confirmations_are_append_only_revisions(self):
        brief = brief_propose(self.root, 'bounded')
        confirmed = brief_confirm(self.root, brief['id'])
        self.assertEqual(json.loads((self.root / '.howhow/briefs' / (brief['id'] + '.json')).read_text())['status'], 'PROPOSED')
        self.assertEqual(confirmed['revision_of'], brief['id'])
        self.select_one()
        target = target_propose(self.root, 'a', words=100, argument_skeleton=['claim', 'evidence'])
        confirmed_target = target_confirm(self.root, target['id'], 'ACCEPT')
        self.assertEqual(json.loads((self.root / '.howhow/targets' / (target['id'] + '.json')).read_text())['status'], 'PROPOSED')
        self.assertEqual(confirmed_target['revision_of'], target['id'])
        with self.assertRaises(SystemExit): target_confirm(self.root, target['id'], 'REJECT')
        with self.assertRaises(SystemExit): target_propose(self.root, 'not-selected')

    def test_claim_audit_checks_source_and_run_bindings(self):
        source_file = self.tmp / 'source.txt'; source_file.write_text('bound source', encoding='utf-8')
        source = source_add(self.root, str(source_file), 'CC0')
        run_file = self.tmp / 'run.json'; run_file.write_text(json.dumps({'id': 'run-1', 'hypothesis': 'h', 'command': ['fixture'], 'status': 'SUCCESS', 'raw_observations': [{'ok': True}], 'metrics': {'n': 1}, 'code_revision': 'fixture', 'seed': 1}), encoding='utf-8')
        record_experiment(self.root, run_file)
        claim_add(self.root, {'id': 'c1', 'section': 'intro', 'paragraph': 'p1', 'type': 'EMPIRICAL', 'uncertainty': 'explicit', 'source_ids': [source['source_id']], 'run_ids': ['run-1']})
        self.assertTrue(claim_audit(self.root)['passed'])
        claim_add(self.root, {'id': 'c2', 'section': 'intro', 'paragraph': 'p2', 'type': 'EXTERNAL', 'uncertainty': 'explicit', 'source_ids': ['missing-source'], 'run_ids': ['missing-run']})
        audit = claim_audit(self.root)
        self.assertFalse(audit['passed'])
        self.assertTrue(any('unknown source_id' in issue for issue in audit['issues']))
        self.assertTrue(any('unknown run_id' in issue for issue in audit['issues']))

    def test_cli_phase_a_conversational_path(self):
        env = {**__import__('os').environ, 'PYTHONPATH': str(Path(__file__).parents[1])}
        commands = [['start'], ['brief', 'propose', 'bounded'], ['brief', 'confirm', 'brief-1']]
        for identifier in ('a', 'b', 'c'):
            idea_path = self.tmp / (identifier + '.json')
            idea_path.write_text(json.dumps({'id': identifier, 'title': identifier, 'question': 'q', 'evidence_plan': 'e',
                'gates': {x: True for x in ('safety', 'ethics', 'license', 'data', 'evaluator', 'resource', 'evidence')}}), encoding='utf-8')
            commands.append(['idea', 'add', str(idea_path)])
        commands += [['idea', 'rank'], ['idea', 'select', 'a'], ['target', 'propose', 'a'], ['target', 'confirm', 'target-1', 'ACCEPT'], ['claim', 'audit']]
        for command in commands:
            result = subprocess.run([sys.executable, '-m', 'howhow', *command], cwd=self.root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, ' '.join(command) + ': ' + result.stderr)
        self.assertTrue((self.root / '.howhow/briefs/brief-1.json').exists())
        self.assertTrue((self.root / '.howhow/targets/target-2-rev-2.json').exists())


if __name__ == '__main__':
    unittest.main()
