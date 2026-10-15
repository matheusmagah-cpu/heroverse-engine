import copy
import datetime as dt
import unittest
from next_window import budget_preflight, REQUEST_ID, n


def ledger():
    now = dt.datetime.now(dt.timezone.utc)
    claim = {'request_id': REQUEST_ID, 'status': 'RESERVED_BEFORE_EFFECT',
        'reserved_at': now.isoformat(), 'day_utc': now.date().isoformat(),
        'reserved_transfer_bytes': 80 * 1024**2, 'reserved_runner_minutes': 10,
        'reserved_units': 14, 'reserved_requests': 40}
    return {'version': 'native-av-reservations-v1', 'claims': [claim],
            'production': False, 'publication': False}


class AdmissionTests(unittest.TestCase):
    def test_duplicate_or_spent_claim_cannot_reenter(self):
        for duplicated in [True, False]:
            value = ledger()
            if duplicated:
                value['claims'].append(copy.deepcopy(value['claims'][0]))
            else:
                value['claims'][0]['status'] = 'START_ATTEMPTED'
            with self.assertRaises(n.ProbeError):
                budget_preflight(value)

    def test_missing_expired_or_reduced_reservation_blocks(self):
        for mode in ['missing', 'expired', 'reduced']:
            value = ledger()
            if mode == 'missing':
                value['claims'] = []
            elif mode == 'expired':
                value['claims'][0]['reserved_at'] = '2020-01-01T00:00:00+00:00'
            else:
                value['claims'][0]['reserved_transfer_bytes'] = -1
            with self.subTest(mode=mode), self.assertRaises(n.ProbeError):
                budget_preflight(value)

    def test_fourth_daily_job_stops_before_remote_work(self):
        value = ledger()
        for i in range(3):
            c = copy.deepcopy(value['claims'][0]); c['request_id'] = str(i)
            value['claims'].append(c)
        with self.assertRaisesRegex(n.ProbeError, 'DAILY_JOB_CAP'):
            budget_preflight(value)

    def test_unresolved_claim_retains_full_monthly_transfer_reservation(self):
        value = ledger()
        for i in range(96):
            c = copy.deepcopy(value['claims'][0]); c['request_id'] = str(i); c['day_utc'] = '2026-10-01'
            value['claims'].append(c)
        with self.assertRaisesRegex(n.ProbeError, 'MONTHLY_TRANSFER_CAP'):
            budget_preflight(value)

    def test_one_fresh_full_reservation_is_admissible_but_not_an_approval(self):
        self.assertIsNone(budget_preflight(ledger()))


if __name__ == '__main__':
    unittest.main()
