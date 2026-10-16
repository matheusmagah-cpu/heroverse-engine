"""Deterministic PCM16 energy windows. No model, network, decoder or approval.

Public whole-WAV entry point: aggregate.measure_audio_activity. This lower-level
function consumes validated interleaved PCM bytes. Integer sum-of-squares and an
exact decimal threshold avoid floating-point threshold rounding. Channels are
never downmixed. A qualifying window is operational activity, not a sound event.
"""
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import struct


VERSION = "pcm16-window-rms-activity-v1"


def _append_window(intervals, start, end):
    if intervals and intervals[-1][1] == start:
        intervals[-1][1] = end
    else:
        intervals.append([start, end])


def _summary(intervals):
    return {"active_intervals_frames": intervals,
            "active_interval_count": len(intervals),
            "active_frames": sum(end - start for start, end in intervals)}


def measure_pcm16_activity(pcm, *, channels, sample_rate,
                           window_frames=48, rms_threshold="0.02"):
    """Measure nonoverlapping windows, including a final unpadded short window.

    Integer PCM values are normalized by 32768. For each channel, a window is
    active iff mean(sample**2) >= (32768 * threshold)**2. The result includes each
    channel and the union of active windows across channels. It does not merge
    gaps, apply minimum durations or assert silence when no window qualifies.
    """
    if type(pcm) is not bytes or not pcm:
        raise ValueError("Nonempty PCM bytes required")
    if type(channels) is not int or channels not in (1, 2):
        raise ValueError("Audio activity supports only mono or stereo")
    if type(sample_rate) is not int or sample_rate <= 0:
        raise ValueError("Positive integer sample rate required")
    if type(window_frames) is not int or window_frames <= 0:
        raise ValueError("Positive integer window_frames required")
    if type(rms_threshold) is not str or len(rms_threshold) > 64:
        raise ValueError("Finite decimal threshold string required")
    try:
        threshold = Decimal(rms_threshold)
    except InvalidOperation:
        raise ValueError("Finite decimal threshold string required") from None
    if not threshold.is_finite() or not Decimal(0) < threshold <= Decimal(1):
        raise ValueError("RMS threshold must be greater than zero and at most one")
    # Bound decimal complexity; this is a small offline instrument, not arbitrary
    # precision input processing. This also prevents extreme exponent allocation.
    if threshold.as_tuple().exponent < -18 or threshold.as_tuple().exponent > 0:
        raise ValueError("RMS threshold supports at most 18 decimal places")
    ratio = Fraction(threshold)
    threshold_text = format(threshold, "f")
    if "." in threshold_text:
        threshold_text = threshold_text.rstrip("0").rstrip(".")
    squared_denominator = ratio.denominator ** 2
    squared_scaled_numerator = (ratio.numerator * 32768) ** 2
    align = channels * 2
    if len(pcm) % align:
        raise ValueError("Incomplete PCM16 frame")
    frames = len(pcm) // align
    channel_intervals = [[] for _ in range(channels)]
    union = []
    for start in range(0, frames, window_frames):
        end = min(frames, start + window_frames)
        sums = [0] * channels
        for frame in struct.iter_unpack("<" + "h" * channels, pcm[start * align:end * align]):
            for channel, value in enumerate(frame):
                sums[channel] += value * value
        flags = [total * squared_denominator >= (end - start) * squared_scaled_numerator
                 for total in sums]
        for channel, active in enumerate(flags):
            if active:
                _append_window(channel_intervals[channel], start, end)
        if any(flags):
            _append_window(union, start, end)
    return {
        "version": VERSION,
        "scope": "WHOLE_ARTIFACT_OPERATIONAL_ENERGY",
        "sample_format": "SIGNED_PCM16_LITTLE_ENDIAN",
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "frames": frames,
        "parameters": {
            "window_frames": window_frames,
            "hop_frames": window_frames,
            "rms_threshold_full_scale": threshold_text,
            "comparison": "MEAN_SQUARE_GREATER_THAN_OR_EQUAL_THRESHOLD_SQUARED",
            "sample_scale": 32768,
            "channel_policy": "PER_CHANNEL_THEN_ANY_CHANNEL_UNION_NO_DOWNMIX",
            "partial_final_window": "ACTUAL_FRAME_COUNT_NO_PADDING",
            "time_basis": "HALF_OPEN_PCM_FRAME_INDICES_FROM_ARTIFACT_START",
        },
        "per_channel": [dict(channel_index=i, **_summary(intervals))
                        for i, intervals in enumerate(channel_intervals)],
        "any_channel": _summary(union),
    }
