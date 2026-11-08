"""OWNER: A. Rule tests for engine/margin.py.

Expected numbers are the notebook's saved outputs on the frozen data/stock_prices.csv, except that
the raised soft edge uses x1.5 rather than the notebook's x1.25. If that snapshot is refreshed, the
demo numbers change and these need updating.
"""
import pandas as pd
import pytest

from engine.calendar import soft_edge_uplift
from engine.margin import _accounts, get_account, liquidation_distance, margin_status, weekend_risk_check
from engine.prices import DATA_DIR, get_prices

FRIDAY = "2026-11-06T15:00:00Z"
THURSDAY = "2026-11-05T15:00:00Z"


@pytest.mark.parametrize(
    "account_id,equity,mm_req,se_req,status",
    [
        ("M-001", 11206.100, 1861.8300, 1241.220, "healthy"),
        ("M-002", 3608.800, 1438.0800, 1027.200, "healthy"),
        ("M-003", 1137.400, 1241.2200, 827.480, "below_mm"),
        ("M-004", 8012.875, 1803.8625, 1202.575, "healthy"),
        ("M-005", 4717.600, 2876.1600, 2054.400, "healthy"),
        ("M-006", 1531.050, 2259.3150, 1506.210, "below_mm"),
        ("M-007", 7857.675, 2357.3025, 1571.535, "healthy"),
        ("M-008", -291.200, 1438.0800, 1027.200, "below_se"),
        ("M-009", 3090.475, 1527.1425, 1018.095, "healthy"),
        ("M-010", -793.900, 1861.8300, 1241.220, "below_se"),
    ],
)
def test_all_accounts_match_notebook(account_id, equity, mm_req, se_req, status):
    s = margin_status(account_id)
    assert s.equity == pytest.approx(equity)
    assert s.mm_req == pytest.approx(mm_req)
    assert s.se_req == pytest.approx(se_req)
    assert s.status == status


def test_every_status_is_covered():
    statuses = {margin_status(a).status for a in pd.read_csv(DATA_DIR / "accounts.csv")["account_id"]}
    assert statuses == {"healthy", "below_mm", "below_se"}


def test_below_soft_edge_is_immediate():
    assert margin_status("M-008").liquidation_risk == "immediate"


def test_below_maintenance_over_48h_is_anytime():
    s = margin_status("M-003", "2026-11-02T15:00:00Z")
    assert s.hours_below_mm == 77.0
    assert s.liquidation_risk == "anytime"


def test_below_maintenance_under_48h_is_after_48h():
    s = margin_status("M-003", "2026-10-31T10:00:00Z")
    assert s.hours_below_mm == 24.0
    assert s.liquidation_risk == "after_48h"


def test_healthy_account_has_no_clock():
    s = margin_status("M-001")
    assert s.hours_below_mm == 0.0
    assert s.liquidation_risk == "none"


def test_demo_clock_is_still_running_for_m006():
    s = margin_status("M-006")
    assert s.hours_below_mm == 24.0
    assert s.liquidation_risk == "after_48h"


def test_missing_breach_time_is_unknown_not_zero(monkeypatch):
    accounts = _accounts().copy()
    accounts.loc["M-006", "below_mm_since"] = float("nan")
    monkeypatch.setattr("engine.margin._accounts", lambda: accounts)
    s = margin_status("M-006")
    assert s.hours_below_mm is None
    assert s.liquidation_risk == "anytime"


def test_every_account_below_maintenance_has_a_breach_time():
    for account_id in _accounts().index:
        if margin_status(account_id).status != "healthy":
            assert pd.notna(_accounts().at[account_id, "below_mm_since"]), account_id


def test_shortfalls():
    s = margin_status("M-003")
    assert s.shortfall_to_mm == pytest.approx(1241.22 - 1137.4)
    assert s.shortfall_to_se == 0.0


def test_uses_each_stocks_own_ratios():
    ratios = {p.ticker: p.maintenance_ratio for p in margin_status("M-005").positions}
    assert ratios == {"TSLA": 0.35}


def test_liquidation_distance_matches_notebook():
    d = liquidation_distance("M-003", {"NVDA": -0.08})
    assert d.pct_drop_to_mm == 0.0
    assert d.pct_drop_to_se == pytest.approx(0.09363368298931686)
    assert d.stressed_equity == pytest.approx(806.408)
    assert d.binding_position == "NVDA"


def test_drop_to_threshold_really_reaches_it():
    """Applying the reported drop to every position leaves equity exactly at the requirement."""
    account_id = "M-002"
    d = liquidation_distance(account_id, {p.ticker: 0.0 for p in get_account(account_id).positions})
    shocks = {p.ticker: -d.pct_drop_to_mm for p in get_account(account_id).positions}
    stressed = liquidation_distance(account_id, shocks)
    assert stressed.stressed_equity == pytest.approx(stressed.stressed_market_value * 0.35)


def test_drop_is_capped_when_threshold_cannot_be_reached():
    """M-001 has cash and no loan, so even losing every position can't breach."""
    d = liquidation_distance("M-001")
    assert d.pct_drop_to_mm == 1.0
    assert d.pct_drop_to_se == 1.0


def test_friday_uplift_raises_soft_edge():
    r = weekend_risk_check("M-003", FRIDAY)
    assert r.is_pre_weekend
    assert (r.se_ratio_now, r.se_ratio_raised) == (pytest.approx(0.2), pytest.approx(0.3))
    assert r.se_req_raised == pytest.approx(1241.22)
    assert r.would_breach  # 1137.40 of equity is below the raised requirement, before any price move
    assert soft_edge_uplift(pd.Timestamp(FRIDAY).date()) == 1.5


def test_friday_uplift_leaves_healthy_account_alone():
    assert not weekend_risk_check("M-001", FRIDAY).would_breach


def test_s3_shock_breaches_only_the_raised_soft_edge():
    shocks = {"NVDA": -0.08}
    r = weekend_risk_check("M-003", FRIDAY, shocks)
    assert r.equity == pytest.approx(806.408)
    assert r.se_req_raised == pytest.approx(1141.9224)
    assert r.would_breach
    assert margin_status("M-003").status == "below_mm"
    assert r.equity > r.se_req_raised / 1.5  # still above the normal soft edge


def test_no_breach_outside_uplift_window():
    r = weekend_risk_check("M-003", THURSDAY, {"NVDA": -0.08})
    assert not r.is_pre_weekend
    assert not r.would_breach
    assert soft_edge_uplift(pd.Timestamp(THURSDAY).date()) == 1.0


@pytest.mark.parametrize("fn", [get_account, margin_status, liquidation_distance, weekend_risk_check])
def test_unknown_account_raises_keyerror(fn):
    with pytest.raises(KeyError):
        fn("M-999")


def test_data_files_are_consistent():
    """The notebook's validation checks, so a bad CSV edit fails here instead of at demo time."""
    accounts = pd.read_csv(DATA_DIR / "accounts.csv")
    positions = pd.read_csv(DATA_DIR / "positions.csv")
    prices = pd.read_csv(DATA_DIR / "stock_prices.csv")
    ratios = pd.read_csv(DATA_DIR / "margin_ratios.csv")
    assert accounts["account_id"].is_unique
    assert prices["ticker"].is_unique
    assert ratios["ticker"].is_unique
    assert not positions.duplicated(["account_id", "ticker"]).any()
    assert (accounts[["cash", "margin_loan"]] >= 0).all().all()
    assert (positions["qty"] > 0).all()
    assert (prices["price"] > 0).all()
    assert set(accounts["account_id"]) == set(positions["account_id"])  # no account without positions
    assert positions["ticker"].isin(prices["ticker"]).all()
    assert positions["ticker"].isin(ratios["ticker"]).all()
    assert ((ratios["initial_ratio"] >= ratios["maintenance_ratio"]) & (ratios["maintenance_ratio"] >= ratios["soft_edge_ratio"])).all()


def test_snapshot_prices_come_from_the_csv():
    quote = get_prices(["NVDA"])["NVDA"]
    assert (quote.price, quote.currency, quote.source) == (206.87, "USD", "snapshot:moomoo")


def test_live_mode_falls_back_to_snapshot(monkeypatch):
    """No moomoo token and Yahoo unreachable still returns a clearly labelled snapshot price."""
    monkeypatch.delenv("MOOMOO_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr("engine.prices._yfinance_quote", lambda ticker: None)
    assert get_prices(["NVDA"], mode="live")["NVDA"].source == "snapshot:moomoo"
    with pytest.raises(KeyError):
        get_prices(["NOPE"], mode="live")


def test_live_mode_prefers_moomoo_over_yfinance(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            item = {"code": "US.NVDA", "last_price": 210.0, "data_date": "2026-11-03"}
            return {"ret_code": 0, "data": {"snapshot_list": [item]}}

    monkeypatch.setenv("MOOMOO_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr("engine.prices.requests.post", lambda *a, **k: Response())
    monkeypatch.setattr("engine.prices._yfinance_quote", lambda ticker: None)
    quotes = get_prices(["NVDA", "TSLA"], mode="live")
    assert (quotes["NVDA"].price, quotes["NVDA"].source) == (210.0, "moomoo")
    assert quotes["TSLA"].source == "snapshot:moomoo"


def test_gaps_are_computed_by_the_engine():
    """The agent must not subtract numbers itself, so every gap it may quote comes from here."""
    s = margin_status("M-003")
    assert s.excess_over_se == pytest.approx(1137.4 - 827.48)
    assert (s.excess_over_mm, s.shortfall_to_se) == (0.0, 0.0)
    r = weekend_risk_check("M-003", FRIDAY, {"NVDA": -0.08})
    assert r.shortfall_to_se_raised == pytest.approx(1141.9224 - 806.408)
    assert r.excess_over_se_raised == 0.0
    assert weekend_risk_check("M-001", FRIDAY).shortfall_to_se_raised == 0.0
