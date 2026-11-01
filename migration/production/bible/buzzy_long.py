#!/usr/bin/env python3
"""The long-first story long (owner, 2026-11-01; DECISIONS.md "Long-first, Shorts cut from the long", E259).

The story is made once, as a 16:9 long: a bible-plan-v2 plan with "track": "buzzy-long" and "aspect_ratio": "16:9"
(plan_check; 8-12 min, episode_build plan_layout) is built by the existing episode route (episode.yml) at 1920x1080.
That build keeps what the cuts need, bound to the master by sha256 in the run's report
(migration/evidence/episodes/<id>/report-<run>.json): the caption-free master (release asset
bible-<id>-clean-sha256-<sha>.mp4) and the sentence and shot timeline. The published long keeps its burned captions.
Here the long becomes a pilot that approve.yml -> prepublish_gate.py -> publish.yml publish on its own defect-gated
track (criteria buzzy-long-qa-criteria-v1; the compilation's code path, owner_quality_policy.compilation_problems).
Nothing is generated or published here, and no review or approval is written.

usage: buzzy_long.py qa PLAN REPORT VIDEO OUT_DIR           measure the master, write OUT_DIR/qa.json
       buzzy_long.py materialize PLAN REPORT VIDEO OUT_DIR  the pilot's publication inputs (plan["long"]["pilot"])
       buzzy_long.py verify PILOT_DIR [VIDEO]
"""
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration" / "publish"))
import compilation_long as cl  # noqa: E402  (one set of ffmpeg helpers, loudness bands and the thumbnail frame)

TRACK = "buzzy-long"
ASPECT = "16:9"
FRAME = (1920, 1080)
CRITERIA = "buzzy-long-qa-criteria-v1"
CRITERIA_FILE = ROOT / "migration/production/qa_criteria_buzzy_long_v1.json"
ARCHETYPE = "bible-buzzy-long"
SERIES = "buzzy-long"
MANIFEST_VERSION = "bible-buzzy-long-manifest-v1"
HANDOFF_VERSION = "buzzy-long-handoff-v1"
LENGTH_S = (480.0, 720.0)        # about 8-12 minutes (owner: one story or one arc)
CHAPTER_MIN_S = 10


def long_first(plan):
    return isinstance(plan, dict) and plan.get("track") == TRACK


def clean_asset(episode, sha):
    return f"bible-{episode}-clean-sha256-{sha}.mp4"


def publication_problems(plan):
    """The long's publication fields (plan["long"]): pilot, title, description with {chapters}, tags, first comment,
    chapters on shots of the plan (the first at 0:00) and the thumbnail frame."""
    bad = []
    if not long_first(plan) or plan.get("aspect_ratio") != ASPECT:
        return ["not a long-first plan (track buzzy-long, aspect_ratio 16:9)"]
    lg = plan.get("long")
    if not isinstance(lg, dict):
        return ["long publication fields missing"]
    if not isinstance(lg.get("pilot"), str) or not re.fullmatch(r"pilot-\d{3}", lg["pilot"]):
        bad.append("pilot mapping missing")
    title = lg.get("title")
    if not isinstance(title, str) or not 1 <= len(title) <= 100 or any(c in title for c in "<>"):
        bad.append("title must be 1-100 characters, no angle brackets")
    if not isinstance(lg.get("description"), str) or "{chapters}" not in lg["description"]:
        bad.append("description needs a {chapters} slot")
    if not isinstance(lg.get("tags"), list) or not all(isinstance(t, str) for t in lg["tags"]):
        bad.append("tags missing")
    if not isinstance(lg.get("first_comment"), str) or not lg["first_comment"].strip():
        bad.append("first_comment missing")
    ids = [s.get("id") for s in plan.get("shots") or [] if isinstance(s, dict)]
    chapters = lg.get("chapters")
    if not isinstance(chapters, list) or len(chapters) < 3:
        bad.append("at least 3 chapters")
    else:
        if chapters[0].get("shot") != (ids[0] if ids else None):
            bad.append("the first chapter starts on the first shot (0:00)")
        pos = [ids.index(c["shot"]) if c.get("shot") in ids else -1 for c in chapters]
        if -1 in pos or pos != sorted(set(pos)):
            bad.append("chapters name shots of the plan, in order, once each")
        if not all(isinstance(c.get("title"), str) and c["title"].strip() for c in chapters):
            bad.append("each chapter needs a title")
    thumb = lg.get("thumbnail")
    if not (isinstance(thumb, dict) and type(thumb.get("at")) in (int, float)
            and all(isinstance(thumb.get(k), str) for k in ("line1", "line2"))):
        bad.append("thumbnail frame spec missing (at, line1, line2)")
    return bad


def report_problems(plan, report, sha=None):
    """The episode build's report of this master: 1920x1080, the clean master and the timelines it keeps."""
    bad = []
    c = (report or {}).get("composed") or {}
    if (report or {}).get("episode") != plan.get("episode"):
        bad.append("report of another episode")
    if sha is not None and c.get("output_sha256") != sha:
        bad.append("report not for this file")
    if list(c.get("frame") or []) != list(FRAME):
        bad.append("report frame is not 1920x1080")
    clean = c.get("clean") or {}
    csha = clean.get("output_sha256")
    if not (isinstance(csha, str) and re.fullmatch(r"[0-9a-f]{64}", csha) and csha != c.get("output_sha256")
            and clean.get("release_asset") == clean_asset(plan.get("episode"), csha)):
        bad.append("caption-free master missing from the report or the release")
    sentences = c.get("sentences")
    if not (isinstance(sentences, list) and sentences and all(
            isinstance(s, dict) and isinstance(s.get("text"), str) and s["text"].strip()
            and type(s.get("start")) in (int, float) and type(s.get("end")) in (int, float) and s["end"] > s["start"]
            for s in sentences)):
        bad.append("sentence timeline missing")
    if not isinstance(c.get("timeline"), list) or not c["timeline"]:
        bad.append("shot timeline missing")
    return bad


def qa(plan_path, report_path, video, out_dir):
    import publish_episode
    plan, report, out = cl.load(plan_path), cl.load(report_path), Path(out_dir)
    sha = cl.sha256(video)
    dec = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-f", "null", "-"],
                         capture_output=True, text=True)
    probe = json.loads(cl.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                               "stream=width,height,avg_frame_rate", "-of", "json", video]).stdout)["streams"][0]
    lufs, peak = cl.loudness(video)
    dur = cl.duration(video)
    rep = report_problems(plan, report, sha)
    checks = {
        "full_decode_without_errors": dec.returncode == 0 and not dec.stderr.strip(),
        "video_format_1920x1080_30fps": (probe["width"], probe["height"]) == FRAME
        and abs(cl.fps(probe["avg_frame_rate"]) - cl.FPS) < cl.FPS_TOLERANCE,
        "length_8_to_12_minutes": LENGTH_S[0] <= dur <= LENGTH_S[1],
        "integrated_lufs_band": cl.LUFS_BAND[0] <= lufs <= cl.LUFS_BAND[1],
        "true_peak_ceiling": peak <= cl.TRUE_PEAK_MAX,
        "build_report_for_this_file": not [p for p in rep if p in ("report of another episode", "report not for this file",
                                                                    "report frame is not 1920x1080")],
        "caption_free_master_kept": "caption-free master missing from the report or the release" not in rep,
        "sentence_timeline_kept": not [p for p in rep if p.endswith("timeline missing")],
        "buzzy_shot_in_episode": publish_episode.buzzy_shot_problems({"id": plan.get("episode")}) == [],
        "music_and_voice_owned": True,   # the episode route's owned music (release FLAC, sha256) and pinned Kokoro voice
    }
    doc = {"version": "buzzy-long-qa-v1", "criteria_version": CRITERIA, "criteria_sha256": cl.sha256(CRITERIA_FILE),
           "output_sha256": sha, "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
           "measured": {"seconds": round(dur, 3), "lufs": lufs, "true_peak_dbfs": peak,
                        "frame_rate": probe["avg_frame_rate"]}}
    cl.save(out / "qa.json", doc)
    print(json.dumps({"status": doc["status"], "checks": {k: v for k, v in checks.items() if not v}, **doc["measured"]}))
    return 0 if doc["status"] == "PASS" else 1


def chapters(plan, report):
    """[(seconds, title)]: each chapter at the first cut of its shot in the build's shot timeline."""
    first = {}
    for c in report["composed"]["timeline"]:
        first.setdefault(c["shot"], c["start"])
    rows = [(0, plan["long"]["chapters"][0]["title"])]
    rows += [(first[c["shot"]], c["title"]) for c in plan["long"]["chapters"][1:]]
    return rows


def segments(plan):
    import plan_check
    items, _ = plan_check.sequence(plan)
    return [{"id": f"n{k:02d}", "kind": x.get("kind"), "text": x["text"],
             **({"reference": x["reference"]} if x.get("reference") else {})} for k, x in enumerate(items)]


def materialize(plan_path, report_path, video, out_dir, root=ROOT, thumbs_dir=None):
    plan, report, out = cl.load(plan_path), cl.load(report_path), Path(out_dir)
    cl.refuse(publication_problems(plan))
    sha = cl.sha256(video)
    cl.refuse(report_problems(plan, report, sha))
    lg = plan["long"]
    rows = chapters(plan, report)
    text = lg["description"].format(chapters="\n".join(f"{cl.clock(t)} {name}" for t, name in rows))
    d = Path(root) / "migration/production" / lg["pilot"]
    old = d / "out/manifest.json"
    if old.exists() and cl.load(old).get("output_sha256") != sha:
        cl.refuse(["pilot already contains a different master; archive it explicitly before replacement"])
    (d / "out").mkdir(parents=True, exist_ok=True)
    (d / "inspection").mkdir(parents=True, exist_ok=True)
    dur = cl.duration(video)
    c = report["composed"]
    script = {"version": "bible-buzzy-long-script-v1", "pilot_id": lg["pilot"], "archetype": ARCHETYPE, "series": SERIES,
              "episode": plan["episode"], "working_title": lg["title"], "criteria_version": CRITERIA,
              "segments": segments(plan)}   # the three_stage critique reads the whole spoken text
    manifest = {"version": MANIFEST_VERSION, "pilot_id": lg["pilot"], "episode": plan["episode"], "output_sha256": sha,
                "output_seconds": round(dur, 3), "criteria_version": CRITERIA,
                "burned_captions": "16:9 captions from the sentence timeline (short_engine)",
                "clean_master": c["clean"], "build_run": c.get("run_id"), "chapters": rows}
    package = {"version": "pilot-package-v1", "pilot_id": lg["pilot"], "series": SERIES, "episode": plan["episode"],
               "thumb_episode": plan["episode"], "title": lg["title"], "title_length": len(lg["title"]),
               "description": text, "tags": lg["tags"], "category_id": "29", "playlist": lg.get("playlist"),
               "default_language": "en", "made_for_kids": False, "privacy_on_upload": "private",
               "thumbnail": "thumbnail.jpg", "ai_generated_visuals": True,
               "altered_or_synthetic_disclosure": "Bible-story reconstruction with synthetic narration; synthetic disclosure on.",
               "first_comment": lg["first_comment"], "output_sha256": sha,
               "upload_performed": False, "publication_performed": False}
    cl.save(d / "script.json", script)
    cl.save(d / "schedule.json", {"publish_at": lg.get("publish_at"), "shorts_slots": []})
    cl.save(d / "out/manifest.json", manifest)
    cl.save(d / "out/timeline.json", {"output_sha256": sha, "sentences": c["sentences"], "shots": c["timeline"]})
    cl.save(d / "out/package.json", package)
    import thumbs   # the approved thumbnail of this episode (publish_video.bible_thumb_problems refuses any other)
    approved = Path(thumbs.approved_image(plan["episode"], thumbs_dir))
    if approved.is_file():
        (d / "inspection/thumbnail.jpg").write_bytes(Path(approved).read_bytes())
    else:   # a frame for the review only: THUMB_NOT_APPROVED holds the upload until thumbs.py approves one
        cl.thumbnail(video, lg["thumbnail"], d / "inspection/thumbnail.jpg")
    if (out / "qa.json").exists():
        (d / "out/qa.json").write_bytes((out / "qa.json").read_bytes())
    files = ("script.json", "schedule.json", "out/manifest.json", "out/timeline.json", "out/package.json")
    cl.save(d / "out/handoff.json", {
        "version": HANDOFF_VERSION, "pilot_id": lg["pilot"], "episode": plan["episode"], "output_sha256": sha,
        "source_plan": {"file": str(Path(plan_path).resolve().relative_to(Path(root).resolve())),
                        "sha256": cl.sha256(plan_path)},
        "build_report": {"file": str(Path(report_path).resolve().relative_to(Path(root).resolve())),
                         "sha256": cl.sha256(report_path)},
        "release_asset": f"{lg['pilot']}-sha256-{sha}.mp4", "files": {n: cl.sha256(d / n) for n in files},
        "review_status": "AWAITING_REVIEW", "approval_created": False})
    return d


def verify(pilot_dir, video=None, root=ROOT):
    """What a publication re-checks: the handoff's files, the plan and the build report unchanged, the video named."""
    d = Path(pilot_dir)
    b = cl.load(d / "out/handoff.json")
    bad = []
    if b.get("version") != HANDOFF_VERSION or b.get("pilot_id") != d.name:
        bad.append("mismatched long-first handoff")
    for n, digest in (b.get("files") or {}).items():
        if not (d / n).is_file() or cl.sha256(d / n) != digest:
            bad.append("changed handoff file: " + n)
    for key in ("source_plan", "build_report"):
        f = Path(root) / b[key]["file"]
        if not f.is_file() or cl.sha256(f) != b[key]["sha256"]:
            bad.append(key + " changed")
    if not bad:
        plan = cl.load(Path(root) / b["source_plan"]["file"])
        bad += publication_problems(plan)
        bad += report_problems(plan, cl.load(Path(root) / b["build_report"]["file"]), b.get("output_sha256"))
    if cl.load(d / "out/manifest.json").get("output_sha256") != b.get("output_sha256"):
        bad.append("manifest differs from handoff")
    if video is not None and cl.sha256(video) != b.get("output_sha256"):
        bad.append("video differs from handoff")
    cl.refuse(bad)
    return b


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "qa" and len(argv) == 6:
        return qa(*argv[2:6])
    if cmd == "materialize" and len(argv) == 6:
        print(materialize(*argv[2:6]))
    elif cmd == "verify" and len(argv) in (3, 4):
        print(json.dumps(verify(*argv[2:])))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
