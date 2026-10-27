# AI video prompts for the Bible-story series (owner, 2026-10-24: "the secret is the prompt; no credit wasted")

AI video comes from Pavo first (Agnes Flash, 720p, 4-12 s, exact zero-credit quote; owner 2026-10-25), then Agnes
direct, then vidIQ (~15 credits/s veo-3.1-lite 1080p to ~23 credits/s minimax-h3 2k) only when both fail. Shorts are
almost all AI; every scene still shows its words. A Pavo clip costs no credits but a miss costs a slot, so every
prompt passes this guide before it is sent. Pavo clips carry an audio track even with no audio asked: strip it (`-an`).

## Structure (Google's Veo formula, five parts, in this order)
1. **Cinematography**: shot size, lens feel, ONE camera move ("slow push-in", "static wide", "low tracking shot").
2. **Subject**: the one thing on screen, concrete and physical.
3. **Action**: ONE dominant action, described as what physically happens.
4. **Context**: place, time of day, weather, light source.
5. **Style and ambience**: one style anchor ("photorealistic nature documentary") and the mood.
Then: duration and aspect come from the tool fields, not the text.

## Rules learned (with the clip that taught it)
- **Write physics, not metaphor.** "Light tears open the darkness… the water catching fire with light" produced a laser
  beam striking the sea with sparks, smoke and fire (job_4a79d62e, 60 credits wasted). "The clouds slowly part and
  wide soft sunbeams pour down, spreading gentle light across the water" produced exactly the intended shot
  (job_ebf7f7b2).
- **Say what IS there; avoid listing what is not.** Veo 3.1 has no reliable negative field; naming "fire, smoke,
  explosion" can prime them. Write the positive version ("natural sunlight only, soft mist"). Keep only the short
  standard tail: "No people, no text, no logos."
- **Particles in a light shaft read as fire.** "Fine reddish dust swirls upward into a shaft of morning sunlight"
  produced a glowing orange column like flames (job_8a50c757, 60 credits). Veo Lite turns glowing particles, beams and
  embers into fire; a dust or light moment starts from a checked still (image-to-video) or from real footage.
- **One action, one camera move per clip.** Two moves or two events give unstable, jittery output.
- **Name the motion.** A prompt about stillness returns a frozen-looking clip; say what moves (mist gliding, ripples,
  clouds parting).
- **Real-world phenomena look real.** Sunbeams through clouds, mist on water, an eagle in flight read as footage;
  invented spectacle (beams of power, glowing portals) reads as cheap CGI.
- **State the period in every scene (E108).** genesis-07 run 40341856955 asked for "a torch-lit lane", "the road out
  of the city", "a dusty lane", "a quiet room" with no age named, and got a cobbled European street with a man in a long
  coat and a glass kerosene lantern, a town with church towers, a stone village with chimneys, a peaked cap, glass jars
  (8 of 30 scene shots). Every scene prompt (God's voice-over and a speaking character's shot too; not the Keeper; the
  long's scenes too) carries its story's period word for word before the standard tail: for Genesis before the flood
  `plan_check.PERIOD_SETTING` "The ancient Near East before the flood: only goat-hair tents, open fires and torches on
  the open plain." and `PERIOD_EXCLUDE` "No stone buildings, towers, churches, glass lanterns, modern clothing or
  roads." (SCENE_PERIOD_MISSING). With both sentences taken out it names nothing the period excludes
  (`PERIOD_AVOID`: city, lane, room, table, street, road, building, brick, wall, house, dome, tower, church, town,
  village, lantern, coat, hat, peaked cap...: SCENE_PERIOD_CONFLICT); say "a camp of tents", "a path between the
  tents", "inside a goat-hair tent", "a dusty track across the open plain", "a clay oil lamp". The period is the plan's
  `period` (a preset: `eden`, `before-the-flood`, `the-flood`; or its own setting and exclusions, a malformed one is
  PERIOD_INVALID) or its passage's (Genesis 1-3, 4-6, 7-9); a passage across two periods is PERIOD_AMBIGUOUS until the
  plan sets one. Probed before genesis-07's rebuild (`evidence/pavo/20261026/period/probes.json`): "tents, mud-brick
  and the open plain" put a mud-brick tower or a domed tower behind 4 of 8 probes; "...clay lamps, fires and torches"
  none, but a small metal-and-glass candle lantern in 3 of 11 night shots; "...open fires and torches" none of either
  in the probes that followed. Look for a stray prop on the frame sheet anyway; `episode.yml` `regenerate` redoes that
  shot alone.
- **The ark has one look (E113).** genesis-08 run 40438106839 lost 7 of 29 shots at the frame review because each
  prompt described the ark in its own words ("a huge wooden frame", "the distant hull", "the towering hull"): a
  longship with a spiked prow, a steamship with a smoking funnel, a galleon, a round vat, separate rib arcs; genesis-09's
  probes drew sailing ships, a barn, a dome and a red waterline band. Every scene prompt that names the ark (ark, hull,
  keel, ship, boat, vessel; the flood's period sentence does not count) carries `plan_check.ARK_LOOK` "The ark is one
  long, low, box-shaped wooden hull with straight sides of rough planks and flat square ends, the same low height from
  end to end." and `ARK_EXCLUDE` "The ark has no mast, sail, prow, figurehead, funnel or smokestack, no smoke rising
  from it and no band along its waterline." word for word (ARK_LOOK_NOT_CANONICAL), and names no ship, boat, mast,
  sail, prow, funnel or curved sides beside them (ARK_LOOK_CONFLICT). The shot's own words say only its state ("the
  half-built ark ... a row of bare upright ribs along its top", "the vast finished ark, its whole hull smeared
  pitch-black under a flat plank roof"), never its shape again. Light it from the side or show it from above: a hull
  silhouetted against a bright sky drew curled ends in every probe that tried it. (Parts 1-8; from part 9 the next
  rule replaces it.)
- **From part 9 the ark is named in positive words only (E123; the ark's stories only: Genesis 4-10, periods before-the-flood and the-flood; Jonah's ship or a fishing boat elsewhere stay as they are).** With the ark's approved references sent, E113's two
  sentences still drew curved bows, cabins and smoking funnels (genesis-09 run 2026102704): an image model reads "no
  mast, sail, prow, funnel or smokestack, no smoke rising" as a list of things to draw, and "ark"/"hull" pull its ship
  prior. Probe (`evidence/pavo/20261027/genesis-09-ark-probe/`): E113's wording with the references 0 of 3 held the
  box; the positive phrase with the references 3 of 3; the phrase without references drew a crate or shed at the wrong
  scale. Every scene, still and thumbnail prompt that shows the ark names it only as `plan_check.ARK_PHRASE`, word for
  word, inside the shot's own sentence: "a giant long rectangular wooden crate of rough planks smeared pitch-black, with
  a flat plank roof and flat square ends, as tall at both ends as in the middle" (a capital first letter at a
  sentence start). No prompt says ark, hull, keel, ship, boat, vessel, barge, mast, sail, prow, figurehead, funnel,
  smokestack, "no smoke" and the like (`ARK_WORDS`, ARK_LOOK_CONFLICT), even negated; "crate" without the phrase is
  ARK_LOOK_NOT_CANONICAL. The flood's period sentence names no ark: "The ancient Near East in the days of the flood: the
  open water, the mountains of Ararat and the empty new earth." A still with the phrase is made with the ark's
  references; a still without it needs none and shows none. No word list closes every synonym (galley, deck, floating
  box and enclosure are refused too; "bow" never, Genesis 9:13): the 9.5 frame review stays the final guard. People near it, in positive words: "the roof is empty and
  flat" (not "nobody on the roof"), and a crowd "seen from behind, faces turned away toward the crate".
- **People and God.** No face of God. Biblical people only when the story needs them, then from a fixed reference
  image (character sheet) so the same face returns in every episode.

## Cheap preview before paid video
1. Write the prompt with the five parts.
2. Make the first frame as a still first (free: Cloudflare FLUX; the Runway connector is not used, CLAUDE.md) and look at it.
3. If the still is right, send it as Pavo's `first_frame` (vidIQ: `startFrameB64`) and prompt only the motion and the
   camera (do not re-describe the picture: two descriptions of one subject drift). Light, dust and particle moments
   always start from a checked still.
   In the engine (owner, 27/10, "image first"): the still's prompt goes in `bible/stills/<still-id>.json` (status
   DRAFT; the static composition, the period sentences and, when it shows the ark, the ark sentences word for word),
   the shot gets `"first_frame": "<still-id>"` (optional `last_frame`; a scene with no characters and no input audio)
   and a motion-and-camera prompt. `scene-stills.yml` (plan, shots, candidates 1-3) makes the candidates on the free
   FLUX allocation at 9:16 and pushes them with a contact sheet to `claude/stills-<episode>-<run>`; after Claude's
   review `scene_stills.py approve <still-id> <candidate-id> --score S --note TEXT` records it APPROVED with its sha256,
   by PR. plan_check refuses a missing, unapproved or changed still (STILL_*), and the request digest carries the
   still's sha256, so a new still is SHOT_REQUEST_CHANGED.
4. One generation per shot. A miss is diagnosed against this guide before any retry, and the lesson is added here.

## Template
"Photorealistic [style anchor], cinema camera. [Shot size], [one camera move]. [Subject] [one physical action].
[Place, time, weather, light source]. [Mood in two words]. No people, no text, no logos."

## Cost log (credits)
| job | model | s | credits | result |
|---|---|---|---|---|
| job_757c6775 eagle at dawn | minimax-h3 2k | 6 | 140 | good |
| job_4a79d62e first light (metaphor prompt) | veo-3.1-lite 1080p | 4 | 60 | MISS: laser and fire |
| job_ebf7f7b2 first light (physics prompt) | veo-3.1-lite 1080p | 4 | 60 | good |
| job_02862131 Spirit over the waters | veo-3.1-lite 1080p | 4 | 60 | good |
| job_de8873e3 the first man at dawn, from behind | veo-3.1-lite 1080p | 4 | 60 | good |
| job_8a50c757 dust rising into sunlight | veo-3.1-lite 1080p | 4 | 60 | MISS: read as fire |

## Built for 9.5 before compose (owner, 2026-10-24: "a 9.5 needs a structure made for 9.5")
Genesis 1 (part 1) scored ~8 because nothing checked the clips before the compose. Every episode now passes, in
order, before any paid compose:
1. Every stock clip is looked at (its preview frame), not chosen by its text description: no modern objects (cars,
   aquariums, ski gear), no modern people, the subject inside the 9:16 center crop.
2. Each clip matches the exact words over it (the moon on "the moon", not a black frame).
3. Captions large for Shorts (about 7 % of the frame height), loudness about -14 LUFS.
4. The frame sheet of the composed file is reviewed before publication; any frame below 9.5 is fixed first.
5. Every downloaded candidate passes `clip_check.py CLIP...` (no black start or end, short side >= 720, >= 24 fps)
   before it goes into a compose.
6. Scene changes use `"transitionIn": {"kind": "cut"}`. Tested 2026-10-24: vidIQ's "fade" and "wipe" start the
   incoming scene from black, which flashed 1-2 black frames at every faded change of Genesis 2-4; "dip_to_black" only
   where the black is meant (into the prayer, the close).
7. The composed file passes `clip_check.py --composed FILE <intended dip seconds>` (no black anywhere else) before the
   review; its result goes into the episode record (`review.black_check`).
8. Before the voiceover, every Scripture line of the narration goes into the episode record as
   `"scripture": [{"reference": "Genesis 4:9 (KJV)", "text": "..."}]` and passes `kjv_check.py EPISODE.json`: the
   KJV word for word (`kjv/kjv.tsv.gz`, 1769 text). A misquote is paid for in voice and compose credits.
9. From part 6 on (owner, 2026-10-25), the whole narration goes into the record as `narration` (kind scripture,
   story, insight, cta) and `publish_episode.short_problems` passes before the voiceover: 62-90 s (part 6; 170-179 s from part
   7, below), at least 40 % of
   the words ours, one insight of at least 20 words of our own reading of the passage, a close that names the full
   story. A Short under a minute does not count for TikTok Creator Rewards; a Short that only reads the verse over
   stock footage reads as reused content on both platforms.

## Characters stay the same in every video (owner, 2026-10-25)
"If Moses appears once, he is the same Moses a hundred videos later." `production/characters/characters.json` is the
character bible: each person or creature has a fixed `look` (exact words), `wardrobe` variants for the story phase, a
FLUX `seed` and a `status`. Before a character's first scene:
1. Its reference sheet (front, three-quarter, full figure) is generated with `cf-images.yml` (pilot `characters`) from
   `characters/images.json`, and Claude reviews it (same face in all three, period-true clothing, no modern object).
   Only then is its status set to APPROVED, by PR.
2. Every still prompt that shows it carries its `look` word for word plus one `wardrobe` variant, and reuses its seed.
3. Every AI clip that shows it uses reference mode (Pavo `references`, else `agnes-clip.yml` input `characters`): the
   approved reference images go in (at most 5) and the prompt carries the look; `characters.py` refuses an unapproved character
   or a changed look before any call.
4. A new character joins the bible the first time a story needs it, never improvised inside one episode.
God the Father is never shown as a person: light, wind and voice carry Him, and the KJV text speaks.


## Keeper + acted scenes: the measured grammar (Shorts v2, owner 2026-10-26)
The mining of 26/10 (`structures/bible-story-short.json`, 6 winners from 6 channels, 3 weak contrasts) measured what
the winning Bible-story Shorts do, and the owner set the grammar from it (DECISIONS.md 2026-10-26 "Shorts v2"): the
conflict opens, spoken by a character; the characters speak their lines lip-synced; the Keeper (our own hypothesis:
no winner has a host on screen) comes only at the close; 170-179 s. Claude writes only the plan; `episode.yml` does
the rest and nothing is published before Claude's review.

**The plan** (`plans/<episode-id>.json`, `bible-plan-v2`): the `narration` records (kind story / scripture / insight /
cta, the ones `publish_episode.short_problems` reads) and the `shots` in order. The voice track is the shots' words in
order (`plan_check.sequence`): the narration lines they carry, in the Keeper's voice (`am_michael`), and each
speaking shot's own `line` where that shot is, in its speaker's own voice.
- **Open (0-3 %): the conflict, spoken.** The first shot is a scene whose spoken line starts at 0 s: a character's
  challenge or plea, or God's voice; the KJV line where the text has one. Never the Keeper, never narration first,
  no atmosphere or title card.
- **Spoken lines.** A scene shot carries `speaker` and `line` (+ `reference` when it is Scripture: KJV word for word,
  kjv_check). A character speaker is APPROVED, has its `voice` in characters.json (Adam am_fenrir, Eve af_heart, the
  serpent bm_fable, Noah bm_george), is in the shot's `characters` (look word for word), and the prompt says it
  speaks, lips moving with every word; its line (2-12 s) goes to Pavo as input audio with its references and
  `lipsync_check.py` judges the clip like the Keeper's; the clip's length comes from the line (no `seconds`).
  `speaker: "god"`: Scripture only; the shot shows no person, no figure, no face (light, storm, wind, fire, rain), its
  `seconds` are the clip's, and the line is a deep voice-over (`am_onyx`, speed 0.9; no lipsync check). Its
  generated clip goes through the same face landmarker (`lipsync_check.py --faces`, sampled frames): any face is
  `GOD_SHOT_FACE` and the shot is regenerated (at most 2 times), because a prompt can be written around a word list.
- **Scripture is always referenced.** A line with no `reference` that quotes the KJV anyway (8 consecutive words) is
  refused (`KJV_UNREFERENCED`) and counts as Scripture, not our words.
- **Talking clips keep our audio (E95, `evidence/pavo/20261026/keeper-audio-binding.json`).** Pavo keeps the input
  audio only when the clip it is asked for is at most ~0.65 s longer than the speech (6.385 s line: 7 s clip audio
  0.80, 8 s 0.36, 10 s 0.03); at 1.6 s or more it makes its own track. So a talking clip is ceil(speech) seconds
  (4-12), the speech 0.25-0.65 s shorter: `episode_build lines` retimes a line that misses it to N - 0.45 s (atempo,
  pitch kept, at most +-10 %, else `TALK_LINE_RETIME_OVER`) before anything is laid out, and the compose holds the
  clip's last frame (<= 1.3 s) for the gap or the closing tail. A talking line is 3.23-11.55 s (one ceiling,
  `TALK_LINE_MAX`, the closing Keeper too), never ~3.94-4.14 s at any pace from the normal to the slowest
  (`TALK_LINE_UNREACHABLE`: no clip within 10 %), so a single talking line has at least 12 words. The request binds the reference and the audio: "Image 1 is the narrator" (or the character's name) and "speaks the words of the
  audio clip, his lips moving in sync with the voice" (`bind_prompt`, replacing "speaks to the camera, his lips
  moving clearly with every word"), and Image 1 is the speaker's `talk_refs` speaking frame when it has one, sent in
  place of its approved refs (the Keeper: his calibration clip's frame, alone as in the tests that passed; the
  mouth-closed front view failed the lips, -0.043).
- **Stake and open loop (3-10 %)**, then **escalation (10-60 %)**: three rising steps of the opposition, acted (in
  dialogue when an approved speaker lives in the story), each ending on a small hook; shots 2-6 s, cuts only.
- **Climax (60-80 %)**: the hero or God speaks the key KJV line at the turn; at least one acted scene is flagged
  `climax: true`, with people on screen (approved characters or anonymous figures): never a landscape, the Keeper or
  God's voice-over sky (E92: when God speaks the turn, the climax is the acted shot right after His line).
- **Payoff (80-85 %)**: the outcome shown, one beat.
- **Keeper close (85-100 %)**: `keeper` shots only after the last climax shot and only for lines of kind insight or
  cta: one original insight from the text (>= 20 words, no sermon), a comment question, the CTA to the full story and
  "Part N+1 tomorrow: ...". He closes (the last shot); his prompt carries his `look` and one `wardrobe` variant word
  for word and says he speaks; each Keeper line 3.23-11.55 s, retimed to its clip (E95; the tail is a held frame).
  He faces the lens on a still frame: "static camera" and "holds his head level, looks straight into the camera"; no
  push-in, pull-back, tracking, orbit, lean or bow (`KEEPER_POSE`, E98: those lost the face or the lips).
  Keeper <= 25 % of the Short; the lesson (insight + cta lines + every Keeper second) <= 25 % (gate), aim <= 15 %
  (the winners: 0-28 %, the weak Noah Short 41 %).
- **Scenes**: `seconds` 4-12 of Pavo video, the five-part prompt above, `characters` APPROVED with their look word for
  word (<= 5 references). No character yet? Anonymous people seen only from behind or in silhouette (`figures:
  "anonymous"`, the prompt says so; a DRAFT character such as Noah only that way, no face) or an `establishing: true`
  landscape held <= 2 s, all of them <= 15 %. Consecutive scene shots may share a narration line; a spoken line
  between them would cut it in two, so it is refused.
- God the Father is never a figure: a prompt that names Him shows only light, wind, fire or a voice, never a body,
  face, hands, robe or throne (best: do not name Him in a prompt at all; show what He does).

**Length: 170-179 s from part 7** (5/6 winners ran 170-179 s, 0/3 weak; measured with the tail, below YouTube's
180 s Shorts limit). plan_check estimates the narration at 2.75 words a second (Kokoro, 2.756 measured over the
genesis-07 to 10 Shorts) and each speaker's line between its voice's two measured bounds (`voice_pace.py`, E104): the
fastest run for a line too short (God in a Short 3.072, Adam 3.975, Eve 3.732, Noah 2.970, the scoffer 3.579, the
serpent 2.728) and the slower of the slowest run x 2.25/2.75 and the slowest line for a line too long or unreachable. A
talking voice not in it is VOICE_PACE_UNMEASURED. One talking line that reaches a clip at every pace between them: the
Keeper and the serpent 12-25 words, Noah 13-27, the scoffer 15-32, Eve 16-32, Adam 17-35 (a character's 12 words would
be ~3.2 s, under the 4 s clip). The band is narrow, so the measured length in `episode_build lines` decides; measure a
new plan locally (`pilot_render.py voice`) before dispatching. Genesis 7 v2: 466 words, 24 lines, estimate 172.8 s,
measured 173.8-173.9 s.

**The checks, in order** (each stops the run): `plan_check.py --strict` (KJV word for word, the Short rules on the
estimated length, every rule above; the Keeper while DRAFT is one pending row) → Kokoro line by line, each line in its
speaker's voice; the measured Short 170-179 s, Keeper <= 25 %, lesson <= 25 %, each talking line retimed into its clip (E95) → references
sha256-checked → every shot one Pavo generation at a fresh exact 0-credit quote; `clip_check.py` on every clip,
`lipsync_check.py` (our line in the clip's audio, lips in sync) on every talking clip (the Keeper, a character
speaking); a failed shot is a NEW generation at most 2 times (5 for a talking clip, E98), then the run fails naming the shot → compose (a talking
clip's picture spans exactly its line's audio, from the start of its clip at normal speed, its last frame held for the
gap or tail; `short_engine.talk_problems` refuses it off its line) → `clip_check.py --composed`, loudness -14 +-1 LUFS → 20-frame sheet and per-shot report for
Claude's review at 9.5.

## Keeper voice-over: the owner-approved fallback (plan B, owner 2026-10-26)
The owner's decision for genesis-07 (26/10, as relayed): "If the last test fails, genesis-07 publishes 27/10 13:30 UTC
with the Keeper ON SCREEN at the close in calm, mouth-closed shots: looking into the fire, closing the scroll, looking
at the camera at the very end. His narration plays as a voice-over, so nobody appears to speak with a still mouth and
there is no wrong lip sync. The check must confirm that no mouth is talking in those shots." The test failed: his
lip-synced lines passed 1 time in 45 (PR #419, `evidence/pavo/20261026/keeper-line-length.json`).

An explicit, opt-in plan mode; a Keeper shot without the flag still talks, lip-synced, as above.
- **The plan:** a `keeper` shot may carry `"voiceover": true` (a keeper shot only, true or false, else
  `VOICEOVER_FIELD`). It is not a talking shot: no input audio, no `TALK_*` retime, no `KEEPER_POSE`. Its prompt says
  his mouth stays closed ("his lips closed, silent") and names no speech (speaks, talking, says, lips moving, words,
  audio...), else `KEEPER_VO_PROMPT`; he faces the lens on a static camera ("static camera", "looks straight into the
  camera"; nothing that turns his eyes or head off the lens: looking or glancing down, into or at the fire, flames,
  embers or scroll, eyes on the flames, eyes raised from the fire, head bowed, lowered eyes, profile, reading the
  scroll, push-in or lean), else `KEEPER_VO_POSE`. His character entry needs a `talk_refs` frame, else
  `KEEPER_VO_NO_TALK_REF` (also refused by `episode_build refs` and the request: never the front view in its place).
  His `look` and one `wardrobe` variant stay word for word; Keeper <= 25 %, lesson <= 25 %, only after the climax,
  never opens, closes: all count these shots. His line is narration in am_michael carried by the voice track, at
  least 2.0 s (`VO_LINE_MIN`, the floor `episode_build lines` holds a Keeper line to). One helper,
  `plan_check.vo_cover`, gives what his clip covers besides the line, by the compose's own run logic: the 0.35 s gap
  before it when a talking shot comes first, and the 0.35 s gap or the 1.2 s closing tail after it. plan_check (at
  the slowest pace), `episode_build lines` (measured) and the compose all cap that whole time at 15.6 s (one 12 s clip
  slowed 1.3), and the clip is ceil(it) seconds, 4-12 (`vo_clip_seconds`). The long has no voice-over path yet:
  `LONG_VOICEOVER_UNSUPPORTED`.
- **The build:** the request sends his `talk_refs` frame alone (else his approved refs), no audio, no speech clause;
  Pavo's audio is stripped. `lipsync_check.py --still-mouth` (the same pinned landmarker and inner-lip opening as the
  lips check) flags `MOUTH_TALKING` when any 1 s of the clip moves fast (mean frame-to-frame change > 0.0063 of the
  face height; or the whole clip is wide and fast, the first rule), `MOUTH_NOT_CLOSED` when any 1 s after the first
  2.5 s is open (median > 0.013; the talking frame's open mouth may settle closed within those 2.5 s, no longer), and
  `FACE_NOT_FOUND` under 80 % of the frames, as for the lips; every measure goes into report.json; 6
  generations like a talking shot (`attempts_for`: Pavo is free and 1 in 6 passed before the prompts were settled),
  generated right after the talking shots (E99). The compose plays his clip unbroken from its 0 s over
  his line (slowed at most 1.3, never cut or held); his words and captions come from the voice track.
- **Why these rules** (`evidence/pavo/20261026/keeper-vo/calibration.json`, 14 direct 0-credit closed-mouth Pavo clips
  and 42 talking clips, their per-frame series in `opening-series.json`, replayed by test_lipsync_check): 42 talking
  clips (the Keeper's, passing and failing the lips alike, and the genesis-06 narrator) move 0.0091-0.026 in their
  fastest second and open 0.039-0.084 in their most open second after 2.5 s, all `MOUTH_TALKING`; the closed clips
  0.0005-0.0043 and 0.0011-0.0046. A whole-clip mean (the first rule) would let 2.5 s of talking in a 12 s clip pass,
  and a still open mouth passed it (review of #423). With the mouth-closed front reference his face was found in
  2-27 % of the frames (4 of 4 `FACE_NOT_FOUND`, whatever the gaze or light); with his talking frame facing the lens,
  100 %, the mouth settling closed within 2.5 s from the reference's open mouth and staying closed (spread 0.041,
  motion 0.0006: passes); looking down into the fire, 17 % (`FACE_NOT_FOUND`). So the owner's "into the fire" and
  "closing the scroll" are the fire beside him and the scroll rolled closed while he faces the camera.
- **genesis-07 is built this way:** `plans/genesis-07-short.json` now has its three Keeper shots as voice-over (prompts
  rewritten, lines unchanged); every scene and God shot is byte-identical to the plan run 40307414749 built from
  (commit 1c1ed79, tested), so its resume keeps the 30 clips (E93: the same request). Each Keeper prompt was probed as
  the build sends it before the build (2 direct 0-credit clips each, `calibration.json` "build_probes"): k-question 2/2,
  k-close 2/2 (word for word the clip that first passed); k-insight 0/2 with "his eyes sad and kind, breathing slowly
  as the flames flicker beside him" (face 0.68, 0.60), 2/2 once rewritten as clip 5 ("a calm kind look, breathing
  slowly"). Rule from it: a voice-over Keeper prompt stays close to the passing wording; a new one is probed first.
  Measured locally with Kokoro: 173.8 s (the Keeper's lines no longer retimed), Keeper 11.0 %, lesson 11.4 %.
