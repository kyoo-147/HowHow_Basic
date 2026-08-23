import sys, tempfile, unittest
from pathlib import Path
from howhow.core import init_project
from howhow.vnext import GATES, brief_confirm, brief_propose, idea_add, idea_rank, idea_select
from howhow.experiment_v2 import proposal_create, grant_issue, run_grant, experiment_audit, objective_save

class PhaseCContractTests(unittest.TestCase):
    def setUp(self):
        self.root = init_project(tempfile.mkdtemp())
        brief = brief_confirm(self.root, brief_propose(self.root, 'bounded')['id'])
        for ident in ('a', 'b', 'c'):
            idea_add(self.root, {'id': ident, 'title': ident, 'question': 'q', 'evidence_plan': 'e', 'gates': {k: True for k in GATES}})
        idea_rank(self.root); idea_select(self.root, 'a')
        self.brief = brief['id']
        objective_save(self.root, {'id': 'objective-1', 'primary_metrics': ['score'], 'baseline': 'baseline command', 'outcome_definitions': {'score': 'printed score'}, 'stopping_rules': ['stop after bounded repetitions'], 'repetitions': 1, 'uncertainty_method': 'descriptive', 'known_confounders': [], 'ablation_plan': ['remove declared change'], 'no_progress_policy': 'stop after one non-improving attempt'})

    def proposal(self):
        return proposal_create(self.root, {'id': 'proposal-1', 'idea_id': 'a', 'brief_id': self.brief,
            'command': [sys.executable, '-c', 'print("baseline")'], 'cwd': '.', 'inputs': [], 'outputs': [],
            'seed': 3, 'trust_profile': 'TRUSTED_LOCAL', 'policy_revision': 'phase-c-1',
            'cleanup_plan': 'retain evidence', 'evidence_plan': 'raw observations', 'bounds': {'timeout_seconds': 3},
            'network': 'possible', 'design_level': 'EXPLORATORY', 'baseline': 'baseline command', 'declared_change': 'none', 'ablation_plan': ['remove change'], 'no_progress_policy': 'stop after one non-improving attempt', 'objective_id': 'objective-1'})

    def test_one_shot_grant_and_truthful_warning(self):
        self.proposal(); grant = grant_issue(self.root, 'proposal-1', 'project', 'human', '2099-01-01T00:00:00Z')
        result = run_grant(self.root, grant['id'])
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(result['runner']['trust_profile'], 'TRUSTED_LOCAL')
        with self.assertRaises(SystemExit): run_grant(self.root, grant['id'])
        self.assertTrue(experiment_audit(self.root)['passed'])

    def test_mutated_input_and_disabled_profile_fail_closed(self):
        script = self.root / 'script.py'; script.write_text('print(1)', encoding='utf-8')
        value = self.proposal(); value.update(id='proposal-2', command=['script.py'], inputs=['script.py'])
        proposal_create(self.root, value)
        script.write_text('print(2)', encoding='utf-8')
        grant_issue(self.root, 'proposal-2', 'project', 'human', '2099-01-01T00:00:00Z')
        grant = next(iter((self.root / '.howhow/grants').glob('*.json')))
        with self.assertRaises(SystemExit): run_grant(self.root, grant.stem)
        value.update(id='proposal-disabled', trust_profile='OS_ISOLATED')
        with self.assertRaises(SystemExit): proposal_create(self.root, value)

if __name__ == '__main__': unittest.main()
