# Verified security sweep: request-input-digits, 2026-10-30

## Context

Required original workflow sweep of the one-line input-key validator correction in
`.github/workflows/requests.yml`, its regression additions in
`migration/ops/test_requests.py`, and E229 in `migration/ops/ERRORS.json`.
Trigger: the integrating agent reported BAD_INPUT in dispatcher run 41072937005,
before any claim or provider dispatch, when the committed request contained the
legitimate `sha256` input. This sweep reproduced that failure locally rather than
inferring success from the earlier Pavo CI runs.

Actual reviewer: **Codex**. Original **Verified Security Sweep 1.4.0**, upstream
`SecPlusDev/verified-security-sweep` at
`90a73a192b404ad139bee970f49f73f07410c949`; original scripts and references retained.
Vulnerable live/base commit: `a3b79cba5d46a51ebc06148b70337ed3ac069dbb`.
Final local source commit: `212da1afc808c988c985e9d26dabae3d4f356f41`.
The integrating agent archived that source remotely as
`1a8cf534bbc8413d58d68cb29ead3a4d9a7999e0`; the coordinator independently
verified its GitHub GET metadata against the local tree
`043aba5c6ed97fbc4b011f8b2ad3868995061cc1`. The vulnerable base is already a
real public commit; the finding index binds directly to it. The recheck log keeps
the local commit on which tests actually ran.
Diff: three files, 58 insertions and one deletion; the only runtime change is the
key regex. Root implemented and committed the fix; the sweep made no production edit.
A later operational commit `ebf907046358401105aa20f32106bc813efe8219` adds six lines of `_resume`
metadata to the existing pending request only. The coordinator compared its parent
and result: workflow and every input value are identical, `_dispatch` is absent,
and no duplicate request path was added. This bookkeeping delta does not alter
the runtime freeze above; it was inspected separately before hand-off.

Mandatory pre-read was retained after byte-comparing 41 rules/audit files against
the preceding completed checkout, all identical. This includes AGENTS, CLAUDE,
security guidance, categories, every prior report and registry, including the
PR553 Pavo sweep. No `docs/specs/` or coverage matrix is present. Relevant previous
closures: the E165 durable-request-claim integration in
`2026-10-28-gpt-reviewer-handoff.md`, and the separately fixed Pavo recovery/quota
findings in `2026-10-30-pavo-private-audio.md`. Their indexed commands were listed,
inspected as ordinary test-runner calls, and rerun: both remained FIXED, with the
append-only recheck evidence recorded. They are not new findings in this zone.

Original fresh-code and registry scripts ran. The new validator is the deliberately
bounded zone despite higher churn elsewhere; the migration test-root heuristic
was not treated as evidence of absent tests. Initial registry: 20 zones, 35 dated
reports, zero divergent/stale entries. Probes covered shell interpolation,
argument construction, claim-before-dispatch ordering and unchanged credentials.

| Final changed file | SHA256 |
|---|---|
| `.github/workflows/requests.yml` | `6f53971f08ca43b442ab0d068018e508ca867984df25b65a951cf0e9366cae47` |
| `migration/ops/test_requests.py` | `8d6cca7e7bb43b0d34269c281a927f3d2b141952cfc83dca13b682fde663ef5b` |
| `migration/ops/ERRORS.json` | `b8dc4709b9bc7bc677c70c90d70b0939c5f157aded49e94d2b405b23ad5ad2ae` |
| `migration/requests/20261030-pavo-private-k-close-once.json` (operational metadata only) | `db37ba6f60ac7a0dfb40aa8a95dbc561983cb6e61cc29870efcf59a13a67c067` |

## Delegation

The original skill explicitly permits the coordinator to read a single small
zone directly. That exception was used: one validator line, its complete workflow
caller and existing offline shell harness. The coordinator is independent of the
root agent who wrote the fix and read the frozen delta as a review. No additional
reviewer was claimed. Verification, reproduction, reporting and original-script
validation remained with this Codex sweep.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| F1 legitimate digit-bearing input name is rejected before dispatch | request-input-digits | VERIFIED REAL | Medium | Medium, fixed | Availability/correctness; the request stopped before any claim or provider call. | `.github/workflows/requests.yml:56`; exact vulnerable-commit shell reproduction ran: 1 expected FAIL (BAD_INPUT), 2 controls PASS. Final same test ran, PASS, including exact sha256 value and durable claim. |
| R1 allowing digits opens shell or option injection through the key | request-input-digits | FALSE POSITIVE | Medium candidate | - | First character remains lowercase/underscore; digits are allowed only afterward. | `.github/workflows/requests.yml:56`, `.github/workflows/requests.yml:58`; eight invalid-key cases in the sweep and eight canonical key cases ran, PASS: no claim or dispatch. |
| R2 new accepted keys make input values execute as shell syntax | request-input-digits | FALSE POSITIVE | Medium candidate | - | The workflow still uses eval, but the assembled arguments are individually shell-quoted and tested as literal values. | `.github/workflows/requests.yml:57`, `.github/workflows/requests.yml:58`, `.github/workflows/requests.yml:90`; real-shell canonical metacharacter/newline/certificate fixture ran, PASS; no marker file created. |
| R3 the fix permits a POST before durable claim or replays an uncertain dispatch | request-input-digits | FALSE POSITIVE | Medium candidate | - | No claim, push, retry or dispatch ordering changed. | `.github/workflows/requests.yml:84`, `.github/workflows/requests.yml:90`; all 10 canonical dispatcher tests ran, PASS, including claim-push failure, lost acknowledgement, crash and stale checkout. |

## Confirmed defects

**One Medium defect confirmed and fixed; zero open confirmed defects.** No High,
Critical or separate Low finding was established.

F1 / E229: at `.github/workflows/requests.yml:56`, the original fullmatch accepted
only lowercase letters and underscores. A valid request to a workflow declaring
`sha256` therefore raised BAD_INPUT before claim creation. The path is the pending
JSON file, the embedded Python input loop, then the validation exception; neither
the later workflow's own validation nor argument quoting can restore a rejected
legitimate key. The actor is the authorized operator submitting the bound request.

The reproduction file extracts the exact vulnerable workflow from real commit
`a3b79cba5d46a51ebc06148b70337ed3ac069dbb` when REQUESTS_SWEEP_SNAPSHOT is set.
It then runs the workflow's actual shell using the existing test harness, a
synthetic local bare Git repository and stub gh. The initial sha256/input_v2 test
failed with BAD_INPUT; original snake_case and invalid-key refusal controls passed.
No external dispatch occurred. The default test invocation reads current code,
so the index's reproduction can distinguish the fixed state on later sweeps.

Root changed the regex to `[a-z_][a-z0-9_]*`, preserving the existing shlex.quote
argument construction and durable-claim ordering. The final reproduction verifies
one dispatch, exact values and a remotely durable claim in the local stub fixture.
The full canonical suite verifies malicious values remain literal and ambiguous
outcomes cannot replay. The added canonical E229 test begins at
`migration/ops/test_requests.py:164`.

## Refused or unconfirmed candidates

- R1: refused, existing mitigation. Empty, uppercase, digit-leading, option-shaped,
  non-ASCII and shell-syntax keys remain refused before claim/dispatch. No new
  CLI option or shell separator is admitted by allowing an interior digit.
- R2: refused, existing mitigation. Each complete argument is quoted using shlex;
  multiline strings, quotes, command substitution and backticks remain literal in
  the stub CLI argv. No raw input is added to shell syntax by this change.
- R3: refused, existing mitigation and prior closure E165. Persisted claim still
  precedes the single dispatch; an ambiguous result remains inflight and is not
  retried by a later push. The unchanged protection was executed, not assumed.

## Coverage

Read the entire workflow, test harness and changed tests, E229 metadata and frozen
diff. Applied exploitability, claim correctness and existing-mitigation lenses.
Every changed runtime path was read; no scoped file skipped. This is not a second
sweep of Pavo generation, private upload, publication or unrelated request flows.

Executed with bytecode disabled and isolated Python:

- Exact vulnerable workflow via REQUESTS_SWEEP_SNAPSHOT: three sweep cases,
  one expected FAIL and two controls PASS.
- Current `test_request_input_digits_sweep.py`: three cases PASS.
- Current `migration/ops/test_requests.py`: all ten cases PASS.
- Original Pavo-index recheck: two previously fixed findings remain FIXED.

Original validators passed: 10 citations resolve to inspected source; four verification rows, one VERIFIED REAL and three refused entries, zero report problems; strict findings index checks all three stored findings against real commits with zero missing snapshots or problems. Recheck ran the listed guard/reproduction commands and appended results: the new E229 finding and both prior Pavo findings are FIXED, zero open/inconclusive. Registry check: 21 zones, 36 dated reports, zero divergent/stale entries. Audit diff whitespace check: PASS.
The real incident and provider non-execution were reported by the integrating
agent; this sweep independently proves the same pre-dispatch refusal through the
actual shell with a stub CLI. No credential, private media or live provider call
was needed. Temporary test Git writes stayed in their own synthetic repositories.

## Hand-off

Retain the E229 canonical regression and sweep reproduction, then use the root-owned
PR/CI process. The pending real request was never dispatched according to the
integrator's incident evidence; its later authorized handling belongs to the root,
not to this read-only review. No new request, provider job, approval or publication
was created by the sweep. Only audit records and its reproduction test were written.
