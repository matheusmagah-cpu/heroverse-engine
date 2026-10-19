import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import existing_reach_probe as c
import run_existing_reach_probe as w

FIRST='17695215035'
SECOND='20613781334'
def url(rid):return f'https://youtubereporting.googleapis.com/v1/media/CHANNEL/owned/jobs/{c.JOB}/reports/{rid}?alt=media'
class Opener:
 def __init__(self):self.calls=[]
 def open(self,*args,**kwargs):self.calls.append(args);raise AssertionError('NO_REQUEST_EXPECTED')
class Tests(unittest.TestCase):
 def test_only_pending_constant_and_limits(self):
  self.assertEqual(c.FETCH_REPORT_IDS,(SECOND,));self.assertEqual(c.MAX_TOTAL_BYTES,4*1024**2);self.assertEqual(c.CTR_UNIT,'provider_raw_representation_unverified');self.assertEqual(w.EXPECTED_RUN_NUMBER,'4')
 def test_first_report_denied_all_network_layers(self):
  op=Opener();t=w.Transport(opener=op)
  for target,stage in [(w.META_BASE+FIRST,'report_metadata'),(url(FIRST),'report_csv')]:
   with self.assertRaises(c.ProbeBlocked):t.open(target,stage,bearer='synthetic')
  with self.assertRaises(c.ProbeBlocked):w.ReportService().get(jobId=c.JOB,reportId=FIRST)
  with self.assertRaises(c.ProbeBlocked):c.validate_download_url(url(FIRST),FIRST)
  with self.assertRaises(c.ProbeBlocked):c.verify_resource({'id':FIRST},{'id':FIRST})
  with self.assertRaises(c.ProbeBlocked):c.bounded_download(None,{'id':FIRST,'downloadUrl':url(FIRST)},100, c.time.monotonic()+10)
  self.assertEqual(op.calls,[]);self.assertEqual(sum(t.counts.values()),0)
 def test_second_request_count_cap_before_send(self):
  op=Opener();t=w.Transport(opener=op)
  for target,stage in [(w.TOKEN_URL,'token_refresh'),(w.META_BASE+SECOND,'report_metadata'),(url(SECOND),'report_csv')]:
   t.counts[stage]=1
   with self.assertRaises(c.ProbeBlocked):t.open(target,stage,**({'data':b'fake'} if stage=='token_refresh' else {'bearer':'synthetic'}))
  self.assertEqual(op.calls,[])
 def test_strict_dates_and_pacific(self):
  for value in ['20261012','2026-10-12']:self.assertEqual(c.parse_reporting_day(value).isoformat(),'2026-10-12T00:00:00-07:00')
  for value in ['2026/10/12','2026101','20260230','2026-1-12',' 20261012','２０２６１０１２','20261012T00:00']:
   with self.assertRaisesRegex(c.ProbeBlocked,'CSV_DATE_INVALID'):c.parse_reporting_day(value)
 def test_compact_raw_preserved_and_mixed_duplicate_blocked(self):
  header='date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n'
  row=f'20261012,{c.CHANNEL},FifnlNUQKNk,9,1\n';res={'startTime':'2026-10-12T07:00:00Z','endTime':'2026-10-13T07:00:00Z'}
  parsed=c.parse_csv((header+row).encode(),res);self.assertEqual(parsed['rows'][0]['date'],'20261012');self.assertEqual(parsed['rows'][0]['video_thumbnail_impressions_ctr'],'1')
  with self.assertRaisesRegex(c.ProbeBlocked,'DUPLICATE'):c.parse_csv((header+row+row.replace('20261012','2026-10-12')).encode(),res)
  for bad in ['20261011','20261013']:
   with self.assertRaisesRegex(c.ProbeBlocked,'OUTSIDE_REPORT'):c.parse_csv((header+row.replace('20261012',bad)).encode(),res)
 def test_third_receipts_tamper_rejected(self):
  for changed in [w.THIRD_FAILURE_PATH,w.THIRD_COLLECTION_PATH]:
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    for path in [w.PREVIOUS_FAILURE_PATH,w.SECOND_FAILURE_PATH,w.THIRD_FAILURE_PATH,w.THIRD_COLLECTION_PATH]:
     f=root/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(path.read_bytes()+(b' ' if path==changed else b''))
    with self.assertRaisesRegex(c.ProbeBlocked,'HASH_MISMATCH'):w.validate_previous_failure(root)
 def test_workflow_excludes_received_csv_and_run3(self):
  s=Path('.github/workflows/owned-reach-existing-once.yml').read_text();self.assertNotIn('report-17695215035.csv',s);self.assertIn('"$RUN_NUMBER" = 4',s);self.assertIn('report-20613781334.csv',s)
if __name__=='__main__':unittest.main()
