#!/usr/bin/env python3
"""The character bible (owner, 2026-10-25: "if Moses appears once, he is the same Moses 100 videos later").

characters.json holds each character's canonical `look` (fixed words), `wardrobe` variants, FLUX `seed` and `status`.
Its reference sheet (front, three-quarter, full figure) is made by cf-images.yml (pilot "characters") and recorded in
images/<id>.json with its public release asset; Claude reviews the sheet and only then sets status APPROVED.

problems(shots) refuses a shot that names a character which is not APPROVED, or whose prompt does not carry the
character's look word for word. reference_urls(ids) gives the approved reference images an Agnes clip passes in
reference mode (at most 5), so the model sees the same face every time.
usage: characters.py check SHOTS_JSON      ([{"prompt": "...", "characters": ["eve"]}, ...]); exit 1 on a problem
"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RELEASE = "https://github.com/matheusmagah-cpu/heroverse-engine/releases/download/"
RAW = "https://raw.githubusercontent.com/matheusmagah-cpu/heroverse-engine/main/"   # refs kept in the repository
LEGACY_TAG = "v0.0.0-cloud-assets-20261013"   # records made before E85 name no release_tag
MAX_REFS = 5                      # Agnes Video 2.5 Flash reference mode
REF_ORDER = ("front", "three-quarter", "full")


def registry(path=HERE / "characters.json"):
    return json.loads(Path(path).read_text())["characters"]


def problems(shots, chars=None):
    chars = chars if chars is not None else registry()
    out = []
    for i, shot in enumerate(shots):
        for cid in shot.get("characters", []):
            c = chars.get(cid)
            if not c:
                out.append(f"CHARACTER_UNKNOWN shot {i}: {cid} (add it to characters.json first)")
            elif c.get("status") != "APPROVED":
                out.append(f"CHARACTER_NOT_APPROVED shot {i}: {cid} ({c.get('status')}; review its reference sheet)")
            elif c["look"] not in shot.get("prompt", ""):
                out.append(f"CHARACTER_LOOK_CHANGED shot {i}: {cid} (the prompt must carry its look word for word)")
    return out


def reference_urls(ids, images_dir=HERE / "images", chars=None):
    """Only the shots Claude kept (`refs`): one face per character, never a rejected look-alike."""
    chars = chars if chars is not None else registry()
    urls = []
    for cid in ids:
        for shot in chars.get(cid, {}).get("refs", REF_ORDER):
            rec = Path(images_dir) / f"ch-{cid}-{shot}.json"
            m = json.loads(rec.read_text()) if rec.exists() else {}
            if m.get("release_asset"):
                urls.append(f'{RELEASE}{m.get("release_tag") or LEGACY_TAG}/{m["release_asset"]}')
            elif m.get("repo_path"):   # the Keeper: a reviewed frame of his first Pavo test (2026-10-26)
                urls.append(RAW + m["repo_path"])
    if len(urls) > MAX_REFS:   # one face per character first: front views of every character, then the rest
        fronts = [u for u in urls if "-front-" in u]
        urls = (fronts + [u for u in urls if u not in fronts])[:MAX_REFS]
    return urls


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "check":
        raise SystemExit(__doc__)
    found = problems(json.loads(Path(sys.argv[2]).read_text()))
    print(json.dumps({"problems": found}))
    sys.exit(1 if found else 0)
