"""Metadata eligibility for a declared 3–4 hour research cohort, never AV approval."""
from datetime import datetime, timezone
import math

CONTRACT={'minimum_seconds':10800,'maximum_seconds':14400,
    'declared_languages':['en','en-US'],'minimum_complete_age_days':1,'maximum_complete_age_days':30,
    'basis':'PREDECLARED_RESEARCH_DESIGN_NOT_CAUSAL_EQUIVALENCE'}

def select(source, *, now=None):
    now=now or datetime.now(timezone.utc)
    cutoff=datetime.fromisoformat(source['captured_at'].replace('Z','+00:00'))
    if cutoff.tzinfo is None or not 0 <= (now-cutoff).total_seconds() <= 86400:
        raise PermissionError('CURRENT_PUBLIC_CATALOGUE_REQUIRED')
    channels={r['channel_id']:r for r in source['market_snapshots'] if r['entity_type']=='CHANNEL'}
    selected=[];exclusions=[];seen=set()
    for row in source['market_snapshots']:
        if row['entity_type']!='VIDEO':continue
        key=row['entity_id']
        if key in seen:raise PermissionError('DUPLICATE_PUBLIC_VIDEO_IDENTITY')
        seen.add(key);p=row['payload'];duration=p.get('duration_seconds');published=p.get('timestamp')
        reason=None
        if row['captured_at']!=source['captured_at'] or row['operation_id']!=source['operation_id']:
            raise PermissionError('OBSERVATION_CLOCK_OR_OPERATION_CHANGED')
        if row['channel_id'] not in channels or p.get('channel_id_public')!=row['channel_id']:
            raise PermissionError('PUBLIC_CHANNEL_LINEAGE_REQUIRED')
        if p.get('availability')!='public':reason='PUBLIC_AVAILABILITY_REQUIRED'
        elif type(duration) not in (int,float) or not math.isfinite(duration) or not 10800 <= duration <= 14400:
            reason='OUTSIDE_DECLARED_3_TO_4_HOUR_BAND'
        elif p.get('default_audio_language') not in CONTRACT['declared_languages']:
            reason='SOURCE_LANGUAGE_UNCONFIRMED_OR_DIFFERENT'
        elif type(published) not in (int,float) or not math.isfinite(published):reason='PUBLICATION_CLOCK_UNAVAILABLE'
        else:
            age=math.floor((cutoff.timestamp()-published)/86400)
            if not 1 <= age <= 30:reason='OUTSIDE_CURRENT_COMPLETE_1_TO_30_DAY_BAND'
        if reason:exclusions.append({'snapshot_id':row['snapshot_id'],'video_id':key,'reason':reason})
        else:selected.append(row)
    used={r['channel_id'] for r in selected}
    bundle={'schema_version':'1.0.0','operation_id':source['operation_id'],'captured_at':source['captured_at'],
        'snapshots':[channels[c] for c in sorted(used)]+selected}
    return bundle,{'contract':CONTRACT,'eligible_videos':len(selected),'eligible_channels':sorted(used),
        'exclusions':exclusions,'coverage':'PUBLIC_METADATA_ONLY_PENDING_AUDIOVISUAL_CONFIRMATION',
        'competitor_ctr_observed':False,'quality_authorized':False,'publication_authorized':False}
