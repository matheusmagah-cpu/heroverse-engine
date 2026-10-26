# Verified security sweep: refusal-parity-e106, 2026-10-26

## Context

Scope: PR #422 (E106 refusal parity and episode preflight; E105 project_map).
- Workflows: `.github/workflows/episode.yml` (the `verify-preflight` step before any secret; the still-mouth tool
  check before any generation), `.github/workflows/pr-checks.yml` (two new tests).
- Scripts: `migration/production/bible/episode_preflight.py` (new), `episode_build.py` (shared prediction functions,
  offline request validation, `safe_rmtree`), `plan_check.py` (build prediction, path check, `PROMPT_REPEATED`),
  `migration/publish/publish_episode.py` (`problems(episode, video=None)`), `migration/ops/project_map.py`.
- Guards: four `.claude/hookify.*.local.md` rules; `migration/ops/refusal_registry.json`, `test_refusal_parity.py`.

Trigger: the PR touches `.github/workflows/` and `migration/publish/` (CLAUDE.md: a recorded sweep for both).

Branch: `claude/refusal-parity-preflight`. The sweep and the code review read the PR at `437deec`. The fixes below
are in the following commit on the same branch.

## Delegation

The coordinating session ran the security sweep (categories: workflow injection, path traversal and destructive
file operations, secrets, a gate that can be satisfied without its evidence). A separate code review covered
correctness. The primary session reproduced each review finding with a test that failed before the fix.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 plan input reaches the shell in episode.yml | refusal-parity-e106 | FALSE POSITIVE | < 8 | - | `PLAN` comes through `env:`, is matched against the fixed plans path pattern before use and always quoted | `episode.yml` plan step; `test_strict_refuses_a_path_or_episode_episode_yml_refuses` |
| S2 the report vouches for less than the build uses | refusal-parity-e106 | NOTED, FIXED | < 8 | Yes | setups.json, the reference image records and the build code were not bound; all of characters.json was | `binding()` + `stale_parts()`; `test_the_binding_holds_what_the_plan_uses_and_names_what_changed` |
| S3 `--write` trusts the plan's episode field | refusal-parity-e106 | NOTED, FIXED | < 8 | Yes | the report path and the work directory came from `plan["episode"]` | `episode_id()`; `test_a_crafted_episode_id_is_refused_before_any_path` |
| R1 rmtree of a path built from the episode id | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | `x/../../migration` would remove the repository tree in `voice_step` | id checked first (episode.yml's pattern and the file name); `safe_rmtree` refuses the root, anything outside it and links |
| R2 verify bound to the whole character bible | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | approving an unused character made a PASS stale; probes, images and code were unbound | canonical digest of the parts the plan uses; STALE names each changed part |
| R3 codes named at run time missed by the parity parser | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | `{}_CLIP_SHORT`, `REFERENCES_OVER_{}`, `{}_NOT_ON_HIS_LINE` and 14 more | AST of f-strings; `test_the_parser_sees_a_new_build_refusal`; 302 codes classified |
| R4 still-mouth negative control took any failure as "flagged" | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | a crash or missing model passed it | requires `MOUTH_TALKING` in the JSON; `test_the_still_mouth_negative_control_requires_mouth_talking` |
| R5 the preflight hook let `;`, `||` and another plan through | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | episode.yml's own verify still refused those runs | only `verify-preflight P && gh workflow run episode.yml -f plan=P`; cases in `test_hookify_rules.py` |
| R6 the cf-images hook blocked quoted valid values | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | - | optional quotes; ALLOW cases |
| R7 voice-over PROBE_REQUIRED named the talking minimum | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | - | `probe_required()`; `test_a_voice_over_probe_required_names_its_own_minimum_and_match` |
| R8 request_problems could crash | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | IndexError on an empty PavoError, any other exception escaped | `test_a_failing_request_is_a_named_refusal_never_a_crash` |
| R9 copies of publish_episode's rules and of the establishing share | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | - | `record_problems` calls `publish_episode.problems`; one `establishing_share` helper |
| R10 hand-parsed arguments; a zero-length line divided | refusal-parity-e106 | CONFIRMED, FIXED | review | Yes | - | argparse with a usage; `measured_pace` lists None |

## Confirmed defects

No security finding at confidence 8 or above; the findings index gets no entry. R1-R10 were defects in unmerged
code, each fixed on the branch with a test that failed first; they are recorded under E106.

## Coverage

All scoped files were read in full. Categories: workflow injection, path traversal and destructive file
operations, secrets in committed reports (none: hashes, ids and measures only), a gate satisfiable without its
evidence (the preflight report binding, the hookify forms).
