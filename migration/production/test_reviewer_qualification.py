#!/usr/bin/env python3
"""Safety boundaries for the isolated reviewer; no network, secrets or real QA."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reviewer_qualification as q


class Response(io.BytesIO):
    status = 200


class Qualification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = 'unit-test-key-not-a-real-credential'
        self.clock = q.utc('2026-10-22T16:15:00Z')
        observation = json.loads((q.ROOT / q.OBSERVATION).read_text())
        credential_policy = {'key_sha256': hashlib.sha256(self.key.encode()).hexdigest()}
        for path, data in [(q.OBSERVATION, json.dumps(observation).encode()),
                           (q.CREDENTIAL_POLICY, json.dumps(credential_policy).encode()),
                           (q.MANIFEST, (q.ROOT / q.MANIFEST).read_bytes())]:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.report = {k: 9.2 for k in q.sr.RUBRIC}
        self.report.update(overall=9.2, issues=[], strongest_moment='00:20 original example')
        self.envelope = {'model': q.MODEL, 'status': 'completed', 'steps': [
            {'type': 'model_output', 'content': [{'type': 'text', 'text': json.dumps(self.report)}]}],
            'usage': {'total_input_tokens': 100, 'input_tokens_by_modality': [
                {'modality': 'audio', 'tokens': 10}, {'modality': 'video', 'tokens': 80}]}}
        self.payload = {'contents': [{'parts': [
            {'fileData': {'fileUri': q.sr.BASE + '/v1beta/files/test', 'mimeType': 'video/mp4'}},
            {'text': 'The unchanged production rubric.'}]}], 'generationConfig': {
                'maxOutputTokens': 4096, 'responseSchema': {'type': 'OBJECT', 'properties': {'overall': {'type': 'NUMBER'}}}}}

    def policy(self):
        p = q.ReviewHTTPPolicy(cutoff_utc=q.now() + timedelta(seconds=600))
        p.begin()
        return p

    def call(self, envelope=None):
        inference = q.InteractionInference()
        with patch.object(q.urllib.request, 'urlopen', return_value=Response(json.dumps(envelope or self.envelope).encode())) as send:
            result = inference(self.payload, self.key, [q.MODEL], http_policy=self.policy())
        return inference, result, send

    def test_rotated_key_stale_paid_or_unbound_project_cannot_reach_provider(self):
        q.validate_inputs(self.root, self.key, self.clock)
        with self.assertRaisesRegex(ValueError, 'KEY_MISMATCH'):
            q.validate_inputs(self.root, 'rotated', self.clock)
        with self.assertRaisesRegex(ValueError, 'OBSERVATION_STALE'):
            q.validate_inputs(self.root, self.key, self.clock + timedelta(days=1))
        path = self.root / q.OBSERVATION
        original = json.loads(path.read_text())
        for field, value in [('billing_account_present', True), ('tier', 'PAID'), ('key_project_binding_verified', False)]:
            with self.subTest(field=field):
                path.write_text(json.dumps({**original, field: value}))
                with self.assertRaises(ValueError):
                    q.validate_inputs(self.root, self.key, self.clock)

    def test_manifest_change_blocks_even_if_new_manifest_declares_pass(self):
        with (self.root / q.MANIFEST).open('a') as f:
            f.write(' ')
        with self.assertRaisesRegex(ValueError, 'MANIFEST_CHANGED'):
            q.validate_inputs(self.root, self.key, self.clock)

    def test_reservation_replay_or_unavailable_history_fails_closed(self):
        for data in ({'total_count': 1, 'artifacts': [{'name': q.START_ARTIFACT}]}, {},
                     {'total_count': 0, 'artifacts': [{}]}):
            with patch.object(q, 'github_json', return_value=data):
                with self.assertRaisesRegex(ValueError, 'QUALIFICATION_ALREADY_RESERVED'):
                    q.require_unused_reservation('test-token')
        with patch.object(q, 'github_json', return_value={'total_count': 0, 'artifacts': []}):
            q.require_unused_reservation('test-token')

    def test_real_request_is_full_video_same_prompt_single_call_and_stateless(self):
        inference, result, send = self.call()
        request = send.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, q.ENDPOINT)
        self.assertNotIn(self.key, request.full_url)
        self.assertEqual(body['input'][0]['uri'], self.payload['contents'][0]['parts'][0]['fileData']['fileUri'])
        self.assertEqual(body['input'][1]['text'], 'The unchanged production rubric.')
        self.assertEqual(body['input'][0]['processing'], {'type': 'static', 'fps': 1})
        self.assertTrue(all(body[k] is False for k in ('store', 'background', 'stream')))
        self.assertNotIn('tools', body)
        self.assertEqual(result, (q.MODEL, self.report))
        self.assertEqual(send.call_count, 1)
        self.assertEqual(len(inference.response_evidence['usage']['input_tokens_by_modality']), 2)

    def test_incomplete_other_model_invalid_scores_and_model_invented_audit_rejected(self):
        candidates = []
        for field, value in [('status', 'incomplete'), ('status', 'in_progress'), ('model', 'another-model')]:
            candidates.append({**self.envelope, field: value})
        for field, value in [('overall', True), ('picture_quality', float('nan')), ('edit_rhythm', 11),
                             ('transport_attempts', [{'http_status': 200}])]:
            candidate = deepcopy(self.envelope)
            candidate['steps'][0]['content'][0]['text'] = json.dumps({**self.report, field: value})
            candidates.append(candidate)
        duplicate = deepcopy(self.envelope)
        duplicate['steps'][0]['content'][0]['text'] = '{"overall":9,"overall":10}'
        candidates.append(duplicate)
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                with self.assertRaises(q.ProviderFailure):
                    self.call(candidate)

    def test_503_has_one_attempt_no_retry_sleep_and_no_error_prose(self):
        error = urllib.error.HTTPError(q.ENDPOINT, 503, 'private text', {},
                 io.BytesIO(b'{"error":{"code":503,"status":"UNAVAILABLE","message":"private text"}}'))
        policy = self.policy()
        with patch.object(q.urllib.request, 'urlopen', side_effect=error) as send, patch.object(policy, 'wait') as sleep:
            with self.assertRaises(q.ProviderFailure):
                q.InteractionInference()(self.payload, self.key, [q.MODEL], http_policy=policy)
        self.assertEqual(send.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(policy._trace[0]['http_status'], 503)
        self.assertNotIn('private text', json.dumps(policy.audit()))

    def test_shared_review_reuses_hash_and_deletes_file_without_invoking_qa(self):
        media = self.root / 'short-00.mp4'
        media.write_bytes(b'test media bytes')
        digest = q.sr.output_digest(media)
        record = {'hook': 'Test hook', 'qa_output_sha256': digest}
        policy = self.policy()
        # review owns begin(), so pass a fresh policy to the shared function.
        policy._started = None
        with patch.object(q.sr, 'upload', return_value={'name': 'files/test', 'uri': 'test-uri'}), \
             patch.object(q.sr, 'request') as cleanup, patch.object(q.sr.shorts_qa, 'check', create=True, side_effect=AssertionError('QA_REPEATED')):
            review = q.sr.review(media, record, self.key, http_policy=policy,
                                 inference=lambda *a, **kw: (q.MODEL, deepcopy(self.report)))
        self.assertEqual(review['output_sha256'], digest)
        self.assertEqual(policy._cleanup, 'SUCCESS')
        self.assertEqual(cleanup.call_args.kwargs['method'], 'DELETE')
        self.assertEqual(q.sr.output_digest(media), digest)

    def test_isolated_result_keeps_individual_floor_and_never_changes_manifest(self):
        output = self.root / 'result'
        output.mkdir()
        media = output / 'short-00.mp4'
        media.write_bytes(b'isolated media fixture')
        digest = q.sr.output_digest(media)
        manifest_path = self.root / q.MANIFEST
        manifest = json.loads(manifest_path.read_text())
        record = next(s for s in manifest['shorts'] if s['file'] == 'short-00.mp4')
        record['sha256'] = record['qa_output_sha256'] = digest
        manifest_path.write_text(json.dumps(manifest))
        manifest_before = manifest_path.read_bytes()
        observation_path = self.root / q.OBSERVATION
        observation = json.loads(observation_path.read_text())
        observation.update(observed_at=q.now().isoformat(), expires_at=(q.now() + timedelta(hours=23)).isoformat())
        observation_path.write_text(json.dumps(observation))
        env = {'GITHUB_REPOSITORY': q.REPO, 'GITHUB_REF': 'refs/heads/main',
               'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_RUN_ID': '123', 'GITHUB_SHA': 'a' * 40,
               'HERO_GEMINI_API_KEY': self.key}
        q.write(output / 'receipt.json', {'state': 'STARTED', 'mode': 'review', 'qualification_id': q.QUALIFICATION,
                'run_id': '123', 'repository_sha': 'a' * 40,
                'project_observation_sha256': hashlib.sha256(observation_path.read_bytes()).hexdigest()})
        rejected = deepcopy(self.envelope)
        rejected['steps'][0]['content'][0]['text'] = json.dumps({**self.report, 'edit_rhythm': 6.8})
        with patch.object(q, 'ROOT', self.root), patch.object(q, 'MEDIA_SHA', digest), \
             patch.object(q, 'MEDIA_BYTES', media.stat().st_size), \
             patch.object(q, 'MANIFEST_SHA', hashlib.sha256(manifest_before).hexdigest()), \
             patch.object(q.sr, 'upload', return_value={'name': 'files/test', 'uri': 'test-uri'}), \
             patch.object(q.sr, 'request'), \
             patch.object(q.urllib.request, 'urlopen', return_value=Response(json.dumps(rejected).encode())) as send:
            result = q.infer(output, env)
            self.assertEqual(result['state'], 'REVIEWED')
            self.assertEqual(result['review']['status'], 'FAIL')
            self.assertEqual(result['qualification_result'], 'REJECTED_MASTER')
            self.assertFalse(result['publish'])
            self.assertEqual(result['inference_requests'], 1)
            with self.assertRaisesRegex(ValueError, 'ATTEMPT_UNBOUND'):
                q.infer(output, env)
            self.assertEqual(send.call_count, 1)
        self.assertEqual(manifest_path.read_bytes(), manifest_before)

    def test_restarted_workflow_or_non_main_fails_before_any_network(self):
        env = {'GITHUB_REPOSITORY': q.REPO, 'GITHUB_REF': 'refs/heads/main', 'GITHUB_RUN_ATTEMPT': '2'}
        with patch.object(q.urllib.request, 'urlopen') as send:
            with self.assertRaisesRegex(ValueError, 'REPLAY_BLOCKED'):
                q.prepare(self.root / 'out', 'review', env)
            env['GITHUB_REF'] = 'refs/heads/other'
            with self.assertRaisesRegex(ValueError, 'MAIN_ONLY'):
                q.prepare(self.root / 'out', 'review', env)
        send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
