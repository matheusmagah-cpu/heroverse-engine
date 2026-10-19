from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
CHANNEL_ID = "UCuMF6pJQkyMzaVoAxFL86yA"
VIDEO_ID = "iK_5edYQtx8"
BASE = Path("output/operations/phase6/intelligence")
DIAGNOSIS_LATEST = BASE / "diagnoses/latest.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _validate(root: Path, schema_name: str, value: dict[str, Any]) -> None:
    schema = _read(root / "schemas" / schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical(value))
    temporary.replace(path)


def _write_immutable(path: Path, value: dict[str, Any]) -> None:
    payload = _canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise PermissionError(f"immutable record collision: {path.name}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _rate_to_ratio(value: Any) -> float | None:
    """Normalize an API rate for decisions while preserving the raw source artifact."""

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    rate = float(value)
    if rate < 0 or rate > 100:
        return None
    return rate / 100 if rate > 1 else rate


def build_diagnostic_decision(
    latest_snapshot: dict[str, Any],
    config: dict[str, Any],
    *,
    decided_at: str | None = None,
    expected_video_id: str = VIDEO_ID,
) -> dict[str, Any]:
    """Choose one evidence-bound bottleneck without treating a small sample as causality."""

    if latest_snapshot.get("channel_id") != CHANNEL_ID or latest_snapshot.get("video_id") != expected_video_id:
        raise PermissionError("diagnostic snapshot identity mismatch")
    timestamp = decided_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    age = float(latest_snapshot.get("age_hours") or 0)
    snapshot_status = str(latest_snapshot.get("status") or "UNAVAILABLE")
    decision_status = str(latest_snapshot.get("decision_status") or "INSUFFICIENT_DATA")
    private = latest_snapshot.get("private_metrics") or {}
    public = latest_snapshot.get("public_metrics") or {}
    sources = latest_snapshot.get("sources") or {}
    gates = config.get("quality_gates") or {}
    minimum_views = int(gates.get("phase6_minimum_diagnostic_views", 30))
    ctr_floor = float(gates.get("long_ctr_scale", 0.05))
    intro_floor = float(gates.get("long_intro_30s_scale", 0.50))
    avp_floor = float(gates.get("long_average_percentage_viewed_scale", 0.50))
    owned_views = (
        int(private["views"])
        if isinstance(private.get("views"), (int, float)) and not isinstance(private.get("views"), bool)
        else None
    )
    public_views = (
        int(public["viewCount"])
        if isinstance(public.get("viewCount"), (int, float)) and not isinstance(public.get("viewCount"), bool)
        else None
    )
    if owned_views is not None:
        diagnostic_sample_views = owned_views
        diagnostic_sample_source = "YOUTUBE_ANALYTICS_EXACT_VIDEO"
        sample_source_valid = (sources.get("youtube_analytics_api") or {}).get("status") == "PASS"
    elif public_views is not None:
        diagnostic_sample_views = public_views
        diagnostic_sample_source = "YOUTUBE_DATA_API_PUBLIC_EXACT_VIDEO"
        sample_source_valid = (sources.get("youtube_data_api") or {}).get("status") == "PASS"
    else:
        diagnostic_sample_views = None
        diagnostic_sample_source = "NONE"
        sample_source_valid = False
    metrics = {
        "owned_views": owned_views,
        "public_views": public_views,
        "diagnostic_sample_views": diagnostic_sample_views,
        "diagnostic_sample_source": diagnostic_sample_source,
        "thumbnail_impressions": int(private["videoThumbnailImpressions"]) if isinstance(private.get("videoThumbnailImpressions"), (int, float)) else None,
        "thumbnail_ctr_ratio": _rate_to_ratio(private.get("videoThumbnailImpressionsClickRate")),
        "intro_30s_ratio": _rate_to_ratio(private.get("intro30sAudienceWatchRatio")),
        "average_view_percentage_ratio": _rate_to_ratio(private.get("averageViewPercentage")),
        "watch_minutes": float(private["estimatedMinutesWatched"]) if isinstance(private.get("estimatedMinutesWatched"), (int, float)) else None,
        "subscribers_gained": int(private["subscribersGained"]) if isinstance(private.get("subscribersGained"), (int, float)) else None,
        "normalization": "RATE_VALUES_ABOVE_1_AND_AT_MOST_100_ARE_DIVIDED_BY_100; RAW_VALUES_REMAIN_IN_SOURCE_SNAPSHOT",
    }
    controlled = [
        "channel_and_niche", "format_pack_and_pipeline", "quality_profile", "duration_band",
        "voice_identity", "visual_style_bible", "publication_window", "rights_and_cost_gates",
    ]
    creative_metrics_complete = (
        age >= 24
        and snapshot_status == "OBSERVED"
        and decision_status == "ELIGIBLE_FOR_COMPARISON"
        and owned_views is not None
        and metrics["intro_30s_ratio"] is not None
    )
    distribution_only_eligible = (
        age >= 24
        and snapshot_status != "FAILED"
        and sample_source_valid
        and diagnostic_sample_views is not None
        and diagnostic_sample_views < minimum_views
    )
    eligibility_scope = (
        "FULL_CREATIVE_METRICS"
        if creative_metrics_complete
        else ("DISTRIBUTION_ONLY_EXACT_COUNT" if distribution_only_eligible else "NOT_ELIGIBLE")
    )
    if snapshot_status == "FAILED" or decision_status == "INVALID_OBSERVATION":
        status = "BLOCKED_INVALID_BASELINE"
        bottleneck, action, variable, primary, confidence = "INVALID_BASELINE", "WAIT", "NONE", "NONE", "NONE"
        reasons = ["BASELINE_FAILED_VALIDATION"]
        instruction = "Do not produce Video 2; repair collection integrity and obtain a valid owned snapshot."
        may_start = False
    elif distribution_only_eligible:
        status = "DIAGNOSED"
        bottleneck, action, variable, primary, confidence = "DISTRIBUTION_SAMPLE", "EXPAND_SAMPLE", "TOPIC_ANGLE", "views", "LOW"
        reasons = ["OWNED_SAMPLE_BELOW_DIAGNOSTIC_FLOOR", "NO_CREATIVE_FAILURE_INFERRED_FROM_SMALL_SAMPLE"]
        if diagnostic_sample_source == "YOUTUBE_DATA_API_PUBLIC_EXACT_VIDEO":
            reasons.append("PUBLIC_EXACT_VIDEO_COUNT_USED_DURING_ANALYTICS_LAG")
        else:
            reasons.append("OWNED_EXACT_VIDEO_COUNT_USED_DURING_CREATIVE_METRICS_LAG")
        instruction = "Change only the ChannelDNA-compatible problem angle; preserve package grammar, direct-anchor hook mechanics, narrative arc, duration, voice and visual system to expand the owned sample. Do not infer a hook, package or narrative defect from delayed creative metrics."
        may_start = True
    elif not creative_metrics_complete:
        status = "WAITING_FOR_ELIGIBLE_BASELINE"
        bottleneck, action, variable, primary, confidence = "UNDETERMINED", "WAIT", "NONE", "NONE", "NONE"
        reasons = ["WAIT_FOR_24H_ELIGIBLE_OWNED_METRICS"]
        instruction = "Keep the current release unchanged and collect the next preregistered owned checkpoint."
        may_start = False
    elif metrics["owned_views"] < minimum_views:
        status = "DIAGNOSED"
        bottleneck, action, variable, primary, confidence = "DISTRIBUTION_SAMPLE", "EXPAND_SAMPLE", "TOPIC_ANGLE", "views", "LOW"
        reasons = ["OWNED_SAMPLE_BELOW_DIAGNOSTIC_FLOOR", "NO_CREATIVE_FAILURE_INFERRED_FROM_SMALL_SAMPLE"]
        instruction = "Change only the ChannelDNA-compatible problem angle; preserve package grammar, direct-anchor hook mechanics, narrative arc, duration, voice and visual system to expand the owned sample."
        may_start = True
    elif metrics["thumbnail_ctr_ratio"] is not None and metrics["thumbnail_ctr_ratio"] < ctr_floor:
        status = "DIAGNOSED"
        bottleneck, action, variable, primary, confidence = "PACKAGING", "ITERATE_PACKAGE", "TITLE_THUMBNAIL_PROMISE", "videoThumbnailImpressionsClickRate", "MEDIUM"
        reasons = ["CTR_BELOW_INTERNAL_OPERATIONAL_FLOOR", "EXPOSURE_AT_OR_ABOVE_DIAGNOSTIC_FLOOR"]
        instruction = "Change only the combined title-thumbnail promise; preserve topic, first-eight-second mechanism, narrative, duration, voice and visual system."
        may_start = True
    elif metrics["intro_30s_ratio"] < intro_floor:
        status = "DIAGNOSED"
        bottleneck, action, variable, primary, confidence = "HOOK", "ITERATE_HOOK", "FIRST_8_SECONDS_MECHANISM", "intro30sAudienceWatchRatio", "MEDIUM"
        reasons = ["INTRO_30S_BELOW_INTERNAL_OPERATIONAL_FLOOR", "EXPOSURE_AT_OR_ABOVE_DIAGNOSTIC_FLOOR"]
        instruction = "Change only the first-eight-second promise-delivery mechanism; preserve topic, package grammar, body arc, duration, voice and visual system."
        may_start = True
    elif metrics["average_view_percentage_ratio"] is not None and metrics["average_view_percentage_ratio"] < avp_floor:
        status = "DIAGNOSED"
        bottleneck, action, variable, primary, confidence = "NARRATIVE", "ITERATE_NARRATIVE", "BODY_PROGRESSIVE_DISCLOSURE", "averageViewPercentage", "MEDIUM"
        reasons = ["AVERAGE_VIEW_PERCENTAGE_BELOW_INTERNAL_OPERATIONAL_FLOOR", "HOOK_FLOOR_MET"]
        instruction = "Change only progressive disclosure and payoff spacing after eight seconds; preserve topic, package, hook mechanism, duration, voice and visual system."
        may_start = True
    else:
        status = "DIAGNOSED"
        bottleneck, action, variable, primary, confidence = "REPLICATION", "EXPAND_SAMPLE", "TOPIC_ANGLE", "views", "MEDIUM"
        reasons = ["AVAILABLE_CREATIVE_GATES_MET", "MORE_OWNED_RELEASES_REQUIRED_BEFORE_RULE_PROMOTION"]
        instruction = "Change only the ChannelDNA-compatible problem angle and replicate the approved production system; do not promote a general rule from one baseline."
        may_start = True

    stable = "|".join([
        "diagnostic-policy-1.1.0", str(latest_snapshot.get("snapshot_id")), status,
        bottleneck, action, variable, primary, eligibility_scope,
    ])
    value = {
        "schema_version": "1.1.0",
        "diagnosis_id": f"phase6-diagnosis-{hashlib.sha256(stable.encode()).hexdigest()[:16]}",
        "operation_id": "heroverse-phase6-controlled-longform-v1",
        "phase": 6, "channel_id": CHANNEL_ID, "status": status,
        "baseline": {
            "snapshot_id": latest_snapshot.get("snapshot_id"), "captured_at": latest_snapshot.get("captured_at"),
            "age_hours": age, "snapshot_status": snapshot_status, "decision_status": decision_status,
            "eligibility_scope": eligibility_scope,
        },
        "metrics": metrics,
        "policy": {
            "minimum_diagnostic_views": minimum_views, "ctr_floor": ctr_floor,
            "intro_30s_floor": intro_floor, "average_view_percentage_floor": avp_floor,
            "source": "config/engine.json#quality_gates", "threshold_class": "INTERNAL_OPERATIONAL_GATE_NOT_MARKET_FACT",
            "distribution_lag_rule": "AT_OR_AFTER_24H_AN_EXACT_VIDEO_COUNT_BELOW_THE_VIEW_FLOOR_MAY_AUTHORIZE_TOPIC_ANGLE_SAMPLE_EXPANSION_ONLY",
        },
        "decision": {
            "dominant_bottleneck": bottleneck, "action": action, "treatment_variable": variable,
            "primary_metric": primary, "confidence": confidence, "reason_codes": reasons,
            "controlled_constants": controlled, "treatment_instruction": instruction,
            "production_may_start": may_start,
        },
        "evidence_refs": [
            f"output/operations/phase6/metrics/{expected_video_id}/latest.json",
            "config/engine.json#quality_gates",
            "output/modeling/phase4/channel-model-v1/channel_model.json#hypotheses/H-HOOK-DIRECT-ANCHOR",
        ],
        "claim_boundary": [
            "Internal thresholds are operational gates, not universal market benchmarks.",
            "A small sample selects controlled replication and never proves a creative failure.",
            "During Analytics lag, an exact public count may authorize only low-sample expansion; it cannot diagnose packaging, hook or narrative.",
            "One observed baseline cannot establish causality or a general rule.",
            "Production permission here never bypasses rights, quality, channel, OAuth, quota or publication gates.",
        ],
        "decided_at": timestamp, "technical_cost_brl": 0,
    }
    return value


def build_prediction(
    feature_snapshot: dict[str, Any],
    *,
    horizon_hours: int = 24,
    comparable_outcomes: list[float] | None = None,
    minimum_calibration_size: int = 3,
    created_at: str | None = None,
    expected_video_id: str = VIDEO_ID,
) -> dict[str, Any]:
    """Create a cutoff-pinned record without pretending sparse data is calibrated."""

    if feature_snapshot.get("channel_id") != CHANNEL_ID or feature_snapshot.get("video_id") != expected_video_id:
        raise PermissionError("prediction feature snapshot identity mismatch")
    cutoff = _parse(str(feature_snapshot["captured_at"]))
    created = _parse(created_at) if created_at is not None else datetime.now(timezone.utc)
    if created < cutoff:
        raise ValueError("prediction creation cannot predate its available feature cutoff")
    if horizon_hours < 1 or minimum_calibration_size < 3:
        raise ValueError("horizon must be positive and calibration requires at least three completed comparable outcomes")
    outcomes = [float(value) for value in (comparable_outcomes or []) if float(value) >= 0]
    source_id = str(feature_snapshot["snapshot_id"])
    digest = hashlib.sha256(f"{source_id}|{horizon_hours}|cumulative_public_views".encode()).hexdigest()[:16]
    if len(outcomes) < minimum_calibration_size:
        status = "WITHHELD_INSUFFICIENT_CALIBRATION"
        baseline = {"method": "WITHHELD_NO_COMPARABLE_COMPLETED_WINDOW", "value": None, "source_ids": [source_id]}
        forecast = None
    else:
        point = float(statistics.median(outcomes))
        status = "PRE_REGISTERED_CALIBRATED"
        baseline = {
            "method": "LAST_OBSERVATION_CARRIED_FORWARD",
            "value": float(outcomes[-1]),
            "source_ids": [source_id],
        }
        forecast = {
            "point": point,
            "interval": {"level": 0.9, "lower": max(0.0, _quantile(outcomes, 0.05)), "upper": _quantile(outcomes, 0.95)},
            "calibration_status": "CALIBRATED_OUT_OF_SAMPLE",
        }
    return {
        "schema_version": "1.0.0", "status": status,
        "prediction_id": f"prediction-{expected_video_id}-{digest}",
        "operation_id": "heroverse-phase6-controlled-longform-v1",
        "channel_id": CHANNEL_ID, "video_id": expected_video_id,
        "target": "cumulative_public_views", "unit": "views",
        "cutoff_at": _stamp(cutoff),
        "horizon": {"hours": horizon_hours, "ends_at": _stamp(cutoff + timedelta(hours=horizon_hours))},
        "cohort": {
            "format": "LONG", "quality_profile": "STANDARD",
            "format_pack_id": "fp-broll-cinematic-narration", "format_pack_version": "1.1.0",
            "calibration_sample_size": len(outcomes),
        },
        "baseline": baseline, "forecast": forecast,
        "pipeline_version": "phase6-prediction-v1",
        "available_feature_snapshot_id": source_id,
        "assumptions": [
            "Only completed comparable owned-channel windows available at cutoff may calibrate the forecast.",
            "Campaign traffic is absent and cannot be counted as qualified YPP progress.",
        ],
        "limitations": [
            "A withheld forecast is evidence of insufficient calibration, not a zero-view prediction.",
            "Even a calibrated interval is uncertainty, not a guarantee of views or monetization.",
        ],
        "created_at": _stamp(created), "technical_cost_brl": 0,
    }


def materialize_prediction(
    feature_snapshot: dict[str, Any],
    root: Path = ROOT,
    *,
    horizon_hours: int = 24,
    comparable_outcomes: list[float] | None = None,
    created_at: str | None = None,
) -> Path:
    root = root.resolve()
    value = build_prediction(
        feature_snapshot, horizon_hours=horizon_hours,
        comparable_outcomes=comparable_outcomes, created_at=created_at,
    )
    _validate(root, "prediction_record.schema.json", value)
    path = root / BASE / "predictions" / f"{value['prediction_id']}.json"
    if path.is_file():
        prior = _read(path)
        prior_stable, value_stable = dict(prior), dict(value)
        prior_stable.pop("created_at", None)
        value_stable.pop("created_at", None)
        if prior_stable == value_stable:
            _write_atomic(root / BASE / "predictions" / "latest.json", prior)
            return path
    _write_immutable(path, value)
    _write_atomic(root / BASE / "predictions" / "latest.json", value)
    return path


def evaluate_prediction(
    prediction: dict[str, Any],
    *,
    outcome_value: float | None,
    observed_at: str,
    outcome_source_id: str,
) -> dict[str, Any]:
    observed = _parse(observed_at)
    horizon_end = _parse(prediction["horizon"]["ends_at"])
    horizon_key = horizon_end.strftime("%Y%m%dT%H%M%SZ")
    evaluation_id = f"evaluation-{prediction['prediction_id']}-{horizon_key}"
    if observed < horizon_end:
        status, outcome, errors, out_of_sample = "TOO_EARLY", None, None, False
        baseline_error = uplift = None
    elif prediction["forecast"] is None or outcome_value is None:
        status, errors, out_of_sample = "NOT_EVALUABLE_WITHHELD", None, True
        outcome = (
            {
                "value": float(outcome_value),
                "observed_at": _stamp(observed),
                "source_id": outcome_source_id,
            }
            if outcome_value is not None
            else None
        )
        baseline_error = uplift = None
    else:
        actual = float(outcome_value)
        forecast = prediction["forecast"]
        absolute = abs(actual - float(forecast["point"]))
        baseline_value = prediction["baseline"]["value"]
        baseline_error = abs(actual - float(baseline_value)) if baseline_value is not None else None
        uplift = baseline_error - absolute if baseline_error is not None else None
        status = "EVALUATED"
        outcome = {"value": actual, "observed_at": _stamp(observed), "source_id": outcome_source_id}
        errors = {
            "absolute_error": absolute,
            "percentage_error": absolute / actual if actual else None,
            "interval_covered": float(forecast["interval"]["lower"]) <= actual <= float(forecast["interval"]["upper"]),
        }
        out_of_sample = True
    return {
        "schema_version": "1.0.0", "evaluation_id": evaluation_id,
        "prediction_id": prediction["prediction_id"], "status": status,
        "outcome": outcome, "errors": errors,
        "baseline_comparison": {"baseline_absolute_error": baseline_error, "forecast_uplift_vs_baseline_error": uplift},
        "out_of_sample": out_of_sample, "evaluated_at": _stamp(observed), "technical_cost_brl": 0,
    }


def build_experiment_protocol(
    latest_snapshot: dict[str, Any],
    *,
    diagnosis: dict[str, Any] | None = None,
    created_at: str | None = None,
    expected_video_id: str = VIDEO_ID,
) -> dict[str, Any]:
    if latest_snapshot.get("channel_id") != CHANNEL_ID or latest_snapshot.get("video_id") != expected_video_id:
        raise PermissionError("experiment snapshot identity mismatch")
    timestamp = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    age = float(latest_snapshot.get("age_hours") or 0)
    metrics = latest_snapshot.get("private_metrics") or {}
    baseline_ready = age >= 24 and metrics.get("intro30sAudienceWatchRatio") is not None
    diagnosed = bool(
        diagnosis
        and diagnosis.get("status") == "DIAGNOSED"
        and (diagnosis.get("decision") or {}).get("production_may_start") is True
    )
    decision = (diagnosis or {}).get("decision") or {}
    treatment_video_id = None
    if diagnosed:
        treatment_video_id = (
            expected_video_id
            if decision.get("treatment_variable") == "TITLE_THUMBNAIL_PROMISE"
            else "phase6-video-2-prepublication"
        )
    value = {
        "schema_version": "1.1.0", "protocol_id": "heroverse-phase6-single-variable-v1",
        "phase": 6, "channel_id": CHANNEL_ID,
        "status": "PREREGISTERED" if diagnosed else ("READY_TO_PREREGISTER" if baseline_ready else "WAITING_FOR_24H_BASELINE"),
        "baseline": {
            "video_id": expected_video_id, "role": "OBSERVATIONAL_BASELINE_NOT_CAUSAL",
            "comparable_window_hours": 24,
            "snapshot_id": latest_snapshot.get("snapshot_id") if baseline_ready or diagnosed else None,
        },
        "treatment": {
            "video_id": treatment_video_id,
            "variable": decision.get("treatment_variable", "NONE") if diagnosed else "NONE",
            "control_lock": ["niche", "format_pack", "quality_profile", "duration_band", "voice", "release_gates"],
            "preregistered_before_production": diagnosed,
        },
        "primary_metric": decision.get("primary_metric", "NONE") if diagnosed else "NONE",
        "sample": {
            "minimum_views_per_arm": diagnosis["policy"]["minimum_diagnostic_views"] if diagnosed else None,
            "derivation_status": "OPERATIONAL_EXPLORATORY_FLOOR" if diagnosed else "BLOCKED_NO_BASELINE_VARIANCE",
            "reason": (
                "The preregistered floor permits a controlled exploratory comparison; it does not claim statistical power, and a result below the floor remains inconclusive."
                if diagnosed else
                "One canary cannot supply an owned variance estimate; sample size will be derived only after comparable owned observations exist."
            ),
        },
        "duration": {"minimum_hours": 24, "maximum_hours": 168},
        "cost": {"technical_cost_brl": 0, "media_budget_brl": 0, "paid_traffic_enabled": False},
        "risks": ["small owned sample", "non-randomized publication timing", "topic-demand confounding", "analytics latency"],
        "stopping_rule": "Stop immediately on critical rights, policy, identity, quality or collection-integrity failure; otherwise classify only at a comparable preregistered window.",
        "causality_boundary": [
            "The already-published canary is a baseline observation because this protocol did not predate its publication.",
            "Video 2 cannot be called an experiment until its treatment and sample rule are preregistered before production.",
            "A single favorable comparison cannot become a general or cross-channel rule.",
        ],
        "created_at": timestamp,
    }
    if diagnosed:
        value["diagnosis"] = {
            "diagnosis_id": diagnosis["diagnosis_id"],
            "path": (
                "output/operations/phase6/intelligence/diagnoses/"
                f"{diagnosis['diagnosis_id']}.json"
            ),
            "status": "DIAGNOSED",
        }
    return value


def evaluate_learning(
    *,
    experiment_id: str,
    metric: str,
    baseline: dict[str, Any],
    treatment: dict[str, Any],
    validity: dict[str, Any],
    evidence_ids: list[str],
    evaluated_at: str,
) -> dict[str, Any]:
    means_present = baseline.get("mean") is not None and treatment.get("mean") is not None
    errors_present = baseline.get("standard_error") is not None and treatment.get("standard_error") is not None
    invalid = (
        not validity.get("preregistered") or not validity.get("same_window")
        or not validity.get("single_variable") or validity.get("critical_incident")
        or bool(validity.get("confounders"))
    )
    if means_present and errors_present:
        delta = float(treatment["mean"]) - float(baseline["mean"])
        margin = 1.96 * math.sqrt(float(baseline["standard_error"]) ** 2 + float(treatment["standard_error"]) ** 2)
        lower, upper = delta - margin, delta + margin
    else:
        delta = lower = upper = None
    if invalid:
        classification, decision = "INVALID_EXPERIMENT", "DISCARD_RESULT_AND_REPLAN_WITH_VALID_CONTROLS"
    elif not means_present:
        classification, decision = "INCONCLUSIVE", "NO_RULE_CHANGE_OUTCOME_NOT_OBSERVED"
    elif not validity.get("minimum_sample_met"):
        classification, decision = "INCONCLUSIVE", "NO_RULE_CHANGE_COLLECT_COMPARABLE_SAMPLE"
    elif not errors_present:
        classification, decision = "INCONCLUSIVE", "NO_RULE_CHANGE_UNCERTAINTY_NOT_ESTIMABLE"
    elif lower is not None and lower > 0:
        classification, decision = "SUPPORTED", "REGISTER_CHANNEL_LOCAL_CANDIDATE_ONLY"
    elif upper is not None and upper < 0:
        classification, decision = "REJECTED", "REJECT_HYPOTHESIS_PRESERVE_EVIDENCE"
    else:
        classification, decision = "INCONCLUSIVE", "NO_RULE_CHANGE_INTERVAL_CROSSES_ZERO"
    return {
        "schema_version": "1.0.0",
        "evaluation_id": f"learning-{experiment_id}-{hashlib.sha256('|'.join(evidence_ids).encode()).hexdigest()[:12]}",
        "experiment_id": experiment_id, "channel_id": CHANNEL_ID,
        "classification": classification, "metric": metric,
        "baseline": baseline, "treatment": treatment, "delta": delta,
        "uncertainty": {"level": 0.95, "lower": lower, "upper": upper, "method": "NORMAL_APPROXIMATION_FROM_INDEPENDENT_STANDARD_ERRORS"},
        "validity": validity, "decision": decision, "evidence_ids": evidence_ids,
        "evaluated_at": evaluated_at, "technical_cost_brl": 0,
    }


def validate_preregistered_protocol_activation(
    root: Path,
    *,
    protocol_path: Path,
    completion_job: dict[str, Any],
) -> dict[str, Any]:
    """Validate every substantive activation precondition without mutating."""

    root = root.resolve()
    experiments = (root / BASE / "experiments").resolve()
    staged = protocol_path.resolve()
    try:
        staged.relative_to(experiments)
    except ValueError as exc:
        raise PermissionError("staged protocol is outside the Phase 6 experiment store") from exc
    if not staged.is_file() or staged.name in {"active.json", "latest.json"}:
        raise PermissionError("an immutable staged protocol is required before activation")

    checkpoint = completion_job.get("checkpoint") or {}
    expected_path = staged.relative_to(root).as_posix()
    expected_hash = _sha256(staged)
    prepared_or_committed = completion_job.get("state") == "SUCCEEDED" or (
        completion_job.get("state") == "LEASED"
        and isinstance(completion_job.get("lease_owner"), str)
        and bool(completion_job.get("lease_owner"))
    )
    if not (
        prepared_or_committed
        and completion_job.get("task_type") == "OWNED_METRICS_CHECKPOINT"
        and completion_job.get("operation_id") == "heroverse-phase6-controlled-longform-v1"
        and completion_job.get("channel_id") == CHANNEL_ID
        and (completion_job.get("payload") or {}).get("video_id") == VIDEO_ID
        and checkpoint.get("observer_transaction_version") == "phase6-owned-observer-transaction-v2"
        and checkpoint.get("experiment_protocol_stage") == expected_path
        and checkpoint.get("experiment_protocol_stage_hash") == expected_hash
    ):
        raise PermissionError(
            "exact prepared or successful observer transaction does not authorize protocol activation"
        )

    protocol = _read(staged)
    _validate(root, "phase6_experiment_protocol.schema.json", protocol)
    diagnosis = protocol.get("diagnosis") or {}
    if not (
        protocol.get("schema_version") == "1.1.0"
        and protocol.get("status") == "PREREGISTERED"
        and protocol.get("channel_id") == CHANNEL_ID
        and (protocol.get("baseline") or {}).get("snapshot_id") == checkpoint.get("baseline_snapshot_id")
        and diagnosis.get("path") == checkpoint.get("diagnostic_decision")
        and checkpoint.get("diagnostic_decision_hash")
    ):
        raise PermissionError("staged protocol does not match the committed observer evidence")
    diagnosis_path = (root / str(diagnosis["path"])).resolve()
    if (
        not diagnosis_path.is_file()
        or diagnosis_path.is_symlink()
        or _sha256(diagnosis_path) != checkpoint["diagnostic_decision_hash"]
    ):
        raise PermissionError("committed diagnosis hash does not match the staged protocol")

    active = experiments / "active.json"
    latest = experiments / "latest.json"
    if active.is_symlink() or (active.exists() and not active.is_file()):
        raise PermissionError("active protocol target is not a regular file")
    if active.is_file() and active.read_bytes() != _canonical(protocol):
        raise PermissionError("active protocol collides with the prepared immutable stage")
    if latest.is_symlink() or (latest.exists() and not latest.is_file()):
        raise PermissionError("latest protocol target is not a regular file")
    return protocol


def activate_preregistered_protocol(
    root: Path,
    *,
    protocol_path: Path,
    completion_job: dict[str, Any],
) -> Path:
    """Expose a staged protocol only from an exact successful observer job.

    Substantive validation may run while the job is leased, but the immutable
    active view is written only after the queue commit.  A transient filesystem
    failure is recovered from the successful job by the observer outbox scan.
    """

    if completion_job.get("state") != "SUCCEEDED":
        raise PermissionError("a successful observer transaction is required for activation")
    root = root.resolve()
    staged = protocol_path.resolve()
    protocol = validate_preregistered_protocol_activation(
        root,
        protocol_path=staged,
        completion_job=completion_job,
    )

    experiments = (root / BASE / "experiments").resolve()
    active = experiments / "active.json"
    _write_immutable(active, protocol)
    _write_atomic(experiments / "latest.json", protocol)
    return active


def verify_active_preregistered_protocol(root: Path, *, protocol_path: Path) -> Path:
    """Revalidate an existing active protocol and return its immutable source.

    Later owned-metrics checkpoints do not activate a new experiment.  They may
    only proceed when ``active.json`` and ``latest.json`` remain exact copies of
    one immutable staged protocol and its pinned diagnosis still validates.
    """

    root = root.resolve()
    experiments = (root / BASE / "experiments").resolve()
    active = protocol_path.resolve()
    expected_active = (experiments / "active.json").resolve()
    latest = experiments / "latest.json"
    if active != expected_active or not active.is_file() or active.is_symlink():
        raise PermissionError("the exact regular active protocol is required for reentry")
    if not latest.is_file() or latest.is_symlink() or latest.read_bytes() != active.read_bytes():
        raise PermissionError("active/latest protocol bytes diverged during reentry")

    protocol = _read(active)
    _validate(root, "phase6_experiment_protocol.schema.json", protocol)
    diagnosis = protocol.get("diagnosis") or {}
    treatment = protocol.get("treatment") or {}
    if not (
        protocol.get("schema_version") == "1.1.0"
        and protocol.get("status") == "PREREGISTERED"
        and protocol.get("channel_id") == CHANNEL_ID
        and (protocol.get("baseline") or {}).get("snapshot_id")
        and treatment.get("variable") != "NONE"
        and treatment.get("preregistered_before_production") is True
        and isinstance(diagnosis.get("diagnosis_id"), str)
        and isinstance(diagnosis.get("path"), str)
    ):
        raise PermissionError("the active Phase 6 protocol is not an exact preregistration")

    diagnoses = (root / BASE / "diagnoses").resolve()
    diagnosis_path = (root / diagnosis["path"]).resolve()
    try:
        diagnosis_path.relative_to(diagnoses)
    except ValueError as exc:
        raise PermissionError("active protocol diagnosis escaped the immutable diagnosis store") from exc
    if (
        not diagnosis_path.is_file()
        or diagnosis_path.is_symlink()
        or diagnosis_path.name == "latest.json"
        or diagnosis_path.name != f"{diagnosis['diagnosis_id']}.json"
    ):
        raise PermissionError("active protocol diagnosis is not the exact immutable record")
    diagnosis_value = _read(diagnosis_path)
    _validate(root, "phase6_diagnostic_decision.schema.json", diagnosis_value)
    decision = diagnosis_value.get("decision") or {}
    baseline = diagnosis_value.get("baseline") or {}
    stable = "|".join(
        [
            "diagnostic-policy-1.1.0",
            str(baseline.get("snapshot_id")),
            str(diagnosis_value.get("status")),
            str(decision.get("dominant_bottleneck")),
            str(decision.get("action")),
            str(decision.get("treatment_variable")),
            str(decision.get("primary_metric")),
            str(baseline.get("eligibility_scope")),
        ]
    )
    expected_diagnosis_id = "phase6-diagnosis-" + hashlib.sha256(stable.encode()).hexdigest()[:16]
    if not (
        diagnosis_value.get("diagnosis_id") == diagnosis["diagnosis_id"]
        and diagnosis_value.get("diagnosis_id") == expected_diagnosis_id
        and diagnosis_value.get("status") == diagnosis.get("status") == "DIAGNOSED"
        and diagnosis_value.get("channel_id") == CHANNEL_ID
        and baseline.get("snapshot_id") == (protocol.get("baseline") or {}).get("snapshot_id")
        and decision.get("treatment_variable") == treatment.get("variable")
        and decision.get("primary_metric") == protocol.get("primary_metric")
        and diagnosis_path.read_bytes() == _canonical(diagnosis_value)
    ):
        raise PermissionError("active protocol diagnosis identity diverged")

    active_bytes = active.read_bytes()
    if active_bytes != _canonical(protocol):
        raise PermissionError("active protocol bytes are not the canonical immutable record")
    staged_matches = [
        candidate.resolve()
        for candidate in sorted(experiments.glob("protocol-*.json"))
        if candidate.is_file()
        and not candidate.is_symlink()
        and candidate.read_bytes() == active_bytes
    ]
    if len(staged_matches) != 1:
        raise PermissionError("active protocol lacks one exact immutable staged twin")
    return staged_matches[0]


def _materialize_audio_current(root, relative, bindings, release_hash, snapshot_reference):
    """Derive current decisions from a succeeded, quota-authenticated owned read.

    No caller-provided PASS, mutable latest or legacy active experiment is input.
    Historical learning is not calibration for a new format.
    """
    from .phase5_youtube_publisher import _validate_current_release, execute_publication_pipeline
    from .queue_phase6 import TransactionalQueue
    from .central_manager_phase5 import (
        _read_owned_artifact, _validate_owned_preflight, _validate_owned_quota_debit_chain,
    )
    _validate_current_release(root, relative, bindings, release_hash)
    publication = execute_publication_pipeline(None, None, root, package_relative=relative,
        current_bindings=bindings, expected_release_hash=release_hash)
    if publication.get("status") != "COMPLETE_PUBLIC":
        raise PermissionError("Current intelligence requires completed public delivery")
    receipt_path = root / relative / "youtube-publication-receipt.json"
    receipt_hash = _sha256(receipt_path)
    video = publication["video_id"]
    matches = [job for job in TransactionalQueue(root).snapshot()["jobs"]
        if job["state"] == "SUCCEEDED" and job["task_type"] == "OWNED_METRICS_CHECKPOINT"
        and job["operation_id"] == "heroverse-audio-static-longform-v1"
        and job["payload"].get("video_id") == video
        and job["payload"].get("publication_receipt_hash") == receipt_hash
        and job["checkpoint"].get("metrics_snapshot") == snapshot_reference]
    if len(matches) != 1:
        raise PermissionError("Current intelligence snapshot lacks its unique completed owned job")
    job = matches[0]
    _validate_owned_preflight(root, job_id=job["job_id"], checkpoint=job["checkpoint"])
    path, snapshot = _read_owned_artifact(root, job_id=job["job_id"], label="owned-metrics",
        reference=snapshot_reference, expected_hash=job["checkpoint"]["metrics_snapshot_hash"],
        schema_name="own_channel_performance_snapshot.schema.json")
    _validate_owned_quota_debit_chain(root, job=job, snapshot=snapshot)
    if snapshot["channel_id"] != publication["channel_id"] or snapshot["video_id"] != video:
        raise PermissionError("Current intelligence observed delivery differs")
    config_path = root / "config/engine.json"
    instrumental = 'music_inputs' in bindings
    if instrumental:
        from .creative_direction import rest_delivery_format
        mode=rest_delivery_format(_read(Path(bindings['music_inputs']['recipe']['path'])))
    pack_path = root / "config/format_packs" / (mode['pack_file']
        if instrumental else "fp-narrated-reflection-static-v1.json")
    pack = _read(pack_path)
    expected_pack = mode['format_pack_id'] if instrumental else 'fp-narrated-reflection-static'
    if (pack.get("format_pack_id"), pack.get("version")) != (expected_pack, "1.0.0"):
        raise PermissionError("Current intelligence format cohort is incompatible")
    pins = {path: _sha256(path), receipt_path: receipt_hash, config_path: _sha256(config_path),
            pack_path: _sha256(pack_path)}
    base = relative / "intelligence"
    timestamp = _stamp(datetime.now(timezone.utc))
    prediction = build_prediction(snapshot, expected_video_id=video, created_at=timestamp)
    prediction_version = ("1.3.0" if expected_pack == "fp-christian-reflection-rest-static" else "1.2.0") if instrumental else "1.1.0"
    prediction.update(schema_version=prediction_version, operation_id="heroverse-audio-static-longform-v1")
    prediction["cohort"].update(format_pack_id=pack["format_pack_id"], format_pack_version=pack["version"])
    diagnosis = build_diagnostic_decision(snapshot, _read(config_path), expected_video_id=video, decided_at=timestamp)
    diagnosis.update(schema_version="1.2.0", operation_id="heroverse-audio-static-longform-v1")
    diagnosis["baseline"]["video_id"] = video
    diagnosis["evidence_refs"] = [snapshot_reference, "config/engine.json#quality_gates",
        (relative / "release_gate.json").as_posix(),
        (Path(bindings['music_inputs']['recipe']['path']).resolve().relative_to(root).as_posix()
         if instrumental else (relative / "narrative_script.json").as_posix())]
    protocol = build_experiment_protocol(snapshot, diagnosis=diagnosis, expected_video_id=video, created_at=timestamp)
    protocol.update(schema_version="1.2.0", protocol_id="heroverse-audio-static-single-variable-v1")
    # This observation proposes a next treatment; it does not predate the video
    # already published, or claim activation/production of the next one.
    protocol["status"] = "READY_TO_PREREGISTER" if diagnosis["status"] == "DIAGNOSED" else "WAITING_FOR_24H_BASELINE"
    protocol["treatment"]["preregistered_before_production"] = False
    if protocol["treatment"]["video_id"] != video:
        protocol["treatment"]["video_id"] = None
    diagnosis_path = root / base / "diagnoses" / f"{diagnosis['diagnosis_id']}.json"
    if "diagnosis" in protocol:
        protocol["diagnosis"]["path"] = diagnosis_path.relative_to(root).as_posix()
    protocol["causality_boundary"] = [
        "The published audio is an observational baseline, not a preregistered experiment.",
        "The next treatment and sample rule require activation before new production; this staged proposal is not activation.",
        "One favorable result cannot establish a general, cross-format, economic or causal rule.",
    ]
    records = [
        (root / base / "predictions" / f"{prediction['prediction_id']}.json", prediction, "prediction_record.schema.json", "created_at"),
        (diagnosis_path, diagnosis, "phase6_diagnostic_decision.schema.json", "decided_at"),
        (root / base / "experiments" / f"protocol-{prediction['prediction_id']}.json", protocol, "phase6_experiment_protocol.schema.json", "created_at"),
    ]
    # Validate every output/collision and re-open all authority inputs before
    # persistence. A later identical observation retains its original times.
    for target, value, schema, clock in records:
        _validate(root, schema, value)
        if target.is_file():
            previous = _read(target)
            if {k:v for k,v in previous.items() if k != clock} != {k:v for k,v in value.items() if k != clock}:
                raise PermissionError(f"immutable current intelligence collision: {target.name}")
            value[clock] = previous[clock]
    _validate_current_release(root, relative, bindings, release_hash)
    if any(_sha256(source) != digest for source, digest in pins.items()):
        raise PermissionError("Current intelligence inputs changed during evaluation")
    resident = TransactionalQueue(root).snapshot()["jobs"]
    if not any(current["job_id"] == job["job_id"] and current["state"] == "SUCCEEDED"
               and current["checkpoint"] == job["checkpoint"] for current in resident):
        raise PermissionError("Current intelligence completion changed during evaluation")
    for target, value, _, _ in records:
        _write_immutable(target, value)
    for target, value, _, _ in records:
        _write_atomic(target.parent / "latest.json", value)
    return tuple(target for target, _, _, _ in records)


def materialize_current(root: Path = ROOT, *, package_relative: Path | None = None,
                        current_bindings: dict[str, Any] | None = None,
                        expected_release_hash: str | None = None,
                        snapshot_reference: str | None = None) -> tuple[Path, Path, Path]:
    root = root.resolve()
    selection = (package_relative, current_bindings, expected_release_hash, snapshot_reference)
    if any(item is not None for item in selection):
        if any(item is None for item in selection):
            raise PermissionError("Current intelligence requires complete explicit delivery selection")
        return _materialize_audio_current(root, Path(package_relative), current_bindings,
                                          expected_release_hash, snapshot_reference)
    snapshot_path = root / "output/operations/phase6/metrics" / VIDEO_ID / "latest.json"
    snapshot = _read(snapshot_path)
    prediction_path = materialize_prediction(snapshot, root)
    config = _read(root / "config/engine.json")
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    diagnosis = build_diagnostic_decision(snapshot, config, decided_at=timestamp)
    _validate(root, "phase6_diagnostic_decision.schema.json", diagnosis)
    diagnosis_folder = root / BASE / "diagnoses"
    diagnosis_path = diagnosis_folder / f"{diagnosis['diagnosis_id']}.json"
    if diagnosis_path.is_file():
        prior = _read(diagnosis_path)
        prior_stable, current_stable = dict(prior), dict(diagnosis)
        prior_stable.pop("decided_at", None)
        current_stable.pop("decided_at", None)
        if prior_stable != current_stable:
            raise PermissionError(f"immutable diagnosis collision: {diagnosis_path.name}")
        diagnosis = prior
    else:
        _write_immutable(diagnosis_path, diagnosis)
    _write_atomic(root / DIAGNOSIS_LATEST, diagnosis)
    protocol = build_experiment_protocol(snapshot, diagnosis=diagnosis, created_at=timestamp)
    _validate(root, "phase6_experiment_protocol.schema.json", protocol)
    protocol_folder = root / BASE / "experiments"
    active_protocol_path = protocol_folder / "active.json"
    if active_protocol_path.is_file():
        active_protocol = _read(active_protocol_path)
        _validate(root, "phase6_experiment_protocol.schema.json", active_protocol)
        if (
            active_protocol.get("status") != "PREREGISTERED"
            or active_protocol.get("channel_id") != CHANNEL_ID
            or (active_protocol.get("treatment") or {}).get("variable") == "NONE"
            or (active_protocol.get("treatment") or {}).get("preregistered_before_production") is not True
        ):
            raise PermissionError("the immutable active Phase 6 experiment is not a valid preregistration")
        # Phase 6 contains one controlled live experiment. Once preregistered,
        # its baseline, variable, sample rule and timestamp must not drift when
        # later canary checkpoints are observed. Keep the human-facing latest
        # view byte-equivalent to the immutable active protocol.
        _write_atomic(protocol_folder / "latest.json", active_protocol)
        return prediction_path, diagnosis_path, active_protocol_path
    protocol_key = re.sub(r"[^A-Za-z0-9_.-]", "_", str(snapshot.get("snapshot_id") or "missing"))
    protocol_schema_key = str(protocol.get("schema_version") or "unversioned").replace(".", "_")
    protocol_path = protocol_folder / f"protocol-{protocol_key}-{protocol_schema_key}-{protocol['status'].lower()}.json"
    if protocol_path.is_file():
        prior = _read(protocol_path)
        prior_stable, current_stable = dict(prior), dict(protocol)
        prior_stable.pop("created_at", None)
        current_stable.pop("created_at", None)
        if prior_stable != current_stable:
            raise PermissionError(f"immutable protocol collision: {protocol_path.name}")
        protocol = prior
    else:
        _write_immutable(protocol_path, protocol)
    # A new PREREGISTERED protocol remains staged under this immutable name.
    # The owned-metrics transaction promotes it to active.json only after the
    # queue job has reached SUCCEEDED; see activate_preregistered_protocol().
    _write_atomic(protocol_folder / "latest.json", protocol)
    return prediction_path, diagnosis_path, protocol_path


if __name__ == "__main__":
    for artifact in materialize_current(ROOT):
        print(artifact)
