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
| D-03 (1 Short per long) | 5/22 vs 1/26 | Fisher p = 0.062 (93.8%) | **active**: passes the 90% minimum |
| D-05 (subscribe ask) | 13/20 winners | no comparison group, not testable | **reverted** in pilots 004–006 (pilot-003 had already rendered with it) |
| D-01/D-04 (length) | 5/22 vs 1/7 | p = 0.55, not a proven improvement | **kept as conformance**: they return execution to the registered 25–40 min strategy that the 15-min scripts had drifted from |
| D-02 (hide 4 fear-bait videos) | owner policy | compliance | **kept** |

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
