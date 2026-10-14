"""Exactly one owner-requested transient recovery, then the unstarted source, serially."""
import hashlib,json,os,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gemini_public_av import analyze,digest
from observe_public_av import ExistingObserverLedger,POLICY
from observe_market_av import validate_plan

PRIOR=Path('migration/evidence/public-av-31a76077e12ef7fc9e60308344cdfbfbf53907ead97216ea9de7abd569f8ff24.json')
PREVIOUS=Path('migration/evidence/market-av-38593822345.json')
PLAN=Path('migration/evidence/market-av-plan-20261014.json')

def main():
    if os.environ.get('GITHUB_REPOSITORY')!='matheusmagah-cpu/heroverse-engine':
        raise PermissionError('REPOSITORY_MISMATCH')
    request=json.loads(Path('migration/evidence/focused-refinement-request.json').read_bytes())
    if request.get('request_id')!='20261014-owner-market-503-recovery-1':
        raise PermissionError('EXACT_OWNER_RECOVERY_REQUEST_REQUIRED')
    plan_raw=PLAN.read_bytes();plan=json.loads(plan_raw)
    if hashlib.sha256(plan_raw).hexdigest()!=request['plan_sha256']:
        raise PermissionError('ORIGINAL_PLAN_CHANGED')
    validate_plan(plan,Path(plan['source_binding']['path']).read_bytes())
    raw=PRIOR.read_bytes();prior=json.loads(raw);prior_hash=hashlib.sha256(raw).hexdigest()
    if request['prior_receipt_sha256']!=prior_hash:
        raise PermissionError('PRIOR_FAILURE_CHANGED')
    ledger=ExistingObserverLedger('cloud-evidence/quota-ledger.sqlite3',os.environ['GITHUB_RUN_ID'])
    with sqlite3.connect(ledger.db) as c:
        row=c.execute('SELECT state,receipt_path,receipt_hash FROM public_av_reservations WHERE key=?',
            (prior['key'],)).fetchone()
        if row!=('COMPLETED',PRIOR.as_posix(),prior_hash):
            raise PermissionError('DURABLE_PRIOR_FAILURE_REQUIRED')
        used=c.execute('SELECT COALESCE(SUM(seconds),0) FROM public_av_reservations WHERE day=?',
            (datetime.now(timezone.utc).date().isoformat(),)).fetchone()[0]
        if used+70>28800:raise PermissionError('BOUNDED_RECOVERY_CAPACITY_UNAVAILABLE')
    policy=json.loads(POLICY.read_bytes());key=os.environ.get('HERO_GEMINI_API_KEY','')
    previous=json.loads(PREVIOUS.read_bytes());results=[]
    for sample in previous['samples']:
        if sample['status']!='WINDOW_AWAITING_AV_REVIEW':continue
        saved=Path('migration/evidence')/('public-av-'+sample['key'].split(':')[1]+'.json')
        report=json.loads(saved.read_bytes())
        if report['key']!=sample['key'] or report['window']!=sample['window']:
            raise PermissionError('SAVED_SUCCESS_CHANGED')
        results.append(sample)
    recovery={'attempt_id':request['request_id'],'owner_request':request['owner_request'],
        'prior_receipt':prior,'prior_receipt_sha256':prior_hash}
    recovered=analyze(prior['source'],api_key=key,policy=policy,reserve=ledger.reserve,persist=ledger.persist,
        window=tuple(prior['window']),refinement=True,research_context='CHRISTIAN_REST_MUSIC',recovery=recovery)
    results.append({'video_id':prior['source']['video_id'],'window':prior['window'],'key':recovered['key'],
        'status':recovered['status'],'evidence_class':recovered['evidence_class']})
    complete=recovered['status']=='WINDOW_AWAITING_AV_REVIEW'
    if complete:
        item=next(v for v in plan['videos'] if v['video_id']=='AgkqbwJ_P1Y')
        source={'video_id':item['video_id'],'duration_seconds':item['duration_seconds'],'visibility':'PUBLIC'}
        for window in item['windows']:
            receipt=analyze(source,api_key=key,policy=policy,reserve=ledger.reserve,persist=ledger.persist,
                window=tuple(window),refinement=True,research_context='CHRISTIAN_REST_MUSIC')
            results.append({'video_id':source['video_id'],'window':window,'key':receipt['key'],
                'status':receipt['status'],'evidence_class':receipt['evidence_class']})
            if receipt['status']!='WINDOW_AWAITING_AV_REVIEW':complete=False;break
    out=Path('migration/evidence')/('market-av-'+os.environ['GITHUB_RUN_ID']+'.json')
    summary={**previous,'samples':results,'status':'SAMPLES_AWAITING_REVIEW' if complete else 'STOPPED_AT_FIRST_FAILED_SAMPLE',
        'owner_recovery':{'prior_receipt_path':PRIOR.as_posix(),'prior_receipt_sha256':prior_hash,
            'request_id':request['request_id'],'maximum_new_requested_seconds':70},
        'saved_samples_reused':11,'publication_authorized':False}
    out.write_text(json.dumps(summary,sort_keys=True)+'\n')
    ledger.checkpoint('Persist owner-authorized one-shot recovery and sequential unstarted market source')
    print(json.dumps({'status':summary['status'],'samples':len(results),'saved_samples_reused':11,
        'publication_authorized':False}))
    return 0 if complete else 2

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print(json.dumps({'status':'BLOCKED','exception_type':type(e).__name__,
            'code':str(e) if isinstance(e,PermissionError) else 'DETAILS_REDACTED','publication_authorized':False}));sys.exit(2)
