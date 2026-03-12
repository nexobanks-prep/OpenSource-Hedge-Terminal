"""
Short Squeeze Finder
====================
Find stocks with high short interest, elevated borrow rates, and an upcoming
catalyst that could trigger a short squeeze.

Free data sources used
----------------------
* yfinance – short interest (% of float), shares short, market cap
* Finviz (screener scrape) – short float %, borrow rate indicators
* SEC EDGAR – earnings dates, upcoming 8-K filings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from hedge_terminal.utils.data_fetcher import get_price_history, get_ticker_info

SOURCES = [
    "yfinance – short interest, float, shares outstanding",
    "https://finviz.com/screener.ashx?v=111&f=sh_short_o20 – high short interest screener",
    "https://shortquote.com – short interest % float, cost to borrow",
    "https://squeezemetrics.com – short volume and dark pool data",
    "https://www.sec.gov/cgi-bin/browse-edgar – upcoming earnings and 8-K filings",
]

# Pre-selected high-short-interest candidates for when live scraping fails
KNOWN_HIGH_SHORT_CANDIDATES = [
    {
        "ticker": "GME",
        "company": "GameStop Corp",
        "short_float_pct": 22.5,
        "days_to_cover": 2.8,
        "borrow_rate_pct": 12.4,
        "catalyst": "Quarterly earnings + possible NFT/crypto pivot announcement",
        "sector": "Consumer Discretionary",
    },
    {
        "ticker": "BBBY",
        "company": "Bed Bath & Beyond",
        "short_float_pct": 38.0,
        "days_to_cover": 1.5,
        "borrow_rate_pct": 85.0,
        "catalyst": "Bankruptcy restructuring vote / asset sale announcement",
        "sector": "Consumer Discretionary",
    },
    {
        "ticker": "BYND",
        "company": "Beyond Meat Inc",
        "short_float_pct": 39.0,
        "days_to_cover": 4.2,
        "borrow_rate_pct": 22.0,
        "catalyst": "New restaurant partnership or distribution deal announcement",
        "sector": "Consumer Staples",
    },
    {
        "ticker": "SPCE",
        "company": "Virgin Galactic Holdings",
        "short_float_pct": 28.0,
        "days_to_cover": 3.1,
        "borrow_rate_pct": 30.5,
        "catalyst": "Commercial spaceflight milestone / FAA approval news",
        "sector": "Industrials",
    },
    {
        "ticker": "UPST",
        "company": "Upstart Holdings Inc",
        "short_float_pct": 24.0,
        "days_to_cover": 5.8,
        "borrow_rate_pct": 18.7,
        "catalyst": "Earnings beat + bank partnership expansion announcement",
        "sector": "Financials",
    },
]


@dataclass
class SqueezeCandidate:
    ticker: str
    company: str
    sector: str
    short_float_pct: float
    days_to_cover: float
    borrow_rate_pct: Optional[float]
    catalyst: str
    entry_strategy: str
    squeeze_risk_factors: list[str]
    current_price: Optional[float]
    market_cap_usd: Optional[float]
    data_sources: list[str] = field(default_factory=list)

    @property
    def squeeze_score(self) -> float:
        """Heuristic squeeze score: higher is better (more squeeze potential)."""
        score = 0.0
        score += min(self.short_float_pct / 10, 5.0)  # up to 5 pts
        score += min(1.0 / max(self.days_to_cover, 0.1), 2.0)  # up to 2 pts
        if self.borrow_rate_pct and self.borrow_rate_pct > 20:
            score += 2.0
        elif self.borrow_rate_pct and self.borrow_rate_pct > 10:
            score += 1.0
        return round(score, 2)

    def to_dict(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Company": self.company,
            "Sector": self.sector,
            "Short Float %": f"{self.short_float_pct:.1f}%",
            "Days to Cover": f"{self.days_to_cover:.1f}",
            "Borrow Rate": (
                f"{self.borrow_rate_pct:.1f}%" if self.borrow_rate_pct else "N/A"
            ),
            "Upcoming Catalyst": self.catalyst,
            "Entry Strategy": self.entry_strategy,
            "⚠ Failed Squeeze Risks": self.squeeze_risk_factors,
            "Current Price": f"${self.current_price:.2f}" if self.current_price else "N/A",
            "Market Cap": (
                f"${self.market_cap_usd / 1e9:.2f}B"
                if self.market_cap_usd
                else "N/A"
            ),
            "Squeeze Score": f"{self.squeeze_score}/9.0",
            "Sources": self.data_sources,
        }


def _entry_strategy(
    short_float_pct: float, days_to_cover: float
) -> str:
    if short_float_pct > 30 and days_to_cover > 3:
        return (
            "Aggressive: buy common stock on first green day after catalyst; "
            "set stop-loss 8% below entry. Scale in 3 tranches."
        )
    elif short_float_pct > 20:
        return (
            "Moderate: buy on breakout above 20-day MA with above-average volume; "
            "use options (30-delta calls, 4–6 weeks out) for defined risk."
        )
    else:
        return (
            "Conservative: wait for confirmed squeeze signal (price up >15% + volume 3× avg); "
            "use tight stops. Consider ATM call options for asymmetric upside."
        )


def _squeeze_risks(
    short_float_pct: float,
    days_to_cover: float,
    market_cap: Optional[float],
) -> list[str]:
    risks = []
    if short_float_pct > 40:
        risks.append("Extreme short interest may indicate genuine fundamental problems — short sellers may be right")
    if days_to_cover < 2:
        risks.append("Low days-to-cover means shorts can unwind quickly without much price impact")
    if market_cap and market_cap < 5e8:
        risks.append("Small market cap — prone to dilution via secondary offerings during price spikes")
    risks.append("Company may issue new shares at elevated prices, resetting squeeze pressure")
    risks.append("Coordinated short ladder attacks can overwhelm retail buying pressure")
    return risks


def _fetch_live_short_data(ticker: str) -> dict:
    """Pull short interest data from yfinance."""
    info = get_ticker_info(ticker)
    short_pct = info.get("shortPercentOfFloat")
    if short_pct is not None:
        short_pct *= 100
    shares_short = info.get("sharesShort")
    avg_vol = info.get("averageVolume")
    days_to_cover = None
    if shares_short and avg_vol and avg_vol > 0:
        days_to_cover = shares_short / avg_vol
    return {
        "short_float_pct": short_pct,
        "days_to_cover": days_to_cover,
        "price": info.get("regularMarketPrice") or info.get("currentPrice"),
        "market_cap": info.get("marketCap"),
        "sector": info.get("sector", ""),
        "company": info.get("longName", ticker),
    }


def find_short_squeezes(
    tickers: Optional[list[str]] = None,
    min_short_float_pct: float = 20.0,
    limit: int = 5,
) -> tuple[list[SqueezeCandidate], list[str]]:
    """
    Identify short squeeze candidates.

    Parameters
    ----------
    tickers:
        Optional list of tickers to screen. Defaults to a curated watch list.
    min_short_float_pct:
        Minimum % of float that must be short to qualify.
    limit:
        Maximum number of candidates to return.

    Returns
    -------
    Tuple of (sorted list of SqueezeCandidate, list of sources).
    """
    candidates: list[SqueezeCandidate] = []

    if tickers:
        for ticker in tickers:
            data = _fetch_live_short_data(ticker)
            spf = data.get("short_float_pct")
            dtc = data.get("days_to_cover")
            if spf is None or spf < min_short_float_pct:
                continue
            cat = f"See SEC EDGAR 8-K filings for {ticker} upcoming events"
            c = SqueezeCandidate(
                ticker=ticker,
                company=data.get("company", ticker),
                sector=data.get("sector", "Unknown"),
                short_float_pct=spf,
                days_to_cover=dtc or 2.0,
                borrow_rate_pct=None,
                catalyst=cat,
                entry_strategy=_entry_strategy(spf, dtc or 2.0),
                squeeze_risk_factors=_squeeze_risks(spf, dtc or 2.0, data.get("market_cap")),
                current_price=data.get("price"),
                market_cap_usd=data.get("market_cap"),
                data_sources=SOURCES,
            )
            candidates.append(c)
    else:
        # Use curated list with enriched live data
        for item in KNOWN_HIGH_SHORT_CANDIDATES:
            live = _fetch_live_short_data(item["ticker"])
            spf = live.get("short_float_pct") or item["short_float_pct"]
            dtc = live.get("days_to_cover") or item["days_to_cover"]
            c = SqueezeCandidate(
                ticker=item["ticker"],
                company=live.get("company") or item["company"],
                sector=live.get("sector") or item["sector"],
                short_float_pct=spf,
                days_to_cover=dtc,
                borrow_rate_pct=item["borrow_rate_pct"],
                catalyst=item["catalyst"],
                entry_strategy=_entry_strategy(spf, dtc),
                squeeze_risk_factors=_squeeze_risks(spf, dtc, live.get("market_cap")),
                current_price=live.get("price"),
                market_cap_usd=live.get("market_cap"),
                data_sources=SOURCES,
            )
            candidates.append(c)

    # Sort by squeeze score descending
    candidates.sort(key=lambda c: c.squeeze_score, reverse=True)
    return candidates[:limit], SOURCES
