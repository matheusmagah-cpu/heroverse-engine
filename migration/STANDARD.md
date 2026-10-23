# HeroVerse Production Standard v1 (2026-10-19)

> Scope (SYSTEM.md): execution rules of `structures/guided-prayer-scenic.json`, **validated 2026-10-19** (6 winners from 6 channels, 3 weak contrasts; `evidence/vidiq/20261019/structure_audit.json`). Measured **drivers**: continuous camera motion (R2; 6/6 winners vs 0/3 weak), a viewer-directed hook within 5 s (R7; 5/6 vs 0/3), and for night prayers a gratitude topic (2.08x median views, same channel). R1 (no figure), R4 (no caption box) and R6 (no persistent CTA) are **house choices on free attributes**: the market splits on them (3/6, 4/6, 4/6), and the two highest breakouts use the clean grammar. They are kept for a cleaner, more professional look, not claimed as drivers.

One standard. Every rule is measured on breakout videos (vidIQ, read-only) and is checked
before publication. Evidence: `migration/evidence/vidiq/20261019/`.

Benchmarks (spoken English prayer, published in the last 3 months, small channels):
- L1 `OuqwfEgNavE` "Psalm 91 Prayer for Protection": 4.8k subscribers, 237k views, breakout 2310, 14:17.
- L2 `fXhKzleJhxI` "Thank You, Lord, for Today": 1.5k subscribers, 68k views, breakout 1333, 5:47.
- S1 `DigF0F0LrfY` "Jesus, I Trust in You", a Short: 42.9k subscribers, 197k views, 2:58.

Across the 20 spoken-prayer outliers, the median channel has 5.2k subscribers. New channels do break out in this niche.

## What differs from our pilots 002–006 (cause of "amateur")

| | Winners (measured) | Our pilots | Rule |
|---|---|---|---|
| Picture | Full-frame scenery, **no person or figure** (L1: drone footage; L2: AI 2.5D landscapes) | A cut-out figure fixed at the left for 25–30 min | **R1** |
| Motion | Always moving: slow push-in or pan, plus drifting light, clouds or stars | A static figure; the background moves | **R2** |
| Scene length | One scene every 20–30 s (L1 2–3 per min; L2 2 per min) | Background about every 9 s behind a fixed figure | **R3** |
| Captions | Bold white sans-serif, dark outline or shadow, **no box**, centered (L2) or bottom-centered (L1), phrase by phrase | A gray translucent box at the right | **R4** |
| Scripture | The verse text itself in a rounded dark translucent card, centered, 6–25 s, only while it is read (L1: 14 cards) | A reference badge that lingered | **R5** |
| Calls to action | Mid-video: 2 small animated graphics, about 7–11 s each (L1 at 1:00 and 7:00). Otherwise only in the spoken outro, 20–35 s | SUBSCRIBE/LIKE/SHARE rotating all the time, plus a permanent "Type AMEN" | **R6** |
| Hook | Direct address and a concrete promise, then "Let us pray"; the prayer starts by 0:14 (L2) | A title card, then a hook | **R7** |
| Voice pace | L2 measured exactly from the transcript: 790 words in 347 s = **137 wpm** | 134–137 wpm | No change (vidIQ's "85–95 wpm" estimate was **refuted** by the count) |
| Music | Soft ambient piano or pads, well under the voice | Owned music, ducked | No change |
| Short | Starts on a full sentence, one image, phrase captions of 1–5 words, no CTA, ends on "Amen." | Frames started mid-sentence | **R8** |

## Rules (blocking)

- **R1.** No persistent person or figure on screen. Every frame is full-frame scenery (light, sky, water, fields, a church or altar with no people).
- **R2.** The picture is never still. Each scene has continuous camera motion (zoom 1.00→1.08 or a pan). There is no hard freeze of 2 s or more outside the fades.
- **R3.** Scenes last 18–36 s, change with a cross-fade of at most 1.0 s, and no image repeats within 5 minutes.
- **R4.** Captions are phrase-level (at most 7 words, at most 2 lines), bold white sans-serif with a dark outline or shadow, no box, centered in the lower third. They are timed to the narration.
- **R5.** Scripture: when a verse is read, the verse text (KJV) and its reference appear in a rounded translucent card. The card appears only while that verse is spoken and is removed when the verse ends. No reference badge stays on screen.
- **R6.** Calls to action:
  - at most 2 mid-video animated graphics, each 10 s or less, the first not before 0:45;
  - the spoken CTA (Amen, like, share, subscribe) only in the outro, at most 35 s;
  - nothing persistent except a small channel mark of at most 4 % of the frame area.
- **R7.** Opening:
  - within 8 s: direct "you" address and the title promise in concrete words (L2 by 0:03, L1 by 0:02); "Let us pray" is not required (L1 prays only after 1:40);
  - no title card longer than 3 s;
  - no claim that God sent this video or that something will happen to the viewer (fabricated prophecy is forbidden even though L1 uses it).
- **R8.** Short:
  - starts at a sentence start, with a complete line within the first 3 s, and ends on a completed sentence;
  - phrase captions of 1–5 words;
  - no CTA overlay.
- **R9.** Thumbnail, measured on the 20 spoken-prayer winners (`evidence/vidiq/20261019/thumbnails.json`, runner audit 2026-10-19; images not stored). Each item is in ≥ 70 % of winners; no weak contrasts were measured, so none is claimed as a driver. They block as our standard:
  - overlaid text present (20/20), **4–12 words in 2–4 lines** (17/20 each);
  - white text (20/20) with a **dark outline or shadow** (19/20) and **no box** (19/20); a yellow or gold accent line is a house choice (13/20);
  - **mean luminance 48–147 of 255** (all 20 inside; none bright, 8/20 dark), measured on the 1280×720 file;
  - a **visible light source** in the picture: sun, moon, lamp, candle or window light (15/20);
  - no realistic human face (house choice, consistent with R1; 13/20 winners show no person);
  - 1280×720 JPG under the Help size limit (stage 5).

- **R10.** Resolution and 3D look (owner, 2026-10-20). It blocks from pilot-008 on; pilot-006 (published 2026-10-21 00:00) keeps its painted set, so one video never mixes two looks.
  - **Minimum 1080p everywhere.** Every delivered video is at least 1920×1080 (long) or 1080×1920 (Short), at ≥ 24 fps. Every source image is at least 1920×1080 after the 16:9 crop (vertical: 1080×1920), generated at that size, or brought to it by AI super-resolution (Real-ESRGAN 2×, as `cf-images.yml` does for FLUX's 1024 px output); never by a plain resize.
  - **3D cinematic look.** Every image and animation reads as a photoreal 3D cinematic render: volumetric light, global illumination, depth of field, real depth for the parallax. No flat illustration and no painting style.
  - Prompts end with the house suffix: `photorealistic cinematic 3D render, volumetric light rays, global illumination, shallow depth of field, rich depth and atmosphere, ultra-detailed, no people, no text`.

- **R11.** Real cinematic motion and dynamics (owner, 2026-10-23: "no static images", "4 to 7 s shots, bet on dynamics", "never below 1440p"). Pilots with a `footage` list are rendered and judged under `production/qa_criteria_v4.json`:
  - Frame 2560×1440 (30 fps). Every source is ≥ 1440p before the crop: footage from ≥ 1440p sources, stills through Real-ESRGAN to 4096 px (`images-upres.yml` for older ones). A plain upscale is refused (`IMAGE_BELOW_FRAME`).
  - Shots of 4–7 s on a varied cadence, cut on a nearby sentence start. Two footage shots for every still, so real footage is ≥ 60 % of the picture. A clip gives up to 3 distinct shots (6.5 s segments). The 5-minute repeat gap applies to every shot.
  - Footage comes only from the shared library (`production/footage/library/`): Pexels License, CC0, public domain or CC BY. Never share-alike, non-commercial or other channels' videos. Every clip is vetted automatically (no black frames, no readable text, nothing described as people, buildings or vehicles), credited in the description and hash-bound.
  - No Subscribe/Like badges over the picture (3 reviews named them as breaking the immersion). The spoken amen invitation after the payoff stays.
- **R12.** The first 3 seconds (owner, 2026-10-23: "they must be devastating"). Measured on breakout winners in `evidence/vidiq/20261023/hook_audit.md`; checked by `script_check.hook_problems` and the renderer:
  - The voice starts at 0.3 s over moving footage. There is no still title card. The spoken hook line is on screen as large centred text from frame 0 until it has been said. Music starts at 0:00.
  - The first sentence has ≤ 14 words, speaks to "you" and places the moment ("Before you sleep tonight…") or opens on a contrast ("The world tells you… but God…"). It never opens on a greeting. The hook promises the prayer.
  - No sound effects: none of the measured winners uses them. Soft piano and pads only, as now.
  - Length: 12–18 min for v4 prayers (breakouts on small channels cluster at 5–18 min, median ~14 min).
- **R13.** Continuity and authenticity (owner, 2026-10-23: "viral to explode fast, then authenticity and originality for continuity"; research in `strategy/DECISIONS.md`, day 6 evening). Checked by `script_check.continuity_problems` for v4 pilots:
  - A `roadmap` segment within 30 s names what we will pray for and where the video ends (promise, then commitment).
  - A `rehook-N` segment previews the next prayer at least every 3.5 min until the commitment or payoff (promise, deliver, promise the next). Sleep readings after the CTA are exempt: they must not wake the listener.
  - The spoken CTA invites a prayer request in the comments, and the next prayer of the same series prays over the requests shared (themes only, never names): the community ritual is the channel's authenticity layer and the reason to return.
  - Variety against the inauthentic-content policy (YouTube, July 2025: "template with little to no variation"): consecutive pilots of one series alternate archetype (passage walk-through such as 008/009/011, topical guided prayer such as 010/013/014, a retold Bible narrative with prayer), and every script is written for its own topic.
- **R14.** What the algorithm promotes and kills (study of 811 videos in 23 channels plus 98 niche breakouts, strict within-channel-and-month tests: `evidence/vidiq/20261023/algorithm_study/REPORT.md`). Checked by `script_check.title_problems` for v4 pilots:
  - Title = hook (time anchor or gratitude) + one emoji `|` an exact search phrase (Morning/Night/Bedtime/Evening Prayer). Never a date, weekday, month or year (×10 odds of a dead video, p = 0.001).
  - One format per slot, every day, no hopping (every never-grew channel hops; every grower repeats).
  - Gratitude themes first in the cold start (dead odds ×0.35, p = 0.002); morning 15–25 min; night moves to ≥ 60 min, then ≥ 90 min of guided prayer plus Scripture for sleep (≥ 90 min was never dead, p = 0.008).
  - Script polish does not unlock a cold channel (dead videos read as well as winners); packaging, format and the channel's audience profile do.
- **R15.** Description and picture (the same study: 334 videos' metadata in 62 channel-month strata, and 20 videos watched end to end, `algorithm_study/meta_perm_results.txt` and `visual_watch.md`):
  - No Bible reference (book + chapter or verse) anywhere in the description, chapter names included: hit odds ×0.33, p = 0.007. Checked by `script_check.description_problems` and refused by `package_pilot` (`DESCRIPTION_SCRIPTURE_REF`). The KJV attribution line stays.
  - A subscribe ask in the description: hit odds ×3.27, p = 0.014. Written by `package_pilot`.
  - Production quality does not separate hits from dead videos (watcher score 6.9 vs 6.8; our own two videos scored the highest, 9 and 8.5, with 6–40 views). Picture and sound are table stakes: burned-in captions, music from 0:00 well under the voice, slow narration, calm palette. Further polish is not the lever; title, theme, length and cadence are.
- **Owner floor.** Every new upload needs the designated watched review's overall ≥ 9.5 (owner, 2026-10-23), on top of the rubric's item ≥ 7 and overall ≥ 8.

## Gate

`qa_pilot.py` with the frozen criteria `production/qa_criteria_v3.json`, or `qa_criteria_v4.json` for R11 pilots (deterministic, from the render manifest and the file), checks R1–R7 and R11; `prepublish_gate.py` blocks on every row (`DIMENSIONS_V3` / `DIMENSIONS_V4`). R8 is checked by the Shorts tests. One miss is a FAIL. It runs before the watched review, so the watched review never has to judge what a rule already decides.
