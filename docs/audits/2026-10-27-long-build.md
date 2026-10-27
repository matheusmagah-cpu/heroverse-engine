# Verified security sweep: long-build, 2026-10-27

## Context

Scope: the PR on branch `claude/long-build` (LONG_DESIGN slice 3), which builds the Bible-story long from approved
clips.
- Code: `migration/production/bible/long_build.py` (new), `episode_build.py` (`voice_layout`, the long's compose in
  `compose_prediction`), `episode_preflight.py` (the long's compose predicted), `scene_stills.py` (16:9 stills),
  `migration/ops/dispatch_guard.py` (`long-build.yml` registered).
- Workflows: `.github/workflows/long-build.yml` (new: prepare, upscale matrix, assemble, record) and the test list of
  `.github/workflows/pr-checks.yml`.

Trigger: the PR touches `.github/workflows/` (CLAUDE.md: a recorded sweep for workflow changes).

## Delegation

The session ran the sweep itself. Categories: workflow script injection, secret exposure, untrusted artifacts reaching
a release, path containment of files written from plan or matrix data, write permissions.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 dispatch input or matrix value reaches a shell | long-build | FALSE POSITIVE | < 8 | Yes | `plan`, `resume_run` and `matrix.shot` reach the steps through `env:` only; `$PLAN` is checked by the path regex in the prepare job, `$SHOT` and `$EP` by id regexes, `$RESUME_RUN` by a digits regex; no `${{ }}` inside a `run:` script. The upload-artifact `name:` uses a step output built from ids the plan and the approved sha256 give. | `long-build.yml` |
| S2 a Pavo or other secret in the build | long-build | FALSE POSITIVE | < 8 | Yes | No job reads `secrets.`; the build never creates a Pavo client (`generate_step` fetches approved clips only). | `test_long_build.test_long_build_yml_ships_approved_clips_only_and_resumes`, `test_long_preflight.Contract` |
| S3 untrusted pictures reach the release through `resume_run` | long-build | HARDENING, APPLIED (H2) | 6 | Yes | Before: any run id of the repository could lend its `long-up-*` artifacts, and a pull request run (fork code, read-only token) can upload artifacts of any name with a record claiming the approved sha256. The record's `source_sha256` check alone cannot tell. Now both the prepare and assemble jobs refuse a resume run that is not a `long-build.yml` `workflow_dispatch` of `main` (RESUME_RUN_NOT_A_LONG_BUILD). Claude's frame review of the sheet still sees every picture. | `long-build.yml` ids step and resume step |
| S4 upscale and assemble jobs read any plan path | long-build | HARDENING, APPLIED (H1) | < 8 | Yes | The guard's `attempt` mode does not re-check inputs, so the matrix and assembly jobs now apply the prepare job's long-plan path regex too. `checked_plan` also refuses a non-long plan and runs `verify-preflight`. | `long-build.yml` |
| S5 files written outside their folder | long-build | FALSE POSITIVE | < 8 | Yes | `upscale_step` writes `OUT/<shot>.mp4` only for a generated shot id of the plan (UPSCALE_SHOT_REFUSED otherwise); the resume copy uses `find -exec cp -n` into one folder; the record job writes under `evidence/episodes/<EP>` with `$EP` regex-checked. | `long_build.upscale_step`, `long-build.yml` record job |
| S6 write permission wider than needed | long-build | FALSE POSITIVE | < 8 | Yes | `contents: write` only in the record job (release assets and the evidence branch), which holds no secret and runs after the assembly's checks; it verifies the report, manifest and .srt hashes against the file before any upload. | `long-build.yml` record job |

| H3 the token in every step's env | long-build | HARDENING, APPLIED (review of #470) | - | Yes | `GH_TOKEN` is no longer in any job's `env:`: only the steps that call `gh` or `ci/assets.sh` (the guard, refs, generate, the resume steps, upscale, assemble, record) get it. The resume provenance check (H2) moved into `long_build.py resume-names` / `resume-download`, tested with a fake `gh`. | `test_long_build.test_long_build_yml_ships_approved_clips_only_and_resumes`, `Resume` |

0 of 6 claimed findings at 8 or above; 3 hardenings applied in the PR (H1, H2, H3).

Note outside this PR's scope (not a security finding): `episode.yml`'s `resume_run` has the same shape as S3 (any run
id's `episode-*` artifact); its clips are then checked by sha256 against `shots/<episode>.json`, which closes it there.

| Zone | Reason |
|---|---|
| `oauth-compliance` | heroverse-oauth-compliance holds only static HTML (privacy, terms); no code or credentials. |
