#!/usr/bin/env python3
"""Antidotes for the autopilot planner (AUTOPILOT.md S1-S3 / section 4 'bad plan never reaches a PR')."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autopilot_plan as ap  # noqa: E402

NOW = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)
REAL = json.loads((HERE / 'plans/genesis-11-short.json').read_text())


def outline_of(plan):
    """The outline a perfect model would return for an existing, accepted plan."""
    out = {'story': plan['story'], 'narration': [], 'scenes': []}
    for n in plan['narration']:
        out['narration'].append({'kind': n['kind'], 'reference': n['reference'], 'excerpt': n['text']} if n['kind'] == 'scripture'
                                else {'kind': n['kind'], 'text': n['text']})
    for s in plan['shots']:
        if s.get('speaker') == 'god':
            out['god_voice'] = {'reference': s['reference'], 'text': s['line'], 'seconds': s['seconds'],
                                'scene': ap._scene_sentence(s['prompt'])}
        elif s['kind'] == 'scene':
            out['scenes'].append({'id': s['id'], 'lines': s['lines'], 'seconds': s['seconds'],
                                  'scene': ap._scene_sentence(s['prompt']), 'climax': s.get('climax', False),
                                  'figures': s.get('figures')})
    return out


def reply(outline):
    return 200, {'modelVersion': 'gemini-3.8-flash', 'usageMetadata': {'totalTokenCount': 5000},
                 'candidates': [{'content': {'parts': [{'text': json.dumps(outline)}]}}]}


class Sandbox:
    def __init__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.plans = Path(self.dir.name) / 'plans'
        shutil.copytree(HERE / 'plans', self.plans)
        (self.plans / 'genesis-11-short.json').unlink()
        self.ledger = ap.budget.empty()
        self.calls = []

    def post(self, replies):
        it = iter(replies)

        def f(model, body, key, timeout=0):
            self.calls.append(model)
            return next(it)
        return f


class Planner(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.dir.cleanup()

    def run_draft(self, replies, **kw):
        return ap.draft(self.sb.ledger, 'k', 'genesis-11-short', self.sb.plans, NOW, self.sb.post(replies), **kw)

    def test_s1_picks_first_unplanned_short_in_arc_order(self):
        self.assertEqual(ap.next_episode(plans_dir=HERE / 'plans')[0], 'genesis-12-short')
        self.assertEqual(ap.series_row(12), ('The tower of Babel', 'Genesis 11:1-9'))
        self.assertEqual(ap.series_row(14)[1], 'Genesis 12-19')

    def test_a_good_outline_passes_every_gate_and_is_written(self):
        code, res = self.run_draft([reply(outline_of(REAL))])
        self.assertEqual((code, res['status']), (0, 'PASS'), res)
        plan = json.loads((self.sb.plans / 'genesis-11-short.json').read_text())
        self.assertEqual(plan['shots'][0]['speaker'], 'god')
        self.assertEqual([c['status'] for c in self.sb.ledger['calls']], ['200'])
        self.assertEqual(self.sb.calls, ['gemini-3.8-flash'])
        self.assertEqual(res['plan_sha256'], __import__('hashlib').sha256((self.sb.plans / 'genesis-11-short.json').read_bytes()).hexdigest())

    def test_scripture_is_inserted_by_code_never_by_the_model(self):
        o = outline_of(REAL)
        for n in o['narration']:
            if n['kind'] == 'scripture':
                n['text'] = 'a misquoted verse'
        plan = ap.assemble(o, 'genesis-11-short', 11, 'Genesis 8:18-9:16', json.loads((self.sb.plans / 'genesis-10-short.json').read_text()))
        for a, b in zip(plan['narration'], REAL['narration']):
            if a['kind'] == 'scripture':
                self.assertNotIn('misquoted', a['text'])
                self.assertEqual(a['reference'], b['reference'])

    def test_a_paraphrased_excerpt_is_refused_before_any_gate(self):
        o = outline_of(REAL)
        first = next(n for n in o['narration'] if n['kind'] == 'scripture')
        first['excerpt'] = 'and the waters went down in a hurry'
        prev = json.loads((self.sb.plans / 'genesis-10-short.json').read_text())
        with self.assertRaises(ValueError) as cm:
            ap.assemble(o, 'genesis-11-short', 11, 'x', prev)
        self.assertIn('EXCERPT_NOT_IN_VERSE', str(cm.exception))

    def test_a_failing_plan_is_fed_back_then_never_written_after_three_attempts(self):
        bad = outline_of(REAL)
        bad['narration'][0]['text'] = 'Short.'
        bad['scenes'] = bad['scenes'][:2]
        code, res = self.run_draft([reply(bad)] * 3)
        self.assertEqual(code, 1)
        self.assertEqual(len(res['attempts']), 3)
        self.assertEqual(len(self.sb.calls), 3)
        self.assertFalse((self.sb.plans / 'genesis-11-short.json').exists())
        self.assertTrue(res['final_problems'])

    def test_second_attempt_can_fix_the_first(self):
        bad = outline_of(REAL)
        bad['scenes'] = bad['scenes'][:2]
        code, res = self.run_draft([reply(bad), reply(outline_of(REAL))])
        self.assertEqual((code, len(res['attempts'])), (0, 2))
        self.assertTrue(res['attempts'][0]['problems'])

    def test_plan_overlapping_our_last_plans_is_refused(self):
        o = outline_of(REAL)
        prev = json.loads((self.sb.plans / 'genesis-10-short.json').read_text())
        o['narration'] = [({'kind': n['kind'], 'text': n['text']} if n['kind'] != 'scripture' else x)
                          for n, x in zip(prev['narration'], o['narration'])]
        plan = ap.assemble(outline_of(REAL), 'genesis-11-short', 11, 'x', prev)
        plan['narration'] = [dict(n) for n in prev['narration']]
        probs = ap.overlap_problems(plan, self.sb.plans)
        self.assertTrue([p for p in probs if p.startswith('OWN_OVERLAP genesis-10-short')], probs)

    def test_reference_overlap_is_refused(self):
        import hashlib
        plan = json.loads(json.dumps(REAL))
        sh = ap.three_stage.shingles(ap.three_stage.words(ap.own_words(plan)))
        d = Path(self.sb.dir.name) / 'refs'
        d.mkdir()
        (d / 'ref1.json').write_text(json.dumps({'hashes': [hashlib.sha256(s.encode()).hexdigest()[:16] for s in sh]}))
        self.assertIn('REFERENCE_OVERLAP', ' '.join(ap.overlap_problems(plan, self.sb.plans, str(d / '*.json'))))

    def test_429_stops_the_day_and_is_never_retried(self):
        code, res = self.run_draft([(429, {'error': {'status': 'RESOURCE_EXHAUSTED'}})])
        self.assertEqual((code, res['status']), (3, 'PROVIDER_ERROR'))
        self.assertEqual(len(self.sb.calls), 1)
        self.assertIsNotNone(ap.budget.stopped(self.sb.ledger, NOW))
        code, res = ap.draft(self.sb.ledger, 'k', 'genesis-11-short', self.sb.plans, NOW + timedelta(minutes=5),
                             self.sb.post([]))
        self.assertEqual((code, res['status']), (3, 'BUDGET_REFUSED'))
        self.assertEqual(len(self.sb.calls), 1)  # no fallback model after a quota stop

    def test_uncertain_call_is_not_retried(self):
        code, res = self.run_draft([(None, None)])
        self.assertEqual((code, res['status']), (3, 'UNCERTAIN'))
        self.assertEqual(len(self.sb.calls), 1)
        self.assertEqual(self.sb.ledger['calls'][0]['status'], 'UNCERTAIN')

    def test_503_is_retried_once_as_a_counted_call(self):
        err = (503, {'error': {'status': 'UNAVAILABLE'}})
        code, res = self.run_draft([err, reply(outline_of(REAL))])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.sb.ledger['calls']), 2)
        code, res = ap.draft(ap.budget.empty(), 'k', 'genesis-11-short', Path(self.sb.dir.name) / 'plans2', NOW, self.sb.post([]))
        self.assertEqual(code, 4)

    def test_fallback_model_only_when_the_budget_refuses_the_first(self):
        for i in range(16):  # 80% of 20 RPD already reserved today for the primary
            self.sb.ledger['calls'].append({'id': 'x%d' % i, 'model': ap.MODELS[0], 'at': '2026-10-31T10:%02d:00Z' % i,
                                            'pacific_day': '2026-10-31', 'status': '200', 'tokens': 1})
        code, res = self.run_draft([reply(outline_of(REAL))])
        self.assertEqual(code, 0)
        self.assertEqual(self.sb.calls, [ap.MODELS[1]])

    def test_the_module_cannot_write_approvals_or_call_media_providers(self):
        text = (HERE / 'autopilot_plan.py').read_text().lower()
        for banned in ('approval.json', 'pavo', 'buzzy', 'merge_pull', 'pr merge'):
            self.assertNotIn(banned, text)

    def test_workflow_opens_a_pr_and_never_merges(self):
        wf = (HERE.parents[2] / '.github/workflows/autopilot-plan.yml').read_text().lower()
        self.assertIn('gh pr create', wf)
        for banned in ('pr merge', '--auto', 'merge_pull_request', 'approval.json', 'pavo', 'buzzy'):
            self.assertNotIn(banned, wf)
        self.assertIn('heroverse-gemini-budget', wf)


if __name__ == '__main__':
    unittest.main()
