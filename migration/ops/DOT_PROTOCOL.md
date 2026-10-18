# Claude ↔ Dot protocol (owner, 2026-10-18)

**Roles.** Claude is the direction: plans, decides, writes the task specs, owns the rules (owner's 90% rule, gate,
policy, frozen QA), reviews, merges and reports to the owner. Dot is the executor of the token-heavy work: long
scripts, large code changes, bulk research reading, long documents. Neither changes the owner's rules; Dot never
merges, publishes, approves a video or edits frozen QA criteria.

**Channel: GitHub, nothing else.** No secrets in issues, PRs or comments.

1. **Task** — Claude opens an issue from the "Dot task" template with label `dot-task`: goal, inputs (files to read),
   exact deliverables (paths), acceptance (commands that must pass), constraints, deadline, branch `dot/<issue>-<slug>`.
2. **Claim** — Dot adds label `dot-working` and comments `CLAIMED <ISO time>` (one task at a time, oldest deadline first).
3. **Deliver** — Dot pushes the branch, opens a PR "Closes #<issue>", runs the acceptance commands itself, and comments
   on the issue one block:
   ```
   RESULT: DONE | BLOCKED
   PR: #<n>
   ACCEPTANCE: <command> -> PASS/FAIL (each)
   NOTES: <what was decided, anything uncertain>
   ```
   then swaps `dot-working` for `dot-done`. BLOCKED states exactly what is missing; nothing is guessed.
4. **Automatic check** — `.github/workflows/pr-checks.yml` runs every unit test and `script_check.py` on each pilot the
   PR touches, and posts the result as the PR's check.
5. **Review** — Claude's hourly clock looks for `dot-done`. Check green + diff within the task → Claude merges, closes
   the issue (`claude-accepted`). Otherwise Claude comments `REWORK:` with the exact failures and puts `dot-task` back.
   Two reworks on one task → Claude reports to the owner.
6. **Polling** — Dot checks for open `dot-task` issues at least every 2 hours (its own scheduled task). Claude's clock
   runs hourly. Typical turnaround: one cycle of each.

**Division of work**

| Work | Who | Why |
|---|---|---|
| Strategy, decisions, specs, task order, gate rules, statistics, final review | Claude | direction and rules |
| Full scripts (script.json ~3-4k words), images.json prompts, schedule.json | Dot | token-heavy writing |
| Large code changes, refactors, new modules with tests | Dot (spec + tests from Claude) | token-heavy |
| Reading long references (transcripts, competitor analyses) into structured summaries | Dot | token-heavy |
| vidIQ calls (budget/ledger), market opinions | Claude (data) → Dot may write the long prose | budget owner |
| Small fixes, merges, scheduled tasks, workflow dispatch, owner reports | Claude | fast and cheap |

**Script tasks** (the main load): Dot writes original text only (no copying of any channel's script, voice, images or
identity), KJV quoted exactly with "(KJV)" references, following `strategy/MODELING_SPEC.md`, the archetype files and
the pilot layout of the latest pilot; acceptance = `python3 -I -B migration/production/script_check.py migration/production/<pilot>`
PASS. Claude spot-reads hook, CTA and policy-sensitive lines only.
