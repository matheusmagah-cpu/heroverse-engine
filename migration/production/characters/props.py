#!/usr/bin/env python3
"""Props with approved reference images, like a character's (E122).

The ark of genesis-09's 64 Pavo stills carried plan_check's ARK_LOOK and ARK_EXCLUDE word for word (E113), yet drew a
tower at one end, a gabled barn or a curved ship's bow from shot to shot: text alone does not hold a prop's look. A
character's face is held by its approved reference images (characters.json `refs`, images/ch-<id>-<view>.json, the
image passed to the model). A prop gets the same: props.json holds each prop's status and views; its candidates are
Pavo agnes-image stills of the prop alone in a neutral setting, whose prompt carries the prop's look and exclusion
sentences (plan_check.PROPS) word for word, each after a fresh exact 0-credit quote, or frames cut by `frame` from a
shot clip Claude already approved at >= 9.5 (its sha256 in bible/shots/<episode>.json; the text-to-image run
2026102701 kept drawing end blocks and ship bows); any other source is refused. Claude reviews the contact sheet
and `approve` copies a kept candidate to refs/pr-<prop>-<view>.jpg with its record images/pr-<prop>-<view>.json
(repo_path, sha256: never by hand). The prop is APPROVED when every view has its approved image.

plan_check.prop_references gives a still the prop's approved references (repository paths Pavo takes, with their
sha256); scene_stills.py prepare / finalize / approve and plan_check.frame_problems refuse a still whose prompt names
the prop unless it was made with exactly those (STILL_PROP_UNREFERENCED).

  props.json                                 status DRAFT|APPROVED, views, refs (the views approved), reviewed
  props/candidates/pr-<prop>-<view>-<run>-<n>.jpg|json   candidates (DRAFT): prompt, source, quote, sha256
  props/sheets/<prop>-<run>.jpg              the contact sheet Claude reviews
  refs/pr-<prop>-<view>.jpg, images/pr-<prop>-<view>.json   the approved reference (written by `approve`)

usage:
  props.py finalize PROP VIEW RUN N IMAGE META_JSON    one Pavo candidate (META_JSON: prompt, conversation_id, quote)
  props.py frame PROP VIEW RUN N CLIP EPISODE SHOT SECONDS [--crop X,Y,W,H]   one candidate cut from a clip Claude already approved at
                                                       >= 9.5 (bible/shots/<episode>.json: the clip's sha256 must be
                                                       the approved one; ffmpeg takes the frame here, never by hand)
  props.py sheet PROP RUN OUT_JPG                      that run's contact sheet
  props.py approve PROP VIEW CANDIDATE --score S --note TEXT   after Claude's review (>= 9.5), by PR
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PROPS_FILE = HERE / "props.json"
IMAGES_DIR = HERE / "images"
REFS_DIR = HERE / "refs"
CANDIDATES_DIR = HERE / "props" / "candidates"
SHOTS_DIR = REPO / "migration" / "production" / "bible" / "shots"
PAVO = "pavo-agnes-image-2.5-flash"
CLIP_FRAME = "approved-clip-frame"   # a frame of a shot clip Claude approved (E122: text-to-image did not hold it)
FLOOR = 9.5
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CID = re.compile(r"^pr-([a-z0-9]+)-([a-z0-9]+(?:-[a-z0-9]+)*)-([0-9]{1,20})-([1-9])$")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def rel(path):
    return str(Path(path).resolve().relative_to(REPO.resolve()))


def registry(path=None):
    return json.loads(Path(path or PROPS_FILE).read_text())["props"]


def record_path(prop, view, images_dir=None):
    return Path(images_dir or IMAGES_DIR) / f"pr-{prop}-{view}.json"


def approved_refs(prop, props=None, images_dir=None):
    """(the prop's approved references [{record, repo_path, sha256}], None) or ([], why not). Each image on disk is
    checked against its record's sha256: an image changed by hand is no reference."""
    props = registry() if props is None else props
    p = props.get(prop)
    if not p:
        return [], f"{prop} is not in props.json"
    if p.get("status") != "APPROVED":
        return [], f"the {prop}'s reference images are {p.get('status')}: Claude reviews its sheet, props.py approve"
    views = list(p.get("views") or [])
    if not views or sorted(p.get("refs") or []) != sorted(views):
        return [], f"the {prop} is APPROVED without an approved image for every view {views}"
    out = []
    for view in views:
        path = record_path(prop, view, images_dir)
        rec = json.loads(path.read_text()) if path.is_file() else {}
        src = (REPO / str(rec.get("repo_path") or "")).resolve()
        if not rec.get("repo_path") or REPO.resolve() not in src.parents or not src.is_file() \
                or sha256(src) != rec.get("sha256"):
            return [], f"pr-{prop}-{view}: its image is not the approved one (sha256)"
        out.append({"record": rec.get("id") or f"pr-{prop}-{view}", "repo_path": rec["repo_path"],
                    "sha256": rec["sha256"]})
    return out, None


def _look_problems(prop, prompt):
    sys.path.insert(0, str(REPO / "migration" / "production" / "bible"))
    import plan_check
    spec = plan_check.PROPS.get(prop)
    if spec is None:
        return [f"{prop} is not in plan_check.PROPS"]
    return [f"the prompt lacks, word for word: '{w}'" for w in (spec["look"], spec["exclude"])
            if w not in (prompt or "")]


def _zero_quote(quote):
    q = quote or {}
    return q.get("required_credits") == 0 and q.get("is_estimate") is False


def _approved_clip(episode, shot, clip_sha256, shots_dir=None):
    """The approval record of SHOT in bible/shots/<episode>.json when CLIP_SHA256 is its approved clip at >= 9.5,
    else None."""
    if not NAME.fullmatch(str(episode or "")):
        return None
    path = Path(shots_dir or SHOTS_DIR) / f"{episode}.json"
    rec = (json.loads(path.read_text()).get("shots") or {}).get(shot) if path.is_file() else None
    if not rec or rec.get("clip_sha256") != clip_sha256 or not isinstance(rec.get("score"), (int, float)) \
            or rec["score"] < FLOOR:
        return None
    return rec


def source_problems(prop, meta, shots_dir=None):
    """What keeps a candidate from being a reference: a Pavo still needs the prop's look word for word and an exact
    0-credit quote; a clip frame needs the clip Claude approved (sha256, >= 9.5). Any other source is refused."""
    src = meta.get("source")
    if src == PAVO:
        out = _look_problems(prop, meta.get("prompt"))
        if not _zero_quote(meta.get("quote")):
            out.append(f"quote {meta.get('quote')} is not an exact 0-credit quote")
        return out
    if src == CLIP_FRAME:
        c = meta.get("clip") or {}
        if not _approved_clip(c.get("episode"), c.get("shot"), c.get("clip_sha256"), shots_dir):
            return [f"the clip {c.get('episode')} {c.get('shot')} {c.get('clip_sha256')} is not an approved clip"]
        return []
    return [f"source {src!r} is neither {PAVO} nor {CLIP_FRAME}"]


def finalize_frame(prop, view, run, n, clip, episode, shot, seconds, crop=None, cand_dir=None, props=None,
                   shots_dir=None):
    """One candidate cut from an approved shot clip: the clip's sha256 must be the one Claude approved for SHOT in
    bible/shots/<episode>.json (>= 9.5); ffmpeg takes the frame at SECONDS (PNG -> JPEG), optionally cut to CROP
    (x, y, w, h in the frame's pixels: the ark without the crowd); status DRAFT."""
    import subprocess
    import tempfile
    props = registry() if props is None else props
    if prop not in props or view not in (props[prop].get("views") or []):
        raise SystemExit(f"PROP_VIEW_UNKNOWN {prop} {view}")
    if not re.fullmatch(r"[0-9]{1,20}", str(run)) or not 1 <= int(n) <= 9:
        raise SystemExit(f"PROP_CANDIDATE_NAME_REFUSED {run}-{n}")
    digest = sha256(clip)
    approval = _approved_clip(episode, shot, digest, shots_dir)
    if approval is None:
        raise SystemExit(f"PROP_SOURCE_REFUSED {episode} {shot} (clip {digest} is not its approved clip at >= {FLOOR})")
    seconds = float(seconds)
    if not 0 <= seconds <= float(approval.get("clip_seconds") or 60):
        raise SystemExit(f"PROP_FRAME_TIME_REFUSED {seconds}")
    cid = f"pr-{prop}-{view}-{run}-{n}"
    dst = Path(cand_dir or CANDIDATES_DIR) / f"{cid}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "f.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{seconds:.3f}", "-i", str(clip), "-frames:v", "1",
                        str(png)], check=True)
        with Image.open(png) as im:
            im = im.convert("RGB")
            if crop:
                x, y, w, h = (int(v) for v in crop)
                if x < 0 or y < 0 or w < 64 or h < 64 or x + w > im.size[0] or y + h > im.size[1]:
                    raise SystemExit(f"PROP_CROP_REFUSED {crop} (inside the {im.size} frame)")
                im = im.crop((x, y, x + w, y + h))
            size = list(im.size)
            im.save(dst, "JPEG", quality=95)
    rec = {"id": cid, "prop": prop, "view": view, "run": str(run), "status": "DRAFT", "source": CLIP_FRAME,
           "clip": {"episode": episode, "shot": shot, "asset": approval.get("asset"), "clip_sha256": digest,
                    "seconds": seconds, "crop": list(crop) if crop else None, "approved_score": approval.get("score"), "approval_note": approval.get("note")},
           "prompt": None, "quote": None, "references": [], "size": size, "repo_path": rel(dst), "sha256": sha256(dst),
           "generated_by": "HeroVerse pipeline (frame of an AI-generated clip)"}
    save(dst.with_suffix(".json"), rec)
    return rec


def finalize(prop, view, run, n, image, meta, cand_dir=None, props=None):
    """One candidate reference: the model's image as JPEG with its sha256, the prompt (the prop's look and exclusion
    word for word), source, job and its exact 0-credit quote; status DRAFT."""
    from PIL import Image
    props = registry() if props is None else props
    if prop not in props or view not in (props[prop].get("views") or []):
        raise SystemExit(f"PROP_VIEW_UNKNOWN {prop} {view}")
    if not re.fullmatch(r"[0-9]{1,20}", str(run)) or not 1 <= int(n) <= 9:
        raise SystemExit(f"PROP_CANDIDATE_NAME_REFUSED {run}-{n}")
    if meta.get("source", PAVO) != PAVO:
        raise SystemExit(f"PROP_SOURCE_REFUSED {prop} {view} ({meta.get('source')!r}: a Pavo still here, a clip frame "
                         "only through `frame`)")
    bad = _look_problems(prop, meta.get("prompt"))
    if bad:
        raise SystemExit(f"PROP_PROMPT_REFUSED {prop} {view}: " + "; ".join(bad))
    if not _zero_quote(meta.get("quote")):
        raise SystemExit(f"PROP_QUOTE_NOT_ZERO {prop} {view} ({meta.get('quote')}: an exact 0-credit quote only)")
    cid = f"pr-{prop}-{view}-{run}-{n}"
    dst = Path(cand_dir or CANDIDATES_DIR) / f"{cid}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image) as im:
        size = list(im.size)
        im.convert("RGB").save(dst, "JPEG", quality=92)
    rec = {"id": cid, "prop": prop, "view": view, "run": str(run), "status": "DRAFT", "prompt": meta["prompt"],
           "source": PAVO, "model": meta.get("model", "agnes-image"),
           "ratio": meta.get("ratio"), "resolution": meta.get("resolution"),
           "conversation_id": meta.get("conversation_id"), "quote": meta.get("quote"), "references": [],
           "size": size, "repo_path": rel(dst), "sha256": sha256(dst),
           "generated_by": "HeroVerse pipeline (AI-generated image)"}
    save(dst.with_suffix(".json"), rec)
    return rec


def sheet(prop, run, out_jpg, cand_dir=None):
    """The run's candidates of the prop (aspect kept: 2 landscape or 3 portrait a row), labelled with the id."""
    from PIL import Image, ImageDraw
    cand_dir = Path(cand_dir or CANDIDATES_DIR)
    files = sorted(p for p in cand_dir.glob(f"pr-{prop}-*-{run}-*.jpg") if CID.fullmatch(p.stem))
    if not files:
        raise SystemExit(f"PROP_SHEET_EMPTY {prop} run {run}")
    from PIL import ImageOps
    with Image.open(files[0]) as first:
        portrait = first.size[1] > first.size[0]
    cols, tw, th, band = (3, 360, 640, 28) if portrait else (2, 800, 450, 28)
    rows = (len(files) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * tw, rows * (th + band)), (20, 20, 20))
    draw = ImageDraw.Draw(canvas)
    for k, path in enumerate(files):
        x, y = (k % cols) * tw, (k // cols) * (th + band)
        with Image.open(path) as im:
            fit = ImageOps.contain(im.convert("RGB"), (tw, th))   # aspect kept: a reference is judged undistorted
            canvas.paste(fit, (x + (tw - fit.size[0]) // 2, y + (th - fit.size[1]) // 2))
        draw.text((x + 6, y + th + 8), path.stem, fill=(235, 235, 235))
    Path(out_jpg).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_jpg, "JPEG", quality=88)
    return [p.stem for p in files]


def approve(prop, view, candidate, score, note, cand_dir=None, props_file=None, images_dir=None, refs_dir=None,
            today=None, shots_dir=None):
    """Claude's review kept CANDIDATE as the prop's VIEW reference (overall >= 9.5): its image becomes
    refs/pr-<prop>-<view>.jpg, the record images/pr-<prop>-<view>.json holds the sha256 computed here, and the prop
    is APPROVED once every view has one."""
    props_file = Path(props_file or PROPS_FILE)
    data = json.loads(props_file.read_text())
    p = data["props"].get(prop)
    if p is None or view not in (p.get("views") or []):
        raise SystemExit(f"PROP_VIEW_UNKNOWN {prop} {view}")
    if not isinstance(score, (int, float)) or score < FLOOR or score > 10:
        raise SystemExit(f"PROP_SCORE_BELOW_FLOOR {score} (overall >= {FLOOR})")
    if not isinstance(note, str) or not note.strip():
        raise SystemExit("PROP_NOTE_MISSING (what the review saw)")
    m = CID.fullmatch(candidate or "")
    src = Path(cand_dir or CANDIDATES_DIR) / f"{candidate}.jpg"
    meta_path = src.with_suffix(".json")
    if not m or m.group(1) != prop or m.group(2) != view or not src.is_file() or not meta_path.is_file():
        raise SystemExit(f"PROP_CANDIDATE_UNKNOWN {candidate} (a {view} candidate of the {prop})")
    meta = json.loads(meta_path.read_text())
    if sha256(src) != meta.get("sha256"):
        raise SystemExit(f"PROP_CANDIDATE_SHA256_MISMATCH {candidate}")
    bad = source_problems(prop, meta, shots_dir)
    if bad:
        raise SystemExit(f"PROP_SOURCE_REFUSED {candidate}: " + "; ".join(bad))
    dst = Path(refs_dir or REFS_DIR) / f"pr-{prop}-{view}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    date = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rec = {"id": f"pr-{prop}-{view}", "prop": prop, "view": view, "repo_path": rel(dst), "sha256": sha256(dst),
           "size": meta.get("size"), "candidate": candidate, "prompt": meta.get("prompt"),
           "source": (f"{PAVO} conversation {meta.get('conversation_id')}, 0-credit quote" if meta.get("source") == PAVO
                      else f"{CLIP_FRAME} {json.dumps(meta.get('clip'), sort_keys=True)}"),
           "approved": {"date": date, "score": score, "note": note.strip(),
                        "by": "Claude's reference review (ops/CLAUDE_REVIEW.md)"}}
    save(record_path(prop, view, images_dir), rec)
    p["refs"] = [v for v in p["views"] if v in set(p.get("refs") or []) | {view}]
    if p["refs"] == list(p["views"]):
        p["status"] = "APPROVED"
    p["reviewed"] = f"{date}: {view} {candidate} kept ({score}): {note.strip()}" + (
        "" if p["status"] == "APPROVED" else f"; still DRAFT until {[v for v in p['views'] if v not in p['refs']]}")
    save(props_file, data)
    return rec


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd, args = argv[1], argv[2:]
    if cmd == "finalize" and len(args) == 6:
        rec = finalize(args[0], args[1], args[2], int(args[3]), args[4], json.loads(Path(args[5]).read_text()))
        print(json.dumps({"candidate": rec["id"], "sha256": rec["sha256"]}))
    elif cmd == "frame" and len(args) in (8, 10) and (len(args) == 8 or args[8] == "--crop"):
        crop = [int(v) for v in args[9].split(",")] if len(args) == 10 else None
        rec = finalize_frame(args[0], args[1], args[2], int(args[3]), args[4], args[5], args[6], args[7], crop)
        print(json.dumps({"candidate": rec["id"], "sha256": rec["sha256"], "clip": rec["clip"]["clip_sha256"]}))
    elif cmd == "sheet" and len(args) == 3:
        print(json.dumps({"sheet": args[2], "candidates": sheet(args[0], args[1], args[2])}))
    elif cmd == "approve" and len(args) == 7 and args[3] == "--score" and args[5] == "--note":
        rec = approve(args[0], args[1], args[2], float(args[4]), args[6])
        print(json.dumps({"reference": rec["id"], "sha256": rec["sha256"]}))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
