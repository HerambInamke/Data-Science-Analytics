"""Persistence for what users create (REQ §17 table names). Derived outputs are recomputed on startup, not stored.

shortcut: SQLite file via stdlib, single process; move to Postgres/PostGIS when running more than one worker.
"""
import json
import os
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "festivalpulse.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (scenario_id TEXT PRIMARY KEY, name TEXT, levers_json TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS signals (signal_id INTEGER PRIMARY KEY, zone_id TEXT, ts REAL, category TEXT, source TEXT,
                                    anonymised_text TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value_json TEXT);
CREATE TABLE IF NOT EXISTS model_runs (run_id INTEGER PRIMARY KEY, model_name TEXT, version TEXT, data_version TEXT,
                                       "commit" TEXT, metrics_json TEXT, created_at REAL);
"""


def connect():
    path = Path(os.environ.get("FESTIVALPULSE_DB", DEFAULT_DB))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.executescript(SCHEMA)
    return db


def save_scenario(db, sid, name, levers):
    with db:
        db.execute("INSERT INTO scenarios VALUES (?, ?, ?, ?)", (sid, name, json.dumps(levers), time.time()))


def load_scenarios(db):
    return [(sid, name, json.loads(lv)) for sid, name, lv in
            db.execute("SELECT scenario_id, name, levers_json FROM scenarios ORDER BY created_at")]


def save_signals(db, rows, source):
    with db:
        db.executemany("INSERT INTO signals (zone_id, ts, category, source, anonymised_text) VALUES (?, ?, ?, ?, ?)",
                       [(r["zone_id"], time.time(), r["category"], source, r["text"]) for r in rows])


def load_signals(db):
    return [{"zone_id": z, "category": c, "text": t} for z, c, t in
            db.execute("SELECT zone_id, category, anonymised_text FROM signals ORDER BY signal_id")]


def save_settings(db, values):
    with db:
        db.executemany("INSERT OR REPLACE INTO settings VALUES (?, ?)", [(k, json.dumps(v)) for k, v in values.items()])


def load_settings(db):
    return {k: json.loads(v) for k, v in db.execute("SELECT key, value_json FROM settings")}


def log_model_runs(db, metrics, data_version, commit):
    """FR-8.3: one row per trained model with the input data version and code commit."""
    with db:
        db.executemany('INSERT INTO model_runs (model_name, version, data_version, "commit", metrics_json, created_at) '
                       "VALUES (?, ?, ?, ?, ?, ?)",
                       [(name, "v1", data_version, commit, json.dumps(m), time.time()) for name, m in metrics.items()])


def model_runs(db, limit=10):
    cols = ["run_id", "model_name", "version", "data_version", "commit", "metrics", "created_at"]
    rows = db.execute('SELECT run_id, model_name, version, data_version, "commit", metrics_json, created_at '
                      "FROM model_runs ORDER BY run_id DESC LIMIT ?", (limit,))
    return [dict(zip(cols, (*r[:5], json.loads(r[5]), r[6]))) for r in rows]
