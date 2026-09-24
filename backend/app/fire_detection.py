"""Evidence-based fire-existence layer for 2024 FIRMS detections.

This is deliberately separate from the supervised source/type classifier.
The supplied labels describe source/context and are not independent ground truth
for whether a satellite thermal detection was a real fire. Therefore this layer
returns an evidence score, not a claimed ground-truth probability.
"""
from __future__ import annotations

import math
from typing import Any


def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-min(x, 40.0))
        return 1.0 / (1.0 + z)
    z = math.exp(min(-x, 40.0))
    return z / (1.0 + z)


def _firms_confidence(value: Any) -> float:
    if isinstance(value, str):
        return {"l": 0.45, "n": 0.70, "h": 0.90}.get(value.lower(), 0.60)
    try:
        return _clip(float(value) / 100.0)
    except (TypeError, ValueError):
        return 0.60


def compute_fire_detection(hotspot: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}

    try:
        brightness = float(hotspot.get("brightness") or 0)
        bright_t31 = float(hotspot.get("bright_t31") or 0)
        frp = max(0.0, float(hotspot.get("frp") or 0))
    except (TypeError, ValueError):
        brightness, bright_t31, frp = 0.0, 0.0, 0.0

    brightness_signal = _sigmoid((brightness - bright_t31 - 18.0) / 7.5)
    frp_signal = 1.0 - math.exp(-frp / 8.0)
    satellite_confidence = _firms_confidence(hotspot.get("confidence"))

    nearby_24h = int(context.get("nearby_count_24h") or 0)
    nearby_72h = int(context.get("nearby_count_72h") or 0)
    distinct_dates = int(context.get("distinct_dates_72h") or 0)
    same_pass = int(context.get("same_pass_count") or 0)

    prior_cluster_signal = 1.0 - math.exp(-nearby_24h / 3.0)
    same_pass_cluster_signal = 1.0 - math.exp(-same_pass / 2.0)
    cluster_signal = max(prior_cluster_signal, same_pass_cluster_signal)
    persistence_signal = min(
        1.0,
        0.55 * (1.0 - math.exp(-nearby_72h / 4.0))
        + 0.45 * (distinct_dates / 3.0),
    )

    # The score is intentionally conservative: one isolated low-signal pixel
    # should not look like a confirmed fire merely because the type classifier
    # is confident about its source/context.
    score = 100.0 * (
        0.30 * satellite_confidence
        + 0.25 * brightness_signal
        + 0.20 * frp_signal
        + 0.15 * cluster_signal
        + 0.10 * persistence_signal
    )

    # A single weak/isolated detection is explicitly prevented from receiving
    # a high fire-existence score.
    if nearby_24h == 0 and nearby_72h == 0 and same_pass == 0:
        score = min(score, 58.0)
    if satellite_confidence < 0.5 and frp < 3.0 and brightness_signal < 0.55:
        score = min(score, 42.0)

    score = int(round(_clip(score, 0.0, 100.0)))

    if score >= 65:
        status = "LIKELY FIRE"
        level = "HIGH"
    elif score >= 45:
        status = "REVIEW"
        level = "MEDIUM"
    else:
        status = "POSSIBLE THERMAL ANOMALY"
        level = "LOW"

    method = (
        "FIRMS signal only; prior 2024 spatial-temporal evidence deferred until selection"
        if not context
        else "FIRMS signal + prior 2024 spatial-temporal persistence evidence"
    )

    return {
        "fire_confidence": score,
        "status": status,
        "level": level,
        "evidence": {
            "satellite_signal": round(satellite_confidence * 100),
            "brightness_signal": round(brightness_signal * 100),
            "frp_signal": round(frp_signal * 100),
            "nearby_detections_24h": nearby_24h,
            "nearby_detections_72h": nearby_72h,
            "distinct_days_72h": distinct_dates,
            "same_pass_detections": same_pass,
            "cluster_signal": round(cluster_signal * 100),
            "persistence_signal": round(persistence_signal * 100),
        },
        "method": method,
        "calibration_note": "Evidence score; not an independently ground-truth-calibrated probability of a real fire.",
    }
