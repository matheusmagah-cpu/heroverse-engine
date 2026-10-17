#!/usr/bin/env python3
"""Pre-registered, falsifiable market forecasts (predictability contract).

register: from the latest compact panel, predict for every modelled channel
  (a) subscribers at +7 and +28 days and (b) whether it is over the YPP proxy
  (low-retention scenario) at +28 days. Method v1: lifetime average daily
  subscriber gain carried forward; probability of crossing from the observed
  share of older channels of the same strategy. Baseline: no change.
  The file is written once (refuses to overwrite) and committed before the
  outcome window.
evaluate: score a registered file against a later panel: MAE of subscribers
  vs baseline, and Brier score of the crossing probabilities vs a constant.
usage: market_forecast.py register PANEL OUT | evaluate REGISTERED PANEL OUT
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ypp_market_model as ym  # noqa: E402

HORIZONS = (7, 28)


def strategy_of(row):
    return next((name for name, keep in ym.STRATEGIES.items() if keep(row)), "other")


def register(panel_path, out):
    out = Path(out)
    if out.exists():
        raise SystemExit("ALREADY_REGISTERED")
    panel = json.loads(Path(panel_path).read_text())
    rows = ym.channel_rows(panel)
    # crossing probability: share over the proxy among channels 28 days older, same strategy
    def p_cross(row):
        target = row["activity_days"] + 28
        peers = [r for r in rows if strategy_of(r) == strategy_of(row) and abs(r["activity_days"] - target) <= 15]
        if len(peers) < 3:
            return None
        return round(sum(r["eligible_long_low"] or r["eligible_shorts"] for r in peers) / len(peers), 3)
    predictions = []
    for r in rows:
        rate = r["subscribers"] / r["activity_days"]
        predictions.append({"channel_id": r["channel_id"], "strategy": strategy_of(r), "activity_days": r["activity_days"],
                            "subscribers_now": r["subscribers"], "eligible_now": bool(r["eligible_long_low"] or r["eligible_shorts"]),
                            **{f"subscribers_d{h}": round(r["subscribers"] + rate * h) for h in HORIZONS},
                            "p_eligible_d28": None if (r["eligible_long_low"] or r["eligible_shorts"]) else p_cross(r)})
    record = {"version": "market-forecast-v1", "registered_from_panel": panel["captured_at"],
              "method": "lifetime average daily subscriber gain carried forward; crossing probability from same-strategy "
                        "channels 13-43 days older in the same panel (cross-sectional)",
              "baseline": "subscribers unchanged; constant crossing probability equal to the panel-wide share",
              "pass_criteria_preregistered": {"subscribers_mae_beats_baseline": True,
                                              "brier_beats_constant": True,
                                              "min_scored_channels": 30},
              "predictions": predictions}
    out.write_text(json.dumps(record, indent=0) + "\n")
    print(json.dumps({"predictions": len(predictions)}))


def evaluate(registered, panel_path, out):
    reg = json.loads(Path(registered).read_text())
    panel = json.loads(Path(panel_path).read_text())
    now = {c["channel_id"]: c for c in panel["channels"]}
    rows = {r["channel_id"]: r for r in ym.channel_rows(panel)}
    from datetime import datetime
    days = (datetime.fromisoformat(panel["captured_at"].replace("Z", "+00:00"))
            - datetime.fromisoformat(reg["registered_from_panel"].replace("Z", "+00:00"))).days
    scored = []
    for p in reg["predictions"]:
        c = now.get(p["channel_id"])
        if not c or c.get("subscribers") is None:
            continue
        horizon = min(HORIZONS, key=lambda h: abs(h - days))
        pred = p["subscribers_now"] + (p[f"subscribers_d{horizon}"] - p["subscribers_now"]) * days / horizon
        scored.append({"channel_id": p["channel_id"], "actual": c["subscribers"], "model": pred, "baseline": p["subscribers_now"],
                       "p": p["p_eligible_d28"], "crossed": bool(rows.get(p["channel_id"], {}).get("eligible_long_low"))
                       if p["channel_id"] in rows else None, "eligible_before": p["eligible_now"]})
    mae = lambda key: round(sum(abs(s[key] - s["actual"]) for s in scored) / len(scored), 1) if scored else None
    probs = [s for s in scored if s["p"] is not None and s["crossed"] is not None and not s["eligible_before"]]
    base = sum(s["crossed"] for s in probs) / len(probs) if probs else None
    brier = lambda f: round(sum((f(s) - s["crossed"]) ** 2 for s in probs) / len(probs), 4) if probs else None
    result = {"version": "market-forecast-evaluation-v1", "registered": reg["registered_from_panel"],
              "evaluated_at": panel["captured_at"], "elapsed_days": days, "scored_channels": len(scored),
              "subscribers_mae_model": mae("model"), "subscribers_mae_baseline": mae("baseline"),
              "crossing_scored": len(probs), "brier_model": brier(lambda s: s["p"]), "brier_constant": brier(lambda s: base),
              "note": "Crossing is only final at +28 days; earlier evaluations are interim."}
    Path(out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    if sys.argv[1] == "register":
        register(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "evaluate":
        evaluate(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(__doc__)
