#!/usr/bin/env python3
"""Offline tests of the Gemini image route (fake API; no network, no key)."""
import base64
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import urllib.error

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import image  # noqa: E402

KEY = "AIza" + "x" * 35
REQUEST = HERE / "requests/arc-01-long-s-c3-eve-near.json"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1344, 768) + b"\x08\x02\x00\x00\x00" + b"\x00" * 20


class Resp:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_for(answer=None, status=None, error=None, seen=None):
    def opener(req, timeout=None):
        if seen is not None:
            seen.append(req)
        if status:
            raise urllib.error.HTTPError(req.full_url, status, "x", {}, io.BytesIO(json.dumps(error).encode()))
        return Resp(answer)
    return opener


def answer_with(data):
    return {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png",
                                                                  "data": base64.b64encode(data).decode()}}]},
                            "finishReason": "STOP"}], "modelVersion": "gemini-2.5-flash-image", "responseId": "r1"}


class Request(unittest.TestCase):
    def test_the_eve_request_sends_three_approved_stills_at_full_resolution(self):
        req, still, refs, problems = image.load_request(REQUEST)
        self.assertEqual(problems, [])
        self.assertEqual([r["id"] for r, _ in refs], ["arc-01-long-s-c1-eve", "arc-01-long-s-c3-eve", "arc-01-long-s-c4-eve"])
        for rec, data in refs:
            self.assertEqual(image.size_of(data), (1920, 1080))     # the file itself, not a thumbnail
            self.assertEqual(image.sha256(data), rec["sha256"])
        body = image.payload(still["prompt"], refs, req["subject"])
        parts = body["contents"][0]["parts"]
        self.assertEqual(len(parts), 4)
        self.assertEqual(base64.b64decode(parts[0]["inline_data"]["data"]), refs[0][1])
        self.assertIn("ONE new image, a wide 16:9 frame", parts[-1]["text"])
        self.assertEqual(body["generationConfig"]["imageConfig"], {"aspectRatio": "16:9"})
        self.assertEqual(body["generationConfig"]["candidateCount"], 1)

    def test_a_draft_or_altered_reference_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            req = json.loads(REQUEST.read_text())
            req["refs"] = ["migration/production/bible/stills/arc-01-long-s-c3-eve-near.json"]   # a DRAFT
            p = Path(d) / "r.json"
            p.write_text(json.dumps(req))
            self.assertTrue(any("REF_NOT_APPROVED" in x for x in image.load_request(p)[3]))
            with self.assertRaises(image.Refusal) as c:
                image.generate(p, d, KEY, opener=opener_for(answer_with(PNG)))
            self.assertEqual(c.exception.code, 2)


class Generate(unittest.TestCase):
    def test_one_candidate_with_its_record(self):
        seen = []
        with tempfile.TemporaryDirectory() as d:
            rec = image.generate(REQUEST, d, KEY, opener=opener_for(answer_with(PNG), seen=seen))
            self.assertEqual((rec["status"], rec["size"], rec["is_16_9"]), ("DRAFT", [1344, 768], False))
            self.assertEqual(Path(d, rec["file"]).read_bytes(), PNG)
            self.assertEqual(rec["sha256"], image.sha256(PNG))
            self.assertEqual(len(rec["references"]), 3)
            self.assertIn("won't claim ownership", rec["licence"]["ownership"])
            saved = json.loads(Path(d, rec["id"] + ".json").read_text())
            self.assertNotIn(KEY, json.dumps(saved))
        self.assertEqual(seen[0].get_header("X-goog-api-key"), KEY)     # header, never the URL
        self.assertNotIn(KEY, seen[0].full_url)

    def test_quota_and_billing_refuse_cleanly_without_the_key(self):
        quota = {"error": {"status": "RESOURCE_EXHAUSTED", "message": f"Quota exceeded, limit: 0 (key {KEY})"}}
        billing = {"error": {"status": "FAILED_PRECONDITION", "message": "Image generation requires billing."}}
        other = {"error": {"status": "INVALID_ARGUMENT", "message": "bad"}}
        for status, err, code in ((429, quota, 3), (400, billing, 4), (400, other, 5)):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(image.Refusal) as c:
                    image.generate(REQUEST, d, KEY, opener=opener_for(status=status, error=err))
                self.assertEqual(list(Path(d).iterdir()), [])             # nothing saved
            self.assertEqual(c.exception.code, code)
            self.assertNotIn(KEY, str(c.exception))

    def test_an_answer_without_an_image_is_named(self):
        text = {"candidates": [{"content": {"parts": [{"text": "I can't"}]}, "finishReason": "IMAGE_SAFETY"}]}
        with tempfile.TemporaryDirectory() as d, self.assertRaises(image.Refusal) as c:
            image.generate(REQUEST, d, KEY, opener=opener_for(text))
        self.assertEqual(c.exception.code, 6)
        self.assertIn("IMAGE_SAFETY", c.exception.detail)

    def test_main_never_prints_the_key(self):
        import contextlib
        import os
        from unittest import mock
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"HERO_GEMINI_API_KEY": KEY}), contextlib.redirect_stdout(buf), \
                mock.patch.object(image, "models", side_effect=image.Refusal(5, "API_REFUSED", f"echo {KEY}")):
            self.assertEqual(image.main(["image.py", "models"]), 5)
        self.assertNotIn(KEY, buf.getvalue())


class Workflow(unittest.TestCase):
    def test_key_only_from_secrets_inputs_through_env_pinned_actions(self):
        wf = (ROOT / ".github/workflows/gemini-image.yml").read_text()
        self.assertIn("HERO_GEMINI_API_KEY: ${{ secrets.HERO_GEMINI_API_KEY }}", wf)
        self.assertNotIn("${{ inputs.", wf.split("env:", 1)[1].split("steps:", 1)[1])   # inputs reach run: via env
        for use in [l for l in wf.splitlines() if "uses:" in l]:
            self.assertRegex(use, r"@[0-9a-f]{40}")
        self.assertNotIn("schedule:", wf)
        self.assertNotIn("set -x", wf)


if __name__ == "__main__":
    unittest.main()
