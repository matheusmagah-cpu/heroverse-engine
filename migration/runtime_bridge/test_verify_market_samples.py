"""Real saved receipt regression controls; no provider or publication calls."""
import copy
import json
from pathlib import Path
import unittest
from verify_market_samples import verify

ROOT = Path(__file__).resolve().parent

class SavedMarketVerificationTests(unittest.TestCase):
    def setUp(self):
        evidence = ROOT if (ROOT/'market-summary.json').exists() else ROOT.parent/'evidence'
        summary_name = 'market-summary.json' if evidence == ROOT else 'market-av-38600754626.json'
        self.summary = json.loads((evidence/summary_name).read_bytes())
        self.plan = json.loads((evidence/'market-av-plan-20261014.json').read_bytes())
        receipts = ROOT/'receipts' if evidence == ROOT else evidence
        self.files = {'migration/evidence/'+p.name:p.read_bytes()
                      for p in receipts.glob('public-av-*.json')}

    def test_duplicate_sample_cannot_inflate_coverage(self):
        self.summary['samples'].append(copy.deepcopy(self.summary['samples'][0]))
        with self.assertRaisesRegex(PermissionError,'DUPLICATE_SAMPLE_WINDOW'):
            verify(self.summary,self.plan,self.files.__getitem__)

    def test_unplanned_sample_cannot_enter_handoff(self):
        self.summary['samples'][0]['window'] = [0,41]
        with self.assertRaisesRegex(PermissionError,'UNPLANNED_SAMPLE_WINDOW'):
            verify(self.summary,self.plan,self.files.__getitem__)

    def test_real_completed_plan_reopens_without_remote_effects(self):
        result = verify(self.summary,self.plan,self.files.__getitem__)
        self.assertEqual(result['verified_sample_seconds'],300)
        self.assertEqual(len(result['verified_samples']),15)
        self.assertEqual(result['gaps'],[])
        self.assertEqual(result['provider_calls'],0)
        self.assertFalse(result['native_frames_independently_reviewed'])
        self.assertFalse(result['publication_authorized'])

    def test_changed_prior_failure_rejects_recovery_lineage(self):
        for path,raw in list(self.files.items()):
            item = json.loads(raw)
            if item.get('failure_code') == 'HTTP_503_UNAVAILABLE':
                item['failure_code'] = 'HTTP_429_RESOURCE_EXHAUSTED'
                self.files[path] = json.dumps(item).encode()
        with self.assertRaisesRegex(PermissionError,'PRIOR_RECOVERY_RECEIPT_CHANGED'):
            verify(self.summary,self.plan,self.files.__getitem__)

    def test_invented_owner_recovery_is_rejected(self):
        for path,raw in list(self.files.items()):
            item = json.loads(raw)
            if item.get('recovery'):
                item['recovery']['owner_request'] = 'invented'
                self.files[path] = json.dumps(item).encode()
        with self.assertRaisesRegex(PermissionError,'OWNER_RECOVERY_CHANGED'):
            verify(self.summary,self.plan,self.files.__getitem__)

    def test_completed_sample_does_not_authorize_publication(self):
        sample = self.summary['samples'][0]
        path = 'migration/evidence/public-av-'+sample['key'].split(':')[1]+'.json'
        receipt = json.loads(self.files[path]);receipt['publication_authorized'] = True
        self.files[path] = json.dumps(receipt).encode()
        with self.assertRaisesRegex(PermissionError,'SAMPLE_CANNOT_GRANT_AUTHORITY'):
            verify(self.summary,self.plan,self.files.__getitem__)

if __name__ == '__main__': unittest.main()
