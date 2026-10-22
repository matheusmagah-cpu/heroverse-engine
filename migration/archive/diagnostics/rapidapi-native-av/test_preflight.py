import unittest
from preflight import quota_headers, safe_public_schemas
from connection_probe import ProbeError

class PreflightTests(unittest.TestCase):
    def test_only_numeric_quota_headers_survive(self):
        headers={'X-RateLimit-units-Remaining':'498','X-RateLimit-units-Limit':'500','Mcp-Session-Id':'private',
                 'X-RateLimit-other-Remaining':'secret-value','Set-Cookie':'private'}
        self.assertEqual(quota_headers(headers), {'x-ratelimit-units-remaining':'498','x-ratelimit-units-limit':'500'})

    def test_reflected_credential_cannot_enter_public_schema(self):
        key='local-fake-private-key'
        tools=[{'name':n,'inputSchema':{'type':'object','description':key},'private':key} for n in ('download','progress','info')]
        result=safe_public_schemas({'tools':tools},key)
        self.assertNotIn(key,str(result))
        self.assertNotIn('private',str(result))

    def test_duplicate_or_missing_tool_stops_before_info(self):
        for names in [('download','download','info'),('download','progress')]:
            with self.assertRaises(ProbeError):
                safe_public_schemas({'tools':[{'name':n,'inputSchema':{}} for n in names]},'fake-key')

if __name__ == '__main__': unittest.main()
