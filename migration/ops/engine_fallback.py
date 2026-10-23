#!/usr/bin/env python3
"""E57: when the runner cannot be woken (HERO_RUNNER_PAT rejected or missing), render on the engine itself.

The heartbeat's runner-wake job calls this with the engine's own GITHUB_TOKEN. It dispatches
pilot-render-stills.yml for the first due pilot whose images are ready and whose current script has no
current render, unless an engine render is already active or the daily cap is reached. No gate changes.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'production'))
import render_queue

REPO = 'matheusmagah-cpu/heroverse-engine'
WORKFLOW = 'pilot-render-stills.yml'
ACTIVE = ('queued', 'in_progress', 'waiting', 'requested', 'pending')
FALLBACK_FOR = ('BLOCKED_API_HTTP_401', 'BLOCKED_API_HTTP_403', 'BLOCKED_MISSING_HERO_RUNNER_PAT')
DAILY_CAP = 8      # a render takes about 2.5 h, so at most about 9 fit in a day; failures cannot loop forever
WINDOW = timedelta(hours=24)


def candidate(production, ledger, now):
    row = next((r for r in render_queue.due(production, ledger, now, 48)
                if not r['missing_images'] and not r['rendered']), None)
    return row['pilot'] if row else None


def decision(runs, now):
    if any(r.get('status') in ACTIVE for r in runs):
        return 'ENGINE_RENDER_ACTIVE'
    recent = [r for r in runs if r.get('event') == 'workflow_dispatch'
              and datetime.fromisoformat(r['created_at'].replace('Z', '+00:00')) >= now - WINDOW]
    if len(recent) >= DAILY_CAP:
        return 'ENGINE_DAILY_CAP'
    return 'DISPATCH'


class GitHub:
    def __init__(self, token):
        if not token:
            raise SystemExit('BLOCKED_MISSING_GITHUB_TOKEN')
        self.token = token

    def request(self, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        req = Request('https://api.github.com/repos/' + REPO + path, data=body, method='POST' if body else 'GET',
                      headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                               'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=20) as response:
                return None if body else json.load(response)
        except HTTPError as error:
            raise SystemExit('BLOCKED_ENGINE_API_HTTP_' + str(error.code)) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise SystemExit('BLOCKED_ENGINE_API_UNAVAILABLE') from None

    def runs(self):
        return self.request('/actions/workflows/' + WORKFLOW + '/runs?per_page=50')['workflow_runs']

    def dispatch(self, pilot):
        self.request('/actions/workflows/' + WORKFLOW + '/dispatches', {'ref': 'main', 'inputs': {'pilot': pilot}})


def execute(production, ledger_path, token, now=None, api_factory=GitHub):
    now = now or datetime.now(timezone.utc)
    api = api_factory(token)
    pilot = candidate(production, json.loads(Path(ledger_path).read_text()), now)
    if pilot is None:
        return 'QUEUE_EMPTY'
    verdict = decision(api.runs(), now)
    if verdict != 'DISPATCH':
        return verdict
    api.dispatch(pilot)
    return 'ENGINE_DISPATCH_ACCEPTED ' + pilot


def main():
    status = execute(sys.argv[1], sys.argv[2], os.environ.get('GITHUB_TOKEN', ''))
    print(status)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write('Engine render fallback: ' + status + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
