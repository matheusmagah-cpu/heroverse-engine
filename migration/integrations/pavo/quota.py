"""Free agnes-image quota guard (E124): a daily cap before any call, and a stop after failed read-backs.

On 2026-10-27 Pavo's free image quota ran out after ~180 stills in one day. pavo_quote_image kept quoting an exact 0
(the price endpoint does not see the free-generation quota) and pavo_image_job read only status "failed" with no
reason, so 31 submissions of genesis-09 run 2026102705 were spent on nothing (the owner's app showed "the free model
quota has been used up ... try again in 3 hours"; nothing was charged). This guard keeps that from repeating:

- PAVO_DAILY_CAP: at most DAILY_CAP images a UTC day (env PAVO_IMAGE_DAILY_CAP, or the ledger's `daily_cap`), counted
  in the ledger for every submission that created a conversation; refused before the quote, so nothing is sent.
- PAVO_FREE_QUOTA_SUSPECTED: FAILED_STREAK read-backs in a row that end "failed" with no image (each job counted
  once) suspend generation for COOL_DOWN from `suspended_at`. After it exactly one probe may go; every other
  submission is refused until that probe reads back: a failed probe suspends again at once, a completed one lifts the
  suspension. Only a job submitted after `suspended_at` (the probe, or a later one) may lift it; an older job that
  completes late does not.
- PAVO_LEDGER_UNREADABLE: a ledger that exists but cannot be read or holds malformed fields (merge-conflict markers,
  a naive or garbage time, a non-integer count) fails closed: nothing is sent until it is fixed by hand and
  committed. A missing ledger is a fresh one.

The ledger (LEDGER, env PAVO_IMAGE_LEDGER) is plain JSON: {version, daily_cap?, days: {YYYY-MM-DD: {generated, note?}},
failed_streak, failed_jobs, jobs: {conversation_id: submitted_at}, suspended_at, suspended_until, probe}. It holds
counts, times and conversation ids only, never a credential or URL. It is written atomically through a unique
temporary file (tempfile.mkstemp) in its own folder.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import tempfile

from client import PavoError

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / "migration" / "evidence" / "pavo" / "image-ledger.json"
DAILY_CAP = 120
FAILED_STREAK = 2
COOL_DOWN = timedelta(hours=3)
KEEP_FAILED = 50
KEEP_JOBS = 200
DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _unreadable(why):
    return PavoError("PAVO_LEDGER_UNREADABLE (%s; fix migration/evidence/pavo/image-ledger.json by PR)" % why)


def _when(value, field):
    """An aware ISO time, or None; anything else is unreadable (a naive time is refused, never assumed UTC)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise _unreadable("%s is not a time" % field)
    try:
        t = datetime.fromisoformat(value)
    except ValueError:
        raise _unreadable("%s is not an ISO time" % field) from None
    if t.tzinfo is None or t.utcoffset() is None:
        raise _unreadable("%s has no time zone" % field)
    return t


class QuotaGuard:
    def __init__(self, path=None, cap=None, now=None):
        self.path = Path(path or os.environ.get("PAVO_IMAGE_LEDGER") or LEDGER)
        self._cap = cap
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _load(self):
        """The ledger, checked field by field; a missing file is a fresh ledger, anything malformed fails closed."""
        if not self.path.exists():
            data = {}
        else:
            try:
                data = json.loads(self.path.read_text())
            except (OSError, ValueError, UnicodeDecodeError):
                raise _unreadable("not JSON") from None
            if not isinstance(data, dict):
                raise _unreadable("not a JSON object")
        data.setdefault("version", "pavo-image-ledger-v1")
        data.setdefault("days", {})
        data.setdefault("failed_jobs", [])
        data.setdefault("failed_streak", 0)
        data.setdefault("jobs", {})
        data.setdefault("suspended_at", None)
        data.setdefault("suspended_until", None)
        data.setdefault("probe", None)
        days = data["days"]
        if not isinstance(days, dict):
            raise _unreadable("days is not an object")
        for day, row in days.items():
            if not DAY.fullmatch(str(day)) or not isinstance(row, dict) or type(row.get("generated", 0)) is not int \
                    or row.get("generated", 0) < 0:
                raise _unreadable("days.%s is not {generated: a count}" % day)
        if type(data["failed_streak"]) is not int or data["failed_streak"] < 0:
            raise _unreadable("failed_streak is not a count")
        if not isinstance(data["failed_jobs"], list) or not all(isinstance(j, str) for j in data["failed_jobs"]):
            raise _unreadable("failed_jobs is not a list of ids")
        if not isinstance(data["jobs"], dict):
            raise _unreadable("jobs is not an object")
        for job, at in data["jobs"].items():
            _when(at, "jobs.%s" % job)
        _when(data["suspended_at"], "suspended_at")
        _when(data["suspended_until"], "suspended_until")
        if data["suspended_until"] is not None and data["suspended_at"] is None:
            raise _unreadable("suspended_until without suspended_at")
        probe = data["probe"]
        if probe is not None and (not isinstance(probe, dict) or not isinstance(probe.get("conversation_id"), str)):
            raise _unreadable("probe is not {conversation_id}")
        cap = data.get("daily_cap")
        if cap is not None and (type(cap) is not int or cap < 0):
            raise _unreadable("daily_cap is not a count")
        return data

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="." + self.path.name + ".", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(json.dumps(data, indent=1, sort_keys=True) + "\n")
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def cap(self, data=None):
        if self._cap is not None:
            return int(self._cap)
        env = os.environ.get("PAVO_IMAGE_DAILY_CAP", "").strip()
        if env:
            try:
                value = int(env)
            except ValueError:
                value = None   # malformed: ignored, the safe default stays
            if value is not None and value >= 0:
                return value
        given = (data or {}).get("daily_cap")
        return given if type(given) is int and given >= 0 else DAILY_CAP

    def _day(self):
        return self._now().astimezone(timezone.utc).strftime("%Y-%m-%d")

    def before_generate(self):
        """Raise before any request when the ledger is unreadable, a quota stop is suspected (the cool-down runs, or
        its one probe has not read back yet) or the day's cap is reached."""
        data = self._load()
        until = _when(data["suspended_until"], "suspended_until")
        if until is not None:
            if self._now() < until:
                raise PavoError("PAVO_FREE_QUOTA_SUSPECTED until=%s failed_streak=%d"
                                % (data["suspended_until"], data["failed_streak"]))
            if data["probe"] is not None:
                raise PavoError("PAVO_FREE_QUOTA_SUSPECTED probe=%s (read it back with pavo_image_job first)"
                                % data["probe"]["conversation_id"])
        done = (data["days"].get(self._day()) or {}).get("generated", 0)
        cap = self.cap(data)
        if done >= cap:
            raise PavoError("PAVO_DAILY_CAP generated=%d cap=%d day=%s" % (done, cap, self._day()))

    def submitted(self, conversation_id):
        """Count one submission that created a conversation (whatever its acknowledgement said); after a cool-down it
        is the one probe."""
        data = self._load()
        now = self._now()
        day = data["days"].setdefault(self._day(), {"generated": 0})
        day["generated"] = int(day.get("generated", 0)) + 1
        data["jobs"][conversation_id] = now.isoformat()
        if len(data["jobs"]) > KEEP_JOBS:
            data["jobs"] = dict(sorted(data["jobs"].items(), key=lambda kv: kv[1])[-KEEP_JOBS:])
        until = _when(data["suspended_until"], "suspended_until")
        if until is not None and now >= until and data["probe"] is None:
            data["probe"] = {"conversation_id": conversation_id, "submitted_at": now.isoformat()}
        self._save(data)

    def read_back(self, conversation_id, status, images):
        """A job read back: completed with images lifts a suspension only when the job was submitted after it began;
        failed with none counts toward a stop (and a failed probe suspends again at once)."""
        if status == "completed" and images:
            data = self._load()
            at = _when(data["suspended_at"], "suspended_at")
            if at is not None:
                sent = _when(data["jobs"].get(conversation_id), "jobs.%s" % conversation_id)
                if sent is None or sent < at:
                    return   # an older job finishing late says nothing about the quota now
                data.update(suspended_at=None, suspended_until=None, probe=None)
            data["failed_streak"] = 0
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
            now = self._now()
            data.update(suspended_at=now.isoformat(), suspended_until=(now + COOL_DOWN).isoformat(), probe=None)
        self._save(data)
