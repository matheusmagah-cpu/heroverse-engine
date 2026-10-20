# Owner temporal exception — implementation report

Task #257, baseline 38c7f70502904c3e961296b680e9526c9a9bef32. The owner explicitly requested a one-post exception mechanism on 20 October2026 at21:07:33UTC, with the normal time lock preserved. This is a separate development task, not the denied replacement of #231.

Preflight: current main has no temporal exception interface. Normal finalizer cutoff is19:30UTC. Actual Short cb3ce331529437f4fadc3b14dec01dfad18909a3e9f024a99cea141e91ae956f already has real QA PASS and designated watched-review overall8.5. It has not been uploaded. The owner explicitly retained authorization for this artifact; future content requires overall>=9 in addition to existing gates.

Trust boundary: dot attests the verified authenticated conversation, with literal evidence and IDs. The registry pins one admitted receipt digest. This is operational admission, not a human GitHub review or cryptographic identity proof. No arbitrary new receipt self-authorizes.

Implementation in progress: separate finalizer wrapper, closed registry, durable remote pre-upload reservation, same-ID readback and uncertain-result blocking. Ordinary cutoff and finalizer/file function ASTs are unchanged. CARD_OK on the current card. Code review, all tests, exact-SHA CI, real generated manifest and verified publication remain pending. Not DONE.


## Implemented code and local verification,21:17 UTC
The ordinary LEAD_DEADLINE remains19:30. finalize_manifest and finalize_file AST hashes remain89ff8b6d6daffe82cbb60bc856741d791cc4f88044d6ce5cb5416d814637a2a4 and509e97f2625ea6f685bfc6ab4ce2e20d3444871d55bebea1ae9ec16d8abe1d97 respectively. The explicit --finalize-exception MANIFEST MP4 RECEIPT path first invokes that unchanged finalizer and can recover only TARGET_SLOT_LEAD_MISSED. QA/review/hash failures remain nonpublishable. Actual file hashes are checked before/after and failure leaves eligibility revoked.

Receipt canonical digest dd2990b2ecebe3a7a4ed93d842d248f8e9ea9c3a2ecbfb6921d7b91d3f4db5f2 admits only this owner-attested instruction and approved output. Registry binding is exact, not a generic authorization boolean. Before upload, the existing workflow checks the exact original target, reserves the exception for GITHUB_RUN_ID:GITHUB_RUN_ATTEMPT, commits/pushes the ledger and verifies remote bytes. Publisher changes local state to UNCERTAIN before POST; any repeated call without a video ID fails closed. After a returned ID, reservation and Short entry are atomically bound to the same ID before readback. Existing IDs are GET-only. A hard kill after upload can leave only the remote RESERVED intent: this blocks replay and requires reconciliation, not another upload.

Commands actually executed:
- /tmp/hv228-venv/bin/python -I -B migration/production/test_shorts_edit_plan.py:56 PASS,9.875s. Includes unchanged baseline AST/cutoff, malformed receipt, quality negatives, missing receipt CLI and TOCTOU.
- python3 -I -B migration/publish/test_publication_exception.py:19 PASS,2.707s. Includes digest/scope/hash/pilot/clock validation, reservation conflicts, uncertain state, reuse and atomic failure.
- python3 -I -B migration/publish/test_publish_shorts.py:38 PASS,0.101s. Includes public readback, pending-to-success same ID, uncertain upload, target mismatch before reserve and ordinary scheduling invariance.
- python3 -I -B migration/ops/card_check.py card-257.md: CARD_OK.
- git diff --check: PASS.
- Frozen shorts_qa.py, shorts_review.py and pilot005 qa_criteria.json bytes equal baseline. No prompt/model/rubric/threshold change.
- Pure integration on the actual preserved manifest and rehashed actual MP4: READY_BY_OWNER_TEMPORAL_EXCEPTION, with original QA/review/media records identical. No file was written and no provider or upload called.
Independent reviewer personally ran19+38+56 tests PASS and found no current blocker; final SHA binding and CI still pending at this report checkpoint. The generated production manifest is not yet exposed. Publication remains uncompleted.

Parent technical verification at21:17 UTC: git diff --check and direct execution of helper19 tests(2.910s), publisher38 tests(0.121s), adapter56 tests(4.321s), all exit0. Independent reviewer also executed19+38+56 PASS and inspected unchanged baseline functions, admitted evidence, exception bindings, reservation and same-ID readback. Printed synthetic errors/IDs are negative-test evidence only, never real upload evidence. Workflow verification initially used a harness that assumed every step had a name and raised KeyError; corrected harness uses optional name lookup and proved the parsed YAML outside the one allowed run body identical. No production test or guard was weakened.

Full-loop first result:44 files PASS, test_no_live_pilot_data FAIL because the adapter test read the pinned evidence file with a pilot-005-prefixed filename; the conservative guard treats that path as live. Correction: adapter test now embeds the exact immutable receipt JSON literal instead of reading a repository path. The guard itself is unchanged; its4tests PASS. This is a fixture isolation fix, not a weakened check. Workflow review added FETCH_HEAD==HEAD immediately after remote reservation fetch, before upload, so a concurrent hold/manifest/code change fails closed even when the ledger alone matches. Publisher suite now39PASS including this guard. Final aggregate rerun is in progress.

## Generated recovery evidence,21:22 UTC
Code SHA f0f193368a04cf81cd5c3dbca4ee082843c87d03 passed CI39499450353; all45test files PASS, nine remote blobs match exact bytes/newlines, independent review PASS and parent technical tests19+39+56PASS. Independent review is dot technical review, not attributed to the owner or Claude.

Executed the validated explicit finalizer once on the actual preserved MP4:
`python -I -B migration/production/shorts_edit_plan.py --finalize-exception migration/production/pilot-005/shorts/shorts.json migration/production/pilot-005/shorts/short-00.mp4 migration/evidence/publication-exceptions/pilot-005-cb3ce331-owner.json`
Output: READY_BY_OWNER_TEMPORAL_EXCEPTION, publish=true, COMPLETE at2026-10-20T21:22:18.211167+00:00. The ordinary failure is retained as TARGET_SLOT_LEAD_MISSED. Real MP4 SHA remains cb3ce331529437f4fadc3b14dec01dfad18909a3e9f024a99cea141e91ae956f. Generated manifest SHA1973f5f4ceb96eeb70de84d3280347d0cb69df6d39151d5456c28fadba91d942. Automatic output only; no manual flag or approval edit.

Compared original and generated manifest: QA, review, media checks, QA/output hashes, edit plan, review rubric and source pilot are identical. Only generated eligibility/release/finalization metadata changed. No rerender or provider call. Provenance/licenses remain those of the previously qualified sources; no replacement asset. Long005 prerequisite PASS; remote publication hold absent, ledger has no entry for this Short and no exception reservation. Existing long ID XDwxi4pvllM. Intended Short title is A Prayer for Peace in Your Relationships #shorts, full-prayer URL https://youtu.be/XDwxi4pvllM. Authenticated channel identity and actual final metadata/readback will be verified by the publisher. No upload or public availability is claimed yet; final delivery CI/review and runtime gates remain.
