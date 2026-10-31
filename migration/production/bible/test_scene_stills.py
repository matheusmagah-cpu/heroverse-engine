#!/usr/bin/env python3
"""Image first (owner, 27/10): a scene shot's `first_frame` / `last_frame` name APPROVED scene stills; plan_check and
episode_build.request refuse by the same function, the request digest carries each still's sha256, and the
registry is written only by scene-stills.yml (candidates) and `scene_stills.py approve`."""
import copy
import json
import re
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "migration" / "integrations" / "pavo"))
import episode_build as eb  # noqa: E402
import plan_check as pc  # noqa: E402
import scene_stills as ss  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / "characters"))
import props as pr  # noqa: E402

PLAN = json.loads((HERE / "plans" / "genesis-08-short.json").read_text())


def jpeg(path, size=(1080, 1920), colour=(90, 70, 50)):
    from PIL import Image
    Image.new("RGB", size, colour).save(path, "JPEG", quality=90)


class Stills(unittest.TestCase):
    def test_e215_critical_scene_details_are_explicit_inside_the_vertical_crop(self):
        # Static brief protection after inspecting run 40793104573. This does not grade generated pixels.
        required = {
            "genesis-09-short-s-noah-door": ("Only the back of his head is visible",
                                           "both ears and shoulders are symmetric",
                                           "uninterrupted opening reaches the floor",
                                           "walking on foot"),
            "genesis-09-s-rock": ("water surface crosses both shins",
                                  "feet and ankles lie entirely beneath opaque floodwater",
                                  "unbroken empty water"),
            "genesis-09-short-s-noah-lamp": ("clay oil lamp and its single flame are fully visible",
                                           "inside the central third",
                                           "warm light clearly reveals",
                                           "Only the back of his head is visible")}
        for sid, clauses in required.items():
            prompt = json.loads((HERE / "stills" / f"{sid}.json").read_text())["prompt"]
            for clause in clauses:
                with self.subTest(still=sid, clause=clause):
                    self.assertIn(clause, prompt)

    def setUp(self):
        # inside the repository (a still is a repository image), removed after each test
        self.dir = Path(tempfile.mkdtemp(prefix=".test-stills-", dir=HERE))
        self.saved = pc.STILLS_DIR
        pc.STILLS_DIR = self.dir
        self.plan = copy.deepcopy(PLAN)
        self.index = {s["id"]: i for i, s in enumerate(self.plan["shots"])}
        self.i = self.index["s-dust"]
        self.shot = self.plan["shots"][self.i]
        # the feature is tested on a copy: genesis-08's s-dust starts from its registered still here, whatever the
        # live plan uses (the 6 FLUX candidates were rejected on 27/10 and the shot went back to text)
        self.still = self.shot.setdefault("first_frame", "genesis-08-s-dust")
        real = json.loads((HERE / "stills" / f"{self.still}.json").read_text())
        ss.save(self.dir / f"{self.still}.json", real)
        # E122: s-dust names the ark, so its still is made with the ark's approved references; here an APPROVED ark
        # of the test's own (the committed one is DRAFT until Claude's review)
        self.saved_props = (pr.PROPS_FILE, pr.IMAGES_DIR)
        self.arkrefs = self.approved_ark()

    def approved_ark(self, status="APPROVED"):
        props = self.dir / "props.json"
        ss.save(props, {"props": {"ark": {"status": status, "views": ["side", "three-quarter"],
                                          "refs": ["side", "three-quarter"]}}})
        refs = []
        for k, view in enumerate(("side", "three-quarter")):
            img = self.dir / "refs" / f"pr-ark-{view}.jpg"
            img.parent.mkdir(parents=True, exist_ok=True)
            jpeg(img, size=(1600, 900), colour=(60 + k, 40, 20))
            ss.save(self.dir / "images" / f"pr-ark-{view}.json",
                    {"id": f"pr-ark-{view}", "repo_path": ss.rel(img), "sha256": ss.sha256(img),
                     "approved": {"note": "one box, flat square ends, no people (E125)"}})
            refs.append({"record": f"pr-ark-{view}", "repo_path": ss.rel(img), "sha256": ss.sha256(img)})
        pr.PROPS_FILE, pr.IMAGES_DIR = props, self.dir / "images"
        return refs

    def tearDown(self):
        pc.STILLS_DIR = self.saved
        pr.PROPS_FILE, pr.IMAGES_DIR = self.saved_props
        shutil.rmtree(self.dir)

    def proof(self, count=2, conversation="373466105375099584", status="completed"):
        """What the Pavo calls answered: pavo_generate_image (input_images) and the pavo_image_job read-back."""
        return {"generate": {"model": "agnes-image", "conversation_id": conversation, "input_images": count,
                             "quote": {"required_credits": 0.0, "is_estimate": False}},
                "job": {"conversation_id": conversation, "status": status}}

    def candidate(self, run="123", n=1, colour=(90, 70, 50), prompt=None, references=None, pavo=None):
        cid = f"{self.still}-{run}-{n}"
        img = self.dir / "candidates" / f"{cid}.jpg"
        img.parent.mkdir(parents=True, exist_ok=True)
        jpeg(img, colour=colour)
        rec = pc.still_record(self.still, self.dir)
        ss.save(img.with_suffix(".json"), {"id": cid, "still": self.still, "status": "DRAFT",
                                           "prompt": prompt or rec["prompt"], "size": list(ss.SIDE),
                                           "repo_path": ss.rel(img), "sha256": ss.sha256(img),
                                           "references": self.arkrefs if references is None else references,
                                           "pavo": self.proof() if pavo is None else pavo})
        return cid

    def approve(self, cid, score=9.6):
        return ss.approve(self.still, cid, score, "the ark box-shaped, the dust soft, no stray prop",
                          stills_dir=self.dir, today="2026-10-27", reviewer="claude-session-reviewer")

    def codes(self, shot=None):
        return [p.split()[0] for p in pc.frame_problems(self.i, shot or self.shot, self.plan)]

    def test_e149_still_identity_is_explicit_truthful_and_consumed(self):
        cid = self.candidate()
        before = (self.dir / f"{self.still}.json").read_bytes()
        for model in (None, "", "unknown-session", "gemini-3.8-flash"):
            with self.assertRaisesRegex(SystemExit, "REVIEWER_IDENTITY_REFUSED"):
                ss.approve(self.still, cid, 9.6, "reviewed fixture", stills_dir=self.dir, reviewer=model)
            self.assertEqual((self.dir / f"{self.still}.json").read_bytes(), before)
            self.assertFalse((self.dir / f"{self.still}.jpg").exists())
        rec = ss.approve(self.still, cid, 9.6, "reviewed fixture", stills_dir=self.dir,
                         reviewer="gpt-6-astra-session-reviewer")
        self.assertEqual(rec["approved"]["model"], "gpt-6-astra-session-reviewer")
        self.assertEqual(rec["approved"]["by"], rec["approved"]["model"])
        self.assertEqual(self.codes(), [])
        rec["approved"]["model"] = "not-the-reviewer"
        ss.save(self.dir / f"{self.still}.json", rec)
        self.assertIn("STILL_NOT_APPROVED", self.codes())
        del rec["approved"]["model"]
        ss.save(self.dir / f"{self.still}.json", rec)
        self.assertEqual(self.codes(), [])  # historical attribution stays untouched, not relabelled as GPT

    def test_genesis_08s_registered_stills_obey_the_rules_and_the_live_plan_starts_from_none(self):
        # 27/10: the six FLUX candidates for s-dust, s-ridge and s-board were rejected at review and the shots went
        # back to their canonical-ark text; the three still records stay registered (DRAFT) and keep obeying the rules
        for sid in ("s-dust", "s-ridge", "s-board"):
            rec = pc.still_record(f"genesis-08-{sid}", HERE / "stills")
            self.assertEqual((rec["episode"], rec["shot"]), ("genesis-08-short", sid))
            self.assertEqual(pc.still_prompt_problems(sid, rec["prompt"], PLAN), [])
            for sentence in (pc.ARK_LOOK, pc.ARK_EXCLUDE, pc.PERIOD_SETTING, pc.PERIOD_EXCLUDE):
                self.assertIn(sentence, rec["prompt"])
        self.assertEqual([s["id"] for s in PLAN["shots"] if "first_frame" in s], [])
        pc.STILLS_DIR = self.saved   # the registry as committed
        self.assertEqual([p for p in pc.check(PLAN)["problems"] if "STILL" in p.split()[0]], [])

    def test_a_draft_or_missing_still_is_refused_by_plan_check_and_the_request_alike(self):
        self.assertEqual(self.codes(), ["STILL_NOT_APPROVED"])
        with self.assertRaises(SystemExit) as err:
            eb.request(self.shot, self.i, self.plan, {}, {})
        self.assertTrue(str(err.exception).startswith("STILL_NOT_APPROVED s-dust"))
        gone = dict(self.shot, first_frame="genesis-08-nothing")
        self.assertEqual(self.codes(gone), ["STILL_MISSING"])
        self.assertIn("STILL_NOT_APPROVED", [p.split()[0] for p in pc.check(self.plan)["problems"]])

    def test_frames_go_only_on_a_scene_without_references_or_audio(self):
        self.assertIn("FRAMES_WITH_REFERENCES", self.codes(dict(self.shot, characters=["noah"])))
        self.assertIn("FRAMES_WITH_AUDIO", self.codes(dict(self.shot, speaker="noah", line="Come in.",
                                                           characters=["noah"])))
        keeper = next(s for s in self.plan["shots"] if s["kind"] == "keeper")
        self.assertIn("FRAMES_NOT_SCENE", self.codes(dict(keeper, first_frame=self.still)))
        last_only = {k: v for k, v in self.shot.items() if k != "first_frame"}
        self.assertIn("FRAME_LAST_WITHOUT_FIRST", self.codes(dict(last_only, last_frame=self.still)))
        self.assertIn("FRAME_FIELD_INVALID", self.codes(dict(self.shot, first_frame="../x")))
        # the Pavo adapter refuses the same pair (frames and references exclusive)
        from client import PavoError
        import images
        with self.assertRaises(PavoError):
            images.plan("a.jpg", "", ["b.jpg"])

    def test_the_still_prompt_obeys_the_period_and_the_ark(self):
        rec = pc.still_record(self.still, self.dir)
        for bad in (rec["prompt"].replace(pc.ARK_LOOK, "The ark is a great ship."),
                    rec["prompt"].replace(pc.PERIOD_SETTING, ""),
                    rec["prompt"] + " An old scroll lies open."):
            ss.save(self.dir / f"{self.still}.json", dict(rec, prompt=bad))
            self.assertIn("STILL_PROMPT_REFUSED", self.codes())
            with self.assertRaises(SystemExit) as err:
                ss.prepare(self.plan, ["s-dust"], 2, "123", stills_dir=self.dir)
            self.assertIn("STILL_PROMPT_REFUSED", str(err.exception))

    def test_prepare_makes_the_candidates_from_the_record_prompt(self):
        spec = ss.prepare(self.plan, ["s-dust"], 2, "123", stills_dir=self.dir, engine="pavo")
        self.assertEqual([x["id"] for x in spec["images"]], [f"{self.still}-123-1", f"{self.still}-123-2"])
        self.assertEqual(spec["images"][0]["prompt"], pc.still_record(self.still, self.dir)["prompt"])
        self.assertIn("vertical", spec["style"])
        for bad in ((["s-axe"], 2), (["s-dust"], 4), (["nope"], 1)):
            with self.assertRaises(SystemExit):
                ss.prepare(self.plan, bad[0], bad[1], "123", stills_dir=self.dir)

    def test_approve_records_the_hash_and_the_request_digest_changes_with_the_still(self):
        with self.assertRaises(SystemExit) as err:
            self.approve(self.candidate(), score=9.4)
        self.assertIn("STILL_SCORE_BELOW_FLOOR", str(err.exception))
        cid = self.candidate()
        rec = self.approve(cid)
        self.assertEqual(rec["status"], "APPROVED")
        self.assertEqual(rec["sha256"], ss.sha256(self.dir / f"{self.still}.jpg"))
        self.assertEqual(self.codes(), [])
        req = eb.request(self.shot, self.i, self.plan, {}, {})
        self.assertEqual(req["first_frame"], rec["repo_path"])
        self.assertIsNone(req["references"])
        self.assertIsNone(req["audios"])
        self.assertEqual(eb.request_problems(dict(self.plan, shots=[self.shot]), {}, {}), [])   # the adapter's checks
        sha, canonical = eb.request_identity(self.shot, self.i, self.plan, {}, {})
        self.assertEqual(canonical["frames"], [{"still": self.still, "sha256": rec["sha256"]}])
        # another candidate approved: a changed still is another request (SHOT_REQUEST_CHANGED)
        rec2 = self.approve(self.candidate(n=2, colour=(10, 120, 200)))
        self.assertNotEqual(rec2["sha256"], rec["sha256"])
        sha2 = eb.request_identity(self.shot, self.i, self.plan, {}, {})[0]
        self.assertNotEqual(sha, sha2)
        approvals = {"s-dust": {"request_sha256": sha}}
        self.assertTrue(any(p.startswith("SHOT_REQUEST_CHANGED s-dust") for p in
                            eb.review_problems({"shots": [self.shot]}, {"s-dust": sha2}, approvals)))
        # a shot without frames digests exactly as before (the adopted clips keep their approvals)
        other = self.plan["shots"][self.index["s-axe"]]
        self.assertNotIn("frames", eb.request_identity(other, self.index["s-axe"], self.plan, {}, {})[1])

    def test_e148_nonfinite_review_scores_never_write_an_approval(self):
        cid = self.candidate()
        record = self.dir / f"{self.still}.json"
        before = record.read_bytes()
        for score in (float("nan"), float("inf"), -float("inf"), 9.49):
            with self.subTest(score=score), self.assertRaisesRegex(SystemExit, "STILL_SCORE_BELOW_FLOOR"):
                self.approve(cid, score=score)
            self.assertEqual(record.read_bytes(), before)
            self.assertFalse((self.dir / f"{self.still}.jpg").exists())

    def test_an_approved_still_edited_by_hand_is_refused(self):
        rec = self.approve(self.candidate())
        jpeg(self.dir / f"{self.still}.jpg", colour=(1, 2, 3))
        self.assertEqual(self.codes(), ["STILL_SHA256_MISMATCH"])
        jpeg(self.dir / f"{self.still}.jpg")
        ss.save(self.dir / f"{self.still}.json", dict(rec, sha256=ss.sha256(self.dir / f"{self.still}.jpg"),
                                                      prompt=rec["prompt"] + " Dusk."))
        self.assertIn("STILL_PROMPT_CHANGED", self.codes())
        cid = self.candidate(n=3)
        meta = json.loads((self.dir / "candidates" / f"{cid}.json").read_text())
        ss.save(self.dir / "candidates" / f"{cid}.json", dict(meta, sha256="0" * 64))
        with self.assertRaises(SystemExit) as err:
            self.approve(cid)
        self.assertIn("STILL_CANDIDATE_SHA256_MISMATCH", str(err.exception))

    def test_a_square_still_is_refused(self):
        rec = self.approve(self.candidate())
        jpeg(self.dir / f"{self.still}.jpg", size=(1024, 1024))
        ss.save(self.dir / f"{self.still}.json", dict(rec, sha256=ss.sha256(self.dir / f"{self.still}.jpg")))
        self.assertEqual(self.codes(), ["STILL_ASPECT_MISMATCH"])

    def test_crop_finalize_and_sheet(self):
        from PIL import Image
        img = self.dir / "img"
        img.mkdir()
        Image.new("RGB", (1024, 1024), (200, 100, 50)).save(img / f"{self.still}-77-1.png")
        (img / f"{self.still}-77-1.json").write_text(json.dumps({"prompt": "x", "engine": "flux",
                                                                 "references": self.arkrefs,
                                                                 "pavo": self.proof()}))
        ss.crop(img)
        with Image.open(img / f"{self.still}-77-1.png") as im:
            self.assertEqual(im.size, (576, 1024))
        self.assertEqual(ss.finalize(img, "77", stills_dir=self.dir), [f"{self.still}-77-1"])
        meta = json.loads((self.dir / "candidates" / f"{self.still}-77-1.json").read_text())
        self.assertEqual((meta["status"], meta["size"]), ("DRAFT", [1080, 1920]))
        self.assertEqual(meta["sha256"], ss.sha256(self.dir / "candidates" / f"{self.still}-77-1.jpg"))
        self.assertEqual(meta["source"], "cf-flux")
        # Pavo's Agnes Image 2.5 Flash: a native 9:16 JPEG with its source, quote and job in the sidecar
        Image.new("RGB", (1472, 2624), (90, 80, 70)).save(img / f"{self.still}-77-2.jpg", "JPEG")
        (img / f"{self.still}-77-2.json").write_text(json.dumps({
            "prompt": "x", "engine": "pavo", "source": "pavo-agnes-image-2.5-flash", "conversation_id": "9",
            "quote": {"required_credits": 0, "final_points": 0, "is_estimate": False},
            "upscaler": "none (native 1472x2624), Lanczos to 1080x1920", "references": self.arkrefs,
            "pavo": self.proof()}))
        self.assertEqual(ss.finalize(img, "77", stills_dir=self.dir), [f"{self.still}-77-1", f"{self.still}-77-2"])
        pavo = json.loads((self.dir / "candidates" / f"{self.still}-77-2.json").read_text())
        self.assertEqual((pavo["source"], pavo["size"], pavo["status"], pavo["quote"]["required_credits"]),
                         ("pavo-agnes-image-2.5-flash", [1080, 1920], "DRAFT", 0))
        with Image.open(self.dir / "candidates" / f"{self.still}-77-2.jpg") as im:
            self.assertEqual(im.size, (1080, 1920))
        out = self.dir / "sheet.jpg"
        self.assertEqual(ss.sheet("77", out, stills_dir=self.dir), [f"{self.still}-77-1", f"{self.still}-77-2"])
        self.assertTrue(out.is_file())

    def test_a_still_naming_the_ark_is_made_only_with_the_arks_approved_reference_images(self):
        # E122: genesis-09's 64 Pavo stills carried ARK_LOOK and ARK_EXCLUDE word for word and still drew a tower at
        # one end, a gabled barn or a ship's bow: text alone does not hold a prop. Like a character's face, the ark
        # is held by its approved reference images, sent by sha256 with every still that names it.
        prompt = pc.still_record(self.still, self.dir)["prompt"]
        self.assertEqual(pc.prop_references("A camp of goat-hair tents at dusk.")[1], [])
        need, missing = pc.prop_references(prompt)
        self.assertEqual((need, missing), (self.arkrefs, []))
        # E113's flood sentence alone named the ark (and Pavo drew it: 2026102704's carry, climb, feet); E123's names
        # none, so a still that does not show the ark needs no reference; the phrase alone is the ark
        self.assertEqual(pc.prop_references(pc.PERIOD_SETTING_FLOOD_E113)[0], self.arkrefs)
        self.assertEqual(pc.prop_references(pc.PERIODS["the-flood"]["setting"]), ([], []))
        self.assertEqual(pc.prop_references("Wide shot. " + pc.ARK_PHRASE[:1].upper() + pc.ARK_PHRASE[1:] + " sits "
                                            "level in the floodwater.")[0], self.arkrefs)
        # prepare hands the references (repository paths Pavo takes) with every candidate
        spec = ss.prepare(self.plan, ["s-dust"], 1, "123", stills_dir=self.dir, engine="pavo")
        self.assertEqual(spec["images"][0]["references"], [r["repo_path"] for r in self.arkrefs])
        # a candidate made from text alone, or without one of the views, or with another image, is refused
        for refs in ([], self.arkrefs[:1], [dict(self.arkrefs[0], sha256="0" * 64), self.arkrefs[1]]):
            with self.assertRaises(SystemExit) as err:
                self.approve(self.candidate(n=4, references=refs))
            self.assertIn("STILL_PROP_UNREFERENCED", str(err.exception))
        from PIL import Image
        img = self.dir / "img"
        img.mkdir()
        Image.new("RGB", (1472, 2624), (90, 80, 70)).save(img / f"{self.still}-78-1.jpg", "JPEG")
        (img / f"{self.still}-78-1.json").write_text(json.dumps({"prompt": "x", "source": "pavo-agnes-image-2.5-flash"}))
        with self.assertRaises(SystemExit) as err:
            ss.finalize(img, "78", stills_dir=self.dir)
        self.assertIn("STILL_PROP_UNREFERENCED", str(err.exception))
        # an approved still whose record lost its references (or a hand-made record) is refused by plan_check and
        # the build alike
        rec = self.approve(self.candidate())
        self.assertEqual(self.codes(), [])
        ss.save(self.dir / f"{self.still}.json", dict(rec, references=[]))
        self.assertIn("STILL_PROP_UNREFERENCED", self.codes())
        with self.assertRaises(SystemExit) as err:
            eb.request(self.shot, self.i, self.plan, {}, {})
        self.assertTrue(str(err.exception).startswith("STILL_PROP_UNREFERENCED s-dust"))
        ss.save(self.dir / f"{self.still}.json", rec)
        # a reference image changed by hand is no reference
        jpeg(self.dir / "refs" / "pr-ark-side.jpg", size=(1600, 900), colour=(1, 1, 1))
        self.assertEqual(self.codes(), ["STILL_PROP_UNREFERENCED"])
        # while the ark is DRAFT (as committed until Claude's review) every still naming it is refused, even an
        # approved one made with the references
        self.approved_ark(status="DRAFT")
        self.assertEqual(self.codes(), ["STILL_PROP_UNREFERENCED"])
        with self.assertRaises(SystemExit) as err:
            ss.prepare(self.plan, ["s-dust"], 1, "123", stills_dir=self.dir, engine="pavo")
        self.assertIn("STILL_PROP_UNREFERENCED", str(err.exception))
        pr.PROPS_FILE, pr.IMAGES_DIR = self.saved_props
        self.assertEqual(pr.registry()["ark"]["status"] == "APPROVED", not pc.prop_references(prompt)[1])

    def test_references_are_proved_by_pavos_answer_and_bound_by_the_approval(self):
        # E122 (review of #462): a sidecar that only declares `references` proves nothing. The still carries Pavo's own
        # answer (generate: input_images; job: completed, same conversation), and the approval binds the references
        for bad in ({}, self.proof(count=0), self.proof(count=1), self.proof(status="running"),
                    dict(self.proof(), job={"conversation_id": "1", "status": "completed"}),
                    dict(self.proof(), generate=dict(self.proof()["generate"], model="gpt-image"))):
            with self.assertRaises(SystemExit) as err:
                self.approve(self.candidate(n=5, pavo=bad))
            self.assertIn("STILL_PROP_UNREFERENCED", str(err.exception))
        with self.assertRaises(SystemExit) as err:   # a reference sent twice is not the other view
            self.approve(self.candidate(n=5, references=[self.arkrefs[0], self.arkrefs[0]]))
        self.assertIn("STILL_PROP_UNREFERENCED", str(err.exception))
        rec = self.approve(self.candidate())
        self.assertEqual(rec["approved"]["references_sha256"], pc.reference_digest(self.arkrefs))
        self.assertEqual(rec["pavo"]["generate"]["input_images"], 2)
        self.assertEqual(self.codes(), [])
        # the proof removed by hand, or references swapped by hand after the approval, are refused
        ss.save(self.dir / f"{self.still}.json", dict(rec, pavo=None))
        self.assertEqual(self.codes(), ["STILL_PROP_UNREFERENCED"])
        ss.save(self.dir / f"{self.still}.json", dict(rec, references=list(reversed(self.arkrefs))))
        self.assertEqual(self.codes(), ["STILL_PROMPT_CHANGED"])
        # a still approved without references, references then added by hand: the approval never bound them
        approved = dict(rec["approved"])
        approved.pop("references_sha256")
        ss.save(self.dir / f"{self.still}.json", dict(rec, approved=approved))
        self.assertEqual(self.codes(), ["STILL_PROMPT_CHANGED"])

    def test_prepare_refuses_a_still_naming_the_ark_on_flux_before_any_image(self):
        # E122 (review of #462): cf_images.py (FLUX) sends no reference image; the refusal comes before the run, not
        # in finalize after the free allocation was spent
        with self.assertRaises(SystemExit) as err:
            ss.prepare(self.plan, ["s-dust"], 1, "123", stills_dir=self.dir)
        self.assertIn("STILL_PROP_UNREFERENCED", str(err.exception))
        self.assertIn("FLUX", str(err.exception))
        with self.assertRaises(SystemExit) as err:
            ss.prepare(self.plan, ["s-dust"], 1, "123", stills_dir=self.dir, engine="dalle")
        self.assertIn("STILL_ENGINE_INVALID", str(err.exception))
        self.assertEqual(ss.prepare(self.plan, ["s-dust"], 1, "123", stills_dir=self.dir, engine="pavo")["engine"], "pavo")
        # a still that names no prop still goes to FLUX
        rec = pc.still_record(self.still, self.dir)
        plain = rec["prompt"]
        for w in (" " + pc.ARK_LOOK, " " + pc.ARK_EXCLUDE, " Far off across the bare plain, seen side-on and small in "
                  "the frame, lies the half-built ark, a row of bare upright ribs along its top."):
            self.assertIn(w, plain)
            plain = plain.replace(w, "")
        ss.save(self.dir / f"{self.still}.json", dict(rec, prompt=plain))
        self.assertEqual(pc.prop_references(plain), ([], []))
        self.assertEqual(ss.prepare(self.plan, ["s-dust"], 1, "123", stills_dir=self.dir)["engine"], "flux")

    def test_the_build_lists_every_frame_refusal_plan_check_raises(self):
        src = (HERE / "plan_check.py").read_text()
        body = src[src.index("def frame_problems("):src.index("def frame_paths(")]
        raised = set(re.findall(r'f"([A-Z0-9_]+) shot', body))
        self.assertEqual(raised, set(eb.FRAME_REFUSALS))



class LongStills(unittest.TestCase):
    """LONG_DESIGN slice 3: the long's image-first shots get 16:9 stills (1920x1080) through the same prepare,
    crop, finalize, sheet and approve; a picture at the wrong aspect is refused, never stretched."""
    SHOT = "s-co-gate"

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix=".test-long-stills-", dir=HERE))
        self.saved = pc.STILLS_DIR
        pc.STILLS_DIR = self.dir
        self.plan = json.loads((HERE / "plans" / "arc-01-long.json").read_text())
        self.i, shot = next((i, s) for i, s in enumerate(self.plan["shots"]) if s["id"] == self.SHOT)
        self.still = f"arc-01-long-{self.SHOT}"
        shot["first_frame"] = self.still
        self.shot = shot
        ss.save(self.dir / f"{self.still}.json", {"id": self.still, "episode": "arc-01-long", "shot": self.SHOT,
                                                  "status": "DRAFT", "prompt": shot["prompt"]})

    def tearDown(self):
        pc.STILLS_DIR = self.saved
        shutil.rmtree(self.dir)

    def test_a_long_still_is_made_reviewed_and_approved_at_16x9(self):
        from PIL import Image
        spec = ss.prepare(self.plan, [self.SHOT], 2, "55", stills_dir=self.dir)
        self.assertEqual((spec["aspect_ratio"], spec["side"], spec["style"]), ("16:9", [1920, 1080], ss.STYLES["16:9"]))
        self.assertEqual(ss.prepare(self.plan, [self.SHOT], 1, "55", stills_dir=self.dir, engine="pavo")["aspect_ratio"],
                         "16:9")   # the Pavo agnes-image request's ratio (quoted 0 credits at 16:9)
        img = self.dir / "img"
        img.mkdir()
        Image.new("RGB", (1024, 1024), (200, 100, 50)).save(img / f"{self.still}-55-1.png")
        (img / f"{self.still}-55-1.json").write_text(json.dumps({"prompt": "x", "engine": "flux"}))
        ss.crop(img)
        with Image.open(img / f"{self.still}-55-1.png") as im:
            self.assertEqual(im.size, (1024, 576))       # the centre 16:9 band
        self.assertEqual(ss.finalize(img, "55", stills_dir=self.dir), [f"{self.still}-55-1"])
        cid = f"{self.still}-55-1"
        meta = json.loads((self.dir / "candidates" / f"{cid}.json").read_text())
        self.assertEqual((meta["size"], meta["aspect_ratio"]), ([1920, 1080], "16:9"))
        with Image.open(self.dir / "candidates" / f"{cid}.jpg") as im:
            self.assertEqual(im.size, (1920, 1080))
        out = self.dir / "sheet.jpg"
        self.assertEqual(ss.sheet("55", out, stills_dir=self.dir), [cid])
        with Image.open(out) as im:
            self.assertGreater(im.size[0], im.size[1] * 0.9)   # 640x360 cells
        rec = ss.approve(self.still, cid, 9.6, "the sword's fire soft, the gate dark, no figure", stills_dir=self.dir,
                         today="2026-10-27", reviewer="claude-session-reviewer")
        self.assertEqual((rec["status"], rec["size"]), ("APPROVED", [1920, 1080]))
        self.assertEqual(pc.frame_problems(self.i, self.shot, self.plan), [])
        # the request sends the approved 16:9 still as its first frame
        self.assertEqual(pc.frame_paths(self.shot)[0], rec["repo_path"])

    def test_a_still_at_the_wrong_aspect_is_refused_never_stretched(self):
        from PIL import Image
        img = self.dir / "img"
        img.mkdir()
        Image.new("RGB", (1080, 1920), (90, 80, 70)).save(img / f"{self.still}-56-1.jpg", "JPEG")   # a 9:16 picture
        with self.assertRaises(SystemExit) as c:
            ss.finalize(img, "56", stills_dir=self.dir)
        self.assertTrue(str(c.exception).startswith("STILL_ASPECT_MISMATCH"), str(c.exception))
        # a 9:16 candidate recorded by hand is refused at the approval too
        cand = self.dir / "candidates" / f"{self.still}-56-2.jpg"
        cand.parent.mkdir(parents=True, exist_ok=True)
        jpeg(cand)
        ss.save(cand.with_suffix(".json"), {"id": cand.stem, "still": self.still, "status": "DRAFT",
                                            "prompt": self.shot["prompt"], "size": [1080, 1920],
                                            "repo_path": ss.rel(cand), "sha256": ss.sha256(cand)})
        with self.assertRaises(SystemExit) as c:
            ss.approve(self.still, cand.stem, 9.6, "x", stills_dir=self.dir, reviewer="claude-session-reviewer")
        self.assertTrue(str(c.exception).startswith("STILL_ASPECT_MISMATCH"), str(c.exception))
        with self.assertRaises(SystemExit) as c:
            ss.aspect_of({"aspect_ratio": "4:3"})
        self.assertTrue(str(c.exception).startswith("STILL_ASPECT_UNSUPPORTED"))
        self.assertEqual(ss.aspect_of({}), "9:16")


    def test_crop_cuts_flux_pngs_only_and_refuses_a_native_source_at_the_wrong_aspect(self):
        from PIL import Image
        img = self.dir / "img"
        img.mkdir()
        good = img / f"{self.still}-57-1.jpg"
        Image.new("RGB", (2624, 1472), (90, 80, 70)).save(good, "JPEG")   # Pavo at 16:9: never cut
        before = ss.sha256(good)
        ss.crop(img)
        self.assertEqual(ss.sha256(good), before)
        Image.new("RGB", (1472, 2624), (90, 80, 70)).save(img / f"{self.still}-57-2.jpg", "JPEG")   # 9:16 in a long
        with self.assertRaises(SystemExit) as c:
            ss.crop(img)
        self.assertTrue(str(c.exception).startswith(f"STILL_ASPECT_MISMATCH {self.still}-57-2"), str(c.exception))


class PublicStills(unittest.TestCase):
    """E237 (owner 31/10, "utilizar a pública"): a public-domain or openly licensed picture becomes a scene still only
    from an allowlisted host, with its licence read from the source's own API, the exact bytes' sha256, a crop at the
    plan's aspect and resolution, and a full-resolution review naming every check; then it is a still like any other."""
    PAGE = "https://commons.wikimedia.org/wiki/File:Gustave_Dore_-_The_Deluge.jpg"
    FILE = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Gustave_Dore_-_The_Deluge.jpg"
    CHECKS = ["period", "writing", "god", "characters"]
    NOTE = "Full-res: engraved pairs of animals on a bare hill, no legible text or signature, no figure of God."

    def setUp(self):
        import public_sources
        self.ps = public_sources
        self.dir = Path(tempfile.mkdtemp(prefix=".test-public-", dir=HERE))
        self.saved = pc.STILLS_DIR
        pc.STILLS_DIR = self.dir
        self.plan = json.loads((HERE / "plans" / "genesis-09-short.json").read_text())
        for sid in ("genesis-09-s-pairs", "genesis-09-s-lions"):
            rec = json.loads((HERE / "stills" / f"{sid}.json").read_text())
            ss.save(self.dir / f"{sid}.json", {k: rec[k] for k in ("id", "episode", "shot", "prompt")} |
                    {"status": "DRAFT"})
        self.data = self.picture()
        self.licence = ("cc-by-sa-4.0", "CC BY-SA 4.0")

    def tearDown(self):
        pc.STILLS_DIR = self.saved
        shutil.rmtree(self.dir)

    @staticmethod
    def picture(size=(1600, 1200)):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", size, (120, 110, 90)).save(buf, "JPEG", quality=90)
        return buf.getvalue()

    def get(self, url):
        import hashlib
        if url == self.FILE:
            return self.data
        if url.startswith("https://commons.wikimedia.org/w/api.php"):
            ext = {"License": {"value": self.licence[0]}, "LicenseShortName": {"value": self.licence[1]},
                   "Artist": {"value": "<a href=\"//x\">Gustave Doré</a>"}, "ObjectName": {"value": "The Deluge"}}
            return json.dumps({"query": {"pages": [{"imageinfo": [{
                "url": self.FILE, "sha1": hashlib.sha1(self.data).hexdigest(), "extmetadata": ext}]}]}}).encode()
        raise AssertionError(f"unexpected fetch {url}")

    def fetch(self, still="genesis-09-s-pairs", n=1, **kw):
        kw.setdefault("get", self.get)
        return self.ps.fetch(still, kw.pop("page", self.PAGE), kw.pop("file_url", self.FILE), n=n,
                             stills_dir=self.dir, **kw)

    def approve(self, cand, still="genesis-09-s-pairs", checks=None, note=None):
        return self.ps.approve(still, cand["id"], 9.6, self.CHECKS if checks is None else checks,
                               self.NOTE if note is None else note, stills_dir=self.dir,
                               reviewer="claude-session-reviewer")

    def refused(self, code, fn, *a, **kw):
        with self.assertRaises(SystemExit) as err:
            fn(*a, **kw)
        self.assertTrue(str(err.exception).startswith(code), str(err.exception))

    def test_e237_public_still_is_verified_reviewed_and_used_like_a_generated_still(self):
        import shot_sources
        sys.path.insert(0, str(HERE.parents[1] / "publish"))
        import publish_episode
        cand = self.fetch()
        pub = cand["public"]
        self.assertEqual((pub["licence"], pub["author"], pub["licence_source"]),
                         ("CC-BY-SA-4.0", "Gustave Doré", "commons-extmetadata"))
        self.assertEqual(pub["sha256"], __import__("hashlib").sha256(self.data).hexdigest())
        self.assertEqual(pub["crop"], [462, 0, 675, 1200])
        self.assertIn("Gustave Doré", pub["attribution"])
        rec = self.approve(cand)
        self.assertEqual((rec["status"], rec["engine"], rec["approved"]["review"]["checked"]),
                         ("APPROVED", "public-image", sorted(self.CHECKS)))
        i = next(k for k, s in enumerate(self.plan["shots"]) if s["id"] == "s-pairs")
        shot = self.plan["shots"][i]
        self.assertEqual(pc.frame_problems(i, shot, self.plan, self.dir), [])
        # a tampered record (attribution dropped) no longer carries the frame
        bad = json.loads((self.dir / "genesis-09-s-pairs.json").read_text())
        bad["public"]["attribution"] = None
        ss.save(self.dir / "genesis-09-s-pairs.json", bad)
        self.assertTrue(any(p.startswith("STILL_PUBLIC_REFUSED") and "PUBLIC_ATTRIBUTION_MISSING" in p
                            for p in pc.frame_problems(i, shot, self.plan, self.dir)))
        with self.assertRaises(SystemExit) as err:
            shot_sources.approve_source(self.plan, "s-pairs", "still_motion", "genesis-09-s-pairs", 9.6, "x",
                                        shots_dir=self.dir / "shots", reviewer="claude-session-reviewer")
        self.assertTrue(str(err.exception).startswith("SOURCE_PUBLIC_REFUSED"), str(err.exception))
        ss.save(self.dir / "genesis-09-s-pairs.json", rec)
        # approve-source: camera motion over it, its licence and attribution carried, E139 by the original's sha256
        entry = shot_sources.approve_source(self.plan, "s-pairs", "still_motion", "genesis-09-s-pairs", 9.6,
                                            "the pairs on the hill", shots_dir=self.dir / "shots",
                                            reviewer="claude-session-reviewer")
        self.assertEqual((entry["licence"], entry["attribution"], entry["picture_sha256"]),
                         ("CC-BY-SA-4.0", pub["attribution"], pub["sha256"]))
        self.assertEqual(shot_sources.picture_sha256(entry), pub["sha256"])
        # the description must credit it word for word
        ep = {"id": "genesis-09-short", "description": "Genesis 7 (public domain). AI visuals."}
        self.assertTrue(publish_episode.attribution_problems(ep, self.dir / "shots")[0].startswith(
            "ATTRIBUTION_MISSING s-pairs"))
        ep["description"] += "\nVisual credits: " + pub["attribution"]
        self.assertEqual(publish_episode.attribution_problems(ep, self.dir / "shots"), [])

    def test_e237_each_refusal_of_a_public_still(self):
        import hashlib
        # host not allowlisted (file and page), and an allowlisted host without a licence reader
        self.refused("PUBLIC_HOST_REFUSED", self.fetch, file_url="https://example.org/deluge.jpg")
        self.refused("PUBLIC_HOST_REFUSED", self.fetch, file_url=self.FILE.replace("https", "http"))
        self.refused("PUBLIC_HOST_REFUSED", self.fetch, page="https://en.wikipedia.org/wiki/File:x.jpg")
        self.refused("PUBLIC_LICENCE_UNVERIFIED", self.fetch, page="https://www.loc.gov/item/2006691549/")
        # bad licences: NC, ND, unknown
        for lic in (("cc-by-nc-sa-4.0", "CC BY-NC-SA 4.0"), ("cc-by-nd-4.0", "CC BY-ND 4.0"), ("", "All rights")):
            self.licence = lic
            self.refused("PUBLIC_LICENCE_REFUSED", self.fetch)
        self.licence = ("cc-by-sa-4.0", "CC BY-SA 4.0")
        # sha mismatch: Commons' sha1, the caller's expected sha256
        good = self.get

        def wrong_sha1(url):
            out = good(url)
            return out.replace(hashlib.sha1(self.data).hexdigest().encode(), b"0" * 40) if b"sha1" in out else out
        self.refused("PUBLIC_SHA_MISMATCH", self.fetch, get=wrong_sha1)
        self.refused("PUBLIC_SHA256_MISMATCH", self.fetch, expect_sha256="0" * 64)
        # resolution: a crop whose long side is under a FLUX still's
        self.data = self.picture((900, 700))
        self.refused("PUBLIC_RESOLUTION_LOW", self.fetch)
        self.data = self.picture()
        self.refused("STILL_ASPECT_MISMATCH", self.fetch, crop=[0, 0, 900, 1200])
        self.assertFalse(list((self.dir / "candidates").glob("*.json")) if (self.dir / "candidates").is_dir()
                         else [])
        # missing attribution for CC-BY(-SA) at record level
        cand = self.fetch()
        rec = dict(cand["public"], attribution=None)
        self.assertTrue(pc.public_problems(rec)[0].startswith("PUBLIC_ATTRIBUTION_MISSING"))
        self.assertEqual(pc.public_problems(dict(rec, licence="Public Domain")), [])
        # approve without a review note, with checks missing, through the generated-still route, or tampered
        self.refused("PUBLIC_REVIEW_NOTE_MISSING", self.approve, cand, note=" ")
        self.refused("PUBLIC_REVIEW_INCOMPLETE", self.approve, cand, checks=["period", "writing"])
        self.refused("PUBLIC_CANDIDATE_REFUSED", ss.approve, "genesis-09-s-pairs", cand["id"], 9.6, "x",
                     self.dir, reviewer="claude-session-reviewer")
        self.refused("REVIEWER_IDENTITY_REFUSED", self.ps.approve, "genesis-09-s-pairs", cand["id"], 9.6,
                     self.CHECKS, self.NOTE, stills_dir=self.dir, reviewer=None)
        self.assertEqual(pc.still_record("genesis-09-s-pairs", self.dir)["status"], "DRAFT")
        jpg = self.dir / "candidates" / f"{cand['id']}.jpg"
        saved = jpg.read_bytes()
        jpg.write_bytes(saved + b"\0")
        self.refused("STILL_CANDIDATE_SHA256_MISMATCH", self.approve, cand)
        jpg.write_bytes(saved)
        # E139: the same original approved for another still of this Short (shorter than 300 s) is a repeat
        self.approve(cand)
        other = self.fetch("genesis-09-s-lions", crop=[0, 0, 675, 1200])
        self.refused("PUBLIC_IMAGE_REPEAT genesis-09-s-lions", self.approve, other, still="genesis-09-s-lions")
        self.assertEqual(pc.still_record("genesis-09-s-lions", self.dir)["status"], "DRAFT")

    def test_e237_met_open_access_is_read_from_its_api(self):
        page = "https://www.metmuseum.org/art/collection/search/436105"
        image = "https://images.metmuseum.org/CRDImages/ep/original/DP-13139-001.jpg"
        obj = {"isPublicDomain": True, "primaryImage": image, "additionalImages": [], "title": "The Flood",
               "artistDisplayName": "A Painter"}

        def get(url):
            if url == image:
                return self.data
            if url == "https://collectionapi.metmuseum.org/public/collection/v1/objects/436105":
                return json.dumps(obj).encode()
            raise AssertionError(url)
        cand = self.fetch(page=page, file_url=image, get=get)
        self.assertEqual((cand["public"]["licence"], cand["public"]["attribution"]), ("CC0", None))
        obj["isPublicDomain"] = False
        self.refused("PUBLIC_LICENCE_REFUSED", self.fetch, page=page, file_url=image, get=get, n=2)


if __name__ == "__main__":
    unittest.main()
