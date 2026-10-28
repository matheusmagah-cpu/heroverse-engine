"""Agnes Image 2.5 Flash stills: price, submission recovery and credential regressions; no network or real secrets."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib
from urllib.error import URLError

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from client import ORIGIN, PavoError
from image_gen import IMAGE_MODEL, IMAGE_RATIOS, PavoImageClient
import images
from quota import (COOL_DOWN, DAILY_CAP, FAILED_STREAK, IMAGE_UNITS, LEDGER, NO_ACTIONS, VIDEO_UNITS, MAX_UNREAD, SHORTS_DAILY_JOBS, QuotaGuard,
                   combine, git_actions_usage, probe_record_path, record_usage)
from video import MODEL as VIDEO_MODEL
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


def failed_history():
    return envelope({"is_running": False, "turns": [{"assistant": [{"type": "GenerationFailed", "data": {}}]}]})


class FreeQuota(unittest.TestCase):
    """E124 (2026-10-27): the free agnes-image quota ran out after ~180 stills in one day; pavo_quote_image kept
    quoting an exact 0 and pavo_image_job only read "failed" with no reason, so 31 submissions of genesis-09 run
    2026102705 were spent on nothing. The guard stops the burn: a daily cap before any call, and two failed read-backs
    in a row suspend generation (a possible quota stop) for a cool-down or until a job reads back completed."""
    token = "synthetic-offline-pavo-credential"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "image-ledger.json"
        self.t = datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def guard(self, cap=None):
        return QuotaGuard(self.ledger, cap=cap, now=lambda: self.t)

    def client(self, *responses, cap=None):
        return PavoImageClient(self.token, Responses(*responses), guard=self.guard(cap))

    def submit(self, cap=None):
        return self.client(quote(), envelope({"conversation_id": "777"}), started(IMAGE_MODEL),
                           cap=cap).generate_image("A dry plain at dusk.")

    def test_e137_no_fixed_daily_total_blocks_a_live_quota_and_only_the_owner_can_cap_a_day(self):
        """E137 (28/10): Pavo's quota is a rolling window (~35-50 jobs back ~3 h after a stop, ~9-12 jobs an hour);
        E128's fixed 120 units a UTC day refused work while the quota was live. Every submission is still counted."""
        self.ledger.write_text(json.dumps({"days": {"2026-10-27": {"generated": 250}}, "daily_cap": 120}))
        self.assertEqual(self.submit()["status"], "submitted")      # 250 used today: no fixed total refuses it
        self.assertEqual(json.loads(self.ledger.read_text())["days"]["2026-10-27"]["generated"], 251)
        saved = os.environ.get("PAVO_IMAGE_DAILY_CAP")
        try:
            os.environ["PAVO_IMAGE_DAILY_CAP"] = "251"                # the owner's explicit cap still holds
            fake = Responses()
            with self.assertRaisesRegex(PavoError, "PAVO_DAILY_CAP"):
                PavoImageClient(self.token, fake, guard=self.guard()).generate_image("A dry plain at dusk.")
            self.assertEqual(fake.calls, [])              # refused before the quote: nothing sent
        finally:
            if saved is None:
                os.environ.pop("PAVO_IMAGE_DAILY_CAP", None)
            else:
                os.environ["PAVO_IMAGE_DAILY_CAP"] = saved
        self.assertEqual((DAILY_CAP, SHORTS_DAILY_JOBS), (120, 25))

    def test_two_failed_read_backs_suspend_generation_until_a_cool_down_or_a_success(self):
        for job in ("11", "12"):
            self.assertEqual(self.client(failed_history()).image_job(job)["status"], "failed")
        self.client(failed_history()).image_job("12")     # the same job read twice counts once
        fake = Responses()
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            PavoImageClient(self.token, fake, guard=self.guard()).generate_image("A dry plain at dusk.")
        self.assertEqual(fake.calls, [])
        self.t += timedelta(hours=2, minutes=59)
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            self.client().generate_image("A dry plain at dusk.")
        self.t += timedelta(minutes=2)                    # the cool-down passed: one probe may go
        probe = self.submit()["conversation_id"]
        self.client(failed_history()).image_job(probe)    # the probe failed too: suspended again at once
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            self.client().generate_image("A dry plain at dusk.")
        self.t += timedelta(hours=3, minutes=1)
        probe = self.submit()["conversation_id"]
        ok = self.client(history([{"url": CDN, "width": 768, "height": 1344}])).image_job(probe)
        self.assertEqual(ok["status"], "completed")       # the probe completed: the suspension is lifted
        self.assertEqual(self.submit()["status"], "submitted")

    def test_e136_no_new_submission_while_two_of_todays_jobs_are_unread(self):
        """E136 (28/10): 11 stills went back to back before any read-back, the quota had run out and 10 came back
        failed; FAILED_STREAK can only stop a fan-out when read-backs come between submissions."""
        def submit(job):
            return self.client(quote(), envelope({"conversation_id": job}), started(IMAGE_MODEL)).generate_image(
                "A dry plain at dusk.")
        self.assertEqual(submit("31")["status"], "submitted")
        self.assertEqual(submit("32")["status"], "submitted")
        fake = Responses()
        with self.assertRaisesRegex(PavoError, "PAVO_UNREAD_JOBS 31,32"):
            PavoImageClient(self.token, fake, guard=self.guard()).generate_image("A dry plain at dusk.")
        self.assertEqual(fake.calls, [])                  # refused before the quote: nothing sent
        self.client(history([{"url": CDN}])).image_job("31")   # one read back completed: one more may go
        self.assertEqual(submit("33")["status"], "submitted")
        with self.assertRaisesRegex(PavoError, "PAVO_UNREAD_JOBS"):
            self.client().generate_image("A dry plain at dusk.")
        self.client(failed_history()).image_job("32")    # a failed read-back is read too
        self.assertEqual(submit("34")["status"], "submitted")
        self.t += timedelta(days=1)                       # yesterday's unread jobs do not hold today
        self.assertEqual(submit("35")["status"], "submitted")
        self.assertEqual(MAX_UNREAD, 2)

    def test_one_failure_alone_does_not_suspend(self):
        self.client(failed_history()).image_job("11")
        self.client(history([{"url": CDN}])).image_job("12")
        self.client(failed_history()).image_job("14")
        self.assertEqual(self.submit()["status"], "submitted")

    def suspend(self):
        for job in ("11", "12"):
            self.client(failed_history()).image_job(job)

    def test_after_the_cool_down_exactly_one_probe_goes_until_it_reads_back(self):
        # review of #466: every submission went through once suspended_until had passed
        self.suspend()
        self.t += timedelta(hours=3, minutes=1)
        probe = self.submit()
        self.assertEqual(probe["status"], "submitted")
        for _ in range(3):
            with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
                self.client().generate_image("A dry plain at dusk.")
        self.client(history([], running=True)).image_job(probe["conversation_id"])   # still running: no change
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            self.client().generate_image("A dry plain at dusk.")
        self.client(history([{"url": CDN}])).image_job(probe["conversation_id"])     # the probe completed
        self.assertEqual(self.submit()["status"], "submitted")
        self.assertEqual(self.submit()["status"], "submitted")

    def test_only_a_job_submitted_after_the_suspension_lifts_it(self):
        old = self.submit()["conversation_id"]                                       # submitted before the stop
        self.t += timedelta(minutes=1)
        self.suspend()
        self.client(history([{"url": CDN}])).image_job(old)                          # an older job completing
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            self.client().generate_image("A dry plain at dusk.")

    def test_an_unreadable_ledger_fails_closed(self):
        day = self.t.strftime("%Y-%m-%d")
        for text in ("<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> main\n", "[]", "{",
                     json.dumps({"days": {}, "suspended_until": "garbage"}),
                     json.dumps({"days": {}, "suspended_until": "2026-10-28T00:00:00"}),      # naive
                     json.dumps({"days": {day: {"generated": "500"}}}),
                     json.dumps({"days": {day: {"generated": -1}}}),
                     json.dumps({"days": [], "failed_streak": 0}),
                     json.dumps({"days": {}, "failed_streak": "2"})):
            self.ledger.write_text(text)
            fake = Responses()
            with self.subTest(text=text), self.assertRaisesRegex(PavoError, "PAVO_LEDGER_UNREADABLE"):
                PavoImageClient(self.token, fake, guard=self.guard()).generate_image("A dry plain at dusk.")
            self.assertEqual(fake.calls, [])
        self.ledger.unlink()                                                         # no ledger yet: a fresh day
        self.assertEqual(self.submit()["status"], "submitted")

    def test_the_env_cap_never_crashes_and_the_write_is_atomic_under_a_unique_name(self):
        import os
        saved = os.environ.get("PAVO_IMAGE_DAILY_CAP")
        try:
            for bad in ("\u00b2", "-3", "abc", "1e3", ""):
                os.environ["PAVO_IMAGE_DAILY_CAP"] = bad
                self.assertEqual(QuotaGuard(self.ledger).cap(), DAILY_CAP, bad)
            os.environ["PAVO_IMAGE_DAILY_CAP"] = "7"
            self.assertEqual(QuotaGuard(self.ledger).cap(), 7)
        finally:
            if saved is None:
                os.environ.pop("PAVO_IMAGE_DAILY_CAP", None)
            else:
                os.environ["PAVO_IMAGE_DAILY_CAP"] = saved
        src = (HERE / "quota.py").read_text()
        self.assertNotIn('with_suffix(".tmp")', src)
        self.assertIn("tempfile.mkstemp", src)

    def test_the_server_wires_the_guard_and_the_readme_warns_the_quote_is_not_the_quota(self):
        src = (HERE / "server.py").read_text()
        self.assertIn("PavoImageClient(guard=QuotaGuard(actions=git_actions_usage))", src)   # E128: Actions too
        self.assertIn("A 0 quote does not mean the free quota is available", (HERE / "README.md").read_text())
        self.assertEqual(QuotaGuard().path, LEDGER)
        self.assertEqual((FAILED_STREAK, COOL_DOWN), (2, timedelta(hours=3)))


def video_failed():
    return envelope({"is_running": False, "turns": [{"assistant": [{"type": "GenerationFailed", "data": {}}]}]})


def probe_record(outcomes):
    """A shot-probe record shaped like run 40592173923's: {shot: clips: [{generations: [...]}]}; OUTCOMES is
    [(shot, conversation id, got a video)] in any order (the record lists shots in risk order, not by time)."""
    shots = {}
    for shot, cid, ok in outcomes:
        clips = shots.setdefault(shot, {"clips": [{"round": 1, "generations": []}]})["clips"]
        clips[0]["generations"].append({"conversation_id": cid, "submission": "submitted",
                                        "flags": [] if ok else ["NO_VIDEO"]})
    return {"episode": "arc-01-long", "shots": shots}


class SharedBudget(unittest.TestCase):
    """E128 (2026-10-27 ~22:40 UTC): a Flash video job makes an Agnes Image 2.5 Flash still inside its conversation
    (the owner's app: "Painterly cinematic image of the Garden of Eden at dawn ... wide 16:9", shot-probe run
    40592173923), so videos spend the free-model quota E124 counted for MCP stills only. That run read back 3 clips and
    then 24 submissions in a row failed with no video. One budget now counts every generation, image and video, MCP
    and Actions, and two failed video read-backs stop generation like two failed stills."""
    token = "synthetic-offline-pavo-credential"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "image-ledger.json"
        self.t = datetime(2026, 10, 27, 22, 0, tzinfo=timezone.utc)
        self.actions = dict(NO_ACTIONS)

    def tearDown(self):
        self.tmp.cleanup()

    def guard(self, cap=None):
        return QuotaGuard(self.ledger, cap=cap, now=lambda: self.t, actions=lambda day: self.actions)

    def video(self, *responses, cap=None):
        return PavoImageClient(self.token, Responses(*responses), guard=self.guard(cap))

    def submit_video(self, cid="901", cap=None):
        return self.video(quote(), envelope({"conversation_id": cid}), started(VIDEO_MODEL),
                          cap=cap).generate_video("Mist drifts through a garden at dawn.", 8, "16:9")

    def submit_image(self, cid="777", cap=None):
        return self.video(quote(), envelope({"conversation_id": cid}), started(IMAGE_MODEL),
                          cap=cap).generate_image("A dry plain at dusk.")

    def test_a_video_spends_the_same_budget_as_a_still_and_is_refused_before_any_request(self):
        self.assertEqual(self.submit_image(cap=5)["status"], "submitted")              # 1 unit
        self.video(history([{"url": CDN}])).image_job("777")                          # E136: read back before more
        self.assertEqual(self.submit_video(cap=5)["status"], "submitted")              # 2 units
        self.assertEqual(self.submit_video("902", cap=5)["status"], "submitted")       # 2 units: 5 counted
        self.assertEqual(json.loads(self.ledger.read_text())["days"]["2026-10-27"]["generated"], 5)
        self.assertEqual((IMAGE_UNITS, VIDEO_UNITS), (1, 2))
        for make in (lambda c: c.generate_video("Mist at dawn.", 8, "16:9"), lambda c: c.generate_image("A plain.")):
            fake = Responses()                                                         # E136: two videos unread
            with self.assertRaisesRegex(PavoError, "PAVO_UNREAD_JOBS"):
                make(PavoImageClient(self.token, fake, guard=self.guard(cap=5)))
            self.assertEqual(fake.calls, [])                                           # nothing sent, not even a quote

    def test_two_failed_video_read_backs_stop_videos_and_stills(self):
        for cid in ("373600417911467520", "373600509753560128"):
            self.assertEqual(self.video(video_failed()).job(cid)["status"], "failed")
        for make in (lambda c: c.generate_video("Mist at dawn.", 8, "16:9"), lambda c: c.generate_image("A plain.")):
            fake = Responses()
            with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
                make(PavoImageClient(self.token, fake, guard=self.guard()))
            self.assertEqual(fake.calls, [])
        self.t += timedelta(hours=3, minutes=1)                                       # one probe, then it must read back
        probe = self.submit_video("903")["conversation_id"]
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            self.video().generate_image("A plain.")
        done = envelope({"is_running": False, "turns": [{"assistant": [{"type": "GenerationSuccess", "data": {"data": {
            "model_code": VIDEO_MODEL, "results": [{"url": "https://cos-aigc-default.agnes-ai.space/pavo/v/x.mp4"}]}}}]}]})
        self.assertEqual(self.video(done).job(probe)["status"], "completed")
        self.assertEqual(self.submit_image()["status"], "submitted")

    def test_todays_shot_probe_runs_count_and_their_failed_tail_stops_generation(self):
        self.actions = {"units": 119, "failed_tail": 0, "last_at": None}
        self.assertEqual(self.submit_image()["status"], "submitted")                  # counted, never a day's cap
        self.assertEqual(self.guard().check_batch(0)["used"], 120)
        self.ledger.unlink()
        self.actions = {"units": 54, "failed_tail": 24, "last_at": (self.t - timedelta(hours=1)).isoformat()}
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            self.video().generate_video("Mist at dawn.", 8, "16:9")
        self.t += timedelta(hours=2, minutes=1)                                       # the run's stop is 3 h old
        self.assertEqual(self.submit_video()["status"], "submitted")

    def test_a_batch_larger_than_one_window_is_refused_before_it_starts(self):
        # E137: what was used today no longer refuses a batch; a batch alone larger than one window does
        self.actions = {"units": 54, "failed_tail": 0, "last_at": None}
        self.ledger.write_text(json.dumps({"days": {"2026-10-27": {"generated": 140}}}))
        self.assertEqual(self.guard().check_batch(26), {"used": 194, "planned": 26, "cap": DAILY_CAP,
                                                         "remaining": DAILY_CAP - 26})
        with self.assertRaisesRegex(PavoError, "PAVO_BUDGET_SHORT planned=121 window=120"):
            self.guard().check_batch(DAILY_CAP + 1)
        self.actions = {"units": 54, "failed_tail": 2, "last_at": self.t.isoformat()}   # a stop still refuses
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            self.guard().check_batch(2)

    def test_a_probe_record_counts_every_generation_and_its_failed_tail_in_submission_order(self):
        # run 40592173923: 3 clips, then 24 failed; the record lists shots in risk order, the ids give the time
        outcomes = [("g-c1-lights", "373595250617019904", True), ("g-c1-image", "373596512523709952", True),
                    ("g-c2-command", "373597833729489600", True)]
        outcomes += [("g-c4-serpent", str(373599328776227520 + k), False) for k in range(24)]
        record = probe_record(list(reversed(outcomes)))
        self.assertEqual(record_usage(record), (27 * VIDEO_UNITS, 24))
        record = probe_record(outcomes + [("g-c4-dust", "373700000000000000", True)])
        self.assertEqual(record_usage(record), (28 * VIDEO_UNITS, 0))
        at = datetime(2026, 10, 27, 22, 41, tzinfo=timezone.utc)
        self.assertEqual(combine([(at - timedelta(hours=9), probe_record(outcomes[:3])), (at, probe_record(outcomes))]),
                         {"units": 30 * VIDEO_UNITS, "failed_tail": 24, "last_at": at.isoformat()})
        self.assertEqual(probe_record_path("claude/shot-probe-arc-01-long-40592173923"),
                         "migration/evidence/shots/arc-01-long/40592173923.json")
        self.assertIsNone(probe_record_path("claude/stills-genesis-09-short-3"))

    def test_the_local_guard_reads_todays_probe_records_from_the_origin_refs(self):
        import os
        import subprocess
        repo = Path(self.tmp.name) / "repo"
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@example.invalid", "HOME": self.tmp.name, "PATH": os.environ["PATH"],
               "GIT_CONFIG_NOSYSTEM": "1"}

        def vcs(*args, date="2026-10-27T22:41:00+00:00"):
            return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                                  env=dict(env, GIT_COMMITTER_DATE=date, GIT_AUTHOR_DATE=date)).stdout.strip()
        repo.mkdir()
        vcs("init", "-q")
        failed = [("g-c4-serpent", str(373599328776227520 + k), False) for k in range(3)]
        for run, date in (("40592173923", "2026-10-27T22:41:00+00:00"),
                          ("40400000000", "2026-10-26T10:00:00+00:00")):     # yesterday's run: not counted today
            path = repo / "migration" / "evidence" / "shots" / "arc-01-long" / f"{run}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(probe_record(failed)))
            vcs("add", "-A")
            vcs("commit", "-q", "-m", run, date=date)
            vcs("update-ref", f"refs/remotes/origin/claude/shot-probe-arc-01-long-{run}", "HEAD")
        usage = git_actions_usage("2026-10-27", repo=repo, now=datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc))
        self.assertEqual((usage["units"], usage["failed_tail"]), (3 * VIDEO_UNITS, 3))
        self.assertEqual(git_actions_usage("2026-10-25", repo=repo, now=datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)),
                         NO_ACTIONS)
        with self.assertRaisesRegex(PavoError, "PAVO_BUDGET_UNREADABLE"):
            git_actions_usage("2026-10-27", repo=Path(self.tmp.name) / "not-a-repo")


def probe_repo(root, runs):
    """A git repo whose origin/claude/shot-probe-* refs hold RUNS: [(run id, ISO commit time, record)]."""
    import os
    import subprocess
    repo = Path(root) / "repo"
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "HOME": str(root), "PATH": os.environ["PATH"],
           "GIT_CONFIG_NOSYSTEM": "1"}

    def vcs(*args, date="2026-10-27T22:41:00+00:00"):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                       env=dict(env, GIT_COMMITTER_DATE=date, GIT_AUTHOR_DATE=date))
    repo.mkdir()
    vcs("init", "-q")
    for run, date, record in runs:
        path = repo / "migration" / "evidence" / "shots" / "arc-01-long" / f"{run}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record))
        vcs("add", "-A")
        vcs("commit", "-q", "-m", run, date=date)
        vcs("update-ref", f"refs/remotes/origin/claude/shot-probe-arc-01-long-{run}", "HEAD")
    return repo


class ReviewOf475(unittest.TestCase):
    """Review of #475: a probe record with no generations (an adopt_run) after a stop hid the stop's cool-down, and
    the cool-down ended at 00:00 UTC because only the day's records were read."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def stopped(self):
        return probe_record([("g-c4-serpent", str(373599328776227520 + k), False) for k in range(3)])

    def test_an_adopt_run_after_a_stop_does_not_hide_it(self):
        stop = datetime(2026, 10, 27, 22, 41, tzinfo=timezone.utc)
        adopted = {"episode": "arc-01-long", "shots": {"s-a": {"clips": [{"round": 1, "asset": "shot-x.mp4"}]}}}
        usage = combine([(stop, self.stopped()), (stop + timedelta(minutes=20), adopted)], "2026-10-27")
        self.assertEqual(usage, {"units": 3 * VIDEO_UNITS, "failed_tail": 3, "last_at": stop.isoformat()})
        self.assertEqual(combine([(stop, adopted)]), {"units": 0, "failed_tail": 0, "last_at": None})
        guard = QuotaGuard(Path(self.tmp.name) / "l.json", now=lambda: stop + timedelta(minutes=30),
                           actions=lambda day: usage)
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            guard.before_generate(VIDEO_UNITS)

    def test_a_stop_just_before_midnight_holds_after_it(self):
        repo = probe_repo(self.tmp.name, [("40592173923", "2026-10-27T23:30:00+00:00", self.stopped())])
        after = datetime(2026, 10, 28, 0, 30, tzinfo=timezone.utc)
        usage = git_actions_usage("2026-10-28", repo=repo, now=after)
        self.assertEqual((usage["units"], usage["failed_tail"]), (0, 3))   # yesterday's units, today's stop
        guard = QuotaGuard(Path(self.tmp.name) / "l.json", now=lambda: after, actions=lambda day: usage)
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            guard.before_generate(VIDEO_UNITS)
        later = after + timedelta(hours=2, minutes=1)                         # 3 h after the stop: over
        self.assertEqual(git_actions_usage("2026-10-28", repo=repo, now=later), NO_ACTIONS)


if __name__ == "__main__":
    unittest.main()
