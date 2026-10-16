# One c01 direct-audio diagnostic

Prepared against `daa087c85019518b7cc2fa1ada0310dd916e6843`. This directory's
code, documentation and derivation proof are operator-only. Only the exact WAV
and `evaluator-prompt.txt` enter the model request. No expected answer, timing
measurement, script, proof, video, or earlier model response is sent.

## Scope and manual entry

Use the existing `official-evidence.yml` manual entry on main, first attempt
only: `av_synthetic_c01=true`, `checkpoint_only=true`, all other nine options
false. The c01 option is explicitly labelled AUDIO_ONLY in this revision.
Scheduled/default paths and the existing concurrency group are unchanged.
No collector, public-source admission, cancelled recovery, or production gate
is enabled by this diagnostic.

The existing runtime policy, original-project fingerprint check, private-repo
boundary and original observer ledger remain mandatory. The unchanged policy's
project observation is `2026-10-16T01:35:25Z`, with a 24-hour maximum age; source
delivery provenance is also retained. Documentation is in
`rest-contract-20261016.json` and the existing Flash-Lite policy evidence.
No actual credential is read during offline preparation or tests.

One `gemini-3.5-flash-lite:generateContent` attempt uses only a user content with
`inlineData` (`audio/wav`, executor-memory base64) and the frozen neutral text.
Generation configuration remains candidateCount 1 / maxOutputTokens 4096.
There are no tools, grounding, FileData, video fields, audio-output request, or
system instructions. The wall deadline is 110 seconds. HTTP 429/503, a timeout,
and provider rejection are terminal; there is no automatic retry or fallback.

Before that call, the original manager durably reserves 6 seconds, capped at
28800 seconds per UTC day. Google RPD resets on Pacific time, independently.
The stable identity includes modality, WAV/parent-media hashes, model, prompt
hash and configuration; it contains no run date or ephemeral asset identifier.
The model receipt is checkpointed using the original manager. Terminal replay
does not call the provider or debit again. COMPLETED is accounting status only.
All quality/production/publication permissions stay false.

## Exact media derivation

`build_audio.py` regenerates the original MP4 through the preserved helper and
requires byte identity before decoding its real AAC audio track. It does not
create a clean substitute tone track. The verified source is 19083 bytes,
SHA256 `5562d675416107eb9ec70643edd43e5375b85aa74051730f1d357a88d34e79df`.

The original decode yields 288768 mono float32 samples at 48000 Hz. Only the
last 768 samples, proved exactly zero, are omitted. Samples 0 through 287999
retain their positions. Float32 SHA256 before trimming is
`5efda979496abfda7a03ae21f255319f24524f58b4726f21666fa905bf5beae0`;
the retained float32 bytes hash to
`02c73b990852858d14ca6a29be9dcbeb07f049f2fab908743117c6991d2e162e`.

The six-second WAV has a canonical 44-byte header, mono signed PCM16 LE at
48000 Hz, 288000 samples, 576044 total bytes. Float-to-PCM16 conversion is
nearest/ties-to-even with zero clipped samples and maximum absolute error
1/65536 of full scale. It is not bit-exact preservation of float samples.
There is no resampling, normalization, dither, or time shift. Operational
1-ms RMS event intervals are unchanged by the quantization.

- PCM16 SHA256: `6434c16155d75c81933f30efabb4aea450718027f42db376119287b8dcf7f0f4`
- WAV SHA256: `ed00a94f25785cd763f1dc23f33447c317d0bea9cf8f0a11232d8d00f619a45b`
- Prompt SHA256: `11a0e3ef81950db83c3a6229a8a48e0b57865b30e4f2f1c5494eb48074f8c30d`

Media stays in `synthetic-audio-control-output/` on the runner. It is never
committed, logged, sent through chat/MCP, or included in Actions artifacts.
Only its textual `proof.json` is included alongside the ordinary evidence
artifact. Provider media or credential echoes are rejected before persistence.
Build/hash failure stops before any provider action.

## Frozen operator-only audio rubric

This is a new direct-audio diagnostic. It does not change the earlier
audiovisual protocol or its physical timing tolerance of 0.015 seconds.
The new prompt asks description, count, and approximate onset times without
giving the expected values. Adjudication occurs offline after preserving the
literal answer and usage, and is explicitly AI review unless a human reviews it.

- Detection/count/description: three separated short tones or beeps.
- Timing is scored separately, exploratorily: each reported onset within
  0.25 seconds of the measured 1.500, 3.501 and 5.501 seconds. Missing numeric
  timestamps do not prevent assessing count and description.
- Sending failure or an empty answer: INCONCLUSIVE.
- A wrong count or incompatible description: that capability was not demonstrated.
- A positive AUDIO count in usage supports provider input-modality accounting;
  it does not prove correct perception. Missing AUDIO telemetry is inconclusive.
- A partial success does not establish audiovisual synchronization, general
  semantic competence, production readiness, or human approval. No prompt is
  replayed to teach the expected answer.

## Preserved prior result

Run 38839955057 (#42), attempt 1, finished successfully as infrastructure but
answered four flashes/four beeps/simultaneous, versus three/three/delayed audio.
Its provider response, receipt and 6-second debit remain untouched, as does the
earlier 3.8 HIGH_DEMAND 503 debit. Final run42 HEAD was
`daa087c85019518b7cc2fa1ada0310dd916e6843`. Literal receipt:
`migration/evidence/public-av-7e431b2811680333a574d970c68b74d073421105b805234d7721be3af9fe04ba.json`.
Its separate AI adjudication is in
`migration/evidence/av-evaluator-controls-20261016/operator-only/api-c01-lite-adjudication-38839955057.json`.
The video response's VIDEO-without-AUDIO usage detail does not establish that
audio was discarded; this diagnostic tests direct audio as a separate input.

## Offline checks

From a clean checkout with FFmpeg/ffprobe available:

    python3 migration/diagnostics/synthetic-audio-c01/build_audio.py synthetic-audio-control-output
    python3 -m unittest discover -s migration/runtime_bridge -p 'test_*.py'

Tests use a fake key, mock HTTP and checkpoint commits, and temporary databases.
Files counterfactual tests reconstruct only the verified pre-run42 snapshot in
memory (whole-file SHA256 asserted), while audio tests retain both real AV
receipts and debits. Neither test fixture alters the repository ledger.

The NEW-call counterfactual suite is bound to this pre-diagnostic snapshot, not
a continuous-CI fixture: after a new AUDIO_ONLY ledger row is checkpointed, its
historical whole-file assertion must be adapted to an independent historical
fixture before reuse. Do not remove production ledger entries to make tests pass.
