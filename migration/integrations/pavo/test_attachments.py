"""Draft transfer is not production approval or a generation endpoint."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import attachments as a


class DraftAttachments(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / a.INPUT / 'one.png'
        self.path.parent.mkdir(parents=True)
        self.data = b'\x89PNG\r\n\x1a\n' + b'\0\0\0\rIHDR' + struct.pack('>II', 1024, 1536)
        self.path.write_bytes(self.data)
        self.sha = hashlib.sha256(self.data).hexdigest()
        self.manifest = self.root / a.BASE / 'test.json'
        self.payload = {'version': 1, 'source': 'openai-imagegen', 'status': 'DRAFT',
                        'approved': False, 'generation_enabled': False,
                        'items': [{'shot': 's-test', 'path': str(self.path.relative_to(self.root)),
                                   'sha256': self.sha, 'prompt': None, 'provenance_status': 'EXACT_GENERATION_PROMPT_NOT_RECOVERED',
                                   'reference_sha256': []}]}
        self.save()

    def save(self):
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        self.manifest.write_text(json.dumps(self.payload))

    def claim(self, run='42', attempt='1'):
        return a.claim(self.manifest, run, attempt, self.root)

    def test_e216_remote_transfer_is_wired_without_enabling_generation(self):
        wf = (Path(__file__).resolve().parents[3] / '.github/workflows/pavo-mcp.yml').read_text()
        self.assertIn('attachments_manifest:', wf)
        self.assertIn('attachments.py claim', wf)
        self.assertIn('attachments.py send', wf)
        self.assertLess(wf.index('Persist attachment claims before any provider call'), wf.index('PAVO_TOKEN: ${{ secrets.PAVO_TOKEN }}', wf.index('  attachments:')))
        self.assertIn('git push origin HEAD:main', wf)

    def test_e217_exact_isolated_cli_loads_without_test_path_injection(self):
        cli = Path(__file__).resolve().with_name('attachments.py')
        result = subprocess.run([sys.executable, '-I', '-B', str(cli), '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('claim', result.stdout)

    def test_generation_routes_are_refused_before_network(self):
        c = a.AttachmentClient(token='offline-test')
        for route in ('create', 'stream', 'history'):
            with self.assertRaises(a.TransferError):
                c._video_json(route, {})

    def test_committed_three_candidate_hashes_and_unknown_prompts_match(self):
        root = Path(__file__).resolve().parents[3]
        payload, _ = a.load(root / a.BASE / 'short09-openai-20261029.json', root)
        self.assertEqual(len(payload['items']), 3)
        for item in payload['items']:
            sidecar = json.loads((root / item['path']).with_suffix('.json').read_text())
            self.assertEqual(item['sha256'], sidecar['sha256'])
            self.assertEqual(sidecar['source']['provider'], 'OpenAI')
            self.assertIsNone(item['prompt'])
            self.assertIsNone(sidecar['sent_prompt'])

    def test_unknown_prompt_is_not_invented(self):
        self.payload['items'][0]['prompt'] = 'Unproven prompt'
        self.save()
        with self.assertRaises(a.TransferError):
            self.claim()

    def test_hash_and_provenance_are_checked_before_claim(self):
        for field, value in [('source', 'cf-flux'), ('status', 'APPROVED'), ('approved', True), ('generation_enabled', True)]:
            with self.subTest(field=field):
                old = self.payload[field]
                self.payload[field] = value
                self.save()
                with self.assertRaises(a.TransferError):
                    self.claim()
                self.payload[field] = old
        self.payload['items'][0]['sha256'] = '0' * 64
        self.save()
        with self.assertRaises(a.TransferError):
            self.claim()
        self.assertFalse((self.root / a.RECEIPTS).exists())

    def test_claim_is_content_addressed_and_rerun_never_replays(self):
        self.claim()
        for run, attempt in [('42', '1'), ('42', '2'), ('43', '1')]:
            with self.assertRaises(a.TransferError):
                self.claim(run, attempt)
        with self.assertRaises(a.TransferError):
            a.send(self.manifest, '42', '2', self.root, client=object())

    def test_upload_requires_zero_quote_and_readback_of_exact_bytes(self):
        outer = self
        class Client:
            uploads = 0
            readback = staticmethod(lambda u: b'')
            def quote_video(self, **kw):
                return {'zero_cost_confirmed': True}
            def _upload(self, item):
                outer.assertEqual(item['data'], outer.data)
                self.uploads += 1
                return {'url': 'https://cos-aigc-default.agnes-ai.space/draft.png'}
        self.claim()
        c = Client()
        a.send(self.manifest, '42', '1', self.root, client=c, readback=lambda u: self.data)
        receipt = json.loads((self.root / a.RECEIPTS / (self.sha + '.json')).read_text())
        self.assertEqual(receipt['state'], 'UPLOADED_HASH_VERIFIED')
        self.assertFalse(receipt['approved'])
        self.assertFalse(receipt['generation_enabled'])
        with self.assertRaises(a.TransferError):
            a.send(self.manifest, '42', '1', self.root, client=c, readback=lambda u: self.data)
        self.assertEqual(c.uploads, 1)

    def test_failure_stops_without_retry_or_second_asset(self):
        class Client:
            uploads = 0
            readback = staticmethod(lambda u: b'')
            def quote_video(self, **kw):
                return {'zero_cost_confirmed': True}
            def _upload(self, item):
                self.uploads += 1
                raise TimeoutError('must not log provider body')
        self.claim()
        c = Client()
        for _ in range(2):
            with self.assertRaises(a.TransferError):
                a.send(self.manifest, '42', '1', self.root, client=c)
        self.assertEqual(c.uploads, 1)
        self.assertEqual(json.loads((self.root / a.RECEIPTS / (self.sha + '.json')).read_text())['state'], 'OUTCOME_REQUIRES_RECONCILIATION')

    def test_nonzero_quote_and_bad_readback_do_not_approve(self):
        class Client:
            uploads = 0
            readback = staticmethod(lambda u: b'')
            def quote_video(self, **kw):
                return {'zero_cost_confirmed': False}
            def _upload(self, item):
                self.uploads += 1
        self.claim()
        c = Client()
        with self.assertRaises(a.TransferError):
            a.send(self.manifest, '42', '1', self.root, client=c)
        self.assertEqual(c.uploads, 0)

    def test_destination_is_fixed_and_signed_url_never_becomes_public_receipt(self):
        for u in ['https://127.0.0.1/x', 'https://evil.test/x', 'http://cos-aigc-default.agnes-ai.space/x',
                  'https://cos-aigc-default.agnes-ai.space/x?token=x', 'https://u@cos-aigc-default.agnes-ai.space/x']:
            with self.assertRaises(a.TransferError):
                a.storage_url(u)

    def test_bad_readback_retains_upload_url_but_never_reuploads(self):
        class Client:
            uploads = 0
            def quote_video(self, **kw):
                return {'zero_cost_confirmed': True}
            def _upload(self, item):
                self.uploads += 1
                return {'url': 'https://cos-aigc-default.agnes-ai.space/draft.png'}
        self.claim()
        c = Client()
        for _ in range(2):
            with self.assertRaises(a.TransferError):
                a.send(self.manifest, '42', '1', self.root, client=c, readback=lambda u: b'wrong')
        self.assertEqual(c.uploads, 1)
        r = json.loads((self.root / a.RECEIPTS / (self.sha + '.json')).read_text())
        self.assertEqual(r['state'], 'UPLOADED_NOT_VERIFIED')
        self.assertFalse(r['approved'])


if __name__ == '__main__':
    unittest.main()
