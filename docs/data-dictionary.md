# Data dictionary and source register

## Source register

| Dataset | Source | Licence | Real or synthetic | Where |
|---|---|---|---|---|
| Hourly weather (rain, temperature, wind) | Open-Meteo historical archive (ERA5 reanalysis) | CC BY 4.0 | Real | `backend/data/raw/weather_<year>.json` |
| City air quality (US AQI, PM2.5, PM10) | Open-Meteo air quality (CAMS) | CC BY 4.0 | Real (modelled grid value) | `backend/data/raw/air_<year>.json` |
| Raw file log | Written by `python -m festivalpulse.ingest` | - | - | `backend/data/raw/sources.json` (URL, fetch time, sha256) |
| Zone register | Hand-curated centroids and attributes | - | Approximate | `backend/festivalpulse/zones.py` |
| Crowd labels | Generated in `data.true_crowd` | - | **Synthetic** | in memory |
| Zone AQI spread | Generated in `data.zone_aqi` | - | **Synthetic** | in memory |
| Social posts | Template posts in `signals.py`, or admin uploads | - | Synthetic unless uploaded | `signals` table |
| Map tiles | OpenStreetMap | ODbL, attribution required | Real | loaded by the browser |

Visarjan dates (Anant Chaturdashi): 2022-09-09, 2023-09-28, 2024-09-17, 2025-09-06. Check them against PMC notices
before claiming accuracy.

## Zone register (`zones.py`)

| Field | Meaning |
|---|---|
| zone_id | Z01-Z10 |
| name, zone_type | Display name; market, ghat, residential or transit |
| lat, lon | Centroid; the polygon is a hexagon around it |
| capacity_persons | Assumed people the zone holds at crowd index 1.0 |
| proc_start, peak | Procession start and crowd peak as timeline hour indices (0 = 06:00, 23 = 05:00 next day) |
| immersion_dist_km | Distance to the nearest immersion point |
| shop_density | 0-1 relative density of shops |
| stalls, waste_points, toilets | Baseline counts used by the waste, sales and sanitation rules |

## Training table (zone x hour, `data.generate`)

| Column | Meaning |
|---|---|
| zone_id, h, clock_hour | Zone; timeline hour index; hour of day |
| year, day, is_festival | Festival year; days before the festival (0 = Visarjan); 1 on Visarjan day |
| hours_to_procession, procession_active | Hours relative to the procession start; 1 while it runs |
| rain_mm, temp_c, wind_kmh | Hourly weather |
| aqi_prev_day | Same-hour city AQI the previous day |
| hist_crowd | Mean crowd for the same zone, day type and relative hour in earlier years |
| crowd_idx | Target: crowd index 0-1 (synthetic) |
| aqi | Target: zone US AQI |
| weather_real | False where the synthetic weather fallback was used |

## Prediction columns (`/api/predictions`)

| Column | Unit | Meaning |
|---|---|---|
| crowd_idx, crowd_p10, crowd_p90 | 0-1 | Crowd forecast and 80% interval |
| congestion_prob | 0-1 | Probability the zone's roads are congested (rule) |
| aqi_pred, aqi_p10, aqi_p90 | US AQI | AQI forecast and 80% interval |
| aqi_uplift | US AQI | Forecast minus the no-festival counterfactual |
| persons | people | crowd_idx x capacity_persons (business footfall layer) |
| waste_kg | kg/hour | Waste generated |
| sanitation_risk | 0-1 | Crowd pressure against toilet capacity |
| emergency_per_h | incidents/hour | Expected emergency load |
| risk | 0-1 | Weighted fusion; weights on the Method and Admin tabs |

## Stored tables (SQLite, REQ §17 names)

| Table | Columns |
|---|---|
| scenarios | scenario_id, name, levers_json, created_at |
| signals | signal_id, zone_id, ts, category, source, anonymised_text |
| settings | key, value_json (risk_weights, action_thresholds) |
| model_runs | run_id, model_name, version, data_version, commit, metrics_json, created_at |
