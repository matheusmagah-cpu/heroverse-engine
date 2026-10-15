"""One-shot existing-grant Reporting read. Standard library only; no redirects/retries."""
from __future__ import annotations
import json
import math
import os
import shutil
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import existing_reach_probe as core

REPOSITORY = 'matheusmagah-cpu/heroverse-engine'
EXPECTED_RUN_NUMBER = '3'
PREVIOUS_FAILURE_PATH = Path('migration/evidence/owned-reach-preflight-failure-38822029275.json')
PREVIOUS_FAILURE_SHA256 = 'f5c8c636e0f7dca289f8982ed901924a85b9832d3b30d40e2b934a6ac0facaa2'
SECOND_FAILURE_PATH = Path('migration/evidence/owned-reach-helper-failure-38822885890.json')
SECOND_FAILURE_SHA256 = '8f24e0f89d44c28a0e3e1446af3a8f6c5722d4535c9d882a5280ba3ba6451533'
REQUIRED_DISK_BYTES = 256 * 1024**2
REQUIRED_MEMORY_BYTES = 512 * 1024**2
RESOURCE_POLICY = 'BOUNDED_REPORTING_STDLIB_ONLY_V1'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
META_BASE = f'https://youtubereporting.googleapis.com/v1/jobs/{core.JOB}/reports/'
READ_SCOPE = 'https://www.googleapis.com/auth/yt-analytics.readonly'
HELPER_HASHES = {'oauth_health.py': 'b2f667c880d6e5cf5b7e60889acaf7b9eddd28db8720cf8b9e8702feeb8f412c', 'verify_worker_oauth.py': 'aebf4236d9afddd702a79bbfc720e8cfa1560c2132dd1a50bfaa48956e015e46'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise core.ProbeBlocked('HTTP_REDIRECT_BLOCKED')


class Transport:
    def __init__(self, opener=None, deadline=None):
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.deadline = deadline or time.monotonic() + core.MAX_SECONDS
        self.counts = {'token_refresh': 0, 'report_metadata': 0, 'report_csv': 0}
        self.events = []
        self.seen_targets = set()

    def open(self, url, stage, *, data=None, bearer=None):
        remaining = self.deadline - time.monotonic()
        core.require(remaining > 0, 'DEADLINE_EXCEEDED')
        if stage == 'token_refresh':
            core.require(url == TOKEN_URL and data is not None and bearer is None, 'REFRESH_TARGET_BLOCKED')
            core.require(self.counts[stage] < 1, 'REFRESH_ONCE_ONLY')
        elif stage == 'report_metadata':
            core.require(url in {META_BASE+r for r in core.REPORT_IDS} and data is None and bearer, 'METADATA_TARGET_BLOCKED')
            core.require(self.counts[stage] < 2, 'METADATA_COUNT_LIMIT')
        elif stage == 'report_csv':
            core.require(data is None and bearer, 'CSV_REQUEST_BLOCKED')
            ids=[r for r in core.REPORT_IDS if '/reports/'+r+'?' in url]
            core.require(len(ids)==1, 'CSV_TARGET_BLOCKED')
            core.validate_download_url(url, ids[0])
            core.require(self.counts[stage] < 2, 'CSV_COUNT_LIMIT')
        else:
            raise core.ProbeBlocked('UNKNOWN_REQUEST_STAGE')
        core.require((stage,url) not in self.seen_targets,'EXACT_REQUEST_ALREADY_ATTEMPTED')
        self.seen_targets.add((stage,url))
        self.counts[stage] += 1
        headers={'Accept-Encoding':'identity'}
        if bearer:headers['Authorization']='Bearer '+bearer
        if data is not None:headers['Content-Type']='application/x-www-form-urlencoded'
        req=urllib.request.Request(url,data=data,headers=headers,method='POST' if data is not None else 'GET')
        event={'stage':stage,'attempt':self.counts[stage],'http_status':None}
        self.events.append(event)
        try:
            response=self.opener.open(req,timeout=min(20,remaining))
        except urllib.error.HTTPError as e:
            event['http_status']=e.code
            e.close()
            raise core.ProbeBlocked('HTTP_STATUS_'+str(e.code)) from None
        event['http_status']=response.status
        if response.status != 200 or response.geturl() != url:
            response.close()
            raise core.ProbeBlocked('HTTP_RESPONSE_IDENTITY_OR_STATUS')
        return response

    def json(self,url,stage,*,data=None,bearer=None):
        response=self.open(url,stage,data=data,bearer=bearer)
        try:
            core.require(response.headers.get('Content-Encoding','').lower() in ('','identity'), 'JSON_ENCODING_BLOCKED')
            raw=response.read(65537)
            core.require(len(raw)<=65536,'JSON_BYTE_LIMIT')
            value=json.loads(raw)
            core.require(isinstance(value,dict),'JSON_OBJECT_REQUIRED')
            return value
        finally:response.close()


def refresh_once(raw,transport,observe_refresh,check_token):
    # Both helpers are already in the project; never invoke their main routines.
    core.require(check_token(raw) is None,'EXISTING_TOKEN_CONFIG_INVALID')
    info=json.loads(raw)
    core.require(READ_SCOPE in info['scopes'],'EXISTING_READ_SCOPE_REQUIRED')
    def renew(_):
        payload=urllib.parse.urlencode({k:info[k] for k in ('client_id','client_secret','refresh_token')} |
                                     {'grant_type':'refresh_token'}).encode()
        value=transport.json(TOKEN_URL,'token_refresh',data=payload)
        token=value.get('access_token')
        core.require(isinstance(token,str) and bool(token) and '\n' not in token and '\r' not in token,'ACCESS_TOKEN_INVALID')
        core.require(value.get('token_type','').lower()=='bearer','TOKEN_TYPE_INVALID')
        core.require(isinstance(value.get('expires_in'),(int,float)) and math.isfinite(value['expires_in']) and value['expires_in']>=core.MAX_SECONDS,'TOKEN_EXPIRY_TOO_SHORT')
        if 'scope' in value:
            scopes=set(value['scope'].split())
            core.require(READ_SCOPE in scopes and scopes<=set(info['scopes']),'RETURNED_SCOPE_MISMATCH')
        # No scope parameter, consent, persistence, automatic refresh or retry.
        return SimpleNamespace(token=token)
    credentials,health=observe_refresh(raw,renew)
    core.require(credentials is not None,'EXISTING_REFRESH_FAILED')
    return credentials.token,health


class ReportService:
    def jobs(self):return self
    def reports(self):return self
    def get(self,*,jobId,reportId):
        core.require(jobId==core.JOB and reportId in core.REPORT_IDS,'EXACT_REPORT_REQUIRED')
        return META_BASE+reportId


class CSVResponse:
    history=[]
    def __init__(self,response):
        self.response=response;self.url=response.geturl();self.status_code=response.status;self.headers=response.headers
    def iter_content(self,chunk_size):
        while True:
            chunk=self.response.read(chunk_size)
            if not chunk:break
            yield chunk
    def close(self):self.response.close()


class CSVSession:
    def __init__(self,transport,token):self.transport=transport;self.token=token
    def get(self,url,**kwargs):
        core.require(kwargs.get('allow_redirects') is False and kwargs.get('stream') is True,'CSV_TRANSPORT_POLICY')
        return CSVResponse(self.transport.open(url,'report_csv',bearer=self.token))


def validate_execution_boundary(env):
    core.require(env.get('GITHUB_REPOSITORY')==REPOSITORY,'REPOSITORY_MISMATCH')
    core.require(env.get('HERO_REPOSITORY_PRIVATE')=='true','PRIVATE_REPOSITORY_REQUIRED')
    core.require(env.get('GITHUB_REF')=='refs/heads/main','MAIN_REF_REQUIRED')
    return {'repository':REPOSITORY,'repository_private':True,'ref':'refs/heads/main'}


class ResourceMarginBlocked(core.ProbeBlocked):
    def __init__(self, measurements):
        super().__init__('RESOURCE_MARGIN_REQUIRED')
        self.measurements = measurements


def validate_previous_failure(root):
    raw=(root/PREVIOUS_FAILURE_PATH).read_bytes()
    core.require(core.digest(raw)==PREVIOUS_FAILURE_SHA256,'PREVIOUS_FAILURE_HASH_MISMATCH')
    value=json.loads(raw)
    core.require(value.get('run_id')=='38822029275'
                 and value.get('commit')=='26d3103aaef8064d7e2e0f74e180d5bfbf4b2dec'
                 and value.get('status')=='BLOCKED'
                 and value.get('error_code')=='RESOURCE_MARGIN_REQUIRED'
                 and value.get('network_operations_attempted')==0
                 and value.get('requests')=={} and value.get('request_events')==[]
                 and value.get('youtube_data_api_calls')==0
                 and value.get('youtube_data_api_units')==0
                 and value.get('data_api_ledger_modified') is False,
                 'PREVIOUS_FAILURE_NOT_ZERO_NETWORK')
    second_raw=(root/SECOND_FAILURE_PATH).read_bytes()
    core.require(core.digest(second_raw)==SECOND_FAILURE_SHA256,'SECOND_FAILURE_HASH_MISMATCH')
    second=json.loads(second_raw)
    core.require(second.get('run_id')=='38822885890'
                 and second.get('commit')=='e635c8ba094c3e2a96414b27b5da7d546de68c6f'
                 and second.get('status')=='BLOCKED'
                 and second.get('error_code')=='AUTH_HELPER_IDENTITY_MISMATCH'
                 and second.get('network_operations_attempted')==0
                 and second.get('requests')=={} and second.get('request_events')==[]
                 and second.get('youtube_data_api_calls')==0
                 and second.get('youtube_data_api_units')==0
                 and second.get('data_api_ledger_modified') is False,
                 'SECOND_FAILURE_NOT_ZERO_NETWORK')
    return {'previous_run_ids':['38822029275','38822885890'],
            'previous_receipt_sha256':[PREVIOUS_FAILURE_SHA256,SECOND_FAILURE_SHA256],
            'previous_network_operations':0,'admitted_run_number':EXPECTED_RUN_NUMBER,
            'admitted_run_attempt':'1','previous_receipt_preserved':True}


def preflight(root,env):
    boundary=validate_execution_boundary(env)
    core.require(env.get('GITHUB_EVENT_NAME')=='workflow_dispatch','MANUAL_EVENT_REQUIRED')
    core.require(env.get('GITHUB_RUN_NUMBER')==EXPECTED_RUN_NUMBER and env.get('GITHUB_RUN_ATTEMPT')=='1','ONE_EXECUTION_ATTEMPT_ONLY')
    core.require(env.get('GITHUB_RUN_ID','').isdigit(),'RUN_ID_REQUIRED')
    core.require(not (root/'migration/evidence/observer-claim.json').exists(),'OBSERVER_CLAIM_UNRESOLVED')
    recovery=validate_previous_failure(root)
    free=shutil.disk_usage(root).free
    samples=[]
    for index in range(2):
        if index:time.sleep(0.1)
        samples.append(next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))
    available=min(samples)
    measurements = {'execution_boundary':boundary,'recovery':recovery,'resource_policy':RESOURCE_POLICY,'memory_samples_bytes':samples,'disk_free_bytes':free,'memory_available_bytes':available,
            'required_disk_free_bytes':REQUIRED_DISK_BYTES,'required_memory_available_bytes':REQUIRED_MEMORY_BYTES,
            'disk_margin_passed':free>=REQUIRED_DISK_BYTES,'memory_margin_passed':available>=REQUIRED_MEMORY_BYTES,
            'data_api_requests':0,'data_api_units_required':0,
            'reason':'EXISTING_REPORTING_REPORTS_ONLY_NO_DATA_API',
            'observer_ledger_modified':False,'new_jobs_created':0}
    if not measurements['disk_margin_passed'] or not measurements['memory_margin_passed']:
        raise ResourceMarginBlocked(measurements)
    return measurements


def main():
    root=Path.cwd();output=root/'owned-reach-probe-output'
    core.require(not output.exists(),'OUTPUT_ALREADY_EXISTS')
    envelope={'status':'BLOCKED','manual_approval':False,'production_approved':False,'publication_authorized':False}
    transport=None
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(core.ProbeBlocked('WALL_DEADLINE_EXCEEDED')))
    signal.alarm(core.MAX_SECONDS)
    try:
        envelope['preflight']=preflight(root,os.environ)
        snapshot=(root/'migration/evidence/observer-38749052276.json').read_bytes()
        core.plan_from_snapshot(snapshot)
        for name,expected in HELPER_HASHES.items():
            core.require(core.digest((root/'migration'/name).read_bytes())==expected,'AUTH_HELPER_IDENTITY_MISMATCH')
        sys.path.insert(0,str(root/'migration'))
        from oauth_health import observe_refresh
        from verify_worker_oauth import check_token
        transport=Transport()
        raw=os.environ.pop('HERO_YT_AUTHORIZED_USER_JSON','')
        token,health=refresh_once(raw,transport,observe_refresh,check_token);raw=None
        envelope['oauth_health']=health
        def execute(url,stage):return transport.json(url,'report_metadata',bearer=token)
        result=core.collect_existing_reports(snapshot,ReportService(),execute,CSVSession(transport,token),output)
        token=None
        envelope['status']=result['status']
        envelope['owner_binding']='PINNED_OWNED_JOB_AND_EXACT_CSV_CHANNEL_WHEN_ROWS_EXIST_NOT_NEW_CHANNEL_API_PROOF'
        envelope['receipt_sha256']=core.digest((output/'receipt.json').read_bytes())
    except Exception as e:
        if isinstance(e,ResourceMarginBlocked):
            envelope['preflight']=e.measurements
        envelope['error_code']=str(e) if isinstance(e,core.ProbeBlocked) else type(e).__name__
    finally:
        signal.alarm(0)
        envelope['requests']=transport.counts if transport else {}
        envelope['request_events']=transport.events if transport else []
        envelope['network_operations_attempted']=sum(envelope['requests'].values())
        envelope['network_operations_maximum']=5
        envelope['youtube_data_api_calls']=0
        envelope['youtube_data_api_units']=0
        envelope['data_api_ledger_modified']=False
        envelope['run_id']=os.environ.get('GITHUB_RUN_ID')
        envelope['commit']=os.environ.get('GITHUB_SHA')
        envelope['code_sha256']=core.digest(Path(__file__).read_bytes())
        output.mkdir(exist_ok=True)
        with (output/'execution.json').open('x') as f:json.dump(envelope,f,indent=2,allow_nan=False)
    print(json.dumps({'status':envelope['status'],'request_counts':envelope['requests'],'details_redacted':True}))
    return 0 if envelope['status']=='INGESTED_BOUNDED_REPORTS' else 2

if __name__=='__main__':
    sys.exit(main())
