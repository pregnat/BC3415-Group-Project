"""Price lookup from data/price_snapshot.parquet. OWNER: A."""
from __future__ import annotations

from datetime import datetime

from contracts import PriceQuote


def get_price(ticker: str, as_of: datetime | None = None) -> PriceQuote:
    # TODO(A): read from data/price_snapshot.parquet; raise KeyError for unknown tickers.
    fake = {"D05.SI": (38.0, "SGD"), "NVDA": (120.0, "USD")}
    price, ccy = fake.get(ticker, (10.0, "SGD"))
    return PriceQuote(ticker, price, ccy, as_of or datetime(2026, 11, 6, 15, 0), "stub")
