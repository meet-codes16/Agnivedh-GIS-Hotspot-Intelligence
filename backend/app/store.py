"""FIRMS-backed data store with a real runtime dataset.

Prototype source of truth is the frontend mock JS files so both sides share
the same FIRMS-shaped records.

The full training source is kept under backend/data/training_source; the runtime CSV keeps API startup responsive.

    
"""

from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
import math
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
FRONTEND_DATA = ROOT / "frontend" / "src" / "data"

# FUTURE CSV hook â€” keep this path; load when the file is present.
FIRMS_CSV_PATH = DATA_DIR / "fires_runtime.csv"
HOTSPOTS_2024_CSV_PATH = DATA_DIR / "hotspots_2024.csv"

FIRMS_COLUMNS = [
    "latitude",
    "longitude",
    "brightness",
    "scan",
    "track",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "version",
    "bright_t31",
    "frp",
    "daynight",
    "type",
    "assigned_class",
    "study_area",
    "worldcover_code",
    "worldcover_class",
    "fire_source_label",
    "final_source_label",
    "final_label_confidence",
    "label_basis",
    "source_evidence",
    "source_distance_m",
]

STUDY_BOXES = {
    "satpura_melghat": (21.0, 22.8, 76.5, 78.5),
    "similipal": (21.3, 22.2, 86.0, 86.8),
    "punjab_haryana": (28.3, 32.5, 74.0, 77.5),
    "ankleshwar_dahej": (21.1, 22.0, 72.5, 73.2),
    "durgapur_asansol": (23.4, 23.8, 86.8, 87.4),
    "bharuch_dahej": (21.5, 21.9, 72.4, 72.7),
    "upper_assam": (27.2, 27.7, 95.2, 95.9),
    "jharia": (23.7, 23.9, 86.2, 86.6),
    "korba_singrauli": (22.2, 22.5, 82.5, 82.9),
}

SOURCE = "csv"


def infer_region_key(row: dict) -> str:
    if row.get("region_key"):
        return str(row["region_key"])
    area = str(row.get("study_area") or "").lower()
    mapping = (
        ("ankleshwar", "ankleshwar_dahej"),
        ("durgapur", "durgapur_asansol"),
        ("bharuch", "bharuch_dahej"),
        ("dahej chemical", "bharuch_dahej"),
        ("assam", "upper_assam"),
        ("jharia", "jharia"),
        ("korba", "korba_singrauli"),
        ("singrauli", "korba_singrauli"),
        ("punjab", "punjab_haryana"),
        ("haryana", "punjab_haryana"),
        ("similipal", "similipal"),
        ("satpura", "satpura_melghat"),
        ("melghat", "satpura_melghat"),
    )
    for needle, key in mapping:
        if needle in area:
            return key
    try:
        lat = float(row["latitude"])
        lon = float(row["longitude"])
    except (KeyError, TypeError, ValueError):
        return "ankleshwar_dahej"
    for key, (lat_min, lat_max, lon_min, lon_max) in STUDY_BOXES.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return key
    return f"grid_{math.floor(lat)}_{math.floor(lon)}"


def _coerce_hotspot(row: dict, index: int) -> dict:
    item = {col: row.get(col, "") for col in FIRMS_COLUMNS}
    # Keep the original 2024 dataset row identifier so F24-* IDs remain stable
    # after date/day-night filtering and sorting.
    try:
        item["fire_row_id"] = int(float(row.get("fire_row_id") or index))
    except (TypeError, ValueError):
        item["fire_row_id"] = int(index)
    for key in ("latitude", "longitude", "brightness", "scan", "track", "bright_t31", "frp"):
        try:
            item[key] = float(item[key])
        except (TypeError, ValueError):
            item[key] = 0.0
    # FIRMS confidence is commonly categorical (l/n/h). Preserve it so the
    # trained feature mapping can distinguish low/nominal/high confidence.
    raw_confidence = str(item.get("confidence") or "").strip().lower()
    if raw_confidence in {"l", "n", "h"}:
        item["confidence"] = raw_confidence
    else:
        try:
            item["confidence"] = float(raw_confidence)
        except (TypeError, ValueError):
            item["confidence"] = "n"
    try:
        item["type"] = int(float(item["type"] or 0))
    except (TypeError, ValueError):
        item["type"] = 0
    item["acq_time"] = str(item.get("acq_time") or "0000").zfill(4)
    # 2024 hotspot CSV has no study_area/assigned_class columns. Never invent a
    # named region or source label; use a deterministic 1-degree spatial grid.
    if not str(item.get("study_area") or "").strip():
        try:
            item["study_area"] = f"GRID {math.floor(float(item['latitude']))}_{math.floor(float(item['longitude']))}"
        except (TypeError, ValueError):
            item["study_area"] = "GRID UNKNOWN"
    item["id"] = row.get("id") or f"FRM-{index:04d}"
    # Preserve context columns used by the trained model and evidence layer.
    try:
        item["worldcover_code"] = int(float(item.get("worldcover_code") or 0))
    except (TypeError, ValueError):
        item["worldcover_code"] = 0
    item["worldcover_class"] = str(item.get("worldcover_class") or "")
    item["fire_source_label"] = str(item.get("fire_source_label") or "")
    item["final_source_label"] = str(item.get("final_source_label") or "")
    item["final_label_confidence"] = str(item.get("final_label_confidence") or "")
    item["label_basis"] = str(item.get("label_basis") or "")
    item["source_evidence"] = str(item.get("source_evidence") or "")
    try:
        item["source_distance_m"] = float(item.get("source_distance_m") or 0)
    except (TypeError, ValueError):
        item["source_distance_m"] = 0.0
    item["region_key"] = infer_region_key({**item, "region_key": row.get("region_key")})
    return item


def _load_from_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [_coerce_hotspot(row, index) for index, row in enumerate(reader, start=1)]


def _js_object_to_json(text: str) -> str:
    quoted = re.sub(r"([\{\[,]\s*)([A-Za-z_][\w]*)\s*:", r'\1"\2":', text)
    return re.sub(r",\s*([}\]])", r"\1", quoted)


def _extract_js_value(path: Path, marker: str, closer: str) -> object:
    text = path.read_text(encoding="utf-8")
    start = text.index(marker) + len(marker)
    blob = text[start:]
    end = blob.index(closer)
    payload = blob[:end] + closer[0]
    return json.loads(_js_object_to_json(payload))


def _load_hotspots() -> list[dict]:
    global SOURCE
    if FIRMS_CSV_PATH.exists():
        SOURCE = "csv"
        return _load_from_csv(FIRMS_CSV_PATH)
    # The runtime API does not fall back to mock/generated hotspot records.
    SOURCE = "internal_2024_firms_csv" if HOTSPOTS_2024_CSV_PATH.exists() else "unavailable"
    return []


def _load_baseline() -> dict:
    profiles_path = DATA_DIR.parent / "models" / "baseline_profiles.json"
    if profiles_path.exists():
        return json.loads(profiles_path.read_text(encoding="utf-8")).get("profiles", {})
    return {}


def _load_forecast() -> dict:
    """Load optional forecast metadata without depending on mock frontend data."""
    bundle = DATA_DIR / "mock_bundle.json"
    if bundle.exists():
        try:
            return json.loads(bundle.read_text(encoding="utf-8")).get("forecast", {})
        except (OSError, json.JSONDecodeError, TypeError):
            return {}
    # No mock forecast fallback. Runtime hotspot intelligence uses real 2024 FIRMS data.
    return {}


HOTSPOTS: list[dict] = _load_hotspots()
BASELINE: dict = _load_baseline()
FORECAST: dict = _load_forecast()
_BY_ID = {item["id"]: item for item in HOTSPOTS}


def _load_2024_hotspots_cached() -> tuple[dict, ...]:
    if not HOTSPOTS_2024_CSV_PATH.exists():
        return tuple()

    rows: list[dict] = []

    for chunk in pd.read_csv(
        HOTSPOTS_2024_CSV_PATH,
        dtype=str,
        keep_default_na=False,
        chunksize=50000,
    ):
        for index, row in chunk.iterrows():
            rows.append(_coerce_hotspot(row.to_dict(), int(index) + 1))

    return tuple(rows)


@lru_cache(maxsize=32)
def _csv_fire_row_index_for_date(acq_date: str) -> dict[tuple, str]:
    """Return stable source-row IDs for one 2024 date.

    Parquet exports can be physically reordered and some exports omit
    ``fire_row_id``.  The CSV is the authoritative supplied dataset, so use
    its unique source-row ID to reconcile filtered parquet results.
    """
    if not HOTSPOTS_2024_CSV_PATH.exists():
        return {}

    index: dict[tuple, str] = {}
    usecols = [
        "fire_row_id", "latitude", "longitude", "acq_date", "acq_time",
        "frp", "brightness", "satellite", "instrument",
    ]
    for chunk in pd.read_csv(
        HOTSPOTS_2024_CSV_PATH,
        dtype=str,
        keep_default_na=False,
        usecols=lambda c: c in usecols,
        chunksize=50000,
    ):
        if "acq_date" not in chunk.columns:
            continue
        chunk = chunk[chunk["acq_date"].astype(str).eq(str(acq_date))]
        for row in chunk.to_dict("records"):
            rid = str(row.get("fire_row_id") or "").strip()
            if not rid:
                continue
            key = (
                str(row.get("acq_date") or ""),
                str(row.get("acq_time") or "").zfill(4),
                round(float(row.get("latitude") or 0), 6),
                round(float(row.get("longitude") or 0), 6),
                round(float(row.get("frp") or 0), 4),
                round(float(row.get("brightness") or 0), 4),
                str(row.get("satellite") or ""),
                str(row.get("instrument") or ""),
            )
            index[key] = rid
    return index


def _attach_stable_ids(rows: list[dict], acq_date: str | None) -> list[dict]:
    if not rows or not acq_date:
        return rows

    source_index = _csv_fire_row_index_for_date(str(acq_date))
    for row in rows:
        key = (
            str(row.get("acq_date") or ""),
            str(row.get("acq_time") or "").zfill(4),
            round(float(row.get("latitude") or 0), 6),
            round(float(row.get("longitude") or 0), 6),
            round(float(row.get("frp") or 0), 4),
            round(float(row.get("brightness") or 0), 4),
            str(row.get("satellite") or ""),
            str(row.get("instrument") or ""),
        )
        existing_id = row.get("fire_row_id")
        if existing_id is not None and str(existing_id).strip():
            try:
                rid = int(float(existing_id))
                if rid > 0:
                    row["fire_row_id"] = rid
                    row["id"] = f"F24-{rid}"
                    continue
            except (TypeError, ValueError):
                pass

        rid = source_index.get(key)
        if rid:
            row["fire_row_id"] = int(rid)
            row["id"] = f"F24-{rid}"
        else:
            # Last-resort deterministic ID; this should only occur if the
            # parquet and supplied CSV contain genuinely different rows.
            row["id"] = (
                f"F24-{str(row.get('acq_date') or '00000000').replace('-', '')}-"
                f"{str(row.get('acq_time') or '0000').zfill(4)}-"
                f"{abs(hash((key))) % 100000000:08d}"
            )
    return rows



def batch_same_pass_context(rows: list[dict]) -> dict[str, dict]:
    """Fast same-pass spatial cluster context for one loaded date.

    This uses the currently loaded satellite-pass slice only. It is designed
    for map rendering and avoids scanning the full 552k-row history once per
    marker.
    """
    bins: dict[tuple[int, int, str], int] = {}
    row_keys: dict[str, tuple[int, int, str]] = {}
    for row in rows:
        try:
            lat = float(row.get("latitude") or 0)
            lon = float(row.get("longitude") or 0)
        except (TypeError, ValueError):
            continue
        hour = str(row.get("acq_time") or "0000").zfill(4)[:2]
        key = (math.floor(lat / 0.05), math.floor(lon / 0.05), hour)
        bins[key] = bins.get(key, 0) + 1
        row_keys[str(row.get("id") or "")] = key

    result: dict[str, dict] = {}
    for row in rows:
        rid = str(row.get("id") or "")
        key = row_keys.get(rid)
        if not key:
            result[rid] = {"same_pass_count": 0, "nearby_count_24h": 0, "nearby_count_72h": 0, "distinct_dates_72h": 0}
            continue
        c_lat, c_lon, hour = key
        total = 0
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                total += bins.get((c_lat + di, c_lon + dj, hour), 0)
        result[rid] = {
            "same_pass_count": max(0, total - 1),
            "nearby_count_24h": 0,
            "nearby_count_72h": 0,
            "distinct_dates_72h": 0,
        }
    return result

def query_hotspots_2024(year: int = 2024, acq_date: str | None = None, daynight: str | None = None) -> list[dict]:
    """Return actual 2024 FIRMS rows for the requested date/D-N filter."""
    if int(year) != 2024:
        return []

    wanted_daynight = (daynight or "").strip().upper()
    if wanted_daynight not in {"", "D", "N"}:
        raise ValueError("daynight must be D, N, or omitted")

    parquet_path = DATA_DIR / "hotspots_2024.parquet"

    reader = None
    if parquet_path.exists():
        filters = []
        if acq_date:
            filters.append(("acq_date", "==", acq_date))
        if wanted_daynight:
            filters.append(("daynight", "==", wanted_daynight))
        try:
            reader = pd.read_parquet(
                parquet_path,
                filters=[filters] if filters else None,
                engine="pyarrow",
            )
        except (ImportError, ValueError, ModuleNotFoundError):
            reader = None

    rows: list[dict] = []

    if reader is not None:
        for index, row in reader.iterrows():
            copied = _coerce_hotspot(row.to_dict(), int(index) + 1)
            copied["id"] = f"F24-{int(copied.get("fire_row_id") or (int(index) + 1))}"
            rows.append(copied)
    elif HOTSPOTS_2024_CSV_PATH.exists():
        # CSV fallback keeps the app runnable even when optional parquet support
        # is unavailable. Chunking avoids loading the complete 552k-row file.
        offset = 0
        for chunk in pd.read_csv(
            HOTSPOTS_2024_CSV_PATH,
            dtype=str,
            keep_default_na=False,
            chunksize=50000,
        ):
            chunk_dates = chunk["acq_date"].astype(str) if "acq_date" in chunk.columns else None
            mask = pd.Series(True, index=chunk.index)
            if acq_date and chunk_dates is not None:
                mask &= chunk_dates.eq(str(acq_date))
            if wanted_daynight and "daynight" in chunk.columns:
                mask &= chunk["daynight"].astype(str).str.upper().eq(wanted_daynight)
            selected_chunk = chunk.loc[mask]
            for local_index, row in selected_chunk.iterrows():
                original_index = offset + int(local_index) + 1
                copied = _coerce_hotspot(row.to_dict(), original_index)
                copied["id"] = f"F24-{int(copied.get("fire_row_id") or original_index)}"
                rows.append(copied)
            offset += len(chunk)
    else:
        return []

    rows = _attach_stable_ids(rows, acq_date)

    rows.sort(
        key=lambda r: (
            str(r.get("acq_date") or ""),
            int(float(r.get("acq_time") or 0)),
            float(r.get("latitude") or 0),
            float(r.get("longitude") or 0),
            str(r.get("id") or ""),
        )
    )

    return rows

@lru_cache(maxsize=1)
def _event_history_frame():
    """Cached compact 2024 event table loaded directly from Parquet/CSV."""
    parquet_path = DATA_DIR / "hotspots_2024.parquet"
    columns = ["latitude", "longitude", "acq_date", "acq_time", "frp", "brightness", "bright_t31"]
    if parquet_path.exists():
        try:
            frame = pd.read_parquet(parquet_path, columns=columns, engine="pyarrow")
        except (ImportError, ValueError):
            frame = pd.read_csv(HOTSPOTS_2024_CSV_PATH, usecols=columns, low_memory=False) if HOTSPOTS_2024_CSV_PATH.exists() else pd.DataFrame()
    elif HOTSPOTS_2024_CSV_PATH.exists():
        frame = pd.read_csv(HOTSPOTS_2024_CSV_PATH, usecols=columns, low_memory=False)
    else:
        return pd.DataFrame(columns=["latitude", "longitude", "timestamp", "acq_date"])
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    raw_time = pd.to_numeric(frame["acq_time"], errors="coerce").fillna(0).astype(int)
    frame["frp"] = pd.to_numeric(frame.get("frp"), errors="coerce").fillna(0.0)
    frame["brightness"] = pd.to_numeric(frame.get("brightness"), errors="coerce").fillna(0.0)
    frame["bright_t31"] = pd.to_numeric(frame.get("bright_t31"), errors="coerce").fillna(0.0)
    frame["timestamp"] = pd.to_datetime(frame["acq_date"].astype(str) + " " + raw_time.astype(str).str.zfill(4), format="%Y-%m-%d %H%M", errors="coerce")
    frame["acq_date"] = frame["acq_date"].astype(str)
    # 0.05 degree cells are used only as a candidate index; final distances are
    # still calculated with the haversine formula, so the cell is not an accuracy claim.
    frame["cell_lat"] = np.floor(frame["latitude"].to_numpy(dtype=float) / 0.05).astype(np.int32)
    frame["cell_lon"] = np.floor(frame["longitude"].to_numpy(dtype=float) / 0.05).astype(np.int32)
    return frame.dropna(subset=["latitude", "longitude", "timestamp"]).reset_index(drop=True)


def _load_event_window(
    ts: pd.Timestamp,
    start_ts: pd.Timestamp | None = None,
    end_ts: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Load only the small temporal slice required for selected-hotspot context.

    Parquet predicate pushdown is used whenever possible. This intentionally
    avoids materialising the complete 2024 FIRMS dataset into pandas.
    """
    parquet_path = DATA_DIR / "hotspots_2024.parquet"
    columns = [
        "latitude",
        "longitude",
        "acq_date",
        "acq_time",
        "frp",
        "brightness",
        "bright_t31",
    ]

    start_ts = start_ts if start_ts is not None else ts
    end_ts = end_ts if end_ts is not None else ts

    frames: list[pd.DataFrame] = []

    if parquet_path.exists():
        try:
            start_date = start_ts.strftime("%Y-%m-%d")
            end_date = end_ts.strftime("%Y-%m-%d")

            filters = [
                ("acq_date", ">=", start_date),
                ("acq_date", "<=", end_date),
            ]

            frame = pd.read_parquet(
                parquet_path,
                columns=columns,
                filters=[filters],
                engine="pyarrow",
            )

            if not frame.empty:
                raw_time = pd.to_numeric(
                    frame["acq_time"],
                    errors="coerce",
                ).fillna(0).astype(int)

                frame["timestamp"] = pd.to_datetime(
                    frame["acq_date"].astype(str)
                    + " "
                    + raw_time.astype(str).str.zfill(4),
                    format="%Y-%m-%d %H%M",
                    errors="coerce",
                )

                frame = frame[
                    frame["timestamp"].notna()
                    & frame["timestamp"].between(
                        start_ts,
                        end_ts,
                        inclusive="both",
                    )
                ].copy()

                frames.append(frame)

        except (
            ImportError,
            ModuleNotFoundError,
            ValueError,
            OSError,
            KeyError,
        ):
            frames = []

    # CSV is a fallback only when Parquet is unavailable/unreadable.
    if not frames and HOTSPOTS_2024_CSV_PATH.exists():
        try:
            for chunk in pd.read_csv(
                HOTSPOTS_2024_CSV_PATH,
                usecols=columns,
                low_memory=False,
                chunksize=50000,
            ):
                raw_time = pd.to_numeric(
                    chunk["acq_time"],
                    errors="coerce",
                ).fillna(0).astype(int)

                chunk["timestamp"] = pd.to_datetime(
                    chunk["acq_date"].astype(str)
                    + " "
                    + raw_time.astype(str).str.zfill(4),
                    format="%Y-%m-%d %H%M",
                    errors="coerce",
                )

                mask = (
                    chunk["timestamp"].notna()
                    & chunk["timestamp"].between(
                        start_ts,
                        end_ts,
                        inclusive="both",
                    )
                )

                if mask.any():
                    frames.append(chunk.loc[mask].copy())

                del chunk

        except (
            ImportError,
            ModuleNotFoundError,
            ValueError,
            OSError,
            KeyError,
        ):
            frames = []

    if not frames:
        return pd.DataFrame(
            columns=[
                "latitude",
                "longitude",
                "acq_date",
                "acq_time",
                "frp",
                "brightness",
                "bright_t31",
                "timestamp",
            ]
        )

    frame = pd.concat(frames, ignore_index=True)

    frame["latitude"] = pd.to_numeric(
        frame["latitude"],
        errors="coerce",
    )
    frame["longitude"] = pd.to_numeric(
        frame["longitude"],
        errors="coerce",
    )
    frame["frp"] = pd.to_numeric(
        frame["frp"],
        errors="coerce",
    ).fillna(0.0)
    frame["brightness"] = pd.to_numeric(
        frame["brightness"],
        errors="coerce",
    ).fillna(0.0)
    frame["bright_t31"] = pd.to_numeric(
        frame["bright_t31"],
        errors="coerce",
    ).fillna(0.0)
    frame["acq_date"] = frame["acq_date"].astype(str)

    return frame.dropna(
        subset=["latitude", "longitude", "timestamp"]
    ).reset_index(drop=True)


def recent_event_context(
    hotspot: dict,
    radius_km: float = 5.0,
    hours: int = 72,
) -> dict:
    """Return leakage-safe prior-event and same-pass context.

    Only the requested temporal window is read from the 2024 dataset.
    No full-dataset pandas frame is materialised.
    """
    empty = {
        "nearby_count_24h": 0,
        "nearby_count_72h": 0,
        "distinct_dates_72h": 0,
        "same_pass_count": 0,
        "nearest_distance_km": None,
    }

    try:
        lat = float(hotspot.get("latitude") or 0)
        lon = float(hotspot.get("longitude") or 0)

        ts = pd.to_datetime(
            f"{hotspot.get('acq_date', '')} "
            f"{str(hotspot.get('acq_time') or '0000').zfill(4)}",
            format="%Y-%m-%d %H%M",
            errors="coerce",
        )

        if pd.isna(ts):
            return empty

    except Exception:
        return empty

    start = ts - pd.Timedelta(hours=hours)

    frame = _load_event_window(
        ts,
        start_ts=start,
        end_ts=ts,
    )

    if frame.empty:
        return empty

    lat1 = math.radians(lat)
    lon1 = math.radians(lon)

    # Same satellite-pass/time spatial cluster.
    same_pass = frame[
        frame["timestamp"] == ts
    ]

    same_pass_count = 0

    if not same_pass.empty:
        lat2 = (
            same_pass["latitude"].to_numpy(dtype=float)
            * math.pi / 180.0
        )
        lon2 = (
            same_pass["longitude"].to_numpy(dtype=float)
            * math.pi / 180.0
        )

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            np.sin(dlat / 2.0) ** 2
            + math.cos(lat1)
            * np.cos(lat2)
            * np.sin(dlon / 2.0) ** 2
        )

        distances = (
            6371.0088
            * 2.0
            * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
        )

        same_pass_count = int(
            (
                (distances <= radius_km)
                & (distances > 0.001)
            ).sum()
        )

    # Strictly prior observations only.
    h = frame[
        (frame["timestamp"] < ts)
        & (frame["timestamp"] >= start)
    ].copy()

    if h.empty:
        return {
            **empty,
            "same_pass_count": same_pass_count,
        }

    lat2 = (
        h["latitude"].to_numpy(dtype=float)
        * math.pi / 180.0
    )
    lon2 = (
        h["longitude"].to_numpy(dtype=float)
        * math.pi / 180.0
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2.0) ** 2
        + math.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

    distances = (
        6371.0088
        * 2.0
        * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    )

    h["distance_km"] = distances
    h = h[h["distance_km"] <= radius_km]

    if h.empty:
        return {
            **empty,
            "same_pass_count": same_pass_count,
        }

    recent_24 = h[
        h["timestamp"] >= ts - pd.Timedelta(hours=24)
    ]

    return {
        "nearby_count_24h": int(len(recent_24)),
        "nearby_count_72h": int(len(h)),
        "distinct_dates_72h": int(h["acq_date"].nunique()),
        "same_pass_count": same_pass_count,
        "nearest_distance_km": round(
            float(h["distance_km"].min()),
            3,
        ),
    }


def _event_grid_index():
    """Compact spatial-temporal index for fast batch event association.

    The original implementation inserted every 2024 row into a Python dict in
    a loop. With 552k observations that made the first historical-fire lookup
    unnecessarily slow. Build the same hourly cell counts with pandas vector
    operations instead; the lookup semantics remain unchanged.
    """
    frame = _event_history_frame()
    if frame.empty:
        return {}

    indexed = frame[["latitude", "longitude", "timestamp"]].copy()
    indexed["cell_lat"] = np.floor(indexed["latitude"].to_numpy(dtype=float) / 0.05).astype(np.int32)
    indexed["cell_lon"] = np.floor(indexed["longitude"].to_numpy(dtype=float) / 0.05).astype(np.int32)
    indexed["hour"] = indexed["timestamp"].dt.floor("h")

    grouped = indexed.groupby(["cell_lat", "cell_lon", "hour"], sort=False).size()
    return {(
        int(lat_cell),
        int(lon_cell),
        hour,
    ): int(count) for (lat_cell, lon_cell, hour), count in grouped.items()}


def recent_event_context_fast(hotspot: dict) -> dict:
    """Approximate prior-event context for batch 2024 inference."""
    try:
        lat = float(hotspot.get("latitude") or 0)
        lon = float(hotspot.get("longitude") or 0)
        date = str(hotspot.get("acq_date") or "")
        hh = int(str(hotspot.get("acq_time") or "0000").zfill(4)[:2])
        ts = pd.Timestamp(date) + pd.Timedelta(hours=hh)
    except Exception:
        return {"nearby_count_24h": 0, "nearby_count_72h": 0, "distinct_dates_72h": 0, "nearest_distance_km": None}

    bins = _event_grid_index()
    c_lat = math.floor(lat / 0.05)
    c_lon = math.floor(lon / 0.05)
    total24 = 0
    total72 = 0
    same_pass = 0
    active_days = set()
    # Same-hour spatial cluster is available at the satellite pass and does not
    # use observations from later hours/days.
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            same_pass += bins.get((c_lat + di, c_lon + dj, ts.floor("h")), 0)
    same_pass = max(0, same_pass - 1)

    for offset in range(1, 73):
        bucket = ts - pd.Timedelta(hours=offset)
        hour_total = 0
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                hour_total += bins.get((c_lat + di, c_lon + dj, bucket.floor("h")), 0)
        if hour_total:
            total72 += hour_total
            active_days.add(bucket.date().isoformat())
            if offset <= 24:
                total24 += hour_total
    return {
        "nearby_count_24h": int(total24),
        "nearby_count_72h": int(total72),
        "distinct_dates_72h": int(len(active_days)),
        "same_pass_count": int(same_pass),
        "nearest_distance_km": None,
    }

def persistent_source_history(
    hotspot: dict,
    radius_km: float = 5.0,
) -> dict:
    """Return leakage-safe 2024 thermal-source history around one detection.

    Only observations up to the selected hotspot timestamp are considered.
    The loader first restricts the Parquet read by date and then applies the
    exact spatial Haversine test.
    """
    try:
        lat = float(hotspot.get("latitude") or 0)
        lon = float(hotspot.get("longitude") or 0)

        ts = pd.to_datetime(
            f"{hotspot.get('acq_date', '')} "
            f"{str(hotspot.get('acq_time') or '0000').zfill(4)}",
            format="%Y-%m-%d %H%M",
            errors="coerce",
        )

        if pd.isna(ts):
            raise ValueError

    except Exception:
        return {
            "status": "UNAVAILABLE",
            "reason": "Invalid hotspot timestamp or coordinates.",
            "timeline": [],
        }

    # Date-bounded read. This avoids materialising the entire 2024 dataset.
    frame = _load_event_window(
        ts,
        start_ts=pd.Timestamp("2024-01-01"),
        end_ts=ts,
    )

    if frame.empty:
        return {
            "status": "TRANSIENT",
            "detection_count": 1,
            "active_days": 1,
            "first_seen": str(hotspot.get("acq_date")),
            "last_seen": str(hotspot.get("acq_date")),
            "duration_days": 0,
            "timeline": [
                {
                    "date": str(hotspot.get("acq_date")),
                    "count": 1,
                    "max_frp": float(hotspot.get("frp") or 0),
                }
            ],
        }

    # Candidate cells first; exact Haversine distance follows.
    c_lat = math.floor(lat / 0.05)
    c_lon = math.floor(lon / 0.05)

    frame["cell_lat"] = np.floor(
        frame["latitude"].to_numpy(dtype=float) / 0.05
    ).astype(np.int32)

    frame["cell_lon"] = np.floor(
        frame["longitude"].to_numpy(dtype=float) / 0.05
    ).astype(np.int32)

    candidates = frame[
        frame["cell_lat"].between(c_lat - 1, c_lat + 1)
        & frame["cell_lon"].between(c_lon - 1, c_lon + 1)
        & (frame["timestamp"] <= ts)
    ].copy()

    if candidates.empty:
        return {
            "status": "TRANSIENT",
            "detection_count": 1,
            "active_days": 1,
            "first_seen": str(hotspot.get("acq_date")),
            "last_seen": str(hotspot.get("acq_date")),
            "duration_days": 0,
            "timeline": [
                {
                    "date": str(hotspot.get("acq_date")),
                    "count": 1,
                    "max_frp": float(hotspot.get("frp") or 0),
                }
            ],
        }

    lat1 = math.radians(lat)
    lon1 = math.radians(lon)

    lat2 = (
        candidates["latitude"].to_numpy(dtype=float)
        * math.pi / 180.0
    )
    lon2 = (
        candidates["longitude"].to_numpy(dtype=float)
        * math.pi / 180.0
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2.0) ** 2
        + math.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

    distances = (
        6371.0088
        * 2.0
        * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    )

    h = candidates[
        distances <= radius_km
    ].copy()

    if h.empty:
        h = pd.DataFrame(
            [{
                "acq_date": str(hotspot.get("acq_date")),
                "timestamp": ts,
                "frp": float(hotspot.get("frp") or 0),
            }]
        )

    active_dates = sorted(
        set(h["acq_date"].astype(str))
    )

    first_seen = (
        active_dates[0]
        if active_dates
        else str(hotspot.get("acq_date"))
    )

    last_seen = (
        active_dates[-1]
        if active_dates
        else str(hotspot.get("acq_date"))
    )

    duration_days = max(
        0,
        (
            pd.Timestamp(last_seen)
            - pd.Timestamp(first_seen)
        ).days,
    )

    detection_count = int(len(h))
    active_days = int(len(active_dates))

    timeline_df = h.groupby(
        "acq_date",
        as_index=False,
    ).agg(
        count=("acq_date", "size"),
        max_frp=("frp", "max"),
    )

    timeline_df = timeline_df.sort_values("acq_date")

    timeline = [
        {
            "date": str(r.acq_date),
            "count": int(r.count),
            "max_frp": round(float(r.max_frp), 2),
        }
        for r in timeline_df.tail(18).itertuples(index=False)
    ]

    current_frp = float(
        hotspot.get("frp") or 0
    )

    historical_frp = h.loc[
        h["timestamp"] < ts,
        "frp",
    ]

    median_frp = (
        float(historical_frp.median())
        if not historical_frp.empty
        else current_frp
    )

    spike_ratio = (
        current_frp / median_frp
        if median_frp > 0
        else (
            2.0
            if current_frp > 0
            else 1.0
        )
    )

    if active_days >= 5 and duration_days >= 14:
        behaviour = "PERSISTENT THERMAL SOURCE"
    elif active_days >= 3 and duration_days >= 7:
        behaviour = "RECURRENT THERMAL ACTIVITY"
    else:
        behaviour = "TRANSIENT ACTIVITY"

    abnormal = bool(
        behaviour != "TRANSIENT ACTIVITY"
        and spike_ratio >= 2.0
    )

    return {
        "status": "AVAILABLE",
        "behaviour": behaviour,
        "abnormal_persistence": abnormal,
        "detection_count": detection_count,
        "active_days": active_days,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "duration_days": duration_days,
        "radius_km": radius_km,
        "median_frp": round(median_frp, 2),
        "current_frp": round(current_frp, 2),
        "frp_spike_ratio": round(spike_ratio, 2),
        "timeline": timeline,
        "interpretation": (
            "Repeated thermal detections at a stable location; this does not mean one continuous fire."
            if behaviour != "TRANSIENT ACTIVITY"
            else
            "Few nearby detections in 2024; persistence is not established."
        ),
    }


def historical_2024_baselines(acq_date: str, daynight: str | None = None) -> dict[str, dict]:
    """Build leakage-safe 2024 baselines without loading the full dataset.

    Only observations strictly before the selected date and belonging to the
    selected calendar month/day-night are read. Parquet filtering is pushed
    down where possible; CSV is used only as a fallback.
    """
    try:
        selected_ts = pd.Timestamp(acq_date)
        month = int(selected_ts.month)
    except (TypeError, ValueError):
        return {}

    wanted = (daynight or "").strip().upper()

    # First day of a month has no same-month historical observations.
    if selected_ts.day <= 1:
        return {}

    columns = [
        "latitude",
        "longitude",
        "frp",
        "acq_date",
        "acq_time",
        "daynight",
        "region_key",
        "brightness",
        "scan",
        "track",
    ]

    history: list[dict] = []
    parquet_path = DATA_DIR / "hotspots_2024.parquet"

    # --------------------------------------------------------
    # PARQUET PATH
    # --------------------------------------------------------
    if parquet_path.exists():
        try:
            # Read only the selected month/date range.
            # This avoids loading the complete 552k-row dataset.
            filters = [
                ("acq_date", "<", acq_date),
            ]

            if wanted in {"D", "N"}:
                filters.append(("daynight", "==", wanted))

            frame = pd.read_parquet(
                parquet_path,
                columns=columns,
                filters=[filters],
                engine="pyarrow",
            )

            if not frame.empty:
                dates = pd.to_datetime(
                    frame["acq_date"],
                    errors="coerce",
                )

                frame = frame[
                    dates.notna()
                    & dates.lt(selected_ts)
                    & dates.dt.month.eq(month)
                ]

                if wanted in {"D", "N"} and "daynight" in frame.columns:
                    frame = frame[
                        frame["daynight"]
                        .astype(str)
                        .str.upper()
                        .eq(wanted)
                    ]

                if not frame.empty:
                    history = frame.to_dict("records")

                del frame

        except (
            ImportError,
            ModuleNotFoundError,
            ValueError,
            OSError,
            KeyError,
        ):
            history = []

    # --------------------------------------------------------
    # CSV FALLBACK
    # --------------------------------------------------------
    # Only reached if Parquet could not be used.
    if not history and HOTSPOTS_2024_CSV_PATH.exists():
        try:
            for chunk in pd.read_csv(
                HOTSPOTS_2024_CSV_PATH,
                dtype=str,
                keep_default_na=False,
                usecols=lambda c: c in columns,
                chunksize=50000,
            ):
                dates = pd.to_datetime(
                    chunk.get("acq_date"),
                    errors="coerce",
                )

                mask = (
                    dates.notna()
                    & dates.lt(selected_ts)
                    & dates.dt.month.eq(month)
                )

                if wanted in {"D", "N"} and "daynight" in chunk.columns:
                    mask &= (
                        chunk["daynight"]
                        .astype(str)
                        .str.upper()
                        .eq(wanted)
                    )

                if mask.any():
                    history.extend(
                        chunk.loc[mask].to_dict("records")
                    )

                del chunk

        except (
            ImportError,
            ModuleNotFoundError,
            ValueError,
            OSError,
            KeyError,
        ):
            history = []

    if not history:
        return {}

    # --------------------------------------------------------
    # GROUP BASELINE
    # --------------------------------------------------------
    grouped: dict[str, list[dict]] = {}

    for item in history:
        key = item.get("region_key") or infer_region_key(item)
        grouped.setdefault(key, []).append(item)

    from app.engine import historical_baseline, aggregate_region_baseline

    result: dict[str, dict] = {}

    for key, rows in grouped.items():
        if len(rows) >= 3:
            result[key] = aggregate_region_baseline(
                rows,
                historical_baseline(rows[0]),
            )

            result[key]["region_key"] = key
            result[key]["region"] = (
                f"GRID {key.replace('grid_', '').replace('_', ' / ')}"
            )
            result[key]["notes"] = (
                f"2024 historical baseline: {len(rows)} observations "
                f"before {acq_date}; month {month}; "
                f"no future/test observations used."
            )
            result[key]["source"] = "2024 historical observations"

        else:
            sample = {
                "latitude": 0,
                "longitude": 0,
                "acq_date": acq_date,
            }

            if key.startswith("grid_"):
                try:
                    a, b = key[5:].split("_")[:2]
                    sample["latitude"] = float(a) + 0.5
                    sample["longitude"] = float(b) + 0.5
                except Exception:
                    pass

            result[key] = historical_baseline(sample)

    return result

def list_hotspots() -> list[dict]:
    """Return FIRMS-shaped hotspot objects.

    If backend/data/fires_2024.csv exists it is used. Column names stay unchanged.
    """
    return HOTSPOTS


def get_hotspot(hotspot_id: str) -> dict | None:
    item = _BY_ID.get(hotspot_id)
    if item:
        return item

    match = re.fullmatch(r"F24-(\d+)", str(hotspot_id or ""))
    if not match:
        return None
    fire_row_id = int(match.group(1))
    if fire_row_id <= 0:
        return None

    parquet_path = DATA_DIR / "hotspots_2024.parquet"
    if parquet_path.exists():
        try:
            # F24-* is the stable source row id, not a positional index. This
            # matters because filtered parquet reads may be reindexed/sorted.
            frame = pd.read_parquet(
                parquet_path,
                filters=[[('fire_row_id', '==', str(fire_row_id))]],
                engine='pyarrow',
            )
            if not frame.empty:
                item = _coerce_hotspot(frame.iloc[0].to_dict(), fire_row_id)
                item['id'] = f'F24-{fire_row_id}'
                return item
        except (ImportError, ModuleNotFoundError, OSError, ValueError, KeyError):
            pass

    if HOTSPOTS_2024_CSV_PATH.exists():
        for chunk in pd.read_csv(
            HOTSPOTS_2024_CSV_PATH,
            dtype=str,
            keep_default_na=False,
            chunksize=50000,
        ):
            if 'fire_row_id' not in chunk.columns:
                continue
            matches = chunk[chunk['fire_row_id'].astype(str).eq(str(fire_row_id))]
            if not matches.empty:
                item = _coerce_hotspot(matches.iloc[0].to_dict(), fire_row_id)
                item['id'] = f'F24-{fire_row_id}'
                return item

    return None

def list_baselines() -> list[dict]:
    return list(BASELINE.values())


def nearby_for(hotspot: dict) -> list[dict]:
    """Return real named OpenStreetMap context for the selected FIRMS hotspot."""
    from app.osm_facility import nearby_osm_features

    try:
        features = nearby_osm_features(
            float(hotspot["latitude"]),
            float(hotspot["longitude"]),
        )
    except Exception:
        return []

    result = []
    hotspot_id = hotspot.get("id")
    for feature in features:
        item = dict(feature)
        name = str(item.get("name") or item.get("display_name") or "").strip()
        if not name:
            continue
        item["hotspot_id"] = hotspot_id
        item["name"] = name
        item["display_name"] = name
        result.append(item)
    return result

