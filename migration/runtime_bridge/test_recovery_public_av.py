import copy,hashlib,json,unittest
from gemini_public_av import analyze,ProviderFailure
from test_gemini_public_av import ManagerFixture,SOURCE,NOW,KEY,POLICY,REPORT

class OwnerRecoveryTests(unittest.TestCase):
    def fixture(self):
        m=ManagerFixture()
        args=dict(api_key=KEY,policy=POLICY,reserve=m.reserve,persist=m.persist,now=NOW,
            window=(0,10),refinement=True,research_context='CHRISTIAN_REST_MUSIC')
        def unavailable(*a):m.calls+=1;raise ProviderFailure('HTTP_503_UNAVAILABLE')
        prior=analyze(SOURCE,send=unavailable,**args)
        recovery={'attempt_id':'20261014-owner-market-503-recovery-1',
            'owner_request':'2026-10-14T13:38:01-03:00:resolve-problems',
            'prior_receipt':prior,'prior_receipt_sha256':'a'*64}
        report={**REPORT,'coverage':'FULL_WINDOW','window_start_seconds':0,'window_end_seconds':10,
            'segments':[{**REPORT['segments'][0],'start_seconds':0,'end_seconds':10}]}
        def success(*a):
            m.calls+=1;return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(report)}]}}]}
        return m,args,prior,recovery,success
    def test_new_owner_attempt_preserves_failure_and_replays_zero_calls(self):
        m,args,prior,recovery,success=self.fixture();old=copy.deepcopy(prior)
        recovered=analyze(SOURCE,recovery=recovery,send=success,**args)
        self.assertEqual(recovered['status'],'WINDOW_AWAITING_AV_REVIEW')
        self.assertNotEqual(recovered['key'],prior['key']);self.assertEqual(prior,old)
        self.assertEqual(analyze(SOURCE,recovery=recovery,send=success,**args),recovered)
        self.assertEqual(m.calls,2);self.assertEqual(len(m.saved),2)
        self.assertFalse(recovered['publication_authorized'])
    def test_quota_or_invalid_input_failure_cannot_use_transient_recovery(self):
        for code in ('HTTP_429_RESOURCE_EXHAUSTED','HTTP_400_INVALID_ARGUMENT','REPORT_VALIDATION_FAILED'):
            m,args,_,recovery,success=self.fixture();recovery['prior_receipt']['failure_code']=code
            with self.assertRaises(PermissionError):analyze(SOURCE,recovery=recovery,send=success,**args)
            self.assertEqual(m.calls,1)
    def test_changed_request_or_new_unbounded_attempt_is_rejected(self):
        m,args,_,recovery,success=self.fixture();recovery['attempt_id']='another-attempt'
        with self.assertRaises(PermissionError):analyze(SOURCE,recovery=recovery,send=success,**args)
        recovery['attempt_id']='20261014-owner-market-503-recovery-1'
        with self.assertRaises(PermissionError):analyze(SOURCE,recovery=recovery,send=success,**{**args,'window':(10,20)})
        self.assertEqual(m.calls,1)

if __name__=='__main__':unittest.main()
