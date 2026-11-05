"""OWNER: A. Price data-quality checks on hand-made data, so no network is needed."""
from datetime import date

import pandas as pd

from engine.price_checks import check_prices, sessions_between

FRIDAY = date(2026, 11, 6)


def _prices(*rows):
    return pd.DataFrame(rows, columns=["ticker", "price", "timestamp"])


def _positions(*rows):
    return pd.DataFrame(rows, columns=["ticker", "avg_cost"])


def _checks(issues):
    return {(i.ticker, i.check) for i in issues}


def test_clean_data_has_no_issues():
    issues = check_prices(_prices(("NVDA", 206.87, "2026-11-05")), _positions(("NVDA", 180)), FRIDAY, {"NVDA": 207.0})
    assert issues == []


def test_missing_and_invalid_prices():
    issues = check_prices(
        _prices(("NVDA", 0.0, "2026-11-05")), _positions(("NVDA", 180), ("TSLA", 250)), FRIDAY
    )
    assert _checks(issues) == {("TSLA", "missing"), ("NVDA", "invalid")}


def test_stale_counts_trading_sessions_not_days():
    assert sessions_between(date(2026, 11, 2), FRIDAY) == 3  # Tue, Wed, Thu
    assert sessions_between(date(2026, 11, 25), date(2026, 11, 30)) == 1  # Thanksgiving and the weekend skipped
    issues = check_prices(_prices(("NVDA", 206.87, "2026-11-02")), _positions(("NVDA", 180)), FRIDAY)
    assert _checks(issues) == {("NVDA", "stale")}


def test_split_against_cost_basis_and_reference():
    issues = check_prices(
        _prices(("NVDA", 52.0, "2026-11-05")), _positions(("NVDA", 208)), FRIDAY, {"NVDA": 207.0}
    )
    assert _checks(issues) == {("NVDA", "split_suspect")}
    assert len(issues) == 2


def test_source_mismatch_over_two_percent():
    prices = _prices(("NVDA", 206.87, "2026-11-05"), ("TSLA", 410.88, "2026-11-05"))
    issues = check_prices(prices, _positions(("NVDA", 180), ("TSLA", 250)), FRIDAY, {"NVDA": 215.0, "TSLA": 412.0})
    assert _checks(issues) == {("NVDA", "source_mismatch")}
