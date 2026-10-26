"""Scenario engine: model outputs -> zone x hour metrics, fused risk, sustainability score, action plan.

REQ §10.2, §10.4, §10.6, §10.7, §11, §12. Every rule-based coefficient here is an
"assumed effect" (REQ §11) until real data calibrates it; see ASSUMPTIONS.
"""
import numpy as np
import pandas as pd

from .data import clock_hour, features, lookup_history, scenario_day
from .zones import ZONE_BY_ID, ZONES, neighbours

RISK_WEIGHTS = {"crowd": 0.30, "traffic": 0.25, "aqi": 0.20, "waste": 0.15, "emergency": 0.10}
SCORE_WEIGHTS = {"emissions": 20, "waste": 20, "traffic_delay": 15, "crowd_safety": 20, "economic": 15, "water": 10}
HIGH_CROWD = 0.75
ASSUMPTIONS = {
    "traffic": "congestion = sigmoid(8*(load-0.6) + 0.1*rain); load = 0.6*crowd + 0.4*time-of-day traffic",
    "diversion": "diverted load on the corridor is split equally onto its 2 nearest zones (shortest-path proxy)",
    "aqi_exhaust": "AQI changes by 20 points per unit change in traffic load after diversion",
    "waste": "0.02 kg per person-hour + 15 kg per stall per day; each collection point clears 1500 kg/day",
    "toilets": "one mobile toilet serves ~5000 person-hours of pressure",
    "emergency": "incidents/hour = 3*crowd^2 + 0.5*congestion",
    "sales": "stall baseline INR 5000/day; uplift = 1.5 x mean crowd index (range 1.0-2.0)",
}
DEFAULT_LEVERS = {"diversion_pct": 0, "diversion_zone": "Z03", "start_shift_h": 0, "rain_override_mm": None,
                  "extra_waste_points": {}, "extra_toilets": {}}


def hour_label(h):
    return f"{clock_hour(h):02d}:00"


def validate_levers(levers):
    lv = {**DEFAULT_LEVERS, **(levers or {})}
    if not 0 <= float(lv["diversion_pct"]) <= 100:
        raise ValueError("diversion_pct must be 0-100")
    if lv["diversion_zone"] not in ZONE_BY_ID:
        raise ValueError("unknown diversion_zone")
    if not -6 <= int(lv["start_shift_h"]) <= 6:
        raise ValueError("start_shift_h must be between -6 and 6")
    if lv["rain_override_mm"] is not None and not 0 <= float(lv["rain_override_mm"]) <= 100:
        raise ValueError("rain_override_mm must be 0-100")
    for key in ("extra_waste_points", "extra_toilets"):
        for z, n in lv[key].items():
            if z not in ZONE_BY_ID or not 0 <= int(n) <= 50:
                raise ValueError(f"{key}: unknown zone or count out of range 0-50")
    return lv


def simulate(crowd_model, aqi_model, levers=None, day=None):
    lv = validate_levers(levers)
    day = day or scenario_day()
    rain, temp, wind, prev = day["rain"], day["temp"], day["wind"], day["aqi_prev"]
    if lv["rain_override_mm"] is not None:
        rain = np.full(len(rain), float(lv["rain_override_mm"]))
    df = pd.concat([features(z, rain, temp, wind, True, int(lv["start_shift_h"]), prev) for z in ZONES], ignore_index=True)
    cf = pd.concat([features(z, rain, temp, wind, False, aqi_prev=prev) for z in ZONES], ignore_index=True)
    df["hist_crowd"], cf["hist_crowd"] = lookup_history(df, crowd_model.history), lookup_history(cf, crowd_model.history)

    mid, lo, hi = crowd_model.predict(df)
    df["crowd_idx"], df["crowd_p10"], df["crowd_p90"] = (np.clip(a, 0, 1) for a in (mid, lo, hi))
    cf["crowd_idx"] = np.clip(crowd_model.predict(cf)[0], 0, 1)

    # traffic load and diversion
    ch = df["clock_hour"].to_numpy()
    rush = np.exp(-((ch - 9) ** 2) / 4) + np.exp(-((ch - 19) ** 2) / 4)
    df["load"] = 0.6 * df["crowd_idx"] + 0.4 * (0.3 + 0.3 * rush)
    load0 = df["load"].copy()
    d = float(lv["diversion_pct"]) / 100
    if d:
        corridor = df["zone_id"] == lv["diversion_zone"]
        moved = df.loc[corridor, "load"].to_numpy() * d
        df.loc[corridor, "load"] -= moved
        for n in neighbours(lv["diversion_zone"]):
            df.loc[df["zone_id"] == n, "load"] += moved / 2
    df["congestion_prob"] = 1 / (1 + np.exp(-(8 * (df["load"] - 0.6) + 0.1 * df["rain_mm"])))

    mid, lo, hi = aqi_model.predict(df)
    exhaust = 20 * (df["load"] - load0)
    df["aqi_pred"], df["aqi_p10"], df["aqi_p90"] = mid + exhaust, lo + exhaust, hi + exhaust
    df["aqi_uplift"] = df["aqi_pred"] - aqi_model.predict(cf)[0]

    z = df["zone_id"].map(ZONE_BY_ID)
    df["persons"] = df["crowd_idx"] * z.map(lambda r: r["capacity_persons"])
    df["waste_kg"] = df["persons"] * 0.02 + z.map(lambda r: r["stalls"]) * 15 / 24
    toilets = z.map(lambda r: r["toilets"]) + df["zone_id"].map(lambda i: int(lv["extra_toilets"].get(i, 0)))
    df["sanitation_risk"] = df["crowd_idx"] * np.minimum(1, df["persons"] / (toilets * 5000))
    df["emergency_per_h"] = 3 * df["crowd_idx"] ** 2 + 0.5 * df["congestion_prob"]

    df["risk"] = (RISK_WEIGHTS["crowd"] * df["crowd_idx"] + RISK_WEIGHTS["traffic"] * df["congestion_prob"]
                  + RISK_WEIGHTS["aqi"] * np.clip((df["aqi_pred"] - 50) / 250, 0, 1)
                  + RISK_WEIGHTS["waste"] * np.clip(df["waste_kg"] / 1500, 0, 1)
                  + RISK_WEIGHTS["emergency"] * np.clip(df["emergency_per_h"] / 3.5, 0, 1))
    df["hour"] = df["h"].map(hour_label)
    return df, zone_summary(df, lv), lv


def zone_summary(df, lv):
    g = df.groupby("zone_id")
    s = pd.DataFrame({"waste_kg_day": g["waste_kg"].sum(), "peak_crowd": g["crowd_idx"].max(),
                      "mean_crowd": g["crowd_idx"].mean(), "peak_risk": g["risk"].max()})
    points = pd.Series({i: ZONE_BY_ID[i]["waste_points"] + int(lv["extra_waste_points"].get(i, 0)) for i in s.index})
    s["collection_capacity_kg"] = points * 1500
    s["uncollected_kg"] = np.maximum(0, s["waste_kg_day"] - s["collection_capacity_kg"])
    s["hotspot"] = (s["waste_kg_day"] >= s["waste_kg_day"].quantile(0.9)).astype(int)
    ghat = pd.Series({i: ZONE_BY_ID[i]["zone_type"] == "ghat" for i in s.index})
    s["river_load_kg"] = s["uncollected_kg"] * np.where(ghat, 0.4, 0.05)
    base_sales = pd.Series({i: ZONE_BY_ID[i]["stalls"] * 5000 for i in s.index})
    s["sales_uplift_inr"] = base_sales * 1.5 * s["mean_crowd"]
    return s


def sustainability(df, zs):
    comps = {
        "emissions": 1 - (df["load"] * (1 + df["congestion_prob"])).sum() / (2 * len(df)),
        "waste": 1 - zs["uncollected_kg"].sum() / zs["waste_kg_day"].sum(),
        "traffic_delay": 1 - df["congestion_prob"].mean(),
        "crowd_safety": (df["crowd_idx"] < HIGH_CROWD).mean(),
        "economic": zs["sales_uplift_inr"].sum() / (1.5 * sum(z["stalls"] * 5000 for z in ZONES)),
        "water": 1 - zs["river_load_kg"].sum() / zs["waste_kg_day"].sum(),
    }
    comps = {k: round(100 * float(np.clip(v, 0, 1)), 1) for k, v in comps.items()}
    total = round(sum(comps[k] * w for k, w in SCORE_WEIGHTS.items()) / 100, 1)
    return {"score": total, "components": comps, "weights": SCORE_WEIGHTS,
            "note": "Planning aid, not an official rating."}


def _window(sub, mask):
    hs = sub.loc[mask, "h"]
    return f"{hour_label(hs.min())}-{hour_label(hs.max() + 1)}" if len(hs) else None


def action_plan(df, zs):
    rules = [
        ("crowd_idx", 0.7, "Deploy volunteers and barricades; open alternate exits", "Police + mandal volunteers",
         lambda s: f"peak crowd index {s['crowd_idx'].max():.2f}"),
        ("congestion_prob", 0.7, "Restrict vehicle entry and activate diversions", "Traffic police",
         lambda s: f"peak congestion probability {s['congestion_prob'].max():.2f}"),
        ("sanitation_risk", 0.5, "Place extra mobile toilets", "PMC sanitation",
         lambda s: f"peak sanitation risk {s['sanitation_risk'].max():.2f}"),
        ("aqi_pred", 200, "Water sprinkling on dusty stretches; mask advisory for vulnerable groups", "PMC environment cell",
         lambda s: f"peak AQI {s['aqi_pred'].max():.0f}"),
    ]
    plan = []
    for zid, sub in df.groupby("zone_id"):
        for col, thr, action, owner, impact in rules:
            w = _window(sub, sub[col] > thr)
            if w:
                plan.append({"zone_id": zid, "zone": ZONE_BY_ID[zid]["name"], "window": w, "action": action,
                             "owner": owner, "expected_impact": impact(sub)})
        z = zs.loc[zid]
        if z["uncollected_kg"] > 0 or z["hotspot"]:
            peak = sub.nlargest(6, "waste_kg")
            plan.append({"zone_id": zid, "zone": ZONE_BY_ID[zid]["name"], "window": _window(sub, sub["h"].isin(peak["h"])),
                         "action": f"Pre-position waste trucks; add {int(np.ceil(z['uncollected_kg'] / 1500))} collection points",
                         "owner": "PMC sanitation",
                         "expected_impact": f"{z['uncollected_kg']:.0f} kg/day otherwise uncollected"})
    return plan
