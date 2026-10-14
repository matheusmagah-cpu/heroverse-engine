import json
import hashlib
from datetime import datetime,timezone
import unittest
from observe_market_av import validate_plan,execute
from gemini_public_av import build_request

class MarketAVBoundaryTests(unittest.TestCase):
    def test_third_reference_retains_language_gate_and_declared_sample_scope(self):
        plan,raw,now=self.fixture();data=json.loads(raw);row=data['market_snapshots'][0]
        row['entity_id']='VA3qvxoZr4Q';row['channel_id']='UCemzpRC1q9xqvYKnTvWeQ3A'
        raw=json.dumps(data).encode();plan['source_binding']['sha256']=hashlib.sha256(raw).hexdigest()
        plan.update(purpose='THIRD_METADATA_WINNER_SAMPLED_NOT_NATIVE_APPROVED',opening_seconds=38,
            requested_seconds=58,qualified_winner=False)
        plan['videos'][0].update(video_id=row['entity_id'],channel_id=row['channel_id'],
            role='METADATA_WINNER_AWAITING_NATIVE_AV',windows=[[0,38],[5400,5410],[10790,10800]])
        self.assertEqual(validate_plan(plan,raw,now=now),58)
        row['payload']['default_audio_language']=None;raw=json.dumps(data).encode()
        plan['source_binding']['sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(PermissionError,'MATCHED_PUBLIC_SOURCE_REQUIRED'):
            validate_plan(plan,raw,now=now)
    def test_third_reference_cannot_use_changed_identity_or_shorter_unplanned_opening(self):
        plan,raw,now=self.fixture();plan.update(purpose='THIRD_METADATA_WINNER_SAMPLED_NOT_NATIVE_APPROVED',
            opening_seconds=37,qualified_winner=False)
        with self.assertRaisesRegex(PermissionError,'EXACT_THIRD_METADATA_REFERENCE_REQUIRED'):
            validate_plan(plan,raw,now=now)
    def discovery_fixture(self):
        plan,raw,now=self.fixture();data=json.loads(raw)
        row=data['market_snapshots'][0];row['entity_id']='yY9dDJCLfHU'
        row['channel_id']='UCAOiKo0Ad8F_eRdxgpQSW_A';row['payload']['default_audio_language']=None
        raw=json.dumps(data).encode();plan['source_binding']['sha256']=hashlib.sha256(raw).hexdigest()
        item=plan['videos'][0];item['video_id']=row['entity_id'];item['channel_id']=row['channel_id']
        item['role']='EXPLORATORY_UNQUALIFIED_LANGUAGE_UNKNOWN'
        plan.update(purpose='UNQUALIFIED_DISCOVERY_AV_NO_LANGUAGE_OR_COHORT_UPGRADE',qualified_winner=False)
        return plan,raw,now
    def test_discovery_does_not_require_inventing_declared_language(self):
        plan,raw,now=self.discovery_fixture()
        self.assertEqual(validate_plan(plan,raw,now=now),60)
        self.assertIsNone(json.loads(raw)['market_snapshots'][0]['payload']['default_audio_language'])
    def test_unknown_language_does_not_enter_matched_branch(self):
        plan,raw,now=self.discovery_fixture();del plan['purpose']
        with self.assertRaisesRegex(PermissionError,'MATCHED_PUBLIC_SOURCE_REQUIRED'):
            validate_plan(plan,raw,now=now)
    def test_discovery_cannot_upgrade_winner_or_change_source(self):
        plan,raw,now=self.discovery_fixture();plan['qualified_winner']=True
        with self.assertRaisesRegex(PermissionError,'EXACT_UNQUALIFIED_DISCOVERY_REQUIRED'):
            validate_plan(plan,raw,now=now)
        plan['qualified_winner']=False;plan['videos'][0]['video_id']='other-source'
        with self.assertRaisesRegex(PermissionError,'EXACT_UNQUALIFIED_DISCOVERY_REQUIRED'):
            validate_plan(plan,raw,now=now)
    def fixture(self):
        now=datetime(2026,10,14,16,tzinfo=timezone.utc)
        raw=json.dumps({'captured_at':now.isoformat(),'market_snapshots':[{'entity_type':'VIDEO',
            'entity_id':'abcdefghijk','channel_id':'reference','payload':{'availability':'public',
            'duration_seconds':10800,'default_audio_language':'en-US'}}]}).encode()
        plan={'source_binding':{'sha256':hashlib.sha256(raw).hexdigest()},'publication_authorized':False,
            'coverage':'SAMPLED_NOT_FULL_VIDEO','requested_seconds':60,'videos':[{'video_id':'abcdefghijk',
            'duration_seconds':10800,'channel_id':'reference','windows':[[0,40],[5400,5410],[10790,10800]]}]}
        return plan,raw,now
    def test_whole_video_claim_or_changed_identity_cannot_pass(self):
        plan,raw,now=self.fixture();self.assertEqual(validate_plan(plan,raw,now=now),60)
        plan['coverage']='FULL'
        with self.assertRaises(PermissionError):validate_plan(plan,raw,now=now)
    def test_changed_source_is_rejected_before_call(self):
        plan,raw,now=self.fixture()
        with self.assertRaises(PermissionError):validate_plan(plan,raw+b' ',now=now)
    def test_first_failure_stops_remaining_effects(self):
        plan,_,_=self.fixture();calls=[]
        class Ledger:
            reserve=None;persist=None
        def analyzer(*a,**kw):
            calls.append(kw['window']);return {'key':'key','status':'FAILED','evidence_class':'MODEL_REPORTED'}
        results,complete=execute(plan,Ledger(),'unused',{},analyzer=analyzer)
        self.assertFalse(complete);self.assertEqual(calls,[(0,40)]);self.assertEqual(len(results),1)
    def test_actual_window_success_enum_advances_sequentially(self):
        plan,_,_=self.fixture();calls=[]
        class Ledger:
            reserve=None;persist=None
        def analyzer(*a,**kw):
            calls.append(kw['window']);return {'key':'key','status':'WINDOW_AWAITING_AV_REVIEW',
                'evidence_class':'MODEL_REPORTED'}
        results,complete=execute(plan,Ledger(),'unused',{},analyzer=analyzer)
        self.assertTrue(complete);self.assertEqual(calls,[(0,40),(5400,5410),(10790,10800)])
        self.assertEqual(len(results),3)
    def test_music_context_does_not_replay_teacher_request(self):
        source={'video_id':'abcdefghijk','duration_seconds':10800,'visibility':'PUBLIC'}
        music=build_request(source,window=(0,40),refinement=True,research_context='CHRISTIAN_REST_MUSIC')
        teacher=build_request(source,window=(0,40),refinement=True)
        self.assertNotEqual(music,teacher)
        self.assertIn('Audio summaries are not verbatim transcripts',music['contents'][0]['parts'][1]['text'])
        self.assertNotIn('what is pasted',music['contents'][0]['parts'][1]['text'])

if __name__=='__main__':unittest.main()
