#!/usr/bin/env python3
"""Autopilot Gemini budget (AUTOPILOT.md 2.7, phase A1-1): every Gemini call is counted against the free-tier numbers
read from AI Studio on 2026-10-31 (AUTOPILOT.md 1.1) before it is made.

Rules (pure functions; the ledger is a JSON file the caller commits):
- An unknown model has no known free limit: refused (never assume a quota).
- A call is refused when it would pass 80% of the model's RPD, RPM or TPM (counted per Pacific day / last 60 s).
- Any 429 / RESOURCE_EXHAUSTED stops every Gemini call until the next midnight Pacific (RPD reset). A 429 is never a
  score and never retried that day.
- A call is reserved (counted) BEFORE submission. If the outcome is unknown (timeout, connection drop, no status)
  it stays UNCERTAIN: still counted, and never retried; the caller reconciles by its saved ID instead.
- Only a definitive transient provider error (500/503 with a parsed error body) may be retried, once, on the same
  input and model (the existing retry_transient_once rule); the retry is itself a counted call.

CLI: autopilot_budget.py LEDGER check MODEL [TOKENS] | reserve MODEL PURPOSE [TOKENS] | settle CALL_ID STATUS [TOKENS]
     | status. check/reserve exit 3 on refusal (stop), 0 on allow.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

SCHEMA = 'heroverse-autopilot-budget-v1'
PACIFIC = ZoneInfo('America/Los_Angeles')
SAFETY = 0.8
# AUTOPILOT.md 1.1 (owner's AI Studio screen, 2026-10-31, free tier). Unknown models are refused.
LIMITS = {
    'gemini-3.8-flash': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemini-3.6-flash': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemini-3-flash': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemini-2.5-flash': {'rpm': 5, 'tpm': 250_000, 'rpd': 20},
    'gemini-3.5-flash-lite': {'rpm': 15, 'tpm': 250_000, 'rpd': 500},
    'gemini-3.1-flash-lite': {'rpm': 15, 'tpm': 250_000, 'rpd': 500},
}
UNCERTAIN = 'UNCERTAIN'
PENDING = 'PENDING'


def empty():
    return {'schema': SCHEMA, 'limits_source': 'migration/ops/AUTOPILOT.md 1.1 (AI Studio, 2026-10-31)',
            'calls': [], 'stops': []}


def pacific_day(at):
    return at.astimezone(PACIFIC).date().isoformat()


def _at(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _iso(at):
    return at.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def stopped(ledger, now):
    """The 429 stop of today (Pacific), or None."""
    day = pacific_day(now)
    return next((s for s in ledger.get('stops', []) if s.get('pacific_day') == day), None)


def decide(ledger, model, now, tokens=0):
    """('ALLOW', None) or ('REFUSE', reason). Counts every reserved call, including uncertain ones."""
    if model not in LIMITS:
        return 'REFUSE', 'MODEL_LIMIT_UNKNOWN'
    stop = stopped(ledger, now)
    if stop:
        return 'REFUSE', 'QUOTA_STOP_TODAY:' + stop.get('reason', '429')
    lim = LIMITS[model]
    day = pacific_day(now)
    mine = [c for c in ledger.get('calls', []) if c.get('model') == model]
    today = [c for c in mine if c.get('pacific_day') == day]
    if len(today) + 1 > int(lim['rpd'] * SAFETY):
        return 'REFUSE', 'RPD_80'
    minute = [c for c in mine if now - _at(c['at']) < timedelta(seconds=60)]
    if len(minute) + 1 > int(lim['rpm'] * SAFETY):
        return 'REFUSE', 'RPM_80'
    used = sum(int(c.get('tokens') or c.get('tokens_estimate') or 0) for c in minute)
    if used + int(tokens) > lim['tpm'] * SAFETY:
        return 'REFUSE', 'TPM_80'
    return 'ALLOW', None


def reserve(ledger, model, purpose, now, tokens=0):
    """Count the call before it is made. Returns the call id, or raises RuntimeError(reason) on refusal."""
    verdict, reason = decide(ledger, model, now, tokens)
    if verdict != 'ALLOW':
        raise RuntimeError(reason)
    call_id = 'c%04d' % (len(ledger.setdefault('calls', [])) + 1)
    ledger['calls'].append({'id': call_id, 'model': model, 'purpose': str(purpose)[:80], 'at': _iso(now),
                            'pacific_day': pacific_day(now), 'tokens_estimate': int(tokens), 'status': PENDING})
    return call_id


def _quota_error(status):
    return str(status) in ('429', 'RESOURCE_EXHAUSTED')


def settle(ledger, call_id, status, now, tokens=None):
    """Record the outcome. status: an HTTP code, 'RESOURCE_EXHAUSTED', or None/'' for an unknown outcome."""
    call = next(c for c in ledger['calls'] if c['id'] == call_id)
    if call['status'] != PENDING:
        raise RuntimeError('ALREADY_SETTLED')
    call['status'] = UNCERTAIN if status in (None, '') else str(status)
    if tokens is not None:
        call['tokens'] = int(tokens)
    if _quota_error(call['status']):
        ledger.setdefault('stops', []).append({'pacific_day': pacific_day(now), 'at': _iso(now),
                                               'reason': call['status'], 'model': call['model']})
    return call


def retry_allowed(ledger, call_id):
    """Only a definitive transient provider error, once. Uncertain, pending, quota and quality outcomes: never."""
    call = next(c for c in ledger['calls'] if c['id'] == call_id)
    if call['status'] not in ('500', '503') or call.get('retry_of'):
        return False
    return not any(c.get('retry_of') == call_id for c in ledger['calls'])


def status(ledger, now):
    day = pacific_day(now)
    out = {'pacific_day': day, 'stopped': stopped(ledger, now), 'models': {}}
    for model, lim in LIMITS.items():
        n = sum(1 for c in ledger.get('calls', []) if c.get('model') == model and c.get('pacific_day') == day)
        if n:
            out['models'][model] = {'calls_today': n, 'refuse_at': int(lim['rpd'] * SAFETY), 'rpd': lim['rpd']}
    return out


def load(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else empty()


def save(path, ledger):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(ledger, indent=1) + '\n')


def main(argv, now=None):
    now = now or datetime.now(timezone.utc)
    path, cmd, *rest = argv
    ledger = load(path)
    if cmd == 'check':
        verdict, reason = decide(ledger, rest[0], now, int(rest[1]) if len(rest) > 1 else 0)
        print(json.dumps({'verdict': verdict, 'reason': reason}))
        return 0 if verdict == 'ALLOW' else 3
    if cmd == 'reserve':
        try:
            call_id = reserve(ledger, rest[0], rest[1], now, int(rest[2]) if len(rest) > 2 else 0)
        except RuntimeError as e:
            print(json.dumps({'verdict': 'REFUSE', 'reason': str(e)}))
            return 3
        save(path, ledger)
        print(json.dumps({'verdict': 'ALLOW', 'call_id': call_id}))
        return 0
    if cmd == 'settle':
        call = settle(ledger, rest[0], rest[1] or None, now, int(rest[2]) if len(rest) > 2 else None)
        save(path, ledger)
        print(json.dumps({'call_id': call['id'], 'status': call['status']}))
        return 0
    if cmd == 'status':
        print(json.dumps(status(ledger, now), indent=1))
        return 0
    raise SystemExit('USAGE')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
