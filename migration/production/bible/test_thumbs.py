#!/usr/bin/env python3
"""Offline: the character-first thumbnail (owner, 27/10) is refused unless its spec keeps the rules, and a publish
uploads only the approved image (THUMB_NOT_APPROVED in check-record, before publish-episode.yml)."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "publish"))
import thumbs  # noqa: E402
import publish_episode as pe  # noqa: E402
import publish_video as pv  # noqa: E402

REAL = json.loads((HERE / "thumbs" / "genesis-09-short.json").read_text())


def codes(found):
    return {p.split()[0] for p in found}


class Spec(unittest.TestCase):
    def test_the_genesis_09_spec_passes(self):
        self.assertEqual(thumbs.spec_problems(REAL), [])
        self.assertEqual(REAL["status"], "DRAFT")   # candidates for the owner's review; never approved here

    def test_each_rule_refuses(self):
        chars = thumbs.characters()
        cases = {
            "THUMB_CHARACTER_NOT_APPROVED": dict(character="scoffer"),
            "THUMB_CHARACTER_UNKNOWN": dict(character="moses-x"),
            "THUMB_TEXT_WORDS": dict(text="THE DAY THE FLOOD BEGAN"),
            "THUMB_TEXT_NOT_STORY": dict(text="SHUT IN"),
            "THUMB_FACE_MISSING": dict(framing="wide"),
            "THUMB_EMOTION_MISSING": dict(emotion="joy"),
            "THUMB_SCENE_MISSING": dict(scene=""),
            "THUMB_FORMAT_INVALID": dict(format="square"),
        }
        for code, over in cases.items():
            self.assertIn(code, codes(thumbs.spec_problems(dict(REAL, **over), chars)), code)
        self.assertIn("THUMB_LOOK_CHANGED", codes(thumbs.spec_problems(
            dict(REAL, prompt=REAL["prompt"].replace("long grey beard", "short beard")), chars)))
        self.assertIn("THUMB_PROMPT_REFUSED", codes(thumbs.spec_problems(
            dict(REAL, prompt=REAL["prompt"].replace(thumbs_ark(), "")), chars)))
        self.assertIn("THUMB_TEXT_IN_PROMPT", codes(thumbs.spec_problems(
            dict(REAL, prompt=REAL["prompt"] + " THE FLOOD BEGINS"), chars)))

    def test_keeper_only_in_an_owner_approved_ab_variant(self):
        chars = thumbs.characters()
        keeper = dict(REAL, character="keeper", prompt=REAL["prompt"].replace(chars["noah"]["look"], chars["keeper"]["look"]))
        self.assertIn("THUMB_KEEPER_FACE", codes(thumbs.spec_problems(keeper, chars)))
        self.assertIn("THUMB_KEEPER_FACE", codes(thumbs.spec_problems(dict(keeper, variant={"ab": True}), chars)))
        ab = dict(keeper, variant={"ab": True, "owner_approved": "owner 2026-11-01: A/B the Keeper on genesis-10"})
        self.assertNotIn("THUMB_KEEPER_FACE", codes(thumbs.spec_problems(ab, chars)))


def thumbs_ark():
    sys.path.insert(0, str(HERE))
    import plan_check
    return plan_check.ARK_LOOK


class Pipeline(unittest.TestCase):
    """finalize -> approve -> publish_problems on a temporary thumbs folder, with a synthetic picture."""
    def setUp(self):
        from PIL import Image
        self.tmp = tempfile.TemporaryDirectory(dir=HERE / "thumbs")
        self.dir = Path(self.tmp.name)
        self.spec = copy.deepcopy(REAL)
        (self.dir / "genesis-09-short.json").write_text(json.dumps(self.spec))
        self.img = self.dir / "src.png"
        Image.new("RGB", (1472, 2624), (200, 90, 30)).save(self.img)   # saturated, warm: R16 passes

    def tearDown(self):
        self.tmp.cleanup()

    def test_candidate_approve_and_publish(self):
        from PIL import Image
        rec = thumbs.finalize(self.dir / "genesis-09-short.json", self.img, "7", "1", {"source": "test"}, self.dir)
        with Image.open(thumbs.REPO / rec["repo_path"]) as im:
            self.assertEqual(im.size, (1080, 1920))
        self.assertNotEqual(rec["sha256"], rec["base_sha256"])   # our text is drawn on it
        ep = "genesis-09-short"
        self.assertTrue(all(p.startswith("THUMB_NOT_APPROVED") for p in thumbs.publish_problems(ep, "short", None, self.dir)))
        with self.assertRaises(SystemExit) as low:
            thumbs.approve(ep, rec["id"], 9.0, "x", self.dir)
        self.assertIn("THUMB_SCORE_BELOW_FLOOR", str(low.exception))
        thumbs.approve(ep, rec["id"], 9.6, "character, emotion, text read at phone size", self.dir)
        self.assertEqual(thumbs.publish_problems(ep, "short", None, self.dir), [])
        self.assertEqual(thumbs.publish_problems(ep, "short", self.dir / f"{ep}.jpg", self.dir), [])
        self.assertTrue(thumbs.publish_problems(ep, "short", self.img, self.dir))   # not the approved bytes
        self.assertTrue(thumbs.publish_problems(ep, "long", None, self.dir))       # wrong format
        spec = json.loads((self.dir / f"{ep}.json").read_text())
        spec["text"] = "NOAH AND THE FLOOD"
        (self.dir / f"{ep}.json").write_text(json.dumps(spec))
        self.assertTrue(any("changed after its approval" in p for p in thumbs.publish_problems(ep, "short", None, self.dir)))

    def test_an_approval_written_by_hand_is_refused(self):
        """Review of #460: publish re-checks what `approve` checks (score, note, a recorded candidate with these bytes,
        this spec and R16 PASS), so a spec edited to APPROVED does not pass."""
        import shutil
        from PIL import Image
        ep = "genesis-09-short"
        grey = self.dir / "grey.jpg"
        Image.new("RGB", (1080, 1920), (128, 128, 128)).save(grey, "JPEG")
        shutil.copyfile(grey, self.dir / f"{ep}.jpg")
        forged = dict(self.spec, status="APPROVED", approved={
            "sha256": thumbs.sha256(grey), "spec_sha256": thumbs.digest(self.spec), "candidate": f"{ep}-7-1",
            "score": 1, "note": ""})
        (self.dir / f"{ep}.json").write_text(json.dumps(forged))
        found = " ".join(thumbs.publish_problems(ep, "short", None, self.dir))
        for reason in ("score 1", "no review note", "not a recorded candidate"):
            self.assertIn(reason, found)
        rec = thumbs.finalize(self.dir / f"{ep}.json", grey, "7", "1", {}, self.dir)   # grey: R16 FAIL
        forged["approved"].update(sha256=rec["sha256"], candidate=rec["id"], score=9.6, note="x")
        shutil.copyfile(thumbs.REPO / rec["repo_path"], self.dir / f"{ep}.jpg")
        (self.dir / f"{ep}.json").write_text(json.dumps(forged))
        self.assertIn("R16 PASS", " ".join(thumbs.publish_problems(ep, "short", None, self.dir)))

    def test_an_approved_spec_is_not_another_episodes(self):
        import shutil
        ep = "genesis-09-short"
        rec = thumbs.finalize(self.dir / f"{ep}.json", self.img, "7", "1", {}, self.dir)
        thumbs.approve(ep, rec["id"], 9.6, "ok", self.dir)
        shutil.copyfile(self.dir / f"{ep}.json", self.dir / "genesis-10-short.json")
        shutil.copyfile(self.dir / f"{ep}.jpg", self.dir / "genesis-10-short.jpg")
        found = thumbs.publish_problems("genesis-10-short", "short", None, self.dir)
        self.assertTrue(any("genesis-09-short'" in p for p in found), found)
        self.assertTrue(any("not a recorded candidate" in p for p in found), found)

    def test_an_episode_name_is_never_a_path(self):
        self.assertTrue(thumbs.publish_problems("../../x", "short", None, self.dir)[0].startswith("THUMB_NOT_APPROVED"))
        with self.assertRaises(SystemExit):
            thumbs.approved_image("../genesis-09-short")

    def test_a_candidate_of_another_spec_is_refused(self):
        rec = thumbs.finalize(self.dir / "genesis-09-short.json", self.img, "7", "2", {}, self.dir)
        spec = dict(self.spec, emotion="dread")
        (self.dir / "genesis-09-short.json").write_text(json.dumps(spec))
        with self.assertRaises(SystemExit) as e:
            thumbs.approve("genesis-09-short", rec["id"], 9.6, "x", self.dir)
        self.assertIn("THUMB_SPEC_CHANGED", str(e.exception))


class Publish(unittest.TestCase):
    def test_check_record_refuses_part_9_without_an_approved_thumbnail(self):
        ep = {"id": "genesis-09-short", "format": "short", "part": 9}
        self.assertTrue(any(p.startswith("THUMB_NOT_APPROVED") for p in pe.thumb_problems(ep)))
        self.assertTrue(any(p.startswith("THUMB_NOT_APPROVED") for p in pe.thumb_problems(dict(ep, id="genesis-99-short"))))
        self.assertEqual(pe.thumb_problems(dict(ep, part=8)), [])   # published parts keep what they have

    def test_a_bible_long_needs_its_approved_thumbnail(self):
        self.assertEqual(pv.bible_thumb_problems({"pilot_id": "pilot-015"}, None), [])
        self.assertTrue(pv.bible_thumb_problems({"series": "bible"}, None)[0].startswith("THUMB_NOT_APPROVED"))
        self.assertTrue(pv.bible_thumb_problems({"series": "bible", "thumb_episode": "arc-01-long"}, None))

    def test_a_story_long_needs_it_without_a_series_key(self):
        """Review of #460: no package writer sets `series`, so the pilot's script.json (bible-story-long) decides."""
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(pv.bible_thumb_problems({}, None, t), [])   # no script: not a story long
            (Path(t) / "script.json").write_text(json.dumps({"archetype": "bible-story-long"}))
            self.assertTrue(pv.bible_thumb_problems({}, None, t)[0].startswith("THUMB_NOT_APPROVED"))


if __name__ == "__main__":
    unittest.main()
