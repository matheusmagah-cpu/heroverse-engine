#!/usr/bin/env python3
"""Ads stage (owner, 2026-10-24: "real predictability of monetization for an investment").

Facts this model is built on (evidence/ads/20261024-research.json, with sources):
- Watch hours AND subscribers gained through ad campaigns do not count toward the YPP thresholds (YouTube Promote
  help). Ads never buy the YPP counter directly; they can only seed an audience that then returns organically.
- Benchmarks (third-party, 2026): cost per view (skippable in-stream / Promote) $0.02-0.10; a YouTube Promote study:
  $4-6 per subscriber (undated).
- vidIQ earnings model, Religion, US, English: long-form ~$1.98-5.28 per 1,000 views (mid 3.30); Shorts ~$0.04-0.11.

So a paid view pays back only through the ORGANIC views it causes afterwards (returning viewers, subscribers'
feeds, recommendations seeded by the paid audience): organic_per_paid = k. The model is deterministic; every input
is a range to be replaced by our own measured value after the first test campaign.

usage: ads_model.py BUDGET_USD [K_ORGANIC_PER_PAID]   prints the low/mid/high outcome of that budget
"""
import json
import sys

CPV = {"low": 0.10, "mid": 0.05, "high": 0.02}            # USD per paid view (low = expensive case)
RPM_LONG = {"low": 1.98, "mid": 3.30, "high": 5.28}       # USD per 1,000 monetized long-form views
COST_PER_SUB = {"low": 6.0, "mid": 5.0, "high": 4.0}      # USD per ad-attributed subscriber
AVG_VIEW_MIN = 7.0                                        # our measured long-form average from Related traffic (442 s)


def outcome(budget, k, case, monetized=True):
    paid_views = budget / CPV[case]
    organic_views = paid_views * k
    revenue = (organic_views + (paid_views if monetized else 0)) * RPM_LONG[case] / 1000 if monetized else 0.0
    return {"case": case, "paid_views": round(paid_views), "ad_subscribers_not_counted_for_ypp": round(budget / COST_PER_SUB[case]),
            "organic_views_caused": round(organic_views),
            "organic_watch_hours_counted_for_ypp": round(organic_views * AVG_VIEW_MIN / 60, 1),
            "revenue_usd_if_monetized": round(revenue, 2), "return_on_spend": round(revenue / budget, 3) if budget else None}


def break_even_k(case):
    """Organic views each paid view must cause for ad revenue to repay the spend (after YPP)."""
    return round(CPV[case] / (RPM_LONG[case] / 1000) - 1, 1)


def main(argv):
    budget = float(argv[0])
    k = float(argv[1]) if len(argv) > 1 else 1.0
    print(json.dumps({"budget_usd": budget, "k_organic_per_paid": k,
                      "outcomes": [outcome(budget, k, c) for c in ("low", "mid", "high")],
                      "break_even_k": {c: break_even_k(c) for c in ("low", "mid", "high")}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
