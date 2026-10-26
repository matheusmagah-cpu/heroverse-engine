#!/usr/bin/env python3
"""Offline checks of the Actions minutes report: a speed measure (public repo, standard runners free; E102). The CI
speedups found while measuring it are checked in migration/ci/test_ci_setup.py."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import minutes as m  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github/workflows"
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def run(name, created, started, updated, conclusion="success"):
    return {"name": name, "created_at": created, "run_started_at": started, "updated_at": updated,
            "status": "completed", "conclusion": conclusion}


class Minutes(unittest.TestCase):
    def test_rounding_windows_and_alerts(self):
        # E21's antidote, kept: each run rounds up to a whole minute and lands in its windows. E102: no alerts any more
        runs = [run("approve", "2026-10-20T08:00:00Z", "2026-10-20T08:00:00Z", "2026-10-20T08:14:10Z"),   # 15 min
                run("heartbeat", "2026-10-20T09:00:00Z", "2026-10-20T09:00:00Z", "2026-10-20T09:00:20Z"),  # 1 min
                run("old", "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z", "2026-09-01T02:00:00Z"),        # outside 30 d
                {**run("q", "2026-10-20T10:00:00Z", None, "2026-10-20T10:00:00Z"), "run_started_at": None}]  # never ran
        s = m.summary(runs, NOW)
        self.assertEqual(s["windows"], {"24h": 16, "7d": 16, "30d": 16})
        self.assertEqual(s["top"][0], {"workflow": "approve", "minutes": 15, "runs": 1, "per_run": 15.0})
        self.assertNotIn("alerts", s)

    def test_report_is_a_speed_metric_with_no_budget_alarm(self):
        # E102: the engine is public and standard runners are free for public repos; the report said "private
        # engine; budget 7000 min / 30 days" and raised a spending alarm that did not exist
        heavy = [run("render", "2026-10-20T0%d:00:00Z" % h, "2026-10-20T0%d:00:00Z" % h, "2026-10-20T0%d:59:00Z" % h)
                 for h in range(1, 7)]                                      # 354 min in a day: no alarm
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "runs.json").write_text(json.dumps(heavy))
            m.main(str(Path(d) / "runs.json"), str(Path(d) / "report.md"), NOW.isoformat())
            report = (Path(d) / "report.md").read_text()
        self.assertIn("## Actions minutes (speed only; public repo: standard runners free)", report)
        self.assertIn("| render | 354 | 6 | 59.0 |", report)
        for word in ("budget", "overage", "projection", "\u26a0", "target"):
            self.assertNotIn(word, report.lower())
        source = (ROOT / "migration/ops/minutes.py").read_text()
        self.assertNotRegex(source, r"BUDGET\s*=|7000|overage alert")
        self.assertNotIn("minutes.py check", (WF / "heartbeat.yml").read_text())
        system = (ROOT / "migration/SYSTEM.md").read_text()
        self.assertNotIn("7000 / 30 days", system)
        self.assertIn("standard GitHub-hosted runners are free for public repositories", system)
        self.assertIn("public repo, standard runners free", (WF / "goal-report.yml").read_text())


if __name__ == "__main__":
    unittest.main()
