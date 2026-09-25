from fastapi import APIRouter, HTTPException

from app.engine import run_analysis
from app.store import get_hotspot, historical_2024_baselines, recent_event_context, persistent_source_history

router = APIRouter()


@router.get("/analysis/{hotspot_id}")
def analysis(hotspot_id: str):
    hotspot = get_hotspot(hotspot_id)
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")

    if str(hotspot.get("id", "")).startswith("F24-"):
        from app.model_service import classify_hotspot
        from app.engine import compare_hotspot, feature_engine, risk_engine
        from app.osm_facility import nearest_osm_context
        from app.fire_detection import compute_fire_detection

        baseline = historical_2024_baselines(
            hotspot["acq_date"],
            hotspot.get("daynight"),
            hotspot.get("region_key"),
        ).get(hotspot.get("region_key"))

        if not baseline:
            from app.engine import historical_baseline
            baseline = historical_baseline(hotspot)

        classification = classify_hotspot(hotspot)

        fire_context = recent_event_context(hotspot)
        fire_detection = compute_fire_detection(hotspot, fire_context)
        source_history = persistent_source_history(hotspot)

        osm_context = nearest_osm_context(
            hotspot["latitude"],
            hotspot["longitude"],
            10000,
        )
        nearby = list(osm_context.get("nearby") or [])

        for place in nearby:
            place["hotspot_id"] = hotspot.get("id")

        features = feature_engine(hotspot, baseline, nearby, 1, fire_context)
        comparison = compare_hotspot(hotspot, baseline, 1)
        comparison["baseline_source"] = baseline.get(
            "source",
            "2022-2023 historical fallback",
        )

        return {
            "hotspot": hotspot,
            "baseline": baseline,
            "nearby": nearby,
            "comparison": comparison,
            "features": features,
            "classification": classification,
            "fire_detection": fire_detection,
            "source_history": source_history,
            "risk": risk_engine(features, classification, fire_detection),
            "critical_context": osm_context.get("critical"),
            "nearest_industry": osm_context.get("nearest_industry"),
            "osm_context": {
                "available": bool(osm_context.get("available")),
                "radius_km": osm_context.get("radius_km", 5.0),
                "source": osm_context.get("source", "OpenStreetMap"),
                "nearest_industry": osm_context.get("nearest_industry"),
                "critical": osm_context.get("critical"),
                "nearby": nearby,
            },
            "forecast": [],
            "prototype": False,
        }

    return run_analysis(hotspot)

