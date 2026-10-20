import unittest,copy,sys,tempfile,json,hashlib,gzip,subprocess
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
 def test_error_metrics_unverified_and_no_private_text(self):
  snapshot=ll.capture_existing([{'id':'a','snippet':{'title':'private title','description':'private text','publishedAt':'2020-01-01'},'status':{'privacyStatus':'private'}}],{'a':(None,2,3,4,5)},captured_at='t',start='s',end='e',analytics_status='ERROR')
  self.assertNotIn('private title',ll.canonical(snapshot));self.assertNotIn('private text',ll.canonical(snapshot))
  f=build_feedback([snapshot],{})
  row=next(o for o in f['videos'][0]['observations'] if o['kind']=='PRIVATE_REQUESTED_RANGE')
  self.assertEqual(row['basic_rows'][0]['views']['status'],'SOURCE_REPORTED_UNVERIFIED')
  self.assertIsNone(row['basic_rows'][0]['averageViewDuration']['value'])
 def test_file_pipeline_hashes_replay_and_tamper(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);out=root/'out'
   snapshot=ll.capture_existing([],{},captured_at='t',start='s',end='e',analytics_status='UNAVAILABLE')
   capture=ll.save_capture(snapshot,out);self.assertEqual(capture,ll.save_capture(snapshot,out))
   docs=[{}, {'id':'s','version':'v1','evidence':[]},{'videos':[]},{'rows':[]}]
   paths=[]
   for i,doc in enumerate(docs):
    p=root/f'{i}.json';p.write_text(ll.canonical(doc));paths.append(str(p))
   cli=subprocess.run([sys.executable,'-I','-B',str(Path(ll.__file__)),str(out),*paths],text=True,capture_output=True)
   self.assertEqual(cli.returncode,0,cli.stderr)
   first=json.loads(cli.stdout);second=ll.run(str(out),*paths)
   self.assertEqual(first,second)
   for src in first['source_records'].values():self.assertEqual(hashlib.sha256(Path(src['path']).read_bytes()).hexdigest(),src['sha256'])
   raw=gzip.decompress(Path(first['report']['path']).read_bytes());self.assertEqual(hashlib.sha256(raw).hexdigest(),first['report']['uncompressed_sha256'])
   self.assertEqual(len(list((out/'captures').iterdir())),1)
   capture.write_text('{}')
   with self.assertRaisesRegex(ValueError,'CAPTURE_HASH_MISMATCH'):ll.run(str(out),*paths)
 def test_output_aliases_cannot_overwrite_inputs(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);out=root/'out';snapshot={'owned_videos':[]};ll.save_capture(snapshot,out)
   ledger=out/'latest.json';ledger.write_text('{}');other=root/'source.json';other.write_text('{}')
   original=ledger.read_bytes()
   with self.assertRaisesRegex(ValueError,'INPUT_INSIDE_OUTPUT_ROOT'):ll.run(str(out),str(ledger),str(other),str(other),str(other))
   self.assertEqual(ledger.read_bytes(),original)
   alias=root/'alias.json';alias.symlink_to(ledger)
   with self.assertRaisesRegex(ValueError,'INPUT_INSIDE_OUTPUT_ROOT'):ll.run(str(out),str(alias),str(other),str(other),str(other))
   ledger.unlink();outside=root/'outside.json';outside.write_text('untouched');ledger.symlink_to(outside)
   with self.assertRaisesRegex(ValueError,'OUTPUT_ESCAPES_ROOT'):ll.run(str(out),str(other),str(other),str(other),str(other))
   self.assertEqual(outside.read_text(),'untouched');self.assertFalse((out/'sources').exists())
 def test_workflow_preserves_health_and_records_partial_failure(self):
  root=Path(__file__).resolve().parents[2];w=(root/'.github/workflows/goal-report.yml').read_text()
  self.assertLess(w.index('Content runway'),w.index('Compose existing evidence'))
  self.assertIn("steps.learning.outcome == 'failure'",w)
  self.assertNotIn('continue-on-error',w)
 def test_reference_cohort_preserved(self):
  root=Path(__file__).resolve().parents[2]
  structure=json.loads((root/'migration/structures/guided-prayer-scenic.json').read_bytes())
  audit=json.loads((root/'migration/evidence/vidiq/20261019/structure_audit.json').read_bytes())
  thumbs=json.loads((root/'migration/evidence/vidiq/20261019/thumbnails.json').read_bytes())
  src={k:{'path':k,'sha256':str(i)*64} for i,k in enumerate(('snapshot','ledger','structure','structure_audit','thumbnails'))}
  r=ll.compose({'owned_videos':[]},{},structure,audit,thumbs,feedback_builder=build_feedback,card_builder=build_report,sources=src)
  self.assertEqual(r['references']['cohort_counts'],{'winner':6,'weak':3})
  self.assertEqual(r['references']['thumbnail_reconciliation']['sample_size'],20)
if __name__=='__main__':unittest.main()
