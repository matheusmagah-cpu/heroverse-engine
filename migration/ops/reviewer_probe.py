#!/usr/bin/env python3
"""E58 root cause: is the designated reviewer down for any request, or only for our video requests?

One tiny text request ("Reply OK", 5 output tokens) per free model, plus the model listing. Prints model,
HTTP status, provider status and seconds only: never the key, never a response body beyond the status line.
Usage (Actions, HERO_GEMINI_API_KEY in env): reviewer_probe.py OUT_JSON
"""
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mining'))
from gemini_public_av import FREE_MODELS, sanitized_provider_error  # noqa: E402

BASE = 'https://generativelanguage.googleapis.com/v1beta/models'


def probe(model, key):
    body = json.dumps({'contents': [{'role': 'user', 'parts': [{'text': 'Reply OK'}]}],
                       'generationConfig': {'maxOutputTokens': 5}}).encode()
    req = urllib.request.Request(f'{BASE}/{model}:generateContent', data=body, method='POST',
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return {'model': model, 'http': r.status, 'seconds': round(time.time() - t, 2)}
    except urllib.error.HTTPError as e:
        d = sanitized_provider_error(e.read(8193), e.code, key)
        return {'model': model, 'http': e.code, 'provider_status': d.get('provider_status'),
                'message': str(d.get('message', ''))[:160], 'seconds': round(time.time() - t, 2)}
    except Exception as e:  # noqa: BLE001
        return {'model': model, 'http': None, 'error': type(e).__name__, 'seconds': round(time.time() - t, 2)}


def listed(key):
    req = urllib.request.Request(f'{BASE}?pageSize=200', headers={'x-goog-api-key': key})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            models = json.load(r).get('models', [])
        return sorted(m['name'].split('/')[-1] for m in models if 'generateContent' in m.get('supportedGenerationMethods', []))
    except Exception as e:  # noqa: BLE001
        return [f'LIST_FAILED {type(e).__name__}']


def main(out):
    key = os.environ['HERO_GEMINI_API_KEY']
    result = {'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'probes': [probe(m, key) for m in FREE_MODELS],
              'listed_flash_models': [m for m in listed(key) if 'flash' in m]}
    Path(out).write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main(sys.argv[1])
