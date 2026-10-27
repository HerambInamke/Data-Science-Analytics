# Model cards

Holdout metrics for each model are in [evaluation.md](evaluation.md), which is regenerated from code. Every startup also
logs a row per model in the `model_runs` table (data version and git commit, FR-8.3).

## Crowd model

| | |
|---|---|
| Purpose | Crowd index (0-1, share of zone capacity) per zone and hour of Visarjan day, with an 80% interval |
| Algorithm | scikit-learn `HistGradientBoostingRegressor` (LightGBM-style histogram boosting): squared-error point model, 0.1 and 0.9 quantile models for the interval, widened by a conformal margin |
| Features | clock hour, hours to procession, procession active, distance to immersion point, zone type, shop density, rain, temperature, festival flag, historical crowd for the same zone and relative hour |
| Training data | 4 festivals (2022-2025) x 21 days x 10 zones x 24 hours. Weather is real (ERA5); **crowd labels are synthetic** |
| Weighting | Festival rows weighted 10x: they are the target and about 5% of rows |
| Evaluation | Most recent festival held out; seasonal-naive baseline (same zone-hour, previous festival); intervals calibrated on the year before the holdout |
| Explanations | Top-3 drivers per zone-hour by occlusion (swap each feature to its ordinary-day mean) |
| Limitations | Synthetic labels, so accuracy against real crowds is unknown. Zones are approximate hexagons. Associations, not causes |
| Intended use | Planning aid for PMC, police and mandals. Not for real-time crowd control or decisions about individuals |

## AQI model

| | |
|---|---|
| Purpose | Zone US AQI per hour plus the festival uplift against a same-day no-festival counterfactual |
| Algorithm | Same quantile gradient boosting set-up as the crowd model |
| Features | clock hour, crowd index, rain, wind speed, temperature, festival flag, same-hour AQI the previous day |
| Training data | City AQI is **real but modelled** (CAMS grid cell via Open-Meteo, 24h-averaged US AQI). The zone-to-zone spread is synthetic (proportional to crowd) |
| Evaluation | Festival-day holdout vs seasonal-naive; ordinary days vs same-hour-yesterday persistence |
| Known weakness | Slightly worse than persistence on ordinary days, because training favours festival days |
| Limitations | No station-level readings; the uplift is a model counterfactual, not a measurement |

## Social-risk classifier

| | |
|---|---|
| Purpose | Sort public text into ROUTE_BLOCKED, TOO_CROWDED, NO_DUSTBIN, MEDICAL_HELP_NEEDED, TRAFFIC_SLOW, POSITIVE_EVENT, OTHER |
| Algorithm | TF-IDF (word 1-2 grams) + logistic regression |
| Pre-processing | Emails, URLs, @handles and phone numbers masked **before** classification and storage (FR-3.5) |
| Geocoding | Longest-match lookup in a hand-made gazetteer of Pune landmarks; unmatched posts are counted but not placed |
| Training data | 400 synthetic template posts; evaluated on 300 more |
| Limitations | Near-perfect scores only reflect the templates. Needs at least 300 hand-labelled real posts (REQ §10.5). English only; no Marathi or Hindi |
| Intended use | Aggregate counts per zone as a check on the predictions. Raw text is never shown in the UI or API |

## Rule-based components

Traffic congestion, diversion effect, waste, sanitation, emergency load, sales uplift, combined risk and the
Sustainability Score are formulas with assumed coefficients, not trained models. Each assumption is listed in
`engine.ASSUMPTIONS` and on the Method tab. The risk weights and action thresholds can be changed on the Admin tab.
