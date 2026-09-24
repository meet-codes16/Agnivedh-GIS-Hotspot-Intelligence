from fastapi import APIRouter, HTTPException

from app.schemas import ManualValidationRequest
from app.model_service import classify_hotspot
from app.store import infer_region_key
from app.engine import historical_baseline, feature_engine, compare_hotspot, risk_engine
from app.fire_detection import compute_fire_detection
from app.osm_facility import nearby_osm_features, nearest_osm_context
from app.worldcover import lookup_worldcover

router = APIRouter()


@router.post("/validation/manual")
def manual_validation(request: ManualValidationRequest):
    daynight = str(request.daynight or "D").upper()
    if daynight not in {"D", "N"}:
        raise HTTPException(status_code=400, detail="daynight must be D or N")

    try:
        acq_time = str(request.acq_time).zfill(4)
        hour = int(acq_time[:2])
        minute = int(acq_time[2:])
        if hour > 23 or minute > 59:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="acq_time must be a valid FIRMS HHMM time")

    wc = (
        {
            "code": request.worldcover_code,
            "class": None,
            "source": "manual",
            "available": request.worldcover_code is not None,
        }
        if request.worldcover_code is not None
        else lookup_worldcover(request.latitude, request.longitude)
    )

    hotspot = {
        "id": "MANUAL-VALIDATION",
        "latitude": request.latitude,
        "longitude": request.longitude,
        "brightness": request.brightness,
        "scan": request.scan,
        "track": request.track,
        "acq_date": request.acq_date,
        "acq_time": acq_time,
        "satellite": request.satellite,
        "instrument": request.instrument,
        "confidence": request.confidence,
        "version": request.version,
        "bright_t31": request.bright_t31,
        "frp": request.frp,
        "daynight": daynight,
        "type": request.type,
        "worldcover_code": wc.get("code") or 0,
        "worldcover_class": wc.get("class") or "",
        "region_key": infer_region_key({"latitude": request.latitude, "longitude": request.longitude}),
        "study_area": "MANUAL SCENARIO",
    }

    baseline = historical_baseline(hotspot)
    classification = classify_hotspot(hotspot)
    context = {"same_pass_count": 0, "nearby_count_24h": 0, "nearby_count_72h": 0, "distinct_dates_72h": 0}
    fire_detection = compute_fire_detection(hotspot, context)
    nearby = nearby_osm_features(request.latitude, request.longitude)
    for place in nearby:
        place["hotspot_id"] = hotspot["id"]

    critical_context = nearest_osm_context(request.latitude, request.longitude)
    features = feature_engine(hotspot, baseline, nearby, 1, context)
    comparison = compare_hotspot(hotspot, baseline, 1)
    comparison.update({
        "baseline_source": "2022-2023 historical FIRMS baseline",
        "baseline_leakage_safe": True,
        "validation_mode": True,
    })
    risk = risk_engine(features, classification, fire_detection)

    return {
        "hotspot": hotspot,
        "baseline": baseline,
        "nearby": nearby,
        "comparison": comparison,
        "features": features,
        "classification": classification,
        "fire_detection": fire_detection,
        "risk": risk,
        "critical_context": critical_context.get("critical"),
        "nearest_industry": critical_context.get("nearest_industry"),
        "osm_context": {
            "available": bool(critical_context.get("available")),
            "radius_km": critical_context.get("radius_km", 5.0),
            "source": critical_context.get("source", "OpenStreetMap"),
        },
        "worldcover": wc,
        "validation": {
            "mode": "manual",
            "same_production_pipeline": True,
            "uses_2024_target_label": False,
            "worldcover_required_by_model": True,
            "worldcover_available": bool(wc.get("available")),
            "worldcover_warning": None if wc.get("available") else "WorldCover could not be resolved automatically. Prediction still runs, but this manual case should not be treated as a high-confidence validation case until the WorldCover input is supplied.",
        },
        "prototype": False,
    }
