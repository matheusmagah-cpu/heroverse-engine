# Pilot-006 single preserved Short recovery: phase 2

Baseline: 9f7c762638bad129206f136880e0a2fc73bec09f. SPEC v4 issue259 was consolidated at 2026-10-21T00:15:30Z after independent contract review.

Verified original manifest SHA256: 37465008e0b73a51f3d394d283500eab1426fdd679d36b571ed241d20689e402. All three original records have publish=false and NOT_REVIEWED_ProviderFailure. The historical detailed HTTP cause was discarded by the old reviewer and remains unknown.

Plan only: preserve short-00.mp4 hash 9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707 and review it once through the existing designated reviewer after code gates. No media approval or provider recovery is claimed. No provider, rendering or dispatch has occurred in phase 2.

Contract review caught a temporal rollover risk and required explicit recovery binding in pending/publisher, fixed 14:00 UTC slot, 13:15 UTC cutoff, context identity checks, immutable source fields and durable failure diagnostics. Existing criteria, rubric and ordinary finalizer stay unchanged.

Implementation and acceptance are pending. Issue259 remains open and working; not DONE.

## Independent checks before review dispatch
- Existing `shorts_prerequisite.py migration/production/pilot-006` printed `{"status": "PASS", "problems": []}` at 2026-10-21 00:17 UTC. Long approval and review are prerequisites, not a Short verdict.
- `review_recovery.py --list` against the real unchanged manifest printed exactly `short-00.mp4 9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707`; no provider was called.
- The preserved candidate text contains Philippians 4:6-7 (KJV), an opening “You can let go. He will not.” and a closing about peace standing watch. Text inspection is not watched review; two-scene pacing remains to be evaluated honestly by the designated reviewer.
- Asset receipts identify `bg-still-water-night` hash `7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2` and `bg-healing-garden` hash `97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070`, original HeroVerse FLUX.1-schnell generation (Apache-2.0) with recorded Real-ESRGAN BSD-3-Clause upscaler. This records existing provenance; prompts alone are not evidence of visual content or quality. Actual rendered-file verification remains in the workflow before review.
- Source long manifest records preserved Kokoro v1.0 am_michael narration and owned instrumental-v2 music. No new voice, images or music were generated for this recovery.
- Workflow baseline SHA256 is `caf36ac8c64f23eebdf71fe0eb7e2418170b108f102eed532d1c20edc1bb892d`. YAML BaseLoader comparison with only the two authorized run bodies replaced confirms all remaining nodes identical. Automated test also reconstructs baseline raw bytes and hashes them.
- All 15 frozen criteria and ordinary-finalizer files remain byte-identical to phase 1 main. No R3 exception for pilot005 is transferred to pilot006.

## Code acceptance at 2026-10-21 00:21 UTC
- `python3 -I -B migration/publish/test_review_recovery.py`: PASS, 28 tests in 0.185s.
- `python3 -I -B migration/publish/test_pending_shorts.py`: PASS, 9 tests; independent review and technical direction also executed it.
- `python3 -I -B migration/publish/test_publish_shorts.py`: final PASS, 49 tests in 0.394s after the collision fix and post-QA cutoff recheck.
- Existing complete PR loop with configured interpreter: PASS, 47 test files, exit 0. No skips or threshold changes introduced.
- Independent review found a missing direct-publisher collision guard: scheduler checks alone were insufficient. Added ledger and other schedule collision rejection before session, plus source-long opening constraint and negative tests. The same reviewer verified rejection `RECOVERY_TARGET_ALREADY_TAKEN` before session. This was corrected before delivery, not hidden by a PASS from other tests.
- Baseline antidote: exact old publisher from 9f7c762 accepted a synthetic late candidate and rolled it to 20UTC at 13:15:01. Current publisher rejects before session/upload. Mock video IDs and observations in those logs are synthetic, not evidence of an external upload.
- `git diff --check`: PASS. Contract `card_check`: CARD_OK. Scope checker: IN_SCOPE 9 files. Remote SHA/bytes and CI will be recorded after delivery; no code PASS is a media PASS.

## Persistence limitation
The wrapper provides local atomic replacement. It does not claim distributed exactly-once after a runner crash before the existing Record push. Any uncertain outcome or failed persistence blocks redispatch until run/log evidence is reconciled. No automatic retry trigger was created.

## Phase 3 correction initiated — 2026-10-21 00:55 UTC

Actual run39521492371 reviewed hash9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707: QA PASS, editorial FAIL overall7.6, rhythm6.5 and ending7. All publication flags remain false. The exact recorded manifest is archived byte-identically as correction-history.json, SHA2564c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677. No unchanged FAIL re-review.

SPEC v5 contract received independent PASS and CARD_OK. The first issue-body update was denied before execution; after owner specifically confirmed the exact consolidated replacement, one same-operation retry succeeded at00:54:38UTC. No alternate route or scope expansion was used.

The closed36second plan preserves complete narration,1.310seconds after the last word and two nominal18second scenes. Existing painted assets and FLAC sources were verified by hash. Their use is a plan, not qualified output. Continuous atmosphere and a longer tail do not guarantee a score9; local visual/auditory smoke, real output QA, watched review>=9 and publication gates remain required. No new MP4, render or provider call yet.

Canonical plan SHA2561c52034ce611b8a30c9d92ce22e9b6ce8f7cbff14b803a44ff8e7d1eb4991c57,3460bytes including newline. Source script/timeline/inputs/images/long manifest/long review hashes all matched the contract. Music10800seconds covers the planned offset; voice source is24000Hz mono,1529.993333seconds. Output resampling48k is not source provenance.

Issue259 remains open and dot-working. No new claim; this phase PR uses Refs only. The phase2 accidental auto-closure from a negated closing phrase was corrected; future phase PR bodies must never contain a closing keyword before an issue reference, even negated.
