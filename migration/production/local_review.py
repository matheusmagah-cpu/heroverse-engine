#!/usr/bin/env python3
"""Offline-capable calibration adapter; never a production reviewer or approval.

usage: local_review.py RENDER WORK OUT_JSON TITLE MODEL_ID REVISION
ML imports/downloads happen only in load_runtime(), called by the manual workflow.
The 0.5-fps frames and word-timestamped ASR are data, not native audio. Context
overflow is ERROR, never truncation or a reduced sampling rate. CPU speed and
accuracy require real runs; a linear timing projection is not a full-video test.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import long_review as lr
import review_calibration as rc

MODEL_ID = "HuggingFaceTB/SmolVLM2-2.2B-Instruct"
REVISION = "482adb537c021c86670beed01cd58990d01e72e4"
FPS = 0.5
CASE_SECONDS = 180
FRAME_COUNT = 90
FRAME_FILTER = "fps=0.5:start_time=0:round=up"
MAX_NEW_TOKENS = 512
ASR_MODEL = "base.en"


def validate_model(model, revision):
    # Adding another model requires its separately verified license/revision/adapter.
    if (model, revision) != (MODEL_ID, REVISION):
        raise ValueError("UNVERIFIED_MODEL_OR_REVISION")


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def score_report(value):
    """Missing/malformed scores are ERROR, never a fabricated numerical FAIL."""
    if not isinstance(value, dict):
        raise ValueError("INVALID_REVIEW_OBJECT")
    result = {}
    for key in (*lr.RUBRIC, "overall"):
        v = value.get(key)
        if not finite_number(v) or not 0 <= v <= 10:
            raise ValueError("INVALID_SCORE_" + key)
        result[key] = v
    result["status"] = ("PASS" if all(result[k] >= lr.PASS_ITEM for k in lr.RUBRIC)
                        and result["overall"] >= lr.PASS_OVERALL else "FAIL")
    if isinstance(value.get("issues"), list):
        result["issues"] = value["issues"][:6]
    return result


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_REVIEW_KEY")
        result[key] = value
    return result


def parse_report(text):
    """Accept a JSON object, or unambiguous exact rubric labels from the unchanged prompt."""
    try:
        return score_report(json.loads(text.strip().removeprefix("```json").removesuffix("```").strip(), object_pairs_hook=unique_object))
    except (ValueError, TypeError):
        pass
    values = {}
    for key in (*lr.RUBRIC, "overall"):
        # Count labels including invalid values; do not silently discard a contradictory score.
        labels = re.findall(r"(?im)^[ \t]*(?:[-*]|\d+[.)])?[ \t]*\*{0,2}" + re.escape(key)
                            + r"\*{0,2}[ \t]*:", text)
        if len(labels) != 1:
            raise ValueError("UNPARSEABLE_REVIEW_" + key)
        # No positional guesses, synonym mapping or choosing among repeated scores.
        matches = re.findall(r"(?im)^\s*(?:[-*]|\d+[.)])?\s*\*{0,2}" + re.escape(key)
                             + r"\*{0,2}[ \t]*:[ \t]*\*{0,2}([0-9]+(?:\.[0-9]+)?)(?:[ \t]*/[ \t]*10)?"
                             + r"\*{0,2}(?:[ \t]+[-–—][ \t]+[^\n]*)?[ \t]*$", text)
        if len(matches) != 1:
            raise ValueError("UNPARSEABLE_REVIEW_" + key)
        values[key] = float(matches[0])
    return score_report(values)


def validate_words(words):
    if not isinstance(words, list) or not words:
        raise ValueError("ASR_WORD_TIMESTAMPS_MISSING")
    previous = 0.0
    for row in words:
        if (not isinstance(row, dict) or not isinstance(row.get("word"), str) or not row["word"].strip()
                or not finite_number(row.get("start")) or not finite_number(row.get("end"))
                or not 0 <= row["start"] <= row["end"] <= CASE_SECONDS + 0.1
                or row["start"] < previous):
            raise ValueError("ASR_WORD_TIMESTAMPS_INVALID")
        previous = row["start"]
    return words


def frame_paths(path, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # A fresh per-case directory prevents stale frames being counted as coverage.
    if list(directory.iterdir()):
        raise ValueError("FRAME_DIRECTORY_NOT_EMPTY")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", str(path)], check=True, capture_output=True, text=True)
    seconds = float(probe.stdout)
    if not math.isfinite(seconds) or abs(seconds - CASE_SECONDS) > 0.2:
        raise ValueError("CASE_DURATION_NOT_180S")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", FRAME_FILTER,
                    str(directory / "%04d.png")], check=True, capture_output=True)
    frames = sorted(directory.glob("*.png"))
    if len(frames) != FRAME_COUNT:
        raise ValueError("FRAME_COVERAGE_INCOMPLETE")
    return frames


class ContextLimit(ValueError):
    def __init__(self, tokens, limit, frames):
        super().__init__("CONTEXT_TOO_LONG")
        self.details = {"input_tokens": tokens, "context_limit": limit, "frames": frames, "truncated": False}


def context_guard(input_tokens, limit, frame_count):
    if frame_count != FRAME_COUNT:
        raise ValueError("FRAME_COVERAGE_INCOMPLETE")
    if input_tokens + MAX_NEW_TOKENS > limit:
        raise ContextLimit(input_tokens, limit, frame_count)


def load_runtime(model, revision):
    validate_model(model, revision)
    import torch
    import whisper
    from PIL import Image
    from huggingface_hub import hf_hub_download
    from transformers import AutoConfig, AutoProcessor, AutoModelForImageTextToText

    # The pinned model repository declares Apache-2.0 in its README; it has no
    # standalone LICENSE file. Record that fact and the exact declaration source.
    readme = Path(hf_hub_download(model, "README.md", revision=revision, token=False))
    license_text = readme.read_text()
    if "Apache-2.0" not in license_text and "apache-2.0" not in license_text:
        raise ValueError("MODEL_LICENSE_NOT_VERIFIED")
    license_record = {"identifier": "Apache-2.0", "source_file": "README.md", "standalone_license_file": False,
                      "source_url": f"https://huggingface.co/{model}/blob/{revision}/README.md",
                      "source_sha256": hashlib.sha256(readme.read_bytes()).hexdigest(),
                      "declaration": [line for line in license_text.splitlines() if "apache-2.0" in line.lower()]}
    processor = AutoProcessor.from_pretrained(model, revision=revision, token=False, trust_remote_code=False)
    processor.image_processor.do_image_splitting = False
    processor.image_processor.size = {"longest_edge": 384}
    config = AutoConfig.from_pretrained(model, revision=revision, token=False, trust_remote_code=False)
    network = None  # Do not download/load VLM weights until the complete input fits its context.
    asr_model = whisper.load_model(ASR_MODEL, device="cpu")

    def transcribe(path):
        result = asr_model.transcribe(str(path), language="en", word_timestamps=True, fp16=False, verbose=None, temperature=0.0, task="transcribe")
        return validate_words([{k: word[k] for k in ("word", "start", "end")}
                               for segment in result["segments"] for word in segment.get("words", [])])

    def infer(frames, words, prompt):
        nonlocal network
        # The review prompt is byte-identical. All added text is timestamped input data.
        content = [{"type": "text", "text": prompt}]
        for i in range(len(frames)):
            content.extend([{"type": "text", "text": f"Frame timestamp: {i / FPS:.1f} s"}, {"type": "image"}])
        content.append({"type": "text", "text": "ASR word timestamps (data): " + json.dumps(words, ensure_ascii=False)})
        text = processor.apply_chat_template([{"role": "user", "content": content}], tokenize=False, add_generation_prompt=True)
        with ExitStack() as stack:
            images = [stack.enter_context(Image.open(frame)).convert("RGB") for frame in frames]
            inputs = processor(text=[text], images=[images], return_tensors="pt", do_image_splitting=False,
                               truncation=False, padding=False, add_special_tokens=False)
        if (int(inputs["pixel_values"].shape[1]) != len(frames)
                or int((inputs["input_ids"] == processor.image_token_id).sum()) != processor.image_seq_len * len(frames)):
            raise ValueError("FRAME_COVERAGE_INCOMPLETE")
        tokens = int(inputs["input_ids"].shape[-1])
        limit = int(config.text_config.max_position_embeddings)
        context_guard(tokens, limit, len(frames))
        if network is None:
            network = AutoModelForImageTextToText.from_pretrained(
                model, revision=revision, token=False, trust_remote_code=False, use_safetensors=True,
                dtype=torch.float32, attn_implementation="sdpa", low_cpu_mem_usage=True).to("cpu").eval()
        with torch.inference_mode():
            output = network.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
        generated = output[0, tokens:]
        if len(generated) >= MAX_NEW_TOKENS:
            raise ValueError("REVIEW_OUTPUT_TRUNCATED")
        report = parse_report(processor.decode(generated, skip_special_tokens=True))
        return report, {"input_tokens": tokens, "context_limit": limit, "frames": len(frames),
                        "image_splitting": False, "truncated": False}

    return infer, transcribe, license_record


def save(out, output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(out, indent=1, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)


def calibrate(render, work, output, title, model, revision, *, infer=None, asr=None,
              make=rc.make, frames=frame_paths, clock=time.monotonic, loader=load_runtime):
    validate_model(model, revision)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    out = {"model": model, "revision": revision, "render": Path(render).name,
           "at": datetime.now(timezone.utc).isoformat(), "timing": {"seconds_per_180s_case": None},
           "cases": {name: {"expected": expected, "verdict": "ERROR", "review": {"status": "ERROR", "error": "NOT_RUN"}}
                     for name, (_, expected, _) in rc.CASES.items()},
           "input_mode": "FRAMES_PLUS_WORD_TIMESTAMPED_ASR_NOT_NATIVE_AUDIO", "sample_fps": FPS,
           "asr": {"package": "openai-whisper==20250625", "model": ASR_MODEL, "license": "MIT",
                   "license_url": "https://github.com/openai/whisper/blob/v20250625/LICENSE",
                   "weights_sha256": "25a8566e1d0c1e2231d1c762132cd20e0f96a85d16145c3a00adf5d1ac670ead"},
           "limits": ["Calibration only; never production approval.", "No native audio reaches the visual model.",
                      "Timing is a linear projection, not a full 28-minute context/memory benchmark."]}
    save(out, output)  # Includes ERROR rows if interrupted, OOM-killed, or initialization fails.
    if infer is None or asr is None:
        try:
            infer, asr, out["license"] = loader(model, revision)
        except Exception as error:
            out["setup_error"] = type(error).__name__  # No arbitrary provider/error data in evidence or logs.
            save(out, output)
            return out
    else:
        out["test_stub"] = True  # Never hide that injected callables are synthetic evidence.
    elapsed = []
    for name, (filters, expected, _) in rc.CASES.items():
        started = clock()
        row = {"expected": expected, "verdict": "ERROR", "review": {"status": "ERROR"}}
        try:
            path = make(render, work, name, filters)
            pictures = frames(path, work / (name + "-frames"))
            if len(pictures) != FRAME_COUNT:
                raise ValueError("FRAME_COVERAGE_INCOMPLETE")
            words = validate_words(asr(path))
            result, details = infer(pictures, words, lr.review_prompt(title))
            row["review"] = score_report(result)
            row["verdict"] = row["review"]["status"]
            row["input"] = {"frames": len(pictures), "asr_words": len(words), **details}
        except Exception as error:
            code = str(error) if isinstance(error, ValueError) and re.fullmatch(r"[A-Z_]+", str(error)) else type(error).__name__
            row["review"] = {"status": "ERROR", "error": code}
            if isinstance(error, ContextLimit):
                row["input"] = error.details
        duration = clock() - started
        if not finite_number(duration) or duration <= 0:
            row["review"] = {"status": "ERROR", "error": "TIMING_INVALID"}
            row["verdict"] = "ERROR"
            duration = None
        row["wall_seconds"] = duration
        elapsed.append(duration)
        out["cases"][name] = row
        # Keep timing invalid until all seven cases complete.
        if len(elapsed) == len(rc.CASES) and all(v is not None for v in elapsed):
            out["timing"]["seconds_per_180s_case"] = sum(elapsed) / len(elapsed)
        out["timing_status"] = rc.timing_status(out)
        save(out, output)
        print(name, row["review"]["status"], flush=True)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 7:
        raise SystemExit(__doc__)
    result = calibrate(*sys.argv[1:])
    raise SystemExit(1 if any(c["review"]["status"] == "ERROR" for c in result["cases"].values()) else 0)
