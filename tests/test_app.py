"""OWNER: C. The app renders without an API key; no message is sent, so nothing is called."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from agent.escalation import create_case, list_cases
from agent.tools import run_tool
from contracts import AgentResponse
from engine.margin import margin_status, weekend_risk_check

APP_DIR = Path(__file__).resolve().parents[1] / "app"
APP = str(APP_DIR / "streamlit_app.py")
RISK_DESK = str(APP_DIR / "risk_desk.py")


def _run(account_id=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    if account_id:
        at.sidebar.selectbox[0].select(account_id).run()
    return at


def _text(elements):
    return " ".join(e.value for e in elements)


def test_app_starts_with_account_card_and_cases():
    at = _run()
    assert not at.exception
    assert {"Equity", "Maintenance", "Soft edge"} <= {m.label for m in at.main.metric}
    assert any("risk desk cases" in e.label for e in at.sidebar.expander)


def test_account_card_shows_the_engine_numbers():
    at = _run("M-003")
    status = margin_status("M-003")
    metrics = {m.label: m.value for m in at.main.metric}
    assert metrics["Equity"] == f"{status.equity:,.2f}"
    assert metrics["Maintenance"] == f"{status.mm_req:,.2f}"
    assert metrics["Hours below"] == f"{status.hours_below_mm:,.0f}"
    assert "Below maintenance" in _text(at.main.markdown)


def test_account_card_says_how_old_the_prices_are():
    assert "Prices from the 02 Nov snapshot, 3 trading sessions old." in _text(_run().main.caption)


def test_negative_equity_is_described_not_given_as_a_percentage():
    at = _run("M-008")
    assert not at.exception
    assert "Below soft edge" in _text(at.main.markdown)
    assert "-20%" not in str(at.main)


def test_weekend_alert_only_for_accounts_that_would_breach():
    assert "Weekend alert" not in _text(_run("M-001").warning)
    alert = _text(_run("M-003").warning)
    r = weekend_risk_check("M-003")
    assert "Weekend alert" in alert and f"{r.shortfall_to_se_raised:,.2f}" in alert
    assert "Mon 09 Nov 14:30 UTC" in alert


def test_what_if_slider_runs_the_engine():
    at = _run("M-003")
    at.sidebar.slider(key="shock_M-003_NVDA").set_value(-8).run()
    metrics = {m.label: m.value for m in at.sidebar.metric}
    assert metrics["Equity after the move"] == "806.41"  # S3: NVDA -8%
    assert "raised pre-weekend soft edge" in _text(at.sidebar.error)


def test_talk_to_a_human_opens_a_case():
    at = _run("M-006")
    at.sidebar.button[0].click().run()
    assert "opened" in _text(at.sidebar.success)
    assert list_cases("M-006")[0]["reason"] == "other"


def test_suggested_questions_fit_the_account():
    assert "If NVDA drops 8%" in str(_run("M-003").main)
    assert "Should I sell TSLA to fix this?" in str(_run("M-008").main)


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
    assert "matches the margin engine" in _text(at.main.caption)
    assert "1,500.00" in _text(at.main.warning)


def test_risk_desk_page_lists_cases():
    create_case("M-003", "liquidation_dispute", "I want compensation.", "Dispute over a forced sale.")
    at = AppTest.from_file(RISK_DESK, default_timeout=60).run()
    assert not at.exception
    assert at.dataframe and any("Liquidation dispute" in e.label for e in at.expander)


def test_risk_desk_page_with_no_cases():
    at = AppTest.from_file(RISK_DESK, default_timeout=60).run()
    assert not at.exception and at.info
