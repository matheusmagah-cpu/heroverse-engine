#!/usr/bin/env python3
"""Offline: qa_pilot.py reads the frozen story QA v3 for the acted Bible-story long (E126). Every v3 row maps to a
check, no footage minimum comes back (owner, 2026-10-27: "Libera o pavo no longo"), the .srt track is measured
against the script and the voice timeline, and the older criteria keep their own grammar. No instrument, network
or secret: the grammar is read from a manifest fixture."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "publish"))
import qa_pilot as q  # noqa: E402
import captions  # noqa: E402

V3 = json.loads((HERE / "qa_criteria_story_v3.json").read_text())
V1 = json.loads((HERE / "qa_criteria_story_v1.json").read_text())
APPROVED = {"adam", "eve", "serpent", "keeper", "noah"}
LINES = [("eve", "He says you will not die. He says your eyes will be opened, and you will see."),
         (None, "In the beginning God created the heaven and the earth."),
         ("keeper", "Stay with me, because this is where everything we know about the world starts to break."),
         (None, "And the LORD God commanded the man, saying, Of every tree of the garden thou mayest freely eat.")]
# the checks main() measures itself (decode, ffprobe, loudness, ASR, music, voice, KJV), not the grammar function
MAIN_CHECKS = {"full_decode_without_errors", "video_format", "duration_min", "integrated_lufs", "true_peak",
               "speech_presence", "no_singing", "wer_vs_script", "words_per_minute", "first_word_onset",
               "hook_second_person", "music_owned", "voice_model_pinned", "scripture_kjv_exact"}


def timeline():
    out, t = [], 0.0
    for k, (who, text) in enumerate(LINES):
        end = round(t + len(text.split()) / 2.6, 3)
        out.append({"segment": f"n{k:02d}", "text": text, "start": round(t, 3), "end": end,
                    **({"speaker": who} if who else {})})
        t = end + 0.6
    return out


def clip(cid, **kw):
    ai = V3["rights"]["ai_video"]
    return {"id": cid, "source": "pavo", "licence": ai["licence"], "model": ai["model"], "upscaler": ai["upscaler"],
            "audio": "removed", "vetting": "APPROVED", "credit": "Pavo generated (owner-owned)", "sha256": "a" * 64,
            "clip_check": "PASS", **kw}


def manifest(base):
    sents = timeline()
    total = sents[-1]["end"] + 1.0
    holds, t, i = [], 0.0, 0
    beats = ["cold_open", "cold_open", "keeper_promise", "chapter", "chapter", "chapter"]
    who = [["eve"], ["adam"], ["keeper"], [], ["serpent"], ["adam", "eve"]]
    while t < total - 1e-6:
        end = min(t + 5.5, total) if total - t - 5.5 >= 4.0 or total - t <= 7.0 else t + 5.0
        n = i % len(beats)
        holds.append({"start": round(t, 3), "end": round(end, 3), "image": f"c{i}", "kind": "footage", "motion": True,
                      "beat": beats[n], "characters": who[n], **({"shot_kind": "keeper"} if beats[n] == "keeper_promise" else {})})
        t, i = end, i + 1
    text, record = captions.track_record(sents)
    (Path(base) / record["file"]).write_text(text)
    clips = [clip(f"c{k}", **({"talking": True, "lipsync_check": "PASS"} if holds[k]["beat"] != "chapter" else {}))
             for k in range(len(holds))]
    return {"pilot_id": "pilot-015", "holds": holds, "sentences": sents, "clips": clips, "images": {},
            "crossfade_seconds": 0.0, "burned_captions": False, "captions": [], "persistent_overlays": ["brand"],
            "cta": [], "scripture_cards": [], "caption_track": record, "output_seconds": round(total, 3)}


def script():
    return {"segments": [{"id": s["segment"], "text": s["text"]} for s in timeline()]}


def asr(sents):
    words = []
    for s in sents:
        ws = s["text"].split()
        for k, w in enumerate(ws):
            words.append({"word": w, "start_seconds": s["start"] + (s["end"] - s["start"]) * k / len(ws)})
    return words


class StoryV3Rows(unittest.TestCase):
    def test_every_frozen_v3_row_maps_to_a_check_that_is_measured(self):
        rows = sorted(f"{s}.{k}" for s in ("technical", "speech", "rights", "grammar") for k in V3[s])
        self.assertEqual(sorted(q.STORY_V3_ROWS), rows)
        with tempfile.TemporaryDirectory() as d:
            checks, _ = q.grammar_checks_story_v3(V3, manifest(d), script(), asr(timeline()), 0.0, None, d, APPROVED)
        produced = set(checks) | MAIN_CHECKS
        for row, names in q.STORY_V3_ROWS.items():
            self.assertTrue(names, row)
            self.assertEqual(set(names) - produced, set(), row)

    def test_a_good_acted_long_passes_every_grammar_row_with_no_footage_minimum(self):
        with tempfile.TemporaryDirectory() as d:
            checks, measures = q.grammar_checks_story_v3(V3, manifest(d), script(), asr(timeline()), 0.0, None, d,
                                                         APPROVED)
        self.assertEqual({k: v for k, v in checks.items() if v is not True}, {}, measures)
        self.assertNotIn("footage_picture_share", checks)          # v3 has no footage minimum (owner, 27/10)
        self.assertNotIn("footage_picture_share_min", V3["grammar"])
        self.assertEqual(V3["grammar"]["ai_video_picture_share_max"], 1.0)
        states = q.row_states({**checks, **{c: True for c in MAIN_CHECKS}})
        self.assertEqual(set(states.values()), {"PASS"})

    def test_the_v3_reader_is_chosen_by_version_and_v1_keeps_its_own_rows(self):
        src = (HERE / "qa_pilot.py").read_text()
        self.assertIn('criteria["version"] == STORY_V3', src)
        self.assertEqual(q.STORY_V3, V3["version"])
        # story v1 (frozen) still measures its footage minimum, unchanged
        self.assertIn("footage_picture_share_min", V1["grammar"])
        self.assertIn('g["footage_picture_share_min"]', src)

    def test_each_acted_long_row_fails_its_defect(self):
        def check(change, key):
            with tempfile.TemporaryDirectory() as d:
                m = manifest(d)
                change(m, d)
                checks, _ = q.grammar_checks_story_v3(V3, m, script(), asr(m["sentences"]), m["sentences"][0]["start"],
                                                      None, d, APPROVED)
            return checks[key]

        self.assertFalse(check(lambda m, d: m["holds"][0].update(characters=["keeper"], shot_kind="keeper"),
                               "first_shot_cold_open"))                       # never the Keeper in the cold open
        self.assertFalse(check(lambda m, d: m["holds"][0].update(title_card=True), "first_shot_cold_open"))
        self.assertFalse(check(lambda m, d: m["sentences"][0].pop("speaker"), "first_shot_cold_open"))  # narrator first
        self.assertFalse(check(lambda m, d: m["holds"][3].update(characters=["god"]), "figures_allowed"))
        self.assertFalse(check(lambda m, d: m["holds"][3].update(characters=["scoffer"]), "figures_allowed"))  # DRAFT
        self.assertFalse(check(lambda m, d: m["holds"][4].update(characters=["keeper"], shot_kind="keeper"),
                               "figures_allowed"))                            # the Keeper outside his beats
        self.assertIsNone(check(lambda m, d: m["holds"][3].pop("characters"), "figures_allowed"))
        self.assertFalse(check(lambda m, d: m["clips"][0].update(lipsync_check="FAIL"), "ai_video_clip_checks"))
        self.assertFalse(check(lambda m, d: m["clips"][3].update(clip_check=None), "ai_video_clip_checks"))
        self.assertFalse(check(lambda m, d: m["clips"][0].update(voiceover="god"), "ai_video_clip_checks"))
        self.assertIsNone(check(lambda m, d: m.update(clips=[]), "ai_video_clip_checks"))
        self.assertFalse(check(lambda m, d: m["clips"][0].update(model="other"), "ai_video_source_and_licence"))
        self.assertFalse(check(lambda m, d: m["clips"][0].update(audio="kept"), "ai_video_source_and_licence"))
        self.assertFalse(check(lambda m, d: m.update(burned_captions=True), "no_burned_captions"))
        self.assertFalse(check(lambda m, d: m.update(captions=[{"start": 0, "end": 1, "text": "x"}]),
                               "no_burned_captions"))
        self.assertFalse(check(lambda m, d: m["holds"][1].update(motion=False), "every_scene_in_motion"))
        self.assertFalse(check(lambda m, d: m["holds"][1].update(end=m["holds"][1]["start"] + 8), "scene_seconds"))

    def test_the_srt_track_is_measured_against_script_timeline_and_audio(self):
        def check(change, key="caption_track", words=True):
            with tempfile.TemporaryDirectory() as d:
                m = manifest(d)
                s = script()
                change(m, d, s)
                checks, _ = q.grammar_checks_story_v3(V3, m, s, asr(timeline()) if words else None, 0.0, None, d,
                                                      APPROVED)
            return checks[key]

        self.assertTrue(check(lambda m, d, s: None))
        # no track recorded: every caption row fails (never skipped)
        for key in ("caption_track", "srt_coverage_of_speech", "srt_cue_seconds_median", "srt_cue_chars_max",
                    "srt_cue_words_max"):
            self.assertFalse(check(lambda m, d, s: m.pop("caption_track"), key), key)
        self.assertFalse(check(lambda m, d, s: (Path(d) / "captions.srt").unlink()))            # the file is gone
        self.assertFalse(check(lambda m, d, s: (Path(d) / "captions.srt").write_text("1\n00:00:00,000 --> "
                                                                                   "00:00:01,000\nx\n")))
        self.assertFalse(check(lambda m, d, s: m["caption_track"].update(sha256="0" * 64)))
        # a word changed in the script (a KJV line misquoted on screen, or the voice not the script)
        self.assertFalse(check(lambda m, d, s: s["segments"][1].update(text=s["segments"][1]["text"].replace(
            "heaven", "heavens"))))
        # cue limits come from the record: a looser record fails the frozen rows
        def loose(m, d, s):
            text, rec = captions.track_record(m["sentences"], 20, 120)
            (Path(d) / rec["file"]).write_text(text)
            m["caption_track"] = rec
        self.assertFalse(check(loose, "srt_cue_words_max"))
        self.assertFalse(check(loose, "srt_cue_chars_max"))
        # coverage of the words heard: speech outside the timeline's cues is not covered
        def late_voice(m, d, s):
            m["sentences"] = [dict(x, start=x["start"], end=x["start"] + 0.5) for x in m["sentences"]]
            text, rec = captions.track_record(m["sentences"])
            (Path(d) / rec["file"]).write_text(text)
            m["caption_track"] = rec
        self.assertFalse(check(late_voice, "srt_coverage_of_speech"))

    def test_row_states_never_pass_a_missing_or_unknown_check(self):
        rows = {"a.x": ["one", "two"], "a.y": ["three"], "a.z": ["four"]}
        self.assertEqual(q.row_states({"one": True, "two": None, "three": False}, rows),
                         {"a.x": "UNKNOWN", "a.y": "FAIL", "a.z": "UNKNOWN"})

    def test_the_kjv_check_runs_on_the_voiced_script(self):
        good = {"scripture": [{"reference": "Genesis 1:1", "text": "In the beginning God created the heaven and the earth."}]}
        bad = copy.deepcopy(good)
        bad["scripture"][0]["text"] = "In the beginning God made the heavens and the earth."
        self.assertTrue(q.scripture_kjv_exact(good))
        self.assertFalse(q.scripture_kjv_exact(bad))

    def test_the_criteria_a_plan_is_checked_against_are_the_ones_the_gates_read(self):
        # E126 antidote: v3 was frozen and the long's plan checked against it (#418) while qa_pilot, render_queue
        # and prepublish_gate still knew only story v1, so no long could be measured or approved. Every frozen QA a
        # plan check reads must be pinned, with the same hash, by the readers that measure and gate the render.
        import re
        import hashlib
        import prepublish_gate
        import render_queue
        seen = 0
        for checker in sorted(HERE.glob("bible/*plan_check.py")):
            if checker.name.startswith("test_"):
                continue
            src = checker.read_text()
            for name in re.findall(r'"(qa_criteria[a-z0-9_]*\.json)"', src):
                crit = HERE / name
                version = json.loads(crit.read_text())["version"]
                sha = hashlib.sha256(crit.read_bytes()).hexdigest()
                where = f"{checker.name} -> {name}"
                self.assertEqual(prepublish_gate.FROZEN_CRITERIA_SHA256.get(version), sha, where)
                self.assertEqual(prepublish_gate.CRITERIA_FILES.get(version), crit, where)
                self.assertEqual(render_queue.STANDARD_QAS.get(version), sha, where)
                # qa_pilot reads it with its own grammar (main() branches on the version), never a fallback
                self.assertIn(f'"{version}"', (HERE / "qa_pilot.py").read_text(), where)
                pinned = re.search(r'QA_SHA256 = "([0-9a-f]{64})"', src)
                if pinned:
                    self.assertEqual(pinned.group(1), sha, where)
                seen += 1
        self.assertGreaterEqual(seen, 1)   # long_plan_check reads story QA v3

    def test_the_instruments_load_only_in_main(self):
        # importing the QA (the gate reads STORY_V3_ROWS) never loads the audio/video instruments
        self.assertNotIn("av_profile", sys.modules)
        self.assertNotIn("av_semantic", sys.modules)


if __name__ == "__main__":
    unittest.main()
