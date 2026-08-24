import json
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path
from howhow.core import init_project
from howhow.vnext import brief_propose, brief_confirm, idea_add, idea_rank, idea_select, target_propose, target_confirm, claim_add
from howhow.paper import create_context, add_section, audit

class PaperTests(unittest.TestCase):
    def setUp(self):
        self.root = init_project(str(Path(tempfile.mkdtemp()) / 'p'))
        brief_confirm(self.root, brief_propose(self.root, 'fixture paper')['id'])
        for x in 'abc':
            idea_add(self.root, {'id': x, 'title': x, 'question': 'q', 'evidence_plan': 'fixture', 'gates': {k: True for k in ('safety','ethics','license','data','evaluator','resource','evidence')}})
        idea_rank(self.root); idea_select(self.root, 'a')
        target_confirm(self.root, target_propose(self.root, 'a')['id'], 'ACCEPT')
        claim_add(self.root, {'id': 'op-1', 'section': 'any', 'paragraph': 'p', 'type': 'OPINION', 'uncertainty': 'typed preference'})

    def test_cli_e2e_shows_expected_failure_then_fixture_success(self):
        result = subprocess.run([sys.executable, '-m', 'howhow', 'paper', 'context'], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)
        path = self.root / 'section.json'
        bad = self.root / 'bad-section.json'
        bad.write_text(json.dumps({'id': 'bad', 'type': 'ABSTRACT', 'paragraphs': [{'text': 'bad', 'claim_ids': ['missing']}] }), encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'howhow', 'paper', 'section', 'add', str(bad)], cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

        path.write_text(json.dumps({'id': 'cli-abstract', 'type': 'ABSTRACT', 'paragraphs': [{'text': 'Fixture uncertainty is disclosed.', 'claim_ids': ['op-1']}] }), encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'howhow', 'paper', 'section', 'add', str(path)], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['context_id'], context['id'])

    def test_context_and_import_are_immutable_and_anchored(self):
        context = create_context(self.root)
        self.assertTrue((self.root / '.howhow/paper/contexts' / (context['id'] + '.json')).exists())
        with self.assertRaises(SystemExit):
            add_section(self.root, {'id': 'bad', 'type': 'ABSTRACT', 'paragraphs': [{'text': 'x', 'claim_ids': ['missing']} ]})
        section = add_section(self.root, {'id': 'abstract', 'type': 'ABSTRACT', 'paragraphs': [{'text': 'A typed preference and uncertainty are disclosed.', 'claim_ids': ['op-1']}]})
        self.assertEqual(section['word_count'], 7)
        with self.assertRaises(SystemExit):
            add_section(self.root, {'id': 'abstract', 'type': 'ABSTRACT', 'paragraphs': [{'text': 'new', 'claim_ids': ['op-1']}]})

    def test_audit_uses_frozen_claim_snapshots(self):
        create_context(self.root)
        section = add_section(self.root, {'id': 'frozen', 'type': 'ABSTRACT', 'paragraphs': [{'text': 'A typed preference and uncertainty are disclosed.', 'claim_ids': ['op-1']}]})
        claim = json.loads((self.root / '.howhow/claims/op-1.json').read_text())
        claim['uncertainty'] = 'mutated after context'
        (self.root / '.howhow/claims/op-1.json').write_text(json.dumps(claim), encoding='utf-8')
        self.assertIn('claim snapshot mismatch', ' '.join(audit(self.root)['issues']))

    def test_audit_reports_failures_then_passes_non_scientific_fixture(self):
        create_context(self.root)
        self.assertFalse(audit(self.root)['passed'])
        for n, typ in enumerate(('TITLE_AND_CONTRIBUTIONS','ABSTRACT','INTRODUCTION','RELATED_WORK','QUESTION_HYPOTHESIS','METHODS_SYSTEM','ANALYSIS_EXPERIMENT_DESIGN','RESULTS','ROBUSTNESS_ABLATION_SENSITIVITY','DISCUSSION_COMPETING_EXPLANATIONS','THREATS','LIMITATIONS','ETHICS_RIGHTS_DUAL_USE','REPRODUCIBILITY','CONCLUSION','REFERENCES','APPENDICES')):
            text = 'fixture uncertainty input seed environment code data.' if typ == 'METHODS_SYSTEM' else ('Fixture ethics privacy and dual-use risk; uncertainty is disclosed.' if typ == 'ETHICS_RIGHTS_DUAL_USE' else ('Fixture threats, competing explanations, and alternative confounds; uncertainty is disclosed.' if typ in {'THREATS', 'DISCUSSION_COMPETING_EXPLANATIONS'} else 'Fixture non-scientific preference; uncertainty is disclosed.'))
            add_section(self.root, {'id': 's' + str(n), 'type': typ, 'paragraphs': [{'text': text, 'claim_ids': ['op-1']} ]})
        result = audit(self.root)
        self.assertTrue(result['passed'], result['issues'])
        self.assertIn('page count', result['contract'])

if __name__ == '__main__': unittest.main()
