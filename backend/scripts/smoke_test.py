"""Local smoke test for the shipped Agnivedh backend.

Run from backend with the project environment active:
    python scripts/smoke_test.py
"""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app


def main() -> None:
    client = TestClient(app)

    health = client.get("/api/health")
    assert health.status_code == 200, health.text
    assert health.json().get("status") == "online"

    query = client.get(
        "/api/hotspots/query",
        params={"year": 2024, "acq_date": "2024-01-01"},
    )
    assert query.status_code == 200, query.text
    payload = query.json()
    assert payload["count"] > 0
    first = payload["hotspots"][0]
    assert first.get("worldcover_code", 0) != 0
    assert "baseline_deviation_score" in first["_comparison"]

    hotspot_id = first["id"]
    analysis = client.get(f"/api/analysis/{hotspot_id}")
    assert analysis.status_code == 200, analysis.text
    detail = analysis.json()
    assert "fire_detection" in detail
    assert "source_history" in detail
    assert detail["source_history"].get("status") in {"AVAILABLE", "UNAVAILABLE"}

    context = client.get(f"/api/osm/context/{hotspot_id}")
    assert context.status_code == 200, context.text
    assert "nearest_industry" in context.json()
    assert "critical" in context.json()

    manual = client.post(
        "/api/validation/manual",
        json={
            "latitude": float(first["latitude"]),
            "longitude": float(first["longitude"]),
            "brightness": float(first["brightness"]),
            "bright_t31": float(first["bright_t31"]),
            "frp": float(first["frp"]),
            "scan": float(first["scan"]),
            "track": float(first["track"]),
            "confidence": first["confidence"],
            "daynight": first["daynight"],
            "type": int(first["type"]),
            "acq_date": first["acq_date"],
            "acq_time": first["acq_time"],
            "worldcover_code": int(first["worldcover_code"]),
        },
    )
    assert manual.status_code == 200, manual.text
    manual_payload = manual.json()
    assert manual_payload["validation"]["same_production_pipeline"] is True
    assert "classification" in manual_payload and "risk" in manual_payload

    bad_year = client.get(
        "/api/hotspots/query",
        params={"year": 2023, "acq_date": "2023-01-01"},
    )
    assert bad_year.status_code == 400

    print("AGNIVEDH SMOKE TEST: PASS")
    print(f"2024-01-01 observations: {payload['count']}")
    print(f"sample hotspot: {hotspot_id}")
    print(f"worldcover_code: {first.get('worldcover_code')}")
    print(f"source history: {detail['source_history'].get('behaviour', detail['source_history'].get('status'))}")


if __name__ == "__main__":
    main()
