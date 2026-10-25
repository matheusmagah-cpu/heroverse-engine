#!/usr/bin/env python3
"""Offline: the TikTok mirror (through Buffer) sends only Shorts already published on YouTube, the same file by its
public release URL, with a caption that points to the long video and states the AI visuals, one per run, never twice,
and a Short that keeps failing never blocks the queue."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiktok_publish as tp  # noqa: E402

NOW = datetime(2026, 10, 25, 15, 0, tzinfo=timezone.utc)


def episodes(d, items):
    for eid, sha, slot in items:
        (Path(d) / f"{eid}.json").write_text(json.dumps({"id": eid, "output_sha256": sha, "slot": slot,
                                                         "title": f"{eid} title #shorts"}))


def ledger(*keys):
    return {"entries": {k: {"video_id": "yt" + k[-3:], "uploaded_at": "2026-10-24T10:00:00+00:00"} for k in keys}}


class Fake:
    """Answers like Buffer's GraphQL API and records every call."""
    def __init__(self, create=None, status="sent", net=False):
        self.calls, self.create, self.status, self.net = [], create, status, net

    def __call__(self, method, url, token=None, body=None, **kw):
        self.calls.append({"token": token, "body": body})
        q = body["query"]
        if self.net:
            return {"_http": 0, "_net": "TimeoutError"}
        if "organizations" in q:
            return {"_http": 200, "data": {"account": {"organizations": [{"id": "o"}]}}}
        if "channels(input" in q:
            return {"_http": 200, "data": {"channels": [{"id": "ch-yt", "service": "youtube"},
                                                        {"id": "ch-tt", "service": "tiktok"}]}}
        if "createPost" in q:
            if isinstance(self.create, int):
                return {"_http": self.create}
            return {"_http": 200, "data": {"createPost": self.create or {"post": {"id": "bp1", "status": "sending"}}}}
        if "post(input" in q:
            if self.status is None:
                return {"_http": 200, "errors": [{"message": "Cannot query field"}]}
            return {"_http": 200, "data": {"post": {"id": "bp1", "status": self.status}}}
        return {"_http": 200, "data": {}}


class Pending(unittest.TestCase):
    def test_only_published_shorts_past_their_slot_oldest_first_and_never_twice(self):
        with tempfile.TemporaryDirectory() as d:
            episodes(d, [("genesis-01-short", "a" * 64, "2026-10-24T13:30:00Z"),
                         ("genesis-02-short", "b" * 64, "2026-10-23T23:30:00Z"),
                         ("genesis-05-short", "c" * 64, "2026-10-26T13:30:00Z"),     # YouTube slot still ahead
                         ("genesis-03-short", "d" * 64, "2026-10-24T23:30:00Z")])
            led = ledger("bible:genesis-01-short:" + "a" * 64, "bible:genesis-02-short:" + "b" * 64,
                         "bible:genesis-05-short:" + "c" * 64, "bible:genesis-03-short:" + "e" * 64,  # other file
                         "pilot-011:" + "f" * 64)                                                     # a long
            got = [k.split(":")[1] for k, _ in tp.pending(led, {"posts": {}}, d, NOW)]
            self.assertEqual(got, ["genesis-02-short", "genesis-01-short"])
            done = {"posts": {"bible:genesis-02-short:" + "b" * 64: {"status": "SENDING"},
                              "bible:genesis-01-short:" + "a" * 64: {"status": "FAILED"}}}
            self.assertEqual([k.split(":")[1] for k, _ in tp.pending(led, done, d, NOW)], ["genesis-01-short"])

    def test_an_episode_without_a_slot_waits_a_day_after_its_upload(self):
        with tempfile.TemporaryDirectory() as d:
            episodes(d, [("e", "a" * 64, None)])
            led = {"entries": {"bible:e:" + "a" * 64: {"video_id": "v", "uploaded_at": "2026-10-25T10:00:00+00:00"}}}
            self.assertEqual(tp.pending(led, {"posts": {}}, d, NOW), [])
            led["entries"]["bible:e:" + "a" * 64]["uploaded_at"] = "2026-10-24T10:00:00+00:00"
            self.assertEqual(len(tp.pending(led, {"posts": {}}, d, NOW)), 1)

    def test_a_short_that_keeps_failing_stops_blocking_the_queue(self):
        with tempfile.TemporaryDirectory() as d:
            episodes(d, [("old", "a" * 64, "2026-10-20T13:30:00Z"), ("new", "b" * 64, "2026-10-24T13:30:00Z")])
            old, new = "bible:old:" + "a" * 64, "bible:new:" + "b" * 64
            prev = None
            for _ in range(tp.MAX_FAILURES):
                prev = tp.settle({"status": "FAILED"}, prev)
            self.assertEqual(prev["status"], "FAILED_FINAL")
            self.assertEqual([k for k, _ in tp.pending(ledger(old, new), {"posts": {old: prev}}, d, NOW)], [new])
            once = tp.settle({"status": "FAILED"}, None)       # a single failure retries after the untried ones
            self.assertEqual([k for k, _ in tp.pending(ledger(old, new), {"posts": {old: once}}, d, NOW)], [new, old])


class Post(unittest.TestCase):
    EP = {"id": "genesis-06-short", "output_sha256": "f" * 64,
          "title": "He Walked With God ☁️ | Enoch, Bible Story (KJV) #shorts"}

    def test_the_caption_points_to_the_long_and_states_the_ai_visuals(self):
        c = tp.caption(self.EP)
        self.assertIn("Enoch, Bible Story (KJV), is on YouTube: HeroVerse (link in bio)", c)
        self.assertIn("Visuals and voice: AI-generated", c)
        self.assertIn("#aigenerated", c)
        self.assertNotIn("#shorts", c)

    def test_buffer_publishes_the_public_release_file_automatically_now(self):
        fake, rec = Fake(), []
        r = tp.post(self.EP, "key", "ch-tt", rec.append, call=fake)
        inp = fake.calls[0]["body"]["variables"]["input"]
        self.assertEqual((inp["channelId"], inp["schedulingType"], inp["mode"]), ("ch-tt", "automatic", "shareNow"))
        self.assertEqual(inp["assets"][0]["video"]["url"],
                         tp.RELEASE + "bible-genesis-06-short-sha256-" + "f" * 64 + ".mp4")
        self.assertEqual(rec[0]["status"], "SENDING")              # recorded before the call
        self.assertEqual((r["status"], r["buffer_post_id"]), ("QUEUED", "bp1"))

    def test_a_refusal_fails_and_a_lost_reply_is_never_sent_again(self):
        r = tp.post(self.EP, "key", "ch-tt", lambda x: None, call=Fake(create={"message": "video too long"}))
        self.assertEqual((r["status"], r["fail_reason"]), ("FAILED", "video too long"))
        r = tp.post(self.EP, "key", "ch-tt", lambda x: None, call=Fake(net=True))
        self.assertEqual(r["status"], "SENDING")
        with tempfile.TemporaryDirectory() as d:
            key = "bible:genesis-06-short:" + "f" * 64
            episodes(d, [("genesis-06-short", "f" * 64, "2026-10-24T13:30:00Z")])
            self.assertEqual(tp.pending(ledger(key), {"posts": {key: r}}, d, NOW), [])

    def test_an_unclear_reply_is_never_sent_again(self):
        # review of e8f9c3b: a 504 after Buffer created the post used to be FAILED, and the next run posted it again
        for create in (504, 502):
            r = tp.post(self.EP, "key", "ch-tt", lambda x: None, call=Fake(create=create))
            self.assertEqual(r["status"], "SENDING", create)
        r = tp.post(self.EP, "key", "ch-tt", lambda x: None, call=Fake(create=401))
        self.assertEqual(r["status"], "FAILED")

    def test_a_post_that_cannot_be_confirmed_is_stuck_not_resent(self):
        # review of e8f9c3b: a status query that keeps failing used to turn into FAILED after 24 h and a second post
        tiktok = {"posts": {"k": {"status": "QUEUED", "buffer_post_id": "bp1", "at": "2026-10-24T10:00:00+00:00"}}}
        self.assertEqual(tp.recheck(tiktok, "key", NOW, call=Fake(status=None)), ["k"])
        self.assertEqual(tiktok["posts"]["k"]["status"], "STUCK")
        tiktok["posts"]["k"].update(status="QUEUED")
        tp.recheck(tiktok, "key", NOW, call=Fake(status="sending"))
        self.assertEqual(tiktok["posts"]["k"]["status"], "STUCK")
        tiktok["posts"]["k"].update(status="QUEUED")
        tp.recheck(tiktok, "key", NOW, call=Fake(status="error"))
        self.assertEqual(tiktok["posts"]["k"]["status"], "FAILED")     # only Buffer's own error is retried

    def test_queued_posts_are_followed_until_sent(self):
        tiktok = {"posts": {"k": {"status": "QUEUED", "buffer_post_id": "bp1", "at": "2026-10-25T14:00:00+00:00"}}}
        self.assertEqual(tp.recheck(tiktok, "key", NOW, call=Fake(status="sending")), [])
        self.assertEqual(tp.recheck(tiktok, "key", NOW, call=Fake(status="sent")), ["k"])
        self.assertEqual(tiktok["posts"]["k"]["status"], "SENT")

    def test_the_tiktok_channel_is_found_and_the_key_only_travels_in_the_header(self):
        fake = Fake()
        self.assertEqual(tp.tiktok_channel("key", call=fake), "ch-tt")
        self.assertEqual(fake.calls[0]["token"], "key")
        self.assertNotIn("key", json.dumps(fake.calls[0]["body"]))


class Describe(unittest.TestCase):
    def test_discover_lists_the_input_types_createpost_accepts(self):
        types = {"CreatePostInput": [{"name": "assets", "type": {"kind": "LIST", "name": None, "ofType": {
                     "kind": "NON_NULL", "name": None, "ofType": {"kind": "INPUT_OBJECT", "name": "AssetInput",
                                                                  "ofType": None}}}}],
                 "AssetInput": [{"name": "video", "type": {"kind": "INPUT_OBJECT", "name": "VideoAssetInput",
                                                           "ofType": None}}],
                 "VideoAssetInput": [{"name": "url", "type": {"kind": "NON_NULL", "name": None,
                                                              "ofType": {"kind": "SCALAR", "name": "String"}}}]}

        def call(method, url, token=None, body=None, **kw):
            name = json.loads(body["query"].split("name: ")[1].split(")")[0])
            return {"_http": 200, "data": {"__type": {"name": name, "inputFields": types.get(name, [])}}}
        out = tp.describe("key", call=call)
        self.assertEqual(out["CreatePostInput"]["assets"], "LIST / NON_NULL / AssetInput")
        self.assertEqual(out["VideoAssetInput"]["url"], "NON_NULL / String")


if __name__ == "__main__":
    unittest.main()
