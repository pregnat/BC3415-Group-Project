"""Shared data shapes between layers. FROZEN once the team signs off.

Changing a field here breaks someone else's code: open a PR, tag both
other teammates, and update tests/test_contracts.py in the same PR.

Owners:  A = data + engine   B = RAG + eval   C = agent + app
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# --- A: engine ------------------------------------------------------------

MarginStatusCode = Literal["OK", "BELOW_MAINTENANCE", "BELOW_SOFT_EDGE"]
# none      -> equity >= maintenance requirement
# after_48h -> below maintenance for < 48h; liquidation possible once 48h passes
# anytime   -> below maintenance for >= 48h; liquidation can happen at any time
# immediate -> below soft edge; liquidation can happen immediately
LiquidationRisk = Literal["none", "after_48h", "anytime", "immediate"]


@dataclass
class PriceQuote:
    ticker: str
    price: float
    currency: str  # "SGD" | "USD" | "HKD"
    as_of: datetime
    source: str  # e.g. "snapshot:price_snapshot.parquet"


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
    margin_loan: float
    equity: float  # = market_value - margin_loan
    initial_requirement: float
    maintenance_requirement: float
    soft_edge_requirement: float
    status: MarginStatusCode
    liquidation_risk: LiquidationRisk
    hours_below_maintenance: float  # 0 if not below
    shortfall_to_maintenance: float  # 0 if not below; amount of equity needed
    shortfall_to_soft_edge: float
    soft_edge_uplift_applied: bool  # True if pre-weekend/holiday uplift is in effect
    positions: list[PositionMargin] = field(default_factory=list)


# --- B: RAG ---------------------------------------------------------------


@dataclass
class Chunk:
    chunk_id: str  # stable, e.g. "margin-call-faq#3"
    text: str
    title: str  # help-centre article title
    url: str  # canonical moomoo SG help-centre URL, used for citations
    score: float  # higher = more relevant


# --- C: escalation --------------------------------------------------------

EscalationReason = Literal["liquidation_dispute", "extension_request", "other"]


@dataclass
class EscalationCase:
    case_id: str
    account_id: str
    reason: EscalationReason
    customer_message: str
    summary: str  # structured summary written by the agent for the risk desk
    margin_snapshot: MarginStatus | None
    cited_chunk_ids: list[str]
    created_at: datetime
