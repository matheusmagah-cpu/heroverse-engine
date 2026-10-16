"""Focused offline AUDIO_ONLY integration. No actual key, HTTP, git or media logs."""
import base64
import contextlib
from datetime import datetime,timezone,timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

import synthetic_audio_control as a
import synthetic_files_av as av
import durable_evidence_checkpoint as d
from observe_public_av import ExistingObserverLedger

ROOT=Path(__file__).resolve().parents[2]
NOW=datetime(2026,10,16,2,40,tzinfo=timezone.utc)
KEY='offline-key-not-a-secret';KEY_HASH=hashlib.sha256(KEY.encode()).hexdigest()
POLICY=dict(json.loads((ROOT/av.POLICY).read_bytes()),key_sha256=KEY_HASH)
SQL_RAW=(ROOT/d.SQL).read_text()
WAV=(ROOT/a.WAV).read_bytes();PROMPT=(ROOT/a.PROMPT).read_bytes();PROOF=(ROOT/a.PROOF).read_bytes()
RESPONSE={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'Three short tones.'}]}}],
    'usageMetadata':{'promptTokenCount':240,'candidatesTokenCount':4,'totalTokenCount':244,
        'promptTokensDetails':[{'modality':'TEXT','tokenCount':48},{'modality':'AUDIO','tokenCount':192}]}}
ENV={'GITHUB_REPOSITORY':'matheusmagah-cpu/heroverse-engine','HERO_REPOSITORY_PRIVATE':'true',
    'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1',
    'GITHUB_WORKFLOW_REF':'matheusmagah-cpu/heroverse-engine/.github/workflows/official-evidence.yml@refs/heads/main',
    'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'12345','HERO_GEMINI_API_KEY':KEY,
    'HERO_STAGE_SELECTION':json.dumps({'checkpoint_only':True,'av_synthetic_c01':True})}


class Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        cwd=Path.cwd();self.addCleanup(os.chdir,cwd);os.chdir(temp.name)
        Path('migration/evidence').mkdir(parents=True);Path('cloud-evidence').mkdir()
        d.SQL.write_text(SQL_RAW);d.CLAIM.write_text('{"run_id":"12345"}')
        with sqlite3.connect(av.DB) as c:c.executescript(SQL_RAW)
        for h,_ in a.PRIOR:
            rel=Path('migration/evidence/public-av-'+h+'.json');rel.write_bytes((ROOT/rel).read_bytes())
        self.initial=self.rows();self.send=Mock(return_value=RESPONSE);self.commits=[]
        for p in [patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('NETWORK_FORBIDDEN')),
                  patch.object(d,'commit',side_effect=lambda m:self.commits.append(m)),
                  patch.object(av,'HISTORICAL_KEY_SHA256',KEY_HASH)]:p.start();self.addCleanup(p.stop)
        self.ledger=ExistingObserverLedger(av.DB,'12345')
    def rows(self):
        with sqlite3.connect(av.DB) as c:return c.execute('SELECT * FROM public_av_reservations ORDER BY key').fetchall()
    def run_one(self,**kwargs):
        args=dict(api_key=KEY,policy=POLICY,reserve=self.ledger.reserve,persist=self.ledger.persist,
            proof_sha256=hashlib.sha256(PROOF).hexdigest(),send=self.send,clock=lambda:NOW)
        args.update(kwargs);return a.analyze_audio(WAV,PROMPT,**args)
    def install_inputs(self):
        for rel in (av.CAPTURE,av.PROMPT,Path(POLICY['verification_evidence']['path']),a.PROMPT):
            Path(rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,rel)
        av.POLICY.write_text(json.dumps(POLICY));a.WAV.parent.mkdir();a.WAV.write_bytes(WAV);a.PROOF.write_bytes(PROOF)
    def assert_no_effect(self):
        self.assertEqual(self.send.call_count,0);self.assertEqual(self.rows(),self.initial);self.assertEqual(self.commits,[])
    def test_payload_only_exact_inline_wav_and_neutral_audio_prompt(self):
        payload=a.build_request(WAV,PROMPT);parts=payload['contents'][0]['parts']
        self.assertEqual(set(payload),{'contents','generationConfig'});self.assertEqual(len(parts),2)
        self.assertEqual(set(parts[0]),{'inlineData'});self.assertEqual(parts[0]['inlineData']['mimeType'],'audio/wav')
        self.assertEqual(hashlib.sha256(base64.b64decode(parts[0]['inlineData']['data'])).hexdigest(),a.WAV_SHA256)
        self.assertEqual(parts[1],{'text':PROMPT.decode()});self.assertEqual(payload['generationConfig'],a.GENERATION_CONFIG)
        for hint in ('3','1.5','3.5','5.5','bipes','simultaneamente','operator-only','gabarito'):
            self.assertFalse(hint in PROMPT.decode())
    def test_identity_binds_mode_media_model_prompt_config_without_run_or_date(self):
        key,h,ident=a.request_identity(PROMPT);self.assertEqual(key,'synthetic-audio:'+h)
        self.assertEqual(ident['source'],a.SOURCE)
        for change in (patch.object(a,'MODEL','other'),patch.object(a,'MODE','other'),
                patch.object(a,'SOURCE',{**a.SOURCE,'content_sha256':'a'*64}),
                patch.object(a,'GENERATION_CONFIG',{'candidateCount':1,'maxOutputTokens':512})):
            with change:self.assertNotEqual(a.request_identity(PROMPT)[0],key)
        self.assertNotEqual(a.request_identity(PROMPT+b' ')[0],key)
        for forbidden in ('files/qe6pn3aifbkw','2026-10-16','12345'):self.assertFalse(forbidden in json.dumps(ident))
    def test_real_wav_proof_preserves_48khz_track_and_only_zero_padding_cut(self):
        proof=json.loads(PROOF);self.assertEqual(a.validate_media(WAV,PROMPT),PROMPT.decode())
        self.assertEqual(proof['source']['decoded_sample_count'],288768)
        self.assertEqual(proof['source']['removed_tail_samples'],768);self.assertTrue(proof['source']['removed_tail_exactly_zero'])
        self.assertEqual(proof['output']['sample_count'],288000);self.assertEqual(proof['output']['sample_rate'],48000)
        self.assertFalse(proof['conversion']['resampled']);self.assertEqual(proof['conversion']['clipped_samples'],0)
        self.assertLessEqual(proof['conversion']['max_absolute_quantization_error'],1/65536)
        self.assertTrue(proof['timing']['intervals_exactly_preserved'])
    def test_source_hash_rejected_before_decoder_or_builder_effect(self):
        sys.path.insert(0,str(ROOT/'migration/diagnostics/synthetic-audio-c01'))
        import build_audio as b
        fake=Path('wrong.mp4');fake.write_bytes(b'not-c01')
        with patch.object(b,'run') as call,self.assertRaises(ValueError):b.decode_source(fake)
        self.assertEqual(call.call_count,0)
        with self.assertRaises(ValueError):b.canonical_wav(b'')
    def test_one_call_checkpoint_before_send_preserves_all_old_rows_and_receipts(self):
        def effect(payload,key,model):
            with sqlite3.connect(':memory:') as c:
                c.executescript(d.SQL.read_text());row=c.execute('SELECT seconds,state FROM public_av_reservations WHERE key=?',(a.request_identity(PROMPT)[0],)).fetchone()
            self.assertEqual(row,(6,'CLAIMED'));self.assertEqual(len(self.commits),1)
            self.assertEqual(model,'gemini-3.5-flash-lite');return RESPONSE
        self.send.side_effect=effect;receipt=self.run_one();self.assertEqual(self.send.call_count,1)
        self.assertEqual(receipt['status'],'SYNTHETIC_AUDIO_RESPONSE_AWAITING_REVIEW');self.assertEqual(receipt['reported_audio_input_tokens'],192)
        self.assertEqual(receipt['review_status'],'NOT_REVIEWED');self.assertEqual(receipt['precision_verdict'],'NOT_ADJUDICATED')
        self.assertEqual([r for r in self.rows() if r[0]!=receipt['key']],self.initial)
        for h,sha in a.PRIOR:self.assertEqual(hashlib.sha256(Path('migration/evidence/public-av-'+h+'.json').read_bytes()).hexdigest(),sha)
        for k in av.FALSE_AUTHORITY:self.assertFalse(receipt[k])
        self.assertFalse(base64.b64encode(WAV[:48]).decode() in json.dumps(receipt));self.assertEqual(len(self.commits),2)
    def test_missing_audio_token_details_stays_inconclusive_not_proof_of_absence(self):
        self.send.return_value={**RESPONSE,'usageMetadata':{'promptTokensDetails':[{'modality':'VIDEO','tokenCount':10}]}}
        receipt=self.run_one();self.assertEqual(receipt['status'],'SYNTHETIC_AUDIO_RESPONSE_AWAITING_REVIEW')
        self.assertIsNone(receipt['reported_audio_input_tokens']);self.assertEqual(receipt['audio_token_evidence'],'NOT_REPORTED_OR_ZERO_INCONCLUSIVE')
    def test_runtime_and_terminal_replay_without_get_new_debit_or_media_logs(self):
        self.install_inputs()
        with patch.dict(os.environ,ENV,clear=True),patch.object(av,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(a.preflight(),0)
            # analyze_audio default clock remains real UTC but still within current policy.
            self.assertEqual(a.run_control(send=self.send),0);rows=self.rows();commits=list(self.commits)
            self.assertEqual(a.run_control(send=self.send),0)
        self.assertEqual(self.send.call_count,1);self.assertEqual(self.rows(),rows);self.assertEqual(self.commits,commits)
        self.assertFalse(KEY in output.getvalue());self.assertFalse(base64.b64encode(WAV[:48]).decode() in output.getvalue())
    def test_wrong_policy_or_key_cannot_reserve(self):
        for changes in ({'key_sha256':'a'*64},{'model':'gemini-3.8-flash'},{'tier':'PAID'},
                        {'verified_at':'2026-10-14T01:35:25Z'},{'output_price_usd':.01}):
            with self.assertRaises(PermissionError):self.run_one(policy={**POLICY,**changes})
            self.assert_no_effect()
    def test_wav_prompt_and_proof_mismatch_rejected_before_calls(self):
        with self.assertRaises(PermissionError):a.validate_media(WAV+b' ',PROMPT)
        with self.assertRaises(PermissionError):a.validate_media(WAV,PROMPT+b' ')
        self.install_inputs();a.PROOF.write_text('{}')
        with patch.dict(os.environ,ENV,clear=True),patch.object(av,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(a.preflight(),2)
        self.assert_no_effect()
    def test_prior_lite_receipt_or_debit_cannot_be_replaced(self):
        self.install_inputs();h,sha=a.PRIOR[-1];path=Path('migration/evidence/public-av-'+h+'.json');path.write_bytes(path.read_bytes()+b' ')
        with patch.dict(os.environ,ENV,clear=True),patch.object(av,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(a.preflight(),2)
        self.assert_no_effect()
    def test_reservation_checkpoint_failure_never_sends(self):
        with patch.object(d,'commit',side_effect=RuntimeError('OFFLINE_CHECKPOINT_FAILURE')):
            with self.assertRaises(RuntimeError):self.run_one()
        self.assertEqual(self.send.call_count,0)
        with self.assertRaises(PermissionError):self.run_one()
        self.assertEqual(self.send.call_count,0)
    def test_503_terminal_replay_and_no_fallback(self):
        self.send.side_effect=a.ProviderFailure('HTTP_503_UNAVAILABLE:HIGH_DEMAND')
        first=self.run_one();self.assertEqual(self.run_one(),first);self.assertEqual(self.send.call_count,1)
        self.assertEqual(first['status'],'FAILED_NO_AUTOMATIC_RETRY');self.assertEqual(first['generate_content_calls'],1)
        self.assertFalse(first['automatic_retry'])
    def test_429_is_one_terminal_call(self):
        self.send.side_effect=a.ProviderFailure('HTTP_429_RESOURCE_EXHAUSTED:QUOTA')
        receipt=self.run_one();self.assertEqual(self.send.call_count,1)
        self.assertEqual(receipt['failure_code'],'HTTP_429_RESOURCE_EXHAUSTED:QUOTA')
    def test_empty_tool_media_credential_and_media_echo_cannot_be_success_or_leak(self):
        prefix=base64.b64encode(WAV).decode()[:64]
        for parts in ([],[{'toolCall':{}}],[{'inlineData':{'mimeType':'audio/wav','data':'not-media'}}],
                      [{'text':KEY}],[{'text':prefix}]):
            persist=Mock();reserve=lambda k,h,*args:{'status':'NEW','durable':True,'key':k,'request_hash':h}
            self.send.return_value={'candidates':[{'finishReason':'STOP','content':{'parts':parts}}]}
            receipt=self.run_one(reserve=reserve,persist=persist)
            self.assertEqual(receipt['status'],'FAILED_NO_AUTOMATIC_RETRY');self.assertEqual(persist.call_count,1)
            self.assertFalse(KEY in json.dumps(receipt));self.assertFalse(prefix in json.dumps(receipt))
            self.assertFalse('inlineData' in json.dumps(receipt))
    def test_policy_freshness_rechecked_after_reservation(self):
        clock=Mock(side_effect=[NOW,NOW+timedelta(days=1),NOW+timedelta(days=1)])
        receipt=self.run_one(clock=clock);self.assertEqual(receipt['generate_content_calls'],0);self.assertEqual(self.send.call_count,0)
        self.assertEqual(receipt['status'],'FAILED_NO_AUTOMATIC_RETRY')
    def test_workflow_remains_manual_same_ledger_and_media_excluded_from_artifact(self):
        text=(ROOT/'.github/workflows/official-evidence.yml').read_text()
        self.assertIn("- cron: '17 9 * * *'",text);self.assertIn('group: heroverse-official-evidence',text)
        self.assertIn('AUDIO_ONLY c01 diagnostic once',text)
        self.assertLess(text.index('build_audio.py synthetic-audio-control-output'),text.index('synthetic_audio_control.py preflight'))
        self.assertLess(text.index('synthetic_audio_control.py preflight'),text.index('durable_evidence_checkpoint.py claim'))
        artifact=text.split('      - name: Preserve evidence and quota continuation')[1]
        self.assertIn('synthetic-audio-control-output/proof.json',artifact)
        self.assertFalse('control.wav' in artifact);self.assertFalse('source-build' in artifact)
        self.assertIn('if: inputs.av_synthetic_c01 && inputs.checkpoint_only',text)

if __name__=='__main__':unittest.main()
