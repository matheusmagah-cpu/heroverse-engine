#!/usr/bin/env python3
"""Offline: an episode is refused unless the file matches its hash and the KJV and AI disclosures are stated."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_episode as pe  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class Episode(unittest.TestCase):
    def test_every_episode_record_is_publishable_metadata(self):
        for f in sorted((ROOT / "production/bible/episodes").glob("*.json")):
            ep = json.loads(f.read_text())
            self.assertLessEqual(len(ep["title"]), pe.TITLE_MAX, f.name)
            self.assertIn("(public domain)", ep["description"], f.name)
            self.assertIn("AI", ep["description"], f.name)
            self.assertRegex(ep["output_sha256"], r"^[0-9a-f]{64}$")

    def test_hash_mismatch_and_missing_disclosure_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d, "v.mp4")
            v.write_bytes(b"video")
            ep = {"output_sha256": pe.sha256_file(v), "title": "T", "description": "KJV (public domain). AI voice."}
            self.assertEqual(pe.problems(ep, v), [])
            self.assertIn("OUTPUT_SHA256_MISMATCH", pe.problems(dict(ep, output_sha256="0" * 64), v))
            self.assertIn("DISCLOSURE_MISSING", pe.problems(dict(ep, description="no source"), v))


def short(**over):
    lines = [{"kind": "scripture", "text": "And Enoch walked with God: and he was not; for God took him."},
             {"kind": "story", "text": "In a list of names that ends with the same three words, one man breaks the pattern "
                                       "and the writer slows down to tell us why."},
             {"kind": "insight", "text": "Most people read this as a reward for being good, but the text never says he was "
                                         "perfect; it says he walked, which is a daily habit, not a single great deed."},
             {"kind": "cta", "text": "The whole story of the first families is in the full video on the channel."}]
    ep = {"format": "short", "part": 6, "seconds": 68.0, "narration": lines}
    ep.update(over)
    return ep


class ShortRules(unittest.TestCase):
    """Owner, 2026-10-25: from part 6 on, Shorts run 1 minute or more and carry our own retelling, an insight of our
    own and a close that sends the viewer to the long video (TikTok Creator Rewards and YouTube originality)."""
    def test_a_long_enough_original_short_passes(self):
        self.assertEqual(pe.short_problems(short()), [])

    def test_each_rule_fails_when_broken(self):
        self.assertTrue(pe.short_problems(short(seconds=55.0))[0].startswith("SHORT_LENGTH"))
        lines = short()["narration"]
        quoted = [dict(x, kind="scripture") if x["kind"] == "story" else x for x in lines] + [lines[0]] * 6
        self.assertTrue(any(p.startswith("ORIGINAL_SHARE") for p in pe.short_problems(short(narration=quoted))))
        no_insight = [x for x in lines if x["kind"] != "insight"]
        self.assertTrue(any(p.startswith("INSIGHT_MISSING") for p in pe.short_problems(short(narration=no_insight))))
        no_cta = [dict(x, text="Subscribe for more.") if x["kind"] == "cta" else x for x in lines]
        self.assertTrue(any(p.startswith("CTA_NOT_TO_THE_LONG") for p in pe.short_problems(short(narration=no_cta))))
        self.assertEqual(pe.short_problems(short(narration=[]))[-1][:17], "NARRATION_MISSING")

    def test_published_parts_keep_their_rules(self):
        self.assertEqual(pe.short_problems(short(part=5, seconds=46.6, narration=[])), [])


if __name__ == "__main__":
    unittest.main()
