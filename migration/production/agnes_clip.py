#!/usr/bin/env python3
"""One AI clip from Agnes Video 2.5 Flash (owner, 2026-10-25: "this video AI is very good"), TEST ONLY until its terms
are confirmed for commercial use and its free output is checked for a watermark.

Agnes AI API (free Flash tier, 720p, 4-12 s): POST {API}/videos creates a task, GET {API_ROOT}/agnesapi?video_id=...
&model_name=... is polled until completed or failed, then the MP4 is downloaded. The key comes only from AGNES_API_KEY
(a repository secret) and is never printed. A full free queue (HTTP 503 video_queue_full) is retried with backoff.
Nothing here publishes: the workflow keeps the clip as a run artifact for Claude's review (clip_check.py + frames).
Modes: text (prompt only) or keyframe (a first frame, e.g. an approved FLUX still from our public release, put in
motion by the prompt; Flash takes first_frame/last_frame URLs, 720P only).
Reference mode keeps a character the same in every clip: the approved reference images of the characters named
(characters/characters.py, at most 5) go in `images`, and the prompt must carry each character's look word for word.
usage: agnes_clip.py PROMPT_FILE OUT.mp4 [SECONDS] [ASPECT] [FIRST_FRAME_URL] [CHARACTER_IDS]
"""
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://apihub.agnes-ai.com"
API = API_ROOT + "/v1"
MODEL = "agnes-video-2.5-flash"
QUEUE_TRIES = 8            # 503 video_queue_full: retry the create call with growing waits
POLL_TRIES = 120           # x POLL_S: up to 20 minutes for one clip
POLL_S = 10


def http(method, url, key, body=None, timeout=120):
    h = {"Authorization": f"Bearer {key}"}
    data = None
    if body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, code = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    except OSError as e:
        return {"_http": 0, "_net": type(e).__name__}
    try:
        out = json.loads(raw or b"{}")
    except ValueError:
        out = {"_raw": raw[:200].decode("utf-8", "replace")}
    return dict(out, _http=code) if isinstance(out, dict) else {"_http": code, "_body": out}


def find(obj, pred):
    """First value anywhere in a JSON reply for which pred(key, value) holds (the reply shape is not fixed)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if pred(k, v):
                return v
            got = find(v, pred)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = find(v, pred)
            if got is not None:
                return got
    return None


def task_id(reply):
    return find(reply, lambda k, v: k in ("video_id", "id", "task_id") and isinstance(v, str) and v)


def status_of(reply):
    s = find(reply, lambda k, v: k == "status" and isinstance(v, str))
    return (s or "").lower()


def mp4_url(reply):
    return find(reply, lambda k, v: isinstance(v, str) and v.startswith("http") and
                (".mp4" in v or k in ("video_url", "url", "download_url", "output")))


OWN_FRAMES = "https://github.com/matheusmagah-cpu/heroverse-engine/releases/download/"


def create(prompt, key, seconds="6", aspect="9:16", first_frame=None, references=None, call=http, sleep=time.sleep):
    body = {"model": MODEL, "mode": "text", "prompt": prompt, "size": "720P", "aspect_ratio": aspect,
            "seconds": str(seconds), "n": 1}
    if first_frame:
        if not first_frame.startswith(OWN_FRAMES):   # only our own approved stills are put in motion
            raise SystemExit("FIRST_FRAME_NOT_OURS")
        body.update(mode="keyframe", first_frame=first_frame)
    elif references:
        if not all(u.startswith(OWN_FRAMES) for u in references):
            raise SystemExit("REFERENCE_NOT_OURS")
        body.update(mode="reference", images=list(references)[:5])
    for i in range(QUEUE_TRIES):
        r = call("POST", API + "/videos", key, body)
        vid = task_id(r)
        if r.get("_http") == 200 and vid:
            return vid
        if r.get("_http") in (0, 429, 503):      # full free queue or a lost connection: wait and try again
            sleep(min(30 * 2 ** i, 300))
            continue
        raise SystemExit(f"AGNES_CREATE HTTP {r.get('_http')} {json.dumps(r.get('error') or r)[:300]}")
    raise SystemExit("AGNES_QUEUE_FULL (free queue busy; try again later)")


def wait(vid, key, call=http, sleep=time.sleep):
    q = urllib.parse.urlencode({"video_id": vid, "model_name": MODEL})
    for _ in range(POLL_TRIES):
        r = call("GET", f"{API_ROOT}/agnesapi?{q}", key)
        s = status_of(r)
        if s in ("completed", "succeeded", "success"):
            url = mp4_url(r)
            if not url:
                raise SystemExit(f"AGNES_NO_VIDEO_URL {json.dumps(r)[:300]}")
            return url, r
        if s in ("failed", "error", "cancelled"):
            raise SystemExit(f"AGNES_FAILED {json.dumps(r)[:300]}")
        sleep(POLL_S)
    raise SystemExit("AGNES_TIMEOUT")


def main(prompt_file, out, seconds="6", aspect="9:16", first_frame=None, character_ids=""):
    key = os.environ.get("AGNES_API_KEY")
    if not key:
        raise SystemExit("AGNES_API_KEY_MISSING")
    prompt = Path(prompt_file).read_text().strip()
    refs = None
    ids = [c for c in (character_ids or "").split(",") if c]
    if ids:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "characters"))
        import characters
        found = characters.problems([{"prompt": prompt, "characters": ids}])
        if found:
            raise SystemExit("; ".join(found))
        refs = characters.reference_urls(ids)
        if not refs:
            raise SystemExit("CHARACTER_REFERENCES_MISSING (generate the reference sheet first)")
    vid = create(prompt, key, seconds, aspect, first_frame or None, refs)
    url, reply = wait(vid, key)
    with urllib.request.urlopen(urllib.request.Request(url), timeout=300) as r:
        Path(out).write_bytes(r.read())
    meta = {k: v for k, v in reply.items() if not k.startswith("_") and "key" not in k.lower()}
    print(json.dumps({"agnes": "DOWNLOADED", "task": vid, "bytes": Path(out).stat().st_size, "reply": meta})[:2000])
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4, 5, 6, 7):
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:]))
