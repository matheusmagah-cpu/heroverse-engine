#!/usr/bin/env python3
"""Preflight of a Short's plan before episode.yml is dispatched (owner, 2026-10-26: "an error must never repeat";
E106). It runs locally, with no Actions minute and no credit, everything the build can know before its first Pavo
generation, with the build's own functions, and says which new setups need a direct 0-credit Pavo probe first.

  episode_build.py preflight PLAN [--voice VOICE_PYTHON PREPARED_WORK] [--refs] [--write]
  episode_build.py verify-preflight PLAN       exit 0 only when the committed report is PASS for this exact plan

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
  6. talking setups: each talking shot's setup (speaker, the reference images it sends, the prompt binding) must have
     a direct 0-credit Pavo probe recorded in evidence/pavo/setups.json (generations and lips-check passes); one
     missing is PROBE_REQUIRED. From the recorded pass rate: each shot's and the run's chance at TALK_ATTEMPTS.
The report is PASS only when every step ran and found nothing. --write saves it to
evidence/preflight/<episode>.json (bound to the plan's and characters.json's sha256); episode.yml runs
verify-preflight on main before any secret is used, so a build without a PASS preflight of that exact plan stops in
its first step.
"""
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import episode_build as eb  # noqa: E402
import plan_check  # noqa: E402

ch = eb.ch
REPORTS = REPO / "migration" / "evidence" / "preflight"
SETUPS = REPO / "migration" / "evidence" / "pavo" / "setups.json"
CHARACTERS = ch.HERE / "characters.json"
CF_DAILY_IMAGES = 44          # Workers AI free allocation in FLUX images a day (OPERATIONS.md "Known limits")
SHEET_IMAGES = len(ch.REF_ORDER)   # a character's reference sheet: front, three-quarter, full


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def report_path(plan):
    return REPORTS / f"{plan['episode']}.json"


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
    """FLUX images recorded on main today (UTC): the image records cf-images.yml commits ("Record ... images from
    Cloudflare Workers AI"). Reported, not enforced: a used-up allocation defers (E62), it never fails a build."""
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    done = run(["git", "-C", str(REPO), "log", f"--since={today}T00:00:00Z", "--grep",
                "images from Cloudflare Workers AI", "--diff-filter=A", "--name-only", "--format=", "origin/main"],
               capture_output=True, text=True)
    if done.returncode:
        return None
    return sum(1 for line in done.stdout.splitlines() if line.endswith(".json") and "/images/" in line)


def setup_key(shot, chars, images_dir=ch.HERE / "images"):
    """A talking shot's setup: who speaks, the reference images its request sends for the speaker (record id and
    sha256) and the prompt binding. A new speaker, a new speaking frame or a new binding is a new setup (SYSTEM.md
    "No rework": probed with direct 0-credit Pavo calls before a build)."""
    who = eb.speaker_of(shot)
    try:
        records = (eb.reference_records(who, chars, images_dir, "talk_refs")
                   or eb.reference_records(who, chars, images_dir))
    except SystemExit:
        records = []
    return {"kind": "talk", "speaker": who, "references": {rid: m.get("sha256") for rid, m in records},
            "binding": eb.BOUND_AUDIO}


def probe_rows(plan, chars, setups=None):
    """Each talking shot with its recorded probe, or PROBE_REQUIRED; the expected pass rates at TALK_ATTEMPTS."""
    if setups is None:
        setups = json.loads(SETUPS.read_text())["setups"] if SETUPS.exists() else []
    rows, missing, run_chance = [], [], 1.0
    for s in plan["shots"]:
        if plan_check.talking(s):
            key = setup_key(s, chars)
            found = next((x for x in setups if all(x.get(k) == v for k, v in key.items())), None)
            row = dict(key, shot=s["id"])
            if not found or not found.get("generations"):
                row["probe"] = "PROBE_REQUIRED"
                missing.append(s["id"])
            else:
                rate = found["passed"] / found["generations"]
                shot_chance = 1 - (1 - rate) ** eb.TALK_ATTEMPTS
                run_chance *= shot_chance
                row.update(probe=found.get("evidence"), pass_rate=round(rate, 3),
                           shot_chance=round(shot_chance, 3))
            rows.append(row)
        elif plan_check.speaking(s):
            rows.append({"kind": "god_voice_over", "shot": s["id"],
                         "probe": "none needed: generated right after the talking shots (risk_order), face check"})
    return rows, missing, round(run_chance, 3)


def measured_pace(plan, work):
    """Words a second of each voice-track line as Kokoro spoke it (before the retime), by speaker."""
    items, _ = plan_check.sequence(plan)
    timeline = json.loads((Path(work) / "timeline.json").read_text())
    by = {}
    for k, x in enumerate(items):
        sentences = [s for s in timeline["sentences"] if s["segment"] == f"n{k:02d}"]
        if sentences:
            seconds = sentences[-1]["end"] - sentences[0]["start"]
            by.setdefault(x.get("speaker") or "narration", []).append(round(plan_check.words(x["text"]) / seconds, 2))
    return by


def voice_step(plan, voice_python, prepared, work):
    """Kokoro locally (the pinned model in a prepared work directory), then the build's lines step."""
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
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
    return {"ran": True, "problems": eb.request_problems(plan, layout, refs)}


def preflight(plan_path, voice=None, refs=False, chars=None, setups=None, today_images=None):
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    chars = chars if chars is not None else ch.registry()
    result = plan_check.check(plan, chars)
    report = {"plan": str(plan_path.resolve().relative_to(REPO.resolve())) if REPO.resolve() in plan_path.resolve().parents
              else str(plan_path), "episode": plan.get("episode"), "plan_sha256": sha256(plan_path),
              "characters_sha256": sha256(CHARACTERS),
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
    work = REPO / ".episode" / f"preflight-{plan.get('episode')}"
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
        probes, missing, chance = probe_rows(plan, chars, setups)
        report["setups"] = {"shots": probes, "probes_required": missing, "talk_attempts": eb.TALK_ATTEMPTS,
                            "run_chance_all_talking_shots": chance}
        blockers += [f"PROBE_REQUIRED {sid} (a direct 0-credit Pavo test of this setup with lipsync_check, recorded in "
                     "evidence/pavo/setups.json)" for sid in missing]
    report["blockers"] = blockers
    report["status"] = "PASS" if not blockers else "BLOCKED"
    return report


def verify(plan_path):
    """episode.yml's first step: the committed preflight report is PASS for this exact plan and character bible."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    path = report_path(plan)
    if not path.exists():
        return f"PREFLIGHT_MISSING {path.name} in {REPORTS.name}/ (episode_build.py preflight PLAN --voice ... --refs --write, by PR)"
    report = json.loads(path.read_text())
    if report.get("plan_sha256") != sha256(plan_path) or report.get("characters_sha256") != sha256(CHARACTERS):
        return "PREFLIGHT_STALE (the plan or characters.json changed after the preflight; run it again)"
    if report.get("status") != "PASS":
        return "PREFLIGHT_NOT_PASS " + "; ".join(report.get("blockers", []))[:600]
    return None


def record_problems(episode, video=None):
    """E106: what publish-episode.yml's publish_episode.problems would refuse (EPISODE_REFUSED: TITLE_LENGTH,
    DESCRIPTION_LENGTH, DISCLOSURE_MISSING, the Short's words, OUTPUT_SHA256_MISMATCH with the video), with its own
    functions, before that workflow is dispatched."""
    pe = plan_check.publish_episode
    out = pe.short_problems(episode)
    if not 0 < len(episode.get("title") or "") <= pe.TITLE_MAX:
        out.append("TITLE_LENGTH")
    out += pe.description_problems(episode.get("description") or "")
    if video is not None and pe.sha256_file(video) != episode.get("output_sha256"):
        out.append("OUTPUT_SHA256_MISMATCH")
    return out


def main(argv):
    if len(argv) >= 3 and argv[1] == "check-record":
        bad = record_problems(json.loads(Path(argv[2]).read_text()), argv[3] if len(argv) > 3 else None)
        print(json.dumps({"record": argv[2], "problems": bad}))
        return 1 if bad else 0
    if len(argv) >= 3 and argv[1] == "verify-preflight":
        bad = verify(argv[2])
        print(bad or "PREFLIGHT_PASS")
        return 1 if bad else 0
    args = argv[2:]
    voice, refs, write = None, "--refs" in args, "--write" in args
    if "--voice" in args:
        i = args.index("--voice")
        voice = (args[i + 1], args[i + 2])
    report = preflight(args[0], voice=voice, refs=refs)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if write:
        eb.save(report_path(json.loads(Path(args[0]).read_text())), report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
