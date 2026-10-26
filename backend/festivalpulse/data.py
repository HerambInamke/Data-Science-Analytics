"""Synthetic training data (REQ §8.2: labelled synthetic, never presented as observed).

Generates zone x hour rows for past Visarjan days and ordinary days so the crowd
and AQI models have something to learn from until real labels are sourced.
"""
import numpy as np
import pandas as pd

from .zones import ZONES, ZONE_TYPES

HOURS = 24  # event timeline: index 0 = 06:00, 23 = 05:00 next day
DATA_LABEL = "synthetic"
FEATURES_CROWD = ["clock_hour", "hours_to_procession", "procession_active", "immersion_dist_km",
                  "zone_type_code", "shop_density", "rain_mm", "temp_c", "is_festival", "hist_crowd"]
FEATURES_AQI = ["clock_hour", "crowd_idx", "rain_mm", "wind_kmh", "temp_c", "is_festival"]


def clock_hour(h):
    return (6 + h) % 24


def weather(rng):
    h = np.arange(HOURS)
    rain = np.where(rng.random(HOURS) < 0.2, rng.gamma(1.5, 3.0, HOURS), 0.0)
    temp = 27 + 3 * np.sin((clock_hour(h) - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.5, HOURS)
    wind = rng.uniform(2, 12, HOURS)
    return rain, temp, wind


def features(zone, rain, temp, wind, is_festival, shift=0):
    h = np.arange(HOURS)
    start = zone["proc_start"] + shift
    return pd.DataFrame({
        "zone_id": zone["zone_id"], "h": h, "clock_hour": clock_hour(h),
        "hours_to_procession": (h - start) if is_festival else np.full(HOURS, -24),
        "procession_active": ((h >= start) & (h < start + 18)).astype(int) if is_festival else 0,
        "immersion_dist_km": zone["immersion_dist_km"], "zone_type_code": ZONE_TYPES.index(zone["zone_type"]),
        "shop_density": zone["shop_density"], "rain_mm": rain, "temp_c": temp, "wind_kmh": wind,
        "is_festival": int(is_festival),
    })


def true_crowd(df, zone, rng, growth=1.0):
    ch = df["clock_hour"].to_numpy()
    d = np.abs(ch - 19)
    daily = 0.15 + 0.15 * zone["shop_density"] * np.exp(-np.minimum(d, 24 - d) ** 2 / 30)
    # peak sits a fixed offset after procession start, so a start-time shift moves it
    bump = np.exp(-((df["hours_to_procession"].to_numpy() - (zone["peak"] - zone["proc_start"])) ** 2) / 32)
    near_water = 0.15 * np.exp(-zone["immersion_dist_km"])
    fest = df["is_festival"].to_numpy() * (0.55 * bump * df["procession_active"].to_numpy() + near_water * bump)
    y = growth * (daily + fest) - 0.025 * df["rain_mm"].to_numpy() + rng.normal(0, 0.04, len(df))
    return np.clip(y, 0, 1)


def true_aqi(df, rng):
    ch = df["clock_hour"].to_numpy()
    rush = np.exp(-((ch - 9) ** 2) / 4) + np.exp(-((ch - 19) ** 2) / 4)
    night = ((ch >= 20) | (ch <= 2)).astype(float)
    fest = df["is_festival"].to_numpy()
    y = (70 + 25 * rush + 60 * df["crowd_idx"].to_numpy() + fest * night * 45 * df["crowd_idx"].to_numpy()
         - 5 * df["rain_mm"].to_numpy() - 1.5 * df["wind_kmh"].to_numpy() + rng.normal(0, 8, len(df)))
    return np.clip(y, 20, 500)


def generate(years=(2022, 2023, 2024, 2025), ordinary_days=20, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for i, year in enumerate(years):
        growth = 1 + 0.03 * i
        for day in range(ordinary_days + 1):
            fest = day == 0
            rain, temp, wind = weather(rng)
            for z in ZONES:
                df = features(z, rain, temp, wind, fest)
                df["crowd_idx"] = true_crowd(df, z, rng, growth)
                df["aqi"] = true_aqi(df, rng)
                df["year"], df["day"] = year, day
                rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    out["data_label"] = DATA_LABEL
    for year in years:
        mask = out["year"] == year
        out.loc[mask, "hist_crowd"] = lookup_history(out[mask], history_table(out, year - 1))
    return out


def _rel(df):
    # festival rows align on procession-relative hour so a start-time shift carries history with it
    return np.where(df["is_festival"] == 1, df["hours_to_procession"], df["h"])


def history_table(df, year):
    """historical_footfall_same_hour (REQ §10.1): mean crowd per zone / day type / relative hour in `year`."""
    d = df[df["year"] == year]
    return d.assign(rel=_rel(d)).groupby(["zone_id", "is_festival", "rel"])["crowd_idx"].mean()


def lookup_history(df, table):
    keys = pd.MultiIndex.from_arrays([df["zone_id"], df["is_festival"], _rel(df)])
    return table.reindex(keys).to_numpy()  # NaN where no history; the model handles missing values
