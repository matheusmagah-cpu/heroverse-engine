#!/usr/bin/env python3
"""Offline checks of the YPP counters estimate: only public long-form hours (365 d) and public Shorts views (90 d)."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile,json,contextlib,io
from datetime import datetime,timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goal_report as gr  # noqa: E402


class Eligible(unittest.TestCase):
    def test_counts_only_what_ypp_counts(self):
        videos = [{"id": "L1", "short": False}, {"id": "S1", "short": True}, {"id": "L2", "short": False}]  # public now
        per365 = {"L1": ("LONG_FORM_CONTENT", 600), "S1": ("SHORTS", 1200), "L2": ("LONG_FORM_CONTENT", 120),
                  "GONE": ("LONG_FORM_CONTENT", 6000)}  # GONE: private or removed, not counted
        per90 = {"S1": ("SHORTS", 900), "L1": ("LONG_FORM_CONTENT", 50), "OLD": ("SHORTS", 10_000)}
        e = gr.eligible(videos, per365, per90)
        self.assertEqual(e["public_long_form_watch_hours_365d"], 12.0)   # (600 + 120) / 60, no Shorts, no GONE
        self.assertEqual(e["public_shorts_views_90d"], 900)              # public Shorts only, 90 days
        self.assertEqual(e["all_content_watch_hours_365d_top200"], 132.0)

    def test_duration_fallback_when_type_unknown(self):
        videos = [{"id": "A", "short": True}, {"id": "B", "short": False}]
        e = gr.eligible(videos, {"A": (None, 60), "B": (None, 120)}, {"A": (None, 5), "B": (None, 7)})
        self.assertEqual((e["public_long_form_watch_hours_365d"], e["public_shorts_views_90d"]), (2.0, 5))


class Funnel(unittest.TestCase):
    """Short -> long funnel of a long video, from its Analytics rows by traffic source (owner, 2026-10-26: measured)."""
    def test_share_and_watch_time_of_viewers_who_came_from_shorts(self):
        rows = [["SHORTS", 300, 1500, 300], ["SUBSCRIBER", 100, 800, 480], ["RELATED_VIDEO", 100, 400, 240]]
        f = gr.funnel(rows)
        self.assertEqual((f["views"], f["views_from_shorts"], f["share_from_shorts"]), (500, 300, 0.6))
        self.assertEqual((f["avg_view_s_from_shorts"], f["avg_view_s_other"]), (300.0, 360.0))
        self.assertEqual(f["verdict"], "SHORTS_VIEWERS_LEAVE_EARLIER")
        self.assertEqual(list(f["sources"]), ["SHORTS", "SUBSCRIBER", "RELATED_VIDEO"])

    def test_viewers_from_shorts_who_watch_as_long_and_no_shorts_traffic(self):
        self.assertEqual(gr.funnel([["SHORTS", 50, 500, 600], ["YT_SEARCH", 50, 400, 480]])["verdict"], "SHORTS_VIEWERS_STAY")
        f = gr.funnel([["YT_SEARCH", 10, 20, 120]])
        self.assertEqual((f["verdict"], f["share_from_shorts"]), ("NO_SHORTS_TRAFFIC", 0.0))
        self.assertIsNone(gr.funnel([])["share_from_shorts"])


class Integration(unittest.TestCase):
    def test_existing_collection_to_learning_capture_no_added_requests(self):
        calls=[]
        class Client:
            units=3
            def __init__(self, token, budget):
                assert budget==50
            def get(self, endpoint, params, cost):
                calls.append(endpoint)
                if endpoint=='channels': return {'items':[{'statistics':{'subscriberCount':'1','viewCount':'3'},'contentDetails':{'relatedPlaylists':{'uploads':'u'}}}]}
                if endpoint=='playlistItems': return {'items':[{'contentDetails':{'videoId':'v'}}]}
                return {'items':[{'id':'v','snippet':{'title':'Prayer','publishedAt':'2026-10-19T00:00:00Z'},'statistics':{'viewCount':'3'},'status':{'privacyStatus':'public'},'contentDetails':{'duration':'PT600S'}}]}
        def per(token,start,end,metrics):
            return ({'v':('LONG_FORM_CONTENT',2,3,4,1)} if 'estimatedMinutesWatched' in metrics else {'v':('LONG_FORM_CONTENT',3)}),'analytics creatorContentType'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);prod=root/'production';prod.mkdir();ledger=root/'ledger.json';ledger.write_text('{}');out=root/'out'
            with patch.object(gr.mp,'access_token',return_value='fixture'),patch.object(gr.mp,'Client',Client),patch.object(gr,'analytics',return_value={'rows':[[2,3,1,4]]}) as query,patch.object(gr,'per_video',side_effect=per) as per_query,contextlib.redirect_stdout(io.StringIO()):
                gr.main(prod,ledger,out)
            self.assertEqual(calls,['channels','playlistItems','videos']);self.assertEqual(query.call_count,2);self.assertEqual(per_query.call_count,2)  # totals + the funnel of the one public long
            pointer=json.loads((out/'learning/latest-capture.json').read_bytes());snap=json.loads(Path(pointer['path']).read_bytes())
            self.assertEqual(snap['data_api_units'],3);self.assertEqual(snap['additional_api_calls'],0)
            self.assertEqual(snap['owned_videos'][0]['snippet']['publishedAt'],'2026-10-19T00:00:00Z')
            self.assertFalse(snap['coverage']['exact_checkpoint']);self.assertEqual(snap['owned_private'][0]['basic']['rows'][0]['views'],3)
            import learning_loop as loop
            repo=Path(__file__).resolve().parents[2]
            result=loop.run(str(out/'learning'),str(ledger),str(repo/'migration/structures/guided-prayer-scenic.json'),str(repo/'migration/evidence/vidiq/20261019/structure_audit.json'),str(repo/'migration/evidence/vidiq/20261019/thumbnails.json'))
            self.assertEqual(result['decision']['evidence_decision'],'HOLD')
            self.assertTrue(Path(result['brief']['path']).exists())
    def test_analytics_error_remains_unavailable_in_capture(self):
        class Client:
            units=2
            def __init__(self,*args):pass
            def get(self,endpoint,params,cost):
                if endpoint=='channels':return {'items':[{'statistics':{},'contentDetails':{'relatedPlaylists':{'uploads':'u'}}}]}
                return {'items':[]}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'prod').mkdir();(root/'ledger.json').write_text('{}')
            with patch.object(gr.mp,'access_token',return_value='fixture'),patch.object(gr.mp,'Client',Client),patch.object(gr,'analytics',side_effect=RuntimeError('unavailable')),contextlib.redirect_stdout(io.StringIO()):
                gr.main(root/'prod',root/'ledger.json',root/'out')
            pointer=json.loads((root/'out/learning/latest-capture.json').read_bytes());snapshot=json.loads(Path(pointer['path']).read_bytes())
            self.assertEqual(snapshot['analytics_source_status'],'ERROR');self.assertEqual(snapshot['owned_private'],[])
    def test_uploaded_is_not_public(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)/'pilot-012';(d/'out').mkdir(parents=True)
            (d/'schedule.json').write_text('{"publish_at":"2026-10-20T00:00:00Z"}')
            (d/'out/manifest.json').write_text('{"output_sha256":"hash"}')
            ledger={'entries':{'pilot-012:hash':{'video_id':'v'}}};now=datetime(2026,10,20,tzinfo=timezone.utc)
            rows,_=gr.pipeline(temp,ledger,now);self.assertTrue(rows[0]['uploaded']);self.assertIsNone(rows[0]['published'])
            rows,_=gr.pipeline(temp,ledger,now,{'v':'private'});self.assertFalse(rows[0]['published'])
            rows,_=gr.pipeline(temp,ledger,now,{'v':'public'});self.assertTrue(rows[0]['published'])

if __name__ == "__main__":
    unittest.main()
