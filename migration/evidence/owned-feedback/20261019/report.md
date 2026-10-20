# Owned-video feedback, preserved observations

This report is descriptive and does not approve production or claim market success.

## What is now available
- Four immutable captures from October13–16:55 exact video identities,200 public-lifetime observations and32 private requested-range observations.
- Four daily reach rows preserved, including two rows outside the original eight targets. No missing row is treated as zero.
- Retention curves are retained point by point. Average view percentage is a percent; audienceWatchRatio and elapsedVideoTimeRatio are ratios; watch time is minutes and average duration is seconds.
- Every observation links by source_id to a source record with exact input-byte SHA256/path, then by JSON pointer to its source value. File hashes are distinct from fallback in-memory fingerprints.
- The complete JSON is feedback.json.gz, deterministic gzip with mtime0. Decompress with Python gzip or any standard gzip reader. It retains all observations and uncertainty fields.

## What the existing data cannot establish
- The four private reporting windows are requested cumulative date ranges. Neither captured_at nor end_requested proves complete data through that time or exact48-hour/7-day coverage.
- Upload time, snippet publication time and schedule slot are stored separately. None is promoted to verified historical public visibility.
- No reliable video-to-structure/version assignment is supplied for these historical observations. Checkpoint keys are therefore absent rather than invented; supplied assignments in unit tests produce only INSUFFICIENT checkpoints.
- No matched, predeclared baseline exists for this cohort/publication age. All55 records remain INSUFFICIENT for good/bad/neutral classification. No causal explanation or growth promise is produced.
- Aggregate CTR remains null. Daily CTR representation is explicitly provider_raw_representation_unverified, with unit source_unspecified and original raw strings retained. Daily CTR and impressions remain separate source observations; no clicks or aggregate CTR are manufactured. Empty retention remains UNKNOWN.

## Operational use
This is an offline report adapter, not a new collection job. It makes historical outcomes inspectable before designing an experiment. To evaluate the current structure, supply a trustworthy structure assignment, verified public-publication time, matching complete checkpoint metrics and a baseline declared before observing the result. Future comparisons should test one stated hypothesis and preserve cohort, age and format comparability. This patch does not set those thresholds or change a gate.

## Verification
22 new tests PASS. All36 CI test scripts personally run locally PASS. Actual CLI run twice is byte-identical; gzip roundtrip and source overwrite protection tested. Source evidence/ledger and frozen QA remain byte-identical. No network or model calls. Exact source/output hashes and suite results accompany this report. Remote exact-SHA byte verification and CI are recorded on the PR after pushing.
