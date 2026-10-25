"""Offline regression tests for credential boundaries and zero-side-effect behavior."""
import io
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import MAX_BYTES, ORIGIN, NoRedirect, PavoClient, PavoError


class Reply(io.BytesIO):
    status = 200


class FakeOpener:
    def __init__(self, data=None, error=None, raw=None):
        self.raw = raw if raw is not None else json.dumps({"code": "000000", "data": data}).encode()
        self.error = error
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return Reply(self.raw)


class Boundaries(unittest.TestCase):
    def test_account_returns_only_selected_fields_and_token_stays_in_header(self):
        token = "synthetic-credential-for-offline-tests"
        fake = FakeOpener({"level_name": "PRO", "total_balance": 1700,
                           "subscription_credits": 1000, "email": "private@example.invalid",
                           "token": token, "daily_free_credits": 200})
        result = PavoClient(token, fake).account()
        request, timeout = fake.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, ORIGIN + "/v3/subscription/credits-balance")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + token)
        self.assertIsNone(request.data)
        self.assertEqual(timeout, 12)
        self.assertEqual(result["plan"], "PRO")
        self.assertEqual(result["credits"]["total_balance"], 1700)
        self.assertNotIn(token, json.dumps(result))
        self.assertNotIn("private@example.invalid", json.dumps(result))

    def test_remote_secret_echo_is_not_returned_even_in_allowed_display_field(self):
        token = "synthetic-credential-for-offline-tests"
        fake = FakeOpener({"level_name": token, "total_balance": float("nan")})
        result = PavoClient(token, fake).account()
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["credits"]["total_balance"])
        self.assertNotIn(token, json.dumps(result))

    def test_public_catalog_never_receives_token_or_claims_verified_free_price(self):
        fake = FakeOpener([{"model_code": "agnes-video-new-flash", "model_alias": "Agnes Video 2.5 Flash",
                            "tags": ["free"], "secret": "discard-me"}])
        result = PavoClient("synthetic-credential", fake).models()
        self.assertIsNone(fake.calls[0][0].get_header("Authorization"))
        self.assertTrue(result["models"][0]["free_label"])
        self.assertIsNone(result["models"][0]["verified_price_credits"])
        self.assertFalse(result["price_verified"])
        self.assertNotIn("discard-me", json.dumps(result))

    def test_missing_or_header_injection_credential_does_not_touch_network(self):
        for token in ("", "bad\r\nInjected: header", "x" * 8193):
            fake = FakeOpener()
            with self.assertRaisesRegex(PavoError, "PAVO_CREDENTIAL_REQUIRED"):
                PavoClient(token, fake).account()
            self.assertEqual(fake.calls, [])

    def test_mode_catalog_uses_code_and_tag_objects(self):
        fake = FakeOpener({"models": [{"code": "agnes-video-new-flash", "alias": "Agnes Video 2.5 Flash",
                                       "tags": [{"code": "free"}]}]})
        result = PavoClient("", fake).models()
        self.assertEqual(result["models"][0]["code"], "agnes-video-new-flash")
        self.assertTrue(result["models"][0]["free_label"])

    def test_no_arbitrary_url_purchase_or_generation_route(self):
        fake = FakeOpener()
        client = PavoClient("synthetic-credential", fake)
        for route in ("https://example.invalid", "../credits", "/v1/subscription/subscribe", "generate"):
            with self.assertRaisesRegex(PavoError, "ROUTE_NOT_ALLOWED"):
                client._get(route)
        self.assertEqual(fake.calls, [])

    def test_paid_subscription_does_not_enable_submission_or_spending(self):
        fake = FakeOpener(error=AssertionError("No network expected"))
        client = PavoClient("synthetic-credential", fake)
        result = client.prepare_video("Soft sunlight crosses a river.", 5, "9:16")
        self.assertTrue(result["prepared"])
        self.assertFalse(result["submitted"])
        self.assertFalse(result["additional_spend_allowed"])
        self.assertIsNone(result["estimated_credits"])
        self.assertEqual(fake.calls, [])
        self.assertFalse(client.status()["account_verified"])

    def test_bad_brief_and_credential_in_prompt_are_refused_without_echo(self):
        client = PavoClient("synthetic-credential", FakeOpener())
        for prompt, seconds, ratio in (("", 5, "9:16"), ("test", 13, "9:16"),
                                       ("test", True, "9:16"), ("test", 5, "bad"),
                                       ("synthetic-credential", 5, "9:16")):
            with self.assertRaises(PavoError) as ctx:
                client.prepare_video(prompt, seconds, ratio)
            self.assertNotIn("synthetic-credential", str(ctx.exception))

    def test_redirects_cannot_forward_authorization(self):
        with self.assertRaisesRegex(PavoError, "REDIRECT_REFUSED"):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")

    def test_network_and_http_errors_are_sanitized_and_never_retried(self):
        for error, expected in ((URLError("synthetic-credential"), "PAVO_UNREACHABLE"),
                                (TimeoutError("synthetic-credential"), "PAVO_UNREACHABLE"),
                                (HTTPError(ORIGIN, 403, "synthetic-credential", {}, io.BytesIO()),
                                 "PAVO_ACCESS_REFUSED"),
                                (HTTPError(ORIGIN, 429, "synthetic-credential", {}, io.BytesIO()),
                                 "PAVO_RATE_LIMITED")):
            fake = FakeOpener(error=error)
            with self.assertRaisesRegex(PavoError, expected):
                PavoClient("synthetic-credential", fake).account()
            self.assertEqual(len(fake.calls), 1)

    def test_malformed_oversized_and_expired_responses_fail_closed(self):
        for raw, expected in ((b"<html>private response</html>", "INVALID_PAVO_RESPONSE"),
                              (b"x" * (MAX_BYTES + 1), "RESPONSE_TOO_LARGE"),
                              (b'{"code":"000501","message":"private response"}', "PAVO_SESSION_EXPIRED"),
                              (b'{"code":"000000","data":{}}', "PAVO_BALANCE_SCHEMA_CHANGED")):
            with self.assertRaisesRegex(PavoError, expected):
                PavoClient("synthetic-credential", FakeOpener(raw=raw)).account()


if __name__ == "__main__":
    unittest.main()
