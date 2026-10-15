"""One preclaimed midpoint; exact prior quota, no duplicate start or approval."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import Request, build_opener

import native_probe as n

REQUEST_ID = '20261015-rapidapi-native-j2rk8ycXe3c-6354-6364-v1'
WINDOW = [6354, 6364]
REPO = 'matheusmagah-cpu/heroverse-engine'
EVIDENCE = Path('migration/evidence/cloud-video-player-20261015')


def require(value, code):
    if not value:
        raise n.ProbeError(code)


def budget_preflight(ledger):
    require(ledger['version'] == 'native-av-reservations-v1', 'LEDGER_VERSION_CHANGED')
    claims = ledger['claims']
    require(all(x['reserved_transfer_bytes'] == 80 * 1024**2 and x['reserved_runner_minutes'] == 10
                and x['reserved_units'] == 14 and x['reserved_requests'] == 40 for x in claims),
            'INVALID_OR_REDUCED_RESERVATION')
    require(len({x['request_id'] for x in claims}) == len(claims), 'DUPLICATE_CLAIM')
    current = [x for x in claims if x['request_id'] == REQUEST_ID]
    require(len(current) == 1 and current[0]['status'] == 'RESERVED_BEFORE_EFFECT', 'EXACT_UNSPENT_CLAIM_REQUIRED')
    now = dt.datetime.now(dt.timezone.utc)
    require(0 <= (now - dt.datetime.fromisoformat(current[0]['reserved_at'])).total_seconds() < 3600,
            'CLAIM_EXPIRED')
    require(sum(x['reserved_transfer_bytes'] for x in claims) <= 8_000_000_000, 'MONTHLY_TRANSFER_CAP')
    require(sum(x['reserved_runner_minutes'] for x in claims) <= 1100, 'MONTHLY_RUNTIME_CAP')
    require(sum(x['reserved_requests'] for x in claims) <= 100000, 'MONTHLY_REQUEST_CAP')
    today = now.date().isoformat()
    require(sum(x['day_utc'] == today for x in claims) <= 3, 'DAILY_JOB_CAP')
    require(sum(x['reserved_units'] for x in claims if x['day_utc'] == today) <= 450, 'DAILY_UNIT_CAP')
    require(ledger['production'] is False and ledger['publication'] is False, 'AUTHORITY_BOUNDARY_CHANGED')


def artifact_preflight(key, out):
    # No RapidAPI credential is used here. This token is scoped to this repository.
    token = os.environ.get('GH_ARTIFACT_TOKEN', '')
    require(bool(token), 'ARTIFACT_READ_TOKEN_MISSING')
    size = count = 0
    for page in range(1, 11):
        url = 'https://api.github.com/repos/' + REPO + '/actions/artifacts?per_page=100&page=' + str(page)
        req = Request(url, headers={'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
        with build_opener(n.NoRedirect()).open(req, timeout=15) as response:
            body = response.read(256 * 1024 + 1)
            require(len(body) <= 256 * 1024, 'ARTIFACT_INVENTORY_RESPONSE_CAP')
            values = json.loads(body)['artifacts']
        for item in values:
            if not item['expired']:
                size += item['size_in_bytes']
                count += 1
        if len(values) < 100:
            break
    else:
        raise n.ProbeError('ARTIFACT_INVENTORY_INCOMPLETE')
    require(size + 96 * 1024**2 <= 450_000_000, 'REPOSITORY_ARTIFACT_HEADROOM_REQUIRED')
    return {'unexpired_repository_artifact_bytes': size, 'unexpired_artifacts': count,
        'reserved_output_bytes': 96 * 1024**2, 'account_wide_storage_not_proven_by_repo_inventory': True}


def inspect(out, evidence):
    path = out / 'native.mp4'
    data = json.loads(n.command(['ffprobe', '-v', 'error', '-show_entries',
        'format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,duration',
        '-of', 'json', str(path)]))
    vs = [s for s in data['streams'] if s['codec_type'] == 'video']
    aus = [s for s in data['streams'] if s['codec_type'] == 'audio']
    require(len(vs) == 1 and len(aus) == 1, 'ONE_NATIVE_VIDEO_AND_AUDIO_REQUIRED')
    require(vs[0]['height'] == 1080, 'REQUESTED_1080P_REQUIRED')
    require(abs(float(data['format']['duration']) - 10) <= .1, 'EXACT_TEN_SECOND_WINDOW_REQUIRED')
    evidence['native_probe'] = data
    n.command(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'])
    evidence['complete_clip_decode_passed'] = True
    evidence['source_clock_mapping'] = []
    for offset in [0, 5, 9]:
        target = out / ('frame-%02d.jpg' % offset)
        n.command(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(offset), '-i', str(path), '-frames:v', '1', '-q:v', '2', str(target)])
        evidence['source_clock_mapping'].append({'local_seconds': offset, 'source_seconds': 6354 + offset,
            'file': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    n.command(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-map', '0:a:0', '-c:a', 'pcm_s16le', str(out / 'audio-review.wav')])
    evidence['native_pcm_sha256'] = hashlib.sha256((out / 'audio-review.wav').read_bytes()).hexdigest()
    require(sum(p.stat().st_size for p in out.iterdir() if p.is_file()) < 96 * 1024**2, 'OUTPUT_STORAGE_CAP')


def run(out, e, key):
    require(os.environ.get('GITHUB_REPOSITORY') == REPO, 'REPOSITORY_MISMATCH')
    require(os.environ.get('GITHUB_RUN_NUMBER') == '2' and os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'DUPLICATE_RUN_REFUSED')
    no_effect = json.loads((EVIDENCE / 'rapidapi-midpoint-no-effect-38761164057.json').read_text())['result']
    require(no_effect['effect_status'] == 'NOT_SENT' and no_effect['download_tools_call_requests'] == 0
        and no_effect['failure_code'] == 'REQUEST_COUNTER_CHANGED_RECONCILIATION_REQUIRED',
        'PRIOR_ZERO_EFFECT_REQUIRED')
    budget_preflight(json.loads((EVIDENCE / 'native-av-reservations.json').read_text()))
    prior = json.loads((EVIDENCE / 'rapidapi-native-first-result.json').read_text())
    require(prior['complete_clip_decode_passed'] and prior['download_tools_call_requests'] == 1,
            'PRIOR_SUCCESS_REQUIRED_NO_REACQUISITION')
    n.command(['ffmpeg', '-v', 'error', '-version'])
    e['storage_preflight'] = artifact_preflight(key, out)
    # Poll the already completed job once for fresh counters; never reacquire it.
    q_e = {'progress_polls': 0, 'control_response_bytes': 0,
        'baseline_quota_headers': prior['last_quota_headers']}
    previous = n.progress(prior['provider_job_id'], key, q_e, out, 99)
    require(previous.get('success') == 1 and previous.get('progress') == 1000, 'EXISTING_JOB_NOT_FINISHED')
    q = q_e['last_quota_headers']
    e['fresh_preflight_quota_headers'] = q
    e['existing_job_preflight_polls'] = 1
    e['preflight_control_response_bytes'] = q_e['control_response_bytes']
    n.private_json(out / 'receipt.json', e, key)
    require(q.get('x-ratelimit-units-limit') == '500' and q.get('x-ratelimit-units-remaining') == '486', 'QUOTA_CHANGED_RECONCILIATION_REQUIRED')
    require(q.get('x-ratelimit-requests-limit') == '500000'
        and 499900 <= int(q.get('x-ratelimit-requests-remaining', '0')) <= 499995
        and q.get('x-ratelimit-rapid-free-plans-hard-limit-limit') == '500000'
        and 499900 <= int(q.get('x-ratelimit-rapid-free-plans-hard-limit-remaining', '0')) <= 499995,
        'MONTHLY_INCLUDED_HEADROOM_REQUIRED')
    e['request_counter_reconciliation'] = {'prior_observed_remaining': 499995,
        'fresh_remaining': int(q['x-ratelimit-requests-remaining']),
        'difference_includes_preflight_and_any_intervening_usage_not_attributed_to_media':
            499995 - int(q['x-ratelimit-requests-remaining']),
        'no_exact_counter_assumption': True, 'native_quality_gates_unchanged': True}
    e['baseline_quota_headers'] = q
    e['existing_job_preflight_polls'] = 1
    e['control_response_bytes'] = q_e['control_response_bytes']
    n.PARAMS.update(start_time=WINDOW[0], end_time=WINDOW[1])
    n.REQUEST_ID = REQUEST_ID
    client = n.Client(key)
    client.send('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
        'clientInfo': {'name': 'heroverse-preclaimed-midpoint', 'version': '1'}})
    client.send('notifications/initialized')
    started = n.start_download(client, n.OneStart(), e, out)
    job = started.get('id')
    require(isinstance(job, str) and n.re.fullmatch(r'[a-zA-Z0-9_-]{1,160}', job), 'NO_RESUMABLE_JOB_ID')
    require(key not in job, 'REFLECTED_CREDENTIAL')
    e['provider_job_id'] = job
    e['effect_status'] = 'JOB_ID_RECEIVED_NO_RESTART_ALLOWED'
    n.private_json(out / 'receipt.json', e, key)
    print('HEROVERSE_MIDPOINT_JOB_SAVED=' + json.dumps({'request_id': REQUEST_ID, 'provider_job_id': job}), flush=True)
    deadline = time.monotonic() + 270
    for index in range(n.MAX_POLLS):
        require(time.monotonic() <= deadline, 'RESUME_EXISTING_JOB_ONLY')
        if index:
            time.sleep(10)
        value = n.progress(job, key, e, out, index)
        url = value.get('download_url') or value.get('downloadUrl') or value.get('file_url')
        if url:
            n.fetch_media(url, out, e)
            inspect(out, e)
            e['status'] = 'NATIVE_MIDPOINT_DECODED_AWAITING_REVIEW'
            return
        require(value.get('status') not in ('error', 'failed', 'FAILED') and not value.get('error'), 'SOURCE_JOB_FAILED_NO_RESTART')
    raise n.ProbeError('RESUME_EXISTING_JOB_ONLY')


def main():
    out = Path('output/qualification/rapidapi-native-j2rk8ycXe3c-midpoint-v1')
    out.mkdir(parents=True, exist_ok=True)
    key = os.environ.get('HERO_RAPIDAPI_KEY', '')
    e = {'version': 'preclaimed-native-midpoint-v1', 'request_id': REQUEST_ID,
        'source_video_id': 'j2rk8ycXe3c', 'source_requested_seconds': WINDOW,
        'started_at': n.utc_now(), 'status': 'BLOCKED', 'effect_status': 'NOT_SENT',
        'download_tools_call_requests': 0, 'progress_polls': 0,
        'production': False, 'publication': False, 'supervisor': False,
        'perceptual_audio_review_completed': False, 'recurring_capacity_qualified': False}
    started = time.monotonic()
    try:
        require(bool(key), 'KEY_MISSING')
        run(out, e, key)
    except Exception as error:
        e['failure_code'] = str(error) if isinstance(error, n.ProbeError) else type(error).__name__
    e['elapsed_seconds'] = round(time.monotonic() - started, 3)
    e['completed_at'] = n.utc_now()
    n.private_json(out / 'receipt.json', e, key)
    print('HEROVERSE_MIDPOINT_RECEIPT=' + json.dumps(e), flush=True)
    return 0 if e['status'] == 'NATIVE_MIDPOINT_DECODED_AWAITING_REVIEW' else 2


if __name__ == '__main__':
    raise SystemExit(main())
