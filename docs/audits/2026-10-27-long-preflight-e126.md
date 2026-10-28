# Verified security sweep: long-preflight-e126, 2026-10-27

## Context

Scope: the PR on branch `claude/long-preflight` (E126), which gives the Bible-story long the Shorts' no-rework contract.
- Code: `migration/production/bible/long_preflight.py` (new), `episode_build.py` (check_plan, the long's layout,
  windows, risk_rank, `probe-queue`, the long's probe gate in `check-probe`), `episode_preflight.py` (the long's review
  rows and binding), `migration/ops/dispatch_guard.py` (shot-probe: window ids refused, the preflight report as a dep).
- Workflows: the plan step of `.github/workflows/shot-probe.yml` (long_plan_check for a long plan) and the test list
  of `.github/workflows/pr-checks.yml`.

Trigger: the PR touches `.github/workflows/` (CLAUDE.md: a recorded sweep for workflow changes).

## Delegation

The coordinating session ran the sweep itself. Categories: workflow script injection, secret exposure (where the Pavo
secret is reachable), path containment of files written from plan data, and integrity of the approval and preflight
binding (a probe or a build accepted on a report that no longer matches the plan).

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 dispatch input reaches a shell | long-preflight-e126 | FALSE POSITIVE | < 8 | Yes | The new branch reads `$PLAN` from `env:` after the existing path regex and the `episode` check; the plan is passed as `sys.argv[1]` to `python3 -I`, never interpolated. No new `${{ }}` in a `run:` script. | `shot-probe.yml` plan step |
| S2 the Pavo secret before the long's checks | long-preflight-e126 | FALSE POSITIVE | < 8 | Yes | long_plan_check `--strict` and `check-probe` (with LONG_PROBE_PREFLIGHT) run in the plan step; `PAVO_TOKEN` is set only on the later generation step, as before. The long's build path (`generate_step`) creates no Pavo client. | `shot-probe.yml`; `test_long_preflight.test_the_build_ships_approved_clips_only`, `Contract` (a workflow that runs `episode_build.py generate` holds no `PAVO_TOKEN`) |
| S3 a probe on a report that no longer matches the plan | long-preflight-e126 | FALSE POSITIVE | < 8 | Yes | `probe_gate` recomputes the binding and refuses any changed part except the probe rows (`setups`) and the review rows (`review`), which change no request; the build's `verify-preflight` tolerates none and re-reads the review rows now. | `long_preflight.probe_gate`; `test_shot_probe_takes_the_long_plan_and_refuses_windows_and_an_unclean_preflight`, `test_verify_requires_...` |
| S4 a window id used to probe or approve a clip with no request | long-preflight-e126 | FALSE POSITIVE | < 8 | Yes | The dispatch guard and `probe_ids` refuse a `window_of` id (PROBE_WINDOW_SHOT); `review_problems`, `request_digests`, `clip_needs` and `risk_order` leave windows out, so no approval can be recorded for one. | `dispatch_guard.shot_probe`, `episode_build.probe_ids` |
| H1 estimate output path from plan data | long-preflight-e126 | HARDENING, APPLIED | - | Yes | `long_preflight.py estimate --write` names its file after the plan's `episode`; it now refuses an id outside `plan_check.EPISODE_ID` (no `/` or `..`). Local CLI only. | `long_preflight.main` |

0 of 4 claimed findings at 8 or above; 1 hardening applied in the PR.
