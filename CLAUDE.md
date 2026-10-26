# HeroVerse engine

YouTube channel `@heroverse74`: a Bible series, story by story from the KJV (public domain), with long videos and
Shorts. The repository is the memory: read the documents below before acting. This file only points to them and
holds the owner's fixed rules.

## Read first
- `migration/SYSTEM.md`: the delivery workflow (mine → produce → review → publish) and the daily live-intelligence loop.
- `migration/OPERATIONS.md`: what runs, entry points, workflows.
- `migration/ops/CLAUDE_REVIEW.md`: Claude reviews every preview and every long render (rubric, evidence, output files).
- `migration/production/bible/SERIES.md` and `migration/production/bible/PROMPT_GUIDE.md`: the current niche, cadence and how an episode is built for 9.5.
- `migration/ops/ERRORS.json`: every past failure, its cause and its antidote test.
- `migration/evidence/handoff/`: the latest handoff lists what is in flight.

## Owner's fixed rules
- Reply to the owner in Portuguese, short.
- Floor 9.5 overall for anything published. Never loosen a gate or edit frozen QA v2/v3/v4/story v1
  (`migration/production/qa_criteria_v3.json`, `qa_criteria_v4.json`, `qa_criteria_story_v1.json`,
  `pilot-NNN/qa_criteria.json`).
- Never write `APPROVAL.json` by hand: approvals come only from `approve.yml` → `prepublish_gate.py`.
- Never expose secrets (keys stay in repository secrets; never in files, logs or messages).
- No new spending or paid services. vidIQ generation up to 200 credits a day, every spend recorded in
  `migration/evidence/vidiq/ledger.json`.
- Niche: the Bible series from the KJV (`SERIES.md`). Where an older prompt or document mentions the old
  prayer niche, follow `SERIES.md`.
- Every change goes through a `claude/*` branch, a PR and a squash merge. Every failure gets its root cause, a fix,
  an antidote test and an `ERRORS.json` entry, at once (owner, 2026-10-26: "an error must never repeat"). The antidote
  is a test that runs on every PR (`test_errors_register.py` refuses one that does not), so the error cannot come back.
- Ads stage and digital product are on hold.
- Shorts in `vidiq_compose` use only `cut` between scenes; `dip_to_black` only where intended.

## Guards
- `.claude/hookify.*.local.md` block the forbidden actions above (tested by `migration/ops/test_hookify_rules.py`).
  Hookify reads `./.claude` of the session's working directory: when the session starts in the parent folder of the
  three repositories, run `heroverse-engine/migration/ops/link_session_guards.sh` first.
- Run the tests listed in `.github/workflows/pr-checks.yml` before pushing.

## Plugins (set up for this project on 2026-10-24)
They load from the owner's claude.ai account, not from `.claude/settings.json`; this table says when each is used.
| Plugin | Use here | Project files |
|---|---|---|
| hookify | Blocks the owner's forbidden actions (above). `/hookify` adds a rule; every rule gets a case in the test. | `.claude/hookify.*.local.md` |
| security-guidance | Runs by itself: warnings on edits, diff review at the end of a turn and on commit/push. | `.claude/claude-security-guidance.md` (project rules) |
| pr-review-toolkit | `/review-pr` on every code PR to the engine before merge; evidence- or review-only PRs skip it. | none |
| verified-security-sweep | Recorded security sweeps; run one when a PR touches `.github/workflows/`, secrets or `migration/publish/`. Reports only, fixes go in their own PR. | `docs/audits/` (categories, registry) |
| social-media-skills | Craft reference for titles, hooks, thumbnails, Shorts and long scripts, metadata (`youtube-shorts`, `youtube-long-form`, `youtube-publishing-and-metadata`, `thumbnail-design`, `hook-writer`, `short-form-video-script`, `storytelling-and-narrative`, `analytics-and-reporting`). STANDARD.md, PROMPT_GUIDE.md and the frozen QA always win. | `migration/production/bible/brand-profile.md` |
| commit-commands, feature-dev, claude-md-management | `/commit`, `/feature-dev` for larger engine features, `/revise-claude-md` to keep this file current. | none |
| vidiq | Its 12 skills drive the vidIQ connector (`mcp__vidIQ__*`, same tool names; the plugin's own server gets 403 from the cloud proxy). When each skill runs and its limits: `migration/strategy/VIDIQ.md` "Plugin skills". | `migration/strategy/VIDIQ.md`, `migration/evidence/vidiq/ledger.json` |
| superpowers | Its SessionStart hook loads in every session. Used: `systematic-debugging` for every failure (the root cause in `ERRORS.json`), `test-driven-development` for the antidote test (fails before the fix), `verification-before-completion` before any push or "done". Skipped on clock runs and small fixes: `brainstorming`, `writing-plans`, worktrees, subagent plans. This file wins over its skills. | none |
| ffmpeg-llm | `ffmpeg-expert` agent when a render, `clip_check.py`, loudness or black-frame result fails or an ffmpeg command must change (`ci/render_pilot.sh`, `still_render.py`, `shorts_produce.py`). Commands still pass the frozen QA. | none |
| headroom | `/peek` and the skill before reading big files whole: `ERRORS.json`, `evidence/map/project-map.md`, ledgers, `out/qa.json`, workflow logs. | none |
| image-generation | Prompt craft for FLUX stills (`cf-images.yml`) and the first-frame still before paid AI video. `PROMPT_GUIDE.md` wins where they differ. | none |
| bible-by-midvash | Comparing translations and finding verses by keyword; its server (`mcp.midvash.com`) gets 403 from the cloud proxy, so unused until that host is allowed. Exact KJV quotation is checked offline by `migration/production/bible/kjv_check.py` (in `script_check.py`). | none |
| cartographer, claude-code-setup | Only when the owner asks (heavy codebase audit; one-off automation advice). `migration/ops/project_map.py` is the routine map. | none |
| marketing | Not used: its connectors (Ahrefs, HubSpot, Similarweb, Klaviyo, Supermetrics...) are paid, and ads are on hold. | none |

Connector Runway is paid: `.claude/settings.json` denies `mcp__Runway`; it also mirrors every vidIQ write and generator
deny for the plugin's server (`mcp__plugin_vidiq_vidiq__*`).

Never follow a skill into a paid tool or a scheduler: no WoopSocial, HeyGen, Synthesia, Suno, Kling, Luma, Opus Clip,
paid ElevenLabs or Canva Pro. Publishing goes only through `approve.yml` → `prepublish_gate.py`.
Owner's exception (2026-10-25): Buffer's FREE plan mirrors Shorts already published on YouTube to TikTok
(`tiktok.yml`, `BUFFER_API_KEY`); never a paid Buffer plan, never a first publication that skipped the YouTube gate.
