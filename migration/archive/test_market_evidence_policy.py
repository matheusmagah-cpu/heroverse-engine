import copy
import unittest
from market_evidence_policy import route_evidence
NOW='2026-10-13T19:48:22Z'
def sample():
    return {'raw_candidates':[{'videoId':str(i),'channelId':'channel'+str(i),
       'published_at':'2026-09-21T07:30:00Z','viewCount':120000,
       'videoDuration':1800,'vph':100} for i in range(3)],
       'cohorts':[{'id':'spoken-prayer','positive_ids':['0','1','2']}],
       'own_baseline':{'retention':'INSUFFICIENT_DATA'}}
class MarketPolicyTests(unittest.TestCase):
    def test_partial_own_values_do_not_claim_complete_private_evidence(self):
        s=sample();s['own_baseline']={'retention':0.8,'views':8,'ctr_ratio':0.005,'status':'OBSERVED'}
        self.assertFalse(route_evidence(s,NOW)['own_creative_metrics_sufficient'])
    def test_missing_own_retention_routes_to_external_review(self):
        d=route_evidence(sample(),NOW)
        self.assertEqual('REVIEW_MARKET_AUDIOVISUAL_AND_COUNTEREXAMPLES',d['action'])
        self.assertTrue(d['own_missing_does_not_pause_market_research'])
    def test_future_candidate_does_not_establish_recurring_pattern(self):
        s=sample();s['raw_candidates'][0]['published_at']='2026-10-14T00:00:00Z'
        self.assertEqual('EXPAND_COMPARABLE_MARKET_DISCOVERY',route_evidence(s,NOW)['action'])
    def test_one_channel_cannot_impersonate_three_channels(self):
        s=sample()
        for row in s['raw_candidates']:row['channelId']='same'
        self.assertEqual(1,route_evidence(s,NOW)['market_cohorts'][0]['distinct_channel_ids'])
    def test_old_candidate_does_not_enter_recent_cohort(self):
        s=sample();s['raw_candidates'][0]['published_at']='2025-09-21T07:30:00Z'
        self.assertFalse(route_evidence(s,NOW)['market_cohorts'][0]['triage_ready'])
    def test_public_views_never_manufacture_private_ctr_retention_or_acceleration(self):
        d=route_evidence(sample(),NOW)
        row=d['market_cohorts'][0]['positive_candidates'][0]
        self.assertIsNone(row['competitor_ctr']);self.assertIsNone(row['competitor_retention'])
        self.assertIsNone(row['measured_acceleration'])
        self.assertFalse(d['release_authority']);self.assertFalse(d['production_ready'])
    def test_incompatible_duration_rejects_comparison(self):
        s=sample();s['raw_candidates'][0]['videoDuration']=10800
        self.assertFalse(route_evidence(s,NOW)['market_cohorts'][0]['triage_ready'])
    def test_duplicate_ids_do_not_expand_sample(self):
        s=sample();s['cohorts'][0]['positive_ids']=['0','0','0']
        d=route_evidence(s,NOW)['market_cohorts'][0]
        self.assertEqual(1,len(d['positive_candidates']))
if __name__=='__main__':unittest.main()
