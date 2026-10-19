import unittest
from vidiq_credit_policy import decide

class CreditPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now='2026-10-13T20:00:00Z'
        self.balance={'remaining':21,'observed_at':self.now,'renews_at':'2026-11-03T16:42:50.024390Z'}
        self.request={'routine':False,'critical_gap':True,'free_alternatives_exhausted':True,
                      'request_id':'research-001','maximum_credit_cost':5}
    def test_current_balance_blocked(self):
        self.assertEqual(decide(self.request,self.balance,self.now)['reason'],'EXISTING_25_CREDIT_RESERVE')
    def test_routine_even_after_renewal_blocked(self):
        self.balance['remaining']=150;self.request['routine']=True
        self.assertFalse(decide(self.request,self.balance,self.now)['allowed'])
    def test_exact_reserve_allowed(self):
        self.balance['remaining']=30
        self.assertTrue(decide(self.request,self.balance,self.now)['allowed'])
    def test_duplicate_blocked(self):
        self.balance['remaining']=150
        self.assertFalse(decide(self.request,self.balance,self.now,already_requested=True)['allowed'])
    def test_unknown_negative_boolean_nan_cost_blocked(self):
        for value in (None,-1,True,float('nan')):
            self.request['maximum_credit_cost']=value
            self.assertFalse(decide(self.request,self.balance,self.now)['allowed'])
    def test_stale_and_renewal_require_read(self):
        self.balance['remaining']=150
        for now in ('2026-10-13T21:00:01Z','2026-11-03T16:42:50.024390Z'):
            self.assertEqual(decide(self.request,self.balance,now)['reason'],'BALANCE_RECHECK_REQUIRED')
    def test_missing_proven_need_blocked(self):
        self.balance['remaining']=150;self.request['free_alternatives_exhausted']=False
        self.assertFalse(decide(self.request,self.balance,self.now)['allowed'])
    def test_naive_time_and_missing_id_blocked(self):
        self.balance['remaining']=150
        self.assertFalse(decide(self.request,self.balance,'2026-10-13T20:00:00')['allowed'])
        self.request.pop('request_id')
        self.assertFalse(decide(self.request,self.balance,self.now)['allowed'])

if __name__=='__main__':unittest.main()
