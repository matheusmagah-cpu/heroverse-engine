"""Focused offline AUDIO_ONLY integration. No actual key, HTTP, git or media logs."""
import base64
import copy
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
# Historical pre-enum-fix counterfactual, reconstructed IN MEMORY only.
# Later diagnostic receipts must not turn NEW-call tests into provider replays.
# Preserve the four original receipts; whole-file hash pins all remaining rows.
CURRENT_SQL_RAW=(ROOT/d.SQL).read_text()
ORIGINAL_AUDIO_KEY='synthetic-audio:7fe5d21cea9ccc07ac4d064ef371351b428b9d0ee4fc9ff617985d6de09f5a7a'
REJECTED_AUDIO_KEY='synthetic-audio:bf7925b517b92159cf196ad25f71e98bec81f8e695c47bf9b9098b02ed80b41a'
SQL_RAW=''.join(line for line in CURRENT_SQL_RAW.splitlines(keepends=True)
    if not line.startswith('INSERT INTO "public_av_reservations" VALUES(\'synthetic-audio:')
    or any(line.startswith('INSERT INTO "public_av_reservations" VALUES(\''+key+"',")
        for key in (ORIGINAL_AUDIO_KEY,REJECTED_AUDIO_KEY)))
assert hashlib.sha256(SQL_RAW.encode()).hexdigest()=='18b10b0b021a56572b951a20da16d7fff88c5d5c50613278e0c92c4c12dd1e76', 'HISTORICAL_PRE_ENUM_FIXTURE_CHANGED'
WAV=(ROOT/a.WAV).read_bytes();PROMPT=(ROOT/a.PROMPT).read_bytes();PROOF=(ROOT/a.PROOF).read_bytes()
REPORT={'status':'complete','count':1,'events':[{'label':'tone','start_seconds':2.0,'end_seconds':2.1}], 'uncertainty':None}
RESPONSE={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(REPORT)}]}}],
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
        for prior_key,_ in a.PRIOR:
            h=prior_key.split(':',1)[1]
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
        for prior_key,sha in a.PRIOR:
            h=prior_key.split(':',1)[1]
            self.assertEqual(hashlib.sha256(Path('migration/evidence/public-av-'+h+'.json').read_bytes()).hexdigest(),sha)
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
        self.install_inputs();prior_key,sha=a.PRIOR[-1];h=prior_key.split(':',1)[1];path=Path('migration/evidence/public-av-'+h+'.json');path.write_bytes(path.read_bytes()+b' ')
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

    def test_contract_is_only_wire_change_and_changes_stable_identity(self):
        old_key='synthetic-audio:7fe5d21cea9ccc07ac4d064ef371351b428b9d0ee4fc9ff617985d6de09f5a7a'
        original=json.loads((ROOT/('migration/evidence/public-av-'+old_key.split(':')[1]+'.json')).read_text())
        payload=a.build_request(WAV,PROMPT)
        self.assertNotEqual(a.request_identity(PROMPT)[0],old_key)
        self.assertEqual(set(payload['generationConfig']),{'candidateCount','maxOutputTokens','responseFormat'})
        self.assertEqual(payload['generationConfig']['responseFormat']['text']['mimeType'],'APPLICATION_JSON')
        self.assertEqual(payload['generationConfig']['responseFormat']['text']['schema'],a.RESPONSE_SCHEMA)
        del payload['generationConfig']['responseFormat']
        self.assertEqual(a.digest(payload),original['wire_payload_sha256'])
        current=a.request_identity(PROMPT)[2];current['generation_config'].pop('responseFormat')
        self.assertEqual(current,original['request_identity'])
        self.assertEqual(len(PROMPT),227)
        for forbidden in ('1.5','3.501','5.501','gabarito','três','three'):
            self.assertNotIn(forbidden,json.dumps(a.RESPONSE_SCHEMA,ensure_ascii=False))
    def test_schema_nested_mutation_does_not_change_frozen_config(self):
        before=copy.deepcopy(a.GENERATION_CONFIG)
        payload=a.build_request(WAV,PROMPT)
        payload['generationConfig']['responseFormat']['text']['schema']['required'].clear()
        identity=a.request_identity(PROMPT)[2]
        identity['generation_config']['responseFormat']['text']['schema']['required'].clear()
        self.assertEqual(a.GENERATION_CONFIG,before)
    def test_real_current_fixture_preserves_four_receipts_and_twenty_four_seconds(self):
        a.validate_prior_results()
        rows=[r for r in self.initial if r[2]=='2026-10-16']
        self.assertEqual(len(rows),4);self.assertEqual(sum(r[3] for r in rows),24)
        self.assertEqual(len(a.PRIOR),4)
        self.run_one()
        self.assertEqual([r for r in self.rows() if r[0] in dict(a.PRIOR)],rows)
        a.validate_prior_results()
    def test_current_repository_ledger_retains_all_four_real_debits(self):
        with sqlite3.connect(':memory:') as connection:
            connection.executescript(CURRENT_SQL_RAW)
            current=connection.execute('SELECT * FROM public_av_reservations ORDER BY key').fetchall()
        self.assertEqual([row for row in current if row[0] in dict(a.PRIOR)],
            [row for row in self.initial if row[0] in dict(a.PRIOR)])
        self.assertGreaterEqual(sum(row[3] for row in current if row[2]=='2026-10-16'),24)
        before=(ROOT/d.SQL).read_bytes();self.run_one()
        self.assertEqual((ROOT/d.SQL).read_bytes(),before)
    def test_complete_shape_is_not_perceptual_success(self):
        # Deliberately wrong synthetic answer passes shape only, not accuracy.
        receipt=self.run_one()
        self.assertEqual(receipt['response_contract_status'],'COMPLETE_UNREVIEWED')
        self.assertEqual(receipt['structured_response'],REPORT)
        self.assertEqual(receipt['precision_verdict'],'NOT_ADJUDICATED')
        self.assertEqual(receipt['review_status'],'NOT_REVIEWED')
        for key in av.FALSE_AUTHORITY:self.assertFalse(receipt[key])
    def test_unknown_and_partial_are_abstentions_never_zero_or_success(self):
        for report in ({'status':'unknown','count':None,'events':[],'uncertainty':'Cannot determine.'},
                       {'status':'partial','count':None,'events':[{'label':None,'start_seconds':None,'end_seconds':None}],
                        'uncertainty':'Cannot identify or time the event.'}):
            parsed,status=a.validate_structured_output(json.dumps(report))
            self.assertEqual(parsed,report);self.assertIsNone(parsed['count']);self.assertEqual(status,'ABSTAINED')
        report={'status':'partial','count':1,'events':copy.deepcopy(REPORT['events']),'uncertainty':'Unsure.'}
        self.send.return_value={**RESPONSE,'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(report)}]}}]}
        receipt=self.run_one();self.assertEqual(receipt['response_contract_status'],'ABSTAINED')
        self.assertEqual(receipt['precision_verdict'],'NOT_ADJUDICATED')
    def test_unknown_end_allowed_but_must_be_disclosed(self):
        report=copy.deepcopy(REPORT);report['events'][0]['end_seconds']=None
        with self.assertRaises(PermissionError):a.validate_structured_output(json.dumps(report))
        report['uncertainty']='End is unknown.'
        self.assertEqual(a.validate_structured_output(json.dumps(report)),(report,'COMPLETE_UNREVIEWED'))
    def test_non_json_duplicate_truncated_and_nonfinite_are_rejected(self):
        literal=json.dumps(REPORT)
        malformed=['caption only',literal+' trailing',literal[:-1],
            literal.replace('"status": "complete"','"status":"complete","status":"complete"'),
            literal.replace('"label": "tone"','"label":"tone","label":"tone"'),
            literal.replace('2.0','NaN'),literal.replace('2.0','Infinity'),
            literal.replace('2.0','-Infinity'),literal.replace('2.0','1e999')]
        for text in malformed:
            with self.subTest(text=text),self.assertRaises(PermissionError):a.validate_structured_output(text)
    def test_missing_fields_types_extras_null_and_incoherence_are_rejected(self):
        bads=[[],None,True]
        for key in REPORT:
            v=copy.deepcopy(REPORT);del v[key];bads.append(v)
        for key in REPORT['events'][0]:
            v=copy.deepcopy(REPORT);del v['events'][0][key];bads.append(v)
        for change in ({'extra':True},{'status':[]},{'status':'other'},
                {'count':True},{'count':1.0},{'count':'1'},{'count':-1},{'count':None},{'count':2},
                {'events':None},{'events':{}},{'events':[]},{'uncertainty':[]},{'uncertainty':''}):
            bads.append({**copy.deepcopy(REPORT),**change})
        for change in ({'extra':True},{'label':None},{'label':''},{'label':False},
                {'start_seconds':None},{'start_seconds':True},{'start_seconds':'2'},
                {'start_seconds':-0.1},{'start_seconds':6.01},{'start_seconds':10**400},
                {'end_seconds':False},{'end_seconds':1.9},{'end_seconds':6.01}):
            v=copy.deepcopy(REPORT);v['events'][0].update(change);bads.append(v)
        v=copy.deepcopy(REPORT);v['count']=2;v['events'].append({'label':'tone','start_seconds':1,'end_seconds':1.1});bads.append(v)
        bads += [{**copy.deepcopy(REPORT),'status':'unknown'},
                 {**copy.deepcopy(REPORT),'status':'partial','count':0,'uncertainty':'Unsure.'}]
        for report in bads:
            with self.subTest(report=report),self.assertRaises(PermissionError):a.validate_structured_output(json.dumps(report))
    def test_old_caption_is_preserved_as_invalid_contract_not_precision_failure(self):
        text='O som de bipe de chamada de telefone está presente.\n'
        self.send.return_value={**RESPONSE,'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':text}]}}]}
        receipt=self.run_one()
        self.assertEqual(receipt['status'],'FAILED_NO_AUTOMATIC_RETRY')
        self.assertEqual(receipt['response_contract_status'],'INVALID')
        self.assertEqual(receipt['failure_code'],'STRUCTURED_JSON_REQUIRED')
        self.assertEqual(receipt['evaluator_response'],text)
        self.assertEqual(receipt['provider_response'],self.send.return_value)
        self.assertEqual(receipt['precision_verdict'],'NOT_ADJUDICATED')
        self.assertEqual(self.run_one(),receipt);self.assertEqual(self.send.call_count,1)
    def test_numerically_well_formed_duplicates_remain_unreviewed(self):
        report=copy.deepcopy(REPORT);report['events']*=3;report['count']=3
        self.assertEqual(a.validate_structured_output(json.dumps(report))[1],'COMPLETE_UNREVIEWED')
        # Technical shape must not certify these duplicated onsets as accurate.
        self.send.return_value={**RESPONSE,'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(report)}]}}]}
        receipt=self.run_one();self.assertEqual(receipt['precision_verdict'],'NOT_ADJUDICATED')
        self.assertFalse(receipt['quality_authorized'])

    def test_output_enum_matches_discovery_and_is_only_change_from_rejected_payload(self):
        source=ROOT/'migration/diagnostics/synthetic-audio-c01/gemini-v1beta-text-response-format-20261016.json'
        evidence=json.loads(source.read_text())
        # Exact discovery excerpt is verified independently; no tutorial MIME literal.
        fragment=evidence['relevant_fragment']
        self.assertEqual(a.digest(fragment),evidence['fragment_canonical_sha256'])
        enum=fragment['TextResponseFormat.properties.mimeType']['enum']
        self.assertIn('APPLICATION_JSON',enum);self.assertNotIn('application/json',enum)
        payload=a.build_request(WAV,PROMPT)
        self.assertEqual(payload['generationConfig']['responseFormat']['text']['mimeType'],'APPLICATION_JSON')
        self.assertEqual(payload['contents'][0]['parts'][0]['inlineData']['mimeType'],'audio/wav')
        rejected=json.loads((ROOT/'migration/evidence/public-av-bf7925b517b92159cf196ad25f71e98bec81f8e695c47bf9b9098b02ed80b41a.json').read_text())
        self.assertNotEqual(a.request_identity(PROMPT)[0],rejected['key'])
        payload['generationConfig']['responseFormat']['text']['mimeType']='application/json'
        self.assertEqual(a.digest(payload),rejected['wire_payload_sha256'])
        identity=a.request_identity(PROMPT)[2]
        identity['generation_config']['responseFormat']['text']['mimeType']='application/json'
        self.assertEqual(identity,rejected['request_identity'])
    def test_error_diagnostic_persists_and_replays_without_new_call(self):
        from gemini_public_av import sanitized_provider_error
        raw=json.dumps({'error':{'status':'INVALID_ARGUMENT','message':'Invalid value at generation_config.response_format.text.mime_type; '+KEY}}).encode()
        diagnostic=sanitized_provider_error(raw,400,KEY)
        self.send.side_effect=a.ProviderFailure('HTTP_400_INVALID_ARGUMENT',diagnostic)
        first=self.run_one();self.assertEqual(first['provider_error'],diagnostic)
        self.assertNotIn(KEY,json.dumps(first));self.assertEqual(first['response_contract_status'],'NOT_EVALUATED')
        self.assertEqual(first['precision_verdict'],'NOT_ADJUDICATED')
        self.assertEqual(self.run_one(),first);self.assertEqual(self.send.call_count,1)
        a.validate_prior_results()

if __name__=='__main__':unittest.main()
