"""Bounded read-only inspection of the cloud account already used by HeroVerse.

Never deploys, purchases, changes billing, reads token values, or emits raw API
responses. A successful list request is not permission to deploy or a cost quote.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

BASE = 'https://api.cloudflare.com/client/v4'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('REDIRECT_REFUSED')


def reader(token):
    def get(path):
        if not re.fullmatch(r'/accounts(?:/[a-f0-9]{32}/(?:workers/scripts|workers/subdomain|subscriptions))?', path):
            raise ValueError('PATH_NOT_ALLOWED')
        request = urllib.request.Request(BASE + path, headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}, method='GET')
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
                data = response.read(1_000_001)
                if len(data) > 1_000_000:
                    return 0, {'success': False}
                return response.status, json.loads(data)
        except urllib.error.HTTPError as error:
            return error.code, {'success': False}
        except Exception:
            return 0, {'success': False}
    return get


def inspect(account, credential_present, read):
    result = {'schema': 'heroverse-cloud-readiness-v1', 'deployed': False,
              'generation_enabled': False, 'purchases_enabled': False,
              'deployment_permission': 'NOT_VERIFIED', 'billing_state': 'NOT_VERIFIED',
              'worker_list_readable': False, 'worker_count': None,
              'worker_subdomain_readable': False, 'subscription_count': None,
              'status': 'CREDENTIAL_NOT_CONFIGURED', 'http_status': {}}
    if not credential_present:
        return result
    if not account:
        status, body = read('/accounts')
        rows = body.get('result') if isinstance(body, dict) else None
        if status != 200 or body.get('success') is not True or not isinstance(rows, list) or len(rows) != 1:
            result['status'] = 'ACCOUNT_BINDING_REQUIRED'
            return result
        account = rows[0].get('id', '')
    if not re.fullmatch('[a-f0-9]{32}', account):
        raise ValueError('ACCOUNT_IDENTIFIER_INVALID')
    paths = {'workers': 'workers/scripts', 'subdomain': 'workers/subdomain', 'subscriptions': 'subscriptions'}
    for name, suffix in paths.items():
        status, body = read(f'/accounts/{account}/{suffix}')
        result['http_status'][name] = status
        if status != 200 or not isinstance(body, dict) or body.get('success') is not True:
            continue
        rows = body.get('result')
        if name == 'workers' and isinstance(rows, list):
            result['worker_list_readable'] = True
            result['worker_count'] = len(rows)
        elif name == 'subdomain' and isinstance(rows, dict):
            result['worker_subdomain_readable'] = isinstance(rows.get('subdomain'), str) and bool(rows['subdomain'])
        elif name == 'subscriptions' and isinstance(rows, list):
            result['subscription_count'] = len(rows)
            result['billing_state'] = 'READABLE_NOT_A_COST_QUOTE'
    result['status'] = ('READABLE_DEPLOYMENT_NOT_AUTHORIZED' if result['worker_list_readable']
                        and result['worker_subdomain_readable'] else 'CLOUD_ACCESS_INCOMPLETE')
    return result


def main():
    if os.environ.get('GITHUB_REPOSITORY') != 'matheusmagah-cpu/heroverse-engine' or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise SystemExit('MAIN_REPOSITORY_REQUIRED')
    token = os.environ.get('CLOUDFLARE_API_TOKEN', '')
    account = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')
    try:
        report = inspect(account, bool(token), reader(token))
    except Exception:
        report = {'schema': 'heroverse-cloud-readiness-v1', 'status': 'INPUT_OR_RESPONSE_INVALID',
                  'deployed': False, 'generation_enabled': False}
    report['checked_at'] = datetime.now(timezone.utc).isoformat()
    out = Path(os.environ['RUNNER_TEMP']) / 'buzzy-cloud-readiness.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))

if __name__ == '__main__':
    main()
