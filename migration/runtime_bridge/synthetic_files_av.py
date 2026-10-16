"""One synthetic c01 Files inference in the original observer's ledger.

Not a public-source admission path, scheduler, adjudicator, or upload client.
Only the neutral frozen prompt and the already-uploaded File reach the provider.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import sys
import urllib.request
import urllib.error

from gemini_public_av import canonical, digest, ProviderFailure, transport, validate_free_policy
from observe_public_av import ExistingObserverLedger
from durable_evidence_checkpoint import CLAIM, SQL

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'migration/diagnostics/gemini-files-delivery'))
from probe import decode_remote_sha256

MODEL = 'gemini-3.8-flash'
FILE_NAME = 'files/qe6pn3aifbkw'
FILE_URL = 'https://generativelanguage.googleapis.com/v1beta/' + FILE_NAME
CONTENT_SHA256 = '5562d675416107eb9ec70643edd43e5375b85aa74051730f1d357a88d34e79df'
PROMPT_SHA256 = '44c9397dc7abb05e2b614b3ec9b2e56ca374e3df704a7426a14ef5cd07ace486'
CAPTURE_SHA256 = 'c6e9e810f0d1f82d8517678d45ef2e0ac2c4c589ae709836fee340b64b34a986'
HISTORICAL_KEY_SHA256 = 'dce7edfa7f6515d6da7a53331ea7cfc31b5ad94cc2bfb3cafce3f0f1e08bc811'
EXPIRATION = '2026-10-18T01:24:40.549171836Z'
CAPTURE = Path('migration/diagnostics/gemini-files-delivery/fixtures/metadata-capture-38836054574.json')
POLICY = Path('migration/evidence/gemini-free-runtime-policy.json')
PROMPT = Path('migration/evidence/av-evaluator-controls-20261016/evaluator-prompt.txt')
DB = Path('cloud-evidence/quota-ledger.sqlite3')
GENERATION_CONFIG = {'candidateCount': 1, 'maxOutputTokens': 4096}
VIDEO_METADATA = {'startOffset': '0s', 'endOffset': '6s', 'fps': 10}
SOURCE = {'kind': 'SYNTHETIC_CONTROL', 'content_sha256': CONTENT_SHA256,
          'duration_seconds': 6, 'mime_type': 'video/mp4', 'size_bytes': 19083}
FALSE_AUTHORITY = {'quality_authorized': False, 'production_authorized': False,
                   'publication_authorized': False}
OCT14_ROWS_SHA256 = 'd53c182f245c49952c6e98fe06dc9a923612783546708ca4e4d0d5badc8c4008'
OWNER_REQUEST = 'Sentinel_0212eae8ba548191890633bc89023ab1'
DEADLINE_SECONDS = 110


def require(ok, code):
    if not ok:
        raise PermissionError(code)


def utcnow():
    return datetime.now(timezone.utc)


@contextmanager
def wall_deadline(seconds):
    def expired(_signum, _frame):
        raise ProviderFailure('SYNTHETIC_CONTROL_DEADLINE_NO_RETRY')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def validate_boundary(env):
    expected = {'GITHUB_REPOSITORY': 'matheusmagah-cpu/heroverse-engine',
        'HERO_REPOSITORY_PRIVATE': 'true', 'GITHUB_REF': 'refs/heads/main',
        'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_RUN_ATTEMPT': '1',
        'GITHUB_WORKFLOW_REF': 'matheusmagah-cpu/heroverse-engine/.github/workflows/official-evidence.yml@refs/heads/main'}
    require(all(env.get(k) == v for k,v in expected.items()), 'PRIVATE_FIRST_ATTEMPT_MANUAL_MAIN_REQUIRED')
    require(re.fullmatch(r'[a-f0-9]{40}', env.get('GITHUB_SHA','')) is not None
            and re.fullmatch(r'[0-9]+', env.get('GITHUB_RUN_ID','')) is not None, 'EXACT_RUN_IDENTITY_REQUIRED')
    stages = json.loads(env.get('HERO_STAGE_SELECTION', '{}'))
    require(stages.get('checkpoint_only') is True and stages.get('av_synthetic_c01') is True
            and all(v is False for k,v in stages.items() if k not in ('checkpoint_only','av_synthetic_c01')),
            'SYNTHETIC_ONLY_CHECKPOINT_STAGE_REQUIRED')


def validate_policy(api_key, policy, now):
    # The shared original guard runs before a reservation or a metadata GET.
    model = validate_free_policy(api_key, policy, now)
    require(model == MODEL and policy.get('automatic_paid_fallback') is False
            and policy.get('expires_after_hours') == 24
            and policy.get('key_sha256') == HISTORICAL_KEY_SHA256
            and policy.get('runtime_key_match_required_before_remote_effect') is True,
            'EXACT_SYNTHETIC_FREE_POLICY_REQUIRED')
    return model


def validate_prompt(prompt):
    require(type(prompt) is bytes and hashlib.sha256(prompt).hexdigest() == PROMPT_SHA256,
            'EXACT_NEUTRAL_PROMPT_REQUIRED')
    return prompt.decode('utf-8')


def validate_metadata(meta, now, *, require_uri=True):
    require(type(meta) is dict and meta.get('name') == FILE_NAME, 'EXACT_EXISTING_FILE_REQUIRED')
    require(meta.get('state') == 'ACTIVE' and meta.get('mimeType') == 'video/mp4'
            and meta.get('sizeBytes') == '19083'
            and meta.get('videoMetadata') == {'videoDuration': '6s'}, 'EXACT_ACTIVE_C01_METADATA_REQUIRED')
    actual, representation = decode_remote_sha256(meta.get('sha256Hash'))
    require(actual == CONTENT_SHA256, 'EXACT_C01_HASH_REQUIRED')
    require(meta.get('expirationTime') == EXPIRATION, 'EXACT_EXPIRATION_REQUIRED')
    expires = datetime.fromisoformat(EXPIRATION.replace('Z','+00:00'))
    require(now.tzinfo is not None and (expires-now).total_seconds() > DEADLINE_SECONDS+10,
            'FILE_EXPIRED_OR_TOO_CLOSE_TO_EXPIRY')
    if require_uri:
        # Compare a provider-returned URI; never present a constructed URI as observed.
        require(meta.get('uri') == FILE_URL, 'PROVIDER_RETURNED_EXACT_FILE_URI_REQUIRED')
    return {'source': dict(SOURCE), 'hash_representation': representation,
            'expiration_time': EXPIRATION, 'metadata_checked_at': now.isoformat()}


def verify_inputs(policy, prompt, capture_raw, now):
    validate_prompt(prompt)
    require(hashlib.sha256(capture_raw).hexdigest() == CAPTURE_SHA256, 'SAVED_CAPTURE_BINDING_FAILED')
    capture = json.loads(capture_raw)
    require(capture['file_resource_name'] == FILE_NAME
            and capture['local_input']['sha256'] == CONTENT_SHA256
            and capture['generate_content_calls'] == 0, 'SAVED_DELIVERY_CAPTURE_REQUIRED')
    validate_metadata(capture['raw_file_metadata'], now, require_uri=False)
    evidence = policy.get('verification_evidence', {})
    require(evidence.get('path') == 'migration/evidence/gemini-project-policy-observation-20261016.json',
            'POLICY_EVIDENCE_PATH_REQUIRED')
    body = Path(evidence['path']).read_bytes()
    require(hashlib.sha256(body).hexdigest() == evidence.get('sha256'), 'POLICY_EVIDENCE_BINDING_FAILED')
    require(SQL.is_file(), 'EXISTING_LEDGER_MUST_NOT_BE_BOOTSTRAPPED')
    # Read-only in-memory reconstruction of the exact existing SQL, no new runtime ledger.
    with sqlite3.connect(':memory:') as c:
        c.executescript(SQL.read_text())
        require(c.execute('pragma integrity_check').fetchone()[0] == 'ok', 'EXISTING_LEDGER_INVALID')
        row = c.execute("SELECT count(*),sum(seconds),sum(state='CLAIMED') FROM public_av_reservations WHERE day='2026-10-14'").fetchone()
        require(row == (53,28800,0), 'PRESERVED_OCT14_HISTORY_REQUIRED')
        history = c.execute("SELECT * FROM public_av_reservations WHERE day='2026-10-14' ORDER BY key").fetchall()
        require(digest(history) == OCT14_ROWS_SHA256, 'HISTORICAL_AV_ROWS_CHANGED')
        require(c.execute("SELECT count(*) FROM public_av_reservations WHERE state='CLAIMED'").fetchone()[0] == 0,
                'UNRESOLVED_EXISTING_CLAIM_BLOCKED')


def request_identity(prompt, *, model=MODEL, content_sha256=CONTENT_SHA256,
                     video_metadata=None, generation_config=None):
    """Content identity excludes calendar time, run ID, policy age and File URI."""
    identity = {'version': 'synthetic-files-av-request-v1', 'kind': 'SYNTHETIC_CONTROL',
        'content_sha256': content_sha256, 'mime_type': 'video/mp4', 'duration_seconds': 6,
        'model': model, 'prompt_sha256': hashlib.sha256(prompt).hexdigest(),
        'media_processing': 'STATIC',
        'video_metadata': VIDEO_METADATA if video_metadata is None else video_metadata,
        'generation_config': GENERATION_CONFIG if generation_config is None else generation_config}
    request_hash = digest(identity)
    return 'synthetic-av:' + request_hash, request_hash, identity


def build_request(meta, prompt, now):
    validate_metadata(meta, now)
    text = validate_prompt(prompt)
    return {'contents': [{'role': 'user', 'parts': [
        {'fileData': {'fileUri': meta['uri'], 'mimeType': 'video/mp4'},
         'mediaProcessing': 'STATIC', 'videoMetadata': dict(VIDEO_METADATA)},
        {'text': text}]}], 'generationConfig': dict(GENERATION_CONFIG)}


def get_existing_metadata(api_key):
    """One GET of the existing resource; no upload, listing, redirect or retry."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    req = urllib.request.Request(FILE_URL, method='GET', data=None, headers={'x-goog-api-key': api_key})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=20) as r:
            if r.status != 200: raise ProviderFailure('METADATA_UNEXPECTED_HTTP_STATUS')
            raw = r.read(16385)
        if len(raw) > 16384: raise ProviderFailure('METADATA_RESPONSE_TOO_LARGE')
        return json.loads(raw)
    except ProviderFailure: raise
    except urllib.error.HTTPError as e:
        raise ProviderFailure('METADATA_HTTP_' + str(e.code)) from None
    except Exception:
        raise ProviderFailure('METADATA_FAILED_NO_RETRY') from None


def analyze_synthetic_file(meta, prompt, *, api_key, policy, reserve, persist,
                           send=transport, now=None, clock=utcnow):
    now = now or clock()
    validate_policy(api_key, policy, now)
    require(callable(reserve) and callable(persist), 'EXISTING_DURABLE_MANAGER_REQUIRED')
    payload = build_request(meta, prompt, now)
    key, request_hash, identity = request_identity(prompt)
    claim = reserve(key, request_hash, 6, 28800)
    require(claim.get('key') == key and claim.get('request_hash') == request_hash, 'MANAGER_CLAIM_BINDING_REQUIRED')
    if claim.get('status') == 'REPLAY':
        receipt = claim['receipt']
        require(receipt.get('key') == key and receipt.get('request_hash') == request_hash
                and receipt.get('source') == SOURCE and receipt.get('request_identity') == identity
                and receipt.get('review_status') == 'NOT_REVIEWED'
                and all(receipt.get(k) is False for k in FALSE_AUTHORITY), 'MANAGER_REPLAY_BINDING_REQUIRED')
        return receipt
    require(claim.get('status') == 'NEW' and claim.get('durable') is True,
            'AV_QUOTA_OR_UNRESOLVED_CLAIM_BLOCKED')
    receipt = {'version': 'heroverse-synthetic-files-av-v1', 'key': key, 'request_hash': request_hash,
        'request_identity': identity, 'wire_payload_sha256': digest(payload),
        'source': dict(SOURCE), 'model': MODEL, 'file_resource_name': FILE_NAME,
        'file_uri_observed': meta['uri'], 'file_expiration_time': EXPIRATION,
        'sample_fps': 10, 'media_processing': 'STATIC', 'full_interval_seconds': [0,6],
        'local_budget_seconds': 6, 'local_budget_cap_seconds': 28800,
        'local_budget_timezone': 'UTC', 'google_rpd_reset_timezone': 'America/Los_Angeles',
        'local_budget_basis': 'REQUESTED_INTERVAL_NOT_PROVIDER_QUOTA_ASSERTION',
        'review_status': 'NOT_REVIEWED', 'evidence_class': 'MODEL_OUTPUT_NOT_INDEPENDENTLY_VERIFIED',
        'precision_verdict': 'NOT_ADJUDICATED', 'automatic_retry': False,
        'generate_content_calls': 0, 'upload_calls': 0, 'count_tokens_calls': 0,
        'delete_calls': 0, 'owner_request_message_id': OWNER_REQUEST,
        'key_binding': {'status': 'MATCH', 'checked_at': now.isoformat()},
        **FALSE_AUTHORITY}
    try:
        # Reservation checkpoint latency must not make freshness or expiry stale.
        send_time = clock()
        validate_policy(api_key, policy, send_time)
        validate_metadata(meta, send_time)
        receipt['generate_content_calls'] = 1
        with wall_deadline(DEADLINE_SECONDS):
            response = send(payload, api_key, model=MODEL)
        require(type(response) is dict, 'PROVIDER_RESPONSE_SHAPE_REJECTED')
        raw = canonical(response)
        require(api_key not in raw.decode('utf-8'), 'CREDENTIAL_ECHO_REJECTED')
        receipt['response_sha256'] = hashlib.sha256(raw).hexdigest()
        receipt['provider_response'] = response
        candidates = response.get('candidates', [])
        receipt['finish_reasons'] = [c.get('finishReason') for c in candidates]
        require(len(candidates) == 1 and candidates[0].get('finishReason') == 'STOP', 'PROVIDER_BLOCKED_OR_TRUNCATED')
        parts = candidates[0].get('content', {}).get('parts', [])
        require(all(not any(k in p for k in ('toolCall','toolResponse','functionCall','executableCode')) for p in parts),
                'UNEXPECTED_AGENTIC_OR_TOOL_OUTPUT')
        output = ''.join(p.get('text','') for p in parts if not p.get('thought',False))
        require(output.strip() != '', 'EMPTY_EVALUATOR_RESPONSE')
        receipt.update(status='SYNTHETIC_RESPONSE_AWAITING_REVIEW', evaluator_response=output)
    except Exception as error:
        receipt.update(status='FAILED_NO_AUTOMATIC_RETRY',
            failure_code=error.code if isinstance(error,ProviderFailure) else
                str(error) if isinstance(error,PermissionError) and re.fullmatch(r'[A-Z0-9_]+',str(error))
                else 'SYNTHETIC_RESPONSE_OR_LOCAL_FAILURE')
    receipt['finished_at'] = clock().isoformat()
    # A failed commit propagates, leaving the durable claim unresolved. Never resend.
    persist(receipt)
    return receipt


def prepare_runtime(*, now=None):
    validate_boundary(os.environ)
    now = now or utcnow()
    policy = json.loads(POLICY.read_text())
    prompt = PROMPT.read_bytes()
    verify_inputs(policy, prompt, CAPTURE.read_bytes(), now)
    api_key = os.environ.get('HERO_GEMINI_API_KEY','')
    validate_policy(api_key, policy, now)
    return policy, prompt, api_key


def safe_failure_code(error):
    code = error.code if isinstance(error,ProviderFailure) else str(error)
    return code if re.fullmatch(r'[A-Z0-9_:,]+',code) else 'LOCAL_OR_CHECKPOINT_FAILURE'


def save_local_preflight_failure(error):
    # This folder is created early only on failure; the restore step is then skipped.
    # The workflow's existing always-upload step preserves the diagnostic artifact.
    receipt = {'schema':'heroverse-synthetic-preflight-failure-v1',
        'status':'FAILED_BEFORE_RESERVATION_NO_AUTOMATIC_RETRY',
        'failure_code':safe_failure_code(error), 'metadata_get_calls':0,
        'generate_content_calls':0, 'upload_calls':0, 'automatic_retry':False,
        'run_id':os.environ.get('GITHUB_RUN_ID'), 'review_status':'NOT_REVIEWED', **FALSE_AUTHORITY}
    out = Path('cloud-evidence/synthetic-c01-preflight-failure.json')
    out.parent.mkdir(exist_ok=True)
    with out.open('x') as f:json.dump(receipt,f,sort_keys=True,allow_nan=False)
    return receipt


def preflight():
    try:
        prepare_runtime()
    except Exception as error:
        print(json.dumps(save_local_preflight_failure(error)))
        return 2
    print(json.dumps({'status':'SYNTHETIC_PREFLIGHT_PASSED','key_binding':'MATCH',
        'provider_calls':0, 'review_status':'NOT_REVIEWED', **FALSE_AUTHORITY}))
    return 0


def run_control(*, metadata_get=get_existing_metadata, send=transport):
    try:
        policy, prompt, api_key = prepare_runtime()
    except Exception as error:
        print(json.dumps(save_local_preflight_failure(error)))
        return 2
    ledger = ExistingObserverLedger(DB, os.environ['GITHUB_RUN_ID'])
    # Terminal replay can be returned locally, without repeating even the metadata GET.
    key, request_hash, identity = request_identity(prompt)
    with sqlite3.connect(DB) as c:
        row = c.execute('SELECT request_hash,state FROM public_av_reservations WHERE key=?',(key,)).fetchone()
    if row:
        require(row == (request_hash,'COMPLETED'), 'EXISTING_SYNTHETIC_CLAIM_BLOCKED')
        claim = ledger.reserve(key, request_hash, 6, 28800)
        receipt = claim.get('receipt',{})
        require(claim.get('status') == 'REPLAY' and receipt.get('request_identity') == identity
                and receipt.get('source') == SOURCE and receipt.get('review_status') == 'NOT_REVIEWED'
                and all(receipt.get(k) is False for k in FALSE_AUTHORITY), 'MANAGER_REPLAY_BINDING_REQUIRED')
    else:
        preflight_path = Path('migration/evidence')/('synthetic-c01-preflight-'+os.environ['GITHUB_RUN_ID']+'.json')
        observation = {'schema':'heroverse-synthetic-c01-preflight-v1',
            'status':'METADATA_GET_REQUESTED', 'file_resource_name':FILE_NAME,
            'metadata_get_calls':1, 'generate_content_calls':0, 'upload_calls':0,
            'automatic_retry':False, 'review_status':'NOT_REVIEWED',
            'key_binding':{'status':'MATCH','checked_at':utcnow().isoformat(),'run_id':os.environ['GITHUB_RUN_ID']},
            **FALSE_AUTHORITY}
        with preflight_path.open('x') as f:json.dump(observation,f,sort_keys=True,allow_nan=False)
        ledger.checkpoint('Checkpoint same-file metadata attempt before the single GET')
        try:
            with wall_deadline(25):
                meta = metadata_get(api_key)
            observation.update(validate_metadata(meta,utcnow()),status='METADATA_VERIFIED',
                provider_returned_uri=meta['uri'],wire_payload_sha256=digest(build_request(meta,prompt,utcnow())))
        except Exception as error:
            observation.update(status='FAILED_BEFORE_RESERVATION_NO_AUTOMATIC_RETRY',
                failure_code=safe_failure_code(error))
            with preflight_path.open('w') as f:json.dump(observation,f,sort_keys=True,allow_nan=False)
            ledger.checkpoint('Preserve terminal metadata failure without an inference reservation')
            print(json.dumps({'status':observation['status'],'failure_code':observation['failure_code'],**FALSE_AUTHORITY}))
            return 2
        with preflight_path.open('w') as f:json.dump(observation,f,sort_keys=True,allow_nan=False)
        ledger.checkpoint('Preserve same-file preflight without inference or new upload')
        receipt = analyze_synthetic_file(meta,prompt,api_key=api_key,policy=policy,
                    reserve=ledger.reserve,persist=ledger.persist,send=send,clock=utcnow)
    print(json.dumps({'status':receipt['status'],'review_status':'NOT_REVIEWED',
        'generate_content_calls_in_receipt':receipt['generate_content_calls'], **FALSE_AUTHORITY}))
    return 0 if receipt['status'] == 'SYNTHETIC_RESPONSE_AWAITING_REVIEW' else 2


def finalize_control():
    """Close this observer invocation only after its existing ledger is reconciled."""
    validate_boundary(os.environ)
    run = os.environ['GITHUB_RUN_ID']
    ledger = ExistingObserverLedger(DB, run)
    with sqlite3.connect(DB) as c:
        require(c.execute("SELECT count(*) FROM public_av_reservations WHERE state='CLAIMED'").fetchone()[0] == 0,
                'UNRESOLVED_AV_CLAIM_KEEP_OBSERVER_CLAIM')
    # Preserve a local preparation failure that occurred after the run claim.
    failure = Path('cloud-evidence/synthetic-c01-preflight-failure.json')
    if failure.is_file():
        saved = Path('migration/evidence')/('synthetic-c01-preflight-failure-'+run+'.json')
        with saved.open('xb') as f:f.write(failure.read_bytes())
    # No observer-state change, production queue write or cancelled recovery revival.
    CLAIM.unlink()
    ledger.checkpoint('Close bounded synthetic control with original observer ledger preserved')
    return 0


if __name__ == '__main__':
    try:
        require(len(sys.argv)==2 and sys.argv[1] in ('preflight','run','finalize'), 'EXPLICIT_CONTROL_MODE_REQUIRED')
        raise SystemExit({'preflight':preflight,'run':run_control,'finalize':finalize_control}[sys.argv[1]]())
    except Exception as error:
        safe_code = safe_failure_code(error)
        print(json.dumps({'status':'SYNTHETIC_CONTROL_BLOCKED','error_type':type(error).__name__,'failure_code':safe_code,
            'details_redacted':True, **FALSE_AUTHORITY}))
        raise SystemExit(2)
