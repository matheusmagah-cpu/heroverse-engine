#!/usr/bin/env python3
"""The nightly queue: which pilots need images, and which one to render next.

A pilot is due when its schedule.json opens within HORIZON hours and it is not
yet on YouTube. It needs images while any image its script uses has no
images/<id>.json record; it needs a render when its images are complete and no
completed frozen-v3 render exists for the current script and matching output hash.
A completed v3 QA FAIL is not rerendered repeatedly; it awaits an input correction.
usage: render_queue.py PRODUCTION_DIR LEDGER {images|render|reconcile|review} [HOURS]
  review: prints "PILOT SHA256" for every due render with QA PASS and no Claude review for that hash
  images: prints "PILOT id,id,..." for every pilot with images still missing
  reassign: prints "PILOT clip,clip,..." for every unrendered pilot whose footage the library no longer approves (E78);
            preview and render skip such a pilot until assign.py reassigns it
  render: prints the next pilot to render (earliest publish time) or nothing
  stale: prints "STALE PILOT PUBLISH_AT" for pilots whose slot passed more than 6 h ago (within STALE_DAYS) and that
         have no video on YouTube: due() no longer sees them, so they must be rescheduled (E49)
  reconcile: prints "approve PILOT" (QA PASS, no approval, review missing or ERROR, or final decision UNKNOWN),
  "shorts PILOT" (Shorts inputs handed off, Shorts never made) and
             "publish PILOT" (approved for this file, not on YouTube) so failed steps are retried, and
             "comment PILOT" (on YouTube, public by its schedule, first comment still PENDING: E61)
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "publish"))
from shorts_prerequisite import ready as shorts_ready
sys.path.insert(0, str(Path(__file__).resolve().parent))  # E73: python3 -I does not add the script's own directory
import preview_gate  # noqa: E402


def when(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def needed_images(d, script):
    spec = json.loads((d / "images.json").read_text()) if (d / "images.json").exists() else {"images": []}
    ids = {i["id"] for i in spec["images"]} | set(script["backgrounds"]) | {script["figure"], script["overlay"]["title_image"]}
    return sorted(i for i in ids if not (d / "images" / f"{i}.json").exists())


STANDARD_QA = "pilot-qa-criteria-v3"  # migration/STANDARD.md v1: the only renders that may be approved or published
# v4 (owner, 2026-10-23: licensed real footage) is the same standard with the footage grammar; both may publish
STANDARD_QAS = {"pilot-qa-criteria-v3": "4851878674101c7a64816815e9514786a2a7e0576d35b8bdf670ab7053c2e2b3",
                "pilot-qa-criteria-v4": "36f2d648d2f37f44781d4ccbee0cd775fd01a5010357cc3bb3478daaafe86b11",
                "story-qa-criteria-v1": "5dcf63f92fc716852096cefa8fd48f7498f4733eb1d347f4212a6f31a6c95360"}

STANDARD_QA_SHA256 = "4851878674101c7a64816815e9514786a2a7e0576d35b8bdf670ab7053c2e2b3"


def object_or_empty(path):
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def current_render(manifest, qa, script_sha):
    """Completed current render, not a publication verdict. FAIL must not loop."""
    if not isinstance(manifest, dict) or not isinstance(qa, dict):
        return False
    output = manifest.get("output_sha256")
    return (isinstance(output, str) and re.fullmatch(r"[0-9a-f]{64}", output) is not None
            and manifest.get("script_sha256") == script_sha
            and qa.get("output_sha256") == output
            and qa.get("criteria_version") in STANDARD_QAS
            and qa.get("criteria_sha256") == STANDARD_QAS[qa.get("criteria_version")]
            and qa.get("status") in ("PASS", "FAIL"))


def unvetted_footage(production, script):
    """E78: footage the script still lists but the shared library no longer approves (rejected after assignment, or
    gone), so a preview or render never shows a clip Claude already turned down."""
    lib = Path(production) / "footage" / "library"
    out = []
    for c in script.get("footage") or []:
        rec = object_or_empty(lib / f"{c}.json")
        if rec.get("vetting") != "APPROVED":
            out.append(c)
    return out


def next_render(rows):
    """The one rule for the next full render, shared by the queue, the runner wake and the engine fallback (E78: two
    copies of it missed the footage check): images complete, footage vetted, not rendered, preview at the floor."""
    return next((r for r in rows if not r["missing_images"] and not r["unvetted_footage"] and not r["rendered"]
                 and r["preview_ok"]), None)


def due(production, ledger, now, hours):
    entries = ledger.get("entries", {})
    out = []
    for d in sorted(Path(production).glob("pilot-[0-9][0-9][0-9]")):
        if not (d / "schedule.json").exists() or not (d / "script.json").exists():
            continue
        t = when(json.loads((d / "schedule.json").read_text())["publish_at"])
        if not now - timedelta(hours=6) <= t <= now + timedelta(hours=hours):
            continue
        manifest = d / "out" / "manifest.json"
        m = object_or_empty(manifest)
        if m and "video_id" in entries.get(f"{d.name}:{m.get('output_sha256')}", {}):
            continue  # already on YouTube
        script_sha = hashlib.sha256((d / "script.json").read_bytes()).hexdigest()
        script = json.loads((d / "script.json").read_text())
        out.append({"pilot": d.name, "publish_at": t, "missing_images": needed_images(d, script),
                    "unvetted_footage": unvetted_footage(production, script),
                    "rendered": current_render(m, object_or_empty(d / "out" / "qa.json"), script_sha),
                    "preview_ok": preview_gate.approved(d)})
    return sorted(out, key=lambda x: x["publish_at"])


STALE_DAYS = 7
COMMENT_DAYS = 7  # a first comment is retried for a week after the video goes public


def pending_comments(production, ledger, now):
    """E61: the first comment is refused while a video is still scheduled (HTTP 403), and nothing retried it once the
    video was public: 006, 007 and 010 kept "PENDING" for days. Pilots on YouTube whose slot passed (and is at most
    COMMENT_DAYS old) with a PENDING first comment are retried by first-comment.yml."""
    out = []
    for key, entry in sorted(ledger.get("entries", {}).items()):
        pilot = key.split(":", 1)[0]
        comment = (entry.get("steps") or {}).get("first_comment")
        if not re.fullmatch(r"pilot-\d{3}", pilot) or not entry.get("video_id"):
            continue
        if not (isinstance(comment, str) and comment.startswith("PENDING")):
            continue
        sched = Path(production) / pilot / "schedule.json"
        try:
            public = when(json.loads(sched.read_text())["publish_at"])
        except (FileNotFoundError, ValueError, KeyError):
            continue
        if public + timedelta(minutes=10) <= now <= public + timedelta(days=COMMENT_DAYS) and pilot not in out:
            out.append(pilot)
    return out


def pending_episode_comments(production, ledger, now):
    """E70: Bible-series episodes publish through publish-episode.yml; a scheduled one refuses its first comment (HTTP 403)
    like the pilots did (E61), and nothing retried it. Episodes whose slot (or upload, when published at once) passed
    10 minutes to COMMENT_DAYS ago with a PENDING first comment are re-run; the publisher is idempotent."""
    out = []
    for key, entry in sorted(ledger.get("entries", {}).items()):
        kind, _, rest = key.partition(":")
        comment = (entry.get("steps") or {}).get("first_comment")
        if kind != "bible" or not entry.get("video_id") or not (isinstance(comment, str) and comment.startswith("PENDING")):
            continue
        episode = rest.split(":", 1)[0]
        try:
            ep = json.loads((Path(production) / "bible" / "episodes" / f"{episode}.json").read_text())
            public = when(ep.get("slot") or entry["uploaded_at"])
        except (FileNotFoundError, ValueError, KeyError):
            continue
        if public + timedelta(minutes=10) <= now <= public + timedelta(days=COMMENT_DAYS) and episode not in out:
            out.append(episode)
    return out


def stale(production, ledger, now, days=STALE_DAYS):
    """E49: pilot-008..011 left the queue silently once their slot was more than 6 h old (the reviewer returned 503
    and two renders failed QA), and nothing reported it for a day. Any ledger entry with a video_id for the pilot
    counts as published, whichever render it came from."""
    entries = ledger.get("entries", {})
    out = []
    for d in sorted(Path(production).glob("pilot-[0-9][0-9][0-9]")):
        if not (d / "schedule.json").exists() or not (d / "script.json").exists():
            continue
        t = when(json.loads((d / "schedule.json").read_text())["publish_at"])
        if not now - timedelta(days=days) <= t < now - timedelta(hours=6):
            continue
        if any(k.split(":", 1)[0] == d.name and "video_id" in v for k, v in entries.items()):
            continue
        qa = object_or_empty(d / "out" / "qa.json")
        if qa and qa.get("criteria_version") not in STANDARD_QAS:
            continue  # rendered before migration/STANDARD.md: retired, never published (pilot-003)
        out.append({"pilot": d.name, "publish_at": t})
    return out


def reviewed_shorts(path):
    """True when Shorts exist and at least one got a verdict (PASS or FAIL) from the watched review; Shorts left
    unreviewed (provider quota or error, NOT_REVIEWED_*) are made again."""
    if not path.exists():
        return False
    return any((s.get("review") or {}).get("status") in ("PASS", "FAIL") for s in json.loads(path.read_text())["shorts"])


HOLD = Path(__file__).resolve().parents[1] / "ops" / "PUBLICATION_HOLD"
# while present, the runner renders nothing (e.g. scripts are being moved to a new standard: a render of the old
# script would only be thrown away and would hold the single runner for ~2 h)
RENDER_HOLD = Path(__file__).resolve().parents[1] / "ops" / "RENDER_HOLD"
RETRY_AFTER = timedelta(minutes=30)


def quota_spent(rev, now):
    """True while a retry would only hit the same quota again. E29: only a quota the provider names as per day
    (quotaId containing "PerDay") waits for the 07:00 UTC reset; a per-minute or unnamed quota waits RETRY_AFTER,
    never a whole day (pilot-003 waited 5 h on 2026-10-19 while pilot-004 was approved on the same quota)."""
    if rev.get("status") != "ERROR" or "QUOTA" not in str(rev.get("error", "")) or not rev.get("failed_at"):
        return False
    failed = datetime.fromisoformat(rev["failed_at"].replace("Z", "+00:00"))
    if any("PerDay" in q for q in rev.get("quota_ids") or []):
        reset = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if now < reset:
            reset -= timedelta(days=1)
        return failed >= reset
    return now - failed < RETRY_AFTER


def main(production, ledger_path, mode, hours="48"):
    ledger = json.loads(Path(ledger_path).read_text()) if Path(ledger_path).exists() else {}
    now = datetime.now(timezone.utc)
    rows = due(production, ledger, now, int(hours))
    if mode == "stale":
        for r in stale(production, ledger, now):
            print("STALE", r["pilot"], r["publish_at"].strftime("%Y-%m-%dT%H:%M:%SZ"))
    elif mode == "images":  # "PILOT id,id": only the images still missing (never regenerate a recorded one)
        for r in rows:
            if r["missing_images"]:
                print(r["pilot"], ",".join(r["missing_images"]))
    elif mode == "preview":
        # a script with no current render and no preview of itself gets the ~15 min preview first (one at a time)
        nxt = next((r for r in rows if not r["missing_images"] and not r["unvetted_footage"] and not r["rendered"]
                    and not r["preview_ok"] and not preview_gate.previewed(Path(production) / r["pilot"])), None)
        if nxt:
            print(nxt["pilot"])
    elif mode == "reassign":
        for r in rows:
            if r["unvetted_footage"] and not r["rendered"]:
                print(r["pilot"], ",".join(r["unvetted_footage"]))
    elif mode == "preview-review":
        # Claude reviews every preview of a current script that has no review for that script yet
        for r in rows:
            d = Path(production) / r["pilot"]
            if not r["rendered"] and preview_gate.previewed(d) and not preview_gate.review(d):
                print(r["pilot"], preview_gate.script_sha(d))
    elif mode == "review":
        # the designated reviewer (Claude) reviews every due render that passed QA and has no review for its hash
        for r in rows:
            d = Path(production) / r["pilot"]
            qa = object_or_empty(d / "out" / "qa.json")
            cr = object_or_empty(d / "inspection" / "claude_review.json")
            if r["rendered"] and qa.get("status") == "PASS" and cr.get("output_sha256") != qa.get("output_sha256"):
                print(r["pilot"], qa.get("output_sha256"))
    elif mode == "reconcile" and HOLD.exists():
        print("PUBLICATION_HOLD", file=sys.stderr)  # owner pause: no approval, publication or Shorts is dispatched
    elif mode == "reconcile":
        # E25: approve.yml keeps ONE pending run (concurrency group): dispatching several approvals cancels all but the
        # last, i.e. the farthest slot. So only the earliest due approval is sent, and Shorts wait until no approval is
        # pending, because both spend the same free Gemini quota and the long video publishes first.
        approve, publish, shorts = [], [], []
        long_quota_pending = False
        for r in rows:
            d = Path(production) / r["pilot"]
            try:
                qa = json.loads((d / "out" / "qa.json").read_text())
            except (FileNotFoundError, ValueError):
                continue
            if not r["rendered"] or qa.get("status") != "PASS":
                continue
            if qa.get("criteria_version") not in STANDARD_QAS:
                continue  # renders made before migration/STANDARD.md (owner: "amateur") are never approved or published
            ap = json.loads((d / "inspection" / "APPROVAL.json").read_text()) if (d / "inspection" / "APPROVAL.json").exists() else {}
            rev = json.loads((d / "out" / "review.json").read_text()) if (d / "out" / "review.json").exists() else {}
            gate = json.loads((d / "out" / "gate.json").read_text()) if (d / "out" / "gate.json").exists() else {}
            unknown = gate.get("output_sha256") == qa["output_sha256"] and gate.get("decision") == "UNKNOWN"
            if ap.get("approved") and ap.get("output_sha256") == qa["output_sha256"]:
                publish.append(r["pilot"])  # due rows are never already on YouTube
            elif rev.get("status") == "AWAITING_REVIEW" and rev.get("output_sha256") == qa["output_sha256"]:
                pass  # waits for the Claude review (render_queue.py review lists it); approve.yml starts when it lands
            elif quota_spent(rev, now):
                long_quota_pending = True  # reserve shared review quota for the waiting long
            elif rev.get("output_sha256") != qa["output_sha256"] or rev.get("status") == "ERROR" or unknown:
                approve.append(r["pilot"])
            # Shorts handed off by the render but never made (provider quota or error): made again
            if (d / "shorts" / "inputs.json").exists() and not reviewed_shorts(d / "shorts" / "shorts.json") and shorts_ready(d):
                shorts.append(r["pilot"])
        for p in publish:
            print("publish", p)
        comments = pending_comments(production, ledger, now)
        if comments:  # first-comment.yml shares the publish concurrency group: one at a time, like approvals (E25)
            print("comment", comments[0])
        episodes = pending_episode_comments(production, ledger, now)
        if episodes and not comments:
            print("episode", episodes[0])
        if approve:
            print("approve", approve[0])  # rows are sorted by publish time: the earliest slot first
        elif not long_quota_pending:
            for p in shorts:
                print("shorts", p)
    elif RENDER_HOLD.exists():
        print("RENDER_HOLD", file=sys.stderr)
    else:
        # owner, 2026-10-24: only a script whose preview reached 9.5 is rendered in full (preview_gate.py)
        nxt = next_render(rows)
        if nxt:
            print(nxt["pilot"])


if __name__ == "__main__":
    main(*sys.argv[1:5])
