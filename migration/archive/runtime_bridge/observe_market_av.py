"""One sequential sampled market stage through the existing observer and ledger."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gemini_public_av import analyze
from observe_public_av import ExistingObserverLedger,POLICY

def validate_plan(plan,raw,*,now=None):
    if hashlib.sha256(raw).hexdigest()!=plan['source_binding']['sha256']:
        raise PermissionError('MARKET_AV_SOURCE_HASH_CHANGED')
    evidence=json.loads(raw);now=now or datetime.now(timezone.utc)
    captured=datetime.fromisoformat(evidence['captured_at'].replace('Z','+00:00'))
    if captured.tzinfo is None or not 0 <= (now-captured).total_seconds() <= 86400:
        raise PermissionError('FRESH_MARKET_IDENTITY_REQUIRED')
    if plan.get('publication_authorized') is not False or plan.get('coverage')!='SAMPLED_NOT_FULL_VIDEO':
        raise PermissionError('MARKET_SAMPLE_AUTHORITY_BOUNDARY_REQUIRED')
    rows={r['entity_id']:r for r in evidence['market_snapshots'] if r['entity_type']=='VIDEO'}
    selected=plan['videos'];seen=set();seconds=0
    discovery=plan.get('purpose')=='UNQUALIFIED_DISCOVERY_AV_NO_LANGUAGE_OR_COHORT_UPGRADE'
    third=plan.get('purpose')=='THIRD_METADATA_WINNER_SAMPLED_NOT_NATIVE_APPROVED'
    if third and (len(selected)!=1 or selected[0].get('video_id')!='VA3qvxoZr4Q'
            or selected[0].get('channel_id')!='UCemzpRC1q9xqvYKnTvWeQ3A'
            or selected[0].get('role')!='METADATA_WINNER_AWAITING_NATIVE_AV'
            or plan.get('opening_seconds')!=38 or plan.get('qualified_winner') is not False):
        raise PermissionError('EXACT_THIRD_METADATA_REFERENCE_REQUIRED')
    if discovery and (len(selected)!=1 or selected[0].get('video_id')!='yY9dDJCLfHU'
            or selected[0].get('channel_id')!='UCAOiKo0Ad8F_eRdxgpQSW_A'
            or selected[0].get('role')!='EXPLORATORY_UNQUALIFIED_LANGUAGE_UNKNOWN'
            or plan.get('qualified_winner') is not False):
        raise PermissionError('EXACT_UNQUALIFIED_DISCOVERY_REQUIRED')
    if not 1<=len(selected)<=5:raise PermissionError('BOUNDED_MARKET_SAMPLE_COUNT_REQUIRED')
    for item in selected:
        vid=item['video_id']
        if vid in seen or vid not in rows:raise PermissionError('EXACT_MARKET_VIDEO_REQUIRED')
        seen.add(vid);row=rows[vid];p=row['payload'];duration=p.get('duration_seconds')
        if (p.get('availability')!='public' or (not discovery and p.get('default_audio_language') not in ('en','en-US'))
                or type(duration) not in (int,float) or not 10800<=duration<=14400
                or duration!=int(duration) or item['duration_seconds']!=duration
                or item['channel_id']!=row['channel_id']):
            raise PermissionError('MATCHED_PUBLIC_SOURCE_REQUIRED')
        expected=[[0,38 if third else 40],[int(duration)//2,int(duration)//2+10],[int(duration)-10,int(duration)]]
        if item['windows']!=expected:raise PermissionError('EXACT_SAMPLE_WINDOWS_REQUIRED')
        seconds+=58 if third else 60
    if seconds>300 or plan.get('requested_seconds')!=seconds:
        raise PermissionError('MARKET_STAGE_BUDGET_CHANGED')
    return seconds

def execute(plan,ledger,key,policy,*,analyzer=analyze):
    results=[]
    for item in plan['videos']:
        source={k:item[k] for k in ('video_id','duration_seconds')};source['visibility']='PUBLIC'
        for start,end in item['windows']:
            receipt=analyzer(source,api_key=key,policy=policy,reserve=ledger.reserve,persist=ledger.persist,
                window=(start,end),refinement=True,research_context='CHRISTIAN_REST_MUSIC')
            results.append({'video_id':item['video_id'],'window':[start,end],'key':receipt['key'],
                'status':receipt['status'],'evidence_class':receipt['evidence_class']})
            if receipt['status']!='WINDOW_AWAITING_AV_REVIEW':return results,False
    return results,True

def main():
    if os.environ.get('GITHUB_REPOSITORY')!='matheusmagah-cpu/heroverse-engine':
        raise PermissionError('REPOSITORY_MISMATCH')
    request=json.loads(Path('migration/evidence/focused-refinement-request.json').read_bytes())
    discovery=request.get('mode')=='MARKET_AV_DISCOVERY_ONLY'
    third=request.get('mode')=='THIRD_METADATA_REFERENCE_AV_ONLY'
    if third and request.get('request_id')!='20261014-third-metadata-reference-av-v1':
        raise PermissionError('EXACT_THIRD_REFERENCE_OWNER_REQUEST_REQUIRED')
    if discovery and request.get('request_id')!='20261014-holy-moments-av-discovery-v1':
        raise PermissionError('EXACT_DISCOVERY_OWNER_REQUEST_REQUIRED')
    plan_path=Path('migration/evidence/market-av-third-reference-plan-20261014.json' if third else
        'migration/evidence/market-av-discovery-plan-20261014.json' if discovery
        else 'migration/evidence/market-av-plan-20261014.json');plan_raw=plan_path.read_bytes()
    plan=json.loads(plan_raw)
    if discovery != (plan.get('purpose')=='UNQUALIFIED_DISCOVERY_AV_NO_LANGUAGE_OR_COHORT_UPGRADE'):
        raise PermissionError('DISCOVERY_SCOPE_CHANGED')
    if third != (plan.get('purpose')=='THIRD_METADATA_WINNER_SAMPLED_NOT_NATIVE_APPROVED'):
        raise PermissionError('THIRD_REFERENCE_SCOPE_CHANGED')
    if request.get('plan_sha256')!=hashlib.sha256(plan_raw).hexdigest():
        raise PermissionError('OWNER_PLAN_BINDING_CHANGED')
    source_path=Path(plan['source_binding']['path'])
    expected_catalogue='migration/evidence/observer-38624074018.json' if third else 'migration/evidence/observer-38604686944.json' if discovery else 'migration/evidence/observer-38591891691.json'
    if source_path.as_posix()!=expected_catalogue:
        raise PermissionError('EXACT_OFFICIAL_CATALOGUE_REQUIRED')
    seconds=validate_plan(plan,source_path.read_bytes())
    ledger=ExistingObserverLedger('cloud-evidence/quota-ledger.sqlite3',os.environ['GITHUB_RUN_ID'])
    with sqlite3.connect(ledger.db) as c:
        used=c.execute('SELECT COALESCE(SUM(seconds),0) FROM public_av_reservations WHERE day=?',
            (datetime.now(timezone.utc).date().isoformat(),)).fetchone()[0]
        if used+seconds>28800:raise PermissionError('LOCAL_MARKET_STAGE_BUDGET_UNAVAILABLE')
    results,complete=execute(plan,ledger,os.environ.get('HERO_GEMINI_API_KEY',''),json.loads(POLICY.read_bytes()))
    out=Path('migration/evidence')/('market-av-'+os.environ['GITHUB_RUN_ID']+'.json')
    summary={'status':'SAMPLES_AWAITING_REVIEW' if complete else 'STOPPED_AT_FIRST_FAILED_SAMPLE',
        'plan_sha256':hashlib.sha256(plan_raw).hexdigest(),'source_binding':plan['source_binding'],
        'coverage':'SAMPLED_NOT_FULL_VIDEO','requested_seconds':seconds,'samples':results,
        'evidence_class':'MODEL_REPORTED_AV_NOT_INDEPENDENTLY_VERIFIED',
        'review_status':'NOT_REVIEWED','quality_authorized':False,'production_authorized':False,
        'publication_authorized':False,'vidiq_credits_used':0}
    if discovery:
        summary.update(purpose=plan['purpose'],qualified_winner=False,
            declared_audio_language=None,language_evidence_status='UNDECLARED_NOT_UPGRADED_FROM_TITLE')
    if third:
        summary.update(purpose=plan['purpose'],qualified_winner=False,
            metadata_cohort_winner=True,native_av_review_qualified=False)
    out.write_text(json.dumps(summary,sort_keys=True)+'\n')
    ledger.checkpoint('Persist sampled market audiovisual stage without granting production authority')
    print(json.dumps({'status':summary['status'],'samples':len(results),'publication_authorized':False}))
    return 0 if complete else 2

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:
        print(json.dumps({'status':'BLOCKED','exception_type':type(error).__name__,
            'code':str(error) if isinstance(error,PermissionError) else 'DETAILS_REDACTED',
            'publication_authorized':False}));sys.exit(2)
