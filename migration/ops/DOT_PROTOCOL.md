# Claude ↔ Dot contract (owner, 2026-10-18)

One rule above all: **Dot delivers exactly what the task card asks — not more, not less.** Claude writes the card,
checks the delivery and answers for the result to the owner.

## Roles
| | Claude (direction) | Dot (executor) |
|---|---|---|
| Does | strategy, decisions, task cards, rules, review, merge, owner reports, small fixes | token-heavy work: full scripts, large code with tests, long reading into summaries |
| Never | loosens a rule or an acceptance check to accept a delivery | merges, publishes, approves a video, edits frozen QA, touches secrets, works outside the card |

Channel: GitHub issues and PRs only. No secrets anywhere.

## 1. The task card (Claude, issue from the "Dot task" template, label `dot-task`)
Every card has these eight parts; a card missing one is not sent.
1. **GOAL** — one sentence: what exists when the task is done.
2. **INPUTS** — the files Dot reads (paths).
3. **ALLOWED PATHS** — a fenced ` ```allowed ` block, one glob per line. **Dot may create or change only these
   files.** PR checks fail any other file (`migration/ops/dot_scope.py`).
4. **EXACT VALUES** — every fixed value (dates, slots, titles, counts, limits). Dot copies them; never changes them.
5. **QUALITY BAR** — what makes the content good enough (format rules, sources, tone), beyond the automatic checks.
6. **ACCEPTANCE** — commands that must print PASS, run by Dot and by PR checks.
7. **FORBIDDEN** — the owner rules for this task (always: no secrets, merge, publication, approval, frozen-QA edit,
   copying; plus anything specific).
8. **DEADLINE (UTC)** and **BRANCH** `dot/<issue>-<slug>`.

Before sending, Claude checks every value against the repository as it is (schedules, slots, existing files,
`script_check.py` rules) — the card must be executable as written.

## 2. Dot's line
- Claim: label `dot-working` + comment `CLAIMED <ISO time>`. One task at a time, oldest deadline first; a card that
  says "START ONLY AFTER …" waits for that comment.
- Work only inside ALLOWED PATHS, with the EXACT VALUES. Merge `origin/main` into the branch before delivering (merge
  commit; no rebase, no force-push).
- If the card is impossible, contradictory or missing something: **stop and report `RESULT: BLOCKED`** with the exact
  question. Never improvise, never widen the scope, never "fix" something outside the card. Ideas go in `NOTES`.
- Deliver: PR titled like the card, body `Closes #<issue>`; then one comment on the issue, exactly:
  ```
  RESULT: DONE | BLOCKED
  PR: #<n>
  FILES: <every changed path>
  ACCEPTANCE: <command> -> PASS | FAIL   (one line per command)
  CI: <PR checks run link> -> success | failure
  NOTES: <decisions inside the card's freedom; any doubt>
  ```
  and swap `dot-working` for `dot-done`. `DONE` only when every acceptance line and CI say PASS/success.
- Check for open `dot-task` issues at least every 2 hours.

## 3. Claude's review (hourly clock; every `dot-done`)
1. **Automatic:** PR checks green (unit tests, acceptance of every pilot touched, ALLOWED PATHS scope).
2. **Report:** the RESULT block is complete and true (FILES equals the PR's files; CI link is this PR's run).
3. **Quality:** Claude reads against the card's QUALITY BAR. For scripts: hook, CTA, every policy-sensitive line, a
   sample of KJV quotes against the KJV text, the EXACT VALUES.

One of three outcomes, written on the issue:
- **ACCEPTED** — Claude merges (squash), label `claude-accepted`, issue closed.
- **REWORK** — Dot's delivery misses the card: a numbered list of exact fixes; label back to `dot-task`.
- **SPEC-FIX** — the card was wrong or too small for the needed result: Claude edits the card (marks it `SPEC v2`,
  stating what changed and why), then label back to `dot-task`. Claude's error is corrected in the card, never
  pushed onto Dot.
Two REWORKs on one task → Claude reports to the owner with the cause.
Every REWORK or SPEC-FIX is an error: Claude also adds its antidote (a check in `script_check.py`, `dot_scope.py`,
a test, or a line in the card template) and a line in `ops/ERRORS.json`, so the same miss cannot pass again.

## 4. Standard card for a script (the main load)
- ALLOWED (two lines): `migration/production/<pilot>/*.json` and `migration/production/<pilot>/images/*.json`.
- EXACT VALUES: `publish_at`; one Short slot (night pilot of day D → D 14:00 UTC, morning → D 20:00 UTC); title or
  "after TOPIC CONFIRMED"; ≤ N new images; `qa_criteria.json` byte-identical to the latest pilot's.
- QUALITY BAR: original text only (no channel's script, voice, images or identity); KJV quoted exactly with "(KJV)";
  `strategy/MODELING_SPEC.md` §1 and the latest pilot's layout; no fear-bait, prophecy, health or wealth promises.
- ACCEPTANCE: `python3 -I -B migration/production/imagegen/hydrate_reused.py migration/production/<pilot>` then
  `python3 -I -B migration/production/script_check.py migration/production/<pilot>` → PASS; PR checks green.
