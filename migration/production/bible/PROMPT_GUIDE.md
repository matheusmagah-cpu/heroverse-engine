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
- **People and God.** No face of God. Biblical people only when the story needs them, then from a fixed reference
  image (character sheet) so the same face returns in every episode.

## Cheap preview before paid video
1. Write the prompt with the five parts.
2. Make the first frame as a still first (free: Cloudflare FLUX; the Runway connector is not used, CLAUDE.md) and look at it.
3. If the still is right, send it as Pavo's `first_frame` (vidIQ: `startFrameB64`) and prompt only the motion and the
   camera (do not re-describe the picture: two descriptions of one subject drift). Light, dust and particle moments
   always start from a checked still.
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
  clip's last frame (<= 1.3 s) for the gap or the closing tail. A talking line is 3.23-11.55 s. The request binds
  the reference and the audio: "Image 1 is the narrator" (or the character's name) and "speaks the words of the
  audio clip, his lips moving in sync with the voice" (`bind_prompt`, replacing "speaks to the camera, his lips
  moving clearly with every word"), and Image 1 is the speaker's `talk_refs` speaking frame when it has one (the
  Keeper: his calibration clip's frame; the mouth-closed front view failed the lips, -0.043).
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
180 s Shorts limit). plan_check estimates at 2.75 words a second (Kokoro, measured on Genesis 7 v2); the band is
narrow, so the measured length in `episode_build lines` decides; measure a new plan locally (`pilot_render.py voice`)
before dispatching. Genesis 7 v2: 466 words, 24 lines, estimate 174.3 s, measured 173.9 s.

**The checks, in order** (each stops the run): `plan_check.py --strict` (KJV word for word, the Short rules on the
estimated length, every rule above; the Keeper while DRAFT is one pending row) → Kokoro line by line, each line in its
speaker's voice; the measured Short 170-179 s, Keeper <= 25 %, lesson <= 25 %, each talking line retimed into its clip (E95) → references
sha256-checked → every shot one Pavo generation at a fresh exact 0-credit quote; `clip_check.py` on every clip,
`lipsync_check.py` (our line in the clip's audio, lips in sync) on every talking clip (the Keeper, a character
speaking); a failed shot is a NEW generation at most 2 times, then the run fails naming the shot → compose (a talking
clip's picture spans exactly its line's audio, from the start of its clip at normal speed, its last frame held for the
gap or tail; `short_engine.talk_problems` refuses it off its line) → `clip_check.py --composed`, loudness -14 +-1 LUFS → 20-frame sheet and per-shot report for
Claude's review at 9.5.
