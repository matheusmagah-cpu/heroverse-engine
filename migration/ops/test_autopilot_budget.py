#!/usr/bin/env python3
"""Antidotes for the autopilot Gemini budget (AUTOPILOT.md 2.7 / section 4 'Gemini quota out')."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autopilot_budget as b  # noqa: E402

# 2026-10-31 20:00 UTC = 13:00 Pacific (PDT), Pacific day 2026-10-31
NOW = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)
REVIEW = 'gemini-3.8-flash'
LITE = 'gemini-3.5-flash-lite'


def spaced(ledger, model, n, start=NOW):
    ids = []
    for k in range(n):
        at = start + timedelta(minutes=2 * k)
        ids.append(b.reserve(ledger, model, 'test', at))
        b.settle(ledger, ids[-1], 200, at, 1000)
    return ids


class Budget(unittest.TestCase):
    def test_limits_match_the_ai_studio_readback(self):
        self.assertEqual(b.LIMITS[REVIEW], {'rpm': 5, 'tpm': 250_000, 'rpd': 20})
        self.assertEqual(b.LIMITS[LITE], {'rpm': 15, 'tpm': 250_000, 'rpd': 500})
        self.assertEqual(b.SAFETY, 0.8)

    def test_no_call_past_80_percent_of_rpd(self):
        led = b.empty()
        spaced(led, REVIEW, 16)
        self.assertEqual(b.decide(led, REVIEW, NOW + timedelta(hours=1)), ('REFUSE', 'RPD_80'))
        with self.assertRaises(RuntimeError):
            b.reserve(led, REVIEW, 'x', NOW + timedelta(hours=1))
        self.assertEqual(b.decide(led, LITE, NOW + timedelta(hours=1)), ('ALLOW', None))

    def test_rpd_resets_at_midnight_pacific_not_utc(self):
        led = b.empty()
        spaced(led, REVIEW, 16)
        utc_midnight = datetime(2026, 11, 1, 0, 30, tzinfo=timezone.utc)  # still 31/10 in Pacific
        self.assertEqual(b.decide(led, REVIEW, utc_midnight)[0], 'REFUSE')
        pacific_midnight = datetime(2026, 11, 1, 7, 5, tzinfo=timezone.utc)  # 00:05 PDT on 1/11
        self.assertEqual(b.decide(led, REVIEW, pacific_midnight), ('ALLOW', None))

    def test_rpm_and_tpm_windows(self):
        led = b.empty()
        for k in range(4):
            b.reserve(led, REVIEW, 'x', NOW + timedelta(seconds=k))
        self.assertEqual(b.decide(led, REVIEW, NOW + timedelta(seconds=10)), ('REFUSE', 'RPM_80'))
        self.assertEqual(b.decide(led, REVIEW, NOW + timedelta(seconds=70))[0], 'ALLOW')
        led = b.empty()
        b.reserve(led, REVIEW, 'x', NOW, 150_000)
        self.assertEqual(b.decide(led, REVIEW, NOW + timedelta(seconds=5), 60_000), ('REFUSE', 'TPM_80'))

    def test_429_stops_every_model_for_the_pacific_day_and_is_never_retried(self):
        led = b.empty()
        cid = b.reserve(led, LITE, 'x', NOW)
        b.settle(led, cid, 429, NOW)
        self.assertEqual(b.decide(led, REVIEW, NOW + timedelta(hours=2))[0], 'REFUSE')
        self.assertTrue(b.decide(led, LITE, NOW + timedelta(hours=2))[1].startswith('QUOTA_STOP_TODAY'))
        self.assertFalse(b.retry_allowed(led, cid))
        self.assertEqual(b.decide(led, LITE, datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)), ('ALLOW', None))
        led = b.empty()
        cid = b.reserve(led, REVIEW, 'x', NOW)
        b.settle(led, cid, 'RESOURCE_EXHAUSTED', NOW)
        self.assertIsNotNone(b.stopped(led, NOW))

    def test_uncertain_submission_counts_and_is_never_retried(self):
        led = b.empty()
        cid = b.reserve(led, REVIEW, 'x', NOW)
        call = b.settle(led, cid, None, NOW)
        self.assertEqual(call['status'], b.UNCERTAIN)
        self.assertFalse(b.retry_allowed(led, cid))
        self.assertEqual(b.status(led, NOW)['models'][REVIEW]['calls_today'], 1)
        with self.assertRaises(RuntimeError):
            b.settle(led, cid, 200, NOW)  # an outcome is written once

    def test_pending_call_counts_before_its_outcome(self):
        led = b.empty()
        for k in range(16):
            b.reserve(led, REVIEW, 'x', NOW + timedelta(minutes=2 * k))  # never settled
        self.assertEqual(b.decide(led, REVIEW, NOW + timedelta(hours=2)), ('REFUSE', 'RPD_80'))

    def test_only_a_definitive_transient_error_may_be_retried_once(self):
        led = b.empty()
        cid = b.reserve(led, REVIEW, 'x', NOW)
        b.settle(led, cid, 503, NOW)
        self.assertTrue(b.retry_allowed(led, cid))
        rid = b.reserve(led, REVIEW, 'retry', NOW + timedelta(minutes=1))
        led['calls'][-1]['retry_of'] = cid
        self.assertFalse(b.retry_allowed(led, cid))
        b.settle(led, rid, 503, NOW + timedelta(minutes=1))
        self.assertFalse(b.retry_allowed(led, rid))
        cid = b.reserve(led, REVIEW, 'x', NOW + timedelta(minutes=5))
        b.settle(led, cid, 400, NOW + timedelta(minutes=5))
        self.assertFalse(b.retry_allowed(led, cid))

    def test_unknown_model_is_refused(self):
        self.assertEqual(b.decide(b.empty(), 'gemini-4-argon', NOW), ('REFUSE', 'MODEL_LIMIT_UNKNOWN'))
        self.assertEqual(b.decide(b.empty(), 'gemini-omni-flash', NOW)[0], 'REFUSE')

    def test_cli_refusal_exits_3_and_ledger_holds_no_secret(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / 'budget.json')
            for k in range(16):
                self.assertEqual(b.main([path, 'reserve', REVIEW, 'p', '10'], NOW + timedelta(minutes=2 * k)), 0)
            self.assertEqual(b.main([path, 'reserve', REVIEW, 'p'], NOW + timedelta(hours=1)), 3)
            self.assertEqual(b.main([path, 'check', REVIEW], NOW + timedelta(hours=1)), 3)
            text = Path(path).read_text()
            self.assertNotIn('key', text.lower())
            self.assertEqual(text.count('"model"'), 16)


if __name__ == '__main__':
    unittest.main()
