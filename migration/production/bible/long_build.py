#!/usr/bin/env python3
"""The Bible-story long's build (LONG_DESIGN.md slice 3 and section 7; owner 27/10: arc-01's long publishable with no
rework). It is the Short's build (episode_build.py: voice-script, lines, refs, generate with approved clips only) run
on the long's plan, plus only what differs, here:

- the voice: the lines at LONG_LINE_GAP and the cold open's last frame held (silence under the music) until the
  Keeper at the structure's cold_open_s, at most COLD_OPEN_HOLD_MAX, measured on the real voice (cold_open_layout,
  called by episode_build.voice_layout, so preflight, lines and the compose share it: COLD_OPEN_LENGTH, COLD_OPEN_SHORT);
- the cut: one cut a shot, every cut a story QA v3 hold (grammar.scene_seconds 4-7 s; HOLD_UNDER_QA, HOLD_OVER_QA),
  the shots of one voice run sharing it equally (long_plan_check's own model); a talking shot from its first word at
  normal speed to the next run (its last frame held for the gap); a `window_of` shot shows the next unseen part of
  its source's clip (the source and its windows slowed together, at most MAX_SLOW: FOOTAGE_SHORT). Nothing is
  generated for a window: it reuses its source's approved, upscaled clip;
- the picture: every approved 1280x720 Pavo clip through Real-ESRGAN general x4v3 to 2560x1440 30 fps (story QA v3
  rights.ai_video.upscaler; pavo_footage.render, the library's own path), one clip a matrix job; the composed file at
  the frozen QA's frame, H.264 30 fps, no burned captions;
- the sound: the voice and the owned music (ducked) mixed, then two-pass loudnorm to -15 LUFS / -1.5 dBTP (inside
  story QA v3's -16..-14 LUFS and <= -1 dBTP; LONG_DESIGN section 3), measured again on the file (LOUDNESS);
- the captions: the .srt track from the compose timeline by captions.py's own writer (captions.track_record, story QA
  v3's cue limits), never burned in;
- the manifest qa_pilot reads for story QA v3 (holds[].beat/characters/shot_kind, sentences[].speaker, clips[] with
  their checks, burned_captions false, caption_track), beside the file, its .srt and a report.

The build never holds a Pavo secret and generates nothing (E114, E126): verify-preflight runs first, the clips come from
shots/<long>.json by their content hash.

usage (long-build.yml runs them in order; each refuses a plan long_plan_check --strict refuses and, but for
upscale-ids, a plan without a PASS preflight bound to it now):
  long_build.py timeline PLAN WORK              after episode_build generate: the long's cuts on the approved 720p
                                                clips (WORK/long-timeline.json), refused before any upscale
  long_build.py resume-names RUN REPO EP OUT    resume_run's upscale artifact names of this long (an earlier
                                                long-build of main only: RESUME_RUN_NOT_A_LONG_BUILD), to OUT
  long_build.py resume-download RUN REPO EP DEST  those upscales into DEST without replacing this run's
  long_build.py upscale-ids PLAN [NAMES_FILE]   the generated shots still to upscale, as JSON: all of them, less those
                                                whose artifact (artifact_name) is listed in NAMES_FILE (resume_run)
  long_build.py upscale PLAN SHOT OUT WEIGHTS   one approved clip (sha256 checked) to OUT/<shot>.mp4 + .json at
                                                2560x1440 30 fps (Real-ESRGAN x4v3, weights sha256 checked)
  long_build.py assemble PLAN WORK UP MUSIC OUT the composed long OUT/<long>.mp4, OUT/captions.srt,
                                                OUT/manifest.json, OUT/report.json; refused on any check
  long_build.py sheet VIDEO SHEET.jpg           20 frames of the composed long on one 16:9 sheet (5 x 4)
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "migration" / "publish"))
sys.path.insert(0, str(REPO / "migration" / "production" / "footage"))
import episode_build as eb  # noqa: E402
import long_plan_check as lpc  # noqa: E402
import plan_check as pc  # noqa: E402

QA = lpc.qa()
FRAME = tuple(QA["technical"]["frame"])          # 2560x1440: the frozen story QA v3's frame
FPS = 30
LUFS_TARGET, TP_TARGET = -15.0, -1.5             # LONG_DESIGN section 3: inside -16..-14 LUFS, <= -1 dBTP
LUFS_BAND = tuple(QA["technical"]["integrated_lufs"])
TP_MAX = QA["technical"]["true_peak_dbtp_max"]
HOLDS = tuple(QA["grammar"]["scene_seconds"])    # every cut 4-7 s
MAX_SLOW = pc.MAX_SLOW
FADE_OUT = eb.FADE_OUT
MUSIC_DB = -22.0                                 # short_engine.MUSIC_DB (test_long_build holds them equal)
AI = QA["rights"]["ai_video"]
UP_RECORD = "long-upscale-v1"
MIN_SECONDS = QA["technical"]["duration_seconds_min"]   # 601 s: the frozen QA's floor, checked at build time
# review of #470: the upscale resamples 24 fps to 30 fps, so a clip can come back up to one frame shorter; the timeline
# step on the 720p clips leaves that frame of margin, so a cut that passes there cannot fail after the upscale
FRAME_MARGIN = 1 / FPS
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RUN_ID = re.compile(r"^[0-9]{6,20}$")
# sweep H2: the only runs whose upscales a resume may borrow (never a pull request run's artifacts)
LONG_BUILD_RUN = ".github/workflows/long-build.yml workflow_dispatch main"
ARTIFACT = re.compile(r"^long-up-([a-z0-9]+(?:-[a-z0-9]+)*)--([a-z0-9]+(?:-[a-z0-9]+)*)-([0-9a-f]{16})$")


def artifact_name(episode, shot_id, clip_sha256):
    """The upscale job's artifact: the shot and the first 16 hex of the approved clip it was made from (resume)."""
    return f"long-up-{episode}--{shot_id}-{clip_sha256[:16]}"


# ---------- the voice: the cold open's hold ----------

def cold_open_layout(plan, layout):
    """(layout, (first line after the cold open, hold seconds) or None, problems): the lines from the first one after
    the cold open start at the structure's cold_open_s exactly, the cold open's last frame held until then
    (long_plan_check's own rule, here on the measured voice)."""
    shots = plan["shots"]
    after = next((i for i, s in enumerate(shots) if s.get("beat") != "cold_open"), None)
    if after is None or shots[0].get("beat") != "cold_open":
        return layout, None, []
    _, carried = pc.sequence(plan)
    k0 = carried[after][0]
    cold = lpc.gate()["cold_open_s"]
    voice = layout[k0][0]
    problems = []
    if voice > cold + 1e-6:
        problems.append(f"COLD_OPEN_LENGTH {voice:.2f} s > {cold} s (measured: the cold open's words and gap end "
                        "after the structure's cold open)")
    hold = max(0.0, cold - voice)
    if hold > lpc.COLD_OPEN_HOLD_MAX + 1e-6:
        problems.append(f"COLD_OPEN_SHORT {voice:.2f} s (measured: its last frame would hold {hold:.2f} s before the "
                        f"Keeper at {cold} s; at most {lpc.COLD_OPEN_HOLD_MAX:g} s)")
    if hold <= 1e-6:
        return layout, None, problems
    shifted = list(layout[:k0]) + [(round(a + hold, 3), round(b + hold, 3)) for a, b in layout[k0:]]
    return shifted, (k0, hold), problems


# ---------- the cut ----------

def compose_long_shots(plan, layout, clips, clip_seconds):
    """short_engine shots tiling [0, total]: one cut a shot. clips and clip_seconds are keyed by generated shot id (a
    window's cut plays its source's clip). Each cut carries `shot`, `source` and `kind` (scene, window, keeper,
    speaker)."""
    shots, total, lines = plan["shots"], layout["total"], layout["lines"]
    _, carried = pc.sequence(plan)
    runs = pc.groups(shots, carried)
    out, cursor = [], 0.0
    for r, (a, b, ln) in enumerate(runs):
        last = r == len(runs) - 1
        end = total if last else lines[runs[r + 1][2][0]]["start"]
        s = shots[a]
        # E130: a voice-over Keeper (plan B) is cut like a scene run: his silent clip covers his line from its first
        # word to the next run (slowed with its parts at most MAX_SLOW), his words play from the voice track
        if pc.talking(s):
            kind = "keeper" if s["kind"] == "keeper" else "speaker"
            start, stop = lines[ln[0]]["start"], lines[ln[-1]]["end"]
            if abs(start - cursor) > 1e-3:
                raise SystemExit(f"{kind.upper()}_NOT_ON_HIS_LINE {s['id']}")
            have = clip_seconds[s["id"]]
            hold = max(0.0, (end - start) - have)
            held = round(hold + eb.HOLD_MARGIN, 3) if hold > 1e-3 else 0.0
            if held > pc.TALK_HOLD_MAX or have + 1e-3 < stop - start:
                raise SystemExit(f"{kind.upper()}_CLIP_SHORT {s['id']} ({have:.2f} s for {end - start:.2f} s, a hold "
                                 f"of at most {pc.TALK_HOLD_MAX} s)")
            cut = {"clip": clips[s["id"]], "start": round(start, 3), "end": round(end, 3), "src_start": 0.0,
                   "speed": 1.0, "shot": s["id"], "source": s["id"], "kind": kind,
                   "talk": {"start": round(start, 3), "end": round(stop, 3)}}
            if held:
                cut["hold"] = held
            out.append(cut)
            cursor = end
            continue
        members = shots[a:b + 1]
        share = (end - cursor) / len(members)
        t = cursor
        for m in members:
            src = m.get("window_of") or m["id"]
            out.append({"clip": clips[src], "start": round(t, 3), "end": round(t + share, 3), "shot": m["id"],
                        "source": src, "kind": "window" if eb.is_window(m) else
                        ("keeper_vo" if pc.voiceover(m) else "scene")})
            t += share
        out[-1]["end"] = round(end, 3)
        cursor = end
    parts = {}
    for c in out:
        if c["kind"] in ("scene", "window", "keeper_vo"):
            parts.setdefault(c["source"], []).append(c)
    for src, cs in parts.items():   # the source and its windows: distinct parts of one clip, in order
        shown = sum(c["end"] - c["start"] for c in cs)
        factor = max(1.0, shown / clip_seconds[src])
        if factor > MAX_SLOW + 1e-9:
            raise SystemExit(f"FOOTAGE_SHORT {src} ({clip_seconds[src]:.2f} s of clip for {shown:.2f} s on screen, "
                             f"slowed at most {MAX_SLOW})")
        used = 0.0
        for c in cs:
            c["src_start"] = round(used / factor, 3)
            c["speed"] = round(factor, 4)
            used += c["end"] - c["start"]
    return out


def hold_problems(cuts, holds=HOLDS):
    """story QA v3 grammar.scene_seconds, as qa_pilot measures it: every cut but the last inside the band, the last
    at least its floor."""
    lo, hi = holds
    out = []
    for i, c in enumerate(cuts):
        d = c["end"] - c["start"]
        if d < lo - 1e-6:
            out.append(f"HOLD_UNDER_QA cut {i} {c['shot']} ({d:.2f} s; story QA holds {lo:g}-{hi:g} s)")
        elif i < len(cuts) - 1 and d > hi + 1e-6:
            out.append(f"HOLD_OVER_QA cut {i} {c['shot']} ({d:.2f} s; story QA holds {lo:g}-{hi:g} s)")
    return out


def establishing_share(plan, cuts, total):
    by_id = {s["id"]: s for s in plan["shots"]}
    t = sum(c["end"] - c["start"] for c in cuts if by_id[c["source"]].get("establishing"))
    return round(t / total, 3) if total else 0.0


def compose_problems(plan, layout, clip_seconds):
    """Every refusal the long's compose raises for these clip lengths ({generated shot id: seconds}), before any
    clip is upscaled: the preflight (episode_build.compose_prediction), the timeline step and the assembly."""
    import short_engine
    try:
        cuts = compose_long_shots(plan, layout, {k: k for k in clip_seconds}, clip_seconds)
    except (SystemExit, KeyError) as exc:
        return [str(exc) if isinstance(exc, SystemExit) else f"CLIP_MISSING {exc}"]
    sentences = [{"start": x["start"], "end": x["end"]} for x in layout["lines"]]
    problems = (short_engine.check_shots(cuts, layout["total"]) + short_engine.talk_problems(cuts, sentences)
                + hold_problems(cuts))
    for i, c in enumerate(cuts):
        if short_engine.explicit_speed(c, clip_seconds[c["source"]]) is None:
            problems.append(f"CLIP_TOO_SHORT cut {i} {c['shot']}")
    share = establishing_share(plan, cuts, layout["total"])
    if share > pc.ESTABLISHING_SHARE_MAX:
        problems.append(f"ESTABLISHING_SHARE {share:.3f} (composed)")
    return problems


def generated(plan):
    return [s for s in plan["shots"] if not eb.is_window(s)]


def durations(folder, plan):
    import short_engine
    out = {}
    for s in generated(plan):
        f = Path(folder) / f"{s['id']}.mp4"
        if not f.is_file():
            raise SystemExit(f"CLIP_MISSING {s['id']} in {folder}")
        out[s["id"]] = short_engine.duration(f)
    return out


def timeline_step(plan, work):
    """After episode_build generate: the long's cuts on the approved 720p clips, refused before hours of upscaling."""
    work = Path(work)
    layout = eb.load(work / "layout.json")
    seconds = {k: v - FRAME_MARGIN for k, v in durations(work / "clips", plan).items()}   # the upscale's frame
    problems = compose_problems(plan, layout, seconds)
    cuts = [] if problems else compose_long_shots(plan, layout, {k: k for k in seconds}, seconds)
    eb.save(work / "long-timeline.json", {"clip_seconds": seconds, "frame_margin": FRAME_MARGIN, "cuts": cuts,
                                          "problems": problems})
    print(json.dumps({"cuts": len(cuts), "problems": problems[:5]}))
    if problems:
        raise SystemExit("LONG_TIMELINE_REFUSED " + "; ".join(problems))
    return cuts


# ---------- the picture: Real-ESRGAN on every approved clip (matrix) ----------

def upscale_ids(plan, done_names=(), approvals=None):
    """The generated shots to upscale: every one whose artifact of the approved clip it ships now is not in
    done_names (a resume_run's artifacts)."""
    approvals = eb.load_approvals(plan) if approvals is None else approvals
    done = set(done_names)
    todo = []
    for s in generated(plan):
        a = approvals.get(s["id"])
        if not a:
            raise SystemExit(f"SHOT_NOT_REVIEWED {s['id']}")
        if artifact_name(plan["episode"], s["id"], a["clip_sha256"]) not in done:
            todo.append(s["id"])
    return todo


def upscale_step(plan, shot_id, out, weights, frame_fn=None, fetch=eb.fetch_release_asset, approvals=None):
    """One approved clip (by its content hash, sha256 checked) to OUT/<shot>.mp4 at 2560x1440 30 fps and its record
    OUT/<shot>.json binding it to the approved clip."""
    import pavo_footage
    if not isinstance(shot_id, str) or not SLUG.fullmatch(shot_id):
        raise SystemExit(f"SHOT_ID_REFUSED {shot_id!r}")
    approvals = eb.load_approvals(plan) if approvals is None else approvals
    if shot_id not in {s["id"] for s in generated(plan)}:
        raise SystemExit(f"UPSCALE_SHOT_REFUSED {shot_id} (a generated shot of {plan['episode']})")
    a = approvals.get(shot_id)
    if not a:
        raise SystemExit(f"SHOT_NOT_REVIEWED {shot_id}")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    src = out / f"{shot_id}.src.mp4"
    eb.fetch_shot_clip(a, src, fetch)
    if frame_fn is None:
        frame_fn = pavo_footage.real_esrgan(weights)
        upscaler = AI["upscaler"]
    else:
        upscaler = "stub (tests only)"
    dst = out / f"{shot_id}.mp4"
    try:
        w, h, fps, seconds = pavo_footage.render(src, dst, frame_fn)
    finally:
        src.unlink(missing_ok=True)
    rec = {"version": UP_RECORD, "episode": plan["episode"], "shot": shot_id, "source_asset": a["asset"],
           "source_sha256": a["clip_sha256"], "source": {"width": w, "height": h, "fps": round(fps, 3),
                                                          "seconds": round(seconds, 3)},
           "frame": frame_of(dst), "fps": FPS, "upscaler": upscaler, "sha256": eb.sha256(dst),
           "artifact": artifact_name(plan["episode"], shot_id, a["clip_sha256"])}
    eb.save(out / f"{shot_id}.json", rec)
    print(json.dumps({"shot": shot_id, "sha256": rec["sha256"], "artifact": rec["artifact"]}))
    return rec


def upscaled(plan, up, approvals, frame=FRAME):
    """{shot id: (clip path, record)} of every generated shot, each bound to the clip approved now: UPSCALE_MISSING,
    UPSCALE_SOURCE_MISMATCH (made from another clip than the approved one), UPSCALE_SHA256_MISMATCH,
    UPSCALE_FRAME (not the QA's frame)."""
    out, problems = {}, []
    for s in generated(plan):
        sid = s["id"]
        f, r = Path(up) / f"{sid}.mp4", Path(up) / f"{sid}.json"
        if not f.is_file() or not r.is_file():
            problems.append(f"UPSCALE_MISSING {sid}")
            continue
        rec = eb.load(r)
        if rec.get("source_sha256") != (approvals.get(sid) or {}).get("clip_sha256"):
            problems.append(f"UPSCALE_SOURCE_MISMATCH {sid}")
        elif eb.sha256(f) != rec.get("sha256"):
            problems.append(f"UPSCALE_SHA256_MISMATCH {sid}")
        elif tuple(rec.get("frame") or ()) != tuple(frame) or tuple(frame_of(f)) != tuple(frame):
            problems.append(f"UPSCALE_FRAME {sid} {frame_of(f)} (the QA's {list(frame)})")
        else:
            out[sid] = (f, rec)
    if problems:
        raise SystemExit("; ".join(problems))
    return out


def frame_of(path):
    """[width, height] of a file's video stream, measured (ffprobe)."""
    v = probe(path)["video"]
    return [v[0].get("width"), v[0].get("height")] if v else None


# ---------- resume (sweep H2, review of #470) ----------

def gh(args, gh_bin="gh"):
    return subprocess.run([gh_bin, *args], capture_output=True, text=True)


def resume_names(run_id, repo, episode, gh_bin="gh"):
    """The upscale artifacts of this long that an earlier long-build of main kept: RESUME_RUN_REFUSED (not a run id),
    RESUME_RUN_NOT_A_LONG_BUILD (any other run: a pull request run can upload artifacts of any name)."""
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise SystemExit(f"RESUME_RUN_REFUSED {run_id!r}")
    if not SLUG.fullmatch(episode or "") or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo or ""):
        raise SystemExit(f"RESUME_RUN_REFUSED {repo!r} {episode!r}")
    done = gh(["api", f"repos/{repo}/actions/runs/{run_id}", "--jq", '[.path, .event, .head_branch] | join(" ")'],
              gh_bin)
    source = done.stdout.strip()
    if done.returncode or source != LONG_BUILD_RUN:
        raise SystemExit(f"RESUME_RUN_NOT_A_LONG_BUILD {run_id}: {source or done.stderr.strip()[-200:]}")
    done = gh(["api", "--paginate", f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100", "--jq",
               ".artifacts[] | select(.expired == false) | .name"], gh_bin)
    if done.returncode:
        raise SystemExit(f"RESUME_DOWNLOAD_FAILED {run_id}: {done.stderr.strip()[-300:]}")
    return [n for n in done.stdout.split() if (ARTIFACT.fullmatch(n) or [None, None])[1] == episode]


def resume_download(run_id, repo, episode, dest, gh_bin="gh"):
    """resume_run's upscales into DEST without replacing this run's: nothing is downloaded when the run kept none of
    this long's, and "no artifact matches" (expired since) is no failure; assemble refuses any shot still missing."""
    names = resume_names(run_id, repo, episode, gh_bin)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if not names:
        print(json.dumps({"resumed_from": run_id, "kept": []}))
        return []
    prev = dest.parent / f"resume-{run_id}"
    done = gh(["run", "download", run_id, "--repo", repo, "-p", f"long-up-{episode}--*", "-D", str(prev)], gh_bin)
    if done.returncode:
        if "no artifact matches" in (done.stderr + done.stdout).lower():
            print(json.dumps({"resumed_from": run_id, "kept": [], "note": "no artifact matches"}))
            return []
        raise SystemExit(f"RESUME_DOWNLOAD_FAILED {run_id}: {done.stderr.strip()[-300:]}")
    kept = []
    for f in sorted(prev.rglob("*")):
        if f.is_file() and f.suffix in (".mp4", ".json") and not f.is_symlink() and SLUG.fullmatch(f.stem):
            target = dest / f.name
            if not target.exists():   # this run's upscale wins
                target.write_bytes(f.read_bytes())
                kept.append(f.name)
    print(json.dumps({"resumed_from": run_id, "kept": kept}))
    return kept


# ---------- the render (16:9, no burned captions, -15 LUFS) ----------

def run(args):
    done = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"FFMPEG_FAILED {done.returncode}: {done.stderr.strip()[-600:]}")
    return done


def loudness(path):
    """(integrated LUFS, true peak dBTP) of a file's audio (ffmpeg ebur128, true peak)."""
    done = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", str(path), "-af", "ebur128=peak=true", "-f",
                           "null", "-"], capture_output=True, text=True)
    i = re.findall(r"I:\s+(-?[0-9.]+) LUFS", done.stderr)
    tp = re.findall(r"Peak:\s+(-?[0-9.]+|-inf) dBFS", done.stderr)
    return (float(i[-1]) if i else None), (float(tp[-1]) if tp and tp[-1] != "-inf" else None)


def render(cplan, out, frame=FRAME):
    """The compose plan (short_engine's shape, cuts tiling [0, voice + tail]) at FRAME, 30 fps, H.264, no captions:
    each cut encoded once (the fade-out on the last), concatenated without re-encoding, the voice and the ducked owned
    music mixed and brought to -15 LUFS / -1.5 dBTP by two-pass loudnorm."""
    import short_engine
    w, h = frame
    timeline = json.loads(Path(cplan["timeline"]).read_text())
    total = round(timeline["voice_seconds"] + cplan.get("tail", eb.TAIL), 3)
    cuts = cplan["shots"]
    problems = short_engine.check_shots(cuts, total) + short_engine.talk_problems(cuts, timeline["sentences"])
    if problems:
        raise SystemExit("PLAN_REFUSED " + "; ".join(problems))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts = []
        for i, c in enumerate(cuts):
            have = short_engine.duration(c["clip"])
            factor = short_engine.explicit_speed(c, have)
            if factor is None:
                raise SystemExit(f"CLIP_TOO_SHORT cut {i} {c['shot']}")
            need = c["end"] - c["start"]
            fade = f",fade=t=out:st={max(0.0, need - FADE_OUT):.3f}:d={FADE_OUT}" if i == len(cuts) - 1 else ""
            part = tmp / f"p{i:03d}.mp4"
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{c.get('src_start', 0.0):.3f}", "-i", c["clip"],
                 "-an", "-vf", f"setpts={factor:.4f}*PTS,{short_engine.hold_filter(c)}scale={w}:{h}:flags=lanczos:"
                               f"force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},format=yuv420p{fade}",
                 "-t", f"{need:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(FPS), part])
            parts.append(part)
        (tmp / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", tmp / "list.txt",
             "-c", "copy", tmp / "picture.mp4"])
        mix = (f"[0:a]aresample=48000,apad=whole_dur={total},asplit=2[v][vk];"
               f"[1:a]aresample=48000,atrim=start={cplan.get('music_offset', 0.0)}:duration={total},"
               f"asetpts=PTS-STARTPTS,volume={MUSIC_DB}dB[m];"
               "[m][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[md];"
               f"[v][md]amix=inputs=2:normalize=0,afade=t=out:st={total - FADE_OUT}:d={FADE_OUT},"
               "aformat=sample_rates=48000:channel_layouts=stereo[a]")
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", cplan["voice"], "-i", cplan["music"], "-filter_complex",
             mix, "-map", "[a]", "-t", str(total), "-c:a", "pcm_s16le", tmp / "mix.wav"])
        first = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", str(tmp / "mix.wav"), "-af",
                                f"loudnorm=I={LUFS_TARGET}:TP={TP_TARGET}:LRA=11:print_format=json", "-f", "null", "-"],
                               capture_output=True, text=True)
        try:
            m = json.loads(first.stderr[first.stderr.rindex("{"):first.stderr.rindex("}") + 1])
        except ValueError:
            raise SystemExit("LOUDNORM_MEASURE_FAILED " + first.stderr.strip()[-300:])
        norm = (f"loudnorm=I={LUFS_TARGET}:TP={TP_TARGET}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
                "linear=true,aresample=48000")
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp / "picture.mp4", "-i", tmp / "mix.wav", "-map", "0:v",
             "-map", "1:a", "-af", norm, "-t", str(total), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar",
             "48000", "-ac", "2", "-movflags", "+faststart", out])
    return total


def probe(path):
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                      "stream=codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels,"
                                      "duration:"
                                      "format=duration", "-of", "json", str(path)],
                                     capture_output=True, text=True, check=True).stdout)
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    return {"video": v, "audio": a, "seconds": float(info["format"]["duration"])}


# ---------- the assembly ----------

def manifest_of(plan, cuts, layout, timeline, report, ups, music_sha, out_sha, seconds, track):
    """The render manifest qa_pilot reads for story QA v3 (LONG_DESIGN "manifest contract")."""
    by_id = {s["id"]: s for s in plan["shots"]}
    gods = {s["id"] for s in plan["shots"] if pc.speaking(s) and s.get("speaker") == eb.ch.GOD}
    holds = []
    for c in cuts:
        shot, src = by_id[c["shot"]], by_id[c["source"]]
        who = ["keeper"] if src["kind"] == "keeper" else list(src.get("characters") or [])
        holds.append({"start": c["start"], "end": c["end"], "image": f"{c['source']}#{c['src_start']:.3f}",
                      "kind": "footage", "motion": True, "beat": shot.get("beat"), "chapter": shot.get("chapter"),
                      "characters": who, "shot": c["shot"], "shot_kind": "keeper" if src["kind"] == "keeper" else
                      ("window" if c["kind"] == "window" else "scene"), "speed": c["speed"]})
    clips = []
    for s in generated(plan):
        entry = (report.get("shots") or {}).get(s["id"]) or {}
        flags = (entry.get("checks") or {}).get("flags")
        ok = "PASS" if flags == [] else ("FAIL" if flags else None)
        talking = pc.talking(s)
        f, rec = ups[s["id"]]
        clips.append({"id": s["id"], "source": AI["source"], "licence": AI["licence"], "model": AI["model"],
                      "upscaler": rec["upscaler"], "audio": AI["audio"], "vetting": AI["vetting_required"]
                      if (entry.get("approved") or {}).get("clip_sha256") == rec["source_sha256"] else "PENDING",
                      "credit": "AI video: Pavo (Agnes Video Flash), owner-owned output", "sha256": rec["sha256"],
                      "source_sha256": rec["source_sha256"], "approved_asset": rec["source_asset"],
                      "clip_check": ok, "talking": talking, "lipsync_check": ok if talking else None,
                      "voiceover": "god" if s["id"] in gods else None, "face_check": ok if s["id"] in gods else None})
    return {"version": "bible-long-manifest-v1", "pilot_id": plan.get("pilot"), "long": plan["episode"],
            "criteria_version": QA["version"], "output_sha256": out_sha, "output_seconds": seconds,
            "frame": list(FRAME), "holds": holds, "sentences": timeline["sentences"], "clips": clips, "images": {},
            "music": {"file": "original-rest-music.lossless.flac", "sha256": music_sha,
                      "offset_seconds": float(plan.get("music_offset", 600.0))}, "voice": {"voice_id": eb.VOICE["voice_id"], "speed": eb.VOICE["speed"]},
            "crossfade_seconds": 0.0, "persistent_overlays": [], "cta": [], "scripture_cards": [],
            "burned_captions": False, "captions": [], "caption_track": track,
            "keeper_share": layout.get("keeper_share"), "line_gap": eb.line_gap(plan)}


def assemble_step(plan, work, up, music, out_dir, frame=FRAME, approvals=None, render_fn=render,
                  min_seconds=MIN_SECONDS):
    """The composed long from the upscaled approved clips: OUT/<long>.mp4, captions.srt, manifest.json, report.json.
    Refused (LONG_COMPOSE_REFUSED) on a frame, length, black frame or loudness outside the frozen QA."""
    import captions
    import clip_check
    work, out_dir = Path(work), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    approvals = eb.load_approvals(plan) if approvals is None else approvals
    ups = upscaled(plan, up, approvals, frame)
    layout = eb.load(work / "layout.json")
    timeline = eb.load(work / "compose-timeline.json")
    report_path = work / "report.json"
    report = eb.load(report_path) if report_path.exists() else {"episode": plan["episode"], "shots": {}}
    import short_engine
    seconds = {k: short_engine.duration(f) for k, (f, _) in ups.items()}
    problems = compose_problems(plan, layout, seconds)
    offset = float(plan.get("music_offset", 600.0))
    music_seconds = short_engine.duration(music)
    if music_seconds + 1e-3 < offset + layout["total"]:   # review of #470: the bed under every second, never silence
        problems.append(f"MUSIC_SHORT {music_seconds:.1f} s of music for offset {offset:.1f} s + {layout['total']:.1f} s")
    if layout["total"] < min_seconds:
        problems.append(f"DURATION_UNDER_QA {layout['total']:.1f} s (story QA v3 duration_seconds_min {min_seconds})")
    if problems:
        raise SystemExit("LONG_COMPOSE_REFUSED " + "; ".join(problems))
    cuts = compose_long_shots(plan, layout, {k: str(f) for k, (f, _) in ups.items()}, seconds)
    cplan = {"voice": str(work / "narration.wav"), "timeline": str(work / "compose-timeline.json"),
             "music": str(music), "music_offset": float(plan.get("music_offset", 600.0)), "tail": eb.TAIL,
             "frame": list(frame), "shots": cuts}
    eb.save(work / "compose-plan.json", cplan)
    video = out_dir / f"{plan['episode']}.mp4"
    total = render_fn(cplan, video, frame)
    info = probe(video)
    lufs, tp = loudness(video)
    runs = clip_check.black_runs(str(video))
    dip = round(total - FADE_OUT, 2)
    bad_black = clip_check.unexpected(runs, [dip], info["seconds"])
    text, track = captions.track_record(timeline["sentences"])
    (out_dir / track["file"]).write_text(text)
    out_sha = eb.sha256(video)
    music_sha = eb.sha256(music)
    v = info["video"][0] if info["video"] else {}
    a = info["audio"][0] if info["audio"] else {}
    composed = {
        "output_sha256": out_sha, "seconds": round(info["seconds"], 3), "frame": [v.get("width"), v.get("height")],
        "fps": v.get("avg_frame_rate"), "video_codec": v.get("codec_name"), "audio": {
            "codec": a.get("codec_name"), "sample_rate": a.get("sample_rate"), "channels": a.get("channels")},
        "lufs": lufs, "true_peak_dbtp": tp, "black_check": {"black_starts": runs, "unexpected": bad_black,
                                                            "intended_dips": [dip]},
        "keeper_share": layout.get("keeper_share"), "establishing_share": establishing_share(plan, cuts, total),
        "cuts": len(cuts), "windows": sum(c["kind"] == "window" for c in cuts),
        "captions": {"file": track["file"], "sha256": track["sha256"], "cues": track["cues"], "burned": False},
        "upscaled": {k: r["sha256"] for k, (_, r) in ups.items()},
        "timeline": [{k: c.get(k) for k in ("shot", "source", "kind", "start", "end", "src_start", "speed")}
                     for c in cuts]}
    report["composed"] = composed
    eb.save(report_path, report)
    eb.save(out_dir / "report.json", report)
    eb.save(out_dir / "manifest.json", manifest_of(plan, cuts, layout, timeline, report, ups, music_sha, out_sha,
                                                   round(info["seconds"], 3), track))
    problems = []
    if [v.get("width"), v.get("height")] != list(frame) or v.get("codec_name") != "h264" or \
            v.get("avg_frame_rate") not in ("30/1", "30000/1000"):
        problems.append(f"FRAME {v.get('width')}x{v.get('height')} {v.get('codec_name')} {v.get('avg_frame_rate')} "
                        f"(QA: {frame[0]}x{frame[1]} H.264 30 fps)")
    if a.get("codec_name") != "aac" or a.get("sample_rate") != "48000" or a.get("channels") != 2:
        problems.append(f"AUDIO_FORMAT {a}")
    # review of #470: the picture's own length (the video stream), not the container's, which the audio can carry
    shown = float(v.get("duration") or 0.0)
    if abs(shown - total) > 0.1 or abs(info["seconds"] - total) > 0.1:
        problems.append(f"LENGTH video {shown:.2f} s, file {info['seconds']:.2f} s (the timeline: {total:.2f} s)")
    if info["seconds"] < min_seconds:
        problems.append(f"DURATION_UNDER_QA {info['seconds']:.1f} s (story QA v3 duration_seconds_min {min_seconds})")
    if bad_black:
        problems.append(f"BLACK_FRAMES {bad_black}")
    if lufs is None or not LUFS_BAND[0] <= lufs <= LUFS_BAND[1]:
        problems.append(f"LOUDNESS {lufs} LUFS ({LUFS_BAND[0]}..{LUFS_BAND[1]})")
    if tp is None or tp > TP_MAX:
        problems.append(f"TRUE_PEAK {tp} dBTP (<= {TP_MAX})")
    print(json.dumps({k: composed[k] for k in ("output_sha256", "seconds", "frame", "lufs", "true_peak_dbtp",
                                               "cuts")}))
    if problems:
        raise SystemExit("LONG_COMPOSE_REFUSED " + "; ".join(problems))
    return report


def sheet_step(video, sheet, frames=20):
    import short_engine
    d = short_engine.duration(video)
    tmp = Path(sheet).parent / "sheet-frames"
    tmp.mkdir(parents=True, exist_ok=True)
    for k in range(frames):
        t = d * (k + 0.5) / frames
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-vf",
             f"scale=384:216,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{t:.1f}s':"
             "x=6:y=6:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.6", tmp / f"f{k:02d}.jpg"])
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp / "f%02d.jpg", "-vf", "tile=5x4", "-frames:v", "1",
         "-q:v", "3", sheet])
    eb.safe_rmtree(tmp, Path(sheet).parent)


def checked_plan(path, verify=True):
    """The plan, refused unless it is a long that long_plan_check --strict passes and, with verify, its committed
    preflight is PASS and bound to it now (episode_preflight.verify: E106, E126)."""
    plan = eb.load(path)
    if not eb.is_long(plan):
        raise SystemExit(f"LONG_PLAN_REQUIRED {path} (version {eb.LONG_VERSION})")
    result = eb.check_plan(plan)
    if result["problems"] or result["pending"]:
        raise SystemExit("PLAN_REFUSED " + "; ".join(result["problems"] + result["pending"]))
    if verify:
        import episode_preflight
        bad = episode_preflight.verify(path)
        if bad:
            raise SystemExit(bad)
    return plan


def main(argv):
    if len(argv) == 4 and argv[1] == "sheet":
        return sheet_step(argv[2], argv[3])
    if len(argv) in (3, 4) and argv[1] == "upscale-ids":
        plan = checked_plan(argv[2], verify=False)
        names = Path(argv[3]).read_text().split() if len(argv) == 4 else []
        print(json.dumps(upscale_ids(plan, names)))
        return 0
    if len(argv) == 6 and argv[1] == "resume-names":   # RUN REPO EP OUT: the artifact names a resume keeps
        Path(argv[5]).write_text("".join(f"{n}\n" for n in resume_names(argv[2], argv[3], argv[4])))
        return 0
    if len(argv) == 6 and argv[1] == "resume-download":   # RUN REPO EP DEST
        resume_download(argv[2], argv[3], argv[4], argv[5])
        return 0
    if len(argv) == 4 and argv[1] == "timeline":
        timeline_step(checked_plan(argv[2]), argv[3])
    elif len(argv) == 6 and argv[1] == "upscale":
        upscale_step(checked_plan(argv[2]), argv[3], argv[4], argv[5])
    elif len(argv) == 7 and argv[1] == "assemble":
        assemble_step(checked_plan(argv[2]), argv[3], argv[4], argv[5], argv[6])
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
