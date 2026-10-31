#!/usr/bin/env python3
"""Offline adversarial guards for the private-hook sweep; no production edits.

Run from the repository root with python3 -I -B. External I/O surfaces are fail-fast
patched or mocked. Only standard-library temporary receipt/quota files are
written. No subprocess, Git, HTTP, media, ML, FFmpeg, MediaPipe or SyncNet call.
"""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path('migration/integrations/pavo').resolve()))
import private_audio as b
import dispatch_guard as dg


class HookAdversarial(unittest.TestCase):
    def setUp(self):
        self.manifest_path = b.MANIFESTS + 'genesis-09-s-voice-20261030.json'
        self.m = json.loads((b.ROOT / self.manifest_path).read_text())
        self.i = {
            'plan': 'migration/production/bible/plans/genesis-09-short.json',
            'manifest': self.manifest_path, 'sha256': b.digest(self.m),
            'lease_run_id': 'offline-review',
            'receipt_certificate': 'unused-mock',
        }
        # Tripwires: no unexpected network, subprocess or Git operation can run.
        for target in ('socket.socket.connect', 'socket.create_connection',
                       'urllib.request.OpenerDirector.open', 'subprocess.run'):
            p = patch(target, side_effect=AssertionError('forbidden external operation: ' + target))
            p.start()
            self.addCleanup(p.stop)

    def env(self, directory, **extra):
        return {
            'RUNNER_TEMP': directory, 'GITHUB_RUN_ID': '1234567891',
            'GITHUB_REPOSITORY': 'matheusmagah-cpu/heroverse-engine',
            'GITHUB_REF': 'refs/heads/main', 'GITHUB_RUN_ATTEMPT': '1',
            'PRIVATE_AUDIO_INPUTS': json.dumps({**self.i, **extra}),
            'PAVO_IMAGE_LEDGER': str(Path(directory) / 'missing-quota.json'),
        }

    def test_second_quote_refuses_before_upload_create_stream(self):
        calls = []

        class Client(b.PrivateVideoClient):
            def __init__(self, *args, **kwargs):
                super().__init__(token='offline-secret-unrelated-to-fixtures', *args, **kwargs)

            def _quote(self, *args, **kwargs):
                calls.append('quote')
                allowed = len(calls) == 1
                return {'zero_cost_confirmed': allowed,
                        'required_credits': 0 if allowed else 1,
                        'final_points': 0 if allowed else 1, 'is_estimate': False}

            def _upload(self, *args):
                raise AssertionError('upload must not execute')

            def _video_json(self, *args, **kwargs):
                raise AssertionError('provider mutation must not execute')

        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, self.env(directory)), \
             patch.object(b, 'lease'), patch.object(b, 'PrivateVideoClient', Client), \
             patch.object(b, 'persist', side_effect=lambda r, p: b.atomic(p, r)), \
             patch.object(dg, 'pavo_budget', return_value=0):
            receipt = Path(directory) / 'pavo-private-audio/receipt.json'
            b.atomic(receipt, b.initial_record(self.m, '1234567891'))
            b.cli('prepare')
            b.cli('ready')
            with self.assertRaisesRegex(b.PavoError, 'ZERO_CREDIT'):
                b.cli('submit')
            self.assertEqual(calls, ['quote', 'quote'])
            record = json.loads(receipt.read_text())
            self.assertEqual(record['state'], 'SUBMITTING')
            self.assertIsNone(record['conversation_id'])
            with self.assertRaises(b.Blocked):
                b.require_new([b.public_record(record)], b.digest(self.m), manifest=self.m)

    def test_actual_inputs_recover_and_poll_only_same_cid_preserve_times(self):
        record = b.initial_record(self.m, '1234567890')
        record.update(conversation_id='373800000000000004', state='UNKNOWN',
                      submitted_at='2026-10-29T10:00:00+00:00')
        public = b.public_record(record)
        calls = []

        def read(path):
            calls.append(path)
            self.assertEqual(path, '/contents/migration/evidence/shots/genesis-09-short/'
                             '1234567890.json?ref=claude/shot-probe-genesis-09-short-1234567890')
            return {'content': base64.b64encode(json.dumps(public).encode()).decode()}

        class Client(b.PrivateVideoClient):
            def __init__(self, *args, **kwargs):
                super().__init__(token='offline-secret-unrelated-to-fixtures', *args, **kwargs)

            def _video_json(self, route, body=None, job=None):
                assert route == 'history' and body is None and job == record['conversation_id']
                calls.append(('history', job))
                return {'is_running': False, 'turns': [{'assistant': [{
                    'type': 'GenerationSuccess', 'data': {'data': {
                        'model_code': 'agnes-video-new-flash', 'results': [{
                            'url': 'https://cos-aigc-default.agnes-ai.space/synthetic.mp4',
                            'duration': 10, 'width': 720, 'height': 1280,
                        }]}}}]}]}

        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, self.env(directory, reconcile_run='1234567890')), \
             patch.object(b, 'lease'), \
             patch.object(b.native_review, 'github_read', side_effect=read), \
             patch.object(b, 'PrivateVideoClient', Client), \
             patch.object(b, 'persist', side_effect=lambda r, p: b.atomic(p, r)):
            b.cli('recover')
            b.cli('poll')
            out = json.loads((Path(directory) / 'pavo-private-audio/receipt.json').read_text())
            self.assertEqual(out['state'], 'COMPLETE')
            self.assertEqual(out['run_id'], '1234567890')
            self.assertEqual(out['submitted_at'], record['submitted_at'])
            self.assertEqual(out['created_at'], record['created_at'])
            self.assertFalse(out['production_approved'])
            self.assertFalse(out['published'])
            self.assertEqual(len(calls), 2)
            for command in ('claim', 'prepare', 'ready', 'submit'):
                with self.assertRaisesRegex(b.Blocked, 'RECOVERY_READ_ONLY'):
                    b.cli(command)
            projected = json.dumps(b.public_record(out))
            self.assertNotIn('https:', projected)
            self.assertNotIn(self.m['prompt'], projected)
            self.assertNotIn('provider_result', projected)

    def test_modes_reject_omni_audio_sound_and_nonce(self):
        for extra in ({'last_frame': ''}, {'references': []}, {'audios': []},
                      {'audio_seconds': 10}, {'nonce': 'next'}, {'sound': True}):
            with self.subTest(extra=extra), self.assertRaises(b.Blocked):
                b.validate({**self.m, **extra})
        for state in ('CLAIMED', 'INPUT_VERIFIED', 'SUBMITTING', 'UNKNOWN',
                      'FAILED', 'COMPLETE', 'BLOCKED'):
            old = b.initial_record(self.m, '1234567890')
            old['state'] = state
            changed = {**self.m, 'prompt': self.m['prompt'] + ' changed'}
            with self.subTest(state=state), self.assertRaisesRegex(b.Blocked, 'HOOK_EXISTING'):
                b.require_new([b.public_record(old)], b.digest(changed), manifest=changed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
