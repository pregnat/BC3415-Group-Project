"""Tool schemas + dispatch for the agent. OWNER: C.

account_id is bound from the logged-in session, never chosen by the model,
so a customer can't ask about someone else's account.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from agent.escalation import create_case
from engine.margin import compute_margin_status
from engine.prices import get_price
from rag.retriever import search

TOOLS = [
    {
        "name": "get_margin_status",
        "description": (
            "Compute the logged-in customer's current margin status: market value, loan, "
            "equity, initial/maintenance/soft-edge requirements, shortfalls, hours below "
            "maintenance, liquidation risk, and per-position ratios."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "get_price",
        "description": "Latest snapshot price for one ticker, e.g. 'D05.SI' or 'NVDA'.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "search_help_centre",
        "description": (
            "Search moomoo SG help-centre articles on margin rules. Returns chunks with "
            "chunk_id, title and url to cite."
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
                "cited_chunk_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["reason", "customer_message", "summary", "cited_chunk_ids"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def run_tool(name: str, args: dict, account_id: str) -> str:
    if name == "get_margin_status":
        result = compute_margin_status(account_id)
    elif name == "get_price":
        result = get_price(args["ticker"])
    elif name == "search_help_centre":
        result = search(args["query"])
    elif name == "escalate_to_risk_desk":
        result = create_case(account_id=account_id, **args)
    else:
        raise ValueError(f"Unknown tool: {name}")
    return _to_json(result)


def _to_json(obj) -> str:
    if isinstance(obj, list):
        obj = [asdict(o) for o in obj]
    else:
        obj = asdict(obj)
    return json.dumps(obj, default=str)
