"""One progress read; use a new provider-issued host only, never start a job."""
import hashlib,json,os,time
from pathlib import Path
from urllib.parse import urlsplit
import native_probe as n
from next_window import inspect

out=Path('refreshed-midpoint');out.mkdir(exist_ok=True)
prior_dir=Path('midpoint-attempt')
prior=json.loads((prior_dir/'receipt.json').read_text())
old=json.loads((prior_dir/'progress-03.json').read_text())['download_url']
e={'version':'existing-midpoint-location-refresh-v1','status':'BLOCKED','new_provider_jobs':0,
   'provider_job_id':prior['provider_job_id'],'progress_polls':0,'control_response_bytes':0,
   'baseline_quota_headers':prior['last_quota_headers'],'media_requests':0,
   'production':False,'publication':False,'supervisor':False,'recurring_capacity_qualified':False}
started=time.monotonic();key=os.environ.get('HERO_RAPIDAPI_KEY','')
try:
    assert os.environ['GITHUB_RUN_NUMBER']=='1' and os.environ['GITHUB_RUN_ATTEMPT']=='1'
    assert prior['provider_job_id']=='v2_stream_065e6ed9572627501de7'
    assert prior['download_tools_call_requests']==1 and prior['effect_status']=='JOB_ID_RECEIVED_NO_RESTART_ALLOWED'
    assert key
    value=n.progress(prior['provider_job_id'],key,e,out,0)
    e['provider_progress_summary'] = {k:value.get(k) for k in ['success','progress','message','text']}
    if value.get('success') != 1 or value.get('progress') != 1000:
        raise n.ProbeError('EXISTING_JOB_NOT_SUCCESSFUL_NO_MEDIA_REQUEST')
    new=value['download_url']
    e['previous_delivery_host']=urlsplit(old).hostname
    e['current_delivery_host']=urlsplit(new).hostname
    e['previous_delivery_url_sha256']=hashlib.sha256(old.encode()).hexdigest()
    e['current_delivery_url_sha256']=hashlib.sha256(new.encode()).hexdigest()
    if e['previous_delivery_host']==e['current_delivery_host']:
        e['status']='UNCHANGED_DELIVERY_HOST_NO_MEDIA_RETRY'
    else:
        e['media_requests']=1
        n.fetch_media(new,out,e,timeout=90)
        inspect(out,e)
        e['status']='EXISTING_JOB_DELIVERED_FROM_PROVIDER_CHANGED_HOST'
except n.HTTPError as error:
    e['failure_code']='HTTP_'+str(error.code)
except n.ProbeError as error:
    e['failure_code']=str(error)
except Exception as error:
    e['failure_type']=type(error).__name__
finally:
    e['elapsed_seconds']=time.monotonic()-started
    n.private_json(out/'receipt.json',e,key)
    print('HEROVERSE_LOCATION_REFRESH='+json.dumps(e),flush=True)
raise SystemExit(0 if e['status']=='EXISTING_JOB_DELIVERED_FROM_PROVIDER_CHANGED_HOST' else 2)
