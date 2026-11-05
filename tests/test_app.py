"""OWNER: C. The app renders without an API key; no message is sent, so nothing is called."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from engine.margin import margin_status

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


def _run(account_id=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    if account_id:
        at.sidebar.selectbox[0].select(account_id).run()
    return at


def test_app_starts_with_gauge_and_cases():
    at = _run()
    assert not at.exception
    labels = [m.label for m in at.sidebar.metric]
    assert {"Equity", "Maintenance", "Soft edge"} <= set(labels)
    assert any(e.label.startswith("Risk desk cases") for e in at.sidebar.expander)


def test_gauge_shows_the_engine_numbers():
    at = _run("M-003")
    status = margin_status("M-003")
    metrics = {m.label: m.value for m in at.sidebar.metric}
    assert metrics["Equity"] == f"{status.equity:,.2f}"
    assert metrics["Maintenance"] == f"{status.mm_req:,.2f}"
    assert metrics["Hours below"] == f"{status.hours_below_mm:,.0f}"
