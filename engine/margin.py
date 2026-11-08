"""Margin engine. OWNER: A.

Rules (moomoo SG help centre):
  equity = total market value + cash - margin loan
  below maintenance for > 48h  -> liquidation can happen at any time
  below soft edge              -> liquidation can happen immediately
  soft edge may be raised before weekends/holidays (see engine/calendar.py)
Accounts and positions come from data/accounts.csv and data/positions.csv. Ratios come from
data/margin_ratios.csv (documented assumptions, see docs/assumptions.md).

Ported from notebooks/data_margin_engine/Data and Margin Engine.ipynb.
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache

import pandas as pd

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
from engine.calendar import SOFT_EDGE_UPLIFT, is_pre_weekend_or_holiday
from engine.prices import DATA_DIR, DEMO_NOW, get_prices


@lru_cache
def _accounts() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "accounts.csv", index_col="account_id")


@lru_cache
def _positions() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "positions.csv")


@lru_cache
def _ratios() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "margin_ratios.csv", index_col="ticker")


def _as_utc(now: datetime | str) -> datetime:
    """Timestamps without a timezone are read as UTC, like accounts.csv's below_mm_since."""
    ts = pd.Timestamp(now)
    return (ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")).to_pydatetime()


def get_account(account_id: str) -> Account:
    """Raises KeyError for unknown accounts."""
    row = _accounts().loc[account_id]
    positions = _positions()[_positions()["account_id"] == account_id]
    return Account(
        account_id=account_id,
        currency=row["currency"],
        cash=float(row["cash"]),
        margin_loan=float(row["margin_loan"]),
        positions=[
            Position(p.ticker, float(p.qty), float(p.avg_cost)) for p in positions.itertuples()
        ],
    )


def _stressed_values(account: Account, shocks: dict[str, float] | None) -> dict[str, float]:
    """Market value per ticker. shocks maps ticker to fractional change, e.g. {"NVDA": -0.08}."""
    prices = get_prices([p.ticker for p in account.positions])
    return {p.ticker: p.qty * prices[p.ticker].price * (1 + (shocks or {}).get(p.ticker, 0.0)) for p in account.positions}


def _requirement(values: dict[str, float], ratio: str) -> float:
    """Sum of market value x the stock's ratio. ratio is a column of margin_ratios.csv."""
    return sum(value * float(_ratios().at[ticker, ratio]) for ticker, value in values.items())


def _hours_below_mm(account_id: str, now: datetime) -> float | None:
    """None if accounts.csv has no below_mm_since for this account."""
    since = _accounts().at[account_id, "below_mm_since"]
    if pd.isna(since):
        return None
    return max(0.0, (now - pd.Timestamp(since)).total_seconds() / 3600)


def margin_status(account_id: str, now: datetime | str | None = None) -> MarginStatus:
    now = _as_utc(now or DEMO_NOW)
    account = get_account(account_id)
    values = _stressed_values(account, None)
    market_value = sum(values.values())
    equity = market_value + account.cash - account.margin_loan
    mm_req, se_req = _requirement(values, "maintenance_ratio"), _requirement(values, "soft_edge_ratio")

    status: MarginStatusCode = "below_se" if equity < se_req else "below_mm" if equity < mm_req else "healthy"
    hours_below_mm = 0.0 if status == "healthy" else _hours_below_mm(account_id, now)
    risk: LiquidationRisk = "none"
    if status == "below_se":
        risk = "immediate"
    elif status == "below_mm":
        # An unknown clock can't show the 48 hours are still running, so assume they have passed.
        risk = "anytime" if hours_below_mm is None or hours_below_mm >= 48 else "after_48h"
    quantities = {p.ticker: p.qty for p in account.positions}
    ratios = _ratios()
    return MarginStatus(
        account_id=account_id,
        as_of=now,
        currency=account.currency,
        market_value=market_value,
        cash=account.cash,
        margin_loan=account.margin_loan,
        equity=equity,
        im_req=_requirement(values, "initial_ratio"),
        mm_req=mm_req,
        se_req=se_req,
        status=status,
        liquidation_risk=risk,
        hours_below_mm=hours_below_mm,
        shortfall_to_mm=max(0.0, mm_req - equity),
        shortfall_to_se=max(0.0, se_req - equity),
        excess_over_mm=max(0.0, equity - mm_req),
        excess_over_se=max(0.0, equity - se_req),
        soft_edge_uplift_applied=False,  # the raised soft edge is only modelled in weekend_risk_check
        positions=[
            PositionMargin(
                t,
                quantities[t],
                v / quantities[t],
                v,
                float(ratios.at[t, "initial_ratio"]),
                float(ratios.at[t, "maintenance_ratio"]),
                float(ratios.at[t, "soft_edge_ratio"]),
                ratios.at[t, "ratio_source"],
            )
            for t, v in values.items()
        ],
    )


def liquidation_distance(account_id: str, shocks: dict[str, float] | None = None) -> LiquidationDistance:
    account = get_account(account_id)
    values = _stressed_values(account, None)
    current = sum(values.values())
    equity = current + account.cash - account.margin_loan
    stressed = _stressed_values(account, shocks)
    stressed_value = sum(stressed.values())

    def pct_drop(ratio: str) -> float:
        # Solves equity - d * current = req * (1 - d) for a uniform drop d across all positions.
        req = _requirement(values, ratio)
        return min(1.0, max(0.0, (equity - req) / (current - req)))

    return LiquidationDistance(
        pct_drop_to_mm=pct_drop("maintenance_ratio"),
        pct_drop_to_se=pct_drop("soft_edge_ratio"),
        stressed_market_value=stressed_value,
        stressed_equity=stressed_value + account.cash - account.margin_loan,
        binding_position=max(stressed, key=stressed.get),
    )


def weekend_risk_check(
    account_id: str, now: datetime | str | None = None, shocks: dict[str, float] | None = None
) -> WeekendRisk:
    now = _as_utc(now or DEMO_NOW)
    account = get_account(account_id)
    values = _stressed_values(account, shocks)
    market_value = sum(values.values())
    equity = market_value + account.cash - account.margin_loan
    se_req = _requirement(values, "soft_edge_ratio")
    se_req_raised = se_req * SOFT_EDGE_UPLIFT
    is_pre_weekend = is_pre_weekend_or_holiday(now.date())
    return WeekendRisk(
        is_pre_weekend=is_pre_weekend,
        se_ratio_now=se_req / market_value,
        se_ratio_raised=se_req_raised / market_value,
        equity=equity,
        se_req_raised=se_req_raised,
        shortfall_to_se_raised=max(0.0, se_req_raised - equity),
        excess_over_se_raised=max(0.0, equity - se_req_raised),
        would_breach=is_pre_weekend and equity < se_req_raised,
    )
