"""
Dividend Analyzer
=================
Screen for stocks with apparently attractive dividend yields (>5%) but with
warning signs: high payout ratio, negative free cash flow, or rising debt.

Free data sources used
----------------------
* yfinance – fundamentals, dividend yield, payout ratio, FCF
* Yahoo Finance screener (via yfinance batch download)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from hedge_terminal.utils.data_fetcher import get_price_history, get_ticker_info

SOURCES = [
    "yfinance (Yahoo Finance) – dividend yield, payout ratio, earnings, FCF",
    "https://finance.yahoo.com/screener – dividend screener",
    "https://www.macrotrends.net – historical payout ratio & FCF trends",
    "https://simplywall.st – dividend safety scores",
]

# High-yield stocks that have historically shown warning signs.
# Used as a default sample when live screening is not possible.
DEFAULT_WATCH_LIST = [
    "MO",   # Altria – very high yield, rising debt
    "T",    # AT&T – historically unsustainable payout
    "MPW",  # Medical Properties Trust – REIT with FCF issues
    "INTC", # Intel – dividend cut history
    "WBA",  # Walgreens – cut dividend, falling FCF
    "VZ",   # Verizon – high debt load
    "PFE",  # Pfizer – yield spike after patent cliffs
    "OHI",  # Omega Healthcare – REIT with payout concerns
]

CUT_PROBABILITY_THRESHOLDS = {
    "low": (0, 20),
    "moderate": (20, 50),
    "high": (50, 75),
    "very high": (75, 100),
}


@dataclass
class DividendWarning:
    ticker: str
    company: str
    sector: str
    current_yield_pct: float
    payout_ratio_pct: Optional[float]
    free_cash_flow_usd: Optional[float]
    total_debt_usd: Optional[float]
    warning_flags: list[str]
    cut_probability_label: str
    cut_probability_pct: float
    safer_alternatives: list[str]
    data_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Company": self.company,
            "Sector": self.sector,
            "Current Yield": f"{self.current_yield_pct:.2f}%",
            "Payout Ratio": (
                f"{self.payout_ratio_pct:.0f}%" if self.payout_ratio_pct else "N/A"
            ),
            "Free Cash Flow": (
                f"${self.free_cash_flow_usd / 1e9:.2f}B"
                if self.free_cash_flow_usd is not None
                else "N/A"
            ),
            "⚠ Warning Flags": ", ".join(self.warning_flags) if self.warning_flags else "None",
            "Div. Cut Probability": f"{self.cut_probability_label.title()} (~{self.cut_probability_pct:.0f}%)",
            "Safer Alternatives": ", ".join(self.safer_alternatives),
            "Sources": self.data_sources,
        }


SECTOR_SAFE_ALTERNATIVES: dict[str, list[str]] = {
    "Communication Services": ["VZ (if healthy)", "TMUS", "CMCSA"],
    "Consumer Staples": ["PG", "KO", "CL"],
    "Energy": ["CVX", "XOM", "ENB"],
    "Healthcare": ["JNJ", "ABT", "BMY"],
    "Industrials": ["MMM", "ITW", "GWW"],
    "Real Estate": ["O", "NNN", "VICI"],
    "Utilities": ["NEE", "SO", "DUK"],
    "Technology": ["MSFT", "AAPL", "TXN"],
    "Financials": ["JPM", "BLK", "V"],
    "": ["VYM", "SCHD", "HDV"],  # diversified dividend ETFs as fallback
}


def _score_cut_probability(
    payout_ratio: Optional[float],
    fcf: Optional[float],
    debt: Optional[float],
    earnings: Optional[float],
) -> float:
    """
    Heuristic dividend cut probability score (0–100).

    Factors:
    * Payout ratio > 80% → +20 pts, > 100% → +35 pts
    * Negative FCF → +30 pts
    * Debt / earnings > 5× → +15 pts
    """
    score = 0.0
    if payout_ratio is not None:
        if payout_ratio > 100:
            score += 35
        elif payout_ratio > 80:
            score += 20
        elif payout_ratio > 60:
            score += 10
    if fcf is not None and fcf < 0:
        score += 30
    if debt is not None and earnings is not None and earnings > 0:
        leverage = debt / earnings
        if leverage > 5:
            score += 15
        elif leverage > 3:
            score += 7
    return min(score, 99.0)


def _cut_probability_label(score: float) -> str:
    for label, (lo, hi) in CUT_PROBABILITY_THRESHOLDS.items():
        if lo <= score < hi:
            return label
    return "very high"


def _build_warning_flags(
    payout_ratio: Optional[float],
    fcf: Optional[float],
    debt: Optional[float],
    earnings: Optional[float],
    yield_pct: float,
) -> list[str]:
    flags = []
    if payout_ratio is not None and payout_ratio > 80:
        flags.append(f"Payout ratio {payout_ratio:.0f}% > 80%")
    if fcf is not None and fcf < 0:
        flags.append("Negative free cash flow")
    if debt is not None and earnings is not None and earnings > 0:
        if debt / earnings > 5:
            flags.append(f"Debt/Earnings ratio {debt/earnings:.1f}× (very high)")
        elif debt / earnings > 3:
            flags.append(f"Debt/Earnings ratio {debt/earnings:.1f}× (elevated)")
    if yield_pct > 10:
        flags.append(f"Yield {yield_pct:.1f}% may signal market distrust")
    return flags


def analyze_dividend_stock(ticker: str) -> Optional[DividendWarning]:
    """
    Fetch fundamentals for *ticker* and return a DividendWarning if the yield
    exceeds 5% and at least one warning flag is triggered.
    """
    info = get_ticker_info(ticker)
    if not info:
        return None

    yield_val = info.get("dividendYield")
    if not yield_val or yield_val < 0.05:
        return None

    yield_pct = yield_val * 100
    payout_ratio = info.get("payoutRatio")
    if payout_ratio is not None:
        payout_ratio = payout_ratio * 100  # convert to %

    fcf = info.get("freeCashflow")
    total_debt = info.get("totalDebt")
    net_income = info.get("netIncomeToCommon")
    sector = info.get("sector", "")
    company = info.get("longName", ticker)

    score = _score_cut_probability(payout_ratio, fcf, total_debt, net_income)
    flags = _build_warning_flags(payout_ratio, fcf, total_debt, net_income, yield_pct)

    if not flags:
        return None  # No warning signs, skip

    label = _cut_probability_label(score)
    alternatives = SECTOR_SAFE_ALTERNATIVES.get(sector, SECTOR_SAFE_ALTERNATIVES[""])

    return DividendWarning(
        ticker=ticker,
        company=company,
        sector=sector or "Unknown",
        current_yield_pct=yield_pct,
        payout_ratio_pct=payout_ratio,
        free_cash_flow_usd=fcf,
        total_debt_usd=total_debt,
        warning_flags=flags,
        cut_probability_label=label,
        cut_probability_pct=score,
        safer_alternatives=alternatives,
        data_sources=SOURCES,
    )


def screen_dividend_warnings(
    tickers: Optional[list[str]] = None, limit: int = 5
) -> list[DividendWarning]:
    """
    Screen a list of tickers and return up to *limit* dividend warnings.

    If no tickers are provided, uses a built-in watch list.
    """
    watch = tickers or DEFAULT_WATCH_LIST
    warnings: list[DividendWarning] = []

    for t in watch:
        result = analyze_dividend_stock(t)
        if result:
            warnings.append(result)
        if len(warnings) >= limit:
            break

    return warnings
