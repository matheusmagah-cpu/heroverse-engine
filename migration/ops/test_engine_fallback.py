#!/usr/bin/env python3
"""Offline: E57 engine render fallback when the runner cannot be woken."""
from datetime import timedelta
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'production'))
import engine_fallback as f
from test_render_queue import pilot, NOW

ROOT = Path(__file__).resolve().parents[2]


def run(status='completed', age=60):
    return {'status': status, 'event': 'workflow_dispatch', 'created_at': (NOW - timedelta(minutes=age)).isoformat()}


class FakeAPI:
    def __init__(self, token, runs=()):
        self.history, self.sent = list(runs), []

    def runs(self):
        return self.history

    def dispatch(self, pilot):
        self.sent.append(pilot)


class Fallback(unittest.TestCase):
    def test_decision(self):
        self.assertEqual(f.decision([run('in_progress', 2000)], NOW), 'ENGINE_RENDER_ACTIVE')
        self.assertEqual(f.decision([run()] * f.DAILY_CAP, NOW), 'ENGINE_DAILY_CAP')
        self.assertEqual(f.decision([run(age=2000)] * f.DAILY_CAP, NOW), 'DISPATCH')
        self.assertEqual(f.decision([], NOW), 'DISPATCH')

    def test_dispatches_the_first_due_unrendered_pilot_with_images(self):
        with tempfile.TemporaryDirectory() as t:
            pilot(t, 'pilot-001', '2026-10-19T10:00:00Z', images_done=False)
            pilot(t, 'pilot-002', '2026-10-19T12:00:00Z', rendered=True)
            pilot(t, 'pilot-003', '2026-10-19T14:00:00Z')
            ledger = Path(t) / 'ledger.json'
            ledger.write_text('{"entries": {}}')
            api = FakeAPI('x')
            self.assertEqual(f.execute(t, ledger, 'x', NOW, lambda _: api, runner_runs=lambda: []), 'ENGINE_DISPATCH_ACCEPTED pilot-003')
            self.assertEqual(api.sent, ['pilot-003'])
            busy = FakeAPI('x', [run('queued')])
            self.assertEqual(f.execute(t, ledger, 'x', NOW, lambda _: busy, runner_runs=lambda: []), 'ENGINE_RENDER_ACTIVE')
            self.assertEqual(busy.sent, [])

    def test_never_renders_beside_a_live_runner(self):
        # E63: the runner rendered pilot-009 on its own cron (run 40042851661) while the fallback started a second
        # render of the same pilot on the engine (run 40047808539)
        with tempfile.TemporaryDirectory() as t:
            pilot(t, 'pilot-003', '2026-10-19T14:00:00Z')
            ledger = Path(t) / 'ledger.json'
            ledger.write_text('{"entries": {}}')
            for runner, verdict in (([{'status': 'in_progress', 'created_at': (NOW - timedelta(hours=3)).isoformat()}], 'RUNNER_ALIVE_RENDERS_IT'),
                                    ([run('completed', 30)], 'RUNNER_ALIVE_RENDERS_IT'),
                                    (None, 'RUNNER_STATE_UNKNOWN')):
                api = FakeAPI('x')
                self.assertEqual(f.execute(t, ledger, 'x', NOW, lambda _: api, runner_runs=lambda r=runner: r), verdict)
                self.assertEqual(api.sent, [])
            api = FakeAPI('x')
            self.assertTrue(f.execute(t, ledger, 'x', NOW, lambda _: api, runner_runs=lambda: [run('completed', 600)])
                            .startswith('ENGINE_DISPATCH_ACCEPTED'))

    def test_heartbeat_falls_back_to_the_engine_when_the_runner_token_is_rejected(self):
        # E57: HERO_RUNNER_PAT returned 401 on every heartbeat (runs 39964015145, 40005305507) and nothing rendered
        wf = (ROOT / '.github/workflows/heartbeat.yml').read_text()
        job = wf[wf.index('  runner-wake:'):]
        self.assertIn('actions: write', job)
        self.assertIn('migration/ops/engine_fallback.py', job)
        for status in f.FALLBACK_FOR:
            self.assertIn(status, job)
        self.assertTrue(re.search(r'GITHUB_TOKEN: \$\{\{ github.token \}\}', job))


if __name__ == '__main__':
    unittest.main()
