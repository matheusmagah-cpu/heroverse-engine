import io
import os
import subprocess
import tempfile
import textwrap
import json
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
import run_existing_reach_probe as w
import existing_reach_probe as c

class Response(io.BytesIO):
    def __init__(self,url,value,status=200):
        super().__init__(json.dumps(value).encode());self.url=url;self.status=status;self.headers={}
    def geturl(self):return self.url

class Opener:
    def __init__(self,value=None):self.calls=[];self.value=value or {'ok':True}
    def open(self,req,timeout):
        self.calls.append((req,timeout));return Response(req.full_url,self.value)

def observe(raw,renew):return renew(raw),{'status':'REFRESH_PASSED_IDENTITY_NOT_YET_OBSERVED'}
def info():return json.dumps({'client_id':'synthetic-client','client_secret':'synthetic-secret','refresh_token':'synthetic-refresh','scopes':[w.READ_SCOPE]})

class Tests(unittest.TestCase):
    def test_refresh_once_without_scope_or_persistence(self):
        op=Opener({'access_token':'synthetic-access','token_type':'Bearer','expires_in':3600,'scope':w.READ_SCOPE})
        t=w.Transport(op);token,health=w.refresh_once(info(),t,observe,lambda _:None)
        self.assertEqual(token,'synthetic-access');self.assertEqual(t.counts['token_refresh'],1)
        req=op.calls[0][0];self.assertEqual(req.full_url,w.TOKEN_URL);self.assertEqual(req.get_method(),'POST')
        self.assertNotIn(b'scope=',req.data);self.assertFalse(req.has_header('Authorization'))
        with self.assertRaises(c.ProbeBlocked):w.refresh_once(info(),t,observe,lambda _:None)
        self.assertEqual(len(op.calls),1)
    def test_invalid_config_before_network(self):
        t=w.Transport(Opener())
        with self.assertRaises(c.ProbeBlocked):w.refresh_once(info(),t,observe,lambda _:'BAD_CONFIG')
        self.assertFalse(t.opener.calls)
    def test_returned_scope_expansion_blocks(self):
        op=Opener({'access_token':'synthetic-access','token_type':'Bearer','expires_in':3600,'scope':w.READ_SCOPE+' new-scope'})
        with self.assertRaises(c.ProbeBlocked):w.refresh_once(info(),w.Transport(op),observe,lambda _:None)
    def test_expired_and_injected_token_rejected(self):
        for token,seconds in [('ok',30),('bad\nvalue',3600)]:
            op=Opener({'access_token':token,'token_type':'Bearer','expires_in':seconds})
            with self.assertRaises(c.ProbeBlocked):w.refresh_once(info(),w.Transport(op),observe,lambda _:None)
    def test_only_exact_metadata_get_no_retries(self):
        op=Opener();t=w.Transport(op);url=w.META_BASE+c.FETCH_REPORT_IDS[0]
        t.json(url,'report_metadata',bearer='synthetic-access')
        self.assertEqual(op.calls[0][0].get_method(),'GET')
        self.assertEqual(op.calls[0][0].get_header('Authorization'),'Bearer synthetic-access')
        with self.assertRaises(c.ProbeBlocked):t.json(url,'report_metadata',bearer='synthetic-access')
        self.assertEqual(len(op.calls),1)
        self.assertNotIn('synthetic-access',json.dumps(t.events))
    def test_target_rejections_before_send(self):
        t=w.Transport(Opener())
        for url,stage in [('https://evil.invalid','report_metadata'),('https://oauth2.googleapis.com.evil/token','token_refresh'),('https://youtubereporting.googleapis.com/v1/jobs','report_metadata')]:
            with self.assertRaises(c.ProbeBlocked):t.open(url,stage,bearer='fake')
        self.assertFalse(t.opener.calls)
    def test_redirect_handler_never_forwards(self):
        with self.assertRaises(c.ProbeBlocked):w.NoRedirect().redirect_request(None,None,302,'',{},'https://evil.invalid')
    def test_http_401_one_attempt_sanitized(self):
        class Unauthorized(Opener):
            def open(self,req,timeout):
                self.calls.append(req);raise urllib.error.HTTPError(req.full_url,401,'secret detail',{},io.BytesIO(b'secret'))
        op=Unauthorized();t=w.Transport(op)
        with self.assertRaisesRegex(c.ProbeBlocked,'^HTTP_STATUS_401$'):t.json(w.META_BASE+c.FETCH_REPORT_IDS[0],'report_metadata',bearer='fake')
        self.assertEqual(len(op.calls),1);self.assertEqual(t.events[0]['http_status'],401)
    def test_preflight_attempt_guards(self):
        env={'HERO_REPOSITORY_PRIVATE':'true','GITHUB_REF':'refs/heads/main','GITHUB_REPOSITORY':w.REPOSITORY,'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_NUMBER':'5','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'123'}
        with self.assertRaisesRegex(c.ProbeBlocked,'ONE_EXECUTION'):w.preflight(Path('.'),env)
    def test_response_origin_and_large_json_block(self):
        class Wrong(Opener):
            def open(self,req,timeout):return Response('https://evil.invalid',{})
        with self.assertRaises(c.ProbeBlocked):w.Transport(Wrong()).json(w.META_BASE+c.FETCH_REPORT_IDS[0],'report_metadata',bearer='fake')
        with self.assertRaises(c.ProbeBlocked):w.Transport(Opener({'large':'x'*65536})).json(w.META_BASE+c.FETCH_REPORT_IDS[0],'report_metadata',bearer='fake')

    def test_boundary_accepts_only_exact_private_main(self):
        env={'GITHUB_REPOSITORY':w.REPOSITORY,'HERO_REPOSITORY_PRIVATE':'true','GITHUB_REF':'refs/heads/main'}
        self.assertTrue(w.validate_execution_boundary(env)['repository_private'])
        for field,bad in [('GITHUB_REPOSITORY','another/heroverse-engine'),('GITHUB_REPOSITORY','matheusmagah-cpu/other'),('HERO_REPOSITORY_PRIVATE','false'),('HERO_REPOSITORY_PRIVATE','True'),('GITHUB_REF','refs/heads/test'),('GITHUB_REF','refs/tags/main'),('GITHUB_REF','refs/pull/1/merge')]:
            changed=dict(env);changed[field]=bad
            with self.assertRaises(c.ProbeBlocked):w.validate_execution_boundary(changed)
        for field in env:
            changed=dict(env);del changed[field]
            with self.assertRaises(c.ProbeBlocked):w.validate_execution_boundary(changed)
    def test_boundary_failure_precedes_resources_or_network(self):
        with patch.object(w.shutil,'disk_usage',side_effect=AssertionError('should not run')):
            with self.assertRaisesRegex(c.ProbeBlocked,'PRIVATE_REPOSITORY_REQUIRED'):
                w.preflight(Path('.'),{'GITHUB_REPOSITORY':w.REPOSITORY,'HERO_REPOSITORY_PRIVATE':'false','GITHUB_REF':'refs/heads/main'})
    def test_workflow_gates_job_secret_and_upload(self):
        local=Path(__file__).parent/'owned-reach-existing-once.yml'
        path=local if local.exists() else Path('.github/workflows/owned-reach-existing-once.yml')
        text=path.read_text()
        boundary="github.repository == 'matheusmagah-cpu/heroverse-engine' && github.event.repository.private == true && github.ref == 'refs/heads/main'"
        self.assertEqual(text.count(boundary),3)
        self.assertIn("if: success() && steps.boundary.outputs.accepted == 'true' && "+boundary,text)
        self.assertIn("if: always() && steps.boundary.outputs.accepted == 'true' && "+boundary,text)
        self.assertEqual(text.count('secrets.HERO_YT_AUTHORIZED_USER_JSON'),1)
        self.assertLess(text.index('test "$REPOSITORY_PRIVATE" = true'),text.index('secrets.HERO_YT_AUTHORIZED_USER_JSON'))
        self.assertIn('HERO_REPOSITORY_PRIVATE: ${{ github.event.repository.private }}',text)

    def test_shell_boundary_negative_cases_never_accept(self):
        local=Path(__file__).parent/'owned-reach-existing-once.yml'
        path=local if local.exists() else Path('.github/workflows/owned-reach-existing-once.yml')
        script=textwrap.dedent(path.read_text().split('        run: |\n',1)[1].split('      - uses:',1)[0])
        base={'REPOSITORY':w.REPOSITORY,'REPOSITORY_PRIVATE':'true','REF':'refs/heads/main','EVENT':'workflow_dispatch','RUN_NUMBER':'4','RUN_ATTEMPT':'1'}
        cases=[None,('REPOSITORY','other/fork'),('REPOSITORY_PRIVATE','false'),('REPOSITORY_PRIVATE',''),('REF','refs/heads/feature'),('REF','refs/tags/main')]
        for case in cases:
            with tempfile.TemporaryDirectory() as temp:
                dest=Path(temp)/'output';env=dict(base)
                if case:env[case[0]]=case[1]
                env.update(PATH=os.defpath,GITHUB_OUTPUT=str(dest))
                result=subprocess.run(['bash','-e','-c',script],env=env,capture_output=True,text=True)
                if case:
                    self.assertNotEqual(result.returncode,0)
                    self.assertFalse(dest.exists())
                else:
                    self.assertEqual(result.returncode,0)
                    self.assertEqual(dest.read_text(),'accepted=true\n')

if __name__=='__main__':unittest.main(verbosity=2)
