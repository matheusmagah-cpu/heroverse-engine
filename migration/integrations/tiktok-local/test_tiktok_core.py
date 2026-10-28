#!/usr/bin/env python3
"""Offline tests of the TikTok runner's rules (no browser, no network)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] if len(HERE.parents) > 2 else HERE   # the repository; on the PC the folder itself
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration/publish"))
sys.path.insert(0, str(HERE / "vendor/migration/publish"))   # on the PC (deploy.py)
import reply_policy  # noqa: E402
import tiktok_core as core  # noqa: E402

NOW = datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
VID = "7570000000000000001"
OWN = {VID}


def item(n, **kw):
    return {"comment_id": f"75700000000000{n:05d}", "video_id": VID, "author": "viewer", "comment_text": "Amen",
            "decision": "REPLY", "text": f"Thank you for watching, friend {n}.", **kw}


class Plan(unittest.TestCase):
    def test_caps_a_run_and_a_day(self):
        todo, skips, refused, wait = core.plan([item(i) for i in range(10)], core.empty_ledger(), OWN, NOW,
                                               policy=reply_policy.problems)
        self.assertEqual((len(todo), skips, refused, wait), (core.RUN_CAP, [], [], None))
        ledger = core.empty_ledger()
        for i in range(core.DAY_CAP):
            ledger["actions"][str(i)] = {"state": "REPLIED", "at": core.iso(NOW - timedelta(hours=3))}
        self.assertEqual(core.plan([item(99)], ledger, OWN, NOW, policy=reply_policy.problems)[3], "DAY_CAP_REACHED")

    def test_never_twice_and_a_gap_after_the_last_action(self):
        ledger = core.empty_ledger()
        ledger["actions"][item(1)["comment_id"]] = {"state": "UNCERTAIN", "at": core.iso(NOW - timedelta(hours=2))}
        todo = core.plan([item(1), item(2)], ledger, OWN, NOW, policy=reply_policy.problems)[0]
        self.assertEqual([t["comment_id"] for t in todo], [item(2)["comment_id"]])
        ledger["actions"]["x"] = {"state": "REPLIED", "at": core.iso(NOW - timedelta(minutes=5))}
        self.assertTrue(core.plan([item(3)], ledger, OWN, NOW, policy=reply_policy.problems)[3].startswith("WAIT_MIN_GAP"))

    def test_only_our_videos_and_only_through_the_policy(self):
        bad = [item(1, video_id="7570000000000000999"), item(2, text="see heroverse.com"), item(3, text="x" * 151),
               item(4, text="Genesis 2:7 says so."), item(5, decision="MAYBE")]
        todo, _, refused, _ = core.plan(bad, core.empty_ledger(), OWN, NOW, policy=reply_policy.problems)
        self.assertEqual(todo, [])
        self.assertEqual(len(refused), 5)
        self.assertIn("NOT_OUR_VIDEO", refused[0]["problems"])
        self.assertTrue(any("VERSE_UNCHECKED" in p for p in refused[3]["problems"]))
        # without the repository's policy deployed, nothing is answered
        self.assertTrue(core.plan([item(6)], core.empty_ledger(), OWN, NOW)[2])

    def test_skips_are_recorded_without_any_action(self):
        todo, skips, refused, _ = core.plan([item(1, decision="SKIP", reason="hate"), item(2)], core.empty_ledger(),
                                            OWN, NOW, policy=reply_policy.problems)
        self.assertEqual(([s["comment_id"] for s in skips], len(todo), refused), ([item(1)["comment_id"]], 1, []))

    def test_pauses_are_human_and_random(self):
        p = core.pauses(3, random.Random(1))
        self.assertEqual(p[0], 0)
        self.assertTrue(all(core.PAUSE[0] <= x <= core.PAUSE[1] for x in p[1:]))


class Parse(unittest.TestCase):
    def test_comment_list_keeps_viewers_top_level_comments(self):
        body = {"comments": [
            {"cid": "1", "text": "Amen", "user": {"unique_id": "viewer"}, "create_time": 1, "user_digged": 0},
            {"cid": "2", "text": "ours", "user": {"unique_id": core.HANDLE}},
            {"cid": "3", "text": "a reply", "user": {"unique_id": "v2"}, "reply_id": "1"}]}
        got = core.comments_from_api(body, VID)
        self.assertEqual([c["comment_id"] for c in got], ["1"])
        self.assertEqual(core.comments_from_api(None, VID), [])

    def test_item_list_keeps_only_our_videos(self):
        body = {"itemList": [{"id": VID, "author": {"uniqueId": core.HANDLE}, "stats": {"commentCount": 2}},
                             {"id": "2", "author": {"uniqueId": "someone"}}]}
        self.assertEqual([v["video_id"] for v in core.videos_from_api(body)], [VID])

    def test_new_comments_leave_out_decided_ones(self):
        ledger = core.empty_ledger()
        ledger["actions"]["1"] = {"state": "SKIPPED", "at": core.iso(NOW)}
        found = [{"comment_id": "1"}, {"comment_id": "2"}, {"comment_id": "2"}]
        self.assertEqual(core.new_comments(found, ledger), [{"comment_id": "2"}])


class Source(unittest.TestCase):
    def test_no_cookie_value_spoofing_or_captcha_code(self):
        src = (HERE / "runner.py").read_text()
        for banned in ("cookie[\"value\"]", "c[\"value\"]", "['value']", "stealth", "navigator.webdriver",
                       "add_init_script", "proxy=", "2captcha", "anticaptcha", "storage_state("):
            self.assertFalse(banned in src, banned)
        self.assertIn('c["name"] == "sessionid"', src)

    def test_story_is_reported_unsupported_and_does_nothing(self):
        import runner  # noqa: E402  (no browser is started by the story command)
        self.assertEqual(runner.main(["story", VID]), 2)


if __name__ == "__main__":
    unittest.main()
