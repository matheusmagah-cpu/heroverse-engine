"""Known-answer tests for interval growth and within-channel cohorts."""
import datetime as dt
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opportunity as o  # noqa: E402

T0 = dt.datetime(2026, 10, 14, tzinfo=dt.timezone.utc)


def meta(channel, stratum="601_1800_SECONDS", title="Morning prayer"):
    return {"title": title, "channel_id": channel, "duration_seconds": 1200,
            "published": T0 - dt.timedelta(days=10), "stratum": stratum, "language": "en"}


class OpportunityTests(unittest.TestCase):
    def test_interval_growth_and_acceleration(self):
        points = [(T0, 1000), (T0 + dt.timedelta(days=1), 2000), (T0 + dt.timedelta(days=2), 4000)]
        g = o.growth(points)
        self.assertEqual(g["views_per_day_interval"], 1500.0)
        self.assertEqual(g["acceleration_views_per_day"], 1000.0)
        self.assertIsNone(o.growth([(T0, 1), (T0 + dt.timedelta(hours=5), 9)]))

    def test_cohorts_are_within_channel_and_stratum(self):
        series, info = {}, {}
        for i, gain in enumerate((10, 500, 50, 5, 900, 90)):
            vid = f"v{i}"
            series[vid] = [(T0, 0), (T0 + dt.timedelta(days=2), gain * 2)]
            info[vid] = meta("A" if i < 3 else "B")
        rows, summary = o.report(series, info)
        by = {r["video_id"]: r["cohort"] for r in rows}
        self.assertEqual((by["v1"], by["v2"], by["v0"]), ("WINNER", "MEDIAN", "WEAK"))
        self.assertEqual((by["v4"], by["v5"], by["v3"]), ("WINNER", "MEDIAN", "WEAK"))
        plan = o.acquisition_plan(rows)
        self.assertEqual({p["video_id"] for p in plan}, {f"v{i}" for i in range(6)})
        self.assertTrue(all(p["start"] == 0 and p["end"] == 40 for p in plan))


if __name__ == "__main__":
    unittest.main()
