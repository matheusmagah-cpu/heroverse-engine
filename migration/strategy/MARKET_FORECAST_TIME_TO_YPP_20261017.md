# Market-based time-to-YPP forecast for HeroVerse (registered 2026-10-17, before any new publication)

Author: Claude Code (AI assistant). Registered before the outcome window, following PREDICTABILITY_CONTRACT.md: it is not edited after outcomes. Revisions are appended with date and reason. It replaces the judgement-only ranges drafted earlier that day, which were never committed.

## Data (measured)
- Panel `evidence/market-panel/panel-20261017.json` (run 39024990233, 7,499 Data API units, no paid calls).
  - 30 English Christian niche queries (US, en), last 30 days, two orders. One order samples recent uploads regardless of success, so failing channels are included. The other samples the most-viewed uploads.
  - 2,115 channels. 389 have a complete public upload history and visible subscriber counts.
- Model `evidence/ypp-market-model-20261017.json` (`mining/ypp_market_model.py` v2).
  - "Activity age" counts from the first public upload.
  - YPP proxy = 1,000 subscribers plus public long-form hours ≥ 4,000, using the **low** retention scenario: views × duration × 0.20. The other route is 10M Shorts views in ≤ 90 days.
  - Watch hours, retention, CTR, RPM and approval status of other channels are not public.

## Base rates by strategy (share of channels already over the proxy; Wilson 90% interval)
| Strategy | 0–30 days | 31–60 days | 61–90 days |
|---|---|---|---|
| Long-form ≥ 20 min, ≤ 20% Shorts, ≥ 0.5 uploads/day | **23%** (5/22, 12–40%) | **38%** (5/13, 20–61%) | **75%** (6/8, 46–91%) |
| Long-form 3–20 min | 14% (1/7) | 33% (2/6) | 50% (2/4) |
| Mixed long + Shorts | 4% (1/26) | 17% (2/12) | 25% (3/12) |
| Shorts-heavy (≥ 80% Shorts) | **3%** (3/118) | **3%** (2/61) | **10%** (5/48) |

- The fast long-form channels share a profile (45 channels over the proxy within 90 days): median **one upload/day**, **median long video 36 min**, **0% Shorts**, and a median top-video share of 27%. They do not depend on a single hit.
- Subscriber conversion in long-form channels: **8.8 subscribers per 1,000 long-form views** (p25 5.7, p75 12.6; 56 channels).
- **Subscribers, not hours, are the binding constraint.** HeroVerse needs 737 more subscribers, which is about **84,000 long-form views** at the median conversion (59k–129k across p75–p25). At 36 min and 20% retention, 4,000 h needs only about 33,000 views.

## Forecast for HeroVerse
Condition: HeroVerse executes the fast long-form strategy. That means daily original 25–40 min prayer videos, Shorts only as acquisition, and day 0 = the first publication of the new series.

| Event | Probability (central, 90% interval) | Basis |
|---|---|---|
| Thresholds reached by day 30 | **23%** (12–40%) | measured base rate, n = 22 |
| Thresholds reached by day 60 | **38%** (20–61%) | measured, n = 13 |
| Thresholds reached by day 90 | **75%** (46–91%) | measured, n = 8 (weak) |
| **Approved and monetized by day 30** | **≤ 10%** | inferred: thresholds by ~day 20 are needed, then a review of about 1 month |
| Approved before 1 Feb 2027 (old thresholds) | about 50% | inferred: thresholds by ~day 60 plus review |

- Applying the same strategy with Shorts as the main route drops the probability to 3–10%. That is why Shorts serve here only to bring viewers to the long videos.
- Known biases: the sample consists of channels that survived and still publish (failures that stopped are missing), and the n per band is small. The intervals already include the sampling uncertainty, but not the survivorship bias. The true rate is probably **lower** than the table.

## Leading indicators and decision rules (pre-registered)
Measured from owned data at fixed ages after day 0:
- **Day 14:** cumulative long-form views ≥ 30,000 means on the p25 track of fast channels (20–40 days: p25 32k, median 158k). Below 5,000 is off track: change the topic/packaging variable before producing more of the same.
- **Day 30:** subscribers ≥ 600 and views ≥ 75,000 means likely to cross before day 60.
- Per video at 7 days: impressions CTR ≥ 4% and average view duration ≥ 6 min (16% of 36 min). Otherwise, iterate packaging (CTR) or hook/script (AVD), one variable at a time (D-083).

## Checking that the market model itself predicts (no waiting for our own channel)
`evidence/market-forecast-registered-20261017.json` holds predictions registered today for 389 market channels: subscribers at +7 and +28 days, and the probability of crossing the proxy by +28 days. The daily panel (`market-panel.yml`) refreshes those channels and writes `market-forecast-eval-*.json`. The model is accepted only if it beats the baselines (MAE vs "unchanged", Brier vs constant) on at least 30 channels, as pre-registered.

## Policy filter applied to the mechanisms (from the policy digest)
Fast channels using these mechanisms are excluded as models:
- impersonating real preachers ("Billy Graham Legacy", sermons of named pastors);
- prosperity or money-release promises;
- AI personas presented as people;
- mass loops.

The retained mechanism is authored prayer and scripture content with varied visuals and an honest title/thumbnail.

## Revision 2026-10-17 14:40 UTC: owner sets the target at 14 days (30 days is only the error margin)
**Reason for the revision:** owner directive. The benchmark becomes the channels that crossed the proxy fastest, not the 30-day base rate. Source: the same panel `panel-20261017.json`.

**Measured within ≤ 14 days of activity:**
- 1 of 108 channels is over the proxy. It is a Shorts channel with 11.2M Shorts views in 10 days.
- Long-form daily channels: 0 of 12 (Wilson 90% upper bound 18%).

**Fastest compliant long-form benchmark: Grace & Glory Prayers.**
- Day 19 of activity: 31 long videos (1.6 per day, median 36 min), 2,660 subscribers, 362,634 long views, at least 44,000 public hours in the low-retention scenario.
- Its average pace is 140 subscribers/day and 19,000 long views/day.
- At that pace, HeroVerse's gap (737 subscribers; hours are not binding) closes in about 5–6 days.

**Other channels at 18–21 days (excluded as models):**
- Bible Prophecy: sensational prophecy claims (misinformation risk).
- The Billy Graham Legacy: impersonation of a real preacher.
- Two Shorts channels (devotional edits) with 13–16M Shorts views, whose content has not yet been checked for reused material.

**14-day pace targets for HeroVerse:**
- **Rates (from day 1):** 53 net subscribers/day and about 6,000 long-form views/day (at 8.8 subscribers per 1,000 views).
- **Day-by-day checkpoints:**
  - Day 3: at least 18,000 long views and 160 net subscribers.
  - Day 7: at least 42,000 long views and 370 net subscribers.
  - Day 10: at least 60,000 long views and 530 net subscribers.

  Falling behind on two consecutive days triggers an immediate change of topic or packaging, chosen from that day's intelligence.
- **Production implication:** match the benchmark cadence of 1.5–2 long videos/day of 25–40 min, using Kaggle GPU rendering. A cadence of 1 per day is below the benchmark.

**Probability, stated honestly:**
- Reaching the thresholds within 14 days: no compliant long-form channel in today's panel did it. The only proven 14-day route was viral Shorts, at a measured rate of about 1%.
- **Approval** within 14 days also needs the YouTube review to finish. That review is not under our control and takes up to about one month.
- This is the measured base rate. The daily panel from tomorrow measures real trajectories and will update it.
