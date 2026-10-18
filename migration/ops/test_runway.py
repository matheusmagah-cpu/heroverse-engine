#!/usr/bin/env python3
"""Offline checks of the content runway."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runway as r  # noqa: E402

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)


def pilot(prod, name, at, rendered=False, approved=False):
    d = prod / name
    (d / "out").mkdir(parents=True)
    (d / "inspection").mkdir()
    (d / "schedule.json").write_text(json.dumps({"publish_at": at}))
    if rendered:
        (d / "out" / "manifest.json").write_text("{}")
    if approved:
        (d / "inspection" / "APPROVAL.json").write_text("{}")


class Runway(unittest.TestCase):
    def test_every_slot_listed_and_gaps_alerted(self):
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-008", "2026-10-22T00:00:00Z", rendered=True, approved=True)
            pilot(prod, "pilot-009", "2026-10-22T10:00:00Z", rendered=True)         # 22 h left, not approved yet: fine
            pilot(prod, "pilot-010", "2026-10-23T00:00:00Z")                        # 36 h left, script only: fine
            rows, alerts = r.check(prod, {}, NOW)
            self.assertEqual(len(rows), 8)                                          # 4 days x 2 slots
            self.assertEqual([x["stage"] for x in rows[:3]], ["approved", "rendered", "script"])
            self.assertTrue(any("2026-10-23 10:00" in a and "NO PILOT" in a for a in alerts))  # 46 h, no script
            self.assertFalse(any("pilot-009" in a or "pilot-010" in a for a in alerts))

    def test_late_render_and_late_approval(self):
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-008", "2026-10-22T00:00:00Z", rendered=True)         # 12 h left, still not approved
            pilot(prod, "pilot-009", "2026-10-22T10:00:00Z")                        # 22 h... script only
            alerts = r.check(prod, {}, datetime(2026, 10, 21, 19, 0, tzinfo=timezone.utc))[1]
            self.assertTrue(any("pilot-008" in a and "rendered" in a for a in alerts))
            self.assertTrue(any("pilot-009" in a and "script" in a for a in alerts))

    def test_uploaded_counts_and_format_start(self):
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-003", "2026-10-19T10:00:00Z", rendered=True)
            rows = r.check(prod, {"entries": {"pilot-003:abc": {"video_id": "x"}}}, datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc))[0]
            self.assertEqual(rows[0], {"slot": "2026-10-19T10:00Z", "pilot": "pilot-003", "stage": "uploaded", "late": False})
            self.assertNotIn("2026-10-19T00:00Z", [x["slot"] for x in rows])       # before the two-a-day format


if __name__ == "__main__":
    unittest.main()
