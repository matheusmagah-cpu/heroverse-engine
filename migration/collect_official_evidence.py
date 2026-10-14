"""Bounded read-only evidence collection using the restored HeroVerse modules.

This is a migration observation task, never a manager, publisher or learned rule.
Secrets stay in memory. Only sanitized observations and the original quota ledger
continuation are exported. No candidate media is downloaded.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
import zipfile

SOURCE_SHA='fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10'
SNAPSHOT_SHA='bbd5b7b9daa76b5ac1754eba6dc135e75f15bbeb4e72a79a0a8891c9fd64d790'
CHANNEL='UCuMF6pJQkyMzaVoAxFL86yA'
PRAYER_REFERENCES=['UC_h1E8wccvaX1gTtx4VsYXw','UC2d7chxFUVEurYmI4yfmTlQ','UC5spXp9tnfnAuRQKgZgw2tg']
PRIVATE_UNKNOWN=['IMPRESSIONS','CTR','INTRO_RETENTION','AVERAGE_VIEW_DURATION','WATCH_HOURS','SUBSCRIBERS_GAINED','REVENUE','RPM']
MAX_DATA_CALLS=40
DISCOVERY_IDS=('TYCZe65GxdQ','ZGiGg9O09yU','beIMxaH7YuI')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf8') as out:json.dump(value,out,ensure_ascii=False,sort_keys=True,allow_nan=False)

def restore(archive,digest,destination):
    if sha(archive.read_bytes())!=digest:raise PermissionError('ARCHIVE_IDENTITY_MISMATCH')
    with zipfile.ZipFile(archive) as z:
        for m in z.infolist():
            p=PurePosixPath(m.filename)
            if p.is_absolute() or '..' in p.parts or ((m.external_attr>>16)&0o170000)==0o120000:
                raise PermissionError('UNSAFE_ARCHIVE_MEMBER')
        z.extractall(destination)

def duration(value):
    m=re.fullmatch(r'P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?',value or '')
    if not m:return None
    d,h,mn,s=[float(x or 0) for x in m.groups()]
    return d*86400+h*3600+mn*60+s

def stratum(seconds):
    if seconds is None or seconds<=180:return 'FORMAT_UNCONFIRMED'
    if seconds<=600:return '181_600_SECONDS'
    if seconds<=1800:return '601_1800_SECONDS'
    if seconds<=3600:return '1801_3600_SECONDS'
    return '3601_PLUS_SECONDS'

def exact_owned(response):
    items=response.get('items',[])
    if len(items)!=1 or items[0].get('id')!=CHANNEL:raise PermissionError('OWNED_CHANNEL_MISMATCH')
    return items[0]

def safe_error(error):
    status=getattr(getattr(error,'resp',None),'status',None)
    return {'exception_type':type(error).__name__,'http_status':status,'details_redacted':True}

def exportable(value):
    if isinstance(value,dict):
        return {k:exportable(v) for k,v in value.items()
                if k not in {'nextPageToken','downloadUrl','token','refresh_token','client_secret','access_token','Authorization'}}
    if isinstance(value,list):return [exportable(v) for v in value]
    return value

def report_rows(response):
    names=[h['name'] for h in response.get('columnHeaders',[])]
    return [dict(zip(names,row,strict=True)) for row in response.get('rows',[])]

def public_projection(video):
    public=video.get('status',{}).get('privacyStatus')=='public'
    return {'availability':'public' if public else 'unavailable','public_fields_only':public,
            'webpage_url':'https://www.youtube.com/watch?v='+video['id']}

def snapshot(operation,captured,channel,entity,identity,payload):
    body=json.dumps([operation,channel,entity,identity,captured],separators=(',',':'))
    return {'schema_version':'1.0.0','snapshot_id':'snap-'+sha(body.encode())[:24],
        'operation_id':operation,'channel_id':channel,'entity_type':entity,'entity_id':identity,
        'collection_status':'COMPLETE','captured_at':captured,
        'source_uri':'https://www.youtube.com/'+('watch?v='+identity if entity=='VIDEO' else 'channel/'+channel),
        'collector':{'name':'YouTube Data API','version':'v3-bounded-migration-1','mode':'PUBLIC_METADATA_NO_MEDIA'},
        'evidence_class':'OBSERVED','payload':payload,'unavailable_metrics':PRIVATE_UNKNOWN,'error':None}

def collect(root,export,*,health_only=False,candidate_only=False):
    from oauth_health import observe_refresh,identity_health
    raw=os.environ.get('HERO_YT_AUTHORIZED_USER_JSON','')
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from hero_engine.google_api_runtime import build_authorized_service,execute_google_request,GoogleOperationDeadline
    from hero_engine.phase6_quota import reserve_general_quota,consume_general_quota
    class BoundedRequest(Request):
        def __call__(self,*a,**kw):kw['timeout']=20;return super().__call__(*a,**kw)
    def renew(value):
        credentials=Credentials.from_authorized_user_info(json.loads(value))
        credentials.refresh(BoundedRequest())
        return credentials
    credentials,health=observe_refresh(raw,renew);raw=None
    write(export/'oauth-health.json',health)
    if credentials is None:raise PermissionError(health['failure_code'])
    youtube=build_authorized_service('youtube','v3',credentials=credentials,request_timeout_seconds=20)
    analytics=build_authorized_service('youtubeAnalytics','v2',credentials=credentials,request_timeout_seconds=20)
    deadline=GoogleOperationDeadline(seconds=300)
    operation='cloud-evidence-'+os.environ.get('GITHUB_RUN_ID','local')
    if operation.endswith('local'):raise PermissionError('BOUNDED_CLOUD_RUN_ID_REQUIRED')
    calls=[]; errors=[]
    def read(request,stage,data_api=True):
        if data_api and sum(c['data_api_units'] for c in calls)>=MAX_DATA_CALLS:raise PermissionError('DATA_CALL_BOUND_REACHED')
        key=operation+':'+stage
        if data_api:
            debit=reserve_general_quota(root,idempotency_key=key,operation_id=operation,job_id=operation,
                attempt_count=1,effective_general_before=2001,units=1,preventive_floor=12)
            consume_general_quota(root,idempotency_key=key)
        calls.append({'stage':stage,'data_api_units':1 if data_api else 0})
        value=execute_google_request(request,deadline=deadline,stage=stage)
        write(export/'raw'/(str(len(calls)).zfill(2)+'-'+stage+'.json'),exportable(value))
        return value
    captured=datetime.now(timezone.utc).isoformat()
    owned=exact_owned(read(youtube.channels().list(part='id,snippet,statistics,contentDetails',mine=True),'owned-channel'))
    write(export/'oauth-channel-health.json',identity_health(health,owned['id'],CHANNEL))
    if health_only:
        return {'status':'AUTH_HEALTH_OBSERVED','channel_id':CHANNEL,'data_api_units_reserved':1,
            'market_collection_performed':False,'production_ready':False,'publication_performed':False}

    if candidate_only:
        # Discovery leads are not evidence until this official response is saved.
        result=read(youtube.videos().list(part='id,snippet,statistics,contentDetails,status',
            id=','.join(DISCOVERY_IDS)),'candidate-video-identities')
        videos=[v for v in result.get('items',[]) if v.get('status',{}).get('privacyStatus')=='public']
        ids=sorted({v['snippet']['channelId'] for v in videos})
        channels=read(youtube.channels().list(part='id,snippet,statistics,contentDetails',
            id=','.join(ids)),'candidate-channel-identities') if ids else {'items':[]}
        observations=[]
        for v in videos:
            published=datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z','+00:00'))
            seconds=duration(v.get('contentDetails',{}).get('duration'))
            observations.append(snapshot(operation,captured,v['snippet']['channelId'],'VIDEO',v['id'],{
                'video_id':v['id'],'title':v['snippet']['title'],'channel_id_public':v['snippet']['channelId'],
                'timestamp':published.timestamp(),'duration_seconds':seconds,
                'view_count':int(v['statistics']['viewCount']) if 'viewCount' in v.get('statistics',{}) else None,
                'default_audio_language':v['snippet'].get('defaultAudioLanguage'),
                'availability':'public','catalog_role':'DISCOVERY_LEAD_NOT_QUALIFIED_REFERENCE',
                'format_basis':'PUBLIC_METADATA_REQUIRES_AV_CONFIRMATION',
                'license':v.get('status',{}).get('license')}))
        summary={'status':'CANDIDATE_IDENTITIES_OBSERVED','operation_id':operation,'captured_at':captured,
            'channel_id':CHANNEL,'requested_video_ids':list(DISCOVERY_IDS),
            'unavailable_video_ids':sorted(set(DISCOVERY_IDS)-{v['id'] for v in videos}),
            'market_snapshots':observations,'candidate_channels':exportable(channels.get('items',[])),
            'quota':{'calls':calls,'data_api_units_reserved':sum(c['data_api_units'] for c in calls)},
            'production_ready':False,'publication_performed':False,'vidiq_credits_used':0,
            'candidate_media_downloaded':False,
            'limitations':['Discovery metadata is not audiovisual mining, a winner cohort, CTR or monetization evidence.']}
        write(export/'evidence.json',summary)
        write(export/'summary.json',{'status':summary['status'],'public_candidates':len(videos),
            'publication_performed':False,'data_api_units_reserved':summary['quota']['data_api_units_reserved']})
        return {'status':summary['status'],'public_candidates':len(videos),'publication_performed':False}

    config=json.loads((root/'config/current_audio_research.json').read_text())
    refs=[r['channel_id'] for r in config['references']]+PRAYER_REFERENCES
    market=read(youtube.channels().list(part='id,snippet,statistics,contentDetails',id=','.join(refs)),'reference-channels')
    channels=[owned]+market.get('items',[])
    returned={c['id'] for c in channels}
    missing=sorted(set(refs)-returned)
    video_ids=[]; by_channel={}; listings={}
    for c in channels:
        cid=c['id'];playlist=c.get('contentDetails',{}).get('relatedPlaylists',{}).get('uploads')
        if not playlist:errors.append({'channel_id':cid,'code':'UPLOADS_PLAYLIST_ABSENT'});continue
        try:
            entries=read(youtube.playlistItems().list(part='contentDetails',playlistId=playlist,maxResults=50),'uploads-'+cid)
            ids=[x['contentDetails']['videoId'] for x in entries.get('items',[])]
            by_channel[cid]=ids;listings[cid]={'returned_count':len(ids),'has_more':bool(entries.get('nextPageToken'))}
            video_ids.extend(ids)
        except Exception as error:errors.append({'channel_id':cid,**safe_error(error)})
    videos=[]
    unique=list(dict.fromkeys(video_ids))
    for index in range(0,len(unique),50):
        result=read(youtube.videos().list(part='id,snippet,statistics,contentDetails,status',id=','.join(unique[index:index+50])),'videos-'+str(index//50))
        videos.extend(result.get('items',[]))
    owned_videos=[v for v in videos if v.get('snippet',{}).get('channelId')==CHANNEL]
    private=[]
    for video in owned_videos[:8]:
        vid=video['id'];start=video['snippet']['publishedAt'][:10];end=datetime.now(timezone.utc).date().isoformat()
        result={'video_id':vid,'date_window':{'start':start,'end_requested':end},'reach':{'impressions':None,'ctr':None,'status':'REPORTING_REQUIRED'},'qualified_ypp_hours':None}
        for label,metrics,dimensions in [('basic','views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost',None),('retention','audienceWatchRatio','elapsedVideoTimeRatio')]:
            try:
                args=dict(ids='channel==MINE',startDate=start,endDate=end,metrics=metrics,filters='video=='+vid)
                if dimensions:args.update(dimensions=dimensions,sort=dimensions)
                data=read(analytics.reports().query(**args),'owned-'+label+'-'+vid,False)
                rows=report_rows(data);result[label]={'status':'OBSERVED' if rows else 'EMPTY_OR_DATA_LAG','rows':rows}
            except Exception as error:result[label]={'status':'UNAVAILABLE',**safe_error(error)}
        private.append(result)
    reporting={'status':'UNAVAILABLE','jobs':[]}
    try:
        service=build_authorized_service('youtubereporting','v1',credentials=credentials,request_timeout_seconds=20)
        jobs=read(service.jobs().list(includeSystemManaged=False),'existing-reporting-jobs',False)
        reporting={'status':'OBSERVED','jobs':[{'id':j.get('id'),'report_type_id':j.get('reportTypeId'),'name':j.get('name'),'create_time':j.get('createTime')} for j in jobs.get('jobs',[])]}
        for job in reporting['jobs']:
            if job['report_type_id']!='channel_reach_basic_a1':continue
            data=read(service.jobs().reports().list(jobId=job['id'],pageSize=5),'existing-reach-reports',False)
            job['reports']=[{'id':r.get('id'),'start_time':r.get('startTime'),'end_time':r.get('endTime'),'create_time':r.get('createTime')} for r in data.get('reports',[])]
            job['more_reports_available']=bool(data.get('nextPageToken'))
    except Exception as error:reporting={'status':'UNAVAILABLE',**safe_error(error)}
    rows=[]; partitions={}
    for c in channels:
        if c['id']==CHANNEL:continue
        rows.append(snapshot(operation,captured,c['id'],'CHANNEL',c['id'],{'channel_id_public':c['id'],'channel_name_public':c['snippet']['title'],'catalog_role':'FORMAT_REFERENCE','media_downloaded':False}))
    for v in videos:
        cid=v.get('snippet',{}).get('channelId')
        if cid==CHANNEL or cid not in refs:continue
        seconds=duration(v.get('contentDetails',{}).get('duration'));bucket=stratum(seconds)
        if bucket=='FORMAT_UNCONFIRMED':continue
        published=datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z','+00:00'))
        row=snapshot(operation,captured,cid,'VIDEO',v['id'],{'video_id':v['id'],'title':v['snippet']['title'],'channel_id_public':cid,
            'timestamp':published.timestamp(),'upload_date':published.strftime('%Y%m%d'),'duration_seconds':seconds,
            'view_count':int(v['statistics']['viewCount']) if 'viewCount' in v.get('statistics',{}) else None,
            'catalog_role':'FORMAT_REFERENCE','content_format':'LONG','format_basis':'DURATION_OVER_180_SECONDS_INFERENCE_PENDING_AV',
            **public_projection(v),
            'duration_stratum':bucket,'default_audio_language':v['snippet'].get('defaultAudioLanguage'),
            'thumbnail':v['snippet'].get('thumbnails',{}).get('high',{}).get('url'),'license':v.get('status',{}).get('license')})
        if row['payload']['view_count'] is None:row['collection_status']='PARTIAL'
        rows.append(row);partitions.setdefault(bucket,[]).append(row)
    # Load this byte-verified pure original module directly. Importing the broad
    # observatory package also initializes OCR/ASR even for metadata-only work.
    module_path=root/'hero_engine/observatory/format_cohorts.py'
    spec=importlib.util.spec_from_file_location('heroverse_original_format_cohorts',module_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    compile_format_cohorts=module.compile_format_cohorts
    cohorts={}
    for bucket,subset in partitions.items():
        path=root/'output/market'/operation/(bucket+'.json')
        write(path,{'schema_version':'1.0.0','operation_id':operation,'captured_at':captured,'snapshots':[r for r in rows if r['entity_type']=='CHANNEL']+subset})
        try:cohorts[bucket]=compile_format_cohorts(path)
        except Exception as error:cohorts[bucket]={'status':'UNAVAILABLE',**safe_error(error)}
    safe={'schema_version':'cloud-evidence-v1','operation_id':operation,'captured_at':captured,'channel_id':CHANNEL,
        'owned_channel':owned,'owned_videos':owned_videos,'owned_private':private,'reporting':reporting,
        'market_snapshots':rows,'cohorts_by_duration':cohorts,'missing_reference_channels':missing,'playlist_coverage':listings,'errors':errors,
        'original_cohort_module_sha256':sha(module_path.read_bytes()),
        'quota':{'calls':calls,'data_api_units_reserved':sum(c['data_api_units'] for c in calls),'untracked_general_reserve':2000,'preventive_floor':12},
        'limitations':['Duration-based LONG classification requires audiovisual confirmation; no Shorts performance inferred.',
            'First page of each uploads playlist is a bounded sample, not complete catalogue.',
            'Two dated snapshots are required for acceleration; views/day is descriptive.',
            'Analytics watch time is not qualified YPP watch time.','No causal CTR, cadence, viral or monetization claim.'],
        'production_ready':False,'publication_performed':False,'vidiq_credits_used':0,'candidate_media_downloaded':False}
    write(export/'evidence.json',exportable(safe))
    shutil.copy2(root/'output/operations/zero-cost/phase6-quota-ledger.sqlite3',export/'quota-ledger.sqlite3')
    summary={'status':'OBSERVATIONS_COLLECTED','operation_id':operation,'channel_id':CHANNEL,
        'owned_videos':len(owned_videos),'market_videos':sum(r['entity_type']=='VIDEO' for r in rows),'missing_reference_channels':missing,
        'owned_basic_available':sum(x.get('basic',{}).get('status')=='OBSERVED' for x in private),
        'reporting_status':reporting['status'],'data_api_units_reserved':safe['quota']['data_api_units_reserved'],
        'vidiq_credits_used':0,'candidate_media_downloaded':False,'production_ready':False,'publication_performed':False}
    write(export/'summary.json',summary)
    return summary

def main():
    export=Path('cloud-evidence');export.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='heroverse-evidence-',dir=os.environ.get('RUNNER_TEMP')) as tmp:
        base=Path(tmp);restore(Path('HeroVerse_Linux_Source_Ready_20261013_v2.zip'),SOURCE_SHA,base/'source')
        manifest=json.loads((base/'source/SOURCE_TRANSFER_REPORT.json').read_text());root=base/'source/project'
        for item in manifest['files']:
            raw=(root/item['path']).read_bytes()
            if len(raw)!=item['bytes'] or sha(raw)!=item['sha256']:raise PermissionError('SOURCE_MEMBER_MISMATCH')
        restore(Path('HeroVerse_operational_snapshot.zip'),SNAPSHOT_SHA,base/'snapshot')
        ledger=base/'snapshot/databases/output/operations/zero-cost/phase6-quota-ledger.sqlite3'
        snapshot_manifest=json.loads((base/'snapshot/OPERATIONAL_SNAPSHOT_MANIFEST.json').read_text())
        entry=next(x for x in snapshot_manifest['databases'] if x['snapshot_path'].endswith('phase6-quota-ledger.sqlite3'))
        if sha(ledger.read_bytes())!=entry['sha256']:raise PermissionError('LEDGER_SOURCE_MISMATCH')
        destination=root/'output/operations/zero-cost/phase6-quota-ledger.sqlite3';destination.parent.mkdir(parents=True)
        from durable_evidence_checkpoint import restore_ledger,SQL,CLAIM
        if not CLAIM.exists() or json.loads(CLAIM.read_text()).get('run_id')!=os.environ.get('GITHUB_RUN_ID'):
            raise PermissionError('DURABLE_OBSERVER_CLAIM_REQUIRED')
        restore_ledger(SQL,destination)
        sys.path.insert(0,str(root))
        try:summary=collect(root,export,health_only=os.environ.get('HERO_AUTH_HEALTH_ONLY')=='true',
            candidate_only=os.environ.get('HERO_CANDIDATE_PROBE_ONLY')=='true')
        finally:
            if destination.exists():shutil.copy2(destination,export/'quota-ledger.sqlite3')
        print(json.dumps(summary))
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:out.write('```json\n'+json.dumps(summary,indent=2)+'\n```\n')

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'BLOCKED','error':safe_error(error),'secret_values_logged':False,'publication_performed':False}))
        raise SystemExit(2)
