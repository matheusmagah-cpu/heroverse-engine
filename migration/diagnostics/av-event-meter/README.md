# Blind AV event meter v2 (deterministic, offline)

`av_event_meter.py MEDIA` measures, without any model or network call:

- **Audio onsets**: 1 ms RMS windows (maximum over channels, no downmix). A window is an onset candidate when it is ≥ 12 dB above the median 10 ms level of the trailing 20–210 ms (local novelty) and ≥ −50 dBFS; candidates closer than 30 ms are merged; the onset is then refined to the sample. This finds hits inside continuous music, where a whole-file floor rule fails (v1: 1/5, v2: 5/5 in the test). Also reports `exact_digital_silence` when every decoded sample is zero.
- **Visual change onsets**: mean of the top-decile absolute luma differences between consecutive frames on a 64×48 area-averaged gray proxy; threshold `max(6, median + 8·MAD)` of the file; changes within 0.2 s are merged. Onset time is the packet PTS of the first changed frame.
- **Sync (consensus)**: among all audio-minus-video differences within ±1 s, the offset chosen is the one that the most picture changes support one-to-one (an audio onset within one frame of picture + offset). Nearest-neighbour pairing is not used, because real content has many audio onsets (music notes) near each picture change; the first real-opening run showed that failure. The verdict is `AMBIGUOUS` when a clearly different offset has equal support, or when fewer than 3 pairs exist and a paired picture change has other audio onsets within ±1 s; with fewer than 3 pairs otherwise it is `LOW_SUPPORT` (offset reported, no sync verdict). Otherwise it uses the ITU-R BT.1359 detectability window (sound lead ≤ 45 ms, lag ≤ 125 ms).

Every onset carries its `resolution_seconds` (one audio sample; one video frame interval, since a visual change is only known to lie between two frames). Media is streamed in bounded chunks with numpy, and audio and video are measured in parallel: about 2.2 s for 40 s of 1080p30 stereo, of which ffmpeg decoding alone takes 1.7 s.

The meter receives only the media path. It never reads answers or manifests.

## Why

Every model run on the synthetic controls failed on **count and timing** (run 42: 4 flashes/4 beeps/simultaneous; run 45: 4 beeps at 1/2/3/4 s). Those properties are measurable from the signal. This meter decides them deterministically. Models stay limited to semantic labels, with abstention, and are never the sole authority for count, time or sync.

## Qualification

- `criteria.json` was frozen and committed **before** the meter existed.
- `qualify_controls.py OUT.json` rebuilds c01–c05 with the hash-pinned recipe, requires SHA-256 identity with the frozen stimuli, measures each file alone in an empty directory through an isolated interpreter, and compares against the recipe constants: **5/5 PASS** (`qualification.json`).
- `test_av_event_meter.py`: 11 offline tests on synthetic media unlike the controls (different counts, times, levels, noise, fps, sample rates and channel layouts). All pass with the same tolerances.
- Mutation check: deliberately broken parameters are caught by the qualifier and/or the tests.
- `qualify_injection.py OUT.json MEDIA...` (CI on the five real 0–40 s openings from the private release): inserts 6 tone bursts and 6 full-frame flashes at seeded times away from natural events, with a known +40 ms offset, re-encodes, then measures blind. Pass rule, frozen before any real run: 6/6 audio, 6/6 video, offset within one frame, zero spurious events. This measures detection on real backgrounds, **not** the correctness of the natural events.

## Limits (not covered, not claimed)

- It does not identify speech, music, effects or visual content. It has no semantic understanding.
- Continuous music, dense speech, camera motion and gradual fades are not countable events. Natural-event accuracy on real content needs a human-labelled reference. Injection measures only detection of known inserted events on real backgrounds.
- An event less than 12 dB above its trailing local level is not counted (tested, documented). Events in the first 10 ms of a file are not detectable.
- Not integrated into the runtime. It changes no gate, scheduler, production or publication state.
