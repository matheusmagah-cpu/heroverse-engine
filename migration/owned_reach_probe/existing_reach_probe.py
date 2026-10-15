"""Review-only bounded read probe. No CLI, credential loading, job creation or dispatch.
Caller must supply the already-authorized Reporting service/read executor and a
preauthenticated session after original resource/quota/auth preflight.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl
from zoneinfo import ZoneInfo

CHANNEL = 'UCuMF6pJQkyMzaVoAxFL86yA'
JOB = 'ce0b4a6d-b8db-4550-a856-5ff8e8a83ba2'
REPORT_IDS = ('17695215035', '20613781334')
FETCH_REPORT_IDS = ('20613781334',)
REPORT_TYPE = 'channel_reach_basic_a1'
MAX_REPORT_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_ROWS = 20000
MAX_SECONDS = 90
COLUMNS = {'date', 'channel_id', 'video_id', 'video_thumbnail_impressions', 'video_thumbnail_impressions_ctr'}
PACIFIC = ZoneInfo('America/Los_Angeles')
CTR_UNIT = 'provider_raw_representation_unverified'
SOURCE_SHA = '49032963a3e1bd0421c487ea6e4aa6d8f5e96b0f2d6153506f9e62d2f25a1a3c'


class ProbeBlocked(ValueError):
    """Errors contain codes only, never URLs, token-bearing exceptions or CSV rows."""


def require(ok, code):
    if not ok:
        raise ProbeBlocked(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def dt(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def plan_from_snapshot(raw):
    require(digest(raw) == SOURCE_SHA, 'SNAPSHOT_HASH_MISMATCH')
    data = json.loads(raw)
    require(data['channel_id'] == CHANNEL, 'CHANNEL_MISMATCH')
    jobs = [j for j in data['reporting']['jobs'] if j.get('id') == JOB and j.get('report_type_id') == REPORT_TYPE]
    require(len(jobs) == 1, 'EXACT_JOB_REQUIRED')
    selected = {r['id']: r for r in jobs[0]['reports'] if r['id'] in REPORT_IDS}
    require(set(selected) == set(REPORT_IDS), 'EXACT_REPORTS_REQUIRED')
    targets = [v['video_id'] for v in data['owned_private']]
    require(len(targets) == 8 and len(set(targets)) == 8, 'EXACT_TARGET_SET_REQUIRED')
    return {'reports': selected, 'target_video_ids': targets, 'source_captured_at': data['captured_at']}


def verify_resource(resource, expected):
    require(resource.get('id') in FETCH_REPORT_IDS, 'REPORT_NOT_PENDING')
    require(resource.get('jobId') == JOB and resource.get('id') == expected['id'], 'REPORT_IDENTITY_MISMATCH')
    for a, b in [('startTime', 'start_time'), ('endTime', 'end_time'), ('createTime', 'create_time')]:
        require(resource.get(a) == expected[b], 'REPORT_TIME_MISMATCH')
    require(dt(resource['startTime']) < dt(resource['endTime']), 'REPORT_TIME_ORDER')
    validate_download_url(resource.get('downloadUrl', ''), resource['id'])


def validate_download_url(url, report_id):
    require(report_id in FETCH_REPORT_IDS, 'REPORT_NOT_PENDING')
    require(isinstance(url, str) and 0 < len(url) <= 1000, 'DOWNLOAD_URL_INVALID')
    u = urlsplit(url)
    require(u.scheme == 'https' and u.netloc == 'youtubereporting.googleapis.com' and not u.fragment, 'DOWNLOAD_ORIGIN_BLOCKED')
    # Provider resource name may use a channel identifier differing from UC id.
    # Exact job/report suffix binds resource; CSV channel must match CHANNEL.
    pattern = rf'/v1/media/CHANNEL/[A-Za-z0-9_-]+/jobs/{re.escape(JOB)}/reports/{re.escape(report_id)}'
    require(re.fullmatch(pattern, u.path) is not None, 'DOWNLOAD_PATH_BLOCKED')
    require(parse_qsl(u.query, keep_blank_values=True) == [('alt', 'media')], 'DOWNLOAD_QUERY_BLOCKED')


def bounded_download(session, resource, remaining, deadline):
    validate_download_url(resource['downloadUrl'], resource['id'])
    require(time.monotonic() < deadline, 'DEADLINE_EXCEEDED')
    limit = min(MAX_REPORT_BYTES, remaining)
    require(limit > 0, 'TOTAL_BYTE_LIMIT')
    # No redirect following: authorization never forwarded to any new origin.
    response = session.get(resource['downloadUrl'], headers={'Accept-Encoding': 'identity'},
                           stream=True, allow_redirects=False, timeout=(10, min(20, max(1, deadline-time.monotonic()))))
    try:
        require(response.status_code == 200, 'DOWNLOAD_HTTP_NOT_200')
        require(not response.history, 'REDIRECT_HISTORY_BLOCKED')
        require(response.url == resource['downloadUrl'], 'RESPONSE_URL_MISMATCH')
        encoding = response.headers.get('Content-Encoding', '').lower()
        require(encoding in ('', 'identity'), 'UNEXPECTED_CONTENT_ENCODING')
        length = response.headers.get('Content-Length')
        if length is not None:
            require(length.isdigit() and int(length) <= limit, 'CONTENT_LENGTH_LIMIT')
        chunks = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            require(time.monotonic() < deadline, 'DEADLINE_EXCEEDED')
            require(len(chunks) + len(chunk) <= limit, 'STREAM_BYTE_LIMIT')
            chunks.extend(chunk)
        require(bool(chunks), 'EMPTY_DOWNLOAD')
        if length is not None:
            require(len(chunks) == int(length), 'CONTENT_LENGTH_MISMATCH')
        return bytes(chunks)
    finally:
        response.close()


def parse_reporting_day(raw):
    # Preserve provider text; accept observed compact dates and documented ISO dates.
    fmt = '%Y%m%d' if re.fullmatch(r'[0-9]{8}', raw) else '%Y-%m-%d' if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', raw) else None
    require(fmt is not None, 'CSV_DATE_INVALID')
    try:
        return datetime.strptime(raw, fmt).replace(tzinfo=PACIFIC)
    except ValueError:
        raise ProbeBlocked('CSV_DATE_INVALID') from None


def dimension_key(row):
    return (parse_reporting_day(row['date']).date().isoformat(), row['channel_id'], row['video_id'])


def parse_csv(raw, resource):
    require(len(raw) <= MAX_REPORT_BYTES, 'CSV_BYTE_LIMIT')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), strict=True)
    headers = reader.fieldnames or []
    require(len(headers) == len(set(headers)) and set(headers) == COLUMNS, 'CSV_SCHEMA_MISMATCH')
    start, end = dt(resource['startTime']), dt(resource['endTime'])
    seen = set()
    parsed = []
    for row in reader:
        require(len(parsed) < MAX_ROWS, 'CSV_ROW_LIMIT')
        require(set(row) == COLUMNS and all(x is not None for x in row.values()), 'CSV_ROW_SHAPE')
        require(row['channel_id'] == CHANNEL, 'CSV_CHANNEL_MISMATCH')
        require(re.fullmatch(r'[A-Za-z0-9_-]{11}', row['video_id']) is not None, 'CSV_VIDEO_ID_INVALID')
        day = parse_reporting_day(row['date'])
        # Reporting date dimension is Pacific time, not UTC calendar slicing.
        require(start <= day and day + timedelta(days=1) <= end, 'CSV_DATE_OUTSIDE_REPORT')
        key = dimension_key(row)
        require(key not in seen, 'CSV_DUPLICATE_DIMENSION_KEY')
        seen.add(key)
        require(re.fullmatch(r'\d+', row['video_thumbnail_impressions']) is not None, 'CSV_IMPRESSIONS_INVALID')
        try:
            ctr = Decimal(row['video_thumbnail_impressions_ctr'])
        except InvalidOperation:
            raise ProbeBlocked('CSV_CTR_INVALID') from None
        require(ctr.is_finite() and 0 <= ctr <= 100, 'CSV_CTR_RANGE')
        parsed.append(dict(row))  # Retain exact provider string, never rescale.
    return {'headers': headers, 'rows': parsed, 'row_count': len(parsed), 'duplicate_dimension_keys': 0}


def collect_existing_reports(snapshot_raw, service, execute, session, output_dir):
    """Called only after root review; this function itself has no auth/setup code.
    execute(request, stage) must use existing bounded execute_google_request.
    service is only used as jobs().reports().get(), never list/create.
    session must disable retries, redirects, implicit credential refresh and proxies.
    """
    plan = plan_from_snapshot(snapshot_raw)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + MAX_SECONDS
    total = 0
    records = []
    observed = {v: [] for v in plan['target_video_ids']}
    all_keys = set()
    failed = None
    for report_id in FETCH_REPORT_IDS:
        record = {'report_id': report_id, 'job_id': JOB, 'status': 'NOT_READ'}
        try:
            require(time.monotonic() < deadline, 'DEADLINE_EXCEEDED')
            expected = plan['reports'][report_id]
            resource = execute(service.jobs().reports().get(jobId=JOB, reportId=report_id), 'existing-reach-' + report_id)
            verify_resource(resource, expected)
            record.update({k: expected[k] for k in ('start_time', 'end_time', 'create_time')})
            raw = bounded_download(session, resource, MAX_TOTAL_BYTES-total, deadline)
            total += len(raw)
            name = 'report-' + report_id + '.csv'
            with (out / name).open('xb') as f:
                f.write(raw)
            record.update(raw_file=name, raw_sha256=digest(raw), raw_bytes=len(raw))
            parsed = parse_csv(raw, resource)
            record.update(headers=parsed['headers'], row_count=parsed['row_count'], duplicate_dimension_keys=0)
            keys = {dimension_key(row) for row in parsed['rows']}
            require(not keys.intersection(all_keys), 'CROSS_REPORT_DUPLICATE_KEY')
            all_keys.update(keys)
            for row in parsed['rows']:
                if row['video_id'] in observed:
                    observed[row['video_id']].append(dict(row, report_id=report_id))
            record['status'] = 'INGESTED'
        except Exception as error:
            failed = str(error) if isinstance(error, ProbeBlocked) else type(error).__name__
            record.update(status='BLOCKED', error_code=failed)
        records.append(record)
        if failed:
            break  # No retry/fallback/expanded report search.
    result = {'schema_version': 'existing-reach-probe-v1', 'status': 'BLOCKED' if failed else 'INGESTED_BOUNDED_REPORTS',
              'channel_id': CHANNEL, 'job_id': JOB, 'report_type': REPORT_TYPE,
              'source_snapshot_sha256': digest(snapshot_raw), 'source_captured_at': plan['source_captured_at'],
              'reports_requested': list(FETCH_REPORT_IDS), 'reports': records, 'csv_bytes_preserved': total,
              'csv_rows_ingested': len(all_keys), 'ctr_unit': CTR_UNIT,
              'coverage_scope': 'ONLY_SECOND_PENDING_REPORT_PERIOD_NOT_COMBINED_OR_LIFETIME',
              'video_observations': [{'video_id': v, 'status': ('PARTIAL_ROWS_PROBE_BLOCKED' if r else 'UNKNOWN_PROBE_BLOCKED') if failed else ('OBSERVED_ROWS' if r else 'NO_MATCHING_ROW_IN_INGESTED_REPORTS'),
                                      'covered_dates': sorted({x['date'] for x in r}), 'rows': r,
                                      'aggregate_ctr': None} for v,r in observed.items()],
              'new_jobs_created': 0, 'public_metadata_collected': False, 'manual_approval': False,
              'production_approved': False, 'publication_authorized': False}
    with (out / 'receipt.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    return result
