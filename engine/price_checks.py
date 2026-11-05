"""Price data-quality checks: missing, invalid, stale, split-adjusted and cross-source. OWNER: A.

Run: python -m engine.price_checks           (snapshot vs data/stock_prices_backup.csv)
     python -m engine.price_checks --live    (snapshot vs yfinance; needs the network)
Results are written up in docs/data_quality.md.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from engine.calendar import is_trading_day
from engine.prices import DATA_DIR, DEMO_NOW

MAX_SESSIONS_OLD = 1  # a snapshot more than one completed session old is stale
MAX_SOURCE_GAP = 0.02  # 2% between two sources is a mismatch
SPLIT_RATIOS = (2, 3, 4, 5, 10, 20)
SPLIT_TOLERANCE = 0.05


@dataclass
class Issue:
    ticker: str
    check: str  # "missing" | "invalid" | "stale" | "split_suspect" | "source_mismatch"
    detail: str


def sessions_between(start: date, end: date) -> int:
    """US trading days strictly after start and strictly before end."""
    return sum(is_trading_day(start + timedelta(days=i)) for i in range(1, (end - start).days))


def _split_ratio(a: float, b: float) -> int | None:
    """The split ratio if a/b or b/a is close to one, e.g. 4 for 200 vs 50."""
    ratio = max(a, b) / min(a, b)
    return next((r for r in SPLIT_RATIOS if abs(ratio - r) / r < SPLIT_TOLERANCE), None)


def check_prices(
    prices: pd.DataFrame,
    positions: pd.DataFrame,
    as_of: date,
    reference: dict[str, float] | None = None,
    reference_name: str = "reference",
) -> list[Issue]:
    """prices has ticker, price, timestamp; positions has ticker, avg_cost. reference maps ticker to a
    second source's price, for the split and cross-source checks."""
    issues = []
    priced = prices.set_index("ticker")
    for ticker in sorted(set(positions["ticker"]) - set(priced.index)):
        issues.append(Issue(ticker, "missing", "held in positions.csv but has no price"))

    for ticker, row in priced.iterrows():
        price = row["price"]
        if pd.isna(price) or not 0 < price < float("inf"):
            issues.append(Issue(ticker, "invalid", f"price is {price}"))
            continue

        age = sessions_between(pd.Timestamp(row["timestamp"]).date(), as_of)
        if age > MAX_SESSIONS_OLD:
            issues.append(Issue(ticker, "stale", f"priced {row['timestamp']}, {age} sessions before {as_of}"))

        for avg_cost in positions.loc[positions["ticker"] == ticker, "avg_cost"].unique():
            if (r := _split_ratio(price, avg_cost)) is not None:
                issues.append(Issue(ticker, "split_suspect", f"price {price} is ~1:{r} of avg_cost {avg_cost}"))

        other = (reference or {}).get(ticker)
        if other is None:
            continue
        if (r := _split_ratio(price, other)) is not None:
            issues.append(Issue(ticker, "split_suspect", f"price {price} is ~1:{r} of {reference_name} {other}"))
        elif abs(price - other) / other > MAX_SOURCE_GAP:
            issues.append(Issue(ticker, "source_mismatch", f"price {price} vs {reference_name} {other}"))
    return issues


def _yfinance_reference(tickers: list[str]) -> dict[str, float]:
    from engine.prices import _yfinance_quote

    quotes = {t: _yfinance_quote(t) for t in tickers}
    return {t: q.price for t, q in quotes.items() if q is not None}


def main(argv: list[str]) -> None:
    prices = pd.read_csv(DATA_DIR / "stock_prices.csv")
    positions = pd.read_csv(DATA_DIR / "positions.csv")
    if "--live" in argv:
        reference, name = _yfinance_reference(list(prices["ticker"])), "yfinance"
    else:
        backup = pd.read_csv(DATA_DIR / "stock_prices_backup.csv")
        reference, name = dict(zip(backup["ticker"], backup["price"])), "backup"
    issues = check_prices(prices, positions, DEMO_NOW.date(), reference, name)
    for issue in issues:
        print(f"{issue.ticker:6} {issue.check:16} {issue.detail}")
    print(f"{len(issues)} issue(s); compared with {name} for {len(reference)} ticker(s)")


if __name__ == "__main__":
    main(sys.argv[1:])
