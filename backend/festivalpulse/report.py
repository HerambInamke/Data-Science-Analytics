"""Write docs/evaluation.md from a fresh training run (REQ §18, §23 item 4). Run: python -m festivalpulse.report"""
import time
from pathlib import Path

from .data import DATA_LABEL, generate
from .models import train
from .signals import SIGNALS_LABEL, train_classifier

OUT = Path(__file__).resolve().parents[2] / "docs" / "evaluation.md"


def _table(header, rows):
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] +
                     ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def render(metrics, clf_metrics):
    c, a = metrics["crowd"], metrics["aqi"]
    o = a["ordinary_days"]
    reg = _table(["Model", "Slice", "MAE", "Baseline MAE", "Gain", "RMSE", "Bias", "80% interval coverage", "Baseline"],
                 [["Crowd", "festival day", c["mae"], c["baseline_mae"], f"{c['improvement_pct']}%", c["rmse"], c["bias"],
                   c["interval_coverage_80"], c["baseline"]],
                  ["AQI", "festival day", a["mae"], a["baseline_mae"], f"{a['improvement_pct']}%", a["rmse"], a["bias"],
                   a["interval_coverage_80"], a["baseline"]],
                  ["AQI", f"ordinary days (n={o['n']})", o["mae"], o["baseline_mae"], f"{o['improvement_pct']}%", "-", o["bias"],
                   "-", o["baseline"]]])
    cls = _table(["Category", "Precision", "Recall", "F1", "n"],
                 [[k, m["precision"], m["recall"], m["f1"], m["n"]] for k, m in clf_metrics.items()])
    verdict = "met" if c["improvement_pct"] >= 15 else "NOT met"
    return f"""# Evaluation report

Generated {time.strftime("%Y-%m-%d")} by `python -m festivalpulse.report`. Do not edit by hand; rerun instead.

Data: {DATA_LABEL}. Holdout: the {c["holdout_year"]} festival, never used for tuning (REQ §18.2). Intervals are
calibrated on the year before the holdout.

## Crowd and AQI models (REQ §18.1)

{reg}

- NFR-3 (crowd beats seasonal-naive by at least 15% MAE): **{verdict}** ({c["improvement_pct"]}%). Crowd labels are
  synthetic, so this shows the pipeline works, not that it predicts real crowds.
- AQI on ordinary days is compared with same-hour-yesterday persistence. A negative gain means persistence wins; the
  model is trained to favour festival days (10x sample weight).
- Traffic, waste, sanitation and emergency are rule-based (assumptions on the Method tab), so they have no holdout
  metrics yet. Waste hotspot precision needs observed collection data.

## Social-risk classifier (REQ §10.5)

Data: {SIGNALS_LABEL}.

{cls}

These scores are inflated: test posts come from the same templates as training posts. A real evaluation needs at least
300 hand-labelled real posts.

## Scenario sanity checks (REQ §18.3)

Covered by `backend/tests`: full diversion never gives negative traffic, extra waste points never increase uncollected
waste, rain never increases crowd, a later start moves the peak later.
"""


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(train(generate())[2], train_classifier()[1]), encoding="utf-8")
    print(f"wrote {OUT}")
