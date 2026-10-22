#!/usr/bin/env python3
"""Compare measured audiovisual features of acquired reference windows across
growth cohorts (winner / median / weak within the same channel and stratum).

Inputs: migration/acquisition/profiles/*.json (meter + semantic + loudness +
colour per window) and the market opportunity report. Output: per-cohort
feature table, per-channel winner-minus-weak differences and the opening
transcripts. With a handful of videos per cohort every difference is a
HYPOTHESIS for the modeler (F4), never a causal rule; small samples are
labelled INCONCLUSIVE.
"""
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "acquisition/profiles"
FEATURES = {
    "speech_presence": lambda p: p["sound_classes"]["presence_fraction"]["speech"],
    "music_presence": lambda p: p["sound_classes"]["presence_fraction"]["music"],
    "singing_presence": lambda p: p["sound_classes"]["presence_fraction"]["singing"],
    "words_per_minute": lambda p: p["sound_classes"]["words_per_minute"],
    "picture_changes_per_minute": lambda p: p["editing"]["picture_changes_per_minute"],
    "median_shot_seconds": lambda p: p["editing"]["median_shot_seconds"],
    "motion": lambda p: p["editing"]["motion_median_top_decile_diff"],
    "audio_onsets_per_minute": lambda p: p["rhythm"]["audio_onsets_per_minute"],
    "integrated_lufs": lambda p: p["loudness"]["integrated_lufs"],
    "mean_brightness": lambda p: p["colour"]["mean_brightness"],
    "mean_saturation": lambda p: p["colour"]["mean_saturation"],
}
MIN_PER_COHORT = 3


def load_profiles(directory=PROFILES):
    out = {}
    for path in sorted(directory.glob("acq-*-0-40-v1.json")):
        record = json.loads(path.read_text())["profiles"][0]
        video = path.name[len("acq-"):].rsplit("-0-40-v1.json", 1)[0]
        out[video] = record
    return out


def compare(profiles, cohorts):
    rows = []
    for video, profile in profiles.items():
        c = cohorts.get(video)
        if not c:
            continue
        row = {"video_id": video, "cohort": c["cohort"], "channel_id": c["channel_id"],
               "views_per_day_interval": c["views_per_day_interval"], "title": c["title"],
               "opening_transcript": profile["sound_classes"].get("transcript", "")}
        for name, fn in FEATURES.items():
            try:
                row[name] = fn(profile)
            except (KeyError, TypeError):
                row[name] = None
        rows.append(row)
    table = {}
    for cohort in ("WINNER", "MEDIAN", "WEAK"):
        members = [r for r in rows if r["cohort"] == cohort]
        stats = {}
        for name in FEATURES:
            values = [r[name] for r in members if r[name] is not None]
            stats[name] = round(statistics.median(values), 3) if values else None
        table[cohort] = {"n": len(members), "median": stats,
                         "status": "DESCRIPTIVE" if len(members) >= MIN_PER_COHORT else "INCONCLUSIVE_SMALL_SAMPLE"}
    pairs = []
    for channel in sorted({r["channel_id"] for r in rows}):
        w = [r for r in rows if r["channel_id"] == channel and r["cohort"] == "WINNER"]
        k = [r for r in rows if r["channel_id"] == channel and r["cohort"] == "WEAK"]
        if w and k:
            pairs.append({"channel_id": channel, "winner": w[0]["video_id"], "weak": k[0]["video_id"],
                          "difference_winner_minus_weak": {
                              n: (round(w[0][n] - k[0][n], 3) if w[0][n] is not None and k[0][n] is not None else None)
                              for n in FEATURES}})
    return {"version": "av-cohort-comparison-v1", "videos": len(rows), "cohort_table": table,
            "within_channel_pairs": pairs, "rows": rows,
            "interpretation": "Differences are hypotheses for the modeler; n per cohort is small and openings are 40 s only.",
            "provider_calls": 0}


def main(opportunity_path, out):
    report = json.loads(Path(opportunity_path).read_text())
    cohorts = {p["video_id"]: p for p in report["acquisition_plan_10_30_min"]}
    result = compare(load_profiles(), cohorts)
    Path(out).write_text(json.dumps(result, indent=1) + "\n")
    for cohort, value in result["cohort_table"].items():
        print(cohort, value["n"], value["status"], value["median"])
    for r in result["rows"]:
        print(r["cohort"], r["video_id"], r["views_per_day_interval"], "|", (r["opening_transcript"] or "")[:160])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
