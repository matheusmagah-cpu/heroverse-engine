"""Route market research without inventing competitor private metrics or release authority."""
import argparse
import json
import math
from datetime import datetime,timezone
from pathlib import Path

def parse_time(text):
    value=datetime.fromisoformat(text.replace('Z','+00:00'))
    if value.tzinfo is None:raise ValueError('timestamps must include timezone')
    return value.astimezone(timezone.utc)

def route_evidence(data, now):
    current=parse_time(now)
    by_id={row['videoId']:row for row in data['raw_candidates']}
    cohort_results=[]
    for cohort in data['cohorts']:
        positives=[]
        rejected=[]
        channels=set()
        for identity in dict.fromkeys(cohort['positive_ids']):
            row=by_id.get(identity)
            if row is None:
                rejected.append({'id':identity,'reason':'MISSING_SOURCE'});continue
            published=parse_time(row['published_at'])
            age=(current-published).total_seconds()/86400
            views=row.get('viewCount')
            duration=row.get('videoDuration')
            if age<0 or age>30:
                rejected.append({'id':identity,'reason':'OUTSIDE_PRIMARY_RECENCY_WINDOW'});continue
            if type(views) is not int or views<100000:
                rejected.append({'id':identity,'reason':'PUBLIC_VIEW_FILTER_NOT_MET'});continue
            if type(duration) is not int or not 24*60<=duration<=45*60:
                rejected.append({'id':identity,'reason':'INCOMPATIBLE_DURATION_BAND'});continue
            channels.add(row['channelId'])
            positives.append({'id':identity,'channel_id':row['channelId'],
              'age_days':round(age,3),'views':views,
              'average_views_per_day':round(views/age,2) if age else None,
              'provider_vph':row.get('vph'),
              'measured_acceleration':None,'competitor_ctr':None,'competitor_retention':None})
        cohort_results.append({'cohort_id':cohort['id'],'positive_candidates':positives,
             'distinct_channel_ids':len(channels),'ownership_independence_verified':False,
             'rejected':rejected,'triage_ready':len(channels)>=3,
             'full_audiovisual_review_complete':False})
    own=data.get('own_baseline') or {}
    retention=own.get('retention')
    ctr=own.get('ctr_ratio')
    own_retention=(own.get('status')=='VALIDATED' and type(own.get('views')) is int
        and own['views']>=30 and type(retention) in (int,float)
        and math.isfinite(retention) and 0<=retention<=1
        and type(ctr) in (int,float) and math.isfinite(ctr) and 0<=ctr<=1)
    triage=any(c['triage_ready'] for c in cohort_results)
    return {'schema_version':'1.0.0','policy':'MARKET_FIRST_WITH_OWN_FEEDBACK',
      'observed_at':now,'own_creative_metrics_sufficient':own_retention,
      'own_missing_does_not_pause_market_research':True,
      'action':'REVIEW_MARKET_AUDIOVISUAL_AND_COUNTEREXAMPLES' if triage else 'EXPAND_COMPARABLE_MARKET_DISCOVERY',
      'market_cohorts':cohort_results,
      'experiment_priority':'TITLE_THUMBNAIL_PROMISE_ALIGNED_WITH_FIRST_30_SECONDS',
      'required_before_style_selection':['actual audiovisual review','matched median and weak comparators',
            'independence/provenance check','substantive original contribution'],
      'required_before_measured_velocity_claim':['two dated view-count snapshots'],
      'competitor_ctr_known':False,'competitor_retention_known':False,
      'winner_selected':False,'forecast_calibrated':False,
      'production_ready':False,'release_authority':False,'publication_performed':False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('dataset')
    parser.add_argument('--now',required=True)
    args=parser.parse_args()
    data=json.loads(Path(args.dataset).read_text())
    print(json.dumps(route_evidence(data,args.now),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
