import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import channel_config as cc  # noqa: E402
import publish_video as pv  # noqa: E402

# test fixture only: not the channel's real configuration (structures/channel.json is evidence-based, stage 0)
FIXTURE = {"version": "channel-v1", "channel_id": pv.CHANNEL, "settings": {
    "description": {"value": "Fixture description.", "source": "fixture: Help page quote", "verified_at": "2026-10-19"},
    "keywords": {"value": ["fixture prayer", "kjv"], "source": "fixture: vidIQ winners", "verified_at": "2026-10-19"},
    "country": {"value": "us", "source": "fixture: owner", "verified_at": "2026-10-19"},
    "default_language": {"value": "en", "source": "", "verified_at": None},
    "unsubscribed_trailer": {"value": "TRAILER01", "source": "UNMEASURED", "verified_at": None},
    "sections": {"value": [{"type": "singlePlaylist"}], "source": "fixture", "verified_at": "2026-10-19"}}}

CURRENT = {"channel": {"title": "HeroVerse", "description": "Old description.", "keywords": '"fixture prayer" kjv',
                       "defaultLanguage": "pt", "trackingAnalyticsAccountId": "UA-keep"},
           "image": {"bannerExternalUrl": "https://example.invalid/banner"}, "watch": {"textColor": "#fff"}}


class R:
    def __init__(self, code, body=None):
        self.status_code, self._body = code, body
        self.content = json.dumps(body).encode() if body is not None else b""
        self.text = self.content.decode()

    def json(self):
        return self._body


class FakeSession:
    """Mocked YouTube session (no network): channels.list returns the stored brandingSettings, update stores them."""

    def __init__(self, branding=None, channel=pv.CHANNEL):
        self.branding, self.channel, self.calls, self.updates = copy.deepcopy(branding or CURRENT), channel, [], []

    def get(self, url, params=None, **kw):
        self.calls.append(("GET", url.split("/")[-1], params))
        return R(200, {"items": [{"id": self.channel, "snippet": {"title": "HeroVerse"},
                                  "brandingSettings": copy.deepcopy(self.branding), "localizations": {}}]})

    def put(self, url, params=None, json=None, **kw):
        self.calls.append(("PUT", url.split("/")[-1], params))
        self.updates.append(copy.deepcopy(json))
        self.branding = copy.deepcopy(json["brandingSettings"])
        return R(200, json)

    def post(self, *a, **kw):
        raise AssertionError("channel_config never posts")


class ChannelConfig(unittest.TestCase):
    def run_cfg(self, d, fake, apply, fixture=FIXTURE):
        cc.pv.session = lambda: fake
        (d / "channel.json").write_text(json.dumps(fixture))
        receipt = cc.main(d / "channel.json", apply=apply, receipts_dir=d / "receipts")
        files = list((d / "receipts").glob("channel-config-*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text()), receipt)
        return {r["setting"]: r for r in receipt["rows"]}, receipt

    def test_plan_only_reads_and_reports(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeSession()
            rows, receipt = self.run_cfg(Path(t), fake, apply=False)
            self.assertEqual([c[0] for c in fake.calls], ["GET"])
            self.assertEqual(fake.calls[0][2], {"part": "brandingSettings,snippet,localizations", "mine": "true"})
            self.assertEqual({k: r["status"] for k, r in rows.items()}, {
                "description": "CHANGE", "keywords": "SAME", "country": "CHANGE", "default_language": "REFUSED",
                "unsubscribed_trailer": "REFUSED", "sections": "NOT_APPLIED"})
            self.assertEqual((receipt["mode"], receipt["applied"]), ("plan", False))
            self.assertEqual(receipt["before"]["brandingSettings"], CURRENT)

    def test_apply_sends_only_changed_fields_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeSession()
            rows, receipt = self.run_cfg(Path(t), fake, apply=True)
            self.assertEqual(len(fake.updates), 1)
            self.assertEqual(fake.calls[1][2], {"part": "brandingSettings"})
            sent = fake.updates[0]
            expected = copy.deepcopy(CURRENT)
            expected["channel"].update(description="Fixture description.", country="US")
            self.assertEqual(sent, {"id": pv.CHANNEL, "brandingSettings": expected})  # refused fields untouched
            self.assertEqual(sent["brandingSettings"]["channel"]["defaultLanguage"], "pt")
            self.assertNotIn("unsubscribedTrailer", sent["brandingSettings"]["channel"])
            self.assertEqual(sorted(receipt["changed_fields"]), ["country", "description"])
            self.assertEqual(receipt["after"]["brandingSettings"], expected)
            self.assertTrue(rows["description"]["applied"] and rows["country"]["applied"])

    def test_apply_with_nothing_to_change_makes_no_update(self):
        with tempfile.TemporaryDirectory() as t:
            branding = copy.deepcopy(CURRENT)
            branding["channel"].update(description="Fixture description.", country="US")
            fake = FakeSession(branding)
            _, receipt = self.run_cfg(Path(t), fake, apply=True)
            self.assertEqual(fake.updates, [])
            self.assertFalse(receipt["applied"])

    def test_keywords_list_formatted_and_over_limit_refused(self):
        fixture = copy.deepcopy(FIXTURE)
        fixture["settings"]["keywords"]["value"] = ["night prayer", "psalms"]
        with tempfile.TemporaryDirectory() as t:
            rows, _ = self.run_cfg(Path(t), FakeSession(), apply=False, fixture=fixture)
            self.assertEqual(rows["keywords"]["target"], '"night prayer" psalms')
            self.assertEqual(rows["keywords"]["status"], "CHANGE")
        fixture["settings"]["description"]["value"] = "x" * 1001
        with tempfile.TemporaryDirectory() as t:
            fake = FakeSession()
            rows, _ = self.run_cfg(Path(t), fake, apply=True, fixture=fixture)
            self.assertEqual(rows["description"]["status"], "REFUSED")
            self.assertEqual(fake.updates[0]["brandingSettings"]["channel"]["description"], "Old description.")

    def test_wrong_channel_or_version_refused(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(SystemExit):
                self.run_cfg(Path(t), FakeSession(channel="UCother"), apply=True)
        with tempfile.TemporaryDirectory() as t:
            bad = dict(FIXTURE, version="channel-v0")
            cc.pv.session = lambda: FakeSession()
            (Path(t) / "c.json").write_text(json.dumps(bad))
            with self.assertRaises(SystemExit):
                cc.main(Path(t) / "c.json", apply=True, receipts_dir=Path(t))

    def test_update_not_verified_fails(self):
        class Ignores(FakeSession):
            def put(self, url, params=None, json=None, **kw):
                self.updates.append(json)
                return R(200, json)  # stored nothing
        with tempfile.TemporaryDirectory() as t:
            cc.pv.session = lambda: Ignores()
            (Path(t) / "c.json").write_text(json.dumps(FIXTURE))
            with self.assertRaises(SystemExit) as e:
                cc.main(Path(t) / "c.json", apply=True, receipts_dir=Path(t) / "receipts")
            self.assertIn("CHANNEL_UPDATE_NOT_VERIFIED", str(e.exception))
            self.assertTrue(list((Path(t) / "receipts").glob("channel-config-*.json")))  # receipt still written


if __name__ == "__main__":
    unittest.main()
