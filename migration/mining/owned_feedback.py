#!/usr/bin/env python3
"""Offline descriptive owned-video feedback. Never approves or predicts performance.
CLI: owned_feedback.py OUT_JSON LEDGER_JSON REACH_JSON SNAPSHOT_JSON [SNAPSHOT_JSON ...]
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

UNITS = {'views': 'views', 'estimatedMinutesWatched': 'minutes', 'averageViewDuration': 'seconds',
         'averageViewPercentage': 'percent', 'subscribersGained': 'subscribers', 'subscribersLost': 'subscribers'}
PUBLIC = {'viewCount': 'views', 'likeCount': 'likes', 'commentCount': 'comments'}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def read_source(path):
    data = Path(path).read_bytes()
    return json.loads(data), {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'hash_method': 'EXACT_FILE_BYTES'}


def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite input')
    if isinstance(value, dict):
        for item in value.values(): finite(item)
    elif isinstance(value, list):
        for item in value: finite(item)


def number(value):
    if value is None: return None
    if isinstance(value, bool): raise ValueError('boolean metric')
    try: n = float(value)
    except (ValueError, TypeError): raise ValueError('invalid numeric metric') from None
    if not math.isfinite(n) or n < 0: raise ValueError('invalid numeric metric')
    return int(n) if n.is_integer() else n


def source(document, provided=None):
    if provided:
        return copy.deepcopy(provided)
    return {'path': None, 'sha256': None, 'hash_method': None,
            'content_fingerprint': hashlib.sha256(canonical(document).encode()).hexdigest()}


def evidence(src, pointer):
    return dict(src, json_pointer=pointer)


def metric(value, unit, src, pointer):
    val = number(value)
    return {'value': val, 'unit': unit, 'status': 'OBSERVED' if val is not None else 'UNKNOWN',
            'evidence': evidence(src, pointer)}


def unique(rows, key):
    ids = [r.get(key) for r in rows]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('missing or duplicate ' + key)


def without_evidence(value):
    if isinstance(value, dict): return {k: without_evidence(v) for k, v in value.items() if k != 'evidence'}
    if isinstance(value, list): return [without_evidence(v) for v in value]
    return value


def build_feedback(snapshots, ledger, *, structure_assignments=None, reach_receipt=None, sources=None):
    """Inputs are immutable; source metadata is supplied by the exact-byte CLI reader."""
    finite([snapshots, ledger, structure_assignments, reach_receipt, sources])
    sources = sources or {}; assignments = structure_assignments or {}; reach = reach_receipt or {}
    records = {}; seen = {}; snapshot_sources = sources.get('snapshots', [])
    if snapshot_sources and len(snapshot_sources) != len(snapshots): raise ValueError('snapshot source count')
    def record(vid):
        if not isinstance(vid, str) or not vid: raise ValueError('invalid video id')
        return records.setdefault(vid, {'video_id': vid, 'observations': [], 'ledger_events': [], 'reach': []})
    for si, snap in enumerate(snapshots):
        src = source(snap, snapshot_sources[si] if snapshot_sources else None)
        identity = src.get('sha256') or src.get('content_fingerprint')
        fingerprint = hashlib.sha256(canonical(snap).encode()).hexdigest()
        if identity in seen:
            if seen[identity] != fingerprint: raise ValueError('source identity conflict')
            continue
        seen[identity] = fingerprint
        videos = snap.get('owned_videos', []); private = snap.get('owned_private', [])
        unique(videos, 'id'); unique(private, 'video_id')
        for vi, video in enumerate(videos):
            vid = video['id']; p = '/owned_videos/' + str(vi); snip = video.get('snippet') or {}
            statistics = video.get('statistics') or {}
            record(vid)['observations'].append({'kind': 'PUBLIC_LIFETIME', 'captured_at': snap.get('captured_at'),
                'snippet_published_at': snip.get('publishedAt'), 'privacy_at_capture': (video.get('status') or {}).get('privacyStatus'),
                'proven_public_publication_at': None, 'coverage': {'scope': 'lifetime_reported', 'effective_start': None,
                    'effective_end': None, 'data_lag': None}, 'evidence': evidence(src, p),
                'metrics': {k: metric(statistics.get(k), unit, src, p + '/statistics/' + k) for k, unit in PUBLIC.items()}})
        for pi, item in enumerate(private):
            vid = item['video_id']; p = '/owned_private/' + str(pi); basic = item.get('basic') or {}
            rows = basic.get('rows') or []; retention = item.get('retention') or {}; rr = retention.get('rows') or []
            # No row reduction: multiple rows have no declared aggregation contract.
            basic_rows = [{k: metric(row.get(k), unit, src, p + '/basic/rows/' + str(i) + '/' + k)
                           for k, unit in UNITS.items()} for i, row in enumerate(rows)]
            retention_rows = []
            for i, row in enumerate(rr):
                rp = p + '/retention/rows/' + str(i)
                retention_rows.append({k: metric(row.get(k), 'ratio', src, rp + '/' + k)
                                       for k in ('audienceWatchRatio', 'elapsedVideoTimeRatio')})
            record(vid)['observations'].append({'kind': 'PRIVATE_REQUESTED_RANGE', 'captured_at': snap.get('captured_at'),
                'coverage': {'scope': 'requested_dates_only', 'requested': copy.deepcopy(item.get('date_window')),
                    'effective_start': None, 'effective_end': None, 'data_lag': None, 'exact_checkpoint': False},
                'basic_source_status': basic.get('status'), 'basic_status': 'OBSERVED' if rows else 'UNKNOWN',
                'basic_rows': basic_rows, 'retention_source_status': retention.get('status'),
                'retention_status': 'OBSERVED' if rr else 'UNKNOWN', 'retention_rows': retention_rows,
                'reach': {k: metric((item.get('reach') or {}).get(k), unit, src, p + '/reach/' + k)
                          for k, unit in (('impressions', 'impressions'), ('ctr', 'source_unspecified'))},
                'evidence': evidence(src, p)})
    ls = source(ledger, sources.get('ledger'))
    for key, event in sorted(ledger.get('entries', {}).items()):
        if not event.get('video_id'): continue
        pointer = '/entries/' + key.replace('~', '~0').replace('/', '~1')
        record(event['video_id'])['ledger_events'].append({'uploaded_at': event.get('uploaded_at'), 'slot': event.get('slot'),
            'proven_public_publication_at': None, 'evidence': evidence(ls, pointer)})
    rs = source(reach, sources.get('reach'))
    for i, item in enumerate(reach.get('target_observations', [])):
        unique([item], 'video_id'); p = '/target_observations/' + str(i); rows = []
        for j, row in enumerate(item.get('rows', [])):
            if row.get('video_id') != item['video_id']: raise ValueError('reach row identity mismatch')
            rp = p + '/rows/' + str(j)
            rows.append({'date': row.get('date_normalized') or row.get('date'), 'report_id': row.get('report_id'),
                'impressions': metric(row.get('video_thumbnail_impressions'), 'impressions', rs, rp + '/video_thumbnail_impressions'),
                'ctr': metric(row.get('video_thumbnail_impressions_ctr'), 'ratio', rs, rp + '/video_thumbnail_impressions_ctr')})
        record(item['video_id'])['reach'].append({'status': 'OBSERVED' if rows else 'UNKNOWN', 'rows': rows,
            'aggregate_ctr': metric(item.get('aggregate_ctr'), 'ratio', rs, p + '/aggregate_ctr'),
            'coverage': copy.deepcopy(reach.get('coverage')), 'evidence': evidence(rs, p)})
    result = []
    for vid, rec in sorted(records.items()):
        rec['observations'].sort(key=canonical)
        assignment = assignments.get(vid)
        valid = isinstance(assignment, dict) and all(assignment.get(k) for k in ('structure_id', 'structure_version'))
        rec['structure_assignment'] = copy.deepcopy(assignment) if valid else None
        rec['checkpoints'] = [{'key': [vid, assignment['structure_version'], cp], 'status': 'INSUFFICIENT',
            'classification': 'INSUFFICIENT', 'reasons': ['no verified exact checkpoint coverage', 'no matched baseline']}
            for cp in ('48h', '7d')] if valid else []
        rec['classification'] = 'INSUFFICIENT'
        rec['limitations'] = ['no proven public-publication timestamp', 'no matched baseline',
            'requested date ranges do not prove effective completeness'] + ([] if valid else ['structure assignment/version unknown'])
        groups = {}
        for obs in rec['observations']:
            key = canonical([obs['kind'], obs['captured_at'], obs.get('coverage')])
            groups.setdefault(key, []).append(obs)
        rec['conflicts'] = [{'kind': group[0]['kind'], 'captured_at': group[0]['captured_at'],
            'sources': [o['evidence'] for o in group]} for group in groups.values()
            if len({canonical(without_evidence(o)) for o in group}) > 1]
        result.append(rec)
    return {'version': 'owned-feedback-v1', 'report_only': True, 'snapshot_count': len(seen),
            'video_count': len(result), 'videos': result,
            'limitations': ['descriptive observations only; no causal or market-performance claim',
                            'no new collection; no structure is updated']}


def main(argv):
    out, ledger_path, reach_path, *paths = argv
    inputs = [ledger_path, reach_path] + paths
    if not paths or Path(out).resolve() in [Path(p).resolve() for p in inputs]: raise ValueError('invalid output/input paths')
    ledger, ls = read_source(ledger_path); reach, rs = read_source(reach_path)
    pairs = [read_source(p) for p in paths]
    report = build_feedback([p[0] for p in pairs], ledger, reach_receipt=reach,
                            sources={'snapshots': [p[1] for p in pairs], 'ledger': ls, 'reach': rs})
    Path(out).write_text(canonical(report))


if __name__ == '__main__': main(sys.argv[1:])
