"""FastAPI layer (REQ §16). Run: uvicorn festivalpulse.main:app --reload (from backend/)."""
import csv
import io
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from . import advisor, engine
from .data import DATA_LABEL, generate
from .models import train
from .zones import ZONE_BY_ID, geojson

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
PRED_COLS = ["zone_id", "h", "hour", "crowd_idx", "crowd_p10", "crowd_p90", "congestion_prob", "aqi_pred", "aqi_p10",
             "aqi_p90", "aqi_uplift", "waste_kg", "sanitation_risk", "emergency_per_h", "risk"]

STATE = {}
SCENARIOS = {}  # shortcut: in-memory, lost on restart; move to the scenarios table (Postgres) for sharing across restarts


def _run(levers=None):
    df, zs, lv = engine.simulate(STATE["crowd"], STATE["aqi"], levers)
    return {"df": df, "zs": zs, "levers": lv, "score": engine.sustainability(df, zs), "plan": engine.action_plan(df, zs)}


@asynccontextmanager
async def lifespan(_app):
    STATE["crowd"], STATE["aqi"], STATE["metrics"] = train(generate())
    STATE["trained_at"] = time.time()
    SCENARIOS["baseline"] = {"name": "Baseline", **_run()}
    yield


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
    return {"run_id": scenario, "plan": plan}


@app.get("/api/health")
def health():
    return {"status": "ok" if STATE else "starting", "data_label": DATA_LABEL,
            "models_trained_at": STATE.get("trained_at"), "metrics": STATE.get("metrics")}


@app.get("/api/methodology")
def methodology():
    return {"data_label": DATA_LABEL, "metrics": STATE["metrics"], "assumptions": engine.ASSUMPTIONS,
            "risk_weights": engine.RISK_WEIGHTS, "score_weights": engine.SCORE_WEIGHTS,
            "limitations": ["All training data is synthetic; no observed festival data is used yet.",
                            "Zone boundaries are approximate hexagons around hand-picked centroids.",
                            "Traffic, waste, sanitation and sales are rule-based with assumed coefficients.",
                            "Associations only; no causal claims.", "Advisory only; not an official rating."],
            "sources": ["OpenStreetMap tiles (ODbL), attribution required"]}
