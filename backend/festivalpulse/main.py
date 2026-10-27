"""FastAPI layer (REQ §16). Run: uvicorn festivalpulse.main:app --reload (from backend/)."""
import csv
import hashlib
import json
import io
import os
import secrets
import subprocess
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fpdf import FPDF
import pandas as pd
from pydantic import BaseModel

from . import advisor, engine, signals, store
from .data import DATA_LABEL, DATASETS, generate, scenario_day
from .ingest import RAW
from .models import train
from .zones import ZONE_BY_ID, geojson

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
PRED_COLS = ["zone_id", "h", "hour", "crowd_idx", "crowd_p10", "crowd_p90", "congestion_prob", "aqi_pred", "aqi_p10",
             "aqi_p90", "aqi_uplift", "waste_kg", "sanitation_risk", "emergency_per_h", "persons", "risk"]

STATE = {}
SCENARIOS = {}  # served results; inputs persist in store.scenarios and are re-simulated on startup


def _run(levers=None):
    df, zs, lv = engine.simulate(STATE["crowd"], STATE["aqi"], levers, STATE["day"])
    return {"df": df, "zs": zs, "levers": lv, "score": engine.sustainability(df, zs), "plan": engine.action_plan(df, zs)}


def _data_version():
    try:
        return hashlib.sha256((RAW / "sources.json").read_bytes()).hexdigest()[:12]
    except OSError:
        return "synthetic-only"


def _commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5,
                              cwd=FRONTEND.parent).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return os.environ.get("FESTIVALPULSE_COMMIT", "unknown")


@asynccontextmanager
async def lifespan(_app):
    db = STATE["db"] = store.connect()
    saved = store.load_settings(db)  # applied before any run so the baseline uses them
    engine.RISK_WEIGHTS.update(saved.get("risk_weights", {}))
    engine.ACTION_THRESHOLDS.update(saved.get("action_thresholds", {}))
    data = generate()
    STATE["crowd"], STATE["aqi"], STATE["metrics"] = train(data)
    store.log_model_runs(db, STATE["metrics"], _data_version(), _commit())
    STATE["day"] = scenario_day()
    STATE["weather_real_share"] = round(float(data["weather_real"].mean()), 3)
    STATE["trained_at"] = time.time()
    SCENARIOS.clear()
    SCENARIOS["baseline"] = {"name": "Baseline", **_run()}
    # shortcut: every saved scenario is re-simulated at startup (~0.1 s each); cache results if this grows to hundreds
    for sid, name, levers in store.load_scenarios(db):
        try:
            SCENARIOS[sid] = {"name": name, **_run(levers)}
        except (ValueError, TypeError, AttributeError):
            pass  # levers no longer valid under current rules; keep the row, skip serving it
    STATE["signal_clf"], STATE["signal_metrics"] = signals.train_classifier()
    STATE["signals"] = signals.demo_feed(STATE["signal_clf"]) + store.load_signals(db)
    yield  # db stays open: every write commits immediately, process exit closes it


app = FastAPI(title="FestivalPulse API", lifespan=lifespan)


_hits = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        q, now = _hits[request.client.host if request.client else "?"], time.time()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= 60:
            return JSONResponse({"detail": "rate limit: 60 requests/minute"}, status_code=429)
        q.append(now)
    return await call_next(request)


def _scenario(sid):
    if sid not in SCENARIOS:
        raise HTTPException(404, "scenario not found")
    return SCENARIOS[sid]


@app.get("/")
def index():
    return FileResponse(FRONTEND)


@app.get("/api/zones")
def zones():
    return geojson()


@app.get("/api/predictions")
def predictions(zone: str | None = None, layer: str | None = None, scenario: str = "baseline"):
    df = _scenario(scenario)["df"]
    if zone:
        df = df[df["zone_id"] == zone]
    cols = PRED_COLS if not layer else ["zone_id", "h", "hour", layer]
    if layer and layer not in PRED_COLS:
        raise HTTPException(400, f"unknown layer; choose from {PRED_COLS[3:]}")
    return {"run_id": scenario, "data_label": DATA_LABEL, "rows": df[cols].round(3).to_dict("records")}


@app.get("/api/risk")
def risk(scenario: str = "baseline"):
    return predictions(layer="risk", scenario=scenario)


@app.get("/api/zones/{zone_id}")
def zone_detail(zone_id: str, h: int = 14, scenario: str = "baseline"):
    if zone_id not in ZONE_BY_ID or not 0 <= h < 24:
        raise HTTPException(404, "unknown zone or hour")
    s = _scenario(scenario)
    df = s["df"]
    row = df[(df["zone_id"] == zone_id) & (df["h"] == h)]
    return {"zone": ZONE_BY_ID[zone_id], "run_id": scenario, "data_label": DATA_LABEL,
            "prediction": row[PRED_COLS].round(3).to_dict("records")[0],
            "drivers": STATE["crowd"].drivers(row),
            "summary": s["zs"].loc[zone_id].round(1).to_dict(),
            "actions": [p for p in s["plan"] if p["zone_id"] == zone_id]}


class ScenarioIn(BaseModel):
    name: str = "Untitled scenario"
    levers: dict = {}


def _compare(sid):
    s, b = _scenario(sid), SCENARIOS["baseline"]
    metrics = ["crowd_idx", "congestion_prob", "aqi_pred", "waste_kg", "risk", "sanitation_risk"]
    delta = (s["df"].groupby("zone_id")[metrics].mean() - b["df"].groupby("zone_id")[metrics].mean()).round(3)
    return {"scenario_id": sid, "name": s["name"], "levers": s["levers"], "score": s["score"],
            "baseline_score": b["score"], "zone_deltas": delta.reset_index().to_dict("records"),
            "uncollected_kg": {"scenario": round(s["zs"]["uncollected_kg"].sum()),
                               "baseline": round(b["zs"]["uncollected_kg"].sum())},
            "assumed_effects": engine.ASSUMPTIONS, "data_label": DATA_LABEL}


@app.post("/api/scenarios")
def create_scenario(body: ScenarioIn):
    try:
        run = _run(body.levers)
    except (ValueError, TypeError, AttributeError) as e:
        raise HTTPException(422, str(e))
    sid = uuid.uuid4().hex[:8]
    SCENARIOS[sid] = {"name": body.name[:80], **run}
    store.save_scenario(STATE["db"], sid, body.name[:80], body.levers)
    return _compare(sid)


@app.get("/api/scenarios/{sid}")
def get_scenario(sid: str):
    return _compare(sid)


class Question(BaseModel):
    question: str
    scenario_id: str = "baseline"


@app.post("/api/advisor/query")
def advisor_query(body: Question):
    s = _scenario(body.scenario_id)
    return advisor.answer(body.question[:500], s["df"], body.scenario_id, s["plan"])


@app.get("/api/action-plan")
def action_plan(scenario: str = "baseline", format: str = "json"):
    plan = _scenario(scenario)["plan"]
    if format == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["zone_id", "zone", "window", "action", "owner", "expected_impact"])
        w.writeheader()
        w.writerows(plan)
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=action-plan-{scenario}.csv"})
    if format == "pdf":
        return Response(plan_pdf(plan, _scenario(scenario)["name"]), media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=action-plan-{scenario}.pdf"})
    return {"run_id": scenario, "plan": plan}


def plan_pdf(plan, name):
    """FR-6.2 PDF export. Core PDF fonts are Latin-1 only, so other characters are replaced."""
    clean = lambda t: str(t).encode("latin-1", "replace").decode("latin-1")
    pdf = FPDF(orientation="landscape")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, clean(f"FestivalPulse action plan - Ganesh Visarjan, Pune - {name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=8)
    pdf.multi_cell(0, 4, clean(f"Data: {DATA_LABEL}. Planning suggestions only; not operational orders. "
                               "Generated " + time.strftime("%Y-%m-%d %H:%M")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    with pdf.table(col_widths=(14, 50, 22, 80, 40, 60), text_align="LEFT") as t:
        t.row(["Zone", "Name", "Window", "Action", "Owner", "Expected impact"])
        for a in plan:
            t.row([clean(a[k]) for k in ("zone_id", "zone", "window", "action", "owner", "expected_impact")])
    return bytes(pdf.output())


def _admin(token):
    want = os.environ.get("FESTIVALPULSE_ADMIN_TOKEN")
    if not want or not secrets.compare_digest(token or "", want):
        raise HTTPException(401, "admin token required (set FESTIVALPULSE_ADMIN_TOKEN, send X-Admin-Token)")


@app.get("/api/signals")
def get_signals(zone: str | None = None, category: str | None = None):
    """FR-3.4: aggregated counts only (no raw text), compared with predicted peak crowd per zone."""
    if category and category not in signals.CATEGORIES:
        raise HTTPException(400, f"unknown category; choose from {signals.CATEGORIES}")
    rows = [s for s in STATE["signals"] if s["zone_id"] and (not zone or s["zone_id"] == zone)]
    counts = {z: dict.fromkeys(signals.CATEGORIES, 0) for z in ZONE_BY_ID if not zone or z == zone}
    for s in rows:
        counts[s["zone_id"]][s["category"]] += 1
    peak = SCENARIOS["baseline"]["df"].groupby("zone_id")["crowd_idx"].max()
    pressure = {z: c["TOO_CROWDED"] + c["TRAFFIC_SLOW"] + c["ROUTE_BLOCKED"] for z, c in counts.items()}
    rho = None
    if len(counts) > 2:
        rho = round(float(peak[list(pressure)].rank().corr(pd.Series(pressure).rank())), 3)
    return {"data_label": signals.SIGNALS_LABEL, "category": category,
            "zones": [{"zone_id": z, "name": ZONE_BY_ID[z]["name"], "counts": c,
                       "total": c[category] if category else sum(c.values()),
                       "pressure_signals": pressure[z], "predicted_peak_crowd": round(float(peak[z]), 3)}
                      for z, c in counts.items()],
            "unlocated": sum(1 for s in STATE["signals"] if not s["zone_id"]),
            "validation": {"spearman_pressure_vs_predicted_crowd": rho,
                           "note": "Pressure = TOO_CROWDED + TRAFFIC_SLOW + ROUTE_BLOCKED posts; association only."},
            "classifier_metrics": STATE["signal_metrics"]}


class SignalsIn(BaseModel):
    texts: list[str]


@app.post("/api/signals")
def upload_signals(body: SignalsIn, x_admin_token: str | None = Header(None)):
    """FR-3.1 manual upload of permitted public text; PII is masked before storage (FR-3.5)."""
    _admin(x_admin_token)
    if len(body.texts) > 1000:
        raise HTTPException(413, "max 1000 texts per upload")
    added = signals.ingest(STATE["signal_clf"], body.texts)
    STATE["signals"].extend(added)
    store.save_signals(STATE["db"], added, "manual upload")
    return {"added": len(added), "located": sum(1 for a in added if a["zone_id"]),
            "categories": {c: sum(a["category"] == c for a in added) for c in signals.CATEGORIES}}


THRESHOLD_RANGE = {"crowd_idx": (0, 1), "congestion_prob": (0, 1), "sanitation_risk": (0, 1), "aqi_pred": (0, 500)}


def _settings():
    return {"risk_weights": engine.RISK_WEIGHTS, "action_thresholds": engine.ACTION_THRESHOLDS,
            "threshold_ranges": THRESHOLD_RANGE, "models_trained_at": STATE.get("trained_at"),
            "weather_real_share": STATE.get("weather_real_share"), "raw_sources": _source_log(),
            "signals_stored": len(STATE.get("signals", [])), "scenarios_in_memory": len(SCENARIOS)}


@app.get("/api/admin/settings")
def get_settings(x_admin_token: str | None = Header(None)):
    _admin(x_admin_token)
    return _settings()


class SettingsIn(BaseModel):
    risk_weights: dict[str, float] | None = None
    action_thresholds: dict[str, float] | None = None


@app.put("/api/admin/settings")
def put_settings(body: SettingsIn, x_admin_token: str | None = Header(None)):
    """Screen 8: change fusion weights / action thresholds, then recompute every stored scenario."""
    _admin(x_admin_token)
    w, t = body.risk_weights, body.action_thresholds
    if w is not None:
        if set(w) != set(engine.RISK_WEIGHTS) or min(w.values()) < 0 or abs(sum(w.values()) - 1) > 0.01:
            raise HTTPException(422, f"risk_weights need keys {sorted(engine.RISK_WEIGHTS)}, each >= 0, summing to 1")
    if t is not None:
        bad = [k for k, v in t.items() if k not in THRESHOLD_RANGE or not THRESHOLD_RANGE[k][0] <= v <= THRESHOLD_RANGE[k][1]]
        if bad:
            raise HTTPException(422, f"invalid thresholds {bad}; ranges {THRESHOLD_RANGE}")
    engine.RISK_WEIGHTS.update(w or {})
    engine.ACTION_THRESHOLDS.update(t or {})
    store.save_settings(STATE["db"], {"risk_weights": engine.RISK_WEIGHTS, "action_thresholds": engine.ACTION_THRESHOLDS})
    for sid, s in list(SCENARIOS.items()):
        SCENARIOS[sid] = {"name": s["name"], **_run(s["levers"])}
    return _settings()


@app.get("/api/health")
def health():
    # NFR-5: anything below 1.0 means some days fell back to synthetic weather; the UI shows a badge
    return {"status": "ok" if STATE else "starting", "data_label": DATA_LABEL,
            "scenario_weather": STATE["day"]["label"] if STATE else None,
            "weather_real_share": STATE.get("weather_real_share"),
            "models_trained_at": STATE.get("trained_at"), "metrics": STATE.get("metrics"),
            "model_runs": store.model_runs(STATE["db"], 2) if "db" in STATE else []}


def _source_log():
    try:
        return json.loads((RAW / "sources.json").read_text())
    except (OSError, ValueError):
        return []


@app.get("/api/methodology")
def methodology():
    return {"data_label": DATA_LABEL, "datasets": DATASETS, "scenario_weather": STATE["day"]["label"],
            "raw_sources": _source_log(), "metrics": STATE["metrics"], "assumptions": engine.ASSUMPTIONS,
            "risk_weights": engine.RISK_WEIGHTS, "score_weights": engine.SCORE_WEIGHTS,
            "limitations": ["Crowd labels are synthetic; no observed footfall data is used yet.",
                            "City AQI is a modelled CAMS grid value (24h-averaged US AQI), not a station reading; "
                            "zone-to-zone AQI differences are synthetic.",
                            "Zone boundaries are approximate hexagons around hand-picked centroids.",
                            "Traffic, waste, sanitation and sales are rule-based with assumed coefficients.",
                            "Social signals are synthetic template posts; the classifier's held-out scores are near "
                            "perfect only because test posts share the templates. Real accuracy needs >=300 hand-labelled "
                            "real posts (REQ section 10.5).",
                            "Associations only; no causal claims.", "Advisory only; not an official rating."],
            "sources": ["OpenStreetMap tiles (ODbL), attribution required",
                        "Weather data by Open-Meteo.com (CC BY 4.0), ERA5 reanalysis",
                        "Air quality data by Open-Meteo.com (CC BY 4.0), CAMS"]}
