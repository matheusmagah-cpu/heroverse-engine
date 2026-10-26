#!/usr/bin/env python3
"""Offline checks of the Pavo clip path: only the Pavo CDN is fetched, the list is validated, the output is
2560x1440 30 fps without audio and the record carries the library schema plus Pavo's provenance (no network, no
model: a stub stands in for Real-ESRGAN)."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pavo_footage as pf  # noqa: E402

GOOD = "https://cos-aigc-default.agnes-ai.space/aigc/video/2026/10/25/abc-123_def.mp4"


def entry(**kw):
    e = {"id": "pavo-ark-door", "conversation_id": "conv-1", "url": GOOD, "prompt": "The ark's door closes, rain",
         "words": "and the LORD shut him in"}
    e.update(kw)
    return e


def write_list(d, items):
    p = Path(d) / "pavo.json"
    p.write_text(json.dumps(items))
    return p


def stub(img):
    """Nearest-neighbour 4x: shape-correct stand-in for the model (tests only)."""
    return img.repeat(4, axis=0).repeat(4, axis=1)


def synthetic(dst, size="1280x720", rate=24, seconds=1, audio=True):
    """A tiny clip like Pavo's: 24 fps with an AAC track."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=f=440:duration={seconds}", "-c:a", "aac"]
    subprocess.run(cmd + ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-shortest", str(dst)],
                   check=True)


class Urls(unittest.TestCase):
    def test_only_the_pavo_cdn_without_query(self):
        self.assertTrue(pf.url_ok(GOOD))
        for bad in (GOOD.replace("https://", "http://"), GOOD + "?x-oss-signature=1", GOOD + "#t=1",
                    GOOD.replace(".mp4", ".mov"), "https://cos-aigc-default.agnes-ai.space.evil.com/a.mp4",
                    "https://evil.com/cos-aigc-default.agnes-ai.space/a.mp4",
                    "https://user@cos-aigc-default.agnes-ai.space/a.mp4",
                    "https://cos-aigc-default.agnes-ai.space:8443/a.mp4",
                    "https://cos-aigc-default.agnes-ai.space/../a.mp4",
                    "https://cos-aigc-default.agnes-ai.space/a.mp4\n", "file:///etc/passwd", "", None):
            self.assertFalse(pf.url_ok(bad), bad)

    def test_download_refuses_before_any_request(self):
        with self.assertRaises(SystemExit):
            pf.download("https://example.com/a.mp4", "/nonexistent/x")


class Lists(unittest.TestCase):
    def test_bad_entries_refused(self):
        with tempfile.TemporaryDirectory() as d:
            for items, code in (([entry(url=GOOD + "?a=b")], "PAVO_URL_REFUSED"), ([entry(id="clip-x")], "PAVO_BAD_ID"),
                                ([entry(id="pavo-$(id)")], "PAVO_BAD_ID"), ([entry(id="pavo-ark\n")], "PAVO_BAD_ID"),
                                ([entry(), entry()], "PAVO_DUPLICATE_ID"), ([entry(words="")], "PAVO_MISSING_WORDS"),
                                ([entry(conversation_id=None)], "PAVO_MISSING_CONVERSATION_ID"), ([], "PAVO_LIST_EMPTY")):
                with self.assertRaises(SystemExit) as ctx:
                    pf.entries(write_list(d, items))
                self.assertIn(code, str(ctx.exception))

    def test_plan_skips_clips_already_in_the_library(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d) / "library"
            lib.mkdir()
            (lib / "pavo-ark-door.json").write_text("{}")
            p = write_list(d, {"clips": [entry(), entry(id="pavo-rain-falls")]})
            self.assertEqual(pf.plan(p, lib), ["pavo-rain-falls"])


class Make(unittest.TestCase):
    def test_output_spec_and_record(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.mp4"
            synthetic(src)
            self.assertTrue(pf.probe(src)[4])   # the fixture really carries audio, like Pavo's
            fetched = []
            rec = pf.make(write_list(d, [entry()]), "pavo-ark-door", Path(d) / "out", None, frame_fn=stub,
                          fetch=lambda url, dst: (fetched.append(url), shutil.copy(src, dst)))
            self.assertEqual(fetched, [GOOD])
            mp4 = Path(d) / "out" / "pavo-ark-door.mp4"
            w, h, fps, seconds, audio = pf.probe(mp4)
            self.assertEqual((w, h, round(fps), audio), (2560, 1440, 30, False))
            self.assertAlmostEqual(seconds, 1.0, delta=0.1)
            pix = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=pix_fmt,codec_name", "-of", "csv=p=0",
                                  str(mp4)], capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(pix, "h264,yuv420p")
            self.assertFalse((Path(d) / "out" / "pavo-ark-door.src.mp4").exists())
            self.assertEqual(json.loads((Path(d) / "out" / "pavo-ark-door.json").read_text()), rec)
            # the library schema (footage.py) ...
            lib = json.loads(next((Path(__file__).resolve().parent / "library").glob("clip-*.json")).read_text())
            for k in ("id", "theme", "query", "source", "title", "page", "author", "licence_url", "licence",
                      "licence_as_published", "source_seconds", "source_height", "start", "seconds", "credit",
                      "picture", "frame", "sha256", "vetting", "release_asset"):
                self.assertIn(k, rec, k)
                self.assertIn(k, lib, k)
            self.assertEqual(rec["picture"], lib["picture"])
            # ... plus Pavo's provenance
            self.assertEqual((rec["source"], rec["licence"], rec["licence_url"], rec["credit"]),
                             ("pavo", "Pavo generated (owner-owned)", "https://app.pavo-ai.work/terms",
                              "AI video: Pavo (Agnes Video Flash), owner-owned output"))
            self.assertEqual((rec["conversation_id"], rec["prompt"], rec["words"]),
                             ("conv-1", entry()["prompt"], entry()["words"]))
            self.assertEqual(rec["frame"], [2560, 1440])
            self.assertEqual(rec["vetting"], "PENDING")
            self.assertEqual((rec["release_asset"], rec["release_tag"]), (None, None))
            self.assertEqual(rec["upscaler"]["licence"], "bsd-3-clause")
            self.assertEqual(rec["upscaler"]["source"], pf.upscale.WEIGHTS_URL)
            import hashlib
            self.assertEqual(rec["sha256"], hashlib.sha256(mp4.read_bytes()).hexdigest())

    def test_non_16_9_or_small_source_refused(self):
        with tempfile.TemporaryDirectory() as d:
            for size in ("720x1280", "640x360"):
                src = Path(d) / f"{size}.mp4"
                synthetic(src, size=size, audio=False)
                with self.assertRaises(SystemExit) as ctx:
                    pf.make(write_list(d, [entry()]), "pavo-ark-door", Path(d) / "out", None, frame_fn=stub,
                            fetch=lambda url, dst: shutil.copy(src, dst))
                self.assertIn("PAVO_SOURCE_NOT_720P_16_9", str(ctx.exception))

    def test_a_plain_resize_is_not_the_upscaler(self):
        """The default frame function is Real-ESRGAN with the pinned weights: wrong weights are refused."""
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "w.pth"
            fake.write_bytes(b"not the model")
            with self.assertRaises(SystemExit) as ctx:
                pf.real_esrgan(fake)
            self.assertIn("WEIGHTS_SHA256_MISMATCH", str(ctx.exception))
        self.assertEqual(pf.upscale.WEIGHTS_SHA256, "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292")

    def test_workflow_pins_the_same_weights_and_path_regex(self):
        root = Path(__file__).resolve().parents[3]
        wf = (root / ".github" / "workflows" / "pavo-footage.yml").read_text()
        self.assertIn(pf.upscale.WEIGHTS_SHA256, wf)
        self.assertIn(pf.upscale.WEIGHTS_URL, wf)
        self.assertIn(r"^migration/production/pilot-[0-9]{3}/pavo(-[0-9]+)?\.json$", wf)
        self.assertIn("max-parallel: 10", wf)


if __name__ == "__main__":
    unittest.main()
