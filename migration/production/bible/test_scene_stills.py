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
        # E121: s-dust names the ark, so its still is made with the ark's approved references; here an APPROVED ark
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
                    {"id": f"pr-ark-{view}", "repo_path": ss.rel(img), "sha256": ss.sha256(img)})
            refs.append({"record": f"pr-ark-{view}", "repo_path": ss.rel(img), "sha256": ss.sha256(img)})
        pr.PROPS_FILE, pr.IMAGES_DIR = props, self.dir / "images"
        return refs

    def tearDown(self):
        pc.STILLS_DIR = self.saved
        pr.PROPS_FILE, pr.IMAGES_DIR = self.saved_props
        shutil.rmtree(self.dir)

    def candidate(self, run="123", n=1, colour=(90, 70, 50), prompt=None, references=None):
        cid = f"{self.still}-{run}-{n}"
        img = self.dir / "candidates" / f"{cid}.jpg"
        img.parent.mkdir(parents=True, exist_ok=True)
        jpeg(img, colour=colour)
        rec = pc.still_record(self.still, self.dir)
        ss.save(img.with_suffix(".json"), {"id": cid, "still": self.still, "status": "DRAFT",
                                           "prompt": prompt or rec["prompt"], "size": list(ss.SIDE),
                                           "repo_path": ss.rel(img), "sha256": ss.sha256(img),
                                           "references": self.arkrefs if references is None else references})
        return cid

    def approve(self, cid, score=9.6):
        return ss.approve(self.still, cid, score, "the ark box-shaped, the dust soft, no stray prop",
                          stills_dir=self.dir, today="2026-10-27")

    def codes(self, shot=None):
        return [p.split()[0] for p in pc.frame_problems(self.i, shot or self.shot, self.plan)]

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
        spec = ss.prepare(self.plan, ["s-dust"], 2, "123", stills_dir=self.dir)
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
                                                                 "references": self.arkrefs}))
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
            "upscaler": "none (native 1472x2624), Lanczos to 1080x1920", "references": self.arkrefs}))
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
        # E121: genesis-09's 64 Pavo stills carried ARK_LOOK and ARK_EXCLUDE word for word and still drew a tower at
        # one end, a gabled barn or a ship's bow: text alone does not hold a prop. Like a character's face, the ark
        # is held by its approved reference images, sent by sha256 with every still that names it.
        prompt = pc.still_record(self.still, self.dir)["prompt"]
        self.assertEqual(pc.prop_references("A camp of goat-hair tents at dusk.")[1], [])
        need, missing = pc.prop_references(prompt)
        self.assertEqual((need, missing), (self.arkrefs, []))
        # the flood's setting sentence alone names the ark (and Pavo draws it): it needs the references too
        self.assertEqual(pc.prop_references(pc.PERIODS["the-flood"]["setting"])[0], self.arkrefs)
        # prepare hands the references (repository paths Pavo takes) with every candidate
        spec = ss.prepare(self.plan, ["s-dust"], 1, "123", stills_dir=self.dir)
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
        self.assertEqual(self.codes(), ["STILL_PROP_UNREFERENCED"])
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
            ss.prepare(self.plan, ["s-dust"], 1, "123", stills_dir=self.dir)
        self.assertIn("STILL_PROP_UNREFERENCED", str(err.exception))
        pr.PROPS_FILE, pr.IMAGES_DIR = self.saved_props
        self.assertEqual(pr.registry()["ark"]["status"] == "APPROVED", not pc.prop_references(prompt)[1])

    def test_the_build_lists_every_frame_refusal_plan_check_raises(self):
        src = (HERE / "plan_check.py").read_text()
        body = src[src.index("def frame_problems("):src.index("def frame_paths(")]
        raised = set(re.findall(r'f"([A-Z0-9_]+) shot', body))
        self.assertEqual(raised, set(eb.FRAME_REFUSALS))


if __name__ == "__main__":
    unittest.main()
