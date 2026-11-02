"""Price lookup: frozen snapshot, moomoo OpenAPI live mode, yfinance fallback. OWNER: A."""
from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
import requests

from contracts import PriceQuote

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEMO_NOW = datetime(2026, 11, 6, 15, 0)  # Friday before the close; the default clock for demos

_CURRENCY = "USD"  # the snapshot and both live sources only cover US-listed stocks


@lru_cache
def _snapshot() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "stock_prices.csv", index_col="ticker")


def _quote(ticker: str, price: float, timestamp: str, source: str) -> PriceQuote:
    return PriceQuote(ticker, float(price), _CURRENCY, pd.Timestamp(timestamp).to_pydatetime(), source)


def _snapshot_quote(ticker: str) -> PriceQuote:
    row = _snapshot().loc[ticker]  # KeyError for unknown tickers
    return _quote(ticker, row["price"], row["timestamp"], f"snapshot:{row['source']}")


def _moomoo_quotes(tickers: list[str]) -> dict[str, PriceQuote]:
    """Empty if there is no MOOMOO_ACCESS_TOKEN or the API call fails."""
    token = os.environ.get("MOOMOO_ACCESS_TOKEN")
    if not token:
        return {}
    try:
        response = requests.post(
            "https://webapi.moomoo.com/api/v1.0/quote/snapshot",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"code_list": [f"US.{t}" for t in tickers]},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("ret_code") != 0:
            return {}
        quotes = {}
        for item in data.get("data", {}).get("snapshot_list", []):
            ticker = item["code"].replace("US.", "")
            price = float(item["last_price"])
            if ticker in tickers and 0 < price < float("inf"):
                quotes[ticker] = _quote(ticker, price, item.get("data_date", ""), "moomoo")
        return quotes
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return {}


def _yfinance_quote(ticker: str) -> PriceQuote | None:
    import yfinance as yf

    try:
        history = yf.Ticker(ticker).history(period="5d")
        price = float(history["Close"].iloc[-1])
    except Exception:  # yfinance raises many types when Yahoo is down or the ticker is unknown
        return None
    if not 0 < price < float("inf"):
        return None
    return _quote(ticker, price, str(history.index[-1].date()), "yfinance")


def get_prices(tickers: list[str], mode: Literal["snapshot", "live"] = "snapshot") -> dict[str, PriceQuote]:
    """Live mode tries moomoo, then yfinance, then the snapshot. KeyError if a ticker has no price."""
    if mode == "snapshot":
        return {ticker: _snapshot_quote(ticker) for ticker in tickers}
    quotes = _moomoo_quotes(tickers)
    for ticker in tickers:
        if ticker not in quotes:
            quotes[ticker] = _yfinance_quote(ticker) or _snapshot_quote(ticker)
    return quotes
