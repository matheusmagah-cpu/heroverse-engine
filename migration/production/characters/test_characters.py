#!/usr/bin/env python3
"""Offline: a character is only used approved and always with the same look and reference images."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import characters as ch  # noqa: E402

LOOK = "a woman of about twenty-five with long black hair"


class Characters(unittest.TestCase):
    def test_a_character_is_used_only_approved_and_with_its_exact_look(self):
        chars = {"eve": {"status": "APPROVED", "look": LOOK}, "adam": {"status": "DRAFT", "look": "a man"}}
        self.assertEqual(ch.problems([{"prompt": f"Eve, {LOOK}, reaches for the fruit", "characters": ["eve"]}], chars), [])
        out = ch.problems([{"prompt": "Eve, a woman with red hair", "characters": ["eve"]},
                           {"prompt": "a man walks", "characters": ["adam"]},
                           {"prompt": "x", "characters": ["moses"]}], chars)
        self.assertEqual([p.split()[0] for p in out], ["CHARACTER_LOOK_CHANGED", "CHARACTER_NOT_APPROVED",
                                                       "CHARACTER_UNKNOWN"])

    def test_reference_images_come_from_the_release_front_views_first(self):
        with tempfile.TemporaryDirectory() as d:
            for cid in ("adam", "eve"):
                for shot in ch.REF_ORDER:
                    Path(d, f"ch-{cid}-{shot}.json").write_text(json.dumps(
                        {"release_asset": f"characters-img-ch-{cid}-{shot}-sha256-x.png"}))
            urls = ch.reference_urls(["adam", "eve"], d, chars={})
            self.assertEqual(len(urls), ch.MAX_REFS)
            self.assertTrue(all(u.startswith(ch.RELEASE) for u in urls))
            self.assertEqual([u.split("ch-")[1].split("-sha")[0] for u in urls[:2]], ["adam-front", "eve-front"])

    def test_the_registry_and_its_reference_prompts_agree(self):
        chars = ch.registry()
        spec = json.loads((ch.HERE / "images.json").read_text())
        for img in spec["images"]:
            c = chars[img["character"]]
            self.assertIn(c["look"], img["prompt"], img["id"])
            self.assertEqual(img["seed"], c["seed"], img["id"])

    def test_only_the_kept_shots_are_references(self):
        with tempfile.TemporaryDirectory() as d:
            for shot in ch.REF_ORDER:
                Path(d, f"ch-eve-{shot}.json").write_text(json.dumps({"release_asset": f"ch-eve-{shot}-sha256-x.png"}))
            urls = ch.reference_urls(["eve"], d, chars={"eve": {"refs": ["full"]}})
            self.assertEqual([u.rsplit("/", 1)[1] for u in urls], ["ch-eve-full-sha256-x.png"])

    def test_every_approved_character_has_its_kept_references_recorded(self):
        for cid, c in ch.registry().items():
            if c["status"] == "APPROVED":
                self.assertTrue(c.get("refs"), cid)
                for shot in c["refs"]:
                    self.assertTrue((ch.HERE / "images" / f"ch-{cid}-{shot}.json").exists(), (cid, shot))


class Voices(unittest.TestCase):
    """Owner, 2026-10-26: every character speaks its lines in its own Kokoro voice; the Keeper keeps am_michael."""
    def test_every_character_has_its_own_voice_from_the_preserved_model(self):
        chars = ch.registry()
        voices = {cid: c.get("voice") for cid, c in chars.items()}
        self.assertEqual(voices["keeper"], "am_michael")
        for cid, v in voices.items():
            self.assertIn(v, ch.KOKORO_VOICES, cid)
        god = ch.voice(ch.GOD)
        self.assertIn(god["voice_id"], ch.KOKORO_VOICES)
        every = list(voices.values()) + [god["voice_id"]]
        self.assertEqual(len(every), len(set(every)), "one distinct voice per speaker")
        self.assertEqual(ch.voice("eve"), {"voice_id": voices["eve"], "speed": 1.0})
        self.assertIsNone(ch.voice("moses"))

    def test_noah_is_approved_with_his_kept_references_and_a_fixed_look(self):
        # 2026-10-27: front and three-quarter kept by Claude's review (characters.json "reviewed")
        noah = ch.registry()["noah"]
        self.assertEqual(noah["status"], "APPROVED")
        self.assertEqual(noah["refs"], ["front", "three-quarter"])
        self.assertIn("about seventy", noah["look"])
        self.assertIn("long grey beard", noah["look"])
        self.assertGreaterEqual(len(noah["wardrobe"]), 2)
        self.assertNotIn(noah["look"], ch.registry()["keeper"]["look"])
        spec = json.loads((ch.HERE / "images.json").read_text())
        self.assertEqual(sorted(i["id"] for i in spec["images"] if i["character"] == "noah"),
                         ["ch-noah-front", "ch-noah-full", "ch-noah-three-quarter"])
        self.assertEqual(ch.problems([{"prompt": noah["look"], "characters": ["noah"]}]), [])

    def test_scoffer_waits_as_a_draft_antagonist_with_his_own_face_voice_and_reference_prompts(self):
        chars = ch.registry()
        scoffer = chars["scoffer"]
        self.assertEqual(scoffer["status"], "DRAFT")
        self.assertEqual(scoffer["refs"], [])
        self.assertIn("about forty-five", scoffer["look"])
        self.assertGreaterEqual(len(scoffer["wardrobe"]), 2)
        for other in ("noah", "keeper"):
            self.assertNotIn(scoffer["look"], chars[other]["look"])
        spec = json.loads((ch.HERE / "images.json").read_text())
        mine = [i for i in spec["images"] if i["character"] == "scoffer"]
        self.assertEqual(sorted(i["id"] for i in mine),
                         ["ch-scoffer-front", "ch-scoffer-full", "ch-scoffer-three-quarter"])
        self.assertTrue(all(scoffer["look"] in i["prompt"] and i["seed"] == scoffer["seed"] for i in mine))
        self.assertTrue(ch.problems([{"prompt": scoffer["look"], "characters": ["scoffer"]}])[0]
                        .startswith("CHARACTER_NOT_APPROVED"))


class RepoReference(unittest.TestCase):
    def test_keeper_reference_is_the_reviewed_repo_frame(self):
        import hashlib
        urls = ch.reference_urls(["keeper"])
        self.assertEqual(urls, [ch.RAW + "migration/production/characters/refs/ch-keeper-front.jpg"])
        rec = json.loads((ch.HERE / "images" / "ch-keeper-front.json").read_text())
        img = ch.HERE.parents[2] / rec["repo_path"]
        self.assertEqual(hashlib.sha256(img.read_bytes()).hexdigest(), rec["sha256"])


class Props(unittest.TestCase):
    """E122: the ark is a referenced prop like a character: DRAFT candidates with sha256 and a 0-credit quote, approved
    only by `props.py approve` (>= 9.5), APPROVED only when every view has its image."""

    def setUp(self):
        import props as pr
        import shutil
        self.pr, self.shutil = pr, shutil
        sys.path.insert(0, str(pr.REPO / "migration" / "production" / "bible"))
        import plan_check
        self.look = plan_check.ARK_LOOK + " " + plan_check.ARK_EXCLUDE
        self.d = Path(tempfile.mkdtemp(prefix=".test-props-", dir=pr.HERE))   # inside the repository
        self.file = self.d / "props.json"
        pr.save(self.file, {"props": {"ark": {"status": "DRAFT", "views": ["side", "three-quarter"], "refs": []}}})
        self.props = pr.registry(self.file)

    def tearDown(self):
        self.shutil.rmtree(self.d)

    def image(self, name, colour):
        from PIL import Image
        path = self.d / name
        Image.new("RGB", (64, 36), colour).save(path, "JPEG")
        return path

    def meta(self, prompt=None, credits=0.0):
        return {"prompt": prompt or f"Prop reference image, side elevation. {self.look} No text.",
                "conversation_id": "1", "quote": {"required_credits": credits, "final_points": 0.0,
                                                  "is_estimate": False}}

    def finalize(self, view, n, colour, **kw):
        return self.pr.finalize("ark", view, "9", n, self.image(f"{view}-{n}.jpg", colour), self.meta(**kw),
                                cand_dir=self.d / "candidates", props=self.props)

    def approve(self, view, cid, score=9.6):
        return self.pr.approve("ark", view, cid, score, "one box, flat square ends", cand_dir=self.d / "candidates",
                               props_file=self.file, images_dir=self.d / "images", refs_dir=self.d / "refs",
                               today="2026-10-27")

    def test_candidates_carry_the_look_a_zero_quote_and_their_sha256(self):
        rec = self.finalize("side", 1, (90, 60, 30))
        self.assertEqual((rec["status"], rec["id"]), ("DRAFT", "pr-ark-side-9-1"))
        self.assertEqual(rec["sha256"], self.pr.sha256(self.pr.REPO / rec["repo_path"]))
        for kw, code in (({"prompt": "a long wooden ship"}, "PROP_PROMPT_REFUSED"), ({"credits": 2.0},
                                                                                     "PROP_QUOTE_NOT_ZERO")):
            with self.assertRaises(SystemExit) as err:
                self.finalize("side", 2, (1, 2, 3), **kw)
            self.assertIn(code, str(err.exception))
        with self.assertRaises(SystemExit):
            self.finalize("top", 1, (1, 2, 3))
        self.assertEqual(self.pr.sheet("ark", "9", self.d / "sheet.jpg", cand_dir=self.d / "candidates"),
                         ["pr-ark-side-9-1"])

    def test_the_prop_is_approved_only_with_every_view_and_its_images_by_sha256(self):
        side = self.finalize("side", 1, (90, 60, 30))["id"]
        tq = self.finalize("three-quarter", 1, (80, 50, 20))["id"]
        with self.assertRaises(SystemExit) as err:
            self.approve("side", side, score=9.4)
        self.assertIn("PROP_SCORE_BELOW_FLOOR", str(err.exception))
        with self.assertRaises(SystemExit):
            self.approve("three-quarter", side)   # a side candidate is no three-quarter view
        self.approve("side", side)
        props = self.pr.registry(self.file)
        self.assertEqual((props["ark"]["status"], props["ark"]["refs"]), ("DRAFT", ["side"]))
        self.assertEqual(self.pr.approved_refs("ark", props, self.d / "images")[0], [])
        self.approve("three-quarter", tq)
        props = self.pr.registry(self.file)
        self.assertEqual(props["ark"]["status"], "APPROVED")
        refs, why = self.pr.approved_refs("ark", props, self.d / "images")
        self.assertIsNone(why)
        self.assertEqual([r["record"] for r in refs], ["pr-ark-side", "pr-ark-three-quarter"])
        from PIL import Image
        Image.new("RGB", (64, 36), (1, 1, 1)).save(self.d / "refs" / "pr-ark-side.jpg", "JPEG")
        self.assertIn("sha256", self.pr.approved_refs("ark", props, self.d / "images")[1])

    def test_a_frame_is_cut_only_from_a_clip_claude_approved(self):
        import subprocess
        clip = self.d / "clip.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=brown:s=144x256:d=2:r=10",
                        "-pix_fmt", "yuv420p", str(clip)], check=True)
        digest = self.pr.sha256(clip)
        shots = self.d / "shots"
        self.pr.save(shots / "ep-a.json", {"shots": {"s-box": {"asset": "a.mp4", "clip_sha256": digest, "score": 9.5,
                                                              "clip_seconds": 2},
                                                    "s-low": {"clip_sha256": digest, "score": 9.0}}})
        kw = {"cand_dir": self.d / "candidates", "props": self.props, "shots_dir": shots}
        rec = self.pr.finalize_frame("ark", "side", "9", 1, clip, "ep-a", "s-box", 1.0, crop=[0, 0, 144, 128], **kw)
        self.assertEqual((rec["source"], rec["size"], rec["clip"]["clip_sha256"]), ("approved-clip-frame", [144, 128],
                                                                                   digest))
        self.assertEqual(rec["sha256"], self.pr.sha256(self.pr.REPO / rec["repo_path"]))
        for args, code in ((("ep-a", "s-low", 1.0), "PROP_SOURCE_REFUSED"),     # approved below 9.5
                           (("ep-a", "s-none", 1.0), "PROP_SOURCE_REFUSED"),    # no approval
                           (("../x", "s-box", 1.0), "PROP_SOURCE_REFUSED"),
                           (("ep-a", "s-box", 9.0), "PROP_FRAME_TIME_REFUSED")):
            with self.assertRaises(SystemExit) as err:
                self.pr.finalize_frame("ark", "side", "9", 2, clip, *args, **kw)
            self.assertIn(code, str(err.exception))
        with self.assertRaises(SystemExit) as err:   # another clip under the approved shot's name
            other = self.d / "other.mp4"
            other.write_bytes(clip.read_bytes() + b"x")
            self.pr.finalize_frame("ark", "side", "9", 2, other, "ep-a", "s-box", 1.0, **kw)
        self.assertIn("PROP_SOURCE_REFUSED", str(err.exception))
        # a frame never enters as a Pavo still with a borrowed source, nor any other source
        with self.assertRaises(SystemExit) as err:
            self.pr.finalize(
                "ark", "side", "9", 3, self.image("x.jpg", (1, 2, 3)), dict(self.meta(), source="approved-clip-frame"),
                cand_dir=self.d / "candidates", props=self.props)
        self.assertIn("PROP_SOURCE_REFUSED", str(err.exception))
        self.assertTrue(self.pr.source_problems("ark", {"source": "hand"}))
        # approve re-checks the approval: a clip no longer approved refuses its frame
        self.pr.save(shots / "ep-a.json", {"shots": {"s-box": {"clip_sha256": "0" * 64, "score": 9.5}}})
        with self.assertRaises(SystemExit) as err:
            self.pr.approve("ark", "side", rec["id"], 9.6, "box", cand_dir=self.d / "candidates", props_file=self.file,
                            images_dir=self.d / "images", refs_dir=self.d / "refs", shots_dir=shots)
        self.assertIn("PROP_SOURCE_REFUSED", str(err.exception))
        self.pr.save(shots / "ep-a.json", {"shots": {"s-box": {"clip_sha256": digest, "score": 9.5}}})
        ref = self.pr.approve("ark", "side", rec["id"], 9.6, "box", cand_dir=self.d / "candidates",
                              props_file=self.file, images_dir=self.d / "images", refs_dir=self.d / "refs",
                              shots_dir=shots)
        self.assertIn("approved-clip-frame", ref["source"])

    def test_the_committed_ark_candidates_are_recorded_and_unapproved_until_review(self):
        props = self.pr.registry()
        ark = props["ark"]
        if ark["status"] != "APPROVED":
            self.assertEqual(self.pr.approved_refs("ark", props)[0], [])
        for meta in sorted(self.pr.CANDIDATES_DIR.glob("pr-ark-*.json")):
            rec = json.loads(meta.read_text())
            self.assertEqual(rec["sha256"], self.pr.sha256(self.pr.REPO / rec["repo_path"]), meta.name)
            # a Pavo still with the look and an exact 0-credit quote, or a frame of a clip approved at >= 9.5
            self.assertEqual(self.pr.source_problems("ark", rec), [], meta.name)
            if rec["source"] == self.pr.PAVO:
                self.assertIn(self.look, rec["prompt"], meta.name)
        for view in ark.get("refs") or []:
            rec = json.loads(self.pr.record_path("ark", view).read_text())
            self.assertEqual(rec["sha256"], self.pr.sha256(self.pr.REPO / rec["repo_path"]))


if __name__ == "__main__":
    unittest.main()
