# Exact-byte helper recovery and complete offline preflight

State: local proposal only. No new workflow dispatch, provider request or commit.

## Second run: precise observed result

Run 38822885890, job 116723429947, commit e635c8ba094c3e2a96414b27b5da7d546de68c6f, run 2/attempt 1 completed FAILURE at 23:19:46 UTC. Thirty-five tests passed. Disk 14,092,525,568 bytes and two identical memory samples 7,258,116,096 bytes passed the scoped resource policy. Failure was AUTH_HELPER_IDENTITY_MISMATCH before OAuth. Zero network attempts, zero Data API calls/units, unchanged ledger, no CSV or report metadata received.

Artifact 12012738845: ZIP 906 bytes; SHA256 df41bfeb11d465b7752aeb8059eaac7ffb79871f040b892e742405c1120817ca. Downloaded once, hash checked, execution.json preserved exactly. First run 38822029275 and its original receipt remain unchanged.

## Cause and exact correction

The earlier local tool-based file creation appended one LF to both helper source files, and the pins were mistakenly calculated from those staging copies. Remote files did not change: local copies equal exact remote bytes plus one LF, and their ASTs match. Correct pins are calculated directly from original remote content bytes, without stripping/normalizing anything:

- migration/oauth_health.py: 3,377 bytes; Git blob 757c12001b4ea6336d1a3f958cd33dd339024b55; SHA256 b2f667c880d6e5cf5b7e60889acaf7b9eddd28db8720cf8b9e8702feeb8f412c.
- migration/verify_worker_oauth.py: 4,080 bytes; Git blob 6be04fedb6204b8e4bd3cc623494970ee93c0a06; SHA256 aebf4236d9afddd702a79bbfc720e8cfa1560c2132dd1a50bfaa48956e015e46.

The exact hash guard remains mandatory; added LF, CRLF rewriting and any other bytes fail. No helper source is changed.

## Complete checkout-shaped offline verification

Fetched ten exact files at immutable e635c8b, preserved raw connector responses first, reconstructed their exact UTF-8 bytes and independently recomputed every Git blob hash. Files include both helpers, the original observer snapshot, first failure receipt, core/wrapper/test files and workflow. Remote observer bytes equal the existing original input byte-for-byte. No invented fixture substitutes that snapshot.

Original reconstructed checkout: all 35 tests pass. Candidate checkout: 41 tests pass, including new checks for every source/helper/prior-receipt SHA pin, exact helper Git blobs, import safety, actual helper configuration validation with synthetic credentials, readonly-scope rejection, unapproved token endpoint/client rejection, exact report IDs/create/start/end timestamps, workflow private/main guards, and both preserved failure receipts.

A complete main() path runs with actual helper validation and an injected synthetic transport in real checkout layout, reaching both synthetic CSV outputs and receipts with expected one refresh/two metadata/two CSV operations. No real credentials are used. The full suite runs under a socket/urllib network guard: zero attempted live connections. Synthetic success is not live OAuth or Reporting success.

The new recovery guard admits exclusively run_number=3 and run_attempt=1. It validates both immutable zero-network receipts before the secret step and again before auth; run1/run2/run4 and rerun attempt2 fail. Resources, five-operation cap, exact two reports, no retries, redirects off, private/main restrictions, raw CTR strings, manual approval=false and production/publication=false remain intact.

## Remaining uncertainty and foreseeable blockers

No additional deterministic source/layout/import/pin/config-shape blocker was found by the complete offline preflight. Live secret validity, current OAuth grant status, permission to retrieve each report, returned download URL shape, report availability, actual CSV headers/content and transient network conditions cannot be established by fixtures. These remain fail-closed checks; no assertion of live access or complete reach data is made. Existing exact URL/schema guards are deliberately not broadened based on guesses.

No third attempt should be launched until root reviews this consolidated change. If actual report bytes arrive and parsing fails, preserve and fix offline rather than recollecting them.

## Candidate paths

- Modified wrapper, wrapper tests, resource tests and workflow.
- New test_exact_helper_identity.py and test_checkout_preflight.py.
- New migration/evidence/owned-reach-helper-failure-38822885890.json, copied byte-for-byte from downloaded artifact.

These seven paths are listed with hashes in consolidated-manifest.json. No source helper, original snapshot, first failure receipt, AV/production contract or active observer is modified. Local evidence: remote-checkout-byte-proof.json, helper-byte-proof.json, consolidated-offline-proof.json, original-checkout-tests.txt and candidate-tests.txt.
