#!/usr/bin/env python3
"""Offline structural gates and unchanged media helpers against frozen input snapshots.

Windows on whole sentences (30-55 s, no context opener first, first word at the cut), captions of 1-5 words,
no CTA, the reference only while KJV text is spoken, the hook only when it is the first line's own words,
and no figure overlay in the ffmpeg call. Missing data is an error, never a pass.
"""
import hashlib
import inspect
import io
import json
import math
import os
from pathlib import Path
import re
import random
import subprocess
import sys
import tempfile
import unittest
import wave
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shorts_produce as sp  # noqa: E402
import shorts_select  # noqa: E402

PILOT = HERE / "fixtures" / "shorts-pilot-006"
OPENER = re.compile(r"(?i)^(and|but|so|then|this|that|it|he|she|they|because|or)\b")
CTA_TEXT = re.compile(r"(?i)subscribe|full prayer|on the channel|▶|\blike (this|the video)|\bshare (this|it)\b|\blink\b")
EPS = 0.05


def load(path):
    if not path.is_file():
        raise AssertionError(f"MISSING_TEST_DATA: {path}")
    return json.loads(path.read_text())


def secs(stamp):
    h, m, s = stamp.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def events(ass, style):
    out = []
    for line in ass.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if parts[3] == style:
                out.append((secs(parts[1]), secs(parts[2]), re.sub(r"\{[^}]*\}", "", parts[9])))
    return out


TIMELINE = load(PILOT / "out" / "timeline.json")
SCRIPT = load(PILOT / "script.json")
RECORDED = load(PILOT / "shorts" / "selection.json")
SENTENCES = TIMELINE["sentences"]
REFS = {s["id"]: s.get("reference") for s in SCRIPT["segments"]}


def offline_selection():
    """shorts_select on the real timeline with the measured score only (no network)."""
    key = os.environ.pop("HERO_GEMINI_API_KEY", None)
    try:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "selection.json"
            shorts_select.main(str(PILOT / "out" / "timeline.json"), str(PILOT / "script.json"), str(out), "3")
            return json.loads(out.read_text())["chosen"]
    finally:
        if key is not None:
            os.environ["HERO_GEMINI_API_KEY"] = key


OFFLINE = offline_selection()
# Frozen historical windows exercise media helpers, not the strict production gate.
WINDOWS, REJECTED = sp.snap_all(OFFLINE + RECORDED["chosen"], SENTENCES)


class Windows(unittest.TestCase):
    def test_historical_overlong_opening_is_an_explicit_negative(self):
        moment = RECORDED["chosen"][0]
        self.assertEqual(moment["start"], 1306.977)
        self.assertEqual(sp.snap_all([moment], SENTENCES, REFS)[0], [])
        self.assertEqual(sp.snap_all([moment], SENTENCES, REFS)[1][0]["reason"], "OPENING_OVER_3S")
        self.assertGreater(len(WINDOWS), 0, "historical media tests must not become empty loops")

    def test_there_are_windows(self):
        self.assertGreaterEqual(len(OFFLINE), 1, "offline selection chose nothing")
        self.assertEqual(len(sp.snap_all(OFFLINE, SENTENCES)[0]), len(OFFLINE), "a selected window broke R8")
        self.assertGreaterEqual(len(WINDOWS), 3)

    def test_sentence_boundaries(self):
        starts, ends = [s["start"] for s in SENTENCES], [s["end"] for s in SENTENCES]
        for w in WINDOWS:
            self.assertTrue(any(abs(w["start"] - x) <= EPS for x in starts), w["start"])
            self.assertTrue(any(abs(w["end"] - x) <= EPS for x in ends), w["end"])
            self.assertAlmostEqual(w["sentences"][0]["start"], w["start"], delta=EPS)
            self.assertAlmostEqual(w["sentences"][-1]["end"], w["end"], delta=EPS)
            self.assertRegex(w["sentences"][-1]["text"].strip(), r"[.!?]$")
            # contiguous: every timeline sentence inside the window is in it, none outside
            inside = [s for s in SENTENCES if s["start"] >= w["start"] - EPS and s["end"] <= w["end"] + EPS]
            self.assertEqual(inside, w["sentences"])

    def test_no_context_opener_and_length(self):
        for w in WINDOWS:
            self.assertIsNone(OPENER.match(w["sentences"][0]["text"].strip()), w["sentences"][0]["text"])
            self.assertTrue(30.0 <= w["end"] - w["start"] <= 55.0, w["end"] - w["start"])

    def test_first_word_at_the_cut(self):
        for w in WINDOWS:
            caps = events(sp.ass(w, w.get("hook"), REFS, w["end"] - w["start"] + sp.TAIL_S, SENTENCES), "Cap")
            self.assertLessEqual(caps[0][0], 0.3)
            self.assertLessEqual(w["sentences"][0]["start"] - w["start"], 0.3)

    def test_snap_inward_and_reject(self):
        # a moment cut mid-sentence on both sides snaps inward to whole sentences
        good = sp.snap(RECORDED["chosen"][0], SENTENCES)[0]
        i = SENTENCES.index(good["sentences"][0])
        z = SENTENCES.index(good["sentences"][-1])
        self.assertGreater(i, 0)
        raw = {"start": SENTENCES[i - 1]["start"] + 0.3, "end": SENTENCES[z + 1]["end"] - 0.3, "hook": None}
        w, why = sp.snap(raw, SENTENCES)
        self.assertIsNone(why)
        self.assertEqual(w["start"], SENTENCES[i]["start"])
        self.assertEqual(w["end"], SENTENCES[z]["end"])
        # a context opener first is dropped
        j = next(k for k, s in enumerate(SENTENCES) if OPENER.match(s["text"]))
        self.assertEqual(sp.snap({"start": SENTENCES[j]["start"], "end": SENTENCES[j]["start"] + 45}, SENTENCES)[1],
                         "CONTEXT_OPENER")
        # too short / too long is dropped (same opening sentence, only the length differs)
        short = [s for s in SENTENCES if s["start"] >= good["start"] and s["end"] - good["start"] < 30]
        self.assertTrue(sp.snap({"start": good["start"], "end": short[-1]["end"]}, SENTENCES)[1].startswith("LENGTH_"))
        k = z
        while SENTENCES[k]["end"] - good["start"] <= 55 or not SENTENCES[k]["text"].rstrip().endswith((".", "!", "?")):
            k += 1
        long_why = sp.snap({"start": good["start"], "end": SENTENCES[k]["end"]}, SENTENCES)[1]
        self.assertTrue(long_why.startswith(("LENGTH_", "CTA_")), long_why)


class Text(unittest.TestCase):
    def ass_of(self, w):
        return sp.ass(w, w.get("hook"), REFS, w["end"] - w["start"] + sp.TAIL_S, SENTENCES)

    def test_captions_1_to_5_words_on_the_sentence_clock(self):
        for w in WINDOWS:
            caps = events(self.ass_of(w), "Cap")
            self.assertTrue(caps)
            for a, b, text in caps:
                self.assertTrue(1 <= len(text.split()) <= 5, text)
                self.assertTrue(any(s["start"] - w["start"] - EPS <= a and b <= s["end"] - w["start"] + EPS
                                    for s in w["sentences"]), text)
            spoken = " ".join(s["text"] for s in w["sentences"]).split()
            self.assertEqual(" ".join(t for _, _, t in caps).split(), [sp.ass_text(x) for x in spoken])

    def test_caption_style(self):
        a = self.ass_of(WINDOWS[0])
        style = next(line for line in a.splitlines() if line.startswith("Style: Cap,")).split(",")
        self.assertEqual(style[3], "&H00FFFFFF")       # white
        self.assertEqual(style[7], "1")                 # bold
        self.assertEqual(style[15], "1")                # outline, no box
        self.assertGreater(int(style[16]), 0)
        for line in a.splitlines():
            if ",Cap," in line and line.startswith("Dialogue:"):
                self.assertIn(f"\\pos(540,{sp.CAPTION_Y})", line)
                self.assertIn("\\an5", line)
        self.assertEqual(sp.CAPTION_Y, 1150)

    def test_no_cta(self):
        for w in WINDOWS:
            a = self.ass_of(w)
            self.assertNotIn("Style: Cta", a)
            for line in a.splitlines():
                if line.startswith("Dialogue:"):
                    self.assertNotIn(",Cta,", line)
                    self.assertIsNone(CTA_TEXT.search(line), line)

    def test_reference_only_inside_kjv_sentences(self):
        seen = 0
        for w in WINDOWS:
            verse = sp.verse_sentences(SENTENCES, REFS)
            for a, b, ref in events(self.ass_of(w), "Ref"):
                seen += 1
                a, b = a + w["start"], b + w["start"]
                spoken = [s for s in w["sentences"] if s["start"] < b - EPS and s["end"] > a + EPS]
                self.assertTrue(spoken)
                for s in spoken:
                    self.assertIn(s, verse, s["text"])
                    self.assertEqual(REFS[s["segment"]], ref)
                self.assertGreaterEqual(a, spoken[0]["start"] - EPS)
                self.assertLessEqual(b, spoken[-1]["end"] + EPS)
        self.assertGreater(seen, 0, "no window with Scripture: the reference rule was not exercised")

    def test_verse_excludes_the_introduction(self):
        verse = sp.verse_sentences(SENTENCES, REFS)
        intro = next(s for s in SENTENCES if s["text"].startswith("The prophet Jeremiah prayed"))
        self.assertNotIn(intro, verse)
        self.assertIn(next(s for s in SENTENCES if s["text"].startswith("Heal me, O LORD")), verse)

    def test_hook_only_when_first_line(self):
        w = WINDOWS[0]
        first = w["sentences"][0]["text"]
        self.assertEqual(events(sp.ass(w, "Pray this with me right now", REFS, 40.0), "Hook"), [])
        own = " ".join(first.split()[:4])
        hooks = events(sp.ass(w, own, REFS, 40.0), "Hook")
        self.assertEqual(len(hooks), 1)
        self.assertLessEqual(hooks[0][1] - hooks[0][0], 2.5)

    def test_reference_enters_after_the_hook(self):
        m = {"start": 0.0, "sentences": [{"segment": "v", "start": 0.0, "end": 3.0, "text": "Thou art my strength."}]}
        a = sp.ass(m, "Thou art my strength", {"v": "Isaiah 40:31 (KJV)"}, 30.0)
        (h0, h1, _), (r0, r1, _) = events(a, "Hook")[0], events(a, "Ref")[0]
        self.assertGreaterEqual(r0, h1)
        self.assertLessEqual(r1, 3.0)

    def test_no_reference_no_line(self):
        m = {"start": 0.0, "sentences": [{"segment": "p", "start": 0.2, "end": 3.0, "text": "Renew my strength, Lord."}]}
        self.assertEqual(events(sp.ass(m, None, {"p": None}, 30.0), "Ref"), [])


class Picture(unittest.TestCase):
    def args(self, w):
        dur = w["end"] - w["start"] + sp.TAIL_S
        n, length = sp.scene_plan(dur)
        stills = [Path(f"/x/s{k:02d}.png") for k in range(n)]
        return dur, n, length, sp.render_args(stills, Path("/x/voice.wav"), Path("/x/music.flac"), Path("/x/s.ass"),
                                              w, dur, "vignette", Path("/x/short.mp4"))

    def test_no_figure_overlay(self):
        for w in WINDOWS:
            dur, n, length, args = self.args(w)
            graph = args[args.index("-filter_complex") + 1]
            self.assertNotIn("overlay", graph)
            self.assertNotIn("figure", " ".join(args))
            inputs = [args[k + 1] for k, a in enumerate(args) if a == "-i"]
            self.assertEqual(inputs, [f"/x/s{k:02d}.png" for k in range(n)] + ["/x/voice.wav", "/x/music.flac"])
            self.assertIn(f"s={sp.VW}x{sp.VH}", graph)
            self.assertEqual((sp.VW, sp.VH), (1080, 1920))

    def test_scenes_zoom_and_fades(self):
        for w in WINDOWS:
            dur, n, length, args = self.args(w)
            self.assertGreaterEqual(length, 15.0)
            graph = args[args.index("-filter_complex") + 1]
            self.assertEqual(graph.count("xfade"), n - 1)
            for d in re.findall(r"xfade=transition=fade:duration=([\d.]+)", graph):
                self.assertLessEqual(float(d), 0.6)
            self.assertEqual(graph.count("zoompan"), 1)  # one zoom over the whole Short, after the cross-fades
            self.assertIn("zoompan=z='min(1.06,1.00+0.06*on/", graph)
            self.assertLess(graph.index("xfade") if n > 1 else 0, graph.index("zoompan"))

    def test_voice_is_the_window(self):
        w = WINDOWS[0]
        _, _, _, args = self.args(w)
        k = args.index("/x/voice.wav")
        self.assertEqual(args[k - 5:k - 1], ["-ss", f"{w['start']:.3f}", "-t", f"{w['end'] - w['start']:.3f}"])



def sentence(segment, start, end, text):
    return {"segment": segment, "start": start, "end": end, "text": text}


def positive_source(offset=0.0):
    """Explicit synthetic structural positive; no claim of acoustic/editorial QA."""
    sentences = [
        sentence("opening", offset, offset + 3.0, "You can rest."),
        sentence("scripture-psalm-23", offset + 3.4, offset + 20.0,
                 "The LORD is my shepherd; I shall not want."),
        sentence("prayer-close", offset + 20.4, offset + 32.0,
                 "Father, help me meet this day with patience and kindness."),
    ]
    refs = {"opening": None, "scripture-psalm-23": "Psalm 23:1 (KJV)", "prayer-close": None}
    timeline = {"sentences": sentences, "segments": [
        {"id": s["segment"], "start": s["start"], "end": s["end"] + (0.18 if i == 2 else 0)}
        for i, s in enumerate(sentences)]}
    script = {"pilot_id": "synthetic-structural-only", "backgrounds": ["still-a", "still-b"],
              "segments": [{"id": key, "reference": value} for key, value in refs.items()]}
    return timeline, script, refs


def write_source(root, timeline, script):
    timeline_path, script_path = root / "timeline.json", root / "script.json"
    # Distinct whitespace/newline bytes deliberately test raw-byte hashes, not canonical JSON.
    timeline_path.write_bytes((json.dumps(timeline, indent=2) + "\n\n").encode())
    script_path.write_bytes((json.dumps(script, separators=(",", ":")) + "\n").encode())
    return timeline_path, script_path


class StructuralValidation(unittest.TestCase):
    def test_exact_positive_32_seconds_and_trailing_segment_silence(self):
        timeline, _, refs = positive_source()
        cands, counts = shorts_select.candidate_analysis(timeline["sentences"], refs)
        self.assertEqual(len(cands), 1)
        self.assertEqual((cands[0]["start"], cands[0]["end"]), (0.0, 32.0))
        self.assertEqual(cands[0]["sentences"], timeline["sentences"])
        self.assertEqual(timeline["segments"][-1]["end"], 32.18)
        self.assertEqual(counts, {"opening_starts_total": 3, "opening_starts_accepted": 1,
                                 "opening_rejections": {"OPENING_OVER_3S": 2},
                                 "window_pairs_total": 1, "window_pairs_accepted": 1,
                                 "window_rejections": {}})
        accepted, why = shorts_select.validate_candidate(timeline["sentences"], refs, {"start": 0, "end": 32})
        self.assertIsNone(why)
        self.assertEqual(accepted["end"], 32)
        # These are structural facts only, not fabricated semantic/acoustic/technical approval.
        self.assertNotIn("semantic_pass", accepted)
        self.assertNotIn("technical_qa", accepted)
        self.assertNotIn("watched_review", accepted)

    def test_public_candidates_reject_source_opening_regressions(self):
        for text, end in [("Carry that with you.", 3), ("You can rest:", 3),
                          ("you can rest.", 3), ("You carry that burden.", 3),
                          ("You can rest.", 3.001)]:
            with self.subTest(text=text, end=end):
                timeline, _, refs = positive_source()
                timeline["sentences"][0].update(text=text, end=end)
                self.assertEqual(shorts_select.candidates(timeline["sentences"], refs), [])

    def test_public_candidates_reject_unresolved_midsegment_period(self):
        timeline, _, refs = positive_source()
        timeline["sentences"].append(sentence("prayer-close", 32.18, 36.0, "We continue praying together."))
        candidates = shorts_select.candidates(timeline["sentences"], refs)
        self.assertGreater(len(candidates), 0, "the completed segment must remain a positive")
        self.assertEqual([(c["start"], c["end"]) for c in candidates], [(0.0, 36.0)])

    def test_public_candidates_reject_partial_scripture_with_amen(self):
        timeline, _, refs = positive_source()
        timeline["sentences"][2].update(segment="scripture-psalm-23", text="The LORD is good. Amen.")
        timeline["sentences"].append(sentence("scripture-psalm-23", 32.2, 40, "He restoreth my soul."))
        candidates = shorts_select.candidates(timeline["sentences"], refs)
        self.assertGreater(len(candidates), 0, "the full Scripture segment must remain a positive")
        self.assertEqual([(c["start"], c["end"]) for c in candidates], [(0.0, 40)])

    def test_overlong_opening_and_short_single_sentence_are_not_candidates(self):
        timeline, _, refs = positive_source()
        timeline["sentences"][0]["end"] = 3.001
        self.assertEqual(shorts_select.opening_reason(timeline["sentences"][0]), "OPENING_OVER_3S")
        self.assertEqual(shorts_select.candidates(timeline["sentences"], refs), [])
        first = sentence("opening", 0, 3, "You can rest.")
        self.assertIsNone(shorts_select.opening_reason(first))
        cands, counts = shorts_select.candidate_analysis([first], {"opening": None})
        self.assertEqual(cands, [])
        self.assertEqual(counts["opening_starts_accepted"], 1)
        self.assertEqual(counts["window_pairs_total"], 0)

    def test_opening_reason_priority_and_closed_reference_exception(self):
        cases = [
            ("", 1, "EMPTY_OR_INCOMPLETE_OPENING"),
            ("   ", 1, "EMPTY_OR_INCOMPLETE_OPENING"),
            ("And carry that:", 8, "EMPTY_OR_INCOMPLETE_OPENING"),
            ("You can rest:", 1, "EMPTY_OR_INCOMPLETE_OPENING"),
            ("And carry that.", 8, "CONTEXT_OPENER"),
            ("That God cares.", 1, "CONTEXT_OPENER"),
            ("This is hope.", 1, "CONTEXT_OPENER"),
            ("carry that with you.", 8, "DEPENDENT_OPENING_REFERENCE"),
            ("Carry that with you.", 2, "DEPENDENT_OPENING_REFERENCE"),
            ("You carry that burden.", 2, "DEPENDENT_OPENING_REFERENCE"),
            ("I know that burden.", 2, "DEPENDENT_OPENING_REFERENCE"),
            ("You need it now.", 2, "DEPENDENT_OPENING_REFERENCE"),
            ("You need this hope.", 2, "DEPENDENT_OPENING_REFERENCE"),
            ("You need those prayers.", 2, "DEPENDENT_OPENING_REFERENCE"),
            ("You need these prayers.", 2, "DEPENDENT_OPENING_REFERENCE"),
            ("you can rest.", 8, "CONTINUATION_OPENING_LINE"),
            ("... 123 you can rest.", 1, "CONTINUATION_OPENING_LINE"),
            ("123.", 1, "CONTINUATION_OPENING_LINE"),
            ("You can rest.", 3.001, "OPENING_OVER_3S"),
            ("I know that God cares.", 2, None),
            ("I believe that the Lord cares.", 2, None),
            ("I trust that Jesus cares.", 2, None),
            ("I pray that you rest.", 2, None),
            ("You can believe that he cares.", 2, None),
            ("I know that God cares:", 2, "EMPTY_OR_INCOMPLETE_OPENING"),
            ("I know that God cares.", 3.001, "OPENING_OVER_3S"),
            ("You can rest knowing this.", 2, None),  # token 4 is outside the first-four check
            ("  ‘You can rest.’  ", 2, "EMPTY_OR_INCOMPLETE_OPENING"),
            ("  ‘You can rest.  ", 2, None),
        ]
        for text, duration, reason in cases:
            with self.subTest(text=text, duration=duration):
                self.assertEqual(shorts_select.opening_reason(sentence("opening", 0, duration, text)), reason)
        self.assertEqual(shorts_select.tokens("You’re God’s child, 23:1."), ["you're", "god's", "child", "23", "1"])

    def test_exact_pilot005_carry_that_is_rejected(self):
        timeline = load(HERE / "fixtures" / "shorts-pilot-005-20261020" / "out" / "timeline.json")
        found = [s for s in timeline["sentences"] if s["text"] == "Carry that with you."]
        self.assertEqual(len(found), 1)
        self.assertEqual(shorts_select.opening_reason(found[0]), "DEPENDENT_OPENING_REFERENCE")

    def test_completed_ending_requires_full_segment_or_explicit_closure(self):
        timeline, _, refs = positive_source()
        sentences = timeline["sentences"]
        sentences.append(sentence("prayer-close", 32.18, 36.0, "We continue praying together."))
        for text, expected in [
                ("Father, help me meet this day with patience and kindness.", "UNRESOLVED_SEGMENT_END"),
                ("Father, help me meet this day:", "INCOMPLETE_ENDING"),
                ("Father, help me. Amen.", None),
                ("May the Lord keep you.", None),
                ("Father, may the Lord keep you.", "UNRESOLVED_SEGMENT_END")]:
            with self.subTest(text=text):
                sentences[2]["text"] = text
                accepted, why = shorts_select.validate_candidate(sentences, refs, {"start": 0, "end": 32})
                self.assertEqual(why, expected)
                self.assertEqual(accepted is not None, expected is None)
        self.assertIsNone(shorts_select.ending_reason(sentences, sentences))

    def test_partial_scripture_rejects_even_amen_and_missing_source_segment(self):
        timeline, _, refs = positive_source()
        sentences = timeline["sentences"]
        sentences[2]["segment"] = "scripture-psalm-23"
        sentences[2]["text"] = "The LORD is good. Amen."
        sentences.append(sentence("scripture-psalm-23", 32.2, 40, "He restoreth my soul."))
        self.assertEqual(shorts_select.validate_candidate(sentences, refs, {"start": 0, "end": 32})[1],
                         "PARTIAL_SCRIPTURE")
        timeline, _, refs = positive_source()
        del refs["prayer-close"]
        self.assertEqual(shorts_select.validate_candidate(timeline["sentences"], refs, {"start": 0, "end": 32})[1],
                         "PARTIAL_SCRIPTURE")

    def test_window_pair_denominators_first_reason_and_excluded_lengths(self):
        sentences, refs = [], {}
        reasons = ["CTA_OR_TRANSITION_SEGMENT", "PARTIAL_SCRIPTURE", "INCOMPLETE_ENDING",
                   "UNRESOLVED_SEGMENT_END", None]
        for i, reason in enumerate(reasons):
            start, opening, closing = i * 100, f"open-{i}", f"close-{i}"
            if i == 0:
                closing = "cta"
            refs[opening] = None
            refs[closing] = "Psalm 23:1 (KJV)" if i in (0, 1) else None
            sentences.extend([sentence(opening, start, start + 3, "You can rest."),
                              sentence(closing, start + 3.4, start + 32,
                                       "A prayer with no ending:" if i in (0, 1, 2) else "God gives peace.")])
            if i in (0, 1, 3):
                sentences.append(sentence(closing, start + 60, start + 70, "God gives peace."))
        cands, counts = shorts_select.candidate_analysis(sentences, refs)
        self.assertEqual(len(cands), 1)
        self.assertEqual((cands[0]["start"], cands[0]["end"]), (400, 432))
        self.assertEqual(counts["opening_starts_total"], 13)
        self.assertEqual(counts["opening_starts_accepted"], 5)
        self.assertEqual(counts["opening_rejections"], {"EMPTY_OR_INCOMPLETE_OPENING": 3, "OPENING_OVER_3S": 5})
        self.assertEqual(counts["window_pairs_total"], 5)
        self.assertEqual(counts["window_pairs_accepted"], 1)
        self.assertEqual(counts["window_rejections"], {reason: 1 for reason in reasons if reason})
        self.assertEqual(counts["opening_starts_total"], counts["opening_starts_accepted"] + sum(counts["opening_rejections"].values()))
        self.assertEqual(counts["window_pairs_total"], counts["window_pairs_accepted"] + sum(counts["window_rejections"].values()))

    def test_timeline_first_word_offsets_not_acoustic_onset(self):
        timeline, _, refs = positive_source(offset=1.0)
        for offset, reason in [(0.0, None), (0.3, None), (0.301, "FIRST_WORD_OFFSET"), (-0.001, "FIRST_WORD_OFFSET")]:
            with self.subTest(offset=offset):
                cut = {"start": 1.0 - offset, "end": 33.0}
                accepted, why = shorts_select.validate_candidate(timeline["sentences"], refs, cut)
                self.assertEqual(why, reason)
                if accepted:
                    self.assertEqual(accepted["start"], 1.0)
                    self.assertEqual(accepted["sentences"][0]["start"] - accepted["start"], 0.0)
                    self.assertLessEqual(events(sp.ass(accepted, "You can rest.", refs, 32.5,
                                                       timeline["sentences"]), "Cap")[0][0], 0.3)


class SyntheticPositiveMedia(unittest.TestCase):
    def test_positive_exercises_real_caption_reference_and_render_args_builders(self):
        timeline, _, refs = positive_source()
        windows = shorts_select.candidates(timeline["sentences"], refs)
        self.assertEqual(len(windows), 1, "the positive media helper assertions must be exercised")
        w = windows[0]
        subtitles = sp.ass(w, "You can rest.", refs, 32.5, timeline["sentences"])
        caps, references, hooks = events(subtitles, "Cap"), events(subtitles, "Ref"), events(subtitles, "Hook")
        self.assertGreater(len(caps), 0)
        self.assertEqual(" ".join(text for _, _, text in caps).split(),
                         " ".join(s["text"] for s in timeline["sentences"]).split())
        for a, b, text in caps:
            self.assertTrue(1 <= len(text.split()) <= 5)
            self.assertTrue(any(s["start"] - EPS <= a and b <= s["end"] + EPS for s in timeline["sentences"]))
        self.assertEqual(caps[0][0], 0)
        self.assertEqual(caps[-1][1], 32)
        self.assertEqual(references, [(3.4, 20.0, "Psalm 23:1 (KJV)")])
        self.assertEqual(hooks, [(0.0, 2.5, "You can rest.")])
        self.assertEqual(sp.reference_events(w, refs, timeline["sentences"]), references)
        dur, n, length, args = Picture().args(w)
        self.assertEqual(dur, 32.5)
        self.assertEqual((n, length), (2, 16.25))
        graph = args[args.index("-filter_complex") + 1]
        self.assertIn("s=1080x1920:fps=30", graph)
        self.assertIn("zoompan", graph)
        self.assertEqual(graph.count("xfade"), 1)
        self.assertNotIn("overlay", graph)
        k = args.index("/x/voice.wav")
        self.assertEqual(args[k - 5:k - 1], ["-ss", "0.000", "-t", "32.000"])
        self.assertEqual(args[-4:], ["32.500", "-movflags", "+faststart", "/x/short.mp4"])


class SelectorCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.provider = mock.Mock(side_effect=AssertionError("REAL_PROVIDER_FORBIDDEN"))
        self.fake_transport = SimpleNamespace(call=self.provider, SUPPORT_MODELS=("fake-offline-provider",),
                                              S=lambda **fields: fields, STR="string", NUM="number", INT="integer",
                                              arr=lambda item: {"items": item})
        self.environment = mock.patch.dict(os.environ, {"HERO_GEMINI_API_KEY": "configured-fake-offline-key"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        modules = mock.patch.dict(sys.modules, {"structure_mining": self.fake_transport})
        modules.start()
        self.addCleanup(modules.stop)

    def invoke(self, timeline, script, extra=()):
        timeline_path, script_path = write_source(self.root, timeline, script)
        output = self.root / "selection.json"
        with redirect_stdout(io.StringIO()):
            shorts_select.cli([str(timeline_path), str(script_path), str(output), *extra])
        return load(output)

    def block_source(self, count):
        sentences, refs = [], {}
        for i in range(count):
            start = i * 100
            for j, (a, b, text) in enumerate([(start, start + 3, "You can rest."),
                                             (start + 3.4, start + 32, "God gives peace."),
                                             (start + 32.4, start + 34, "Peace remains.")]):
                seg = f"block-{i}-{j}"
                refs[seg] = None
                sentences.append(sentence(seg, a, b, text))
        return {"sentences": sentences}, {"pilot_id": "synthetic-blocks", "segments": [
            {"id": key, "reference": value} for key, value in refs.items()]}

    def test_all_four_cli_forms_legacy_rubric_and_measured_zero_calls(self):
        timeline, script = self.block_source(5)
        forms = [((), False, 3), (("2",), False, 2),
                 (("--measured-only",), True, 3), (("2", "--measured-only"), True, 2)]
        for args, measured_only, expected in forms:
            with self.subTest(args=args), mock.patch.object(shorts_select, "rubric", return_value=("fake-offline-model", {})) as rubric:
                result = self.invoke(timeline, script, args)
                self.assertEqual(len(result["chosen"]), expected)
                self.assertEqual(result["selection_mode"], "MEASURED_ONLY" if measured_only else "LEGACY")
                if measured_only:
                    rubric.assert_not_called()
                    self.assertIsNone(result["rubric_model"])
                    for candidate in result["shortlist"]:
                        self.assertNotIn("rubric", candidate)
                        self.assertEqual(candidate["final_score"], candidate["measured_score"])
                    for chosen in result["chosen"]:
                        self.assertEqual(chosen["hook"], chosen["sentences"][0]["text"])
                        self.assertEqual(chosen["title"], chosen["hook"])
                else:
                    rubric.assert_called_once()
                    self.assertEqual(rubric.call_args.args[1], "configured-fake-offline-key")
                    self.assertEqual(result["rubric_model"], "fake-offline-model")
                self.provider.assert_not_called()
                self.assertEqual(result["input_sha256"], {
                    "timeline": hashlib.sha256((self.root / "timeline.json").read_bytes()).hexdigest(),
                    "script": hashlib.sha256((self.root / "script.json").read_bytes()).hexdigest()})

    def test_main_signature_and_legacy_behavior_remain_compatible(self):
        self.assertEqual(str(inspect.signature(shorts_select.main)), "(timeline_path, script_path, out_path, n='3')")
        timeline, script, _ = positive_source()
        paths = write_source(self.root, timeline, script)
        out = self.root / "legacy.json"
        with mock.patch.object(shorts_select, "rubric", return_value=("fake-offline-model", {})) as rubric, redirect_stdout(io.StringIO()):
            shorts_select.main(*map(str, paths), str(out))
        rubric.assert_called_once()
        self.assertEqual(len(load(out)["chosen"]), 1)
        self.provider.assert_not_called()

    def test_legacy_reaches_fake_provider_but_measured_never_does(self):
        timeline, script, _ = positive_source()
        self.provider.side_effect = None
        self.provider.return_value = ("fake-offline-provider", {"ratings": []})
        legacy = self.invoke(timeline, script)
        self.provider.assert_called_once()
        self.assertEqual(self.provider.call_args.args[1], "configured-fake-offline-key")
        self.assertEqual(legacy["rubric_model"], "fake-offline-provider")
        self.assertEqual(len(legacy["chosen"]), 1)
        self.provider.reset_mock()
        with mock.patch.object(shorts_select, "rubric", wraps=shorts_select.rubric) as rubric:
            measured = self.invoke(timeline, script, ("--measured-only",))
        self.assertEqual(len(measured["chosen"]), 1)
        self.assertIsNone(measured["rubric_model"])
        rubric.assert_not_called()
        self.provider.assert_not_called()

    def test_final_score_sort_precedes_nonoverlapping_choice(self):
        timeline, script = self.block_source(3)
        ratings = {i: {"index": i, **{key: 8 + i for key in shorts_select.RUBRIC},
                       "hook_line": "You can rest.", "title": f"Offline title {i}"} for i in range(3)}
        with mock.patch.object(shorts_select, "measured", return_value=(0.5, {})), mock.patch.object(
                shorts_select, "rubric", return_value=("fake-offline-model", ratings)):
            result = self.invoke(timeline, script, ("2",))
        self.assertEqual([c["start"] for c in result["shortlist"]], [200, 100, 0])
        self.assertEqual([c["start"] for c in result["chosen"]], [200, 100])
        self.assertEqual([c["final_score"] for c in result["shortlist"]], [0.8, 0.74, 0.68])
        self.provider.assert_not_called()

    def test_exact_positive_is_selected_and_measured_hook_is_source_words(self):
        timeline, script, _ = positive_source()
        with mock.patch.object(shorts_select, "rubric", side_effect=AssertionError("RUBRIC_FORBIDDEN")) as rubric:
            result = self.invoke(timeline, script, ("--measured-only",))
        self.assertEqual(result["candidates_considered"], 1)
        self.assertEqual(len(result["chosen"]), 1)
        self.assertEqual(result["chosen"][0]["hook"], "You can rest.")
        self.assertEqual(result["chosen"][0]["title"], "You can rest.")
        self.assertEqual((result["chosen"][0]["start"], result["chosen"][0]["end"]), (0, 32))
        self.assertIsNone(result["reason"])
        rubric.assert_not_called()
        self.provider.assert_not_called()
        hook = shorts_select.opening_hook({"text": "You will find peace and hope in the morning."})
        self.assertEqual(hook, "You will find peace and hope")
        self.assertLessEqual(len(hook.split()), 7)

    def test_invalid_positive_integer_n_and_flag_position(self):
        timeline, script, _ = positive_source()
        for bad in ("0", "-1", "1.5", "no", "", "True"):
            with self.subTest(n=bad), self.assertRaisesRegex(ValueError, "N_MUST_BE_POSITIVE_INTEGER"):
                self.invoke(timeline, script, (bad, "--measured-only"))
        with self.assertRaises((SystemExit, ValueError)):
            self.invoke(timeline, script, ("--measured-only", "2"))
        self.provider.assert_not_called()

    def test_shortlist_cap_duplicate_start_and_stable_measured_ties(self):
        timeline, script = self.block_source(20)
        with mock.patch.object(shorts_select, "measured", return_value=(0.5, {})), mock.patch.object(shorts_select, "rubric") as rubric:
            result = self.invoke(timeline, script, ("20", "--measured-only"))
        self.assertEqual(result["candidates_considered"], 40)
        self.assertEqual(len(result["shortlist"]), 15)
        self.assertEqual(len(result["chosen"]), 15)
        self.assertEqual([c["start"] for c in result["shortlist"]], list(range(0, 1500, 100)))
        self.assertEqual([c["end"] - c["start"] for c in result["shortlist"]], [32] * 15)
        self.assertEqual(result["chosen"], result["shortlist"])
        rubric.assert_not_called()
        self.provider.assert_not_called()

    def test_selection_is_nonoverlapping_and_final_score_ties_are_stable(self):
        sentences = [sentence(f"s-{i}", i * 8, i * 8 + 3, "You can rest.") for i in range(10)]
        timeline = {"sentences": sentences}
        script = {"pilot_id": "synthetic-overlaps", "segments": [{"id": s["segment"]} for s in sentences]}
        with mock.patch.object(shorts_select, "measured", return_value=(0.5, {})):
            result = self.invoke(timeline, script, ("10", "--measured-only"))
        self.assertEqual([c["start"] for c in result["chosen"]], [0, 40])
        self.assertEqual([c["end"] for c in result["chosen"]], [35, 75])
        for i, chosen in enumerate(result["chosen"]):
            for other in result["chosen"][i + 1:]:
                self.assertTrue(chosen["end"] <= other["start"] or chosen["start"] >= other["end"])
        self.provider.assert_not_called()

    def test_no_structural_candidate_keeps_hashes_counts_and_null_model(self):
        timeline, script, _ = positive_source()
        timeline["sentences"][0]["text"] = "Carry that with you."
        with mock.patch.object(shorts_select, "rubric") as rubric:
            result = self.invoke(timeline, script, ("--measured-only",))
        self.assertEqual(result["chosen"], [])
        self.assertEqual(result["shortlist"], [])
        self.assertEqual(result["candidates_considered"], 0)
        self.assertEqual(result["reason"], "NO_STRUCTURAL_CANDIDATE")
        self.assertIsNone(result["rubric_model"])
        self.assertEqual(result["structural_counts"], {
            "opening_starts_total": 3, "opening_starts_accepted": 0,
            "opening_rejections": {"DEPENDENT_OPENING_REFERENCE": 1, "OPENING_OVER_3S": 2},
            "window_pairs_total": 0, "window_pairs_accepted": 0, "window_rejections": {}})
        self.assertEqual(result["input_sha256"]["timeline"], hashlib.sha256((self.root / "timeline.json").read_bytes()).hexdigest())
        self.assertEqual(result["input_sha256"]["script"], hashlib.sha256((self.root / "script.json").read_bytes()).hexdigest())
        rubric.assert_not_called()
        self.provider.assert_not_called()


class ProducerGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.timeline, self.script, self.refs = positive_source()
        self.forged = {"start": 0, "end": 32, "final_score": 1000000,
                       "measured_score": 1000000, "segments": ["forged-safe"],
                       "sentences": [sentence("forged-safe", 0, 32, "You can rest. Amen.")],
                       "reference": "Forged 1:1", "text": "Invented complete prayer. Amen.", "hook": "You can rest."}

    def main_with_spy(self, moment):
        _, script_path = write_source(self.root, self.timeline, self.script)
        selection = self.root / "selection.json"
        selection.write_text(json.dumps({"chosen": [moment]}))
        return (str(self.root), str(selection), str(script_path), str(self.root / "images"),
                "unused-figure", "unused-music", str(self.root / "out"))

    def test_main_rejects_invalid_actual_opening_before_produce_despite_forgery(self):
        for text, end, reason in [("Carry that with you.", 3, "DEPENDENT_OPENING_REFERENCE"),
                                  ("You can rest.", 3.001, "OPENING_OVER_3S"),
                                  ("you can rest.", 3, "CONTINUATION_OPENING_LINE"),
                                  ("You can rest:", 3, "EMPTY_OR_INCOMPLETE_OPENING")]:
            with self.subTest(reason=reason):
                self.timeline["sentences"][0].update(text=text, end=end)
                args = self.main_with_spy(self.forged)
                stream = io.StringIO()
                with mock.patch.object(sp, "produce") as produce, mock.patch.object(sp, "run") as run, redirect_stdout(stream):
                    with self.assertRaisesRegex(SystemExit, "NO_SHORT_MEETS_R8"):
                        sp.main(*args)
                produce.assert_not_called()
                run.assert_not_called()
                self.assertIn(reason, stream.getvalue())

    def test_main_rejects_partial_scripture_even_with_forged_complete_metadata(self):
        self.timeline["sentences"][2]["segment"] = "scripture-psalm-23"
        self.timeline["sentences"][2]["text"] = "The LORD is good. Amen."
        self.timeline["sentences"].append(sentence("scripture-psalm-23", 32.2, 40, "He restoreth my soul."))
        args = self.main_with_spy(self.forged)
        with mock.patch.object(sp, "produce") as produce, mock.patch.object(sp, "run") as run, redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(SystemExit, "NO_SHORT_MEETS_R8"):
                sp.main(*args)
        produce.assert_not_called()
        run.assert_not_called()
        self.assertIn("PARTIAL_SCRIPTURE", output.getvalue())

    def test_main_reconstructs_valid_cut_from_full_source_not_forged_metadata(self):
        args = self.main_with_spy(self.forged)
        fake_record = {"file": "not-rendered.mp4", "seconds": 32.5, "hook": "You can rest."}
        with mock.patch.object(sp, "produce", return_value=fake_record) as produce, mock.patch.object(sp, "run") as run, redirect_stdout(io.StringIO()):
            sp.main(*args)
        produce.assert_called_once()
        passed = produce.call_args.args[1]
        self.assertEqual(passed["sentences"], self.timeline["sentences"])
        self.assertEqual(passed["segments"], ["opening", "scripture-psalm-23", "prayer-close"])
        self.assertEqual(passed["reference"], "Psalm 23:1 (KJV)")
        self.assertEqual(passed["text"], " ".join(s["text"] for s in self.timeline["sentences"]))
        self.assertNotIn("Invented", json.dumps(passed))
        self.assertNotIn("forged-safe", json.dumps(passed))
        self.assertEqual(produce.call_args.args[9], self.timeline["sentences"])
        self.assertEqual(produce.call_args.kwargs["script_refs"], self.refs)
        run.assert_not_called()

    def test_main_checks_proposed_input_offset_before_inward_snap(self):
        self.timeline, self.script, self.refs = positive_source(offset=1.0)
        for offset, accepted in [(0.3, True), (0.301, False), (-0.001, False)]:
            with self.subTest(offset=offset):
                moment = dict(self.forged, start=1.0 - offset, end=33.0)
                args = self.main_with_spy(moment)
                with mock.patch.object(sp, "produce", return_value={"file": "not-rendered", "seconds": 32.5, "hook": None}) as produce, redirect_stdout(io.StringIO()):
                    if accepted:
                        sp.main(*args)
                        produce.assert_called_once()
                        cut = produce.call_args.args[1]
                        self.assertEqual(cut["start"], 1.0)
                        self.assertEqual(cut["sentences"][0]["start"] - cut["start"], 0.0)
                    else:
                        with self.assertRaisesRegex(SystemExit, "NO_SHORT_MEETS_R8"):
                            sp.main(*args)
                        produce.assert_not_called()

    def direct_args(self):
        return (self.root, self.forged, 0, self.script, self.root / "images", None,
                self.root / "music", self.root / "out")

    def test_direct_produce_requires_both_full_source_inputs_before_subprocess(self):
        self.assertEqual(inspect.signature(sp.produce).parameters["script_refs"].kind, inspect.Parameter.KEYWORD_ONLY)
        for kwargs in ({}, {"timeline_sentences": self.timeline["sentences"]}, {"script_refs": self.refs}):
            with self.subTest(kwargs=tuple(kwargs)), mock.patch.object(sp, "run") as run, mock.patch.object(sp, "vertical_still") as still:
                with self.assertRaisesRegex(ValueError, "^FULL_SOURCE_REQUIRED$"):
                    sp.produce(*self.direct_args(), **kwargs)
                run.assert_not_called()
                still.assert_not_called()
                self.assertFalse((self.root / "out").exists())

    def test_direct_produce_revalidates_invalid_source_and_partial_scripture(self):
        self.timeline["sentences"][0]["text"] = "Carry that with you."
        with mock.patch.object(sp, "run") as run, mock.patch.object(sp, "vertical_still") as still:
            with self.assertRaisesRegex(ValueError, "DEPENDENT_OPENING_REFERENCE"):
                sp.produce(*self.direct_args(), timeline_sentences=self.timeline["sentences"], script_refs=self.refs)
            self.timeline, self.script, self.refs = positive_source()
            self.timeline["sentences"][2]["segment"] = "scripture-psalm-23"
            self.timeline["sentences"].append(sentence("scripture-psalm-23", 32.2, 40, "He restoreth my soul."))
            with self.assertRaisesRegex(ValueError, "PARTIAL_SCRIPTURE"):
                sp.produce(*self.direct_args(), timeline_sentences=self.timeline["sentences"], script_refs=self.refs)
            forged_refs = dict(self.refs, **{"scripture-psalm-23": None})
            with self.assertRaisesRegex(ValueError, "SOURCE_REFS_MISMATCH"):
                sp.produce(*self.direct_args(), timeline_sentences=self.timeline["sentences"], script_refs=forged_refs)
            run.assert_not_called()
            still.assert_not_called()
            self.assertFalse((self.root / "out").exists())

    def test_common_validator_is_reused_and_snap_signature_stays_compatible(self):
        self.assertIs(sp.validate_candidate, shorts_select.validate_candidate)
        self.assertEqual(str(inspect.signature(sp.snap)), "(moment, sentences)")
        self.assertEqual((shorts_select.MIN_S, shorts_select.MAX_S), (30, 55))
        self.assertEqual((sp.WINDOW_S, sp.TAIL_S, sp.FIRST_WORD_MAX), ((30, 55), 0.5, 0.3))


# This literal is the approved card, not a mutable pilot source and not production evidence.
EDITORIAL_PLAN = {'version': 'shorts-editorial-plan-v2',
 'source_pilot': 'pilot-005',
 'source_baseline_sha': '7fb9e9e1fad9396b80c029212f0a3144c1428d51',
 'source_sha256': {'script': 'c0cf3d5fc0747b5f743d9d0189e9deb4326a124a9769a41d4341b14aa347359a',
                   'timeline': '53496f5a82ed391422974e517b5b895059d0040db790c2044030f06bd06245c5',
                   'inputs': '67e393596d74f77e64f5a9de143c99dbc4bc4cb2cb8e898b261900ae69623831'},
 'voice': {'asset': 'pilot-005-voice-sha256-6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc.flac',
           'sha256': '6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc'},
 'music': {'asset': 'original-rest-music.lossless.flac',
           'sha256': '1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c'},
 'candidate': {'start': 459.86,
               'end': 499.672,
               'hook': 'Lord, protect my relationships.',
               'title': 'A Prayer for Peace in Your Relationships',
               'reference': None},
 'tail_seconds': 0.5,
 'transition': {'type': 'fade', 'seconds': 0.5},
 'scenes': [{'image_id': 'bg-dawn-lake',
             'asset': 'pilot-003-img-bg-dawn-lake-sha256-74d22480484ff2088b82de7d0dd83170be6171711aaeb198f96fc74f40d26018.png',
             'sha256': '74d22480484ff2088b82de7d0dd83170be6171711aaeb198f96fc74f40d26018',
             'nominal_start': 0.0,
             'nominal_end': 5.0,
             'motion_profile': 'phrase_push_in_v1'},
            {'image_id': 'bg-sheltered-valley',
             'asset': 'pilot-005-img-bg-sheltered-valley-sha256-1d8055fd45c97ae66eead1c19f80dcaf1a9a28644761f31f41f34975bfe34d85.png',
             'sha256': '1d8055fd45c97ae66eead1c19f80dcaf1a9a28644761f31f41f34975bfe34d85',
             'nominal_start': 5.0,
             'nominal_end': 10.0,
             'motion_profile': 'phrase_pan_right_v1'},
            {'image_id': 'bg-sunlit-road',
             'asset': 'pilot-005-img-bg-sunlit-road-sha256-79591089b067d1e73cc8cb5ad7c5ebcea6754a1b6eb4e1eff039de3d6abb7794.png',
             'sha256': '79591089b067d1e73cc8cb5ad7c5ebcea6754a1b6eb4e1eff039de3d6abb7794',
             'nominal_start': 10.0,
             'nominal_end': 15.0,
             'motion_profile': 'phrase_push_in_v1'},
            {'image_id': 'bg-fortress-dawn',
             'asset': 'pilot-005-img-bg-fortress-dawn-sha256-8fe838ae8d71963474991719861e02aaf83651817031e4af59a73858ba043bba.png',
             'sha256': '8fe838ae8d71963474991719861e02aaf83651817031e4af59a73858ba043bba',
             'nominal_start': 15.0,
             'nominal_end': 20.0,
             'motion_profile': 'phrase_pan_right_v1'},
            {'image_id': 'bg-sunrise-field',
             'asset': 'pilot-003-img-bg-sunrise-field-sha256-8083ef5de4d2e1bf8b078a4f8ac0af71cc9992a68c9663528149fe8255aed1e0.png',
             'sha256': '8083ef5de4d2e1bf8b078a4f8ac0af71cc9992a68c9663528149fe8255aed1e0',
             'nominal_start': 20.0,
             'nominal_end': 25.0,
             'motion_profile': 'phrase_push_in_v1'},
            {'image_id': 'bg-misty-valley',
             'asset': 'pilot-003-img-bg-misty-valley-sha256-a7e0c31b6a3cd366971a604e648ec0728c1227b45ae71dcfaac0a03679f6acdc.png',
             'sha256': 'a7e0c31b6a3cd366971a604e648ec0728c1227b45ae71dcfaac0a03679f6acdc',
             'nominal_start': 25.0,
             'nominal_end': 30.0,
             'motion_profile': 'phrase_pan_right_v1'},
            {'image_id': 'bg-mountain-sunrise',
             'asset': 'pilot-003-img-bg-mountain-sunrise-sha256-886b55ab2de854099a05358f2a8059cd5ad8b42d1a7af482c40e2dde1b84c6c5.png',
             'sha256': '886b55ab2de854099a05358f2a8059cd5ad8b42d1a7af482c40e2dde1b84c6c5',
             'nominal_start': 30.0,
             'nominal_end': 35.0,
             'motion_profile': 'phrase_push_in_v1'},
            {'image_id': 'bg-tower-hill',
             'asset': 'pilot-005-img-bg-tower-hill-sha256-0a2619e6dbddc3966d31850f2ab74e2e92738d2787ac0dcdd23ad44b7c92f961.png',
             'sha256': '0a2619e6dbddc3966d31850f2ab74e2e92738d2787ac0dcdd23ad44b7c92f961',
             'nominal_start': 35.0,
             'nominal_end': 40.312,
             'motion_profile': 'phrase_pan_right_v1'}],
 'publish': False,
 'rhythm_exception': {'id': 'pilot-005-20261020-eight-scenes-r3',
                      'target_slot': '2026-10-20T20:00:00Z',
                      'scene_count': 8,
                      'nominal_seconds': [4.0, 6.0],
                      'visible_seconds': [4.0, 6.0]},
 'hook_animation': {'profile': 'cinematic_hook_v1',
                    'start_seconds': 0.0,
                    'end_seconds': 3.0,
                    'caption_policy': 'single_track_no_duplicate'}}


def editorial_source():
    fixture = HERE / "fixtures" / "shorts-pilot-005-20261020"
    timeline = load(fixture / "out" / "timeline.json")
    script = load(fixture / "script.json")
    refs = {s["id"]: s.get("reference") for s in script["segments"]}
    moment, reason = shorts_select.validate_candidate(timeline["sentences"], refs,
                                                      dict(EDITORIAL_PLAN["candidate"]))
    if reason or moment is None:
        raise AssertionError(f"APPROVED_FROZEN_SOURCE_REJECTED: {reason}")
    return timeline, script, refs, moment


def phrase_boundaries(moment, start, end):
    points = {start, end}
    points.update(s[key] - moment["start"] for s in moment["sentences"] for key in ("start", "end")
                  if start < s[key] - moment["start"] < end)
    return sorted(points)


SYNTHETIC_COLORS = [(180, 40, 30), (30, 175, 45), (30, 50, 180), (180, 160, 30),
                    (175, 35, 165), (30, 165, 175), (195, 100, 35), (105, 55, 190)]


def synthetic_ppm(path, width, height, scene=0):
    """Locally invented eight-color texture, never a production image or evidence."""
    pixels = bytearray()
    color = SYNTHETIC_COLORS[scene]
    for y in range(height):
        for x in range(width):
            texture = (x * 11 + y * 7) % 23
            pixels.extend(min(255, channel + texture) for channel in color)
    path.write_bytes(f"P6\n{width} {height}\n255\n".encode() + pixels)


class EditorialMotion(unittest.TestCase):
    def test_frozen_source_is_exactly_the_ten_sentence_plan(self):
        timeline, _, refs, moment = editorial_source()
        self.assertEqual(moment["sentences"], timeline["sentences"][106:116])
        self.assertEqual(len(moment["sentences"]), 10)
        self.assertEqual((moment["start"], moment["end"]), (459.860, 499.672))
        self.assertAlmostEqual(moment["end"] - moment["start"] + sp.TAIL_S, 40.312)
        self.assertEqual(moment["sentences"][-1]["text"],
                         "Let my words carry your peace into every room I enter.")
        subtitles = sp.ass(moment, moment["hook"], refs, 40.312, timeline["sentences"],
                           hook_mode="caption_only")
        self.assertEqual(events(subtitles, "Hook"), [])
        self.assertEqual(events(subtitles, "Ref"), [])
        captions = events(subtitles, "Cap")
        first = [event for event in captions if event[0] < 2.667]
        self.assertEqual(" ".join(text for _, _, text in first), "Lord, protect my relationships.")
        self.assertEqual(first[0][0], 0.0)
        self.assertAlmostEqual(first[-1][1], 2.667, delta=0.01)
        self.assertGreater(len(captions), 10)
        # The new policy is explicit; the positional legacy helper remains an overlay.
        self.assertEqual(events(sp.ass(moment, moment["hook"], refs, 40.312,
                                       timeline["sentences"]), "Hook"),
                         [(0.0, 2.5, "Lord, protect my relationships.")])
        self.assertEqual(inspect.signature(sp.ass).parameters["hook_mode"].kind,
                         inspect.Parameter.KEYWORD_ONLY)

    def test_frame_plan_has_the_rounded_overlap_without_subtracting_it_twice(self):
        plan = sp.scene_frame_plan(EDITORIAL_PLAN)
        for key, value in {
                "fps": 30, "output_frames": 1209,
                "boundary_frames": [150, 300, 450, 600, 750, 900, 1050],
                "fade_start_frames": [143, 293, 443, 593, 743, 893, 1043],
                "fade_end_frames": [158, 308, 458, 608, 758, 908, 1058], "fade_frames": 15,
                "scene_frames": [158, 165, 165, 165, 165, 165, 165, 166],
                "nominal_scene_frames": [150, 150, 150, 150, 150, 150, 150, 159],
                "scene_spans": [[0, 158], [143, 308], [293, 458], [443, 608],
                                [593, 758], [743, 908], [893, 1058], [1043, 1209]]}.items():
            self.assertEqual(plan[key], value, key)
        self.assertEqual(sum(plan["scene_frames"]), 1314)
        self.assertEqual(sum(plan["scene_frames"]) - 7 * plan["fade_frames"], plan["output_frames"])
        self.assertEqual(sum(plan["nominal_scene_frames"]), plan["output_frames"])
        for length in plan["scene_frames"] + plan["nominal_scene_frames"]:
            self.assertGreaterEqual(length, 4 * sp.FPS)
            self.assertLessEqual(length, 6 * sp.FPS)
        for frame in range(plan["output_frames"]):
            self.assertIn(sum(a <= frame < b for a, b in plan["scene_spans"]), (1, 2))
        self.assertEqual(math.floor(40.312 * 30 + 0.5), plan["output_frames"])
        self.assertLessEqual(abs(plan["output_frames"] / 30 - 40.312), 1 / 30)
        self.assertEqual(sp.TAIL_S, 0.5)

    def test_phrase_progress_matches_the_fixed_expression_and_is_monotonic(self):
        _, _, _, moment = editorial_source()
        for a, b in sp.scene_frame_plan(EDITORIAL_PLAN)["scene_spans"]:
            start, end = a / 30, b / 30
            bounds = phrase_boundaries(moment, start, end)
            self.assertGreaterEqual(len(bounds), 2)
            samples = [start + (end - start) * i / 4000 for i in range(4001)]
            actual = [sp.motion_progress(t, bounds) for t in samples]
            self.assertTrue(all(math.isfinite(p) and 0 <= p <= 1 for p in actual))
            self.assertEqual(actual[0], 0)
            self.assertEqual(actual[-1], 1)
            self.assertTrue(all(a <= b for a, b in zip(actual, actual[1:])))
            for a, b in zip(bounds, bounds[1:]):
                for u in (0, 0.1, 0.25, 0.5, 0.75, 0.9, 1):
                    g = u - 0.35 * math.sin(2 * math.pi * u) / (2 * math.pi)
                    expected = (a - start + (b - a) * g) / (end - start)
                    self.assertAlmostEqual(sp.motion_progress(a + (b - a) * u, bounds),
                                           expected, delta=1e-12)

    def test_position_zoom_and_velocity_are_continuous_at_every_phrase_boundary(self):
        _, _, _, moment = editorial_source()
        for a, b in sp.scene_frame_plan(EDITORIAL_PLAN)["scene_spans"]:
            start, end = a / 30, b / 30
            bounds = phrase_boundaries(moment, start, end)
            for t in bounds[1:-1]:
                with self.subTest(span=(start, end), boundary=t):
                    h = 1e-6
                    left = sp.motion_progress(t - h, bounds)
                    center = sp.motion_progress(t, bounds)
                    right = sp.motion_progress(t + h, bounds)
                    self.assertLessEqual(abs(left - right), 1e-6)
                    self.assertLessEqual(abs((1 + 0.08 * left) - (1 + 0.08 * right)), 1e-6)
                    self.assertAlmostEqual((center - left) / h, (right - center) / h, delta=1e-4)
                    self.assertAlmostEqual((center - left) / h, 0.65 / (end - start), delta=1e-4)
            progress = [sp.motion_progress(t, bounds) for t in bounds]
            for p in progress:
                zoom = 1 + 0.08 * p
                self.assertTrue(1 <= zoom <= 1.08)
                # Full-margin right pan in scaled-output coordinates; never silently clamp a bad crop.
                for width, height in [(1080, 1920), (108, 192)]:
                    scaled_w, scaled_h = width * 1.08, height * 1.08
                    x, y = p * (scaled_w - width), (scaled_h - height) / 2
                    self.assertGreaterEqual(x, 0)
                    self.assertLessEqual(x + width, scaled_w + 1e-9)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(y + height, scaled_h + 1e-9)
            self.assertEqual(progress[0], 0)
            self.assertEqual(progress[-1], 1)

    def test_editorial_render_has_seven_padded_transitions_and_sample_bounded_audio(self):
        _, _, _, moment = editorial_source()
        paths = [Path(f"/synthetic/scene-{i}.ppm") for i in range(8)]
        args = sp.render_args(paths, Path("/synthetic/voice.flac"), Path("/synthetic/music.flac"),
                              Path("/synthetic/captions.ass"), moment, 40.312, "null",
                              Path("/synthetic/result.mp4"), edit_plan=EDITORIAL_PLAN,
                              hook_video=Path("/synthetic/opening.mkv"))
        graph = args[args.index("-filter_complex") + 1]
        fades = re.findall(r"xfade=transition=fade:duration=([\d.]+):offset=([\d.]+)", graph)
        self.assertEqual(len(fades), 7)
        for actual, start in zip(fades, [143, 293, 443, 593, 743, 893, 1043]):
            self.assertAlmostEqual(float(actual[0]), 0.5)
            self.assertAlmostEqual(float(actual[1]), start / 30)
        self.assertNotIn("overlay", graph)
        self.assertNotIn("setpts=0.", graph)
        self.assertNotIn("async=", graph)
        self.assertNotIn("atempo", graph)
        self.assertIn("loudnorm=I=-14:TP=-2:LRA=9", graph)
        self.assertIn("alimiter=limit=0.75:attack=5:release=50:level=false", graph)
        self.assertIn("aresample=48000,apad=whole_len=1934976,atrim=end_sample=1934976,asetpts=N/SR/TB", graph)
        self.assertGreaterEqual(graph.count("asetpts=N/SR/TB"), 3)
        voice = next(part for part in graph.split(";") if part.startswith("[8:a]"))
        self.assertNotIn("afade", voice, "v2 must not attenuate the final spoken word")
        # Ignore insignificant decimal formatting, but require the exact intervals and ordering.
        self.assertRegex(graph, r"afade=t=out:st=38\.3120*:d=2(?:\.0+)?:curve=hsin")
        self.assertRegex(graph, r"afade=t=out:st=39\.8120*:d=0\.50*:curve=hsin")
        self.assertLess(graph.index("sidechaincompress="), graph.index("afade=t=out:st=38.312"))
        self.assertLess(graph.index("atrim=end_sample=1934976"), graph.index("afade=t=out:st=39.812"))
        self.assertLess(graph.index("alimiter="), graph.index("afade=t=out:st=39.812"))
        for option, value in [("-c:v", "libx264"), ("-r", "30"), ("-c:a", "aac"), ("-ar", "48000")]:
            self.assertEqual(args[args.index(option) + 1], value)
        self.assertIn("format=yuv420p", graph)
        for parameter in ("edit_plan", "hook_video"):
            self.assertEqual(inspect.signature(sp.render_args).parameters[parameter].kind,
                             inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual((sp.VW, sp.VH, sp.FPS, sp.TAIL_S), (1080, 1920, 30, 0.5))
        i = args.index("/synthetic/voice.flac")
        self.assertEqual(args[i - 5:i - 1], ["-ss", "459.860", "-t", "39.812"])

    def test_editorial_command_owns_exact_tested_thread_limits(self):
        _, _, _, moment = editorial_source()
        args = sp.render_args([Path(f"/synthetic/scene-{i}.ppm") for i in range(8)],
                              Path("/synthetic/voice.flac"), Path("/synthetic/music.flac"),
                              Path("/synthetic/captions.ass"), moment, 40.312, "null",
                              Path("/synthetic/result.mp4"), edit_plan=EDITORIAL_PLAN,
                              hook_video=Path("/synthetic/opening.mkv"))
        self.assertEqual(args[1:5], ["-filter_complex_threads", "1", "-filter_threads", "1"])
        inputs = [i for i, value in enumerate(args) if value == "-i"]
        self.assertEqual(len(inputs), 10)
        for flag in ("-filter_complex_threads", "-filter_threads"):
            self.assertEqual(args.count(flag), 1)
            position = args.index(flag)
            self.assertEqual(args[position + 1], "1")
            self.assertLess(position, inputs[0])
        start = 1
        for index, end in enumerate(inputs):
            options = args[start:end]
            self.assertEqual(options.count("-threads"), 1, f"input {index} must own its decoder cap")
            self.assertEqual(options[options.index("-threads") + 1], "1")
            start = end + 2
        self.assertEqual(args.count("-threads"), 10)
        output = args[inputs[-1] + 2:]
        self.assertEqual(output.count("-threads:v"), 1)
        self.assertEqual(output[output.index("-threads:v") + 1], "1")
        self.assertEqual(args.count("-threads:v"), 1)
        # Resource bounds must not alter the graph, source seeks, dimensions, or codecs.
        resource_flags = {"-filter_complex_threads", "-filter_threads", "-threads", "-threads:v"}
        uncapped = []
        index = 0
        while index < len(args):
            if args[index] in resource_flags:
                index += 2
            else:
                uncapped.append(args[index])
                index += 1
        self.assertEqual(hashlib.sha256(json.dumps(uncapped, separators=(",", ":")).encode()).hexdigest(),
                         "5637a6a4a6493ab37fc886337718f98b274fe50e4f2fcae74422ce74c0d5689b")

    def test_legacy_render_command_is_unchanged_by_editorial_resource_limits(self):
        args = sp.render_args([Path("/synthetic/first.ppm"), Path("/synthetic/second.ppm")],
                              Path("/synthetic/voice.wav"), Path("/synthetic/music.wav"),
                              Path("/synthetic/captions.ass"), {"start": 12.0, "end": 44.0},
                              32.5, "null", Path("/synthetic/result.mp4"))
        self.assertNotIn("-filter_complex_threads", args)
        self.assertNotIn("-filter_threads", args)
        self.assertNotIn("-threads", args)
        self.assertNotIn("-threads:v", args)
        self.assertEqual(hashlib.sha256(json.dumps(args, separators=(",", ":")).encode()).hexdigest(),
                         "b7f6ae24310a5795195aa75e09e17e27d43d195a09c3ab3eb16243026d36179a")

    def test_actual_emitted_camera_expressions_reach_the_declared_endpoints_without_clamping(self):
        _, _, _, moment = editorial_source()
        _, parts = sp.editorial_picture([Path(f"/synthetic/scene-{i}.ppm") for i in range(8)],
                                        moment, EDITORIAL_PLAN, hook_video=Path("/synthetic/opening.mkv"))
        expressions = [re.search(r"zoompan=z='([^']+)':x='([^']+)':y='([^']+)'", part)
                       for part in parts if "zoompan=" in part]
        self.assertEqual(len(expressions), 8)
        frames = sp.scene_frame_plan(EDITORIAL_PLAN)["scene_frames"]
        # Evaluate only the code-owned expression vocabulary, never JSON/caller expressions.
        vocabulary = {"__builtins__": {}, "sin": math.sin, "PI": math.pi,
                      "lte": lambda a, b: a <= b, "choose": lambda test, a, b: a if test else b}
        for index, (match, count) in enumerate(zip(expressions, frames)):
            self.assertIsNotNone(match)
            z_expr, x_expr, y_expr = (text.replace("if(", "choose(") for text in match.groups())
            self.assertNotIn("min(", x_expr)
            self.assertNotIn("max(", x_expr)
            samples = []
            for frame in range(count):
                variables = {"on": frame, "iw": 2 * sp.VW, "ih": 2 * sp.VH}
                z = eval(z_expr, vocabulary, variables)
                variables["zoom"] = z
                x, y = eval(x_expr, vocabulary, variables), eval(y_expr, vocabulary, variables)
                self.assertTrue(all(math.isfinite(value) for value in (z, x, y)))
                self.assertGreaterEqual(x, -0.5)
                self.assertLessEqual(x + variables["iw"] / z, variables["iw"] + 0.5)
                self.assertGreaterEqual(y, -0.5)
                self.assertLessEqual(y + variables["ih"] / z, variables["ih"] + 0.5)
                samples.append((z, x, y))
            if index % 2 == 0:
                self.assertAlmostEqual(samples[0][0], 1, delta=1e-6)
                self.assertAlmostEqual(samples[-1][0], 1.08, delta=1e-6)
                self.assertTrue(all(a[0] <= b[0] for a, b in zip(samples, samples[1:])))
                for z, x, y in samples:
                    self.assertAlmostEqual(x, (2 * sp.VW - 2 * sp.VW / z) / 2, delta=1e-6)
                    self.assertAlmostEqual(y, (2 * sp.VH - 2 * sp.VH / z) / 2, delta=1e-6)
            else:
                self.assertTrue(all(z == 1.08 for z, _, _ in samples))
                self.assertAlmostEqual(samples[0][1], 0, delta=1e-6)
                self.assertAlmostEqual(samples[-1][1], 2 * sp.VW - 2 * sp.VW / 1.08, delta=1e-6)
                self.assertTrue(all(a[1] <= b[1] for a, b in zip(samples, samples[1:])))

    def test_real_portrait_crop_math_covers_sources_without_claiming_native_detail(self):
        for width, height in [(1344, 768), (2048, 2048), (16, 384), (384, 16), (1, 1)]:
            with self.subTest(size=(width, height)):
                crop = sp.portrait_crop(width, height)
                self.assertEqual((crop["source_width"], crop["source_height"]), (width, height))
                self.assertEqual((crop["crop_width"], crop["crop_height"]), (1080, 1920))
                self.assertGreaterEqual(crop["crop_x"], 0)
                self.assertGreaterEqual(crop["crop_y"], 0)
                self.assertLessEqual(crop["crop_x"] + 1080, crop["scaled_width"] + 0.5)
                self.assertLessEqual(crop["crop_y"] + 1920, crop["scaled_height"] + 0.5)
                self.assertLessEqual(crop["native_portrait_width"], width)
                self.assertLessEqual(crop["native_portrait_height"], height)
                self.assertAlmostEqual(crop["native_portrait_width"] / crop["native_portrait_height"], 9 / 16)
        garden = sp.portrait_crop(1344, 768)
        self.assertEqual((garden["native_portrait_width"], garden["native_portrait_height"]), (432, 768))
        for dimensions in [(True, 1920), (1080, False), (0, 1920), (-1, 1920), (1080.0, 1920)]:
            with self.subTest(dimensions=dimensions), self.assertRaises(ValueError):
                sp.portrait_crop(*dimensions)


class EditorialSerialStaging(unittest.TestCase):
    def test_serial_range_requires_a_measured_allowlisted_value(self):
        _, _, _, moment = editorial_source()
        stills = [Path(f"/synthetic/scene-{i}.ppm") for i in range(8)]
        arguments = (stills, Path("/synthetic/voice.flac"), Path("/synthetic/music.flac"),
                     Path("/synthetic/captions.ass"), moment, 40.312, "null", Path("/synthetic/result.mp4"))
        options = {"edit_plan": EDITORIAL_PLAN, "hook_video": Path("/synthetic/opening.mkv"),
                   "picture_video": Path("/synthetic/picture.mkv")}
        self.assertEqual(inspect.signature(sp.render_args).parameters["picture_range"].kind,
                         inspect.Parameter.KEYWORD_ONLY)
        with self.assertRaisesRegex(ValueError, "EDITORIAL_PICTURE_RANGE_REQUIRED"):
            sp.render_args(*arguments, **options)
        for value in ("", "limited", "full", "TV", "auto", "unknown,scale=1:1", 1, False):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "EDITORIAL_PICTURE_RANGE_INVALID"):
                sp.render_args(*arguments, **options, picture_range=value)
        for value, tag in (("unknown", "unspecified"), ("tv", "tv"), ("pc", "pc")):
            with self.subTest(value=value):
                args = sp.render_args(*arguments, **options, picture_range=value)
                graph = args[args.index("-filter_complex") + 1]
                self.assertIn(f"fps=30,setparams=range={tag},trim=end_frame=1209[picture]", graph)
                self.assertEqual(graph.count("setparams="), 1)

    def test_reference_range_probe_uses_the_real_capped_graph_and_one_frame(self):
        _, _, _, moment = editorial_source()
        stills = [Path(f"/synthetic/scene-{i}.ppm") for i in range(8)]
        hook = Path("/synthetic/opening.mkv")
        inputs, graph = sp.editorial_picture(stills, moment, EDITORIAL_PLAN, hook_video=hook)
        for measured in ("unknown", "tv", "pc"):
            with self.subTest(measured=measured), mock.patch.object(sp.subprocess, "run", return_value=
                    SimpleNamespace(stderr=f"[Parsed_showinfo] color_range:{measured} color_space:unknown\n")) as process:
                self.assertEqual(sp.reference_picture_range(stills, moment, EDITORIAL_PLAN, hook_video=hook), measured)
            command = process.call_args.args[0]
            self.assertEqual(process.call_args.kwargs, {"check": True, "capture_output": True, "text": True})
            self.assertEqual(command[command.index("-filter_complex") + 1],
                             ";".join([*graph, "[picture]trim=end_frame=1,showinfo[inspection]"]))
            self.assertEqual(command[command.index("-y") + 1:command.index("-filter_complex")], inputs)
            self.assertEqual(command[command.index("-frames:v") + 1], "1")
            self.assertEqual(command.count("-threads"), 8)
            for flag in ("-filter_complex_threads", "-filter_threads", "-threads:v"):
                self.assertEqual(command[command.index(flag) + 1], "1")
            self.assertEqual(command[-3:], ["-f", "null", "-"])
            self.assertNotIn("scale=108:192", command[command.index("-filter_complex") + 1])

    def test_reference_range_probe_fails_closed_without_unambiguous_metadata(self):
        _, _, _, moment = editorial_source()
        stills = [Path(f"/synthetic/scene-{i}.ppm") for i in range(8)]
        for stderr in ("", "color_range:invalid", "color_range:tv\ncolor_range:pc", "color_range:unknown\ncolor_range:unknown"):
            with self.subTest(stderr=stderr), mock.patch.object(sp.subprocess, "run", return_value=
                    SimpleNamespace(stderr=stderr)):
                with self.assertRaisesRegex(ValueError, "EDITORIAL_COLOR_RANGE_PROBE_FAILED"):
                    sp.reference_picture_range(stills, moment, EDITORIAL_PLAN, hook_video=Path("/synthetic/opening.mkv"))
        error = subprocess.CalledProcessError(7, ["ffmpeg"])
        with mock.patch.object(sp.subprocess, "run", side_effect=error):
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                sp.reference_picture_range(stills, moment, EDITORIAL_PLAN, hook_video=Path("/synthetic/opening.mkv"))
        self.assertIs(caught.exception, error)

    def test_scene_fade_and_final_commands_have_bounded_input_and_output_scopes(self):
        _, _, _, moment = editorial_source()
        stills = [Path(f"/synthetic/scene-{i}.ppm") for i in range(8)]
        hook = Path("/synthetic/opening.mkv")
        plan = sp.scene_frame_plan(EDITORIAL_PLAN)
        commands = []
        for index in range(8):
            args = sp.scene_clip_args(stills, moment, EDITORIAL_PLAN, index,
                                      Path(f"/synthetic/scene-{index}.mkv"), hook_video=hook)
            commands.append((args, 1, "ffv1"))
            self.assertEqual(args[args.index("-pix_fmt") + 1], "yuv420p")
            self.assertEqual(int(args[args.index("-frames:v") + 1]), plan["scene_frames"][index])
            expected = sp.editorial_scene_filter(0, plan["scene_frames"][index], plan["scene_spans"][index],
                                                 moment, EDITORIAL_PLAN["scenes"][index]["motion_profile"])
            self.assertEqual(args[args.index("-filter_complex") + 1], expected)
        for index in range(1, 8):
            args = sp.xfade_clip_args(Path("/synthetic/left.mkv"), Path("/synthetic/right.mkv"),
                                      index, EDITORIAL_PLAN, Path("/synthetic/fade.mkv"))
            commands.append((args, 2, "ffv1"))
            self.assertEqual(args[args.index("-pix_fmt") + 1], "yuv444p")
            self.assertEqual(int(args[args.index("-frames:v") + 1]), plan["scene_spans"][index][1])
            graph = args[args.index("-filter_complex") + 1]
            self.assertEqual(graph.count("xfade="), 1)
            self.assertNotIn("zoompan", graph)
        arguments = (stills, Path("/synthetic/voice.flac"), Path("/synthetic/music.flac"),
                     Path("/synthetic/captions.ass"), moment, 40.312, "null", Path("/synthetic/result.mp4"))
        final = sp.render_args(*arguments, edit_plan=EDITORIAL_PLAN, hook_video=hook,
                               picture_video=Path("/synthetic/picture.mkv"), picture_range="unknown")
        commands.append((final, 3, "libx264"))
        graph = final[final.index("-filter_complex") + 1]
        self.assertNotIn("xfade=", graph)
        self.assertNotIn("zoompan", graph)
        self.assertEqual(final[final.index("-i") + 1], "/synthetic/picture.mkv")
        reference = sp.render_args(*arguments, edit_plan=EDITORIAL_PLAN, hook_video=hook)
        audio_parts = lambda text: [part for part in text.split(";") if ":a]" in part or
                                   part.startswith(("[m][key]", "[vo][duck]"))]
        self.assertEqual(audio_parts(graph.replace("[1:a]", "[8:a]").replace("[2:a]", "[9:a]")),
                         audio_parts(reference[reference.index("-filter_complex") + 1]))
        self.assertEqual(inspect.signature(sp.render_args).parameters["picture_video"].kind,
                         inspect.Parameter.KEYWORD_ONLY)
        for args, count, codec in commands:
            with self.subTest(inputs=count, output=args[-1]):
                inputs = [i for i, value in enumerate(args) if value == "-i"]
                self.assertEqual(len(inputs), count)
                for flag in ("-filter_complex_threads", "-filter_threads"):
                    self.assertEqual(args.count(flag), 1)
                    self.assertEqual(args[args.index(flag) + 1], "1")
                    self.assertLess(args.index(flag), inputs[0])
                start = 1
                for end in inputs:
                    options = args[start:end]
                    self.assertEqual(options.count("-threads"), 1)
                    self.assertEqual(options[options.index("-threads") + 1], "1")
                    start = end + 2
                self.assertEqual(args.count("-threads"), count)
                output = args[inputs[-1] + 2:]
                self.assertEqual(output.count("-threads:v"), 1)
                self.assertEqual(output[output.index("-threads:v") + 1], "1")
                self.assertEqual(output[output.index("-c:v") + 1], codec)

    def test_progress_markers_follow_success_and_failures_never_claim_completion(self):
        _, _, _, moment = editorial_source()
        stills = [Path(f"/synthetic/scene-{i}.ppm") for i in range(8)]
        expected = []
        for index in range(8):
            for stage, name in [("SCENE", f"scene-{index:02d}.mkv"),
                                *(([("FADE", f"picture-{index:02d}.mkv")]) if index else [])]:
                expected += [("phase", f"SHORTS_PHASE_{stage}_{index:02d}_START", True),
                             ("run", name), ("phase", f"SHORTS_PHASE_{stage}_{index:02d}_END", True)]
        run_positions = [index for index, event in enumerate(expected) if event[0] == "run"]
        for failure in (None, *range(15)):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                tmp = Path(directory)
                observed = []
                run_count = 0
                def run(command):
                    nonlocal run_count
                    observed.append(("run", Path(command[-1]).name))
                    index = run_count
                    run_count += 1
                    if index == failure:
                        raise subprocess.CalledProcessError(19, command)
                    Path(command[-1]).write_bytes(b"synthetic orchestration witness, not media")
                def phase(text, *, flush):
                    observed.append(("phase", text, flush))
                with mock.patch.object(sp, "run", side_effect=run), mock.patch("builtins.print", side_effect=phase):
                    if failure is None:
                        result = sp.write_editorial_picture(stills, moment, EDITORIAL_PLAN, tmp,
                                                            hook_video=Path("/synthetic/opening.mkv"))
                        self.assertEqual(result, tmp / "picture-07.mkv")
                    else:
                        with self.assertRaises(subprocess.CalledProcessError):
                            sp.write_editorial_picture(stills, moment, EDITORIAL_PLAN, tmp,
                                                       hook_video=Path("/synthetic/opening.mkv"))
                self.assertEqual(observed, expected if failure is None else expected[:run_positions[failure] + 1])
                if failure is None:
                    self.assertEqual([path.name for path in tmp.iterdir()], ["picture-07.mkv"])


class EditorialOpeningAtmosphere(unittest.TestCase):
    """Exercise actual atmosphere pixels with a fixed camera, no grain, and no provider."""
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        cls.base = np.full((192, 108, 3), 0.3, dtype=np.float32)

    @staticmethod
    def envelope(frame):
        t = frame / 30
        if not 0 <= t < 3:
            return 0.0
        smooth = lambda u: u * u * (3 - 2 * u)
        return smooth(min(1, t / 0.35)) * smooth(min(1, (3 - t) / 0.45))

    def test_transparent_endpoints_determinism_seed_and_finite_bounded_composition(self):
        np = self.np
        base = self.base.copy()
        for frame in (-1, 0, 90, 120):
            output, alpha = sp.opening_atmosphere(base, frame)
            np.testing.assert_array_equal(output, base)
            np.testing.assert_array_equal(alpha, np.zeros(base.shape[:2]))
        for frame in range(91):
            output, alpha = sp.opening_atmosphere(base, frame, seed=231005)
            self.assertEqual(output.shape, base.shape)
            self.assertEqual(alpha.shape, base.shape[:2])
            self.assertTrue(np.issubdtype(output.dtype, np.floating))
            self.assertTrue(np.issubdtype(alpha.dtype, np.floating))
            self.assertTrue(np.isfinite(output).all() and np.isfinite(alpha).all())
            self.assertGreaterEqual(float(output.min()), 0)
            self.assertLessEqual(float(output.max()), 1)
            self.assertGreaterEqual(float(alpha.min()), 0)
            self.assertLessEqual(float(alpha.max()), 0.18 + 1e-7)
        a, aa = sp.opening_atmosphere(base, 45, seed=231005)
        b, ba = sp.opening_atmosphere(base, 45, seed=231005)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(aa, ba)
        c, _ = sp.opening_atmosphere(base, 45, seed=231006)
        self.assertGreater(float(np.abs(a - c).max()), 0)
        np.testing.assert_array_equal(base, self.base)

    def test_exact_moving_fog_without_camera_particles_grain_or_source_highlights(self):
        np = self.np
        h, w = self.base.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        with mock.patch.object(sp, "opening_particles", return_value=[]):
            images = []
            for frame in (15, 45):
                t = frame / 30
                image, alpha = sp.opening_atmosphere(self.base, frame)
                fog = np.exp(-((yy / h - 0.72) / 0.22) ** 2) * (
                    0.5 + 0.25 * np.sin(2 * math.pi * (xx / w - 0.035 * t))
                    + 0.25 * np.sin(2 * math.pi * (1.7 * xx / w + 0.7 * yy / h - 0.05 * t)))
                np.testing.assert_allclose(alpha, 0.09 * self.envelope(frame) * fog, atol=2e-6, rtol=2e-6)
                images.append(image)
            luma_delta = np.abs((images[0] - images[1]) @ np.array([0.2126, 0.7152, 0.0722]))
            self.assertGreaterEqual(float(np.mean(luma_delta > 1 / 1024)), 0.05)

    def test_full_motion_changes_real_luminance_and_has_no_adjacent_flash(self):
        np = self.np
        outputs = [sp.opening_atmosphere(self.base, i)[0] for i in range(91)]
        luma = [frame @ np.array([0.2126, 0.7152, 0.0722]) for frame in outputs]
        self.assertGreaterEqual(float(np.mean(np.abs(luma[15] - luma[45]) > 1 / 1024)), 0.05)
        self.assertLessEqual(max(abs(float(a.mean() - b.mean())) for a, b in zip(luma, luma[1:])), 0.005)
        with mock.patch.object(sp, "opening_particles", return_value=[]):
            fog = [sp.opening_atmosphere(self.base, i)[0] for i in (15, 45)]
        # Difference from a same-frame no-particle baseline isolates particle pixels, not grain.
        particles = [outputs[i] - background for i, background in zip((15, 45), fog)]
        self.assertGreater(float(np.abs(particles[0]).max()), 1 / 1024)
        self.assertGreater(float(np.abs(particles[1]).max()), 1 / 1024)
        self.assertGreater(float(np.abs(particles[0] - particles[1]).max()), 1 / 1024)

    def test_particle_paths_are_continuous_scaled_bounded_and_outside_caption_area(self):
        particles = [sp.opening_particles(i, 1080, 1920, seed=231005) for i in range(91)]
        self.assertTrue(all(len(frame) == 24 for frame in particles))
        self.assertEqual(particles[45], sp.opening_particles(45, 1080, 1920, seed=231005))
        self.assertNotEqual(particles[45], sp.opening_particles(45, 1080, 1920, seed=231006))
        scaled = sp.opening_particles(45, 108, 192, seed=231005)
        for index in range(24):
            first = particles[0][index]
            self.assertTrue(50 <= first["x"] <= 1030)
            self.assertTrue(100 <= first["y"] <= 900)
            self.assertTrue(1 <= first["radius"] <= 2.5)
            vx = (particles[1][index]["x"] - first["x"]) * 30
            vy = (particles[1][index]["y"] - first["y"]) * 30
            self.assertTrue(6 - 1e-9 <= vx <= 12 + 1e-9)
            self.assertTrue(-18 - 1e-9 <= vy <= -10 + 1e-9)
            for frame_index, frame in enumerate(particles):
                particle = frame[index]
                self.assertTrue(all(math.isfinite(particle[key]) for key in ("x", "y", "radius", "alpha")))
                self.assertAlmostEqual(particle["x"], first["x"] + frame_index / 30 * vx, delta=1e-8)
                self.assertAlmostEqual(particle["y"], first["y"] + frame_index / 30 * vy, delta=1e-8)
                self.assertGreaterEqual(particle["alpha"], 0)
                self.assertLessEqual(particle["alpha"], 0.1 * self.envelope(frame_index) + 1e-8)
                self.assertGreater(particle["x"] - particle["radius"], 0)
                self.assertLess(particle["x"] + particle["radius"], 1080)
                self.assertGreater(particle["y"] - particle["radius"], 0)
                self.assertLess(particle["y"] + particle["radius"], sp.CAPTION_Y - 150)
            for key in ("x", "y", "radius"):
                self.assertAlmostEqual(scaled[index][key], particles[45][index][key] / 10, delta=1e-8)
            self.assertAlmostEqual(scaled[index]["alpha"], particles[45][index]["alpha"], delta=1e-8)

    def test_highlight_light_is_source_derived_and_uses_bounded_gaussian_scale(self):
        import cv2
        np = self.np
        base = self.base.copy()
        base[20:45, 45:65] = 0.95
        with mock.patch.object(cv2, "GaussianBlur", wraps=cv2.GaussianBlur) as blur:
            output, alpha = sp.opening_atmosphere(base, 45)
        self.assertTrue(blur.called, "warm light must be smoothed source highlights, not an invented sun")
        expected_luma = base @ np.array([0.2126, 0.7152, 0.0722])
        expected_highlights = np.clip((expected_luma - 0.65) / 0.35, 0, 1)
        matching = [call for call in blur.call_args_list
                    if getattr(call.args[0], "shape", None) == base.shape[:2]
                    and np.allclose(call.args[0], expected_highlights, atol=1e-6)]
        self.assertTrue(matching, "blur input must be the original source's thresholded luminance")
        for call in matching:
            sigma = call.kwargs.get("sigmaX", call.args[2] if len(call.args) > 2 else None)
            self.assertAlmostEqual(sigma, 0.025 * base.shape[1])
        self.assertLessEqual(float(alpha.max()), 0.18 + 1e-7)
        self.assertTrue(np.isfinite(output).all())


class EditorialProducerMain(unittest.TestCase):
    def setUp(self):
        import shorts_edit_plan
        from test_shorts_edit_plan import INPUTS_RAW
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work, self.source, self.out = self.root / "work", self.root / "source", self.root / "output"
        self.work.mkdir()
        (self.source / "shorts").mkdir(parents=True)
        fixture = HERE / "fixtures" / "shorts-pilot-005-20261020"
        self.timeline_path = self.work / "timeline.json"
        self.script_path = self.source / "script.json"
        self.inputs_path = self.source / "shorts" / "inputs.json"
        self.source_bytes = {
            self.timeline_path: (fixture / "out" / "timeline.json").read_bytes(),
            self.script_path: (fixture / "script.json").read_bytes(),
            self.inputs_path: INPUTS_RAW,
        }
        for path, raw in self.source_bytes.items():
            path.write_bytes(raw)
        self.assertEqual(hashlib.sha256(INPUTS_RAW).hexdigest(), EDITORIAL_PLAN["source_sha256"]["inputs"])
        plan_path = self.root / "literal-plan.json"
        plan_path.write_text(json.dumps(EDITORIAL_PLAN))
        self.selection_path = self.root / "prepared-selection.json"
        self.prepared = shorts_edit_plan.main(plan_path, self.timeline_path, self.script_path,
                                              self.inputs_path, self.selection_path)
        self.args = tuple(map(str, (self.work, self.selection_path, self.script_path, self.root / "images",
                                   self.root / "unused-figure", self.root / "music", self.out)))

    def write_selection(self):
        self.selection_path.write_text(json.dumps(self.prepared))

    def assert_rejected_before_production(self):
        with mock.patch.object(sp, "produce") as produce, \
                mock.patch.object(sp, "run") as render, \
                mock.patch.object(sp.subprocess, "run") as subprocess_run, \
                mock.patch.object(shorts_select, "rubric") as provider, redirect_stdout(io.StringIO()):
            with self.assertRaises((ValueError, SystemExit, TypeError, KeyError)):
                sp.main(*self.args)
        produce.assert_not_called()
        render.assert_not_called()
        subprocess_run.assert_not_called()
        provider.assert_not_called()
        self.assertFalse((self.out / "shorts.json").exists())

    def test_valid_prepared_selection_calls_produce_exactly_once_with_reconstructed_source(self):
        fake_record = {"file": "short-00.mp4", "seconds": 40.3,
                       "hook": EDITORIAL_PLAN["candidate"]["hook"], "publish": False}
        with mock.patch.object(sp, "produce", return_value=fake_record) as produce, \
                mock.patch.object(sp, "run") as render, \
                mock.patch.object(sp.subprocess, "run") as subprocess_run, \
                mock.patch.object(shorts_select, "rubric") as provider, \
                mock.patch.dict(os.environ, {"HERO_GEMINI_API_KEY": "configured-fake-offline-key"}), \
                redirect_stdout(io.StringIO()):
            sp.main(*self.args)
        produce.assert_called_once()
        call = produce.call_args
        source = load(self.timeline_path)
        self.assertEqual(call.args[1]["sentences"], source["sentences"][106:116])
        self.assertEqual(len(call.args[1]["sentences"]), 10)
        self.assertEqual(call.args[1], self.prepared["chosen"][0])
        self.assertEqual(call.args[2], 0)
        self.assertEqual(call.args[9], source["sentences"])
        self.assertEqual(call.kwargs["edit_plan"], EDITORIAL_PLAN)
        self.assertEqual(call.kwargs["script_refs"],
                         {s["id"]: s.get("reference") for s in load(self.script_path)["segments"]})
        manifest = load(self.out / "shorts.json")
        self.assertEqual(manifest["shorts"], [fake_record])
        self.assertEqual(manifest["edit_plan"], EDITORIAL_PLAN)
        self.assertIsNone(manifest["selection_rubric_model"])
        self.assertEqual(manifest["rejected_r8"], [])
        render.assert_not_called()
        subprocess_run.assert_not_called()
        provider.assert_not_called()

    def test_tampered_prepared_candidates_or_selection_mode_never_reach_produce(self):
        original = json.dumps(self.prepared)
        for mutation in ("forged_text", "forged_cut", "duplicate", "empty", "wrong_mode"):
            with self.subTest(mutation=mutation):
                self.prepared = json.loads(original)
                if mutation == "forged_text":
                    self.prepared["chosen"][0]["sentences"][0]["text"] = "A forged prayer."
                    self.prepared["chosen"][0]["final_score"] = 1000000
                elif mutation == "forged_cut":
                    self.prepared["chosen"][0].update(start=1404.681, end=1440.736)
                elif mutation == "duplicate":
                    self.prepared["chosen"] *= 2
                elif mutation == "empty":
                    self.prepared["chosen"] = []
                else:
                    self.prepared["selection_mode"] = "LEGACY"
                self.write_selection()
                self.assert_rejected_before_production()

    def test_tampered_editorial_plan_never_reaches_produce(self):
        original = json.dumps(self.prepared)
        for mutation in ("tail", "motion", "source_hash", "extra", "pilot", "order", "scene_count",
                         "exception", "exception_target", "bool", "nan", "hook_policy"):
            with self.subTest(mutation=mutation):
                self.prepared = json.loads(original)
                plan = self.prepared["edit_plan"]
                if mutation == "tail":
                    plan["tail_seconds"] = 0.4
                elif mutation == "motion":
                    plan["scenes"][0]["motion_profile"] = "arbitrary_expression"
                elif mutation == "source_hash":
                    plan["source_sha256"]["timeline"] = "0" * 64
                elif mutation == "pilot":
                    plan["source_pilot"] = "pilot-006"
                elif mutation == "order":
                    plan["scenes"][0], plan["scenes"][1] = plan["scenes"][1], plan["scenes"][0]
                elif mutation == "scene_count":
                    plan["scenes"].pop()
                elif mutation == "exception":
                    del plan["rhythm_exception"]
                elif mutation == "exception_target":
                    plan["rhythm_exception"]["target_slot"] = "2026-10-21T20:00:00Z"
                elif mutation == "bool":
                    plan["scenes"][0]["nominal_start"] = False
                elif mutation == "nan":
                    plan["tail_seconds"] = float("nan")
                elif mutation == "hook_policy":
                    plan["hook_animation"]["caption_policy"] = "duplicate_overlay"
                else:
                    plan["force_publish"] = True
                self.write_selection()
                self.assert_rejected_before_production()

    def test_missing_or_null_plan_cannot_downgrade_editorial_selection_to_legacy(self):
        original = json.dumps(self.prepared)
        for missing in (False, True):
            with self.subTest(missing=missing):
                self.prepared = json.loads(original)
                if missing:
                    del self.prepared["edit_plan"]
                else:
                    self.prepared["edit_plan"] = None
                self.write_selection()
                self.assert_rejected_before_production()

    def test_newline_change_to_each_raw_source_fails_hash_before_produce(self):
        for changed, raw in self.source_bytes.items():
            with self.subTest(source=changed.name):
                for path, baseline in self.source_bytes.items():
                    path.write_bytes(baseline)
                changed.write_bytes(raw + b"\n")
                self.assertEqual(json.loads(changed.read_bytes()), json.loads(raw))
                self.assertNotEqual(hashlib.sha256(changed.read_bytes()).hexdigest(), hashlib.sha256(raw).hexdigest())
                self.assert_rejected_before_production()


class EditorialProducerSources(unittest.TestCase):
    def test_editorial_render_uses_the_hash_verified_original_flac_and_legacy_keeps_wav(self):
        timeline, script, refs, moment = editorial_source()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, images, out = root / "work", root / "images", root / "shorts"
            for folder in (work, images, out):
                folder.mkdir()
            original_flac, legacy_wav, music = root / "voice.flac", work / "voice.wav", root / "music.flac"
            # Explicitly distinct dummy files: a converted/unbound WAV must never replace the
            # verified original on the editorial path. No source audio or output media is rendered.
            original_flac.write_bytes(b"synthetic mock of original source")
            legacy_wav.write_bytes(b"synthetic different unbound conversion")
            for scene in EDITORIAL_PLAN["scenes"]:
                (images / (scene["image_id"] + ".json")).write_text(json.dumps({
                    "id": scene["image_id"], "release_asset": scene["asset"], "sha256": scene["sha256"],
                    "models": {"synthetic-test": {"license": "synthetic test declaration, not production evidence"}}}))
            expected_hashes = {
                original_flac: EDITORIAL_PLAN["voice"]["sha256"],
                music: EDITORIAL_PLAN["music"]["sha256"],
                out / "short-00.mp4": "f" * 64,
                **{images / (scene["image_id"] + ".png"): scene["sha256"] for scene in EDITORIAL_PLAN["scenes"]},
            }
            for edit_plan, expected_voice in [(EDITORIAL_PLAN, original_flac), (None, legacy_wav)]:
                with self.subTest(editorial=edit_plan is not None):
                    fake_cinematic = SimpleNamespace(grade=mock.Mock(), look=mock.Mock(return_value="null"))
                    with mock.patch.dict(sys.modules, {"cinematic": fake_cinematic}), \
                            mock.patch.object(sp, "sha256", side_effect=lambda path: expected_hashes[Path(path)]) as hashed, \
                            mock.patch.object(sp.subprocess, "run", return_value=SimpleNamespace(
                                stdout='{"streams":[{"width":1344,"height":768}]}')) as probe, \
                            mock.patch.object(sp, "probe_duration", return_value=40.3), \
                            mock.patch.object(sp, "vertical_still") as prepare, \
                            mock.patch.object(sp, "write_opening_video", return_value=root / "synthetic-opening.mkv") as opening, \
                            mock.patch.object(sp, "write_editorial_picture", return_value=root / "synthetic-picture.mkv") as picture, \
                            mock.patch.object(sp, "reference_picture_range", return_value="unknown") as range_probe, \
                            mock.patch.object(sp, "ass", wraps=sp.ass) as captions, \
                            mock.patch.object(sp, "render_args", wraps=sp.render_args) as renderer, \
                            mock.patch.object(sp, "run") as render, \
                            mock.patch("builtins.print") as phase:
                        record = sp.produce(work, moment, 0, script, images, None, music, out,
                                            timeline_sentences=timeline["sentences"], script_refs=refs,
                                            edit_plan=edit_plan)
                        renderer.assert_called_once()
                        render.assert_called_once()
                        self.assertEqual(renderer.call_args.args[1], expected_voice)
                        actual_args = render.call_args.args[0]
                        actual_inputs = [actual_args[i + 1] for i, value in enumerate(actual_args) if value == "-i"]
                        self.assertIn(str(expected_voice), actual_inputs)
                        self.assertEqual(len(actual_inputs), 3 if edit_plan is not None else 4)
                        self.assertEqual(prepare.call_count, 8 if edit_plan is not None else 2)
                        self.assertEqual(record["sha256"], "f" * 64)
                        if edit_plan is not None:
                            self.assertEqual(phase.call_args_list, [
                                mock.call(f"SHORTS_PHASE_{name}", flush=True) for name in (
                                    "PREPARE_START", "PREPARE_END", "HOOK_START", "HOOK_END",
                                    "RANGE_START", "RANGE_END", "ENCODE_START", "ENCODE_END")])
                            self.assertEqual(hashed.call_args_list[0].args[0], expected_voice)
                            self.assertNotIn(str(legacy_wav), actual_inputs)
                            self.assertEqual(probe.call_count, 8)
                            opening.assert_called_once_with(out / "tmp-00" / "s00.png",
                                                            out / "tmp-00" / "opening.mkv")
                            self.assertEqual(renderer.call_args.kwargs["hook_video"], root / "synthetic-opening.mkv")
                            picture.assert_called_once_with([out / "tmp-00" / f"s{i:02d}.png" for i in range(8)],
                                                            moment, edit_plan, out / "tmp-00",
                                                            hook_video=root / "synthetic-opening.mkv")
                            self.assertEqual(renderer.call_args.kwargs["picture_video"], root / "synthetic-picture.mkv")
                            self.assertEqual(renderer.call_args.kwargs["picture_range"], "unknown")
                            range_probe.assert_called_once_with(
                                [out / "tmp-00" / f"s{i:02d}.png" for i in range(8)], moment, edit_plan,
                                hook_video=root / "synthetic-opening.mkv")
                            self.assertEqual(actual_inputs[0], str(root / "synthetic-picture.mkv"))
                            self.assertEqual(captions.call_args.kwargs["hook_mode"], "caption_only")
                            self.assertEqual({Path(call.args[0]).stem for call in hashed.call_args_list
                                              if Path(call.args[0]).suffix == ".png"},
                                             {scene["image_id"] for scene in EDITORIAL_PLAN["scenes"]})
                            self.assertEqual(record["hook_mode"], "caption_only")
                            self.assertTrue(record["hook_shown"])
                            self.assertEqual(record["scenes"], [s["image_id"] for s in EDITORIAL_PLAN["scenes"]])
                            self.assertIs(record["publish"], False)
                        else:
                            phase.assert_not_called()
                            self.assertNotIn(str(original_flac), actual_inputs)
                            probe.assert_not_called()
                            opening.assert_not_called()
                            picture.assert_not_called()
                            range_probe.assert_not_called()
                            self.assertEqual(captions.call_args.kwargs["hook_mode"], "overlay")


    def test_each_approved_image_is_hash_and_mapping_checked_before_any_render(self):
        timeline, script, refs, moment = editorial_source()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, images, out = root / "work", root / "images", root / "output"
            work.mkdir()
            images.mkdir()
            music = root / "music.flac"
            hashes = {root / "voice.flac": EDITORIAL_PLAN["voice"]["sha256"],
                      music: EDITORIAL_PLAN["music"]["sha256"],
                      **{images / (scene["image_id"] + ".png"): scene["sha256"]
                         for scene in EDITORIAL_PLAN["scenes"]}}
            for changed in range(8):
                for mutation in ("bytes", "asset", "license"):
                    with self.subTest(scene=changed, mutation=mutation):
                        for index, scene in enumerate(EDITORIAL_PLAN["scenes"]):
                            meta = {"id": scene["image_id"], "release_asset": scene["asset"],
                                    "sha256": scene["sha256"], "models": {"synthetic": {"license": "test"}}}
                            if index == changed and mutation == "asset":
                                meta["release_asset"] = "wrong-asset.png"
                            if index == changed and mutation == "license":
                                meta["models"] = {}
                            (images / (scene["image_id"] + ".json")).write_text(json.dumps(meta))
                        altered = images / (EDITORIAL_PLAN["scenes"][changed]["image_id"] + ".png")
                        digest = lambda path: "0" * 64 if mutation == "bytes" and Path(path) == altered else hashes[Path(path)]
                        with mock.patch.object(sp, "sha256", side_effect=digest), \
                                mock.patch.object(sp.subprocess, "run") as process, \
                                mock.patch.object(sp.subprocess, "Popen") as encoder, \
                                mock.patch.object(sp, "run") as render, \
                                mock.patch.object(sp, "vertical_still") as prepare, \
                                mock.patch.object(sp, "write_opening_video") as opening, \
                                mock.patch.object(shorts_select, "rubric") as provider:
                            with self.assertRaisesRegex(ValueError, "IMAGE_(HASH_MISMATCH|MAPPING_MISMATCH|LICENSE_MISSING)"):
                                sp.produce(work, moment, 0, script, images, None, music, out,
                                           timeline_sentences=timeline["sentences"], script_refs=refs,
                                           edit_plan=EDITORIAL_PLAN)
                        for spy in (process, encoder, render, prepare, opening, provider):
                            spy.assert_not_called()
                        self.assertFalse(out.exists())


class EditorialSyntheticFFmpeg(unittest.TestCase):
    """Synthetic source/render measurements only: never production or watched-review evidence."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.width, cls.height = 108, 192
        cls.stills = [cls.root / f"scene-{i}.ppm" for i in range(8)]
        for index, path in enumerate(cls.stills):
            synthetic_ppm(path, 216, 384, index)
        _, _, _, cls.moment = editorial_source()
        # Local 8 kHz tones retain the real source-seek interval. A different terminal
        # frequency guards against padding silently replacing the last spoken material.
        cls.audio, cls.music = cls.root / "synthetic.wav", cls.root / "silence.wav"
        sample_rate = 8000
        one_second = b"".join(int(900 * math.sin(2 * math.pi * 220 * i / sample_rate))
                              .to_bytes(2, "little", signed=True) for i in range(sample_rate))
        seconds = math.ceil(sp.MUSIC_OFFSET + 501)
        pcm = bytearray(one_second * seconds)
        marker_start = round((cls.moment["end"] - 0.16) * sample_rate)
        marker_end = round(cls.moment["end"] * sample_rate)
        pcm[marker_start * 2:marker_end * 2] = b"".join(
            int(900 * math.sin(2 * math.pi * 1100 * i / sample_rate)).to_bytes(2, "little", signed=True)
            for i in range(marker_end - marker_start))
        for path, data in ((cls.audio, pcm), (cls.music, bytes(len(pcm)))):
            with wave.open(str(path), "wb") as sound:
                sound.setnchannels(1)
                sound.setsampwidth(2)
                sound.setframerate(sample_rate)
                sound.writeframes(data)
        cls.captions = cls.root / "empty.ass"
        cls.captions.write_text(sp.HEAD)
        cls.output, cls.pcm_output = cls.root / "synthetic-stills.mp4", cls.root / "preencoder.wav"
        cls.hook = cls.root / "synthetic-opening.mkv"
        sp.write_opening_video(cls.stills[0], cls.hook)
        cls.serial_tmp = cls.root / "serial"
        cls.serial_tmp.mkdir()
        cls.serial_probes = []
        def run_and_probe(command):
            result = cls.invoke(command)
            probe = json.loads(cls.invoke([
                "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                "-show_entries", "stream=codec_name,pix_fmt,width,height,avg_frame_rate,nb_read_frames,color_range,color_space,color_primaries,color_transfer,chroma_location,sample_aspect_ratio",
                "-of", "json", command[-1]]).stdout)["streams"][0]
            cls.serial_probes.append(probe)
            return result
        with mock.patch.multiple(sp, VW=cls.width, VH=cls.height), \
                mock.patch.object(sp, "run", side_effect=run_and_probe) as serial_run:
            cls.picture_range = sp.reference_picture_range(cls.stills, cls.moment, EDITORIAL_PLAN,
                                                           hook_video=cls.hook)
            cls.picture = sp.write_editorial_picture(cls.stills, cls.moment, EDITORIAL_PLAN,
                                                     cls.serial_tmp, hook_video=cls.hook)
            cls.serial_commands = [call.args[0] for call in serial_run.call_args_list]
            args = sp.render_args(cls.stills, cls.audio, cls.music, cls.captions,
                                  cls.moment, 40.312, "null", cls.output, edit_plan=EDITORIAL_PLAN,
                                  hook_video=cls.hook, picture_video=cls.picture, picture_range=cls.picture_range)
        # Keep all production processing. An output-only split captures the actual
        # pre-AAC samples, without changing any media filter or resampling decision.
        graph_index = args.index("-filter_complex") + 1
        args[graph_index] = args[graph_index].replace("[aout]", "[preencoder]") + (
            ";[preencoder]asplit=2[aout][samplecheck]")
        args += ["-map", "[samplecheck]", "-c:a", "pcm_s16le", str(cls.pcm_output)]
        args[args.index("-preset") + 1] = "ultrafast"
        cls.invoke(args)
        cls.probe = json.loads(cls.invoke([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,pix_fmt,avg_frame_rate,nb_read_frames,duration",
            "-of", "json", str(cls.output)]).stdout)["streams"][0]
        cls.rgb = cls.invoke(["ffmpeg", "-v", "error", "-i", str(cls.output),
                              "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]).stdout
        cls.frame_bytes = cls.width * cls.height * 3
        cls.frames = [cls.rgb[i:i + cls.frame_bytes] for i in range(0, len(cls.rgb), cls.frame_bytes)]

    @classmethod
    def invoke(cls, args):
        result = subprocess.run(args, capture_output=True, timeout=180,
                                env=dict(os.environ, XDG_CACHE_HOME=str(cls.root / "cache")))
        if result.returncode:
            raise AssertionError(f"SYNTHETIC_FFMPEG_FAILED: {result.stderr.decode(errors='replace')[-4000:]}")
        return result

    def test_actual_decoded_frame_count_duration_and_all_timestamps(self):
        self.assertEqual((self.probe["width"], self.probe["height"]), (108, 192))
        self.assertEqual(self.probe["codec_name"], "h264")
        self.assertEqual(self.probe["pix_fmt"], "yuv420p")
        self.assertEqual(self.probe["avg_frame_rate"], "30/1")
        self.assertEqual(int(self.probe["nb_read_frames"]), len(self.frames))
        self.assertEqual(len(self.frames), 1209)
        self.assertTrue(all(len(frame) == self.frame_bytes for frame in self.frames))
        self.assertAlmostEqual(float(self.probe["duration"]), 40.3, delta=1 / 30)
        self.assertLessEqual(abs(float(self.probe["duration"]) - 40.312), 1 / 30)
        frames = json.loads(self.invoke([
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
            "-show_entries", "frame=best_effort_timestamp_time", "-of", "json",
            str(self.output)]).stdout)["frames"]
        self.assertEqual(len(frames), 1209)
        for index, frame in enumerate(frames):
            self.assertAlmostEqual(float(frame["best_effort_timestamp_time"]), index / 30, delta=1e-6)

    def test_actual_eight_scene_fingerprints_all_seven_fades_and_final_frames(self):
        import numpy as np
        images = np.frombuffer(self.rgb, np.uint8).reshape((-1, self.height, self.width, 3))
        colors = images.mean(axis=(1, 2))
        references = np.array([colors[index * 150 + 75] for index in range(8)])
        self.assertEqual(len({tuple(np.rint(color)) for color in references}), 8)
        for i, expected in enumerate(SYNTHETIC_COLORS):
            self.assertLess(float(np.linalg.norm(references[i] - np.array(expected) - 11)), 15)
        nearest = np.linalg.norm(colors[:, None, :] - references[None, :, :], axis=2).argmin(axis=1)
        starts, ends = [143, 293, 443, 593, 743, 893, 1043], [158, 308, 458, 608, 758, 908, 1058]
        spans = [(0, starts[0]), *zip(ends[:-1], starts[1:]), (ends[-1], 1209)]
        self.assertEqual(len(spans), 8)
        for i, (start, end) in enumerate(spans):
            self.assertTrue(np.all(nearest[start:end] == i), (i, start, end))
        for i, (start, end) in enumerate(zip(starts, ends)):
            a, b = references[i], references[i + 1]
            direction = b - a
            progression = ((colors[start:end + 1] - a) @ direction) / (direction @ direction)
            self.assertLess(abs(float(progression[0])), 0.05)
            self.assertLess(abs(float(progression[-1] - 1)), 0.05)
            self.assertGreater(int(np.sum((progression > 0.1) & (progression < 0.9))), 8)
            self.assertTrue(np.all(np.diff(progression) > -0.03), (i, progression.tolist()))
            self.assertLess(float(np.max(np.abs(np.diff(progression)))), 0.12,
                            "a transition must not reset or jump")
        hashes = [hashlib.sha256(frame).hexdigest() for frame in self.frames]
        self.assertNotEqual(hashes[0], hashes[120])
        self.assertNotEqual(hashes[1058], hashes[-1])
        self.assertNotEqual(hashes[-61], hashes[-1], "the ending cannot freeze for two seconds")
        self.assertTrue(np.all(images.max(axis=(1, 2, 3)) > 100))
        # The atmosphere endpoint must join the unaltered source without a flash/reset.
        means = images.mean(axis=(1, 2, 3)) / 255
        self.assertLess(float(np.max(np.abs(np.diff(means[80:101])))), 0.01)
        black = self.invoke([
            "ffmpeg", "-hide_banner", "-i", str(self.output), "-an", "-vf",
            "blackdetect=d=0.0333333333333333:pix_th=0.02:pic_th=0.99", "-f", "null", "-"])
        self.assertNotIn(b"black_start:", black.stderr)

    def test_resource_limits_preserve_all_preencoder_picture_frames_and_timestamps(self):
        with mock.patch.multiple(sp, VW=self.width, VH=self.height):
            args = sp.render_args(self.stills, self.audio, self.music, self.captions,
                                  self.moment, 40.312, "null", self.root / "not-encoded.mp4",
                                  edit_plan=EDITORIAL_PLAN, hook_video=self.hook)
        graph_index = args.index("-filter_complex") + 1
        parts = args[graph_index].split(";")
        finish = next(index for index, part in enumerate(parts) if part.startswith("[picture]"))
        # Tap the actual geometric picture before film finish, captions, or encoding.
        # Only the diagnostic output format changes; the production camera/fade graph stays exact.
        graph = ";".join(parts[:finish])
        output_cap = args.index("-threads:v")
        capped = [*args[:graph_index], graph, "-map", "[picture]", "-an",
                  *args[output_cap:output_cap + 2], "-c:v", "rawvideo", "-fps_mode", "passthrough",
                  "-f", "framemd5", "-"]
        uncapped = []
        index = 0
        while index < len(capped):
            if capped[index] in {"-filter_complex_threads", "-filter_threads", "-threads", "-threads:v"}:
                index += 2
            else:
                uncapped.append(capped[index])
                index += 1
        fingerprints = []
        for command in (uncapped, capped):
            result = self.invoke(command).stdout.decode()
            records = [[value.strip() for value in line.split(",")]
                       for line in result.splitlines() if line and not line.startswith("#")]
            self.assertEqual(len(records), 1209)
            self.assertEqual([int(row[2]) for row in records], list(range(1209)))
            fingerprints.append(records)
        self.assertEqual(fingerprints[0], fingerprints[1],
                         "thread bounds must preserve each preencoder picture frame and its PTS")

    def test_serial_lossless_picture_matches_all_1209_monolithic_frames_and_pts(self):
        with mock.patch.multiple(sp, VW=self.width, VH=self.height):
            args = sp.render_args(self.stills, self.audio, self.music, self.captions,
                                  self.moment, 40.312, "null", self.root / "reference.mp4",
                                  edit_plan=EDITORIAL_PLAN, hook_video=self.hook)
        graph_index = args.index("-filter_complex") + 1
        parts = args[graph_index].split(";")
        finish = next(index for index, part in enumerate(parts) if part.startswith("[picture]"))
        reference = [*args[:graph_index], ";".join(parts[:finish]), "-map", "[picture]", "-an",
                     "-threads:v", "1", "-c:v", "rawvideo", "-fps_mode", "passthrough",
                     "-f", "framemd5", "-"]
        with mock.patch.multiple(sp, VW=self.width, VH=self.height):
            final_args = sp.render_args(self.stills, self.audio, self.music, self.captions,
                                        self.moment, 40.312, "null", self.root / "serial-reference.mp4",
                                        edit_plan=EDITORIAL_PLAN, hook_video=self.hook,
                                        picture_video=self.picture, picture_range=self.picture_range)
        final_graph_index = final_args.index("-filter_complex") + 1
        final_parts = final_args[final_graph_index].split(";")
        final_finish = next(index for index, part in enumerate(final_parts) if part.startswith("[picture]"))
        serial = [*final_args[:final_graph_index], ";".join(final_parts[:final_finish]),
                  "-map", "[picture]", "-an", "-threads:v", "1", "-c:v", "rawvideo",
                  "-fps_mode", "passthrough", "-f", "framemd5", "-"]
        fingerprints = []
        for command in (reference, serial):
            output = self.invoke(command).stdout.decode()
            self.assertRegex(output, r"(?m)^#tb 0: 1/30$")
            records = [[value.strip() for value in line.split(",")]
                       for line in output.splitlines() if line and not line.startswith("#")]
            self.assertEqual(len(records), 1209)
            self.assertEqual([int(row[2]) for row in records], list(range(1209)))
            fingerprints.append(records)
        self.assertEqual(fingerprints[0], fingerprints[1],
                         "lossless scene/fade round trips must preserve every monolithic picture sample")

    def test_all_serial_scene_and_fade_clips_are_lossless_and_have_exact_frame_counts(self):
        self.assertEqual(len(self.serial_commands), 15)
        scene_counts = [158, 165, 165, 165, 165, 165, 165, 166]
        fade_counts = [308, 458, 608, 758, 908, 1058, 1209]
        scenes, fades = [], []
        for command, probe in zip(self.serial_commands, self.serial_probes):
            inputs = command.count("-i")
            self.assertIn(inputs, (1, 2))
            target = scenes if inputs == 1 else fades
            expected_format = "yuv420p" if inputs == 1 else "yuv444p"
            self.assertEqual(probe["codec_name"], "ffv1")
            self.assertEqual(probe["pix_fmt"], expected_format)
            self.assertEqual((probe["width"], probe["height"], probe["avg_frame_rate"]),
                             (self.width, self.height, "30/1"))
            target.append(int(probe["nb_read_frames"]))
        self.assertEqual(scenes, scene_counts)
        self.assertEqual(fades, fade_counts)

    def test_serial_audio_remap_preserves_every_preencoder_pcm_sample(self):
        with mock.patch.multiple(sp, VW=self.width, VH=self.height):
            args = sp.render_args(self.stills, self.audio, self.music, self.captions,
                                  self.moment, 40.312, "null", self.root / "reference.mp4",
                                  edit_plan=EDITORIAL_PLAN, hook_video=self.hook)
        graph_index = args.index("-filter_complex") + 1
        parts = args[graph_index].split(";")
        audio = ";".join(part for part in parts if ":a]" in part or
                         part.startswith(("[m][key]", "[vo][duck]")))
        audio = audio.replace("[aout]", "[preencoder]") + ";[preencoder]asplit=2[aout][samplecheck]"
        reference = [*args[:graph_index], audio, "-map", "[aout]", "-c:a", "aac", "-b:a", "160k",
                     "-ar", "48000", "-t", "40.312", "-f", "null", "-",
                     "-map", "[samplecheck]", "-c:a", "pcm_s16le", "-f", "s16le", "-"]
        raw = self.invoke(reference).stdout
        with wave.open(str(self.pcm_output), "rb") as sound:
            actual = sound.readframes(sound.getnframes())
        self.assertEqual(len(raw), 1934976 * 2 * 2)
        self.assertEqual(raw, actual, "remapping final audio inputs must not change even one PCM sample")

    def test_serial_picture_preserves_effective_color_properties_and_sar(self):
        properties = []
        for picture in (None, self.picture):
            with mock.patch.multiple(sp, VW=self.width, VH=self.height):
                args = sp.render_args(self.stills, self.audio, self.music, self.captions,
                                      self.moment, 40.312, "null", self.root / "unused.mp4",
                                      edit_plan=EDITORIAL_PLAN, hook_video=self.hook, picture_video=picture,
                                      picture_range=self.picture_range if picture is not None else None)
            graph_index = args.index("-filter_complex") + 1
            parts = args[graph_index].split(";")
            finish = next(i for i, part in enumerate(parts) if part.startswith("[picture]"))
            graph = ";".join([*parts[:finish], "[picture]showinfo[inspection]"])
            output_cap = args.index("-threads:v")
            command = [*args[:graph_index], graph, "-map", "[inspection]", "-an",
                       *args[output_cap:output_cap + 2], "-frames:v", "1209", "-f", "null", "-"]
            command[command.index("-v") + 1] = "info"
            text = self.invoke(command).stderr.decode()
            geometry = re.findall(r"fmt:(\S+)(?: cl:(\S+))? sar:(\S+) s:(\S+)", text)
            color = re.findall(r"color_range:(\S+) color_space:(\S+) color_primaries:(\S+) color_trc:(\S+)", text)
            self.assertEqual(len(geometry), 1209)
            self.assertEqual(len(color), 1209)
            # Both taps are full-resolution 4:4:4: there is no subsampled chroma siting
            # to reinterpret. The lossless 4:2:0 scene round trips are pixel-checked above.
            self.assertTrue(all(frame[0] == "yuv444p" for frame in geometry))
            properties.append((geometry, color))
        mismatches = [(kind, index, left, right)
                      for kind, (before, after) in zip(("geometry", "color"), zip(properties[0], properties[1]))
                      for index, (left, right) in enumerate(zip(before, after)) if left != right]
        self.assertFalse(bool(mismatches), f"actual picture metadata differs: {mismatches[:3]!r}")


    def test_actual_opening_clip_has_91_lossless_frames_and_transparent_endpoint(self):
        probe = json.loads(self.invoke([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,nb_read_frames", "-of", "json", str(self.hook)
        ]).stdout)["streams"][0]
        self.assertEqual(probe["codec_name"], "ffv1")
        self.assertEqual(int(probe["nb_read_frames"]), 91)
        raw = self.invoke(["ffmpeg", "-v", "error", "-i", str(self.hook), "-map", "0:v:0",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]).stdout
        source = self.stills[0].read_bytes().split(b"\n", 3)[3]
        size = 216 * 384 * 3
        self.assertEqual(len(raw), 91 * size)
        self.assertEqual(raw[:size], source)
        self.assertEqual(raw[-size:], source)
        self.assertNotEqual(raw[15 * size:16 * size], raw[45 * size:46 * size])

    def test_actual_aac_frame_pts_are_sample_contiguous_including_old_gap_location(self):
        payload = json.loads(self.invoke([
            "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_frames", "-show_streams",
            "-show_entries", "stream=codec_name,sample_rate,time_base:frame=pts,nb_samples",
            "-of", "json", str(self.output)]).stdout)
        stream, frames = payload["streams"][0], payload["frames"]
        self.assertEqual((stream["codec_name"], stream["sample_rate"], stream["time_base"]),
                         ("aac", "48000", "1/48000"))
        self.assertGreater(len(frames), 1800)
        self.assertEqual(frames[0]["pts"], 0)
        for previous, current in zip(frames, frames[1:]):
            self.assertEqual(current["pts"] - previous["pts"], previous["nb_samples"],
                             f"AAC timestamp gap after sample {previous['pts']}")
        around_gap = [frame for frame in frames if 37.35 <= frame["pts"] / 48000 <= 37.5]
        self.assertGreaterEqual(len(around_gap), 6)
        self.assertLessEqual(abs(sum(frame["nb_samples"] for frame in frames) - 1934976), 1024)

    def test_actual_preencoder_sample_count_preserves_terminal_source_marker(self):
        import numpy as np
        with wave.open(str(self.pcm_output), "rb") as sound:
            self.assertEqual((sound.getframerate(), sound.getnchannels(), sound.getsampwidth()), (48000, 2, 2))
            self.assertEqual(sound.getnframes(), 1934976)
            data = np.frombuffer(sound.readframes(sound.getnframes()), "<i2").reshape((-1, 2)).mean(axis=1)
        def spectral_power(start, end, frequency):
            piece = data[round(start * 48000):round(end * 48000)]
            phase = np.arange(len(piece)) * 2 * np.pi * frequency / 48000
            return abs(np.dot(piece, np.exp(-1j * phase))) / len(piece)
        self.assertGreater(spectral_power(39.69, 39.79, 1100), 100,
                           "the terminal source marker must survive; silence padding is not preservation")
        self.assertGreater(spectral_power(39.69, 39.79, 1100),
                           spectral_power(39.69, 39.79, 220) * 10)
        self.assertGreater(spectral_power(39.3, 39.4, 220), spectral_power(39.3, 39.4, 1100) * 10)
        self.assertLess(float(np.max(np.abs(data[round(40.2 * 48000):]))), 2)

    def test_portrait_preparation_covers_adversarial_source_aspect_ratios(self):
        for width, height in [(16, 384), (384, 16), (64, 64)]:
            with self.subTest(size=(width, height)):
                source, target = self.root / f"{width}x{height}.ppm", self.root / f"{width}x{height}.png"
                synthetic_ppm(source, width, height)
                with mock.patch.multiple(sp, VW=108, VH=192):
                    sp.vertical_still(source, target)
                pixels = self.invoke([
                    "ffmpeg", "-v", "error", "-i", str(target), "-frames:v", "1",
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]).stdout
                self.assertEqual(len(pixels), self.frame_bytes)
                for index in (0, (self.width - 1) * 3, (self.height - 1) * self.width * 3,
                              self.frame_bytes - 3):
                    self.assertGreater(min(pixels[index:index + 3]), 0)

    def test_temporal_source_fingerprints_expose_premature_eof_or_duplicated_ending(self):
        output = self.root / "synthetic-clock.mp4"
        with mock.patch.multiple(sp, VW=self.width, VH=self.height):
            args = sp.render_args(self.stills, self.audio, self.music, self.captions,
                                  self.moment, 40.312, "null", output, edit_plan=EDITORIAL_PLAN,
                                  hook_video=self.hook)
        # Adapt only the eight source inputs. The unchanged production graph sees
        # a moving test clock, which exposes duplicated or prematurely ended frames.
        for index in reversed(range(1, 8)):
            end = args.index(str(self.stills[index])) + 1
            start = max(i for i in range(end) if args[i] == "-loop")
            duration = args[args.index("-t", start, end) + 1]
            args[start:end] = ["-f", "lavfi", "-i",
                               f"testsrc2=size={self.width}x{self.height}:rate=30:duration={duration}"]
        end = args.index(str(self.hook)) + 1
        args[end - 2:end] = ["-f", "lavfi", "-i",
                            f"testsrc2=size={self.width}x{self.height}:rate=30:duration={158 / 30}"]
        args[args.index("-preset") + 1] = "ultrafast"
        self.invoke(args)
        decoded = self.invoke([
            "ffmpeg", "-v", "error", "-i", str(output), "-map", "0:v:0",
            "-f", "framemd5", "-"]).stdout.decode()
        records = [line.split(",") for line in decoded.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(records), 1209)
        self.assertEqual([int(row[2]) for row in records], list(range(1209)))
        hashes = [row[-1].strip() for row in records]
        self.assertEqual(len(set(hashes[-60:])), 60)
        self.assertNotEqual(hashes[-2], hashes[-1])


WORKFLOW_STEP = "Select (whole video, Gemini), produce (own edit, STANDARD R8), watched review"
WORKFLOW_MARKER = "__PHASE2_ALLOWED_RUN_BODY__"


def workflow_body_and_frozen_bytes(source):
    """Mask only the three phase7 approved run scalars; preserve every other byte."""
    name = b"      - name: " + WORKFLOW_STEP.encode() + b"\n"
    if source.count(name) != 1:
        raise AssertionError("WORKFLOW_STEP_OCCURRENCE_COUNT")
    pattern = (rb"(" + re.escape(name)
               + rb"(?:        [^\n]*\n)*?        run: \|\n)"
               + rb"((?:          [^\n]*\n|\n)*)(?=      - name: Preserve privately and record\n)")
    matches = list(re.finditer(pattern, source))
    if len(matches) != 1:
        raise AssertionError("WORKFLOW_RUN_SCALAR_SHAPE")
    match = matches[0]
    frozen = source[:match.start(2)] + b"          " + WORKFLOW_MARKER.encode() + b"\n" + source[match.end(2):]
    body = "\n".join(line[10:] for line in match.group(2).decode().splitlines()) + "\n"
    preserve = re.compile(rb"(      - name: Preserve privately and record\n"
                          rb"(?:        [^\n]*\n)*?        run: \|\n)"
                          rb"((?:          [^\n]*\n|\n)*)(?=      - name:|\Z)")
    matches = list(preserve.finditer(frozen))
    if len(matches) != 1:
        raise AssertionError("PRESERVE_RUN_SCALAR_SHAPE")
    match = matches[0]
    frozen = frozen[:match.start(2)] + b"          __PHASE3_PRESERVE_RUN_BODY__\n" + frozen[match.end(2):]
    tools = re.compile(rb"(      - name: Tools, verified inputs \(narration, figure, music, images\)\n"
                       rb"(?:        [^\n]*\n)*?        run: \|\n)"
                       rb"((?:          [^\n]*\n|\n)*)(?=      - name:|\Z)")
    matches = list(tools.finditer(frozen))
    if len(matches) != 1:
        raise AssertionError("TOOLS_RUN_SCALAR_SHAPE")
    match = matches[0]
    frozen = frozen[:match.start(2)] + b"          __PHASE7_TOOLS_RUN_BODY__\n" + frozen[match.end(2):]
    return body, frozen


class FrozenEditorialWorkflow(unittest.TestCase):
    def source(self):
        return (HERE.parents[1] / ".github" / "workflows" / "shorts.yml").read_bytes()

    def test_every_unapproved_workflow_byte_including_comments_is_frozen(self):
        _, frozen = workflow_body_and_frozen_bytes(self.source())
        self.assertEqual(hashlib.sha256(frozen).hexdigest(),
                         "049daef8fa133c5426171e5ab9b041da44ba8c368e3577c9e72c176e3dd6ca3a")

    def test_card_baseloader_structural_hashes_or_stricter_stdlib_byte_assertion(self):
        source = self.source()
        # The byte assertion also runs in CI without installing an unpinned YAML dependency.
        _, frozen = workflow_body_and_frozen_bytes(source)
        self.assertEqual(hashlib.sha256(frozen).hexdigest(),
                         "049daef8fa133c5426171e5ab9b041da44ba8c368e3577c9e72c176e3dd6ca3a")
        try:
            import yaml
        except ImportError:
            return
        document = yaml.load(source, Loader=yaml.BaseLoader)
        digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        for key, expected in {
                "on": "9a7e3275489cb9fbc7dc49f85ec1f2d10bac7d3eb9fea495b9c9a545ae1d94af",
                "permissions": "794d512df45fe099199526cb758a415296f1b47a2a66c425328073fb8fbbac87",
                "concurrency": "546ad4646a5e40545552d4b66f34ef0fbda3b4e78a5736099cdb0bf71930e85a"}.items():
            self.assertEqual(digest(document[key]), expected, key)
        self.assertEqual(digest(document["on"]["workflow_dispatch"]["inputs"]),
                         "07f7be8257213dfb3c17630e4f2fe288f413ae5bc564baa25e872a9944503996")
        steps = [step for job in document["jobs"].values() for step in job["steps"]
                 if step.get("name") == WORKFLOW_STEP]
        self.assertEqual(len(steps), 1)
        steps[0]["run"] = WORKFLOW_MARKER
        preserves = [step for job in document["jobs"].values() for step in job["steps"]
                     if step.get("name") == "Preserve privately and record"]
        self.assertEqual(len(preserves), 1)
        preserves[0]["run"] = "__PHASE3_PRESERVE_RUN_BODY__"
        tools = [step for job in document["jobs"].values() for step in job["steps"]
                 if step.get("name") == "Tools, verified inputs (narration, figure, music, images)"]
        self.assertEqual(len(tools), 1)
        tools[0]["run"] = "__PHASE7_TOOLS_RUN_BODY__"
        self.assertEqual(digest(document), "e8422348255a897ae3db5567d396ea3c132e296e4963d4d05a71930294939f89")

    def run_synthetic_workflow(self, has_plan, failing=None):
        body, _ = workflow_body_and_frozen_bytes(self.source())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = root / "runner"
            python = runner / "cine" / "bin" / "python"
            python.parent.mkdir(parents=True)
            log = root / "calls.jsonl"
            python.write_text("#!/usr/bin/env python3\n"
                              "import json, os, sys\n"
                              "with open(os.environ['SYNTHETIC_CALLS'], 'a') as output:\n"
                              "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                              "sys.exit(17 if os.environ.get('SYNTHETIC_FAIL') in sys.argv[1:] else 0)\n")
            python.chmod(0o755)
            source = root / "migration" / "production" / "synthetic-case" / "shorts"
            source.mkdir(parents=True)
            if has_plan:
                (source / "edit-plan.json").write_text(json.dumps(EDITORIAL_PLAN))
            env = dict(os.environ, RUNNER_TEMP=str(runner), PILOT="synthetic-case",
                       SYNTHETIC_CALLS=str(log), SYNTHETIC_FAIL=failing or "")
            result = subprocess.run(["bash", "-e", "-c", body], cwd=root, env=env,
                                    capture_output=True, timeout=15)
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            normalized = [[value.replace(str(runner), "$T") for value in call] for call in calls]
            return result.returncode, normalized

    def test_editorial_workflow_order_is_prepare_produce_measure_review_finalize(self):
        code, calls = self.run_synthetic_workflow(True)
        self.assertEqual(code, 0)
        self.assertEqual([call[2] for call in calls], [
            "migration/production/shorts_edit_plan.py",
            "migration/production/shorts_produce.py",
            "migration/production/shorts_edit_plan.py",
            "migration/production/shorts_review.py",
            "migration/production/shorts_edit_plan.py"])
        self.assertEqual(calls[0][3:], [
            "migration/production/synthetic-case/shorts/edit-plan.json", "$T/work/timeline.json",
            "migration/production/synthetic-case/script.json",
            "migration/production/synthetic-case/shorts/inputs.json", "$T/work/shorts/selection.json"])
        self.assertEqual(calls[2][3:], [
            "--check-media", "$T/work", "migration/production/synthetic-case/shorts/edit-plan.json",
            "$T/work/shorts/shorts.json", "$T/voice.flac", "$T/in/music.flac", "$T/in/img",
            "migration/evidence/shorts-v2/phase2-review-history.json"])
        self.assertEqual(calls[3][3:], ["$T/work/shorts", "1"])
        self.assertEqual(calls[4][3:], ["--finalize", "$T/work/shorts/shorts.json", "$T/work/shorts/short-00.mp4"])

    def test_absent_plan_preserves_the_three_exact_legacy_commands(self):
        code, calls = self.run_synthetic_workflow(False)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [
            ["-I", "-B", "migration/production/shorts_select.py", "$T/work/timeline.json",
             "migration/production/synthetic-case/script.json", "$T/work/shorts/selection.json", "3"],
            ["-I", "-B", "migration/production/shorts_produce.py", "$T/work",
             "$T/work/shorts/selection.json", "migration/production/synthetic-case/script.json",
             "$T/in/img", "$T/in/figure.png", "$T/in/music.flac", "$T/work/shorts"],
            ["-I", "-B", "migration/production/shorts_review.py", "$T/work/shorts", "1"]])

    def test_failed_media_measurement_cannot_reach_review_or_finalize(self):
        code, calls = self.run_synthetic_workflow(True, "--check-media")
        self.assertEqual(code, 17)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1][3], "--check-media")
        self.assertFalse(any("migration/production/shorts_review.py" in call for call in calls))

    def test_historical_fail_guard_uses_the_fixed_archive_and_stops_before_review(self):
        history = "migration/evidence/shorts-v2/phase2-review-history.json"
        code, calls = self.run_synthetic_workflow(True, history)
        self.assertEqual(code, 17)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1][3], "--check-media")
        self.assertEqual(calls[-1][-1], history)
        self.assertEqual(sum(history in call for call in calls), 1)
        self.assertFalse(any("migration/production/shorts_review.py" in call for call in calls))
        self.assertFalse(any("--finalize" in call for call in calls))


class MaterialRenderer(unittest.TestCase):
    def plan(self):
        import shorts_006_material as adapter
        return json.loads(json.dumps(adapter.EXPECTED_PLAN))

    def test_closed_native_route_and_no_second_camera(self):
        p = self.plan()
        self.assertEqual(sp._editorial_adapter(p).__name__, 'shorts_006_material')
        for version,pilot in [('shorts-006-correction-plan-v2','pilot-005'),
                               ('shorts-editorial-plan-v2','pilot-006')]:
            with self.assertRaises(ValueError):sp._editorial_adapter(dict(p,version=version,source_pilot=pilot))
        args=sp.scene_clip_args(['a','b'],{},p,0,'out',hook_video=['native-a','native-b'])
        graph=args[args.index('-filter_complex')+1]
        self.assertIn('trim=end_frame=637',graph)
        for forbidden in ['scale=','zoompan','tpad','crop=']:self.assertNotIn(forbidden,graph)
        self.assertEqual(sp.scene_frame_plan(p)['scene_spans'],[[0,637],[622,1260]])
        with self.assertRaisesRegex(ValueError,'MATERIAL_AUDIO_REMUX_REQUIRED'):
            sp.render_args(['a','b'],'voice','music','sub',{},42,'null','out',edit_plan=p)

    def test_native_grade_order_retains_exact_historical_eq(self):
        with mock.patch.object(sp,'run') as run:
            sp.native_still('native.png','graded.png')
        cmd=run.call_args.args[0]
        self.assertEqual(cmd[cmd.index('-vf')+1],'eq=brightness=-0.05:saturation=1.05')
        self.assertNotIn('scale',str(cmd));self.assertNotIn('crop',str(cmd))
        source=inspect.getsource(sp.produce)
        self.assertLess(source.index('(native_still if material'),source.index('cinematic.grade(p)'))
        self.assertLess(source.index('cinematic.grade(p)'),source.index('write_native_video(path'))

    def test_video_encode_and_copy_only_audio_command(self):
        cmd=sp.material_video_args('picture','tv','caption.ass','LOOK','video.mp4',1260)
        self.assertEqual(cmd[cmd.index('-crf')+1],'19')
        self.assertEqual(cmd[cmd.index('-preset')+1],'medium')
        self.assertEqual(cmd[cmd.index('-frames:v')+1],'1260')
        self.assertIn('-an',cmd);self.assertNotIn('-c:a',cmd)
        self.assertEqual(cmd[cmd.index('-filter_complex')+1].count('ass=caption.ass'),1)
        mux=sp.material_remux_args('video','reference','output')
        self.assertEqual([mux[i+1] for i,x in enumerate(mux) if x=='-map'],['0:v:0','1:a:0'])
        self.assertEqual(mux[mux.index('-c')+1],'copy')
        for option in ['-t','-shortest','-af','-ar','-ss','-reset_timestamps']:self.assertNotIn(option,mux)

    def test_produce_native_then_verified_remux_before_output_hash(self):
        from contextlib import ExitStack
        import shorts_006_material as adapter
        import cinematic
        from test_shorts_006_plan import sources
        plan=self.plan();docs=sources();timeline,script=docs['timeline'],docs['script']
        refs={item['id']:item.get('reference') for item in script['segments']}
        moment,reason=sp.validate_candidate(timeline['sentences'],refs,plan['candidate'])
        self.assertIsNone(reason)
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory);work=root/'work';work.mkdir();images=root/'images';images.mkdir();out=root/'out';out.mkdir()
            voice=root/'voice.flac';music=root/'music.flac';reference=work/'reference-audio.mp4'
            for path in (voice,music,reference):path.touch()
            hashes={voice:plan['voice']['sha256'],music:plan['music']['sha256']}
            for scene in plan['scenes']:
                image=images/(scene['image_id']+'.png');image.touch();hashes[image]=scene['sha256']
                meta=images/(scene['image_id']+'.json');hashes[meta]=scene['metadata_sha256']
                meta.write_text(json.dumps({'id':scene['image_id'],'release_asset':scene['asset'],
                    'sha256':scene['sha256'],'models':{'test':{'license':'synthetic'}}}))
            events=[]
            def hashed(path):
                if Path(path)==out/'short-00.mp4':events.append('output-hash');return 'f'*64
                return hashes[Path(path)]
            def patch(obj,name,**kwargs):return stack.enter_context(mock.patch.object(obj,name,**kwargs))
            patch(sp,'sha256',side_effect=hashed)
            preflight=patch(adapter,'preflight');patch(adapter,'source_durations')
            patch(adapter,'verify_audio_reference',side_effect=lambda *a:events.append('verify-reference'))
            patch(adapter,'verify_audio_remux',side_effect=lambda *a:events.append('verify-remux'))
            patch(sp.subprocess,'run',return_value=SimpleNamespace(stdout='{"streams":[{"width":2048,"height":2048}]}'))
            native=patch(sp,'native_still');oldstill=patch(sp,'vertical_still');patch(cinematic,'grade')
            oldmotion=patch(sp,'write_continuous_video')
            nativevideo=patch(sp,'write_native_video',side_effect=lambda path,out,index:out)
            patch(sp,'reference_picture_range',return_value='tv');patch(sp,'write_editorial_picture',return_value=root/'picture.mkv')
            patch(sp,'probe_duration',return_value=42)
            commands=[]
            patch(sp,'run',side_effect=lambda command:(commands.append(command),events.append('remux' if '-c' in command else 'encode')))
            record=sp.produce(work,moment,0,script,images,'unused',music,out,
                timeline_sentences=timeline['sentences'],script_refs=refs,edit_plan=plan,audio_reference=reference)
            self.assertEqual(events,['verify-reference','encode','verify-reference','remux','verify-remux','output-hash'])
            self.assertEqual(len(commands),2);self.assertNotIn(str(voice),str(commands));self.assertNotIn(str(music),str(commands))
            self.assertEqual(native.call_count,2);self.assertEqual(nativevideo.call_count,2)
            oldstill.assert_not_called();oldmotion.assert_not_called()
            self.assertEqual(preflight.call_args.args[1:],sp._correction_paths(adapter.CANONICAL_PILOT,plan))
            self.assertEqual(record['source_image_info'][plan['scenes'][0]['image_id']]['width'],2048)
            self.assertFalse(record['publish'])
            # A broken remux proof must abort before the output obtains a record/hash.
            events.clear()
            patch(adapter,'verify_audio_remux',side_effect=ValueError('AUDIO_REMUX_MISMATCH'))
            with self.assertRaisesRegex(ValueError,'AUDIO_REMUX_MISMATCH'):
                sp.produce(work,moment,0,script,images,'unused',music,out,
                    timeline_sentences=timeline['sentences'],script_refs=refs,edit_plan=plan,audio_reference=reference)
            self.assertNotIn('output-hash',events)

    def test_main_supplies_reference_only_after_canonical_preflight(self):
        import shorts_006_material as adapter
        from test_shorts_006_plan import sources
        docs=sources();plan=self.plan();script=docs['script'];timeline=docs['timeline']
        chosen=[dict(plan['candidate'])]
        prepared={'selection_mode':'EDITORIAL_PLAN','chosen':chosen,'edit_plan':plan}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir();(root/'shorts').mkdir()
            (root/'script.json').write_text(json.dumps(script));(work/'timeline.json').write_text(json.dumps(timeline))
            (root/'shorts/inputs.json').write_text('{}');(root/'selection.json').write_text(json.dumps(prepared))
            record={'file':'short-00.mp4','seconds':42,'hook':'Let your face soften.'}
            with mock.patch.object(adapter,'preflight') as preflight, \
                 mock.patch.object(adapter,'validate_plan',return_value=prepared), \
                 mock.patch.object(sp,'snap_all',return_value=(chosen,[])), \
                 mock.patch.object(sp,'produce',return_value=record) as produce:
                sp.main(work,root/'selection.json',root/'script.json',root/'images','figure','music',root/'out')
                self.assertEqual(produce.call_args.kwargs['audio_reference'],work/'reference-audio.mp4')
                preflight.assert_called_once_with(root,*sp._correction_paths(root,plan))
                for failure in ['PASS','FAIL','NOT_REVIEWED','malformed']:
                    produce.reset_mock();preflight.side_effect=ValueError('CANONICAL_'+failure)
                    with self.assertRaises(ValueError):
                        sp.main(work,root/'selection.json',root/'script.json',root/'images','figure','music',root/'out')
                    produce.assert_not_called()

    def test_native_writer_allocates_exact_count_and_output_geometry(self):
        import shorts_006_motion as motion
        for index,count in [(0,637),(1,638)]:
            with mock.patch.object(sp,'_write_atmosphere_video',return_value='out') as writer, \
                 mock.patch.object(motion,'source_frame',return_value='frame') as frame:
                self.assertEqual(sp.write_native_video('native','out',index),'out')
                call=writer.call_args
                self.assertEqual(call.args[:3],('native','out',count))
                self.assertEqual(call.kwargs,{'continuous':True,'output_size':(1080,1920)})
                self.assertEqual(call.args[3]('source',count-1),('frame',None))
                frame.assert_called_once_with('source',index,count-1,count)

    def test_v2_canonical_paths_are_separate(self):
        p=self.plan();root=Path('/synthetic')
        self.assertEqual(sp._correction_paths(root,p),(root/'shorts/correction-plan-v2.json',root/'shorts/correction-history-96c8268f.json'))
        self.assertEqual(sp._correction_paths(root,{}),(root/'shorts/correction-plan.json',root/'shorts/correction-history.json'))


def correction_source():
    import shorts_006_plan as adapter
    plan = json.loads(json.dumps(adapter.EXPECTED_PLAN))
    from test_shorts_006_plan import sources
    docs = sources()
    timeline, script = docs['timeline'], docs['script']
    refs = {s['id']: s.get('reference') for s in script['segments']}
    moment, reason = sp.validate_candidate(timeline['sentences'], refs, plan['candidate'])
    assert reason is None, reason
    return plan, timeline, script, refs, moment


class CorrectionRenderer(unittest.TestCase):
    def setUp(self):
        from test_shorts_006_plan import synthetic_environment
        root = self.enterContext(tempfile.TemporaryDirectory())
        self.fixture = self.enterContext(synthetic_environment(root))
        pilot = self.fixture['pilot']
        # This test begins before the one permitted persisted correction.
        (pilot / 'shorts/shorts.json').write_bytes((pilot / 'shorts/correction-history.json').read_bytes())

    def test_closed_routing_at_every_entry_and_mixed_pairs(self):
        plan, timeline, script, refs, moment = correction_source()
        self.assertEqual(sp._editorial_adapter(plan).__name__, 'shorts_006_plan')
        self.assertEqual(sp._editorial_adapter(EDITORIAL_PLAN).__name__, 'shorts_edit_plan')
        calls = [lambda p: sp.scene_frame_plan(p),
                 lambda p: sp.editorial_picture(['a', 'b'], moment, p, hook_video=['c', 'd']),
                 lambda p: sp.scene_clip_args(['a', 'b'], moment, p, 0, 'x', hook_video=['c', 'd']),
                 lambda p: sp.render_args(['a', 'b'], 'v', 'm', 'a', moment, 42, 'null', 'x', edit_plan=p,
                                          picture_video='p', picture_range='tv'),
                 lambda p: sp.produce(Path('/unused'), moment, 0, script, Path('/unused'), 'f', 'm', Path('/unused'),
                                     timeline_sentences=timeline['sentences'], script_refs=refs, edit_plan=p)]
        for version, pilot in [('shorts-editorial-plan-v2','pilot-006'),
                               ('shorts-006-correction-plan-v1','pilot-005'),
                               ('unknown','pilot-006'), ('shorts-006-correction-plan-v1','unknown')]:
            bad = dict(plan, version=version, source_pilot=pilot)
            for call in calls:
                with self.subTest(pair=(version,pilot),call=call), mock.patch.object(sp,'run') as render:
                    with self.assertRaisesRegex(ValueError,'EDITORIAL_PLAN_DISCRIMINATOR'): call(bad)
                    render.assert_not_called()
        self.assertNotIn('from shorts_edit_plan import', inspect.getsource(sp))

    def test_exact_allocation_full_inputs_and_separate_audio_clock(self):
        plan, timeline, script, refs, moment = correction_source()
        frames = sp.scene_frame_plan(plan)
        self.assertEqual(frames['scene_spans'], [[0,637],[622,1260]])
        self.assertEqual(frames['scene_frames'], [637,638])
        self.assertEqual(frames['fade_frames'],15)
        args=sp.render_args(['a','b'],'voice.flac','music.flac','caption.ass',moment,42,'null','out.mp4',
                            edit_plan=plan,hook_video=['full-a.mkv','full-b.mkv'])
        graph=args[args.index('-filter_complex')+1]
        self.assertNotIn('tpad', graph); self.assertNotIn('-loop', args)
        self.assertEqual([args[i+1] for i,x in enumerate(args) if x=='-i'],
                         ['full-a.mkv','full-b.mkv','voice.flac','music.flac'])
        self.assertIn('40.690',args);self.assertIn('2013.728',args)
        self.assertIn('apad=whole_len=2016000',graph)
        self.assertIn('atrim=end_sample=2016000',graph)
        self.assertIn('afade=t=out:st=40.690:d=1.31:curve=hsin',graph)
        self.assertNotIn('d=0.04',graph)
        self.assertEqual(args[args.index('-preset')+1],'medium')
        self.assertEqual(args[args.index('-crf')+1],'19')
        self.assertEqual(args[args.index('-b:a')+1],'160k')
        captions=sp.caption_events(moment)
        self.assertAlmostEqual(captions[0][1],1.941)
        self.assertAlmostEqual(max(x[1] for x in captions),40.689)
        for bad in (None,'hook.mkv',['one'],['one','two','three']):
            with self.assertRaises(ValueError):
                sp.editorial_picture(['a','b'],moment,plan,hook_video=bad)
        with self.assertRaisesRegex(ValueError,'CORRECTION_RENDER_CLOCK_MISMATCH'):
            sp.render_args(['a','b'],'v','m','a',moment,35.19,'null','x',edit_plan=plan,hook_video=['a','b'])

    def test_source_duration_failures_precede_any_render(self):
        import shorts_006_plan as adapter
        plan, timeline, script, refs, moment = correction_source()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); work=root/'work';images=root/'images';images.mkdir();work.mkdir()
            music=root/'music.flac';music.touch();(root/'voice.flac').touch()
            hashes={root/'voice.flac':plan['voice']['sha256'],music:plan['music']['sha256']}
            for scene in plan['scenes']:
                image=images/(scene['image_id']+'.png'); image.touch(); hashes[image]=scene['sha256']
                (images/(scene['image_id']+'.json')).write_text(json.dumps({
                    'id':scene['image_id'],'release_asset':scene['asset'],'sha256':scene['sha256'],
                    'models':{'test':{'license':'synthetic'}}}))
            for durations, expected in [([854.417,10800],'VOICE_SOURCE_TRUNCATED'),
                                        ([1529.993333,2055.727],'MUSIC_SOURCE_TRUNCATED'),
                                        ([float('nan'),10800],'VOICE_SOURCE_TRUNCATED')]:
                with mock.patch.object(sp,'sha256',side_effect=lambda p:hashes[Path(p)]), \
                     mock.patch.object(adapter,'_probe',side_effect=[
                         {'streams':[{'codec_type':'audio','sample_rate':'24000','channels':1}],
                          'format':{'duration':str(durations[0])}},
                         {'streams':[{'codec_type':'audio'}],'format':{'duration':str(durations[1])}}]), \
                     mock.patch.object(sp,'run') as run, mock.patch.object(sp.subprocess,'run') as probe:
                    with self.assertRaisesRegex(ValueError,expected):
                        sp.produce(work,moment,0,script,images,'unused',music,root/'out',
                                   timeline_sentences=timeline['sentences'],script_refs=refs,edit_plan=plan)
                    run.assert_not_called();probe.assert_not_called()

    def test_produce_uses_two_complete_clips_and_one_encoder(self):
        import shorts_006_plan as adapter
        import cinematic
        plan,timeline,script,refs,moment=correction_source()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);work=root/'work';work.mkdir();images=root/'images';images.mkdir();out=root/'out';out.mkdir()
            voice=root/'voice.flac';voice.touch();music=root/'music.flac';music.touch()
            hashes={voice:plan['voice']['sha256'],music:plan['music']['sha256'],out/'short-00.mp4':'f'*64}
            for scene in plan['scenes']:
                image=images/(scene['image_id']+'.png');image.touch();hashes[image]=scene['sha256']
                (images/(scene['image_id']+'.json')).write_text(json.dumps({
                    'id':scene['image_id'],'release_asset':scene['asset'],'sha256':scene['sha256'],
                    'models':{'test':{'license':'synthetic'}}}))
            with mock.patch.object(sp,'sha256',side_effect=lambda p:hashes[Path(p)]), \
                 mock.patch.object(adapter,'source_durations') as durations, \
                 mock.patch.object(sp.subprocess,'run',return_value=SimpleNamespace(stdout='{"streams":[{"width":1080,"height":1920}]}')), \
                 mock.patch.object(sp,'vertical_still'), mock.patch.object(cinematic,'grade'), \
                 mock.patch.object(cinematic,'look',return_value='null'), \
                 mock.patch.object(sp,'write_opening_video') as old, \
                 mock.patch.object(sp,'write_continuous_video',side_effect=lambda p,out,n,seed,**kw:out) as animated, \
                 mock.patch.object(sp,'reference_picture_range',return_value='tv'), \
                 mock.patch.object(sp,'write_editorial_picture',return_value=root/'picture.mkv') as staging, \
                 mock.patch.object(sp,'probe_duration',return_value=42), mock.patch.object(sp,'run') as encode:
                record=sp.produce(work,moment,0,script,images,'unused',music,out,
                                  timeline_sentences=timeline['sentences'],script_refs=refs,edit_plan=plan)
                durations.assert_called_once_with(voice,music,plan)
                old.assert_not_called();self.assertEqual(animated.call_count,2)
                self.assertEqual([(c.args[2],c.args[3]) for c in animated.call_args_list],[(637,259006),(638,259007)])
                self.assertEqual([c.kwargs for c in animated.call_args_list],
                                 [{'opening_profile':'source_atmosphere_hook_v1'}, {'opening_profile':None}])
                self.assertEqual(len(staging.call_args.kwargs['hook_video']),2)
                encode.assert_called_once();self.assertIn(str(voice),encode.call_args.args[0])
                self.assertIsNone(record['reference'])
                self.assertEqual(record['source_end'],854.417);self.assertEqual(record['seconds'],42)
                self.assertFalse(record['publish']);self.assertEqual(record['render_plan'],adapter.frame_plan(plan))
            image=images/(plan['scenes'][0]['image_id']+'.png');image.unlink();image.symlink_to(voice)
            with mock.patch.object(sp,'run') as encode:
                with self.assertRaisesRegex(ValueError,'UNSAFE_PATH'):
                    sp.produce(work,moment,0,script,images,'unused',music,out,
                               timeline_sentences=timeline['sentences'],script_refs=refs,edit_plan=plan)
                encode.assert_not_called()


    def test_changed_canonical_prepared_selection_cannot_invoke_produce(self):
        import shorts_006_plan as adapter
        plan,timeline,script,refs,moment=correction_source()
        pilot=self.fixture['pilot']
        prepared=adapter.validate_plan(plan,timeline,script,self.fixture['docs']['inputs'],
                                      raw_sha256={k:plan['source_sha256'][k] for k in ('timeline','script','inputs')})
        original_hash=adapter.hash_file
        canonical=pilot/'shorts/shorts.json'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);selection=root/'selection.json';selection.write_text(json.dumps(prepared))
            for data in [json.dumps({'shorts':[{'review':{'status':status}}]}).encode()
                         for status in ('PASS','FAIL','NOT_REVIEWED_ProviderFailure')]+[b'{malformed']:
                digest=hashlib.sha256(data).hexdigest()
                with mock.patch.object(adapter,'hash_file',side_effect=lambda p:
                                       digest if Path(p)==canonical else original_hash(p)), \
                     mock.patch.object(sp,'produce') as make, mock.patch.object(sp,'run') as render:
                    with self.assertRaisesRegex(ValueError,'CANONICAL_ATTEMPT_ALREADY_CHANGED'):
                        sp.main(pilot/'out',selection,pilot/'script.json',root,'unused','music',root/'output')
                    make.assert_not_called();render.assert_not_called()
            selection.write_text(json.dumps({'chosen':[moment]}))
            with mock.patch.object(sp,'produce') as make:
                with self.assertRaisesRegex(ValueError,'CORRECTION_PLAN_MISSING'):
                    sp.main(pilot/'out',selection,pilot/'script.json',root,'unused','music',root/'output')
                make.assert_not_called()


    def test_main_uses_006_adapter_reconstructs_one_and_rejects_mixed_pair(self):
        import shorts_006_plan as adapter
        plan,timeline,script,refs,moment=correction_source()
        pilot=self.fixture['pilot']
        prepared=adapter.validate_plan(plan,timeline,script,self.fixture['docs']['inputs'],
                                      raw_sha256={k:plan['source_sha256'][k] for k in ('timeline','script','inputs')})
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);selection=root/'selection.json';selection.write_text(json.dumps(prepared))
            with mock.patch.object(sp,'produce',return_value={'file':'short-00.mp4','seconds':42,'hook':moment['hook']}) as make:
                sp.main(pilot/'out',selection,pilot/'script.json',root,'unused','music',root/'output')
                make.assert_called_once();self.assertEqual(make.call_args.kwargs['edit_plan'],plan)
                self.assertEqual(make.call_args.args[1]['sentences'],moment['sentences'])
            prepared['edit_plan']['source_pilot']='pilot-005';selection.write_text(json.dumps(prepared))
            with mock.patch.object(sp,'produce') as make:
                with self.assertRaisesRegex(ValueError,'EDITORIAL_PLAN_DISCRIMINATOR'):
                    sp.main(pilot/'out',selection,pilot/'script.json',root,'unused','music',root/'output')
                make.assert_not_called()


# Frozen numerical oracle from baseline 582ff607089f9accb91a8a4d1a8c2fe6f4e47408.
# Original three-function source SHA256: 5656c706eda6745afc8afc1b3935ea1f3981be30a3d3cfd54577cd3d71e769ca.
# Independent of production helpers; run with the same NumPy/OpenCV build.
def frozen_005_opening_envelope(frame_index):
    """Zero outside the approved three-second hook; smooth entry and exit."""
    if type(frame_index) is not int:
        raise ValueError("INVALID_HOOK_FRAME")
    t = frame_index / 30
    if not 0 <= t < 3:
        return 0.0
    def smooth(u):
        u = min(1.0, max(0.0, u))
        return u * u * (3 - 2 * u)
    return smooth(t / 0.35) * smooth((3 - t) / 0.45)


def frozen_005_opening_particles(frame_index, width, height, seed=231005):
    """Deterministic dust paths in source coordinates, never in the caption zone."""
    if any(type(x) is not int for x in (width, height, seed)) or min(width, height) <= 0:
        raise ValueError("INVALID_HOOK_GEOMETRY")
    envelope = frozen_005_opening_envelope(frame_index)
    t, rng = frame_index / 30, random.Random(seed)
    particles = []
    for _ in range(24):
        x, y = rng.uniform(50, 1030), rng.uniform(100, 900)
        radius, vx, vy = rng.uniform(1, 2.5), rng.uniform(6, 12), rng.uniform(-18, -10)
        particles.append({"x": (x + vx * t) * width / 1080,
                          "y": (y + vy * t) * height / 1920,
                          "radius": radius * width / 1080, "alpha": 0.10 * envelope})
    return particles


def frozen_005_opening_atmosphere(base_rgb, frame_index, seed=231005):
    """Source-bound fog, warm highlights and dust; no camera, grain or generated asset.

    RGB and diagnostic alpha are floats in [0,1]. Input uint8 is also accepted;
    the caller's source is never mutated. The helper is deterministic and local.
    """
    import cv2
    import numpy as np
    base = np.asarray(base_rgb)
    if base.ndim != 3 or base.shape[2] != 3 or min(base.shape[:2]) <= 0:
        raise ValueError("INVALID_HOOK_IMAGE")
    base = base.astype(np.float32) / (255 if base.dtype == np.uint8 else 1)
    if not np.isfinite(base).all() or np.any(base < 0) or np.any(base > 1):
        raise ValueError("INVALID_HOOK_IMAGE")
    envelope = frozen_005_opening_envelope(frame_index)
    h, w = base.shape[:2]
    particles = frozen_005_opening_particles(frame_index, w, h, seed)
    if not envelope:
        return base.copy(), np.zeros((h, w), dtype=np.float32)
    t = frame_index / 30
    y, x = np.mgrid[:h, :w].astype(np.float32)
    fog = (np.exp(-((y / h - 0.72) / 0.22) ** 2) *
           (0.50 + 0.25 * np.sin(2 * np.pi * (x / w - 0.035 * t)) +
            0.25 * np.sin(2 * np.pi * (1.7 * x / w + 0.7 * y / h - 0.05 * t))))
    fog_alpha = 0.09 * envelope * fog
    luma = base @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    highlights = cv2.GaussianBlur(np.clip((luma - 0.65) / 0.35, 0, 1),
                                  (0, 0), sigmaX=0.025 * w)
    light_alpha = 0.06 * envelope * highlights
    dust_alpha = np.zeros((h, w), dtype=np.float32)
    subsamples = (np.arange(8, dtype=np.float32) + 0.5) / 8 - 0.5
    for p in particles:
        # A compact C1 disk has the declared physical radius. Subpixel area
        # integration avoids blinking when the dust is smaller than one pixel.
        radius = p["radius"]
        x0, x1 = max(0, math.floor(p["x"] - radius - 0.5)), min(w, math.ceil(p["x"] + radius + 0.5))
        y0, y1 = max(0, math.floor(p["y"] - radius - 0.5)), min(h, math.ceil(p["y"] + radius + 0.5))
        if x0 < x1 and y0 < y1:
            dx2 = (np.arange(x0, x1)[:, None] + subsamples - p["x"]) ** 2
            dy2 = (np.arange(y0, y1)[:, None] + subsamples - p["y"]) ** 2
            disk = np.maximum(0, 1 - (dy2[:, :, None, None] + dx2[None, None, :, :]) / radius ** 2) ** 2
            dust_alpha[y0:y1, x0:x1] += p["alpha"] * disk.mean(axis=(1, 3))
    dust_alpha = np.minimum(dust_alpha, 0.10 * envelope)
    total = fog_alpha + light_alpha + dust_alpha
    factor = np.minimum(1, 0.18 / np.maximum(total, 1e-20))
    alpha = total * factor
    light = (fog_alpha[..., None] * np.array([0.92, 0.94, 1.0], np.float32) +
             light_alpha[..., None] * np.array([1.0, 0.92, 0.75], np.float32) +
             dust_alpha[..., None] * np.array([1.0, 0.96, 0.84], np.float32)) * factor[..., None]
    composed = base * (1 - alpha[..., None]) + light
    return np.clip(composed, 0, 1).astype(np.float32), alpha.astype(np.float32)



class CorrectionAtmosphere(unittest.TestCase):
    def test_existing_005_matches_frozen_oracle_in_the_same_opencv(self):
        import numpy as np
        base=np.arange(54*96*3,dtype=np.uint8).reshape(96,54,3)
        # Exact float equality against pre-refactor code in this runtime avoids
        # treating numerical OpenCV build differences as producer regressions.
        # Every original opening frame is covered, not only six digest probes.
        for frame in range(91):
            expected, expected_alpha = frozen_005_opening_atmosphere(base,frame)
            image,alpha=sp.opening_atmosphere(base,frame)
            np.testing.assert_array_equal(image,expected)
            np.testing.assert_array_equal(alpha,expected_alpha)

    def test_continuous_deterministic_nonmutating_bounded_and_late_motion(self):
        import numpy as np
        base=np.full((192,108,3),.2,np.float32);original=base.copy()
        for count,seed in [(548,259006),(547,259007)]:
            for frame in (0,91,270,count-2,count-1):
                a,alpha=sp.continuous_atmosphere(base,frame,count,seed)
                b,beta=sp.continuous_atmosphere(base,frame,count,seed)
                np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(alpha,beta)
                self.assertTrue(np.isfinite(a).all());self.assertGreaterEqual(float(a.min()),0)
                self.assertLessEqual(float(a.max()),1);self.assertLessEqual(float(alpha.max()),.180001)
                if frame<count-1:
                    c,_=sp.continuous_atmosphere(base,frame+1,count,seed)
                    self.assertGreater(float(np.abs(c-a).sum()),0)
            for frame in (-1,count,count+10):
                a,alpha=sp.continuous_atmosphere(base,frame,count,seed)
                np.testing.assert_array_equal(a,base);self.assertEqual(float(alpha.sum()),0)
        np.testing.assert_array_equal(base,original)
        for image in (np.zeros((0,1,3)), np.zeros((3,3)), np.full((2,2,3),np.nan)):
            with self.assertRaises(ValueError):sp.continuous_atmosphere(image,1,548,259006)
        for frame,count,seed in [(True,548,259006),(1,0,259006),(1,548,False)]:
            with self.assertRaises(ValueError):sp.continuous_atmosphere(base,frame,count,seed)


    def test_none_profile_matches_frozen_continuous_oracle(self):
        import numpy as np
        base=np.arange(54*96*3,dtype=np.uint8).reshape(96,54,3)
        # Only the independent frozen envelope is replaced with the already
        # approved continuous envelope; all original pixel arithmetic stays frozen.
        with mock.patch(__name__+'.frozen_005_opening_envelope',return_value=1.0):
            for seed in (259006,259007):
                for frame in (0,10,45,89,90,91,300,636):
                    expected,expected_alpha=frozen_005_opening_atmosphere(base,frame,seed)
                    for kwargs in ({},{'opening_profile':None}):
                        image,alpha=sp.continuous_atmosphere(base,frame,638,seed,**kwargs)
                        np.testing.assert_array_equal(image,expected)
                        np.testing.assert_array_equal(alpha,expected_alpha)

    def test_closed_hook_fields_and_continuity(self):
        import numpy as np
        y,x=np.mgrid[:192,:108].astype(np.float32);x/=108;y/=192
        def smooth(u):
            u=np.clip(u,0,1)
            return u*u*(3-2*u)
        for t in (-1,0,.35,1,1.941,2.25,89/30,3,91/30,4,20):
            phase,light=sp._opening_atmosphere_fields(t,x,y)
            p=smooth(t/3)
            self.assertEqual(phase,t+4*p)
            h=smooth(t/.35)*smooth((3-t)/.75) if 0<=t<3 else 0
            expected=.85*h*np.exp(-((x-(.32+.36*p))/.22)**2-((y-.30)/.20)**2)*(1-smooth((y-.48)/.06))
            np.testing.assert_array_equal(light,expected.astype(np.float32))
            self.assertTrue(np.all(light[y>=.54]==0))
            if t<=0 or t>=3:self.assertTrue(np.all(light==0))
        eps=1e-5
        for t in (0,3):
            left=sp._opening_atmosphere_fields(t-eps,x,y)[0]
            middle=sp._opening_atmosphere_fields(t,x,y)[0]
            right=sp._opening_atmosphere_fields(t+eps,x,y)[0]
            self.assertAlmostEqual((middle-left)/eps,1,places=4)
            self.assertAlmostEqual((right-middle)/eps,1,places=4)

    def test_hook_pixels_bounds_endpoint_and_source_immutability(self):
        import numpy as np
        base=np.full((192,108,3),.2,np.float32);original=base.copy()
        profile='source_atmosphere_hook_v1'
        outputs={}
        for frame in (0,10,30,58,68,89,90,91,120,636):
            a,alpha=sp.continuous_atmosphere(base,frame,637,259006,opening_profile=profile)
            b,beta=sp.continuous_atmosphere(base,frame,637,259006,opening_profile=profile)
            np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(alpha,beta)
            self.assertTrue(np.isfinite(a).all());self.assertGreaterEqual(float(a.min()),0)
            self.assertLessEqual(float(a.max()),1);self.assertLessEqual(float(alpha.max()),.18+1e-7)
            outputs[frame]=a
        np.testing.assert_array_equal(outputs[0],sp.continuous_atmosphere(base,0,637,259006)[0])
        self.assertFalse(np.array_equal(outputs[30],sp.continuous_atmosphere(base,30,637,259006)[0]))
        # At the endpoint only the original fog with its continuous +4s phase
        # remains. Dust is suppressed on BOTH sides solely to isolate that clock.
        with mock.patch.object(sp,'_atmosphere_particles',return_value=[]):
            for frame in (90,91,120):
                actual=sp.continuous_atmosphere(base,frame,637,259006,opening_profile=profile)
                expected=sp.continuous_atmosphere(base,frame+120,637,259006)
                for a,b in zip(actual,expected):np.testing.assert_array_equal(a,b)
        # Adjacent-frame transition is bounded analytically by the smooth fields,
        # not a visual-quality percentage or a substitute for watched review.
        for a,b in ((89,90),(90,91)):
            self.assertLess(float(np.max(np.abs(outputs[a]-outputs[b]))),.002)
        for frame in (-1,637,638):
            a,alpha=sp.continuous_atmosphere(base,frame,637,259006,opening_profile=profile)
            np.testing.assert_array_equal(a,base);self.assertEqual(float(alpha.sum()),0)
        np.testing.assert_array_equal(base,original)

    def test_invalid_profile_fails_before_video_writer(self):
        import numpy as np
        base=np.zeros((2,2,3),np.float32)
        for profile in ('', 'unknown', True, 1, {}, []):
            with self.subTest(profile=profile),mock.patch.object(sp,'_write_atmosphere_video') as writer:
                for call in (lambda:sp.continuous_atmosphere(base,0,637,259006,opening_profile=profile),
                             lambda:sp._atmosphere_composite(base,0,259006,0,opening_profile=profile),
                             lambda:sp.write_continuous_video('missing','output',637,259006,opening_profile=profile)):
                    with self.assertRaisesRegex(ValueError,'INVALID_OPENING_ATMOSPHERE_PROFILE'):call()
                writer.assert_not_called()


class CorrectionSyntheticFFmpeg(unittest.TestCase):
    """Offline valid-duration two-source reference, not production qualification."""
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name);cls.plan,_,_,_,cls.moment=correction_source()
        cls.stills=[cls.root/f'scene{i}.ppm' for i in range(2)]
        cls.clips=[cls.root/f'animated{i}.mkv' for i in range(2)]
        for i,(still,clip,count) in enumerate(zip(cls.stills,cls.clips,[637,638])):
            synthetic_ppm(still,108,192,i)
            sp.write_continuous_video(still,clip,count,259006+i,
                                      opening_profile=cls.plan["scenes"][i]["atmosphere"].get("opening_profile"))
        cls.ass=cls.root/'empty.ass';cls.ass.write_text(sp.HEAD)
        cls.voice=cls.root/'voice.wav';cls.music=cls.root/'music.wav'
        rate=8000;seconds=2549
        tone=b''.join(int(900*math.sin(2*math.pi*220*i/rate)).to_bytes(2,'little',signed=True) for i in range(rate))
        pcm=bytearray(tone*seconds)
        # Sound after the narrative boundary but before extraction end proves the
        # source clock, while a later marker must never enter the cut.
        for lo,hi,freq in [(854.417,854.418,1100),(855.728,856,1900)]:
            a,b=round(lo*rate),round(hi*rate)
            pcm[2*a:2*b]=b''.join(int(900*math.sin(2*math.pi*freq*i/rate)).to_bytes(2,'little',signed=True) for i in range(b-a))
        for path,data in [(cls.voice,pcm),(cls.music,bytes(len(pcm)))]:
            with wave.open(str(path),'wb') as out:
                out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(data)
        with mock.patch.multiple(sp,VW=108,VH=192):
            cls.range=sp.reference_picture_range(cls.stills,cls.moment,cls.plan,hook_video=cls.clips)
            cls.picture=sp.write_editorial_picture(cls.stills,cls.moment,cls.plan,cls.root,hook_video=cls.clips)
            cls.reference=sp.render_args(cls.stills,cls.voice,cls.music,cls.ass,cls.moment,42,'null',cls.root/'ref.mp4',edit_plan=cls.plan,hook_video=cls.clips)
            cls.serial=sp.render_args(cls.stills,cls.voice,cls.music,cls.ass,cls.moment,42,'null',cls.root/'serial.mp4',edit_plan=cls.plan,hook_video=cls.clips,picture_video=cls.picture,picture_range=cls.range)

    def run_part(self,args,label,fmt):
        end=args.index('-map');cmd=args[:end]+['-map',label]
        gi=cmd.index('-filter_complex')+1
        cmd[gi]+=(';[aout]anullsink' if label=='[vout]' else ';[vout]nullsink')
        if label=='[vout]':cmd+=['-an','-threads:v','1','-pix_fmt','yuv420p','-frames:v','1260','-fps_mode','passthrough']
        else:cmd+=['-vn','-c:a','pcm_s16le','-ar','48000']
        cmd+=['-f',fmt,'-']
        result=subprocess.run(cmd,capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[-4000:])
        return result.stdout

    def test_every_picture_frame_and_pts_match_reference(self):
        ref=self.run_part(self.reference,'[vout]','framemd5')
        serial=self.run_part(self.serial,'[vout]','framemd5')
        clean=lambda b:[x for x in b.splitlines() if not x.startswith(b'#')]
        self.assertEqual(len(clean(ref)),1260);self.assertEqual(clean(ref),clean(serial))
        for i,line in enumerate(clean(serial)):
            self.assertEqual(int(line.split(b',')[2]),i)

    def test_every_pcm_sample_matches_reference_and_exact_output_length(self):
        ref=self.run_part(self.reference,'[aout]','s16le')
        serial=self.run_part(self.serial,'[aout]','s16le')
        self.assertEqual(len(ref),2016000*2*2);self.assertEqual(ref,serial)

    def test_all_source_frames_are_real_animated_and_exact_length(self):
        for path,count in zip(self.clips,[637,638]):
            result=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:v','-f','framemd5','-'],check=True,capture_output=True)
            lines=[x for x in result.stdout.splitlines() if not x.startswith(b'#')]
            self.assertEqual(len(lines),count)
            self.assertNotEqual(lines[-1].split(b',')[-1],lines[-2].split(b',')[-1])
            self.assertNotEqual(lines[150].split(b',')[-1],lines[151].split(b',')[-1])


if __name__ == "__main__":
    unittest.main()
