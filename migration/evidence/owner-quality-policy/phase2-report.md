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


## Preserved SPEC v7 before metadata-only consolidation (2026-10-21 09:28 UTC)

Exact prior issue259 body, SHA256 dd0b97d79242285d04d8c5419e843bec9236eeaec425a370ef6753b0d98f5fb4. The following is archived history, not competing current instructions. Runtime evidence is commit94e652d55248e4395f85e187a35c319f358b9854; accepted recovery implementation is PR264/main e8e74393f963d43609b108e49bb88473b369afa6. Both provider503 results remain authoritative and no new invocation is authorized.

<details><summary>Full prior issue body, preserved verbatim</summary>

# SPEC v7 — Owner quality floor and pilot-006 review-only recovery
## GOAL
Enforce the owner's additional overall >=9 requirement for every future new long/Short upload, without changing frozen QA or the existing reviewer rubric; deliver one corrected pilot-006 Short after actual historical review FAIL, preserving the completed diagnostic and recovery evidence.
## Authority and priority
Direct owner instruction Sentinel_efdcc18966988191b93f7ad0f0b6de38 at 2026-10-20T20:14:14.608652+00:00: “Pode postar mais os próximos quero 9 pra cima.”
Temporary technical direction was delegated directly on 2026-10-20 at15:56:57 UTC. This is the sole active execution; #257 remains BLOCKED for formal post-upload verification, not DONE. #231 body is not edited. The already uploaded pilot-005 hash cb3ce331529437f4fadc3b14dec01dfad18909a3e9f024a99cea141e91ae956f is not invalidated or uploaded again.
## INPUTS
Baseline main 767badb5f99ef89274693813bd2e8ea1ec76f22c; DOT_PROTOCOL; existing publish/production tests; pilot-006 shorts manifest and run39453449948 logs; existing ledger and receipts read-only.
## ALLOWED PATHS
```allowed
migration/publish/owner_quality_policy.py
migration/publish/test_owner_quality_policy.py
migration/publish/pending_shorts.py
migration/publish/test_pending_shorts.py
migration/publish/publish_shorts.py
migration/publish/test_publish_shorts.py
migration/publish/publish_video.py
migration/publish/test_publish_video.py
migration/publish/test_first_comment.py
migration/production/shorts_review.py
migration/production/test_shorts_review.py
migration/evidence/owner-quality-policy/report.md
migration/evidence/owner-quality-policy/pilot-006-diagnosis.json
migration/publish/review_recovery.py
migration/publish/test_review_recovery.py
migration/evidence/owner-quality-policy/pilot-006-selection.json
migration/evidence/owner-quality-policy/phase2-report.md
migration/production/pilot-006/shorts/shorts.json
.github/workflows/shorts-review.yml
migration/production/shorts_produce.py
migration/production/test_shorts_produce.py
migration/production/shorts_006_plan.py
migration/production/test_shorts_006_plan.py
migration/production/pilot-006/shorts/correction-plan.json
migration/production/pilot-006/shorts/correction-history.json
migration/production/pilot-006/shorts/correction-media-checks.json
migration/production/pilot-006/shorts/selection.json
migration/production/pilot-006/shorts/short-00-frame.jpg
.github/workflows/shorts.yml
.github/workflows/pr-checks.yml
```
Phases1–3 implementation/render execution are completed. Their paths remain in the audit union, not a license to repeat execution. Current phase4 changes only shorts_006_plan.py, its test, the existing phase2-report.md audit, the integration assertion test_workflow_only_two_run_bodies_changed in migration/publish/test_review_recovery.py, and the two shorts-review.yml run bodies specified below. All triggers, inputs, permissions and other workflow fields remain unchanged.
## INTERFACES
```interfaces
migration/publish/pending_shorts.py: def approved(s):
migration/publish/publish_shorts.py: def main(shorts_json, shorts_dir, long_key, ledger_path, receipt_path, slots):
migration/publish/publish_video.py: def main(package_path, manifest_path, video, thumbnail, ledger_path, receipt_path, publish_at=None):
migration/production/shorts_review.py: def main(shorts_dir, n="3"):
migration/production/shorts_review.py: PASS_ITEM, PASS_OVERALL = 7, 8
```
## EXACT VALUES
Add pure owner_quality_policy.check(review, output_sha256) returning a list of categorical problems. Require a dictionary, status PASS, model gemini-3.8-flash, overall finite int/float excluding bool, 9.0<=overall<=10.0, and review.output_sha256 equals a valid lowercase64hex actual/bound output_sha256. It adds an eligibility gate, not a reviewer score or approval.
Shorts: post-review selection applies this gate; record owner_quality_policy result separately without rewriting review verdict/rubric. pending_shorts.approved requires publish is True, QA.status PASS and the same policy; states reports owner_quality_policy_blocked distinctly from review_by_undesignated_model, with existing video_id evaluated first. New upload publisher checks policy before credentials/session/POST, including direct invocation and stale manifest. Existing video_id path remains readback-only and is not rejected retrospectively due to the new score floor; never reupload. Preserve existing records for readback even when their local publish flag is false; missing local MP4 after cleanup does not require another upload. An existing uploaded record can remain in the published/ scheduled state independently of eligibility for NEW uploads.
Long: publish_video main loads review.json from the manifest file's parent for a NEW upload, computes SHA256 from actual VIDEO bytes (streaming), requires that actual hash equals manifest.output_sha256 and top-level review.output_sha256 with top-level status PASS, then supplies a new in-memory copy of watched_review with output_sha256 set from the validated top-level hash to the helper. The original review file/object is never rewritten. All checks run before session/credentials/POST. Missing or malformed evidence fails closed. Existing ledger video_id resumes unchanged, no extra upload and no retroactive threshold enforcement. Do not alter publication_binding or prepublish_gate frozen rubric. This final-upload gate also covers already prepared but not uploaded old approvals.
Only the todo (new upload) records receive rehash, policy and QA checks; cached policy results, publish flags and finalization markers never substitute for those checks. Existing OwnerException tests that expected a NEW8.5 upload must become explicit rejection tests; reservation/durability positives use synthetic>=9 records while already CONSUMED8.5 readback remains covered. This is the new owner requirement, not weakening any acceptance.
No whitelist authorizes a new8.5 upload. The consumed005 exception remains historical only. Existing9.0/9.3 long uploads are unchanged.
Preserve frozen QA bytes, PASS_ITEM/PASS_OVERALL, prompt AST, reviewer models and retry behavior. Do not change the ordinary temporal finalizer or slots.
Diagnostic JSON contains only verified run/SHA/status/hash evidence, sources and unknown reasons. Exact HTTP cause for old006 is null if logs/code discarded it, not inferred503. Preserve old verdicts and assets.
Phases1–3 completed without current media eligibility: corrected render run39569442793 preserved the new MP4 and a provider503, not editorial FAIL or PASS. Phase4 below permits one bounded review-only recovery after code gates, never another render or re-review of historical FAIL bytes. Publication still requires all real gates and fixed-slot checks.
Fixtures in test_first_comment.py may be updated only to provide valid synthetic raw hashes and bound PASS9 review; keep all original assertions and behaviors. New tests must explicitly cover real VIDEO bytes differing from matching stale manifest/review hashes, with zero session/upload calls.
## QUALITY BAR
Fail closed on missing evidence; no fabricated scores, no new routine human approval, no duplicate uploads. An additional policy rejection is not an editorial FAIL and must not rewrite the original review. Honest audit of old lost diagnostics and evidence limitations.
## ACCEPTANCE
python3 -I -B migration/publish/test_owner_quality_policy.py
python3 -I -B migration/publish/test_pending_shorts.py
python3 -I -B migration/publish/test_publish_shorts.py
python3 -I -B migration/publish/test_publish_video.py
python3 -I -B migration/production/test_shorts_review.py
Full existing PR test loop; card_check; dot_scope; git diff --check; remote exact bytes/newline; independent review; CI exactSHA.
Known answers:9.0 PASS,8.99/8.5 reject,10PASS,>10/NaN/inf/bool/missing reject, wrongmodel/status/hash reject; old PASS8.5 cannot appear as new pending upload or invoke session/upload; existingID8.5 causes zero new uploads and preserves readback. Long missing/mismatched review blocks before session. QA/reviewerFAIL never becomes eligible at9.5 in the full workflow. The standalone long publisher guard guarantees the additional score/hash/review requirements; canonical QA/approval/gate revalidation remains in the existing publication_binding workflow step, unchanged. Do not falsely attribute QA validation to helper(review, hash). Existing canonical review may still label8.5PASS, but additional policy blocks NEW publication. Tests must demonstrate old behavior fails new negative cases; no skips or relaxed expectations. Synthetic tests do not qualify media.
## FORBIDDEN
No frozen criteria/rubric edits, cron/triggers/permissions/access/secrets changes, spending, new render, manual live manifest/approval/ledger edits, #231 body rewrite, or unchanged retry of denied operations. Phases2 and3 execution concluded and must not repeat. Current provider/workflow execution is only the single phase4 review-only attempt on pinned corrected bytes after code gates. Only its two specified shorts-review.yml run bodies may change; shorts.yml, pr-checks.yml and all workflow triggers, inputs, permissions, concurrency, schedules and Record remain unchanged. The previously refused fail-archive preservation change remains excluded.
## DEADLINE (UTC) / BRANCH
Urgent before pilot-006 Short slot2026-10-21T14:00:00Z. Branch dot/259-owner-quality-floor.
Draft PR with Refs this issue; phase1 code completion does not close media follow-up or #257. RESULT with full files, actual commands/output/SHA/CI, honest diagnostic unknowns. Normal protected merge only after independent review and gates.


## Historical phase 2 — completed, not executable again

The following phase2 requirements document the accepted code and completed run39521492371, not permission to rerun its FAIL hash. Current execution is exclusively phase4 below. Its recovery interface remains unchanged for audit; do not invoke it again for this candidate.

### Historical single preserved Short review recovery
Phase 1 merged as 9f7c762638bad129206f136880e0a2fc73bec09f; its requirements remain unchanged. This phase activates only after code/review/CI acceptance. No repeated #231 operation.

## Additional ALLOWED paths
migration/publish/review_recovery.py
migration/publish/test_review_recovery.py
migration/evidence/owner-quality-policy/pilot-006-selection.json
migration/evidence/owner-quality-policy/phase2-report.md
migration/production/pilot-006/shorts/shorts.json
.github/workflows/shorts-review.yml

The live shorts.json is exclusively validated automatic output of the review wrapper/workflow, never hand-edited publish/approval/verdict. Historical records remain in the manifest with original verdicts; only the chosen record gets new QA/review. Nonselected publish flags must remain false, and the wrapper rejects an input with any nonselected publish=true rather than silently changing an authorized delivery.

## Exact selection and source
selection version single-short-review-recovery-v1; pilot pilot-006; file short-00.mp4; output_sha256 9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707; source_manifest_sha256 37465008e0b73a51f3d394d283500eab1426fdd679d36b571ed241d20689e402; original_review_status NOT_REVIEWED_ProviderFailure; target_slot 2026-10-21T14:00:00Z; release_deadline 2026-10-21T13:15:00Z. Selection is an offline plan, not approval.
Pin all these values in the wrapper, not arbitrary editable selector authority. Unknown keys/types/pilot/filename/digests/slots reject. Resolve only exact pilot directory and exact basename, no traversal/symlink or arbitrary paths. Baseline original manifest is immutable input; rerunning after recorded review changes its hash and blocks before provider.

## Interfaces
Existing shorts_review.main(shorts_dir,n="3"), shorts_prerequisite.problems(pilot_dir) returns a list; require an empty list before review. The wrapper does not change existing signatures or rubric. New prepare(pilot_dir,selection_path) -> validated input; review_selected(pilot_dir,selection_path) -> generated manifest; CLI --list PILOT_DIR SELECTION prints exactly selected basename and SHA for existing download loop; --review PILOT_DIR SELECTION performs recovery.
--list validates source manifest/selection and source status, not media bytes before download. --review revalidates source and actual downloaded MP4 SHA and qualified-long prerequisite BEFORE any provider call. It permits only the pinned NOT_REVIEWED_ProviderFailure, never PASS/FAIL or absent status. No retry on unchanged editorialFAIL. Re-run on changed manifest fails closed, including a newly recorded providererror.

Use a temporary isolated workdir containing a copy of the selected manifest record and the hash-verified MP4. Call existing shorts_review.main(tempdir,"1") once. It recomputes QA/hash and uses the exact unchanged designated reviewer; internal existing retry semantics unchanged. No direct model/API implementation. Recheck source manifest still byte-identical and original/copy MP4 same hash before atomic merge. Record failure diagnostics supplied by current reviewer; no fabricated cause. Exceptions leave canonical manifest unchanged and exit failure.

The three old rendered candidates were never editorially reviewed; this new attempt is materially different because current reviewer records sanitized error details and hash bindings, the new policy enforces>=9, and only one selected hash is evaluated. Do not infer provider recovery before result.

Preserve the untouched two records exactly. Preserve selected source fields and old failure under previous_review (exact original dictionary), replacing only the exact whitelist qa, qa_output_sha256, review, publish, owner_quality_policy from validated automatic output. Require exactly one isolated output record with original file/sha256 identity and every source field unchanged; reject altered text/title/selection or arbitrary extra fields. The original sha256 is immutable. A legitimate QA failure may have review={status:NOT_REVIEWED_QA_FAIL} without output_sha256; preserve that failure exactly with publish=false, binding actual bytes in qa_output_sha256 and recovery evidence rather than inventing a review hash. Eligible selected record requires original rubricPASS, frozen QA PASS, output binding and additional>=9 policy; no manual promotion. At most one publish=true. If now>release_deadline, force publish=false with categorical TARGET_SLOT_LEAD_MISSED while preserving actual review, never change schedule or rollover. Obtain UTC from real clock, tests may inject. Unknown/FAIL remains false and durable. Store execution/run provenance and actual output SHA in a top-level review_recovery_execution object inside generated shorts.json, the file persisted by the existing Record step. Its exact fields are reviewed_at (UTC ISO timestamp), github_run_id and github_run_attempt (positive decimal strings from the workflow; synthetic tests inject fixed positive decimal strings), and output_sha256. The binding validator validates field types and actual/pinned hash but never treats execution metadata as approval. No APPROVAL.json.

## Explicit temporal binding, without pretending editorial finalization
The generated manifest has a separate review_recovery object, never edit_plan/finalization: version single-short-review-recovery-v1, pilot pilot-006, file short-00.mp4, output_sha256 pinned above, source_manifest_sha256 pinned above, target_slot 2026-10-21T14:00:00Z, release_deadline 2026-10-21T13:15:00Z, previous_review_status NOT_REVIEWED_ProviderFailure, status REVIEW_RECORDED. The wrapper populates it only after validated output. This describes recovery provenance, not an approval. No free-form authority field.
The pure review_recovery.binding(spec) is separate from prepare() and never imports or initializes provider code; lazy import shorts_review occurs only inside review_selected after preflight. binding(spec) validates exact schema/types/pinned values, source_pilot, exactly the selected record identity and exactly three records, other records publish is False. Identify pilot006 from trusted invocation context, not only editable source_pilot: pending/states require pilot directory name and source_pilot to agree; publisher requires pilot prefix of long_key, canonical shorts_json pilot context and source_pilot to agree whenever any identifies pilot006. Changing/removing source_pilot cannot select the legacy branch. Reject traversal/symlink aliases in this recovery path. The existing publisher passes shorts_dir=$RUNNER_TEMP/shorts: do not require a pilot name in this temporary media directory. Validate it as a regular nonsymlink media directory and bind its selected file by actual hash; pilot identity comes from canonical shorts_json path, long_key and source_pilot. Test a pilot006 path/long_key with source_pilot changed to another pilot: zero session/upload. For pilot-006 new uploads the binding is mandatory; a missing/malformed binding cannot fall back to legacy. Other pilots remain unchanged. Re-check actual review/QA/hash/policy in existing publisher, never rely on this binding as PASS.
Existing allowed pending_shorts.py and publish_shorts.py plus their tests are retained in the union. pending() returns only the fixed14UTC slot for the selected hash when clock<=13:15UTC, long opens+30min<=target and slot not taken; after deadline or collision returns no eligible pilot006 candidate, never slots_for rollover. states/todo_files similarly report temporal_recovery_blocked after deadline; already uploaded IDs preserve readback regardless of clock.
publish_shorts.main validates the binding and exact single requested slot before session for new pilot006 uploads, requires real clock<=deadline, and rechecks deadline immediately before upload. No fallback slot, no past publishAt, no reupload of existing ID. Existing-ID-only paths remain readback-only even after cutoff. Tests require wrong/missing binding, wrong slot, another candidate, multiple eligible records, taken slot, and deadline+1s to produce zero session/upload for new uploads. This is an additional bounded correction, not a change of schedule or a temporal exception.

## Workflow invariant
Use existing shorts-review.yml main-only workflow, same pilot input, concurrency,permissions,env,timeout,trigger and steps. Only replace body of “Shorts from the private release (hash-verified)” and “Watched review (Gemini free tier)” as needed for pilot-006 branch; non006 legacy bodies unchanged. The selected download remains release hash-verified; --list returns one exactfile. Other pilots retain current behavior but phase1>=9 still applies. Existing Record step persists generated shorts.json.
Before code acceptance compare YAML BaseLoader canonical content with only those two run bodies replaced by placeholders against baseline; require byte equality of all non-run nodes. No trigger/dispatch/persistent access changes. No new workflow or new inputs.
After merged code and real source/provenance/long prerequisite checks, execute existing shorts-review.yml main pilot006 once, only if no active same-pilot review. Result and remote persistence must be known before any further action; no concurrent/render run. Local atomic replacement does not guarantee distributed exactly-once: a crash after provider but before the existing Record push can leave the original remote manifest. Any uncertain outcome, failed Record, cancellation or persistence failure blocks redispatch/re-run; reconcile run logs and preserved evidence before any new separately reviewed recovery decision. Do not infer no provider call from an unchanged remote manifest. No automatic retry mechanism is added. No provider usage outside configured free tier or paid fallback.

## Acceptance
New test_review_recovery.py automatically included by existing publish/test_*.py glob. Positive fixture: three records, one selectedNOT_REVIEWED, QA/review>=9 -> one shorts_review.main invocation for one candidate with existing internal provider retries unchanged, exactly one eligible record, untouched2byte-equivalent JSON values. Negative invalidsha/pilot/filename/schema/source manifest; selectedFAIL/PASS; nonselectedpublishtrue; wronglong/hash; changedoriginalMP4; changedtempMP4; changedsource while reviewing; errors beforeprovider must spy zero calls. Empty/malformed result failsclosed. Providererror/QAFAIL/reviewFAIL/8.99 remain false, with exact diagnosis and priorfailurepreserved. now13:15:00 mayeligible,13:15:01false, no slotchange. Second invocation after output mutation zero provider. CLI output exact; workflow actually consumes selector/onefile/main unchanged. Run old module against new invariants where applicable. FullCI, frozenhashes,13+newremote bytes,newline, independentreview/SHA all required.
Phase2 reviewPASS is not publication by itself: verify metadata/provenance/identity/full-long availability, existing publisher realQA/idempotency/readback and exact14UTCslot before publication. If FAIL editorial, report exact flaws and consolidate correction with newbytes before review again. One-timeR3exception for005 does not apply to006.



# Historical phase 3: corrected pilot-006 Short — render completed

This section preserves the accepted phase3 material contract, code requirements and source pins. Its one production run39569442793 completed2026-10-21T08:41:51Z after PR263 merged as b710b7c; new MP4 was preserved, QA/acoustics PASS, watched review NOT_REVIEWED_ProviderFailure HTTP503. These are historical render instructions, not current permission to render again. Phase4 alone governs the next execution. All source/material/criteria pins and valid publication barriers remain binding.

## Diagnosis and fixed objective

Recovered historical manifest SHA256: 4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677. Archive its exact bytes as correction-history.json. It includes all three historical records. Selected MP4 9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707 has actual review FAIL, overall 7.6, rhythm 6.5 and ending 7. Do not re-review those bytes or erase their evidence. The concrete defects are minimal motion around 00:03–16 and abrupt closing around 00:33–36.

Keep target 2026-10-21T14:00:00Z and release deadline 2026-10-21T13:15:00Z. No rollover. A passed software check is not approval of media. New output requires real QA and watched review, overall >=9 plus every pre-existing gate. The previous 005 exception does not apply: scene nominal durations are 20.977 and 21.023 seconds, both within the unchanged gate.

## Material-only correction and rejected alternatives

SPEC v6 established the completed phase3 candidate, extraction, duration, scene timing and derived plan digest, and incorporated the owner-requested cinematic animated opening through the closed first-scene profile below. This contract is not code acceptance, dispatch, media approval or permission to bypass any gate. All earlier phases, immutable history/source pins, allowed paths, licenses, movement outside the explicitly scoped opening, designated reviewer, QA, deadline, slot, code acceptance, preservation and publication requirements remain in force. No new acceptance method is authorized.

The owner refused the proposed acoustic exception: the frozen 0.3-second rule remains unchanged. Run 39529000826 failed; logged output SHA256 126c2e8335f5135e4d2ec2407c67e6eb636d8ce36ea7d0bd489d8ed34ff9c617 is MP4_UNPRESERVED. Preserve its actual failure and diagnostic evidence; do not re-review or redispatch those bytes, claim an archived MP4 exists, or infer nonexecution from unchanged canonical files. The prior replacement candidate 62.232–106.493 is discarded as UNRESOLVED_SEGMENT_END; do not silently resolve its source end or relax criteria.

The proposed fail-archive workflow change was refused and is not included. Keep the existing Preserve step's original if condition unchanged; only its already authorized run-body scope remains available. Do not add an always/failure condition, new archive path or acceptance exception. An unpreserved or uncertain execution remains subject to the existing authoritative reconciliation requirement before any separately authorized new attempt. The pinned correction-history.json remains byte-identical; do not append this diagnostic note to that immutable archive or change its digest.

## Source baseline and immutable pins

Source baseline for the recovered manifest: 582ff607089f9accb91a8a4d1a8c2fe6f4e47408. Implementation baseline is main e0c72367031d4ceadfb39c1577af71d21a55b8e5; its changes after merged phase3 affect only pilot-010 outputs, not these pinned pilot-006 sources. Before implementation, executor confirms remote baseline and raw bytes match these pins; divergence is not silently accepted.

- pilot-006/script.json: 1006e8bec3bc8c43dffe6e5ad1d26e257ceaea5fbe0eb12fa414b9c059d10cad
- pilot-006/out/timeline.json: 73357bd61adf13f004967f0a2b2ef3e16569fb2cd344eb419e3d1fcabf1af7a2
- pilot-006/shorts/inputs.json: 07a75a6b6849ed7ada9fc621a573b947689effc458693d6889ce3bc8568f514b
- pilot-006/images.json: f2e32a9a210ebd3d4f93d1d6fb9254ee2241d416784c9d31343c8f02138bb695
- pilot-006/out/manifest.json: 0d40777f7dd2a84db9615bd148df8c3173e2e46b9f7b32418e7677392e49a2bb
- pilot-006/out/review.json: e68b0ede86b2837d6070a18f20a17ad097be20d0636c427a4214c0f49324a00f
- voice asset pilot-006-voice-sha256-d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d.flac; SHA256 d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d
- music asset original-rest-music.lossless.flac; SHA256 1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c
- image 1 bg-still-water-night; asset pilot-006-img-bg-still-water-night-sha256-7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2.png; SHA256 7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2
- image 2 bg-healing-garden; asset pilot-006-img-bg-healing-garden-sha256-97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070.png; SHA256 97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070

Both PNGs were visually inspected and rehashed on 2026-10-21 around 00:40 UTC: moonlit pond and moonlit garden fountain; no person or text observed. Keep their painted appearance, explicitly retained for pilot-006 by R10. Keep source license/provenance receipts; do not generate substitutes. The figure input remains CLI-compatible but must never be composited.

## Closed plan values

Existing schema identifier remains shorts-006-correction-plan-v1. Reject missing, unknown, non-finite or altered closed fields. One candidate only, source_pilot pilot-006, title "Rest in God's Care", first-line hook "Let your face soften.", reference null. Retain the original script and all sentence text verbatim; do not attach the previous candidate's Philippians reference to this passage. The selector must accept this exact candidate with rejection reason null under its existing rules; null is not a permission override.

Narrative candidate start=813.728 and end=854.417, exactly the 12 complete sentences at original timeline indices 191:203 (zero-based, end-exclusive). Preserve every sentence through "Rest now." The first complete sentence ends 815.669, duration 1.941 seconds. The second ends 817.791; do not claim both opening sentences fit within 3 seconds. Narrative duration=40.689 seconds.

Separate audio_source_end=854.418, exactly 1 ms after the rounded narrative endpoint to preserve the complete native-timeline utterance and its remaining decay. This is source-exact extraction, not an acoustic exception or a newly invented segment boundary. The final nonzero native sample from timeline rounding is at 854.417333; next sentence starts 855.797 and must not enter the cut. The 976560-sample native reference and extraction match SHA256 e49a6b29b469a61298508e796b933a6ba87067427512649b28ed4d18fc9008af. Source FLAC extraction duration=40.690. tail_seconds=1.310 means padding after that extraction; narrative_tail_seconds=1.311 means time after the last word. output_seconds=42.000. Actual source voice verified by the executor:24000Hz mono,1529.993333 seconds, pinned SHA256. Extraction at native24000Hz is 976560 samples; resampling to output48000Hz yields 1953120 samples, padding=62880, output=2016000. Do not describe the source as48kHz. Reset sample timestamps, preserve rate, no retime, voice alteration or trimming of decay to manufacture a PASS. Music begins at MUSIC_OFFSET 1200+813.728=2013.728 and must contain 42 seconds through 2055.728. Preflight duration before encoding.

Use existing editorial ducking, loudness and limiter. Parameterize only the scoped audio end/duration and tail. Begin final mixed fade after audio_source_end relative to the cut (40.690), duration 1.310; never apply the legacy 40 ms pre-cut fade to the last spoken word. Existing music 2-second fade is preserved. Low end amplitude is only a measurement, not evidence that the ending sounds complete. The existing frozen RMS method and maximum 0.3-second leading/trailing inactivity rule remain mandatory. The source-exact extraction measured leading 0.13 seconds and trailing 0.29 seconds, PASS; these technical measurements are not a generated-MP4 QA verdict or watched review.

Scene1 bg-still-water-night: nominal[0,20.977]. Scene2 bg-healing-garden: nominal[20.977,42]. transition fade0.5. Output1080x1920,30fps,1260 frames. Existing half-up allocation: nominal split 629 frames; scene spans [0,637),[622,1260), fade 15 frames[622,637). No R3 exception. Camera phrase_push_in_v1 for both scenes, existing C1 progress from1.00 to1.08, derived from sentence boundaries with scene endpoints included.

Derived 42-second clocks replace the old material-specific numbers without changing measurement methods or tolerances: 1260 frames; first video PTS0, last1259/30; audio presentation2016000 samples; AAC packet_count1970, first_pts_samples=-1024, skip_samples1024, last_pts_samples2015232, last_duration_samples768, codec_frame_samples1024, continuous packet clock. Decode may expose2016000 or2016256 samples only when the existing packet-clock proof accounts for the final256 coded-padding samples; no arbitrary truncation or added content. A bounded synthetic42-second AAC clock check confirmed these packet values; it is not production QA.

## Continuous internal movement and renderer reuse

Factor the numerical composition core from opening_atmosphere into a private reusable helper. Preserve existing opening_atmosphere/opening_particles/write_opening_video outputs for005 exactly, including91frames/envelope. New scoped006 source-clip writer renders every scene frame, not91frames plus cloned frames. It uses the existing source-bound fog, blurred source-highlight light and deterministic particles for the entire scene with envelope1, seeds259006 and259007. Keep existing fog frequencies, drift, tint, light and dust limits and alpha cap0.18. Particles may leave the frame naturally; do not wrap or restart abruptly. Fog remains continuously animated even when a particle leaves.

Do not distort the fountain statue, flowers, moon or buildings. No guessed water mask or independently generated object. This is atmospheric internal motion, not a claim to have physically simulated the fountain stream. Actual watched review decides whether the result is convincing and lively enough. If it is not, preserve FAIL and correct the actual cause, never raise scores by inference.

Use two full-length lossless source clips in the already implemented serial FFV1 renderer, then the existing single xfade, then one original final encoder. No tpad cloned tail for either scene. Preserve threads caps, pixel range handling,1080p,30fps,CRF19,medium preset,AAC160k and48kHz. No added depth model or vendor. Keep captions once, KJV references and the original safe-area rules. Final picture continues moving to EOF; do not introduce black padding to manufacture an ending.

Before production, a bounded local diagnostic smoke on actual assets is allowed after this contract is accepted: sample representative clips/frames from each scene at start, middle and end, without provider. Inspect captions and atmosphere, not only pixel difference. This is not a substitute for full media qualification.

## Closed cinematic opening profile for scene 1

The owner requested a cinematic animated hook on 2026-10-21 at 07:56 UTC. Add only scenes[0].atmosphere.opening_profile="source_atmosphere_hook_v1" to the closed plan. Scene 2 has no opening_profile field and remains unchanged. No additional provider, asset, person, simulated water or new acceptance gate is introduced. The new plan digest binds this exact first-scene field; unexpected profiles, locations or extra fields fail closed. Existing continuous atmospheric motion remains throughout both scenes, beyond the opening.

Use the existing source-bound composition, blur, luminance, colors and alpha limits. Define t=frame/FPS, X=x/w and Y=y/h. Define S(u)=clamp(u,0,1)^2*(3-2*clamp(u,0,1)), P=S(t/3), and Tfog=t+4*P. Substitute Tfog for t only in the two existing fog terms. At and after 3 seconds Tfog=t+4, maintaining continuous drift rather than resetting the clock. Particle time remains t; no particle acceleration, restart, wrapping or parameter changes.

Define H=S(t/0.35)*S((3-t)/0.75) for 0<=t<3, and H=0 otherwise. Define C=0.32+0.36*P; G=exp(-((X-C)/0.22)^2-((Y-0.30)/0.20)^2); and M=1-S((Y-0.48)/0.06). Replace the existing source-highlight mask by max(highlights,0.85*H*G*M) before the unchanged downstream composition. The added highlight contribution is zero for Y>=0.54 and outside the opening; this does not require existing source illumination to be zero. Keep fog_alpha_max=0.09, light_alpha_max=0.06, dust_alpha_max=0.10 and alpha_cap=0.18, with the original blur, the original source-luminance highlight mask; the explicitly specified new Gaussian term is a procedural light overlay independent of source luminance, not a claim of physically simulated lighting, colors and source-image immutability. Do not treat the highlight mask as permission to increase opacity or create new objects.

Add keyword-only opening_profile=None to continuous_atmosphere, write_continuous_video and _atmosphere_composite while retaining all existing positional and keyword parameters. None preserves the previous implementation bitwise; the exact source_atmosphere_hook_v1 selects only the formulas above. Any other value raises INVALID_OPENING_ATMOSPHERE_PROFILE before rendering. Pass the profile through the renderer only for the exact pilot-006 correction adapter and scene 1. The ordinary pipeline, pilot-005, scene 2 and every None call remain unchanged. No workflow or preservation changes accompany this opening.

After contract acceptance and before full production, perform a bounded local visual smoke over 0–4 seconds on the actual pinned moonlit-pond source, with real crop, camera and caption composition, plus an otherwise identical None-profile control. Inspect actual frames at 0,0.35,1,1.941,2.25,2.967,3,3.033 and4 seconds, sampling by the renderer's established frame convention and recording actual frame indices/times. Visually inspect the sequence, not only isolated pixel differences: the hook must visibly move beyond camera zoom without a flash or an abrupt transition at 3 seconds. Confirm captions remain readable, no people are introduced and no water simulation is claimed. No provider call for this smoke. Technical and visual smoke evidence cannot substitute for complete-MP4 audiovisual QA and the existing watched review with overall>=9.

Additional required tests: bitwise unchanged pilot-005 opening and continuous None-profile output; continuity of the time/envelope formulas and rendered transition at frames89/90/91 (30fps); unchanged alpha limits; immutable source inputs; zero added highlight for Y>=0.54; unchanged scene 2; exact profile routing and rejection of invalid profiles. Do not invent a percentage-of-changed-pixels acceptance threshold or infer a watched-review score from technical tests. Preserve all prior tests, gates, allowed paths and frozen criteria.

## Exact proposed interfaces

New module migration/production/shorts_006_plan.py:
- validate_plan_schema(plan)
- validate_plan(plan, timeline, script, inputs, *, raw_sha256)
- frame_plan(plan)
- main(plan_path, timeline_path, script_path, inputs_path, out_path)
- check_media(work, plan, manifest, voice_flac, music, images_dir, history_path)
- finalize_file(manifest, mp4)
- binding(spec, *, plan_sha256, history_sha256)
- cli(argv=None)

CLI mirrors the existing005 adapter and uses only positional arguments:
1. python migration/production/shorts_006_plan.py PLAN TIMELINE SCRIPT INPUTS SELECTION_OUT
2. python migration/production/shorts_006_plan.py --check-media WORK PLAN MANIFEST VOICE_FLAC MUSIC IMAGES_DIR HISTORY_PATH
3. python migration/production/shorts_006_plan.py --finalize MANIFEST MP4

The producer's public signature and CLI stay compatible. Its existing edit_plan keyword accepts this second closed discriminator through a private adapter selector. Reject unknown discriminators; do not weaken005 validation. Share generic measurement and atomic JSON helpers where safe rather than copying large implementations; no change to frozen QA/review code or thresholds.

The selection output contains exactly one original complete narrative candidate plus the bound correction plan. Producer writes selection.json and shorts.json using its existing output convention. The existing Preserve workflow step, not the producer, generates short-00-frame.jpg. Filename of the new MP4 is short-00.mp4. Never invent its hash before it exists.

Check-media binds plan/hash/history/source hashes, complete source duration, actual geometry/fps/frames/PTS/PCM/captions/motion metadata and actual MP4 hash. It rejects the prior FAIL hash and any hash previously reviewed FAIL in the pinned history. Preserve existing black-frame, source and output integrity checks without relaxation. QA checks and reviewer both use pre/post hash equality; finalizer matches all hashes to actual bytes. Reuse existing review invocation, prompt/rubric/model/retries unchanged.

Finalization starts by revoking eligibility atomically. It accepts one record only, real QA PASS, real review PASS, overall>=9 with existing item thresholds, valid source/long approval, bound measurements and actual bytes, valid deadline/target, no FAIL hash. It then generates finalization.kind='pilot-006-correction-v1', status='COMPLETE', source_pilot, plan_sha256, history_sha256, output_sha256, target_slot, release_deadline, validated_at and release_status='READY'. Fields are generated, not manually filled. At or before13:15:00 may qualify;13:15:01 fails closed. Publication still requires the existing remaining editorial/provenance/license/metadata/channel gates.

The exact canonical PLAN digest supplied below must be pinned in implementation/tests/report before review. It was calculated from the supplied newline-terminated JSON, not invented. History pin above is known and must be exact. Runtime plan and history files must match their pinned digests; record-only assertions are insufficient.

## Operational integration

In the existing shorts.yml select/produce/review step, add a branch for pilot-006 plus the exact correction-plan.json. Validate plan and sources, produce one, check media, review one, finalize automatically. Do not fall into legacy select3 if the correction plan exists but is invalid. Preserve all other branches. No edits to workflow triggers, inputs, permissions, concurrency or schedule. Keep the existing preservation step, archiving the historical manifest first as a tracked immutable file. Its run body must additionally copy the generated correction-media-checks.json from the work directory to pilot-006/shorts/correction-media-checks.json; the present step does not copy this file. Its existing frame extraction remains responsible for short-00-frame.jpg. These run-body changes are allowed; triggers/inputs/permissions remain byte-identical.

In pending_shorts.recovery_gate, preserve the directory/path/symlink/context checks. Select the correction binding only for exact finalization.kind='pilot-006-correction-v1'; validate pinned plan/history files and deadline. Otherwise call existing review_recovery.binding unchanged. Malformed correction metadata must never fall back to the historical gate. Existing uploaded IDs remain handled before new-upload eligibility.

In publish_shorts.recovery_upload_gate, reuse that guard and keep exactly one publishable record, matching output hash, filename, target and slot. Confirm actual MP4 bytes before upload. Preserve idempotent ledger/readback handling, no reupload of an existing/uncertain ID. No modification of review_recovery.py or old pinned FAIL inputs is needed. The new binding authorizes only corrected bytes that genuinely passed gates, not an override of the old FAIL.

## ALLOWED PATHS for this phase

migration/production/shorts_produce.py
migration/production/test_shorts_produce.py
migration/production/shorts_006_plan.py
migration/production/test_shorts_006_plan.py
migration/production/pilot-006/shorts/correction-plan.json
migration/production/pilot-006/shorts/correction-history.json
migration/production/pilot-006/shorts/correction-media-checks.json
migration/production/pilot-006/shorts/selection.json
migration/production/pilot-006/shorts/shorts.json
migration/production/pilot-006/shorts/short-00-frame.jpg
migration/publish/pending_shorts.py
migration/publish/test_pending_shorts.py
migration/publish/publish_shorts.py
migration/publish/test_publish_shorts.py
.github/workflows/shorts.yml
.github/workflows/pr-checks.yml

migration/evidence/owner-quality-policy/phase2-report.md

This is the existing authorized report path. selection.json, correction-media-checks.json, shorts.json and short-00-frame.jpg are generated outputs only. History is copied byte-identically; source input files and criteria are not editable. MP4 is preserved through the existing verified release-asset interface, not a new arbitrary repository path.

## ACCEPTANCE and known answers

- Validate fixed source hashes, exact history bytes and actual image/voice/music hashes, with trailing newline counted. Wrong/missing/symlink/nonfinite/unknown fields fail closed.
- Exact arithmetic:40.689 narrative,40.690 FLAC,1.310 padding,42.000 output;1953120+62880=2016000 samples;1260frames;spans [0,637),[622,1260);nominal split629;15-frame fade;first line 1.941 seconds. Native extraction 976560 samples; narrative tail 1.311 seconds; unchanged RMS 0.3-second limit requires actual measurement. No boundary truncation, retiming, acoustic exception or new acceptance method.
- Negative source/music truncation blocks before render/provider; next spoken sentence excluded. Tests distinguish narrative end from extraction end and captions never extend into padding.
- Actual producer command uses full animated inputs for both scenes, no tpad/cloned remainder, capped threads, original encoding settings and one final audio pipeline.
- Atmospheric helper is deterministic, does not mutate source, preserves limits and nonzero internal temporal change at t>3 and near the end of both scenes. Test outside active composition/invalid dimensions, not only visual score proxies.
- Confirm serial output equivalence against the two-source reference for frames/PTS/PCM and cross-version range semantics. Use valid-duration fixtures and a bounded FullHD real command; retain resource/invalid-fixture evidence honestly.
- Pin and compare existing005 procedural output and legacy CLI commands. Existing005/ordinary adapters and recoveryFAIL logic remain unchanged.
- Check-media rejects historical FAIL MP4, changed bytes, bad source hash, missing history and wrong plan. Provider spy must remain zero for pre-review failures.
- Finalizer rejects QA FAIL, reviewFAIL, overall8.99, missing watched review, changed MP4, mismatch among QA/review/media/output hashes, second candidate and late clock. Positive fixture9.0 must pass only with all other gates valid.
- pending/publisher reject forged/mismatched correction binding, wrong pilot/path/plan/history, reused oldFAIL, extra record/slot and expired deadline. Existing uploaded/uncertain IDs never cause another upload.
- Inspect workflow AST: triggers, inputs, permissions, concurrency and schedule exactly unchanged;006 invalid plan cannot reach select3. No provider invocation in tests.
- Run relevant full suites, independent review, exact-SHA CI, remote byte/hash checks. The one phase3 production render is now completed and preserved. Do not repeat it. Phase4 must obtain actual watched review>=9 and all gates on those same bytes before existing scheduling/publication readback.

## Historical phase3 production checks (render completed; media gates still binding)

1. Canonical plan and digest are now supplied below; the literal existing report path is included above. No technical authorization gap beyond contract publication is claimed.
2. Music duration independently verified by the executor: original-rest-music.lossless.flac has the pinned SHA256 and ffprobe duration10800.000000 seconds, sufficient for2013.728–2055.728. Actual voice FLAC also verified by the executor: pinned SHA256,24000Hz mono,1529.993333 seconds. Inspected image hashes match.
3. Inspect smoke frames and temporal samples; record audio smoke as NOT_REVIEWED when perceptual audio is unavailable. Acoustic measurements are technical only. Mandatory audiovisual watched review remains on the complete newly rendered MP4 through the existing designated reviewer, after code gates and before any eligibility/publication. No extra smoke provider call. The planned motion and longer tail do not guarantee editorial9 or physical realism. Correct genuine defects without inventing pass evidence or altering criteria.

## Closed routing choice (mandatory)

Implement one private producer resolver `_editorial_adapter(plan)`: exact version `shorts-006-correction-plan-v1` AND source_pilot `pilot-006` selects shorts_006_plan; exact existing005 version AND pilot005 selects shorts_edit_plan; every other pair raises before render. Both adapters still validate their complete closed schemas. Replace direct005 imports in each existing scene_frame_plan/editorial_picture/render/produce/main validation site with this resolver; do not infer scope merely from edit_plan presence. Tests enumerate every call site and wrong/mixed version/pilot pair. Shared serial FFV1 writer and final encoding remain one implementation. Where005-only measurement assumptions exist (8scenes,10sentences,referenceNone,20UTC slot),006 owns explicit two-scene/source-aware validation instead of passing through005's validator or relaxing it. Generic numerical helpers may be reused only if they do not embed005 constants.

## Exact canonical plan artifact

Proposed file:correction-plan-v6.json. Repository destination after contract approval: migration/production/pilot-006/shorts/correction-plan.json. UTF-8, ensure_ascii=False, indent2, one terminal newline. SHA256: 95624da1b4e4e4b256faee29fb37c8bc78fdb5c9747a3be86c69d9ec0e319905. Byte count: 3489. Reject a raw-byte hash mismatch even if parsed JSON is semantically similar.

The following object defines ALL allowed fields recursively; no arbitrary extra keys. Numeric values are exact finite values (not booleans); file/hash/identifier strings must match literally. The audio object separates candidate sentence bounds from FLAC extraction, resampling and padding. The scene atmosphere object specifies the new full-duration procedural profile. Neither schema is accepted by005: route solely through the closed006 adapter.

```json
{
  "version": "shorts-006-correction-plan-v1",
  "source_pilot": "pilot-006",
  "source_baseline_sha": "582ff607089f9accb91a8a4d1a8c2fe6f4e47408",
  "source_sha256": {
    "script": "1006e8bec3bc8c43dffe6e5ad1d26e257ceaea5fbe0eb12fa414b9c059d10cad",
    "timeline": "73357bd61adf13f004967f0a2b2ef3e16569fb2cd344eb419e3d1fcabf1af7a2",
    "inputs": "07a75a6b6849ed7ada9fc621a573b947689effc458693d6889ce3bc8568f514b",
    "images": "f2e32a9a210ebd3d4f93d1d6fb9254ee2241d416784c9d31343c8f02138bb695",
    "long_manifest": "0d40777f7dd2a84db9615bd148df8c3173e2e46b9f7b32418e7677392e49a2bb",
    "long_review": "e68b0ede86b2837d6070a18f20a17ad097be20d0636c427a4214c0f49324a00f"
  },
  "history": {
    "file": "correction-history.json",
    "sha256": "4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677",
    "rejected_output_sha256": "9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707"
  },
  "voice": {
    "asset": "pilot-006-voice-sha256-d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d.flac",
    "sha256": "d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d"
  },
  "music": {
    "asset": "original-rest-music.lossless.flac",
    "sha256": "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c",
    "source_start": 2013.728
  },
  "candidate": {
    "start": 813.728,
    "end": 854.417,
    "hook": "Let your face soften.",
    "title": "Rest in God's Care",
    "reference": null
  },
  "audio": {
    "source_start": 813.728,
    "source_end": 854.418,
    "source_sample_rate": 24000,
    "source_channels": 1,
    "source_samples": 976560,
    "output_sample_rate": 48000,
    "resampled_source_samples": 1953120,
    "padding_samples": 62880,
    "output_samples": 2016000,
    "fade_start": 40.69,
    "fade_seconds": 1.31
  },
  "tail_seconds": 1.31,
  "narrative_tail_seconds": 1.311,
  "output_seconds": 42.0,
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "transition": {
    "type": "fade",
    "seconds": 0.5
  },
  "scenes": [
    {
      "image_id": "bg-still-water-night",
      "asset": "pilot-006-img-bg-still-water-night-sha256-7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2.png",
      "sha256": "7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2",
      "nominal_start": 0.0,
      "nominal_end": 20.977,
      "motion_profile": "phrase_push_in_v1",
      "atmosphere": {
        "profile": "source_atmosphere_continuous_v1",
        "seed": 259006,
        "envelope": 1.0,
        "alpha_cap": 0.18,
        "fog_alpha_max": 0.09,
        "light_alpha_max": 0.06,
        "dust_alpha_max": 0.1,
        "opening_profile": "source_atmosphere_hook_v1"
      }
    },
    {
      "image_id": "bg-healing-garden",
      "asset": "pilot-006-img-bg-healing-garden-sha256-97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070.png",
      "sha256": "97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070",
      "nominal_start": 20.977,
      "nominal_end": 42.0,
      "motion_profile": "phrase_push_in_v1",
      "atmosphere": {
        "profile": "source_atmosphere_continuous_v1",
        "seed": 259007,
        "envelope": 1.0,
        "alpha_cap": 0.18,
        "fog_alpha_max": 0.09,
        "light_alpha_max": 0.06,
        "dust_alpha_max": 0.1
      }
    }
  ],
  "release": {
    "target_slot": "2026-10-21T14:00:00Z",
    "release_deadline": "2026-10-21T13:15:00Z",
    "minimum_overall": 9.0,
    "file": "short-00.mp4"
  }
}
```

## Preserve scope guard

Only two existing shorts.yml run bodies may change: select/produce/review and Preserve. In pr-checks.yml, only add migration/production/test_shorts_006_plan.py to the existing test loop; all other bytes remain unchanged. In the006 correction branch, replace broad frame cleanup with cleanup of short-00-frame.jpg only. Preserve tracked short-01-frame.jpg and short-02-frame.jpg byte-identically and preserve historical records through the pinned archive. No glob removal of historical frames, no deletion of other pilots or artifacts. Tests inspect the006 command branch and compare tracked01/02 hashes. Existing non006 behavior remains unchanged.

## Mandatory one-attempt canonical preflight

Additional exact CLI: python migration/production/shorts_006_plan.py --preflight PILOT_DIR PLAN HISTORY_PATH. Python interface preflight(pilot_dir, plan_path, history_path). Before prepare/render/provider, require PILOT_DIR resolves to the authorized pilot-006 directory, exact closed plan raw digest, exact pinned history bytes, and PILOT_DIR/shorts/shorts.json raw SHA256=4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677. Reject missing plan even on006; it must never fall back to select3. Reject symlinks/traversal and source pin mismatch. After any new result is persisted, canonical hash changes, so another attempt is blocked pending a new precise contract. An uncertain execution or failed preservation requires reconciliation, not redispatch even if canonical bytes did not change; executor must check authoritative run state and artifacts before dispatch. This preflight is not an exactly-once claim across an unpersisted run. Test changed canonical PASS, FAIL, NOT_REVIEWED and malformed bytes all fail with zero render/provider calls.

## Additional closed interface and binding details

The006 adapter exposes hash_file(path) and read_json(path) with the same semantics as the existing neutral helpers. It may import those helpers, never monkeypatch005 constants. Existing005 measure_video invokes005-specific validation and must not be reused wholesale; reuse only neutral measurement primitives and implement explicit006 duration/frame/audio validation against audio.source_end, not the narrative end.

check_media writes correction-media-checks.json beside MANIFEST, using atomic_json, and binds the same generated measurement object/hash into the manifest. The006 Preserve branch copies that exact file from RUNNER_TEMP/work/shorts to the authorized canonical shorts directory together with selection.json and shorts.json. Missing or mismatched measurements block preservation/release.

binding revalidates the complete finalization schema and all nested QA/review/media/record gates against the actual pinned plan/history files and their raw hashes, not merely kind/status or asserted digests. Reject correction edit_plan with missing/wrong finalization kind, correction finalization with005 plan, and any simultaneous review_recovery or owner_exception fields. Tests forge READY/publish=true while changing QA toFAIL, review to8.99, media hash, plan identity or nested measurements and require zero session/upload. No binding asserts a PASS based only on its own existence.

## Persisting legitimate non-eligible results

A well-formed real QA FAIL, review FAIL, overall below9, NOT_REVIEWED provider result or expired cutoff is not a CLI integrity exception: finalizer records finalization.status COMPLETE, publish=false and a categorical release_status/reason, preserves original evidence, and returns exit0 so the existing Preserve step records the new manifest. COMPLETE means evaluation completed, never eligibility by itself. READY is emitted only for all gates PASS. Malformed evidence, hash mismatch or unreadable media instead records ERROR with publish=false and exits1; treat failed preservation as an uncertain outcome requiring reconciliation, never repeat against unchanged canonical bytes. Tests cover both exit semantics and workflow preservation of legitimate negative results. No failed review is promoted or suppressed.

## Historical phase3 acceptance commands (not an instruction to repeat completed tests)
Run from repository root with configured Python environment (numpy/opencv available):
python3 -I -B migration/production/test_shorts_006_plan.py
python3 -I -B migration/production/test_shorts_produce.py
python3 -I -B migration/production/test_shorts_edit_plan.py
python3 -I -B migration/publish/test_pending_shorts.py
python3 -I -B migration/publish/test_publish_shorts.py
python3 -I -B migration/publish/test_review_recovery.py
git diff --check
Each command must exit0 and report all tests successful. Additionally run the repository test-file loop, card_check, dot_scope against this card, frozen-file hash comparisons, independent review and exact-SHA HeroVerse PR checks. Record commands, actual outputs and SHA. Generated media is not qualified by these software tests.


# Current phase 4 — one corrected-006 review-only recovery

No render, added retry loop, fallback, publication or refused archive change. One review invocation retains only its existing internal retries.

## Evidence and fixed pins
Run39569442793 ended2026-10-21T08:41:51Z;42s MP4 preserved, QA/acousticPASS, provider503 without editorial verdict. Baseline89541e4cd3232195e8f626d8419b023cc0cd3317:
- source_manifest_sha256: a33d46db02ee419c357ae4ecefeee615b3d6ac32af143e85814cfbcb82bd1418 (raw shorts.json including newline).
- media_sha256: 6d3f0199f1ea9b0b22a87dbb29b9abfa7a3632f74488d6f1be990a9b46e00200 (raw correction-media-checks.json).
- output_sha256: 96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e; short-00.mp4,20,581,582bytes.
- previous failed_at:2026-10-21T08:41:45.362893+00:00; http_status503,provider_statusUNAVAILABLE.
- not_before:2026-10-21T08:51:45Z; cutoff:2026-10-21T13:15:00Z; target_slot:2026-10-21T14:00:00Z.
not_before is 9min59.637107s after failed_at, not >=600s or proof of recovery. One review, never FAIL bytes.

## Current allowed subset and interfaces
Edits: shorts_006_plan.py, test_shorts_006_plan.py, phase2-report.md audit, two shorts-review.yml run bodies, and only test_workflow_only_two_run_bodies_changed in migration/publish/test_review_recovery.py, using full union paths above. Update that historical routing assertion/normalization to the new two bodies, preserving its baseline SHA256 caf36ac8c64f23eebdf71fe0eb7e2418170b108f102eed532d1c20edc1bb892d and every assertion for unchanged workflow bytes. Do not normalize unrelated differences or remove the test. Runtime output only canonical pilot-006/shorts/shorts.json via unchanged Record; other files/workflow fields unchanged.
New signatures:
- def recovery_preflight(pilot_dir, *, now_utc):
- def recovery_list(pilot_dir):
- def recover_review(pilot_dir):
CLI: --recovery-list PILOT_DIR; --recover-review PILOT_DIR. Real datetime.now(timezone.utc), no clock/hash/run override. now_utc injection only in tests; identity from GITHUB_RUN_ID/GITHUB_RUN_ATTEMPT.
Reuse existing validators, atomic_json/finalize_file, shorts_review.review/failure_record, owner_quality_policy.check. Never call producer preflight/check_media, shorts_review.main or old wrapper.

## Preconditions and fresh QA
Canonical nonsymlink pilot-006, one short-00.mp4; exact raw manifest/media pins. _contract verifies source/plan/history/qualified-long pins; _bind_record/validate_media_checks bind MP4, QA and metadata. finalization kind=pilot-006-correction-v1,status=COMPLETE; all release_status fields REVIEW_NOT_REVIEWED; publish=false. Exact original503 review including clock/diagnostic/hash, no scores/audit/FAIL for these bytes. _evaluate must return REVIEW_NOT_REVIEWED with QA PASS.
List validates one record and documents, not unavailable local MP4, and prints file/hash. Review requires regular nonsymlink MP4 after download; requires positive decimal GITHUB_RUN_ID different from source, GITHUB_RUN_ATTEMPT="1", no active/uncertain review and real UTC in window immediately before provider.
Hash and size actual MP4, run unchanged shorts_qa.check, rehash. Require fresh _qa_verdict(qa,42.0)==PASS/allchecks true. Original qa/qa_output_sha256 unchanged; audit keeps real fresh QA (localpath/measurements may differ). Same thresholds, original measured_at<=now and same UTC day.
Key/QA/rehash/preflight before STARTED; failure leaves source byte-identical, exit1, local sanitized diagnostic/QA only, no audit or Record promise.

## Closed audit schema
Only new metadata: correction_review_attempt. Closed keys/types; no nonfinite/bool-as-int. Recursive review_recovery/review_recovery_execution/owner_exception prohibition unchanged.
- version:string literal shorts-006-review-attempt-v1.
- source_run_id:string literal39569442793; run_id:positive decimal string distinct from source; run_attempt:int1.
- source_manifest_sha256/media_sha256/output_sha256:hex64 exact pins above.
- not_before/cutoff/target_slot:exact UTC strings above.
- started_at:actual ISO UTC string; completed_at:null inSTARTED, actual ISO UTC >=started_at at completion.
- state:STARTED|COMPLETE|ERROR.
- previous_review:deep-equal entire source503 review dictionary, including sanitized diagnostic; never raw provider body.
- fresh_qa:actual check() result validated by _qa_verdict, statusPASS; originalQA stays unchanged.
- reason:null forCOMPLETE; ERROR enum INPUT_CHANGED|OUTPUT_CHANGED|FINALIZATION_ERROR|OUTPUT_WHITELIST_VIOLATION|OPERATION_ERROR. Never exception prose/secrets.
Pure audit validation in _evaluate covers finalize_manifest/finalize_file/binding: exact schema/pins/previous_review, _qa_verdict and chronology. STARTED/ERROR neverREADY. Finalizer candidate: COMPLETE,reason=null,real completed_at>=started_at. Ordinary flows unchanged. Only the pinned 96c826…7b6e output PASS/FAIL requires audit; original503 withoutaudit only noneligible input.

## One attempt, atomic result, bounded differences
After prechecks atomically store STARTED/publish=false and retain original snapshot/STARTED hash. Invoke shorts_review.review(mp4,deepcopy(record),key) once; existing internal retries/model/prompt/rubric frozen, no added retry. Exceptions use failure_record; previous503 exact.
After call rehash MP4/revalidate contract/media/STARTED bytes; concurrent change forbids overwrite. Exclusive untracked candidate beside manifest gets realreview/computedpolicy/COMPLETE audit; finalize_file(candidate,mp4), recheck identities/whitelist, atomic install, remove temporary. No partialREADY.
Diff whitelist: top-level correction_review_attempt,finalization,release_status,publish; record review,owner_quality_policy,release_status,publish only. All else exact, including QA/media/measured_at/text/edit_plan/selection/render_plan. No other file mutation. Persist integrity ERROR only while canonical is this run’s state; otherwise reconcile.
After finalize_file and slow checks, read real UTC immediately before canonical install. If cutoff crossed, automatically finalize using that actual instant: COMPLETE,publish=false,TARGET_SLOT_LEAD_MISSED, retaining real review/audit; exit0 for Record. completed_at/validated_at follow actual sequence, not old timestamps; same-day/media chronology remains required. CLI never accepts clock override. Expiry is not integrity ERROR.
FAIL/503/PASS<9 consume attempt, stay ineligible. COMPLETE negatives exit0 for Record; integrity/unknown exit1. Pins/audit/run_attempt block reruns. Crash before Record can leave old remote bytes after provider: failed Record/cancel/unknown require reconciliation, no redispatch. No exactly-once claim.

## Exact two run bodies
Replace only download run body; malformed006 never falls back:
```bash
set -euo pipefail
case "$PILOT" in pilot-[0-9][0-9][0-9]) ;; *) exit 1;; esac
sudo apt-get install -y -qq --no-install-recommends ffmpeg >/dev/null
d="migration/production/$PILOT/shorts"
if [ "$PILOT" = pilot-006 ]; then
  python3 -I -B migration/production/shorts_006_plan.py --recovery-list "migration/production/$PILOT"
else
  python3 -I -c "import json,sys;[print(s['file'],s['sha256']) for s in json.load(open(sys.argv[1]))['shorts']]" "$d/shorts.json"
fi |
while read -r f sha; do
  gh release download "$TAG" --repo "$GITHUB_REPOSITORY" --pattern "$PILOT-${f%.mp4}-sha256-$sha.mp4" -O "$d/$f"
  echo "$sha  $d/$f" | sha256sum -c -
done
```
Watched review step:
```bash
set -euo pipefail
if [ "$PILOT" = pilot-006 ]; then
  python3 -I -B migration/production/shorts_006_plan.py --recover-review "migration/production/$PILOT"
else
  python3 -I -B migration/production/shorts_review.py "migration/production/$PILOT/shorts" 3
fi
```

## Acceptance
Run test_shorts_006_plan.py plus existing full code/remote-hash/independent-review/exact-SHA CI gates; no provider in tests.
Negatives before call: FAIL current/prior, wrong hash/pilot/file, completed review,429/unknown error, missing key, prior audit, attempt2, stale/future media, source change, QA FAIL/decode/hash change. Precheck failures preserve original manifest. Test time boundaries, no CLI override and expiry DURING finalization producing durable COMPLETE negative. Test source/media/manifest/MP4 races, no partial READY on atomic/finalizer errors, exact previous503, closed audit/whitelist/prohibited keys, removed audit from recovered PASS/FAIL, STARTED/ERROR forged eligibility. Positive >=9 requires every gate;8.9/FAIL/503 never eligible. Test original/fresh QA, two-body-only YAML diff, non006 invariance, no006 fallback/render.
After code gates/merge and idle check, run shorts-review.yml pilot006 once in window; verify remote result. Unknown blocks repeat; publication gates/14UTC unchanged.

</details>

## SPEC v8 phase5: bounded rest metadata correction (2026-10-21)

The one phase4 recovery run39575597092 recorded a second HTTP503_UNAVAILABLE at09:17:47.236719UTC, preserving the original failure and fresh QA PASS. Commit94e652d55248e4395f85e187a35c319f358b9854 retains publish=false and REVIEW_NOT_REVIEWED. This metadata change does not authorize another provider invocation, render, upload, or quality exception. No score exists for the preserved96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e MP4.

The existing generic publisher incorrectly described this rest/reflection clip with morning-prayer tags. New metadata_for is formatting only, restricted to exact pilot006/hash96c. It emits the approved rest title, neutral rest description and six exact tags. Other pilots and historical IDs retain legacy behavior. Existing IDs continue GET-only even after cutoff or absent local media/identity fields; inconsistent local identity becomes UNKNOWN, never another upload. New uploads retain full correction binding, QA, actual hash, designated watched review, additional overall>=9, channel, slot and deadline gates. Optional tags are read back only for this closed profile and automatically persisted inside the existing observation structure; no separate snapshot or ledger schema authority is added.

FILES (complete):
- migration/publish/publish_shorts.py
- migration/publish/test_publish_shorts.py
- migration/evidence/owner-quality-policy/phase2-report.md

ACCEPTANCE executed against actual implementation bytes:
- /tmp/hv228-venv/bin/python -I -B migration/publish/test_publish_shorts.py: 58 tests PASS. Root personal execution:58 tests1.755s OK, exit0; independent reviewer:58 tests1.283s OK.
- /tmp/hv228-venv/bin/python -I -B migration/publish/test_pending_shorts.py:13 tests PASS,0.080s; independent reviewer also PASS.
- /tmp/hv228-venv/bin/python -I -B migration/production/test_shorts_006_plan.py:33 tests PASS,3.526s; independent reviewer also PASS.
- Existing PR loop:48 test files all PASS, aggregate exit0. Logs retained in /tmp/259-v8-tests. Synthetic outputs are fixtures, not real uploads or media approval.
- Antidote against the unchanged prior publisher in a temporary copy: old exit1 with wrong morning description/tags; current exit0 with the exact rest description/tags. No weakening or skipped assertions. The initial historical positive fixture used a synthetic hash outside the new closed profile; it was adjusted by patching the profile pin only in that fixture, without live pilot data or changes to production criteria.
- card_check: CARD_OK. dot_scope: IN_SCOPE3 files. git diff --check: PASS.17 frozen files including all QA criteria, rubric/reviewer/adapters and relevant media gates remain byte-identical; all workflows unchanged.
- Independent static review confirmed the original verification core AST is unchanged after extraction to _verification, and legacy title/description/gates are intact. Contract review PASS for SPECv8 SHA2561224992dd66008db4aa47ea6076cf29adc2561fb7fe4497b2a1d9f0373a957b4. Source-body archive above is verbatim, not current execution authority.

Remote delivery SHA, byte hashes and CI are recorded in the PR acceptance comment once those operations complete. They were pending when this report was prepared. No DONE, publication, review score, or scheduled upload is claimed.


## SPEC v8 verbatim archive before phase 6

Archived before consolidation on 2026-10-21. These are historical instructions, not competing active rules. UTF-8 bytes: 58880; SHA256: 1224992dd66008db4aa47ea6076cf29adc2561fb7fe4497b2a1d9f0373a957b4.

<!-- BEGIN SPEC V8 VERBATIM -->
# SPEC v8 — Owner quality floor and pilot-006 rest metadata
## GOAL
Enforce the owner's additional overall >=9 requirement for every future new long/Short upload, without changing frozen QA or the existing reviewer rubric; deliver one corrected pilot-006 Short after actual historical review FAIL, preserving the completed diagnostic and recovery evidence.
## Authority and priority
Direct owner instruction Sentinel_efdcc18966988191b93f7ad0f0b6de38 at 2026-10-20T20:14:14.608652+00:00: “Pode postar mais os próximos quero 9 pra cima.”
Temporary technical direction was delegated directly on 2026-10-20 at15:56:57 UTC. This is the sole active execution; #257 remains BLOCKED for formal post-upload verification, not DONE. #231 body is not edited. The already uploaded pilot-005 hash cb3ce331529437f4fadc3b14dec01dfad18909a3e9f024a99cea141e91ae956f is not invalidated or uploaded again.
## INPUTS
Baseline main 767badb5f99ef89274693813bd2e8ea1ec76f22c; DOT_PROTOCOL; existing publish/production tests; pilot-006 shorts manifest and run39453449948 logs; existing ledger and receipts read-only.
## ALLOWED PATHS
```allowed
migration/publish/owner_quality_policy.py
migration/publish/test_owner_quality_policy.py
migration/publish/pending_shorts.py
migration/publish/test_pending_shorts.py
migration/publish/publish_shorts.py
migration/publish/test_publish_shorts.py
migration/publish/publish_video.py
migration/publish/test_publish_video.py
migration/publish/test_first_comment.py
migration/production/shorts_review.py
migration/production/test_shorts_review.py
migration/evidence/owner-quality-policy/report.md
migration/evidence/owner-quality-policy/pilot-006-diagnosis.json
migration/publish/review_recovery.py
migration/publish/test_review_recovery.py
migration/evidence/owner-quality-policy/pilot-006-selection.json
migration/evidence/owner-quality-policy/phase2-report.md
migration/production/pilot-006/shorts/shorts.json
.github/workflows/shorts-review.yml
migration/production/shorts_produce.py
migration/production/test_shorts_produce.py
migration/production/shorts_006_plan.py
migration/production/test_shorts_006_plan.py
migration/production/pilot-006/shorts/correction-plan.json
migration/production/pilot-006/shorts/correction-history.json
migration/production/pilot-006/shorts/correction-media-checks.json
migration/production/pilot-006/shorts/selection.json
migration/production/pilot-006/shorts/short-00-frame.jpg
.github/workflows/shorts.yml
.github/workflows/pr-checks.yml
```
Phases 1–4 implementation and execution are completed. Their paths remain in the audit union, not permission to repeat execution. Current phase 5 changes only migration/publish/publish_shorts.py, migration/publish/test_publish_shorts.py and migration/evidence/owner-quality-policy/phase2-report.md (audit only). All workflows, triggers, inputs, permissions and other workflow fields remain unchanged.
## INTERFACES
```interfaces
migration/publish/pending_shorts.py: def approved(s):
migration/publish/publish_shorts.py: def main(shorts_json, shorts_dir, long_key, ledger_path, receipt_path, slots):
migration/publish/publish_video.py: def main(package_path, manifest_path, video, thumbnail, ledger_path, receipt_path, publish_at=None):
migration/production/shorts_review.py: def main(shorts_dir, n="3"):
migration/production/shorts_review.py: PASS_ITEM, PASS_OVERALL = 7, 8
```
## EXACT VALUES
Add pure owner_quality_policy.check(review, output_sha256) returning a list of categorical problems. Require a dictionary, status PASS, model gemini-3.8-flash, overall finite int/float excluding bool, 9.0<=overall<=10.0, and review.output_sha256 equals a valid lowercase64hex actual/bound output_sha256. It adds an eligibility gate, not a reviewer score or approval.
Shorts: post-review selection applies this gate; record owner_quality_policy result separately without rewriting review verdict/rubric. pending_shorts.approved requires publish is True, QA.status PASS and the same policy; states reports owner_quality_policy_blocked distinctly from review_by_undesignated_model, with existing video_id evaluated first. New upload publisher checks policy before credentials/session/POST, including direct invocation and stale manifest. Existing video_id path remains readback-only and is not rejected retrospectively due to the new score floor; never reupload. Preserve existing records for readback even when their local publish flag is false; missing local MP4 after cleanup does not require another upload. An existing uploaded record can remain in the published/ scheduled state independently of eligibility for NEW uploads.
Long: publish_video main loads review.json from the manifest file's parent for a NEW upload, computes SHA256 from actual VIDEO bytes (streaming), requires that actual hash equals manifest.output_sha256 and top-level review.output_sha256 with top-level status PASS, then supplies a new in-memory copy of watched_review with output_sha256 set from the validated top-level hash to the helper. The original review file/object is never rewritten. All checks run before session/credentials/POST. Missing or malformed evidence fails closed. Existing ledger video_id resumes unchanged, no extra upload and no retroactive threshold enforcement. Do not alter publication_binding or prepublish_gate frozen rubric. This final-upload gate also covers already prepared but not uploaded old approvals.
Only the todo (new upload) records receive rehash, policy and QA checks; cached policy results, publish flags and finalization markers never substitute for those checks. Existing OwnerException tests that expected a NEW8.5 upload must become explicit rejection tests; reservation/durability positives use synthetic>=9 records while already CONSUMED8.5 readback remains covered. This is the new owner requirement, not weakening any acceptance.
No whitelist authorizes a new8.5 upload. The consumed005 exception remains historical only. Existing9.0/9.3 long uploads are unchanged.
Preserve frozen QA bytes, PASS_ITEM/PASS_OVERALL, prompt AST, reviewer models and retry behavior. Do not change the ordinary temporal finalizer or slots.
Diagnostic JSON contains only verified run/SHA/status/hash evidence, sources and unknown reasons. Exact HTTP cause for old006 is null if logs/code discarded it, not inferred503. Preserve old verdicts and assets.
Phases 1–4 completed without current media eligibility: corrected render run39569442793 preserved the new MP4 and a provider503; the single review-only recovery run39575597092 returned a second503, not an editorial PASS or FAIL. Its provider permission is consumed. Current phase 5 is metadata-only and does not authorize another review, render or upload. Publication still requires all real gates and fixed-slot checks.
Fixtures in test_first_comment.py may be updated only to provide valid synthetic raw hashes and bound PASS9 review; keep all original assertions and behaviors. New tests must explicitly cover real VIDEO bytes differing from matching stale manifest/review hashes, with zero session/upload calls.
## QUALITY BAR
Fail closed on missing evidence; no fabricated scores, no new routine human approval, no duplicate uploads. An additional policy rejection is not an editorial FAIL and must not rewrite the original review. Honest audit of old lost diagnostics and evidence limitations.
## ACCEPTANCE
python3 -I -B migration/publish/test_owner_quality_policy.py
python3 -I -B migration/publish/test_pending_shorts.py
python3 -I -B migration/publish/test_publish_shorts.py
python3 -I -B migration/publish/test_publish_video.py
python3 -I -B migration/production/test_shorts_review.py
Full existing PR test loop; card_check; dot_scope; git diff --check; remote exact bytes/newline; independent review; CI exactSHA.
Known answers:9.0 PASS,8.99/8.5 reject,10PASS,>10/NaN/inf/bool/missing reject, wrongmodel/status/hash reject; old PASS8.5 cannot appear as new pending upload or invoke session/upload; existingID8.5 causes zero new uploads and preserves readback. Long missing/mismatched review blocks before session. QA/reviewerFAIL never becomes eligible at9.5 in the full workflow. The standalone long publisher guard guarantees the additional score/hash/review requirements; canonical QA/approval/gate revalidation remains in the existing publication_binding workflow step, unchanged. Do not falsely attribute QA validation to helper(review, hash). Existing canonical review may still label8.5PASS, but additional policy blocks NEW publication. Tests must demonstrate old behavior fails new negative cases; no skips or relaxed expectations. Synthetic tests do not qualify media.
## FORBIDDEN
No frozen criteria/rubric edits, cron/triggers/permissions/access/secrets changes, spending, new render, manual live manifest/approval/ledger edits, #231 body rewrite, or unchanged retry of denied operations. Phases 2, 3 and 4 execution concluded and must not repeat. Current phase 5 grants no provider, render, upload or workflow execution. No workflow may change; shorts-review.yml, shorts.yml, pr-checks.yml and all workflow triggers, inputs, permissions, concurrency, schedules and Record remain unchanged. The previously refused fail-archive preservation change remains excluded.
## DEADLINE (UTC) / BRANCH
Urgent before pilot-006 Short slot2026-10-21T14:00:00Z. Branch dot/259-owner-quality-floor.
Draft PR with Refs this issue; phase1 code completion does not close media follow-up or #257. RESULT with full files, actual commands/output/SHA/CI, honest diagnostic unknowns. Normal protected merge only after independent review and gates.


## Historical phase 2 — completed and non-executable

Run39521492371 consumed the single review recovery of historical short-00.mp4 SHA2569c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707. Its actual editorial FAIL remains immutable, ineligible and forbidden to re-review. Original source-manifest pin37465008e0b73a51f3d394d283500eab1426fdd679d36b571ed241d20689e402 and recovered-history pin4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677 are historical provenance, not current execution authority. The untouched records, old verdicts and consumed005 exception remain historical; no manual promotion, reupload or rollback.

The superseded phase2 instructions and complete preceding SPECv7 body have been preserved verbatim in the prepared local working copy of migration/evidence/owner-quality-policy/phase2-report.md, for delivery with the phase5 PR. This is not a claim that remote main already contains the archive. The full local archive is verified before this consolidation is published. Original body SHA256dd0b97d79242285d04d8c5419e843bec9236eeaec425a370ef6753b0d98f5fb4 (65083 UTF-8 bytes). Its tested frozen recovery behavior remains available at immutable source links: [review_recovery.py](https://github.com/matheusmagah-cpu/heroverse-engine/blob/e0c72367031d4ceadfb39c1577af71d21a55b8e5/migration/publish/review_recovery.py), [test_review_recovery.py](https://github.com/matheusmagah-cpu/heroverse-engine/blob/e0c72367031d4ceadfb39c1577af71d21a55b8e5/migration/publish/test_review_recovery.py). This summary removes no current gate or source pin. Earlier acceptance/no-duplicate/no-fabrication requirements above and active correction binding, QA, >=9, audit, temporal and idempotency requirements below remain in force. Current work is exclusively phase5 metadata; phase2/3/4 must not execute again.

# Historical phase 3: corrected pilot-006 Short — render completed

This section preserves the accepted phase3 material contract, code requirements and source pins. Its one production run39569442793 completed2026-10-21T08:41:51Z after PR263 merged as b710b7c; new MP4 was preserved, QA/acoustics PASS, watched review NOT_REVIEWED_ProviderFailure HTTP503. These are historical render instructions, not current permission to render again. Phase 4 was subsequently consumed by run39575597092 with a second503. Current phase 5 is metadata-only, not permission for another execution. All source/material/criteria pins and valid publication barriers remain binding.

## Diagnosis and fixed objective

Recovered historical manifest SHA256: 4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677. Archive its exact bytes as correction-history.json. It includes all three historical records. Selected MP4 9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707 has actual review FAIL, overall 7.6, rhythm 6.5 and ending 7. Do not re-review those bytes or erase their evidence. The concrete defects are minimal motion around 00:03–16 and abrupt closing around 00:33–36.

Keep target 2026-10-21T14:00:00Z and release deadline 2026-10-21T13:15:00Z. No rollover. A passed software check is not approval of media. New output requires real QA and watched review, overall >=9 plus every pre-existing gate. The previous 005 exception does not apply: scene nominal durations are 20.977 and 21.023 seconds, both within the unchanged gate.

## Material-only correction and rejected alternatives

SPEC v6 established the completed phase3 candidate, extraction, duration, scene timing and derived plan digest, and incorporated the owner-requested cinematic animated opening through the closed first-scene profile below. This contract is not code acceptance, dispatch, media approval or permission to bypass any gate. All earlier phases, immutable history/source pins, allowed paths, licenses, movement outside the explicitly scoped opening, designated reviewer, QA, deadline, slot, code acceptance, preservation and publication requirements remain in force. No new acceptance method is authorized.

The owner refused the proposed acoustic exception: the frozen 0.3-second rule remains unchanged. Run 39529000826 failed; logged output SHA256 126c2e8335f5135e4d2ec2407c67e6eb636d8ce36ea7d0bd489d8ed34ff9c617 is MP4_UNPRESERVED. Preserve its actual failure and diagnostic evidence; do not re-review or redispatch those bytes, claim an archived MP4 exists, or infer nonexecution from unchanged canonical files. The prior replacement candidate 62.232–106.493 is discarded as UNRESOLVED_SEGMENT_END; do not silently resolve its source end or relax criteria.

The proposed fail-archive workflow change was refused and is not included. Keep the existing Preserve step's original if condition unchanged; only its already authorized run-body scope remains available. Do not add an always/failure condition, new archive path or acceptance exception. An unpreserved or uncertain execution remains subject to the existing authoritative reconciliation requirement before any separately authorized new attempt. The pinned correction-history.json remains byte-identical; do not append this diagnostic note to that immutable archive or change its digest.

## Source baseline and immutable pins

Source baseline for the recovered manifest: 582ff607089f9accb91a8a4d1a8c2fe6f4e47408. Implementation baseline is main e0c72367031d4ceadfb39c1577af71d21a55b8e5; its changes after merged phase3 affect only pilot-010 outputs, not these pinned pilot-006 sources. Before implementation, executor confirms remote baseline and raw bytes match these pins; divergence is not silently accepted.

- pilot-006/script.json: 1006e8bec3bc8c43dffe6e5ad1d26e257ceaea5fbe0eb12fa414b9c059d10cad
- pilot-006/out/timeline.json: 73357bd61adf13f004967f0a2b2ef3e16569fb2cd344eb419e3d1fcabf1af7a2
- pilot-006/shorts/inputs.json: 07a75a6b6849ed7ada9fc621a573b947689effc458693d6889ce3bc8568f514b
- pilot-006/images.json: f2e32a9a210ebd3d4f93d1d6fb9254ee2241d416784c9d31343c8f02138bb695
- pilot-006/out/manifest.json: 0d40777f7dd2a84db9615bd148df8c3173e2e46b9f7b32418e7677392e49a2bb
- pilot-006/out/review.json: e68b0ede86b2837d6070a18f20a17ad097be20d0636c427a4214c0f49324a00f
- voice asset pilot-006-voice-sha256-d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d.flac; SHA256 d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d
- music asset original-rest-music.lossless.flac; SHA256 1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c
- image 1 bg-still-water-night; asset pilot-006-img-bg-still-water-night-sha256-7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2.png; SHA256 7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2
- image 2 bg-healing-garden; asset pilot-006-img-bg-healing-garden-sha256-97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070.png; SHA256 97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070

Both PNGs were visually inspected and rehashed on 2026-10-21 around 00:40 UTC: moonlit pond and moonlit garden fountain; no person or text observed. Keep their painted appearance, explicitly retained for pilot-006 by R10. Keep source license/provenance receipts; do not generate substitutes. The figure input remains CLI-compatible but must never be composited.

## Closed plan values

Existing schema identifier remains shorts-006-correction-plan-v1. Reject missing, unknown, non-finite or altered closed fields. One candidate only, source_pilot pilot-006, title "Rest in God's Care", first-line hook "Let your face soften.", reference null. Retain the original script and all sentence text verbatim; do not attach the previous candidate's Philippians reference to this passage. The selector must accept this exact candidate with rejection reason null under its existing rules; null is not a permission override.

Narrative candidate start=813.728 and end=854.417, exactly the 12 complete sentences at original timeline indices 191:203 (zero-based, end-exclusive). Preserve every sentence through "Rest now." The first complete sentence ends 815.669, duration 1.941 seconds. The second ends 817.791; do not claim both opening sentences fit within 3 seconds. Narrative duration=40.689 seconds.

Separate audio_source_end=854.418, exactly 1 ms after the rounded narrative endpoint to preserve the complete native-timeline utterance and its remaining decay. This is source-exact extraction, not an acoustic exception or a newly invented segment boundary. The final nonzero native sample from timeline rounding is at 854.417333; next sentence starts 855.797 and must not enter the cut. The 976560-sample native reference and extraction match SHA256 e49a6b29b469a61298508e796b933a6ba87067427512649b28ed4d18fc9008af. Source FLAC extraction duration=40.690. tail_seconds=1.310 means padding after that extraction; narrative_tail_seconds=1.311 means time after the last word. output_seconds=42.000. Actual source voice verified by the executor:24000Hz mono,1529.993333 seconds, pinned SHA256. Extraction at native24000Hz is 976560 samples; resampling to output48000Hz yields 1953120 samples, padding=62880, output=2016000. Do not describe the source as48kHz. Reset sample timestamps, preserve rate, no retime, voice alteration or trimming of decay to manufacture a PASS. Music begins at MUSIC_OFFSET 1200+813.728=2013.728 and must contain 42 seconds through 2055.728. Preflight duration before encoding.

Use existing editorial ducking, loudness and limiter. Parameterize only the scoped audio end/duration and tail. Begin final mixed fade after audio_source_end relative to the cut (40.690), duration 1.310; never apply the legacy 40 ms pre-cut fade to the last spoken word. Existing music 2-second fade is preserved. Low end amplitude is only a measurement, not evidence that the ending sounds complete. The existing frozen RMS method and maximum 0.3-second leading/trailing inactivity rule remain mandatory. The source-exact extraction measured leading 0.13 seconds and trailing 0.29 seconds, PASS; these technical measurements are not a generated-MP4 QA verdict or watched review.

Scene1 bg-still-water-night: nominal[0,20.977]. Scene2 bg-healing-garden: nominal[20.977,42]. transition fade0.5. Output1080x1920,30fps,1260 frames. Existing half-up allocation: nominal split 629 frames; scene spans [0,637),[622,1260), fade 15 frames[622,637). No R3 exception. Camera phrase_push_in_v1 for both scenes, existing C1 progress from1.00 to1.08, derived from sentence boundaries with scene endpoints included.

Derived 42-second clocks replace the old material-specific numbers without changing measurement methods or tolerances: 1260 frames; first video PTS0, last1259/30; audio presentation2016000 samples; AAC packet_count1970, first_pts_samples=-1024, skip_samples1024, last_pts_samples2015232, last_duration_samples768, codec_frame_samples1024, continuous packet clock. Decode may expose2016000 or2016256 samples only when the existing packet-clock proof accounts for the final256 coded-padding samples; no arbitrary truncation or added content. A bounded synthetic42-second AAC clock check confirmed these packet values; it is not production QA.

## Continuous internal movement and renderer reuse

Factor the numerical composition core from opening_atmosphere into a private reusable helper. Preserve existing opening_atmosphere/opening_particles/write_opening_video outputs for005 exactly, including91frames/envelope. New scoped006 source-clip writer renders every scene frame, not91frames plus cloned frames. It uses the existing source-bound fog, blurred source-highlight light and deterministic particles for the entire scene with envelope1, seeds259006 and259007. Keep existing fog frequencies, drift, tint, light and dust limits and alpha cap0.18. Particles may leave the frame naturally; do not wrap or restart abruptly. Fog remains continuously animated even when a particle leaves.

Do not distort the fountain statue, flowers, moon or buildings. No guessed water mask or independently generated object. This is atmospheric internal motion, not a claim to have physically simulated the fountain stream. Actual watched review decides whether the result is convincing and lively enough. If it is not, preserve FAIL and correct the actual cause, never raise scores by inference.

Use two full-length lossless source clips in the already implemented serial FFV1 renderer, then the existing single xfade, then one original final encoder. No tpad cloned tail for either scene. Preserve threads caps, pixel range handling,1080p,30fps,CRF19,medium preset,AAC160k and48kHz. No added depth model or vendor. Keep captions once, KJV references and the original safe-area rules. Final picture continues moving to EOF; do not introduce black padding to manufacture an ending.

Before production, a bounded local diagnostic smoke on actual assets is allowed after this contract is accepted: sample representative clips/frames from each scene at start, middle and end, without provider. Inspect captions and atmosphere, not only pixel difference. This is not a substitute for full media qualification.

## Closed cinematic opening profile for scene 1

The owner requested a cinematic animated hook on 2026-10-21 at 07:56 UTC. Add only scenes[0].atmosphere.opening_profile="source_atmosphere_hook_v1" to the closed plan. Scene 2 has no opening_profile field and remains unchanged. No additional provider, asset, person, simulated water or new acceptance gate is introduced. The new plan digest binds this exact first-scene field; unexpected profiles, locations or extra fields fail closed. Existing continuous atmospheric motion remains throughout both scenes, beyond the opening.

Use the existing source-bound composition, blur, luminance, colors and alpha limits. Define t=frame/FPS, X=x/w and Y=y/h. Define S(u)=clamp(u,0,1)^2*(3-2*clamp(u,0,1)), P=S(t/3), and Tfog=t+4*P. Substitute Tfog for t only in the two existing fog terms. At and after 3 seconds Tfog=t+4, maintaining continuous drift rather than resetting the clock. Particle time remains t; no particle acceleration, restart, wrapping or parameter changes.

Define H=S(t/0.35)*S((3-t)/0.75) for 0<=t<3, and H=0 otherwise. Define C=0.32+0.36*P; G=exp(-((X-C)/0.22)^2-((Y-0.30)/0.20)^2); and M=1-S((Y-0.48)/0.06). Replace the existing source-highlight mask by max(highlights,0.85*H*G*M) before the unchanged downstream composition. The added highlight contribution is zero for Y>=0.54 and outside the opening; this does not require existing source illumination to be zero. Keep fog_alpha_max=0.09, light_alpha_max=0.06, dust_alpha_max=0.10 and alpha_cap=0.18, with the original blur, the original source-luminance highlight mask; the explicitly specified new Gaussian term is a procedural light overlay independent of source luminance, not a claim of physically simulated lighting, colors and source-image immutability. Do not treat the highlight mask as permission to increase opacity or create new objects.

Add keyword-only opening_profile=None to continuous_atmosphere, write_continuous_video and _atmosphere_composite while retaining all existing positional and keyword parameters. None preserves the previous implementation bitwise; the exact source_atmosphere_hook_v1 selects only the formulas above. Any other value raises INVALID_OPENING_ATMOSPHERE_PROFILE before rendering. Pass the profile through the renderer only for the exact pilot-006 correction adapter and scene 1. The ordinary pipeline, pilot-005, scene 2 and every None call remain unchanged. No workflow or preservation changes accompany this opening.

After contract acceptance and before full production, perform a bounded local visual smoke over 0–4 seconds on the actual pinned moonlit-pond source, with real crop, camera and caption composition, plus an otherwise identical None-profile control. Inspect actual frames at 0,0.35,1,1.941,2.25,2.967,3,3.033 and4 seconds, sampling by the renderer's established frame convention and recording actual frame indices/times. Visually inspect the sequence, not only isolated pixel differences: the hook must visibly move beyond camera zoom without a flash or an abrupt transition at 3 seconds. Confirm captions remain readable, no people are introduced and no water simulation is claimed. No provider call for this smoke. Technical and visual smoke evidence cannot substitute for complete-MP4 audiovisual QA and the existing watched review with overall>=9.

Additional required tests: bitwise unchanged pilot-005 opening and continuous None-profile output; continuity of the time/envelope formulas and rendered transition at frames89/90/91 (30fps); unchanged alpha limits; immutable source inputs; zero added highlight for Y>=0.54; unchanged scene 2; exact profile routing and rejection of invalid profiles. Do not invent a percentage-of-changed-pixels acceptance threshold or infer a watched-review score from technical tests. Preserve all prior tests, gates, allowed paths and frozen criteria.

## Exact proposed interfaces

New module migration/production/shorts_006_plan.py:
- validate_plan_schema(plan)
- validate_plan(plan, timeline, script, inputs, *, raw_sha256)
- frame_plan(plan)
- main(plan_path, timeline_path, script_path, inputs_path, out_path)
- check_media(work, plan, manifest, voice_flac, music, images_dir, history_path)
- finalize_file(manifest, mp4)
- binding(spec, *, plan_sha256, history_sha256)
- cli(argv=None)

CLI mirrors the existing005 adapter and uses only positional arguments:
1. python migration/production/shorts_006_plan.py PLAN TIMELINE SCRIPT INPUTS SELECTION_OUT
2. python migration/production/shorts_006_plan.py --check-media WORK PLAN MANIFEST VOICE_FLAC MUSIC IMAGES_DIR HISTORY_PATH
3. python migration/production/shorts_006_plan.py --finalize MANIFEST MP4

The producer's public signature and CLI stay compatible. Its existing edit_plan keyword accepts this second closed discriminator through a private adapter selector. Reject unknown discriminators; do not weaken005 validation. Share generic measurement and atomic JSON helpers where safe rather than copying large implementations; no change to frozen QA/review code or thresholds.

The selection output contains exactly one original complete narrative candidate plus the bound correction plan. Producer writes selection.json and shorts.json using its existing output convention. The existing Preserve workflow step, not the producer, generates short-00-frame.jpg. Filename of the new MP4 is short-00.mp4. Never invent its hash before it exists.

Check-media binds plan/hash/history/source hashes, complete source duration, actual geometry/fps/frames/PTS/PCM/captions/motion metadata and actual MP4 hash. It rejects the prior FAIL hash and any hash previously reviewed FAIL in the pinned history. Preserve existing black-frame, source and output integrity checks without relaxation. QA checks and reviewer both use pre/post hash equality; finalizer matches all hashes to actual bytes. Reuse existing review invocation, prompt/rubric/model/retries unchanged.

Finalization starts by revoking eligibility atomically. It accepts one record only, real QA PASS, real review PASS, overall>=9 with existing item thresholds, valid source/long approval, bound measurements and actual bytes, valid deadline/target, no FAIL hash. It then generates finalization.kind='pilot-006-correction-v1', status='COMPLETE', source_pilot, plan_sha256, history_sha256, output_sha256, target_slot, release_deadline, validated_at and release_status='READY'. Fields are generated, not manually filled. At or before13:15:00 may qualify;13:15:01 fails closed. Publication still requires the existing remaining editorial/provenance/license/metadata/channel gates.

The exact canonical PLAN digest supplied below must be pinned in implementation/tests/report before review. It was calculated from the supplied newline-terminated JSON, not invented. History pin above is known and must be exact. Runtime plan and history files must match their pinned digests; record-only assertions are insufficient.

## Operational integration

In the existing shorts.yml select/produce/review step, add a branch for pilot-006 plus the exact correction-plan.json. Validate plan and sources, produce one, check media, review one, finalize automatically. Do not fall into legacy select3 if the correction plan exists but is invalid. Preserve all other branches. No edits to workflow triggers, inputs, permissions, concurrency or schedule. Keep the existing preservation step, archiving the historical manifest first as a tracked immutable file. Its run body must additionally copy the generated correction-media-checks.json from the work directory to pilot-006/shorts/correction-media-checks.json; the present step does not copy this file. Its existing frame extraction remains responsible for short-00-frame.jpg. These run-body changes are allowed; triggers/inputs/permissions remain byte-identical.

In pending_shorts.recovery_gate, preserve the directory/path/symlink/context checks. Select the correction binding only for exact finalization.kind='pilot-006-correction-v1'; validate pinned plan/history files and deadline. Otherwise call existing review_recovery.binding unchanged. Malformed correction metadata must never fall back to the historical gate. Existing uploaded IDs remain handled before new-upload eligibility.

In publish_shorts.recovery_upload_gate, reuse that guard and keep exactly one publishable record, matching output hash, filename, target and slot. Confirm actual MP4 bytes before upload. Preserve idempotent ledger/readback handling, no reupload of an existing/uncertain ID. No modification of review_recovery.py or old pinned FAIL inputs is needed. The new binding authorizes only corrected bytes that genuinely passed gates, not an override of the old FAIL.

## ALLOWED PATHS for this phase

migration/production/shorts_produce.py
migration/production/test_shorts_produce.py
migration/production/shorts_006_plan.py
migration/production/test_shorts_006_plan.py
migration/production/pilot-006/shorts/correction-plan.json
migration/production/pilot-006/shorts/correction-history.json
migration/production/pilot-006/shorts/correction-media-checks.json
migration/production/pilot-006/shorts/selection.json
migration/production/pilot-006/shorts/shorts.json
migration/production/pilot-006/shorts/short-00-frame.jpg
migration/publish/pending_shorts.py
migration/publish/test_pending_shorts.py
migration/publish/publish_shorts.py
migration/publish/test_publish_shorts.py
.github/workflows/shorts.yml
.github/workflows/pr-checks.yml

migration/evidence/owner-quality-policy/phase2-report.md

This is the existing authorized report path. selection.json, correction-media-checks.json, shorts.json and short-00-frame.jpg are generated outputs only. History is copied byte-identically; source input files and criteria are not editable. MP4 is preserved through the existing verified release-asset interface, not a new arbitrary repository path.

## ACCEPTANCE and known answers

- Validate fixed source hashes, exact history bytes and actual image/voice/music hashes, with trailing newline counted. Wrong/missing/symlink/nonfinite/unknown fields fail closed.
- Exact arithmetic:40.689 narrative,40.690 FLAC,1.310 padding,42.000 output;1953120+62880=2016000 samples;1260frames;spans [0,637),[622,1260);nominal split629;15-frame fade;first line 1.941 seconds. Native extraction 976560 samples; narrative tail 1.311 seconds; unchanged RMS 0.3-second limit requires actual measurement. No boundary truncation, retiming, acoustic exception or new acceptance method.
- Negative source/music truncation blocks before render/provider; next spoken sentence excluded. Tests distinguish narrative end from extraction end and captions never extend into padding.
- Actual producer command uses full animated inputs for both scenes, no tpad/cloned remainder, capped threads, original encoding settings and one final audio pipeline.
- Atmospheric helper is deterministic, does not mutate source, preserves limits and nonzero internal temporal change at t>3 and near the end of both scenes. Test outside active composition/invalid dimensions, not only visual score proxies.
- Confirm serial output equivalence against the two-source reference for frames/PTS/PCM and cross-version range semantics. Use valid-duration fixtures and a bounded FullHD real command; retain resource/invalid-fixture evidence honestly.
- Pin and compare existing005 procedural output and legacy CLI commands. Existing005/ordinary adapters and recoveryFAIL logic remain unchanged.
- Check-media rejects historical FAIL MP4, changed bytes, bad source hash, missing history and wrong plan. Provider spy must remain zero for pre-review failures.
- Finalizer rejects QA FAIL, reviewFAIL, overall8.99, missing watched review, changed MP4, mismatch among QA/review/media/output hashes, second candidate and late clock. Positive fixture9.0 must pass only with all other gates valid.
- pending/publisher reject forged/mismatched correction binding, wrong pilot/path/plan/history, reused oldFAIL, extra record/slot and expired deadline. Existing uploaded/uncertain IDs never cause another upload.
- Inspect workflow AST: triggers, inputs, permissions, concurrency and schedule exactly unchanged;006 invalid plan cannot reach select3. No provider invocation in tests.
- Run relevant full suites, independent review, exact-SHA CI, remote byte/hash checks. The one phase3 production render is now completed and preserved. Do not repeat it. Phase 4 completed with a second503, not watched-review eligibility. Actual watched review>=9 and all gates remain mandatory before publication; phase 5 does not provide or authorize another attempt to obtain them.

## Historical phase3 production checks (render completed; media gates still binding)

1. Canonical plan and digest are now supplied below; the literal existing report path is included above. No technical authorization gap beyond contract publication is claimed.
2. Music duration independently verified by the executor: original-rest-music.lossless.flac has the pinned SHA256 and ffprobe duration10800.000000 seconds, sufficient for2013.728–2055.728. Actual voice FLAC also verified by the executor: pinned SHA256,24000Hz mono,1529.993333 seconds. Inspected image hashes match.
3. Inspect smoke frames and temporal samples; record audio smoke as NOT_REVIEWED when perceptual audio is unavailable. Acoustic measurements are technical only. Mandatory audiovisual watched review remains on the complete newly rendered MP4 through the existing designated reviewer, after code gates and before any eligibility/publication. No extra smoke provider call. The planned motion and longer tail do not guarantee editorial9 or physical realism. Correct genuine defects without inventing pass evidence or altering criteria.

## Closed routing choice (mandatory)

Implement one private producer resolver `_editorial_adapter(plan)`: exact version `shorts-006-correction-plan-v1` AND source_pilot `pilot-006` selects shorts_006_plan; exact existing005 version AND pilot005 selects shorts_edit_plan; every other pair raises before render. Both adapters still validate their complete closed schemas. Replace direct005 imports in each existing scene_frame_plan/editorial_picture/render/produce/main validation site with this resolver; do not infer scope merely from edit_plan presence. Tests enumerate every call site and wrong/mixed version/pilot pair. Shared serial FFV1 writer and final encoding remain one implementation. Where005-only measurement assumptions exist (8scenes,10sentences,referenceNone,20UTC slot),006 owns explicit two-scene/source-aware validation instead of passing through005's validator or relaxing it. Generic numerical helpers may be reused only if they do not embed005 constants.

## Exact canonical plan artifact

Proposed file:correction-plan-v6.json. Repository destination after contract approval: migration/production/pilot-006/shorts/correction-plan.json. UTF-8, ensure_ascii=False, indent2, one terminal newline. SHA256: 95624da1b4e4e4b256faee29fb37c8bc78fdb5c9747a3be86c69d9ec0e319905. Byte count: 3489. Reject a raw-byte hash mismatch even if parsed JSON is semantically similar.

The following object defines ALL allowed fields recursively; no arbitrary extra keys. Numeric values are exact finite values (not booleans); file/hash/identifier strings must match literally. The audio object separates candidate sentence bounds from FLAC extraction, resampling and padding. The scene atmosphere object specifies the new full-duration procedural profile. Neither schema is accepted by005: route solely through the closed006 adapter.

```json
{
  "version": "shorts-006-correction-plan-v1",
  "source_pilot": "pilot-006",
  "source_baseline_sha": "582ff607089f9accb91a8a4d1a8c2fe6f4e47408",
  "source_sha256": {
    "script": "1006e8bec3bc8c43dffe6e5ad1d26e257ceaea5fbe0eb12fa414b9c059d10cad",
    "timeline": "73357bd61adf13f004967f0a2b2ef3e16569fb2cd344eb419e3d1fcabf1af7a2",
    "inputs": "07a75a6b6849ed7ada9fc621a573b947689effc458693d6889ce3bc8568f514b",
    "images": "f2e32a9a210ebd3d4f93d1d6fb9254ee2241d416784c9d31343c8f02138bb695",
    "long_manifest": "0d40777f7dd2a84db9615bd148df8c3173e2e46b9f7b32418e7677392e49a2bb",
    "long_review": "e68b0ede86b2837d6070a18f20a17ad097be20d0636c427a4214c0f49324a00f"
  },
  "history": {
    "file": "correction-history.json",
    "sha256": "4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677",
    "rejected_output_sha256": "9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707"
  },
  "voice": {
    "asset": "pilot-006-voice-sha256-d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d.flac",
    "sha256": "d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d"
  },
  "music": {
    "asset": "original-rest-music.lossless.flac",
    "sha256": "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c",
    "source_start": 2013.728
  },
  "candidate": {
    "start": 813.728,
    "end": 854.417,
    "hook": "Let your face soften.",
    "title": "Rest in God's Care",
    "reference": null
  },
  "audio": {
    "source_start": 813.728,
    "source_end": 854.418,
    "source_sample_rate": 24000,
    "source_channels": 1,
    "source_samples": 976560,
    "output_sample_rate": 48000,
    "resampled_source_samples": 1953120,
    "padding_samples": 62880,
    "output_samples": 2016000,
    "fade_start": 40.69,
    "fade_seconds": 1.31
  },
  "tail_seconds": 1.31,
  "narrative_tail_seconds": 1.311,
  "output_seconds": 42.0,
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "transition": {
    "type": "fade",
    "seconds": 0.5
  },
  "scenes": [
    {
      "image_id": "bg-still-water-night",
      "asset": "pilot-006-img-bg-still-water-night-sha256-7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2.png",
      "sha256": "7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2",
      "nominal_start": 0.0,
      "nominal_end": 20.977,
      "motion_profile": "phrase_push_in_v1",
      "atmosphere": {
        "profile": "source_atmosphere_continuous_v1",
        "seed": 259006,
        "envelope": 1.0,
        "alpha_cap": 0.18,
        "fog_alpha_max": 0.09,
        "light_alpha_max": 0.06,
        "dust_alpha_max": 0.1,
        "opening_profile": "source_atmosphere_hook_v1"
      }
    },
    {
      "image_id": "bg-healing-garden",
      "asset": "pilot-006-img-bg-healing-garden-sha256-97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070.png",
      "sha256": "97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070",
      "nominal_start": 20.977,
      "nominal_end": 42.0,
      "motion_profile": "phrase_push_in_v1",
      "atmosphere": {
        "profile": "source_atmosphere_continuous_v1",
        "seed": 259007,
        "envelope": 1.0,
        "alpha_cap": 0.18,
        "fog_alpha_max": 0.09,
        "light_alpha_max": 0.06,
        "dust_alpha_max": 0.1
      }
    }
  ],
  "release": {
    "target_slot": "2026-10-21T14:00:00Z",
    "release_deadline": "2026-10-21T13:15:00Z",
    "minimum_overall": 9.0,
    "file": "short-00.mp4"
  }
}
```

## Preserve scope guard

Only two existing shorts.yml run bodies may change: select/produce/review and Preserve. In pr-checks.yml, only add migration/production/test_shorts_006_plan.py to the existing test loop; all other bytes remain unchanged. In the006 correction branch, replace broad frame cleanup with cleanup of short-00-frame.jpg only. Preserve tracked short-01-frame.jpg and short-02-frame.jpg byte-identically and preserve historical records through the pinned archive. No glob removal of historical frames, no deletion of other pilots or artifacts. Tests inspect the006 command branch and compare tracked01/02 hashes. Existing non006 behavior remains unchanged.

## Mandatory one-attempt canonical preflight

Additional exact CLI: python migration/production/shorts_006_plan.py --preflight PILOT_DIR PLAN HISTORY_PATH. Python interface preflight(pilot_dir, plan_path, history_path). Before prepare/render/provider, require PILOT_DIR resolves to the authorized pilot-006 directory, exact closed plan raw digest, exact pinned history bytes, and PILOT_DIR/shorts/shorts.json raw SHA256=4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677. Reject missing plan even on006; it must never fall back to select3. Reject symlinks/traversal and source pin mismatch. After any new result is persisted, canonical hash changes, so another attempt is blocked pending a new precise contract. An uncertain execution or failed preservation requires reconciliation, not redispatch even if canonical bytes did not change; executor must check authoritative run state and artifacts before dispatch. This preflight is not an exactly-once claim across an unpersisted run. Test changed canonical PASS, FAIL, NOT_REVIEWED and malformed bytes all fail with zero render/provider calls.

## Additional closed interface and binding details

The006 adapter exposes hash_file(path) and read_json(path) with the same semantics as the existing neutral helpers. It may import those helpers, never monkeypatch005 constants. Existing005 measure_video invokes005-specific validation and must not be reused wholesale; reuse only neutral measurement primitives and implement explicit006 duration/frame/audio validation against audio.source_end, not the narrative end.

check_media writes correction-media-checks.json beside MANIFEST, using atomic_json, and binds the same generated measurement object/hash into the manifest. The006 Preserve branch copies that exact file from RUNNER_TEMP/work/shorts to the authorized canonical shorts directory together with selection.json and shorts.json. Missing or mismatched measurements block preservation/release.

binding revalidates the complete finalization schema and all nested QA/review/media/record gates against the actual pinned plan/history files and their raw hashes, not merely kind/status or asserted digests. Reject correction edit_plan with missing/wrong finalization kind, correction finalization with005 plan, and any simultaneous review_recovery or owner_exception fields. Tests forge READY/publish=true while changing QA toFAIL, review to8.99, media hash, plan identity or nested measurements and require zero session/upload. No binding asserts a PASS based only on its own existence.

## Persisting legitimate non-eligible results

A well-formed real QA FAIL, review FAIL, overall below9, NOT_REVIEWED provider result or expired cutoff is not a CLI integrity exception: finalizer records finalization.status COMPLETE, publish=false and a categorical release_status/reason, preserves original evidence, and returns exit0 so the existing Preserve step records the new manifest. COMPLETE means evaluation completed, never eligibility by itself. READY is emitted only for all gates PASS. Malformed evidence, hash mismatch or unreadable media instead records ERROR with publish=false and exits1; treat failed preservation as an uncertain outcome requiring reconciliation, never repeat against unchanged canonical bytes. Tests cover both exit semantics and workflow preservation of legitimate negative results. No failed review is promoted or suppressed.

## Historical phase3 acceptance commands (not an instruction to repeat completed tests)
Run from repository root with configured Python environment (numpy/opencv available):
python3 -I -B migration/production/test_shorts_006_plan.py
python3 -I -B migration/production/test_shorts_produce.py
python3 -I -B migration/production/test_shorts_edit_plan.py
python3 -I -B migration/publish/test_pending_shorts.py
python3 -I -B migration/publish/test_publish_shorts.py
python3 -I -B migration/publish/test_review_recovery.py
git diff --check
Each command must exit0 and report all tests successful. Additionally run the repository test-file loop, card_check, dot_scope against this card, frozen-file hash comparisons, independent review and exact-SHA HeroVerse PR checks. Record commands, actual outputs and SHA. Generated media is not qualified by these software tests.


# Historical phase 4 — consumed corrected-006 review-only recovery

This phase is historical: its one authorized review invocation was consumed by run39575597092, which returned a second503. The requirements and pins below remain audit evidence, not dispatch permission. No render, added retry loop, fallback, publication or refused archive change was authorized; no further provider invocation is authorized now.

## Evidence and fixed pins
Run39569442793 ended2026-10-21T08:41:51Z;42s MP4 preserved, QA/acousticPASS, provider503 without editorial verdict. Baseline89541e4cd3232195e8f626d8419b023cc0cd3317:
- source_manifest_sha256: a33d46db02ee419c357ae4ecefeee615b3d6ac32af143e85814cfbcb82bd1418 (raw shorts.json including newline).
- media_sha256: 6d3f0199f1ea9b0b22a87dbb29b9abfa7a3632f74488d6f1be990a9b46e00200 (raw correction-media-checks.json).
- output_sha256: 96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e; short-00.mp4,20,581,582bytes.
- previous failed_at:2026-10-21T08:41:45.362893+00:00; http_status503,provider_statusUNAVAILABLE.
- not_before:2026-10-21T08:51:45Z; cutoff:2026-10-21T13:15:00Z; target_slot:2026-10-21T14:00:00Z.
not_before is 9min59.637107s after failed_at, not >=600s or proof of recovery. One review, never FAIL bytes.

## Historical phase 4 allowed subset and interfaces
Edits: shorts_006_plan.py, test_shorts_006_plan.py, phase2-report.md audit, two shorts-review.yml run bodies, and only test_workflow_only_two_run_bodies_changed in migration/publish/test_review_recovery.py, using full union paths above. Update that historical routing assertion/normalization to the new two bodies, preserving its baseline SHA256 caf36ac8c64f23eebdf71fe0eb7e2418170b108f102eed532d1c20edc1bb892d and every assertion for unchanged workflow bytes. Do not normalize unrelated differences or remove the test. Runtime output only canonical pilot-006/shorts/shorts.json via unchanged Record; other files/workflow fields unchanged.
New signatures:
- def recovery_preflight(pilot_dir, *, now_utc):
- def recovery_list(pilot_dir):
- def recover_review(pilot_dir):
CLI: --recovery-list PILOT_DIR; --recover-review PILOT_DIR. Real datetime.now(timezone.utc), no clock/hash/run override. now_utc injection only in tests; identity from GITHUB_RUN_ID/GITHUB_RUN_ATTEMPT.
Reuse existing validators, atomic_json/finalize_file, shorts_review.review/failure_record, owner_quality_policy.check. Never call producer preflight/check_media, shorts_review.main or old wrapper.

## Preconditions and fresh QA
Canonical nonsymlink pilot-006, one short-00.mp4; exact raw manifest/media pins. _contract verifies source/plan/history/qualified-long pins; _bind_record/validate_media_checks bind MP4, QA and metadata. finalization kind=pilot-006-correction-v1,status=COMPLETE; all release_status fields REVIEW_NOT_REVIEWED; publish=false. Exact original503 review including clock/diagnostic/hash, no scores/audit/FAIL for these bytes. _evaluate must return REVIEW_NOT_REVIEWED with QA PASS.
List validates one record and documents, not unavailable local MP4, and prints file/hash. Review requires regular nonsymlink MP4 after download; requires positive decimal GITHUB_RUN_ID different from source, GITHUB_RUN_ATTEMPT="1", no active/uncertain review and real UTC in window immediately before provider.
Hash and size actual MP4, run unchanged shorts_qa.check, rehash. Require fresh _qa_verdict(qa,42.0)==PASS/allchecks true. Original qa/qa_output_sha256 unchanged; audit keeps real fresh QA (localpath/measurements may differ). Same thresholds, original measured_at<=now and same UTC day.
Key/QA/rehash/preflight before STARTED; failure leaves source byte-identical, exit1, local sanitized diagnostic/QA only, no audit or Record promise.

## Closed audit schema
Only new metadata: correction_review_attempt. Closed keys/types; no nonfinite/bool-as-int. Recursive review_recovery/review_recovery_execution/owner_exception prohibition unchanged.
- version:string literal shorts-006-review-attempt-v1.
- source_run_id:string literal39569442793; run_id:positive decimal string distinct from source; run_attempt:int1.
- source_manifest_sha256/media_sha256/output_sha256:hex64 exact pins above.
- not_before/cutoff/target_slot:exact UTC strings above.
- started_at:actual ISO UTC string; completed_at:null inSTARTED, actual ISO UTC >=started_at at completion.
- state:STARTED|COMPLETE|ERROR.
- previous_review:deep-equal entire source503 review dictionary, including sanitized diagnostic; never raw provider body.
- fresh_qa:actual check() result validated by _qa_verdict, statusPASS; originalQA stays unchanged.
- reason:null forCOMPLETE; ERROR enum INPUT_CHANGED|OUTPUT_CHANGED|FINALIZATION_ERROR|OUTPUT_WHITELIST_VIOLATION|OPERATION_ERROR. Never exception prose/secrets.
Pure audit validation in _evaluate covers finalize_manifest/finalize_file/binding: exact schema/pins/previous_review, _qa_verdict and chronology. STARTED/ERROR neverREADY. Finalizer candidate: COMPLETE,reason=null,real completed_at>=started_at. Ordinary flows unchanged. Only the pinned 96c826…7b6e output PASS/FAIL requires audit; original503 withoutaudit only noneligible input.

## One attempt, atomic result, bounded differences
After prechecks atomically store STARTED/publish=false and retain original snapshot/STARTED hash. Invoke shorts_review.review(mp4,deepcopy(record),key) once; existing internal retries/model/prompt/rubric frozen, no added retry. Exceptions use failure_record; previous503 exact.
After call rehash MP4/revalidate contract/media/STARTED bytes; concurrent change forbids overwrite. Exclusive untracked candidate beside manifest gets realreview/computedpolicy/COMPLETE audit; finalize_file(candidate,mp4), recheck identities/whitelist, atomic install, remove temporary. No partialREADY.
Diff whitelist: top-level correction_review_attempt,finalization,release_status,publish; record review,owner_quality_policy,release_status,publish only. All else exact, including QA/media/measured_at/text/edit_plan/selection/render_plan. No other file mutation. Persist integrity ERROR only while canonical is this run’s state; otherwise reconcile.
After finalize_file and slow checks, read real UTC immediately before canonical install. If cutoff crossed, automatically finalize using that actual instant: COMPLETE,publish=false,TARGET_SLOT_LEAD_MISSED, retaining real review/audit; exit0 for Record. completed_at/validated_at follow actual sequence, not old timestamps; same-day/media chronology remains required. CLI never accepts clock override. Expiry is not integrity ERROR.
FAIL/503/PASS<9 consume attempt, stay ineligible. COMPLETE negatives exit0 for Record; integrity/unknown exit1. Pins/audit/run_attempt block reruns. Crash before Record can leave old remote bytes after provider: failed Record/cancel/unknown require reconciliation, no redispatch. No exactly-once claim.

## Exact two run bodies
Replace only download run body; malformed006 never falls back:
```bash
set -euo pipefail
case "$PILOT" in pilot-[0-9][0-9][0-9]) ;; *) exit 1;; esac
sudo apt-get install -y -qq --no-install-recommends ffmpeg >/dev/null
d="migration/production/$PILOT/shorts"
if [ "$PILOT" = pilot-006 ]; then
  python3 -I -B migration/production/shorts_006_plan.py --recovery-list "migration/production/$PILOT"
else
  python3 -I -c "import json,sys;[print(s['file'],s['sha256']) for s in json.load(open(sys.argv[1]))['shorts']]" "$d/shorts.json"
fi |
while read -r f sha; do
  gh release download "$TAG" --repo "$GITHUB_REPOSITORY" --pattern "$PILOT-${f%.mp4}-sha256-$sha.mp4" -O "$d/$f"
  echo "$sha  $d/$f" | sha256sum -c -
done
```
Watched review step:
```bash
set -euo pipefail
if [ "$PILOT" = pilot-006 ]; then
  python3 -I -B migration/production/shorts_006_plan.py --recover-review "migration/production/$PILOT"
else
  python3 -I -B migration/production/shorts_review.py "migration/production/$PILOT/shorts" 3
fi
```

## Acceptance
Run test_shorts_006_plan.py plus existing full code/remote-hash/independent-review/exact-SHA CI gates; no provider in tests.
Negatives before call: FAIL current/prior, wrong hash/pilot/file, completed review,429/unknown error, missing key, prior audit, attempt2, stale/future media, source change, QA FAIL/decode/hash change. Precheck failures preserve original manifest. Test time boundaries, no CLI override and expiry DURING finalization producing durable COMPLETE negative. Test source/media/manifest/MP4 races, no partial READY on atomic/finalizer errors, exact previous503, closed audit/whitelist/prohibited keys, removed audit from recovered PASS/FAIL, STARTED/ERROR forged eligibility. Positive >=9 requires every gate;8.9/FAIL/503 never eligible. Test original/fresh QA, two-body-only YAML diff, non006 invariance, no006 fallback/render.
The phase 4 one-shot dispatch is consumed by run39575597092 with a second503. Do not execute it again. Its output and audit remain preserved evidence; publication gates and the14UTC slot are unchanged.

# Current phase 5 — corrected006 metadata only
Phase4 is consumed: run39575597092 returned second503. No provider/render/retry/upload permission, workflow or media changes. All existing >=9/QA/audit/binding/channel/idempotency gates, pins, 14UTC target and13:15UTC cutoff remain mandatory. Current editable subset only:
migration/publish/publish_shorts.py
migration/publish/test_publish_shorts.py
migration/evidence/owner-quality-policy/phase2-report.md (audit)

Add pure metadata_for(short,long_url,long_title,*,pilot=None), returning exactly title,description,tags. Only pilot-006 plus sha256=96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e selects fixed rest metadata; all other/default cases reproduce legacy bytes. description_for/title_for stay compatible.
Title: Rest in God's Care #shorts
Description (no terminal newline):
▶ Full prayer: {long_url}
{long_title}

A quiet moment to rest in God's care.

#prayer #rest #jesus #faith #shorts
Tags, exact ordered list: ["prayer","rest","christian reflection","jesus","faith","shorts"]

NEW uploads still require existing trusted path/key/pilot agreement, correction binding and all gates. Require short-00.mp4/title Rest in God's Care/hook Let your face soften./reference null before session; no fallback on inconsistency. Metadata is not approval. Body, expected readback and receipt title use the same computed metadata; all other snippet/status fields unchanged.
Existing ID: GET only after cutoff/missing MP4/publish=false; no fresh eligibility gate. Other hashes remain legacy. Inconsistent local filename/title/hook/reference still permits GET with fixed metadata; report VERIFICATION_UNKNOWN/LOCAL_METADATA_IDENTITY_MISMATCH unless stronger remote VERIFICATION_FAIL, never reupload/edit. Changed long title yields honest description mismatch. Reconfirm no prior ID for this hash before release; otherwise reconcile first.

observe_video(session,video_id,*,include_tags=False): unchanged default; true only for the exact pilot-006/96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e selector observes tags; every other expected/observation omits tags, list[str] only. verification checks tags only when expected includes them: missing/invalid -> VERIFICATION_UNKNOWN/MISSING_TAGS; unequal ordered list -> VERIFICATION_FAIL/MISMATCH_TAGS. Tags never downgrade an established verification FAIL. Only nested observation.tags/unknown_fields.tags may extend existing ledger.verification and receipt observations. No snapshot/new top-level fields/remote PUT/PATCH.

Synthetic tests: exact/legacy metadata; forged identity/binding/hash/path and all existing gate negatives zero upload; body/readback equality; existing-ID GET/no reupload with missing media/expired clock/changed or absent filename/title/hook/reference; tag match/missing/type/mismatch; unchanged status/slot and ledger shape outside observation. Run publisher/pending/adapter suites and existing full tests, card_check/dot_scope/diff/frozen hashes/remote bytes/independent review/exact-SHA CI. No live fixtures/provider. Publish verified consolidated contract before code.

<!-- END SPEC V8 VERBATIM -->

## Phase 6 preparation: HTTP diagnosis, 2026-10-21 10:03 UTC

The owner requested correction of the 503 failure at 09:45:44 UTC. This diagnosis does not establish the provider's internal cause and does not qualify the video. No new provider call, render or publication occurred during diagnosis.

The two real runs remain preserved: 39569442793 and 39575597092. Both ended with HTTP_503_UNAVAILABLE and no editorial score. The current manifest SHA256 is 856f2765f104a1a98a54ec322784302066b545882595290020cf672183ebf9f8. The current MP4 remains 96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e, 20,581,582 bytes. Its QA/acoustic checks passed; watched review and eligibility remain NOT_REVIEWED/false.

Code-path inference, not retained Files API evidence: ProviderFailure HTTP_503_UNAVAILABLE originates in the generateContent transport. Reaching that call requires upload to return ACTIVE. The old Files API request path would instead raise a raw HTTPError, projected as UNKNOWN. No mismatch was demonstrated in endpoint, model, payload/schema, timeout or file size. Specific backend cause is UNKNOWN.

Offline counterexamples used fully mocked network responses, never the real provider. The diagnostic script SHA256 is e7102d28898d6ed3e463a0eb13d104dfce79106920a1fa9b2de71412aba919a5; JSONL evidence SHA256 is 235fda13653d2310fb9b89b816272c1927bd1998474be6980218997e7c877b13. Assertions exited 0:
- A first 503 with Retry-After 180 seconds and RetryInfo 120 seconds caused only a 20-second wait. Server guidance was ignored.
- A second terminal 503 caused another 40-second sleep even though no further request followed.
- A 503 followed by HTTP 200 with invalid candidate JSON produced UNPARSEABLE_MODEL_OUTPUT carrying stale diagnostic.http_status=503.
- The existing sanitized retry_delay string is lossy and unsuitable as authoritative retry input. Negative/exponent/text forms can become different positive durations.

These are client resilience and diagnostic defects. They are not proof that this client caused either real server 503. The proposed correction is opt-in, bounded, same-model and fail-closed, with the original behavior retained for other callers. A new invocation requires the revised contract, tested implementation, independent review, exact-SHA CI and a fresh one-shot preflight. Existing audits and failed editorial artifacts must remain intact.

Official references checked during diagnosis:
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/api/files
- https://ai.google.dev/gemini-api/docs/files
- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- https://ai.google.dev/gemini-api/docs/troubleshooting
The generic free-tier status page reported operational at 09:22 UTC. This does not establish health for this model, project or individual request, and does not independently justify repeating a consumed attempt.

Read-only reconciliation at 10:02 UTC found no new repository comments since 09:43 UTC and no new dot-task update beyond issue259's known 09:30:44 update. Remote DOT_PROTOCOL bytes equal local main. An initial attempt to parse its decoded text as JSON raised SyntaxError locally; the subsequent text comparison succeeded. No external state changed from that parsing error.

### SPEC v9 publication and implementation start

The first body-only PATCH was denied at 10:04 UTC because exact replacement-payload approval was absent. No external mutation occurred. The owner explicitly approved that same operation at 10:49:48 UTC in response to the 10:05:05 question. A fresh GET showed no intervening edit. One retry succeeded at 10:50:34 UTC; response and subsequent GET match reviewed payload SHA256 e874b37d7b2b8b72e61c1c93536b8503cc2ed578ec90b05dc3461fa4eadf28bb exactly. No alternate route was used.

Independent contract review PASS and card_check CARD_OK apply to that payload, not implementation or media. Current work is phase6; previous execution permissions remain consumed. Full v8 above is historical, not a concurrent rule.

Initial implementation progress: shorts-review.yml changes only --recovery-list to --http-recovery-list and --recover-review to --recover-http-review in the two authorized run bodies. Its historical static integration assertion follows those tokens while retaining the caf36 baseline and all outside-body checks. python3 -I -B migration/publish/test_review_recovery.py: 28 tests, 0.310s, OK, exit0. git diff --check PASS. The new HTTP implementation and its complete acceptance are pending; no provider call is authorized by this partial draft evidence.

### Initial draft CI failure, preserved rather than hidden

Draft SHA0a40215c4638d5a5f32a46612c72ba5ab2e4c5b4 ran CI39587769097/job119180840616 and failed. The fetched real log identifies only test_shorts_006_plan.py test_workflow_recovery_routing: StopIteration at line808 while searching the old --recovery-list token. The draft had changed routing before the adapter test update was delivered. The 33-test adapter suite reported one error; the other47 registered files passed. This is not a provider failure or qualified delivery. The correction updates that routing assertion to the new CLI and retains a reversible full-workflow baseline check; no test or gate is removed. No unchanged CI rerun was requested.
Source: https://github.com/matheusmagah-cpu/heroverse-engine/actions/runs/39587769097/job/119180840616

### Phase 6 code acceptance before delivery

The implementation uses the opt-in designated-review-http-v1 policy only in the separately pinned006 recovery. Other callers retain their legacy behavior. The new policy uses at most two generateContent transports, the same designated model and unchanged payload, a600-second monotonic budget, the real UTC deadline, strict original Retry-After/RetryInfo parsing, and no final sleep. It does not claim to repair the provider's internal availability.

Client diagnostics are produced by code, not model output. The new audit preserves the prior v1 dictionary and both previous503 records. It records real timing, stage, HTTP status, cleanup and completion; malformed, late or incomplete results remain ineligible. Actual output bytes and source evidence are revalidated before/after the one invocation. An uncertain or unrecorded outcome is not permission to redispatch.

Implementation review caught and corrected these pre-delivery defects:
- Sleep duration was initially counted twice between the policy and pure validator.
- Final503 hints and a partial HTTP200 read-timeout needed factual negative trace handling.
- An interrupted partial sleep must be preserved as terminal negative, without authorizing a second transport.
- An integrity failure after provider activity must preserve validated client trace in ERROR where available, never promote eligibility.
No production request was made while diagnosing these issues.

Known-answer semantic antidote, fully mocked HTTP against baseline d11e195 and corrected opt-in code:
- Retry-After180: old sleeps20 (FAIL); corrected sleeps180 (PASS).
- Two503: old sleeps20 and40 (FAIL); corrected sleeps180 once and stops (PASS).
- 503 followed by invalid200 JSON: old terminal diagnostic retains503 (FAIL); corrected terminal diagnostic has no stale503 (PASS).
All six observations were asserted; script exited0. These are resilience proofs, not media or service-health evidence.

Worker suites:30 mining tests and46 reviewer tests PASS;47 adapter tests PASS. Executor personally ran the47-test adapter suite:11.540s, OK, exit0. Root technical direction personally ran the frozen bytes at11:02 UTC: mining30tests0.071sOK; reviewer46tests0.124sOK; adapter47tests6.286sOK, all exit0. These are technical tests by dot, not owner/Claude review or watched media review.

Static acceptance: git diff --check PASS; card_check CARD_OK; dot_scope IN_SCOPE10files. Six AST assignments (rubric, thresholds, model tuple, prompt, schema and payload) are unchanged. Sixteen frozen whole files including all12 qa_criteria.json files, STANDARD, shorts_qa,005finalizer and historical recovery are byte-identical including newline. The complete registered48-file test loop and final independent review/remote CI are recorded separately after completion; not presumed PASS here.

Full registered test loop completed at11:03 UTC: all48 files PASS, aggregate exit0. The producer suite within it ran104tests67.303sOK; no synthetic test qualifies actual media. Independent technical review of frozen bytes also PASS: personal suites47adapter,30mining,46reviewer,58publisher,13pending,28historical recovery and3error-register tests. Reviewer confirmed legacy transport/call/request/upload AST after removing only opt-in branches, exact two-token workflow change, unchanged media/quality gates and one exact v8 archive. Final remote bytes, exact-SHA CI and operational preflight remain required before a real recovery.
