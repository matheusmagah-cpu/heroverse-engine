# Review evidence schema correction (E208)

Base: `119757db01c26ad4f1d627cc79e260a92ff5903d`.

## Reproduction and scope

Before the fix, the new long-review regression had 10 failing subcases:
truthy scalar/object evidence, invalid list elements, and malformed issue entries
were accepted. The prepublication regression had 14 failing subcases, including
absent evidence and rubric scores of infinity and 11. These are offline input
validation reproductions, not a claim that a published video bypassed review.

## Correction

The session reader and final prepublication reader now share evidence-list and
0-10 numeric-score validators. Evidence must be a nonempty list of nonblank
strings; issues must be a list of nonblank strings (an empty list is valid).
Booleans, NaN, infinities and out-of-range values are not scores. Invalid review
evidence stays AWAITING_REVIEW/UNKNOWN, not an editorial verdict.

The reviewer allowlist, owner floor, rubric thresholds, frozen QA, stored media
and historical approvals are unchanged. The five committed session review
records have compatible evidence/issue shapes; no historical record was edited.

## Manual code and security review

Reviewed the diff separately from the reproduction. No network call, provider,
credential, scheduler, file deletion or publication was added. The helpers are
pure predicates, and no review record is rewritten by them. They do not open
paths supplied in evidence. The prepublication reader handles a non-object
watched review as missing evidence. Existing identity and media-binding checks
remain. Test fixture enrichment adds the documented evidence/issue fields;
it does not relax any frozen criterion or production score.

No Claude-hosted review/security plugin was invoked; this is a manual review.

## Limits and next step

Schema validity does not prove that evidence files exist, that their contents
were inspected, that audio was heard, or that the declared reviewer is genuine.
The change is not a review, approval, render or publication. Complete audiovisual
access and a genuinely designated reviewer remain prerequisites. Integrate only
after the PR checks pass on the exact submitted head.

Targeted validation after the fix: long review 10, prepublication 22,
owner quality policy 7, error register 13 tests PASS. The new regressions were
run before and after the implementation; their initial failures were retained
in the execution record. `git diff --check` PASS.

The canonical 83-suite list was executed locally: 81 passed in the default
isolated Python; lipsync (31 tests) and cinematic (2 tests) failed only because
that interpreter lacks OpenCV. Both unchanged suites then passed with the
existing `/tmp/heroverse-validation-venv/bin/python -I -B` (OpenCV 5.0.0).
Thus all 83 suites have passing results on this code, with the initial
environment failures preserved; this is not a claim of one 83/83 default-Python
run or of a remote CI result. No dependencies were installed for this fix.
