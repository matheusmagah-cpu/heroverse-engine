#!/usr/bin/env python3
"""Offline checks of the pilot acceptance used on the executor's work: a real pilot passes; copies, fear-bait
packaging, promises, wrong length, edited QA criteria and a taken slot fail."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import script_check as sc  # noqa: E402

HERE = Path(__file__).resolve().parent


def make(t, mutate=None, name="pilot-099", at="2099-01-01T10:00:00Z"):
    prod = Path(t)
    shutil.copytree(HERE / "pilot-005", prod / name, ignore=shutil.ignore_patterns("out", "market", "shorts", "inspection"))
    shutil.copytree(HERE / "pilot-003", prod / "pilot-003", ignore=shutil.ignore_patterns("out", "market", "shorts", "inspection"))
    s = json.loads((prod / name / "script.json").read_text())
    s["pilot_id"] = name
    if mutate:
        mutate(s, prod / name)
    (prod / name / "script.json").write_text(json.dumps(s))
    sch = json.loads((prod / name / "schedule.json").read_text()); sch["publish_at"] = at
    (prod / name / "schedule.json").write_text(json.dumps(sch))
    return prod / name


class Check(unittest.TestCase):
    def run_check(self, mutate=None, **kw):
        with tempfile.TemporaryDirectory() as t:
            return sc.check(make(t, mutate, **kw))[0]

    def test_real_pilot_passes(self):
        self.assertEqual(self.run_check(), [])

    def test_copied_prayer_fails(self):
        other = json.loads((HERE / "pilot-003" / "script.json").read_text())["segments"]
        prayer = next(x for x in other if x["id"].startswith("prayer") and not x.get("reference"))
        def copy(s, d):
            s["segments"][3]["text"] += " " + prayer["text"]
        self.assertTrue(any(p.startswith("NOT_ORIGINAL") for p in self.run_check(copy)))

    def test_fear_bait_title_and_promises_fail(self):
        def bait(s, d):
            s["working_title"] = "WARNING: Morning Prayer They Don't Want You To Hear"
        self.assertTrue(any(p.startswith("POLICY_WORDING") for p in self.run_check(bait)))
        def promise(s, d):
            s["segments"][2]["text"] += " Pray this and you will be healed."
        self.assertTrue(any(p.startswith("POLICY_WORDING") for p in self.run_check(promise)))

    def test_length_and_speech(self):
        def short(s, d):
            s["segments"] = s["segments"][:20]
        self.assertTrue(any(p.startswith("LENGTH") for p in self.run_check(short)))
        def silent(s, d):
            for x in s["segments"]:
                x["pause_after"] = 4.0
        self.assertTrue(any(p.startswith("SPEECH_PRESENCE_EST") for p in self.run_check(silent)))

    def test_reused_images_must_be_hydrated(self):
        def unhydrated(s, d):
            (d / "images" / "figure-a.json").unlink()
        self.assertTrue(any(p.startswith("REUSED_NOT_HYDRATED") for p in self.run_check(unhydrated)))

    def test_frozen_criteria_and_slot(self):
        def edit(s, d):
            (d / "qa_criteria.json").write_text((d / "qa_criteria.json").read_text() + " ")
        self.assertIn("QA_CRITERIA_NOT_THE_FROZEN_FILE", self.run_check(edit))
        taken = json.loads((HERE / "pilot-003" / "schedule.json").read_text())["publish_at"]
        probs = self.run_check(at=taken)
        self.assertTrue(any(p.startswith("SLOT_TAKEN") or p == "PUBLISH_AT_IN_THE_PAST" for p in probs))

    def test_shorts_slot_taken(self):
        def same(s, d):
            sch = json.loads((d / "schedule.json").read_text())
            sch["shorts_slots"] = json.loads((HERE / "pilot-003" / "schedule.json").read_text())["shorts_slots"][:1]
            (d / "schedule.json").write_text(json.dumps(sch))
        self.assertTrue(any(p.startswith("SHORTS_SLOT_TAKEN") for p in self.run_check(same)))


if __name__ == "__main__":
    unittest.main()
