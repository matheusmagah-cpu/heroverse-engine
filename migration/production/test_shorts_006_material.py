#!/usr/bin/env python3
"""Offline synthetic contracts, not media qualification or production evidence."""
from contextlib import contextmanager, ExitStack, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shorts_006_material as ep
import shorts_006_plan as legacy

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
PLAN_HASH = "99e0ecbd3a5a0c5736e6ce8eaadc766a346cb789b08203577fa38dde1ade1543"
HISTORY_HASH = "5b1798377d25f54a813ed8ae1e99fbe17fa7ccab0ea4650454fcb76c5ba1cede"
OUTPUT_BYTES = b"synthetic corrected file, not a video or a qualification"
OUTPUT_HASH = hashlib.sha256(OUTPUT_BYTES).hexdigest()


def sources():
    # Fully local synthetic timeline. Only contract-required endpoints and hook
    # match the pinned candidate; interior wording is deliberately synthetic.
    sentences = [{"segment": "earlier", "text": "Earlier synthetic sentence.", "start": i * 3., "end": i * 3. + 1.}
                 for i in range(191)]
    bounds = [(813.728, 815.669), (815.849, 817.791), (819.171, 821.155),
              (821.335, 824.343), (824.523, 826.443), (826.623, 831.081),
              (831.261, 834.525), (834.705, 836.135), (837.515, 846.389),
              (846.569, 850.559), (850.739, 852.915), (853.095, 854.417)]
    for i, (start, end) in enumerate(bounds):
        sentences.append({"segment": "sleep-relax-1" if i < 2 else "sleep-relax-2" if i < 8 else "sleep-relax-3",
                          "text": "Let your face soften." if i == 0 else f"Synthetic complete sentence {i}.",
                          "start": start, "end": end})
    sentences.append({"segment": "following", "text": "Following synthetic sentence.", "start": 855.797, "end": 858.0})
    script = {"pilot_id": "pilot-006", "segments": [{"id": ident, "reference": None}
              for ident in dict.fromkeys(s["segment"] for s in sentences)],
              "backgrounds": ["bg-healing-stream-night", "bg-still-water-night"]}
    return {"timeline": {"sentences": sentences}, "script": script,
            "inputs": {"voice_asset": ep.EXPECTED_PLAN["voice"]["asset"], "voice_sha256": ep.EXPECTED_PLAN["voice"]["sha256"]}}


def media_fixture(plan, docs):
    return {"version": "shorts-006-media-checks-v2", "plan_sha256": ep.PLAN_SHA256, "history_sha256": ep.HISTORY_SHA256,
        "source_sha256": deepcopy(plan["source_sha256"]), "output_sha256": OUTPUT_HASH,
        "source_voice_sha256": plan["voice"]["sha256"], "source_music_sha256": plan["music"]["sha256"],
        "source_image_sha256": {s["image_id"]: s["sha256"] for s in plan["scenes"]},
        "source_durations": {"voice_seconds": 1529.993333, "music_seconds": 10800., "voice_sample_rate": 24000, "voice_channels": 1},
        "measured_at": "2026-10-21T11:00:00+00:00", "status": "PASS",
        "acoustic": {"pcm_sample_rate": 48000, "window_samples": 480, "active_threshold_dbfs": -40.,
            "leading_inactive_seconds": .13, "trailing_inactive_seconds": .29, "first_active_sample": 6240,
            "last_active_sample": 1939200, "narration_samples": 1953120, "status": "PASS"},
        "video": {"decoded_frame_count": 1260, "fps": 30., "seconds": 42., "width": 1080, "height": 1920,
            "video_codec": "h264", "audio_codec": "aac", "audio_sample_rate": 48000, "audio_channels": 2,
            "decoded_audio_samples": 2016256, "presentation_audio_samples": 2016000,
            "first_pts": 0., "last_pts": 1259 / 30, "pts_uniform": True,
            "audio_packets": {"packet_count": 1970, "first_pts_samples": -1024, "skip_samples": 1024,
                "last_pts_samples": 2015232, "last_duration_samples": 768, "packet_clock_continuous": True, "codec_frame_samples": 1024},
            "black_intervals": [], "render_plan": ep.frame_plan(plan), "status": "PASS"},
        "editorial_metadata": ep._editorial_metadata(plan, docs), "audio_preservation": proof_fixture(plan)}


def manifest_fixture(plan, docs, media, media_hash):
    moment = ep.validate_plan(plan, docs["timeline"], docs["script"], docs["inputs"],
                              raw_sha256={k: plan["source_sha256"][k] for k in ("timeline", "script", "inputs")})["chosen"][0]
    qa = {"file": "short-00.mp4", "seconds": 42., "lufs": -14., "true_peak_dbtp": -2.,
          "checks": {k: True for k in ep.QA_CHECKS}, "status": "PASS"}
    review = {k: 9. for k in ep.RUBRIC}
    review.update(status="PASS", model="gemini-3.8-flash", overall=9.6, issues=[], strongest_moment="synthetic", output_sha256=OUTPUT_HASH)
    record = {"file": "short-00.mp4", "sha256": OUTPUT_HASH, "seconds": 42., "source_start": 813.728, "source_end": 854.417,
        "hook": "Let your face soften.", "title": "Rest in God's Care", "reference": None,
        "hook_mode": "caption_only", "hook_shown": True, "scenes": [s["image_id"] for s in plan["scenes"]],
        "figure": False, "parallax": False, "render_plan": ep.frame_plan(plan), "text": moment["text"], "segments": moment["segments"],
        "qa_output_sha256": OUTPUT_HASH, "qa": qa, "review": review, "media_checks": deepcopy(media), "media_checks_sha256": media_hash,
        "publish": False, "selection": {"final_score": None}}
    return {"source_pilot": "pilot-006", "edit_plan": deepcopy(plan), "shorts": [record],
            "review_rubric": {"items": list(ep.RUBRIC), "pass_item": 7, "pass_overall": 8}}


def proof_fixture(plan):
    snapshot = {"aac_packets_sha256": plan["audio_preservation"]["aac_packets_sha256"],
        "packet_manifest_sha256": "a" * 64, "extradata_sha256": "b" * 64, "pcm_sha256": "c" * 64, "pcm_samples": 2016256}
    return {"version": "aac-remux-proof-v1", "reference_sha256": plan["audio_preservation"]["reference_sha256"],
        "reference_bytes": plan["audio_preservation"]["reference_bytes"], "ffmpeg_version": "ffmpeg synthetic-test-only",
        "reference": snapshot, "output": deepcopy(snapshot)}


def client_audit():
    return {"transport_attempts": [{"attempt": 1, "started_at": "2026-10-21T11:59:52Z",
        "elapsed_start_seconds": 2., "elapsed_end_seconds": 8., "outcome": "SUCCESS", "http_status": 200,
        "provider_status": None, "retry_after_seconds": None, "retry_info_seconds": None,
        "selected_delay_seconds": None, "slept_seconds": 0., "decision": "RETURN"}],
        "http_completion": "COMPLETED", "terminal_stage": "GENERATE_CONTENT", "cleanup_status": "SUCCESS", "http_elapsed_seconds": 9.}


def journal_fixture(spec, media_hash):
    return ep._attempt_constants(OUTPUT_HASH, media_hash) | client_audit() | {
        "run_id": "77777777777", "run_attempt": 1, "started_at": "2026-10-21T11:59:50Z",
        "completed_at": "2026-10-21T11:59:59Z", "state": "COMPLETE", "reason": None,
        "fresh_qa": deepcopy(spec["shorts"][0]["qa"])}


@contextmanager
def synthetic_environment(root):
    """Actual files/binding with only code pins replaced, never reads live fixtures."""
    pilot = Path(root) / "production/pilot-006"
    (pilot / "shorts").mkdir(parents=True)
    (pilot / "out").mkdir()
    docs = sources()
    docs.update(images={"synthetic": True}, long_manifest={"synthetic": True}, long_review={"synthetic": True})
    paths = {"script": "script.json", "timeline": "out/timeline.json", "inputs": "shorts/inputs.json",
        "images": "images.json", "long_manifest": "out/manifest.json", "long_review": "out/review.json"}
    for k, relative in paths.items():
        ep.atomic_json(pilot / relative, docs[k])
    plan = deepcopy(ep.EXPECTED_PLAN)
    plan["source_sha256"] = {k: ep.hash_file(pilot / relative) for k, relative in paths.items()}
    history = b'{"source_pilot":"pilot-006","synthetic":true}'
    history += b' ' * (17623 - len(history))
    history_path = pilot / "shorts/correction-history-96c8268f.json"
    history_path.write_bytes(history)
    history_hash = ep.hash_file(history_path)
    plan["previous_material"]["sha256"] = history_hash
    for name in ("correction-plan.json", "correction-history.json"):
        (pilot / "shorts" / name).write_text('{"synthetic":true}\n')
    old_hash = ep.hash_file(pilot / "shorts/correction-plan.json")
    plan["history"]["sha256"] = old_hash
    plan["previous_material"]["previous_plan_sha256"] = old_hash
    plan_path = pilot / "shorts/correction-plan-v2.json"
    ep.atomic_json(plan_path, plan)
    plan_hash = ep.hash_file(plan_path)
    with ExitStack() as stack:
        for name, value in (("CANONICAL_PILOT", pilot), ("EXPECTED_PLAN", plan), ("PLAN_SHA256", plan_hash),
                ("HISTORY_SHA256", history_hash), ("LEGACY_PLAN_SHA256", old_hash), ("LEGACY_HISTORY_SHA256", old_hash)):
            stack.enter_context(patch.object(ep, name, value))
        clock = stack.enter_context(patch.object(ep, "datetime"))
        clock.now.return_value = NOW
        stack.enter_context(patch.object(ep.shorts_prerequisite, "problems", return_value=[]))
        media = media_fixture(plan, docs)
        ep.atomic_json(pilot / "shorts" / ep.MEDIA_FILE, media)
        media_hash = ep.hash_file(pilot / "shorts" / ep.MEDIA_FILE)
        spec = manifest_fixture(plan, docs, media, media_hash)
        spec[ep.JOURNAL] = journal_fixture(spec, media_hash)
        contract = ep._contract()
        spec = ep.finalize_manifest(spec, actual_output_sha256=OUTPUT_HASH, now_utc=NOW,
            media_checks=media, media_sha256=media_hash, contract=contract)
        ep.atomic_json(pilot / "shorts/shorts.json", spec)
        output = pilot / "shorts/short-00.mp4"
        output.write_bytes(OUTPUT_BYTES)
        yield {"pilot": pilot, "spec": spec, "plan": plan, "docs": docs, "media": media,
            "media_hash": media_hash, "plan_hash": plan_hash, "history_hash": history_hash,
            "output": output, "contract": contract, "history_path": history_path}


class MaterialTests(unittest.TestCase):
    def setUp(self):
        self.plan = deepcopy(ep.EXPECTED_PLAN)
        self.docs = sources()
        self.media = media_fixture(self.plan, self.docs)
        self.mh = "d" * 64
        self.spec = manifest_fixture(self.plan, self.docs, self.media, self.mh)
        self.spec[ep.JOURNAL] = journal_fixture(self.spec, self.mh)

    def finalize(self, spec=None, media=None, now=NOW):
        return ep.finalize_manifest(spec or self.spec, actual_output_sha256=OUTPUT_HASH, now_utc=now,
            media_checks=media or self.media, media_sha256=self.mh, contract=(self.plan, ep.DENIED_OUTPUTS, self.docs))

    def test_plan_exact_digest_and_native_frames(self):
        raw = (json.dumps(self.plan, ensure_ascii=False, indent=2) + "\n").encode()
        self.assertEqual(len(raw), 6538)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PLAN_HASH)
        self.assertEqual(ep.PLAN_SHA256, PLAN_HASH)
        self.assertEqual(ep.HISTORY_SHA256, HISTORY_HASH)
        self.assertEqual([(x["start_frame"], x["end_frame"]) for x in ep.frame_plan(self.plan)["scene_frame_spans"]], [(0,637),(622,1260)])
        for field in ("audio", "voice", "music", "candidate", "source_sha256"):
            self.assertEqual(self.plan[field], legacy.EXPECTED_PLAN[field])

    def test_legacy_adapter_rejects_new_plan_antidote(self):
        with self.assertRaisesRegex(ep.EvidenceError, "INVALID_CORRECTION_PLAN"):
            legacy.validate_plan_schema(self.plan)
        with self.assertRaisesRegex(ep.EvidenceError, "INVALID_CORRECTION_PLAN"):
            ep.validate_plan_schema(legacy.EXPECTED_PLAN)

    def test_closed_plan_schema(self):
        for field, value in [("fps", True), ("fps", float("nan")), ("version", "shorts-006-correction-plan-v1"), ("scenes", [])]:
            with self.subTest(field=field):
                changed = deepcopy(self.plan); changed[field] = value
                with self.assertRaises(ep.EvidenceError): ep.validate_plan_schema(changed)
        changed = deepcopy(self.plan); changed["extra"] = 1
        with self.assertRaises(ep.EvidenceError): ep.validate_plan_schema(changed)

    def test_neutral_helpers_are_same_functions(self):
        for name in ("_probe", "_black_intervals", "_audio_packets", "_validate_acoustic", "_qa_verdict", "_review_verdict"):
            self.assertIs(getattr(ep, name), getattr(legacy, name))

    def test_positive_finalization_and_real_file_binding(self):
        self.assertEqual(self.finalize()["release_status"], "READY")
        with tempfile.TemporaryDirectory() as root, synthetic_environment(root) as env:
            result = ep.binding(env["spec"], pilot_dir=env["pilot"])
            self.assertEqual(set(result), {"output_sha256", "target_slot", "release_deadline", "file", "plan_sha256", "metadata_profile"})
            self.assertEqual(result["metadata_profile"], "rest-v1")
            self.assertEqual(result["plan_sha256"], env["plan_hash"])
            (env["pilot"] / "shorts/correction-history.json").write_text("changed")
            with self.assertRaisesRegex(ep.EvidenceError, "LEGACY_HISTORY_CHANGED"):
                ep.binding(env["spec"], pilot_dir=env["pilot"])

    def test_changed_sources_histories_plan_media_rejected(self):
        for relative in ("script.json", "shorts/correction-plan-v2.json", "shorts/correction-plan.json",
                         "shorts/correction-history-96c8268f.json", "shorts/" + ep.MEDIA_FILE):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as root, synthetic_environment(root) as env:
                (env["pilot"] / relative).write_text('{}')
                with self.assertRaises((ep.EvidenceError, KeyError)):
                    ep.binding(env["spec"], pilot_dir=env["pilot"])

    def test_missing_forged_or_replayed_journal(self):
        mutations = [lambda s:s.pop(ep.JOURNAL), lambda s:s[ep.JOURNAL].update(state="STARTED"),
            lambda s:s[ep.JOURNAL].update(run_attempt=True), lambda s:s[ep.JOURNAL].update(run_id="39590168285"),
            lambda s:s[ep.JOURNAL].update(output_sha256="e"*64), lambda s:s[ep.JOURNAL].update(extra=1),
            lambda s:s[ep.JOURNAL].update(transport_attempts=[]), lambda s:s.update(correction_review_attempt={}),
            lambda s:s.update(owner_exception={}), lambda s:s[ep.JOURNAL].update(history_sha256="e"*64)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                spec=deepcopy(self.spec); mutate(spec)
                out=self.finalize(spec)
                self.assertEqual(out["finalization"]["status"],"ERROR")
                self.assertFalse(out["shorts"][0]["publish"])

    def test_missing_editorial_identity_never_ready(self):
        for key in ("file","hook","title","reference"):
            spec=deepcopy(self.spec);spec["shorts"][0].pop(key)
            result=self.finalize(spec)
            self.assertEqual(result["finalization"]["status"],"ERROR")
            self.assertFalse(result["shorts"][0]["publish"])

    def test_denied_all_three_hashes(self):
        for digest in ep.DENIED_OUTPUTS:
            spec=deepcopy(self.spec);spec["shorts"][0]["sha256"]=digest
            out=ep.finalize_manifest(spec,actual_output_sha256=digest,now_utc=NOW,media_checks=self.media,
                media_sha256=self.mh,contract=(self.plan,ep.DENIED_OUTPUTS,self.docs))
            self.assertEqual(out["finalization"]["status"],"ERROR")

    def test_real_fail_and_under_nine_complete_negative(self):
        for overall,rhythm,status in [(8.3,6.8,"FAIL"),(8.9,9.,"PASS")]:
            spec=deepcopy(self.spec);spec["shorts"][0]["review"].update(overall=overall,edit_rhythm=rhythm,status=status)
            out=self.finalize(spec)
            self.assertEqual(out["finalization"]["status"],"COMPLETE")
            self.assertFalse(out["shorts"][0]["publish"])
            self.assertEqual(out["shorts"][0]["review"]["overall"],overall)

    def test_late_real_verdict_preserved_negative(self):
        spec=deepcopy(self.spec)
        spec[ep.JOURNAL].update(http_completion="DEADLINE_EXCEEDED",completed_at="2026-10-21T13:16:00Z")
        spec[ep.JOURNAL]["transport_attempts"][-1]["decision"]="STOP_DEADLINE"
        out=self.finalize(spec,now=datetime(2026,10,21,13,16,tzinfo=timezone.utc))
        self.assertEqual(out["finalization"]["status"],"COMPLETE")
        self.assertEqual(out["release_status"],"HTTP_DEADLINE_EXCEEDED")
        self.assertEqual(out["shorts"][0]["review"],spec["shorts"][0]["review"])
        self.assertFalse(out["shorts"][0]["publish"])

    def test_cutoff_and_budget_negative(self):
        out=self.finalize(now=datetime(2026,10,21,13,16,tzinfo=timezone.utc))
        self.assertEqual(out["release_status"],"TARGET_SLOT_LEAD_MISSED")
        spec=deepcopy(self.spec);spec[ep.JOURNAL]["http_elapsed_seconds"]=601
        self.assertEqual(self.finalize(spec)["release_status"],"HTTP_BUDGET_EXHAUSTED")

    def test_media_closed_schema_and_audio_all_fields(self):
        for field in self.media:
            media=deepcopy(self.media);media.pop(field)
            with self.assertRaises(ep.EvidenceError): ep.validate_media_checks(media,self.plan,OUTPUT_HASH,docs=self.docs)
        for field in self.media["audio_preservation"]["output"]:
            media=deepcopy(self.media);media["audio_preservation"]["output"][field]="e"*64 if field!="pcm_samples" else 2016000
            with self.assertRaises(ep.EvidenceError): ep.validate_media_checks(media,self.plan,OUTPUT_HASH,docs=self.docs)
        for val in (True,float("nan"),2015999):
            media=deepcopy(self.media);media["audio_preservation"]["output"]["pcm_samples"]=val
            with self.assertRaises(ep.EvidenceError): ep.validate_media_checks(media,self.plan,OUTPUT_HASH,docs=self.docs)

    def test_measured_acoustic_failure_complete_not_exception(self):
        media=deepcopy(self.media);media["acoustic"].update(first_active_sample=19200,leading_inactive_seconds=.4,status="FAIL")
        media["status"]="FAIL"
        spec=deepcopy(self.spec);spec.pop(ep.JOURNAL)
        spec["shorts"][0].update(media_checks=media,review={"status":"NOT_REVIEWED_MEDIA_FAIL"})
        out=self.finalize(spec,media)
        self.assertEqual(out["finalization"]["status"],"COMPLETE")
        self.assertEqual(out["release_status"],"MEDIA_CHECKS_FAIL")

    def test_false_acoustic_and_black_metadata_rejected(self):
        media=deepcopy(self.media);media["acoustic"]["leading_inactive_seconds"]=.4
        with self.assertRaises(ep.EvidenceError):ep.validate_media_checks(media,self.plan,OUTPUT_HASH,docs=self.docs)
        media=deepcopy(self.media);media["video"].update(black_intervals=[{"start_frame":1259,"end_frame":1260}],status="FAIL");media["status"]="FAIL"
        self.assertEqual(ep.validate_media_checks(media,self.plan,OUTPUT_HASH,docs=self.docs),"FAIL")
        media["video"]["black_intervals"][0]["unknown"]=1
        with self.assertRaises(ep.EvidenceError):ep.validate_media_checks(media,self.plan,OUTPUT_HASH,docs=self.docs)

    def test_packet_manifest_exact_full_sequence(self):
        packets=[{"data_hash":"SHA256:"+"a"*64,"size":"33","pts":(i-1)*1024,"dts":(i-1)*1024,
            "duration":768 if i==1969 else 1024} for i in range(1970)]
        packets[0]["side_data_list"]=[{"side_data_type":"Skip Samples","skip_samples":1024,"discard_padding":0,"skip_reason":0,"discard_reason":0}]
        normalized=ep._packet_manifest(packets)
        self.assertEqual(len(normalized),1970)
        digest=ep._canonical_hash(normalized)
        for index,key,value in [(900,"data_hash","SHA256:"+"b"*64),(900,"size","34")]:
            changed=deepcopy(packets);changed[index][key]=value
            self.assertNotEqual(ep._canonical_hash(ep._packet_manifest(changed)),digest)
        for index,key,value in [(900,"pts",42),(900,"dts",42),(1969,"duration",1024),(0,"size",True)]:
            changed=deepcopy(packets);changed[index][key]=value
            with self.assertRaises(ep.EvidenceError):ep._packet_manifest(changed)
        for key,value in [("skip_samples",0),("discard_padding",256),("extra",1)]:
            changed=deepcopy(packets);changed[0]["side_data_list"][0][key]=value
            with self.assertRaises(ep.EvidenceError):ep._packet_manifest(changed)

    def test_reference_and_remux_rehash(self):
        with tempfile.TemporaryDirectory() as root:
            reference=Path(root)/"ref.mp4";reference.write_bytes(b"reference")
            output=Path(root)/"new.mp4";output.write_bytes(OUTPUT_BYTES)
            plan=deepcopy(self.plan);plan["audio_preservation"].update(reference_sha256=ep.hash_file(reference),reference_bytes=9)
            snapshot=proof_fixture(plan)["reference"]
            with patch.object(ep,"EXPECTED_PLAN",plan),patch.object(ep,"_ffmpeg_version",return_value="ffmpeg synthetic"),patch.object(ep,"_audio_snapshot",return_value=snapshot):
                ep.verify_audio_remux(reference,output,plan)
                reference.write_bytes(b"corrupted")
                with self.assertRaisesRegex(ep.EvidenceError,"AUDIO_REFERENCE_CHANGED"):ep.verify_audio_reference(reference,plan)

    def test_check_media_foreign_write_and_late_integrity_failure(self):
        from types import SimpleNamespace
        for foreign in (False, True):
            with self.subTest(foreign=foreign),tempfile.TemporaryDirectory() as root,ExitStack() as stack:
                work=Path(root);images=work/"images";images.mkdir()
                output=work/"short-00.mp4";output.write_bytes(OUTPUT_BYTES)
                plan=deepcopy(self.plan);docs=deepcopy(self.docs)
                for kind in ("voice","music"):
                    path=work/(kind+".flac");path.write_bytes(kind.encode())
                    plan[kind]["sha256"]=ep.hash_file(path)
                docs["inputs"]["voice_sha256"]=plan["voice"]["sha256"]
                ep.atomic_json(work/"timeline.json",docs["timeline"])
                plan["source_sha256"]["timeline"]=ep.hash_file(work/"timeline.json")
                for scene in plan["scenes"]:
                    image=images/(scene["image_id"]+".png");image.write_bytes(scene["image_id"].encode())
                    scene["sha256"]=ep.hash_file(image)
                    ep.atomic_json(image.with_suffix(".json"),{"id":scene["image_id"],"release_asset":scene["asset"],
                        "sha256":scene["sha256"],"models":{"synthetic":{"license":"test"}}})
                    scene["metadata_sha256"]=ep.hash_file(image.with_suffix(".json"))
                stack.enter_context(patch.object(ep,"EXPECTED_PLAN",plan))
                media=media_fixture(plan,docs);spec=manifest_fixture(plan,docs,media,self.mh)
                spec["shorts"][0].pop("review");manifest=work/"shorts.json";ep.atomic_json(manifest,spec)
                stack.enter_context(patch.object(ep,"preflight",return_value=plan))
                stack.enter_context(patch.object(ep,"_contract",return_value=(plan,ep.DENIED_OUTPUTS,docs)))
                stack.enter_context(patch.object(ep,"historical_failed_hashes",return_value=ep.DENIED_OUTPUTS))
                stack.enter_context(patch.object(ep,"source_durations",return_value=media["source_durations"]))
                stack.enter_context(patch.object(ep,"_run",return_value=SimpleNamespace(stdout=b"synthetic pcm",stderr=b"")))
                stack.enter_context(patch.object(ep,"acoustic_measurements",return_value=media["acoustic"]))
                stack.enter_context(patch.object(ep,"verify_audio_remux",return_value=proof_fixture(plan)))
                def measured(*args):
                    if foreign:manifest.write_bytes(b"foreign-during-measurement")
                    return media["video"]
                stack.enter_context(patch.object(ep,"measure_video",side_effect=measured))
                if not foreign:
                    stack.enter_context(patch.object(ep,"validate_media_checks",side_effect=ep.EvidenceError("LATE_SYNTHETIC_INTEGRITY")))
                with self.assertRaisesRegex(ep.EvidenceError,"INPUT_CHANGED" if foreign else "LATE_SYNTHETIC_INTEGRITY"):
                    ep.check_media(work,plan,manifest,work/"voice.flac",work/"music.flac",images,work/"history.json",work/"reference.mp4")
                if foreign:self.assertEqual(manifest.read_bytes(),b"foreign-during-measurement")
                else:
                    saved,_=ep.read_json(manifest)
                    self.assertFalse(saved["shorts"][0]["publish"])
                    self.assertEqual(saved["shorts"][0]["media_checks_reason"],"LATE_SYNTHETIC_INTEGRITY")
                    self.assertEqual(len(saved["shorts"][0]["media_checks"]),15)

    def test_media_integrity_error_cli_nonzero_but_measured_fail_zero(self):
        args=["--check-media"]+["synthetic"]*8
        with patch.object(ep,"check_media",side_effect=ep.EvidenceError("MEDIA_CHANGED_DURING_MEASUREMENT")),redirect_stdout(io.StringIO()):
            self.assertEqual(ep.cli(args),1)
        media=deepcopy(self.media);media["status"]="FAIL"
        with patch.object(ep,"check_media",return_value=media),redirect_stdout(io.StringIO()):
            self.assertEqual(ep.cli(args),0)

    def test_no_old_cli_routes(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ep.cli(["--recover-review","unused"]),1)
            self.assertEqual(ep.cli(["--recover-http-review","unused"]),1)
            self.assertEqual(ep.cli(["--recovery-list","unused"]),1)



@contextmanager
def review_environment(root):
    with synthetic_environment(root) as env, ExitStack() as stack:
        # Canonical predecessor remains byte-identical until normal Record.
        (env["pilot"] / "shorts/shorts.json").write_bytes(env["history_path"].read_bytes())
        work = Path(root) / "work"
        work.mkdir()
        manifest = work / "shorts.json"
        output = work / "short-00.mp4"
        output.write_bytes(OUTPUT_BYTES)
        spec = deepcopy(env["spec"])
        spec.pop(ep.JOURNAL); spec.pop("finalization"); spec.pop("review_rubric")
        record = spec["shorts"][0]
        review = record.pop("review")
        qa = record.pop("qa")
        record.pop("qa_output_sha256")
        record["publish"] = False
        spec.pop("release_status", None)
        ep.atomic_json(manifest, spec)
        ep.atomic_json(work / ep.MEDIA_FILE, env["media"])
        import shorts_review, shorts_qa
        audit = client_audit()
        audit["transport_attempts"][0]["started_at"] = NOW.isoformat()
        policy = stack.enter_context(patch.object(shorts_review, "ReviewHTTPPolicy"))
        policy.return_value.audit.return_value = audit
        provider = stack.enter_context(patch.object(shorts_review, "review", return_value=review))
        stack.enter_context(patch.object(shorts_qa, "check", return_value=qa))
        stack.enter_context(patch.dict(ep.os.environ, {"GITHUB_RUN_ID":"77777777777", "GITHUB_RUN_ATTEMPT":"1", "HERO_GEMINI_API_KEY":"synthetic-not-a-key"}))
        env.update(manifest=manifest, output=output, provider=provider, policy=policy, qa=qa, review=review, work=work, clock=ep.datetime)
        yield env


class ReviewTests(unittest.TestCase):
    def test_one_shot_complete_and_no_second_provider(self):
        with tempfile.TemporaryDirectory() as root, review_environment(root) as env:
            out=ep.review_material(env["manifest"],env["output"])
            self.assertEqual(out["release_status"],"READY")
            self.assertEqual(out[ep.JOURNAL]["state"],"COMPLETE")
            self.assertEqual(env["provider"].call_count,1)
            with self.assertRaisesRegex(ep.EvidenceError,"MATERIAL_ATTEMPT_ALREADY_STARTED"):
                ep.review_material(env["manifest"],env["output"])
            self.assertEqual(env["provider"].call_count,1)

    def test_prior_all_journal_states_block_dispatch(self):
        for state in ("STARTED","COMPLETE","ERROR"):
            with self.subTest(state=state),tempfile.TemporaryDirectory() as root,review_environment(root) as env:
                spec,_=ep.read_json(env["manifest"]);spec[ep.JOURNAL]={"state":state};ep.atomic_json(env["manifest"],spec)
                with self.assertRaisesRegex(ep.EvidenceError,"MATERIAL_ATTEMPT_ALREADY_STARTED"):
                    ep.review_material(env["manifest"],env["output"])
                env["provider"].assert_not_called()

    def test_removed_journal_cannot_replay_any_previous_review(self):
        for status in ("FAIL","PASS","NOT_REVIEWED_ProviderFailure"):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as root,review_environment(root) as env:
                spec,_=ep.read_json(env["manifest"])
                spec["shorts"][0]["review"]={"status":status,"overall":8.3,"output_sha256":OUTPUT_HASH}
                ep.atomic_json(env["manifest"],spec);before=env["manifest"].read_bytes()
                with self.assertRaisesRegex(ep.EvidenceError,"MATERIAL_PREVIOUS_ATTEMPT_EVIDENCE"):
                    ep.review_material(env["manifest"],env["output"])
                env["provider"].assert_not_called()
                self.assertEqual(env["manifest"].read_bytes(),before)

    def test_previous_finalization_qa_or_policy_blocks_replay(self):
        for key in ("finalization","review_rubric","qa","qa_output_sha256","owner_quality_policy","provider_diagnostic"):
            with self.subTest(key=key),tempfile.TemporaryDirectory() as root,review_environment(root) as env:
                spec,_=ep.read_json(env["manifest"])
                target=spec if key in {"finalization","review_rubric"} else spec["shorts"][0]
                target[key]=None
                ep.atomic_json(env["manifest"],spec);before=env["manifest"].read_bytes()
                with self.assertRaisesRegex(ep.EvidenceError,"MATERIAL_PREVIOUS_ATTEMPT_EVIDENCE"):
                    ep.review_material(env["manifest"],env["output"])
                env["provider"].assert_not_called()
                self.assertEqual(env["manifest"].read_bytes(),before)

    def test_bad_run_or_missing_key_no_provider(self):
        for values in ({"GITHUB_RUN_ATTEMPT":"2"},{"GITHUB_RUN_ID":"39590168285"},{"HERO_GEMINI_API_KEY":""}):
            with self.subTest(values=values),tempfile.TemporaryDirectory() as root,review_environment(root) as env,patch.dict(ep.os.environ,values):
                with self.assertRaises(ep.EvidenceError):ep.review_material(env["manifest"],env["output"])
                env["provider"].assert_not_called()

    def test_real_qa_fail_complete_without_journal_or_provider(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            env["qa"]["checks"]["decode_clean"]=False;env["qa"]["status"]="FAIL"
            out=ep.review_material(env["manifest"],env["output"])
            self.assertEqual(out["finalization"]["status"],"COMPLETE")
            self.assertEqual(out["release_status"],"QA_FAIL")
            self.assertNotIn(ep.JOURNAL,out)
            env["provider"].assert_not_called()

    def test_real_503_complete_negative(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            env["provider"].return_value={"status":"NOT_REVIEWED_ProviderFailure","output_sha256":OUTPUT_HASH}
            audit=client_audit();entry=audit["transport_attempts"][0]
            entry.update(started_at=NOW.isoformat(),outcome="HTTP_ERROR",http_status=503,provider_status="UNAVAILABLE",decision="STOP_NONRETRYABLE")
            env["policy"].return_value.audit.return_value=audit
            out=ep.review_material(env["manifest"],env["output"])
            self.assertEqual(out["finalization"]["status"],"COMPLETE")
            self.assertFalse(out["shorts"][0]["publish"])
            self.assertEqual(out[ep.JOURNAL]["transport_attempts"][0]["http_status"],503)

    def test_output_changed_by_provider_persists_error(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            def change(*args,**kwargs):
                env["output"].write_bytes(b"changed")
                return env["review"]
            env["provider"].side_effect=change
            with self.assertRaisesRegex(ep.EvidenceError,"OUTPUT_CHANGED"):
                ep.review_material(env["manifest"],env["output"])
            saved,_=ep.read_json(env["manifest"])
            self.assertEqual(saved[ep.JOURNAL]["state"],"ERROR")
            self.assertFalse(saved["shorts"][0]["publish"])

    def test_foreign_manifest_during_provider_preserved(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            def change(*args,**kwargs):
                env["manifest"].write_bytes(b"foreign-provider-write")
                return env["review"]
            env["provider"].side_effect=change
            with self.assertRaisesRegex(ep.EvidenceError,"INPUT_CHANGED"):
                ep.review_material(env["manifest"],env["output"])
            self.assertEqual(env["manifest"].read_bytes(),b"foreign-provider-write")

    def test_foreign_after_started_write_not_adopted(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            real=ep.atomic_json
            def write(path,spec):
                real(path,spec)
                if spec.get(ep.JOURNAL,{}).get("state")=="STARTED":Path(path).write_bytes(b"foreign-after-started")
            with patch.object(ep,"atomic_json",side_effect=write),self.assertRaisesRegex(ep.EvidenceError,"INPUT_CHANGED"):
                ep.review_material(env["manifest"],env["output"])
            self.assertEqual(env["manifest"].read_bytes(),b"foreign-after-started")
            env["provider"].assert_not_called()

    def test_foreign_before_started_write_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            real=ep._material_stable;calls=[0]
            def stable(data,digest):
                calls[0]+=1
                if calls[0]==2:env["manifest"].write_bytes(b"foreign-before-started")
                return real(data,digest)
            with patch.object(ep,"_material_stable",side_effect=stable),self.assertRaisesRegex(ep.EvidenceError,"INPUT_CHANGED"):
                ep.review_material(env["manifest"],env["output"])
            self.assertEqual(env["manifest"].read_bytes(),b"foreign-before-started")
            env["provider"].assert_not_called()

    def test_output_changed_during_pure_finalization_no_ready(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            real=ep.finalize_manifest
            def finalize(*args,**kwargs):
                result=real(*args,**kwargs);env["output"].write_bytes(b"changed-at-finalize");return result
            with patch.object(ep,"finalize_manifest",side_effect=finalize),self.assertRaisesRegex(ep.EvidenceError,"OUTPUT_CHANGED"):
                ep.review_material(env["manifest"],env["output"])
            saved,_=ep.read_json(env["manifest"])
            self.assertEqual(saved[ep.JOURNAL]["state"],"ERROR")

    def test_final_slow_source_check_foreign_write_preserved(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            real=ep._contract;calls=[0]
            def contract():
                calls[0]+=1;result=real()
                if calls[0]==7:env["manifest"].write_bytes(b"foreign-final-slow-check")
                return result
            with patch.object(ep,"_contract",side_effect=contract),self.assertRaisesRegex(ep.EvidenceError,"INPUT_CHANGED"):
                ep.review_material(env["manifest"],env["output"])
            self.assertEqual(env["manifest"].read_bytes(),b"foreign-final-slow-check")

    def test_cutoff_crosses_final_rehash_complete_negative(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            real=ep._material_stable;calls=[0]
            def stable(data,digest):
                calls[0]+=1;result=real(data,digest)
                if calls[0]==6:env["clock"].now.return_value=datetime(2026,10,21,13,16,tzinfo=timezone.utc)
                return result
            with patch.object(ep,"_material_stable",side_effect=stable):out=ep.review_material(env["manifest"],env["output"])
            self.assertEqual(out["finalization"]["status"],"COMPLETE")
            self.assertEqual(out["release_status"],"TARGET_SLOT_LEAD_MISSED")
            self.assertEqual(env["provider"].call_count,1)

    def test_cutoff_crosses_prestarted_check_no_journal(self):
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            real=ep._material_stable;calls=[0]
            def stable(data,digest):
                calls[0]+=1;result=real(data,digest)
                if calls[0]==2:env["clock"].now.return_value=datetime(2026,10,21,13,16,tzinfo=timezone.utc)
                return result
            with patch.object(ep,"_material_stable",side_effect=stable):out=ep.review_material(env["manifest"],env["output"])
            self.assertEqual(out["finalization"]["status"],"COMPLETE")
            self.assertNotIn(ep.JOURNAL,out)
            env["provider"].assert_not_called()

    def test_cutoff_after_started_uses_real_policy_zero_http(self):
        import shorts_review
        import structure_mining
        actual_review = shorts_review.review
        actual_policy = shorts_review.ReviewHTTPPolicy
        late = datetime(2026,10,21,13,16,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as root,review_environment(root) as env:
            real=ep._material_stable;calls=[0]
            def stable(data,digest):
                calls[0]+=1;result=real(data,digest)
                if calls[0]==3:env["clock"].now.return_value=late
                return result
            with patch.object(ep,"_material_stable",side_effect=stable), \
                 patch.object(shorts_review,"review",side_effect=actual_review) as review, \
                 patch.object(shorts_review,"ReviewHTTPPolicy",actual_policy), \
                 patch.object(structure_mining,"review_utc_now",return_value=late), \
                 patch.object(shorts_review,"upload") as upload,patch.object(structure_mining,"call") as generate:
                out=ep.review_material(env["manifest"],env["output"])
            self.assertEqual(review.call_count,1)
            upload.assert_not_called();generate.assert_not_called()
            self.assertEqual(out["finalization"]["status"],"COMPLETE")
            self.assertEqual(out[ep.JOURNAL]["state"],"COMPLETE")
            self.assertEqual(out[ep.JOURNAL]["http_completion"],"DEADLINE_EXCEEDED")
            self.assertEqual(out[ep.JOURNAL]["transport_attempts"],[])
            self.assertEqual(out[ep.JOURNAL]["terminal_stage"],"NONE")
            self.assertFalse(out["shorts"][0]["publish"])

    def test_finalize_file_foreign_write_preserved(self):
        with tempfile.TemporaryDirectory() as root,synthetic_environment(root) as env:
            manifest=env["pilot"]/"shorts/shorts.json";real=ep._contract;calls=[0]
            def contract():
                calls[0]+=1;result=real()
                if calls[0]==3:manifest.write_bytes(b"foreign-finalizer")
                return result
            with patch.object(ep,"_contract",side_effect=contract),self.assertRaisesRegex(ep.EvidenceError,"INPUT_CHANGED"):
                ep.finalize_file(manifest,env["output"])
            self.assertEqual(manifest.read_bytes(),b"foreign-finalizer")

    def test_finalize_file_crosses_last_rehash(self):
        with tempfile.TemporaryDirectory() as root,synthetic_environment(root) as env:
            manifest=env["pilot"]/"shorts/shorts.json";real=ep._material_stable;calls=[0]
            def stable(data,digest):
                calls[0]+=1;result=real(data,digest)
                if calls[0]==2:ep.datetime.now.return_value=datetime(2026,10,21,13,16,tzinfo=timezone.utc)
                return result
            with patch.object(ep,"_material_stable",side_effect=stable):out=ep.finalize_file(manifest,env["output"])
            self.assertEqual(out["finalization"]["status"],"COMPLETE")
            self.assertFalse(out["shorts"][0]["publish"])

    def test_coherent_future_evidence_rejected_at_binding(self):
        with tempfile.TemporaryDirectory() as root,synthetic_environment(root) as env:
            ep.datetime.now.return_value=NOW-timedelta(minutes=1)
            with self.assertRaisesRegex(ep.EvidenceError,"FINALIZATION_IN_FUTURE"):
                ep.binding(env["spec"],pilot_dir=env["pilot"])


if __name__ == "__main__":
    unittest.main()
