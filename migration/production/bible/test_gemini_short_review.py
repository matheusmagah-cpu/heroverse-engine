#!/usr/bin/env python3
"""Antidotes for the autopilot Short pre-filter reviewer (AUTOPILOT.md 2.3 and section 4): an error, partial output,
ungrounded or failing answer is never PASS; the reviewer only reaches READY_FOR_CLAUDE_REVIEW until a conservative
calibration against accepted Short reviews qualifies the exact model, prompt and validator; no retry of an uncertain
call; a 429 stops the day. Offline: the provider is a stub."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemini_short_review as g  # noqa: E402

B = g.budget
NOW = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)


def report(overall=9.6, items=9.6, seconds=60.0, issues=None, links=None):
    segs = [{'start': s, 'end': min(s + 15, seconds), 'audible_observation': 'narrator voice, low music',
             'visual_observation': 'tents at dusk', 'speech_excerpt': 'in the beginning God',
             'motion_observation': 'camera_only'} for s in range(0, int(seconds), 15)]
    segs[-1]['end'] = seconds
    return {'audio_received': True, 'visual_received': True, 'duration_seconds': seconds,
            'scores': {k: items for k in g.RUBRIC}, 'overall': overall, 'issues': issues or [],
            'limitations': ['4 fps sampling'], 'criterion_issues': links or {}, 'coverage': segs}


def ok(rep, model=g.MODEL, seconds=60.0):
    return {'status': 'OK', 'report': rep, 'seconds': seconds, 'model': model, 'prompt_sha256': g.prompt_sha256()}


def qualified():
    return {'qualified': True, 'model': g.MODEL, 'validator_version': g.VALIDATOR_VERSION,
            'prompt_sha256s': [g.prompt_sha256()]}


class Validation(unittest.TestCase):
    def test_valid_report_has_no_problems(self):
        self.assertEqual(g.problems(report(), 60.0), [])

    def test_sub_floor_score_needs_a_timed_issue(self):
        self.assertIn('UNSUPPORTED_SCORE:overall', g.problems(report(overall=9.0), 60.0))
        rep = report(overall=9.0, issues=['somewhere a blur'], links={'overall': [0]})
        self.assertIn('UNGROUNDED_ISSUE:overall', g.problems(rep, 60.0))
        rep = report(overall=9.0, issues=['05:00 blur'], links={'overall': [0]})   # outside a 60 s video
        self.assertIn('UNGROUNDED_ISSUE:overall', g.problems(rep, 60.0))
        rep = report(overall=9.0, issues=['00:12 blur on the tent'], links={'overall': [0]})
        self.assertEqual(g.problems(rep, 60.0), [])

    def test_partial_or_unheard_answers_are_not_evidence(self):
        rep = report()
        rep['audio_received'] = False
        self.assertIn('AV_NOT_CONFIRMED', g.problems(rep, 60.0))
        rep = report()
        rep['coverage'] = rep['coverage'][:2]
        self.assertTrue(g.problems(rep, 60.0))
        rep = report()
        rep['coverage'][1]['speech_excerpt'] = ''
        self.assertIn('HEARD_EXCERPT_MISSING', g.problems(rep, 60.0))
        rep = report()
        rep['scores'].pop('policy_safe')
        self.assertIn('SCORE_INVALID', g.problems(rep, 60.0))
        self.assertIn('DURATION_MISMATCH', g.problems(report(seconds=60.0), 175.0))
        self.assertEqual(g.problems('PASS', 60.0), ['NOT_AN_OBJECT'])


class Routing(unittest.TestCase):
    def test_errors_never_pass(self):
        for res in ({'status': 'UNCERTAIN'}, {'status': 'PROVIDER_ERROR', 'http': 503},
                    {'status': 'BUDGET_REFUSED'}, {'status': 'UNPARSEABLE'}):
            self.assertEqual(g.route(res, qualified()), 'NO_EVIDENCE')
        bad = report()
        bad['audio_received'] = False
        self.assertEqual(g.route(ok(bad), qualified()), 'NO_EVIDENCE')

    def test_below_floor_or_item_below_7_is_rejected(self):
        rep = report(overall=9.4, issues=['00:10 soft focus'], links={'overall': [0]})
        self.assertEqual(g.route(ok(rep)), 'REJECT')
        rep = report(overall=9.6)
        rep['scores']['picture_quality'] = 6.5
        rep['issues'] = ['00:10 soft focus']
        rep['criterion_issues'] = {'picture_quality': [0]}
        self.assertEqual(g.route(ok(rep), qualified()), 'REJECT')

    def test_passing_answer_stops_at_claude_until_calibrated(self):
        self.assertEqual(g.route(ok(report())), 'READY_FOR_CLAUDE_REVIEW')
        self.assertEqual(g.route(ok(report()), {**qualified(), 'qualified': False}), 'READY_FOR_CLAUDE_REVIEW')
        self.assertEqual(g.route(ok(report()), {**qualified(), 'prompt_sha256s': ['0' * 64]}),
                         'READY_FOR_CLAUDE_REVIEW')
        self.assertEqual(g.route(ok(report()), {**qualified(), 'validator_version': 'old'}),
                         'READY_FOR_CLAUDE_REVIEW')
        self.assertEqual(g.route(ok(report(), model='gemini-3.6-flash'), qualified()), 'READY_FOR_CLAUDE_REVIEW')
        self.assertEqual(g.route(ok(report()), qualified()), 'GEMINI_REVIEW_QUALIFIED')

    def test_module_writes_no_approval(self):
        src = (Path(__file__).resolve().parent / 'gemini_short_review.py').read_text()
        for word in ('APPROVAL.json', 'approve-shot', 'LONG_REVIEWERS', 'owner_quality_policy'):
            self.assertNotIn(word, src)


def row(status, overall, gem, repeat=False, vid=None):
    return {'episode': 'e', 'video_id': vid or ('v%s' % overall), 'accepted_status': status,
            'accepted_overall': overall, 'gemini_overall': gem, 'repeat': repeat,
            'gemini_status': 'PASS' if gem >= 9.5 else 'FAIL', 'prompt_sha256': g.prompt_sha256()}


def corpus(gems, bad_gem=8.0, reps=(0.0, 0.0)):
    rows = [row('PASS', 9.5, x, vid='p%d' % i) for i, x in enumerate(gems)] + [row('FAIL', 8.0, bad_gem, vid='b')]
    rows += [row('PASS', 9.5, gems[i] + d, repeat=True, vid='p%d' % i) for i, d in enumerate(reps)]
    return rows


class Calibration(unittest.TestCase):
    def test_rule_is_fixed_and_conservative(self):
        self.assertEqual(g.RULE['max_mean_signed'], 0.25)
        self.assertEqual(g.RULE['max_mean_abs'], 0.5)
        self.assertEqual(g.RULE['max_row_abs'], 1.0)
        self.assertEqual(g.RULE['min_accepted_rows'], 7)

    def test_agreeing_reviewer_qualifies(self):
        self.assertTrue(g.qualify(corpus([9.5, 9.6, 9.5, 9.7, 9.5, 9.6, 9.5]))['qualified'])

    def test_known_bad_must_fail(self):
        q = g.qualify(corpus([9.5] * 7, bad_gem=9.6))
        self.assertFalse(q['qualified'])
        self.assertFalse(q['same_verdict_everywhere'])

    def test_lenient_harsh_unstable_or_incomplete_does_not_qualify(self):
        lenient = corpus([10, 10, 10, 10, 10, 10, 10], bad_gem=9.4)
        self.assertFalse(g.qualify(lenient)['qualified'])              # mean signed > +0.25
        self.assertFalse(g.qualify(corpus([9.0] * 7))['qualified'])    # same as FAIL verdicts
        self.assertFalse(g.qualify(corpus([9.5] * 7, reps=(0.5, 0.0)))['qualified'])  # unstable
        self.assertFalse(g.qualify(corpus([9.5] * 7, reps=()))['qualified'])          # no repeats
        self.assertFalse(g.qualify(corpus([9.5] * 6))['qualified'])                   # corpus too small
        rows = corpus([9.5] * 7)
        rows[2]['error'] = 'UNCERTAIN'
        self.assertEqual(g.qualify(rows)['reason'], 'INCOMPLETE_OR_INVALID')

    def test_corpus_is_the_published_accepted_shorts(self):
        c = g.accepted_corpus()
        self.assertGreaterEqual(sum(r['accepted_status'] == 'PASS' for r in c), 7)
        self.assertTrue(any(r['accepted_status'] == 'FAIL' for r in c))
        self.assertTrue(all(r['video_id'] and r['seconds'] > 0 for r in c))


class Provider(unittest.TestCase):
    def ledger(self):
        return B.empty()

    def test_uncertain_call_is_counted_and_not_retried(self):
        calls = []
        led = self.ledger()

        def post(body, key):
            calls.append(1)
            return None, None
        res = g.review('https://www.youtube.com/watch?v=x', 60.0, 'k', led, 't', NOW, post)
        self.assertEqual(res['status'], 'UNCERTAIN')
        self.assertEqual(len(calls), 1)
        self.assertEqual(led['calls'][0]['status'], B.UNCERTAIN)
        self.assertFalse(B.retry_allowed(led, res['call_id']))

    def test_429_stops_the_calibration_and_the_day(self):
        calls = []

        def post(body, key):
            calls.append(1)
            return 429, {'error': {'status': 'RESOURCE_EXHAUSTED', 'message': 'quota'}}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(g.time, 'sleep'):
            q = g.calibrate(str(Path(d) / 'b.json'), str(Path(d) / 'rows.json'), 'k', post=post)
            self.assertEqual(len(calls), 1)
            self.assertFalse(q['qualified'])
            led = B.load(str(Path(d) / 'b.json'))
            self.assertIsNotNone(B.stopped(led, datetime.now(timezone.utc)))
            calls.clear()
            g.calibrate(str(Path(d) / 'b.json'), str(Path(d) / 'rows.json'), 'k', post=post)
            self.assertEqual(calls, [])  # stopped for the day: nothing is sent

    def test_recorded_uncertain_or_invalid_rows_are_never_re_asked(self):
        calls = []

        def post(body, key):
            calls.append(1)
            return None, None  # every call times out: uncertain
        with tempfile.TemporaryDirectory() as d, mock.patch.object(g.time, 'sleep'):
            tick = iter(NOW + timedelta(minutes=k) for k in range(100))
            args = (str(Path(d) / 'b.json'), str(Path(d) / 'rows.json'), 'k')
            q = g.calibrate(*args, post=post, clock=lambda: next(tick))
            first = len(calls)
            self.assertEqual(q['reason'], 'INCOMPLETE_OR_INVALID')
            g.calibrate(*args, post=post, clock=lambda: next(tick))
            self.assertEqual(len(calls), first)  # nothing re-sent

    def test_budget_refusal_sends_nothing(self):
        led = self.ledger()
        led['stops'].append({'pacific_day': B.pacific_day(NOW), 'reason': '429'})
        res = g.review('u', 60.0, 'k', led, 't', NOW, lambda *a: self.fail('sent'))
        self.assertEqual(res['status'], 'BUDGET_REFUSED')

    def test_calibration_resumes_and_qualifies_only_by_the_rule(self):
        def post(body, key):
            secs = float(body['contents'][0]['parts'][1]['text'].split('complete ')[1].split('-second')[0])
            rep = report(overall=9.5, items=9.5, seconds=secs)
            return 200, {'modelVersion': g.MODEL, 'usageMetadata': {'totalTokenCount': 20000},
                         'candidates': [{'content': {'parts': [{'text': json.dumps(rep)}]}}]}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(g.time, 'sleep'):
            tick = iter(NOW + timedelta(minutes=k) for k in range(100))
            q = g.calibrate(str(Path(d) / 'b.json'), str(Path(d) / 'rows.json'), 'k', post=post,
                            clock=lambda: next(tick))
            rows = json.loads((Path(d) / 'rows.json').read_text())
            self.assertEqual(len(rows), 10)  # 8 published Shorts + 2 repeats
            self.assertFalse(q['qualified'])  # the known-bad 8.0 Short was passed: never qualifies
            self.assertFalse(q['same_verdict_everywhere'])
            self.assertNotIn('"k"', (Path(d) / 'b.json').read_text())


if __name__ == '__main__':
    unittest.main()
