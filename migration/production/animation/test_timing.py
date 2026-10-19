import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import timing  # noqa: E402
from pilot_render import LEAD_IN, SENTENCE_GAP, sentences  # noqa: E402

PROJECT = HERE / "the-bag-he-almost-passed"
SCRIPT = json.loads((PROJECT / "script.json").read_text())
SCENES = json.loads((PROJECT / "scenes.json").read_text())
CRITERIA_PATH = HERE / "qa_criteria_animation_v1.json"
CRITERIA = json.loads(CRITERIA_PATH.read_text())


def make_timeline(seconds_per_word):
    """A timeline laid out exactly like pilot_render.voice(); seconds_per_word(scene_id) sets each sentence length."""
    cursor, segments, spoken = LEAD_IN, [], []
    for seg in SCRIPT["segments"]:
        start = cursor
        for text in sentences(seg["text"]):
            length = len(text.split()) * seconds_per_word(seg["id"])
            spoken.append({"segment": seg["id"], "text": text, "start": round(cursor, 3), "end": round(cursor + length, 3)})
            cursor += length + SENTENCE_GAP
        segments.append({"id": seg["id"], "start": round(start, 3), "end": round(cursor, 3)})
        cursor += seg["pause_after"]
    return {"segments": segments, "sentences": spoken, "voice_seconds": round(cursor, 3)}


def per_word_for(scene_ids, target, fixed=0.0, drop_first=()):
    """Seconds per word making the spans of scene_ids total `target` (`fixed` s of other spans included);
    scenes in drop_first are counted without their first sentence."""
    texts = {s["id"]: sentences(s["text"])[1 if s["id"] in drop_first else 0:] for s in SCRIPT["segments"]}
    words = sum(len(t.split()) for sid in scene_ids for t in texts[sid])
    gaps = sum(len(texts[sid]) - 1 for sid in scene_ids)
    return (target - fixed - SENTENCE_GAP * gaps) / words


def fitting(trim_s14=False):
    """Per-word lengths giving short1 42.0 s and short2 41.0 s (with trim_s14: 41.0 s only once S14 loses
    its first sentence, so whole scenes are too long), S15 lasting 4.0 s."""
    s1 = [s for s in SCENES["shorts"]["short1"]["scenes"] if s != "S15"]
    s2 = [s for s in SCENES["shorts"]["short2"]["scenes"] if s != "S15"]
    cta_words = len(SCRIPT["segments"][-1]["text"].split())
    k1 = per_word_for(s1, 42.0, 4.0)
    k2 = per_word_for(s2, 41.0, 4.0, drop_first=("S14",) if trim_s14 else ())
    return lambda sid: 4.0 / cta_words if sid == "S15" else k1 if sid in s1 else k2 if sid in s2 else 0.4


class SceneTiming(unittest.TestCase):
    def setUp(self):
        self.timeline = make_timeline(fitting())
        self.t = timing.scene_timing(self.timeline, SCENES)

    def test_contiguous_from_zero_to_master_end(self):
        scenes = self.t["scenes"]
        self.assertEqual([s["id"] for s in scenes], [s["id"] for s in SCENES["scenes"]])
        self.assertEqual(scenes[0]["first_frame"], 0)
        self.assertEqual(scenes[0]["start_s"], 0.0)
        for a, b in zip(scenes, scenes[1:]):
            self.assertEqual(a["end_frame"], b["first_frame"])
            self.assertEqual(a["end_s"], b["start_s"])
            self.assertLess(a["first_frame"], a["end_frame"])
        self.assertEqual(scenes[-1]["end_s"], self.timeline["voice_seconds"])
        self.assertEqual(scenes[-1]["end_frame"], self.t["frames_total"])
        self.assertEqual(self.t["fps"], 24)

    def test_pause_belongs_to_preceding_scene(self):
        seg = {s["id"]: s for s in self.timeline["segments"]}
        s01 = self.t["scenes"][0]
        self.assertEqual(s01["end_s"], seg["S02"]["start"])
        self.assertGreater(s01["end_s"], seg["S01"]["end"])  # S01's pause_after is inside S01

    def test_24_fps_rounding(self):
        self.assertEqual(timing.frame(1.0204), 24)   # 24.4896
        self.assertEqual(timing.frame(1.0209), 25)   # 24.5016
        self.assertEqual(timing.frame(0.021), 1)     # 0.504
        self.assertEqual(timing.frame(152.0), 3648)
        for s in self.t["scenes"]:
            self.assertEqual(s["first_frame"], round(s["start_s"] * 24))
            self.assertEqual(s["end_frame"], round(s["end_s"] * 24))

    def test_segments_must_equal_scenes(self):
        bad = dict(self.timeline, segments=self.timeline["segments"][1:])
        with self.assertRaises(timing.TimingError):
            timing.scene_timing(bad, SCENES)


class ShortsMap(unittest.TestCase):
    def _bounds_ok(self, timeline, spans):
        for sp in spans:
            mine = [s for s in timeline["sentences"] if s["segment"] == sp["scene"]]
            self.assertIn(sp["master_start_s"], [s["start"] for s in mine])
            self.assertIn(sp["master_end_s"], [s["end"] for s in mine])

    def test_whole_scenes_cut_on_sentence_boundaries(self):
        tl = make_timeline(fitting())
        m = timing.shorts_map(tl, SCENES, CRITERIA)
        for name in ("short1", "short2"):
            spans = m[name]["spans"]
            self.assertEqual([s["scene"] for s in spans], SCENES["shorts"][name]["scenes"])
            self._bounds_ok(tl, spans)
            self.assertEqual(m[name]["speed"], 1.0)
            lo, hi = CRITERIA["shorts"]["duration_seconds"][name]
            self.assertTrue(lo <= m[name]["total_s"] <= hi, m[name]["total_s"])
            self.assertAlmostEqual(m[name]["total_s"], sum(s["master_end_s"] - s["master_start_s"] for s in spans), places=3)
        s05 = next(s for s in m["short1"]["spans"] if s["scene"] == "S05")
        first = next(s for s in tl["sentences"] if s["segment"] == "S05")
        self.assertEqual(s05["master_start_s"], first["start"])
        self.assertEqual(first["text"], "Daniel stopped beside the bench.")

    def test_trims_s14_from_its_start_never_mid_sentence(self):
        # short2 scenes made long enough that whole scenes exceed 42 s; S14 is trimmed by whole sentences
        base = fitting(trim_s14=True)
        tl = make_timeline(base)
        whole = sum(s["end"] - s["start"] for s in tl["segments"] if s["id"] in ("S07", "S08", "S11", "S14", "S15"))
        self.assertGreater(whole, 42.0)
        m = timing.shorts_map(tl, SCENES, CRITERIA)
        spans = m["short2"]["spans"]
        self._bounds_ok(tl, spans)
        s14 = next(s for s in spans if s["scene"] == "S14")
        s14_sents = [s for s in tl["sentences"] if s["segment"] == "S14"]
        self.assertEqual(s14["master_start_s"], s14_sents[1]["start"])
        self.assertEqual(s14["master_end_s"], s14_sents[-1]["end"])
        self.assertTrue(40.0 <= m["short2"]["total_s"] <= 42.0, m["short2"]["total_s"])
        # spans other than the trimmable one stay whole
        s07 = next(s for s in spans if s["scene"] == "S07")
        self.assertEqual(s07["master_start_s"], next(s for s in tl["sentences"] if s["segment"] == "S07")["start"])


class DurationFail(unittest.TestCase):
    def test_short_outside_frozen_range_exits_1(self):
        slow = fitting()
        tl = make_timeline(lambda sid: slow(sid) * 0.8)  # every Short ~20% too short
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tl.json").write_text(json.dumps(tl))
            out = subprocess.run([sys.executable, "-I", "-B", str(HERE / "timing.py"), str(Path(d) / "tl.json"),
                                  str(PROJECT / "scenes.json"), str(Path(d) / "out"), str(CRITERIA_PATH)],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
            self.assertTrue(out.stdout.startswith("SHORT_DURATION short1 "), out.stdout)
            total = float(out.stdout.split()[2])
            self.assertLess(total, 41.0)
            self.assertTrue((Path(d) / "out" / "timing.json").is_file())
            self.assertFalse((Path(d) / "out" / "shorts-map.json").exists())

    def test_cli_writes_both_files_when_inside_range(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tl.json").write_text(json.dumps(make_timeline(fitting())))
            out = subprocess.run([sys.executable, "-I", "-B", str(HERE / "timing.py"), str(Path(d) / "tl.json"),
                                  str(PROJECT / "scenes.json"), str(Path(d) / "out")], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            m = json.loads((Path(d) / "out" / "shorts-map.json").read_text())
            self.assertEqual(sorted(m), ["short1", "short2"])

    def test_too_long_without_trimmable_scene_fails(self):
        tl = make_timeline(lambda sid: fitting()(sid) * 1.2)
        short1 = dict(SCENES["shorts"]["short1"])
        with self.assertRaises(timing.TimingError) as ctx:
            timing.short_spans("short1", short1, tl, CRITERIA["shorts"]["duration_seconds"]["short1"])
        self.assertTrue(str(ctx.exception).startswith("SHORT_DURATION short1 "))


if __name__ == "__main__":
    unittest.main()
