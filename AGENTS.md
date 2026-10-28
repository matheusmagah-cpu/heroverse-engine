# HeroVerse: entry point for ChatGPT and Codex

The project memory already lives in this repository. Read `CLAUDE.md` first: its
fixed owner rules and reading order apply to work by any assistant. This file is
an entry point, not a second set of production rules.

Before continuing production, read the latest files in
`migration/evidence/handoff/`, the current plans and ledgers, and the latest
applicable decisions in `migration/strategy/DECISIONS.md`. Historical handoffs
describe their own snapshots; current plans, evidence and later owner decisions
must be checked before acting. `migration/production/bible/SERIES.md` supersedes
the retired prayer niche.

Keep implementation changes on a `claude/*` branch and follow the existing PR,
test and review process in `CLAUDE.md`. Use the tests in
`.github/workflows/pr-checks.yml` before pushing. Do not create a parallel status
ledger: record a transition in the existing handoff directory.

Review evidence must identify the assistant that actually performed the review.
A legacy filename containing `claude` is not permission to claim that Claude
reviewed a file. Consult the current designated-reviewer policy and
`migration/ops/CLAUDE_REVIEW.md`; changing the agent never replaces the required
viewing, scores, hashes or automatic publication gates.

Verify scheduled execution separately from a chat handoff. Existing GitHub
workflows, external assistant clocks and local-computer runners are different
execution surfaces. Record which ones were actually checked or transferred;
do not infer that a clock moved merely because another assistant has the code.
