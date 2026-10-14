import copy, hashlib, json, unittest
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

if __name__=='__main__': unittest.main()
