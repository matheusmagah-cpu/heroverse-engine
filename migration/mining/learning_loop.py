"""Proposed offline composition; no network, approval or production mutation."""
import copy
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n'


def capture_existing(videos, per_video, *, captured_at, start, end, analytics_status):
    """Normalize only responses already collected by goal_report, retaining nulls."""
    owned=[]
    for video in videos:
        snippet=video.get('snippet') or {}
        owned.append({'id':video['id'],'snippet':{'publishedAt':snippet.get('publishedAt')},
            'status':{'privacyStatus':(video.get('status') or {}).get('privacyStatus')},
            'statistics':copy.deepcopy(video.get('statistics') or {})})
    private=[]
    for vid,row in sorted(per_video.items()):
        if len(row)!=5:raise ValueError('PER_VIDEO_SCHEMA')
        kind,minutes,views,pct,subscribers=row
        private.append({'video_id':vid,'date_window':{'start':start,'end':end},
            'basic':{'status':analytics_status,'rows':[{'estimatedMinutesWatched':minutes,
                'views':views,'averageViewPercentage':pct,'subscribersGained':subscribers}]},
            'retention':{'status':'UNAVAILABLE','rows':[]},'reach':{'impressions':None,'ctr':None}})
    return {'version':'owned-existing-capture-v1','captured_at':captured_at,
        'owned_videos':sorted(owned,key=lambda row:row['id']),'owned_private':private,
        'analytics_source_status':analytics_status,
        'coverage':{'public_list_limit':50,'analytics_list_limit':200,
            'requested_start':start,'requested_end':end,'effective_complete_through':None,
            'exact_checkpoint':False},'additional_api_calls':0}


def compose(snapshot,ledger,structure,audit,thumbnails,*,feedback_builder,card_builder,sources):
    """Injected existing adapters keep this module pure and mockable."""
    original=canonical([snapshot,ledger,structure,audit,thumbnails,sources])
    feedback=feedback_builder([snapshot],ledger,sources={'snapshots':[sources['snapshot']],
        'ledger':sources['ledger']})
    cards=card_builder(structure,audit,thumbnails,sources={key:sources[key]
        for key in ('structure','structure_audit','thumbnails')})
    reasons=['NO_VERIFIED_EXACT_CHECKPOINT','NO_MATCHED_BASELINE','NO_VERSIONED_OWNED_STRUCTURE_ASSIGNMENT']
    public={v['id']:(v.get('status') or {}).get('privacyStatus') for v in snapshot.get('owned_videos',[])}
    pipeline=[]
    for key,event in sorted(ledger.get('entries',{}).items()):
        vid=event.get('video_id')
        if not vid:continue
        privacy=public.get(vid)
        pipeline.append({'ledger_key':key,'video_id':vid,'uploaded':True,
            'public_observation':privacy=='public' if privacy is not None else None,
            'privacy_observed_at':snapshot.get('captured_at') if privacy is not None else None,
            'public_since':None})
    if any(c.get('conflicts') for c in cards.get('cards',[])):reasons.append('REFERENCE_SOURCE_CONFLICTS')
    decision={'evidence_decision':'HOLD','plan_action':'KEEP_EXISTING_PENDING_EVIDENCE',
        'reasons':reasons,'causal_claim':None,'performance_classification':'INSUFFICIENT'}
    identity=hashlib.sha256(canonical({'sources':sources,'decision':decision}).encode()).hexdigest()
    brief={'id':identity,'status':'EVIDENCE_INSUFFICIENT','structure_id':structure.get('id'),
        'structure_version':structure.get('version'),'reference_report_only':True,
        'facts':['Reference cohort and evidence retain the existing adapter provenance.'],
        'unknowns':reasons,'hypotheses':[], 'single_variable_experiment':None,
        'source_records':copy.deepcopy(sources),
        'reference_cohort_counts':copy.deepcopy(cards.get('cohort_counts',{})),
        'reference_card_ids':[c.get('video_id') for c in cards.get('cards',[])],
        'required_next_evidence':['Explicit versioned structure assignment','Verified exposure and effective metric coverage','Predeclared matched baseline'],
        'script_mutation':False,'rendered_inputs_mutation':False}
    result={'version':'learning-loop-report-v1','report_only':True,'sources':copy.deepcopy(sources),
        'capture_at':snapshot.get('captured_at'),'feedback':feedback,'references':cards,
        'pipeline':pipeline,'decision':decision,'brief':brief}
    if original!=canonical([snapshot,ledger,structure,audit,thumbnails,sources]):raise ValueError('INPUT_MUTATED')
    return result


def immutable_write(path, data):
    from pathlib import Path
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=data:raise ValueError('CONTENT_ADDRESS_COLLISION')
    path.write_bytes(data)


def safe_output(root, path):
    root=Path(root).resolve();path=Path(path)
    try:path.resolve().relative_to(root)
    except ValueError:raise ValueError('OUTPUT_ESCAPES_ROOT') from None
    if path.is_symlink():raise ValueError('OUTPUT_SYMLINK')


def save_capture(snapshot, out_dir):
    from pathlib import Path
    out=Path(out_dir);data=canonical(snapshot).encode();sha=hashlib.sha256(data).hexdigest()
    path=out/'captures'/f'{sha}.json'
    safe_output(out,path);safe_output(out,out/'latest-capture.json')
    immutable_write(path,data)
    (out/'latest-capture.json').write_text(canonical({'path':str(path),'sha256':sha}))
    return path


def run(out_dir, ledger_path, structure_path, audit_path, thumbnails_path):
    from pathlib import Path
    import gzip
    from owned_feedback import build_feedback
    from video_analysis_card import build_report
    out=Path(out_dir)
    safe_output(out,out/'latest-capture.json')
    capture=json.loads((out/'latest-capture.json').read_bytes())
    try:Path(capture['path']).resolve().relative_to((out/'captures').resolve())
    except ValueError:raise ValueError('CAPTURE_OUTSIDE_CAPTURE_DIRECTORY') from None
    for path in (ledger_path,structure_path,audit_path,thumbnails_path):
        if Path(path).resolve().is_relative_to(out.resolve()):raise ValueError('INPUT_INSIDE_OUTPUT_ROOT')
    writes=[]
    paths={'snapshot':capture['path'],'ledger':ledger_path,'structure':structure_path,
        'structure_audit':audit_path,'thumbnails':thumbnails_path}
    data={};sources={}
    for key,path in paths.items():
        raw=Path(path).read_bytes();sha=hashlib.sha256(raw).hexdigest()
        if key=='snapshot' and sha!=capture['sha256']:raise ValueError('CAPTURE_HASH_MISMATCH')
        stored=out/'sources'/f'{sha}.json';writes.append((stored,raw))
        data[key]=json.loads(raw);sources[key]={'path':str(stored),'origin_path':str(path),
            'sha256':sha,'hash_method':'EXACT_FILE_BYTES'}
    result=compose(data['snapshot'],data['ledger'],data['structure'],data['structure_audit'],data['thumbnails'],
        feedback_builder=build_feedback,card_builder=build_report,sources=sources)
    raw=canonical(result).encode();sha=hashlib.sha256(raw).hexdigest()
    compressed=gzip.compress(raw,mtime=0);report_path=out/'reports'/f'{sha}.json.gz'
    writes.append((report_path,compressed))
    brief_data=canonical(result['brief']).encode();brief_path=out/'briefs'/f"{result['brief']['id']}.json"
    writes.append((brief_path,brief_data))
    receipt={'version':'learning-loop-receipt-v1','status':'REPORT_BUILT','report_only':True,
        'captured_at':result['capture_at'],'decision':result['decision'],
        'report':{'path':str(report_path),'sha256':hashlib.sha256(compressed).hexdigest(),'uncompressed_sha256':sha},
        'brief':{'path':str(brief_path),'sha256':hashlib.sha256(brief_data).hexdigest()},
        'capture':capture,'additional_api_calls':0,'source_records':sources}
    for path,content in writes:
        safe_output(out,path)
        if path.exists() and path.read_bytes()!=content:raise ValueError('CONTENT_ADDRESS_COLLISION')
    safe_output(out,out/'latest.json')
    for path,content in writes:immutable_write(path,content)
    (out/'latest.json').write_text(canonical(receipt));return receipt


if __name__=='__main__':
    import sys
    print(canonical(run(*sys.argv[1:])))
