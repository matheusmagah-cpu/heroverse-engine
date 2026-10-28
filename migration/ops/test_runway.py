#!/usr/bin/env python3
"""Offline long runway checks: authoritative arc deadlines, plus the legacy cadence when no calendar exists."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "production"))
import runway as r  # noqa: E402
from test_script_check import structured_story  # noqa: E402  (a script on the registered beat map)

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
PRAYER = "migration/strategy/FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md"
REAL_CHECK = r.script_check.check


def pilot(prod, name, at, rendered=False, approved=False, script=None):
    d = prod / name
    (d / "out").mkdir(parents=True)
    (d / "inspection").mkdir()
    (d / "schedule.json").write_text(json.dumps({"publish_at": at}))
    (d / "script.json").write_text(script if isinstance(script, str) else json.dumps(structured_story() if script is None else script))
    if rendered:
        (d / "out" / "manifest.json").write_text("{}")
    if approved:
        (d / "inspection" / "APPROVAL.json").write_text("{}")


def structure_only(d, production=None):
    """Stands in for script_check.check in tests whose pilots carry only a script: the structure decides."""
    return r.script_check.structure_problems(json.loads((Path(d) / "script.json").read_text())), {}


class Runway(unittest.TestCase):
    def setUp(self):
        p = patch.object(r.script_check, "check", structure_only)
        p.start()
        self.addCleanup(p.stop)

    def test_slots_keep_the_legacy_cadence_when_no_calendar_is_supplied(self):
        got = r.slots(NOW)
        self.assertEqual([t.strftime("%d/%m %H:%M") for t in got], ["29/10 10:00", "31/10 10:00", "02/11 10:00"])
        self.assertEqual(r.slots(datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc))[0].strftime("%d/%m"), "31/10")
        self.assertTrue(all(b - a == timedelta(days=2) for a, b in zip(got, got[1:])))   # never 2+ days without
        self.assertNotIn(0, {t.hour for t in r.slots(NOW, 20)})                       # the night slots retired

    def test_e166_authoritative_arc_deadline_is_visible_until_upload_without_invented_pilot_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            prod = Path(temporary)
            bible = prod / "bible"
            (bible / "plans").mkdir(parents=True)
            (bible / "arcs.json").write_text(json.dumps({"arcs": [
                {"id": "arc-01", "long": {"pilot": "pilot-015", "slot": "2026-10-28T22:00:00Z"}},
                {"id": "arc-02", "long": {"pilot": None, "slot": "2026-10-31T10:00:00Z"}}
            ]}))
            (bible / "plans/arc-01-long.json").write_text(json.dumps({"version": "bible-long-plan-v1",
                                                                      "episode": "arc-01-long"}))
            for at in ("2026-10-28T14:00:00Z", "2026-10-28T22:00:00Z", "2026-10-29T00:01:00Z"):
                with self.subTest(at=at):
                    rows, alerts = r.check(prod, {}, r.ts(at))
                    self.assertEqual([row["slot"] for row in rows], ["2026-10-28T22:00Z", "2026-10-31T10:00Z"])
                    self.assertEqual(rows[0]["pilot"], "arc-01-long")
                    self.assertEqual(rows[0]["stage"], "planned")
                    self.assertTrue(rows[0]["late"])
                    self.assertTrue(any("arc-01-long" in alert for alert in alerts))
            ledger = {"entries": {"bible:arc-01-long:" + "a" * 64: {"video_id": "confirmed-video"}}}
            rows, _ = r.check(prod, ledger, r.ts("2026-10-29T00:01:00Z"))
            self.assertEqual([row["slot"] for row in rows], ["2026-10-31T10:00Z"])

    def test_invalid_arc_calendar_is_reported_instead_of_replaced_by_a_different_deadline(self):
        with tempfile.TemporaryDirectory() as temporary:
            prod = Path(temporary)
            (prod / "bible").mkdir()
            (prod / "bible/arcs.json").write_text('{"arcs":[{"id":"arc-01","long":{"slot":"not-a-date"}}]}')
            rows, alerts = r.check(prod, {}, NOW)
            self.assertEqual(rows, [])
            self.assertTrue(any("LONG_CALENDAR_INVALID" in alert for alert in alerts))

    def test_every_slot_listed_and_gaps_alerted(self):
        # E15: every long slot of the next days is listed and a gap alerts; a prayer pilot never fills one (2026-10-26)
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-016", "2026-10-29T10:00:00Z", rendered=True, approved=True, script={"archetype": PRAYER})
            rows, alerts = r.check(prod, {}, NOW)
            self.assertEqual([x["slot"] for x in rows], ["2026-10-29T10:00Z", "2026-10-31T10:00Z", "2026-11-02T10:00Z"])
            self.assertEqual(rows[0], {"slot": "2026-10-29T10:00Z", "pilot": None, "stage": "missing", "late": True})
            self.assertTrue(any("2026-10-29 10:00" in a and "NO BIBLE-STORY LONG" in a for a in alerts))

    def test_a_scheduled_prayer_long_alerts_instead_of_dropping_out(self):
        # review of #415: a forgotten prayer schedule.json must be seen, not silently skipped
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-008", "2026-10-28T00:00:00Z", rendered=True, approved=True, script={"archetype": PRAYER})
            pilot(prod, "pilot-013", "2026-10-27T00:00:00Z", rendered=True, script={"archetype": PRAYER})  # passed
            alerts = r.check(prod, {"entries": {"pilot-008:a": {"video_id": "8heTdP0LllM"}}}, NOW)[1]
            self.assertIn("PRAYER_LONG_SCHEDULED pilot-008 at 2026-10-28 00:00 UTC (uploaded; prayer longs stopped "
                          "2026-10-26: hold the upload with channel-privacy.yml unschedule and retire its schedule.json)",
                          alerts)
            self.assertFalse(any("pilot-013" in a for a in alerts))

    def test_a_story_script_counts_only_when_the_full_script_check_passes(self):
        # review of #415: structure alone is not enough; the whole script_check decides "script"
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-015", "2026-10-29T10:00:00Z")                             # on the beat map
            self.assertEqual(r.long_stage(prod / "pilot-015", {}), ("script", []))
            with patch.object(r.script_check, "check", lambda d, p=None: (["MISSING images.json"], {})):
                self.assertEqual(r.long_stage(prod / "pilot-015", {}), ("script-fail", ["MISSING images.json"]))
                rows, alerts = r.check(prod, {}, NOW)
            self.assertEqual(rows[0]["stage"], "script-fail")
            self.assertTrue(any("pilot-015" in a and "script-fail" in a for a in alerts))
        with tempfile.TemporaryDirectory() as t, patch.object(r.script_check, "check", REAL_CHECK):   # no stub
            prod = Path(t)
            pilot(prod, "pilot-015", "2026-10-29T10:00:00Z")
            st, problems = r.long_stage(prod / "pilot-015", {})
            self.assertEqual(st, "script-fail")
            self.assertIn("MISSING images.json", problems)

    def test_off_structure_and_unreadable_scripts_fail_without_crashing(self):
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-015", "2026-10-29T10:00:00Z", script=structured_story(burned_captions=True))
            pilot(prod, "pilot-017", "2026-10-31T10:00:00Z", script="{not json")
            st, problems = r.long_stage(prod / "pilot-015", {})
            self.assertEqual(st, "script-fail")
            self.assertTrue(any(p.startswith("STORY_BURNED_CAPTIONS") for p in problems))
            self.assertEqual(r.long_stage(prod / "pilot-017", {})[0], "script-fail")
            r.check(prod, {}, NOW)                                                      # no exception

    def test_a_rendered_approved_or_uploaded_long_keeps_its_stage(self):
        # review of #415: a long past the script stage never drops out because of later gate fields
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            off = structured_story(burned_captions=True)
            pilot(prod, "pilot-015", "2026-10-29T10:00:00Z", rendered=True, script=off)
            pilot(prod, "pilot-017", "2026-10-31T10:00:00Z", rendered=True, approved=True, script=off)
            pilot(prod, "pilot-019", "2026-11-02T10:00:00Z", script=off)
            ledger = {"entries": {"pilot-019:abc": {"video_id": "x"}}}
            self.assertEqual([x["stage"] for x in r.check(prod, ledger, NOW)[0]], ["rendered", "approved", "uploaded"])

    def test_approval_one_day_ahead(self):
        # E24: pilot-003 had 3 h between the quota reset and its slot and missed it on a provider error
        self.assertGreaterEqual(r.APPROVAL_LEAD, timedelta(hours=24))
        self.assertGreater(r.RENDER_LEAD, r.APPROVAL_LEAD)
        with tempfile.TemporaryDirectory() as t:
            prod = Path(t)
            pilot(prod, "pilot-015", "2026-10-29T10:00:00Z")                             # 30 h, script: render late
            pilot(prod, "pilot-017", "2026-10-31T10:00:00Z", rendered=True)              # 78 h, rendered: fine
            rows, alerts = r.check(prod, {}, datetime(2026, 10, 28, 4, 0, tzinfo=timezone.utc))
            self.assertTrue(any("pilot-015" in a and "'script'" in a for a in alerts))
            self.assertFalse(any("pilot-017" in a for a in alerts))
            alerts = r.check(prod, {}, datetime(2026, 10, 30, 14, 0, tzinfo=timezone.utc))[1]   # 20 h, not approved
            self.assertTrue(any("pilot-017" in a and "rendered" in a for a in alerts))


if __name__ == "__main__":
    unittest.main()
