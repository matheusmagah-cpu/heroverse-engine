# The Bible, story by story (KJV): series plan (owner, 2026-10-24)

Owner: one micro-story at a time from Genesis, narrated from the KJV (public domain), cinematic and never still, AI
video only at the hook and the story's peak, finishing with a short reflection and a prayer. Shorts feed long videos.

## One format, two lengths: the Shorts lead to the long (owner, 2026-10-25)
Owner: "o que está pronto, mantém; a partir desse momento passa para a ideia do short ... o short tem que seguir o
padrão do longo e o longo do short ... o short direcionar pro vídeo longo; monta uma estratégia efetiva".

**Why (measured 2026-10-25, DECISIONS.md day 8 and evidence/vidiq/20261025):** Genesis 1 and 2 Shorts reached 107
and 192 views in their first day (breakout 14 and 48); the prayer long videos 8-96 views each. The long-form winners
of this line (7 channels, 8x-589x their channel) tell ONE Bible story per video in 11-47 min, titled
"<story>: <human angle> | Genesis N Bible Story".

**The funnel.**
- The Bible is told in **arcs**: one arc = one complete story = 4 Short episodes = 1 long video.
- **Shorts (the door, 2 a day, 13:30 and 23:30 UTC):** one moment of the arc each, in order, 170-179 s from
  part 7 (owner, 2026-10-26: the measured driver of `structures/bible-story-short.json`, 5/6 winners vs 0/3 weak; under
  YouTube's 180 s limit, the tail included; parts 1-6 stay at their 62-90 s, TikTok Creator Rewards counting 1 minute or more), almost all AI video from Pavo (owner,
  2026-10-25; each scene matches its words). Built in four
  beats, recorded line by line in the episode's `narration` (kind scripture / story / insight / cta): the hook; the
  moment told in the KJV with our own retelling around it; one **insight** of our own (what most readers miss, a
  tension in the text, a critique of a common reading; never a paraphrase of the verse); and a close that sends the
  viewer to the full story. At least 40 % of the narration words are ours, not the quotation. `publish_episode.py`
  refuses a Short from part 6 on that breaks any of this (`short_problems`); parts 1-5 stay as published. Each ends with the next part ("Part N+1 tomorrow: ...") and, once the arc's long exists,
  points to it ("The full story is on the channel"); its first comment links the long, and the Studio "related video"
  of every Short in the arc is set to the long.
- **Long (the room, every other day):** the whole arc in 14-18 min (render limit 200 min; winners 11-47 min), the same
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

**Calendar (long slots at 10:00 UTC, one Bible-story long every 2 days; prayer longs stopped, owner 2026-10-26:
"stop the prayer videos; the channel is going in another direction").** The long stands on its own: it follows its own
registered structure (`structures/bible-story-long.json`, gate in `script.gate`: 14-18 min, a character speaks the
conflict in the first 30 s, >= 6 re-hooks, the climax at 0.6-0.85, the Keeper in every long, <= 25 % and never in the
cold open, no burned captions); traffic from its Shorts is only a plus. `ops/runway.py` counts these slots (a
script counts once the full `script_check` passes; a prayer long still scheduled alerts PRAYER_LONG_SCHEDULED).
| Arc | Shorts (episodes) | Shorts dates | Long | Long slot |
|---|---|---|---|---|
| prayer (stopped 26/10) | - | - | 013 night (public); 014 morning (its slot passed before the stop: the hold leaves it if public); 008 night held by `channel-privacy.yml` unschedule (`channel/hold-plan.json`) | 26/10 00:00, 26/10 10:00; 27/10 00:00 withdrawn |
| 1 In the beginning | 1-4 (Gen 1-3) | 24-25/10 | Creation, Eden and the Fall | 04/11 10:00 (moved from 28/10, owner 27/10: DECISIONS.md) |
| 2 Brothers and the walk with God | 5-8 (Gen 4-6) | 26-27/10 | Cain, Abel and the days before the Flood | 30/10 10:00 |
| 3 The Flood | 9-12 (Gen 7-11) | 28-29/10 | Noah, the Flood and the rainbow | 01/11 10:00 |
| 4 Abram | 13-16 (Gen 12-19) | 30-31/10 | The call of Abraham | 03/11 10:00 |
(then every 2 days: 4 Shorts, 1 long; the episode table below is cut into arcs of 4 in order.)

**Production.**
- AI video comes from Pavo first (free, exact zero-credit quote; DECISIONS.md 2026-10-25 "Pavo is the first source"),
  then Agnes direct, and vidIQ's generator only when both fail. Shorts are almost all AI (owner, 2026-10-25), each scene
  still matching its words; this replaces "AI video only at the hook and the peak".
- Shorts (from part 7, owner 2026-10-26): produced by `episode.yml` from a plan (`plans/<episode-id>.json`, PROMPT_GUIDE
  "Keeper + acted scenes", Shorts v2): the conflict opens spoken by a character or God's voice, the characters speak
  their own lines lip-synced, the story acted out in Pavo scenes, the Keeper only for the insight and the close, composed by the engine, no vidIQ credits; Claude writes the plan and reviews the sheet before
  `publish-episode.yml`. (Parts 1-5 used vidIQ voice, stock search and compose, about 45 credits each.)
- Credit budget: 3,811 credits on 25/10 must last to the renewal on 18/11 (about 159 a day). Two Shorts a day at
  about 100 each run over that, so each Short is held to about 75 (no wasted previews; music theme reused), and the
  long costs no vidIQ credits.
- Voice: the Shorts use ElevenLabs "George" through vidIQ (about 14 credits a minute: about 220 for a 16-minute long,
  which the budget cannot carry every other day). The long uses the engine's free Kokoro voice `am_michael`, the
  voice the frozen gate pins (`qa_pilot.voice_model_pinned`); a different Kokoro voice would mean changing a gate.
- Long: one per arc of `arcs.json` (arc-01 = Genesis 1-3, Shorts 1-4). How it is planned, built, measured and
  published is `LONG_DESIGN.md` only (owner, 2026-10-26: the Keeper narrating, the same characters as the Shorts;
  owner, 2026-10-27: "Libera o pavo no longo").
- Measured each day by the live intelligence: views of each long from Shorts, long retention, subscribers per arc.

## Credits (vidIQ: ~4,200 on 2026-10-24; renewal of 6,000 on 2026-11-18)
- Per Short: AI clips from Pavo (0) + voice (~14 a minute: ~20 for the 62-90 s of parts 1-6; from part 7 the voice is free Kokoro) + stock search (~8) + compose (~16) ≈ 45;
  a vidIQ AI clip (veo-3.1-lite 4 s, 60) only when Pavo and Agnes both fail.
- Ceiling 200 credits a day; the ledger records every call (owner authorization 2026-10-24: "libero tudo").

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
