#!/usr/bin/env python3
"""Offline failure-evidence tests. No provider, upload, render or live pilot input."""
import ast
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shorts_review as sr  # noqa: E402
import structure_mining as sm
from structure_mining import ProviderFailure  # noqa: E402

FIXED_TIME = datetime(2026, 10, 20, 16, 0, 1, 234567, tzinfo=timezone.utc)
ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
AST_HASHES = {
    "RUBRIC": "a9f4a2814b3a057bc237b760c4e437beb4e4c68945bce4762115ace72a63d3df",
    "(PASS_ITEM, PASS_OVERALL)": "9faefc6c3f12db24b6336abfb39645318ba2be395a416107b47c1c5f9fff3e4d",
    "REVIEW_MODELS": "0dc4e3b2023fe31acf07963cdc9f6a2d54f47015ae5076ed5c294d7154be6c40",
    "review.prompt": "873c0d83930f6f33ddc829c60ac37a79bc201a356522b0f14e63a2eda94b2854",
}


class OfflineTest(unittest.TestCase):
    def setUp(self):
        # Any overlooked network/render path fails, rather than reaching a real provider.
        self.addCleanup(patch.stopall)
        patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK_FORBIDDEN")).start()
        patch("subprocess.run", side_effect=AssertionError("RENDER_FORBIDDEN")).start()
        self.clock = patch.object(sr, "datetime").start()
        self.clock.now.return_value = FIXED_TIME
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "short-00.mp4"
        # Synthetic byte fixtures only, not generated or approved video.
        self.output.write_bytes(b"abc")


class FailureEvidence(OfflineTest):
    def test_known_provider_failures_have_categorical_evidence(self):
        cases = [
            ("HTTP_503_UNAVAILABLE", 503, "UNAVAILABLE"),
            ("HTTP_429_RESOURCE_EXHAUSTED:QUOTA", 429, "RESOURCE_EXHAUSTED"),
            ("HTTP_400_INVALID_ARGUMENT", 400, "INVALID_ARGUMENT"),
        ]
        for code, status, provider in cases:
            with self.subTest(code=code):
                diagnostic = {"http_status": status, "provider_status": provider,
                              "body_truncated": False, "raw_body_retained": False,
                              "sanitized": True, "body_parse_status": "JSON_ERROR_OBJECT",
                              "body_bytes_read": 125}
                result = sr.failure_record(ProviderFailure(code, diagnostic), self.output)
                self.assertEqual(result, {
                    "status": "NOT_REVIEWED_ProviderFailure", "error_code": code,
                    "provider_diagnostic": diagnostic, "failed_at": FIXED_TIME.isoformat(),
                    "output_sha256": ABC_SHA256,
                })
        self.clock.now.assert_called_with(timezone.utc)

    def test_closed_error_code_allowlist(self):
        accepted = [
            "PROVIDER_CALL_FAILED", "NO_FREE_MODEL", "UNPARSEABLE_MODEL_OUTPUT",
            "HTTP_100_", "HTTP_599_:QUOTA",
        ]
        statuses = ("INVALID_ARGUMENT", "UNAUTHENTICATED", "PERMISSION_DENIED",
                    "NOT_FOUND", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
        accepted += [f"HTTP_400_{s}{quota}" for s in statuses for quota in ("", ":QUOTA")]
        rejected = [
            None, True, 503, [], {}, "503", "HTTP_099_UNAVAILABLE", "HTTP_600_UNAVAILABLE",
            "HTTP_503_UNKNOWN", "HTTP_503_UNAVAILABLE:RETRY", "HTTP_503_UNAVAILABLE\n",
            "prefix_HTTP_503_UNAVAILABLE", "HTTP_503", "PROVIDER_CALL_FAILED:QUOTA",
            "PROVIDER_RESPONSE_TOO_LARGE", "https://private.invalid/secret",
            "HTTP_429_RESOURCE_EXHAUSTED:QUOTA quota prose",
        ]
        for code in accepted + rejected:
            with self.subTest(code=code):
                result = sr.failure_record(ProviderFailure(code), self.output)
                self.assertEqual(result["error_code"], code if code in accepted else "UNKNOWN")
                self.assertEqual(result["provider_diagnostic"], {})

    def test_unparseable_output_is_explicit_not_a_fabricated_http_cause(self):
        result = sr.failure_record(ProviderFailure("UNPARSEABLE_MODEL_OUTPUT"), self.output)
        self.assertEqual(result["error_code"], "UNPARSEABLE_MODEL_OUTPUT")
        self.assertEqual(result["provider_diagnostic"], {})

    def test_http_and_runtime_exception_prose_is_never_parsed(self):
        errors = [
            urllib.error.HTTPError("https://private.invalid/secret", 503, "UNAVAILABLE", {}, None),
            RuntimeError("HTTP_429_RESOURCE_EXHAUSTED:QUOTA secret-password"),
            RuntimeError("HTTP_503_UNAVAILABLE"),
        ]
        for error in errors:
            with self.subTest(error_type=type(error).__name__):
                result = sr.failure_record(error, self.output)
                self.assertEqual(result["error_code"], "UNKNOWN")
                self.assertEqual(result["provider_diagnostic"], {})
                self.assertEqual(result["status"], f"NOT_REVIEWED_{type(error).__name__}")
                for forbidden in ("private", "secret", "UNAVAILABLE", "QUOTA"):
                    self.assertNotIn(forbidden, json.dumps(result))

    def test_exception_string_is_not_called(self):
        class OpaqueFailure(Exception):
            def __str__(self):
                raise AssertionError("Do not parse exception strings")
        result = sr.failure_record(OpaqueFailure(), self.output)
        self.assertEqual(result["error_code"], "UNKNOWN")

    def test_projection_drops_prose_urls_fields_quota_and_nested_secrets(self):
        diagnostic = {
            "http_status": 429, "provider_status": "RESOURCE_EXHAUSTED",
            "body_truncated": True, "raw_body_retained": False, "sanitized": True,
            "body_parse_status": "JSON_ERROR_OBJECT", "body_bytes_read": 12000,
            "message": "secret-password https://private.invalid/token",
            "fielddescription": "sensitive", "description": "sensitive",
            "field_violations": [{"description": "secret-password", "field": "private"}],
            "quota_ids": ["private quota"], "retry_delay": "20s",
            "raw_body": "PRIVATE", "url": "https://private.invalid",
            "nested": {"secret": "PRIVATE"}, "diagnostic_size_limited": True,
        }
        result = sr.failure_record(ProviderFailure("HTTP_429_RESOURCE_EXHAUSTED:QUOTA", diagnostic), self.output)
        self.assertEqual(result["provider_diagnostic"], {
            "http_status": 429, "provider_status": "RESOURCE_EXHAUSTED",
            "body_truncated": True, "raw_body_retained": False, "sanitized": True,
            "body_parse_status": "JSON_ERROR_OBJECT", "body_bytes_read": 8193,
        })
        serialized = json.dumps(result)
        for forbidden in ("secret", "https", "private", "PRIVATE", "message", "field", "retry", "quota_ids"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(diagnostic["body_bytes_read"], 12000, "Projection must not mutate the input")

    def test_exact_types_disallow_booleans_as_integers_and_nested_values(self):
        values = [None, True, False, "503", 503.0, [], {}, {"secret": "PRIVATE"}]
        for value in values:
            with self.subTest(value=value):
                malformed = {"http_status": value, "provider_status": value,
                             "body_parse_status": value, "body_bytes_read": value}
                self.assertEqual(sr.failure_record(ProviderFailure("NO_FREE_MODEL", malformed),
                                                   self.output)["provider_diagnostic"], {})
        for value in (None, 0, 1, "true", [], {"secret": "PRIVATE"}):
            with self.subTest(boolean=value):
                malformed = {k: value for k in ("body_truncated", "raw_body_retained", "sanitized")}
                self.assertEqual(sr.failure_record(ProviderFailure("NO_FREE_MODEL", malformed),
                                                   self.output)["provider_diagnostic"], {})
        for diagnostic in (None, True, [], ["secret"], "message", 5):
            with self.subTest(diagnostic=diagnostic):
                self.assertEqual(sr.failure_record(ProviderFailure("NO_FREE_MODEL", diagnostic),
                                                   self.output)["provider_diagnostic"], {})

    def test_diagnostic_numeric_boundaries_and_parse_enums(self):
        for status in (99, 100, 599, 600):
            with self.subTest(status=status):
                safe = sr.failure_record(ProviderFailure("NO_FREE_MODEL", {"http_status": status}),
                                         self.output)["provider_diagnostic"]
                self.assertEqual(safe, {"http_status": status} if 100 <= status <= 599 else {})
        for count, expected in ((-1, 0), (0, 0), (8192, 8192), (8193, 8193), (8194, 8193), (10**100, 8193)):
            with self.subTest(count=count):
                safe = sr.failure_record(ProviderFailure("NO_FREE_MODEL", {"body_bytes_read": count}),
                                         self.output)["provider_diagnostic"]
                self.assertEqual(safe, {"body_bytes_read": expected})
        for value in ("NOT_PARSED", "INVALID_JSON_OR_SHAPE", "JSON_ERROR_OBJECT"):
            safe = sr.failure_record(ProviderFailure("NO_FREE_MODEL", {"body_parse_status": value}),
                                     self.output)["provider_diagnostic"]
            self.assertEqual(safe, {"body_parse_status": value})

    def test_digest_is_of_actual_bytes_and_changes_with_them(self):
        error = ProviderFailure("NO_FREE_MODEL")
        self.assertEqual(sr.failure_record(error, self.output)["output_sha256"], ABC_SHA256)
        same_bytes = self.root / "different-name.mp4"
        same_bytes.write_bytes(b"abc")
        self.assertEqual(sr.failure_record(error, same_bytes)["output_sha256"], ABC_SHA256)
        self.output.write_bytes(b"abcd")
        result = sr.failure_record(error, self.output)
        self.assertEqual(result["output_sha256"], hashlib.sha256(b"abcd").hexdigest())
        self.assertNotEqual(result["output_sha256"], ABC_SHA256)

    def test_unreadable_or_missing_file_has_explicit_null_and_category_only(self):
        paths = (None, self.root / "secret-path.mp4", self.root)
        for path in paths:
            with self.subTest(path_kind=type(path).__name__):
                result = sr.failure_record(RuntimeError("secret"), path)
                self.assertIsNone(result["output_sha256"])
                self.assertEqual(result["output_hash_error"], "FILE_UNREADABLE")
                self.assertEqual(result["status"], "NOT_REVIEWED_RuntimeError")
                self.assertNotIn(str(self.root), json.dumps(result))
                self.assertNotIn("secret", json.dumps(result))
        with patch.object(Path, "open", side_effect=PermissionError("secret-path")):
            result = sr.failure_record(RuntimeError("secret"), self.output)
        self.assertIsNone(result["output_sha256"])
        self.assertEqual(result["output_hash_error"], "FILE_UNREADABLE")

    def test_hash_failure_is_categorical_without_exception_text(self):
        with patch.object(sr.hashlib, "sha256", side_effect=RuntimeError("secret hash failure")):
            result = sr.failure_record(ProviderFailure("NO_FREE_MODEL"), self.output)
        self.assertIsNone(result["output_sha256"])
        self.assertEqual(result["output_hash_error"], "FILE_UNREADABLE")
        self.assertNotIn("secret", json.dumps(result))


class ReviewIntegration(OfflineTest):
    def run_main(self, records, *, qa="PASS", qa_effect=None, review_result=None, review_error=None,
                 key="fake-offline-key", n="3"):
        spec_path = self.root / "shorts.json"
        spec_path.write_text(json.dumps({"shorts": records}))
        with patch.dict(sr.os.environ, {"HERO_GEMINI_API_KEY": key}), \
                patch.object(sr.shorts_qa, "check", return_value={"status": qa}, side_effect=qa_effect), \
                patch.object(sr, "review", return_value=review_result, side_effect=review_error) as reviewer, \
                patch.object(sr, "call", side_effect=AssertionError("PROVIDER_FORBIDDEN")) as provider, \
                patch.object(sr, "upload", side_effect=AssertionError("UPLOAD_FORBIDDEN")) as upload, \
                patch("builtins.print"):
            sr.main(str(self.root), n)
        return json.loads(spec_path.read_text()), reviewer, provider, upload

    def record(self, **fields):
        return {"file": self.output.name, "publish": True, "hook": "You can rest.",
                "output_sha256": "forged-record-sha256", "selection": {"final_score": 999}, **fields}

    def test_main_failure_is_not_publishable_and_ignores_forged_record_sha(self):
        error = ProviderFailure("HTTP_503_UNAVAILABLE", {"http_status": 503, "provider_status": "UNAVAILABLE"})
        spec, reviewer, provider, upload = self.run_main([self.record()], review_error=error)
        record = spec["shorts"][0]
        reviewer.assert_called_once()
        provider.assert_not_called()
        upload.assert_not_called()
        self.assertFalse(record["publish"])
        self.assertEqual(record["review"]["status"], "NOT_REVIEWED_ProviderFailure")
        self.assertEqual(record["review"]["error_code"], "HTTP_503_UNAVAILABLE")
        self.assertEqual(record["review"]["output_sha256"], ABC_SHA256)
        self.assertEqual(record["qa_output_sha256"], ABC_SHA256)
        self.assertEqual(record["review"]["failed_at"], FIXED_TIME.isoformat())
        self.output.write_bytes(b"modified")
        spec, _, _, _ = self.run_main([self.record()], review_error=error)
        self.assertEqual(spec["shorts"][0]["review"]["output_sha256"], hashlib.sha256(b"modified").hexdigest())

    def test_qa_failure_never_attempts_review_or_provider(self):
        spec, reviewer, provider, upload = self.run_main([self.record()], qa="FAIL")
        reviewer.assert_not_called()
        provider.assert_not_called()
        upload.assert_not_called()
        self.assertEqual(spec["shorts"][0]["review"], {"status": "NOT_REVIEWED_QA_FAIL"})
        self.assertFalse(spec["shorts"][0]["publish"])

    def test_missing_key_never_attempts_review_or_provider(self):
        spec, reviewer, provider, upload = self.run_main([self.record()], key="")
        reviewer.assert_not_called()
        provider.assert_not_called()
        upload.assert_not_called()
        self.assertEqual(spec["shorts"][0]["review"], {"status": "NOT_REVIEWED_NO_KEY"})
        self.assertFalse(spec["shorts"][0]["publish"])

    def test_failure_does_not_erase_previous_editorial_fail_or_add_attempts(self):
        previous = {"status": "FAIL", "overall": 6, "ending_and_loop": 4,
                    "issues": ["Ending is abrupt at 00:31."]}
        spec, reviewer, _, _ = self.run_main([self.record(review=previous)],
                                           review_error=ProviderFailure("HTTP_503_UNAVAILABLE"))
        reviewer.assert_called_once()
        record = spec["shorts"][0]
        self.assertEqual(record["previous_editorial_review"], previous)
        self.assertEqual(record["review"]["status"], "NOT_REVIEWED_ProviderFailure")
        self.assertFalse(record["publish"])
        spec, reviewer, _, _ = self.run_main([record], review_error=RuntimeError("historic cause unknown"))
        reviewer.assert_called_once()
        self.assertEqual(spec["shorts"][0]["previous_editorial_review"], previous)
        self.assertEqual(spec["shorts"][0]["review"]["error_code"], "UNKNOWN")
        self.assertFalse(spec["shorts"][0]["publish"])

    def test_missing_output_on_failure_remains_not_reviewed_and_not_publishable(self):
        self.output.unlink()
        spec, reviewer, provider, upload = self.run_main(
            [self.record()], qa_effect=AssertionError("QA must not run on unreadable input"),
            review_error=RuntimeError("file secret-path"))
        record = spec["shorts"][0]
        self.assertFalse(record["publish"])
        self.assertEqual(record["review"]["status"], "NOT_REVIEWED_FILE_UNREADABLE")
        self.assertIsNone(record["review"]["output_sha256"])
        self.assertIsNone(record["qa_output_sha256"])
        self.assertEqual(record["review"]["output_hash_error"], "FILE_UNREADABLE")
        reviewer.assert_not_called()
        provider.assert_not_called()
        upload.assert_not_called()

    def test_publication_selection_stays_score_ordered_and_capped(self):
        records = [
            self.record(file="a.mp4", selection={"final_score": 1}),
            self.record(file="b.mp4", selection={"final_score": 3}),
            self.record(file="c.mp4", selection={"final_score": 999}),
            self.record(file="d.mp4", selection={"final_score": 2}),
        ]
        reviews = [{"status": "PASS", "overall": 9.6}, {"status": "PASS", "overall": 9.6},
                   {"status": "FAIL", "overall": 10}, {"status": "PASS", "overall": 8}]
        for record, verdict in zip(records, reviews):
            (self.root / record["file"]).write_bytes(b"abc")
            verdict["output_sha256"] = ABC_SHA256
            verdict["model"] = "gemini-3.8-flash"
        spec, reviewer, _, _ = self.run_main(records, review_error=reviews, n="2")
        self.assertEqual(reviewer.call_count, 4)
        self.assertEqual([r["file"] for r in spec["shorts"] if r["publish"]], ["a.mp4", "b.mp4"])

    def test_owner_floor_does_not_rewrite_editorial_pass(self):
        verdict = {"status": "PASS", "overall": 8.5, "model": "gemini-3.8-flash", "output_sha256": ABC_SHA256}
        spec, _, _, _ = self.run_main([self.record()], review_result=verdict)
        record = spec["shorts"][0]
        self.assertEqual(record["review"], verdict)
        self.assertFalse(record["publish"])
        self.assertEqual(record["owner_quality_policy"]["status"], "FAIL")
        self.assertEqual(spec["review_rubric"]["pass_overall"], 8)

    def test_qa_digest_is_recomputed_instead_of_trusting_record(self):
        verdict = {"status": "PASS", "overall": 9.6, "model": "gemini-3.8-flash", "output_sha256": ABC_SHA256}
        spec, reviewer, _, _ = self.run_main(
            [self.record(qa_output_sha256="e" * 64)], review_result=verdict)
        record = spec["shorts"][0]
        self.assertEqual(record["qa_output_sha256"], ABC_SHA256)
        self.assertEqual(record["review"]["output_sha256"], ABC_SHA256)
        self.assertTrue(record["publish"])
        reviewer.assert_called_once()

    def test_changed_or_unreadable_during_qa_skips_review_and_is_not_bound(self):
        for unreadable in (False, True):
            with self.subTest(unreadable=unreadable):
                self.output.write_bytes(b"abc")
                def qa(path):
                    self.output.unlink() if unreadable else self.output.write_bytes(b"changed")
                    return {"status": "PASS"}
                spec, reviewer, provider, upload = self.run_main(
                    [self.record(qa_output_sha256=ABC_SHA256)], qa_effect=qa)
                record = spec["shorts"][0]
                self.assertFalse(record["publish"])
                self.assertIsNone(record["qa_output_sha256"])
                expected = "FILE_UNREADABLE" if unreadable else "OUTPUT_CHANGED"
                self.assertEqual(record["review"]["status"], "NOT_REVIEWED_" + expected)
                self.assertNotIn("overall", record["review"])
                reviewer.assert_not_called()
                provider.assert_not_called()
                upload.assert_not_called()

    def test_change_between_qa_and_review_is_rejected_before_upload(self):
        original_review = sr.review
        def changed(path, record, key):
            self.output.write_bytes(b"changed")
            return original_review(path, record, key)
        spec, reviewer, provider, upload = self.run_main([self.record()], review_error=changed)
        record = spec["shorts"][0]
        self.assertFalse(record["publish"])
        self.assertEqual(record["qa_output_sha256"], ABC_SHA256)
        self.assertEqual(record["review"]["status"], "NOT_REVIEWED_QA_OUTPUT_HASH_MISMATCH")
        reviewer.assert_called_once()
        provider.assert_not_called()
        upload.assert_not_called()

    def test_copied_stale_or_missing_verdict_hash_is_not_rebound(self):
        for status in ("PASS", "FAIL"):
            for stale_hash in (None, "e" * 64):
                with self.subTest(status=status, stale_hash=stale_hash):
                    copied = {"status": status, "overall": 9.6}
                    if stale_hash is not None:
                        copied["output_sha256"] = stale_hash
                    before = dict(copied)
                    spec, reviewer, _, _ = self.run_main([self.record(review=copied)], review_result=copied)
                    record = spec["shorts"][0]
                    self.assertFalse(record["publish"])
                    self.assertEqual(record["review"]["status"], "NOT_REVIEWED_REVIEW_OUTPUT_HASH_MISMATCH")
                    self.assertEqual(record["qa_output_sha256"], ABC_SHA256)
                    self.assertEqual(copied, before, "Never stamp a copied verdict with the current digest")
                    reviewer.assert_called_once()

    def test_output_changed_after_review_does_not_keep_temporary_pass(self):
        for unreadable in (False, True):
            with self.subTest(unreadable=unreadable):
                self.output.write_bytes(b"abc")
                def changed(path, record, key):
                    self.output.unlink() if unreadable else self.output.write_bytes(b"changed")
                    return {"status": "PASS", "overall": 9.6, "output_sha256": ABC_SHA256}
                spec, reviewer, _, _ = self.run_main([self.record()], review_error=changed)
                record = spec["shorts"][0]
                self.assertFalse(record["publish"])
                expected = "FILE_UNREADABLE" if unreadable else "QA_OUTPUT_HASH_MISMATCH"
                self.assertEqual(record["review"]["status"], "NOT_REVIEWED_" + expected)
                self.assertNotIn("overall", record["review"])
                reviewer.assert_called_once()

    def test_watched_review_calls_only_designated_model_once_and_cleans_up(self):
        uploaded = {"uri": "https://offline.invalid/file", "name": "files/offline"}
        for score, overall, expected in ((7, 8, "PASS"), (6, 8, "FAIL"), (7, 7, "FAIL")):
            scores = {**{k: score for k in sr.RUBRIC}, "overall": overall, "issues": []}
            with self.subTest(score=score, overall=overall), \
                    patch.object(sr, "upload", return_value=uploaded), \
                    patch.object(sr, "call", return_value=(sr.REVIEW_MODELS[0], scores)) as provider, \
                    patch.object(sr, "request") as cleanup:
                result = sr.review(self.output, self.record(), "fake-offline-key")
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["output_sha256"], ABC_SHA256)
            provider.assert_called_once()
            self.assertEqual(provider.call_args.args[2], list(sr.REVIEW_MODELS))
            cleanup.assert_called_once_with(sr.BASE + "/v1beta/files/offline", "fake-offline-key", method="DELETE")

    def test_provider_failure_has_no_outer_retry_and_still_cleans_up(self):
        uploaded = {"uri": "https://offline.invalid/file", "name": "files/offline"}
        with patch.object(sr, "upload", return_value=uploaded), \
                patch.object(sr, "call", side_effect=ProviderFailure("HTTP_503_UNAVAILABLE")) as provider, \
                patch.object(sr, "request") as cleanup:
            with self.assertRaises(ProviderFailure):
                sr.review(self.output, self.record(), "fake-offline-key")
        provider.assert_called_once()
        cleanup.assert_called_once()

    def test_frozen_prompt_rubric_threshold_and_model_ast(self):
        tree = ast.parse((HERE / "shorts_review.py").read_text())
        nodes = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                target = ast.unparse(node.targets[0])
                if target in AST_HASHES:
                    nodes[target] = node
            if isinstance(node, ast.FunctionDef) and node.name == "review":
                for child in ast.walk(node):
                    if isinstance(child, ast.Assign) and ast.unparse(child.targets[0]) == "prompt":
                        nodes["review.prompt"] = child
        self.assertEqual(set(nodes), set(AST_HASHES))
        for name, node in nodes.items():
            with self.subTest(node=name):
                self.assertEqual(hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
                                 AST_HASHES[name])
        self.assertEqual((sr.PASS_ITEM, sr.PASS_OVERALL), (7, 8))
        self.assertEqual(sr.REVIEW_MODELS, ("gemini-3.8-flash",))


class ReviewBinding(OfflineTest):
    def verdict(self, score=9):
        return {**{k: score for k in sr.RUBRIC}, "overall": score, "issues": []}

    def record(self):
        return {"hook": "You can rest.", "output_sha256": "f" * 64,
                "review": {"status": "PASS", "output_sha256": "e" * 64, "overall": 10}}

    def exercise_review(self, *, score=9, on_upload=None, on_call=None, on_cleanup=None):
        def upload(*args):
            if on_upload:
                on_upload()
            return {"uri": "https://offline.invalid/file", "name": "files/offline"}

        def call(*args):
            if on_call:
                on_call()
            return sr.REVIEW_MODELS[0], self.verdict(score)

        with patch.object(sr, "upload", side_effect=upload) as upload_spy, \
                patch.object(sr, "call", side_effect=call) as provider, \
                patch.object(sr, "request", side_effect=on_cleanup) as cleanup:
            result = sr.review(self.output, self.record(), "fake-offline-key")
        return result, upload_spy, provider, cleanup

    def assert_unbound(self, result, reason, digest):
        self.assertEqual(result["status"], f"NOT_REVIEWED_{reason}")
        self.assertFalse(result["publish"])
        self.assertEqual(result["output_sha256"], digest)
        self.assertEqual(result["failed_at"], FIXED_TIME.isoformat())
        self.assertNotIn("overall", result)
        self.assertNotIn("model", result)
        self.assertFalse(set(sr.RUBRIC) & set(result))

    def test_fresh_pass_and_fail_bind_actual_bytes_not_record_supplied_hash(self):
        for score, status in ((9, "PASS"), (6, "FAIL")):
            with self.subTest(status=status):
                result, upload, provider, cleanup = self.exercise_review(score=score)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["output_sha256"], ABC_SHA256)
                self.assertEqual(result["model"], sr.REVIEW_MODELS[0])
                upload.assert_called_once()
                provider.assert_called_once()
                cleanup.assert_called_once()
        self.assertEqual(self.record()["review"]["output_sha256"], "e" * 64)

    def test_altered_during_upload_skips_provider_and_cleans_up(self):
        result, upload, provider, cleanup = self.exercise_review(on_upload=lambda: self.output.write_bytes(b"changed"))
        self.assert_unbound(result, "OUTPUT_CHANGED", hashlib.sha256(b"changed").hexdigest())
        upload.assert_called_once()
        provider.assert_not_called()
        cleanup.assert_called_once()

    def test_altered_during_provider_cannot_return_pass_or_fail_and_never_retries(self):
        for score in (9, 6):
            with self.subTest(score=score):
                self.output.write_bytes(b"abc")
                result, upload, provider, cleanup = self.exercise_review(
                    score=score, on_call=lambda: self.output.write_bytes(b"changed"))
                self.assert_unbound(result, "OUTPUT_CHANGED", hashlib.sha256(b"changed").hexdigest())
                upload.assert_called_once()
                provider.assert_called_once()
                cleanup.assert_called_once()

    def test_altered_during_cleanup_cannot_return_editorial_verdict(self):
        result, _, provider, cleanup = self.exercise_review(
            on_cleanup=lambda *args, **kwargs: self.output.write_bytes(b"changed"))
        self.assert_unbound(result, "OUTPUT_CHANGED", hashlib.sha256(b"changed").hexdigest())
        provider.assert_called_once()
        cleanup.assert_called_once()

    def test_unreadable_before_upload_skips_all_remote_actions(self):
        self.output.unlink()
        result, upload, provider, cleanup = self.exercise_review()
        self.assert_unbound(result, "FILE_UNREADABLE", None)
        self.assertEqual(result["output_hash_error"], "FILE_UNREADABLE")
        upload.assert_not_called()
        provider.assert_not_called()
        cleanup.assert_not_called()
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_unreadable_during_upload_skips_provider_and_cleans_up(self):
        result, upload, provider, cleanup = self.exercise_review(on_upload=self.output.unlink)
        self.assert_unbound(result, "FILE_UNREADABLE", None)
        upload.assert_called_once()
        provider.assert_not_called()
        cleanup.assert_called_once()

    def test_unreadable_after_provider_cannot_return_editorial_verdict(self):
        result, upload, provider, cleanup = self.exercise_review(on_call=self.output.unlink)
        self.assert_unbound(result, "FILE_UNREADABLE", None)
        upload.assert_called_once()
        provider.assert_called_once()
        cleanup.assert_called_once()


class HTTPReviewIntegration(OfflineTest):
    """Full client integration using synthetic bytes and intercepted HTTP only."""
    def setUp(self):
        super().setUp()
        self.elapsed = 0.0
        self.utc = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        patch.object(sm.time, "monotonic", side_effect=lambda: self.elapsed).start()
        patch.object(sm, "review_utc_now", side_effect=lambda: self.utc).start()
        self.sleeper = patch.object(sm.time, "sleep", side_effect=self.advance).start()
        patch("socket.create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")).start()
        self.events, self.payloads, self.effects = [], [], {}
        self.initial_state = "ACTIVE"
        self.polls = 0
        self.active_on_poll = 1
        self.generations = []
        self.urlopen = patch("urllib.request.urlopen", side_effect=self.http).start()
        self.addCleanup(sm.USAGE.clear)

    def advance(self, seconds, utc_seconds=None):
        self.elapsed += seconds
        self.utc += timedelta(seconds=seconds if utc_seconds is None else utc_seconds)

    def verdict(self, overall=9.6):
        return {**{name: overall for name in sr.RUBRIC}, "overall": overall, "issues": [], "strongest_moment": "synthetic"}

    def response(self, value=None, headers=None, raw=None):
        return HTTPResponse(json.dumps(value or {}).encode() if raw is None else raw, headers)

    def generated(self, score=9, extra=None):
        return self.response({"candidates": [{"content": {"parts": [{"text": json.dumps(self.verdict(score) | (extra or {}))}]}}]})

    def error(self, status=503, after=None):
        headers = {} if after is None else {"Retry-After": after}
        return urllib.error.HTTPError("https://offline.invalid/secret", status, "secret", headers,
                io.BytesIO(json.dumps({"error": {"status": "UNAVAILABLE", "message": "secret https://private.invalid"}}).encode()))

    def http(self, request, timeout):
        if request.get_method() == "DELETE":
            stage = "DELETE"
            result = self.response()
        elif request.full_url.endswith("/upload/v1beta/files"):
            stage = "UPLOAD_START"
            result = self.response(headers={"X-Goog-Upload-URL": "https://offline.invalid/upload-finalize"})
        elif request.full_url.endswith("/upload-finalize"):
            stage = "UPLOAD_FINALIZE"
            result = self.response({"file": {"name": "files/offline", "uri": "https://offline.invalid/fileURI", "state": self.initial_state}})
        elif request.full_url.endswith(":generateContent"):
            stage = "GENERATE_CONTENT"
            self.payloads.append(json.loads(request.data))
            result = self.generations.pop(0) if self.generations else self.generated()
        else:
            self.assertTrue(request.full_url.endswith("/v1beta/files/offline"))
            stage = "FILE_POLL"
            self.polls += 1
            result = self.response({"name": "files/offline", "uri": "https://offline.invalid/fileURI",
                                    "state": "ACTIVE" if self.polls >= self.active_on_poll else "PROCESSING"})
        self.events.append((stage, timeout))
        effect = self.effects.get(stage)
        if effect:
            effect()
        if isinstance(result, BaseException):
            raise result
        return result

    def invoke(self, cutoff="2026-10-21T13:15:00Z"):
        policy = sr.ReviewHTTPPolicy(cutoff_utc=cutoff)
        error = None
        try:
            result = sr.review(self.output, {"hook": "synthetic", "qa_output_sha256": ABC_SHA256},
                               "fake-key", http_policy=policy)
        except Exception as caught:
            error = caught
            result = sr.failure_record(caught, self.output)
        return result, policy.audit(), error, policy

    def test_opt_in_payload_matches_legacy_exactly_and_does_not_retry_editorial_fail(self):
        legacy = sr.review(self.output, {"hook": "synthetic", "qa_output_sha256": ABC_SHA256}, "fake-key")
        payload = self.payloads[-1]
        self.events.clear()
        self.generations = [self.generated(3)]
        result, audit, error, _ = self.invoke()
        self.assertIsNone(error)
        self.assertEqual(legacy["status"], "PASS")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(payload, self.payloads[-1])
        self.assertEqual([x[0] for x in self.events], ["UPLOAD_START", "UPLOAD_FINALIZE", "GENERATE_CONTENT", "DELETE"])
        self.assertEqual(audit["http_completion"], "COMPLETED")
        self.assertEqual(audit["terminal_stage"], "GENERATE_CONTENT")
        self.assertEqual(audit["cleanup_status"], "SUCCESS")
        self.sleeper.assert_not_called()
        self.assertEqual(self.events[-1][1], 5)

    def test_full_retry_trace_is_client_owned_and_contains_no_secrets(self):
        self.generations = [self.error(after="180"), self.generated(extra={"transport_attempts": [{"secret": "MODEL_TRACE"}],
                             "http_completion": "FORGED", "http_elapsed_seconds": -1})]
        result, audit, error, _ = self.invoke()
        self.assertIsNone(error)
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn("transport_attempts", result)
        self.assertEqual([r["decision"] for r in audit["transport_attempts"]], ["RETRY", "RETURN"])
        self.assertEqual(audit["http_elapsed_seconds"], 180)
        self.assertEqual([x[1] for x in self.events], [300, 300, 300, 300, 5])
        for forbidden in ("secret", "fake-key", "http://", "https://", "fileURI", "MODEL_TRACE", "FORGED"):
            self.assertNotIn(forbidden, json.dumps(audit))

    def test_files_failures_keep_factual_status_without_upload_retry(self):
        for stage in ("UPLOAD_START", "UPLOAD_FINALIZE", "FILE_POLL"):
            with self.subTest(stage=stage):
                self.events.clear()
                self.initial_state = "PROCESSING"
                self.effects = {stage: lambda: (_ for _ in ()).throw(self.error())}
                result, audit, error, _ = self.invoke()
                self.assertIsInstance(error, ProviderFailure)
                self.assertEqual(result["error_code"], "HTTP_503_UNAVAILABLE")
                self.assertEqual(result["provider_diagnostic"]["http_status"], 503)
                self.assertEqual(audit["http_completion"], "UPLOAD_FAILED")
                self.assertEqual(audit["terminal_stage"], stage)
                self.assertEqual(audit["transport_attempts"], [])
                self.assertEqual(sum(s == stage for s, _ in self.events), 1)
                self.assertNotIn("GENERATE_CONTENT", [s for s, _ in self.events])
                self.assertEqual(audit["cleanup_status"], "SUCCESS" if stage == "FILE_POLL" else "NOT_ATTEMPTED")
                self.assertNotIn("secret", json.dumps(result))

    def test_cleanup_is_one_bounded_attempt_and_cannot_replace_primary_failure(self):
        self.generations = [self.error(), self.error()]
        self.effects["DELETE"] = lambda: (_ for _ in ()).throw(TimeoutError("secret cleanup"))
        result, audit, _, _ = self.invoke()
        self.assertEqual(result["error_code"], "HTTP_503_UNAVAILABLE")
        self.assertEqual(audit["cleanup_status"], "FAILED")
        self.assertEqual(audit["terminal_stage"], "GENERATE_CONTENT")
        self.assertEqual(sum(s == "DELETE" for s, _ in self.events), 1)
        self.assertEqual(self.events[-1][1], 5)
        self.sleeper.assert_called_once_with(20)

    def test_after_active_cutoff_blocks_generation_but_still_cleans_up(self):
        self.effects["UPLOAD_FINALIZE"] = lambda: self.advance(2)
        result, audit, _, _ = self.invoke("2026-10-21T12:00:01Z")
        self.assertEqual(result["error_code"], "REVIEW_DEADLINE_EXCEEDED")
        self.assertEqual(audit["http_completion"], "DEADLINE_EXCEEDED")
        self.assertEqual(audit["terminal_stage"], "UPLOAD_FINALIZE")
        self.assertEqual(audit["transport_attempts"], [])
        self.assertEqual([x[0] for x in self.events], ["UPLOAD_START", "UPLOAD_FINALIZE", "DELETE"])
        self.assertEqual(self.events[-1][1], 5)

    def test_upload_local_read_and_initial_hash_count_towards_budget(self):
        real_read = Path.read_bytes
        def slow_read(path):
            data = real_read(path)
            self.advance(601, utc_seconds=-500)
            return data
        with patch.object(Path, "read_bytes", slow_read):
            result, audit, _, _ = self.invoke()
        self.assertEqual(result["error_code"], "REVIEW_BUDGET_EXHAUSTED")
        self.assertEqual([x[0] for x in self.events], ["UPLOAD_START"])
        self.assertEqual(audit["http_elapsed_seconds"], 601)
        self.events.clear()
        real_digest = sr.output_digest
        count = [0]
        def slow_digest(path):
            count[0] += 1
            if count[0] == 1:
                self.advance(601)
            return real_digest(path)
        with patch.object(sr, "output_digest", side_effect=slow_digest):
            result, audit, _, _ = self.invoke()
        self.assertEqual(result["error_code"], "REVIEW_BUDGET_EXHAUSTED")
        self.assertEqual(self.events, [])
        self.assertEqual(audit["terminal_stage"], "NONE")

    def test_poll_wait_and_processing_time_reduce_next_operation_timeout(self):
        self.initial_state = "PROCESSING"
        self.effects["UPLOAD_FINALIZE"] = lambda: self.advance(590)
        result, audit, error, _ = self.invoke()
        self.assertIsNone(error)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(audit["http_elapsed_seconds"], 595)
        self.assertEqual(dict(self.events)["FILE_POLL"], 5)
        self.assertEqual(dict(self.events)["GENERATE_CONTENT"], 5)

    def test_active_at_final_poll_is_checked_and_never_discards_success(self):
        self.initial_state = "PROCESSING"
        self.active_on_poll = 60
        result, audit, error, _ = self.invoke()
        self.assertIsNone(error)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(self.polls, 60)
        self.assertEqual(audit["http_elapsed_seconds"], 300)

    def test_late_success_and_cleanup_time_remain_noneligible_without_losing_verdict(self):
        self.effects["GENERATE_CONTENT"] = lambda: self.advance(599)
        self.effects["DELETE"] = lambda: self.advance(2)
        result, audit, error, _ = self.invoke()
        self.assertIsNone(error)
        self.assertEqual(result["overall"], 9)
        self.assertEqual(audit["http_elapsed_seconds"], 601)
        self.assertEqual(audit["http_completion"], "BUDGET_EXHAUSTED")
        self.assertEqual(audit["transport_attempts"][-1]["decision"], "STOP_BUDGET")
        self.assertEqual(audit["transport_attempts"][-1]["elapsed_end_seconds"], 599)

    def test_late_pass_and_editorial_fail_are_retained_without_another_transport(self):
        for score in (3, 9):
            for deadline in (False, True):
                with self.subTest(score=score, deadline=deadline):
                    self.events.clear()
                    self.utc = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
                    self.generations = [self.generated(score)]
                    self.effects = {"GENERATE_CONTENT": lambda: self.advance(601 if not deadline else 2)}
                    result, audit, error, _ = self.invoke("2026-10-21T12:00:01Z" if deadline else "2026-10-21T13:15:00Z")
                    self.assertIsNone(error)
                    self.assertEqual(result["overall"], score)
                    self.assertEqual(result["status"], "PASS" if score == 9 else "FAIL")
                    self.assertEqual(audit["http_completion"], "DEADLINE_EXCEEDED" if deadline else "BUDGET_EXHAUSTED")
                    self.assertEqual(audit["transport_attempts"][-1]["outcome"], "SUCCESS")
                    self.assertEqual(audit["transport_attempts"][-1]["decision"], "STOP_DEADLINE" if deadline else "STOP_BUDGET")
                    self.assertEqual(sum(stage == "GENERATE_CONTENT" for stage, _ in self.events), 1)
                    self.assertEqual(audit["cleanup_status"], "SUCCESS")
                    self.sleeper.assert_not_called()

    def test_change_during_cleanup_cannot_leave_a_bound_verdict(self):
        self.effects["DELETE"] = lambda: self.output.write_bytes(b"changed")
        result, audit, error, _ = self.invoke()
        self.assertIsNone(error)
        self.assertEqual(result["status"], "NOT_REVIEWED_OUTPUT_CHANGED")
        self.assertNotIn("overall", result)
        self.assertEqual(audit["cleanup_status"], "SUCCESS")

    def test_unknown_transport_timeout_is_not_reported_as_http_503(self):
        self.generations = [TimeoutError("HTTP_503_UNAVAILABLE secret")]
        result, audit, _, _ = self.invoke()
        self.assertEqual(result["error_code"], "PROVIDER_CALL_FAILED")
        self.assertEqual(result["provider_diagnostic"], {})
        self.assertEqual(audit["transport_attempts"][0]["outcome"], "TRANSPORT_ERROR")
        self.assertIsNone(audit["transport_attempts"][0]["http_status"])
        self.sleeper.assert_not_called()

    def test_only_three_new_failure_codes_are_added(self):
        for code in ("RETRY_HINT_INVALID", "REVIEW_BUDGET_EXHAUSTED", "REVIEW_DEADLINE_EXCEEDED"):
            self.assertEqual(sr.failure_record(ProviderFailure(code), self.output)["error_code"], code)
        self.assertEqual(sr.failure_record(ProviderFailure("UPLOAD_FAILED"), self.output)["error_code"], "UNKNOWN")


class HTTPResponse:
    def __init__(self, raw, headers=None):
        self.raw, self.headers, self.status = raw, headers or {}, 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count=-1):
        return self.raw if count < 0 else self.raw[:count]


if __name__ == "__main__":
    unittest.main()
