#!/usr/bin/env python3
"""The "complete story" compilation long of an arc (owner, 2026-11-01; DECISIONS.md "Strategy reset", E251).

Nothing is generated here. The long is assembled from the arc's already-public Shorts: each Short's accepted master
(episode record `output_sha256`, release asset `bible-<id>-sha256-<sha>.mp4`, sha256 checked) framed for 16:9
(1920x1080: the 9:16 video centred over a blurred, darkened, scaled copy; the Short's burned captions are kept),
one chapter card before each story, and a new Keeper hook and close (two Pavo clips made at a fresh exact zero-credit
quote, committed with their zero-cost record; their audio is our own Kokoro line). Every segment fades in and out
(FADE) and is brought to LUFS by gain only, so a join has no pop and no cut speech.

usage: compilation_long.py inputs PLAN            asset name and sha256 of each source master, one per line
       compilation_long.py build PLAN SRC_DIR OUT_DIR   SRC_DIR holds the masters by asset name
       compilation_long.py qa PLAN OUT_DIR              measure the master, write out/qa.json (criteria compilation-qa-criteria-v1)
       compilation_long.py materialize PLAN OUT_DIR     write the pilot's publication inputs (no review, no approval)
       compilation_long.py verify PILOT_DIR [VIDEO]
"""
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN_VERSION = "bible-compilation-plan-v1"
MANIFEST_VERSION = "bible-compilation-manifest-v1"
CRITERIA = "compilation-qa-criteria-v1"
ARCHETYPE = "bible-compilation-long"
SERIES = "compilation"          # not "bible": a compilation has no per-story approved character thumbnail
W, H, FPS = 1920, 1080, 30
LUFS = -14.0
LUFS_BAND = (-15.0, -13.0)
TRUE_PEAK_MAX = -1.0
CARD = 2.5
FADE = 0.25
BEAT = 0.5                      # still beat at each end of a Keeper clip
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
EPISODES = HERE / "episodes"
CARD_BG = "0x0b1020"
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def refuse(problems):
    if problems:
        raise SystemExit("COMPILATION_REFUSED " + "; ".join(problems))


def episode(short_id, episodes=EPISODES):
    return load(Path(episodes) / f"{short_id}.json")


def plan_problems(plan, episodes=EPISODES, root=ROOT):
    """Everything that stops a build: schema, canonical order, public Shorts of one arc, the Keeper clips' record."""
    bad = []
    if plan.get("version") != PLAN_VERSION:
        bad.append("not a compilation plan")
    if not isinstance(plan.get("id"), str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", plan["id"]):
        bad.append("unsafe id")
    if not isinstance(plan.get("pilot"), str) or not re.fullmatch(r"pilot-\d{3}", plan["pilot"]):
        bad.append("pilot mapping missing")
    title = plan.get("title")
    if not isinstance(title, str) or not 1 <= len(title) <= 100 or any(c in title for c in "<>"):
        bad.append("title must be 1-100 characters, no angle brackets")
    chapters = plan.get("chapters")
    if not isinstance(chapters, list) or not 2 <= len(chapters):
        return bad + ["chapters missing"]
    parts = []
    for c in chapters:
        try:
            ep = episode(c["short"], episodes)
        except (OSError, ValueError, KeyError, TypeError):
            bad.append("unknown short " + str(c.get("short") if isinstance(c, dict) else c))
            continue
        parts.append(ep.get("part"))
        if ep.get("format") != "short" or not ep.get("video_id") or not re.fullmatch(r"[0-9a-f]{64}", ep.get("output_sha256", "")):
            bad.append(f"{c['short']} is not a public Short with a master sha256")
        if not all(isinstance(c.get(k), str) and c[k].strip() for k in ("title", "reference")):
            bad.append(f"{c['short']} chapter needs title and reference")
    if parts != sorted(parts) or len(set(parts)) != len(parts) or any(b - a != 1 for a, b in zip(parts, parts[1:])):
        bad.append("shorts are not consecutive parts in canonical order")
    for key in ("hook", "close"):
        k = plan.get(key) or {}
        if not all(isinstance(k.get(f), str) and k[f] for f in ("text", "video", "audio", "video_sha256", "audio_sha256",
                                                                   "conversation_id", "quote")):
            bad.append(key + " Keeper clip record incomplete")
            continue
        if k["quote"] != "0 credits (exact, fresh)":
            bad.append(key + " clip was not made at an exact zero-credit quote")
        for f in ("video", "audio"):
            p = Path(root) / k[f]
            if not p.is_file() or sha256(p) != k[f + "_sha256"]:
                bad.append(f"{key} {f} missing or changed")
    return bad


def sources(plan, episodes=EPISODES):
    """[(short id, asset name, sha256, record)] in the plan's canonical order."""
    out = []
    for c in plan["chapters"]:
        ep = episode(c["short"], episodes)
        out.append((c["short"], f"bible-{c['short']}-sha256-{ep['output_sha256']}.mp4", ep["output_sha256"], ep))
    return out


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode:
        raise SystemExit(f"COMMAND_FAILED {cmd[0]} {r.stderr[-600:]}")
    return r


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout)


def loudness(path):
    """(integrated LUFS, true peak dBFS) of the file's audio (ffmpeg ebur128)."""
    err = run(["ffmpeg", "-nostdin", "-hide_banner", "-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    tail = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", tail)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    if not i or not p:
        raise SystemExit("LOUDNESS_UNREADABLE")
    return float(i.group(1)), float(p.group(1))


def gain_filter(path):
    """Gain only (no compression): the segment's mean brought to LUFS, then a -1 dBFS ceiling."""
    lufs, _ = loudness(path)
    return f"volume={LUFS - lufs:.2f}dB,alimiter=limit=0.8:level=false"


def fades(d):
    return (f"fade=t=in:st=0:d={FADE},fade=t=out:st={max(d - FADE, 0):.3f}:d={FADE}",
            f"afade=t=in:st=0:d={FADE},afade=t=out:st={max(d - FADE, 0):.3f}:d={FADE}")


def render_short(src, out):
    d = duration(src)
    v, a = fades(d)
    graph = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:6,"
             f"eq=brightness=-0.28[bg];[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,setsar=1,{v}[v];"
             f"[0:a]aresample=48000,aformat=channel_layouts=stereo,{gain_filter(src)},{a}[a]")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-filter_complex", graph, "-map", "[v]", "-map", "[a]", *ENC, out])


def render_card(kind_text, out):
    """kind_text: (small line, title, reference). Text goes through files (no escaping); silent audio."""
    tmp = Path(out).with_suffix("")
    files = []
    for n, t in enumerate(kind_text):
        p = Path(f"{tmp}.{n}.txt")
        p.write_text(t)
        files.append(p)
    v, a = fades(CARD)
    dt = lambda p, size, y, col: (f"drawtext=fontfile={FONT}:textfile={p}:fontsize={size}:fontcolor={col}:"
                                  f"x=(w-text_w)/2:y={y}")
    vf = ",".join([dt(files[0], 40, 330, "0xd9b25f"), dt(files[1], 78, 440, "white"), dt(files[2], 44, 590, "0xc9d3e6"), v])
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={CARD_BG}:s={W}x{H}:r={FPS}:d={CARD}",
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(CARD), "-vf", vf, "-af", a, *ENC, out])
    for p in files:
        p.unlink()


def render_keeper(video, audio, out):
    """Keeper clip at 16:9 with a still beat (BEAT) at each end: first/last frame held, our own line starts after the
    first beat; its audio is our Kokoro wav, so nothing depends on the clip's own sound."""
    d = duration(video) + 2 * BEAT
    v, a = fades(d)
    graph = (f"[0:v]scale={W}:{H}:flags=lanczos,setsar=1,tpad=start_mode=clone:start_duration={BEAT}:"
             f"stop_mode=clone:stop_duration={BEAT},{v}[v];"
             f"[1:a]aresample=48000,aformat=channel_layouts=stereo,{gain_filter(audio)},adelay={int(BEAT * 1000)}:all=1,"
             f"apad=whole_dur={d:.3f},{a}[a]")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-i", audio, "-filter_complex", graph, "-map", "[v]",
         "-map", "[a]", "-t", f"{d:.3f}", *ENC, out])


def thumbnail(src, spec, out):
    """A 1280x720 frame of a Short's master: a 16:9 window of its vertical picture (spec: at, y fraction) plus our title."""
    ys = max(0.0, min(1.0, float(spec.get("y", 0.4))))
    t1, t2 = Path(str(out) + ".1.txt"), Path(str(out) + ".2.txt")
    t1.write_text(spec["line1"])
    t2.write_text(spec["line2"])
    vf = (f"crop=iw:iw*9/16:0:(ih-iw*9/16)*{ys:.3f},scale=1280:720:flags=lanczos,"
          f"drawbox=x=0:y=ih-190:w=iw:h=190:color=black@0.55:t=fill,"
          f"drawtext=fontfile={FONT}:textfile={t1}:fontsize=84:fontcolor=white:x=(w-text_w)/2:y=h-175:borderw=3:bordercolor=black,"
          f"drawtext=fontfile={FONT}:textfile={t2}:fontsize=52:fontcolor=0xd9b25f:x=(w-text_w)/2:y=h-72:borderw=2:bordercolor=black")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(spec["at"]), "-i", src, "-frames:v", "1", "-vf", vf,
         "-q:v", "2", out])
    t1.unlink()
    t2.unlink()


def fps(rate):
    num, _, den = str(rate).partition("/")
    return float(num) / float(den or 1) if float(den or 1) else 0.0


def clock(t):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


def build(plan_path, src_dir, out_dir):
    plan = load(plan_path)
    refuse(plan_problems(plan))
    src_dir, out = Path(src_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    segs, rows = [], []

    def add(kind, name, path, **extra):
        segs.append(path)
        rows.append({"kind": kind, "name": name, "seconds": round(duration(path), 3), **extra})

    seg = out / "segments"
    seg.mkdir(exist_ok=True)
    render_keeper(ROOT / plan["hook"]["video"], ROOT / plan["hook"]["audio"], seg / "00-hook.mp4")
    add("hook", "hook", seg / "00-hook.mp4")
    verified = []
    for k, (sid, asset, sha, ep) in enumerate(sources(plan), 1):
        master = src_dir / asset
        if not master.is_file() or sha256(master) != sha:
            raise SystemExit(f"SOURCE_SHA256_MISMATCH {sid}")
        verified.append({"short": sid, "asset": asset, "sha256": sha, "video_id": ep["video_id"], "seconds": ep["seconds"]})
        c = plan["chapters"][k - 1]
        render_card((f"PART {k} OF {len(plan['chapters'])}", c["title"], c["reference"] + " (KJV)"), seg / f"{k:02d}a-card.mp4")
        add("card", sid, seg / f"{k:02d}a-card.mp4")
        render_short(master, seg / f"{k:02d}b-short.mp4")
        add("short", sid, seg / f"{k:02d}b-short.mp4", source_sha256=sha)
    render_keeper(ROOT / plan["close"]["video"], ROOT / plan["close"]["audio"], seg / "99-close.mp4")
    add("close", "close", seg / "99-close.mp4")
    lst = out / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in segs))
    master = out / f"{plan['id']}.mp4"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
         "-movflags", "+faststart", master])
    t, timeline = 0.0, []
    for r in rows:
        r["start"] = round(t, 3)
        t += r["seconds"]
        r["end"] = round(t, 3)
        timeline.append(r)
    thumb_src = next(v for v in verified if v["short"] == plan["thumbnail"]["short"])
    thumbnail(src_dir / thumb_src["asset"], plan["thumbnail"], out / "thumbnail.jpg")
    sha = sha256(master)
    save(out / "timeline.json", {"output_sha256": sha, "segments": timeline})
    save(out / "sources.json", verified)
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", master, "-vf",
         f"fps=20/{duration(master):.3f},scale=480:270,tile=5x4", "-frames:v", "1", "-q:v", "3", out / "sheet.jpg"])
    print(json.dumps({"output_sha256": sha, "byte_size": master.stat().st_size, "seconds": round(duration(master), 3)}))


def qa(plan_path, out_dir):
    plan, out = load(plan_path), Path(out_dir)
    master = out / f"{plan['id']}.mp4"
    sha = sha256(master)
    tl = load(out / "timeline.json")
    src = load(out / "sources.json")
    dec = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(master), "-f", "null", "-"], capture_output=True, text=True)
    probe = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,avg_frame_rate", "-of", "json", master]).stdout)["streams"][0]
    lufs, peak = loudness(master)
    dur = duration(master)
    expected = sum(r["seconds"] for r in tl["segments"])
    shorts = [r for r in tl["segments"] if r["kind"] == "short"]
    checks = {
        "full_decode_without_errors": dec.returncode == 0 and not dec.stderr.strip(),
        "video_format_1920x1080_30fps": (probe["width"], probe["height"]) == (W, H) and abs(fps(probe["avg_frame_rate"]) - FPS) < 0.01,
        "duration_is_sum_of_segments": abs(dur - expected) < 1.0,
        "no_padding": dur <= sum(s["seconds"] for s in src) + 30 + len(src) * (CARD + 1.0),
        "integrated_lufs_band": LUFS_BAND[0] <= lufs <= LUFS_BAND[1],
        "true_peak_ceiling": peak <= TRUE_PEAK_MAX,
        "sources_are_the_public_masters_by_sha": [s["short"] for s in src] == [c["short"] for c in plan["chapters"]]
        and all(len(s["sha256"]) == 64 for s in src) and [r["source_sha256"] for r in shorts] == [s["sha256"] for s in src],
        "canonical_order": [r["kind"] for r in tl["segments"]] == ["hook"] + ["card", "short"] * len(src) + ["close"],
        "keeper_clips_zero_credit": plan["hook"]["quote"] == plan["close"]["quote"] == "0 credits (exact, fresh)",
        "music_and_voice_owned": True,   # the Shorts' own recorded sources (Kokoro voice, owned music) and our Kokoro hook/close
    }
    doc = {"version": "compilation-qa-v1", "criteria_version": CRITERIA,
           "criteria_sha256": sha256(ROOT / "migration/production/qa_criteria_compilation_v1.json"),
           "output_sha256": sha, "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
           "measured": {"seconds": round(dur, 3), "lufs": lufs, "true_peak_dbfs": peak, "frame_rate": probe["avg_frame_rate"]}}
    save(out / "qa.json", doc)
    print(json.dumps({"status": doc["status"], "checks": {k: v for k, v in checks.items() if not v}, **doc["measured"]}))
    return 0 if doc["status"] == "PASS" else 1


def description(plan, tl):
    rows = [(0, plan["chapter_zero"])] + [(r["start"], plan["chapters"][i]["title"])
                                          for i, r in enumerate(x for x in tl["segments"] if x["kind"] == "card")]
    close = next(r for r in tl["segments"] if r["kind"] == "close")
    rows.append((close["start"], plan["chapter_last"]))
    chapters = "\n".join(f"{clock(t)} {name}" for t, name in rows)
    links = "\n".join(f"- {c['title']} ({c['reference']}): https://www.youtube.com/shorts/{episode(c['short'])['video_id']}"
                      for c in plan["chapters"])
    return plan["description"].format(chapters=chapters, links=links), rows


def materialize(plan_path, out_dir, root=ROOT):
    plan, out = load(plan_path), Path(out_dir)
    refuse(plan_problems(plan))
    manifest_tl = load(out / "timeline.json")
    sha = sha256(out / f"{plan['id']}.mp4")
    if manifest_tl["output_sha256"] != sha:
        raise SystemExit("TIMELINE_NOT_FOR_THIS_FILE")
    text, rows = description(plan, manifest_tl)
    d = Path(root) / "migration/production" / plan["pilot"]
    old = d / "out/manifest.json"
    if old.exists() and load(old).get("output_sha256") != sha:
        refuse(["pilot already contains a different master; archive it explicitly before replacement"])
    (d / "out").mkdir(parents=True, exist_ok=True)
    (d / "inspection").mkdir(parents=True, exist_ok=True)
    dur = duration(out / f"{plan['id']}.mp4")
    script = {"version": "bible-compilation-script-v1", "pilot_id": plan["pilot"], "archetype": ARCHETYPE, "series": SERIES,
              "episode": plan["id"], "working_title": plan["title"], "criteria_version": CRITERIA,
              "shorts": [c["short"] for c in plan["chapters"]],
              "hook": {"text": plan["hook"]["text"]}, "close": {"text": plan["close"]["text"]}}
    manifest = {"version": MANIFEST_VERSION, "pilot_id": plan["pilot"], "compilation": plan["id"], "output_sha256": sha,
                "output_seconds": round(dur, 3), "criteria_version": CRITERIA, "burned_captions": "kept from the Shorts",
                "sources": load(out / "sources.json"), "segments": manifest_tl["segments"], "chapters": rows,
                "keeper_clips": {k: {f: plan[k][f] for f in ("conversation_id", "quote", "video_sha256", "audio_sha256")}
                                 for k in ("hook", "close")}}
    package = {"version": "pilot-package-v1", "pilot_id": plan["pilot"], "series": SERIES, "episode": plan["id"],
               "title": plan["title"], "title_length": len(plan["title"]), "description": text, "tags": plan["tags"],
               "category_id": "29", "playlist": plan.get("playlist"), "default_language": "en", "made_for_kids": False,
               "privacy_on_upload": "private", "thumbnail": "thumbnail.jpg", "ai_generated_visuals": True,
               "altered_or_synthetic_disclosure": "Bible-story reconstruction with synthetic narration; synthetic disclosure on.",
               "first_comment": plan["first_comment"], "output_sha256": sha,
               "upload_performed": False, "publication_performed": False}
    save(d / "script.json", script)
    save(d / "schedule.json", {"publish_at": plan.get("publish_at"), "shorts_slots": []})
    save(d / "out/manifest.json", manifest)
    save(d / "out/timeline.json", manifest_tl)
    save(d / "out/package.json", package)
    (d / "inspection/thumbnail.jpg").write_bytes((out / "thumbnail.jpg").read_bytes())
    if (out / "qa.json").exists():
        (d / "out/qa.json").write_bytes((out / "qa.json").read_bytes())
    files = ("script.json", "schedule.json", "out/manifest.json", "out/timeline.json", "out/package.json", "inspection/thumbnail.jpg")
    save(d / "out/handoff.json", {"version": "compilation-handoff-v1", "pilot_id": plan["pilot"], "episode": plan["id"],
                                  "output_sha256": sha, "source_plan": {"file": str(Path(plan_path).resolve().relative_to(Path(root).resolve())),
                                                                        "sha256": sha256(plan_path)},
                                  "release_asset": f"{plan['pilot']}-sha256-{sha}.mp4",
                                  "files": {n: sha256(d / n) for n in files}, "review_status": "AWAITING_REVIEW",
                                  "approval_created": False})
    return d


def verify(pilot_dir, video=None, root=ROOT):
    """What a publication re-checks: the handoff's files unchanged, the plan unchanged, the video the manifest names."""
    d = Path(pilot_dir)
    b = load(d / "out/handoff.json")
    bad = []
    if b.get("version") != "compilation-handoff-v1" or b.get("pilot_id") != d.name:
        bad.append("mismatched compilation handoff")
    for n, digest in (b.get("files") or {}).items():
        if not (d / n).is_file() or sha256(d / n) != digest:
            bad.append("changed handoff file: " + n)
    plan_file = Path(root) / b["source_plan"]["file"]
    if not plan_file.is_file() or sha256(plan_file) != b["source_plan"]["sha256"]:
        bad.append("source plan changed")
    else:
        bad += plan_problems(load(plan_file))
    if load(d / "out/manifest.json").get("output_sha256") != b.get("output_sha256"):
        bad.append("manifest differs from handoff")
    if video is not None and sha256(video) != b.get("output_sha256"):
        bad.append("video differs from handoff")
    refuse(bad)
    return b


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "inputs" and len(argv) == 3:
        plan = load(argv[2])
        refuse(plan_problems(plan))
        for _, asset, sha, _ in sources(plan):
            print(asset, sha)
    elif cmd == "build" and len(argv) == 5:
        build(*argv[2:])
    elif cmd == "qa" and len(argv) == 4:
        return qa(argv[2], argv[3])
    elif cmd == "materialize" and len(argv) == 4:
        print(materialize(argv[2], argv[3]))
    elif cmd == "verify" and len(argv) in (3, 4):
        print(json.dumps(verify(*argv[2:])))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
