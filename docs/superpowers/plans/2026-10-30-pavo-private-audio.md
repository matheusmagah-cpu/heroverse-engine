# Private Pavo audio delivery implementation plan

> For agentic workers: use superpowers:executing-plans for this single bounded change.

**Goal:** Generate one private DRAFT talking clip from an existing exact WAV without exporting media, URLs or credentials to public GitHub.

**Architecture:** An Actions job opens one Pavo attachment upload, encrypts its receipt to the existing operator certificate, and waits for the caller's direct PUT. It verifies the received bytes, then uses the existing PavoVideoClient for exactly one generation. Public claims and conversation IDs use the existing shot-probe record branches; private provider results stay in CMS artifacts.

**Tech stack:** Python standard library, existing Pavo adapter/quota guard, OpenSSL CMS, pinned GitHub Actions.

**Spec:** migration/strategy/DECISIONS.md, Owner recovery direction 2026-10-30; migration/ops/CLAUDE_REVIEW.md private evidence transport.

## Constraints

- Zero new spending; exact zero quote including audio/reference before upload and again through the existing generator.
- One generation per exact manifest hash, never automatically replay an unknown submission.
- Existing executor lease, subject concurrency, shared quota, 25 Short jobs/day and original publication gates remain.
- Approved Keeper reference and exact PCM SHA256; no voice reconstruction or media in public logs/artifacts.
- DRAFT only: a completed generation does not approve source, speech, lip sync, plan or publication.
- Original toolkit and verified security sweep before merge; all canonical tests and CI.

## Review focus

Uncertain create/stream acknowledgement; lost persistence after provider effects; malicious storage redirects or headers; mismatched audio bytes/duration/reference; competing executor or exhausted shared quota.

## Task 1: private attachment and one-shot generation

Files: migration/integrations/pavo/private_audio.py and test_private_audio.py; .github/workflows/pavo-private-audio.yml; dispatch_guard.py; pr-checks.yml; ERRORS.json; OPERATIONS.md.

- [ ] Write tests proving malformed manifests, nonzero quotes, unsafe URLs, changed WAV bytes and replay are refused before generation; durable conversation ID precedes stream; unknown outcomes are GET-only.
- [ ] Run the tests and observe RED for the missing implementation.
- [ ] Implement manifest validation, encrypted upload receipt, bounded exact-byte readback, existing-adapter submission and same-ID polling. Use a shot-probe branch claim before external mutations and persist conversation ID in the quota callback before streaming.
- [ ] Integrate the workflow with existing dispatch/subject/quota controls and record E226 with its canonical regression.
- [ ] Run targeted tests, original review workflows, canonical suites, then PR and CI.
- [ ] Transfer one prepared WAV, confirm a real provider ID/result, and retain private output. Stop on a quota/credential refusal and record exact state.

Ruling: execution is already authorized by the owner's repeated requests; no additional plan-approval pause. Keep progress here and in the existing handoff, not a parallel production ledger.
