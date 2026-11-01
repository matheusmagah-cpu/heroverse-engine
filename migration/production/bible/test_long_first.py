#!/usr/bin/env python3
"""Offline checks of the long-first route (E259, owner 2026-11-01): the 16:9 buzzy-long plan track and its centre 9:16
safe area, the 1920x1080 compose with its caption-free master, the defect-gated long through long_review /
prepublish_gate / publication_binding, the Short cuts (refused inside speech, outside 20-179 s, off sentence edges)
rendered for real from a tiny clean master, their records under publish_episode, and every other track unchanged."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration/publish"))
sys.path.insert(0, str(ROOT / "migration/production"))
import buzzy_long as bl  # noqa: E402
import compilation_long as cl  # noqa: E402
import episode_build as eb  # noqa: E402
import long_review as lr  # noqa: E402
import native_review as nr  # noqa: E402
import owner_quality_policy as oq  # noqa: E402
import plan_check as pc  # noqa: E402
import prepublish_gate as pg  # noqa: E402
import publication_binding as pb  # noqa: E402
import publish_episode as pe  # noqa: E402
import short_cuts as sc  # noqa: E402
import short_engine as se  # noqa: E402

FFMPEG = shutil.which("ffmpeg") is not None
SHORT_PLAN = HERE / "plans/genesis-09-short.json"
SHA = "a" * 64
CLEAN = "c" * 64


def ff(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args], check=True)


def long_plan():
    plan = json.loads(SHORT_PLAN.read_text())
    plan.update(track="buzzy-long", aspect_ratio="16:9", episode="genesis-long-test")
    for s in plan["shots"]:
        s["prompt"] = s.get("prompt", "") + " The subject is centred in the frame."
    ids = [s["id"] for s in plan["shots"]]
    plan["long"] = {"pilot": "pilot-099", "title": "The Flood, the whole story (KJV)", "tags": ["noah"],
                    "description": "Genesis 7 (public domain KJV), AI visuals.\n{chapters}", "first_comment": "Part one.",
                    "chapters": [{"shot": ids[0], "title": "Seven days"}, {"shot": ids[2], "title": "The door"},
                                 {"shot": ids[4], "title": "The rain"}],
                    "thumbnail": {"at": 1.0, "line1": "THE FLOOD", "line2": "Genesis 7"}}
    return plan


SENTENCES = [  # the long's sentence timeline, as episode_build.compose_step keeps it for a long-first long
    {"segment": "n00", "line": 0, "line_kind": "scripture", "kind": "scripture", "reference": "Genesis 7:4 (KJV)",
     "text": "For yet seven days, and I will cause it to rain.", "start": 0.5, "end": 4.0},
    {"segment": "n01", "line": 1, "line_kind": "story", "text": "Noah heard it and went on building.", "start": 4.35, "end": 9.0},
    {"segment": "n01", "line": 1, "line_kind": "story", "text": "His sons carried the beams.", "start": 9.0, "end": 12.0},
    {"segment": "n02", "line": 2, "line_kind": "insight", "text": "Obedience here is slow work done before the rain, "
     "when nobody else believes it, and that is the point the story keeps making to us.", "start": 12.35, "end": 22.0},
    {"segment": "n03", "line": 3, "line_kind": "story", "text": "Then the rain came.", "start": 22.35, "end": 24.0}]


def report(episode="genesis-long-test", sha=SHA, sentences=SENTENCES, seconds=25.0):
    return {"episode": episode, "composed": {
        "output_sha256": sha, "seconds": seconds, "frame": [1920, 1080], "run_id": "1",
        "clean": {"output_sha256": CLEAN, "seconds": seconds, "release_asset": bl.clean_asset(episode, CLEAN)},
        "sentences": sentences,
        "timeline": [{"shot": s["id"], "kind": "scene", "start": float(i * 2), "end": float(i * 2 + 2), "src_start": 0.0,
                      "speed": 1.0} for i, s in enumerate(json.loads(SHORT_PLAN.read_text())["shots"])]}}


def review_doc(**kw):
    base = {"model": "claude-session-reviewer", "output_sha256": SHA, "overall": 7.0,
            "issues": ["00:10 [info] soft hand", "00:20 [b] fixed by retime"],
            "defects": [{"issue": 0, "category": "info", "resolved": False}, {"issue": 1, "category": "b", "resolved": True}],
            "publish_decision": {"decision": "publish", "by": "claude-session-reviewer", "note": "watched and heard it"},
            "evidence": ["watched the master", "listened to every join"]}
    base.update(kw)
    return base


class PlanTrack(unittest.TestCase):
    def test_long_first_is_16_9_and_keeps_the_centre_safe_area(self):
        plan = long_plan()
        problems = pc.check(plan)["problems"]
        self.assertFalse([p for p in problems if p.startswith("ASPECT_RATIO") or p.startswith("SAFE_AREA")], problems)
        wrong = dict(plan, aspect_ratio="9:16")
        self.assertIn("ASPECT_RATIO (a long-first plan, track buzzy-long, is 16:9)", pc.check(wrong)["problems"])
        bare = copy.deepcopy(plan)
        bare["shots"][1]["prompt"] = bare["shots"][1]["prompt"].replace(" The subject is centred in the frame.", "")
        self.assertTrue(any(p.startswith("SAFE_AREA_UNSTATED shot 1") for p in pc.check(bare)["problems"]))
        off = copy.deepcopy(plan)
        off["shots"][2]["prompt"] += " Noah stands at the far left edge, rule of thirds."
        self.assertTrue(any(p.startswith("SAFE_AREA_OFF_CENTRE shot 2") for p in pc.check(off)["problems"]))
        self.assertTrue(any(p.startswith("SAFE_AREA_UNSTATED") for p in
                            pc.still_prompt_problems("s-x/st-1", "A wide view of the ark at dusk.", plan)))

    def test_other_tracks_are_unchanged(self):
        short = json.loads(SHORT_PLAN.read_text())
        self.assertEqual(pc.check(short)["problems"], [])
        self.assertIn("ASPECT_RATIO (Shorts are 9:16)", pc.check(dict(short, aspect_ratio="16:9"))["problems"])
        self.assertEqual(pc.RATIOS, ("9:16",))
        self.assertFalse(any(p.startswith("SAFE_AREA") for p in pc.check(short)["problems"]))
        # the Short's caption style and frame are the ones it always had
        self.assertEqual((se.W, se.H, se.CAPTION_WORDS, se.FONT_SIZE, se.MARGIN_V), (1080, 1920, 2, 132, 560))
        head = se.build_ass([{"text": "one two three", "start": 0.0, "end": 1.0}])
        self.assertIn("PlayResX: 1080\nPlayResY: 1920", head)
        self.assertIn("Style: Cap,DejaVu Sans,132,", head)
        self.assertIn(",0,0,0,,one two\n", head)
        # the long gates: the 9.5 floor still refuses on every story long, the defect tracks are only these two
        self.assertNotIn(pg.BUZZY_LONG, pg.STANDARD_VERSIONS)
        self.assertIn(pg.STORY_V5, pg.STANDARD_VERSIONS)
        self.assertEqual(set(pg.DEFECT_TRACKS), {pg.COMPILATION, pg.BUZZY_LONG})
        self.assertTrue(oq.check({"status": "PASS", "model": "claude-session-reviewer", "overall": 9.4,
                                  "output_sha256": SHA}, SHA, oq.LONG_REVIEWERS))
        # the Short publisher: the default track keeps 9.5, the buzzy track its own Buzzy shot and decision
        rec = {"id": "genesis-09-short", "output_sha256": SHA, "track": None,
               "review": {"overall": 9.4, "reviewer": "gemini-3.8-flash", "output_sha256": SHA, "issues": []}}
        self.assertIn("REVIEW_BELOW_FLOOR", pe.review_problems(rec))
        self.assertIn("TRACK_UNKNOWN", pe.review_problems(dict(rec, track="buzzy-long")))
        self.assertEqual(pe.short_length(9), (170.0, 179.0))
        with tempfile.TemporaryDirectory() as t:   # a plan with no track keeps the native review's 9.5
            plain = Path(t) / "plain.json"
            plain.write_text(json.dumps({k: v for k, v in short.items() if k != "track"}))
            self.assertEqual(nr.floor_for(plain), 9.5)

    def test_long_first_length_replaces_the_short_band(self):
        n = len(pc.sequence(long_plan())[0])

        def layout(total):   # every line laid end to end over `total` seconds
            step = total / n
            return [(round(k * step, 3), round((k + 1) * step - 0.35, 3)) for k in range(n)]

        def codes(plan, total):
            return [p.split()[0] for p in eb.plan_layout(plan, layout(total))["problems"]]
        self.assertIn("LONG_FIRST_LENGTH", codes(long_plan(), 175.0))
        self.assertNotIn("LONG_FIRST_LENGTH", codes(long_plan(), 600.0))
        self.assertNotIn("SHORT_LENGTH", codes(long_plan(), 175.0))
        short = json.loads(SHORT_PLAN.read_text())
        self.assertIn("SHORT_LENGTH", codes(short, 600.0))
        self.assertNotIn("LONG_FIRST_LENGTH", codes(short, 600.0))


@unittest.skipUnless(FFMPEG, "ffmpeg")
class Compose(unittest.TestCase):
    def test_long_first_compose_is_1920x1080_with_a_caption_free_master(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            ff("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-t", "3", "-pix_fmt", "yuv420p", t / "clip.mp4")
            ff("-f", "lavfi", "-i", "sine=frequency=300:sample_rate=24000", "-t", "2", t / "voice.wav")
            ff("-f", "lavfi", "-i", "sine=frequency=500:sample_rate=48000", "-t", "5", t / "music.flac")
            (t / "timeline.json").write_text(json.dumps({"voice_seconds": 2.0, "sentences": [
                {"text": "In the beginning God created", "start": 0.1, "end": 1.9}]}))
            plan = {"voice": str(t / "voice.wav"), "timeline": str(t / "timeline.json"), "music": str(t / "music.flac"),
                    "tail": 1.0, "shots": [{"clip": str(t / "clip.mp4"), "start": 0.0, "end": 3.0, "src_start": 0.0}],
                    "frame": [1920, 1080], "clean_out": str(t / "clean.mp4")}
            (t / "plan.json").write_text(json.dumps(plan))
            se.main(str(t / "plan.json"), str(t / "out.mp4"))
            for f in ("out.mp4", "clean.mp4"):
                p = sc.short_engine_probe(t / f)
                self.assertEqual(p, (1920, 1080), f)
            self.assertNotEqual(cl.sha256(t / "out.mp4"), cl.sha256(t / "clean.mp4"))
            ass = se.build_ass([{"text": "one two three four five", "start": 0.0, "end": 1.0}], se.caption_style(1920, 1080))
            self.assertIn("PlayResX: 1920\nPlayResY: 1080", ass)
            self.assertIn(",0,0,0,,one two three four\n", ass)
            (t / "plan.json").write_text(json.dumps(dict(plan, frame=[1280, 720])))
            with self.assertRaisesRegex(SystemExit, "FRAME_REFUSED"):
                se.main(str(t / "plan.json"), str(t / "x.mp4"))


class LongGate(unittest.TestCase):
    def test_report_and_publication_fields(self):
        plan = long_plan()
        self.assertEqual(bl.publication_problems(plan), [])
        self.assertEqual(bl.report_problems(plan, report(), SHA), [])
        self.assertIn("report not for this file", bl.report_problems(plan, report(), "b" * 64))
        r = report()
        r["composed"]["clean"]["release_asset"] = "elsewhere.mp4"
        self.assertIn("caption-free master missing from the report or the release", bl.report_problems(plan, r))
        bad = copy.deepcopy(plan)
        bad["long"]["chapters"][1], bad["long"]["chapters"][2] = bad["long"]["chapters"][2], bad["long"]["chapters"][1]
        self.assertIn("chapters name shots of the plan, in order, once each", bl.publication_problems(bad))
        self.assertEqual(bl.chapters(plan, report())[:2], [(0, "Seven days"), (4.0, "The door")])

    def pilot(self, root, review=None):
        d = Path(root) / "pilot-099"
        (d / "out").mkdir(parents=True)
        (d / "inspection").mkdir()
        (d / "script.json").write_text(json.dumps({"pilot_id": "pilot-099", "archetype": pg.BUZZY_LONG_ARCHETYPE}))
        (d / "out/manifest.json").write_text(json.dumps({"output_sha256": SHA, "output_seconds": 600}))
        if review is not None:
            (d / "inspection/claude_review.json").write_text(json.dumps(review))
        return d

    def test_long_review_and_the_gate_use_the_defect_track(self):
        with tempfile.TemporaryDirectory() as t:
            d = self.pilot(t)
            lr.main(str(d))
            self.assertEqual(json.loads((d / "out/review.json").read_text())["status"], "AWAITING_REVIEW")
            d = self.pilot(t + "/x", review_doc())
            lr.main(str(d))
            r = json.loads((d / "out/review.json").read_text())
            self.assertEqual((r["status"], r["track"]), ("PASS", "buzzy-long"))
            checks = {k: True for k in sum(pg.BUZZY_LONG_DIMENSIONS.values(), [])}
            qa = {"output_sha256": SHA, "criteria_version": pg.BUZZY_LONG, "status": "PASS", "checks": checks,
                  "criteria_sha256": pg.FROZEN_CRITERIA_SHA256[pg.BUZZY_LONG]}
            (d / "out/qa.json").write_text(json.dumps(qa))
            (d / "out/scan.json").write_text(json.dumps({"status": "PASS", "rows": {"black": {"pass": True, "longest_s": 0, "blocking": True}}}))
            gate = pg.evaluate(d, None, [])
            self.assertEqual(gate["dimensions"]["defect_review"], "PASS")
            self.assertEqual(gate["dimensions"]["structure"], "PASS")
            self.assertEqual(gate["decision"], "PASS", gate["dimensions"])
            approval = {"approved": True, "output_sha256": SHA}
            self.assertEqual(pb.check(qa, approval, {"output_sha256": SHA}, gate, r), [])
            # a compilation review track on a long-first pilot, or the 9.5 track's qa, never passes this way
            wrong = dict(r, track="compilation")
            (d / "out/review.json").write_text(json.dumps(wrong))
            self.assertEqual(pg.evaluate(d, None, [])["dimensions"]["format"], "FAIL")
            unresolved = copy.deepcopy(r)
            unresolved["watched_review"]["defects"][0] = {"issue": 0, "category": "a", "resolved": False}
            (d / "out/review.json").write_text(json.dumps(unresolved))
            self.assertEqual(pg.evaluate(d, None, [])["dimensions"]["defect_review"], "FAIL")

    def test_the_upload_applies_the_defect_gate_only_to_this_track(self):
        import publish_video as pv
        with tempfile.TemporaryDirectory() as t:
            video = Path(t) / "v.mp4"
            video.write_bytes(b"master")
            sha = cl.sha256(video)
            (Path(t) / "review.json").write_text(json.dumps({"status": "PASS", "output_sha256": sha, "track": "buzzy-long",
                                                            "watched_review": review_doc(output_sha256=sha)}))
            pv.check_new_upload(Path(t) / "manifest.json", {"output_sha256": sha}, video)
            (Path(t) / "review.json").write_text(json.dumps({"status": "PASS", "output_sha256": sha,
                                                            "watched_review": review_doc(output_sha256=sha)}))
            with self.assertRaisesRegex(SystemExit, "OWNER_QUALITY_POLICY_BLOCKED"):   # the 9.5 track: 7.0 is refused
                pv.check_new_upload(Path(t) / "manifest.json", {"output_sha256": sha}, video)

    def test_frozen_criteria_hash(self):
        self.assertEqual(pg.sha256_file(pg.CRITERIA_FILES[pg.BUZZY_LONG]), pg.FROZEN_CRITERIA_SHA256[pg.BUZZY_LONG])
        self.assertEqual(bl.CRITERIA, pg.BUZZY_LONG)
        rows = json.loads(bl.CRITERIA_FILE.read_text())["rows"]
        self.assertEqual(sorted(rows), sorted(sum(pg.BUZZY_LONG_DIMENSIONS.values(), [])))

    @unittest.skipUnless(FFMPEG, "ffmpeg")
    def test_materialize_and_verify(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            plan = long_plan()
            for rel in ("migration/production/bible/plans", "migration/evidence/episodes/genesis-long-test"):
                (root / rel).mkdir(parents=True)
            video = root / "long.mp4"
            ff("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30", "-f", "lavfi", "-i", "sine=frequency=400",
               "-t", "3", "-pix_fmt", "yuv420p", "-shortest", video)
            sha = cl.sha256(video)
            plan_path = root / "migration/production/bible/plans/genesis-long-test.json"
            plan_path.write_text(json.dumps(plan))
            rep = root / "migration/evidence/episodes/genesis-long-test/report-1.json"
            rep.write_text(json.dumps(report(sha=sha)))
            d = bl.materialize(plan_path, rep, video, root / "out", root=root, thumbs_dir=root / "thumbs")
            script = json.loads((d / "script.json").read_text())
            self.assertEqual((script["archetype"], d.name), (pg.BUZZY_LONG_ARCHETYPE, "pilot-099"))
            man = json.loads((d / "out/manifest.json").read_text())
            self.assertEqual(man["chapters"][0], [0, "Seven days"])
            self.assertEqual(man["clean_master"]["output_sha256"], CLEAN)
            self.assertIn("0:04 The door", json.loads((d / "out/package.json").read_text())["description"])
            self.assertEqual(bl.verify(d, video, root=root)["output_sha256"], sha)
            rep.write_text(json.dumps(report(sha=sha, seconds=26.0)))
            with self.assertRaisesRegex(SystemExit, "build_report changed"):
                bl.verify(d, video, root=root)


def cut_root(t, cuts):
    root = Path(t)
    for rel in ("migration/production/bible/plans", "migration/evidence/episodes/genesis-long-test",
                "migration/production/bible/cuts", "migration/production/bible/episodes"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    (root / "migration/production/bible/plans/genesis-long-test.json").write_text(json.dumps(long_plan()))
    (root / "migration/evidence/episodes/genesis-long-test/report-1.json").write_text(json.dumps(report()))
    spec = {"version": "bible-cuts-v1", "track": "buzzy-cut", "long": "genesis-long-test", "pilot": "pilot-099",
            "report": "migration/evidence/episodes/genesis-long-test/report-1.json", "cuts": cuts}
    path = root / "migration/production/bible/cuts/genesis-long-test.json"
    path.write_text(json.dumps(spec))
    return root, spec, path


def cut(cid="genesis-07-cut-1", start=0.2, end=22.2, **kw):
    return {"id": cid, "start": start, "end": end, "title": "Seven days #shorts",
            "description": "Genesis 7 (public domain KJV), AI visuals. The full story: the long video.", **kw}


class Cuts(unittest.TestCase):
    def test_no_cut_speech_length_and_sentence_edges(self):
        with tempfile.TemporaryDirectory() as t:
            root, spec, _ = cut_root(t, [cut()])
            got = sc.check(spec, root)
            self.assertEqual(got["problems"], [])
            self.assertEqual((got["cuts"]["genesis-07-cut-1"]["first"], got["cuts"]["genesis-07-cut-1"]["last"]), (0, 3))
            self.assertEqual(got["cuts"]["genesis-07-cut-1"]["advice"], [])   # hook (KJV), beat, the Keeper's insight
            for c, code in ((cut(start=1.0), "CUT_STARTS_INSIDE_SPEECH"), (cut(end=20.0), "CUT_ENDS_INSIDE_SPEECH"),
                            (cut(start=4.2, end=22.2), "CUT_LENGTH"), (cut(start=0.2, end=10.5), "CUT_ENDS_INSIDE_SPEECH"),
                            (cut(x=1.5), "CUT_X"), (cut(cid="genesis-long-test"), "CUT_ID"),
                            (cut(title=""), "CUT_TITLE")):
                spec["cuts"] = [c]
                self.assertTrue(any(p.startswith(code) for p in sc.check(spec, root)["problems"]), (c, code))
            # the shortest coherent unit is still 20 s; a sentence-edge end in the silence after the insight passes
            spec["cuts"] = [cut(start=4.2, end=24.5)]
            self.assertEqual(sc.check(spec, root)["problems"], [])
            self.assertTrue(sc.check(spec, root)["cuts"]["genesis-07-cut-1"]["advice"])   # ends on a story line
            spec["cuts"] = [cut(end=200.0)]
            self.assertTrue(any(p.startswith("CUT_RANGE") for p in sc.check(spec, root)["problems"]))
            spec["track"] = "buzzy"
            self.assertTrue(sc.check(spec, root)["problems"][0].startswith("SPEC_VERSION"))

    @unittest.skipUnless(FFMPEG, "ffmpeg")
    def test_render_is_a_9_16_short_with_captions_gain_and_fades(self):
        with tempfile.TemporaryDirectory() as t:
            root, spec, path = cut_root(t, [cut(x=0.6)])
            clean = Path(t) / "clean.mp4"
            ff("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-f", "lavfi", "-i", "sine=frequency=300",
               "-t", "25", "-af", "volume=-20dB", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
               "-shortest", clean)
            rep = json.loads((root / spec["report"]).read_text())
            rep["composed"]["clean"].update(output_sha256=cl.sha256(clean),
                                            release_asset=bl.clean_asset("genesis-long-test", cl.sha256(clean)))
            (root / spec["report"]).write_text(json.dumps(rep))
            done = sc.render(path, clean, Path(t) / "out", root=root)
            rec = json.loads((Path(t) / "out/genesis-07-cut-1.json").read_text())
            self.assertTrue(all(rec["checks"].values()), rec["checks"])
            self.assertEqual(rec["frame"], [1080, 1920])
            self.assertAlmostEqual(rec["seconds"], 22.0, delta=0.2)
            self.assertEqual(done[0]["output_sha256"], cl.sha256(Path(t) / "out/genesis-07-cut-1.mp4"))
            self.assertEqual(rec["sentences"][0]["start"], 0.3)   # the long's 0.5 s, cut at 0.2 s
            with self.assertRaisesRegex(SystemExit, "CLEAN_MASTER_SHA256_MISMATCH"):
                sc.render(path, Path(t) / "out/genesis-07-cut-1.mp4", Path(t) / "out2", root=root)
            episode = sc.record(path, Path(t) / "out/genesis-07-cut-1.json", root=root)
            ep = json.loads(episode.read_text())
            self.assertEqual((ep["track"], ep["parent"]["long"], ep["parent"]["pilot"]), ("buzzy-cut", "genesis-long-test", "pilot-099"))
            self.assertEqual([x["kind"] for x in ep["narration"]], ["scripture", "story", "insight"])
            self.assertEqual(ep["narration"][1]["text"], "Noah heard it and went on building. His sons carried the beams.")
            self.assertNotIn("review", ep)   # never a copied score: its own native review and decision come next


class CutRecords(unittest.TestCase):
    def record(self, **kw):
        rec = {"id": "genesis-07-cut-1", "format": "short", "track": "buzzy-cut", "part": 9, "seconds": 45.0,
               "output_sha256": SHA, "title": "t", "description": "Genesis 7 (public domain), AI. The full story: link",
               "parent": {"long": "genesis-long-test", "pilot": "pilot-099", "clean_master_sha256": CLEAN},
               "narration": [{"kind": "scripture", "text": "For yet seven days"},
                             {"kind": "insight", "text": "our own words about obedience before the rain"}]}
        rec.update(kw)
        return rec

    def test_cut_track_rules(self):
        self.assertEqual(pe.short_problems(self.record()), [])
        self.assertIn("CUT_LENGTH 15.0 s (need 20-179)", pe.short_problems(self.record(seconds=15.0)))
        self.assertIn("CUT_LENGTH 180.0 s (need 20-179)", pe.short_problems(self.record(seconds=180.0)))
        self.assertTrue(any(p.startswith("CUT_PARENT_MISSING") for p in pe.short_problems(self.record(parent=None))))
        self.assertTrue(any(p.startswith("CUT_DESCRIPTION_NOT_TO_THE_LONG")
                            for p in pe.short_problems(self.record(description="Genesis 7 (public domain), AI."))))
        kjv_only = self.record(narration=[{"kind": "scripture", "text": "For yet seven days and I will cause it"}])
        self.assertTrue(any(p.startswith("ORIGINAL_SHARE") for p in pe.short_problems(kjv_only)))
        # its review is the defect gate on its own master, never the long's or a copied score
        with tempfile.TemporaryDirectory() as t:
            ledger = Path(t) / "ledger.json"
            ledger.write_text(json.dumps({"calls": [{"task_id": "task-1"}]}))
            (Path(t) / "genesis-long-test.json").write_text(json.dumps({"shots": {"s-1": {"source": "buzzy", "task_id": "task-1"}}}))
            review = {"reviewer": "claude-session-reviewer", "output_sha256": SHA, "issues": ["00:01 [info] soft"],
                      "defects": [{"issue": 0, "category": "info", "resolved": False}],
                      "publish_decision": {"decision": "publish", "by": "claude-session-reviewer", "note": "heard it whole"}}
            self.assertEqual(pe.review_problems(self.record(review=review), t, ledger), [])
            self.assertIn("REVIEW_NOT_FOR_THIS_FILE", pe.review_problems(self.record(review=dict(review, output_sha256="b" * 64)), t, ledger))
            cut_speech = dict(review, issues=["00:00 [a] first word clipped"], defects=[{"issue": 0, "category": "a", "resolved": False}])
            self.assertIn("REVIEW_DEFECT_UNRESOLVED", pe.review_problems(self.record(review=cut_speech), t, ledger))
            self.assertIn("TRACK_BUZZY_WITHOUT_BUZZY_SHOT", pe.review_problems(self.record(review=review), Path(t) / "none", ledger))

    def test_native_review_and_arc_links_know_the_cut(self):
        with tempfile.TemporaryDirectory() as t:
            spec = Path(t) / "spec.json"
            spec.write_text(json.dumps({"version": "bible-cuts-v1", "track": "buzzy-cut", "long": "x"}))
            self.assertEqual((nr.track_for(spec), nr.floor_for(spec)), ("buzzy-cut", 0.0))
            self.assertIn("[a] speech cut off", nr.prompt(45.0, "buzzy-cut"))
            self.assertIn("16:9", nr.prompt(600.0, "buzzy-long"))
            import arc_links
            eps = Path(t) / "episodes"
            eps.mkdir()
            (eps / "genesis-07-cut-1.json").write_text(json.dumps(self.record()))
            arcs = {"arcs": [{"id": "arc-x", "shorts": [], "long": {"pilot": "pilot-099"}}]}
            got = arc_links.resolve(arcs, {"entries": {}}, eps)
            self.assertEqual([s[0] for s in got[0]["shorts"]], ["genesis-07-cut-1"])


if __name__ == "__main__":
    unittest.main()
