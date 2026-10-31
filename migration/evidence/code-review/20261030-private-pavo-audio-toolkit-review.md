# Original PR Review Toolkit — private Pavo audio

Date: 2026-10-30. Result: **no remaining Critical or Important toolkit issue** in the reviewed production source and final regression-test delta. All six original specialists completed sequentially. This is a code review; the output remains DRAFT, with no audiovisual, 9.5, source, speech, lip-sync or publication approval granted.

## Scope and provenance

- Repository: `matheusmagah-cpu/heroverse-engine`; local checkout `/workspace/scratch/e9fba7e7fbca/pavo-private`.
- Base: `d4bac72714e7a9618cfe11a983fda00d09bd3f1b`.
- Initial reviewed head: `7bdf009044c5f6e12ab3dc0394ced2aad4fefca6`.
- Retry/recovery head: `2a4b00d990ba3cb738fe22c3c9c7afbc345c29d3`.
- Final production head: `67e415a8e58fae86128e8ef239780467574bdc7b` (12 changed files, 903 additions and 5 deletions versus base).
- Additional reviewed working-tree delta: 23 added lines in `migration/integrations/pavo/test_private_audio.py`, adding multi-history retry coverage and a submission-timestamp assertion. Its final Git blob is `e4ee4236d7d3d8681534d23ab1f9c0d4177811e3`; SHA256 is `dc76d88411fb75e735afa60ca6091b64b6249a7e213937ef5e77384f1a8ef38a`. Production code was unchanged by this test addition.
- Complete changed scope: private-audio workflow, PR checks, implementation plan, OPERATIONS, committed input metadata, `private_audio.py`, shared `quota.py`, private-audio tests, E226–E228, dispatch guard, refusal registry and dispatch tests. Review included necessary existing video/client/upload, encryption, quota and record consumers, with fresh AGENTS.md and CLAUDE.md instructions.
- Actual host/assistant: **Codex**. Coordinator: `/root/toolkit_review`. No Claude runtime or Claude reviewer identity is claimed.
- Original toolkit: `anthropics/claude-plugins-official`, revision `f8c5e7a1dcb71b10cb74586224b5401f3de5db28`, plugin version 1.0.1, Apache-2.0. Installed adapter: `/root/.codex/skills/remote-skills/skill-6ae485f046f08191a956b66af5efff73/SKILL.md`.
- The original review command and all six complete specialist prompts were applied. The coordinator verified all nine hashes in the bundled upstream source manifest. Task/Agent/Bash/Read were mapped to Codex collaboration and authorized local tools. The upstream `opus` model metadata was not represented as a Claude execution; the adapter's inherited Codex model was used. No blocking host-adapter problem occurred.

## Critical and Important issues

**Open: none.** The following issues were resolved during review; source fixes were made by the parent implementer, not the review team.

1. **E228 / Important87 — GET-only recovery blocked after a failed poll.** At the initial head, a new reconciliation dispatch reached the ordinary same-subject rerun guard and failed with `GUARD_RERUN_WITHOUT_FIX` at the same SHA before recovery could run. The code specialist reproduced this offline independently of the security sweep. The narrow validated mode exception in `migration/ops/dispatch_guard.py:776` now permits reconciliation while retaining ordinary generation restrictions; actual claim/recovery checks enforce each mode's stronger conditions. The canonical regression proves recovery succeeds after failed polling while an ordinary new generation remains refused. Code rechecks closed the finding.

2. **E227 — historical readback changed shared quota accounting.** This finding originated in the separate security sweep. Updating an old record branch could move yesterday's generation into today's count and allow an old successful job to replace more recent failure evidence. The fix persists `submitted_at` with CID before streaming (`private_audio.py:175`), preserves it through public records and recovery, and normalizes both REST/git consumers through `quota.combine()` (`quota.py:127`). UNKNOWN jobs consume units without clearing terminal failure evidence; FAILED cooldown uses stable first terminal time. Code and error specialists independently verified this fix; they did not claim discovery credit.

3. **Test coverage gap, 8/10 — all matching claims and latest retry source.** The initial retry test used one matching record. The test specialist demonstrated that in-memory mutations from `all()` to `any()` and from `max()` to `min()` survived it, although production code correctly enforced both conditions. The new `test_retry_requires_all_history_failed_and_the_latest_source` uses three failed records, rejects older source selections and rejects prior UNKNOWN/COMPLETE/SUBMITTING claims. The coordinator ran the new test plus the callback test successfully, then repeated the mutations: `all→any` produced two failures and `max→min` one error. Both mutations are now detected. Source hashes were unchanged by this isolated harness. **Gap closed.**

The explicit `retry_run` mode is an authorized contract extension, not a relaxation for unknown outcomes: all matching claims must be FAILED with CIDs, the requested source must be the latest, the first terminal read must be at least three hours old, and a fresh provider GET must still show failed with no video before the new durable claim. `retry_of` records the relationship. Current lease, shared quota and exact zero quote remain required; each job invokes the generator once. A claim without a CID remains unresolved and non-replayable.

## Executed specialists

Each row identifies a real separate Codex subagent using the corresponding original prompt. Specialists were run sequentially; applicable new deltas received targeted rechecks rather than a repeated whole-project review.

| Specialist identity | Scope and outcome | Executed evidence |
|---|---|---|
| `/root/toolkit_review/code_reviewer` | Full initial 11-file diff and needed consumers; then recovery, retry and E227 deltas. Important87 found and closed; no remaining confidence ≥80 finding. | Initial 9 tests passed; recovery-fix 10 passed; exact retry-head 11 passed from Git objects; final E227 11 isolated assertions passed. Offline failed-poll rerun reproduction; diff whitespace checks passed. |
| `/root/toolkit_review/pr_test_analyzer` | Full initial behavior/tests review, then retry/E227 coverage. Identified the now-closed 8/10 multi-history gap; no current production defect. | Mocked CLI recover→poll preserved source run/CID, reached COMPLETE using one job read, rejected submit and mismatched digest. In-memory mutations exposed the original gap; E227 regression passed. Coordinator subsequently verified the corrected tests kill both mutations. |
| `/root/toolkit_review/silent_failure_hunter` | Full error/retry/persistence paths through retry head, then final E227 error delta. No remaining Critical/Important issue. | 11 tests passed; four mocked CLI poll outcomes persisted COMPLETE/FAILED/BLOCKED/UNKNOWN correctly without generation; terminal timestamp stability passed. Final delta: eight invalid-timestamp cases raised PavoError, and stable accounting/terminal-time assertion passed. |
| `/root/toolkit_review/comment_analyzer` | All 12 changed files and necessary consumers at final production head. Substantive docs match implementation; no Critical/Important issue. | Static cross-check only; no tests or edits. Optional wording improvements below. |
| `/root/toolkit_review/type_design_analyzer` | Manifest/WAV, receipt/public record, retry states, adapter subclasses and shared quota timestamps at final production head. No new production defect. | Static invariant/consumer review only; no tests or edits. Ratings below are type-design assessments, not audiovisual scores. |
| `/root/toolkit_review/code_simplifier` | Final advisory pass after blockers closed: entire new bridge, workflow, quota/dispatch deltas and final 23 test lines. | Static review only. One optional clarity recommendation; no changes applied and no tests repeated. |

Type-design ratings (encapsulation / invariant expression / usefulness / enforcement): manifest and WAV **8/8/9/9**; receipt/public record and retry state **7/8/10/8**; PrivateVideoClient/RecordingGuard **8/8/9/9**; shared quota timestamps **8/8/9/8**. Mutable dictionaries and string states are proportionate to this bounded Python adapter; no new schema framework or class hierarchy was recommended.

## Nonblocking suggestions

- Tests, 7/10: retain the successfully exercised mocked `cli('recover') → cli('poll')` flow as a canonical regression, including source run/CID preservation, wrong digest and forbidden submission. A full timestamp producer/recovery/quota lifecycle test would also strengthen coverage; callback-to-public-record coverage was added, and terminal stability was exercised offline.
- Tests, 6/10: a command-level expired/mismatched lease regression would protect the requirement that execution stops before persistence, attachment or generation.
- Diagnostics: new private-record timestamp failures use `_unreadable()`, whose remediation text points at `image-ledger.json`. Record-specific guidance would identify the actual source correctly; current behavior already fails closed.
- Documentation: `quota.py:118` and its git-reader wording at line 150 still describe commit-time semantics without the private-record exception. The workflow's “hash-only” manifest label at line 11 could say “metadata manifest with input hashes.” Neither changes execution.
- Simplification: replace the nested state-selection ternary at `private_audio.py:186` with explicit `if/elif/else`, preserving every outcome and `terminal_at` behavior. Keep claim, quota/lease, CID persistence and generation order explicit; additional abstraction was not recommended.

These suggestions are not prerequisites for this code review and did not trigger new implementation work.

## Validation and source binding

The coordinator independently ran `python3 -I -B migration/integrations/pavo/test_private_audio.py` after the final test addition: **13 tests passed**. The two focused regression checks and both in-memory mutation checks described above also passed their expected assertions. Production/test file hashes were preserved during these checks. Final `git diff --check` passed.

The coordinator read `/workspace/scratch/e9fba7e7fbca/pavo-private-tests-final/results.json`: **88/88 canonical test modules returned code 0**. Its private-audio log contains 12 passing tests, so that suite precedes the final additional regression; the final 13-test module run above covers the new test. This canonical suite was run by the parent, not independently rerun by every specialist. The parent also reported targeted image-generation 26/26, dispatch 33/33, error-register 13/13, and security reproductions changing from RED to GREEN; these are distinguished from reviewer-executed checks.

Final reviewed production hashes:

| File | SHA256 |
|---|---|
| `migration/integrations/pavo/private_audio.py` | `c4a3564ef4ac562fabb448ea6ce5155087bd6156cf78e098c5d52d415f6632d3` |
| `migration/integrations/pavo/quota.py` | `c44dcab374dd556fc230cb7854f55632ea617ed4ab9685daa3c00f02a51c8f40` |
| `migration/ops/dispatch_guard.py` | `fc22cdf1a5ad88c834a464e7f896dc2fb71c55dc8b2596dacb31b92eb2d55031` |
| `.github/workflows/pavo-private-audio.yml` | `278fde4c8d2fd64712c42433e61edc1228b9fa6fb82994e3b7393e41e9d393b1` |
| Final working-tree `test_private_audio.py` | `dc76d88411fb75e735afa60ca6091b64b6249a7e213937ef5e77384f1a8ef38a` |

## Strengths, limits and next action

Claims precede provider mutations; durable CID and submission time precede streaming. Exact byte/hash/PCM checks bind the WAV. Public records project only selected metadata and force production/publication flags false; private provider data uses encrypted receipts. Unknown submissions cannot be replayed; recovery reads the saved CID; explicit terminal-failure retries retain lease, quota and quote gates. Shared quota consumers preserve historical timing.

Reviewers did not upload or generate media, call Pavo/GitHub externally, spend credits, mutate a lease, edit source code, approve media or publish anything. Tests used synthetic fixtures, mocked external services, in-memory mutations and temporary local Git repositories. The only coordinator repository write was this authorized report. Existing unrelated work was preserved.

This report does not establish live provider behavior, receipt delivery/decryption, real media quality or remote CI status. It is separate from the completed security sweep and does not replace its evidence. Preserve the original audiovisual and publication gates, the current request/claim/receipt chain and shared lease/quota. Carry this report and the final regression delta into the code PR; any later production-source delta requires a targeted review before relying on this conclusion.
