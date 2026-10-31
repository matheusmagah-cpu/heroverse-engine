#!/usr/bin/env python3
"""Public images for scene stills, and the footage review record (owner 31/10: "Pode pegar imagens reais mesmo, que
se encaixa... E utilizar a pública, lógico."; DECISIONS: licensed/public-domain visuals with truthful provenance; E237).

A public still is an ordinary scene still (bible/stills/<still-id>.json, the same prompt, the same scene rules) whose
APPROVED image is a public-domain or openly licensed picture instead of a generated one. It then goes through
plan_check.frame_problems and shot_sources approve-source as still_motion exactly like a generated still: camera
motion only, never acted motion. Its record keeps `public` (plan_check.public_problems):

  source_page, file_url, host     https on plan_check.PUBLIC_PAGE_HOSTS / PUBLIC_FILE_HOSTS only
  title, author, licence          licence read from the source's own metadata (Commons extmetadata, the Met's
  licence_source, metadata_url    isPublicDomain); Public Domain, CC0, CC-BY-x, CC-BY-SA-x only (NC/ND/unknown refused)
  attribution                     required for CC-BY / CC-BY-SA; carried into the approval and the description
  retrieved_at, sha256, bytes     the exact downloaded bytes (Commons: their sha1 must equal the API's)
  dimensions, crop                the original's size and the crop box [x, y, w, h] at the plan's aspect

usage:
  public_sources.py fetch STILL_ID SOURCE_PAGE FILE_URL [--crop X,Y,W,H] [--n N] [--sha256 HEX]
        download from an allowlisted host, verify the licence from the source's API, record a DRAFT candidate
        (bible/stills/candidates/<still>-<utc yyyymmddHHMMSS>-<n>.jpg + .json; the crop resized to the plan's side)
  public_sources.py approve STILL_ID CANDIDATE_ID --score S --checked period,writing,god,characters --note TEXT
        --reviewer MODEL
        after the named reviewer's full-resolution review (>= 9.5) of the candidate: period accuracy, no legible
        writing / watermark / signature text, God never depicted as a figure, characters consistent or anonymous
  public_sources.py footage-seen CLIP_ID CLIP_SHA256 FRAMES --note TEXT --reviewer MODEL
        the named reviewer's real frame review of one library clip (its sha256, the frames looked at): writes
        claude_seen and its review record; nothing sets claude_seen automatically
"""
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan_check  # noqa: E402
import reviewer_identity  # noqa: E402
import scene_stills  # noqa: E402

LIBRARY = HERE.parents[1] / "production" / "footage" / "library"
MAX_BYTES = 80 * 1024 * 1024
USER_AGENT = "HeroVerse-still-pipeline/1.0 (https://github.com/matheusmagah-cpu/heroverse-engine)"
FOOTAGE_FRAMES_MIN = 3


def host_problem(url, hosts):
    """None when URL is https on one of HOSTS, else the reason."""
    p = urllib.parse.urlsplit(str(url or ""))
    if p.scheme != "https" or (p.hostname or "") not in hosts or p.username or p.port not in (None, 443):
        return f"PUBLIC_HOST_REFUSED {url!r} (https on {sorted(hosts)})"
    return None


class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        why = host_problem(newurl, plan_check.PUBLIC_FILE_HOSTS | plan_check.PUBLIC_API_HOSTS)
        if why:
            raise SystemExit(f"{why} (redirected)")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_get(url):
    """The bytes at URL (an allowlisted host, redirects too), at most MAX_BYTES."""
    opener = urllib.request.build_opener(_Redirects)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener.open(req, timeout=120) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise SystemExit(f"PUBLIC_FILE_TOO_LARGE {url} (> {MAX_BYTES} bytes)")
    return data


def _strip_html(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(text or ""))).strip()


def commons_meta(page, file_url, data, get):
    """Wikimedia Commons: the file's own API record (imageinfo + extmetadata). The file URL must be the API's, the
    bytes' sha1 the API's (PUBLIC_SHA_MISMATCH), the licence its machine-readable one."""
    path = urllib.parse.urlsplit(page).path
    if not path.startswith("/wiki/File:"):
        raise SystemExit(f"PUBLIC_SOURCE_PAGE_REFUSED {page} (a commons.wikimedia.org/wiki/File:... page)")
    title = urllib.parse.unquote(path[len("/wiki/"):])
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2&prop=imageinfo"
           "&iiprop=url%7Csha1%7Csize%7Cmime%7Cextmetadata&titles=" + urllib.parse.quote(title))
    pages = (json.loads(get(api)).get("query") or {}).get("pages") or []
    info = ((pages[0] if pages else {}).get("imageinfo") or [{}])[0]
    if info.get("url") != file_url:
        raise SystemExit(f"PUBLIC_FILE_NOT_THE_PAGES {file_url} (the API gives {info.get('url')!r} for {title})")
    if hashlib.sha1(data).hexdigest() != info.get("sha1"):
        raise SystemExit(f"PUBLIC_SHA_MISMATCH {file_url} (the bytes' sha1 is not the Commons API's)")
    ext = info.get("extmetadata") or {}
    val = lambda k: _strip_html((ext.get(k) or {}).get("value"))  # noqa: E731
    if val("NonFree").lower() in ("true", "1"):
        raise SystemExit(f"PUBLIC_LICENCE_REFUSED {title} (Commons marks it non-free)")
    licence = plan_check.normalize_licence(val("License"), val("LicenseShortName"))
    return {"title": val("ObjectName") or title[len("File:"):], "author": val("Artist") or val("Credit"),
            "licence": licence, "licence_as_published": val("LicenseShortName") or val("License"),
            "licence_source": "commons-extmetadata", "metadata_url": api}


def met_meta(page, file_url, data, get):
    """The Met's Open Access: the object's collection API record; isPublicDomain must be true (Open Access, CC0) and
    the file one of the object's own images."""
    m = re.fullmatch(r"/art/collection/search/([0-9]{1,9})/?", urllib.parse.urlsplit(page).path)
    if not m:
        raise SystemExit(f"PUBLIC_SOURCE_PAGE_REFUSED {page} (a www.metmuseum.org/art/collection/search/<id> page)")
    api = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{m.group(1)}"
    obj = json.loads(get(api))
    if obj.get("isPublicDomain") is not True:
        raise SystemExit(f"PUBLIC_LICENCE_REFUSED {page} (the Met's API: isPublicDomain is not true)")
    if file_url not in [obj.get("primaryImage")] + list(obj.get("additionalImages") or []):
        raise SystemExit(f"PUBLIC_FILE_NOT_THE_PAGES {file_url} (not an image of object {m.group(1)})")
    return {"title": obj.get("title") or "", "author": obj.get("artistDisplayName") or "Unknown artist",
            "licence": "CC0", "licence_as_published": "Open Access (CC0), isPublicDomain true",
            "licence_source": "met-collectionapi", "metadata_url": api}


# a host whose licence can be read from its own API; any other allowlisted host is refused until one is written
VERIFIERS = {"commons.wikimedia.org": commons_meta, "www.metmuseum.org": met_meta}


def attribution_for(meta, page):
    return f"\"{meta['title']}\" by {meta['author']}, {meta['licence']}, via {page}"


def fetch(still, page, file_url, crop=None, n=1, expect_sha256=None, stills_dir=None, get=http_get, now=None):
    """A public picture recorded as a DRAFT candidate of STILL: hosts allowlisted, licence verified from the source,
    sha256 of the exact bytes, the crop at the plan's aspect and resolution, resized to the plan's side."""
    from PIL import Image
    stills_dir = Path(stills_dir or plan_check.STILLS_DIR)
    rec = plan_check.still_record(still, stills_dir)
    if rec is None:
        raise SystemExit(f"STILL_MISSING {still}")
    for url, hosts in ((page, plan_check.PUBLIC_PAGE_HOSTS), (file_url, plan_check.PUBLIC_FILE_HOSTS)):
        why = host_problem(url, hosts)
        if why:
            raise SystemExit(why)
    verify = VERIFIERS.get(urllib.parse.urlsplit(page).hostname)
    if verify is None:
        raise SystemExit(f"PUBLIC_LICENCE_UNVERIFIED {page} (no licence reader for this host: {sorted(VERIFIERS)})")
    if not (isinstance(n, int) and 1 <= n <= 9):
        raise SystemExit(f"STILL_CANDIDATES_INVALID {n} (1-9)")
    data = get(file_url)
    digest = hashlib.sha256(data).hexdigest()
    if expect_sha256 is not None and digest != expect_sha256:
        raise SystemExit(f"PUBLIC_SHA256_MISMATCH {file_url} (got {digest}, expected {expect_sha256})")
    meta = verify(page, file_url, data, get)
    if not meta["licence"]:
        raise SystemExit(f"PUBLIC_LICENCE_REFUSED {page} ({meta['licence_as_published']!r}: Public Domain, CC0, "
                         "CC-BY or CC-BY-SA only)")
    im = Image.open(io.BytesIO(data))
    im.load()
    dims = list(im.size)
    aspect = scene_stills.still_aspect(still, stills_dir)
    box = list(crop) if crop else centre_crop(dims, aspect)
    stamp = (now or datetime.now(timezone.utc))
    public = {"source_page": page, "file_url": file_url, "host": urllib.parse.urlsplit(file_url).hostname,
              **meta, "attribution": attribution_for(meta, page) if meta["licence"].startswith("CC-BY") else None,
              "retrieved_at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "sha256": digest, "bytes": len(data),
              "dimensions": dims, "crop": box}
    bad = plan_check.public_problems(public, aspect)
    if bad:
        raise SystemExit(bad[0])
    side = scene_stills.SIDES[aspect]
    cid = f"{still}-{stamp.strftime('%Y%m%d%H%M%S')}-{n}"
    dst = stills_dir / "candidates" / f"{cid}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    x, y, w, h = box
    im.convert("RGB").crop((x, y, x + w, y + h)).resize(side, Image.LANCZOS).save(dst, "JPEG", quality=92)
    out = {"id": cid, "still": still, "episode": rec.get("episode"), "shot": rec.get("shot"),
           "run": stamp.strftime("%Y%m%d%H%M%S"), "status": "DRAFT", "prompt": rec.get("prompt"),
           "source": "public", "engine": "public-image", "references": [], "pavo": None,
           "upscaler": f"crop {box}, Lanczos to {side[0]}x{side[1]}", "aspect_ratio": aspect, "size": list(side),
           "repo_path": scene_stills.rel(dst), "sha256": scene_stills.sha256(dst), "public": public}
    scene_stills.save(dst.with_suffix(".json"), out)
    return out


def centre_crop(dims, aspect):
    """The largest centred box at ASPECT inside DIMS."""
    w, h = dims
    aw, ah = (int(v) for v in aspect.split(":"))
    if w * ah > h * aw:
        cw = round(h * aw / ah)
        return [(w - cw) // 2, 0, cw, h]
    ch = round(w * ah / aw)
    return [0, (h - ch) // 2, w, ch]


def repeat_refusal(still, rec, public, stills_dir):
    """E139 for a public picture: the same original (by sha256, whatever crop) APPROVED for another still of this plan
    whose shot is nearer than story QA's image_repeat_gap_seconds_min (a Short is shorter than the gap: any other)."""
    import long_plan_check as lpc
    others = []
    for p in sorted(Path(stills_dir).glob("*.json")):
        o = json.loads(p.read_text())
        if o.get("id") != still and o.get("status") == "APPROVED" and o.get("episode") == rec.get("episode") \
                and (o.get("public") or {}).get("sha256") == public.get("sha256"):
            others.append(o)
    if not others:
        return None
    path = HERE / "plans" / f"{rec.get('episode')}.json"
    plan = json.loads(path.read_text()) if path.is_file() else {}
    gap = (lpc.qa_for(plan) or lpc.qa())["grammar"]["image_repeat_gap_seconds_min"]
    near = [o["id"] for o in others]
    if plan.get("version") == lpc.VERSION:
        tl = lpc.timeline(plan)
        at = {s["id"]: (tl["begin"][i], tl["end"][i]) for i, s in enumerate(plan["shots"])}
        mine = at.get(rec.get("shot"))
        near = [o["id"] for o in others if mine is None or o.get("shot") not in at
                or max(at[o["shot"]][0] - mine[1], mine[0] - at[o["shot"]][1]) < gap]
    if not near:
        return None
    return (f"PUBLIC_IMAGE_REPEAT {still} (the same picture, sha256 {public.get('sha256')}, is approved for "
            f"{', '.join(near)} within story QA's image_repeat_gap_seconds_min {gap:g} s; E139)")


def approve(still, candidate, score, checked, note, stills_dir=None, today=None, *, reviewer=None):
    """The named reviewer's full-resolution review approved the public CANDIDATE as STILL: the same checks as a
    generated still (scene_stills.approve: sha256, aspect, prompt, scene rules, E122) plus the public record's own
    (licence, attribution, hosts, resolution), the review's checks and note, and E139's repeat rule."""
    import shutil
    stills_dir = Path(stills_dir or plan_check.STILLS_DIR)
    rec = plan_check.still_record(still, stills_dir)
    if rec is None:
        raise SystemExit(f"STILL_MISSING {still}")
    if not isinstance(score, (int, float)) or not math.isfinite(score) or not scene_stills.FLOOR <= score <= 10:
        raise SystemExit(f"STILL_SCORE_BELOW_FLOOR {score} (overall >= {scene_stills.FLOOR})")
    review = {"checked": sorted({c.strip() for c in checked or [] if c.strip()}),
              "note": (note or "").strip() if isinstance(note, str) else ""}
    parts = scene_stills.split_candidate(candidate)
    src = stills_dir / "candidates" / f"{candidate}.jpg"
    if not parts or parts[0] != still or not src.is_file() or not src.with_suffix(".json").is_file():
        raise SystemExit(f"STILL_CANDIDATE_UNKNOWN {candidate} (a candidate of {still} in stills/candidates)")
    meta = json.loads(src.with_suffix(".json").read_text())
    public = meta.get("public")
    if not isinstance(public, dict):
        raise SystemExit(f"PUBLIC_CANDIDATE_REFUSED {candidate} (not a public candidate: scene_stills.py approve)")
    if scene_stills.sha256(src) != meta.get("sha256"):
        raise SystemExit(f"STILL_CANDIDATE_SHA256_MISMATCH {candidate}")
    review["reviewed_sha256"] = meta.get("sha256")
    bad = plan_check.public_review_problems(review)
    if bad:
        raise SystemExit(bad[0])
    from PIL import Image
    with Image.open(src) as im:
        size = im.size
    aspect = scene_stills.still_aspect(still, stills_dir)
    if not scene_stills.at_aspect(size, aspect):
        raise SystemExit(f"STILL_ASPECT_MISMATCH {candidate} ({list(size)} is not {aspect})")
    bad = plan_check.public_problems(public, aspect)
    if bad:
        raise SystemExit(bad[0])
    if meta.get("prompt") != rec.get("prompt"):
        raise SystemExit(f"STILL_PROMPT_CHANGED {candidate} (chosen for another prompt than {still}'s; fetch again)")
    plan_path = HERE / "plans" / f"{rec.get('episode')}.json"
    plan = json.loads(plan_path.read_text()) if plan_path.is_file() else {}
    bad = plan_check.still_prompt_problems(f"{rec.get('shot')}/{still}", rec["prompt"], plan)
    if bad:
        raise SystemExit(f"STILL_PROMPT_REFUSED {still}: " + "; ".join(bad))
    unref = plan_check.prop_reference_problems(rec["prompt"], [], pavo=None, plan=plan or None)
    if unref:   # E122: a prop's one look comes from its approved references; a public picture of it is refused
        raise SystemExit(f"STILL_PROP_UNREFERENCED {candidate}: " + "; ".join(unref) + " (E122)")
    repeat = repeat_refusal(still, rec, public, stills_dir)
    if repeat:
        raise SystemExit(repeat)
    model = reviewer_identity.require(reviewer)
    dst = stills_dir / f"{still}.jpg"
    shutil.copyfile(src, dst)
    rec.update({"status": "APPROVED", "repo_path": scene_stills.rel(dst), "sha256": scene_stills.sha256(dst),
                "size": meta.get("size"), "candidate": candidate, "engine": "public-image", "references": [],
                "pavo": None, "source": {"license": public["licence"], "revision": f"public:{public['sha256']}"},
                "public": public,
                "approved": {"date": today or datetime.now(timezone.utc).strftime("%Y-%m-%d"), "score": score,
                             "note": review["note"], "by": model, "model": model, "review": review,
                             "prompt_sha256": hashlib.sha256(rec["prompt"].encode()).hexdigest(),
                             "references_sha256": plan_check.reference_digest([])}})
    scene_stills.save(stills_dir / f"{still}.json", rec)
    return rec


def footage_seen(clip_id, clip_sha256, frames, note, library=None, today=None, *, reviewer=None):
    """The named reviewer's real frame review of one library clip: the clip's own sha256 (the bytes looked at), how
    many frames, and what was seen. Only then claude_seen (shot_sources.footage_ok) is written, with that record."""
    folder = Path(library or LIBRARY)
    path = folder / f"{clip_id}.json"
    if not re.fullmatch(r"clip-[a-z0-9-]+", str(clip_id or "")) or not path.is_file():
        raise SystemExit(f"FOOTAGE_UNKNOWN {clip_id}")
    rec = json.loads(path.read_text())
    if rec.get("vetting") != "APPROVED":
        raise SystemExit(f"FOOTAGE_NOT_VETTED {clip_id} (vetting {rec.get('vetting')})")
    if not rec.get("sha256") or clip_sha256 != rec.get("sha256"):
        raise SystemExit(f"FOOTAGE_SHA256_MISMATCH {clip_id} (the review names {clip_sha256}, the clip is "
                         f"{rec.get('sha256')})")
    if not isinstance(frames, int) or frames < FOOTAGE_FRAMES_MIN:
        raise SystemExit(f"FOOTAGE_REVIEW_INCOMPLETE {clip_id} (at least {FOOTAGE_FRAMES_MIN} frames looked at)")
    if not isinstance(note, str) or not note.strip():
        raise SystemExit(f"FOOTAGE_REVIEW_NOTE_MISSING {clip_id} (what the frames showed)")
    model = reviewer_identity.require(reviewer)
    rec["claude_seen"] = True
    rec["claude_seen_review"] = {"date": today or datetime.now(timezone.utc).strftime("%Y-%m-%d"), "by": model,
                                 "model": model, "sha256": clip_sha256, "frames": frames, "note": note.strip()}
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
    return rec


def _opt(args, name):
    if name in args:
        k = args.index(name)
        if k + 1 >= len(args):
            raise SystemExit(__doc__)
        value = args[k + 1]
        del args[k:k + 2]
        return value
    return None


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd, args = argv[1], list(argv[2:])
    if cmd == "fetch":
        crop, n, expect = _opt(args, "--crop"), _opt(args, "--n"), _opt(args, "--sha256")
        if len(args) != 3:
            raise SystemExit(__doc__)
        box = [int(v) for v in crop.split(",")] if crop else None
        if box is not None and len(box) != 4:
            raise SystemExit("PUBLIC_CROP_INVALID (X,Y,W,H)")
        out = fetch(args[0], args[1], args[2], box, int(n or 1), expect)
        print(json.dumps({"candidate": out["id"], "sha256": out["public"]["sha256"],
                          "licence": out["public"]["licence"], "attribution": out["public"]["attribution"]}))
    elif cmd == "approve":
        score, checked, note, who = (_opt(args, k) for k in ("--score", "--checked", "--note", "--reviewer"))
        if len(args) != 2 or score is None:
            raise SystemExit(__doc__)
        rec = approve(args[0], args[1], float(score), (checked or "").split(","), note, reviewer=who)
        print(json.dumps({"still": rec["id"], "status": rec["status"], "sha256": rec["sha256"]}))
    elif cmd == "footage-seen":
        note, who = _opt(args, "--note"), _opt(args, "--reviewer")
        if len(args) != 3 or not args[2].isdigit():
            raise SystemExit(__doc__)
        rec = footage_seen(args[0], args[1], int(args[2]), note, reviewer=who)
        print(json.dumps({"clip": rec["id"], "claude_seen": rec["claude_seen"]}))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
