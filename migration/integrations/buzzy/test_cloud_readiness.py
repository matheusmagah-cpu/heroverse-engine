import importlib.util
import json
import re
from pathlib import Path
import unittest

P = Path(__file__).with_name('cloud_readiness.py')

class Readiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if P.exists():
            spec = importlib.util.spec_from_file_location('cloud_readiness', P)
            cls.mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.mod)
        else:
            cls.mod = None

    def test_implementation_exists(self):
        self.assertIsNotNone(self.mod, 'read-only cloud deployment verifier not implemented')

    def fake(self, response):
        seen = []
        def read(path):
            seen.append(path)
            return response.get(path, (403, {'success': False, 'errors': [{'message': 'PRIVATE_SECRET'}]}))
        return read, seen

    def test_missing_credentials_never_requests(self):
        if self.mod is None: self.skipTest('implementation absent')
        read, seen = self.fake({})
        r = self.mod.inspect('', False, read)
        self.assertEqual(seen, [])
        self.assertEqual(r['status'], 'CREDENTIAL_NOT_CONFIGURED')
        self.assertFalse(r['deployed'])

    def test_multiple_accounts_not_guessed(self):
        if self.mod is None: self.skipTest('implementation absent')
        read, seen = self.fake({'/accounts': (200, {'success': True, 'result': [{'id': 'a'*32}, {'id': 'b'*32}]})})
        r = self.mod.inspect('', True, read)
        self.assertEqual(r['status'], 'ACCOUNT_BINDING_REQUIRED')
        self.assertEqual(seen, ['/accounts'])

    def test_read_access_is_not_write_or_free_cost_proof(self):
        if self.mod is None: self.skipTest('implementation absent')
        account = 'a'*32
        read, seen = self.fake({f'/accounts/{account}/workers/scripts': (200, {'success': True, 'result': [{'id': 'PRIVATE_WORKER'}]})})
        r = self.mod.inspect(account, True, read)
        self.assertTrue(r['worker_list_readable'])
        self.assertEqual(r['worker_count'], 1)
        self.assertEqual(r['deployment_permission'], 'NOT_VERIFIED')
        self.assertEqual(r['billing_state'], 'NOT_VERIFIED')
        self.assertNotIn('PRIVATE', json.dumps(r))
        self.assertFalse(r['deployed'])

    def test_private_response_not_exported(self):
        if self.mod is None: self.skipTest('implementation absent')
        read, seen = self.fake({})
        r = self.mod.inspect('a'*32, True, read)
        self.assertNotIn('PRIVATE_SECRET', json.dumps(r))
        self.assertEqual(r['status'], 'CLOUD_ACCESS_INCOMPLETE')
        self.assertEqual(len(seen), 3)

    def test_account_identifier_is_validated(self):
        if self.mod is None: self.skipTest('implementation absent')
        read, seen = self.fake({})
        with self.assertRaises(ValueError): self.mod.inspect('../other', True, read)
        self.assertEqual(seen, [])

    def test_empty_subscription_list_is_not_free_tier_proof(self):
        if self.mod is None: self.skipTest('implementation absent')
        account = 'b'*32
        read, seen = self.fake({f'/accounts/{account}/subscriptions': (200, {'success': True, 'result': []})})
        r = self.mod.inspect(account, True, read)
        self.assertEqual(r['subscription_count'], 0)
        self.assertEqual(r['billing_state'], 'READABLE_NOT_A_COST_QUOTE')
        self.assertFalse(r['generation_enabled'])

    def test_account_binding_matches_the_existing_image_workflow(self):
        root = Path(__file__).resolve().parents[3]
        pattern = r"CLOUDFLARE_ACCOUNT_ID: (\$\{\{[^\n]+?\}\})"
        existing = re.search(pattern, (root / '.github/workflows/cf-images.yml').read_text())
        inspection = re.search(pattern, (root / '.github/workflows/buzzy-cloud-readiness.yml').read_text())
        self.assertIsNotNone(existing)
        self.assertIsNotNone(inspection)
        self.assertEqual(inspection.group(1), existing.group(1))

if __name__ == '__main__': unittest.main()
