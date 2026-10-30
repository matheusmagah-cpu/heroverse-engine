#!/usr/bin/env python3
"""episode_build.py offline (stubbed Pavo client and voice): shot -> Pavo request, a failed shot regenerated at most
twice, an uncertain submission only read back, and the compose timeline keeps the Keeper's picture on his line."""
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "migration" / "integrations" / "pavo"))
import episode_build as eb  # noqa: E402
import short_engine  # noqa: E402
from client import PavoError  # noqa: E402

HAS_FFMPEG = shutil.which("ffmpeg") is not None


# genesis-07-short.json as main had it before plan B (#413, commit 1c1ed79): the lip-synced Keeper. Run 40307414749
# built its 30 scene and God clips from exactly these requests (its report.json: 30 of 30 prompts and seconds equal)
TALKING_COMMIT = "1c1ed79"


def talking_genesis_07():
    out = subprocess.run(["git", "-C", str(HERE), "show",
                          f"{TALKING_COMMIT}:migration/production/bible/plans/genesis-07-short.json"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


# E108: every scene prompt states its period word for word (plan_check.period_problems; request() refuses one that
# does not). The older plans and the stubs here get it the way genesis-07's unchanged scenes got it: the period
# inserted before the standard tail
PERIOD = f"{eb.plan_check.PERIOD_SETTING} {eb.plan_check.PERIOD_EXCLUDE}"
TAIL = re.compile(r"\s*(No people, no text, no logos\.|No text, no logos\.)$")


def with_period(plan):
    plan.setdefault("period", "before-the-flood")
    for s in plan["shots"]:
        if s["kind"] == "scene" and PERIOD not in s["prompt"]:
            m = TAIL.search(s["prompt"])
            s["prompt"] = f"{s['prompt'][:m.start()]} {PERIOD} {m.group(1)}" if m else f"{s['prompt']} {PERIOD}"
    return plan


# the default mode (a talking, lip-synced Keeper) is tested on the plan main had before plan B; genesis-07 itself is
# now the voice-over plan (VO_EXAMPLE)
EXAMPLE = with_period(talking_genesis_07())
# its scene prompts asked for "the road out of the city", "a lane", "the city of tents", "a quiet room": refused now
# (SCENE_PERIOD_CONFLICT, E108), so every scene takes genesis-07's own prompt; the talking Keeper stays the test's
_NOW = {v["id"]: v["prompt"] for v in json.loads((HERE / "plans" / "genesis-07-short.json").read_text())["shots"]}
EXAMPLE["shots"] = [dict(s, prompt=_NOW[s["id"]]) if s["kind"] == "scene" else s for s in EXAMPLE["shots"]]


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
        if eb.plan_check.voiceover(s):      # plan B: no input audio, his line plays from the voice track
            keeper[s["id"]] = dict(rec, voiceover=True)
        elif s["kind"] == "keeper":
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


def _dialogue_plan():
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


def dialogue_plan():
    return with_period(_dialogue_plan())


class SourceRevocations(unittest.TestCase):
    def test_e189_shot_writer_archives_current_only_revocation_before_replacement(self):
        from unittest import mock
        # Named reviewer and measured-duration fields are offline fixtures for the E149/E152 writer contract.
        reviewer = {"reviewer": "gpt-6-astra-session-reviewer"} if hasattr(eb, "reviewer_identity") else {}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(eb, "REPO", Path(tmp)):
            directory = Path(tmp, "approvals")
            path = directory / "fixture.json"
            original = {"score": 9.6, "clip_sha256": "a" * 64, "request_sha256": "c" * 64,
                        "note": "historical review", "revocation": {"by": "ChatGPT", "reason": "visible aircraft"}}
            eb.save(path, {"episode": "fixture", "shots": {"s": original}})
            record = Path(tmp, "migration/evidence/shots/fixture/probe.json")
            eb.save(record, {"episode": "fixture", "run_id": "40500000001", "shots": {"s": {
                "request_sha256": "c" * 64, "clip_seconds": 6,
                "clips": [{"asset": name, "clip_sha256": sha, "uploaded": True, "flags": [],
                           "media": {"version": "clip-media-v1", "clip_sha256": sha,
                                     "video_seconds": 6.0, "audio_seconds": None}}
                          for name, sha in (("new.mp4", "b" * 64), ("old.mp4", "a" * 64))]}}})
            before = path.read_bytes()
            with self.assertRaisesRegex(SystemExit, "SHOT_REVIEW_REVOKED"):
                eb.approve_shot(record, "s", "old.mp4", 10, "not reinstatement", shots_dir=directory, **reviewer)
            self.assertEqual(path.read_bytes(), before)
            eb.approve_shot(record, "s", "new.mp4", 9.6, "replacement reviewed", shots_dir=directory, **reviewer)
            replaced = eb.load(path)
            self.assertEqual(replaced["revocations"], [dict(original, shot="s")])
            self.assertEqual(replaced["shots"]["s"]["clip_sha256"], "b" * 64)
            self.assertNotIn("revocation", replaced["shots"]["s"])
            eb.approve_shot(record, "s", "new.mp4", 9.6, "replacement reviewed", shots_dir=directory, **reviewer)
            self.assertEqual(eb.load(path)["revocations"], replaced["revocations"])
            before = path.read_bytes()
            with self.assertRaisesRegex(SystemExit, "SHOT_REVIEW_REVOKED"):
                eb.approve_shot(record, "s", "old.mp4", 10, "not reinstatement", shots_dir=directory, **reviewer)
            self.assertEqual(path.read_bytes(), before)

    def test_e189_revocation_wins_score_digest_and_source_type(self):
        # A retraction is not a new quality score or a model-approved replacement.
        with tempfile.TemporaryDirectory() as tmp:
            for source in ("pavo", "pavo_reuse", "footage", "still_motion"):
                for marker in ({"by": "ChatGPT", "reason": "visible aircraft"}, None, False):
                    with self.subTest(source=source, marker=marker):
                        rec = {"source": source, "score": 10, "clip_sha256": "a" * 64,
                               "still_sha256": "b" * 64, "request_sha256": "c" * 64,
                               "revocation": marker}
                        before = copy.deepcopy(rec)
                        bad = eb.revocation_problems("fixture", {"s": rec}, shots_dir=tmp)
                        self.assertTrue(any(p.startswith("SHOT_REVIEW_REVOKED") for p in bad), bad)
                        self.assertEqual(rec, before)
            self.assertEqual(eb.revocation_problems("fixture", {"s": {"score": 9.6}}, shots_dir=tmp), [])

    def test_e189_revoked_bytes_cannot_be_reused_even_after_the_source_shot_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "origin.json").write_text(json.dumps({"shots": {"s": {"clip_sha256": "d" * 64}},
                "revocations": [{"shot": "s", "clip_sha256": "a" * 64, "score": 9.6,
                                 "revocation": {"by": "ChatGPT", "reason": "visible aircraft"}}]}))
            for source in ("pavo", "pavo_reuse", "footage", "still_motion"):
                rec = {"source": source, "score": 10, "request_sha256": "c" * 64,
                       ("still_sha256" if source == "still_motion" else "clip_sha256"): "a" * 64}
                self.assertTrue(eb.revocation_problems("borrower", {"s": rec}, shots_dir=tmp))
            self.assertTrue(eb.revocation_problems("old-master", {}, shots_dir=tmp, source_hashes=["a" * 64]))
            self.assertEqual(eb.revocation_problems("origin", shots_dir=tmp), [])

    def test_e189_corrupt_revocation_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for history in (False, [{"revocation": {"reason": "missing hash"}}]):
                Path(tmp, "origin.json").write_text(json.dumps({"revocations": history}))
                self.assertTrue(eb.revocation_problems("fixture", {}, shots_dir=tmp))


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

    def test_the_prediction_and_the_compose_share_one_establishing_share(self):
        # review of #422: compose_prediction had its own copy of compose_step's establishing share
        layout = eb.predict(EXAMPLE, DURATIONS)[1]
        saved = eb.establishing_share
        try:
            eb.establishing_share = lambda plan, shots, total: 0.5
            self.assertIn("ESTABLISHING_SHARE 0.500 (composed)", eb.compose_prediction(EXAMPLE, layout))
        finally:
            eb.establishing_share = saved
        import inspect
        self.assertIn("establishing_share(plan, shots, layout[\"total\"])", inspect.getsource(eb.compose_step))


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
        if isinstance(item, BaseException):   # a cancel (KeyboardInterrupt) or a SIGTERM exit too
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
    """generate_clips (shot-probe.yml's generation engine, E114) with a stubbed Pavo, download, clip_check, lipsync_check and face check: every talking clip is
    judged against its own line's WAV; God's voice-over shot is not lip-checked but must show no face; scenes and
    God's shot lose Pavo's audio track."""
    def setUp(self):
        self.saved = (eb.clip_flags, eb.lipsync_flags, eb.face_flags, eb.run)
        self.work = Path(tempfile.mkdtemp(dir=eb.REPO, prefix=".test-gate-"))
        self.plan = dialogue_plan()
        (self.work / "layout.json").write_text(json.dumps(layout_for(self.plan, [2.4, 3.0, 2.5, 3.1])))
        (self.work / "refs.json").write_text(json.dumps({"keeper": ["k.jpg"], "eve": ["eve.jpg"]}))
        self.lip, self.faces, self.stripped = [], [], []
        eb.clip_flags = lambda path, aspect=None: []
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
        report = eb.generate_clips(self.plan, self.work, "py", "model", client=client,
                                   download=lambda url, dst: Path(dst).write_bytes(b"raw"), sleep=lambda s: None)
        return client, report

    def test_an_invalid_request_is_refused_before_any_generation(self):
        # E106: the adapter's own checks (images, audio, prompt, seconds) ran only when a shot's turn came, after
        # the shots generated before it; now every request is validated offline first
        client = FakeClient([{"conversation_id": "0", "status": "submitted"}], {"0": [done("0")]})
        with self.assertRaises(SystemExit) as err:
            eb.generate_clips(self.plan, self.work, "py", "model", client=client, validate=True,
                              download=lambda url, dst: None, sleep=lambda s: None)
        self.assertTrue(str(err.exception).startswith("REQUESTS_REFUSED"), err.exception)
        self.assertIn("INPUT_IMAGE_PATH_REFUSED", str(err.exception))
        self.assertEqual(client.calls, [])

    def approvals(self, clip=b"approved clip"):
        layout, refs = json.loads((self.work / "layout.json").read_text()), json.loads((self.work / "refs.json").read_text())
        sha = hashlib.sha256(clip).hexdigest()
        return {s["id"]: {"asset": eb.shot_asset_name(self.plan["episode"], s["id"], sha), "clip_sha256": sha,
                          "request_sha256": eb.request_identity(s, i, self.plan, layout, refs)[0], "score": 9.6,
                          "clip_seconds": eb.shot_seconds(s, i, self.plan, layout)}
                for i, s in enumerate(self.plan["shots"])}

    def test_a_fallback_approval_never_ships_on_a_spoken_or_character_shot(self):
        # review of #476: generate_step checks again, at build, that a footage / still approval is on a shot with no
        # line and no character, even when its request digest was made to match (a hand-written approval)
        import shot_sources as ss
        approvals, sha = self.approvals(), hashlib.sha256(b"approved clip").hexdigest()
        for want in ("SOURCE_SPOKEN_SHOT", "SOURCE_CHARACTER_SHOT"):
            plan = copy.deepcopy(self.plan)
            spoken = [k for k, s in enumerate(plan["shots"]) if eb.pavo_native.spoken(s)]
            i = spoken[0] if want == "SOURCE_SPOKEN_SHOT" else next(
                k for k, s in enumerate(plan["shots"]) if k not in spoken and s["kind"] == "scene")
            shot = plan["shots"][i]
            if want == "SOURCE_CHARACTER_SHOT":
                shot["characters"] = ["eve"]   # the plan changed the shot after a fallback was chosen for it
            forged = dict(approvals, **{shot["id"]: dict(
                approvals[shot["id"]], source="footage", footage="clip-river-a",
                request_sha256=ss.fallback_digest(plan, shot, i, "footage", "clip-river-a", sha))})
            self.assertFalse([m for m in eb.review_problems(plan, {}, {shot["id"]: forged[shot["id"]]})
                              if m.startswith("SHOT_REQUEST_CHANGED")])   # the digest alone would let it through
            with self.assertRaises(SystemExit) as err:
                eb.generate_step(plan, self.work, "py", "model", approvals=forged,
                                 fetch=lambda name, dst: Path(dst).write_bytes(b"approved clip"))
            self.assertTrue(str(err.exception).startswith(f"{want} {shot['id']}"), err.exception)

    def test_e189_revocation_blocks_build_before_any_fetch(self):
        import shot_sources as ss
        for source in ("pavo", "pavo_reuse", "footage", "still_motion"):
            with self.subTest(source=source):
                approvals = self.approvals()
                digests = {k: a["request_sha256"] for k, a in approvals.items()}
                rec = approvals["s-a"]
                rec.update(source=source, footage="fixture-footage", still="fixture-still", clip_from="origin#s",
                           still_sha256="e" * 64, revocation={"by": "ChatGPT", "reason": "visible aircraft"})
                rec["request_sha256"] = ss.expected_request(self.plan, self.plan["shots"][1], 1, rec, digests)
                bad = eb.review_problems(self.plan, digests, approvals)
                self.assertFalse(any(p.startswith("SHOT_REQUEST_CHANGED") for p in bad), bad)
                with self.assertRaisesRegex(SystemExit, "SHOT_REVIEW_REVOKED"):
                    eb.generate_step(self.plan, self.work, "py", "model", approvals=approvals,
                                     fetch=lambda *a: self.fail("revoked bytes were fetched"))

    def test_a_build_never_generates_a_shot_that_has_a_reviewed_clip(self):
        # E114 (genesis-07: 8 builds; genesis-08: 7 of 29 shots rejected at the review after a full build): the clip
        # Claude reviewed is the clip the build ships, downloaded by its content hash and checked again, never a new one
        approvals, fetched, checked = self.approvals(), [], []
        eb.clip_flags = lambda path, aspect=None: checked.append(Path(path).name) or []

        def fetch(name, dst):
            fetched.append(name)
            Path(dst).write_bytes(b"approved clip")
        saved = eb.submit
        eb.submit = lambda *a, **k: self.fail("the build submitted a generation")
        try:
            with self.assertRaises(SystemExit) as err:                # no approved clip: refused before any fetch
                eb.generate_step(self.plan, self.work, "py", "model", approvals={}, fetch=fetch)
            self.assertTrue(str(err.exception).startswith("SHOT_NOT_REVIEWED"), err.exception)
            self.assertEqual(fetched, [])
            report = eb.generate_step(self.plan, self.work, "py", "model", approvals=approvals, fetch=fetch)
            self.assertEqual(sorted(fetched), sorted(a["asset"] for a in approvals.values()))
            self.assertEqual(sorted(checked), sorted(f"{s['id']}.mp4" for s in self.plan["shots"]))
            self.assertTrue(all(v["approved"]["asset"] == approvals[k]["asset"] for k, v in report["shots"].items()))
            self.assertTrue(len(self.lip) > 0)                                   # talking clips lip-checked again
            # a resume keeps an approved clip already on disk (same sha256) without downloading it again
            fetched.clear()
            eb.generate_step(self.plan, self.work, "py", "model", approvals=approvals, fetch=fetch)
            self.assertEqual(fetched, [])
            # a clip approved for another request is never shipped
            sid = self.plan["shots"][0]["id"]
            changed = dict(approvals, **{sid: dict(approvals[sid], request_sha256="0" * 64)})
            with self.assertRaises(SystemExit) as err:
                eb.generate_step(self.plan, self.work, "py", "model", approvals=changed, fetch=fetch)
            self.assertEqual(str(err.exception).split(" (")[0], f"SHOT_REQUEST_CHANGED {sid}")
            # E118: a clip shorter than this machine's layout needs is never shipped, refused before any download
            fetched.clear()
            short = dict(approvals, **{sid: dict(approvals[sid], clip_seconds=approvals[sid]["clip_seconds"] - 1)})
            with self.assertRaises(SystemExit) as err:
                eb.generate_step(self.plan, self.work, "py", "model", approvals=short, fetch=fetch)
            self.assertTrue(str(err.exception).startswith(f"SHOT_CLIP_TOO_SHORT {sid}("), err.exception)
            self.assertEqual(fetched, [])
            # another file under the asset's name is refused; an approved clip failing the checks stops the run
            for f in (self.work / "clips").glob("*.mp4"):
                f.unlink()
            with self.assertRaises(SystemExit) as err:
                eb.generate_step(self.plan, self.work, "py", "model", approvals=approvals,
                                 fetch=lambda name, dst: Path(dst).write_bytes(b"other"))
            self.assertTrue(str(err.exception).startswith("SHOT_CLIP_SHA256_MISMATCH"))
            eb.clip_flags = lambda path, aspect=None: ["BLACK_FRAMES"]
            with self.assertRaises(SystemExit) as err:
                eb.generate_step(self.plan, self.work, "py", "model", approvals=approvals, fetch=fetch)
            self.assertIn("SHOT_APPROVED_CLIP_FAILED", str(err.exception))
        finally:
            eb.submit = saved
        # the build step holds no Pavo secret and constructs no client
        src = (eb.HERE / "episode_build.py").read_text()
        build = src[src.index("def generate_step("):src.index("# ---------- shot probe and approval")]
        self.assertNotIn("PavoVideoClient", build)
        wf = (eb.REPO / ".github/workflows/episode.yml").read_text()
        self.assertNotIn("PAVO_TOKEN", wf)

    def test_the_request_digest_holds_nothing_derived_from_a_measurement(self):
        # E118 (genesis-08 run 40483267526: SHOT_REQUEST_CHANGED k-insight, Kokoro 174.0 s local vs 173.929 s on the
        # runner): the derived clip seconds of a voice-over or talking shot flipped across a rounding boundary. Class
        # level: every shot of every kind, with every measured value of the layout moved so the derived clip seconds
        # cross a boundary, digests the same; coverage (not the digest) checks the clip's length
        layout, refs = json.loads((self.work / "layout.json").read_text()), json.loads((self.work / "refs.json").read_text())
        vo = copy.deepcopy(self.plan)
        k = next(i for i, s in enumerate(vo["shots"]) if s["kind"] == "keeper")
        vo["shots"][k]["voiceover"] = True
        refs = dict(refs, **{"keeper:talk": ["k-talk.jpg"]})
        for plan in (self.plan, vo):
            moved = copy.deepcopy(layout)
            for rec in moved["lines"]:
                rec["start"], rec["end"] = round(rec["start"] + 1.003, 3), round(rec["end"] + 1.003, 3)
            moved["total"] = layout["total"] + 1.003
            for group in ("keeper", "speakers"):
                for rec in moved.get(group, {}).values():
                    for key in ("start", "end", "seconds"):
                        if isinstance(rec.get(key), (int, float)):
                            rec[key] = round(rec[key] + 1.003, 3)
            crossed = 0
            for i, s in enumerate(plan["shots"]):
                a = eb.request_identity(s, i, plan, layout, refs)
                b = eb.request_identity(s, i, plan, moved, refs)
                self.assertEqual(a[0], b[0], s["id"])
                self.assertNotIn("seconds", a[1])
                self.assertNotIn("seconds", a[1]["audio"] or {})
                crossed += eb.shot_seconds(s, i, plan, layout) != eb.shot_seconds(s, i, plan, moved)
            self.assertGreater(crossed, 0)       # the move did cross a rounding boundary of the derived seconds
            # and coverage refuses the clip made for the shorter layout once the layout needs more
            needs = eb.clip_needs(plan, moved)
            have = {s["id"]: {"clip_seconds": eb.shot_seconds(s, i, plan, layout)} for i, s in enumerate(plan["shots"])}
            short = eb.coverage_problems(plan, needs, have)
            self.assertTrue(short and short[0].startswith("SHOT_CLIP_TOO_SHORT"), short)
            self.assertEqual(eb.coverage_problems(plan, eb.clip_needs(plan, layout), have), [])
            # a measurement within MEASURE_TOLERANCE above the one the clip was made for still covers it (the runner
            # measures a few hundredths apart from the local preflight)
            near = copy.deepcopy(layout)
            for group in ("keeper", "speakers"):
                for rec in near.get(group, {}).values():
                    rec["seconds"] = round(rec["seconds"] + eb.MEASURE_TOLERANCE * 0.9, 3)
            self.assertEqual(eb.coverage_problems(plan, eb.clip_needs(plan, near, eb.MEASURE_TOLERANCE), have), [])

    def test_every_committed_approval_records_its_clip_seconds(self):
        # E118: coverage reads the seconds an approved clip was generated at; an approval without them covers nothing
        for path in sorted(eb.SHOTS_DIR.glob("*.json")):
            for sid, a in json.loads(path.read_text())["shots"].items():
                self.assertTrue(isinstance(a.get("clip_seconds"), int) and a["clip_seconds"] > 0, f"{path.name} {sid}")

    def test_the_request_digest_ignores_measured_seconds_but_not_the_words(self):
        # E114 (review of #442): Kokoro measures differ between the local preflight and the runners by a few ms; the
        # digest covers what decides the clip and the words, never a measured value (E118: nor the derived seconds)
        layout, refs = json.loads((self.work / "layout.json").read_text()), json.loads((self.work / "refs.json").read_text())
        moved = copy.deepcopy(layout)
        for group in ("keeper", "speakers"):
            for rec in moved.get(group, {}).values():
                for k in ("start", "end", "seconds"):
                    if isinstance(rec.get(k), (int, float)):
                        rec[k] = round(rec[k] + 0.04, 3)
        talk = [(i, s) for i, s in enumerate(self.plan["shots"]) if eb.plan_check.talking(s)]
        self.assertTrue(talk)
        for i, s in talk:
            a = eb.request_identity(s, i, self.plan, layout, refs)
            b = eb.request_identity(s, i, self.plan, moved, refs)
            self.assertEqual(a[0], b[0], s["id"])
            self.assertNotIn("seconds", a[1]["audio"])
        i, s = next((i, s) for i, s in talk if eb.plan_check.speaking(s))
        edited = copy.deepcopy(self.plan)
        edited["shots"][i]["line"] = edited["shots"][i]["line"] + " Amen"
        self.assertNotEqual(eb.request_identity(edited["shots"][i], i, edited, layout, refs)[0],
                            eb.request_identity(s, i, self.plan, layout, refs)[0])

    def test_a_probe_generates_the_build_request_and_approval_copies_its_hashes(self):
        # E114: shot-probe.yml generates exactly the request the build sends, with the build's checks; approve-shot
        # copies the reviewed clip's hashes from the sealed probe record (nobody hand-edits them), only at 9.5-10
        ids, n = eb.probe_ids(self.plan, f" {self.plan['shots'][0]['id']} ", "2")
        for text, attempts in (("", "2"), ("x;y", "2"), ("no-such-shot", "2"), (ids[0], "0"), (ids[0], "7")):
            with self.assertRaises(SystemExit):
                eb.probe_ids(self.plan, text, attempts)
        client = FakeClient([{"conversation_id": str(i), "status": "submitted"} for i in range(n)],
                            {str(i): [done(str(i))] for i in range(n)})
        out = self.work / "out"
        sheets = []
        record = eb.probe_step(self.plan, self.work, "py", "model", out, ids, n, client=client,
                               download=lambda url, dst: Path(dst).write_bytes(b"raw"), sleep=lambda s: None,
                               sheet=lambda video, sheet: sheets.append(Path(sheet).name))
        layout, refs = json.loads((self.work / "layout.json").read_text()), json.loads((self.work / "refs.json").read_text())
        build_req = eb.request(self.plan["shots"][0], 0, self.plan, layout, refs)
        self.assertEqual(client.calls, [build_req, build_req])
        entry = record["shots"][ids[0]]
        self.assertEqual(entry["request_sha256"], eb.request_identity(self.plan["shots"][0], 0, self.plan, layout, refs)[0])
        self.assertEqual((len(entry["clips"]), len(sheets)), (2, 2))
        clip = entry["clips"][0]
        self.assertEqual(clip["clip_sha256"], eb.sha256(out / clip["asset"]))
        self.assertEqual(clip["asset"], eb.shot_asset_name(self.plan["episode"], ids[0], clip["clip_sha256"]))
        self.assertEqual(eb.probe_assets(out, self.plan["episode"]), [clip["asset"]])
        with self.assertRaises(SystemExit) as err:
            eb.probe_assets(self.work / "nothing", self.plan["episode"])
        self.assertTrue(str(err.exception).startswith("NO_PROBE_RECORD"))
        records = eb.REPO / "migration" / "evidence" / "shots"
        rec = Path(tempfile.mkdtemp(dir=records.parent, prefix=".test-shots-"))
        records.mkdir(parents=True, exist_ok=True)
        unsealed, path = records / f".test-{os.getpid()}-raw.json", records / f".test-{os.getpid()}.json"
        try:
            with self.assertRaises(SystemExit) as err:                             # outside evidence/shots/
                eb.approve_shot(out / "probe.json", ids[0], clip["asset"], "9.6", "ok", shots_dir=rec, reviewer="claude-session-reviewer")
            self.assertTrue(str(err.exception).startswith("SHOT_RECORD_REFUSED"))
            shutil.copyfile(out / "probe.json", unsealed)                          # not from shot-probe's record job
            with self.assertRaises(SystemExit) as err:
                eb.approve_shot(unsealed, ids[0], clip["asset"], "9.6", "ok", shots_dir=rec, reviewer="claude-session-reviewer")
            self.assertTrue(str(err.exception).startswith("SHOT_RECORD_REFUSED"))
            no_upload = dict(json.loads(unsealed.read_text()), run_id="40500000001")
            unsealed.write_text(json.dumps(no_upload))
            with self.assertRaises(SystemExit) as err:
                eb.approve_shot(unsealed, ids[0], clip["asset"], "9.6", "ok", shots_dir=rec, reviewer="claude-session-reviewer")
            self.assertTrue(str(err.exception).startswith("SHOT_CLIP_NOT_UPLOADED"))
            media = {"version": "clip-media-v1", "clip_sha256": clip["clip_sha256"],
                     "video_seconds": 7.25, "audio_seconds": 7.28}
            with patch.object(eb.clip_timing, "measure", return_value=media):  # probe fixture has fake media bytes
                eb.probe_assets(out, self.plan["episode"], "40500000001", path)
            for model in (None, "unknown-session"):
                with self.assertRaisesRegex(SystemExit, "REVIEWER_IDENTITY_REFUSED"):
                    eb.approve_shot(path, ids[0], clip["asset"], "9.6", "reviewed fixture", shots_dir=rec,
                                    reviewer=model)
                self.assertFalse((rec / f"{self.plan['episode']}.json").exists())
            for score, note, code in (("9.4", "ok", "SHOT_SCORE_OUT_OF_RANGE"), ("10.5", "ok", "SHOT_SCORE_OUT_OF_RANGE"),
                                      ("nan", "ok", "SHOT_SCORE_OUT_OF_RANGE"), ("inf", "ok", "SHOT_SCORE_OUT_OF_RANGE"),
                                      ("9.6", " ", "SHOT_NOTE_MISSING"), ("x", "ok", "SHOT_SCORE_INVALID")):
                with self.assertRaises(SystemExit) as err:
                    eb.approve_shot(path, ids[0], clip["asset"], score, note, shots_dir=rec, reviewer="claude-session-reviewer")
                self.assertTrue(str(err.exception).startswith(code), (score, err.exception))
            approved = eb.approve_shot(path, ids[0], clip["asset"], "9.6", "period, faces, motion clean", shots_dir=rec,
                                       reviewer="gpt-6-astra-session-reviewer")
            self.assertEqual(approved["model"], "gpt-6-astra-session-reviewer")
            self.assertEqual(approved["clip_seconds"], media["video_seconds"])
            self.assertEqual(approved["requested_clip_seconds"], entry["clip_seconds"])
            self.assertEqual(approved["media"], media)
            self.assertEqual((approved["clip_sha256"], approved["request_sha256"], approved["asset"], approved["run_id"]),
                             (clip["clip_sha256"], entry["request_sha256"], clip["asset"], "40500000001"))
            self.assertEqual(eb.load_approvals(self.plan, rec / f"{self.plan['episode']}.json")[ids[0]], approved)
            # E189: an explicit retraction cannot be overwritten by the same bytes with a higher score.
            approvals_path = rec / f"{self.plan['episode']}.json"
            history = json.loads(approvals_path.read_text())
            history["revocations"] = [dict(approved, shot=ids[0], revocation={
                "by": "ChatGPT", "reason": "later direct visual inspection found a modern object"})]
            approvals_path.write_text(json.dumps(history))
            before = approvals_path.read_bytes()
            with self.assertRaisesRegex(SystemExit, "SHOT_REVIEW_REVOKED"):
                eb.approve_shot(path, ids[0], clip["asset"], "10", "new score cannot undo revocation", shots_dir=rec)
            self.assertEqual(approvals_path.read_bytes(), before)
            failed = json.loads(path.read_text())
            failed["shots"][ids[0]]["clips"][0]["flags"] = ["FREEZE"]
            path.write_text(json.dumps(failed))
            with self.assertRaises(SystemExit) as err:
                eb.approve_shot(path, ids[0], clip["asset"], "9.8", "ok", shots_dir=rec, reviewer="claude-session-reviewer")
            self.assertTrue(str(err.exception).startswith("SHOT_CHECKS_FAILED"))
        finally:
            for f in (path, unsealed):
                f.unlink(missing_ok=True)
            shutil.rmtree(rec)

    def test_a_clip_a_build_made_and_claude_approved_is_adopted_without_a_generation(self):
        # E114: genesis-08's clips approved inside build runs 40438106839/40460764662 are adopted from the run's
        # artifact: what the run sent (its recorded request, the words of its input audio) must equal the plan's
        # request now; a line edited after the run is refused; the build's checks run again
        self.generate()
        run = self.work / "run"
        (run / "clips").mkdir(parents=True)
        for name in ("report.json", "layout.json"):
            shutil.copyfile(self.work / name, run / name)
        for f in (self.work / "clips").glob("*.mp4"):
            shutil.copyfile(f, run / "clips" / f.name)
        layout = json.loads((self.work / "layout.json").read_text())
        items, carried = eb.plan_check.sequence(self.plan)
        sentences, made = [], []
        for i, s in enumerate(self.plan["shots"]):
            if eb.plan_check.talking(s):
                rec = eb.talk_record(layout, s)
                sentences.append({"segment": "n", "text": " ".join(items[k]["text"] for k in carried[i]),
                                  "start": rec["start"], "end": rec["end"]})
                wav = eb.REPO / rec["wav"]
                (run / "clips" / wav.name).write_bytes(b"wav")
                if not wav.exists():
                    made.append(wav)
        (run / "compose-timeline.json").write_text(json.dumps({"sentences": sentences}))
        saved = eb.ref_paths
        eb.ref_paths = lambda plan, work, chars=None: json.loads((self.work / "refs.json").read_text())
        try:
            ids = [s["id"] for s in self.plan["shots"]]
            out = self.work / "adopted"
            record = eb.adopt_step(self.plan, run, "py", "model", out, ids, "40460764662",
                                   sheet=lambda video, sheet: None)
            self.assertEqual(set(record["shots"]), set(ids))
            sid = ids[0]
            clip = record["shots"][sid]["clips"][0]
            self.assertEqual((clip["source_run"], clip["clip_sha256"]),
                             ("40460764662", eb.sha256(run / "clips" / f"{sid}.mp4")))
            # a spoken line edited after the run: what the run sent no longer matches the plan
            i, talker = next((i, s) for i, s in enumerate(self.plan["shots"]) if eb.plan_check.speaking(s)
                             and eb.plan_check.talking(s))
            edited = copy.deepcopy(self.plan)
            edited["shots"][i]["line"] = talker["line"] + " Amen"
            with self.assertRaises(SystemExit) as err:
                eb.adopt_step(edited, run, "py", "model", out, ids, "40460764662", sheet=lambda video, sheet: None)
            self.assertEqual(str(err.exception).split(" (")[0], f"SHOT_REQUEST_CHANGED {talker['id']}")
            # a prompt edited after the run
            older = json.loads((run / "report.json").read_text())
            older["shots"][sid]["request"]["prompt"] = "an older prompt"
            (run / "report.json").write_text(json.dumps(older))
            with self.assertRaises(SystemExit) as err:
                eb.adopt_step(self.plan, run, "py", "model", out, ids, "40460764662", sheet=lambda video, sheet: None)
            self.assertEqual(str(err.exception).split(" (")[0], f"SHOT_REQUEST_CHANGED {sid}")
        finally:
            eb.ref_paths = saved
            for wav in made:
                wav.unlink(missing_ok=True)

    def test_regenerate_is_refused_whatever_it_names(self):
        # E114: the build generates nothing; a rejected clip is replaced by shot-probe.yml and a new approval
        plan = dialogue_plan()
        self.assertEqual(eb.regenerate_ids(plan, " ", "123456789"), [])
        for text in ("s-a", "s-a,s-god", "$(id)"):
            with self.assertRaises(SystemExit) as err:
                eb.regenerate_ids(plan, text, "123456789")
            self.assertTrue(str(err.exception).startswith("SHOT_APPROVED_USE_PROBE"), err.exception)
        with tempfile.TemporaryDirectory() as d:                 # the CLI step episode.yml runs before any secret
            path = Path(d) / "plan.json"
            path.write_text(json.dumps(plan))
            env = dict(os.environ, REGENERATE="s-a", RESUME_RUN="123456789")
            r = subprocess.run([sys.executable, "-I", "-B", str(HERE / "episode_build.py"), "check-regenerate", str(path)],
                               capture_output=True, text=True, env=env)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("SHOT_APPROVED_USE_PROBE", r.stderr)

    def test_episode_yml_passes_regenerate_through_the_env_and_checks_it_first(self):
        wf = (HERE.parents[2] / ".github" / "workflows" / "episode.yml").read_text()
        self.assertIn("      regenerate:\n", wf)
        self.assertIn("      REGENERATE: ${{ inputs.regenerate }}\n", wf)
        self.assertIn("      RESUME_RUN: ${{ inputs.resume_run }}\n", wf)
        for line in wf.splitlines():   # never expanded inline in a script
            if "inputs.regenerate" in line:
                self.assertTrue(line.strip().startswith("REGENERATE: ${{"), line)
        plan_step = wf.split("- id: plan", 1)[1].split("\n      - ", 1)[0]
        self.assertLess(plan_step.index("verify-preflight"), plan_step.index("episode_build.py check-regenerate"))
        self.assertNotIn("secrets.", plan_step)

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
        self.assertEqual(client.calls[2]["prompt"], f"storm {PERIOD}")
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
            # plan B: a voice-over Keeper shot also gets his talking frame (the still-mouth check needs his face)
            vo = eb.refs_step({"shots": [{"id": "k", "kind": "keeper", "voiceover": True, "lines": [0]}]}, work)
            self.assertEqual(sorted(vo), ["keeper", "keeper:talk"])
            # review of #423: without a talking frame it is refused, never generated from the front view
            chars = copy.deepcopy(eb.ch.registry())
            chars["keeper"].pop("talk_refs")
            with self.assertRaises(SystemExit) as err:
                eb.refs_step({"shots": [{"id": "k", "kind": "keeper", "voiceover": True, "lines": [0]}]}, work,
                             chars=chars)
            self.assertIn("KEEPER_VO_NO_TALK_REF", str(err.exception))
            self.assertEqual(sorted(eb.refs_step({"shots": [{"id": "k", "kind": "keeper", "lines": [0]}]}, work,
                                                 chars=chars)), ["keeper"])   # a talking Keeper: his kept refs
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


VO_EXAMPLE = json.loads((HERE / "plans" / "genesis-07-short.json").read_text())


def vo_dialogue_plan():
    p = dialogue_plan()
    p["shots"][-1].update(voiceover=True, prompt="Medium close-up, static camera. The narrator looks into the fire, his "
                                                  "lips closed, silent.")
    return p


class KeeperVoiceover(unittest.TestCase):
    """Plan B (owner, 2026-10-26): a `"voiceover": true` Keeper shot sends his talking-frame reference and no audio,
    binds no speech, is checked for a still mouth (lipsync_check --still-mouth) and plays his line from the voice
    track."""

    def test_the_request_sends_the_reference_whose_clips_show_his_face_and_no_audio_or_speech(self):
        # keeper-vo/calibration.json: with the mouth-closed front view the face was found in 2-27 % of the frames (4 of
        # 4 FACE_NOT_FOUND); with the talking frame, facing the lens, in 100 %. No talking frame: refused, never the
        # front view in its place (review of #423)
        with self.assertRaises(SystemExit) as err:
            eb.request(VO_EXAMPLE["shots"][-1], len(VO_EXAMPLE["shots"]) - 1, VO_EXAMPLE,
                       layout_for(VO_EXAMPLE, DURATIONS), {"keeper": ["front.jpg"]})
        self.assertIn("KEEPER_VO_NO_TALK_REF", str(err.exception))
        layout = layout_for(VO_EXAMPLE, DURATIONS)
        refs = {"keeper": [".episode/x/refs/ch-keeper-front.jpg"], "keeper:talk": [".episode/x/refs/ch-keeper-talk.jpg"]}
        shots = VO_EXAMPLE["shots"]
        for i, s in enumerate(shots):
            if s["kind"] != "keeper":
                continue
            r = eb.request(s, i, VO_EXAMPLE, layout, refs)
            self.assertEqual(r["references"], refs["keeper:talk"], s["id"])   # the frame whose clips show his face
            self.assertIsNone(r["audios"], s["id"])
            self.assertEqual(r["prompt"], s["prompt"], s["id"])             # no "Image 1 is", no "speaks the words"
            self.assertFalse(r["sound"])
            covered = eb.plan_check.vo_covered(layout["keeper"][s["id"]]["seconds"], shots, i)
            self.assertEqual(r["seconds"], eb.plan_check.vo_clip_seconds(covered))
        self.assertEqual(eb.request(shots[-1], len(shots) - 1, VO_EXAMPLE, layout, refs)["seconds"], 8)   # 6.54 + 1.2

    def test_after_a_talking_shot_the_clip_also_covers_the_gap_before_his_line(self):
        """Review of #423: plan_check, lines_step, shot_seconds and compose_shots share plan_check.vo_cover."""
        p = vo_dialogue_plan()
        p["narration"].insert(1, {"kind": "insight", "text": "x y z"})
        p["shots"].insert(3, {"id": "k-talk", "kind": "keeper", "lines": [1], "prompt": "k"})
        p["shots"][-1]["lines"] = [2]
        lay = layout_for(p, [2.4, 3.0, 4.55, 2.5, 6.6])
        refs = {"keeper": ["k.jpg"], "keeper:talk": ["k-talk.jpg"], "eve": ["eve.jpg"]}
        self.assertEqual(eb.plan_check.vo_cover(p["shots"], 4), (eb.LINE_GAP, eb.TAIL))
        r = eb.request(p["shots"][4], 4, p, lay, refs)
        self.assertEqual(r["seconds"], 9)          # ceil(0.35 + 6.6 + 1.2 = 8.15): 8 s would miss the gap before
        clips = {s["id"]: f"{s['id']}.mp4" for s in p["shots"]}
        seconds = {"s-eve": 4.59, "s-a": 6.59, "s-god": 8.59, "k-talk": 5.0, "k-close": float(r["seconds"])}
        shots = eb.compose_shots(p, lay, clips, seconds)
        self.assertEqual(short_engine.check_shots(shots, lay["total"]), [])
        vo = [c for c in shots if c["shot"] == "k-close"][0]
        line = lay["keeper"]["k-close"]
        self.assertAlmostEqual(vo["start"], line["start"] - eb.LINE_GAP, places=3)
        self.assertAlmostEqual(vo["end"], lay["total"], places=3)
        self.assertEqual(vo["speed"], 1.0)

    def test_every_scene_and_god_request_keeps_the_talking_plans_seconds_and_references(self):
        # E108: every scene prompt of genesis-07 changed (the period, and the rewritten shots); with the same prompt
        # the voice-over plan's request is the talking plan's, byte for byte: seconds, references and audio unchanged
        refs = {"keeper": ["k.jpg"], "keeper:talk": ["k-talk.jpg"]}
        base, vo = layout_for(EXAMPLE, DURATIONS), layout_for(VO_EXAMPLE, DURATIONS)
        same = 0
        for i, (a, b) in enumerate(zip(EXAMPLE["shots"], VO_EXAMPLE["shots"])):
            if a["kind"] == "scene":
                self.assertEqual(eb.request(a, i, EXAMPLE, base, refs), eb.request(b, i, VO_EXAMPLE, vo, refs), a["id"])
                same += 1
        self.assertEqual(same, 30)

    def test_the_still_mouth_check_runs_on_voiceover_keeper_clips_only(self):
        p = vo_dialogue_plan()
        order = [s["id"] for _, s in eb.risk_order(p["shots"])]
        self.assertEqual(order, ["s-eve", "s-god", "k-close", "s-a"])      # a check that can fail: before the scenes
        # 1 pass in 6 direct closed-mouth clips: 3 generations would lose the run; Pavo is free, so 6 like a talking shot
        self.assertEqual(eb.attempts_for(p["shots"][-1]), eb.TALK_ATTEMPTS)
        self.assertEqual(eb.attempts_for(p["shots"][1]), eb.ATTEMPTS)
        self.assertTrue(all(eb.attempts_for(s) == eb.TALK_ATTEMPTS for s in VO_EXAMPLE["shots"] if s["kind"] == "keeper"))

    def test_the_layout_counts_his_share_and_writes_no_input_audio(self):
        p = vo_dialogue_plan()
        lay = layout_for(p, [2.4, 3.0, 2.5, 3.1])
        self.assertNotIn("wav", lay["keeper"]["k-close"])
        self.assertTrue(lay["keeper"]["k-close"]["voiceover"])

    def test_compose_plays_his_line_from_the_voice_track_over_one_unbroken_clip(self):
        layout = layout_for(VO_EXAMPLE, DURATIONS)
        clips = {s["id"]: f"{s['id']}.mp4" for s in VO_EXAMPLE["shots"]}
        seconds = {s["id"]: (s.get("seconds") or 12) + 0.59 for s in VO_EXAMPLE["shots"]}
        for i, s in enumerate(VO_EXAMPLE["shots"]):
            if s["kind"] == "keeper":
                covered = eb.plan_check.vo_covered(layout["keeper"][s["id"]]["seconds"], VO_EXAMPLE["shots"], i)
                seconds[s["id"]] = float(eb.plan_check.vo_clip_seconds(covered))
        shots = eb.compose_shots(VO_EXAMPLE, layout, clips, seconds)
        self.assertEqual(short_engine.check_shots(shots, layout["total"]), [])
        sentences = [{"start": x["start"], "end": x["end"]} for x in layout["lines"]]
        self.assertEqual(short_engine.talk_problems(shots, sentences), [])
        vo = [c for c in shots if c["shot"].startswith("k-")]
        self.assertEqual([c["shot"] for c in vo], ["k-insight", "k-question", "k-close"])   # one piece each, no cuts
        ends = {"k-insight": layout["keeper"]["k-question"]["start"], "k-question": layout["keeper"]["k-close"]["start"],
                "k-close": layout["total"]}
        for c in vo:
            line = layout["keeper"][c["shot"]]
            self.assertEqual(c["kind"], "keeper-vo")
            self.assertNotIn("talk", c)                       # no lips to align: the line is narration in the mix
            self.assertNotIn("hold", c)
            self.assertAlmostEqual(c["start"], line["start"], places=3)
            self.assertAlmostEqual(c["end"], ends[c["shot"]], places=3)
            self.assertEqual((c["src_start"], c["speed"]), (0.0, 1.0))
            self.assertIsNotNone(short_engine.explicit_speed(c, seconds[c["shot"]]))
        # a clip shorter than its span is slowed at most 1.3, else refused
        slow = eb.compose_shots(VO_EXAMPLE, layout, clips, dict(seconds, **{"k-close": 6.5}))
        c = [x for x in slow if x["shot"] == "k-close"][0]
        self.assertTrue(1.0 < c["speed"] <= eb.MAX_SLOW)
        self.assertIsNotNone(short_engine.explicit_speed(c, 6.5))
        with self.assertRaises(SystemExit) as err:
            eb.compose_shots(VO_EXAMPLE, layout, clips, dict(seconds, **{"k-close": 4.0}))
        self.assertIn("KEEPER_CLIP_SHORT k-close", str(err.exception))

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
    def test_lines_step_caps_the_gap_before_his_line_and_the_tail_after_it(self):
        """Review of #423: the line alone was held to VO_LINE_MAX (15.6 s); after a talking shot the clip also covers
        the 0.35 s gap before it and the 1.2 s tail after it (14.5 + 1.55 = 16.05 s)."""
        work = Path(tempfile.mkdtemp(dir=eb.REPO / ".episode" if (eb.REPO / ".episode").is_dir() else eb.REPO,
                                     prefix="test-vo-cap-"))
        try:
            plan = {"shots": [{"id": "s-a", "kind": "scene", "lines": [0]},
                              {"id": "k-talk", "kind": "keeper", "lines": [1]},
                              {"id": "k-close", "kind": "keeper", "voiceover": True, "lines": [2]}],
                    "narration": [{"text": "a"}, {"text": "b"}, {"text": "c"}]}
            tone_wav(work / "voice.wav", 90.0)
            spans = [(0.3, 60.0), (60.18, 66.73), (66.91, 81.41)]
            (work / "timeline.json").write_text(json.dumps({"sentences": [
                {"segment": f"n{k:02d}", "text": "x.", "start": a, "end": b} for k, (a, b) in enumerate(spans)]}))
            with self.assertRaises(SystemExit) as err:
                eb.lines_step(plan, work)
            self.assertIn("KEEPER_AUDIO k-close", str(err.exception))
        finally:
            shutil.rmtree(work)

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
    def test_lines_step_neither_retimes_nor_cuts_input_audio_for_his_line_and_captions_follow(self):
        work = Path(tempfile.mkdtemp(dir=eb.REPO / ".episode" if (eb.REPO / ".episode").is_dir() else eb.REPO,
                                     prefix="test-vo-lines-"))
        try:
            plan = {"shots": [{"id": "k-open", "kind": "keeper", "lines": [0]},
                              {"id": "s-a", "kind": "scene", "lines": [1]},
                              {"id": "k-close", "kind": "keeper", "voiceover": True, "lines": [2]}],
                    "narration": [{"text": "a"}, {"text": "b"}, {"text": "c"}]}
            tone_wav(work / "voice.wav", 70.0)
            # k-close 3.30 s would be retimed to 3.55 s as a talking line; as a voice-over it stays 3.30 s
            spans = [(0.3, 6.85), (7.03, 30.0), (30.18, 60.0), (60.18, 63.48)]
            (work / "timeline.json").write_text(json.dumps({"sentences": [
                {"segment": g, "text": f"{g}.", "start": a, "end": b}
                for g, (a, b) in zip(["n00", "n01", "n01", "n02"], spans)]}))
            result = eb.lines_step(plan, work)
            self.assertNotIn("k-close", result["retimed"])
            k = result["keeper"]["k-close"]
            self.assertAlmostEqual(k["seconds"], 3.3, places=2)
            self.assertTrue(k["voiceover"])
            self.assertNotIn("wav", k)
            self.assertFalse((work / "keeper" / "k-close.wav").exists())
            self.assertTrue((work / "keeper" / "k-open.wav").exists())        # the default Keeper still talks
            self.assertAlmostEqual(result["keeper_share"],
                                   (result["keeper"]["k-open"]["seconds"] + k["seconds"]) / result["total"], places=2)
            timeline = json.loads((work / "compose-timeline.json").read_text())
            last = timeline["sentences"][-1]                                  # his caption sits on his line
            self.assertEqual(last["segment"], "n02")
            self.assertAlmostEqual(last["start"], k["start"], places=2)
            self.assertAlmostEqual(last["end"], k["end"], places=2)
            self.assertNotIn("speaker", last)
        finally:
            shutil.rmtree(work)


class StillMouthGate(unittest.TestCase):
    """generate_clips (shot-probe.yml's engine) on a voice-over Keeper shot: Pavo's audio stripped, no lipsync, the still-mouth check instead;
    MOUTH_TALKING is a failed generation (regenerated at most twice); a broken check stops the run."""
    def setUp(self):
        self.saved = (eb.clip_flags, eb.lipsync_flags, eb.face_flags, eb.still_mouth_flags, eb.run)
        self.work = Path(tempfile.mkdtemp(dir=eb.REPO, prefix=".test-still-"))
        self.plan = vo_dialogue_plan()
        (self.work / "layout.json").write_text(json.dumps(layout_for(self.plan, [2.4, 3.0, 2.5, 3.1])))
        (self.work / "refs.json").write_text(json.dumps({"keeper": ["k.jpg"], "keeper:talk": ["k-talk.jpg"],
                                                         "eve": ["eve.jpg"]}))
        self.lip, self.still, self.stripped = [], [], []
        eb.clip_flags = lambda path, aspect=None: []
        eb.lipsync_flags = lambda py, model, clip, wav: (self.lip.append(Path(clip).name) or [],
                                                         {"audio": {"corr": 0.9}, "mouth": {"corr": 0.5}})
        eb.face_flags = lambda py, model, clip: ([], {"faces": {"frames_sampled": 40, "faces_found": 0}})
        eb.still_mouth_flags = lambda py, model, clip: (self.still.append(Path(clip).name) or [],
                                                        {"still_mouth": {"opening_range": 0.01, "face_frames": 0.95}})
        eb.run = lambda args, **kw: (self.stripped.append(Path(str(args[-1])).name),
                                     Path(str(args[-1])).write_bytes(b"v"))

    def tearDown(self):
        eb.clip_flags, eb.lipsync_flags, eb.face_flags, eb.still_mouth_flags, eb.run = self.saved
        shutil.rmtree(self.work)

    def generate(self, extra=0):
        n = len(self.plan["shots"]) + extra
        client = FakeClient([{"conversation_id": str(i), "status": "submitted"} for i in range(n)],
                            {str(i): [done(str(i))] for i in range(n)})
        report = eb.generate_clips(self.plan, self.work, "py", "model", client=client,
                                   download=lambda url, dst: Path(dst).write_bytes(b"raw"), sleep=lambda s: None)
        return client, report

    def test_a_voiceover_clip_is_still_mouth_checked_never_lip_checked_and_loses_pavos_audio(self):
        client, report = self.generate()
        self.assertEqual(self.lip, ["s-eve.mp4"])
        self.assertEqual(self.still, ["k-close.mp4"])
        self.assertIn("k-close.mp4", self.stripped)
        k = [c for c in client.calls if c["prompt"] == self.plan["shots"][-1]["prompt"]][0]
        self.assertEqual((k["references"], k["audios"]), (["k-talk.jpg"], None))
        self.assertEqual(report["shots"]["k-close"]["attempts"][0]["still_mouth"]["opening_range"], 0.01)

    def test_a_talking_mouth_is_regenerated_at_most_five_times_then_the_run_stops(self):
        seen = []
        eb.still_mouth_flags = lambda py, model, clip: (seen.append(clip) or ["MOUTH_TALKING"],
                                                        {"still_mouth": {"opening_range": 0.09}})
        with self.assertRaises(SystemExit) as err:
            self.generate(extra=eb.TALK_ATTEMPTS - 1)
        self.assertIn(f"SHOT_FAILED k-close after {eb.TALK_ATTEMPTS} generations: MOUTH_TALKING", str(err.exception))
        self.assertEqual(len(seen), eb.TALK_ATTEMPTS)

    def test_a_broken_still_mouth_check_stops_the_run_and_spends_no_regeneration(self):
        fake = self.work / "python"
        fake.write_text("#!/bin/sh\necho 'ImportError: libEGL.so.1' >&2\nexit 1\n")
        fake.chmod(0o755)
        with self.assertRaises(SystemExit) as caught:
            self.saved[3](fake, "model.task", "clip.mp4")
        self.assertIn("STILL_MOUTH_TOOL_BROKEN exit 1", str(caught.exception))
        calls = []

        def attempt(n):
            calls.append(n)
            return {"generation": n}, self.work / "clip.mp4"
        with self.assertRaises(SystemExit):
            eb.make_shot("k-close", attempt, lambda path: self.saved[3](fake, "model.task", path))
        self.assertEqual(calls, [1])

    def test_the_still_mouth_command_line(self):
        seen = []
        orig = eb.subprocess.run

        class Done:
            stdout = json.dumps({"flags": [], "opening_range": 0.012, "opening_motion": 0.0006, "window_motion": 0.0021,
                                 "closed_opening": 0.0024, "face_frames": 0.97, "frames": 200}) + "\n"
            stderr, returncode = "", 0
        eb.subprocess.run = lambda args, **kw: (seen.append(args), Done())[1]
        try:
            flags, measures = self.saved[3]("py", "model.task", "clip.mp4")
        finally:
            eb.subprocess.run = orig
        self.assertEqual(seen[0][1:4], ["-I", "-B", str(eb.HERE / "lipsync_check.py")])
        self.assertEqual(seen[0][4:], ["--still-mouth", "clip.mp4", "model.task"])
        self.assertEqual((flags, measures["still_mouth"]["opening_range"]), ([], 0.012))
        # review of #423: every measure the verdict uses reaches report.json
        self.assertEqual(measures["still_mouth"], {"opening_range": 0.012, "opening_motion": 0.0006,
                                                   "window_motion": 0.0021, "closed_opening": 0.0024,
                                                   "face_frames": 0.97, "frames": 200})


class Workflow(unittest.TestCase):
    """episode.yml holds PAVO_TOKEN: manual runs of main only, the secret in one step, inputs only through env."""
    def test_the_secret_stays_in_one_step_of_a_main_only_manual_run(self):
        import re
        text = (eb.REPO / ".github" / "workflows" / "episode.yml").read_text()
        jobs = text.split("\n  record:\n")
        build, record = jobs[0], jobs[1]
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", build)
        self.assertEqual(text.count("secrets."), 0)    # E114: the build generates nothing and holds no Pavo secret
        self.assertIn("persist-credentials: false", build)
        # the Pavo secret lives in shot-probe.yml's one generation step, a main-only manual run, never its record job
        probe = (eb.REPO / ".github" / "workflows" / "shot-probe.yml").read_text()
        pjob, precord = probe.split("\n  record:\n")
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", pjob)
        self.assertEqual(probe.count("secrets."), 1)
        self.assertNotIn("secrets.", precord)
        step = [s for s in pjob.split("\n      - ") if "secrets.PAVO_TOKEN" in s][0]
        self.assertIn("episode_build.py probe ", step)
        self.assertIn("if: inputs.adopt_run == ''", step)
        self.assertIn("persist-credentials: false", pjob)
        for block in re.findall(r"run: \|\n((?:          .*\n?)+)", probe):
            self.assertNotIn("${{", block)
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


class GuardedFake(FakeClient):
    """FakeClient behind the real quota guard, as PavoVideoClient wires it (E128): before_generate before the quote,
    submitted once a conversation exists, read_back on every job read."""
    def __init__(self, guard, submissions, jobs):
        super().__init__(submissions, jobs)
        self.guard = guard

    def generate_video(self, **req):
        import quota
        self.guard.before_generate(quota.VIDEO_UNITS)
        result = super().generate_video(**req)
        self.guard.submitted(result["conversation_id"], quota.VIDEO_UNITS)
        return result

    def job(self, cid):
        result = super().job(cid)
        self.guard.read_back(cid, result["status"], result.get("videos") or [])
        return result


class SharedQuotaStop(unittest.TestCase):
    """E128: shot-probe run 40592173923 (arc-01-long, God's voice-overs) read back 3 clips, then submitted 24 more that
    all came back failed with no video (Pavo's free-model quota was spent; the quote still said 0): make_shot
    regenerated each failed clip and probe_step went on to the next shot. Now the run's client is guarded by a
    run-local ledger seeded with the day's units, two failed read-backs in a row stop the whole run, and the
    generations already spent stay in its record."""
    def setUp(self):
        self.saved = (eb.clip_flags, eb.lipsync_flags, eb.face_flags, eb.run, os.environ.get("PAVO_IMAGE_LEDGER"))
        self.work = Path(tempfile.mkdtemp(dir=eb.REPO, prefix=".test-quota-"))
        self.plan = dialogue_plan()
        (self.work / "layout.json").write_text(json.dumps(layout_for(self.plan, [2.4, 3.0, 2.5, 3.1])))
        (self.work / "refs.json").write_text(json.dumps({"keeper": ["k.jpg"], "eve": ["eve.jpg"]}))
        eb.clip_flags = lambda path, aspect=None: []
        eb.lipsync_flags = lambda py, model, clip, wav: ([], {"audio": {"corr": 0.9}, "mouth": {"corr": 0.5}})
        eb.face_flags = lambda py, model, clip: ([], {"faces": {"frames_sampled": 40, "faces_found": 0}})
        eb.run = lambda args, **kw: Path(str(args[-1])).write_bytes(b"v")

    def tearDown(self):
        eb.clip_flags, eb.lipsync_flags, eb.face_flags, eb.run, ledger = self.saved
        if ledger is None:
            os.environ.pop("PAVO_IMAGE_LEDGER", None)
        else:
            os.environ["PAVO_IMAGE_LEDGER"] = ledger
        shutil.rmtree(self.work)

    def test_two_failed_read_backs_stop_the_whole_probe_run(self):
        import quota
        ledger = eb.seed_budget(self.work, "0", main_ledger=self.work / "missing-main-ledger.json")
        n = 30
        failed = {"status": "failed", "videos": []}
        client = GuardedFake(quota.QuotaGuard(ledger, actions=None),
                             [{"conversation_id": str(373599328776227520 + i), "status": "submitted"} for i in range(n)],
                             {str(373599328776227520 + i): [dict(failed, conversation_id=str(373599328776227520 + i))]
                              for i in range(n)})
        out = self.work / "out"
        ids = [s["id"] for s in self.plan["shots"]]
        with self.assertRaises(SystemExit) as err:
            eb.probe_step(self.plan, self.work, "py", "model", out, ids, 2, client=client,
                          download=lambda url, dst: Path(dst).write_bytes(b"raw"), sleep=lambda s: None,
                          sheet=lambda video, sheet: None)
        self.assertTrue(str(err.exception).startswith("PAVO_FREE_QUOTA_SUSPECTED"), err.exception)
        self.assertEqual(len(client.calls), quota.FAILED_STREAK)          # 2 spent, not 24
        record = json.loads((out / "probe.json").read_text())
        spent = [g["conversation_id"] for e in record["shots"].values() for c in e["clips"] for g in c["generations"]]
        self.assertEqual(len(spent), quota.FAILED_STREAK)                  # the spent generations stay in the record
        self.assertIn("PAVO_FREE_QUOTA_SUSPECTED", record["stopped"])
        self.assertEqual(quota.record_usage(record), (2 * quota.VIDEO_UNITS, 2))   # what the next guard reads
        day = json.loads(ledger.read_text())["days"]
        self.assertEqual(sum(d["generated"] for d in day.values()), 2 * quota.VIDEO_UNITS)

    def test_the_run_ledger_is_seeded_from_the_guard_count_and_never_missing(self):
        import quota
        for used in ("", "x", "-1", None):
            with self.assertRaises(SystemExit) as err:
                eb.seed_budget(self.work, used)
            self.assertTrue(str(err.exception).startswith("PAVO_BUDGET_UNKNOWN"), err.exception)
        main = self.work / "main-ledger.json"
        main.write_text(json.dumps({"days": {"2026-10-27": {"generated": 251}}, "daily_cap": 300,
                                    "suspended_at": "2026-10-27T22:00:00+00:00",
                                    "suspended_until": "2026-10-28T01:00:00+00:00", "failed_streak": 2}))
        from datetime import datetime, timezone
        now = datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)
        ledger = eb.seed_budget(self.work, "305", main_ledger=main, now=now)
        seeded = json.loads(ledger.read_text())
        self.assertEqual(seeded["days"]["2026-10-27"]["generated"], 305)     # main's 251 + today's probe records
        self.assertEqual((seeded["daily_cap"], seeded["suspended_until"]), (300, "2026-10-28T01:00:00+00:00"))
        with self.assertRaisesRegex(PavoError, "PAVO_FREE_QUOTA_SUSPECTED"):
            quota.QuotaGuard(ledger, now=lambda: now).before_generate(quota.VIDEO_UNITS)
        os.environ.pop("PAVO_IMAGE_LEDGER", None)
        with self.assertRaises(SystemExit) as err:                           # never an unguarded client
            eb.budget_client()
        self.assertTrue(str(err.exception).startswith("PAVO_BUDGET_UNKNOWN"))
        os.environ["PAVO_IMAGE_LEDGER"] = str(ledger)
        self.assertEqual(eb.budget_client()._guard.path, ledger)
        import inspect
        self.assertIn("client = budget_client()", inspect.getsource(eb.generate_clips))
        self.assertNotIn("PavoVideoClient()", inspect.getsource(eb.generate_clips))

    def test_the_probe_command_seeds_the_budget_before_any_generation(self):
        text = (eb.HERE / "episode_build.py").read_text()
        start = text.index('elif cmd == "probe" and len(argv) == 7:')
        body = text[start:text.index("elif cmd ==", start + 10)]
        self.assertLess(body.index("seed_budget("), body.index("probe_step("))   # seeded before any generation
        wf = (eb.REPO / ".github" / "workflows" / "shot-probe.yml").read_text()
        self.assertIn("PAVO_BUDGET_USED: ${{ steps.guard.outputs.pavo_used }}", wf)


def native_plan():
    """The dialogue plan on Pavo's own speech (owner 27/10, R4): a Short that says so."""
    p = dialogue_plan()
    p["audio_route"] = "pavo_native"
    p["ambience"] = "the garden at dusk: a soft evening wind through the leaves"
    return p


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe")
class MediaTiming(unittest.TestCase):
    def test_e152_measured_bytes_not_requested_seconds_govern_native_coverage_and_queue(self):
        import long_preflight as lp
        root = eb.REPO / "migration" / "evidence" / "shots"
        with tempfile.TemporaryDirectory(prefix=".test-media-", dir=root) as d:
            d = Path(d)
            video = d / "native.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "testsrc2=size=160x90:rate=30:duration=2.3", "-f", "lavfi", "-i",
                            "sine=frequency=220:sample_rate=48000:duration=2.4", "-c:v", "libx264", "-pix_fmt",
                            "yuv420p", "-c:a", "aac", str(video)], check=True)
            p = native_plan()
            p["episode"] = "test-native-measured"
            p["shots"] = p["shots"][:1]
            sid, key = p["shots"][0]["id"], eb.sha256(video)
            a = {"clip_seconds": 1, "clip_sha256": key, "request_sha256": "request",
                 "speech": {"onset": 0.1, "end": 2.2, "gain_db": 0.0, "flags": []}}
            needs = eb.clip_needs(p, {}, approvals={sid: a})
            self.assertEqual(needs, {sid: 2.2})  # not ceil(Kokoro speech + generation padding)
            self.assertTrue(eb.coverage_problems(p, needs, {sid: a}))  # old nominal approval is too short
            before = copy.deepcopy(a)
            record = d / "probe.json"
            record.write_text(json.dumps({"episode": p["episode"], "shots": {sid: {"clips": [a]}}}))
            media_dir = d / "measurements" / p["episode"] / "media"
            media = eb.measure_clip_step(record, sid, video, media_dir)
            self.assertEqual(media["clip_sha256"], key)
            self.assertAlmostEqual(media["video_seconds"], 2.3, places=3)
            self.assertGreaterEqual(media["audio_seconds"], 2.4)
            with patch.object(eb.clip_timing, "RECORDS", d / "measurements"):
                self.assertEqual(eb.coverage_problems(p, needs, {sid: a}), [])
                queued = lp.queue(p, {sid: "request"}, {sid: a}, needs, max_units=400)
                self.assertEqual((queued["approved"], queued["to_probe"]), (1, 0))
                self.assertEqual(eb.native_spans(p, {sid: a})[sid][1:], (0.1, 2.2))
                outside = copy.deepcopy(a)
                outside["speech"]["end"] = 2.5
                with self.assertRaisesRegex(SystemExit, "NATIVE_SPEECH_OUTSIDE_MEDIA"):
                    eb.native_spans(p, {sid: outside})
                corrupt = dict(media, clip_sha256="0" * 64)
                eb.save(media_dir / f"{key}.json", corrupt)
                with self.assertRaisesRegex(SystemExit, "SHOT_MEDIA_UNMEASURED"):
                    eb.coverage_problems(p, needs, {sid: a})
            self.assertEqual(a, before)  # no rewritten historical approval, score, note, or speech endpoint
            with patch.object(eb.pavo_native, "premix") as premix:
                bad = copy.deepcopy(a)
                bad["speech"]["end"] = 2.5
                with self.assertRaisesRegex(SystemExit, "NATIVE_SPEECH_OUTSIDE_MEDIA"):
                    eb.native_voice(p, d, {"lines": [{"start": 0, "end": 2.4}], "total": 3.6},
                                    {sid: str(video)}, {sid: 2.3}, {sid: bad})
                premix.assert_not_called()  # an ASR timestamp beyond real media is not padded into speech
            with self.assertRaisesRegex(SystemExit, "SHOT_CLIP_NOT_IN_RECORD"):
                eb.measure_clip_step(record, "other-shot", video, d / "not-written")
            self.assertFalse((d / "not-written").exists())


class NativeSpeech(unittest.TestCase):
    """Owner 27/10 (R1, R2, R4): spoken shots keep Pavo's own speech and ambience on a plan that opts in; a line
    Pavo's prompt filter refuses goes to our Kokoro voice by itself (E129); a clip already made is never made again."""
    def setUp(self):
        import pavo_native
        import shot_sources
        self.pn, self.ss = pavo_native, shot_sources
        self.saved = (eb.clip_flags, eb.lipsync_flags, eb.face_flags, eb.run, pavo_native.BLOCKS, eb.own_track)
        self.work = Path(tempfile.mkdtemp(dir=eb.REPO, prefix=".test-native-"))
        pavo_native.BLOCKS = self.work / "prompt-blocks.json"
        pavo_native.BLOCKS.write_text(json.dumps({"words": ["naked"], "lines": []}))
        shot_sources._CACHE.clear()
        self.layout = layout_for(native_plan(), [2.4, 3.0, 2.5, 3.1])
        (self.work / "layout.json").write_text(json.dumps(self.layout))
        (self.work / "refs.json").write_text(json.dumps({"keeper": ["k.jpg"], "eve": ["eve.jpg"], "keeper:talk": ["kt.jpg"]}))
        self.refs = json.loads((self.work / "refs.json").read_text())
        self.lip = []
        eb.clip_flags = lambda path, aspect=None: []
        eb.lipsync_flags = lambda py, model, clip, wav: (self.lip.append(Path(wav).name) or [], {"audio": {}, "mouth": {}})
        eb.face_flags = lambda py, model, clip: ([], {"faces": {"frames_sampled": 40, "faces_found": 0}})
        eb.run = lambda args, **kw: Path(str(args[-1])).write_bytes(b"v")
        eb.own_track = lambda clip: Path(clip).with_suffix(".own.wav")

    def tearDown(self):
        eb.clip_flags, eb.lipsync_flags, eb.face_flags, eb.run, self.pn.BLOCKS, eb.own_track = self.saved
        self.ss._CACHE.clear()
        shutil.rmtree(self.work)

    def req(self, plan, sid):
        i = next(k for k, s in enumerate(plan["shots"]) if s["id"] == sid)
        return eb.request(plan["shots"][i], i, plan, self.layout, self.refs), eb.request_identity(
            plan["shots"][i], i, plan, self.layout, self.refs)

    def test_a_native_spoken_shot_asks_pavo_for_its_own_speech_and_ambience_no_music(self):
        native, kokoro = native_plan(), dialogue_plan()
        (req, (sha, canon)), (old, (old_sha, _)) = self.req(native, "s-eve"), self.req(kokoro, "s-eve")
        self.assertEqual((req["sound"], req["audios"]), (True, None))
        self.assertTrue(old["audios"] and old["sound"] is False)                 # the Kokoro route is unchanged
        self.assertIn('Eve says exactly these words and nothing else, once, in English: "Why do you hide?"',
                      req["prompt"])
        self.assertIn("the natural ambient sound of the garden at dusk", req["prompt"])
        self.assertNotIn("music", req["prompt"].lower())                         # excluded in positive words only
        self.assertNotIn(eb.BOUND_AUDIO.format(pronoun="her"), req["prompt"])    # no input audio to bind
        self.assertEqual(canon["audio"]["route"], "pavo_native")
        self.assertNotEqual(sha, old_sha)
        god, _ = self.req(native, "s-god")
        self.assertIn("off screen as a voice-over", god["prompt"])
        # a scene that speaks no line is generated exactly as before: its approval stays valid
        self.assertEqual(self.req(native, "s-a")[1][0], self.req(kokoro, "s-a")[1][0])

    def test_a_short_on_pavos_own_speech_is_refused_until_its_criteria_exist(self):
        # review of #476: no Short criteria file holds the speech-check rows yet, so the plan check refuses it
        found = [x.split()[0] for x in eb.plan_check.audio_route_problems(native_plan(), native_plan()["shots"])]
        self.assertEqual(found, ["AUDIO_ROUTE_SHORT_UNSUPPORTED"])
        # the build's own plan check (every build, probe and preflight command runs it first) refuses it
        self.assertTrue(any(x.startswith("AUDIO_ROUTE_SHORT_UNSUPPORTED")
                            for x in eb.check_plan(native_plan())["problems"]))
        p = native_plan()
        p["audio_route"] = "pavo"
        self.assertEqual([x.split()[0] for x in eb.plan_check.audio_route_problems(p, p["shots"])],
                         ["AUDIO_ROUTE_UNKNOWN"])
        self.assertEqual(eb.plan_check.audio_route_problems(dialogue_plan(), []), [])   # today's plans: untouched
        # and a v4 long that says "kokoro" keeps our voice
        self.assertTrue(self.pn.native_plan({"criteria": self.pn.V4}))
        self.assertFalse(self.pn.native_plan({"criteria": self.pn.V4, "audio_route": "kokoro"}))

    def test_e153_short_native_admission_uses_the_effective_route_not_only_an_explicit_flag(self):
        # A V4/V5 criteria selector enables native_plan even without audio_route. The Short's guard must use
        # that same resolver: removing the explicit flag cannot admit an unsupported native audio route.
        for version in (self.pn.V4, self.pn.V4X, self.pn.V5):
            for route in (None, self.pn.NATIVE):
                with self.subTest(criteria=version, route=route):
                    p = dialogue_plan()
                    p["criteria"] = version
                    if route is not None:
                        p["audio_route"] = route
                    self.assertTrue(self.pn.native_plan(p))
                    self.assertEqual([x.split()[0] for x in eb.plan_check.audio_route_problems(p, p["shots"])],
                                     ["AUDIO_ROUTE_SHORT_UNSUPPORTED"])
                    self.assertTrue(any(x.startswith("AUDIO_ROUTE_SHORT_UNSUPPORTED")
                                        for x in eb.check_plan(p)["problems"]))
            p["audio_route"] = self.pn.KOKORO
            self.assertFalse(self.pn.native_plan(p))
            self.assertEqual(eb.plan_check.audio_route_problems(p, p["shots"]), [])
        # Legacy Shorts still resolve to Kokoro, whether the field is absent or explicit.
        for route in (None, self.pn.KOKORO):
            p = dialogue_plan()
            if route is not None:
                p["audio_route"] = route
            self.assertFalse(self.pn.native_plan(p))
            self.assertEqual(eb.plan_check.audio_route_problems(p, p["shots"]), [])

    def test_e153_native_longs_keep_their_own_criteria_admission(self):
        import long_plan_check as lc
        import test_long_plan_check as fixture
        for version in (self.pn.V4, self.pn.V5):
            for route in (None, self.pn.NATIVE, self.pn.KOKORO):
                with self.subTest(criteria=version, route=route):
                    p = fixture.v4_plan()
                    p.update(criteria=version, episode=p["long"])
                    if route is not None:
                        p["audio_route"] = route
                    with patch.object(lc, "arcs", return_value=fixture.ARCS):
                        result = eb.check_plan(p, fixture.CHARS)
                    self.assertEqual(result["problems"], [])
                    self.assertEqual(self.pn.native_plan(p), route != self.pn.KOKORO)

    def probe(self, plan, ids, rounds, client):
        return eb.probe_step(plan, self.work, "py", "model", self.work / "out", ids, rounds, client=client,
                             download=lambda url, dst: Path(dst).write_bytes(b"raw"), sleep=lambda s: None,
                             sheet=lambda video, sheet: None)

    def test_a_prompt_block_stops_that_shot_for_the_rest_of_the_run(self):
        # review of #476: a blocked scene (or a blocked Kokoro-route shot) is never resubmitted with the same prompt
        client = FakeClient([{"conversation_id": "1", "status": "submitted"}],
                            {"1": [{"status": "blocked", "blocked_reason": "text_rejected_porn"}]})
        rec = self.probe(dialogue_plan(), ["s-a"], 3, client)
        self.assertEqual(len(client.calls), 1)                      # 3 rounds asked, one submission
        self.assertTrue(rec["shots"]["s-a"]["blocked"].startswith("PAVO_PROMPT_BLOCKED"))
        # a native line blocked, then blocked again on the Kokoro route: two submissions in all, never a third
        client = FakeClient([{"conversation_id": "3", "status": "submitted"}, {"conversation_id": "4",
                                                                               "status": "submitted"}],
                            {"3": [{"status": "blocked", "blocked_reason": "x"}],
                             "4": [{"status": "blocked", "blocked_reason": "x"}]})
        rec = self.probe(native_plan(), ["s-eve"], 3, client)
        self.assertEqual([c["sound"] for c in client.calls], [True, False])
        self.assertIn("blocked", rec["shots"]["s-eve"])

    def test_blocks_learned_in_actions_persist_with_the_record_and_bind_the_preflight(self):
        # review of #476: the block lives in the probe record; the record job merges it into prompt-blocks.json and
        # commits it, so the next run routes the line to Kokoro and the preflight (which binds the file) agrees
        import episode_preflight as pf
        plan = native_plan()
        client = FakeClient([{"conversation_id": "1", "status": "submitted"},
                             {"conversation_id": "2", "status": "submitted"}],
                            {"1": [{"status": "blocked", "blocked_reason": "text_rejected_porn"}], "2": [done("2")]})
        rec = self.probe(plan, ["s-eve"], 1, client)
        self.assertEqual(len(rec["prompt_blocks"]), 1)
        self.assertIsNone(rec["shots"]["s-eve"]["request"]["audio"].get("route"))   # recorded with the Kokoro request
        fresh = self.work / "main-blocks.json"                                      # main's file, in the record job
        fresh.write_text(json.dumps({"words": [], "lines": []}))
        self.pn.BLOCKS = fresh
        self.assertEqual(self.pn.route(plan, plan["shots"][0], 0), "pavo_native")
        (self.work / "plan.json").write_text(json.dumps(plan))
        before = pf.binding(self.work / "plan.json", plan)["prompt_blocks"]
        self.assertEqual(self.pn.merge_blocks(dict(rec, run_id="40600000000"), fresh),
                         [rec["prompt_blocks"][0]["line_sha256"]])
        self.assertEqual(self.pn.merge_blocks(rec, fresh), [])           # merged once
        odd = {"run_id": "1", "prompt_blocks": [{"line_sha256": "f" * 64, "shot": "$(x)\n", "reason": "a b",
                                                 "conversation_id": "1;rm"}]}
        self.pn.merge_blocks(odd, fresh)                                   # sweep H2: only plain ids are copied
        kept = json.loads(fresh.read_text())["lines"][-1]
        self.assertEqual((kept["shot"], kept["reason"], kept["conversation_id"]), ("", "unknown", ""))
        fresh.write_text(json.dumps({"words": [], "lines": json.loads(fresh.read_text())["lines"][:-1]}))
        self.assertEqual(self.pn.route(plan, plan["shots"][0], 0), "kokoro")   # the next run's route
        self.assertNotEqual(pf.binding(self.work / "plan.json", plan)["prompt_blocks"], before)   # preflight stale
        wf = (eb.REPO / ".github" / "workflows" / "shot-probe.yml").read_text()
        self.assertIn('merge-blocks "$d/$GITHUB_RUN_ID.json" migration/evidence/pavo/prompt-blocks.json', wf)
        self.assertIn('git add "$d" migration/evidence/pavo/prompt-blocks.json', wf)

    def test_e129_a_prompt_filter_block_is_surfaced_and_never_waited_out(self):
        c = FakeClient([], {"5": [{"status": "blocked", "code": "PAVO_PROMPT_BLOCKED",
                                   "blocked_reason": "text_rejected_porn"}]})
        with self.assertRaises(eb.ShotFailed) as err:
            eb.wait_job(c, "5", sleep=lambda s: self.fail("a block is not waited out"))
        self.assertEqual(str(err.exception), "PAVO_PROMPT_BLOCKED 5 text_rejected_porn")
        self.assertEqual(c.reads, ["5"])

    def test_e129_a_blocked_line_goes_to_kokoro_by_itself_and_stays_there(self):
        plan = native_plan()
        client = FakeClient([{"conversation_id": "1", "status": "submitted"},
                             {"conversation_id": "2", "status": "submitted"}],
                            {"1": [{"status": "blocked", "blocked_reason": "text_rejected_porn"}], "2": [done("2")]})
        report = eb.generate_clips(plan, self.work, "py", "model", ids=["s-eve"], client=client,
                                   download=lambda url, dst: Path(dst).write_bytes(b"raw"), sleep=lambda s: None)
        entry = report["shots"]["s-eve"]
        self.assertEqual((entry["route"], entry["prompt_blocked"]["reason"]), ("kokoro", "text_rejected_porn"))
        self.assertEqual([c["sound"] for c in client.calls], [True, False])      # Pavo's speech, then our voice
        self.assertTrue(client.calls[1]["audios"])
        self.assertEqual(len(client.calls), 2)                                   # the refused words never sent again
        self.assertEqual(self.pn.route(plan, plan["shots"][0], 0), "kokoro")     # learned for every later run
        # a word the filter is known to refuse never reaches Pavo's speech at all
        plan["shots"][0]["line"] = "I was naked; and I hid myself."
        self.pn.BLOCKS.write_text(json.dumps({"words": ["naked"], "lines": []}))
        self.assertFalse(self.req(plan, "s-eve")[0]["sound"])

    def test_r1_a_clip_already_made_keeps_its_route_and_is_never_made_again(self):
        plan = native_plan()
        kokoro_sha = self.req(dialogue_plan(), "s-god")[1][0]
        self.ss._CACHE[plan["episode"]] = {"s-god": [{"request_sha256": kokoro_sha, "from": "record"}]}
        req, (sha, _) = self.req(plan, "s-god")
        self.assertFalse(req["sound"])                          # God's existing clip is reused (R1 over R4)
        self.assertEqual(sha, kokoro_sha)
        self.assertTrue(self.req(plan, "s-eve")[0]["sound"])     # the others still get Pavo's speech

    def test_a_native_approval_ships_only_with_its_speech_checks_on_that_clip(self):
        self.assertEqual(eb.speech_record_flags({}, "a"), ["SPEECH_UNCHECKED"])
        ok = {"speech": {"clip_sha256": "a", "flags": [], "gain_db": 2.5}}
        self.assertEqual(eb.speech_record_flags(ok, "a"), [])
        self.assertEqual(eb.speech_record_flags(ok, "b"), ["SPEECH_UNCHECKED"])   # another clip
        bad = {"speech": {"clip_sha256": "a", "flags": ["VOICE_NOT_DISTINCT"], "gain_db": 2.5}}
        self.assertEqual(eb.speech_record_flags(bad, "a"), ["SPEECH_UNCHECKED"])

    def test_native_lines_take_their_clip_time_and_talking_cuts_start_at_the_speech(self):
        plan = native_plan()
        approvals = {"s-eve": {"speech": {"onset": 1.16, "end": 4.5, "gain_db": 1.0, "flags": []}}}
        spans = eb.native_spans(plan, approvals)
        self.assertEqual(spans, {"s-eve": ([0], 1.16, 4.5)})
        self.assertEqual(eb.native_spans(dialogue_plan(), approvals), {})          # v3 / Kokoro plans: unchanged
        cuts = eb.shift_onsets([{"shot": "s-eve", "talk": {}, "src_start": 0.0}, {"shot": "s-a", "src_start": 0.0}],
                               {"s-eve": 1.16, "s-a": 0.5})
        self.assertEqual([c["src_start"] for c in cuts], [1.16, 0.0])             # only a talking cut follows the lips


class VoiceBinding(unittest.TestCase):
    """Review of #476 (blocking): a native speech clip's voice is judged against exactly the reference voices.json
    holds for its speaker (by sha256; a caller's file never replaces it) and against every other speaker's reference;
    the reference itself is chosen by Claude's review through `episode_build.py voice-reference`, never by hand."""
    K, E, A = "k" * 64, "e" * 64, "a" * 64

    def setUp(self):
        import pavo_native
        self.pn = pavo_native
        self.saved = pavo_native.VOICES
        self.root = eb.REPO / "migration" / "evidence" / "shots"
        self.episode = f"t-voice-{os.getpid()}"
        self.dir = self.root / self.episode
        self.dir.mkdir(parents=True, exist_ok=True)
        self.out = Path(tempfile.mkdtemp(prefix="voice-"))
        self.voices = self.out / "voices.json"
        self.set_refs(keeper=self.K)
        pavo_native.VOICES = self.voices
        self.clip = "c" * 64
        self.record = self.dir / "40500000002.json"
        self.record.write_text(json.dumps({"episode": self.episode, "run_id": "40500000002", "shots": {"s-eve": {
            "request_sha256": "r", "clip_seconds": 6, "request": {"audio": {
                "route": "pavo_native", "speaker": "eve", "words": ["Why", "do", "you", "hide?"]}},
            "clips": [{"asset": "shot-x.mp4", "clip_sha256": self.clip, "flags": [], "uploaded": True,
                       "media": {"version": "clip-media-v1", "clip_sha256": self.clip,
                                 "video_seconds": 6.0, "audio_seconds": 6.0}}]}}}))

    def tearDown(self):
        self.pn.VOICES = self.saved
        shutil.rmtree(self.dir)
        shutil.rmtree(self.out)

    def set_refs(self, **refs):
        voices = {w: {"pavo_voice": f"{w}'s voice", "reference": None} for w in ("keeper", "god", "adam", "eve")}
        for who, sha in refs.items():
            voices[who]["reference"] = {"clip_sha256": sha}
        self.voices.write_text(json.dumps({"voices": voices}))

    def measures(self, reference=None, others=None, music=0.0):
        crit = self.pn.criteria()
        return {"asr": {"model_bin_sha256": crit["speech"]["asr_model"]["model_bin_sha256"], "text": "Why do you hide?",
                        "speech_span": [1.0, 3.0]},
                "voice": {"reference": reference or self.E, "same": 0.93, "others": [0.7] * len(others or [self.K]),
                          "others_references": others or [self.K]},
                "lufs": -24.0, "music": music, "singing": 0.0, "lips": []}

    def side(self, measures):
        (self.dir / "speech").mkdir(exist_ok=True)
        (self.dir / "speech" / f"{self.clip}.json").write_text(json.dumps({"measures": measures}))

    def approve(self):
        return eb.approve_shot(self.record, "s-eve", "shot-x.mp4", "9.6", "lips and voice clean", shots_dir=self.out, reviewer="claude-session-reviewer")

    def test_the_verdict_binds_the_speakers_reference_and_every_other_reference(self):
        line, ok = "Why do you hide?", {"reference": self.E, "others": [self.K]}
        self.assertEqual(self.pn.speech_verdict(self.measures(), line, binding=ok), [])
        cases = ((None, self.measures(), "VOICE_REFERENCE_MISSING"),                      # no reference recorded
                 ({"reference": self.A, "others": [self.K]}, self.measures(), "VOICE_REFERENCE_MISMATCH"),
                 ({"reference": self.E, "others": []}, self.measures(), "VOICE_OTHERS_MISSING"),   # distinct from none
                 (ok, dict(self.measures(), voice={"reference": self.E, "same": 0.93, "others": []}),
                  "VOICE_OTHERS_MISSING"),
                 ({"reference": self.E, "others": [self.A, self.K]}, self.measures(), "VOICE_OTHERS_MISMATCH"))
        for binding, m, flag in cases:
            self.assertEqual(self.pn.speech_verdict(m, line, binding=binding), [flag], flag)
        self.set_refs(keeper=self.K, eve=self.E, adam=self.A)
        self.assertEqual(self.pn.voice_binding("eve"), {"reference": self.E, "others": [self.A, self.K]})
        self.assertEqual(self.pn.voice_binding("god"), {"reference": None, "others": [self.A, self.E, self.K]})

    def test_a_reference_file_is_the_recorded_clip_or_refused(self):
        clip = self.out / "eve.mp4"
        clip.write_bytes(b"eve's reference clip")
        keeper = self.out / "keeper.mp4"
        keeper.write_bytes(b"the keeper")
        self.set_refs(keeper=eb.sha256(keeper), eve=eb.sha256(clip))
        both = {"eve": str(clip), "keeper": str(keeper)}
        self.assertEqual(eb.voice_references(both), both)
        other = self.out / "other.mp4"
        other.write_bytes(b"another voice")
        for given, code in (({"eve": str(other), "keeper": str(keeper)}, "VOICE_REFERENCE_FILE_MISMATCH"),
                            ({"eve": str(clip)}, "VOICE_REFERENCE_FILES_MISSING"),      # the others are measured
                            (dict(both, adam=str(other)), "VOICE_REFERENCE_UNSET")):
            with self.assertRaises(SystemExit) as err:
                eb.voice_references(given)
            self.assertTrue(str(err.exception).startswith(code), (code, str(err.exception)))

    def test_approve_shot_refuses_unchecked_or_failed_speech_and_binds_voices_json(self):
        with self.assertRaises(SystemExit) as err:
            self.approve()
        self.assertTrue(str(err.exception).startswith("SPEECH_UNCHECKED"))
        self.side(self.measures())
        with self.assertRaises(SystemExit) as err:                     # eve has no reference in voices.json yet
            self.approve()
        self.assertEqual(str(err.exception), "SPEECH_CHECKS_FAILED s-eve VOICE_REFERENCE_MISSING")
        self.set_refs(keeper=self.K, eve=self.A)                       # the sidecar was measured against another clip
        with self.assertRaises(SystemExit) as err:
            self.approve()
        self.assertEqual(str(err.exception), "SPEECH_CHECKS_FAILED s-eve VOICE_REFERENCE_MISMATCH")
        self.set_refs(keeper=self.K, eve=self.E, adam=self.A)          # adam's reference was not measured
        with self.assertRaises(SystemExit) as err:
            self.approve()
        self.assertEqual(str(err.exception), "SPEECH_CHECKS_FAILED s-eve VOICE_OTHERS_MISMATCH")
        self.set_refs(keeper=self.K, eve=self.E)
        self.side(self.measures(music=0.3))
        with self.assertRaises(SystemExit) as err:
            self.approve()
        self.assertEqual(str(err.exception), "SPEECH_CHECKS_FAILED s-eve PAVO_MUSIC")
        self.side(self.measures())
        self.assertEqual(self.approve()["speech"]["flags"], [])

    def test_voice_reference_records_a_reviewed_clips_sha256_by_command(self):
        def choose(score="9.6", note="one warm clear voice"):
            return eb.voice_reference_step(self.record, "s-eve", "shot-x.mp4", score, note, today="2026-10-28")
        with self.assertRaises(SystemExit) as err:
            choose()
        self.assertTrue(str(err.exception).startswith("SPEECH_UNCHECKED"))
        self.side(self.measures(music=0.3))
        with self.assertRaises(SystemExit) as err:                     # every check but the voice ones must pass
            choose()
        self.assertEqual(str(err.exception), "SPEECH_CHECKS_FAILED s-eve PAVO_MUSIC")
        self.side(self.measures())
        with self.assertRaises(SystemExit) as err:
            choose(score="9.4")
        self.assertTrue(str(err.exception).startswith("SHOT_SCORE_OUT_OF_RANGE"))
        ref = choose()
        self.assertEqual((ref["clip_sha256"], ref["shot"], ref["run_id"]), (self.clip, "s-eve", "40500000002"))
        self.assertEqual(self.pn.voice_reference("eve"), self.clip)       # copied from the record, never typed
        self.assertEqual(choose()["previous"]["clip_sha256"], self.clip)   # a replaced reference is kept
        kokoro = json.loads(self.record.read_text())
        kokoro["shots"]["s-eve"]["request"]["audio"]["route"] = None
        self.record.write_text(json.dumps(kokoro))
        with self.assertRaises(SystemExit) as err:
            choose()
        self.assertTrue(str(err.exception).startswith("VOICE_REFERENCE_NOT_NATIVE"))
        text = (eb.HERE / "episode_build.py").read_text()
        self.assertIn('cmd == "voice-reference"', text)
        self.assertIn("episode_build.py voice-reference", json.loads(self.saved.read_text())["about"])


class ProbeRecordOnAnyExit(unittest.TestCase):
    """Review of #475: a probe cancelled, timed out or crashed while a shot waited on Pavo lost that shot's submitted
    generations from out/probe.json, so the next dispatch guard under-counted the day's units."""
    setUp, tearDown = SharedQuotaStop.setUp, SharedQuotaStop.tearDown
    def run_until(self, interrupt):
        import quota
        ledger = eb.seed_budget(self.work, "0", main_ledger=self.work / "missing-main-ledger.json")
        cids = [str(373600000000000000 + i) for i in range(4)]
        client = GuardedFake(quota.QuotaGuard(ledger, actions=None),
                             [{"conversation_id": c, "status": "submitted"} for c in cids],
                             {cids[0]: [done(cids[0])], cids[1]: [interrupt]})
        out = self.work / "out"
        ids = [s["id"] for s in self.plan["shots"]]
        with self.assertRaises(type(interrupt)):
            eb.probe_step(self.plan, self.work, "py", "model", out, ids, 1, client=client,
                          download=lambda url, dst: Path(dst).write_bytes(b"raw"), sleep=lambda s: None,
                          sheet=lambda video, sheet: None)
        record = json.loads((out / "probe.json").read_text())
        spent = [g["conversation_id"] for e in record["shots"].values() for c in e["clips"] for g in c["generations"]]
        self.assertEqual(spent, cids[:2])                      # the one in flight is in the record too
        self.assertIn("PROBE_INTERRUPTED", [c.get("error") for e in record["shots"].values() for c in e["clips"]])
        self.assertEqual(quota.record_usage(record)[0], 2 * quota.VIDEO_UNITS)

    def test_a_cancel_keeps_the_in_flight_generation(self):
        self.run_until(KeyboardInterrupt())

    def test_a_terminate_or_crash_keeps_it_too(self):
        self.run_until(SystemExit("PROBE_TERMINATED (SIGTERM)"))
        text = (eb.HERE / "episode_build.py").read_text()
        self.assertIn("signal.signal(signal.SIGTERM", text)


@unittest.skipUnless(HAS_FFMPEG, 'ffmpeg required')
class ExistingEditImport(unittest.TestCase):
    def fixture(self, root):
        root.mkdir()
        plan = {"episode": "import-fixture", "narration": [{"kind": "cta", "text": "Keep the existing words."}],
                "shots": [{"id": "k-close", "kind": "keeper", "lines": [0], "prompt": "unchanged"}]}
        eb.save(root / "plan.json", plan)
        with wave.open(str(root / "narration.wav"), "wb") as f:
            f.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            f.writeframes(struct.pack('<h', 321) * 48000)
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(root / 'narration.wav'),
                        '-c:a', 'aac', str(root / 'mix.m4a')], check=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=32x48',
                        '-frames:v', '1', '-threads', '1', str(root / 'image.png')], check=True)
        (root / "captions.ass").write_text('[Script Info]\nScriptType: v4.00+\n'
                                          '[V4+ Styles]\nFormat: Name, Fontname, Fontsize\n'
                                          'Style: Default,DejaVu Sans,16\n[Events]\n'
                                          'Format: Layer, Start, End, Style, Text\n')
        manifest = {"status": "DRAFT_NOT_APPROVED", "narrator": "narration.wav", "ass": "captions.ass",
                    "reuse_existing_stills": True,
                    "audio_copy": {"source": "mix.m4a", "sha256": eb.sha256(root / "mix.m4a")},
                    "segments": [{"id": "k-close", "source": "image.png", "kind": "image", "seconds": 2,
                                  "sha256": eb.sha256(root / "image.png"), "crop": [0, 0, 16, 24]}]}
        eb.save(root / "manifest.json", manifest)
        def asset(name):
            return {"path": name, "sha256": eb.sha256(root / name)}
        binding = {"schema": "heroverse-existing-edit-v1", "episode": "import-fixture", "fps": 30, "frames": 60,
                   "plan": asset("plan.json"), "manifest": asset("manifest.json"),
                   "master_audio": asset("narration.wav"), "final_mix": asset("mix.m4a"),
                   "captions": asset("captions.ass"),
                   "visuals": [{"id": "k-close", "start_frame": 0, "end_frame": 60,
                                "logical_shots": [{"shot": "k-close", "start_frame": 0, "end_frame": 60}],
                                "narration_units": [{"kind": "cta", "voice": "am_michael",
                                                     "text": "Keep the existing words."}]}]}
        eb.save(root / "binding.json", binding)
        return plan, binding

    def test_e224_existing_master_is_preserved_and_lines_cannot_rebuild_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, work = Path(tmp, "source"), Path(tmp, "imported")
            plan, binding = self.fixture(root)
            result = eb.import_edit_step(root / "binding.json", root, work)
            self.assertEqual(result["status"], "IMPORTED_NOT_APPROVED")
            self.assertEqual(result["frames"], 60)
            self.assertEqual(result["seconds"], 2)
            self.assertTrue(result["plan_blockers"])
            self.assertEqual((work / "narration.wav").read_bytes(), (root / "narration.wav").read_bytes())
            with wave.open(str(work / "keeper" / "k-close.wav"), 'rb') as clip:
                self.assertEqual(clip.readframes(48000), struct.pack('<h', 321) * 48000)
            self.assertEqual(eb.load(work / "manifest.json")["segments"][0]["crop"], [0, 0, 16, 24])
            with self.assertRaisesRegex(SystemExit, "EXISTING_EDIT_IMMUTABLE"):
                eb.lines_step(plan, work)
            for command in ('voice-script', 'lines', 'generate', 'probe', 'compose', 'adopt'):
                with self.subTest(command=command), self.assertRaisesRegex(SystemExit, 'EXISTING_EDIT_IMMUTABLE'):
                    eb.main(['episode_build.py', command, str(root / 'plan.json'), str(work)])
            self.assertEqual((work / "narration.wav").read_bytes(), (root / "narration.wav").read_bytes())
            self.assertFalse((work / "APPROVAL.json").exists())
            self.assertFalse((work / "layout.json").exists())
            self.assertEqual(eb.import_edit_step(root / "binding.json", root, work), result)

    def test_import_refuses_changed_bytes_semantics_frames_and_paths_before_writes(self):
        cases = ("hash", "text", "gap", "duration", "escape", "symlink", "bool", "nan", "non_aac")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root, work = Path(tmp, "source"), Path(tmp, "imported")
                _, binding = self.fixture(root)
                if case == "hash":
                    binding["master_audio"]["sha256"] = "0" * 64
                elif case == "text":
                    binding["visuals"][0]["narration_units"][0]["text"] = "Different words."
                elif case == "gap":
                    binding["visuals"][0]["start_frame"] = 1
                elif case == "duration":
                    binding["frames"] = 61
                elif case == "escape":
                    binding["master_audio"]["path"] = "../source/narration.wav"
                elif case == "symlink":
                    (root / "alias.wav").symlink_to(root / "narration.wav")
                    binding["master_audio"]["path"] = "alias.wav"
                elif case == "bool":
                    binding["frames"] = True
                elif case == "nan":
                    manifest = eb.load(root / 'manifest.json')
                    manifest['segments'][0]['seconds'] = float('nan')
                    eb.save(root / 'manifest.json', manifest)
                    binding['manifest']['sha256'] = eb.sha256(root / 'manifest.json')
                elif case == 'non_aac':
                    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(root / 'narration.wav'),
                                    '-c:a', 'alac', str(root / 'mix.m4a')], check=True)
                    binding['final_mix']['sha256'] = eb.sha256(root / 'mix.m4a')
                    manifest = eb.load(root / 'manifest.json')
                    manifest['audio_copy']['sha256'] = binding['final_mix']['sha256']
                    eb.save(root / 'manifest.json', manifest)
                    binding['manifest']['sha256'] = eb.sha256(root / 'manifest.json')
                eb.save(root / "binding.json", binding)
                with self.assertRaises((ValueError, SystemExit)):
                    eb.import_edit_step(root / "binding.json", root, work)
                self.assertFalse(work.exists())

    def test_import_never_overwrites_partial_or_mutated_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, work = Path(tmp, "source"), Path(tmp, "imported")
            self.fixture(root)
            work.mkdir()
            (work / "narration.wav").write_bytes(b"unrelated")
            with self.assertRaisesRegex(ValueError, "EXISTING_EDIT_OUTPUT_EXISTS"):
                eb.import_edit_step(root / "binding.json", root, work)
            self.assertEqual((work / "narration.wav").read_bytes(), b"unrelated")
            other = Path(tmp, "complete")
            eb.import_edit_step(root / "binding.json", root, other)
            (other / "narration.wav").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "EXISTING_EDIT_OUTPUT_CHANGED"):
                eb.import_edit_step(root / "binding.json", root, other)

    def test_import_has_real_draft_consumer_with_identical_audio_packets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, work = Path(tmp, 'source'), Path(tmp, 'imported')
            self.fixture(root)
            eb.import_edit_step(root / 'binding.json', root, work)
            result = eb.existing_edit.render_imported(work, Path(tmp, 'draft.mp4'))
            self.assertEqual(result['validation']['video_frames'], 60)
            self.assertTrue(result['validation']['audio_packets_identical'])
            self.assertFalse(result['publication_approved'])
            with self.assertRaisesRegex(ValueError, 'EXISTING_EDIT_OUTPUT_OVERLAP'):
                eb.existing_edit.render_imported(work, work / 'narration.wav')

    def test_shared_narration_can_span_two_visuals_without_inventing_word_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, work = Path(tmp, 'source'), Path(tmp, 'imported')
            plan, binding = self.fixture(root)
            plan['shots'] = [{'id': sid, 'kind': 'scene', 'lines': [0], 'seconds': 1,
                              'characters': [], 'establishing': True, 'prompt': 'fixture'}
                             for sid in ('s-one', 's-two')]
            eb.save(root / 'plan.json', plan)
            binding['plan']['sha256'] = eb.sha256(root / 'plan.json')
            manifest = eb.load(root / 'manifest.json')
            manifest['segments'] = [dict(manifest['segments'][0], id=sid, seconds=1)
                                     for sid in ('s-one', 's-two')]
            eb.save(root / 'manifest.json', manifest)
            binding['manifest']['sha256'] = eb.sha256(root / 'manifest.json')
            binding['visuals'] = [dict(binding['visuals'][0], id=sid, start_frame=i*30, end_frame=(i+1)*30,
                                      logical_shots=[{'shot': sid, 'start_frame': i*30, 'end_frame': (i+1)*30}])
                                  for i, sid in enumerate(('s-one', 's-two'))]
            eb.save(root / 'binding.json', binding)
            result = eb.import_edit_step(root / 'binding.json', root, work)
            self.assertEqual(result['frames'], 60)
            self.assertIsNone(result['word_boundaries'])

    def test_e225_caption_or_manifest_change_after_verify_is_refused_at_consumption(self):
        for name in ('captions.ass', 'manifest.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root, work = Path(tmp, 'source'), Path(tmp, 'imported')
                self.fixture(root)
                eb.import_edit_step(root / 'binding.json', root, work)
                render = eb.existing_edit.dr.render
                def interleave(*args, **kwargs):
                    with (work / name).open('ab') as f:
                        f.write(b'\nchanged after verification\n')
                    return render(*args, **kwargs)
                with patch.object(eb.existing_edit.dr, 'render', side_effect=interleave):
                    with self.assertRaisesRegex(ValueError, 'HASH_MISMATCH'):
                        eb.existing_edit.render_imported(work, Path(tmp, 'draft.mp4'))
                self.assertFalse(Path(tmp, 'draft.mp4').exists())

    def test_keeper_slice_uses_nonzero_frame_offset_without_audio_retime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, work = Path(tmp, 'source'), Path(tmp, 'imported')
            plan, binding = self.fixture(root)
            pcm = struct.pack('<h', 321) * 24000 + struct.pack('<h', 987) * 24000
            with wave.open(str(root / 'narration.wav'), 'wb') as f:
                f.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                f.writeframes(pcm)
            binding['master_audio']['sha256'] = eb.sha256(root / 'narration.wav')
            plan['narration'].insert(0, {'kind': 'story', 'text': 'Earlier narration.'})
            plan['shots'][0]['lines'] = [1]
            plan['shots'].insert(0, {'id': 's-opening', 'kind': 'scene', 'lines': [0], 'seconds': 1,
                                      'characters': [], 'establishing': True, 'prompt': 'fixture'})
            eb.save(root / 'plan.json', plan)
            binding['plan']['sha256'] = eb.sha256(root / 'plan.json')
            manifest = eb.load(root / 'manifest.json')
            manifest['segments'] = [dict(manifest['segments'][0], id=sid, seconds=1)
                                     for sid in ('s-opening', 'k-close')]
            eb.save(root / 'manifest.json', manifest)
            binding['manifest']['sha256'] = eb.sha256(root / 'manifest.json')
            binding['visuals'] = [dict(binding['visuals'][0], id=sid, start_frame=i*30, end_frame=(i+1)*30,
                                      logical_shots=[{'shot': sid, 'start_frame': i*30, 'end_frame': (i+1)*30}],
                                      narration_units=[dict(plan['narration'][i], voice='am_michael')])
                                  for i, sid in enumerate(('s-opening', 'k-close'))]
            eb.save(root / 'binding.json', binding)
            result = eb.import_edit_step(root / 'binding.json', root, work)
            with wave.open(str(work / result['keeper']['k-close']['path']), 'rb') as f:
                self.assertEqual(f.getnframes(), 24000)
                self.assertEqual(f.readframes(24000), struct.pack('<h', 987) * 24000)

    def test_interrupted_receipt_write_still_blocks_voice_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, work = Path(tmp, 'source'), Path(tmp, 'imported')
            plan, _ = self.fixture(root)
            actual_open = Path.open
            def fail_receipt(path, *args, **kwargs):
                if path == work / 'existing-edit.json' and args == ('xb',):
                    raise OSError('synthetic receipt write failure')
                return actual_open(path, *args, **kwargs)
            with patch.object(Path, 'open', fail_receipt):
                with self.assertRaisesRegex(OSError, 'synthetic receipt'):
                    eb.import_edit_step(root / 'binding.json', root, work)
            before = (work / 'narration.wav').read_bytes()
            with self.assertRaisesRegex(SystemExit, 'EXISTING_EDIT_IMMUTABLE'):
                eb.lines_step(plan, work)
            self.assertEqual((work / 'narration.wav').read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
