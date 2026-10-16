import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import build_c01
import probe

KEY = 'offline-synthetic-key-never-real'
MEDIA = b'\x00\x00\x00\x20ftypisom' + b'offline-fixture' * 4
PREFLIGHT = {'sha256': hashlib.sha256(MEDIA).hexdigest(), 'size_bytes': len(MEDIA)}
NAME = 'files/c01-fixture'
URL = probe.UPLOAD_ENDPOINT + '?upload_id=offline-session&upload_protocol=resumable'


def metadata(state='ACTIVE'):
    return {'name': NAME, 'state': state, 'mimeType': 'video/mp4', 'sizeBytes': str(len(MEDIA)),
            'sha256Hash': base64.b64encode(hashlib.sha256(MEDIA).digest()).decode(),
            'uri': probe.ORIGIN + '/v1beta/' + NAME, 'videoMetadata': {'videoDuration': '6.000s'}}


def receipt():
    return {'upload_start_calls': 0, 'bytes_upload_calls': 0, 'metadata_get_calls': 0,
            'generate_content_calls': 0, 'count_tokens_calls': 0, 'delete_calls': 0}


class FakeClock:
    def __init__(self): self.now = 0
    def monotonic(self): return self.now
    def sleep(self, seconds): self.now += seconds


class FakeTransport:
    def __init__(self, states=None, error_at=None):
        self.calls = []
        self.states = list(states or [metadata()])
        self.error_at = error_at
    def __call__(self, method, url, *, headers, body=None, timeout=15):
        probe.validate_request(method, url, headers, body)
        self.calls.append((method, url, headers, body, timeout))
        if len(self.calls) == self.error_at:
            raise probe.ProviderFailure('HTTP_503')
        if len(self.calls) == 1:
            return {'upload_url': URL}, {}
        current = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return {}, {'file': current} if method == 'POST' else current


class DeliveryTests(unittest.TestCase):
    def run_delivery(self, send=None):
        send = send or FakeTransport()
        r, saved, clock = receipt(), [], FakeClock()
        result = probe.deliver(MEDIA, PREFLIGHT, api_key=KEY, receipt=r,
            checkpoint=lambda v: saved.append(copy.deepcopy(v)), send=send,
            monotonic=clock.monotonic, sleep=clock.sleep)
        return result, send, saved, clock
    def test_success_one_upload_and_no_inference(self):
        r, send, saved, _ = self.run_delivery()
        self.assertEqual(r['status'], 'PASS_FILES_DELIVERY_ONLY')
        self.assertEqual(r['remote_verification']['sha256'], PREFLIGHT['sha256'])
        self.assertEqual([c[0] for c in send.calls], ['POST', 'POST'])
        self.assertEqual(send.calls[0][3], b'{"file":{"displayName":"c01.mp4"}}')
        self.assertEqual(send.calls[1][3], MEDIA)
        self.assertEqual(r['upload_start_calls'], 1)
        self.assertEqual(r['bytes_upload_calls'], 1)
        self.assertEqual(r['generate_content_calls'], 0)
        self.assertEqual(r['count_tokens_calls'], 0)
        self.assertNotIn(KEY, json.dumps(saved))
        self.assertNotIn('offline-session', json.dumps(saved))
        self.assertNotIn('sha256Hash', json.dumps(saved))
        self.assertEqual(saved[0]['stage'], 'UPLOAD_START_REQUESTED')
        self.assertEqual(saved[1]['stage'], 'BYTES_UPLOAD_REQUESTED')
    def test_processing_then_active(self):
        r, send, saved, clock = self.run_delivery(FakeTransport([metadata('PROCESSING'), metadata()]))
        self.assertEqual(r['metadata_get_calls'], 1)
        self.assertEqual(clock.now, 5)
        self.assertEqual(send.calls[-1][0], 'GET')
        self.assertIsNone(send.calls[-1][3])
    def test_poll_deadline_never_reuploads(self):
        send, clock, r = FakeTransport([metadata('PROCESSING')]), FakeClock(), receipt()
        with self.assertRaisesRegex(probe.ProviderFailure, 'METADATA_POLL_DEADLINE'):
            probe.deliver(MEDIA, PREFLIGHT, api_key=KEY, receipt=r, checkpoint=lambda _: None,
                          send=send, monotonic=clock.monotonic, sleep=clock.sleep)
        self.assertLessEqual(clock.now, 120)
        self.assertLessEqual(r['metadata_get_calls'], 24)
        self.assertEqual(r['bytes_upload_calls'], 1)
        self.assertEqual(sum(c[0] == 'POST' for c in send.calls), 2)
    def test_failed_processing_stops(self):
        send = FakeTransport([metadata('FAILED')])
        with self.assertRaisesRegex(probe.ProviderFailure, 'REMOTE_PROCESSING_FAILED'):
            self.run_delivery(send)
        self.assertEqual(len(send.calls), 2)
    def test_unknown_state_stops(self):
        with self.assertRaisesRegex(probe.ProviderFailure, 'REMOTE_STATE_UNRECOGNIZED'):
            self.run_delivery(FakeTransport([metadata('STATE_UNSPECIFIED')]))
    def test_network_failure_never_retries(self):
        for number in (1, 2, 3):
            with self.subTest(number=number):
                send = FakeTransport([metadata('PROCESSING')], error_at=number)
                with self.assertRaisesRegex(probe.ProviderFailure, 'HTTP_503'):
                    self.run_delivery(send)
                self.assertEqual(len(send.calls), number)
    def test_checkpoint_failure_prevents_first_request(self):
        send = FakeTransport()
        with self.assertRaises(OSError):
            probe.deliver(MEDIA, PREFLIGHT, api_key=KEY, receipt=receipt(),
                          checkpoint=lambda _: (_ for _ in ()).throw(OSError('local failure')), send=send)
        self.assertFalse(send.calls)
    def test_bad_session_url_prevents_bytes(self):
        calls = []
        def send(*args, **kwargs):
            calls.append(args)
            return {'upload_url': 'https://attacker.invalid/?key=' + KEY}, {}
        with self.assertRaisesRegex(probe.ProviderFailure, 'UPLOAD_URL_REJECTED'):
            self.run_delivery(send)
        self.assertEqual(len(calls), 1)
    def test_missing_key_prevents_network(self):
        send = FakeTransport()
        for key in ('', 'x\n' * 30, 'é' * 30):
            with self.assertRaisesRegex(probe.ProviderFailure, 'SECRET_MISSING_OR_MALFORMED'):
                probe.deliver(MEDIA, PREFLIGHT, api_key=key, receipt=receipt(), checkpoint=lambda _: None, send=send)
        self.assertFalse(send.calls)
    def test_remote_id_changes_stop(self):
        changed = metadata(); changed['name'] = 'files/other'
        with self.assertRaisesRegex(probe.ProviderFailure, 'REMOTE_IDENTITY_CHANGED'):
            self.run_delivery(FakeTransport([metadata('PROCESSING'), changed]))


class MetadataTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(probe.verify_remote(metadata(), PREFLIGHT, NAME)['all_four_metadata_checks_passed'])
    def test_mismatch_each_required_field(self):
        replacements = [('mimeType', 'audio/mp4', 'MIME'), ('sizeBytes', '999', 'SIZE'),
                        ('sha256Hash', base64.b64encode(b'x' * 32).decode(), 'HASH'),
                        ('videoMetadata', {'videoDuration': '7s'}, 'DURATION'),
                        ('uri', 'https://other.invalid/file', 'URI'), ('state', 'PROCESSING', 'NOT_ACTIVE')]
        for field, value, code in replacements:
            with self.subTest(field=field):
                m = metadata(); m[field] = value
                with self.assertRaisesRegex(probe.ProviderFailure, code):
                    probe.verify_remote(m, PREFLIGHT, NAME)
    def test_missing_hash_or_invalid_base64_not_accepted(self):
        for value in ('', '%%%%', base64.b64encode(PREFLIGHT['sha256'].encode()).decode()):
            m = metadata(); m['sha256Hash'] = value
            with self.assertRaises(probe.ProviderFailure): probe.verify_remote(m, PREFLIGHT, NAME)
    def test_duration_precision_bound(self):
        for value in ('NaNs', '6e0s', '-6s', '6.0000000000s', '6.035s', None):
            m = metadata(); m['videoMetadata']['videoDuration'] = value
            with self.assertRaises(probe.ProviderFailure): probe.verify_remote(m, PREFLIGHT, NAME)
    def test_one_frame_duration_tolerance(self):
        m = metadata(); m['videoMetadata']['videoDuration'] = '6.033333333s'
        self.assertTrue(probe.verify_remote(m, PREFLIGHT, NAME)['all_four_metadata_checks_passed'])
    def test_metadata_is_not_inference_evidence(self):
        r, *_ = DeliveryTests().run_delivery()
        self.assertEqual(r['model_understanding'], 'NOT_TESTED')


class SecurityTests(unittest.TestCase):
    def test_upload_url_allowlist(self):
        for url in ('http://generativelanguage.googleapis.com/upload/v1beta/files?upload_id=x',
                    probe.UPLOAD_ENDPOINT + '?upload_id=x&key=secret',
                    probe.UPLOAD_ENDPOINT + '?upload_id=x&upload_id=y',
                    probe.UPLOAD_ENDPOINT + '?upload_id=x#fragment',
                    'https://generativelanguage.googleapis.com.evil.invalid/upload/v1beta/files?upload_id=x',
                    'https://user@generativelanguage.googleapis.com/upload/v1beta/files?upload_id=x',
                    'https://generativelanguage.googleapis.com:444/upload/v1beta/files?upload_id=x',
                    probe.ORIGIN + '/v1beta/models/x:generateContent?upload_id=x',
                    probe.UPLOAD_ENDPOINT + '?upload_id=x%0Aheader', None):
            with self.subTest(url=url), self.assertRaises(probe.ProviderFailure):
                probe.validate_upload_url(url)
    def test_no_generation_count_delete_list_or_arbitrary_url(self):
        for method, url in [('POST', probe.ORIGIN + '/v1beta/models/gemini-3.8-flash:generateContent'),
                            ('POST', probe.ORIGIN + '/v1beta/models/gemini-3.8-flash:countTokens'),
                            ('DELETE', probe.ORIGIN + '/v1beta/' + NAME),
                            ('GET', probe.ORIGIN + '/v1beta/files'), ('GET', 'https://example.com')]:
            with self.subTest(method=method, url=url), self.assertRaises(probe.ProviderFailure):
                probe.validate_request(method, url, {}, None)
    def test_redirect_handler_declines(self):
        self.assertIsNone(probe.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid'))
    def test_transport_disables_proxy_and_redacts_http_errors(self):
        error = urllib.error.HTTPError('https://url-with-secret/' + KEY, 403, KEY, {}, io.BytesIO(KEY.encode()))
        with patch.object(urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = error
            with self.assertRaisesRegex(probe.ProviderFailure, '^HTTP_403$'):
                probe.transport('GET', probe.ORIGIN + '/v1beta/' + NAME, headers={'x-goog-api-key': KEY})
            self.assertEqual(build.call_args.args[0].proxies, {})
            self.assertIsInstance(build.call_args.args[1], probe.NoRedirect)
            self.assertEqual(build.return_value.open.call_count, 1)
    def test_transport_redacts_exception_text(self):
        with patch.object(urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = ValueError(KEY)
            with self.assertRaisesRegex(probe.ProviderFailure, '^NETWORK_OR_RESPONSE_FAILED_NO_RETRY$'):
                probe.transport('GET', probe.ORIGIN + '/v1beta/' + NAME, headers={'x-goog-api-key': KEY})
    def test_response_limit(self):
        with patch.object(urllib.request, 'build_opener') as build:
            response = build.return_value.open.return_value.__enter__.return_value
            response.status = 200; response.read.return_value = b'x' * (probe.MAX_RESPONSE + 1)
            with self.assertRaisesRegex(probe.ProviderFailure, 'RESPONSE_SIZE_LIMIT'):
                probe.transport('GET', probe.ORIGIN + '/v1beta/' + NAME, headers={'x-goog-api-key': KEY})
    def test_invalid_requests_never_open_transport(self):
        with patch.object(urllib.request, 'build_opener') as build:
            with self.assertRaises(probe.ProviderFailure):
                probe.transport('GET', 'https://other.invalid', headers={})
            build.assert_not_called()
    def test_boundary_private_main_attempt_and_workflow(self):
        env = {'GITHUB_REPOSITORY': 'matheusmagah-cpu/heroverse-engine', 'HERO_REPOSITORY_PRIVATE': 'true',
               'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
               'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_RUN_NUMBER': '1', 'GITHUB_SHA': 'a' * 40,
               'GITHUB_WORKFLOW_REF': 'matheusmagah-cpu/heroverse-engine/.github/workflows/gemini-files-delivery-once.yml@refs/heads/main'}
        probe.check_boundary(env)
        for key in env:
            with self.subTest(key=key), self.assertRaises(probe.ProviderFailure):
                probe.check_boundary({**env, key: 'invalid'})
    def test_signal_budget_restored(self):
        import signal
        old = signal.getsignal(signal.SIGALRM)
        with probe.wall_budget(120): self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0], 0)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0, 0))
        self.assertEqual(signal.getsignal(signal.SIGALRM), old)


class MainSafetyTests(unittest.TestCase):
    def test_prior_receipt_is_preserved_without_key_read_or_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'gemini-files-delivery-output'; root.mkdir()
            prior = b'{"prior": "preserve exactly"}\n'
            (root / 'receipt.json').write_bytes(prior)
            cwd = Path.cwd()
            try:
                os.chdir(tmp)
                with patch.object(probe, 'deliver') as deliver, patch.object(probe, 'verify_local') as verify:
                    self.assertEqual(probe.main(), 1)
                    deliver.assert_not_called(); verify.assert_not_called()
                self.assertEqual((root / 'receipt.json').read_bytes(), prior)
            finally: os.chdir(cwd)
    def test_prior_unresolved_claim_is_preserved_and_blocks_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'gemini-files-delivery-output'; root.mkdir()
            (root / 'attempt-claim.json').write_text('{"previous": true}')
            cwd = Path.cwd()
            try:
                os.chdir(tmp)
                with patch.object(probe, 'deliver') as deliver:
                    self.assertEqual(probe.main(), 1)
                    deliver.assert_not_called()
                self.assertFalse((root / 'receipt.json').exists())
            finally: os.chdir(cwd)


class RecipeTests(unittest.TestCase):
    def test_exact_preserved_recipe_and_positive_late_control(self):
        recipe = build_c01.load_recipe()
        self.assertEqual(recipe.CASES[0], ('c01.mp4', 'audio_late_500ms', True, .5))
        self.assertEqual(recipe.SECONDS, 6)
        self.assertEqual(recipe.FLASH_STARTS, [1, 3, 5])
    def test_new_output_required(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'NEW_OUTPUT_DIRECTORY_REQUIRED'):
            build_c01.build(Path(tmp))
    def test_local_media_tampering_fails_before_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'stimuli').mkdir(); (root / 'operator-only').mkdir()
            (root / 'stimuli/c01.mp4').write_bytes(MEDIA)
            manifest = {'all_checks_passed': True, 'files': [{'filename': 'c01.mp4', 'sha256': PREFLIGHT['sha256'],
                'size_bytes': len(MEDIA), 'verification': 'PASS', 'video': {'duration_seconds': 6},
                'audio': {'duration_seconds': 6, 'nominal_audio_shift_seconds': .5}}]}
            mr = json.dumps(manifest).encode(); (root / 'operator-only/manifest.json').write_bytes(mr)
            pf = {**PREFLIGHT, 'version': 'heroverse-gemini-files-preflight-v1', 'filename': 'c01.mp4',
                  'mime_type': 'video/mp4', 'duration_seconds': 6, 'nominal_audio_onset_minus_flash_seconds': .5,
                  'pixels_and_pcm_verified': True, 'all_checks_passed': True,
                  'recipe_source_sha256': build_c01.RECIPE_SHA256, 'manifest_sha256': hashlib.sha256(mr).hexdigest()}
            (root / 'preflight.json').write_text(json.dumps(pf))
            self.assertEqual(probe.verify_local(root)[0], MEDIA)
            (root / 'stimuli/c01.mp4').write_bytes(MEDIA + b'tamper')
            with self.assertRaisesRegex(probe.ProviderFailure, 'LOCAL_INPUT_BINDING_FAILED'): probe.verify_local(root)


if __name__ == '__main__': unittest.main()
