"""Ingest real hourly weather and city air quality for past Visarjan days (REQ §8, FR-8.1).

Run `python -m festivalpulse.ingest` (from backend/) to fetch; files are committed so the
demo and tests run offline. Every raw file is logged with source, fetch time and sha256.
"""
import datetime as dt
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
LAT, LON = 18.5196, 73.8554  # Pune city centre
DAYS_BEFORE = 20  # ordinary days used as non-festival training rows
# Anant Chaturdashi (Visarjan) dates; verify against PMC notices before claiming accuracy
FESTIVAL_DATES = {2022: "2022-09-09", 2023: "2023-09-28", 2024: "2024-09-17", 2025: "2025-09-06"}
SOURCES = {
    "weather": ("https://archive-api.open-meteo.com/v1/archive", "precipitation,temperature_2m,wind_speed_10m",
                "real: Open-Meteo historical weather (ERA5 reanalysis), CC BY 4.0"),
    "air": ("https://air-quality-api.open-meteo.com/v1/air-quality", "us_aqi,pm2_5,pm10",
            "real (modelled): Open-Meteo air quality (CAMS reanalysis/forecast, city grid cell), CC BY 4.0"),
}


def _window(year):
    d = dt.date.fromisoformat(FESTIVAL_DATES[year])
    return d - dt.timedelta(days=DAYS_BEFORE), d + dt.timedelta(days=1)  # +1: timeline runs to 05:00 next day


def fetch(source, year):
    base, hourly, licence = SOURCES[source]
    start, end = _window(year)
    url = base + "?" + urllib.parse.urlencode({"latitude": LAT, "longitude": LON, "hourly": hourly, "timezone": "Asia/Kolkata",
                                               "start_date": start.isoformat(), "end_date": end.isoformat()})
    with urllib.request.urlopen(url, timeout=30) as r:
        body = r.read()
    json.loads(body)  # fail loudly on a non-JSON error page before writing anything
    path = RAW / f"{source}_{year}.json"
    path.write_bytes(body)
    return {"source": source, "year": year, "url": url, "licence": licence, "path": path.name,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(body).hexdigest()}


def fetch_all():
    RAW.mkdir(parents=True, exist_ok=True)
    log = [fetch(s, y) for y in FESTIVAL_DATES for s in SOURCES]
    (RAW / "sources.json").write_text(json.dumps(log, indent=1))
    return log


def load_hourly(year):
    """Local-time hourly frame for a year's window, or None if the raw files are missing or corrupt (NFR-5)."""
    frames = []
    try:
        for source in SOURCES:
            body = json.loads((RAW / f"{source}_{year}.json").read_text())
            frames.append(pd.DataFrame(body["hourly"]).set_index("time"))
    except (OSError, ValueError, KeyError):
        return None
    df = pd.concat(frames, axis=1)
    df.index = pd.to_datetime(df.index)
    # REQ §8.3: forward-fill gaps up to 3 hours, leave longer gaps missing
    return df.ffill(limit=3).rename(columns={"precipitation": "rain_mm", "temperature_2m": "temp_c",
                                             "wind_speed_10m": "wind_kmh", "us_aqi": "city_aqi"})


def day_slice(hourly, date):
    """24 rows from 06:00 on `date` to 05:00 the next day, or None if any value is missing."""
    start = pd.Timestamp(date) + pd.Timedelta(hours=6)
    d = hourly.reindex(pd.date_range(start, periods=24, freq="h"))
    return None if d[["rain_mm", "temp_c", "wind_kmh", "city_aqi"]].isna().any().any() else d


if __name__ == "__main__":
    for entry in fetch_all():
        print(entry["path"], entry["sha256"][:12])
    sys.exit(0)
