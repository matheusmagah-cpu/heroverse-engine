"""The TikTok runner's rules, without a browser (tested in the repository on every PR).

Ledger (ledger.json next to runner.py): {"actions": {comment_id: {"video_id", "state", "at", "reply_cid", "liked"}}}
state ATTEMPTING is written before the first click, so a run that dies mid-action leaves the comment blocked
(UNCERTAIN), never retried by itself: nothing is ever done twice. REPLIED and LIKED are recorded after TikTok's own
response confirms them.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import re

HANDLE = "heroverse.official"
DAY_CAP = 20                 # replies (each with its like) a day, owner
RUN_CAP = 3                  # a run; the main clock calls every 4 h, so the day's 20 spread over the day
PAUSE = (45, 240)            # seconds between two comments
SHORT_PAUSE = (4, 15)        # seconds between the steps on one comment (like, open reply, type, send)
MIN_GAP = timedelta(minutes=20)   # since the last action of any earlier run
LIMIT = 150                  # TikTok's comment length limit
URL = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|net|org|io|ly|be|me|tv|app)\b", re.I)
VIDEO_ID = re.compile(r"^\d{15,22}$")
COMMENT_ID = re.compile(r"^\d{15,22}$")


def now_utc():
    return datetime.now(timezone.utc)


def iso(t):
    return t.isoformat(timespec="seconds")


def read_json(path, default):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)   # E133: a fresh install has no out/ yet
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def empty_ledger():
    return {"version": "tiktok-local-ledger-v1", "actions": {}}


def actions_today(ledger, now):
    return sum(1 for a in ledger.get("actions", {}).values()
               if a.get("state") in ("REPLIED", "ATTEMPTING", "UNCERTAIN")
               and datetime.fromisoformat(a["at"]).date() == now.date())


def last_action(ledger):
    times = [datetime.fromisoformat(a["at"]) for a in ledger.get("actions", {}).values()
             if a.get("at") and a.get("state") != "SKIPPED"]
    return max(times) if times else None


def reply_problems(item, own_videos, policy=None):
    """Why one decision of the input file may not be acted on ([] = it may). `policy` is reply_policy.problems (the
    repository's gate, deployed next to the runner); the runner's own checks stay even without it."""
    out = []
    cid, vid, text = str(item.get("comment_id", "")), str(item.get("video_id", "")), (item.get("text") or "").strip()
    if not COMMENT_ID.match(cid):
        out.append("COMMENT_ID_INVALID")
    if not VIDEO_ID.match(vid):
        out.append("VIDEO_ID_INVALID")
    elif vid not in own_videos:
        out.append("NOT_OUR_VIDEO")
    if item.get("decision") == "SKIP":
        return out + ([] if policy is None else policy(item, "tiktok"))
    if item.get("decision") != "REPLY":
        return out + ["DECISION_INVALID"]
    if not text:
        out.append("REPLY_EMPTY")
    if len(text) > LIMIT:
        out.append("REPLY_TOO_LONG")
    if URL.search(text) or re.search(r"(?<![\w.])@\w", text) or re.search(r"(?<![\w&])#\w", text):
        out.append("REPLY_HAS_LINK_MENTION_OR_TAG")
    if policy is None:
        out.append("POLICY_UNAVAILABLE (deploy reply_policy.py and kjv_check.py with the runner)")
    else:
        out += policy(item, "tiktok")
    return out


def plan(replies, ledger, own_videos, now, run_cap=RUN_CAP, policy=None):
    """(the replies to act on this run, the skips to record, the refused ones with reasons, why the run waits or None).
    A SKIP (spam, hate, provocation...) is only recorded: nothing is clicked and it counts toward no cap."""
    skips = [i for i in replies if i.get("decision") == "SKIP" and str(i.get("comment_id", "")) not in ledger.get("actions", {})
             and not reply_problems(i, own_videos, policy)]
    gap = last_action(ledger)
    if gap and now - gap < MIN_GAP:
        return [], skips, [], f"WAIT_MIN_GAP last action {iso(gap)}"
    room = max(0, min(run_cap, DAY_CAP - actions_today(ledger, now)))
    if room == 0:
        return [], skips, [], "DAY_CAP_REACHED"
    todo, refused, seen = [], [], set()
    for item in replies:
        cid = str(item.get("comment_id", ""))
        if cid in ledger.get("actions", {}) or cid in seen or item.get("decision") == "SKIP":
            continue
        bad = reply_problems(item, own_videos, policy)
        if bad:
            refused.append({"comment_id": cid, "problems": bad})
            continue
        seen.add(cid)
        if len(todo) < room:
            todo.append(item)
    return todo, skips, refused, None


def pauses(n, rng=random):
    """The waits before each of n comments: none before the first, PAUSE between the others."""
    return [0] + [rng.uniform(*PAUSE) for _ in range(max(0, n - 1))]


def comments_from_api(body, video_id, handle=HANDLE):
    """Viewers' top-level comments from one /api/comment/list/ response (TikTok web)."""
    out = []
    for c in (body or {}).get("comments") or []:
        user = c.get("user") or {}
        if user.get("unique_id") == handle or c.get("reply_id") not in (None, "0", 0):
            continue
        out.append({"comment_id": str(c.get("cid")), "video_id": str(video_id), "author": user.get("unique_id"),
                    "text": c.get("text") or c.get("share_info", {}).get("desc", ""),
                    "create_time": c.get("create_time"), "digg_count": c.get("digg_count", 0),
                    "liked_by_us": bool(c.get("user_digged")),
                    "replies_total": c.get("reply_comment_total", 0)})
    return out


def videos_from_api(body, handle=HANDLE):
    """Our videos from one /api/post/item_list/ response: only items whose author is our handle."""
    out = []
    for it in (body or {}).get("itemList") or []:
        if (it.get("author") or {}).get("uniqueId") != handle:
            continue
        out.append({"video_id": str(it.get("id")), "desc": it.get("desc", ""), "create_time": it.get("createTime"),
                    "comments": (it.get("stats") or {}).get("commentCount", 0)})
    return out


def new_comments(found, ledger):
    """Comments not decided yet: none acted on or skipped (the ledger), each once."""
    acted, out, seen = set(ledger.get("actions", {})), [], set()
    for c in found:
        if c["comment_id"] not in acted and c["comment_id"] not in seen:
            seen.add(c["comment_id"])
            out.append(c)
    return out
