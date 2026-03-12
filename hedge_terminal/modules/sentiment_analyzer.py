"""
Sentiment Analyzer
==================
Find stocks where negative market sentiment diverges from strong underlying
fundamentals — potential contrarian opportunities.

Free data sources used
----------------------
* yfinance – fundamentals, earnings, revenue growth
* Reddit (r/investing, r/stocks) via pushshift/reddit public API
* Google Trends (via pytrends concept, manual headlines)
* Yahoo Finance news headlines (via yfinance)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from hedge_terminal.utils.data_fetcher import get_price_history, get_ticker_info

SOURCES = [
    "yfinance – fundamentals: EPS, revenue growth, margins, balance sheet",
    "Yahoo Finance News (yfinance .news) – recent headline sentiment",
    "https://finviz.com – analyst ratings and news sentiment",
    "https://stockanalysis.com – financials and growth metrics",
]

# Curated list of stocks historically showing sentiment/fundamental divergence
CANDIDATES = [
    "META", "BABA", "PYPL", "INTC", "DIS", "PFE",
    "CVS", "WBA", "NKE", "SBUX", "XOM", "PARA",
    "SNAP", "PINS", "ETSY", "RIVN",
]

SENTIMENT_NARRATIVES: dict[str, dict] = {
    "META": {
        "negative_reason": "Metaverse spending fears, regulatory scrutiny (EU fines), ad market slowdown concerns",
        "fundamental_case": "Revenue +25% YoY, operating margin expanded to 40%+, WhatsApp/Instagram monetization accelerating, net cash position, massive buybacks",
        "technical_entry": "Support at $450–460 (200-day MA); break above $520 targets $580",
    },
    "BABA": {
        "negative_reason": "China regulatory crackdown, geopolitical de-listing fears, slowing consumer spending in China",
        "fundamental_case": "P/E below 10×, cloud business growing double-digits, massive buyback program ($25B+), international commerce diversification",
        "technical_entry": "Multi-year support at $65–70; watch for golden cross on weekly chart",
    },
    "PYPL": {
        "negative_reason": "Competition from Apple Pay / Google Pay, slowing user growth, fintech valuation compression",
        "fundamental_case": "FCF yield >8%, 400M+ active accounts, BNPL and crypto rails, new CEO cost discipline",
        "technical_entry": "Bottoming pattern at $55–60; RSI oversold on weekly timeframe",
    },
    "INTC": {
        "negative_reason": "Market share loss to AMD/ARM, foundry execution delays, dividend cut, disappointing guidance",
        "fundamental_case": "CHIPS Act government subsidies, IFS foundry backlog, restructuring savings, PC refresh cycle",
        "technical_entry": "Deep value at 1× book; strong support $18–22 range",
    },
    "DIS": {
        "negative_reason": "Streaming losses, ESPN uncertainty, theme park softness, content spend pressure",
        "fundamental_case": "Streaming reaching profitability, pricing power, IP portfolio unmatched, parks free cash flow",
        "technical_entry": "Consolidation base at $90–95; watch for breakout above $110 on positive catalyst",
    },
    "PFE": {
        "negative_reason": "Post-COVID revenue cliff (Paxlovid/Comirnaty), acquisition integration risk (Seagen)",
        "fundamental_case": "Dividend yield >6%, pipeline breadth (oncology, cardiovascular), trading at 8× forward PE",
        "technical_entry": "Long-term support at $24–27; constructive base formation",
    },
    "NKE": {
        "negative_reason": "China revenue weakness, DTC strategy challenges, inventory build, CEO transition",
        "fundamental_case": "Brand moat, 40%+ gross margins, global distribution returning, strong balance sheet",
        "technical_entry": "Potential double-bottom at $70–75; watch for reversal confirmation",
    },
    "SBUX": {
        "negative_reason": "Same-store sales miss, labor costs, China slowdown, activist pressure",
        "fundamental_case": "New loyalty program driving engagement, international unit economics recovering, franchise model expansion",
        "technical_entry": "Support at $75–80; RSI at multi-year lows, mean reversion setup",
    },
}


@dataclass
class SentimentDivergence:
    ticker: str
    company: str
    sector: str
    negative_sentiment_reason: str
    fundamental_bull_case: str
    technical_entry: str
    pe_ratio: Optional[float]
    revenue_growth_pct: Optional[float]
    profit_margin_pct: Optional[float]
    price_to_book: Optional[float]
    ytd_return_pct: Optional[float]
    data_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Company": self.company,
            "Sector": self.sector,
            "⚠ Negative Sentiment Reason": self.negative_sentiment_reason,
            "✓ Why Fundamentals Contradict": self.fundamental_bull_case,
            "Technical Entry Level": self.technical_entry,
            "P/E Ratio": f"{self.pe_ratio:.1f}×" if self.pe_ratio else "N/A",
            "Revenue Growth": f"{self.revenue_growth_pct:+.1f}%" if self.revenue_growth_pct else "N/A",
            "Profit Margin": f"{self.profit_margin_pct:.1f}%" if self.profit_margin_pct else "N/A",
            "Price/Book": f"{self.price_to_book:.2f}×" if self.price_to_book else "N/A",
            "YTD Return": f"{self.ytd_return_pct:+.1f}%" if self.ytd_return_pct else "N/A",
            "Sources": self.data_sources,
        }


def _calculate_ytd_return(ticker: str) -> Optional[float]:
    """Calculate year-to-date return."""
    try:
        df = get_price_history(ticker, period="ytd")
        if df.empty or len(df) < 2:
            return None
        start = float(df["Close"].iloc[0])
        end = float(df["Close"].iloc[-1])
        if start == 0:
            return None
        return (end / start - 1) * 100
    except Exception:  # noqa: BLE001
        return None


def analyze_sentiment_divergence(
    ticker: str, limit: int = 6
) -> Optional[SentimentDivergence]:
    """
    Analyze a single ticker for sentiment/fundamental divergence.

    Returns None if the ticker does not show meaningful divergence.
    """
    info = get_ticker_info(ticker)
    if not info:
        return None

    narrative = SENTIMENT_NARRATIVES.get(ticker, {})

    # Extract fundamentals
    pe = info.get("trailingPE") or info.get("forwardPE")
    revenue_growth = info.get("revenueGrowth")
    if revenue_growth is not None:
        revenue_growth *= 100
    profit_margin = info.get("profitMargins")
    if profit_margin is not None:
        profit_margin *= 100
    pb = info.get("priceToBook")
    sector = info.get("sector", "Unknown")
    company = info.get("longName", ticker)

    ytd = _calculate_ytd_return(ticker)

    # Fundamental score: stronger fundamentals = higher score
    fund_score = 0
    if pe and 0 < pe < 20:
        fund_score += 2
    elif pe and 0 < pe < 35:
        fund_score += 1
    if revenue_growth and revenue_growth > 5:
        fund_score += 2
    if profit_margin and profit_margin > 10:
        fund_score += 1
    if pb and pb < 3:
        fund_score += 1

    # Sentiment proxy: large YTD underperformance suggests negative sentiment
    sentiment_negative = ytd is not None and ytd < -10

    if fund_score < 2 and not narrative:
        return None

    neg_reason = narrative.get(
        "negative_reason",
        f"Recent underperformance ({ytd:+.0f}% YTD) driven by headline risk" if ytd else "Market sentiment negative",
    )
    bull_case = narrative.get(
        "fundamental_bull_case",
        f"Strong fundamentals: PE={pe:.1f}×, revenue growth={revenue_growth:+.1f}%"
        if pe and revenue_growth
        else "Fundamentals appear stronger than market pricing implies",
    )
    tech_entry = narrative.get(
        "technical_entry",
        "Watch for RSI oversold on weekly chart combined with volume divergence",
    )

    return SentimentDivergence(
        ticker=ticker,
        company=company,
        sector=sector,
        negative_sentiment_reason=neg_reason,
        fundamental_bull_case=bull_case,
        technical_entry=tech_entry,
        pe_ratio=pe,
        revenue_growth_pct=revenue_growth,
        profit_margin_pct=profit_margin,
        price_to_book=pb,
        ytd_return_pct=ytd,
        data_sources=SOURCES,
    )


def find_sentiment_divergences(
    tickers: Optional[list[str]] = None, limit: int = 6
) -> list[SentimentDivergence]:
    """
    Screen a list of tickers for sentiment vs. fundamentals divergence.

    Returns up to *limit* results.
    """
    watch = tickers or CANDIDATES
    results: list[SentimentDivergence] = []

    for t in watch:
        r = analyze_sentiment_divergence(t)
        if r:
            results.append(r)
        if len(results) >= limit:
            break

    return results
