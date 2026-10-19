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
- **R9.** Thumbnail: to be measured. Dot's card collects the thumbnails of the 20 winners; until then no rule is assumed.

## Gate

`qa_pilot.py` with the frozen criteria `production/qa_criteria_v3.json` (deterministic, from the render manifest and the file) checks R1–R7; `prepublish_gate.py` blocks on every row (`DIMENSIONS_V3`). R8 is checked by the Shorts tests. One miss is a FAIL. It runs before the watched review, so the watched review never has to judge what a rule already decides.
