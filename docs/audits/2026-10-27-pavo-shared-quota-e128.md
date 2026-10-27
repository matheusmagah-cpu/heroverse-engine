# Verified security sweep: pavo-shared-quota-e128, 2026-10-27

## Context

Scope: the PR on branch `claude/pavo-shared-quota` (E128), one free-model budget for every Pavo generation.
- Code: `migration/integrations/pavo/quota.py` (units, probe-record usage, `git_actions_usage`, `check_batch`),
  `video.py` (the guard on `generate_video` and `job`), `image_gen.py`, `server.py` (the guard reads today's probe
  records from the local refs), `migration/production/bible/episode_build.py` (`seed_budget`, `budget_client`, the
  probe's budget stop), `long_preflight.py` (`planned_units`, the queue's units), `migration/ops/dispatch_guard.py`
  (`pavo_actions_usage`, `pavo_budget`, the `pavo_used` output).
- Workflow: the guard step name and the generation step's env (`PAVO_BUDGET_USED`) of `.github/workflows/shot-probe.yml`.

Trigger: the PR touches `.github/workflows/` (CLAUDE.md: a recorded sweep for workflow changes).

## Delegation

The coordinating session ran the sweep itself. Categories: workflow script injection, secret exposure (where the Pavo
secret and the run token are reachable), untrusted data read from branches (the probe records), subprocess use in the
MCP server, and fail-open paths in the budget (a check that passes what it could not read).

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 a step output reaches a shell | pavo-shared-quota-e128 | FALSE POSITIVE | < 8 | Yes | `steps.guard.outputs.pavo_used` is set only through `env:` (no new `${{ }}` in a `run:` script); it is the guard's own integer, and `seed_budget` accepts only `[0-9]{1,6}` (PAVO_BUDGET_UNKNOWN otherwise). | `shot-probe.yml` generation step; `test_the_run_ledger_is_seeded_from_the_guard_count_and_never_missing` |
| S2 the Pavo secret or token moves | pavo-shared-quota-e128 | FALSE POSITIVE | < 8 | Yes | `PAVO_TOKEN` stays on the generation step only. The dispatch guard reads branches, commits and contents with the run's read-only `GITHUB_TOKEN` (job `contents: read`); nothing is written. The ledgers hold counts, times and conversation ids, no credential or URL. | `dispatch_guard.pavo_actions_usage`; `quota.py` docstring |
| S3 a forged probe record on a `claude/shot-probe-*` branch | pavo-shared-quota-e128 | FALSE POSITIVE | < 8 | Yes | Needs repository write access. A record is parsed as JSON and only counted: an inflated one refuses a batch (fail closed), a deflated one weakens the cap but not the in-run stop (two failed read-backs). An unreadable record refuses (PAVO_BUDGET_UNREADABLE). | `quota.record_usage`, `dispatch_guard.pavo_actions_usage` |
| S4 git subprocess in the MCP server | pavo-shared-quota-e128 | FALSE POSITIVE | < 8 | Yes | Argument lists, no shell; a branch name is used in `git show` only after `PROBE_BRANCH` (`[a-z0-9-]` and digits, never a leading `-`) matched it; a git that cannot answer refuses (PAVO_BUDGET_UNREADABLE), never passes. | `quota.git_actions_usage`; `test_the_local_guard_reads_todays_probe_records_from_the_origin_refs` |
| S5 an unguarded Pavo client on the Actions path | pavo-shared-quota-e128 | FALSE POSITIVE | < 8 | Yes | `generate_clips` builds its client only through `budget_client()`, which refuses without the run-local ledger; `episode_build.py probe` seeds it before `probe_step`. | `test_the_probe_command_seeds_the_budget_before_any_generation`, `test_two_failed_read_backs_stop_the_whole_probe_run` |

0 of 5 claimed findings at 8 or above; no hardening needed beyond the PR.

Review of #475 (same PR, second commit): the REST scan of probe branches now refuses `PAVO_BUDGET_UNREADABLE` when more
pages remain than it reads (it used to stop at 10 pages and pass a partial count), the failed tail ignores records with
no generations and reads the last 3 h across 00:00 UTC, the dispatch check uses the batch's worst case, and the probe
installs a SIGTERM handler that only exits (no new input, no secret moves).
