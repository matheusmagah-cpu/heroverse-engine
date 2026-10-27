#!/usr/bin/env python3
"""E08 / E86 / E90 class (E115 sweep): GitHub drops and delays cron triggers, so only heartbeat.yml may rely on a
schedule. Every other workflow with a `schedule:` trigger must also be dispatched by the heartbeat
(ops/heartbeat.py SLOTS), so a dropped cron never leaves it unrun."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def scheduled(text):
    on = re.search(r"^on:\s*\n((?:[ \t]+.*\n|\s*\n)*)", text, re.M)
    return bool(on and re.search(r"^\s+schedule:", on.group(1), re.M))


def dispatched_by_heartbeat():
    return set(re.findall(r'"workflow":\s*"([a-z0-9-]+\.yml)"', (ROOT / "migration/ops/heartbeat.py").read_text()))


class Schedules(unittest.TestCase):
    def test_only_heartbeat_relies_on_a_cron_schedule(self):
        beat = dispatched_by_heartbeat()
        crons = [wf.name for wf in sorted(WORKFLOWS.glob("*.yml")) if scheduled(wf.read_text())]
        self.assertIn("heartbeat.yml", crons)
        for name in crons:
            if name == "heartbeat.yml":
                continue
            self.assertIn(name, beat, f"{name} relies on cron: dispatch it from ops/heartbeat.py too (E08, E86, E90)")
            self.assertIn("workflow_dispatch", (WORKFLOWS / name).read_text(), f"{name}: the heartbeat cannot dispatch it")

    def test_the_parser_sees_a_schedule(self):
        self.assertTrue(scheduled("name: x\non:\n  schedule:\n    - cron: '0 * * * *'\n  workflow_dispatch:\njobs:\n"))
        self.assertFalse(scheduled("name: x\non:\n  workflow_dispatch:\njobs:\n  a:\n    schedule: no\n"))


if __name__ == "__main__":
    unittest.main()
