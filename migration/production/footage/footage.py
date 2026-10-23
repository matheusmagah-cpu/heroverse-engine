#!/usr/bin/env python3
"""Licensed real footage for the cinematic picture (owner, 2026-10-23: "no static images, real cinematic animation").

Sources, no paid call:
  pexels  -> api.pexels.com, Pexels License (free commercial use and modification, no attribution required),
             only when PEXELS_API_KEY is set
  commons -> commons.wikimedia.org, only CC0, public domain or CC BY (attribution goes into the description);
             share-alike (CC BY-SA) and non-commercial licences are refused
Every clip is cut to a clean 2560x1440 30 fps picture without audio and recorded with its source page, author,
licence, licence URL and SHA-256 in library/<id>.json. Nothing here uploads or publishes.

usage:
  footage.py search QUERIES_JSON OUT_DIR [PER_THEME]   candidates + downloads + transcodes into OUT_DIR
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "HeroVerse/1.0 (https://github.com/matheusmagah-cpu/heroverse-engine; footage library)"}
MIN_HEIGHT = 1440          # owner, 2026-10-23: never below 1440p (no plain upscale)
MIN_SECONDS = 8.0
CLIP_SECONDS = 20.0          # at most this much of each source is kept
TRIES_PER_QUERY = 6          # downloads per query at most (accepted or rejected)
W, H, FPS = 2560, 1440, 30
# R1 (no people) and no text or branding on screen: titles that announce them are refused before download
BLOCK = re.compile(r"(?i)\b(people|person|man|men|woman|women|girl|boy|child|children|kid|crowd|tourist|selfie|"
                   r"interview|portrait|face|wedding|festival|concert|protest|logo|text|title|intro|news|"
                   r"advert|commercial|drone pilot|vlog|car|traffic|city|street|police|military|war|skyline|building|"
                   r"rocket|launch|satellite|map|trailer|documentary|presents|rafting|kayak|boat|hurricane|storm|"
                   r"vigil|memorial|movie|film)s?\b|\b(18|19)\d\d\b")
COMMONS_OK = re.compile(r"(?i)^(cc0|cc-zero|public domain|pd|cc by \d(\.\d)?( \w+)?)$")


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


ACCEPTED = ("Pexels License", "CC0", "Public domain", "CC BY 2.0", "CC BY 2.5", "CC BY 3.0", "CC BY 4.0")  # = QA v4


def canonical(source, licence):
    """The licence as pilot-qa-criteria-v4 lists it ("CC BY 3.0 de" -> "CC BY 3.0"), or None when not accepted."""
    if source == "pexels":
        return "Pexels License" if licence == "Pexels License" else None
    raw = (licence or "").strip()
    if not COMMONS_OK.match(raw):
        return None
    if re.match(r"(?i)^(cc0|cc-zero)$", raw):
        return "CC0"
    if re.match(r"(?i)^(public domain|pd)$", raw):
        return "Public domain"
    m = re.match(r"(?i)^cc by (\d(\.\d)?)", raw)
    lic = f"CC BY {m.group(1)}" if m else None
    return lic if lic in ACCEPTED else None


def licence_ok(source, licence):
    return canonical(source, licence) is not None


def eligible(c):
    """A candidate is usable when its licence is accepted, it is at least 1080p and 8 s, and its title does not
    announce people, text or branding."""
    return (licence_ok(c["source"], c["licence"]) and (c.get("height") or 0) >= MIN_HEIGHT
            and (c.get("seconds") or 0) >= MIN_SECONDS and not BLOCK.search(c.get("title", "")))


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def commons_search(query, limit=50):
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6"
           f"&gsrsearch={urllib.parse.quote('filetype:video ' + query)}&gsrlimit={limit}&prop=videoinfo"
           "&viprop=url|size|mime|extmetadata|derivatives"
           "&viextmetadatafilter=LicenseShortName|LicenseUrl|Artist|AttributionRequired")
    out = []
    for p in (get_json(url).get("query") or {}).get("pages", {}).values():
        info = (p.get("videoinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        derivs = [d for d in info.get("derivatives") or [] if (d.get("height") or 0) >= MIN_HEIGHT]
        best = min(derivs, key=lambda d: d.get("height") or 0) if derivs else None  # the smallest >= 1440p
        out.append({"source": "commons", "title": p["title"].removeprefix("File:"),
                    "page": info.get("descriptionurl"), "width": info.get("width"), "height": info.get("height"),
                    "seconds": float(info.get("duration") or 0),
                    "licence": strip_html(meta.get("LicenseShortName", {}).get("value")),
                    "licence_url": strip_html(meta.get("LicenseUrl", {}).get("value")),
                    "author": strip_html(meta.get("Artist", {}).get("value"))[:120],
                    "download": (best or {}).get("src") or info.get("url")})
    return out


def pexels_search(query, key, limit=40):
    d = get_json(f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page={limit}"
                 "&orientation=landscape&size=large", {"Authorization": key})
    out = []
    for v in d.get("videos", []):
        files = [f for f in v.get("video_files", []) if (f.get("height") or 0) >= MIN_HEIGHT and f.get("link")]
        best = min(files, key=lambda f: f["height"]) if files else {}
        out.append({"source": "pexels", "title": v.get("url", "").rstrip("/").split("/")[-1].replace("-", " "),
                    "page": v.get("url"), "width": best.get("width"), "height": best.get("height"),
                    "seconds": float(v.get("duration") or 0), "licence": "Pexels License",
                    "licence_url": "https://www.pexels.com/license/", "author": (v.get("user") or {}).get("name", ""),
                    "download": best.get("link")})
    return out


def credit(c):
    """One description line per clip; required for CC BY, kept for every source as provenance."""
    if c["source"] == "pexels":
        return f"Footage: {c['author']} via Pexels ({c['page']})"
    return f"Footage: \"{c['title']}\" by {c['author'] or 'unknown author'}, {c['licence']}, via Wikimedia Commons ({c['page']})"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def transcode(src, dst, seconds):
    keep = max(MIN_SECONDS, min(CLIP_SECONDS, seconds - 2.0))
    start = 1.0 if seconds - keep >= 1.0 else 0.0   # skip the first second: fades, slates and camera shake
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start}", "-t", f"{keep}", "-i", str(src), "-an",
                    "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-movflags", "+faststart",
                    str(dst)], check=True)
    return start, keep


VET_WORDS = re.compile(r"(?i)\b(person|people|man|men|woman|women|girl|boy|child|children|face|hand|crowd|text|"
                       r"words|letters|logo|sign|caption|title|watermark|city|building|buildings|skyscraper|car|cars|"
                       r"truck|boat|kayak|raft|rocket|satellite|map|chart|diagram|screen|poster)\b")


def frame_luma(path):
    from PIL import Image, ImageStat
    return ImageStat.Stat(Image.open(path).convert("L")).mean[0]


def ocr_words(path):
    """Words tesseract reads on the frame with confidence >= 70 and >= 4 letters (titles, captions, labels)."""
    try:
        out = subprocess.run(["tesseract", str(path), "-", "--psm", "11", "tsv"], capture_output=True, text=True,
                             timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    words = []
    for line in out.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) == 12 and cols[11].strip() and float(cols[10]) >= 70 and len(re.sub(r"[^A-Za-z]", "", cols[11])) >= 4:
            words.append(cols[11].strip())
    return words


def describe(path):
    """A short description from an open vision model on Cloudflare Workers AI (free allocation), or None."""
    token, account = os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        return None
    body = json.dumps({"image": list(Path(path).read_bytes()), "max_tokens": 80,
                       "prompt": "Describe everything visible in this image in one sentence. Mention any people, "
                                 "text, logos, buildings or vehicles."}).encode()
    req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/llava-hf/llava-1.5-7b-hf",
                                 data=body, method="POST", headers={"Authorization": "Bearer " + token,
                                                                    "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return (json.loads(r.read()).get("result") or {}).get("description", "").strip() or None
    except Exception:  # noqa: BLE001  (quota or outage: the clip stays PENDING, never approved blind)
        return None


def vet(clip, work):
    """Automatic vetting on five frames: no black frames, no readable text, nothing the description names as
    people, text, buildings or vehicles. Every check must actually run: a missing check leaves the clip PENDING."""
    d = probe_seconds(clip)
    frames = []
    for k in range(5):
        f = work / f"{clip.stem}-vet-{k}.jpg"   # small JPEG: the vision model receives the bytes as a JSON array
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{d * (k + 0.5) / 5:.2f}", "-i", str(clip),
                        "-frames:v", "1", "-vf", "scale=672:378", "-q:v", "4", str(f)], check=True)
        frames.append(f)
    luma = [round(frame_luma(f), 1) for f in frames]
    ocr = [ocr_words(f) for f in frames]
    descriptions = [describe(frames[0]), describe(frames[2])]
    for f in frames:
        f.unlink(missing_ok=True)
    return decide(luma, ocr, descriptions)


def decide(luma, ocr, descriptions):
    """The vetting verdict from the measured frames (pure, so it is tested offline)."""
    words = [w for found in ocr if found for w in found]
    ocr_ran = all(found is not None for found in ocr)
    reasons = []
    if sum(1 for x in luma if x < 12) >= 2:
        reasons.append("BLACK_FRAMES")
    if words:
        reasons.append("TEXT_ON_SCREEN " + " ".join(words[:6]))
    named = sorted({m.group(1).lower() for t in descriptions if t for m in VET_WORDS.finditer(t)})
    if named:
        reasons.append("DESCRIBED " + ",".join(named))
    status = "REJECTED" if reasons else ("APPROVED" if ocr_ran and all(descriptions) else "PENDING")
    return {"vetting": status, "vetting_note": "automatic (5 frames: luma, tesseract OCR, llava description)",
            "vetting_reasons": reasons, "vetting_luma": luma, "vetting_descriptions": descriptions}


def probe_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def main(queries_path, out_dir, per_theme="3"):
    import hashlib
    spec = json.loads(Path(queries_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("PEXELS_API_KEY", "")
    lib = Path(spec.get("library", "migration/production/footage/library"))
    have = {p.stem for p in lib.glob("*.json")}
    seen_pages = {json.loads(p.read_text()).get("page") for p in lib.glob("*.json")}
    made = []
    for theme in spec["themes"]:
        cands = []
        if key:
            cands += pexels_search(theme["query"], key)
        cands += commons_search(theme["query"])
        picked = tried = 0
        for c in sorted((c for c in cands if eligible(c)), key=lambda c: (c["source"] != "pexels", -(c["seconds"]))):
            cid = f"clip-{theme['theme']}-{slug(c['title'])}"
            if cid in have or picked >= int(per_theme) or c["page"] in seen_pages:
                continue
            if tried >= TRIES_PER_QUERY:  # bounded run time: rejected candidates never stall the whole library
                break
            tried += 1
            raw = out / f"{cid}.src"
            try:
                req = urllib.request.Request(c["download"], headers=UA)
                with urllib.request.urlopen(req, timeout=300) as r, open(raw, "wb") as f:
                    f.write(r.read())
                start, keep = transcode(raw, out / f"{cid}.mp4", c["seconds"])
            except Exception as e:  # noqa: BLE001  (one bad source never stops the library)
                print(json.dumps({"skip": cid, "reason": f"{type(e).__name__}: {str(e)[:120]}"}))
                continue
            finally:
                raw.unlink(missing_ok=True)
            sha = hashlib.sha256((out / f"{cid}.mp4").read_bytes()).hexdigest()
            rec = {"id": cid, "theme": theme["theme"], "query": theme["query"], **{k: c[k] for k in (
                "source", "title", "page", "author", "licence_url")},
                "licence": canonical(c["source"], c["licence"]), "licence_as_published": c["licence"],
                "source_seconds": c["seconds"], "source_height": c["height"], "start": start, "seconds": keep,
                "credit": credit(c), "picture": f"{W}x{H} {FPS} fps H.264 crf 18, no audio", "frame": [W, H], "sha256": sha,
                **vet(out / f"{cid}.mp4", out)}
            (out / f"{cid}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
            have.add(cid)
            seen_pages.add(c["page"])
            made.append(cid)
            picked += 1 if rec["vetting"] != "REJECTED" else 0  # a rejected clip does not use the theme's quota
    print(json.dumps({"made": made}))


if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[1] != "search":
        raise SystemExit(__doc__)
    main(*sys.argv[2:5])
