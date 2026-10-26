"""AI City Advisor, retrieval-only (REQ §13).

shortcut: keyword intent routing over prediction tables, no LLM. Every answer is
built from retrieved rows, so citations are exact. Swap in an LLM with tool calls
over these same retrieval functions when an API key and budget are available.
"""
import re

from .engine import hour_label
from .zones import ZONE_BY_ID

OUT_OF_SCOPE = re.compile(r"\b(close|block|shut|arrest|dispatch|order|deploy now)\b", re.I)
NIGHT = list(range(14, 21))  # 20:00-02:00 on the event timeline
INTENTS = [
    (r"toilet|sanitation|loo", "sanitation_risk", "sanitation risk", NIGHT),
    (r"waste|garbage|dustbin|truck|clean", "waste_kg", "waste generation (kg/h)", None),
    (r"aqi|air|pollution|smoke", "aqi_pred", "predicted AQI", None),
    (r"traffic|congest|divert|road", "congestion_prob", "congestion probability", None),
    (r"emergency|medical|ambulance|incident", "emergency_per_h", "estimated incidents per hour", None),
    (r"crowd|safe|people|footfall|vendor|stall", "crowd_idx", "crowd density index", None),
    (r"risk|where|worst|hotspot", "risk", "combined risk score", None),
]


def _cite(run_id, row):
    return {"table": "predictions", "run_id": run_id, "zone_id": row["zone_id"], "hour": row["hour"]}


def answer(question, df, run_id, plan=None):
    q = question.strip()
    if not q:
        return {"answer": "Please ask a question.", "citations": []}
    if OUT_OF_SCOPE.search(q):
        return {"answer": "FestivalPulse is advisory and cannot issue operational commands. "
                          "Please contact Pune Traffic Police or PMC control room for that.", "citations": []}
    if re.search(r"action|recommend|what should|top 3|plan", q, re.I) and plan:
        risk = df.groupby("zone_id")["risk"].max()
        top, seen = [], set()
        for p in sorted(plan, key=lambda p: -risk[p["zone_id"]]):  # first action of each highest-risk zone
            if p["zone_id"] not in seen:
                seen.add(p["zone_id"])
                top.append(p)
        top = top[:3]
        lines = [f"{i + 1}. {p['zone']} ({p['window']}): {p['action']}, {p['expected_impact']}." for i, p in enumerate(top)]
        return {"answer": "Top 3 recommended actions (planning suggestions):\n" + "\n".join(lines),
                "citations": [{"table": "action_plans", "run_id": run_id, "zone_id": p["zone_id"], "window": p["window"]}
                              for p in top]}
    for pattern, col, label, hours in INTENTS:
        if re.search(pattern, q, re.I):
            sub = df[df["h"].isin(hours)] if hours else df
            top = sub.sort_values(col, ascending=False).drop_duplicates("zone_id").head(3)
            window = f" between {hour_label(hours[0])} and {hour_label(hours[-1] + 1)}" if hours else ""
            lines = []
            for i, r in enumerate(top.to_dict("records")):
                ci = f" (crowd 80% CI {r['crowd_p10']:.2f}-{r['crowd_p90']:.2f})"
                lines.append(f"{i + 1}. {ZONE_BY_ID[r['zone_id']]['name']} at {r['hour']}: {label} {r[col]:.2f}, "
                             f"crowd index {r['crowd_idx']:.2f}{ci}.")
            return {"answer": f"Top 3 zones by {label}{window}:\n" + "\n".join(lines)
                              + "\nThis is a planning suggestion based on synthetic-trained models.",
                    "citations": [_cite(run_id, r) for r in top.to_dict("records")]}
    return {"answer": "I don't have data to answer that. I can answer about crowd, traffic, AQI, waste, "
                      "sanitation, emergency load, combined risk, or recommended actions.", "citations": []}
