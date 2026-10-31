# Verified security sweep: pavo-private-hook, 2026-10-30

## Context

Required bounded pre-merge review of the silent Genesis 09 s-voice hook extension:
`.github/workflows/pavo-private-audio.yml`,
`migration/integrations/pavo/private_audio.py`,
`migration/ops/dispatch_guard.py`, the canonical bridge tests, and the three
committed manifest/handoff files listed below. The authorized behavior is one
10-second frames-to-video DRAFT using the exact already-approved first frame,
without supplied audio. Existing lease, quota, claim, encrypted receipt and
same-conversation recovery controls remain the baseline. This review does not
approve audiovisual quality, source voice, final timing, publication or a provider
charge guarantee.

Actual coordinator and fresh reader: **Codex**. Original **Verified Security Sweep
1.4.0**, upstream `SecPlusDev/verified-security-sweep` at
`90a73a192b404ad139bee970f49f73f07410c949`; original skill, references and scripts
were used, with their preserved license and provenance. No substitute workflow
or Claude execution is claimed.

Branch: `claude/short09-hook-inputs-20261030`. Base:
`b483923f213009a6a6d02b72845d234f91c836f5`. The complete original review and
adversarial probes used the frozen implementation commit
`11a90bebd2a1e0cf310d2d251a9fa9feb192948b` (seven files, 396 insertions and 16
deletions). Final source snapshot:
`c2e399f88abe9839bff20a9c7092f1d3e0b31b75`. Its sole delta adds 24 lines to
`test_private_audio.py`: a CLI claim regression and its legitimate empty-history
control, prompted by the separate Toolkit test review. The coordinator inspected
that diff and reran all 18 focused tests. All production bytes remain identical
to the original frozen implementation. These are actual local commits, not a
claim of remote commit identity or of a merged result.

Mandatory pre-read: project AGENTS/CLAUDE/security rules, categories, every
previous audit and registry, and zone handoff/operational documents. The 42
previously read rules/audit files were byte-compared against the preceding
completed checkout and were unchanged. No `docs/specs/` or coverage matrix exists.
Relevant closures include the original Pavo provider-contract limitation in
`2026-10-25-pavo-mcp.md`; quota controls in
`2026-10-27-pavo-shared-quota-e128.md`; recovery, privacy, replay and stable quota
time in `2026-10-30-pavo-private-audio.md`; and the dispatcher key correction in
`2026-10-30-request-input-digits.md`. None is re-reported as a new defect.

Original fresh-code and registry scripts ran. Private bridge and dispatcher
changes were reviewed first; the script's migration-test discovery heuristic
was not treated as proof that tests were absent. Rule-derived probes traced
manifest/hash/approval binding, source-to-adapter mode selection, exact quote
ordering, durable claim/CID ordering, shared quota and lease checks, public
projection, CMS artifact paths, storage authority and GET-only recovery.
Initial registry: 21 zones, 36 dated reports, no divergent or stale entries.

| Final changed file | SHA256 |
|---|---|
| `.github/workflows/pavo-private-audio.yml` | `d23f60c5d5efc14a0cc2e46c42c0cafe7c293ae98095b8e11b1ffafcb556ab96` |
| [migration/evidence/handoff/2026-10-30-short09-hook-inputs.md](https://github.com/matheusmagah-cpu/heroverse-engine/blob/62362bc10c6a414af65fed72b8fdfe8aaafa99fc/migration/evidence/handoff/2026-10-30-short09-hook-inputs.md) | `f80a21efcaa39626dd034308e20d3f4ad5d1b47a2d9dd653012aa88a65d405fb` |
| `migration/evidence/pavo/prepared/genesis-09-s-voice-20261030.json` | `3d6c6920a37989cda580c59c3c7d88a6281b1d1747567c5a874f7c7fcfe0a00a` |
| `migration/integrations/pavo/private-inputs/genesis-09-s-voice-20261030.json` | `de9fa240faab052bcf4968de12bbe0929219989b96095ccabe91252be07ffc4c` |
| `migration/integrations/pavo/private_audio.py` | `ab4c3fca08d9190dfa85baa1a8c8fb2b5464e5c759449c5ee39b755a51968f47` |
| `migration/integrations/pavo/test_private_audio.py` | `2bf5bbca4db5c278247d3699bbe4d139579d8b679f394dee81c813ea95a5b296` |
| `migration/ops/dispatch_guard.py` | `3dfe7de0b9d20ad9242a83acf664e29abf75dc6bea587c0b974f20f1d91da4f9` |

## Delegation

One fresh-context read-only reviewer, `hook_security_reader`, was delegated the
single bounded zone. The original brief required rules/categories/specs and all
previous reports before code; exact sink locations; source, sink and missing
mitigation evidence; calibrated severity; at most ten candidates; explicit
refusals and coverage. The reviewer waited for the implementation freeze, then
read all seven changed files and their direct consumers independently of the
implementer. No network, provider call, model execution, production edit or
project Git mutation was authorized or performed by the sweep.

The coordinator opened the actual cited lines, applied exploitability, claim
correctness and existing-mitigation lenses, and owned verification and reporting.
The reader's initial summary listed clean control checks as candidates; that
classification was corrected before this report. Coverage checks below do not
inflate the candidate denominator. The reader supplied three adversarial guards;
the coordinator inspected their full harness, retained it under `docs/audits/`,
and independently executed it with network/subprocess tripwires. No failing
defect reproduction is claimed when no defect was found.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| R1 first-frame replacement after validation reaches generation | pavo-private-hook | FALSE POSITIVE | Uncalibrated lead | - | No untrusted concurrent writer was identified in this runner; the local-writer assumption remains explicit. | `migration/integrations/pavo/private_audio.py:70`, `migration/integrations/pavo/private_audio.py:237`, `migration/integrations/pavo/private_audio.py:398`; exact frame bytes/record checked, canonical altered-binding guards ran, PASS. |
| R2 non-private probe history permits duplicate hook claims | pavo-private-hook | FALSE POSITIVE | Uncalibrated lead | - | The new claim contract applies to this private bridge; no conflicting prior hook submission or bypass through this route was demonstrated. | `migration/integrations/pavo/private_audio.py:274`, `migration/integrations/pavo/private_audio.py:159`, `migration/integrations/pavo/private_audio.py:326`; all-state/different-digest guards and final CLI history/empty-history controls ran, PASS. |
| R3 revoking the local frame prevents same-CID recovery | pavo-private-hook | FALSE POSITIVE | Uncalibrated lead | - | Recovery still requires the current bound input to be valid. A future owner revocation/removal would require separate operational handling; it is not an observed failure on this approved snapshot. | `migration/integrations/pavo/private_audio.py:237`, `migration/integrations/pavo/private_audio.py:341`; actual-input recover-to-poll guard ran, PASS, same ID and timestamps, mutation commands refused. |
| R4 hook approval metadata bypasses the generic approval reader | pavo-private-hook | FALSE POSITIVE | Uncalibrated lead | - | This narrow route accepts one fixed already-approved image, not arbitrary new approval records. No invalid current approval or untrusted writer of main was demonstrated. | `migration/integrations/pavo/private_audio.py:73`; actual frame hash/APPROVED/9.5 record checked, canonical DRAFT/low-score/wrong-hash guards ran, PASS. |
| R5 two zero quotes guarantee atomic provider pricing | pavo-private-hook | NEEDS DEEPER REVIEW | Previously recorded upstream limitation | - | No local bypass, observed charge or new provider-contract evidence; no live provider request was made. | `migration/integrations/pavo/video.py:318`; second-quote refusal guard ran, PASS before upload/create/stream. Atomic pricing remains unverified as in `2026-10-25-pavo-mcp.md`. |

## Confirmed defects

**Zero confirmed defects**, including zero Low findings, for this frozen bounded
delta. No new `findings.jsonl` entry is appropriate. Four leads were refused and
the existing upstream pricing limitation remains unresolved; clean coverage
checks are not counted as findings.

The three historical indexed findings were listed first and their exact
commands inspected as ordinary local Python test-runner invocations on project
tests. Original `findings.py recheck --run --write` then ran their legitimate
guards and reproductions: **zero open, three fixed, zero inconclusive**.
The append-only log records the actual execution at `11a90beb...`; the subsequent
test-only commit did not change their implementation. The strict index validator
also verifies all three real historical commit/snippet bindings locally; there
is no missing-snapshot gap for these entries.

## Refused or unconfirmed candidates

- R1: refused, exploitability. The hook path and SHA are constants, the bytes are
  checked on each CLI input load, and the adapter loads its image before the
  quote/upload sequence. No untrusted concurrent writer was identified. A
  trusted repository writer can already change executable workflow code. This
  does not assert atomic filesystem binding against an attacker inside the
  runner; the analogous local-writer limitation was recorded in the prior
  private-audio sweep.
- R2: refused, claim correctness and existing mitigation. The history reader
  filters for private bridge records, and every private hook claim is included.
  The slot guard blocks all prior states and changed prompt digests, and the CLI
  forwards the manifest. Other generation engines are not silently certified by
  this route. Their existence alone does not demonstrate a bypass of the scoped
  one-claim contract. The final regression now detects losing that CLI argument.
- R3: refused as a current defect, claim correctness. Every command, including
  recovery, intentionally enters through current manifest/frame validation.
  The exact current frame remains approved and present; actual-input recovery
  succeeds. No revocation recovery contract or observed legitimate failure was
  supplied. Retain the operational limitation rather than weakening validation
  speculatively or re-opening the separately fixed dispatch recovery finding.
- R4: refused, existing mitigation and claim correctness. The route fixes the
  path/hash, requires matching APPROVED metadata and a finite numeric score at
  least 9.5, and keeps every generated result a DRAFT. It cannot select arbitrary
  approval records. The existing still score is not inherited by generated video.
- R5: needs deeper review, unchanged provider-contract limitation. Both local
  quote checks are enforced, including a fresh refusal immediately before upload.
  No atomic upstream price-lock contract is established by this sweep. This was
  already recorded in the original Pavo audit and is not a newly confirmed defect.

## Coverage

Read all seven changed files, the actual frame and approval metadata, and the
direct `video.py`, `images.py`, quota, storage/client, dispatcher and CMS consumers
needed to trace the changed route. Source line citations refer to the unchanged
production bytes at both frozen commits. The approved first-frame bytes hash to
`8c3ef26c79c19d7b7d0acb2b825809fab104790d49dfa452e597cbf5b6711e19`.

Checked with no defect found:

- Strict hook fields refuse audio, alternate frames/references, extra nonce,
  sound, duration and slot changes. Existing WAV generation still passes its
  fixed reference and verified audio; an extra audio-manifest dependency field
  does not replace that generation input.
- Preparation and generation request frames-to-video, one image, zero audio and
  sound false. A second nonzero quote refuses before upload, creation or stream.
  The quote is a local guard, subject to R5's provider limitation.
- The same shared short budget runs before submission; lease validation and
  workflow concurrency remain in place. CID and stable submitted_at persist
  before stream. A persistence failure cannot proceed into the stream.
- Recovery validates the saved digest/CID, keeps creation/submission times,
  uses the same history request and refuses claim/prepare/ready/submit. The
  existing quota normalizer and GET-only dispatch exception remain intact.
- Explicit public projection excludes prompt, private media and provider URLs;
  independent Git index persistence and CMS-only artifact paths remain intact.
  The fixed storage hosts/header rules and redirect refusal are unchanged.
  All approval/publication flags remain false.
- Handoff and metadata describe preparation and later review, not a generated
  result. Prompt instructions for the requested camera/cut timing are not proof
  the provider will obey them. No approval/publish gate was weakened.

Coordinator execution:

| Check | Result |
|---|---|
| Canonical `test_private_audio.py`, initial frozen implementation | 17/17 PASS |
| Canonical `test_private_audio.py`, final test-only commit | 18/18 PASS |
| `docs/audits/reproductions/test_pavo_private_hook_sweep.py` | 3/3 PASS |
| Original historical finding guards/reproductions | 3 FIXED, 0 open, 0 inconclusive |
| Seven frozen source files and final test-only diff | Exact bytes verified |

The retained adversarial file has SHA256
`3985f3335695bc964e31572d4089cef09c8f804916b278119c6433b8e7bd1913`.
It is a guard harness, not evidence that a defect once existed. Tests use synthetic
provider responses and temporary receipts/quota files; unexpected sockets, HTTP
or subprocess calls fail immediately. The canonical suite's Git-persistence case
uses isolated temporary repositories only.

The integrating agent separately completed all 88 canonical files on final
commit `c2e399f8...`, with 88 PASS and no failures, and a mutation check proving
the new CLI regression fails if `manifest=m` is removed in memory. The coordinator
inspected the final full-run summary, added test and mutation evidence and reran
the actual final focused suite; this report does not relabel the separately
executed full run as coordinator execution.

Skipped: provider internals and live quotes/uploads/generation, other engines,
unrelated audio/video processing, audiovisual quality, real MediaPipe/SyncNet,
publication and final composition. No such execution or certification is implied.
Original validators passed: 10 exact citations; five verification rows, zero
VERIFIED REAL, five refused/unconfirmed entries and no report problems;
`findings.py check --strict` verified all three historical entries with zero
problems or unavailable commits. `sweep_status.py --check` reports 22 zones,
37 dated reports, zero divergent and zero stale entries. Audit diff whitespace
check passed. No pre-existing unrelated temporary artifact was altered.

## Hand-off

**OK for the reviewed bounded code delta: zero confirmed defects.** Retain the
strict input/claim/quote guards and final CLI regression through normal PR/CI
review. This sweep does not dispatch a job, spend quota, publish content or alter
production code. Any generation remains a separate authorized workflow action
under the current lease, shared quota, exact quotes and durable claim.

Preserve R1's local-writer assumption, R3's current-input recovery prerequisite
and R5's unresolved upstream pricing semantics. Generated output still needs its
own actual review; the approved first-frame score does not approve a video.

Sweep writes are limited to this report, the offline adversarial guard, the
append-only historical recheck log and the registry row. No new index finding,
production edit or project commit was made by the sweep.
