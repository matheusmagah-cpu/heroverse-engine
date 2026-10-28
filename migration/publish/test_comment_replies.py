#!/usr/bin/env python3
"""Offline tests of reply_policy.py and comment_replies.py with a fake YouTube (no network, no secrets)."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration/ops"))
import comment_replies as cr  # noqa: E402
import heartbeat as hb  # noqa: E402
import reply_policy as rp  # noqa: E402

NOW = datetime(2026, 10, 28, 13, 10, tzinfo=timezone.utc)
CH = cr.CHANNEL
SCOPES = {cr.COMMENT_SCOPE}
GOOD = {"decision": "REPLY", "text": "Thank you for watching! Adam was made from dust, yet God breathed life into him."}
VERSE = {"decision": "REPLY",
         "text": "Amen. Genesis 2:7 says it plainly: \"And the LORD God formed man of the dust of the ground\".",
         "verse": {"reference": "Genesis 2:7", "quote": "And the LORD God formed man of the dust of the ground"}}


class R:
    def __init__(self, code, body=None):
        self.status_code, self._body = code, body
        self.content = json.dumps(body).encode() if body is not None else b""

    def json(self):
        return self._body


def thread(cid, vid, text, author="UCviewer", channel=CH, replies=()):
    return {"id": cid, "snippet": {"channelId": channel, "videoId": vid, "topLevelComment": {"id": cid, "snippet": {
        "authorChannelId": {"value": author}, "authorDisplayName": "Viewer", "textOriginal": text,
        "publishedAt": "2026-10-28T09:00:00Z", "likeCount": 1, "videoId": vid}}},
        "replies": {"comments": [{"snippet": {"authorChannelId": {"value": a}}} for a in replies]}}


class FakeYT:
    def __init__(self, threads=(), insert_code=200, existing_reply=None):
        self.threads = {t["id"]: t for t in threads}
        self.insert_code, self.existing_reply, self.inserts, self.gets = insert_code, existing_reply, [], []

    def get(self, url, params=None):
        self.gets.append((url.rsplit("/", 1)[-1], dict(params or {})))
        name = url.rsplit("/", 1)[-1]
        if name == "channels":
            return R(200, {"items": [{"id": CH}]})
        if name == "videos":
            return R(200, {"items": [{"id": v, "snippet": {"title": "T " + v}} for v in params["id"].split(",")]})
        if name == "commentThreads" and "id" in params:
            return R(200, {"items": [self.threads[params["id"]]] if params["id"] in self.threads else []})
        if name == "commentThreads":
            return R(200, {"items": list(self.threads.values())})
        if name == "comments":
            items = []
            if self.existing_reply:
                items = [{"id": "REPLYold", "snippet": {"authorChannelId": {"value": CH}, "textOriginal": self.existing_reply}}]
            return R(200, {"items": items})
        raise AssertionError(url)

    def post(self, url, params=None, json=None):
        self.inserts.append(json)
        if self.insert_code >= 300:
            return R(self.insert_code, {"error": {"errors": [{"reason": "commentsDisabled"}]}})
        return R(200, {"id": f"REPLY{len(self.inserts)}"})


class Policy(unittest.TestCase):
    def test_a_short_plain_reply_passes(self):
        self.assertEqual(rp.problems(GOOD, "youtube"), [])
        self.assertEqual(rp.problems(VERSE, "youtube"), [])

    def test_skip_needs_a_known_reason(self):
        self.assertEqual(rp.problems({"decision": "SKIP", "reason": "spam"}, "youtube"), [])
        self.assertTrue(rp.problems({"decision": "SKIP", "reason": "meh"}, "youtube"))
        self.assertTrue(rp.problems({"decision": "MAYBE"}, "youtube"))

    def test_links_mentions_tags_and_banned_words_are_refused(self):
        for text in ("Watch https://youtu.be/x", "see heroverse.com", "@someone yes", "#bible amen",
                     "This is SHOCKING", "you're wrong about Adam", "Subscribe for more", "call +1 555 123 4567"):
            self.assertTrue(rp.problems({"decision": "REPLY", "text": text}, "youtube"), text)

    def test_length_follows_the_platform(self):
        text = "Amen, thank you. " * 10   # 170 characters
        self.assertEqual(rp.problems({"decision": "REPLY", "text": text}, "youtube"), [])
        self.assertTrue(any("TOO_LONG" in p for p in rp.problems({"decision": "REPLY", "text": text}, "tiktok")))

    def test_scripture_only_through_a_checked_verse(self):
        unchecked = {"decision": "REPLY", "text": "Genesis 2:7 tells us God made man from the dust."}
        self.assertTrue(any("VERSE_UNCHECKED" in p for p in rp.problems(unchecked, "youtube")))
        wrong = dict(VERSE, verse={"reference": "Genesis 2:7", "quote": "And God made man out of the dust of the ground"},
                     text="Genesis 2:7: \"And God made man out of the dust of the ground\".")
        self.assertTrue(any(p.startswith("KJV_") for p in rp.problems(wrong, "youtube")))
        missing = dict(VERSE, text="Amen, God formed us.")
        self.assertIn("VERSE_QUOTE_NOT_IN_REPLY", rp.problems(missing, "youtube"))

    def test_the_same_reply_twice_reads_as_a_bot(self):
        bad = rp.file_problems({"a": GOOD, "b": dict(GOOD)}, "youtube")
        self.assertTrue(any("REPLY_DUPLICATE_OF a" in p for p in bad))


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.q, self.r, self.l, self.p = (self.d / n for n in ("q.json", "r.json", "l.json", "p.json"))
        self.p.write_text(json.dumps({"entries": {"bible:genesis-02-short:abc": {"video_id": "VID1"}}}))

    def fetch(self, yt):
        return cr.fetch(yt, self.q, self.r, self.l, self.p, now=NOW)

    def decide(self, **replies):
        self.r.write_text(json.dumps({"replies": replies}))

    def test_fetch_queues_only_viewers_comments_not_yet_answered(self):
        yt = FakeYT([thread("C1", "VID1", "Beautiful story"), thread("C2", "VID1", "our own", author=CH),
                     thread("C3", "VID1", "answered", replies=[CH]), thread("C4", "XVID", "other", channel="UCother")])
        new = self.fetch(yt)
        self.assertEqual(set(new), {"C1"})
        q = json.loads(self.q.read_text())["comments"]["C1"]
        self.assertEqual((q["episode"], q["video_title"]), ("genesis-02-short", "T VID1"))
        self.assertEqual(self.fetch(yt), {})   # a second fetch adds nothing
        listing = [p for n, p in yt.gets if n == "commentThreads"][0]
        self.assertEqual(listing["allThreadsRelatedToChannelId"], CH)

    def test_todo_lists_undecided_comments_then_the_posts_waiting(self):
        self.fetch(FakeYT([thread("C1", "VID1", "a"), thread("C2", "VID1", "b")]))
        self.decide(C1=GOOD)
        waiting, to_post = cr.todo(*(json.loads(p.read_text()) for p in (self.q, self.r)), cr.empty_ledger())
        self.assertEqual((waiting, to_post), (["C2"], 1))

    def test_post_once_then_never_again(self):
        yt = FakeYT([thread("C1", "VID1", "a")])
        self.fetch(yt)
        self.decide(C1=GOOD)
        cr.post(yt, SCOPES, queue_path=self.q, replies_path=self.r, ledger_path=self.l, now=NOW, out=lambda *_: None)
        self.assertEqual(yt.inserts, [{"snippet": {"parentId": "C1", "textOriginal": GOOD["text"]}}])
        self.assertEqual(json.loads(self.l.read_text())["posted"]["C1"]["reply_id"], "REPLY1")
        cr.post(yt, SCOPES, queue_path=self.q, replies_path=self.r, ledger_path=self.l, now=NOW, out=lambda *_: None)
        self.assertEqual(len(yt.inserts), 1)

    def test_a_reply_already_live_is_recorded_not_posted(self):
        yt = FakeYT([thread("C1", "VID1", "a")], existing_reply=GOOD["text"])
        self.fetch(yt)
        self.decide(C1=GOOD)
        cr.post(yt, SCOPES, queue_path=self.q, replies_path=self.r, ledger_path=self.l, now=NOW, out=lambda *_: None)
        self.assertEqual(yt.inserts, [])
        self.assertEqual(json.loads(self.l.read_text())["posted"]["C1"]["reply_id"], "REPLYold")

    def test_caps_skip_and_policy(self):
        yt = FakeYT([thread(f"C{i}", "VID1", str(i)) for i in range(30)])
        self.fetch(yt)
        self.decide(**{f"C{i}": {"decision": "REPLY", "text": f"Thank you, friend number {i}."} for i in range(28)},
                    C28={"decision": "SKIP", "reason": "spam"}, C29={"decision": "REPLY", "text": "see x.com"})
        args = dict(queue_path=self.q, replies_path=self.r, ledger_path=self.l, now=NOW, out=lambda *_: None)
        for _ in range(10):
            cr.post(yt, SCOPES, **args)
        self.assertEqual(len(yt.inserts), cr.DAY_CAP)        # 20 a day, at most MAX_RUN a run
        posted = json.loads(self.l.read_text())["posted"]
        self.assertNotIn("C28", posted)
        self.assertNotIn("C29", posted)
        later = datetime(2026, 10, 29, 1, 10, tzinfo=timezone.utc)
        self.assertEqual(len(cr.post(yt, SCOPES, **dict(args, now=later))), cr.MAX_RUN)   # a new day

    def test_comments_disabled_is_refused_for_good_and_scope_is_required(self):
        yt = FakeYT([thread("C1", "VID1", "a")], insert_code=403)
        self.fetch(yt)
        self.decide(C1=GOOD)
        args = dict(queue_path=self.q, replies_path=self.r, ledger_path=self.l, now=NOW, out=lambda *_: None)
        cr.post(yt, SCOPES, **args)
        self.assertIn("commentsDisabled", json.loads(self.l.read_text())["refused"]["C1"]["reason"])
        cr.post(yt, SCOPES, **args)
        self.assertEqual(len(yt.inserts), 1)
        with self.assertRaises(SystemExit):
            cr.post(yt, set(), **args)

    def test_dry_run_writes_nothing(self):
        yt = FakeYT([thread("C1", "VID1", "a")])
        self.fetch(yt)
        self.decide(C1=GOOD)
        cr.post(yt, SCOPES, queue_path=self.q, replies_path=self.r, ledger_path=self.l, now=NOW, dry=True, out=lambda *_: None)
        self.assertEqual((yt.inserts, self.l.exists()), ([], False))

    def test_the_youtube_api_cannot_like_a_comment_so_nothing_tries(self):
        src = (HERE / "comment_replies.py").read_text()
        self.assertNotIn("setModerationStatus", src)
        self.assertNotIn("rating", src)


class Repository(unittest.TestCase):
    def test_committed_decisions_pass_the_policy(self):
        q, r = (json.loads((HERE / n).read_text()) for n in ("comment_queue.json", "comment_replies.json"))
        self.assertEqual(cr.check(q, r), [])

    def test_the_heartbeat_fetches_and_posts_through_the_day(self):
        task = [t for t in hb.TASKS if t["workflow"] == "comment-replies.yml"]
        self.assertEqual(len(task), 1)
        self.assertGreaterEqual(len(task[0]["slots"]) * cr.MAX_RUN, cr.DAY_CAP)
        wf = (ROOT / ".github/workflows/comment-replies.yml").read_text()
        self.assertNotIn("schedule:", wf)
        self.assertIn("PUBLICATION_HOLD", wf)
        self.assertIn("test_comment_replies.py", wf)
        self.assertLess(wf.index("comment_replies.py post"), wf.index("comment_replies.py fetch"))


if __name__ == "__main__":
    unittest.main()
