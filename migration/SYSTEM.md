# HeroVerse: current operating contract

This is the single current workflow for every executor. The product is the English KJV Bible series on
`@heroverse74`: original stories, Shorts and their story longs. The continuation point is
`evidence/handoff/CURRENT.md`; `OPERATIONS.md` maps the implementation. Receipts and audits remain evidence.

**Construct for 9.5, verify the actual result, publish it, confirm it is public and processed, then continue.**
Do not restart accepted work because the executor changes, a slot passes or one provider is unavailable.

## 1. Continue the accepted delivery

1. Read CURRENT, the current plan or preserved-edit binding, relevant source approvals, saved jobs and ledger.
2. Acquire or validate the existing shared executor lease before effects. Reconcile uncertain operations by their
   saved identity before any retry. `OPERATIONS.md` defines the compare-and-swap procedure.
3. Identify the missing check or demonstrated defect. Complete it at its responsible stage and retain all
   still-valid work. A draft, workflow success, issue closure or merged PR is not audiovisual approval.
4. Update the same delivery records and CURRENT with the result and one concrete next action. No parallel ledger,
   replacement scheduler or extra approval stage is created for a handoff.

Keep one current delivery and one next episode in preparation. The immediate order is Short09, Short10
preparation, then the existing arc-01 long. Use confirmed completions to restore cadence; missed dates are not slots
to backdate or batch together. `production/bible/SERIES.md` defines the editorial plan and conditional reserve.

## 2. Bible Short: the existing episode route

The proven route is episode plan → approved sources and preflight → `episode.yml` composition → complete
audiovisual review → episode record → **`publish-episode.yml`** → YouTube readback. Genesis08 used this route successfully.

| Stage | Work and evidence | Acceptance |
|---|---|---|
| Plan and sources | `bible-plan-v2`, exact KJV, narration and shot timing; inspect each source and a contextual construction sample | Sources fit their words and purpose; approvals bind their bytes, request, reviewer and context |
| Preflight | `plan_check.py --strict`; `episode_build.py preflight` and `verify-preflight` for a regular build | Current inputs, approvals, timing, references and required probes pass before dispatch |
| Compose | `episode.yml` assembles approved sources; preserve a pre-existing edit through `episode_build.py import-edit` | Final video, accepted audio, captions, construction record and measured technical checks agree |
| Review | Full native audio/video evidence or an authorized session that watches and hears the complete master | Every rubric item ≥7 and overall ≥9.5; source, originality, policy and package checks pass |
| Publish | Qualified `episodes/<id>.json`, `episode_build.py check-record`, then `publish-episode.yml` | Hash, channel, approved package, revocations and existing ledger are checked before upload |
| Confirm | Reconcile the existing video ID through the publisher/receipt route | YouTube reports `public` and `processed`; preserve the receipt and finish pending package work |

An imported edit resumes from its actual media and preserved audio. The tracked plan's old estimate or refusal
count is not a measurement of a different imported timeline. Reconcile the current binding and inspect the actual
source/context; retain every applicable refusal. The import receipt and DRAFT renderer do not approve a source or
produce a publication qualification. A clean final master must be built from accepted construction and reviewed
under its own hash. Private unfinished material stays private during transport.

BibleShort records and the existing episode publisher are the publication interface. The long's `APPROVAL.json`
and pilot gate are not an additional BibleShort stage. A record writer must not invent a review to satisfy an
interface; code that only checks record fields is not evidence that a perceptual review occurred.

## 3. Story long: its separate existing route

Use `production/bible/LONG_DESIGN.md`, the long's registered structure and frozen criteria. The path is
`long_plan_check --strict` → current long preflight and approved sources → `long-build.yml` → the exact long
handoff/technical evidence → complete authorized review → **`approve.yml` → `prepublish_gate.py` → `publish.yml`**
→ public/processed readback. Long preview and source checks resolve defects before a complete final render.

The long session identities allowed by `publish/owner_quality_policy.py` are `claude-session-reviewer` and
`gpt-6-astra-session-reviewer`. Record the one that performed the work. Only the existing workflow may write the
long's `APPROVAL.json`, from actual passing evidence. No hand-written approval, provider error or transferred score
satisfies it. Frozen criteria remain unchanged; a Short's approval never approves its arc's long.

## 4. Construction and source policy

Apply the eight review dimensions while selecting each source and checking its contextual sample, before the
complete final render. A target of 9.5 is a construction requirement, not an assigned review score. Record the real
frame interval, words, dramatic purpose, source identity, observed figures/action, movement and remaining defect.
`production/bible/PROMPT_GUIDE.md` gives the detailed construction rules and existing probes.

- Reuse qualified existing clips, stills, voices and evidence while their exact inputs and context match.
- Pavo is the first current route for the hook and speaking Keeper/characters, subject to exact zero-credit quote,
  current shared capacity, approved references and the actual speech/lip-sync checks. Preserve accepted audio;
  a provider's incidental track is not permission to replace it.
- **Keeper Plan B remains authorized:** an explicit `voiceover:true` Keeper is silent on screen while the original
  narration plays. Use approved matching footage and its still-mouth evidence. It must pass the same identity,
  contextual quality, timing and ≤25% share rules. A failed talking clip is not relabeled as a passing silent one.
- Licensed/public-domain footage and GPT-generated stills with cinematic motion are authorized for appropriate
  other visuals. Record their true origin, rights and actual capabilities. Public access is not a licence; unknown
  provenance stays pending. A GPT image is not relabeled as Pavo or as a different licence to fit an old record.
- Camera motion on a still is camera motion. It does not establish body action, fluid movement or lip-sync. Show
  the actual dramatic action where required, including the acted climax; qualify the result in context.
- God's words stay exact KJV in the pinned offscreen voice. Never depict God as a person. Approved characters and
  the canonical ark references remain consistent; do not invent dialogue or modern objects.
- Sources and thumbnails need real observed approval ≥9.5, bound to their bytes and true reviewer identity.
  Revocations remain binding. Repair the responsible source without regenerating unrelated work.

Every regular build has its current preflight. Every later refusal remains mapped in `ops/refusal_registry.json`
to an early check, a measured probe, a residual review question or an explicit external blocker. Class-level fixes
and regression tests prevent the same construction failure from recurring in full renders.

## 5. Audiovisual review and publication quality

The reviewer must receive the complete video's native audio and video, verify its identity and technical evidence,
and assess the full result. Contact sheets support image inspection; audio measures support technical assessment.
Neither substitutes for hearing delivery, music, continuity and spoken words.

The owner authorized the tested native Gemini route for Short09 on 29 October. `native-review.yml` records the actual
`gemini-3.8-flash` identity, native audio, explicit 4 fps video sampling, full timeline coverage and saved interaction
IDs. This is an authorized route for the actual Short, not an exclusive model mandate inherited from another
format. Sampling is disclosed; it does not claim 30 fps inspection. A session review must similarly state what it
actually saw and heard. The detailed evidence and rubric are in `ops/CLAUDE_REVIEW.md`.

Every rubric item must be ≥7 and overall ≥9.5 for a new upload. A score below 9.5 names the timestamped defect.
Keep actual failed reviews and their findings. Correct the demonstrated defect, then review the changed master;
do not resubmit unchanged media to seek a higher score or replace the reviewer's identity. Unknown coverage,
missing audio, an unavailable provider or an expired target is not PASS.

## 6. Originality, intention and monetization quality

Every video must meet the existing originality and value requirements:

- Script 8-word shingle overlap <5% against each mined reference transcript; retain hashes rather than copied text.
- Against the channel's last 10 videos: a different opening, Scripture set, image set and a title that changes more
  than keywords; script overlap <15%. This concerns the actual comparison set and result, not a new requirement to
  reconstruct every historical episode before one delivery. Reuse of an approved asset is judged in the complete
  episode's context; it does not automatically make the image set identical.
- Original reflection/teaching is ≥35% of spoken words generally and ≥40% in the current BibleShort contract, with
  its own insight of at least 20 words. KJV quotations count as Scripture even when a label is missing.
- The opening promise is fulfilled, each beat adds meaning and the ending resolves it. A slideshow or decorative
  motion with little narrative value does not meet the editorial standard.
- The support critique checks fear-bait, fabricated prophecy, health/wealth promises and borrowed identity. Any
  finding is corrected. Missing comparison/critique evidence remains explicit; no mechanical PASS is invented.
- Disclose realistic synthetic people/events and record scenery-only generation accurately.

Monetization strategy is to deliver distinctive, original Bible stories consistently, improve retention and
subscriber value from measured results, and connect Shorts to their completed story long. Ads and the digital
product remain on hold. No revenue or eligibility outcome is guaranteed by publication count alone.

## 7. Publish the complete package and verify it

Use the approved title, description, thumbnail, captions, disclosure, playlist and intended visibility. From
BibleShort part 9, the approved character thumbnail is required. It shows the story character with approved
references, a clear emotion and at most 4 words; dimensions follow the format. Metadata follows the current
structure and existing publisher checks. Shorts link to the arc's long once that long is public.

Upload idempotently through the format's publisher. Reconcile saved upload sessions, ledger entries and video IDs
before retrying. Verify the channel and returned visibility/processing state. A private/scheduled upload is
recorded as such until its intended public state is confirmed. A failed thumbnail, comment, caption or readback
resumes on that same video; it never justifies another upload. Studio-only package tasks remain explicitly pending.

Completion evidence is the existing receipt for the public, processed video. Then update the same episode
record/ledger and CURRENT, continue the next episode, and let the existing arc-link/mirror paths consume the public
delivery. Comments and other outward messages follow their existing authorization and policy.

## 8. Automation, cost and learning

Use the existing heartbeat, durable requests and shared supervisors. The heartbeat can hand a qualified plan to
an existing build and discover its evidence; source/perceptual review still requires an available authorized
executor. Verify each surface from runs and receipts before describing it as autonomous. No extra clock.

No new spending or paid fallback. A tool balance, historical quota or elapsed wait is not a new authorization.
Pavo needs a fresh exact zero-credit quote and shared quota readback; uncertain jobs are reconciled before creation.
vidIQ research uses the existing ledger and ceilings only when current access/cost permits; do not repeat paid
research to reconstruct available evidence. Buzzy remains diagnostics-only until its route is qualified.
Runway remains excluded. Buffer's free mirror follows an already-public YouTube Short.

Actions minutes are speed evidence: standard GitHub-hosted runners are free for public repositories. Keep the
existing account/runner limits and avoid unnecessary rebuilds. Delegate bounded independent work, read only the
needed evidence, reuse reviewers for their fixes and update CURRENT at a safe handoff. Check host availability
instead of assuming another agent's balance or installed tools. Preserve valid leases through handoffs.

Mining identifies structures rather than copying channels: ≥6 winners from ≥4 channels, no channel above one-third,
≥3 weak contrasts and measured drivers. Until validated, a candidate is a pilot. Winners have breakout ≥50;
drivers appear in ≥70% of winners and ≤30% of weak contrasts. Store sources, counts, instrument and limitations in
`structures/`; apply `strategy/BEAT_THE_REFERENCE_RULE.md` to measured targets. A renderer limitation does not by
itself disqualify a good structure; prove a zero-additional-cost execution before adopting it.

After publication, use available 48-hour and 7-day results at comparable ages to assess retention, audience response
and the Short-to-long path. Sparse data stays inconclusive. `mining/live_intel.py` and existing learning records
retain observations; change one supported attribute at a time and measure it. Defects and policy problems are
corrected immediately. `strategy/DECISIONS.md` summarizes current policy; CURRENT carries execution.

## Token budget

Hard rule (owner, 2026-10-31; E232): this project spends at most 50% of the weekly Claude Code cap, and the stop cannot
be passed. On 2026-10-28 ~13:08Z the account hit the weekly limit and every agent stopped until the reset on 2026-10-31
19:00Z, because nothing enforced a budget.
- `migration/ops/token_budget.json`: `weekly_cap_tokens` (an ESTIMATE: weighted usage from the first surviving transcript,
  2026-10-27T13:22Z, to the first weekly-limit error, 2026-10-28T13:07:59Z, about 201M; the real cap is at least that),
  `project_share` 0.5, `cache_read_weight` 0.1 (cache reads are cheap; counted tokens = input + cache creation + output +
  0.1 x cache read), reset Saturday 19:00 UTC. There is no warn level: crossing is a stop.
- Hook (`.claude/settings.json`, PreToolUse on every tool and UserPromptSubmit) runs `token_budget.py check`; exit 2 with
  TOKEN_BUDGET_EXCEEDED blocks. For an Agent call the hook takes the action type from the brief; for other tools, the tool kind.
  Over budget only `token_budget.py status|plan` and `git status` pass, so the session can report. Do not work around it.
- Pre-check: `token_budget.py check --action <type>` blocks when used + that action's p90 would cross the budget, or when
  its activity allocation (`token_plan.json`) would be crossed. Run it before a long, a Short, a clock or a review agent.
- Reading it: `token_budget.py status` (used, budget, %, projected end of week); `plan` (allocation, spent, left per
  activity: long, shorts, clocks, reviews_prs, reserve); `costs --write` (weekly, at the reset: recompute
  `token_costs.json` mean and p90 per action from last week's transcripts); `plan --write` (re-size the allocations from
  the cost table and the cadence in `token_plan.json`, scaling down when the cadence does not fit the budget).
- `record --action T --actual N` after each action stores the actual against its estimate; with 3+ actuals in the week
  the estimate follows them. `record` alone saves the weekly ledger (`migration/evidence/tokens/<week>.json`, merged by
  max per session so container restarts lose nothing); commit it with the handoff.
- Be economical: no whole-file reads of big files, no 600k+ context orchestrators, brief agents narrowly.
Antidote: `migration/ops/test_token_budget.py`.
