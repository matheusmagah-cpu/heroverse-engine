import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch
import run_existing_reach_probe as w
import existing_reach_probe as core
import sys
sys.path.insert(0,str(Path('migration').resolve()))
from verify_worker_oauth import CLIENT_ID,SCOPES,check_token
from oauth_health import observe_refresh

ROOT=Path.cwd()
FIXTURE={'type':'authorized_user','client_id':CLIENT_ID,'client_secret':'synthetic-secret','refresh_token':'synthetic-refresh','scopes':sorted(SCOPES),'token_uri':w.TOKEN_URL}
ENV={'GITHUB_REPOSITORY':w.REPOSITORY,'HERO_REPOSITORY_PRIVATE':'true','GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_NUMBER':'3','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'999000','GITHUB_SHA':'synthetic-candidate','HERO_YT_AUTHORIZED_USER_JSON':json.dumps(FIXTURE)}

class RawResponse(io.BytesIO):
    status=200
    def __init__(self,url,raw):super().__init__(raw);self.url=url;self.headers={'Content-Length':str(len(raw))}
    def geturl(self):return self.url

class FakeTransport:
    def __init__(self,plan):self.plan=plan;self.counts={'token_refresh':0,'report_metadata':0,'report_csv':0};self.events=[]
    def mark(self,stage):self.counts[stage]+=1;self.events.append({'stage':stage,'http_status':200})
    def json(self,url,stage,**kwargs):
        self.mark(stage)
        if stage=='token_refresh':return {'access_token':'synthetic-access','token_type':'Bearer','expires_in':3600,'scope':' '.join(sorted(SCOPES))}
        rid=url.rsplit('/',1)[1];e=self.plan['reports'][rid]
        return {'id':rid,'jobId':core.JOB,'startTime':e['start_time'],'endTime':e['end_time'],'createTime':e['create_time'],'downloadUrl':f'https://youtubereporting.googleapis.com/v1/media/CHANNEL/exact-owned/jobs/{core.JOB}/reports/{rid}?alt=media'}
    def open(self,url,stage,**kwargs):
        self.mark(stage);rid=next(r for r in core.REPORT_IDS if '/reports/'+r+'?' in url)
        date='2026-10-13' if rid==core.REPORT_IDS[0] else '2026-10-12'
        raw=('date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n'+date+','+core.CHANNEL+',FifnlNUQKNk,10,0.5\n').encode()
        return RawResponse(url,raw)

class Tests(unittest.TestCase):
    def test_real_helpers_fixture_scope_and_endpoint_fail_closed(self):
        self.assertIsNone(check_token(json.dumps(FIXTURE)))
        for key,value in [('scopes',[]),('client_id','wrong'),('token_uri','https://evil.invalid/token')]:
            bad=dict(FIXTURE);bad[key]=value;calls=[]
            result,health=observe_refresh(json.dumps(bad),lambda raw:calls.append(raw))
            self.assertIsNone(result);self.assertEqual(calls,[]);self.assertEqual(health['status'],'CONFIGURATION_BLOCKED')
    def test_all_exact_pins_and_report_metadata_shapes(self):
        data=(ROOT/'migration/evidence/observer-38749052276.json').read_bytes();plan=core.plan_from_snapshot(data)
        self.assertEqual(hashlib.sha256(data).hexdigest(),core.SOURCE_SHA)
        w.validate_previous_failure(ROOT)
        for name,expected in w.HELPER_HASHES.items():self.assertEqual(core.digest((ROOT/'migration'/name).read_bytes()),expected)
        transport=FakeTransport(plan)
        for rid in core.REPORT_IDS:core.verify_resource(transport.json(w.META_BASE+rid,'report_metadata'),plan['reports'][rid])
    def test_full_main_checkout_fixture_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            needed=[Path('migration/evidence/observer-38749052276.json'),w.PREVIOUS_FAILURE_PATH,w.SECOND_FAILURE_PATH]+[Path('migration')/n for n in w.HELPER_HASHES]
            for path in needed:
                dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/path).read_bytes())
            plan=core.plan_from_snapshot((root/'migration/evidence/observer-38749052276.json').read_bytes());t=FakeTransport(plan)
            old=Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ,ENV,clear=False),patch.object(w,'Transport',return_value=t),patch.object(socket,'create_connection',side_effect=AssertionError('NETWORK_FORBIDDEN')):
                    self.assertEqual(w.main(),0)
            finally:os.chdir(old)
            execution=json.loads((root/'owned-reach-probe-output/execution.json').read_text())
            receipt=json.loads((root/'owned-reach-probe-output/receipt.json').read_text())
            self.assertEqual(execution['network_operations_attempted'],5)
            self.assertEqual(receipt['csv_rows_ingested'],2)
            self.assertEqual(execution['preflight']['recovery']['previous_run_ids'],['38822029275','38822885890'])
            self.assertFalse(execution['manual_approval']);self.assertEqual(len(list((root/'owned-reach-probe-output').glob('*.csv'))),2)
    def test_second_receipt_tamper_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/w.PREVIOUS_FAILURE_PATH;a.parent.mkdir(parents=True);a.write_bytes((ROOT/w.PREVIOUS_FAILURE_PATH).read_bytes())
            (root/w.SECOND_FAILURE_PATH).write_bytes((ROOT/w.SECOND_FAILURE_PATH).read_bytes()+b'\n')
            with self.assertRaisesRegex(core.ProbeBlocked,'SECOND_FAILURE_HASH_MISMATCH'):w.validate_previous_failure(root)

if __name__=='__main__':unittest.main(verbosity=2)
