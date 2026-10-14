import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import oauth_health as health
import durable_evidence_checkpoint as checkpoint

def token():
    from verify_worker_oauth import CLIENT_ID,SCOPES
    return json.dumps({'type':'authorized_user','client_id':CLIENT_ID,'client_secret':'TEST_SECRET_NEVER_EXPORTED',
        'refresh_token':'TEST_REFRESH_NEVER_EXPORTED','scopes':sorted(SCOPES)})

class OAuthHealthTests(unittest.TestCase):
    def test_missing_token_never_contacts_provider(self):
        called=[];credentials,result=health.observe_refresh('',lambda v:called.append(v))
        self.assertIsNone(credentials);self.assertEqual(called,[])
        self.assertEqual(result['failure_code'],'CLOUD_TOKEN_NOT_PROVISIONED')
        health.validate_health(result)
    def test_invalid_grant_is_recorded_without_sensitive_exception(self):
        def renew(raw):raise Exception('TEST_SECRET_NEVER_EXPORTED',{'error':'invalid_grant','error_description':'TEST_REFRESH_NEVER_EXPORTED'})
        credentials,result=health.observe_refresh(token(),renew)
        self.assertIsNone(credentials);self.assertEqual(result['status'],'AUTHORIZATION_ACTION_REQUIRED')
        self.assertNotIn('TEST_SECRET',json.dumps(result));self.assertNotIn('TEST_REFRESH',json.dumps(result))
        health.validate_health(result)
    def test_transient_failure_does_not_claim_revocation(self):
        def renew(raw):raise TimeoutError('TEST_SECRET_NEVER_EXPORTED')
        _,result=health.observe_refresh(token(),renew)
        self.assertEqual(result['status'],'REFRESH_UNAVAILABLE');health.validate_health(result)
    def test_success_requires_exact_identity_and_never_approves_console(self):
        credentials,result=health.observe_refresh(token(),lambda v:object())
        self.assertIsNotNone(credentials)
        with self.assertRaises(PermissionError):health.identity_health(result,'foreign','UCuMF6pJQkyMzaVoAxFL86yA')
        final=health.identity_health(result,'UCuMF6pJQkyMzaVoAxFL86yA','UCuMF6pJQkyMzaVoAxFL86yA')
        health.validate_health(final);self.assertFalse(final['production_ready'])
        self.assertEqual(final['console_publishing_status'],'UNOBSERVED')
    def test_unexpected_secret_field_cannot_be_checkpointed(self):
        value=health.record('REFRESH_UNAVAILABLE');value['client_secret']='unexpected'
        with self.assertRaises(ValueError):health.validate_health(value)
    def test_failed_authorization_closes_claim_and_preserves_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd=os.getcwd()
            try:
                os.chdir(folder);Path('migration/evidence').mkdir(parents=True);Path('cloud-evidence').mkdir()
                Path('migration/evidence/observer-claim.json').write_text('{"run_id":"123"}')
                c=sqlite3.connect('cloud-evidence/quota-ledger.sqlite3')
                for name in ['general_quota_debits','upload_quota_debits','composed_quota_reservations']:
                    c.execute('CREATE TABLE '+name+' (id INTEGER PRIMARY KEY)')
                c.execute('INSERT INTO general_quota_debits VALUES (7)');c.commit();c.close()
                _,result=health.observe_refresh('',lambda v:None)
                Path('cloud-evidence/oauth-health.json').write_text(json.dumps(result))
                with patch.dict(os.environ,{'GITHUB_REPOSITORY':'matheusmagah-cpu/heroverse-engine','GITHUB_RUN_ID':'123'}),patch.object(checkpoint,'git',return_value=''):
                    checkpoint.main('checkpoint')
                self.assertFalse(Path('migration/evidence/observer-claim.json').exists())
                self.assertEqual(Path('migration/evidence/observer-auth-health.json').read_bytes(),Path('migration/evidence/observer-auth-health-123.json').read_bytes())
                self.assertIn('VALUES(7)',Path('migration/evidence/observer-ledger.sql').read_text())
            finally:os.chdir(cwd)

if __name__=='__main__':unittest.main()
