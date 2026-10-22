import copy
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import remaining_openings as b

class BatchGuards(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,10,15,21,40,tzinfo=dt.timezone.utc)
        self.billing={'observed_at':self.now.isoformat(),'github_included_runner_minutes_remaining':1800,
          'rapidapi_subscription_active_basic_zero_usd':True,'rapidapi_bandwidth_display':'0.00%',
          'bandwidth_headroom_basis':'PRACTICAL_DISPLAY_INFERENCE_NOT_HARD_STOP_PROOF',
          'github_zero_additional_spend_confirmed':True,'github_actions_budget_usd':0,
          'github_actions_budget_status':'Usage blocked','github_storage_display':'0 GB / 0.5 GB','new_payment_or_plan_change':False}
        self.approval={'batch_id':b.BATCH_ID,'status':'APPROVED_ONE_TIME_EXCEPTION','approved_by_owner':True,
          'approval_message_id':'offline-test-only','sources':list(b.SOURCES),'qualification_exception':copy.deepcopy(b.EXCEPTION),
          'production':False,'publication':False,'recurring_cadence_authorized':False,'billing':self.billing}
        self.ledger={'version':'native-av-reservations-v1','limits':{'daily_jobs':3},'production':False,'publication':False,
          'qualification_recovery_extra_runner_minutes_reserved':6,
          'claims':[dict(b.s.RESERVATION,request_id=r,status='RETAINED',day_utc='2026-10-15') for r in b.INITIAL_REQUESTS]}
        self.inventory=json.loads((b.EVIDENCE/'five-source-native-gap.json').read_text())

    def test_checked_in_admission_fails_closed(self):
        admission=json.loads((b.EVIDENCE/'remaining-openings-admission.json').read_text())
        # Check a pending fixture independently of later approved record changes.
        admission.update(status='PENDING_OWNER_APPROVAL',approved_by_owner=False,approval_message_id=None)
        with self.assertRaisesRegex(b.s.n.ProbeError,'APPROVAL_MISSING'):b.validate_admission(admission,self.now)

    def test_exact_approval_and_freshness(self):
        b.validate_admission(self.approval,self.now)
        with self.assertRaisesRegex(b.s.n.ProbeError,'FRESH_BATCH'):b.validate_admission(self.approval,self.now+dt.timedelta(minutes=31))

    def test_no_swapped_or_extra_source(self):
        self.approval['sources'].reverse()
        with self.assertRaisesRegex(b.s.n.ProbeError,'EXACT_BATCH_SCOPE'):b.validate_admission(self.approval,self.now)

    def test_no_recurring_authority(self):
        self.approval['recurring_cadence_authorized']=True
        with self.assertRaisesRegex(b.s.n.ProbeError,'AUTHORITY_BOUNDARY'):b.validate_admission(self.approval,self.now)

    def test_all_saved_metadata_eligible(self):
        for source in b.SOURCES:b.validate_metadata(self.inventory,source,self.now)

    def test_metadata_expiry_and_bad_hash(self):
        with self.assertRaisesRegex(b.s.n.ProbeError,'SNAPSHOT'):b.validate_metadata(self.inventory,b.SOURCES[0],self.now+dt.timedelta(days=1))
        self.inventory['provenance']['observer_sha256']='wrong'
        with self.assertRaisesRegex(b.s.n.ProbeError,'SNAPSHOT'):b.validate_metadata(self.inventory,b.SOURCES[0],self.now)

    def test_first_job_retains_all_original_claims(self):
        result=b.prior_claims(self.ledger,0,Path('/unused'))
        self.assertEqual(result,self.ledger)
        self.assertEqual(len(result['claims']),3)

    def test_missing_predecessor_fails(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(b.s.n.ProbeError,'PREDECESSOR_RECEIPT_MISSING'):b.prior_claims(self.ledger,1,Path(t))

    def chain(self,status='NATIVE_OPENING_DECODED_AWAITING_REVIEW'):
        return {'batch_id':b.BATCH_ID,'request_id':b.REQUESTS[0],'source_video_id':b.SOURCES[0],
          'status':status,'download_tools_call_requests':1,'complete_clip_decode_passed':True,
          'run_id':'mock-run','head_sha':'mock-head','provider_job_id':'mock-job','media_file':{'bytes':100,'sha256':'a'*64},
          'reservation':dict(b.s.RESERVATION,request_id=b.REQUESTS[0],day_utc='2026-10-15')}

    def test_prior_failure_stops_chain(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'GITHUB_RUN_ID':'mock-run','GITHUB_SHA':'mock-head'}):
            p=Path(t)/b.SOURCES[0];p.mkdir();(p/'chain-receipt.json').write_text(json.dumps(self.chain('BLOCKED')))
            with self.assertRaisesRegex(b.s.n.ProbeError,'PREDECESSOR_NOT_SUCCESSFUL'):b.prior_claims(self.ledger,1,Path(t))

    def test_successful_same_run_receipt_preserves_claim(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'GITHUB_RUN_ID':'mock-run','GITHUB_SHA':'mock-head'}):
            p=Path(t)/b.SOURCES[0];p.mkdir();(p/'chain-receipt.json').write_text(json.dumps(self.chain()))
            result=b.prior_claims(self.ledger,1,Path(t));self.assertEqual(result['claims'][:3],self.ledger['claims']);self.assertEqual(len(result['claims']),4)
            with patch.dict(os.environ,{'GITHUB_RUN_ID':'different'}):
                with self.assertRaisesRegex(b.s.n.ProbeError,'PREDECESSOR_NOT_SUCCESSFUL'):b.prior_claims(self.ledger,1,Path(t))

    def test_current_cap_blocks_without_exact_exception(self):
        source=b.SOURCES[0];request=b.REQUESTS[0];params=dict(b.s.PARAMS,url='https://www.youtube.com/watch?v='+source)
        plan=dict(request_id=request,status='PLANNED_NOT_ADMITTED',parameters=params,reservation=b.s.RESERVATION)
        billing=dict(self.billing,request_id=request,status='VERIFIED_FOR_ONE_SHOT')
        with patch.object(b.s,'REQUEST_ID',request),patch.object(b.s,'PARAMS',params):
            with self.assertRaisesRegex(b.s.n.ProbeError,'DAILY_JOB_CAP'):b.s.admit(plan,self.ledger,billing,self.now)
            b.s.admit(plan,self.ledger,billing,self.now,b.EXCEPTION)
            wrong=copy.deepcopy(b.EXCEPTION);wrong['day_utc']='2026-10-16'
            with self.assertRaisesRegex(b.s.n.ProbeError,'EXACT_QUALIFICATION'):b.s.admit(plan,self.ledger,billing,self.now,wrong)

    def test_third_exception_claim_allowed_seventh_not(self):
        self.ledger['claims'].extend(dict(b.s.RESERVATION,request_id=r,day_utc='2026-10-15') for r in b.REQUESTS[:2])
        params=dict(b.s.PARAMS,url='https://www.youtube.com/watch?v='+b.SOURCES[2]);plan=dict(request_id=b.REQUESTS[2],status='PLANNED_NOT_ADMITTED',parameters=params,reservation=b.s.RESERVATION)
        billing=dict(self.billing,request_id=b.REQUESTS[2],status='VERIFIED_FOR_ONE_SHOT')
        with patch.object(b.s,'REQUEST_ID',b.REQUESTS[2]),patch.object(b.s,'PARAMS',params):
            b.s.admit(plan,self.ledger,billing,self.now,b.EXCEPTION)
            self.ledger['claims'].append(dict(b.s.RESERVATION,request_id='unapproved-fourth-base',day_utc='2026-10-15'))
            with self.assertRaisesRegex(b.s.n.ProbeError,'EXCEPTION_CAP'):b.s.admit(plan,self.ledger,billing,self.now,b.EXCEPTION)

    def test_offline_approval_failure_before_any_network(self):
        with patch.object(b,'prepare_config',side_effect=b.s.n.ProbeError('EXPLICIT_BATCH_APPROVAL_MISSING')),patch.object(b.s,'artifact_preflight') as inventory,patch.object(b.s,'run') as run:
            with self.assertRaises(b.s.n.ProbeError):b.execute(b.SOURCES[0],Path('/unused'),Path('/unused'),{},'mock')
            inventory.assert_not_called();run.assert_not_called()

    def test_execute_reuses_one_runner_and_strengthens_batch_quota(self):
        params=dict(b.s.PARAMS,url='https://www.youtube.com/watch?v='+b.SOURCES[0])
        config={'plan':{'parameters':params},'ledger':{},'billing':{}}
        q={'x-ratelimit-units-limit':'500','x-ratelimit-units-remaining':'462'}
        for prefix in ('x-ratelimit-requests','x-ratelimit-rapid-free-plans-hard-limit'):
            q[prefix+'-limit']='500000';q[prefix+'-remaining']='499993'
        def runner(out,e,key,config):
            b.s.fresh_quota(q)
            q['x-ratelimit-units-remaining']='41'
            with self.assertRaisesRegex(b.s.n.ProbeError,'BATCH_UNIT_HEADROOM'):b.s.fresh_quota(q)
        with patch.object(b,'prepare_config',return_value=(0,{},config)),patch.object(b.s,'admit'),patch.object(b.s,'artifact_preflight',return_value={'unexpired_repository_artifact_bytes':100_000_000}),patch.object(b.s,'run',side_effect=runner) as run,patch.object(b.s,'fresh_quota',b.s.fresh_quota),patch.object(b.s,'PARAMS',b.s.PARAMS.copy()),patch.object(b.s,'REQUEST_ID',b.s.REQUEST_ID),patch.object(b.s,'SOURCE',b.s.SOURCE),patch.object(b.s,'EVIDENCE',b.s.EVIDENCE):
            b.execute(b.SOURCES[0],Path('/unused'),Path('/unused'),{},'mock')
            run.assert_called_once()

    def test_batch_storage_checked_before_shared_runner(self):
        config={'plan':{'parameters':dict(b.s.PARAMS)},'ledger':{},'billing':{}}
        with patch.object(b,'prepare_config',return_value=(0,{},config)),patch.object(b.s,'admit'),patch.object(b.s,'artifact_preflight',return_value={'unexpired_repository_artifact_bytes':200_000_000}),patch.object(b.s,'run') as run,patch.object(b.s,'PARAMS',b.s.PARAMS.copy()),patch.object(b.s,'REQUEST_ID',b.s.REQUEST_ID),patch.object(b.s,'SOURCE',b.s.SOURCE),patch.object(b.s,'EVIDENCE',b.s.EVIDENCE):
            with self.assertRaisesRegex(b.s.n.ProbeError,'BATCH_STORAGE'):b.execute(b.SOURCES[0],Path('/unused'),Path('/unused'),{},'mock')
            run.assert_not_called()

    def test_workflow_serial_ten_minutes_no_media_copy(self):
        text=(b.ROOT.parent/'.github/workflows/remaining-openings-once.yml').read_text()
        self.assertEqual(text.count('timeout-minutes: 10'),3)
        self.assertIn('needs: [third_winner]',text);self.assertIn('needs: [third_winner, median]',text)
        self.assertEqual(text.count('gh run download'),3)
        self.assertNotIn('matrix:',text);self.assertNotIn('schedule:',text);self.assertNotIn('${{ runner.temp }}',text)
        for line in text.splitlines():
            if 'gh run download' in line:self.assertIn('remaining-opening-chain-',line)

if __name__=='__main__':unittest.main()
