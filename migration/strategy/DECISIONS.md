# Decisions (living intelligence ledger)

Owner rule (2026-10-18): no random actions. Every change must:
- rest on enough data;
- have its consequences checked across the pipeline before it ships;
- carry a measurement that keeps or reverts it.

The goal is YPP in 14 days (30 at most), and the system is being validated to become a product.

## Protocol (daily, after the goal report at 07:45 UTC)
1. **Read:**
   - `evidence/daily-report/latest.md` (our channel, Analytics);
   - `evidence/daily-intel/` (market);
   - weekly packaging, structure and accuracy files.
2. **Propose** only changes that close the gap to the goal (subscribers per day, watch hours per day). Each proposal needs:
   - evidence (file and numbers, our own measured data first, then market data);
   - the expected effect;
   - the risks checked (policy, quota, render time, gates);
   - the measurement and the keep/revert rule.
3. **Apply** only to pilots not yet rendered. Criteria of a rendered pilot and frozen QA criteria are never edited.
4. **Measure:** our own Analytics per video (watch hours, average view %, subscribers gained) at 48 h and 7 days; keep, adjust or revert, and write the outcome here.

## The 90–99% rule (owner, 2026-10-18; 90% is the minimum, higher is better)
A change happens **only** when the evidence shows, with at least 90% confidence, a clear effect toward the goal:
- **Statistics:** one-sided p < 0.10 at minimum (p < 0.01 preferred), or a confidence interval of at least 90% that excludes "no improvement".
- **Data:** our own Analytics first, then market data with an adequate sample.
- **Mechanism:** a plausible link from the change to subscribers/day or watch hours/day.
- **Checks:** consequences checked across the pipeline.

Otherwise nothing changes. The daily analysis still runs and records measurements, but it does not act on weaker evidence.

**Not "changes" (always done):**
- fixing defects (bugs, failures, broken automation);
- compliance with the owner's fixed rules (policy, zero cost, English-only);
- execution drifting from the strategy registered before publication (`MARKET_FORECAST_TIME_TO_YPP_20261017.md`: daily original 25–40 min prayer videos, Shorts as acquisition).

**Applied to today's decisions:**

| Decision | Evidence | Confidence | Outcome |
|---|---|---|---|
| D-03 (1 Short per long) | 5/22 vs 1/26 channels | one-sided Fisher p = 0.062 (< 0.10) | **active**: passes the 90% minimum |
| D-05 (subscribe ask) | 13/20 winners | no comparison group, not testable | **reverted** in pilots 004–006 (pilot-003 had already rendered with it) |
| D-01/D-04 (length) | 5/22 vs 1/7 | p = 0.55, not a proven improvement | **kept as conformance**: they return execution to the registered 25–40 min strategy that the 15-min scripts had drifted from |
| D-02 (hide 4 fear-bait videos) | owner policy | compliance | **kept** |

**How to read these numbers (correction 2026-10-18):** p = 0.062 is NOT a 93.8% chance that the strategy works. It is
the chance of seeing a gap at least this large between the two groups if strategy made no difference. The evidence is
observational and small: 48 market channels (22 long-form ≥ 20 min, of which 5 reached the fast outcome; 26 mixed, of
which 1), not our channel, not randomised; niche, start date, budget and luck can explain part of the gap, and one
channel more or less in a group moves p a lot. It clears the owner's 90% bar as a statistical threshold; it does not
predict how fast HeroVerse reaches YPP.

## Ledger

### D-2026-10-18-01 — Night prayer to ~33–40 min (from ~15)
- **Evidence:** `evidence/ypp-market-model-20261017.json`, fast ≤ 90-day channels with ≥ 3 long videos (n = 37), by median long-video length (model estimates: views × length × 30% retention):

  | Length | Channels | Hours per long video | Subscribers/day |
  |---|---|---|---|
  | < 15 min | 9 | 467 | 91 |
  | 15–30 min | 5 | 3,003 | 116 |
  | 30–60 min | 12 | 3,608 | 194 |
  | 60+ min | 11 | 3,327 | 56 |

  The strongest clean example is THE HIDDEN GOSPEL (43 min, 715 subscribers/day at 34 days). Our gap on day 1 is 280 watch hours a day.
- **Change:** pilot-004 (first), then night pilots: guided prayer ~15 min, CTA, then "Scripture for sleep" (relaxation plus slow full KJV readings with short reflections). All text is original and nothing is looped, so it is not repetitive content.
- **Checked:**
  - Approval hard length band raised to 50 min; reported band 15–45 min.
  - Gemini free-tier tokens: review at fps 0.5 (~156k tokens for 40 min); scorecard windows 35 s apart.
  - Approval timeout 120 min.
  - Runner render ~105 min for 33 min of video, within its 240 min limit.
  - QA criteria unchanged (minimum length only).
- **Measure:** watch hours per video and average view % at 48 h / 7 days, pilot-004 (33 min) vs pilot-002/003 (15–21 min). Keep if hours per video ≥ 3× the short format; revert to 15–20 min if the average view % falls below 15% and hours do not rise.
- **Not done:** 60–90 min (lower subscribers/day in the data).

### D-2026-10-18-02 — Hide 4 old fear-bait / "prophecy" public videos (reversible)
- **Evidence:** `evidence/daily-report/20261018.json` (Analytics, 365 days). The 5 public titles flagged as fear-bait or prophecy carry 2.5 of the channel's 76.9 watch hours.
  - "The 2026 Prophecy: What They Are Hiding From You…" (×2) and "The 2026 Warning: What They DON'T Want You to Know": 0 h each.
  - "God is WARNIG you: The Law of Divine Return is HERE!": 1.3 h, 0 subscribers gained.
  - "Why God Chose YOU… (Don't Ignore This)": 1.2 h, 12 subscribers gained, 57% average view. Mild urgency, not prophecy, so it stays public.
- **Why:** the owner's policy forbids fear-bait and fabricated prophecy. YPP reviewers look at the channel's main theme and its most viewed and latest videos, and misleading metadata is a YouTube spam and deceptive-practices risk. A rejection costs at least 30 days, longer than the 14-day goal.
- **Cost:** at most 1.3 watch hours (1.7% of 76.9).
- **Change:** the 4 ids are added to `channel/privacy-plan.json` (`policy_hidden`, with reasons); the daily 08:05 UTC privacy job sets them private.
- **Measure:** the channel's public watch hours (expected drop ≤ 1.3 h); reversible at any time.

### D-2026-10-18-03 — One Short per long video (from three)
- **Evidence:** `strategy/MARKET_FORECAST_TIME_TO_YPP_20261017.md` (panel 2026-10-17, Wilson 90% intervals). Share of channels over the YPP proxy at 0–30 days:

  | Strategy | Share |
  |---|---|
  | Long-form ≥ 20 min, ≤ 20% Shorts | 23% (5/22) |
  | Mixed long + Shorts | 4% (1/26) |
  | Shorts-heavy | 3% (3/118) |

  The fast profile (45 channels) has a median Shorts share of 0%. Subscribers are the binding constraint, at 8.8 per 1,000 long-form views. Shorts views count for neither the watch-hour path nor the long-form conversion.
- **Change:** 3 candidates selected (was 5); only the best watched-review score is published (was 3). pilot-002 keeps short-02 (9/10). This follows the owner rule: Shorts stay, as the gateway to the long video.
- **Checked:** `publish_shorts`, `pending_shorts` and preflight count only Shorts marked to publish. Fewer candidates save private minutes and Gemini calls.
- **Measure:** subscribers gained per Short and the Short→long click path (Analytics) over 7 days. Raise back to 2 per long video if Shorts bring ≥ 30% of the subscribers gained at under 30% of uploads.

### Robustness (no verdict change)
- `long_review.py`: provider errors write `status: ERROR` (retried), distinct from FAIL (never retried).
- `reconcile.yml` at 07:20, 13:20 and 19:20 UTC re-dispatches approval for due QA-PASS renders with no review or an ERROR review, and publication for approved files not yet on YouTube. 07:20 is right after the Data API day resets, so an upload that failed on quota succeeds then.

### D-2026-10-18-04 — Morning prayer to ~25 min (from ~15); night ~28–33 min
- **Evidence:** `strategy/MARKET_FORECAST_TIME_TO_YPP_20261017.md`. Base rate at 0–30 days: long-form ≥ 20 min 23% (5/22) vs 3–20 min 14% (1/7). The fast profile (45 channels over the proxy within 90 days) has a median long video of 36 min at 1 upload/day. D-2026-10-18-01 shows the hours per video.
- **Change:**
  - pilot-005 (morning): guided prayer, then "Scripture to carry into your day" (Psalm 91, 23, 27, 46, 121; Ephesians 6; Isaiah 43; Romans 8, each with a reflection), ~25 min.
  - pilot-006 (night): guided prayer, CTA, then healing Scripture for sleep, ~28 min.
  - pilot-003 (15 min) is already rendering and stays as the measured control.
- **Checked:** same as D-01 (approval band ≤ 50 min, token-safe review, runner time). Morning CTA stays after the payoff (viewers are awake); night CTA comes before the sleep section.
- **Measure:** watch hours per video and average view % at 48 h / 7 days: pilot-003 (15 min) vs pilot-005 (25 min) for mornings, pilot-004/006 for nights. Keep if hours per video rise ≥ 2× without the average view % falling below 15%.

### D-2026-10-18-05 — Ask for the subscription, with a reason, in every CTA
- **Evidence:** `evidence/structure-mining/20261017` (policy-clean winners, model transcripts). 13 of 20 videos ask to subscribe (65%), always with a reason ("subscribe so you can keep walking through the text with us"). Comments 11/20, share 9/20. Our CTAs asked for "amen" only. Subscribers are the binding constraint (8.8 per 1,000 long-form views).
- **Change:** pilots 003–006: "subscribe, so tomorrow's prayer is waiting for you / ready when you lie down", kept after the payoff (morning) or before the sleep section (night). No early or repeated asks: the prayer is not interrupted.
- **Measure:** subscribers gained per 1,000 views per video (Analytics), against 8.8 (market median) and our earlier videos.

### Measurement 2026-10-18 — mining accuracy vs native audio (first run)
- **File:** `evidence/structure-mining/20261017/accuracy.json`. 10 windows compared, 2 without speech.
- **Results:**
  - Transcript agreement: median 0.881. Openings (0–30 s) score 0.90–0.99.
  - Three mid-video windows score 0.11–0.20. One of them has both opening phrases found, so the text is right and the mined timestamps drift late in long videos.
  - Opening-words agreement: 0.733 (11/15).
- **Reading:** content and openings are usable. Mid-video timing is not yet measured-grade. Beat and shot counts stay reported rows, not hard gates (MODELING_SPEC section 3).
- **Next:** the weekly run repeats this. If the drift persists, structure mining moves to shorter windows (180 s) so timestamps stay anchored.

### Correction 2026-10-18 — the first accuracy reading was wrong (mining-accuracy-v2)
- **Cause found (both sides were defective):** the miner accepted windows whose transcript was stamped outside the window (relative or rescaled times), out of order, one giant line, or truncated (speech beats with < 60 words/min). 45 of 141 windows in `20261017` are defective (24 outside window, 18 incomplete, 7 not ordered, 3 line too long). The comparator borrowed lines from neighbouring windows (8YXRtsNnGX0 0–30 s: 893 "mined" words vs 64 spoken), and labelled windows as "no speech" while our ASR heard 71 and 65 words (they were mined omissions). The median hid these.
- **Fix:** `structure_mining.transcript_problems` rejects such windows (re-mined, never used); `accuracy_check` compares only the window's own lines, counts invalid, omitted and conflicting windows as errors, and gives PASS only when ≥ 80% of speech windows agree ≥ 0.85 and openings ≥ 0.80; no speech or no openings → UNKNOWN. Regression tests for each defect.
- **Honest re-run (tuning set, the 12 windows used to find the bugs):** FAIL — 8 compared, 4 invalid, window pass rate 0.50, openings 0.818. Proof needs the holdout (`evidence/mining-accuracy-holdout.json`, criteria fixed before it is acquired, videos never used before): UNKNOWN until then.
- **Consequence:** wpm/beats/shots numbers in `measured.json` and MODELING_SPEC section 1 include defective windows. They stay informative only and are recomputed from valid windows after re-mining. Data API durations (D-01, D-04) and the frozen QA criteria do not depend on transcripts and are unaffected.

### Measurement 2026-10-20 — day 3 (daily analysis 08:10 UTC)
- **Official (YouTube Data API, goal report 01:52 UTC):** 269 subscribers; 28 public videos; 2,888 total channel views.
- **Own calculation (Analytics rows):** public long-form watch hours 365 d ≈ 3.3; public Shorts views 90 d = 22.
- **Estimate (vidIQ title score, informative only, never blocks):** pilot-008 87 · pilot-009 82 · pilot-010 84 · pilot-011 80 (`production/pilot-0NN/market/vidiq.json`).
- **Gates:** pilot-007 approved (watched review 9.0, `gemini-3.8-flash`), uploaded for 2026-10-21 10:00 UTC. pilot-006 GATE FAIL on `authenticity / no_template_image_set` (0.529 vs pilot-012; limit 0.5, not loosened). The same check finds identical background sets in 008 = 010 = 012 and 009 = 011, so all would fail. Data fix #225 and antidote E30 #226 (check moved to `script_check`).
- **Learning loop:** `learning/latest.json` decision HOLD / INSUFFICIENT (no exact 48 h checkpoint, no matched baseline). No strategy change today; the 90 % rule is not met by any new evidence.

## Cross-platform and the YPP 2027 deadline (2026-10-20)
- Evidence: `evidence/research/cross-platform-20261020.md`, where each claim is labelled official or third-party.
- **YouTube changes on 2027-02-01.** The YPP entry bar becomes 8,000 watch hours or 20 M Shorts views, and Shorts-pool revenue then needs ≥ 10 M Shorts views per 90 days. Channels accepted before that date keep their status, so **our 4,000 h goal must be met and applied for before 2027-02-01**.
- **Facebook Page + Instagram: automatic cross-post of every approved Short ≤ 90 s, plus the long prayers on Facebook.** Facebook monetization is invite-only, but the cost is ≈ 0 through the official Meta APIs. Go/no-go after 30 days on measured reach.
- **TikTok: not now.** Creator Rewards needs original, ≥ 1 min videos, and AI-generated content may be excluded. The API also needs an audit before any public post.
- **Snapchat: no.**

## Owner directive and 14-day pace (2026-10-20 14:10 UTC)
- **Owner:** "The plan is 14 days, up to 30. The platform's dates do not matter; the project is mine. Analyse daily whether the number of videos and the average views reach the goal in 14 days, and adjust the strategy daily." The YouTube 2027 date is therefore **not** a planning input. The 14-day plan (day 1 = 2026-10-18, day 14 = 2026-10-31, day 30 = 2026-11-16) is.
- **Pace needed from today (11 days left):** **≈ 66 subscribers a day** (731 to go) and **≈ 363 public long-form watch hours a day** (3,997 to go).
- **Measured pace now:** new long videos get 1–11 views each (daily report). Recent Shorts get 127–287 views. **The gap is about 100–300×**, so the current format and volume cannot reach day 14 without a breakout.
- **The biggest measured lever for watch hours: long sleep videos with Scripture**
  - Evidence: `structures/sleep-scripture-long.json`, `evidence/vidiq/20261020/sleep_scripture_long.json`.
  - 6 winners from 4 channels of 783–18,000 subscribers, each 2.2–8 h long, with 68,000–311,000 views in under 3 months. There are 3 weak contrasts of the same shape.
  - Arithmetic: 363 h/day = ~730 views/day at 30 min watched per view (2–3 h video), against ~2,700 views/day at 8 min per view (26-min prayer). This per-view figure is not measured on our channel yet.
  - **Decision:** the night slot (00:00 UTC) moves to the sleep-scripture-long shape (2–3 h, original prayers and reflections ≥ 35 % of words, KJV readings) as soon as Dot delivers the first one. The morning slot stays at the validated guided prayer.
- **Subscriber lever:** Shorts v2 (#231) and the bell strategy (#241). 66 subscribers a day needs roughly 2,000–6,000 Shorts views a day, at the 1–3 % subscribe rate seen on our July Shorts.
- **Daily:** the daily analysis routine computes the needed pace against the measured pace and the projection for day 14 and day 30, and adjusts the next day's plan with this lever list.

## Owner directive: 14 days, flexible format (2026-10-20 14:30 UTC)
- **The goal is to meet the YPP requirements (1,000 subscribers + 4,000 public long-form watch hours) by day 14 (2026-10-31).** Day 30 (2026-11-16) is an exception, not the plan. Monetization itself is then YouTube's decision.
- **The project is not locked to a format.** Only two things are fixed:
  - the niche: English Christian prayer;
  - coherence between posts.
- Everything else is chosen by what mining, modeling and the daily analysis show, and can change from one day to the next: format, length, slot, cadence, the Shorts mix and packaging.
- **How a format enters.** It enters production when mining shows it winning in our niche (count rule: winners and weak contrasts), or when our own measured results show it.
- **Allocation** (which format in which slot, how many videos and Shorts) is adjusted **daily** from the numbers, with no waiting period.
- **Quality and policy gates never change:** R1–R10, originality, the watched review, and no fear-bait.

## Day 6 measurement and decision (2026-10-23 10:30 UTC)
Source: `evidence/daily-report/latest.md` of 2026-10-23. YouTube API counts are marked [official]; our calculations from Analytics rows are marked [own].

**Where we stand**
- Subscribers [official]: 272 of 1,000. That is +0 since 22/10; reaching the goal by day 14 needs 80.9 a day.
- Public long-form watch hours [own]: 6.7 of 4,000, +1.2 since 22/10. Day 14 needs 444 a day.
- The gap is about 80× for subscribers and about 370× for hours. **Day 14 cannot be reached at the current reach.** This is arithmetic on measured numbers, not a forecast.

**Measured per format**
- Long videos: 1–18 views each and 1–26 % average watched.
  - The long 006 scored 9.3 in the watched review and then got 6 views at 1.6 %.
  - A high review score does not create distribution on a channel this small.
- Shorts: 199–299 views and 4–5 subscribers each (the 18/10 and 19/10 Shorts). Almost every new subscriber came from a Short.

**What blocked publication on 21–23/10**
- The designated reviewer (free tier) returned 503 continuously.
- pilot-009 and pilot-011 failed QA on the image repeat gap (E46).
- pilot-008 failed the owner floor of 9 (pacing 6.5, spelled "G-O-D"; E47, E48).
- All four pilots then left the queue when their slots passed (E49).

**Decision**
1. **Stock.**
   - 008–011 are corrected and re-rendered with ≥ 18 R10 backgrounds and moved to 24–25/10 (#278).
   - New original scripts 013 (night forgiveness) and 014 (morning family) fill 26/10 (#279).
   - Runway: 3.0 days.
2. **Allocation.** Two long videos a day stay as long as the reviewer allows it. The free limit is 20 requests a day, and each long video plus up to 3 Short candidates uses 4 or more.
3. **Shorts first for subscribers.** Once the reviewer answers, Shorts reviews for the already-published 006/007 and the new pilots get the remaining daily requests. Shorts are the only format with measured subscriber yield.
4. **Unchanged.**
   - Zero additional cost: billing and paid reviewers stay off.
   - The owner floor of ≥ 9 and the frozen gates stay.
   - The night sleep-scripture-long format waits until the publication path works again. Building it now would add a third blocked format.
5. **Dot.** The owner ended Dot's role on 23/10. Claude writes scripts, code and fixes, and the GitHub workflows do the heavy work (images, render, review, upload).

## Research: viral layer + authenticity layer, fused as R13 (2026-10-23 evening)
Owner: "work the viral format to explode fast, then the authenticity and originality layer for continuity; research beyond the mining and fuse both". Web research 2026-10-23 (secondary sources: creator-education blogs and vendor guides, the YouTube Help Center could not be fetched from this environment; figures are rules of thumb, not measurements):
- **Viral layer.** The first 30 s decide recommendation; the common frame is pattern interrupt (0–5 s), concrete promise (5–15 s), commitment to what comes next (15–30 s); 60–70 % kept at 30 s is the usual target. Mid-video: promise, deliver, promise the next. Series and playlists convert viewers into subscribers (binge). Shorts discover, long videos convert: a Short should be a hook clip pointing to the full video, on-niche. A devotional channel ("Daily Jesus Devotional") reportedly reached 300K subscribers in 90 days with synthetic voice and stock visuals (self-reported, unverified).
- **Authenticity layer.** YouTube renamed "repetitious" to "inauthentic content" (July 2025): mass-produced videos "made with a template with little to no variation" lose monetization at channel level; secondary sources name generic synthetic narration with no emotion or insight and near-identical narrated videos. The same intro/outro is allowed.
- **Where we stood.** R12 hook, 12–18 min, original specific prayers, exact KJV, licensed 1440p footage, no copied content. Missing: roadmap and re-hooks, a community ritual, explicit format variation, a more expressive voice.
- **Decision (R13, STANDARD).** Roadmap within 30 s, a re-hook at least every 3.5 min until the commitment, a spoken prayer-request invitation answered in the next prayer of the series, and archetype alternation (passage walk-through / topical / retold narrative). Applied to 008–014 (15.6–16.4 min). Shorts become hook clips of the long video with a pointer to it (next). Voice: test Chatterbox (MIT, emotion control) on a 60 s sample against Kokoro on the free CPU runner; switch only if clearly better and the 15-min render fits.
- **Not claimed.** None of this is measured on our own channel yet; the first renders under R13 are the test.

## Algorithm study: what promotes and what kills (2026-10-23 evening)
Owner: "understand what the winners have in common and what the ones that do not grow have in common; this is the gold of the operation". Full report and raw data: `evidence/vidiq/20261023/algorithm_study/REPORT.md` (811 videos ≥ 10 days old, 23 channels, 98 niche breakouts, transcripts of 4 winners and 4 dead videos; strict tests inside the same channel and month, permutation p-values).
- **Kills.** A date, weekday or month in the title (dead ×10, p = 0.001); format hopping (all 4 never-grew channels); short videos on a cold channel; clever titles nobody searches; 10–17 min night videos.
- **Promotes.** Gratitude themes (dead ×0.35, p = 0.002); ≥ 90 min sleep content (never dead, p = 0.008); "hook | search phrase" titles (hit ×2.0, p = 0.009) with one emoji (×2.3, p = 0.010); morning prayers of 12–35 min; daily cadence in one format (fat-tailed outcomes: growth is the rare 30–400× video).
- **Does not decide.** Script quality on a cold channel (the dead videos' scripts are as good); copying a surging title (16 % vs 17 % baseline).
- **Unlock.** Growers broke out at upload #12, #12, #18 and #30 (14–64 min, gratitude or protection); 4 of 8 cold channels never did.
- **Decision.** STANDARD R14 (title gate in `script_check`), and pilots 008–014 retitled. Night videos move to ≥ 60 min, then ≥ 90 min (renderer: a low-cost long sleep section). The first-week themes favour gratitude.
- **Owner decisions (outward, not taken).** Make the 18 off-niche July Shorts and videos private (prophecy and motivation, tagged #marvel and #theflash), and consider a niche display name.

## Compare everything: metadata, picture and sound (2026-10-23 night)
Owner: "compare everything… structure, every detail, so we only produce what the algorithm delivers".
- **Metadata (334 hit or dead videos).** Bible references in the description: hit ×0.33 (p = 0.007). A subscribe ask in the description: hit ×3.27 (p = 0.014). Upload hour, chapters, tags, hashtags and links do not decide.
- **Picture and sound (20 watched with vidIQ).** Quality does not separate: hits 6.9, dead 6.8. Our two videos scored 9 and 8.5, the best of the sample, with 6–40 views. The same channel with the same template has both outcomes (Grace & Purpose 287K vs 98; Favor for Today 54K vs 73).
- **Decision.** STANDARD R15: no Bible references in descriptions or chapter names, and a subscribe line in every description. Intros of 008, 009, 011 and 014 are rewritten. Thumbnails are measured by `thumb-study.yml`.
- **Leaning, not adopted (HYPOTHESIS).** A persistent "Type Amen 🙏" badge (4 of 9 hits, 2 of 8 dead). No female voice among the hits.

## Thumbnails (2026-10-23 night)
- **Measured.** 806 thumbnails of the study (`thumb-study.yml`). Saturated: dead ×0.29 (p = 0.003). Blue-dominant: hit ×0.26 (p = 0.008). Faces, brightness, text amount and contrast do not decide.
- **Seen.** Breakouts: huge bold text across the frame (search phrase on top, hook below), warm gold light, one template per channel. Dead: dark, cool, desaturated, thin small text (a whole channel of them never broke out), dated thumbnails.
- **Ours before.** Darkened frame, text in the right half at most 14 % of the height: the dead style.
- **Decision.** STANDARD R16: breakout layout over the warmest still, and a thumbnail ruler in every render.

## Voice A/B judged by the ruler (2026-10-23, run 39993253146)
The same 4-segment opening of pilot-010 was narrated by Kokoro (am_michael 0.85) and Chatterbox (MIT, cloned from our Kokoro), then measured by `voice_judge.py`.
- Kokoro: WER 0.016, F0 112 Hz, 3.58 semitones, 135 wpm, pauses 0.72 s (max 1.94 s), 0 glitches. PASS.
- Chatterbox calm: one audible glitch (FAIL). Chatterbox warm: 153 wpm, too fast (FAIL). Both took about 10 CPU s per audio s, which is about 2.7 h for a 16-minute prayer.
- **Decision.** Kokoro stays. The study's breakout voices all speak at about 60–120 wpm, slower than our 135: a slower Kokoro speed is the next voice test, measured by the same ruler.
- **Speed test (run 40004867140).** The verified voice engine accepts 0.80–1.25. Kokoro 0.80 measured 124 wpm but had one glitch (FAIL); 0.85 measured 135 wpm and passed. Kokoro stays at 0.85; the narration's pace is not the lever within the frozen QA band.

## Owner pendings resolved (2026-10-23 night)
- **July off-niche items stay public.** Owner: "keep it as it is unless the analysis shows a real need". The analysis does not: the 11 July Shorts brought 43 of the channel's subscribers and are its best-retained videos (56–692 % average view percentage); making a video private does not remove its subscribers, and the format-hopping finding (K2) is about what a channel keeps uploading, not about its archive. The 5 titles flagged as policy-risk total 2.9 watch hours; none has a strike. No change.
- **Display name.** Every one of the 23 growing and never-grew channels sampled has "Prayer" in its name (HYPOTHESIS, not measured), and our watermark already reads "HeroVerse Prayer". Renaming the channel title is a YouTube Studio action (the Data API does not change it), so it stays with the owner: Studio → Customization → Basic info → Name: "HeroVerse Prayer". The handle and the subscribers do not change.
- **E57 (runner token 401).** Renders no longer wait on HERO_RUNNER_PAT: when the runner cannot be woken, the heartbeat renders on the engine.
- **E58 (reviewer 503).** The designated reviewer is asked again within the run after 2, 5 and 10 minutes when it is overloaded.

## Reviewer down: root cause and what changes (2026-10-23 night)
- **Root cause (measured).** The designated reviewer `gemini-3.8-flash` does not answer our free key at all: a 5-token text call timed out, while `gemini-3.6-flash` and `gemini-3.5-flash-lite` answered in under 1 s with the same key (`evidence/reviewer-probe/`). Google's developer forum has the same report for free-tier 3.8-flash, including one-line text requests, and notes that 503 answers may count against the daily allowance. It is a provider outage, not our file.
- **Wrong first fix, undone.** Retrying within the run (E58, first version) only spent the allowance on a reviewer that does not answer. Owner: "do not keep trying; fix the problem, then try again".
- **Replacement measured, refused.** `gemini-3.6-flash` was calibrated on six renders the designated reviewer judged (five PASS, one FAIL). It failed all six (overall 6.0–7.0, mean −2.2) and scored the FAIL render (008, 7.0) as high as the best one: it does not reproduce the designated judgement, so it does not replace it. The bar is not lowered.
- **Now.** Every review asks the reviewer one tiny health question first; while it is down, no video call is made. The review runs again only when the health question is answered.

## Corrections (2026-10-24 early)
- **The reviewer is intermittent, not dead.** At 22:35 UTC reconcile's retry reached `gemini-3.8-flash`: pilot-010 PASS, overall 9.5; approved, uploaded and public at 00:00 UTC (`9g2MeIit9ys`). The probe at 22:57 then timed out again. The health check (E58) stays: a down reviewer costs one tiny call; an answering one reviews.
- **The runner never stopped.** It renders on its own cron (:13 and :43); only the engine→runner wake-up needed HERO_RUNNER_PAT. E63 keeps the engine fallback from rendering beside a live runner.
- **Fixed tonight:** E60 (render > 2 GiB lost), E61 (first comments left PENDING), E62 (images lost when the Cloudflare allocation ran out), E63 (duplicate render).

## The reviewer is replaced: Claude reviews long videos (2026-10-24)
- **Owner.** "I need to replace it; I cannot have this in the system; find another AI." Then "Ok" to Claude.
- **Candidates measured** (`evidence/reviewer-probe/`, `evidence/reviewer-calibration/`): the omni models have no free quota; 3.7-flash and flash-latest hang like 3.8; 2.5-flash approves everything (9–10, the FAIL render included); 3.5-flash runs out of daily quota after four reviews; 3.6-flash and 3-flash-preview score about 7 on every item and cannot tell a good render from a bad one (3-flash-preview also 503s). None passed.
- **Decision.** Claude is the designated reviewer of long videos (`ops/CLAUDE_REVIEW.md`): sheets, transcript, thumbnail, QA audio measures; same rubric, gate and owner floor 9.5; every score below 9.5 names its issue. `long_review.py` makes no provider call; without a valid Claude review for the render's hash the status is AWAITING_REVIEW. Shorts move to the same reviewer next.
