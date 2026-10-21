# Owner quality floor and pilot-006 diagnosis

## Scope and authority
Issue #259, SPEC v3, baseline 767badb5f99ef89274693813bd2e8ea1ec76f22c. The owner's 2026-10-20 20:14:14 UTC requirement applies an additional overall >=9 eligibility condition to new publications. It does not rewrite the frozen rubric's PASS threshold, previously uploaded videos, or the consumed pilot-005 temporal exception.

The first attempt to create the separate issue was denied before execution because explicit authorization for a new issue was missing. The owner specifically authorized that action at 23:53:59 UTC; one retry created #259 at 23:54:25 UTC. No alternative route or repeated denied rewrite of #231 was used. #257 remains BLOCKED for formal post-upload verification and is not DONE.

## Implementation
- A pure policy requires a designated PASS review, a finite numeric overall score in [9,10] excluding bool, and exact lowercase SHA256 binding.
- Shorts selection and pending eligibility enforce the additional policy. Stored policy flags cannot authorize publication. A low score remains its original editorial verdict and receives a separate policy rejection.
- The Short publisher rechecks eligibility, actual media hash and existing QA before a new upload. Existing IDs remain readback-only even if a historical publish flag is false, the score is 8.5, or the local media was cleaned up.
- The long publisher hashes actual VIDEO bytes before session creation and requires the manifest and complete review to match. It adapts a copy of the nested watched review to the existing top-level hash schema without modifying the review. Existing IDs retain the existing idempotent resume behavior. Canonical long QA/approval revalidation remains in the unchanged workflow step; the new helper does not pretend to perform QA.
- No workflow, schedule, permissions, credentials, provider call, render, live approval, ledger or frozen criterion was changed.

## Real diagnosis, not an invented provider cause
Run 39453449948 executed reviewer code at 5ec6ec0265d20f2d9950e900ea9bf43f1038f462 that caught exceptions and saved only their class. Its three pilot-006 records have QA PASS and NOT_REVIEWED_ProviderFailure. The exact HTTP/provider cause is null because the diagnostic was discarded, not because an editorial verdict failed. No claim that these were 503 or quota errors is supported.

The three MP4 release digests match their manifest records. This is a GitHub-record comparison, not a fresh local binary hash. The diagnostic JSON records the exact hashes and links. Existing review-only workflow uses N=3; reusing it unchanged risks making three records eligible and allocating extra slots. A precise one-candidate contract must precede media recovery. Phase 1 performs no provider call or render and does not claim a qualified Short for 2026-10-21 14:00 UTC.

## Acceptance evidence
Personal execution with python3 -I -B: owner_quality_policy 5 tests PASS; pending_shorts 6 PASS; publish_shorts 44 PASS; publish_video 11 PASS; first_comment 14 PASS; shorts_review 33 PASS. The independent reviewer additionally executed publication_binding 17, publication_exception 19 and prepublish_gate 8 tests, all PASS. Temporary technical direction independently ran the six primary suites at 2026-10-21 00:01 UTC, all PASS. These are synthetic tests, never upload or watched-review evidence.

git diff --check -> PASS. card_check.py on the exact SPEC v3 -> CARD_OK. The original prompt/model/rubric AST checks remain in test_shorts_review.py and pass. All qa_criteria.json files, shorts_qa.py, prepublish_gate.py and ordinary temporal finalizer bytes are identical to baseline.

Counterexample: original pending_shorts.approved returned True for a bound PASS 8.5 record; the new code returns False. For the long publisher, offline baseline tests accepted score 8.5 and changed VIDEO bytes with mutually matching stale manifest/review hashes (one session and upload each); new code rejects both with zero session and upload calls.

An initial new test invocation failed because its fixture omitted the required setup(done=()) argument. This was a test-construction error, not media or infrastructure evidence; corrected fixtures pass without relaxing assertions. Full PR loop, exact remote bytes, final SHA review and CI are recorded in the delivery comment when available. No DONE or production qualification is claimed here.

## Independent public observation
At 2026-10-20 23:59:36 UTC, the unauthenticated page for tri-CUwy_m0 said private. At 2026-10-21 00:01:44 UTC it displayed the HeroVerse long video and 25:33 duration publicly, consistent with the scheduled 00:00 UTC transition. Playback remained inconclusive in the already limited cloud browser (0:00, readyState 0); no API processing confirmation or playback PASS is fabricated. No dispatch or publication change was made for this observation.
