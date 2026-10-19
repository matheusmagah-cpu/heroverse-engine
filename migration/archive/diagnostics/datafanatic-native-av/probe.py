"""One JSON metadata request. No media request, redirect, retry, or integration."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = 'matheusmagah-cpu/heroverse-engine'
HOST = 'youtube-media-downloader.p.rapidapi.com'
ENDPOINT = 'https://' + HOST + '/v2/video/details'
PARAMS = {'videoId': 'j2rk8ycXe3c', 'urlAccess': 'normal', 'videos': 'true',
          'audios': 'true', 'subtitles': 'false', 'related': 'false', 'lang': 'en-US'}
LIMIT = 1024 * 1024
QUOTA = frozenset({'x-ratelimit-requests-limit', 'x-ratelimit-requests-remaining',
                   'x-ratelimit-requests-reset', 'x-ratelimit-bandwidth-limit',
                   'x-ratelimit-bandwidth-remaining', 'x-ratelimit-bandwidth-reset',
                   'x-ratelimit-units-limit', 'x-ratelimit-units-remaining',
                   'x-ratelimit-units-reset',
                   'x-ratelimit-rapid-free-plans-hard-limit-limit',
                   'x-ratelimit-rapid-free-plans-hard-limit-remaining',
                   'x-ratelimit-rapid-free-plans-hard-limit-reset'})
KNOWN_KEYS = frozenset(('id videoId video_id duration durationSeconds lengthSeconds '
                       'videos audios subtitles related items url formats title status '
                       'data video videoDetails details mimeType quality audioQuality '
                       'hasAudio hasVideo bitrate width height success error message').split())
ID_KEYS = frozenset({'videoId', 'video_id'})
DURATION_KEYS = frozenset({'duration', 'durationSeconds', 'lengthSeconds'})

class Stop(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Stop('redirect_blocked')

def fail(code):
    raise Stop(code)

def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail('duplicate_json_keys')
        result[key] = value
    return result

def parse_json(raw):
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=strict_pairs,
                          parse_constant=lambda _: fail('nonfinite_json'))
    except (UnicodeError, ValueError, RecursionError):
        fail('invalid_json')

def safe_key(key):
    # Unknown keys may themselves contain URLs, server messages, or credentials.
    return key if key in KNOWN_KEYS else 'field_' + hashlib.sha256(key.encode()).hexdigest()[:12]

def structure(value, depth=0):
    if depth > 24:
        return {'type': 'depth_limit'}
    if isinstance(value, dict):
        keys = list(value)[:64]
        return {'type': 'object', 'count': len(value), 'fields': {
            safe_key(k): structure(value[k], depth + 1) for k in keys},
            'truncated': len(value) > len(keys)}
    if isinstance(value, list):
        return {'type': 'array', 'count': len(value),
                'sample_types': sorted(set(type(v).__name__ for v in value)),
                'first': structure(value[0], depth + 1) if value else None}
    return {'type': type(value).__name__}

def observations(value):
    ids, durations = [], []
    # Candidate fields only; this traversal does not assert supplier schema equivalence.
    def walk(v):
        if isinstance(v, dict):
            for k, child in v.items():
                if k in ID_KEYS:
                    ids.append('match' if child == PARAMS['videoId'] else 'mismatch')
                if k in DURATION_KEYS:
                    durations.append('match' if type(child) in (int, float) and child == 12708
                                     or type(child) is str and child == '12708' else 'unverified')
                walk(child)
        elif isinstance(v, list):
            for child in v:
                walk(child)
    try:
        walk(value)
    except RecursionError:
        fail('json_depth_exceeded')
    return {'source_id_candidates': ids, 'duration_12708_candidates': durations,
            'schema_verified': False, 'native_media_candidate_verified': False}

def contains_secret(value, secret):
    if isinstance(value, str):
        return secret in value
    if isinstance(value, dict):
        return any(secret in k or contains_secret(v, secret) for k, v in value.items())
    if isinstance(value, list):
        return any(contains_secret(v, secret) for v in value)
    return False

def quota_headers(headers):
    # Only integer quota values; never arbitrary header values/server text.
    return {name: int(headers[name]) for name in QUOTA
            if headers.get(name) is not None and re.fullmatch(r'[0-9]{1,16}', headers[name])}

def validate_request(path):
    request = parse_json(Path(path).read_bytes())
    expected = {'method': 'GET', 'endpoint': ENDPOINT, 'params': PARAMS,
                'expected_duration_seconds': 12708, 'expected_quota_units': 3}
    if request != expected:
        fail('request_manifest_mismatch')

def run(manifest, output, opener=None):
    validate_request(manifest)
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY:
        fail('repository_mismatch')
    if os.environ.get('GITHUB_RUN_NUMBER') != '1' or os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
        fail('one_shot_guard')
    key = os.environ.get('HERO_RAPIDAPI_KEY', '')
    if not key or any(ord(c) < 33 or ord(c) > 126 for c in key):
        fail('missing_or_invalid_secret')
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Claim before transport. Any failure after this point is uncertain and never retried.
    try:
        with (output / 'attempt.claim').open('x') as claim:
            claim.write('claimed; no automatic rerun\n')
    except FileExistsError:
        fail('already_claimed')
    request = urllib.request.Request(ENDPOINT + '?' + urllib.parse.urlencode(PARAMS),
        headers={'x-rapidapi-host': HOST, 'x-rapidapi-key': key,
                 'Accept': 'application/json', 'Accept-Encoding': 'identity'}, method='GET')
    opener = opener or urllib.request.build_opener(NoRedirect())
    status = None
    response_headers = None
    try:
        with opener.open(request, timeout=30) as response:
            status = response.status if type(response.status) is int else None
            response_headers = response.headers
            if response.status != 200:
                fail('http_status_blocked')
            if response.geturl() != request.full_url:
                fail('destination_changed')
            if response.headers.get_content_type() != 'application/json':
                fail('non_json_content_type')
            if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                fail('encoded_response_blocked')
            length = response.headers.get('Content-Length')
            if length is not None and (not length.isdigit() or int(length) >= LIMIT):
                fail('response_size_blocked')
            raw = response.read(LIMIT)
            # Reject exactly-limit bodies too: never read an extra byte to detect truncation.
            if len(raw) >= LIMIT:
                fail('response_size_blocked')
            if length is not None and len(raw) != int(length):
                fail('incomplete_response')
            data = parse_json(raw)
            # A secret echo must never reach output, including the private artifact.
            if contains_secret(data, key) or key.encode() in raw:
                fail('secret_echo_blocked')
            # Stop on recognizable access challenges in JSON too, without logging them.
            lowered = raw.lower()
            if any(marker in lowered for marker in (b'captcha', b'login required',
                   b'authentication required', b'sign in to confirm', b'access denied')):
                fail('access_challenge_blocked')
            checks = observations(data)
            receipt = {'result': 'json_received_requires_private_inspection',
                       'bytes': len(raw), 'quota_headers': quota_headers(response.headers),
                       'structure': structure(data), 'validation': checks,
                       'recurring_bandwidth_gate': 'BLOCKED', 'quota_usage_proven': False,
                       'local_body_cap_bytes': LIMIT,
                       'provider_billing_total_proven': False,
                       'request_attempt_count': 1, 'media_request_count': 0,
                       'http_status': 200, 'request_state_uncertain': False}
            encoded_receipt = json.dumps(receipt, separators=(',', ':')).encode()
            if len(encoded_receipt) > LIMIT // 2:
                fail('receipt_size_blocked')
            with (output / 'response.json').open('xb') as f:
                os.chmod(f.name, 0o600)
                f.write(raw)
            with (output / 'receipt.json').open('xb') as f:
                f.write(encoded_receipt)
            return receipt
    except Stop as e:
        persist_failure(output, str(e), status=status, headers=response_headers)
        raise
    except urllib.error.HTTPError as e:
        # Do not read the error body or expose server messages/URLs.
        code = e.code if type(e.code) is int and 100 <= e.code <= 599 else None
        persist_failure(output, 'http_error_blocked', status=code,
                        headers=e.headers, uncertain=False)
        fail('http_error_blocked')
    except PermissionError:
        persist_failure(output, 'permission_error_no_rerun')
        fail('permission_error_no_rerun')
    except Exception:
        persist_failure(output, 'request_state_uncertain_no_rerun')
        fail('request_state_uncertain_no_rerun')

def persist_failure(output, result, status=None, headers=None, uncertain=True):
    receipt = {'result': result, 'http_status': status,
               'quota_headers': quota_headers(headers) if headers is not None else {},
               'request_attempt_count': 1, 'media_request_count': 0,
               'native_response_file_count': 0, 'request_state_uncertain': uncertain,
               'retry': False, 'recurring_bandwidth_gate': 'BLOCKED',
               'quota_usage_proven': False, 'provider_billing_total_proven': False,
               'local_body_cap_bytes': LIMIT}
    try:
        # A partial persistence failure must not leave a native JSON response.
        (output / 'response.json').unlink(missing_ok=True)
        with (output / 'receipt.json').open('w') as f:
            os.chmod(f.name, 0o600)
            json.dump(receipt, f, separators=(',', ':'))
    except OSError:
        fail('receipt_permission_or_io_error_no_rerun')
    print(json.dumps(receipt, separators=(',', ':')))


def main():
    def expired(*_):
        fail('deadline_exceeded_no_rerun')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(30)
    try:
        receipt = run(sys.argv[1], sys.argv[2])
        print(json.dumps(receipt, separators=(',', ':')))
        return 0
    except Stop as e:
        print(json.dumps({'result': str(e), 'retry': False}))
        return 1
    except PermissionError:
        print('{"result":"permission_error_no_rerun","retry":false}')
        return 1
    except Exception:
        print('{"result":"local_failure_no_rerun","retry":false}')
        return 1
    finally:
        signal.alarm(0)

if __name__ == '__main__':
    sys.exit(main())
