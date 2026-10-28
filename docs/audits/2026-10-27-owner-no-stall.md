# Verified security sweep: owner-no-stall, 2026-10-27

## Context

Scope: branch `claude/owner-no-stall` (owner 27/10 R1-R4; E129, E130, E131), merged with `claude/pavo-shared-quota`
(#475, swept separately in `2026-10-27-pavo-shared-quota-e128.md`).
- Code: `migration/integrations/pavo/video.py` (status `blocked`, PAVO_PROMPT_BLOCKED, reason code only),
  `migration/production/bible/pavo_native.py` (native requests, speech checks, premix), `shot_sources.py` (reuse,
  budget allocation, fallbacks, approve-source, fetch by source), `episode_build.py`, `long_build.py`,
  `long_plan_check.py`, `plan_check.py`, `episode_preflight.py`, `long_preflight.py`; the gate readers
  `migration/production/qa_pilot.py` (STORY_V4_ROWS), `migration/publish/prepublish_gate.py` (v4 pin and rows),
  `migration/production/render_queue.py` (v4 pin), `migration/publish/publish_video.py` (v4 longs keep the .srt rule).
- Workflows: `.github/workflows/pr-checks.yml` (one test path added: `bible/test_shot_sources.py`);
  `.github/workflows/shot-probe.yml` (review of #476: the record job runs `episode_build.py merge-blocks` and adds
  `evidence/pavo/prompt-blocks.json` to its probe-branch commit).
- Review of #476 (re-swept 2026-10-28): the voice reference bound to `voices.json` by sha256 and the new
  `episode_build.py voice-reference` command (writes `voices.json` only from a sealed shot-probe record, by PR),
  `long_build.upscale_step` still_motion through `shot_sources.fetch_source`, `approve-source pavo_reuse` refusals.
- Data: new frozen `migration/production/qa_criteria_story_v4.json`, `bible/voices.json`,
  `evidence/pavo/prompt-blocks.json`, `ops/refusal_registry.json`, `ops/ERRORS.json`.

Trigger: the PR touches `.github/workflows/` and `migration/publish/` (CLAUDE.md: a recorded sweep).

## Delegation

Run by the implementing agent on its own worktree, after the tests. Categories from `docs/audits/categories.md`:
secrets, workflow script injection, publish gate integrity, frozen QA criteria, failure turned into a pass, spend
ceiling, external integrations, path containment.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 secret in new files or logs | owner-no-stall | FALSE POSITIVE | < 8 | Yes | No key, token or credential added; the adapter returns the block's reason code only (a strict `[a-z_]` pattern), never its text, and the test asserts the token is absent. | `test_a_prompt_filter_block_is_its_own_status_never_incomplete` |
| S2 workflow injection or permission change | owner-no-stall | FALSE POSITIVE | < 8 | Yes | `pr-checks.yml` gains one path in the existing test loop; no `${{ }}` in a `run:`, permissions and concurrency unchanged. Review of #476: `shot-probe.yml`'s record job adds one `python3 -I -B ... merge-blocks` line on paths it already builds (`$d` from the regex-checked `$EP`, `$GITHUB_RUN_ID`) and one file to its existing `git add`; it still pushes only its own `claude/shot-probe-<ep>-<run>` branch (main is reached by PR only), no new secret, permission or `${{ }}` in a `run:`. | `shot-probe.yml` diff; `test_blocks_learned_in_actions_persist_with_the_record_and_bind_the_preflight` |
| S3 frozen criteria edited or loosened | owner-no-stall | FALSE POSITIVE | < 8 | Yes | v1/v2/v3 story and pilot v3/v4 files untouched (v3 sha `746e772d...` still pinned). v4 is a new file; a test holds every v3 value equal in v4 except `rights.ai_video.audio` and the added rows; WER 0.1 on the whole file, loudness, holds and the 9.5 floor unchanged; the per-clip rows are stricter (WER 0 per clip). | `test_v4_is_v3_with_only_the_owner_rows_changed_or_added`; `test_the_criteria_a_plan_is_checked_against_are_the_ones_the_gates_read` |
| S4 failure turned into a pass | owner-no-stall | FALSE POSITIVE | < 8 | Yes | Every v4 row is a gate item; an absent or None check is UNKNOWN (asr_model_pinned unmeasured is UNKNOWN). A native clip ships only with a speech record of that exact clip whose recomputed verdict is empty (SPEECH_UNCHECKED); a missing measure is a flag, never a pass. A fallback needs Claude's approve-source (>= 9.5) and is refused on a spoken or character shot. | `test_failed_speech_checks_or_an_unpinned_asr_never_pass`; `test_a_clean_clip_passes_and_each_defect_fails`; `test_a_fallback_is_refused_where_it_would_break_the_floor` |
| S5 publish gate integrity | owner-no-stall | FALSE POSITIVE | < 8 | Yes | prepublish_gate pins v4's hash and file like v3; publish_video applies v3's caption-track rule to v4 longs too (a v4 long without its track is refused). No approval path added; APPROVAL.json still only from approve.yml. | `StoryV4` in `test_prepublish_gate.py` |
| S6 external integrations (Pavo CDN fetch, git) | owner-no-stall | FALSE POSITIVE | < 8 | Yes | An inventory clip is fetched only from `https://cos-aigc-default.agnes-ai.space/...mp4` (no query, fixed host) and its sha256 checked; branch records are read with `git` argument lists, branch names matched by `quota.PROBE_BRANCH` and paths from `probe_record_path`. No new endpoint, no paid call, no generation in this PR. | `shot_sources.CDN`, `fetch_source`; `test_a_clean_clip_on_a_shot_probe_branch_is_awaiting_review_not_queued` |
| H1 path from JSON (speech sidecar) | owner-no-stall | HARDENING, APPLIED | < 8 | Yes | `speech-check` wrote its sidecar under `evidence/shots/<record episode>/speech/`; the record must now sit under `evidence/shots/` and its episode match the plan's and EPISODE_ID. A library asset name, a still path and an inventory URL are each matched before use. | `episode_build.speech_check_step` |
| H2 artifact data into a committed file (prompt blocks) | owner-no-stall | HARDENING, APPLIED | < 8 | Yes | `merge-blocks` copies the probe record's blocks (from the probe job's artifact) into `prompt-blocks.json`: the digest must be 64 hex, the reason `[a-z_]`, the shot `[a-z0-9-]` and the conversation id `[A-Za-z0-9_-]`, anything else dropped; never the filter's text. | `pavo_native.merge_blocks`; the same test |
| S8 voice reference written by a command | owner-no-stall | FALSE POSITIVE | < 8 | Yes | `voice-reference` writes `voices.json` only from a sealed shot-probe record under `evidence/shots/` (run id), an uploaded clean native clip whose speech sidecar passes every non-voice check, with a score >= 9.5 and a note; the sha256 is copied from the record. `speech-check` refuses a REFS file that is not the recorded clip. Nothing is approved for publication by it. | `VoiceBinding` in `test_episode_build.py` |
| S9 still path at the long build | owner-no-stall | FALSE POSITIVE | < 8 | Yes | `long_build.upscale_step` renders a still only through `fetch_source`: inside the repository and of the approved sha256 (STILL_PATH_REFUSED, STILL_SHA256_MISMATCH). | `test_an_approved_still_is_rendered_only_if_it_is_the_still_claude_approved` |
| S7 spend | owner-no-stall | FALSE POSITIVE | < 8 | Yes | No vidIQ, Pavo generation or paid service; the fallbacks are the vetted free library and FLUX stills already on the free Workers AI allocation; Pavo's budget is the shared guard of #475. | diff |

Score: 0/9 security findings at or above 8; two hardenings (H1, H2) applied in the PR.

## Candidates verified and refused

| Zone | Reason |
|---|---|
| ffmpeg filter strings (premix, still motion) | Built from floats formatted by the code and fixed constants; file paths go in `-i` arguments, never in a filter or a shell. |
