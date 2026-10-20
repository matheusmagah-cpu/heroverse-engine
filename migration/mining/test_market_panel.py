from datetime import datetime, timezone
import sys
from pathlib import Path
import unittest
import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError

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
        # half of the 38 queries by date (19) + 12 cross-niche + 6 by views
        self.assertEqual(record["data_api_units"], 37 * 100 + 1 + 2 + 2)
        self.assertEqual(rows["UCyoung"]["niche"], "christian")

    def test_budget_stops_discovery_without_overspending(self):
        record = mp.build(Fake(450), NOW)
        self.assertLessEqual(record["data_api_units"], 450)


class UnavailablePanel(unittest.TestCase):
    def build_case(self, failures, total=10, code=404):
        client = Fake(10000)
        original = client.get
        def get(endpoint, params, units):
            if endpoint == 'playlistItems' and params['playlistId'] in failures:
                client.units += units
                client.calls += 1
                raise HTTPError('https://example.invalid', code, 'unavailable', {}, None)
            return original(endpoint, params, units)
        client.get = get
        found = {str(i): {'queries': {'q'}, 'orders': {'date'}, 'niches': {'christian'}} for i in range(total)}
        info = {str(i): {'channel_id': str(i), 'uploads_playlist': str(i), 'videos': 1,
                        'published_at': '2026-09-01T00:00:00Z', 'uploads_status': 'NOT_FETCHED'} for i in range(total)}
        with patch.object(mp, 'discover', return_value=found), patch.object(mp, 'channels', return_value=info):
            record = mp.build(client, NOW)
        return record, client

    def test_one_404_channel_is_recorded_and_other_channels_continue(self):
        record, client = self.build_case({'0'})
        self.assertEqual(record['unavailable_channels'], ['0'])
        failed = record['channels'][0]
        self.assertEqual(failed['uploads_status'], 'UNAVAILABLE_404')
        self.assertEqual(failed['uploads'], [])
        self.assertIs(failed['uploads_truncated'], False)
        self.assertEqual(sum(c['uploads_status'] == 'FETCHED' for c in record['channels']), 9)
        self.assertEqual(client.units, 19)  # failed request still costs 1, nine successful histories cost 2 each
        self.assertEqual(mp.compact(record)['unavailable_channels'], ['0'])

    def run_main(self, record):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / 'nested/raw.json'
            small = Path(directory) / 'compact/panel.json'
            err = io.StringIO()
            with patch.object(mp, 'access_token', return_value='fake'), patch.object(mp, 'Client', return_value=Fake(10000)), patch.object(mp, 'build', return_value=record), redirect_stderr(err), redirect_stdout(io.StringIO()):
                result = mp.main(['market_panel.py', str(raw), '10000', str(small)])
            self.assertEqual(json.loads(raw.read_text())['unavailable_channels'], record['unavailable_channels'])
            self.assertEqual(json.loads(small.read_text())['unavailable_channels'], record['unavailable_channels'])
            return result, err.getvalue()

    def test_thirty_percent_404_exits_one_but_preserves_evidence(self):
        record, client = self.build_case({'0', '1', '2'})
        self.assertEqual(client.units, 17)
        self.assertEqual(self.run_main(record), (1, 'PANEL_MOSTLY_UNAVAILABLE\n'))

    def test_exactly_twenty_five_percent_is_not_an_outage(self):
        record, _ = self.build_case({'0'}, total=4)
        self.assertEqual(self.run_main(record), (0, ''))

    def test_one_in_ten_and_no_unavailable_exit_zero(self):
        for failures in ({'0'}, set()):
            record, _ = self.build_case(failures)
            self.assertEqual(self.run_main(record), (0, ''))

    def test_non_404_http_errors_are_not_swallowed(self):
        for code in (401, 403, 429, 500, 503):
            with self.subTest(code=code), self.assertRaises(HTTPError) as cm:
                self.build_case({'0'}, code=code)
            self.assertEqual(cm.exception.code, code)

    def test_ineligible_channels_without_status_still_count_in_panel(self):
        found = {'x': {'queries': {'q'}, 'orders': {'date'}, 'niches': {'christian'}}}
        for playlist, videos in ((None, 3), ('UUx', 0), ('UUx', 201)):
            info = {'x': {'channel_id': 'x', 'uploads_playlist': playlist, 'videos': videos,
                          'published_at': '2015-01-01T00:00:00Z'}}
            with patch.object(mp, 'discover', return_value=found), patch.object(mp, 'channels', return_value=info):
                record = mp.build(Fake(10000), NOW)
            self.assertEqual(record['unavailable_channels'], [])
            self.assertEqual(len(record['channels']), 1)
            self.assertEqual(self.run_main(record), (0, ''))

    def test_empty_panel_does_not_divide_by_zero(self):
        record, _ = self.build_case(set(), total=0)
        self.assertEqual(self.run_main(record), (0, ''))


if __name__ == "__main__":
    unittest.main()
