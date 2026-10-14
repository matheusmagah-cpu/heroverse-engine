import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gemini_public_av import digest
import observe_public_av as observer

class RefinementWorkflowTests(unittest.TestCase):
    def run_stage(self,fail=False,gap=False,coarse=False):
        calls=[];checkpoints=[]
        def analyze(source,**kw):
            window=kw['window'];calls.append(window)
            if fail:return {'status':'FAILED_NO_AUTOMATIC_RETRY','failure_code':'SYNTHETIC_FAILURE'}
            start,end=window
            segments=[{'start_seconds':s,'end_seconds':min(s+20,end),
                'audio_summary':'Synthetic speech','visual_observation':'Synthetic image',
                'relationship':'Synthetic correspondence','mechanism':'Synthetic mechanism',
                'limitations':[]} for s in range(start,end,20)]
            receipt={'status':'WINDOW_AWAITING_AV_REVIEW','key':'public-av:'+digest(window),
                'window':window,'report':{'video_id':source['video_id'],
                'duration_seconds':1178,'coverage':'FULL_WINDOW','audio_received':True,
                'visual_received':True,'window_start_seconds':start,'window_end_seconds':end,
                'segments':segments,'limitations':[]}}
            if gap and window==(690,840):
                receipt.update(status='FAILED_NO_AUTOMATIC_RETRY',failure_code='REPORT_VALIDATION_FAILED',finish_reasons=['STOP'])
                receipt['report']['segments']=receipt['report']['segments'][:6]
                receipt['report']['segments'][-1]['end_seconds']=810.0
            if coarse and window==(690,840):
                receipt.update(status='FAILED_NO_AUTOMATIC_RETRY',failure_code='REPORT_VALIDATION_FAILED',finish_reasons=['STOP'])
                receipt['report']['segments']=receipt['report']['segments'][:6]+[{**receipt['report']['segments'][6],'end_seconds':840}]
            path=Path('migration/evidence')/('public-av-'+receipt['key'].split(':')[1]+'.json')
            path.write_text(json.dumps(receipt))
            return receipt
        class Ledger:
            def __init__(self,*args):pass
            def checkpoint(self,message):checkpoints.append(message)
            def reserve(self,*args):raise AssertionError('stub producer should not reserve')
            def persist(self,*args):raise AssertionError('stub producer should not persist')
        cwd=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp);Path('migration/evidence').mkdir(parents=True)
                observer.POLICY.write_text('{"model":"synthetic"}')
                with patch.dict(os.environ,GITHUB_RUN_ID='123'),patch.object(observer,'analyze',analyze),patch.object(observer,'ExistingObserverLedger',Ledger):
                    result=observer.refine_reference()
                artifacts=list(Path('migration/evidence').glob('focused-av-refinement-*'))
                return result,calls,checkpoints,len(artifacts)
            finally:os.chdir(cwd)
    def test_saved_json_tuple_array_roundtrip_is_valid_and_advances_sequentially(self):
        result,calls,checkpoints,count=self.run_stage()
        self.assertEqual(result,0);self.assertEqual(calls,[(130,270),(690,840),(840,900),(900,960),(960,1020),(1020,1040),(1040,1050)])
        self.assertEqual(len(checkpoints),1);self.assertEqual(count,1)
    def test_first_failure_blocks_later_windows_and_completion_receipt(self):
        result,calls,checkpoints,count=self.run_stage(fail=True)
        self.assertEqual(result,2);self.assertEqual(calls,[(130,270)])
        self.assertFalse(checkpoints);self.assertEqual(count,0)

    def test_incomplete_prefix_recovers_only_missing_seconds(self):
        result,calls,checkpoints,count=self.run_stage(gap=True)
        self.assertEqual(result,0)
        self.assertEqual(calls,[(130,270),(690,840),(810,830),(830,840),(840,900),(900,960),(960,1020),(1020,1040),(1040,1050)])
        self.assertEqual(len(checkpoints),2);self.assertEqual(count,1)

    def test_coarse_suffix_reuses_only_valid_detailed_prefix(self):
        result,calls,checkpoints,count=self.run_stage(coarse=True)
        self.assertEqual(result,0)
        self.assertIn((810,830),calls);self.assertIn((830,840),calls)
        self.assertEqual(calls.count((690,840)),1)
        self.assertEqual(count,1)

if __name__=='__main__':unittest.main()
