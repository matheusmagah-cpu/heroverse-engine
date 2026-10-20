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
EDITORIAL_PLAN = {
    "version": "shorts-editorial-plan-v1",
    "source_pilot": "pilot-005",
    "source_baseline_sha": "7fb9e9e1fad9396b80c029212f0a3144c1428d51",
    "source_sha256": {
        "script": "c0cf3d5fc0747b5f743d9d0189e9deb4326a124a9769a41d4341b14aa347359a",
        "timeline": "53496f5a82ed391422974e517b5b895059d0040db790c2044030f06bd06245c5",
        "inputs": "67e393596d74f77e64f5a9de143c99dbc4bc4cb2cb8e898b261900ae69623831",
    },
    "voice": {
        "asset": "pilot-005-voice-sha256-6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc.flac",
        "sha256": "6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc",
    },
    "music": {
        "asset": "original-rest-music.lossless.flac",
        "sha256": "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c",
    },
    "candidate": {
        "start": 459.860,
        "end": 499.672,
        "hook": "Lord, protect my relationships.",
        "title": "A Prayer for Peace in Your Relationships",
        "reference": None,
    },
    "tail_seconds": 0.5,
    "transition": {"type": "fade", "seconds": 0.5, "center_seconds": 22.153},
    "scenes": [
        {
            "image_id": "bg-home-sunrise",
            "asset": "pilot-005-img-bg-home-sunrise-sha256-5ebdbb61901120845c3872f15cdca23d2ff0baac58ae0284f6f52effffd848c6.png",
            "sha256": "5ebdbb61901120845c3872f15cdca23d2ff0baac58ae0284f6f52effffd848c6",
            "nominal_start": 0.0,
            "nominal_end": 22.153,
            "motion_profile": "phrase_push_in_v1",
        },
        {
            "image_id": "bg-garden",
            "asset": "pilot-002-img-bg-garden-sha256-5172945b7bc917143eb1e0d62ed1f66d90b943a9956ddd20b84c73b679dfea04.png",
            "sha256": "5172945b7bc917143eb1e0d62ed1f66d90b943a9956ddd20b84c73b679dfea04",
            "nominal_start": 22.153,
            "nominal_end": 40.312,
            "motion_profile": "phrase_pan_right_v1",
        },
    ],
    "publish": False,
}


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


def synthetic_ppm(path, width, height, scene=0):
    """Locally invented texture, not a copy of an image or a production asset."""
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            texture = (x * 11 + y * 7) % 31
            green = 40 + int(80 * x / max(1, width - 1))
            pixels.extend((175 + texture, green, 30) if scene == 0 else (30, green, 175 + texture))
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
        subtitles = sp.ass(moment, moment["hook"], refs, 40.312, timeline["sentences"])
        self.assertEqual(events(subtitles, "Hook"), [(0.0, 2.5, "Lord, protect my relationships.")])
        self.assertEqual(events(subtitles, "Ref"), [])
        self.assertGreater(len(events(subtitles, "Cap")), 10)

    def test_frame_plan_has_the_rounded_overlap_without_subtracting_it_twice(self):
        plan = sp.scene_frame_plan(EDITORIAL_PLAN)
        for key, value in {
                "fps": 30, "output_frames": 1209, "boundary_frame": 665,
                "fade_start_frame": 657, "fade_end_frame": 672, "fade_frames": 15,
                "scene_frames": [672, 552], "nominal_scene_frames": [665, 544],
                "scene_spans": [[0, 672], [657, 1209]]}.items():
            self.assertEqual(plan[key], value, key)
        self.assertEqual(sum(plan["scene_frames"]) - plan["fade_frames"], plan["output_frames"])
        self.assertEqual(sum(plan["nominal_scene_frames"]), plan["output_frames"])
        for length in plan["scene_frames"] + plan["nominal_scene_frames"]:
            self.assertGreaterEqual(length, 18 * sp.FPS)
            self.assertLessEqual(length, 36 * sp.FPS)
        self.assertEqual(math.floor(40.312 * 30 + 0.5), plan["output_frames"])
        self.assertLessEqual(abs(plan["output_frames"] / 30 - 40.312), 1 / 30)
        self.assertEqual(sp.TAIL_S, 0.5)

    def test_phrase_progress_matches_the_fixed_expression_and_is_monotonic(self):
        _, _, _, moment = editorial_source()
        for start, end in [(0, 672 / 30), (657 / 30, 1209 / 30)]:
            bounds = phrase_boundaries(moment, start, end)
            self.assertGreater(len(bounds), 8)
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
        for start, end in [(0, 22.4), (21.9, 40.3)]:
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

    def test_editorial_render_has_one_padded_transition_and_preserves_audio_and_codec(self):
        _, _, _, moment = editorial_source()
        paths = [Path("/synthetic/first.ppm"), Path("/synthetic/second.ppm")]
        args = sp.render_args(paths, Path("/synthetic/voice.wav"), Path("/synthetic/music.wav"),
                              Path("/synthetic/captions.ass"), moment, 40.312, "null",
                              Path("/synthetic/result.mp4"), edit_plan=EDITORIAL_PLAN)
        graph = args[args.index("-filter_complex") + 1]
        self.assertEqual(graph.count("xfade="), 1)
        match = re.search(r"xfade=transition=fade:duration=([\d.]+):offset=([\d.]+)", graph)
        self.assertIsNotNone(match)
        self.assertEqual(tuple(map(float, match.groups())), (0.5, 21.9))
        self.assertNotIn("overlay", graph)
        self.assertNotIn("setpts=0.", graph)
        self.assertIn("loudnorm=I=-14:TP=-2:LRA=9", graph)
        self.assertIn("alimiter=limit=0.75:attack=5:release=50:level=false", graph)
        self.assertIn("apad=whole_dur=40.312", graph)
        for option, value in [("-c:v", "libx264"), ("-r", "30"), ("-c:a", "aac"), ("-ar", "48000")]:
            self.assertEqual(args[args.index(option) + 1], value)
        self.assertIn("format=yuv420p", graph)
        self.assertEqual(inspect.signature(sp.render_args).parameters["edit_plan"].kind,
                         inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual((sp.VW, sp.VH, sp.FPS, sp.TAIL_S), (1080, 1920, 30, 0.5))

    def test_actual_emitted_camera_expressions_reach_the_declared_endpoints_without_clamping(self):
        _, _, _, moment = editorial_source()
        _, parts = sp.editorial_picture([Path("/synthetic/a.ppm"), Path("/synthetic/b.ppm")],
                                        moment, EDITORIAL_PLAN)
        expressions = [re.search(r"zoompan=z='([^']+)':x='([^']+)':y='([^']+)'", part)
                       for part in parts if "zoompan=" in part]
        self.assertEqual(len(expressions), 2)
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
            if index == 0:
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
        for mutation in ("tail", "motion", "source_hash", "extra"):
            with self.subTest(mutation=mutation):
                self.prepared = json.loads(original)
                plan = self.prepared["edit_plan"]
                if mutation == "tail":
                    plan["tail_seconds"] = 0.4
                elif mutation == "motion":
                    plan["scenes"][0]["motion_profile"] = "arbitrary_expression"
                elif mutation == "source_hash":
                    plan["source_sha256"]["timeline"] = "0" * 64
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
                            mock.patch.object(sp, "render_args", wraps=sp.render_args) as renderer, \
                            mock.patch.object(sp, "run") as render:
                        record = sp.produce(work, moment, 0, script, images, None, music, out,
                                            timeline_sentences=timeline["sentences"], script_refs=refs,
                                            edit_plan=edit_plan)
                        renderer.assert_called_once()
                        render.assert_called_once()
                        self.assertEqual(renderer.call_args.args[1], expected_voice)
                        actual_args = render.call_args.args[0]
                        actual_inputs = [actual_args[i + 1] for i, value in enumerate(actual_args) if value == "-i"]
                        self.assertIn(str(expected_voice), actual_inputs)
                        self.assertEqual(len(actual_inputs), 4)
                        self.assertEqual(prepare.call_count, 2)
                        self.assertEqual(record["sha256"], "f" * 64)
                        if edit_plan is not None:
                            self.assertEqual(hashed.call_args_list[0].args[0], expected_voice)
                            self.assertNotIn(str(legacy_wav), actual_inputs)
                            self.assertEqual(probe.call_count, 2)
                            self.assertIs(record["publish"], False)
                        else:
                            self.assertNotIn(str(original_flac), actual_inputs)
                            probe.assert_not_called()


class EditorialSyntheticFFmpeg(unittest.TestCase):
    """Synthetic source/render measurements only: never production or watched-review evidence."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.width, cls.height = 108, 192
        cls.stills = [cls.root / "red.ppm", cls.root / "blue.ppm"]
        for index, path in enumerate(cls.stills):
            synthetic_ppm(path, 216, 384, index)
        # A tiny 8 kHz local test tone, long enough for the renderer's unmodified source seeks.
        # Production still resamples to 48 kHz and preserves its original narration.
        cls.audio = cls.root / "synthetic.wav"
        sample_rate = 8000
        one_second = b"".join(int(900 * math.sin(2 * math.pi * 220 * i / sample_rate))
                              .to_bytes(2, "little", signed=True) for i in range(sample_rate))
        with wave.open(str(cls.audio), "wb") as sound:
            sound.setnchannels(1)
            sound.setsampwidth(2)
            sound.setframerate(sample_rate)
            for _ in range(math.ceil(sp.MUSIC_OFFSET + 501)):
                sound.writeframesraw(one_second)
        cls.captions = cls.root / "empty.ass"
        cls.captions.write_text(sp.HEAD)
        _, _, _, cls.moment = editorial_source()
        cls.output = cls.root / "synthetic-stills.mp4"
        with mock.patch.multiple(sp, VW=cls.width, VH=cls.height):
            args = sp.render_args(cls.stills, cls.audio, cls.audio, cls.captions,
                                  cls.moment, 40.312, "null", cls.output, edit_plan=EDITORIAL_PLAN)
        # Keep the production graph/codecs/quantized clock; bound CPU use in small CI workers.
        args[1:1] = ["-filter_complex_threads", "1", "-threads", "1"]
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

    def test_actual_scene_fingerprints_fade_coverage_and_second_scene_length(self):
        colors = [(sum(frame[0::3]) / (self.width * self.height),
                   sum(frame[2::3]) / (self.width * self.height)) for frame in self.frames]
        # Red and blue dominance is an independent source fingerprint, not copied plan arithmetic.
        mixed = [i for i, (red, blue) in enumerate(colors) if red > 45 and blue > 45]
        self.assertGreater(len(mixed), 8)
        self.assertGreaterEqual(min(mixed), 657)
        self.assertLess(max(mixed), 672)
        self.assertTrue(all(red > blue * 3 for red, blue in colors[:657]))
        self.assertTrue(all(blue > red * 3 for red, blue in colors[672:]))
        self.assertGreaterEqual(len(colors[665:]), 540)
        self.assertGreaterEqual(len(colors[657:]), 540)
        self.assertLessEqual(len(colors[657:]), 1080)
        self.assertLess(colors[664][0], colors[658][0])
        self.assertGreater(colors[664][1], colors[658][1])
        hashes = [hashlib.sha256(frame).hexdigest() for frame in self.frames]
        self.assertNotEqual(hashes[0], hashes[650])
        self.assertNotEqual(hashes[672], hashes[-1])
        self.assertNotEqual(hashes[-61], hashes[-1], "the ending cannot freeze for two seconds")
        for frame in self.frames:
            self.assertGreater(max(frame), 100, "a decoded frame has no source coverage")
        black = self.invoke([
            "ffmpeg", "-hide_banner", "-i", str(self.output), "-an", "-vf",
            "blackdetect=d=0.0333333333333333:pix_th=0.02:pic_th=0.99", "-f", "null", "-"])
        self.assertNotIn(b"black_start:", black.stderr)

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
            args = sp.render_args(self.stills, self.audio, self.audio, self.captions,
                                  self.moment, 40.312, "null", output, edit_plan=EDITORIAL_PLAN)
        # Only adapt the two source inputs: the exact production filter graph consumes a moving
        # test clock. Static images can legitimately repeat low-resolution integer-crop samples,
        # so static hashes alone cannot establish that the graph did not repeat its final frame.
        for path in reversed(self.stills):
            end = args.index(str(path)) + 1
            start = max(i for i in range(end) if args[i] == "-loop")
            duration = args[args.index("-t", start, end) + 1]
            args[start:end] = ["-f", "lavfi", "-i",
                               f"testsrc2=size={self.width}x{self.height}:rate=30:duration={duration}"]
        args[1:1] = ["-filter_complex_threads", "1", "-threads", "1"]
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
    """Replace precisely one approved scalar; retain all other raw bytes, including comments."""
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
    return body, frozen


class FrozenEditorialWorkflow(unittest.TestCase):
    def source(self):
        return (HERE.parents[1] / ".github" / "workflows" / "shorts.yml").read_bytes()

    def test_every_unapproved_workflow_byte_including_comments_is_frozen(self):
        _, frozen = workflow_body_and_frozen_bytes(self.source())
        self.assertEqual(hashlib.sha256(frozen).hexdigest(),
                         "dfd67d011a1b93e2d959369181ceb5be23d83abce4045a8ed1ca6cc9272b1bce")

    def test_card_baseloader_structural_hashes_or_stricter_stdlib_byte_assertion(self):
        source = self.source()
        # The byte assertion also runs in CI without installing an unpinned YAML dependency.
        _, frozen = workflow_body_and_frozen_bytes(source)
        self.assertEqual(hashlib.sha256(frozen).hexdigest(),
                         "dfd67d011a1b93e2d959369181ceb5be23d83abce4045a8ed1ca6cc9272b1bce")
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
        self.assertEqual(digest(document), "92056d8367a1c3b69b314b595679aebedcd73a1dd59d957c4d7e862d49dacaf2")

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


if __name__ == "__main__":
    unittest.main()
