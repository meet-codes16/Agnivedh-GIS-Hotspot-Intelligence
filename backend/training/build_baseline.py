"""Build a historical FIRMS baseline artifact without using target labels.

Profiles are keyed by 1-degree grid and calendar month. Statistics are
computed only from the supplied historical rows; no future/test rows are
included.

The artifact also stores real historical hourly FRP/activity profiles so the
UI can render a location-specific baseline curve.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument(
        "--out",
        default="../models/baseline_profiles.json",
    )
    args = ap.parse_args()

    df = pd.read_csv(
        args.data,
        usecols=[
            "latitude",
            "longitude",
            "frp",
            "acq_date",
            "acq_time",
            "daynight",
            "year",
        ],
        low_memory=False,
    )

    # ------------------------------------------------------------------
    # Date / time normalization
    # ------------------------------------------------------------------
    d = pd.to_datetime(df["acq_date"], errors="coerce")

    t = (
        pd.to_numeric(df["acq_time"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    df["month"] = d.dt.month

    # Decimal hour, e.g. 0730 -> 7.5
    df["hour"] = t // 100 + (t % 100) / 60.0

    # Integer hour bucket 0..23
    df["hour_bin"] = np.floor(df["hour"]).clip(0, 23).astype(int)

    # ------------------------------------------------------------------
    # 1-degree spatial grid
    # ------------------------------------------------------------------
    df["grid_lat"] = np.floor(df["latitude"]).astype(int)
    df["grid_lon"] = np.floor(df["longitude"]).astype(int)

    df["grid_key"] = (
        df["grid_lat"].astype(str)
        + "_"
        + df["grid_lon"].astype(str)
    )

    profiles = {}

    # ------------------------------------------------------------------
    # Grid + month historical profiles
    # ------------------------------------------------------------------
    for (g, m), x in df.groupby(["grid_key", "month"]):
        if pd.isna(m):
            continue

        # Historical active days
        daily = x.groupby(d.loc[x.index]).size()

        # Circular mean of historical acquisition time
        ang = 2 * np.pi * x["hour"] / 24
        s = np.sin(ang).mean()
        c = np.cos(ang).mean()

        h = (
            np.arctan2(s, c) % (2 * np.pi)
        ) * 24 / (2 * np.pi)

        minute = int(round((h - int(h)) * 60)) % 60
        hour_display = int(h) % 24

        # --------------------------------------------------------------
        # Real hourly historical profile
        #
        # Each value is the median FRP of historical observations that
        # occurred in that hour for this grid/month.
        #
        # Missing hours remain null rather than being filled with
        # synthetic values.
        # --------------------------------------------------------------
        hourly_frp = {}

        for hour in range(24):
            hour_rows = x[x["hour_bin"] == hour]

            if len(hour_rows):
                hourly_frp[str(hour)] = float(
                    hour_rows["frp"].median()
                )
            else:
                hourly_frp[str(hour)] = None

        # Historical observation count by hour.
        # This is useful for activity/frequency interpretation.
        hourly_frequency = {}

        for hour in range(24):
            hour_rows = x[x["hour_bin"] == hour]

            hourly_frequency[str(hour)] = int(len(hour_rows))

        # --------------------------------------------------------------
        # Profile
        # --------------------------------------------------------------
        profiles[f"{g}|{int(m)}"] = {
            "region": f"GRID {g}",

            # Existing aggregate baseline metrics
            "normal_frp": float(x["frp"].median()),

            "normal_frequency": float(
                len(x) / max(x["year"].nunique(), 1)
            ),

            "normal_hour": (
                f"{hour_display:02d}:{minute:02d}"
            ),

            "normal_hour_value": float(h),

            "normal_daynight_ratio": float(
                (x["daynight"] == "N").mean()
            ),

            "normal_persistence": (
                "PERSISTENT"
                if len(daily) >= 30
                else (
                    "RECURRENT"
                    if len(daily) >= 5
                    else "SPARSE"
                )
            ),

            "persistence_score": float(
                min(len(daily) / 60, 1.0)
            ),

            "normal_location_density": float(len(x)),

            "location_stability": float(
                1
                / (
                    1
                    + float(
                        x[
                            ["latitude", "longitude"]
                        ]
                        .std()
                        .fillna(0)
                        .mean()
                        * 100
                    )
                )
            ),

            # ----------------------------------------------------------
            # NEW: real historical hourly profiles
            # ----------------------------------------------------------
            "hourly_frp": hourly_frp,
            "hourly_frequency": hourly_frequency,

            "notes": (
                "Historical FIRMS baseline; 1-degree grid; "
                "monthly profile; built from supplied historical data."
            ),
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "grid_size_degrees": 1,
        "profiles": profiles,
        "source_years": sorted(
            df["year"]
            .dropna()
            .unique()
            .astype(int)
            .tolist()
        ),
        "rows": len(df),
        "hourly_profile": {
            "enabled": True,
            "metric": "median_frp_by_hour",
            "hours": 24,
            "source": "historical_rows_only",
        },
    }

    out.write_text(
        json.dumps(
            artifact,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    print(
        f"Wrote {len(profiles)} profiles to {out}"
    )


if __name__ == "__main__":
    main()
