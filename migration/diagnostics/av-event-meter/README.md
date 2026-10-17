# Blind AV event meter (deterministic, offline)

`av_event_meter.py MEDIA` measures, without any model or network call:

- **Audio onsets**: 1 ms RMS windows (maximum over channels, no downmix), detected at 20 dB above the file's own 20th-percentile floor and never below −50 dBFS; events closer than 30 ms are merged. Also reports `exact_digital_silence` when every decoded sample is zero.
- **Visual change onsets**: mean of the top-decile absolute luma differences between consecutive frames on a 64×48 area-averaged gray proxy; threshold `max(6, median + 8·MAD)` of the file; changes within 0.2 s are merged. Onset time is the packet PTS of the first changed frame.
- **Sync**: each audio onset is paired with the nearest visual onset within ±1 s; the median audio-minus-video offset is reported, and the verdict uses the ITU-R BT.1359 detectability window (sound lead ≤ 45 ms, lag ≤ 125 ms).

The meter receives only the media path. It never reads answers or manifests.

## Why

Every model run on the synthetic controls failed on **count and timing** (run 42: 4 flashes/4 beeps/simultaneous; run 45: 4 beeps at 1/2/3/4 s). Those properties are measurable from the signal. This meter decides them deterministically. Models stay limited to semantic labels, with abstention, and are never the sole authority for count, time or sync.

## Qualification

- `criteria.json` was frozen and committed **before** the meter existed.
- `qualify_controls.py OUT.json` rebuilds c01–c05 with the hash-pinned recipe, requires SHA-256 identity with the frozen stimuli, measures each file alone in an empty directory through an isolated interpreter, and compares against the recipe constants: **5/5 PASS** (`qualification.json`).
- `test_av_event_meter.py`: 6 offline tests on synthetic media unlike the controls (different counts, times, levels, noise, fps, sample rates and channel layouts). All pass with the same tolerances.
- Mutation check: deliberately broken parameters are caught by the qualifier and/or the tests.

## Limits (not covered, not claimed)

- It does not identify speech, music, effects or visual content. It has no semantic understanding.
- Continuous music, dense speech, camera motion and gradual fades are not countable events. Real-content accuracy is **not yet measured**: the next step is the five preserved 0–40 s openings, with a human-labelled reference.
- An event less than 20 dB above the file's floor is not counted (tested, documented).
- Not integrated into the runtime. It changes no gate, scheduler, production or publication state.
