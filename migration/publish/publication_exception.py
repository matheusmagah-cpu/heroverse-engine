#!/usr/bin/env python3
"""One owner-attested temporal exception, not a quality or identity bypass.

The closed registry pins an operational attestation by dot of authenticated owner
messages. It is NOT a cryptographic owner signature or GitHub-human proof.
Reservation must be persisted remotely before upload by the caller. A local
atomic write alone is not a distributed lock, and uncertain uploads never retry.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

EXCEPTION_ID = "owner-temporal-pilot005-cb3ce331-20261020"
RECEIPT_SHA256 = "dd2990b2ecebe3a7a4ed93d842d248f8e9ea9c3a2ecbfb6921d7b91d3f4db5f2"
PILOT = "pilot-005"
OUTPUT_SHA256 = "cb3ce331529437f4fadc3b14dec01dfad18909a3e9f024a99cea141e91ae956f"
AUTHORIZED_AT = "2026-10-20T21:08:15.004165+00:00"
BINDING = {
    "version": "owner-publication-exception-binding-v1",
    "exception_id": EXCEPTION_ID,
    "receipt_sha256": RECEIPT_SHA256,
    "pilot": PILOT,
    "output_sha256": OUTPUT_SHA256,
    "scope": "temporal_only",
    "baseline_cutoff": "2026-10-20T19:30:00Z",
    "target_slot": "2026-10-20T20:00:00Z",
    "owner_authorized_at": AUTHORIZED_AT,
}


def require(condition, code):
    if not condition:
        raise ValueError("OWNER_EXCEPTION_" + code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def instant(value):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")) if type(value) is str else value
        require(type(dt) is datetime and dt.tzinfo is not None and dt.utcoffset().total_seconds() == 0, "CLOCK_INVALID")
        return dt
    except (TypeError, AttributeError, ValueError):
        raise ValueError("OWNER_EXCEPTION_CLOCK_INVALID") from None


def validate_binding(binding, *, pilot, output_sha256, now_utc):
    require(type(binding) is dict and canonical(binding) == canonical(BINDING), "BINDING_INVALID")
    require(type(pilot) is str and pilot == PILOT, "PILOT_MISMATCH")
    require(type(output_sha256) is str and output_sha256 == OUTPUT_SHA256, "OUTPUT_HASH_MISMATCH")
    require(instant(now_utc) >= instant(AUTHORIZED_AT), "NOT_YET_AUTHORIZED")
    return deepcopy(BINDING)


def validate_receipt(receipt, *, pilot, output_sha256, now_utc):
    require(type(receipt) is dict, "RECEIPT_INVALID")
    require(hashlib.sha256(canonical(receipt)).hexdigest() == RECEIPT_SHA256, "RECEIPT_DIGEST_MISMATCH")
    return validate_binding(BINDING, pilot=pilot, output_sha256=output_sha256, now_utc=now_utc)


def _run_key(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is not None, "RUN_KEY_INVALID")


def _video_id(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{11}", value) is not None, "VIDEO_ID_INVALID")
    return value


def _context(ledger, binding):
    # reserve/consume use the real clock; tests may inject time only at the pure
    # validation APIs. Neither CLI nor ledger accepts a caller's claimed clock.
    bound = validate_binding(binding, pilot=binding.get("pilot") if type(binding) is dict else None,
                             output_sha256=binding.get("output_sha256") if type(binding) is dict else None,
                             now_utc=datetime.now(timezone.utc))
    require(type(ledger) is dict and ledger.get("version") == "publish-ledger-v1"
            and type(ledger.get("entries")) is dict, "LEDGER_INVALID")
    exceptions = ledger.get("owner_exceptions", {})
    require(type(exceptions) is dict, "LEDGER_INVALID")
    reservation = exceptions.get(EXCEPTION_ID)
    if EXCEPTION_ID in exceptions:
        require(type(reservation) is dict and set(reservation) in (
            {"state", "run_key", "binding"}, {"state", "run_key", "binding", "video_id"}), "RESERVATION_INVALID")
        require(reservation["state"] in ("RESERVED", "UNCERTAIN", "CONSUMED"), "RESERVATION_INVALID")
        _run_key(reservation["run_key"])
        require(canonical(reservation["binding"]) == canonical(bound), "RESERVATION_BINDING_MISMATCH")
        if reservation["state"] == "CONSUMED":
            require("video_id" in reservation, "RESERVATION_UNCERTAIN")
    key = f"short:{PILOT}:{OUTPUT_SHA256}"
    entry = ledger["entries"].get(key)
    if key in ledger["entries"]:
        require(type(entry) is dict, "LEDGER_ENTRY_INVALID")
        if "output_sha256" in entry:
            require(entry["output_sha256"] == OUTPUT_SHA256, "LEDGER_HASH_MISMATCH")
    ids = []
    for item in (reservation, entry):
        if item is not None and "video_id" in item:
            ids.append(_video_id(item["video_id"]))
    require(len(set(ids)) <= 1, "VIDEO_ID_CONFLICT")
    known = ids[0] if ids else None
    if known is not None:
        for other_key, other in ledger["entries"].items():
            if other_key != key and type(other) is dict:
                require(other.get("video_id") != known, "VIDEO_ID_REUSED")
        for other_key, other in exceptions.items():
            if other_key != EXCEPTION_ID and type(other) is dict:
                require(other.get("video_id") != known, "VIDEO_ID_REUSED")
    return bound, reservation, known


def reserve(ledger, binding, *, run_key):
    """Pure copy. Any existing uncertain reservation blocks even the same run."""
    _run_key(run_key)
    bound, reservation, known = _context(ledger, binding)
    if known is not None:
        return deepcopy(ledger)  # readback only; never overwrite or reserve anew
    require(reservation is None, "RESERVATION_UNCERTAIN")
    result = deepcopy(ledger)
    result.setdefault("owner_exceptions", {})[EXCEPTION_ID] = {
        "state": "RESERVED", "run_key": run_key, "binding": bound}
    return result


def validate_consumption(ledger, binding, *, run_key, video_id=None):
    """Authorize one reserved attempt or readback of an already persisted ID.

    Before upload, the caller persists state UNCERTAIN locally so a repeat call
    in the same run cannot upload. After upload returns an ID, call again with
    that ID, then atomically persist both
entries[short-key] and owner_exceptions[id] with state CONSUMED and video_id.
This function never modifies a ledger or performs an upload.
"""
    _run_key(run_key)
    _, reservation, known = _context(ledger, binding)
    if video_id is not None:
        _video_id(video_id)
    if known is not None:
        require(video_id is None or video_id == known, "VIDEO_ID_CONFLICT")
        return {"mode": "readback_only", "video_id": known}
    require(reservation is not None, "RESERVATION_REQUIRED")
    require(reservation["run_key"] == run_key, "RESERVATION_RUN_MISMATCH")
    require(reservation["state"] == "RESERVED"
            or (reservation["state"] == "UNCERTAIN" and video_id is not None), "RESERVATION_UNCERTAIN")
    if video_id is not None:
        for entry in ledger["entries"].values():
            require(type(entry) is not dict or entry.get("video_id") != video_id, "VIDEO_ID_REUSED")
        for entry in ledger.get("owner_exceptions", {}).values():
            require(type(entry) is not dict or entry.get("video_id") != video_id, "VIDEO_ID_REUSED")
    return {"mode": "upload", "video_id": video_id}


def _unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "JSON_DUPLICATE_KEY")
        value[key] = item
    return value


def _read(path):
    def invalid(_):
        raise ValueError("OWNER_EXCEPTION_JSON_NONFINITE")
    return json.loads(Path(path).read_bytes(), object_pairs_hook=_unique, parse_constant=invalid)


def atomic_json(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=1, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def reserve_file(ledger_path, manifest_path, run_key):
    ledger, manifest = _read(ledger_path), _read(manifest_path)
    require(type(manifest) is dict and type(manifest.get("finalization")) is dict, "MANIFEST_INVALID")
    final = manifest["finalization"]
    rows = manifest.get("shorts")
    require(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict, "MANIFEST_INVALID")
    row = rows[0]
    require(final.get("status") == "COMPLETE" and row.get("publish") is True
            and manifest.get("release_status") == "READY_BY_OWNER_TEMPORAL_EXCEPTION"
            and row.get("release_status") == "READY_BY_OWNER_TEMPORAL_EXCEPTION"
            and final.get("ordinary_release_status") == "TARGET_SLOT_LEAD_MISSED", "MANIFEST_NOT_ELIGIBLE")
    binding = validate_binding(final.get("owner_exception"), pilot=manifest.get("source_pilot"),
                               output_sha256=row.get("sha256"), now_utc=datetime.now(timezone.utc))
    require(final.get("output_sha256") == binding["output_sha256"]
            and final.get("target_slot") == binding["target_slot"], "MANIFEST_BINDING_MISMATCH")
    reserved = reserve(ledger, binding, run_key=run_key)
    result = validate_consumption(reserved, binding, run_key=run_key)
    if reserved != ledger:
        atomic_json(ledger_path, reserved)
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 4 or argv[0] != "--reserve":
        print("usage: publication_exception.py --reserve LEDGER MANIFEST RUN_KEY", file=sys.stderr)
        return 2
    try:
        result = reserve_file(*argv[1:])
    except (OSError, ValueError, TypeError, KeyError) as error:
        code = str(error) if str(error).startswith("OWNER_EXCEPTION_") else "OWNER_EXCEPTION_INVALID_INPUT"
        print(json.dumps({"status": "ERROR", "reason": code}))
        return 1
    print(json.dumps({"status": "RESERVED" if result["mode"] == "upload" else "READBACK_ONLY", **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
