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

    def test_noah_waits_as_a_draft_with_a_fixed_look_and_his_reference_prompts(self):
        noah = ch.registry()["noah"]
        self.assertEqual(noah["status"], "DRAFT")
        self.assertEqual(noah["refs"], [])
        self.assertIn("about seventy", noah["look"])
        self.assertIn("long grey beard", noah["look"])
        self.assertGreaterEqual(len(noah["wardrobe"]), 2)
        self.assertNotIn(noah["look"], ch.registry()["keeper"]["look"])
        spec = json.loads((ch.HERE / "images.json").read_text())
        self.assertEqual(sorted(i["id"] for i in spec["images"] if i["character"] == "noah"),
                         ["ch-noah-front", "ch-noah-full", "ch-noah-three-quarter"])
        self.assertTrue(ch.problems([{"prompt": noah["look"], "characters": ["noah"]}])[0]
                        .startswith("CHARACTER_NOT_APPROVED"))


class RepoReference(unittest.TestCase):
    def test_keeper_reference_is_the_reviewed_repo_frame(self):
        import hashlib
        urls = ch.reference_urls(["keeper"])
        self.assertEqual(urls, [ch.RAW + "migration/production/characters/refs/ch-keeper-front.jpg"])
        rec = json.loads((ch.HERE / "images" / "ch-keeper-front.json").read_text())
        img = ch.HERE.parents[2] / rec["repo_path"]
        self.assertEqual(hashlib.sha256(img.read_bytes()).hexdigest(), rec["sha256"])


if __name__ == "__main__":
    unittest.main()
