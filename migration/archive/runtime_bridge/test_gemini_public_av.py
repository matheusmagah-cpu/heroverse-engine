import base64, copy, hashlib, io, json, unittest
import urllib.error
import urllib.parse
from unittest.mock import Mock, patch
import gemini_public_av as g
from datetime import datetime, timezone, timedelta
from gemini_public_av import analyze, build_request,validate_report,normalize_report

NOW = datetime(2026,10,14,10,45,tzinfo=timezone.utc)
SOURCE = {'video_id':'7GvhWbXDWHQ','duration_seconds':1178,'visibility':'PUBLIC'}
KEY = 'synthetic-test-key'
POLICY = {'project_id':'gen-lang-client-0909161074','model':'gemini-3.8-flash',
 'tier':'FREE','billing_enabled':False,'input_price_usd':0,'output_price_usd':0,
 'verified_at':NOW.isoformat(),'key_sha256':hashlib.sha256(KEY.encode()).hexdigest()}
REPORT = {'video_id':SOURCE['video_id'],'duration_seconds':1178,
 'audio_received':True,'visual_received':True,'coverage':'FULL',
 'segments':[{'start_seconds':0,'end_seconds':1178,'audio_summary':'Synthetic narration',
 'visual_observation':'Synthetic visual','relationship':'Synthetic pairing',
 'mechanism':'Synthetic mechanism','limitations':[]}],'limitations':['Synthetic fixture']}

class ManagerFixture:
    """Testing only: not deployed as a second ledger."""
    def __init__(self): self.claims={}; self.calls=0; self.saved=[]
    def reserve(self,key,h,seconds,cap):
        if key in self.claims:
            result=dict(self.claims[key])
            result['status']='REPLAY' if 'receipt' in result else 'BLOCKED'
            return result
        result={'status':'NEW','durable':True,'key':key,'request_hash':h}
        self.claims[key]=result; return result
    def persist(self,receipt):
        self.saved.append(receipt); self.claims[receipt['key']]['receipt']=receipt
    def send(self,payload,key):
        self.calls+=1
        return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(REPORT)}]}}]}

class Tests(unittest.TestCase):
    def setUp(self): self.m=ManagerFixture()
    def run_adapter(self,**changes):
        kw=dict(api_key=KEY,policy=POLICY,reserve=self.m.reserve,persist=self.m.persist,
                send=self.m.send,now=NOW); kw.update(changes)
        return analyze(SOURCE,**kw)
    def test_report_has_no_production_authority(self):
        r=self.run_adapter()
        self.assertEqual(r['status'],'AWAITING_AV_REVIEW')
        self.assertFalse(r['publication_authorized']); self.assertEqual(r['review_status'],'NOT_REVIEWED')
    def test_replay_has_zero_new_call(self):
        first=self.run_adapter(); self.assertEqual(self.run_adapter(),first)
        self.assertEqual(self.m.calls,1)
    def test_lost_checkpoint_blocks_repeat(self):
        def broken(r): raise OSError('synthetic disk failure')
        with self.assertRaises(OSError): self.run_adapter(persist=broken)
        with self.assertRaises(PermissionError): self.run_adapter()
        self.assertEqual(self.m.calls,1)
    def test_paid_stale_foreign_or_different_key_zero_calls(self):
        for change in [{'tier':'PAID'},{'billing_enabled':True},{'project_id':'other'},
                       {'verified_at':(NOW-timedelta(days=2)).isoformat()},{'key_sha256':'a'*64}]:
            with self.assertRaises(PermissionError): self.run_adapter(policy={**POLICY,**change})
        self.assertEqual(self.m.calls,0)
    def test_quota_blocked_zero_calls(self):
        def blocked(k,h,*args): return {'status':'BLOCKED','key':k,'request_hash':h}
        with self.assertRaises(PermissionError): self.run_adapter(reserve=blocked)
        self.assertEqual(self.m.calls,0)
    def test_audio_only_and_gapped_timeline_never_admitted(self):
        for change in [{'visual_received':False},{'video_id':'abcdefghijk'},
                       {'segments':[{**REPORT['segments'][0],'start_seconds':1}]}]:
            m=ManagerFixture()
            def send(p,k): return {'candidates':[{'finishReason':'STOP','content':{
                'parts':[{'text':json.dumps({**REPORT,**change})}]}}]}
            r=analyze(SOURCE,api_key=KEY,policy=POLICY,reserve=m.reserve,persist=m.persist,send=send,now=NOW)
            self.assertEqual(r['status'],'FAILED_NO_AUTOMATIC_RETRY')
    def test_secret_bearing_provider_error_is_not_exposed(self):
        def send(p,k): raise RuntimeError('secret='+k)
        r=self.run_adapter(send=send)
        self.assertNotIn(KEY,json.dumps(r)); self.assertEqual(len(self.m.saved),1)
    def test_truncated_response_rejected(self):
        r=self.run_adapter(send=lambda p,k:{'candidates':[{'finishReason':'MAX_TOKENS'}]})
        self.assertEqual(r['failure_code'],'PROVIDER_BLOCKED_OR_TRUNCATED')
    def test_private_media_rejected(self):
        with self.assertRaises(PermissionError): build_request({**SOURCE,'visibility':'PRIVATE'})
    def test_lossless_normalization_preserves_words_and_timestamps(self):
        original={**REPORT,'segments':[{**REPORT['segments'][0],
            'audio_speech':'exact original words','limitations':'exact caveat'}]}
        del original['segments'][0]['audio_summary']
        converted=normalize_report(original)
        self.assertEqual(converted['segments'][0]['audio_summary'],'exact original words')
        self.assertEqual(converted['segments'][0]['limitations'],['exact caveat'])
        self.assertEqual(converted['segments'][0]['start_seconds'],0)
        self.assertNotIn('audio_summary',original['segments'][0])
        validate_report(converted,SOURCE)
    def test_normalization_never_fills_missing_visual_modality(self):
        original={**REPORT,'visual_received':False}
        with self.assertRaises(PermissionError):validate_report(normalize_report(original),SOURCE)
    def test_window_receipt_does_not_claim_whole_video(self):
        report={**REPORT,'coverage':'FULL_WINDOW','window_start_seconds':240,
            'window_end_seconds':480,'segments':[{**REPORT['segments'][0],
                'start_seconds':240,'end_seconds':480}]}
        self.assertEqual(validate_report(report,SOURCE,window=(240,480)),report)
        with self.assertRaises(PermissionError):validate_report(report,SOURCE)
    def test_missing_window_interval_is_rejected(self):
        report={**REPORT,'coverage':'FULL_WINDOW','window_start_seconds':240,
            'window_end_seconds':480,'segments':[{**REPORT['segments'][0],
                'start_seconds':241,'end_seconds':480}]}
        with self.assertRaises(PermissionError):validate_report(report,SOURCE,window=(240,480))
    def test_video_clipping_preserves_source_identity_and_global_clock(self):
        p=build_request(SOURCE,today='2026-10-14',window=(240,480))
        m=p['contents'][0]['parts'][0]['videoMetadata']
        self.assertEqual(m['startOffset'],'240s');self.assertEqual(m['endOffset'],'480s')
        self.assertIn('1178',p['contents'][0]['parts'][1]['text'])
    def test_request_has_video_fps_and_no_search_or_fallback(self):
        payload=build_request(SOURCE,today='2026-10-14')
        self.assertEqual(payload['contents'][0]['parts'][0]['videoMetadata']['fps'],1)
        self.assertNotIn('tools',payload)

    def test_refinement_rejects_coarse_scene_summary(self):
        r={**REPORT,'coverage':'FULL_WINDOW','window_start_seconds':130,
            'window_end_seconds':270,'segments':[{**REPORT['segments'][0],
            'start_seconds':130,'end_seconds':270}]}
        with self.assertRaises(PermissionError):validate_report(r,SOURCE,window=(130,270),refinement=True)
    def test_refinement_replays_without_repeating_effect(self):
        r={**REPORT,'coverage':'FULL_WINDOW','window_start_seconds':130,
            'window_end_seconds':150,'segments':[{**REPORT['segments'][0],
            'start_seconds':130,'end_seconds':150}]}
        calls=[]
        def send(payload,key):
            calls.append(payload)
            return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(r)}]}}]}
        args=dict(api_key=KEY,policy=POLICY,reserve=self.m.reserve,persist=self.m.persist,
            send=send,now=NOW,window=(130,150),refinement=True)
        first=analyze(SOURCE,**args);second=analyze(SOURCE,**args)
        self.assertEqual(first,second);self.assertEqual(len(calls),1)
        self.assertEqual(first['sample_fps'],2)
        self.assertFalse(first['publication_authorized'])
    def test_refinement_preserves_existing_baseline_request(self):
        p=build_request(SOURCE,today='2026-10-14',window=(130,270))
        q=build_request(SOURCE,today='2026-10-14',window=(130,270),refinement=True)
        self.assertEqual(p['contents'][0]['parts'][0]['videoMetadata']['fps'],1)
        self.assertEqual(q['contents'][0]['parts'][0]['videoMetadata']['fps'],2)
        self.assertNotEqual(p,q)
        with self.assertRaises(PermissionError):build_request(SOURCE,refinement=True)

    def test_clipped_local_budget_preserves_full_source_identity_and_failed_debit(self):
        reservations=[]
        def reserve(key,h,seconds,cap):
            reservations.append((seconds,cap))
            return self.m.reserve(key,h,seconds,cap)
        receipt=self.run_adapter(reserve=reserve,window=(960,980),refinement=True)
        self.assertEqual(reservations,[(20,28800)])
        self.assertEqual(receipt['source']['duration_seconds'],1178)
        self.assertEqual(receipt['local_budget_seconds'],20)
        self.assertEqual(receipt['status'],'FAILED_NO_AUTOMATIC_RETRY')
        self.assertEqual(len(self.m.saved),1)
    def test_whole_video_local_budget_still_debits_whole_duration(self):
        reservations=[]
        def reserve(key,h,seconds,cap):
            reservations.append((seconds,cap))
            return self.m.reserve(key,h,seconds,cap)
        receipt=self.run_adapter(reserve=reserve)
        self.assertEqual(reservations,[(1178,28800)])
        self.assertFalse(receipt['publication_authorized'])

    def test_http400_retains_bounded_sanitized_message_and_field_violation(self):
        raw=json.dumps({'error':{'code':400,'status':'INVALID_ARGUMENT',
            'message':"Invalid value at 'generation_config.response_format.text.mime_type': application/json.",
            'details':[{'@type':'type.googleapis.com/google.rpc.BadRequest','fieldViolations':[
                {'field':'generation_config.response_format.text.mime_type','description':'Expected APPLICATION_JSON.'}]}]}}).encode()
        http=urllib.error.HTTPError('https://example.invalid/private',400,'unsafe reason',{},io.BytesIO(raw))
        opener=Mock();opener.open.side_effect=http
        with patch('urllib.request.build_opener',return_value=opener):
            with self.assertRaises(g.ProviderFailure) as caught:g.transport({'contents':[{'parts':[{}]}]},KEY)
        self.assertEqual(opener.open.call_count,1)
        error=caught.exception;self.assertEqual(error.code,'HTTP_400_INVALID_ARGUMENT')
        self.assertIn('generation_config.response_format.text.mime_type',error.diagnostic['message'])
        self.assertEqual(error.diagnostic['field_violations'][0]['description'],'Expected APPLICATION_JSON.')
        self.assertFalse(error.diagnostic['raw_body_retained'])
        self.assertNotIn('unsafe reason',json.dumps(error.diagnostic))
        self.assertLessEqual(len(g.canonical(error.diagnostic)),g.ERROR_DIAGNOSTIC_LIMIT)
    def test_error_diagnostic_redacts_key_encodings_base64_urls_and_unknown_metadata(self):
        key='offline-key+/?not-a-real-secret';encoded=base64.b64encode(key.encode()).decode()
        media=base64.b64encode(b'RIFF'+b'private synthetic media '*8).decode()
        url='https://user:password@example.invalid/path?access_token=do-not-retain'
        text=' '.join([key,urllib.parse.quote(key,safe=''),encoded,media,url,'token=shortsecret'])
        raw=json.dumps({'error':{'status':'INVALID_ARGUMENT','message':text,
            'unknown_metadata':{'secret':'never copied'},'headers':{'authorization':key},
            'details':[{'@type':'type.googleapis.com/google.rpc.BadRequest','fieldViolations':[
                {'field':key,'description':text,'raw':media}]}]}}).encode()
        diagnostic=g.sanitized_provider_error(raw,400,key);saved=json.dumps(diagnostic)
        for forbidden in (key,urllib.parse.quote(key,safe=''),encoded,media,url,'shortsecret','never copied','authorization','unknown_metadata'):
            self.assertNotIn(forbidden,saved)
        self.assertIn('REDACTED',saved)
    def test_error_diagnostic_empty_or_nonstring_key_does_not_disable_scrubbing(self):
        raw=json.dumps({'error':{'status':'INVALID_ARGUMENT','message':
            'Invalid enum; api_key=shortsecret https://example.invalid/?token=abc '+('A'*64)}}).encode()
        for key in ('',None,False,0):
            diagnostic=g.sanitized_provider_error(raw,400,key);saved=json.dumps(diagnostic)
            self.assertIn('Invalid enum',saved)
            for forbidden in ('shortsecret','https://','example.invalid','A'*64):self.assertNotIn(forbidden,saved)
    def test_nested_percent_escapes_and_quoted_public_enums(self):
        key='offline-key+/?not-a-real-secret'
        hidden=urllib.parse.quote(urllib.parse.quote(key,safe=''),safe='').lower()
        raw=json.dumps({'error':{'message':hidden+' "APPLICATION_JSON" "application/json" https:\\/\\/example.invalid/?secret=short'}}).encode()
        saved=json.dumps(g.sanitized_provider_error(raw,400,key))
        self.assertNotIn(key,saved);self.assertNotIn(hidden,saved);self.assertNotIn('example.invalid',saved)
        self.assertIn('APPLICATION_JSON',saved);self.assertIn('application/json',saved)
    def test_nonjson_truncated_or_malformed_error_never_retains_raw(self):
        for raw in (b'<html>secret=never</html>',b'{"error":',b'[]',b'{"error":true}',b'\xff',b'x'*(g.ERROR_BODY_LIMIT+1)):
            diagnostic=g.sanitized_provider_error(raw,400,KEY)
            self.assertFalse(diagnostic['raw_body_retained']);self.assertNotIn('message',diagnostic)
            self.assertNotIn('never',json.dumps(diagnostic))
        large=b'x'*(g.ERROR_BODY_LIMIT+10000)
        http=urllib.error.HTTPError('https://example.invalid',400,'unsafe',{},io.BytesIO(large))
        opener=Mock();opener.open.side_effect=http
        with patch('urllib.request.build_opener',return_value=opener),self.assertRaises(g.ProviderFailure) as caught:
            g.transport({'contents':[{'parts':[{}]}]},KEY)
        diagnostic=caught.exception.diagnostic
        self.assertEqual(diagnostic['body_bytes_read'],g.ERROR_BODY_LIMIT+1);self.assertTrue(diagnostic['body_truncated'])
    def test_diagnostic_bounds_unicode_and_field_violation_counts(self):
        body={'error':{'status':'INVALID_ARGUMENT','message':'á '*500,
            'details':[{'@type':'type.googleapis.com/google.rpc.BadRequest','fieldViolations':[
                {'field':'generation_config.'+'a.'*70,'description':'á '*100} for _ in range(6)]}]}}
        diagnostic=g.sanitized_provider_error(json.dumps(body,ensure_ascii=False).encode(),400,KEY)
        self.assertEqual(len(diagnostic['field_violations']),4)
        self.assertLessEqual(len(diagnostic['message'].encode()),768)
        self.assertLessEqual(len(g.canonical(diagnostic)),g.ERROR_DIAGNOSTIC_LIMIT)
        for item in diagnostic['field_violations']:
            self.assertLessEqual(len(item['field'].encode()),128);self.assertLessEqual(len(item['description'].encode()),384)
    def test_existing_error_codes_and_reason_tags_are_compatible(self):
        for code,status,message,expected in [(503,'UNAVAILABLE','High demand','HTTP_503_UNAVAILABLE:HIGH_DEMAND'),
                (429,'RESOURCE_EXHAUSTED','Quota exceeded','HTTP_429_RESOURCE_EXHAUSTED:QUOTA')]:
            raw=json.dumps({'error':{'status':status,'message':message}}).encode()
            http=urllib.error.HTTPError('https://example.invalid',code,'ignored',{},io.BytesIO(raw));opener=Mock();opener.open.side_effect=http
            with patch('urllib.request.build_opener',return_value=opener),self.assertRaises(g.ProviderFailure) as caught:
                g.transport({'contents':[{'parts':[{}]}]},KEY)
            self.assertEqual(caught.exception.code,expected);self.assertEqual(opener.open.call_count,1)

if __name__=='__main__': unittest.main()
