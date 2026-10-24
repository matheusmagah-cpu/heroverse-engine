#!/usr/bin/env python3
"""Offline: E62 images made before the free allocation runs out are kept; the rest are deferred."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cf_images as cf  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def png():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 150, 60)).save(buf, "PNG")
    return buf.getvalue()


class Allocation(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
