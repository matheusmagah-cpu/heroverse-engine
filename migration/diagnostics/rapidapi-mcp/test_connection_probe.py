import io
import json
import unittest
from connection_probe import Client, NoRedirect, ProbeError, ProtocolNegotiationError, PROTOCOLS, probe, read_reply


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
    def test_only_uncorrelated_method_not_found_can_continue_to_catalogue(self):
        first = Response(b'{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}}}}')
        notification = Response(b'{"jsonrpc":"2.0","id":null,"error":{"code":-32601,"message":"private-value"}}')
        listing = Response(b'{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"download"}]}}')
        result = probe("fake-key", FakeOpener([first, notification, listing]))
        self.assertEqual(result["status"], "MCP_TRANSPORT_AND_TOOL_LIST_VERIFIED")
        self.assertEqual(result["notification_rpc_error_code"], -32601)
        self.assertEqual(result["notification_acknowledgement"], "HTTP_200_METHOD_NOT_FOUND_COMPATIBILITY")
        self.assertFalse(result["standard_notification_acknowledgement"])
        self.assertNotIn("private-value", json.dumps(result))
        self.assertFalse(result["owner_entitlement_verified_by_this_probe"])

    def test_other_notification_errors_remain_fatal(self):
        for code, response_id in [(-32600, None), (-32001, None), (-32601, 1)]:
            with self.subTest(code=code, response_id=response_id):
                notification = Response(json.dumps({"jsonrpc":"2.0","id":response_id,"error":{"code":code,"message":"private-value"}}).encode())
                client = Client("fake-key", FakeOpener([notification]))
                client._protocol = "2024-11-05"
                with self.assertRaisesRegex(ProbeError, "NOTIFICATION_RPC_ERROR"):
                    client.send("notifications/initialized")
                self.assertIsNone(client.notification_acknowledgement)
                self.assertNotIn("private-value", json.dumps(client.public_trace()))

    def test_empty_success_notification_compatibility_is_explicit(self):
        for status in (200, 204):
            with self.subTest(status=status):
                client = Client("fake-key", FakeOpener([Response(b"", status=status)]))
                client._protocol = "2024-11-05"
                client.send("notifications/initialized")
                self.assertEqual(client.notification_acknowledgement, "HTTP_" + str(status) + "_EMPTY_COMPATIBILITY")

    def test_null_result_notification_compatibility_is_explicit(self):
        client = Client("fake-key", FakeOpener([Response(b'{"jsonrpc":"2.0","id":null,"result":null}')]))
        client._protocol = "2024-11-05"
        client.send("notifications/initialized")
        self.assertEqual(client.notification_acknowledgement, "HTTP_200_NULL_RESULT_COMPATIBILITY")

    def test_notification_failure_is_not_accepted_or_disclosed(self):
        for response in [Response(b'{"jsonrpc":"2.0","error":{"message":"private-value"}}'), Response(b'{"message":"private-value"}'), Response(b"", status=201)]:
            client = Client("fake-key", FakeOpener([response]))
            client._protocol = "2024-11-05"
            with self.assertRaises(ProbeError) as raised:
                client.send("notifications/initialized")
            self.assertNotIn("private-value", str(raised.exception))
            self.assertIsNone(client.notification_acknowledgement)

    def test_failure_retains_only_safe_protocol_and_http_trace(self):
        first = Response(b'{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}}}}')
        opener = FakeOpener([first, Response(b'{"error":{"message":"private-value"}}')])
        evidence = {}
        with self.assertRaisesRegex(ProbeError, "NOTIFICATION_RPC_ERROR"):
            probe("fake-local-test-key", opener, evidence)
        self.assertEqual(evidence["protocol_version"], "2024-11-05")
        self.assertEqual(evidence["http_responses"], [{"method":"initialize","status":200},{"method":"notifications/initialized","status":200}])
        self.assertNotIn("private-value", json.dumps(evidence))
        self.assertNotIn("fake-local-test-key", json.dumps(evidence))
        self.assertEqual(len(opener.requests), 2)

    def test_each_supported_handshake_revision_reaches_the_catalogue(self):
        for protocol in PROTOCOLS:
            with self.subTest(protocol=protocol):
                first = Response(json.dumps({"jsonrpc":"2.0","id":1,"result":{"protocolVersion":protocol,"capabilities":{"tools":{}}}}).encode())
                listing = Response(b'{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"download"}]}}')
                opener = FakeOpener([first, Response(b"", status=202), listing])
                result = probe("fake-local-test-key", opener)
                self.assertEqual(result["protocol_version"], protocol)
                self.assertEqual(json.loads(opener.requests[0].data)["params"]["protocolVersion"], "2025-11-25")
                self.assertEqual(opener.requests[2].get_header("Mcp-protocol-version"), protocol)
                self.assertEqual(len(opener.requests), 3)

    def test_unknown_protocol_stops_before_notification_and_redacts_peer_text(self):
        for protocol, expected in [("2026-07-28", "2026-07-28"), ("private-secret-value", "UNRECOGNIZED_OR_MISSING"), (None, "UNRECOGNIZED_OR_MISSING")]:
            with self.subTest(protocol=protocol):
                first = Response(json.dumps({"jsonrpc":"2.0","id":1,"result":{"protocolVersion":protocol,"capabilities":{"tools":{}}}}).encode())
                opener = FakeOpener([first])
                with self.assertRaises(ProtocolNegotiationError) as raised:
                    probe("fake-local-test-key", opener)
                self.assertEqual(str(raised.exception), "UNSUPPORTED_NEGOTIATED_PROTOCOL")
                self.assertEqual(raised.exception.server_protocol_version, expected)
                self.assertEqual(len(opener.requests), 1)

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
