#!/usr/bin/env python3
"""Offline checks of the Shorts publication: slots only for Shorts still to upload, never a duplicate upload,
and the state of every Short (failed / not selected / approved awaiting slot / scheduled / published)."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_shorts as ps  # noqa: E402
import publish_shorts as pub  # noqa: E402


class Resp:
    def __init__(self, data):
        self.data = data


class FakeYouTube:
    def __init__(self):
        self.uploads = []

    def get(self, url, params=None):
        if url.endswith("channels"):
            return Resp({"items": [{"id": pub.pv.CHANNEL}]})
        if params.get("part") == "snippet":
            return Resp({"items": [{"snippet": {"title": "Long"}}]})
        return Resp({"items": [{"status": {"uploadStatus": "uploaded"}}]})


def setup(t, done):
    d = Path(t)
    files = {}
    for i in range(3):
        data = f"short {i}".encode()
        (d / f"short-0{i}.mp4").write_bytes(data)
        files[i] = hashlib.sha256(data).hexdigest()
    shorts = [{"file": f"short-0{i}.mp4", "sha256": files[i], "hook": "Hook.", "title": f"T{i}", "publish": True,
               "review": {"status": "PASS", "model": "gemini-3.8-flash"}} for i in range(3)]
    (d / "shorts.json").write_text(json.dumps({"source_pilot": "pilot-009", "shorts": shorts}))
    entries = {"pilot-009:L": {"video_id": "LONG"}}
    entries.update({f"short:pilot-009:{files[i]}": {"video_id": f"OLD{i}", "slot": "2026-10-18T14:00:00Z"} for i in done})
    (d / "ledger.json").write_text(json.dumps({"entries": entries}))
    return d, files


class PublishShorts(unittest.TestCase):
    def setUp(self):
        self.yt = FakeYouTube()
        self.real = (pub.pv.session, pub.pv.check, pub.pv.upload, pub.shorts_qa.check)
        pub.pv.session = lambda: self.yt
        pub.pv.check = lambda r, what: r.data
        pub.pv.upload = lambda s, path, body: (self.yt.uploads.append((path.name, body["status"]["publishAt"])), {"id": "NEW-" + path.name})[1]
        pub.shorts_qa.check = lambda path: {"status": "PASS"}

    def tearDown(self):
        pub.pv.session, pub.pv.check, pub.pv.upload, pub.shorts_qa.check = self.real

    def run_pub(self, d, slots):
        pub.main(str(d / "shorts.json"), str(d), "pilot-009:L", str(d / "ledger.json"), str(d / "receipt.json"), slots)
        return json.loads((d / "receipt.json").read_text())

    def test_partial_earlier_run_needs_slots_only_for_the_rest(self):
        with tempfile.TemporaryDirectory() as t:
            d, files = setup(t, done=(0,))
            (d / "short-00.mp4").unlink()  # already on YouTube, file deleted from the release
            r = self.run_pub(d, "2026-10-19T14:00:00Z,2026-10-19T20:00:00Z")
            self.assertEqual(self.yt.uploads, [("short-01.mp4", "2026-10-19T14:00:00Z"), ("short-02.mp4", "2026-10-19T20:00:00Z")])
            self.assertEqual([x["video_id"] for x in r["shorts"]], ["OLD0", "NEW-short-01.mp4", "NEW-short-02.mp4"])

    def test_rerun_after_everything_uploaded_uploads_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=(0, 1, 2))
            self.run_pub(d, "")
            self.assertEqual(self.yt.uploads, [])

    def test_too_few_slots_still_fails_loudly(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            with self.assertRaises(SystemExit) as e:
                self.run_pub(d, "2026-10-19T14:00:00Z")
            self.assertIn("NOT_ENOUGH_SLOTS", str(e.exception))
            self.assertEqual(self.yt.uploads, [])


class States(unittest.TestCase):
    def test_every_short_has_one_state(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "pilot-009"
            (d / "shorts").mkdir(parents=True)
            shorts = [{"file": "a", "sha256": "a", "publish": False, "review": {"status": "FAIL"}},
                      {"file": "b", "sha256": "b", "publish": False, "review": {"status": "PASS", "model": "gemini-3.8-flash"}},
                      {"file": "c", "sha256": "c", "publish": True, "review": {"status": "PASS", "model": "gemini-3.8-flash"}},
                      {"file": "d", "sha256": "d", "publish": True, "review": {"status": "PASS", "model": "gemini-3.8-flash"}},
                      {"file": "e", "sha256": "e", "publish": True, "review": {"status": "PASS", "model": "gemini-3.8-flash"}},
                      {"file": "f", "sha256": "f", "publish": True, "review": {"status": "PASS", "model": "gemini-3.8-flash"}, "qa": {"status": "FAIL"}}]
            (d / "shorts" / "shorts.json").write_text(json.dumps({"source_pilot": "pilot-009", "shorts": shorts}))
            ledger = {"entries": {"short:pilot-009:d": {"video_id": "D", "slot": "2026-10-20T14:00:00Z"},
                                  "short:pilot-009:e": {"video_id": "E", "slot": "2026-10-18T14:00:00Z"}}}
            now = datetime(2026, 10, 19, tzinfo=timezone.utc)
            self.assertEqual([r["state"] for r in ps.states(d, ledger, now)],
                             ["failed", "not_selected", "approved_awaiting_slot", "scheduled", "published", "failed"])
            self.assertEqual(ps.todo_files(d, ledger), [("c", "c")])
            shorts[2]["review"]["model"] = "gemini-3.5-flash-lite"  # a fallback model's PASS never publishes
            (d / "shorts" / "shorts.json").write_text(json.dumps({"source_pilot": "pilot-009", "shorts": shorts}))
            self.assertEqual(ps.states(d, ledger, now)[2]["state"], "review_by_undesignated_model")
            self.assertEqual(ps.todo_files(d, ledger), [])


if __name__ == "__main__":
    unittest.main()
