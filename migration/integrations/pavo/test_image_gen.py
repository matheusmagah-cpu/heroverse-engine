"""Agnes Image 2.5 Flash stills: price, submission recovery and credential regressions; no network or real secrets."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import ORIGIN, PavoError
from image_gen import IMAGE_MODEL, IMAGE_RATIOS, PavoImageClient
import images
from test_video import Responses, envelope, quote, started

CDN = "https://cos-aigc-default.agnes-ai.space/pixa/ugc_image/x/still.png"


def png(width, height):
    head = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + head + struct.pack(">I", zlib.crc32(b"IHDR" + head))


def presigned(name):
    return envelope({"public_url": "https://files.example/" + name, "upload_url": "https://store.example/" + name,
                     "required_headers": {"Content-Type": "image/png"}})


def history(results, model=IMAGE_MODEL, running=False):
    return envelope({"is_running": running, "turns": [{"assistant": [
        {"type": "GenerationSuccess", "data": {"data": {"model_code": model, "results": results}}}]}]})


class Image(unittest.TestCase):
    token = "synthetic-offline-pavo-credential"

    def test_exact_free_quote_and_submission_bind_the_free_model_ratio_and_resolution(self):
        fake = Responses(quote(), envelope({"conversation_id": "777"}), started(IMAGE_MODEL))
        result = PavoImageClient(self.token, fake).generate_image("A dry plain at dusk.", "9:16", "hd")
        self.assertEqual(result["status"], "submitted")
        self.assertEqual((result["quoted_credits"], result["retry_submission"], result["published"]), (0, False, False))
        requests = [r for r, _ in fake.calls]
        self.assertEqual([r.full_url[len(ORIGIN):] for r in requests],
                         ["/v1/aigc/credits/calculate", "/v1/chat/conversation", "/v1/chat/stream"])
        pricing, body = json.loads(requests[0].data), json.loads(requests[2].data)
        self.assertEqual(pricing, {"model_code": "agnes-image",
                                   "outputs": [{"count": 1, "media_type": "image", "resolution": "hd"}]})
        self.assertEqual((body["mode"], body["model"], body["ratio"], body["resolution"], body["count"]),
                         ("generate_image", "agnes-image", "9:16", "hd", 1))
        self.assertEqual(json.loads(body["creative_prompt_json"]), [{"type": "text", "content": "A dry plain at dusk."}])
        self.assertNotIn("images", body)
        self.assertNotIn("duration", body)
        self.assertNotIn("sound", body)
        for request in requests:
            self.assertEqual(request.get_header("Authorization"), "Bearer " + self.token)
            self.assertNotIn(self.token.encode(), request.data)
        self.assertEqual(requests[2].get_header("X-platform"), "1")
        self.assertNotIn(self.token, json.dumps(result))

    def test_nonzero_estimated_and_malformed_quotes_create_nothing_and_report_the_price(self):
        for raw in (quote(4), quote(0, True), quote(0, False, 1), quote(None), quote(True), envelope({})):
            with self.subTest(raw=raw):
                fake = Responses(raw)
                with self.assertRaises(PavoError):
                    PavoImageClient(self.token, fake).generate_image("A plain.")
                self.assertEqual(len(fake.calls), 1)
        with self.assertRaisesRegex(PavoError, "required_credits=4 final_points=4 is_estimate=false"):
            PavoImageClient(self.token, Responses(quote(4, False, 4))).generate_image("A plain.")

    def test_only_the_free_model_is_ever_sent(self):
        fake = Responses(quote(), quote(), envelope({"conversation_id": "9"}), started(IMAGE_MODEL))
        client = PavoImageClient(self.token, fake)
        client.quote_image("16:9", "uhd")
        client.generate_image("A plain.")
        for request, _ in fake.calls:
            body = json.loads(request.data)
            self.assertEqual(body.get("model_code", body.get("model", IMAGE_MODEL)), "agnes-image")

    def test_quote_is_fresh_for_every_submission(self):
        fake = Responses(quote(), quote(2))
        client = PavoImageClient(self.token, fake)
        self.assertTrue(client.quote_image()["zero_cost_confirmed"])
        with self.assertRaisesRegex(PavoError, "PAVO_ZERO_CREDIT_QUOTE_REQUIRED"):
            client.generate_image("A plain.")
        self.assertEqual(len(fake.calls), 2)

    def test_every_spec_ratio_and_resolution_is_quoted_and_bad_inputs_touch_no_network(self):
        for ratio in IMAGE_RATIOS:
            self.assertEqual(PavoImageClient(self.token, Responses(quote())).quote_image(ratio)["aspect_ratio"], ratio)
        for res in ("sd", "hd", "uhd"):
            self.assertEqual(PavoImageClient(self.token, Responses(quote())).quote_image("9:16", res)["resolution"], res)
        for args, code in ((("", "9:16"), "INVALID_PROMPT"), (("x" * 10001, "9:16"), "INVALID_PROMPT"),
                           (("A plain.", "5:4"), "INVALID_ASPECT_RATIO"),
                           (("A plain.", "9:16", "8k"), "INVALID_IMAGE_RESOLUTION"),
                           (("A plain " + self.token, "9:16"), "CREDENTIAL_IN_PROMPT_REFUSED"),
                           (("A plain.", "9:16", "sd", "a.png"), "INPUT_REFERENCES_REFUSED"),
                           (("A plain.", "9:16", "sd", ["x"] * 7), "INPUT_REFERENCES_REFUSED"),
                           (("A plain.", "9:16", "sd", ["../../etc/passwd.png"]), "INPUT_IMAGE_PATH_REFUSED")):
            with self.subTest(code=code):
                fake = Responses()
                with self.assertRaisesRegex(PavoError, code):
                    PavoImageClient(self.token, fake).generate_image(*args)
                self.assertEqual(fake.calls, [])
        with self.assertRaisesRegex(PavoError, "PAVO_CREDENTIAL_REQUIRED"):
            PavoImageClient("", Responses()).quote_image()

    def test_references_are_priced_uploaded_without_the_credential_and_indexed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a.png", "b.png"):
                Path(tmp, name).write_bytes(png(720, 1280))
            original = images.REPO
            images.REPO = Path(tmp)
            try:
                fake = Responses(quote(), presigned("a.png"), b"", envelope({}), presigned("b.png"), b"",
                                 envelope({}), envelope({"conversation_id": "55"}), started(IMAGE_MODEL))
                result = PavoImageClient(self.token, fake).generate_image("Noah.", references=["a.png", "b.png"])
            finally:
                images.REPO = original
        self.assertEqual((result["status"], result["input_images"]), ("submitted", 2))
        requests = [r for r, _ in fake.calls]
        self.assertEqual(json.loads(requests[0].data)["inputs"], [{"count": 1, "media_type": "image"}] * 2)
        for put in (requests[2], requests[5]):
            self.assertEqual(put.get_method(), "PUT")
            self.assertIsNone(put.get_header("Authorization"))
        body = json.loads(requests[-1].data)
        self.assertEqual(body["images"], [{"url": "https://files.example/a.png"}, {"url": "https://files.example/b.png"}])
        self.assertEqual(json.loads(body["creative_prompt_json"])[1:],
                         [{"type": "image", "url": "https://files.example/a.png", "source_index": 1},
                          {"type": "image", "url": "https://files.example/b.png", "source_index": 2}])

    def test_lost_acknowledgement_keeps_the_job_and_never_retries(self):
        for failure in (URLError(self.token), b"", started("agnes-video-new-flash"), started("gpt-image-2")):
            with self.subTest(failure=failure):
                fake = Responses(quote(), envelope({"conversation_id": "12345"}), failure)
                result = PavoImageClient(self.token, fake).generate_image("A plain.")
                self.assertEqual((result["status"], result["conversation_id"]), ("unknown", "12345"))
                self.assertFalse(result["retry_submission"])
                self.assertEqual(len(fake.calls), 3)
                self.assertNotIn(self.token, json.dumps(result))

    def test_explicit_rejection_is_not_success(self):
        fake = Responses(quote(), envelope({"conversation_id": "12"}), b"event: error\ndata: {}\n\n")
        self.assertEqual(PavoImageClient(self.token, fake).generate_image("A plain.")["status"], "rejected")

    def test_job_returns_only_images_of_the_free_model_on_the_fixed_cdn(self):
        result = PavoImageClient(self.token, Responses(history([{"url": CDN, "width": 768, "height": 1344}]))).image_job("12")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["images"], [{"url": CDN, "width": 768.0, "height": 1344.0}])
        alt = PavoImageClient(self.token, Responses(history([{"image_url": CDN}]))).image_job("12")
        self.assertEqual(alt["images"][0]["url"], CDN)
        for bad in ([{"url": CDN.replace("cos-aigc-default.agnes-ai.space", "evil.example")}],
                    [{"url": CDN + "?token=1"}], [{"url": CDN.replace(".png", ".mp4")}], [{"url": None}]):
            with self.subTest(bad=bad), self.assertRaises(PavoError):
                PavoImageClient(self.token, Responses(history(bad))).image_job("12")
        with self.assertRaisesRegex(PavoError, "PAVO_RESULT_SCHEMA_CHANGED"):
            PavoImageClient(self.token, Responses(history([{"url": CDN}], "gpt-image-2"))).image_job("12")
        with self.assertRaisesRegex(PavoError, "INVALID_CONVERSATION_ID"):
            PavoImageClient(self.token, Responses()).image_job("12&x=1")
        running = PavoImageClient(self.token, Responses(history([], running=True))).image_job("12")
        self.assertEqual(running["status"], "running")


if __name__ == "__main__":
    unittest.main()
