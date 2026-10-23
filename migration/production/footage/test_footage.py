#!/usr/bin/env python3
"""Offline checks of the footage selection: licence, size, length and title filters, and the credit line."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import footage as ft  # noqa: E402


def cand(**kw):
    c = {"source": "commons", "title": "Sunrise over the hills", "page": "https://commons.wikimedia.org/wiki/File:X.webm",
         "width": 2560, "height": 1440, "seconds": 30.0, "licence": "CC BY 4.0", "author": "A. Author",
         "licence_url": "https://creativecommons.org/licenses/by/4.0", "download": "https://upload.wikimedia.org/x.webm"}
    c.update(kw)
    return c


class Selection(unittest.TestCase):
    def test_accepted_licences(self):
        for lic in ("CC0", "Public domain", "CC BY 2.0", "CC BY 3.0", "CC BY 4.0", "CC BY 3.0 de"):
            self.assertTrue(ft.eligible(cand(licence=lic)), lic)
        self.assertTrue(ft.eligible(cand(source="pexels", licence="Pexels License")))

    def test_share_alike_non_commercial_and_unknown_refused(self):
        for lic in ("CC BY-SA 4.0", "CC BY-SA 3.0", "CC BY-NC 4.0", "CC BY-ND 4.0", "GFDL", "", "Attribution"):
            self.assertFalse(ft.eligible(cand(licence=lic)), lic)
        self.assertFalse(ft.eligible(cand(source="pexels", licence="CC BY 4.0")))

    def test_canonical_licence_matches_qa_v4(self):
        import json
        v4 = json.loads((Path(__file__).resolve().parents[1] / "qa_criteria_v4.json").read_text())
        self.assertEqual(tuple(v4["rights"]["allowed_footage_licences"]), ft.ACCEPTED)
        self.assertEqual(ft.canonical("commons", "CC BY 3.0 de"), "CC BY 3.0")
        self.assertEqual(ft.canonical("commons", "cc-zero"), "CC0")
        self.assertEqual(ft.canonical("commons", "PD"), "Public domain")
        self.assertIsNone(ft.canonical("commons", "CC BY 1.0"))

    def test_resolution_and_length(self):
        self.assertFalse(ft.eligible(cand(height=720)))
        self.assertFalse(ft.eligible(cand(height=1080)))   # owner, 2026-10-23: never below 1440p
        self.assertFalse(ft.eligible(cand(seconds=5.0)))
        self.assertFalse(ft.eligible(cand(width=1080, height=1920)))  # E51: vertical source, would be enlarged

    def test_titles_announcing_people_or_text_refused(self):
        for t in ("Tourists at the waterfall", "A man walking at sunrise", "Festival lights", "Logo intro",
                  "City traffic at night", "Children by the lake"):
            self.assertFalse(ft.eligible(cand(title=t)), t)
        self.assertTrue(ft.eligible(cand(title="Waterfall in the mountains")))

    def test_credit_lines(self):
        self.assertEqual(ft.credit(cand()), 'Footage: "Sunrise over the hills" by A. Author, CC BY 4.0, via Wikimedia '
                                            'Commons (https://commons.wikimedia.org/wiki/File:X.webm)')
        self.assertTrue(ft.credit(cand(source="pexels", page="https://www.pexels.com/video/x-1/")).endswith(
            "via Pexels (https://www.pexels.com/video/x-1/)"))

    def test_pixabay_hits_keep_the_smallest_file_at_or_above_1440p(self):
        hit = {"pageURL": "https://pixabay.com/videos/waterfall-1/", "tags": "waterfall, forest, nature", "duration": 24,
               "user": "Author", "videos": {"large": {"url": "https://cdn.pixabay.com/l.mp4", "width": 3840, "height": 2160},
                                            "medium": {"url": "https://cdn.pixabay.com/m.mp4", "width": 1920, "height": 1080}}}
        old, ft.get_json = ft.get_json, lambda url, headers=None: {"hits": [hit]}
        try:
            (c,) = ft.pixabay_search("waterfall", "k")
        finally:
            ft.get_json = old
        self.assertEqual((c["height"], c["download"]), (2160, "https://cdn.pixabay.com/l.mp4"))
        self.assertTrue(ft.eligible(c))
        self.assertEqual(ft.canonical("pixabay", c["licence"]), "Pixabay Content License")
        self.assertEqual(ft.credit(c), "Footage: Author via Pixabay (https://pixabay.com/videos/waterfall-1/)")
        self.assertFalse(ft.eligible({**c, "licence": "CC BY 4.0"}))
        self.assertFalse(ft.eligible({**c, "title": "woman, waterfall"}))


class Vetting(unittest.TestCase):
    OK_DESC = ["A waterfall pours over mossy rocks into a green pool.", "White water rushes between rocks and ferns."]

    def test_clean_clip_is_approved(self):
        self.assertEqual(ft.decide([80, 90, 85, 88, 70], [[], [], [], [], []], self.OK_DESC)["vetting"], "APPROVED")

    def test_black_frames_text_and_named_objects_rejected(self):
        self.assertIn("BLACK_FRAMES", ft.decide([5, 4, 80, 90, 85], [[]] * 5, self.OK_DESC)["vetting_reasons"])
        r = ft.decide([80] * 5, [["POLICE", "WEEK"], [], [], [], []], self.OK_DESC)
        self.assertEqual(r["vetting"], "REJECTED")
        self.assertTrue(r["vetting_reasons"][0].startswith("TEXT_ON_SCREEN"))
        r = ft.decide([80] * 5, [[]] * 5, ["A city skyline with tall buildings at sunset.", "Clouds over the city."])
        self.assertEqual(r["vetting_reasons"], ["DESCRIBED buildings,city"])
        r = ft.decide([80] * 5, [[]] * 5, ["A man in a kayak on a river.", "A river."])
        self.assertEqual(r["vetting"], "REJECTED")

    def test_a_check_that_did_not_run_leaves_it_pending(self):
        self.assertEqual(ft.decide([80] * 5, [None, [], [], [], []], self.OK_DESC)["vetting"], "PENDING")
        self.assertEqual(ft.decide([80] * 5, [[]] * 5, [None, self.OK_DESC[1]])["vetting"], "PENDING")

    def test_title_filter_catches_the_first_library_rejects(self):
        for t in ("Half Shot at Sunrise (1930) by Paul Sloane", "Artemis II SLS rocket rollout", "Silom sunset timelapse city",
                  "Rogue River rafting", "Candle light vigil 2015", "Ernesto brings dangerous seas, satellite view"):
            self.assertFalse(ft.eligible(cand(title=t)), t)


if __name__ == "__main__":
    unittest.main()
