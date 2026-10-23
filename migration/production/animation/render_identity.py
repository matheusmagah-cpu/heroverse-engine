#!/usr/bin/env python3
"""Hash the complete render input identity; never approve or publish a render.

CLI: render_identity.py --script FILE --scenes FILE --voice FILE --music FILE
 --srt FILE --bundle DIR --criteria FILE --blender-version VERSION --engine NAME
 --samples N --fps N --resolution WIDTH HEIGHT [--out FILE]
"""
import argparse
import hashlib
import json
from pathlib import Path


def render_id(fields: dict) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_fields(args):
    bundle = Path(args.bundle)
    files = sorted(p for p in bundle.rglob("*") if p.is_file())
    if not files:
        raise ValueError("EMPTY_BUNDLE")
    if any(p.is_symlink() for p in bundle.rglob("*")):
        raise ValueError("BUNDLE_SYMLINK")
    fields = {key: file_sha256(getattr(args, value)) for key, value in (
        ("script_sha256", "script"), ("scenes_sha256", "scenes"),
        ("voice_wav_sha256", "voice"), ("music_sha256", "music"),
        ("srt_sha256", "srt"), ("criteria_sha256", "criteria"))}
    fields.update({"bundle_sha256 (each file)": {
        p.relative_to(bundle).as_posix(): file_sha256(p) for p in files},
        "blender_version": args.blender_version, "engine": args.engine,
        "samples": args.samples, "fps": args.fps, "resolution": args.resolution})
    required = json.loads(Path(args.criteria).read_text())["render_identity"]["fields"]
    if set(fields) != set(required):
        raise ValueError("IDENTITY_FIELDS_MISMATCH")
    return fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("script", "scenes", "voice", "music", "srt", "bundle", "criteria", "blender-version", "engine"):
        parser.add_argument("--" + name, required=True)
    for name in ("samples", "fps"):
        parser.add_argument("--" + name, required=True, type=int)
    parser.add_argument("--resolution", required=True, type=int, nargs=2)
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.samples <= 0 or args.fps <= 0 or min(args.resolution) <= 0:
        parser.error("render settings must be positive")
    fields = build_fields(args)
    text = json.dumps({"render_id": render_id(fields), "fields": fields}, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
