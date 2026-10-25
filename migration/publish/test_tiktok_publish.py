#!/usr/bin/env python3
"""Offline: the TikTok mirror posts only Shorts already published on YouTube, the same file, labelled as AI content,
one per run, never twice, and never prints or loses a token."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiktok_auth as ta  # noqa: E402
import tiktok_publish as tp  # noqa: E402

NOW = datetime(2026, 10, 25, 15, 0, tzinfo=timezone.utc)


def episodes(d, items):
    for eid, sha, slot in items:
        (Path(d) / f"{eid}.json").write_text(json.dumps({"id": eid, "output_sha256": sha, "slot": slot,
                                                         "title": f"{eid} title #shorts"}))


def ledger(*keys):
    return {"entries": {k: {"video_id": "yt" + k[-3:], "uploaded_at": "2026-10-24T10:00:00+00:00"} for k in keys}}


class Fake:
    """Records every call; answers like the Content Posting API."""
    def __init__(self, status="SEND_TO_USER_INBOX", options=("SELF_ONLY",), put=201):
        self.calls, self.status, self.options, self.put = [], status, list(options), put

    def __call__(self, method, url, token=None, body=None, data=None, headers=None, timeout=120):
        self.calls.append({"method": method, "url": url, "body": body, "headers": headers or {},
                           "size": len(data) if data else None})
        if url.endswith("creator_info/query/"):
            return {"data": {"privacy_level_options": self.options}, "error": {"code": "ok"}, "_http": 200}
        if url.endswith("video/init/"):
            return {"data": {"publish_id": "p_1", "upload_url": "https://upload.example/u"}, "error": {"code": "ok"}}
        if method == "PUT":
            return {"_http": self.put}
        if url.endswith("status/fetch/"):
            return {"data": {"status": self.status, "fail_reason": "x" if self.status == "FAILED" else None},
                    "error": {"code": "ok"}}
        return {}


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
            done = {"posts": {"bible:genesis-02-short:" + "b" * 64: {"status": "PROCESSING_UPLOAD"},
                              "bible:genesis-01-short:" + "a" * 64: {"status": "FAILED"}}}
            self.assertEqual([k.split(":")[1] for k, _ in tp.pending(led, done, d, NOW)], ["genesis-01-short"])


class Post(unittest.TestCase):
    def setUp(self):
        self.recorded = []
        self.rec = self.recorded.append

    def video(self, d):
        p = Path(d) / "v.mp4"
        p.write_bytes(b"\0" * 1000)
        return p

    def test_inbox_sends_the_file_whole_without_post_info(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Fake()
            r = tp.post({"id": "e", "title": "T"}, self.video(d), "tok", "inbox", self.rec, call=fake, sleep=lambda s: None)
            init = next(c for c in fake.calls if c["url"].endswith("inbox/video/init/"))
            self.assertNotIn("post_info", init["body"])
            self.assertEqual(init["body"]["source_info"]["total_chunk_count"], 1)
            put = next(c for c in fake.calls if c["method"] == "PUT")
            self.assertEqual((put["size"], put["headers"]["Content-Range"]), (1000, "bytes 0-999/1000"))
            self.assertEqual(r["status"], "SEND_TO_USER_INBOX")

    def test_direct_is_labelled_ai_and_private_until_the_app_is_audited(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Fake(status="PUBLISH_COMPLETE")
            r = tp.post({"id": "e", "title": "Eve #shorts"}, self.video(d), "tok", "direct", self.rec, call=fake,
                        sleep=lambda s: None)
            info = next(c for c in fake.calls if c["url"].endswith("publish/video/init/"))["body"]["post_info"]
            self.assertTrue(info["is_aigc"])
            self.assertEqual((info["privacy_level"], r["privacy"]), ("SELF_ONLY", "SELF_ONLY"))
            self.assertNotIn("#shorts", info["title"].split("\n")[0])
            fake = Fake(status="PUBLISH_COMPLETE", options=("SELF_ONLY", "PUBLIC_TO_EVERYONE"))
            r = tp.post({"id": "e", "title": "Eve"}, self.video(d), "tok", "direct", self.rec, call=fake, sleep=lambda s: None)
            self.assertEqual(r["privacy"], "PUBLIC_TO_EVERYONE")

    def test_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            r = tp.post({"id": "e", "title": "T"}, self.video(d), "tok", "inbox", self.rec, call=Fake(status="FAILED"),
                        sleep=lambda s: None)
            self.assertEqual((r["status"], r["fail_reason"]), ("FAILED", "x"))


    def test_the_publish_id_is_recorded_before_the_upload_so_a_crash_never_posts_twice(self):
        # review: a timeout after init used to leave no record, and the next run posted the Short again
        with tempfile.TemporaryDirectory() as d:
            order = []
            fake = Fake()
            call = lambda m, u, **k: (order.append(m if m == "PUT" else u.rsplit("/", 2)[-2]), fake(m, u, **k))[1]
            tp.post({"id": "e", "title": "T"}, self.video(d), "tok", "inbox",
                    lambda r: order.append("RECORD " + r["status"]), call=call, sleep=lambda s: None)
            self.assertLess(order.index("RECORD INITIALIZED"), order.index("PUT"))

    def test_a_refused_upload_fails_and_an_unfinished_one_is_followed_not_resent(self):
        with tempfile.TemporaryDirectory() as d:
            r = tp.post({"id": "e", "title": "T"}, self.video(d), "tok", "inbox", self.rec, call=Fake(put=500),
                        sleep=lambda s: None)
            self.assertEqual((r["status"], r["fail_reason"]), ("FAILED", "upload HTTP 500"))
            r = tp.post({"id": "e", "title": "T"}, self.video(d), "tok", "inbox", self.rec,
                        call=Fake(status="PROCESSING_UPLOAD"), sleep=lambda s: None)
            self.assertEqual(r["status"], "PROCESSING_UPLOAD")
            key = "bible:e:" + "a" * 64
            tiktok = {"posts": {key: dict(r, at="2026-10-25T14:00:00+00:00")}}
            episodes(d, [("e", "a" * 64, "2026-10-24T13:30:00Z")])
            self.assertEqual(tp.pending(ledger(key), tiktok, d, NOW), [])      # never sent twice
            self.assertEqual(tp.recheck(tiktok, "tok", NOW, call=Fake()), [key])
            self.assertEqual(tiktok["posts"][key]["status"], "SEND_TO_USER_INBOX")

    def test_a_short_tiktok_keeps_refusing_stops_blocking_the_queue(self):
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

    def test_an_episode_without_a_slot_waits_a_day_after_its_upload(self):
        with tempfile.TemporaryDirectory() as d:
            episodes(d, [("e", "a" * 64, None)])
            led = {"entries": {"bible:e:" + "a" * 64: {"video_id": "v", "uploaded_at": "2026-10-25T10:00:00+00:00"}}}
            self.assertEqual(tp.pending(led, {"posts": {}}, d, NOW), [])
            led["entries"]["bible:e:" + "a" * 64]["uploaded_at"] = "2026-10-24T10:00:00+00:00"
            self.assertEqual(len(tp.pending(led, {"posts": {}}, d, NOW)), 1)


class Tokens(unittest.TestCase):
    ENV = {"TIKTOK_CLIENT_KEY": "k", "TIKTOK_CLIENT_SECRET": "s", "TIKTOK_REFRESH_TOKEN": "old",
           "GH_SECRETS_PAT": "pat", "GITHUB_REPOSITORY": "o/r"}

    def test_a_rotated_refresh_token_is_detected_and_stored_through_stdin(self):
        access, new = tp.refresh(call=lambda *a, **k: {"access_token": "a", "refresh_token": "new"}, env=self.ENV)
        self.assertEqual((access, new), ("a", "new"))
        _, same = tp.refresh(call=lambda *a, **k: {"access_token": "a", "refresh_token": "old"}, env=self.ENV)
        self.assertIsNone(same)
        seen = {}

        class R:
            returncode = 0

        def run(cmd, **kw):
            seen.update(cmd=cmd, input=kw["input"], gh=kw["env"]["GH_TOKEN"])
            return R()
        tp.store_refresh_token("new", run=run, env=self.ENV)
        self.assertNotIn("new", seen["cmd"])               # never on the command line
        self.assertEqual((seen["input"], seen["gh"]), ("new", "pat"))

    def test_exchange_stores_the_refresh_token_and_prints_no_token(self):
        import contextlib
        import io
        stored, out = [], io.StringIO()
        env = dict(self.ENV, TIKTOK_CODE="c0de")
        with contextlib.redirect_stdout(out):
            rc = ta.exchange(env=env, store=stored.append, call=lambda *a, **k: {
                "access_token": "acc-secret", "refresh_token": "ref-secret", "scope": "user.info.basic,video.upload,video.publish"})
        self.assertEqual((rc, stored), (0, ["ref-secret"]))
        self.assertNotIn("secret", out.getvalue())
        self.assertIn("redirect_uri=https%3A%2F%2Fmatheusmagah-cpu.github.io", ta.consent_url("k", "st"))


if __name__ == "__main__":
    unittest.main()
