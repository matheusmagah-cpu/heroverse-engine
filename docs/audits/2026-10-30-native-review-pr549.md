# Verified security sweep: native-review-pr549, 2026-10-30

## Context

Zone: `native-review-pr549`. Trigger: required pre-merge sweep for PR #549 because
its change set includes publishing-test paths; the existing workflow is also a supporting security boundary. Scope:
`.github/workflows/native-review.yml`,
`migration/production/bible/native_review.py`, and
`migration/publish/test_native_review.py`. Direct caller/policy reads are
supporting evidence, not a sweep of every publication or provider component.

Method: original **Verified Security Sweep 1.4.0**, from
https://github.com/SecPlusDev/verified-security-sweep/tree/v1.4.0,
upstream commit `90a73a192b404ad139bee970f49f73f07410c949`.
The original SKILL.md, five reference files and five Python scripts were read and
used without modification. The MIT license and source manifest were preserved;
all 13 retained upstream files, including the plugin manifest and license, were
verified against their Git blob IDs and SHA256 hashes. This is an execution of
that workflow by **Codex**, not a claim of Claude-hosted execution or review.

Snapshot: branch `claude/native-review-grounding-20261030`. The inspected working
files include the pending E222 description check and regression improvements over
PR head `8e4decf8d87feb7c4b006688a3ceff24ed24f1bc`, reconstructed as index tree
`95504516d5c2ccde0a42c1d5dd6279c602ac8059`. Local HEAD
`d65fbc6da4408d4fa429bf451b2256886a3717d3` is reconstruction history, **not** the
reviewed PR head. The exact file hashes below bind this result; later changes need
reassessment. This zone contains the PR's evidence-grounding change and its pending correction. The workflow itself matches the supplied PR
index tree. Concurrent coordination-document edits are outside the code verdict.

| Inspected working file | SHA256 |
|---|---|
| `.github/workflows/native-review.yml` | `50f9e06d6e4d001309af893e8e9c48d235115396d182bfa0c034ad159fa1d2db` |
| `migration/production/bible/native_review.py` | `c65b65db53f6d7786f7d376db8a7536e2d041a0811c4f1e7a8e8a3314bc3470d` |
| `migration/publish/test_native_review.py` | `8093125609b82bdf1a06eb6bb80c6789db6ecad66ebfc8d5f1c93582bebc963a` |

Pre-read: AGENTS.md, CLAUDE.md, security guidance, categories, all 32 previous dated
reports and the undated Pavo preparation report, then registry and findings index.
No `docs/specs/` or coverage matrix exists. The previous native-master, native-review-input,
native-review-hash and native-review-grounding reports closed transport, certificate,
hash-decoding and timestamp cases; their limitations remain applicable. The prior
manual reports are not retroactively relabeled as plugin executions.

Original `fresh_code.py --src migration/production/bible/native_review.py --tests migration/publish --json`
reported two historical commits and a test mention. The local reconstructed
history makes that a limited churn signal, not proof of full upstream history.
Original `findings.py recheck` reported no open findings; no recorded command ran.
Stack probes were derived from security guidance: dispatch interpolation,
credential placement, redirects/hosts, subprocess construction, state transitions,
approval writers and exact hash binding. Hits were read, not counted as findings.

## Delegation

One fresh, read-only Codex reviewer, `native_security_reader`, read the entire
three-file zone. Its brief required original skill and verification reference;
project rules, all prior audits, categories and registry; exact sink lines;
source-to-sink and missing-mitigation evidence; calibrated severity; refused
candidates; and explicit read/skipped coverage. It named the earlier native reports
and their closed cases, prohibited live calls and edits, and required working-file
hashes instead of claiming local HEAD as the PR head.

The coordinating Codex reviewer independently opened every cited control, read
the direct dispatch and policy wiring, ran the focused tests, and reproduced the
punctuation-only limitation with a mocked provider response. Verification and this
report stayed with the coordinator. No candidate was accepted solely on the
fresh reviewer's paraphrase. Both reviewers obtained the same final file hashes.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 punctuation-only text is a new E222 security bypass | native-review-pr549 | FALSE POSITIVE | Low candidate | - | Claim correctness: the authorized repair is structural nonempty text after timestamp/separators, not semantic quality. Acceptance is an explicit limitation. | `migration/production/bible/native_review.py:334`; independent mocked `poll()` probe ran: `00:05 .` retained overall 6.6, false owner-floor/publication/production flags and one GET. |
| S2 fixed duration breaks an authorized generic-master service | native-review-pr549 | FALSE POSITIVE | Medium candidate | - | Claim correctness: deployed authorization is the actual Short09, not arbitrary-duration masters. | `migration/production/bible/native_review.py:315`; `migration/ops/CLAUDE_REVIEW.md:77`; native duration and valid-coverage tests ran, pass. |
| S3 encryption failure exposes plaintext or permits inference | native-review-pr549 | FALSE POSITIVE | High candidate | - | Existing mitigation: encryption check precedes provider mutation; failures block subsequent default-success inference steps. | `migration/production/bible/native_review.py:395`, `.github/workflows/native-review.yml:64`, `.github/workflows/native-review.yml:74`; real local certificate roundtrip and workflow-boundary tests ran, pass. |
| S4 missing repaired evidence becomes validated success | native-review-pr549 | FALSE POSITIVE | Medium candidate | - | Existing mitigation: raw response is saved as unvalidated before validators run; rejected evidence cannot resubmit or grant approval. | `migration/production/bible/native_review.py:374`, `migration/publish/test_native_review.py:104`; timestamp/description and field regressions ran, pass. |
| S5 wrong master reaches inference | native-review-pr549 | FALSE POSITIVE | High candidate | - | Closed earlier; no current bypass of the exact hash, size, MIME, URI and state checks found. | `migration/production/bible/native_review.py:273`, `migration/production/bible/native_review.py:295`; hash-encoding and wrong-master tests ran, pass. |
| S6 uncertainty or recovery automatically repeats a POST | native-review-pr549 | FALSE POSITIVE | Medium candidate | - | Existing mitigation: uncertain state precedes POST; recovery proves inference was skipped and only retrieves the existing upload. | `migration/production/bible/native_review.py:302`, `migration/production/bible/native_review.py:125`, `migration/production/bible/native_review.py:219`; replay/recovery tests ran, pass. |
| S7 dispatch or provider input exposes credentials through shell/redirect | native-review-pr549 | FALSE POSITIVE | High candidate | - | Existing mitigation: event JSON/env, argument-list subprocess, strict provider host and redirect refusal; sanitized error output. | `.github/workflows/native-review.yml:45`, `migration/production/bible/native_review.py:60`, `migration/production/bible/native_review.py:73`, `migration/production/bible/native_review.py:175`, `migration/production/bible/native_review.py:413`; host/redirect and workflow tests ran, pass. |
| S8 native evidence grants production/publication approval | native-review-pr549 | FALSE POSITIVE | High candidate | - | Claim correctness: evidence receipt is not an approval and no direct publication consumer accepts it as one. | `migration/production/bible/native_review.py:210`, `migration/production/bible/native_review.py:379`; workflow/poll tests ran, pass; direct-consumer search found no approval reader for this receipt. |

## Confirmed defects

None. **Zero confirmed defects from eight examined candidates**, at every severity.
There is no current confirmed defect requiring a failing reproduction test, and
no invented finding was appended to the existing empty `findings.jsonl`.
This result is confined to the file hashes and authorized evidence-only flow above.

## Refused or unconfirmed candidates

- S1: refused, claim correctness. `EVIDENCE_COMPLETE` identifies structural validation,
  not semantic truth. The observed punctuation-only response is retained as a
  limitation, just as a plausible invented sentence can pass the schema. It does
  not change scores, satisfy the 9.5 floor in this probe or grant publication.
  No open-ended semantic heuristic or production change is proposed by this sweep.
- S2: refused, claim correctness. The owner-authorized route is the 175-second
  Short09. Reusing it for another duration would require a separately authorized
  contract change; this sweep does not claim generality.
- S3: refused, existing mitigation. The certificate roundtrip runs before provider
  mutation. Only CMS ciphertext is eligible for an artifact; an encryption or
  persistence failure leaves the job failed and later inference skipped.
  No plaintext-artifact fallback exists in the inspected workflow.
- S4: refused, existing mitigation. Invalid evidence remains `COMPLETE_UNVALIDATED`
  with the actual response preserved. The pending regression exercises `poll()`,
  unchanged scores, no approval and refusal of subsequent poll/submit attempts.
- S5: closed earlier by `2026-10-30-native-review-hash.md` and the transport boundary
  in `2026-10-29-native-master-review.md`; refused, existing mitigation still holds.
  Both supported provider hash encodings resolve to the same required digest.
- S6: refused, existing mitigation. The receipt is durably changed before inference;
  matching historical runs and attempts are refused, and recovery proves skipped
  inference before reusing an existing uploaded file. No automatic retry was added.
- S7: refused, existing mitigation. Dispatch values do not enter shell source; API
  credentials go only to the fixed provider host, redirects are refused, and the
  exception boundary prints local codes rather than URLs or provider bodies.
- S8: refused, claim correctness. `production_approved` and `publication_ready`
  remain false; native evidence does not replace source, thumbnail, plan, QA,
  prepublication or publishing gates.

## Coverage

Read all three scoped files in full. No scoped file skipped. Supporting reads:
`migration/ops/dispatch_guard.py` native-review registration and subject handling,
`migration/ops/CLAUDE_REVIEW.md` native evidence policy, operations guidance and
direct-consumer references. Applied all three original lenses: exploitability,
claim correctness and existing mitigation. Categories covered: secrets,
workflow injection, token scope, publication-gate integrity, failure-to-pass,
spend checks, external integrations, replay/concurrency and path containment.
No changed frozen criteria, approval writer or new spending path was found.

Primary commands, run from repository root with bytecode writing disabled:

- `python3 -I -B migration/publish/test_native_review.py`: 15 tests, PASS.
- `python3 -I -B migration/ops/test_dispatch_guard.py`: 33 tests, PASS.
- Independent isolated mocked `poll()` probe: punctuation-only text accepted as
  described in S1; overall unchanged, one GET, no publication/production approval.
- Original `check_citations.py`: PASS, 20 citations opened, zero invalid citations.
- Original `check_report.py`: PASS, eight verdict rows, eight refused entries, zero problems.
- Original `findings.py check`: PASS, zero entries and zero problems.
- Original `sweep_status.py --check`: PASS, 18 zones, 33 dated reports, zero divergent/stale.
- `git diff --check` for the audit files: PASS.

Provider internals, live billing, real media truth, GitHub-hosted execution and
broader publication implementation were not revalidated. No real credential,
private media, private account/provider identifier, live network operation,
generation, dispatch or publication was used by this sweep. Source installation
used the authorized GitHub connector; that is distinct from invoking a production
workflow. Full canonical PR checks remain the integrating agent's separate duty.

## Hand-off

No code fix proposed. Keep the schema limitations and evidence-only boundary
explicit; actual audiovisual consistency and existing publication gates remain
required. The required upstream sweep is complete for the bounded hashes above,
with the original report/index/registry validators passing. This is not whole-project
security certification or audiovisual approval.

The original status script found one pre-existing registry reference mismatch:
`thumb-character-first` names the existing `2026-10-27-thumbs-460.md` report but
cannot match that filename. The registry slug is corrected to `thumbs-460` with
the former label retained in its argument. No historical report, finding, yield
or review conclusion is altered. This is solely the operational reference needed
for the original registry check; no unrelated code change is made.

The sweep changes only this report and `docs/audits/sweep-registry.md`; it does
not modify production code, tests, credentials, schedules or approval records.
