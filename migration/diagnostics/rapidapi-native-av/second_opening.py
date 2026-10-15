"""One new opening via the proven route; offline until billing admission exists."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
import native_probe as n
from next_window import artifact_preflight, require

REQUEST_ID = '20261015-rapidapi-native-BeFOHnncaeQ-0-40-v1'
SOURCE = 'BeFOHnncaeQ'
REPO = 'matheusmagah-cpu/heroverse-engine'
EVIDENCE = Path('migration/evidence/cloud-video-player-20261015')
PARAMS = dict(n.PARAMS, url='https://www.youtube.com/watch?v=' + SOURCE)
MAX_CONTROL_REQUESTS = 40
MAX_CONTROL_RESPONSE_BYTES = 1024 * 1024
RESERVATION = dict(reserved_transfer_bytes=80 * 1024**2,
    reserved_runner_minutes=10, reserved_units=14, reserved_requests=40)


def admit(plan, ledger, billing, now):
    require(plan['request_id'] == REQUEST_ID and plan['status'] == 'PLANNED_NOT_ADMITTED', 'EXACT_PLAN_REQUIRED')
    require(plan['parameters'] == PARAMS and plan['reservation'] == RESERVATION, 'PLAN_OR_RESERVATION_CHANGED')
    require(ledger['version'] == 'native-av-reservations-v1', 'LEDGER_VERSION_CHANGED')
    claims = ledger['claims']
    require(len({x['request_id'] for x in claims}) == len(claims), 'DUPLICATE_EXISTING_CLAIM')
    require(all(x['request_id'] != REQUEST_ID for x in claims), 'PRIOR_CLAIM_EXISTS_NO_RESTART')
    require(all(all(x[k] >= v for k, v in RESERVATION.items()) for x in claims), 'PRIOR_RESERVATION_REDUCED')
    today = now.date().isoformat()
    today_claims = [x for x in claims if x['day_utc'] == today]
    require(len(today_claims) + 1 <= 3, 'DAILY_JOB_CAP')
    require(sum(x['reserved_units'] for x in today_claims) + 14 <= 450, 'DAILY_UNIT_CAP')
    require(sum(x['reserved_transfer_bytes'] for x in claims) + RESERVATION['reserved_transfer_bytes'] <= 8_000_000_000, 'MONTHLY_TRANSFER_CAP')
    require(sum(x['reserved_runner_minutes'] for x in claims) + ledger.get('qualification_recovery_extra_runner_minutes_reserved', 0) + 10 <= 1100, 'MONTHLY_RUNNER_CAP')
    require(sum(x['reserved_requests'] for x in claims) + 40 <= 100000, 'MONTHLY_REQUEST_CAP')
    require(ledger['production'] is False and ledger['publication'] is False, 'AUTHORITY_BOUNDARY_CHANGED')
    require(billing['request_id'] == REQUEST_ID and billing['status'] == 'VERIFIED_FOR_ONE_SHOT', 'BILLING_NOT_VERIFIED')
    age = (now - dt.datetime.fromisoformat(billing['observed_at'].replace('Z', '+00:00'))).total_seconds()
    require(0 <= age <= 3600, 'BILLING_OBSERVATION_EXPIRED')
    require(billing['rapidapi_subscription_active_basic_zero_usd'] is True, 'FREE_BASIC_REQUIRED')
    require(billing['rapidapi_bandwidth_display'] == '0.00%', 'BANDWIDTH_HEADROOM_RECONCILIATION_REQUIRED')
    require(billing['bandwidth_headroom_basis'] == 'PRACTICAL_DISPLAY_INFERENCE_NOT_HARD_STOP_PROOF', 'HEADROOM_BASIS_REQUIRED')
    require(billing['github_zero_additional_spend_confirmed'] is True, 'GITHUB_ZERO_COST_NOT_VERIFIED')
    require(billing['github_included_runner_minutes_remaining'] >= 10, 'GITHUB_RUNNER_HEADROOM_REQUIRED')
    require(billing['github_actions_budget_usd'] == 0 and billing['github_actions_budget_status'] == 'Usage blocked', 'GITHUB_ZERO_SPEND_STOP_REQUIRED')
    require(billing['github_storage_display'] == '0 GB / 0.5 GB', 'GITHUB_STORAGE_OBSERVATION_REQUIRED')
    require(billing['new_payment_or_plan_change'] is False, 'NEW_PAYMENT_OR_PLAN_REFUSED')
    return dict(RESERVATION, request_id=REQUEST_ID, status='RESERVED_BEFORE_EFFECT',
                reserved_at=now.isoformat(), day_utc=today)


class CountedOpener:
    """Count all gateway attempts, including initialize and notifications."""
    def __init__(self, inner, evidence):
        self.inner, self.evidence = inner, evidence

    def open(self, request, *args, **kwargs):
        host = urlsplit(request.full_url).hostname
        if host in ('mcp.rapidapi.com', n.HOST):
            count = self.evidence.get('gateway_request_attempts', 0)
            require(count < MAX_CONTROL_REQUESTS, 'CONTROL_REQUEST_CAP')
            # Bounded outgoing JSON/query/headers; values are never logged.
            size = len(request.full_url.encode()) + len(request.data or b'')
            size += sum(len(k.encode()) + len(v.encode()) + 4 for k, v in request.header_items())
            require(size <= 32768, 'OUTGOING_CONTROL_CAP')
            self.evidence['gateway_request_attempts'] = count + 1
        return self.inner.open(request, *args, **kwargs)


def fresh_quota(q):
    require(q.get('x-ratelimit-units-limit') == '500', 'UNIT_PLAN_CHANGED')
    require(14 <= int(q.get('x-ratelimit-units-remaining', '-1')) <= 500, 'INCLUDED_UNIT_HEADROOM_REQUIRED')
    for prefix in ('x-ratelimit-requests', 'x-ratelimit-rapid-free-plans-hard-limit'):
        require(q.get(prefix + '-limit') == '500000', 'REQUEST_PLAN_CHANGED')
        require(40 <= int(q.get(prefix + '-remaining', '-1')) <= 500000, 'INCLUDED_REQUEST_HEADROOM_REQUIRED')


def run(out, e, key):
    require(os.environ.get('GITHUB_REPOSITORY') == REPO, 'REPOSITORY_MISMATCH')
    require(os.environ.get('GITHUB_RUN_NUMBER') == '1' and os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'REPEAT_RUN_REFUSED')
    require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and os.environ.get('GITHUB_REF') == 'refs/heads/main', 'MANUAL_MAIN_ONLY')
    require(bool(key), 'KEY_MISSING')
    plan = json.loads((EVIDENCE / 'second-opening-plan.json').read_text())
    ledger = json.loads((EVIDENCE / 'native-av-reservations.json').read_text())
    # Parent-verified browser billing observation must remain fresh before
    # dispatch. It contains no credential material.
    billing = json.loads((EVIDENCE / 'second-opening-billing-admission.json').read_text())
    reservation = admit(plan, ledger, billing, dt.datetime.now(dt.timezone.utc))
    n.command(['ffmpeg', '-v', 'error', '-version'])
    e['storage_preflight'] = artifact_preflight(key, out)
    # Enforce private repository: artifacts must never become public media.
    from urllib.request import Request, build_opener
    token = os.environ['GH_ARTIFACT_TOKEN']
    req = Request('https://api.github.com/repos/' + REPO,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json'})
    with build_opener(n.NoRedirect()).open(req, timeout=15) as response:
        raw = response.read(MAX_CONTROL_RESPONSE_BYTES + 1)
        require(len(raw) <= MAX_CONTROL_RESPONSE_BYTES, 'REPOSITORY_METADATA_CAP')
        require(json.loads(raw)['private'] is True, 'PRIVATE_REPOSITORY_REQUIRED')
    prior = json.loads((EVIDENCE / 'rapidapi-native-first-result.json').read_text())
    require(prior['complete_clip_decode_passed'] is True, 'PRIOR_SUCCESS_REQUIRED')
    e['baseline_quota_headers'] = prior['last_quota_headers']
    original_opener = n.build_opener
    n.build_opener = lambda *a, **kw: CountedOpener(original_opener(*a, **kw), e)
    # Only inspect the successful opening for current counters; never poll or
    # restart the terminal midpoint. Fresh values need not equal old counters.
    previous = n.progress(prior['provider_job_id'], key, e, out, 99)
    require(previous.get('success') == 1 and previous.get('progress') == 1000, 'PRIOR_JOB_NOT_COMPLETE')
    fresh_quota(e['last_quota_headers'])
    e['baseline_quota_headers'] = e['last_quota_headers']
    e['quota_baseline_observed_at'] = n.utc_now()
    e['reservation'] = reservation
    n.private_json(out / 'reservation.json', reservation, key)
    n.private_json(out / 'receipt.json', e, key)
    n.PARAMS = PARAMS.copy()
    n.REQUEST_ID = REQUEST_ID
    client = n.Client(key, opener=n.build_opener(n.NoRedirect()))
    client.send('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
        'clientInfo': {'name': 'heroverse-second-opening-once', 'version': '1'}})
    client.send('notifications/initialized')
    value = n.start_download(client, n.OneStart(), e, out)
    job = value.get('id')
    require(isinstance(job, str) and n.re.fullmatch(r'[a-zA-Z0-9_-]{1,160}', job) and key not in job, 'NO_SAFE_RESUMABLE_JOB_ID')
    e.update(provider_job_id=job, effect_status='JOB_ID_RECEIVED_NO_RESTART_ALLOWED')
    n.private_json(out / 'receipt.json', e, key)
    n.private_json(out / 'job.json', {'request_id': REQUEST_ID, 'provider_job_id': job, 'parameters': PARAMS}, key)
    print('HEROVERSE_SECOND_OPENING_JOB_SAVED=' + json.dumps({'request_id': REQUEST_ID, 'provider_job_id': job}), flush=True)
    deadline = time.monotonic() + 270
    for index in range(n.MAX_POLLS):
        require(time.monotonic() <= deadline, 'PENDING_STOP_NO_AUTOMATIC_RECOVERY')
        if index:
            time.sleep(10)
        value = n.progress(job, key, e, out, index)
        url = n.ready_delivery_url(value)
        if url:
            host = urlsplit(url).hostname or ''
            require(host == 'savenow.to' or host.endswith('.savenow.to'), 'UNEXPECTED_DELIVERY_HOST_STOP')
            e['delivery_url_sha256'] = hashlib.sha256(url.encode()).hexdigest()
            n.fetch_media(url, out, e)
            n.inspect_media(out, e)
            audios = [s for s in e['native_probe']['streams'] if s.get('codec_type') == 'audio']
            require(len(audios) == 1, 'EXACTLY_ONE_AUDIO_REQUIRED')
            require(sum(p.stat().st_size for p in out.iterdir() if p.is_file()) < 96 * 1024**2, 'OUTPUT_STORAGE_CAP')
            e['source_clock_mapping'] = [{'local_seconds': t, 'source_seconds': t,
                'file': 'frame-%02d.jpg' % t,
                'sha256': hashlib.sha256((out / ('frame-%02d.jpg' % t)).read_bytes()).hexdigest()} for t in (0, 10, 20, 30, 39)]
            e['status'] = 'NATIVE_OPENING_DECODED_AWAITING_REVIEW'
            return
    raise n.ProbeError('PENDING_STOP_NO_AUTOMATIC_RECOVERY')


def main():
    out = Path('output/qualification/rapidapi-native-BeFOHnncaeQ-0-40-v1')
    # Existing output is an uncertain previous effect, never overwrite it.
    out.mkdir(parents=True, exist_ok=False)
    os.chmod(out, 0o700)
    key = os.environ.get('HERO_RAPIDAPI_KEY', '')
    e = dict(version='second-native-opening-v1', request_id=REQUEST_ID,
        source_video_id=SOURCE, source_requested_seconds=[0, 40],
        started_at=n.utc_now(), status='BLOCKED', effect_status='NOT_SENT',
        download_tools_call_requests=0, progress_polls=0, gateway_request_attempts=0,
        control_response_bytes=0, production=False, publication=False, supervisor=False,
        recurring_capacity_qualified=False, perceptual_audio_review_completed=False)
    started = time.monotonic()
    try:
        run(out, e, key)
    except Exception as error:
        e['status'] = 'BLOCKED'
        e['failure_code'] = str(error) if isinstance(error, n.ProbeError) else type(error).__name__
    e['elapsed_seconds'] = round(time.monotonic() - started, 3)
    e['completed_at'] = n.utc_now()
    e['restart_allowed'] = False
    n.private_json(out / 'receipt.json', e, key)
    # Only allowlisted receipt fields; never raw exceptions, key, URL or bodies.
    public = {k: e[k] for k in ('request_id', 'status', 'effect_status',
        'download_tools_call_requests', 'gateway_request_attempts', 'elapsed_seconds', 'restart_allowed')}
    if 'failure_code' in e:
        public['failure_code'] = e['failure_code']
    print('HEROVERSE_SECOND_OPENING_RECEIPT=' + json.dumps(public), flush=True)
    return 0 if e['status'] == 'NATIVE_OPENING_DECODED_AWAITING_REVIEW' else 2


if __name__ == '__main__':
    raise SystemExit(main())
