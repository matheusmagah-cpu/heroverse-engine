#!/usr/bin/env python3
"""Owner 27/10 ~22:50 UTC (R1-R4, the long and the Shorts, "em qualquer situação"): no stall. Offline: every clip
already made is reused (R1), the Pavo budget goes first to the spoken shots (R2), the silent shots it does not reach
are filled from free licensed footage or approved stills in motion, each still approved by Claude (R3), and a clip that
keeps Pavo's speech is judged clip by clip (R4: story QA v4 speech_checks) and mixed with one gain, short fades and a
continuous bed."""
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
import episode_build as eb  # noqa: E402
import pavo_native as pn  # noqa: E402
import shot_sources as ss  # noqa: E402

HAS_FFMPEG = shutil.which("ffmpeg") is not None
STYLE = "Painterly cinematic realism, cinema camera"
V4 = pn.criteria()


def plan():
    return {"episode": "t-sources", "aspect_ratio": "16:9", "narration": [{"kind": "story", "text": "The river ran through the garden."},
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
        # review of #476: the dispatch guard's worst-case bound, not the expected mean (which would let s-god, s-river
        # and s-pair in too and stop the batch half-way)
        one = long_preflight.planned_units([p["shots"][0]], worst=True)
        self.assertGreater(one, long_preflight.planned_units(p["shots"][:3]))
        got = dict((s["id"], c) for s, c in ss.allocate(p, todo, one))
        self.assertEqual(got, {"s-eve": "pavo", "s-god": "WAIT_PAVO_BUDGET", "s-river": "fallback",
                               "s-pair": "WAIT_PAVO_BUDGET"})
        rich = dict((s["id"], c) for s, c in ss.allocate(p, todo, 10 ** 6))
        self.assertEqual(set(rich.values()), {"pavo"})

    def test_a_planned_fallback_never_takes_the_budget_or_a_probe(self):
        # owner 28/10 (arc-02, a long designed to one day's Pavo budget): before this, allocate and probe-queue spent
        # the budget in risk order, so a wide or establishing shot the plan gives to FLUX or footage (rank 3) took Pavo
        # before the acted scenes (rank 4); the plan's source_design now decides, and a character shot stays on Pavo
        import long_preflight
        p = plan()
        p["source_design"] = {"pavo_talking": ["s-eve"], "pavo_voice_over": ["s-god"], "pavo_scene": ["s-pair"],
                              "window": [], "footage": ["s-river"], "still_motion": []}
        self.assertEqual(ss.source_design_problems(p), [])
        self.assertEqual(ss.planned_fallbacks(p), {"s-river"})
        todo = [s for _, s in eb.risk_order(p["shots"])]
        rich = dict((s["id"], c) for s, c in ss.allocate(p, todo, 10 ** 6))
        self.assertEqual(rich, {"s-eve": "pavo", "s-god": "pavo", "s-river": "fallback", "s-pair": "pavo"})
        q = long_preflight.queue(p, {}, {}, max_units=10 ** 6)
        probed = [x for b in q["batches"] for x in b["shots"].split(",")]
        self.assertEqual((q["planned_fallback"], sorted(probed)), (["s-river"], ["s-eve", "s-god", "s-pair"]))
        # a plan that names a character or a spoken shot as a fallback is refused, and that shot stays on Pavo
        p["source_design"].update(pavo_scene=[], still_motion=["s-pair"])
        self.assertTrue(any(x.startswith("SOURCE_DESIGN_FALLBACK SOURCE_CHARACTER_SHOT s-pair")
                            for x in ss.source_design_problems(p)))
        self.assertEqual(ss.planned_fallbacks(p), {"s-river"})
        p["source_design"].update(still_motion=["s-river", "s-nope"])
        bad = ss.source_design_problems(p)
        for code in ("SOURCE_DESIGN_TWICE s-river", "SOURCE_DESIGN_UNKNOWN still_motion s-nope",
                     "SOURCE_DESIGN_MISSING s-pair"):
            self.assertTrue(any(x.startswith(code) for x in bad), (code, bad))
        # without a source_design nothing changes (the Shorts and arc-01)
        del p["source_design"]
        self.assertEqual(ss.planned_fallbacks(p), set())

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
        # review of #476: the shot's kind, speaker and characters are part of a fallback's request too
        for change in ({"characters": ["eve"]}, {"speaker": "eve", "line": "Why do you hide?"}, {"kind": "keeper"},
                       {"voiceover": True}):
            p = plan()
            p["shots"][2].update(change)
            self.assertTrue(any(m.startswith("SHOT_REQUEST_CHANGED") and "s-river" in m
                                for m in eb.review_problems(p, {}, approvals)), change)

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

    def test_e139_a_fallback_picture_is_never_shown_twice_within_the_repeat_gap(self):
        """E139 (found designing arc-02, 28/10): story QA's image_repeat_gap_seconds_min was measured on the hold's
        `image`, `<shot id>#<src_start>`, so the same library clip or still approved for two shots counted as two
        pictures; approve-source let it in and qa_pilot passed it. A fallback's picture is its source's sha256: a
        second shot of the plan within the gap is refused at approval (SOURCE_IMAGE_REPEAT), and qa_pilot keys a
        fallback hold by that sha256 (a still is one picture whatever part is shown; footage by its part too)."""
        import long_plan_check as lpc
        sys.path.insert(0, str(HERE.parent))
        import qa_pilot
        # a Short is shorter than the gap: the same clip on two of its shots is a repeat
        p = plan()
        p["shots"].append(dict(p["shots"][2], id="s-river2", lines=[1]))
        p["shots"].pop(3)
        ss.approve_source(p, "s-river", "footage", "clip-river-a", 9.6, "the river", lib=self.lib, shots_dir=self.dir)
        with self.assertRaises(SystemExit) as err:
            ss.approve_source(p, "s-river2", "footage", "clip-river-a", 9.6, "the river", lib=self.lib,
                              shots_dir=self.dir)
        self.assertTrue(str(err.exception).startswith("SOURCE_IMAGE_REPEAT s-river2"), str(err.exception))
        ss.approve_source(p, "s-river", "footage", "clip-river-a", 9.6, "approved again", lib=self.lib,
                          shots_dir=self.dir)                       # the same shot again is not a repeat
        # the long: the gap is measured on the plan's own timeline
        arc = json.loads((HERE / "plans" / "arc-02-long.json").read_text())
        gap = lpc.qa_for(arc)["grammar"]["image_repeat_gap_seconds_min"]
        tl = lpc.timeline(arc)
        at = {s["id"]: (tl["begin"][i], tl["end"][i]) for i, s in enumerate(arc["shots"])}
        foot = arc["source_design"]["footage"]
        first = foot[0]
        near = next(x for x in foot[1:] if at[x][0] - at[first][1] < gap)
        far = next(x for x in reversed(foot) if at[x][0] - at[first][1] >= gap)
        ids = [s["id"] for s in arc["shots"]]
        said = {w for x in (first, near, far) for w in ss.subject(arc, arc["shots"][ids.index(x)], ids.index(x))}
        title = " ".join(sorted(w for w in said if not ss.period_clash(arc, {"title": w, "query": ""})))
        lib = [clip("clip-any", theme="sky", title=title)]
        d = self.dir / "long"
        ss.approve_source(arc, first, "footage", "clip-any", 9.6, "x", lib=lib, shots_dir=d)
        ss.approve_source(arc, far, "footage", "clip-any", 9.6, "x", lib=lib, shots_dir=d)   # far enough apart
        with self.assertRaises(SystemExit) as err:
            ss.approve_source(arc, near, "footage", "clip-any", 9.6, "x", lib=lib, shots_dir=d)
        self.assertTrue(str(err.exception).startswith(f"SOURCE_IMAGE_REPEAT {near}"), str(err.exception))
        # qa_pilot: two holds of different shots showing one still (or one footage part) are the same picture
        holds = [{"start": 0.0, "end": 5.0, "image": "s-a#0.000"}, {"start": 30.0, "end": 35.0, "image": "s-b#0.000"},
                 {"start": 60.0, "end": 65.0, "image": "s-c#2.000"}, {"start": 90.0, "end": 95.0, "image": "s-d#0.000"}]
        manifest = {"holds": holds, "images": {"s-a": {"sha256": "a" * 64}, "s-b": {"sha256": "a" * 64}},
                    "clips": [{"id": "s-c", "source": "footage", "source_sha256": "c" * 64},
                              {"id": "s-d", "source": "footage", "source_sha256": "c" * 64}]}
        self.assertEqual(qa_pilot.repeat_gaps(manifest), [25.0])     # the still twice; footage parts differ
        manifest["holds"][3]["image"] = "s-d#2.000"
        self.assertEqual(qa_pilot.repeat_gaps(manifest), [25.0, 25.0])
        manifest["images"]["s-b"]["sha256"] = "b" * 64
        manifest["clips"][1]["source_sha256"] = "d" * 64
        self.assertEqual(qa_pilot.repeat_gaps(manifest), [])           # different pictures: no repeat


class OwnerException(unittest.TestCase):
    """Owner 28/10 ~02:30 UTC ("tem que ser amanhã"): for the arc-01 long ONLY, a silent shot with characters may be a
    still in motion made by Pavo with every approved reference of each character it shows, and a spoken shot on the
    Kokoro voice (plan B) may stand on such a still. Everywhere else v4's refusals stand."""

    def setUp(self):
        self.saved = (ss.owner_exception, eb.reference_records)
        self.refs = {"eve": [("ch-eve-full", {"sha256": "e" * 64})], "keeper": [("ch-keeper-front", {"sha256": "k" * 64})]}
        eb.reference_records = lambda cid, chars=None, *a, **k: self.refs[cid]

    def tearDown(self):
        ss.owner_exception, eb.reference_records = self.saved

    @staticmethod
    def still(shas, inputs=None):
        return {"references": [{"record": "r", "sha256": s} for s in shas],
                "pavo": {"generate": {"model": "agnes-image", "conversation_id": "1",
                                      "input_images": len(shas) if inputs is None else inputs},
                         "job": {"conversation_id": "1", "status": "completed"}}}

    def test_without_the_exception_v4_refuses_every_person_or_voice_on_a_fallback(self):
        ss.owner_exception = lambda plan: False
        p = plan()
        good = self.still(["e" * 64])
        self.assertTrue(ss.fallback_refusal(p, p["shots"][3], 3, "still_motion", good).startswith("SOURCE_CHARACTER_SHOT"))
        self.assertTrue(ss.fallback_refusal(p, p["shots"][0], 0, "still_motion", good).startswith("SOURCE_SPOKEN_SHOT"))
        self.assertIsNone(ss.fallback_refusal(p, p["shots"][2], 2, "footage"))

    def test_the_exception_takes_a_character_still_only_with_its_approved_references(self):
        ss.owner_exception = lambda plan: True
        p = plan()
        pair = p["shots"][3]
        self.assertIsNone(ss.fallback_refusal(p, pair, 3, "still_motion", self.still(["e" * 64])))
        for bad in (self.still([]), self.still(["x" * 64]), self.still(["e" * 64], inputs=0), {"references": []}):
            self.assertTrue(ss.fallback_refusal(p, pair, 3, "still_motion", bad).startswith("SOURCE_CHARACTER_STILL"))
        self.assertTrue(ss.fallback_refusal(p, pair, 3, "footage").startswith("SOURCE_CHARACTER_SHOT"))

    def test_the_exception_takes_a_spoken_shot_only_on_the_kokoro_voice(self):
        ss.owner_exception = lambda plan: True
        p = plan()
        p["criteria"] = pn.V4X
        eve = p["shots"][0]
        self.assertTrue(ss.fallback_refusal(p, eve, 0, "still_motion", self.still(["e" * 64]))
                        .startswith("SOURCE_SPOKEN_SHOT"))          # Pavo's own speech route: never a still
        eve["audio_route"] = "kokoro"
        self.assertIsNone(ss.fallback_refusal(p, eve, 0, "still_motion", self.still(["e" * 64])))
        god = p["shots"][1]
        god["audio_route"] = "kokoro"
        self.assertIsNone(ss.fallback_refusal(p, god, 1, "still_motion", {}))   # God: a still with no one on it
        self.assertTrue(ss.fallback_refusal(p, god, 1, "footage").startswith("SOURCE_SPOKEN_SHOT"))

    def test_a_shot_may_show_another_shots_approved_still_only_far_enough_apart(self):
        """Owner exception, 28/10 contingency (fewer new Pavo stills, nothing loosened): a character shot may show the
        APPROVED still of another shot (`still_of`) with another camera move, only with the same characters, never
        chained, and every shot showing that still at least image_repeat_gap_seconds_min from every other (E139)."""
        import copy
        import long_plan_check as lpc
        ss.owner_exception, eb.reference_records = self.saved
        arc = json.loads((HERE / "plans" / "arc-01-long.json").read_text())
        reused = [s for s in arc["shots"] if s.get("still_of")]
        if not reused:
            self.skipTest("the plan reuses no still")
        self.assertEqual(ss.still_of_problems(arc), [])
        self.assertEqual(lpc.check(arc)["problems"], [])
        ids = [s["id"] for s in arc["shots"]]
        tl = lpc.timeline(arc)
        tgt = reused[0]
        src = tgt["still_of"]
        near = next(s["id"] for i, s in enumerate(arc["shots"]) if s["id"] not in (tgt["id"], src)
                    and s.get("window_of") is None and s["kind"] == tgt["kind"]
                    and sorted(ss.shown_characters(s)) == sorted(ss.shown_characters(tgt))
                    and abs(tl["begin"][i] - tl["begin"][ids.index(src)]) < 120)
        for change, code in (({"still_of": tgt["id"]}, "STILL_OF_UNKNOWN"),
                             ({"still_of": "no-such-shot"}, "STILL_OF_UNKNOWN")):
            p = copy.deepcopy(arc)
            p["shots"][ids.index(tgt["id"])].update(change)
            self.assertTrue(any(r.startswith(code) for r in ss.still_of_problems(p)), code)
        p = copy.deepcopy(arc)
        p["shots"][ids.index(near)]["still_of"] = src                 # the same still within the gap
        self.assertTrue(any(r.startswith(f"STILL_OF_GAP {near}") or r.startswith(f"STILL_OF_GAP {tgt['id']}")
                            or (r.startswith("STILL_OF_GAP") and near in r) for r in ss.still_of_problems(p)))
        self.assertTrue(any(r.startswith("STILL_OF_GAP") for r in lpc.check(p)["problems"]))
        p = copy.deepcopy(arc)
        other = next(s for s in arc["shots"] if s.get("window_of") is None and ss.has_character(s)
                     and sorted(ss.shown_characters(s)) != sorted(ss.shown_characters(tgt)) and not s.get("still_of"))
        p["shots"][ids.index(tgt["id"])]["still_of"] = other["id"]
        self.assertTrue(any(r.startswith("STILL_OF_CHARACTERS") for r in ss.still_of_problems(p)))
        p = copy.deepcopy(arc)
        p["shots"][ids.index(src)]["still_of"] = near                 # a reused still never names a reuse
        self.assertTrue(any(r.startswith("STILL_OF_CHAIN") for r in ss.still_of_problems(p)))
        p = copy.deepcopy(arc)
        p["episode"] = "arc-02-long"                                  # the exception is the arc-01 long's only
        self.assertTrue(all(r.startswith("STILL_OF_OUTSIDE_EXCEPTION") for r in ss.still_of_problems(p)))
        # approve-source: the reuse takes its source's APPROVED still with another camera move; no other shot may
        approved = [s for s in reused if (pc_rec := __import__("plan_check").still_record(
            f"arc-01-long-{s['still_of']}")) and pc_rec.get("status") == "APPROVED"]
        if approved:
            t = approved[0]
            d = Path(tempfile.mkdtemp())
            try:
                a = ss.approve_source(arc, t["id"], "still_motion", f"arc-01-long-{t['still_of']}", 9.6, "x",
                                      shots_dir=d)
                self.assertEqual(a["motion"], ss.REUSE_KEEPER_MOTION if t["kind"] == "keeper" else ss.REUSE_MOTION)
                other = next(s["id"] for s in arc["shots"] if s["id"] not in (t["id"], t["still_of"])
                             and s.get("still_of") != t["still_of"] and s.get("window_of") is None
                             and sorted(ss.shown_characters(s)) == sorted(ss.shown_characters(t)))
                with self.assertRaises(SystemExit) as err:   # a shot that does not name the still never takes it
                    ss.approve_source(arc, other, "still_motion", f"arc-01-long-{t['still_of']}", 9.6, "x",
                                      shots_dir=d)
                self.assertTrue(str(err.exception).startswith("STILL_NOT_FOR_SHOT"), str(err.exception))
            finally:
                shutil.rmtree(d)

    def test_v5_is_v4_with_only_the_source_rows_and_the_agreed_values_changed(self):
        """Owner 28/10 ("destrave todos os vídeos.. tanto os longos.. tanto os shorts"): story QA v5 is the general rule
        of the integrated source plan, for any plan that names it; v4 copied, then only the source order (Pavo assets,
        Pavo video, faceless footage, animated stills, Kokoro), the 12 s hold and the measured character-free share."""
        import long_build
        import long_plan_check as lpc
        ss.owner_exception = self.saved[0]
        self.assertIsNone(lpc.frozen_qa_problem(plan={"criteria": lpc.V5}))
        v4, v5 = lpc.qa(lpc.QA_V4), lpc.qa(lpc.QA_V5)
        self.assertNotIn("owner_exception", v5)                       # general: bound to no plan
        self.assertEqual(v5["grammar"]["scene_seconds"], [4.0, 12.0])
        self.assertEqual(v5["grammar"]["image_repeat_gap_seconds_min"], 300.0)
        self.assertTrue(v5["grammar"]["every_scene_in_motion"])
        self.assertLess(v5["grammar"]["establishing_share_max"], 0.2)
        for key in set(v4) | set(v5):
            if key in ("version", "frozen_at_utc", "owner_v5"):
                continue
            if key in ("rights", "grammar"):
                skip = ("fallback_sources", "fallback_shots", "scene_seconds", "establishing_share_max")
                self.assertEqual({k: v for k, v in v4[key].items() if k not in skip},
                                 {k: v for k, v in v5[key].items() if k not in skip}, key)
            else:
                self.assertEqual(v4.get(key), v5.get(key), key)
        for episode in ("arc-01-long", "arc-02-long", "genesis-10-short"):
            self.assertTrue(lpc.owner_exception({"criteria": lpc.V5, "episode": episode}))
        self.assertFalse(lpc.owner_exception({"criteria": lpc.V4, "episode": "arc-01-long"}))
        self.assertEqual(long_build.plan_holds({"criteria": lpc.V5, "version": lpc.VERSION}), (4.0, 12.0))
        self.assertEqual(lpc.establishing_share_max(v4), __import__("plan_check").ESTABLISHING_SHARE_MAX)
        # faceless footage: only on a v5 shot of anonymous figures; text, branding and the modern world stay refused
        anon = {"id": "s-x", "kind": "scene", "characters": [], "figures": "anonymous"}
        v5plan = {"criteria": lpc.V5, "passage": "Genesis 3"}
        self.assertTrue(ss.faceless_shot(v5plan, anon))
        self.assertFalse(ss.faceless_shot({"criteria": lpc.V4, "passage": "Genesis 3"}, anon))
        self.assertFalse(ss.faceless_shot(v5plan, dict(anon, characters=["eve"])))
        rec = {"title": "woman walking barefoot on grass", "query": "bare feet grass"}
        self.assertTrue(ss.period_clash(v5plan, rec))
        self.assertFalse(ss.period_clash(v5plan, rec, faceless=True))
        self.assertTrue(ss.period_clash(v5plan, {"title": "woman walking in the city street", "query": "x"},
                                        faceless=True))

    def test_the_exception_is_bound_to_the_arc01_plan(self):
        import long_plan_check as lpc
        ss.owner_exception = self.saved[0]
        q = lpc.qa_for({"criteria": lpc.V4X})
        self.assertEqual(q["owner_exception"]["episode"], "arc-01-long")
        self.assertTrue(lpc.owner_exception({"criteria": lpc.V4X, "episode": "arc-01-long"}))
        self.assertFalse(lpc.owner_exception({"criteria": lpc.V4X, "episode": "arc-02-long"}))
        self.assertFalse(lpc.owner_exception({"criteria": lpc.V4, "episode": "arc-01-long"}))
        self.assertIsNone(lpc.frozen_qa_problem(plan={"criteria": lpc.V4X}))
        v4, v4x = lpc.qa(lpc.QA_V4), lpc.qa(lpc.QA_V4X)
        for key in set(v4) | set(v4x):   # only the fallback rows, the version, the freeze time and the record change
            if key in ("version", "frozen_at_utc", "owner_exception"):
                continue
            if key in ("rights", "grammar"):
                a = {k: v for k, v in v4[key].items() if k not in ("fallback_sources", "fallback_shots")}
                b = {k: v for k, v in v4x[key].items() if k not in ("fallback_sources", "fallback_shots")}
                self.assertEqual(a, b, key)
            else:
                self.assertEqual(v4.get(key), v4x.get(key), key)


class VoiceAudio(unittest.TestCase):
    """E137: speech-check died on the arc-01 long's native clips (28/10): resemblyzer.preprocess_wav reads with librosa,
    which (>= 0.11) reads only what soundfile reads, never an MP4. The voice is measured on a WAV decoded from the clip."""

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
    def test_e137_the_voice_encoder_reads_a_wav_decoded_from_the_clip(self):
        import inspect
        import wave
        d = Path(tempfile.mkdtemp())
        try:
            clip = d / "c.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x36:d=1",
                            "-f", "lavfi", "-i", "sine=f=220:d=1", "-shortest", "-c:v", "libx264", "-c:a", "aac",
                            str(clip)], check=True)
            out = pn.voice_wav(clip)
            with wave.open(out) as w:
                self.assertEqual((w.getnchannels(), w.getframerate()), (1, 16000))
                self.assertGreater(w.getnframes(), 8000)
            with self.assertRaises(SystemExit):
                pn.voice_wav(d / "missing.mp4")
        finally:
            shutil.rmtree(d)
        src = inspect.getsource(pn.measure)
        self.assertNotIn("preprocess_wav(str(", src)          # never the clip path itself
        self.assertEqual(src.count("preprocess_wav(voice_wav("), 2)   # the clip and every reference


class ApproveReuse(unittest.TestCase):
    """R1, review of #476: an inventory clip (Pavo's CDN) is approved only for the request the committed preflight
    says the plan sends now, clean, from the CDN, and on a native spoken shot only with its speech checks passed."""
    URL = "https://cos-aigc-default.agnes-ai.space/v/clip-1.mp4"

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.saved = pn.VOICES
        self.sha = "1" * 64
        self.inv = self.dir / "inv"
        self.inv.mkdir()
        self.write_inventory()

    def tearDown(self):
        pn.VOICES = self.saved
        shutil.rmtree(self.dir)

    def write_inventory(self, url=None, checks=None, request="req-eve"):
        (self.inv / "inventory.json").write_text(json.dumps({"plan": "migration/production/bible/plans/t-sources.json",
                                                             "shots": [{"shot": "s-eve", "request_sha256": request,
                                                                        "clips": [{"sha256": self.sha,
                                                                                   "url": url or self.URL,
                                                                                   "seconds": 6.0,
                                                                                   "lipsync_check": checks or []}]}]}))

    def approve(self, p=None, digests=None, item=None, **kw):
        return ss.approve_source(p or plan(), "s-eve", "pavo_reuse", item or f"{self.inv / 'inventory.json'}#{self.sha}",
                                 9.6, "the same take, clean", digests=digests, shots_dir=self.dir,
                                 today="2026-10-28", inventories=self.inv, **kw)

    def refused(self, code, **kw):
        with self.assertRaises(SystemExit) as err:
            self.approve(**kw)
        self.assertTrue(str(err.exception).startswith(code), (code, str(err.exception)))
        self.assertFalse((self.dir / "t-sources.json").exists())   # nothing approved by a refusal

    def test_a_clean_inventory_clip_of_the_request_now_is_approved(self):
        self.refused("REUSE_PREFLIGHT_MISSING")                                    # no committed preflight digests
        self.refused("REUSE_REQUEST_CHANGED", digests={"s-eve": "req-other"})
        self.refused("REUSE_NOT_CLEAN", digests={"s-eve": "req-eve"}, item=f"{self.inv / 'inventory.json'}#{'2' * 64}")
        self.write_inventory(checks=["AUDIO_NOT_OUR_LINE"])
        self.refused("REUSE_NOT_CLEAN", digests={"s-eve": "req-eve"})
        self.write_inventory(url="https://example.com/clip-1.mp4")
        self.refused("REUSE_URL_REFUSED", digests={"s-eve": "req-eve"})
        self.write_inventory()
        a = self.approve(digests={"s-eve": "req-eve"})
        self.assertEqual((a["url"], a["clip_sha256"], a["request_sha256"]), (self.URL, self.sha, "req-eve"))
        self.assertNotIn("speech", a)                                               # the Kokoro route: no Pavo speech

    def test_a_native_spoken_shot_reuses_a_clip_only_with_its_speech_checks(self):
        p = dict(plan(), audio_route="pavo_native", ambience="the garden at dusk")
        speech = self.dir / "speech"
        speech.mkdir()
        voices = self.dir / "voices.json"
        voices.write_text(json.dumps({"voices": {"eve": {"pavo_voice": "x", "reference": {"clip_sha256": "e" * 64}},
                                                 "keeper": {"pavo_voice": "y", "reference": {"clip_sha256": "k" * 64}}}}))
        pn.VOICES = voices
        kw = {"p": p, "digests": {"s-eve": "req-eve"}, "speech_dir": speech}
        self.refused("REUSE_SPEECH_UNCHECKED", **kw)
        m = {"asr": {"model_bin_sha256": V4["speech"]["asr_model"]["model_bin_sha256"], "text": "Why do you hide?",
                     "speech_span": [1.0, 3.0]},
             "voice": {"reference": "a" * 64, "same": 0.93, "others": [0.7], "others_references": ["k" * 64]},
             "lufs": -24.0, "music": 0.0, "singing": 0.0, "lips": []}
        (speech / f"{self.sha}.json").write_text(json.dumps({"measures": m}))
        self.refused("SPEECH_CHECKS_FAILED s-eve VOICE_REFERENCE_MISMATCH", **kw)      # bound to voices.json
        m["voice"]["reference"] = "e" * 64
        (speech / f"{self.sha}.json").write_text(json.dumps({"measures": m}))
        a = self.approve(**kw)
        self.assertEqual((a["speech"]["clip_sha256"], a["speech"]["flags"]), (self.sha, []))

    def test_the_build_fetches_a_reused_clip_only_from_the_cdn_and_by_its_sha256(self):
        approval = {"source": "pavo_reuse", "url": self.URL, "clip_sha256": hashlib.sha256(b"the clip").hexdigest()}
        dst = self.dir / "out" / "s-eve.mp4"
        self.assertEqual(ss.fetch_source(approval, dst, download=lambda url, d: Path(d).write_bytes(b"the clip")), dst)
        with self.assertRaises(SystemExit) as err:
            ss.fetch_source(approval, dst, download=lambda url, d: Path(d).write_bytes(b"another clip"))
        self.assertTrue(str(err.exception).startswith("SHOT_CLIP_SHA256_MISMATCH"))
        with self.assertRaises(SystemExit) as err:
            ss.fetch_source(dict(approval, url="https://example.com/x.mp4"), dst,
                            download=lambda url, d: self.fail("never downloaded"))
        self.assertEqual(str(err.exception), "REUSE_URL_REFUSED")


class SpeechChecks(unittest.TestCase):
    """R4 / story QA v4: each kept speech clip, measured; a missing measure never passes."""
    LINE = "Who told thee that thou wast naked"
    BIND = {"reference": "r", "others": ["a", "k"]}   # voices.json's references (pavo_native.voice_binding)

    def good(self):
        return {"asr": {"model_bin_sha256": V4["speech"]["asr_model"]["model_bin_sha256"], "text": self.LINE + "?",
                        "speech_span": [1.2, 4.0]},
                "voice": {"reference": "r", "same": 0.93, "others": [0.72, 0.64], "others_references": ["k", "a"]},
                "lufs": -24.0, "music": 0.0,
                "singing": 0.0, "lips": []}

    def test_a_clean_clip_passes_and_each_defect_fails(self):
        self.assertEqual(pn.speech_verdict(self.good(), self.LINE, V4, self.BIND), [])
        cases = {"SPEECH_WORDS_NOT_EXACT": ("asr", {"text": "Who told thee that thou was naked"}),
                 "ASR_MODEL_NOT_PINNED": ("asr", {"model_bin_sha256": "base.en"}),
                 "VOICE_REFERENCE_MISSING": ("voice", {"reference": None}),
                 "VOICE_NOT_CONSISTENT": ("voice", {"same": 0.85}),
                 "VOICE_NOT_DISTINCT": ("voice", {"same": 0.893, "others": [0.878, 0.6]}),   # #473: Adam vs Keeper
                 "SPEECH_LEVEL_UNREACHABLE": ("lufs", -31.0), "PAVO_MUSIC": ("music", 0.2),
                 "PAVO_SINGING": ("singing", 0.1), "LIPS_NOT_CHECKED": ("lips", None)}
        for flag, (key, value) in cases.items():
            m = self.good()
            m[key] = dict(m[key], **value) if isinstance(value, dict) else value
            self.assertIn(flag, pn.speech_verdict(m, self.LINE, V4, self.BIND), flag)
        m = self.good()
        m["lips"] = ["MOUTH_NOT_IN_SYNC"]
        self.assertEqual(pn.speech_verdict(m, self.LINE, V4, self.BIND), ["MOUTH_NOT_IN_SYNC"])
        self.assertIn("VOICE_REFERENCE_MISSING", pn.speech_verdict(self.good(), self.LINE, V4))   # no binding

    def test_the_approval_record_holds_the_span_and_one_gain(self):
        rec = pn.speech_record("c", self.good(), self.LINE, V4, self.BIND)
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

    def test_a_short_fallback_is_made_at_the_shorts_frame(self):
        """E132: shot_sources rendered every still in motion at the long's 2560x1440 and offered the 16:9 library to a
        9:16 Short, so a Short's approved fallback would fail its own build (CLIP_ASPECT_MISMATCH). The frame is the
        plan's: 1080x1920 for a Short, 2560x1440 for a long; the library offers only clips at that frame."""
        short = dict(plan(), aspect_ratio="9:16")
        self.assertEqual(ss.plan_frame(short), (1080, 1920))
        self.assertEqual(ss.plan_frame({"aspect_ratio": "16:9"}), ss.FRAME)
        self.assertEqual(ss.plan_frame({}), (1080, 1920))   # a plan with no aspect is a Short (episode_build)
        lib = [clip("clip-river-a"), clip("clip-river-v", frame=[1080, 1920])]
        self.assertEqual([c["item"] for c in ss.footage_candidates(short, short["shots"][2], 2, lib)],
                         ["clip-river-v"])
        self.assertEqual([c["item"] for c in ss.footage_candidates(plan(), plan()["shots"][2], 2, lib)],
                         ["clip-river-a"])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as err:
                ss.approve_source(short, "s-river", "footage", "clip-river-a", 9.6, "x", lib=lib, shots_dir=d)
            self.assertTrue(str(err.exception).startswith("FOOTAGE_NOT_USABLE"))
        # a still in motion is approved with the Short's frame and the build's fetch renders it there
        # (episode_build.generate_step calls fetch_source with no frame: the approval carries it)
        import plan_check
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "still.jpg").write_bytes(b"jpeg")
            rec = {"id": "st-river", "episode": "t-sources", "shot": "s-river", "status": "APPROVED",
                   "repo_path": "still.jpg", "sha256": hashlib.sha256(b"jpeg").hexdigest()}
            keep = plan_check.still_record
            plan_check.still_record = lambda i: rec if i == "st-river" else None
            try:
                a = ss.approve_source(short, "s-river", "still_motion", "st-river", 9.6, "x", shots_dir=d)
            finally:
                plan_check.still_record = keep
            self.assertEqual(a["frame"], [1080, 1920])
            seen = {}
            keep_repo, keep_clip = ss.REPO, ss.still_motion_clip
            ss.REPO = d
            ss.still_motion_clip = lambda s, o, sec, frame=ss.FRAME: seen.update(frame=frame) or o
            try:
                ss.fetch_source(dict(a, clip_seconds=1.0), d / "out.mp4")
            finally:
                ss.REPO, ss.still_motion_clip = keep_repo, keep_clip
            self.assertEqual(seen["frame"], (1080, 1920))

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg")
    def test_a_shorts_still_in_motion_is_vertical(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=108x192:d=1", "-frames:v", "1",
                            str(d / "still.jpg")], check=True)
            ss.still_motion_clip(d / "still.jpg", d / "out.mp4", 1.0, frame=ss.plan_frame({"aspect_ratio": "9:16"}))
            info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json",
                                              str(d / "out.mp4")], capture_output=True, text=True).stdout)
            v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
            self.assertEqual((v["width"], v["height"]), (1080, 1920))

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
