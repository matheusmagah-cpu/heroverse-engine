#!/usr/bin/env python3
"""Antidotes for the autopilot sources step (AUTOPILOT.md S5-S9 / section 4 'no footage, repeat review, Gemini stop')."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import urllib.parse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autopilot_sources as src  # noqa: E402
import scene_stills  # noqa: E402

NOW = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)
EP = 'genesis-11-short'


def jpeg(seed):
    from PIL import Image
    im = Image.new('RGB', (1100, 1800), (seed * 40 % 255, 90, 60))
    buf = io.BytesIO()
    im.save(buf, 'JPEG')
    return buf.getvalue()


class Net:
    """Commons search + per-file API + file bytes, for a handful of titles."""
    def __init__(self, n=400, licence=('pd', 'Public domain')):
        pool = [jpeg(i + 1) for i in range(6)]
        self.files = {'F%03d.jpg' % i: pool[i % 6] for i in range(n)}
        self.licence = licence
        self.urls = []

    def info(self, t):
        data = self.files[t]
        return {'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/' + t,
                'descriptionurl': 'https://commons.wikimedia.org/wiki/File:' + t, 'width': 1100, 'height': 1800,
                'mime': 'image/jpeg', 'sha1': hashlib.sha1(data).hexdigest(),
                'extmetadata': {'License': {'value': self.licence[0]}, 'LicenseShortName': {'value': self.licence[1]},
                                'ObjectName': {'value': t}, 'Artist': {'value': 'An Old Master'}}}

    def __call__(self, url):
        self.urls.append(url)
        if 'generator=search' in url:
            q = urllib.parse.unquote(url.split('gsrsearch=')[1].split('&')[0])
            names = sorted(self.files)
            off = int(hashlib.sha1(q.encode()).hexdigest(), 16) % (len(names) - 20)   # a different window per query
            return json.dumps({'query': {'pages': [{'index': i, 'title': 'File:' + t, 'imageinfo': [self.info(t)]}
                                                   for i, t in enumerate(names[off:off + 18])]}}).encode()
        if 'titles=' in url:
            t = urllib.parse.unquote(url.split('titles=')[1]).removeprefix('File:')
            return json.dumps({'query': {'pages': [{'imageinfo': [self.info(t)]}]}}).encode()
        return self.files[url.rsplit('/', 1)[1]]


def gem(obj, status=200):
    return status, {'modelVersion': 'gemini-3.5-flash-lite', 'usageMetadata': {'totalTokenCount': 900},
                    'candidates': [{'content': {'parts': [{'text': json.dumps(obj)}]}}]}


class Clock:
    """A callable `now` whose sleep() moves it, so the per-minute window passes without waiting."""
    def __init__(self):
        self.t = NOW

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        from datetime import timedelta
        self.t += timedelta(seconds=seconds)


class Sandbox:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        scene_stills.REPO = self.root
        self.stills = self.root / 'stills'
        self.plan_path = self.root / (EP + '.json')
        plan = json.loads((HERE / 'plans' / (EP + '.json')).read_text())
        for s in plan['shots']:
            s.pop('first_frame', None)
        self.plan_path.write_text(json.dumps(plan))
        self.plan = plan
        self.ledger = src.budget.empty()
        self.calls = []

    def post(self, replies):
        it = iter(replies)

        def f(model, body, key, timeout=0):
            self.calls.append((model, body))
            r = next(it)
            return r(body) if callable(r) else r
        return f

    def run(self, replies=(), net=None, **kw):
        clock = Clock()
        self.clock = clock
        return src.run(self.plan_path, self.ledger, 'k', clock, self.stills, net or Net(), self.sb_post(replies),
                       clock.sleep, root=self.root, evidence_dir=self.root / 'ev',
                       library=HERE.parents[1] / 'production/footage/library', **kw)

    def sb_post(self, replies):
        return self.post(replies)


def maybe_all(body):
    ids = [p['text'] for p in body['contents'][0]['parts'] if 'text' in p][0]
    got = json.loads(ids[ids.index('with ids ') + 9:ids.index('. Answer')])
    return gem({'images': [{'id': i, 'verdict': 'MAYBE', 'reasons': [], 'match': 7} for i in got]})


class Sources(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self._repo = scene_stills.REPO

    def tearDown(self):
        scene_stills.REPO = Path(src.ROOT)
        self.sb.tmp.cleanup()

    def test_queries_are_deterministic_and_only_for_anonymous_scenes(self):
        q1, q2 = src.shot_queries(self.sb.plan), src.shot_queries(self.sb.plan)
        self.assertEqual(q1, q2)
        self.assertNotIn('s-voice', q1)                       # God's voice: Pavo/Claude route
        self.assertFalse([k for k in q1 if k.startswith('k-')])  # Keeper: Pavo/Claude route
        self.assertIn('s-colour', q1)
        self.assertTrue(all(len(v['still']) == 2 and v['footage'] for v in q1.values()))
        routes = {r['shot'] for r in src.routed_to_claude(self.sb.plan)}
        self.assertTrue({'s-voice', 'k-close'} <= routes)

    def test_full_run_lists_candidates_sheet_clips_and_writes_no_approval(self):
        shots = len(src.shot_queries(self.sb.plan))
        code, res = self.sb.run([maybe_all] * shots)
        self.assertEqual(code, 0, res.get('prefilter'))
        self.assertEqual(res['approvals_written'], 0)
        cands = [c for r in res['stills'].values() for c in r['candidates']]
        self.assertTrue(cands)
        for c in cands:
            self.assertTrue(c['prefilter']['evidence_only'])
            self.assertEqual(c['prefilter']['verdict'], 'MAYBE')
            rec = json.loads((self.root_of(c)).with_suffix('.json').read_text())
            self.assertEqual(rec['status'], 'DRAFT')            # never APPROVED here
            self.assertNotIn('approved', rec)
        for p in self.sb.stills.glob('*.json'):
            self.assertEqual(json.loads(p.read_text())['status'], 'DRAFT')
        self.assertTrue((self.sb.root / res['sheet']).exists())
        self.assertTrue(all(len(r['candidates']) <= src.PER_SHOT for r in res['stills'].values()))
        plan = json.loads(self.sb.plan_path.read_text())
        self.assertTrue(all(s.get('first_frame') for s in plan['shots'] if src.eligible(s)))
        self.assertFalse([s for s in plan['shots'] if not src.eligible(s) and s.get('first_frame')])
        self.assertTrue((self.sb.root / 'ev' / ('sources-%s.json' % EP)).exists())
        self.assertFalse(any('APPROVAL' in str(p) for p in self.sb.root.rglob('*')))

    def root_of(self, c):
        return self.sb.root / c['repo_path']

    def test_only_gemini_flash_lite_is_used_and_never_pavo_or_buzzy(self):
        code, res = self.sb.run([maybe_all] * 40)
        self.assertEqual({m for m, _ in self.sb.calls}, {'gemini-3.5-flash-lite'})
        text = (HERE / 'autopilot_sources.py').read_text().lower()
        for banned in ('pavo_', 'buzzy', 'mcp__', 'approve(', 'approval.json', 'claude_seen_review', "['claude_seen']", 'footage_seen(', 'reviewer_identity'):
            self.assertNotIn(banned, text)

    def test_prefilter_can_reject_only_with_a_reason_and_rejects_leave_the_pr(self):
        def reject_first(body):
            ids = json.loads([p['text'] for p in body['contents'][0]['parts'] if 'text' in p][0].split('with ids ')[1].split('. Answer')[0])
            return gem({'images': [{'id': ids[0], 'verdict': 'REJECT', 'reasons': ['watermark text']}] +
                        [{'id': i, 'verdict': 'REJECT', 'reasons': []} for i in ids[1:2]] +
                        [{'id': i, 'verdict': 'ACCEPT'} for i in ids[2:]]})
        code, res = self.sb.run([reject_first] * 40)
        row = res['stills']['s-colour']
        self.assertEqual(len(row['rejected_prefilter']), 1)
        self.assertFalse(self.root_of(row['rejected_prefilter'][0]).exists())      # dropped from the PR
        self.assertEqual(row['rejected_prefilter'][0]['prefilter']['reasons'], ['watermark text'])
        verdicts = [c['prefilter']['verdict'] for c in row['candidates']]
        self.assertEqual(verdicts, ['MAYBE'] * len(verdicts))                      # REJECT without reason, ACCEPT: MAYBE
        self.assertNotIn('ACCEPT', json.dumps(res['stills']))

    def test_429_stops_gemini_for_the_day_candidates_are_still_listed_unfiltered(self):
        code, res = self.sb.run([(429, {'error': {'status': 'RESOURCE_EXHAUSTED'}})])
        self.assertEqual(code, 3)
        self.assertEqual(len(self.sb.calls), 1)                                    # never retried, no second shot call
        self.assertTrue(res['prefilter']['status'].startswith('STOPPED'))
        cands = [c for r in res['stills'].values() for c in r['candidates']]
        self.assertTrue(cands and all(c['prefilter']['verdict'] == 'NOT_RUN' for c in cands[:1]))
        self.assertIsNotNone(src.budget.stopped(self.sb.ledger, NOW))

    def test_uncertain_call_is_not_retried(self):
        code, res = self.sb.run([(None, None)])
        self.assertEqual((code, len(self.sb.calls)), (3, 1))
        self.assertEqual(self.sb.ledger['calls'][0]['status'], 'UNCERTAIN')

    def test_licence_refused_by_the_source_api_is_recorded_not_listed(self):
        code, res = self.sb.run([], net=Net(licence=('cc-by-nc-4.0', 'CC BY-NC 4.0')), gemini=False)
        self.assertEqual(code, 0)
        self.assertFalse([c for r in res['stills'].values() for c in r['candidates']])
        self.assertEqual(self.sb.calls, [])

    def test_all_rejected_triggers_one_rephrase_round_only(self):
        def reject_all(body):
            ids = json.loads([p['text'] for p in body['contents'][0]['parts'] if 'text' in p][0].split('with ids ')[1].split('. Answer')[0])
            return gem({'images': [{'id': i, 'verdict': 'REJECT', 'reasons': ['modern object']} for i in ids]})

        def route(body):
            text = [p['text'] for p in body['contents'][0]['parts'] if 'text' in p][0]
            return gem({'queries': ['ancient valley rainbow', 'storm clouds valley']}) if 'search queries' in text else reject_all(body)
        shots = len(src.shot_queries(self.sb.plan))
        net = Net()
        code, res = self.sb.run([route] * 200, net=net)
        rephrases = [c for c in self.sb.ledger['calls'] if c['purpose'].startswith('sources rephrase')]
        self.assertEqual(len(rephrases), shots)                                    # one per emptied shot, once
        self.assertLessEqual(len([c for c in self.sb.ledger['calls'] if 'prefilter' in c['purpose']]), 2 * shots)

    def test_clips_come_from_the_vetted_library_and_missing_ones_become_footage_queries(self):
        code, res = self.sb.run([maybe_all] * 40, gemini=False)
        for sid, rows in res['clips'].items():
            for c in rows:
                self.assertEqual(c['vetting'], 'APPROVED')
                self.assertFalse(c['claude_seen'])
        fq = res['footage_queries']
        self.assertEqual(fq['version'], 'footage-queries-v1')
        self.assertEqual(len(fq['themes']), len([s for s, r in res['clips'].items() if len(r) < src.CLIPS_PER_SHOT]))

    def test_workflow_opens_a_pr_and_never_merges_or_approves(self):
        wf = (HERE.parents[2] / '.github/workflows/autopilot-sources.yml').read_text().lower()
        self.assertIn('gh pr create', wf)
        for banned in ('pr merge', '--auto', 'merge_pull_request', 'pavo', 'buzzy', 'approval.json'):
            self.assertNotIn(banned, wf)
        self.assertIn('heroverse-gemini-budget', wf)


if __name__ == '__main__':
    unittest.main()
