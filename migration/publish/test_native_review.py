"""Native reviewer transport boundaries, no network and no credentials."""
import importlib.util
import copy
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

    def test_e242_buzzy_plan_floor_is_8_and_the_default_stays_9_5(self):
        with tempfile.TemporaryDirectory() as d:
            for name, track, want in (('a.json', 'buzzy', 8.0), ('b.json', None, 9.5), ('c.json', 'other', 9.5)):
                Path(d, name).write_text(json.dumps({'track': track} if track else {}))
                self.assertEqual(n.floor_for(Path(d, name)), want)
            self.assertEqual(n.floor_for(Path(d, 'missing.json')), 9.5)

    def test_e222_grounding_required_without_changing_scores(self):
        r = {'audio_received': True, 'visual_received': True, 'duration_seconds': 175,
             'scores': {k: 9.5 for k in n.RUBRIC}, 'overall': 9.5,
             'issues': [], 'limitations': [], 'criterion_issues': {},
             'coverage': [{'start': x*25, 'end': (x+1)*25,
                 'audible_observation': 'Voice over music', 'visual_observation': 'Landscape',
                 'sync_observation': 'Words align', 'speech_excerpt': 'A synthetic fixture sentence',
                 'speaker_observation': 'One low voice', 'motion_observation': 'camera_only'}
                 for x in range(7)]}
        before = copy.deepcopy(r)
        n.validate_report(r, 175)
        self.assertEqual(r, before)
        for field in ('speech_excerpt', 'speaker_observation', 'motion_observation'):
            bad=copy.deepcopy(r); del bad['coverage'][0][field]
            before = copy.deepcopy(bad)
            with self.assertRaises(n.Refusal): n.validate_report(bad, 175)
            self.assertEqual(bad, before)
        for key in (*n.RUBRIC, 'overall'):
            bad=copy.deepcopy(r)
            if key == 'overall': bad[key]=6.6
            else: bad['scores'][key]=6.6
            before = copy.deepcopy(bad)
            with self.assertRaises(n.Refusal): n.validate_report(bad, 175)
            self.assertEqual(bad, before)
            bad['issues']=['00:05.00 - Synthetic fixture defect']
            bad['criterion_issues']={key:[0]}
            before = copy.deepcopy(bad)
            n.validate_report(bad, 175)
            self.assertEqual(bad, before)
            for ref in (-1, 1, True, '0'):
                bad['criterion_issues']={key:[ref]}
                before = copy.deepcopy(bad)
                with self.assertRaises(n.Refusal): n.validate_report(bad, 175)
                self.assertEqual(bad, before)
        self.assertNotIn('the speaking Keeper', n.prompt(175))

    def test_e222_issue_times_are_valid_and_inside_media(self):
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
                before = copy.deepcopy(bad)
                with self.assertRaises(n.Refusal):
                    n.validate_report(bad, 175)
                self.assertEqual(bad, before)
        for stamp in ('00:00', '02:54.99', '00:02:54.99'):
            good = copy.deepcopy(report)
            good['issues'] = [stamp + ' Synthetic defect']
            before = copy.deepcopy(good)
            n.validate_report(good, 175)
            self.assertEqual(good, before)

    def test_e222_timestamp_without_description_stays_unvalidated(self):
        report = {'audio_received': True, 'visual_received': True, 'duration_seconds': 175,
                  'scores': {k: 9.5 for k in n.RUBRIC}, 'overall': 6.6,
                  'issues': ['00:05 Synthetic defect'], 'limitations': [],
                  'criterion_issues': {'overall': [0]},
                  'coverage': [{'start': x*25, 'end': (x+1)*25,
                      'audible_observation': 'Voice over music', 'visual_observation': 'Landscape',
                      'sync_observation': 'Words align', 'speech_excerpt': 'A synthetic fixture sentence',
                      'speaker_observation': 'One low voice', 'motion_observation': 'camera_only'}
                      for x in range(7)]}
        for issue in ('00:05 ', '00:05\n\t', '00:05\u00a0', '00:05 - ', '00:05 — : -\t'):
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as d, \
                 patch.object(n, 'free_key', return_value='test'):
                report['issues'] = [issue]
                before = copy.deepcopy(report)
                response_text = json.dumps(report)
                body = json.dumps({'id': 'fixture-id', 'model': n.MODEL, 'status': 'completed',
                                   'steps': [{'type': 'model_output', 'content': [
                                       {'type': 'text', 'text': response_text}]}]}).encode()
                receipt = Path(d) / 'receipt.json'
                n.save(receipt, {'status': 'SUBMITTED', 'output_sha256': 'a'*64,
                                 'interaction_id': 'fixture-id', 'duration_seconds': 175})
                with patch.object(n, 'request', return_value=({}, body)) as send:
                    with self.assertRaisesRegex(n.Refusal, 'ISSUE_DESCRIPTION_MISSING'):
                        n.poll({'sha256': 'a'*64}, receipt)
                    saved = json.loads(receipt.read_text())
                    self.assertEqual(saved['status'], 'COMPLETE_UNVALIDATED')
                    self.assertEqual(saved['response_text'], response_text)
                    self.assertEqual(saved['response_sha256'], n.hashlib.sha256(body).hexdigest())
                    self.assertNotIn('report', saved)
                    self.assertFalse(saved.get('publication_ready', False))
                    with self.assertRaisesRegex(n.Refusal, 'POLL_STATE_INVALID'):
                        n.poll({'sha256': 'a'*64}, receipt)
                    with self.assertRaisesRegex(n.Refusal, 'SUBMIT_STATE_INVALID'):
                        n.submit({'sha256': 'a'*64}, receipt)
                    send.assert_called_once_with(n.API + '/v1beta/interactions/fixture-id', 'test')
                self.assertEqual(report, before)
                self.assertFalse((Path(d) / 'APPROVAL.json').exists())

    def test_e230_timestamp_colon_separator_is_accepted_without_mutation(self):
        report = {'audio_received': True, 'visual_received': True, 'duration_seconds': 175,
                  'scores': {k: 9.5 for k in n.RUBRIC}, 'overall': 6.0,
                  'issues': ['00:06.40: Abrupt cut to a static facade'], 'limitations': [],
                  'criterion_issues': {'overall': [0]},
                  'coverage': [{'start': x*25, 'end': (x+1)*25,
                      'audible_observation': 'Voice over music', 'visual_observation': 'Landscape',
                      'sync_observation': 'Words align', 'speech_excerpt': 'A synthetic fixture sentence',
                      'speaker_observation': 'One low voice', 'motion_observation': 'camera_only'}
                      for x in range(7)]}
        before = copy.deepcopy(report)
        n.validate_report(report, 175)
        self.assertEqual(report, before)

    def test_e236_measured_master_duration_drives_prompt_and_validation(self):
        # The rebuilt Genesis09 master is 174.4 s: its report must not be judged against an old 175 s constant.
        f = {'videoMetadata': {'videoDuration': '174.400s'}}
        duration = n.provider_duration(f)
        self.assertEqual(duration, 174.4)
        for bad in ({}, {'videoMetadata': {}}, {'videoMetadata': {'videoDuration': '174.4'}},
                    {'videoMetadata': {'videoDuration': '0s'}}, {'videoMetadata': {'videoDuration': 174.4}},
                    {'videoMetadata': {'videoDuration': '-3s'}}, {'videoMetadata': {'videoDuration': '9999s'}}):
            with self.subTest(bad=bad), self.assertRaises(n.Refusal):
                n.provider_duration(bad)
        text = n.prompt(duration)
        self.assertIn('complete 174.4-second', text)
        self.assertIn('covering 0-174.4 without gaps', text)
        for stale in ('175', '6.40', '114.28', '131.46'):
            self.assertNotIn(stale, text)
        self.assertEqual(n.prompt(60), n.prompt(60.0))
        self.assertNotEqual(n.prompt(60), n.prompt(174.4))

        def report(ends):
            starts = [0] + ends[:-1]
            return {'audio_received': True, 'visual_received': True, 'duration_seconds': 174.4,
                    'scores': {k: 9.5 for k in n.RUBRIC}, 'overall': 9.0,
                    'issues': ['02:54.30 Synthetic final-frame defect'], 'limitations': [],
                    'criterion_issues': {'overall': [0]},
                    'coverage': [{'start': a, 'end': b,
                        'audible_observation': 'Voice over music', 'visual_observation': 'Landscape',
                        'sync_observation': 'Words align', 'speech_excerpt': 'A synthetic fixture sentence',
                        'speaker_observation': 'One low voice', 'motion_observation': 'camera_only'}
                        for a, b in zip(starts, ends)]}
        good = report([25, 50, 75, 100, 125, 150, 174.4])
        before = copy.deepcopy(good)
        n.validate_report(good, duration)
        self.assertEqual(good, before)
        # The old constant would have refused this valid 174.4 s report (issue at 174.3 s is inside media).
        n.validate_report(good | {'issues': ['02:54.39 Synthetic last-frame defect']}, duration)
        cases = {'COVERAGE_INCOMPLETE': report([25, 50, 75, 100, 125, 150, 173.5]),       # stops early
                 'COVERAGE_INCOMPLETE ': report([25, 50, 75, 100, 125, 150, 175]),        # exceeds media
                 'ISSUE_TIMESTAMP_OUTSIDE_MEDIA': good | {'issues': ['02:54.40 Synthetic defect']},
                 'COVERAGE_DURATION_INVALID': good | {'duration_seconds': 176}}
        for code, bad in cases.items():
            with self.subTest(code=code), self.assertRaisesRegex(n.Refusal, code.strip()):
                n.validate_report(bad, duration)
        for missing in (None, 0, -1, '174.4', True):
            with self.subTest(missing=missing), self.assertRaisesRegex(n.Refusal, 'DURATION_INVALID'):
                n.validate_report(good, missing)
        # Submit and poll use the receipt's own measured duration; a receipt without one is refused.
        with tempfile.TemporaryDirectory() as d, patch.object(n, 'free_key', return_value='test'), \
             patch.object(n, 'request', return_value=({}, json.dumps({'id': 'actual-id', 'model': n.MODEL}).encode())) as send:
            p = Path(d) / 'receipt.json'
            n.save(p, {'status': 'FILE_READY', 'output_sha256': 'a'*64, 'file_uri': n.API+'/v1beta/files/test'})
            with self.assertRaisesRegex(n.Refusal, 'SUBMIT_STATE_INVALID'):
                n.submit({'sha256': 'a'*64}, p)
            send.assert_not_called()
            n.save(p, {'status': 'FILE_READY', 'output_sha256': 'a'*64, 'file_uri': n.API+'/v1beta/files/test',
                       'duration_seconds': duration})
            n.submit({'sha256': 'a'*64}, p)
            sent = json.loads(send.call_args.args[2])['input'][1]['text']
            self.assertEqual(sent, n.prompt(174.4))
            self.assertEqual(json.loads(p.read_text())['prompt_sha256'], n.hashlib.sha256(sent.encode()).hexdigest())
        # A file that the provider cannot measure never reaches inference.
        with tempfile.TemporaryDirectory() as d, patch.object(n, 'free_key', return_value='test'):
            p = Path(d) / 'receipt.json'
            n.save(p, {'file_display_name': 'fixture'})
            digest = 'a' * 64
            f = {'name': 'files/test', 'state': 'ACTIVE', 'mimeType': 'video/mp4', 'sizeBytes': '80',
                 'uri': n.API + '/v1beta/files/test', 'sha256Hash': n.base64.b64encode(digest.encode()).decode()}
            with patch.object(n, 'find_file', return_value=f), \
                 self.assertRaisesRegex(n.Refusal, 'PROVIDER_DURATION_MISSING'):
                n.file_ready({'sha256': digest, 'byte_size': '80'}, p)
            self.assertNotEqual(json.loads(p.read_text())['status'], 'FILE_READY')

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
               'uri':n.API+'/v1beta/files/test','sha256Hash':n.base64.b64encode(digest.encode()).decode(),
               'videoMetadata':{'videoDuration':'174.400s'}}
            with patch.object(n,'find_file',return_value=f): n.file_ready(i,receipt)
            self.assertEqual(json.loads(receipt.read_text())['status'],'FILE_READY')
            self.assertEqual(json.loads(receipt.read_text())['duration_seconds'],174.4)
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
            n.save(p, {'status': 'FILE_READY', 'output_sha256': 'a'*64, 'file_uri': n.API+'/v1beta/files/test',
                       'duration_seconds': 175})
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
        n.validate_report(r, 175)
        for delta in ({'audio_received': False}, {'duration_seconds': 20}, {'overall': True},
                      {'coverage': r['coverage'][:-1]}, {'coverage': r['coverage'][1:]}):
            with self.assertRaises(n.Refusal):
                n.validate_report(r | delta, 175)

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
            n.save(p, {'status': 'FILE_READY', 'output_sha256': 'a'*64, 'file_uri': n.API+'/v1beta/files/test',
                       'duration_seconds': 175})
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
        self.assertLess(w.index('Persist interaction ID'), w.index('native_review_recovery.py poll'))
        self.assertLess(w.index('Refuse duplicate'), w.index('secrets.'))
        self.assertNotIn('APPROVAL.json', w)
        self.assertNotIn('path: ${{ runner.temp }}/native-review/receipt.json', w)
        self.assertIn('native-review/receipt.cms', w)


class PublicEvidence(unittest.TestCase):
    """E233: a score must not exist only inside a receipt encrypted to one executor's key."""

    I = {'plan': 'migration/production/bible/plans/genesis-09-short.json', 'sha256': 'b' * 64}
    PRIVATE = {'interaction_id': 'v1_SyntheticInteraction_abc123', 'file_name': 'files/synthfile42',
               'file_uri': n.API + '/v1beta/files/synthfile42',
               'upload_url': n.API + '/upload/v1beta/files?upload_id=SYNTHuploadTOKEN',
               'response_body_base64': 'eyJzZWNyZXQiOiJyYXcifQ==', 'response_sha256': 'c' * 64}

    def report(self):
        scores = {k: 9.6 for k in n.RUBRIC}
        scores['audio_clarity_and_mix'] = 8.0
        return {'audio_received': True, 'visual_received': True, 'duration_seconds': 175,
                'scores': scores, 'overall': 9.1,
                'issues': ['01:54.28 Music swells over the narration in files/synthfile42 '
                           'see https://example.invalid/x?key=AIzaSyntheticKeyValue123456'],
                'limitations': ['Sampled at 4 fps'], 'criterion_issues': {'audio_clarity_and_mix': [0],
                                                                         'overall': [0]},
                'coverage': [{'start': 0, 'end': 175, 'speech_excerpt': 'secret heard words here'}]}

    def test_e233_public_evidence_has_scores_and_timed_issues_without_private_fields(self):
        r = dict(self.PRIVATE, status='EVIDENCE_COMPLETE', reviewed_at='2026-10-31T20:00:00+00:00',
                 report=self.report(), response_text=json.dumps(self.report()))
        p = n.public_evidence(self.I, r, '999')
        self.assertTrue(p['report_validated'])
        self.assertEqual(p['overall'], 9.1)
        self.assertEqual(p['scores']['audio_clarity_and_mix'], 8.0)
        self.assertEqual(set(p['scores']), set(n.RUBRIC))
        self.assertEqual(p['criterion_issues'], {'audio_clarity_and_mix': [0], 'overall': [0]})
        self.assertTrue(p['issues'][0].startswith('01:54.28 Music swells'))
        self.assertFalse(p['owner_floor_met'])
        self.assertFalse(p['production_approved'])
        self.assertFalse(p['publication_ready'])
        text = json.dumps(p)
        for secret in ('SyntheticInteraction', 'synthfile42', 'SYNTHuploadTOKEN', 'eyJzZWNyZXQ',
                       'AIzaSynthetic', 'example.invalid', 'secret heard words', 'c' * 64):
            self.assertNotIn(secret, text)
        for field in ('interaction_id', 'file_name', 'file_uri', 'upload_url', 'response_text',
                      'response_body_base64', 'provider_response', 'coverage_segments', 'report'):
            self.assertNotIn(field, p)

    def test_e233_unvalidated_report_is_exposed_but_never_passes(self):
        good = self.report()
        good['overall'] = 9.8
        good['scores'] = {k: 9.8 for k in n.RUBRIC}
        r = dict(self.PRIVATE, status='COMPLETE_UNVALIDATED', response_text='```json\n' + json.dumps(good) + '\n```')
        p = n.public_evidence(self.I, r, '1000')
        self.assertFalse(p['report_validated'])
        self.assertEqual(p['overall'], 9.8)
        self.assertFalse(p['owner_floor_met'])
        self.assertFalse(p['every_criterion_at_least_9_5'])

    def test_e233_provider_failure_publishes_only_error_codes(self):
        response = {'id': self.PRIVATE['interaction_id'], 'status': 'failed',
                    'errors': [{'code': 'INTERNAL', 'message': 'detail with files/synthfile42'}]}
        r = dict(self.PRIVATE, status='PROVIDER_FAILED', provider_response=response)
        p = n.public_evidence(dict(self.I, recover_submitted_run='41157848418'), r, '41197695635')
        self.assertEqual(p['provider_error_codes'], ['INTERNAL'])
        self.assertEqual(p['provider_status'], 'failed')
        self.assertEqual(p['source_run_id'], '41157848418')
        self.assertNotIn('scores', p)
        self.assertNotIn('synthfile42', json.dumps(p))
        self.assertNotIn('detail with', json.dumps(p))

    def test_e233_missing_receipt_and_summary_file(self):
        with tempfile.TemporaryDirectory() as d:
            summary = Path(d) / 'summary.md'
            with patch.dict(os.environ, {'GITHUB_RUN_ID': '7', 'GITHUB_STEP_SUMMARY': str(summary)}):
                p = n.write_public(self.I, Path(d) / 'absent.json', Path(d) / 'out')
                self.assertEqual(p['status'], 'NO_RECEIPT')
                receipt = Path(d) / 'receipt.json'
                n.save(receipt, dict(self.PRIVATE, status='EVIDENCE_COMPLETE', report=self.report()))
                p = n.write_public(self.I, receipt, Path(d) / 'out')
            stored = json.loads((Path(d) / 'out' / 'public-evidence.json').read_text())
            self.assertEqual(stored, p)
            md = summary.read_text()
            self.assertIn('audio_clarity_and_mix | 8.0', md)
            self.assertIn('01:54.28', md)
            self.assertNotIn('synthfile42', md)

    def test_e233_workflow_always_publishes_public_evidence_after_readback(self):
        w = (ROOT / '.github/workflows/native-review.yml').read_text()
        step = w.split('- name: Write public score evidence', 1)[1].split('- name:', 1)[0]
        self.assertIn('if: always()', step)
        self.assertIn('native_review.py public', step)
        self.assertNotIn('secrets.', step)
        upload = w.split('- name: Preserve public score evidence', 1)[1].split('- name:', 1)[0]
        self.assertIn('if: always()', upload)
        self.assertIn('native-review-public/public-evidence.json', upload)
        self.assertIn('retention-days: 90', upload)
        self.assertLess(w.rindex('native_review_recovery.py poll'), w.index('Write public score evidence'))
        self.assertLess(w.index('Delete provider media'), w.index('Write public score evidence'))
        self.assertNotIn('contents: write', w)


if __name__ == '__main__':
    unittest.main()
