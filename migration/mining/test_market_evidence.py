#!/usr/bin/env python3
"""Offline checks: missing opinion is UNKNOWN, malformed INVALID, old STALE; the daily research budget."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import market_evidence as me  # noqa: E402

NOW = datetime(2026, 10, 18, 15, tzinfo=timezone.utc)


def opinion(**kw):
    o = {k: [] if k in ("calls", "comparables", "evidence_for", "evidence_against", "limitations") else "x" for k in me.REQUIRED}
    o.update({"data_as_of": "2026-10-18T09:20:09Z", "calls": [{"credits": 5}], **kw})
    return o


class Market(unittest.TestCase):
    def test_states(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "vidiq.json"
            self.assertEqual(me.summary(p, NOW)["status"], "UNKNOWN")
            p.write_text("{")
            self.assertEqual(me.summary(p, NOW)["status"], "INVALID")
            o = opinion(); del o["evidence_against"]
            p.write_text(json.dumps(o))
            self.assertEqual(me.summary(p, NOW)["status"], "INVALID")           # contrary evidence is mandatory
            p.write_text(json.dumps(opinion()))
            s = me.summary(p, NOW)
            self.assertEqual((s["status"], s["credits"]), ("KNOWN", 5))
            p.write_text(json.dumps(opinion(data_as_of="2026-09-01T00:00:00Z")))
            self.assertEqual(me.summary(p, NOW)["status"], "STALE")

    def test_daily_and_cycle_caps(self):
        led = {"calls": [{"date": "2026-10-19", "kind": "research", "count": 10, "credits": 50}]}
        self.assertFalse(me.budget(led, "2026-10-19")["may_call"])                 # 10 calls used today
        self.assertTrue(me.budget(led, "2026-10-20")["may_call"])
        led["calls"].append({"date": "2026-10-20", "kind": "research", "count": 40, "credits": 200, "approved_by_owner": True})
        self.assertTrue(me.budget(led, "2026-10-20")["may_call"])                  # announced and approved extra
        full = {"calls": [{"date": "2026-10-25", "kind": "research", "count": 1, "credits": 1998}]}
        self.assertFalse(me.budget(full, "2026-10-26")["may_call"])                # cycle cap
        self.assertTrue(me.budget({"calls": [{"date": "2026-10-20", "kind": "account", "credits": 0}]}, "2026-10-20")["may_call"])


if __name__ == "__main__":
    unittest.main()
