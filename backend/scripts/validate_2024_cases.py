"""Print Agnivedh results for the independently cross-checked 2024 cases.

Run from backend with the API already running:
    python scripts/validate_2024_cases.py
"""
import json
from urllib.request import urlopen

IDS = [
    "F24-1493001",
    "F24-1493002",
    "F24-1584147",
    "F24-1584148",
    "F24-1597174",
]

for hotspot_id in IDS:
    with urlopen(f"http://127.0.0.1:8001/api/analysis/{hotspot_id}", timeout=30) as response:
        payload = json.load(response)
    h = payload["hotspot"]
    c = payload.get("classification") or {}
    f = payload.get("fire_detection") or {}
    r = payload.get("risk") or {}
    print(
        f"{hotspot_id} | {h.get('acq_date')} {h.get('acq_time')} | "
        f"{h.get('latitude')},{h.get('longitude')} | FRP {h.get('frp')} MW | "
        f"{c.get('label')} {c.get('confidence')}% | "
        f"fire={f.get('fire_confidence')} {f.get('status')} | "
        f"risk={r.get('score')} {r.get('level')}"
    )
