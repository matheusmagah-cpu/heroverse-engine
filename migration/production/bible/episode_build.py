#!/usr/bin/env python3
"""Build a Short from its plan with no chat session (owner, 2026-10-26): it opens on the conflict spoken by a
character or God's voice, the characters speak their own lines lip-synced, the story is acted out by the character
bible's people, the Keeper closes with our insight; everything generated free on Pavo, composed by the engine and
checked. episode.yml runs the steps in order; Claude only writes the plan and reviews the result. Nothing here
publishes: the composed file, a 20-frame sheet and a per-shot report go to Claude's review (>= 9.5), who then writes
the episode record and dispatches publish-episode.yml.

  episode_build.py voice-script PLAN WORK        WORK/voice-script.json for pilot_render.py voice (one segment a line
                                                 of plan_check.sequence; a spoken line in its speaker's own voice)
  episode_build.py lines PLAN WORK               per-line WAVs, each talking line retimed (atempo, <= +-10 %) to fit
                                                 a 4-12 s clip 0.25-0.65 s longer than its speech (E95), the voice
                                                 track rebuilt from them in order, each talking clip's input audio
                                                 (the Keeper's lines, a character's line; mono 44.1 kHz),
                                                 WORK/layout.json; refuses TALK_LINE_RETIME_OVER, a Keeper share or a
                                                 lesson share > 25 % and a length outside the part's range (170-179 s
                                                 from part 7)
  episode_build.py refs PLAN WORK                approved reference images (release asset or repository file, sha256
                                                 checked), as JPEG <= 1536 px in WORK/refs; a talking speaker's
                                                 `talk_refs` speaking frame as "<id>:talk" (E95)
  episode_build.py generate PLAN WORK LIP_PYTHON FACE_MODEL
                                                 E114: no generation and no Pavo secret. Every shot ships the clip
                                                 Claude approved (shots/<episode>.json), made from the request the
                                                 plan sends now (else SHOT_NOT_REVIEWED / SHOT_REQUEST_CHANGED)
                                                 and covering its layout (SHOT_CLIP_TOO_SHORT, E118),
                                                 downloaded by its content hash (sha256 checked) and checked again:
                                                 clip_check, lipsync_check on a talking clip, the face check on God's
                                                 voice-over, still-mouth on a voice-over Keeper (plan B)
  episode_build.py compose PLAN WORK MUSIC OUT   short_engine.py (cuts only, captions, owned music, -14 LUFS), then
                                                 clip_check --composed; WORK/report.json gets the timeline and checks
  episode_build.py sheet VIDEO SHEET.jpg         20 frames of the composed Short on one sheet (5 x 4)
  episode_build.py preflight PLAN [--voice VOICE_PYTHON PREPARED_WORK] [--refs] [--write]
                                                 E106, before any dispatch, locally (0 Actions, 0 credits): the build
                                                 predicted with its own functions, local Kokoro, refs and requests,
                                                 the talking setups that need a direct Pavo probe (episode_preflight.py)
  episode_build.py verify-preflight PLAN         episode.yml's first step: the committed report is PASS for this plan
                                                 (a long: long_preflight.py, E127, also no review row open)
  episode_build.py probe-queue PLAN [MAX_MINUTES]
                                                 E127: the shots still without an approved clip of their request,
                                                 riskiest first, in shot-probe.yml batches (resume)
  episode_build.py check-regenerate PLAN         episode.yml's first step: the `regenerate` input (env REGENERATE) is
                                                 refused whatever it names (E114: SHOT_APPROVED_USE_PROBE)
  episode_build.py check-probe PLAN               shot-probe.yml's first step: env SHOTS (shot ids of this plan) and
                                                 ATTEMPTS (1-6)
  episode_build.py probe PLAN WORK LIP_PYTHON FACE_MODEL OUT
                                                 E114, shot-probe.yml (PAVO_TOKEN): ATTEMPTS rounds of the build's
                                                 generation engine (generate_clips: one Pavo generation per shot at a
                                                 fresh exact 0-credit quote, the build's checks, a failed clip a NEW
                                                 generation, at most 2 more, 5 for a talking clip) on the named shots;
                                                 each clean clip in OUT under its content-hash asset name with a frame
                                                 sheet, OUT/probe.json. E128: env PAVO_BUDGET_USED (the dispatch
                                                 guard's count of today's free-model units) seeds a run-local quota
                                                 ledger; every generation is counted and two failed read-backs in a
                                                 row stop the run (PAVO_FREE_QUOTA_SUSPECTED), as the cap does
  episode_build.py probe-assets OUT EP [RUN_ID DST]
                                                 shot-probe.yml's record job: each clip checked against its name and
                                                 sha256 (names printed); with RUN_ID DST, after the upload, the record
                                                 sealed (run id, uploaded clips) to DST
  episode_build.py adopt PLAN RUN_DIR LIP_PYTHON FACE_MODEL OUT SOURCE_RUN
                                                 E114, shot-probe.yml with adopt_run: clips a build run made and
                                                 Claude approved, as a probe record (request recomputed and equal to
                                                 the plan's now, the build's checks again); nothing generated
  episode_build.py approve-shot RECORD SHOT ASSET SCORE NOTE
                                                 E114: Claude's frame review (SCORE >= 9.5) approves one probed clip
                                                 into shots/<episode>.json (by PR); the build ships that clip
  episode_build.py voice-reference RECORD SHOT ASSET SCORE NOTE
                                                 story QA v4 (review of #476): Claude's review (>= 9.5) records one
                                                 probed native clip's sha256 as its speaker's reference in voices.json
                                                 (by PR); speech-check and approve-shot bind every voice to it
  episode_build.py check-record EPISODE_JSON [VIDEO]
                                                 what publish-episode.yml would refuse in the record (title,
                                                 description, disclosure, the words), before it is dispatched

WORK must be inside the repository: the Pavo adapter reads input images and audio only from repository paths.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import wave

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "migration" / "production" / "characters"))
sys.path.insert(0, str(REPO / "migration" / "production" / "footage"))
sys.path.insert(0, str(REPO / "migration" / "integrations" / "pavo"))
import plan_check  # noqa: E402
import characters as ch  # noqa: E402
import pavo_native  # noqa: E402  (owner 27/10: Pavo's own speech, story QA v4)

VOICE = {"voice_id": "am_michael", "speed": 1.0}   # the pinned engine voice (qa_pilot.voice_model_pinned)
LINE_GAP = plan_check.LINE_GAP
TAIL = plan_check.TAIL
CUT_MAX = 4.0              # a scene cut every 2-4 s (DECISIONS 2026-10-26)
ESTABLISHING_HOLD = plan_check.ESTABLISHING_HOLD
MAX_SLOW = 1.3             # short_engine.MAX_SLOW
ATTEMPTS = 3               # one generation and at most 2 regenerations
# E98: a talking clip passes the lips check about 4 times in 10 (evidence/pavo/20261026/keeper-lipsync-rate.json):
# 3 generations lost a three-Keeper-shot run about half the time; 6 keep a shot at ~95 % (Pavo at 0 credits)
TALK_ATTEMPTS = 6
POLL_S = 15
JOB_TIMEOUT_S = 25 * 60
INCOMPLETE_POLLS = 8       # history can be empty just after submission; then "incomplete" means failed
RATE_LIMIT_WAITS = (60, 120, 240, 480)
# E93: Pavo unreachable for minutes killed a 25-of-33-shot run. generate_video raises it only before a generation
# starts (quote, upload, conversation create; a lost acknowledgement comes back as status unknown instead), so the
# call is sent again after a wait: about 33 min in all before the run gives up
OUTAGE_WAITS = (60, 120, 300, 600, 900)
TRANSIENT = {"PAVO_RATE_LIMITED": RATE_LIMIT_WAITS, "PAVO_UNREACHABLE": OUTAGE_WAITS,
             "PAVO_UPLOAD_HOST_UNREACHABLE": OUTAGE_WAITS}
REF_SIDE = 1536
LUFS = (-15.0, -13.0)
FADE_OUT = 0.8             # short_engine.FADE_OUT
RETIME_TRIM_MAX = 0.02     # atempo's few-ms miss cut or padded after a retime, never more (review of #412)
HOLD_MARGIN = 0.01         # a talking clip's held last frame is written this much longer than the time it covers
# E114: the clip Claude reviewed is the clip the build ships. shot-probe.yml generates a shot's exact request; Claude's
# frame review approves one clip (>= SHOT_REVIEW_MIN) into SHOTS_DIR/<episode>.json by PR (approve-shot); the build
# downloads that exact asset and never generates a shot that has one.
SHOTS_DIR = HERE / "shots"
SHOT_REVIEW_MIN = 9.5      # the owner's floor, the same as the review's
PROBE_ATTEMPTS_MAX = 6     # generations one shot-probe run may spend on one shot (TALK_ATTEMPTS)
SHOT_ASSET = re.compile(r"^shot-[a-z0-9]+(-[a-z0-9]+)*-sha256-[0-9a-f]{64}\.mp4$")
# E118: Kokoro measures the same voice a few hundredths of a second apart on two machines (genesis-08: 174.0 s local,
# 173.929 s on the runner, run 40483267526). The build accepts an approved clip that covers what this machine would
# request for a measurement up to MEASURE_TOLERANCE shorter, so a clip the local preflight found covering (its own
# measurement, no slack) still covers on a runner that measures within it; the compose slows a clip at most MAX_SLOW.
MEASURE_TOLERANCE = 0.1


class ShotFailed(Exception):
    pass


# E128: a refusal of the shared free-model budget (quota.py) stops the whole probe run: every later submission would
# be refused the same way (or, without the guard, burned on a spent quota: run 40592173923, 24 failed in a row)
BUDGET_STOPS = ("PAVO_DAILY_CAP", "PAVO_FREE_QUOTA_SUSPECTED", "PAVO_LEDGER_UNREADABLE", "PAVO_BUDGET_UNREADABLE")
RUN_LEDGER = "pavo-ledger.json"


def budget_stop(text):
    """The budget code a probe's SHOT_FAILED / PAVO_REFUSED message carries, or None."""
    return next((c for c in BUDGET_STOPS if c in str(text).split()), None)


def seed_budget(work, used, main_ledger=None, now=None):
    """E128, shot-probe.yml: the run-local quota ledger WORK/RUN_LEDGER, seeded with USED (the dispatch guard's units
    of today: main's ledger + today's shot-probe records) and main's suspension, so this run's own generations and
    failed read-backs count against the same budget. Returns its path (PAVO_IMAGE_LEDGER for the run)."""
    from datetime import datetime, timezone
    import quota
    if not re.fullmatch(r"[0-9]{1,6}", str(used or "").strip()):
        raise SystemExit(f"PAVO_BUDGET_UNKNOWN {used!r} (the dispatch guard's pavo_used output; never generate "
                         "without it)")
    base = quota.QuotaGuard(main_ledger or quota.LEDGER, actions=None)._load()   # fails closed if unreadable
    day = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%d")
    seeded = {k: base[k] for k in ("version", "failed_streak", "failed_jobs", "jobs", "suspended_at",
                                   "suspended_until", "probe")}
    if base.get("daily_cap") is not None:
        seeded["daily_cap"] = base["daily_cap"]
    seeded["days"] = {day: {"generated": int(used), "note": "seeded by the dispatch guard (E128)"}}
    path = Path(work) / RUN_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    save(path, seeded)
    return path


def budget_client():
    """The Pavo client of a shot-probe run: always guarded by the run-local ledger (PAVO_IMAGE_LEDGER, seed_budget)."""
    import quota
    from video import PavoVideoClient
    ledger = os.environ.get("PAVO_IMAGE_LEDGER", "")
    if not ledger or not Path(ledger).is_file():
        raise SystemExit("PAVO_BUDGET_UNKNOWN (no run-local quota ledger: episode_build.py probe seeds it)")
    return PavoVideoClient(guard=quota.QuotaGuard(ledger, actions=None))


# E127: the Bible-story long (bible-long-plan-v1, long_plan_check.py) goes through the same no-rework contract as a
# Short: its own preflight (long_preflight.py), shot-probe.yml, approve-shot into shots/<long>.json, a build that only
# ships approved clips. These helpers are the only places the two plans differ in this file.
LONG_VERSION = "bible-long-plan-v1"   # long_plan_check.VERSION (test_long_preflight holds them equal)


def is_long(plan):
    return isinstance(plan, dict) and plan.get("version") == LONG_VERSION


def line_gap(plan):
    """The silence between two voice-track lines: the Short's LINE_GAP, the long's LONG_LINE_GAP (0.6 s: at 0.35 s the
    measured arc-1 voice ran at the QA's 165 words-a-minute ceiling)."""
    if is_long(plan):
        import long_plan_check
        return long_plan_check.LONG_LINE_GAP
    return LINE_GAP


def is_window(shot):
    """A long's `window_of` shot shows another part of an earlier clip: never generated, probed or approved."""
    return shot.get("window_of") is not None


def check_plan(plan, chars=None):
    """plan_check for a Short, long_plan_check (and its frozen story QA) for a long: {problems, pending, ...}."""
    if not is_long(plan):
        return plan_check.check(plan, chars)
    import long_plan_check
    result = long_plan_check.check(plan, chars)
    frozen = long_plan_check.frozen_qa_problem(plan=plan)
    if frozen:
        result["problems"].append(frozen)
    if plan.get("episode") != plan.get("long"):   # shot-probe.yml, the dispatch guard and shots/ key on `episode`
        result["problems"].append(f"LONG_EPISODE_ID {plan.get('episode')!r} (a long's `episode` is its `long` id)")
    return result


def load(path):
    return json.loads(Path(path).read_text())


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def run(args, **kw):
    done = subprocess.run([str(a) for a in args], capture_output=True, text=True, **kw)
    if done.returncode:
        raise SystemExit(f"COMMAND_FAILED {Path(str(args[0])).name}: {done.stderr.strip()[-400:]}")
    return done.stdout


def safe_rmtree(path, root):
    """Review of #422: a work directory is removed only strictly inside its intended root, never the root itself,
    never through a symlink (shutil.rmtree does not follow the links inside it)."""
    path, root = Path(path), Path(root).resolve()
    if path.is_symlink() or root not in path.resolve().parents:
        raise SystemExit(f"RMTREE_REFUSED {path} (only a directory inside {root})")
    shutil.rmtree(path.resolve())


def rel(path):
    """Repository-relative path (the Pavo adapter takes only those)."""
    target = Path(path).resolve()
    if REPO.resolve() not in target.parents:
        raise SystemExit(f"WORK_OUTSIDE_REPOSITORY {path}")
    return str(target.relative_to(REPO.resolve()))


# ---------- voice ----------

def voice_script(plan, chars=None):
    """One segment a line of the voice track (plan_check.sequence): the narration in the Keeper's voice, each spoken
    line in its speaker's own voice (characters.voice; God's is the deep voice-over)."""
    items, _ = plan_check.sequence(plan)
    segments = []
    for k, x in enumerate(items):
        seg = {"id": f"n{k:02d}", "text": x["text"], "pause_after": 0.0}
        if x.get("speaker"):
            v = ch.voice(x["speaker"], chars)
            if not v:
                raise SystemExit(f"SPEAKER_NO_VOICE {x['speaker']}")
            seg.update(v, speaker=x["speaker"])
        segments.append(seg)
    return {"voice": dict(VOICE), "segments": segments}


def talk_record(layout, shot):
    """The line a talking shot's clip carries (input audio, lipsync_check): the Keeper's or a character's."""
    return layout["keeper"][shot["id"]] if shot["kind"] == "keeper" else layout["speakers"][shot["id"]]


def line_layout(durations, gap=LINE_GAP):
    """Lines laid end to end from 0 s with `gap` between them: [(start, end)]. The Keeper's hook starts at 0."""
    out, t = [], 0.0
    for d in durations:
        out.append((round(t, 3), round(t + d, 3)))
        t += d + gap
    return out


def voice_layout(plan, durations):
    """The voice track's lines laid out: (layout, cold-open hold (line index, seconds) or None, problems). A Short's
    lines sit end to end at LINE_GAP. A long's sit at LONG_LINE_GAP, and its cold open's last frame is held (silence
    under the music) until the Keeper at the structure's cold_open_s, at most COLD_OPEN_HOLD_MAX: measured here on
    the real voice (long_build.cold_open_layout; LONG_DESIGN slice 3: "the build must re-check it")."""
    layout = line_layout(durations, line_gap(plan))
    if not is_long(plan):
        return layout, None, []
    import long_build
    return long_build.cold_open_layout(plan, layout)


def keeper_span(lines, layout):
    return layout[lines[0]][0], layout[lines[-1]][1]


# ---------- the build's own rules as pure functions (E106: plan_check and preflight predict with these) ----------

def retime_plan(plan, durations):
    """E95/E97: the stretch talk_retime gives each talking shot's words ({shot id: (line indices, gaps, stretch)},
    stretch 1.0 = untouched) and TALK_LINE_RETIME_OVER for one no clip reaches. lines_step applies it to the audio;
    plan_check (estimated lengths) and preflight (local Kokoro) apply it to the numbers."""
    _, carried = plan_check.sequence(plan)
    out, problems = {}, []
    for i, s in enumerate(plan["shots"]):
        if not plan_check.talking(s):
            continue
        idx = carried[i]
        gaps = line_gap(plan) * (len(idx) - 1)
        words = sum(durations[k] for k in idx)
        found = plan_check.talk_retime(words, gaps)   # the cap is on the words atempo stretches, not on the gaps
        if found is None:
            problems.append(f"TALK_LINE_RETIME_OVER {s['id']} {words + gaps:.2f} s (no {plan_check.TALK_CLIP[0]}-"
                            f"{plan_check.TALK_CLIP[1]} s clip within +-{plan_check.TALK_RETIME_MAX:.0%} of its words)")
            continue
        out[s["id"]] = (idx, gaps, found[1])
    return out, problems


def plan_layout(plan, layout, voice_seconds=None, problems=()):
    """The talking and voice-over records, the shares and the length the build measures, from the lines laid out
    end to end (line_layout of the retimed lengths); no file is read or written. lines_step adds each talking clip's
    input audio (`wav`) to the records it returns."""
    items, carried = plan_check.sequence(plan)
    problems = list(problems)
    if voice_seconds is None:
        voice_seconds = round(layout[-1][1], 3) if layout else 0.0
    total = round(voice_seconds + TAIL, 3)
    keeper, speakers, voice_over, keeper_seconds = {}, {}, {}, 0.0
    shots = plan["shots"]
    native = native_spans(plan)
    refused = {p.split()[1] for p in problems}
    for i, s in enumerate(shots):
        if (s["kind"] != "keeper" and not plan_check.speaking(s)) or s["id"] in refused:
            continue
        start, end = keeper_span(carried[i], layout)
        seconds = end - start
        talks = plan_check.talking(s)
        if s["kind"] == "keeper":
            keeper_seconds += seconds
            low, code, into = plan_check.KEEPER_AUDIO[0], "KEEPER_AUDIO", keeper
        else:
            low, code = plan_check.SPEAKER_AUDIO[0], "SPEAKER_AUDIO"
            into = speakers if talks else voice_over
        # one talking ceiling (plan_check.TALK_LINE_MAX: the retime brings every talking line under it; 1 ms is the
        # layout's rounding); God's voice-over fills one scene clip
        limit = plan_check.TALK_LINE_MAX if talks else plan_check.SPEAKER_AUDIO[1]
        if plan_check.voiceover(s):
            # review of #423: his clip covers the gap before (after a talking shot), the line and the gap or tail
            # after (plan_check.vo_cover, the compose's own run logic): that whole time is capped, the line floored
            covered = plan_check.vo_covered(seconds, shots, i, is_long(plan))
            if not plan_check.VO_LINE_MIN <= seconds or covered > plan_check.VO_LINE_MAX + 1e-9:
                problems.append(f"{code} {s['id']} {seconds:.2f} s, {covered:.2f} s with the gap before and the gap or "
                                f"tail after (line >= {plan_check.VO_LINE_MIN:.1f} s, all <= "
                                f"{plan_check.VO_LINE_MAX:.1f} s)")
                continue
        elif s["id"] in native:   # Pavo's own speech, its length its approved clip's (story QA v4): Pavo made it
            pass
        elif not low <= seconds <= limit + (1e-3 if talks else 0.0):
            problems.append(f"{code} {s['id']} {seconds:.2f} s ({low:.0f}-{limit:.2f} s)")
            continue
        if talks and s["id"] not in native:
            # its clip is ceil(speech) seconds with the speech 0.25-0.65 s shorter (E95): refused here, before any
            # Pavo clip, when no 4-12 s clip can carry it
            need = talk_need(seconds)
            if need > plan_check.TALK_CLIP_MAX or not talk_fits(seconds):
                problems.append(f"TALK_LINE_TOO_LONG {s['id']} {seconds:.2f} s (needs a {need} s clip; Pavo keeps our "
                                f"audio in a {plan_check.TALK_CLIP[0]}-{plan_check.TALK_CLIP[1]} s clip 0.25-0.65 s "
                                "longer than the speech)")
                continue
        record = {"start": start, "end": end, "seconds": round(seconds, 3)}
        if plan_check.voiceover(s):     # plan B: no input audio, no lipsync; his line is narration in the track
            keeper[s["id"]] = dict(record, voiceover=True)
            continue
        if s["kind"] != "keeper":
            record["speaker"] = s["speaker"]
        into[s["id"]] = record   # God: mixed as a voice-over in the track; no clip audio, no lipsync check
    share = keeper_seconds / total
    if is_long(plan):   # E127: the long's own gate (structures/bible-story-long.json), measured; no lesson share
        import long_plan_check
        g = long_plan_check.gate()
        if share > g["keeper_share_max"] + 1e-9:
            problems.append(f"KEEPER_SHARE {share:.3f} > {g['keeper_share_max']} (measured)")
        low, high = g["length_min"]
        if not low * 60 <= total <= high * 60:
            problems.append(f"LONG_LENGTH {total / 60:.2f} min ({low}-{high}, measured)")
        return {"lines": [{"start": a, "end": b} for a, b in layout], "voice_seconds": voice_seconds, "total": total,
                "keeper": keeper, "speakers": speakers, "voice_over": voice_over, "keeper_share": round(share, 3),
                "lesson_share": None, "retimed": {}, "problems": problems}
    if share > plan_check.KEEPER_SHARE_MAX:
        problems.append(f"KEEPER_SHARE {share:.3f} > {plan_check.KEEPER_SHARE_MAX} (measured)")
    lesson = sorted({k for i, s in enumerate(shots) for k in carried[i]
                     if s["kind"] == "keeper" or items[k].get("kind") in plan_check.LESSON_KINDS})
    lesson_seconds = sum(layout[k][1] - layout[k][0] for k in lesson) + LINE_GAP * max(len(lesson) - 1, 0)
    lesson_share = lesson_seconds / total
    if lesson_share > plan_check.LESSON_SHARE_MAX:
        problems.append(f"LESSON_SHARE {lesson_share:.3f} > {plan_check.LESSON_SHARE_MAX} (measured)")
    low, high = plan_check.publish_episode.short_length(plan.get("part", 0))
    if not low <= total <= high:
        problems.append(f"SHORT_LENGTH {total} s ({low:.0f}-{high:.0f}, measured)")
    return {"lines": [{"start": a, "end": b} for a, b in layout], "voice_seconds": voice_seconds, "total": total,
            "keeper": keeper, "speakers": speakers, "voice_over": voice_over, "keeper_share": round(share, 3),
            "lesson_share": round(lesson_share, 3), "retimed": {}, "problems": problems}


def compose_prediction(plan, layout, clip_seconds=None):
    """E106: the compose's own refusals (compose_shots, short_engine.check_shots / talk_problems / speed, the
    establishing share) on the planned clip lengths, before any clip exists: [problems]. The real clips can still
    differ by Pavo's few hundredths of a second (clip_seconds: measured ones, when there are)."""
    import short_engine
    if clip_seconds is None:
        clip_seconds = {s["id"]: float(shot_seconds(s, i, plan, layout)) for i, s in enumerate(plan["shots"])
                        if not is_window(s)}
    if is_long(plan):   # LONG_DESIGN slice 3: one cut a shot at the story QA's 4-7 s holds, windows on their source
        import long_build
        return long_build.compose_problems(plan, layout, clip_seconds)
    try:
        shots = compose_shots(plan, layout, {s["id"]: s["id"] for s in plan["shots"]}, clip_seconds)
    except SystemExit as exc:
        return [str(exc)]
    sentences = [{"start": x["start"], "end": x["end"]} for x in layout["lines"]]
    problems = short_engine.check_shots(shots, layout["total"]) + short_engine.talk_problems(shots, sentences)
    for i, c in enumerate(shots):
        have = clip_seconds[c["shot"]]
        factor = short_engine.explicit_speed(c, have) if "speed" in c else short_engine.speed(c, have)
        if factor is None:
            problems.append(f"CLIP_TOO_SHORT shot {i} {c['shot']}")
    share = establishing_share(plan, shots, layout["total"])
    if share > plan_check.ESTABLISHING_SHARE_MAX:
        problems.append(f"ESTABLISHING_SHARE {share:.3f} (composed)")
    return problems


def establishing_share(plan, shots, total):
    """The composed time on establishing shots over the Short, rounded as the report keeps it: one helper for
    compose_step and compose_prediction (review of #422)."""
    establishing = sum(c["end"] - c["start"] for c in shots
                       if any(s["id"] == c["shot"] and s.get("establishing") for s in plan["shots"]))
    return round(establishing / total, 3) if total else 0.0


def predict(plan, durations):
    """E106: every refusal lines_step and the compose would raise for these line lengths (seconds per voice-track
    item, before the retime): (problems, layout). plan_check runs it on its estimate, preflight on local Kokoro."""
    durations = [float(d) for d in durations]
    stretches, problems = retime_plan(plan, durations)
    for idx, _, stretch in stretches.values():
        for k in idx:
            durations[k] *= stretch
    laid, _, cold = voice_layout(plan, durations)
    layout = plan_layout(plan, laid, None, problems + cold)
    if layout["problems"]:   # the compose needs every talking record
        return layout["problems"], layout
    return compose_prediction(plan, layout), layout


VO_REFS = "talk_refs only"   # reference_keys' field for a voice-over Keeper: his speaking frame, no fallback


def reference_keys(shot):
    """The reference sets one shot's request sends, in order: [(refs key, character id, characters.json field)].
    A talking shot sends its speaker's `talk_refs` speaking frame in place of its refs (E95), then the others. A
    voice-over Keeper shot (plan B) sends his `talk_refs` frame alone and never his front view in its place (field
    VO_REFS: keeper-vo/calibration.json, the front view lost his face 4 of 4)."""
    ids = ["keeper"] if shot["kind"] == "keeper" else list(shot.get("characters") or [])
    if plan_check.voiceover(shot):
        return [(f"{ch.NARRATOR}:talk", ch.NARRATOR, VO_REFS)]
    if not plan_check.talking(shot):
        return [(cid, cid, "refs") for cid in ids]
    who = speaker_of(shot)
    return [(f"{who}:talk", who, "talk_refs")] + [(c, c, "refs") for c in ids if c != who]


def reference_problems(plan, chars=None, images_dir=ch.HERE / "images"):
    """E106: what refs_step and request() would refuse, checked from the repository before any run: every kept
    reference record exists with its sha256 and source (REFERENCE_RECORD_MISSING), a repository image is inside the
    repository with that sha256 (REFERENCE_PATH_REFUSED / REFERENCE_SHA256_MISMATCH), a release asset has a safe name
    (REFERENCE_ASSET_NAME_REFUSED), and a shot sends at most MAX_REFS images, counted as request() sends them.
    Characters that are not APPROVED are left to plan_check (CHARACTER_NOT_APPROVED / CHARACTER_PENDING)."""
    chars = chars if chars is not None else ch.registry()
    out, seen = [], {}
    for i, s in enumerate(plan["shots"]):
        keys = reference_keys(s)
        if any((chars.get(cid) or {}).get("status") != "APPROVED" for _, cid, _ in keys):
            continue
        count = 0
        for key, cid, field in keys:
            if key not in seen:
                try:
                    if field == VO_REFS:
                        records = reference_records(cid, chars, images_dir, "talk_refs")
                        if not records:
                            raise SystemExit(f"KEEPER_VO_NO_TALK_REF {cid} (a voice-over Keeper is generated from "
                                             "his `talk_refs` frame)")
                    elif field == "refs":
                        records = reference_records(cid, chars, images_dir, field)
                    else:
                        records = (reference_records(cid, chars, images_dir, field)
                                   or reference_records(cid, chars, images_dir))
                    seen[key] = (records, [])
                except SystemExit as exc:
                    seen[key] = ([], [str(exc)])
                records, bad = seen[key]
                for rid, m in records:
                    if m.get("repo_path"):
                        src = (REPO / m["repo_path"]).resolve()
                        if REPO.resolve() not in src.parents or not src.is_file():
                            bad.append(f"REFERENCE_PATH_REFUSED {rid}")
                        elif sha256(src) != m["sha256"]:
                            bad.append(f"REFERENCE_SHA256_MISMATCH {rid}")
                    elif not re.fullmatch(r"[A-Za-z0-9._-]+\.(png|jpg|jpeg)", m["release_asset"]):
                        bad.append(f"REFERENCE_ASSET_NAME_REFUSED {rid}")
                out += [f"{p} (shot {i} {s['id']})" for p in bad]
            count += len(seen[key][0])
        if count > ch.MAX_REFS:
            out.append(f"REFERENCES_OVER_{ch.MAX_REFS} shot {i} {s['id']} ({count} images as the request sends them)")
    return out


def request_problems(plan, layout, refs, client=None, chars=None):
    """E106: every shot's Pavo request validated offline by the adapter's own checks (prepare_video: prompt,
    seconds, aspect; _plan: reference images and input audio), before the first generation: [problems]. Without
    this an invalid request surfaced as PAVO_REFUSED only when its shot's turn came, after the shots before it."""
    from client import PavoError
    if client is None:
        from video import PavoVideoClient
        client = PavoVideoClient(token="")
    out = []
    for index, shot in enumerate(plan["shots"]):
        if is_window(shot):
            continue
        try:
            req = request(shot, index, plan, layout, refs, chars)
            client.prepare_video(req["prompt"], req["seconds"], req["aspect_ratio"])
            client._plan(req.get("first_frame", ""), req.get("last_frame", ""), req["references"], req["audios"],
                         req["sound"])
        except PavoError as exc:
            out.append(f"PAVO_REQUEST_INVALID {shot['id']} {(str(exc).split() or ['PavoError'])[0]}")
        except (Exception, SystemExit) as exc:   # review of #422: any failure is a refusal by name, never a crash
            out.append(f"PAVO_REQUEST_INVALID {shot['id']} {type(exc).__name__}: {str(exc)[:200]}")
    return out


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        return w.getparams(), w.readframes(w.getnframes())


def write_wav(path, params, frames):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setparams(params)
        w.writeframes(frames)


def native_spans(plan, approvals=None):
    """{shot id: (line indices, onset, end)} of the spoken shots whose approved clip keeps Pavo's own speech (story QA
    v4): the speech span its approval measured. {} on any other plan."""
    if not pavo_native.native_plan(plan):
        return {}
    approvals = load_approvals(plan) if approvals is None else approvals
    _, carried = plan_check.sequence(plan)
    out = {}
    for i, s in enumerate(plan["shots"]):
        speech = (approvals.get(s["id"]) or {}).get("speech") or {}
        if pavo_native.spoken(s) and not is_window(s) and isinstance(speech.get("onset"), (int, float)) and \
                isinstance(speech.get("end"), (int, float)) and speech["end"] > speech["onset"]:
            out[s["id"]] = (carried[i], float(speech["onset"]), float(speech["end"]))
    return out


def lines_step(plan, work):
    """Cut each line of the voice track out of pilot_render's voice.wav, rebuild the track from the line WAVs in
    order, write each talking clip's input audio (the Keeper's lines, a character's spoken line) and the compose
    timeline; measure the Short against the plan's rules again."""
    work = Path(work)
    items, carried = plan_check.sequence(plan)
    timeline = load(work / "timeline.json")
    params, frames = read_wav(work / "voice.wav")
    if params.sampwidth != 2:   # retime() reads atempo's pcm_s16le back under these params (review of #412)
        raise SystemExit(f"VOICE_SAMPLE_WIDTH {params.sampwidth * 8}-bit voice.wav (16-bit PCM only)")
    rate, width = params.framerate, params.sampwidth * params.nchannels
    n = len(items)
    by_line = {k: [s for s in timeline["sentences"] if s["segment"] == f"n{k:02d}"] for k in range(n)}
    if any(not v for v in by_line.values()):
        raise SystemExit("VOICE_LINE_MISSING " + " ".join(f"n{k:02d}" for k, v in by_line.items() if not v))
    pieces, durations = [], []
    for k in range(n):
        a = int(round(by_line[k][0]["start"] * rate)) * width
        b = int(round(by_line[k][-1]["end"] * rate)) * width
        pieces.append(frames[a:b])
        durations.append(len(frames[a:b]) / width / rate)
    # E95: a talking clip keeps our audio only when it is 0.25-0.65 s longer than the speech; a talking line that
    # misses that window is retimed (atempo, pitch kept, at most +-10 %) before anything is laid out, so the track,
    # the captions, the input audio and the lips check all use the same retimed words
    retimes = {}
    scale = [1.0] * n
    # story QA v4 (owner 27/10, R4): a line Pavo speaks itself takes the time its approved clip speaks it (the
    # approval's measured speech span); its place in our track is silence, Pavo's own speech is laid there at the
    # compose (long_build.premix). Before any approval the Kokoro length predicts it.
    native = native_spans(plan)
    for sid, (idx, onset, end) in native.items():
        gaps = line_gap(plan) * (len(idx) - 1)
        spoken = sum(durations[k] for k in idx)
        factor = max(0.05, (end - onset) - gaps) / spoken if spoken else 1.0
        for k in idx:
            want = int(round(durations[k] * factor * rate)) * width
            pieces[k] = b"\x00" * want
            scale[k] = factor
            durations[k] = want / width / rate
    stretches, problems = retime_plan(plan, durations)   # E106: the same rule plan_check and preflight predict with
    stretches = {k: v for k, v in stretches.items() if k not in native}
    problems = [p for p in problems if p.split()[1] not in native] if native else problems
    for sid, (idx, gaps, stretch) in stretches.items():
        if stretch == 1.0:
            continue
        speech = sum(durations[k] for k in idx) + gaps
        factor = 1 / stretch                                       # atempo > 1 speeds the words up
        for k in idx:
            piece = retime(pieces[k], params, factor, work / "lines" / f"n{k:02d}")
            scale[k] = (len(piece) / width / rate) / durations[k]
            pieces[k], durations[k] = piece, len(piece) / width / rate
        retimes[sid] = {"speech": round(speech, 3), "retimed": round(sum(durations[k] for k in idx) + gaps, 3),
                        "atempo": round(factor, 4)}
    for k in range(n):
        write_wav(work / "lines" / f"n{k:02d}.wav", params, pieces[k])
    layout, cold, cold_problems = voice_layout(plan, durations)
    problems += cold_problems
    silence = b"\x00" * (int(round(line_gap(plan) * rate)) * width)
    if cold:   # a long: the cold open's last frame held in silence until the Keeper (voice_layout)
        k0, hold = cold
        held = silence + b"\x00" * (int(round(hold * rate)) * width)
        track = silence.join(pieces[:k0]) + held + silence.join(pieces[k0:])
    else:
        track = silence.join(pieces)
    write_wav(work / "narration.wav", params, track)
    voice_seconds = round(len(track) / width / rate, 3)
    sentences = []
    for k in range(n):
        first = by_line[k][0]["start"]
        who = {"speaker": items[k]["speaker"]} if items[k].get("speaker") else {}
        sentences += [dict({"segment": f"n{k:02d}", "text": s["text"],
                            "start": round(layout[k][0] + (s["start"] - first) * scale[k], 3),
                            "end": round(layout[k][0] + (s["end"] - first) * scale[k], 3)}, **who) for s in by_line[k]]
        sentences[-1]["end"] = round(layout[k][1], 3)
    save(work / "compose-timeline.json", {"voice_seconds": voice_seconds, "sentences": sentences,
                                          "voice_id": VOICE["voice_id"], "speed": VOICE["speed"], "sample_rate": rate})
    result = plan_layout(plan, layout, voice_seconds, problems)
    for folder, records in (("keeper", result["keeper"]), ("speakers", result["speakers"])):
        for sid, record in records.items():   # each talking clip's input audio, cut from the rebuilt track
            if record.get("voiceover"):        # plan B: a silent Keeper clip takes no input audio
                continue
            native = work / folder / f"{sid}-native.wav"
            a, b = int(round(record["start"] * rate)) * width, int(round(record["end"] * rate)) * width
            write_wav(native, params, track[a:b])
            out = work / folder / f"{sid}.wav"
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", native, "-ac", "1", "-ar", "44100", "-c:a",
                 "pcm_s16le", out])
            record["wav"] = rel(out)
    result["retimed"] = retimes
    problems = result["problems"]
    save(work / "layout.json", result)
    print(json.dumps({k: result[k] for k in ("voice_seconds", "total", "keeper_share", "lesson_share", "problems")}))
    if problems:
        raise SystemExit("LINES_REFUSED " + "; ".join(problems))
    return result


# ---------- reference images ----------

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def reference_records(cid, chars=None, images_dir=ch.HERE / "images", field="refs"):
    """The kept reference images of one APPROVED character, in characters.json order: [(record id, record)].
    field "talk_refs": its speaking frames (E95: a mouth-closed front view broke the lip tracking), [] when none."""
    chars = chars if chars is not None else ch.registry()
    c = chars.get(cid)
    if not c or c.get("status") != "APPROVED" or not c.get("refs"):
        raise SystemExit(f"CHARACTER_NOT_APPROVED {cid}")
    out = []
    for shot in c.get(field) or []:
        rec = Path(images_dir) / f"ch-{cid}-{shot}.json"
        m = load(rec) if rec.exists() else {}
        if not m.get("sha256") or not (m.get("release_asset") or m.get("repo_path")):
            raise SystemExit(f"REFERENCE_RECORD_MISSING ch-{cid}-{shot}")
        out.append((f"ch-{cid}-{shot}", m))
    return out


def fetch_release_asset(name, dst):
    run(["bash", REPO / "migration" / "ci" / "assets.sh", "download", "--pattern", name, "-O", dst, "--clobber"])


def ref_wants(plan):
    """The reference sets the plan needs: ([(refs key, character id, characters.json field)], silent speakers)."""
    needed, talkers = [], []
    for s in plan["shots"]:
        for cid in (["keeper"] if s["kind"] == "keeper" else s.get("characters", [])):
            if cid not in needed:
                needed.append(cid)
        if (plan_check.talking(s) or plan_check.voiceover(s)) and speaker_of(s) not in talkers:
            talkers.append(speaker_of(s))
    wanted = [(cid, cid, "refs") for cid in needed] + [(f"{cid}:talk", cid, "talk_refs") for cid in talkers]
    return wanted, {speaker_of(s) for s in plan["shots"] if plan_check.voiceover(s)}


def ref_paths(plan, work, chars=None):
    """E114: refs.json as refs_step would write it, from the kept records alone (no image fetched): what an adopted
    clip's request is recomputed with (request_identity reads each reference by its record id and sha256)."""
    out = {}
    for key, cid, field in ref_wants(plan)[0]:
        records = reference_records(cid, chars, field=field)
        if records:
            out[key] = [rel(Path(work) / "refs" / f"{rid}.jpg") for rid, _ in records]
    return out


def refs_step(plan, work, fetch=fetch_release_asset, chars=None):
    """Every reference a shot needs, verified by sha256 and resized to <= 1536 px JPEG (Flash takes up to 15 MiB)."""
    work = Path(work)
    out = {}
    wanted, silent = ref_wants(plan)
    for key, cid, field in wanted:
        records = reference_records(cid, chars, field=field)
        if not records and field == "talk_refs" and cid in silent:
            # review of #423: the front view lost his face 4 of 4 (keeper-vo/calibration.json); never in its place
            raise SystemExit(f"KEEPER_VO_NO_TALK_REF {cid} (a voice-over Keeper is generated from his `talk_refs` frame)")
        if not records:
            continue
        out[key] = []
        for rid, m in records:
            raw = work / "refs" / "raw" / rid
            raw.parent.mkdir(parents=True, exist_ok=True)
            if m.get("repo_path"):
                src = (REPO / m["repo_path"]).resolve()
                if REPO.resolve() not in src.parents or not src.is_file():
                    raise SystemExit(f"REFERENCE_PATH_REFUSED {rid}")
                shutil.copyfile(src, raw)
            else:
                if not re.fullmatch(r"[A-Za-z0-9._-]+\.(png|jpg|jpeg)", m["release_asset"]):
                    raise SystemExit(f"REFERENCE_ASSET_NAME_REFUSED {rid}")
                fetch(m["release_asset"], raw)
            if sha256(raw) != m["sha256"]:
                raise SystemExit(f"REFERENCE_SHA256_MISMATCH {rid}")
            jpg = work / "refs" / f"{rid}.jpg"
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", raw, "-vf",
                 f"scale='min({REF_SIDE},iw)':'min({REF_SIDE},ih)':force_original_aspect_ratio=decrease",
                 "-q:v", "2", "-frames:v", "1", jpg])
            out[key].append(rel(jpg))
    save(work / "refs.json", out)
    print(json.dumps({c: len(v) for c, v in out.items()}))
    return out


# ---------- generation ----------

talk_need = plan_check.talk_need     # plan and build share the talking-clip rules (E95)
talk_fits = plan_check.talk_fits


def retime(piece, params, factor, stem):
    """One line's PCM through ffmpeg atempo (pitch kept): factor > 1 shortens it. The result is cut or padded with
    silence to round(frames / factor), since atempo misses by a few ms (11.7 s -> 11.553 s for 11.55 s) and a line
    retimed to the ceiling would else be refused by it; a miss over RETIME_TRIM_MAX is refused (RETIME_TRIM_OVER).
    16-bit PCM only (lines_step refuses any other voice.wav): the frames come back as pcm_s16le under its params."""
    src, dst = Path(f"{stem}-native.wav"), Path(f"{stem}-retimed.wav")
    write_wav(src, params, piece)
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-af", f"atempo={factor:.5f}", "-ar",
         str(params.framerate), "-ac", str(params.nchannels), "-c:a", "pcm_s16le", dst])
    frames = read_wav(dst)[1]
    width = params.sampwidth * params.nchannels
    want = int(round(len(piece) / width / factor)) * width
    miss = abs(len(frames) - want) / width / params.framerate
    if miss > RETIME_TRIM_MAX:
        raise SystemExit(f"RETIME_TRIM_OVER {Path(stem).name} {miss * 1000:.0f} ms from its target "
                         f"(atempo misses by a few ms; at most {RETIME_TRIM_MAX * 1000:.0f} ms is cut or padded)")
    return frames[:want] + b"\x00" * max(0, want - len(frames))


def shot_seconds(shot, index, plan, layout, slack=0.0):
    """Clip seconds a shot is generated at. A voice-over or talking shot's come from its measured line (minus
    `slack`: E118's coverage tolerance), a scene's from the plan."""
    if plan_check.voiceover(shot):   # the gap before, his line, the gap or tail after (plan_check.vo_cover)
        covered = plan_check.vo_covered(layout["keeper"][shot["id"]]["seconds"] - slack, plan["shots"], index,
                                        is_long(plan))
        return plan_check.vo_clip_seconds(covered)
    if not plan_check.talking(shot):
        return shot["seconds"]
    return min(plan_check.TALK_CLIP[1], talk_need(talk_record(layout, shot)["seconds"] - slack))


def clip_needs(plan, layout, slack=0.0):
    """E118: {shot id: the clip seconds this machine's layout needs} (shot_seconds). The preflight records them with
    no slack; the build checks against them with MEASURE_TOLERANCE (coverage_problems)."""
    return {s["id"]: shot_seconds(s, i, plan, layout, slack) for i, s in enumerate(plan["shots"])
            if not is_window(s)}


BOUND_AUDIO = "speaks the words of the audio clip, {pronoun} lips moving in sync with the voice"
UNBOUND_SPEECH = re.compile(r"speaks to the camera, (his|her|its) lips moving clearly with every word")


def speaker_of(shot):
    return ch.NARRATOR if shot["kind"] == "keeper" else shot["speaker"]


def bind_prompt(prompt, who, chars=None):
    """E95: Pavo kept our line in the Keeper's lips only when the prompt named the reference as the speaker ("Image 1
    is the narrator") and tied the speech to the audio clip ("speaks the words of the audio clip, his lips moving in
    sync with the voice"). The plan's "speaks to the camera, his lips moving clearly with every word" is replaced by
    that clause, else the clause is added."""
    chars = chars if chars is not None else ch.registry()
    c = chars.get(who) or {}
    pronoun = c.get("pronoun", "his")
    label = "the narrator" if who == ch.NARRATOR else c.get("name", who)
    clause = BOUND_AUDIO.format(pronoun=pronoun)
    if "Image 1" not in prompt:
        prompt = f"Image 1 is {label}. {prompt}"
    if clause not in prompt:
        if UNBOUND_SPEECH.search(prompt):
            prompt = UNBOUND_SPEECH.sub(clause, prompt, count=1)
        else:
            subject = {"his": "He", "her": "She", "its": "It"}.get(pronoun, "He")
            prompt = f"{prompt.rstrip()} {subject} {clause}."
    return prompt


SHOT_ID_INPUT = re.compile(r"^[a-z0-9-]+$")


def regenerate_ids(plan, text, resume_run="", approvals=None):
    """E114: the build generates no shot (each ships the clip Claude approved), so episode.yml's `regenerate` input
    is refused whatever it names: a rejected clip is replaced only by shot-probe.yml and a new approval. [] when
    empty. check-regenerate runs it in the plan step, before any secret."""
    text = (text or "").strip()
    if text:
        raise SystemExit("SHOT_APPROVED_USE_PROBE " + text[:200] + " (the build generates nothing: shot-probe.yml, "
                         "then episode_build.py approve-shot; the build ships the approved clip)")
    return []


def digest(value):
    """sha256 of a canonical JSON form (sorted keys, no spaces): the same data always gives the same digest."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                          .encode()).hexdigest()


def shots_path(plan):
    return SHOTS_DIR / f"{plan['episode']}.json"


def load_approvals(plan, path=None):
    """E114: {shot id: approved clip} from shots/<episode>.json (written by approve-shot, merged by PR); {} if none."""
    path = Path(path) if path else shots_path(plan)
    return (load(path).get("shots") or {}) if path.exists() else {}


def period_refusal(plan, shot):
    """E108: a scene's request is refused when its prompt does not state the story's period word for word or names
    what the period excludes (plan_check.period_problems, the same function plan_check and the preflight run): None
    or the refusal."""
    if shot.get("kind") != "scene":
        return None
    per, problem = plan_check.resolve_period(plan)
    if problem:   # PERIOD_INVALID, PERIOD_AMBIGUOUS or plan_check.missing_period, word for word
        return f"{problem} (shot {shot['id']})"
    found = plan_check.period_problems(0, shot, per)
    if not found:
        return None
    detail = found[0].split(" ", 4)[-1]
    if any(p.startswith("SCENE_PERIOD_MISSING") for p in found):
        return f"SCENE_PERIOD_MISSING {shot['id']} {detail}"
    return f"SCENE_PERIOD_CONFLICT {shot['id']} {detail}"


def writing_refusal(shot):
    """E110: a scene's request is refused when its prompt asks for writing (plan_check.writing_problems, the same
    function plan_check, long_plan_check and the preflight run): None or the refusal."""
    found = plan_check.writing_problems(0, shot)
    return f"SCENE_WRITING {shot['id']} {found[0].split(' ', 4)[-1]}" if found else None


def prop_refusal(plan, shot):
    """E113: a scene's request is refused when its prompt names the ark (a hull, keel, ship, boat, vessel) without
    its look and exclusion sentences word for word, or names what that look rules out; E123, from part 9: when it says
    any of plan_check.ARK_WORDS or "crate" without ARK_PHRASE (plan_check.prop_problems, the
    same function plan_check, long_plan_check and the preflight run): None or the refusal."""
    if shot.get("id") in plan_check.ark_grandfathered(plan, plan.get("shots") or [])[0]:
        return None
    per = plan_check.period(plan)
    found = plan_check.prop_problems(0, shot, per, plan)   # E123: from part 9, the positive phrase and no ship words
    if not found:
        still = plan_check.prop_shot_problems(0, shot, plan, per)   # E122: from part 9 a prop is shown from a still
        return f"PROP_SHOT_WITHOUT_STILL {shot['id']} {still[0].split(' ', 4)[-1]}" if still else None
    detail = found[0].split(" ", 4)[-1]
    if found[0].startswith("ARK_LOOK_NOT_CANONICAL"):
        return f"ARK_LOOK_NOT_CANONICAL {shot['id']} {detail}"
    return f"ARK_LOOK_CONFLICT {shot['id']} {detail}"


# image first (owner, 27/10): the refusals frame_refusal passes on, each raised by plan_check.frame_problems
FRAME_REFUSALS = ("FRAMES_NOT_SCENE", "FRAME_FIELD_INVALID", "FRAME_LAST_WITHOUT_FIRST", "FRAMES_WITH_REFERENCES",
                  "FRAMES_WITH_AUDIO", "STILL_MISSING", "STILL_NOT_APPROVED", "STILL_PATH_REFUSED",
                  "STILL_SHA256_MISMATCH", "STILL_PROMPT_CHANGED", "STILL_ASPECT_MISMATCH", "STILL_PROMPT_REFUSED",
                  "STILL_PROP_UNREFERENCED")


def frame_refusal(plan, shot):
    """Image first: a shot's `first_frame` / `last_frame` are refused unless each names an APPROVED scene still whose
    image and prompt are the approved ones (plan_check.frame_problems, the same function plan_check and the
    preflight run): None or the refusal."""
    found = plan_check.frame_problems(0, shot, plan)
    if not found:
        return None
    code = found[0].split()[0]   # one of FRAME_REFUSALS (test_episode_build holds them equal)
    return f"{code} {shot['id']} {found[0].split(' ', 4)[-1]}"


def request(shot, index, plan, layout, refs, chars=None, route=None):
    """The Pavo call for one shot: references from the approved images (<= 5); a talking shot (the Keeper, a character
    speaking) sends its own line as input audio. God's voice-over shot sends none: no one speaks on screen. A
    voice-over Keeper shot (plan B) sends his `talk_refs` frame alone (keeper-vo/calibration.json: with the
    mouth-closed front view the landmarker found his face in 2-27 % of the frames, FACE_NOT_FOUND in 4 of 4; with
    the talking frame, facing the lens, 100 %), no audio and no speech clause."""
    talks = plan_check.talking(shot)
    prompt = shot["prompt"]
    refused = (period_refusal(plan, shot) or writing_refusal(shot) or prop_refusal(plan, shot)
               or frame_refusal(plan, shot))
    if refused:
        raise SystemExit(refused)
    if plan_check.voiceover(shot) and not refs.get(f"{ch.NARRATOR}:talk"):
        raise SystemExit(f"KEEPER_VO_NO_TALK_REF {shot['id']} (no talking frame in refs.json; the front view lost "
                         "his face 4 of 4)")
    # E95: a talking speaker is Image 1 and the prompt binds it to the audio clip. Its `talk_refs` speaking frame is
    # sent in place of its approved refs, not before them: the direct Pavo tests that passed (lips 0.578, face 0.98)
    # sent storyteller-ref.jpg alone, and no test sent it beside the mouth-closed front view that failed.
    # reference_keys is the one order (reference_problems counts the same sets at plan time, E106)
    references = [p for key, cid, field in reference_keys(shot)
                  for p in (refs.get(key) if field == VO_REFS else (refs.get(key) or refs[cid]))]
    if talks:
        prompt = bind_prompt(prompt, speaker_of(shot), chars)
    if len(references) > ch.MAX_REFS:
        raise SystemExit(f"REFERENCES_OVER_{ch.MAX_REFS} {shot['id']}")
    audios = [talk_record(layout, shot)["wav"]] if talks else []
    req = {"prompt": prompt, "seconds": shot_seconds(shot, index, plan, layout),
           "aspect_ratio": plan.get("aspect_ratio", "9:16"), "references": references or None,
           "audios": audios or None, "sound": False}
    first, last = plan_check.frame_paths(shot)
    if first:   # image first: Pavo's frames_to_video animates the approved still; the prompt gives motion and camera
        req["first_frame"] = first
        if last:
            req["last_frame"] = last
    if (route or audio_route(shot, index, plan, req, chars)) == pavo_native.NATIVE:
        req = pavo_native.native_request(req, plan, shot, index, chars)
        req["seconds"] = max(req["seconds"] if not plan_check.talking(shot) and not plan_check.voiceover(shot) else 0,
                             pavo_native.native_seconds(shot, index, plan))
    return req


def audio_route(shot, index, plan, kokoro_req, chars=None):
    """Owner 27/10: None for a shot that speaks no line; "pavo_native" (R2/R4: Pavo's own speech) on a native plan,
    "kokoro" for a line Pavo's prompt filter refuses (E129) and on every other plan. R1 wins over R4: a spoken shot
    that already has a clean clip of its Kokoro-route request (approved, in a committed shot-probe record, or in a
    clip inventory) keeps that route, so the clip is reused and never generated again."""
    chosen = pavo_native.route(plan, shot, index)
    if chosen != pavo_native.NATIVE:
        return chosen
    import shot_sources
    words = plan_spoken(shot, index, plan) if kokoro_req["audios"] else None
    kokoro = request_digest(kokoro_req, shot, words, chars)[0]
    return pavo_native.KOKORO if shot_sources.clean_clip(plan, shot["id"], kokoro) else chosen


WORD = re.compile(r"[a-z0-9']+")


def spoken_words(text):
    """The words of a spoken text, lower case, no punctuation: what the input audio says, whoever split it."""
    return WORD.findall(text.lower())


def voice_of(who, chars=None):
    return dict(VOICE) if who == ch.NARRATOR else ch.voice(who, chars)


def plan_spoken(shot, index, plan):
    """The words a talking shot's input audio carries in the plan now (plan_check.sequence)."""
    items, carried = plan_check.sequence(plan)
    return spoken_words(" ".join(items[k]["text"] for k in carried[index]))


def request_identity(shot, index, plan, layout, refs, chars=None):
    """E114: (sha256, canonical form) of the request a shot sends, independent of the machine: only what decides the
    clip. The prompt, the aspect, the sound flag (E118: never the clip seconds, nor anything else derived from a
    measured voice or layout: those are checked as coverage, coverage_problems), each reference image by its record id and the sha256 its approved record holds, and for a talking
    shot its speaker, voice and spoken words. shot-probe.yml records it with every clip, approve-shot copies it, the
    preflight computes it from the plan now (verify-preflight) and the build again before using an approved clip."""
    req = request(shot, index, plan, layout, refs, chars)
    words = plan_spoken(shot, index, plan) if req["audios"] or native_speech(req, shot) else None
    return request_digest(req, shot, words, chars)


def native_speech(req, shot):
    """The request asks Pavo for its own speech (story QA v4, owner 27/10): a spoken shot with Pavo's sound on."""
    return bool(req.get("sound")) and pavo_native.spoken(shot)


def request_digest(req, shot, words=None, chars=None):
    """(sha256, canonical form) of one request as sent (request_identity's rules); `words` are the spoken words of
    its input audio (None when it sends none). Also run on the request a build run recorded (adopt)."""
    references = []
    for path in req["references"] or []:
        rid = Path(path).stem
        rec = ch.HERE / "images" / f"{rid}.json"
        references.append({"image": rid, "sha256": load(rec).get("sha256") if rec.exists() else None})
    audio = None
    if req["audios"]:
        who = speaker_of(shot)
        audio = {"speaker": who, "voice": voice_of(who, chars), "words": list(words or [])}
    elif native_speech(req, shot):   # Pavo speaks the line itself (its voice description is in the prompt)
        audio = {"route": pavo_native.NATIVE, "speaker": pavo_native.speaker(shot), "words": list(words or [])}
    # E118: no `seconds`: a voice-over or talking shot's clip seconds are derived from measured line timing, which
    # differs between machines across a rounding boundary (genesis-08 k-insight, run 40483267526)
    canonical = {"prompt": req["prompt"], "aspect_ratio": req["aspect_ratio"], "sound": req["sound"],
                 "references": references, "audio": audio}
    frames = [req[f] for f in plan_check.FRAME_FIELDS if req.get(f)]
    if frames:   # image first: each still by its id and approved sha256 (a request without frames digests as before)
        canonical["frames"] = [{"still": Path(p).stem, "sha256": (plan_check.still_record(Path(p).stem) or {}).get(
            "sha256")} for p in frames]
    return digest(canonical), canonical


def request_digests(plan, layout, refs, chars=None):
    return {s["id"]: request_identity(s, i, plan, layout, refs, chars)[0] for i, s in enumerate(plan["shots"])
            if not is_window(s)}


def review_problems(plan, digests, approvals=None, needs=None):
    """E114: a build runs only when every shot has an approved clip made from the request the plan sends now:
    SHOT_NOT_REVIEWED (no approved clip) and SHOT_REQUEST_CHANGED (approved for another request), each naming its
    shots; E118: and long enough for what the layout needs (`needs`, SHOT_CLIP_TOO_SHORT). verify-preflight runs it
    on the committed preflight's digests and needs; generate_step on the build's own."""
    approvals = load_approvals(plan) if approvals is None else approvals
    ids = [s["id"] for s in plan["shots"] if not is_window(s)]   # a window ships its source's approved clip
    missing = [i for i in ids if i not in approvals]
    # owner 27/10 (R3): a fallback shot (licensed footage, a still in motion) is approved for its own request, the
    # shot and its exact source (shot_sources.expected_request); every other shot for the request the plan sends now
    import shot_sources
    index = {s["id"]: k for k, s in enumerate(plan["shots"])}
    changed = [i for i in ids if i in approvals and approvals[i].get("request_sha256") != shot_sources.expected_request(
        plan, plan["shots"][index[i]], index[i], approvals[i], digests)]
    out = []
    if missing:
        out.append("SHOT_NOT_REVIEWED " + " ".join(missing) + " (shot-probe.yml, Claude's frame review >= 9.5, "
                   "episode_build.py approve-shot, by PR)")
    if changed:
        out.append("SHOT_REQUEST_CHANGED " + " ".join(changed) + " (the plan's request is no longer the one the "
                   "approved clip was made from: probe and approve again)")
    if needs is not None:
        out += coverage_problems(plan, needs, {k: v for k, v in approvals.items() if k not in changed})
    return out


def coverage_problems(plan, needs, approvals):
    """E118: every approved clip is at least as long as the clip seconds the layout needs for its shot (`needs`:
    clip_needs). A clip with no recorded clip seconds, or a shot with no need, is refused too: SHOT_CLIP_TOO_SHORT."""
    short = []
    for s in plan["shots"]:
        if is_window(s):
            continue
        a = approvals.get(s["id"])
        if a is None:
            continue
        have, need = a.get("clip_seconds"), needs.get(s["id"])
        if not isinstance(have, (int, float)) or not isinstance(need, (int, float)) or have < need:
            short.append(f"{s['id']}({have}<{need})")
    return [("SHOT_CLIP_TOO_SHORT " + " ".join(short) + " (the approved clip is shorter than the clip seconds this "
             "layout needs: probe at the new length and approve again)")] if short else []


def submit(client, req, sleep=time.sleep, log=print):
    """One generation. PAVO_RATE_LIMITED and PAVO_UNREACHABLE are raised before any job exists, so that call is sent
    again after a wait (TRANSIENT); every other refusal stops the run. An uncertain submission is never resubmitted:
    its job is read with job()."""
    from client import PavoError
    used = {}
    while True:
        try:
            return client.generate_video(**req)
        except PavoError as exc:
            code = str(exc).split()[0]
            waits = TRANSIENT.get(str(exc))
            n = used.get(code, 0)
            if waits is None or n >= len(waits):
                raise ShotFailed(f"PAVO_REFUSED {code}") from None
            used[code] = n + 1
            log(f"{code}: waiting {waits[n]} s")
            sleep(waits[n])


def wait_job(client, cid, sleep=time.sleep, clock=time.monotonic):
    """completed -> the video, failed/incomplete/timeout -> None. Read errors are retried (the job runs on)."""
    from client import PavoError
    deadline, incomplete = clock() + JOB_TIMEOUT_S, 0
    while clock() < deadline:
        try:
            job = client.job(cid)
        except PavoError as exc:
            if str(exc) in ("PAVO_MEDIA_URL_REFUSED", "PAVO_RESULT_SCHEMA_CHANGED", "PAVO_SESSION_EXPIRED",
                            "PAVO_ACCESS_REFUSED", "PAVO_CREDENTIAL_REQUIRED"):
                raise ShotFailed(f"PAVO_JOB {exc} {cid}") from None
            sleep(POLL_S)
            continue
        if job["status"] == "completed":
            return job["videos"][0]
        if job["status"] == "blocked":   # E129: the prompt filter refused the words; never the same prompt again
            raise ShotFailed(f"PAVO_PROMPT_BLOCKED {cid} {job.get('blocked_reason') or 'unknown'}")
        if job["status"] == "failed":
            return None
        if job["status"] == "incomplete":
            incomplete += 1
            if incomplete >= INCOMPLETE_POLLS:
                return None
        sleep(POLL_S)
    return None


def attempts_for(shot):
    """E98: generations allowed for one shot; every caller of make_shot passes it, so a talking shot gets 6, and so
    does a voice-over Keeper shot (plan B: 1 pass in 6 direct closed-mouth clips before the probes; Pavo is free)."""
    return TALK_ATTEMPTS if plan_check.talking(shot) or plan_check.voiceover(shot) else ATTEMPTS


def make_shot(shot_id, attempt, check, attempts=ATTEMPTS):
    """attempt(n) -> (record, clip path or None); check(path) -> (flags, measures or None). A failed shot gets a NEW
    generation, at most attempts - 1 times; then the run fails naming the shot. Returns (kept path, records)."""
    records = []
    for n in range(1, attempts + 1):
        try:
            record, path = attempt(n)
        except ShotFailed as exc:   # E128: a refusal mid-shot keeps the generations already spent in the report
            exc.records = records
            raise
        if path is not None:
            record["flags"], measures = check(path)
            if measures:
                if "faces" in measures:
                    record["faces"] = measures["faces"]
                elif "still_mouth" in measures:
                    record["still_mouth"] = measures["still_mouth"]
                else:
                    record["lipsync"] = measures
            if not record["flags"]:
                records.append(record)
                return path, records
            # E94: a refused generation is kept beside the shot, so the failure-evidence job can show what failed
            kept = Path(path).with_name(f"{Path(path).stem}-fail{n}{Path(path).suffix}")
            if Path(path).is_file():
                shutil.copyfile(path, kept)
                record["clip"] = kept.name
        else:
            record.setdefault("flags", ["NO_VIDEO"])
        records.append(record)
    failed = ShotFailed(f"SHOT_FAILED {shot_id} after {attempts} generations: "
                        + "; ".join(",".join(r["flags"]) for r in records))
    failed.records = records   # the measures of every attempt reach the report (E94)
    raise failed


def clip_flags(path, aspect=None):
    """clip_check's flags; with the plan's aspect_ratio also CLIP_ASPECT_MISMATCH (E127)."""
    import clip_check
    return clip_check.check(str(path), aspect)["flags"]


def lipsync_flags(lip_python, face_model, clip, wav):
    done = subprocess.run([str(lip_python), "-I", "-B", str(HERE / "lipsync_check.py"), str(clip), str(wav),
                           str(face_model)], capture_output=True, text=True)
    try:
        result = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        # the check itself broke (E89: a missing library): not the clip's fault, so no regeneration is spent on it
        tail = " | ".join(done.stderr.strip().splitlines()[-3:])
        raise SystemExit(f"LIPSYNC_TOOL_BROKEN exit {done.returncode}: {tail[-600:]}")
    return result["flags"], {"audio": result["audio"], "mouth": result["mouth"]}


def face_flags(lip_python, face_model, clip):
    """God's voice-over clip must show no person: the pinned face landmarker on sampled frames (lipsync_check
    --faces). A face found flags GOD_SHOT_FACE (the shot is regenerated); a check that prints no JSON stops the run,
    like LIPSYNC_TOOL_BROKEN (E89), so no regeneration is spent on a broken tool."""
    done = subprocess.run([str(lip_python), "-I", "-B", str(HERE / "lipsync_check.py"), "--faces", str(clip),
                           str(face_model)], capture_output=True, text=True)
    try:
        result = json.loads(done.stdout.strip().splitlines()[-1])
        flags = list(result["flags"])
    except (ValueError, IndexError, KeyError, TypeError):
        tail = " | ".join(done.stderr.strip().splitlines()[-3:])
        raise SystemExit(f"FACE_TOOL_BROKEN exit {done.returncode}: {tail[-600:]}")
    return flags, {"faces": {k: result.get(k) for k in ("frames_sampled", "faces_found")}}


def still_mouth_flags(lip_python, face_model, clip):
    """Plan B: a voice-over Keeper clip shows no talking mouth (lipsync_check --still-mouth: the same landmarker and
    lip opening; MOUTH_TALKING over the calibrated range, FACE_NOT_FOUND under 80 % of frames). A check that prints
    no JSON stops the run (E89): no regeneration is spent on a broken tool."""
    done = subprocess.run([str(lip_python), "-I", "-B", str(HERE / "lipsync_check.py"), "--still-mouth", str(clip),
                           str(face_model)], capture_output=True, text=True)
    try:
        result = json.loads(done.stdout.strip().splitlines()[-1])
        flags = list(result["flags"])
    except (ValueError, IndexError, KeyError, TypeError):
        tail = " | ".join(done.stderr.strip().splitlines()[-3:])
        raise SystemExit(f"STILL_MOUTH_TOOL_BROKEN exit {done.returncode}: {tail[-600:]}")
    return flags, {"still_mouth": {k: result.get(k) for k in ("opening_range", "opening_motion", "window_motion",
                                                               "closed_opening", "face_frames", "frames")}}


WIDE = re.compile(r"(?i)\b(?:extreme )?wide shot\b|\baerial\b")


def risk_rank(shot):
    """E99, E127: how likely a shot is to fail, lowest first. 0 a character speaking on screen (lipsync_check on a
    face drawn from its sheet), 1 the Keeper speaking (genesis-07: 1 pass in 33 on his lines), 2 God's and the Keeper's
    voice-over shots (no face, no talking mouth), 3 wide and establishing scenes (E108/E114: the European street, the
    modern houses at the edge of the 16:9 test frame), 4 the other scenes."""
    if plan_check.talking(shot):
        return 1 if shot.get("kind") == "keeper" else 0
    if plan_check.speaking(shot) or plan_check.voiceover(shot):
        return 2
    if shot.get("establishing") or WIDE.search(str(shot.get("prompt") or "")):
        return 3
    return 4


def risk_order(shots):
    """E99: (plan index, shot) with the shots that can fail first (risk_rank), plan order within a rank. A failure
    costs minutes, not a whole build or a day of probes. A window (a long's second view of an earlier clip) is never
    generated, so it is left out."""
    return sorted(((i, s) for i, s in enumerate(shots) if not is_window(s)), key=lambda item: risk_rank(item[1]))


def in_plan_order(report, plan):
    """The report lists its shots in plan order whatever order they were generated in (risk_order, E99)."""
    shots = report["shots"]
    report["shots"] = {**{s["id"]: shots[s["id"]] for s in plan["shots"] if s["id"] in shots},
                       **{k: v for k, v in shots.items() if k not in {s["id"] for s in plan["shots"]}}}
    return report


def shot_runner(shot, index, plan, layout, refs, work, client, download, lip_python, face_model, sleep=time.sleep,
                progress=None):
    """One shot's request and the build's own attempt(n) and check(path), shared by generate_step and probe_step
    (E114: a probe generates exactly what the build would, with the same checks)."""
    req = request(shot, index, plan, layout, refs)
    talks = plan_check.talking(shot)
    native = native_speech(req, shot)   # owner 27/10 (R4): Pavo's own speech and ambience are the clip's track
    raw = work / "clips" / f"{shot['id']}-raw.mp4"
    final = work / "clips" / f"{shot['id']}.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)

    def attempt(n):
        result = submit(client, req, sleep=sleep)
        record = {"generation": n, "conversation_id": result["conversation_id"], "submission": result["status"],
                  "quoted_credits": result.get("quoted_credits")}
        if progress is not None:   # review of #475: a submitted generation is on disk before its (long) wait
            progress(record)
        if result["status"] == "rejected":
            return record, None
        video = wait_job(client, result["conversation_id"], sleep=sleep)
        if not video:
            return record, None
        download(video["url"], raw)
        record["source"] = {"width": video.get("width"), "height": video.get("height"),
                            "seconds": video.get("seconds")}
        if not talks and not native:   # Pavo adds an AAC track even with sound false: strip it
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", raw, "-an", "-c:v", "copy", final])
        else:           # a talking clip keeps our line (or Pavo's own speech) as its track
            shutil.copyfile(raw, final)
        return record, final

    voice_over = plan_check.speaking(shot) and not talks
    still = plan_check.voiceover(shot)

    aspect = plan.get("aspect_ratio", "9:16")   # E127: the shape this request asked Pavo for

    def check(path):
        flags = clip_flags(path, aspect)
        if still:       # plan B: the Keeper on screen, silent; his line plays from the voice track
            more, measures = still_mouth_flags(lip_python, face_model, path)
            return flags + more, measures
        if voice_over:  # God's voice-over shot: no lipsync, but no face may appear in it
            more, measures = face_flags(lip_python, face_model, path)
            return flags + more, measures
        if not talks:   # scenes: no lipsync check
            return flags, None
        # a native clip is judged against its own soundtrack (story QA v4 speech_checks.lipsync); its words, voice,
        # level and music are measured by speech-check before approve-shot (pavo_native.speech_verdict)
        wav = own_track(path) if native else REPO / talk_record(layout, shot)["wav"]
        more, measures = lipsync_flags(lip_python, face_model, path, wav)
        return flags + more, measures

    return req, attempt, check, raw, final


def speech_check_step(plan_path, record_path, shot_id, clip, whisper_dir, yamnet, lip_python, face_model,
                      refs_json=None, measure=None):
    """Story QA v4: measure one probed native clip (its record under evidence/shots, the clip by its sha256) and write
    the sidecar approve-shot reads, migration/evidence/shots/<episode>/speech/<clip sha256>.json. The verdict is
    recomputed at approval; nothing is approved here."""
    plan = load(plan_path)
    root = (REPO / "migration" / "evidence" / "shots").resolve()
    if root not in Path(record_path).resolve().parents:   # sweep H1: the sidecar path comes from the record
        raise SystemExit(f"SHOT_RECORD_REFUSED {record_path} (a shot-probe record under migration/evidence/shots/)")
    record = load(record_path)
    if not plan_check.EPISODE_ID.fullmatch(str(record.get("episode"))) or record.get("episode") != plan.get("episode"):
        raise SystemExit(f"PROBE_EPISODE_MISMATCH {record.get('episode')!r} != {plan.get('episode')!r}")
    entry = (record.get("shots") or {}).get(shot_id) or {}
    clip_sha = sha256(clip)
    if not any(c.get("clip_sha256") == clip_sha for c in entry.get("clips") or []):
        raise SystemExit(f"SHOT_CLIP_NOT_IN_RECORD {shot_id} {clip_sha}")
    shot = next(s for s in plan["shots"] if s["id"] == shot_id)
    if plan_check.talking(shot):
        lips, _ = lipsync_flags(lip_python, face_model, clip, own_track(clip))
    elif plan_check.voiceover(shot):
        lips, _ = still_mouth_flags(lip_python, face_model, clip)
    else:
        lips, _ = face_flags(lip_python, face_model, clip)
    who = pavo_native.speaker(shot)
    refs = voice_references(load(refs_json) if refs_json else {})
    measures = (measure or pavo_native.measure)(clip, whisper_dir, yamnet, refs, who, lips)
    out = REPO / "migration" / "evidence" / "shots" / str(record["episode"]) / "speech" / f"{clip_sha}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    words = " ".join(((entry.get("request") or {}).get("audio") or {}).get("words") or [])
    verdict = pavo_native.speech_verdict(measures, words, binding=pavo_native.voice_binding(who))
    save(out, {"shot": shot_id, "clip_sha256": clip_sha, "measures": measures, "verdict": verdict})
    return {"shot": shot_id, "sidecar": rel(out), "verdict": verdict}


def voice_references(given, voices=None):
    """Review of #476: {speaker: local clip} for the voice measure, each the exact clip voices.json holds as that
    speaker's reference (sha256), and every reference voices.json holds given (so "others" is every other speaker):
    VOICE_REFERENCE_UNSET (a file for a speaker with none), VOICE_REFERENCE_FILE_MISMATCH (another file),
    VOICE_REFERENCE_FILES_MISSING (a set reference not given). A caller's file never replaces the recorded one."""
    voices = pavo_native.load_voices() if voices is None else voices
    out = {}
    for who, path in (given or {}).items():
        want = pavo_native.voice_reference(who, voices)
        if not want:
            raise SystemExit(f"VOICE_REFERENCE_UNSET {who} (episode_build.py voice-reference first)")
        if not Path(path).is_file() or sha256(path) != want:
            raise SystemExit(f"VOICE_REFERENCE_FILE_MISMATCH {who} (not the clip voices.json holds: {want[:12]})")
        out[who] = path
    missing = sorted(w for w in voices if pavo_native.voice_reference(w, voices) and w not in out)
    if missing:
        raise SystemExit("VOICE_REFERENCE_FILES_MISSING " + " ".join(missing) + " (every reference is measured)")
    return out


VOICE_FLAGS = ("VOICE_REFERENCE_MISSING", "VOICE_REFERENCE_MISMATCH", "VOICE_OTHERS_MISSING", "VOICE_OTHERS_MISMATCH",
               "VOICE_NOT_CONSISTENT", "VOICE_NOT_DISTINCT")


def voice_reference_step(record_path, shot_id, asset, score, note, voices_path=None, today=None):
    """Review of #476 (the command voices.json names): Claude's review (>= 9.5) chooses one probed native clip as its
    speaker's reference voice, by PR. The clip is in a sealed shot-probe record, uploaded, passed the build's checks
    and every speech check but the voice ones (no reference exists yet to judge them); its sha256 is copied from the
    record, never typed. A reference replaced keeps the one before under `previous`."""
    record_path = Path(record_path)
    root = (REPO / "migration" / "evidence" / "shots").resolve()
    if root not in record_path.resolve().parents:
        raise SystemExit(f"SHOT_RECORD_REFUSED {record_path} (a shot-probe record under migration/evidence/shots/)")
    record = load(record_path)
    if not re.fullmatch(r"[0-9]{6,20}", str(record.get("run_id") or "")):
        raise SystemExit(f"SHOT_RECORD_REFUSED {record_path} (no shot-probe.yml run id)")
    entry = (record.get("shots") or {}).get(shot_id) or {}
    clip = next((c for c in entry.get("clips", []) if c.get("asset") == asset), None)
    if not clip or clip.get("uploaded") is not True or clip.get("flags"):
        raise SystemExit(f"SHOT_CLIP_NOT_IN_RECORD {shot_id} {asset} (an uploaded clip that passed its checks)")
    audio = (entry.get("request") or {}).get("audio") or {}
    if audio.get("route") != pavo_native.NATIVE:
        raise SystemExit(f"VOICE_REFERENCE_NOT_NATIVE {shot_id} (Pavo's own speech only)")
    try:
        score = float(score)
    except (TypeError, ValueError):
        raise SystemExit(f"SHOT_SCORE_INVALID {score!r}") from None
    if not (math.isfinite(score) and SHOT_REVIEW_MIN <= score <= 10) or not (note or "").strip():
        raise SystemExit(f"SHOT_SCORE_OUT_OF_RANGE {shot_id} {score} (a review score {SHOT_REVIEW_MIN}-10 and a note)")
    side = root / str(record["episode"]) / "speech" / f"{clip['clip_sha256']}.json"
    if not side.is_file():
        raise SystemExit(f"SPEECH_UNCHECKED {shot_id} (episode_build.py speech-check first)")
    flags = pavo_native.speech_verdict(load(side).get("measures") or {}, " ".join(audio.get("words") or []))
    left = [f for f in flags if f not in VOICE_FLAGS]
    if left:
        raise SystemExit(f"SPEECH_CHECKS_FAILED {shot_id} {','.join(left)}")
    path = Path(voices_path or pavo_native.VOICES)
    data = load(path)
    who = audio.get("speaker")
    if who not in data["voices"]:
        raise SystemExit(f"PAVO_VOICE_UNDESCRIBED {who}")
    old = data["voices"][who].get("reference")
    data["voices"][who]["reference"] = {
        "clip_sha256": clip["clip_sha256"], "asset": asset, "episode": record["episode"], "shot": shot_id,
        "run_id": record["run_id"], "score": score, "note": note.strip(),
        "chosen_at": today or time.strftime("%Y-%m-%d", time.gmtime()), **({"previous": old} if old else {})}
    save(path, data)
    return data["voices"][who]["reference"]


def speech_record_flags(approved, clip_sha):
    """A native speech clip ships only with the speech checks its approval recorded for this exact clip, all passed
    (story QA v4 rights.ai_video.speech_checks): SPEECH_UNCHECKED otherwise."""
    speech = approved.get("speech") or {}
    if speech.get("clip_sha256") != clip_sha or speech.get("flags") != [] or not isinstance(speech.get("gain_db"),
                                                                                           (int, float)):
        return ["SPEECH_UNCHECKED"]
    return []


def own_track(clip):
    """A native clip's own soundtrack as the mono 44.1 kHz WAV lipsync_check reads, beside the clip."""
    wav = Path(clip).with_suffix(".own.wav")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", clip, "-vn", "-ac", "1", "-ar", "44100", "-c:a",
         "pcm_s16le", wav])
    return wav


def fetch_shot_clip(approved, dst, fetch=fetch_release_asset):
    """E114: the approved clip, by its content-hash asset name, sha256 checked (never another file in its place)."""
    name = approved.get("asset") or ""
    if not SHOT_ASSET.fullmatch(name) or not name.endswith(f"-sha256-{approved.get('clip_sha256')}.mp4"):
        raise SystemExit(f"SHOT_ASSET_NAME_REFUSED {name!r}")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    fetch(name, dst)
    if sha256(dst) != approved["clip_sha256"]:
        raise SystemExit(f"SHOT_CLIP_SHA256_MISMATCH {name}")
    return dst


def generate_clips(plan, work, lip_python, face_model, ids=None, client=None, download=None, sleep=time.sleep,
                   validate=None, report_path=None):
    """shot-probe.yml's generation engine (E114: the build itself generates nothing): the named shots (all when
    None) in risk_order (E99), each through shot_runner (the build's own request and checks) and make_shot (a
    failed clip is a NEW generation, attempts_for(shot) in all, each refused one kept beside the shot, E94); the
    report in plan order. A shot that fails all its generations stops with SHOT_FAILED naming it."""
    work = Path(work)
    rel(work)
    layout, refs = load(work / "layout.json"), load(work / "refs.json")
    if validate is None:
        validate = client is None   # the real run; tests with a fake client pass validate=True to check it
    if validate:
        # E106: every request through the adapter's own offline checks before the first generation, so an invalid
        # request never waits behind the shots generated before it
        bad = request_problems(plan, layout, refs)
        if bad:
            raise SystemExit("REQUESTS_REFUSED " + "; ".join(bad))
    if client is None:
        client = budget_client()   # E128: the shared free-model budget, never an unguarded client
    if download is None:
        import pavo_footage
        download = pavo_footage.download
    report_path = Path(report_path) if report_path else work / "report.json"
    report = {"episode": plan["episode"], "shots": {}}
    wanted = None if ids is None else set(ids)
    for index, shot in risk_order(plan["shots"]):
        if wanted is not None and shot["id"] not in wanted:
            continue
        inflight = []

        def progress(rec, sid=shot["id"]):
            inflight.append(rec)
            report["shots"][sid] = dict(entry, attempts=list(inflight), in_flight=True)
            save(report_path, in_plan_order(report, plan))
        req, attempt, check, raw, final = shot_runner(shot, index, plan, layout, refs, work, client, download,
                                                      lip_python, face_model, sleep, progress)
        entry = {"kind": shot["kind"], "lines": shot.get("lines"), "request": {k: v for k, v in req.items()}}
        if plan_check.speaking(shot):
            entry.update(speaker=shot["speaker"], line=shot["line"])
        try:
            try:
                _, records = make_shot(shot["id"], attempt, check, attempts=attempts_for(shot))
            except ShotFailed as exc:
                if not (str(exc).startswith("PAVO_PROMPT_BLOCKED") and native_speech(req, shot)):
                    raise
                # E129 / owner R4: Pavo's filter refused the line's words; the block is kept by the line's words, so
                # the route is Kokoro from now on (pavo_native.route), and the shot goes again at once on that route
                code, cid, reason = (str(exc).split() + ["", "", ""])[:3]
                line = pavo_native.shot_line(plan, index)
                pavo_native.record_block(shot["id"], line, reason, cid)
                # the probe record carries it too, so shot-probe.yml's record job commits it (merge-blocks)
                entry["prompt_blocked"] = {"conversation_id": cid, "reason": reason, "shot": shot["id"],
                                           "line_sha256": pavo_native.line_digest(line),
                                           "attempts": list(inflight) or getattr(exc, "records", None)}
                inflight.clear()
                req, attempt, check, raw, final = shot_runner(shot, index, plan, layout, refs, work, client, download,
                                                              lip_python, face_model, sleep, progress)
                entry["request"] = {k: v for k, v in req.items()}
                entry["route"] = pavo_native.KOKORO
                _, records = make_shot(shot["id"], attempt, check, attempts=attempts_for(shot))
        except (ShotFailed, SystemExit) as exc:
            entry["error"] = str(exc)
            # review of #475: every submitted generation (progress), also one whose wait was cut short
            if inflight or getattr(exc, "records", None):
                entry["attempts"] = list(inflight) or exc.records
            report["shots"][shot["id"]] = entry
            save(report_path, in_plan_order(report, plan))
            raise SystemExit(str(exc))
        entry["attempts"] = records
        entry["clip"] = final.name
        report["shots"][shot["id"]] = entry
        save(report_path, in_plan_order(report, plan))
        print(json.dumps({"shot": shot["id"], "generations": len(records)}))
    return report


def generate_step(plan, work, lip_python, face_model, approvals=None, fetch=fetch_release_asset):
    """episode.yml's shots step (E114): every shot ships the clip Claude approved in shots/<episode>.json, made from
    the request the plan sends now (SHOT_NOT_REVIEWED / SHOT_REQUEST_CHANGED, as verify-preflight predicted),
    downloaded by its content hash (sha256 checked) and checked again with the build's own checks. No Pavo client,
    no generation. A clip already in WORK with the approved sha256 (episode.yml resume_run) is kept as it is."""
    work = Path(work)
    rel(work)
    approvals = load_approvals(plan) if approvals is None else approvals
    layout, refs = load(work / "layout.json"), load(work / "refs.json")
    digests = request_digests(plan, layout, refs)   # E127: windows ship their source clip
    bad = review_problems(plan, digests, approvals, clip_needs(plan, layout, MEASURE_TOLERANCE))
    if bad:
        raise SystemExit("; ".join(bad))
    report_path = work / "report.json"
    report = {"episode": plan["episode"], "shots": {}}
    for index, shot in risk_order(plan["shots"]):
        req, _, check, _, final = shot_runner(shot, index, plan, layout, refs, work, None, None, lip_python,
                                              face_model)
        approved = approvals[shot["id"]]
        entry = {"kind": shot["kind"], "lines": shot.get("lines"), "request": {k: v for k, v in req.items()}}
        if plan_check.speaking(shot):
            entry.update(speaker=shot["speaker"], line=shot["line"])
        import shot_sources
        source = approved.get("source", "pavo")   # owner 27/10 (R1-R3): the source Claude approved, recorded per shot
        if source in shot_sources.FALLBACKS:   # review of #476: the plan may have changed the shot since
            refused = shot_sources.fallback_refusal(plan, shot, index, source, plan_check.still_record(
                approved.get("still")) if source == "still_motion" else None)
            if refused:
                raise SystemExit(refused)
        if not (final.exists() and approved.get("clip_sha256") and sha256(final) == approved["clip_sha256"]):
            shot_sources.fetch_source(approved, final, fetch)
        if source in shot_sources.FALLBACKS:   # a licensed clip or a still in motion: no person, no speech
            flags, measures = clip_flags(final, plan.get("aspect_ratio", "9:16")), None
        else:
            flags, measures = check(final)
            if native_speech(req, shot):   # story QA v4: the speech checks Claude's approval was given on
                flags = flags + speech_record_flags(approved, sha256(final))
        entry["source"] = source
        entry["approved"] = {k: approved.get(k) for k in ("asset", "clip_sha256", "request_sha256", "score", "source",
                                                          "footage", "still", "url", "licence", "credit", "speech")
                             if k in approved}
        entry["checks"] = {"flags": flags, "measures": measures}
        report["shots"][shot["id"]] = entry
        if flags:
            entry["error"] = f"SHOT_APPROVED_CLIP_FAILED {shot['id']} {','.join(flags)}"
            save(report_path, in_plan_order(report, plan))
            raise SystemExit(entry["error"])
        save(report_path, in_plan_order(report, plan))
        print(json.dumps({"shot": shot["id"], "approved_clip": approved["asset"]}))
    return report


# ---------- shot probe and approval (E114) ----------

def probe_ids(plan, text, attempts):
    """shot-probe.yml's inputs, checked before any secret: ([shot ids of this plan], attempts 1-PROBE_ATTEMPTS_MAX)."""
    ids = [x.strip() for x in (text or "").split(",") if x.strip()]
    bad = [x for x in ids if not SHOT_ID_INPUT.fullmatch(x)]
    if not ids or bad:
        raise SystemExit("PROBE_SHOTS_REFUSED " + " ".join(repr(x) for x in bad) + " (a comma list of shot ids)")
    unknown = [x for x in ids if x not in {s["id"] for s in plan["shots"]}]
    if unknown:
        raise SystemExit("PROBE_UNKNOWN_SHOT " + " ".join(unknown) + f" (not a shot of {plan.get('episode')})")
    windows = [x for x in ids if any(s["id"] == x and is_window(s) for s in plan["shots"])]
    if windows:   # E127: a window is a second view of its source clip; the source is probed and approved
        raise SystemExit("PROBE_WINDOW_SHOT " + " ".join(windows) + " (a window_of shot ships its source's clip)")
    if not re.fullmatch(r"[1-9][0-9]?", str(attempts).strip()) or not 1 <= int(attempts) <= PROBE_ATTEMPTS_MAX:
        raise SystemExit(f"PROBE_ATTEMPTS_REFUSED {attempts!r} (1-{PROBE_ATTEMPTS_MAX})")
    return list(dict.fromkeys(ids)), int(attempts)


def shot_asset_name(episode, shot_id, clip_sha):
    return f"shot-{episode}-{shot_id}-sha256-{clip_sha}.mp4"


def probe_step(plan, work, lip_python, face_model, out, ids, attempts, client=None, download=None,
               sleep=time.sleep, sheet=None):
    """E114, shot-probe.yml: `attempts` rounds of the build's own generation engine (generate_clips: the same
    request, checks and regenerations) on the named shots. Each round's clean clip is kept in OUT under its
    content-hash asset name with a frame sheet; every generation's checks, refused ones included, and the shot's
    request sha256 go to OUT/probe.json. A shot that fails a round is recorded and the others go on. Nothing is
    approved here."""
    work, out = Path(work), Path(out)
    layout, refs = load(work / "layout.json"), load(work / "refs.json")
    if client is None:
        bad = request_problems(plan, layout, refs)
        if bad:
            raise SystemExit("REQUESTS_REFUSED " + "; ".join(bad))
    sheet = sheet or sheet_step
    out.mkdir(parents=True, exist_ok=True)
    record = {"episode": plan["episode"], "plan_sha256": None, "attempts": attempts, "shots": {}}
    index = {s["id"]: i for i, s in enumerate(plan["shots"])}
    for sid in ids:
        sha, canonical = request_identity(plan["shots"][index[sid]], index[sid], plan, layout, refs)
        record["shots"][sid] = {"kind": plan["shots"][index[sid]]["kind"], "request_sha256": sha,
                                "request": canonical, "clips": [],
                                "clip_seconds": shot_seconds(plan["shots"][index[sid]], index[sid], plan, layout)}
    inflight = None   # review of #475: (shot, round) whose generations are not in the record yet
    blocked = set()   # E129 (review of #476): a shot whose prompt Pavo's filter refused is never sent again this run
    try:
        for n in range(1, attempts + 1):
            for _, shot in risk_order([plan["shots"][index[sid]] for sid in ids]):
                sid, entry = shot["id"], record["shots"][shot["id"]]
                if sid in blocked:
                    continue
                inflight = (sid, n)
                try:
                    report = generate_clips(plan, work, lip_python, face_model, ids=[sid], client=client,
                                            download=download, sleep=sleep, validate=False,
                                            report_path=work / f"probe-{sid}-{n}.json")
                except SystemExit as exc:
                    if not str(exc).startswith(("SHOT_FAILED", "PAVO_REFUSED", "PAVO_JOB", "PAVO_PROMPT_BLOCKED")):
                        raise   # a broken tool or a refused request stops the probe (E89)
                    failed = load(work / f"probe-{sid}-{n}.json")["shots"].get(sid, {})
                    entry["clips"].append({"round": n, "error": str(exc), "generations": failed.get("attempts", [])})
                    if failed.get("prompt_blocked"):
                        record.setdefault("prompt_blocks", []).append(failed["prompt_blocked"])
                    if str(exc).startswith("PAVO_PROMPT_BLOCKED"):   # the same prompt would be refused again
                        blocked.add(sid)
                        entry["blocked"] = str(exc)
                    inflight = None
                    save(out / "probe.json", record)
                    stop = budget_stop(exc)
                    if stop:   # E128: the budget is spent or a quota stop is suspected: no other shot may submit
                        record["stopped"] = str(exc)
                        save(out / "probe.json", record)
                        raise SystemExit(f"{stop} probe stopped at {sid} round {n}: {exc}")
                    continue
                built = report["shots"][sid]
                if built.get("prompt_blocked"):   # E129: made on the Kokoro route after the filter's block
                    record.setdefault("prompt_blocks", []).append(built["prompt_blocked"])
                    sha, canonical = request_identity(shot, index[sid], plan, layout, refs)
                    entry.update(request_sha256=sha, request=canonical, prompt_blocked=built["prompt_blocked"],
                                 clip_seconds=shot_seconds(shot, index[sid], plan, layout))
                path = work / "clips" / built["clip"]
                clip_sha = sha256(path)
                asset = shot_asset_name(plan["episode"], sid, clip_sha)
                shutil.copyfile(path, out / asset)
                sheet(out / asset, out / f"{sid}-{n}.jpg")
                last = built["attempts"][-1]
                entry["clips"].append({"round": n, "asset": asset, "clip_sha256": clip_sha, "flags": last["flags"],
                                       "generations": built["attempts"], "sheet": f"{sid}-{n}.jpg"})
                inflight = None
                save(out / "probe.json", record)
    finally:
        if inflight is not None:   # a timeout, a cancel or an unexpected error: what was submitted still counts
            sid, n = inflight
            part = work / f"probe-{sid}-{n}.json"
            try:
                gens = (load(part)["shots"].get(sid) or {}).get("attempts", []) if part.is_file() else []
            except (OSError, ValueError):
                gens = []
            record["shots"][sid]["clips"].append({"round": n, "error": "PROBE_INTERRUPTED", "generations": gens})
            save(out / "probe.json", record)
    for sid in ids:
        print(json.dumps({"shot": sid, "clips": [c.get("asset") or c.get("error") for c in
                                                 record["shots"][sid]["clips"]]}))
    save(out / "probe.json", record)
    return record


def probe_assets(out, episode, run_id=None, dst=None):
    """shot-probe.yml's record job (no secret): every clip of OUT/probe.json is checked against its name
    (shot_asset_name) and its sha256: [asset names]. With run_id and dst, after the upload: the record marked with
    the run and each uploaded clip, written to dst (the only record approve-shot accepts)."""
    out = Path(out)
    if not (out / "probe.json").is_file():
        raise SystemExit("NO_PROBE_RECORD (the probe job left no record: read its log)")
    record = load(out / "probe.json")
    if record.get("episode") != episode:
        raise SystemExit(f"PROBE_EPISODE_MISMATCH {record.get('episode')} != {episode}")
    names = []
    for sid, entry in record["shots"].items():
        for clip in entry["clips"]:
            if not clip.get("asset"):
                continue
            if clip["asset"] != shot_asset_name(episode, sid, clip.get("clip_sha256")) or \
                    sha256(out / clip["asset"]) != clip["clip_sha256"]:
                raise SystemExit(f"SHOT_CLIP_SHA256_MISMATCH {clip['asset']}")
            names.append(clip["asset"])
            if run_id:
                clip["uploaded"] = True
                clip["sheet"] = f"{run_id}-{clip['sheet']}"   # the name it is pushed under
    if run_id and dst:
        if not re.fullmatch(r"[0-9]{6,20}", str(run_id)):
            raise SystemExit("PROBE_RUN_REFUSED")
        record["run_id"] = str(run_id)
        save(dst, record)
    return sorted(set(names))


def run_spoken(run_dir, layout, shot):
    """The words a build run actually sent as a talking shot's input audio: the run's compose-timeline sentences
    inside that shot's line (layout start..end), in order. None when the run kept no timeline."""
    path = Path(run_dir) / "compose-timeline.json"
    if not path.is_file():
        return None
    rec = talk_record(layout, shot)
    texts = [x["text"] for x in load(path)["sentences"]
             if rec["start"] - 1e-6 <= (x["start"] + x["end"]) / 2 <= rec["end"] + 1e-6]
    return spoken_words(" ".join(texts))


def adopt_step(plan, run_dir, lip_python, face_model, out, ids, source_run, sheet=None):
    """E114: clips a build run already made and Claude's review approved (genesis-08 runs 40438106839, 40460764662),
    turned into a probe record without generating them again. For each named shot, the request that run recorded
    in its report.json (prompt, seconds, references) and the words its input audio carried (its compose-timeline)
    are digested and refused unless they equal the request the plan sends now (SHOT_REQUEST_CHANGED: a line or a
    prompt edited after the run); the build's checks run again; the clip is kept under its content-hash name with
    a frame sheet. approve-shot then approves it like any probed clip."""
    run_dir, out = Path(run_dir), Path(out)
    report, layout = load(run_dir / "report.json"), load(run_dir / "layout.json")
    if report.get("episode") != plan["episode"]:
        raise SystemExit(f"ADOPT_EPISODE_MISMATCH {report.get('episode')} != {plan['episode']}")
    work = REPO / ".episode" / plan["episode"]   # where the run's layout points its input audio (episode.yml WORK)
    refs = ref_paths(plan, work)
    sheet = sheet or sheet_step
    out.mkdir(parents=True, exist_ok=True)
    record = {"episode": plan["episode"], "adopted_from": str(source_run), "shots": {}}
    index = {s["id"]: i for i, s in enumerate(plan["shots"])}
    changed = []
    for sid in ids:
        shot, i = plan["shots"][index[sid]], index[sid]
        built = (report.get("shots") or {}).get(sid) or {}
        clip = run_dir / "clips" / f"{sid}.mp4"
        if built.get("error") or not built.get("request") or not clip.is_file():
            raise SystemExit(f"ADOPT_CLIP_MISSING {sid} (no clean clip of this shot in run {source_run})")
        sent = built["request"]
        words = run_spoken(run_dir, layout, shot) if sent.get("audios") else None
        if sent.get("audios") and words is None:
            raise SystemExit(f"ADOPT_CLIP_MISSING {sid} (run {source_run} kept no compose-timeline.json)")
        made = request_digest(sent, shot, words)[0]
        now, canonical = request_identity(shot, i, plan, layout, refs)
        if made != now:
            changed.append(sid)
            continue
        if plan_check.talking(shot):   # the run's input audio, back where its layout points, for lipsync_check
            wav = REPO / talk_record(layout, shot)["wav"]
            if not wav.exists():
                wav.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(run_dir / "clips" / wav.name, wav)
        _, _, check, _, _ = shot_runner(shot, i, plan, layout, refs, work, None, None, lip_python, face_model)
        flags, measures = check(clip)
        clip_sha = sha256(clip)
        asset = shot_asset_name(plan["episode"], sid, clip_sha)
        shutil.copyfile(clip, out / asset)
        sheet(out / asset, out / f"{sid}-adopted.jpg")
        record["shots"][sid] = {"kind": shot["kind"], "request_sha256": now, "request": canonical,
                                "clip_seconds": sent.get("seconds"), "clips": [{"round": "adopted", "source_run": str(source_run), "asset": asset,
                                           "clip_sha256": clip_sha, "flags": flags, "measures": measures,
                                           "sheet": f"{sid}-adopted.jpg"}]}
        print(json.dumps({"shot": sid, "adopted": asset, "flags": flags}))
    save(out / "probe.json", record)
    if changed:
        raise SystemExit("SHOT_REQUEST_CHANGED " + " ".join(changed) + f" (run {source_run} made these clips from "
                         "another request: probe them with shot-probe.yml)")
    return record


def approve_shot(record_path, shot_id, asset, score, note, shots_dir=None, today=None):
    """E114: Claude's frame review approves one probed clip (>= SHOT_REVIEW_MIN) into shots/<episode>.json, copied
    from the probe record so nobody hand-edits a hash. Refused: a record outside evidence/shots/, a clip that failed
    the build's checks, a score under the floor, an empty note."""
    record_path = Path(record_path)
    root = (REPO / "migration" / "evidence" / "shots").resolve()
    if root not in record_path.resolve().parents:
        raise SystemExit(f"SHOT_RECORD_REFUSED {record_path} (a shot-probe record under migration/evidence/shots/)")
    record = load(record_path)
    if not re.fullmatch(r"[0-9]{6,20}", str(record.get("run_id") or "")):
        raise SystemExit(f"SHOT_RECORD_REFUSED {record_path} (no shot-probe.yml run id: only its record job's "
                         "record is approved)")
    entry = (record.get("shots") or {}).get(shot_id)
    clip = next((c for c in (entry or {}).get("clips", []) if c.get("asset") == asset), None)
    if not clip:
        raise SystemExit(f"SHOT_CLIP_NOT_IN_RECORD {shot_id} {asset}")
    if clip.get("uploaded") is not True:
        raise SystemExit(f"SHOT_CLIP_NOT_UPLOADED {shot_id} {asset} (shot-probe.yml's record job uploads every clip)")
    if clip.get("flags"):
        raise SystemExit(f"SHOT_CHECKS_FAILED {shot_id} {','.join(clip['flags'])} (the build would refuse this clip)")
    try:
        score = float(score)
    except (TypeError, ValueError):
        raise SystemExit(f"SHOT_SCORE_INVALID {score!r}") from None
    if not (math.isfinite(score) and SHOT_REVIEW_MIN <= score <= 10):
        raise SystemExit(f"SHOT_SCORE_OUT_OF_RANGE {shot_id} {score} (a review score {SHOT_REVIEW_MIN}-10)")
    if not (note or "").strip():
        raise SystemExit(f"SHOT_NOTE_MISSING {shot_id} (what the frame review saw)")
    # E118: the seconds the clip was generated at (coverage_problems); a record from before E118 kept them in its
    # request's canonical form
    seconds = entry.get("clip_seconds", (entry.get("request") or {}).get("seconds"))
    if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
        raise SystemExit(f"SHOT_CLIP_SECONDS_UNKNOWN {shot_id} (the probe record holds no clip seconds)")
    speech = None
    audio = (entry.get("request") or {}).get("audio") or {}
    if audio.get("route") == pavo_native.NATIVE:
        # story QA v4 (owner 27/10, R4): a clip that keeps Pavo's speech is approved only with its speech checks
        # measured on this exact clip (episode_build.py speech-check) and passed, the verdict recomputed here
        side = root / str(record["episode"]) / "speech" / f"{clip['clip_sha256']}.json"
        if not side.is_file():
            raise SystemExit(f"SPEECH_UNCHECKED {shot_id} {asset} (episode_build.py speech-check first: "
                             f"{rel(side)})")
        speech = pavo_native.speech_record(clip["clip_sha256"], load(side).get("measures") or {},
                                           " ".join(audio.get("words") or []),
                                           binding=pavo_native.voice_binding(audio.get("speaker")))
        if speech["flags"]:
            raise SystemExit(f"SPEECH_CHECKS_FAILED {shot_id} {','.join(speech['flags'])}")
    path = Path(shots_dir or SHOTS_DIR) / f"{record['episode']}.json"
    data = load(path) if path.exists() else {"episode": record["episode"], "shots": {}}
    data["shots"][shot_id] = {"asset": asset, "clip_sha256": clip["clip_sha256"],
                              "request_sha256": entry["request_sha256"], "clip_seconds": seconds, "score": score, "note": note.strip(),
                              "probe_record": rel(record_path), "run_id": record.get("run_id"),
                              "source_run": clip.get("source_run"),
                              "approved_at": today or time.strftime("%Y-%m-%d", time.gmtime())}
    if speech:
        data["shots"][shot_id]["speech"] = speech
    data["shots"] = dict(sorted(data["shots"].items()))
    save(path, data)
    return data["shots"][shot_id]


# ---------- compose ----------

def split_scene(span, members, clip_seconds):
    """Time for each scene shot of one run: establishing shots hold <= 2 s, the rest shares by clip length."""
    est = [m for m in members if m.get("establishing")]
    if len(est) == len(members):
        return [span / len(members)] * len(members)
    hold = min(ESTABLISHING_HOLD, span / len(members))
    rest = span - hold * len(est)
    weight = sum(clip_seconds[m["id"]] for m in members if not m.get("establishing"))
    return [hold if m.get("establishing") else rest * clip_seconds[m["id"]] / weight for m in members]


def cuts(clip, start, end, clip_len):
    """One scene's span cut every <= 4 s. Windows spread over the clip (a jump between them) when it is long enough,
    else contiguous and slowed at most MAX_SLOW."""
    piece = end - start
    n = max(1, math.ceil(piece / CUT_MAX - 1e-9))
    length = piece / n
    out = []
    if n * length <= clip_len:
        step = (clip_len - length) / (n - 1) if n > 1 else 0.0
        for i in range(n):
            out.append({"clip": clip, "start": round(start + i * length, 3), "end": round(start + (i + 1) * length, 3),
                        "src_start": round(min(i * step, clip_len - length), 3), "speed": 1.0})
    else:
        have = clip_len / n
        factor = length / have
        if factor > MAX_SLOW:
            raise SystemExit(f"CLIP_TOO_SHORT {clip} ({clip_len:.2f} s for {piece:.2f} s)")
        for i in range(n):
            out.append({"clip": clip, "start": round(start + i * length, 3), "end": round(start + (i + 1) * length, 3),
                        "src_start": round(i * have, 3), "speed": round(factor, 4)})
    out[-1]["end"] = round(end, 3)
    return out


def compose_shots(plan, layout, clips, clip_seconds):
    """short_engine shots tiling [0, total]. A talking shot (the Keeper, a character speaking) spans exactly its
    line's audio (from its first word to its last), from the start of its clip at normal speed, so the lips meet the
    voice (`talk`: the line's span, checked again by short_engine); it covers the silent gap only when the next shot
    talks too, and the closing one covers the tail; beyond its clip (~0.45 s past the speech, E95) its last frame is
    held (`hold`, <= TALK_HOLD_MAX). Scene runs (God's voice-over shots among them) fill the time between, cut every
    2-4 s."""
    shots, total, lines = plan["shots"], layout["total"], layout["lines"]
    _, carried = plan_check.sequence(plan)
    runs = plan_check.groups(shots, carried)
    out, cursor = [], 0.0
    for r, (a, b, ln) in enumerate(runs):
        last = r == len(runs) - 1
        if plan_check.voiceover(shots[a]):
            # plan B: one unbroken clip of the silent Keeper over his line, from where the shot before ended (his
            # first word, or the gap after a talking shot) to the next line (or the end), from its 0 s; his line is
            # narration in the voice track (captions from the timeline). A clip shorter than that is slowed at most
            # MAX_SLOW, never cut or held
            s = shots[a]
            before, after = plan_check.vo_cover(shots, a)   # the one rule plan_check and lines_step cap by
            start = lines[ln[0]]["start"] - before
            end = total if last else lines[ln[-1]]["end"] + after
            if abs(start - cursor) > 1e-3 or (not last and abs(end - lines[runs[r + 1][2][0]]["start"]) > 1e-3):
                raise SystemExit(f"KEEPER_VO_NOT_ON_HIS_LINE {s['id']} (cover {before}/{after} s off the run's "
                                 f"{cursor:.3f} s start or the next line)")
            span = end - cursor
            factor = max(1.0, span / clip_seconds[s["id"]])
            if factor > MAX_SLOW + 1e-9:
                raise SystemExit(f"KEEPER_CLIP_SHORT {s['id']} ({clip_seconds[s['id']]:.2f} s for {span:.2f} s, slowed "
                                 f"at most {MAX_SLOW})")
            out.append({"clip": clips[s["id"]], "start": round(cursor, 3), "end": round(end, 3), "src_start": 0.0,
                        "speed": round(factor, 4) if factor > 1.0 else 1.0, "shot": s["id"], "kind": "keeper-vo"})
            cursor = end
            continue
        if plan_check.talking(shots[a]):
            s = shots[a]
            kind = "keeper" if s["kind"] == "keeper" else "speaker"
            start, end = lines[ln[0]]["start"], lines[ln[-1]]["end"]
            talk = {"start": round(start, 3), "end": round(end, 3)}
            if abs(start - cursor) > 1e-3:
                raise SystemExit(f"{kind.upper()}_NOT_ON_HIS_LINE {s['id']}")
            if last:
                end = total
            elif plan_check.talking(shots[runs[r + 1][0]]):
                end = lines[runs[r + 1][2][0]]["start"]   # covers the silent gap before the next talking line
            # E95: the clip is only ~0.45 s longer than the speech; the gap or the closing tail beyond it is its last
            # frame held (at most TALK_HOLD_MAX; the closing fade-out covers the tail)
            hold = max(0.0, (end - start) - clip_seconds[s["id"]])
            # the hold is written HOLD_MARGIN longer than the time it covers, and short_engine checks that written
            # value against HOLD_MAX, so it is the one checked here (review of #408: else CLIP_TOO_SHORT later)
            held = round(hold + HOLD_MARGIN, 3) if hold > 1e-3 else 0.0
            if held > plan_check.TALK_HOLD_MAX or clip_seconds[s["id"]] + 1e-3 < talk["end"] - talk["start"]:
                raise SystemExit(f"{kind.upper()}_CLIP_SHORT {s['id']} ({clip_seconds[s['id']]:.2f} s for "
                                 f"{end - start:.2f} s, a hold of at most {plan_check.TALK_HOLD_MAX} s)")
            shot_out = {"clip": clips[s["id"]], "start": round(start, 3), "end": round(end, 3), "src_start": 0.0,
                        "speed": 1.0, "shot": s["id"], "kind": kind, "talk": talk}
            if held:
                shot_out["hold"] = held
            out.append(shot_out)
            cursor = end
            continue
        end = total if last else lines[runs[r + 1][2][0]]["start"]
        members = shots[a:b + 1]
        t = cursor
        for m, share in zip(members, split_scene(end - cursor, members, clip_seconds)):
            for c in cuts(clips[m["id"]], t, t + share, clip_seconds[m["id"]]):
                out.append(dict(c, shot=m["id"], kind="scene"))
            t += share
        out[-1]["end"] = round(end, 3)
        cursor = end
    return out


def native_voice(plan, work, layout, audio_clips, seconds, approvals=None):
    """Story QA v4 (owner 27/10): (voice track, clip seconds from each speech onset, {shot: onset}). Our track with
    each approved native clip's own speech and ambience laid at its line (one gain to the common level, short fades,
    a continuous ambience bed: pavo_native.premix); a talking cut then starts its clip at the speech onset so the lips
    meet the words. Any other plan: our track as it is."""
    work = Path(work)
    spans = native_spans(plan, approvals)
    if not spans:
        return str(work / "narration.wav"), seconds, {}
    approvals = load_approvals(plan) if approvals is None else approvals
    places = pavo_native.placements(plan, layout, spans, audio_clips, approvals)
    mixed = work / "narration-native.wav"
    pavo_native.premix(work / "narration.wav", places, mixed, layout["total"])
    onsets = {sid: onset for sid, (_, onset, _) in spans.items()}
    return str(mixed), {k: v - onsets.get(k, 0.0) for k, v in seconds.items()}, onsets


def shift_onsets(cuts, onsets):
    """A native talking cut plays its clip from the speech onset (pavo_native: the first word came at 0-1.5 s)."""
    for c in cuts:
        if "talk" in c and c.get("shot") in onsets:
            c["src_start"] = round(onsets[c["shot"]], 3)
    return cuts


def measure_lufs(path):
    done = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                          capture_output=True, text=True)
    found = re.findall(r"I:\s+(-?[0-9.]+) LUFS", done.stderr)
    return float(found[-1]) if found else None


def compose_step(plan, work, music, out):
    import clip_check
    import short_engine
    work = Path(work)
    layout = load(work / "layout.json")
    clips = {s["id"]: str(work / "clips" / f"{s['id']}.mp4") for s in plan["shots"]}
    seconds = {k: short_engine.duration(v) for k, v in clips.items()}
    voice, seconds, onsets = native_voice(plan, work, layout, clips, seconds)
    shots = shift_onsets(compose_shots(plan, layout, clips, seconds), onsets)
    compose_plan = {"voice": voice, "timeline": str(work / "compose-timeline.json"),
                    "music": str(music), "music_offset": float(plan.get("music_offset", 600.0)), "tail": TAIL,
                    "shots": shots}
    save(work / "compose-plan.json", compose_plan)
    short_engine.main(str(work / "compose-plan.json"), str(out))
    runs = clip_check.black_runs(str(out))
    length = clip_check.probe(str(out))["seconds"]
    dip = round(layout["total"] - FADE_OUT, 2)
    unexpected = clip_check.unexpected(runs, [dip], length)
    lufs = measure_lufs(out)
    report_path = work / "report.json"
    report = load(report_path) if report_path.exists() else {"episode": plan["episode"], "shots": {}}
    report["composed"] = {
        "output_sha256": sha256(out), "seconds": round(length, 2), "frame": [short_engine.W, short_engine.H],
        "black_check": {"black_starts": runs, "unexpected": unexpected, "intended_dips": [dip]},
        "lufs": lufs, "keeper_share": layout["keeper_share"], "lesson_share": layout.get("lesson_share"),
        "spoken": {**layout.get("speakers", {}), **layout.get("voice_over", {})},
        "establishing_share": establishing_share(plan, shots, layout["total"]),
        "cuts": len(shots), "timeline": [{k: c[k] for k in ("shot", "kind", "start", "end", "src_start", "speed")}
                                         for c in shots]}
    save(report_path, report)
    problems = []
    if unexpected:
        problems.append(f"BLACK_FRAMES {unexpected}")
    if lufs is None or not LUFS[0] <= lufs <= LUFS[1]:
        problems.append(f"LOUDNESS {lufs} LUFS (-14 +-1)")
    if report["composed"]["establishing_share"] > plan_check.ESTABLISHING_SHARE_MAX:
        problems.append("ESTABLISHING_SHARE")
    print(json.dumps({k: report["composed"][k] for k in ("output_sha256", "seconds", "lufs", "keeper_share", "cuts")}))
    if problems:
        raise SystemExit("COMPOSE_REFUSED " + "; ".join(problems))
    return report


def sheet_step(video, sheet, frames=20):
    import short_engine
    d = short_engine.duration(video)
    tmp = Path(sheet).parent / "sheet-frames"
    tmp.mkdir(parents=True, exist_ok=True)
    for k in range(frames):
        t = d * (k + 0.5) / frames
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-vf",
             f"scale=216:384,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{t:.1f}s':"
             "x=6:y=6:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.6", tmp / f"f{k:02d}.jpg"])
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp / "f%02d.jpg", "-vf", "tile=5x4", "-frames:v", "1",
         "-q:v", "3", sheet])
    safe_rmtree(tmp, Path(sheet).parent)


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    cmd = argv[1]
    if cmd == "sheet" and len(argv) == 4:
        return sheet_step(argv[2], argv[3])
    if cmd == "check-regenerate" and len(argv) == 3:
        regenerate_ids(load(argv[2]), os.environ.get("REGENERATE", ""))   # E114: any value is refused
        print(json.dumps({"regenerate": []}))
        return 0
    if cmd == "probe-assets" and len(argv) in (4, 6):   # shot-probe.yml's record job: OUT EP [RUN_ID DST]
        for name in probe_assets(argv[2], argv[3], *(argv[4:6] if len(argv) == 6 else ())):
            print(name)
        return 0
    if cmd == "approve-shot" and len(argv) == 7:   # E114: RECORD SHOT ASSET SCORE NOTE
        print(json.dumps(approve_shot(argv[2], argv[3], argv[4], argv[5], argv[6]), ensure_ascii=False))
        return 0
    if cmd == "check-probe" and len(argv) == 3:    # shot-probe.yml's inputs (env SHOTS, ATTEMPTS), before any secret
        ids, n = probe_ids(load(argv[2]), os.environ.get("SHOTS", ""), os.environ.get("ATTEMPTS", ""))
        if is_long(load(argv[2])):   # E127: a long's shots are probed only from a clean preflight of this plan
            import long_preflight
            refused = long_preflight.probe_gate(argv[2])
            if refused:
                raise SystemExit(refused)
        print(json.dumps({"shots": ids, "attempts": n}))
        return 0
    if cmd == "voice-reference" and len(argv) == 7:   # RECORD SHOT ASSET SCORE NOTE (review of #476)
        print(json.dumps(voice_reference_step(*argv[2:7]), ensure_ascii=False))
        return 0
    if cmd == "merge-blocks" and len(argv) == 4:   # shot-probe.yml's record job: PROBE_JSON BLOCKS_FILE (E129)
        print(json.dumps({"added": pavo_native.merge_blocks(load(argv[2]), argv[3])}))
        return 0
    if cmd in ("sources", "approve-source"):   # owner 27/10 (R1-R3): per-shot sources, Claude's approval of one
        import shot_sources
        return shot_sources.main(argv)
    if cmd == "speech-check" and len(argv) in (10, 11):   # story QA v4: PLAN RECORD SHOT CLIP WHISPER YAMNET LIP FACE [REFS]
        print(json.dumps(speech_check_step(*argv[2:10], refs_json=argv[10] if len(argv) == 11 else None)))
        return 0
    if cmd in ("preflight", "verify-preflight", "check-record"):   # E106: before any dispatch (episode_preflight.py)
        import episode_preflight
        return episode_preflight.main(argv)
    if cmd == "probe-queue" and len(argv) in (3, 4):   # E127: the next shots to probe, riskiest first (resume)
        import long_preflight
        return long_preflight.queue_main(argv[2], argv[3] if len(argv) == 4 else None)
    plan = load(argv[2])
    result = check_plan(plan)   # E127: long_plan_check for a long
    if result["problems"] or result["pending"]:
        raise SystemExit("PLAN_REFUSED " + "; ".join(result["problems"] + result["pending"]))
    if cmd == "voice-script" and len(argv) == 4:
        save(Path(argv[3]) / "voice-script.json", voice_script(plan))
    elif cmd == "lines" and len(argv) == 4:
        lines_step(plan, argv[3])
    elif cmd == "refs" and len(argv) == 4:
        refs_step(plan, argv[3])
    elif cmd == "generate" and len(argv) == 6:   # E114: the approved clips only; no Pavo, no secret
        generate_step(plan, argv[3], argv[4], argv[5])
    elif cmd == "probe" and len(argv) == 7:       # E114: shot-probe.yml (PAVO_TOKEN, SHOTS, ATTEMPTS from the env)
        if not os.environ.get("PAVO_TOKEN"):
            raise SystemExit("PAVO_CREDENTIAL_REQUIRED")
        ids, n = probe_ids(plan, os.environ.get("SHOTS", ""), os.environ.get("ATTEMPTS", ""))
        used = os.environ.get("PAVO_BUDGET_USED", "")
        ledger = seed_budget(argv[3], used)   # E128: before any generation; refused without the guard's count
        os.environ["PAVO_IMAGE_LEDGER"] = str(ledger)
        import signal   # review of #475: a cancel (SIGTERM) unwinds through probe_step's finally, so the record is kept
        signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit("PROBE_TERMINATED (SIGTERM)"))
        try:
            record = probe_step(plan, argv[3], argv[4], argv[5], argv[6], ids, n)
        finally:
            out = Path(argv[6]) / "probe.json"
            if out.is_file():
                rec = load(out)
                spent = sum(d.get("generated", 0) for d in load(ledger)["days"].values()) - int(used)
                rec.update(plan_sha256=sha256(argv[2]), pavo_budget={"units_before": int(used), "units_this_run": spent})
                save(out, rec)
    elif cmd == "adopt" and len(argv) == 8:       # E114: ADOPT PLAN RUN_DIR LIP FACE OUT SOURCE_RUN (env SHOTS)
        ids, _ = probe_ids(plan, os.environ.get("SHOTS", ""), 1)
        if not re.fullmatch(r"[0-9]{6,20}", argv[7]):
            raise SystemExit("ADOPT_RUN_REFUSED")
        record = adopt_step(plan, argv[3], argv[4], argv[5], argv[6], ids, argv[7])
        record["plan_sha256"] = sha256(argv[2])
        save(Path(argv[6]) / "probe.json", record)
    elif cmd == "compose" and len(argv) == 6:
        compose_step(plan, argv[3], argv[4], argv[5])
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
