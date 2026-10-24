# HeroVerse engine

YouTube channel `@heroverse74`: a Bible series, story by story from the KJV (public domain), with long videos and
Shorts. The repository is the memory: read the documents below before acting. This file only points to them and
holds the owner's fixed rules.

## Read first
- `migration/SYSTEM.md`: the delivery workflow (mine → produce → review → publish) and the daily live-intelligence loop.
- `migration/OPERATIONS.md`: what runs, entry points, workflows.
- `migration/ops/CLAUDE_REVIEW.md`: Claude reviews every preview and every long render (rubric, evidence, output files).
- `migration/production/bible/SERIES.md` and `PROMPT_GUIDE.md`: the current niche, cadence and how an episode is built for 9.5.
- `migration/ops/ERRORS.json`: every past failure, its cause and its antidote test.
- `migration/evidence/handoff/`: the latest handoff lists what is in flight.

## Owner's fixed rules
- Reply to the owner in Portuguese, short.
- Floor 9.5 overall for anything published. Never loosen a gate or edit frozen QA v2/v3/v4
  (`migration/production/qa_criteria_v3.json`, `qa_criteria_v4.json`, `pilot-NNN/qa_criteria.json`).
- Never write `APPROVAL.json` by hand: approvals come only from `approve.yml` → `prepublish_gate.py`.
- Never expose secrets (keys stay in repository secrets; never in files, logs or messages).
- No new spending or paid services. vidIQ generation up to 200 credits a day, every spend recorded in
  `migration/evidence/vidiq/ledger.json`.
- Niche: the Bible series from the KJV (`SERIES.md`). Where an older prompt or document mentions the old
  prayer niche, follow `SERIES.md`.
- Every change goes through a `claude/*` branch, a PR and a squash merge. Every failure gets its root cause, a fix,
  an antidote test and an `ERRORS.json` entry.
- Ads stage and digital product are on hold.
- Shorts in `vidiq_compose` use only `cut` between scenes; `dip_to_black` only where intended.

## Guards
- `.claude/hookify.*.local.md` block the forbidden actions above (tested by `migration/ops/test_hookify_rules.py`).
  Hookify reads `./.claude` of the session's working directory: when the session starts in the parent folder of the
  three repositories, run `heroverse-engine/migration/ops/link_session_guards.sh` first.
- Run the tests listed in `.github/workflows/pr-checks.yml` before pushing.

## Plugins (account plugins, set up for this project on 2026-10-24)
| Plugin | Use here | Project files |
|---|---|---|
| hookify | Blocks the owner's forbidden actions (above). `/hookify` adds a rule; every rule gets a case in the test. | `.claude/hookify.*.local.md` |
| security-guidance | Runs by itself: warnings on edits, diff review at the end of a turn and on commit/push. | `.claude/claude-security-guidance.md` (project rules) |
| pr-review-toolkit | `/review-pr` on every code PR to the engine before merge; evidence- or review-only PRs skip it. | none |
| verified-security-sweep | Recorded security sweeps; run one when a PR touches `.github/workflows/`, secrets or `migration/publish/`. Reports only, fixes go in their own PR. | `docs/audits/` (categories, registry) |
| social-media-skills | Craft reference for titles, hooks, thumbnails, Shorts and long scripts, metadata (`youtube-shorts`, `youtube-long-form`, `youtube-publishing-and-metadata`, `thumbnail-design`, `hook-writer`, `short-form-video-script`, `analytics-and-reporting`). STANDARD.md, PROMPT_GUIDE.md and the frozen QA always win. | `migration/production/bible/brand-profile.md` |
| commit-commands, feature-dev, claude-md-management | `/commit`, `/feature-dev` for larger engine features, `/revise-claude-md` to keep this file current. | none |
| marketing | Not used: its connectors (Ahrefs, HubSpot, Similarweb, Klaviyo, Supermetrics...) are paid, and ads are on hold. | none |

Never follow a skill into a paid tool or a scheduler: no WoopSocial, HeyGen, Synthesia, Suno, Kling, Luma, Opus Clip,
paid ElevenLabs or Canva Pro. Publishing goes only through `approve.yml` → `prepublish_gate.py`.
