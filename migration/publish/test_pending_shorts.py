#!/usr/bin/env python3
"""Offline checks: which approved Shorts are still to publish, and when."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_shorts as ps  # noqa: E402

SCHED = {"publish_at": "2026-10-18T10:00:00Z", "shorts_slots": ["2026-10-18T14:00:00Z", "2026-10-18T20:00:00Z", "2026-10-18T23:00:00Z"]}


def setup(tmp, approved=2, long_published=True, done=()):
    d = Path(tmp) / "pilot-002"
    (d / "shorts").mkdir(parents=True)
    (d / "out").mkdir()
    (d / "out" / "manifest.json").write_text(json.dumps({"output_sha256": "abc"}))
    (d / "schedule.json").write_text(json.dumps(SCHED))
    shorts = [{"file": f"short-0{i}.mp4", "sha256": f"s{i}", "publish": i < approved, "review": {"status": "PASS" if i < approved else "FAIL", "model": "gemini-3.8-flash"}}
              for i in range(4)]
    (d / "shorts" / "shorts.json").write_text(json.dumps({"source_pilot": "pilot-002", "shorts": shorts}))
    entries = {"pilot-002:abc": {"video_id": "L"}} if long_published else {}
    entries.update({f"short:pilot-002:{s}": {"video_id": "x"} for s in done})
    return Path(tmp), {"entries": entries}


class Pending(unittest.TestCase):
    def test_uses_schedule_slots_while_ahead(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t)
            self.assertEqual(ps.pending(prod, ledger, datetime(2026, 10, 18, 7, 35, tzinfo=timezone.utc)),
                             ("pilot-002", ["2026-10-18T14:00:00Z", "2026-10-18T20:00:00Z"]))

    def test_late_slots_roll_forward(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, approved=3)
            self.assertEqual(ps.pending(prod, ledger, datetime(2026, 10, 18, 19, 50, tzinfo=timezone.utc))[1],
                             ["2026-10-18T23:00:00Z", "2026-10-19T14:00:00Z", "2026-10-19T20:00:00Z"])

    def test_nothing_when_long_unpublished_or_all_done(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, long_published=False)
            self.assertIsNone(ps.pending(prod, ledger))
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, done=("s0", "s1"))
            self.assertIsNone(ps.pending(prod, ledger))


if __name__ == "__main__":
    unittest.main()
