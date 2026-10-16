"""Offline counterfactuals. No real key, HTTP, git checkpoint or model call."""
from datetime import datetime, timezone, timedelta
import base64
import copy
import shutil
import contextlib
import io
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, Mock
import urllib.error

import synthetic_files_av as s
import gemini_public_av as g
import durable_evidence_checkpoint as d
from observe_public_av import ExistingObserverLedger

NOW = datetime(2026,10,16,2,0,tzinfo=timezone.utc)
KEY = 'offline-test-key-not-a-secret-1234567890'
KEY_HASH = hashlib.sha256(KEY.encode()).hexdigest()
ROOT = Path(__file__).resolve().parents[2]
CAPTURE_RAW = (ROOT/s.CAPTURE).read_bytes()
PROMPT = (ROOT/s.PROMPT).read_bytes()
BASE_META = json.loads(CAPTURE_RAW)['raw_file_metadata']
META = dict(BASE_META,uri=s.FILE_URL)
BASE_POLICY = json.loads((ROOT/s.POLICY).read_bytes())
POLICY = dict(BASE_POLICY,key_sha256=KEY_HASH)
# These counterfactual NEW-call tests retain the byte-exact pre-run42 snapshot.
# Construct it only in memory; require the recorded historical whole-file hash.
# Never rewrite the real ledger or infer a fresh budget from COMPLETED rows.
CURRENT_SQL_RAW = (ROOT/d.SQL).read_text()
LITE_KEY = 'synthetic-av:7e431b2811680333a574d970c68b74d073421105b805234d7721be3af9fe04ba'
SQL_RAW = ''.join(line for line in CURRENT_SQL_RAW.splitlines(keepends=True)
    if not line.startswith('INSERT INTO "public_av_reservations" VALUES(\''+LITE_KEY+"',"))
assert hashlib.sha256(SQL_RAW.encode()).hexdigest() == 'ea495b34686a2e2ba22789d7c6aa6efc927d718203bb8518c2502ab11e5bc7f4', 'HISTORICAL_PRE_RUN42_FIXTURE_CHANGED'
PRIOR_KEY = 'synthetic-av:27ef45f42c98789a4a30b043669c2973bf3c1c8b7e45484f3e15ca99bafe9d27'
PRIOR_PATH = Path('migration/evidence/public-av-'+PRIOR_KEY.split(':')[1]+'.json')
PRIOR_RAW = (ROOT/PRIOR_PATH).read_bytes()
PRIOR_SHA256 = '8b8bf5e574a2ea0ef2a5532c9887d0a6239670c5a18a638b01a4f6c83571aac3'
RESPONSE = {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'Observed result, unreviewed.'}]}}],
            'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':12}}
ENV = {'GITHUB_REPOSITORY':'matheusmagah-cpu/heroverse-engine','HERO_REPOSITORY_PRIVATE':'true',
       'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1',
       'GITHUB_WORKFLOW_REF':'matheusmagah-cpu/heroverse-engine/.github/workflows/official-evidence.yml@refs/heads/main',
       'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'12345',
       'HERO_STAGE_SELECTION':json.dumps({'checkpoint_only':True,'av_synthetic_c01':True,'av_reference':False})}

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.oldcwd = Path.cwd();self.addCleanup(os.chdir,self.oldcwd)
        os.chdir(self.temp.name)
        Path('migration/evidence').mkdir(parents=True);Path('cloud-evidence').mkdir()
        d.SQL.write_text(SQL_RAW)
        PRIOR_PATH.write_bytes(PRIOR_RAW)
        d.CLAIM.write_text(json.dumps({'run_id':'12345'}))
        self.db = s.DB
        with sqlite3.connect(self.db) as c:c.executescript(SQL_RAW)
        self.initial = self.rows()
        self.key_binding = patch.object(s,'HISTORICAL_KEY_SHA256',KEY_HASH);self.key_binding.start();self.addCleanup(self.key_binding.stop)
        self.no_network = patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('NO_LIVE_NETWORK_ALLOWED'))
        self.no_network.start();self.addCleanup(self.no_network.stop)
        self.checkpoints=[]
        self.commits = patch.object(d,'commit',side_effect=lambda message:self.checkpoints.append(message))
        self.commits.start();self.addCleanup(self.commits.stop)
        self.ledger = ExistingObserverLedger(self.db,'12345')
        self.send = Mock(return_value=copy.deepcopy(RESPONSE))
    def rows(self):
        with sqlite3.connect(self.db) as c:return c.execute('SELECT * FROM public_av_reservations ORDER BY key').fetchall()
    def run_one(self, **kwargs):
        args=dict(api_key=KEY,policy=POLICY,reserve=self.ledger.reserve,persist=self.ledger.persist,
                  send=self.send,now=NOW,clock=lambda:NOW)
        args.update(kwargs)
        return s.analyze_synthetic_file(META,PROMPT,**args)
    def assert_no_effect(self):
        self.send.assert_not_called();self.assertEqual(self.rows(),self.initial);self.assertEqual(self.checkpoints,[])
    def test_exact_neutral_payload_static_full_six_seconds(self):
        p=s.build_request(META,PROMPT,NOW)
        self.assertEqual(set(p),{'contents','generationConfig'})
        parts=p['contents'][0]['parts'];self.assertEqual(len(parts),2)
        self.assertEqual(parts[0],{'fileData':{'fileUri':s.FILE_URL,'mimeType':'video/mp4'},
            'mediaProcessing':'STATIC','videoMetadata':{'fps':10,'startOffset':'0s','endOffset':'6s'}})
        self.assertEqual(parts[1],{'text':PROMPT.decode()});self.assertEqual(p['generationConfig'],s.GENERATION_CONFIG)
        for forbidden in ('operator-only','audio_late_500ms','500ms','gabarito','0.5','Today is','systemInstruction','tools','cachedContent'):
            self.assertNotIn(forbidden,json.dumps(p))
    def test_prompt_hash_exact(self):self.assertEqual(hashlib.sha256(PROMPT).hexdigest(),s.PROMPT_SHA256)
    def test_prompt_change_rejected(self):
        with self.assertRaises(PermissionError):s.analyze_synthetic_file(META,PROMPT+b' ',api_key=KEY,policy=POLICY,reserve=self.ledger.reserve,persist=self.ledger.persist,send=self.send,now=NOW)
        self.assert_no_effect()
    def test_day_run_file_uri_not_in_idempotency_identity(self):
        key,h,identity=s.request_identity(PROMPT)
        self.assertEqual(key,'synthetic-av:'+h)
        body=json.dumps(identity)
        for value in (s.FILE_NAME,s.FILE_URL,'2026-10-16','12345',BASE_POLICY['verified_at']):self.assertNotIn(value,body)
        self.assertEqual(s.request_identity(PROMPT),s.request_identity(PROMPT))
    def test_content_model_prompt_and_config_change_identity(self):
        baseline=s.request_identity(PROMPT)[0]
        for kw in ({'content_sha256':'a'*64},{'model':'other'},{'video_metadata':{'fps':1}}, {'generation_config':{'maxOutputTokens':2048}}):
            self.assertNotEqual(baseline,s.request_identity(PROMPT,**kw)[0])
        self.assertNotEqual(baseline,s.request_identity(PROMPT+b' ')[0])
    def test_current_policy_fixture_is_documentary_not_real_key_match(self):
        self.assertEqual(BASE_POLICY['key_binding_status'],'EXPECTED_HISTORICAL_FINGERPRINT_PENDING_RUNTIME_MATCH')
        with self.assertRaises(PermissionError):g.validate_free_policy(KEY,BASE_POLICY,NOW)
    def test_policy_counterfactuals_before_reserve(self):
        for k,v in [('project_id','other'),('model','gemini-3.6-flash'),('model','gemini-3.8-flash'),('tier','PAID'),('billing_enabled',True),
            ('input_price_usd',.01),('output_price_usd',.01),('verified_at','2026-10-14T01:35:25Z'),
            ('verified_at','2026-10-17T01:35:25Z'),('key_sha256','a'*64),('automatic_paid_fallback',True),
            ('runtime_key_match_required_before_remote_effect',False),('expires_after_hours',48)]:
            with self.subTest(k=k),self.assertRaises((PermissionError,ValueError,TypeError)):self.run_one(policy={**POLICY,k:v})
            self.assert_no_effect()
    def test_secret_mismatch_no_effect(self):
        with self.assertRaises(PermissionError):self.run_one(api_key=KEY+'changed')
        self.assert_no_effect()
    def test_metadata_counterfactuals_before_reserve(self):
        bads=[{'name':'files/other'},{'state':'PROCESSING'},{'mimeType':'audio/wav'}, {'sizeBytes':'19084'},
            {'videoMetadata':{'videoDuration':'5s'}},{'uri':'https://evil.invalid/file'},
            {'sha256Hash':base64.b64encode(('0'+s.CONTENT_SHA256[1:]).encode()).decode()}, {'expirationTime':'2099-01-01T00:00:00Z'}]
        for change in bads:
            with self.subTest(change=change),self.assertRaises((PermissionError,g.ProviderFailure)):
                s.analyze_synthetic_file({**META,**change},PROMPT,api_key=KEY,policy=POLICY,reserve=self.ledger.reserve,persist=self.ledger.persist,send=self.send,now=NOW)
            self.assert_no_effect()
    def test_observed_uri_required_capture_alone_cannot_generate(self):
        with self.assertRaises(PermissionError):s.build_request(BASE_META,PROMPT,NOW)
    def test_both_strict_hash_encodings_reconcile(self):
        for raw in (bytes.fromhex(s.CONTENT_SHA256),s.CONTENT_SHA256.encode()):
            meta={**META,'sha256Hash':base64.b64encode(raw).decode()}
            self.assertEqual(s.validate_metadata(meta,NOW)['source'],s.SOURCE)
    def test_expired_and_near_expiry_block(self):
        for now in [datetime(2026,10,18,1,24,tzinfo=timezone.utc),datetime(2026,10,19,tzinfo=timezone.utc)]:
            with self.assertRaises(PermissionError):s.validate_metadata(META,now)
    def test_actual_same_ledger_history_and_exact_six_second_reservation(self):
        def effect(payload,key,model):
            self.assertEqual(len(self.checkpoints),1)
            # Confirm checkpoint SQL already contains the durable debit before transport.
            with sqlite3.connect(':memory:') as c:
                c.executescript(d.SQL.read_text())
                self.assertEqual(c.execute("SELECT seconds,state FROM public_av_reservations WHERE key=?",(s.request_identity(PROMPT)[0],)).fetchone(),(6,'CLAIMED'))
            return RESPONSE
        self.send.side_effect=effect;r=self.run_one();self.assertEqual(self.send.call_count,1)
        self.assertEqual(r['status'],'SYNTHETIC_RESPONSE_AWAITING_REVIEW');self.assertEqual(r['review_status'],'NOT_REVIEWED')
        self.assertEqual(len(self.rows()),len(self.initial)+1);self.assertEqual([r for r in self.rows() if r[0]!=s.request_identity(PROMPT)[0]],self.initial)
        self.assertEqual(len(self.checkpoints),2)
        for k in s.FALSE_AUTHORITY:self.assertIs(r[k],False)
        self.assertNotIn(KEY,json.dumps(r));self.assertEqual(r['generate_content_calls'],1)
    def test_real_lite_price_proof_binds_unchanged_ui_and_exact_prior_receipt(self):
        evidence=BASE_POLICY['verification_evidence'];raw=(ROOT/evidence['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),evidence['sha256']);proof=json.loads(raw)
        self.assertEqual(proof['selected_model'],s.MODEL)
        pricing=proof['official_documentation']['pricing']
        self.assertEqual(pricing['model'],s.MODEL);self.assertEqual(pricing['input_price_usd'],0);self.assertEqual(pricing['output_price_usd'],0)
        ui=proof['project_observation_reused']
        self.assertEqual(hashlib.sha256((ROOT/ui['path']).read_bytes()).hexdigest(),ui['sha256'])
        self.assertEqual(BASE_POLICY['verified_at'],ui['observed_at_utc']);self.assertFalse(ui['freshness_rebased'])
        prior=proof['prior_attempt'];self.assertEqual(prior['path'],str(PRIOR_PATH));self.assertEqual(prior['sha256'],PRIOR_SHA256)
        config=proof['next_candidate_requirements']
        self.assertEqual(config['video_metadata'],s.VIDEO_METADATA);self.assertEqual(config['generation_config'],s.GENERATION_CONFIG)
        self.assertEqual(config['prompt_sha256'],s.PROMPT_SHA256);self.assertEqual(config['content_sha256'],s.CONTENT_SHA256)
    def test_model_selection_changes_only_model_identity_not_media_or_prompt(self):
        key,h,identity=s.request_identity(PROMPT)
        old_key,old_hash,old_identity=s.request_identity(PROMPT,model='gemini-3.8-flash')
        self.assertEqual(old_key,PRIOR_KEY);self.assertNotEqual(key,old_key)
        self.assertEqual(s.MODEL,'gemini-3.5-flash-lite')
        self.assertEqual(identity,{**old_identity,'model':s.MODEL})
        prior=json.loads(PRIOR_RAW)
        self.assertEqual(g.digest(s.build_request(META,PROMPT,NOW)),prior['wire_payload_sha256'])
    def test_real_503_prior_receipt_and_six_second_debit_are_preserved(self):
        self.assertEqual(hashlib.sha256(PRIOR_RAW).hexdigest(),PRIOR_SHA256)
        prior=json.loads(PRIOR_RAW)
        self.assertEqual(prior['failure_code'],'HTTP_503_UNAVAILABLE:HIGH_DEMAND')
        self.assertEqual(prior['generate_content_calls'],1)
        row=[r for r in self.initial if r[0]==PRIOR_KEY]
        self.assertEqual(len(row),1);self.assertEqual(row[0][2:5],('2026-10-16',6,'COMPLETED'))
        self.run_one()
        self.assertEqual([r for r in self.rows() if r[0]==PRIOR_KEY],row)
        self.assertEqual(PRIOR_PATH.read_bytes(),PRIOR_RAW)
        self.send.reset_mock();checkpoints=list(self.checkpoints);rows=self.rows()
        replay=self.ledger.reserve(PRIOR_KEY,prior['request_hash'],6,28800)
        self.assertEqual(replay['status'],'REPLAY');self.assertEqual(replay['receipt'],prior)
        self.send.assert_not_called();self.assertEqual(self.checkpoints,checkpoints);self.assertEqual(self.rows(),rows)
    def test_lite_503_is_terminal_without_fallback_or_prior_debit_replacement(self):
        self.send.side_effect=g.ProviderFailure('HTTP_503_UNAVAILABLE:HIGH_DEMAND')
        receipt=self.run_one();self.assertEqual(receipt['status'],'FAILED_NO_AUTOMATIC_RETRY')
        self.assertEqual(self.send.call_count,1);self.assertEqual(self.send.call_args.kwargs,{'model':'gemini-3.5-flash-lite'})
        self.assertEqual(receipt['failure_code'],'HTTP_503_UNAVAILABLE:HIGH_DEMAND')
        self.assertEqual(PRIOR_PATH.read_bytes(),PRIOR_RAW)
        self.assertEqual([r for r in self.rows() if r[0]!=receipt['key']],self.initial)
        self.send.reset_mock();self.assertEqual(self.run_one(),receipt);self.send.assert_not_called()
    def test_terminal_replay_has_no_new_call_or_debit(self):
        r=self.run_one();before=self.rows();self.send.reset_mock();count=len(self.checkpoints)
        self.assertEqual(self.run_one(),r);self.send.assert_not_called();self.assertEqual(self.rows(),before);self.assertEqual(len(self.checkpoints),count)
    def test_replay_next_day_same_identity(self):
        r=self.run_one();self.send.reset_mock()
        tomorrow=NOW+timedelta(days=1)
        policy={**POLICY,'verified_at':tomorrow.isoformat()}
        self.assertEqual(self.run_one(now=tomorrow,clock=lambda:tomorrow,policy=policy),r);self.send.assert_not_called()
    def test_quota_429_terminal_no_retry_fallback(self):
        self.send.side_effect=g.ProviderFailure('HTTP_429_RESOURCE_EXHAUSTED:QUOTA')
        r=self.run_one();self.assertEqual(r['status'],'FAILED_NO_AUTOMATIC_RETRY');self.assertEqual(self.send.call_count,1)
        self.send.reset_mock();self.assertEqual(self.run_one(),r);self.send.assert_not_called();self.assertEqual(len(self.rows()),len(self.initial)+1)
    def test_transport_exception_is_redacted_terminal(self):
        self.send.side_effect=RuntimeError(KEY);r=self.run_one();self.assertEqual(self.send.call_count,1)
        self.assertEqual(r['failure_code'],'SYNTHETIC_RESPONSE_OR_LOCAL_FAILURE');self.assertNotIn(KEY,json.dumps(r))
    def test_truncated_blocked_empty_tool_and_echo_are_not_success(self):
        for response in ({'candidates':[]}, {'candidates':[{'finishReason':'MAX_TOKENS'}]},
            {'candidates':[{'finishReason':'STOP','content':{'parts':[]}}]},
            {'candidates':[{'finishReason':'STOP','content':{'parts':[{'toolCall':{}}]}}]},
            {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':KEY}]}}]}):
            reserve=Mock(side_effect=lambda k,h,*a:{'status':'NEW','durable':True,'key':k,'request_hash':h})
            persist=Mock();self.send.return_value=response
            r=self.run_one(reserve=reserve,persist=persist)
            self.assertEqual(r['status'],'FAILED_NO_AUTOMATIC_RETRY');persist.assert_called_once();self.assertNotIn(KEY,json.dumps(r))
    def test_cap_enforced_in_original_ledger(self):
        today=datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.db) as c:c.execute('INSERT INTO public_av_reservations VALUES(?,?,?,?,?,?,?)',('test-cap','x',today,28795,'COMPLETED',None,None))
        before=self.rows()
        with self.assertRaises(PermissionError):self.run_one()
        self.send.assert_not_called();self.assertEqual(self.rows(),before)
    def test_unresolved_claim_any_day_blocks(self):
        with sqlite3.connect(self.db) as c:c.execute('INSERT INTO public_av_reservations VALUES(?,?,?,?,?,?,?)',('test-unresolved','x','2020-01-01',1,'CLAIMED',None,None))
        before=self.rows()
        with self.assertRaises(PermissionError):self.run_one()
        self.send.assert_not_called();self.assertEqual(self.rows(),before)
    def test_failed_reservation_checkpoint_prevents_call_and_stays_unresolved(self):
        with patch.object(d,'commit',side_effect=RuntimeError('checkpoint failure')):
            with self.assertRaises(RuntimeError):self.run_one()
        self.send.assert_not_called();self.assertEqual(len(self.rows()),len(self.initial)+1)
        with self.assertRaises(PermissionError):self.run_one()
        self.send.assert_not_called()
    def test_failed_persistence_never_reissues_effect(self):
        with self.assertRaises(RuntimeError):self.run_one(persist=Mock(side_effect=RuntimeError('persistence failure')))
        self.assertEqual(self.send.call_count,1);self.send.reset_mock()
        with self.assertRaises(PermissionError):self.run_one()
        self.send.assert_not_called()
    def test_missing_durable_claim_rejected(self):
        for claim in ({'status':'NEW','durable':False},{'status':'BLOCKED'}):
            reserve=lambda k,h,*a:{**claim,'key':k,'request_hash':h}
            with self.assertRaises(PermissionError):self.run_one(reserve=reserve)
            self.assert_no_effect()
    def test_receipt_tamper_prevents_replay(self):
        r=self.run_one();p=Path('migration/evidence')/('public-av-'+r['key'].split(':')[1]+'.json');p.write_bytes(p.read_bytes()+b' ')
        self.send.reset_mock()
        with self.assertRaises(PermissionError):self.run_one()
        self.send.assert_not_called()
    def test_freshness_rechecked_after_durable_checkpoint(self):
        r=self.run_one(clock=lambda:NOW+timedelta(days=1))
        self.assertEqual(r['status'],'FAILED_NO_AUTOMATIC_RETRY');self.assertEqual(r['generate_content_calls'],0);self.send.assert_not_called()
    def test_runtime_boundary_rejects_schedule_fork_retry_other_stage(self):
        s.validate_boundary(ENV)
        changes=[{'GITHUB_EVENT_NAME':'schedule'},{'GITHUB_RUN_ATTEMPT':'2'}, {'HERO_REPOSITORY_PRIVATE':'false'},
            {'GITHUB_REF':'refs/heads/other'},{'GITHUB_REPOSITORY':'another/repo'},
            {'HERO_STAGE_SELECTION':json.dumps({'checkpoint_only':False,'av_synthetic_c01':True})},
            {'HERO_STAGE_SELECTION':json.dumps({'checkpoint_only':True,'av_synthetic_c01':True,'av_reference':True})}]
        for change in changes:
            with self.assertRaises(PermissionError):s.validate_boundary({**ENV,**change})
    def test_finalize_unresolved_preserves_observer_claim(self):
        with sqlite3.connect(self.db) as c:c.execute('INSERT INTO public_av_reservations VALUES(?,?,?,?,?,?,?)',('unresolved','x','2026-10-16',6,'CLAIMED',None,None))
        with patch.dict(os.environ,ENV,clear=True),self.assertRaises(PermissionError):s.finalize_control()
        self.assertTrue(d.CLAIM.exists())
    def test_finalize_terminal_does_not_touch_observer_state(self):
        self.run_one();state=Path('migration/evidence/observer-state.json');state.write_text('unchanged')
        with patch.dict(os.environ,ENV,clear=True):s.finalize_control()
        self.assertFalse(d.CLAIM.exists());self.assertEqual(state.read_text(),'unchanged')
    def test_public_youtube_admission_guard_unchanged(self):
        with self.assertRaises(PermissionError):g.build_request(s.SOURCE)
    def test_original_ledger_missing_claim_refused(self):
        d.CLAIM.unlink()
        with self.assertRaises(PermissionError):ExistingObserverLedger(self.db,'12345')
    def test_transport_get_exact_uri_no_redirect_or_retry(self):
        fake=Mock();fake.__enter__=Mock(return_value=fake);fake.__exit__=Mock(return_value=False);fake.status=200
        fake.read.return_value=json.dumps(META).encode();opener=Mock();opener.open.return_value=fake
        with patch('urllib.request.build_opener',return_value=opener) as build:
            self.assertEqual(s.get_existing_metadata(KEY),META)
        req=opener.open.call_args.args[0];self.assertEqual(req.full_url,s.FILE_URL);self.assertEqual(req.method,'GET');self.assertIsNone(req.data)
        self.assertNotIn(KEY,req.full_url);self.assertEqual(opener.open.call_count,1)
    def test_metadata_get_failure_no_retry_or_error_text_leak(self):
        opener=Mock();opener.open.side_effect=urllib.error.HTTPError(s.FILE_URL,429,KEY,None,None)
        with patch('urllib.request.build_opener',return_value=opener),self.assertRaises(g.ProviderFailure) as caught:s.get_existing_metadata(KEY)
        self.assertEqual(str(caught.exception),'METADATA_HTTP_429');self.assertEqual(opener.open.call_count,1)
    def install_inputs(self):
        for rel in (s.CAPTURE,s.PROMPT,Path(BASE_POLICY['verification_evidence']['path'])):
            Path(rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,rel)
        s.POLICY.write_text(json.dumps(POLICY))
    def test_full_runtime_uses_same_ledger_and_one_get_one_generate(self):
        self.install_inputs();get=Mock(return_value=META)
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()) as logs:
            self.assertEqual(s.preflight(),0)
            self.assertEqual(s.run_control(metadata_get=get,send=self.send),0)
            self.assertEqual(s.run_control(metadata_get=get,send=self.send),0)
        self.assertEqual(get.call_count,1);self.assertEqual(self.send.call_count,1);self.assertEqual(len(self.rows()),len(self.initial)+1)
        self.assertNotIn(KEY,logs.getvalue())
        saved=json.loads(Path('migration/evidence/synthetic-c01-preflight-12345.json').read_text())
        self.assertEqual(saved['provider_returned_uri'],s.FILE_URL);self.assertEqual(saved['key_binding']['status'],'MATCH')
    def test_full_runtime_mismatch_never_gets_metadata_or_reserves(self):
        self.install_inputs();get=Mock()
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY+'wrong'},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(s.run_control(metadata_get=get,send=self.send),2)
        get.assert_not_called();self.assert_no_effect()
    def test_saved_capture_corruption_blocks_runtime(self):
        self.install_inputs();s.CAPTURE.write_bytes(CAPTURE_RAW+b' ');get=Mock()
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(s.run_control(metadata_get=get,send=self.send),2)
        get.assert_not_called();self.assert_no_effect()
    def test_previous_model_price_receipt_cannot_stand_in_for_lite_proof(self):
        self.install_inputs();policy=json.loads(s.POLICY.read_text())
        old=Path('migration/evidence/gemini-project-policy-observation-20261016.json')
        policy['verification_evidence']={'path':str(old),'sha256':hashlib.sha256((ROOT/old).read_bytes()).hexdigest()}
        s.POLICY.write_text(json.dumps(policy));get=Mock()
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(s.run_control(metadata_get=get,send=self.send),2)
        get.assert_not_called();self.assert_no_effect()
        self.assertEqual(json.loads(Path('cloud-evidence/synthetic-c01-preflight-failure.json').read_text())['failure_code'],'POLICY_EVIDENCE_PATH_REQUIRED')
    def test_documentary_policy_evidence_corruption_blocks_runtime(self):
        self.install_inputs();Path(BASE_POLICY['verification_evidence']['path']).write_text('{}');get=Mock()
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(s.run_control(metadata_get=get,send=self.send),2)
        get.assert_not_called();self.assert_no_effect()
    def test_missing_sql_never_bootstraps_another_ledger(self):
        self.install_inputs();d.SQL.unlink();get=Mock()
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(s.run_control(metadata_get=get,send=self.send),2)
        get.assert_not_called();self.assert_no_effect();self.assertFalse(d.SQL.exists())
    def test_historical_debit_change_blocks_runtime(self):
        self.install_inputs();d.SQL.write_text(SQL_RAW.replace("'2026-10-14',1178,", "'2026-10-14',1179,",1));get=Mock()
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(s.run_control(metadata_get=get,send=self.send),2)
        get.assert_not_called();self.assert_no_effect()
    def test_fresh_metadata_mismatch_and_get_failure_never_reserve_or_generate(self):
        self.install_inputs()
        for i,get in enumerate((Mock(return_value={**META,'uri':'https://evil.invalid'}),Mock(side_effect=g.ProviderFailure('METADATA_HTTP_429')))):
            with patch.dict(os.environ,{**ENV,'GITHUB_RUN_ID':'12345','HERO_GEMINI_API_KEY':KEY},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(s.run_control(metadata_get=get,send=self.send),2)
            get.assert_called_once();self.send.assert_not_called();self.assertEqual(self.rows(),self.initial)
            path=Path('migration/evidence/synthetic-c01-preflight-12345.json');failure=json.loads(path.read_text())
            self.assertEqual(failure['status'],'FAILED_BEFORE_RESERVATION_NO_AUTOMATIC_RETRY')
            self.assertEqual(failure['metadata_get_calls'],1);self.assertEqual(failure['generate_content_calls'],0)
            self.assertEqual(len(self.checkpoints),(i+1)*2);self.assertNotIn(KEY,path.read_text())
            # Each fixture represents an independent manual attempt, never an automatic retry.
            path.unlink()
    def test_metadata_attempt_is_durable_before_get(self):
        self.install_inputs()
        def get(key):
            path=Path('migration/evidence/synthetic-c01-preflight-12345.json')
            self.assertEqual(json.loads(path.read_text())['status'],'METADATA_GET_REQUESTED')
            self.assertEqual(len(self.checkpoints),1);self.assertEqual(self.rows(),self.initial)
            raise RuntimeError(KEY)
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()) as log:self.assertEqual(s.run_control(metadata_get=get,send=self.send),2)
        self.send.assert_not_called();body=Path('migration/evidence/synthetic-c01-preflight-12345.json').read_text()
        self.assertNotIn(KEY,body+log.getvalue());self.assertEqual(json.loads(body)['failure_code'],'LOCAL_OR_CHECKPOINT_FAILURE')
    def test_failed_metadata_attempt_checkpoint_prevents_even_get(self):
        self.install_inputs();get=Mock()
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY},clear=True),patch.object(s,'utcnow',return_value=NOW),patch.object(d,'commit',side_effect=RuntimeError('checkpoint failed')),self.assertRaises(RuntimeError):s.run_control(metadata_get=get,send=self.send)
        get.assert_not_called();self.send.assert_not_called();self.assertEqual(self.rows(),self.initial)
    def test_preflight_failure_local_receipt_is_redacted_and_preserved_by_finalize(self):
        self.install_inputs()
        with patch.dict(os.environ,{**ENV,'HERO_GEMINI_API_KEY':KEY+'wrong'},clear=True),patch.object(s,'utcnow',return_value=NOW),contextlib.redirect_stdout(io.StringIO()) as logs:
            self.assertEqual(s.preflight(),2)
            self.assertEqual(s.finalize_control(),0)
        local=Path('cloud-evidence/synthetic-c01-preflight-failure.json').read_bytes()
        self.assertEqual(Path('migration/evidence/synthetic-c01-preflight-failure-12345.json').read_bytes(),local)
        self.assertNotIn(KEY,local.decode()+logs.getvalue());r=json.loads(local)
        self.assertEqual(r['metadata_get_calls'],0);self.assertEqual(r['generate_content_calls'],0)
        self.assertFalse(d.CLAIM.exists())
    def test_workflow_preserves_cron_and_blocks_other_collection_for_control(self):
        text=(ROOT/'.github/workflows/official-evidence.yml').read_text()
        self.assertIn("- cron: '17 9 * * *'",text);self.assertIn('group: heroverse-official-evidence',text)
        self.assertIn("if: always() && steps.durable_claim.outcome == 'success' && !inputs.av_synthetic_c01",text)
        self.assertIn('if: inputs.av_synthetic_c01 && inputs.checkpoint_only',text)
        self.assertLess(text.index('synthetic_audio_control.py preflight'),text.index('durable_evidence_checkpoint.py claim'))
        self.assertNotIn('av_synthetic_c01\n        type: boolean\n        default: true',text)

if __name__=='__main__':unittest.main()
