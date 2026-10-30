"""Offline Verified Security Sweep reproductions; only synthetic IDs/data and fake APIs."""
import json
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'migration/integrations/pavo'))
sys.path.insert(0, str(ROOT / 'migration/ops'))
import private_audio as bridge
import dispatch_guard as guard


class RecoveryGuard(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / bridge.MANIFESTS / 'genesis-09-k-close-20261030.json').read_text())
        self.inputs = {'plan': 'migration/production/bible/plans/genesis-09-short.json',
                       'manifest': bridge.MANIFESTS + 'genesis-09-k-close-20261030.json',
                       'sha256': bridge.digest(self.manifest), 'lease_run_id': 'synthetic-lease',
                       'reconcile_run': '9000000001'}

    def check_previous(self, conclusion, recover=True, workflow=bridge.WORKFLOW):
        inputs = dict(self.inputs)
        if not recover:
            inputs.pop('reconcile_run')
        facts = guard.private_audio(inputs)
        facts.update(subject=inputs['plan'], files=set())
        run = {'id': 9000000001, 'conclusion': conclusion, 'head_sha': 'a' * 40,
               'display_title': guard.run_name(workflow, inputs)}
        def api(path):
            if path.startswith('actions/workflows/'):
                return {'workflow_runs': [run]}
            if path.startswith('compare/'):
                return {'status': 'identical', 'files': []}
            raise AssertionError('unexpected API path: ' + path)
        with patch.object(guard, 'failed_in_guard', return_value=False), \
             patch.object(guard, 'recorded_retry', return_value=False), \
             patch.object(guard, 'depends_on', return_value=[inputs['manifest']]):
            return guard.rerun(workflow, facts, inputs, api, '9000000002', 1, 'a' * 40)

    def test_get_only_recovery_remains_available_after_failed_poll(self):
        # A failed UNKNOWN poll needs another history GET, never another generation.
        self.check_previous('failure')

    def test_generation_still_requires_fix_after_failed_run(self):
        with self.assertRaisesRegex(guard.Refusal, 'GUARD_RERUN_WITHOUT_FIX'):
            self.check_previous('failure', recover=False)

    def test_get_only_recovery_after_success_is_intact(self):
        self.check_previous('success')

    def test_recovery_exception_does_not_release_another_workflow(self):
        with self.assertRaisesRegex(guard.Refusal, 'GUARD_RERUN_WITHOUT_FIX'):
            self.check_previous('failure', workflow='shot-probe.yml')

    def test_malformed_recovery_is_refused_even_at_direct_guard_entry(self):
        inputs = dict(self.inputs, reconcile_run='invalid-run')
        with self.assertRaises(guard.Refusal):
            guard.rerun(bridge.WORKFLOW, {}, inputs, lambda p: {}, '9000000002', 1, 'a' * 40)


class LeaseGuard(unittest.TestCase):
    def test_only_matching_unexpired_active_lease_is_accepted(self):
        now = datetime.now(timezone.utc)
        record = {'state': 'active', 'owner': 'codex', 'run_id': 'synthetic-lease',
                  'expires_at': (now + timedelta(minutes=10)).isoformat()}
        for delta in ({}, {'run_id': 'other-lease'}, {'state': 'released'},
                      {'expires_at': (now - timedelta(seconds=1)).isoformat()}):
            commit = {'commit': {'message': 'HEROVERSE_EXECUTOR_LEASE_V1\n' + json.dumps(record | delta)}}
            with self.subTest(delta=delta), patch.object(bridge.native_review, 'github_read', return_value=commit):
                if delta:
                    with self.assertRaisesRegex(bridge.Blocked, 'EXECUTOR_LEASE_REQUIRED'):
                        bridge.lease({'lease_run_id': 'synthetic-lease'})
                else:
                    bridge.lease({'lease_run_id': 'synthetic-lease'})


class HistoricalQuota(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2030, 1, 2, 12, 0, tzinfo=timezone.utc)
        self.old = self.now - timedelta(days=1)
        self.recovered = {'version': 'private-audio-probe-v1', 'episode': 'genesis-09-short',
                          'run_id': '9000000001', 'state': 'COMPLETE',
                          'created_at': self.old.isoformat(), 'submitted_at': self.old.isoformat(),
                          'terminal_at': (self.old + timedelta(minutes=1)).isoformat(),
                          'updated_at': self.now.isoformat(), 'conversation_id': '900001',
                          'shots': {'k-close': {'clips': [{'generations': [
                              {'conversation_id': '900001', 'flags': []}]}]}}}

    def usage(self, extra=(), git_consumer=False):
        entries = [(self.now, self.recovered), *extra]
        branches = [{'name': f"claude/shot-probe-{r['episode']}-{r['run_id']}",
                     'commit': {'sha': str(n + 1) * 40}} for n, (_, r) in enumerate(entries)]
        def api(path):
            if path.startswith('branches?'):
                return branches
            for branch, (at, record) in zip(branches, entries):
                sha = branch['commit']['sha']
                if path == 'commits/' + sha:
                    return {'commit': {'committer': {'date': at.isoformat()}}}
                if path == 'contents/' + bridge.quota.probe_record_path(branch['name']) + '?ref=' + sha:
                    return {'content': base64.b64encode(json.dumps(record).encode()).decode()}
            raise AssertionError(path)
        if git_consumer:
            def run(args, **kwargs):
                if args[3] == 'for-each-ref':
                    lines = [b['name'] + ' ' + at.isoformat() for b, (at, _) in zip(branches, entries)]
                    return SimpleNamespace(returncode=0, stdout='\n'.join(lines))
                if args[3] == 'show':
                    for b, (_, record) in zip(branches, entries):
                        if args[4].startswith('origin/' + b['name'] + ':'):
                            return SimpleNamespace(returncode=0, stdout=json.dumps(record))
                raise AssertionError(args)
            return bridge.quota.git_actions_usage('2030-01-02', run=run, now=self.now)
        return guard.pavo_actions_usage(api, '2030-01-02', self.now)

    def test_history_read_does_not_charge_yesterdays_job_to_today(self):
        self.assertEqual(self.usage()['short_units'], 0,
                         'GET-only recovery must not create a new Short quota unit')

    def test_history_read_does_not_clear_newer_quota_failure_tail(self):
        recent = {'episode': 'genesis-10-short', 'run_id': '9000000002',
                  'shots': {'shot': {'clips': [{'generations': [
                      {'conversation_id': '900002', 'flags': ['NO_VIDEO']},
                      {'conversation_id': '900003', 'flags': ['NO_VIDEO']}]}]}}}
        used = self.usage([(self.now - timedelta(minutes=1), recent)])
        self.assertEqual(used['failed_tail'], 2,
                         'Polling an old success must not clear a newer provider quota stop')

    def test_mcp_reader_does_not_charge_yesterdays_job_to_today(self):
        self.assertEqual(self.usage(git_consumer=True)['units'], 0)

    def test_actual_current_day_private_submission_is_counted(self):
        self.recovered.update(created_at=self.now.isoformat(), submitted_at=self.now.isoformat())
        self.assertEqual(self.usage()['short_units'], 2)


if __name__ == '__main__':
    unittest.main()
