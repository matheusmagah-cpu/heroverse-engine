#!/usr/bin/env python3
"""Synthetic regression tests; no provider requests or private production data."""
import base64
import hashlib
from datetime import datetime, timezone, timedelta
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.find_spec('native_review_recovery')
if SPEC:
    import native_review_recovery as recovery
else:
    recovery = None


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(recovery, 'GET-only recovery and persistent readback are missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'receipt.json'
        self.i = {'plan': 'migration/production/bible/plans/test-short.json',
                  'sha256': 'a'*64, 'byte_size': '123', 'recover_submitted_run': '1234'}
        self.receipt = {'version': 'native-av-evidence-v1', 'run_id': '1234',
                        'plan': self.i['plan'], 'model': recovery.MODEL,
                        'output_sha256': 'a'*64, 'provider_sha256': 'a'*64,
                        'byte_size': 123, 'status': 'SUBMITTED', 'production_approved': False,
                        'interaction_id': 'synthetic_interaction', 'file_name': 'files/synthetic',
                        'file_uri': recovery.API+'/v1beta/files/synthetic',
                        'prompt_sha256': 'b'*64,
                        'coverage': {'video_sampling_fps': 4, 'native_audio': True, 'full_input': True}}
        recovery.save(self.path, self.receipt)

    def response(self, status, **extra):
        return json.dumps({'id': 'synthetic_interaction', 'model': recovery.MODEL,
                           'status': status, **extra}).encode()

    def readback(self, status, **extra):
        return recovery.record_readback(self.path, self.response(status, **extra), lambda r: None)

    def stored(self):
        return json.loads(self.path.read_text())

    def test_failure_is_preserved_not_lost_as_generic_pending(self):
        self.assertEqual(self.readback('failed', error={'code': 'synthetic_quota'}), 'PROVIDER_FAILED')
        r = self.stored()
        self.assertEqual(r['provider_response']['error']['code'], 'synthetic_quota')
        self.assertEqual(base64.b64decode(r['response_body_base64']), self.response('failed', error={'code': 'synthetic_quota'}))
        self.assertFalse(r['production_approved'])

    def test_each_non_success_terminal_state_is_explicit(self):
        for state in ('cancelled', 'incomplete', 'requires_action'):
            recovery.save(self.path, self.receipt)
            self.assertEqual(self.readback(state), 'PROVIDER_'+state.upper())
            self.assertFalse(self.stored()['publication_ready'])

    def test_pending_stays_resumable(self):
        self.assertEqual(self.readback('in_progress'), 'SUBMITTED')
        self.assertEqual(self.stored()['provider_status'], 'in_progress')

    def test_identity_mismatch_cannot_approve_and_retains_raw_body(self):
        raw = json.dumps({'id': 'wrong', 'model': recovery.MODEL, 'status': 'completed'}).encode()
        with self.assertRaisesRegex(recovery.Blocked, 'READBACK_IDENTITY_MISMATCH'):
            recovery.record_readback(self.path, raw, lambda r: None)
        self.assertEqual(base64.b64decode(self.stored()['response_body_base64']), raw)
        self.assertFalse(self.stored()['production_approved'])

    def test_malformed_outer_json_is_preserved(self):
        with self.assertRaisesRegex(recovery.Blocked, 'READBACK_JSON_INVALID'):
            recovery.record_readback(self.path, b'not-json', lambda r: None)
        self.assertEqual(base64.b64decode(self.stored()['response_body_base64']), b'not-json')

    def test_malformed_report_preserves_complete_unvalidated(self):
        with self.assertRaisesRegex(recovery.Blocked, 'REPORT_JSON_INVALID'):
            self.readback('completed', steps=[{'type':'model_output','content':[{'type':'text','text':'bad report'}]}])
        self.assertEqual(self.stored()['status'], 'COMPLETE_UNVALIDATED')
        self.assertEqual(self.stored()['response_text'], 'bad report')

    def test_report_validation_cannot_be_skipped(self):
        report = {'overall':9.8, 'scores':{'x':9.8}}
        raw=self.response('completed', steps=[{'type':'model_output','content':[{'type':'text','text':json.dumps(report)}]}])
        def reject(r): raise ValueError('synthetic invalid coverage')
        with self.assertRaisesRegex(recovery.Blocked, 'REPORT_VALIDATION_FAILED'):
            recovery.record_readback(self.path, raw, reject)
        self.assertEqual(self.stored()['status'], 'COMPLETE_UNVALIDATED')
        self.assertNotIn('owner_floor_met',self.stored())

    def test_valid_evidence_does_not_grant_publication(self):
        for overall, item, passes in [(9.5,9.5,True),(9.4,9.5,False),(9.6,6.9,False)]:
            recovery.save(self.path,self.receipt)
            report={'overall':overall,'scores':{k:item for k in recovery.RUBRIC}}
            self.assertEqual(self.readback('completed',steps=[{'type':'model_output','content':[{'type':'text','text':json.dumps(report)}]}]),'EVIDENCE_COMPLETE')
            self.assertEqual(self.stored()['owner_floor_met'],passes)
            self.assertFalse(self.stored()['publication_ready'])

    def source(self):
        run={'id':1234,'display_title':recovery.subject_title(self.i),'path':'.github/workflows/native-review.yml',
             'status':'completed','conclusion':'failure','run_attempt':1,'head_branch':'main'}
        steps=[{'name':name,'status':'completed','conclusion':'success'} for name in recovery.SOURCE_STEPS]
        return run,[{'name':'review','steps':steps}]

    def test_source_requires_same_master_and_successful_prior_submission(self):
        run,jobs=self.source()
        recovery.check_source(self.i,run,jobs)
        jobs[0]['steps'][-1]['conclusion']='skipped'
        with self.assertRaises(recovery.Blocked): recovery.check_source(self.i,run,jobs)
        run,jobs=self.source();run['display_title']='other master'
        with self.assertRaises(recovery.Blocked): recovery.check_source(self.i,run,jobs)

    def test_receipt_cannot_change_binding_or_inject_request_path(self):
        recovery.check_receipt(self.i,self.receipt)
        for field,value in [('run_id','5678'),('output_sha256','c'*64),('byte_size',456),
                            ('interaction_id','x/../../files'),('file_name','https://evil.test'),
                            ('production_approved',True),('status','FILE_READY')]:
            bad=dict(self.receipt);bad[field]=value
            with self.subTest(field=field), self.assertRaises(recovery.Blocked):
                recovery.check_receipt(self.i,bad)

    def test_real_cms_roundtrip_and_corruption_fail_closed(self):
        recovery.make_transport_key(self.root)
        raw=json.dumps(self.receipt).encode()
        cipher=subprocess.run(['openssl','cms','-encrypt','-binary','-aes-256-gcm','-outform','DER',str(self.root/'ingress.pem')],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
        self.assertEqual(recovery.decrypt_receipt(self.root,cipher),self.receipt)
        damaged=bytearray(cipher);damaged[-1]^=1
        with self.assertRaises(recovery.Blocked): recovery.decrypt_receipt(self.root,bytes(damaged))

    def test_poll_only_uses_get_and_never_replays_submission(self):
        calls=[]
        def get(url, key):
            calls.append(url)
            return {},self.response('failed',error={'code':'synthetic'})
        class Legacy:
            request=staticmethod(get)
            validate_report=staticmethod(lambda r: None)
        self.assertEqual(recovery.poll_saved(self.i,self.path,'fake-key',Legacy, attempts=1),'PROVIDER_FAILED')
        self.assertEqual(calls,[recovery.API+'/v1beta/interactions/synthetic_interaction'])

    def test_workflow_cannot_submit_upload_or_delete_in_recovery(self):
        text=(ROOT.parents[2]/'.github/workflows/native-review.yml').read_text()
        for name in ('Open one private resumable upload session',
                     'Await exact-byte upload and read back provider hash',
                     'Submit native audio and video review once',
                     'Delete provider media after completed review'):
            block=text.split('- name: '+name,1)[1].split('- name:',1)[0]
            self.assertIn("inputs.recover_submitted_run == ''",block)
        self.assertNotIn('schedule:',text)
        self.assertIn('contents: read',text)
        self.assertIn('actions: read',text)
        self.assertNotIn('contents: write',text)
        self.assertIn('native_review_recovery.py poll',text)
        self.assertIn('run-name: "native-review: plan=${{ inputs.plan }} sha256=${{ inputs.sha256 }}"',text)
        self.assertIn('path: ${{ runner.temp }}/native-review/ingress.pem',text)
        self.assertNotIn('path: ${{ runner.temp }}/native-review/ingress.key',text)

    def test_validation_reason_is_retained_privately(self):
        raw=self.response('completed',steps=[{'type':'model_output','content':[{'type':'text','text':'{}'}]}])
        def reject(r): raise ValueError('synthetic invalid coverage')
        with self.assertRaises(recovery.Blocked): recovery.record_readback(self.path,raw,reject)
        self.assertEqual(self.stored().get('validation_error_type'),'ValueError')
        self.assertEqual(self.stored().get('validation_error'),'synthetic invalid coverage')

    def test_receive_real_encrypted_receipt_discards_injected_report(self):
        recovery.make_transport_key(self.root)
        r=dict(self.receipt);r['prompt_sha256']=hashlib.sha256(b'synthetic prompt').hexdigest()
        r['report']={'overall':10};r['publication_ready']=True
        cipher=subprocess.run(['openssl','cms','-encrypt','-binary','-aes-256-gcm','-outform','DER',str(self.root/'ingress.pem')],input=json.dumps(r).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
        encoded=base64.b64encode(cipher)
        obj={'type':'file','encoding':'base64','size':len(encoded),'content':base64.b64encode(encoded).decode()}
        class Legacy:
            github_read=staticmethod(lambda path: obj)
            prompt=staticmethod(lambda: 'synthetic prompt')
        recovery.save(self.root/'recovery.json',{'source_run_id':'1234','current_run_id':'5678','plan':self.i['plan'],'sha256':self.i['sha256']})
        with patch.dict(os.environ,{'GITHUB_RUN_ID':'5678'}), patch.object(recovery,'check_lease'):
            recovery.receive(self.i,self.root,self.path,Legacy)
        self.assertNotIn('report',self.stored())
        self.assertFalse(self.stored()['publication_ready'])
        self.assertFalse((self.root/'ingress.key').exists())

    def test_expired_or_other_owner_lease_refuses(self):
        lease={'schema':'heroverse-executor-lease-v1','owner':'codex','run_id':'synthetic-lease','state':'active',
               'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()}
        def read(path):
            return {'object':{'sha':'fake'}} if '/git/ref/' in path else {'message':'HEROVERSE_EXECUTOR_LEASE_V1\n'+json.dumps(lease)}
        class Legacy: github_read=staticmethod(read)
        i=dict(self.i,lease_run_id='synthetic-lease')
        recovery.check_lease(i,Legacy)
        lease['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        with self.assertRaises(recovery.Blocked): recovery.check_lease(i,Legacy)
        lease['expires_at']=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
        lease['run_id']='another-lease'
        with self.assertRaises(recovery.Blocked): recovery.check_lease(i,Legacy)

    def test_completed_recovery_requires_original_input_and_file(self):
        r=dict(self.receipt);r['prompt_sha256']=hashlib.sha256(b'synthetic prompt').hexdigest()
        recovery.save(self.path,r)
        report={'overall':9.5,'scores':{k:9.5 for k in recovery.RUBRIC}}
        parts=[{'type':'video','uri':r['file_uri']},{'type':'text','text':'synthetic prompt'}]
        response={'id':r['interaction_id'],'model':recovery.MODEL,'status':'completed','steps':[
          {'type':'user_input','content':parts},{'type':'model_output','content':[{'type':'text','text':json.dumps(report)}]}]}
        f={'name':r['file_name'],'uri':r['file_uri'],'displayName':'review-master-'+'a'*64+'-1234','sha256Hash':'synthetic','sizeBytes':123}
        calls=[]
        def get(url,key):
            calls.append(url)
            return {},json.dumps(response if '/interactions/' in url else f).encode()
        class Legacy:
            request=staticmethod(get)
            validate_report=staticmethod(lambda report:None)
            provider_sha256=staticmethod(lambda digest:'a'*64)
        self.assertEqual(recovery.poll_saved(self.i,self.path,'fake',Legacy,attempts=1),'EVIDENCE_COMPLETE')
        self.assertEqual(len(calls),2)
        recovery.save(self.path,r);parts[0]['uri']='https://other.invalid/video'
        with self.assertRaises(recovery.Blocked): recovery.poll_saved(self.i,self.path,'fake',Legacy,attempts=1)
        self.assertEqual(self.stored()['status'],'COMPLETE_UNVALIDATED')


if __name__ == '__main__': unittest.main()
