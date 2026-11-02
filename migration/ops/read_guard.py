#!/usr/bin/env python3
"""E263: PreToolUse hook for Read. Denies (exit 2) the whole-file reads that burn tens of thousands of tokens:
ERRORS.json without `limit`, video/audio files, and images or JSON over 2 MB."""
import json
import os
import sys

LIMIT_BYTES = 2 * 1024 * 1024
BINARY = (".mp4", ".mov", ".wav")
IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff")


def reason(tool_input):
    path = str(tool_input.get("file_path") or "")
    low = path.lower()
    if low.replace("\\", "/").endswith("migration/ops/errors.json") and not tool_input.get("limit"):
        return ("Read of ERRORS.json without `limit` is blocked (~62k tokens). Use "
                "`python3 migration/ops/errors_query.py E262`, `--grep word` or `--class name`.")
    if low.endswith(BINARY):
        return (f"Read of {os.path.basename(path)} is blocked (binary media). Use ffprobe or the saved "
                "evidence JSON/report instead.")
    if low.endswith(IMAGES + (".json",)):
        try:
            size = os.path.getsize(path)
        except OSError:
            return None
        if size > LIMIT_BYTES:
            return (f"Read of {os.path.basename(path)} ({size // 1024} KB) is blocked: over 2 MB. "
                    "Use jq/grep/python to extract the needed fields, or ffmpeg to shrink the image.")
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name", "Read") != "Read":
        return 0
    why = reason(data.get("tool_input") or {})
    if why:
        print(why, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
