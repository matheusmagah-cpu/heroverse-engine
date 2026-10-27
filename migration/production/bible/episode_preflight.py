#!/usr/bin/env python3
"""Preflight of a Short's plan before episode.yml is dispatched (owner, 2026-10-26: "an error must never repeat";
E106). It runs locally, with no Actions minute and no credit, everything the build can know before its first Pavo
generation, with the build's own functions, and says which new setups need a direct 0-credit Pavo probe first.

  episode_build.py preflight PLAN [--voice VOICE_PYTHON PREPARED_WORK] [--refs] [--write]
  episode_build.py verify-preflight PLAN       exit 0 only when the committed report is PASS for this exact plan
                                               and every shot has an approved clip of its request (E114)

Steps (each one is the build's own code, not a copy):
  1. plan_check --strict: the grammar, the path episode.yml takes, and the build predicted on the estimate
     (episode_build.predict, reference_problems).
  2. characters: every character the plan uses, its status, kept references, speaking frame and voice; a DRAFT one
     names what it still needs (reference sheet on cf-images, Claude's review, a PR setting APPROVED).
  3. cf-images: images recorded on main today (UTC) against the free allocation (about CF_DAILY_IMAGES a day), and the
     images a missing reference sheet would take.
  4. voice (--voice): pilot_render.py voice with the pinned Kokoro model in a prepared work directory (its `source/`
     and `models/`), then episode_build lines on the measured lines: retime, talking records, shares and length as
     the build measures them, and the compose predicted on that layout. Each line's measured pace is reported.
  5. requests (--refs, after the voice): refs_step fetches and checks the reference images, and every shot's Pavo
     request goes through the adapter's own offline checks (episode_build.request_problems).
  6. talking lines: each talking shot's line, with its speaker, the reference images it sends and the prompt binding,
     must have a direct 0-credit Pavo probe in evidence/pavo/setups.json (lips-check passes over generations on that
     line: #419 showed the rate belongs to the line, not to the setup). None is PROBE_REQUIRED; a rate whose chance
     within TALK_ATTEMPTS is under MIN_SHOT_CHANCE is PROBE_RATE_LOW. The run's chance is reported.
The report is PASS only when every step ran and found nothing. --write saves it to
evidence/preflight/<episode>.json (bound to the plan's and characters.json's sha256); episode.yml runs
verify-preflight on main before any secret is used, so a build without a PASS preflight of that exact plan stops in
its first step.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import episode_build as eb  # noqa: E402
sys.path.insert(0, str(REPO / "migration" / "production" / "imagegen"))
import cf_allocation  # noqa: E402
import plan_check  # noqa: E402

ch = eb.ch
REPORTS = REPO / "migration" / "evidence" / "preflight"
SETUPS = REPO / "migration" / "evidence" / "pavo" / "setups.json"
CHARACTERS = ch.HERE / "characters.json"
CF_DAILY_IMAGES = 44          # Workers AI free allocation in FLUX images a day (OPERATIONS.md "Known limits")
SHEET_IMAGES = len(ch.REF_ORDER)   # a character's reference sheet: front, three-quarter, full


WORK_ROOT = REPO / ".episode"   # the only place preflight creates or removes a work directory
# the code a report vouches for: a change to any of them can change what the build refuses
CODE = [HERE / "episode_build.py", HERE / "plan_check.py", HERE / "voice_pace.py", HERE / "lipsync_check.py",
        HERE / "syncnet.py", HERE / "episode_preflight.py"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    """sha256 of a canonical JSON form (sorted keys, no spaces): the same data always gives the same digest."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                          .encode()).hexdigest()


def episode_id(plan_path, plan):
    """Review of #422: the episode id names the work directory and the report, so it is checked first, before any
    path is built: episode.yml's pattern (plan_check.EPISODE_ID) and the plan file's own name."""
    ep = plan.get("episode") if isinstance(plan, dict) else None
    if not isinstance(ep, str) or not plan_check.EPISODE_ID.fullmatch(ep) or Path(plan_path).stem != ep:
        raise SystemExit(f"EPISODE_ID_REFUSED {ep!r} (a-z 0-9 and single hyphens, the plan file named <episode>.json)")
    return ep


def report_path(plan, plan_path):
    return REPORTS / f"{episode_id(plan_path, plan)}.json"


def characters_used(plan):
    used = []
    for s in plan["shots"]:
        for cid in (["keeper"] if s["kind"] == "keeper" else list(s.get("characters") or [])):
            if cid not in used:
                used.append(cid)
        if plan_check.speaking(s) and s["speaker"] not in used + [ch.GOD]:
            used.append(s["speaker"])
    return used


def character_rows(plan, chars, images_dir=ch.HERE / "images"):
    rows, needs = [], []
    for cid in characters_used(plan):
        c = chars.get(cid) or {}
        records = sorted(p.stem for p in Path(images_dir).glob(f"ch-{cid}-*.json"))
        row = {"id": cid, "status": c.get("status"), "refs": c.get("refs") or [], "talk_refs": c.get("talk_refs") or [],
               "voice": c.get("voice"), "image_records": records}
        if c.get("status") != "APPROVED":
            if not records:
                row["next"] = (f"reference sheet: cf-images.yml pilot=characters only=<{cid} sheet ids> "
                               f"({SHEET_IMAGES} FLUX images), then Claude's review, then a PR setting APPROVED with kept refs")
                needs.append((cid, SHEET_IMAGES))
            else:
                row["next"] = "Claude reviews its reference sheet and sets APPROVED with kept refs, by PR"
        rows.append(row)
    return rows, needs


def cf_images_today(today=None, run=subprocess.run):
    """FLUX images recorded on main today (UTC): the image records cf-images.yml commits, counted by the one
    predicate the dispatch guard uses too (cf_allocation.flux_record, E116). Reported, not enforced here: a used-up
    allocation defers (E62), it never fails a build."""
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    done = run(["git", "-C", str(REPO), "log", f"--since={today}T00:00:00Z", "--grep",
                "images from Cloudflare Workers AI", "--diff-filter=A", "--name-only", "--format=%x00%s", "origin/main"],
               capture_output=True, text=True)
    if done.returncode:
        return None
    subject, n = "", 0
    for line in done.stdout.splitlines():
        if line.startswith("\0"):
            subject = line[1:]
        elif line:
            n += cf_allocation.flux_record(subject, line)
    return n


MIN_SHOT_CHANCE = 0.9         # a talking shot must pass its lips check within TALK_ATTEMPTS at least this often
MIN_PROBE_GENERATIONS = 6     # a line's rate is read from at least this many direct generations (TALK_ATTEMPTS)
# a voice-over Keeper prompt: 2 direct generations, the owner-approved plan B protocol (keeper-vo/calibration.json
# build_probes), all passing; the still-mouth result was decided by the reference and the gaze, which plan_check
# fixes (KEEPER_VO_POSE, the talking frame alone), not by a line. Read by the rule of succession below, 2 of 2 is 0.75
MIN_VO_PROBE_GENERATIONS = 2


def line_words(text):
    """A line's words, case and punctuation ignored: what a probe is matched on (#419: the rate is the line's)."""
    return " ".join(plan_check._plain(text))


def setup_key(shot, chars, line, images_dir=ch.HERE / "images"):
    """A talking shot's probe key: who speaks, the reference images its request sends for the speaker (record id
    and sha256), the prompt binding and the line itself. PR #419 measured that the lips pass rate belongs to the line
    (line-01 7 of 14, genesis-07's Keeper lines 1 of 39 with the same speaker, reference, pose and binding), so a
    probe on one line never vouches for another."""
    who = eb.speaker_of(shot)
    try:
        records = (eb.reference_records(who, chars, images_dir, "talk_refs")
                   or eb.reference_records(who, chars, images_dir))
    except SystemExit:
        records = []
    return {"speaker": who, "references": {rid: m.get("sha256") for rid, m in records}, "binding": eb.BOUND_AUDIO,
            "line": line_words(line)}


def vo_key(shot, chars, images_dir=ch.HERE / "images"):
    """A voice-over Keeper shot's probe key (plan B, #423): no line is spoken on screen, so what decides the
    still-mouth check is the one reference it sends (his talking frame) and the exact prompt (gaze, light, the mouth
    words: keeper-vo/calibration.json, the front view or a look down into the fire lost the face)."""
    try:
        records = eb.reference_records(ch.NARRATOR, chars, images_dir, "talk_refs")
    except SystemExit:
        records = []
    return {"kind": "still_mouth", "speaker": ch.NARRATOR,
            "references": {rid: m.get("sha256") for rid, m in records}, "prompt": shot.get("prompt")}


def load_probes():
    return json.loads(SETUPS.read_text())["probes"] if SETUPS.exists() else []


def probe_rows(plan, chars, probes=None):
    """Each talking shot with the recorded probes of its own line (speaker, references and binding equal), and each
    voice-over Keeper shot with the still-mouth probes of its own prompt and reference; none, or fewer than the
    minimum, is PROBE_REQUIRED, and a recorded rate whose chance within the shot's attempts is under MIN_SHOT_CHANCE
    is PROBE_RATE_LOW. Returns (rows, required, low, run chance or None while a shot is unprobed)."""
    probes = load_probes() if probes is None else probes
    items, carried = plan_check.sequence(plan)
    rows, missing, low, run_chance = [], [], [], 1.0
    for i, s in enumerate(plan["shots"]):
        talks, silent = plan_check.talking(s), plan_check.voiceover(s)
        if talks or silent:
            if talks:
                key = setup_key(s, chars, " ".join(items[k]["text"] for k in carried[i]))
                found = [x for x in probes if x.get("kind", "talk") == "talk" and all(
                    (line_words(x.get("line", "")) if k == "line" else x.get(k)) == v for k, v in key.items())]
                row, minimum = dict(key, shot=s["id"], kind="talk"), MIN_PROBE_GENERATIONS
            else:
                key = vo_key(s, chars)
                found = [x for x in probes if all(x.get(k) == v for k, v in key.items())]
                row = dict(key, shot=s["id"], check="lipsync_check --still-mouth")
                row.pop("prompt")
                minimum = MIN_VO_PROBE_GENERATIONS
            generations = sum(x.get("generations") or 0 for x in found)
            row["matched"] = found   # the probe entries this shot relies on (binding; dropped from the report rows)
            if generations < minimum:   # none, or too few to be a rate (1 of 3 is not evidence)
                row.update(probe="PROBE_REQUIRED", generations=generations, minimum=minimum)
                missing.append(s["id"])
            else:
                passed = sum(x.get("passed") or 0 for x in found)
                # the rule of succession: never a certainty from a few clips (2 of 2 reads 0.75, 7 of 14 0.5)
                rate = (passed + 1) / (generations + 2)
                shot_chance = 1 - (1 - rate) ** eb.attempts_for(s)
                run_chance *= shot_chance
                row.update(probe=sorted({x.get("evidence") for x in found}), passed=f"{passed} of {generations}",
                           shot_chance=round(shot_chance, 3))
                if shot_chance < MIN_SHOT_CHANCE:
                    low.append(s["id"])
            rows.append(row)
        elif plan_check.speaking(s):
            rows.append({"kind": "god_voice_over", "shot": s["id"],
                         "probe": "none needed: generated right after the talking shots (risk_order), face check"})
    return rows, missing, low, (round(run_chance, 3) if not missing else None)


def binding(plan_path, plan, chars_raw=None, probes=None):
    """Review of #422: what a report vouches for, part by part, so a STALE refusal names what changed and a change
    the plan does not use (another character approved) leaves it valid: the plan's bytes; the characters.json
    entries it uses (God's voice included when He speaks); their image records; the setups.json probes its talking
    and voice-over shots match; the preflight and build code."""
    data = json.loads(CHARACTERS.read_text()) if chars_raw is None else chars_raw
    used = characters_used(plan)
    entries = {cid: data["characters"].get(cid) for cid in used}
    if any(plan_check.speaking(s) and s["speaker"] == ch.GOD for s in plan["shots"]):
        entries[ch.GOD] = data.get("god")
    records = {p.name: sha256(p) for cid in used for p in sorted((ch.HERE / "images").glob(f"ch-{cid}-*.json"))}
    rows = probe_rows(plan, data["characters"], probes)[0]
    matched = sorted((digest(x) for r in rows for x in r.get("matched", [])))
    return {"plan": sha256(plan_path), "characters": digest(entries), "image_records": records,
            "setups": digest(matched), "code": {p.name: sha256(p) for p in CODE}}


def stale_parts(old, new):
    """The parts of a binding that changed: top-level names, and the file names inside image_records and code."""
    out = []
    for part in sorted(set(old or {}) | set(new)):
        a, b = (old or {}).get(part), new.get(part)
        if isinstance(b, dict) and isinstance(a, dict):
            out += [f"{part}:{k}" for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
        elif a != b:
            out.append(part)
    return out


def measured_pace(plan, work):
    """Words a second of each voice-track line as Kokoro spoke it (before the retime), by speaker; a line measured
    at no length is listed as None, never divided by."""
    items, _ = plan_check.sequence(plan)
    timeline = json.loads((Path(work) / "timeline.json").read_text())
    by = {}
    for k, x in enumerate(items):
        sentences = [s for s in timeline["sentences"] if s["segment"] == f"n{k:02d}"]
        if sentences:
            seconds = sentences[-1]["end"] - sentences[0]["start"]
            pace = round(plan_check.words(x["text"]) / seconds, 2) if seconds > 0 else None
            by.setdefault(x.get("speaker") or "narration", []).append(pace)
    return by


def voice_step(plan, voice_python, prepared, work):
    """Kokoro locally (the pinned model in a prepared work directory), then the build's lines step."""
    work = Path(work)
    if work.exists() or work.is_symlink():
        eb.safe_rmtree(work, WORK_ROOT)   # review of #422: never anything outside .episode/
    work.mkdir(parents=True)
    for name in ("source", "models"):
        src = Path(prepared) / name
        if not src.is_dir():
            return {"ran": False, "problems": [f"VOICE_NOT_PREPARED {src} (pilot_render.py prepare WORK ARCHIVE once)"]}
        (work / name).symlink_to(src.resolve())
    eb.save(work / "voice-script.json", eb.voice_script(plan))
    env = dict(os.environ)
    try:
        env["ESPEAK_DATA_PATH"] = subprocess.run([str(voice_python), "-I", "-c",
                                                  "import espeakng_loader as e;print(e.get_data_path())"],
                                                 capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    done = subprocess.run([str(voice_python), "-I", "-B", str(REPO / "migration" / "production" / "pilot_render.py"),
                           "voice", str(work), str(work / "voice-script.json")], capture_output=True, text=True, env=env)
    if done.returncode:
        return {"ran": False, "problems": [f"VOICE_FAILED {done.stderr.strip()[-300:]}"]}
    try:
        with contextlib.redirect_stdout(sys.stderr):   # the step logs; the report is the only stdout
            layout = eb.lines_step(plan, work)
        problems = []
    except SystemExit as exc:
        layout = json.loads((work / "layout.json").read_text()) if (work / "layout.json").exists() else None
        problems = [str(exc)]
    if layout and not problems:
        problems = [f"COMPOSE {p}" for p in eb.compose_prediction(plan, layout)]
    return {"ran": True, "problems": problems, "pace": measured_pace(plan, work),
            "measured": {k: layout[k] for k in ("total", "keeper_share", "lesson_share", "retimed")} if layout else None}


def refs_and_requests(plan, work):
    try:
        with contextlib.redirect_stdout(sys.stderr):
            refs = eb.refs_step(plan, work)
    except SystemExit as exc:
        return {"ran": False, "problems": [f"REFS {exc}"]}
    layout = json.loads((Path(work) / "layout.json").read_text())
    problems = eb.request_problems(plan, layout, refs)
    # E114: the sha256 of every shot's request, machine-independent (episode_build.request_identity); verify-preflight
    # compares the approved clips of shots/<episode>.json with these. E118: and the clip seconds this measured layout
    # needs per shot (no slack; the build allows MEASURE_TOLERANCE), which the approved clips must cover
    if problems:
        return {"ran": True, "problems": problems, "digests": {}, "needs": {}}
    return {"ran": True, "problems": problems, "digests": eb.request_digests(plan, layout, refs),
            "needs": eb.clip_needs(plan, layout)}


def preflight(plan_path, voice=None, refs=False, chars=None, setups=None, today_images=None):
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    ep = episode_id(plan_path, plan)   # before any path is built or any step runs (review of #422)
    chars = chars if chars is not None else ch.registry()
    result = plan_check.check(plan, chars)
    report = {"plan": str(plan_path.resolve().relative_to(REPO.resolve())) if REPO.resolve() in plan_path.resolve().parents
              else str(plan_path), "episode": ep,
              "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "plan_check": {"problems": plan_check.path_problems(plan_path, plan) + result["problems"],
                             "pending": result["pending"], "estimate": result["estimate"]}}
    rows, needs = character_rows(plan, chars)
    report["characters"] = rows
    used = cf_images_today() if today_images is None else today_images
    report["cf_images"] = {"recorded_today": used, "daily_allocation": CF_DAILY_IMAGES,
                           "sheets_needed": {cid: n for cid, n in needs},
                           "fits_today": None if used is None else used + sum(n for _, n in needs) <= CF_DAILY_IMAGES}
    blockers = [f"PLAN {p}" for p in report["plan_check"]["problems"] + report["plan_check"]["pending"]]
    # the voice and the setups are measured whenever the plan's structure holds (a character still DRAFT is no
    # reason to learn its pace or its missing probe later)
    sound = result["estimate"] != {}
    work = WORK_ROOT / f"preflight-{ep}"
    if voice and sound:
        try:
            report["voice"] = voice_step(plan, voice[0], voice[1], work)
        except SystemExit as exc:
            report["voice"] = {"ran": False, "problems": [str(exc)]}
        blockers += [f"VOICE {p}" for p in report["voice"]["problems"]]
        if not report["voice"]["ran"]:
            blockers.append("VOICE_NOT_MEASURED")
    else:
        report["voice"] = {"ran": False, "problems": [], "why": "plan structure broken" if voice else "no --voice given"}
        blockers.append("VOICE_NOT_MEASURED (run with --voice VOICE_PYTHON PREPARED_WORK)")
    if refs and report["voice"].get("ran") and not report["voice"]["problems"] and not blockers:
        report["requests"] = refs_and_requests(plan, work)
        blockers += [f"REQUEST {p}" for p in report["requests"]["problems"]]
    else:
        report["requests"] = {"ran": False, "problems": [],
                              "why": "needs --refs, a clean plan and a clean measured voice" if refs else "no --refs given"}
        blockers.append("REQUESTS_NOT_CHECKED (run with --refs once the plan and the voice are clean)")
    if sound:
        rows, missing, low, chance = probe_rows(plan, chars, setups)
        for r in rows:
            r.pop("matched", None)
        report["setups"] = {"shots": rows, "probes_required": missing, "rate_low": low,
                            "talk_attempts": eb.TALK_ATTEMPTS, "min_shot_chance": MIN_SHOT_CHANCE,
                            "run_chance_all_talking_shots": chance}
        blockers += [probe_required(r) for r in rows if r.get("shot") in missing]
        blockers += [f"PROBE_RATE_LOW {r['shot']} ({'still mouth' if r.get('kind') == 'still_mouth' else 'lips'} passed "
                     f"{r['passed']}: {r['shot_chance']} within {eb.TALK_ATTEMPTS} attempts < {MIN_SHOT_CHANCE})"
                     for r in rows if r.get("shot") in low]
    # E114: which shots still need a probed, reviewed and approved clip (shot-probe.yml, approve-shot). Not a blocker
    # of this report (an approval comes after it, by its own PR); verify-preflight refuses the build until none is left
    digests = report["requests"].get("digests")
    report["shot_review"] = (eb.review_problems(plan, digests, needs=report["requests"].get("needs") or {})
                             if digests else ["REQUESTS_NOT_CHECKED"])
    report["binding"] = binding(plan_path, plan, probes=setups)
    report["blockers"] = blockers
    report["status"] = "PASS" if not blockers else "BLOCKED"
    return report


def probe_required(row):
    """PROBE_REQUIRED, in the words of the shot's own kind: a talking line or a voice-over Keeper prompt."""
    if row.get("kind") == "still_mouth":
        return (f"PROBE_REQUIRED {row['shot']} ({row['generations']} of the >= {MIN_VO_PROBE_GENERATIONS} direct "
                "0-credit Pavo generations of this voice-over Keeper shot, matched on its exact prompt and its talking "
                "reference frame, judged by lipsync_check --still-mouth, recorded in evidence/pavo/setups.json)")
    return (f"PROBE_REQUIRED {row['shot']} ({row['generations']} of the >= {MIN_PROBE_GENERATIONS} direct 0-credit "
            "Pavo generations of this line with its speaker, reference and binding, judged by lipsync_check, "
            "recorded in evidence/pavo/setups.json)")


def verify(plan_path, approvals=None):
    """episode.yml's first step: the committed preflight report is PASS and bound to what this plan uses now (the
    plan, its characters and their image records, its probes, the preflight and build code)."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    path = report_path(plan, plan_path)
    if not path.exists():
        return (f"PREFLIGHT_MISSING {path.name} in {REPORTS.name}/ (episode_build.py preflight PLAN --voice ... "
                "--refs --write, by PR)")
    report = json.loads(path.read_text())
    changed = stale_parts(report.get("binding"), binding(plan_path, plan))
    if changed:
        return f"PREFLIGHT_STALE {', '.join(changed)} changed after the preflight; run it again"
    if report.get("status") != "PASS":
        return "PREFLIGHT_NOT_PASS " + "; ".join(report.get("blockers", []))[:600]
    # E114: every shot ships the clip Claude reviewed, made from the request this plan sends now
    # E118: and every approved clip covers the clip seconds the preflight's measured layout needs (a report without
    # them covers nothing: SHOT_CLIP_TOO_SHORT)
    requests = report.get("requests") or {}
    review = eb.review_problems(plan, requests.get("digests") or {}, approvals, requests.get("needs") or {})
    return "; ".join(review) if review else None


def record_problems(episode, video=None):
    """E106: what publish-episode.yml refuses in the record (EPISODE_REFUSED), by publish_episode.problems itself,
    before that workflow is dispatched; the file's sha256 only when the video is given."""
    try:
        return plan_check.publish_episode.problems(episode, video)
    except KeyError as exc:   # a record missing a field publish_episode reads: named, never a crash
        return [f"RECORD_FIELD_MISSING {exc.args[0]}"]


def parser():
    p = argparse.ArgumentParser(prog="episode_build.py", description="E106: the preflight of a Short's plan, its "
                                "verification by episode.yml, and the check of an episode record before publishing.")
    sub = p.add_subparsers(dest="cmd", required=True)
    pre = sub.add_parser("preflight", help="run every check the build can know before its first Pavo generation")
    pre.add_argument("plan")
    pre.add_argument("--voice", nargs=2, metavar=("VOICE_PYTHON", "PREPARED_WORK"),
                     help="the Kokoro venv's python and a work directory prepared by pilot_render.py prepare")
    pre.add_argument("--refs", action="store_true", help="fetch the reference images and validate every request")
    pre.add_argument("--write", action="store_true", help="save the report to evidence/preflight/<episode>.json")
    ver = sub.add_parser("verify-preflight", help="exit 0 only when the committed report is PASS for this plan")
    ver.add_argument("plan")
    rec = sub.add_parser("check-record", help="publish_episode's rules on an episode record")
    rec.add_argument("record")
    rec.add_argument("video", nargs="?")
    return p


def main(argv):
    args = parser().parse_args(argv[1:])
    if args.cmd == "check-record":
        bad = record_problems(json.loads(Path(args.record).read_text()), args.video)
        print(json.dumps({"record": args.record, "problems": bad}))
        return 1 if bad else 0
    if args.cmd == "verify-preflight":
        bad = verify(args.plan)
        print(bad or "PREFLIGHT_PASS")
        return 1 if bad else 0
    report = preflight(args.plan, voice=tuple(args.voice) if args.voice else None, refs=args.refs)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if args.write:
        eb.save(report_path(json.loads(Path(args.plan).read_text()), args.plan), report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
