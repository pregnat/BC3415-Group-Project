"""OWNER: C. The app renders without an API key; no message is sent, so nothing is called."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from agent.escalation import create_case, list_cases
from agent.tools import run_tool
from contracts import AgentResponse
from engine.margin import margin_status, weekend_risk_check

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
RISK_DESK = str(Path(__file__).resolve().parents[1] / "app" / "pages" / "risk_desk.py")


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


def test_gauge_says_how_old_the_prices_are():
    captions = " ".join(c.value for c in _run().sidebar.caption)
    assert "Prices from the 02 Nov snapshot, 3 trading sessions old." in captions


def test_weekend_alert_only_for_accounts_that_would_breach():
    assert not [w for w in _run("M-001").warning if "Weekend alert" in w.value]
    alert = [w.value for w in _run("M-003").warning if "Weekend alert" in w.value]
    r = weekend_risk_check("M-003")
    assert alert and f"{r.shortfall_to_se_raised:,.2f}" in alert[0]
    assert "Mon 09 Nov 14:30 UTC" in alert[0]


def test_what_if_slider_runs_the_engine():
    at = _run("M-003")
    at.sidebar.slider(key="shock_M-003_NVDA").set_value(-8).run()
    metrics = {m.label: m.value for m in at.sidebar.metric}
    assert metrics["Equity after the move"] == "806.41"  # S3: NVDA -8%
    assert any("raised pre-weekend soft edge" in e.value for e in at.sidebar.error)


def test_talk_to_a_human_opens_a_case():
    at = _run("M-006")
    at.sidebar.button[0].click().run()
    assert any("opened" in s.value for s in at.sidebar.success)
    assert list_cases("M-006")[0]["reason"] == "other"


def test_answers_get_a_number_check_badge():
    output = run_tool("margin_status", {}, "M-003")
    call = {"name": "margin_status", "input": {}, "output": output, "is_error": False}
    good = AgentResponse("Your equity is 1,137.40.", [], [call], False, None)
    bad = AgentResponse("Your equity is 1,500.00.", [], [call], False, None)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["account_id"] = "M-001"
    at.session_state["api_messages"] = []
    at.session_state["turns"] = [
        ("user", "Am I at risk?", None), ("assistant", good.answer, good),
        ("user", "And now?", None), ("assistant", bad.answer, bad),
    ]
    at.run()
    assert any("matches the margin engine" in c.value for c in at.caption)
    assert any("1,500.00" in w.value for w in at.warning)


def test_risk_desk_page_lists_cases():
    create_case("M-003", "liquidation_dispute", "I want compensation.", "Dispute over a forced sale.")
    at = AppTest.from_file(RISK_DESK, default_timeout=60).run()
    assert not at.exception
    assert at.dataframe and any("liquidation_dispute" in e.label for e in at.expander)


def test_risk_desk_page_with_no_cases():
    at = AppTest.from_file(RISK_DESK, default_timeout=60).run()
    assert not at.exception and at.info
