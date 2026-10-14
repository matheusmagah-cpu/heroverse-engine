import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from collect_official_evidence import collect, CHANNEL, DISCOVERY_IDS


class CandidateStageTests(unittest.TestCase):
    def run_stage(self, privacy='public', owned=CHANNEL,catalog=False):
        calls=[]; reserved=[]; consumed=[]
        video={'id':DISCOVERY_IDS[0], 'snippet':{'channelId':'reference',
            'title':'Observed title','publishedAt':'2026-10-01T00:00:00Z'},
            'contentDetails':{'duration':'PT3H'},'statistics':{'viewCount':'123'},
            'status':{'privacyStatus':privacy}}
        class Resource:
            def __init__(self,kind):self.kind=kind
            def list(self,**kw):
                calls.append((self.kind,kw))
                if self.kind=='videos':return {'items':[video]}
                if self.kind=='playlist':return {'items':[{'contentDetails':{'videoId':video['id']}}]}
                return {'items':[{'id':owned}]} if kw.get('mine') else {'items':[{'id':'reference',
                    'snippet':{'title':'Observed channel'},'contentDetails':{'relatedPlaylists':{'uploads':'UUreference'}}}]}
        youtube=types.SimpleNamespace(channels=lambda:Resource('channels'),videos=lambda:Resource('videos'),
            playlistItems=lambda:Resource('playlist'))
        def module(**kw):return types.SimpleNamespace(**kw)
        stubs={
            'oauth_health':module(observe_refresh=lambda raw,renew:(object(),{'status':'PASS'}),
                identity_health=lambda *a:{'status':'PASS'}),
            'google.oauth2.credentials':module(Credentials=object),
            'google.auth.transport.requests':module(Request=object),
            'hero_engine.google_api_runtime':module(build_authorized_service=lambda *a,**kw:youtube,
                execute_google_request=lambda request,**kw:request, GoogleOperationDeadline=lambda **kw:object()),
            'hero_engine.phase6_quota':module(reserve_general_quota=lambda *a,**kw:reserved.append(kw),
                consume_general_quota=lambda *a,**kw:consumed.append(kw))}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules,stubs), patch.dict('os.environ',
                {'GITHUB_RUN_ID':'12345','HERO_YT_AUTHORIZED_USER_JSON':'unused-test-only'}):
            root=Path(tmp);export=root/'export';export.mkdir()
            if owned!=CHANNEL:
                with self.assertRaises(PermissionError):collect(root,export,candidate_only=True)
                self.assertEqual(len(calls),1)
                return
            result=collect(root,export,candidate_only=True,catalog_only=catalog)
            evidence=json.loads((export/'evidence.json').read_text())
        return result,evidence,calls,reserved,consumed

    def test_official_candidates_use_exact_ids_and_existing_quota(self):
        result,evidence,calls,reserved,consumed=self.run_stage()
        self.assertEqual(calls[1][1]['id'],','.join(DISCOVERY_IDS))
        self.assertEqual(len(calls),3);self.assertEqual(len(reserved),3);self.assertEqual(len(consumed),3)
        self.assertTrue(all(x['units']==1 for x in reserved))
        row=evidence['market_snapshots'][0]
        self.assertEqual(row['payload']['duration_seconds'],10800)
        self.assertEqual(row['payload']['view_count'],123)
        self.assertEqual(row['payload']['catalog_role'],'DISCOVERY_LEAD_NOT_QUALIFIED_REFERENCE')
        self.assertFalse(evidence['publication_performed']);self.assertFalse(evidence['production_ready'])
        self.assertEqual(evidence['vidiq_credits_used'],0)

    def test_unlisted_candidate_cannot_enter_public_evidence(self):
        _,evidence,calls,_,_=self.run_stage('unlisted')
        self.assertEqual(evidence['market_snapshots'],[])
        self.assertEqual(len(calls),2)
        self.assertEqual(evidence['unavailable_video_ids'],sorted(DISCOVERY_IDS))

    def test_wrong_owned_identity_stops_before_discovery(self):
        self.run_stage(owned='foreign')

    def test_catalogue_is_bounded_and_adds_existing_matched_channels(self):
        _,evidence,calls,reserved,_=self.run_stage(catalog=True)
        self.assertEqual(len(calls),5);self.assertEqual(len(reserved),5)
        self.assertEqual(calls[3][1]['maxResults'],50)
        self.assertIn('UCTdc_zl40D9wa0_LH9yaGZA',calls[2][1]['id'])
        self.assertEqual(evidence['status'],'BOUNDED_CANDIDATE_CATALOG_OBSERVED')
        self.assertEqual(evidence['market_snapshots'][0]['entity_type'],'CHANNEL')
        self.assertFalse(evidence['production_ready'])

if __name__=='__main__':unittest.main()
