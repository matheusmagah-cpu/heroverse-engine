"""Reopen saved provider receipts; this verifies provenance, never native-media review."""
import hashlib,json
from pathlib import Path
import sys
from gemini_public_av import canonical,digest,validate_report,build_request

def require(condition,code):
    if not condition:raise PermissionError(code)

def verify(summary,plan,read,*,request_day='2026-10-14'):
    accepted=[]; gaps=[]
    identities={v['video_id']:v for v in plan['videos']}
    for sample in summary['samples']:
        if sample['status']!='WINDOW_AWAITING_AV_REVIEW':
            gaps.append({'video_id':sample['video_id'],'window':sample['window'],'status':sample['status']});continue
        path='migration/evidence/public-av-'+sample['key'].split(':')[1]+'.json'
        raw=read(path);receipt=json.loads(raw);source=receipt['source'];item=identities[sample['video_id']]
        require(source=={'video_id':sample['video_id'],'duration_seconds':item['duration_seconds'],'visibility':'PUBLIC'},'SOURCE_CHANGED')
        require(receipt['key']==sample['key'] and receipt['window']==sample['window'],'WINDOW_OR_KEY_CHANGED')
        require(receipt['status']=='WINDOW_AWAITING_AV_REVIEW' and receipt['finish_reasons']==['STOP'],'COMPLETE_WINDOW_REQUIRED')
        require(receipt['sample_fps']==2 and receipt['refinement'] is True,'DENSE_SAMPLE_REQUIRED')
        require(receipt['research_context']=='CHRISTIAN_REST_MUSIC','MUSIC_CONTEXT_CHANGED')
        require(receipt['response_sha256']==digest(receipt['provider_response']),'PROVIDER_RESPONSE_CHANGED')
        payload=build_request(source,today=request_day,window=tuple(sample['window']),refinement=True,
            research_context='CHRISTIAN_REST_MUSIC')
        expected=digest({'model':receipt['model'],'payload':payload})
        require(receipt['request_hash']==expected and receipt['key']=='public-av:'+digest({'source':source,'request_hash':expected}),
            'REQUEST_HASH_CHANGED')
        for flag in ('quality_authorized','production_authorized','publication_authorized'):
            require(receipt[flag] is False,'SAMPLE_CANNOT_GRANT_AUTHORITY')
        require(receipt['review_status']=='NOT_REVIEWED','FALSE_REVIEW_UPGRADE')
        validate_report(receipt['report'],source,tuple(sample['window']),refinement=True)
        accepted.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'video_id':source['video_id'],
            'window':sample['window'],'sample_fps':2,'segment_count':len(receipt['report']['segments'])})
    attempted={(s['video_id'],tuple(s['window'])) for s in summary['samples']}
    for item in plan['videos']:
        gaps.extend({'video_id':item['video_id'],'window':w,'status':'NOT_STARTED_AFTER_PROVIDER_FAILURE'}
            for w in item['windows'] if (item['video_id'],tuple(w)) not in attempted)
    return {'status':'SAVED_SAMPLE_PROVENANCE_VERIFIED_WITH_GAPS','verified_samples':accepted,'gaps':gaps,
        'verified_sample_seconds':sum(w['window'][1]-w['window'][0] for w in accepted),
        'coverage':'SAMPLED_NOT_FULL_VIDEO','provider_calls':0,'native_frames_independently_reviewed':False,
        'verbatim_transcript_available':False,'quality_authorized':False,'publication_authorized':False}

if __name__=='__main__':
    root=Path(sys.argv[1]);summary=json.loads((root/'market-summary.json').read_bytes())
    plan=json.loads((root/'market-av-plan-20261014.json').read_bytes())
    result=verify(summary,plan,lambda p:(root/'receipts'/Path(p).name).read_bytes())
    (root/'market-sample-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('verified_samples','gaps')}))
