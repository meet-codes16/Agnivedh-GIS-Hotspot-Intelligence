from functools import lru_cache
from fastapi import APIRouter, HTTPException, Query

from app.store import (
    FORECAST,
    SOURCE,
    get_hotspot,
    list_hotspots,
    nearby_for,
    query_hotspots_2024,
    batch_same_pass_context,
)

from app.osm_facility import nearest_osm_facility, nearest_osm_context

from app.fire_detection import compute_fire_detection

from app.engine import (
    run_analysis,
    historical_baseline,
    historical_baseline_metadata,
    feature_engine,
    risk_engine,
    compare_hotspot,
)

router = APIRouter()


@router.get("/hotspots")
def get_hotspots():
    """
    Default real-data view.

    Uses actual 2024 FIRMS observations for 2024-01-01.
    Historical baseline comes exclusively from the
    independently generated 2022-2023 baseline artifact.
    """

    rows = query_hotspots_2024(
        2024,
        "2024-01-01",
        None
    )

    from app.model_service import classify_hotspots

    classifications = classify_hotspots(rows)

    # Current 2024 observation count per spatial region.
    region_counts = {}

    for row in rows:
        key = row.get("region_key") or "grid_unknown"
        region_counts[key] = region_counts.get(key, 0) + 1

    enriched = []
    pass_contexts = batch_same_pass_context(rows)

    for row, classification in zip(rows, classifications):
        # Leakage-safe 2024 fire-existence evidence. Only prior observations
        # contribute to the spatial/temporal context for this hotspot.
        # Batch view uses only the current 2024 slice for a lightweight fire
        # evidence signal. Full 72-hour prior-event evidence is computed lazily
        # when a hotspot is selected (/api/analysis/{hotspot_id}).
        fire_context = pass_contexts.get(str(row.get("id") or ""), {
            "same_pass_count": 0,
            "nearby_count_24h": 0,
            "nearby_count_72h": 0,
            "distinct_dates_72h": 0,
        })
        fire_detection = compute_fire_detection(row, fire_context)

        # IMPORTANT:
        # Baseline is ALWAYS obtained from the saved
        # 2022-2023 historical baseline.
        #
        # No 2024 observations are used to construct it.
        baseline = historical_baseline(row)

        nearby = []
        fire_context = pass_contexts.get(str(row.get("id") or ""), {
            "same_pass_count": 0,
            "nearby_count_24h": 0,
            "nearby_count_72h": 0,
            "distinct_dates_72h": 0,
        })

        features = feature_engine(
            row,
            baseline,
            nearby,
            region_counts.get(
                row.get("region_key"),
                1
            ),
            fire_context,
        )

        comparison = compare_hotspot(
            row,
            baseline,
            region_counts.get(
                row.get("region_key"),
                1
            )
        )

        enriched.append({
            **row,

            "_classification": classification,

            "_baseline": baseline,

            "_comparison": {
                **comparison,
                "baseline_source": "2022-2023 historical FIRMS baseline",
                "baseline_leakage_safe": True,
                "selected_date": "2024-01-01",
            },

            "_features": features,
            "_fire_detection": fire_detection,

            "_risk": risk_engine(
                features,
                classification,
                fire_detection,
            ),
        })

    return {
        "hotspots": enriched,
        "count": len(enriched),
        "source": "internal_2024_firms_csv",
        "date": "2024-01-01",
        "prototype": False,
        "model": "real_trained_model",
        "target_used_for_prediction": False,

        "baseline": historical_baseline_metadata(),
    }


@lru_cache(maxsize=64)
def _cached_2024_query(acq_date: str, daynight: str) -> dict:
    """
    Cache the complete deterministic inference response for a
    date + day/night combination.

    The underlying 2024 observations come from the cached CSV.
    Expensive ML/baseline/feature/risk processing therefore happens
    only once per unique request during the backend process lifetime.
    """
    filter_daynight = None if daynight == "ALL" else daynight

    rows = query_hotspots_2024(
        2024,
        acq_date,
        filter_daynight,
    )

    from app.model_service import classify_hotspots

    classifications = classify_hotspots(rows)

    region_counts = {}

    for row in rows:
        key = row.get("region_key") or "grid_unknown"
        region_counts[key] = region_counts.get(key, 0) + 1

    enriched = []
    pass_contexts = batch_same_pass_context(rows)

    for row, classification in zip(rows, classifications):
        # Use the same prior-only 2024 fire-existence evidence in the batch
        # map/risk view that is shown for a selected hotspot.
        # Batch view uses only the current 2024 slice for a lightweight fire
        # evidence signal. Full 72-hour prior-event evidence is computed lazily
        # when a hotspot is selected (/api/analysis/{hotspot_id}).
        fire_context = pass_contexts.get(str(row.get("id") or ""), {
            "same_pass_count": 0,
            "nearby_count_24h": 0,
            "nearby_count_72h": 0,
            "distinct_dates_72h": 0,
        })
        fire_detection = compute_fire_detection(row, fire_context)
        baseline = historical_baseline(row)
        nearby = []

        current_region_count = region_counts.get(
            row.get("region_key"),
            1,
        )

        features = feature_engine(
            row,
            baseline,
            nearby,
            current_region_count,
            fire_context,
        )

        comparison = compare_hotspot(
            row,
            baseline,
            current_region_count,
        )

        comparison.update({
            "baseline_source": "2022-2023 historical FIRMS baseline",
            "baseline_leakage_safe": True,
            "selected_date": acq_date,
        })

        # Keep the existing batch anomaly/risk semantics unchanged. The
        # evidence-aware risk is recalculated for the selected hotspot after
        # the full prior-event context is available.
        risk = risk_engine(
            features,
            classification,
            fire_detection,
        )

        enriched.append({
            **row,
            "_classification": classification,
            "_baseline": baseline,
            "_comparison": comparison,
            "_features": features,
            "_fire_detection": fire_detection,
            "_risk": risk,
        })

    # Relative 0-100 baseline deviation for the selected comparison set.
    # Raw deviation remains untouched for auditability; the largest absolute
    # FRP deviation in this date/day-night slice is the 100 reference.
    raw_deviations = [
        abs(float((item.get("_comparison") or {}).get("frp_deviation") or 0))
        for item in enriched
    ]
    deviation_max = max(raw_deviations, default=0.0)
    for item in enriched:
        raw = abs(float((item.get("_comparison") or {}).get("frp_deviation") or 0))
        item["_comparison"]["baseline_deviation_score"] = (
            round((raw / deviation_max) * 100, 1) if deviation_max > 0 else 0.0
        )
        item["_comparison"]["baseline_deviation_reference"] = "max absolute FRP deviation in selected 2024 date/day-night set"

    return {
        "hotspots": enriched,
        "count": len(enriched),
        "year": 2024,
        "acq_date": acq_date,
        "daynight": daynight,
        "source": "internal_2024_firms_csv",
        "model": "real_trained_model",
        "prototype": False,
        "target_used_for_prediction": False,
        "baseline": historical_baseline_metadata(),
    }


@router.get("/hotspots/query")
def query_hotspots(
    year: int = Query(
        2024,
        ge=2000,
        le=2100,
    ),
    acq_date: str = Query(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    daynight: str | None = Query(None),
):
    """
    Fetch deterministic real 2024 FIRMS observations.

    Expensive inference is cached by date + day/night filter.
    The historical baseline remains exclusively 2022-2023.
    """

    if year != int(acq_date[:4]):
        raise HTTPException(
            status_code=400,
            detail="year must match acq_date",
        )

    if year != 2024:
        raise HTTPException(
            status_code=400,
            detail="Only the supplied 2024 hotspot dataset is available",
        )

    requested_daynight = (daynight or "ALL").upper()

    if requested_daynight not in {"ALL", "D", "N"}:
        raise HTTPException(
            status_code=400,
            detail="daynight must be ALL, D or N",
        )

    try:
        return _cached_2024_query(
            acq_date,
            requested_daynight,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/hotspots/{hotspot_id}")
def get_hotspot_by_id(
    hotspot_id: str
):
    hotspot = get_hotspot(hotspot_id)

    if not hotspot:
        raise HTTPException(
            status_code=404,
            detail="Hotspot not found"
        )

    return hotspot



@router.get("/osm/context/{hotspot_id}")
def get_osm_context(hotspot_id: str):
    """Lazy combined industrial + critical-infrastructure context lookup."""
    hotspot = get_hotspot(hotspot_id)
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    try:
        latitude = float(hotspot["latitude"])
        longitude = float(hotspot["longitude"])
    except (KeyError, TypeError, ValueError):
        return {"nearest_industry": None, "critical": None, "source": "OpenStreetMap", "available": False}
    return nearest_osm_context(latitude, longitude)


@router.get("/osm/facility/{hotspot_id}")
def get_osm_facility(
    hotspot_id: str
):
    """
    Lazy OpenStreetMap facility enrichment.

    Runs only when a hotspot is selected/requested.
    Does not modify hotspot classification, baseline or risk.
    """

    hotspot = get_hotspot(hotspot_id)

    if not hotspot:
        raise HTTPException(
            status_code=404,
            detail="Hotspot not found"
        )

    try:
        latitude = float(hotspot["latitude"])
        longitude = float(hotspot["longitude"])
    except (KeyError, TypeError, ValueError):
        return {
            "facility": None,
            "source": "OpenStreetMap",
            "message": "Invalid hotspot coordinates",
        }

    facility = nearest_osm_facility(
        latitude,
        longitude,
    )

    if facility:
        facility = {
            **facility,
            "hotspot_id": hotspot_id,
        }

    return {
        "facility": facility,
        "source": "OpenStreetMap",
        "radius_km": 5,
    }
@router.get("/nearby/{hotspot_id}")
def get_nearby(
    hotspot_id: str
):
    hotspot = get_hotspot(hotspot_id)

    if not hotspot:
        raise HTTPException(
            status_code=404,
            detail="Hotspot not found"
        )

    return {
        "places": run_analysis(hotspot)["nearby"],
        "source": "mock-overpass-ready"
    }


@router.get("/forecast")
def get_forecast(
    assigned_class: str | None = None
):
    """
    Legacy forecast endpoint.

    This endpoint is kept temporarily for frontend compatibility.
    It is NOT used as the historical baseline.
    """

    key = (
        assigned_class
        if assigned_class in FORECAST
        else "default"
    )

    return {
        "series": FORECAST[key],
        "label": "LEGACY FORECAST"
    }
