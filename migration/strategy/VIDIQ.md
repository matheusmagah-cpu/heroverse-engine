# vidIQ in HeroVerse — role, limits, validation (2026-10-18)

The owner uses vidIQ (app.vidiq.com, channel HeroVerse connected; screenshot 2026-10-18: 262 subscribers,
2.68k views). This file fixes what vidIQ may do in the project, before any of its numbers are used.

## What vidIQ is (sources: vidIQ support and MCP pages, third-party reviews; vidiq.com is blocked from our cloud)
- Research product over the YouTube API: keyword research (Keyword Score = estimated 30-day YouTube searches +
  competition, in brackets Very low 0-19 … Very high 80-100; volume/competition shown High/Medium/Low), outliers
  (videos far above their channel's usual views), trending videos, channel stats, similar thumbnails, earnings
  estimates, daily AI ideas, AI coach.
- **Official MCP server** (52-67 tools, read-only), in the Claude connector directory ("vidIQ",
  directoryUuid dc5bb20f-6ebd-4dbe-a47e-c2d20fa25acc), available on every plan including Free; tool calls draw
  from the plan's shared credit pool (third-party: ~5 credits per call; Free ~150 credits/month → ~30 calls/month).
- vidIQ publishes no accuracy figure for its search-volume estimates; they are modelled estimates.
- No public REST API at standard tiers; automated scraping of the site is outside its terms (and vidiq.com is not
  reachable from our cloud). The only sanctioned machine path is the MCP server (OAuth, or a read-only API key).

## What it may do here (and what not)
| Use | Status | Why |
|---|---|---|
| Keyword demand/competition for the topic and title of the next script (1 call/day) | **informative** until validated (below) | estimate of unknown accuracy |
| Outliers in "morning prayer", "night prayer before sleep", "psalm 91", "prayer for healing" (weekly, 4 calls) | candidates for structure_channels.txt / mining, then measured by our own instruments | finds videos our search panel misses |
| Trending videos in the niche (weekly, 1-2 calls) | context for the daily analysis | — |
| Subscribers, views, watch hours of our channel | **not used** | official numbers come from the Data API / Analytics API (vidIQ showed 262 while the Data API gave 263: cached) |
| Earnings estimates | not used | monetisation not reached; estimates only |
| AI titles/thumbnails/ideas | not used to decide | our packaging is mined and gated; an AI suggestion is not evidence |
| Any change of strategy, format, packaging or cadence | only through the owner's 90 % rule (DECISIONS.md) | vidIQ numbers alone never pass it |

Budget: the connected account holds 6,000 renewable credits a month (+120 add-on; balance read 2026-10-18,
renews 2026-11-18); keyword research costs 5 credits. Cap for the project: 1,000 credits a month (≈ 200 calls),
spent by the main/daily Claude session; never in GitHub Actions without a read-only API key stored as a secret
(owner decision). No plan change or purchase.

## Validation before vidIQ may break a tie between topics (pre-registered)
- Sample: the 30 queries of our market panel (`market-panel/panel-*.json`), plus the next 10 script topics.
- Our own measure: median views/day of the top results the panel finds for each query (Data API, measured).
- vidIQ measure: Keyword Score and volume bracket for the same query (MCP `vidiq_keyword_research`, ~40 calls,
  spread over the free monthly budget).
- Criterion fixed now: one-sided Spearman ρ ≥ 0.5 with p < 0.10 between vidIQ volume and our measured demand →
  vidIQ may break ties between topics that are otherwise equal under MODELING_SPEC; otherwise it stays
  informative. Re-checked monthly.

## Validation result 2026-10-18 (`evidence/vidiq/validation-20261018.json`)
30 panel queries, 150 credits. vidIQ estimated monthly searches vs our measured demand: Spearman ρ = 0.404,
one-sided p = 0.014 (permutation, 100k). The association is real but below the pre-registered ρ ≥ 0.5: **FAIL**.
vidIQ stays informative and does not break topic ties. Overall score (volume + competition) vs our demand:
ρ = 0.10, p = 0.30 (no signal). Re-check monthly with the same criterion; the criterion is not lowered.

## Tool safety
`.claude/settings.json` denies every vidIQ tool that writes to the channel or to Instagram (update video/thumbnail,
upload, reply to comments, publish reel, connect/authorize channel, competitor edits) and the credit-heavy media
generators. Publication only ever goes through the pipeline's gate.

## Security note (owner decision)
vidIQ's channel connection asks for "Manage your YouTube account" (scope `youtube`, write access) plus Analytics
read. The research tools and the MCP connector do not need the channel connected. Least privilege: keep the vidIQ
account for research and revoke its channel access at myaccount.google.com/permissions if write access is not
needed (reversible; reconnect any time).

## Status
Connector connected 2026-10-18 by the owner (claude.ai → Settings → Connectors → vidIQ).
