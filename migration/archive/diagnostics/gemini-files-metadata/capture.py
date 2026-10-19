#!/usr/bin/env python3
"""Capture one existing File's metadata. No upload, reconciliation or inference."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime_bridge'))
from gemini_public_av import ProviderFailure

FILE_NAME = 'files/qe6pn3aifbkw'
URL = 'https://generativelanguage.googleapis.com/v1beta/' + FILE_NAME
PRIOR_SHA256 = 'ef6c73a3c91884e3d28dd37135b7f160c7937fa069ca4e9e0f02ddbd935974b4'
PRIOR = Path(__file__).resolve().parents[2] / 'evidence/gemini-files-delivery-38834915350/receipt.json'
OUTPUT = Path('gemini-files-metadata-output')
MAX_RESPONSE = 16384


def require(ok, code):
    if not ok:
        raise ProviderFailure(code)


def boundary(env):
    expected = {
        'GITHUB_REPOSITORY': 'matheusmagah-cpu/heroverse-engine',
        'HERO_REPOSITORY_PRIVATE': 'true', 'GITHUB_REF': 'refs/heads/main',
        'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_RUN_NUMBER': '1',
        'GITHUB_RUN_ATTEMPT': '1',
        'GITHUB_WORKFLOW_REF': 'matheusmagah-cpu/heroverse-engine/.github/workflows/gemini-files-metadata-once.yml@refs/heads/main',
    }
    require(all(env.get(k) == v for k, v in expected.items()), 'PRIVATE_MAIN_FIRST_MANUAL_RUN_REQUIRED')
    require(re.fullmatch(r'[a-f0-9]{40}', env.get('GITHUB_SHA', '')) is not None, 'COMMIT_SHA_REQUIRED')


def verify_prior():
    raw = PRIOR.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == PRIOR_SHA256, 'PRIOR_RECEIPT_BINDING_FAILED')
    return json.loads(raw)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get_metadata(api_key):
    """Exactly one GET, fixed URL and empty body; no proxy, redirect or retry."""
    request = urllib.request.Request(URL, method='GET', data=None,
                                     headers={'x-goog-api-key': api_key})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            require(response.status == 200, 'UNEXPECTED_HTTP_STATUS')
            raw = response.read(MAX_RESPONSE + 1)
            require(len(raw) <= MAX_RESPONSE, 'RESPONSE_SIZE_LIMIT')
        return json.loads(raw)
    except ProviderFailure:
        raise
    except urllib.error.HTTPError as error:
        raise ProviderFailure('HTTP_' + str(error.code)) from None
    except Exception:
        raise ProviderFailure('NETWORK_OR_RESPONSE_FAILED_NO_RETRY') from None


def project_metadata(meta, api_key):
    """Whitelist data fields only. Preserve sha256Hash verbatim, without decoding."""
    require(type(meta) is dict and meta.get('name') == FILE_NAME, 'FILE_IDENTITY_MISMATCH')
    patterns = {
        'state': r'(?:STATE_UNSPECIFIED|PROCESSING|ACTIVE|FAILED)',
        'mimeType': r'[a-zA-Z0-9.+-]{1,60}/[a-zA-Z0-9.+-]{1,60}',
        'sizeBytes': r'[0-9]{1,20}',
        'sha256Hash': r'[A-Za-z0-9+/=_-]{1,256}',
        'createTime': r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]{8,20}(?:Z|[+-][0-9]{2}:[0-9]{2})',
        'expirationTime': r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]{8,20}(?:Z|[+-][0-9]{2}:[0-9]{2})',
    }
    result = {'name': FILE_NAME}
    for key, pattern in patterns.items():
        value = meta.get(key)
        require(value is None or (type(value) is str and re.fullmatch(pattern, value)),
                'METADATA_FIELD_SHAPE_REJECTED')
        result[key] = value
    video = meta.get('videoMetadata')
    require(video is None or type(video) is dict, 'VIDEO_METADATA_SHAPE_REJECTED')
    duration = None if video is None else video.get('videoDuration')
    require(duration is None or (type(duration) is str and
            re.fullmatch(r'[0-9]{1,10}(?:\.[0-9]{1,9})?s', duration)), 'DURATION_SHAPE_REJECTED')
    result['videoMetadata'] = {'videoDuration': duration}
    require(api_key not in json.dumps(result), 'CREDENTIAL_ECHO_REJECTED')
    return result


def main():
    receipt_path = OUTPUT / 'receipt.json'
    claim_path = OUTPUT / 'attempt-claim.json'
    own_claim = False
    receipt = {'schema': 'heroverse-files-metadata-capture-v1',
               'started_at': datetime.now(timezone.utc).isoformat(),
               'file_resource_name': FILE_NAME, 'metadata_get_calls': 0,
               'upload_start_calls': 0, 'bytes_upload_calls': 0,
               'generate_content_calls': 0, 'count_tokens_calls': 0,
               'delete_calls': 0, 'billing_changes': 0, 'automatic_retry': False,
               'delivery_verdict': 'BLOCKED_PENDING_HASH_RECONCILIATION',
               'model_understanding': 'NOT_TESTED', 'project_identity': 'NOT_IDENTIFIED',
               'billing_tier': 'NOT_IDENTIFIED'}
    def checkpoint():
        temp = receipt_path.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, receipt_path)
    def deadline(_signum, _frame):
        raise ProviderFailure('METADATA_GET_DEADLINE')
    try:
        require(len(sys.argv) == 1, 'NO_ARGUMENTS_ACCEPTED')
        require(not receipt_path.exists() and not claim_path.exists(), 'EXISTING_CAPTURE_DO_NOT_REPEAT')
        boundary(os.environ)
        prior = verify_prior()
        receipt['prior_receipt_sha256'] = PRIOR_SHA256
        receipt['local_input'] = prior['local_input']
        receipt['source_commit'] = os.environ['GITHUB_SHA']
        OUTPUT.mkdir(exist_ok=True)
        with claim_path.open('x', encoding='utf-8') as handle:
            json.dump({'file_resource_name': FILE_NAME, 'source_commit': receipt['source_commit']}, handle)
            handle.flush(); os.fsync(handle.fileno())
        own_claim = True
        # Key is read only after all local guards and the immutable prior binding.
        key = os.environ.get('HERO_GEMINI_API_KEY', '')
        require(type(key) is str and 20 <= len(key) <= 256 and key.isascii()
                and not any(c.isspace() for c in key), 'SECRET_MISSING_OR_MALFORMED')
        receipt['metadata_get_calls'] = 1
        receipt['status'] = 'METADATA_GET_REQUESTED'
        checkpoint()
        previous = signal.signal(signal.SIGALRM, deadline)
        signal.setitimer(signal.ITIMER_REAL, 25)
        try:
            meta = get_metadata(key)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        receipt['raw_file_metadata'] = project_metadata(meta, key)
        receipt['status'] = 'METADATA_CAPTURED_NOT_RECONCILED'
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        checkpoint()
        print('METADATA_CAPTURED_NOT_RECONCILED: one existing File; see private receipt.')
        return 0
    except Exception as error:
        receipt['status'] = 'FAILED_NO_AUTOMATIC_RETRY'
        receipt['failure_code'] = error.code if isinstance(error, ProviderFailure) else 'LOCAL_OR_CHECKPOINT_ERROR'
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        if own_claim:
            try:
                checkpoint()
            except Exception:
                receipt['failure_code'] = 'CHECKPOINT_FAILED_NO_RETRY'
        print('METADATA_CAPTURE_FAILED: ' + receipt['failure_code'])
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
