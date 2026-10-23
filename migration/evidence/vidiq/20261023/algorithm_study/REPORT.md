# What the algorithm promotes and what it kills: English spoken-prayer YouTube (2026-10-23)

Owner, 2026-10-23: "understand what all the winners have in common and what the ones that do not grow have in
common, so we only execute what makes a channel grow; this analysis is the gold of the operation".

## Data (vidIQ, read-only; raw files in this folder)
- 98 breakout long-form videos in the niche, last 6 months, channels ≤ 500K subscribers (`outliers.md`); 75 are
  spoken word, 23 music/worship.
- The last ~50 long uploads of 23 channels (`channel_videos.json`). The 23 are 17 growing spoken-prayer channels,
  4 channels that post a lot and never grew (5–29 median views), and 2 young fast growers.
- 811 videos ≥ 10 days old (`rows.json`). Outcome per video = views / its own channel's median ("ratio"): hit ≥ 3×,
  dead ≤ 0.5×.
- Transcripts of 4 breakout videos and 4 dead videos on the same themes.
- Our own channel (HeroVerse, 9 long + 23 Shorts).

## Method
Every feature is tested **inside the same channel and the same month** (89 strata, Mantel–Haenszel odds ratio,
2,000-permutation p-value; `perm.py`). This removes the channel's size, voice, niche and life stage, so only
the video itself differs. Crude odds ratios (stratified by channel only, `analyze.py`) are shown for context.
Rules below are graded:
- **PROVEN**: p ≤ 0.01 in the strict test, or the same result in every channel observed.
- **STRONG**: p ≤ 0.05, or consistent but observational.
- **HYPOTHESIS**: plausible, not measured.

## What kills
| # | Finding | Evidence | Grade |
|---|---|---|---|
| K1 | A date, weekday, month or year in the title | Odds of a dead video ×10.0 (p = 0.001). Daily Hope Prayer's dated morning prayers got 14–60 views; the same channel's undated prayers got 30–80K. | PROVEN |
| K2 | Format hopping: affirmations one day, Bible stories, Psalms, warfare, "3AM prayer" the next | All 4 never-grew channels hop. All 17 growers repeat one format. Our July Shorts (prophecy, "Marvel" and "theflash" tags) are the same mistake. | PROVEN (observational) |
| K3 | Videos under 10 minutes on a cold channel | Crude hit odds ×0.28 and dead odds ×4.4. Not significant within the same month (p = 0.08–0.26): partly the cold-start stage. Peaceful Night Prayers: 5–9 min videos got 50–400 views; 44–68 min got 14–243K. | STRONG |
| K4 | Clever, abstract titles that nobody searches ("Let God Do The Math", "Choose The Lowest Seat") | TheGuide to Jesus, 30K subscribers: 50 consecutive uploads at 376–1,673 views, never a hit. | STRONG |
| K5 | Night videos of 10–17 min | Prayer Sleep Oasis: 37 night prayers of 10–16 min with good titles, 1–154 views. Niche night winners have a median of 40.6 min. | STRONG |

## What promotes
| # | Finding | Evidence | Grade |
|---|---|---|---|
| P1 | Gratitude as the theme ("Thank God…", "Thank You Lord…") | Dead odds ×0.35 (p = 0.002); hit odds ×1.69 (p = 0.05). The biggest jackpots lead with it: PRAY NOW TV 957K, Peaceful Prayers 180K and 168K, Daily Hope 80K and 63K, Favor for Today 54K. | PROVEN |
| P2 | Long sleep content (≥ 90 min) for night | Never dead within its channel-month (p = 0.008); hit odds ×3.1 (p = 0.08). Niche winners ≥ 90 min have a median of 140K views. Selah's 3.5 h Psalms: 433K, 346K, 311K. | PROVEN (never dead), STRONG (hit) |
| P3 | Two-part title "hook \| exact search phrase" | Hit odds ×2.0 (p = 0.009). Winners: "Before You Sleep, Thank God for Everything 🙏 \| Peaceful Night Prayer for Gratitude & Rest". | PROVEN |
| P4 | One emoji (🙏 🌙 🌅) | Hit odds ×2.3 (p = 0.010). | PROVEN |
| P5 | Morning prayers of 12–35 min | Morning winners have a median of 21.3 min. First jackpots at 12.9, 14.3, 14.5, 14.9 and 20 min. | STRONG |
| P6 | Daily cadence in one format = many lottery tickets | Outcomes are fat-tailed. Christ Prayer Daily has a median of 1.4K views but three videos at 130–173K. Growth is the rare 30–400× video, not the average one. | PROVEN (observational) |
| P7 | Retention contract in the first 30 s, then specific pains, a first-person prayer the viewer repeats, repeated declarations, and a CTA of "type amen" or a custom phrase plus a prayer request and "send it to one person" | Present in every winner transcript read. Grace & Purpose's Psalm 91 (287K): "stay with me… by the time we say amen…" and a mid-video "don't leave now, this is the part you came for". | STRONG (necessary, not sufficient: see N1) |

## What does not decide (as important as the rules)
- **N1. Script quality does not decide distribution on a cold channel.** The dead videos' scripts are as good as the
  winners'. Morning Prayer Today (88 views) has a hook, a roadmap, re-hooks, gratitude and CTAs; TheGuide to Jesus
  (729 views) is excellent writing. A cold channel is never shown; packaging and the channel's audience profile decide
  whether anyone sees the script.
- **N2. Copying a surging title is a lottery.** 25 near-identical titles posted within 30 days of a hit: 4 hits (16 %)
  against a 17 % baseline. When it works it is huge (Daily Hope's copy, 63K; Morning Grace's copy, 213K), but there is
  no average lift.
- **N3. Upload frequency alone.** The never-grew channels also post 7×/week.

## Unlock timeline (cold start)
Growing channels were "born dead" (50–400 views per video) until a first jackpot:

| Channel | Upload of first ≥ 20K video | Length | Theme |
|---|---|---|---|
| Morning Grace Daily | #12 | 14 min | gratitude |
| Favor for Today | #12 | 16 min | night gratitude |
| Grace & Purpose | #18 | 14 min | Psalm 91 |
| Peaceful Night Prayers | #30 | 64 min | night protection |

After the first jackpot the baseline rises for good: Peaceful Prayers went from ~1K to 10–450K per video.
The 4 channels that never unlocked hopped formats or made short night videos.

## HeroVerse diagnosis
- 6 prayer uploads, 6–40 views each: the cold-start stage, as expected.
- The channel's July history is prophecy and motivational Shorts tagged #marvel and #theflash. That is the format
  hopping (K2) that the never-grew channels show.
- The channel name "HeroVerse" does not say "prayer"; all 23 sampled channels do. This is a HYPOTHESIS, not measured.

## Decisions taken from this study (STANDARD R14)
1. Titles: "hook (time anchor or gratitude) + one emoji | exact search phrase". Never a date, weekday, month or year.
   Checked by `script_check`.
2. One format per slot, every day, with no hopping:
   - morning: guided prayer, 15–25 min;
   - night: guided prayer plus Scripture for sleep, moving to ≥ 60 min and then ≥ 90 min (renderer work: a
     low-cost long sleep section).
3. The first week favours unlock themes: gratitude (morning and night), Psalm 91 protection, "before you sleep".
4. Owner decisions (outward-facing, not taken by Claude):
   - make the 18 off-niche July Shorts and videos private;
   - consider a niche display name (e.g. "HeroVerse Prayer").

## Not measured
- Thumbnails: images could not be fetched from this environment.
- Click-through rate and retention curves: only the channel owner's analytics hold them.
- Audience country.
