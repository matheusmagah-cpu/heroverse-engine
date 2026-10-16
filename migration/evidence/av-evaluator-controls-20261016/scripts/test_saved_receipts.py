#!/usr/bin/env python3
"""Offline regression checks for the saved, source-bound adjudication record."""
import json, shutil, tempfile, unittest
from pathlib import Path
import evaluate_saved_responses as evaluator

ROOT=Path(__file__).resolve().parents[1]
class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='av_receipt_test_')
        self.root=Path(self.temp.name)/'record'
        shutil.copytree(ROOT,self.root,ignore=shutil.ignore_patterns('__pycache__'))
    def tearDown(self): self.temp.cleanup()
    def change(self,relative,mutate):
        p=self.root/relative;data=json.loads(p.read_text());mutate(data)
        p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    def test_existing_receipts_reproduce(self):
        result=evaluator.evaluate(self.root,True)
        self.assertEqual(result['route_configuration_result'],'NOT_QUALIFIED')
        self.assertEqual(result['backend_ingestion'],'NOT_VERIFIED')
    def test_aligned_word_does_not_earn_synchrony_credit(self):
        d=json.loads((self.root/'receipts/c04-receipt.json').read_text())
        self.assertEqual(d['synchrony']['literal_relation_label_comparison'],'MATCH')
        self.assertEqual(d['synchrony']['capability_result'],'NOT_ESTABLISHED')
    def test_partial_correct_claims_are_preserved(self):
        c1=json.loads((self.root/'receipts/c01-receipt.json').read_text())
        c2=json.loads((self.root/'receipts/c02-receipt.json').read_text())
        c3=json.loads((self.root/'receipts/c03-receipt.json').read_text())
        self.assertEqual(c1['audio']['sound_presence_comparison'],'MATCH')
        self.assertEqual(c1['audio']['event_count_comparison'],'CONTRADICTION')
        self.assertEqual(c2['visual']['target_events_comparison'],'MATCH')
        self.assertEqual(c2['audio']['target_events_comparison'],'CONTRADICTION')
        self.assertEqual(c3['audio']['target_events_comparison'],'MATCH')
        self.assertEqual(c3['access']['backend_ingestion'],'NOT_VERIFIED')
    def test_missing_ai_authorship_rejected(self):
        self.change('operator-only/manual-adjudications.json',lambda x:x['c01'].pop('author_type'))
        with self.assertRaisesRegex(AssertionError,'AI authorship must be explicit'):evaluator.evaluate(self.root,True)
    def test_certified_human_review_claim_rejected(self):
        self.change('operator-only/manual-adjudications.json',lambda x:x['c01'].update(certified_human_review=True))
        with self.assertRaisesRegex(AssertionError,'human review must not be asserted'):evaluator.evaluate(self.root,True)
    def test_changed_frozen_manifest_rejected(self):
        p=self.root/'operator-only/manifest.json';p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(AssertionError,'Frozen input changed'):evaluator.evaluate(self.root,True)
    def test_changed_response_rejected(self):
        self.change('responses/c01-response.json',lambda x:x.update(response='Altered'))
        with self.assertRaisesRegex(AssertionError,'response changed'):evaluator.evaluate(self.root,True)
    def test_extra_response_rejected(self):
        shutil.copyfile(self.root/'responses/c01-response.json',self.root/'responses/c06-response.json')
        with self.assertRaisesRegex(AssertionError,'Unexpected response file count'):evaluator.evaluate(self.root,True)
    def test_retry_count_rejected(self):
        self.change('observations/ai-studio-observations.json',lambda x:x.update(repeat_inference_count=1))
        with self.assertRaisesRegex(AssertionError,'no repeated inference'):evaluator.evaluate(self.root,True)
    def test_nonexistent_evidence_quote_rejected(self):
        self.change('operator-only/manual-adjudications.json',lambda x:x['c01']['audio']['quoted_evidence'].append('Never said this'))
        with self.assertRaisesRegex(AssertionError,'missing evidence quote'):evaluator.evaluate(self.root,True)
    def test_changed_receipt_rejected(self):
        self.change('receipts/c01-receipt.json',lambda x:x.update(route_configuration_result='QUALIFIED'))
        with self.assertRaisesRegex(AssertionError,'Receipt mismatch'):evaluator.evaluate(self.root,True)

if __name__=='__main__':unittest.main(verbosity=2)
