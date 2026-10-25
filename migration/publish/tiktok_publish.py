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
oldest first. Idempotent through tiktok_ledger.json: the key is recorded as SENDING before the call, so a lost or
unclear reply never sends twice (it is reported); only an explicit refusal or Buffer's "error" is retried, and three
failures make a Short FAILED_FINAL so it never blocks the queue.
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


FINAL = DONE | {"FAILED_FINAL", "STUCK"}
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
    """One Buffer GraphQL call: (data, error text or None, refused). `refused` is True only when the reply says
    nothing was done (a 4xx, or GraphQL errors without data); a 5xx, an unreadable body or a lost reply is unknown."""
    r = call("POST", API, token=key, body={"query": query, "variables": variables or {}})
    code = r.get("_http")
    if code == 0:
        return None, f"network {r.get('_net')}", False
    msg = "; ".join(str(e.get("message", ""))[:400] for e in r.get("errors") or [])
    if code != 200:
        return r.get("data"), f"HTTP {code} {msg}".strip(), 400 <= (code or 0) < 500
    if msg:
        return r.get("data"), msg, not r.get("data")
    return r.get("data"), None, False


ORGS = "query { account { organizations { id } } }"
CREATE = """mutation Create($input: CreatePostInput!) { createPost(input: $input) {
  ... on PostActionSuccess { post { id status } }
  ... on MutationError { message } } }"""


def channels_query(org):
    return "query { channels(input: {organizationId: %s}) { id service name } }" % json.dumps(org)


def status_query(post_id):
    return "query { post(input: {id: %s}) { id status } }" % json.dumps(post_id)


INPUT_TYPE = "query { __type(name: %s) { name inputFields { name type { kind name ofType { kind name ofType { kind name ofType { name } } } } } } }"


def describe(key, root="CreatePostInput", call=http, depth=3):
    """The input types createPost accepts (names only), so a schema change is fixed from evidence, not guessed."""
    out, todo = {}, [root]
    while todo and depth:
        nxt = []
        for name in todo:
            data, err, _ = gql(INPUT_TYPE % json.dumps(name), None, key, call)
            fields = ((data or {}).get("__type") or {}).get("inputFields") or []
            out[name] = err or {}
            for f in fields:
                t, chain = f["type"], []
                while t:
                    chain.append(t.get("name") or t.get("kind"))
                    t = t.get("ofType")
                out[name][f["name"]] = " / ".join(c for c in chain if c)
                base = [c for c in chain if c and c not in ("NON_NULL", "LIST")]
                if base and base[-1].endswith("Input") and base[-1] not in out:
                    nxt.append(base[-1])
        todo, depth = nxt, depth - 1
    return out


def tiktok_channel(key, call=http):
    data, err, _ = gql(ORGS, None, key, call)
    if err:
        raise SystemExit(f"BUFFER_ORGANIZATIONS {err}")
    found = []
    for org in (data or {}).get("account", {}).get("organizations", []):
        data, err, _ = gql(channels_query(org["id"]), None, key, call)
        if err:
            raise SystemExit(f"BUFFER_CHANNELS {err}")
        found += [c for c in (data or {}).get("channels") or [] if str(c.get("service", "")).lower() == "tiktok"]
    if len(found) != 1:
        raise SystemExit(f"BUFFER_TIKTOK_CHANNEL {len(found)} found (expected exactly 1)")
    return found[0]["id"]


def post(ep, key, channel, record, call=http):
    """SENDING is recorded before the call. Only an explicit refusal is FAILED (retried later); any reply that does not
    say what happened stays SENDING, is never sent again, and is reported until the owner checks Buffer."""
    record({"status": "SENDING", "video_url": video_url(ep)})
    data, err, refused = gql(CREATE, {"input": {"channelId": channel, "text": caption(ep), "schedulingType": "automatic",
                                                "mode": "shareNow", "needsApproval": False, "aiAssisted": True,
                                                "assets": [{"video": {"url": video_url(ep)}}]}},
                             key, call)
    res = (data or {}).get("createPost") or {}
    if (res.get("post") or {}).get("id"):
        return {"status": "QUEUED", "buffer_post_id": res["post"]["id"], "buffer_status": res["post"].get("status")}
    if res.get("message"):
        return {"status": "FAILED", "fail_reason": str(res["message"])[:200]}
    if refused:
        return {"status": "FAILED", "fail_reason": (err or "refused")[:600]}
    return {"status": "SENDING", "fail_reason": (err or "no post id in the reply")[:200]}


def recheck(tiktok, key, now, call=http):
    """Follow posts Buffer has not sent yet by their post id; never send them again. Only Buffer's own "error" allows
    a retry; a post that cannot be confirmed within a day becomes STUCK (reported, never re-sent)."""
    changed = []
    for k, rec in tiktok.get("posts", {}).items():
        if rec.get("status") != "QUEUED" or not rec.get("buffer_post_id"):
            continue
        data, err, _ = gql(status_query(rec["buffer_post_id"]), None, key, call)
        status = str(((data or {}).get("post") or {}).get("status", "")).lower()
        if not err and status == "sent":
            rec.update(status="SENT", buffer_status=status)
        elif not err and status == "error":
            rec.update(status="FAILED", fail_reason="Buffer reported an error sending to TikTok")
        elif parse(rec.get("at")) and now - parse(rec["at"]) > timedelta(hours=RECHECK_HOURS):
            rec.update(status="STUCK", fail_reason=f"not confirmed after {RECHECK_HOURS} h (last {status or err})")
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
        print(json.dumps({"tiktok_channel": tiktok_channel(key), "pending": [k for k, _ in todo],
                          "create_post_input": describe(key)}, indent=1))
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
    attention = {k: r["status"] for k, r in posts.items() if r.get("status") in ("FAILED_FINAL", "STUCK", "SENDING")}
    if attention:   # the owner checks these in Buffer; the queue moves on, the run turns red until they are settled
        print(json.dumps({"tiktok_needs_owner": attention}))
        rc = 1
    return rc


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] not in ("pending", "post", "discover"):
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:]))
