"""Native reviewer transport boundaries, no network and no credentials."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('native_review', ROOT / 'migration/production/bible/native_review.py')
n = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(n)


class Review(unittest.TestCase):

    def test_e222_grounding_required_without_changing_scores(self):
        r = {'audio_received': True, 'visual_received': True, 'duration_seconds': 175,
             'scores': {k: 9.5 for k in n.RUBRIC}, 'overall': 9.5,
             'issues': [], 'limitations': [], 'criterion_issues': {},
             'coverage': [{'start': x*25, 'end': (x+1)*25,
                 'audible_observation': 'Voice over music', 'visual_observation': 'Landscape',
                 'sync_observation': 'Words align', 'speech_excerpt': 'A synthetic fixture sentence',
                 'speaker_observation': 'One low voice', 'motion_observation': 'camera_only'}
                 for x in range(7)]}
        n.validate_report(r)
        import copy
        for field in ('speech_excerpt', 'speaker_observation', 'motion_observation'):
            bad=copy.deepcopy(r); del bad['coverage'][0][field]
            with self.assertRaises(n.Refusal): n.validate_report(bad)
        for key in (*n.RUBRIC, 'overall'):
            bad=copy.deepcopy(r)
            if key == 'overall': bad[key]=6.6
            else: bad['scores'][key]=6.6
            with self.assertRaises(n.Refusal): n.validate_report(bad)
            bad['issues']=['00:05.00 - Synthetic fixture defect']
            bad['criterion_issues']={key:[0]}
            n.validate_report(bad)
            for ref in (-1, 1, True, '0'):
                bad['criterion_issues']={key:[ref]}
                with self.assertRaises(n.Refusal): n.validate_report(bad)
        self.assertNotIn('the speaking Keeper', n.prompt())

    def test_e222_issue_times_are_valid_and_inside_media(self):
        import copy
        report = {'audio_received': True, 'visual_received': True, 'duration_seconds': 175,
                  'scores': {k: 9.5 for k in n.RUBRIC}, 'overall': 6.6,
                  'issues': ['00:05 Synthetic defect'], 'limitations': [],
                  'criterion_issues': {'overall': [0]},
                  'coverage': [{'start': x*25, 'end': (x+1)*25,
                      'audible_observation': 'Voice over music', 'visual_observation': 'Landscape',
                      'sync_observation': 'Words align', 'speech_excerpt': 'A synthetic fixture sentence',
                      'speaker_observation': 'One low voice', 'motion_observation': 'camera_only'}
                      for x in range(7)]}
        for stamp in ('99:99', '00:60', '00:01:60', '01:00:00', '02:55', '02:55.01', '03:00'):
            with self.subTest(stamp=stamp):
                bad = copy.deepcopy(report)
                bad['issues'] = [stamp + ' Synthetic defect']
                with self.assertRaises(n.Refusal):
                    n.validate_report(bad)
        for stamp in ('00:00', '02:54.99', '00:02:54.99'):
            good = copy.deepcopy(report)
            good['issues'] = [stamp + ' Synthetic defect']
            n.validate_report(good)
        self.assertEqual(report['overall'], 6.6)

    def test_e221_provider_hash_encodings_preserve_exact_identity(self):
        digest = '34c91fa1a67f01575596e5440c86ff230f7cd5e0adc55544d945974e864812df'
        for wire in (n.base64.b64encode(bytes.fromhex(digest)).decode(),
                     n.base64.b64encode(digest.encode()).decode()):
            self.assertEqual(n.provider_sha256(wire), digest)
        for wire in ('bad', n.base64.b64encode(b'x'*64).decode(),
                     n.base64.b64encode(b'x'*31).decode()):
            with self.assertRaises(n.Refusal):
                n.provider_sha256(wire)

    def test_resume_requires_proof_inference_was_never_started(self):
        i = {'plan': 'x', 'sha256': 'a'*64, 'resume_before_inference': '1'}
        run = {'id': 1, 'display_title': n.title(i), 'path': '.github/workflows/native-review.yml',
               'status': 'completed', 'conclusion': 'failure', 'run_attempt': 1}
        steps = [{'name': k, 'status': 'completed', 'conclusion': v} for k, v in (
            ('Open one private resumable upload session', 'success'),
            ('Await exact-byte upload and read back provider hash', 'failure'),
            ('Submit native audio and video review once', 'skipped'),
            ('Read the same interaction (GET only)', 'skipped'))]
        jobs = [{'name':'review', 'steps':steps}]
        self.assertEqual(n.recovery_source(i, run, jobs), '1')
        for delta in ({'status':'in_progress'}, {'run_attempt':2}, {'display_title':'another master'},
                      {'conclusion':'success'}, {'id':3}):
            with self.assertRaises(n.Refusal): n.recovery_source(i, run | delta, jobs)
        for conclusion in ('success', 'failure', None):
            changed = [dict(s) for s in steps]; changed[2]['conclusion'] = conclusion
            with self.assertRaises(n.Refusal):
                n.recovery_source(i, run, [{'name':'review', 'steps':changed}])
        n.reject_duplicate(i, [run], 2, 1, '1')
        with self.assertRaises(n.Refusal):
            n.reject_duplicate(i, [run, run | {'id':3}], 2, 1, '1')

    def test_resume_never_uploads_again_and_still_verifies_file(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'GITHUB_RUN_ID':'2'}), \
             patch.object(n, 'free_key', return_value='test'), patch.object(n, 'request') as send:
            root=Path(d); receipt=root/'receipt.json'; digest='a'*64
            i={'plan':'x', 'sha256':digest, 'byte_size':'80', 'resume_before_inference':'1'}
            n.save(root/'recovery.json', {'source_run_id':'1', 'current_run_id':'2',
                                        'sha256':digest, 'inference_was_skipped':True})
            n.upload(i,root,receipt); send.assert_not_called()
            self.assertEqual(json.loads(receipt.read_text())['file_display_name'], 'review-master-'+digest+'-1')
            f={'name':'files/test','state':'ACTIVE','mimeType':'video/mp4','sizeBytes':'80',
               'uri':n.API+'/v1beta/files/test','sha256Hash':n.base64.b64encode(digest.encode()).decode()}
            with patch.object(n,'find_file',return_value=f): n.file_ready(i,receipt)
            self.assertEqual(json.loads(receipt.read_text())['status'],'FILE_READY')
            send.assert_not_called()

    def test_exact_content_never_replayed_even_after_success(self):
        i = {'plan': 'x', 'sha256': 'a' * 64}
        for status in ('success', 'failure', None):
            with self.assertRaises(n.Refusal):
                n.reject_duplicate(i, [{'id': 1, 'display_title': n.title(i), 'conclusion': status}], 2, 1)
        with self.assertRaises(n.Refusal):
            n.reject_duplicate(i, [], 1, 2)
        n.reject_duplicate(i, [{'id': 1, 'display_title': n.title(i)}], 1, 1)

    def test_urls_never_send_key_to_another_host_or_redirect(self):
        for url in ('http://generativelanguage.googleapis.com', 'https://evil.test/',
                    'https://generativelanguage.googleapis.com.evil.test/',
                    'https://user@generativelanguage.googleapis.com', 'https://generativelanguage.googleapis.com:444'):
            with self.assertRaises(n.Refusal):
                n.https(url, True)
        with self.assertRaises(n.Refusal):
            n.NoRedirect().redirect_request(None, None, None, None, None)

    def test_paid_stale_mismatched_key_proof_refused(self):
        proof = {'tier': 'Free', 'billing_account_linked': False, 'model': n.MODEL,
                 'source': 'verified-ai-studio-readback', 'verified_at_unix': time.time(),
                 'api_key_sha256': n.hashlib.sha256(b'test').hexdigest()}
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test'}):
            self.assertEqual(n.free_key({'free_tier_evidence': json.dumps(proof)}), 'test')
            for delta in ({'tier': 'Paid'}, {'billing_account_linked': True}, {'verified_at_unix': 0},
                          {'api_key_sha256': 'wrong'}, {'model': 'different-model'}):
                with self.assertRaises(n.Refusal):
                    n.free_key({'free_tier_evidence': json.dumps(proof | delta)})

    def test_wrong_master_never_reaches_inference(self):
        with tempfile.TemporaryDirectory() as d, patch.object(n, 'free_key', return_value='test'), \
             patch.object(n, 'find_file', return_value={'name':'files/test', 'state':'ACTIVE',
                                                       'sha256Hash': n.base64.b64encode(b'wrong').decode()}), \
             patch.object(n, 'request') as send:
            p=Path(d)/'receipt.json'
            n.save(p, {'file_display_name': 'fixture'})
            with self.assertRaisesRegex(n.Refusal, 'PROVIDER_FILE_HASH_MISMATCH'):
                n.file_ready({'sha256': 'a'*64}, p)
            send.assert_not_called()

    def test_uncertain_submit_stops_second_post(self):
        with tempfile.TemporaryDirectory() as d, patch.object(n, 'free_key', return_value='test'), \
             patch.object(n, 'request', side_effect=TimeoutError('private URL should not leak')) as send:
            p=Path(d)/'r.json'
            n.save(p, {'status': 'FILE_READY', 'output_sha256': 'a'*64, 'file_uri': n.API+'/v1beta/files/test'})
            with self.assertRaises(TimeoutError):
                n.submit({'sha256': 'a'*64}, p)
            self.assertEqual(json.loads(p.read_text())['status'], 'SUBMIT_UNCERTAIN')
            with self.assertRaises(n.Refusal):
                n.submit({'sha256': 'a'*64}, p)
            self.assertEqual(send.call_count, 1)

    def test_missing_native_audio_and_gaps_refused(self):
        r = {'audio_received': True, 'visual_received': True, 'duration_seconds': 175,
             'scores': {k: 9.5 for k in n.RUBRIC}, 'overall': 9.5, 'issues': [], 'limitations': [],
             'coverage': [{'start': x*25, 'end': (x+1)*25, 'audible_observation': 'audio',
                           'visual_observation': 'video', 'sync_observation': 'sync',
                           'speech_excerpt': 'A synthetic fixture sentence',
                           'speaker_observation': 'One low voice', 'motion_observation': 'camera_only'} for x in range(7)]}
        n.validate_report(r)
        for delta in ({'audio_received': False}, {'duration_seconds': 20}, {'overall': True},
                      {'coverage': r['coverage'][:-1]}, {'coverage': r['coverage'][1:]}):
            with self.assertRaises(n.Refusal):
                n.validate_report(r | delta)

    def test_e220_single_line_certificate_roundtrip_hides_private_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); key = root / 'key.pem'; cert = root / 'cert.pem'
            n.subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                              '-keyout', str(key), '-out', str(cert), '-days', '1', '-subj', '/CN=fixture'],
                             check=True, stdout=n.subprocess.DEVNULL, stderr=n.subprocess.DEVNULL)
            receipt = root / 'receipt.json'
            n.save(receipt, {'private_id': 'private-receipt-fixture'})
            n.seal({'receipt_certificate': cert.read_text().replace('\n', '')}, receipt)
            encrypted = (root / 'receipt.cms').read_bytes()
            self.assertNotIn(b'private-receipt-fixture', encrypted)
            clear = n.subprocess.check_output(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
                                               '-in', str(root / 'receipt.cms'), '-inkey', str(key)])
            self.assertEqual(clear, receipt.read_bytes())

    def test_submit_retains_native_av_and_real_provider_id(self):
        with tempfile.TemporaryDirectory() as d, patch.object(n, 'free_key', return_value='test'), \
             patch.object(n, 'request', return_value=({}, json.dumps({'id': 'actual-id', 'model': n.MODEL}).encode())) as send:
            p = Path(d) / 'receipt.json'
            n.save(p, {'status': 'FILE_READY', 'output_sha256': 'a'*64, 'file_uri': n.API+'/v1beta/files/test'})
            n.submit({'sha256': 'a'*64}, p)
            payload = json.loads(send.call_args.args[2])
            self.assertTrue(payload['background'])
            self.assertEqual(payload['input'][0]['type'], 'video')
            self.assertEqual(payload['input'][0]['processing'], {'type': 'static', 'fps': 4})
            self.assertEqual(json.loads(p.read_text())['interaction_id'], 'actual-id')

    def test_workflow_never_takes_url_or_writes_approvals(self):
        w = (ROOT / '.github/workflows/native-review.yml').read_text()
        self.assertNotIn('source_url', w)
        self.assertNotIn('contents: write', w)
        self.assertNotIn('HEROVERSE_REVIEW_MEDIA_URL', w)
        self.assertLess(w.index('Persist interaction ID'), w.index('native_review.py poll'))
        self.assertLess(w.index('Refuse duplicate'), w.index('secrets.'))
        self.assertNotIn('APPROVAL.json', w)
        self.assertNotIn('path: ${{ runner.temp }}/native-review/receipt.json', w)
        self.assertIn('native-review/receipt.cms', w)


if __name__ == '__main__':
    unittest.main()
