#!/usr/bin/env python3
"""episode_build.py offline (stubbed Pavo client and voice): shot -> Pavo request, a failed shot regenerated at most
twice, an uncertain submission only read back, and the compose timeline keeps the Keeper's picture on his line."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "migration" / "integrations" / "pavo"))
import episode_build as eb  # noqa: E402
import short_engine  # noqa: E402
from client import PavoError  # noqa: E402

EXAMPLE = json.loads((HERE / "plans" / "genesis-07-short.json").read_text())
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def layout_for(plan, durations):
    lines = [{"start": a, "end": b} for a, b in eb.line_layout(durations)]
    total = round(lines[-1]["end"] + eb.TAIL, 3)
    keeper = {}
    for s in plan["shots"]:
        if s["kind"] == "keeper":
            a, b = lines[s["lines"][0]]["start"], lines[s["lines"][-1]]["end"]
            keeper[s["id"]] = {"wav": f".episode/x/keeper/{s['id']}.wav", "start": a, "end": b,
                               "seconds": round(b - a, 3)}
    return {"lines": lines, "total": total, "keeper": keeper}


DURATIONS = [2.6, 6.79, 9.47, 9.08, 5.55, 5.58, 4.91, 6.22, 3.2, 8.47, 6.33]   # Kokoro, measured 2026-10-26


class Requests(unittest.TestCase):
    def test_voice_is_the_pinned_engine_voice_one_segment_a_line(self):
        v = eb.voice_script(EXAMPLE)
        self.assertEqual(v["voice"], {"voice_id": "am_michael", "speed": 1.0})
        self.assertEqual([s["id"] for s in v["segments"]], [f"n{k:02d}" for k in range(len(EXAMPLE["narration"]))])
        self.assertEqual(v["segments"][2]["text"], EXAMPLE["narration"][2]["text"])

    def test_shot_to_generation_request(self):
        layout = layout_for(EXAMPLE, DURATIONS)
        refs = {"keeper": [".episode/x/refs/ch-keeper-front.jpg"], "eve": [".episode/x/refs/ch-eve-full.jpg"]}
        shots = EXAMPLE["shots"]
        k = eb.request(shots[0], 0, EXAMPLE, layout, refs)
        self.assertEqual(k["references"], refs["keeper"])
        self.assertEqual(k["audios"], [".episode/x/keeper/k-open.wav"])
        self.assertEqual(k["seconds"], 4)                      # 2.6 s line: Flash's minimum of 4 s
        self.assertFalse(k["sound"])
        self.assertEqual(k["prompt"], shots[0]["prompt"])
        last = eb.request(shots[-1], len(shots) - 1, EXAMPLE, layout, refs)
        self.assertEqual(last["seconds"], 9)                   # 6.33 s line + 1.2 s tail + 0.6 s margin
        s = eb.request(shots[1], 1, EXAMPLE, layout, refs)
        self.assertEqual((s["seconds"], s["references"], s["audios"]), (6, None, None))
        acted = dict(shots[3], characters=["eve"])
        self.assertEqual(eb.request(acted, 3, EXAMPLE, layout, refs)["references"], refs["eve"])
        for i, shot in enumerate(shots):
            r = eb.request(shot, i, EXAMPLE, layout, refs)
            self.assertTrue(4 <= r["seconds"] <= 12 and type(r["seconds"]) is int, shot["id"])


class FakeClient:
    def __init__(self, submissions, jobs=None):
        self.submissions, self.jobs, self.calls, self.reads = list(submissions), dict(jobs or {}), [], []

    def generate_video(self, **req):
        self.calls.append(req)
        item = self.submissions.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def job(self, cid):
        self.reads.append(cid)
        item = self.jobs[cid].pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def done(cid, n=1):
    return {"conversation_id": cid, "status": "completed", "videos": [{"url": f"https://cdn/{cid}-{n}.mp4"}]}


class Generation(unittest.TestCase):
    def test_a_failed_shot_is_regenerated_at_most_twice_then_the_run_names_it(self):
        made = []

        def attempt(n):
            made.append(n)
            return {"generation": n}, f"clip-{n}.mp4"
        with self.assertRaises(eb.ShotFailed) as err:
            eb.make_shot("k-open", attempt, lambda p: (["MOUTH_NOT_IN_SYNC"], {"audio": {}}))
        self.assertEqual(made, [1, 2, 3])
        self.assertIn("SHOT_FAILED k-open after 3 generations", str(err.exception))

    def test_the_first_clean_generation_is_kept(self):
        flags = {"clip-1.mp4": ["BLACK_START"], "clip-2.mp4": []}
        path, records = eb.make_shot("s-a", lambda n: ({"generation": n}, f"clip-{n}.mp4"), lambda p: (flags[p], None))
        self.assertEqual(path, "clip-2.mp4")
        self.assertEqual([r["flags"] for r in records], [["BLACK_START"], []])

    def test_a_generation_with_no_video_counts_as_a_failed_attempt(self):
        with self.assertRaises(eb.ShotFailed):
            eb.make_shot("s-a", lambda n: ({"generation": n}, None), lambda p: ([], None))

    def test_rate_limit_is_waited_out_without_a_new_attempt_other_refusals_stop(self):
        waits = []
        ok = {"conversation_id": "1", "status": "submitted"}
        c = FakeClient([PavoError("PAVO_RATE_LIMITED"), PavoError("PAVO_RATE_LIMITED"), ok])
        self.assertEqual(eb.submit(c, {"prompt": "x"}, sleep=waits.append, log=lambda *_: None), ok)
        self.assertEqual(waits, list(eb.RATE_LIMIT_WAITS[:2]))
        c = FakeClient([PavoError("PAVO_ZERO_CREDIT_QUOTE_REQUIRED required_credits=4 final_points=4 is_estimate=false")])
        with self.assertRaises(eb.ShotFailed) as err:
            eb.submit(c, {"prompt": "x"}, sleep=waits.append)
        self.assertIn("PAVO_ZERO_CREDIT_QUOTE_REQUIRED", str(err.exception))
        self.assertEqual(len(c.calls), 1)

    def test_an_uncertain_submission_is_read_back_never_resubmitted(self):
        c = FakeClient([{"conversation_id": "7", "status": "unknown"}],
                       {"7": [PavoError("PAVO_UNREACHABLE"), {"status": "incomplete"}, {"status": "running"},
                              done("7")]})
        result = eb.submit(c, {"prompt": "x"}, sleep=lambda s: None)
        video = eb.wait_job(c, result["conversation_id"], sleep=lambda s: None)
        self.assertEqual(video["url"], "https://cdn/7-1.mp4")
        self.assertEqual(len(c.calls), 1)
        self.assertEqual(c.reads, ["7"] * 4)

    def test_a_job_that_stays_incomplete_or_fails_gives_no_video(self):
        c = FakeClient([], {"8": [{"status": "incomplete"}] * eb.INCOMPLETE_POLLS, "9": [{"status": "failed"}]})
        self.assertIsNone(eb.wait_job(c, "8", sleep=lambda s: None))
        self.assertIsNone(eb.wait_job(c, "9", sleep=lambda s: None))
        c = FakeClient([], {"5": [PavoError("PAVO_MEDIA_URL_REFUSED")]})
        with self.assertRaises(eb.ShotFailed):
            eb.wait_job(c, "5", sleep=lambda s: None)


class Compose(unittest.TestCase):
    def test_keeper_picture_spans_equal_their_line_audio_and_scenes_cut_every_2_to_4_s(self):
        layout = layout_for(EXAMPLE, DURATIONS)
        clips = {s["id"]: f"{s['id']}.mp4" for s in EXAMPLE["shots"]}
        seconds = {s["id"]: (s.get("seconds") or 12) + 0.59 for s in EXAMPLE["shots"]}
        shots = eb.compose_shots(EXAMPLE, layout, clips, seconds)
        self.assertEqual(short_engine.check_shots(shots, layout["total"]), [])
        keepers = [c for c in shots if c["kind"] == "keeper"]
        self.assertEqual([c["shot"] for c in keepers], ["k-open", "k-insight", "k-close"])
        for c in keepers:
            line = layout["keeper"][c["shot"]]
            self.assertAlmostEqual(c["start"], line["start"], places=3)
            # k-insight is followed by the Keeper again: he holds the 0.35 s gap before his next line
            end = {"k-close": layout["total"], "k-insight": layout["keeper"]["k-close"]["start"]}.get(c["shot"], line["end"])
            self.assertAlmostEqual(c["end"], end, places=3)
            self.assertEqual((c["src_start"], c["speed"]), (0.0, 1.0))   # never slowed: lips stay on the voice
        self.assertEqual(shots[0]["start"], 0.0)
        for c in shots:
            if c["kind"] == "scene":
                self.assertLessEqual(c["end"] - c["start"], eb.CUT_MAX + 1e-3, c)
                self.assertGreaterEqual(c["end"] - c["start"], 1.0, c)
                self.assertIsNotNone(short_engine.explicit_speed(c, seconds[c["shot"]]), c)
        est = {s["id"] for s in EXAMPLE["shots"] if s.get("establishing")}
        for sid in est:
            self.assertLessEqual(sum(c["end"] - c["start"] for c in shots if c["shot"] == sid), 2.0 + 1e-3)

    def test_a_long_clip_is_cut_into_windows_a_short_one_slowed_at_most_1_3(self):
        spread = eb.cuts("a.mp4", 10.0, 17.0, 8.59)
        self.assertEqual(len(spread), 2)
        self.assertEqual([c["speed"] for c in spread], [1.0, 1.0])
        self.assertLessEqual(spread[-1]["src_start"] + 3.5, 8.59 + 1e-6)
        slow = eb.cuts("b.mp4", 0.0, 7.5, 6.59)
        self.assertGreater(slow[0]["speed"], 1.0)
        self.assertLessEqual(slow[0]["speed"], eb.MAX_SLOW)
        with self.assertRaises(SystemExit):
            eb.cuts("c.mp4", 0.0, 12.0, 6.59)

    def test_short_engine_honours_a_planned_speed_only_within_bounds(self):
        self.assertEqual(short_engine.explicit_speed({"start": 0, "end": 3, "src_start": 0, "speed": 1.0}, 6.59), 1.0)
        self.assertIsNone(short_engine.explicit_speed({"start": 0, "end": 3, "src_start": 5, "speed": 1.0}, 6.59))
        self.assertIsNone(short_engine.explicit_speed({"start": 0, "end": 3, "src_start": 0, "speed": 1.5}, 6.59))

    def test_a_keeper_clip_shorter_than_his_line_is_refused(self):
        layout = layout_for(EXAMPLE, DURATIONS)
        clips = {s["id"]: "x.mp4" for s in EXAMPLE["shots"]}
        seconds = {s["id"]: 12.59 for s in EXAMPLE["shots"]}
        seconds["k-insight"] = 6.0
        with self.assertRaises(SystemExit) as err:
            eb.compose_shots(EXAMPLE, layout, clips, seconds)
        self.assertIn("KEEPER_CLIP_SHORT k-insight", str(err.exception))


def tone_wav(path, seconds, rate=24000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", 3000 if (i // 40) % 2 else -3000) for i in range(int(seconds * rate))))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
class Lines(unittest.TestCase):
    def test_the_narration_track_is_rebuilt_from_the_line_wavs_and_the_keeper_gets_his_line(self):
        plan = {"shots": [{"id": "k-open", "kind": "keeper", "lines": [0]}, {"id": "s-a", "kind": "scene", "lines": [1]},
                          {"id": "k-close", "kind": "keeper", "lines": [2]}],
                "narration": [{"text": "a"}, {"text": "b"}, {"text": "c"}]}
        work = Path(tempfile.mkdtemp(dir=eb.REPO / ".episode" if (eb.REPO / ".episode").is_dir() else eb.REPO,
                                     prefix="test-lines-"))
        try:
            # pilot_render's voice.wav: 0.3 s lead-in, sentences 0.18 s apart (line 1 has two sentences)
            tone_wav(work / "voice.wav", 70.0)
            sentences = [{"segment": "n00", "text": "a.", "start": 0.3, "end": 3.3},
                         {"segment": "n01", "text": "b.", "start": 3.48, "end": 30.0},
                         {"segment": "n01", "text": "b2.", "start": 30.18, "end": 60.0},
                         {"segment": "n02", "text": "c.", "start": 60.18, "end": 66.18}]
            (work / "timeline.json").write_text(json.dumps({"sentences": sentences}))
            result = eb.lines_step(plan, work)
            starts = [x["start"] for x in result["lines"]]
            self.assertEqual(starts[0], 0.0)                       # the hook starts at 0 s
            self.assertAlmostEqual(starts[1], 3.0 + eb.LINE_GAP, places=2)
            k = result["keeper"]["k-close"]
            self.assertAlmostEqual(k["seconds"], 6.0, places=2)
            self.assertAlmostEqual(result["keeper_share"], 9.0 / result["total"], places=2)
            info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels", "-of",
                                   "json", str(eb.REPO / k["wav"])], capture_output=True, text=True).stdout
            stream = json.loads(info)["streams"][0]
            self.assertEqual((stream["sample_rate"], stream["channels"]), ("44100", 1))
            timeline = json.loads((work / "compose-timeline.json").read_text())
            self.assertAlmostEqual(timeline["sentences"][-1]["start"], k["start"], places=2)
            self.assertAlmostEqual(timeline["voice_seconds"], k["end"], places=2)
            # measured again after the voice: a Keeper over 25 % of the Short stops the run
            sentences[0]["end"] = 12.3
            sentences[1].update(start=12.48, end=25.0)
            sentences[2].update(start=25.18, end=40.0)
            sentences[3].update(start=40.18, end=50.38)
            (work / "timeline.json").write_text(json.dumps({"sentences": sentences}))
            with self.assertRaises(SystemExit) as err:
                eb.lines_step(plan, work)
            self.assertIn("KEEPER_SHARE", str(err.exception))
        finally:
            shutil.rmtree(work)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
class Refs(unittest.TestCase):
    def test_references_are_hash_checked_and_resized(self):
        work = Path(tempfile.mkdtemp(dir=eb.REPO, prefix=".test-refs-"))
        try:
            img = work / "src.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=2048x2048", "-frames:v",
                            "1", str(img)], check=True)
            digest = hashlib.sha256(img.read_bytes()).hexdigest()
            recs = work / "images"
            recs.mkdir()
            (recs / "ch-eve-full.json").write_text(json.dumps({"release_asset": "characters-img-ch-eve-full.png",
                                                               "sha256": digest}))
            chars = {"eve": {"status": "APPROVED", "refs": ["full"]}}
            plan = {"shots": [{"kind": "scene", "characters": ["eve"]}]}
            orig = eb.reference_records
            eb.reference_records = lambda cid, chars=None: orig(cid, chars, recs)
            try:
                out = eb.refs_step(plan, work, fetch=lambda name, dst: shutil.copyfile(img, dst), chars=chars)
                size = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                                       str(eb.REPO / out["eve"][0])], capture_output=True, text=True).stdout.strip()
                self.assertEqual(size, "1536,1536")
                with self.assertRaises(SystemExit) as err:
                    eb.refs_step(plan, work, fetch=lambda name, dst: Path(dst).write_bytes(b"other"), chars=chars)
                self.assertIn("REFERENCE_SHA256_MISMATCH", str(err.exception))
                with self.assertRaises(SystemExit):
                    eb.refs_step(plan, work, fetch=None, chars={"eve": {"status": "DRAFT", "refs": ["full"]}})
            finally:
                eb.reference_records = orig
        finally:
            shutil.rmtree(work)

    def test_the_keeper_reference_is_the_repository_frame(self):
        recs = eb.reference_records("keeper")
        self.assertTrue(all(m.get("repo_path") or m.get("release_asset") for _, m in recs))


class Workflow(unittest.TestCase):
    """episode.yml holds PAVO_TOKEN: manual runs of main only, the secret in one step, inputs only through env."""
    def test_the_secret_stays_in_one_step_of_a_main_only_manual_run(self):
        import re
        text = (eb.REPO / ".github" / "workflows" / "episode.yml").read_text()
        jobs = text.split("\n  record:\n")
        build, record = jobs[0], jobs[1]
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", build)
        self.assertEqual(text.count("secrets."), 1)
        self.assertNotIn("secrets.", record)
        step = [s for s in build.split("\n      - ") if "secrets.PAVO_TOKEN" in s][0]
        self.assertIn("episode_build.py generate", step)
        self.assertIn("persist-credentials: false", build)
        for line in text.splitlines():
            if "uses:" in line:
                self.assertRegex(line, r"@[0-9a-f]{40}$", line)
        for block in re.findall(r"run: \|\n((?:          .*\n?)+)", text):
            self.assertNotIn("${{", block)
        self.assertIn("contents: read", build)
        self.assertNotIn("contents: write", build)
        rx = re.search(r'\[\[ "\$PLAN" =~ (\S+) \]\]', text).group(1)
        self.assertTrue(re.fullmatch(rx, "migration/production/bible/plans/genesis-07-short.json"))
        for bad in ("migration/production/bible/plans/../x.json", "migration/production/bible/plans/a;b.json",
                    "migration/production/bible/plans/a b.json"):
            self.assertIsNone(re.fullmatch(rx, bad), bad)


if __name__ == "__main__":
    unittest.main()
