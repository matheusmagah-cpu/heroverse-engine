#!/usr/bin/env python3
"""Check that a talking clip (the Keeper, Pavo audio-input mode) says OUR narration line, in sync (owner, 2026-10-26:
"sincronização 100%").

Two measures, both on the delivered file:
  audio   - the clip's soundtrack against the narration WAV we sent: RMS envelopes (40 ms hops) cross-correlated;
            the clip must carry our line (correlation >= AUDIO_CORR_MIN) with no offset (|lag| <= LAG_MAX_MS).
  mouth   - the lip opening (inner-lip landmarks 13/14 over the face height, MediaPipe Face Landmarker, model pinned
            by sha256) against the clip's own speech envelope: the lips open with the voice (correlation >=
            MOUTH_CORR_MIN at a lag within +-LAG_MAX_MS), open wider while speaking than in pauses, and the face is
            found in most frames. (An OpenCV Haar mouth-motion measure was tried first: the hood and beard hid the
            face in 70 % of the frames, so it could not judge.)
Calibration 2026-10-26 (evidence/pavo/20261026/keeper): our Kokoro line sent as Pavo input audio came back with
audio corr 0.89 at 0 ms and lips corr 0.52 at 0 ms, open 1.98x more while speaking; a clip with Pavo's own voice
had lips at 208 ms (out of sync) and audio corr 0.14 against our line.
A clip that fails is not composed; it is regenerated (PROMPT_GUIDE "Built for 9.5").

usage: lipsync_check.py CLIP.mp4 LINE.wav FACE_LANDMARKER.task   prints one JSON line; exit 1 on any failure
       lipsync_check.py --faces CLIP.mp4 FACE_LANDMARKER.task    God's voice-over shot: sampled frames, any face found
                                                                  flags GOD_SHOT_FACE (exit 1)
       lipsync_check.py --still-mouth CLIP.mp4 FACE_LANDMARKER.task
                                                 a voice-over Keeper clip (plan B): the same lip opening on every
                                                 frame; MOUTH_TALKING when any ~1 s moves fast, MOUTH_NOT_CLOSED
                                                 when any ~1 s after the settle is open, FACE_NOT_FOUND under 80 %
                                                 of frames (exit 1)
(model: https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task)
"""
import json
import subprocess
import sys

import numpy as np

HOP_S = 0.04
AUDIO_CORR_MIN = 0.85
MOUTH_CORR_MIN = 0.45
SPEAK_TO_PAUSE_MIN = 1.5
FACE_FRAMES_MIN = 0.8
LAG_MAX_MS = 84            # two frames at 24 fps
FACE_SAMPLE_EVERY = 4      # --faces: every 4th frame (6 a second at 24 fps)
# Plan B (owner, 2026-10-26): a voice-over Keeper clip shows no talking mouth and a mouth confirmed closed. Measures
# of the inner-lip opening over the face height on the frames where the face is found (calibration 2026-10-26,
# mediapipe 0.10.35, this model, evidence/pavo/20261026/keeper-vo/calibration.json; the per-frame series of the 42
# talking clips - the Keeper's 40 direct clips of PR #419 and his calibration clip, passing and failing the lips alike,
# and the genesis-06 narrator - and the 14 closed-mouth Keeper clips are kept in opening-series.json and replayed by
# test_lipsync_check):
# - window motion: the largest mean frame-to-frame change over any STILL_MOUTH_WINDOW_S (at least half of it with the
#   face), so a few seconds of talking inside a long clip are not averaged away. Talking 0.0091-0.026, closed
#   0.0005-0.0043 (the highest in the first seconds, while a mouth settles): MOUTH_TALKING over 0.0063, near the
#   geometric middle. The whole-clip rule stays as well (spread > 0.016 and mean motion > 0.0032; talking spread
#   0.056-0.125, mean 0.0041-0.018; closed mean <= 0.0025).
# - closed opening: the most open STILL_MOUTH_WINDOW_S (its median) after STILL_MOUTH_SETTLE_S. The talking reference
#   starts with an open mouth that closes within ~2.5 s (clip 5, conversation 373100393016087168), so the settle is
#   allowed explicitly and no longer. Talking 0.039-0.084, closed 0.0011-0.0046: MOUTH_NOT_CLOSED over 0.013, near the
#   geometric middle; nothing measurable after the settle is never a confirmed closed mouth.
STILL_MOUTH_RANGE_MAX = 0.016
STILL_MOUTH_MOTION_MAX = 0.0032
STILL_MOUTH_WINDOW_S = 1.0
STILL_MOUTH_WINDOW_MOTION_MAX = 0.0063
STILL_MOUTH_SETTLE_S = 2.5
STILL_MOUTH_CLOSED_MAX = 0.013
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"


def pcm(path, rate=16000):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(rate),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0, rate


def envelope(samples, rate, hop_s=HOP_S):
    hop = int(rate * hop_s)
    n = len(samples) // hop
    if n == 0:
        return np.zeros(0)
    return np.sqrt((samples[: n * hop].reshape(n, hop) ** 2).mean(axis=1))


def best_lag(a, b, max_lag):
    """Pearson correlation of a against b shifted by -max_lag..max_lag steps; (corr, lag) of the best."""
    best = (-1.0, 0)
    for lag in range(-max_lag, max_lag + 1):
        x = a[max(lag, 0): len(a) + min(lag, 0)]
        y = b[max(-lag, 0): len(b) + min(-lag, 0)]
        n = min(len(x), len(y))
        if n < 10:
            continue
        x, y = x[:n], y[:n]
        if x.std() == 0 or y.std() == 0:
            continue
        c = float(np.corrcoef(x, y)[0, 1])
        if c > best[0]:
            best = (c, lag)
    return best


def audio_match(clip, line):
    a, rate = pcm(clip)
    b, _ = pcm(line)
    ea, eb = envelope(a, rate), envelope(b, rate)
    corr, lag = best_lag(ea, eb, int(LAG_MAX_MS * 3 / 1000 / HOP_S))
    return {"corr": round(corr, 3), "lag_ms": int(lag * HOP_S * 1000)}, ea


def lip_opening(clip, model):
    """Inner-lip gap over face height per frame (NaN where no face), the frame rate and the share of frames with a face."""
    import hashlib
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    if hashlib.sha256(open(model, "rb").read()).hexdigest() != MODEL_SHA256:
        raise SystemExit("FACE_MODEL_HASH_MISMATCH")
    options = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=model),
                                           running_mode=vision.RunningMode.VIDEO, num_faces=1)
    landmarker = vision.FaceLandmarker.create_from_options(options)
    cap = cv2.VideoCapture(clip)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    opening, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        found = landmarker.detect_for_video(image, int(i * 1000 / fps)).face_landmarks
        i += 1
        if found:
            p = found[0]
            opening.append(abs(p[14].y - p[13].y) / max(abs(p[152].y - p[10].y), 1e-6))
        else:
            opening.append(np.nan)
    cap.release()
    opening = np.array(opening)
    share = float((~np.isnan(opening)).mean()) if len(opening) else 0.0
    return opening, fps, share


def mouth_sync(opening, fps, clip_env):
    """Correlation and lag of the lip opening against the speech envelope, and how much wider the lips open while
    speaking than in pauses."""
    filled = np.where(np.isnan(opening), np.nanmean(opening) if (~np.isnan(opening)).any() else 0.0, opening)
    t = np.arange(len(filled)) / fps
    speech = np.interp(t, np.arange(len(clip_env)) * HOP_S, clip_env) if len(clip_env) else np.zeros(len(filled))
    corr, lag = best_lag(filled, speech, int(LAG_MAX_MS * 3 / 1000 * fps))
    speaking = speech > (0.25 * speech.max() if speech.max() > 0 else 1)
    ratio = (filled[speaking].mean() / max(filled[~speaking].mean(), 1e-6)) if speaking.any() and (~speaking).any() else 0.0
    return round(corr, 3), int(round(lag / fps * 1000)), round(float(ratio), 2)


def landmarker(model, mode):
    import hashlib
    from mediapipe.tasks.python import BaseOptions, vision
    if hashlib.sha256(open(model, "rb").read()).hexdigest() != MODEL_SHA256:
        raise SystemExit("FACE_MODEL_HASH_MISMATCH")
    options = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=model), running_mode=mode,
                                           num_faces=1)
    return vision.FaceLandmarker.create_from_options(options)


def faces(clip, model, every=FACE_SAMPLE_EVERY):
    """God's voice-over shot shows no person (owner, 2026-10-26): every `every`-th frame through the same pinned face
    landmarker; any face found flags GOD_SHOT_FACE and the clip is regenerated. Calibration 2026-10-26 (mediapipe
    0.10.35, this model): the Genesis 6 Pavo clips storm, sunbeams and tents 0 faces in 40-48 sampled frames; the
    Keeper's clip 30/44 and the Adam-and-Eve clip 21/48."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    lm = landmarker(model, vision.RunningMode.IMAGE)
    cap = cv2.VideoCapture(clip)
    sampled, found, at, i = 0, 0, [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % every == 0:
            sampled += 1
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if lm.detect(image).face_landmarks:
                found += 1
                at.append(i)
        i += 1
    cap.release()
    lm.close()
    return face_verdict(clip, sampled, found, at)


def face_verdict(clip, sampled, found, at):
    flags = ["GOD_SHOT_FACE"] if found else []
    if not sampled:
        flags.append("NO_FRAMES")
    return {"clip": clip, "frames_sampled": sampled, "faces_found": found, "face_frames": at[:20], "flags": flags}


def _windows(values, width):
    """Each run of `width` values with at least half of them measured (not NaN): the measured values."""
    for k in range(0, len(values) - width + 1):
        seg = values[k:k + width]
        ok = seg[~np.isnan(seg)]
        if len(ok) >= width / 2:
            yield ok


def still_mouth_verdict(opening, share, fps=24.0):
    """A voice-over Keeper clip's mouth (plan B):
    MOUTH_TALKING when the mean lip motion over any STILL_MOUTH_WINDOW_S exceeds STILL_MOUTH_WINDOW_MOTION_MAX, or the
    whole clip is wide and fast (p95 - p5 > STILL_MOUTH_RANGE_MAX and mean motion > STILL_MOUTH_MOTION_MAX);
    MOUTH_NOT_CLOSED when the median opening of any STILL_MOUTH_WINDOW_S after STILL_MOUTH_SETTLE_S exceeds
    STILL_MOUTH_CLOSED_MAX, or nothing after the settle can be measured; MOUTH_UNMEASURED when no window of motion can;
    FACE_NOT_FOUND under FACE_FRAMES_MIN of the frames (as for the lips check); NO_FRAMES for an empty clip. Frames
    without a face are left out, never counted as a closed mouth."""
    opening = np.asarray(opening, dtype=float)
    width = max(2, int(round(STILL_MOUTH_WINDOW_S * fps)))
    seen = opening[~np.isnan(opening)] if len(opening) else opening
    spread = float(np.percentile(seen, 95) - np.percentile(seen, 5)) if len(seen) else None
    diff = np.abs(np.diff(opening)) if len(opening) > 1 else np.zeros(0)
    measured = diff[~np.isnan(diff)]
    motion = float(measured.mean()) if len(measured) else None
    window_motion = max((float(w.mean()) for w in _windows(diff, width)), default=None)
    after = opening[int(round(STILL_MOUTH_SETTLE_S * fps)):]
    closed_opening = max((float(np.median(w)) for w in _windows(after, width)), default=None)
    flags = []
    if not len(opening):
        flags.append("NO_FRAMES")
    if share < FACE_FRAMES_MIN:
        flags.append("FACE_NOT_FOUND")
    whole = (spread is not None and spread > STILL_MOUTH_RANGE_MAX and motion is not None
             and motion > STILL_MOUTH_MOTION_MAX)
    if whole or (window_motion is not None and window_motion > STILL_MOUTH_WINDOW_MOTION_MAX):
        flags.append("MOUTH_TALKING")
    elif window_motion is None:
        flags.append("MOUTH_UNMEASURED")
    if closed_opening is None or closed_opening > STILL_MOUTH_CLOSED_MAX:
        flags.append("MOUTH_NOT_CLOSED")
    r4 = lambda x, n: None if x is None else round(x, n)  # noqa: E731
    return {"opening_range": r4(spread, 4), "opening_motion": r4(motion, 5), "window_motion": r4(window_motion, 5),
            "closed_opening": r4(closed_opening, 5), "face_frames": round(float(share), 2),
            "frames": int(len(opening)), "flags": flags}


def still_mouth(clip, model):
    opening, fps, share = lip_opening(clip, model)
    return dict({"clip": clip}, **still_mouth_verdict(opening, share, fps))


def verdict(audio, mouth):
    flags = []
    if audio["corr"] < AUDIO_CORR_MIN:
        flags.append("AUDIO_NOT_OUR_LINE")
    if abs(audio["lag_ms"]) > LAG_MAX_MS:
        flags.append("AUDIO_OFFSET")
    if mouth["face_frames"] < FACE_FRAMES_MIN:
        flags.append("FACE_NOT_FOUND")
    if mouth["corr"] < MOUTH_CORR_MIN or abs(mouth["lag_ms"]) > LAG_MAX_MS:
        flags.append("MOUTH_NOT_IN_SYNC")
    if mouth["speak_to_pause"] < SPEAK_TO_PAUSE_MIN:
        flags.append("MOUTH_OPEN_IN_PAUSES")
    return flags


def check(clip, line, model):
    audio, clip_env = audio_match(clip, line)
    opening, fps, share = lip_opening(clip, model)
    corr, lag, ratio = mouth_sync(opening, fps, clip_env)
    mouth = {"corr": corr, "lag_ms": lag, "speak_to_pause": ratio, "face_frames": round(share, 2)}
    return {"clip": clip, "line": line, "audio": audio, "mouth": mouth, "flags": verdict(audio, mouth)}


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--still-mouth":
        result = still_mouth(sys.argv[2], sys.argv[3])
        print(json.dumps(result))
        sys.exit(1 if result["flags"] else 0)
    if len(sys.argv) == 4 and sys.argv[1] == "--faces":
        result = faces(sys.argv[2], sys.argv[3])
        print(json.dumps(result))
        sys.exit(1 if result["flags"] else 0)
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    result = check(sys.argv[1], sys.argv[2], sys.argv[3])
    print(json.dumps(result))
    sys.exit(1 if result["flags"] else 0)
