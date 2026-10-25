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
            urls = ch.reference_urls(["adam", "eve"], d)
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


if __name__ == "__main__":
    unittest.main()
