# Evaluation report

Generated 2026-10-27 by `python -m festivalpulse.report`. Do not edit by hand; rerun instead.

Data: mixed: real weather and city AQI, synthetic crowd. Holdout: the 2025 festival, never used for tuning (REQ §18.2). Intervals are
calibrated on the year before the holdout.

## Crowd and AQI models (REQ §18.1)

| Model | Slice | MAE | Baseline MAE | Gain | RMSE | Bias | 80% interval coverage | Baseline |
|---|---|---|---|---|---|---|---|---|
| Crowd | festival day | 0.039 | 0.046 | 15.2% | 0.0496 | -0.0158 | 0.863 | seasonal-naive (same zone-hour, previous festival) |
| AQI | festival day | 7.483 | 22.1501 | 66.2% | 9.4257 | 5.8501 | 0.8 | seasonal-naive (same zone-hour, previous festival) |
| AQI | ordinary days (n=4620) | 11.0001 | 10.1813 | -8.0% | - | 3.4558 | - | persistence (same hour, previous day) |

- NFR-3 (crowd beats seasonal-naive by at least 15% MAE): **met** (15.2%). Crowd labels are
  synthetic, so this shows the pipeline works, not that it predicts real crowds.
- AQI on ordinary days is compared with same-hour-yesterday persistence. A negative gain means persistence wins; the
  model is trained to favour festival days (10x sample weight).
- Traffic, waste, sanitation and emergency are rule-based (assumptions on the Method tab), so they have no holdout
  metrics yet. Waste hotspot precision needs observed collection data.

## Social-risk classifier (REQ §10.5)

Data: synthetic social signals (template posts) unless uploaded.

| Category | Precision | Recall | F1 | n |
|---|---|---|---|---|
| ROUTE_BLOCKED | 1.0 | 1.0 | 1.0 | 52 |
| TOO_CROWDED | 1.0 | 1.0 | 1.0 | 52 |
| NO_DUSTBIN | 1.0 | 1.0 | 1.0 | 47 |
| MEDICAL_HELP_NEEDED | 1.0 | 1.0 | 1.0 | 42 |
| TRAFFIC_SLOW | 1.0 | 1.0 | 1.0 | 29 |
| POSITIVE_EVENT | 1.0 | 1.0 | 1.0 | 44 |
| OTHER | 1.0 | 1.0 | 1.0 | 34 |

These scores are inflated: test posts come from the same templates as training posts. A real evaluation needs at least
300 hand-labelled real posts.

## Scenario sanity checks (REQ §18.3)

Covered by `backend/tests`: full diversion never gives negative traffic, extra waste points never increase uncollected
waste, rain never increases crowd, a later start moves the peak later.
