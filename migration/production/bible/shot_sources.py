#!/usr/bin/env python3
"""Where each shot's picture comes from, so a video is produced without stalling (owner, 27/10 ~22:50 UTC, for the
long and the Shorts, "em qualquer situação"; story QA v4 rights.fallback_sources):

  R1 pavo_reuse   every Pavo clip already made for a shot is used before anything is generated: an approved clip, a
                  clean clip in a shot-probe record (committed, or still on its claude/shot-probe-<episode>-<run>
                  branch: it is awaiting review, never queued again) or a clean clip of a clip inventory, matched by
                  the shot and its request sha256, adopted by its content hash;
  R2 pavo         the day's free Pavo budget (quota.py, the shared budget of #475) goes first to the spoken shots
                  (risk_order: characters and the Keeper speaking, then the voice-overs), then to the rest;
  R3 footage      a non-spoken shot with no character that the budget does not reach is filled from the vetted
     still_motion licensed library (Pixabay / Wikimedia... under the frozen licence list, APPROVED, seen by Claude,
                  2560x1440, no person) or from an APPROVED scene still (FLUX on Workers AI, free) in camera motion,
                  whichever shows what its line says;
  a spoken shot, and a shot with a character (its canonical look needs its references), waits for the budget
  (WAIT_PAVO_BUDGET): neither has a free source that keeps the 9.5 floor.

Nothing here approves anything. Each candidate goes through Claude's review: `approve-shot` for a probed or adopted
clip, `approve-source` (below) for a library clip, a still in motion or an inventory clip, each with a score >= 9.5 and
a note, by PR. The approval records the shot's `source`, and the build ships exactly that (episode_build.generate_step,
long_build.upscale_step), the manifest naming it per shot.

usage:
  episode_build.py sources PLAN [--write]   the per-shot source plan for today's budget (evidence/sources/<ep>.json)
  episode_build.py approve-source PLAN SHOT SOURCE ITEM SCORE NOTE
        SOURCE footage (ITEM a library clip id), still_motion (ITEM an APPROVED still id of this shot) or pavo_reuse
        (ITEM <inventory.json path>#<clip sha256>)
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for _p in (HERE, REPO / "migration" / "production" / "characters", REPO / "migration" / "production" / "footage",
           REPO / "migration" / "integrations" / "pavo", REPO / "migration" / "production"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SOURCES = ("pavo_reuse", "pavo", "footage", "still_motion")
FALLBACKS = ("footage", "still_motion")
LIBRARY = REPO / "migration" / "production" / "footage" / "library"
RECORDS = REPO / "migration" / "evidence" / "shots"
INVENTORIES = REPO / "migration" / "evidence" / "pavo"
SOURCES_DIR = REPO / "migration" / "evidence" / "sources"
REVIEW_MIN = 9.5
FRAME = (2560, 1440)
SHORT_FRAME = (1080, 1920)
CDN = re.compile(r"^https://cos-aigc-default\.agnes-ai\.space/[A-Za-z0-9_./%+-]+\.mp4$")
STOP = {"a", "an", "the", "and", "of", "to", "in", "on", "at", "his", "her", "its", "their", "with", "from", "by",
        "is", "are", "was", "be", "it", "this", "that", "for", "as", "into", "over", "under", "no", "not", "one", "all",
        "shot", "camera", "slow", "wide", "close", "up", "light", "painterly", "cinematic", "realism", "grain", "film"}


MAX_STILL_CLIP_SECONDS = 12     # plan_check.SCENE_SECONDS[1]: a still in motion for a shot that names no seconds
PAVO_STILL_LICENCE = "Pavo generated (owner-owned)"   # story QA v4 rights.ai_video.licence


def still_licence(rec):
    """The licence a still carries: a FLUX still its model's (apache-2.0), a Pavo agnes-image still Pavo's (owner-owned
    output). `source` is the engine's name (a string) or a {license, revision} record."""
    src = (rec or {}).get("source")
    if isinstance(src, dict):
        return src.get("license") or "apache-2.0"
    if str(src or "").startswith("pavo") or (rec or {}).get("pavo"):
        return PAVO_STILL_LICENCE
    return "apache-2.0"


def words(text):
    return [w for w in re.findall(r"[a-z]+", str(text or "").lower()) if w not in STOP and len(w) > 2]


# ---------- R1: every clip already made ----------

def clean(clip):
    """A clip that passed the build's checks where it was made: explicit empty flags (a probe record), or an inventory
    entry whose recorded checks are all empty."""
    if "flags" in clip:
        return clip["flags"] == []
    checks = [clip.get(k) for k in ("lipsync_check", "clip_check", "checks") if k in clip]
    return bool(checks) and all(c == [] for c in checks)


def committed_clips(plan, records=RECORDS, inventories=INVENTORIES, approvals=None):
    """{shot id: [clip]} of every clean clip made for this plan's shots that main holds: approvals, committed
    shot-probe records and clip inventories. Each clip: {request_sha256, clip_sha256, from, asset | url}."""
    import episode_build as eb
    ep = plan.get("episode")
    out = {}
    approvals = eb.load_approvals(plan) if approvals is None else approvals
    for sid, a in approvals.items():
        out.setdefault(sid, []).append({"request_sha256": a.get("request_sha256"), "clip_sha256": a.get("clip_sha256"),
                                        "asset": a.get("asset"), "from": "approved"})
    folder = Path(records) / str(ep)
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        out = merge(out, record_clips(json.loads(path.read_text()), str(path.relative_to(REPO))
                                      if REPO in path.parents else str(path)))
    for path in sorted(Path(inventories).rglob("inventory.json")) if Path(inventories).is_dir() else []:
        inv = json.loads(path.read_text())
        if not str(inv.get("plan", "")).endswith(f"/{ep}.json"):
            continue
        for row in inv.get("shots") or []:
            for c in row.get("clips") or []:
                if clean(c) and c.get("same_request") is not False:
                    out.setdefault(row["shot"], []).append({
                        "request_sha256": row.get("request_sha256"), "clip_sha256": c.get("sha256"),
                        "url": c.get("url"), "seconds": c.get("seconds"),
                        "from": f"{path.relative_to(REPO) if REPO in path.parents else path}#{c.get('sha256')}"})
    return out


def record_clips(record, where):
    out = {}
    for sid, entry in (record.get("shots") or {}).items():
        for c in entry.get("clips") or []:
            if c.get("asset") and clean(c):
                out.setdefault(sid, []).append({"request_sha256": entry.get("request_sha256"),
                                                "clip_sha256": c.get("clip_sha256"), "asset": c["asset"],
                                                "uploaded": c.get("uploaded"), "from": where})
    return out


def merge(a, b):
    for k, v in b.items():
        a.setdefault(k, []).extend(v)
    return a


def branch_clips(plan, repo=REPO, run=subprocess.run):
    """Clean clips in shot-probe records still on their claude/shot-probe-<episode>-<run> branch (the local origin
    refs; fetch first): made and uploaded, awaiting Claude's review and approve-shot. Unreadable git: {} (the queue
    then may only miss a reuse, never generate in its place: the queue says so)."""
    import quota
    ep = plan.get("episode")
    try:
        refs = run(["git", "-C", str(repo), "for-each-ref", "--format=%(refname:lstrip=3)",
                    "refs/remotes/origin/claude/"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if refs.returncode:
        return None
    out = {}
    for branch in refs.stdout.split():
        m = quota.PROBE_BRANCH.fullmatch(branch)
        if not m or m.group(1) != ep:
            continue
        shown = run(["git", "-C", str(repo), "show", f"origin/{branch}:{quota.probe_record_path(branch)}"],
                    capture_output=True, text=True, timeout=30)
        if shown.returncode == 0:
            try:
                out = merge(out, record_clips(json.loads(shown.stdout), branch))
            except ValueError:
                continue
    return out


_CACHE = {}


def clean_clip(plan, shot_id, request_sha256):
    """True when main holds a clean clip of this shot made from exactly this request (R1: reused, never generated
    again). Read once per process and episode."""
    key = plan.get("episode")
    if key not in _CACHE:
        _CACHE[key] = committed_clips(plan)
    return any(c.get("request_sha256") == request_sha256 for c in _CACHE[key].get(shot_id, []))


def awaiting_review(plan, digests, approvals, branch=None):
    """{shot id: [clip]}: shots with no approval of their request now but a clean clip of it already made (main's
    records and inventories, plus `branch`: the shot-probe branches). They are reviewed, never probed again (R1)."""
    found = committed_clips(plan, approvals={})
    if branch:
        found = merge(found, branch)
    out = {}
    for sid, clips in found.items():
        a = approvals.get(sid)
        if a and a.get("request_sha256") == digests.get(sid):
            continue
        same = [c for c in clips if c.get("request_sha256") == digests.get(sid) and c.get("from") != "approved"]
        if same:
            out[sid] = same
    return out


# ---------- R2 / R3: the day's budget, spoken shots first, free fallbacks for the rest ----------

def budget_remaining(guard=None):
    """(units left today, why): the shared free-model budget (quota.QuotaGuard with the Actions records); a stop or an
    unreadable budget is 0, never a guess."""
    import quota
    guard = guard or quota.QuotaGuard(actions=quota.git_actions_usage)
    try:
        fits = guard.check_batch(0)
        return fits["remaining"], f"{fits['used']} of {fits['cap']} units used today"
    except quota.PavoError as exc:
        return 0, str(exc)


def has_character(shot):
    return bool(shot.get("characters")) or shot.get("kind") == "keeper"


def shown_characters(shot):
    return ["keeper"] if shot.get("kind") == "keeper" else list(shot.get("characters") or [])


def owner_exception(plan):
    """The owner's arc-01 exception (qa_criteria_story_v4_owner_exception_arc01.json, bound to its plan)."""
    import long_plan_check
    return long_plan_check.owner_exception(plan)


def character_still_problems(shot, rec, chars=None):
    """Owner exception: a still that shows characters was made by Pavo agnes-image with exactly the approved
    reference images of every character the shot shows (by sha256), Pavo's read-back proving that many inputs."""
    import episode_build as eb
    import plan_check
    need = []
    for cid in shown_characters(shot):
        try:
            need += [m.get("sha256") for _, m in eb.reference_records(cid, chars)]
        except SystemExit as exc:
            return [str(exc)]
    sent = [r.get("sha256") for r in (rec or {}).get("references") or [] if isinstance(r, dict)]
    if not need or sorted(sent) != sorted(need):
        return [f"made without exactly the approved references of {shown_characters(shot)}"]
    return plan_check.pavo_proof_problems((rec or {}).get("pavo"), len(need))


def fallback_refusal(plan, shot, index, source, still=None):
    """Why a free fallback may not carry this shot, or None. v4: a spoken shot or a shot with a character never
    (SOURCE_SPOKEN_SHOT, SOURCE_CHARACTER_SHOT). The owner's arc-01 exception: a spoken shot on the Kokoro voice
    (plan B) and a shot with characters, as a still in motion made with their references (SOURCE_CHARACTER_STILL)."""
    import pavo_native
    exc = owner_exception(plan)
    if pavo_native.spoken(shot) and not (exc and source == "still_motion"
                                         and pavo_native.route(plan, shot, index) == pavo_native.KOKORO):
        return f"SOURCE_SPOKEN_SHOT {shot['id']} (a spoken shot is always Pavo: R2)"
    if has_character(shot):
        if not exc or source != "still_motion":
            return f"SOURCE_CHARACTER_SHOT {shot['id']} (a character's canonical look needs its references)"
        if still is not None:
            bad = character_still_problems(shot, still)
            if bad:
                return f"SOURCE_CHARACTER_STILL {shot['id']} " + "; ".join(bad)
    return None


REUSE_MOTION = "pull_out"
REUSE_KEEPER_MOTION = "static_crop"


def still_owner(shot):
    """The shot whose APPROVED still this shot shows: its own, or the one its `still_of` names (owner exception)."""
    return shot.get("still_of") or shot.get("id")


def still_of_problems(plan, timeline=None):
    """Owner exception (arc-01 long, 28/10 contingency): a character shot may show the APPROVED still of another shot of
    the plan (`still_of`: that shot's id) instead of a new Pavo still, rendered with another camera move
    (REUSE_MOTION). Nothing in the frozen QA moves: the still keeps its references and Pavo read-back
    (character_still_problems on the shot that shows it), and every shot showing one still is at least story QA's
    image_repeat_gap_seconds_min from every other (E139: a picture is its sha256). Rows: STILL_OF_OUTSIDE_EXCEPTION,
    STILL_OF_UNKNOWN, STILL_OF_CHAIN, STILL_OF_CHARACTERS, STILL_OF_REFUSED (a shot a fallback still may not carry),
    STILL_OF_GAP."""
    import long_plan_check as lpc
    shots = plan.get("shots") or []
    users = [s for s in shots if isinstance(s, dict) and s.get("still_of") is not None]
    if not users:
        return []
    if not owner_exception(plan):
        return [f"STILL_OF_OUTSIDE_EXCEPTION {s.get('id')} (a reused still is the owner's arc-01 exception only)"
                for s in users]
    index = {s.get("id"): i for i, s in enumerate(shots)}
    out, groups = [], {}
    for s in users:
        src = s["still_of"]
        if src not in index or src == s.get("id") or shots[index[src]].get("window_of") is not None:
            out.append(f"STILL_OF_UNKNOWN {s.get('id')} ({src!r}: another generated shot of the plan)")
            continue
        if shots[index[src]].get("still_of") is not None:
            out.append(f"STILL_OF_CHAIN {s.get('id')} ({src} itself shows {shots[index[src]]['still_of']}'s still)")
            continue
        if sorted(shown_characters(s)) != sorted(shown_characters(shots[index[src]])) or not has_character(s):
            out.append(f"STILL_OF_CHARACTERS {s.get('id')} (shows {shown_characters(s)}, {src}'s still shows "
                       f"{shown_characters(shots[index[src]])}: the same characters, by their references)")
            continue
        why = fallback_refusal(plan, s, index[s["id"]], "still_motion")
        if why:
            out.append(f"STILL_OF_REFUSED {why}")
            continue
        groups.setdefault(src, [src]).append(s["id"])
    if not groups:
        return out
    tl = timeline or lpc.timeline(plan)
    gap = (lpc.qa_for(plan) or lpc.qa())["grammar"]["image_repeat_gap_seconds_min"]
    at = {s["id"]: (tl["begin"][i], tl["end"][i]) for i, s in enumerate(shots)}
    for src, ids in sorted(groups.items()):
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                x, y = at[ids[a]], at[ids[b]]
                apart = max(y[0] - x[1], x[0] - y[1])
                if apart < gap:
                    out.append(f"STILL_OF_GAP {ids[b]} ({src}'s still also on {ids[a]}, {apart:.1f} s apart < story "
                               f"QA's image_repeat_gap_seconds_min {gap:g})")
    return out


DESIGN_KEYS = ("pavo_talking", "pavo_voice_over", "pavo_scene", "window", "footage", "still_motion")


def planned_fallbacks(plan):
    """Owner 28/10 (a long designed to one day's Pavo budget): the shots the plan's `source_design` gives a free source
    (`footage`, `still_motion`) and that a fallback may carry (fallback_refusal: silent, no character). They never take
    Pavo budget (allocate) and are never queued for a probe (long_preflight.queue): the budget goes to the spoken
    shots and the acted scenes first. A listed shot a fallback may not carry stays on Pavo, and long_plan_check refuses
    the plan (SOURCE_DESIGN_FALLBACK)."""
    design = (plan or {}).get("source_design")
    if not isinstance(design, dict):
        return set()
    listed = {x for k in FALLBACKS for x in (design.get(k) or []) if isinstance(x, str)}
    return {s["id"] for i, s in enumerate(plan.get("shots") or [])
            if s.get("id") in listed and s.get("window_of") is None
            and fallback_refusal(plan, s, i, "still_motion") is None}


def source_design_problems(plan):
    """long_plan_check's rows on the plan's `source_design` (when it has one): every id a shot of the plan, in one list
    only; `window` holds exactly the windows; a `footage` or `still_motion` shot is one a fallback may carry."""
    design = plan.get("source_design")
    if not isinstance(design, dict):
        return ["SOURCE_DESIGN (an object: " + ", ".join(DESIGN_KEYS) + " as lists of shot ids, and a note)"]
    shots = plan.get("shots") or []
    index = {s.get("id"): i for i, s in enumerate(shots) if isinstance(s, dict)}
    out, seen = [], {}
    for k in DESIGN_KEYS:
        for sid in design.get(k) or []:
            if sid not in index:
                out.append(f"SOURCE_DESIGN_UNKNOWN {k} {sid}")
                continue
            if sid in seen:
                out.append(f"SOURCE_DESIGN_TWICE {sid} ({seen[sid]} and {k})")
            seen[sid] = k
            s = shots[index[sid]]
            if (k == "window") != (s.get("window_of") is not None):
                out.append(f"SOURCE_DESIGN_WINDOW {sid} ({k}: `window` lists exactly the window_of shots)")
            elif k in FALLBACKS:
                why = fallback_refusal(plan, s, index[sid], k)
                if why:
                    out.append(f"SOURCE_DESIGN_FALLBACK {why}")
    missing = [sid for sid in index if sid not in seen]
    if missing:
        out.append(f"SOURCE_DESIGN_MISSING {', '.join(missing[:8])} (every shot names its source)")
    return out


def allocate(plan, todo, remaining, rounds=None):
    """[(shot, source or WAIT_PAVO_BUDGET)] for the shots still to make (`todo`, in risk_order: the spoken shots come
    first), spending `remaining` units on Pavo first come first served; a non-spoken shot with no character that the
    budget does not reach gets a free fallback (and, under the owner's arc-01 exception, a character shot or a spoken
    shot on the Kokoro voice gets a still in motion)."""
    import long_preflight
    import pavo_native
    rounds = rounds or long_preflight.PROBE_ROUNDS
    index = {s["id"]: i for i, s in enumerate(plan["shots"])}
    planned = planned_fallbacks(plan)
    out = []
    for s in todo:
        if s["id"] in planned:   # owner 28/10: the plan gives it a free source; the budget is for the acted shots
            out.append((s, "fallback"))
            continue
        units = long_preflight.planned_units([s], rounds, worst=True)   # the dispatch guard's bound (#475 review)
        if units <= remaining:
            remaining -= units
            out.append((s, "pavo"))
        elif (pavo_native.spoken(s) or has_character(s)) and fallback_refusal(plan, s, index[s["id"]],
                                                                               "still_motion"):
            out.append((s, "WAIT_PAVO_BUDGET"))
        else:
            out.append((s, "fallback"))
    return out


def subject(plan, shot, index):
    """What the picture must show: the shot's subject sentence (the five-part prompt's third) and its line."""
    import pavo_native
    parts = str(shot.get("prompt") or "").split(". ")
    line = pavo_native.shot_line(plan, index) if shot.get("lines") is not None else ""
    return words((parts[2] if len(parts) > 2 else shot.get("prompt", "")) + " " + line)


def plan_frame(plan):
    """E132: the frame a fallback is made at, the plan's own: a Short (9:16, the default of episode_build) 1080x1920,
    a long 2560x1440. A fallback at another frame fails its build (CLIP_ASPECT_MISMATCH)."""
    return SHORT_FRAME if (plan or {}).get("aspect_ratio", "9:16") == "9:16" else FRAME


def library(path=LIBRARY):
    return [json.loads(p.read_text()) for p in sorted(Path(path).glob("clip-*.json"))]


def footage_ok(rec, frame=FRAME):
    """A library clip a fallback may use: APPROVED, seen by Claude on its sheet, under the frozen licence list, at the
    plan's frame (E132: plan_frame), in the release by content hash."""
    from footage import ACCEPTED
    return (rec.get("vetting") == "APPROVED" and rec.get("claude_seen") is True and rec.get("licence") in ACCEPTED
            and rec.get("frame") == list(frame) and rec.get("sha256")
            and rec.get("release_asset", "").endswith(f"-sha256-{rec.get('sha256')}.mp4"))


def faceless_shot(plan, shot):
    """Story QA v5 (rights.fallback_sources.faceless_footage): a shot of anonymous figures (`figures: "anonymous"`, no
    named character, never God) may take a clip of a faceless figure; Claude's review refuses any visible face."""
    import long_plan_check as lpc
    return (lpc.criteria_version(plan) == lpc.V5 and (shot or {}).get("figures") == "anonymous"
            and not (shot or {}).get("characters"))


def period_clash(plan, rec, faceless=False):
    """Words of the plan's period exclusions (plan_check.PERIODS[...]["avoid"]) or footage.BLOCK in the clip's title or
    query: the picture would break the period rules or show a person."""
    import plan_check
    from footage import BLOCK, BLOCK_FACELESS
    block = BLOCK_FACELESS if faceless else BLOCK
    text = f"{rec.get('title', '')} {rec.get('query', '')}"
    avoid = (plan_check.period(plan) or {}).get("avoid") or []
    hit = [w for w in avoid if re.search(rf"(?i)\b(?:{w})\b", text)]
    return hit or ([block.search(text).group(0)] if block.search(text) else [])


def footage_candidates(plan, shot, index, lib=None, n=3):
    """The library clips whose theme, query and title share the most words with what the shot shows (the picture
    follows the words); none shares a word: none is a candidate."""
    want = set(subject(plan, shot, index))
    scored = []
    for rec in (library() if lib is None else lib):
        if not footage_ok(rec, plan_frame(plan)) or period_clash(plan, rec):
            continue
        have = set(words(f"{rec.get('theme', '')} {rec.get('query', '')} {rec.get('title', '')}"))
        overlap = sorted(want & have)
        if overlap:
            scored.append((-len(overlap), rec["id"], overlap))
    return [{"source": "footage", "item": cid, "matched": m} for _, cid, m in sorted(scored)[:n]]


def still_candidates(plan, shot, stills_dir=None):
    """APPROVED scene stills made for this shot (scene_stills.py, Claude's review >= 9.5 already) at the plan's
    aspect."""
    import plan_check
    folder = Path(stills_dir) if stills_dir else HERE / "stills"
    out = []
    for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        rec = json.loads(p.read_text())
        if rec.get("episode") == plan.get("episode") and rec.get("shot") == still_owner(shot) and \
                rec.get("status") == "APPROVED" and rec.get("repo_path") and rec.get("sha256"):
            out.append({"source": "still_motion", "item": rec["id"]})
    first = (shot.get("first_frame") or "")
    if first and plan_check.still_record(first) and not any(c["item"] == first for c in out):
        rec = plan_check.still_record(first)
        if rec.get("status") == "APPROVED":
            out.append({"source": "still_motion", "item": first})
    return out


def sources_report(plan, digests, approvals, guard=None, branch=None, lib=None, today=None):
    """The per-shot source plan (R1-R3) for today's budget: approved, awaiting review (a clip exists), pavo, a free
    fallback with its candidates, or waiting for the budget."""
    import episode_build as eb
    remaining, why = budget_remaining(guard)
    waiting = awaiting_review(plan, digests, approvals, branch)
    todo, shots = [], {}
    for i, s in eb.risk_order(plan["shots"]):
        a = approvals.get(s["id"])
        if a and (a.get("request_sha256") == digests.get(s["id"]) or a.get("source") in FALLBACKS):
            shots[s["id"]] = {"source": a.get("source", "pavo"), "state": "approved"}
        elif s["id"] in waiting:
            shots[s["id"]] = {"source": "pavo_reuse", "state": "awaiting_review",
                              "clips": [{k: c.get(k) for k in ("asset", "url", "clip_sha256", "from")}
                                        for c in waiting[s["id"]]]}
        else:
            todo.append((i, s))
    index = {s["id"]: i for i, s in todo}
    for s, choice in allocate(plan, [s for _, s in todo], remaining):
        if choice == "fallback":
            import pavo_native
            free = not has_character(s) and not pavo_native.spoken(s)   # a person or a voice: a still with refs only
            cands = (footage_candidates(plan, s, index[s["id"]], lib) if free else []) + still_candidates(plan, s)
            shots[s["id"]] = {"source": cands[0]["source"] if cands else "WAIT_FALLBACK_CANDIDATE",
                              "state": "fallback", "candidates": cands}
        else:
            shots[s["id"]] = {"source": choice, "state": "to_make"}
    order = {s["id"]: k for k, s in enumerate(plan["shots"])}
    return {"version": "shot-sources-v1", "episode": plan.get("episode"),
            "date": today or time.strftime("%Y-%m-%d", time.gmtime()),
            "pavo_budget": {"remaining_units": remaining, "why": why},
            "branch_records_read": branch is not None,
            "counts": {k: sum(v["source"] == k for v in shots.values()) for k in
                       SOURCES + ("WAIT_PAVO_BUDGET", "WAIT_FALLBACK_CANDIDATE")},
            "shots": dict(sorted(shots.items(), key=lambda kv: order[kv[0]]))}


# ---------- the approval of a fallback or an inventory clip (Claude's review, never automatic) ----------

def fallback_digest(plan, shot, index, source, item, sha):
    """The request of a fallback shot: the shot, what it must show (its prompt and line words) and the exact source."""
    import pavo_native
    canonical = {"shot": shot["id"], "kind": shot.get("kind"), "speaker": shot.get("speaker"),
                 "voiceover": shot.get("voiceover"), "characters": sorted(shot.get("characters") or []),
                 "prompt": shot.get("prompt"), "words": pavo_native.words(
        pavo_native.shot_line(plan, index)) if shot.get("lines") is not None else [], "source": source,
                 "item": item, "sha256": sha}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def approve_source(plan, shot_id, source, item, score, note, digests=None, lib=None, shots_dir=None, today=None,
                   speech_dir=None, inventories=INVENTORIES):
    """Claude's review of one fallback or inventory candidate (>= 9.5), into shots/<episode>.json with its `source`.
    Refused: a spoken shot or a shot with a character on a free fallback (SOURCE_SPOKEN_SHOT, SOURCE_CHARACTER_SHOT), a
    library clip not vetted, outside the licence list or clashing with the period (FOOTAGE_NOT_USABLE), one sharing
    no word with the shot (SOURCE_OFF_LINE: the picture follows the words), a still not APPROVED for this shot
    (STILL_NOT_FOR_SHOT), an inventory clip not clean or of another request (REUSE_NOT_CLEAN, REUSE_REQUEST_CHANGED),
    or with no committed preflight to say which request the plan sends now (REUSE_PREFLIGHT_MISSING), a reused clip
    keeping Pavo's speech on a native spoken shot without its speech checks passed on that clip (REUSE_SPEECH_UNCHECKED,
    SPEECH_CHECKS_FAILED; review of #476), a score under the floor or an empty note."""
    import episode_build as eb
    import pavo_native
    import plan_check
    index = {s["id"]: i for i, s in enumerate(plan["shots"])}
    if shot_id not in index or eb.is_window(plan["shots"][index[shot_id]]):
        raise SystemExit(f"SOURCE_SHOT_UNKNOWN {shot_id}")
    i, shot = index[shot_id], plan["shots"][index[shot_id]]
    if source not in ("footage", "still_motion", "pavo_reuse"):
        raise SystemExit(f"SOURCE_REFUSED {source!r} (footage, still_motion or pavo_reuse)")
    try:
        score = float(score)
    except (TypeError, ValueError):
        raise SystemExit(f"SHOT_SCORE_INVALID {score!r}") from None
    if not (math.isfinite(score) and REVIEW_MIN <= score <= 10):
        raise SystemExit(f"SHOT_SCORE_OUT_OF_RANGE {shot_id} {score} (a review score {REVIEW_MIN}-10)")
    if not (note or "").strip():
        raise SystemExit(f"SHOT_NOTE_MISSING {shot_id} (what the review saw)")
    entry = {"source": source, "score": score, "note": note.strip(),
             "approved_at": today or time.strftime("%Y-%m-%d", time.gmtime())}
    if source in FALLBACKS:
        refused = fallback_refusal(plan, shot, i, source, plan_check.still_record(item) if source == "still_motion"
                                   else None)
        if refused:
            raise SystemExit(refused)
    if source == "footage":
        rec = next((r for r in (library() if lib is None else lib) if r.get("id") == item), None)
        frame = plan_frame(plan)
        if rec is None or not footage_ok(rec, frame) or period_clash(plan, rec, faceless_shot(plan, shot)):
            raise SystemExit(f"FOOTAGE_NOT_USABLE {item} (APPROVED, seen by Claude, the frozen licence list, "
                             f"{frame[0]}x{frame[1]}, no period clash or person)")
        if not set(subject(plan, shot, i)) & set(words(f"{rec.get('theme')} {rec.get('query')} {rec.get('title')}")):
            raise SystemExit(f"SOURCE_OFF_LINE {shot_id} {item} (the clip shares no word with what the shot shows)")
        entry.update(footage=item, asset=rec["release_asset"], clip_sha256=rec["sha256"], licence=rec["licence"],
                     credit=rec.get("credit"), clip_seconds=int(float(rec.get("seconds") or 0)),
                     request_sha256=fallback_digest(plan, shot, i, source, item, rec["sha256"]))
    elif source == "still_motion":
        rec = plan_check.still_record(item)
        if not rec or rec.get("status") != "APPROVED" or rec.get("shot") != still_owner(shot) or \
                rec.get("episode") != plan.get("episode") or not rec.get("repo_path"):
            raise SystemExit(f"STILL_NOT_FOR_SHOT {item} (an APPROVED scene still of {still_owner(shot)})")
        if shot.get("still_of") is not None:
            bad = still_of_problems(plan)
            mine = [b for b in bad if shot_id in b.split()[1:3]]
            if mine:
                raise SystemExit(mine[0])
            # another camera move over the same picture; a talking Keeper stays static (E98): a tighter crop
            entry["motion"] = REUSE_KEEPER_MOTION if shot.get("kind") == "keeper" else REUSE_MOTION
        entry.update(still=item, repo_path=rec["repo_path"], clip_sha256=None, still_sha256=rec["sha256"],
                     frame=list(plan_frame(plan)),   # E132: rendered at the frame of the plan that ships it
                     licence=still_licence(rec),
                     # a spoken shot has no `seconds` (its line decides): the longest clip the adapter makes covers it
                     clip_seconds=int(shot.get("seconds") or MAX_STILL_CLIP_SECONDS),   # E118: whole seconds, like a Pavo clip
                     request_sha256=fallback_digest(plan, shot, i, source, item, rec["sha256"]))
    else:   # pavo_reuse: a clean clip of an inventory, of the request the plan sends now
        path, _, sha = str(item).partition("#")
        found = [c for c in committed_clips(plan, inventories=inventories, approvals={}).get(shot_id, [])
                 if c.get("url") and c.get("from") == f"{path}#{sha}"]
        if not found:
            raise SystemExit(f"REUSE_NOT_CLEAN {shot_id} {item} (a clean inventory clip of this shot)")
        clip = found[0]
        if digests is None:   # review of #476: never approved without the request the plan sends now
            raise SystemExit(f"REUSE_PREFLIGHT_MISSING {shot_id} (the committed preflight's request digests)")
        if clip.get("request_sha256") != digests.get(shot_id):
            raise SystemExit(f"REUSE_REQUEST_CHANGED {shot_id} (made from another request than the plan sends now)")
        if not CDN.fullmatch(str(clip.get("url"))):
            raise SystemExit(f"REUSE_URL_REFUSED {shot_id}")
        entry.update(url=clip["url"], clip_sha256=clip["clip_sha256"], request_sha256=clip["request_sha256"],
                     clip_seconds=float(clip.get("seconds") or 0.0), inventory=f"{path}#{sha}")
        if pavo_native.native_plan(plan) and pavo_native.route(plan, shot, i) == pavo_native.NATIVE:
            # review of #476: a reused clip that keeps Pavo's speech passes the same speech checks as a probed one
            side = (speech_dir or RECORDS / str(plan["episode"]) / "speech") / f"{clip['clip_sha256']}.json"
            if not Path(side).is_file():
                raise SystemExit(f"REUSE_SPEECH_UNCHECKED {shot_id} (episode_build.py speech-check on the clip first)")
            speech = pavo_native.speech_record(clip["clip_sha256"], json.loads(Path(side).read_text()).get(
                "measures") or {}, pavo_native.shot_line(plan, i),
                binding=pavo_native.voice_binding(pavo_native.speaker(shot)))
            if speech["flags"]:
                raise SystemExit(f"SPEECH_CHECKS_FAILED {shot_id} {','.join(speech['flags'])}")
            entry["speech"] = speech
    out = Path(shots_dir or eb.SHOTS_DIR) / f"{plan['episode']}.json"
    data = eb.load(out) if out.exists() else {"episode": plan["episode"], "shots": {}}
    if source in FALLBACKS:
        repeat = image_repeat_refusal(plan, shot_id, entry, data["shots"])
        if repeat:
            raise SystemExit(repeat)
    data["shots"][shot_id] = entry
    data["shots"] = dict(sorted(data["shots"].items()))
    eb.save(out, data)
    return entry


def picture_sha256(approval):
    """E139: what a fallback shows, by content: a still's sha256 (one picture whatever part is shown) or a library
    clip's; None for a Pavo clip (each generation is its own picture)."""
    a = approval or {}
    if a.get("source") == "still_motion":
        return a.get("still_sha256")
    if a.get("source") == "footage":
        return a.get("clip_sha256")
    return None


def image_repeat_refusal(plan, shot_id, entry, approvals):
    """E139: story QA's image_repeat_gap_seconds_min for a fallback: the same still or library clip (by sha256)
    approved for another shot of the plan whose hold is nearer than the gap is SOURCE_IMAGE_REPEAT. A long is measured
    on its own timeline (long_plan_check.timeline); a Short is shorter than the gap, so any other shot is near."""
    import long_plan_check as lpc
    sha = picture_sha256(entry)
    others = [k for k, a in (approvals or {}).items() if k != shot_id and sha and picture_sha256(a) == sha]
    if not others:
        return None
    gap = (lpc.qa_for(plan) or lpc.qa())["grammar"]["image_repeat_gap_seconds_min"]
    near = others
    if plan.get("version") == lpc.VERSION:
        tl = lpc.timeline(plan)
        at = {s["id"]: (tl["begin"][i], tl["end"][i]) for i, s in enumerate(plan["shots"])}
        mine = at.get(shot_id)
        near = [k for k in others if k not in at or mine is None
                or max(at[k][0] - mine[1], mine[0] - at[k][1]) < gap]
    if not near:
        return None
    return (f"SOURCE_IMAGE_REPEAT {shot_id} ({entry.get('footage') or entry.get('still')} is already approved for "
            f"{', '.join(sorted(near))}, within story QA's image_repeat_gap_seconds_min {gap:g} s: a picture is its "
            "sha256, not its shot; choose another source)")


def expected_request(plan, shot, index, approval, digests):
    """The request sha256 an approval must hold now: a fallback's own (fallback_digest of its source), else the
    request the plan sends now."""
    if (approval or {}).get("source") == "footage":
        return fallback_digest(plan, shot, index, "footage", approval.get("footage"), approval.get("clip_sha256"))
    if (approval or {}).get("source") == "still_motion":
        return fallback_digest(plan, shot, index, "still_motion", approval.get("still"), approval.get("still_sha256"))
    return digests.get(shot["id"])


# ---------- the build: fetch and render what was approved ----------

def still_motion_clip(still, out, seconds, frame=FRAME, motion="push_in", fps=30):
    """An approved still in slow continuous camera motion (motion.py's eased zoompan over a 2x master) at the QA's
    frame, no audio."""
    import motion as camera
    w, h = frame
    frames = int(round(seconds * fps))
    e = f"(3*pow(on/{frames},2)-2*pow(on/{frames},3))"
    base = 1 / (1 - camera.ZOOM)
    z = {"push_in": f"(1.0000+{base - 1:.4f}*{e})", "pull_out": f"({base:.4f}-{base - 1:.4f}*{e})",
         "static_crop": f"{base:.4f}"}.get(motion, f"{base:.4f}")
    vf = (f"scale={2 * w}:{2 * h}:force_original_aspect_ratio=increase,crop={2 * w}:{2 * h},"
          f"zoompan=z='{z}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={frames}:s={w}x{h}:fps={fps},"
          f"trim=end_frame={frames},format=yuv420p")
    done = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(still), "-vf", vf, "-an", "-c:v",
                           "libx264", "-preset", "medium", "-crf", "18", "-r", str(fps), str(out)],
                          capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"STILL_MOTION_FAILED {done.stderr.strip()[-300:]}")
    return out


def fetch_source(approval, dst, fetch=None, download=None, frame=FRAME):
    """The approved clip of a shot by its source, its sha256 checked: a probed clip or a library clip from the release
    by content-hash name, an inventory clip from Pavo's CDN, a still rendered in motion (its still's sha256)."""
    import episode_build as eb
    src = approval.get("source", "pavo")
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src == "still_motion":
        # E132: the approval names the frame of the plan that ships it (approve_source: plan_frame); a Short's still
        # rendered at the long's default would fail its build (CLIP_ASPECT_MISMATCH)
        frame = tuple(approval.get("frame") or frame)
        still = REPO / str(approval.get("repo_path") or "")
        if REPO.resolve() not in still.resolve().parents or not still.is_file():
            raise SystemExit(f"STILL_PATH_REFUSED {approval.get('still')}")
        if eb.sha256(still) != approval.get("still_sha256"):
            raise SystemExit(f"STILL_SHA256_MISMATCH {approval.get('still')}")
        move = {"motion": approval["motion"]} if approval.get("motion") else {}   # a reused still's own camera move
        return still_motion_clip(still, dst, approval["clip_seconds"], frame, **move)
    if src == "pavo_reuse" and approval.get("url"):
        if not CDN.fullmatch(approval["url"]):
            raise SystemExit("REUSE_URL_REFUSED")
        if download is None:
            import pavo_footage
            download = pavo_footage.download
        download(approval["url"], dst)
    elif src == "footage":
        name = approval.get("asset") or ""
        if not re.fullmatch(r"footage-clip-[a-z0-9-]+-sha256-[0-9a-f]{64}\.mp4", name):
            raise SystemExit(f"SHOT_ASSET_NAME_REFUSED {name!r}")
        (fetch or eb.fetch_release_asset)(name, dst)
    else:
        return eb.fetch_shot_clip(approval, dst, fetch or eb.fetch_release_asset)
    if eb.sha256(dst) != approval.get("clip_sha256"):
        raise SystemExit(f"SHOT_CLIP_SHA256_MISMATCH {approval.get('asset') or approval.get('url')}")
    return dst


def main(argv):
    import episode_build as eb
    if len(argv) >= 3 and argv[1] == "sources":
        plan = eb.load(argv[2])
        import long_preflight
        _, report, _ = long_preflight.report_for(argv[2])
        digests = ((report or {}).get("requests") or {}).get("digests") or {}
        result = sources_report(plan, digests, eb.load_approvals(plan), branch=branch_clips(plan))
        print(json.dumps(result, indent=1, ensure_ascii=False))
        if "--write" in argv:
            out = SOURCES_DIR / f"{plan['episode']}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            eb.save(out, result)
        return 0
    if len(argv) == 8 and argv[1] == "approve-source":
        plan = eb.load(argv[2])
        import long_preflight
        _, report, _ = long_preflight.report_for(argv[2])
        digests = ((report or {}).get("requests") or {}).get("digests")
        print(json.dumps(approve_source(plan, argv[3], argv[4], argv[5], argv[6], argv[7], digests),
                         ensure_ascii=False))
        return 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
