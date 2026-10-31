#!/usr/bin/env python3
"""Offline tests of the ChatGPT app driver's rules and bridge (no app, no network)."""
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


class JobFile(unittest.TestCase):
    def test_a_missing_or_broken_job_file_is_a_named_refusal(self):
        # E143: the PC's first `runner.py job` (now app_driver.py job) named a job not written yet (its folder did not exist) and died with a
        # FileNotFoundError traceback instead of an exit code the bridge can read
        import contextlib
        import io
        import app_driver  # noqa: E402  (the app is not touched before the job is read)
        with tempfile.TemporaryDirectory() as d, mock_lock(app_driver, d):
            bad = Path(d) / "broken.json"
            bad.write_text("{not json")
            for path in (str(Path(d) / "missing.json"), str(bad)):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(app_driver.main(["job", path]), 2)
                self.assertIn("JOB_UNREADABLE", buf.getvalue())


class FakeEl:
    """A UI Automation wrapper as pywinauto returns it from Desktop().windows(): element_info, rectangle(),
    descendants(), and no child_window()."""
    def __init__(self, ctype, name="", cls="", rect=(0, 0, 10, 10), pid=1, kids=()):
        from types import SimpleNamespace
        self.element_info = SimpleNamespace(control_type=ctype, name=name, class_name=cls, process_id=pid)
        self._r, self._kids = rect, list(kids)

    def rectangle(self):
        from types import SimpleNamespace
        l, t, r, b = self._r
        return SimpleNamespace(left=l, top=t, right=r, bottom=b, width=lambda: r - l, height=lambda: b - t)

    def descendants(self):
        return self._kids


class AppWrappers(unittest.TestCase):
    def test_the_new_chat_button_comes_from_the_wrapper_itself(self):
        # E233: the first real run called child_window() on the wrapper Desktop().windows() returns and crashed
        import app_driver
        top = FakeEl("Button", "Novo chat", rect=(60, 96, 282, 126))
        low = FakeEl("Button", "Novo chat", rect=(322, 434, 346, 458))
        w = FakeEl("Window", "ChatGPT", kids=[low, FakeEl("Button", "Juninho"), top])
        self.assertFalse(hasattr(w, "child_window"))
        self.assertIs(app_driver.new_chat_button(w), top)
        self.assertIsNone(app_driver.new_chat_button(FakeEl("Window", kids=[])))

    def test_the_open_dialog_is_found_by_its_class_inside_the_app(self):
        # E234: the app's Open dialog was looked for among the desktop's windows by title and never found
        import app_driver
        from unittest import mock
        dlg = FakeEl("Window", "Selecionar arquivos", cls="#32770")
        w = FakeEl("Window", "ChatGPT", kids=[FakeEl("Button", "Enviar"), dlg])
        fake_desktop = mock.Mock()
        fake_desktop.return_value.windows.return_value = []
        with mock.patch.dict(sys.modules, {"pywinauto": mock.Mock(Desktop=fake_desktop)}):
            self.assertIs(app_driver.file_dialog(w), dlg)
            self.assertIsNone(app_driver.file_dialog(FakeEl("Window", kids=[FakeEl("Button", "Enviar")])))


class Hands(unittest.TestCase):
    def test_no_click_or_key_reaches_another_window(self):
        # E235: on the PC in use, the owner's Claude app came over ChatGPT and the driver's '+' click landed outside
        # the app; every click and key now checks the app's process is the one in front and under the pointer
        import app_driver
        from unittest import mock
        fake_mouse = mock.Mock()
        fake_kb = mock.Mock()
        pw = mock.Mock(mouse=fake_mouse)
        mods = {"pywinauto": pw, "pywinauto.mouse": fake_mouse, "pywinauto.keyboard": fake_kb}
        el = FakeEl("Button", "Enviar", rect=(100, 100, 140, 130))
        with mock.patch.dict(sys.modules, mods), mock.patch.object(app_driver.time, "sleep"), \
                mock.patch.object(app_driver, "ours_at", return_value=False), \
                mock.patch.object(app_driver, "foreground_pid", return_value=999), \
                mock.patch.dict(app_driver.APP, {"pids": {42}, "win": None}), \
                mock.patch.object(app_driver.ctypes, "windll", create=True):
            with self.assertRaises(app_driver.Stop) as c:
                app_driver.glide_click(el)
            self.assertIn("APP_NOT_IN_FRONT", str(c.exception))
            fake_mouse.click.assert_not_called()
            with self.assertRaises(app_driver.Stop):
                app_driver.keys("^v")
            fake_kb.send_keys.assert_not_called()


def mock_lock(mod, d):
    from unittest import mock
    import contextlib
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch.object(mod, "LOCK", Path(d) / "runner.lock"))
    stack.enter_context(mock.patch.object(mod, "LOG", Path(d) / "logs" / "driver.log"))
    return stack


class Source(unittest.TestCase):
    def test_no_cookie_value_spoofing_proxy_or_captcha_code(self):
        src = (HERE / "app_driver.py").read_text() + (HERE / "mcp_server.py").read_text() + (HERE / "bridge.py").read_text()
        for banned in ('["value"]', "['value']", "stealth", "navigator.webdriver", "add_init_script", "proxy=",
                       "2captcha", "anticaptcha", "storage_state("):
            self.assertFalse(banned in src, banned)
        self.assertIn("x > 350", src)          # the sidebar (the owner's other chats) is never read


if __name__ == "__main__":
    unittest.main()
