#!/usr/bin/env python3
"""Market evidence from vidIQ (strategy/VIDIQ.md): a short opinion per pilot, a ledger of every vidIQ call, and the
informative summary the pre-publication package carries. It never takes part in the PASS/FAIL/UNKNOWN decision.

- Opinion: production/<pilot>/market/vidiq.json (REQUIRED fields below). Missing -> UNKNOWN; malformed -> INVALID;
  data older than STALE_DAYS at gate time -> STALE. Never invented, never a reason to relax a criterion.
- Ledger: evidence/vidiq/ledger.json, one row per call (date, tool, credits, purpose, saved_to). The owner's cadence:
  at most RESEARCH_PER_DAY research call a day; a research needing more calls is announced to the owner first and
  recorded with "approved_by_owner".
usage: market_evidence.py check OPINION_JSON | budget LEDGER_JSON [YYYY-MM-DD]
"""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

STALE_DAYS = 14
RESEARCH_PER_DAY = 1
REQUIRED = ("pilot_id", "generated_at", "source", "calls", "data_as_of", "opportunity", "comparables", "evidence_for",
            "evidence_against", "limitations", "recommendation", "relation_to_content", "validation_status")
NOT_CLAIMED = "market evidence only: not technical quality, not a performance forecast, not a guarantee of views, revenue or monetization"


def summary(path, now=None):
    """Informative block for gate.json; never a verdict."""
    now = now or datetime.now(timezone.utc)
    p = Path(path)
    if not p.exists():
        return {"status": "UNKNOWN", "detail": "no vidIQ market opinion for this pilot", "not_claimed": NOT_CLAIMED}
    try:
        o = json.loads(p.read_text())
    except ValueError:
        return {"status": "INVALID", "detail": "opinion is not valid JSON", "not_claimed": NOT_CLAIMED}
    missing = [k for k in REQUIRED if k not in o]
    if missing:
        return {"status": "INVALID", "detail": f"missing fields: {', '.join(missing)}", "not_claimed": NOT_CLAIMED}
    age = (now - datetime.fromisoformat(o["data_as_of"].replace("Z", "+00:00"))).days
    return {"status": "STALE" if age > STALE_DAYS else "KNOWN", "data_age_days": age, "opportunity": o["opportunity"],
            "recommendation": o["recommendation"], "validation_status": o["validation_status"],
            "credits": sum(c.get("credits", 0) for c in o["calls"]), "file": str(p), "not_claimed": NOT_CLAIMED}


def budget(ledger, day):
    rows = [r for r in ledger.get("calls", []) if r["date"] == day and r.get("kind") == "research"]
    approved = [r for r in rows if r.get("approved_by_owner")]
    used = len(rows) - len(approved)
    return {"date": day, "research_calls_today": used, "allowed": RESEARCH_PER_DAY,
            "may_call": used < RESEARCH_PER_DAY, "owner_approved_extra": len(approved)}


if __name__ == "__main__":
    if sys.argv[1] == "check":
        print(json.dumps(summary(sys.argv[2])))
    elif sys.argv[1] == "budget":
        led = json.loads(Path(sys.argv[2]).read_text()) if Path(sys.argv[2]).exists() else {}
        print(json.dumps(budget(led, sys.argv[3] if len(sys.argv) > 3 else date.today().isoformat())))
