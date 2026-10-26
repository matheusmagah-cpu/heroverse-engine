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
    """layout.json as lines_step writes it, from measured line durations (stub: no voice, no ffmpeg)."""
    lines = [{"start": a, "end": b} for a, b in eb.line_layout(durations)]
    total = round(lines[-1]["end"] + eb.TAIL, 3)
    _, carried = eb.plan_check.sequence(plan)
    keeper, speakers, voice_over = {}, {}, {}
    for i, s in enumerate(plan["shots"]):
        if s["kind"] != "keeper" and not eb.plan_check.speaking(s):
            continue
        a, b = lines[carried[i][0]]["start"], lines[carried[i][-1]]["end"]
        rec = {"start": a, "end": b, "seconds": round(b - a, 3)}
        if s["kind"] == "keeper":
            keeper[s["id"]] = dict(rec, wav=f".episode/x/keeper/{s['id']}.wav")
        elif eb.plan_check.talking(s):
            speakers[s["id"]] = dict(rec, wav=f".episode/x/speakers/{s['id']}.wav", speaker=s["speaker"])
        else:
            voice_over[s["id"]] = dict(rec, speaker=s["speaker"])
    return {"lines": lines, "total": total, "keeper": keeper, "speakers": speakers, "voice_over": voice_over}


# Kokoro, measured locally 2026-10-26 on the Genesis 7 v2 plan, the talking lines after the E95 retime
DURATIONS = [6.69, 9.49, 8.99, 9.47, 9.04, 9.34, 4.91, 9.85, 5.5, 9.55, 7.37, 6.13, 8.4, 4.4, 8.34, 3.07, 7.65, 3.2,
             5.23, 3.67, 5.18, 8.42, 4.54, 6.54]   # 174.184 s
EVE = "a woman of about twenty-five with long black hair"
STUB_CHARS = {"eve": {"status": "APPROVED", "look": EVE, "refs": ["full"], "voice": "af_heart"},
              "keeper": {"status": "APPROVED", "look": "x", "refs": ["front"], "voice": "am_michael"}}


def dialogue_plan():
    """Eve challenges at 0 s (her own voice, lip-synced), narration over a scene, God's voice-over, the Keeper closes."""
    style = "Painterly cinematic realism, cinema camera."
    return {"episode": "t", "part": 0, "narration": [{"kind": "story", "text": "a b c"},
                                                     {"kind": "cta", "text": "the full story"}],
            "shots": [{"id": "s-eve", "kind": "scene", "speaker": "eve", "line": "Why do you hide?",
                       "characters": ["eve"], "prompt": f"{style} Close-up, static. Eve, {EVE}, speaks."},
                      {"id": "s-a", "kind": "scene", "lines": [0], "seconds": 6, "characters": [],
                       "figures": "anonymous", "prompt": "p"},
                      {"id": "s-god", "kind": "scene", "speaker": "god", "line": "I will destroy man.",
                       "reference": "Genesis 6:7 (KJV)", "seconds": 8, "characters": [], "prompt": "storm"},
                      {"id": "k-close", "kind": "keeper", "lines": [1], "prompt": "k"}]}


class Requests(unittest.TestCase):
    def test_voice_is_one_segment_a_line_each_spoken_line_in_its_speakers_own_voice(self):
        v = eb.voice_script(EXAMPLE)
        self.assertEqual(v["voice"], {"voice_id": "am_michael", "speed": 1.0})
        items, _ = eb.plan_check.sequence(EXAMPLE)
        self.assertEqual([s["id"] for s in v["segments"]], [f"n{k:02d}" for k in range(len(items))])
        self.assertEqual(len(items), len(EXAMPLE["narration"]) + 3)          # three lines of God's voice
        god = v["segments"][0]
        self.assertEqual((god["voice_id"], god["speed"], god["speaker"]), ("am_onyx", 0.9, "god"))
        self.assertEqual(god["text"], EXAMPLE["shots"][0]["line"])
        self.assertEqual(v["segments"][1]["text"], EXAMPLE["narration"][0]["text"])
        self.assertNotIn("voice_id", v["segments"][1])                     # the narration: the Keeper's voice
        d = eb.voice_script(dialogue_plan(), STUB_CHARS)["segments"]
        self.assertEqual([(s.get("speaker"), s.get("voice_id")) for s in d],
                         [("eve", "af_heart"), (None, None), ("god", "am_onyx"), (None, None)])
        with self.assertRaises(SystemExit):
            eb.voice_script(dialogue_plan(), {"eve": dict(STUB_CHARS["eve"], voice=None)})

    def test_shot_to_generation_request(self):
        layout = layout_for(EXAMPLE, DURATIONS)
        refs = {"keeper": [".episode/x/refs/ch-keeper-front.jpg"], "keeper:talk": [".episode/x/refs/ch-keeper-talk.jpg"],
                "eve": [".episode/x/refs/ch-eve-full.jpg"]}
        shots = EXAMPLE["shots"]
        g = eb.request(shots[0], 0, EXAMPLE, layout, refs)         # God's voice-over: a scene, no audio, no one shown
        self.assertEqual((g["seconds"], g["references"], g["audios"]), (8, None, None))
        self.assertEqual(g["prompt"], shots[0]["prompt"])          # scenes keep the plan's prompt (resume, E93)
        ki = [i for i, s in enumerate(shots) if s["id"] == "k-insight"][0]
        k = eb.request(shots[ki], ki, EXAMPLE, layout, refs)
        self.assertEqual(k["references"], refs["keeper:talk"])     # E95: his speaking frame, not the closed mouth
        self.assertEqual(k["audios"], [".episode/x/keeper/k-insight.wav"])
        self.assertEqual(k["seconds"], 9)                      # ceil(8.47 s): 0.53 s of clip past the words (E95)
        self.assertFalse(k["sound"])
        self.assertTrue(k["prompt"].startswith("Image 1 is the narrator. "))
        self.assertIn("speaks the words of the audio clip, his lips moving in sync with the voice", k["prompt"])
        self.assertNotIn("lips moving clearly with every word", k["prompt"])
        last = eb.request(shots[-1], len(shots) - 1, EXAMPLE, layout, refs)
        self.assertEqual(last["seconds"], 7)                   # 6.55 s retimed line; the tail is a held frame
        s = eb.request(shots[1], 1, EXAMPLE, layout, refs)
        self.assertEqual((s["seconds"], s["references"], s["audios"]), (6, None, None))
        acted = dict(shots[3], characters=["eve"])
        self.assertEqual(eb.request(acted, 3, EXAMPLE, layout, refs)["references"], refs["eve"])
        for i, shot in enumerate(shots):
            r = eb.request(shot, i, EXAMPLE, layout, refs)
            self.assertTrue(4 <= r["seconds"] <= 12 and type(r["seconds"]) is int, shot["id"])

    def test_a_speaking_character_sends_its_own_line_and_references_and_is_lipsync_checked(self):
        p = dialogue_plan()
        layout = layout_for(p, [3.55, 3.0, 2.5, 4.55])
        refs = {"keeper": ["k.jpg"], "keeper:talk": ["k-talk.jpg"], "eve": ["eve.jpg"]}
        r = eb.request(p["shots"][0], 0, p, layout, refs)
        self.assertEqual((r["references"], r["audios"], r["seconds"]), (["eve.jpg"], [".episode/x/speakers/s-eve.wav"],
                                                                        4))   # no `talk` frame: her kept reference
        self.assertTrue(r["prompt"].startswith("Image 1 is Eve. "))
        self.assertTrue(r["prompt"].endswith("She speaks the words of the audio clip, her lips moving in sync with the "
                                             "voice."))
        self.assertIsNone(eb.request(p["shots"][2], 2, p, layout, refs)["audios"])
        self.assertEqual(eb.request(p["shots"][3], 3, p, layout, refs)["references"], ["k-talk.jpg"])
        self.assertEqual(eb.talk_record(layout, p["shots"][0])["speaker"], "eve")
        # which clips go through lipsync_check: the talking ones (Eve, the Keeper), never God's voice-over or a scene
        self.assertEqual([eb.plan_check.talking(s) for s in p["shots"]], [True, False, False, True])


    def test_every_talking_request_binds_image_1_and_the_audio_clip(self):
        """E95: Pavo kept our line in the lips only with "Image 1 is the narrator" and "speaks the words of the audio
        clip, his lips moving in sync with the voice" (plan prompt unchanged: audio 0.105 at 7 s)."""
        layout = layout_for(EXAMPLE, DURATIONS)
        refs = {"keeper": ["k.jpg"], "keeper:talk": ["k-talk.jpg"]}
        talking = [(i, s) for i, s in enumerate(EXAMPLE["shots"]) if eb.plan_check.talking(s)]
        self.assertEqual([s["id"] for _, s in talking], ["k-insight", "k-question", "k-close"])
        for i, s in talking:
            r = eb.request(s, i, EXAMPLE, layout, refs)
            self.assertIn("Image 1 is the narrator", r["prompt"], s["id"])
            self.assertEqual(r["prompt"].count("speaks the words of the audio clip, his lips moving in sync with the "
                                               "voice"), 1, s["id"])
            self.assertEqual(r["references"][0], "k-talk.jpg", s["id"])
            speech = layout["keeper"][s["id"]]["seconds"]
            self.assertTrue(0.25 - 1e-6 <= r["seconds"] - speech <= 0.65 + 1e-6, (s["id"], speech, r["seconds"]))
        bound = eb.bind_prompt(eb.bind_prompt("A wide shot. He walks.", "keeper"), "keeper")   # idempotent
        self.assertEqual(bound, "Image 1 is the narrator. A wide shot. He walks. He speaks the words of the audio clip, "
                                "his lips moving in sync with the voice.")


class Prediction(unittest.TestCase):
    def test_the_prediction_is_the_build_on_the_same_lengths(self):
        # E106: plan_check and preflight predict with the build's own functions: on the measured Genesis 7 lengths
        # the predicted layout is the one lines_step lays out and the compose takes it with no refusal
        problems, layout = eb.predict(EXAMPLE, DURATIONS)
        self.assertEqual(problems, [])
        stretches, _ = eb.retime_plan(EXAMPLE, DURATIONS)
        retimed = list(DURATIONS)
        for idx, _, stretch in stretches.values():
            for k in idx:
                retimed[k] *= stretch
        self.assertEqual(layout["lines"], [{"start": a, "end": b} for a, b in eb.line_layout(retimed)])
        self.assertTrue(170 <= layout["total"] <= 179)
        # a Keeper line no clip reaches is the build's TALK_LINE_RETIME_OVER, predicted before any voice
        short = list(DURATIONS)
        _, carried = eb.plan_check.sequence(EXAMPLE)
        close = [i for i, s in enumerate(EXAMPLE["shots"]) if s["id"] == "k-close"][0]
        short[carried[close][0]] = 4.0
        self.assertEqual([p.split()[0] for p in eb.predict(EXAMPLE, short)[0]], ["TALK_LINE_RETIME_OVER"])


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

    def test_a_talking_shot_gets_six_generations_a_scene_three(self):
        # E98: genesis-07 run 40297987571 refused k-insight 3 times on the lips check; measured, a talking clip passes
        # it about 4 times in 10, so 3 generations failed half the runs with three Keeper shots
        talk = {"id": "k-a", "kind": "keeper", "lines": [0]}
        scene = {"id": "s-a", "kind": "scene", "lines": [1]}
        self.assertEqual(eb.attempts_for(talk), eb.TALK_ATTEMPTS)
        self.assertEqual(eb.attempts_for(scene), eb.ATTEMPTS)
        self.assertGreaterEqual(eb.TALK_ATTEMPTS, 6)
        n = []
        with self.assertRaises(eb.ShotFailed):
            eb.make_shot("k-a", lambda i: (n.append(i) or {"generation": i}, None), lambda p: ([], None),
                         attempts=eb.attempts_for(talk))
        self.assertEqual(len(n), eb.TALK_ATTEMPTS)
        # generate_step itself giving a talking shot TALK_ATTEMPTS generations: the E94 failed-shot test (s-eve)

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

    def test_pavo_unreachable_before_any_job_is_waited_out_then_the_run_stops(self):
        # E93: generate_video raises PAVO_UNREACHABLE only before a generation starts, so it is sent again
        waits = []
        ok = {"conversation_id": "1", "status": "submitted"}
        c = FakeClient([PavoError("PAVO_UNREACHABLE"), PavoError("PAVO_RATE_LIMITED"), PavoError("PAVO_UNREACHABLE"), ok])
        self.assertEqual(eb.submit(c, {"prompt": "x"}, sleep=waits.append, log=lambda *_: None), ok)
        self.assertEqual(waits, [eb.OUTAGE_WAITS[0], eb.RATE_LIMIT_WAITS[0], eb.OUTAGE_WAITS[1]])
        c = FakeClient([PavoError("PAVO_UNREACHABLE")] * (len(eb.OUTAGE_WAITS) + 1))
        with self.assertRaises(eb.ShotFailed) as err:
            eb.submit(c, {"prompt": "x"}, sleep=lambda s: None, log=lambda *_: None)
        self.assertIn("PAVO_REFUSED PAVO_UNREACHABLE", str(err.exception))
        self.assertEqual(len(c.calls), len(eb.OUTAGE_WAITS) + 1)
        self.assertGreaterEqual(sum(eb.OUTAGE_WAITS), 30 * 60)

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
        self.assertEqual([c["shot"] for c in keepers], ["k-insight", "k-question", "k-close"])
        for c in keepers:
            line = layout["keeper"][c["shot"]]
            self.assertAlmostEqual(c["start"], line["start"], places=3)
            # followed by the Keeper again: he holds the 0.35 s gap before his next line
            end = {"k-close": layout["total"], "k-insight": layout["keeper"]["k-question"]["start"],
                   "k-question": layout["keeper"]["k-close"]["start"]}[c["shot"]]
            self.assertAlmostEqual(c["end"], end, places=3)
            self.assertEqual((c["src_start"], c["speed"]), (0.0, 1.0))   # never slowed: lips stay on the voice
            self.assertEqual(c["talk"], {"start": line["start"], "end": line["end"]})
        self.assertEqual(shots[0]["start"], 0.0)
        self.assertEqual(shots[0]["shot"], "s-voice")            # God's voice over the storm opens, cut as a scene
        sentences = [{"start": x["start"], "end": x["end"]} for x in layout["lines"]]
        self.assertEqual(short_engine.talk_problems(shots, sentences), [])
        for c in shots:
            if c["kind"] == "scene":
                self.assertLessEqual(c["end"] - c["start"], eb.CUT_MAX + 1e-3, c)
                self.assertGreaterEqual(c["end"] - c["start"], 1.0, c)
                self.assertIsNotNone(short_engine.explicit_speed(c, seconds[c["shot"]]), c)
        est = {s["id"] for s in EXAMPLE["shots"] if s.get("establishing")}
        for sid in est:
            self.assertLessEqual(sum(c["end"] - c["start"] for c in shots if c["shot"] == sid), 2.0 + 1e-3)

    def test_a_dialogue_clip_keeps_its_own_line_aligned(self):
        p = dialogue_plan()
        layout = layout_for(p, [2.4, 3.0, 2.5, 3.1])
        clips = {s["id"]: f"{s['id']}.mp4" for s in p["shots"]}
        seconds = {"s-eve": 4.59, "s-a": 6.59, "s-god": 8.59, "k-close": 5.59}
        shots = eb.compose_shots(p, layout, clips, seconds)
        self.assertEqual(short_engine.check_shots(shots, layout["total"]), [])
        eve = shots[0]
        self.assertEqual((eve["shot"], eve["kind"], eve["start"], eve["src_start"], eve["speed"]),
                         ("s-eve", "speaker", 0.0, 0.0, 1.0))
        self.assertEqual(eve["talk"], {"start": 0.0, "end": 2.4})
        self.assertEqual(eve["end"], 2.4)                 # her last word; the next scene covers the 0.35 s gap
        self.assertEqual(shots[1]["start"], 2.4)
        self.assertEqual([c["kind"] for c in shots if c["shot"] == "s-god"], ["scene"] * 1)   # voice-over: a scene
        self.assertNotIn("talk", [k for c in shots if c["shot"] == "s-god" for k in c])
        sentences = [{"start": x["start"], "end": x["end"]} for x in layout["lines"]]
        self.assertEqual(short_engine.talk_problems(shots, sentences), [])
        # the composer refuses a talking clip moved off its line, slowed, started later in the clip or off the voice
        for change, code in (({"start": 0.2}, "TALK_NOT_ALIGNED"), ({"speed": 1.1}, "TALK_NOT_ALIGNED"),
                             ({"src_start": 0.5}, "TALK_NOT_ALIGNED"), ({"end": 2.0}, "TALK_NOT_ALIGNED"),
                             ({"talk": {"start": 0.0, "end": 1.7}}, "TALK_NOT_ON_THE_VOICE")):
            moved = [dict(shots[0], **change)] + shots[1:]
            self.assertIn(f"{code} 0", short_engine.talk_problems(moved, sentences), change)
        # a speaker's clip shorter than its line is refused, like the Keeper's
        with self.assertRaises(SystemExit) as err:
            eb.compose_shots(p, layout, clips, dict(seconds, **{"s-eve": 2.0}))
        self.assertIn("SPEAKER_CLIP_SHORT s-eve", str(err.exception))
        # a scene before a talking shot: the talking shot must start on its line
        q = dialogue_plan()
        q["shots"][0], q["shots"][1] = q["shots"][1], q["shots"][0]
        q["narration"][0]["text"] = "a b c"
        lay = layout_for(q, [3.0, 2.4, 2.5, 3.1])
        out = eb.compose_shots(q, lay, clips, seconds)
        talk = [c for c in out if c["shot"] == "s-eve"][0]
        self.assertAlmostEqual(talk["start"], lay["lines"][1]["start"], places=3)

    def test_a_talking_clip_covers_its_speech_and_holds_its_last_frame_for_the_gap_or_tail(self):
        """E95: a talking clip is only ~0.45 s longer than its speech; the closing tail beyond it is the last frame
        held (<= 1.3 s, the fade-out covers it); a gap the clip already covers needs no hold."""
        layout = layout_for(EXAMPLE, DURATIONS)
        clips = {s["id"]: f"{s['id']}.mp4" for s in EXAMPLE["shots"]}
        seconds = {s["id"]: (s.get("seconds") or 12) + 0.59 for s in EXAMPLE["shots"]}
        for sid in ("k-insight", "k-question", "k-close"):     # the clip lengths Pavo returns: ceil(speech)
            seconds[sid] = float(eb.talk_need(layout["keeper"][sid]["seconds"]))
        shots = eb.compose_shots(EXAMPLE, layout, clips, seconds)
        self.assertEqual(short_engine.check_shots(shots, layout["total"]), [])
        by = {c["shot"]: c for c in shots if c["kind"] == "keeper"}
        self.assertNotIn("hold", by["k-insight"])               # 9 s clip for 8.47 s + the 0.35 s gap
        self.assertNotIn("hold", by["k-question"])              # 5 s for 4.55 s + 0.35 s
        close = by["k-close"]
        self.assertAlmostEqual(close["hold"], (close["end"] - close["start"]) - seconds["k-close"] + 0.01, places=3)
        self.assertLessEqual(close["hold"], short_engine.HOLD_MAX)
        self.assertIsNotNone(short_engine.explicit_speed(close, seconds["k-close"]))
        self.assertIn("tpad=stop_mode=clone:stop_duration=", short_engine.hold_filter(close))
        self.assertEqual(short_engine.hold_filter(by["k-insight"]), "")
        sentences = [{"start": x["start"], "end": x["end"]} for x in layout["lines"]]
        self.assertEqual(short_engine.talk_problems(shots, sentences), [])
        self.assertIsNone(short_engine.explicit_speed(dict(close, hold=1.5), seconds["k-close"]))
        # a clip that would need more than 1.3 s of held frame is refused
        with self.assertRaises(SystemExit) as err:
            eb.compose_shots(EXAMPLE, layout, clips, dict(seconds, **{"k-close": 5.0}))
        self.assertIn("KEEPER_CLIP_SHORT k-close", str(err.exception))

    def test_every_hold_compose_writes_is_one_short_engine_accepts(self):
        """Review of #408: compose_shots accepted a hold up to TALK_HOLD_MAX + 1 ms and wrote it + 0.01 s, which
        short_engine refused (> 1.3 s), so the run died later as CLIP_TOO_SHORT instead of KEEPER_CLIP_SHORT."""
        layout = layout_for(EXAMPLE, DURATIONS)
        clips = {s["id"]: f"{s['id']}.mp4" for s in EXAMPLE["shots"]}
        seconds = {s["id"]: (s.get("seconds") or 12) + 0.59 for s in EXAMPLE["shots"]}
        for sid in ("k-insight", "k-question", "k-close"):
            seconds[sid] = float(eb.talk_need(layout["keeper"][sid]["seconds"]))
        layout["total"] = round(layout["total"] + 0.2, 3)       # a 1.4 s tail: a hold near 1.3 s with the whole line
        span = layout["total"] - layout["keeper"]["k-close"]["start"]
        for hold in (1.28, 1.295, 1.3, 1.3005):
            clip = dict(seconds, **{"k-close": span - hold})
            try:
                shots = eb.compose_shots(EXAMPLE, layout, clips, clip)
            except SystemExit as err:
                self.assertIn("KEEPER_CLIP_SHORT k-close", str(err), hold)
                continue
            close = [c for c in shots if c["shot"] == "k-close"][0]
            self.assertIsNotNone(short_engine.explicit_speed(close, clip["k-close"]), hold)
        ok = eb.compose_shots(EXAMPLE, layout, clips, dict(seconds, **{"k-close": span - 1.28}))
        self.assertTrue(any(c["shot"] == "k-close" and c.get("hold") for c in ok))

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


class Gating(unittest.TestCase):
    """generate_step with a stubbed Pavo, download, clip_check, lipsync_check and face check: every talking clip is
    judged against its own line's WAV; God's voice-over shot is not lip-checked but must show no face; scenes and
    God's shot lose Pavo's audio track."""
    def setUp(self):
        self.saved = (eb.clip_flags, eb.lipsync_flags, eb.face_flags, eb.run)
        self.work = Path(tempfile.mkdtemp(dir=eb.REPO, prefix=".test-gate-"))
        self.plan = dialogue_plan()
        (self.work / "layout.json").write_text(json.dumps(layout_for(self.plan, [2.4, 3.0, 2.5, 3.1])))
        (self.work / "refs.json").write_text(json.dumps({"keeper": ["k.jpg"], "eve": ["eve.jpg"]}))
        self.lip, self.faces, self.stripped = [], [], []
        eb.clip_flags = lambda path: []
        eb.lipsync_flags = lambda py, model, clip, wav: (self.lip.append((Path(clip).name, Path(wav).name)) or [],
                                                         {"audio": {"corr": 0.9}, "mouth": {"corr": 0.5}})
        eb.face_flags = lambda py, model, clip: (self.faces.append(Path(clip).name) or [],
                                                 {"faces": {"frames_sampled": 40, "faces_found": 0}})
        eb.run = lambda args, **kw: (self.stripped.append(Path(str(args[-1])).name),
                                     Path(str(args[-1])).write_bytes(b"v"))

    def tearDown(self):
        eb.clip_flags, eb.lipsync_flags, eb.face_flags, eb.run = self.saved
        shutil.rmtree(self.work)

    def generate(self, extra=0):
        n = len(self.plan["shots"]) + extra
        client = FakeClient([{"conversation_id": str(i), "status": "submitted"} for i in range(n)],
                            {str(i): [done(str(i))] for i in range(n)})
        report = eb.generate_step(self.plan, self.work, "py", "model", client=client,
                                  download=lambda url, dst: Path(dst).write_bytes(b"raw"), sleep=lambda s: None)
        return client, report

    def test_an_invalid_request_is_refused_before_any_generation(self):
        # E106: the adapter's own checks (images, audio, prompt, seconds) ran only when a shot's turn came, after
        # the shots generated before it; now every request is validated offline first
        client = FakeClient([{"conversation_id": "0", "status": "submitted"}], {"0": [done("0")]})
        with self.assertRaises(SystemExit) as err:
            eb.generate_step(self.plan, self.work, "py", "model", client=client, validate=True,
                             download=lambda url, dst: None, sleep=lambda s: None)
        self.assertTrue(str(err.exception).startswith("REQUESTS_REFUSED"), err.exception)
        self.assertIn("INPUT_IMAGE_PATH_REFUSED", str(err.exception))
        self.assertEqual(client.calls, [])

    def test_a_rerun_keeps_the_clips_already_made_and_regenerates_only_the_rest(self):
        # E93: run 40263488773 lost 25 good clips when Pavo went unreachable at shot 26; a resumed run starts there
        first, report = self.generate()
        kept = self.plan["shots"][0]["id"]
        report["shots"].pop(self.plan["shots"][-1]["id"])                       # the shot the outage stopped
        (self.work / "clips" / f"{self.plan['shots'][-1]['id']}.mp4").unlink()
        (self.work / "report.json").write_text(json.dumps(report))
        client, again = self.generate()
        self.assertEqual(len(client.calls), 1)                                   # only the missing shot
        self.assertEqual(again["shots"][kept], report["shots"][kept])
        changed = json.loads((self.work / "report.json").read_text())
        changed["shots"][kept]["request"]["prompt"] = "an older prompt"         # a changed request is regenerated
        (self.work / "report.json").write_text(json.dumps(changed))
        client, _ = self.generate()
        self.assertEqual(len(client.calls), 1)

    def test_the_shots_that_can_fail_are_generated_first(self):
        # E99: genesis-07 builds failed on the Keeper's talking shots only after ~30 scene shots (hours, minutes of
        # Actions each time); the talking shots, then God's voice-over shots, are generated first
        shots = [{"id": "s-a", "kind": "scene", "lines": [0]},
                 {"id": "g-a", "kind": "scene", "speaker": eb.plan_check.ch.GOD, "line": "x", "lines": None},
                 {"id": "s-eve", "kind": "scene", "speaker": "eve", "line": "y", "characters": ["eve"]},
                 {"id": "s-b", "kind": "scene", "lines": [1]},
                 {"id": "k-a", "kind": "keeper", "lines": [2]}]
        order = [s["id"] for _, s in eb.risk_order(shots)]
        self.assertEqual(order, ["s-eve", "k-a", "g-a", "s-a", "s-b"])
        self.assertEqual([i for i, _ in eb.risk_order(shots)], [2, 4, 1, 0, 3])   # each keeps its plan index
        # generate_step's own Pavo submissions follow it: the Gating test below

    def test_generate_step_submits_the_talking_shots_then_gods_voice_over_then_the_scenes(self):
        # E99: s-eve and k-close (talking, with our line as input audio), then s-god (voice-over), then s-a
        client, report = self.generate()
        self.assertEqual([bool(c.get("audios")) for c in client.calls], [True, True, False, False])
        self.assertEqual(client.calls[2]["prompt"], "storm")
        self.assertEqual(list(report["shots"]), ["s-eve", "s-a", "s-god", "k-close"])   # the report keeps plan order

    def test_a_failed_shot_keeps_each_refused_generation_and_its_measures_in_the_report(self):
        # E94: run 40278642295 refused k-insight three times; only the flags reached the log, no clip, no measures
        eb.lipsync_flags = lambda py, model, clip, wav: (["AUDIO_NOT_OUR_LINE"], {"audio": {"corr": 0.2}, "mouth": {}})
        with self.assertRaises(SystemExit):
            self.generate(extra=eb.TALK_ATTEMPTS - 1)   # s-eve talks: every one of its generations is refused
        report = json.loads((self.work / "report.json").read_text())
        attempts = report["shots"]["s-eve"]["attempts"]
        self.assertEqual([a["clip"] for a in attempts],
                         [f"s-eve-fail{n}.mp4" for n in range(1, eb.TALK_ATTEMPTS + 1)])   # a talking shot (E98)
        self.assertEqual(attempts[0]["lipsync"]["audio"]["corr"], 0.2)
        for a in attempts:
            self.assertTrue((self.work / "clips" / a["clip"]).exists())
        wf = (eb.REPO / ".github/workflows/episode.yml").read_text()
        job = wf.split("\n  failure-evidence:\n")[1]
        self.assertIn("if: failure()", job)
        self.assertNotIn("secrets.", job)
        self.assertIn("-fail[0-9].mp4", job)

    def test_lipsync_runs_on_each_talking_clip_with_its_own_line(self):
        client, report = self.generate()
        self.assertEqual(self.lip, [("s-eve.mp4", "s-eve.wav"), ("k-close.mp4", "k-close.wav")])
        self.assertEqual(self.faces, ["s-god.mp4"])               # only God's voice-over shot is face-checked
        self.assertEqual(sorted(self.stripped), ["s-a.mp4", "s-god.mp4"])
        self.assertEqual(client.calls[0]["audios"], [".episode/x/speakers/s-eve.wav"])
        self.assertIsNone(client.calls[2]["audios"])
        self.assertEqual(report["shots"]["s-eve"]["speaker"], "eve")
        self.assertIn("lipsync", report["shots"]["s-eve"]["attempts"][0])
        self.assertNotIn("lipsync", report["shots"]["s-god"]["attempts"][0])
        self.assertEqual(report["shots"]["s-god"]["attempts"][0]["faces"]["faces_found"], 0)

    def test_a_face_in_gods_shot_is_regenerated_at_most_twice_then_the_run_stops(self):
        """Review of #400: a prompt can be written around the word list; the generated clip itself is checked."""
        found = {"n": 0}

        def faces(py, model, clip):
            found["n"] += 1
            return ["GOD_SHOT_FACE"], {"faces": {"frames_sampled": 40, "faces_found": 3}}
        eb.face_flags = faces
        with self.assertRaises(SystemExit) as err:
            self.generate(extra=2)
        self.assertIn("SHOT_FAILED s-god after 3 generations: GOD_SHOT_FACE", str(err.exception))
        self.assertEqual(found["n"], 3)
        report = json.loads((self.work / "report.json").read_text())
        self.assertIn("GOD_SHOT_FACE", report["shots"]["s-god"]["error"])

    def test_a_broken_face_check_stops_the_run_with_its_error_and_spends_no_regeneration(self):
        eb.face_flags = self.saved[2]
        fake = self.work / "python"
        fake.write_text("#!/bin/sh\necho 'ImportError: libGLESv2.so.2: cannot open shared object file' >&2\nexit 1\n")
        fake.chmod(0o755)
        with self.assertRaises(SystemExit) as caught:
            eb.face_flags(fake, "model.task", "clip.mp4")
        self.assertIn("FACE_TOOL_BROKEN exit 1", str(caught.exception))
        self.assertIn("libGLESv2.so.2", str(caught.exception))
        calls = []

        def attempt(n):
            calls.append(n)
            return {"generation": n}, self.work / "clip.mp4"
        with self.assertRaises(SystemExit):
            eb.make_shot("s-god", attempt, lambda path: eb.face_flags(fake, "model.task", path))
        self.assertEqual(calls, [1])

    def test_the_workflow_proves_the_face_check_before_any_generation(self):
        text = (eb.REPO / ".github" / "workflows" / "episode.yml").read_text()
        proof = text.find("lipsync_check.py --faces migration/evidence/pavo/20261026/keeper/keeper-lipsync.mp4")
        self.assertGreater(proof, 0)
        self.assertLess(proof, text.find("episode_build.py generate"))
        self.assertIn("FACE_CHECK_BLIND", text)


def tone_wav(path, seconds, rate=24000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", 3000 if (i // 40) % 2 else -3000) for i in range(int(seconds * rate))))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
class Lines(unittest.TestCase):
    PLAN = {"shots": [{"id": "k-open", "kind": "keeper", "lines": [0]}, {"id": "s-a", "kind": "scene", "lines": [1]},
                      {"id": "k-close", "kind": "keeper", "lines": [2]}],
            "narration": [{"text": "a"}, {"text": "b"}, {"text": "c"}]}

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(dir=eb.REPO / ".episode" if (eb.REPO / ".episode").is_dir() else eb.REPO,
                                          prefix="test-lines-"))

    def tearDown(self):
        shutil.rmtree(self.work)

    def voice(self, spans, seconds=70.0):
        """pilot_render's voice.wav and timeline: 0.3 s lead-in, sentences 0.18 s apart (line 1 has two)."""
        tone_wav(self.work / "voice.wav", seconds)
        segs = ["n00", "n01", "n01", "n02"]
        (self.work / "timeline.json").write_text(json.dumps({"sentences": [
            {"segment": g, "text": f"{g}.", "start": a, "end": b} for g, (a, b) in zip(segs, spans)]}))

    def test_the_narration_track_is_rebuilt_from_the_line_wavs_and_the_keeper_gets_his_line(self):
        # k-open 3.30 s misses Pavo's window (a 4 s clip, 0.70 s longer): retimed to 3.55 s; k-close 6.55 s fits a 7 s clip
        self.voice([(0.3, 3.6), (3.78, 30.0), (30.18, 60.0), (60.18, 66.73)])
        result = eb.lines_step(self.PLAN, self.work)
        starts = [x["start"] for x in result["lines"]]
        self.assertEqual(starts[0], 0.0)                       # the hook starts at 0 s
        self.assertAlmostEqual(result["lines"][0]["end"], 3.55, delta=0.02)
        self.assertAlmostEqual(starts[1], result["lines"][0]["end"] + eb.LINE_GAP, places=3)
        self.assertEqual(list(result["retimed"]), ["k-open"])
        self.assertAlmostEqual(result["retimed"]["k-open"]["atempo"], 3.3 / 3.55, places=3)
        k = result["keeper"]["k-close"]
        self.assertAlmostEqual(k["seconds"], 6.55, places=2)
        opened = result["keeper"]["k-open"]
        self.assertAlmostEqual(result["keeper_share"], (opened["seconds"] + k["seconds"]) / result["total"], places=2)
        for rec in (opened, k):                                  # the input audio is the retimed line itself
            info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels:format=duration",
                                   "-of", "json", str(eb.REPO / rec["wav"])], capture_output=True, text=True).stdout
            probe = json.loads(info)
            self.assertEqual((probe["streams"][0]["sample_rate"], probe["streams"][0]["channels"]), ("44100", 1))
            self.assertAlmostEqual(float(probe["format"]["duration"]), rec["seconds"], delta=0.02)
            self.assertTrue(eb.talk_fits(rec["seconds"]), rec)
        timeline = json.loads((self.work / "compose-timeline.json").read_text())
        self.assertAlmostEqual(timeline["sentences"][0]["end"], result["lines"][0]["end"], places=3)   # captions too
        self.assertAlmostEqual(timeline["sentences"][-1]["start"], k["start"], places=2)
        self.assertAlmostEqual(timeline["voice_seconds"], k["end"], places=2)

    def test_a_keeper_over_25_percent_measured_stops_the_run(self):
        self.voice([(0.3, 12.3), (12.48, 25.0), (25.18, 40.0), (40.18, 50.38)])
        with self.assertRaises(SystemExit) as err:
            eb.lines_step(self.PLAN, self.work)
        self.assertIn("KEEPER_SHARE", str(err.exception))

    def test_a_talking_line_is_retimed_into_a_clip_pavo_keeps_its_audio_in(self):
        """E95: Pavo kept our line only in a clip at most ~0.65 s longer than the speech (7 s for 6.385 s: audio 0.80;
        8 s: 0.36; 10 s: 0.03). A talking clip is ceil(speech) s with the speech 0.25-0.65 s shorter; a line that
        misses it is retimed to N - 0.45 s, at most +-10 %, else refused before any Pavo clip."""
        for speech, target in ((8.47, 8.47), (4.34, 4.55), (6.33, 6.55), (6.385, 6.385), (3.3, 3.55), (12.5, 11.55),
                               (9.9, 9.55), (5.2, 5.55)):
            got = eb.plan_check.talk_retime(speech)[0]
            self.assertAlmostEqual(got, target, places=3, msg=speech)
            self.assertTrue(eb.talk_fits(got), speech)
            self.assertLessEqual(abs(got / speech - 1), 0.10 + 1e-9, speech)
        for speech in (2.4, 3.0, 13.0, 15.0):
            self.assertIsNone(eb.plan_check.talk_retime(speech), speech)
        self.assertEqual([eb.talk_need(s) for s in (3.55, 4.55, 6.385, 8.47, 11.55)], [4, 5, 7, 9, 12])
        for clip, speech in ((7, 6.385), (5, 4.55)):          # the measured pass: at most 0.65 s of clip past the words
            self.assertLessEqual(clip - speech, plan_check_pad()[1])
        self.assertFalse(eb.talk_fits(6.385 - 1.6 + 1))       # 1.6 s longer: Pavo made its own track
        # lines_step refuses a talking line no 4-12 s clip can carry within 10 %, before any Pavo clip
        self.voice([(0.3, 2.7), (2.88, 30.0), (30.18, 60.0), (60.18, 66.73)])
        with self.assertRaises(SystemExit) as err:
            eb.lines_step(self.PLAN, self.work)
        self.assertIn("TALK_LINE_RETIME_OVER k-open 2.40 s", str(err.exception))
        self.assertNotIn("k-close", str(err.exception))

    def test_a_closing_keeper_line_over_the_talking_ceiling_is_retimed_under_it_not_refused(self):
        """Review of #408: an 11.6 s closing line fits a 12 s clip, so retime left it as it was, and the closing
        ceiling (11.55 s) then refused it (KEEPER_AUDIO). One ceiling: it is retimed to 11.55 s, exactly."""
        self.voice([(0.3, 3.85), (4.03, 30.0), (30.18, 50.0), (50.18, 61.78)], seconds=80.0)
        result = eb.lines_step(self.PLAN, self.work)
        k = result["keeper"]["k-close"]
        self.assertLessEqual(k["seconds"], eb.plan_check.TALK_LINE_MAX + 1e-3)
        self.assertAlmostEqual(k["seconds"], eb.plan_check.TALK_LINE_MAX, places=2)
        self.assertTrue(eb.talk_fits(k["seconds"]))
        self.assertEqual(list(result["retimed"]), ["k-close"])

    def test_a_voice_that_is_not_16_bit_is_refused_up_front_even_with_no_line_to_retime(self):
        """Review of #412: the width was checked only when a line needed a retime; lines_step checks every voice.wav
        once, before anything is cut (the retimed frames come back as pcm_s16le under its params)."""
        rate = 24000
        with wave.open(str(self.work / "voice.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(3)
            w.setframerate(rate)
            w.writeframes(b"\x00\x10\x00" * int(70 * rate))
        segs = ["n00", "n01", "n01", "n02"]
        spans = [(0.3, 3.85), (4.03, 30.0), (30.18, 60.0), (60.18, 66.73)]     # 3.55 s and 6.55 s: no retime
        (self.work / "timeline.json").write_text(json.dumps({"sentences": [
            {"segment": g, "text": f"{g}.", "start": a, "end": b} for g, (a, b) in zip(segs, spans)]}))
        with self.assertRaises(SystemExit) as err:
            eb.lines_step(self.PLAN, self.work)
        self.assertIn("VOICE_SAMPLE_WIDTH 24-bit", str(err.exception))

    def test_a_retime_that_misses_its_target_by_more_than_20_ms_is_refused(self):
        """Review of #412: the cut or pad to the target length is a few ms of atempo rounding, never more."""
        tone_wav(self.work / "t.wav", 6.0)
        params, frames = eb.read_wav(self.work / "t.wav")
        saved = eb.run

        def short_atempo(args, **kw):        # an atempo that lost 0.1 s
            tone_wav(Path(str(args[-1])), 6.0 / 1.05 - 0.1)
        eb.run = short_atempo
        try:
            with self.assertRaises(SystemExit) as err:
                eb.retime(frames, params, 1.05, self.work / "lines" / "n00")
        finally:
            eb.run = saved
        self.assertIn("RETIME_TRIM_OVER", str(err.exception))

    def test_a_retimed_line_is_exactly_its_target_length(self):
        """atempo overshoots by a few ms (11.7 s -> 11.553 s): the piece is cut or padded to the target frames, so a
        line retimed to the ceiling is not refused by it."""
        tone_wav(self.work / "t.wav", 11.7)
        params, frames = eb.read_wav(self.work / "t.wav")
        out = eb.retime(frames, params, 11.7 / 11.55, self.work / "lines" / "n00")
        self.assertEqual(len(out) // 2, int(11.55 * 24000))


class Retime(unittest.TestCase):
    """Review of #412: lines_step refuses exactly what plan_check.talk_retime refuses, through a real call."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(dir=eb.REPO / ".episode" if (eb.REPO / ".episode").is_dir() else eb.REPO,
                                          prefix="test-retime-"))

    def tearDown(self):
        shutil.rmtree(self.work)

    def lines(self, plan, spans, seconds=80.0):
        tone_wav(self.work / "voice.wav", seconds)
        (self.work / "timeline.json").write_text(json.dumps({"sentences": [
            {"segment": g, "text": f"{g}.", "start": a, "end": b} for g, (a, b) in spans]}))
        try:
            return eb.lines_step(plan, self.work), None
        except SystemExit as exc:
            return None, str(exc)

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
    def test_lines_step_refuses_what_plan_check_refuses(self):
        for speech in (3.3, 3.95, 4.0, 4.13, 4.14, 6.385, 11.7):
            spans = [("n00", (0.3, 0.3 + speech)), ("n01", (0.48 + speech, 30.0)), ("n01", (30.18, 70.0)),
                     ("n02", (70.18, 76.73))]
            result, err = self.lines(Lines.PLAN, spans, seconds=90.0)
            refused = err is not None and f"TALK_LINE_RETIME_OVER k-open {speech:.2f} s" in err
            self.assertEqual(refused, eb.plan_check.talk_retime(speech) is None, (speech, err))
            if not refused:
                self.assertIsNone(err, speech)

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
    def test_the_cap_is_on_the_words_of_a_shot_of_several_lines(self):
        """3.80 s of words + one 0.35 s gap: the whole shot is +9.6 % from 4.55 s, the words +10.5 %: refused. 3.90 s
        of words + the gap (4.25 s) are retimed into a 5 s clip, +7.7 % on the words."""
        plan = {"shots": [{"id": "k-open", "kind": "keeper", "lines": [0]}, {"id": "s-a", "kind": "scene", "lines": [1]},
                          {"id": "k-close", "kind": "keeper", "lines": [2, 3]}],
                "narration": [{"text": "a"}, {"text": "b"}, {"text": "c"}, {"text": "d"}]}
        for words, refused in ((3.80, True), (3.90, False)):
            half = words / 2
            spans = [("n00", (0.3, 3.85)), ("n01", (4.03, 66.0)), ("n02", (66.18, 66.18 + half)),
                     ("n03", (66.36 + half, 66.36 + words))]
            self.assertEqual(eb.plan_check.talk_retime(words, eb.LINE_GAP) is None, refused)
            result, err = self.lines(plan, spans)
            if refused:
                self.assertIn("TALK_LINE_RETIME_OVER k-close", err or "")
            else:
                self.assertIsNone(err)
                self.assertAlmostEqual(result["keeper"]["k-close"]["seconds"], 4.55, places=2)
                self.assertAlmostEqual(result["retimed"]["k-close"]["atempo"], words / (4.55 - eb.LINE_GAP), places=3)

    def test_the_build_has_no_second_retime_rule(self):
        self.assertFalse(hasattr(eb, "retime_target"))

    def test_the_hold_ceiling_is_the_same_in_compose_and_short_engine(self):
        self.assertEqual(eb.plan_check.TALK_HOLD_MAX, short_engine.HOLD_MAX)


def plan_check_pad():
    return eb.plan_check.TALK_PAD


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
            eb.reference_records = lambda cid, chars=None, field="refs": orig(cid, chars, recs, field)
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

    def test_talking_shots_get_the_speaking_frame_scenes_keep_the_front(self):
        """E95: the mouth-closed front view broke the lip tracking (lips -0.043); his calibration clip's speaking frame
        passed (0.578)."""
        talk = eb.reference_records("keeper", field="talk_refs")
        self.assertEqual([rid for rid, _ in talk], ["ch-keeper-talk"])
        self.assertEqual(talk[0][1]["repo_path"], "migration/evidence/pavo/20261026/keeper/storyteller-ref.jpg")
        self.assertEqual(hashlib.sha256((eb.REPO / talk[0][1]["repo_path"]).read_bytes()).hexdigest(), talk[0][1]["sha256"])
        self.assertEqual([rid for rid, _ in eb.reference_records("keeper")], ["ch-keeper-front"])
        self.assertEqual(eb.reference_records("eve", field="talk_refs"), [])   # no talk frame: the kept refs
        # review of #408: the talk frame replaces the approved refs (the passing direct tests sent it alone); the
        # record says so instead of "first reference"
        use = talk[0][1]["use"]
        self.assertIn("in place of", use)
        self.assertNotIn("first reference", use)
        work = Path(tempfile.mkdtemp(dir=eb.REPO, prefix=".test-talkrefs-"))
        try:
            plan = {"shots": [{"id": "k", "kind": "keeper", "lines": [0]}]}
            out = eb.refs_step(plan, work)
            self.assertEqual(sorted(out), ["keeper", "keeper:talk"])
            self.assertTrue(out["keeper:talk"][0].endswith("ch-keeper-talk.jpg"))
        finally:
            shutil.rmtree(work)


class LipsyncTool(unittest.TestCase):
    """E89: on the runner mediapipe could not load libEGL, the check printed no JSON, and three Keeper generations
    were spent on a broken tool, recorded only as LIPSYNC_CHECK_FAILED."""
    def test_a_broken_check_stops_the_run_with_its_error_and_spends_no_regeneration(self):
        with tempfile.TemporaryDirectory() as t:
            fake = Path(t) / "python"
            fake.write_text("#!/bin/sh\necho 'ImportError: libEGL.so.1: cannot open shared object file' >&2\nexit 1\n")
            fake.chmod(0o755)
            with self.assertRaises(SystemExit) as caught:
                eb.lipsync_flags(fake, "model.task", "clip.mp4", "line.wav")
            self.assertIn("LIPSYNC_TOOL_BROKEN exit 1", str(caught.exception))
            self.assertIn("libEGL.so.1", str(caught.exception))
            calls = []

            def attempt(n):
                calls.append(n)
                return {"generation": n}, Path(t) / "clip.mp4"

            def check(path):
                return eb.lipsync_flags(fake, "model.task", path, "line.wav")
            with self.assertRaises(SystemExit):
                eb.make_shot("k-close", attempt, check)
            self.assertEqual(calls, [1])

    def test_the_workflow_installs_the_check_libraries_and_proves_the_check_before_any_generation(self):
        text = (eb.REPO / ".github" / "workflows" / "episode.yml").read_text()
        apt = [l for l in text.splitlines() if "apt-get install" in l][0]
        for lib in ("libegl1", "libgles2"):
            self.assertIn(lib, apt)
        proof = text.find("lipsync_check.py migration/evidence/pavo/20261026/keeper/keeper-lipsync.mp4")
        self.assertGreater(proof, 0)
        self.assertLess(proof, text.find("episode_build.py generate"))
        for f in ("keeper-lipsync.mp4", "line-01.wav"):
            self.assertTrue((eb.REPO / "migration/evidence/pavo/20261026/keeper" / f).exists())


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
