# Verified security sweep: pavo-private-audio, 2026-10-30

## Context

Required original Verified Security Sweep for the new workflow and private Pavo
bridge. One bounded zone: `.github/workflows/pavo-private-audio.yml`,
`migration/integrations/pavo/private_audio.py`, its tests/hash-only input manifest,
and the `migration/ops/dispatch_guard.py` integration. The F2 fix adds the direct
shared accounting consumer `migration/integrations/pavo/quota.py`. The PR's
supporting CI, plan, operations and refusal/error-registry deltas were inspected.
No publishing or approval mechanism was added or relaxed.

Original skill: **Verified Security Sweep 1.4.0**, upstream
`SecPlusDev/verified-security-sweep`, commit
`90a73a192b404ad139bee970f49f73f07410c949`, with original references/scripts and
verified upstream file hashes. Actual reviewers: **Codex**, not Claude.

Base: `d4bac72714e7a9618cfe11a983fda00d09bd3f1b`. Initial review snapshot:
`7bdf009044c5f6e12ab3dc0394ced2aad4fefca6` (11 files, 743 inserted lines).
The user-authorized terminal-failure retry was then frozen at
`2a4b00d990ba3cb738fe22c3c9c7afbc345c29d3`. Final reviewed source:
`67e415a8e58fae86128e8ef239780467574bdc7b`. Both vulnerable commits are real and
remain available locally. Runtime observations were made on those local commits.
For durable remote evidence, the integrating agent later archived the exact trees
in real remote commits. The index now references those archives. The coordinator
verified both vulnerable tree pairs using local Git objects; final source archive
metadata was independently read through GitHub GET and matched its local tree.
No archive is presented as a commit that already existed during reproduction.

| Snapshot | Reviewed local commit | Remote archive | Exact matching tree |
|---|---|---|---|
| F1 vulnerable | `7bdf009044c5f6e12ab3dc0394ced2aad4fefca6` | `cbd9feff31c2274131b00464963ff315bf275d0e` | `f42bfe650956a8361d341dee0545e3c93d3e4ec2` |
| F2 vulnerable | `2a4b00d990ba3cb738fe22c3c9c7afbc345c29d3` | `f8fe84d39e7aa3aea7296275c9d8c9d3a442b85e` | `1453b3e34aed72fecad0154454e72cc849290dd5` |
| Fixed source | `67e415a8e58fae86128e8ef239780467574bdc7b` | `eadddf5f3c77b4ee0436e53f0ea60b649d800c28` | `307f3886415715a63c559b29ef1447544b401768` |

After the fixed-source commit, a test-only delta added multi-record retry history
and submission-time assertions. The coordinator read it and ran all 13 canonical
private-audio tests successfully. Its final working-file hash is included below;
production code remained identical to the fixed-source commit.

Rules (`AGENTS.md`, `CLAUDE.md`, security guidance), categories and registry were
read. All 34 prior dated audits and the undated Pavo preparation report matched
the prior fully read checkout byte-for-byte; the pre-read was retained. There is
no `docs/specs/` or coverage matrix. The new implementation plan and current owner
recovery direction define the contract. Relevant earlier closures:

- `2026-10-25-pavo-mcp.md`: ambiguous submissions do not replay; origin/redirect
  boundaries; exact zero quote, with upstream atomic repricing still unverified.
- `2026-10-27-pavo-shared-quota-e128.md`: shared units, complete history scans,
  failure-tail handling and guards before provider requests.
- `2026-10-29-pavo-draft-attachments.md`: manual prior review of attachment host,
  bounds, byte binding and durable claims; it did not certify this new bridge.
- `2026-10-30-existing-edit-import.md`: fixed renderer hash handoff, DRAFT only;
  its historical-index gap is separate and is not inherited by this run.

Initial original `findings.py recheck`: no open entries. `fresh_code.py` identified
the new importer and high churn in dispatch; its test-name heuristic misses the
migration test roots, so NO was not treated as lack of tests. Initial registry
check: 19 zones, 34 reports, zero divergent/stale entries. Rule-derived probes
covered shell interpolation, secret scope, pinned Actions, public artifact paths,
subprocess argument lists, destinations, persistence, quota and recovery.

Final source SHA256 (all changed PR paths, before this audit's own artifacts):

| File | SHA256 |
|---|---|
| `.github/workflows/pavo-private-audio.yml` | `278fde4c8d2fd64712c42433e61edc1228b9fa6fb82994e3b7393e41e9d393b1` |
| `.github/workflows/pr-checks.yml` | `f25b001f6cb67d376d6ce37059cace0506be17d88fd90361f7fa4dec8e6a26a6` |
| `docs/superpowers/plans/2026-10-30-pavo-private-audio.md` | `d70760169c420a7bf379d43e790f3600ed2d0b95c87c77dd23b0c6749f7794aa` |
| `migration/OPERATIONS.md` | `846d9dc63045406be75012c0b3e8b3df5b4cebbea31f077a195fe1abcdf3d6d6` |
| `migration/integrations/pavo/private-inputs/genesis-09-k-close-20261030.json` | `2f5d7bbc608048f62784c2928c25affc02750907609caa603279ca9895ff148a` |
| `migration/integrations/pavo/private_audio.py` | `c4a3564ef4ac562fabb448ea6ce5155087bd6156cf78e098c5d52d415f6632d3` |
| `migration/integrations/pavo/quota.py` | `c44dcab374dd556fc230cb7854f55632ea617ed4ab9685daa3c00f02a51c8f40` |
| `migration/integrations/pavo/test_private_audio.py` | `dc76d88411fb75e735afa60ca6091b64b6249a7e213937ef5e77384f1a8ef38a` |
| `migration/ops/ERRORS.json` | `5021c6b58cea7f5bf002a1d752ed97eaa025b21bf42952a3bea61236c3c221bc` |
| `migration/ops/dispatch_guard.py` | `fc22cdf1a5ad88c834a464e7f896dc2fb71c55dc8b2596dacb31b92eb2d55031` |
| `migration/ops/refusal_registry.json` | `5feabca463f38e9df021cc7d8ca2b03611c777884b622a393a7625c636ea61bc` |
| `migration/ops/test_dispatch_guard.py` | `93e7c15ef418f0a2d16a28cb6682cd5f701dd9ebf9eb404ba67fce6518b3557d` |

## Delegation

One fresh-context read-only Codex reviewer, `private_audio_reader`, read the
original skill and verification reference, mandatory rules/categories/plan,
all prior audits/registry and the bounded implementation with direct consumers.
The brief explicitly named the prior closures above and required a single sink
line, source-to-sink evidence, calibrated severity, mitigation checks, refused
candidates and coverage. No production edit, external call, provider generation
or project Git mutation was authorized to that reviewer.

The coordinator independently found/reproduced F1 and verified the reader's F2
candidate with real project accounting functions and fixed UTC fixtures. The
reader independently verified F1, the authorized retry delta and final F2 fix.
Its final review of commit 67e415a8e58fae86128e8ef239780467574bdc7b found no
new defect; seven focused tests and six additional adversarial cases passed.
Production fixes and commits belong to the implementing root agent. The sweep
kept reproduction, verification, index and report work with its coordinator.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| F1 generic failure guard blocks GET-only recovery | pavo-private-audio | VERIFIED REAL | Medium | Medium, fixed | Legitimate read-only recovery was blocked; no extra submission occurred. | Original reproduction ran, 1 expected ERROR and 2 controls PASS; final recovery/ordinary-generation/other-workflow checks PASS. Historical index location `migration/ops/dispatch_guard.py:773`; current fix `migration/ops/dispatch_guard.py:776`. |
| F2 GET recovery moves quota dates and clears a newer failure tail | pavo-private-audio | VERIFIED REAL | Medium candidate | Medium, fixed | Free quota accounting/stop control, not observed paid spending. | Original UTC reproduction ran: old job counted 2 instead of 0 today; newer failed_tail became 0 instead of 2; current-day control PASS. Index sink `migration/ops/dispatch_guard.py:689`; shared fix `migration/integrations/pavo/quota.py:128`. Final REST and git/MCP regressions PASS. |
| R1 unknown acknowledgement automatically duplicates a generation | pavo-private-audio | FALSE POSITIVE | Medium candidate | - | Explicit failed-job retry is a different, newly authorized action. UNKNOWN remains non-replayable. | Durable claim and callback inspected; `migration/integrations/pavo/private_audio.py:177`; canonical lost-persistence/unknown tests ran, PASS. |
| R2 private audio, URLs or credentials enter a public branch/artifact | pavo-private-audio | FALSE POSITIVE | High candidate | - | Authorized operator certificate owns decryption; provider storage itself is outside local access-control certification. | Explicit public projection `migration/integrations/pavo/private_audio.py:128`; isolated index at `migration/integrations/pavo/private_audio.py:270`; synthetic Git persistence and real CMS roundtrip ran, PASS. Workflow uploads only receipt.cms. |
| R3 signed upload address, redirect or headers leak credentials to another origin | pavo-private-audio | FALSE POSITIVE | High candidate | - | Existing fixed storage hosts remain trusted; this does not certify provider internals. | `migration/integrations/pavo/private_audio.py:89`, `migration/integrations/pavo/private_audio.py:94`, `migration/integrations/pavo/attachments.py:37`, `migration/integrations/pavo/client.py:32`; storage/header/client boundary tests ran, PASS. |
| R4 changed or truncated WAV reaches generation as the bound input | pavo-private-audio | FALSE POSITIVE | Medium candidate | - | No untrusted concurrent writer was identified in the isolated runner between local recheck and adapter load. Exact PCM is not a speech/voice-quality verdict. | Byte hash/size and PCM checks `migration/integrations/pavo/private_audio.py:76`, `migration/integrations/pavo/private_audio.py:79`, and pre-submit check `migration/integrations/pavo/private_audio.py:351`; canonical altered/truncated/format tests ran, PASS. |
| R5 recovery changes the bound manifest/CID or mutates the provider | pavo-private-audio | FALSE POSITIVE | Medium candidate | - | Public history requires trusted repository writer; an authorized writer already controls workflow code. | Digest/CID guard `migration/integrations/pavo/private_audio.py:317`; recovery mode `migration/integrations/pavo/private_audio.py:299`; independent fresh reviewer recover-to-poll probe used only same-CID history and refused mutation commands, ran, PASS. |
| R6 completed DRAFT becomes production/publication approval | pavo-private-audio | FALSE POSITIVE | High candidate | - | Successful provider completion is not acceptance of source, voice, content, quality or rights. | False flags `migration/integrations/pavo/private_audio.py:133`; reviewed route has no approval or publication consumer. DRAFT and public-projection tests ran, PASS. |
| R7 exact zero quote guarantees an atomic provider no-charge contract | pavo-private-audio | NEEDS DEEPER REVIEW | Prior unresolved candidate | - | Recorded as an unproven upstream guarantee in the original Pavo audit; no new bypass or paid charge observed. | `migration/integrations/pavo/private_audio.py:103` and existing fresh quote before generation; quote-refusal tests ran, PASS. Provider atomic repricing semantics remain unverified, as recorded in `2026-10-25-pavo-mcp.md`. |

## Confirmed defects

**Two Medium defects confirmed and fixed; zero open confirmed defects on the final
reviewed commit.** No High/Critical or separate Low finding was established.

### F1 / E228: GET-only recovery must remain available after a failed poll

At initial commit `7bdf009044c5f6e12ab3dc0394ced2aad4fefca6`, the unconditional
history walk begins at `migration/ops/dispatch_guard.py:773`; the index records
its exact original snippet. The workflow always invokes that guard before
recovery. After a legitimate poll timed out as UNKNOWN and the workflow failed,
a new dispatch with `reconcile_run` was treated as another failed generation
attempt. Without an unrelated code/retry-ledger change, the same-subject check
raised GUARD_RERUN_WITHOUT_FIX before the history GET could run.

The local reproduction uses the real `private_audio` input checker and `rerun`
function with a synthetic failed Actions run. Initially the recovery case errored;
ordinary generation after failure was correctly refused and recovery after success
passed. The original failure is preserved in the commit-bound index, not inferred
from the corrected source.

The root agent introduced a workflow-specific, revalidated mode exception. The
final rule also recognizes the separately authorized explicit `retry_run`, whose
stronger terminal-failure constraints execute before any provider mutation. Direct
malformed recovery, ordinary generation after failure and a sibling workflow all
remain refused. Current guard: `migration/ops/dispatch_guard.py:776`.

Reproduction and guards: `docs/audits/reproductions/test_pavo_private_audio_sweep.py`
class `RecoveryGuard` (five final tests PASS). The canonical regression is in
`migration/integrations/pavo/test_private_audio.py`. No workflow-wide rerun bypass
was introduced.

### F2 / E227: recovery commit time is not provider submission time

At commit `2a4b00d990ba3cb738fe22c3c9c7afbc345c29d3`, private polling republished
its historical probe branch. The accounting consumer then appended that record
with the branch's new committer time at `migration/ops/dispatch_guard.py:689`.
The shared combiner treated the recovered old conversation as a current-day job
and as a newer quota observation. This data flow was independent of public media
or an attacker: an authorized operator's ordinary recovery caused it.

The fixed-UTC reproduction executed the real REST accounting consumer. Two cases
failed: a recovered prior-day job consumed two Short units today, and reading an
old success after a newer two-failure record reset failed_tail from two to zero.
A genuinely current-day submission still counted two units. Thus the defect could
both block legitimate daily capacity and release the shared failure stop early.
No paid charge or live provider generation was attempted.

The root fix writes `submitted_at` before streaming, preserves it through public
projection and recovery, and normalizes private records in the shared combiner.
Both REST and git/MCP readers call that combiner. Unknown private outcomes cannot
clear an earlier terminal failure; failed-job stop time uses the first preserved
`terminal_at`. A private generation missing its stable timestamp refuses instead
of silently choosing a new day. Current implementation:
`migration/integrations/pavo/private_audio.py:176`,
`migration/integrations/pavo/private_audio.py:322`, and
`migration/integrations/pavo/quota.py:128`.

`HistoricalQuota` retains the two original failing cases, a legitimate current-day
control and an additional git/MCP consumer regression; all four final tests PASS.
The canonical E227 regression also covers UNKNOWN and missing timestamps.

Historical `file:line` citations above explicitly refer to the indexed commit;
F1's original line moved after the retry integration. The original index validator
opens that exact commit and verifies the snippet. Current fix citations were
separately reopened. Both indexed commands are ordinary test-runner invocations.

## Refused or unconfirmed candidates

- R1: refused, existing mitigation. Intent is durable before effects; CID and
  submission time persist before stream. Failed persistence prevents streaming.
  An unresolved record blocks a new claim. Explicit retry requires every prior
  same-hash claim FAILED with CID, the latest source, at least three hours since
  first terminal failure and a fresh same-CID failed/empty-video GET.
- R2: refused, existing mitigation. Public projection omits input media, prompt,
  provider result, URLs and secret material; an independent Git index excludes
  unrelated staged files. Real synthetic CMS encryption/decryption was verified.
- R3: refused, existing mitigation. HTTPS host/port/userinfo/query rules, exact
  header names and no redirects constrain upload/readback. Storage GET/PUT does
  not receive the Pavo bearer credential. Inputs reach scripts through env JSON.
- R4: refused, exploitability for the deployed surface. Readback and pre-submit
  hash/size/PCM checks reject changed bytes. No hostile local writer was shown;
  no claim of perceptual speech accuracy or cryptographic provider honesty is made.
- R5: refused, existing mitigation. Recovery validates the saved manifest identity
  and CID and only permits recover/poll. Its provider route is GET history; its
  public bookkeeping writes do not create a provider job.
- R6: refused, claim correctness. Provider completion and hash matches never
  issue production approval, source qualification or publication permission.
- R7: needs deeper review, unchanged prior provider-contract limitation. A local
  exact-zero quote is enforced twice; an atomic upstream price lock was not
  established. This is not counted as a newly confirmed defect or re-reported fix.

## Coverage

All core scoped code, workflow wiring, test/manifest and direct quota-fix callers
were read. Supporting reads traced client/video/audio/images/attachments,
private receipt CMS and executor-lease validation. Current lease identity,
active state and expiry were exercised with synthetic records. Explicit retry
was checked independently for all-failed history, latest-source identity,
three-hour boundary, immutable first terminal timestamp, fresh failed GET,
mode exclusivity, one claim and unchanged two-unit quota reservation.

Final/local execution (PYTHONDONTWRITEBYTECODE=1 and isolated Python):

- Sweep reproduction file: 10 tests PASS, including original F1/F2 regressions,
  legitimate controls, sibling workflow, malformed mode, lease and git/MCP usage.
- `test_private_audio.py`: 13 tests PASS, including synthetic isolated-Git
  persistence. It creates only temporary local repositories, no external mutation.
- `test_dispatch_guard.py`: 33 tests PASS after the final shared-quota fix.
- `test_image_gen.py`: 26 tests PASS on the changed shared quota consumer.
- Existing unchanged adapter boundaries: `test_video.py` 32 PASS,
  `test_attachments.py` 12 PASS, `test_client.py` 12 PASS.
- Native-review CMS single-line certificate roundtrip: 1 PASS using generated
  synthetic certificate/key and receipt, no real credential or private media.

Original validators: 24 citations resolve; nine verification rows with two VERIFIED REAL and seven refused/unconfirmed entries, zero report problems. `findings.py check --strict` verifies both real vulnerable snapshots and exact snippets, zero missing snapshots or problems. After the commands were listed and inspected, `findings.py recheck --run --write` executed legitimate guards and reproductions: zero open, two fixed, zero inconclusive; its append-only log retains the final local commit and worktree status. `sweep_status.py --check`: 20 zones, 35 dated reports, zero divergent/stale entries. Audit `git diff --check`: PASS. Both vulnerable remote snapshots are present locally and pass strict validation; the mappings above preserve the original local runtime evidence. The append-only recheck log intentionally keeps the local commit actually executed.
No scoped implementation file was skipped. Provider internals, authenticated live
transport, actual private audio, audiovisual quality, publishing and unrelated
production engines were outside the zone. Full canonical suites and remote CI are
the integrating agent's checks, not inferred from these focused results.

## Hand-off

Retain the F1/E228 and F2/E227 canonical guards, the commit-bound finding index and
sweep reproductions. The final reviewed code has no open confirmed defect; the
upstream atomic pricing limitation remains explicit. One provider request per
durable claim is the contract; a new same-hash probe requires the explicit,
verified terminal-failure retry path, never an UNKNOWN resubmission.

This is the original recorded sweep method for this bounded workflow/bridge,
not whole-repository, provider-security, rights or audiovisual certification.
The sweep changed only audit records and its reproduction test. Production fixes,
commits, PR, remote CI and any later authorized provider use remain root-owned.
