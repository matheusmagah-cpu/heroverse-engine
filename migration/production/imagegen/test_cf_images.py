#!/usr/bin/env python3
"""Offline: E62 images made before the free allocation runs out are kept; the rest are deferred."""
import io
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cf_images as cf  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def png():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 150, 60)).save(buf, "PNG")
    return buf.getvalue()


class Allocation(unittest.TestCase):
    def test_e214_generation_post_is_never_replayed_after_an_http_error(self):
        # A 5xx acknowledgement may follow an accepted generation. Retrying it is not a safe GET retry.
        for status in (400, 401, 403, 408, 500, 502, 503, 504):
            with self.subTest(status=status):
                def refused(*args, **kwargs):
                    raise HTTPError('https://api.cloudflare.com/generation', status, 'refused', {},
                                    io.BytesIO(b'private-provider-details'))
                with mock.patch.dict(cf.os.environ, {'CLOUDFLARE_API_TOKEN': 'offline-token',
                                                    'CLOUDFLARE_ACCOUNT_ID': 'offline-account'}), \
                        mock.patch.object(cf.urllib.request, 'urlopen', side_effect=refused) as post, \
                        mock.patch.object(cf.time, 'sleep'):
                    with self.assertRaises(RuntimeError) as err:
                        cf.run('offline-model', {'prompt': 'offline fixture'})
                    self.assertEqual(post.call_count, 1, 'A generation POST was replayed')
                    self.assertNotIn('private-provider-details', str(err.exception))
                    self.assertIn('NO_REPLAY', str(err.exception))

    def test_generation_timeout_or_invalid_response_requires_reconciliation(self):
        for failure in (TimeoutError('private-details'), URLError('private-details'),
                        ValueError('private-details')):
            with self.subTest(failure=type(failure).__name__), \
                    mock.patch.dict(cf.os.environ, {'CLOUDFLARE_API_TOKEN': 'offline-token',
                                                'CLOUDFLARE_ACCOUNT_ID': 'offline-account'}), \
                    mock.patch.object(cf.urllib.request, 'urlopen', side_effect=failure) as post:
                with self.assertRaisesRegex(RuntimeError, 'CF_GENERATION_OUTCOME_UNCERTAIN_NO_REPLAY') as err:
                    cf.run('offline-model', {'prompt': 'offline fixture'})
                self.assertEqual(post.call_count, 1)
                self.assertNotIn('private-details', str(err.exception))

    def test_single_generation_response_and_allocation_deferral_remain_supported(self):
        for raw, ctype in ((png(), 'image/png'),
                           (json.dumps({'result': {'image': base64.b64encode(png()).decode()}}).encode(),
                            'application/json')):
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = raw
            response.headers = {'Content-Type': ctype}
            with mock.patch.dict(cf.os.environ, {'CLOUDFLARE_API_TOKEN': 'offline-token',
                                                'CLOUDFLARE_ACCOUNT_ID': 'offline-account'}), \
                    mock.patch.object(cf.urllib.request, 'urlopen', return_value=response) as post:
                self.assertEqual(cf.run('offline-model', {'prompt': 'fixture'}), png())
                self.assertEqual(post.call_count, 1)
        with mock.patch.dict(cf.os.environ, {'CLOUDFLARE_API_TOKEN': 'offline-token',
                                            'CLOUDFLARE_ACCOUNT_ID': 'offline-account'}), \
                mock.patch.object(cf.urllib.request, 'urlopen', side_effect=HTTPError(
                    'https://api.cloudflare.com/generation', 429, 'refused', {},
                    io.BytesIO(b'free allocation used up'))) as post:
            with self.assertRaisesRegex(SystemExit, 'CF_DAILY_ALLOCATION_EXHAUSTED'):
                cf.run('offline-model', {'prompt': 'fixture'})
            self.assertEqual(post.call_count, 1)

    def test_images_before_the_allocation_ran_out_are_kept(self):
        # E62: run 40047828009 failed on "used up your daily free allocation" and every image of the run was lost
        calls = []

        def fake(model, payload):
            calls.append(payload["prompt"])
            if len(calls) > 2:
                raise SystemExit("CF_DAILY_ALLOCATION_EXHAUSTED you have used up your daily free allocation")
            return png()
        with tempfile.TemporaryDirectory() as t:
            spec = Path(t) / "images.json"
            spec.write_text(json.dumps({"style": "s", "images": [{"id": f"bg-{i}", "prompt": "p", "seed": i} for i in range(5)]}))
            with mock.patch.object(cf, "run", fake):
                self.assertEqual(cf.main(spec, Path(t) / "img"), "DEFERRED")
            self.assertEqual(sorted(p.name for p in (Path(t) / "img").glob("*.png")), ["bg-0.png", "bg-1.png"])
            with mock.patch.object(cf, "run", side_effect=RuntimeError("CF_HTTP_500 x")):
                with self.assertRaises(RuntimeError):         # any other error still fails
                    cf.main(spec, Path(t) / "img2")
        wf = (ROOT / ".github/workflows/cf-images.yml").read_text()
        self.assertIn("CF_ALLOCATION_EXHAUSTED_DEFERRED", wf)
        self.assertIn("if: env.NO_IMAGES != '1'", wf)


class ErrorDetailTests(unittest.TestCase):
    def test_e260_a_refusal_names_the_provider_code_without_ids(self):
        body = json.dumps({"errors": [{"code": 4006, "message": "you have used up your daily free allocation of 10,000 neurons for account a6384d28432b16b02970b4ffe92731ce"}]})
        d = cf.cf_error_detail(body)
        self.assertIn("cf4006", d)
        self.assertNotIn("a6384d28432b16b02970b4ffe92731ce", d)
        self.assertEqual(cf.cf_error_detail("not json"), "detail=none")

if __name__ == "__main__":
    unittest.main()
