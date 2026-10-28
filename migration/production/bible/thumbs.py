#!/usr/bin/env python3
"""Episode thumbnails, character first (owner, 27/10; evidence/vidiq/20261027/thumb-host.json, PR #458).

The thumbnail shows the story's character (APPROVED in characters.json, made with its approved reference images, so
the same face every time), a close-up face with a clear emotion, and our own text of at most 4 words naming the story
or the character. The Keeper is not the face, except in an owner-approved A/B variant. It is a candidate reviewed
BEFORE publish, together with the episode's stills; the publish step uploads only the approved image (no rework).

  bible/thumbs/<episode>.json              the spec: episode, format (short 1080x1920 / long 1280x720), story,
                                           character, emotion, framing "close-up", scene, text, period, prompt;
                                           status DRAFT, or APPROVED with approved {sha256, spec_sha256, candidate,
                                           score, note, date} once `approve` ran (by PR)
  bible/thumbs/<episode>.jpg               the approved thumbnail (copied by `approve`, never by hand)
  bible/thumbs/candidates/<cid>.jpg|json   candidates, cid = <episode>-<run>-<n>: the image model's picture (Pavo
                                           agnes-image, after a fresh exact 0-credit quote) cropped to the format,
                                           with the text drawn by our own code; the record holds both sha256, the
                                           spec digest, the references sent, the R16 ruler (thumb_check.py)
  bible/thumbs/sheets/<episode>-<run>.jpg  the contact sheet Claude reviews

The prompt carries the character's look word for word and passes the scene rules (period, writing, ark) by
plan_check's own functions. publish_episode.problems (so `episode_build.py check-record`, before publish-episode.yml)
and the long's preflight refuse an episode whose thumbnail is not the approved one: THUMB_NOT_APPROVED.

usage:
  thumbs.py check SPEC                                     the spec's problems (exit 1 on any)
  thumbs.py refs SPEC SRC_DIR OUT_DIR                      the character's approved reference images (verified by
                                                           sha256 from SRC_DIR) as JPEGs the image model accepts
  thumbs.py finalize SPEC IMAGE RUN N META_JSON            one candidate (crop, text, record, R16)
  thumbs.py sheet EPISODE RUN OUT_JPG                      the run's contact sheet
  thumbs.py approve EPISODE CANDIDATE --score S --note T --reviewer MODEL
                                                        after the named session's review (>= 9.5), by PR
  thumbs.py verify EPISODE [THUMBNAIL]                     what publish refuses (exit 1 on any)
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
import reviewer_identity  # noqa: E402

REPO = HERE.parents[2]
THUMBS = HERE / "thumbs"
CHARACTERS = REPO / "migration" / "production" / "characters"
FLOOR = 9.5
MAX_WORDS = 4
FORMATS = {"short": (1080, 1920), "long": (1280, 720)}
RATIOS = {"short": "9:16", "long": "16:9"}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
KEEPER = "keeper"
FROM_PART = 9                    # Shorts from genesis-09 on; what is published stays as it is
DESIGN = ("episode", "format", "story", "character", "emotion", "framing", "scene", "text", "period", "prompt",
          "variant")              # the fields a review approves; approval fields are outside the digest
CID = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)-([0-9]{1,20})-([1-9])$")
WORD = re.compile(r"[A-Za-z0-9']+")
EPISODE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")   # a name, never a path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(spec):
    design = {k: spec.get(k) for k in DESIGN}
    return hashlib.sha256(json.dumps(design, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                          .encode()).hexdigest()


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def rel(path):
    return str(Path(path).resolve().relative_to(REPO.resolve()))


def spec_path(episode, thumbs_dir=None):
    if not isinstance(episode, str) or not EPISODE.fullmatch(episode):
        raise SystemExit(f"THUMB_EPISODE_INVALID {episode!r} (lower-case words joined by '-')")
    return Path(thumbs_dir or THUMBS) / f"{episode}.json"


def image_path(episode, thumbs_dir=None):
    """The approved image is always bible/thumbs/<episode>.jpg (never a path the spec names)."""
    return spec_path(episode, thumbs_dir).with_suffix(".jpg")


def load(episode, thumbs_dir=None):
    p = spec_path(episode, thumbs_dir)
    return json.loads(p.read_text()) if p.is_file() else None


def characters():
    return json.loads((CHARACTERS / "characters.json").read_text())["characters"]


def words(text):
    return WORD.findall(text or "")


def keeper_variant(spec):
    """An A/B variant with the Keeper's face, only when the spec names the owner's approval of it."""
    v = spec.get("variant")
    return isinstance(v, dict) and v.get("ab") is True and isinstance(v.get("owner_approved"), str) \
        and v["owner_approved"].strip() != ""


def spec_problems(spec, chars=None):
    """The thumbnail spec under the owner's rules of 27/10 and the scene rules (plan_check's own functions)."""
    sys.path.insert(0, str(HERE))
    import plan_check
    chars = characters() if chars is None else chars
    out = []
    if not isinstance(spec, dict):
        return ["THUMB_SPEC_INVALID (an object)"]
    if spec.get("format") not in FORMATS:
        out.append(f"THUMB_FORMAT_INVALID {spec.get('format')!r} (one of {sorted(FORMATS)})")
    cid, prompt = spec.get("character"), spec.get("prompt") if isinstance(spec.get("prompt"), str) else ""
    c = chars.get(cid) if isinstance(cid, str) else None
    if c is None:
        out.append(f"THUMB_CHARACTER_UNKNOWN {cid!r} (a characters.json entry)")
    elif c.get("status") != "APPROVED":
        out.append(f"THUMB_CHARACTER_NOT_APPROVED {cid} ({c.get('status')}; its reference sheet is reviewed first)")
    elif c.get("look") not in prompt:
        out.append(f"THUMB_LOOK_CHANGED {cid} (the prompt carries its look word for word)")
    keeper_look = (chars.get(KEEPER) or {}).get("look")
    if (cid == KEEPER or (keeper_look and keeper_look in prompt)) and not keeper_variant(spec):
        out.append("THUMB_KEEPER_FACE (the story character is the face; the Keeper only in an A/B variant with "
                   "variant {ab: true, owner_approved: <the owner's words and date>})")
    n = len(words(spec.get("text")))
    if not 1 <= n <= MAX_WORDS:
        out.append(f"THUMB_TEXT_WORDS {n} (1-{MAX_WORDS} words)")
    else:
        story = {w.lower() for w in words(spec.get("story")) if len(w) >= 4}
        names = {w.lower() for w in words((c or {}).get("name"))}
        if not {w.lower() for w in words(spec.get("text"))} & (story | names):
            out.append("THUMB_TEXT_NOT_STORY (the text names the story or its character)")
    emotion = spec.get("emotion")
    low = prompt.lower()
    if spec.get("framing") != "close-up" or "close-up" not in low or "face" not in low:
        out.append("THUMB_FACE_MISSING (framing close-up, and the prompt asks for a close-up of the face)")
    if not isinstance(emotion, str) or not emotion.strip() or emotion.strip().lower() not in low:
        out.append("THUMB_EMOTION_MISSING (an emotion, named in the prompt)")
    if not isinstance(spec.get("scene"), str) or not spec["scene"].strip():
        out.append("THUMB_SCENE_MISSING (the scene or object behind the face)")
    if spec.get("text") and spec["text"].lower() in low:
        out.append("THUMB_TEXT_IN_PROMPT (the words are drawn by our code, never by the image model)")
    if prompt:
        bad = plan_check.still_prompt_problems(f"thumb/{spec.get('episode')}", prompt, {"period": spec.get("period")})
        out += [f"THUMB_PROMPT_REFUSED {p}" for p in bad]
    else:
        out.append("THUMB_PROMPT_MISSING")
    return out


def publish_problems(episode, form=None, thumbnail=None, thumbs_dir=None, chars=None):
    """What a publish refuses: no spec, a spec with problems, not APPROVED, changed after approval, an image that is not
    the approved one, an approval that `approve` could not have written (another episode's spec, a score below the
    floor, no note, no recorded candidate with these bytes, this spec's digest and R16 PASS); each THUMB_NOT_APPROVED
    with its reason (the spec's own problems by their code). Stdlib only: publish-episode.yml has no PIL."""
    if not isinstance(episode, str) or not EPISODE.fullmatch(episode):
        return [f"THUMB_NOT_APPROVED {episode!r}: not an episode name"]
    thumbs_dir = Path(thumbs_dir or THUMBS)
    spec = load(episode, thumbs_dir)
    if spec is None:
        return [f"THUMB_NOT_APPROVED {episode}: no spec bible/thumbs/{episode}.json"]
    out = spec_problems(spec, chars)
    if form and spec.get("format") != form:
        out.append(f"THUMB_NOT_APPROVED {episode}: format {spec.get('format')} is not the episode's {form}")
    a = spec.get("approved") or {}
    if not reviewer_identity.valid(a):
        out.append(f"THUMB_NOT_APPROVED {episode}: unknown reviewer identity {a.get('model')!r}")
    if spec.get("status") != "APPROVED" or not a.get("sha256"):
        return out + [f"THUMB_NOT_APPROVED {episode}: status {spec.get('status')} (thumbs.py approve after review)"]
    if spec.get("episode") != episode:
        out.append(f"THUMB_NOT_APPROVED {episode}: the spec is {spec.get('episode')!r}'s")
    if a.get("spec_sha256") != digest(spec):
        out.append(f"THUMB_NOT_APPROVED {episode}: the spec changed after its approval")
    score = a.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not FLOOR <= score <= 10:
        out.append(f"THUMB_NOT_APPROVED {episode}: score {score!r} (overall >= {FLOOR})")
    if not isinstance(a.get("note"), str) or not a["note"].strip():
        out.append(f"THUMB_NOT_APPROVED {episode}: no review note")
    m = CID.fullmatch(a.get("candidate") or "") if isinstance(a.get("candidate"), str) else None
    rec_path = thumbs_dir / "candidates" / f"{a.get('candidate')}.json"
    rec = json.loads(rec_path.read_text()) if m and m.group(1) == episode and rec_path.is_file() else None
    if rec is None:
        out.append(f"THUMB_NOT_APPROVED {episode}: candidate {a.get('candidate')!r} is not a recorded candidate of it")
    elif (rec.get("sha256") != a["sha256"] or rec.get("spec_sha256") != a.get("spec_sha256")
          or (rec.get("r16") or {}).get("status") != "PASS"):
        out.append(f"THUMB_NOT_APPROVED {episode}: candidate {a['candidate']} is not these bytes, this spec and R16 PASS")
    img = image_path(episode, thumbs_dir)
    if not img.is_file() or sha256(img) != a["sha256"]:
        out.append(f"THUMB_NOT_APPROVED {episode}: the image is not the approved one (sha256)")
    elif thumbnail is not None and sha256(thumbnail) != a["sha256"]:
        out.append(f"THUMB_NOT_APPROVED {episode}: the thumbnail to upload is not the approved one (sha256)")
    return out


def approved_image(episode, thumbs_dir=None):
    return image_path(episode, thumbs_dir)


def reference_inputs(spec, src_dir, out_dir, chars=None):
    """The character's kept references (`refs`), each verified against its image record's sha256 in SRC_DIR (the
    release asset saved as ch-<id>-<view>.png), saved as a 2048 px JPEG (the image model takes 15 MiB at most)."""
    from PIL import Image
    chars = characters() if chars is None else chars
    cid = spec["character"]
    out = []
    for view in chars[cid].get("refs") or []:
        rec = json.loads((CHARACTERS / "images" / f"ch-{cid}-{view}.json").read_text())
        src = Path(src_dir) / f"ch-{cid}-{view}.png"
        if not src.is_file() or sha256(src) != rec["sha256"]:
            raise SystemExit(f"THUMB_REFERENCE_MISMATCH ch-{cid}-{view} (not the approved image)")
        dst = Path(out_dir) / f"ch-{cid}-{view}.jpg"
        dst.parent.mkdir(parents=True, exist_ok=True)
        Image.open(src).convert("RGB").resize((2048, 2048), Image.LANCZOS).save(dst, "JPEG", quality=92)
        out.append({"record": rec["id"], "sha256": rec["sha256"], "sent": rel(dst), "sent_sha256": sha256(dst)})
    return out


def cover(im, size):
    """Scale to cover SIZE, then centre-crop (faces sit in the middle of the model's frame)."""
    from PIL import Image
    w, h = im.size
    k = max(size[0] / w, size[1] / h)
    im = im.resize((round(w * k), round(h * k)), Image.LANCZOS)
    left, top = (im.size[0] - size[0]) // 2, (im.size[1] - size[1]) // 2
    return im.crop((left, top, left + size[0], top + size[1]))


def overlay(im, text, form):
    """Our own text (the image model never writes): white bold capitals with a black stroke; on a Short in the top
    fifth (the Shorts player covers the bottom), on a long across the bottom third; at most two lines."""
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(im)
    w, h = im.size
    text = " ".join(words(text)).upper()
    parts = text.split()
    lines = [text] if len(parts) <= 2 else [" ".join(parts[:(len(parts) + 1) // 2]), " ".join(parts[(len(parts) + 1) // 2:])]
    box_w, box_h = w * 0.9, h * (0.17 if form == "short" else 0.36)
    size = int(box_h / len(lines))
    while size > 20:
        font = ImageFont.truetype(FONT, size)
        stroke = max(3, size // 12)
        dims = [draw.textbbox((0, 0), line, font=font, stroke_width=stroke) for line in lines]
        if max(b[2] - b[0] for b in dims) <= box_w and sum(b[3] - b[1] for b in dims) * 1.08 <= box_h:
            break
        size -= 4
    total = sum(b[3] - b[1] for b in dims) * 1.08
    y = h * 0.06 if form == "short" else h * 0.95 - total
    for line, b in zip(lines, dims):
        draw.text(((w - (b[2] - b[0])) / 2 - b[0], y - b[1]), line, font=font, fill=(255, 255, 255),
                  stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += (b[3] - b[1]) * 1.08
    return im


def r16(path):
    sys.path.insert(0, str(HERE.parent))
    import thumb_check
    from PIL import Image
    m = thumb_check.thumb_study.measure(Image.open(path).convert("RGB"))
    fails = thumb_check.verdict(m)
    return {"status": "FAIL" if fails else "PASS", "fails": fails, "metrics": {k: round(v, 3) for k, v in m.items()}}


def finalize(spec_file, image, run, n, meta, thumbs_dir=None):
    """One candidate: the model's picture to the format, our text on it, both sha256, the spec digest, R16."""
    from PIL import Image
    spec = json.loads(Path(spec_file).read_text())
    bad = spec_problems(spec)
    if bad:
        raise SystemExit("THUMB_SPEC_REFUSED " + "; ".join(bad))
    if not re.fullmatch(r"[0-9]{1,20}", str(run)) or not 1 <= int(n) <= 9:
        raise SystemExit(f"THUMB_CANDIDATE_NAME_REFUSED {run}-{n}")
    thumbs_dir = Path(thumbs_dir or THUMBS)
    cid = f"{spec['episode']}-{run}-{n}"
    form = spec["format"]
    with Image.open(image) as src:
        source_size = list(src.size)
        base = cover(src.convert("RGB"), FORMATS[form])
    base_path = thumbs_dir / "candidates" / f"{cid}-base.jpg"
    base_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(base_path, "JPEG", quality=92)
    dst = thumbs_dir / "candidates" / f"{cid}.jpg"
    overlay(base.copy(), spec["text"], form).save(dst, "JPEG", quality=90)
    rec = {"id": cid, "episode": spec["episode"], "run": str(run), "status": "DRAFT", "format": form,
           "size": list(FORMATS[form]), "spec_sha256": digest(spec), "prompt": spec["prompt"],
           "text": spec["text"], "text_by": "thumbs.py overlay (DejaVu Sans Bold), never the image model",
           "source": meta.get("source"), "model": meta.get("model"), "ratio": meta.get("ratio"),
           "resolution": meta.get("resolution"), "conversation_id": meta.get("conversation_id"),
           "quote": meta.get("quote"), "references": meta.get("references") or [],
           "references_live": meta.get("references_live"), "source_size": source_size,
           "base_path": rel(base_path), "base_sha256": sha256(base_path),
           "repo_path": rel(dst), "sha256": sha256(dst), "r16": r16(dst),
           "generated_by": "HeroVerse pipeline (AI-generated image)"}
    if dst.stat().st_size > 2 * 1024 * 1024:
        raise SystemExit(f"THUMB_BYTES {dst.stat().st_size} (YouTube takes 2 MB)")
    save(dst.with_suffix(".json"), rec)
    return rec


def sheet(episode, run, out_jpg, thumbs_dir=None):
    """The run's candidates side by side, labelled, with the spec's text and R16 verdict."""
    from PIL import Image, ImageDraw
    thumbs_dir = Path(thumbs_dir or THUMBS)
    recs = [json.loads(p.read_text()) for p in sorted((thumbs_dir / "candidates").glob(f"{episode}-{run}-*.json"))]
    if not recs:
        raise SystemExit(f"THUMB_SHEET_EMPTY {episode} run {run}")
    tw, th = (360, 640) if recs[0]["format"] == "short" else (640, 360)
    band = 44
    canvas = Image.new("RGB", (tw * len(recs), th + band), (20, 20, 20))
    draw = ImageDraw.Draw(canvas)
    for k, r in enumerate(recs):
        canvas.paste(Image.open(REPO / r["repo_path"]).convert("RGB").resize((tw, th)), (k * tw, 0))
        refs = "refs" if r.get("references_live") else "text-only"
        draw.text((k * tw + 6, th + 6), f"{r['id']}  ({refs})", fill=(235, 235, 235))
        draw.text((k * tw + 6, th + 24), f"R16 {r['r16']['status']} sat {r['r16']['metrics'].get('saturation')}",
                  fill=(200, 200, 200))
    Path(out_jpg).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_jpg, "JPEG", quality=88)
    return [r["id"] for r in recs]


def approve(episode, candidate, score, note, thumbs_dir=None, today=None, chars=None, *, reviewer=None):
    """The named session's review approved CANDIDATE (overall >= 9.5): its image becomes bible/thumbs/<episode>.jpg and the spec
    APPROVED with the sha256 computed here. Refused when the candidate is not the recorded image, was made from
    another spec, fails R16 (thumb_check.py), or the spec fails its own rules."""
    thumbs_dir = Path(thumbs_dir or THUMBS)
    spec = load(episode, thumbs_dir)
    if spec is None:
        raise SystemExit(f"THUMB_SPEC_MISSING {episode}")
    bad = spec_problems(spec, chars)
    if bad:
        raise SystemExit("THUMB_SPEC_REFUSED " + "; ".join(bad))
    if not isinstance(score, (int, float)) or not FLOOR <= score <= 10:
        raise SystemExit(f"THUMB_SCORE_BELOW_FLOOR {score} (overall >= {FLOOR})")
    if not isinstance(note, str) or not note.strip():
        raise SystemExit("THUMB_NOTE_MISSING (what the review saw)")
    m = CID.fullmatch(candidate or "")
    src = thumbs_dir / "candidates" / f"{candidate}.jpg"
    if not m or m.group(1) != episode or not src.is_file() or not src.with_suffix(".json").is_file():
        raise SystemExit(f"THUMB_CANDIDATE_UNKNOWN {candidate} (a candidate of {episode} in thumbs/candidates)")
    meta = json.loads(src.with_suffix(".json").read_text())
    if sha256(src) != meta.get("sha256"):
        raise SystemExit(f"THUMB_CANDIDATE_SHA256_MISMATCH {candidate}")
    if meta.get("spec_sha256") != digest(spec):
        raise SystemExit(f"THUMB_SPEC_CHANGED {candidate} (made from another spec; make it again)")
    check = r16(src)
    if check["fails"]:
        raise SystemExit(f"THUMB_R16_FAIL {candidate} " + "; ".join(check["fails"]))
    if meta.get("episode") != episode or spec.get("episode") != episode:
        raise SystemExit(f"THUMB_CANDIDATE_UNKNOWN {candidate} (the spec and candidate are {episode}'s)")
    model = reviewer_identity.require(reviewer)
    dst = image_path(episode, thumbs_dir)
    shutil.copyfile(src, dst)
    spec.update({"status": "APPROVED", "repo_path": rel(dst),
                 "approved": {"sha256": sha256(dst), "spec_sha256": digest(spec), "candidate": candidate,
                              "score": score, "note": note.strip(),
                              "date": today or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                              "by": model, "model": model}})
    save(spec_path(episode, thumbs_dir), spec)
    return spec


def main(argv):
    cmd, args = (argv[1], argv[2:]) if len(argv) > 1 else (None, [])
    if cmd == "check" and len(args) == 1:
        bad = spec_problems(json.loads(Path(args[0]).read_text()))
        print(json.dumps({"spec": args[0], "problems": bad}))
        return 1 if bad else 0
    if cmd == "refs" and len(args) == 3:
        print(json.dumps(reference_inputs(json.loads(Path(args[0]).read_text()), args[1], args[2]), indent=1))
        return 0
    if cmd == "finalize" and len(args) == 5:
        rec = finalize(args[0], args[1], args[2], args[3], json.loads(Path(args[4]).read_text()))
        print(json.dumps({"candidate": rec["id"], "sha256": rec["sha256"], "r16": rec["r16"]["status"]}))
        return 0
    if cmd == "sheet" and len(args) == 3:
        print(json.dumps({"sheet": args[2], "candidates": sheet(*args)}))
        return 0
    if cmd == "approve" and len(args) == 8 and args[2] == "--score" and args[4] == "--note" and args[6] == "--reviewer":
        spec = approve(args[0], args[1], float(args[3]), args[5], reviewer=args[7])
        print(json.dumps({"episode": args[0], "status": spec["status"], "sha256": spec["approved"]["sha256"]}))
        return 0
    if cmd == "verify" and len(args) in (1, 2):
        bad = publish_problems(args[0], None, args[1] if len(args) == 2 else None)
        print(json.dumps({"episode": args[0], "problems": bad}))
        return 1 if bad else 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
