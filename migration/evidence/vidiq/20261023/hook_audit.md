# Hook and pacing audit of breakout prayer videos (vidIQ, 2026-10-23)

Owner, 2026-10-23: "the first 3 seconds must be devastating; analyse the market and apply it to every video".
Source: vidiq_outliers (long, 3 months, channels <= 100K subs, keyword "christian prayer bible verses for sleep
and peace") and vidiq_video_watch with one fixed prompt (seconds 0-1, 1-2, 2-3, 3-5, 5-10; cuts in the first 60 s;
voice, music, SFX, CTA, resolution). Model-reported observations, not our measurements.

| video | channel subs | views | breakout | length | first word | on-screen at 0 s | ASL first 60 s |
|---|---|---|---|---|---|---|---|
| OuqwfEgNavE (2026-10-19 audit) | 5.6K | 284K | 2,658x | 14:18 | 0:02 "Don't rush past this moment." | drone footage, no title card | ~20-30 s (real drone footage, continuous motion) |
| fXhKzleJhxI | 1.6K | 72K | 1,429x | 5:47 | 0:02 "Before you sleep tonight..." | big centred title text | ~20 s (AI stills, slow zoom) |
| mtWtsL5hOLg | 1.9K | 102K | 847x | 9:28 | 0:00 "The world tells us that if we don't put ourselves first, no one will. But Jesus teaches something completely different." | the spoken line as a centred banner | ~3.3 s (18 cuts; looping motion scenes) |
| JNk9Ha7rnMI | 2.2K | 58K | 266x | 18:14 | 0:00 "Dear Heavenly Father, I come before you this morning..." | the spoken line as text | ~10 s |
| 3KGnfsmheGY | 1.4K | 54K | 244x | 16:28 | 0:00.6 "Before you close your eyes tonight, remember this: you don't have to carry tomorrow's worries into tonight's sleep." | the spoken line as a centred banner | ~5 s (12 cuts) |
| wdRNitAZkoc | 1.9K | 162K | 166x | 3:28:09 | INVALID: the analysis described a different 1:37 parenting clip; discarded | | |

## What every valid winner does in the first 3 seconds (5/5)
1. The voice starts at 0.0-2.0 s (4/5 within 0.6 s). No silent or static title card before the voice.
2. The first sentence addresses the viewer and places the moment: "Before you sleep tonight", "Before you close your
   eyes tonight", "Dear Heavenly Father, ... this morning", or a contrast ("The world tells us ... But Jesus ...").
3. The spoken hook line is on screen as large centred text from the first frame (4/5), not small captions.
4. A concrete promise follows by ~8 s ("This prayer will help you end your day resting in His loving presence").
5. Music (soft piano + pads) starts at 0:00. No sound effects in any of the five.
6. Voice: male, mature, warm, slow, reverent, with 1-2 s pauses (5/5).
## Pacing and format
- Shot length varies: the two fast-cut winners hold ~3.3 and ~5 s per scene; the slower ones use continuous motion.
- Every winner is 1080p; none is 1440p/4K (a resolution above 1080p would be a differentiator, not a norm).
- Breakouts on small channels cluster at 5-18 min (median of the top 12 outliers ~14 min) and at 2-3 h sleep videos.
