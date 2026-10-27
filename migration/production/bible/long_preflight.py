#!/usr/bin/env python3
"""The Bible-story long's no-rework contract (E127, owner 27/10: "no rework, ever"). The Shorts had it since E106/E114
(a preflight before any build, every shot probed by shot-probe.yml and approved by Claude before the build, a build
that only assembles approved clips); the long (`bible-long-plan-v1`, arc-01-long) had none of it, so its first build
would have generated ~165 clips that Claude met only after hours of Actions. This module is what differs for the long;
everything else is the Short's own code (episode_preflight.py, episode_build.py), run on the long's plan:

  preflight (episode_build.py preflight PLAN --voice ... --refs --write)
      long_plan_check --strict and the frozen story QA v3 (episode_build.check_plan), the plan's path; the characters
      it uses; the pinned Kokoro voice laid out at the long's LONG_LINE_GAP with the long's measured gate (length,
      Keeper share); every request through the adapter's offline checks and its request digest (windows excluded:
      a `window_of` shot ships its source's clip); every talking line's direct probe (PROBE_REQUIRED /
      PROBE_RATE_LOW). Plus the long's review rows: while any story QA v3 row or any rubric item's `long` entry in
      ops/refusal_registry.json is `open`, the report is BLOCKED (LONG_REVIEW_OPEN). Bound by sha256 to the plan,
      the characters' entries and image records (their references and voices), the matched probes, the review rows
      and the code.
  verify-preflight PLAN
      the build's first step: PASS, not stale, no review row open NOW, and every generated shot approved for the
      request the plan sends now (SHOT_NOT_REVIEWED / SHOT_REQUEST_CHANGED / SHOT_CLIP_TOO_SHORT).
  check-probe PLAN (shot-probe.yml's first step, env SHOTS / ATTEMPTS)
      for a long, also LONG_PROBE_PREFLIGHT: the committed preflight is bound to this plan and its voice, references
      and requests are clean, so a probed clip is the clip of the request the build will send (only the open review
      rows and the talking probes may still block it: neither changes a request).
  probe-queue PLAN [MAX_MINUTES]
      resume: the generated shots with no approved clip of their request now, riskiest first (episode_build.risk_rank:
      talking characters, the Keeper, voice-overs, wide and establishing scenes, the rest), cut into shot-probe.yml
      batches that fit one run.
  estimate PLAN [--write]
      the production estimate (no generation): shots by kind, image-first candidates, Pavo jobs and run time.
"""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import episode_build as eb  # noqa: E402
import long_plan_check as lpc  # noqa: E402
import plan_check  # noqa: E402

REGISTRY = REPO / "migration" / "ops" / "refusal_registry.json"
LONG_CODE = [HERE / "long_plan_check.py", HERE / "long_preflight.py"]
ESTIMATES = REPO / "migration" / "evidence" / "long"
# what may still block a long's preflight while its shots are probed: neither changes a shot's request
PROBE_TOLERATED = ("LONG_REVIEW_OPEN", "PROBE_REQUIRED", "PROBE_RATE_LOW")
PROBE_STALE_TOLERATED = ("setups", "review")   # a new direct probe or a closed review row changes no request
# shot-probe.yml: its job's timeout-minutes (test_long_preflight holds it equal) and the minutes before the first
# generation (apt, two venvs, the face and SyncNet models, Kokoro over the whole long, refs), measured on the Shorts'
# runs at ~12 min and doubled for the long's 123 lines
PROBE_JOB_MINUTES = 240
PROBE_SETUP_MINUTES = 30
# review of #468: a batch is packed to this share of the job's timeout, so a batch whose shots regenerate more than
# the average (GENERATIONS_PER_ROUND is a mean) still ends before the timeout kills the run
PROBE_BATCH_SHARE = 0.7
PROBE_ROUNDS = 2              # shot-probe.yml's default attempts: two clean candidates for Claude to choose from
# expected generations a round makes for one shot (make_shot regenerates a failed clip): a scene ~1.2 (E108/E114 frame
# misses happen after the checks, at the review), a talking clip 1 / its lips pass rate, ~0.4 (keeper-lipsync-rate)
GENERATIONS_PER_ROUND = {"talking": 2.5, "voice_over": 1.2, "scene": 1.2}
sys.path.insert(0, str(REPO / "migration" / "integrations" / "pavo"))
import quota  # noqa: E402  (E128: the shared free-model budget; stdlib only)


def review_rows(registry=None):
    """The rows a long's review relies on: every story QA v3 row and every rubric item's `long` entry
    ({name: entry}). ops/refusal_registry.json maps each to the earlier check that guarantees it, or `open`."""
    data = json.loads(REGISTRY.read_text()) if registry is None else registry
    review = data["review"]
    rows = {f"story_qa_v3.{k}": v for k, v in review["story_qa_v3"].items()}
    rows.update({f"rubric.{k}.long": v["long"] for k, v in review["rubric"].items() if isinstance(v.get("long"), dict)})
    return rows


def open_rows(registry=None):
    return sorted(k for k, v in review_rows(registry).items() if v.get("class") == "open")


def review_problems(registry=None):
    """LONG_REVIEW_OPEN while any row is open: a row with no earlier check is met first at the review, after the
    build (the rework E106 forbids)."""
    rows = open_rows(registry)
    return [f"LONG_REVIEW_OPEN {len(rows)} rows: {' '.join(rows)} (ops/refusal_registry.json review: each needs the "
            "earlier check that guarantees it before the long's build)"] if rows else []


def extend(report, plan, registry=None):
    """episode_preflight.preflight's long part: the review rows into the report and its blockers."""
    rows = open_rows(registry)
    report["review_rows"] = {"open": rows, "total": len(review_rows(registry))}
    report["blockers"] += review_problems(registry)
    report["cf_images"]["note"] = "the long sends no new reference sheet; image-first stills: see the estimate"
    return report


def binding_extra(registry=None):
    """What a long's report vouches for beyond the Short's binding: its review rows and the long's code."""
    return {"review": eb.digest(review_rows(registry)),
            "long_code": {p.name: eb.sha256(p) for p in LONG_CODE}}


def report_for(plan_path):
    import episode_preflight as pf
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    path = pf.report_path(plan, plan_path)
    return plan, (json.loads(path.read_text()) if path.exists() else None), path


def probe_gate(plan_path):
    """shot-probe.yml's first step for a long (LONG_PROBE_PREFLIGHT): None when its shots may be probed now."""
    import episode_preflight as pf
    plan, report, path = report_for(plan_path)
    if report is None:
        return (f"LONG_PROBE_PREFLIGHT {path.name} missing (episode_build.py preflight PLAN --voice ... --refs --write, "
                "by PR, before any of the long's shots is probed)")
    changed = [p for p in pf.stale_parts(report.get("binding"), pf.binding(plan_path, plan))
               if p.split(":")[0] not in PROBE_STALE_TOLERATED]
    if changed:
        return f"LONG_PROBE_PREFLIGHT stale: {', '.join(changed)} changed after the preflight; run it again"
    left = [b for b in report.get("blockers", []) if not b.startswith(PROBE_TOLERATED)]
    if left:
        return "LONG_PROBE_PREFLIGHT blocked: " + "; ".join(left)[:600]
    if not (report.get("requests") or {}).get("digests"):
        return "LONG_PROBE_PREFLIGHT no request digests (run the preflight with --voice and --refs)"
    return None


def kind_of(shot):
    if plan_check.talking(shot):
        return "talking"
    if plan_check.speaking(shot) or plan_check.voiceover(shot):
        return "voice_over"
    return "scene"


def shot_minutes(shot, rounds=PROBE_ROUNDS):
    """Expected wall-clock minutes shot-probe.yml spends on one shot: rounds x generations a round x Pavo's measured
    time a generation (lpc.PAVO_SCENE_S, PAVO_TALK_S with lipsync_check and SyncNet), one after another."""
    kind = kind_of(shot)
    each = lpc.PAVO_TALK_S if kind == "talking" else lpc.PAVO_SCENE_S
    return rounds * GENERATIONS_PER_ROUND[kind] * each / 60


def planned_units(shots, rounds=PROBE_ROUNDS, worst=False):
    """E128: the free-model units a shot-probe batch spends: rounds x the expected generations a round
    (GENERATIONS_PER_ROUND, the same mean the minutes use) x quota.VIDEO_UNITS, rounded up; with worst, rounds x every
    generation make_shot may spend (eb.attempts_for) x VIDEO_UNITS, the bound a batch must fit before it starts so it
    never stops half-way for the budget (review of #475)."""
    if worst:
        return sum(rounds * eb.attempts_for(s) for s in shots) * quota.VIDEO_UNITS
    return math.ceil(sum(rounds * GENERATIONS_PER_ROUND[kind_of(s)] for s in shots) * quota.VIDEO_UNITS)


def batch_budget():
    """Expected minutes of generation one shot-probe run is packed with: PROBE_BATCH_SHARE of its timeout, less setup."""
    return PROBE_BATCH_SHARE * PROBE_JOB_MINUTES - PROBE_SETUP_MINUTES


def queue(plan, digests, approvals, needs=None, max_minutes=None, rounds=PROBE_ROUNDS, max_units=None):
    """The shots still to probe and approve (no approved clip, or one of another request or too short), in
    risk_order, cut into shot-probe.yml batches: one rank per batch, each fitting max_minutes (default:
    batch_budget(), PROBE_BATCH_SHARE of the job's timeout less its setup) and max_units (E128: the free-model units a
    day allows, default the quota cap; a batch's worst case, pavo_units_max, must fit it), each with its expected units
    (pavo_units_est). Resume is this list: an approved shot leaves it, a changed request comes back."""
    max_minutes = max_minutes or batch_budget()
    max_units = max_units or quota.QuotaGuard(actions=None).cap()
    approvals = approvals or {}
    todo = []
    for i, s in eb.risk_order(plan["shots"]):
        a = approvals.get(s["id"])
        need = (needs or {}).get(s["id"])
        if a and a.get("request_sha256") == digests.get(s["id"]) and (
                need is None or (isinstance(a.get("clip_seconds"), (int, float)) and a["clip_seconds"] >= need)):
            continue
        todo.append(s)
    batches, cur, used, rank = [], [], 0.0, None
    def close():
        batches.append({"shots": ",".join(x["id"] for x in cur), "attempts": rounds, "minutes_est": round(used),
                        "rank": rank, "pavo_units_est": planned_units(cur, rounds),
                        "pavo_units_max": planned_units(cur, rounds, worst=True)})
    for s in todo:
        m = shot_minutes(s, rounds)
        if cur and (used + m > max_minutes or eb.risk_rank(s) != rank or planned_units(cur + [s], rounds, worst=True) > max_units):
            close()
            cur, used = [], 0.0
        cur.append(s)
        used += m
        rank = eb.risk_rank(s)
    if cur:
        close()
    generated = [s for s in plan["shots"] if not eb.is_window(s)]
    return {"episode": plan.get("episode"), "generated_shots": len(generated),
            "approved": len(generated) - len(todo), "to_probe": len(todo), "batches": batches,
            "probe_minutes_est": round(sum(b["minutes_est"] for b in batches))}


def queue_main(plan_path, max_minutes=None):
    plan, report, path = report_for(plan_path)
    if report is None:
        raise SystemExit(f"PREFLIGHT_MISSING {path.name} (the queue reads the committed preflight's request digests)")
    requests = report.get("requests") or {}
    result = queue(plan, requests.get("digests") or {}, eb.load_approvals(plan), requests.get("needs"),
                   float(max_minutes) if max_minutes else None)
    result["pavo_budget"] = budget_today(result["batches"])
    print(json.dumps(result, indent=1))
    return 0


def budget_today(batches, guard=None):
    """E128: today's free-model budget (main's ledger + the shot-probe records on the local origin refs) and whether
    the next batch's worst case fits it; the dispatch guard refuses the same batch with PAVO_BUDGET_SHORT."""
    guard = guard or quota.QuotaGuard(actions=quota.git_actions_usage)
    if not batches:
        return {"next_batch": None}
    try:
        fits = guard.check_batch(batches[0]["pavo_units_max"])
        return {"next_batch": "fits", **fits}
    except quota.PavoError as exc:
        return {"next_batch": "refused", "refusal": str(exc)}


# ---------- the production estimate (no generation) ----------

# PROMPT_GUIDE "Cheap preview before paid video": "Light, dust and particle moments always start from a checked still"
STILL_MOMENT = re.compile(r"(?i)\b(light|sunbeams?|rays?|dust|particles?|mist|glow\w*|flam\w+|fire)\b")


def motion_words(prompt):
    """The prompt's subject sentence (the five-part prompt's third: after the style and the shot size), where a light,
    dust or particle moment is the subject; every prompt's own light sentence names its light and is not one."""
    parts = str(prompt or "").split(". ")
    return parts[2] if len(parts) > 2 else ""


def estimate(plan, today=None):
    """Shots by how they are made, the image-first candidates, Pavo jobs and probe time for a long plan."""
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    gens = [(i, s) for i, s in enumerate(plan["shots"]) if not eb.is_window(s)]
    windows = [s["id"] for s in plan["shots"] if eb.is_window(s)]
    talking_char = [s["id"] for _, s in gens if plan_check.talking(s) and s["kind"] != "keeper"]
    talking_keeper = [s["id"] for _, s in gens if plan_check.talking(s) and s["kind"] == "keeper"]
    voice_over = [s["id"] for _, s in gens if kind_of(s) == "voice_over"]
    char_scenes = [s["id"] for _, s in gens if kind_of(s) == "scene" and s.get("characters")]
    # Pavo: frames and references are exclusive and frames take no audio, so only a scene with no character and
    # no input audio can start from a still (plan_check.frame_problems)
    free = [s for _, s in gens if not s.get("characters") and kind_of(s) == "scene" and s["kind"] == "scene"]
    still_moment = [s["id"] for s in free if STILL_MOMENT.search(motion_words(s.get("prompt")))]
    direct = [s["id"] for s in free if s["id"] not in still_moment]
    props = [s["id"] for _, s in gens if plan_check.prop_shot_problems(0, s, dict(plan, part=99), plan_check.period(plan))]
    seconds = {s["id"]: (s.get("seconds") or plan_check.TALK_CLIP[0]) for _, s in gens}
    clip_s = [seconds[x] for x in seconds]
    rounds = PROBE_ROUNDS
    minutes = sum(shot_minutes(s, rounds) for _, s in gens)
    runs = len(queue(plan, {}, {}, rounds=rounds)["batches"])   # one rank a run, each within the job timeout
    talk_lines = len(talking_char) + len(talking_keeper)
    stills_candidates = 2 * len(still_moment)
    return {
        "version": "long-production-estimate-v1", "date": today, "plan": f"migration/production/bible/plans/"
        f"{plan.get('episode')}.json", "episode": plan.get("episode"), "generation": "none (an estimate: no Pavo, no "
        "FLUX, no Actions run)",
        "shots": {"holds": len(plan["shots"]), "generated": len(gens), "windows": len(windows),
                  "talking_character_reference_video": {"n": len(talking_char), "ids": talking_char,
                                                        "how": "references (the speaker's talk_refs frame) + input "
                                                               "audio, lipsync_check + SyncNet"},
                  "talking_keeper_reference_video": {"n": len(talking_keeper), "ids": talking_keeper},
                  "god_voice_over_text_to_video": {"n": len(voice_over), "ids": voice_over,
                                                   "how": "text to video, no person, face check"},
                  "character_reference_video": {"n": len(char_scenes),
                                                "how": "references (characters' approved sheets, <= 5); cannot take "
                                                       "a still (Pavo: frames and references are exclusive)"},
                  "image_first_still_needed": {"n": len(still_moment), "ids": still_moment,
                                               "why": "no character, no audio, and a light / dust / particle / fire "
                                                      "moment: PROMPT_GUIDE 'always start from a checked still'"},
                  "direct_text_to_video": {"n": len(direct),
                                           "how": "no character, no audio, no light moment: text to video, period "
                                                  "sentences word for word, frame review"},
                  "prop_guided": {"n": len(props), "ids": props,
                                  "why": "PROP_SHOT_WITHOUT_STILL is the ark's rule (from part 9); arc-01 is Eden: no "
                                         "prop in props.json applies"}},
        "pavo": {
            "model": "agnes-video-new-flash", "resolution": "720p (1280x720 at 16:9, measured 2026-10-26)",
            "clip_seconds": "4-12 a clip (adapter); the plan's scenes are "
                            f"{min(clip_s)}-{max(clip_s)} s, talking clips 4-12 s after the retime",
            "aspect": "16:9 honoured (evidence/pavo/20261026/long-16x9-and-concurrency.json)",
            "inputs": "<= 5 reference images or first(+last) frame, never both; <= 3 input audios 2-12 s in all",
            "price": "every generation at a fresh exact 0-credit quote (refused otherwise)",
            "free_limits": "E128: Pavo's free quota is the model quota, shared by stills and videos (a Flash video makes "
                           "an Agnes still inside its conversation; run 40592173923 burned 24 video submissions on a "
                           "spent quota). quota.py counts every generation (a still 1 unit, a video 2) against one "
                           "cap of 120 units a UTC day, MCP and shot-probe alike; the dispatch guard refuses a batch "
                           "whose worst case does not fit (PAVO_BUDGET_SHORT) and two failed read-backs in a row stop "
                           "generation. A 0 quote does not prove free quota. At 120 units a day a probe day holds "
                           "about 60 video jobs: the long's probes take several days",
            "jobs_first_pass": len(gens),
            "jobs_expected_probe": round(sum(rounds * GENERATIONS_PER_ROUND[kind_of(s)] for _, s in gens)),
            "jobs_direct_talking_probes": f"{talk_lines} lines x {6} generations = {talk_lines * 6} (the preflight's "
                                          "PROBE_REQUIRED: >= 6 direct 0-credit generations a line, "
                                          "evidence/pavo/setups.json; none recorded for the long's lines yet)",
            "stills": {"candidates": stills_candidates, "engine": "Pavo agnes-image (free, cap 120/day: fits one "
                       "day) or FLUX (Workers AI, ~44 a day: two days)",
                       "blocker": "scene_stills.py makes 9:16 stills only (SIDE 1080x1920); a 16:9 plan refuses "
                                  "them (plan_check STILL_ASPECT_MISMATCH): a 16:9 still path is needed first"}},
        "time": {
            "probe_minutes_sequential": round(minutes), "probe_hours_sequential": round(minutes / 60, 1),
            "shot_probe_runs": runs,
            "why_sequential": "shot-probe.yml has one workflow-level concurrency group (heroverse-shot-probe) and "
                              "generate_clips submits one job and polls it to the end before the next",
            "with_two_pavo_jobs_at_once": round(minutes / 60 / 2, 1),
            "direct_talking_probe_hours": round(talk_lines * 6 * lpc.PAVO_TALK_S / 3600 / 2, 1),
            "upscale_cpu_minutes_1440p": round(sum(clip_s) * lpc.UPSCALE_S_PER_CLIP_S / 60),
            "reviews": f"{len(gens) * rounds} clip frame sheets for Claude (>= 9.5 each, approve-shot by PR)"},
        "publish": {
            "as_of": "2026-10-27 (the proposal of that day; rerun estimates keep it until a new one is written)",
            "proposed_date": "2026-11-04", "earliest_if_every_step_passes_first_time": "2026-11-02",
            "critical_path": [
                "27-28/10: this contract (claude/long-preflight) and the story QA v3 reader, .srt writer and the 25 "
                "open review rows (claude/long-qa-v3-gates) merged: until then LONG_REVIEW_OPEN blocks the build",
                "28/10: the local preflight with the pinned Kokoro (--voice --refs --write, 0 credits): the measured "
                "length and every request digest; a 16:9 still path in scene_stills.py for the "
                f"{len(still_moment)} image-first shots",
                f"28-29/10: {talk_lines * 6} direct 0-credit talking probes ({talk_lines} lines x 6), about "
                f"{round(talk_lines * 6 * lpc.PAVO_TALK_S / 3600 / 2, 1)} h at two Pavo jobs at once; the main risk: "
                "genesis-07's Keeper lines passed 1 in 33, so a Keeper line under 0.9 goes to plan B (voice-over "
                "Keeper, still mouth) before any shot-probe run",
                f"29/10-01/11: {runs} shot-probe.yml runs (~{round(minutes / 60)} h one after "
                "another, probe-queue order) with Claude's frame reviews and approve-shot PRs as each run lands; "
                "about 15 % re-probed",
                "in parallel: LONG_DESIGN slice 3, the long's build (16:9 compose at LONG_LINE_GAP, .srt, owned "
                "music at -15 LUFS, the Real-ESRGAN matrix), which ships approved clips only (verify-preflight first)",
                "02/11: the build, the preview gate and Claude's long review (>= 9.5); 03/11 approve.yml -> "
                "prepublish_gate.py; 04/11 publication (day 30 of the goal is 16/11)"]},
    }


def main(argv):
    if len(argv) >= 3 and argv[1] == "estimate":
        plan = json.loads(Path(argv[2]).read_text())
        result = estimate(plan, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        print(json.dumps(result, indent=1, ensure_ascii=False))
        if "--write" in argv:
            if not plan_check.EPISODE_ID.fullmatch(str(plan.get("episode"))):   # the file name comes from the plan
                raise SystemExit(f"EPISODE_ID_REFUSED {plan.get('episode')!r}")
            out = ESTIMATES / result["date"].replace("-", "") / f"{plan['episode']}-production-estimate.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            eb.save(out, result)
        return 0
    if len(argv) in (3, 4) and argv[1] == "probe-queue":
        return queue_main(argv[2], argv[3] if len(argv) == 4 else None)
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
