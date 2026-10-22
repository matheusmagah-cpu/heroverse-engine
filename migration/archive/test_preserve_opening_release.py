"""Offline tests: mocked GitHub metadata and synthetic local files only."""
import contextlib
import hashlib
import io
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import preserve_opening_release as p


def validate_workflow_contexts(source):
    """Focused expression-context lint for this workflow, beyond YAML syntax.

    GitHub context availability table, reviewed 2026-10-15:
    https://docs.github.com/en/actions/reference/workflows-and-actions/contexts
    This is not a general GitHub Actions or actionlint implementation.
    """
    prefix, steps = source.split('    steps:\n', 1)
    # Conservative subset supported at ALL job-level keys present here.
    # In particular runner and env are unavailable at jobs.<id>.env.
    job_allowed = {'github', 'needs', 'vars', 'inputs'}
    step_allowed = {'github', 'needs', 'strategy', 'matrix', 'job', 'runner',
                    'env', 'vars', 'secrets', 'steps', 'inputs'}
    for section, allowed in [(prefix, job_allowed), (steps, step_allowed)]:
        for expression in re.findall(r'\$\{\{(.*?)\}\}', section, flags=re.S):
            for context in re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*)\.', expression):
                if context not in allowed:
                    raise ValueError('DISALLOWED_CONTEXT:' + context)
    if 'runner.temp' in prefix:
        raise ValueError('RUNNER_CONTEXT_AT_JOB_LEVEL')
    return True


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.asset = {'id': 123, 'name': p.NAME, 'size': p.NATIVE_BYTES,
                      'digest': 'sha256:' + p.NATIVE_SHA, 'state': 'uploaded'}
        self.source = {'id': p.ARTIFACT_ID, 'expired': False,
                       'workflow_run': {'id': p.SOURCE_RUN},
                       'size_in_bytes': p.ARCHIVE_BYTES,
                       'digest': 'sha256:' + p.ARCHIVE_SHA}
        self.env = {'GITHUB_REPOSITORY': p.REPO, 'GITHUB_EVENT_NAME': 'workflow_dispatch',
                    'GITHUB_RUN_NUMBER': '2', 'GITHUB_RUN_ATTEMPT': '1',
                    'GITHUB_REF': 'refs/heads/main', 'GH_TOKEN': 'synthetic-test-token',
                    'GITHUB_OUTPUT': str(self.root / 'output')}

    def test_environment_accepts_only_first_manual_main(self):
        with patch.dict(os.environ, self.env, clear=True):
            p.environment()
            for key, bad in [('GITHUB_REPOSITORY', 'someone/fork'),
                             ('GITHUB_EVENT_NAME', 'push'), ('GITHUB_RUN_NUMBER', '1'),
                             ('GITHUB_RUN_ATTEMPT', '2'), ('GITHUB_REF', 'refs/heads/other'),
                             ('GH_TOKEN', '')]:
                with self.subTest(key=key), patch.dict(os.environ, {key: bad}):
                    with self.assertRaises(ValueError):
                        p.environment()

    def test_asset_identity_and_missing_digest_fail_closed(self):
        self.assertEqual(p.verify_asset(self.asset), self.asset)
        for key, bad in [('name', 'other.mp4'), ('size', 1), ('digest', None),
                         ('digest', 'sha256:wrong'), ('state', 'starter'), ('id', None)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.verify_asset(dict(self.asset, **{key: bad}))

    def metadata(self, assets=None, private=True, tag=None):
        return [{'full_name': p.REPO, 'private': private},
                {'id': p.RELEASE_ID, 'tag_name': p.TAG if tag is None else tag,
                 'draft': False, 'upload_url': p.UPLOAD + '{?name,label}'},
                [] if assets is None else assets]

    def test_destination_missing_is_not_uploaded(self):
        with patch.object(p, 'api', side_effect=self.metadata()) as api:
            self.assertIsNone(p.destination())
            self.assertEqual(api.call_count, 3)

    def test_destination_reuses_identical_asset(self):
        with patch.object(p, 'api', side_effect=self.metadata([self.asset])):
            self.assertEqual(p.destination(), self.asset)

    def test_destination_rejects_public_repo(self):
        with patch.object(p, 'api', side_effect=self.metadata(private=False)), self.assertRaises(ValueError):
            p.destination()

    def test_destination_rejects_wrong_release(self):
        with patch.object(p, 'api', side_effect=self.metadata(tag='other')), self.assertRaises(ValueError):
            p.destination()

    def test_destination_conflict_does_not_delete_or_overwrite(self):
        with patch.object(p, 'api', side_effect=self.metadata([dict(self.asset, size=1)])) as api:
            with self.assertRaises(ValueError):
                p.destination()
            self.assertTrue(all(not call.kwargs for call in api.call_args_list))

    def test_destination_duplicate_name_is_blocked(self):
        with patch.object(p, 'api', side_effect=self.metadata([self.asset, self.asset])), self.assertRaises(ValueError):
            p.destination()

    def test_source_requires_exact_nonexpired_artifact(self):
        with patch.object(p, 'api', return_value=self.source):
            self.assertEqual(p.source_metadata(), self.source)
        for key, bad in [('id', 1), ('expired', True), ('workflow_run', {'id': 2}),
                         ('size_in_bytes', p.LIMIT), ('digest', None)]:
            with self.subTest(key=key), patch.object(p, 'api', return_value=dict(self.source, **{key: bad})):
                with self.assertRaises(ValueError):
                    p.source_metadata()

    def fixture(self):
        nested = self.root / 'actual-prefix' / 'observed-layout'
        nested.mkdir(parents=True)
        file = nested / 'native.mp4'
        file.write_bytes(b'synthetic-av')
        return file

    def test_discovers_actual_nested_path_without_guessing(self):
        file = self.fixture()
        with patch.object(p, 'NATIVE_BYTES', 12), patch.object(p, 'NATIVE_SHA', hashlib.sha256(b'synthetic-av').hexdigest()):
            actual, audit = p.discover_native(self.root)
        self.assertEqual(actual, file)
        self.assertEqual(audit['native_relative_path'], 'actual-prefix/observed-layout/native.mp4')
        self.assertEqual(audit['native_realpath'], str(file.resolve()))

    def test_missing_or_wrong_native_hash_is_blocked(self):
        self.fixture()
        with self.assertRaises(ValueError):
            p.discover_native(self.root)

    def test_symlinks_are_blocked(self):
        self.fixture()
        (self.root / 'link').symlink_to('/tmp')
        with self.assertRaisesRegex(ValueError, 'SYMLINK'):
            p.discover_native(self.root)

    def test_root_symlink_is_blocked(self):
        link = self.root / 'link'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'RESTORE_ROOT'):
            p.discover_native(link)

    def test_size_bound_is_strict(self):
        self.fixture()
        with patch.object(p, 'LIMIT', 12), self.assertRaisesRegex(ValueError, 'BOUND'):
            p.discover_native(self.root)

    def test_file_count_bound(self):
        for number in range(65):
            (self.root / str(number)).touch()
        with self.assertRaisesRegex(ValueError, 'BOUND'):
            p.discover_native(self.root)

    def test_duplicate_native_is_blocked(self):
        file = self.fixture()
        (self.root / 'duplicate.mp4').write_bytes(file.read_bytes())
        with patch.object(p, 'NATIVE_BYTES', 12), patch.object(p, 'NATIVE_SHA', hashlib.sha256(b'synthetic-av').hexdigest()):
            with self.assertRaisesRegex(ValueError, 'NOT_UNIQUE'):
                p.discover_native(self.root)

    def test_preflight_reuse_skips_source_and_download(self):
        with patch.dict(os.environ, self.env), patch.object(p, 'destination', return_value=self.asset), patch.object(p, 'source_metadata') as source, patch.object(p, 'receipt'):
            p.preflight()
        source.assert_not_called()
        self.assertEqual((self.root / 'output').read_text(), 'needs_transfer=false\n')

    def test_preflight_missing_checks_source_before_download(self):
        with patch.dict(os.environ, self.env), patch.object(p, 'destination', return_value=None), patch.object(p, 'source_metadata') as source:
            p.preflight()
        source.assert_called_once()
        self.assertEqual((self.root / 'output').read_text(), 'needs_transfer=true\n')

    def test_transfer_reconciles_before_any_post(self):
        with patch.object(p, 'destination', return_value=self.asset), patch.object(p, 'api') as api, patch.object(p, 'receipt', return_value='reused'):
            self.assertEqual(p.transfer(self.root), 'reused')
        api.assert_not_called()

    def test_transfer_one_post_then_reconciliation(self):
        file = self.fixture()
        with patch.object(p, 'destination', side_effect=[None, self.asset]), patch.object(p, 'source_metadata'), patch.object(p, 'discover_native', return_value=(file, {'native_relative_path': 'actual'})), patch.object(p, 'api', return_value=self.asset) as api, patch.object(p, 'receipt') as receipt:
            p.transfer(self.root)
        api.assert_called_once_with(p.UPLOAD + '?name=' + p.NAME, upload=file)
        self.assertEqual(receipt.call_args.args[0], 'stored')

    def test_ambiguous_post_never_retries(self):
        file = self.fixture()
        with patch.object(p, 'destination', return_value=None), patch.object(p, 'source_metadata'), patch.object(p, 'discover_native', return_value=(file, {})), patch.object(p, 'api', side_effect=TimeoutError) as api, patch.object(p, 'receipt') as receipt:
            with self.assertRaises(TimeoutError):
                p.transfer(self.root)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(receipt.call_args.args[0], 'upload_outcome_ambiguous_reconcile_do_not_repeat')

    def test_unverified_post_or_reconciliation_never_claims_stored(self):
        file = self.fixture()
        for response, reconcile in [(dict(self.asset, digest=None), self.asset), (self.asset, None)]:
            with self.subTest(response=response), patch.object(p, 'destination', side_effect=[None, reconcile]), patch.object(p, 'source_metadata'), patch.object(p, 'discover_native', return_value=(file, {})), patch.object(p, 'api', return_value=response) as api, patch.object(p, 'receipt') as receipt:
                with self.assertRaises(ValueError):
                    p.transfer(self.root)
                self.assertEqual(api.call_count, 1)
                self.assertNotIn('stored', [c.args[0] for c in receipt.call_args_list])

    def test_api_blocks_foreign_destination(self):
        with patch.object(p.subprocess, 'run') as run, self.assertRaises(ValueError):
            p.api('https://example.com/upload')
        run.assert_not_called()

    def test_receipt_has_no_authority_expansion(self):
        with patch.object(Path, 'write_text') as write, contextlib.redirect_stdout(io.StringIO()), patch.dict(os.environ, {}, clear=True):
            value = p.receipt('reused', self.asset)
        for field in ['production', 'publication', 'supervisor', 'full_av_qa_repeated', 'binary_through_chat', 'git_media_blob_created', 'upload_retry_allowed']:
            self.assertIs(value[field], False)
        self.assertEqual(value['provider_calls'], 0)
        self.assertIn('github_asset_id', json.loads(write.call_args.args[0]))

    def live_failed_run(self):
        return {'id': p.FAILED_RUN, 'head_sha': p.FAILED_SHA, 'run_number': 1,
                'run_attempt': 1, 'event': 'push', 'head_branch': 'main',
                'status': 'completed', 'conclusion': 'failure'}

    def test_prior_receipt_and_live_zero_job_failure_are_required(self):
        with patch.object(p, 'api', side_effect=[self.live_failed_run(), {'total_count': 0, 'jobs': []}]) as api:
            saved = p.verify_prior_validation_failure()
        self.assertEqual(saved['run_id'], 38777882037)
        self.assertEqual(api.call_count, 2)
        self.assertIn('filter=all', api.call_args.args[0])

    def test_prior_receipt_missing_or_tampered_stops_before_api(self):
        with patch.object(p, 'api') as api:
            with self.assertRaises(FileNotFoundError):
                p.verify_prior_validation_failure(self.root / 'absent.json')
            saved = json.loads(p.FAILURE_RECEIPT.read_text())
            for key, bad in [('head_sha', 'different'), ('jobs_count', 1),
                             ('replacement_run_number', 3), ('rerun_of_upload_job_allowed', True)]:
                receipt = self.root / 'failure.json'
                receipt.write_text(json.dumps(dict(saved, **{key: bad})))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    p.verify_prior_validation_failure(receipt)
        api.assert_not_called()

    def test_prior_live_run_cannot_have_jobs_or_different_identity(self):
        for jobs in [{'total_count': 1, 'jobs': [{}]}, {'total_count': 0, 'jobs': [{}]}, {}]:
            with self.subTest(jobs=jobs), patch.object(p, 'api', side_effect=[self.live_failed_run(), jobs]):
                with self.assertRaises(ValueError):
                    p.verify_prior_validation_failure()
        for key, bad in [('id', 2), ('head_sha', 'other'), ('run_attempt', 2),
                         ('event', 'workflow_dispatch'), ('conclusion', 'success')]:
            with self.subTest(key=key), patch.object(p, 'api', return_value=dict(self.live_failed_run(), **{key: bad})):
                with self.assertRaises(ValueError):
                    p.verify_prior_validation_failure()

    def test_main_blocks_preflight_and_upload_when_prior_receipt_fails(self):
        for mode in ['preflight', 'transfer']:
            with patch.object(p, 'environment'), patch.object(p, 'verify_prior_validation_failure', side_effect=ValueError), patch.object(p, 'preflight') as preflight, patch.object(p, 'transfer') as transfer, patch.object(p.sys, 'argv', ['script', mode]):
                with self.assertRaises(ValueError):
                    p.main()
                preflight.assert_not_called()
                transfer.assert_not_called()

    def test_only_run_two_attempt_one_is_permitted(self):
        with patch.dict(os.environ, self.env, clear=True):
            for number in ['1', '3', '4', '', '02']:
                with self.subTest(number=number), patch.dict(os.environ, {'GITHUB_RUN_NUMBER': number}):
                    with self.assertRaises(ValueError):
                        p.environment()
            with patch.dict(os.environ, {'GITHUB_RUN_ATTEMPT': '2'}), self.assertRaises(ValueError):
                p.environment()

    def workflow_source(self):
        return (Path(__file__).resolve().parents[1] / '.github/workflows/preserve-opening-release.yml').read_text()

    def test_actual_workflow_expression_contexts(self):
        self.assertTrue(validate_workflow_contexts(self.workflow_source()))

    def test_context_lint_rejects_original_runner_job_env_bug(self):
        broken = self.workflow_source().replace('    steps:\n',
                  '    env:\n      OPENING_RESTORE_ROOT: ${{ runner.temp }}/native-opening-11983614696\n    steps:\n')
        with self.assertRaisesRegex(ValueError, 'DISALLOWED_CONTEXT:runner'):
            validate_workflow_contexts(broken)

    def test_runner_temp_export_precedes_use_and_follows_preflight(self):
        source = self.workflow_source()
        export = source.index("run: printf 'OPENING_RESTORE_ROOT=%s/native-opening-11983614696")
        self.assertIn('"$RUNNER_TEMP" >> "$GITHUB_ENV"', source)
        self.assertLess(source.index('preserve_opening_release.py preflight'), export)
        self.assertLess(export, source.index('mkdir -m 700 "$OPENING_RESTORE_ROOT"'))
        self.assertLess(export, source.index('path: ${{ env.OPENING_RESTORE_ROOT }}'))
        self.assertIn('migration/opening-validation-failure.json', source)
        self.assertIn('test "$NUMBER" = 2', source)
        self.assertIn('test "$ATTEMPT" = 1', source)


if __name__ == '__main__':
    unittest.main()
