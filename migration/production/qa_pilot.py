#!/usr/bin/env python3
"""QA of a rendered pilot against the frozen qa_criteria.json (F5 gates).

Uses the qualified instruments: av-event-meter (cuts), av-semantic (speech,
words, ASR), av-profile (loudness), plus ffprobe/full decode and the render
manifest for rights. Writes qa.json with PASS/FAIL per criterion. A FAIL
blocks approval; nothing here uploads or publishes.
"""
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
DIAG = HERE.parent / "diagnostics"
for sub in ("av-event-meter", "av-semantic", "av-profile"):
    sys.path.insert(0, str(DIAG / sub))
import av_profile  # noqa: E402
import av_semantic  # noqa: E402
from qualify_semantic import wer  # noqa: E402

OWNED_MUSIC_SHA256 = "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c"


def within(value, bounds):
    return value is not None and bounds[0] <= value <= bounds[1]


def main(video, manifest_path, script_path, criteria_path, yamnet, whisper, out):
    criteria = json.loads(Path(criteria_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    script = json.loads(Path(script_path).read_text())
    checks = {}
    decode = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", video, "-f", "null", "-"],
                            capture_output=True, text=True)
    checks["full_decode_without_errors"] = decode.returncode == 0 and not decode.stderr.strip()
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", video],
                                     check=True, capture_output=True, text=True).stdout)
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    checks["video_format"] = (len(v) == 1 and v[0]["codec_name"] == "h264" and v[0]["width"] == 1920
                              and v[0]["height"] == 1080 and v[0]["avg_frame_rate"] in ("30/1", "30000/1000")
                              and len(a) == 1 and a[0]["codec_name"] == "aac" and a[0]["sample_rate"] == "48000"
                              and a[0]["channels"] == 2)
    duration = float(info["format"]["duration"])
    checks["duration_min"] = duration >= criteria["technical"]["duration_seconds_min"]
    semantic = av_semantic.analyze(video, yamnet, whisper)
    profile = av_profile.profile(video, semantic)
    loud = profile["loudness"]
    checks["integrated_lufs"] = within(loud["integrated_lufs"], criteria["technical"]["integrated_lufs"])
    checks["true_peak"] = loud["true_peak_dbtp"] is not None and loud["true_peak_dbtp"] <= criteria["technical"]["true_peak_dbtp_max"]
    sp = criteria["speech"]
    presence = semantic["presence_fraction"]
    checks["speech_presence"] = presence["speech"] >= sp["speech_presence_min"]
    checks["no_singing"] = presence["singing"] <= sp["singing_presence_max"]
    text = " ".join(s["text"] for s in script["segments"])
    error = wer(text, semantic["transcript"])
    checks["wer_vs_script"] = error <= sp["wer_vs_script_max"]
    words = semantic["words"]
    wpm = len(words) / (duration / 60)
    checks["words_per_minute"] = within(wpm, sp["accepted_words_per_minute"])
    first = words[0]["start_seconds"] if words else None
    checks["first_word_onset"] = first is not None and first <= sp["first_word_onset_seconds_max"]
    checks["hook_second_person"] = any(w["word"].lower().strip(".,!?") in ("you", "your", "you're")
                                       and w["start_seconds"] <= sp["hook_second_person_within_seconds"] for w in words)
    ed = criteria["editing"]
    checks["picture_changes_per_minute"] = within(profile["editing"]["picture_changes_per_minute"], ed["picture_changes_per_minute"])
    checks["median_shot_seconds"] = within(profile["editing"]["median_shot_seconds"], ed["median_shot_seconds"])
    spans = {}
    for shot in manifest["shots"]:
        spans.setdefault(shot["video_id"], []).append((shot["source_start"], shot["source_start"] + shot["duration"]))
    checks["no_source_second_reused"] = all(b0 >= a1 - 1e-6 for s in spans.values()
                                            for (a0, a1), (b0, b1) in zip(sorted(s), sorted(s)[1:]))
    clips = manifest["clips"]
    checks["clips_creative_commons_with_attribution"] = bool(clips) and all(
        c["license"] == "creativeCommon" and c["attribution"] and c["picture_only"] for c in clips)
    checks["music_owned"] = manifest["music"]["sha256"] == OWNED_MUSIC_SHA256
    checks["voice_model_pinned"] = manifest["voice"]["voice_id"] == "am_michael"
    checks = {k: bool(v) for k, v in checks.items()}  # numpy bools are not JSON serializable
    result = {"version": "pilot-qa-v1", "pilot_id": manifest["pilot_id"], "output_sha256": manifest["output_sha256"],
              "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
              "measurements": {"duration_seconds": round(duration, 2), "loudness": loud,
                               "speech_presence": presence["speech"], "music_presence": presence["music"],
                               "wer_vs_script": round(error, 4), "accepted_words_per_minute": round(wpm, 1),
                               "first_word_seconds": first, "editing": profile["editing"],
                               "colour": profile["colour"], "rhythm": profile["rhythm"]},
              "transcript_head": semantic["transcript"][:400],
              "criteria_sha256": av_semantic.sha256(criteria_path),
              "human_review": "PENDING (D-076 calibration by sampling)",
              "upload_performed": False, "publication_performed": False}
    Path(out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"status": result["status"], "failed": [k for k, ok in checks.items() if not ok],
                      **{k: result["measurements"][k] for k in ("duration_seconds", "wer_vs_script",
                                                                "accepted_words_per_minute", "speech_presence")}}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:8]))
