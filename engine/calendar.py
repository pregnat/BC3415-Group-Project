"""Trading calendar: weekends, SG/US holidays, soft-edge uplift windows. OWNER: A."""
from __future__ import annotations

from datetime import date, datetime


def is_pre_weekend_or_holiday(d: date) -> bool:
    # TODO(A): add SGX/US holiday list (document the source in docs/assumptions.md).
    return d.weekday() == 4  # Friday


def soft_edge_uplift(d: date) -> float:
    """Multiplier on soft-edge ratios for date d (1.0 = no uplift)."""
    # TODO(A): uplift size is an assumption; record it in docs/assumptions.md.
    return 1.25 if is_pre_weekend_or_holiday(d) else 1.0


def next_market_open(now: datetime) -> datetime:
    # TODO(A)
    raise NotImplementedError
