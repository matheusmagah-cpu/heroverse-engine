#!/usr/bin/env python3
"""Autopilot lease (AUTOPILOT.md 2.2, step S16, phase A1-3): the same HEROVERSE_EXECUTOR_LEASE_V1 protocol on the ref
`claude/shared-executor-control` that OPERATIONS.md "Shared executor control" describes, with owner "autopilot".

Rules (pure decision + compare-and-swap transport):
- Missing or malformed control is INVALID: read-only, never a second controller.
- An active lease that has not expired is never taken, whoever holds it (codex, claude or another autopilot run).
  Available tokens do not transfer ownership. Only idle or expired control may be taken, and an expired one only
  after the caller says saved provider/workflow IDs were reconciled (--reconciled).
- Acquire/renew/release = a commit whose parent is exactly the observed head and whose tree is that head's tree,
  ref updated with force=false, then read back. A competing writer makes the update fail: LOST, never forced.
- Expiry is at most 55 minutes; renew at least every 10; release writes idle, owner null, expiry now.
- An uncertain write is reconciled by reading the ref once; the write is never replayed.
- The readers of the other executors accept owner codex/claude only: an autopilot lease never authorises a Pavo or
  private-audio effect (no Pavo from Actions); it only tells a live session to stay read-only.

CLI (env GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_RUN_ID):
  autopilot_lease.py acquire TASK NEXT_ACTION [--reconciled] | renew NEXT_ACTION | release NEXT_ACTION
Exit: 0 done, 4 BUSY (read-only), 5 INVALID, 6 LOST/uncertain.
"""
from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
import urllib.error
import urllib.request

SCHEMA = 'heroverse-executor-lease-v1'
MARKER = 'HEROVERSE_EXECUTOR_LEASE_V1\n'
REF = 'claude/shared-executor-control'
OWNER = 'autopilot'
MAX_MINUTES = 55
RENEW_MINUTES = 10
PRIVATE = re.compile(r'https?://|token|secret|password|api[_-]?key|bearer|AIza', re.I)


class LeaseError(Exception):
    pass


def _at(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _iso(at):
    return at.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse(message):
    """The lease dict, or raise LeaseError('LEASE_INVALID')."""
    try:
        if not message.startswith(MARKER):
            raise ValueError
        lease = json.loads(message[len(MARKER):])
        if lease.get('schema') != SCHEMA or lease.get('state') not in ('active', 'idle'):
            raise ValueError
        if lease['state'] == 'active':
            _at(lease['expires_at'])
            if not lease.get('owner') or not lease.get('run_id'):
                raise ValueError
        return lease
    except (ValueError, KeyError, TypeError, AttributeError):
        raise LeaseError('LEASE_INVALID') from None


def expired(lease, now):
    return lease['state'] != 'active' or _at(lease['expires_at']) <= now


def decide(message, run_id, now, reconciled=False):
    """('ACQUIRE'|'RENEW'|'BUSY'|'INVALID'|'NEEDS_RECONCILE', reason)."""
    try:
        lease = parse(message)
    except LeaseError:
        return 'INVALID', 'LEASE_INVALID'
    if lease['state'] == 'active' and not expired(lease, now):
        if lease.get('owner') == OWNER and str(lease.get('run_id')) == str(run_id):
            return 'RENEW', None
        return 'BUSY', 'LEASE_HELD_BY_%s' % str(lease.get('owner')).upper()
    if lease['state'] == 'active' and not reconciled:
        return 'NEEDS_RECONCILE', 'EXPIRED_HOLDER_%s' % str(lease.get('owner')).upper()
    return 'ACQUIRE', None


def build(run_id, task, next_action, base_main_sha, now, minutes=MAX_MINUTES, state='active'):
    """The lease commit message. Expiry never exceeds 55 minutes; descriptions stay generic (no links, no secrets)."""
    for text in (task, next_action):
        if PRIVATE.search(str(text)) or len(str(text)) > 200:
            raise LeaseError('LEASE_TEXT_NOT_GENERIC')
    body = {'schema': SCHEMA, 'task': str(task), 'base_main_sha': base_main_sha, 'next_action': str(next_action),
            'renewed_at': _iso(now)}
    if state == 'idle':
        body.update(owner=None, run_id=None, state='idle', expires_at=_iso(now))
    else:
        body.update(owner=OWNER, run_id=str(run_id), state='active',
                    expires_at=_iso(now + timedelta(minutes=min(int(minutes), MAX_MINUTES))))
    return MARKER + json.dumps(body, sort_keys=True)


def _reconcile(api, new):
    try:
        head = api('GET', '/git/ref/heads/' + REF)['object']['sha']
    except Exception:  # noqa: BLE001
        return 'UNCERTAIN', None
    return ('DONE', new) if head == new else ('LOST', None)


def _swap(api, head, message):
    """Compare-and-swap: child of the observed head, same tree, ref moved without force, read back."""
    parent = api('GET', '/git/commits/' + head)
    commit = api('POST', '/git/commits', {'message': message, 'tree': parent['tree']['sha'], 'parents': [head]})
    new = commit['sha']
    try:
        api('PATCH', '/git/refs/heads/' + REF, {'sha': new, 'force': False})
    except urllib.error.HTTPError as e:
        if e.code in (409, 422):
            return 'LOST', None
        return _reconcile(api, new)
    except Exception:  # noqa: BLE001 - outcome unknown: read the ref once, never replay
        return _reconcile(api, new)
    return _reconcile(api, new)


def run(api, cmd, run_id, task='', next_action='', now=None, reconciled=False, base_main_sha=''):
    """Returns (exit_code, result_dict). Never takes an active lease, never forces, never replays."""
    now = now or datetime.now(timezone.utc)
    try:
        head = api('GET', '/git/ref/heads/' + REF)['object']['sha']
        message = api('GET', '/git/commits/' + head).get('message', '')
    except Exception:  # noqa: BLE001 - missing control permits read-only diagnosis only
        return 5, {'verdict': 'INVALID', 'reason': 'LEASE_UNREADABLE'}
    verdict, reason = decide(message, run_id, now, reconciled)
    if cmd == 'acquire':
        if verdict == 'RENEW':
            verdict = 'ACQUIRE'  # already ours: the same compare-and-swap, new expiry
        if verdict != 'ACQUIRE':
            return (4 if verdict in ('BUSY', 'NEEDS_RECONCILE') else 5), {'verdict': verdict, 'reason': reason}
        msg = build(run_id, task, next_action, base_main_sha, now)
    elif cmd in ('renew', 'release'):
        if verdict != 'RENEW':
            return 6, {'verdict': 'LOST', 'reason': reason or 'NOT_OWNER'}  # stop new effects
        old = parse(message)
        msg = build(run_id, old.get('task', ''), next_action, old.get('base_main_sha', ''), now,
                    state='idle' if cmd == 'release' else 'active')
    else:
        raise SystemExit('USAGE')
    outcome, sha = _swap(api, head, msg)
    return (0 if outcome == 'DONE' else 6), {'verdict': outcome, 'sha': sha,
                                              'expires_at': json.loads(msg[len(MARKER):])['expires_at']}


def github_api(repo, token):
    def api(method, path, body=None):
        req = urllib.request.Request('https://api.github.com/repos/%s%s' % (repo, path),
                                     None if body is None else json.dumps(body).encode(),
                                     {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                                      'X-GitHub-Api-Version': '2022-11-28'}, method=method)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b'{}')
    return api


def main(argv):
    flags = [a for a in argv if a.startswith('--')]
    args = [a for a in argv if not a.startswith('--')]
    cmd = args[0]
    task, nxt = (args[1], args[2]) if cmd == 'acquire' else ('', args[1])
    api = github_api(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_TOKEN'])
    code, out = run(api, cmd, os.environ['GITHUB_RUN_ID'], task, nxt, reconciled='--reconciled' in flags,
                    base_main_sha=os.environ.get('GITHUB_SHA', ''))
    print(json.dumps(out))
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
