import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from email.message import Message
import urllib.error
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe as p

MANIFEST = Path(__file__).resolve().parent / 'request.json'
KEY = 'OFFLINE_TEST_SECRET_NEVER_REAL_12345'

class Response:
    status = 200
    def __init__(self, body=b'{"videoId":"j2rk8ycXe3c","duration":12708}', **headers):
        self.body = body
        self.headers = Message()
        self.headers['Content-Type'] = 'application/json'
        for k,v in headers.items():
            self.headers[k] = v
        self.read_calls = []
    def geturl(self):
        return p.ENDPOINT + '?' + p.urllib.parse.urlencode(p.PARAMS)
    def read(self, n):
        self.read_calls.append(n)
        return self.body[:n]
    def __enter__(self): return self
    def __exit__(self, *args): pass

class Opener:
    def __init__(self, response=None, error=None):
        self.response = response or Response()
        self.error = error
        self.calls = []
    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error: raise self.error
        return self.response

class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name) / 'private'
        self.env = patch.dict(os.environ, {'GITHUB_RUN_NUMBER':'1', 'GITHUB_RUN_ATTEMPT':'1',
                                          'HERO_RAPIDAPI_KEY':KEY, 'GITHUB_REPOSITORY':p.REPOSITORY})
        self.env.start()
        self.capture = contextlib.redirect_stdout(io.StringIO())
        self.capture.__enter__()
    def tearDown(self):
        self.capture.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()
    def run_probe(self, opener=None): return p.run(MANIFEST, self.out, opener or Opener())
    def assert_blocked(self, opener, code):
        with self.assertRaisesRegex(p.Stop, '^' + code + '$'): self.run_probe(opener)
        self.assertLessEqual(len(opener.calls), 1)
        self.assertFalse((self.out / 'response.json').exists())
    def test_destination_headers_and_single_request(self):
        opener = Opener()
        receipt = self.run_probe(opener)
        self.assertEqual(len(opener.calls), 1)
        req, timeout = opener.calls[0]
        self.assertEqual(req.full_url, opener.response.geturl())
        self.assertEqual(req.get_method(), 'GET')
        self.assertEqual(req.get_header('X-rapidapi-host'), p.HOST)
        self.assertEqual(req.get_header('X-rapidapi-key'), KEY)
        self.assertEqual(timeout, 30)
        self.assertEqual(receipt['validation']['source_id_candidates'], ['match'])
        self.assertEqual(receipt['validation']['duration_12708_candidates'], ['match'])
        self.assertFalse(receipt['quota_usage_proven'])
        self.assertFalse(receipt['provider_billing_total_proven'])
    def test_unknown_schema_and_urls_private_only(self):
        url = 'https://private.invalid/signed?token=SECRET'
        body = json.dumps({url: url, 'data':[{'url':url}]}).encode()
        receipt = self.run_probe(Opener(Response(body)))
        self.assertNotIn(url, json.dumps(receipt))
        self.assertNotIn('SECRET', json.dumps(receipt))
        self.assertEqual((self.out/'response.json').read_bytes(), body)
        self.assertFalse(receipt['validation']['schema_verified'])
    def test_key_reflection_raw_and_escaped(self):
        for body in [json.dumps({'message':KEY}).encode(),
                     ('{"message":"'+''.join('\\u%04x'%ord(c) for c in KEY)+'"}').encode()]:
            with self.subTest(body=body):
                self.out = self.out.parent / str(len(body))
                self.assert_blocked(Opener(Response(body)), 'secret_echo_blocked')
    def test_hard_read_cap(self):
        response = Response(b' ' * (p.LIMIT+100))
        self.assert_blocked(Opener(response), 'response_size_blocked')
        self.assertEqual(response.read_calls, [p.LIMIT])
    def test_content_length_rejected_before_read(self):
        response = Response(**{'Content-Length':str(p.LIMIT+1)})
        self.assert_blocked(Opener(response), 'response_size_blocked')
        self.assertEqual(response.read_calls, [])
    def test_redirect_handler_never_follows(self):
        with self.assertRaisesRegex(p.Stop,'redirect_blocked'):
            p.NoRedirect().redirect_request(None,None,302,'secret',{},'https://evil.invalid')
    def test_changed_destination_rejected(self):
        response = Response()
        response.geturl = lambda:'https://evil.invalid/'
        self.assert_blocked(Opener(response), 'destination_changed')
    def test_http_error_body_not_read_or_logged(self):
        stream = io.BytesIO(KEY.encode())
        error = urllib.error.HTTPError(p.ENDPOINT,403,KEY,{},stream)
        self.assert_blocked(Opener(error=error),'http_error_blocked')
        self.assertEqual(stream.tell(),0)
        receipt=json.loads((self.out/'receipt.json').read_text())
        self.assertEqual(receipt['http_status'],403)
        self.assertEqual(receipt['request_attempt_count'],1)
        self.assertEqual(receipt['media_request_count'],0)
        self.assertEqual(receipt['native_response_file_count'],0)
        self.assertFalse(receipt['request_state_uncertain'])
        self.assertNotIn(KEY,json.dumps(receipt))
    def test_uncertain_failure_never_retries(self):
        opener = Opener(error=TimeoutError(KEY))
        self.assert_blocked(opener,'request_state_uncertain_no_rerun')
        with self.assertRaisesRegex(p.Stop,'already_claimed'): self.run_probe(opener)
        self.assertEqual(len(opener.calls),1)
    def test_permission_failure_is_sanitized(self):
        original = Path.open
        def deny_response(path, *args, **kwargs):
            if path.name == 'response.json':
                raise PermissionError(KEY)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', deny_response):
            self.assert_blocked(Opener(),'permission_error_no_rerun')
        receipt=json.loads((self.out/'receipt.json').read_text())
        self.assertEqual(receipt['result'],'permission_error_no_rerun')
        self.assertNotIn(KEY,json.dumps(receipt))
    def test_exact_repository_required(self):
        for repo in ('another/heroverse-engine', 'matheusmagah-cpu/other', ''):
            with patch.dict(os.environ, {'GITHUB_REPOSITORY':repo}):
                self.assert_blocked(Opener(),'repository_mismatch')
    def test_exact_https_endpoint(self):
        self.assertEqual(p.ENDPOINT,'https://youtube-media-downloader.p.rapidapi.com/v2/video/details')
        self.assertEqual(p.REPOSITORY,'matheusmagah-cpu/heroverse-engine')
    def test_http_error_quota_allowlist(self):
        headers=Message()
        headers['x-ratelimit-units-remaining']='97'
        headers['x-ratelimit-rapid-free-plans-hard-limit-remaining']='99'
        headers['x-ratelimit-units-reset']=KEY
        headers['server-message']=KEY
        opener=Opener(error=urllib.error.HTTPError(p.ENDPOINT,403,KEY,headers,io.BytesIO(KEY.encode())))
        self.assert_blocked(opener,'http_error_blocked')
        receipt=json.loads((self.out/'receipt.json').read_text())
        self.assertEqual(receipt['quota_headers'],{
            'x-ratelimit-units-remaining':97,
            'x-ratelimit-rapid-free-plans-hard-limit-remaining':99})
    def test_workflow_reruns_blocked(self):
        for name in ['GITHUB_RUN_NUMBER','GITHUB_RUN_ATTEMPT']:
            with patch.dict(os.environ,{name:'2'}):
                self.assert_blocked(Opener(),'one_shot_guard')
    def test_manifest_mutation_blocked(self):
        manifest = json.loads(MANIFEST.read_text())
        manifest['endpoint'] = 'https://evil.invalid'
        file = self.out.parent / 'changed.json'
        file.write_text(json.dumps(manifest))
        opener=Opener()
        with self.assertRaisesRegex(p.Stop,'request_manifest_mismatch'):
            p.run(file,self.out,opener)
        self.assertEqual(opener.calls,[])
    def test_quota_allowlist(self):
        response=Response(**{'x-ratelimit-requests-remaining':'97',
                             'x-ratelimit-requests-reset':KEY,'x-secret':KEY})
        receipt=self.run_probe(Opener(response))
        self.assertEqual(receipt['quota_headers'],{'x-ratelimit-requests-remaining':97})
        self.assertFalse(receipt['quota_usage_proven']) # fixture is not live evidence
    def test_login_challenge_stops(self):
        self.assert_blocked(Opener(Response(b'{"message":"login required"}')),'access_challenge_blocked')
    def test_invalid_json_stops(self):
        self.assert_blocked(Opener(Response(b'not json')),'invalid_json')
    def test_mismatch_is_reported_without_asserting_schema(self):
        receipt=self.run_probe(Opener(Response(b'{"videoId":"other","duration":"03:31:48"}')))
        self.assertEqual(receipt['validation']['source_id_candidates'],['mismatch'])
        self.assertEqual(receipt['validation']['duration_12708_candidates'],['unverified'])
        self.assertFalse(receipt['validation']['native_media_candidate_verified'])

if __name__ == '__main__': unittest.main()
