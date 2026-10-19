#!/usr/bin/env python3
"""Offline checks of the Shorts edit against STANDARD R8, on the real pilot-006 timeline and script.

Windows on whole sentences (30-55 s, no context opener first, first word at the cut), captions of 1-5 words,
no CTA, the reference only while KJV text is spoken, the hook only when it is the first line's own words,
and no figure overlay in the ffmpeg call. Missing data is an error, never a pass.
"""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shorts_produce as sp  # noqa: E402
import shorts_select  # noqa: E402

PILOT = HERE / "pilot-006"
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
WINDOWS, REJECTED = sp.snap_all(OFFLINE + RECORDED["chosen"], SENTENCES)


class Windows(unittest.TestCase):
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
        good = sp.snap(OFFLINE[0], SENTENCES)[0]
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


class Repair012(unittest.TestCase):
    def test_observed_openings_rejected(self):
        baseline=load(HERE/'pilot-012'/'shorts'/'selection.json')
        self.assertEqual([shorts_select.opening_reason(c['sentences'][0]) for c in baseline['chosen']],
                         ['INCOMPLETE_OPENING_LINE','DEPENDENT_OPENING_REFERENCE','INCOMPLETE_OPENING_LINE'])
        for c in baseline['chosen']:
            self.assertIsNone(sp.snap(c,c['sentences'])[0])
    def test_exact_three_second_boundary_and_complete_text(self):
        line={'text':'You can rest.','start':4.0,'end':7.0}
        self.assertIsNone(shorts_select.opening_reason(line))
        self.assertEqual(shorts_select.opening_reason(dict(line,end=7.001)),'OPENING_OVER_3S')
        self.assertEqual(shorts_select.opening_reason(dict(line,text='A little kindness:')),'INCOMPLETE_OPENING_LINE')
        self.assertEqual(shorts_select.opening_reason(dict(line,text='the bed itself.')),'CONTINUATION_OPENING_LINE')
    def test_actual_pilot012_candidates_and_resolution(self):
        timeline=load(HERE/'pilot-012'/'out'/'timeline.json')['sentences']
        script=load(HERE/'pilot-012'/'script.json');refs={r['id']:r.get('reference') for r in script['segments']}
        candidates=shorts_select.candidates(timeline,refs);self.assertTrue(candidates)
        for c in candidates:
            self.assertIsNone(shorts_select.opening_reason(c['sentences'][0]))
            self.assertIsNone(shorts_select.ending_reason(c['sentences'],timeline))
            self.assertIsNone(sp.snap(c,timeline)[1])
        old=load(HERE/'pilot-012'/'shorts'/'selection.json')['chosen'][0]
        next_line={'segment':old['sentences'][-1]['segment'],'text':'A later thought.','start':166,'end':170}
        self.assertEqual(shorts_select.ending_reason(old['sentences'],old['sentences']+[next_line]),'UNRESOLVED_SEGMENT_END')


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


if __name__ == "__main__":
    unittest.main()
