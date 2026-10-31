# HeroVerse: executor entry point

The channel is the English KJV Bible series, story by story. Reply to the owner in concise Portuguese and work
toward a verified public delivery. A plan, a successful job or an uploaded private file is not publication.

## Read in this order

1. `migration/SYSTEM.md` — the single current operating contract, including the separate Short and long routes.
2. `migration/evidence/handoff/CURRENT.md` — the one current continuation point.
3. `migration/OPERATIONS.md` — commands, workflows, shared control and actual automation limits.
4. The relevant plan, source approvals, media evidence and publication ledger. Read
   `migration/production/bible/PROMPT_GUIDE.md` for construction and `migration/ops/CLAUDE_REVIEW.md` for review.

Read only the evidence needed for the current delivery. Historical receipts, audits and error records establish
what happened; they do not create a competing set of instructions. Update CURRENT when the accepted delivery moves.

## Execution rules

- Preserve valid work and the original accepted audio. Correct the demonstrated defect at its responsible stage.
- Build for 9.5. Sources, actual audiovisual review, applicable technical criteria and the publication package
  must qualify for the exact files used. Missing evidence stays pending; never copy a score to changed media.
- Bible Shorts use `publish-episode.yml`. Longs use `approve.yml` → `prepublish_gate.py` → `publish.yml`.
  Only that long approval workflow writes its `APPROVAL.json`; never fabricate an approval for either format.
- Record the true executor and reviewer. Actual audio and video must be reviewed; frames and technical audio
  measures alone do not establish audiovisual quality.
- No new spending. Use current quotas and exact zero-cost verification. Never expose credentials or private media.
- Respect the existing shared executor lease, durable request claims and saved provider IDs before effects.
- Code changes use `claude/*`, a PR, required checks/reviews and squash merge. Run the relevant tests in
  `.github/workflows/pr-checks.yml`; retain the root-cause/antidote process in `migration/ops/ERRORS.json`.
- Keep the existing heartbeat and supervisors. Verify that an execution surface is available before claiming
  automation; a new chat or handoff does not transfer a running clock.

Use the installed original PR Review Toolkit and verified security sweep when applicable; record which executor
actually ran them. Existing Hookify/security guards remain in force. If the session starts above the repository,
`migration/ops/link_session_guards.sh` exposes those guards to that session. Skill availability is host-specific.
Use `.claude/claude-security-guidance.md` for diff security rules and `docs/audits/` for recorded sweeps.
`migration/production/bible/brand-profile.md` supplies the series voice; `migration/strategy/VIDIQ.md` supplies
the current research and cost rules, under SYSTEM.
Ads and the digital product remain on hold. Buffer's free mirror may reuse an already-public YouTube Short.
