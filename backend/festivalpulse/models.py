"""Crowd and AQI models (REQ §10.1, §10.3) with 80% intervals and baseline comparison.

HistGradientBoosting is used in place of LightGBM (same algorithm family, already installed).
"""
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from .data import FEATURES_AQI, FEATURES_CROWD, history_table

FESTIVAL_WEIGHT = 10  # festival rows are the target domain but ~10% of training rows


class QuantileModel:
    def __init__(self, features):
        self.features = features
        # point forecast uses squared error (beat quantile-0.5 loss on holdout); p10/p90 give the 80% interval
        # chosen on a 2024 validation year (train 2022-23), never on the 2025 holdout (REQ §18.2)
        kw = dict(max_iter=300, learning_rate=0.05, min_samples_leaf=40, random_state=0)
        self.models = {"p10": HistGradientBoostingRegressor(loss="quantile", quantile=0.1, **kw),
                       "p50": HistGradientBoostingRegressor(**kw),
                       "p90": HistGradientBoostingRegressor(loss="quantile", quantile=0.9, **kw)}
        self.margin = 0.0  # conformal margin added to both interval ends, set by calibrate()

    def fit(self, df, target):
        w = np.where(df["is_festival"] == 1, FESTIVAL_WEIGHT, 1)
        for m in self.models.values():
            m.fit(df[self.features], df[target], sample_weight=w)
        self.means = df[df["is_festival"] == 0][self.features].mean()
        return self

    def predict(self, df):
        out = {k: m.predict(df[self.features]) for k, m in self.models.items()}
        mid = out["p50"]
        lo, hi = np.minimum(out["p10"], mid), np.maximum(out["p90"], mid)
        return mid, lo - self.margin, hi + self.margin

    def calibrate(self, df, target, coverage=0.8):
        """Conformalized quantile regression: margin = finite-sample quantile of max(lo - y, y - hi)."""
        y = df[target].to_numpy()
        self.margin = 0.0
        _, lo, hi = self.predict(df)
        scores = np.maximum(lo - y, y - hi)
        self.margin = float(np.quantile(scores, min(1.0, np.ceil((len(y) + 1) * coverage) / len(y))))
        return self.margin

    def drivers(self, row, top=3):
        """Occlusion attribution: swap each feature to its ordinary-day mean and measure the change."""
        base = self.models["p50"].predict(row[self.features])[0]
        deltas = {}
        for f in self.features:
            alt = row[self.features].copy()
            alt[f] = self.means[f]
            deltas[f] = base - self.models["p50"].predict(alt)[0]
        return sorted(({"feature": f, "contribution": round(float(v), 3)} for f, v in deltas.items()),
                      key=lambda d: -abs(d["contribution"]))[:top]


def train(df, holdout_year=None):
    """Train on all years before the holdout; report MAE vs seasonal-naive (previous festival year)."""
    holdout_year = holdout_year or df["year"].max()
    train_df, test_df = df[df["year"] < holdout_year], df[(df["year"] == holdout_year) & (df["is_festival"] == 1)]
    crowd = QuantileModel(FEATURES_CROWD).fit(train_df, "crowd_idx")
    aqi = QuantileModel(FEATURES_AQI).fit(train_df, "aqi")
    # calibrate interval width on the year before the holdout (fit on earlier years), so the holdout stays untouched
    cal_year = holdout_year - 1
    cal_df = df[(df["year"] == cal_year) & (df["is_festival"] == 1)]
    for model, feats, target in ((crowd, FEATURES_CROWD, "crowd_idx"), (aqi, FEATURES_AQI, "aqi")):
        model.margin = QuantileModel(feats).fit(df[df["year"] < cal_year], target).calibrate(cal_df, target)

    prev = df[(df["year"] == holdout_year - 1) & (df["is_festival"] == 1)].set_index(["zone_id", "h"])
    naive = prev.loc[list(zip(test_df["zone_id"], test_df["h"]))]
    metrics = {}
    for name, model, target in (("crowd", crowd, "crowd_idx"), ("aqi", aqi, "aqi")):
        mid, lo, hi = model.predict(test_df)
        mae, base = mean_absolute_error(test_df[target], mid), mean_absolute_error(test_df[target], naive[target])
        y = test_df[target].to_numpy()
        metrics[name] = {"mae": round(mae, 4), "baseline_mae": round(base, 4),
                         "improvement_pct": round(100 * (1 - mae / base), 1),
                         "interval_coverage_80": round(float(np.mean((y >= lo) & (y <= hi))), 3),
                         "interval_margin": round(model.margin, 3),
                         "holdout_year": int(holdout_year), "baseline": "seasonal-naive (same zone-hour, previous festival)"}
    # refit on everything for serving; the lag feature's reference table travels with the model
    crowd_all = QuantileModel(FEATURES_CROWD).fit(df, "crowd_idx")
    crowd_all.history = history_table(df, df["year"].max())
    aqi_all = QuantileModel(FEATURES_AQI).fit(df, "aqi")
    crowd_all.margin, aqi_all.margin = crowd.margin, aqi.margin
    return crowd_all, aqi_all, metrics
