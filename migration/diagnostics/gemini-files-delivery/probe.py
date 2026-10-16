#!/usr/bin/env python3
"""One Files delivery proof. No generation, token-count, billing or delete calls."""
from __future__ import annotations
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime_bridge'))
# Reuse the existing adapter's serialization and redacted-error contract only.
from gemini_public_av import canonical, ProviderFailure
from build_c01 import MAX_BYTES, RECIPE_SHA256

ORIGIN = 'https://generativelanguage.googleapis.com'
UPLOAD_ENDPOINT = ORIGIN + '/upload/v1beta/files'
POLL_SECONDS = 120
POLL_INTERVAL = 5
MAX_RESPONSE = 65536
FILE_NAME = r'files/[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?'


def require(ok, code):
    if not ok:
        raise ProviderFailure(code)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def check_boundary(env):
    checks = {
        'GITHUB_REPOSITORY': 'matheusmagah-cpu/heroverse-engine',
        'HERO_REPOSITORY_PRIVATE': 'true', 'GITHUB_REF': 'refs/heads/main',
        'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_RUN_ATTEMPT': '1',
        'GITHUB_RUN_NUMBER': '2',
        'GITHUB_WORKFLOW_REF': 'matheusmagah-cpu/heroverse-engine/.github/workflows/gemini-files-delivery-once.yml@refs/heads/main',
    }
    require(all(env.get(k) == v for k, v in checks.items()), 'PRIVATE_MAIN_FIRST_MANUAL_RUN_REQUIRED')
    require(re.fullmatch(r'[a-f0-9]{40}', env.get('GITHUB_SHA', '')) is not None, 'COMMIT_SHA_REQUIRED')


def validate_upload_url(url):
    require(type(url) is str and len(url) <= 4096, 'UPLOAD_URL_REJECTED')
    try:
        p = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(p.query, strict_parsing=True)
        valid = (p.scheme == 'https' and p.netloc == 'generativelanguage.googleapis.com'
                 and p.path == '/upload/v1beta/files' and not p.fragment
                 and set(query) <= {'upload_id', 'upload_protocol'}
                 and len(query.get('upload_id', [])) == 1
                 and re.fullmatch(r'[A-Za-z0-9_-]{1,2048}', query['upload_id'][0]) is not None
                 and query.get('upload_protocol', ['resumable']) == ['resumable'])
    except Exception:
        valid = False
    require(valid, 'UPLOAD_URL_REJECTED')
    return url


def validate_request(method, url, headers, body):
    if method == 'POST' and url == UPLOAD_ENDPOINT:
        require(body == canonical({'file': {'displayName': 'c01.mp4'}}), 'START_BODY_REJECTED')
        require(headers.get('X-Goog-Upload-Command') == 'start', 'START_HEADERS_REJECTED')
    elif method == 'POST':
        validate_upload_url(url)
        require(type(body) is bytes and 0 < len(body) <= MAX_BYTES, 'UPLOAD_BYTES_REJECTED')
        require(headers.get('X-Goog-Upload-Command') == 'upload, finalize', 'UPLOAD_HEADERS_REJECTED')
    elif method == 'GET':
        require(re.fullmatch(re.escape(ORIGIN + '/v1beta/') + FILE_NAME, url) is not None
                and body is None, 'METADATA_URL_REJECTED')
    else:
        raise ProviderFailure('METHOD_REJECTED')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def transport(method, url, *, headers, body=None, timeout=15):
    """Explicit allowlist, no redirects/proxies/retries; never return raw HTTP errors."""
    validate_request(method, url, headers, body)
    require(0 < timeout <= 20, 'REQUEST_TIMEOUT_REJECTED')
    request = urllib.request.Request(url, method=method, headers=headers, data=body)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            require(response.status == 200, 'UNEXPECTED_HTTP_STATUS')
            raw = response.read(MAX_RESPONSE + 1)
            require(len(raw) <= MAX_RESPONSE, 'RESPONSE_SIZE_LIMIT')
            # Upload URL lives in memory only; it contains a session capability.
            result_headers = {'upload_url': response.headers.get('X-Goog-Upload-URL')}
        return result_headers, json.loads(raw) if raw else {}
    except ProviderFailure:
        raise
    except urllib.error.HTTPError as error:
        raise ProviderFailure('HTTP_' + str(error.code)) from None
    except Exception:
        raise ProviderFailure('NETWORK_OR_RESPONSE_FAILED_NO_RETRY') from None


@contextmanager
def wall_budget(seconds):
    """Linux alarm bounds whole poll phase, including slow socket reads."""
    def expired(_signum, _frame):
        raise ProviderFailure('METADATA_POLL_DEADLINE')
    old_handler = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def verify_local(root):
    preflight = json.loads((root / 'preflight.json').read_text())
    media = (root / 'stimuli/c01.mp4').read_bytes()
    manifest_raw = (root / 'operator-only/manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    require(preflight.get('version') == 'heroverse-gemini-files-preflight-v1'
            and preflight.get('filename') == 'c01.mp4'
            and preflight.get('mime_type') == 'video/mp4'
            and preflight.get('duration_seconds') == 6
            and preflight.get('nominal_audio_onset_minus_flash_seconds') == .5
            and preflight.get('pixels_and_pcm_verified') is True
            and preflight.get('all_checks_passed') is True
            and preflight.get('recipe_source_sha256') == RECIPE_SHA256, 'OFFLINE_PREFLIGHT_REQUIRED')
    require(0 < len(media) <= MAX_BYTES and media[4:8] == b'ftyp'
            and len(media) == preflight.get('size_bytes')
            and hashlib.sha256(media).hexdigest() == preflight.get('sha256')
            and hashlib.sha256(manifest_raw).hexdigest() == preflight.get('manifest_sha256'), 'LOCAL_INPUT_BINDING_FAILED')
    require(manifest.get('all_checks_passed') is True and len(manifest.get('files', [])) == 1,
            'LOCAL_MANIFEST_REQUIRED')
    r = manifest['files'][0]
    require(r['filename'] == 'c01.mp4' and r['sha256'] == preflight['sha256']
            and r['size_bytes'] == len(media) and r['verification'] == 'PASS'
            and r['video']['duration_seconds'] == 6 and r['audio']['duration_seconds'] == 6
            and r['audio']['nominal_audio_shift_seconds'] == .5, 'LOCAL_MANIFEST_BINDING_FAILED')
    return media, preflight


def file_identity(meta):
    name = meta.get('name')
    require(type(name) is str and re.fullmatch(FILE_NAME, name) is not None, 'FILE_NAME_REJECTED')
    return name


def decode_remote_sha256(value):
    """Canonical base64 of digest32 or the observed lowercase ASCII hex64."""
    try:
        require(type(value) is str and len(value) in (44, 88), 'REMOTE_HASH_INVALID')
        raw = base64.b64decode(value, validate=True)
        require(base64.b64encode(raw).decode('ascii') == value, 'REMOTE_HASH_INVALID')
    except ProviderFailure:
        raise
    except Exception:
        raise ProviderFailure('REMOTE_HASH_INVALID') from None
    if len(raw) == 32:
        return raw.hex(), 'BASE64_RAW_SHA256_32_BYTES'
    if len(raw) == 64 and re.fullmatch(rb'[0-9a-f]{64}', raw):
        return raw.decode('ascii'), 'BASE64_ASCII_LOWERCASE_HEX_64_BYTES'
    raise ProviderFailure('REMOTE_HASH_INVALID')


def verify_remote(meta, preflight, name):
    require(meta.get('name') == name, 'REMOTE_IDENTITY_CHANGED')
    require(meta.get('state') == 'ACTIVE', 'REMOTE_NOT_ACTIVE')
    require(meta.get('mimeType') == 'video/mp4', 'REMOTE_MIME_MISMATCH')
    require(str(meta.get('sizeBytes')) == str(preflight['size_bytes']), 'REMOTE_SIZE_MISMATCH')
    actual_hash, hash_representation = decode_remote_sha256(meta.get('sha256Hash'))
    require(actual_hash == preflight['sha256'], 'REMOTE_HASH_MISMATCH')
    duration = meta.get('videoMetadata', {}).get('videoDuration')
    require(type(duration) is str and re.fullmatch(r'\d+(?:\.\d{1,9})?s', duration) is not None,
            'REMOTE_DURATION_MISSING_OR_INVALID')
    require(abs(Decimal(duration[:-1]) - Decimal('6')) <= Decimal('0.034'), 'REMOTE_DURATION_MISMATCH')
    require(meta.get('uri') == ORIGIN + '/v1beta/' + name, 'REMOTE_URI_REJECTED')
    return {'state': 'ACTIVE', 'mime_type': 'video/mp4', 'size_bytes': int(meta['sizeBytes']),
            'sha256': actual_hash, 'sha256_representation': hash_representation, 'video_duration_seconds': float(Decimal(duration[:-1])),
            'duration_tolerance_seconds': .034, 'all_four_metadata_checks_passed': True}


def deliver(media, preflight, *, api_key, receipt, checkpoint, send=transport,
            monotonic=time.monotonic, sleep=time.sleep):
    require(type(api_key) is str and 20 <= len(api_key) <= 256 and api_key.isascii()
            and not any(c.isspace() for c in api_key), 'SECRET_MISSING_OR_MALFORMED')
    auth = {'x-goog-api-key': api_key}
    receipt['stage'] = 'UPLOAD_START_REQUESTED'
    receipt['upload_start_calls'] += 1
    checkpoint(receipt)  # Durable local claim before each effect; never auto-replay.
    headers, _ = send('POST', UPLOAD_ENDPOINT, headers={**auth,
        'Content-Type': 'application/json', 'X-Goog-Upload-Protocol': 'resumable',
        'X-Goog-Upload-Command': 'start', 'X-Goog-Upload-Header-Content-Length': str(len(media)),
        'X-Goog-Upload-Header-Content-Type': 'video/mp4'},
        body=canonical({'file': {'displayName': 'c01.mp4'}}), timeout=20)
    upload_url = validate_upload_url(headers.get('upload_url'))
    receipt['stage'] = 'BYTES_UPLOAD_REQUESTED'
    receipt['bytes_upload_calls'] += 1
    checkpoint(receipt)
    _, response = send('POST', upload_url, headers={**auth, 'Content-Type': 'video/mp4',
        'Content-Length': str(len(media)), 'X-Goog-Upload-Offset': '0',
        'X-Goog-Upload-Command': 'upload, finalize'}, body=media, timeout=20)
    meta = response.get('file', {})
    name = file_identity(meta)
    receipt['file_resource_name'] = name  # Resource ID only, never session URL/authentication.
    receipt['stage'] = 'AWAITING_ACTIVE'
    checkpoint(receipt)
    deadline = monotonic() + POLL_SECONDS
    with wall_budget(POLL_SECONDS):
        while True:
            require(meta.get('name') == name, 'REMOTE_IDENTITY_CHANGED')
            state = meta.get('state')
            require(state in ('PROCESSING', 'ACTIVE', 'FAILED'), 'REMOTE_STATE_UNRECOGNIZED')
            receipt['last_state'] = state
            checkpoint(receipt)
            require(state != 'FAILED', 'REMOTE_PROCESSING_FAILED')
            if state == 'ACTIVE':
                break
            remaining = deadline - monotonic()
            require(remaining > POLL_INTERVAL, 'METADATA_POLL_DEADLINE')
            sleep(POLL_INTERVAL)
            remaining = deadline - monotonic()
            require(remaining > 0, 'METADATA_POLL_DEADLINE')
            receipt['metadata_get_calls'] += 1
            checkpoint(receipt)
            _, meta = send('GET', ORIGIN + '/v1beta/' + name, headers=auth,
                           timeout=min(15, remaining))
    receipt['remote_verification'] = verify_remote(meta, preflight, name)
    receipt['stage'] = 'DELIVERY_VERIFIED'
    receipt['status'] = 'PASS_FILES_DELIVERY_ONLY'
    receipt['model_understanding'] = 'NOT_TESTED'
    checkpoint(receipt)
    return receipt


def main():
    root = Path('gemini-files-delivery-output').resolve()
    receipt_path = root / 'receipt.json'
    claim_path = root / 'attempt-claim.json'
    own_claim = False
    receipt = {'version': 'heroverse-gemini-files-delivery-v1', 'started_at': utcnow(),
               'status': 'NOT_STARTED', 'stage': 'LOCAL_BOUNDARY',
               'upload_start_calls': 0, 'bytes_upload_calls': 0, 'metadata_get_calls': 0,
               'generate_content_calls': 0, 'count_tokens_calls': 0, 'delete_calls': 0,
               'billing_changes': 0, 'automatic_retry': False,
               'quality_authorized': False, 'production_authorized': False,
               'publication_authorized': False}
    def checkpoint(value):
        tmp = receipt_path.with_suffix('.tmp')
        with tmp.open('w', encoding='utf-8') as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, receipt_path)
    try:
        require(not receipt_path.exists() and not claim_path.exists(),
                'EXISTING_RECEIPT_DO_NOT_REPEAT_UPLOAD')
        check_boundary(os.environ)
        media, preflight = verify_local(root)
        receipt['source_commit'] = os.environ['GITHUB_SHA']
        receipt['local_input'] = {k: preflight[k] for k in ('sha256', 'size_bytes', 'duration_seconds', 'mime_type', 'manifest_sha256')}
        # Exclusive claim survives a crash/timeout; another process cannot reupload.
        with claim_path.open('x', encoding='utf-8') as claim:
            json.dump({'source_commit': receipt['source_commit'],
                       'sha256': preflight['sha256'], 'started_at': receipt['started_at']}, claim)
            claim.flush(); os.fsync(claim.fileno())
        own_claim = True
        # No key read or credential setup before all local guards succeed.
        key = os.environ.get('HERO_GEMINI_API_KEY', '')
        deliver(media, preflight, api_key=key, receipt=receipt, checkpoint=checkpoint)
        receipt['finished_at'] = utcnow()
        checkpoint(receipt)
        print('PASS_FILES_DELIVERY_ONLY: ACTIVE and hash/bytes/MIME/duration verified; no inference.')
        return 0
    except Exception as error:
        receipt['status'] = 'FAILED_NO_AUTOMATIC_RETRY'
        receipt['failure_code'] = error.code if isinstance(error, ProviderFailure) else 'LOCAL_OR_CHECKPOINT_ERROR'
        receipt['finished_at'] = utcnow()
        # Do not overwrite a pre-existing receipt from another invocation.
        if root.is_dir() and (own_claim or (not receipt_path.exists() and not claim_path.exists())):
            checkpoint(receipt)
        print('FILES_DELIVERY_PROOF_FAILED: ' + receipt['failure_code'])
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
