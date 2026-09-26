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
import time



# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

# Keep OSM enrichment bounded so a busy public endpoint cannot stall
# the complete AgniVedh analysis for tens of seconds.
OSM_TIMEOUT = 10.0
OSM_QUERY_TIMEOUT = 3
NOMINATIM_TIMEOUT = 4

MAX_QUERY_RADIUS_M = 10000

CACHE_TTL_SECONDS = 30 * 60
MAX_CACHE_ITEMS = 2000

# ------------------------------------------------------------------
# Nominatim rate-limit protection
# ------------------------------------------------------------------
_NOMINATIM_COOLDOWN_UNTIL = 0.0
_NOMINATIM_RATE_LIMIT_SECONDS = 60.0

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

    # Broad actual OSM facility context.
    # Do not require ["name"]: many real OSM facilities are mapped
    # without a name. Downstream parsing uses actual OSM tags and IDs.
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

  nwr["amenity"="fuel"](around:{radius_m},{lat},{lon});
  nwr["man_made"="storage_tank"](around:{radius_m},{lat},{lon});
  nwr["man_made"="mine"](around:{radius_m},{lat},{lon});
  nwr["landuse"="quarry"](around:{radius_m},{lat},{lon});
);

out center tags;
""".strip()


def _run_overpass(query: str):

    # Try the two commonly available public endpoints, but do not walk
    # through all endpoints for every request. The short timeout keeps
    # OSM enrichment from blocking the main analysis for ~40 seconds.
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

    military = str(
        tags.get("military", "")
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

    if man_made in {
        "refinery",
        "factory",
        "works",
    }:
        return "Industrial Facility"

    if industrial:
        return "Industrial Facility"

    if landuse == "industrial":
        return "Industrial Area"

    if military or landuse == "military":
        return "Military Installation"

    if man_made == "storage_tank":
        return "Storage Facility"

    if man_made == "mine" or landuse == "quarry":
        return "Mining Facility"

    if str(tags.get("amenity", "")).lower() == "fuel":
        return "Fuel Facility"

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

    man_made = str(
        tags.get("man_made", "")
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

    if man_made == "refinery":
        return "Critical Industrial Infrastructure"

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

    # Only a genuine OSM name may be exposed.
    # Internal category/critical labels must never become
    # fake real-world facility names.
    display_name = osm_name

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
        "name": osm_name,
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
    global _NOMINATIM_COOLDOWN_UNTIL

    # If Nominatim recently returned HTTP 429, do not hammer
    # the service again. Overpass can still be used normally.
    now = time.monotonic()

    if now < _NOMINATIM_COOLDOWN_UNTIL:
        remaining = int(
            _NOMINATIM_COOLDOWN_UNTIL - now
        )
        print(
            "[OSM-NOMINATIM] Rate-limit cooldown active; "
            f"skipping request ({remaining}s remaining)"
        )
        return None

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "lat": lat,
                "lon": lon,
                "format": "jsonv2",
                "zoom": 18,
                "addressdetails": 1,
                "extratags": 1,
                "namedetails": 1,
            },
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            timeout=NOMINATIM_TIMEOUT,
        )

        if response.status_code == 429:
            retry_after = response.headers.get(
                "Retry-After"
            )

            try:
                cooldown = float(retry_after)
            except (
                TypeError,
                ValueError,
            ):
                cooldown = _NOMINATIM_RATE_LIMIT_SECONDS

            cooldown = max(
                30.0,
                min(cooldown, 300.0),
            )

            _NOMINATIM_COOLDOWN_UNTIL = (
                time.monotonic() + cooldown
            )

            print(
                "[OSM-NOMINATIM] HTTP 429; "
                f"cooldown {int(cooldown)}s"
            )
            return None

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            return None

        return data

    except requests.RequestException as exc:
        print(
            "[OSM-NOMINATIM] FAILED:",
            exc,
        )
        return None

    except ValueError as exc:
        print(
            "[OSM-NOMINATIM] INVALID JSON:",
            exc,
        )
        return None


def _nominatim_search(
    lat: float,
    lon: float,
    radius_m: int,
):
    """Find actual named OSM facilities near the hotspot.

    This is only used after Overpass fails. A bounded search keeps the
    fallback local and avoids fabricating any facility information.
    """

    radius_m = max(
        250,
        min(int(radius_m), MAX_QUERY_RADIUS_M),
    )

    lat_delta = radius_m / 111320.0
    lon_delta = radius_m / (
        111320.0 * max(0.2, math.cos(math.radians(lat)))
    )

    viewbox = ",".join(
        [
            str(lon - lon_delta),
            str(lat + lat_delta),
            str(lon + lon_delta),
            str(lat - lat_delta),
        ]
    )

    # A single broad OSM search is preferable to several sequential
    # Nominatim calls because public Nominatim instances are rate limited.
    queries = (
        "industrial factory power plant refinery substation",
    )

    for query in queries:

        try:

            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 20,
                    "addressdetails": 1,
                    "namedetails": 1,
                    "viewbox": viewbox,
                    "bounded": 1,
                },
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
                timeout=NOMINATIM_TIMEOUT,
            )

            if response.status_code != 200:
                print(
                    "[OSM-NOMINATIM] search FAILED: "
                    f"HTTP {response.status_code}"
                )
                continue

            data = response.json()

            if not isinstance(data, list):
                continue

            facilities = []

            for item in data:

                if not isinstance(item, dict):
                    continue

                name = (
                    (item.get("name") or "").strip()
                    if isinstance(item.get("name"), str)
                    else ""
                )

                if not name:
                    display_name = item.get("display_name") or ""
                    name = str(display_name).split(",")[0].strip()

                if not name:
                    continue

                item_lat = _safe_float(item.get("lat"))
                item_lon = _safe_float(item.get("lon"))

                if item_lat is None or item_lon is None:
                    continue

                distance = _distance_km(
                    lat,
                    lon,
                    item_lat,
                    item_lon,
                )

                if distance > radius_m / 1000.0:
                    continue

                category = str(
                    item.get("category") or ""
                ).lower().strip()

                item_type = str(
                    item.get("type") or ""
                ).lower().strip()

                # Nominatim fallback must use structured OSM-derived
                # category/type fields only. Facility names and address
                # text are display information, not classification evidence.
                osm_supported = (
                    category in {
                        "industrial",
                        "man_made",
                        "power",
                        "military",
                    }
                    or item_type in {
                        "works",
                        "factory",
                        "refinery",
                        "industrial",
                        "plant",
                        "power",
                        "generator",
                        "substation",
                        "warehouse",
                        "military",
                    }
                )

                if not osm_supported:
                    continue

                critical = None

                if item_type in {
                    "power",
                    "plant",
                    "generator",
                    "substation",
                } or category == "power":
                    critical = "Critical Power Infrastructure"

                elif item_type == "military" or category == "military":
                    critical = "Military Installation"

                elif item_type == "refinery":
                    critical = "Critical Industrial Infrastructure"

                if item_type in {
                    "refinery",
                    "factory",
                    "works",
                    "industrial",
                } or category == "industrial":
                    facility_category = (
                        critical
                        or "Industrial Facility"
                    )

                elif item_type in {
                    "warehouse",
                }:
                    facility_category = "Storage Facility"

                elif category == "man_made":
                    facility_category = "Man-Made Facility"

                elif category == "power":
                    facility_category = (
                        critical
                        or "Power Facility"
                    )

                elif category == "military":
                    facility_category = (
                        critical
                        or "Military Installation"
                    )

                else:
                    facility_category = "OSM Facility"

                facilities.append(
                    {
                        "id": (
                            f"osm-{item.get('osm_type', 'unknown')}-"
                            f"{item.get('osm_id', 'unknown')}"
                        ),
                        "osm_type": item.get("osm_type"),
                        "osm_id": item.get("osm_id"),
                        "name": name,
                        "display_name": name,
                        "distance_km": round(distance, 2),
                        "latitude": round(item_lat, 6),
                        "longitude": round(item_lon, 6),
                        "source": "OpenStreetMap",
                        "category": facility_category,
                        "_critical": critical is not None,
                    }
                )


        except requests.Timeout:
            print("[OSM-NOMINATIM] search FAILED: timeout")

        except requests.RequestException as exc:
            print(
                "[OSM-NOMINATIM] search FAILED: "
                f"{type(exc).__name__}: {exc}"
            )

        except Exception as exc:
            print(
                "[OSM-NOMINATIM] search FAILED: "
                f"{type(exc).__name__}: {exc}"
            )

        # Reverse-geocode nearby sample points to discover named OSM
        # features that Nominatim text search can miss.
        grid_points = (
            (lat + 0.003, lon + 0.003),
            (lat - 0.003, lon + 0.003),
            (lat + 0.003, lon - 0.003),
            (lat - 0.003, lon - 0.003),
            (lat, lon + 0.005),
            (lat, lon - 0.005),
        )

        existing_ids = {
            str(item.get("id"))
            for item in facilities
            if isinstance(item, dict)
        }

        for sample_lat, sample_lon in grid_points:
            try:
                response = requests.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={
                        "lat": sample_lat,
                        "lon": sample_lon,
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "namedetails": 1,
                        "zoom": 18,
                    },
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                    },
                    timeout=NOMINATIM_TIMEOUT,
                )

                if response.status_code != 200:
                    continue

                item = response.json()
                if not isinstance(item, dict):
                    continue

                # Prefer an actual OSM name from structured name fields.
                # Internal classification labels must never become
                # real-world facility names.

                name = str(
                    item.get("name") or ""
                ).strip()

                if not name:
                    namedetails = item.get(
                        "namedetails"
                    ) or {}

                    if isinstance(
                        namedetails,
                        dict,
                    ):
                        name = str(
                            namedetails.get("name")
                            or namedetails.get("name:en")
                            or ""
                        ).strip()

                internal_category_names = {
                    "critical power infrastructure",
                    "critical industrial infrastructure",
                    "military installation",
                    "nuclear facility",
                    "industrial facility",
                    "power facility",
                    "storage facility",
                    "mining facility",
                    "fuel facility",
                    "utility facility",
                    "osm facility",
                    "man-made facility",
                    "industrial area",
                }

                if (
                    name.lower()
                    in internal_category_names
                ):
                    name = ""

                # Never use internal classification labels as OSM names.
                if (
                    name
                    and name.lower()
                    in internal_category_names
                ):
                    name = ""

                # Only use the first display_name component when it is
                # clearly a real OSM name, not an internal category label.
                if not name:
                    display_candidate = str(
                        item.get("display_name") or ""
                    ).split(",")[0].strip()

                    if (
                        display_candidate
                        and display_candidate.lower()
                        not in internal_category_names
                    ):
                        name = display_candidate

                # If Nominatim has no genuine name, keep it unnamed.
                # Do NOT manufacture a name from category/type.
                if not name:
                    name = ""

                item_lat = _safe_float(item.get("lat"))
                item_lon = _safe_float(item.get("lon"))

                if not name or item_lat is None or item_lon is None:
                    continue

                distance = _distance_km(
                    lat,
                    lon,
                    item_lat,
                    item_lon,
                )

                if distance > radius_m / 1000.0:
                    continue

                category = str(
                    item.get("category") or ""
                ).lower().strip()

                item_type = str(
                    item.get("type") or ""
                ).lower().strip()

                # Reverse-geocoding fallback must rely only on
                # structured OSM/Nominatim category/type fields.
                # Names and address text are never classification evidence.
                supported = (
                    category in {
                        "industrial",
                        "man_made",
                        "power",
                        "military",
                    }
                    or item_type in {
                        "works",
                        "factory",
                        "refinery",
                        "industrial",
                        "plant",
                        "power",
                        "generator",
                        "substation",
                        "warehouse",
                        "military",
                    }
                )

                if not supported:
                    continue

                facility_id = (
                    f"osm-{item.get('osm_type', 'unknown')}-"
                    f"{item.get('osm_id', 'unknown')}"
                )

                if facility_id in existing_ids:
                    continue

                critical = None

                # Critical classification uses only structured
                # Nominatim category/type fields.
                # Name/address text is NOT classification evidence.

                if (
                    item_type == "refinery"
                    or category == "refinery"
                ):
                    critical = (
                        "Critical Industrial Infrastructure"
                    )

                elif (
                    item_type in {
                        "power",
                        "plant",
                        "generator",
                        "substation",
                    }
                    or category == "power"
                ):
                    critical = (
                        "Critical Power Infrastructure"
                    )

                elif (
                    item_type == "military"
                    or category == "military"
                ):
                    critical = "Military Installation"
                facilities.append(
                    {
                        "id": facility_id,
                        "osm_type": item.get("osm_type"),
                        "osm_id": item.get("osm_id"),
                        "name": name,
                        "display_name": str(
                            item.get("display_name") or name
                        ),
                        "distance_km": round(distance, 2),
                        "latitude": round(item_lat, 6),
                        "longitude": round(item_lon, 6),
                        "source": "OpenStreetMap",
                        "category": (
                            critical or "Industrial Facility"
                        ),
                        "_critical": critical is not None,
                    }
                )

                existing_ids.add(facility_id)

                print(
                    "[OSM-NOMINATIM-REVERSE] Found: "
                    f"{name} | {item_type} | "
                    f"{item.get('osm_id')} | "
                    f"{distance:.2f} km"
                )

            except requests.Timeout:
                print("[OSM-NOMINATIM-REVERSE] timeout")

            except requests.RequestException as exc:
                print(
                    "[OSM-NOMINATIM-REVERSE] FAILED: "
                    f"{type(exc).__name__}: {exc}"
                )

            except Exception as exc:
                print(
                    "[OSM-NOMINATIM-REVERSE] FAILED: "
                    f"{type(exc).__name__}: {exc}"
                )

        unique = {}
        for item in facilities:
            item_id = str(item.get("id"))
            if item_id not in unique:
                unique[item_id] = item
        return list(unique.values())

    return []



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

    # Nominatim extratags are actual OSM structured tags.
    # They are evidence for classification; facility names
    # are never used as critical evidence.
    extra_tags = data.get("extratags") or {}

    if not isinstance(extra_tags, dict):
        extra_tags = {}

    osm_tags = dict(extra_tags)

    osm_tags["power"] = osm_tags.get(
        "power",
        data.get("type", ""),
    )

    osm_tags["man_made"] = osm_tags.get(
        "man_made",
        "",
    )

    osm_tags["military"] = osm_tags.get(
        "military",
        "",
    )

    critical = _critical_type(osm_tags)

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
        "category": (
            critical
            or "Industrial Facility"
        ),
        "_critical": critical is not None,
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
    # 2. NOMINATIM SUPPLEMENT
    # -------------------------------------------------------------
    # Do not skip this when Overpass already returned facilities.
    # Nominatim can contain named industrial features that Overpass
    # does not return for the same query.

    print(
        "[OSM] Running Nominatim supplement "
        "for additional named facilities..."
    )

    nominatim_facilities = _nominatim_search(
        lat,
        lon,
        radius_m,
    )

    if nominatim_facilities:

        existing_ids = {
            str(x.get("id"))
            for x in facilities
            if x.get("id") is not None
        }

        added = 0

        for item in nominatim_facilities:

            item_id = str(item.get("id"))

            if item_id in existing_ids:
                continue

            facilities.append(item)
            existing_ids.add(item_id)
            added += 1

        print(
            "[OSM-NOMINATIM] "
            f"Found {len(nominatim_facilities)} "
            f"named facility/facilities; "
            f"added {added} new"
        )

    # Last fallback: preserve the original reverse-geocoding
    # behavior for cases where the hotspot itself is mapped
    # inside an industrial feature.
    if not facilities:

        nominatim_facility = _nominatim_facility(
            lat,
            lon,
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
    # -------------------------------------------------------------
    # 4.5 DEDUPLICATE RAW OSM COMPONENTS
    # -------------------------------------------------------------
    # Reduce repeated OSM components from the same mapped facility.
    # Critical facilities and genuinely named facilities are preserved.
    # No facility names or coordinates are hardcoded.

    def _norm_osm_text(value):
        return " ".join(
            str(value or "")
            .lower()
            .strip()
            .split()
        )

    deduped_facilities = []
    exact_seen = set()
    named_groups = {}
    generic_groups = {}

    for item in facilities:

        osm_type = str(
            item.get("osm_type") or ""
        ).lower().strip()

        osm_id = str(
            item.get("osm_id") or ""
        ).strip()

        exact_key = (
            osm_type,
            osm_id,
        )

        if osm_type and osm_id:
            if exact_key in exact_seen:
                continue
            exact_seen.add(exact_key)

        category = _norm_osm_text(
            item.get("category")
        )

        name = _norm_osm_text(
            item.get("name")
        )

        lat_i = _safe_float(
            item.get("latitude")
        )

        lon_i = _safe_float(
            item.get("longitude")
        )

        critical_flag = bool(
            item.get("_critical")
        )

        # Critical facilities are never removed.
        if critical_flag:
            deduped_facilities.append(item)
            continue

        generic_names = {
            "industrial facility",
            "storage facility",
            "power facility",
            "utility facility",
            "osm facility",
            "man-made facility",
        }

        # Same named facility + same category within 250 m
        # is treated as the same physical facility.
        if (
            name
            and name not in generic_names
            and lat_i is not None
            and lon_i is not None
        ):
            group_key = (
                name,
                category,
            )

            duplicate = False

            for existing in named_groups.get(
                group_key,
                [],
            ):
                existing_lat = _safe_float(
                    existing.get("latitude")
                )
                existing_lon = _safe_float(
                    existing.get("longitude")
                )

                if (
                    existing_lat is not None
                    and existing_lon is not None
                    and (
                        (
                            (
                                (lat_i - existing_lat) ** 2
                            )
                            +
                            (
                                (
                                    (lon_i - existing_lon)
                                    * __import__("math").cos(
                                        __import__("math").radians(
                                            (lat_i + existing_lat) / 2
                                        )
                                    )
                                ) ** 2
                            )
                        ) ** 0.5
                        * 111.32
                    ) <= 0.25
                ):
                    duplicate = True
                    break

            if duplicate:
                continue

            named_groups.setdefault(
                group_key,
                [],
            ).append(item)

            deduped_facilities.append(item)
            continue

        # Generic unnamed components are grouped into
        # approximately 100 m coordinate cells.
        if (
            lat_i is not None
            and lon_i is not None
        ):
            cell_key = (
                category or "osm",
                round(lat_i, 3),
                round(lon_i, 3),
            )

            if cell_key in generic_groups:
                continue

            generic_groups[cell_key] = True

        deduped_facilities.append(item)

    facilities = deduped_facilities

    print(
        "[OSM] Deduplicated facilities: "
        f"{len(facilities)} records"
    )
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

    # Nearest industry should represent a genuinely named
    # OSM facility. Unnamed OSM industrial polygons remain
    # available in nearby context but are not promoted as
    # the nearest named industry.
    industrial_candidates = [
        x
        for x in facilities
        if x.get("category")
        in {
            "Industrial Facility",
            "Nuclear Facility",
            "Critical Industrial Infrastructure",
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
            min(
                critical_candidates,
                key=lambda x: x.get(
                    "distance_km",
                    float("inf"),
                ),
            )
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










