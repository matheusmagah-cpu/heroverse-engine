#!/usr/bin/env python3
"""Offline: channel-privacy.yml mode unschedule holds scheduled uploads (private, no publishAt) and never touches a
public video (owner, 2026-10-26: the scheduled prayer longs pilot-008 and pilot-014 stop; nothing is deleted)."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "migration" / "channel"))
import channel_privacy as cp  # noqa: E402


class FakeYouTube:
    def __init__(self, videos):
        self.videos = videos          # id -> status
        self.writes = []

    def __call__(self, tok, method, endpoint, params, body=None):
        if method == "GET":
            vid = params["id"]
            return {"items": [{"status": dict(self.videos[vid]), "snippet": {"channelId": cp.CHANNEL}}] if vid in self.videos else []}
        self.writes.append(body)
        self.videos[body["id"]] = {k: v for k, v in body["status"].items()}   # no publishAt sent: the schedule is gone
        return {"status": self.videos[body["id"]]}


def run(plan, videos):
    yt = FakeYouTube(videos)
    with tempfile.TemporaryDirectory() as t:
        p, out = Path(t) / "hold-plan.json", Path(t) / "receipt.json"
        p.write_text(json.dumps(plan))
        error, log = None, io.StringIO()
        with patch.object(cp, "token", return_value="fixture"), patch.object(cp, "call", yt), \
                contextlib.redirect_stdout(log):
            try:
                cp.unschedule(p, out)
            except SystemExit as e:
                error = str(e)
        run.receipt, run.log = json.loads(out.read_text()), log.getvalue()
        return run.receipt["changes"], yt, error


class Unschedule(unittest.TestCase):
    def test_scheduled_becomes_private_without_publish_at_and_public_is_left_alone(self):
        plan = {"channel_id": cp.CHANNEL, "to_unschedule": ["sched", "pub", "held"]}
        changes, yt, error = run(plan, {
            "sched": {"privacyStatus": "private", "publishAt": "2026-10-27T00:00:00Z"},
            "pub": {"privacyStatus": "public"},
            "held": {"privacyStatus": "private"}})
        self.assertIsNone(error)
        by = {c["video_id"]: c for c in changes}
        self.assertEqual(by["sched"]["result"], "UNSCHEDULED")
        self.assertEqual(by["sched"]["before"], {"privacy": "private", "publishAt": "2026-10-27T00:00:00Z"})  # the undo
        self.assertEqual(by["pub"]["result"], "SKIPPED_ALREADY_PUBLIC")
        self.assertEqual(by["held"]["result"], "ALREADY_UNSCHEDULED")
        self.assertEqual([w["id"] for w in yt.writes], ["sched"])          # one write; the public video untouched
        self.assertEqual(yt.writes[0]["status"]["privacyStatus"], "private")
        self.assertNotIn("publishAt", yt.writes[0]["status"])

    def test_a_held_video_already_public_is_reported_plainly_and_never_hidden(self):
        # review of #415: pilot-014's slot (26/10 10:00) may pass before the hold runs; the skip must be visible
        changes, yt, error = run({"channel_id": cp.CHANNEL, "to_unschedule": ["53Xysf9x46c", "sched"]}, {
            "53Xysf9x46c": {"privacyStatus": "public"},
            "sched": {"privacyStatus": "private", "publishAt": "2026-10-27T00:00:00Z"}})
        self.assertIsNone(error)                                              # a skip, not a failure
        self.assertEqual([w["id"] for w in yt.writes], ["sched"])             # never hidden here
        self.assertEqual(run.receipt["already_public_not_changed"], ["53Xysf9x46c"])
        self.assertIn("HELD_VIDEO_ALREADY_PUBLIC 53Xysf9x46c", run.log)
        self.assertIn("::warning::", run.log)                                 # shown on the Actions run page

    def test_a_missing_video_fails_the_run(self):
        changes, yt, error = run({"channel_id": cp.CHANNEL, "to_unschedule": ["gone"]}, {})
        self.assertEqual((changes[0]["result"], error, yt.writes), ("SKIPPED_NOT_OWNED_OR_MISSING", "UNSCHEDULE_INCOMPLETE", []))

    def test_the_hold_plan_lists_the_scheduled_prayer_longs(self):
        plan = json.loads((ROOT / "migration/channel/hold-plan.json").read_text())
        ledger = json.loads((ROOT / "migration/publish/ledger.json").read_text())["entries"]
        ids = {k.split(":")[0]: v["video_id"] for k, v in ledger.items() if k.split(":")[0] in ("pilot-008", "pilot-014")}
        self.assertEqual(plan["channel_id"], cp.CHANNEL)
        self.assertEqual(sorted(plan["to_unschedule"]), sorted(ids.values()))
        wf = (ROOT / ".github/workflows/channel-privacy.yml").read_text()
        self.assertIn("unschedule migration/channel/hold-plan.json", wf)


if __name__ == "__main__":
    unittest.main()
