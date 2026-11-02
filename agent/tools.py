"""Tool schemas + dispatch for the agent. OWNER: C.

account_id is bound from the logged-in session, never chosen by the model,
so a customer can't ask about someone else's account.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from agent.escalation import create_case
from engine.margin import liquidation_distance, margin_status, weekend_risk_check
from engine.prices import get_prices
from rag.retriever import retrieve

_SHOCKS_SCHEMA = {
    "type": "array",
    "description": "Hypothetical price moves to apply. Empty for current prices.",
    "items": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string"},
            "pct_change": {"type": "number", "description": "Fractional change, e.g. -0.08 for an 8% drop."},
        },
        "required": ["ticker", "pct_change"],
        "additionalProperties": False,
    },
}

TOOLS = [
    {
        "name": "margin_status",
        "description": (
            "Compute the logged-in customer's current margin status: market value, loan, "
            "equity, initial/maintenance/soft-edge requirements, shortfalls, hours below "
            "maintenance, liquidation risk, and per-position ratios."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "liquidation_distance",
        "description": (
            "How far prices can fall before the customer's account reaches maintenance and "
            "soft edge, and their equity after any hypothetical price moves."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"shocks": _SHOCKS_SCHEMA},
            "required": ["shocks"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "weekend_risk_check",
        "description": (
            "Whether a raised pre-weekend or pre-holiday soft edge would put the customer's "
            "account in breach, optionally after hypothetical price moves."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"shocks": _SHOCKS_SCHEMA},
            "required": ["shocks"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "get_prices",
        "description": "Latest snapshot prices for tickers, e.g. ['NVDA', 'TSLA'].",
        "input_schema": {
            "type": "object",
            "properties": {"tickers": {"type": "array", "items": {"type": "string"}}},
            "required": ["tickers"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "search_help_centre",
        "description": (
            "Search moomoo SG help-centre articles on securities margin rules. Returns chunks "
            "with chunk_id, title and url to cite, or an empty list if nothing relevant is found."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "escalate_to_risk_desk",
        "description": (
            "Open a case for the human risk desk. Use for liquidation disputes, extension "
            "requests, or anything needing human approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "enum": ["liquidation_dispute", "extension_request", "other"]},
                "customer_message": {"type": "string", "description": "The customer's request, verbatim."},
                "summary": {
                    "type": "string",
                    "description": "Concise case summary for the risk desk: situation, numbers, what the customer wants.",
                },
                "timeline": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "What happened and when, as far as the customer has said.",
                },
                "rule_cited": {"type": "string", "description": "The help-centre rule the case turns on."},
                "cited_chunk_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["reason", "customer_message", "summary", "timeline", "rule_cited", "cited_chunk_ids"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def _shocks(args: dict) -> dict[str, float] | None:
    return {s["ticker"]: s["pct_change"] for s in args["shocks"]} or None


def run_tool(name: str, args: dict, account_id: str) -> str:
    if name == "margin_status":
        result = margin_status(account_id)
    elif name == "liquidation_distance":
        result = liquidation_distance(account_id, _shocks(args))
    elif name == "weekend_risk_check":
        result = weekend_risk_check(account_id, shocks=_shocks(args))
    elif name == "get_prices":
        result = get_prices(args["tickers"])
    elif name == "search_help_centre":
        result = retrieve(args["query"])
    elif name == "escalate_to_risk_desk":
        result = create_case(account_id=account_id, **args)
    else:
        raise ValueError(f"Unknown tool: {name}")
    return _to_json(result)


def _to_json(obj) -> str:
    if isinstance(obj, list):
        obj = [asdict(o) for o in obj]
    elif isinstance(obj, dict):
        obj = {k: asdict(v) for k, v in obj.items()}
    else:
        obj = asdict(obj)
    return json.dumps(obj, default=str)
