# Existing-reach run 38822029275: observed block and bounded correction

## Observed result

Run 38822029275 / job 116720623988, main 26d3103aaef8064d7e2e0f74e180d5bfbf4b2dec, first run/attempt, completed FAILURE at 23:11:26 UTC on 15 October 2026. All 30 fixture tests passed. The read stage terminated before OAuth/Reporting: execution.json says RESOURCE_MARGIN_REQUIRED, requests={}, request_events=[], network_operations_attempted=0 and Data API calls/units=0. Ledger was untouched.

Artifact 12013106924 was independently downloaded once: ZIP 467 bytes, SHA256 2d51c77e39724840906d6ae84d1d9ca53dec6eeb87bcac5a547f75e4edb39d60. It contains only execution.json, preserved byte-for-byte as owned-reach-preflight-failure-38822029275.json. No report metadata or CSV was obtained, so there is nothing to re-download/reparse and no evidence of an OAuth/Reporting access failure. The old preflight raised before returning measurements, so existing evidence cannot say whether disk, memory or both were below threshold.

## Scope-specific resource proposal (local candidate, not yet approved)

The inherited 15 GiB disk/2 GiB RAM preflight was designed for heavy AV/model stages. This probe is standard-library text ingestion with fixed two reports, maximum 4 MiB each/8 MiB total, 20,000 rows per report, no model/media packages, no synthesis/render and 90-second execution bound. The proposal does not edit any original AV/production resource requirement or admit heavy work.

Synthetic local measurement used two CSV inputs of 4,000,086 bytes and 20,000 rows each, with both parsed lists retained concurrently. Peak RSS was 94,120 KiB (91.91 MiB), including tracemalloc overhead; traced Python peak 47,776,104 bytes; runtime 6.97 seconds. This is fixture measurement, not provider delivery or universal worst-case proof. Receipts and retained provider strings remain byte-bounded; no fields are exported to arbitrary public destinations.

Proposed minimum for this lightweight probe only: 256 MiB free disk and 512 MiB available RAM, checked after checkout and before credentials. Disk covers an explicit 32 MiB working allowance (raw 8 MiB + ZIP staging 8 MiB + another 8 MiB transient copy + 8 MiB receipts/log/overhead allowance) with 8x headroom. RAM exceeds measured process peak by 5.57x, leaving approximately 420 MiB beyond measured Python RSS for runtime/transport/artifact-action overhead. Upload action's own memory was not measured; it runs after the Python process exits, and the margin is conservative rather than a guarantee.

Byte/row/time/host/redirect/retry and production restrictions do not change. Two MemAvailable samples separated by 0.1 seconds are recorded; the lower controls the admission check. Both observed quantities, both required quantities, both pass/fail flags and resource policy BOUNDED_REPORTING_STDLIB_ONLY_V1 persist even when admission fails. No cache removal, package removal, host reconfiguration or billing action is proposed.

## One explicitly reconciled next attempt

The new candidate admits only workflow run_number=2 and run_attempt=1. First run, third run and rerun attempt2 are rejected. It requires the exact original zero-network failure receipt by SHA256, run ID, source commit, error code, requests/events and Data API fields. Workflow validates that receipt before the secret-bearing step; Python repeats it before resource measurement/auth. This is a separate reviewed execution, never a rerun or deletion of the original failure. All private repository/exact main guards remain unchanged.

## Changed files proposed

- migration/owned_reach_probe/run_existing_reach_probe.py: bounded resource policy, measurements-on-block and exact prior-failure recovery guard.
- migration/owned_reach_probe/test_run_existing_reach_probe.py: run2 expectations, run3 rejection.
- migration/owned_reach_probe/test_resource_preflight.py: new negative/resource/recovery tests.
- .github/workflows/owned-reach-existing-once.yml: exactly run2/attempt1 and pre-secret prior-receipt check.
- migration/evidence/owned-reach-preflight-failure-38822029275.json: exact original receipt, not rewritten.

35 offline tests passed with zero provider calls. The synthetic measurement script/result and original downloaded ZIP/log/API responses remain local for independent review. No new commit, dispatch, retry or provider request was performed. Root must approve the scoped resource policy and recovery before any execution.
