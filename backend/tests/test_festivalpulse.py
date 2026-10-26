import pytest
from fastapi.testclient import TestClient

from festivalpulse import engine
from festivalpulse.main import app


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
