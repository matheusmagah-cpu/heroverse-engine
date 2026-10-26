#!/usr/bin/env python3
"""Offline checks of the long runway: Bible-story longs only, one every other day at 10:00 UTC (owner, 2026-10-26)."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "production"))
import runway as r  # noqa: E402
from test_script_check import structured_story  # noqa: E402  (a script on the registered beat map)

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
PRAYER = "migration/strategy/FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md"


def pilot(prod, name, at, rendered=False, approved=False, script=None):
    d = prod / name
    (d / "out").mkdir(parents=True)
    (d / "inspection").mkdir()
    (d / "schedule.json").write_text(json.dumps({"publish_at": at}))
    (d / "script.json").write_text(json.dumps(structured_story() if script is None else script))
    if rendered:
        (d / "out" / "manifest.json").write_text("{}")
    if approved:
        (d / "inspection" / "APPROVAL.json").write_text("{}")


class Runway(unittest.TestCase):
    def test_slots_are_the_bible_story_long_cadence(self):
        got = r.slots(NOW)
        self.assertEqual([t.strftime("%d/%m %H:%M") for t in got], ["28/10 10:00", "30/10 10:00", "01/11 10:00"])
        self.assertEqual(r.slots(datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc))[0].strftime("%d/%m"), "30/10")
        self.assertTrue(all(b - a == timedelta(days=2) for a, b in zip(got, got[1:])))   # never 2+ days without
        self.assertNotIn(0, {t.hour for t in r.slots(NOW, 20)})                       # the night slots retired
        arcs = json.loads((Path(r.__file__).resolve().parents[1] / "production/bible/arcs.json").read_text())["arcs"]
        long_slots = [r.ts(a["long"]["slot"]) for a in arcs]
        self.assertEqual(long_slots, [t for t in r.slots(NOW, 30) if t <= long_slots[-1]])  # = SERIES.md calendar

    def test_every_slot_listed_and_gaps_alerted(self):
        # E15: every long slot of the next days is listed and a gap alerts; a prayer pilot never fills one (2026-10-26)
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-008", "2026-10-27T00:00:00Z", rendered=True, approved=True, script={"archetype": PRAYER})
            pilot(prod, "pilot-016", "2026-10-28T10:00:00Z", rendered=True, approved=True, script={"archetype": PRAYER})
            rows, alerts = r.check(prod, {}, NOW)
            self.assertEqual([x["slot"] for x in rows], ["2026-10-28T10:00Z", "2026-10-30T10:00Z", "2026-11-01T10:00Z"])
            self.assertEqual(rows[0], {"slot": "2026-10-28T10:00Z", "pilot": None, "stage": "missing", "late": True})
            self.assertTrue(any("2026-10-28 10:00" in a and "NO BIBLE-STORY LONG" in a for a in alerts))
            self.assertFalse(any("pilot-008" in a or "pilot-016" in a for a in alerts))

    def test_a_story_script_off_its_structure_is_not_a_written_long(self):
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            off = structured_story(burned_captions=True)
            pilot(prod, "pilot-015", "2026-10-28T10:00:00Z", script=off)                 # 46 h left, off-structure
            pilot(prod, "pilot-017", "2026-10-30T10:00:00Z")                             # 94 h, on the beat map
            rows, alerts = r.check(prod, {}, NOW)
            self.assertEqual([x["stage"] for x in rows[:2]], ["off-structure", "script"])
            self.assertTrue(any("pilot-015" in a and "off-structure" in a for a in alerts))
            self.assertFalse(any("pilot-017" in a for a in alerts))

    def test_approval_one_day_ahead(self):
        # E24: pilot-003 had 3 h between the quota reset and its slot and missed it on a provider error
        self.assertGreaterEqual(r.APPROVAL_LEAD, timedelta(hours=24))
        self.assertGreater(r.RENDER_LEAD, r.APPROVAL_LEAD)
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-015", "2026-10-28T10:00:00Z")                             # 30 h, script: render late
            pilot(prod, "pilot-017", "2026-10-30T10:00:00Z", rendered=True)              # 78 h, rendered: fine
            rows, alerts = r.check(prod, {}, datetime(2026, 10, 27, 4, 0, tzinfo=timezone.utc))
            self.assertTrue(any("pilot-015" in a and "'script'" in a for a in alerts))
            self.assertFalse(any("pilot-017" in a for a in alerts))
            alerts = r.check(prod, {}, datetime(2026, 10, 29, 14, 0, tzinfo=timezone.utc))[1]   # 20 h, not approved
            self.assertTrue(any("pilot-017" in a and "rendered" in a for a in alerts))

    def test_uploaded_counts(self):
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-015", "2026-10-28T10:00:00Z", rendered=True)
            rows = r.check(prod, {"entries": {"pilot-015:abc": {"video_id": "x"}}}, NOW)[0]
            self.assertEqual(rows[0], {"slot": "2026-10-28T10:00Z", "pilot": "pilot-015", "stage": "uploaded", "late": False})


if __name__ == "__main__":
    unittest.main()
