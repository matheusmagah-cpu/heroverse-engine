# Shorts phase 2: one corrected, gated edit

Refs #231. SPEC v4 was confirmed remotely at 2026-10-20T16:53:06Z; v5 byte-binding and historical-FAIL amendments were confirmed through 17:09:11Z. Phase 1 merged in fae9879fcf75740ffc7ba7c3f4a6a5ffbb27d7e1. The same executor and prescribed branch continue without a second claim. This is code and synthetic-test evidence, not qualification of a real Short.

## Editorial decision and exact plan

The chosen continuous narration interval is 459.860–499.672 seconds: ten original sentences, opening “Lord, protect my relationships.” and ending “Let my words carry your peace into every room I enter.” The title is “A Prayer for Peace in Your Relationships”. This is an original prayer about relationships and speech, not a healing or wealth promise. No partial KJV quote or spoken CTA is included. The textual editorial assessment is separate from, and cannot replace, a watched review.

Planned output is 40.312 seconds including the unchanged 0.5-second tail. Home-sunrise and garden are existing mapped assets. Source byte hashes, model/license links and metadata are in phase2-inputs.json. Full downloaded asset hashes remain null until the production workflow runs. The home image is recorded as 2048×2048 after its declared upscaler; the garden is 1344×768. Neither is represented as native 1080×1920 detail. The producer records actual probed source dimensions and portrait crop information; output resolution alone never proves source detail. Picture quality must still pass the designated watched review.

## Implementation and fail-closed boundaries

- A strict, exact editorial-plan adapter reconstructs the candidate from pinned source bytes, not arbitrary strings or expressions.
- The editorial renderer uses the hash-verified original FLAC directly. The no-plan legacy path still uses voice.wav.
- Two 18–36-second nominal scenes use continuous, sentence-timed monotonic camera motion. A 15-frame crossfade is centered on the quantized boundary; no abrupt fast-cut substitution was introduced.
- The existing workflow run body performs plan validation, production, actual media checks, designated watched review and automatic finalization before preservation. Its no-plan branch retains the old commands. Triggers, inputs, concurrency, permissions, credentials, jobs and other step bodies remain unchanged.
- Actual frame count, decode, black-frame intervals and source-narration onset/ending are measured. A single black frame at EOF is rejected, not missed because the filter lacked an end marker.
- Review and QA each bind to actual before/after local bytes. The finalizer requires their hashes, media_checks and the recomputed MP4 hash to agree. Copied PASS evidence is not re-stamped as new evidence.
- The historical archive remains immutable. The explicit history guard rejects a current MP4 equal to a previous editorial FAIL before any provider call. A different hash does not grant PASS.
- Missing, malformed, stale or inconsistent evidence stays nonpublishable. Malformed JSON is atomically replaced by a safe tombstone. No manual approval or publish promotion is used.

## Executed validation and failures corrected

- Card validation: CARD_OK. Scope validation: IN_SCOPE 13 files. git diff --check is clean.
- Six source fixture hashes, fifteen frozen file hashes and four reviewer AST hashes remain exact. The PR workflow changes only its permitted test list. The Shorts workflow's five structural hashes remain exact, including normalized whole-document hash 92056d8367a1c3b69b314b595679aebedcd73a1dd59d957c4d7e862d49dacaf2 when only the authorized run scalar is replaced.
- Initial synthetic FFmpeg smoke failed because xfade received frame_rate=1/0. Explicit fps=30 after timebase normalization corrected it. Last-frame camera progress was also corrected to reach the declared endpoint exactly.
- Actual synthetic output: H.264/yuv420p at 108×192 test resolution, 30 fps, 1209 frames, 40.300 seconds. Second nominal scene: 544 frames. Twelve frames exceed the chosen red/blue mixture threshold (659–670), all inside the 15-frame fade envelope (657–671). No claim is made that all 15 frames exceed that measurement threshold. A temporal fixture retained 60 distinct fingerprints in its final 60 frames.
- Independent review reproduced and then revalidated fixes for the FLAC/WAV source mismatch, malformed-JSON inherited publish flag and single EOF black frame.
- Producer main integration tests reconstruct exactly one valid candidate and reject forged selection, altered plan, raw source newline/hash changes and missing/null editorial plans with zero produce calls. The missing-plan guard was separately removed in a regression experiment: both downgrade tests then failed, proving the old path would reach produce. All 45 legacy test methods remain AST-identical.
- Four review-binding antidotes fail against phase-1 baseline fae9879 and pass against this patch: real verdict hash, mutation during provider, mutation during QA with zero review calls, and stale copied verdict rejection. Provider calls in all tests are mocks.
- The first complete 44-file test loop passed 43 files; cinematic tests failed only because system Python lacked cv2. The already configured /tmp/hv228-venv interpreter ran those same two cinematic tests successfully. No dependency or project criterion was changed. Final loop at 17:13 UTC with PATH=/tmp/hv228-venv/bin:$PATH and RUNNER_TEMP=/tmp/231-phase2-tests: all 44 test files PASS. Targeted final counts: producer 68, reviewer 32, edit-plan 41, no-live-data 4 and error-register 3 PASS.
- An initial dot_scope.py --help diagnostic failed because the utility has no optional help parser. Its actual three-positional-argument interface then returned IN_SCOPE 13 files. This was a tooling invocation error, not a hidden acceptance PASS.

## Actual production state

No production render, provider call, dispatch or publication has occurred for this corrected edit. A synthetic test is not real qualification. Local long005 prerequisite check returns PASS with no problems, and its existing automated approval is bound to c98794d71da7ef5ede9d1d79fe50db36cb1e78b1c703a0f371f049951ba36f54. The ledger identifies full-long video XDwxi4pvllM. These must be rechecked on current main before execution/publication.

The existing workflow UI is available in the cloud browser; no new permission or credential was configured. After code review, exact-SHA CI, normal merge and current queue checks, the authorized route is existing shorts.yml on main for pilot-005, never the long renderer. Actual media checks, all designated review scores and output hash will be recorded before any publication.

The target is qualified media and explicit publication dispatch by 19:15 UTC, for the existing 20:00 UTC slot on 20 October 2026 (17:00 Brasília). The lead-time target is not permission to abandon or silently postpone the slot. Existing publish-shorts.yml may be dispatched with that exact slot only after every gate, source/license/metadata/channel and idempotent-ledger check. Verify the actual processed scheduled upload, then public availability at 20:00 UTC. #231 remains open and is not DONE at this code-only stage.
