import json
import tempfile
import unittest
from pathlib import Path
from howhow.core import init_project, source_add, add_evidence
from howhow.literature import (add_matrix, add_transformed, audit, candidate_adapter_request,
    create_protocol, decide_candidate, import_candidate)

class LiteratureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.root = init_project(str(self.tmp / 'p'))
        self.body = self.tmp / 'paper.txt'; self.body.write_text('Retained passage.\n', encoding='utf-8')
        self.source = source_add(self.root, str(self.body), 'CC-BY')
        desc = self.tmp / 'e.json'; desc.write_text(json.dumps({'id':'ev-lit','status':'VERIFIED','source_id':self.source['source_id'],'quote':'Retained passage.','locator':{'char_start':0,'char_end':17}}), encoding='utf-8')
        add_evidence(self.root, desc)

    def test_protocol_adapter_decision_matrix_and_coverage(self):
        request = candidate_adapter_request('gpt-researcher','q')
        create_protocol(self.root, {'id':'protocol-1','questions':['q1'],'claims':['c1'],'filters':{'language':'en'},'date_cutoff':'2025-01-01','retrieval_timestamp':'fixture','queries':['q'],'query_receipts':[{'receipt_id':'receipt-1','provider':'gpt-researcher','query':'q'}],'candidate_result_ids':['cand-1'],'saturation':{'result_count':1,'queries_covered':1,'stopping_test':'fixture saturation test'},'contradiction_search':{'queries':['q contradiction'],'performed':True},'stop_rationale':'fixture saturation'})
        self.assertFalse(request['live'])
        with self.assertRaises(SystemExit): candidate_adapter_request('arxiv','q')
        import_candidate(self.root, {'candidate_id':'cand-1','provider':'gpt-researcher','query_receipt':{'receipt_id':'receipt-1','provider':'gpt-researcher','query':'q'},'url':'https://example.invalid/paper','document_id':'doc-1','protocol_id':'protocol-1','adapter_request':request})
        decide_candidate(self.root, 'cand-1', 'INCLUDED', 'retained and accessible', self.source['source_id'])
        with self.assertRaises(SystemExit): decide_candidate(self.root, 'cand-1', 'INCLUDED', 'bad', 'missing-source')
        add_matrix(self.root, {'id':'m-1','question':'q1','role':'NEAREST','source_ids':[self.source['source_id']],'evidence_ids':['ev-lit'],'status':'RETAINED'})
        add_matrix(self.root, {'id':'m-2','claim':'c1','role':'SUPPORTING','source_ids':[self.source['source_id']],'evidence_ids':['ev-lit'],'status':'RETAINED'})
        self.assertTrue(audit(self.root)['passed'])

    def test_transformed_text_fails_closed_on_parent_or_derived_tampering(self):
        extracted = self.tmp / 'extracted.txt'; extracted.write_text('Retained passage.', encoding='utf-8')
        add_transformed(self.root, {'id':'tx-1','parent_source_id':self.source['source_id'],'extractor':'fixture/1','config_hash':'sha256:config','page_mapping':[{'page':1,'start':0,'end':17}],'locator':{'page':1,'text_start':0,'text_end':17}}, extracted)
        self.assertTrue(audit(self.root)['passed'])
        (self.root / '.howhow/literature/extracted/tx-1.txt').write_text('mutated', encoding='utf-8')
        self.assertFalse(audit(self.root)['passed'])

    def test_transformed_evidence_is_auditable(self):
        extracted = self.tmp / 'derived.txt'; extracted.write_text('Derived passage.', encoding='utf-8')
        add_transformed(self.root, {'id':'tx-e','parent_source_id':self.source['source_id'],'extractor':'fixture/1','config_hash':'sha256:config','page_mapping':[{'page':1,'start':0,'end':16}],'locator':{'page':1,'text_start':0,'text_end':16}}, extracted)
        desc = self.tmp / 'derived-e.json'; desc.write_text(json.dumps({'id':'ev-derived','status':'VERIFIED','transformed_source_id':'tx-e','quote':'Derived passage.','locator':{'char_start':0,'char_end':16}}), encoding='utf-8')
        add_evidence(self.root, desc)
        self.assertTrue(__import__('howhow.core', fromlist=['audit_evidence']).audit_evidence(self.root, strict=True)['passed'])
        (self.root / '.howhow/sources/raw' / self.source['source_id'] / 'payload').write_text('tampered', encoding='utf-8')
        self.assertFalse(audit(self.root)['passed'])

if __name__ == '__main__': unittest.main()
