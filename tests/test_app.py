"""OWNER: C. The app renders without an API key; no message is sent, so nothing is called.
The canvas is drawn as HTML, so checks look for the figures in the rendered markdown."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from agent.escalation import create_case, list_cases
from agent.tools import run_tool
from contracts import AgentResponse
from engine.margin import weekend_risk_check

APP_DIR = Path(__file__).resolve().parents[1] / "app"
APP = str(APP_DIR / "streamlit_app.py")
RISK_DESK = str(APP_DIR / "risk_desk.py")


def _run(account_id=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    if account_id:
        at.selectbox(key="account_id").select(account_id).run()
    return at


def _page(at) -> str:
    return " ".join(m.value for m in at.markdown)


def test_app_starts_on_m003_with_the_engine_numbers():
    at = _run()
    assert not at.exception
    page = _page(at)
    assert "$1,137.40" in page and "$1,241.22" in page and "$827.48" in page  # equity, maintenance, soft edge
    assert "173 h" in page


def test_switching_account_updates_the_canvas():
    at = _run("M-008")
    assert not at.exception
    assert "-$291.20" in _page(at)
    assert "Below soft edge" in _page(at)


def test_canvas_says_how_old_the_prices_are():
    assert "prices from the 02 Nov snapshot (3 trading sessions old)" in _page(_run())


def test_weekend_alert_only_for_accounts_that_would_breach():
    assert "Weekend alert" not in _page(_run("M-001"))
    page = _page(_run("M-003"))
    r = weekend_risk_check("M-003")
    assert "Weekend alert" in page and f"${r.shortfall_to_se_raised:,.2f}" in page
    assert "Mon 09 Nov 14:30 UTC" in page


def test_what_if_slider_runs_the_engine():
    at = _run()
    at.slider(key="shock_M-003_NVDA").set_value(-8).run()
    page = _page(at)
    assert "Equity after the move" in page and "$806.41" in page  # S3: NVDA -8%
    assert "below the raised pre-weekend soft edge" in page


def test_talk_to_a_human_opens_a_case_without_the_api():
    at = _run("M-006")
    next(b for b in at.button if "Talk to a human" in b.label).click().run()
    case = list_cases("M-006")[0]
    assert case["reason"] == "other"
    assert case["case_id"] in _page(at)


def test_answers_get_a_number_check_badge():
    output = run_tool("margin_status", {}, "M-003")
    call = {"name": "margin_status", "input": {}, "output": output, "is_error": False}
    good = AgentResponse("Your equity is 1,137.40.", [], [call], False, None)
    bad = AgentResponse("Your equity is 1,500.00.", [], [call], False, None)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["turns"] = [
        ("user", "Am I at risk?", None, None), ("assistant", good.answer, good, None),
        ("user", "And now?", None, None), ("assistant", bad.answer, bad, None),
    ]
    at.session_state["api_messages"] = []
    at.run()
    assert not at.exception
    assert any("matches the margin engine" in c.value for c in at.caption)
    assert any("1,500.00" in w.value for w in at.warning)


def test_risk_desk_page_lists_cases():
    create_case("M-003", "liquidation_dispute", "I want compensation.", "Dispute over a forced sale.")
    at = AppTest.from_file(RISK_DESK, default_timeout=60).run()
    assert not at.exception
    assert at.dataframe and any("Liquidation dispute" in e.label for e in at.expander)


def test_risk_desk_page_with_no_cases():
    at = AppTest.from_file(RISK_DESK, default_timeout=60).run()
    assert not at.exception and at.info
