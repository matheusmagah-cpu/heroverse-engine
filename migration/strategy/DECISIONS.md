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

### D-2026-10-18-02 — Old fear-bait / "prophecy" public videos: pending evidence
- **Observation:** some old public titles conflict with the owner's policy ("The 2026 Prophecy: What They Are Hiding From You…").
- **Before any action:** measure the watch hours each carries (Analytics per video) and quote the YouTube policy that applies. Decide only with both.
