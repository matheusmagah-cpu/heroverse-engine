"""Price, submission recovery and credential regressions; no network or real secrets."""
import io
import json
from http.client import HTTPResponse
from pathlib import Path
import socket
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import MAX_BYTES, ORIGIN, PavoError
from video import MODEL, PavoVideoClient


class Reply(io.BytesIO):
    status = 200

    def __init__(self, value):
        super().__init__(value)
        self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=SimpleNamespace(shutdown=lambda how: None)))


def envelope(data):
    return json.dumps({"code": "000000", "data": data}).encode()


def quote(credits=0, estimate=False, final=0):
    return envelope({"required_credits": credits, "final_points": final, "is_estimate": estimate})


def started(model=MODEL):
    return b"event: GenerationStart\ndata: " + json.dumps({"model_code": model}).encode() + b"\n\n"


class Responses:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if not self.responses:
            raise AssertionError("Unexpected request or retry")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, HTTPResponse):
            return response
        return Reply(response)


class Video(unittest.TestCase):
    token = "synthetic-offline-pavo-credential"

    def test_exact_free_quote_and_submission_bind_the_same_model_and_output(self):
        fake = Responses(quote(), envelope({"conversation_id": "12345"}), started())
        result = PavoVideoClient(self.token, fake).generate_video("Sunlight over an olive grove.", 5, "9:16")
        self.assertEqual(result["status"], "submitted")
        self.assertFalse(result["retry_submission"])
        self.assertFalse(result["published"])
        self.assertEqual(len(fake.calls), 3)
        requests = [r for r, _ in fake.calls]
        pricing = json.loads(requests[0].data)
        generation = json.loads(requests[2].data)
        self.assertEqual(pricing["model_code"], generation["model"])
        output = pricing["outputs"][0]
        self.assertEqual((output["duration_seconds"], output["resolution"], output["count"], output["gen_audio"]),
                         (generation["duration"], generation["resolution"], generation["count"], generation["sound"]))
        self.assertEqual(generation["mode"], "frames_to_video")
        self.assertEqual(generation["ratio"], "9:16")
        for request in requests:
            self.assertTrue(request.full_url.startswith(ORIGIN + "/"))
            self.assertEqual(request.get_header("Authorization"), "Bearer " + self.token)
            self.assertNotIn(self.token, request.full_url)
            self.assertNotIn(self.token.encode(), request.data)
        # Live regression: missing platform/time metadata returned error 009999.
        self.assertEqual(requests[2].get_header("X-platform"), "1")
        self.assertEqual(requests[2].get_header("X-app-timezone"), "America/Sao_Paulo")
        self.assertRegex(requests[2].get_header("X-client-time-ms"), r"^[0-9]{13}$")
        self.assertEqual(requests[2].get_header("X-user-language"), "en")
        self.assertNotIn(self.token, json.dumps(result))

    def test_nonzero_estimated_and_malformed_quotes_cannot_create_or_submit(self):
        for raw in (quote(1), quote(0, True), quote(0, False, 1), quote(None), quote(True),
                    quote(float("nan")), envelope({}), quote(0, None), quote(0, False, -1)):
            with self.subTest(raw=raw):
                fake = Responses(raw)
                with self.assertRaises(PavoError):
                    PavoVideoClient(self.token, fake).generate_video("An olive grove.")
                self.assertEqual(len(fake.calls), 1)

    def test_quote_is_fresh_for_every_submission_and_cannot_be_passed_back(self):
        fake = Responses(quote(), quote(2))
        client = PavoVideoClient(self.token, fake)
        self.assertTrue(client.quote_video()["zero_cost_confirmed"])
        with self.assertRaisesRegex(PavoError, "PAVO_ZERO_CREDIT_QUOTE_REQUIRED"):
            client.generate_video("An olive grove.")
        self.assertEqual(len(fake.calls), 2)

    def test_positive_prices_cannot_round_or_underflow_to_free(self):
        for raw in (quote("1e-10000", False, "1e-10000"), quote(0, False, "1e-10000"),
                    b'{"code":"000000","data":{"required_credits":1e-10000,"final_points":1e-10000,"is_estimate":false}}'):
            fake = Responses(raw, envelope({"conversation_id": "12345"}), started())
            with self.assertRaises(PavoError):
                PavoVideoClient(self.token, fake).generate_video("An olive grove.")
            self.assertEqual(len(fake.calls), 1)

    def test_acknowledgement_after_stream_deadline_is_not_accepted(self):
        clock = [0.0]
        class SlowReply(Reply):
            def readline(self, n=-1):
                line = super().readline(n)
                if line == b'\n':
                    clock[0] += 31
                return line
            def read1(self, n=-1):
                clock[0] += 31
                return super().read1(n)
        fake = Responses(quote(), envelope({"conversation_id": "12345"}), started())
        original = fake.open
        def open_response(request, timeout):
            response = original(request, timeout)
            return SlowReply(response.getvalue()) if request.full_url.endswith('/stream') else response
        fake.open = open_response
        with patch('video.time.monotonic', side_effect=lambda: clock[0]):
            result = PavoVideoClient(self.token, fake).generate_video("An olive grove.")
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["conversation_id"], "12345")
        self.assertEqual(len(fake.calls), 3)

    def test_lost_acknowledgement_preserves_job_id_and_never_retries_or_echoes_error(self):
        for failure in (URLError(self.token), b"", started("other-model"), b"x" * 16385):
            fake = Responses(quote(), envelope({"conversation_id": "12345"}), failure)
            result = PavoVideoClient(self.token, fake).generate_video("An olive grove.")
            self.assertEqual(result["status"], "unknown")
            self.assertIsNone(result["submitted"])
            self.assertEqual(result["conversation_id"], "12345")
            self.assertFalse(result["retry_submission"])
            self.assertEqual(len(fake.calls), 3)
            self.assertNotIn(self.token, json.dumps(result))

    def test_stream_deadline_interrupts_chunk_metadata_and_preserves_job(self):
        # A local socket pair exercises HTTPResponse's internal chunk readline;
        # no DNS, external network, credentials or generation are involved.
        reader, writer = socket.socketpair()
        reader.settimeout(3)
        done = threading.Event()
        def fallback_close():
            if not done.wait(2):
                writer.shutdown(socket.SHUT_RDWR)
        fallback = threading.Thread(target=fallback_close, daemon=True)
        try:
            writer.sendall(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1;unfinished-extension')
            response = HTTPResponse(reader)
            response.begin()
            fake = Responses(quote(), envelope({"conversation_id": "12345"}), response)
            fallback.start()
            before = time.monotonic()
            with patch('video.STREAM_SECONDS', 0.1, create=True):
                result = PavoVideoClient(self.token, fake).generate_video("An olive grove.")
            elapsed = time.monotonic() - before
            self.assertLess(elapsed, 1.0, "chunk metadata outlived the stream body deadline")
            self.assertEqual(result["status"], "unknown")
            self.assertEqual(result["conversation_id"], "12345")
            self.assertIsNone(result["submitted"])
            self.assertFalse(result["retry_submission"])
            self.assertEqual(len(fake.calls), 3)
        finally:
            done.set()
            fallback.join(timeout=3)
            reader.close()
            writer.close()

    def test_explicit_rejection_is_not_success_and_does_not_echo_remote_message(self):
        event = b'event: error\ndata: ' + json.dumps({"message": self.token}).encode() + b'\n\n'
        fake = Responses(quote(), envelope({"conversation_id": 12345}), event)
        result = PavoVideoClient(self.token, fake).generate_video("An olive grove.")
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(result["submitted"])
        self.assertNotIn(self.token, json.dumps(result))

    def test_invalid_or_missing_inputs_do_not_touch_network(self):
        for token, prompt, seconds, ratio in (("", "test", 5, "9:16"), (self.token, self.token, 5, "9:16"),
                                             (self.token, "test", True, "9:16"), (self.token, "test", 13, "9:16"),
                                             (self.token, "test", 5, "bad")):
            fake = Responses()
            with self.assertRaises(PavoError):
                PavoVideoClient(token, fake).generate_video(prompt, seconds, ratio)
            self.assertEqual(fake.calls, [])

    def test_job_is_read_only_and_rejects_url_or_query_injection(self):
        fake = Responses(envelope({"is_running": True, "turns": [], "private": self.token}))
        client = PavoVideoClient(self.token, fake)
        result = client.job("12345")
        request = fake.calls[0][0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertTrue(result["running"])
        self.assertNotIn(self.token, json.dumps(result))
        for value in ("../123", "123&token=x", "https://example.invalid", True):
            with self.assertRaises(PavoError):
                client.job(value)
        self.assertEqual(len(fake.calls), 1)

    def test_oversized_or_malformed_history_is_not_success(self):
        for raw in (b"x" * (MAX_BYTES + 1), envelope({"is_running": "false", "turns": []}),
                    envelope({"is_running": False, "turns": None})):
            with self.assertRaises(PavoError):
                PavoVideoClient(self.token, Responses(raw)).job("12345")

    def test_completed_job_exposes_only_verified_media_fields_on_the_fixed_cdn(self):
        url = "https://cos-aigc-default.agnes-ai.space/pixa/video/test.mp4"
        payload = {"is_running": False, "turns": [{"assistant": [{"type": "GenerationSuccess", "data": {
            "data": {"model_code": MODEL, "results": [{"url": url, "duration": 5, "width": 720,
                      "height": 1280, "private": self.token}]}, "private": self.token}}]}]}
        result = PavoVideoClient(self.token, Responses(envelope(payload))).job("12345")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["videos"], [{"url": url, "seconds": 5, "width": 720, "height": 1280}])
        self.assertNotIn(self.token, json.dumps(result))
        for bad in ("https://example.invalid/test.mp4", url + "?token=x", url.replace("https:", "http:"),
                    "https://user@cos-aigc-default.agnes-ai.space/test.mp4", url.replace("test.mp4", self.token + ".mp4")):
            payload["turns"][0]["assistant"][0]["data"]["data"]["results"][0]["url"] = bad
            with self.assertRaisesRegex(PavoError, "PAVO_MEDIA_URL_REFUSED"):
                PavoVideoClient(self.token, Responses(envelope(payload))).job("12345")

    def test_finished_without_media_is_not_reported_as_success(self):
        payload = {"is_running": False, "turns": [{"assistant": []}]}
        self.assertEqual(PavoVideoClient(self.token, Responses(envelope(payload))).job("12345")["status"], "incomplete")


def png(width=720, height=1280):
    import struct, zlib
    head = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", 13) + b"IHDR" + head + struct.pack(">I", zlib.crc32(b"IHDR" + head))
    return b"\x89PNG\r\n\x1a\n" + chunk


def presigned(n=1):
    return envelope({"public_url": f"https://files.example.test/u/{n}.png", "upload_url": f"https://store.example.test/put/{n}?sig=x",
                     "required_headers": {"Content-Type": "image/png"}, "meta_data": {"w": 720}})


class Inputs(unittest.TestCase):
    """First/last frame and reference images (capability spec 2026-10-25); no network or real secrets."""
    token = "synthetic-offline-pavo-credential"

    def setUp(self):
        import tempfile
        self.repo = Path(tempfile.mkdtemp())
        (self.repo / "img").mkdir()
        for name in ("a.png", "b.png", "c.png"):
            (self.repo / "img" / name).write_bytes(png())
        (self.repo / "img" / "tiny.png").write_bytes(png(100, 100))
        (self.repo / "img" / "wide.png").write_bytes(png(3000, 600))
        (self.repo / "img" / "x.gif").write_bytes(b"GIF89a")
        self.patch = patch("images.REPO", self.repo)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_first_and_last_frame_are_priced_uploaded_without_the_credential_then_sent_in_order(self):
        fake = Responses(quote(), presigned(1), b"", envelope({}), presigned(2), b"", envelope({}),
                         envelope({"conversation_id": "777"}), started())
        result = PavoVideoClient(self.token, fake).generate_video("The path rises into light.", 6, "9:16",
                                                                  "img/a.png", "img/b.png")
        self.assertEqual((result["status"], result["mode"], result["input_images"]), ("submitted", "frames_to_video", 2))
        requests = [r for r, _ in fake.calls]
        self.assertEqual(json.loads(requests[0].data)["inputs"], [{"count": 1, "media_type": "image"}] * 2)
        for put in (requests[2], requests[5]):
            self.assertEqual(put.get_method(), "PUT")
            self.assertTrue(put.full_url.startswith("https://store.example.test/put/"))
            self.assertIsNone(put.get_header("Authorization"))
            self.assertEqual(put.data, png())
        body = json.loads(requests[8].data)
        self.assertEqual(body["mode"], "frames_to_video")
        self.assertEqual([i["url"] for i in body["images"]], ["https://files.example.test/u/1.png",
                                                              "https://files.example.test/u/2.png"])
        self.assertNotIn("creative_prompt_json", body)

    def test_references_use_omni_mode_with_indexed_prompt_blocks(self):
        fake = Responses(quote(), presigned(1), b"", envelope({}), presigned(2), b"", envelope({}),
                         envelope({"conversation_id": "778"}), started())
        result = PavoVideoClient(self.token, fake).generate_video("Eve walks in the garden.", 5, "9:16",
                                                                  references=["img/a.png", "img/c.png"])
        self.assertEqual(result["mode"], "omni_to_video")
        body = json.loads(fake.calls[-1][0].data)
        self.assertEqual(body["mode"], "omni_to_video")
        self.assertEqual(len(body["images"]), 2)
        blocks = json.loads(body["creative_prompt_json"])
        self.assertEqual(blocks[0], {"type": "text", "content": "Eve walks in the garden."})
        self.assertEqual([b["source_index"] for b in blocks[1:]], [1, 2])

    def test_nonzero_quote_with_images_uploads_nothing(self):
        fake = Responses(quote(credits=5))
        with self.assertRaises(PavoError):
            PavoVideoClient(self.token, fake).generate_video("x", 5, "9:16", "img/a.png")
        self.assertEqual(len(fake.calls), 1)

    def test_failed_upload_creates_no_conversation(self):
        fake = Responses(quote(), presigned(1), URLError("down"))
        with self.assertRaises(PavoError):
            PavoVideoClient(self.token, fake).generate_video("x", 5, "9:16", "img/a.png")
        self.assertEqual(len(fake.calls), 3)     # quote, presign, PUT: no create, no stream

    def test_bad_inputs_never_touch_network(self):
        cases = [dict(first_frame="../../etc/passwd"), dict(first_frame="/etc/hosts"), dict(first_frame="img/x.gif"),
                 dict(first_frame="img/tiny.png"), dict(first_frame="img/wide.png"), dict(last_frame="img/a.png"),
                 dict(first_frame="img/a.png", references=["img/b.png"]), dict(references=["img/a.png"] * 6),
                 dict(references="img/a.png"), dict(first_frame="img/missing.png")]
        for kwargs in cases:
            fake = Responses()
            with self.assertRaises(PavoError, msg=kwargs):
                PavoVideoClient(self.token, fake).generate_video("x", 5, "9:16", **kwargs)
            with self.assertRaises(PavoError, msg=kwargs):
                PavoVideoClient(self.token, fake).quote_video(5, "9:16", **kwargs)
            self.assertEqual(fake.calls, [], kwargs)

    def test_upload_reply_cannot_redirect_the_credential_or_inject_headers(self):
        for data in ({"public_url": "http://files.example.test/a.png", "upload_url": "https://s/p"},
                     {"public_url": "https://f/a.png", "upload_url": "https://s/p", "required_headers": {"Authorization": "x"}},
                     {"public_url": "https://f/a.png?t=1", "upload_url": "https://s/p"},
                     {"public_url": "https://f/a.png", "upload_url": "https://s/p", "required_headers": {"X\nY": "1"}}):
            fake = Responses(quote(), envelope(data))
            with self.assertRaises(PavoError):
                PavoVideoClient(self.token, fake).generate_video("x", 5, "9:16", "img/a.png")
            self.assertEqual(len(fake.calls), 2)

    def test_quote_counts_inputs_and_every_spec_ratio_is_accepted(self):
        for ratio in ("9:16", "3:4", "1:1", "4:3", "16:9", "21:9"):
            fake = Responses(quote())
            q = PavoVideoClient(self.token, fake).quote_video(12, ratio, references=["img/a.png", "img/b.png", "img/c.png"])
            self.assertEqual((q["mode"], q["input_images"], q["zero_cost_confirmed"]), ("omni_to_video", 3, True))
            self.assertEqual(len(json.loads(fake.calls[0][0].data)["inputs"]), 3)


if __name__ == "__main__":
    unittest.main()
