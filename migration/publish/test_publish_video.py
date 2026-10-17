import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_video as pv  # noqa: E402


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
        man.write_text(json.dumps({"output_sha256": "abc", "sentences": [{"start": 0.3, "end": 2.0, "text": "Hi."}]}))
        (d / "v.mp4").write_bytes(b"0" * 10)
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


if __name__ == "__main__":
    unittest.main()
