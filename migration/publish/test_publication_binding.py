import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import publication_binding as binding

ROOT = Path(__file__).resolve().parents[2]


def documents():
    sha='a'*64
    return [{'status':'PASS','output_sha256':sha}, {'approved':True,'output_sha256':sha},
            {'output_sha256':sha}, {'version':'prepublish-gate-v1','output_sha256':sha,'decision':'PASS',
             'eligible_for_automatic_publication':True,'dimensions':{'binding':'PASS'},
             'items':{'binding':[{'state':'PASS'}]}}]


class Tests(unittest.TestCase):
    def test_valid(self): self.assertEqual(binding.check(*documents()),[])
    def test_reviewer_cannot_bypass(self):
        for reviewer in ('HeroVerse automatic gates','HeroVerse three-stage approval','Owner','',None,'unknown'):
            for state in ('FAIL','UNKNOWN',None):
                d=documents();d[1]['reviewer']=reviewer;d[3]['decision']=state
                self.assertIn('GATE_NOT_PASS',binding.check(*d))
    def test_missing_gate_for_every_reviewer(self):
        for reviewer in ('HeroVerse automatic gates','HeroVerse three-stage approval','Owner',''):
            d=documents();d[1]['reviewer']=reviewer;d[3]=None
            self.assertTrue(binding.check(*d))
    def test_hash_binding_each_document(self):
        for i in range(4):
            d=documents();d[i]['output_sha256']='b'*64
            self.assertIn('EVIDENCE_NOT_FOR_THIS_FILE',binding.check(*d))
    def test_empty_invalid_hash(self):
        for value in ('',None,False,'x'*64,'A'*64,'a'*63):
            d=documents();d[0]['output_sha256']=value
            self.assertIn('INVALID_OUTPUT_SHA256',binding.check(*d))
    def test_approval_boolean(self):
        for value in (False,1,'true',None):
            d=documents();d[1]['approved']=value
            self.assertIn('NOT_APPROVED',binding.check(*d))
    def test_qa_fail_unknown(self):
        for value in ('FAIL','UNKNOWN',None):
            d=documents();d[0]['status']=value;self.assertIn('QA_NOT_PASS',binding.check(*d))
    def test_gate_summary_inconsistent(self):
        for key,value in [('dimensions',{}),('items',{}),('dimensions',{'binding':'FAIL'}),('items',{'binding':[]}),
                          ('items',{'binding':[{'state':'UNKNOWN'}]}),('items',{'other':[{'state':'PASS'}]}),
                          ('eligible_for_automatic_publication',1),('version','wrong')]:
            d=documents();d[3][key]=value;self.assertTrue(binding.check(*d),(key,value))
    def test_non_objects(self):
        for i in range(4):
            for value in ([],None,True,'PASS'):
                d=documents();d[i]=value;self.assertTrue(binding.check(*d))
    def test_no_mutation(self):
        d=documents();before=copy.deepcopy(d);binding.check(*d);self.assertEqual(d,before)
    def test_actual012(self):
        d=ROOT/'migration/production/pilot-012';docs=[json.loads((d/p).read_bytes()) for p in binding.FILES]
        self.assertEqual(binding.check(*docs),[])
    def test_cli_optimized_missing_malformed_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            for p,doc in zip(binding.FILES,documents()):
                f=d/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(doc))
            def run():return subprocess.run([sys.executable,'-I','-O','-B',binding.__file__,str(d)],capture_output=True,text=True)
            self.assertEqual(run().returncode,0)
            gate=d/binding.FILES[-1];gate.write_text('{bad');self.assertNotEqual(run().returncode,0)
            gate.unlink();self.assertNotEqual(run().returncode,0)
    def test_workflow_calls_helper_before_upload(self):
        text=(ROOT/'.github/workflows/publish.yml').read_text()
        invocation='python3 -I -B migration/publish/publication_binding.py "$d"'
        self.assertEqual(text.count(invocation),1);self.assertNotIn('startswith("HeroVerse automatic gates")',text)
        self.assertLess(text.index(invocation),text.index('      - name: Preflight'))
        self.assertLess(text.index('PUBLICATION_HOLD'),text.index(invocation))


if __name__=='__main__':unittest.main()
