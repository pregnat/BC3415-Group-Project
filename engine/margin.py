"""Margin engine. OWNER: A.

Rules (moomoo SG help centre):
  equity = total market value - margin loan
  below maintenance for > 48h  -> liquidation can happen at any time
  below soft edge              -> liquidation can happen immediately
  soft edge may be raised before weekends/holidays (see engine/calendar.py)
Ratios come from data/margin_ratios.csv (documented assumptions, see docs/assumptions.md).

Stub accounts: M-001 healthy, M-003 below maintenance (S2-S5), M-007 below soft edge.
"""
from __future__ import annotations

from datetime import datetime

from contracts import (
    Account,
    LiquidationDistance,
    LiquidationRisk,
    MarginStatus,
    MarginStatusCode,
    Position,
    PositionMargin,
    WeekendRisk,
)
from engine.prices import DEMO_NOW, get_prices

_IM, _MM, _SE, _SE_RAISED = 0.40, 0.30, 0.20, 0.30  # TODO(A): per-stock from data/margin_ratios.csv
_STUB_ACCOUNTS = {
    "M-001": (3000.0, 0.0, [("NVDA", 50, 110.0), ("TSLA", 20, 180.0)]),
    "M-003": (15000.0, 20.0, [("NVDA", 100, 130.0), ("TSLA", 40, 220.0)]),
    "M-007": (11000.0, 60.0, [("NVDA", 100, 150.0)]),
}  # account_id: (margin_loan, hours_below_mm, positions)


def get_account(account_id: str) -> Account:
    # TODO(A): read from data/accounts.db; raise KeyError for unknown accounts.
    loan, _, positions = _STUB_ACCOUNTS[account_id]
    return Account(account_id, "USD", 0.0, loan, [Position(*p) for p in positions])


def _stressed_values(account: Account, shocks: dict[str, float] | None) -> dict[str, float]:
    """Market value per ticker. shocks maps ticker to fractional change, e.g. {"NVDA": -0.08}."""
    prices = get_prices([p.ticker for p in account.positions])
    return {p.ticker: p.qty * prices[p.ticker].price * (1 + (shocks or {}).get(p.ticker, 0.0)) for p in account.positions}


def margin_status(account_id: str, now: datetime | None = None) -> MarginStatus:
    # TODO(A): replace stub with real calculation from accounts.db + prices + ratios + 48h clock.
    now = now or DEMO_NOW
    account = get_account(account_id)
    values = _stressed_values(account, None)
    market_value = sum(values.values())
    equity = market_value - account.margin_loan
    mm_req, se_req = market_value * _MM, market_value * _SE
    hours_below_mm = _STUB_ACCOUNTS[account_id][1]

    status: MarginStatusCode = "below_se" if equity < se_req else "below_mm" if equity < mm_req else "healthy"
    risk: LiquidationRisk = "none"
    if status == "below_se":
        risk = "immediate"
    elif status == "below_mm":
        risk = "anytime" if hours_below_mm >= 48 else "after_48h"
    quantities = {p.ticker: p.qty for p in account.positions}
    return MarginStatus(
        account_id=account_id,
        as_of=now,
        currency=account.currency,
        market_value=market_value,
        margin_loan=account.margin_loan,
        equity=equity,
        im_req=market_value * _IM,
        mm_req=mm_req,
        se_req=se_req,
        status=status,
        liquidation_risk=risk,
        hours_below_mm=hours_below_mm,
        shortfall_to_mm=max(0.0, mm_req - equity),
        shortfall_to_se=max(0.0, se_req - equity),
        soft_edge_uplift_applied=False,
        positions=[
            PositionMargin(t, quantities[t], v / quantities[t], v, _IM, _MM, _SE, "assumption_table")
            for t, v in values.items()
        ],
    )


def liquidation_distance(account_id: str, shocks: dict[str, float] | None = None) -> LiquidationDistance:
    # TODO(A): per-stock ratios; edge cases (zero loan, single-stock concentration).
    account = get_account(account_id)
    current = sum(_stressed_values(account, None).values())
    stressed = _stressed_values(account, shocks)
    stressed_value = sum(stressed.values())

    def pct_drop(ratio: float) -> float:
        return max(0.0, 1 - account.margin_loan / (current * (1 - ratio)))

    return LiquidationDistance(
        pct_drop_to_mm=pct_drop(_MM),
        pct_drop_to_se=pct_drop(_SE),
        stressed_market_value=stressed_value,
        stressed_equity=stressed_value - account.margin_loan,
        binding_position=max(stressed, key=stressed.get),
    )


def weekend_risk_check(
    account_id: str, now: datetime | None = None, shocks: dict[str, float] | None = None
) -> WeekendRisk:
    # TODO(A): use engine/calendar.py with the SG/US holiday list.
    now = now or DEMO_NOW
    account = get_account(account_id)
    market_value = sum(_stressed_values(account, shocks).values())
    equity = market_value - account.margin_loan
    se_req_raised = market_value * _SE_RAISED
    return WeekendRisk(
        is_pre_weekend=now.weekday() == 4,
        se_ratio_now=_SE,
        se_ratio_raised=_SE_RAISED,
        equity=equity,
        se_req_raised=se_req_raised,
        would_breach=equity < se_req_raised,
    )
