import io
import json
import unittest
from connection_probe import Client, NoRedirect, ProbeError, probe, read_reply


class Response(io.BytesIO):
    def __init__(self, value, status=200, headers=None):
        super().__init__(value)
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}


class FakeOpener:
    def __init__(self, responses):
        self.responses, self.requests = iter(responses), []

    def open(self, req, timeout):
        self.requests.append(req)
        return next(self.responses)


class ProbeTests(unittest.TestCase):
    def test_negotiated_session_headers_and_zero_media_calls(self):
        first = Response(json.dumps({"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26","capabilities":{"tools":{}}}}).encode(), headers={"Content-Type":"application/json","Mcp-Session-Id":"private-session"})
        listing = Response(b'{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"download"}]}}')
        opener = FakeOpener([first, Response(b"", status=202), listing])
        result = probe("fake-local-test-key", opener)
        self.assertEqual(result["status"], "MCP_TRANSPORT_AND_TOOL_LIST_VERIFIED")
        self.assertFalse(result["native_video_verified"])
        self.assertFalse(result["owner_entitlement_verified_by_this_probe"])
        self.assertNotIn("private-session", json.dumps(result))
        self.assertNotIn("fake-local-test-key", json.dumps(result))
        sent = [json.loads(r.data)["method"] for r in opener.requests]
        self.assertEqual(sent, ["initialize","notifications/initialized","tools/list"])
        self.assertEqual(opener.requests[1].get_header("Mcp-session-id"), "private-session")
        self.assertEqual(opener.requests[2].get_header("Mcp-protocol-version"), "2025-03-26")
        self.assertEqual(opener.requests[0].get_header("X-api-host"), "youtube-info-download-api.p.rapidapi.com")

    def test_sse_skips_notifications_and_stops_at_matching_response(self):
        raw = b'data: {"jsonrpc":"2.0","method":"notifications/message"}\n\ndata: {"jsonrpc":"2.0","id":2,"result":{"tools":[]}}\n\n'
        import time
        self.assertEqual(read_reply(Response(raw, headers={"Content-Type":"text/event-stream"}), 2, time.monotonic()+1), {"tools":[]})

    def test_download_method_cannot_be_sent(self):
        opener = FakeOpener([])
        with self.assertRaisesRegex(ProbeError,"METHOD_NOT_ALLOWED"):
            Client("fake-key",opener).send("tools/call", {"name":"download"})
        self.assertEqual(opener.requests, [])

    def test_redirect_is_refused_without_forwarding_key(self):
        with self.assertRaisesRegex(ProbeError,"REDIRECT_REFUSED"):
            NoRedirect().redirect_request(None,None,307,"",{},"https://other.example/mcp")

    def test_rpc_error_body_cannot_become_receipt_or_exception_text(self):
        import time
        response = Response(b'{"jsonrpc":"2.0","id":1,"error":{"message":"sensitive-value"}}')
        with self.assertRaisesRegex(ProbeError,"^RPC_ERROR$"):
            read_reply(response, 1, time.monotonic()+1)

    def test_missing_secret_has_no_network_effect(self):
        opener = FakeOpener([])
        with self.assertRaisesRegex(ProbeError,"MISSING_OR_INVALID"):
            probe("",opener)
        self.assertEqual(opener.requests, [])


if __name__ == "__main__":
    unittest.main()
