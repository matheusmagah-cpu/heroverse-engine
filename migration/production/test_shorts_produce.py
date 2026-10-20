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
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
