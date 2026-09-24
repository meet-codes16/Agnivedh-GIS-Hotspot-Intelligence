"""
Agnivedh intelligence engines.

Architecture:
    2022-2023 historical FIRMS
            |
            +--> historical baseline
            |
            +--> trained source classifier
            |
            v
        2024 inference
            |
            +--> baseline comparison
            +--> risk engine

Important:
- The source classifier is loaded separately by app.model_service.
- The baseline is built only from historical 2022-2023 FIRMS data.
- 2024 observations are inference/test observations and are NOT used
  to construct the historical baseline.
- No target/source labels are used by the baseline engine.
"""

from __future__ import annotations

from pathlib import Path
import json
import math
from typing import Any


# ---------------------------------------------------------------------------
# PATHS / BASELINE ARTIFACT
# ---------------------------------------------------------------------------

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"

_BASELINE_PROFILES: dict[str, dict[str, Any]] = {}
_BASELINE_META: dict[str, Any] = {}

_BASELINE_PATH = MODEL_DIR / "baseline_profiles.json"

if _BASELINE_PATH.exists():
    try:
        _blob = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))

        _BASELINE_PROFILES = _blob.get("profiles", {}) or {}
        _BASELINE_META = _blob

    except (OSError, json.JSONDecodeError):
        _BASELINE_PROFILES = {}
        _BASELINE_META = {}


# ---------------------------------------------------------------------------
# HISTORICAL BASELINE
# ---------------------------------------------------------------------------


def aggregate_region_baseline(rows: list[dict], fallback: dict | None = None) -> dict:
    """Build a robust short-history baseline from prior FIRMS rows only."""
    if not rows:
        return fallback or historical_baseline({"latitude": 0, "longitude": 0, "acq_date": "2024-01-01"})

    try:
        import pandas as pd
        frame = pd.DataFrame(rows)
        frame["frp_num"] = pd.to_numeric(frame.get("frp"), errors="coerce").fillna(0.0)
        frame["lat_num"] = pd.to_numeric(frame.get("latitude"), errors="coerce")
        frame["lon_num"] = pd.to_numeric(frame.get("longitude"), errors="coerce")
        frame["date"] = pd.to_datetime(frame.get("acq_date"), errors="coerce")
        raw_time = pd.to_numeric(frame.get("acq_time"), errors="coerce").fillna(0).astype(int)
        frame["hour"] = raw_time // 100 + (raw_time % 100) / 60.0
        frame["hour_bin"] = frame["hour"].astype(int).clip(0, 23)
        valid_dates = frame["date"].dropna().dt.date
        daily = valid_dates.nunique()
        hours = frame.groupby("hour_bin")["frp_num"].median()
        freq = frame.groupby("hour_bin").size()
        hour_value = float(frame["hour"].median()) if len(frame) else 0.0
        hour_display = int(hour_value)
        minute = int(round((hour_value - hour_display) * 60))
        if minute >= 60:
            hour_display += 1
            minute = 0
        return {
            "region": fallback.get("region", "2024 historical window") if fallback else "2024 historical window",
            "normal_frp": float(frame["frp_num"].median()),
            "normal_frequency": float(len(frame) / max(daily, 1)),
            "normal_hour": f"{hour_display % 24:02d}:{minute:02d}",
            "normal_hour_value": hour_value % 24,
            "normal_daynight_ratio": float((frame.get("daynight", "") == "N").mean()),
            "normal_persistence": "PERSISTENT" if daily >= 30 else ("RECURRENT" if daily >= 5 else "SPARSE"),
            "persistence_score": float(min(daily / 30.0, 1.0)),
            "normal_location_density": float(len(frame)),
            "location_stability": float(1.0 / (1.0 + float(frame[["lat_num", "lon_num"]].std().fillna(0).mean() * 100.0))),
            "hourly_frp": {str(h): (float(hours[h]) if h in hours.index else None) for h in range(24)},
            "hourly_frequency": {str(h): int(freq[h]) if h in freq.index else 0 for h in range(24)},
            "notes": f"Leakage-safe prior 2024 observations only; {len(frame)} detections across {daily} dates.",
            "source": "2024 historical observations before selected date",
        }
    except Exception:
        return fallback or {}

def historical_baseline(hotspot: dict) -> dict:
    """
    Return the historical baseline profile applicable to a hotspot.

    Baseline lookup:
        1-degree latitude/longitude grid + calendar month

    Example:
        grid = 22_75
        month = 1

        lookup key:
            22_75|1

    The baseline artifact is generated from historical 2022-2023 FIRMS
    observations only.

    It does NOT use:
        - 2024 target labels
        - predicted labels
        - source classification
        - risk score
    """

    try:
        lat = float(hotspot.get("latitude") or 0)
    except (TypeError, ValueError):
        lat = 0.0

    try:
        lon = float(hotspot.get("longitude") or 0)
    except (TypeError, ValueError):
        lon = 0.0

    date = str(hotspot.get("acq_date") or "")

    try:
        month = int(date[5:7])
        if month < 1 or month > 12:
            raise ValueError
    except (ValueError, TypeError):
        month = 1

    grid_lat = math.floor(lat)
    grid_lon = math.floor(lon)

    grid_key = f"{grid_lat}_{grid_lon}"
    profile_key = f"{grid_key}|{month}"

    # Month-level global fallback, if available.
    global_profile = _BASELINE_PROFILES.get(f"GLOBAL|{month}")

    # Final fallback when no historical profile exists.
    fallback = global_profile or {
        "region": "GLOBAL",
        "normal_frp": 0.0,
        "normal_frequency": 0.0,
        "normal_hour": "00:00",
        "normal_hour_value": 0.0,
        "normal_daynight_ratio": 0.0,
        "normal_persistence": "UNKNOWN",
        "persistence_score": 0.0,
        "normal_location_density": 0.0,
        "location_stability": 0.0,
        "hourly_frp": {str(hour): None for hour in range(24)},
        "hourly_frequency": {str(hour): 0 for hour in range(24)},
        "notes": (
            "No historical profile available for this "
            "grid/month combination."
        ),
    }

    return _BASELINE_PROFILES.get(profile_key) or fallback


def historical_baseline_metadata() -> dict:
    """
    Metadata describing the historical baseline artifact.

    This is useful for the API/UI so the system can explicitly show that
    the baseline comes from 2022-2023 historical FIRMS observations.
    """

    source_years = _BASELINE_META.get("source_years", [2022, 2023])

    try:
        source_years = [
            int(year)
            for year in source_years
        ]
    except (TypeError, ValueError):
        source_years = [2022, 2023]

    return {
        "source": "2022-2023 historical FIRMS baseline",
        "source_years": source_years,
        "leakage_safe": True,
        "profile_count": len(_BASELINE_PROFILES),
        "grid_size_degrees": _BASELINE_META.get(
            "grid_size_degrees",
            1,
        ),
        "baseline_rows": _BASELINE_META.get(
            "rows",
            0,
        ),
    }


# ---------------------------------------------------------------------------
# TIME / DEVIATION HELPERS
# ---------------------------------------------------------------------------

def parse_acq_hour(acq_time: Any) -> float:
    """
    Convert FIRMS acquisition time into decimal hours.

    Examples:
        0000 -> 0.0
        0930 -> 9.5
        1430 -> 14.5
        2350 -> 23.833...
    """

    raw = str(acq_time or "0000").strip().zfill(4)

    # Keep only the expected numeric form where possible.
    try:
        value = int(raw)

        hour = value // 100
        minute = value % 100

        if hour < 0 or hour > 23:
            return 0.0

        if minute < 0 or minute > 59:
            return 0.0

        return hour + minute / 60.0

    except (TypeError, ValueError):
        return 0.0


def calculate_deviation(current: float, baseline: float) -> float:
    """
    Percentage deviation from baseline.

    baseline = 0:
        current = 0 -> 0%
        current > 0 -> 100%

    The 100% result is intentionally a bounded representation of
    "activity exists where historical baseline was zero".
    """

    try:
        current_value = float(current)
    except (TypeError, ValueError):
        current_value = 0.0

    try:
        baseline_value = float(baseline)
    except (TypeError, ValueError):
        baseline_value = 0.0

    if baseline_value == 0:
        return 0.0 if current_value == 0 else 100.0

    return (
        (current_value - baseline_value)
        / baseline_value
    ) * 100.0


def calculate_normal_frp(baseline: dict) -> float:
    """Return historical normal FRP."""

    try:
        return float(baseline.get("normal_frp") or 0)
    except (TypeError, ValueError):
        return 0.0


def calculate_hotspot_frequency(baseline: dict) -> float:
    """Return historical normal hotspot frequency."""

    try:
        return float(
            baseline.get("normal_frequency") or 0
        )
    except (TypeError, ValueError):
        return 0.0


def calculate_normal_timing(baseline: dict) -> str:
    """Return historical normal acquisition time."""

    return str(
        baseline.get("normal_hour") or "00:00"
    )


def calculate_persistence(baseline: dict) -> dict:
    """Return historical persistence label and score."""

    try:
        score = float(
            baseline.get("persistence_score") or 0
        )
    except (TypeError, ValueError):
        score = 0.0

    return {
        "label": baseline.get(
            "normal_persistence",
            "UNKNOWN",
        ),
        "score": score,
    }


def calculate_location_stability(baseline: dict) -> float:
    """Return historical spatial stability."""

    try:
        return float(
            baseline.get("location_stability") or 0
        )
    except (TypeError, ValueError):
        return 0.0


def deviation_band(pct: float) -> str:
    """
    Convert percentage deviation into a descriptive band.
    """

    try:
        abs_pct = abs(float(pct))
    except (TypeError, ValueError):
        abs_pct = 0.0

    if abs_pct >= 100:
        return "HIGH DEVIATION"

    if abs_pct >= 40:
        return "MODERATE DEVIATION"

    return "NEAR BASELINE"


# ---------------------------------------------------------------------------
# GIS PROXIMITY HELPERS
# ---------------------------------------------------------------------------

def nearest_distance(
    places: list,
    category: str,
) -> float | None:
    """
    Return nearest distance for a specific GIS category.

    `nearby` is supplied by the existing GIS/store layer.
    """

    distances: list[float] = []

    for place in places or []:
        if not isinstance(place, dict):
            continue

        if place.get("category") != category:
            continue

        try:
            distance = float(
                place.get("distance_km")
            )
        except (TypeError, ValueError):
            continue

        distances.append(distance)

    return min(distances) if distances else None


def proximity_score(
    distance_km: float | None,
    near: float = 1.5,
    far: float = 12.0,
) -> float:
    """
    Convert distance into a 0-1 proximity score.

    <= near km -> 1
    >= far km  -> 0
    between    -> linearly interpolated
    """

    if distance_km is None:
        return 0.0

    try:
        distance = float(distance_km)
    except (TypeError, ValueError):
        return 0.0

    if distance <= near:
        return 1.0

    if distance >= far:
        return 0.0

    return 1.0 - (
        (distance - near)
        / (far - near)
    )


# ---------------------------------------------------------------------------
# FEATURE ENGINE
# ---------------------------------------------------------------------------

def feature_engine(
    hotspot: dict,
    baseline: dict,
    nearby: list,
    region_count: int = 1,
    event_context: dict | None = None,
) -> dict:
    """
    Build inference/risk features for one hotspot.

    Important:
    These features are NOT used to retrain the source classifier.
    They are used by the intelligence/risk layer after classification.
    """

    current_frp = hotspot.get("frp") or 0

    frp_dev = calculate_deviation(
        current_frp,
        baseline.get("normal_frp") or 0,
    )

    freq_dev = calculate_deviation(
        float(region_count),
        baseline.get("normal_frequency") or 0,
    )

    current_hour = parse_acq_hour(
        hotspot.get("acq_time")
    )

    try:
        normal_hour = float(
            baseline.get(
                "normal_hour_value",
                current_hour,
            )
        )
    except (TypeError, ValueError):
        normal_hour = current_hour

    hour_difference = abs(
        current_hour - normal_hour
    )

    # Circular clock difference:
    # e.g. 23:00 and 01:00 are 2 hours apart,
    # not 22 hours apart.
    hour_delta = min(
        hour_difference,
        24.0 - hour_difference,
    )

    dist_ind = nearest_distance(
        nearby,
        "Industrial Facility",
    )

    dist_forest = nearest_distance(
        nearby,
        "Forest",
    )

    dist_mine = nearest_distance(
        nearby,
        "Mine",
    )

    dist_oil = nearest_distance(
        nearby,
        "Oil/Gas Facility",
    )

    daynight = str(
        hotspot.get("daynight") or ""
    ).upper()

    return {
        # Original FIRMS measurements
        "brightness": hotspot.get("brightness"),
        "bright_t31": hotspot.get("bright_t31"),
        "frp": hotspot.get("frp"),
        "scan": hotspot.get("scan"),
        "track": hotspot.get("track"),
        "confidence": hotspot.get("confidence"),
        "daynight": hotspot.get("daynight"),
        "type": hotspot.get("type"),

        # Location / time
        "latitude": hotspot.get("latitude"),
        "longitude": hotspot.get("longitude"),
        "acq_date": hotspot.get("acq_date"),
        "acq_time": hotspot.get("acq_time"),

        # Historical-baseline comparison features
        "frp_deviation": frp_dev,
        "frequency_deviation": freq_dev,
        "temporal_deviation": (
            hour_delta / 12.0
        ) * 100.0,

        # Current-event persistence is derived only from detections that
        # occurred before the selected hotspot.  Do not substitute the
        # regional historical baseline persistence here: that describes the
        # region's normal behaviour, not persistence of this hotspot.
        "location_persistence": min(
            1.0,
            0.55 * min(float((event_context or {}).get("nearby_count_72h") or 0) / 4.0, 1.0)
            + 0.45 * min(float((event_context or {}).get("distinct_dates_72h") or 0) / 3.0, 1.0),
        ),
        "regional_baseline_persistence": baseline.get("persistence_score", 0),

        "night_ratio": (
            1
            if daynight == "N"
            else 0
        ),

        "spatial_stability": baseline.get(
            "location_stability",
            0,
        ),

        # GIS proximity
        "industrial_proximity": proximity_score(
            dist_ind
        ),

        "forest_proximity": proximity_score(
            dist_forest
        ),

        "mine_proximity": proximity_score(
            dist_mine
        ),

        "oilgas_proximity": proximity_score(
            dist_oil
        ),

        # GIS details for frontend
        "gis": {
            "distance_to_industrial": dist_ind,

            "distance_to_road": nearest_distance(
                nearby,
                "Road",
            ),

            "distance_to_settlement": nearest_distance(
                nearby,
                "Settlement",
            ),

            "distance_to_forest": dist_forest,

            "distance_to_mine": dist_mine,

            "distance_to_water": nearest_distance(
                nearby,
                "Water Body",
            ),

            "nearby_facility_count": len(
                [
                    place
                    for place in (nearby or [])
                    if isinstance(place, dict)
                    and place.get("category")
                    in {
                        "Industrial Facility",
                        "Oil/Gas Facility",
                        "Power Plant",
                        "Mine",
                    }
                ]
            ),
        },

        "prototype": False,
    }


# ---------------------------------------------------------------------------
# RISK ENGINE
# ---------------------------------------------------------------------------

def risk_engine(
    features: dict,
    classification: dict,
    fire_detection: dict | None = None,
) -> dict:
    """
    Calculate an intelligence risk score from:
        - FRP deviation
        - historical persistence
        - night activity
        - GIS proximity
        - source classification
        - FIRMS confidence

    This is a deterministic risk layer.

    It does NOT replace the ML source classifier and does NOT use
    future/test target labels.
    """

    # FRP deviation contribution.
    try:
        frp_deviation = float(
            features.get("frp_deviation") or 0
        )
    except (TypeError, ValueError):
        frp_deviation = 0.0

    frp_abs = min(
        abs(frp_deviation) / 150.0,
        1.0,
    )

    # Historical persistence.
    try:
        persist = float(
            features.get(
                "location_persistence"
            ) or 0
        )
    except (TypeError, ValueError):
        persist = 0.0

    persist = max(
        0.0,
        min(1.0, persist),
    )

    # Night activity.
    try:
        night = float(
            features.get("night_ratio") or 0
        )
    except (TypeError, ValueError):
        night = 0.0

    night = max(
        0.0,
        min(1.0, night),
    )

    # GIS proximity.
    try:
        industrial = float(
            features.get(
                "industrial_proximity"
            ) or 0
        )
    except (TypeError, ValueError):
        industrial = 0.0

    try:
        mine = float(
            features.get(
                "mine_proximity"
            ) or 0
        )
    except (TypeError, ValueError):
        mine = 0.0

    try:
        forest = float(
            features.get(
                "forest_proximity"
            ) or 0
        )
    except (TypeError, ValueError):
        forest = 0.0

    industrial = max(
        0.0,
        min(1.0, industrial),
    )

    mine = max(
        0.0,
        min(1.0, mine),
    )

    forest = max(
        0.0,
        min(1.0, forest),
    )

    # FIRMS confidence.
    raw_conf = features.get("confidence")

    if isinstance(raw_conf, str):
        conf = {
            "l": 0.50,
            "n": 0.75,
            "h": 1.00,
        }.get(
            raw_conf.lower(),
            0.75,
        )
    else:
        try:
            conf = float(
                raw_conf
                if raw_conf is not None
                else 75
            ) / 100.0
        except (TypeError, ValueError):
            conf = 0.75

    conf = max(
        0.0,
        min(1.0, conf),
    )

    # Classification-dependent deterministic weight.
    label = str(
        classification.get(
            "label",
            "Other",
        )
    )

    class_weight = {
        "Industrial": 0.55,
        "Mining": 0.55,
        "Gas Flare": 0.48,
        "Wildfire": 0.50,
        "Agricultural Burning": 0.32,
        "Agriculture": 0.32,
        "Other": 0.35,
    }.get(
        label,
        0.35,
    )

    proximity = max(
        industrial,
        mine,
        forest * 0.7,
    )

    # Fire-existence evidence is a gating factor. A highly confident source
    # label must not turn an isolated thermal anomaly into a high-risk fire.
    fire_conf = 0.5
    if fire_detection:
        try:
            fire_conf = max(0.0, min(1.0, float(fire_detection.get("fire_confidence", 50)) / 100.0))
        except (TypeError, ValueError):
            fire_conf = 0.5

    # Deterministic risk formula.
    raw_score = (
        frp_abs * 28
        + persist * 18
        + night * 12
        + proximity * 16
        + class_weight * 16
        + conf * 10
    )

    # Keep a meaningful risk floor for strong satellite evidence, but cap the
    # contribution when fire existence itself is weak.
    raw_score *= 0.35 + 0.65 * fire_conf

    score = round(
        max(
            8,
            min(
                96,
                raw_score,
            ),
        )
    )

    # Operational escalation: a high fire-existence signal should not remain
    # visually LOW merely because the source class/proximity terms are modest.
    # This is a deterministic triage rule, not a calibrated probability.
    if fire_detection and fire_detection.get("status") == "LIKELY FIRE":
        score = max(score, 55)
        same_pass = int((fire_detection.get("evidence") or {}).get("same_pass_detections") or 0)
        if (
            same_pass >= 2
            and label == "Wildfire"
            and abs(frp_deviation) >= 20
        ):
            score = max(score, 65)

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 40:
        level = "MODERATE"
    else:
        level = "LOW"

    def band(value: float) -> str:
        if value >= 0.7:
            return "HIGH"

        if value >= 0.4:
            return "MODERATE"

        return "LOW"

    # Determine strongest GIS proximity driver.
    if (
        industrial >= mine
        and industrial >= forest
    ):
        prox_name = "Industrial proximity"

    elif mine >= forest:
        prox_name = "Mine proximity"

    else:
        prox_name = "Forest proximity"

    drivers = sorted(
        [
            {
                "name": "FRP deviation",
                "level": band(frp_abs),
                "value": round(frp_abs, 4),
            },
            {
                "name": "Persistence",
                "level": band(persist),
                "value": round(persist, 4),
            },
            {
                "name": "Night activity",
                "level": band(night),
                "value": round(night, 4),
            },
            {
                "name": prox_name,
                "level": band(proximity),
                "value": round(proximity, 4),
            },
        ],
        key=lambda item: item["value"],
        reverse=True,
    )

    drivers = list(locals().get("drivers", []))
    drivers.insert(0, {
        "name": "Fire existence evidence",
        "value": fire_conf,
        "level": "HIGH" if fire_conf >= 0.70 else ("MODERATE" if fire_conf >= 0.45 else "LOW"),
    })

    return {
        "score": score,
        "level": level,
        "drivers": drivers,
        "prototype": False,
    }


# ---------------------------------------------------------------------------
# HOTSPOT VS BASELINE COMPARISON
# ---------------------------------------------------------------------------

def compare_hotspot(
    hotspot: dict,
    baseline: dict,
    region_count: int = 1,
) -> dict:
    """
    Compare one current hotspot against its historical baseline.
    """

    try:
        current_frp = float(
            hotspot.get("frp") or 0
        )
    except (TypeError, ValueError):
        current_frp = 0.0

    normal_frp = calculate_normal_frp(
        baseline
    )

    frp_dev = calculate_deviation(
        current_frp,
        normal_frp,
    )

    current_hour = parse_acq_hour(
        hotspot.get("acq_time")
    )

    try:
        normal_hour = float(
            baseline.get(
                "normal_hour_value",
                current_hour,
            )
        )
    except (TypeError, ValueError):
        normal_hour = current_hour

    hour_difference = abs(
        current_hour - normal_hour
    )

    hour_delta = min(
        hour_difference,
        24.0 - hour_difference,
    )

    normal_frequency = (
        calculate_hotspot_frequency(
            baseline
        )
    )

    frequency_deviation = calculate_deviation(
        float(region_count),
        normal_frequency,
    )

    return {
        "region": baseline.get(
            "region",
            hotspot.get("study_area"),
        ),

        "normal_frp": normal_frp,

        "current_frp": current_frp,

        "frp_deviation": frp_dev,

        "frp_deviation_label": deviation_band(
            frp_dev
        ),

        "normal_frequency": normal_frequency,

        "normal_hour": calculate_normal_timing(
            baseline
        ),

        "temporal_deviation": (
            hour_delta / 12.0
        ) * 100.0,

        "night_ratio": baseline.get(
            "normal_daynight_ratio",
            0,
        ),

        "persistence": calculate_persistence(
            baseline
        ),

        "location_stability": (
            calculate_location_stability(
                baseline
            )
        ),

        "current_frequency": region_count,

        "frequency_deviation": frequency_deviation,

        "baseline_source": (
            "2022-2023 historical FIRMS"
        ),

        "baseline_leakage_safe": True,

        "prototype": False,
    }


# ---------------------------------------------------------------------------
# LEGACY / MAIN ANALYSIS ENTRY POINT
# ---------------------------------------------------------------------------

def run_analysis(hotspot: dict) -> dict:
    """
    Run the complete intelligence pipeline for a single hotspot.

    Flow:
        hotspot
          |
          +--> historical baseline
          |
          +--> GIS nearby context
          |
          +--> deterministic comparison/features
          |
          +--> trained source classifier
          |
          +--> deterministic risk engine
    """

    from app.store import nearby_for, list_hotspots

    # Historical baseline ONLY.
    baseline = historical_baseline(
        hotspot
    )

    # Existing GIS context layer.
    nearby = nearby_for(
        hotspot
    )

    # Count current records belonging to the same region.
    region_key = hotspot.get(
        "region_key"
    )

    try:
        region_count = sum(
            1
            for item in list_hotspots()
            if item.get("region_key")
            == region_key
        )
    except Exception:
        region_count = 1

    region_count = max(
        region_count,
        1,
    )

    # Intelligence features.
    features = feature_engine(
        hotspot,
        baseline,
        nearby,
        region_count,
    )

    # Real trained source classifier.
    from app.model_service import classify_hotspot

    classification = classify_hotspot(
        hotspot
    )

    # Baseline comparison.
    comparison = compare_hotspot(
        hotspot,
        baseline,
        region_count,
    )

    # Deterministic risk engine.
    risk = risk_engine(
        features,
        classification,
    )

    return {
        "hotspot": hotspot,

        "baseline": baseline,

        "baseline_metadata": (
            historical_baseline_metadata()
        ),

        "nearby": nearby,

        "comparison": comparison,

        "features": features,

        "classification": classification,

        "risk": risk,

        "prototype": False,
    }