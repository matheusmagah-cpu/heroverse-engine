#!/usr/bin/env python3
"""Offline checks of the Shorts slot rule: which approved Shorts are still to publish, and when (E01/E02).
The pilot-006 recovery and correction cases left with the prayer Shorts line (slim audit 2026-10-28)."""
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
    shorts = [{"file": f"short-0{i}.mp4", "sha256": f"{i:064x}", "publish": i < approved, "review": {"status": "PASS" if i < approved else "FAIL", "model": "gemini-3.8-flash", "overall": 9.6, "output_sha256": f"{i:064x}"}, "qa": {"status": "PASS"}}
              for i in range(4)]
    (d / "shorts" / "shorts.json").write_text(json.dumps({"source_pilot": "pilot-002", "shorts": shorts}))
    entries = {"pilot-002:abc": {"video_id": "L"}} if long_published else {}
    entries.update({f"short:pilot-002:{s}": {"video_id": "x"} for s in done})
    return Path(tmp), {"entries": entries}


class Pending(unittest.TestCase):
    def test_policy_block_is_distinct_and_false_cache_cannot_override(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, approved=1)
            path = prod / "pilot-002/shorts/shorts.json"
            spec = json.loads(path.read_text())
            rec = spec["shorts"][0]
            rec["review"]["overall"] = 8.5
            rec["owner_quality_policy"] = {"status": "PASS"}
            path.write_text(json.dumps(spec))
            self.assertIsNone(ps.pending(prod, ledger))
            self.assertEqual(ps.states(prod / "pilot-002", ledger)[0]["state"], "owner_quality_policy_blocked")
            self.assertEqual(ps.todo_files(prod / "pilot-002", ledger), [])
            ledger["entries"]["short:pilot-002:" + rec["sha256"]] = {"video_id": "EXISTING"}
            self.assertEqual(ps.states(prod / "pilot-002", ledger)[0]["state"], "published")

    def test_truthy_publish_or_qa_failure_never_qualifies(self):
        record = {"publish": True, "sha256": "a" * 64, "qa": {"status": "PASS"},
                  "review": {"status": "PASS", "model": "gemini-3.8-flash", "overall": 9.5, "output_sha256": "a" * 64}}
        self.assertTrue(ps.approved(record))
        record["publish"] = 1
        self.assertFalse(ps.approved(record))
        record["publish"] = True
        record["qa"]["status"] = "FAIL"
        self.assertFalse(ps.approved(record))

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

    def test_late_short_never_takes_another_pilots_slot(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, approved=1)
            other = prod / "pilot-003"; other.mkdir()
            (other / "schedule.json").write_text(json.dumps({"publish_at": "2026-10-18T10:00:00Z",
                                                             "shorts_slots": ["2026-10-18T20:00:00Z"]}))
            ledger["entries"]["short:pilot-001:z"] = {"video_id": "y", "slot": "2026-10-18T23:00:00Z"}
            # missed its 14:00 slot (run at 14:11): 20:00 is pilot-003's, 23:00 is already used -> next free slot
            self.assertEqual(ps.pending(prod, ledger, datetime(2026, 10, 18, 14, 11, tzinfo=timezone.utc))[1],
                             ["2026-10-19T14:00:00Z"])

    def test_nothing_when_long_unpublished_or_all_done(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, long_published=False)
            self.assertIsNone(ps.pending(prod, ledger))
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, done=(f"{0:064x}", f"{1:064x}"))
            self.assertIsNone(ps.pending(prod, ledger))


class RetiredPrayerLongs(unittest.TestCase):
    def test_no_short_of_a_prayer_long_is_published(self):
        # owner, 2026-10-26: "stop the prayer videos"; a Bible-story long's approved Shorts still go out
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t)
            script = prod / "pilot-002" / "script.json"
            script.write_text(json.dumps({"archetype": "migration/strategy/FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md"}))
            self.assertIsNone(ps.pending(prod, ledger, ps.when("2026-10-18T09:00:00Z")))
            script.write_text(json.dumps({"archetype": "bible-story-long"}))
            self.assertEqual(ps.pending(prod, ledger, ps.when("2026-10-18T09:00:00Z"))[0], "pilot-002")


if __name__ == "__main__":
    unittest.main()
