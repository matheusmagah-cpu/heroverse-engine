#!/usr/bin/env python3
"""LONG_DESIGN slice 3: the long's build. Offline: a tiny synthetic long (4 approved fake clips, one window) assembles
to a 16:9 file of the timeline's length with its .srt track and the manifest qa_pilot reads; the cold open's hold is
measured on the voice; every cut is a story QA v3 hold; a window reuses its source's clip; the upscale binds each
picture to its approved clip; the build refuses a long without a PASS preflight; long-build.yml ships approved clips
only (verify-preflight first, no Pavo secret) and resumes like the Shorts."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration" / "publish"))
import episode_build as eb  # noqa: E402
import episode_preflight as pf  # noqa: E402
import long_build as lb  # noqa: E402
import long_plan_check as lpc  # noqa: E402
import short_engine  # noqa: E402

LONG = HERE / "plans" / "arc-01-long.json"
WORKFLOW = ROOT / ".github" / "workflows" / "long-build.yml"
FFMPEG = shutil.which("ffmpeg") is not None


def tiny_plan():
    """Five holds: two cold-open scenes on one line, the Keeper talking, a window of the first scene, a scene."""
    return {"version": eb.LONG_VERSION, "long": "test-long", "episode": "test-long", "arc": "test", "pilot": "pilot-999",
            "aspect_ratio": "16:9", "burned_captions": False, "music_offset": 0.0,
            "narration": [{"kind": "story", "text": "You stand in the garden at dusk while the leaves turn gold."},
                          {"kind": "promise", "text": "Stay with me and see what the old words say."},
                          {"kind": "story", "text": "The man and the woman walk out under a red evening sky."}],
            "shots": [{"id": "s-a", "kind": "scene", "beat": "cold_open", "lines": [0], "seconds": 7,
                       "characters": ["eve"], "prompt": "a"},
                      {"id": "s-b", "kind": "scene", "beat": "cold_open", "lines": [0], "seconds": 5,
                       "characters": [], "prompt": "b"},
                      {"id": "k-1", "kind": "keeper", "beat": "keeper_promise", "lines": [1], "prompt": "k"},
                      {"id": "s-w", "kind": "scene", "beat": "chapter", "chapter": "c1", "lines": [2],
                       "window_of": "s-a"},
                      {"id": "s-c", "kind": "scene", "beat": "chapter", "chapter": "c1", "lines": [2], "seconds": 5,
                       "characters": ["adam"], "prompt": "c"}]}


LINES = [(0.0, 7.4), (8.0, 12.0), (12.6, 20.0)]
CLIPS = {"s-a": 7.0, "s-b": 5.0, "k-1": 4.5, "s-c": 5.0}


def tiny_layout(total=21.2):
    return {"lines": [{"start": a, "end": b} for a, b in LINES], "voice_seconds": round(total - eb.TAIL, 3),
            "total": total, "keeper": {"k-1": {"start": 8.0, "end": 12.0, "seconds": 4.0}}, "speakers": {},
            "voice_over": {}, "keeper_share": 0.19}


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)], check=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Cut(unittest.TestCase):
    def test_one_cut_a_shot_and_a_window_shows_the_next_part_of_its_source_clip(self):
        plan = tiny_plan()
        cuts = lb.compose_long_shots(plan, tiny_layout(), {k: f"{k}.mp4" for k in CLIPS}, CLIPS)
        self.assertEqual([c["shot"] for c in cuts], ["s-a", "s-b", "k-1", "s-w", "s-c"])
        self.assertEqual([c["kind"] for c in cuts], ["scene", "scene", "keeper", "window", "scene"])
        self.assertEqual([(c["start"], c["end"]) for c in cuts],
                         [(0.0, 4.0), (4.0, 8.0), (8.0, 12.6), (12.6, 16.9), (16.9, 21.2)])
        window = cuts[3]
        self.assertEqual(window["clip"], "s-a.mp4")              # no clip of its own: its source's
        factor = (4.0 + 4.3) / 7.0
        self.assertAlmostEqual(window["speed"], factor, places=3)
        self.assertAlmostEqual(window["src_start"], 4.0 / factor, places=2)   # after what s-a showed
        self.assertEqual(cuts[0]["src_start"], 0.0)
        # the Keeper talks from his first word, at normal speed, his last frame held for the gap
        self.assertEqual((cuts[2]["src_start"], cuts[2]["speed"], cuts[2]["talk"]), (0.0, 1.0, {"start": 8.0, "end": 12.0}))
        self.assertAlmostEqual(cuts[2]["hold"], 0.11, places=3)
        self.assertEqual(lb.compose_problems(plan, tiny_layout(), CLIPS), [])

    def test_every_cut_is_a_story_qa_hold_and_a_short_clip_is_refused(self):
        plan = tiny_plan()
        self.assertEqual(lb.HOLDS, tuple(lpc.qa()["grammar"]["scene_seconds"]))
        self.assertEqual(lb.MUSIC_DB, short_engine.MUSIC_DB)
        # the last run shrunk: two cuts of 3.4 s
        shorter = tiny_layout(19.4)
        shorter["lines"][2]["end"] = 18.2
        bad = lb.compose_problems(plan, shorter, CLIPS)
        self.assertTrue(any(p.startswith("HOLD_UNDER_QA cut 3 s-w") for p in bad), bad)
        # the Short's 2-4 s cutting is never used: one cut a shot even when it is long
        longer = lb.compose_long_shots(plan, tiny_layout(), {k: k for k in CLIPS}, dict(CLIPS, **{"s-a": 12.0}))
        self.assertEqual(len(longer), 5)
        # s-a's clip cannot cover its hold and its window's slowed 1.3x at most
        self.assertTrue(lb.compose_problems(plan, tiny_layout(), dict(CLIPS, **{"s-a": 6.0}))[0]
                        .startswith("FOOTAGE_SHORT s-a"))
        self.assertTrue(lb.compose_problems(plan, tiny_layout(), dict(CLIPS, **{"k-1": 3.5}))[0]
                        .startswith("KEEPER_CLIP_SHORT k-1"))


class ColdOpen(unittest.TestCase):
    def durations(self, plan):
        items, _ = eb.plan_check.sequence(plan)
        return [eb.plan_check.words(x["text"]) / lpc.pace(x) for x in items]

    def test_the_keeper_starts_at_the_cold_open_end_measured_on_the_voice(self):
        plan = json.loads(LONG.read_text())
        d = self.durations(plan)
        layout, cold, problems = eb.voice_layout(plan, d)
        self.assertEqual(problems, [])
        k0, hold = cold
        after = next(i for i, s in enumerate(plan["shots"]) if s["beat"] != "cold_open")
        self.assertEqual(k0, eb.plan_check.sequence(plan)[1][after][0])
        self.assertAlmostEqual(layout[k0][0], lpc.gate()["cold_open_s"], places=3)
        self.assertLessEqual(hold, lpc.COLD_OPEN_HOLD_MAX)
        problems, laid = eb.predict(plan, d)   # the preflight's prediction carries the hold and the long's cut
        self.assertEqual(problems, [])
        self.assertAlmostEqual(laid["lines"][k0]["start"], lpc.gate()["cold_open_s"], places=3)
        # the cold open's words measured longer than its 30 s, or so short that its last frame would hold > 3 s
        longer = [x * 1.2 if k < k0 else x for k, x in enumerate(d)]
        self.assertTrue(eb.voice_layout(plan, longer)[2][0].startswith("COLD_OPEN_LENGTH"))
        self.assertTrue(any(p.startswith("COLD_OPEN_LENGTH") for p in eb.predict(plan, longer)[0]))
        shorter = [x * 0.7 if k < k0 else x for k, x in enumerate(d)]
        self.assertTrue(eb.voice_layout(plan, shorter)[2][0].startswith("COLD_OPEN_SHORT"))
        # a Short is untouched: end to end at its own gap, no hold
        short = json.loads((HERE / "plans" / "genesis-09-short.json").read_text())
        laid, cold, problems = eb.voice_layout(short, [3.0, 4.0])
        self.assertEqual((laid, cold, problems), (eb.line_layout([3.0, 4.0], eb.LINE_GAP), None, []))


@unittest.skipUnless(FFMPEG, "ffmpeg")
class Assemble(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir)

    def fixture(self):
        plan = tiny_plan()
        work, up = self.dir / "work", self.dir / "up"
        work.mkdir()
        up.mkdir()
        approvals, report = {}, {"episode": plan["episode"], "shots": {}}
        for k, (sid, secs) in enumerate(CLIPS.items()):
            clip = up / f"{sid}.mp4"
            ffmpeg("-f", "lavfi", "-i", f"testsrc2=size=320x180:rate=30:duration={secs}", "-vf", f"hue=h={k * 60}",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", clip)
            src = f"{k:064x}"
            approvals[sid] = {"asset": f"shot-test-long-sha256-{src}.mp4", "clip_sha256": src}
            eb.save(up / f"{sid}.json", {"shot": sid, "source_sha256": src, "source_asset": approvals[sid]["asset"],
                                         "sha256": sha(clip), "frame": [320, 180], "upscaler": lb.AI["upscaler"]})
            report["shots"][sid] = {"approved": {"clip_sha256": src}, "checks": {"flags": [], "measures": None}}
        layout = tiny_layout()
        eb.save(work / "layout.json", layout)
        eb.save(work / "report.json", report)
        texts = [x["text"] for x in plan["narration"]]
        sentences = [{"segment": f"n{k:02d}", "text": t, "start": a, "end": b}
                     for k, (t, (a, b)) in enumerate(zip(texts, LINES))]
        sentences[0]["speaker"] = "eve"
        eb.save(work / "compose-timeline.json", {"voice_seconds": layout["voice_seconds"], "sentences": sentences,
                                                 "voice_id": "am_michael", "speed": 1.0, "sample_rate": 24000})
        ffmpeg("-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=24000:duration={layout['voice_seconds']}",
               "-af", "volume=0.3", work / "narration.wav")
        music = self.dir / "music.flac"
        ffmpeg("-f", "lavfi", "-i", "anoisesrc=color=pink:sample_rate=48000:duration=30:amplitude=0.2",
               "-ac", "2", music)
        return plan, work, up, music, approvals

    def test_a_tiny_long_assembles_to_a_16x9_file_with_its_srt_track_and_manifest(self):
        import captions
        plan, work, up, music, approvals = self.fixture()
        out = self.dir / "out"
        lb.assemble_step(plan, work, up, music, out, frame=(320, 180), approvals=approvals)
        video = out / "test-long.mp4"
        info = lb.probe(video)
        v = info["video"][0]
        self.assertEqual((v["width"], v["height"], v["avg_frame_rate"]), (320, 180, "30/1"))
        self.assertEqual(v["width"] * 9, v["height"] * 16)
        self.assertAlmostEqual(info["seconds"], 21.2, delta=0.1)
        self.assertEqual((info["audio"][0]["codec_name"], info["audio"][0]["sample_rate"]), ("aac", "48000"))
        lufs, tp = lb.loudness(video)
        self.assertTrue(lb.LUFS_BAND[0] <= lufs <= lb.LUFS_BAND[1], lufs)
        self.assertLessEqual(tp, lb.TP_MAX)
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(captions.manifest_problems(manifest, out), [])   # the .srt beside it, the one uploaded
        srt = (out / "captions.srt").read_text()
        self.assertIn("You stand in", srt)
        self.assertFalse(manifest["burned_captions"])
        self.assertEqual(manifest["output_sha256"], sha(video))
        self.assertEqual([h["shot_kind"] for h in manifest["holds"]], ["scene", "scene", "keeper", "window", "scene"])
        self.assertEqual(manifest["holds"][3]["image"].partition("#")[0], "s-a")
        self.assertNotEqual(manifest["holds"][3]["image"], manifest["holds"][0]["image"])
        self.assertEqual(manifest["holds"][2]["characters"], ["keeper"])
        self.assertEqual(sorted(c["id"] for c in manifest["clips"]), sorted(CLIPS))
        self.assertTrue(all(c["clip_check"] == "PASS" and c["vetting"] == "APPROVED" for c in manifest["clips"]))
        self.assertEqual(manifest["sentences"][0]["speaker"], "eve")
        report = json.loads((out / "report.json").read_text())
        self.assertEqual(report["composed"]["output_sha256"], sha(video))
        self.assertEqual(report["composed"]["windows"], 1)

    def test_a_picture_not_made_from_the_approved_clip_is_refused(self):
        plan, work, up, music, approvals = self.fixture()
        approvals["s-b"] = dict(approvals["s-b"], clip_sha256="f" * 64)   # approved again since the upscale
        with self.assertRaises(SystemExit) as c:
            lb.assemble_step(plan, work, up, music, self.dir / "out", frame=(320, 180), approvals=approvals)
        self.assertEqual(str(c.exception), "UPSCALE_SOURCE_MISMATCH s-b")
        (up / "s-c.mp4").unlink()
        with self.assertRaises(SystemExit) as c:
            lb.upscaled(plan, up, approvals, (320, 180))
        self.assertIn("UPSCALE_MISSING s-c", str(c.exception))

    def test_the_upscale_binds_its_picture_to_the_approved_clip(self):
        import numpy as np
        plan = tiny_plan()
        src = self.dir / "src.mp4"
        ffmpeg("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=24:duration=0.5", "-c:v", "libx264", "-pix_fmt",
               "yuv420p", src)
        digest = sha(src)
        approvals = {"s-c": {"asset": f"shot-test-long-sha256-{digest}.mp4", "clip_sha256": digest}}
        rec = lb.upscale_step(plan, "s-c", self.dir / "up", "weights.pth",
                              frame_fn=lambda img: np.repeat(np.repeat(img, 4, axis=0), 4, axis=1),
                              fetch=lambda name, dst: shutil.copyfile(src, dst), approvals=approvals)
        self.assertEqual((rec["source_sha256"], rec["frame"], rec["fps"]), (digest, [2560, 1440], 30))
        self.assertEqual(rec["sha256"], sha(self.dir / "up" / "s-c.mp4"))
        self.assertEqual(rec["artifact"], lb.artifact_name("test-long", "s-c", digest))
        self.assertFalse((self.dir / "up" / "s-c.src.mp4").exists())
        v = lb.probe(self.dir / "up" / "s-c.mp4")["video"][0]
        self.assertEqual((v["width"], v["height"]), (2560, 1440))
        with self.assertRaises(SystemExit) as c:   # a window is never upscaled: it reuses its source's picture
            lb.upscale_step(plan, "s-w", self.dir / "up", "w", frame_fn=lambda x: x, approvals=approvals)
        self.assertTrue(str(c.exception).startswith("UPSCALE_SHOT_REFUSED s-w"))
        with self.assertRaises(SystemExit):        # a fetched file that is not the approved clip
            lb.upscale_step(plan, "s-c", self.dir / "up2", "w", frame_fn=lambda x: x, approvals=approvals,
                            fetch=lambda name, dst: Path(dst).write_bytes(b"other"))


class Contract(unittest.TestCase):
    def test_the_frame_is_the_frozen_qa_16x9_and_the_loudness_inside_its_band(self):
        self.assertEqual(lb.FRAME, (2560, 1440))
        self.assertEqual(lb.FRAME[0] * 9, lb.FRAME[1] * 16)
        self.assertTrue(lb.LUFS_BAND[0] < lb.LUFS_TARGET < lb.LUFS_BAND[1])
        self.assertLess(lb.TP_TARGET, lb.TP_MAX)

    def test_resume_upscales_only_the_shots_without_an_artifact_of_their_approved_clip(self):
        plan = tiny_plan()
        approvals = {k: {"clip_sha256": f"{n:064x}"} for n, k in enumerate(CLIPS)}
        self.assertEqual(lb.upscale_ids(plan, [], approvals), list(CLIPS))
        done = [lb.artifact_name("test-long", "s-a", approvals["s-a"]["clip_sha256"]),
                lb.artifact_name("test-long", "s-b", "e" * 64)]          # s-b approved again since: redone
        self.assertEqual(lb.upscale_ids(plan, done, approvals), ["s-b", "k-1", "s-c"])
        self.assertTrue(lb.ARTIFACT.fullmatch(done[0]))
        with self.assertRaises(SystemExit):
            lb.upscale_ids(plan, [], {})

    def test_the_build_refuses_a_long_without_a_pass_preflight(self):
        saved = pf.REPORTS
        tmp = Path(tempfile.mkdtemp())
        try:
            pf.REPORTS = tmp
            for step in (["timeline", str(LONG), str(tmp)], ["assemble", str(LONG), str(tmp), str(tmp), "m", str(tmp)],
                         ["upscale", str(LONG), "s-open", str(tmp), "w"]):
                with self.assertRaises(SystemExit) as c:
                    lb.main(["long_build.py", *step])
                self.assertTrue(str(c.exception).startswith("PREFLIGHT_MISSING arc-01-long.json"), step)
            with self.assertRaises(SystemExit) as c:
                lb.checked_plan(HERE / "plans" / "genesis-09-short.json")
            self.assertTrue(str(c.exception).startswith("LONG_PLAN_REQUIRED"))
        finally:
            pf.REPORTS = saved
            shutil.rmtree(tmp)

    def test_long_build_yml_ships_approved_clips_only_and_resumes(self):
        text = WORKFLOW.read_text()
        self.assertNotIn("PAVO_TOKEN", text)
        self.assertNotIn("secrets.", text)
        self.assertLess(text.index("episode_build.py verify-preflight"), text.index("episode_build.py generate"))
        self.assertLess(text.index("episode_build.py generate"), text.index("long_build.py timeline"))
        self.assertIn("long_plan_check.py \"$PLAN\" --strict", text)
        for step in ("long_build.py upscale-ids", "long_build.py upscale ", "long_build.py assemble",
                     "long_build.py sheet", "resume_run", "max-parallel: 20", "sha256sum -c -",
                     "RESUME_RUN_NOT_A_LONG_BUILD"):   # sweep H2: never a pull request run's artifacts
            self.assertIn(step, text, step)
        # the composed file and its .srt go to the release under their content hash, like the Shorts
        self.assertIn('asset="bible-$EP-sha256-$sha.mp4"', text)
        self.assertIn('srt_asset="bible-$EP-sha256-$sha.srt"', text)
        self.assertIn("REPORT_SHA256_MISMATCH", text)
        self.assertRegex(text, r"(?m)^concurrency:\n  group: heroverse-long-build\n")


if __name__ == "__main__":
    unittest.main()
