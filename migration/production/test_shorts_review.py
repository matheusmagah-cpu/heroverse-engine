#!/usr/bin/env python3
"""Offline diagnostic preservation tests; no provider call or approval."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import shorts_review as sr
from structure_mining import ProviderFailure

class Diagnostics(unittest.TestCase):
    def test_allowlisted_failure_without_prose_or_credentials(self):
        error=ProviderFailure('HTTP_429_RESOURCE_EXHAUSTED:QUOTA',{'http_status':429,'provider_status':'RESOURCE_EXHAUSTED','message':'secret-password https://private.invalid/token','raw_body':'SECRET','body_bytes_read':12000,'body_parse_status':'JSON_ERROR_OBJECT','raw_body_retained':False,'sanitized':True})
        out=sr.failure_record(error)
        self.assertEqual(out['error_code'],'HTTP_429_RESOURCE_EXHAUSTED:QUOTA')
        self.assertEqual(out['provider_diagnostic']['http_status'],429)
        self.assertEqual(out['provider_diagnostic']['body_bytes_read'],8193)
        for forbidden in ['secret','https','private','SECRET','message']:
            self.assertNotIn(forbidden,json.dumps(out))
    def test_malformed_fields_are_not_copied(self):
        error=ProviderFailure('https://private.invalid/SECRET',{'http_status':'password','provider_status':'SECRET','body_parse_status':'SECRET','sanitized':'SECRET','body_bytes_read':True})
        out=sr.failure_record(error)
        self.assertEqual(out['error_code'],'UNKNOWN');self.assertEqual(out['provider_diagnostic'],{})
        self.assertNotIn('private',json.dumps(out))
    def test_main_preserves_failure_and_never_marks_it_publishable(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'shorts.json';path.write_text(json.dumps({'shorts':[{'file':'short-00.mp4','publish':False}]}))
            with patch.dict(sr.os.environ,{'HERO_GEMINI_API_KEY':'test-only'}),patch.object(sr.shorts_qa,'check',return_value={'status':'PASS'}),patch.object(sr,'review',side_effect=ProviderFailure('HTTP_503_UNAVAILABLE',{'http_status':503,'provider_status':'UNAVAILABLE'})):
                sr.main(d)
            rec=json.loads(path.read_text())['shorts'][0]
            self.assertFalse(rec['publish']);self.assertEqual(rec['review']['error_code'],'HTTP_503_UNAVAILABLE')
            self.assertEqual(rec['review']['status'],'NOT_REVIEWED_ProviderFailure')
    def test_review_contract_unchanged(self):
        self.assertEqual((sr.PASS_ITEM,sr.PASS_OVERALL),(7,8))
        self.assertEqual(sr.REVIEW_MODELS,('gemini-3.8-flash',))
        self.assertEqual(len(sr.RUBRIC),9)

if __name__=='__main__':unittest.main()
