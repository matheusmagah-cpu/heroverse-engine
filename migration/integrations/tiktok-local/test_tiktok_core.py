#!/usr/bin/env python3
"""Offline tests of the TikTok runner's rules (no browser, no network)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] if len(HERE.parents) > 2 else HERE   # the repository; on the PC the folder itself
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration/publish"))
sys.path.insert(0, str(HERE / "vendor/migration/publish"))   # on the PC (deploy.py)
import reply_policy  # noqa: E402
import tiktok_core as core  # noqa: E402
import runner  # noqa: E402

NOW = datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
VID = "7570000000000000001"
OWN = {VID}


def item(n, **kw):
    return {"comment_id": f"75700000000000{n:05d}", "video_id": VID, "author": "viewer", "comment_text": "Amen",
            "decision": "REPLY", "text": f"Thank you for watching, friend {n}.", **kw}


class Plan(unittest.TestCase):
    def test_e188_reply_requires_complete_comment_identity(self):
        for key in ("author", "comment_text"):
            for value in (None, "", "   ", 123):
                with self.subTest(key=key, value=value):
                    todo, _, refused, _ = core.plan([item(1, **{key: value})], core.empty_ledger(), OWN, NOW,
                                                    policy=reply_policy.problems)
                    self.assertEqual(todo, [])
                    self.assertEqual(len(refused), 1)

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


class CommentNode:
    """Only visible fields / attributes used by the runner; no browser or API is started."""
    def __init__(self, cid, author="viewer", text="Amen"):
        self.cid, self.author, self.text = cid, author, text

    def get_attribute(self, name):
        return self.cid if name == "data-comment-id" else None

    def inner_text(self, **kwargs):
        return f"{self.author}\n{self.text}\nReply"


class VisibleField:
    def __init__(self, text="", href=None):
        self.text, self.href = text, href
        self.first = self

    def count(self):
        return 1

    def inner_text(self, **kwargs):
        return self.text

    def get_attribute(self, name):
        return self.href if name == "href" else None


class Identity(unittest.TestCase):
    def test_profile_href_accepts_only_https_tiktok_or_root_relative_path(self):
        for href in ("/@viewer", "/@viewer/", "https://www.tiktok.com/@viewer", "https://tiktok.com/@viewer/"):
            with self.subTest(href=href):
                self.assertEqual(core.author_from_href(href), "viewer")
        for href in ("javascript:/@viewer", "ftp:/@viewer", "https:/@viewer", "http://www.tiktok.com/@viewer",
                     "https://example.invalid/@viewer", "//www.tiktok.com/@viewer", "///@viewer", "@viewer"):
            with self.subTest(href=href):
                self.assertIsNone(core.author_from_href(href))

    def page(self):
        return SimpleNamespace(url=f"{runner.BASE}/@{core.HANDLE}/video/{VID}", mouse=SimpleNamespace(wheel=Mock()))

    def selectors(self, nodes):
        def select(scope, key, timeout=0):
            if key == "comment_item":
                return SimpleNamespace(all=lambda: nodes)
            if key == "comment_author":
                return VisibleField(scope.author, f"/@{scope.author}")
            if key == "comment_text":
                return VisibleField(scope.text)
            raise AssertionError(f"Unexpected selector {key}")
        return select

    def test_e188_prefix_or_author_substring_cannot_select_a_different_comment(self):
        requested = item(1, comment_text="A" * 40 + " this is the full requested comment")
        wrong = CommentNode(item(2)["comment_id"], "viewer_extra", "A" * 40 + " different ending")
        correct = CommentNode(requested["comment_id"], requested["author"], requested["comment_text"])
        with patch.object(runner, "first", side_effect=self.selectors([wrong, correct])), patch.object(runner, "pause"):
            self.assertIs(runner.find_comment(self.page(), requested), correct)

    def test_duplicate_target_or_mismatched_content_is_refused(self):
        requested = item(1)
        cases = [([CommentNode(requested["comment_id"]), CommentNode(requested["comment_id"])], "AMBIGUOUS"),
                 ([CommentNode(requested["comment_id"], "viewer_extra")], "MISMATCH"),
                 ([CommentNode(requested["comment_id"], text="Amen but a different comment")], "MISMATCH"),
                 ([CommentNode(None)], "UNVERIFIABLE")]
        for nodes, reason in cases:
            with self.subTest(reason=reason), patch.object(runner, "first", side_effect=self.selectors(nodes)), \
                    patch.object(runner, "pause"):
                with self.assertRaisesRegex(RuntimeError, reason):
                    runner.find_comment(self.page(), requested)

    def test_missing_identity_stops_before_open_or_any_effect(self):
        for field in ("comment_id", "video_id", "author", "comment_text"):
            requested = item(1)
            requested.pop(field)
            with self.subTest(field=field), patch.object(runner, "open_video") as opened, \
                    patch.object(runner, "find_comment", return_value=None), patch.object(core, "write_json") as written:
                result = runner.act(self.page(), requested, core.empty_ledger(), False)
                self.assertIn("IDENTITY_INVALID", result)
                opened.assert_not_called()
                written.assert_not_called()

    def test_target_changed_after_lookup_stops_before_ledger_or_click(self):
        requested = item(1)
        node = CommentNode(requested["comment_id"], text="Changed comment")
        buttons = MagicMock()

        def select(scope, key, timeout=0):
            return buttons if key in ("comment_like", "comment_reply") else self.selectors([node])(scope, key, timeout)

        with patch.object(runner, "open_video"), patch.object(runner, "find_comment", return_value=node), \
                patch.object(runner, "first", side_effect=select), patch.object(core, "write_json") as written:
            with self.assertRaisesRegex(RuntimeError, "MISMATCH"):
                runner.act(self.page(), requested, core.empty_ledger(), False)
            written.assert_not_called()
            buttons.first.click.assert_not_called()

    def test_e188_outgoing_write_is_aborted_before_a_mismatched_effect(self):
        requested = item(1)
        endpoints = (("/api/comment/digg", {"aweme_id": VID, "cid": requested["comment_id"], "digg_type": "1"}),
                     ("/api/comment/publish", {"aweme_id": VID, "reply_id": requested["comment_id"], "text": requested["text"]}))
        for endpoint, good in endpoints:
            key = "cid" if endpoint.endswith("digg") else "reply_id"
            cases = [good, {**good, key: item(2)["comment_id"]}, {k: v for k, v in good.items() if k != key},
                     {**good, "aweme_id": "7570000000000000999"}]
            cases.append({**good, "digg_type": "0"} if key == "cid" else {**good, "text": "Different response"})
            for i, fields in enumerate(cases):
                with self.subTest(endpoint=endpoint, case=i):
                    page, route = Mock(), Mock()
                    handlers, effects = [], []
                    page.route.side_effect = lambda pattern, callback: handlers.append(callback)
                    page.expect_response.return_value = MagicMock()
                    page.expect_response.return_value.__enter__.return_value = SimpleNamespace(
                        value=SimpleNamespace(json=lambda: {"status_code": 0}))
                    route.continue_.side_effect = lambda: effects.append("sent")
                    request = SimpleNamespace(url=runner.BASE + endpoint + "/?" + urlencode(fields), post_data=None)
                    action = lambda: handlers[0](route, request)
                    if i == 0:
                        self.assertEqual(runner.wait_api(page, endpoint, action, requested), {"status_code": 0})
                        self.assertEqual(effects, ["sent"])
                        route.abort.assert_not_called()
                    else:
                        with self.assertRaisesRegex(RuntimeError, "COMMENT_REQUEST_IDENTITY_MISMATCH"):
                            runner.wait_api(page, endpoint, action, requested)
                        self.assertEqual(effects, [])
                        route.abort.assert_called_once()
                    page.unroute.assert_called_once()

    def test_outgoing_schema_domain_and_duplicate_fields_are_not_guessed(self):
        requested = item(1)
        endpoint = "/api/comment/publish"
        fields = {"aweme_id": VID, "reply_id": requested["comment_id"], "text": requested["text"]}
        url = runner.BASE + endpoint + "/?" + urlencode(fields)
        self.assertTrue(core.request_targets_comment(url, None, endpoint, requested))
        for bad in (url.replace("www.tiktok.com", "example.invalid"), url + "&reply_id=" + requested["comment_id"],
                    url.replace("/publish/", "/publish/other/"), url.replace("https:", "http:")):
            self.assertFalse(core.request_targets_comment(bad, None, endpoint, requested))
        self.assertFalse(core.request_targets_comment(url, "reply_id=other", endpoint, requested))
        self.assertTrue(core.request_targets_comment(runner.BASE + endpoint + "/", urlencode(fields), endpoint, requested))

    def test_publish_status_alone_or_wrong_parent_never_becomes_replied(self):
        requested = item(1)
        good = {"status_code": 0, "comment": {"cid": item(9)["comment_id"], "reply_id": requested["comment_id"],
                "aweme_id": VID, "text": requested["text"], "user": {"unique_id": core.HANDLE}}}
        self.assertEqual(core.verified_reply_id(good, requested), item(9)["comment_id"])
        for body in (None, [], {}, {"status_code": 0}, {**good, "status_code": 1}, {**good, "status_code": False}):
            self.assertIsNone(core.verified_reply_id(body, requested))
        for key, value in (("cid", ""), ("reply_id", item(2)["comment_id"]), ("aweme_id", "other"),
                           ("user", {"unique_id": "other"}), ("text", "other")):
            with self.subTest(key=key):
                self.assertIsNone(core.verified_reply_id({**good, "comment": {**good["comment"], key: value}}, requested))


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


class FreshInstall(unittest.TestCase):
    def test_state_files_are_written_on_a_fresh_install(self):
        # E141: `comments` died on the PC's first run: out/ did not exist yet, and no test had written a state file
        # outside the repository (env-vs-test). Every file the runner writes goes through write_json into an empty
        # install folder here.
        import tempfile
        import runner  # noqa: E402
        with tempfile.TemporaryDirectory() as d:
            for target in (runner.LEDGER, runner.OWN, Path(runner.HERE) / "out" / "comments.json"):
                dest = Path(d) / Path(target).relative_to(runner.HERE)
                core.write_json(dest, {"ok": True})
                self.assertEqual(core.read_json(dest, None), {"ok": True})


class Listing(unittest.TestCase):
    def test_a_challenge_or_an_empty_listing_is_never_a_silent_success(self):
        # E142: the PC's logged-out dry run got "Drag the slider to fit the puzzle" on our profile page and
        # `comments` ended 0 with videos=0, as if there were nothing to answer
        self.assertEqual(core.listing_outcome(None)[0], 4)
        self.assertIn("CHALLENGE", core.listing_outcome(None)[1])
        self.assertEqual(core.listing_outcome([])[0], 5)
        self.assertEqual(core.listing_outcome([{"video_id": VID}]), (0, None))
        src = (HERE / "runner.py").read_text()
        self.assertIn("code, why = core.listing_outcome(videos)", src)
        self.assertIn("drag the slider", src)


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
