# FestivalPulse demo script (4 minutes)

For the demo video (REQ §23 item 7). Start the app (`docker compose up` or `python -m uvicorn festivalpulse.main:app` in `backend/`), open http://localhost:8000, and have a second tab ready on the Method tab. Read numbers off the screen; they change when the data is re-ingested.

| Time | Screen | Do | Say |
|---|---|---|---|
| 0:00 | Header | Point at the title and the data badge. | "Every Ganesh Visarjan, Pune's centre takes lakhs of people in one night. Planning today is reactive. FestivalPulse is a digital twin of that night: crowd, traffic, air quality and waste, per zone and per hour. The badge says which data is real: weather and city AQI are real, crowd is synthetic and labelled." |
| 0:25 | Map, Combined risk | Drag the timeline from 14:00 to 22:00. | "This is combined risk by zone. Watch the core light up as processions converge after dark. Values are printed on each zone, so colour is never the only cue." |
| 0:50 | Map, layer toggle | Switch the layer to Crowd, then AQI, then Business (footfall). | "Same timeline, different lens. AQI includes the festival uplift over a no-festival counterfactual. Vendors get the footfall view." |
| 1:15 | Zone tab | Click the highest-risk zone. | "Per zone: prediction, an 80% interval calibrated on the previous year, the top crowd drivers, and the actions triggered for this hour. The crowd model beats a seasonal-naive baseline by more than 15% MAE; the evaluation is on the Method tab." |
| 1:45 | What-if tab | Name it "Full diversion", set diversion to 100% on Z03, add 5 waste points and 5 toilets in the hottest zone, Run. | "Now the planner asks: what if we divert this corridor and add waste and toilet points?" |
| 2:10 | What-if result | Point at the Sustainability Score delta, uncollected waste before/after, zone deltas. | "Score versus baseline, with the breakdown, and where risk moved. The scenario has a shareable link." |
| 2:35 | Advisor tab | Ask the default question: "Where should PMC place mobile toilets during Visarjan night?" | "The advisor answers only from model outputs, and cites the table and run. Ask it to close a road and it refuses and points to the authority." Optionally type "close Laxmi Road now" to show the refusal. |
| 3:05 | Plan tab | Show the action table, click Download PDF. | "The output is a per-zone action plan with owner and expected impact, as CSV or PDF for the morning briefing." |
| 3:25 | Signals tab | Show the posts-per-zone bars and the Spearman check. | "Social signals are geocoded to zones after PII masking, and checked against predicted crowd." |
| 3:40 | Method tab | Scroll datasets, metrics, limitations. | "Everything synthetic is labelled, every assumption is listed. These are planning aids, not orders." |
| 3:50 | Map | Back to the map at 22:00. | "We do not just predict that air quality will worsen. We show where to send cleaning crews, how to divert traffic, and how to reduce the festival's environmental cost, without reducing its energy." |

## Before recording

- `python -m pytest -q` in `backend/` is green, including the browser tests in `tests/test_e2e.py`.
- Clear old scenarios (delete `backend/data/festivalpulse.db`) so the scenario dropdown only shows Baseline.
- Browser at 1440×900, zoom 100%, dark OS theme to match the UI.
- If the network is down, map tiles will not load; the zones, values and every tab still work.
