"""Run the real dispatcher shell with only local Git and the existing stub gh."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'migration/ops'))
import test_requests as fixtures


class InputKeys(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.Requests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        snapshot = os.environ.get('REQUESTS_SWEEP_SNAPSHOT')
        if snapshot:
            source = subprocess.check_output(['git', 'show', snapshot + ':.github/workflows/requests.yml'],
                                             cwd=ROOT, text=True)
            folder = tempfile.TemporaryDirectory()
            self.addCleanup(folder.cleanup)
            root = Path(folder.name)
            path = root / '.github/workflows/requests.yml'
            path.parent.mkdir(parents=True)
            path.write_text(source)
            self.enterContext(patch.object(fixtures, 'ROOT', root))

    def test_sha256_dispatch_preserves_exact_value_and_durable_claim(self):
        value = 'a' * 64
        self.f.request('bound.json', 'good.yml', sha256=value, input_v2='literal value')
        result = self.f.run_workflow()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.f.calls()
        self.assertEqual(len(calls), 1)
        self.assertIn('sha256=' + value, calls[0]['args'])
        self.assertIn('input_v2=literal value', calls[0]['args'])
        self.assertTrue(calls[0]['durable_before_post'])
        saved = next(iter(self.f.records('done').values()))
        self.assertEqual(saved['inputs']['sha256'], value)

    def test_original_snake_case_still_dispatches(self):
        self.f.request('original.json', 'good.yml', plan='one plan', lease_run_id='synthetic-lease')
        result = self.f.run_workflow()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.f.calls()), 1)
        self.assertTrue(self.f.calls()[0]['durable_before_post'])

    def test_unsafe_or_digit_leading_keys_never_claim_or_dispatch(self):
        bad = ('1sha', 'sha-256', 'sha 256', 'sha;exit', '-f', '', 'SHA256', 'sha\n256')
        for index, key in enumerate(bad):
            self.f.request(f'invalid-{index}.json', 'good.yml', **{key: 'literal'})
        result = self.f.run_workflow()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BAD_INPUT', result.stderr)
        self.assertEqual(self.f.calls(), [])
        self.assertEqual(self.f.records('inflight'), {})
        self.assertEqual(self.f.records('done'), {})


if __name__ == '__main__':
    unittest.main()
