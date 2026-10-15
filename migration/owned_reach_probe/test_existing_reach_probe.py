import os
import copy
import io
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import existing_reach_probe as p

SOURCE = Path(os.environ.get('HERO_PROBE_SNAPSHOT', 'migration/evidence/observer-38749052276.json'))
PLAN = p.plan_from_snapshot(SOURCE.read_bytes())
VID = PLAN['target_video_ids'][0]

def resource(rid=p.REPORT_IDS[0]):
    e=PLAN['reports'][rid]
    return dict(id=rid,jobId=p.JOB,startTime=e['start_time'],endTime=e['end_time'],createTime=e['create_time'],
                downloadUrl=f'https://youtubereporting.googleapis.com/v1/media/CHANNEL/owned/jobs/{p.JOB}/reports/{rid}?alt=media')

def csv_bytes(rows=None, headers=None):
    h=headers or ['video_id','date','channel_id','video_thumbnail_impressions_ctr','video_thumbnail_impressions']
    rows=rows if rows is not None else [[VID,'2026-10-13',p.CHANNEL,'0.5','660']]
    s=io.StringIO();w=csv.writer(s);w.writerow(h);w.writerows(rows);return s.getvalue().encode()

class Response:
    status_code=200
    history=[]
    def __init__(self,url,raw,status=200):
        self.url=url;self.raw=raw;self.status_code=status;self.headers={'Content-Length':str(len(raw))};self.closed=False
    def iter_content(self,chunk_size):
        yield self.raw
    def close(self):self.closed=True

class Session:
    def __init__(self,raw,status=200):self.raw=raw;self.status=status;self.calls=[]
    def get(self,url,**kw):
        self.calls.append((url,kw));self.response=Response(url,self.raw,self.status);return self.response

class Service:
    def jobs(self):return self
    def reports(self):return self
    def get(self,**kw):return kw

class Tests(unittest.TestCase):
    def test_plan_pinned(self):
        self.assertEqual(len(PLAN['reports']),2)
        with self.assertRaises(p.ProbeBlocked):p.plan_from_snapshot(SOURCE.read_bytes()+b' ')
    def test_named_columns(self):
        r=p.parse_csv(csv_bytes(),resource());self.assertEqual(r['rows'][0]['video_thumbnail_impressions'],'660')
        self.assertEqual(r['rows'][0]['video_thumbnail_impressions_ctr'],'0.5')
    def test_empty_rows_preserved_as_absent(self):self.assertEqual(p.parse_csv(csv_bytes([]),resource())['row_count'],0)
    def test_duplicate_dimension_key_blocks(self):
        row=[VID,'2026-10-13',p.CHANNEL,'0.5','660']
        with self.assertRaisesRegex(p.ProbeBlocked,'DUPLICATE'):p.parse_csv(csv_bytes([row,row]),resource())
    def test_other_video_same_date_is_not_duplicate(self):
        rows=[[v,'2026-10-13',p.CHANNEL,'0','0'] for v in PLAN['target_video_ids'][:2]]
        self.assertEqual(p.parse_csv(csv_bytes(rows),resource())['row_count'],2)
    def test_bad_schema(self):
        for h in [list(p.COLUMNS)+['device_type'],list(p.COLUMNS)+['date'],['date']]:
            with self.assertRaises(p.ProbeBlocked):p.parse_csv(csv_bytes([],h),resource())
    def test_bad_values(self):
        base=[VID,'2026-10-13',p.CHANNEL,'0.5','660']
        for idx,value in [(0,'bad'),(1,'2026-10-14'),(1,'2026-13-01'),(2,'other'),(3,'nan'),(3,'-1'),(3,'101'),(4,'1.5'),(4,'-1')]:
            row=base[:];row[idx]=value
            with self.assertRaises(ValueError):p.parse_csv(csv_bytes([row]),resource())
    def test_extra_and_missing_cells(self):
        for row in [[VID,'2026-10-13',p.CHANNEL,'0','0','oops'],[VID,'2026-10-13']]:
            with self.assertRaises(p.ProbeBlocked):p.parse_csv(csv_bytes([row]),resource())
    def test_resource_identity(self):
        for key in ['id','jobId','startTime','endTime','createTime']:
            r=resource();r[key]='wrong'
            with self.assertRaises(p.ProbeBlocked):p.verify_resource(r,PLAN['reports'][p.REPORT_IDS[0]])
    def test_origin_path_query_reject_before_get(self):
        good=resource()['downloadUrl']
        for u in [good.replace('https:','http:'),good.replace('googleapis.com','googleapis.com.evil'),good.replace('/v1/media/','/redirect/'),good+'&token=x',good.replace('?alt=media','?alt=media&alt=media'),good+'#fragment',good.replace('/CHANNEL/owned','/CHANNEL/../owned')]:
            r=resource();r['downloadUrl']=u;s=Session(b'x')
            with self.assertRaises(p.ProbeBlocked):p.bounded_download(s,r,100, p.time.monotonic()+10)
            self.assertFalse(s.calls)
    def test_redirect_not_followed(self):
        s=Session(b'x',302)
        with self.assertRaises(p.ProbeBlocked):p.bounded_download(s,resource(),100,p.time.monotonic()+10)
        self.assertFalse(s.calls[0][1]['allow_redirects']);self.assertTrue(s.response.closed)
    def test_limit(self):
        with self.assertRaises(p.ProbeBlocked):p.bounded_download(Session(b'123'),resource(),2,p.time.monotonic()+10)
    def test_deadline_before_request(self):
        s=Session(b'x')
        with self.assertRaises(p.ProbeBlocked):p.bounded_download(s,resource(),10,p.time.monotonic()-1)
        self.assertFalse(s.calls)
    def test_collect_both_no_aggregate_no_missing_zero(self):
        class DailySession(Session):
            def get(self,url,**kw):
                day='2026-10-13' if p.REPORT_IDS[0] in url else '2026-10-12'
                self.raw=csv_bytes([[VID,day,p.CHANNEL,'0.5','660']]);return super().get(url,**kw)
        def execute(req,stage):
            self.assertEqual(req['jobId'],p.JOB);return resource(req['reportId'])
        with tempfile.TemporaryDirectory() as tmp:
            r=p.collect_existing_reports(SOURCE.read_bytes(),Service(),execute,DailySession(b''),Path(tmp)/'run')
            self.assertEqual(r['status'],'INGESTED_BOUNDED_REPORTS');self.assertEqual(r['csv_rows_ingested'],2)
            self.assertEqual(r['video_observations'][0]['covered_dates'],['2026-10-12','2026-10-13'])
            self.assertIsNone(r['video_observations'][0]['aggregate_ctr'])
            self.assertEqual(r['video_observations'][1]['rows'],[])
            self.assertFalse(r['manual_approval'])
            text=json.dumps(r);self.assertNotIn('downloadUrl',text);self.assertNotIn('Authorization',text)
    def test_fail_closed_no_retry_or_secret_exception(self):
        calls=[]
        def execute(req,stage):calls.append(req);raise RuntimeError('secret bad URL')
        with tempfile.TemporaryDirectory() as tmp:
            r=p.collect_existing_reports(SOURCE.read_bytes(),Service(),execute,Session(b''),Path(tmp)/'run')
            self.assertEqual(len(calls),1);self.assertEqual(r['status'],'BLOCKED')
            self.assertNotIn('secret',json.dumps(r));self.assertEqual(r['reports'][0]['error_code'],'RuntimeError')
    def test_output_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):p.collect_existing_reports(SOURCE.read_bytes(),Service(),None,None,tmp)

if __name__=='__main__':unittest.main(verbosity=2)
