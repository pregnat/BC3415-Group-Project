"""Margin engine. OWNER: A.

Rules (moomoo SG help centre):
  equity = total market value - margin loan
  below maintenance for > 48h  -> liquidation can happen at any time
  below soft edge              -> liquidation can happen immediately
  soft edge may be raised before weekends/holidays (see engine/calendar.py)
Ratios come from data/margin_ratios.csv (documented assumptions, see docs/assumptions.md).
"""
from __future__ import annotations

from datetime import datetime

from contracts import MarginStatus, PositionMargin


def compute_margin_status(account_id: str, as_of: datetime | None = None) -> MarginStatus:
    # TODO(A): replace stub with real calculation from accounts.db + prices + ratios.
    as_of = as_of or datetime(2026, 11, 6, 15, 0)
    positions = [
        PositionMargin("D05.SI", 1000, 38.0, 38000.0, 0.40, 0.30, 0.20, "assumption_table"),
        PositionMargin("NVDA", 100, 120.0, 12000.0, 0.50, 0.40, 0.30, "assumption_table"),
    ]
    mv = sum(p.market_value for p in positions)
    loan = 36000.0
    maint = sum(p.market_value * p.maintenance_ratio for p in positions)
    soft = sum(p.market_value * p.soft_edge_ratio for p in positions)
    equity = mv - loan
    return MarginStatus(
        account_id=account_id,
        as_of=as_of,
        currency="SGD",
        market_value=mv,
        margin_loan=loan,
        equity=equity,
        initial_requirement=sum(p.market_value * p.initial_ratio for p in positions),
        maintenance_requirement=maint,
        soft_edge_requirement=soft,
        status="BELOW_MAINTENANCE",
        liquidation_risk="after_48h",
        hours_below_maintenance=20.0,
        shortfall_to_maintenance=max(0.0, maint - equity),
        shortfall_to_soft_edge=max(0.0, soft - equity),
        soft_edge_uplift_applied=False,
        positions=positions,
    )
