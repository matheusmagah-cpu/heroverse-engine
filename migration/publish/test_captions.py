#!/usr/bin/env python3
"""Offline: the uploaded caption track (E107). The SRT is valid and framed exactly; after captions.insert the
publisher reads the track's real status and a failed track fails the run (CAPTIONS_FAILED) instead of passing as
`captions: true`; the automatic ASR track is never taken for ours; channel-privacy.yml's captions-audit lists every
track read-only and captions-repair re-uploads only a reviewed plan. No network, no secret."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration" / "channel"))
import captions  # noqa: E402
import publish_video as pv  # noqa: E402
import preflight as pf  # noqa: E402
import captions_audit as ca  # noqa: E402

VIDEO_BYTES = b"0" * 10
VIDEO_SHA = hashlib.sha256(VIDEO_BYTES).hexdigest()
SENTENCES = [{"start": 0.3, "end": 2.0, "text": "Hi."}, {"start": 2.3, "end": 4.0, "text": "In the beginning."}]


def track(tid, status="serving", kind="standard", language="en", name="English", reason=None, draft=False):
    s = {"videoId": "V", "language": language, "name": name, "trackKind": kind, "isDraft": draft, "status": status,
         "audioTrackType": "unknown", "lastUpdated": "2026-10-25T14:44:00Z"}
    if reason:
        s["failureReason"] = reason
    return {"kind": "youtube#caption", "etag": "e", "id": tid, "snippet": s}


class R:
    def __init__(self, code, body=None, headers=None):
        self.status_code, self._body, self.headers = code, body, headers or {}
        self.content = json.dumps(body).encode() if body is not None else b""
        self.text = self.content.decode()

    def json(self):
        return self._body


class FakeYouTube:
    """captions.list answers `states` in turn after the insert (the last one repeats); `before` is what is listed
    before any insert (for example only the automatic ASR track)."""

    def __init__(self, states=("serving",), before=(), reason=None, uploads=None, videos=None):
        self.calls, self.states, self.before, self.reason = [], list(states), list(before), reason
        self.inserted, self.deleted, self.bodies = None, [], []
        self.uploads, self.videos = uploads or [], videos or {}
        self.listings = 0

    def get(self, url, params=None, **kw):
        what = url.split("/")[-1]
        self.calls.append(("GET", what))
        if what == "channels":
            return R(200, {"items": [{"id": pv.CHANNEL, "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
        if what == "playlists":
            return R(200, {"items": []})
        if what == "playlistItems" and params.get("playlistId") == "UU1":
            return R(200, {"items": [{"contentDetails": {"videoId": v}} for v in self.uploads]})
        if what == "captions":
            self.listings += 1
            items = [t for t in self.before if t["id"] not in self.deleted]
            if self.inserted:
                state = self.states[min(self.listings - 1 - self.listed_before, len(self.states) - 1)]
                items.append(track(self.inserted, state, reason=self.reason if state == "failed" else None))
            if params["videoId"] in self.videos:
                items = self.videos[params["videoId"]]["tracks"]
            return R(200, {"items": items})
        if what == "videos":
            ids = params["id"].split(",")
            return R(200, {"items": [self.video(v) for v in ids]})
        return R(200, {"items": []})

    def video(self, vid):
        v = self.videos.get(vid, {})
        return {"id": vid, "snippet": {"channelId": pv.CHANNEL, "title": v.get("title", "T"),
                                       "publishedAt": "2026-10-25T00:00:00Z", "defaultAudioLanguage": v.get("lang", "en")},
                "status": {"privacyStatus": v.get("privacy", "private"), "uploadStatus": "processed"},
                "contentDetails": {"duration": "PT16M4S"}}

    def post(self, url, params=None, data=None, **kw):
        what = url.split("/")[-1]
        self.calls.append(("POST", what))
        if params and params.get("uploadType") == "resumable":
            return R(200, {}, {"Location": "https://upload/session"})
        if what == "playlists":
            return R(200, {"id": "PL1"})
        if what == "captions":
            self.bodies.append((kw.get("headers"), data))
            self.inserted, self.listed_before = "CAP-NEW", self.listings
            return R(200, track("CAP-NEW", "syncing"))
        return R(200, {})

    def delete(self, url, params=None, **kw):
        self.calls.append(("DELETE", url.split("/")[-1]))
        self.deleted.append(params["id"])
        return R(204)

    def put(self, url, data=None, headers=None):
        self.calls.append(("PUT", headers.get("Content-Range")))
        if headers["Content-Range"].startswith("bytes */"):
            return R(308)
        return R(200, {"id": "VID123"})


def publish(d, fake, sentences=SENTENCES, ledger=None, duration=None):
    pkg, man = d / "p.json", d / "m.json"
    pkg.write_text(json.dumps({"pilot_id": "pilot-x", "title": "T", "description": "D", "tags": ["a"]}))
    m = {"output_sha256": VIDEO_SHA, "sentences": sentences}
    if duration:
        m["output_seconds"] = duration
    man.write_text(json.dumps(m))
    (d / "review.json").write_text(json.dumps({"status": "PASS", "output_sha256": VIDEO_SHA, "watched_review": {
        "status": "PASS", "model": "claude-session-reviewer", "overall": 9.6}}))
    (d / "v.mp4").write_bytes(VIDEO_BYTES)
    (d / "t.jpg").write_bytes(b"jpg")
    if ledger:
        (d / "ledger.json").write_text(json.dumps(ledger))
    error, out = None, io.StringIO()
    with patch.object(pv, "session", return_value=fake), patch.object(captions.time, "sleep", lambda s: None), \
            contextlib.redirect_stdout(out):
        try:
            pv.main(pkg, man, d / "v.mp4", d / "t.jpg", d / "ledger.json", d / "r.json")
        except SystemExit as e:
            error = str(e)
    steps = json.loads((d / "ledger.json").read_text())["entries"][f"pilot-x:{VIDEO_SHA}"]["steps"]
    receipt = json.loads((d / "r.json").read_text()) if (d / "r.json").exists() else None
    return error, steps, receipt, out.getvalue()


class Srt(unittest.TestCase):
    def test_every_published_long_srt_is_valid_and_unchanged(self):
        # the offline evidence of E107: the SRT each prayer long was sent (rebuilt from the manifest whose hash is
        # its ledger key) is valid and byte-identical to what the new builder makes, framing included
        ledger = json.loads((HERE / "ledger.json").read_text())["entries"]
        checked = 0
        for key, entry in ledger.items():
            pilot, sha = key.split(":")[0], key.split(":")[-1]
            if not pilot.startswith("pilot-") or not entry.get("steps", {}).get("captions"):
                continue
            man = json.loads((ROOT / "migration/production" / pilot / "out/manifest.json").read_text())
            self.assertEqual(man["output_sha256"], sha, pilot)
            text = captions.srt(man["sentences"])
            self.assertEqual(captions.problems(text.encode(), man["output_seconds"]), [], pilot)
            meta = {"snippet": {"videoId": entry["video_id"], "language": "en", "name": "English", "isDraft": False}}
            self.assertEqual(captions.parts(captions.multipart(meta, text))[1][1], text.encode(), pilot)
            checked += 1
        self.assertGreaterEqual(checked, 11)

    def test_builder_output_and_shape(self):
        self.assertEqual(pv.srt([{"start": 61.5, "end": 62.25, "text": "x"}]), "1\n00:01:01,500 --> 00:01:02,250\nx\n")
        text = captions.srt([{"start": 0, "end": 1, "text": "a\n\nb"}, {"start": 1, "end": 2, "text": "  "},
                             {"start": 2, "end": 3, "text": "c"}])
        self.assertEqual(text, "1\n00:00:00,000 --> 00:00:01,000\na b\n\n2\n00:00:02,000 --> 00:00:03,000\nc\n")
        self.assertEqual(captions.problems(text), [])

    def test_validator_names_each_defect(self):
        good = captions.srt(SENTENCES)
        cases = {
            "SRT_BOM": "﻿" + good,
            "SRT_CR": good.replace("\n", "\r\n"),
            "SRT_NO_FINAL_NEWLINE": good.rstrip("\n"),
            "SRT_CUE_2_NUMBER": good.replace("\n2\n", "\n3\n"),
            "SRT_CUE_1_TIMING_FORMAT": good.replace("00:00:00,300", "0:00:00.300"),
            "SRT_CUE_2_OVERLAPS_PREVIOUS": good.replace("00:00:02,300", "00:00:01,900"),
            "SRT_CUE_1_NOT_POSITIVE": good.replace("00:00:02,000", "00:00:00,200"),
            "SRT_CUE_2_PAST_VIDEO_END": good,
            "SRT_CUE_2_EMPTY_OR_SHORT": good.replace("In the beginning.\n", ""),
            "SRT_CUE_1_BLANK_LINE_INSIDE": good.replace("Hi.\n", "Hi.\n \n"),
            "SRT_CONTROL_CHARACTERS": good.replace("Hi.", "Hi.\x00"),
            "SRT_EMPTY": "",
        }
        for code, text in cases.items():
            with self.subTest(code=code):
                found = " ".join(captions.problems(text, 3.5 if code == "SRT_CUE_2_PAST_VIDEO_END" else None))
                self.assertIn(code, found)
        self.assertIn("SRT_NOT_UTF8", " ".join(captions.problems(good.encode() + b"\xff\n")))
        self.assertIn("SRT_BOM", " ".join(captions.problems(b"\xef\xbb\xbf" + good.encode())))

    def test_multipart_media_part_is_exactly_the_srt(self):
        text = captions.srt(SENTENCES)
        meta = {"snippet": {"videoId": "V", "language": "en", "name": "English", "isDraft": False}}
        body = captions.multipart(meta, text)
        (h1, c1), (h2, c2) = captions.parts(body)
        self.assertIn("application/json", h1)
        self.assertEqual(json.loads(c1), meta)
        self.assertEqual(c2, text.encode())                        # the CRLF before the delimiter is not content
        self.assertTrue(body.endswith(b"--" + captions.BOUNDARY.encode() + b"--\r\n"))
        with self.assertRaisesRegex(ValueError, "BOUNDARY"):
            captions.multipart(meta, text + "--" + captions.BOUNDARY + "\n")


class Tracks(unittest.TestCase):
    LISTING = {"items": [track("ASR1", "serving", kind="asr"), track("C1", "failed", reason="processingFailed"),
                         track("C2", "serving", language="pt-BR", name="Português")]}

    def test_parser_reads_status_reason_kind_and_draft(self):
        got = captions.tracks(self.LISTING)
        self.assertEqual([(t["id"], t["status"], t["track_kind"]) for t in got],
                         [("ASR1", "serving", "asr"), ("C1", "failed", "standard"), ("C2", "serving", "standard")])
        self.assertEqual(got[1]["failure_reason"], "processingFailed")
        self.assertEqual(captions.ours(got)["id"], "C1")             # never the ASR track
        self.assertEqual(captions.verdict(got), "FAILED")
        self.assertEqual(captions.verdict(captions.tracks({"items": [track("A", kind="asr")]})), "NO_UPLOADED_TRACK")
        self.assertEqual(captions.verdict(captions.tracks({"items": [track("S", "syncing")]})), "SYNCING")
        self.assertEqual(captions.verdict(captions.tracks({"items": [track("D", draft=True)]})), "DRAFT")
        self.assertEqual(captions.tracks({}), [])


class PublishVerifiesTheTrack(unittest.TestCase):
    def test_a_track_that_ends_failed_fails_the_run_and_is_recorded(self):
        # E107 antidote: before, captions.insert's HTTP 200 was recorded as captions: true and nothing read the track
        with tempfile.TemporaryDirectory() as t:
            fake = FakeYouTube(states=("syncing", "failed"), reason="processingFailed")
            error, steps, receipt, log = publish(Path(t), fake)
            self.assertIn("CAPTIONS_FAILED", error or "")
            self.assertEqual(steps["captions_status"], "failed")
            self.assertEqual(steps["captions_track"], "CAP-NEW")
            self.assertEqual(steps["captions_failure_reason"], "processingFailed")
            self.assertEqual(receipt["steps"]["captions_status"], "failed")   # recorded before the run fails

    def test_serving_is_recorded_and_a_rerun_lists_nothing_again(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            error, steps, _, _ = publish(d, FakeYouTube(states=("syncing", "serving")))
            self.assertIsNone(error)
            self.assertEqual((steps["captions"], steps["captions_status"]), (True, "serving"))
            again = FakeYouTube()
            publish(d, again)
            self.assertNotIn(("GET", "captions"), again.calls)
            self.assertNotIn(("POST", "captions"), again.calls)

    def test_the_wait_is_bounded_and_still_syncing_is_a_visible_warning(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeYouTube(states=("syncing",))
            error, steps, _, log = publish(Path(t), fake)
            self.assertIsNone(error)
            self.assertEqual(steps["captions_status"], "syncing")
            self.assertEqual(fake.listings, 1 + captions.WAIT_CALLS)      # the existing-track check, then the bound
            self.assertIn("::warning::CAPTIONS_NOT_YET_SERVING", log)
            self.assertLessEqual(pf.LONG_UNITS, pf.DAY_UNITS)

    def test_a_legacy_entry_is_verified_on_rerun(self):
        # every long published before E107 has captions: true and no status; a re-run reads it
        with tempfile.TemporaryDirectory() as t:
            ledger = {"entries": {f"pilot-x:{VIDEO_SHA}": {"video_id": "VID123", "steps": {
                "thumbnail": True, "captions": True}}}}
            fake = FakeYouTube(videos={"VID123": {"tracks": [track("OLD", "failed", reason="unknownFormat")]}})
            error, steps, _, _ = publish(Path(t), fake, ledger=ledger)
            self.assertIn("CAPTIONS_FAILED", error)
            self.assertEqual((steps["captions_track"], steps["captions_failure_reason"]), ("OLD", "unknownFormat"))

    def test_the_automatic_track_is_never_taken_for_ours(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeYouTube(before=[track("ASR", "serving", kind="asr")])
            error, steps, _, _ = publish(Path(t), fake)
            self.assertIsNone(error)
            self.assertIn(("POST", "captions"), fake.calls)               # before E107 the ASR track skipped this
            self.assertEqual(steps["captions_track"], "CAP-NEW")

    def test_an_invalid_srt_is_refused_before_any_caption_call(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeYouTube()
            error, steps, _, _ = publish(Path(t), fake, duration=3.0)    # the second cue ends at 4.0 s
            self.assertIn("CAPTIONS_SRT_INVALID", error)
            self.assertNotIn(("POST", "captions"), fake.calls)
            self.assertNotIn("captions", steps)

    def test_the_body_sent_is_the_framed_srt(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeYouTube()
            publish(Path(t), fake)
            headers, body = fake.bodies[0]
            self.assertEqual(headers["Content-Type"], f"multipart/related; boundary={captions.BOUNDARY}")
            self.assertEqual(captions.parts(body)[1][1], captions.srt(SENTENCES).encode())

    def test_preflight_refuses_an_srt_past_the_video(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "out").mkdir()
            (d / "out" / "manifest.json").write_text(json.dumps({"sentences": SENTENCES, "output_seconds": 3.0}))
            self.assertTrue(any(p.startswith("CAPTIONS_SRT") for p in pf.caption_problems(d)))
            (d / "out" / "manifest.json").write_text(json.dumps({"sentences": SENTENCES, "output_seconds": 9.0}))
            self.assertEqual(pf.caption_problems(d), [])


class Audit(unittest.TestCase):
    def videos(self):
        return {"AAA": {"title": "Night Prayer", "tracks": [track("C1", "failed", reason="processingFailed"),
                                                            track("A1", kind="asr")]},
                "BBB": {"title": "Genesis", "tracks": [track("A2", kind="asr")]},
                "CCC": {"title": "Morning", "privacy": "public", "tracks": [track("C3")]},
                "PTX": {"title": "Você é amado", "lang": "pt", "tracks": []}}

    def run_audit(self, scope="all", units_max=10000):
        fake = FakeYouTube(uploads=["AAA", "BBB", "CCC", "PTX"], videos=self.videos())
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "audit.json"
            ledger = Path(t) / "ledger.json"
            ledger.write_text(json.dumps({"entries": {"pilot-008:abc": {"video_id": "AAA"},
                                                      "bible:genesis-01-short:def": {"video_id": "BBB"}}}))
            with patch.object(ca, "session", return_value=fake), contextlib.redirect_stdout(io.StringIO()):
                ca.audit(out, ledger, scope, units_max, run_id="123")
            return json.loads(out.read_text()), fake

    def test_lists_every_track_and_its_status_read_only(self):
        record, fake = self.run_audit()
        self.assertEqual({c[0] for c in fake.calls}, {"GET"})                 # read-only: no write of any kind
        by = {v["video_id"]: v for v in record["videos"]}
        self.assertEqual(by["AAA"]["verdict"], "FAILED")
        self.assertEqual(by["AAA"]["source"], "pilot-008")
        self.assertEqual(by["AAA"]["tracks"][0]["failure_reason"], "processingFailed")
        self.assertEqual(by["BBB"]["verdict"], "NO_UPLOADED_TRACK")
        self.assertEqual(by["CCC"]["verdict"], "OK")
        self.assertEqual(record["by_verdict"]["FAILED"], ["AAA"])
        self.assertEqual(record["run_id"], "123")
        text = json.dumps(record)
        for secret in ("token", "refresh", "client_secret", "Bearer", "HERO_YT"):
            self.assertNotIn(secret, text)

    def test_scope_and_unit_cap(self):
        record, _ = self.run_audit(scope="engine")
        self.assertEqual(sorted(v["video_id"] for v in record["videos"]), ["AAA", "BBB"])
        record, _ = self.run_audit(scope="english")
        self.assertNotIn("PTX", [v["video_id"] for v in record["videos"]])
        record, fake = self.run_audit(scope="all", units_max=2 * ca.LIST_UNITS + 2)
        self.assertEqual(fake.listings, 1)                                      # 3 units to list the uploads, then one 50-unit captions.list
        self.assertEqual(len(record["not_audited_unit_cap"]), 3)


class Repair(unittest.TestCase):
    def setup(self, d, tracks, plan_ids=("VID008",), manifest_sha="abc"):
        man = d / "manifest.json"
        man.write_text(json.dumps({"output_sha256": manifest_sha, "output_seconds": 9.0, "sentences": SENTENCES}))
        ledger = d / "ledger.json"
        ledger.write_text(json.dumps({"entries": {"pilot-008:abc": {"video_id": "VID008"}}}))
        plan = d / "plan.json"
        plan.write_text(json.dumps({"channel_id": pv.CHANNEL, "reason": "audit run 1: failed",
                                    "to_repair": [{"video_id": v, "pilot": "pilot-008", "manifest": str(man)}
                                                  for v in plan_ids]}))
        return plan, ledger, FakeYouTube(states=("serving",), before=tracks)

    def run_repair(self, d, plan, ledger, fake):
        out = d / "receipt.json"
        error = None
        with patch.object(ca, "session", return_value=fake), patch.object(captions.time, "sleep", lambda s: None), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                ca.repair(plan, out, ledger, root=Path("/"))
            except SystemExit as e:
                error = str(e)
        return json.loads(out.read_text())["changes"], error

    def test_a_failed_track_is_deleted_reinserted_and_verified(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            plan, ledger, fake = self.setup(d, [track("BAD", "failed", reason="processingFailed"), track("A", kind="asr")])
            changes, error = self.run_repair(d, plan, ledger, fake)
            self.assertIsNone(error)
            self.assertEqual(changes[0]["result"], "REPAIRED")
            self.assertEqual(changes[0]["before"]["status"], "failed")
            self.assertEqual(fake.deleted, ["BAD"])                              # never the ASR track
            self.assertEqual(captions.parts(fake.bodies[0][1])[1][1], captions.srt(SENTENCES).encode())

    def test_a_serving_track_is_left_alone(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            plan, ledger, fake = self.setup(d, [track("GOOD", "serving")])
            changes, error = self.run_repair(d, plan, ledger, fake)
            self.assertEqual((changes[0]["result"], error), ("ALREADY_SERVING", None))
            self.assertEqual([c for c in fake.calls if c[0] != "GET"], [])

    def test_a_video_not_bound_to_its_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            plan, ledger, fake = self.setup(d, [track("BAD", "failed")], manifest_sha="other")
            changes, error = self.run_repair(d, plan, ledger, fake)
            self.assertEqual(changes[0]["result"], "SKIPPED_NOT_IN_LEDGER")
            self.assertEqual(error, "CAPTIONS_REPAIR_INCOMPLETE")
            self.assertEqual([c for c in fake.calls if c[0] != "GET"], [])


class Workflow(unittest.TestCase):
    def test_audit_and_repair_are_explicit_modes_never_run_by_the_clock(self):
        wf = (ROOT / ".github/workflows/channel-privacy.yml").read_text()
        self.assertIn("captions-audit)", wf)
        self.assertIn('migration/channel/captions-audit-$GITHUB_RUN_ID.json', wf)
        self.assertIn("captions-repair) test -f migration/channel/captions-repair-plan.json", wf)
        self.assertIn("default: plan", wf)                                      # a dispatch with no mode only plans
        hb = (ROOT / "migration/ops/heartbeat.py").read_text()
        self.assertNotIn("captions-", hb)
        self.assertNotIn("captions-repair-plan.json", [p.name for p in (ROOT / "migration/channel").iterdir()])


if __name__ == "__main__":
    unittest.main()
