from datetime import datetime, timedelta, timezone
from email.message import Message
import io
import json
from unittest.mock import patch
from urllib.error import HTTPError
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import structure_mining as sm  # noqa: E402


def narration(start, end, every=5, words=12):
    """A realistic transcript: one sentence every 5 s, 12 words each (144 wpm), stamped inside the window."""
    return [{"start_seconds": t, "text": " ".join([f"sentence{t}"] + ["word"] * (words - 1))} for t in range(start, end, every)]


def window(start, end, cuts):
    edges = [start, *cuts, end]
    return {"video_id": "abcdefghijk", "window_start_seconds": start, "window_end_seconds": end,
            "transcript": narration(start, end),
            "audio_received": True, "visual_received": True,
            "beats": [{"start_seconds": a, "end_seconds": b, "beat": "hook" if a == 0 else "teaching",
                       "opening_words_verbatim": "x", "content": "x", "device": "none", "emotion": "calm"}
                      for a, b in zip(edges, edges[1:])],
            "picture": {"shots_counted": 30}, "sound": {}, "scripture_references": ["John 3:16"]}


class StructureMining(unittest.TestCase):
    # regression cases from the 2026-10-18 accuracy audit (structure-mining/20261017 vs native ASR)
    def test_reviewer_allowance_is_reserved_for_decisions(self):
        # E26: mining and Shorts selection spent gemini-3.8-flash's small free daily allowance before the reviews
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "migration/production"))
        import long_review
        import shorts_review
        # Read the policy actually used by each reviewer, including shared imported policies.
        reviewers = set(long_review.REVIEW_MODELS) | set(shorts_review.REVIEW_MODELS)
        reviewers = {m for m in reviewers if m.startswith("gemini")}  # session reviews use no Gemini allowance
        self.assertEqual(set(sm.DECISION_MODELS), reviewers)
        self.assertFalse(set(sm.SUPPORT_MODELS) & reviewers)
        self.assertTrue(sm.SUPPORT_MODELS)
        for f in ("migration/production/long_review.py", "migration/production/shorts_select.py", "migration/mining/structure_mining.py",
                  "migration/mining/packaging_mining.py"):
            text = (root / f).read_text()
            self.assertNotIn("call(payload, key, list(sm.FREE_MODELS))", text, f)
            self.assertNotIn("call(payload, key, list(FREE_MODELS))", text, f)
            self.assertNotIn('",".join(FREE_MODELS)', text, f)
            self.assertNotIn("sm.FREE_MODELS)", text, f)

    def test_the_last_failure_keeps_the_provider_diagnostic(self):
        # E29: call() re-raised a bare code, so nobody could tell a per-minute from a per-day quota
        real = sm.transport
        def fail(payload, key, model):
            raise sm.ProviderFailure("HTTP_429_RESOURCE_EXHAUSTED:QUOTA", {"quota_ids": ["X-PerMinute"], "message": "m"})
        sm.transport = fail
        try:
            with self.assertRaises(sm.ProviderFailure) as e:
                sm.call({}, "k", ["m"])
        finally:
            sm.transport = real
        self.assertEqual(e.exception.diagnostic["quota_ids"], ["X-PerMinute"])

    def test_every_call_records_its_token_usage(self):
        real, sm.USAGE[:] = sm.transport, []
        sm.transport = lambda payload, key, model: {"candidates": [{"content": {"parts": [{"text": "{}"}]}}],
                                                    "usageMetadata": {"promptTokenCount": 1200, "totalTokenCount": 1300}}
        try:
            sm.call({}, "k", ["m"])
        finally:
            sm.transport = real
        self.assertEqual(sm.USAGE, [{"model": "m", "promptTokenCount": 1200, "totalTokenCount": 1300}])
        sm.USAGE[:] = []

    def test_transcript_stamped_outside_its_window_is_rejected(self):
        w = window(900, 1200, [960])  # e.g. 8YXRtsNnGX0 window 900-1200 stamped 15-19 s
        w["transcript"] = [{"start_seconds": 15 + i * 0.07, "text": f"line{i} " + "word " * 11} for i in range(67)]
        self.assertIn("TRANSCRIPT_TIME_OUTSIDE_WINDOW", sm.transcript_problems(w, 900, 1200))
        self.assertFalse(sm.valid_window(w, "abcdefghijk", 900, 1200))

    def test_rescaled_times_are_rejected(self):
        w = window(300, 600, [400])  # e.g. 6Q98ZRdnzw8 window 300-600 stamped up to 3375 s
        w["transcript"] = [{"start_seconds": 300 + i * 58.0, "text": f"line{i} " + "word " * 11} for i in range(53)]
        self.assertIn("TRANSCRIPT_TIME_OUTSIDE_WINDOW", sm.transcript_problems(w, 300, 600))

    def test_whole_window_in_one_line_is_rejected(self):
        w = window(300, 600, [400])  # e.g. VGv3fbxG7OI window 300-600: one 770-word line
        w["transcript"] = [{"start_seconds": 305, "text": "word " * 770}]
        self.assertIn("TRANSCRIPT_LINE_TOO_LONG", sm.transcript_problems(w, 300, 600))

    def test_truncated_transcript_is_rejected(self):
        w = window(0, 300, [23, 51, 109])  # e.g. 8YXRtsNnGX0 window 0-300: lines stop at 130 s, 207 words
        w["transcript"] = narration(0, 130, every=5, words=8)
        self.assertIn("TRANSCRIPT_INCOMPLETE", sm.transcript_problems(w, 0, 300))

    def test_music_only_window_with_no_words_is_valid(self):
        w = window(0, 300, [20, 140])
        for b in w["beats"]:
            b["beat"] = "music_only"
        w["transcript"] = []
        self.assertEqual(sm.transcript_problems(w, 0, 300), [])

    def test_normal_narration_has_no_problem(self):
        self.assertEqual(sm.transcript_problems(window(0, 300, [20, 140]), 0, 300), [])

    def test_contiguous_window_is_valid(self):
        self.assertTrue(sm.valid_window(window(0, 300, [20, 140]), "abcdefghijk", 0, 300))

    def test_gap_or_foreign_video_is_rejected(self):
        w = window(0, 300, [20, 140])
        w["beats"][1]["start_seconds"] = 60
        self.assertFalse(sm.valid_window(w, "abcdefghijk", 0, 300))
        self.assertFalse(sm.valid_window(window(0, 300, [20]), "zzzzzzzzzzz", 0, 300))
        self.assertFalse(sm.valid_window(window(0, 250, [20]), "abcdefghijk", 0, 300))

    def test_measured_fields_are_computed_not_asked(self):
        video = {"seconds": 600, "title": "Why Did God Bury Moses Himself?", "description": "0:00 Intro\n2:15 Moses",
                 "likes": 50, "views": 1000, "comments": 5}
        m = sm.measured(video, [window(0, 300, [20, 140]), window(300, 600, [450])])
        self.assertEqual(m["chapters"], 2)
        self.assertEqual(m["beats"], 5)
        self.assertEqual(m["coverage_fraction"], 1.0)
        self.assertEqual(m["shots_per_minute_model_counted"], 6.0)
        self.assertEqual(m["first_spoken_beat"], {"at": 0, "beat": "hook"})

    def test_looping_transcript_is_rejected(self):
        w = window(0, 300, [20, 140])
        w["transcript"] = [{"start_seconds": i, "text": "By divine authority."} for i in range(12)]
        self.assertTrue(sm.degenerate(w))
        self.assertFalse(sm.valid_window(w, "abcdefghijk", 0, 300))

    def test_small_gaps_are_repaired_large_are_not(self):
        w = window(0, 300, [20, 140])
        w["beats"][0]["start_seconds"], w["beats"][1]["start_seconds"] = 5, 30
        self.assertTrue(sm.valid_window(sm.repair(w, 0, 300), "abcdefghijk", 0, 300))
        w = window(0, 300, [20, 140])
        w["beats"][1]["start_seconds"] = 80
        self.assertFalse(sm.valid_window(sm.repair(w, 0, 300), "abcdefghijk", 0, 300))


class HTTPPolicyTests(unittest.TestCase):
    """Synthetic HTTP responses and both fake clocks. Never contact a provider."""
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch("socket.create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")).start()
        self.elapsed = 0.0
        self.utc = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        patch.object(sm.time, "monotonic", side_effect=lambda: self.elapsed).start()
        patch.object(sm, "review_utc_now", side_effect=lambda: self.utc).start()
        self.sleep = patch.object(sm.time, "sleep", side_effect=self.advance).start()
        self.http = patch("urllib.request.urlopen").start()
        self.addCleanup(sm.USAGE.clear)

    def advance(self, seconds, utc_seconds=None):
        self.elapsed += seconds
        self.utc += timedelta(seconds=seconds if utc_seconds is None else utc_seconds)

    def policy(self, cutoff=None):
        policy = sm.ReviewHTTPPolicy(cutoff_utc=cutoff or "2026-10-21T13:15:00Z")
        policy.begin()
        return policy

    def error(self, *, status=503, after=None, info=None, raw=None, details=None, body_code=None):
        headers = Message()
        if after is not None:
            for value in after if type(after) is list else [after]:
                headers["Retry-After"] = value
        body = {"error": {"code": body_code or status, "status": "UNAVAILABLE",
                          "message": "secret-key https://private.invalid/fileURI"}}
        if info is not None:
            body["error"]["details"] = [
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": v}
                for v in (info if type(info) is list else [info])]
        if details is not None:
            body["error"]["details"] = details
        return HTTPError("https://offline.invalid", status, "synthetic", headers,
                         io.BytesIO(raw if raw is not None else json.dumps(body).encode()))

    def response(self, report=None, *, raw=None):
        if raw is None:
            raw = json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(report or {})}]}}]}).encode()
        return MockHTTPResponse(raw)

    def call(self, policy):
        return sm.call({"synthetic": True}, "secret-key", ["gemini-3.8-flash"], http_policy=policy)

    def failed(self, policy, code=None):
        with self.assertRaises(sm.ProviderFailure) as caught:
            self.call(policy)
        if code:
            self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_http_policy_respects_retry_hints_and_never_sleeps_after_final_attempt(self):
        for after, info in (("180", "120s"), ("120", "180s")):
            with self.subTest(after=after, info=info):
                policy = self.policy()
                self.http.side_effect = [self.error(after=after, info=info), self.error(after=after, info=info)]
                self.failed(policy, "HTTP_503_UNAVAILABLE")
                self.assertEqual(self.http.call_count, 2)
                self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [180])
                trace = policy.audit()["transport_attempts"]
                self.assertEqual([x["decision"] for x in trace], ["RETRY", "STOP_FINAL"])
                self.assertEqual([x["slept_seconds"] for x in trace], [180, 0])
                self.assertEqual(trace[0]["elapsed_end_seconds"] + 180, trace[1]["elapsed_start_seconds"])
                self.http.reset_mock(); self.sleep.reset_mock()

    def test_valid_hints_use_maximum_ceil_and_receipt_utc(self):
        cases = [(None, None, 20, None, None),
                 ("Wed, 21 Oct 2026 12:02:00 GMT", None, 120, 120, None),
                 ("Wed, 21 Oct 2026 11:59:00 GMT", None, 20, 0, None),
                 (None, "1.000000001s", 20, None, 2),
                 (None, ["20s", "75.1s", "30s"], 76, None, 76),
                 (" \t25\t ", "23s", 25, 25, 23)]
        for after, info, delay, expected_after, expected_info in cases:
            with self.subTest(after=after, info=info):
                self.utc = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
                policy = self.policy()
                self.http.side_effect = [self.error(after=after, info=info), self.response()]
                self.call(policy)
                first = policy.audit()["transport_attempts"][0]
                self.assertEqual((first["retry_after_seconds"], first["retry_info_seconds"]), (expected_after, expected_info))
                self.sleep.assert_called_once_with(delay)
                self.sleep.reset_mock()

    def test_invalid_hints_fail_closed_including_the_final_503(self):
        duplicate = b'{"error":{"status":"UNAVAILABLE","status":"UNAVAILABLE"}}'
        cases = [{"after": x} for x in ("-1", "+1", "1.5", "1e3", "NaN", "", "1, 2", "0" * 129,
                 "\u0661", "Tue, 21 Oct 2026 12:02:00 GMT", "Wed, 21 Oct 2026 12:02:00 UTC",
                 "Wed, 1 Oct 2026 12:02:00 GMT", ["20", "30"])]
        cases += [{"info": x} for x in ("-30s", "+30s", "1e3s", "abc12s", "NaNs", "1.0000000001s",
                  "315576000000.000000001s", 20, True, {"secret": "x"})]
        cases += [{"raw": x} for x in (b"not json", b"{}", b"x" * 8193, duplicate,
                  b'{"error":{"details":[],"nan":NaN}}', b'{"error":{"details":{}}}')]
        for case in cases:
            with self.subTest(case=case):
                policy = self.policy()
                self.http.side_effect = [self.error(**case)]
                error = self.failed(policy, "RETRY_HINT_INVALID")
                self.assertEqual(error.diagnostic["http_status"], 503)
                self.assertEqual(policy.audit()["transport_attempts"][-1]["decision"], "STOP_HINT_INVALID")
                self.sleep.assert_not_called()
        policy = self.policy()
        self.http.side_effect = [self.error(), self.error(info="-30s")]
        self.failed(policy, "RETRY_HINT_INVALID")
        self.sleep.assert_called_once_with(20)
        self.assertEqual(len(policy.audit()["transport_attempts"]), 2)

    def test_irrelevant_details_are_ignored_and_huge_valid_hints_are_not_capped(self):
        policy = self.policy()
        details = [{"@type": "unrelated", "retryDelay": "garbage"}, None, 8]
        self.http.side_effect = [self.error(details=details), self.response()]
        self.call(policy)
        self.sleep.assert_called_once_with(20)
        self.sleep.reset_mock()
        for case in ({"after": "9" * 128}, {"info": "315576000000s"}):
            with self.subTest(case=case):
                policy = self.policy()
                self.http.side_effect = [self.error(**case)]
                self.failed(policy, "REVIEW_BUDGET_EXHAUSTED")
                self.assertGreater(policy.audit()["transport_attempts"][0]["selected_delay_seconds"], 600)
                self.sleep.assert_not_called()

    def test_retry_delay_must_fit_strictly_and_second_timeout_is_remaining_budget(self):
        for remaining in (179, 180, 181):
            with self.subTest(remaining=remaining):
                self.utc = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
                policy = self.policy()
                def first(*args, **kwargs):
                    self.advance(600 - remaining)
                    raise self.error(after="180")
                count = [0]
                def dispatch(*args, **kwargs):
                    count[0] += 1
                    return first(*args, **kwargs) if count[0] == 1 else self.response()
                self.http.side_effect = dispatch
                if remaining <= 180:
                    self.failed(policy, "REVIEW_BUDGET_EXHAUSTED")
                    self.sleep.assert_not_called()
                    self.assertEqual(count[0], 1)
                else:
                    self.call(policy)
                    self.sleep.assert_called_once_with(180)
                    self.assertEqual(self.http.call_args.kwargs["timeout"], 1)
                self.sleep.reset_mock()

    def test_oversleep_and_utc_rollback_never_extend_budget(self):
        policy = self.policy()
        self.http.side_effect = [self.error(), self.response()]
        self.sleep.side_effect = lambda seconds: self.advance(601, utc_seconds=-300)
        self.failed(policy, "REVIEW_BUDGET_EXHAUSTED")
        trace = policy.audit()["transport_attempts"]
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["slept_seconds"], 601)
        self.assertEqual(trace[0]["decision"], "STOP_BUDGET")

    def test_cutoff_constrains_timeout_and_wait_without_capping(self):
        policy = self.policy("2026-10-21T12:03:00Z")
        self.http.side_effect = [self.error(after="180")]
        self.failed(policy, "REVIEW_DEADLINE_EXCEEDED")
        self.assertEqual(self.http.call_args.kwargs["timeout"], 180)
        self.sleep.assert_not_called()
        self.assertEqual(policy.audit()["transport_attempts"][0]["decision"], "STOP_DEADLINE")

    def test_invalid_200_clears_terminal_diagnostic_after_503(self):
        for bad in (b"not JSON", b"[]", b'{"candidates":[{"content":{"parts":[{"text":"not JSON"}]}}]}',
                    b'{"candidates":[{"content":{"parts":[{"text":"[]"}]}}]}'):
            with self.subTest(bad=bad):
                policy = self.policy()
                self.http.side_effect = [self.error(), self.response(raw=bad)]
                error = self.failed(policy, "UNPARSEABLE_MODEL_OUTPUT")
                self.assertIsNone(error.diagnostic)
                last = policy.audit()["transport_attempts"][-1]
                self.assertEqual((last["outcome"], last["http_status"], last["provider_status"]),
                                 ("UNPARSEABLE_MODEL_OUTPUT", 200, None))
                self.assertEqual(last["decision"], "STOP_NONRETRYABLE")

    def test_only_actual_http_503_is_retryable(self):
        failures = [self.error(status=400, body_code=503), self.error(status=429), self.error(status=500),
                    TimeoutError("HTTP_503_UNAVAILABLE secret"),
                    sm.ProviderFailure("HTTP_503_UNAVAILABLE", {"http_status": 503})]
        for failure in failures:
            with self.subTest(kind=type(failure)):
                policy = self.policy()
                self.http.side_effect = [failure]
                self.failed(policy)
                self.assertEqual(len(policy.audit()["transport_attempts"]), 1)
                self.sleep.assert_not_called()
        policy = self.policy()
        self.http.side_effect = [self.error(body_code=400), self.response()]
        self.call(policy)
        self.sleep.assert_called_once_with(20)

    def test_late_success_is_preserved_but_ineligible(self):
        for utc_seconds, completion, decision in ((0, "BUDGET_EXHAUSTED", "STOP_BUDGET"),
                                                  (4501, "DEADLINE_EXCEEDED", "STOP_DEADLINE")):
            with self.subTest(completion=completion):
                self.utc = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
                policy = self.policy()
                def late(*args, **kwargs):
                    self.advance(601, utc_seconds)
                    return self.response({"overall": 9})
                self.http.side_effect = late
                self.assertEqual(self.call(policy)[1]["overall"], 9)
                audit = policy.audit()
                self.assertEqual(audit["http_completion"], completion)
                self.assertEqual(audit["transport_attempts"][0]["decision"], decision)

    def test_parsing_elapsed_is_measured_and_model_trace_is_discarded(self):
        policy = self.policy()
        fields = {"transport_attempts": [{"secret": "MODEL_TRACE"}], "http_completion": "FORGED",
                  "terminal_stage": "FORGED", "cleanup_status": "FORGED", "http_elapsed_seconds": 0,
                  "http_policy": "FORGED", "overall": 9}
        self.http.side_effect = [self.response(fields)]
        real = sm._strict_json
        def slow(raw):
            result = real(raw)
            self.advance(301)
            return result
        with patch.object(sm, "_strict_json", side_effect=slow):
            _, report = self.call(policy)
        self.assertEqual(report, {"overall": 9})
        audit = policy.audit()
        self.assertEqual(audit["http_completion"], "BUDGET_EXHAUSTED")
        self.assertEqual(audit["transport_attempts"][0]["elapsed_end_seconds"], 602)
        audit["transport_attempts"].clear()
        self.assertEqual(len(policy.audit()["transport_attempts"]), 1)
        self.assertEqual(set(audit), {"transport_attempts", "http_completion", "terminal_stage", "cleanup_status", "http_elapsed_seconds"})
        self.assertNotIn("MODEL_TRACE", json.dumps(policy.audit()))
        self.assertNotIn("secret", json.dumps(policy.audit()))

    def test_bounded_original_error_read_and_duplicate_relevant_keys(self):
        raw = b'{"error":{"status":"UNAVAILABLE"}}'
        bounded = raw + b" " * (8192 - len(raw))
        policy = self.policy()
        error = self.error(raw=bounded)
        with patch.object(error, "read", wraps=error.read) as read:
            self.http.side_effect = [error, self.response()]
            self.call(policy)
        read.assert_called_once_with(8193)
        for raw in (bounded + b" ", b'{"error":{"details":[{"@type":"type.googleapis.com/google.rpc.RetryInfo",'
                     b'"retryDelay":"20s","retryDelay":"30s"}]}}'):
            with self.subTest(size=len(raw)):
                policy = self.policy()
                self.http.side_effect = [self.error(raw=raw)]
                self.failed(policy, "RETRY_HINT_INVALID")

    def test_response_read_timeout_keeps_factual_http_status_without_retry(self):
        policy = self.policy()
        response = self.response()
        with patch.object(response, "read", side_effect=TimeoutError("secret")):
            self.http.side_effect = [response]
            error = self.failed(policy, "PROVIDER_CALL_FAILED")
        self.assertIsNone(error.diagnostic)
        entry = policy.audit()["transport_attempts"][0]
        self.assertEqual((entry["outcome"], entry["http_status"], entry["decision"]),
                         ("TRANSPORT_ERROR", 200, "STOP_NONRETRYABLE"))
        self.sleep.assert_not_called()

    def test_interrupted_or_short_sleep_never_permits_a_second_transport(self):
        for sleep_effect in (lambda seconds: self.advance(1),
                             lambda seconds: (_ for _ in ()).throw(OSError("secret"))):
            with self.subTest(sleep_effect=sleep_effect):
                policy = self.policy()
                self.http.side_effect = [self.error(), self.response()]
                self.sleep.side_effect = sleep_effect
                self.failed(policy, "PROVIDER_CALL_FAILED")
                trace = policy.audit()["transport_attempts"]
                self.assertEqual(len(trace), 1)
                self.assertEqual(trace[0]["decision"], "STOP_NONRETRYABLE")

    def test_expiry_between_completed_sleep_and_second_transport_is_terminal(self):
        policy = self.policy()
        self.http.side_effect = [self.error(), self.response()]
        real_transport = sm.transport
        invocations = [0]
        def delayed_transport(*args, **kwargs):
            invocations[0] += 1
            if invocations[0] == 2:
                self.advance(601)
            return real_transport(*args, **kwargs)
        with patch.object(sm, "transport", side_effect=delayed_transport):
            self.failed(policy, "REVIEW_BUDGET_EXHAUSTED")
        self.assertEqual(self.http.call_count, 1)
        trace = policy.audit()["transport_attempts"]
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["decision"], "STOP_BUDGET")
        self.assertEqual(trace[0]["slept_seconds"], 20)

    def test_profile_cannot_fallback_and_legacy_behavior_is_unchanged(self):
        policy = self.policy()
        with self.assertRaises(sm.ProviderFailure):
            sm.call({}, "k", ["gemini-3.6-flash"], http_policy=policy)
        self.http.assert_not_called()
        with patch.object(sm, "transport", side_effect=[sm.ProviderFailure("HTTP_503_UNAVAILABLE"),
                         sm.ProviderFailure("HTTP_503_UNAVAILABLE")]) as transport:
            with self.assertRaises(sm.ProviderFailure):
                sm.call({}, "k", ["legacy"])
        self.assertEqual([x.args[0] for x in self.sleep.call_args_list], [20, 40])
        self.assertEqual(transport.call_args_list[0].kwargs, {})


class MockHTTPResponse:
    def __init__(self, raw, headers=None, status=200):
        self.raw, self.headers, self.status = raw, headers or {}, status
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count=-1):
        return self.raw if count < 0 else self.raw[:count]


if __name__ == "__main__":
    unittest.main()
