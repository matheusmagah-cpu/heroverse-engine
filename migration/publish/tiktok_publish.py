#!/usr/bin/env python3
"""Mirror the channel's Bible-series Shorts to the HeroVerse TikTok account through Buffer (owner, 2026-10-25: "every
Short posted on one is posted on the other, the old ones too, all automatic"; TikTok is the door to the long videos).

TikTok's own Content Posting API is not open to a tool that posts only to its owner's account (Content Sharing
Guidelines, "Not acceptable"), so the post goes through Buffer's free plan, whose TikTok app is approved, with its
public GraphQL API (BUFFER_API_KEY, a repository secret; never printed). Buffer publishes automatically
(schedulingType automatic, mode shareNow) and fetches the video from its public release URL.

Only a Short already in the YouTube ledger (it passed approve/publish) and whose YouTube slot has passed is sent, the
same file (the workflow checks its sha256), with a caption that names the full story on YouTube (link in bio; TikTok
captions are not clickable) and states the KJV source and the AI-generated visuals and voice. One Short per run,
oldest first. Idempotent through tiktok_ledger.json: the key is recorded as SENDING before the call, so a lost reply
never sends twice; three failures make a Short FAILED_FINAL so it never blocks the queue.
usage: tiktok_publish.py pending|post|discover LEDGER TIKTOK_LEDGER EPISODES_DIR
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import urllib.request

API = "https://api.buffer.com"
PER_RUN = 1
DONE = {"SENT"}
TAGS = "#bible #biblestory #kjv #faith #aigenerated"
RELEASE = "https://github.com/matheusmagah-cpu/heroverse-engine/releases/download/v0.0.0-cloud-assets-20261013/"


def now_utc():
    return datetime.now(timezone.utc)


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


FINAL = DONE | {"FAILED_FINAL"}
MAX_FAILURES = 3          # then FAILED_FINAL: one Short TikTok always refuses never blocks the rest of the queue
RECHECK_HOURS = 24        # a post Buffer has not sent within a day is treated as failed (retried)
UNSLOTTED_MARGIN_H = 24   # an episode without a slot is mirrored only a day after its YouTube upload


def pending(ledger, tiktok, episodes_dir, now):
    """Bible Shorts published on YouTube (ledger key bible:<id>:<sha>) whose slot has passed and that TikTok has not
    received yet: never tried first (oldest slot first), then earlier failures. A key with any other recorded status
    (sending, queued, sent) is never sent again; recheck() follows it by its Buffer post id."""
    out = []
    for key, entry in ledger.get("entries", {}).items():
        if not key.startswith("bible:") or not entry.get("video_id"):
            continue
        _, eid, sha = key.split(":", 2)
        status = (tiktok.get("posts", {}).get(key) or {}).get("status")
        if status not in (None, "FAILED"):
            continue
        path = Path(episodes_dir) / f"{eid}.json"
        if not path.exists():
            continue
        ep = json.loads(path.read_text())
        if ep.get("output_sha256") != sha:
            continue
        slot = parse(ep.get("slot"))
        if not slot and parse(entry.get("uploaded_at")):   # published at once, or with a publish time not recorded
            slot = parse(entry["uploaded_at"]) + timedelta(hours=UNSLOTTED_MARGIN_H)
        if slot and slot <= now:
            out.append((status == "FAILED", slot, key, ep))
    return [(k, ep) for _, _, k, ep in sorted(out, key=lambda x: (x[0], x[1], x[2]))]


def caption(ep):
    """The hook, the way to the long video, the honest source line and tags. Links in TikTok captions are not
    clickable, so the viewer is sent to the link in bio and told what to look for on YouTube."""
    title = (ep.get("title") or "").replace("#shorts", "").replace("#Shorts", "").strip()
    story = title.split("|", 1)[-1].strip() if "|" in title else "the full story"
    return (f"{title}\n\n▶ The full story, {story}, is on YouTube: HeroVerse (link in bio).\n"
            f"Scripture: King James Version. Visuals and voice: AI-generated.\n{TAGS}")[:2200]


def asset_name(ep):
    return f"bible-{ep['id']}-sha256-{ep['output_sha256']}.mp4"


def video_url(ep):
    return RELEASE + asset_name(ep)


def http(method, url, token=None, body=None, data=None, headers=None, timeout=120):
    """JSON reply plus "_http" (status code, or 0 when the network failed: the outcome is unknown)."""
    h = dict(headers or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    if body is not None:
        h["Content-Type"] = "application/json; charset=UTF-8"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, code = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    except OSError as e:   # URLError, timeouts, resets
        return {"_http": 0, "_net": type(e).__name__}
    try:
        out = json.loads(raw or b"{}")
    except ValueError:
        out = {}
    return dict(out, _http=code) if isinstance(out, dict) else {"_http": code}


def gql(query, variables, key, call=http):
    """One Buffer GraphQL call: (data, error text or None). The key travels only in the Authorization header."""
    r = call("POST", API, token=key, body={"query": query, "variables": variables or {}})
    if r.get("_http") == 0:
        return None, f"network {r.get('_net')}"
    if r.get("errors"):
        return r.get("data"), "; ".join(str(e.get("message", ""))[:160] for e in r["errors"])
    if r.get("_http") != 200:
        return r.get("data"), f"HTTP {r.get('_http')}"
    return r.get("data"), None


CHANNELS = "query { account { organizations { id channels { id service name } } } }"
CREATE = """mutation Create($input: CreatePostInput!) { createPost(input: $input) {
  ... on PostActionSuccess { post { id status } }
  ... on MutationError { message } } }"""
STATUS = "query Post($id: PostId!) { post(input: {id: $id}) { id status error { message } } }"


def tiktok_channel(key, call=http):
    data, err = gql(CHANNELS, None, key, call)
    if err:
        raise SystemExit(f"BUFFER_CHANNELS {err}")
    found = [c for o in (data or {}).get("account", {}).get("organizations", []) for c in o.get("channels") or []
             if str(c.get("service", "")).lower() == "tiktok"]
    if len(found) != 1:
        raise SystemExit(f"BUFFER_TIKTOK_CHANNEL {len(found)} found (expected exactly 1)")
    return found[0]["id"]


def post(ep, key, channel, record, call=http):
    """SENDING is recorded before the call; a lost reply stays SENDING (never re-sent; recheck or the owner decides)."""
    record({"status": "SENDING", "video_url": video_url(ep)})
    data, err = gql(CREATE, {"input": {"channelId": channel, "text": caption(ep), "schedulingType": "automatic",
                                       "mode": "shareNow", "assets": {"videos": [{"url": video_url(ep)}]}}}, key, call)
    if err and err.startswith("network"):
        return {"status": "SENDING", "fail_reason": err}
    res = (data or {}).get("createPost") or {}
    if err or res.get("message") or not (res.get("post") or {}).get("id"):
        return {"status": "FAILED", "fail_reason": (err or res.get("message") or "no post id")[:200]}
    return {"status": "QUEUED", "buffer_post_id": res["post"]["id"], "buffer_status": res["post"].get("status")}


def recheck(tiktok, key, now, call=http):
    """Follow posts Buffer has not sent yet by their post id; never send them again."""
    changed = []
    for k, rec in tiktok.get("posts", {}).items():
        if rec.get("status") != "QUEUED" or not rec.get("buffer_post_id"):
            continue
        data, err = gql(STATUS, {"id": rec["buffer_post_id"]}, key, call)
        p = (data or {}).get("post") or {}
        status = str(p.get("status", "")).lower()
        if not err and status == "sent":
            rec.update(status="SENT", buffer_status=status)
        elif not err and status == "error":
            rec.update(status="FAILED", fail_reason=str((p.get("error") or {}).get("message", "error"))[:200])
        elif parse(rec.get("at")) and now - parse(rec["at"]) > timedelta(hours=RECHECK_HOURS):
            rec.update(status="FAILED", fail_reason=f"not sent after {RECHECK_HOURS} h (last {status or err})")
        else:
            continue
        changed.append(k)
    return changed


def settle(rec, previous):
    """Count failures; after MAX_FAILURES the Short is FAILED_FINAL (reported, skipped)."""
    if rec.get("status") == "FAILED":
        rec["failures"] = (previous or {}).get("failures", 0) + 1
        if rec["failures"] >= MAX_FAILURES:
            rec["status"] = "FAILED_FINAL"
    return rec


def main(cmd, ledger_path, tiktok_path, episodes_dir):
    ledger = json.loads(Path(ledger_path).read_text())
    tpath = Path(tiktok_path)
    tiktok = json.loads(tpath.read_text()) if tpath.exists() else {"version": "tiktok-ledger-v1", "posts": {}}
    posts = tiktok.setdefault("posts", {})
    now = now_utc()
    todo = pending(ledger, tiktok, episodes_dir, now)
    if cmd == "pending":
        for k, ep in todo:
            print(k, asset_name(ep))
        return 0
    key = os.environ["BUFFER_API_KEY"]
    if cmd == "discover":   # ids and service names only: what the mirror will post to
        print(json.dumps({"tiktok_channel": tiktok_channel(key), "pending": [k for k, _ in todo]}))
        return 0

    def save():
        tpath.write_text(json.dumps(tiktok, indent=1) + "\n")

    for k in recheck(tiktok, key, now):
        settle(posts[k], dict(posts[k], failures=posts[k].get("failures", 0)))
        print(json.dumps({"key": k, "rechecked": posts[k]["status"]}))
    save()
    if not todo:
        print(json.dumps({"tiktok": "NOTHING_PENDING"}))
        return 0
    channel = tiktok.get("buffer_channel_id") or tiktok_channel(key)
    tiktok["buffer_channel_id"] = channel
    rc = 0
    for k, ep in todo[:PER_RUN]:
        previous = posts.get(k)
        base = {"youtube_video_id": ledger["entries"][k]["video_id"], "at": now.isoformat()}

        def record(rec, k=k, base=base):
            posts[k] = dict(rec, **base, failures=(previous or {}).get("failures", 0))
            save()
        result = settle(dict(post(ep, key, channel, record), **base), previous)
        posts[k] = result
        save()
        print(json.dumps({"key": k, **result}))
        rc = 1 if result["status"] in ("FAILED", "FAILED_FINAL") else rc
    final = sorted(k for k, r in posts.items() if r.get("status") == "FAILED_FINAL")
    if final:
        print(json.dumps({"tiktok_failed_final": final}))   # the owner decides; the queue moves on
    return rc


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] not in ("pending", "post", "discover"):
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:]))
