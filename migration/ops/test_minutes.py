#!/usr/bin/env python3
"""Offline checks of the Actions minutes report."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import minutes as m  # noqa: E402

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def run(name, created, started, updated, conclusion="success"):
    return {"name": name, "created_at": created, "run_started_at": started, "updated_at": updated,
            "status": "completed", "conclusion": conclusion}


class Minutes(unittest.TestCase):
    def test_rounding_windows_and_alerts(self):
        runs = [run("approve", "2026-10-20T08:00:00Z", "2026-10-20T08:00:00Z", "2026-10-20T08:14:10Z"),   # 15 min
                run("heartbeat", "2026-10-20T09:00:00Z", "2026-10-20T09:00:00Z", "2026-10-20T09:00:20Z"),  # 1 min
                run("old", "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z", "2026-09-01T02:00:00Z"),        # outside 30 d
                {**run("q", "2026-10-20T10:00:00Z", None, "2026-10-20T10:00:00Z"), "run_started_at": None}]  # never ran
        s = m.summary(runs, NOW)
        self.assertEqual(s["windows"], {"24h": 16, "7d": 16, "30d": 16})
        self.assertEqual(s["alerts"], [])
        heavy = [run("x", "2026-10-20T0%d:00:00Z" % h, "2026-10-20T0%d:00:00Z" % h, "2026-10-20T0%d:59:00Z" % h) for h in range(1, 7)]
        self.assertTrue(any(a.startswith("last 24 h") for a in m.summary(heavy, NOW)["alerts"]))   # 354 min > 1.5 x 233


if __name__ == "__main__":
    unittest.main()
