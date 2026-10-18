#!/usr/bin/env python3
"""Offline check of the Shorts overlay timing: the scripture reference never shares the screen with the hook."""
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shorts_produce as sp  # noqa: E402


def spans(ass, style):
    out = []
    for line in ass.splitlines():
        m = re.match(r"Dialogue: \d+,(\d+):(\d+):([\d.]+),(\d+):(\d+):([\d.]+)," + style + ",", line)
        if m:
            h1, m1, s1, h2, m2, s2 = m.groups()
            out.append((int(h1) * 3600 + int(m1) * 60 + float(s1), int(h2) * 3600 + int(m2) * 60 + float(s2)))
    return out


class Overlay(unittest.TestCase):
    def moment(self):
        return {"start": 0.0, "sentences": [{"start": 0.2, "end": 3.0, "text": "Renew my strength this morning, Lord."}]}

    def test_reference_enters_after_the_hook(self):
        a = sp.ass(self.moment(), "Renew my strength this morning", "Isaiah 40:31 (KJV)", 40.0)
        (h0, h1), (r0, r1) = spans(a, "Hook")[0], spans(a, "Ref")[0]
        self.assertGreaterEqual(r0, h1)
        self.assertAlmostEqual(r1, 40.0, places=1)

    def test_no_reference_no_line(self):
        self.assertEqual(spans(sp.ass(self.moment(), "Hook", None, 30.0), "Ref"), [])


if __name__ == "__main__":
    unittest.main()
