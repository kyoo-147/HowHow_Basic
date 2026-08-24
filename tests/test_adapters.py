import json
import tempfile
import unittest
from pathlib import Path

from howhow.core import init_project
from howhow.adapters import REPO_PINS, contract, doctor, export_contract, import_contract, validate_import, FIXTURE_ROOT


class E1AdapterTests(unittest.TestCase):
    def setUp(self):
        self.root = init_project(str(Path(tempfile.mkdtemp()) / 'p'))

    def test_every_pinned_repository_has_concrete_contract_and_fixture(self):
        self.assertEqual(len(REPO_PINS), 13)
        for repo in REPO_PINS:
            c = contract(repo)
            self.assertTrue(c['required_upstream_files'])
            self.assertTrue(c['operations'])
            self.assertEqual(c['pin'], REPO_PINS[repo])
            source = c['required_upstream_files'][0]
            fixture = Path(source['fixture'])
            self.assertTrue(fixture.is_file())
            self.assertEqual(source['sha256'], __import__('hashlib').sha256(fixture.read_bytes()).hexdigest())
            self.assertNotIn('/', source['path'].rstrip('/')) if source['path'].endswith('/') else None
            payload = {'artifact_id': 'fixture', 'cross_links': []}
            if repo == 'AI-Scientist': payload['enablement'] = {'restricted_use_acknowledged': True, 'manuscript_ai_disclosure': True}
            if repo == 'DeepScientist': payload['restricted_use_acknowledged'] = True
            envelope = export_contract(repo, c['operations'][0], payload)
            self.assertEqual(validate_import(envelope)['state'], 'PROVISIONAL')

    def test_doctor_missing_checkout_is_not_failure_and_is_read_only(self):
        before = sorted(str(p) for p in (self.root / '.howhow').rglob('*'))
        result = doctor(self.root)
        self.assertTrue(all(x['state'] == 'AVAILABLE_CONTRACT_NOT_INSTALLED' for x in result['integrations']))
        self.assertEqual(before, sorted(str(p) for p in (self.root / '.howhow').rglob('*')))

    def test_tamper_wrong_pin_and_restricted_license_fail_closed(self):
        envelope = export_contract('gpt-researcher', 'candidate-output', {'candidate_id': 'c'})
        bad = dict(envelope); bad['pin'] = '0' * 40
        with self.assertRaises(SystemExit): validate_import(bad)
        bad = dict(envelope); bad['payload'] = dict(envelope['payload'], changed=True)
        with self.assertRaises(SystemExit): validate_import(bad)
        ai = export_contract('AI-Scientist', 'template-run-writeup', {'x': 1})
        with self.assertRaises(SystemExit): validate_import(ai)
        ai = export_contract('AI-Scientist', 'template-run-writeup', {'enablement': {'restricted_use_acknowledged': True, 'manuscript_ai_disclosure': True}})
        self.assertEqual(import_contract(self.root, ai)['state'], 'PROVISIONAL')
        self.assertEqual(len(list((self.root / '.howhow/integrations/receipts').glob('*.json'))), 1)

    def test_import_retains_raw_receipt_and_never_promotes(self):
        env = export_contract('wanshuiyin ARIS', 'idea-dossier', {'idea_id': 'i', 'cross_links': []})
        result = import_contract(self.root, env)
        stored = json.loads(next((self.root / '.howhow/integrations/receipts').glob('*.json')).read_text())
        self.assertTrue(result['raw_receipt_retained'])
        self.assertEqual(stored['state'], 'PROVISIONAL')
        self.assertNotIn('VERIFIED', stored.get('state', ''))

    def test_resigned_schema_state_links_and_restricted_modes_fail_closed(self):
        env = export_contract('gpt-researcher', 'candidate-output', {'candidate_id': 'c'})
        for field, value in [('schema_version', 999), ('state', 'VERIFIED')]:
            bad = dict(env); bad[field] = value
            bad['envelope_sha256'] = __import__('howhow.core', fromlist=['sha256_bytes']).sha256_bytes(__import__('howhow.core', fromlist=['canonical']).canonical({k:v for k,v in bad.items() if k != 'envelope_sha256'}))
            with self.assertRaises(SystemExit): validate_import(bad)
        linked = export_contract('gpt-researcher', 'candidate-output', {'cross_links': ['missing-id']})
        with self.assertRaises(SystemExit): validate_import(linked, set())
        offline = export_contract('OpenScholar', 'rerank-synthesis', {'fetching': True})
        with self.assertRaises(SystemExit): validate_import(offline)
        restricted = export_contract('DeepScientist', 'quest-run', {'x': 1})
        with self.assertRaises(SystemExit): validate_import(restricted)


if __name__ == '__main__': unittest.main()
