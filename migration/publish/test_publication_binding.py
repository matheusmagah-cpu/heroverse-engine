import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
import publication_binding as binding
import three_stage
import test_prepublish_gate as gate_fixture

ROOT = Path(__file__).resolve().parents[2]


def documents():
    d=ROOT/'migration/production/pilot-012'
    return [json.loads((d/p).read_bytes()) for p in binding.FILES]


class Tests(unittest.TestCase):
    def test_e169_publication_reads_the_same_story_dimensions_and_rows_as_the_canonical_gate(self):
        # Synthetic evidence for reader parity only, never an actual QA or approval of a production video.
        for version in binding.canonical_gate.STORY_VERSIONS:
            with self.subTest(version=version):
                qa, manifest, review = gate_fixture.good()
                qa.update(criteria_version=version,
                          criteria_sha256=binding.canonical_gate.FROZEN_CRITERIA_SHA256[version],
                          checks={key: True for names in binding.canonical_gate.story_v3_rows(version).values()
                                  for key in names})
                review['scorecard_hard'] = {'minutes': {'value': 15, 'pass': True}}
                row = {'name': 'fixture', 'state': 'PASS', 'value': 'offline parity fixture'}
                with mock.patch.object(three_stage, 'structure_rows', return_value=[row]), \
                        mock.patch.object(three_stage, 'authenticity_rows', return_value=[row]):
                    gate = gate_fixture.run(qa, manifest, review)
                self.assertEqual(gate['decision'], 'PASS')
                approval = {'approved': True, 'output_sha256': qa['output_sha256']}
                self.assertEqual(binding.check(qa, approval, manifest, gate), [])
                self.assertNotIn('title_card_seconds', {x['item'] for x in gate['items']['image']})
                name = 'story_qa_' + version.rsplit('-', 1)[-1]
                missing = copy.deepcopy(gate); missing['items'][name].pop()
                self.assertIn('GATE_CANONICAL_ITEMS_MISSING:' + name,
                              binding.check(qa, approval, manifest, missing))
                missing = copy.deepcopy(gate)
                del missing['items'][name]; del missing['dimensions'][name]
                self.assertIn('GATE_CANONICAL_DIMENSIONS_MISSING', binding.check(qa, approval, manifest, missing))

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
    def test_missing_each_canonical_dimension(self):
        self.assertEqual(len(documents()[3]['dimensions']),14)
        for name in documents()[3]['dimensions']:
            d=documents();del d[3]['dimensions'][name];del d[3]['items'][name]
            self.assertIn('GATE_CANONICAL_DIMENSIONS_MISSING',binding.check(*d),name)
    def test_missing_static_required_item(self):
        d=documents();d[3]['items']['audio']=[r for r in d[3]['items']['audio'] if r['item']!='integrated_lufs']
        self.assertIn('GATE_CANONICAL_ITEMS_MISSING:audio',binding.check(*d))
    def test_unknown_criteria_version(self):
        d=documents();d[0]['criteria_version']='unknown'
        self.assertIn('QA_CRITERIA_VERSION_UNKNOWN',binding.check(*d))
    def test_existing_review_binding(self):
        d=documents();review={'status':'PASS','output_sha256':d[0]['output_sha256']}
        self.assertEqual(binding.check(*d,review=review),[])
        for bad in ({'status':'FAIL','output_sha256':d[0]['output_sha256']},{'status':'PASS','output_sha256':'b'*64},[]):
            self.assertIn('REVIEW_NOT_PASS_FOR_THIS_FILE',binding.check(*d,review=bad))

    def test_cli_optimized_missing_malformed_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            for p,doc in zip(binding.FILES,documents()):
                f=d/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(doc))
            (d/'script.json').write_text(json.dumps({'archetype':'bible-story-long'}))  # only a story long publishes
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


class RetiredPrayerLongs(unittest.TestCase):
    """Owner, 2026-10-26: "stop the prayer videos". publish.yml runs this binding before any upload or resume, so a
    prayer pilot is refused here even with a recorded approval and a PASS gate (pilot-012 holds both)."""
    def run_main(self, archetype):
        import contextlib, io
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'pilot-012'
            for p, doc in zip(binding.FILES, documents()):
                f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(doc))
            if archetype is not None:
                (d / 'script.json').write_text(json.dumps({'archetype': archetype}))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = binding.main(d)
            return code, json.loads(out.getvalue())

    def test_prayer_pilot_is_refused_even_when_approved(self):
        for archetype in ('migration/strategy/FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md', None):
            code, out = self.run_main(archetype)
            self.assertEqual((code, 'NOT_STORY_LONG' in out['problems']), (1, True), archetype)

    def test_story_long_passes_its_format_row(self):
        self.assertEqual(self.run_main('bible-story-long'), (0, {'status': 'PASS', 'problems': [],
                                                                  'output_sha256': documents()[0]['output_sha256']}))


if __name__=='__main__':unittest.main()
