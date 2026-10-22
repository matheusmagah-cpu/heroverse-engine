"""One explicitly admitted three-source exception; no recurring cap change."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import second_opening as s

SOURCES = ('VA3qvxoZr4Q', 'EkT0XMVln3s', 'ksMAEHpzkZo')
BATCH_ID = '20261015-three-remaining-openings-v1'
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'evidence/cloud-video-player-20261015'
REQUESTS = tuple('20261015-rapidapi-native-' + source + '-0-40-v1' for source in SOURCES)
EXCEPTION = {'day_utc': '2026-10-15', 'request_ids': sorted(REQUESTS)}
INITIAL_REQUESTS = {
    '20261015-rapidapi-native-j2rk8ycXe3c-0-40-v1',
    '20261015-rapidapi-native-j2rk8ycXe3c-6354-6364-v1',
    '20261015-rapidapi-native-BeFOHnncaeQ-0-40-v1',
}
SNAPSHOT_SHA = '49032963a3e1bd0421c487ea6e4aa6d8f5e96b0f2d6153506f9e62d2f25a1a3c'


def validate_admission(value, now):
    s.require(value.get('batch_id') == BATCH_ID and value.get('status') == 'APPROVED_ONE_TIME_EXCEPTION', 'EXPLICIT_BATCH_APPROVAL_MISSING')
    s.require(value.get('approved_by_owner') is True and bool(value.get('approval_message_id')), 'OWNER_APPROVAL_EVIDENCE_MISSING')
    s.require(value.get('sources') == list(SOURCES) and value.get('qualification_exception') == EXCEPTION, 'EXACT_BATCH_SCOPE_REQUIRED')
    s.require(value.get('production') is False and value.get('publication') is False
              and value.get('recurring_cadence_authorized') is False, 'AUTHORITY_BOUNDARY_CHANGED')
    billing = value['billing']
    age = (now - dt.datetime.fromisoformat(billing['observed_at'].replace('Z', '+00:00'))).total_seconds()
    # Allow a maximum thirty-minute batch inside a one-hour billing observation.
    s.require(0 <= age <= 1800, 'FRESH_BATCH_BILLING_REQUIRED')
    s.require(billing['github_included_runner_minutes_remaining'] >= 30, 'BATCH_RUNNER_HEADROOM_REQUIRED')
    return billing


def validate_metadata(inventory, source, now):
    provenance = inventory['provenance']
    age = (now - dt.datetime.fromisoformat(provenance['captured_at'].replace('Z', '+00:00'))).total_seconds()
    s.require(0 <= age < 86400 and provenance['observer_sha256'] == SNAPSHOT_SHA, 'CURRENT_BOUND_SNAPSHOT_REQUIRED')
    rows = [x for x in inventory['source_inventory'] if x['video_id'] == source]
    s.require(len(rows) == 1, 'EXACT_METADATA_SOURCE_REQUIRED')
    row = rows[0]
    s.require(row['metadata_eligibility'] == 'PASS_EXACT_DECLARED_SELECT_RULES'
              and row['declared_audio_language'] == 'en-US'
              and row['saved_broad_cohort_age_band'] == '8_30D'
              and 40 <= row['duration_seconds'] <= 14400, 'METADATA_ELIGIBILITY_CHANGED')
    expected_kind = dict(zip(SOURCES, ('WINNER', 'MEDIAN', 'WEAK')))
    s.require(row['saved_broad_cohort_kind'] == expected_kind[source], 'COHORT_KIND_CHANGED')
    return {'snapshot_id': row['snapshot_id'], 'captured_at': provenance['captured_at'],
            'observer_sha256': provenance['observer_sha256'], 'metadata_eligibility': row['metadata_eligibility']}


def prior_claims(ledger, index, receipt_root):
    s.require({x['request_id'] for x in ledger['claims']} == INITIAL_REQUESTS
              and len(ledger['claims']) == 3 and ledger['limits']['daily_jobs'] == 3, 'INITIAL_THREE_CLAIMS_REQUIRED')
    # Append actual previous successes, not invented reservations or resets.
    ledger = json.loads(json.dumps(ledger))
    for previous in range(index):
        p = receipt_root / SOURCES[previous] / 'chain-receipt.json'
        s.require(p.is_file(), 'PREDECESSOR_RECEIPT_MISSING')
        s.require(p.stat().st_size <= 262144, 'PREDECESSOR_RECEIPT_BYTE_CAP')
        value = json.loads(p.read_text())
        s.require(value.get('batch_id') == BATCH_ID and value.get('request_id') == REQUESTS[previous]
                  and value.get('source_video_id') == SOURCES[previous]
                  and value.get('status') == 'NATIVE_OPENING_DECODED_AWAITING_REVIEW'
                  and value.get('download_tools_call_requests') == 1
                  and value.get('complete_clip_decode_passed') is True
                  and value.get('run_id') == os.environ.get('GITHUB_RUN_ID')
                  and value.get('head_sha') == os.environ.get('GITHUB_SHA'), 'PREDECESSOR_NOT_SUCCESSFUL_THIS_RUN')
        media = value.get('media_file', {})
        s.require(isinstance(media.get('bytes'), int) and 16 <= media['bytes'] <= 64 * 1024**2
                  and isinstance(media.get('sha256'), str) and s.n.re.fullmatch(r'[0-9a-f]{64}', media['sha256'])
                  and isinstance(value.get('provider_job_id'), str)
                  and s.n.re.fullmatch(r'[a-zA-Z0-9_-]{1,160}', value['provider_job_id']), 'PREDECESSOR_NATIVE_PROOF_MISSING')
        claim = value['reservation']
        s.require(claim['request_id'] == REQUESTS[previous], 'PREDECESSOR_CLAIM_MISMATCH')
        ledger['claims'].append(dict(claim, status='COMPLETED_RESERVATION_RETAINED',
                                     provider_job_id=value['provider_job_id']))
    return ledger


def prepare_config(source, receipt_root, now):
    s.require(source in SOURCES, 'SOURCE_NOT_ALLOWLISTED')
    index = SOURCES.index(source)
    approval = json.loads((EVIDENCE / 'remaining-openings-admission.json').read_text())
    billing = dict(validate_admission(approval, now), request_id=REQUESTS[index], status='VERIFIED_FOR_ONE_SHOT')
    metadata = validate_metadata(json.loads((EVIDENCE / 'five-source-native-gap.json').read_text()), source, now)
    ledger = prior_claims(json.loads((EVIDENCE / 'native-av-reservations.json').read_text()), index, receipt_root)
    params = dict(s.PARAMS, url='https://www.youtube.com/watch?v=' + source)
    plan = {'request_id': REQUESTS[index], 'status': 'PLANNED_NOT_ADMITTED',
            'parameters': params, 'reservation': s.RESERVATION}
    return index, metadata, {'plan': plan, 'ledger': ledger, 'billing': billing, 'qualification_exception': EXCEPTION}


def execute(source, out, receipt_root, evidence, key):
    index, metadata, config = prepare_config(source, receipt_root, dt.datetime.now(dt.timezone.utc))
    s.SOURCE, s.REQUEST_ID, s.PARAMS = source, REQUESTS[index], config['plan']['parameters']
    s.EVIDENCE = EVIDENCE
    # Reuse admission before any GitHub/provider request too.
    s.admit(config['plan'], config['ledger'], config['billing'], dt.datetime.now(dt.timezone.utc), EXCEPTION)
    inventory = s.artifact_preflight(key, out)
    remaining = len(SOURCES) - index
    s.require(inventory['unexpired_repository_artifact_bytes'] + remaining * 96 * 1024**2 <= 450_000_000, 'BATCH_STORAGE_HEADROOM_REQUIRED')
    evidence['metadata_binding'] = metadata
    evidence['batch_storage_preflight'] = dict(inventory, reserved_remaining_output_bytes=remaining * 96 * 1024**2)
    # Fresh counters checked by the existing success-job poll inside s.run.
    # Its usual 14/40 minimum is strengthened for all remaining sources.
    original_quota = s.fresh_quota
    def remaining_quota(q):
        original_quota(q)
        s.require(int(q['x-ratelimit-units-remaining']) >= remaining * 14, 'BATCH_UNIT_HEADROOM_REQUIRED')
        for prefix in ('x-ratelimit-requests', 'x-ratelimit-rapid-free-plans-hard-limit'):
            s.require(int(q[prefix + '-remaining']) >= remaining * 40, 'BATCH_REQUEST_HEADROOM_REQUIRED')
    s.fresh_quota = remaining_quota
    s.run(out, evidence, key, config=config)


def main():
    source = sys.argv[1] if len(sys.argv) == 2 else ''
    s.require(source in SOURCES, 'SOURCE_NOT_ALLOWLISTED')
    root = Path('output/qualification/remaining-openings')
    out = root / source
    out.mkdir(parents=True, exist_ok=False)
    out.chmod(0o700)
    receipt_root = Path('output/predecessors')
    chain_dir = Path('output/chain') / source
    chain_dir.mkdir(parents=True, exist_ok=False)
    key = os.environ.get('HERO_RAPIDAPI_KEY', '')
    e = dict(version='remaining-opening-v1', batch_id=BATCH_ID,
        request_id=REQUESTS[SOURCES.index(source)], source_video_id=source,
        source_requested_seconds=[0,40], run_id=os.environ.get('GITHUB_RUN_ID'), head_sha=os.environ.get('GITHUB_SHA'),
        started_at=s.n.utc_now(), status='BLOCKED', effect_status='NOT_SENT', download_tools_call_requests=0,
        progress_polls=0, gateway_request_attempts=0, control_response_bytes=0,
        production=False, publication=False, supervisor=False, recurring_capacity_qualified=False,
        perceptual_audio_review_completed=False)
    start=time.monotonic()
    try:
        execute(source,out,receipt_root,e,key)
    except Exception as error:
        e['status']='BLOCKED'
        e['failure_code']=str(error) if isinstance(error,s.n.ProbeError) else type(error).__name__
    e.update(elapsed_seconds=round(time.monotonic()-start,3),completed_at=s.n.utc_now(),restart_allowed=False)
    s.n.private_json(out/'receipt.json',e,key)
    # Small sanitized predecessor proof only, not copied media/model payloads.
    chain_fields=('batch_id','request_id','source_video_id','run_id','head_sha','status',
                  'download_tools_call_requests','complete_clip_decode_passed','reservation','provider_job_id','media_file')
    s.n.private_json(chain_dir/'chain-receipt.json',{k:e[k] for k in chain_fields if k in e},key)
    print('HEROVERSE_REMAINING_OPENING_RECEIPT='+json.dumps({k:e[k] for k in
        ('request_id','status','effect_status','download_tools_call_requests','gateway_request_attempts','elapsed_seconds')}),flush=True)
    return 0 if e['status']=='NATIVE_OPENING_DECODED_AWAITING_REVIEW' else 2

if __name__=='__main__':raise SystemExit(main())
