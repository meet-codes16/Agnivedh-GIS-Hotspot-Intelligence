from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

WORLD_COVER_CLASSES = {
    10: "TREE_COVER",
    20: "SHRUBLAND",
    30: "GRASSLAND",
    40: "CROPLAND",
    50: "BUILT_UP",
    60: "BARE_SPARSE_VEGETATION",
    70: "SNOW_ICE",
    80: "PERMANENT_WATER",
    90: "HERBACEOUS_WETLAND",
    95: "MANGROVES",
    100: "MOSS_LICHEN",
}


def worldcover_tile(latitude: float, longitude: float) -> str:
    lat0 = math.floor(float(latitude) / 3.0) * 3
    lon0 = math.floor(float(longitude) / 3.0) * 3
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    return f"{ns}{abs(lat0):02d}{ew}{abs(lon0):03d}"


def _worldcover_url(tile: str) -> str:
    return (
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
        f"v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
    )


def _open_tile(tile: str):
    """Open a COG lazily; rasterio reads only the small window needed."""
    import rasterio
    env = rasterio.Env(AWS_NO_SIGN_REQUEST="YES", GDAL_HTTP_TIMEOUT="8")
    env.__enter__()
    try:
        ds = rasterio.open(_worldcover_url(tile))
        return env, ds
    except Exception:
        env.__exit__(None, None, None)
        return None


@lru_cache(maxsize=2048)
def lookup_worldcover(latitude: float, longitude: float) -> dict:
    lat = float(latitude)
    lon = float(longitude)
    tile = worldcover_tile(lat, lon)
    opened = None
    try:
        opened = _open_tile(tile)
        if opened:
            env, ds = opened
            try:
                value = next(ds.sample([(lon, lat)]))[0]
                code = int(value)
                if code in WORLD_COVER_CLASSES:
                    return {
                        "code": code,
                        "class": WORLD_COVER_CLASSES[code],
                        "tile": tile,
                        "reference": "ESA_WorldCover_2021_v200",
                        "source": "ESA WorldCover",
                        "available": True,
                    }
            finally:
                try:
                    ds.close()
                finally:
                    env.__exit__(None, None, None)
    except Exception:
        pass
    return {
        "code": None,
        "class": None,
        "tile": tile,
        "reference": "ESA_WorldCover_2021_v200",
        "source": "ESA WorldCover",
        "available": False,
        "message": "Automatic WorldCover lookup unavailable; enter the WorldCover class/code for this validation case if known.",
    }
