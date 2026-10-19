import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import qa_animation as qa  # noqa: E402
import render_identity as ri  # noqa: E402
import timing  # noqa: E402
from pilot_render import LEAD_IN, SENTENCE_GAP, sentences  # noqa: E402

PROJECT = HERE / "the-bag-he-almost-passed"
CRITERIA_PATH = HERE / "qa_criteria_animation_v1.json"
CRITERIA = json.loads(CRITERIA_PATH.read_text())
CRITERIA_SHA = ri.sha256_file(CRITERIA_PATH)
SCRIPT = json.loads((PROJECT / "script.json").read_text())
SCENES = json.loads((PROJECT / "scenes.json").read_text())
QUOTE, CTA = CRITERIA["scripture"]["quote"], CRITERIA["cta"]["text"]


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def clip(path, w, h, fps=24, pix="yuv420p", rate=48000, layout="stereo", seconds=0.5, volume_db=None):
    """A tiny real clip: test pattern video plus a 1 kHz sine (the lavfi sine is -18 dBFS before volume)."""
    audio = f"sine=frequency=1000:sample_rate={rate}:duration={seconds}"
    af = (f"volume={volume_db}dB," if volume_db is not None else "") + \
        ("pan=stereo|c0=c0|c1=c0" if layout == "stereo" else "pan=mono|c0=c0")
    ffmpeg("-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate={fps}:duration={seconds}", "-f", "lavfi", "-i", audio,
           "-af", af, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", pix, "-c:a", "aac", "-shortest", str(path))


# ---------------------------------------------------------------- full synthetic render (every row PASS)

def make_timeline(per_word):
    cursor, segments, spoken = LEAD_IN, [], []
    for seg in SCRIPT["segments"]:
        start = cursor
        for text in sentences(seg["text"]):
            length = len(text.split()) * per_word(seg["id"])
            spoken.append({"segment": seg["id"], "text": text, "start": round(cursor, 3), "end": round(cursor + length, 3)})
            cursor += length + SENTENCE_GAP
        segments.append({"id": seg["id"], "start": round(start, 3), "end": round(cursor, 3)})
        cursor += seg["pause_after"]
    return {"segments": segments, "sentences": spoken, "voice_seconds": round(cursor, 3)}


def calibrated_timeline():
    """short1 42 s, short2 41 s, S15 4 s, master voice 151.6 s."""
    texts = {s["id"]: sentences(s["text"]) for s in SCRIPT["segments"]}

    def k(ids, target):
        words = sum(len(t.split()) for i in ids for t in texts[i])
        return (target - 4.0 - SENTENCE_GAP * sum(len(texts[i]) - 1 for i in ids)) / words
    s1 = [s for s in SCENES["shorts"]["short1"]["scenes"] if s != "S15"]
    s2 = [s for s in SCENES["shorts"]["short2"]["scenes"] if s != "S15"]
    k1, k2, cta = k(s1, 42.0), k(s2, 41.0), 4.0 / len(texts["S15"][0].split())

    def fn(k0):
        return lambda sid: cta if sid == "S15" else k1 if sid in s1 else k2 if sid in s2 else k0
    a, b = make_timeline(fn(0.0))["voice_seconds"], make_timeline(fn(1.0))["voice_seconds"]
    return make_timeline(fn((151.6 - a) / (b - a)))


def srt_time(t):
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def write_srt(path, cues):
    path.write_text("".join(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text']}\n\n"
                            for i, c in enumerate(cues, 1)), encoding="utf-8")


def short_sentences(timeline, spans):
    out, offset = [], 0.0
    for sp in spans:
        for s in timeline["sentences"]:
            if s["segment"] == sp["scene"] and s["start"] >= sp["master_start_s"] and s["end"] <= sp["master_end_s"]:
                out.append({"text": s["text"], "start": offset + s["start"] - sp["master_start_s"],
                            "end": offset + s["end"] - sp["master_start_s"]})
        offset += sp["master_end_s"] - sp["master_start_s"]
    return out


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def build_full(d):
    d = Path(d)
    shutil.copy(PROJECT / "script.json", d / "script.json")
    shutil.copy(PROJECT / "scenes.json", d / "scenes.json")
    tl = calibrated_timeline()
    (d / "timeline.json").write_text(json.dumps(tl))
    t = timing.scene_timing(tl, SCENES)
    m = timing.shorts_map(tl, SCENES, CRITERIA)
    (d / "timing.json").write_text(json.dumps(t))
    (d / "shorts-map.json").write_text(json.dumps(m))
    s14 = next(s for s in t["scenes"] if s["id"] == "S14")
    hold_from = s14["end_frame"] - 48
    frames = {str(i): sha("hold" if hold_from <= i < s14["end_frame"] else str(i)) for i in range(t["frames_total"])}
    (d / "frames.json").write_text(json.dumps(frames))
    per_output = {"master": [dict(s) for s in tl["sentences"]]}
    for name in m:
        per_output[name] = short_sentences(tl, m[name]["spans"])
    for name, sents in per_output.items():
        write_srt(d / f"{name}.srt", sents)
    cards = {}
    for name, sents in per_output.items():
        cards[name] = {"cta": {"text": CTA, "start_s": sents[-1]["start"], "end_s": sents[-1]["end"] + 0.4}}
        q = [s for s in sents if QUOTE in s["text"]]
        if q:
            cards[name]["scripture"] = {"text": QUOTE, "reference": "Matthew 22:39", "translation": "KJV",
                                        "start_s": q[0]["start"] + 0.5, "end_s": q[0]["end"]}
    ident = {"script_sha256": ri.sha256_file(d / "script.json"), "scenes_sha256": ri.sha256_file(d / "scenes.json"),
             "voice_wav_sha256": "c" * 64, "music_sha256": "d" * 64,
             "srt_sha256": {f"{n}.srt": ri.sha256_file(d / f"{n}.srt") for n in per_output},
             "bundle_sha256": {"scene_base.py": "e" * 64}, "blender_version": "4.3.2", "engine": "BLENDER_EEVEE_NEXT",
             "samples": 16, "fps": 24, "resolution": "1920x1080", "criteria_sha256": CRITERIA_SHA}
    manifest = {
        "render_identity": ident, "render_id": ri.render_id(ident),
        "outputs": {"master": {"render_width": 1920, "render_height": 1080, "camera": "master"},
                    **{n: {"render_width": 1080, "render_height": 1920, "camera": "vertical"} for n in m}},
        "cards": cards,
        "asr": {n: " ".join(s["text"] for s in sents) for n, sents in per_output.items()},
        "voice_model_sha256": "f" * 64, "singing_presence": 0.0, "music": {"generator": "owned", "sha256": "d" * 64},
        "music_under_voice_db": 15.0, "burned_phrases": {n: ["He saw it happen.", "Daniel stopped"] for n in m},
        "rerender_check": {"frames": {"0": frames["0"], "240": frames["240"]}},
        "rights": {k: v for k, v in CRITERIA["rights"].items()},
    }
    (d / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False))
    for name in per_output:
        (d / f"{name}.mp4").write_bytes(b"")  # presence only; probe/loudness/decode are injected
    probes = {"master": {"width": 1920, "height": 1080, "codec": "h264", "pix_fmt": "yuv420p", "fps": 24.0,
                         "duration": round(tl["voice_seconds"] + 0.4, 3), "video_duration": round(tl["voice_seconds"] + 0.4, 3),
                         "audio": [{"codec": "aac", "sample_rate": 48000, "channels": 2,
                                    "duration": round(tl["voice_seconds"] + 0.41, 3)}]}}
    for name in m:
        dur = m[name]["total_s"] + 0.3
        probes[name] = {"width": 1080, "height": 1920, "codec": "h264", "pix_fmt": "yuv420p", "fps": 24.0,
                        "duration": dur, "video_duration": dur,
                        "audio": [{"codec": "aac", "sample_rate": 48000, "channels": 2, "duration": dur}]}
    return {"probes": probes, "frames_total": t["frames_total"], "timeline": tl, "manifest": manifest}


class Fake:
    def __init__(self, fx, loud=None, decode=None):
        self.fx, self.loud_v, self.decode_v = fx, loud, decode

    def probe(self, path):
        return self.fx["probes"][Path(path).stem]

    def loud(self, path):
        return self.loud_v or {"integrated_lufs": -15.0, "true_peak_dbtp": -2.0}

    def decode(self, path):
        return self.decode_v or {"ok": True, "frames": self.fx["frames_total"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.fx = build_full(self.d)
        self.fake = Fake(self.fx)

    def tearDown(self):
        self.tmp.cleanup()

    def ev(self, real_tools=False):
        if real_tools:
            return qa.Evidence(self.d, CRITERIA, CRITERIA_SHA)
        return qa.Evidence(self.d, CRITERIA, CRITERIA_SHA, probe=self.fake.probe, loudness=self.fake.loud,
                           decode=self.fake.decode)

    def row(self, section, key, out=None, ev=None):
        return qa.check_row(ev or self.ev(), section, key, CRITERIA[section][key], out)

    def status(self, section, key, out=None, ev=None):
        return self.row(section, key, out, ev)["status"]

    def edit_manifest(self, fn):
        p = self.d / "manifest.json"
        m = json.loads(p.read_text())
        fn(m)
        p.write_text(json.dumps(m, ensure_ascii=False))


class EndToEnd(Base):
    def test_full_fixture_every_row_passes(self):
        report = qa.evaluate(self.ev())
        bad = [r for r in report["rows"] if r["status"] != "PASS"]
        self.assertEqual(bad, [])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["criteria_sha256"], CRITERIA_SHA)
        self.assertEqual(report["render_id"], self.fx["manifest"]["render_id"])
        ids = {r["id"].split("[")[0] for r in report["rows"]}
        for section, body in CRITERIA.items():
            if isinstance(body, dict):
                for key in body:
                    if (section, key) not in qa.DESCRIPTIVE:
                        self.assertIn(f"{section}.{key}", ids)
        self.assertIn("scripture.card_text_exactly[short1]", {r["id"] for r in report["rows"]})

    def test_main_writes_qa_json(self):
        rc = qa.main(["qa", str(self.d), str(CRITERIA_PATH)], probe=self.fake.probe, loudness=self.fake.loud,
                     decode=self.fake.decode)
        self.assertEqual(rc, 0)
        data = json.loads((self.d / "qa.json").read_text())
        self.assertEqual(sorted(data), ["criteria_sha256", "render_id", "rows", "status"])
        self.assertEqual(sorted(data["rows"][0]), ["id", "limit", "status", "value"])

    def test_criteria_sha_mismatch_exits_2(self):
        other = self.d / "criteria.json"
        other.write_text(CRITERIA_PATH.read_text().replace('"integrated_lufs": [-16.0, -14.0]', '"integrated_lufs": [-30.0, 0.0]'))
        out = subprocess.run([sys.executable, "-I", "-B", str(HERE / "qa_animation.py"), str(self.d), str(other)],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("CRITERIA_SHA_MISMATCH", out.stdout)
        self.assertFalse((self.d / "qa.json").exists())

    def test_absent_evidence_is_unknown_never_pass(self):
        with tempfile.TemporaryDirectory() as empty:
            out = subprocess.run([sys.executable, "-I", "-B", str(HERE / "qa_animation.py"), empty, str(CRITERIA_PATH)],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
            data = json.loads((Path(empty) / "qa.json").read_text())
        self.assertNotIn("PASS", {r["status"] for r in data["rows"]})
        fails = [r["id"] for r in data["rows"] if r["status"] == "FAIL"]
        self.assertEqual(fails, ["subtitles.srt_present_for_master_and_each_short"])  # absence is what it checks
        self.assertEqual(data["status"], "FAIL")

    def test_optional_evidence_absent_is_unknown(self):
        self.edit_manifest(lambda m: [m.pop(k) for k in ("asr", "singing_presence", "rerender_check", "rights")])
        report = qa.evaluate(self.ev())
        by = {r["id"]: r["status"] for r in report["rows"]}
        for rid in ("audio.wer_vs_script_max", "audio.singing_presence_max", "scripture.spoken_exactly[master]",
                    "cta.spoken_exactly_in_master_and_each_short[short2]",
                    "continuity.chunk_boundary_frames_identical_on_rerender", "rights.no_third_party_footage_or_characters"):
            self.assertEqual(by[rid], "UNKNOWN", rid)
        self.assertEqual(report["status"], "UNKNOWN")


class Resolution(Base):
    """Real tiny clips probed with ffprobe."""

    def test_pass(self):
        clip(self.d / "master.mp4", 1920, 1080)
        clip(self.d / "short1.mp4", 1080, 1920)
        ev = self.ev(real_tools=True)
        for key in ("width", "height", "codec", "pix_fmt", "fps", "native_render", "upscaled", "audio"):
            self.assertEqual(self.status("master", key, "master", ev), "PASS", key)
        for key in ("width", "height", "codec", "pix_fmt", "fps", "native_render", "upscaled", "cropped_from_master"):
            self.assertEqual(self.status("shorts", key, "short1", ev), "PASS", key)
        self.assertEqual(self.status("master", "full_decode_without_errors", "master", ev), "PASS")

    def test_fail(self):
        clip(self.d / "master.mp4", 1280, 720, fps=25, pix="yuv444p", rate=44100, layout="mono")
        clip(self.d / "short1.mp4", 1080, 1920)
        self.edit_manifest(lambda m: m["outputs"].update(
            master={"render_width": 960, "render_height": 540, "camera": "master"},
            short1={"render_width": 1080, "render_height": 1920, "camera": "master"}))
        ev = self.ev(real_tools=True)
        for key in ("width", "height", "pix_fmt", "fps", "native_render", "upscaled", "audio"):
            self.assertEqual(self.status("master", key, "master", ev), "FAIL", key)
        self.assertEqual(self.status("shorts", "cropped_from_master", "short1", ev), "FAIL")
        (self.d / "master.mp4").write_bytes(b"not a video")
        self.assertEqual(self.status("master", "full_decode_without_errors", "master", self.ev(real_tools=True)), "FAIL")


class Duration(Base):
    """Probe values injected (rendering 152 s is not needed to test the check)."""

    def test_pass(self):
        self.fx["probes"]["master"].update(duration=152.0, video_duration=152.0)
        self.fx["probes"]["master"]["audio"][0]["duration"] = 152.03
        self.fx["probes"]["short1"]["duration"] = 42.0
        self.assertEqual(self.status("master", "duration_seconds", "master"), "PASS")
        self.assertEqual(self.status("master", "av_duration_delta_seconds_max", "master"), "PASS")
        self.assertEqual(self.status("shorts", "duration_seconds", "short1"), "PASS")
        self.assertEqual(self.status("shorts", "source_speed", "short1"), "PASS")

    def test_fail(self):
        self.fx["probes"]["master"].update(duration=150.5, video_duration=150.5)
        self.fx["probes"]["master"]["audio"][0]["duration"] = 150.7
        self.fx["probes"]["short1"]["duration"] = 44.0
        self.fx["probes"]["short2"]["duration"] = 39.5
        self.assertEqual(self.status("master", "duration_seconds", "master"), "FAIL")
        self.assertEqual(self.status("master", "av_duration_delta_seconds_max", "master"), "FAIL")
        self.assertEqual(self.status("shorts", "duration_seconds", "short1"), "FAIL")
        self.assertEqual(self.status("shorts", "duration_seconds", "short2"), "FAIL")
        self.assertEqual(self.status("shorts", "source_speed", "short1"), "FAIL")  # 42/44 < 0.98


class Fluidity(Base):
    def test_pass_with_declared_hold_exempt(self):
        for key in ("unique_render_fps_min", "unique_frame_ratio_min", "hold_seconds_max"):
            self.assertEqual(self.status("fluidity", key), "PASS", key)
        self.assertEqual(self.row("fluidity", "unique_frame_ratio_min")["value"], 1.0)
        self.assertEqual(self.status("continuity", "frame_set_contiguous_no_missing_no_duplicate_index"), "PASS")

    def test_fail_duplicated_frames(self):
        n = self.fx["frames_total"]
        (self.d / "frames.json").write_text(json.dumps({str(i): sha(str(i // 2)) for i in range(n)}))  # 12 fps doubled
        row = self.row("fluidity", "unique_frame_ratio_min")
        self.assertEqual(row["status"], "FAIL")
        self.assertLess(row["value"], 0.6)
        self.edit_manifest(lambda m: m["render_identity"].update(fps=10))
        self.assertEqual(self.status("fluidity", "unique_render_fps_min"), "FAIL")

    def test_fail_undeclared_hold_and_long_hold(self):
        n = self.fx["frames_total"]
        frames = {str(i): sha("still" if 100 <= i < 300 else str(i)) for i in range(n)}  # 8 s frozen, not declared
        (self.d / "frames.json").write_text(json.dumps(frames))
        self.assertEqual(self.status("fluidity", "unique_frame_ratio_min"), "FAIL")
        scenes = json.loads((self.d / "scenes.json").read_text())
        scenes["scenes"][13]["hold"]["seconds"] = 3.0
        (self.d / "scenes.json").write_text(json.dumps(scenes))
        self.assertEqual(self.status("fluidity", "hold_seconds_max"), "FAIL")

    def test_fail_missing_and_duplicate_index(self):
        frames = json.loads((self.d / "frames.json").read_text())
        del frames["17"]
        (self.d / "frames.json").write_text(json.dumps(frames))
        self.assertEqual(self.status("continuity", "frame_set_contiguous_no_missing_no_duplicate_index"), "FAIL")
        self.assertEqual(self.status("continuity", "every_scene_in_scenes_json_rendered"), "FAIL")
        text = json.dumps({"0": "a" * 64, "1": "b" * 64})[:-1] + ', "1": "' + "c" * 64 + '"}'
        (self.d / "frames.json").write_text(text)
        self.assertEqual(self.status("continuity", "frame_set_contiguous_no_missing_no_duplicate_index"), "FAIL")


class Loudness(Base):
    """Real clips measured with ffmpeg ebur128."""

    def test_pass(self):
        clip(self.d / "master.mp4", 64, 64, seconds=2.0, volume_db=3)  # 1 kHz sine at -15 dBFS peak ~ -15 LUFS
        ev = self.ev(real_tools=True)
        self.assertEqual(self.status("audio", "integrated_lufs", "master", ev), "PASS",
                         self.row("audio", "integrated_lufs", "master", ev))
        self.assertEqual(self.status("audio", "true_peak_dbtp_max", "master", ev), "PASS")

    def test_fail(self):
        clip(self.d / "master.mp4", 64, 64, seconds=2.0, volume_db=17.9)  # near full scale
        ev = self.ev(real_tools=True)
        self.assertEqual(self.status("audio", "integrated_lufs", "master", ev), "FAIL")
        self.assertEqual(self.status("audio", "true_peak_dbtp_max", "master", ev), "FAIL",
                         self.row("audio", "true_peak_dbtp_max", "master", ev))
        clip(self.d / "short1.mp4", 64, 64, seconds=2.0, volume_db=-12)
        self.assertEqual(self.status("audio", "integrated_lufs", "short1", self.ev(real_tools=True)), "FAIL")


class Subtitles(Base):
    def test_pass(self):
        self.assertEqual(self.status("subtitles", "srt_present_for_master_and_each_short"), "PASS")
        for out in ("master", "short1", "short2"):
            for key in ("text_equals_narration_exactly", "cue_start_offset_seconds_max", "cue_end_offset_seconds_max"):
                self.assertEqual(self.status("subtitles", key, out), "PASS", (key, out))

    def test_fail_text_timing_and_missing(self):
        cues = qa.parse_srt((self.d / "master.srt").read_text())
        cues[2]["text"] = cues[2]["text"].replace("Eli", "Ely")
        cues[5]["start"] += 0.3
        cues[6]["end"] += 0.4
        write_srt(self.d / "master.srt", cues)
        self.assertEqual(self.status("subtitles", "text_equals_narration_exactly", "master"), "FAIL")
        self.assertEqual(self.status("subtitles", "cue_start_offset_seconds_max", "master"), "UNKNOWN")  # unaligned text
        cues[2]["text"] = cues[2]["text"].replace("Ely", "Eli")
        write_srt(self.d / "master.srt", cues)
        self.assertEqual(self.status("subtitles", "cue_start_offset_seconds_max", "master"), "FAIL")
        self.assertEqual(self.status("subtitles", "cue_end_offset_seconds_max", "master"), "FAIL")
        short = qa.parse_srt((self.d / "short2.srt").read_text())
        write_srt(self.d / "short2.srt", short[:-1])
        self.assertEqual(self.status("subtitles", "text_equals_narration_exactly", "short2"), "FAIL")
        (self.d / "short1.srt").unlink()
        self.assertEqual(self.status("subtitles", "srt_present_for_master_and_each_short"), "FAIL")
        self.assertEqual(self.status("subtitles", "text_equals_narration_exactly", "short1"), "UNKNOWN")
        self.edit_manifest(lambda m: m["burned_phrases"].update(short1=["one two three four five six"]))
        self.assertEqual(self.status("subtitles", "shorts_burned_phrase_words", "short1"), "FAIL")


class Scripture(Base):
    def test_pass(self):
        ev = self.ev()
        self.assertEqual(ev.scripture_outputs(), ["master", "short1"])
        self.assertEqual(self.status("scripture", "quote"), "PASS")
        for out in ("master", "short1"):
            for key in ("reference", "translation", "spoken_exactly", "card_text_exactly", "card_only_while_spoken"):
                self.assertEqual(self.status("scripture", key, out), "PASS", (key, out))

    def test_fail(self):
        def bad(m):
            card = m["cards"]["master"]["scripture"]
            card.update(text="Thou shalt love thy neighbor as thyself.", reference="Matthew 22:39 (KJV)",
                        translation="NIV", end_s=card["end_s"] + 2.0)
            m["asr"]["master"] = m["asr"]["master"].replace("neighbour as thyself", "neighbour as yourself")
        self.edit_manifest(bad)
        for key in ("reference", "translation", "spoken_exactly", "card_text_exactly", "card_only_while_spoken"):
            self.assertEqual(self.status("scripture", key, "master"), "FAIL", key)
        script = json.loads((self.d / "script.json").read_text())
        script["segments"][5]["text"] = script["segments"][5]["text"].replace("neighbour", "neighbor")
        (self.d / "script.json").write_text(json.dumps(script, ensure_ascii=False))
        self.assertEqual(self.status("scripture", "quote"), "FAIL")


class Cta(Base):
    def test_pass(self):
        self.assertEqual(self.status("cta", "text"), "PASS")
        self.assertEqual(self.status("cta", "position"), "PASS")
        for out in ("master", "short1", "short2"):
            self.assertEqual(self.status("cta", "spoken_exactly_in_master_and_each_short", out), "PASS")
            self.assertEqual(self.status("cta", "on_screen_exactly_in_master_and_each_short", out), "PASS")
        for out in ("short1", "short2"):
            self.assertEqual(self.status("shorts", "self_contained_cta", out), "PASS")

    def test_fail(self):
        def bad(m):
            m["cards"]["short2"]["cta"]["text"] = "Subscribe for more stories."
            m["asr"]["short1"] = m["asr"]["short1"].replace("everyday faith.", "everyday life.")
        self.edit_manifest(bad)
        self.fx["probes"]["master"]["duration"] = self.fx["timeline"]["voice_seconds"] + 2.0
        self.assertEqual(self.status("cta", "position"), "FAIL")
        self.assertEqual(self.status("cta", "on_screen_exactly_in_master_and_each_short", "short2"), "FAIL")
        self.assertEqual(self.status("cta", "spoken_exactly_in_master_and_each_short", "short1"), "FAIL")
        smap = json.loads((self.d / "shorts-map.json").read_text())
        smap["short1"]["spans"] = smap["short1"]["spans"][:-1]
        (self.d / "shorts-map.json").write_text(json.dumps(smap))
        self.assertEqual(self.status("shorts", "self_contained_cta", "short1"), "FAIL")
        tl = json.loads((self.d / "timeline.json").read_text())
        tl["sentences"][-1]["text"] = "Like and subscribe."
        (self.d / "timeline.json").write_text(json.dumps(tl))
        self.assertEqual(self.status("cta", "text"), "FAIL")


class Identity(Base):
    def test_pass_and_fail(self):
        self.assertEqual(self.status("render_identity", "fields"), "PASS")
        self.assertEqual(self.status("render_identity", "rule"), "PASS")
        self.edit_manifest(lambda m: m["render_identity"].update(samples=32))
        self.assertEqual(self.status("render_identity", "rule"), "FAIL")
        (self.d / "master.srt").write_text((self.d / "master.srt").read_text() + "\n")
        self.assertEqual(self.status("render_identity", "fields"), "FAIL")


if __name__ == "__main__":
    unittest.main()
