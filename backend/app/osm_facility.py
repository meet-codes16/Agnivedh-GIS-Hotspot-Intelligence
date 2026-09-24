"""
OpenStreetMap nearby facility enrichment for AgniVedh.

Strategy:
1. Try Overpass for nearby OSM facility objects.
2. If Overpass is unavailable/busy, fall back to Nominatim reverse geocoding.
3. Never hardcode facility names or coordinates.
4. Preserve existing API response shape and compatibility wrappers.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

OSM_TIMEOUT = 12
OSM_QUERY_TIMEOUT = 8
NOMINATIM_TIMEOUT = 15

MAX_QUERY_RADIUS_M = 1000

CACHE_TTL_SECONDS = 30 * 60
MAX_CACHE_ITEMS = 2000

USER_AGENT = (
    "AgniVedh-GIS/1.0 "
    "(OpenStreetMap enrichment; contact project administrator)"
)


# ---------------------------------------------------------------------
# CACHE
# ---------------------------------------------------------------------

_CACHE: Dict[
    Tuple[float, float, int],
    Tuple[float, Dict[str, Any]]
] = {}

_CACHE_LOCK = threading.Lock()


def _cache_key(
    lat: float,
    lon: float,
    radius_m: int,
) -> Tuple[float, float, int]:
    return (
        round(float(lat), 4),
        round(float(lon), 4),
        int(radius_m),
    )


def _cache_get(key):
    now = time.monotonic()

    with _CACHE_LOCK:
        item = _CACHE.get(key)

        if item is None:
            return None

        created_at, value = item

        if now - created_at > CACHE_TTL_SECONDS:
            _CACHE.pop(key, None)
            return None

        return value


def _cache_set(key, value):
    now = time.monotonic()

    with _CACHE_LOCK:

        if len(_CACHE) >= MAX_CACHE_ITEMS:
            oldest_key = min(
                _CACHE,
                key=lambda k: _CACHE[k][0],
            )

            _CACHE.pop(oldest_key, None)

        _CACHE[key] = (now, value)


# ---------------------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------------------

def _safe_float(value):
    try:
        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    except (TypeError, ValueError):
        return None


def _distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:

    earth_radius_km = 6371.0088

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        +
        math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return earth_radius_km * 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(max(0.0, 1.0 - a)),
    )


# ---------------------------------------------------------------------
# OVERPASS
# ---------------------------------------------------------------------

def _named_facility_query(
    lat: float,
    lon: float,
    radius_m: int,
) -> str:

    radius_m = max(
        250,
        min(int(radius_m), MAX_QUERY_RADIUS_M),
    )

    return f"""
[out:json][timeout:{OSM_QUERY_TIMEOUT}];

(
  nwr["power"="plant"](around:{radius_m},{lat},{lon});
  nwr["power"="generator"](around:{radius_m},{lat},{lon});
  nwr["power"="substation"](around:{radius_m},{lat},{lon});

  nwr["landuse"="industrial"](around:{radius_m},{lat},{lon});
  nwr["industrial"](around:{radius_m},{lat},{lon});

  nwr["man_made"="works"](around:{radius_m},{lat},{lon});
  nwr["man_made"="factory"](around:{radius_m},{lat},{lon});
  nwr["man_made"="refinery"](around:{radius_m},{lat},{lon});

  nwr["generator:source"="nuclear"](around:{radius_m},{lat},{lon});

  nwr["landuse"="military"](around:{radius_m},{lat},{lon});
);

out center tags;
""".strip()


def _run_overpass(query: str):

    for url in OVERPASS_URLS:

        try:

            response = requests.post(
                url,
                data=query,
                timeout=OSM_TIMEOUT,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:

                print(
                    f"[OSM] {url} FAILED: "
                    f"HTTP {response.status_code}"
                )

                continue

            try:
                data = response.json()

            except ValueError as exc:

                print(
                    f"[OSM] {url} FAILED: "
                    f"invalid JSON: {exc}"
                )

                continue

            if not isinstance(data, dict):

                print(
                    f"[OSM] {url} FAILED: "
                    f"invalid response object"
                )

                continue

            return data

        except requests.Timeout:

            print(
                f"[OSM] {url} FAILED: "
                f"timeout after {OSM_TIMEOUT}s"
            )

        except requests.RequestException as exc:

            print(
                f"[OSM] {url} FAILED: "
                f"{type(exc).__name__}: {exc}"
            )

        except Exception as exc:

            print(
                f"[OSM] {url} FAILED: "
                f"{type(exc).__name__}: {exc}"
            )

    return None


# ---------------------------------------------------------------------
# OSM FACILITY CLASSIFICATION
# ---------------------------------------------------------------------

def _facility_category(tags: Dict[str, Any]) -> str:

    landuse = str(
        tags.get("landuse", "")
    ).lower()

    industrial = str(
        tags.get("industrial", "")
    ).lower()

    man_made = str(
        tags.get("man_made", "")
    ).lower()

    power = str(
        tags.get("power", "")
    ).lower()

    generator_source = str(
        tags.get("generator:source", "")
    ).lower()

    plant_source = str(
        tags.get("plant:source", "")
    ).lower()

    if (
        generator_source == "nuclear"
        or plant_source == "nuclear"
    ):
        return "Nuclear Facility"

    if power in {
        "plant",
        "generator",
        "substation",
    }:
        return "Power Facility"

    if landuse == "industrial":
        return "Industrial Facility"

    if industrial:
        return "Industrial Facility"

    if man_made in {
        "works",
        "factory",
        "refinery",
    }:
        return "Industrial Facility"

    if landuse == "military":
        return "Military Installation"

    if "military" in tags:
        return "Military Installation"

    return "Utility Facility"


def _critical_type(
    tags: Dict[str, Any]
) -> Optional[str]:

    landuse = str(
        tags.get("landuse", "")
    ).lower()

    military = str(
        tags.get("military", "")
    ).lower()

    power = str(
        tags.get("power", "")
    ).lower()

    generator_source = str(
        tags.get("generator:source", "")
    ).lower()

    plant_source = str(
        tags.get("plant:source", "")
    ).lower()

    if (
        generator_source == "nuclear"
        or plant_source == "nuclear"
    ):
        return "Nuclear Facility"

    if landuse == "military" or military:
        return "Military Installation"

    if power in {
        "plant",
        "generator",
        "substation",
    }:
        return "Critical Power Infrastructure"

    return None


# ---------------------------------------------------------------------
# OVERPASS ELEMENT PARSING
# ---------------------------------------------------------------------

def _element_coordinates(element):

    lat = _safe_float(
        element.get("lat")
    )

    lon = _safe_float(
        element.get("lon")
    )

    if lat is not None and lon is not None:
        return lat, lon

    center = element.get("center") or {}

    lat = _safe_float(
        center.get("lat")
    )

    lon = _safe_float(
        center.get("lon")
    )

    return lat, lon


def _element_id(element):

    osm_type = str(
        element.get("type", "unknown")
    )

    osm_id = str(
        element.get("id", "unknown")
    )

    return f"osm-{osm_type}-{osm_id}"


def _element_to_facility(
    element,
    hotspot_lat,
    hotspot_lon,
):

    tags = element.get("tags") or {}

    lat, lon = _element_coordinates(
        element
    )

    if lat is None or lon is None:
        return None

    category = _facility_category(tags)

    critical = _critical_type(tags)

    osm_name = str(
        tags.get("name", "")
    ).strip()

    if osm_name:

        display_name = osm_name

    elif critical:

        display_name = critical

    else:

        display_name = category

    distance = _distance_km(
        hotspot_lat,
        hotspot_lon,
        lat,
        lon,
    )

    return {
        "id": _element_id(element),
        "osm_type": element.get("type"),
        "osm_id": element.get("id"),
        "name": osm_name or display_name,
        "display_name": display_name,
        "distance_km": round(distance, 2),
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "source": "OpenStreetMap",
        "category": (
            critical
            if critical
            else category
        ),
        "_critical": critical is not None,
    }


# ---------------------------------------------------------------------
# NOMINATIM FALLBACK
# ---------------------------------------------------------------------

def _nominatim_reverse(
    lat: float,
    lon: float,
):

    try:

        response = requests.get(
            NOMINATIM_URL,
            params={
                "lat": lat,
                "lon": lon,
                "format": "jsonv2",
                "zoom": 18,
                "addressdetails": 1,
            },
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            timeout=NOMINATIM_TIMEOUT,
        )

        if response.status_code != 200:

            print(
                f"[OSM-NOMINATIM] "
                f"FAILED: HTTP {response.status_code}"
            )

            return None

        data = response.json()

        if not isinstance(data, dict):
            return None

        return data

    except requests.Timeout:

        print(
            "[OSM-NOMINATIM] FAILED: timeout"
        )

    except requests.RequestException as exc:

        print(
            "[OSM-NOMINATIM] FAILED: "
            f"{type(exc).__name__}: {exc}"
        )

    except Exception as exc:

        print(
            "[OSM-NOMINATIM] FAILED: "
            f"{type(exc).__name__}: {exc}"
        )

    return None


def _nominatim_facility(
    lat: float,
    lon: float,
):

    data = _nominatim_reverse(
        lat,
        lon,
    )

    if not data:
        return None

    address = data.get("address") or {}

    category = str(
        data.get("category", "")
    ).lower()

    osm_type = data.get(
        "osm_type",
        "unknown",
    )

    osm_id = data.get(
        "osm_id",
        "unknown",
    )

    # -------------------------------------------------------------
    # Extract actual OSM industrial / facility context.
    # -------------------------------------------------------------

    industrial_name = (
        address.get("industrial")
        or address.get("factory")
        or address.get("plant")
        or address.get("refinery")
        or address.get("warehouse")
    )

    display_name = (
        industrial_name
        or data.get("display_name")
    )

    if not display_name:
        return None

    is_industrial = bool(
        industrial_name
    )

    # Nominatim category/type can also indicate
    # industrial/man-made/power context.
    if (
        "industrial" in category
        or "industrial" in str(
            data.get("type", "")
        ).lower()
    ):
        is_industrial = True

    if not is_industrial:
        return None

    distance = _distance_km(
        lat,
        lon,
        _safe_float(data.get("lat")) or lat,
        _safe_float(data.get("lon")) or lon,
    )

    facility_name = (
        industrial_name
        or str(display_name).split(",")[0].strip()
    )

    return {
        "id": (
            f"osm-{osm_type}-{osm_id}"
        ),
        "osm_type": osm_type,
        "osm_id": osm_id,
        "name": facility_name,
        "display_name": facility_name,
        "distance_km": round(
            distance,
            2,
        ),
        "latitude": round(
            _safe_float(data.get("lat")) or lat,
            6,
        ),
        "longitude": round(
            _safe_float(data.get("lon")) or lon,
            6,
        ),
        "source": "OpenStreetMap",
        "category": "Industrial Facility",
    }


# ---------------------------------------------------------------------
# MAIN CONTEXT FUNCTION
# ---------------------------------------------------------------------

def nearest_osm_context(
    lat,
    lon,
    radius_m=1000,
):

    lat = _safe_float(lat)
    lon = _safe_float(lon)

    if lat is None or lon is None:

        return {
            "available": False,
            "radius_km": 0.0,
            "source": "OpenStreetMap",
            "nearest_industry": None,
            "critical": None,
            "nearby": [],
        }

    radius_m = max(
        250,
        min(
            int(radius_m),
            MAX_QUERY_RADIUS_M,
        ),
    )

    key = _cache_key(
        lat,
        lon,
        radius_m,
    )

    cached = _cache_get(key)

    if cached is not None:
        return cached

    # -------------------------------------------------------------
    # 1. OVERPASS
    # -------------------------------------------------------------

    query = _named_facility_query(
        lat,
        lon,
        radius_m,
    )

    data = _run_overpass(query)

    facilities = []

    if data:

        seen = set()

        for element in data.get(
            "elements",
            [],
        ):

            osm_id = _element_id(
                element
            )

            if osm_id in seen:
                continue

            seen.add(osm_id)

            facility = _element_to_facility(
                element,
                lat,
                lon,
            )

            if facility is None:
                continue

            facilities.append(
                facility
            )

    # -------------------------------------------------------------
    # 2. IF OVERPASS FAILED, NOMINATIM FALLBACK
    # -------------------------------------------------------------

    if not facilities:

        print(
            "[OSM] Overpass unavailable "
            "or returned no facilities. "
            "Trying Nominatim fallback..."
        )

        nominatim_facility = (
            _nominatim_facility(
                lat,
                lon,
            )
        )

        if nominatim_facility:

            facilities.append(
                nominatim_facility
            )

            print(
                "[OSM-NOMINATIM] "
                f"Found: "
                f"{nominatim_facility.get('name')}"
            )

    # -------------------------------------------------------------
    # 3. NO OSM RESULT
    # -------------------------------------------------------------

    if not facilities:

        result = {
            "available": False,
            "radius_km": round(
                radius_m / 1000.0,
                2,
            ),
            "source": "OpenStreetMap",
            "nearest_industry": None,
            "critical": None,
            "nearby": [],
        }

        _cache_set(
            key,
            result,
        )

        return result
        # -------------------------------------------------------------
    # 4. STRICT RADIUS FILTER
    # -------------------------------------------------------------
    max_distance_km = radius_m / 1000.0

    facilities = [
        x
        for x in facilities
        if _safe_float(x.get("distance_km")) is not None
        and _safe_float(x.get("distance_km")) <= max_distance_km
    ]

    if not facilities:
        result = {
            "available": False,
            "radius_km": round(max_distance_km, 2),
            "source": "OpenStreetMap",
            "nearest_industry": None,
            "critical": None,
            "nearby": [],
        }

        _cache_set(key, result)
        return result

    # -------------------------------------------------------------
    # 4. SORT
    # -------------------------------------------------------------

    facilities.sort(
        key=lambda x: x.get(
            "distance_km",
            float("inf"),
        )
    )

    # -------------------------------------------------------------
    # 5. CLEAN OUTPUT
    # -------------------------------------------------------------

    clean_facilities = []

    for item in facilities:

        clean = dict(item)

        clean.pop(
            "_critical",
            None,
        )

        clean_facilities.append(
            clean
        )

    # -------------------------------------------------------------
    # 6. NEAREST INDUSTRY
    # -------------------------------------------------------------

    industrial_candidates = [
        x
        for x in facilities
        if x.get("category")
        in {
            "Industrial Facility",
            "Nuclear Facility",
        }
    ]

    nearest_industry = (
        industrial_candidates[0]
        if industrial_candidates
        else None
    )

    if nearest_industry:

        nearest_industry = dict(
            nearest_industry
        )

        nearest_industry.pop(
            "_critical",
            None,
        )

    # -------------------------------------------------------------
    # 7. CRITICAL FACILITY
    # -------------------------------------------------------------

    critical_candidates = [
        x
        for x in facilities
        if x.get("_critical")
    ]

    critical = None

    if critical_candidates:

        critical = dict(
            critical_candidates[0]
        )

        critical.pop(
            "_critical",
            None,
        )

    # -------------------------------------------------------------
    # 8. FINAL RESULT
    # -------------------------------------------------------------

    result = {
        "available": True,
        "radius_km": round(
            radius_m / 1000.0,
            2,
        ),
        "source": "OpenStreetMap",
        "nearest_industry": nearest_industry,
        "critical": critical,
        "nearby": clean_facilities,
    }

    _cache_set(
        key,
        result,
    )

    return result


# ---------------------------------------------------------------------
# BACKWARD COMPATIBILITY
# ---------------------------------------------------------------------

def nearest_osm_facility(
    lat,
    lon,
    radius_m=1000,
):

    context = nearest_osm_context(
        lat=lat,
        lon=lon,
        radius_m=radius_m,
    )

    return context.get(
        "nearest_industry"
    )


def nearby_osm_features(
    lat,
    lon,
    radius_m=1000,
):

    context = nearest_osm_context(
        lat=lat,
        lon=lon,
        radius_m=radius_m,
    )

    return context.get(
        "nearby",
        [],
    )