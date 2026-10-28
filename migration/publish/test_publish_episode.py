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

    def test_from_part_7_a_short_runs_170_to_179_s_and_part_6_keeps_62_to_90(self):
        """Owner, 2026-10-26 (structure bible-story-short: 5/6 winners ran 170-179 s, 0/3 weak); under YouTube's
        180 s Shorts limit, the tail included."""
        self.assertEqual(pe.short_length(6), (62.0, 90.0))
        self.assertEqual(pe.short_length(5), (62.0, 90.0))
        self.assertEqual(pe.short_length(7), (170.0, 179.0))
        self.assertEqual(pe.short_length(40), (170.0, 179.0))
        self.assertLess(pe.SHORT_MAX_S, pe.SHORTS_LIMIT_S)
        self.assertEqual(pe.short_problems(short(part=6, seconds=85.5)), [])
        for seconds in (85.5, 124.0, 169.9, 179.1, 180.0):
            self.assertTrue(pe.short_problems(short(part=7, seconds=seconds))[0].startswith("SHORT_LENGTH"), seconds)
        for seconds in (170.0, 174.5, 179.0):
            self.assertEqual(pe.short_problems(short(part=7, seconds=seconds)), [], seconds)
        ep6 = json.loads((ROOT / "production/bible/episodes/genesis-06-short.json").read_text())
        self.assertFalse([p for p in pe.short_problems(ep6) if p.startswith("SHORT_LENGTH")])


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload


class VideoIdRecorded(unittest.TestCase):
    def test_e140_the_upload_writes_its_video_id_into_the_episode_record(self):
        """E140: the ledger got genesis-05..08's video ids but their episode records never did, so live_intel skipped
        them without a word. The publish step writes the id into the record it published (the workflow commits it)."""
        with tempfile.TemporaryDirectory() as d:
            v = Path(d, "v.mp4")
            v.write_bytes(b"video")
            rec = Path(d, "genesis-99-short.json")
            rec.write_text(json.dumps({"id": "genesis-99-short", "part": 8, "format": "short", "title": "T 🐑",
                                       "description": "D", "tags": [], "output_sha256": pe.sha256_file(v)}, indent=1,
                                      ensure_ascii=False) + "\n")
            ledger = Path(d, "ledger.json")
            ledger.write_text(json.dumps({"entries": {}}))

            def get(url, params=None):
                if url.endswith("channels"):
                    return FakeResponse({"items": [{"id": pe.pv.CHANNEL}]})
                return FakeResponse({"items": [{"snippet": {"channelId": pe.pv.CHANNEL, "title": "T"},
                                                "status": {"privacyStatus": "public", "uploadStatus": "processed"}}]})
            fake = type("S", (), {"get": staticmethod(get)})()
            saved = (pe.problems, pe.pv.session, pe.pv.check, pe.pv.upload)
            try:
                pe.problems = lambda episode, video=None: []
                pe.pv.session = lambda: fake
                pe.pv.check = lambda response, what: response.payload
                pe.pv.upload = lambda s, path, body: {"id": "VID12345678"}
                pe.main(str(rec), str(v), str(ledger), str(Path(d, "receipt.json")))
                text = rec.read_text()
                self.assertEqual(json.loads(text)["video_id"], "VID12345678")
                self.assertTrue(text.endswith("\n"))
                self.assertIn("🐑", text)   # the record stays readable UTF-8
                pe.main(str(rec), str(v), str(ledger), str(Path(d, "receipt.json")))   # a re-run is idempotent
                self.assertEqual(rec.read_text(), text)
                rec.write_text(json.dumps(dict(json.loads(text), video_id="OTHER000000")))
                with self.assertRaises(SystemExit) as e:   # a record naming another video is never overwritten
                    pe.main(str(rec), str(v), str(ledger), str(Path(d, "receipt.json")))
                self.assertIn("EPISODE_VIDEO_ID_MISMATCH", str(e.exception))
            finally:
                pe.problems, pe.pv.session, pe.pv.check, pe.pv.upload = saved

    def test_e140_the_publish_workflow_commits_the_episode_record(self):
        wf = (ROOT.parent / ".github/workflows/publish-episode.yml").read_text()
        record_step = wf.split("Record ledger and receipt", 1)[1].split("git commit", 1)[0]
        self.assertIn("migration/production/bible/episodes/$EPISODE.json", record_step)


if __name__ == "__main__":
    unittest.main()
