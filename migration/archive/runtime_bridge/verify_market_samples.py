"""Reopen saved provider receipts; this verifies provenance, never native-media review."""
import hashlib,json
from pathlib import Path
import sys
from gemini_public_av import canonical,digest,validate_report,build_request

def require(condition,code):
    if not condition:raise PermissionError(code)

def modality_concerns(report):
    """Missing supplied audio is not evidence of intentional source silence."""
    limitations=list(report.get('limitations',[]))
    for segment in report.get('segments',[]):limitations.extend(segment.get('limitations',[]))
    missing=('no audio track provided','audio not provided','audio was not received')
    if report.get('audio_received') is True and any(any(term in str(value).lower() for term in missing) for value in limitations):
        return ['AUDIO_INPUT_CLAIM_CONTRADICTION_NOT_SOURCE_SILENCE_EVIDENCE']
    return []

def verify(summary,plan,read,*,request_day='2026-10-14'):
    accepted=[]; gaps=[]; concerns=[]
    identities={v['video_id']:v for v in plan['videos']}
    expected_windows={(v['video_id'],tuple(w)) for v in plan['videos'] for w in v['windows']}
    observed_windows=[(s['video_id'],tuple(s['window'])) for s in summary['samples']]
    require(len(observed_windows)==len(set(observed_windows)),'DUPLICATE_SAMPLE_WINDOW')
    require(set(observed_windows)<=expected_windows,'UNPLANNED_SAMPLE_WINDOW')
    require(summary['source_binding']==plan['source_binding'],'CATALOGUE_BINDING_CHANGED')
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
        binding={'source':source,'request_hash':expected}
        if receipt.get('recovery') is not None:
            recovery=receipt['recovery']
            prior_path='migration/evidence/public-av-'+recovery['prior_key'].split(':')[1]+'.json'
            prior_raw=read(prior_path);prior=json.loads(prior_raw)
            require(hashlib.sha256(prior_raw).hexdigest()==recovery['prior_receipt_sha256'],'PRIOR_RECOVERY_RECEIPT_CHANGED')
            require(prior['failure_code']=='HTTP_503_UNAVAILABLE' and prior['status']=='FAILED_NO_AUTOMATIC_RETRY'
                and prior['source']==source and prior['request_hash']==expected and prior['window']==sample['window']
                and prior['key']=='public-av:'+digest(binding),'EXACT_TRANSIENT_RECOVERY_LINEAGE_REQUIRED')
            require(recovery['attempt_id']=='20261014-owner-market-503-recovery-1'
                and recovery['owner_request']=='2026-10-14T13:38:01-03:00:resolve-problems','OWNER_RECOVERY_CHANGED')
            binding['recovery']=recovery
        require(receipt['request_hash']==expected and receipt['key']=='public-av:'+digest(binding),'REQUEST_HASH_CHANGED')
        for flag in ('quality_authorized','production_authorized','publication_authorized'):
            require(receipt[flag] is False,'SAMPLE_CANNOT_GRANT_AUTHORITY')
        require(receipt['review_status']=='NOT_REVIEWED','FALSE_REVIEW_UPGRADE')
        validate_report(receipt['report'],source,tuple(sample['window']),refinement=True)
        concerns.extend({'path':path,'video_id':source['video_id'],'window':sample['window'],'code':code}
            for code in modality_concerns(receipt['report']))
        accepted.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'video_id':source['video_id'],
            'window':sample['window'],'sample_fps':2,'segment_count':len(receipt['report']['segments'])})
    attempted=set(observed_windows)
    for item in plan['videos']:
        gaps.extend({'video_id':item['video_id'],'window':w,'status':'NOT_STARTED_AFTER_PROVIDER_FAILURE'}
            for w in item['windows'] if (item['video_id'],tuple(w)) not in attempted)
    return {'status':'SAVED_SAMPLE_PROVENANCE_VERIFIED_WITH_GAPS' if gaps else
            'COMPLETE_SAMPLE_PROVENANCE_WITH_UNRESOLVED_CONTENT_CONCERNS' if concerns else
            'COMPLETE_PLANNED_SAMPLES_PROVENANCE_VERIFIED',
        'verified_samples':accepted,'gaps':gaps,
        'content_concerns':concerns,'content_review_required':bool(concerns),
        'verified_sample_seconds':sum(w['window'][1]-w['window'][0] for w in accepted),
        'coverage':'SAMPLED_NOT_FULL_VIDEO','provider_calls':0,'native_frames_independently_reviewed':False,
        'verbatim_transcript_available':False,'quality_authorized':False,'publication_authorized':False}

if __name__=='__main__':
    root=Path(sys.argv[1]);summary=json.loads((root/'market-summary.json').read_bytes())
    plan=json.loads((root/'market-av-plan-20261014.json').read_bytes())
    result=verify(summary,plan,lambda p:(root/'receipts'/Path(p).name).read_bytes())
    (root/'market-sample-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('verified_samples','gaps')}))
