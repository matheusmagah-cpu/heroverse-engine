#!/usr/bin/env python3
"""Offline checks of the scheduler's decisions."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import heartbeat as hb  # noqa: E402

ALL = {"images_missing": True, "reconcile_todo": True, "shorts_pending": True, "production_idle": True}


def t(h, m=0, day=18):
    return datetime(2026, 10, day, h, m, tzinfo=timezone.utc)  # 2026-10-18 is a Sunday


def run(h, m, status="completed", conclusion="success", day=18):
    iso = t(h, m, day).isoformat()
    return {"createdAt": iso, "updatedAt": iso, "status": status, "conclusion": conclusion}


class Heartbeat(unittest.TestCase):
    def test_dropped_crons_are_caught_up(self):
        # 2026-10-18 09:41: nothing ran since midnight -> every passed daily task is dispatched once
        got = hb.decide({}, ALL, t(9, 41))
        for w in ("mining-accuracy.yml", "nightly-images.yml", "market-panel.yml", "reconcile.yml",
                  "publish-shorts.yml", "packaging-mining.yml", "channel-privacy.yml", "structure-mining.yml"):
            self.assertIn(w, got)
        self.assertIn("goal-report.yml", got)          # past wait_max: no longer waits for the panel

    def test_nothing_twice_after_a_run(self):
        runs = {"market-panel.yml": [run(7, 30)], "channel-privacy.yml": [run(8, 10)]}
        got = hb.decide(runs, ALL, t(8, 41))
        self.assertNotIn("market-panel.yml", got)
        self.assertNotIn("channel-privacy.yml", got)

    def test_failed_run_retried_once_after_a_pause(self):
        failed = {"market-panel.yml": [run(7, 30, conclusion="failure")]}
        self.assertNotIn("market-panel.yml", hb.decide(failed, ALL, t(7, 41)))     # too soon
        self.assertIn("market-panel.yml", hb.decide(failed, ALL, t(8, 41)))        # retry
        twice = {"market-panel.yml": [run(7, 30, conclusion="failure"), run(8, 41, conclusion="failure")]}
        self.assertNotIn("market-panel.yml", hb.decide(twice, ALL, t(10, 11)))    # attempts used up

    def test_in_progress_is_not_duplicated(self):
        runs = {"structure-mining.yml": [run(8, 41, status="in_progress", conclusion=None)]}
        self.assertNotIn("structure-mining.yml", hb.decide(runs, ALL, t(10, 11)))

    def test_conditions_keep_idle_tasks_quiet(self):
        idle = {"images_missing": False, "reconcile_todo": False, "shorts_pending": False, "production_idle": True}
        got = hb.decide({}, idle, t(9, 41))
        self.assertFalse({"nightly-images.yml", "reconcile.yml", "publish-shorts.yml"} & set(got))

    def test_minings_wait_for_production_and_stay_due(self):
        busy = dict(ALL, production_idle=False)
        got = hb.decide({}, busy, t(9, 41))
        self.assertFalse({"structure-mining.yml", "packaging-mining.yml"} & set(got))
        self.assertIn("structure-mining.yml", hb.decide({}, ALL, t(15, 11)))      # still due once idle

    def test_each_slot_is_its_own_window(self):
        runs = {"reconcile.yml": [run(7, 25)]}
        self.assertNotIn("reconcile.yml", hb.decide(runs, ALL, t(9, 41)))
        self.assertIn("reconcile.yml", hb.decide(runs, ALL, t(10, 41)))            # 10:20 slot

    def test_report_waits_for_the_panel(self):
        self.assertNotIn("goal-report.yml", hb.decide({}, ALL, t(7, 50)))
        self.assertIn("goal-report.yml", hb.decide({"market-panel.yml": [run(7, 20)]}, ALL, t(7, 50)))
        busy = {"market-panel.yml": [run(7, 20, status="in_progress", conclusion=None)]}
        self.assertNotIn("goal-report.yml", hb.decide(busy, ALL, t(7, 50)))

    def test_weekly_task_only_on_its_day(self):
        self.assertIn("packaging-mining.yml", hb.decide({}, ALL, t(8, 11)))         # Sunday
        self.assertNotIn("packaging-mining.yml", hb.decide({}, ALL, t(8, 11, day=19)))

    def test_before_the_first_slot_nothing(self):
        self.assertEqual(hb.decide({}, ALL, t(0, 11)), [])

    def test_yesterdays_runs_do_not_count(self):
        runs = {"market-panel.yml": [run(7, 30, day=17)]}
        self.assertIn("market-panel.yml", hb.decide(runs, ALL, t(7, 41)))


class Health(unittest.TestCase):
    def test_missed_and_stale_heartbeat(self):
        import health
        runs = {"market-panel.yml": [run(7, 30)], "heartbeat.yml": [run(6, 11)], "runner": [run(9, 13)]}
        rows, alerts = health.check(runs, t(12, 0))
        text = " ".join(alerts)
        self.assertIn("channel-privacy.yml", text)           # 08:05 slot, nothing since, > 3 h
        self.assertNotIn("market-panel.yml", text)
        self.assertNotIn("reconcile.yml", text)              # conditional: not judged from history
        self.assertIn("heartbeat.yml", text)                 # last beat 6 h ago
        self.assertNotIn("runner", text)


if __name__ == "__main__":
    unittest.main()
