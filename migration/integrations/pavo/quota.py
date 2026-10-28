"""Pavo's free-model quota guard (E124, E128): one budget for every Pavo generation, image and video, MCP and Actions.

E128 (2026-10-27 ~22:40 UTC): the quota E124 guards is not the image model's alone. A Flash video job makes an Agnes
Image 2.5 Flash still inside its conversation (the owner's app showed one, "Painterly cinematic image of the Garden of
Eden at dawn ... wide 16:9", made by shot-probe run 40592173923), so the video path spends the same free quota; E124
counted only MCP image calls. That run read back 3 clips, then 24 submissions in a row `failed` with no video, and
nothing stopped it. Now:
- every generation is counted in units: an image IMAGE_UNITS, a video VIDEO_UNITS (its internal still(s), counted
  conservatively); the MCP's pavo_generate_video and pavo_job feed the same guard as the image tools;
- Actions (shot-probe.yml) cannot write this ledger: their usage is read from the probe records the record job pushes
  to claude/shot-probe-<episode>-<run> (record_usage: each generation of the record counts VIDEO_UNITS; when its last
  FAILED_STREAK or more generations, in submission order, came back with no video, that is a quota stop for
  COOL_DOWN). The MCP guard reads them from the local remote-tracking refs (git_actions_usage; fetch them first), the
  dispatch guard from the API, and the run itself takes a run-local ledger seeded with the day's units
  (episode_build.py probe, PAVO_BUDGET_USED), so its own failed read-backs stop it after FAILED_STREAK;
- check_batch refuses a planned batch whose units do not fit what is left today (PAVO_BUDGET_SHORT), so a batch never
  starts if it cannot finish.
Pavo exposes no remaining free quota: /v3/subscription/credits-balance answers the plan and credits only
(total_balance, subscription_credits, daily_free_credits; read 2026-10-27 after the stop, no quota field), and the
price quote keeps answering 0. These counts are the only gate.

E124 (the image path):

On 2026-10-27 Pavo's free image quota ran out after ~180 stills in one day. pavo_quote_image kept quoting an exact 0
(the price endpoint does not see the free-generation quota) and pavo_image_job read only status "failed" with no
reason, so 31 submissions of genesis-09 run 2026102705 were spent on nothing (the owner's app showed "the free model
quota has been used up ... try again in 3 hours"; nothing was charged). This guard keeps that from repeating:

- PAVO_DAILY_CAP: at most DAILY_CAP units a UTC day (E128: an image 1, a video 2; env PAVO_IMAGE_DAILY_CAP, or the
  ledger's `daily_cap`), counted in the ledger for every submission that created a conversation; refused before the
  quote, so nothing is sent.
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
import subprocess
import tempfile

from client import PavoError

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / "migration" / "evidence" / "pavo" / "image-ledger.json"
# E138 (28/10, measured by the long agent): Pavo's free quota is a rolling window, not a UTC day. After a stop about
# 35-50 jobs come back ~3 h later, and sustained throughput is ~9-12 jobs an hour (27/10: ~180 jobs in 15.7 h); a
# still and a video each count about one job. A fixed total a UTC day (E128's 120 units) blocked work while the quota
# was live and let it run while it was spent. The stop signal is the read-back (FAILED_STREAK, COOL_DOWN, one probe,
# MAX_UNREAD); DAILY_CAP is now only the largest batch one run may plan (about one window), never a day's total.
DAILY_CAP = 120
# E138: the owner's split of the rolling quota: the Shorts take at most this many jobs a UTC day, the long the rest
SHORTS_DAILY_JOBS = 25
FAILED_STREAK = 2
# E136 (28/10): 11 stills were submitted back to back before any was read back; the quota had run out and 10 came back
# `failed`. FAILED_STREAK can only stop a fan-out when read-backs come between submissions, so a new submission waits
# while this many of today's jobs are still unread (PAVO_UNREAD_JOBS): a quota stop costs at most this many.
MAX_UNREAD = 2
COOL_DOWN = timedelta(hours=3)
KEEP_FAILED = 50
KEEP_JOBS = 200
DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
# E128: what one generation spends of the free-model quota. A Flash video makes at least one Agnes still inside its
# conversation; counted as two, so a cap set in images is never overrun by videos
IMAGE_UNITS = 1
VIDEO_UNITS = 2
PROBE_BRANCH = re.compile(r"^claude/shot-probe-([a-z0-9]+(?:-[a-z0-9]+)*)-([0-9]{6,20})$")
NO_ACTIONS = {"units": 0, "failed_tail": 0, "last_at": None}


def probe_record_path(branch):
    """The record shot-probe.yml's record job commits on BRANCH, or None for another branch."""
    m = PROBE_BRANCH.fullmatch(branch)
    return "migration/evidence/shots/%s/%s.json" % (m.group(1), m.group(2)) if m else None


def record_usage(record):
    """(units, failed tail) of one shot-probe record: every generation it lists (each created a conversation) counts
    VIDEO_UNITS; the failed tail is how many of its last generations, in submission order (conversation ids grow with
    time), came back with no video."""
    gens = []
    for entry in (record.get("shots") or {}).values():
        for clip in entry.get("clips") or []:
            gens += [g for g in clip.get("generations") or [] if isinstance(g, dict)]

    def order(g):
        cid = str(g.get("conversation_id") or "")
        return int(cid) if cid.isdigit() else 0
    gens.sort(key=order)
    tail = 0
    for g in reversed(gens):
        if "NO_VIDEO" not in (g.get("flags") or []):
            break
        tail += 1
    return len(gens) * VIDEO_UNITS, tail


def wanted(at, day, now):
    """A record counts when committed on DAY (its units) or less than COOL_DOWN before NOW (its failed tail: a stop
    shortly before 00:00 UTC still holds after it; review of #475)."""
    recent = now is not None and now - COOL_DOWN <= at <= now
    return at.astimezone(timezone.utc).strftime("%Y-%m-%d") == day or recent


def combine(records, day=None):
    """records: [(committed_at aware datetime, record)] -> {units (of the records committed on DAY, all when None),
    failed_tail and last_at of the latest record WITH generations}. A record with none (an adopt_run, a run refused
    before generating) says nothing about the quota, so it never hides an earlier run's stop (review of #475)."""
    if not records:
        return dict(NO_ACTIONS)
    units = sum(record_usage(r)[0] for at, r in records
                if day is None or at.astimezone(timezone.utc).strftime("%Y-%m-%d") == day)
    generating = [(at, r) for at, r in records if record_usage(r)[0]]
    if not generating:
        return {"units": units, "failed_tail": 0, "last_at": None}
    at, last = max(generating, key=lambda x: x[0])
    return {"units": units, "failed_tail": record_usage(last)[1], "last_at": at.isoformat()}


def git_actions_usage(day, repo=None, run=subprocess.run, now=None):
    """Today's shot-probe usage from the local remote-tracking refs (origin/claude/shot-probe-*): the records committed
    on DAY (UTC) for the units, and those of the last COOL_DOWN for the failed tail. Fetch them before an MCP
    generation session; a git that cannot answer fails closed."""
    now = now or datetime.now(timezone.utc)
    repo = str(repo or REPO)

    def git(*args):
        try:
            return run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            raise PavoError("PAVO_BUDGET_UNREADABLE (git did not answer)") from None
    out = git("for-each-ref", "--format=%(refname:lstrip=3) %(committerdate:iso-strict)",
              "refs/remotes/origin/claude/")
    if out.returncode != 0:
        raise PavoError("PAVO_BUDGET_UNREADABLE (git for-each-ref failed)")
    records = []
    for line in out.stdout.splitlines():
        branch, _, when = line.strip().partition(" ")
        path = probe_record_path(branch)
        if not path:
            continue
        try:
            at = datetime.fromisoformat(when).astimezone(timezone.utc)
        except ValueError:
            raise PavoError("PAVO_BUDGET_UNREADABLE (%s has no commit time)" % branch) from None
        if not wanted(at, day, now):
            continue
        shown = git("show", "origin/%s:%s" % (branch, path))
        if shown.returncode != 0:
            continue   # a branch without its record: the probe job left none (NO_PROBE_RECORD)
        try:
            records.append((at, json.loads(shown.stdout)))
        except ValueError:
            raise PavoError("PAVO_BUDGET_UNREADABLE (%s: its record is not JSON)" % branch) from None
    return combine(records, day)


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
    def __init__(self, path=None, cap=None, now=None, actions=None):
        """actions: day -> {units, failed_tail, last_at} of the Actions runs (git_actions_usage, or the dispatch
        guard's API read); None when this ledger already holds them (shot-probe's run-local ledger)."""
        self.path = Path(path or os.environ.get("PAVO_IMAGE_LEDGER") or LEDGER)
        self._cap = cap
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._actions = actions

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
        data.setdefault("unread", [])
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
        if not isinstance(data["unread"], list) or not all(isinstance(j, str) for j in data["unread"]):
            raise _unreadable("unread is not a list of ids")
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

    def _usage(self, data):
        """(units used today: this ledger + the Actions records, the Actions part)."""
        actions = self._actions(self._day()) if self._actions else NO_ACTIONS
        done = (data["days"].get(self._day()) or {}).get("generated", 0)
        return done + int(actions.get("units") or 0), actions

    def _stopped(self, data, actions):
        """Raise while a quota stop is suspected: this ledger's suspension (or its one probe not read back), or an
        Actions run that ended with FAILED_STREAK failed read-backs less than COOL_DOWN ago."""
        until = _when(data["suspended_until"], "suspended_until")
        if until is not None:
            if self._now() < until:
                raise PavoError("PAVO_FREE_QUOTA_SUSPECTED until=%s failed_streak=%d"
                                % (data["suspended_until"], data["failed_streak"]))
            if data["probe"] is not None:
                raise PavoError("PAVO_FREE_QUOTA_SUSPECTED probe=%s (read it back with pavo_job / pavo_image_job "
                                "first)" % data["probe"]["conversation_id"])
        last = _when(actions.get("last_at"), "actions.last_at")
        if (actions.get("failed_tail") or 0) >= FAILED_STREAK and last is not None and self._now() < last + COOL_DOWN:
            raise PavoError("PAVO_FREE_QUOTA_SUSPECTED until=%s (a shot-probe run ended with %d failed read-backs)"
                            % ((last + COOL_DOWN).isoformat(), actions["failed_tail"]))

    def before_generate(self, units=IMAGE_UNITS):
        """Raise before any request when the ledger is unreadable, a quota stop is suspected (the cool-down runs, or
        its one probe has not read back yet) or MAX_UNREAD of today's jobs are not read back (E136). E138: no fixed
        daily total; only an owner's explicit PAVO_IMAGE_DAILY_CAP still caps the day (PAVO_DAILY_CAP)."""
        data = self._load()
        used, actions = self._usage(data)
        self._stopped(data, actions)
        cap = self._owner_cap()
        if cap is not None and used + units > cap:
            raise PavoError("PAVO_DAILY_CAP generated=%d units=%d cap=%d day=%s" % (used, units, cap, self._day()))
        waiting = self._unread(data)
        if len(waiting) >= MAX_UNREAD:
            raise PavoError("PAVO_UNREAD_JOBS %s (read them back with pavo_job / pavo_image_job before another "
                            "submission; E136)" % ",".join(waiting))

    def _unread(self, data):
        """E136: today's submissions not yet read back to an end (completed with media, or failed)."""
        day = self._day()
        out = []
        for job in data["unread"]:
            at = _when(data["jobs"].get(job), "jobs.%s" % job)
            if at is not None and at.astimezone(timezone.utc).strftime("%Y-%m-%d") == day:
                out.append(job)
        return out

    def _owner_cap(self):
        """E138: a day's total only when the owner sets PAVO_IMAGE_DAILY_CAP explicitly; None otherwise."""
        env = os.environ.get("PAVO_IMAGE_DAILY_CAP", "").strip()
        try:
            value = int(env) if env else None
        except ValueError:
            return None
        return value if value is not None and value >= 0 else None

    def check_batch(self, units):
        """A planned batch (its worst-case units) before it starts. E138: refused while a quota stop is suspected, and
        (PAVO_BUDGET_SHORT) when the batch alone is larger than one rolling window (cap()) or passes an owner's
        explicit daily cap; the units already used today no longer refuse it. Returns {used, planned, cap,
        remaining}: remaining is the room left in one window after this batch."""
        data = self._load()
        used, actions = self._usage(data)
        self._stopped(data, actions)
        cap = self.cap(data)
        if units > cap:
            raise PavoError("PAVO_BUDGET_SHORT planned=%d window=%d (split the batch: one run plans at most one "
                            "rolling window, E138)" % (units, cap))
        owner = self._owner_cap()
        if owner is not None and used + units > owner:
            raise PavoError("PAVO_BUDGET_SHORT planned=%d used=%d cap=%d day=%s (the owner's daily cap)"
                            % (units, used, owner, self._day()))
        return {"used": used, "planned": units, "cap": cap, "remaining": cap - units}

    def submitted(self, conversation_id, units=IMAGE_UNITS):
        """Count one submission that created a conversation (whatever its acknowledgement said) as its units; after a
        cool-down it is the one probe."""
        data = self._load()
        now = self._now()
        day = data["days"].setdefault(self._day(), {"generated": 0})
        day["generated"] = int(day.get("generated", 0)) + units
        data["jobs"][conversation_id] = now.isoformat()
        if conversation_id not in data["unread"]:
            data["unread"] = (data["unread"] + [conversation_id])[-KEEP_JOBS:]
        if len(data["jobs"]) > KEEP_JOBS:
            data["jobs"] = dict(sorted(data["jobs"].items(), key=lambda kv: kv[1])[-KEEP_JOBS:])
        until = _when(data["suspended_until"], "suspended_until")
        if until is not None and now >= until and data["probe"] is None:
            data["probe"] = {"conversation_id": conversation_id, "submitted_at": now.isoformat()}
        self._save(data)

    def read_back(self, conversation_id, status, images):
        """A job read back (a still's images or a video's clips): completed with media lifts a suspension only when the job was submitted after it began;
        failed with none counts toward a stop (and a failed probe suspends again at once)."""
        if status == "completed" and images:
            data = self._load()
            data["unread"] = [j for j in data["unread"] if j != conversation_id]
            at = _when(data["suspended_at"], "suspended_at")
            if at is not None:
                sent = _when(data["jobs"].get(conversation_id), "jobs.%s" % conversation_id)
                if sent is None or sent < at:
                    self._save(data)   # read (E136), but an older job finishing late says nothing about the quota now
                    return
                data.update(suspended_at=None, suspended_until=None, probe=None)
            data["failed_streak"] = 0
            self._save(data)
            return
        if status != "failed" or images:
            return
        data = self._load()
        data["unread"] = [j for j in data["unread"] if j != conversation_id]
        if conversation_id in data["failed_jobs"]:
            self._save(data)
            return
        data["failed_jobs"] = (data["failed_jobs"] + [conversation_id])[-KEEP_FAILED:]
        data["failed_streak"] += 1
        if data["failed_streak"] >= FAILED_STREAK:
            now = self._now()
            data.update(suspended_at=now.isoformat(), suspended_until=(now + COOL_DOWN).isoformat(), probe=None)
        self._save(data)
