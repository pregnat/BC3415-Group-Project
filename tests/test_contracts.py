"""Contract tests: every layer returns the frozen shapes in contracts.py.
These must keep passing when stubs are replaced with real code."""
from dataclasses import asdict

from agent.tools import TOOLS, run_tool
from contracts import Chunk, MarginStatus, PriceQuote
from engine.margin import compute_margin_status
from engine.prices import get_price
from rag.retriever import search


def test_margin_status_shape():
    s = compute_margin_status("ACC-001")
    assert isinstance(s, MarginStatus)
    assert s.equity == s.market_value - s.margin_loan
    assert s.status in ("OK", "BELOW_MAINTENANCE", "BELOW_SOFT_EDGE")
    assert s.liquidation_risk in ("none", "after_48h", "anytime", "immediate")


def test_price_shape():
    assert isinstance(get_price("D05.SI"), PriceQuote)


def test_search_shape():
    chunks = search("what happens below maintenance margin", k=2)
    assert chunks and all(isinstance(c, Chunk) for c in chunks)
    assert all(c.url and c.chunk_id for c in chunks)


def test_every_tool_dispatches():
    sample_args = {
        "get_margin_status": {},
        "get_price": {"ticker": "D05.SI"},
        "search_help_centre": {"query": "soft edge"},
        "escalate_to_risk_desk": {
            "reason": "extension_request",
            "customer_message": "Can I get 2 more days?",
            "summary": "Customer below maintenance, requests extension.",
            "cited_chunk_ids": [],
        },
    }
    for tool in TOOLS:
        assert run_tool(tool["name"], sample_args[tool["name"]], "ACC-001")
