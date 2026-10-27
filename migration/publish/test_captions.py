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
import channel_privacy as cp  # noqa: E402

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
                                       "publishedAt": "2026-10-25T00:00:00Z", "defaultAudioLanguage": v.get("lang", "en"),
                                       "description": ""},
                "status": {"privacyStatus": v.get("privacy", "private"), "uploadStatus": "processed"},
                "contentDetails": {"duration": "PT16M4S"}}

    def post(self, url, params=None, data=None, **kw):
        what = url.split("/")[-1]
        self.calls.append(("POST", what))
        if what == "captions" and getattr(self, "insert_raises", None):
            raise self.insert_raises
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


def publish(d, fake, sentences=SENTENCES, ledger=None, duration=None, extra=None, qa=None):
    pkg, man = d / "p.json", d / "m.json"
    pkg.write_text(json.dumps({"pilot_id": "pilot-x", "title": "T", "description": "D", "tags": ["a"]}))
    m = {"output_sha256": VIDEO_SHA, "sentences": sentences, **(extra or {})}
    if duration:
        m["output_seconds"] = duration
    man.write_text(json.dumps(m))
    if qa is not None:
        (d / "qa.json").write_text(json.dumps(qa))
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
    steps = json.loads((d / "ledger.json").read_text())["entries"][f"pilot-x:{VIDEO_SHA}"]["steps"] \
        if (d / "ledger.json").exists() else None
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
        self.assertEqual(captions.srt([{"start": 61.5, "end": 62.25, "text": "x"}]), "1\n00:01:01,500 --> 00:01:02,250\nx\n")
        self.assertFalse(hasattr(pv, "srt"))                         # one builder: captions.srt (review of #424)
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

    def test_the_last_cue_may_end_on_the_videos_rounded_end(self):
        # review of #424: the stamp is rounded to the millisecond, the duration was not
        text = captions.srt([{"start": 0.0, "end": 3.9996, "text": "End."}])
        self.assertEqual(text.splitlines()[1], "00:00:00,000 --> 00:00:04,000")
        self.assertEqual(captions.problems(text, 3.9996), [])
        self.assertIn("PAST_VIDEO_END", " ".join(captions.problems(text, 3.9984)))

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

    def legacy(self, d, states, status=None):
        steps = {"thumbnail": True, "captions": True}
        if status:
            steps.update({"captions_track": "OLD", "captions_status": status, "captions_failure_reason": "unknownFormat"})
        ledger = {"entries": {f"pilot-x:{VIDEO_SHA}": {"video_id": "VID123", "steps": steps}}}
        fake = FakeYouTube(states=states, before=[track("OLD", "failed", reason="unknownFormat"),
                                                  track("ASR", kind="asr")], reason="processingFailed")
        return fake, publish(d, fake, ledger=ledger)

    def test_a_legacy_failed_track_is_replaced_once_and_verified(self):
        # every long published before E107 has captions: true and no status; a re-run reads it and, failed, re-inserts
        with tempfile.TemporaryDirectory() as t:
            fake, (error, steps, receipt, _) = self.legacy(Path(t), ("serving",))
            self.assertIsNone(error)
            self.assertEqual(fake.deleted, ["OLD"])                               # ours only, never the ASR track
            self.assertEqual((steps["captions_track"], steps["captions_status"]), ("CAP-NEW", "serving"))
            self.assertNotIn("captions_failure_reason", steps)
            self.assertEqual(fake.calls.count(("POST", "captions")), 1)

    def test_a_recorded_failure_is_retried_once_per_run_and_never_blocks_forever(self):
        # review of #424: a recorded failed status used to fail every re-run with no way out
        with tempfile.TemporaryDirectory() as t:
            fake, (error, steps, _, _) = self.legacy(Path(t), ("serving",), status="failed")
            self.assertIsNone(error)
            self.assertEqual((steps["captions_track"], steps["captions_status"]), ("CAP-NEW", "serving"))
            self.assertEqual(fake.calls.count(("POST", "captions")), 1)
        with tempfile.TemporaryDirectory() as t:
            fake, (error, steps, receipt, _) = self.legacy(Path(t), ("failed",), status="failed")
            self.assertIn("CAPTIONS_FAILED", error)
            self.assertEqual(fake.calls.count(("POST", "captions")), 1)           # at most one insert a run
            self.assertEqual((steps["captions_track"], steps["captions_status"]), ("CAP-NEW", "failed"))
            self.assertEqual(receipt["steps"]["captions_status"], "failed")

    def test_the_automatic_track_is_never_taken_for_ours(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeYouTube(before=[track("ASR", "serving", kind="asr")])
            error, steps, _, _ = publish(Path(t), fake)
            self.assertIsNone(error)
            self.assertIn(("POST", "captions"), fake.calls)               # before E107 the ASR track skipped this
            self.assertEqual(steps["captions_track"], "CAP-NEW")

    def test_an_invalid_srt_refuses_a_new_upload_before_the_session(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeYouTube()
            error, steps, _, _ = publish(Path(t), fake, duration=3.0)    # the second cue ends at 4.0 s
            self.assertIn("CAPTIONS_SRT_INVALID", error)
            self.assertEqual(fake.calls, [])                              # no upload, no call at all
            self.assertIsNone(steps)

    def test_an_invalid_srt_on_a_resumed_upload_is_a_warning_and_the_chain_goes_on(self):
        # review of #424: a legacy manifest that fails the strict check must not block the run forever
        with tempfile.TemporaryDirectory() as t:
            ledger = {"entries": {f"pilot-x:{VIDEO_SHA}": {"video_id": "VID123", "steps": {"thumbnail": True}}}}
            fake = FakeYouTube()
            error, steps, receipt, log = publish(Path(t), fake, ledger=ledger, duration=3.0)
            self.assertIsNone(error)
            self.assertNotIn(("POST", "captions"), fake.calls)            # never an invalid track
            self.assertNotIn("captions", steps)                            # left for the repair path
            self.assertIn("PAST_VIDEO_END", steps["captions_srt_invalid"])
            self.assertIn("::warning::CAPTIONS_SRT_INVALID", log)
            self.assertEqual(receipt["video_id"], "VID123")
        with tempfile.TemporaryDirectory() as t:                           # a recorded failure, SRT invalid
            ledger = {"entries": {f"pilot-x:{VIDEO_SHA}": {"video_id": "VID123", "steps": {
                "thumbnail": True, "captions": True, "captions_track": "OLD", "captions_status": "failed"}}}}
            fake = FakeYouTube(before=[track("OLD", "failed")])
            error, steps, _, log = publish(Path(t), fake, ledger=ledger, duration=3.0)
            self.assertIsNone(error)
            self.assertEqual(fake.deleted, [])
            self.assertNotIn(("POST", "captions"), fake.calls)
            self.assertIn("::warning::CAPTIONS_SRT_INVALID", log)

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
            self.assertTrue(any(p.startswith("CAPTIONS_SRT") for p in pf.caption_problems({"sentences": SENTENCES,
                                                                                            "output_seconds": 3.0})))
            self.assertEqual(pf.caption_problems({"sentences": SENTENCES, "output_seconds": 9.0}), [])


class Audit(unittest.TestCase):
    def videos(self):
        return {"AAA": {"title": "Night Prayer", "tracks": [track("C1", "failed", reason="processingFailed"),
                                                            track("A1", kind="asr")]},
                "BBB": {"title": "Genesis", "tracks": [track("A2", kind="asr")]},
                "CCC": {"title": "Morning", "privacy": "public", "tracks": [track("C3")]},
                "PTX": {"title": "Você é amado", "lang": "pt", "tracks": []},
                "PTN": {"title": "Você não está sozinha, Deus está com você", "lang": None, "tracks": []}}

    def run_audit(self, scope="all", units_max=10000):
        fake = FakeYouTube(uploads=["AAA", "BBB", "CCC", "PTX", "PTN"], videos=self.videos())
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "audit.json"
            ledger = Path(t) / "ledger.json"
            ledger.write_text(json.dumps({"entries": {"pilot-008:abc": {"video_id": "AAA"},
                                                      "bible:genesis-01-short:def": {"video_id": "BBB"}}}))
            with patch.object(ca, "session", return_value=fake), contextlib.redirect_stdout(io.StringIO()), \
                    patch.object(cp, "channel_uploads", wraps=cp.channel_uploads) as shared:
                ca.audit(out, ledger, scope, units_max, run_id="123")
            self.assertEqual(shared.call_count, 1)                              # one paging helper (review of #424)
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
        self.assertEqual(sorted(v["video_id"] for v in record["videos"]), ["AAA", "BBB", "CCC"])   # cp.language's rule
        record, fake = self.run_audit(scope="all", units_max=2 * ca.LIST_UNITS + 2)
        self.assertEqual(fake.listings, 1)                                      # 3 units to list the uploads, then one 50-unit captions.list
        self.assertEqual(len(record["not_audited_unit_cap"]), 4)


class Repair(unittest.TestCase):
    def setup(self, d, tracks, plan_ids=("VID008",), manifest_sha="abc"):
        man = d / "manifest.json"
        man.write_text(json.dumps({"output_sha256": manifest_sha, "output_seconds": 9.0, "sentences": SENTENCES}))
        ledger = d / "ledger.json"
        ledger.write_text(json.dumps({"entries": {"pilot-008:abc": {"video_id": "VID008", "steps": {
            "thumbnail": True, "captions": True, "captions_track": "BAD", "captions_status": "failed",
            "captions_failure_reason": "processingFailed"}}}}))
        plan = d / "plan.json"
        plan.write_text(json.dumps({"channel_id": pv.CHANNEL, "reason": "audit run 1: failed",
                                    "to_repair": [{"video_id": v, "pilot": "pilot-008", "manifest": str(man)}
                                                  for v in plan_ids]}))
        return plan, ledger, FakeYouTube(states=("serving",), before=tracks)

    def run_repair(self, d, plan, ledger, fake):
        out = d / "receipt.json"
        error = None
        self.out = out
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
            # review of #424: the ledger follows the repair, so publish_video never polls the deleted track
            steps = json.loads(ledger.read_text())["entries"]["pilot-008:abc"]["steps"]
            self.assertEqual((steps["captions_track"], steps["captions_status"]), ("CAP-NEW", "serving"))
            self.assertNotIn("captions_failure_reason", steps)

    def test_the_receipt_is_written_after_each_delete_and_insert(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            plan, ledger, fake = self.setup(d, [track("BAD", "failed")])
            fake.insert_raises = RuntimeError("CAPTIONS_HTTP_500")
            with patch.object(ca, "session", return_value=fake), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    ca.repair(plan, d / "receipt.json", ledger, root=Path("/"))
            row = json.loads((d / "receipt.json").read_text())["changes"][0]
            self.assertEqual((row["video_id"], row["result"], row["deleted"]), ("VID008", "DELETED_NOT_REINSERTED", "BAD"))
            steps = json.loads(ledger.read_text())["entries"]["pilot-008:abc"]["steps"]
            self.assertEqual(steps["captions_status"], "deleted")              # the ledger knows the track is gone

    def test_a_plan_longer_than_the_job_can_wait_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            plan, ledger, fake = self.setup(d, [], plan_ids=["V%d" % i for i in range(ca.MAX_PLAN + 1)])
            with patch.object(ca, "session", return_value=fake), self.assertRaisesRegex(SystemExit, "PLAN_TOO_LONG"):
                ca.repair(plan, d / "receipt.json", ledger, root=Path("/"))
            self.assertEqual(fake.calls, [])
        wf = (ROOT / ".github/workflows/channel-privacy.yml").read_text()
        minutes = int(wf.split("timeout-minutes:")[1].split()[0])
        self.assertEqual(ca.JOB_SECONDS, minutes * 60)
        self.assertGreaterEqual(ca.MAX_PLAN, 1)
        self.assertLessEqual(ca.MAX_PLAN * ca.SECONDS_PER_TRACK + ca.MARGIN_SECONDS, ca.JOB_SECONDS)

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
        self.assertIn("git add migration/channel migration/publish/ledger.json", wf)   # the repair's ledger update


class SharedUploads(unittest.TestCase):
    def test_plan_and_audit_page_the_uploads_through_one_helper(self):
        pages = {None: {"items": [{"contentDetails": {"videoId": "A"}}], "nextPageToken": "p2"},
                 "p2": {"items": [{"contentDetails": {"videoId": "B"}}]}}
        seen = []

        def get(endpoint, params):
            seen.append(endpoint)
            if endpoint == "channels":
                return {"items": [{"id": cp.CHANNEL, "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
            if endpoint == "playlistItems":
                return pages[params.get("pageToken")]
            return {"items": [{"id": i, "snippet": {"title": "t", "publishedAt": "x"}, "status": {"privacyStatus": "public"},
                               "contentDetails": {}} for i in params["id"].split(",")]}
        videos, calls = cp.channel_uploads(get, "snippet,status")
        self.assertEqual(([v["id"] for v in videos], calls), (["A", "B"], 4))
        with self.assertRaisesRegex(SystemExit, "CHANNEL_IDENTITY_MISMATCH"):
            cp.channel_uploads(lambda e, p: {"items": [{"id": "UCother"}]}, "snippet")
        with tempfile.TemporaryDirectory() as t, patch.object(cp, "token", return_value="x"), \
                patch.object(cp, "call", lambda tok, method, endpoint, params, body=None: get(endpoint, params)), \
                patch.object(cp, "channel_uploads", wraps=cp.channel_uploads) as shared, \
                contextlib.redirect_stdout(io.StringIO()):
            cp.plan(Path(t) / "plan.json")
            self.assertEqual(shared.call_count, 1)
            self.assertEqual(json.loads((Path(t) / "plan.json").read_text())["uploads"], 2)


LONG = [{"segment": "n00", "speaker": "eve", "start": 0.0, "end": 5.8,
         "text": "He says you will not die. He says your eyes will be opened, and you will see."},
        {"segment": "n01", "start": 6.4, "end": 10.6, "text": "In the beginning God created the heaven and the earth."}]


class LongTrack(unittest.TestCase):
    """E126: the acted Bible long (story QA v3) uploads an .srt of short cues (<= 7 words, <= 44 characters), the
    script's words exact, on their voice timings; publish_video uploads exactly the recorded track."""

    def test_cues_keep_every_word_and_stay_inside_their_sentence(self):
        words_max, chars_max = captions.v3_limits()
        self.assertEqual((words_max, chars_max), (7, 44))                 # the frozen v3 rows
        got = captions.cues(LONG, words_max, chars_max)
        self.assertEqual(" ".join(c["text"] for c in got).split(), " ".join(s["text"] for s in LONG).split())
        self.assertTrue(all(len(c["text"].split()) <= 7 and len(c["text"]) <= 44 for c in got))
        for c in got:
            self.assertTrue(any(s["start"] <= c["start"] < c["end"] <= s["end"] for s in LONG), c)
        text, rec = captions.track_record(LONG)
        self.assertEqual(captions.problems(text), [])
        self.assertEqual((rec["sha256"], rec["words_max"], rec["chars_max"], rec["burned"]),
                         (hashlib.sha256(text.encode()).hexdigest(), 7, 44, False))
        self.assertEqual(captions.manifest_srt({"sentences": LONG, "caption_track": rec}), text)
        self.assertEqual(captions.manifest_srt({"sentences": LONG}), captions.srt(LONG))   # prayer longs unchanged

    def test_the_long_writer_writes_the_srt_and_its_record(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "timeline.json").write_text(json.dumps({"sentences": LONG}))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(captions.write_long(d / "timeline.json", d / "captions.srt"), 0)
            rec = json.loads(out.getvalue())["caption_track"]
            self.assertEqual(hashlib.sha256((d / "captions.srt").read_bytes()).hexdigest(), rec["sha256"])
            man = {"sentences": LONG, "caption_track": rec}
            self.assertEqual(captions.manifest_problems(man, d), [])
            (d / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n")
            self.assertTrue(any(p.startswith("CAPTION_TRACK_FILE_DIFFERS") for p in captions.manifest_problems(man, d)))
            for name in ("../captions.srt", "/etc/hostname", "sub/captions.srt", ".."):   # never a path out
                self.assertTrue(any(p.startswith("CAPTION_TRACK_FILE_MISSING") for p in captions.manifest_problems(
                    {"sentences": LONG, "caption_track": {**rec, "file": name}}, d)), name)
            self.assertTrue(any(p.startswith("CAPTION_TRACK_SHA256") for p in captions.manifest_problems(
                {"sentences": LONG, "caption_track": {**rec, "sha256": "0" * 64}})))

    def test_the_cue_limits_are_the_frozen_ones_never_the_records(self):
        # review of #469: the record cannot loosen v3's limits, and a record without them is a refusal, not a KeyError
        text, rec = captions.track_record(LONG)
        for loose in ({**rec, "words_max": 20, "chars_max": 120}, {k: v for k, v in rec.items() if k != "words_max"}):
            man = {"sentences": LONG, "caption_track": loose}
            self.assertEqual(captions.manifest_srt(man), text)                 # built at the frozen 7 / 44
            self.assertTrue(any(p.startswith("CAPTION_TRACK_LIMITS") for p in captions.manifest_problems(man)), loose)
        self.assertEqual(captions.track_srt(LONG, {}), text)

    def test_an_over_long_word_is_its_own_cue_and_no_cue_is_too_short(self):
        # review of #469: one word over 44 characters split the whole sentence into one-word cues; a short voice
        # span gave cues of 0 ms
        word = "x" * 50
        sent = [{"start": 0.0, "end": 6.0, "text": f"In the beginning God created {word} and the heaven and the earth."}]
        got = captions.cues(sent, 7, 44)
        self.assertIn(word, [c["text"] for c in got])
        self.assertLessEqual(len(got), 4)
        self.assertEqual(" ".join(c["text"] for c in got).split(), sent[0]["text"].split())
        tight = [{"start": 1.0, "end": 1.6, "text": "And God said, Let there be light: and there was light, and it was good."}]
        got = captions.cues(tight, 7, 44)
        self.assertTrue(all(c["end"] - c["start"] >= captions.CUE_MIN_SECONDS - 1e-9 for c in got), got)
        self.assertEqual(" ".join(c["text"] for c in got).split(), tight[0]["text"].split())
        self.assertEqual(captions.problems(captions.srt(got)), [])

    def test_publish_uploads_the_recorded_short_cue_track(self):
        text, rec = captions.track_record(LONG)
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "captions.srt").write_text(text)
            fake = FakeYouTube()
            error, steps, _, _ = publish(d, fake, sentences=LONG, extra={"caption_track": rec},
                                         qa={"criteria_version": "story-qa-criteria-v3"})
            self.assertIsNone(error)
            self.assertEqual(captions.parts(fake.bodies[0][1])[1][1], text.encode())
            self.assertNotEqual(text, captions.srt(LONG))                    # not the one-cue-per-sentence track
            self.assertEqual(steps["captions_track"], "CAP-NEW")

    def test_a_v3_long_without_its_track_or_with_another_file_is_never_uploaded(self):
        with tempfile.TemporaryDirectory() as t:
            fake = FakeYouTube()
            error, steps, _, _ = publish(Path(t), fake, sentences=LONG, qa={"criteria_version": "story-qa-criteria-v3"})
            self.assertIn("CAPTIONS_TRACK_MISSING", error)
            self.assertEqual((fake.calls, steps), ([], None))
        text, rec = captions.track_record(LONG)
        with tempfile.TemporaryDirectory() as t:
            fake = FakeYouTube()                                          # the record names a file that is not there
            error, _, _, _ = publish(Path(t), fake, sentences=LONG, extra={"caption_track": rec},
                                     qa={"criteria_version": "story-qa-criteria-v3"})
            self.assertIn("CAPTION_TRACK_FILE_MISSING", error)
            self.assertEqual(fake.calls, [])
        with tempfile.TemporaryDirectory() as t:                           # older criteria: the old track, as before
            fake = FakeYouTube()
            error, _, _, _ = publish(Path(t), fake, sentences=LONG, qa={"criteria_version": "story-qa-criteria-v1"})
            self.assertIsNone(error)
            self.assertEqual(captions.parts(fake.bodies[0][1])[1][1], captions.srt(LONG).encode())

    def test_a_bible_long_without_its_track_is_refused_even_without_qa(self):
        # review of #469: the refusal no longer depends on out/qa.json being readable
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "pilot-015"
            (d / "out").mkdir(parents=True)
            (d / "script.json").write_text(json.dumps({"archetype": "bible-story-long"}))
            man = d / "out" / "manifest.json"
            self.assertTrue(pv.caption_track_missing(man, {"sentences": LONG}, {}, d))
            self.assertTrue(pv.caption_track_missing(man, {"sentences": LONG}, {"series": "bible"}))
            _, rec = captions.track_record(LONG)
            self.assertFalse(pv.caption_track_missing(man, {"sentences": LONG, "caption_track": rec}, {}, d))
            (d / "script.json").write_text(json.dumps({"archetype": "prayer"}))
            self.assertFalse(pv.caption_track_missing(man, {"sentences": LONG}, {}, d))
        with tempfile.TemporaryDirectory() as t:                 # through main: refused before any call
            fake = FakeYouTube()
            with patch.object(pv, "bible_thumb_problems", return_value=[]), \
                    patch.object(pv, "bible_long", return_value=True):
                error, steps, _, _ = publish(Path(t), fake, sentences=LONG)
            self.assertIn("CAPTIONS_TRACK_MISSING", error)
            self.assertEqual((fake.calls, steps), ([], None))

    def test_preflight_checks_the_track_publish_will_send(self):
        text, rec = captions.track_record(LONG)
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            man = {"sentences": LONG, "caption_track": rec, "output_seconds": 11.0}
            self.assertTrue(any("CAPTION_TRACK_FILE_MISSING" in p for p in pf.caption_problems(man, d)))
            (d / "captions.srt").write_text(text)
            self.assertEqual(pf.caption_problems(man, d), [])


if __name__ == "__main__":
    unittest.main()
