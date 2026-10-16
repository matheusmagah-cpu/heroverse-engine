# One c01 direct-audio diagnostic

Wire-enum and safe-error proposal prepared against `02e728191f34e4b5e058a07ff36a87c7d59128aa`. This directory's
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
Generation configuration retains candidateCount 1 / maxOutputTokens 4096 and
adds only `responseFormat.text` with `mimeType: APPLICATION_JSON` and the JSON
schema embedded in `synthetic_audio_control.py`. Do not combine this current
REST format with legacy responseMimeType, responseSchema or responseJsonSchema.
The exact 227-byte prompt, WAV, model, endpoint and transport remain unchanged.
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

## Structured-output hypothesis and acceptance boundary

This experiment changes one factor: the output-format contract. It asks whether
requiring explicit fields resolves the earlier omission of count/onsets; it does
not presume that formatting improves perception. No expected count, timestamps,
duration, prior response, or operator rubric is in the schema or request text.
Removing `responseFormat` reconstructs the previous request's exact wire hash:
`102ee2f052d18440d29e00b2b7e4a9f35714a40593a4809ade5013b6024cbcf5`.

Required fields are status, count, events and uncertainty. Each event requires
label, start_seconds and end_seconds. Null is explicit abstention for that datum,
never zero or an omitted field. No coercion, rounding, sorting or repair occurs.
The parser rejects malformed/trailing JSON, duplicate keys, unexpected/missing
fields, wrong types including booleans as numbers, nonfinite values, timestamps
outside the known local duration, reversed times and reversed event ordering.

- `complete` requires count equal to event-array length, known nonempty labels
  and known onsets. A null end is allowed only with an uncertainty explanation;
  end precision was not part of the frozen scoring criterion.
- `partial` or `unknown` requires an uncertainty explanation and is ABSTAINED.
- Valid complete output is COMPLETE_UNREVIEWED, not a quality verdict. A wrong
  count or duplicated onsets can satisfy the shape while still failing accuracy.
- Invalid output is a terminal contract failure. Preserve its literal response,
  provider JSON and available usage before recording that failure. Do not retry.
- A green workflow with ABSTAINED means technically valid execution and preserved
  evidence only. It does not mean that the requested ability was demonstrated.
- `precision_verdict` remains NOT_ADJUDICATED; review remains NOT_REVIEWED and all
  quality, production and publication permissions remain false in every case.

Adjudication remains separate and uses the unchanged operator-only rubric below.
Count/onset results must not be presented as audiovisual-sync or general semantic
qualification. End values are checked for technical coherence only, not scored
for perceptual accuracy. No post-result adjustment of rubric is permitted.

The stable request identity includes the entire output contract, creating one
new identity while preserving all four earlier receipts and their 24 seconds.
Replay of this new identity must reuse its terminal receipt without a new call.
This proposal does not itself dispatch a workflow or authorize production.

## Wire enum correction after run44 and bounded error evidence

Run 38853125519 (#44) made one call and received HTTP_400_INVALID_ARGUMENT.
No evaluator response, modelVersion or usage was returned to the receipt, so
contract and precision stayed NOT_EVALUATED / NOT_ADJUDICATED. Its receipt and
six-second debit are immutable and mandatory prior history:
`migration/evidence/public-av-bf7925b517b92159cf196ad25f71e98bec81f8e695c47bf9b9098b02ed80b41a.json`.
The existing transport discarded the error body; its lost details cannot be
reconstructed. This was request rejection, not a perceptual score.

The official tutorial used `application/json`, but Discovery v1beta revision
20261015 and the detailed TextResponseFormat API reference define the output
field as enum `APPLICATION_JSON`. The small public capture is
`gemini-v1beta-text-response-format-20261016.json`. Only that output literal
changes on the wire. Input inlineData.mimeType stays `audio/wav`; schema, prompt,
WAV, model, candidate count, output limit, endpoint and transport destination stay
unchanged. The mismatch proves a published-wire-contract defect, not that it was
the unique cause of HTTP 400 or that the corrected request will be accepted.

Error observability is a separate local change, not an excuse to replay the
rejected payload. The shared transport reads at most 8193 bytes to detect an
8192-byte bound. Malformed/oversized error bodies retain metadata only. Parsed
errors retain only a known status, scrubbed message (768 UTF-8 bytes maximum),
and up to four BadRequest field violations (field 128 bytes, description 384
bytes), with a 4096-byte total diagnostic cap. Unknown detail types/metadata,
headers, raw body and error/request URLs are never retained. Known credential
encodings, token/base64-like strings and URLs are conservatively redacted before
truncation. Empty/non-string fake keys do not disable other redaction.

The HTTP error code remains compatible. ProviderFailure carries the sanitized
representation; this patch adds its persistence only to the direct-audio receipt.
Other adapters retain their previous receipt behavior. Diagnostics do not alter
request identity, model verdicts, retry behavior, quotas or authorization.

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

Run 38842979507 (#43) returned only a short sound caption, without count/onsets.
Its literal reply, provider JSON, receipt and six-second debit remain unchanged:
`migration/evidence/public-av-7fe5d21cea9ccc07ac4d064ef371351b428b9d0ee4fc9ff617985d6de09f5a7a.json`.
The existing response is not retroactively given a structured-contract verdict.

## Offline checks

From a clean checkout with FFmpeg/ffprobe available:

    python3 migration/diagnostics/synthetic-audio-c01/build_audio.py synthetic-audio-control-output
    python3 -m unittest discover -s migration/runtime_bridge -p 'test_*.py'

Tests use a fake key, mock HTTP and checkpoint commits, and temporary databases.
Files counterfactual tests reconstruct the verified pre-run42 snapshot in memory.
Audio counterfactuals reconstruct the verified pre-enum-fix snapshot with all
four real receipts and 24 seconds. Later synthetic-audio rows are excluded only
from those temporary historical test fixtures, with exact whole-file SHA256
assertions. Current production SQL and receipt files are never rewritten or
pruned. The runtime continues using the full current ledger and all prior debits.
Separate tests verify preservation, new identity, terminal replay, invalid-output
receipts, abstention, nullable end handling and shape-versus-accuracy separation.
