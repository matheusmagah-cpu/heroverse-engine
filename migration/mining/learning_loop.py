"""Proposed offline composition; no network, approval or production mutation."""
import copy
import hashlib
import json


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
        'required_next_evidence':['Explicit versioned structure assignment','Verified exposure and effective metric coverage','Predeclared matched baseline'],
        'script_mutation':False,'rendered_inputs_mutation':False}
    result={'version':'learning-loop-report-v1','report_only':True,'sources':copy.deepcopy(sources),
        'capture_at':snapshot.get('captured_at'),'feedback':feedback,'references':cards,
        'pipeline':pipeline,'decision':decision,'brief':brief}
    if original!=canonical([snapshot,ledger,structure,audit,thumbnails,sources]):raise ValueError('INPUT_MUTATED')
    return result
