#!/usr/bin/env python3
"""Antidotes for the autopilot lease (AUTOPILOT.md 2.2 / section 4 'lease busy / crash')."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autopilot_lease as L  # noqa: E402

NOW = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)


def msg(owner, state='active', run='1', minutes=30, at=NOW):
    return L.MARKER + json.dumps({'schema': L.SCHEMA, 'owner': owner, 'run_id': run, 'state': state,
                                  'renewed_at': L._iso(at), 'expires_at': L._iso(at + timedelta(minutes=minutes)),
                                  'task': 't', 'base_main_sha': 'b', 'next_action': 'n'})


class Fake:
    """In-memory git: one ref, commits with message/tree/parent. PATCH is fast-forward-only (force=false)."""
    def __init__(self, first_message, patch_error=None, lose_race=False):
        self.commits = {'c0': {'message': first_message, 'tree': {'sha': 'T'}, 'parents': []}}
        self.head, self.calls, self.patch_error, self.lose_race = 'c0', [], patch_error, lose_race

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == 'GET' and path.startswith('/git/ref/'):
            return {'object': {'sha': self.head}}
        if method == 'GET':
            return self.commits[path.rsplit('/', 1)[1]]
        if method == 'POST':
            sha = 'c%d' % len(self.commits)
            self.commits[sha] = {'message': body['message'], 'tree': {'sha': body['tree']}, 'parents': body['parents']}
            return {'sha': sha}
        if self.patch_error:
            raise self.patch_error
        if self.lose_race:  # a sibling moved the ref first
            self.commits['cX'] = {'message': 'x', 'tree': {'sha': 'T'}, 'parents': [self.head]}
            self.head = 'cX'
        if self.commits[body['sha']]['parents'] != [self.head] or body['force'] is not False:
            raise urllib.error.HTTPError('u', 422, 'not ff', {}, None)
        self.head = body['sha']
        return {}


def body(fake):
    return json.loads(fake.commits[fake.head]['message'][len(L.MARKER):])


class Lease(unittest.TestCase):
    def test_active_unexpired_lease_is_never_taken(self):
        for owner in ('claude', 'codex', 'autopilot'):
            fake = Fake(msg(owner, run='other', minutes=1))
            code, out = L.run(fake, 'acquire', '9', 'plan', 'next', NOW, reconciled=True)
            self.assertEqual((code, out['verdict']), (4, 'BUSY'), owner)
            self.assertEqual(fake.head, 'c0')
            self.assertFalse([c for c in fake.calls if c[0] in ('POST', 'PATCH')])

    def test_missing_or_malformed_control_is_read_only(self):
        for m in ('hello', L.MARKER + '{not json', L.MARKER + json.dumps({'schema': 'x'})):
            fake = Fake(m)
            self.assertEqual(L.run(fake, 'acquire', '9', 'p', 'n', NOW)[0], 5)
            self.assertEqual(fake.head, 'c0')

    def test_expired_holder_needs_reconcile_then_is_taken(self):
        fake = Fake(msg('claude', minutes=-5))
        self.assertEqual(L.run(fake, 'acquire', '9', 'p', 'n', NOW)[0], 4)
        self.assertEqual(fake.head, 'c0')
        code, out = L.run(fake, 'acquire', '9', 'p', 'n', NOW, reconciled=True)
        self.assertEqual((code, out['verdict']), (0, 'DONE'))
        self.assertEqual(body(fake)['owner'], 'autopilot')

    def test_idle_is_taken_with_expiry_at_most_55_minutes_unchanged_tree_exact_parent_no_force(self):
        fake = Fake(msg(None, state='idle', run=None, minutes=0))
        code, _ = L.run(fake, 'acquire', '9', 'p', 'n', NOW)
        self.assertEqual(code, 0)
        b = body(fake)
        self.assertLessEqual(L._at(b['expires_at']) - NOW, timedelta(minutes=55))
        new = fake.commits[fake.head]
        self.assertEqual((new['parents'], new['tree']), (['c0'], {'sha': 'T'}))
        patch = [c for c in fake.calls if c[0] == 'PATCH'][0]
        self.assertIs(patch[2]['force'], False)
        self.assertEqual(L.build('1', 't', 'n', 'b', NOW, minutes=500).count('"expires_at"'), 1)
        self.assertEqual(json.loads(L.build('1', 't', 'n', 'b', NOW, minutes=500)[len(L.MARKER):])['expires_at'],
                         '2026-10-31T20:55:00Z')

    def test_competing_sibling_makes_acquire_fail_and_is_never_forced(self):
        fake = Fake(msg(None, state='idle', run=None, minutes=0), lose_race=True)
        code, out = L.run(fake, 'acquire', '9', 'p', 'n', NOW)
        self.assertEqual((code, out['verdict']), (6, 'LOST'))
        self.assertEqual(fake.head, 'cX')
        self.assertEqual(len([c for c in fake.calls if c[0] == 'PATCH']), 1)

    def test_uncertain_write_is_reconciled_by_reading_and_never_replayed(self):
        fake = Fake(msg(None, state='idle', run=None, minutes=0), patch_error=TimeoutError())
        code, out = L.run(fake, 'acquire', '9', 'p', 'n', NOW)
        self.assertEqual((code, out['verdict']), (6, 'LOST'))
        self.assertEqual(len([c for c in fake.calls if c[0] == 'PATCH']), 1)

    def test_renew_and_release_only_for_the_owning_run(self):
        fake = Fake(msg('autopilot', run='9', minutes=20))
        self.assertEqual(L.run(fake, 'renew', '9', next_action='n', now=NOW)[0], 0)
        self.assertEqual(L._at(body(fake)['expires_at']), NOW + timedelta(minutes=55))
        self.assertEqual(L.run(fake, 'renew', '8', next_action='n', now=NOW)[0], 6)  # stop new effects
        self.assertEqual(L.run(fake, 'release', '8', next_action='n', now=NOW)[0], 6)
        self.assertEqual(body(fake)['state'], 'active')
        self.assertEqual(L.run(fake, 'release', '9', next_action='done', now=NOW)[0], 0)
        b = body(fake)
        self.assertEqual((b['state'], b['owner'], b['expires_at']), ('idle', None, L._iso(NOW)))

    def test_a_lost_lease_cannot_be_renewed(self):
        fake = Fake(msg('claude', run='5', minutes=20))
        self.assertEqual(L.run(fake, 'renew', '9', next_action='n', now=NOW)[0], 6)
        self.assertEqual(fake.head, 'c0')

    def test_descriptions_stay_generic(self):
        for bad in ('see https://example.com/private', 'token abc', 'x' * 201):
            with self.assertRaises(L.LeaseError):
                L.build('1', 't', bad, 'b', NOW)

    def test_autopilot_owner_never_satisfies_the_pavo_readers(self):
        text = (Path(__file__).resolve().parents[1] / 'integrations/pavo/private_audio.py').read_text()
        self.assertIn("('codex', 'claude')", text)  # the effect readers accept only codex/claude
        self.assertNotIn('autopilot', text)


if __name__ == '__main__':
    unittest.main()
