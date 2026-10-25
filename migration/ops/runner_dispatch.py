#!/usr/bin/env python3
"""Bounded, fail-closed engine -> runner wake-up. No rendering/publication gates changed."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'production'))
import render_queue

REPO = 'matheusmagah-cpu/heroverse-runner'
WORKFLOW = 'render.yml'
ACTIVE = ('queued', 'in_progress', 'waiting', 'requested', 'pending')
WINDOW = timedelta(hours=24)
COOLDOWN = timedelta(minutes=45)
SETTLE = timedelta(minutes=5)
MAX_ATTEMPTS = 3
PREFIX = 'engine-wake '


class Blocked(Exception):
    pass


def timestamp(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('timezone required')
    return value


def history_page(data):
    if not isinstance(data, dict):
        raise Blocked('INVALID_RUN_HISTORY')
    count, rows = data.get('total_count'), data.get('workflow_runs')
    if type(count) is not int or count < 0 or not isinstance(rows, list) or len(rows) > count:
        raise Blocked('INVALID_RUN_HISTORY')
    return count, rows


def validate_run(row):
    if not isinstance(row, dict):
        raise Blocked('INVALID_RUN_METADATA')
    for field in ('status', 'event', 'display_title', 'created_at', 'updated_at'):
        if not isinstance(row.get(field), str) or not row[field]:
            raise Blocked('INVALID_RUN_METADATA')
    try:
        if timestamp(row['updated_at']) < timestamp(row['created_at']):
            raise ValueError('inverted timestamps')
    except (ValueError, TypeError):
        raise Blocked('INVALID_RUN_METADATA') from None


def candidate(production, ledger, now):
    row = render_queue.next_render(render_queue.due(production, ledger, now, 48))
    if row is None:
        return None
    script = (Path(production) / row['pilot'] / 'script.json').read_bytes()
    return hashlib.sha256(row['pilot'].encode() + b'\0' + script).hexdigest()


def decision(key, runs, now):
    if any(r['status'] != 'completed' for r in runs):
        return 'RUNNER_ACTIVE'
    recent = [r for r in runs if timestamp(r['created_at']) >= now - WINDOW]
    if any(now - timestamp(r['updated_at']) < SETTLE for r in recent):
        return 'SETTLING'
    matching = [r for r in recent if r.get('event') == 'workflow_dispatch'
                and r.get('display_title') == PREFIX + key]
    if len(matching) >= MAX_ATTEMPTS:
        return 'RETRY_LIMIT'
    # Failed automatic attempts for this artifact back off. Completed successful renders
    # for a different artifact never delay the next eligible item in the queue.
    if any(now - timestamp(r['updated_at']) < COOLDOWN for r in matching):
        return 'COOLDOWN'
    return 'DISPATCH'


class GitHub:
    def __init__(self, token):
        if not token:
            raise Blocked('MISSING_HERO_RUNNER_PAT')
        self.token = token

    def request(self, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request('https://api.github.com/repos/' + REPO + path, data=body,
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Accept': 'application/vnd.github+json',
                                   'X-GitHub-Api-Version': '2022-11-28',
                                   'Content-Type': 'application/json'},
                          method='POST' if body is not None else 'GET')
        try:
            with urlopen(request, timeout=20) as response:
                if body is not None:
                    if response.status != 204:
                        raise Blocked('DISPATCH_RESPONSE_UNEXPECTED')
                    return None
                return json.load(response)
        except HTTPError as error:
            raise Blocked('API_HTTP_' + str(error.code)) from None
        except (URLError, TimeoutError, OSError, ValueError):
            # Never print response bodies, request headers, or token; never retry POST.
            raise Blocked('API_UNAVAILABLE_OR_INVALID_RESPONSE') from None

    def runs(self, now):
        base = '/actions/workflows/' + WORKFLOW + '/runs'
        # Check active runs independently of age, including approvals and queued concurrency.
        for status in ACTIVE:
            data = self.request(base + '?per_page=1&status=' + status)
            count, _ = history_page(data)
            if count:
                return [{'status': status}]
        rows = []
        since = (now - WINDOW).strftime('%Y-%m-%dT%H:%M:%SZ')
        for page in range(1, 11):
            data = self.request(base + f'?per_page=100&page={page}&created=%3E%3D{since}')
            count, batch = history_page(data)
            for row in batch:
                validate_run(row)
            rows.extend(batch)
            if len(rows) >= count:
                return rows
            if not batch:
                break
        raise Blocked('INCOMPLETE_RUN_HISTORY')

    def dispatch(self, key):
        self.request('/actions/workflows/' + WORKFLOW + '/dispatches',
                     {'ref': 'main', 'inputs': {'dispatch_key': key}})


def execute(production, ledger_path, token, now=None, api_factory=GitHub):
    now = now or datetime.now(timezone.utc)
    api = api_factory(token)  # Missing credential is a configuration failure, even for an empty queue.
    ledger = json.loads(Path(ledger_path).read_text())
    key = candidate(production, ledger, now)
    if key is None:
        return 'QUEUE_EMPTY'
    verdict = decision(key, api.runs(now), now)
    if verdict == 'DISPATCH':
        api.dispatch(key)
        return 'DISPATCH_ACCEPTED'  # Acceptance is not proof a render started or succeeded.
    return verdict


def main():
    try:
        status = execute(sys.argv[1], sys.argv[2], os.environ.get('HERO_RUNNER_PAT', ''))
        code = 0
    except Blocked as error:
        status, code = 'BLOCKED_' + str(error), 1
    except (ValueError, KeyError, TypeError, OSError):
        status, code = 'BLOCKED_INVALID_QUEUE_OR_HISTORY', 1
    print(status)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write('Runner wake-up: ' + status + '\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
