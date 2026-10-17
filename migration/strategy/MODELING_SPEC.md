# HeroVerse modeling spec (measured, 2026-10-18)

Source: `evidence/structure-mining/20261017/measured.json` (`blueprint_stats.py`). Usable records need ≥ 90% coverage, narration (≥ 40 wpm) and a policy-clean source.

- **Prayer:** 2 winners (Morning Grace Prayers).
- **Teaching:** 5 winners (Beneath The Verse, The Ancient Bible, Owens Bible).
- **Excluded:**
  - Grace & Glory: borrowed identity and recordings.
  - United Prayer: off-format livestreams.
  - Prayer of Hope: hour-long videos under 90% coverage.

The prayer sample is small. Its targets are bands, not points, and are re-measured every week (structure mining on Sundays). The mining itself is MODEL_REPORTED until the native-window accuracy check reports its agreement rate.

**Rule** (`BEAT_THE_REFERENCE_RULE.md`): every number below is the winner median. Our video must sit inside the band and beat the winner where the arrow points.

## 1. Prayer (morning, night, protection)

| Measure | Winner median | HeroVerse target |
|---|---|---|
| Length | 14.7 min (12.2–17.1) | **15–20 min** (watch hours; QA floor 10:01) |
| Words per minute | 154 (149–159) | **140–160** (QA band 115–165) |
| Beats per minute | 2.1 (1.8–2.5) | **2.0–2.6**: segments of 20–35 s |
| Mean beat length | 25.5 s | 20–30 s |
| "you" per 100 words | 6.0 | **≥ 6** in hook, invitation, reflections; first person ("I/we") inside the prayers |
| Questions per minute | 0.03 | ≤ 0.1 (prayer is declarative) |
| Scripture per 10 min | 0.8 | **≥ 4**: beat the winner on substance; every anchor read verbatim (KJV) |
| Picture changes per minute | 4.3–6.1 | ≥ 6 background holds per minute with parallax; never > 20 s on one background |
| First spoken word | ≤ 1 s | ≤ 0.5 s |

**Beat order by phase** (winners: 100% prayer from second 0; prayer 90% and declaration 10% in the middle; prayer 50%, CTA 33% and application 17% in the last 10%):

1. **0–8 s, hook:** "Good morning/evening" plus the listener's concrete felt need (second person) plus the promise of what this prayer does. The promise is in the title and is spoken by 8 s.
2. **8–30 s, invitation:** settle the body (breath, shoulders), name the need.
3. **30 s–3 min:** the first scripture anchor and the first short prayer. Winners are already praying at 0:15, so ours prays by 1:30 at the latest.
4. **Middle:** guided prayers by life area (mind, work, family, provision, health, home, the weary), each opened by a scripture anchor or closed by a one-line declaration. Two guided-stillness pauses (6 s, music forward) break the run.
5. **Last 10%:**
   - declaration (short lines to repeat);
   - payoff: one concrete commitment for today or tonight;
   - blessing;
   - soft CTA ("Type AMEN", subscribe for tomorrow's prayer).
   The CTA comes only after the payoff.

**Packaging (prayer):**

- **Title:**
  - Pattern: `[Time-of-day] Prayer | [Promise in 5–8 words] [Today/Tonight]`, 9–16 words, 50–70 characters.
  - Caps words ≤ 20%; 🙏 allowed once.
  - Winners also add a benefit list ("Peace, Protection & Blessings"); we keep the promise first.
- **Thumbnail:**
  - 3–5 big words carrying the promise, not repeating the title.
  - A secondary line with the time of day.
  - Warm light sky/landscape; winners use no faces in thumbnails.
  - Text never over the figure's face.
- **Description:** the promise sentence first (≤ 150 characters), then a scripture list with references, then 3 hashtags (#prayer #morningprayer #jesus).
- **Tags:** 6–10 tags, ≤ 400 characters.
- **Category:** 29. Made for kids: no. Synthetic media: declared.

## 2. Teaching and opinion-critique (`FORMAT_OPINION_AND_CRITIQUE.md`)

| Measure | Winner median | HeroVerse target |
|---|---|---|
| Length | 16.8 min (10–34) | **14–20 min** |
| Words per minute | 139 (73–145) | **130–150** |
| Beats per minute | 1.26 | **1.2–1.8**: segments of 35–50 s |
| Shots per minute | 9.5 (5–15) | **≥ 10**: beat the median, toward the top quartile (14) |
| Scripture per 10 min | 7.7 | **≥ 8**, quoted exactly with book:chapter:verse on screen |
| Questions per minute | 0.24 | 0.2–0.4 (open loops) |
| "you" per 100 words | 0.5 | 0.5–2 (narration, not address) |

**Beat order by phase:**

1. **0–15 s:** hook 50% (cold-open story scene or the sharp question), promise.
2. **15–60 s:** context, the thesis stated plainly, an open loop ("Why almonds?").
3. **1–3 min:** teaching plus evidence plus scripture; the first answer is partial and the loop stays open.
4. **Middle:** teaching 44%, scripture 12%, argument 11%, evidence 9%, application 7%. The strongest objection is stated fairly in the second half, then answered.
5. **Last 10%:** application 31%, CTA 23% ("comment your view"), a closing scripture.

**Packaging (teaching):**

- **Title:** a curiosity question or contradiction, 8–12 words, ~33% caps on the key word ("Why Did Aaron's Rod Grow ALMONDS?", "God Never Said RAINBOW…").
- **Thumbnail:** 4–9 words in caps that reframe the title ("MOST CHRISTIANS MISS THIS"); a figure or face allowed.

This format needs its own frozen QA criteria before its first render (the prayer grammar requires the praying figure on screen ≥ 98% of the time). First teaching pilot: after those criteria are frozen.

## 3. Same-instrument scorecard (gate before approval)

Our render is mined with the **same miner and the same model** as the references (`structure_mining.py`, Gemini Files API, free tier), and `blueprint_stats.py` computes the same measured fields. Approval needs all of the following:

- Every row of the format's table inside its target band.
- Hook promise spoken by 8 s; first word ≤ 0.5 s.
- Beat order matching the phase map above (the miner's beat labels by phase).
- Scripture density ≥ target, and every reference present in the script.
- Watched review of the long video (Gemini, rubric as for the Shorts: every item ≥ 7, overall ≥ 8).
- Frozen QA PASS (never edited after results).

## 4. Policy exclusions (never modelled or copied)

- Borrowed identities or recordings (named preachers, "Apostle…", sermon reuploads).
- Fear-bait ("if you skip this…", curses, threats), fabricated prophecy, health or wealth guarantees.
- Reused content: every script is original; scripture is KJV (public domain); images are generated by open-licence models; music is owned.
- The praying figure is HeroVerse's own generated illustration (a stylised devotional painting), not a real person.

## 5. Living intelligence (re-measured, never frozen)

| Source | Cadence |
|---|---|
| Market panel | daily |
| Packaging mining | Sundays |
| Structure mining of winners | Sundays |
| Accuracy check vs native audio | after each structure mining |
| Our own published videos' public stats | daily intel |

When a target moves, this spec is updated with the date and evidence file. The criteria of a pilot already rendered are never changed.
