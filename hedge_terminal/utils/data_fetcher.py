"""Data fetching utilities using free/open-source sources."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests
import yfinance as yf


def get_ticker_info(ticker: str) -> dict[str, Any]:
    """Return basic info for a ticker via yfinance."""
    t = yf.Ticker(ticker)
    return t.info or {}


def get_price_history(
    ticker: str, period: str = "1y", interval: str = "1d"
) -> pd.DataFrame:
    """Download OHLCV price history for a ticker."""
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)
    return df


def get_options_chain(ticker: str) -> dict[str, pd.DataFrame]:
    """
    Return the nearest-expiry options chain for a ticker.

    Returns a dict with keys ``"calls"`` and ``"puts"``.
    """
    t = yf.Ticker(ticker)
    expirations = t.options
    if not expirations:
        return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}
    nearest = expirations[0]
    chain = t.option_chain(nearest)
    return {"calls": chain.calls, "puts": chain.puts, "expiry": nearest}


def fetch_fred_series(series_id: str, api_key: str = "") -> pd.Series:
    """
    Fetch a FRED data series.  Falls back to FRED's public CSV endpoint when
    no API key is provided.
    """
    url = (
        f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        from io import StringIO

        df = pd.read_csv(StringIO(resp.text), parse_dates=["DATE"], index_col="DATE")
        col = df.columns[0]
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        series.name = series_id
        return series
    except Exception:  # noqa: BLE001
        return pd.Series(name=series_id, dtype=float)


def fetch_html_table(url: str, table_index: int = 0) -> pd.DataFrame:
    """Download the first HTML table from *url*."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; OpenSource-Hedge-Terminal/1.0)"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        tables = pd.read_html(resp.text)
        if tables and len(tables) > table_index:
            return tables[table_index]
    except Exception:  # noqa: BLE001
        pass
    return pd.DataFrame()


def safe_get(d: dict, *keys: str, default: Any = None) -> Any:
    """Safely extract a nested key from a dict."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d
