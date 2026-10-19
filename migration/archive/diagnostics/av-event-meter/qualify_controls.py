#!/usr/bin/env python3
"""Blind qualification of av_event_meter on the five frozen synthetic controls.

Rebuilds the stimuli with the preserved recipe (hash-checked), requires byte
identity with the frozen SHA256SUMS, then measures each MP4 alone in an empty
directory through a separate isolated interpreter. Expected values come from
the recipe constants only. Offline: no network, model or provider call.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CONTROLS = HERE.parents[1] / "evidence/av-evaluator-controls-20261016"
RECIPE = CONTROLS / "scripts/build_and_verify.py"
RECIPE_SHA256 = "8b4b9ea021836045c74ec14bd3b881b4f69f9391720534607717de9c4a8fb95d"
SUMS = CONTROLS / "operator-only/SHA256SUMS.stimuli"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_recipe():
    if digest(RECIPE.read_bytes()) != RECIPE_SHA256:
        raise ValueError("PRESERVED_RECIPE_HASH_MISMATCH")
    spec = importlib.util.spec_from_file_location("preserved_control_recipe", RECIPE)
    recipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recipe)
    return recipe


def measure_blind(media):
    with tempfile.TemporaryDirectory(prefix="av_meter_blind_") as tmp:
        tmp = Path(tmp)
        shutil.copy2(HERE / "av_event_meter.py", tmp / "av_event_meter.py")
        shutil.copy2(media, tmp / "input.mp4")
        out = subprocess.run([sys.executable, "-I", "-B", "av_event_meter.py", "input.mp4"],
                             cwd=tmp, check=True, capture_output=True, env={"PATH": "/usr/bin:/bin"})
        return json.loads(out.stdout)


def check(name, flashing, offset, recipe, result, rules):
    failures = []
    expected_video = list(recipe.FLASH_STARTS) if flashing else []
    expected_audio = [] if offset is None else [t + offset for t in recipe.FLASH_STARTS]

    def onsets(kind, expected, tolerance):
        observed = [e["onset_seconds"] for e in result[kind]["events"]]
        if len(observed) != len(expected):
            failures.append(f"{kind}_count {len(observed)} != {len(expected)}")
        else:
            failures.extend(f"{kind}_onset {got} vs {want}" for got, want in zip(observed, expected)
                            if abs(got - want) > tolerance)

    onsets("audio", expected_audio, rules["audio_onset_tolerance_seconds"])
    onsets("video", expected_video, rules["visual_onset_tolerance_seconds"])
    if result["audio"]["exact_digital_silence"] != (offset is None):
        failures.append("exact_digital_silence")
    sync = result["sync"]
    if not (flashing and offset is not None):
        want = "NOT_MEASURABLE"
    else:
        want = "IN_SYNC" if -0.045 <= offset <= 0.125 else "OUT_OF_SYNC"
        if abs(sync["median_offset_seconds"] - offset) > rules["offset_tolerance_seconds"]:
            failures.append(f"offset {sync['median_offset_seconds']} vs {offset}")
    if sync["verdict"] != want:
        failures.append(f"verdict {sync['verdict']} != {want}")
    return {"control": name, "status": "PASS" if not failures else "FAIL", "failures": failures,
            "observed_audio_onsets": [e["onset_seconds"] for e in result["audio"]["events"]],
            "observed_video_onsets": [e["onset_seconds"] for e in result["video"]["events"]],
            "observed_offset_seconds": sync["median_offset_seconds"], "observed_verdict": sync["verdict"]}


def main(output):
    output = Path(output).resolve()
    if output.exists():
        raise SystemExit("NEW_OUTPUT_PATH_REQUIRED")
    criteria = json.loads((HERE / "criteria.json").read_text())
    recipe = load_recipe()
    frozen = dict(line.split("  stimuli/")[::-1] for line in SUMS.read_text().split("\n") if line)
    meter_sha = digest((HERE / "av_event_meter.py").read_bytes())
    results = []
    with tempfile.TemporaryDirectory(prefix="av_controls_") as tmp:
        root = Path(tmp)
        recipe.build(root)
        for name, condition, flashing, offset in recipe.CASES:
            media = root / "stimuli" / name
            if digest(media.read_bytes()) != frozen[name]:
                raise SystemExit(f"STIMULUS_NOT_BYTE_IDENTICAL {name}")
            results.append(check(name, flashing, offset, recipe, measure_blind(media), criteria["rules"]))
    passed = all(r["status"] == "PASS" for r in results)
    record = {
        "version": "av-event-meter-control-qualification-v1",
        "status": "PASS_5_OF_5_BLIND_CONTROLS" if passed else "FAIL",
        "criteria_sha256": digest((HERE / "criteria.json").read_bytes()),
        "meter_sha256": meter_sha, "recipe_sha256": RECIPE_SHA256,
        "stimuli_byte_identical_to_frozen": True, "blind_isolated_subprocess": True,
        "ffmpeg": subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0],
        "python": sys.version.split()[0],
        "results": results,
        "model_inferences": 0, "network_calls": 0, "provider_calls": 0,
        "production_authorized": False, "publication_authorized": False, "runtime_integrated": False,
        "scope": "Discrete flash/tone onsets and AV offset on five 6 s synthetic controls. Not semantic understanding, real-content accuracy or perceptual approval.",
    }
    output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"status": record["status"], "controls": [(r["control"], r["status"]) for r in results]}))
    return 0 if passed else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: qualify_controls.py NEW_OUTPUT_JSON")
    sys.exit(main(sys.argv[1]))
