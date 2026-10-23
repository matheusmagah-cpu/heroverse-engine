#!/usr/bin/env python3
"""Offline checks of the footage selection: licence, size, length and title filters, and the credit line."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import footage as ft  # noqa: E402


def cand(**kw):
    c = {"source": "commons", "title": "Sunrise over the hills", "page": "https://commons.wikimedia.org/wiki/File:X.webm",
         "width": 1920, "height": 1080, "seconds": 30.0, "licence": "CC BY 4.0", "author": "A. Author",
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

    def test_resolution_and_length(self):
        self.assertFalse(ft.eligible(cand(height=720)))
        self.assertFalse(ft.eligible(cand(seconds=5.0)))

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


if __name__ == "__main__":
    unittest.main()
