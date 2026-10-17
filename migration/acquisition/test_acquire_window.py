"""Offline guards for acquire_window: no network, no provider call."""
import copy
import datetime as dt
import json
import unittest

import acquire_window as a

FREE = {"x-ratelimit-units-limit": "500", "x-ratelimit-units-remaining": "480",
        "x-ratelimit-rapid-free-plans-hard-limit-limit": "500000",
        "x-ratelimit-rapid-free-plans-hard-limit-remaining": "499000"}
NOW = dt.datetime(2026, 10, 17, 12, tzinfo=dt.timezone.utc)


def ledger():
    return copy.deepcopy(json.loads(a.LEDGER.read_text()))


class Guards(unittest.TestCase):
    def test_reserve_appends_claim(self):
        led = ledger()
        claim = a.reserve("BeFOHnncaeQ", 120, 160, NOW, FREE, led)
        self.assertEqual(claim["status"], "RESERVED_BEFORE_EFFECT")
        self.assertEqual(led["claims"][-1]["request_id"], "acq-BeFOHnncaeQ-120-160-v1")

    def test_historic_windows_never_repeated(self):
        for window in (("j2rk8ycXe3c", 6354, 6364), ("BeFOHnncaeQ", 0, 40)):
            with self.assertRaisesRegex(a.AcquisitionError, "HISTORIC_WINDOW_NEVER_REPEATED"):
                a.reserve(*window, NOW, FREE, ledger())

    def test_same_request_never_twice_and_open_claim_blocks(self):
        led = ledger()
        a.reserve("BeFOHnncaeQ", 120, 160, NOW, FREE, led)
        with self.assertRaisesRegex(a.AcquisitionError, "PRIOR_CLAIM_EXISTS_NO_RESTART"):
            a.reserve("BeFOHnncaeQ", 120, 160, NOW, FREE, led)
        with self.assertRaisesRegex(a.AcquisitionError, "UNRESOLVED_CLAIM_EXISTS"):
            a.reserve("BeFOHnncaeQ", 200, 240, NOW, FREE, led)

    def test_paid_or_exhausted_plan_refused(self):
        for change, code in (({"x-ratelimit-units-limit": "10000"}, "UNIT_PLAN_NOT_FREE_500"),
                             ({"x-ratelimit-units-remaining": "110"}, "UNIT_FLOOR_WOULD_BE_BROKEN")):
            headers = dict(FREE, **change)
            with self.assertRaisesRegex(a.AcquisitionError, code):
                a.reserve("BeFOHnncaeQ", 120, 160, NOW, headers, ledger())
        headers = {k: v for k, v in FREE.items() if "free-plans" not in k}
        with self.assertRaisesRegex(a.AcquisitionError, "FREE_PLAN_HARD_LIMIT_HEADER_MISSING"):
            a.reserve("BeFOHnncaeQ", 120, 160, NOW, headers, ledger())

    def test_window_validation_and_daily_cap(self):
        for args, code in ((("bad", 0, 40), "INVALID_VIDEO_ID"), (("BeFOHnncaeQ", 50, 40), "INVALID_WINDOW"),
                           (("BeFOHnncaeQ", 0, 5), "WINDOW_LENGTH_OUT_OF_RANGE"),
                           (("BeFOHnncaeQ", 0, 400), "WINDOW_LENGTH_OUT_OF_RANGE")):
            with self.assertRaisesRegex(a.AcquisitionError, code):
                a.reserve(*args, NOW, FREE, ledger())
        led = ledger()
        for k in range(led["daily_job_cap"]):
            led["claims"].append({"request_id": f"x{k}", "status": "COMPLETED", "day_utc": "2026-10-17"})
        with self.assertRaisesRegex(a.AcquisitionError, "DAILY_JOB_CAP"):
            a.reserve("BeFOHnncaeQ", 120, 160, NOW, FREE, led)

    def test_finish_is_terminal(self):
        led = ledger()
        a.reserve("BeFOHnncaeQ", 120, 160, NOW, FREE, led)
        claim = a.finish(led, "acq-BeFOHnncaeQ-120-160-v1",
                         {"status": "BLOCKED", "effect_status": "JOB_ID_RECEIVED_NO_RESTART_ALLOWED",
                          "failure_code": "PENDING_STOP_NO_AUTOMATIC_RECOVERY"})
        self.assertEqual(claim["status"], "FAILED_TERMINAL_EFFECT_UNKNOWN")
        self.assertFalse(claim["restart_allowed"])
        with self.assertRaisesRegex(a.AcquisitionError, "NO_OPEN_CLAIM"):
            a.finish(led, "acq-BeFOHnncaeQ-120-160-v1", {"status": "WINDOW_RECEIVED_AND_DECODED"})


if __name__ == "__main__":
    unittest.main()
