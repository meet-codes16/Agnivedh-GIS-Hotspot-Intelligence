from fastapi import APIRouter, HTTPException
import time

from app.engine import run_analysis
from app.store import get_hotspot, historical_2024_baselines, recent_event_context, persistent_source_history

router = APIRouter()


@router.get("/analysis/{hotspot_id}")
def analysis(hotspot_id: str):
    t0 = time.perf_counter()
    print(f"[ANALYSIS-START] {hotspot_id}", flush=True)

    hotspot = get_hotspot(hotspot_id)
    print(f"[TIMING] get_hotspot: {time.perf_counter() - t0:.3f}s")

    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")

    if str(hotspot.get("id", "")).startswith("F24-"):
        from app.model_service import classify_hotspot
        from app.engine import compare_hotspot, feature_engine, risk_engine
        from app.osm_facility import nearest_osm_context
        from app.fire_detection import compute_fire_detection

        t = time.perf_counter()
        baseline = historical_2024_baselines(
            hotspot["acq_date"],
            hotspot.get("daynight"),
            hotspot.get("region_key"),
        ).get(hotspot.get("region_key"))
        print(f"[TIMING] historical_2024_baselines: {time.perf_counter() - t:.3f}s")

        if not baseline:
            t = time.perf_counter()
            from app.engine import historical_baseline
            baseline = historical_baseline(hotspot)
            print(f"[TIMING] historical_baseline fallback: {time.perf_counter() - t:.3f}s")

        t = time.perf_counter()
        classification = classify_hotspot(hotspot)
        print(f"[TIMING] classify_hotspot: {time.perf_counter() - t:.3f}s")

        t = time.perf_counter()
        fire_context = recent_event_context(hotspot)
        print(f"[TIMING] recent_event_context: {time.perf_counter() - t:.3f}s")

        t = time.perf_counter()
        fire_detection = compute_fire_detection(hotspot, fire_context)
        print(f"[TIMING] compute_fire_detection: {time.perf_counter() - t:.3f}s")

        t = time.perf_counter()
        source_history = persistent_source_history(hotspot)
        print(f"[TIMING] persistent_source_history: {time.perf_counter() - t:.3f}s")

        t = time.perf_counter()
        osm_context = nearest_osm_context(
            hotspot["latitude"],
            hotspot["longitude"],
            10000,
        )
        print(f"[TIMING] nearest_osm_context: {time.perf_counter() - t:.3f}s")

        nearby = list(osm_context.get("nearby") or [])

        for place in nearby:
            place["hotspot_id"] = hotspot.get("id")

        t = time.perf_counter()
        features = feature_engine(hotspot, baseline, nearby, 1, fire_context)
        print(f"[TIMING] feature_engine: {time.perf_counter() - t:.3f}s")

        t = time.perf_counter()
        comparison = compare_hotspot(hotspot, baseline, 1)
        print(f"[TIMING] compare_hotspot: {time.perf_counter() - t:.3f}s")

        comparison["baseline_source"] = baseline.get(
            "source",
            "2022-2023 historical fallback",
        )

        t = time.perf_counter()
        risk = risk_engine(features, classification, fire_detection)
        print(f"[TIMING] risk_engine: {time.perf_counter() - t:.3f}s")

        print(f"[TIMING] TOTAL: {time.perf_counter() - t0:.3f}s")

        return {
            "hotspot": hotspot,
            "baseline": baseline,
            "nearby": nearby,
            "comparison": comparison,
            "features": features,
            "classification": classification,
            "fire_detection": fire_detection,
            "source_history": source_history,
            "risk": risk,
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


