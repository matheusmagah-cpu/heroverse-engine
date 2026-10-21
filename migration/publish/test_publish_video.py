import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_video as pv  # noqa: E402

VIDEO_BYTES = b"0" * 10
VIDEO_SHA = hashlib.sha256(VIDEO_BYTES).hexdigest()


def synthetic_review():
    return {"status": "PASS", "output_sha256": VIDEO_SHA,
            "watched_review": {"status": "PASS", "model": "gemini-3.8-flash", "overall": 9}}


class R:
    def __init__(self, code, body=None, headers=None):
        self.status_code, self._body, self.headers = code, body, headers or {}
        self.content = json.dumps(body).encode() if body is not None else b""
        self.text = self.content.decode()

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, channel=pv.CHANNEL):
        self.calls, self.channel = [], channel

    def get(self, url, params=None, **kw):
        self.calls.append(("GET", url.split("/")[-1]))
        if url.endswith("channels"):
            return R(200, {"items": [{"id": self.channel}]})
        if url.endswith("playlists"):
            return R(200, {"items": []})
        return R(200, {"items": [{"snippet": {"channelId": pv.CHANNEL, "title": "T"}, "status": {"privacyStatus": "private"}}]})

    def post(self, url, params=None, **kw):
        self.calls.append(("POST", url.split("/")[-1]))
        if params and params.get("uploadType") == "resumable":
            self.upload_body = kw.get("json")
            return R(200, {}, {"Location": "https://upload/session"})
        if url.endswith("playlists"):
            return R(200, {"id": "PL1"})
        return R(200, {})

    def put(self, url, data=None, headers=None):
        self.calls.append(("PUT", headers.get("Content-Range")))
        if headers["Content-Range"].startswith("bytes */"):
            return R(308)
        return R(200, {"id": "VID123"})


class Publish(unittest.TestCase):
    def run_once(self, d, fake):
        pv.session = lambda: fake
        pkg, man = d / "p.json", d / "m.json"
        pkg.write_text(json.dumps({"pilot_id": "pilot-x", "title": "T", "description": "D", "tags": ["a"],
                                   "playlist": {"title": "Morning Prayer", "description": "x"}}))
        man.write_text(json.dumps({"output_sha256": VIDEO_SHA, "sentences": [{"start": 0.3, "end": 2.0, "text": "Hi."}]}))
        (d / "review.json").write_text(json.dumps(synthetic_review()))
        (d / "v.mp4").write_bytes(VIDEO_BYTES)
        (d / "t.jpg").write_bytes(b"jpg")
        pv.main(pkg, man, d / "v.mp4", d / "t.jpg", d / "ledger.json", d / "r.json")
        return json.loads((d / "r.json").read_text())

    def test_full_flow_and_idempotent_rerun(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            first = FakeSession()
            receipt = self.run_once(d, first)
            self.assertEqual(receipt["video_id"], "VID123")
            self.assertEqual(first.upload_body["status"]["privacyStatus"], "public")  # validated before upload
            self.assertNotIn("publishAt", first.upload_body["status"])
            self.assertEqual(set(receipt["steps"]), {"thumbnail", "captions", "playlist"})
            second = FakeSession()
            self.run_once(d, second)
            self.assertFalse(any(c[0] == "PUT" for c in second.calls))  # never uploads twice
            self.assertEqual([c for c in second.calls if c[0] == "POST"], [])

    def test_wrong_channel_refused(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(SystemExit):
                self.run_once(Path(t), FakeSession(channel="UCother"))

    def test_srt(self):
        self.assertEqual(pv.srt([{"start": 61.5, "end": 62.25, "text": "x"}]), "1\n00:01:01,500 --> 00:01:02,250\nx\n")


class NewUploadOwnerFloor(unittest.TestCase):
    def fixture(self, d, review=None):
        (d / "p.json").write_text(json.dumps({"pilot_id": "pilot-x", "title": "T", "description": "D", "tags": ["a"]}))
        (d / "m.json").write_text(json.dumps({"output_sha256": VIDEO_SHA}))
        (d / "review.json").write_text(json.dumps(synthetic_review() if review is None else review))
        (d / "v.mp4").write_bytes(VIDEO_BYTES)
        (d / "t.jpg").write_bytes(b"jpg")
        return (d / "p.json", d / "m.json", d / "v.mp4", d / "t.jpg", d / "ledger.json", d / "r.json")

    def assert_blocked_without_session_or_upload(self, args):
        with patch.object(pv, "session") as session, patch.object(pv, "upload") as upload:
            with self.assertRaisesRegex(SystemExit, "OWNER_QUALITY_POLICY_BLOCKED"):
                pv.main(*args)
            session.assert_not_called()
            upload.assert_not_called()
        self.assertFalse(args[-2].exists())
        self.assertFalse(args[-1].exists())

    def test_low_missing_or_invalid_score_blocks_before_session(self):
        for score in (8.5, 8.99, 10.1, True, False, None, "9", float("nan"), float("inf")):
            with self.subTest(score=score), tempfile.TemporaryDirectory() as t:
                review = synthetic_review()
                review["watched_review"]["overall"] = score
                self.assert_blocked_without_session_or_upload(self.fixture(Path(t), review))
        with tempfile.TemporaryDirectory() as t:
            review = synthetic_review()
            del review["watched_review"]["overall"]
            self.assert_blocked_without_session_or_upload(self.fixture(Path(t), review))

    def test_missing_malformed_and_non_object_evidence_blocks(self):
        for value in ("missing", "not JSON", "[]", "null", '{"status":"PASS"}'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as t:
                d = Path(t)
                args = self.fixture(d)
                if value == "missing":
                    (d / "review.json").unlink()
                else:
                    (d / "review.json").write_text(value)
                self.assert_blocked_without_session_or_upload(args)
        for value in (None, [], "PASS", {}):
            with self.subTest(watched=value), tempfile.TemporaryDirectory() as t:
                review = synthetic_review()
                review["watched_review"] = value
                self.assert_blocked_without_session_or_upload(self.fixture(Path(t), review))

    def test_status_and_designated_model_are_required(self):
        for scope, field, value in (("top", "status", "FAIL"), ("top", "status", None),
                                    ("watched", "status", "FAIL"), ("watched", "status", None),
                                    ("watched", "model", "gemini-3.6-flash"), ("watched", "model", None)):
            with self.subTest(scope=scope, field=field, value=value), tempfile.TemporaryDirectory() as t:
                review = synthetic_review()
                target = review if scope == "top" else review["watched_review"]
                target[field] = value
                self.assert_blocked_without_session_or_upload(self.fixture(Path(t), review))

    def test_manifest_or_top_level_review_hash_mismatch_blocks(self):
        for name in ("m.json", "review.json"):
            for value in ("a" * 64, VIDEO_SHA.upper(), "abc", None):
                with self.subTest(name=name, value=value), tempfile.TemporaryDirectory() as t:
                    d = Path(t)
                    args = self.fixture(d)
                    evidence = json.loads((d / name).read_text())
                    evidence["output_sha256"] = value
                    (d / name).write_text(json.dumps(evidence))
                    self.assert_blocked_without_session_or_upload(args)

    def test_actual_video_differs_from_matching_stale_manifest_and_review(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            args = self.fixture(d)
            self.assertEqual(json.loads((d / "m.json").read_text())["output_sha256"],
                             json.loads((d / "review.json").read_text())["output_sha256"])
            (d / "v.mp4").write_bytes(b"different real bytes")
            self.assert_blocked_without_session_or_upload(args)

    def test_missing_video_blocks_new_upload(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            args = self.fixture(d)
            (d / "v.mp4").unlink()
            self.assert_blocked_without_session_or_upload(args)

    def test_hash_is_streamed_and_watched_review_is_adapted_without_rewrite(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.fixture(d)
            contents = b"a" * (2 * 1024 * 1024 + 1)
            sha = hashlib.sha256(contents).hexdigest()
            (d / "v.mp4").write_bytes(contents)
            review = synthetic_review()
            review["output_sha256"] = sha
            before = json.dumps(review)
            (d / "review.json").write_text(before)
            with patch.object(Path, "read_bytes", side_effect=AssertionError("must stream VIDEO")), \
                    patch.object(pv.owner_quality_policy, "check", wraps=pv.owner_quality_policy.check) as check:
                pv.check_new_upload(d / "m.json", {"output_sha256": sha}, d / "v.mp4")
            bound, actual = check.call_args.args
            self.assertEqual(actual, sha)
            self.assertEqual(bound, {**review["watched_review"], "output_sha256": sha})
            self.assertNotIn("output_sha256", review["watched_review"])
            self.assertEqual((d / "review.json").read_text(), before)

    def test_existing_id_8_5_resumes_without_local_video_or_retroactive_gate(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            review = synthetic_review()
            review["watched_review"]["overall"] = 8.5
            args = self.fixture(d, review)
            (d / "v.mp4").unlink()
            (d / "ledger.json").write_text(json.dumps({"entries": {f"pilot-x:{VIDEO_SHA}": {
                "video_id": "EXISTING", "steps": {"thumbnail": True}}}}))
            before = (d / "review.json").read_text()
            fake = FakeSession()
            with patch.object(pv, "session", return_value=fake), patch.object(pv, "upload") as upload, \
                    patch.object(pv, "check_new_upload", side_effect=AssertionError("no retroactive gate")):
                pv.main(*args)
                upload.assert_not_called()
            self.assertEqual(json.loads((d / "r.json").read_text())["video_id"], "EXISTING")
            self.assertEqual((d / "review.json").read_text(), before)
            self.assertFalse(any(c[0] in ("PUT", "POST") for c in fake.calls))


if __name__ == "__main__":
    unittest.main()
