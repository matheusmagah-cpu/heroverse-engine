#!/usr/bin/env python3
"""Publish the Shorts cut from a published long video, each scheduled at its slot.

Gates, all BEFORE upload (owner rule): the long video is already in the ledger
(uploaded, public or scheduled) so every Short can point to it; each Short
passes shorts_qa (vertical 1080x1920, 15-60 s, loudness, true peak, decode) and
its file hash matches shorts.json. Idempotent per Short hash through the same
ledger as publish_video.py. The Data API has no field for the Shorts "related
video", so the link to the full video is the first line of the description.
usage: publish_shorts.py SHORTS_JSON SHORTS_DIR LONG_KEY LEDGER RECEIPT SLOT_ISO[,SLOT_ISO...]
"""
from datetime import datetime, timezone
import hashlib
import json
import os
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_shorts  # noqa: E402
import publish_video as pv  # noqa: E402
import shorts_qa  # noqa: E402


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def title_for(short):
    if short.get("title") and short["title"] != short.get("hook"):
        t = short["title"].strip()
        return t if "#shorts" in t.lower() or len(t) > 90 else t + " #shorts"
    hook = short["hook"].rstrip(".!?")
    title = f"{hook} 🙏 #shorts"
    return title if len(title) <= 100 else hook[:88] + "… #shorts"


def description_for(short, long_url, long_title):
    ref = f"\n\n📖 {short['reference']}" if short.get("reference") else ""
    return (f"▶ Full prayer: {long_url}\n{long_title}{ref}\n\n"
            "Pray this with me and type AMEN if you receive it.\n\n#prayer #morningprayer #jesus #faith #shorts")


REST_OUTPUT_SHA256 = "96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e"


def _rest_correction(short, pilot):
    return pilot == "pilot-006" and short.get("sha256") == REST_OUTPUT_SHA256


def _rest_identity(short):
    expected = {"file": "short-00.mp4", "title": "Rest in God's Care",
                "hook": "Let your face soften.", "reference": None}
    return all(key in short and short[key] == value for key, value in expected.items())


def metadata_for(short, long_url, long_title, *, pilot=None):
    """Formatting only. New-upload authority remains in the existing gates."""
    if _rest_correction(short, pilot):
        return {"title": "Rest in God's Care #shorts",
                "description": f"▶ Full prayer: {long_url}\n{long_title}\n\n"
                               "A quiet moment to rest in God's care.\n\n#prayer #rest #jesus #faith #shorts",
                "tags": ["prayer", "rest", "christian reflection", "jesus", "faith", "shorts"]}
    return {"title": title_for(short), "description": description_for(short, long_url, long_title),
            "tags": ["prayer", "morning prayer", "jesus", "faith", "bible", "shorts"]}


def utc_now():
    return datetime.now(timezone.utc)


def utc_instant(value):
    if not isinstance(value, str):
        raise ValueError("MISSING_TIMESTAMP")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return dt.astimezone(timezone.utc)


def atomic_json(path, value):
    """Durable atomic replacement; never leave partially written JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, indent=1, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def observe_video(session, video_id, *, include_tags=False):
    """Authenticated GET only; never serialize raw exceptions or responses."""
    fields = {"video_id": ("id",), "channel_id": ("snippet", "channelId"),
              "title": ("snippet", "title"), "description": ("snippet", "description"),
              "default_language": ("snippet", "defaultLanguage"),
              "default_audio_language": ("snippet", "defaultAudioLanguage"),
              "upload_status": ("status", "uploadStatus"), "privacy_status": ("status", "privacyStatus"),
              "publish_at": ("status", "publishAt"), "license": ("status", "license"),
              "contains_synthetic_media": ("status", "containsSyntheticMedia"),
              "processing_status": ("processingDetails", "processingStatus")}
    if include_tags:
        fields["tags"] = ("snippet", "tags")
    observation = {k: None for k in fields}
    observation.update(observed_at=utc_now().isoformat(), unknown_fields={})
    try:
        response = session.get(pv.API + "videos", params={
            "part": "id,snippet,status,processingDetails", "id": video_id}, timeout=30)
        data = pv.check(response, "VERIFY")
        items = data.get("items")
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
            raise ValueError("MISSING_VIDEO")
        for name, path in fields.items():
            value = items[0]
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            expected_type = bool if name == "contains_synthetic_media" else str
            valid = (type(value) is list and all(type(tag) is str for tag in value)) if name == "tags" else type(value) is expected_type
            if valid:
                observation[name] = value
            else:
                observation["unknown_fields"][name] = "MISSING_OR_INVALID_FIELD"
        return observation, None
    except (Exception, SystemExit):
        observation["unknown_fields"] = {name: "READBACK_UNAVAILABLE" for name in fields}
        return observation, "READBACK_UNAVAILABLE"


def _verification(observation, error, video_id, slot, expected, now=None):
    now = now or utc_now()
    if error:
        return "VERIFICATION_UNKNOWN", error
    required = {"video_id": video_id, "channel_id": pv.CHANNEL,
                "title": expected["title"], "description": expected["description"],
                "default_language": "en", "default_audio_language": "en",
                "license": "youtube", "contains_synthetic_media": True}
    for key, value in required.items():
        if observation.get(key) is None:
            return "VERIFICATION_UNKNOWN", "MISSING_" + key.upper()
        if observation[key] != value:
            return "VERIFICATION_FAIL", "MISMATCH_" + key.upper()
    try:
        target = utc_instant(slot)
    except (ValueError, TypeError):
        return "VERIFICATION_UNKNOWN", "INVALID_INTENDED_SLOT"
    privacy = observation.get("privacy_status")
    if privacy is None:
        return "VERIFICATION_UNKNOWN", "MISSING_PRIVACY_STATUS"
    if now < target:
        if privacy != "private":
            return "VERIFICATION_FAIL", "PRIVACY_BEFORE_SLOT"
        try:
            if utc_instant(observation.get("publish_at")) != target:
                return "VERIFICATION_FAIL", "PUBLISH_AT_MISMATCH"
        except (ValueError, TypeError):
            return "VERIFICATION_UNKNOWN", "MISSING_OR_INVALID_PUBLISH_AT"
    elif privacy != "public":
        return "VERIFICATION_FAIL", "NOT_PUBLIC_AT_SLOT"
    upload, processing = observation.get("upload_status"), observation.get("processing_status")
    if upload in ("failed", "rejected", "deleted") or processing == "failed":
        return "VERIFICATION_FAIL", "REMOTE_PROCESSING_FAILED"
    if upload is None or processing is None or processing == "terminated":
        return "VERIFICATION_UNKNOWN", "PROCESSING_STATUS_UNAVAILABLE"
    if upload == "uploaded" or processing == "processing":
        return "PENDING_PROCESSING", "PROCESSING_INCOMPLETE"
    if upload != "processed" or processing != "succeeded":
        return "VERIFICATION_UNKNOWN", "UNRECOGNIZED_PROCESSING_STATUS"
    return ("SCHEDULED_VERIFIED" if now < target else "PUBLIC_VERIFIED"), None



def verification(observation, error, video_id, slot, expected, now=None):
    status, reason = _verification(observation, error, video_id, slot, expected, now)
    # Never mask an established identity/privacy/processing failure with an
    # unknown optional field. Legacy expected dictionaries do not contain tags.
    if "tags" in expected and not error and status != "VERIFICATION_FAIL":
        tags = observation.get("tags")
        if type(tags) is not list or any(type(tag) is not str for tag in tags):
            return "VERIFICATION_UNKNOWN", "MISSING_TAGS"
        if tags != expected["tags"]:
            return "VERIFICATION_FAIL", "MISMATCH_TAGS"
    return status, reason


def exception_binding(spec):
    """Validate the closed registry and retained media gates, never a free-form flag."""
    final = spec.get("finalization", {})
    if not isinstance(final, dict) or "owner_exception" not in final:
        return None
    import publication_exception as pe
    records = spec.get("shorts", [])
    if len(records) != 1 or final.get("status") != "COMPLETE":
        raise SystemExit("EXCEPTION_MANIFEST_INVALID")
    record = records[0]
    if (spec.get("release_status") != "READY_BY_OWNER_TEMPORAL_EXCEPTION" or
            record.get("release_status") != "READY_BY_OWNER_TEMPORAL_EXCEPTION" or
            final.get("ordinary_release_status") != "TARGET_SLOT_LEAD_MISSED"):
        raise SystemExit("EXCEPTION_RELEASE_MARKER_INVALID")
    binding = final["owner_exception"]
    pe.validate_binding(binding, pilot=spec.get("source_pilot"),
                        output_sha256=record.get("sha256"), now_utc=utc_now())
    if final.get("target_slot") != binding["target_slot"]:
        raise SystemExit("EXCEPTION_TARGET_SLOT_MISMATCH")
    digest = record.get("sha256")
    review, qa, media = record.get("review", {}), record.get("qa", {}), record.get("media_checks", {})
    scores = ("hook_in_first_2s", "captions_readable_and_synced", "text_clear_of_shorts_ui",
              "picture_quality", "edit_rhythm", "audio_clarity", "stands_alone", "ending_and_loop", "policy_safe")
    checks = ("decode_clean", "one_h264_1080x1920", "fps_30", "one_aac_stereo_48k", "duration", "loudness", "true_peak")
    def score(value, minimum):
        return type(value) in (int, float) and minimum <= value <= 10
    if not (final.get("output_sha256") == digest
            and record.get("qa_output_sha256") == review.get("output_sha256") == media.get("output_sha256") == digest
            and qa.get("status") == media.get("status") == review.get("status") == "PASS"
            and all(qa.get("checks", {}).get(key) is True for key in checks)
            and review.get("model") == "gemini-3.8-flash"
            and all(score(review.get(key), 7) for key in scores) and score(review.get("overall"), 8)):
        raise SystemExit("EXCEPTION_MEDIA_GATES_FAILED")
    return binding


def recovery_upload_gate(spec, shorts_json, shorts_dir, long_key, slots, now):
    """Validate NEW pilot006 uploads; this is not an editorial approval."""
    import review_recovery as rr
    path = Path(shorts_json)
    pilot_dir = path.parent.parent
    context_pilot = pilot_dir.name
    key_pilot = long_key.split(":", 1)[0]
    if rr.PILOT not in (context_pilot, key_pilot, spec.get("source_pilot")):
        return None
    if (path.name != "shorts.json" or path.parent.name != "shorts"
            or tuple(path.parts[-5:]) != ("migration", "production", rr.PILOT, "shorts", "shorts.json")
            or key_pilot != rr.PILOT or spec.get("source_pilot") != rr.PILOT):
        raise SystemExit("RECOVERY_PILOT_CONTEXT_MISMATCH")
    media = Path(shorts_dir)
    if (".." in path.parts or ".." in media.parts or not media.is_dir() or any(p.is_symlink() for p in (media, *media.parents))
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise SystemExit("RECOVERY_PATH_SYMLINK_OR_INVALID")
    try:
        bound = pending_shorts.recovery_gate(spec, pilot_dir, now)
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise SystemExit("RECOVERY_BINDING_INVALID") from error
    chosen = [r for r in spec["shorts"] if r.get("publish") is True]
    if (len(chosen) != 1 or chosen[0].get("sha256") != bound["output_sha256"]
            or chosen[0].get("file") != rr.FILE or slots != [bound["target_slot"]]):
        raise SystemExit("RECOVERY_SINGLE_TARGET_REQUIRED")
    media_file = media / rr.FILE
    if not media_file.is_file() or media_file.is_symlink():
        raise SystemExit("RECOVERY_MEDIA_INVALID")
    return bound


def main(shorts_json, shorts_dir, long_key, ledger_path, receipt_path, slots):
    spec = json.loads(Path(shorts_json).read_text())
    binding = exception_binding(spec)
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text())
    run_key = None
    if binding is not None:
        import publication_exception as pe
        run_key = os.environ.get("GITHUB_RUN_ID", "") + ":" + os.environ.get("GITHUB_RUN_ATTEMPT", "")
        if not all(x.isdigit() and int(x) > 0 for x in run_key.split(":")):
            raise SystemExit("EXCEPTION_RUN_KEY_INVALID")
    long_entry = ledger["entries"].get(long_key)
    if not long_entry or "video_id" not in long_entry:
        raise SystemExit("LONG_VIDEO_NOT_PUBLISHED")
    slots = [s for s in slots.split(",") if s]
    # Editorial-plan publication is bound to its authorized target, not a stale
    # ledger slot. Legacy multi-Short inputs still assign slots only to todo.
    target_slot = None
    if "edit_plan" in spec or "finalization" in spec:
        finalization = spec.get("finalization")
        if not isinstance(finalization, dict):
            raise SystemExit("MISSING_AUTHORIZED_TARGET_SLOT")
        target_slot = finalization.get("target_slot")
        try:
            target_instant = utc_instant(target_slot)
        except (ValueError, TypeError):
            raise SystemExit("INVALID_AUTHORIZED_TARGET_SLOT")
    new_records = [r for r in spec["shorts"] if r.get("publish") and
                   "video_id" not in ledger["entries"].get(f"short:{spec['source_pilot']}:{r['sha256']}", {})]
    recovery = recovery_upload_gate(spec, shorts_json, shorts_dir, long_key, slots, utc_now()) if new_records else None
    if recovery is not None:
        target = utc_instant(recovery["target_slot"])
        pilot_dir = Path(shorts_json).parent.parent
        try:
            if target in pending_shorts.taken(pilot_dir.parent, ledger["entries"], pilot_dir.name):
                raise SystemExit("RECOVERY_TARGET_ALREADY_TAKEN")
            schedule = json.loads((pilot_dir / "schedule.json").read_text())
            if pending_shorts.when(schedule["publish_at"]) + pending_shorts.timedelta(minutes=30) > target:
                raise SystemExit("RECOVERY_LONG_OPENS_TOO_LATE")
        except (OSError, ValueError, TypeError, KeyError):
            raise SystemExit("RECOVERY_SLOT_EVIDENCE_INVALID")
    spec["shorts"] = [r for r in spec["shorts"] if r.get("publish") or
                      "video_id" in ledger["entries"].get(f"short:{spec['source_pilot']}:{r['sha256']}", {})]  # only the Shorts the watched review approved
    if not spec["shorts"]:
        raise SystemExit("NO_SHORT_APPROVED_BY_REVIEW")
    # Shorts already in the ledger keep their slot; only the ones still to upload need one (a partial earlier run
    # used to make this fail with NOT_ENOUGH_SLOTS although nothing was missing)
    todo = [r for r in spec["shorts"] if "video_id" not in ledger["entries"].get(f"short:{spec['source_pilot']}:{r['sha256']}", {})]
    if len(slots) < len(todo):
        raise SystemExit(f"NOT_ENOUGH_SLOTS {len(slots)} slots for {len(todo)} Shorts to upload")
    slot_of = dict(zip((r["sha256"] for r in todo), slots))
    # Closed NEW correction identity check before session/credentials. Existing
    # IDs bypass this check and retain authenticated readback even if local
    # editorial fields are absent or inconsistent.
    if spec.get("source_pilot") == "pilot-006" and spec.get("finalization", {}).get("kind") == "pilot-006-correction-v1":
        for short in todo:
            if not _rest_correction(short, spec["source_pilot"]) or not _rest_identity(short):
                raise SystemExit("CORRECTION_METADATA_IDENTITY_MISMATCH")
    reports = {}
    for short in todo:  # files of Shorts already uploaded were deleted from the release; nothing to check there
        if not pending_shorts.approved(short):
            raise SystemExit("SHORT_NOT_REVIEWED_PASS_BY_DESIGNATED_MODEL " + short["file"])
        path = Path(shorts_dir) / short["file"]
        if sha256_file(path) != short["sha256"]:
            raise SystemExit("SHORT_HASH_MISMATCH " + short["file"])
        report = shorts_qa.check(path)
        reports[short["sha256"]] = report
        if report["status"] != "PASS":
            raise SystemExit("SHORT_QA_FAIL " + json.dumps(report))
    if recovery is not None and utc_now() > utc_instant(recovery["release_deadline"]):
        raise SystemExit("TARGET_SLOT_LEAD_MISSED")
    s = pv.session()
    if [c["id"] for c in pv.check(s.get(pv.API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [pv.CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    long_id = long_entry["video_id"]
    long = pv.check(s.get(pv.API + "videos", params={"part": "snippet", "id": long_id}), "LONG")["items"][0]
    out = []
    receipt = {"version": "shorts-receipt-v1", "long_video_id": long_id, "shorts": out}
    for short in spec["shorts"]:
        slot, report = slot_of.get(short["sha256"]), reports.get(short["sha256"])
        key = f"short:{spec['source_pilot']}:{short['sha256']}"
        entry = ledger["entries"].get(key, {"steps": {}})
        if binding is not None:
            consumption = pe.validate_consumption(ledger, binding, run_key=run_key, video_id=entry.get("video_id"))
            if consumption["mode"] == "readback_only" and not entry.get("video_id"):
                raise SystemExit("EXCEPTION_ID_REQUIRES_LEDGER_RECONCILIATION")
        rest = _rest_correction(short, spec.get("source_pilot"))
        local_metadata_mismatch = rest and not _rest_identity(short)
        metadata = metadata_for(short, f"https://youtu.be/{long_id}", long["snippet"]["title"], pilot=spec.get("source_pilot"))
        expected = {"title": metadata["title"], "description": metadata["description"]}
        if rest:
            expected["tags"] = metadata["tags"]
        if "video_id" not in entry:
            if recovery is not None and utc_now() > utc_instant(recovery["release_deadline"]):
                raise SystemExit("TARGET_SLOT_LEAD_MISSED")
            try:
                if target_slot is not None and utc_instant(slot) != target_instant:
                    raise SystemExit("UPLOAD_SLOT_DIFFERS_FROM_AUTHORIZED_TARGET")
                if utc_instant(slot) <= utc_now() and binding is None:
                    raise ValueError("PAST_SLOT")
            except (ValueError, TypeError):
                raise SystemExit("INVALID_OR_PAST_UPLOAD_SLOT")
            body = {"snippet": {"title": metadata["title"], "description": metadata["description"],
                                "tags": metadata["tags"],
                                "categoryId": "22", "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                    "status": {"privacyStatus": "private", "publishAt": slot, "selfDeclaredMadeForKids": False,
                               "embeddable": True, "license": "youtube", "publicStatsViewable": True,
                               "containsSyntheticMedia": True}}
            if binding is not None and utc_now() >= target_instant:
                body["status"]["privacyStatus"] = "public"
                body["status"].pop("publishAt")
            if binding is not None:
                ledger["owner_exceptions"][binding["exception_id"]]["state"] = "UNCERTAIN"
                atomic_json(ledger_path, ledger)  # no second attempt even if upload never returns
            entry.update({"video_id": pv.upload(s, Path(shorts_dir) / short["file"], body)["id"],
                          "uploaded_at": utc_now().isoformat(), "long_video_id": long_id, "slot": slot,
                          "output_sha256": short["sha256"],
                          "qa": report})
            if binding is not None:
                pe.validate_consumption(ledger, binding, run_key=run_key, video_id=entry["video_id"])
                reserved = ledger["owner_exceptions"][binding["exception_id"]]
                reserved.update(state="CONSUMED", video_id=entry["video_id"])
                entry["owner_exception_id"] = binding["exception_id"]
            ledger["entries"][key] = entry
            atomic_json(ledger_path, ledger)  # durable ID before readback
        result = {"key": key, "file": "short-00.mp4" if rest else short["file"], "output_sha256": entry.get("output_sha256"),
                  "expected_output_sha256": short["sha256"],
                  "upload_status": None, "video_id": entry["video_id"],
                  "url": f"https://youtube.com/shorts/{entry['video_id']}",
                  "slot": entry["slot"], "title": metadata["title"],
                  "verification_status": "VERIFICATION_UNKNOWN", "verification_reason": "READBACK_PENDING",
                  "observation": None}
        if binding is not None:
            result["owner_exception_id"] = binding["exception_id"]
        out.append(result)
        atomic_json(receipt_path, receipt)  # accepted ID survives readback failure
        observation, error = observe_video(s, entry["video_id"], include_tags=True) if rest else observe_video(s, entry["video_id"])
        verification_slot = target_slot if target_slot is not None else entry["slot"]
        status, reason = verification(observation, error, entry["video_id"], verification_slot, expected)
        if target_slot is not None:
            try:
                slot_conflict = (utc_instant(entry["slot"]) != target_instant or
                                 any(utc_instant(x) != target_instant for x in slots))
            except (ValueError, TypeError):
                slot_conflict = True
            if slot_conflict:
                status, reason = "VERIFICATION_FAIL", "AUTHORIZED_TARGET_SLOT_MISMATCH"
            result["authorized_target_slot"] = target_slot
        bound_hash = entry.get("output_sha256")
        if bound_hash is not None and bound_hash != short["sha256"]:
            status, reason = "VERIFICATION_FAIL", "OUTPUT_SHA256_MISMATCH"
        elif bound_hash is None and status != "VERIFICATION_FAIL":
            status, reason = "VERIFICATION_UNKNOWN", "OUTPUT_SHA256_UNRECORDED"
        if local_metadata_mismatch and status != "VERIFICATION_FAIL" and reason != "OUTPUT_SHA256_UNRECORDED":
            status, reason = "VERIFICATION_UNKNOWN", "LOCAL_METADATA_IDENTITY_MISMATCH"
        result.update(upload_status=observation["upload_status"], observation=observation,
                      verification_status=status, verification_reason=reason)
        entry["verification"] = {"status": status, "reason": reason, "observation": observation}
        ledger["entries"][key] = entry
        atomic_json(ledger_path, ledger)
        receipt["verified_at"] = utc_now().isoformat()
        atomic_json(receipt_path, receipt)

    print(json.dumps(out))


if __name__ == "__main__":
    main(*sys.argv[1:7])
