#!/usr/bin/env python3
"""Offline tests of the ChatGPT image runner's rules and bridge (no browser, no network)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chatgpt_core as core  # noqa: E402

NOW = datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", 1536, 864) + b"\x08\x02\x00\x00\x00" + b"\x00" * 16
JOB = {"id": "arc-01-long-s-c3-eve-near-chatgpt-1", "prompt": "Eve walks toward the great tree.",
       "refs": [{"name": "a.png", "sha256": core.sha256(PNG)}]}


class Rules(unittest.TestCase):
    def test_a_valid_job_and_its_refusals(self):
        self.assertEqual(core.job_problems(JOB, [("a.png", PNG)]), [])
        self.assertIn("REF_SHA256_MISMATCH a.png", core.job_problems(JOB, [("a.png", PNG + b"x")]))
        self.assertIn("REF_NOT_AN_IMAGE b.txt", core.job_problems(JOB, [("b.txt", b"hello")]))
        self.assertTrue(core.job_problems(dict(JOB, id="Bad ID"), [("a.png", PNG)]))
        self.assertTrue(core.job_problems(JOB, [("a.png", PNG)] * 5))

    def test_one_at_a_time_a_gap_and_a_day_cap(self):
        ledger = core.empty_ledger()
        self.assertIsNone(core.gate(ledger, "j1", NOW))
        ledger["requests"]["j1"] = {"state": "SAVED", "at": core.iso(NOW - timedelta(minutes=1))}
        self.assertTrue(core.gate(ledger, "j1", NOW).startswith("ALREADY_SAVED"))     # never twice
        self.assertTrue(core.gate(ledger, "j2", NOW).startswith("WAIT_MIN_GAP"))
        for i in range(core.DAY_CAP):
            ledger["requests"][f"x{i}"] = {"state": "SAVED", "at": core.iso(NOW - timedelta(hours=2))}
        self.assertEqual(core.gate(ledger, "j3", NOW), "DAY_CAP_REACHED")

    def test_challenges_and_limits_are_named(self):
        self.assertEqual(core.blocked("Just a moment... Verify you are human")[0], "CHALLENGE")
        self.assertEqual(core.blocked("You've hit the Plus plan limit for image generation requests.")[0], "LIMIT")
        self.assertIsNone(core.blocked("Here is your image of Eve in the garden."))

    def test_the_prompt_asks_for_one_wide_image(self):
        self.assertIn("ONE image, a wide 16:9", core.full_prompt("Eve."))

    def test_the_record_cites_the_licence_and_the_refs(self):
        rec = core.record(JOB, [("a.png", PNG)], PNG, "https://chatgpt.com/c/abc", NOW, NOW)
        self.assertEqual((rec["size"], rec["is_16_9"], rec["status"]), ([1536, 864], True, "DRAFT"))
        self.assertIn("own the Output", rec["licence"]["ownership"])
        self.assertEqual(rec["references"][0]["sha256"], core.sha256(PNG))

    def test_sizes_of_png_jpeg_webp(self):
        jpg = b"\xff\xd8\xff\xe0\x00\x04ab\xff\xc0\x00\x11\x08" + struct.pack(">HH", 1080, 1920) + b"\x03" + b"\x00" * 9
        webp = b"RIFF\x00\x00\x00\x00WEBPVP8X" + b"\x00" * 8 + (1535).to_bytes(3, "little") + (863).to_bytes(3, "little")
        self.assertEqual(core.size_of(PNG), (1536, 864))
        self.assertEqual(core.size_of(jpg), (1920, 1080))
        self.assertEqual(core.size_of(webp), (1536, 864))

    def test_state_is_written_on_a_fresh_install(self):
        with tempfile.TemporaryDirectory() as d:
            core.write_json(Path(d) / "out" / "x" / "r.json", {"ok": 1})
            self.assertEqual(core.read_json(Path(d) / "out" / "x" / "r.json", None), {"ok": 1})


class Bridge(unittest.TestCase):
    @unittest.skipUnless(len(HERE.parents) > 2 and (HERE.parents[1] / "production").exists(), "repository only")
    def test_the_eve_job_names_approved_stills_by_url_and_sha256(self):
        import bridge
        st = "migration/production/bible/stills/"
        job = bridge.make_job(st + "arc-01-long-s-c3-eve-near.json", "the same woman, Eve",
                              [st + f"arc-01-long-s-{s}-eve.json" for s in ("c1", "c3", "c4")], "abc123")
        self.assertEqual(job["id"], "arc-01-long-s-c3-eve-near-chatgpt-1")
        self.assertEqual(len(job["refs"]), 3)
        self.assertTrue(job["refs"][0]["url"].endswith("/abc123/" + st + "arc-01-long-s-c1-eve.jpg"))
        self.assertIn("period wardrobe", job["prompt"])
        self.assertEqual(core.job_problems(job, [(r["name"], (HERE.parents[1] / "production/bible/stills" / r["name"]).read_bytes())
                                                 for r in job["refs"]]), [])
        with self.assertRaises(SystemExit):
            bridge.make_job(st + "arc-01-long-s-c3-eve-near.json", "Eve", [st + "arc-01-long-s-c3-eve-near.json"])


class Source(unittest.TestCase):
    def test_no_cookie_value_spoofing_proxy_or_captcha_code(self):
        src = (HERE / "runner.py").read_text() + (HERE / "mcp_server.py").read_text() + (HERE / "bridge.py").read_text()
        for banned in ('["value"]', "['value']", "stealth", "navigator.webdriver", "add_init_script", "proxy=",
                       "2captcha", "anticaptcha", "storage_state("):
            self.assertFalse(banned in src, banned)
        self.assertIn('c["name"].startswith(SESSION_COOKIE)', src)


if __name__ == "__main__":
    unittest.main()
