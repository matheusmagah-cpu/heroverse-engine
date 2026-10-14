import copy
from datetime import datetime,timezone
import unittest
from market_comparability import select

class ComparabilityTests(unittest.TestCase):
    def fixture(self):
        clock='2026-10-14T15:44:13+00:00';now=datetime.fromisoformat(clock)
        rows=[{'entity_type':'CHANNEL','channel_id':'channel'}]
        for i,duration in enumerate([4000,10800,14000]):
            rows.append({'entity_type':'VIDEO','entity_id':str(i),'channel_id':'channel',
                'snapshot_id':str(i),'operation_id':'op','captured_at':clock,
                'payload':{'channel_id_public':'channel','availability':'public','duration_seconds':duration,
                    'default_audio_language':'en-US','timestamp':now.timestamp()-10*86400}})
        return {'operation_id':'op','captured_at':clock,'market_snapshots':rows},now
    def test_one_hour_cannot_corrobate_three_hour_winners(self):
        source,now=self.fixture();bundle,audit=select(source,now=now)
        self.assertEqual([r['entity_id'] for r in bundle['snapshots'] if r['entity_type']=='VIDEO'],['1','2'])
        self.assertEqual(audit['exclusions'][0]['reason'],'OUTSIDE_DECLARED_3_TO_4_HOUR_BAND')
        self.assertFalse(audit['quality_authorized'])
    def test_unknown_language_is_excluded_not_guessed(self):
        source,now=self.fixture();source['market_snapshots'][2]['payload']['default_audio_language']=None
        _,audit=select(source,now=now);self.assertEqual(audit['eligible_videos'],1)
    def test_source_observations_are_never_relabelled(self):
        source,now=self.fixture();before=copy.deepcopy(source);select(source,now=now);self.assertEqual(source,before)
    def test_stale_source_requires_fresh_observation(self):
        source,now=self.fixture()
        with self.assertRaises(PermissionError):select(source,now=datetime.fromtimestamp(now.timestamp()+86401,timezone.utc))
    def test_identity_mismatch_is_rejected(self):
        source,now=self.fixture();source['market_snapshots'][2]['payload']['channel_id_public']='foreign'
        with self.assertRaises(PermissionError):select(source,now=now)

if __name__=='__main__':unittest.main()
