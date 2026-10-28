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

## Daily analysis, day 7 (2026-10-24 08:06 UTC)
- **Measured [official, vidIQ snapshot].** Subscribers 274 (+2 in 24 h); long-form public watch hours about 7 / 4,000 [own, report of 23/10]. Needed by day 14 (31/10): about 91 subscribers and 570 watch hours a day. Distance factor about 45× (subscribers) and several hundred × (hours). Day 14 is not reachable at this pace; day 30 is not either without a breakout.
- **Per video.** 010 (first R14–R16 video, public 00:00): 6 views, 1 comment, in 8 h. 007 (`NGfnyTul-K0`): 76 views, outlier ×4.1 (from 1 view on 23/10). Shorts keep bringing the subscribers (299 views and 5 subs, 199 and 4).
- **Decision.** (1) Keep one format per slot, morning and night daily (K2). (2) The lever for watch hours is length: night videos move to ≥ 60 min with a low-cost Scripture-for-sleep section (P2: ≥ 90 min never dead); this is the next renderer work. (3) Shorts move to the Claude reviewer so they publish daily again (subscribers). (4) Script runway: scripts exist to 014 (26/10 10:00); 015+ are written before 26/10.
- **Why.** The study's unlock pattern is many tickets in one format plus long night content; nothing measured on our channel contradicts it yet (010 is 8 h old).

## Daily analysis, day 8 (2026-10-25 08:06 UTC)
- **Measured [official, vidIQ].** Subscribers 280 (+6 since 24/10 11:33). Long-form public watch hours about 9 / 4,000
  [own, report of 24/10]. Needed by day 14 (31/10): about 120 subscribers and 665 watch hours a day; distance factor
  about 20× (subscribers) and far beyond (hours). Day 14 is out of reach at this pace.
- **Per video.** Bible Shorts lead from day one: Genesis 2 (`hwq4qgjreh0`) 192 views in 8.5 h (24 vph, breakout 48,
  27 likes); Genesis 1 (`ku2MTQKmXaU`) 107 views (breakout 14). The best prayer Short of October took 7 days to reach
  292. Prayer long videos: 007 96 views (breakout 5.2), 010 15 views in 32 h; the others 8–41.
- **Decision.** (1) Shorts stay at 2 a day in story order (Genesis 3 at 13:30, Genesis 4 at 23:30 are scheduled;
  Genesis 5 on 26/10 13:30; Genesis 6 is made after the credit day resets). (2) The first long Bible compilation
  (Genesis 1–6, SERIES.md "Long: every 3 days") is built as soon as Genesis 6 exists. (3) Open question to the owner:
  SERIES.md says the prayer long videos stop after 011 (format hopping, K2), while 013, 014, 008 and 009 are still
  rendering for 26–27/10 under the "a long video every other day" clock rule; they keep going until the owner chooses.
- **Why.** Two of two Bible Shorts beat every prayer Short of the series in their first day; nothing measured favours
  the prayer long format (best 96 views in 4 days).

## Owner decision: the long videos join the Bible series; Shorts lead to the long (2026-10-25 13:30 UTC)
- **Owner.** "Mantém [o que está pronto], mas depois passa para a mesma ideia do short ... o short tem que seguir o
  padrão do longo e o longo do short ... o short direcionar pro vídeo longo; monta uma estratégia efetiva."
- **What stays.** The prayer long videos already rendered or rendering keep their slots: 013 (26/10 00:00), 014
  (26/10 10:00), 008 (27/10 00:00, rendering). pilot-009 (not rendered for its current script) leaves the queue
  (`schedule.retired.json`).
- **Strategy (SERIES.md "One format, two lengths").** Arcs of 4 Short episodes = 1 long video telling the whole
  story (14-18 min) every other day at 10:00 UTC from 28/10; Shorts point to their arc's long (CTA, first comment,
  Studio related video); the long's chapters are the Shorts' titles, its cold open is the arc's hook shot, and it
  ends on the next arc. Same title formula, voice family and picture style in both.
- **Why.** Bible Shorts 107 and 192 views in their first day vs 8-96 for prayer longs; mined long winners in this
  line tell one Bible story per video (evidence/vidiq/20261025, structure `bible-story-long`, candidate).
- **Budget found.** 3,811 vidIQ credits must last to 18/11 (about 159 a day), less than two 100-credit Shorts a day:
  Shorts are held to about 75 credits and the long is rendered free on the engine (Kokoro `bm_george`).
- **Next.** The engine gets a story-format spec and its own frozen QA (`production/bible/long/`), technical floors
  equal to v4; first long (Gen 1-3) rendered and reviewed before 28/10 10:00.

## Owner decision: TikTok mirrors the Shorts (2026-10-25 15:20 UTC)
- **Owner.** "Every Short on HeroVerse also on TikTok (@heroverse.official), the old ones too; whenever one posts, the
  other posts." This reverses "TikTok: not now" (day-6 cross-platform note), which was about Creator Rewards income;
  reach for the long videos is the goal here.
- **How.** The free Content Posting API, no scheduler service (no MCP posts organically to TikTok; the registry has
  only ads and shop connectors). `tiktok.yml` posts one Short per run after each Short slot, oldest first, with the
  same file and TikTok's AI-generated label. Until TikTok audits the app (2-6 weeks), posts arrive as drafts in the
  TikTok app (inbox) and the owner taps "Post". Only Bible Shorts kept in the release can go; the prayer Shorts' files
  were deleted after their YouTube upload.
- **Owner action (once).** Developer app (Login Kit + Content Posting API) with the compliance site's privacy, terms
  and callback pages; secrets `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `GH_SECRETS_PAT`; then `tiktok-auth.yml`.

## TikTok goes through Buffer's free plan (2026-10-25 17:00 UTC)
- **Rule found.** TikTok's Content Sharing Guidelines list "a utility tool to help upload contents to the account(s)
  you or your team manages" as not acceptable for the Content Posting API audit; without the audit, posts are private
  only. Our own developer app (HeroVerse Channel Operations) stays in Draft, nothing submitted; its secrets are kept.
- **Owner.** "Everything automatic" and "TikTok is the door to the long videos on YouTube". Buffer's free plan
  (3 channels, automatic publishing, public API on every plan) publishes with its own approved TikTok app. The owner
  connected @heroverse.official in Buffer (Free, Automatic) and saved `BUFFER_API_KEY`; no card, no payment. This is
  the owner's exception to "no schedulers" (CLAUDE.md), free only.
- **Door to the long.** Each caption names the story's full video on YouTube and sends to the link in bio (TikTok
  captions are not clickable); the bio link points to the channel or the arc's long; the Short's spoken close already
  sends to the full story (short rules from part 6).

## Agnes Video (Pavo) on trial (2026-10-25)
- **Owner.** "This video AI is very good; integrate it." No MCP or connector exists; Agnes AI has an API (free Flash
  tier: 720p, 4-12 s, daily credits). `AGNES_API_KEY` saved by the owner.
- **Status: test only.** Its terms page shows template placeholders and the consumer app says watermark removal may need
  a paid plan, so commercial use and a clean free output are not confirmed. `agnes-clip.yml` makes one clip as a run
  artifact for review; nothing goes into a Short until the terms are read and a clip is seen clean. If it passes, it
  replaces vidIQ's 60-credit hook clip in the Shorts (720p meets clip_check's 720 floor); the long keeps QA v4's 1440p.


## Pavo is the first source of AI video (owner, 2026-10-25 22:40 UTC)
- **Owner.** "Encaixe o Pavo em todos os lugares que ele conseguir estar ... o vidIQ não precisa gastar o crédito
  dele para gerar tendo o Pavo; fica só como segunda opção ... não precisa esperar ele para continuar as produções."
  Commercial use confirmed by the owner; Pavo's terms (app.pavo-ai.work/terms, read 2026-10-25) say the same: the user
  keeps ownership of generated content (§42) and is responsible for reviewing public and commercial use (§44); Pavo's
  own AI-content marks are never removed (§54, the channel discloses AI on every video anyway).
- **Standing authorization (owner, 2026-10-25).** Pavo generations no longer wait for a "yes" in the chat. The adapter's
  limits stay: a fresh exact zero-credit quote per call, one video per call, an uncertain submission is only read back
  with `pavo_job`, never resubmitted. `PAVO_RATE_LIMITED` refuses before any job exists, so that call is sent again later.
- **Order for every AI clip:** Pavo (`heroverse-pavo` MCP) → Agnes direct (`agnes-clip.yml`) → vidIQ `generate_video`
  (credits) only when both fail. vidIQ credits now go to voice, stock search and compose (~45 a Short instead of ~105).
- **Shorts: almost all AI (owner, 2026-10-25: "quase tudo IA").** This replaces "AI video only at the hook and the
  peak" (24/10, set to save credits). Every scene still follows its words (the moon on "the moon"), passes
  `clip_check.py` with its audio stripped (Pavo returns an AAC track even with `sound: false`), and the frame sheet
  review at 9.5; real footage is used where it shows the words better. People only from the character bible
  (reference mode); a person not yet in the bible is not shown (footprints, objects, landscape instead).
- **Long: 50 % Pavo, 50 % licensed footage (owner, 2026-10-25).** Frozen QA v4 asks >= 60 % real footage, sources
  only under its listed licences and >= 1440p, and the owner's "never below 1440p (no plain upscale)"; Pavo is 720p. So
  the long can take Pavo only through the story format's own QA (SERIES.md, `production/bible/long/`), written and
  frozen before pilot-015's first render, with the v4 technical floors unchanged (2560x1440 output, loudness, speech,
  black scan) and each Pavo clip brought to 1440p by Real-ESRGAN (the stills' upscaler, not a plain resize) and
  checked frame by frame. No frozen v2/v3/v4 file is edited. Owner, 2026-10-25 23:20 UTC: "todos os OKs ... eu dou
  autorização": `production/qa_criteria_story_v1.json` (story-qa-criteria-v1) is frozen before pilot-015's first
  render: v4's technical, speech and grammar rows unchanged, real licensed footage >= 40 % of the picture, Pavo <= 55 %,
  Pavo clips only as library records (source pavo, Real-ESRGAN to 2560x1440, vetting APPROVED). `render_pilot.sh` uses it
  for `archetype: bible-story-long`; the gate, the queue and hookify know its hash.

## The Keeper narrates every video; scenes show the story, not landscapes (owner, 2026-10-26)
- **Owner.** A narrator character in every Short and long, on screen, moving and talking to the viewer, for originality
  and monetization; "every scene gourmet"; "you still prioritise landscapes, it makes no sense: with Pavo make
  cinematic scenes with modern effects"; voice quality must not drop; use Pavo's audio features.
- **Evidence** (`evidence/research/20261026-format-study.md`, quotes from search excerpts, channel numbers are
  estimates): generic photoreal AI Bible channels are saturating (The AI Bible +4K subs in 30 d at 413K); character-led
  Bible content leads (Superbook ~12M); YouTube's inauthentic-content targets are "nearly identical narrated
  slideshows" and "minimally altered story variations", so a recurring original host plus scenes that act out the story
  is the strongest originality signal we can add. No controlled study proves a host lifts views: it is a hypothesis.
- **Decision.** The Keeper (`characters.json`, DRAFT until its sheet is reviewed): an invented elderly storyteller in a
  lamp-lit stone room with an old Bible, never a biblical person, prophet, priest or angel. He opens each Short (0-2 s
  hook), hands to the story and returns for the insight and the close (at most ~25 % of a Short); in the long he opens
  the cold open's roadmap and every chapter re-hook. Story scenes are acted out with the character bible's people in
  reference mode, a cut every 2-4 s and one VFX moment every 15-20 s; landscapes only as a 1-2 s establishing shot.
  Style: painterly-cinematic realism (Old-Master light, one grade, film grain). God the Father only as light, wind,
  fire or voice.
- **Voice.** The narration keeps a quality at least equal to the published Shorts: a free voice (Kokoro or
  Chatterbox) replaces vidIQ's George only after `voice/voice_judge.py` and Claude's listening review find it not worse;
  the Keeper's lip-sync takes our narration as Pavo input audio (v0.4), so the voice never changes between host and
  story.
- **Measured** (live intelligence, one hypothesis): `host` on the next 4 Shorts against the last 4 without: viewed vs
  swiped, average % viewed, subscribers per 1,000 views, Short-to-long clicks. KEPT if not worse.

## Shorts v2: the conflict spoken first, characters speak, the Keeper at the close, 170-179 s (owner, 2026-10-26)
- **Evidence** (`structures/bible-story-short.json`, validated 2026-10-26: 6 winners from 6 channels, breakout >= 50,
  3 weak contrasts; `evidence/vidiq/20261026/bible_story_shorts.json`): drivers counted on winners vs weak: an
  antagonist or opposing power on screen from the first shots (6/6 vs 0/3) and a runtime of 170-179 s (5/6 vs 0/3);
  the conflict hook in the first 2 s (a character's challenge, never atmosphere) in every winner; acted, lip-synced
  dialogue is hygiene (winners and weak alike); no winner has a narrator on screen (the Keeper stays our hypothesis);
  the lesson takes 0-28 % in winners, 41 % in the weak Noah Short. Limits: 6 winners is the minimum, presence from
  one vidIQ audit prompt, the beat positions measured in 2 winners only.
- **Owner decisions.** (1) Shorts from part 7 run 170-179 s, measured with the tail, under YouTube's 180 s limit
  (first set at 100-150 s the same day, replaced by the measured driver); parts 1-6 keep 62-90 s
  (`publish_episode.short_length`). (2) The first shot is a scene whose first words are the conflict, spoken by a
  character or God's voice (God never shown as a person: a voice over light, storm or fire); the Keeper never opens.
  (3) Characters speak their own lines, lip-synced: a scene shot's `speaker` + `line` (KJV exact when Scripture),
  synthesised in the speaker's own Kokoro voice, sent to Pavo as input audio with its references and judged by
  `lipsync_check` (same thresholds); God's lines are Scripture only, a deep voice-over, no lipsync. Voices (preserved
  model voices-v1.0.bin): the Keeper am_michael (unchanged), Adam am_fenrir, Eve af_heart, the serpent bm_fable,
  Noah bm_george, God am_onyx at 0.9. (4) The Keeper only after the climax, for the insight and the close, <= 25 %.
  (5) The lesson (insight + cta + Keeper) <= 25 %, aim <= 15 %; the climax acted (`climax: true`). (6) Noah joins the
  character bible as DRAFT (fixed look, wardrobe, voice, reference prompts in `characters/images.json`); Claude
  approves him after reviewing his sheet; until then he is only a faceless silhouette. (7) Genesis 7 rewritten on the
  beat map: God's Genesis 6:13 at 0 s over the darkening storm, three acted steps of the corruption with anonymous
  figures, God's Genesis 6:7 as voice-over and right after it the acted climax (the wicked crowd scattering, 66 %; E92), Noah's grace as payoff, the Keeper's insight, a comment question and
  "Part eight tomorrow: Noah builds the ark"; measured locally with Kokoro at 173.9 s, Keeper 11 %, lesson 11 %.
- **Where.** `plan_check.py` (`bible-plan-v2`), `episode_build.py` (speaker WAVs, lipsync on every talking clip,
  measured length, Keeper and lesson shares), `short_engine.talk_problems`, `pilot_render.py voice` (a segment may name
  its voice), `characters.json` (`voice`, `god`, Noah), PROMPT_GUIDE "Keeper + acted scenes", SERIES.md.
- **Measured** (live intelligence): Genesis 7 v2 against parts 5-6 on viewed vs swiped, average % viewed, subscribers
  per 1,000 views and Short-to-long clicks. KEPT if better.


## 2026-10-26 (day 9) — daily analysis: the YPP goal by day 14 is out of reach; the Bible arc and its long carry the plan

- **Measured** (goal report 08:53 UTC; [official] Data API, [own] Analytics rows): subscribers 285 (+4 since 25/10 12:17,
  needed 119/day to day 14); public long-form watch hours 21.6 [own] (+8.2 h, needed 663/day); public Shorts views
  90 d 538 [own] (the Shorts path needs 10 M). Distance factor: subscribers ~30x short, watch hours ~80x short. The
  Bible Shorts get 112-242 views each in the first day (parts 1-4), the prayer longs 0-78 views; no long has any
  traffic from Shorts yet (funnel section: NO_SHORTS_TRAFFIC on all 10, the prayer longs have no linked Shorts).
- **Reading.** Monetisation by 31/10 (day 14) is not reachable at any realistic rate; 16/11 (day 30) needs the long
  series to earn its own browse/suggested traffic. Nothing in the data supports more prayer longs: the old niche's
  longs (pilot-008 on 27/10 00:00, already scheduled) are the last.
- **Decision of the day.** (1) Keep 2 Bible Shorts a day (13:30 and 23:30 UTC): Genesis 5 today 13:30, Genesis 6
  today 23:30 (the reviewed landscape version unless the new format is ready by 19:30), Genesis 7 tomorrow 13:30
  (new format; build resuming after E93-E95), Genesis 8 tomorrow 23:30 (plan in writing). (2) The first Bible long
  (arc 1, pilot-015) stays on 28/10 10:00 with the long beat map (structures/bible-story-long.json script) and the
  arc links (#404). (3) Noah's reference sheet generated today (cf-images) so he can speak from part 8. (4) The
  daily vidIQ mining moves to the long's package (title, thumbnail) with more weak contrasts.
- **Execution today.** E93 (Pavo outage waited out, resume), E94 (failure evidence), E95 (talking-clip binding: clip
  length ~ speech, prompt binding, speaking reference) in progress; heartbeat driven by the hourly clock.

## Owner decision: prayer videos stop; the long cadence counts Bible-story longs only (2026-10-26)
- **Owner.** "Stop the prayer videos; the channel is going in another direction." And: the long must stand on its own,
  Shorts traffic only a plus, following its own registered structure, `structures/bible-story-long.json`.
- **Kind.** A direction change, not a failure: no `ERRORS.json` entry for it (the review of #415 found two real bugs, E100 and E101). It replaces the 2026-10-25 "what stays" rule
  (prayer longs already made keep their slots).
- **Stopped at the source (code).** `render_queue.story_pilot` (archetype `bible-story-long`) is the one test of a long:
  a prayer pilot no longer enters `due()` (so no images, preview, render, Claude review, approval, publish or Shorts
  from the heartbeat, runner, engine fallback or reconcile), is never reported stale for rescheduling, gets no
  first-comment retries, and `pending_shorts.py` publishes no Short of it. The publication gate refuses it too:
  `prepublish_gate.py` has a `format` row (FAIL `NOT_STORY_LONG`), and `publication_binding.py`, which publish.yml
  runs before any upload or resume, refuses `NOT_STORY_LONG` even with an older approval and a PASS gate.
- **Long cadence rewritten.** The old runway demanded a long at every 00:00 and 10:00 UTC slot (two prayer longs a
  day, never a day without one). `ops/runway.py` now checks one Bible-story long every 2 days at 10:00 UTC from 28/10
  (= `production/bible/arcs.json`). One stage rule (`runway.long_stage`, also used by the daily report): uploaded,
  approved, rendered, then "script" only when the full `script_check` passes, including the structure's gate
  (`script.gate`, `script_check.structure_problems`: 14-18 min, an APPROVED character or God's voice speaks the
  conflict in the first 30 s, >= 6 re-hooks, one climax at 0.6-0.85, the Keeper in every long, <= 25 % and never in
  the cold open, no burned captions), else "script-fail" with its problems. A prayer pilot still scheduled ahead
  alerts `PRAYER_LONG_SCHEDULED`. The daily report's runway alert asks for Bible-story long scripts ("LONG SCRIPT
  RUNWAY"), not pilots.
- **Already uploaded.** pilot-008 (`8heTdP0LllM`, 27/10 00:00) and pilot-014 (`53Xysf9x46c`, 26/10 10:00) are listed in
  `channel/hold-plan.json` for `channel-privacy.yml` mode `unschedule` (private, publishAt cleared, nothing deleted,
  the receipt keeps the old publishAt for the undo). A video already public is skipped, never hidden, and named in
  the log (`HELD_VIDEO_ALREADY_PUBLIC`, an Actions warning) and in the receipt (`already_public_not_changed`). It runs
  only when dispatched.
- **Measured.** The daily report's long runway and the arc funnel; pilot-015 is the first long on this rule.

## Owner decision: story QA v2, no burned captions on the long (2026-10-26)
- **Owner.** "Nova régua, sem legenda." The Bible-story long carries no captions burned into the picture (the mined
  structure: burned captions read anti, winners 1/7, weak 2/3; `script.gate.burned_captions` false), and the frozen
  story QA v1 demanded burned-caption coverage >= 0.95, so only a new frozen version could change it.
- **Done.** `production/qa_criteria_story_v2.json`, frozen before the first Bible-story long render: v1 unchanged
  except the caption rows, replaced by an uploaded .srt track (YouTube closed captions) held to the same numbers
  (coverage >= 0.95, cue median 1.5-5 s, <= 44 characters, <= 7 words). `qa_criteria_story_v1.json` stays frozen and
  byte-identical (sha256 5dcf63f9...); `bible/test_long_plan_check.py` asserts both. Its sha256 is pinned in
  `bible/long_plan_check.py`; `qa_pilot.py`, `render_queue.py` and `prepublish_gate.py` learn v2 with the long's
  build (publishing code untouched here).
- **Kind.** A rule decision, not a failure: no `ERRORS.json` entry.
- **Still open for the owner** (`production/bible/LONG_DESIGN.md` section 4): v2 keeps v1's no figure on screen,
  >= 40 % real licensed footage, <= 55 % AI video and a 4-7 s title card first; the acted long with the Keeper on
  screen meets none of them, so its first render needs one more frozen version decided by the owner. Also: the arc-1
  long's scope (Genesis 1-7, as asked, vs arcs.json arc-01 Genesis 1-3) and the 1440p upscaling cost (~1,300-1,600
  runner-minutes a long). All three decided the same day (next two entries).

## Owner decision: story QA v3 for the acted Bible long; the long follows arcs.json (2026-10-26)
- **Owner.** "Sim, régua nova": a new frozen `production/qa_criteria_story_v3.json` for the acted Bible long. It is v2
  with only the three conflicting rules replaced by the structure's own: (1) figures: approved characters on screen
  are allowed (v2: none); (2) AI share: 100 % Pavo is allowed, provided each clip passes clip_check and every talking
  clip passes lipsync_check (v2: >= 40 % real licensed footage, <= 55 % Pavo); (3) the first shot: the acted
  cold-open conflict replaces the 4-7 s title card. Everything else is v2's, unchanged: audio, loudness, pace, the
  4-7 s holds, the .srt track, the 9.5 floor and the Claude review. Frozen before any render; v1 and v2 stay
  byte-identical (`bible/test_long_plan_check.py` asserts all three).
- **The exact rows (v2 -> v3, `grammar` only; v3's `basis` points to this entry).** This relaxes three v2 rows, by the
  owner's explicit decision of 2026-10-26 ("Sim, régua nova", relayed and recorded by the coordinator):
  | v2 row | v3 row |
  |---|---|
  | `title_card_seconds` [4.0, 7.0] | `first_shot`: the acted cold-open conflict, spoken from 0 s, never the Keeper |
  | `figure_present_fraction_max` 0.0 | `figures_allowed`: characters.json APPROVED only (look word for word, approved references), the Keeper only in his shots, anonymous figures from behind |
  | `footage_picture_share_min` 0.4, `footage_picture_share_counts`, `ai_video_picture_share_max` 0.55 | `ai_video_picture_share_max` 1.0 and `ai_video_clip_checks`: clip_check on every Pavo clip, lipsync_check on every talking clip, the face check on God's voice-over clips |

  Every other key of v3 equals v2's (version, frozen_at_utc and basis aside); the test refuses any other difference.
- **Not yet readable (build blocker).** `qa_pilot.py` and `prepublish_gate.py` index v1's keys directly and the gate
  knows only `story-qa-criteria-v1`; no renderer or gate may point at v2/v3 until they read the new keys (slice 3,
  guarded by `bible/test_long_plan_check.py` NoRendererReadsTheNewQaYet).
- **Done.** `long_plan_check.py` checks the plan against v3 (sha256 pinned): the QA_CONFLICT_* owner rows of v2 became
  checks (the cold open, approved characters only with DRAFT ones pending, every talking speaker a human face:
  TALKING_WITHOUT_A_FACE, so the serpent stays silent and the Keeper narrates its words).
- **Scope.** The coordinator's "Genesis 1 to 7" was a mistake: the long follows `bible/arcs.json`. arc-01 is Genesis
  1-3, Shorts 1-4, one complete story; `bible/plans/arc-01-long.json` is rewritten for that scope (Adam, Eve, the
  serpent silent, God as a voice, the Keeper), no Cain or Abel for now. It passes `long_plan_check.py --strict`.
- **Kind.** Rule decisions, not failures: no `ERRORS.json` entry.

## Owner decision: thumbnails show the story character, approved before publish (2026-10-27)
- **Owner.** The thumbnail shows the STORY CHARACTER (APPROVED in characters.json, by reference: the same look every
  time), a close-up face with a clear emotion, text of at most 4 words, no Keeper/host face by default. Built for no
  rework: the thumbnail is a candidate reviewed BEFORE publish, with the episode's stills, and the publish step only
  uploads an approved thumbnail.
- **Evidence (PR #458, `evidence/vidiq/20261027/thumb-host.json`).** Bible-story long winners (36 from 31 channels,
  max 3/36): story-character face 30/36 vs weak 3/3, host face 2/36 (both church recordings), presenting gesture
  3/36, arrow 0/36, the host formula 0/36. The host idea is NOT validated (`structures/bible-story-long.json`
  package.not_validated.thumbnail_recurring_host); only our own A/B could test it, so the Keeper is allowed only as a
  spec's `variant {ab: true, owner_approved: ...}`. Character face is hygiene (6/7 vs 3/3 in the package block), not a
  validated driver; text <= 4 words is free (4/7 vs 1/3) and kept as the owner's rule.
- **How.** `production/bible/thumbs.py` (spec, check, refs, finalize, sheet, approve, verify); refusals class A in
  `ops/refusal_registry.json` (THUMB_*); `publish_episode.problems` from part 9 and `publish_video.bible_thumb_problems`
  for a Bible long (both reached early by check-record and `publish/preflight.py`). Published parts 1-8 keep theirs.
- **First candidates.** genesis-09-short run 20261027, 2 candidates, not approved
  (`evidence/thumbs/genesis-09-short-20261027.json`).
- **Kind.** A rule decision, not a failure: no `ERRORS.json` entry.

## Owner decision: Pavo freed in the long, no real-footage minimum (2026-10-27)
- **Owner.** "Libera o pavo no longo." The Bible-story long may be 100 % Pavo AI video, with no real licensed footage.
  Every Pavo clip meets the same checks as in the Shorts: clip_check, lipsync_check where someone talks, the reviewed
  clip being the build clip (E114), the single look of the ark (E113) and the period rules. The 9.5 floor is
  unchanged.
- **No new QA file.** The frozen `production/qa_criteria_story_v3.json` (2026-10-26) already says this. It has no
  `footage_picture_share_min` or `footage_picture_share_counts` row, its `ai_video_picture_share_max` is 1.0, and
  its `ai_video_clip_checks` requires clip_check and lipsync_check. QA_CONFLICT_REAL_FOOTAGE is raised only against
  v2 and older, and `long_plan_check.py --strict` on `plans/arc-01-long.json` passes against v3 (problems [],
  pending []). The rework audit was wrong to say that v3 needs footage. A v4 would repeat v3 key for key, so none was
  made, and no frozen file was touched.
- **Guard.** `bible/test_long_plan_check.py` `test_owner_frees_pavo_in_the_long_and_v3_already_holds_it` checks
  three things: v3 has no footage-share row, its AI share is 1.0 with both clip checks, and the arc-01 plan raises no
  QA_CONFLICT_REAL_FOOTAGE or QA_CONFLICT_AI_SHARE.
- **Still open for the arc-01 long (rework audit, fix 3; not fixed here).**
  - Done (E126): `qa_pilot.py` and `prepublish_gate.py` read story QA v3 by its own rows, with no footage minimum;
    `captions.py long` writes the .srt track, qa_pilot checks it and publish_video uploads it; the 23 open
    `refusal_registry.json` story_qa_v3 rows are `render_qa`.
  - Done (E127): the long's preflight refuses while any review row is open (LONG_REVIEW_OPEN), and the long has the
    Shorts' risk order, resume (`probe-queue`) and approved-shot contract (LONG_DESIGN.md section 7).
  - The preview gate has not run on the real opening.
  - Done (E126): SERIES.md points its long paragraph only to LONG_DESIGN.md; the old footage lines are removed.
- **Kind.** A rule decision, not a failure: no `ERRORS.json` entry.

## Owner decision: the repository stays public; optimise the long for wall-clock time (2026-10-26)
- **Owner.** "Manter público." The repository is public, so GitHub's standard hosted runners cost nothing: Actions
  minutes are not the constraint for the long. Parallel jobs (a matrix for the 1440p Real-ESRGAN upscale) and
  submit-and-leave for Pavo are fine; the long is optimised for wall-clock time. (`ops/minutes.py` still reports
  minutes against its 7,000-minute paid budget; it should be read as a usage report, not a bill.)
- **Measured the same day** (`evidence/pavo/20261026/long-16x9-and-concurrency.json`, two direct 0-credit Pavo
  requests from a Claude session, no Actions run): a 16:9 request returns 1280x720 at 24 fps, and two submissions in a
  row ran at the same time (both done within 7 min of the first, the second first), so submit-and-leave works.

## Daily analysis 2026-10-27 (day 10 of 14, max 30)
- **Pace** (latest report 26/10 08:53, [official] subscribers, [own] hours): 285 / 1,000 subscribers (119/day needed
  to day 14); public long-form watch hours 21.6 / 4,000 (663/day needed). Bible Shorts draw 110-300 views each; the
  prayer longs draw 0-78 views and no Shorts traffic (funnel NO_SHORTS_TRAFFIC on all 10). [plan] Day 14 (31/10) is out
  of reach on both counters; day 30 (16/11) depends on the arc-01 long, which is not built yet (slice 3 open).
- **Decision (owner, 27/10: no rework, solve the open problems before producing more):** no new episode builds until
  three system fixes land: one episode in flight (E112, merged #438), one canonical ark look (plan_check rule, in
  progress) and the reviewed probe clip becoming the build clip (in progress). Genesis 8 ships only at 9.5: 26 of 29
  shots and the Keeper approved; s-dust, s-ridge and s-board go through the new reviewed-clip path, slot 23:30 today
  if ready, else the next slot. Genesis 9 (plan merged #436) waits for Genesis 8's record. Keeper lip sync: LatentSync
  chosen on public evidence (`strategy/LIPSYNC_TOOLS.md` to come), decisive test on the 3 lines running.
- **Why:** each repeated build costs a slot anyway (genesis-07: 8 builds; genesis-08: 7 shots rejected after a full
  build). Fixing the cause once is faster than producing more. No vidIQ calls today (0 credits).

## Owner decision: the arc-01 long first; its slot moves to 04/11 (2026-10-27)
- **Owner, 27/10.** "Prioriza o longo agora."
- **Slot.** `arcs.json` arc-01 long (pilot-015) moves from 2026-10-28T10:00:00Z to 2026-11-04T10:00:00Z, and the
  SERIES.md calendar row with it. 28/10 was not reachable: the production estimate
  (`evidence/long/20261027/arc-01-long-production-estimate.json`, `publish.proposed_date`) puts the earliest date at
  02/11 if every step passes the first time, and proposes 04/11 (direct talking probes, ~21 shot-probe runs, 330 frame
  reviews, the 1440p upscale and the 9.5 review). The later arcs' long slots are unchanged here.

## Owner decision: no stall, Pavo speech kept, free fallbacks for silent shots (2026-10-27)
- **Owner, 27/10 ~20:40-21:00 UTC (R4).** Keep Pavo's own audio for the talking shots: the speech of the characters
  and the Keeper plus the natural ambience, in one pass; no music from Pavo (our one owned track goes under the cut);
  judged clip by clip: the exact KJV words (by ASR, medium.en: base.en mis-hears "gavest"), one consistent voice per
  character against a reference clip, lip sync, diction. Our Kokoro voice only for a line Pavo refuses (its prompt
  filter, e.g. "naked"): the hybrid route of PR #473.
- **Owner, 27/10 ~22:50 UTC, for the long and the Shorts, "em qualquer situação":**
  - **R1.** Use every Pavo clip already generated that fits a shot (same shot and request, passing its checks and
    Claude's review >= 9.5); never regenerate what exists.
  - **R2.** Pavo's budget goes first to the spoken scenes (characters and the Keeper speaking, with Pavo's own speech
    and ambient audio; no Pavo music).
  - **R3.** When Pavo's free quota runs out, the remaining non-spoken scenes are filled from other free sources
    coherent with the narration (licensed footage under the frozen licence list via the footage library, or free FLUX
    stills with motion), so the video is produced without stalling. The 9.5 floor is unchanged; every fallback shot
    still matches its line, the period rules and the canonical look rules.
- **What it became** (branch `claude/owner-no-stall`):
  - a new frozen `production/qa_criteria_story_v4.json`: story QA v3 with only `rights.ai_video.audio` changed
    ("removed" -> "pavo speech+ambient kept per clip under checks") and rows added (the pinned medium.en ASR, the
    per-clip speech checks, the Kokoro voice for refused lines, the fallback sources and shots, the spoken audio mix);
    every v3 number unchanged, v3 untouched. A long is measured by v4 only when its plan says
    `"criteria": "story-qa-criteria-v4"` (and `"audio_route": "kokoro"` keeps a v4 long on our voice); a Short's
    `"audio_route": "pavo_native"` is refused by plan_check (AUDIO_ROUTE_SHORT_UNSUPPORTED, review of #476) until a
    new frozen Short criteria file holds the speech-check rows v4 holds for the long;
  - R1: probe-queue lists a shot with a clean clip of its request (main's shot-probe records, the claude/shot-probe-*
    branches, clip inventories) as awaiting review, never as a new generation; a spoken shot with a clean clip of its
    Kokoro-route request keeps that route (R1 wins over R4);
  - R2/R3: `episode_build.py sources PLAN` spends the shared Pavo budget (quota.py, #475) on the risk order (talking
    shots first), gives a silent, character-free shot the budget does not reach a footage or still-in-motion
    candidate, and leaves a spoken shot or a shot with a character waiting (no free source keeps its voice or its
    canonical look); `approve-source` records Claude's review (>= 9.5) of a fallback, never automatically;
  - R4: native requests (prompt A of #473), PAVO_PROMPT_BLOCKED from the adapter with an automatic Kokoro retry, the
    speech checks before approve-shot, and the build's mix (one gain per clip to -18 LUFS, 80 ms fades, a continuous
    ambience bed, the owned music ducked, -15 LUFS loudnorm).

## Slim system applied: the Agnes direct route retired, one clock per job (2026-10-28)
- **Owner, 28/10.** "Enxuga o sistema; se tiver alguma coisa inútil você retira e deixa tudo muito bem orquestrado sem
  retrabalho." Audit `evidence/audits/20261028-slim.md` (#477); its DECIDE items applied in one PR.
- **Agnes direct (`agnes-clip.yml`, `production/agnes_clip.py`) retired.** The order of 2026-10-25 (Pavo → Agnes direct →
  vidIQ) was replaced by the owner's rules R1-R4 of 27/10 (above): Pavo first, and when its free quota runs out the
  silent shots take free fallbacks (footage library, FLUX stills with motion), wired into `episode_build.py sources`.
  Agnes direct never left "test only" (terms unread, a watermark possible) and its three runs (2026-10-25) all failed.
  Pavo itself still serves Agnes Flash video and agnes-image stills through the `heroverse-pavo` MCP.
- **Also retired:** the prayer Shorts-from-long line (`shorts.yml`, `shorts-review.yml`, `publish-shorts.yml`,
  `shorts_produce.py`, `shorts_006_*`, `publish_shorts.py`, `review_recovery.py`, `shorts_prerequisite.py`; Bible Shorts
  are episodes through `publish-episode.yml`), the closed Chatterbox A/B (`voice-sample.yml`, `chatterbox_sample.py`;
  `voice_judge.py` stays the ruler), the offline native-window mining tools (`opportunity.py`, `native_metrics.py`,
  `native_plan.py`, `accuracy_check.py`; their download route is gone) and `strategy/FORMAT_OPINION_AND_CRITIQUE.md`.
  All stay in git history.
- **Clocks.** `heartbeat.yml` is the only GitHub cron of record (`tiktok.yml` keeps its own as a second chance); the
  light clock (:14) is the only watchdog and no longer dispatches `tiktok.yml`; the main clock (every 4 h at :29) does
  production only; the 08:05 daily pass does report, decision and live intelligence (OPERATIONS.md "Clocks").
  `channel-privacy.yml` left the heartbeat (a finished job; dispatched by hand).
- **Measure:** the daily report's scheduler health (`ops/health.py`) shows no missed slot over the next 7 days, and
  `tiktok.yml`'s run history shows no dispatch by a Claude clock.

## Owner decision: fixed cadence, and the arc-01 long tomorrow by exception (2026-10-28)
- **Cadence (owner, 28/10 ~02:00-02:30 UTC): "cadência fixa (dono 28/10): 2 Shorts/dia, longo dia sim dia não;
  produções desenhadas para o orçamento do Pavo"** ("longo dia sim, dia não"); only the mining can change it. From
  arc-02 on, every production is designed to the shared free Pavo quota (120 units a UTC day, quota.py): a 2-day cycle
  is 240 units = 4 Shorts x ~20 + one long <= 160 units (about 60 Pavo clips with retries; an existing clip is free).
  Measured on arc-01 under frozen story QA v4: the long as planned needs ~142 Pavo clips (~360 units), and even with
  ~40 shots cut one acted long costs ~260 units, so the cadence is capped by the quota until each long is designed to
  the budget.
- **arc-01, owner, 28/10 ~02:30 UTC (exception, this long only):** "Tem que ser amanhã.. abre a exceção e faça o que
  resta do longo com parte das cenas do Pavo misturado com imagens animadas ou vídeos coerentes.. e no outro você faz
  desse jeito aí.. só não pode falhar! Tem que ser preciso, sem retrabalho e assertivo com a estrutura e roteiro."
  The time the owner accepted for "amanhã": **2026-10-29 22:00 UTC** (the 10:00 standard slot cannot be met safely:
  ~145 Pavo still units across two UTC days, the stills' review, the build and the preview review).
- **What it became:** `production/qa_criteria_story_v4_owner_exception_arc01.json` (frozen, pinned by sha256 in
  long_plan_check, render_queue and prepublish_gate): story QA v4 with only `rights.fallback_sources` (and
  `grammar.fallback_shots`, the same rule) widened, plus its version, freeze time and an `owner_exception` record
  naming the plan; long_plan_check refuses it for any other plan (CRITERIA_EXCEPTION_PLAN). Under it a silent shot with
  characters may be a still in motion made by Pavo agnes-image with exactly the characters' approved references
  (SOURCE_CHARACTER_STILL otherwise), and a spoken shot whose native clip does not exist or pass is the long's plan B:
  the pinned Kokoro voice over an approved still of the shot (God always Kokoro, #486). A Pavo character still is
  owner-owned output judged by fallback_shots (qa_pilot), not by the open-model image row. v3, v4, every other gate and
  the 9.5 floor are unchanged; the structure and script are plans/arc-01-long.json as they were (no shot cut).
