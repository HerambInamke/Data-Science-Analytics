"""REQ §18.4 end-to-end tests: timeline, layer toggle, what-if, export, driven in a real browser.

Needs `pip install playwright && python -m playwright install chromium`, plus network for the MapLibre script;
skipped when Playwright is missing.
"""
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "FESTIVALPULSE_DB": os.path.join(tempfile.mkdtemp(), "e2e.db")}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "festivalpulse.main:app", "--port", str(port)],
                            cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(240):  # startup trains the models
            try:
                urllib.request.urlopen(url + "/api/health", timeout=1)
                break
            except OSError:
                if proc.poll() is not None:
                    pytest.fail("server exited during startup")
                time.sleep(0.5)
        else:
            pytest.fail("server did not start in 120 s")
        yield url
    finally:
        proc.terminate()
        proc.wait()


@pytest.fixture(scope="module")
def chromium():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def ui(chromium, server_url):
    ctx = chromium.new_context(accept_downloads=True)
    pg = ctx.new_page()
    pg.route("https://tile.openstreetmap.org/**", lambda r: r.abort())  # tiles are decoration; keep tests off OSM's servers
    pg.goto(server_url)
    sync_api.expect(pg.locator(".zlabel").first).to_be_visible(timeout=30_000)
    yield pg
    ctx.close()


def test_timeline_slider_updates_hour_and_labels(ui):
    n_zones = len(ui.evaluate("zones.features"))
    ui.locator("#hour").fill("0")
    sync_api.expect(ui.locator("#hourLabel")).to_have_text("06:00")
    sync_api.expect(ui.locator(".zlabel")).to_have_count(n_zones)
    ui.locator("#hour").fill("23")
    sync_api.expect(ui.locator("#hourLabel")).to_have_text("05:00")


def test_layer_toggle_changes_legend_and_values(ui):
    ui.select_option("#layer", "aqi_pred")
    sync_api.expect(ui.locator("#legend")).to_contain_text("150+")
    # AQI labels are whole numbers, risk labels are decimals
    sync_api.expect(ui.locator(".zlabel").first).to_have_text(re.compile(r"^Z\d+ \d+$"))


def test_whatif_creates_shareable_scenario(ui):
    ui.get_by_role("tab", name="What-if").click()
    ui.locator("#sname").fill("Full diversion")
    ui.locator("#dpct").fill("100")
    ui.locator("#run").click()
    sync_api.expect(ui.locator("#whatifOut")).to_contain_text("Sustainability Score", timeout=30_000)
    sid = ui.locator("#scenario").input_value()
    assert sid != "baseline"
    assert ui.evaluate("location.hash") == f"#scenario={sid}"
    # shared link reopens the same scenario
    ui.goto(ui.url.split("#")[0] + f"#scenario={sid}")
    ui.reload()
    sync_api.expect(ui.locator("#scenario")).to_have_value(sid, timeout=30_000)


def test_action_plan_csv_and_pdf_export(ui):
    ui.get_by_role("tab", name="Plan").click()
    sync_api.expect(ui.locator("#planOut tr").nth(1)).to_be_visible()
    with ui.expect_download() as d:
        ui.locator("#csv").click()
    assert Path(d.value.path()).read_text(encoding="utf-8").startswith("zone_id,zone,window,action,owner,expected_impact")
    with ui.expect_download() as d:
        ui.locator("#pdf").click()
    assert Path(d.value.path()).read_bytes().startswith(b"%PDF")
