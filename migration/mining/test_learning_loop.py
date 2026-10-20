import unittest,copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));import learning_loop as ll

from owned_feedback import build_feedback
from video_analysis_card import build_report
class Tests(unittest.TestCase):
 def test_capture_missing_not_zero(self):
  s=ll.capture_existing([{'id':'a','status':{'privacyStatus':'private'}}],{'a':('LONG_FORM_CONTENT',2,3,4,1)},captured_at='2026-10-20T00:00:00Z',start='2025-10-20',end='2026-10-20',analytics_status='OBSERVED')
  self.assertEqual(s['owned_videos'][0]['statistics'],{});self.assertIsNone(s['owned_private'][0]['reach']['ctr']);self.assertFalse(s['coverage']['exact_checkpoint']);self.assertEqual(s['additional_api_calls'],0)
 def test_real_adapters_hold_deterministic_no_public_inference(self):
  snapshot=ll.capture_existing([],{},captured_at='2026-10-20T00:00:00Z',start='2025-10-20',end='2026-10-20',analytics_status='UNAVAILABLE')
  ledger={'entries':{'pilot:x':{'video_id':'a','uploaded_at':'now','slot':'later'}}}
  sources={k:{'path':k,'sha256':str(i)*64} for i,k in enumerate(('snapshot','ledger','structure','structure_audit','thumbnails'))}
  args=(snapshot,ledger,{'id':'s','version':'v1','evidence':[]},{'videos':[]},{'rows':[]})
  before=copy.deepcopy(args)
  a=ll.compose(*args,feedback_builder=build_feedback,card_builder=build_report,sources=sources)
  b=ll.compose(*args,feedback_builder=build_feedback,card_builder=build_report,sources=sources)
  self.assertEqual(ll.canonical(a),ll.canonical(b));self.assertEqual(args,before)
  self.assertEqual(a['decision']['evidence_decision'],'HOLD');self.assertIsNone(a['pipeline'][0]['public_observation']);self.assertFalse(a['brief']['script_mutation'])
if __name__=='__main__':unittest.main()
