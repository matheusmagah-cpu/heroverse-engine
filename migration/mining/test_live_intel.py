#!/usr/bin/env python3
"""Offline: live intelligence decides only on comparable evidence, one change at a time, never on the fixed layer."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_intel as li  # noqa: E402


def row(id_, age_h, views, part=1, **attributes):
    return {"id": id_, "part": part, "age_h": age_h, "views": views, "bucket": li.age_bucket(age_h),
            "attributes": attributes}


class LiveIntel(unittest.TestCase):
    def test_young_or_small_is_inconclusive(self):
        hist = [row("a", 50, 300), row("b", 55, 320)]
        self.assertEqual(li.verdict(row("g1", 1.6, 35), hist)["verdict"], "inconclusive")   # Genesis 1 at 1.6 h
        self.assertEqual(li.verdict(row("g1", 50, 40), hist)["verdict"], "inconclusive")    # too few views to judge

    def test_compared_only_with_episodes_at_a_similar_age(self):
        hist = [row("a", 50, 300), row("b", 55, 320), row("c", 160, 2000)]  # c's 7-day total must not count
        v = li.verdict(row("d", 52, 400), hist)
        self.assertEqual((v["median"], v["verdict"]), (310, "good"))
        self.assertEqual(li.verdict(row("d", 52, 200), hist)["verdict"], "bad")
        self.assertEqual(li.verdict(row("d", 52, 330), hist)["verdict"], "neutral")
        self.assertEqual(li.verdict(row("d", 100, 330), hist)["verdict"], "inconclusive")  # no peer near 100 h yet

    def test_hypothesis_kept_or_reverted_only_after_two_consecutive(self):
        h = {"attribute": "hook_type", "value": "question"}
        judged = lambda vs: [dict(row(f"e{i}", 60, 1), verdict={"verdict": v}, attributes={"hook_type": "question"})
                             for i, v in enumerate(vs)]
        self.assertEqual(li.evaluate(h, judged(["good"])), "RUNNING")
        self.assertEqual(li.evaluate(h, judged(["good", "good"])), "KEPT")
        self.assertEqual(li.evaluate(h, judged(["good", "bad"])), "RUNNING")
        self.assertEqual(li.evaluate(h, judged(["bad", "bad"])), "REVERTED")
        self.assertEqual(li.evaluate(h, judged(["good", "inconclusive"])), "RUNNING")

    def test_authenticity_layer_and_one_change_at_a_time(self):
        self.assertEqual(li.can_start([], {"attribute": "prayer"}), (False, "PROTECTED_AUTHENTICITY_LAYER"))
        self.assertEqual(li.can_start([{"status": "RUNNING"}], {"attribute": "hook_type"}),
                         (False, "ONE_CHANGE_AT_A_TIME"))
        self.assertEqual(li.can_start([{"status": "KEPT"}], {"attribute": "hook_type"}), (True, "OK"))

    def test_every_episode_record_carries_its_attributes(self):
        # without the attributes a verdict cannot say what to repeat or change
        for f in sorted((Path(__file__).resolve().parents[1] / "production/bible/episodes").glob("*.json")):
            ep = json.loads(f.read_text())
            self.assertEqual([k for k in li.REQUIRED_ATTRIBUTES if k not in ep.get("attributes", {})], [], f.name)
            self.assertFalse(set(ep["attributes"]) & li.PROTECTED, f.name)

    def test_main_accumulates_history_across_days(self):
        with tempfile.TemporaryDirectory() as t:
            eps = Path(t, "eps"); eps.mkdir()
            for i in (1, 2, 3):
                (eps / f"genesis-0{i}-short.json").write_text(json.dumps(
                    {"id": f"genesis-0{i}", "part": i, "video_id": f"v{i}", "attributes": {"hook_type": "statement"}}))
            day = lambda cap, vids: Path(t, "stats.json").write_text(json.dumps({"captured_at": cap, "videos": vids}))
            state, out = Path(t, "state.json"), Path(t, "out.json")
            day("2026-10-26T12:00:00Z", [{"id": "v1", "published_at": "2026-10-24T12:00:00Z", "views": 400},
                                         {"id": "v2", "published_at": "2026-10-24T13:00:00Z", "views": 380}])
            li.main(eps, Path(t, "stats.json"), state, out)
            day("2026-10-27T12:00:00Z", [{"id": "v3", "published_at": "2026-10-25T12:00:00Z", "views": 900}])
            li.main(eps, Path(t, "stats.json"), state, out)
            v3 = json.loads(out.read_text())["episodes"][0]["verdict"]
            self.assertEqual((v3["verdict"], v3["median"]), ("good", 390))  # judged against v1/v2 at 47-48 h
            self.assertEqual(len(json.loads(state.read_text())["history"]), 3)

    def test_e140_a_published_episode_without_its_video_id_is_refused_not_skipped(self):
        """E140: genesis-05..08 were public with their ids in publish/ledger.json, but their records had no video_id
        and rows() skipped them without a word. main() now refuses: the instrument never drops a published episode."""
        with tempfile.TemporaryDirectory() as t:
            eps = Path(t, "eps")
            eps.mkdir()
            sha = "ab" * 32
            rec = lambda **over: json.dumps(dict({"id": "genesis-05-short", "part": 5, "output_sha256": sha,
                                                  "attributes": {}}, **over))
            (eps / "genesis-05-short.json").write_text(rec())
            ledger = Path(t, "ledger.json")
            ledger.write_text(json.dumps({"entries": {f"bible:genesis-05-short:{sha}": {"video_id": "OYijqQdQq0o"}}}))
            Path(t, "stats.json").write_text(json.dumps({"captured_at": "2026-10-28T08:00:00Z", "videos": []}))
            args = (eps, Path(t, "stats.json"), Path(t, "state.json"), Path(t, "out.json"), ledger)
            with self.assertRaises(SystemExit) as e:
                li.main(*args)
            self.assertIn("EPISODE_VIDEO_ID_MISSING genesis-05-short", str(e.exception))
            self.assertFalse(Path(t, "state.json").exists())   # nothing half-written
            (eps / "genesis-05-short.json").write_text(rec(video_id="WRONG"))
            with self.assertRaises(SystemExit) as e:
                li.main(*args)
            self.assertIn("EPISODE_VIDEO_ID_MISMATCH genesis-05-short", str(e.exception))
            (eps / "genesis-05-short.json").write_text(rec(video_id="OYijqQdQq0o"))
            self.assertEqual(li.main(*args), 0)

    def test_e140_every_published_episode_record_carries_the_ledger_video_id(self):
        root = Path(__file__).resolve().parents[1]
        ledger = json.loads((root / "publish/ledger.json").read_text())
        eps = [json.loads(f.read_text()) for f in sorted((root / "production/bible/episodes").glob("*.json"))]
        self.assertEqual(li.video_id_problems(eps, ledger), [])


if __name__ == "__main__":
    unittest.main()
