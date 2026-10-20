"""Offline owner-exception registry and single-attempt reservation contract."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publication_exception as pe

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "migration/evidence/publication-exceptions/pilot-005-cb3ce331-owner.json"
SHA = "cb3ce331529437f4fadc3b14dec01dfad18909a3e9f024a99cea141e91ae956f"
DIGEST = "dd2990b2ecebe3a7a4ed93d842d248f8e9ea9c3a2ecbfb6921d7b91d3f4db5f2"
ID = "owner-temporal-pilot005-cb3ce331-20261020"
NOW = "2026-10-20T21:08:15.004165+00:00"
VIDEO = "AbcDef123_-"
OTHER_VIDEO = "ZbcDef123_-"
KEY = f"short:pilot-005:{SHA}"


def receipt():
    return json.loads(RECEIPT.read_bytes())


def binding():
    return pe.validate_receipt(receipt(), pilot="pilot-005", output_sha256=SHA, now_utc=NOW)


def ledger():
    return {"version": "publish-ledger-v1", "entries": {}}


def reserved():
    return pe.reserve(ledger(), binding(), run_key="12345:1")


def manifest():
    return {"source_pilot": "pilot-005", "release_status": "READY_BY_OWNER_TEMPORAL_EXCEPTION",
            "shorts": [{"sha256": SHA, "publish": True, "release_status": "READY_BY_OWNER_TEMPORAL_EXCEPTION"}],
            "finalization": {"status": "COMPLETE", "output_sha256": SHA, "target_slot": "2026-10-20T20:00:00Z",
                             "ordinary_release_status": "TARGET_SLOT_LEAD_MISSED", "owner_exception": binding()}}


class RegistryTests(unittest.TestCase):
    def test_receipt_canonical_digest_and_explicit_attestation(self):
        r = receipt()
        self.assertEqual(hashlib.sha256(pe.canonical(r)).hexdigest(), DIGEST)
        self.assertEqual(pe.RECEIPT_SHA256, DIGEST)
        self.assertEqual(r["owner"], "Matheus")
        self.assertEqual(r["source"], "authenticated_owner_dot_conversation")
        self.assertEqual(r["attested_by"], "dot")
        self.assertEqual(r["trust_model"], "operational_dot_attestation_not_cryptographic_signature")
        self.assertEqual([x["message_id"] for x in r["owner_messages"]], [
            "Sentinel_b40883ebd1d88191bc6cf23c59f08c49", "Sentinel_c3a1c9f1e7908191883cbda6ed27e9c1",
            "Sentinel_1512cc545d6c81919a5535ce6fc9e0e6"])
        self.assertEqual(binding()["exception_id"], ID)
        self.assertEqual(binding()["baseline_cutoff"], "2026-10-20T19:30:00Z")
        self.assertEqual(binding()["target_slot"], "2026-10-20T20:00:00Z")
        self.assertEqual(binding()["scope"], "temporal_only")

    def test_receipt_changes_missing_and_extra_fields_reject(self):
        for key in receipt():
            with self.subTest(key=key):
                for delete in (False, True):
                    r = receipt()
                    if delete:
                        del r[key]
                    else:
                        r[key] = "altered"
                    with self.assertRaisesRegex(ValueError, "RECEIPT_DIGEST_MISMATCH"):
                        pe.validate_receipt(r, pilot="pilot-005", output_sha256=SHA, now_utc=NOW)
        r = receipt(); r["self_approved"] = True
        with self.assertRaises(ValueError):
            pe.validate_receipt(r, pilot="pilot-005", output_sha256=SHA, now_utc=NOW)
        for bad in (None, [], True, "receipt"):
            with self.assertRaises(ValueError):
                pe.validate_receipt(bad, pilot="pilot-005", output_sha256=SHA, now_utc=NOW)

    def test_receipt_formatting_and_key_order_not_authority(self):
        r = dict(reversed(list(receipt().items())))
        self.assertEqual(pe.validate_receipt(r, pilot="pilot-005", output_sha256=SHA, now_utc=NOW), binding())

    def test_binding_all_fields_pinned_missing_extra_and_forged(self):
        for key in binding():
            for remove in (False, True):
                with self.subTest(key=key, remove=remove):
                    b = binding()
                    if remove: del b[key]
                    else: b[key] = "forged"
                    with self.assertRaisesRegex(ValueError, "BINDING_INVALID"):
                        pe.validate_binding(b, pilot="pilot-005", output_sha256=SHA, now_utc=NOW)
        for b in (None, [], True, {**binding(), "owner": "Matheus"}):
            with self.assertRaises(ValueError):
                pe.validate_binding(b, pilot="pilot-005", output_sha256=SHA, now_utc=NOW)

    def test_pilot_hash_and_microsecond_clock_boundary(self):
        for pilot, sha in (("pilot-006", SHA), ("pilot-005", "a" * 64), (True, SHA), ("pilot-005", None)):
            with self.assertRaises(ValueError):
                pe.validate_receipt(receipt(), pilot=pilot, output_sha256=sha, now_utc=NOW)
        for now in ("2026-10-20T21:08:15.004164Z", "2026-10-20T19:30:00Z"):
            with self.assertRaisesRegex(ValueError, "NOT_YET_AUTHORIZED"):
                pe.validate_binding(binding(), pilot="pilot-005", output_sha256=SHA, now_utc=now)
        for now in (NOW, "2026-10-21T20:00:00Z", datetime(2026, 10, 20, 22, tzinfo=timezone.utc)):
            self.assertEqual(pe.validate_binding(binding(), pilot="pilot-005", output_sha256=SHA, now_utc=now), binding())
        for now in (None, True, "2026-10-20T22:00:00", "2026-10-20T22:00:00+01:00", "bad", datetime(2026, 10, 20, 22)):
            with self.assertRaisesRegex(ValueError, "CLOCK_INVALID"):
                pe.validate_binding(binding(), pilot="pilot-005", output_sha256=SHA, now_utc=now)

    def test_validation_and_reserve_copy_no_side_effects(self):
        r, b, original = receipt(), binding(), ledger()
        before = deepcopy((r, b, original))
        result = pe.reserve(original, b, run_key="12345:1")
        self.assertEqual((r, b, original), before)
        b["scope"] = "all"
        self.assertEqual(result["owner_exceptions"][ID]["binding"]["scope"], "temporal_only")
        result["owner_exceptions"][ID]["binding"]["scope"] = "bad"
        self.assertEqual(binding()["scope"], "temporal_only")


class ReservationTests(unittest.TestCase):
    def test_first_reservation_and_matching_consumption(self):
        r = reserved()
        self.assertEqual(r["owner_exceptions"][ID], {"state": "RESERVED", "run_key": "12345:1", "binding": binding()})
        self.assertEqual(pe.validate_consumption(r, binding(), run_key="12345:1"), {"mode": "upload", "video_id": None})
        self.assertEqual(pe.validate_consumption(r, binding(), run_key="12345:1", video_id=VIDEO), {"mode": "upload", "video_id": VIDEO})

    def test_repeated_reservation_is_uncertain_even_same_run(self):
        for run in ("12345:1", "12345:2", "67890:1"):
            r = reserved(); before = deepcopy(r)
            with self.assertRaisesRegex(ValueError, "RESERVATION_UNCERTAIN"):
                pe.reserve(r, binding(), run_key=run)
            self.assertEqual(r, before)

    def test_missing_reservation_and_wrong_run_cannot_upload(self):
        with self.assertRaisesRegex(ValueError, "RESERVATION_REQUIRED"):
            pe.validate_consumption(ledger(), binding(), run_key="12345:1")
        for run in ("12345:2", "67890:1"):
            with self.assertRaisesRegex(ValueError, "RESERVATION_RUN_MISMATCH"):
                pe.validate_consumption(reserved(), binding(), run_key=run)

    def test_upload_started_without_id_never_retries_even_same_run(self):
        r = reserved(); r["owner_exceptions"][ID]["state"] = "UNCERTAIN"
        for run in ("12345:1", "12345:2"):
            with self.assertRaises(ValueError):
                pe.validate_consumption(r, binding(), run_key=run)
            with self.assertRaisesRegex(ValueError, "RESERVATION_UNCERTAIN"):
                pe.reserve(r, binding(), run_key=run)
        self.assertEqual(pe.validate_consumption(r, binding(), run_key="12345:1", video_id=VIDEO),
                         {"mode": "upload", "video_id": VIDEO})
        with self.assertRaisesRegex(ValueError, "RESERVATION_RUN_MISMATCH"):
            pe.validate_consumption(r, binding(), run_key="12345:2", video_id=VIDEO)

    def test_saved_id_is_readback_only_and_reserve_never_mutates(self):
        for location in ("reservation", "entry", "both", "entry_without_reservation"):
            with self.subTest(location=location):
                r = ledger() if location == "entry_without_reservation" else reserved()
                if location in ("reservation", "both"):
                    r["owner_exceptions"][ID].update(state="CONSUMED", video_id=VIDEO)
                if location in ("entry", "both", "entry_without_reservation"):
                    r["entries"][KEY] = {"video_id": VIDEO, "output_sha256": SHA}
                before = deepcopy(r)
                self.assertEqual(pe.reserve(r, binding(), run_key="77777:2"), before)
                self.assertEqual(pe.validate_consumption(r, binding(), run_key="77777:2"), {"mode": "readback_only", "video_id": VIDEO})
                self.assertEqual(pe.validate_consumption(r, binding(), run_key="77777:2", video_id=VIDEO)["mode"], "readback_only")
                self.assertEqual(r, before)

    def test_conflicting_ids_and_reused_ids_fail(self):
        r = reserved(); r["owner_exceptions"][ID]["video_id"] = VIDEO
        r["entries"][KEY] = {"video_id": OTHER_VIDEO, "output_sha256": SHA}
        with self.assertRaisesRegex(ValueError, "VIDEO_ID_CONFLICT"):
            pe.reserve(r, binding(), run_key="12345:1")
        r = reserved(); r["owner_exceptions"][ID]["video_id"] = VIDEO
        with self.assertRaisesRegex(ValueError, "VIDEO_ID_CONFLICT"):
            pe.validate_consumption(r, binding(), run_key="12345:1", video_id=OTHER_VIDEO)
        for bucket in ("entries", "owner_exceptions"):
            r = reserved(); r[bucket]["different-key"] = {"video_id": VIDEO}
            with self.assertRaisesRegex(ValueError, "VIDEO_ID_REUSED"):
                pe.validate_consumption(r, binding(), run_key="12345:1", video_id=VIDEO)
            r["owner_exceptions"][ID]["video_id"] = VIDEO
            with self.assertRaisesRegex(ValueError, "VIDEO_ID_REUSED"):
                pe.reserve(r, binding(), run_key="12345:1")

    def test_invalid_ledger_reservation_binding_or_video_id(self):
        for bad in (None, [], {}, {"version": "wrong", "entries": {}}, {"version": "publish-ledger-v1", "entries": []},
                    {**ledger(), "owner_exceptions": None}, {**ledger(), "owner_exceptions": []}):
            with self.assertRaises(ValueError): pe.reserve(bad, binding(), run_key="12345:1")
        for value in (None, [], {}, {"state": "CONSUMED", "run_key": "12345:1", "binding": binding()},
                      {"state": "UNKNOWN", "run_key": "12345:1", "binding": binding()},
                      {"state": "RESERVED", "run_key": "12345:1", "binding": {**binding(), "scope": "all"}}):
            r = ledger(); r["owner_exceptions"] = {ID: value}
            with self.assertRaises(ValueError): pe.reserve(r, binding(), run_key="12345:1")
        for value in (None, True, "", "too-short", "!" * 11):
            r = reserved(); r["owner_exceptions"][ID]["video_id"] = value
            with self.assertRaisesRegex(ValueError, "VIDEO_ID_INVALID"):
                pe.reserve(r, binding(), run_key="12345:1")
        r = reserved(); r["entries"][KEY] = {"video_id": VIDEO, "output_sha256": "a" * 64}
        with self.assertRaisesRegex(ValueError, "LEDGER_HASH_MISMATCH"):
            pe.reserve(r, binding(), run_key="12345:1")
        for run in (None, True, "", "a b", "a\nb", "a" * 129):
            with self.assertRaisesRegex(ValueError, "RUN_KEY_INVALID"):
                pe.reserve(ledger(), binding(), run_key=run)

    def test_other_hash_entry_does_not_consume_this_exception(self):
        r = ledger(); r["entries"]["short:pilot-005:" + "a" * 64] = {"video_id": VIDEO}
        self.assertEqual(pe.reserve(r, binding(), run_key="12345:1")["owner_exceptions"][ID]["state"], "RESERVED")


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lp, self.mp = self.root / "ledger.json", self.root / "shorts.json"
        self.lp.write_text(json.dumps(ledger())); self.mp.write_text(json.dumps(manifest()))

    def call(self, run="12345:1"):
        return subprocess.run([sys.executable, "-I", "-O", "-B", pe.__file__, "--reserve", str(self.lp), str(self.mp), run],
                              capture_output=True, text=True)

    def test_cli_reserves_once_atomic_and_never_changes_manifest(self):
        before = self.mp.read_bytes()
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "RESERVED")
        after = self.lp.read_bytes()
        self.assertEqual(self.mp.read_bytes(), before)
        self.assertEqual(self.call().returncode, 1)
        self.assertEqual(self.lp.read_bytes(), after)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_cli_existing_id_readback_no_write(self):
        r = reserved(); r["owner_exceptions"][ID].update(state="CONSUMED", video_id=VIDEO)
        self.lp.write_text(json.dumps(r)); before = self.lp.read_bytes()
        result = self.call("12345:2")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "READBACK_ONLY")
        self.assertEqual(self.lp.read_bytes(), before)

    def test_cli_manifest_binding_and_eligibility_tampering_no_write(self):
        for field in ("pilot", "output", "binding", "target", "ordinary", "status", "publish", "release", "row_release"):
            with self.subTest(field=field):
                m = manifest()
                if field == "pilot": m["source_pilot"] = "pilot-006"
                elif field == "output": m["shorts"][0]["sha256"] = "a" * 64
                elif field == "binding": del m["finalization"]["owner_exception"]
                elif field == "target": m["finalization"]["target_slot"] = "2026-10-21T20:00:00Z"
                elif field == "ordinary": m["finalization"]["ordinary_release_status"] = "QA_FAIL"
                elif field == "status": m["finalization"]["status"] = "ERROR"
                elif field == "publish": m["shorts"][0]["publish"] = False
                elif field == "release": m["release_status"] = "READY_FOR_TARGET_SLOT"
                else: m["shorts"][0]["release_status"] = "REVIEW_FAIL"
                self.mp.write_text(json.dumps(m)); before = self.lp.read_bytes()
                self.assertEqual(self.call().returncode, 1)
                self.assertEqual(self.lp.read_bytes(), before)

    def test_cli_duplicate_json_and_malformed_inputs_reject(self):
        for raw in ('{"entries":{},"entries":{}}', 'NaN', 'null', '{bad'):
            self.lp.write_text(raw)
            result = self.call()
            self.assertEqual(result.returncode, 1)
            self.assertEqual(self.lp.read_text(), raw)
        self.assertEqual(pe.main([]), 2)

    def test_atomic_failure_preserves_original_and_cleans_temp(self):
        before = self.lp.read_bytes()
        with patch.object(pe.os, "replace", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError): pe.reserve_file(self.lp, self.mp, "12345:1")
        self.assertEqual(self.lp.read_bytes(), before)
        self.assertEqual(list(self.root.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
