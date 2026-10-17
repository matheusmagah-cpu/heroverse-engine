#!/usr/bin/env python3
"""Profile each given media file (event meter + semantic layer + loudness/colour)
and write one compact JSON record per file for mining. Offline, no provider."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "av-semantic"))
import av_profile  # noqa: E402
import av_semantic  # noqa: E402


def main(output, yamnet, whisper_dir, paths):
    records = []
    for path in paths:
        semantic = av_semantic.analyze(path, yamnet, whisper_dir)
        record = av_profile.profile(path, semantic)
        record["sound_segments"] = semantic["segments"]
        record["image_sound"]["sync"] = {k: v for k, v in record["image_sound"]["sync"].items() if k != "pairs"}
        records.append(record)
    Path(output).write_text(json.dumps({"version": "reference-av-profiles-v1", "profiles": records}, indent=1) + "\n")
    print(json.dumps(records, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
