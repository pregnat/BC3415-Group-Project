"""Shared data shapes between layers, matching section 3 of the project plan.
FROZEN once the team signs off.

Changing a field here breaks someone else's code: open a PR, tag both
other teammates, and update tests/test_contracts.py in the same PR.

Owners:  A = data + engine   B = RAG + eval   C = agent + app
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

# --- A: engine ------------------------------------------------------------

MarginStatusCode = Literal["healthy", "below_mm", "below_se"]
# none      -> equity >= maintenance requirement
# after_48h -> below maintenance for < 48h; liquidation possible once 48h passes
# anytime   -> below maintenance for >= 48h or for an unknown time; liquidation can happen at any time
# immediate -> below soft edge; liquidation can happen immediately
LiquidationRisk = Literal["none", "after_48h", "anytime", "immediate"]


@dataclass
class Position:
    ticker: str
    qty: float
    avg_cost: float


@dataclass
class Account:
    account_id: str  # "M-001" ... "M-010"
    currency: str  # one currency per account; mixed USD/SGD is a stretch goal
    cash: float
    margin_loan: float
    positions: list[Position] = field(default_factory=list)


@dataclass
class PriceQuote:
    ticker: str
    price: float
    currency: str  # "SGD" | "USD" | "HKD"
    timestamp: datetime
    source: str  # "moomoo", "yfinance", or "snapshot:<original source>"


@dataclass
class PositionMargin:
    ticker: str
    quantity: float
    price: float
    market_value: float
    initial_ratio: float  # e.g. 0.40
    maintenance_ratio: float  # e.g. 0.30
    soft_edge_ratio: float  # e.g. 0.20 (after any weekend/holiday uplift)
    ratio_source: str  # "assumption_table" until we have real per-stock rates


@dataclass
class MarginStatus:
    account_id: str
    as_of: datetime
    currency: str
    market_value: float
    cash: float
    margin_loan: float
    equity: float  # = market_value + cash - margin_loan
    im_req: float
    mm_req: float
    se_req: float
    status: MarginStatusCode
    liquidation_risk: LiquidationRisk
    hours_below_mm: float | None  # 0 if not below; None if below but the start time isn't recorded
    shortfall_to_mm: float  # 0 if not below; amount of equity needed
    shortfall_to_se: float
    soft_edge_uplift_applied: bool  # True if pre-weekend/holiday uplift is in effect
    positions: list[PositionMargin] = field(default_factory=list)


@dataclass
class LiquidationDistance:
    pct_drop_to_mm: float  # uniform drop across all positions; 0 if already below, 1 if unreachable
    pct_drop_to_se: float
    stressed_market_value: float  # after shocks; current value if shocks is None
    stressed_equity: float
    binding_position: str  # ticker with the largest stressed market value


@dataclass
class WeekendRisk:
    is_pre_weekend: bool
    se_ratio_now: float
    se_ratio_raised: float
    equity: float  # after shocks, if any
    se_req_raised: float  # requirement at se_ratio_raised, after shocks, if any
    would_breach: bool  # is_pre_weekend and equity < se_req_raised


# --- B: RAG ---------------------------------------------------------------


@dataclass
class Chunk:
    chunk_id: str  # stable, e.g. "topic5_493#0"
    text: str
    title: str  # help-centre article title
    url: str  # canonical moomoo SG help-centre URL, used for citations
    date: str  # ISO date we fetched it; help-centre pages show no publish date
    product: str  # "securities_margin" | "forex_cfd" | "futures" | "options" | ...
    score: float  # cosine similarity, higher = more relevant


# --- C: agent + escalation ------------------------------------------------

EscalationReason = Literal["liquidation_dispute", "extension_request", "other"]


@dataclass
class EscalationCase:
    case_id: str
    account_id: str
    reason: EscalationReason
    customer_message: str
    summary: str  # structured summary written by the agent for the risk desk
    timeline: list[str]  # what happened and when, as far as the customer has said
    rule_cited: str  # the help-centre rule the case turns on
    margin_snapshot: MarginStatus | None
    cited_chunk_ids: list[str]
    created_at: datetime


@dataclass
class AgentResponse:
    answer: str
    citations: list[dict[str, str]]  # [{"chunk_id", "title", "url"}] cited in the answer
    tools_called: list[dict[str, Any]]  # [{"name", "input", "output", "is_error"}]
    escalate: bool
    case_summary: dict[str, Any] | None  # the EscalationCase as JSON if escalate is True
