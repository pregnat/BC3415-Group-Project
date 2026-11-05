"""Trading calendar: weekends, SG/US holidays, soft-edge uplift windows. OWNER: A.

Holiday lists cover 2026 only; other years fall back to weekends. Sources:
  US: NYSE holiday calendar (Independence Day is observed on Fri 3 Jul because 4 Jul is a Saturday).
  SG: MOM public holidays (mom.gov.sg/employment-practices/public-holidays). SGX closes on weekday
      holidays and on the Monday in lieu of a Sunday holiday.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd

Market = Literal["US", "SG"]

SOFT_EDGE_UPLIFT = 1.5  # 20% -> 30% in the help centre's Friday example, see docs/assumptions.md

HOLIDAYS: dict[str, frozenset[date]] = {
    "US": frozenset({
        date(2026, 1, 1),  # New Year's Day
        date(2026, 1, 19),  # Martin Luther King Jr. Day
        date(2026, 2, 16),  # Presidents' Day
        date(2026, 4, 3),  # Good Friday
        date(2026, 5, 25),  # Memorial Day
        date(2026, 6, 19),  # Juneteenth
        date(2026, 7, 3),  # Independence Day, observed
        date(2026, 9, 7),  # Labor Day
        date(2026, 11, 26),  # Thanksgiving
        date(2026, 12, 25),  # Christmas
    }),
    "SG": frozenset({
        date(2026, 1, 1),  # New Year's Day
        date(2026, 2, 17),  # Chinese New Year
        date(2026, 2, 18),  # Chinese New Year
        date(2026, 4, 3),  # Good Friday
        date(2026, 5, 1),  # Labour Day
        date(2026, 5, 27),  # Hari Raya Haji
        date(2026, 6, 1),  # Vesak Day (31 May is a Sunday)
        date(2026, 8, 10),  # National Day (9 Aug is a Sunday)
        date(2026, 11, 9),  # Deepavali (8 Nov is a Sunday)
        date(2026, 12, 25),  # Christmas Day
        # Hari Raya Puasa is Sat 21 Mar, so SGX doesn't close for it.
    }),
}

# Regular session open in each market's local time.
MARKET_OPEN: dict[str, tuple[time, ZoneInfo]] = {
    "US": (time(9, 30), ZoneInfo("America/New_York")),
    "SG": (time(9, 0), ZoneInfo("Asia/Singapore")),
}


def is_trading_day(d: date, market: Market = "US") -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS[market]


def is_pre_weekend_or_holiday(d: date, market: Market = "US") -> bool:
    """True on the last trading day before a weekend or holiday, when the soft edge may be raised."""
    return is_trading_day(d, market) and not is_trading_day(d + timedelta(days=1), market)


def soft_edge_uplift(d: date, market: Market = "US") -> float:
    """Multiplier on soft-edge ratios for date d (1.0 = no uplift)."""
    return SOFT_EDGE_UPLIFT if is_pre_weekend_or_holiday(d, market) else 1.0


def next_market_open(now: datetime | str, market: Market = "US") -> datetime:
    """The next regular-session open after `now`, in UTC. This is when a raised soft edge is lowered
    again. Timestamps without a timezone are read as UTC, like the rest of the engine."""
    ts = pd.Timestamp(now)
    now_utc = (ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")).to_pydatetime()
    open_time, tz = MARKET_OPEN[market]
    day = now_utc.astimezone(tz).date()
    while True:
        opens = datetime.combine(day, open_time, tzinfo=tz)
        if is_trading_day(day, market) and opens > now_utc:
            return opens.astimezone(timezone.utc)
        day += timedelta(days=1)
