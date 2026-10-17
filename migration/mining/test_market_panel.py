from datetime import datetime, timezone
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import market_panel as mp  # noqa: E402

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


class Fake(mp.Client):
    def __init__(self, max_units):
        super().__init__("t", max_units)

    def get(self, endpoint, params, units):
        if not self.can(units):
            raise RuntimeError("UNIT_BUDGET")
        self.units += units
        if endpoint == "search":
            return {"items": [{"snippet": {"channelId": "UCyoung"}}, {"snippet": {"channelId": "UCold"}}]}
        if endpoint == "channels":
            return {"items": [
                {"id": "UCyoung", "snippet": {"title": "Y", "publishedAt": "2026-09-01T00:00:00Z"},
                 "statistics": {"subscriberCount": "1200", "viewCount": "90000", "videoCount": "3"},
                 "contentDetails": {"relatedPlaylists": {"uploads": "UUyoung"}}},
                {"id": "UCold", "snippet": {"title": "O", "publishedAt": "2015-01-01T00:00:00Z"},
                 "statistics": {"hiddenSubscriberCount": True, "viewCount": "5", "videoCount": "1"},
                 "contentDetails": {"relatedPlaylists": {"uploads": "UUold"}}}]}
        if endpoint == "playlistItems":
            return {"items": [{"contentDetails": {"videoId": "v1"}}]}
        if endpoint == "videos":
            return {"items": [{"id": "v1", "snippet": {"publishedAt": "2026-09-02T00:00:00Z", "title": "t"},
                               "statistics": {"viewCount": "100"}, "contentDetails": {"duration": "PT10M5S"}}]}
        raise AssertionError(endpoint)


class Panel(unittest.TestCase):
    def test_build_fetches_only_young_channels(self):
        record = mp.build(Fake(10_000), NOW)
        rows = {c["channel_id"]: c for c in record["channels"]}
        self.assertEqual(rows["UCyoung"]["age_days"], 46)
        self.assertEqual(rows["UCyoung"]["uploads"][0]["duration_seconds"], 605)
        self.assertEqual(rows["UCold"]["uploads_status"], "FETCHED")  # short history, old account
        self.assertIsNone(rows["UCold"]["subscribers"])
        self.assertEqual(record["data_api_units"], 60 * 100 + 1 + 2 + 2)

    def test_budget_stops_discovery_without_overspending(self):
        record = mp.build(Fake(450), NOW)
        self.assertLessEqual(record["data_api_units"], 450)


if __name__ == "__main__":
    unittest.main()
