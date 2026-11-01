#!/usr/bin/env python3
"""Offline checks of the cinematic still engine and its auto-director (motion.py; owner 2026-11-01, DECISIONS
"Cinematic still animation"; E261): every move renders smoothly with no edge shown, the director answers the beat,
emotion, span and picture, never repeats a move in a row, a plan override wins, the subject stays inside the centre
9:16 band the Shorts are cut from, the output is bit-exact, and the Short route keeps working."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "bible"))
sys.path.insert(0, str(HERE))
import motion as m  # noqa: E402
import plan_check as pc  # noqa: E402
import shot_sources as ss  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402

FFMPEG = shutil.which("ffmpeg") is not None
FRAME, SHORT = (320, 180), (180, 320)
SHORT_PLAN = HERE / "bible/plans/genesis-09-short.json"


def still(path, size=(640, 360), seed=3):
    """A textured test still (no black anywhere): sky gradient, ground, a centred figure."""
    w, h = size
    r = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = np.linspace(225, 90, h)[:, None, None].astype(np.uint8)
    img[int(h * 0.6):] = (60, 95, 125)
    img = cv2.add(img, cv2.GaussianBlur((r.random((h, w, 3)) * 70).astype(np.uint8), (0, 0), 2))
    cv2.circle(img, (w // 2, int(h * 0.45)), h // 8, (40, 60, 180), -1)
    cv2.imwrite(str(path), img)
    return path


def long_plan(n=28, seconds=16):
    """A long-first plan of n still scenes of `seconds`, words from the Genesis 7 Short."""
    base = json.loads(SHORT_PLAN.read_text())
    scenes = [s for s in base["shots"] if s["kind"] == "scene" and s.get("seconds")]
    shots = []
    for i in range(n):
        s = copy.deepcopy(scenes[i % len(scenes)])
        s.pop("lines", None)
        s.update(id=f"s-{i:02d}", seconds=seconds)
        shots.append(s)
    return dict(base, track="buzzy-long", aspect_ratio="16:9", shots=shots, narration=[], beats="")


def projected_band_ok(d, frame, steps=60):
    hb = m.band_half(frame)
    x0, _, x1, _ = d["subject"]
    for k in range(steps + 1):
        s, x, _ = m.camera(d["keys"], k / steps)
        if (x0 - x) * s < -hb - 1e-6 or (x1 - x) * s > hb + 1e-6:
            return False
    return True


class Moves(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.img = still(cls.tmp / "still.png")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_move_renders_smoothly_with_no_edge(self):
        for move in m.MOTIONS:
            d = m.direction_for(move, FRAME, 2.0, [])
            frames = list(m.Renderer(self.img, d, FRAME).frames(2.0))
            self.assertEqual(len(frames), 60, move)
            for f in frames[::10]:   # no black border: the still covers every edge
                self.assertGreater(min(f[0].mean(), f[-1].mean(), f[:, 0].mean(), f[:, -1].mean()), 30, move)
            path = np.array([m.camera(d["keys"], i / 59) for i in range(60)])
            jerk = np.abs(np.diff(path, 2, axis=0)).max(axis=0)
            self.assertLess(jerk[0], 0.004, move)   # scale: no step from one frame to the next
            self.assertLess(max(jerk[1] * FRAME[0], jerk[2] * FRAME[1]), 0.6, move)   # position: sub-pixel smooth
            if move not in m.TRIVIAL_MOTIONS:
                self.assertGreater(float(np.abs(frames[0].astype(int) - frames[-1].astype(int)).mean()), 0.5, move)

    def test_a_pan_moves_steadily_in_the_picture(self):
        d = m.direction_for("pan_right", FRAME, 2.0, [])
        g = [np.float32(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)) for f in m.Renderer(self.img, d, FRAME).frames(2.0)]
        dx = [cv2.phaseCorrelate(a, b)[0][0] for a, b in zip(g[20:40], g[21:41])]
        self.assertTrue(all(v < 0.05 for v in dx), dx)   # the picture slides one way only, no back-and-forth
        self.assertLess(max(abs(a - b) for a, b in zip(dx, dx[1:])), 0.35, dx)

    def test_every_atmosphere_renders(self):
        plain = next(m.Renderer(self.img, m.direction_for("push_in", FRAME, 1.0, []), FRAME).frames(1.0))
        for a in m.ATMOSPHERES:
            fr = list(m.Renderer(self.img, m.direction_for("push_in", FRAME, 1.0, [a]), FRAME).frames(1.0))
            self.assertEqual(fr[0].shape, plain.shape)
            self.assertGreater(float(np.abs(fr[5].astype(int) - plain.astype(int)).mean()), 0.05, a)

    @unittest.skipUnless(FFMPEG, "ffmpeg")
    def test_the_same_input_gives_the_same_file_and_the_short_frame_works(self):
        for frame in (FRAME, SHORT):
            d = m.direction_for("parallax_2_5d", frame, 1.0, ["dust", "film_grain"])
            a = m.render_direction(self.img, self.tmp / "a.mp4", 1.0, d, frame)
            b = m.render_direction(self.img, self.tmp / "b.mp4", 1.0, copy.deepcopy(d), frame)
            self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(), hashlib.sha256(b.read_bytes()).hexdigest())
            got = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_frames", "-show_entries",
                                  "stream=width,height,nb_read_frames", "-of", "csv=p=0", str(a)],
                                 capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(got, f"{frame[0]},{frame[1]},30")

    def test_the_moves_sheet_shows_every_move(self):
        out = m.moves_sheet(self.img, self.tmp / "moves.jpg", (192, 108))
        self.assertEqual(cv2.imread(str(out)).shape[0], len(m.MOTIONS) * 112)

    def test_the_move_lands_at_the_end_of_the_span_then_holds(self):
        d = m.direction_for("push_in", FRAME, 1.0, [])
        fr = list(m.Renderer(self.img, d, FRAME).frames(1.5))
        self.assertEqual(len(fr), 45)
        self.assertTrue(np.array_equal(fr[30], fr[44]))
        self.assertFalse(np.array_equal(fr[20], fr[29]))


class SafeBand(unittest.TestCase):
    def test_the_subject_stays_inside_the_centre_9_16_band(self):
        subjects = [None, [-0.05, -0.3, 0.05, 0.2], [0.02, -0.2, 0.12, 0.1], [-0.14, -0.1, -0.06, 0.2]]
        for frame in ((1920, 1080), SHORT):
            for sub in subjects:
                for move in m.MOTIONS:
                    an = {"subject": sub, "subject_from": "face"} if sub else None
                    d = m.direction_for(move, frame, 16.0, [], an=an)
                    self.assertEqual(m.path_problems(d["keys"], d["subject"], frame,
                                                     m.parallax_extra(move, d["strength"])), [], (move, sub))
                    self.assertTrue(projected_band_ok(d, frame), (move, sub, frame))

    def test_a_subject_wider_than_the_band_is_centred_and_said(self):
        d = m.direction_for("pan_left", (1920, 1080), 16.0, [], an={"subject": [-0.45, -0.3, 0.45, 0.3]})
        self.assertEqual(d["subject"], [round(v, 4) for v in m.default_subject((1920, 1080))])
        self.assertIn("centred", d["reason"])


class Director(unittest.TestCase):
    def test_beat_and_emotion_choose_different_moves(self):
        f = (1920, 1080)
        hook = m.decide({"id": "a", "prompt": "Wide shot. Ominous and uneasy."}, "hook", 0.0, "dread", 16, None, [], f)
        keeper = m.decide({"id": "a", "prompt": "Calm and tender."}, "keeper", 0.9, "calm", 16, None, [], f)
        climax = m.decide({"id": "a", "prompt": "Hushed."}, "climax", 0.8, "awe", 18, None, [], f)
        grief = m.decide({"id": "a", "prompt": "Grief."}, "aftermath", 0.85, "grief", 16, None, [], f)
        self.assertEqual(len({hook["move"], keeper["move"], climax["move"], grief["move"]}), 4,
                         [hook["move"], keeper["move"], climax["move"], grief["move"]])
        self.assertEqual(climax["move"], "hold_then_push")   # the silence before the KJV line, then the move
        self.assertNotEqual(hook["ease"], keeper["ease"])
        short = m.decide({"id": "a", "prompt": "x"}, "climax", 0.8, "neutral", 5, None, [], f)
        self.assertNotEqual(short["move"], "hold_then_push")   # no time to hold in a 5 s span
        for d in (hook, keeper, climax):
            self.assertIn("beat", d["reason"])

    def test_the_picture_steers_the_move_and_the_atmosphere(self):
        f = (1920, 1080)
        face = {"subject": [0.06, -0.15, 0.14, -0.02], "subject_from": "face", "face": [0.1, -0.08], "fire": True}
        d = m.decide({"id": "a", "prompt": "A man at night by the torch."}, "escalation", 0.4, "neutral", 16, face, [], f)
        self.assertEqual(d["move"], "pan_to_subject")
        self.assertEqual(d["ease"], "settle")
        self.assertEqual(d["keys"][-1][2], max(min(0.1, d["keys"][-1][2]), d["keys"][-1][2]))
        self.assertIn("torch_flicker", d["atmosphere"])
        water = m.choose_atmosphere("The flood waters rise.", "neutral", "escalation", {"water": False})
        self.assertNotIn("water_shimmer", [a for a, _ in water])   # the picture shows no water: no ripple on land
        self.assertIn("rain", [a for a, _ in m.choose_atmosphere("Rain lashes the hill.", "dread", "kjv", {})])

    def test_no_move_repeats_on_consecutive_shots_and_a_sequence_varies(self):
        plan = long_plan()
        d = m.direct(plan, {s["id"] for s in plan["shots"]})
        moves = [d[s["id"]]["move"] for s in plan["shots"]]
        self.assertFalse([i for i in range(1, len(moves)) if moves[i] == moves[i - 1]], moves)
        self.assertGreaterEqual(len(set(moves)), 6, moves)
        self.assertNotIn("hold", moves)
        self.assertEqual(m.direct(plan, {s["id"] for s in plan["shots"]}), d)   # deterministic

    def test_a_plan_override_wins(self):
        plan = long_plan(6)
        plan["shots"][2]["motion"] = "tilt_down"
        plan["shots"][3]["motion"] = {"move": "hold_then_push", "hold": 0.45, "ease": "build", "strength": 1.2}
        plan["shots"][4]["atmosphere"] = ["embers"]
        d = m.direct(plan, {s["id"] for s in plan["shots"]})
        self.assertEqual((d["s-02"]["move"], d["s-02"]["source"]), ("tilt_down", "override"))
        self.assertEqual((d["s-03"]["move"], d["s-03"]["hold"], d["s-03"]["ease"]), ("hold_then_push", 0.45, "build"))
        self.assertEqual(d["s-03"]["keys"][1][0], 0.45)
        self.assertEqual(d["s-04"]["atmosphere"], ["embers"])
        self.assertNotEqual(d["s-04"]["move"], "hold_then_push")

    def test_beats_are_read_from_the_plan(self):
        plan = json.loads(SHORT_PLAN.read_text())
        b = m.beats_of(plan)
        self.assertEqual(b["s-voice"][0], "hook")
        self.assertEqual(b["s-drift"][0], "climax")
        self.assertEqual(b["s-pairs"][0], "kjv")
        self.assertEqual(b["s-noah-lamp"][0], "aftermath")
        self.assertEqual(b["k-insight"][0], "keeper")
        self.assertEqual(m.mood_of("Wide shot. Mocking and uneasy. The valley."), "dread")


class PlanAndBuild(unittest.TestCase):
    def test_e261_a_long_first_still_is_directed_and_a_long_hold_must_move(self):
        plan = long_plan(4, 16)
        self.assertFalse([p for p in pc.motion_problems(plan, plan["shots"])])
        held = copy.deepcopy(plan)
        held["shots"][1]["motion"] = "hold"
        self.assertTrue(any(p.startswith("MOTION_REQUIRED shot 1") for p in pc.motion_problems(held, held["shots"])))
        bad = copy.deepcopy(plan)
        bad["shots"][0]["motion"] = "spin"
        bad["shots"][2]["atmosphere"] = ["snow"]
        got = pc.motion_problems(bad, bad["shots"])
        self.assertTrue(any(p.startswith("MOTION_UNKNOWN") for p in got), got)
        self.assertTrue(any(p.startswith("ATMOSPHERE_UNKNOWN") for p in got), got)
        rep = copy.deepcopy(plan)
        rep["shots"][1]["motion"] = rep["shots"][2]["motion"] = "pan_left"
        self.assertTrue(any(p.startswith("MOTION_REPEATED shot 2") for p in pc.motion_problems(rep, rep["shots"])))
        self.assertEqual(pc.scene_seconds_problems(0, dict(plan["shots"][0], seconds=20), plan), [])
        self.assertTrue(pc.scene_seconds_problems(0, dict(plan["shots"][0], seconds=21), plan))

    def test_the_short_route_is_unchanged(self):
        short = json.loads(SHORT_PLAN.read_text())
        self.assertEqual(pc.motion_problems(short, short["shots"]), [])
        moved = copy.deepcopy(short)
        moved["shots"][1]["motion"] = "push_in"
        self.assertTrue(any(p.startswith("MOTION_LONG_FIRST_ONLY") for p in pc.motion_problems(moved, moved["shots"])))
        self.assertEqual(pc.scene_seconds_problems(0, dict(short["shots"][1], seconds=16), short),
                         [f"SCENE_SECONDS shot 0 {short['shots'][1]['id']} (4-12)"])

    def test_a_long_first_approval_renders_only_a_direction(self):
        with tempfile.TemporaryDirectory(dir=ss.REPO) as t:
            img = still(Path(t) / "still.png")
            sha = hashlib.sha256(img.read_bytes()).hexdigest()
            a = {"source": "still_motion", "repo_path": str(img.relative_to(ss.REPO)), "still_sha256": sha,
                 "still": "st-x", "clip_seconds": 1, "frame": list(FRAME), "motion_engine": m.ENGINE}
            with self.assertRaises(SystemExit) as e:
                ss.fetch_source(a, Path(t) / "out.mp4")
            self.assertIn("STILL_MOTION_DIRECTION_MISSING", str(e.exception))
            if FFMPEG:
                out = ss.fetch_source(a, Path(t) / "out.mp4", direction=m.direction_for("drift", FRAME, 1.0, []))
                self.assertTrue(Path(out).stat().st_size > 0)

    def test_the_depth_model_is_pinned(self):
        with tempfile.TemporaryDirectory() as t:
            fake = Path(t) / "model.onnx"
            fake.write_bytes(b"not the model")
            with self.assertRaises(SystemExit) as e:
                m.depth_maps(fake, [], t)
            self.assertIn("DEPTH_MODEL_SHA256_MISMATCH", str(e.exception))
        self.assertIn(m.DEPTH_MODEL["sha256"], (HERE.parents[1] / ".github/workflows/episode.yml").read_text())


if __name__ == "__main__":
    unittest.main()
