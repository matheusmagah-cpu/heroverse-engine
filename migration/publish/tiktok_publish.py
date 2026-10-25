#!/usr/bin/env python3
"""Mirror the channel's Bible-series Shorts to the HeroVerse TikTok account (owner, 2026-10-25: "every Short posted on
one is posted on the other, the old ones too").

Only a Short already in the YouTube ledger (so it passed approve/publish) and whose YouTube slot has passed is posted,
with the same file (its sha256 must equal the episode record), its title as the caption and TikTok's AI-generated
label (is_aigc). TikTok Content Posting API, free:
  direct -> /v2/post/publish/video/init/ (scope video.publish); until TikTok audits the app, only the privacy levels
            creator_info returns are allowed (SELF_ONLY), so the post is private until the owner opens it
  inbox  -> /v2/post/publish/inbox/video/init/ (scope video.upload); the video lands as a draft in the TikTok app and
            the owner taps "Post"
At most PER_RUN Shorts per run, oldest first, so the backlog never lands as a burst. Idempotent through
tiktok_ledger.json (key -> publish_id, status). Tokens come only from the environment and are never printed; a
rotated refresh token is written back to the repository secret through `gh secret set` (stdin, GH_SECRETS_PAT).
usage: tiktok_publish.py pending|post LEDGER TIKTOK_LEDGER EPISODES_DIR [VIDEO_DIR]
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
import urllib.request

API = "https://open.tiktokapis.com/v2/"
PER_RUN = 1
SINGLE_CHUNK_MAX = 64 * 1024 * 1024    # one PUT up to this size (Content Posting API chunk rules)
DONE = {"PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"}
TAGS = "#bible #biblestory #kjv #faith #shorts"


def now_utc():
    return datetime.now(timezone.utc)


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


FINAL = DONE | {"FAILED_FINAL"}
MAX_FAILURES = 3          # then FAILED_FINAL: one Short TikTok always refuses never blocks the rest of the queue
RECHECK_HOURS = 24        # a post TikTok has not finished within a day is treated as failed (retried)
UNSLOTTED_MARGIN_H = 24   # an episode without a slot is mirrored only a day after its YouTube upload


def pending(ledger, tiktok, episodes_dir, now):
    """Bible Shorts published on YouTube (ledger key bible:<id>:<sha>) whose slot has passed and that TikTok has not
    received yet: never tried first (oldest slot first), then earlier failures. A key with any other recorded status
    (initialized, uploading, processing, done) is never sent again; recheck() follows it by its publish_id."""
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
    title = (ep.get("title") or "").replace("#shorts", "").replace("#Shorts", "").strip()
    return f"{title}\n\nFull story on YouTube: HeroVerse\n{TAGS}"[:2200]


def asset_name(ep):
    return f"bible-{ep['id']}-sha256-{ep['output_sha256']}.mp4"


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


def api_error(resp):
    err = (resp or {}).get("error") or {}
    return None if err.get("code") in (None, "ok") else f"{err.get('code')}: {err.get('message', '')[:160]}"


def refresh(call=http, env=os.environ):
    """A fresh access token; (access_token, new_refresh_token or None when unchanged). Values never printed."""
    form = urllib.parse.urlencode({"client_key": env["TIKTOK_CLIENT_KEY"], "client_secret": env["TIKTOK_CLIENT_SECRET"],
                                   "grant_type": "refresh_token", "refresh_token": env["TIKTOK_REFRESH_TOKEN"]}).encode()
    r = call("POST", API + "oauth/token/", data=form, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if not r.get("access_token"):
        raise SystemExit(f"TIKTOK_TOKEN_REFRESH_FAILED {r.get('error', '')} (re-authorize: tiktok-auth.yml)")
    new = r.get("refresh_token")
    return r["access_token"], (new if new and new != env["TIKTOK_REFRESH_TOKEN"] else None)


def store_refresh_token(token, run=subprocess.run, env=os.environ):
    """Write a rotated refresh token back to the repository secret (stdin only; never echoed)."""
    if not env.get("GH_SECRETS_PAT"):
        raise SystemExit("TIKTOK_REFRESH_TOKEN_ROTATED but GH_SECRETS_PAT is missing (re-authorize: tiktok-auth.yml)")
    r = run(["gh", "secret", "set", "TIKTOK_REFRESH_TOKEN", "--repo", env.get("GITHUB_REPOSITORY", "")],
            input=token, text=True, capture_output=True, env=dict(env, GH_TOKEN=env["GH_SECRETS_PAT"]))
    if r.returncode != 0:
        raise SystemExit("TIKTOK_REFRESH_TOKEN_STORE_FAILED")


def privacy(options):
    """Public when TikTok allows it for this app, else the most private level it offers (unaudited apps)."""
    for p in ("PUBLIC_TO_EVERYONE", "SELF_ONLY"):
        if p in (options or []):
            return p
    raise SystemExit(f"TIKTOK_NO_PRIVACY_OPTION {options}")


def init_body(ep, size, mode, options=None):
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}
    if mode == "inbox":
        return {"source_info": source}
    return {"post_info": {"title": caption(ep), "privacy_level": privacy(options), "disable_duet": False,
                          "disable_comment": False, "disable_stitch": False, "is_aigc": True,
                          "brand_content_toggle": False, "brand_organic_toggle": False},
            "source_info": source}


def fetch(pid, token, call=http):
    s = call("POST", API + "post/publish/status/fetch/", token=token, body={"publish_id": pid})
    d = s.get("data") or {}
    return d.get("status"), d.get("fail_reason")


def poll(pid, token, call=http, sleep=time.sleep, tries=40):
    status, reason = None, None
    for _ in range(tries):
        status, reason = fetch(pid, token, call)
        if status in DONE or status == "FAILED":
            break
        sleep(15)
    return status, reason


def post(ep, video, token, mode, record, call=http, sleep=time.sleep):
    """init -> record(publish_id) BEFORE the upload, so a crash later never leads to a second post -> PUT -> poll.
    Returns the final record; a status that is not final yet is re-checked next run (recheck)."""
    size = Path(video).stat().st_size
    if size > SINGLE_CHUNK_MAX:
        raise SystemExit(f"TIKTOK_FILE_TOO_LARGE {size}")
    options = None
    if mode == "direct":
        info = call("POST", API + "post/publish/creator_info/query/", token=token, body={})
        if api_error(info) or info.get("_http") != 200:
            raise SystemExit(f"TIKTOK_CREATOR_INFO {api_error(info) or info.get('_http')}")
        options = info.get("data", {}).get("privacy_level_options")
    url = API + ("post/publish/inbox/video/init/" if mode == "inbox" else "post/publish/video/init/")
    r = call("POST", url, token=token, body=init_body(ep, size, mode, options))
    if api_error(r) or not (r.get("data") or {}).get("publish_id"):
        return {"status": "FAILED", "mode": mode, "fail_reason": f"init {api_error(r) or r.get('_http')}"}
    pid, upload = r["data"]["publish_id"], r["data"]["upload_url"]
    rec = {"publish_id": pid, "status": "INITIALIZED", "mode": mode,
           "privacy": None if mode == "inbox" else privacy(options)}
    record(rec)
    put = call("PUT", upload, data=Path(video).read_bytes(), timeout=600,
               headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{size - 1}/{size}"})
    if put.get("_http") and not 200 <= put["_http"] < 300:   # refused: TikTok has no file, so a retry is safe
        return dict(rec, status="FAILED", fail_reason=f"upload HTTP {put['_http']}")
    status, reason = poll(pid, token, call, sleep)
    return dict(rec, status=status or "UPLOADING", fail_reason=reason if status == "FAILED" else None)


def recheck(tiktok, token, now, call=http):
    """Follow posts left unfinished by an earlier run through their publish_id; never re-initialize them."""
    changed = []
    for key, rec in tiktok.get("posts", {}).items():
        if rec.get("status") in FINAL | {"FAILED"} or not rec.get("publish_id"):
            continue
        status, reason = fetch(rec["publish_id"], token, call)
        if status in DONE or status == "FAILED":
            rec.update(status=status, fail_reason=reason)
        elif parse(rec.get("at")) and now - parse(rec["at"]) > timedelta(hours=RECHECK_HOURS):
            rec.update(status="FAILED", fail_reason=f"not finished after {RECHECK_HOURS} h (last {status})")
        else:
            continue
        changed.append(key)
    return changed


def settle(rec, previous):
    """Count failures; after MAX_FAILURES the Short is FAILED_FINAL (reported, skipped)."""
    if rec.get("status") == "FAILED":
        rec["failures"] = (previous or {}).get("failures", 0) + 1
        if rec["failures"] >= MAX_FAILURES:
            rec["status"] = "FAILED_FINAL"
    return rec


def main(cmd, ledger_path, tiktok_path, episodes_dir, video_dir=None):
    ledger = json.loads(Path(ledger_path).read_text())
    tpath = Path(tiktok_path)
    tiktok = json.loads(tpath.read_text()) if tpath.exists() else {"version": "tiktok-ledger-v1", "posts": {}}
    posts = tiktok.setdefault("posts", {})
    now = now_utc()
    todo = pending(ledger, tiktok, episodes_dir, now)
    if cmd == "pending":
        for key, ep in todo:
            print(key, asset_name(ep))
        return 0
    mode = os.environ.get("TIKTOK_MODE", "inbox")
    if mode not in ("inbox", "direct"):
        raise SystemExit(f"TIKTOK_MODE {mode}")
    open_posts = [k for k, r in posts.items() if r.get("status") not in FINAL | {"FAILED"} and r.get("publish_id")]
    if not todo and not open_posts:
        print(json.dumps({"tiktok": "NOTHING_PENDING"}))
        return 0

    def save():
        tpath.write_text(json.dumps(tiktok, indent=1) + "\n")

    token, rotated = refresh()
    if rotated:
        store_refresh_token(rotated)
    for key in recheck(tiktok, token, now):
        settle(posts[key], dict(posts[key], failures=posts[key].get("failures", 0)))
        print(json.dumps({"key": key, "rechecked": posts[key]["status"]}))
    save()
    rc = 0
    for key, ep in todo[:PER_RUN]:
        previous = posts.get(key)
        base = {"youtube_video_id": ledger["entries"][key]["video_id"], "at": now.isoformat()}

        def record(rec, key=key, base=base):
            posts[key] = dict(rec, **base, failures=(previous or {}).get("failures", 0))
            save()
        result = settle(dict(post(ep, Path(video_dir) / asset_name(ep), token, mode, record), **base), previous)
        posts[key] = result
        save()
        print(json.dumps({"key": key, **result}))
        rc = 1 if result["status"] in ("FAILED", "FAILED_FINAL") else rc
    final = sorted(k for k, r in posts.items() if r.get("status") == "FAILED_FINAL")
    if final:
        print(json.dumps({"tiktok_failed_final": final}))   # the owner decides; the queue moves on
    return rc


if __name__ == "__main__":
    if len(sys.argv) not in (5, 6) or sys.argv[1] not in ("pending", "post"):
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:]))
