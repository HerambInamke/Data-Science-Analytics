import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from festivalpulse import engine
from festivalpulse.main import app

os.environ["FESTIVALPULSE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")  # never touch the real DB


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def models(client):
    from festivalpulse.main import STATE
    return STATE["crowd"], STATE["aqi"], STATE["metrics"]


def run(models, **levers):
    df, zs, _ = engine.simulate(models[0], models[1], levers)
    return df, zs


def test_models_beat_seasonal_naive_by_15pct(models):  # NFR-3
    for name in ("crowd", "aqi"):
        assert models[2][name]["improvement_pct"] >= 15, models[2][name]


# REQ §18.3 scenario sanity checks
def test_full_diversion_never_negative(models):
    df, _ = run(models, diversion_pct=100, diversion_zone="Z03")
    assert (df["load"] >= 0).all() and (df["congestion_prob"] >= 0).all()
    base, _ = run(models)
    assert df[df.zone_id == "Z03"]["congestion_prob"].mean() < base[base.zone_id == "Z03"]["congestion_prob"].mean()


def test_waste_points_do_not_increase_uncollected(models):
    _, base = run(models)
    _, more = run(models, extra_waste_points={z: 5 for z in base.index})
    assert (more["uncollected_kg"] <= base["uncollected_kg"]).all()


def test_rain_does_not_increase_crowd(models):
    dry, _ = run(models, rain_override_mm=0)
    wet, _ = run(models, rain_override_mm=20)
    assert wet["crowd_idx"].mean() <= dry["crowd_idx"].mean()


def test_time_shift_moves_peak(models):
    base, _ = run(models)
    late, _ = run(models, start_shift_h=3)
    peak = lambda d: d[d.zone_id == "Z02"].sort_values("crowd_idx").iloc[-1]["h"]
    assert peak(late) > peak(base)


def test_invalid_levers_rejected(client):
    assert client.post("/api/scenarios", json={"levers": {"diversion_pct": 150}}).status_code == 422
    assert client.post("/api/scenarios", json={"levers": {"extra_toilets": {"Z99": 1}}}).status_code == 422


def test_score_in_range_and_breakdown(models):
    df, zs = run(models)
    s = engine.sustainability(df, zs)
    assert 0 <= s["score"] <= 100 and set(s["components"]) == set(engine.SCORE_WEIGHTS)


def test_api_flow(client):
    assert len(client.get("/api/zones").json()["features"]) == 10
    p = client.get("/api/predictions", params={"zone": "Z01"}).json()
    assert len(p["rows"]) == 24 and "synthetic crowd" in p["data_label"]
    r = client.post("/api/scenarios", json={"name": "FC divert", "levers": {"diversion_pct": 20}}).json()
    assert client.get(f"/api/scenarios/{r['scenario_id']}").status_code == 200
    d = client.get("/api/zones/Z04", params={"h": 15}).json()
    assert len(d["drivers"]) == 3
    assert client.get("/api/action-plan", params={"format": "csv"}).text.startswith("zone_id,zone,window")


def test_advisor_cites_and_refuses(client):
    a = client.post("/api/advisor/query", json={"question": "Where should PMC place mobile toilets during Visarjan night?"}).json()
    assert len(a["citations"]) == 3 and all(c["table"] == "predictions" for c in a["citations"])
    assert client.post("/api/advisor/query", json={"question": "close FC road now"}).json()["citations"] == []
    assert "don't have data" in client.post("/api/advisor/query", json={"question": "what is the GDP?"}).json()["answer"]
    top3 = client.post("/api/advisor/query", json={"question": "top 3 actions"}).json()
    assert len(top3["citations"]) == 3


def test_raw_files_match_logged_checksums():  # FR-8.1
    import hashlib, json
    from festivalpulse.ingest import RAW
    log = json.loads((RAW / "sources.json").read_text())
    assert len(log) == 8
    for e in log:
        assert hashlib.sha256((RAW / e["path"]).read_bytes()).hexdigest() == e["sha256"]


def test_real_inputs_used_and_fallback_when_missing(monkeypatch, tmp_path):  # NFR-5
    from festivalpulse import data, ingest
    assert data.scenario_day()["real"]
    monkeypatch.setattr(ingest, "RAW", tmp_path)  # no raw files -> synthetic fallback, labelled
    day = data.scenario_day()
    assert not day["real"] and "synthetic" in day["label"] and len(day["rain"]) == 24


def test_intervals_calibrated_on_holdout(models):  # FR-1.7, REQ §18.1 calibration
    for name in ("crowd", "aqi"):
        assert models[2][name]["interval_coverage_80"] >= 0.75, models[2][name]


def test_action_plan_pdf(client):  # FR-6.2
    r = client.get("/api/action-plan", params={"format": "pdf"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")


def test_business_layer_footfall(client):  # FR-1.6 / vendor flow
    rows = client.get("/api/predictions", params={"layer": "persons", "zone": "Z02"}).json()["rows"]
    assert len(rows) == 24 and max(r["persons"] for r in rows) > 0
    assert client.get("/api/zones/Z02").json()["summary"]["sales_uplift_inr"] > 0


def test_signal_pii_masked_and_geocoded():  # FR-3.3, FR-3.5
    from festivalpulse import signals
    t = signals.mask_pii("Crowd at Laxmi Road, call +91 98765 43210 or a@b.com @ravi https://x.co/1")
    assert "98765" not in t and "a@b.com" not in t and "@ravi" not in t and "x.co" not in t
    assert signals.geocode("jam near Sangam Bridge") == "Z05" and signals.geocode("nowhere known") is None


def test_signals_api(client, monkeypatch):  # FR-3.1, FR-3.2, FR-3.4, REQ §10.5
    d = client.get("/api/signals").json()
    assert len(d["zones"]) == 10 and "synthetic" in d["data_label"] and "text" not in d["zones"][0]
    assert sum(m["n"] for m in d["classifier_metrics"].values()) == 300
    assert all(m["recall"] >= 0.8 for m in d["classifier_metrics"].values())
    assert client.get("/api/signals", params={"category": "NOPE"}).status_code == 400
    texts = {"texts": ["Huge crowd at Deccan, can't move, ping 9876543210"]}
    assert client.post("/api/signals", json=texts).status_code == 401
    monkeypatch.setenv("FESTIVALPULSE_ADMIN_TOKEN", "t0ken")
    before = client.get("/api/signals", params={"zone": "Z03"}).json()["zones"][0]["counts"]["TOO_CROWDED"]
    r = client.post("/api/signals", json=texts, headers={"X-Admin-Token": "t0ken"}).json()
    assert r == {"added": 1, "located": 1, "categories": {**dict.fromkeys(r["categories"], 0), "TOO_CROWDED": 1}}
    from festivalpulse.main import STATE
    assert "9876543210" not in STATE["signals"][-1]["text"]
    assert client.get("/api/signals", params={"zone": "Z03"}).json()["zones"][0]["counts"]["TOO_CROWDED"] == before + 1


def test_admin_settings_recompute(client, monkeypatch):  # REQ §15 screen 8, §16 admin auth
    assert client.get("/api/admin/settings").status_code == 401
    monkeypatch.setenv("FESTIVALPULSE_ADMIN_TOKEN", "t0ken")
    h = {"X-Admin-Token": "t0ken"}
    s = client.get("/api/admin/settings", headers=h).json()
    w0, t0 = dict(s["risk_weights"]), dict(s["action_thresholds"])
    assert client.put("/api/admin/settings", json={"risk_weights": {"crowd": 2}}, headers=h).status_code == 422
    assert client.put("/api/admin/settings", json={"action_thresholds": {"aqi_pred": -1}}, headers=h).status_code == 422
    n0 = len(client.get("/api/action-plan").json()["plan"])
    try:
        only_crowd = dict.fromkeys(w0, 0) | {"crowd": 1}
        client.put("/api/admin/settings", json={"risk_weights": only_crowd, "action_thresholds": {"crowd_idx": 0.99}}, headers=h)
        rows = client.get("/api/predictions", params={"zone": "Z01"}).json()["rows"]
        assert all(abs(r["risk"] - r["crowd_idx"]) < 1e-3 for r in rows)
        assert len(client.get("/api/action-plan").json()["plan"]) < n0
    finally:
        client.put("/api/admin/settings", json={"risk_weights": w0, "action_thresholds": t0}, headers=h)
    assert len(client.get("/api/action-plan").json()["plan"]) == n0


def test_state_survives_restart(client, monkeypatch):  # REQ §17 scenarios/signals/settings, FR-8.3 model_runs
    from festivalpulse import engine
    monkeypatch.setenv("FESTIVALPULSE_ADMIN_TOKEN", "t0ken")
    h = {"X-Admin-Token": "t0ken"}
    sid = client.post("/api/scenarios", json={"name": "Kept", "levers": {"diversion_pct": 40}}).json()["scenario_id"]
    client.post("/api/signals", json={"texts": ["no dustbin at Camp, garbage everywhere"]}, headers=h)
    t0 = dict(engine.ACTION_THRESHOLDS)
    client.put("/api/admin/settings", json={"action_thresholds": {"aqi_pred": 180}}, headers=h)
    n_signals = client.get("/api/admin/settings", headers=h).json()["signals_stored"]
    try:
        engine.ACTION_THRESHOLDS["aqi_pred"] = 200  # simulate a fresh process: in-memory value lost
        with TestClient(app) as again:
            s = again.get(f"/api/scenarios/{sid}").json()
            assert s["name"] == "Kept" and s["levers"]["diversion_pct"] == 40
            assert again.get("/api/admin/settings", headers=h).json()["signals_stored"] == n_signals
            assert engine.ACTION_THRESHOLDS["aqi_pred"] == 180
            runs = again.get("/api/health").json()["model_runs"]
            assert len(runs) == 2 and runs[0]["data_version"] and runs[0]["commit"]
    finally:
        client.put("/api/admin/settings", json={"action_thresholds": t0}, headers=h)


def test_evaluation_report(models):  # REQ §18.1, §23 item 4
    from festivalpulse import report, signals
    md = report.render(models[2], signals.train_classifier()[1])
    assert "NFR-3" in md and "ordinary days" in md and "MEDICAL_HELP_NEEDED" in md
    assert models[2]["aqi"]["ordinary_days"]["n"] > 0 and "rmse" in models[2]["crowd"]
