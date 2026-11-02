"""Contract tests: every layer returns the frozen shapes in contracts.py.
These must keep passing when stubs are replaced with real code."""
import json

import pytest

from agent.tools import TOOLS, run_tool
from contracts import Account, Chunk, LiquidationDistance, MarginStatus, PriceQuote, WeekendRisk
from engine.margin import get_account, liquidation_distance, margin_status, weekend_risk_check
from engine.prices import get_prices
from rag.retriever import retrieve


def test_account_shape():
    account = get_account("M-003")
    assert isinstance(account, Account)
    assert account.positions and account.currency


@pytest.mark.parametrize("account_id", ["M-001", "M-003", "M-008"])
def test_margin_status_shape(account_id):
    s = margin_status(account_id)
    assert isinstance(s, MarginStatus)
    assert s.equity == s.market_value + s.cash - s.margin_loan
    assert s.status in ("healthy", "below_mm", "below_se")
    assert s.liquidation_risk in ("none", "after_48h", "anytime", "immediate")


def test_demo_scenario_accounts():
    """S2 needs M-003 below maintenance and S3 needs it to hold NVDA. S5 needs a TSLA holder: M-008."""
    assert margin_status("M-003").status == "below_mm"
    assert "NVDA" in {p.ticker for p in get_account("M-003").positions}
    assert "TSLA" in {p.ticker for p in get_account("M-008").positions}


def test_price_shape():
    quote = get_prices(["NVDA"])["NVDA"]
    assert isinstance(quote, PriceQuote)
    with pytest.raises(KeyError):
        get_prices(["NOPE"])


def test_liquidation_distance_shape():
    d = liquidation_distance("M-003", {"NVDA": -0.08})
    assert isinstance(d, LiquidationDistance)
    account = get_account("M-003")
    assert d.stressed_equity == d.stressed_market_value + account.cash - account.margin_loan
    assert d.stressed_equity < margin_status("M-003").equity


def test_weekend_risk_shape():
    r = weekend_risk_check("M-003", shocks={"NVDA": -0.08})
    assert isinstance(r, WeekendRisk)
    assert r.se_ratio_raised >= r.se_ratio_now
    assert r.would_breach == (r.equity < r.se_req_raised)


def test_retrieve_shape():
    chunks = retrieve("what happens below maintenance margin", k=2)
    assert chunks and all(isinstance(c, Chunk) for c in chunks)
    assert all(c.url and c.chunk_id and c.date and c.product for c in chunks)


def test_tool_output_has_no_float_noise():
    output = json.loads(run_tool("margin_status", {}, "M-003"))
    assert output["equity"] == 1137.4
    assert output["mm_req"] == 1241.22


def test_every_tool_dispatches():
    shocks = {"shocks": [{"ticker": "NVDA", "pct_change": -0.08}]}
    sample_args = {
        "margin_status": {},
        "liquidation_distance": shocks,
        "weekend_risk_check": shocks,
        "get_prices": {"tickers": ["NVDA"]},
        "search_help_centre": {"query": "soft edge"},
        "escalate_to_risk_desk": {
            "reason": "extension_request",
            "customer_message": "Can I get 2 more days?",
            "summary": "Customer below maintenance, requests extension.",
            "timeline": ["Fell below maintenance on 5 Nov."],
            "rule_cited": "Below maintenance for more than 48 hours.",
            "cited_chunk_ids": [],
        },
    }
    for tool in TOOLS:
        assert json.loads(run_tool(tool["name"], sample_args[tool["name"]], "M-003"))
