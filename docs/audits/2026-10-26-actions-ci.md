# Verified security sweep: actions-ci, 2026-10-26

## Context

Scope: the CI changes of PR #417.
- Workflows: `.github/workflows/pr-checks.yml`, `render-smoke.yml`, `pilot-preview.yml`, `pilot-render-stills.yml`,
  `pavo-footage.yml`, `voice-sample.yml`, `goal-report.yml`.
- Scripts: `migration/ci/render_pilot.sh`, `migration/ci/fetch_assets.sh`, `migration/ci/apt_install.sh`,
  `migration/ops/minutes.py`.

Trigger: the PR touches `.github/workflows/` (CLAUDE.md: a recorded sweep for workflow changes).

Branch: `claude/actions-minutes-budget`. The sweep reviewed the PR at `dec0b5c`. The review fixes below are in
`b6fdcce6` (tree `d83edbd1`).

The engine repository is public. Standard runners are free for it, so no spend ceiling applies to Actions
minutes (E102).

## Delegation

The coordinating session ran the security sweep: categories workflow injection, secrets, cache poisoning, supply
chain (action pins) and concurrency. A separate code review covered correctness and the robustness of the new
scripts.

The primary reviewer reopened each cited control and reproduced every review finding with a failing test before
fixing it (`migration/ci/test_ci_setup.py`: 12 of 15 tests failed before the fix commit, all pass after it).

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 PR runs could poison the pip cache that renders on main restore | actions-ci | FALSE POSITIVE | < 8 | - | GitHub scopes caches by ref: a `pull_request` run cannot write main's scope, and the smoke uses `actions/cache/restore` only | `render-smoke.yml:38`; saves only in `pilot-preview.yml:34`, `pilot-render-stills.yml:29`, `pavo-footage.yml:57`, which run on dispatch |
| S2 untrusted `${{ }}` in a `run:` script | actions-ci | FALSE POSITIVE | < 8 | - | No `pull_request_target`; the new `${{ }}` are `github.event.pull_request.number` in a concurrency group and step outputs in cache keys | `pr-checks.yml:10`; the pins steps hash repository files only |
| S3 an asset reaches the render unverified | actions-ci | FALSE POSITIVE | < 8 | - | The hash format is checked before download and the content after it; any miss fails the call | `fetch_assets.sh` `one()`; `test_every_hash_checked_and_any_miss_fails` |
| S4 actions/cache pinned to an unverified SHA | actions-ci | FALSE POSITIVE | < 8 | Checked | `5a3ec84eff668545956fd18022155c47e93e2684` is the lightweight tag `refs/tags/v4.2.3` (`git ls-remote https://github.com/actions/cache`, 2026-10-26) | `test_keys_on_the_pin_lines_only_without_a_fallback` asserts the pin |
| S5 cancel-in-progress cancels another PR's check | actions-ci | FALSE POSITIVE | < 8 | - | The group is the PR number; only a superseded commit of the same PR is cancelled | `pr-checks.yml:10`; `test_every_pr_runs_every_check_and_only_the_superseded_run_is_cancelled` |
| R1 background apt without E55 hardening; unbounded `wait` | actions-ci | CONFIRMED, FIXED | review | Yes | A stalled mirror could hang the render until the job timeout | `migration/ci/apt_install.sh` (official origins, request and command timeouts), used by pr-checks, voice-sample and render_pilot; pip, venv and curl bounded; `AptInstall.*`, `test_every_setup_command_is_bounded`, `test_apt_installs_cannot_hang` |
| R2 duplicate destination: two xargs workers write and check one file | actions-ci | CONFIRMED, FIXED | review | Yes | A torn file could pass, or a good one fail | identical lines fetched once; two hashes for one destination refused (`FETCH_DUPLICATE_DEST`); `test_identical_lines_are_fetched_once`, `test_one_destination_with_two_hashes_is_refused` |
| R3 hand-kept list of tests run before apt could silently skip | actions-ci | CONFIRMED, FIXED | review | Yes | A module that probes ffmpeg or cv2 could skip a check | the list is dropped: every test runs after the install; `test_tests_start_after_the_video_tools` |
| R4 disk check on `$T`, deletion frees `/` | actions-ci | CONFIRMED, FIXED | review | Yes | `/` short of space would go unnoticed | both are measured, and either one short frees the disk; `test_sdks_are_deleted_when_root_or_temp_is_short` |
| R5 9-min step timeout inside a 10-min job | actions-ci | CONFIRMED, FIXED | review | Yes | - | job 15 min, steps 6 + 8; `test_job_timeout_covers_its_steps` |
| R6 polling throttle with a `kill -0` PID loop | actions-ci | CONFIRMED, FIXED | review | Yes | - | `wait -n` with `jobs -rp`; `test_parallel_runner_reports_every_result_and_fails_on_any_failure` |
| R7 `restore-keys` fallback grows stale caches | actions-ci | CONFIRMED, FIXED | review | Yes | - | key = hash of the pin lines only, no fallback; `test_keys_on_the_pin_lines_only_without_a_fallback` |

## Confirmed defects

No security finding at confidence 8 or above; the findings index gets no entry. The seven review findings (R1-R7)
were robustness defects in unmerged code. Each is fixed on the branch with a test that failed first; they are
recorded under E102.

## Pre-existing, outside this PR's change

- P1 The depth model is downloaded and its sha256 only printed, never compared (`migration/ci/render_pilot.sh:61`).
- P2 pip pins name versions without `--hash` (render_pilot venvs, pavo-footage, voice-sample, episode).
- P3 `render-smoke.yml` cancels by `github.ref` (`render-smoke.yml:19`). For a PR this is the PR's merge ref, so
  only a superseded run of the same PR is cancelled. A dispatch on the same ref would share the group.

These were present before PR #417. They are recorded here, not fixed: each needs its own PR.

## Coverage

All scoped files were read in full. Lenses applied: exploitability, claim correctness, existing mitigation.
Categories: workflow injection, secrets, cache scope and poisoning, action pins, concurrency, downloads (hash
checks), failure turned into a pass (skips, unbounded waits).

No secret was read or printed. No workflow was dispatched by the sweep. CI on the PR runs pr-checks and the
render smoke.

## Hand-off

The PR may merge after CI passes and the owner's review. P1-P3 are candidates for a later PR. P1 is the most
direct: compare the depth model's hash against a pinned value, as the other models are.

This sweep changed only audit records. The fixes for R1-R7 are in the PR's own commit.
