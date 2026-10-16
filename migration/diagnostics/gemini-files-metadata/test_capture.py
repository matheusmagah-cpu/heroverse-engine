import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import capture as c

KEY = 'test-key-offline-1234567890'
HASH = '5562d675416107eb9ec70643edd43e5375b85aa74051730f1d357a88d34e79df'
ENV = {'GITHUB_REPOSITORY':'matheusmagah-cpu/heroverse-engine', 'HERO_REPOSITORY_PRIVATE':'true',
       'GITHUB_REF':'refs/heads/main', 'GITHUB_EVENT_NAME':'workflow_dispatch', 'GITHUB_RUN_NUMBER':'1',
       'GITHUB_RUN_ATTEMPT':'1', 'GITHUB_SHA':'d'*40,
       'GITHUB_WORKFLOW_REF':'matheusmagah-cpu/heroverse-engine/.github/workflows/gemini-files-metadata-once.yml@refs/heads/main',
       'HERO_GEMINI_API_KEY':KEY}
META = {'name':c.FILE_NAME, 'state':'ACTIVE', 'mimeType':'video/mp4', 'sizeBytes':'19083',
        'sha256Hash':base64.b64encode(bytes.fromhex(HASH)).decode(),
        'videoMetadata':{'videoDuration':'6s'}, 'createTime':'2026-10-16T01:24:40.123456Z',
        'expirationTime':'2026-10-18T01:24:40.123456Z'}

class Response:
    status = 200
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self, size): return self.body[:size]

class Tests(unittest.TestCase):
    def setUp(self): self.prior = c.PRIOR.read_bytes()
    def main_run(self, meta=META, error=None, env=None, prior=None):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); prior_path = root/'prior.json'; prior_path.write_bytes(prior or self.prior)
        output = root/'out'
        with patch.object(c,'OUTPUT',output), patch.object(c,'PRIOR',prior_path), patch.dict(os.environ,env or ENV,clear=True), patch.object(c.sys,'argv',['capture.py']), patch.object(c,'get_metadata',return_value=meta,side_effect=error) as send, contextlib.redirect_stdout(io.StringIO()) as log:
            result = c.main()
        receipt = json.loads((output/'receipt.json').read_text()) if (output/'receipt.json').exists() else None
        return result,receipt,send,log.getvalue(),output
    def test_boundary(self): c.boundary(ENV)
    def test_negative_guards(self):
        for k,v in [('GITHUB_REPOSITORY','x/y'),('HERO_REPOSITORY_PRIVATE','false'),('GITHUB_REF','refs/heads/dev'),('GITHUB_EVENT_NAME','push'),('GITHUB_RUN_NUMBER','2'),('GITHUB_RUN_ATTEMPT','2'),('GITHUB_SHA','invalid'),('GITHUB_WORKFLOW_REF',ENV['GITHUB_WORKFLOW_REF']+'x')]:
            with self.subTest(k=k), self.assertRaises(c.ProviderFailure): c.boundary({**ENV,k:v})
    def test_prior_exact_bytes(self): self.assertEqual(hashlib.sha256(self.prior).hexdigest(),c.PRIOR_SHA256)
    def test_prior_tamper_no_call(self):
        result,_,send,_,_=self.main_run(prior=self.prior+b' ');self.assertEqual(result,1);send.assert_not_called()
    def test_guard_no_call(self):
        result,_,send,_,_=self.main_run(env={**ENV,'GITHUB_RUN_NUMBER':'2'});self.assertEqual(result,1);send.assert_not_called()
    def test_malformed_secret_no_call(self):
        result,r,send,log,_=self.main_run(env={**ENV,'HERO_GEMINI_API_KEY':''});self.assertEqual(result,1);self.assertEqual(r['metadata_get_calls'],0);send.assert_not_called()
    def test_capture_not_success(self):
        result,r,send,log,_=self.main_run();self.assertEqual(result,0);send.assert_called_once_with(KEY)
        self.assertEqual(r['raw_file_metadata'],META);self.assertEqual(r['status'],'METADATA_CAPTURED_NOT_RECONCILED')
        self.assertEqual(r['delivery_verdict'],'BLOCKED_PENDING_HASH_RECONCILIATION');self.assertEqual(r['metadata_get_calls'],1)
        for k in ['upload_start_calls','bytes_upload_calls','generate_content_calls','count_tokens_calls','delete_calls','billing_changes']:self.assertEqual(r[k],0)
        self.assertNotIn(KEY,json.dumps(r)+log)
    def test_preserve_both_hash_representations_without_interpretation(self):
        for raw in (bytes.fromhex(HASH),HASH.encode()):
            v=base64.b64encode(raw).decode();r=c.project_metadata({**META,'sha256Hash':v},KEY);self.assertEqual(r['sha256Hash'],v)
    def test_missing_metadata_fields_not_fabricated(self):
        r=c.project_metadata({'name':c.FILE_NAME},KEY);self.assertIsNone(r['sha256Hash']);self.assertIsNone(r['videoMetadata']['videoDuration'])
    def test_identity_rejected(self):
        for name in ('files/other','https://evil.invalid',None):
            with self.assertRaises(c.ProviderFailure):c.project_metadata({**META,'name':name},KEY)
    def test_only_whitelist(self):
        r=c.project_metadata({**META,'downloadUri':KEY,'uri':KEY,'displayName':KEY,'error':KEY,'videoMetadata':{'videoDuration':'6s','other':KEY}},KEY)
        self.assertEqual(r,META);self.assertNotIn(KEY,json.dumps(r))
    def test_bad_field_shapes(self):
        for field,value in [('sha256Hash',{}),('sha256Hash','x'*257),('state','arbitrary'),('mimeType','https://evil.invalid'),('sizeBytes',19083),('expirationTime','nonsense'),('videoMetadata',[])]:
            with self.subTest(field=field),self.assertRaises(c.ProviderFailure):c.project_metadata({**META,field:value},KEY)
    def test_credential_echo_rejected(self):
        with self.assertRaises(c.ProviderFailure):c.project_metadata({**META,'sha256Hash':KEY},KEY)
    def test_main_error_redacted_and_one_call(self):
        result,r,send,log,_=self.main_run(error=RuntimeError(KEY));self.assertEqual(result,1);send.assert_called_once();self.assertNotIn(KEY,json.dumps(r)+log);self.assertEqual(r['metadata_get_calls'],1)
    def test_replay_blocked_preserves_receipt(self):
        _,r,_,_,out=self.main_run();before=(out/'receipt.json').read_bytes()
        with patch.object(c,'OUTPUT',out),patch.object(c.sys,'argv',['capture.py']),patch.object(c,'get_metadata') as send,contextlib.redirect_stdout(io.StringIO()):self.assertEqual(c.main(),1)
        send.assert_not_called();self.assertEqual(before,(out/'receipt.json').read_bytes())
    def test_claim_only_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'attempt-claim.json').write_text('{}')
            with patch.object(c,'OUTPUT',out),patch.object(c.sys,'argv',['capture.py']),patch.object(c,'get_metadata') as send,contextlib.redirect_stdout(io.StringIO()):self.assertEqual(c.main(),1)
            send.assert_not_called();self.assertFalse((out/'receipt.json').exists())
    def test_checkpoint_failure_prevents_get(self):
        with patch.object(c.os,'replace',side_effect=OSError(KEY)):
            result,r,send,log,_=self.main_run()
        self.assertEqual(result,1);send.assert_not_called();self.assertNotIn(KEY,log)
        self.assertIn('CHECKPOINT_FAILED_NO_RETRY',log)
    def test_transport_fixed_get_no_body_proxy_or_redirect(self):
        with patch.dict(os.environ,{'HTTP_PROXY':'http://evil.invalid','HTTPS_PROXY':'http://evil.invalid','ALL_PROXY':'http://evil.invalid'}),patch.object(c.urllib.request,'build_opener') as build:
            build.return_value.open.return_value=Response(json.dumps(META).encode());self.assertEqual(c.get_metadata(KEY),META)
            build.return_value.open.assert_called_once();request=build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url,'https://generativelanguage.googleapis.com/v1beta/files/qe6pn3aifbkw');self.assertEqual(request.get_method(),'GET');self.assertIsNone(request.data)
            self.assertEqual(request.get_header('X-goog-api-key'),KEY);self.assertEqual(build.call_args.args[0].proxies,{})
            self.assertIsInstance(build.call_args.args[1],c.NoRedirect);self.assertEqual(build.return_value.open.call_args.kwargs,{'timeout':20})
    def test_transport_http_errors_one_call_redacted(self):
        for status in (301,302,303,307,308,403,404,429,503):
            with patch.object(c.urllib.request,'build_opener') as build:
                build.return_value.open.side_effect=urllib.error.HTTPError(c.URL,status,KEY,{},None)
                with self.assertRaises(c.ProviderFailure) as raised:c.get_metadata(KEY)
                self.assertEqual(raised.exception.code,'HTTP_'+str(status));build.return_value.open.assert_called_once()
    def test_actual_redirect_handler_never_follows(self):
        for status in (301,302,303,307,308):
            handler=c.NoRedirect(); parent=unittest.mock.Mock();handler.add_parent(parent)
            request=urllib.request.Request(c.URL,headers={'x-goog-api-key':KEY})
            self.assertIsNone(handler.http_error_302(request,io.BytesIO(),status,'redirect',{'location':'https://evil.invalid'}))
            parent.open.assert_not_called()
    def test_transport_response_errors_redacted(self):
        for raw in (b'x'*(c.MAX_RESPONSE+1),b'not json '+KEY.encode()):
            with patch.object(c.urllib.request,'build_opener') as build:
                build.return_value.open.return_value=Response(raw)
                with self.assertRaises(c.ProviderFailure) as raised:c.get_metadata(KEY)
                self.assertNotIn(KEY,raised.exception.code);build.return_value.open.assert_called_once()
    def test_deadline_and_network_errors(self):
        for error in (TimeoutError(KEY),c.ProviderFailure('METADATA_GET_DEADLINE')):
            with patch.object(c.urllib.request,'build_opener') as build:
                build.return_value.open.side_effect=error
                with self.assertRaises(c.ProviderFailure) as raised:c.get_metadata(KEY)
                self.assertNotIn(KEY,raised.exception.code);build.return_value.open.assert_called_once()
    def test_no_arguments(self):
        with patch.object(c.sys,'argv',['capture.py','https://evil.invalid']),patch.object(c,'get_metadata') as send,contextlib.redirect_stdout(io.StringIO()):self.assertEqual(c.main(),1)
        send.assert_not_called()

if __name__=='__main__':unittest.main()
