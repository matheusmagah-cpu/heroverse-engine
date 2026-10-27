#!/usr/bin/env python3
"""Scene stills, "image first" (owner, 27/10): Claude reviews cheap stills of a whole episode before any video.

A scene shot may declare `first_frame` (and `last_frame`): the id of a scene still. Pavo then animates that still
(frames_to_video) and the shot's prompt says only the motion and the camera. The registry follows the character
images' pattern:

  bible/stills/<still-id>.json        the still: episode, shot, `prompt` (the static composition, under the scene
                                      rules: period, writing, ark), status DRAFT or APPROVED; once approved also
                                      repo_path (bible/stills/<still-id>.jpg), sha256, size, candidate, approved
                                      {date, score, note, prompt_sha256}
  bible/stills/candidates/<cid>.jpg   candidates made by scene-stills.yml (FLUX on the Workers AI free allocation,
  bible/stills/candidates/<cid>.json  centre crop to the plan's aspect, Real-ESRGAN, 1080x1920 JPEG at 9:16 or
                                      1920x1080 at 16:9 for the long), cid = <still-id>-<run>-<n>,
                                      each with its sha256 and the prompt it was made from; status DRAFT
  bible/stills/sheets/<episode>-<run>.jpg   the contact sheet Claude reviews

Hashes are never written by hand: scene-stills.yml records candidates, `approve` records the approved still.
plan_check.frame_problems refuses a frame whose still is missing, not APPROVED, changed or against the scene rules.
E122: a still whose prompt names a prop (the ark, its setting sentence too) is made with every approved reference image
of that prop (props.json; plan_check.prop_references gives them as repository paths Pavo takes, with their sha256): the
candidate's sidecar lists `references` [{record, sha256}] and `pavo` {generate: the pavo_generate_image answer
(model, conversation_id, input_images), job: the pavo_image_job read-back (conversation_id, status)}, input_images
equal to the references required; finalize and approve refuse it otherwise, and so does plan_check.frame_problems
(STILL_PROP_UNREFERENCED), also while the prop is still DRAFT. The approval binds the references by digest
(approved.references_sha256): references added by hand later are STILL_PROMPT_CHANGED. prepare refuses a still that
names a prop on the FLUX engine before any image.

usage:
  scene_stills.py prepare PLAN SHOTS CANDIDATES RUN OUT_JSON [--engine flux|pavo]   the shots' stills (1-3 each):
                                                                cf_images.py's input (flux), or the Pavo requests
                                                                with each still's `references` (pavo; E122)
  scene_stills.py crop IMG_DIR                                  centre crop each FLUX PNG to its plan's aspect
  scene_stills.py finalize IMG_DIR RUN                          candidates (JPEG 1080x1920 + record) into stills/candidates
                                                                (FLUX PNGs, or Pavo Agnes Image JPEGs with `source`)
  scene_stills.py sheet RUN OUT_JPG                             contact sheet of that run's candidates
  scene_stills.py approve STILL_ID CANDIDATE_ID --score S --note TEXT   after Claude's review (>= 9.5), by PR
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan_check  # noqa: E402

REPO = plan_check.ROOT
STILLS = plan_check.STILLS_DIR
# a still at its plan's aspect (Pavo: side 256-5760, aspect 0.4-2.5): the Short's 9:16 frame, the long's 16:9
# (LONG_DESIGN slice 3: its 9 image-first shots; 1920x1080, above Pavo's 1280x720 video frame). Any other aspect is
# refused (STILL_ASPECT_UNSUPPORTED), and a candidate whose picture is not at its plan's aspect is refused, never
# stretched (STILL_ASPECT_MISMATCH, the same code plan_check raises on an approved still)
SIDES = {"9:16": (1080, 1920), "16:9": (1920, 1080)}
SIDE = SIDES["9:16"]
ASPECT_TOL = 0.01                # plan_check.frame_problems' tolerance
FLOOR = 9.5
MAX_CANDIDATES = 3
# cf_images.py appends ", " + style to each prompt: FLUX schnell on Workers AI is square, so the subject is kept in
# the central third (a 9:16 column) or band (a 16:9 band) and the square is cropped to the plan's aspect
STYLES = {"9:16": "tall vertical composition, the whole subject inside the central third of the frame",
          "16:9": "wide horizontal composition, the whole subject inside the central band of the frame"}
STYLE = STYLES["9:16"]
RUN = re.compile(r"^[0-9]{1,20}$")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def rel(path):
    return str(Path(path).resolve().relative_to(REPO.resolve()))


def aspect_of(plan):
    """The still aspect of a plan (its `aspect_ratio`, 9:16 when it names none): STILL_ASPECT_UNSUPPORTED otherwise."""
    aspect = (plan or {}).get("aspect_ratio", "9:16")
    if aspect not in SIDES:
        raise SystemExit(f"STILL_ASPECT_UNSUPPORTED {aspect} ({' or '.join(SIDES)})")
    return aspect


def still_aspect(still, stills_dir=None):
    """The aspect a still is made at: its record's episode plan's (plans/<episode>.json)."""
    rec = plan_check.still_record(still, stills_dir) or {}
    path = HERE / "plans" / f"{rec.get('episode')}.json"
    return aspect_of(json.loads(path.read_text()) if path.is_file() else {})


def at_aspect(size, aspect):
    w, h = (int(x) for x in aspect.split(":"))
    return bool(size) and abs(size[0] / size[1] - w / h) <= ASPECT_TOL


def plan_stills(plan, ids):
    """[(shot id, still id)] for the named shots' frames, in plan order; refused by name before any image."""
    shots = {s.get("id"): s for s in plan.get("shots") or []}
    out = []
    for sid in ids:
        shot = shots.get(sid)
        if shot is None:
            raise SystemExit(f"STILL_SHOT_UNKNOWN {sid} (not a shot of {plan.get('episode')})")
        frames = [shot[f] for f in plan_check.FRAME_FIELDS if shot.get(f)]
        if not frames:
            raise SystemExit(f"STILL_SHOT_WITHOUT_FRAME {sid} (give the shot `first_frame` first)")
        out += [(sid, still) for still in frames]
    return out


ENGINES = ("flux", "pavo")       # cf_images.py (FLUX, text only) or Pavo agnes-image (reference images)


def prepare(plan, ids, candidates, run, stills_dir=None, engine="flux"):
    """cf_images.py's input: CANDIDATES images of each named shot's stills, refused unless each still's record holds
    a prompt that passes the scene rules (STILL_PROMPT_REFUSED) and its shot may carry frames at all."""
    if not 1 <= candidates <= MAX_CANDIDATES:
        raise SystemExit(f"STILL_CANDIDATES_INVALID {candidates} (1-{MAX_CANDIDATES} a still)")
    if not RUN.fullmatch(str(run)):
        raise SystemExit(f"STILL_RUN_INVALID {run}")
    if engine not in ENGINES:
        raise SystemExit(f"STILL_ENGINE_INVALID {engine} ({' or '.join(ENGINES)})")
    aspect = aspect_of(plan)
    images = []
    shots = {s.get("id"): (i, s) for i, s in enumerate(plan.get("shots") or [])}
    for sid, still in plan_stills(plan, ids):
        i, shot = shots[sid]
        shape = [p for p in plan_check.frame_problems(i, shot, plan, stills_dir)
                 if p.split()[0] in ("FRAMES_NOT_SCENE", "FRAME_FIELD_INVALID", "FRAME_LAST_WITHOUT_FIRST",
                                     "FRAMES_WITH_REFERENCES", "FRAMES_WITH_AUDIO", "STILL_MISSING")]
        if shape:
            raise SystemExit("STILL_SHOT_REFUSED " + "; ".join(shape))
        rec = plan_check.still_record(still, stills_dir)
        if rec.get("episode") != plan.get("episode") or rec.get("shot") != sid:
            raise SystemExit(f"STILL_RECORD_MISMATCH {still} (its record names {rec.get('episode')} "
                             f"{rec.get('shot')}, not {plan.get('episode')} {sid})")
        bad = plan_check.still_prompt_problems(f"{sid}/{still}", rec.get("prompt") or "", plan)
        if bad:
            raise SystemExit(f"STILL_PROMPT_REFUSED {still}: " + "; ".join(bad))
        refs, missing = plan_check.prop_references(rec["prompt"], plan=plan)
        if (refs or missing) and engine == "flux":   # E122: refused before any image, not in finalize
            raise SystemExit(f"STILL_PROP_UNREFERENCED {still}: names a prop and FLUX (cf_images.py) cannot send its "
                             "reference images; prepare with --engine pavo (E122)")
        if missing:
            raise SystemExit(f"STILL_PROP_UNREFERENCED {still}: " + "; ".join(missing) + " (E122)")
        images += [{"id": f"{still}-{run}-{n}", "still": still, "prompt": rec["prompt"], "seed": None,
                    "references": [r["repo_path"] for r in refs], "reference_records": refs}
                   for n in range(1, candidates + 1)]
    # aspect_ratio: what a Pavo agnes-image request asks for (16:9 quoted 0 credits, evidence/pavo/20261027)
    return {"version": "scene-stills-v1", "episode": plan.get("episode"), "engine": engine, "style": STYLES[aspect],
            "aspect_ratio": aspect, "side": list(SIDES[aspect]), "negative": None,
            "width": 1024, "height": 1024, "images": images}


def crop(img_dir, stills_dir=None):
    """Each FLUX PNG (1024 square) cut to its plan's aspect, in place: the centre 9:16 column of a Short's still, the
    centre 16:9 band of a long's (still_aspect: the candidate's still's episode plan). A native source's JPEG (Pavo
    agnes-image, made at the plan's ratio: 1472x2624 at 9:16) is never cut: at another aspect it is refused
    (STILL_ASPECT_MISMATCH), so a wrong-ratio request is generated again, not cropped into another picture."""
    from PIL import Image
    for png in sorted(p for p in Path(img_dir).iterdir() if p.suffix in (".png", ".jpg")):
        parts = split_candidate(png.stem)
        aspect = still_aspect(parts[0], stills_dir) if parts else "9:16"
        side = SIDES[aspect]
        im = Image.open(png).convert("RGB")
        w, h = im.size
        if png.suffix == ".jpg":
            if not at_aspect(im.size, aspect):
                raise SystemExit(f"STILL_ASPECT_MISMATCH {png.stem} ({[w, h]} is not {aspect}: a native source is "
                                 "made at the plan's ratio, never cropped)")
            continue
        if side[0] < side[1]:   # 9:16: the centre column, as before
            cw = round(h * side[0] / side[1])
            if cw < w:
                left = (w - cw) // 2
                im.crop((left, 0, left + cw, h)).save(png)
        else:                   # 16:9: the centre band
            chh = round(w * side[1] / side[0])
            if chh < h:
                top = (h - chh) // 2
                im.crop((0, top, w, top + chh)).save(png)


def split_candidate(cid):
    """<still-id>-<run>-<n> -> (still id, run, n), or None."""
    m = re.fullmatch(r"([a-z0-9]+(?:-[a-z0-9]+)*)-([0-9]{1,20})-([1-9])", cid or "")
    return (m.group(1), m.group(2), int(m.group(3))) if m else None


def finalize(img_dir, run, stills_dir=None):
    """Candidates into stills/candidates: a JPEG at the plan's side (1080x1920 for 9:16, 1920x1080 for 16:9), its
    sha256, the still's prompt, status DRAFT. A picture at another aspect is refused (STILL_ASPECT_MISMATCH), never
    stretched."""
    from PIL import Image
    stills_dir = Path(stills_dir or STILLS)
    out = []
    # FLUX PNGs from scene-stills.yml, or a native 9:16 source's JPEG/PNG whose sidecar names its `source` and
    # `upscaler` (pavo-agnes-image-2.5-flash: 1472x2624 JPEG, Lanczos to 1080x1920)
    for png in sorted(p for p in Path(img_dir).iterdir() if p.suffix in (".png", ".jpg")):
        parts = split_candidate(png.stem)
        if not parts or parts[1] != str(run):
            raise SystemExit(f"STILL_CANDIDATE_NAME_REFUSED {png.name}")
        still = parts[0]
        rec = plan_check.still_record(still, stills_dir)
        if rec is None:
            raise SystemExit(f"STILL_MISSING {still}")
        aspect = still_aspect(still, stills_dir)
        side = SIDES[aspect]
        im = Image.open(png).convert("RGB")
        if not at_aspect(im.size, aspect):
            raise SystemExit(f"STILL_ASPECT_MISMATCH {png.stem} ({list(im.size)} is not {aspect}: crop it first)")
        dst = stills_dir / "candidates" / f"{png.stem}.jpg"
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.resize(side, Image.LANCZOS).save(dst, "JPEG", quality=92)
        made = png.with_suffix(".json")
        meta = json.loads(made.read_text()) if made.is_file() else {}
        plan_path = HERE / "plans" / f"{rec.get('episode')}.json"   # E123: the plan decides what names the ark
        plan = json.loads(plan_path.read_text()) if plan_path.is_file() else None
        unref = plan_check.prop_reference_problems(rec["prompt"], meta.get("references"), pavo=meta.get("pavo"),
                                                   plan=plan)
        if unref:   # E122: text alone does not hold a prop's look; a FLUX or text-only image of the ark is refused
            raise SystemExit(f"STILL_PROP_UNREFERENCED {png.stem}: " + "; ".join(unref) + " (E122)")
        save(dst.with_suffix(".json"), {
            "id": png.stem, "still": still, "episode": rec.get("episode"), "shot": rec.get("shot"), "run": str(run),
            "status": "DRAFT", "prompt": rec["prompt"], "sent_prompt": meta.get("prompt"),
            "engine": meta.get("engine"), "models": meta.get("models"), "generated_by": meta.get("generated_by"),
            "source": meta.get("source", "cf-flux"), "conversation_id": meta.get("conversation_id"),
            "quote": meta.get("quote"), "references": meta.get("references") or [], "pavo": meta.get("pavo"),
            "upscaler": meta.get("upscaler", "Real-ESRGAN general x4v3 (bsd-3-clause), then Lanczos to "
                                             f"{side[0]}x{side[1]}"),
            "aspect_ratio": aspect, "size": list(side), "repo_path": rel(dst), "sha256": sha256(dst)})
        out.append(png.stem)
    return out


def sheet(run, out_jpg, stills_dir=None):
    """The run's candidates side by side, each labelled with its candidate id: 3 a row at 360x640 (9:16), 2 a row at
    640x360 (16:9, the long's)."""
    from PIL import Image, ImageDraw
    stills_dir = Path(stills_dir or STILLS)
    files = sorted(p for p in (stills_dir / "candidates").glob("*.jpg")
                   if (split_candidate(p.stem) or (None, None))[1] == str(run))
    if not files:
        raise SystemExit(f"STILL_SHEET_EMPTY run {run}")
    with Image.open(files[0]) as first:
        wide = first.size[0] > first.size[1]
    cols, tw, th, band = (2, 640, 360, 28) if wide else (3, 360, 640, 28)
    rows = (len(files) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * tw, rows * (th + band)), (20, 20, 20))
    draw = ImageDraw.Draw(canvas)
    for k, path in enumerate(files):
        x, y = (k % cols) * tw, (k // cols) * (th + band)
        canvas.paste(Image.open(path).convert("RGB").resize((tw, th)), (x, y))
        draw.text((x + 6, y + th + 8), path.stem, fill=(235, 235, 235))
    Path(out_jpg).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_jpg, "JPEG", quality=88)
    return [p.stem for p in files]


def approve(still, candidate, score, note, stills_dir=None, today=None):
    """Claude's review approved CANDIDATE as STILL (overall >= 9.5): its image becomes bible/stills/<still>.jpg and
    the record APPROVED with the sha256 computed here. Refused when the candidate's image is not the one recorded, was
    made from another prompt, belongs to another still, or its prompt fails the scene rules."""
    stills_dir = Path(stills_dir or STILLS)
    rec = plan_check.still_record(still, stills_dir)
    if rec is None:
        raise SystemExit(f"STILL_MISSING {still}")
    if not isinstance(score, (int, float)) or score < FLOOR or score > 10:
        raise SystemExit(f"STILL_SCORE_BELOW_FLOOR {score} (overall >= {FLOOR})")
    if not isinstance(note, str) or not note.strip():
        raise SystemExit("STILL_NOTE_MISSING (what the review saw)")
    parts = split_candidate(candidate)
    src = stills_dir / "candidates" / f"{candidate}.jpg"
    meta_path = src.with_suffix(".json")
    if not parts or parts[0] != still or not src.is_file() or not meta_path.is_file():
        raise SystemExit(f"STILL_CANDIDATE_UNKNOWN {candidate} (a candidate of {still} in stills/candidates)")
    meta = json.loads(meta_path.read_text())
    if sha256(src) != meta.get("sha256"):
        raise SystemExit(f"STILL_CANDIDATE_SHA256_MISMATCH {candidate}")
    from PIL import Image
    with Image.open(src) as im:
        size = im.size
    aspect = still_aspect(still, stills_dir)
    if not at_aspect(size, aspect):
        raise SystemExit(f"STILL_ASPECT_MISMATCH {candidate} ({list(size)} is not {aspect})")
    if meta.get("prompt") != rec.get("prompt"):
        raise SystemExit(f"STILL_PROMPT_CHANGED {candidate} (made from another prompt than {still}'s; generate again)")
    plan_path = HERE / "plans" / f"{rec.get('episode')}.json"
    plan = json.loads(plan_path.read_text()) if plan_path.is_file() else {}
    bad = plan_check.still_prompt_problems(f"{rec.get('shot')}/{still}", rec["prompt"], plan)
    if bad:
        raise SystemExit(f"STILL_PROMPT_REFUSED {still}: " + "; ".join(bad))
    unref = plan_check.prop_reference_problems(rec["prompt"], meta.get("references"), pavo=meta.get("pavo"),
                                               plan=plan or None)
    if unref:
        raise SystemExit(f"STILL_PROP_UNREFERENCED {candidate}: " + "; ".join(unref) + " (E122)")
    dst = stills_dir / f"{still}.jpg"
    shutil.copyfile(src, dst)
    rec.update({"status": "APPROVED", "repo_path": rel(dst), "sha256": sha256(dst), "size": meta.get("size"),
                "candidate": candidate, "engine": meta.get("engine"), "references": meta.get("references") or [],
                "pavo": meta.get("pavo"),
                "approved": {"date": today or datetime.now(timezone.utc).strftime("%Y-%m-%d"), "score": score,
                             "note": note.strip(), "by": "Claude's still review (ops/CLAUDE_REVIEW.md)",
                             "prompt_sha256": hashlib.sha256(rec["prompt"].encode()).hexdigest(),
                             "references_sha256": plan_check.reference_digest(meta.get("references") or [])}})
    save(stills_dir / f"{still}.json", rec)
    return rec


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd, args = argv[1], argv[2:]
    if cmd == "prepare" and len(args) in (5, 7) and (len(args) == 5 or args[5] == "--engine"):
        plan = json.loads(Path(args[0]).read_text())
        ids = [x for x in args[1].split(",") if x]
        spec = prepare(plan, ids, int(args[2]), args[3], engine=args[6] if len(args) == 7 else "flux")
        save(args[4], spec)
        print(json.dumps({"episode": spec["episode"], "images": [x["id"] for x in spec["images"]]}))
    elif cmd == "crop" and len(args) == 1:
        crop(args[0])
    elif cmd == "finalize" and len(args) == 2:
        print(json.dumps({"candidates": finalize(args[0], args[1])}))
    elif cmd == "sheet" and len(args) == 2:
        print(json.dumps({"sheet": args[1], "candidates": sheet(args[0], args[1])}))
    elif cmd == "approve" and len(args) == 6 and args[2] == "--score" and args[4] == "--note":
        rec = approve(args[0], args[1], float(args[3]), args[5])
        print(json.dumps({"still": rec["id"], "status": rec["status"], "sha256": rec["sha256"]}))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
