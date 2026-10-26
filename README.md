# FestivalPulse

A decision-support "digital twin" for Ganesh Visarjan in Pune. It predicts crowd pressure, traffic congestion, air-quality spikes, waste and emergency load per zone and hour, lets planners test what-if scenarios on a map, and produces a per-zone action plan. Full spec: [req.md](req.md).

> **Data honesty:** weather (ERA5) and city-level air quality (CAMS) are **real**, fetched from Open-Meteo for the last four Visarjan days and the 20 days before each. Crowd labels and the zone-to-zone AQI spread are **synthetic**. Every dataset is labelled in the API and on the Method tab. Outputs are planning aids, not observations or official ratings.

## Run

```bash
docker compose up --build          # http://localhost:8000
```

or locally (Python 3.12+):

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn festivalpulse.main:app   # http://localhost:8000
python -m pytest -q                        # tests
```

## What's in this version (hackathon mode, REQ §22)

| Area | Status |
|---|---|
| Real data ingest (Open-Meteo weather + air quality), raw files logged with sha256 | `python -m festivalpulse.ingest`; cached in `backend/data/raw` so the demo runs offline |
| Crowd model (gradient boosting, 80% interval, top-3 drivers) | Beats seasonal-naive baseline by 15.2% MAE on the 2025 holdout |
| AQI model + festival uplift vs no-festival counterfactual | Beats baseline by 66% MAE on real city AQI |
| Traffic, waste, sanitation, emergency, combined risk | Rule-based, assumptions listed on the Method tab |
| What-if: diversion %, start-time shift, rain, waste points, toilets | Baseline vs scenario comparison, shareable link |
| Sustainability Score (0-100) with breakdown | Yes |
| Advisor | Retrieval-only answers with citations; refuses operational commands |
| Action plan | JSON + CSV |
| Map + timeline UI | MapLibre, 06:00 → 05:00 slider, layer toggles, zone panel |

Not yet: PostgreSQL/PostGIS persistence, real crowd labels, social signal radar, PDF export, LLM advisor, road-segment traffic.

## Layout

```
backend/festivalpulse/  zones.py  ingest.py  data.py  models.py  engine.py  advisor.py  main.py
backend/tests/          scenario sanity checks, model-vs-baseline, API and advisor tests
frontend/index.html     single-page map UI served at /
```

## API

`GET /api/zones` · `GET /api/predictions` · `GET /api/risk` · `GET /api/zones/{id}` · `POST /api/scenarios` · `GET /api/scenarios/{id}` · `POST /api/advisor/query` · `GET /api/action-plan?format=csv` · `GET /api/health` · `GET /api/methodology`

Map tiles © OpenStreetMap contributors. Weather and air-quality data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).
