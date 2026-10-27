#!/usr/bin/env python3
"""Owner 27/10 ~22:50 UTC (R1-R4, the long and the Shorts, "em qualquer situação"): no stall. Offline: every clip
already made is reused (R1), the Pavo budget goes first to the spoken shots (R2), the silent shots it does not reach
are filled from free licensed footage or approved stills in motion, each still approved by Claude (R3), and a clip that
keeps Pavo's speech is judged clip by clip (R4: story QA v4 speech_checks) and mixed with one gain, short fades and a
continuous bed."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import episode_build as eb  # noqa: E402
import pavo_native as pn  # noqa: E402
import shot_sources as ss  # noqa: E402

HAS_FFMPEG = shutil.which("ffmpeg") is not None
STYLE = "Painterly cinematic realism, cinema camera"
V4 = pn.criteria()


def plan():
    return {"episode": "t-sources", "narration": [{"kind": "story", "text": "The river ran through the garden."},
                                                  {"kind": "story", "text": "And the waters parted below."}],
            "shots": [{"id": "s-eve", "kind": "scene", "speaker": "eve", "line": "Why do you hide?",
                       "characters": ["eve"], "prompt": f"{STYLE}. Close-up. Eve speaks"},
                      {"id": "s-god", "kind": "scene", "speaker": "god", "line": "Let there be light.",
                       "characters": [], "seconds": 8, "prompt": f"{STYLE}. Wide shot. Light over dark water"},
                      {"id": "s-river", "kind": "scene", "lines": [0], "seconds": 6, "characters": [],
                       "prompt": f"{STYLE}. Wide shot. A river runs through the green garden at dawn"},
                      {"id": "s-pair", "kind": "scene", "lines": [1], "seconds": 6, "characters": ["eve"],
                       "prompt": f"{STYLE}. Medium shot. Eve walks by the river"}]}


def clip(cid, theme="river", title="river rocks water", **over):
    sha = (cid.encode().hex() * 64)[:64]
    rec = {"id": cid, "theme": theme, "query": theme, "title": title, "licence": "Pixabay Content License",
           "vetting": "APPROVED", "claude_seen": True, "frame": [2560, 1440], "sha256": sha, "seconds": 20.0,
           "credit": "Footage: x via Pixabay", "release_asset": f"footage-{cid}-sha256-{sha}.mp4"}
    rec.update(over)
    return rec


class Reuse(unittest.TestCase):
    """R1: run 40592173923 returned 3 clean God clips before the quota stop; they wait for review on their branch and
    are never queued for a new generation."""

    def test_a_clean_clip_on_a_shot_probe_branch_is_awaiting_review_not_queued(self):
        p = plan()
        record = {"run_id": "40592173923", "shots": {
            "s-god": {"request_sha256": "g1", "clips": [{"asset": "shot-a.mp4", "clip_sha256": "c", "flags": [],
                                                       "uploaded": True},
                                                      {"error": "SHOT_FAILED s-god after 3 generations: NO_VIDEO"}]},
            "s-river": {"request_sha256": "r-old", "clips": [{"asset": "shot-b.mp4", "clip_sha256": "d", "flags": []}]},
            "s-pair": {"request_sha256": "p1", "clips": [{"asset": "shot-c.mp4", "clip_sha256": "e",
                                                        "flags": ["CLIP_ASPECT_MISMATCH"]}]}}}

        def git(args, **kw):
            if "for-each-ref" in args:
                return subprocess.CompletedProcess(args, 0, "claude/shot-probe-t-sources-40592173923\nclaude/x\n", "")
            return subprocess.CompletedProcess(args, 0, json.dumps(record), "")
        branch = ss.branch_clips(p, run=git)
        digests = {"s-eve": "e1", "s-god": "g1", "s-river": "r1", "s-pair": "p1"}
        waiting = ss.awaiting_review(p, digests, {}, branch)
        self.assertEqual(sorted(waiting), ["s-god"])     # a clip of another request or with flags is not a reuse
        import long_preflight
        q = long_preflight.queue(p, digests, {}, existing=waiting, max_units=1000)
        queued = ",".join(b["shots"] for b in q["batches"]).split(",")
        self.assertNotIn("s-god", queued)
        self.assertEqual(q["awaiting_review"], {"s-god": ["shot-a.mp4"]})
        self.assertIsNone(ss.branch_clips(p, run=lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "no git")))

    def test_inventory_clips_count_only_when_their_checks_are_clean(self):
        self.assertTrue(ss.clean({"flags": []}))
        self.assertFalse(ss.clean({"flags": ["NO_VIDEO"]}))
        self.assertFalse(ss.clean({"lipsync_check": ["AUDIO_NOT_OUR_LINE"]}))
        self.assertTrue(ss.clean({"lipsync_check": []}))
        self.assertFalse(ss.clean({"sha256": "x"}))   # nothing measured is not clean


class Allocation(unittest.TestCase):
    """R2/R3: the spoken shots get the budget first; a silent shot with no character falls back to a free source; a
    shot with a character waits (its look needs its references)."""

    def test_spoken_first_then_free_fallbacks_and_characters_wait(self):
        import long_preflight
        p = plan()
        todo = [s for _, s in eb.risk_order(p["shots"])]
        self.assertEqual([s["id"] for s in todo][:2], ["s-eve", "s-god"])   # probe-queue's order: talking first
        one = long_preflight.planned_units([p["shots"][0]])
        got = dict((s["id"], c) for s, c in ss.allocate(p, todo, one))
        self.assertEqual(got, {"s-eve": "pavo", "s-god": "WAIT_PAVO_BUDGET", "s-river": "fallback",
                               "s-pair": "WAIT_PAVO_BUDGET"})
        rich = dict((s["id"], c) for s, c in ss.allocate(p, todo, 10 ** 6))
        self.assertEqual(set(rich.values()), {"pavo"})

    def test_the_sources_report_fills_the_silent_shot_from_the_library(self):
        class Spent:
            def check_batch(self, units):
                import quota
                raise quota.PavoError("PAVO_DAILY_CAP generated=120 units=0 cap=120 day=2026-10-27")
        lib = [clip("clip-river-a"), clip("clip-candle", theme="candle", title="candle flame")]
        r = ss.sources_report(plan(), {}, {}, guard=Spent(), lib=lib, today="2026-10-27")
        self.assertEqual(r["pavo_budget"]["remaining_units"], 0)
        self.assertEqual(r["shots"]["s-river"]["source"], "footage")
        self.assertEqual(r["shots"]["s-river"]["candidates"][0]["item"], "clip-river-a")
        self.assertEqual(r["shots"]["s-eve"]["source"], "WAIT_PAVO_BUDGET")

    def test_footage_follows_the_words_the_licence_list_and_the_period(self):
        p = plan()
        i = 2
        lib = [clip("clip-river-a"), clip("clip-river-b", vetting="PENDING"), clip("clip-river-c", claude_seen=False),
               clip("clip-river-d", licence="CC BY-SA 4.0"), clip("clip-river-e", title="river through the city"),
               clip("clip-river-f", title="man by the river"), clip("clip-snow", theme="snow", title="snow peak")]
        p["period"] = "eden"
        got = [c["item"] for c in ss.footage_candidates(p, p["shots"][i], i, lib)]
        self.assertEqual(got, ["clip-river-a"])


class ApproveSource(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.lib = [clip("clip-river-a"), clip("clip-snow", theme="snow", title="snow peak")]

    def tearDown(self):
        shutil.rmtree(self.dir)

    def approve(self, shot, item="clip-river-a", score=9.6, note="the river under the line", source="footage"):
        return ss.approve_source(plan(), shot, source, item, score, note, lib=self.lib, shots_dir=self.dir,
                                 today="2026-10-27")

    def test_claude_approves_a_fallback_and_the_build_accepts_exactly_it(self):
        a = self.approve("s-river")
        self.assertEqual((a["source"], a["footage"], a["licence"]), ("footage", "clip-river-a", "Pixabay Content License"))
        p = plan()
        approvals = json.loads((self.dir / "t-sources.json").read_text())["shots"]
        missing = eb.review_problems(p, {}, approvals)
        self.assertFalse(any("s-river" in m for m in missing if m.startswith("SHOT_REQUEST_CHANGED")), missing)
        p["shots"][2]["prompt"] += " Birds rise."          # the shot changed: the approval no longer holds
        self.assertTrue(any(m.startswith("SHOT_REQUEST_CHANGED") and "s-river" in m
                            for m in eb.review_problems(p, {}, approvals)))

    def test_a_fallback_is_refused_where_it_would_break_the_floor(self):
        for shot, item, code in (("s-eve", "clip-river-a", "SOURCE_SPOKEN_SHOT"),
                                 ("s-god", "clip-river-a", "SOURCE_SPOKEN_SHOT"),
                                 ("s-pair", "clip-river-a", "SOURCE_CHARACTER_SHOT"),
                                 ("s-river", "clip-snow", "SOURCE_OFF_LINE"),
                                 ("s-river", "clip-gone", "FOOTAGE_NOT_USABLE")):
            with self.assertRaises(SystemExit) as err:
                self.approve(shot, item)
            self.assertTrue(str(err.exception).startswith(code), (shot, item, str(err.exception)))
        for score, note, code in ((9.4, "x", "SHOT_SCORE_OUT_OF_RANGE"), (9.6, " ", "SHOT_NOTE_MISSING")):
            with self.assertRaises(SystemExit) as err:
                self.approve("s-river", score=score, note=note)
            self.assertTrue(str(err.exception).startswith(code))
        with self.assertRaises(SystemExit) as err:
            self.approve("s-river", item="still-x", source="still_motion")
        self.assertTrue(str(err.exception).startswith("STILL_NOT_FOR_SHOT"))
        self.assertFalse((self.dir / "t-sources.json").exists())   # nothing approved by any refusal


class SpeechChecks(unittest.TestCase):
    """R4 / story QA v4: each kept speech clip, measured; a missing measure never passes."""
    LINE = "Who told thee that thou wast naked"

    def good(self):
        return {"asr": {"model_bin_sha256": V4["speech"]["asr_model"]["model_bin_sha256"], "text": self.LINE + "?",
                        "speech_span": [1.2, 4.0]},
                "voice": {"reference": "r", "same": 0.93, "others": [0.72, 0.64]}, "lufs": -24.0, "music": 0.0,
                "singing": 0.0, "lips": []}

    def test_a_clean_clip_passes_and_each_defect_fails(self):
        self.assertEqual(pn.speech_verdict(self.good(), self.LINE, V4), [])
        cases = {"SPEECH_WORDS_NOT_EXACT": ("asr", {"text": "Who told thee that thou was naked"}),
                 "ASR_MODEL_NOT_PINNED": ("asr", {"model_bin_sha256": "base.en"}),
                 "VOICE_REFERENCE_MISSING": ("voice", {"reference": None}),
                 "VOICE_NOT_CONSISTENT": ("voice", {"same": 0.85}),
                 "VOICE_NOT_DISTINCT": ("voice", {"same": 0.893, "others": [0.878]}),   # #473: Adam vs the Keeper
                 "SPEECH_LEVEL_UNREACHABLE": ("lufs", -31.0), "PAVO_MUSIC": ("music", 0.2),
                 "PAVO_SINGING": ("singing", 0.1), "LIPS_NOT_CHECKED": ("lips", None)}
        for flag, (key, value) in cases.items():
            m = self.good()
            m[key] = dict(m[key], **value) if isinstance(value, dict) else value
            self.assertIn(flag, pn.speech_verdict(m, self.LINE, V4), flag)
        m = self.good()
        m["lips"] = ["MOUTH_NOT_IN_SYNC"]
        self.assertEqual(pn.speech_verdict(m, self.LINE, V4), ["MOUTH_NOT_IN_SYNC"])

    def test_the_approval_record_holds_the_span_and_one_gain(self):
        rec = pn.speech_record("c", self.good(), self.LINE, V4)
        self.assertEqual((rec["flags"], rec["onset"], rec["end"], rec["gain_db"]), ([], 1.2, 4.0, 6.0))
        self.assertEqual(pn.clip_gain_db(-27.6, V4["rights"]["ai_video"]["speech_checks"]), 9.6)   # #473's God clip
        self.assertIsNone(pn.clip_gain_db(-31.0, V4["rights"]["ai_video"]["speech_checks"]))

    def test_gavest_is_exact_only_by_its_words(self):
        line = "The woman whom thou gavest to be with me"
        self.assertEqual(pn.wer(line, "The woman whom thou gavest to be with me."), 0.0)
        self.assertGreater(pn.wer(line, "The woman whom thou gave us to be with me"), 0.1)   # base.en's mishearing


class Mix(unittest.TestCase):
    def test_the_graph_has_one_gain_short_fades_and_a_continuous_bed(self):
        places = [{"clip": "a.mp4", "at": 3.0, "src_start": 1.16, "seconds": 4.2, "gain_db": -2.0}]
        g = pn.premix_filter(places, 20.0)
        self.assertIn("atrim=start=1.160:duration=4.200", g)
        self.assertIn("volume=-2.00dB", g)
        self.assertIn(f"afade=t=in:d={pn.XFADE_S}", g)
        self.assertIn("adelay=3000|3000", g)
        self.assertIn("anoisesrc=color=brown", g)
        self.assertIn("amix=inputs=3:normalize=0", g)
        self.assertLessEqual(pn.XFADE_S, V4["grammar"]["spoken_audio_mix"]["audio_crossfade_seconds_max"])

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
    def test_premix_lays_the_speech_and_never_drops_to_digital_silence(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "6",
                            str(d / "voice.wav")], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x36:d=4", "-f", "lavfi",
                            "-i", "sine=frequency=300:duration=4", "-shortest", "-c:v", "libx264", "-c:a", "aac",
                            str(d / "clip.mp4")], check=True)
            places = [{"clip": str(d / "clip.mp4"), "at": 1.0, "src_start": 0.5, "seconds": 3.0, "gain_db": 0.0}]
            pn.premix(d / "voice.wav", places, d / "mix.wav", 6.0)
            vol = subprocess.run(["ffmpeg", "-v", "info", "-i", str(d / "mix.wav"), "-af",
                                  "atrim=start=4.5:end=5.5,volumedetect", "-f", "null", "-"],
                                 capture_output=True, text=True).stderr
            tone = subprocess.run(["ffmpeg", "-v", "info", "-i", str(d / "mix.wav"), "-af",
                                   "atrim=start=2:end=3,volumedetect", "-f", "null", "-"],
                                  capture_output=True, text=True).stderr
            quiet = float(vol.split("mean_volume:")[1].split("dB")[0])
            loud = float(tone.split("mean_volume:")[1].split("dB")[0])
            self.assertGreater(quiet, -80.0)    # the bed: no digital silence between the clips
            self.assertLess(quiet, -30.0)       # and low
            self.assertGreater(loud, quiet + 15)   # the speech sits where its line is

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
    def test_an_approved_still_moves_at_the_qa_frame(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=192x108:d=1", "-frames:v", "1",
                            str(d / "still.jpg")], check=True)
            ss.still_motion_clip(d / "still.jpg", d / "out.mp4", 2.0, frame=(320, 180))
            info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json",
                                              str(d / "out.mp4")], capture_output=True, text=True).stdout)
            v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
            self.assertEqual((v["width"], v["height"]), (320, 180))
            self.assertFalse([s for s in info["streams"] if s["codec_type"] == "audio"])


if __name__ == "__main__":
    unittest.main()
