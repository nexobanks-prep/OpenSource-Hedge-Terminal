"""
Quote Module
============
Fetch live/delayed stock quotes for one or more tickers.

Replicates Bloomberg Terminal's **BQ / DES** function and
OpenBB Terminal's ``stocks quote`` command — for free, using yfinance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hedge_terminal.utils.data_fetcher import get_ticker_info, get_price_history, safe_get


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class StockQuote:
    ticker: str
    company_name: str
    price: float | None
    prev_close: float | None
    open_price: float | None
    day_high: float | None
    day_low: float | None
    volume: int | None
    avg_volume: int | None
    market_cap: float | None
    pe_ratio: float | None
    eps_ttm: float | None
    dividend_yield_pct: float | None
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    beta: float | None
    change_pct: float | None  # day change %
    currency: str = "USD"
    exchange: str = ""
    sector: str = ""
    industry: str = ""

    # -----------------------------------------------------------------------
    def to_dict(self) -> dict[str, str]:
        def _fmt(v: float | None, decimals: int = 2, suffix: str = "") -> str:
            if v is None:
                return "N/A"
            return f"{v:,.{decimals}f}{suffix}"

        def _fmt_big(v: float | None) -> str:
            if v is None:
                return "N/A"
            if v >= 1e12:
                return f"${v / 1e12:.2f}T"
            if v >= 1e9:
                return f"${v / 1e9:.2f}B"
            if v >= 1e6:
                return f"${v / 1e6:.2f}M"
            return f"${v:,.0f}"

        chg_str = "N/A"
        if self.change_pct is not None:
            sign = "+" if self.change_pct >= 0 else ""
            chg_str = f"{sign}{self.change_pct:.2f}%"

        return {
            "Ticker": self.ticker,
            "Company": self.company_name or "N/A",
            "Exchange": self.exchange or "N/A",
            "Sector / Industry": (
                f"{self.sector} / {self.industry}"
                if self.sector
                else "N/A"
            ),
            "Price": f"{self.currency} {_fmt(self.price)}",
            "Day Change": chg_str,
            "Open": _fmt(self.open_price),
            "Prev Close": _fmt(self.prev_close),
            "Day High": _fmt(self.day_high),
            "Day Low": _fmt(self.day_low),
            "52-Week High": _fmt(self.fifty_two_week_high),
            "52-Week Low": _fmt(self.fifty_two_week_low),
            "Volume": f"{self.volume:,}" if self.volume else "N/A",
            "Avg Volume (3M)": f"{self.avg_volume:,}" if self.avg_volume else "N/A",
            "Market Cap": _fmt_big(self.market_cap),
            "P/E (TTM)": _fmt(self.pe_ratio),
            "EPS (TTM)": _fmt(self.eps_ttm),
            "Dividend Yield": (
                f"{self.dividend_yield_pct:.2f}%"
                if self.dividend_yield_pct is not None
                else "N/A"
            ),
            "Beta": _fmt(self.beta),
        }


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def get_quote(ticker: str) -> StockQuote:
    """Return a :class:`StockQuote` for *ticker* using yfinance."""
    info: dict[str, Any] = get_ticker_info(ticker.upper())

    price = (
        info.get("regularMarketPrice")
        or info.get("currentPrice")
        or info.get("ask")
    )
    prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")

    change_pct: float | None = None
    if price is not None and prev_close and prev_close != 0:
        change_pct = (price - prev_close) / prev_close * 100

    div_yield = info.get("dividendYield")
    if div_yield is not None:
        div_yield = div_yield * 100  # convert 0.04 → 4.0 %

    return StockQuote(
        ticker=ticker.upper(),
        company_name=info.get("longName") or info.get("shortName") or "",
        price=price,
        prev_close=prev_close,
        open_price=info.get("regularMarketOpen") or info.get("open"),
        day_high=info.get("regularMarketDayHigh") or info.get("dayHigh"),
        day_low=info.get("regularMarketDayLow") or info.get("dayLow"),
        volume=info.get("regularMarketVolume") or info.get("volume"),
        avg_volume=info.get("averageVolume"),
        market_cap=info.get("marketCap"),
        pe_ratio=info.get("trailingPE"),
        eps_ttm=info.get("trailingEps"),
        dividend_yield_pct=div_yield,
        fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
        fifty_two_week_low=info.get("fiftyTwoWeekLow"),
        beta=info.get("beta"),
        change_pct=change_pct,
        currency=info.get("currency", "USD"),
        exchange=info.get("exchange") or info.get("fullExchangeName") or "",
        sector=info.get("sector") or "",
        industry=info.get("industry") or "",
    )


def get_quotes(tickers: list[str]) -> list[StockQuote]:
    """Return quotes for a list of tickers (best-effort; skips errors)."""
    results: list[StockQuote] = []
    for t in tickers:
        try:
            results.append(get_quote(t))
        except Exception:  # noqa: BLE001
            pass
    return results
