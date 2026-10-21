#!/usr/bin/env python3
"""Offline checks of the Shorts publication: slots only for Shorts still to upload, never a duplicate upload,
and the state of every Short (failed / not selected / approved awaiting slot / scheduled / published)."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_shorts as ps  # noqa: E402
import publish_shorts as pub  # noqa: E402


class Resp:
    def __init__(self, data):
        self.data = data


class FakeYouTube:
    def __init__(self):
        self.uploads = []

    def get(self, url, params=None, timeout=None):
        if url.endswith("channels"):
            return Resp({"items": [{"id": pub.pv.CHANNEL}]})
        if params.get("part") == "snippet":
            return Resp({"items": [{"snippet": {"title": "Long"}}]})
        return Resp({"items": [{"status": {"uploadStatus": "uploaded"}}]})


def setup(t, done):
    d = Path(t)
    files = {}
    for i in range(3):
        data = f"short {i}".encode()
        (d / f"short-0{i}.mp4").write_bytes(data)
        files[i] = hashlib.sha256(data).hexdigest()
    shorts = [{"file": f"short-0{i}.mp4", "sha256": files[i], "hook": "Hook.", "title": f"T{i}", "publish": True,
               "review": {"status": "PASS", "model": "gemini-3.8-flash", "overall": 9.0, "output_sha256": files[i]}, "qa": {"status": "PASS"}} for i in range(3)]
    (d / "shorts.json").write_text(json.dumps({"source_pilot": "pilot-009", "shorts": shorts}))
    entries = {"pilot-009:L": {"video_id": "LONG"}}
    entries.update({f"short:pilot-009:{files[i]}": {"video_id": f"OLD{i}", "slot": "2026-10-18T14:00:00Z"} for i in done})
    (d / "ledger.json").write_text(json.dumps({"entries": entries}))
    return d, files


class PublishShorts(unittest.TestCase):
    def setUp(self):
        self.yt = FakeYouTube()
        self.real = (pub.pv.session, pub.pv.check, pub.pv.upload, pub.shorts_qa.check, pub.utc_now)
        pub.utc_now = lambda: datetime(2026, 10, 18, tzinfo=timezone.utc)
        pub.pv.session = lambda: self.yt
        pub.pv.check = lambda r, what: r.data
        pub.pv.upload = lambda s, path, body: (self.yt.uploads.append((path.name, body["status"]["publishAt"])), {"id": "NEW-" + path.name})[1]
        pub.shorts_qa.check = lambda path: {"status": "PASS"}

    def tearDown(self):
        pub.pv.session, pub.pv.check, pub.pv.upload, pub.shorts_qa.check, pub.utc_now = self.real

    def run_pub(self, d, slots):
        pub.main(str(d / "shorts.json"), str(d), "pilot-009:L", str(d / "ledger.json"), str(d / "receipt.json"), slots)
        return json.loads((d / "receipt.json").read_text())

    def test_owner_floor_blocks_stale_flags_and_low_score_before_session(self):
        for score in (8.5, 8.99, True, float("nan"), float("inf"), 11, None):
            with self.subTest(score=score), tempfile.TemporaryDirectory() as t:
                d, _ = setup(t, done=())
                spec = json.loads((d / "shorts.json").read_text())
                spec["shorts"][0]["review"]["overall"] = score
                spec["shorts"][0]["owner_quality_policy"] = {"status": "PASS"}
                (d / "shorts.json").write_text(json.dumps(spec))
                with patch.object(pub.pv, "session") as session, self.assertRaises(SystemExit):
                    self.run_pub(d, "2026-10-21T14:00:00Z,2026-10-21T20:00:00Z,2026-10-21T23:00:00Z")
                session.assert_not_called()
                self.assertFalse(self.yt.uploads)

    def test_existing_low_score_false_flag_missing_file_still_readback(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=(0, 1, 2))
            spec = json.loads((d / "shorts.json").read_text())
            for rec in spec["shorts"]:
                rec["publish"] = False
                rec["review"]["overall"] = 8.5
                (d / rec["file"]).unlink()
            (d / "shorts.json").write_text(json.dumps(spec))
            result = self.run_pub(d, "")
            self.assertEqual(len(result["shorts"]), 3)
            self.assertFalse(self.yt.uploads)

    def test_partial_earlier_run_needs_slots_only_for_the_rest(self):
        with tempfile.TemporaryDirectory() as t:
            d, files = setup(t, done=(0,))
            (d / "short-00.mp4").unlink()  # already on YouTube, file deleted from the release
            r = self.run_pub(d, "2026-10-19T14:00:00Z,2026-10-19T20:00:00Z")
            self.assertEqual(self.yt.uploads, [("short-01.mp4", "2026-10-19T14:00:00Z"), ("short-02.mp4", "2026-10-19T20:00:00Z")])
            self.assertEqual([x["video_id"] for x in r["shorts"]], ["OLD0", "NEW-short-01.mp4", "NEW-short-02.mp4"])

    def test_rerun_after_everything_uploaded_uploads_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=(0, 1, 2))
            self.run_pub(d, "")
            self.assertEqual(self.yt.uploads, [])

    def test_too_few_slots_still_fails_loudly(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            with self.assertRaises(SystemExit) as e:
                self.run_pub(d, "2026-10-19T14:00:00Z")
            self.assertIn("NOT_ENOUGH_SLOTS", str(e.exception))
            self.assertEqual(self.yt.uploads, [])

    def test_pending_id_is_durable_before_readback_and_rerun_never_uploads(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            real_observe = pub.observe_video
            def observe(session, video_id):
                ledger = json.loads((d / "ledger.json").read_text())
                receipt = json.loads((d / "receipt.json").read_text())
                self.assertTrue(any(x.get("video_id") == video_id for x in ledger["entries"].values()))
                self.assertEqual(receipt["shorts"][-1]["video_id"], video_id)
                return real_observe(session, video_id)
            with patch.object(pub, "observe_video", side_effect=observe):
                self.run_pub(d, ",".join(["2026-10-20T20:00:00Z"] * 3))
            self.assertEqual(len(self.yt.uploads), 3)
            self.yt.uploads.clear()
            self.run_pub(d, "")
            self.assertEqual(self.yt.uploads, [])

    def test_atomic_persistence_failure_stops_before_readback(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            with patch.object(pub, "atomic_json", side_effect=OSError("disk")), patch.object(pub, "observe_video") as read:
                with self.assertRaises(OSError):
                    self.run_pub(d, ",".join(["2026-10-20T20:00:00Z"] * 3))
                read.assert_not_called()

    def test_past_new_upload_slot_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            with self.assertRaisesRegex(SystemExit, "INVALID_OR_PAST_UPLOAD_SLOT"):
                self.run_pub(d, ",".join(["2026-10-17T20:00:00Z"] * 3))
            self.assertEqual(self.yt.uploads, [])

    def test_true_pending_then_success_same_id_and_error_are_persisted(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            original_get = self.yt.get
            stage = ["processing"]
            def get(url, params=None, timeout=None):
                if params.get("part") != "id,snippet,status,processingDetails":
                    return original_get(url, params, timeout)
                if stage[0] == "timeout":
                    raise TimeoutError("credential never recorded")
                i = int(params["id"].split("short-0")[1].split(".")[0])
                short = json.loads((d / "shorts.json").read_text())["shorts"][i]
                return Resp({"items": [{"id": params["id"], "snippet": {
                    "channelId": pub.pv.CHANNEL, "title": pub.title_for(short),
                    "description": pub.description_for(short, "https://youtu.be/LONG", "Long"),
                    "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                    "status": {"uploadStatus": "uploaded" if stage[0] == "processing" else "processed",
                               "privacyStatus": "private", "publishAt": "2026-10-20T20:00:00+00:00",
                               "license": "youtube", "containsSyntheticMedia": True},
                    "processingDetails": {"processingStatus": stage[0]}}]})
            self.yt.get = get
            first = self.run_pub(d, ",".join(["2026-10-20T20:00:00Z"] * 3))
            self.assertTrue(all(x["verification_status"] == "PENDING_PROCESSING" for x in first["shorts"]))
            ids = [x["video_id"] for x in first["shorts"]]
            self.yt.uploads.clear()
            stage[0] = "succeeded"
            second = self.run_pub(d, "")
            self.assertEqual([x["video_id"] for x in second["shorts"]], ids)
            self.assertTrue(all(x["verification_status"] == "SCHEDULED_VERIFIED" for x in second["shorts"]))
            self.assertEqual(self.yt.uploads, [])
            stage[0] = "timeout"
            third = self.run_pub(d, "")
            self.assertTrue(all(x["verification_status"] == "VERIFICATION_UNKNOWN" for x in third["shorts"]))
            self.assertNotIn("credential", json.dumps(third))
            ledger = json.loads((d / "ledger.json").read_text())
            self.assertTrue(all(x["verification"]["status"] == "VERIFICATION_UNKNOWN" for k, x in ledger["entries"].items() if k.startswith("short:")))
            self.assertEqual(self.yt.uploads, [])

    def test_existing_id_cannot_verify_wrong_ledger_slot_against_itself(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=(0, 1, 2))
            spec = json.loads((d / "shorts.json").read_text())
            spec["finalization"] = {"status": "COMPLETE", "target_slot": "2026-10-20T20:00:00Z"}
            (d / "shorts.json").write_text(json.dumps(spec))
            ledger = json.loads((d / "ledger.json").read_text())
            for key, entry in ledger["entries"].items():
                if key.startswith("short:"):
                    entry["slot"] = "2026-10-20T23:00:00Z"
            (d / "ledger.json").write_text(json.dumps(ledger))
            def observed(session, video_id):
                short = spec["shorts"][int(video_id[-1])]
                return {"video_id": video_id, "channel_id": pub.pv.CHANNEL,
                        "title": pub.title_for(short), "description": pub.description_for(short, "https://youtu.be/LONG", "Long"),
                        "default_language": "en", "default_audio_language": "en", "license": "youtube",
                        "contains_synthetic_media": True, "upload_status": "processed", "processing_status": "succeeded",
                        "privacy_status": "private", "publish_at": "2026-10-20T23:00:00Z"}, None
            with patch.object(pub, "observe_video", side_effect=observed):
                receipt = self.run_pub(d, "2026-10-20T20:00:00Z")
            self.assertTrue(all(x["verification_status"] == "VERIFICATION_FAIL" for x in receipt["shorts"]))
            self.assertTrue(all(x["verification_reason"] == "AUTHORIZED_TARGET_SLOT_MISMATCH" for x in receipt["shorts"]))
            self.assertEqual(self.yt.uploads, [])
            persisted = json.loads((d / "ledger.json").read_text())
            self.assertTrue(all(x["slot"] == "2026-10-20T23:00:00Z" for k, x in persisted["entries"].items() if k.startswith("short:")))

    def test_existing_id_cannot_invent_or_replace_output_hash_binding(self):
        for recorded, want, reason in (("f" * 64, "VERIFICATION_FAIL", "OUTPUT_SHA256_MISMATCH"),
                                       (None, "VERIFICATION_UNKNOWN", "OUTPUT_SHA256_UNRECORDED")):
            with self.subTest(recorded=recorded), tempfile.TemporaryDirectory() as t:
                d, _ = setup(t, done=(0, 1, 2))
                ledger = json.loads((d / "ledger.json").read_text())
                for key, entry in ledger["entries"].items():
                    if key.startswith("short:") and recorded is not None:
                        entry["output_sha256"] = recorded
                (d / "ledger.json").write_text(json.dumps(ledger))
                with patch.object(pub, "verification", return_value=("PUBLIC_VERIFIED", None)):
                    receipt = self.run_pub(d, "")
                self.assertEqual(self.yt.uploads, [])
                self.assertTrue(all(x["verification_status"] == want and x["verification_reason"] == reason
                                    for x in receipt["shorts"]))
                self.assertTrue(all(x["output_sha256"] == recorded for x in receipt["shorts"]))
                saved = json.loads((d / "ledger.json").read_text())
                self.assertTrue(all(x.get("output_sha256") == recorded for k, x in saved["entries"].items()
                                    if k.startswith("short:")))

    def test_new_phase2_upload_cannot_use_different_explicit_slot(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            spec = json.loads((d / "shorts.json").read_text())
            spec["finalization"] = {"target_slot": "2026-10-20T20:00:00Z"}
            (d / "shorts.json").write_text(json.dumps(spec))
            with self.assertRaisesRegex(SystemExit, "UPLOAD_SLOT_DIFFERS_FROM_AUTHORIZED_TARGET"):
                self.run_pub(d, ",".join(["2026-10-20T23:00:00Z"] * 3))
            self.assertEqual(self.yt.uploads, [])


class WorkflowGuard(unittest.TestCase):
    def test_refresh_and_manifest_guard_precede_publisher(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/publish-shorts.yml").read_text()
        call = workflow.index('"$RUNNER_TEMP/venv/bin/python" -I -B migration/publish/publish_shorts.py')
        for required in ("git fetch -q origin main", "git merge --ff-only FETCH_HEAD", "APPROVED_MANIFEST_CHANGED", "migration/publish/shorts_prerequisite.py"):
            self.assertLess(workflow.index(required), call)
        self.assertIn('[ "$expected" = "$actual" ] || { echo APPROVED_MANIFEST_CHANGED; exit 1; }', workflow)

    def test_remote_persistence_before_verified_only_cleanup(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/publish-shorts.yml").read_text()
        persist = workflow.index("- name: Record ledger and receipt")
        cleanup = workflow.index("- name: Delete the published Shorts")
        self.assertLess(persist, cleanup)
        self.assertIn("git push -q origin HEAD:main", workflow[persist:cleanup])
        self.assertIn("PUBLICATION_PERSISTENCE_UNCONFIRMED; exit 1", workflow[persist:cleanup])
        self.assertIn("SCHEDULED_VERIFIED|PUBLIC_VERIFIED", workflow[cleanup:])
        self.assertNotIn("uploaded|processed", workflow[cleanup:])
        self.assertIn('if: env.SKIP !=', workflow[cleanup:])

    def test_cleanup_binds_receipt_hash_not_changed_manifest(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/publish-shorts.yml").read_text()
        cleanup = workflow[workflow.index("- name: Delete the published Shorts"):]
        self.assertIn("output_sha256", cleanup)
        self.assertNotIn("shorts/shorts.json", cleanup)
        self.assertIn('while read -r f st sha', cleanup)
        self.assertIn('asset="$PILOT-${f%.mp4}-sha256-$sha.mp4"', cleanup)
        old = {"file": "short-00.mp4", "output_sha256": "a" * 64}
        changed = {"file": "short-00.mp4", "sha256": "b" * 64}
        asset = f"pilot-005-{old['file'][:-4]}-sha256-{old['output_sha256']}.mp4"
        self.assertIn(old["output_sha256"], asset)
        self.assertNotIn(changed["sha256"], asset)


class Verification(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 20, 18, tzinfo=timezone.utc)
        self.slot = "2026-10-20T20:00:00Z"
        self.expected = {"title": "T", "description": "D"}
        self.observation = {"video_id": "ID", "channel_id": pub.pv.CHANNEL,
                            "title": "T", "description": "D", "default_language": "en",
                            "default_audio_language": "en", "license": "youtube",
                            "contains_synthetic_media": True, "privacy_status": "private",
                            "publish_at": self.slot, "upload_status": "processed", "processing_status": "succeeded"}

    def check(self, changes=None, now=None):
        observation = dict(self.observation, **(changes or {}))
        return pub.verification(observation, None, "ID", self.slot, self.expected, now or self.now)

    def test_scheduled_and_utc_equivalence(self):
        self.assertEqual(self.check(), ("SCHEDULED_VERIFIED", None))
        self.assertEqual(self.check({"publish_at": "2026-10-20T20:00:00+00:00"}), ("SCHEDULED_VERIFIED", None))

    def test_public_requires_slot_reached_and_successful_processing(self):
        after = datetime(2026, 10, 20, 20, tzinfo=timezone.utc)
        self.assertEqual(self.check({"privacy_status": "public", "publish_at": None}, after), ("PUBLIC_VERIFIED", None))
        self.assertEqual(self.check({"privacy_status": "public"})[0], "VERIFICATION_FAIL")
        self.assertEqual(self.check(now=after)[0], "VERIFICATION_FAIL")

    def test_pending_is_not_success_and_does_not_hide_mismatch(self):
        self.assertEqual(self.check({"upload_status": "uploaded", "processing_status": "processing"})[0], "PENDING_PROCESSING")
        self.assertEqual(self.check({"upload_status": "uploaded", "channel_id": "WRONG"})[0], "VERIFICATION_FAIL")

    def test_missing_and_mismatched_fields_never_pass(self):
        for field in self.observation:
            with self.subTest(missing=field):
                self.assertNotIn(self.check({field: None})[0], ("SCHEDULED_VERIFIED", "PUBLIC_VERIFIED"))
        for field in ("video_id", "channel_id", "title", "description", "default_language", "default_audio_language", "license", "privacy_status", "publish_at"):
            with self.subTest(wrong=field):
                self.assertNotIn(self.check({field: "WRONG"})[0], ("SCHEDULED_VERIFIED", "PUBLIC_VERIFIED"))
        self.assertEqual(self.check({"contains_synthetic_media": False})[0], "VERIFICATION_FAIL")

    def test_processing_failures_and_unknown(self):
        for status in ("failed", "rejected", "deleted"):
            self.assertEqual(self.check({"upload_status": status})[0], "VERIFICATION_FAIL")
        self.assertEqual(self.check({"processing_status": "failed"})[0], "VERIFICATION_FAIL")
        self.assertEqual(self.check({"processing_status": "terminated"})[0], "VERIFICATION_UNKNOWN")

    def test_readback_get_only_timeout_and_sanitization(self):
        class Session:
            def __init__(self):
                self.calls = []
            def get(self, url, params, timeout):
                self.calls.append((url, params, timeout))
                raise TimeoutError("SECRET raw body must not escape")
        session = Session()
        observation, error = pub.observe_video(session, "ID")
        self.assertEqual(error, "READBACK_UNAVAILABLE")
        self.assertEqual(session.calls[0][1], {"part": "id,snippet,status,processingDetails", "id": "ID"})
        self.assertEqual(session.calls[0][2], 30)
        self.assertNotIn("SECRET", json.dumps(observation))
        self.assertTrue(all(observation[k] is None for k in observation["unknown_fields"]))

    def test_missing_or_wrong_video_response_never_verifies(self):
        class Session:
            def __init__(self, data):
                self.data = data
            def get(self, url, params, timeout):
                return Resp(self.data)
        with patch.object(pub.pv, "check", side_effect=lambda r, _: r.data):
            for payload in ({"items": []}, {"items": None}, {"items": [{}, {}]}, {"items": ["bad"]}):
                observation, error = pub.observe_video(Session(payload), "ID")
                self.assertEqual(error, "READBACK_UNAVAILABLE")
                self.assertEqual(pub.verification(observation, error, "ID", self.slot, self.expected, self.now)[0], "VERIFICATION_UNKNOWN")
            observation, error = pub.observe_video(Session({"items": [{"id": "WRONG"}]}), "ID")
            self.assertEqual(pub.verification(observation, error, "ID", self.slot, self.expected, self.now)[0], "VERIFICATION_FAIL")

    def test_atomic_json_roundtrip_and_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "ledger.json"
            pub.atomic_json(path, {"id": "ID"})
            self.assertEqual(json.loads(path.read_text()), {"id": "ID"})
            self.assertEqual([p.name for p in Path(t).iterdir()], ["ledger.json"])

class OwnerException(PublishShorts):
    def prepare(self, d):
        import publication_exception as pe
        spec = json.loads((d / "shorts.json").read_text())
        spec.update(source_pilot=pe.PILOT, publish=False, release_status="READY_BY_OWNER_TEMPORAL_EXCEPTION")
        spec["shorts"] = spec["shorts"][:1]
        spec["finalization"] = {"status": "COMPLETE", "ordinary_release_status": "TARGET_SLOT_LEAD_MISSED",
                                "target_slot": pe.BINDING["target_slot"], "output_sha256": pe.OUTPUT_SHA256,
                                "owner_exception": dict(pe.BINDING)}
        r = spec["shorts"][0]
        r.update(sha256=pe.OUTPUT_SHA256, qa_output_sha256=pe.OUTPUT_SHA256,
                 release_status="READY_BY_OWNER_TEMPORAL_EXCEPTION")
        r["media_checks"] = {"status": "PASS", "output_sha256": pe.OUTPUT_SHA256}
        r["qa"] = {"status": "PASS", "checks": {k: True for k in (
            "decode_clean", "one_h264_1080x1920", "fps_30", "one_aac_stereo_48k", "duration", "loudness", "true_peak")}}
        r["review"].update(output_sha256=pe.OUTPUT_SHA256, overall=9.0)
        r["review"].update({k: 8 for k in ("hook_in_first_2s", "captions_readable_and_synced", "text_clear_of_shorts_ui",
            "picture_quality", "edit_rhythm", "audio_clarity", "stands_alone", "ending_and_loop", "policy_safe")})
        ledger = json.loads((d / "ledger.json").read_text())
        ledger["version"] = "publish-ledger-v1"
        ledger = pe.reserve(ledger, pe.BINDING, run_key="123:1")
        (d / "ledger.json").write_text(json.dumps(ledger))
        (d / "shorts.json").write_text(json.dumps(spec))
        pub.utc_now = lambda: datetime(2026, 10, 20, 21, 20, tzinfo=timezone.utc)
        return pe, spec

    def test_new_85_exception_is_not_a_future_score_override(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            pe, spec = self.prepare(d)
            spec["shorts"][0]["review"]["overall"] = 8.5
            (d / "shorts.json").write_text(json.dumps(spec))
            with patch.dict(pub.os.environ, GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1"), patch.object(pub.pv, "session") as session:
                with self.assertRaises(SystemExit):
                    self.run_pub(d, pe.BINDING["target_slot"])
                session.assert_not_called()

    def test_exception_public_pending_then_verified_same_id(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            pe, spec = self.prepare(d)
            short = spec["shorts"][0]
            stage, calls, bodies = ["processing"], [], []
            original_get = self.yt.get
            def get(url, params=None, timeout=None):
                if params.get("part") != "id,snippet,status,processingDetails":
                    return original_get(url, params, timeout)
                calls.append(params["id"])
                return Resp({"items": [{"id": params["id"], "snippet": {
                    "channelId": pub.pv.CHANNEL, "title": pub.title_for(short),
                    "description": pub.description_for(short, "https://youtu.be/LONG", "Long"),
                    "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                    "status": {"uploadStatus": "uploaded" if stage[0] == "processing" else "processed",
                               "privacyStatus": "public", "license": "youtube", "containsSyntheticMedia": True},
                    "processingDetails": {"processingStatus": stage[0]}}]})
            self.yt.get = get
            with patch.dict(pub.os.environ, GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1"), patch.object(pub, "sha256_file", return_value=pe.OUTPUT_SHA256), patch.object(pub.pv, "upload", side_effect=lambda session, path, body: (bodies.append(body), {"id": "VIDEO123456"})[1]):
                first = self.run_pub(d, pe.BINDING["target_slot"])
                self.assertEqual(first["shorts"][0]["verification_status"], "PENDING_PROCESSING")
                stage[0] = "succeeded"
                spec["shorts"][0]["review"]["overall"] = 8.5
                spec["shorts"][0]["publish"] = False
                (d / "shorts.json").write_text(json.dumps(spec))
                (d / "short-00.mp4").unlink()
                with patch.dict(pub.os.environ, GITHUB_RUN_ID="456", GITHUB_RUN_ATTEMPT="2"):
                    second = self.run_pub(d, pe.BINDING["target_slot"])
            self.assertEqual(second["shorts"][0]["verification_status"], "PUBLIC_VERIFIED")
            self.assertEqual(calls, ["VIDEO123456", "VIDEO123456"])
            self.assertEqual(len(bodies), 1)
            self.assertEqual(bodies[0]["status"]["privacyStatus"], "public")
            self.assertNotIn("publishAt", bodies[0]["status"])
            ledger = json.loads((d / "ledger.json").read_text())
            self.assertEqual(ledger["owner_exceptions"][pe.EXCEPTION_ID]["state"], "CONSUMED")
            self.assertEqual(ledger["owner_exceptions"][pe.EXCEPTION_ID]["video_id"], "VIDEO123456")

    def test_exception_rejects_binding_markers_and_gates(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            pe, spec = self.prepare(d)
            import copy
            for section, key, value in (("binding", "receipt_sha256", "0" * 64), ("final", "target_slot", "2026-10-20T23:00:00Z"),
                    ("final", "ordinary_release_status", "REVIEW_FAIL"), ("final", "status", "ERROR"),
                    ("spec", "release_status", "OTHER"), ("record", "release_status", "OTHER"),
                    ("record", "sha256", "0" * 64), ("qa", "status", "FAIL"), ("review", "overall", 7)):
                case = copy.deepcopy(spec)
                target = {"spec": case, "final": case["finalization"], "binding": case["finalization"]["owner_exception"],
                          "record": case["shorts"][0], "qa": case["shorts"][0]["qa"], "review": case["shorts"][0]["review"]}[section]
                target[key] = value
                with self.subTest(section=section, key=key), self.assertRaises((SystemExit, ValueError)):
                    pub.exception_binding(case)

    def test_unknown_upload_reservation_blocks_new_run(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            pe, _ = self.prepare(d)
            with patch.dict(pub.os.environ, GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1"), patch.object(pub, "sha256_file", return_value=pe.OUTPUT_SHA256), patch.object(pub.pv, "upload", side_effect=TimeoutError("unknown")) as upload:
                with self.assertRaises(TimeoutError):
                    self.run_pub(d, pe.BINDING["target_slot"])
                with self.assertRaises(ValueError):
                    self.run_pub(d, pe.BINDING["target_slot"])
                with patch.dict(pub.os.environ, GITHUB_RUN_ID="456", GITHUB_RUN_ATTEMPT="1"), self.assertRaises(ValueError):
                    self.run_pub(d, pe.BINDING["target_slot"])
                self.assertEqual(upload.call_count, 1)
            ledger = json.loads((d / "ledger.json").read_text())
            with self.assertRaises(ValueError):
                pe.reserve(ledger, pe.BINDING, run_key="123:1")

    def test_reserved_intent_other_run_cannot_upload(self):
        with tempfile.TemporaryDirectory() as t:
            d, _ = setup(t, done=())
            pe, _ = self.prepare(d)
            with patch.dict(pub.os.environ, GITHUB_RUN_ID="456", GITHUB_RUN_ATTEMPT="1"), patch.object(pub, "sha256_file", return_value=pe.OUTPUT_SHA256), patch.object(pub.pv, "upload") as upload:
                with self.assertRaises(ValueError):
                    self.run_pub(d, pe.BINDING["target_slot"])
                upload.assert_not_called()

    def test_wrong_slot_shell_aborts_before_reservation(self):
        import subprocess
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/publish-shorts.yml").read_text()
        block = workflow[workflow.index("            exception_slot="):workflow.index('            run_key="$GITHUB_RUN_ID:$GITHUB_RUN_ATTEMPT"')]
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "shorts").mkdir()
            (d / "shorts/shorts.json").write_text(json.dumps({"finalization": {"owner_exception": {"target_slot": "2026-10-20T20:00:00Z"}}}))
            env = dict(pub.os.environ, d=str(d), SLOTS="2026-10-20T23:00:00Z")
            result = subprocess.run(["bash", "-c", block + '\necho reserved > "$d/reservation"'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("EXCEPTION_SLOT_MISMATCH_BEFORE_RESERVATION", result.stdout)
            self.assertFalse((d / "reservation").exists())

    def test_remote_head_change_with_identical_ledger_aborts_before_upload(self):
        import subprocess
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/publish-shorts.yml").read_text()
        guard = next(line.strip() for line in workflow.splitlines() if "EXCEPTION_REMOTE_HEAD_CHANGED" in line)
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=d, text=True).strip()
            git("init", "-q")
            git("config", "user.name", "Offline Test")
            git("config", "user.email", "test@example.invalid")
            (d / "ledger.json").write_text('{"reserved":true}\n')
            git("add", ".")
            git("commit", "-qm", "reserved")
            reserved = git("rev-parse", "HEAD")
            (d / "PUBLICATION_HOLD").write_text("hold\n")
            git("add", ".")
            git("commit", "-qm", "concurrent hold")
            remote = git("rev-parse", "HEAD")
            git("fetch", "-q", ".", remote)
            git("checkout", "-q", reserved)
            self.assertEqual(git("show", "HEAD:ledger.json"), git("show", "FETCH_HEAD:ledger.json"))
            result = subprocess.run(["bash", "-c", guard + "\necho uploaded > uploaded"], cwd=d, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("EXCEPTION_REMOTE_HEAD_CHANGED", result.stdout)
            self.assertFalse((d / "uploaded").exists())
            git("fetch", "-q", ".", reserved)
            result = subprocess.run(["bash", "-c", guard + "\necho allowed > allowed"], cwd=d, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertTrue((d / "allowed").exists())

    def test_workflow_reservation_persisted_before_upload(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/publish-shorts.yml").read_text()
        start = workflow.index("publication_exception.py --reserve")
        upload = workflow.index('"$RUNNER_TEMP/venv/bin/python" -I -B migration/publish/publish_shorts.py')
        self.assertLess(start, upload)
        self.assertLess(workflow.index("EXCEPTION_SLOT_MISMATCH_BEFORE_RESERVATION; exit 1"), start)
        section = workflow[start:upload]
        self.assertIn("git push -q origin HEAD:main", section)
        self.assertIn("git fetch -q origin main", section)
        self.assertLess(section.index("git fetch -q origin main"), section.index("EXCEPTION_REMOTE_HEAD_CHANGED"))
        self.assertLess(section.index("EXCEPTION_REMOTE_HEAD_CHANGED"), section.index("git show FETCH_HEAD:"))
        self.assertIn("EXCEPTION_RESERVATION_PERSISTENCE_UNCONFIRMED; exit 1", section)


class States(unittest.TestCase):
    def test_every_short_has_one_state(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "pilot-009"
            (d / "shorts").mkdir(parents=True)
            shorts = [{"file": "a", "sha256": "a", "publish": False, "review": {"status": "FAIL"}},
                      {"file": "b", "sha256": "b", "publish": False, "review": {"status": "PASS", "model": "gemini-3.8-flash"}},
                      {"file": "c", "sha256": "c", "publish": True, "review": {"status": "PASS", "model": "gemini-3.8-flash"}},
                      {"file": "d", "sha256": "d", "publish": True, "review": {"status": "PASS", "model": "gemini-3.8-flash"}},
                      {"file": "e", "sha256": "e", "publish": True, "review": {"status": "PASS", "model": "gemini-3.8-flash"}},
                      {"file": "f", "sha256": "f", "publish": True, "review": {"status": "PASS", "model": "gemini-3.8-flash"}, "qa": {"status": "FAIL"}}]
            shorts[2]["sha256"] = "c" * 64
            shorts[2]["qa"] = {"status": "PASS"}
            shorts[2]["review"].update(overall=9.0, output_sha256="c" * 64)
            (d / "shorts" / "shorts.json").write_text(json.dumps({"source_pilot": "pilot-009", "shorts": shorts}))
            ledger = {"entries": {"short:pilot-009:d": {"video_id": "D", "slot": "2026-10-20T14:00:00Z"},
                                  "short:pilot-009:e": {"video_id": "E", "slot": "2026-10-18T14:00:00Z"}}}
            now = datetime(2026, 10, 19, tzinfo=timezone.utc)
            self.assertEqual([r["state"] for r in ps.states(d, ledger, now)],
                             ["failed", "not_selected", "approved_awaiting_slot", "scheduled", "published", "failed"])
            self.assertEqual(ps.todo_files(d, ledger), [("c", "c" * 64)])
            shorts[2]["review"]["model"] = "gemini-3.5-flash-lite"  # a fallback model's PASS never publishes
            (d / "shorts" / "shorts.json").write_text(json.dumps({"source_pilot": "pilot-009", "shorts": shorts}))
            self.assertEqual(ps.states(d, ledger, now)[2]["state"], "review_by_undesignated_model")
            self.assertEqual(ps.todo_files(d, ledger), [])


if __name__ == "__main__":
    unittest.main()
