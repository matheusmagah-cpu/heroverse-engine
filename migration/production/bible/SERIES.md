# The Bible, story by story (KJV): series plan (owner, 2026-10-24)

Owner: one micro-story at a time from Genesis, narrated from the KJV (public domain), with cinematic motion,
finishing with a short reflection and a prayer. Shorts feed long videos. The current production and recovery
direction below supersedes historical source and calendar assumptions; frozen gates remain unchanged.

## Current recovery direction (owner, 2026-10-30)

The immediate priority is the next unpublished episode, **genesis-09-short**, with the owner's requested morning
publication on 30 October in America/Sao_Paulo treated as a target, never a readiness or scheduling claim.
At this checkpoint its active plan has 22 shots and 13 stills without approval, its preflight is stale, and the
preserved 175-second private v6 is a DRAFT. Its 21 visual segments, spoken opening and narrator must be reconciled
with the active plan and exact audio. Review the actual resulting master; old scores cannot approve a new hash.
If the morning target passes, record the miss and use the next eligible window after qualification. Do not skip
to a later episode, backdate an upload, bunch missed releases or rebuild unchanged accepted work.

Keep **one current delivery and one next episode in preparation**: finish 09, prepare 10's corrected script and
measured voice timing, then complete the existing arc-01 long. Existing clips, stills, voices and reviews are reused
only while their exact inputs and criteria match. Reconcile saved provider/run IDs before any new submission;
an uncertain request is never replayed. Keep the existing clocks and shared executor lease.

| Planning scenario through 16 November | Quantity | Condition |
|---|---|---|
| Regular Short opportunities, 30 October–16 November inclusive | 18 days × 2 = 36 | Candidate morning/evening windows; a missed window does not become a scheduled video |
| Recovery scenario | 36 regular + up to 4 extras = 40 Shorts | Extras on separate eligible days, at most one/day, only with the next day's regular Shorts ready and the long protected |
| Stretch production scenario | 70 Shorts | Capacity scenario only; requires measured free throughput, source/review capacity and audience evidence; no publication promise or new slots |
| Long recovery scenario | At most 9 longs | First only after 09; then at least 48 hours apart. Nine fits only if the first qualifies on 30 or 31 October; a later start reduces the count |

These are opportunities and scenarios, not inventory or YouTube schedules. Restore two daily Shorts only as
completed 9.5 masters sustain it; build the existing reserve target of four Shorts and one long without widening
work in progress. Do not force the long into a date unsupported by its sources and actual review. Re-anchor
remaining targets from confirmed publication/readback, preserving episode order. After the first new public
delivery, review process throughput and available audience evidence at 48 hours and again by 72 hours; sparse
analytics stay inconclusive. Adjust the next cycle from that evidence through DECISIONS.md.

**Sources.** Pavo is first for the speaking Keeper and speaking characters, with their approved references,
consistent voices, lip-sync and exact speech checks, and a fresh exact zero-credit quote. Preserve existing
matching clips first. God's words remain exact KJV in the pinned Kokoro voice over a scene without a person;
do not invent Noah dialogue. Buzzy stays on standby for diagnostics until its generation route, exact zero-cost
conditions, rights and media checks are qualified. Other scenes use action-matched licensed/public-domain video
or GPT-generated stills with cinematic motion, subject to proven provenance and the existing source gates.
Being publicly accessible does not establish a video licence; camera motion alone does not establish acted
animation or 9.5 quality. GPT DRAFT images are not automatically admissible under frozen story QA v5: qualify
the route without changing frozen criteria, and preserve their true origin and missing prompt evidence.

No new spending, paid provider reads, quota-reset assumptions or manual APPROVAL.json. Source approval,
current plan/preflight, technical QA, actual audiovisual review at overall 9.5, the existing publication gate
and processed/public readback are all required. `arcs.json.recovery` records the scenario and historical targets;
the old absolute targets remain evidence of missed commitments until a qualified re-anchoring decision exists.

## One format, two lengths: the Shorts lead to the long (owner, 2026-10-25)
Owner: "o que está pronto, mantém; a partir desse momento passa para a ideia do short ... o short tem que seguir o
padrão do longo e o longo do short ... o short direcionar pro vídeo longo; monta uma estratégia efetiva".

**Why (measured 2026-10-25, DECISIONS.md day 8 and evidence/vidiq/20261025):** Genesis 1 and 2 Shorts reached 107
and 192 views in their first day (breakout 14 and 48); the prayer long videos 8-96 views each. The long-form winners
of this line (7 channels, 8x-589x their channel) tell ONE Bible story per video in 11-47 min, titled
"<story>: <human angle> | Genesis N Bible Story".

**The funnel.**
- The Bible is told in **arcs**: one arc = one complete story = 4 Short episodes = 1 long video.
- **Shorts (the door; target 2 a day, morning/evening, subject to recovery above):** one moment of the arc each, in order, 170-179 s from
  part 7 (owner, 2026-10-26: the measured driver of `structures/bible-story-short.json`, 5/6 winners vs 0/3 weak; under
  YouTube's 180 s limit, the tail included; parts 1-6 stay at their 62-90 s), with sources following the current
  recovery direction and each scene matching its words. Built in four
  beats, recorded line by line in the episode's `narration` (kind scripture / story / insight / cta): the hook; the
  moment told in the KJV with our own retelling around it; one **insight** of our own (what most readers miss, a
  tension in the text, a critique of a common reading; never a paraphrase of the verse); and a close that sends the
  viewer to the full story. At least 40 % of the narration words are ours, not the quotation. `publish_episode.py`
  refuses a Short from part 6 on that breaks any of this (`short_problems`); parts 1-5 stay as published. Each ends with the next part ("Part N+1 tomorrow: ...") and, once the arc's long exists,
  points to it ("The full story is on the channel"); its first comment links the long, and the Studio "related video"
  of every Short in the arc is set to the long.
- **Long (the room; target at least 48 hours apart after the first qualified release):** the whole arc in 14-18 min (render limit 200 min; winners 11-47 min), the same
  voice, picture style, title formula and thumbnail look as its Shorts, so a viewer who liked the Short recognises
  it. Structure: cold open on the arc's peak moment (0:00-0:30, the Short's hook shot), the story narrated from the
  KJV with plain connecting narration, one chapter per Short episode (chapters = the Short titles), a re-hook
  before each chapter, a short reflection, a closing prayer, and "next story: ..." (the next arc's first Short).
- **Back link:** the long's description lists its Shorts and the next arc; the next arc's Shorts link back to it.
  Automatic (owner, 2026-10-26): `arcs.json` lists each arc's 4 Short episodes, its long's pilot and the next arc;
  `publish/arc_links.py` (`arc-links.yml`, dispatched by the heartbeat when `arc_links.py todo` finds work) waits
  until the long is public, then makes each public Short's first description line "▶ The full story:
  https://youtu.be/<long>" (rest and disclosure lines kept), posts one comment linking the long on each Short,
  and ends the long's description with "▶ This story in Shorts:" (titles and links) and "Next story:" once the next
  arc's first Short is public; every change in `publish/arc_links_ledger.json`. The Studio "related video" and
  pinning that comment are not in the Data API: the one manual step (OPERATIONS.md). Set `long.pilot` in
  `arcs.json` when each arc's long pilot is created.
- **Same pattern both ways:** title formula `<story or question> <emoji> | <Story>, Bible Story (KJV)` (Short) and
  `<Story>: <human angle> | Genesis N-M Bible Story (KJV)` (long); same narrator voice; same visual anchors
  (PROMPT_GUIDE.md); the long's chapters reuse the Shorts' hook lines.

**Historical calendar (superseded by the conditional recovery above; these dates are not a current schedule).**
Prayer longs stopped, owner 2026-10-26: "stop the prayer videos; the channel is going in another direction". The long stands on its own: it follows its own
registered structure (`structures/bible-story-long.json`, gate in `script.gate`: 14-18 min, a character speaks the
conflict in the first 30 s, >= 6 re-hooks, the climax at 0.6-0.85, the Keeper in every long, <= 25 % and never in the
cold open, no burned captions); traffic from its Shorts is only a plus. `ops/runway.py` counts these slots (a
script counts once the full `script_check` passes; a prayer long still scheduled alerts PRAYER_LONG_SCHEDULED).
| Arc | Shorts (episodes) | Shorts dates | Long | Long slot |
|---|---|---|---|---|
| prayer (stopped 26/10) | - | - | 013 night (public); 014 morning (its slot passed before the stop: the hold leaves it if public); 008 night held by `channel-privacy.yml` unschedule (`channel/hold-plan.json`) | 26/10 00:00, 26/10 10:00; 27/10 00:00 withdrawn |
| 1 In the beginning | 1-4 (Gen 1-3) | 24-25/10 | Creation, Eden and the Fall | 28/10 22:00 (owner 28/10 ~11:10Z, "o longo tem que sair HOJE": story QA v5, DECISIONS.md) |
| 2 Brothers and the walk with God | 5-8 (Gen 4-6) | 26-27/10 | Cain, Abel and the days before the Flood | 31/10 10:00 (owner 28/10: every other day after arc-01 on 29/10) |
| 3 The Flood | 9-12 (Gen 7-11) | 28-29/10 | Noah, the Flood and the rainbow | 02/11 10:00 |
| 4 Abram | 13-16 (Gen 12-19) | 30-31/10 | The call of Abraham | 04/11 10:00 |
(The episode table below is cut into arcs of four in order. Future dates require the qualified re-anchoring above.)

**Production.**

- Use the current source direction above. The Agnes direct route is retired; Buzzy standby is not a generation
  authorization, and a provider failure does not authorize spending or an unqualified substitute.
- Shorts (from part 7, owner 2026-10-26): produced by `episode.yml` from a plan (`plans/<episode-id>.json`, PROMPT_GUIDE
  "Keeper + acted scenes", Shorts v2): the conflict opens spoken by a character or God's voice, the characters speak
  their own lines lip-synced, the story acted coherently in qualified sources, the Keeper only for the insight and the close, composed by the engine, no vidIQ credits; the designated executor writes the plan and records the true reviewer identity before
  `publish-episode.yml`. (Parts 1-5 used vidIQ voice, stock search and compose, about 45 credits each.)
- Voice: use the supported existing Pavo/Kokoro routes, exact character voice bindings and the pinned narrator
  `am_michael`; God uses `am_onyx`. Preserve accepted audio and qualify changed lines by measured timing.
  Historical vidIQ balances or per-video estimates are not current spending authorization.
- Long: one per arc of `arcs.json` (arc-01 = Genesis 1-3, Shorts 1-4). How it is planned, built, measured and
  published is `LONG_DESIGN.md` only (owner, 2026-10-26: the Keeper narrating, the same characters as the Shorts;
  owner, 2026-10-27: "Libera o pavo no longo").
- Measured each day by the live intelligence: views of each long from Shorts, long retention, subscribers per arc.

## Capacity and spending

Use observed completions and current free readback, not historical balances, to estimate throughput. Pavo's
shared quota and unread-job stop still apply; a zero quote does not prove available generation capacity.
Existing vidIQ limits and its ledger remain ceilings, not permission to resume paused paid calls. No new spending.

## Episodes (Genesis; KJV ranges)
| # | Story | KJV | Hook moment for AI |
|---|---|---|---|
| 1 | In the beginning (published) | Gen 1:1-31 | light breaking over the deep |
| 2 | The garden of Eden | Gen 2:4-25 | a river parting into four in a green valley |
| 3 | The serpent and the fruit | Gen 3:1-7 | a single fruit on a dark branch |
| 4 | Driven out of the garden | Gen 3:8-24 | a flaming sword before a garden gate |
| 5 | Cain and Abel | Gen 4:1-16 | two altars, one smoke rising, one falling |
| 6 | Enoch walked with God | Gen 5:21-24 | a lone path into bright clouds |
| 7 | God sees the earth corrupt | Gen 6:5-13 | storm clouds gathering over a city of tents |
| 8 | Noah builds the ark | Gen 6:14-22 | a huge wooden hull in a dry valley |
| 9 | The flood | Gen 7:11-24 | rain falling on endless water |
| 10 | The dove and the olive leaf | Gen 8:6-12 | a dove flying back over still water |
| 11 | The rainbow covenant | Gen 9:8-17 | a rainbow over a washed land |
| 12 | The tower of Babel | Gen 11:1-9 | a brick tower rising into clouds |
| 13 | The call of Abram | Gen 12:1-9 | a caravan setting out at dawn |
| 14 | Count the stars | Gen 15:1-6 | a night sky full of stars over a tent |
| 15 | Three visitors at Mamre | Gen 18:1-15 | three figures on the horizon at noon |
| 16 | Sodom and Lot's wife | Gen 19:15-26 | fire falling on a distant plain |
| 17 | Isaac is born | Gen 21:1-7 | a lamp lit in a tent at night |
| 18 | Abraham and Isaac on the mountain | Gen 22:1-14 | a ram caught in a thicket |
(continues through Genesis 50, then Exodus.)

## Each episode before compose (PROMPT_GUIDE.md "Built for 9.5")
script from the KJV + one original line of reflection + one-line prayer -> `kjv_check.py` -> voice -> word timings -> every clip
previewed against the words over it -> AI prompt by the five-part guide -> compose -> frame-sheet review >= 9.5 ->
episode record -> publish-episode.yml.
