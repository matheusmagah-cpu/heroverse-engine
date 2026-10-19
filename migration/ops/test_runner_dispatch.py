#!/usr/bin/env python3
"""Offline tests. No credentials, network, render, or dispatch required."""
from datetime import timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'production'))
import runner_dispatch as d
from test_render_queue import pilot, NOW


def run(age=60, status='completed', key='key', event='workflow_dispatch'):
    at = (NOW - timedelta(minutes=age)).isoformat()
    return {'created_at': at, 'updated_at': at, 'status': status,
            'display_title': d.PREFIX + key, 'event': event}


class Dispatch(unittest.TestCase):
    def test_active_any_age(self):
        for status in d.ACTIVE + ('unknown_future_status',):
            self.assertEqual(d.decision('key', [run(2000, status)], NOW), 'RUNNER_ACTIVE')

    def test_cooldown_dedupe_and_limit_per_artifact(self):
        self.assertEqual(d.decision('key', [run(10)], NOW), 'COOLDOWN')
        self.assertEqual(d.decision('key', [run(60)] * 3, NOW), 'RETRY_LIMIT')
        self.assertEqual(d.decision('new', [run(60)] * 3, NOW), 'DISPATCH')
        self.assertEqual(d.decision('key', [run(60)], NOW), 'DISPATCH')
        self.assertEqual(d.decision('key', [run(1500)] * 3, NOW), 'DISPATCH')

    def test_cron_settle_without_global_daily_cap(self):
        self.assertEqual(d.decision('key', [run(2, event='schedule')], NOW), 'SETTLING')
        self.assertEqual(d.decision('key', [run(60, event='schedule')] * 48, NOW), 'DISPATCH')

    def test_empty_images_manifest_and_script_change(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertIsNone(d.candidate(t, {}, NOW))
            pilot(t, 'pilot-001', '2026-10-19T10:00:00Z', images_done=False)
            self.assertIsNone(d.candidate(t, {}, NOW))
            pilot(t, 'pilot-002', '2026-10-19T10:00:00Z', rendered=True)
            self.assertIsNone(d.candidate(t, {}, NOW))
            p = Path(t) / 'pilot-002' / 'script.json'
            p.write_text(p.read_text() + '\n')
            key = d.candidate(t, {}, NOW)
            self.assertEqual(len(key), 64)
            self.assertNotIn('pilot', key)

    def test_missing_token_fails_even_when_empty(self):
        with self.assertRaisesRegex(d.Blocked, 'MISSING_HERO_RUNNER_PAT'):
            d.execute('unused', 'unused', '', NOW)

    def test_api_auth_failure_timeout_and_invalid_json(self):
        for error in [HTTPError('url', 401, 'error', {}, None),
                      HTTPError('url', 403, 'error', {}, None), URLError('offline'), ValueError('bad JSON')]:
            with patch.object(d, 'urlopen', side_effect=error) as call:
                with self.assertRaises(d.Blocked):
                    d.GitHub('fake-offline-token').runs(NOW)
                self.assertEqual(call.call_count, 1)

    def test_dispatch_contract_no_pilot_and_no_retry(self):
        api = d.GitHub('fake-offline-token')
        with patch.object(api, 'request') as request:
            api.dispatch('key')
            self.assertEqual(request.call_args.args[1], {'ref': 'main', 'inputs': {'dispatch_key': 'key'}})
        with patch.object(d, 'urlopen', side_effect=URLError('uncertain')) as call:
            with self.assertRaises(d.Blocked):
                api.dispatch('key')
            self.assertEqual(call.call_count, 1)

    def test_active_query_short_circuits_and_pagination_fail_closed(self):
        api = d.GitHub('fake-offline-token')
        with patch.object(api, 'request', return_value={'total_count': 1, 'workflow_runs': [run()]}):
            self.assertEqual(api.runs(NOW), [{'status': 'queued'}])
        responses = [{'total_count': 0, 'workflow_runs': []}] * len(d.ACTIVE)
        responses += [{'total_count': 1001, 'workflow_runs': [run()] * 100}] * 10
        with patch.object(api, 'request', side_effect=responses):
            with self.assertRaisesRegex(d.Blocked, 'INCOMPLETE_RUN_HISTORY'):
                api.runs(NOW)

    def test_malformed_pages_and_metadata_fail_closed(self):
        for page in (None, [], {}, {'total_count': True, 'workflow_runs': []},
                     {'total_count': -1, 'workflow_runs': []},
                     {'total_count': 0, 'workflow_runs': [run()]}):
            with self.assertRaises(d.Blocked):
                d.history_page(page)
        for field in ('event', 'display_title', 'status', 'created_at', 'updated_at'):
            row = run()
            del row[field]
            api = d.GitHub('fake-offline-token')
            responses = [{'total_count': 0, 'workflow_runs': []}] * len(d.ACTIVE)
            responses += [{'total_count': 1, 'workflow_runs': [row]}]
            with patch.object(api, 'request', side_effect=responses):
                with self.assertRaisesRegex(d.Blocked, 'INVALID_RUN_METADATA'):
                    api.runs(NOW)
        for row in (None, {}, dict(run(), event=42), dict(run(), updated_at='invalid')):
            with self.assertRaises(d.Blocked):
                d.validate_run(row)

    def test_execute_empty_active_dispatch_and_api_error(self):
        with tempfile.TemporaryDirectory() as t:
            ledger = Path(t) / 'ledger.json'
            ledger.write_text('{}')
            with patch.object(d, 'GitHub') as cls:
                api = cls.return_value
                self.assertEqual(d.execute(t, ledger, 'fake', NOW, cls), 'QUEUE_EMPTY')
                api.runs.assert_not_called()
                pilot(t, 'pilot-001', '2026-10-19T10:00:00Z')
                api.runs.return_value = [{'status': 'queued'}]
                self.assertEqual(d.execute(t, ledger, 'fake', NOW, cls), 'RUNNER_ACTIVE')
                api.dispatch.assert_not_called()
                api.runs.return_value = []
                self.assertEqual(d.execute(t, ledger, 'fake', NOW, cls), 'DISPATCH_ACCEPTED')
                api.dispatch.assert_called_once()
                api.dispatch.reset_mock()
                api.runs.side_effect = d.Blocked('API_HTTP_403')
                with self.assertRaises(d.Blocked):
                    d.execute(t, ledger, 'fake', NOW, cls)
                api.dispatch.assert_not_called()

    def test_workflow_isolated_job_and_existing_cron(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / '.github/workflows/heartbeat.yml').read_text()
        self.assertIn("cron: '41 * * * *'", workflow)   # hourly + the Claude clock at :14 (minutes budget, 2026-10-19)
        self.assertIn('  runner-wake:\n', workflow)
        wake = workflow.split('  runner-wake:\n')[1]
        self.assertNotIn('needs:', wake)
        self.assertNotIn('GH_TOKEN:', wake)
        self.assertIn('HERO_RUNNER_PAT: ${{ secrets.HERO_RUNNER_PAT }}', wake)
        self.assertIn('cancel-in-progress: false', workflow)


if __name__ == '__main__':
    unittest.main()
