# arc-01: measured native-media follow-up (2026-10-28)

Base: `84f44d939b2620442b61bbe2db6fb17aaee5e10f` (PR527 already merged).
This record adds measurements, not an audiovisual approval or a new publication.

## Existing bytes, measured again

The three local MP4s were hashed and probed with the current `clip_timing.measure`.
Each SHA-256 equals its existing entry in `production/bible/shots/arc-01-long.json`.
The content-addressed records under `evidence/shots/arc-01-long/media/` are consumed
by the existing E152 guard and by the preflight binding. Historical approvals,
speech endpoints, scores, source bytes and canonical voice references are unchanged.

| Shot | Video seconds | Audio seconds | Recorded speech end | Coverage |
| --- | ---: | ---: | ---: | --- |
| k-insight-1 | 7.291667 | 7.328 | 7.2 | Within both streams; not a new review |
| s-c2-adam | 9.416667 | 9.44 | 9.16 | Within both streams; not a new review |
| s-c4-blame | 9.416667 | 9.44 | 9.5 | `NATIVE_SPEECH_OUTSIDE_MEDIA` |

This proves an inconsistent timing claim, not that audible words were cut off.
Do not clamp the speech end, pad a missing phrase, change the approved hash or
regenerate the clip merely to clear this refusal. Inspect the exact clip and its
spoken words; a genuinely authorized reviewer must record any corrected speech
measurement through the existing review writer, preserving the prior record.

## Validation and fixture correction

The current strict plan check has no structural problems or pending rows. Its
871.5-second duration is an estimate, not a measured finished master. The pinned
Kokoro reference run completed: 123 segments / 244 sentences, 819.921333 seconds.
This is the reference TTS track, not the final native-speech mix or a video.
Voice SHA-256: `d8fbc57a623b0815bc5bb37b7818b342c18d85345ee665852ad80ed20831fdb5`;
timeline SHA-256: `b2082deeab46487631f5e7c27f925d284a89c948636e73d7ec771266fe485e06`.
Runtime pins match long-build: kokoro-onnx 0.4.9, onnxruntime 1.20.1, numpy 2.2.6,
espeakng-loader 0.2.4 and soundfile 0.13.1. Source and model hashes passed `prepare`.

The canonical command `episode_build.py preflight PLAN --voice ... --refs --write`
returned exit 1 / BLOCKED. The recorded speech/media inconsistency stopped layout;
the report correctly leaves measured final layout null and request validation not
run. Fifteen setup probes remain required, and no long review-registry row is open.
The report has no stale binding parts. `verify-preflight` returns
`PREFLIGHT_NOT_PASS`, not the previous stale-report error. Report SHA-256:
`4c178833bab69e705df53ab6acd59836dde5d328f0f31e41acd2084b006336d5`.

E210: introducing genuine measurements revealed five tests in two suites reading
mutable production approvals while supplying synthetic durations. Their predictions
now use an explicit empty approval fixture; their duration, Keeper-share, request,
queue and refusal assertions are retained. The new isolation test failed before
the fixture fix. The E152 synthetic media test still checks rejection of speech
beyond measured video/audio and preservation of the original approval. A direct
call on the real arc-01 inputs still refuses `s-c4-blame`.

The initial 83-suite run passed 81 and failed only those two coupled suites. The
focused corrected long-preflight suite passed 24 tests (one existing skip), the
cold-open test passed, E152 MediaTiming passed and the registry passed 13 tests.
Final local run: all 83 canonical suites passed (1,334 reported tests, including
the existing skipped case), 64.86 seconds in the existing validation venv. No test
or production code changed after that run. Remote CI and head verification remain
required before integration.
No production-code, frozen QA, reviewer allowlist, rubric or score-floor change.

Manual diff review: only measured records, their blocked preflight, bounded test
fixtures and this continuity record are changed. No secret, dispatch, identity or
approval path is added; no assertion or QA threshold is removed. No unavailable
review plugin is claimed. The original approval JSON and voice registry are intact.

## Next transition

Integrate this evidence only after green CI and read-back. Reconcile the native
timing refusal at the speech-review stage, then repeat only the affected
layout/request checks using preserved voice inputs where valid. A clean preflight
does not replace matching approved sources, final QA, genuine audiovisual review,
or publication/read-back. No Pavo/FLUX submission, heartbeat recovery, render or
upload was initiated for this measurement follow-up.
