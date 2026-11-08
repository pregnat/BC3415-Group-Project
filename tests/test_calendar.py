"""OWNER: A. Trading calendar checks against the 2026 NYSE and MOM holiday lists."""
from datetime import date, datetime, timezone

import pytest

from engine.calendar import is_pre_weekend_or_holiday, is_trading_day, next_market_open, soft_edge_uplift


@pytest.mark.parametrize("d,market,expected", [
    (date(2026, 11, 6), "US", True),  # Friday
    (date(2026, 11, 5), "US", False),  # Thursday
    (date(2026, 11, 25), "US", True),  # day before Thanksgiving
    (date(2026, 4, 2), "US", True),  # day before Good Friday
    (date(2026, 7, 2), "US", True),  # day before the observed Independence Day
    (date(2026, 7, 3), "US", False),  # a holiday is not itself a trading day
    (date(2026, 11, 6), "SG", True),
    (date(2026, 2, 16), "SG", True),  # day before Chinese New Year
    (date(2026, 3, 20), "SG", True),  # Friday; Hari Raya Puasa falls on the Saturday
])
def test_pre_weekend_or_holiday(d, market, expected):
    assert is_pre_weekend_or_holiday(d, market) == expected


def test_markets_have_different_holidays():
    deepavali_in_lieu = date(2026, 11, 9)
    assert is_trading_day(deepavali_in_lieu, "US")
    assert not is_trading_day(deepavali_in_lieu, "SG")


def test_uplift_only_on_the_last_trading_day():
    assert soft_edge_uplift(date(2026, 11, 6)) == 1.5
    assert soft_edge_uplift(date(2026, 11, 7)) == 1.0  # Saturday: no trading day to raise it on


def test_demo_friday_reopens_monday_us_open():
    """DEMO_NOW is Fri 6 Nov 15:00 UTC, after the US open; US clocks are on EST by then."""
    assert next_market_open(datetime(2026, 11, 6, 15, 0)) == datetime(2026, 11, 9, 14, 30, tzinfo=timezone.utc)


def test_sg_reopens_tuesday_after_deepavali():
    assert next_market_open("2026-11-06T15:00:00Z", "SG") == datetime(2026, 11, 10, 1, 0, tzinfo=timezone.utc)


def test_before_the_open_returns_the_same_day():
    assert next_market_open("2026-11-05T12:00:00Z") == datetime(2026, 11, 5, 14, 30, tzinfo=timezone.utc)


def test_summer_open_uses_daylight_time():
    assert next_market_open("2026-07-02T21:00:00Z") == datetime(2026, 7, 6, 13, 30, tzinfo=timezone.utc)
