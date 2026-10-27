"""Free agnes-image quota guard (E124): a daily cap before any call, and a stop after failed read-backs.

On 2026-10-27 Pavo's free image quota ran out after ~180 stills in one day. pavo_quote_image kept quoting an exact 0
(the price endpoint does not see the free-generation quota) and pavo_image_job read only status "failed" with no
reason, so 31 submissions of genesis-09 run 2026102705 were spent on nothing (the owner's app showed "the free model
quota has been used up ... try again in 3 hours"; nothing was charged). This guard keeps that from repeating:

- PAVO_DAILY_CAP: at most DAILY_CAP images a UTC day (env PAVO_IMAGE_DAILY_CAP, or the ledger's `daily_cap`), counted
  in the ledger for every submission that created a conversation; refused before the quote, so nothing is sent.
- PAVO_FREE_QUOTA_SUSPECTED: FAILED_STREAK read-backs in a row that end "failed" with no image (each job counted
  once) suspend generation for COOL_DOWN. After it one probe may go; another failed read-back suspends again at once,
  a read-back that completes lifts the suspension.

The ledger (LEDGER, env PAVO_IMAGE_LEDGER) is plain JSON: {version, daily_cap?, days: {YYYY-MM-DD: {generated}},
failed_streak, failed_jobs, suspended_until}. It holds counts and conversation ids only, never a credential or URL.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from client import PavoError

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / "migration" / "evidence" / "pavo" / "image-ledger.json"
DAILY_CAP = 120
FAILED_STREAK = 2
COOL_DOWN = timedelta(hours=3)
KEEP_FAILED = 50


class QuotaGuard:
    def __init__(self, path=None, cap=None, now=None):
        self.path = Path(path or os.environ.get("PAVO_IMAGE_LEDGER") or LEDGER)
        self._cap = cap
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _load(self):
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("version", "pavo-image-ledger-v1")
        if not isinstance(data.get("days"), dict):
            data["days"] = {}
        if not isinstance(data.get("failed_jobs"), list):
            data["failed_jobs"] = []
        if type(data.get("failed_streak")) is not int:
            data["failed_streak"] = 0
        return data

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
        tmp.replace(self.path)

    def cap(self, data=None):
        if self._cap is not None:
            return int(self._cap)
        env = os.environ.get("PAVO_IMAGE_DAILY_CAP", "")
        if env.isdigit():
            return int(env)
        given = (data or {}).get("daily_cap")
        return given if type(given) is int and given >= 0 else DAILY_CAP

    def _day(self):
        return self._now().astimezone(timezone.utc).strftime("%Y-%m-%d")

    def before_generate(self):
        """Raise before any request when the day's cap is reached or a quota stop is suspected."""
        data = self._load()
        until = data.get("suspended_until")
        if isinstance(until, str):
            try:
                if self._now() < datetime.fromisoformat(until):
                    raise PavoError("PAVO_FREE_QUOTA_SUSPECTED until=%s failed_streak=%d" % (until, data["failed_streak"]))
            except ValueError:
                pass
        done = (data["days"].get(self._day()) or {}).get("generated", 0)
        cap = self.cap(data)
        if done >= cap:
            raise PavoError("PAVO_DAILY_CAP generated=%d cap=%d day=%s" % (done, cap, self._day()))

    def submitted(self, conversation_id):
        """Count one submission that created a conversation (whatever its acknowledgement said)."""
        data = self._load()
        day = data["days"].setdefault(self._day(), {"generated": 0})
        day["generated"] = int(day.get("generated", 0)) + 1
        self._save(data)

    def read_back(self, conversation_id, status, images):
        """A job read back: completed with images lifts any suspension; failed with none counts toward a stop."""
        if status == "completed" and images:
            data = self._load()
            if data["failed_streak"] or data.get("suspended_until"):
                data.update(failed_streak=0, suspended_until=None)
                self._save(data)
            return
        if status != "failed" or images:
            return
        data = self._load()
        if conversation_id in data["failed_jobs"]:
            return
        data["failed_jobs"] = (data["failed_jobs"] + [conversation_id])[-KEEP_FAILED:]
        data["failed_streak"] += 1
        if data["failed_streak"] >= FAILED_STREAK:
            data["suspended_until"] = (self._now() + COOL_DOWN).isoformat()
        self._save(data)
