"""One durable normal observation attempt per UTC day; no provider transport."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE = Path('migration/evidence')

def normal_collection(env):
    return not any(env.get(k) == 'true' for k in (
        'HERO_AUTH_HEALTH_ONLY', 'HERO_CANDIDATE_PROBE_ONLY',
        'HERO_CANDIDATE_CATALOG_ONLY', 'HERO_REFERENCE_EXTENSION_ONLY'))

def observed(path):
    raw = path.read_bytes()
    data = json.loads(raw)
    if (data.get('schema_version') != 'cloud-evidence-v1'
            or data.get('channel_id') != 'UCuMF6pJQkyMzaVoAxFL86yA'
            or data.get('publication_performed') is not False
            or data.get('production_ready') is not False
            or data.get('candidate_media_downloaded') is not False
            or not {'owned_channel', 'market_snapshots', 'cohorts_by_duration'} <= data.keys()):
        raise PermissionError('NORMAL_OBSERVATION_REQUIRED')
    captured = datetime.fromisoformat(data['captured_at'].replace('Z', '+00:00'))
    if captured.tzinfo is None:
        raise PermissionError('OBSERVATION_TIMEZONE_REQUIRED')
    return data, captured.astimezone(timezone.utc), hashlib.sha256(raw).hexdigest()

def reserve_or_reuse(run, commit, now=None):
    from durable_evidence_checkpoint import CLAIM
    if not CLAIM.is_file() or json.loads(CLAIM.read_text()).get('run_id') != run:
        raise PermissionError('DURABLE_OBSERVER_CLAIM_REQUIRED')
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(timezone.utc).date().isoformat()
    marker = EVIDENCE / ('daily-observation-' + day + '.json')
    if marker.exists():
        record = json.loads(marker.read_text())
        if record.get('day') != day or record.get('status') != 'COMPLETED':
            raise PermissionError('DAILY_ATTEMPT_REQUIRES_RECONCILIATION')
        path = Path(record['source_path'])
        if path.parent != EVIDENCE or not re.fullmatch(r'observer-\d+\.json', path.name):
            raise PermissionError('DAILY_SOURCE_PATH_INVALID')
        _, captured, digest = observed(path)
        if digest != record['source_sha256'] or captured > now or captured.date().isoformat() != day:
            raise PermissionError('DAILY_SOURCE_BINDING_INVALID')
        return path
    # Adopt today's already checkpointed normal observation, never retimestamp it.
    candidates = []
    prior_day_sources = {r.get('source_path') for p in EVIDENCE.glob('daily-observation-*.json')
                         for r in [json.loads(p.read_text())] if r.get('day') != day}
    for path in EVIDENCE.glob('observer-*.json'):
        if not re.fullmatch(r'observer-\d+\.json', path.name):
            continue
        if str(path) in prior_day_sources:
            continue  # A midnight-spanning attempt belongs to its reserved day.
        data = json.loads(path.read_text())
        if 'owned_channel' not in data or 'cohorts_by_duration' not in data:
            continue  # Separate explicitly requested candidate/health stage.
        _, captured, digest = observed(path)
        if captured > now:
            raise PermissionError('FUTURE_OBSERVATION_REQUIRES_RECONCILIATION')
        if captured.date().isoformat() == day:
            candidates.append((captured, path, digest))
    record = {'day': day, 'run_id': run, 'status': 'CLAIMED', 'publication_authorized': False}
    reuse = None
    if candidates:
        _, reuse, digest = max(candidates)
        record.update(status='COMPLETED', source_path=str(reuse), source_sha256=digest)
    with marker.open('x') as out:
        json.dump(record, out, sort_keys=True)
    # A failed/uncertain durable push prevents ALL new remote effects.
    commit('Reserve daily normal observation or bind existing observation')
    return reuse

def reuse_state(run, source, copied):
    if source.parent != EVIDENCE or not re.fullmatch(r'observer-\d+\.json', source.name):
        raise PermissionError('DAILY_SOURCE_PATH_INVALID')
    data, _, digest = observed(source)
    if copied.read_bytes() != source.read_bytes():
        raise PermissionError('DAILY_REUSE_COPY_CHANGED')
    origin = source.stem.split('-')[-1]
    if data.get('operation_id') != 'cloud-evidence-' + origin:
        raise PermissionError('DAILY_SOURCE_OPERATION_CHANGED')
    return {'last_checkpointed_run': origin, 'collection_complete': True,
            'publication_performed': False, 'last_reuse_run': run,
            'reused_observation': {'source_path': str(source), 'source_sha256': digest,
                                   'captured_at': data['captured_at']}}

def complete(run, immutable):
    # Called only inside the existing durable final checkpoint. Preserve the
    # original reserved date even when collection finishes after UTC midnight.
    markers = [p for p in EVIDENCE.glob('daily-observation-*.json')
               if json.loads(p.read_text()).get('run_id') == run
               and json.loads(p.read_text()).get('status') == 'CLAIMED']
    if not markers:
        return
    if len(markers) != 1:
        raise PermissionError('DAILY_RESERVATION_AMBIGUOUS')
    _, _, digest = observed(immutable)
    record = json.loads(markers[0].read_text())
    record.update(status='COMPLETED', source_path=str(immutable), source_sha256=digest)
    markers[0].write_text(json.dumps(record, sort_keys=True))
