#!/usr/bin/env python3
"""Answer viewers' comments on our YouTube videos (owner, 2026-10-28). Three files, one writer each:

  publish/comment_queue.json          written by `fetch` (comment-replies.yml): new top-level comments of viewers on
                                      our channel's videos, with the video's title and episode for context
  publish/comment_replies.json        written by Claude (main clock, by PR): one decision per comment id,
                                      REPLY with the text (and a checked KJV verse when it fits) or SKIP with a reason
                                      (spam, hate, provocation...: never argued with); gated by reply_policy.py
  publish/comment_replies_ledger.json written by `post`: every reply posted (comments.insert, parentId) or refused
                                      for good; a comment in it is never answered again

`post` answers at most MAX_RUN comments a run and DAY_CAP a UTC day, only on threads of our own channel, after
checking live that the comment still exists and that the channel has not already answered it (a run that stopped
before recording is recovered, never posted twice). The Data API cannot like a comment: nothing tries.
Same credential as publish_video.py (secret HERO_YT_AUTHORIZED_USER_JSON); youtube.force-ssl is checked each run.
ops/PUBLICATION_HOLD stops fetch and post.

usage: comment_replies.py todo              offline: comment ids waiting for Claude's decision, then "post N"
       comment_replies.py check             offline: every decision passes reply_policy (exit 1 otherwise)
       comment_replies.py fetch             reads YouTube, adds new comments to the queue
       comment_replies.py post [MAX]        posts the decided replies (dry run: env DRY_RUN=1 prints only)
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reply_policy  # noqa: E402

ROOT = HERE.parent.parent
QUEUE = HERE / "comment_queue.json"
REPLIES = HERE / "comment_replies.json"
LEDGER = HERE / "comment_replies_ledger.json"
PUBLISH_LEDGER = HERE / "ledger.json"
HOLD = ROOT / "migration/ops/PUBLICATION_HOLD"
CHANNEL = "UCuMF6pJQkyMzaVoAxFL86yA"
API = "https://www.googleapis.com/youtube/v3/"
COMMENT_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
DAY_CAP = 20          # replies a UTC day (owner)
MAX_RUN = 4           # replies a run: six heartbeat slots spread the day's 20
PAGES = 3             # 100 threads a page, newest first
KEEP = timedelta(days=30)   # a decided comment older than this leaves the queue (the ledger keeps it for good)
TERMINAL = ("commentsDisabled", "commentNotFound", "parentCommentNotFound", "forbidden", "processingFailure",
            "invalidCommentMetadata", "HTTP_404")


def read(path, default):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n")


def now_iso(now=None):
    return (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def empty_queue():
    return {"version": "comment-queue-v1", "comments": {}}


def empty_ledger():
    return {"version": "comment-replies-ledger-v1", "posted": {}, "refused": {}}


def episodes_by_video(publish_ledger):
    """video id -> episode id (Shorts "bible:<ep>:<sha>") or pilot (longs "<pilot>:<sha>"), from the publish ledger."""
    out = {}
    for key, e in (publish_ledger.get("entries") or {}).items():
        if e.get("video_id"):
            parts = key.split(":")
            out[e["video_id"]] = parts[1] if parts[0] == "bible" and len(parts) > 1 else parts[0]
    return out


# ---------- offline ----------

def todo(queue, replies, ledger):
    """(comment ids waiting for a decision, number of REPLY decisions not yet posted or refused)."""
    decided = replies.get("replies", {})
    done = set(ledger.get("posted", {})) | set(ledger.get("refused", {}))
    waiting = sorted(cid for cid in queue.get("comments", {}) if cid not in decided and cid not in done)
    to_post = [cid for cid, d in decided.items() if d.get("decision") == "REPLY" and cid not in done]
    return waiting, len(to_post)


def check(queue, replies, ledger=None):
    out = reply_policy.file_problems(replies.get("replies", {}), "youtube")
    comments = queue.get("comments", {})
    done = set((ledger or {}).get("posted", {})) | set((ledger or {}).get("refused", {}))
    # E256: a posted reply leaves the queue but stays in the decisions file; only an unknown id is an error
    out += [f"{cid}: NOT_IN_QUEUE" for cid in replies.get("replies", {}) if cid not in comments and cid not in done]
    return out


def posted_today(ledger, now):
    day = now.date()
    return sum(1 for e in ledger.get("posted", {}).values() if e.get("posted_at") and ts(e["posted_at"]).date() == day)


def plan(queue, replies, ledger, now, max_run=MAX_RUN):
    """The comment ids to answer this run, in the order the comments came: decided REPLY, passing the policy, in the
    queue, not posted or refused, within the run and day caps."""
    room = max(0, min(max_run, DAY_CAP - posted_today(ledger, now)))
    done = set(ledger.get("posted", {})) | set(ledger.get("refused", {}))
    comments = queue.get("comments", {})
    out = []
    for cid, d in sorted(replies.get("replies", {}).items(), key=lambda kv: comments.get(kv[0], {}).get("published_at", "")):
        if len(out) >= room:
            break
        if (d.get("decision") == "REPLY" and cid in comments and cid not in done
                and not reply_policy.problems(d, "youtube")):
            out.append(cid)
    return out


# ---------- YouTube ----------

def check_response(r, what):
    if r.status_code >= 300:
        reason = ""
        try:
            errs = r.json().get("error", {}).get("errors", [])
            reason = errs[0].get("reason", "") if errs else ""
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(f"{what}_HTTP_{r.status_code} {reason}".strip())
    return r.json() if r.content else {}


def session():
    sys.path.insert(0, str(HERE))
    import arc_links  # noqa: E402  same credential and scope check as the arc links
    return arc_links.session()


def own_channel(s):
    items = check_response(s.get(API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL").get("items", [])
    if [c["id"] for c in items] != [CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")


def threads(s, pages=PAGES):
    out, token = [], None
    for _ in range(pages):
        params = {"part": "snippet,replies", "allThreadsRelatedToChannelId": CHANNEL, "maxResults": 100,
                  "order": "time", "textFormat": "plainText"}
        if token:
            params["pageToken"] = token
        body = check_response(s.get(API + "commentThreads", params=params), "THREADS")
        out += body.get("items", [])
        token = body.get("nextPageToken")
        if not token:
            break
    return out


def answered_by_us(thread):
    return any(r.get("snippet", {}).get("authorChannelId", {}).get("value") == CHANNEL
               for r in (thread.get("replies") or {}).get("comments", []))


def new_comments(items, queue, ledger, titles, episodes, now):
    """Viewers' top-level comments on our videos that are not queued, answered or refused yet."""
    known = set(queue.get("comments", {})) | set(ledger.get("posted", {})) | set(ledger.get("refused", {}))
    out = {}
    for t in items:
        sn = t.get("snippet", {})
        top = sn.get("topLevelComment", {})
        c = top.get("snippet", {})
        cid = top.get("id") or t.get("id")
        if (not cid or cid in known or sn.get("channelId") != CHANNEL
                or c.get("authorChannelId", {}).get("value") == CHANNEL or answered_by_us(t)):
            continue
        vid = sn.get("videoId") or c.get("videoId")
        out[cid] = {"video_id": vid, "video_title": titles.get(vid), "episode": episodes.get(vid),
                    "author": c.get("authorDisplayName"), "text": c.get("textOriginal") or c.get("textDisplay"),
                    "published_at": c.get("publishedAt"), "like_count": c.get("likeCount", 0),
                    "fetched_at": now_iso(now)}
    return out


def video_titles(s, ids):
    out, ids = {}, sorted(i for i in ids if i)
    for i in range(0, len(ids), 50):
        body = check_response(s.get(API + "videos", params={"part": "snippet", "id": ",".join(ids[i:i + 50])}), "VIDEOS")
        out.update({it["id"]: it["snippet"]["title"] for it in body.get("items", [])})
    return out


def prune(queue, replies, ledger, now):
    done = set(ledger.get("posted", {})) | set(ledger.get("refused", {})) | {
        cid for cid, d in replies.get("replies", {}).items() if d.get("decision") == "SKIP"}
    for cid in [c for c, e in queue["comments"].items()
                if c in done and e.get("published_at") and now - ts(e["published_at"]) > KEEP]:
        del queue["comments"][cid]


def fetch(s, queue_path=QUEUE, replies_path=REPLIES, ledger_path=LEDGER, publish_ledger=PUBLISH_LEDGER, now=None):
    now = now or datetime.now(timezone.utc)
    own_channel(s)
    queue, ledger = read(queue_path, empty_queue()), read(ledger_path, empty_ledger())
    items = threads(s)
    vids = {t.get("snippet", {}).get("videoId") for t in items}
    new = new_comments(items, queue, ledger, video_titles(s, vids), episodes_by_video(read(publish_ledger, {})), now)
    queue["comments"].update(new)
    prune(queue, read(replies_path, {"replies": {}}), ledger, now)
    queue["fetched_at"] = now_iso(now)
    write(queue_path, queue)
    print(json.dumps({"threads_read": len(items), "new": len(new), "queued": len(queue["comments"])}))
    return new


def live_thread(s, cid):
    body = check_response(s.get(API + "commentThreads", params={"part": "snippet", "id": cid}), "THREAD")
    return (body.get("items") or [None])[0]


def our_reply(s, cid, text):
    """The id of the channel's reply with this text under the comment, if a run already posted it."""
    body = check_response(s.get(API + "comments", params={"part": "snippet", "parentId": cid, "maxResults": 100,
                                                          "textFormat": "plainText"}), "REPLIES")
    for c in body.get("items", []):
        sn = c.get("snippet", {})
        if sn.get("authorChannelId", {}).get("value") == CHANNEL and reply_policy.norm(sn.get("textOriginal")) == text:
            return c["id"]
    return None


def post(s, scopes, max_run=MAX_RUN, queue_path=QUEUE, replies_path=REPLIES, ledger_path=LEDGER, now=None,
         dry=False, out=print):
    now = now or datetime.now(timezone.utc)
    if COMMENT_SCOPE not in set(scopes or ()):
        raise SystemExit("SCOPE_MISSING youtube.force-ssl (comments.insert)")
    queue, replies = read(queue_path, empty_queue()), read(replies_path, {"replies": {}})
    ledger = read(ledger_path, empty_ledger())
    ids = plan(queue, replies, ledger, now, max_run)
    own_channel(s)
    for cid in ids:
        text = reply_policy.norm(replies["replies"][cid]["text"])
        rec = {"video_id": queue["comments"][cid].get("video_id"), "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
        try:
            thread = live_thread(s, cid)
            if not thread:
                ledger["refused"][cid] = {**rec, "reason": "commentNotFound", "at": now_iso(now)}
            elif thread.get("snippet", {}).get("channelId") != CHANNEL:
                ledger["refused"][cid] = {**rec, "reason": "NOT_OUR_CHANNEL", "at": now_iso(now)}
            elif (found := our_reply(s, cid, text)):
                ledger["posted"][cid] = {**rec, "reply_id": found, "posted_at": now_iso(now), "recovered": True}
            elif dry:
                out(json.dumps({"dry_run": cid, "text": text}, ensure_ascii=False))
                continue
            else:
                body = check_response(s.post(API + "comments", params={"part": "snippet"},
                                             json={"snippet": {"parentId": cid, "textOriginal": text}}), "INSERT")
                ledger["posted"][cid] = {**rec, "reply_id": body.get("id"), "posted_at": now_iso(now)}
        except RuntimeError as e:
            reason = str(e)
            if any(t in reason for t in TERMINAL):
                ledger["refused"][cid] = {**rec, "reason": reason, "at": now_iso(now)}
            else:
                out(f"TRANSIENT {cid} {reason}")   # left for the next run
                continue
        finally:
            if not dry:
                write(ledger_path, ledger)   # after every comment: a crash never loses a posted reply
        state = "posted" if cid in ledger["posted"] else "refused"
        out(json.dumps({"comment": cid, state: ledger[state][cid].get("reply_id") or ledger[state][cid].get("reason")}))
    out(json.dumps({"planned": len(ids), "posted_today": posted_today(ledger, now), "day_cap": DAY_CAP}))
    return ids


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    queue, replies, ledger = read(QUEUE, empty_queue()), read(REPLIES, {"replies": {}}), read(LEDGER, empty_ledger())
    if mode == "todo":
        if HOLD.exists():
            return 0
        waiting, to_post = todo(queue, replies, ledger)
        for cid in waiting:
            print(cid)
        if to_post:
            print(f"post {to_post}")
        return 0
    if mode == "check":
        bad = check(queue, replies, ledger)
        print("\n".join(bad) or "PASS")
        return 1 if bad else 0
    if mode in ("fetch", "post"):
        if HOLD.exists():
            print("PUBLICATION_HOLD")
            return 1
        s, scopes = session()
        if mode == "fetch":
            fetch(s)
        else:
            post(s, scopes, int(argv[2]) if len(argv) > 2 else MAX_RUN, dry=os.environ.get("DRY_RUN") == "1")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
