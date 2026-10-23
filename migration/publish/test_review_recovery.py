#!/usr/bin/env python3
"""Synthetic known answers; no provider, credentials or live media operations."""
import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_recovery as r

# Historical shape, deliberately independent of the live output changed by recovery.
# Values below are synthetic and never constitute media qualification.
SOURCE_FIXTURE = {
    'version':'shorts-v1', 'source_pilot':'pilot-006',
    'selection_rubric_model':'fixture', 'rejected_r8':[],
    'review_rubric':{'pass_item':7,'pass_overall':8},
    'shorts':[
        {'file':f'short-{i:02d}.mp4','sha256':str(i+1)*64,'seconds':35.2,
         'source_start':1311.607,'source_end':1346.297,'segments':[{'start':1311.607,'end':1346.297}],
         'hook':'Synthetic fixture prayer','hook_shown':False,'title':'Synthetic fixture title',
         'reference':'Philippians 4:6-7','scenes':[],'parallax':False,'figure':None,
         'selection':{'final_score':0.8},'text':'Synthetic fixture text, not a real Scripture quote.',
         'qa':{'status':'PASS'},'review':{'status':'NOT_REVIEWED_ProviderFailure'},'publish':False}
        for i in range(3)]}



class Recovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pilot = self.root / 'migration/production/pilot-006'
        (self.pilot / 'shorts').mkdir(parents=True)
        self.path = self.pilot / 'shorts/shorts.json'
        self.media = self.pilot / 'shorts/short-00.mp4'
        self.media.write_bytes(b'synthetic known media, not a qualified video')
        self.hash = hashlib.sha256(self.media.read_bytes()).hexdigest()
        self.original = copy.deepcopy(SOURCE_FIXTURE)
        self.original['shorts'][0]['sha256'] = self.hash
        self.path.write_text(json.dumps(self.original))
        self.source_hash = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.selection = r.SELECTION | {'output_sha256': self.hash, 'source_manifest_sha256': self.source_hash}
        self.selection_path = self.root / 'selection.json'
        self.selection_path.write_text(json.dumps(self.selection))
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in [('OUTPUT_SHA256', self.hash), ('SOURCE_SHA256', self.source_hash), ('SELECTION', self.selection)]:
            self.stack.enter_context(patch.object(r, name, value))
        self.stack.enter_context(patch.dict('os.environ', {'GITHUB_RUN_ID':'123', 'GITHUB_RUN_ATTEMPT':'1'}))
        self.now = datetime(2026,10,21,12,tzinfo=timezone.utc)
        self.stack.enter_context(patch.object(r, 'utc_now', side_effect=lambda:self.now))
        self.prereq = Mock(return_value=[])
        self.provider = Mock(side_effect=self.good_review)
        self.stack.enter_context(patch.dict(sys.modules, {
            'shorts_prerequisite':types.SimpleNamespace(problems=self.prereq),
            'shorts_review':types.SimpleNamespace(main=self.provider)}))

    def good_review(self, directory, n):
        self.assertEqual(n, '1')
        p = Path(directory) / 'shorts.json'
        value = json.loads(p.read_bytes())
        self.assertEqual(len(value['shorts']),1)
        rec = value['shorts'][0]
        rec.update(qa={'status':'PASS'}, qa_output_sha256=self.hash,
                   review={'status':'PASS','model':'gemini-3.8-flash','overall':9.6,'output_sha256':self.hash},
                   publish=True, owner_quality_policy={'status':'PASS','minimum_overall':9.5,'problems':[]})
        p.write_text(json.dumps(value))

    def run_review(self):
        return r.review_selected(self.pilot,self.selection_path)

    def assert_preflight_blocked(self):
        with self.assertRaises((ValueError,OSError)):
            self.run_review()
        self.provider.assert_not_called()

    def alter_original(self, fn):
        data=json.loads(self.path.read_bytes());fn(data)
        self.path.write_text(json.dumps(data))
        newhash=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.stack.enter_context(patch.object(r,'SOURCE_SHA256',newhash))
        self.selection['source_manifest_sha256']=newhash
        self.selection_path.write_text(json.dumps(self.selection))

    def test_success_one_record_and_source_preserved(self):
        result=self.run_review();self.provider.assert_called_once()
        self.assertEqual(result['shorts'][1:],self.original['shorts'][1:])
        for key,value in self.original['shorts'][0].items():
            if key not in r.MUTABLE:self.assertEqual(result['shorts'][0][key],value)
        self.assertEqual(result['shorts'][0]['previous_review'],{'status':r.ORIGINAL_STATUS})
        self.assertEqual(sum(x['publish'] for x in result['shorts']),1)
        self.assertEqual(r.binding(result)['target_slot'],r.TARGET_SLOT)
        self.assertEqual(result,json.loads(self.path.read_bytes()))

    def test_repeat_blocked_before_provider(self):
        self.run_review();self.provider.reset_mock();self.assert_preflight_blocked()

    def test_source_hash_changed(self):
        self.path.write_bytes(self.path.read_bytes()+b'\n');self.assert_preflight_blocked()

    def test_selection_exact_schema(self):
        for key,value in [('pilot','pilot-007'),('file','../short-00.mp4'),('output_sha256','0'*64),
                          ('extra','value'),('target_slot','2026-10-21T20:00:00Z'),('version',True)]:
            with self.subTest(key=key):
                self.selection_path.write_text(json.dumps(self.selection|{key:value}));self.assert_preflight_blocked()
        self.selection_path.write_text(json.dumps(self.selection))

    def test_previous_pass_and_fail_disallowed(self):
        for status in ('PASS','FAIL',None):
            with self.subTest(status=status):
                self.alter_original(lambda x:x['shorts'][0].update(review={'status':status}))
                self.assert_preflight_blocked()

    def test_nonselected_true_disallowed(self):
        self.alter_original(lambda x:x['shorts'][1].update(publish=True));self.assert_preflight_blocked()

    def test_wrong_media_hash(self):
        self.media.write_bytes(b'changed');self.assert_preflight_blocked()

    def test_long_not_qualified(self):
        self.prereq.return_value=['FAIL'];self.assert_preflight_blocked()

    def test_missing_execution(self):
        with patch.dict('os.environ',{'GITHUB_RUN_ID':''}):self.assert_preflight_blocked()

    def test_symlink_media_disallowed(self):
        other=self.root/'other';other.write_bytes(self.media.read_bytes());self.media.unlink();self.media.symlink_to(other)
        self.assert_preflight_blocked()

    def test_symlink_pilot_disallowed(self):
        alias=self.root/'pilot-006';alias.symlink_to(self.pilot,target_is_directory=True)
        with self.assertRaises(ValueError):r.prepare(alias,self.selection_path)

    def test_wrong_pilot_directory(self):
        with self.assertRaises(ValueError):r.prepare(self.root,self.selection_path)

    def test_cli_list_exact(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):r.main('--list',str(self.pilot),str(self.selection_path))
        self.assertEqual(out.getvalue(),f'short-00.mp4 {self.hash}\n');self.provider.assert_not_called()

    def test_cli_unknown_mode(self):
        with self.assertRaises(ValueError):r.main('--bad',self.pilot,self.selection_path)

    def test_boundary(self):
        self.now=datetime(2026,10,21,13,15,tzinfo=timezone.utc)
        self.assertTrue(self.run_review()['shorts'][0]['publish'])

    def test_late_keeps_review_but_blocks(self):
        self.now=datetime(2026,10,21,13,15,1,tzinfo=timezone.utc)
        result=self.run_review();self.assertFalse(result['shorts'][0]['publish'])
        self.assertEqual(result['shorts'][0]['release_status'],'TARGET_SLOT_LEAD_MISSED')
        self.assertEqual(result['shorts'][0]['review']['overall'],9.6)

    def test_provider_exception_preserves_canonical(self):
        before=self.path.read_bytes();self.provider.side_effect=RuntimeError('synthetic')
        with self.assertRaises(RuntimeError):self.run_review()
        self.assertEqual(self.path.read_bytes(),before)

    def mutate_output(self,fn):
        def review(d,n):
            self.good_review(d,n);p=Path(d)/'shorts.json';value=json.loads(p.read_bytes());fn(value,d);p.write_text(json.dumps(value))
        self.provider.side_effect=review

    def test_false_results_are_preserved(self):
        for status,overall,qa in [('FAIL',9.5,'PASS'),('PASS',8.99,'PASS'),('NOT_REVIEWED_ProviderFailure',None,'PASS'),('NOT_REVIEWED_QA_FAIL',None,'FAIL')]:
            with self.subTest(status=status,overall=overall):
                self.path.write_text(json.dumps(self.original))
                def change(v,d):
                    rec=v['shorts'][0];rec['publish']=False;rec['qa']={'status':qa}
                    rec['review']=({'status':status} if overall is None else {'status':status,'overall':overall,'model':'gemini-3.8-flash','output_sha256':self.hash})
                    rec['owner_quality_policy']={'status':'FAIL','minimum_overall':9,'problems':['synthetic']}
                self.mutate_output(change);result=self.run_review()
                self.assertFalse(result['shorts'][0]['publish']);self.assertEqual(result['shorts'][0]['review']['status'],status)
                if overall is None:self.assertNotIn('output_sha256',result['shorts'][0]['review'])

    def test_changed_source_fields_rejected(self):
        for key,value in [('title','altered'),('sha256','0'*64),('file','short-01.mp4'),('extra','injected')]:
            with self.subTest(key=key):
                before=self.path.read_bytes();self.mutate_output(lambda v,d:v['shorts'][0].update({key:value}))
                with self.assertRaises(ValueError):self.run_review()
                self.assertEqual(self.path.read_bytes(),before)

    def test_invalid_output_shapes(self):
        for records in ([],[{},{}],[None]):
            with self.subTest(records=records):
                before=self.path.read_bytes();self.mutate_output(lambda v,d:v.update(shorts=records))
                with self.assertRaises(ValueError):self.run_review()
                self.assertEqual(self.path.read_bytes(),before)

    def test_changed_original_during_review(self):
        self.mutate_output(lambda v,d:self.media.write_bytes(b'changed'))
        with self.assertRaises(ValueError):self.run_review()

    def test_changed_copy_during_review(self):
        self.mutate_output(lambda v,d:(Path(d)/r.FILE).write_bytes(b'changed'))
        with self.assertRaises(ValueError):self.run_review()

    def test_changed_manifest_during_review(self):
        self.mutate_output(lambda v,d:self.path.write_bytes(b'changed concurrently'))
        with self.assertRaises(ValueError):self.run_review()
        self.assertEqual(self.path.read_bytes(),b'changed concurrently')

    def test_malformed_status_rejected(self):
        self.mutate_output(lambda v,d:v['shorts'][0]['review'].update(status=''))
        with self.assertRaises(ValueError):self.run_review()

    def test_unjustified_publish_rejected(self):
        self.mutate_output(lambda v,d:v['shorts'][0]['review'].update(overall=8.5))
        with self.assertRaises(ValueError):self.run_review()

    def test_binding_negative_fields(self):
        good=self.run_review()
        for key,value in [('pilot','pilot-007'),('target_slot','2026-10-21T20:00:00Z'),('output_sha256','0'*64),('extra','unknown')]:
            bad=copy.deepcopy(good);bad['review_recovery'][key]=value
            with self.assertRaises(ValueError):r.binding(bad)
        for mutate in [lambda x:x.pop('review_recovery'),lambda x:x['shorts'][1].update(publish=True),
                       lambda x:x.update(source_pilot='pilot-007'),lambda x:x['review_recovery_execution'].update(github_run_id=True),
                       lambda x:x['review_recovery_execution'].update(reviewed_at='2026-10-21T12:00:00'),
                       lambda x:x['shorts'][0].pop('previous_review')]:
            bad=copy.deepcopy(good);mutate(bad)
            with self.assertRaises(ValueError):r.binding(bad)

    def test_pure_import_has_no_provider(self):
        code=f"import sys;sys.path.insert(0,{str(Path(r.__file__).parent)!r});import review_recovery;assert 'shorts_review' not in sys.modules;assert 'structure_mining' not in sys.modules"
        subprocess.run([sys.executable,'-I','-B','-c',code],check=True)


    def test_workflow_only_two_run_bodies_changed(self):
        workflow = Path(__file__).resolve().parents[2] / '.github/workflows/shorts-review.yml'
        text = workflow.read_text()
        old_list = '          python3 -I -c "import json,sys;[print(s[\'file\'],s[\'sha256\']) for s in json.load(open(sys.argv[1]))[\'shorts\']]" "$d/shorts.json" |\n'
        new_list = ('          if [ "$PILOT" = pilot-006 ]; then\n'
                    '            python3 -I -B migration/production/shorts_006_plan.py --http-recovery-list "migration/production/$PILOT"\n'
                    '          else\n' + '  ' + old_list.rstrip(' |\n') + '\n'
                    '          fi |\n')
        old_review = '        run: python3 -I -B migration/production/shorts_review.py "migration/production/$PILOT/shorts" 3\n'
        new_review = ('        run: |\n          set -euo pipefail\n          if [ "$PILOT" = pilot-006 ]; then\n'
                      '            python3 -I -B migration/production/shorts_006_plan.py --recover-http-review "migration/production/$PILOT"\n'
                      '          else\n            python3 -I -B migration/production/shorts_review.py "migration/production/$PILOT/shorts" 3\n          fi\n')
        self.assertEqual(text.count(new_list), 1)
        self.assertEqual(text.count(new_review), 1)
        download_prefix = '        run: |\n          set -euo pipefail\n          case "$PILOT"'
        original_prefix = '        run: |\n          case "$PILOT"'
        self.assertEqual(text.count(download_prefix), 1)
        baseline = text.replace(new_list, old_list).replace(new_review, old_review).replace(download_prefix, original_prefix)
        self.assertEqual(hashlib.sha256(baseline.encode()).hexdigest(),
                         'caf36ac8c64f23eebdf71fe0eb7e2418170b108f102eed532d1c20edc1bb892d')


if __name__=='__main__':unittest.main()
