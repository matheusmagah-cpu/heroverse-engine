#!/usr/bin/env python3
"""The approved-clip long's measured files enter the existing pilot publication path.

No QA, review score or approval is created here. The workflow measures the same MP4
with qa_pilot, and approve.yml remains the only writer of APPROVAL.json.
usage: long_handoff.py inputs PLAN
       long_handoff.py materialize PLAN BUILT_DIR
       long_handoff.py verify PILOT_DIR [VIDEO]
       long_handoff.py capacity VIDEO PILOT_OR_EMPTY
"""
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "publish"))
import plan_check as pc
import long_plan_check as lpc
import thumbs
import captions
import prepublish_gate as gate


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
        raise SystemExit("LONG_HANDOFF_REFUSED " + "; ".join(problems))


def release_uploads(size, pilot=True, part_bytes=1900 * 1024 * 1024):
    """release_video.sh's real split count, once for the Bible asset and once for the existing pilot alias."""
    return max(1, math.ceil(size / part_bytes)) * (2 if pilot else 1) + 1


def release_capacity(video, pilot=True, api=None):
    # The dispatch guard reserves the minimum before render; here the actual size includes all split parts.
    sys.path.insert(0, str(ROOT / "migration/ops"))
    import dispatch_guard
    if api is None:
        api = lambda path: dispatch_guard.github(path, os.environ.get("GH_TOKEN", ""), os.environ["GITHUB_REPOSITORY"])
    need = release_uploads(Path(video).stat().st_size, pilot)
    used = dispatch_guard.asset_count(api, dispatch_guard.newest_tag())
    if used + need > 1000:
        raise SystemExit(f"LONG_RELEASE_CAPACITY {used} assets + {need} measured parts; preserve the artifact and add a release")
    return {"used": used, "new_assets_max": need}


def input_documents(plan_path, root=ROOT, check_thumbnail=True):
    root, plan_path = Path(root), Path(plan_path)
    plan = load(plan_path)
    import episode_build
    refuse(episode_build.revocation_problems(plan.get("episode"),
           shots_dir=root / "migration/production/bible/shots"))
    episode, pilot = plan.get("episode"), plan.get("pilot")
    bad = []
    if plan.get("version") != "bible-long-plan-v1" or not isinstance(episode, str) or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*-long", episode):
        bad.append("not a long plan with a safe episode id")
    if not isinstance(pilot, str) or not re.fullmatch(r"pilot-\d{3}", pilot):
        bad.append("pilot mapping missing or invalid")
    if episode != str(plan.get("arc")) + "-long":
        bad.append("episode does not match its arc")
    title = plan.get("title")
    if not isinstance(title, str) or not 1 <= len(title) <= 100 or any(c in title for c in "<>"):
        bad.append("publication title must be 1-100 characters, without angle brackets")
    tags = plan.get("tags") or ["Bible story", "KJV Bible", "HeroVerse", plan.get("arc", "")]
    import preflight
    if not isinstance(tags, list) or any(not isinstance(tag, str) or len(tag) > 100 or any(c in tag for c in "<>,")
                                         for tag in tags):
        bad.append("invalid publication tags")
    elif preflight.tag_chars(tags) > 500:
        bad.append("tags exceed YouTube's character limit")
    try:
        comment_for_plan(plan)
    except (SystemExit, KeyError, TypeError) as exc:
        bad.append("invalid publication first comment: " + str(exc)[:150])
    version = lpc.criteria_version(plan)
    criteria = lpc.criteria_files().get(version)
    if criteria is None or lpc.frozen_qa_problem(plan=plan):
        bad.append("unknown or changed frozen story criteria")
    table = load(root / "migration/production/bible/arcs.json")
    matches = [a for a in table.get("arcs", []) if a.get("id") == plan.get("arc")]
    arc = matches[0] if len(matches) == 1 else {}
    long = arc.get("long") or {}
    mapped = [a for a in table.get("arcs", []) if (a.get("long") or {}).get("pilot") == pilot]
    if not arc or long.get("pilot") != pilot or len(mapped) != 1:
        bad.append("arc calendar must map this long to exactly this pilot")
    at = long.get("slot")
    try:
        when = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if when.tzinfo is None:
            raise ValueError("timezone required")
    except (AttributeError, TypeError, ValueError):
        bad.append("arc publication slot is missing or lacks timezone")
    if check_thumbnail and isinstance(episode, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", episode):
        bad += thumbs.publish_problems(episode, "long", thumbs.image_path(episode,
                      root / "migration/production/bible/thumbs"), root / "migration/production/bible/thumbs")
    refuse(bad)
    return plan, {"publish_at": at, "shorts_slots": []}, criteria[0]


def materialized_script(plan, manifest, source_plan):
    """Use precisely the sequence the voice renderer uses; never estimated narration or a prior pilot."""
    items, carried = pc.sequence(plan)
    owners = {k: [plan["shots"][i] for i, indices in enumerate(carried) if k in indices]
              for k in range(len(items))}
    segments = []
    for k, item in enumerate(items):
        shots = owners[k]
        segments.append({"id": f"n{k:02d}", "text": item["text"], "kind": item.get("kind"),
                         **({"reference": item["reference"]} if item.get("reference") else {}),
                         **({"speaker": item["speaker"]} if item.get("speaker") else {}),
                         "keeper": any(s["kind"] == "keeper" for s in shots),
                         "conflict": any(s.get("conflict") is True for s in shots),
                         "climax": any(s.get("climax") is True for s in shots),
                         "rehook": item.get("rehook") is True or any(s.get("rehook") is True for s in shots),
                         "shots": [s["id"] for s in shots]})
    return {"version": "bible-long-publication-script-v1", "pilot_id": plan["pilot"],
            "archetype": "bible-story-long", "series": "bible", "episode": plan["episode"],
            "arc": plan["arc"], "working_title": plan["title"], "passage": plan["passage"],
            "criteria_version": manifest["criteria_version"], "burned_captions": plan.get("burned_captions"),
            "source_plan": source_plan, "chapters": plan["chapters"], "segments": segments,
            "backgrounds": sorted({c["source_sha256"] for c in manifest["clips"] if c.get("source_sha256")})}


def source_problems(plan, manifest, report, timeline, built, script):
    """All witnesses name the same bytes; the script and real retimed sentences contain exactly the same words."""
    built = Path(built)
    bad = []
    video = built / f"{plan['episode']}.mp4"
    digest = sha256(video)
    if any(s != digest for s in (manifest.get("output_sha256"), (report.get("composed") or {}).get("output_sha256"),
                                timeline.get("output_sha256"))):
        bad.append("master/report/manifest/timeline hash mismatch")
    if manifest.get("pilot_id") != plan["pilot"] or manifest.get("long") != plan["episode"] or \
            manifest.get("criteria_version") != lpc.criteria_version(plan):
        bad.append("manifest identity or criteria differs from the plan")
    record = manifest.get("timeline") or {}
    if record.get("file") != "timeline.json" or record.get("sha256") != sha256(built / "timeline.json"):
        bad.append("timeline record does not match the exported timeline")
    if timeline.get("sentences") != manifest.get("sentences"):
        bad.append("manifest and timeline disagree on real speech timing")
    cuts = timeline.get("cuts") or []
    report_cuts = (report.get("composed") or {}).get("timeline") or []
    if len(cuts) != len(report_cuts) or any({k: cut.get(k) for k in rec} != rec
                                         for cut, rec in zip(cuts, report_cuts)):
        bad.append("timeline and compose report disagree on cuts")
    total = manifest.get("output_seconds")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or not math.isfinite(total) or total <= 0:
        bad.append("invalid measured duration")
        return bad
    if timeline.get("output_seconds") != total or timeline.get("pilot_id") != plan["pilot"] or \
            timeline.get("long") != plan["episode"]:
        bad.append("timeline duration differs from master manifest")
    sentences = timeline.get("sentences") or []
    grouped, order, previous = {}, [], -1.0
    for sent in sentences:
        start, end = sent.get("start"), sent.get("end")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end)):
            bad.append("non-finite speech time")
            continue
        if start < previous - 0.001 or not 0 <= start < end <= total:
            bad.append("speech timeline is unordered or outside the master")
        previous = end
        sid = sent.get("segment")
        if not isinstance(sid, str):
            bad.append("sentence has no segment id")
            continue
        if sid not in grouped:
            order.append(sid)
        grouped.setdefault(sid, []).append(sent.get("text", ""))
    if order != [s["id"] for s in script["segments"]]:
        bad.append("spoken segment order differs from the plan")
    for seg in script["segments"]:
        if " ".join(" ".join(grouped.get(seg["id"], [])).split()) != " ".join(seg["text"].split()):
            bad.append("spoken text differs from the plan: " + seg["id"])
    bad += captions.manifest_problems(manifest, built)
    return bad


def chapter_rows(plan, manifest):
    holds = manifest.get("holds") or []
    rows = [(0, "The conflict")]
    for chapter in plan["chapters"]:
        spans = [h for h in holds if h.get("chapter") == chapter["id"]]
        if not spans:
            refuse(["no measured picture for chapter " + chapter["id"]])
        rows.append((int(min(h["start"] for h in spans)), chapter["title"]))
    if len(rows) < 3 or any(b[0] - a[0] < 10 for a, b in zip(rows, rows[1:])) or \
            manifest["output_seconds"] - rows[-1][0] < 10:
        refuse(["measured chapters must start at zero and each last at least ten seconds"])
    return [f"{at // 60}:{at % 60:02d} {title}" for at, title in rows]


def package_for(plan, script, manifest):
    """Story packaging, with actual source attributions and synthetic disclosure; no prayer defaults."""
    credits = list(dict.fromkeys(c["credit"] for c in manifest["clips"] if c.get("credit")))
    ai = any(c.get("source") in ("pavo", "still") for c in manifest["clips"]) or bool(manifest.get("images"))
    real = any(c.get("source") == "footage" for c in manifest["clips"])
    visual_kinds = (["AI-generated or animated illustrations"] if ai else []) + (["licensed footage"] if real else [])
    visuals = "Visuals: " + " and ".join(visual_kinds or ["the sources credited below"]) + "."
    description = "\n".join([plan["title"].split(" | ", 1)[0],
        "An original HeroVerse telling of " + plan["passage"] + ".", "",
        "Subscribe for the complete Bible-story series.", "", "Chapters", *chapter_rows(plan, manifest), "",
        "Scripture quotations: King James Version (public domain).",
        "Original narration and owned music by HeroVerse. Narration voices are AI-generated.",
        visuals,
        "This is an artistic Bible-story reconstruction, not footage of historical events.", "", "Visual credits:",
        *["- " + c for c in credits]])
    tags = plan.get("tags") or ["Bible story", "KJV Bible", "HeroVerse", plan["arc"]]
    import preflight
    first_comment = comment_for_plan(plan)
    refuse((["description exceeds YouTube's byte limit"] if len(description.encode()) > 5000 else []) +
           (["tags exceed YouTube's character limit"] if preflight.tag_chars(tags) > 500 else []))
    return {"version": "pilot-package-v1", "pilot_id": plan["pilot"], "series": "bible", "episode": plan["episode"],
            "title": plan["title"], "title_length": len(plan["title"]), "description": description, "tags": tags,
            "thumb_episode": plan["episode"],
            "category_id": "29", "playlist": plan.get("playlist"), "default_language": "en", "made_for_kids": False,
            "privacy_on_upload": "private", "thumbnail": "thumbnail.jpg", "ai_generated_visuals": ai,
            "altered_or_synthetic_disclosure": "Bible-story reconstruction with synthetic narration; synthetic disclosure on.",
            "first_comment": first_comment, "output_sha256": manifest["output_sha256"],
            "upload_performed": False, "publication_performed": False}


def comment_for_plan(plan):
    """The same cheap comment check runs before render and while materializing its publication package."""
    sys.path.insert(0, str(HERE.parent))
    import package_pilot
    items, _ = pc.sequence(plan)
    cta = " ".join(s["text"] for s in items if s.get("kind") == "cta")
    question = next((x.strip() for x in re.split(r"(?<=[.!?])\s+", cta) if x.strip().endswith("?")), None)
    return package_pilot.check_first_comment(plan.get("first_comment") or question or
                                           "What moment in this story stayed with you?")


def materialize(plan_path, built, root=ROOT):
    root, built, plan_path = Path(root), Path(built), Path(plan_path)
    plan, schedule, _ = input_documents(plan_path, root)
    source = {"file": str(plan_path.resolve().relative_to(root.resolve())), "sha256": sha256(plan_path)}
    manifest, report, timeline = [load(built / f"{name}.json") for name in ("manifest", "report", "timeline")]
    script = materialized_script(plan, manifest, source)
    refuse(source_problems(plan, manifest, report, timeline, built, script))
    package = package_for(plan, script, manifest)
    d = root / "migration/production" / plan["pilot"]
    # Never let a new master inherit a previous master's approval or review. A same-hash rerun may keep its review.
    old = d / "out/manifest.json"
    if old.exists() and load(old).get("output_sha256") != manifest["output_sha256"]:
        refuse(["pilot already contains a different master; archive it explicitly before replacement"])
    if old.exists():
        for name, desired in (("script.json", script), ("schedule.json", schedule), ("out/package.json", package)):
            if (d / name).exists() and load(d / name) != desired:
                refuse(["existing pilot publication inputs changed; review them explicitly before replacement"])
        for name in ("manifest.json", "timeline.json", "captions.srt"):
            if not (d / "out" / name).is_file() or sha256(d / "out" / name) != sha256(built / name):
                refuse(["existing pilot has different render witnesses; reconcile them explicitly before replacement"])
        thumbnail = d / "inspection/thumbnail.jpg"
        source_thumbnail = thumbs.image_path(plan["episode"], root / "migration/production/bible/thumbs")
        if thumbnail.exists() and sha256(thumbnail) != sha256(source_thumbnail):
            refuse(["existing pilot thumbnail changed; review it explicitly before replacement"])
    (d / "out").mkdir(parents=True, exist_ok=True)
    (d / "inspection").mkdir(parents=True, exist_ok=True)
    save(d / "script.json", script)
    save(d / "schedule.json", schedule)
    save(d / "out/package.json", package)
    for name in ("manifest.json", "timeline.json", "captions.srt"):
        shutil.copyfile(built / name, d / "out" / name)
    shutil.copyfile(thumbs.image_path(plan["episode"], root / "migration/production/bible/thumbs"),
                    d / "inspection/thumbnail.jpg")
    binding = {"version": "long-publication-handoff-v1", "pilot_id": plan["pilot"], "episode": plan["episode"],
               "output_sha256": manifest["output_sha256"], "source_plan": source,
               "release_asset": f"{plan['pilot']}-sha256-{manifest['output_sha256']}.mp4",
               "files": {name: sha256(d / name) for name in ("script.json", "schedule.json", "out/manifest.json",
                   "out/timeline.json", "out/captions.srt", "out/package.json", "inspection/thumbnail.jpg")},
               "review_status": "AWAITING_REVIEW", "approval_created": False}
    save(d / "out/handoff.json", binding)
    return d


def verify(pilot_dir, video=None, root=ROOT):
    d, root = Path(pilot_dir), Path(root)
    binding = load(d / "out/handoff.json")
    import episode_build
    manifest = load(d / "out/manifest.json")
    refuse(episode_build.revocation_problems(binding.get("episode"),
           shots_dir=root / "migration/production/bible/shots",
           source_hashes=[c["source_sha256"] for c in manifest.get("clips", []) if c.get("source_sha256")]))
    bad = []
    required = {"script.json", "schedule.json", "out/manifest.json", "out/timeline.json", "out/captions.srt",
                "out/package.json", "inspection/thumbnail.jpg"}
    if binding.get("version") != "long-publication-handoff-v1" or binding.get("pilot_id") != d.name or \
            not isinstance(binding.get("files"), dict) or set(binding["files"]) != required:
        refuse(["incomplete or mismatched publication handoff"])
    for name, digest in binding["files"].items():
        if name not in ("script.json", "schedule.json", "out/manifest.json", "out/timeline.json", "out/captions.srt",
                         "out/package.json", "inspection/thumbnail.jpg") or not (d / name).is_file() or sha256(d / name) != digest:
            bad.append("changed handoff file: " + name)
    plan_file = root / binding["source_plan"]["file"]
    if root.resolve() not in plan_file.resolve().parents or not plan_file.is_file() or \
            sha256(plan_file) != binding["source_plan"]["sha256"]:
        bad.append("source plan changed")
    if video is not None and sha256(video) != binding["output_sha256"]:
        bad.append("video differs from handoff")
    if binding.get("output_sha256") != load(d / "out/manifest.json").get("output_sha256"):
        bad.append("manifest differs from handoff")
    qa_path = d / "out/qa.json"
    if qa_path.exists():
        qa = load(qa_path)
        if qa.get("output_sha256") != binding["output_sha256"]:
            bad.append("QA differs from handoff")
        version = qa.get("criteria_version")
        if qa.get("criteria_sha256") != gate.FROZEN_CRITERIA_SHA256.get(version) or version != load(
                d / "out/manifest.json").get("criteria_version"):
            bad.append("QA criteria differs from handoff")
    refuse(bad)
    return binding


def main(argv):
    if len(argv) == 3 and argv[1] == "inputs":
        plan, _, criteria = input_documents(argv[2])
        print(json.dumps({"pilot": plan["pilot"], "criteria": str(criteria)}))
    elif len(argv) == 4 and argv[1] == "materialize":
        print(materialize(argv[2], argv[3]))
    elif len(argv) in (3, 4) and argv[1] == "verify":
        print(json.dumps(verify(*argv[2:])))
    elif len(argv) == 4 and argv[1] == "capacity":
        print(json.dumps(release_capacity(argv[2], bool(argv[3]))))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
