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

Actual run 39521492371 reviewed hash 9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707: QA PASS, editorial FAIL overall 7.6, rhythm 6.5 and ending 7. All publication flags remain false. The exact recorded manifest is archived byte-identically as correction-history.json, SHA256 4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677. No unchanged FAIL re-review.

SPEC v5 contract received independent PASS and CARD_OK. The first issue-body update was denied before execution; after owner specifically confirmed the exact consolidated replacement, one same-operation retry succeeded at 00:54:38UTC. No alternate route or scope expansion was used.

The closed 36-second plan preserves complete narration, 1.310 seconds after the last word and two nominal 18-second scenes. Existing painted assets and FLAC sources were verified by hash. Their use is a plan, not qualified output. Continuous atmosphere and a longer tail do not guarantee a score 9; local visual/auditory smoke, real output QA, watched review >=9 and publication gates remain required. No new MP4, render or provider call yet.

Canonical plan SHA256 1c52034ce611b8a30c9d92ce22e9b6ce8f7cbff14b803a44ff8e7d1eb4991c57, 3460 bytes including newline. Source script/timeline/inputs/images/long manifest/long review hashes all matched the contract. Music of 10800 seconds covers the planned offset; voice source is 24000 Hz mono, 1529.993333 seconds. Output resampling to 48 kHz is not source provenance.

Issue 259 remains open and dot-working. No new claim; this phase PR uses Refs only. The phase 2 accidental auto-closure from a negated closing phrase was corrected; future phase PR bodies must never contain a closing keyword before an issue reference, even negated.

### Phase 3 local evidence at 2026-10-21 01:08 UTC

- The initial “no render” statement above describes the draft initiation. Six local diagnostic MP4 clips now exist, each one second at FullHD, sampling start/middle/end of both real scenes. They are not the complete production Short and have no editorial score. Commands and measurements are preserved in the execution audit. Source composition remains painterly, no persons observed in inspected frames, captions/reference legible in sampled frames.
- Real source audio was mixed into a 36.000-second diagnostic WAV using the intended audio graph. A native audio-input attempt returned unsupported audio input. Perceptual audio is NOT_REVIEWED; sample counts and energy are technical measurements only. Temporary technical direction approved a single-method clarification, confirmed in issue259 at01:03:41UTC: mandatory audiovisual review is still on the complete real MP4 using the existing designated reviewer, before eligibility/publication. No extra provider call for smoke.
- Producer baseline89 tests passed, including six numerical005 frame hashes identical to baseline. New tests cover continuous006 atmosphere, fixed spans, voice/padding, closed routing and serial/reference equivalence of every synthetic frame/PTS and all1728000 stereo sample frames. Synthetic equivalence is not real media qualification.
- Independent review found direct producer and check-media entrances missing canonical-attempt preflight; both were corrected to block stale prepared selections before rendering/provider. It also found Preserve only checked file existence; Preserve now verifies raw SHA and object identity before any canonical deletion/copy or release upload.
- Current pending suite:13 tests PASS0.074s. Includes execution of the actual Preserve body with altered measurements and proof of zero upload calls plus unchanged canonical manifest/frame.
- Current publisher suite:52 tests PASS0.446s. Actual correction binding and temporary synthetic source/history/media fixtures are used. Positive9.0 yields one fake upload then readback without MP4; seven forged gates fail before session. Fake video IDs in test output are not external publication evidence.
- Test harness failures were preserved and corrected: missing copy import, a branch parser splitting at Python's inline else, and a synthetic path missing the canonical migration/production context. A positive test exposed the path problem, and rejection assertions now require the actual binding failure rather than any earlier exception. No production validator was weakened to pass fixtures.
- A worker exec session disconnected before a final repeated suite could be observed; its result is UNKNOWN. A fresh exec confirmed files/environment intact, then affected tests were rerun. No production run was active and no retry of provider/upload occurred.
- CARD_OK and16 frozen-file byte comparisons passed against582ff607, including all qa_criteria files, STANDARD, shorts_qa, ordinary005 adapter and reviewer. An initial audit command used the wrong shorts_qa path and failed; the corrected existing migration/publish/shorts_qa.py path was then checked successfully. No missing check was reported as PASS.

### Phase 3 CI rejection and correction scope — 2026-10-21 01:24 UTC

CI https://github.com/matheusmagah-cpu/heroverse-engine/actions/runs/39525741977 on SHA 6bdf2a5b331f92349d081859aaab4e9f5a71576a returned FAILURE. The complete local loop also returned exit 1. These are not code acceptance or media PASS.

The three actual failures are retained: (1) a fixed floating-image hash was not portable to the runner's OpenCV 4.6 build; the earlier local baseline comparison does not establish cross-environment equivalence; (2) sixteen references in new producer tests depended on mutable pilot-006 files; (3) test_errors_register correctly rejected the new adapter test because it was absent from the explicit CI loop. A subprocess bridge did not satisfy that register. Neither checker nor thresholds will be weakened.

Temporary technical direction approved only adding migration/production/test_shorts_006_plan.py to the existing pr-checks.yml loop and that exact workflow path to the card. The issue update succeeded at 01:24:15 UTC and exact body readback matched. Removing this single added test token reconstructs all original workflow bytes; triggers, inputs, permissions, concurrency and schedule are untouched. test_errors_register.py then reported 3 tests OK in 0.005 seconds. The remaining fixture/oracle corrections and final full-suite/CI acceptance are still pending at this entry.

The sole task resumed after an interruption. No issue PATCH or CI edit had been attempted before that interruption, so there was no uncertain mutation retried. No new production rendering, provider invocation or publication occurred.

At 01:33 UTC the corrected producer test fixtures use synthetic temporary sources and genuine validators, not mutable pilot files or bypassed scanner rules. The 005 numerical oracle is independently copied from baseline582ff607 and evaluates all91 opening frames with exact array equality in the same OpenCV environment. FPS30 is pinned in the oracle; no expected hash was replaced with an observed value. The redundant bridge was removed because CI now invokes the complete adapter suite directly.

- Corrected focused producer tests:8 PASS0.539s; technical direction independently repeated8 PASS0.540s.
- Unmodified live-data scanner:4 PASS0.819s, independently4 PASS0.276s.
- Unmodified error register:3 PASS0.005s, independently3 PASS0.006s.
- Remaining complete repository loop excluding producer, including directly invoked adapter:47 files PASS, persisted exit0.
- Two long-running revised producer test sessions lost their process handles and had no terminal summary/exit marker. Their result is UNKNOWN, not PASS. No process remained when checked; the full producer suite is being reconciled separately. Prior100-test results apply to the previous test version only, while producer implementation bytes remain unchanged.
- Bounded FullHD transition diagnosis remains pending. The six existing FullHD clips prove sampled rendering only, not serial transition equivalence or editorial quality.
- Card check CARD_OK; scope IN_SCOPE13files; git diff --check PASS. Production remains blocked until all applicable final tests, independent review and exact-SHA CI pass.

## Phase 3 actual production attempt — 2026-10-21 02:09 UTC

RESULT BLOCKED. Code merged as 76fb88ce1253ad8adc56743b463fbae1bd31ccd1 after CI 39528158242 and independent technical review. Existing shorts workflow run 39529000826 rendered pilot-006 once, then failed its acoustic pre-review check. Run: https://github.com/matheusmagah-cpu/heroverse-engine/actions/runs/39529000826 .

Observed MP4 SHA256 in the job log: `126c2e8335f5135e4d2ec2407c67e6eb636d8ce36ea7d0bd489d8ed34ff9c617`. This is **MP4_UNPRESERVED**, not an available or qualified artifact. The Preserve step was skipped; the run returned zero artifacts, and the complete 288-asset release inventory did not contain this hash. No rerender or provider retry was performed.

Actual measurements recorded in the log: duration 36.0 seconds, 1080×1920, 30 fps, 1080 frames, uniform video PTS, no black intervals, 1728000 presentation audio samples with declared AAC padding accounting. These are structural measurements, not frozen-QA or watched-review approval. The acoustic guard failed on source leading/trailing inactive energy of 0.17/0.60 seconds. Frozen QA and designated provider review were not reached; their result is null because they were not executed. No new editorial score exists.

The source FLAC reproduces the same acoustic result. The adapter inherited an explicit pilot-005 energy-edge verdict from issue231 and `shorts_edit_plan.py`, rather than a neutral measurement-only helper. No threshold was changed after seeing the failure. An explicit pilot-006 acceptance amendment is pending, separating source/PCM integrity from perceptual ending review while retaining frozen QA, overall score >=9 and ordinary pilot-005 behavior. Failure preservation is also proposed, strictly hash-bound and publish=false; archive does not mean approval. Implementation and a new render remain blocked until that amendment is authorized and validated.

## 2026-10-21 07:43 UTC owner decision
The proposed acoustic and failure-preservation exception was explicitly rejected by the owner. It is not applied. The earlier pending statement records historical status only. Current work selects materially different complete narration while preserving the existing acoustic, structural, QA and audiovisual-review acceptance rules, including overall >=9. No new render or provider call has occurred yet.

## Material correction SPEC v6 — 2026-10-21 08:12 UTC

The owner rejected the proposed exception and explicitly requested an animated cinematic hook. The new material contract preserves all acceptance rules, including the existing acoustic limit and overall >=9. No failure-preservation exception is implemented.

The first body replacement was denied and verified not executed. After the owner specifically approved replacing issue259 with the reviewed42-second contract, one same-operation retry succeeded at08:12:20UTC. A fresh GET matched all55924 characters exactly. Contract SHA256:714ce5e14b371b2dd032501bcf02796985c40e54316b539fb78cdb5216c4f4a8. Independent contract review PASS does not qualify code or media.

Selected narration:813.728–854.417,12 complete sentences, opening “Let your face soften.” and ending “Rest now.” Title:“Rest in God's Care”. No spoken Scripture, partial quotation, health promise or CTA is introduced. Unchanged structural selector returned no rejection. A previous nurse-analogy candidate was discarded because the unchanged selector reported UNRESOLVED_SEGMENT_END, despite its acoustic pass.

Native extraction813.728–854.418 preserves the complete source and boundary rounding residue:976560 samples at24000Hz. Reference indexing and FFmpeg extraction matched byte-for-byte, PCM SHA256e49a6b29b469a61298508e796b933a6ba87067427512649b28ed4d18fc9008af. Unchanged48kHz acoustic measurement returned leading0.13s/trailing0.29s, PASS against0.3s, without gain or retiming. This is technical evidence, not perceptual audio review.

Output plan42.000s:1953120 source samples plus62880 padding samples,1260 video frames, two nominal scenes20.977/21.023s and the existing0.5s dissolve. Both scenes satisfy the unchanged18–36s rule. Plan3489 bytes including newline, SHA25695624da1b4e4e4b256faee29fb37c8bc78fdb5c9747a3be86c69d9ec0e319905. Opening atmosphere adds the explicitly specified smooth light/fog profile only to scene1. No physical water simulation or cinematic quality PASS is claimed. Real preview inspection, code tests/review/CI, new full render, frozen QA and actual watched review>=9 remain pending.

### V6 implementation checks at 08:19 UTC

The adapter and canonical plan now implement the reviewed material, 12 complete source sentences and exact 42-second clocks. The independent source selector accepted exactly one candidate. The native source interval and plan preflight passed against the real pinned files. The source preflight does not qualify the future output.

Commands and actual results:
- /tmp/hv228-venv/bin/python -I -B migration/production/test_shorts_006_plan.py: 22 tests PASS. Temporary technical direction independently ran 22 tests in 3.876 seconds, exit 0, against these adapter bytes.
- /tmp/hv228-venv/bin/python -I -B migration/publish/test_pending_shorts.py: 13 tests PASS in 0.479 seconds, exit 0.
- /tmp/hv228-venv/bin/python -I -B migration/publish/test_publish_shorts.py: 52 tests PASS in 0.491 seconds, exit 0. Printed video IDs and observations are synthetic test fixtures, not external uploads.
- Existing CI test-file loop excluding the producer suite: 47 files PASS, persisted exit 0. The producer full suite and preview were still running at this entry.
- card_check against SPEC v6: CARD_OK. dot_scope against the six changed paths: IN_SCOPE 6 files. git diff --check: PASS.
- Sixteen frozen files compared byte-for-byte against main e0c72367031d4ceadfb39c1577af71d21a55b8e5: PASS, including all existing QA criteria, migration/STANDARD.md, ordinary pilot-005 adapter, shorts_qa.py and reviewer. The first audit looked for STANDARD at the wrong path and reported ABSENT; the corrected actual path was explicitly verified, not counted as a pass by assumption.
- The actual 42-second synthetic AAC packet probe confirmed 1970 packets, 1024 priming samples and a final packet presenting 768 samples. Decoder padding is accepted only with the same existing packet-clock evidence; no timing tolerance was expanded.

The implementation additionally rejects the logged unpreserved acoustic FAIL hash, without pretending its unavailable bytes were independently measured. Historical manifest bytes remain unchanged. The existing acoustic validator, frozen QA, reviewer rubric, publication policy, deadlines and workflow preservation behavior remain unchanged.

## Phase 4: bounded review-only recovery, implementation in progress (2026-10-21)

The new material from PR #263 rendered once in run 39569442793 on main b710b7c64d58052d3d71e1e56630d6875b876826. The actual 42-second MP4 was preserved as release asset 661879452 (20,581,582 bytes), SHA256 96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e. Downloaded bytes were independently rehashed. Acoustic leading 0.13/trailing 0.29 seconds passed the unchanged 0.3 limit. All seven frozen QA checks passed, loudness −15 LUFS and true peak −2.4 dBTP. No editorial verdict exists: the designated reviewer returned NOT_REVIEWED_ProviderFailure / HTTP_503_UNAVAILABLE at 2026-10-21T08:41:45.362893+00:00. Overall remains null, publish=false, release_status REVIEW_NOT_REVIEWED. Workflow SUCCESS established persistence, not media approval.

Canonical main 89541e4cd3232195e8f626d8419b023cc0cd3317 preserved manifest raw SHA256 a33d46db02ee419c357ae4ecefeee615b3d6ac32af143e85814cfbcb82bd1418 and media-checks raw SHA256 6d3f0199f1ea9b0b22a87dbb29b9abfa7a3632f74488d6f1be990a9b46e00200. Previous editorial FAIL 9c0f… and unpreserved acoustic FAIL 126c… remain unchanged; no rerender or re-review of either.

Issue #259 SPEC v7 was independently reviewed, then updated normally at 08:58:06 UTC. A subsequent GET matched every body byte, SHA256 414e44002f295532c627dad8eaa3441d0c881e145e30435496cd8d474e75945a. It permits one recovery invocation on the preserved new hash after code gates, preserving the existing internal reviewer retry policy. No added retry loop, fallback, model/rubric/QA change, trigger, permission, schedule or failed-render archive change is authorized. The owner's rejection of the earlier acoustic/preservation exception remains honored.

The recovery contract requires fresh real QA and pre/post hashing, exact prior 503 preservation, closed audit validation in the eligibility path, one selected record, real clocks including final installation, and unchanged 13:15 UTC cutoff/14:00 UTC slot. A run interrupted before remote Record is uncertain and must be reconciled, not repeated. Local STARTED is not a distributed exactly-once guarantee.

Implementation is complete within five allowed paths. Initial tests exposed two concrete concurrency windows and clock ordering before provider/final installation; regression tests now require foreign manifest bytes to remain intact, MP4 changes to block installation, and a deadline crossed during the last hash to stay ineligible. No criterion was relaxed. A new YAML test initially required unavailable PyYAML in the configured venv; it was replaced by a stronger required standard-library byte invariant, not skipped. The historical workflow test initially failed because it asserted superseded routing. The issue subset was narrowly clarified at 09:06:13 UTC; only that assertion/normalization changed, preserving baseline hash caf36ac8c64f23eebdf71fe0eb7e2418170b108f102eed532d1c20edc1bb892d.

Software acceptance at delivery preparation:
- Configured Python test_shorts_006_plan.py: 33 tests PASS, 3.248 seconds. Independent review also executed 33 PASS and verified its foreign-writer counterexample now returns INPUT_CHANGED without replacing the foreign bytes.
- test_review_recovery.py: 28 tests PASS, 0.103 seconds; independent execution also PASS.
- Temporary technical direction personally executed the same 33 adapter and 28 historical-recovery tests at 09:07 UTC, both PASS. These are dot technical tests, not reviews attributed to Matheus or Claude.
- Independent pending/publisher tests: 13 and 52 PASS.
- card_check: CARD_OK. dot_scope: IN_SCOPE 5 files. git diff --check: PASS.
- Seventeen frozen files compared byte-identically with main89541e4, including all tracked qa_criteria.json, STANDARD, reviewer, unchanged005 adapter, shorts_qa and historical recovery implementation: PASS.
- Workflow nodes outside the two authorized run bodies are identical; both bodies equal the literal contract. Real read-only --recovery-list returned only short-00.mp4 and the preserved96c826 hash, exit0, no provider.
- Full48-file suite, exact remote bytes and CI are still pending at this draft's preparation; final results must be recorded before ready/merge.

The ordinary finalizer retains truthful priority for QA/review/policy negatives; a candidate that would otherwise qualify becomes TARGET_SLOT_LEAD_MISSED if the deadline expires. Expiration never promotes a negative. No provider recovery or publication is claimed. The original hook preview showed subtle procedural light/fog beyond camera motion, not established cinematic impact; the full reviewer must still evaluate it and all other dimensions with overall >=9.
