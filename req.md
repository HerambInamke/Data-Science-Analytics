# REQ.md: FestivalPulse, India's Cultural Event Impact Digital Twin

Version: 0.1 (draft for hackathon and MVP)
Owner: Vansh (Heramb Vivek Inamke)
Scope: Ganesh Visarjan in Pune (MVP), extensible to other festivals and cities

---

## 1. Summary

FestivalPulse is a decision-support system for city administrators, event organisers, and local businesses. It predicts the hidden impact of large Indian festivals on a city: crowd pressure, traffic congestion, air-quality spikes, waste generation, emergency-response load, and local economic activity. It then recommends concrete actions and lets users test what-if scenarios on a map.

Core question the product answers:

> "During Ganesh Visarjan, which routes will become unsafe or congested, where should sanitation teams be pre-positioned, and what will the festival's environmental and economic footprint be?"

---

## 2. Problem Statement

- Festivals such as Ganesh Chaturthi, Navratri, Diwali, and Visarjan create sudden, concentrated pressure on city systems for a few hours or days.
- Planning is mostly reactive. Waste trucks, mobile toilets, traffic diversions, and police deployments are decided from past experience and phone calls, not from forecasts.
- Air-quality and waste data exist but are not linked to festival schedules, routes, or specific zones.
- Local vendors have no forward-looking view of where footfall will be.

**Who feels this pain**
- Municipal corporation (PMC) sanitation and traffic teams
- Police traffic control units
- Festival committees (mandals) and volunteers
- Local shop and stall owners
- Citizens who want to plan safe routes

---

## 3. Goals and Non-Goals

### 3.1 Goals (MVP)
1. Predict crowd density, traffic congestion, AQI deterioration, and waste hotspots for Ganesh Visarjan in Pune at zone and hour resolution.
2. Provide an interactive map with a time slider from morning through late night.
3. Provide a what-if simulator with at least three levers: traffic diversion %, immersion start time shift, extra waste-collection points.
4. Generate an action plan per zone (what to do, where, when).
5. Provide a grounded AI advisor that answers questions using model outputs and cites the underlying data.
6. Produce a Sustainability Score (0 to 100) for each scenario.

### 3.2 Non-Goals (for MVP)
- Real-time CCTV crowd counting (listed as a future upgrade).
- Reinforcement-learning traffic control.
- Federated learning across municipal zones.
- Mobile citizen app (web responsive only in MVP).
- Live integration with municipal control-room systems.
- Any personal data tracking of individuals.
- Predictions for festivals other than Ganesh Visarjan until the MVP is validated.

---

## 4. Target Users and Personas

| Persona | Needs | Key screens |
|---|---|---|
| Municipal sanitation officer | Where to place trucks and toilets, when | Waste hotspots, action plan export |
| Traffic police planner | Which roads to close or divert, when | Traffic map, what-if simulator |
| Event coordinator / mandal volunteer | Crowd peaks, safe routes | Crowd map, timeline |
| Local vendor | Where and when footfall will peak | Business-opportunity layer |
| Hackathon judge / reviewer | Clear demo, credible method | Full dashboard, methodology page |

---

## 5. Scope and Geography (MVP)

- City: Pune, Maharashtra
- Festival: Ganesh Visarjan (immersion days, with the main peak on the final day, Anant Chaturdashi)
- Zones: 8 to 10 zones, each a cluster of road segments. Suggested zones:
  1. Central Pune (Shaniwar Wada / Budhwar Peth area)
  2. Laxmi Road and Tilak Road corridor
  3. FC Road and Deccan area
  4. Mula-Mutha riverfront ghats (multiple ghats as sub-zones)
  5. Sangam Bridge area
  6. Camp / MG Road market area
  7. Kothrud / Karve Road corridor
  8. Hadapsar and Magarpatta corridor
  9. Swargate and Katraj approach roads
  10. Pune Station / Sadhu Vaswani area
- Time resolution: 1 hour
- Spatial resolution: zone-level for predictions, road-segment level for traffic

Note: Exact zone boundaries, ghat names, and procession routes must be confirmed against official PMC and police announcements before any demo that claims accuracy.

---

## 6. Functional Requirements

### 6.1 Festival Impact Predictor (FR-1)
- FR-1.1 The system shall predict, for each zone and hour, a Crowd Density Index (0 to 1).
- FR-1.2 The system shall predict a Traffic Congestion Probability (0 to 1) for each road segment and hour.
- FR-1.3 The system shall predict an AQI Deterioration Risk for each zone and hour, based on the forecast AQI and the festival-attributable uplift.
- FR-1.4 The system shall predict Waste Generation (kg per zone per day) and identify hotspots (top 10% zones).
- FR-1.5 The system shall predict Emergency-Response Pressure (estimated incidents per zone per hour) using crowd density and historical incident proxies.
- FR-1.6 The system shall estimate Sales Uplift for registered shop and stall clusters in each zone.
- FR-1.7 Each prediction shall include an uncertainty range (80% interval).

### 6.2 City What-If Simulator (FR-2)
- FR-2.1 Users shall adjust levers: traffic diversion % on a chosen corridor; immersion start-time shift (hours, positive or negative); extra waste-collection points per zone; rainfall override (mm/hour); extra mobile toilets per zone.
- FR-2.2 On change, the system shall recompute affected predictions within 5 seconds for the MVP scope.
- FR-2.3 The system shall show a side-by-side comparison between baseline and scenario.
- FR-2.4 Scenarios shall be saveable and shareable via a link.

### 6.3 Social Signal Radar (FR-3)
- FR-3.1 The system shall ingest public text from approved sources: news headlines (RSS), and public social posts where terms of service allow it (manual upload or a permitted API).
- FR-3.2 The system shall classify each text into categories: ROUTE_BLOCKED, TOO_CROWDED, NO_DUSTBIN, MEDICAL_HELP_NEEDED, TRAFFIC_SLOW, POSITIVE_EVENT, OTHER.
- FR-3.3 The system shall geocode mentions to zones using place-name matching and a gazetteer of Pune landmarks.
- FR-3.4 The system shall display signal counts per zone and compare them with sensor-based predictions as a validation layer.
- FR-3.5 The system shall discard or mask any personally identifying information before storage.

### 6.4 AI City Advisor (FR-4)
- FR-4.1 Users shall ask natural-language questions about the event and scenario.
- FR-4.2 The advisor shall answer using retrieval from: current predictions, scenario outputs, the zone register, and the methodology document.
- FR-4.3 Every factual answer shall cite its source (table name, zone ID, timestamp, or document section).
- FR-4.4 If data is insufficient, the advisor shall say so instead of guessing.
- FR-4.5 The advisor shall produce a top-3 recommended action list on request.

### 6.5 Sustainability Score (FR-5)
- FR-5.1 Each scenario shall receive a score from 0 to 100 (see Section 10).
- FR-5.2 The score breakdown shall be visible, with each component's contribution.

### 6.6 Action Plan Export (FR-6)
- FR-6.1 The system shall generate a per-zone action plan: time window, recommended action, responsible team, and expected impact.
- FR-6.2 Plans shall be downloadable as PDF and CSV.

### 6.7 Map and Timeline UI (FR-7)
- FR-7.1 A Pune map shall show zones colour-coded by a selected layer: traffic, AQI, crowd, waste, business, or combined risk.
- FR-7.2 A timeline slider shall move from 06:00 to 06:00 next day in 1-hour steps.
- FR-7.3 Layer toggles shall be available for each metric.
- FR-7.4 Clicking a zone shall open a panel with predictions, uncertainty, top drivers, and recommended actions.

### 6.8 Data Management (FR-8)
- FR-8.1 Raw data shall be stored with source, fetch timestamp, and checksum.
- FR-8.2 Cleaned data shall be stored at zone × hour granularity.
- FR-8.3 All model runs shall be versioned with input data version and code commit.

---

## 7. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | Dashboard first load under 3 seconds on a 4G connection (MVP build) |
| NFR-2 | Performance | What-if recomputation under 5 seconds for MVP scope |
| NFR-3 | Accuracy | Crowd and traffic models shall beat a seasonal-naive baseline by at least 15% MAE on the holdout set |
| NFR-4 | Explainability | Every zone prediction shall list its top 3 drivers (SHAP or equivalent) |
| NFR-5 | Reliability | If a data source is down, the system shall fall back to last known value and show a staleness badge |
| NFR-6 | Privacy | No personally identifiable data stored; social text anonymised; aggregated outputs only |
| NFR-7 | Security | API keys stored in environment variables; rate limiting on public endpoints; no secrets in the frontend bundle |
| NFR-8 | Accessibility | WCAG 2.1 AA colour contrast; colour-blind-safe palette with labels, not colour alone |
| NFR-9 | Portability | Runs locally with a single docker-compose command |
| NFR-10 | Licensing | Only data sources whose licence allows research and demo use |
| NFR-11 | Transparency | Methodology and limitations page shipped with the product |

---

## 8. Data Requirements

### 8.1 Data Sources

| # | Category | Example sources | Used for | Access notes |
|---|---|---|---|---|
| D1 | Air quality | CPCB station data, OpenAQ | AQI forecast baseline and festival uplift | Check licence; OpenAQ offers an API |
| D2 | Weather | IMD open data, Open-Meteo | Rainfall, temperature, wind | Open-Meteo offers a free API for non-commercial use |
| D3 | Road network | OpenStreetMap | Road segments, capacity proxies | Open licence (ODbL), attribution required |
| D4 | Traffic | Historical congestion proxies, probe data if available, manual counts | Congestion labels | Google Traffic API is paid; use only if budget allows; otherwise proxy |
| D5 | Satellite / geospatial | Sentinel-2 (Copernicus), land-use layers | Green cover, water bodies, urban density | Free with registration |
| D6 | Event schedule | PMC and police notices, news, mandal announcements | Procession routes, timings, immersion points | Manual curation with source links |
| D7 | Social text | News RSS, permitted social APIs, manual sample | Social Signal Radar | Respect platform terms; no scraping of private data |
| D8 | Business | Public listings (Google Places-style data via permitted API, or manually curated list) | Shop density, vendor clusters | Use sample data for MVP |
| D9 | Waste | Municipal cleanup records if shared; otherwise synthetic baseline from footfall ratios | Waste model targets | Mark as synthetic where used |
| D10 | Historical crowd | Published event reports, news photo counts, mandal estimates | Crowd model labels (sparse) | Expect sparse labels; use as validation |
| D11 | Vision (future) | Public CCTV or drone imagery datasets (e.g., UVH-26 for vehicle detection) | Future crowd and vehicle counting | Non-MVP |

### 8.2 Data Honesty Rules
- Every dataset in the demo shall be labelled as real, public, manual, or synthetic.
- Synthetic data shall never be presented as observed data.
- Any historical event used as a label shall have a source link.

### 8.3 Data Quality Checks
- Missing AQI readings: forward-fill up to 3 hours; otherwise mark missing and exclude from training.
- Outliers: IQR-based flagging; manual review for values beyond 4 standard deviations.
- Time alignment: all timestamps in Asia/Kolkata; stored in UTC.
- Spatial alignment: every record attached to a zone ID and, where relevant, a road segment ID.

---

## 9. System Architecture

### 9.1 High-Level Components

```
[Data Sources]
   |  (scheduled ingest jobs)
   v
[Ingest Service] -> [Raw Store (Parquet + object storage)]
   |
   v
[Cleaning & Feature Pipeline] -> [Analytics Store (PostgreSQL + PostGIS)]
   |
   v
[Model Service]
   |- Crowd model
   |- Traffic model (road-graph)
   |- AQI model
   |- Waste model
   |- Social-risk classifier
   |- Fusion layer (risk score)
   |
   v
[API Layer (FastAPI)] <--> [LLM Advisor (RAG over outputs + docs)]
   |
   v
[Frontend (Next.js + MapLibre)]
   - Map, timeline, what-if, advisor, action plans
```

### 9.2 Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Frontend | Next.js, TypeScript, MapLibre GL, Recharts | Fast map rendering, familiar stack |
| Backend API | FastAPI (Python) | Easy integration with ML code |
| Database | PostgreSQL + PostGIS | Spatial queries on zones and road segments |
| Analytics files | Parquet + DuckDB | Fast training data access |
| Scheduling | Prefect or cron (MVP) | Reliable ingest runs |
| ML | pandas, scikit-learn, LightGBM, Prophet or statsforecast, NetworkX (road graph), PyTorch Geometric (upgrade) | Practical baseline first |
| Explainability | SHAP | Driver explanations |
| NLP | spaCy, a small transformer classifier, rapidfuzz for place matching | Social signal classification |
| LLM advisor | LLM API with tool calls; embeddings for document retrieval | Grounded answers with citations |
| Containers | Docker, docker-compose | One-command setup |
| Testing | pytest, Playwright (UI), Great Expectations or custom checks (data) | Quality gates |

### 9.3 Deployment (MVP)
- Local: docker-compose with API, DB, frontend, scheduler.
- Demo: single small VM or managed container service; static frontend build.

---

## 10. Models and Logic

### 10.1 Crowd Model
- Target: Crowd Density Index per zone per hour.
- Inputs: hours_to_procession, procession_active flag, immersion_point_distance, historical_footfall_same_hour, weather (rain, temperature), day_of_week, public_holiday flag, zone_type (market, ghat, residential), shop_density.
- Model: LightGBM regressor (MVP); LSTM or Temporal Fusion Transformer as upgrade.
- Validation: time-based split (train on earlier festival years and non-festival days; test on the most recent festival).
- Baseline: same hour on the previous festival day.

### 10.2 Traffic Model
- Target: Congestion Probability per road segment per hour (binary label from speed-drop threshold or manual counts).
- Inputs: segment capacity proxy (lanes, road class from OSM), crowd density of adjacent zones, route closure flags, diversion %, time of day, rainfall.
- Model: LightGBM classifier (MVP); graph-based model over the road network (GNN) as upgrade.
- Diversion logic: when a diversion % is applied to a corridor, the diverted share is added to alternate segments based on a shortest-path rule using NetworkX with travel-time weights.

### 10.3 AQI Model
- Target: AQI at zone level, hourly, and festival uplift = predicted AQI minus no-festival counterfactual.
- Inputs: historical AQI, wind speed and direction, rainfall, temperature, traffic proxy, crowd density (smoke and dust from burning and crowds).
- Model: Prophet or statsforecast for baseline; LightGBM for uplift with festival features.
- Note: fireworks and idol-related burning are key drivers and should be modelled as separate features where data permits. Do not claim causal effects without evidence.

### 10.4 Waste Model
- Target: waste generated per zone per day, and hotspot flag.
- Inputs: predicted crowd (sum over hours), food-stall count, route length, historical cleanup records (if available).
- Model: Poisson or gradient-boosted regression; hotspot = top 10% of zones.

### 10.5 Social-Risk Classifier
- Target: category from FR-3.2.
- Model: fine-tuned small transformer or TF-IDF + logistic regression baseline.
- Evaluation: precision and recall per category on a hand-labelled set of at least 300 items.

### 10.6 Fusion Layer: Combined Risk Score
For each zone and hour:

```
RiskScore = w1 * CrowdNorm + w2 * TrafficNorm + w3 * AQINorm + w4 * WasteNorm + w5 * EmergencyNorm
```

Default weights: w1=0.30, w2=0.25, w3=0.20, w4=0.15, w5=0.10 (sum = 1.0). All components normalised to 0 to 1 using training-period percentiles. Weights are configurable in the admin settings and documented.

### 10.7 Sales Uplift Estimate
- For each shop cluster: baseline sales (from owner input or proxy) × (1 + crowd uplift factor).
- Crowd uplift factor is learned from historical festival sales where available; otherwise a documented assumption with a range.

---

## 11. What-If Simulator: Mechanics

| Lever | Effect on model inputs | Output affected |
|---|---|---|
| Traffic diversion % on corridor C | Reduces load on C; increases load on alternates via shortest-path redistribution | Traffic, AQI (exhaust), crowd (access) |
| Immersion start-time shift (h) | Shifts procession_active and hours_to_procession | Crowd, traffic, waste timing |
| Extra waste points in zone Z | Increases cleanup capacity term in waste model | Waste backlog, AQI (dust reduction assumed small) |
| Rainfall override (mm/h) | Changes weather features | Crowd, traffic, AQI |
| Extra mobile toilets in zone Z | Reduces sanitation-risk term | Sanitation risk (added as a separate score component) |

Simulation rules:
- Scenarios are stored with full lever settings.
- Scenario outputs are compared to baseline with deltas and confidence intervals.
- Any lever with no empirical basis must be labelled "assumed effect."

---

## 12. Sustainability Score

Score (0 to 100) = weighted sum of component scores, each scored 0 to 100 where higher is better:

| Component | Weight | Measure (lower impact = higher score) |
|---|---|---|
| Emissions | 20 | Estimated CO2 from traffic and generator use |
| Waste | 20 | Predicted uncollected waste (kg) vs planned collection |
| Traffic delay | 15 | Average delay minutes across corridors |
| Crowd safety | 20 | Share of zone-hours below high-crowd threshold |
| Economic benefit | 15 | Local vendor sales uplift (higher is better) |
| Water-body impact | 10 | Estimated waste load entering river segments |

Notes:
- The score is a planning aid, not an official rating. This must appear on the page.
- Weights are documented and editable in config.

---

## 13. AI City Advisor: Design

### 13.1 Retrieval Sources
1. Prediction tables (zone × hour)
2. Scenario results
3. Zone register (names, IDs, landmarks, capacities)
4. Methodology and limitations document
5. Action-plan templates

### 13.2 Behaviour Rules
- Answer only from retrieved context.
- Cite sources in every factual statement.
- Refuse operational commands outside scope (e.g., "close this road now"); instead suggest the user contact the authority.
- Show confidence and uncertainty.
- Flag stale data.

### 13.3 Example Interaction

User: "Where should PMC place mobile toilets during Visarjan night?"

Expected behaviour: Return the top 3 zones by sanitation-risk score for 20:00 to 02:00, with the predicted crowd index, waste index, and the confidence interval. Cite the prediction table and timestamp. Note that the recommendation is a planning suggestion.

---

## 14. User Flows

### 14.1 Planner flow
1. Open dashboard; default view is baseline for Visarjan day.
2. Select layer (combined risk).
3. Drag timeline to 20:00.
4. Click highest-risk zone; read drivers and actions.
5. Open What-If; set diversion 20% on FC Road.
6. Compare scenario vs baseline; read Sustainability Score change.
7. Ask advisor for top 3 actions.
8. Download action plan PDF.

### 14.2 Vendor flow
1. Open Business layer.
2. See predicted footfall peaks by zone and hour.
3. Read recommended stall positions (advisory only).

### 14.3 Citizen flow (post-MVP)
1. Enter a route.
2. See predicted congestion windows and alternative routes.

---

## 15. Screens (MVP)

1. **Home / Map**: Pune map with zones, layer toggles, timeline slider, risk legend.
2. **Zone detail panel**: predictions, uncertainty band, drivers, actions.
3. **What-If**: lever controls, scenario name, baseline vs scenario comparison, score.
4. **Advisor**: chat input, cited answers, saved answers.
5. **Action plan**: table of zone, time window, action, owner, expected impact; export buttons.
6. **Signals**: social-signal counts per zone with category filters (no raw personal text).
7. **Methodology**: data sources, model cards, limitations, licences.
8. **Settings (admin)**: fusion weights, thresholds, data refresh status.

---

## 16. API (MVP Outline)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/zones | List zones with geometry and metadata |
| GET | /api/predictions?zone=&from=&to=&layer= | Predictions for zone and time range |
| GET | /api/risk?from=&to= | Fused risk per zone per hour |
| POST | /api/scenarios | Create scenario with lever values |
| GET | /api/scenarios/{id} | Scenario results and comparison |
| GET | /api/signals?zone=&category= | Aggregated social signal counts |
| POST | /api/advisor/query | Question to advisor; returns answer with citations |
| GET | /api/action-plan?event=&format=pdf|csv | Action plan export |
| GET | /api/health | Service and data freshness status |

Auth: none for public demo read-only endpoints; admin endpoints protected by token.
Rate limits: 60 requests per minute per IP for public endpoints.

---

## 17. Database Schema (Core Tables)

| Table | Key columns | Notes |
|---|---|---|
| zones | zone_id (PK), name, geom (PostGIS), zone_type | Zone register |
| road_segments | segment_id (PK), zone_id (FK), geom, road_class, lanes, capacity_proxy | From OSM |
| raw_sources | source_id, fetched_at, checksum, path | Ingest log |
| aqi_readings | zone_id, ts, pm25, pm10, aqi, source | Cleaned hourly |
| weather_hourly | zone_id, ts, temp, rain_mm, wind_speed, wind_dir | Cleaned hourly |
| events | event_id, name, date, route_geojson, immersion_point, notes, source_url | Festival schedule |
| predictions | run_id, zone_id, ts, crowd_idx, crowd_p10, crowd_p90, aqi_pred, waste_kg, congestion_prob | Model outputs |
| model_runs | run_id, model_name, version, data_version, commit, metrics_json, created_at | Versioning |
| scenarios | scenario_id, name, levers_json, created_at, share_token | What-if storage |
| scenario_results | scenario_id, zone_id, ts, metric, value, baseline_value | Comparison |
| signals | signal_id, zone_id, ts, category, source, anonymised_text | Social radar |
| shops | shop_id, zone_id, category, baseline_sales (nullable) | Business layer (sample) |
| action_plans | plan_id, scenario_id, zone_id, window, action, owner | Export source |

---

## 18. Evaluation and Testing

### 18.1 Model Evaluation
- Crowd and traffic: MAE, RMSE, and calibration of 80% intervals.
- AQI: MAE and bias; separate metrics for festival-day and non-festival-day.
- Waste: MAE and hotspot precision at top 10%.
- Social classifier: precision, recall, F1 per category.
- Baseline comparison is mandatory for every model.

### 18.2 Backtesting
- Use prior Ganesh festival years where data exists.
- Hold out the most recent year for final evaluation; do not tune on it.

### 18.3 Scenario Sanity Checks
- Diverting 100% of a corridor should not produce negative traffic.
- Adding waste points should not increase predicted waste.
- Rainfall increase should not increase predicted crowd, all else equal (unless a rule says otherwise, documented).

### 18.4 Software Tests
- Unit tests for feature functions and fusion logic.
- API contract tests.
- Playwright end-to-end tests for timeline, layer toggle, what-if, and export.
- Data-quality tests on every ingest run.

### 18.5 Human Validation
- Show outputs to at least two people with local knowledge (for example, a volunteer or a shop owner) and record their corrections.

---

## 19. Success Metrics

| Metric | Target (MVP) |
|---|---|
| Model MAE improvement vs baseline | At least 15% |
| Zone-hour hotspot precision (top 10%) | At least 0.6 |
| Advisor answers with valid citations | At least 95% on test questions |
| Dashboard load time | Under 3 seconds |
| Scenario recomputation time | Under 5 seconds |
| User test satisfaction (5 testers) | At least 4 of 5 "useful" rating |

---

## 20. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Sparse historical crowd labels | Weak crowd model | Use proxies, manual counts, media estimates; state uncertainty clearly |
| Traffic data is paid or restricted | Weak traffic model | Use OSM-based proxy and congestion labels from manual sampling; document |
| Social data restrictions | Signal radar incomplete | Use news RSS and permitted sources; mark sample size |
| Synthetic data mistaken for real | Credibility loss | Mandatory labels; methodology page |
| Overclaiming causal effects | Misleading decisions | Use "associated with" language; show limitations |
| Festival dates change | Wrong schedule | Manual event verification; event table with source links |
| Scope creep | MVP not delivered | Lock MVP scope in Section 5 and Section 3.2 |
| LLM hallucination | Wrong advice | Retrieval-only answers; citation checks; refusal rules |
| Privacy concerns | Reputational or legal risk | Aggregate-only outputs; anonymisation; no individual tracking |

---

## 21. Ethics and Responsible Use

- The system is advisory. It does not control traffic, deployments, or emergency services.
- Predictions must not be used to exclude or target any community or religious group.
- Crowd and safety outputs are aggregated by zone, never by individual.
- The product should avoid framing festivals as problems. It supports safer and cleaner celebration.
- Data sources and licences must be credited.

---

## 22. Phased Roadmap

| Phase | Weeks | Deliverables |
|---|---|---|
| P0: Scope and data audit | 1 | Zone map, data source audit, licence check, event verification list |
| P1: Data pipeline | 2 | Ingest jobs, cleaning, zone-hour table, data-quality tests |
| P2: Models v1 | 3 | Crowd, traffic, AQI, waste baseline and LightGBM models; metrics report |
| P3: Map and timeline | 4 | Next.js map, zone panel, timeline slider, layer toggles |
| P4: What-if and score | 5 | Scenario engine, comparison view, Sustainability Score |
| P5: Advisor and export | 6 | RAG advisor with citations, action-plan PDF and CSV |
| P6: Hardening and demo | 7 | Tests, methodology page, docker-compose, demo script, pitch deck |

Hackathon mode: compress into 3 to 4 days by keeping only the map, timeline, one what-if lever (diversion %), the advisor, and two models (crowd and AQI). Use synthetic-but-labelled data for the gaps.

---

## 23. Deliverables

1. Source code repository with README and docker-compose
2. Data dictionary and source register
3. Model cards for each model
4. Evaluation report with baseline comparisons
5. Methodology and limitations page (in-app)
6. Action-plan sample (PDF and CSV)
7. Demo video (3 to 5 minutes)
8. Pitch deck (8 to 10 slides)

---

## 24. Pitch Summary

**Problem:** Indian festivals create sudden, large pressure on cities, and planning is reactive.

**Solution:** FestivalPulse is a city digital twin that predicts crowd, traffic, air quality, and waste for festivals, lets planners test scenarios, and recommends concrete actions.

**Demo line:** "We do not just predict that air quality will worsen. We show where to send cleaning crews, how to divert traffic, and how to reduce the festival's environmental cost, without reducing its energy."

---

## 25. Glossary

- **AQI**: Air Quality Index. PM2.5 and PM10 are the main pollutants modelled.
- **Digital twin**: A live computational model of a real system used for prediction and simulation.
- **Visarjan**: The immersion of Ganesh idols at the end of the festival.
- **Zone**: A cluster of road segments and land parcels used as the main spatial unit.
- **What-if simulator**: Tool that recomputes predictions after changing scenario levers.
- **RAG**: Retrieval-Augmented Generation. The advisor answers from retrieved data and documents.
- **MAE**: Mean Absolute Error.
- **Holdout set**: Data kept aside for final evaluation.

---

## 26. Open Questions

1. Which municipal datasets (waste, cleanup logs, traffic counts) can be obtained through official or academic requests?
2. Is a permitted social API available for the MVP, or will we rely on news and manual samples?
3. Who will verify the event schedule and route data before the demo?
4. Should the Sustainability Score weights be validated with a sanitation or environment expert?
5. Is the demo expected to be offline (no live APIs) for judges?

---

## 27. Document Map (for the planned folder)

This REQ.md is the consolidated source. It can be split into the planned files as follows:

| File | Content from this document |
|---|---|
| core-idea.md | Sections 1, 2, 24 |
| PRD.md | Sections 3 to 7, 14, 15, 19 |
| TRD.md | Sections 8 to 13, 16, 17, 18 |
| architecture.md | Section 9 |
| api-architecture.md | Section 16 |
| backendschema.md | Section 17 |
| Appflow.md | Sections 14, 15 |
| how-it-works.md | Sections 6, 10, 11, 12, 13 |
| ideaplan.md | Sections 22, 23 |
| implementation-plan.md | Sections 18, 22 |
| AGENTS.md | Sections 3.2, 9.2, 21 (rules for the coding assistant) |
| CONTRIBUTING.md | Section 18, data honesty rules (8.2) |
| README.md | Sections 1, 5, 9.3, 23 |

---

*End of REQ.md*