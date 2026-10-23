import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "production"))
import first_comment as fc  # noqa: E402
import package_pilot  # noqa: E402
import publish_video as pv  # noqa: E402

TEXT = 'If "His Mercies Are New" spoke to you, write "Amen" below and share one mercy God showed you today.'
VIDEO_BYTES = b"0" * 10
VIDEO_SHA = hashlib.sha256(VIDEO_BYTES).hexdigest()


class R:
    def __init__(self, code, body=None, headers=None):
        self.status_code, self._body, self.headers = code, body, headers or {}
        self.content = json.dumps(body).encode() if body is not None else b""
        self.text = self.content.decode()

    def json(self):
        return self._body


def refusal(code, reason, message="refused"):
    return R(code, {"error": {"code": code, "message": message, "errors": [{"reason": reason}]}})


class FakeSession:
    """Mocked YouTube session: no network. comment_answer is what commentThreads.insert returns."""

    def __init__(self, comment_answer=None, privacy="private", existing=()):
        self.calls, self.comment_answer, self.privacy, self.existing = [], comment_answer, privacy, list(existing)
        self.comment_bodies = []

    def get(self, url, params=None, **kw):
        self.calls.append(("GET", url.split("/")[-1]))
        if url.endswith("channels"):
            return R(200, {"items": [{"id": pv.CHANNEL}]})
        if url.endswith("playlists"):
            return R(200, {"items": []})
        if url.endswith("commentThreads"):
            return R(200, {"items": self.existing})
        return R(200, {"items": [{"snippet": {"channelId": pv.CHANNEL, "title": "T"},
                                  "status": {"privacyStatus": self.privacy, "publishAt": "2026-10-20T00:30:00Z"}}]})

    def post(self, url, params=None, **kw):
        self.calls.append(("POST", url.split("/")[-1]))
        if params and params.get("uploadType") == "resumable":
            return R(200, {}, {"Location": "https://upload/session"})
        if url.endswith("playlists"):
            return R(200, {"id": "PL1"})
        if url.endswith("commentThreads"):
            self.comment_bodies.append((params, kw.get("json")))
            return self.comment_answer or R(200, {"id": "Ugz-comment-1"})
        return R(200, {})

    def put(self, url, data=None, headers=None):
        self.calls.append(("PUT", headers.get("Content-Range")))
        if headers["Content-Range"].startswith("bytes */"):
            return R(308)
        return R(200, {"id": "VID123"})


def posts(fake, what="commentThreads"):
    return [c for c in fake.calls if c == ("POST", what)]


class PublishStep(unittest.TestCase):
    def run_once(self, d, fake, first_comment=TEXT):
        pv.session = lambda: fake
        pkg, man = d / "p.json", d / "m.json"
        package = {"pilot_id": "pilot-x", "title": "T", "description": "D", "tags": ["a"],
                   "playlist": {"title": "Morning Prayer", "description": "x"}}
        if first_comment:
            package["first_comment"] = first_comment
        pkg.write_text(json.dumps(package))
        man.write_text(json.dumps({"output_sha256": VIDEO_SHA, "sentences": [{"start": 0.3, "end": 2.0, "text": "Hi."}]}))
        (d / "review.json").write_text(json.dumps({"status": "PASS", "output_sha256": VIDEO_SHA,
            "watched_review": {"status": "PASS", "model": "gemini-3.8-flash", "overall": 9.6}}))
        (d / "v.mp4").write_bytes(VIDEO_BYTES)
        (d / "t.jpg").write_bytes(b"jpg")
        pv.main(pkg, man, d / "v.mp4", d / "t.jpg", d / "ledger.json", d / "r.json", "2026-10-20T00:30:00Z")
        return json.loads((d / "r.json").read_text())

    def test_comment_posted_after_playlist_and_never_repeated(self):
        with tempfile.TemporaryDirectory() as t:
            d, first = Path(t), FakeSession()
            receipt = self.run_once(d, first)
            self.assertEqual(receipt["steps"]["first_comment"], "Ugz-comment-1")
            params, body = first.comment_bodies[0]
            self.assertEqual(params, {"part": "snippet"})
            self.assertEqual(body, {"snippet": {"videoId": "VID123", "topLevelComment": {"snippet": {"textOriginal": TEXT}}}})
            order = [c[1] for c in first.calls if c[0] == "POST"]
            self.assertLess(order.index("playlists"), order.index("commentThreads"))
            ledger = json.loads((d / "ledger.json").read_text())
            self.assertEqual(ledger["entries"][f"pilot-x:{VIDEO_SHA}"]["steps"]["first_comment"], "Ugz-comment-1")
            second = FakeSession()
            self.run_once(d, second)
            self.assertEqual([c for c in second.calls if c[0] == "POST"], [])  # re-runs repeat nothing

    def test_refusals_are_pending_and_never_fail_the_publication(self):
        for answer in (refusal(403, "insufficientPermissions", "Request had insufficient authentication scopes."),
                       refusal(403, "commentsDisabled"), refusal(403, "forbidden"), refusal(400, "processingFailure")):
            with self.subTest(answer=answer.text), tempfile.TemporaryDirectory() as t:
                receipt = self.run_once(Path(t), FakeSession(comment_answer=answer))
                self.assertEqual(receipt["video_id"], "VID123")
                self.assertTrue(receipt["steps"]["first_comment"].startswith("PENDING: HTTP_"))
                self.assertIn(answer.json()["error"]["errors"][0]["reason"], receipt["steps"]["first_comment"])
                self.assertTrue(receipt["steps"]["thumbnail"] and receipt["steps"]["captions"])

    def test_network_error_is_pending(self):
        class Broken(FakeSession):
            def post(self, url, params=None, **kw):
                if url.endswith("commentThreads"):
                    raise ConnectionError("reset")
                return super().post(url, params, **kw)
        with tempfile.TemporaryDirectory() as t:
            pv.time.sleep, sleep = (lambda s: None), pv.time.sleep
            try:
                receipt = self.run_once(Path(t), Broken())
            finally:
                pv.time.sleep = sleep
            self.assertEqual(receipt["steps"]["first_comment"], "PENDING: ConnectionError")

    def test_pending_is_retried_on_rerun_and_existing_comment_reused(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.run_once(d, FakeSession(comment_answer=refusal(403, "forbidden")))
            mine = {"id": "Ugz-already", "snippet": {"topLevelComment": {"snippet": {
                "authorChannelId": {"value": pv.CHANNEL}, "textOriginal": TEXT}}}}
            again = FakeSession(existing=[mine])
            receipt = self.run_once(d, again)
            self.assertEqual(receipt["steps"]["first_comment"], "Ugz-already")
            self.assertEqual(posts(again), [])  # found, not posted twice

    def test_no_first_comment_in_package_means_no_step(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeSession()
            receipt = self.run_once(Path(t), fake, first_comment=None)
            self.assertNotIn("first_comment", receipt["steps"])
            self.assertEqual(posts(fake), [])

    def test_invalid_text_is_pending_without_a_call(self):
        fake = FakeSession()
        self.assertTrue(pv.first_comment(fake, "V", "x" * 301).startswith("PENDING: FIRST_COMMENT_TEXT_INVALID"))
        self.assertEqual(fake.calls, [])


class RetryCli(unittest.TestCase):
    def receipt(self, d, state=None):
        steps = {"thumbnail": True, "captions": True, "playlist": "PL1"}
        if state is not None:
            steps["first_comment"] = state
        (d / "r.json").write_text(json.dumps({"version": "publish-receipt-v1", "video_id": "VID123", "steps": steps}))
        (d / "ledger.json").write_text(json.dumps({"entries": {"pilot-x:abc": {"video_id": "VID123", "steps": dict(steps)}}}))

    def run_cli(self, d, fake):
        pv.session = lambda: fake
        code = fc.main("VID123", TEXT, d / "r.json", d / "ledger.json")
        return code, json.loads((d / "r.json").read_text()), json.loads((d / "ledger.json").read_text())

    def test_posts_pending_once_public_and_updates_receipt_and_ledger(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.receipt(d, "PENDING: HTTP_403 forbidden")
            fake = FakeSession(privacy="public")
            code, receipt, ledger = self.run_cli(d, fake)
            self.assertEqual(code, 0)
            self.assertEqual(receipt["steps"]["first_comment"], "Ugz-comment-1")
            self.assertEqual(ledger["entries"]["pilot-x:abc"]["steps"]["first_comment"], "Ugz-comment-1")
            again = FakeSession(privacy="public")
            code, _, _ = self.run_cli(d, again)
            self.assertEqual((code, again.calls), (0, []))  # already posted: no call at all

    def test_never_attempted_receipt_is_posted(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.receipt(d)  # published before the first-comment step existed (pilot-012)
            code, receipt, _ = self.run_cli(d, FakeSession(privacy="public"))
            self.assertEqual((code, receipt["steps"]["first_comment"]), (0, "Ugz-comment-1"))

    def test_still_private_stays_pending_without_posting(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.receipt(d, "PENDING: HTTP_403 forbidden")
            fake = FakeSession(privacy="private")
            code, receipt, _ = self.run_cli(d, fake)
            self.assertEqual(code, 3)
            self.assertTrue(receipt["steps"]["first_comment"].startswith("PENDING: video not public yet (privacy=private"))
            self.assertEqual(posts(fake), [])

    def test_public_but_refused_stays_pending(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.receipt(d, "PENDING: x")
            code, receipt, _ = self.run_cli(d, FakeSession(privacy="public", comment_answer=refusal(403, "commentsDisabled")))
            self.assertEqual(code, 3)
            self.assertIn("commentsDisabled", receipt["steps"]["first_comment"])

    def test_wrong_video_refused(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.receipt(d, "PENDING: x")
            pv.session = lambda: FakeSession(privacy="public")
            with self.assertRaises(SystemExit):
                fc.main("OTHER", TEXT, d / "r.json")


class PackageText(unittest.TestCase):
    def test_default_from_title_promise(self):
        text = package_pilot.default_first_comment(
            "Night Prayer of Thanksgiving | His Mercies Are New, Rest in His Faithfulness")
        self.assertEqual(text, 'If "His Mercies Are New, Rest in His Faithfulness" spoke to you, write "Amen" below '
                               'and share one mercy God showed you today.')
        self.assertLessEqual(len(text), 300)
        self.assertTrue(text.isascii())
        self.assertEqual(text.count("."), 1)  # one sentence

    def test_title_without_bar_and_script_override(self):
        self.assertIn('"Morning Prayer"', package_pilot.default_first_comment("Morning Prayer"))
        self.assertEqual(package_pilot.first_comment_for({"working_title": "A | B", "first_comment": " Say Amen. "}), "Say Amen.")
        self.assertIn('"B"', package_pilot.first_comment_for({"working_title": "A | B"}))

    def test_rule_breaking_text_refused_and_default_falls_back(self):
        for bad in ("x" * 301, "", "Type Amen \U0001F64F", "Share this before it's too late", "Your wealth is coming"):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                package_pilot.check_first_comment(bad)
        self.assertEqual(package_pilot.default_first_comment("Prayer | Wealth Is Coming"),
                         'If this prayer spoke to you, write "Amen" below and share one mercy God showed you today.')


if __name__ == "__main__":
    unittest.main()
