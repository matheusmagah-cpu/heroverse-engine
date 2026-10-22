import json
import unittest
from verify_worker_oauth import CLIENT_ID,SCOPES,check_token

class WorkerOAuthTests(unittest.TestCase):
    def token(self):
        return {'type':'authorized_user','client_id':CLIENT_ID,'client_secret':'fixture-secret',
                'refresh_token':'fixture-refresh','token_uri':'https://oauth2.googleapis.com/token','scopes':sorted(SCOPES)}
    def test_missing_is_blocked(self):self.assertEqual('CLOUD_TOKEN_NOT_PROVISIONED',check_token(''))
    def test_incorrect_client_is_blocked(self):
        t=self.token();t['client_id']='wrong'
        self.assertEqual('EXISTING_CLIENT_ID_MISMATCH',check_token(json.dumps(t)))
    def test_scope_gap_blocked(self):
        t=self.token();t['scopes'].pop()
        self.assertEqual('REQUIRED_SCOPES_MISSING',check_token(json.dumps(t)))
    def test_foreign_endpoint_is_blocked_before_credentials_sent(self):
        t=self.token();t['token_uri']='https://untrusted.invalid/token'
        self.assertEqual('UNAPPROVED_TOKEN_ENDPOINT',check_token(json.dumps(t)))
    def test_metadata_is_not_access(self):
        self.assertEqual('EXISTING_CLIENT_ID_MISMATCH',check_token(json.dumps({'installed':{'client_id':CLIENT_ID}})))
    def test_refresh_token_required(self):
        t=self.token();t.pop('refresh_token')
        self.assertEqual('INCOMPLETE_AUTHORIZED_USER_TOKEN',check_token(json.dumps(t)))
    def test_valid_fixture_preflight_only(self):self.assertIsNone(check_token(json.dumps(self.token())))
    def test_original_google_serialization_without_type_is_accepted(self):
        t=self.token();t.pop('type');self.assertIsNone(check_token(json.dumps(t)))
    def test_invalid_json_blocked(self):
        for value in ('invalid','[]','null'):self.assertEqual('INVALID_TOKEN_JSON',check_token(value))

if __name__=='__main__':unittest.main()
