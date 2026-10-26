"""Training data for past Visarjan days and the ordinary days before them (REQ §8).

Weather and city-level AQI are real (see ingest.py); crowd and the zone-to-zone AQI
spread are synthetic until real labels are sourced. Each is labelled (REQ §8.2).
"""
import datetime as dt

import numpy as np
import pandas as pd

from .ingest import DAYS_BEFORE, FESTIVAL_DATES, SOURCES, day_slice, load_hourly
from .zones import ZONES, ZONE_TYPES

HOURS = 24  # event timeline: index 0 = 06:00, 23 = 05:00 next day
DATA_LABEL = "mixed: real weather and city AQI, synthetic crowd"
DATASETS = {"weather": SOURCES["weather"][2], "city_aqi": SOURCES["air"][2],
            "crowd": "synthetic", "zone_aqi_spread": "synthetic (crowd-proportional, centred on city AQI)"}
FEATURES_CROWD = ["clock_hour", "hours_to_procession", "procession_active", "immersion_dist_km",
                  "zone_type_code", "shop_density", "rain_mm", "temp_c", "is_festival", "hist_crowd"]
FEATURES_AQI = ["clock_hour", "crowd_idx", "rain_mm", "wind_kmh", "temp_c", "is_festival", "aqi_prev_day"]


def clock_hour(h):
    return (6 + h) % 24


def weather(rng):
    h = np.arange(HOURS)
    rain = np.where(rng.random(HOURS) < 0.2, rng.gamma(1.5, 3.0, HOURS), 0.0)
    temp = 27 + 3 * np.sin((clock_hour(h) - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.5, HOURS)
    wind = rng.uniform(2, 12, HOURS)
    return rain, temp, wind


def day_inputs(hourly, date, rng):
    """Real weather and city AQI for the 06:00-05:00 timeline, or a labelled synthetic fallback (NFR-5)."""
    d = day_slice(hourly, date) if hourly is not None else None
    if d is None:
        rain, temp, wind = weather(rng)
        ch = clock_hour(np.arange(HOURS))
        city = 70 + 25 * (np.exp(-((ch - 9) ** 2) / 4) + np.exp(-((ch - 19) ** 2) / 4)) - 5 * rain - 1.5 * wind
        return {"rain": rain, "temp": temp, "wind": wind, "city_aqi": city, "aqi_prev": np.full(HOURS, np.nan), "real": False}
    prev = hourly["city_aqi"].reindex(d.index - pd.Timedelta(days=1)).to_numpy()
    return {"rain": d["rain_mm"].to_numpy(), "temp": d["temp_c"].to_numpy(), "wind": d["wind_kmh"].to_numpy(),
            "city_aqi": d["city_aqi"].to_numpy(), "aqi_prev": prev, "real": True}


def scenario_day(seed=2026):
    """Inputs for the scenario: a replay of the most recent Visarjan day's real weather."""
    year = max(FESTIVAL_DATES)
    inp = day_inputs(load_hourly(year), dt.date.fromisoformat(FESTIVAL_DATES[year]), np.random.default_rng(seed))
    inp["label"] = f"replay of Visarjan {year} weather" if inp["real"] else "synthetic weather (source unavailable)"
    return inp


def features(zone, rain, temp, wind, is_festival, shift=0, aqi_prev=np.nan):
    h = np.arange(HOURS)
    start = zone["proc_start"] + shift
    return pd.DataFrame({
        "zone_id": zone["zone_id"], "h": h, "clock_hour": clock_hour(h),
        "hours_to_procession": (h - start) if is_festival else np.full(HOURS, -24),
        "procession_active": ((h >= start) & (h < start + 18)).astype(int) if is_festival else 0,
        "immersion_dist_km": zone["immersion_dist_km"], "zone_type_code": ZONE_TYPES.index(zone["zone_type"]),
        "shop_density": zone["shop_density"], "rain_mm": rain, "temp_c": temp, "wind_kmh": wind,
        "is_festival": int(is_festival), "aqi_prev_day": aqi_prev,
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


def zone_aqi(day, city_aqi, rng):
    """City AQI (real) plus a synthetic zone spread proportional to crowd, centred so the city mean is unchanged."""
    spread = 40 * (day["crowd_idx"] - day.groupby("h")["crowd_idx"].transform("mean"))
    return np.clip(np.tile(city_aqi, len(ZONES)) + spread.to_numpy() + rng.normal(0, 4, len(day)), 0, 500)


def generate(years=tuple(FESTIVAL_DATES), seed=7):
    rng = np.random.default_rng(seed)
    days = []
    for i, year in enumerate(years):
        growth = 1 + 0.03 * i
        hourly, fest_date = load_hourly(year), dt.date.fromisoformat(FESTIVAL_DATES[year])
        for k in range(DAYS_BEFORE, -1, -1):  # 20 ordinary days, then the festival (k=0)
            inp = day_inputs(hourly, fest_date - dt.timedelta(days=k), rng)
            zs = []
            for z in ZONES:
                df = features(z, inp["rain"], inp["temp"], inp["wind"], k == 0, aqi_prev=inp["aqi_prev"])
                df["crowd_idx"] = true_crowd(df, z, rng, growth)
                zs.append(df)
            day = pd.concat(zs, ignore_index=True)
            day["aqi"] = zone_aqi(day, inp["city_aqi"], rng)
            day["year"], day["day"], day["weather_real"] = year, k, inp["real"]
            days.append(day)
    out = pd.concat(days, ignore_index=True)
    for year in years:
        mask = out["year"] == year
        out.loc[mask, "hist_crowd"] = lookup_history(out[mask], history_table(out, year - 1))
    return out


def _rel(df):
    # festival rows align on procession-relative hour so a start-time shift carries history with it
    return np.where(df["is_festival"] == 1, df["hours_to_procession"], df["h"])


def history_table(df, year):
    """historical_footfall_same_hour (REQ §10.1): mean crowd per zone / day type / relative hour over all years up to `year` (averaging cuts single-year noise)."""
    d = df[df["year"] <= year]
    return d.assign(rel=_rel(d)).groupby(["zone_id", "is_festival", "rel"])["crowd_idx"].mean()


def lookup_history(df, table):
    keys = pd.MultiIndex.from_arrays([df["zone_id"], df["is_festival"], _rel(df)])
    return table.reindex(keys).to_numpy()  # NaN where no history; the model handles missing values
