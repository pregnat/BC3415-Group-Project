"""Price lookup: frozen snapshot, moomoo OpenAPI live mode, yfinance fallback. OWNER: A."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from contracts import PriceQuote

DEMO_NOW = datetime(2026, 11, 6, 15, 0)  # Friday before the close; the snapshot's clock

_STUB_PRICES = {"NVDA": (120.0, "USD"), "TSLA": (200.0, "USD")}


def get_prices(tickers: list[str], mode: Literal["snapshot", "live"] = "snapshot") -> dict[str, PriceQuote]:
    # TODO(A): read from data/price_snapshot.parquet; add live mode with the yfinance fallback.
    quotes = {}
    for ticker in tickers:
        price, currency = _STUB_PRICES[ticker]  # KeyError for unknown tickers: keep this in the real code
        quotes[ticker] = PriceQuote(ticker, price, currency, DEMO_NOW, "stub")
    return quotes
