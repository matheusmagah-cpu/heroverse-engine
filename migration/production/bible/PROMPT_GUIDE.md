# AI video prompts for the Bible-story series (owner, 2026-10-24: "the secret is the prompt; no credit wasted")

AI video costs ~15 credits/s (veo-3.1-lite 1080p) to ~23 credits/s (minimax-h3 2k). It is used only for the hook and
the story's peak moments; everything else is licensed footage or animated stills. A clip that misses is paid anyway,
so every prompt passes this guide before it is sent.

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
3. If the still is right, send it as `startFrameB64` and prompt only the motion and the camera (do not re-describe the
   picture: two descriptions of one subject drift).
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
