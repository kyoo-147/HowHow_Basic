import json, tempfile, unittest
from pathlib import Path
from howhow.core import init_project, source_add, add_evidence, sha256_file
from howhow.vnext import claim_add
from howhow.d2 import add_artifact, artifact_audit, add_citation, citation_audit, add_issue, issue_audit, add_policy, policy_audit, d2_audit

class D2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.root = init_project(str(self.tmp/'p'))
        self.raw = self.root/'raw.csv'; self.raw.write_text('x,y\n1,2\n')
        self.script = self.root/'make.py'; self.script.write_text('print("fixture")\n')
        self.out = self.root/'paper/figures/fig-1.pdf'; self.out.write_bytes(b'%PDF fixture')
        srcfile = self.tmp/'source.txt'; srcfile.write_text('Supported claim.\n')
        src = source_add(self.root, str(srcfile), 'CC0')
        add_evidence(self.root, self.tmp/'ev.json') if False else None
        ev = self.tmp/'ev.json'; ev.write_text(json.dumps({'id':'ev-1','status':'VERIFIED','source_id':src['source_id'],'locator':{'char_start':0,'char_end':16},'quote':'Supported claim.'}))
        add_evidence(self.root, ev)
        claim_add(self.root, {'id':'claim-1','section':'results','paragraph':'p1','type':'EXTERNAL','uncertainty':'bounded','evidence_ids':['ev-1']})

    def artifact(self):
        return add_artifact(self.root, {'id':'fig-1','kind':'FIGURE','raw_inputs':[{'path':'raw.csv','sha256':sha256_file(self.raw)}], 'transformation':{'script':'make.py','script_sha256':sha256_file(self.script),'argv':['python','make.py'],'config':{}}, 'generated':{'path':'paper/figures/fig-1.pdf','sha256':sha256_file(self.out)}, 'units':{'x':'count'},'uncertainty':'not estimated','caption_claim_ids':['claim-1'],'accessibility_status':'PASS','visual_qa_status':'PASS','parents':{'source':[],'run':[]},'regeneration_receipt':{'command':['python','make.py'],'status':'RECEIVED'}})

    def test_artifact_tampering_and_citation_support_boundary(self):
        self.artifact(); self.assertTrue(artifact_audit(self.root)['passed'])
        self.out.write_bytes(b'mutated'); self.assertFalse(artifact_audit(self.root)['passed'])
        citation = add_citation(self.root, {'id':'cite-1','citation_key':'Key2024','bibliographic_identity':{'title':'Fixture'},'identifiers':{'doi':'10.1/test'},'identity_receipts':['receipt-url'],'support':{'claim_ids':[],'evidence_ids':[],'exact_links':[]},'correction_retraction_status':'CLEAR','access_redistribution':'CC0'})
        self.assertEqual(citation['support_status'],'UNVERIFIED'); self.assertTrue(citation_audit(self.root)['passed'])

    def test_issue_labels_resolution_rebuttal_dissent_and_policy_block(self):
        add_issue(self.root, {'id':'i-open','severity':'BLOCKING','finding':'needs review','disposition':'OPEN','anchors':{'manuscript':'results:p1'},'reviewer':'model','review_kind':'MACHINE_ASSISTED','context':{'model':'fixture'},'execution_contract':{'action':'propose'}})
        self.assertFalse(issue_audit(self.root)['passed'])
        add_issue(self.root, {'id':'i-dissent','severity':'DISSENT','finding':'alternative reading','disposition':'REBUTTED','anchors':{'evidence':'ev-1'},'reviewer':'human','review_kind':'HUMAN','context':{'meeting':'fixture'},'execution_contract':{'action':'preserve'},'linked_rebuttal_ids':['reb-1']})
        add_policy(self.root, {'id':'policy-license','kind':'DATA','state':'UNKNOWN','subject':'fixture-data','disclosure':'redistribution status unknown','human_review_boundary':'human must decide'})
        self.assertFalse(policy_audit(self.root)['passed'])
        self.assertFalse(d2_audit(self.root)['passed'])

if __name__ == '__main__': unittest.main()
