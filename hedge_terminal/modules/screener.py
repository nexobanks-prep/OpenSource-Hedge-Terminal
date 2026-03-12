"""
Equity Screener Module
======================
Screen stocks by fundamental and technical criteria.

Replicates Bloomberg Terminal's **EQSRCH / EQS** function and
OpenBB Terminal's ``stocks screener`` command — for free, using yfinance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hedge_terminal.utils.data_fetcher import get_ticker_info


# ---------------------------------------------------------------------------
# Screening criteria dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScreenCriteria:
    """
    Criteria for the equity screener.  All bounds are *inclusive*.
    ``None`` means "no constraint on that side".
    """

    # Valuation
    max_pe: float | None = None          # trailing P/E
    min_pe: float | None = None
    max_pb: float | None = None          # price / book
    max_ev_ebitda: float | None = None   # EV/EBITDA

    # Growth
    min_revenue_growth: float | None = None   # YoY, as fraction (0.10 = 10 %)
    min_earnings_growth: float | None = None  # YoY, as fraction

    # Profitability
    min_profit_margin: float | None = None    # net profit margin, fraction
    min_roe: float | None = None              # return on equity, fraction

    # Income
    min_dividend_yield: float | None = None   # fraction (0.03 = 3 %)
    max_payout_ratio: float | None = None     # fraction

    # Size
    min_market_cap: float | None = None       # USD
    max_market_cap: float | None = None

    # Debt
    max_debt_to_equity: float | None = None

    # Technical
    min_beta: float | None = None
    max_beta: float | None = None


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScreenResult:
    ticker: str
    company_name: str
    sector: str
    industry: str
    market_cap: float | None
    pe_ratio: float | None
    pb_ratio: float | None
    ev_ebitda: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    profit_margin: float | None
    roe: float | None
    dividend_yield_pct: float | None
    payout_ratio: float | None
    debt_to_equity: float | None
    beta: float | None
    passed_criteria: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, str]:
        def _pct(v: float | None) -> str:
            return f"{v * 100:.1f}%" if v is not None else "N/A"

        def _fmt(v: float | None, dec: int = 2) -> str:
            return f"{v:.{dec}f}" if v is not None else "N/A"

        def _mc(v: float | None) -> str:
            if v is None:
                return "N/A"
            if v >= 1e12:
                return f"${v / 1e12:.2f}T"
            if v >= 1e9:
                return f"${v / 1e9:.2f}B"
            if v >= 1e6:
                return f"${v / 1e6:.2f}M"
            return f"${v:,.0f}"

        return {
            "Ticker": self.ticker,
            "Company": self.company_name,
            "Sector": self.sector or "N/A",
            "Industry": self.industry or "N/A",
            "Market Cap": _mc(self.market_cap),
            "P/E": _fmt(self.pe_ratio),
            "P/B": _fmt(self.pb_ratio),
            "EV/EBITDA": _fmt(self.ev_ebitda),
            "Rev Growth": _pct(self.revenue_growth),
            "EPS Growth": _pct(self.earnings_growth),
            "Net Margin": _pct(self.profit_margin),
            "ROE": _pct(self.roe),
            # dividend_yield_pct is stored as a plain percentage (e.g. 4.0 for 4%).
            # _pct() expects a fraction (e.g. 0.04), so divide by 100 before passing.
            "Div Yield": _pct(self.dividend_yield_pct / 100) if self.dividend_yield_pct else "N/A",
            "Payout Ratio": _pct(self.payout_ratio),
            "D/E": _fmt(self.debt_to_equity),
            "Beta": _fmt(self.beta),
            "✓ Criteria": ", ".join(self.passed_criteria) if self.passed_criteria else "—",
        }


# ---------------------------------------------------------------------------
# Screening logic
# ---------------------------------------------------------------------------

def _passes(criteria: ScreenCriteria, result: ScreenResult) -> list[str]:
    """
    Check all criteria.  Returns a list of criterion names that PASSED.
    Returns an empty list if *any* hard constraint is violated.
    """
    passed: list[str] = []
    violated = False

    def _check(
        name: str,
        value: float | None,
        lo: float | None,
        hi: float | None,
    ) -> None:
        nonlocal violated
        if value is None:
            return  # skip missing data rather than reject
        if lo is not None and value < lo:
            violated = True
            return
        if hi is not None and value > hi:
            violated = True
            return
        passed.append(name)

    _check("P/E", result.pe_ratio, criteria.min_pe, criteria.max_pe)
    _check("P/B", result.pb_ratio, None, criteria.max_pb)
    _check("EV/EBITDA", result.ev_ebitda, None, criteria.max_ev_ebitda)
    _check("Rev Growth", result.revenue_growth, criteria.min_revenue_growth, None)
    _check("EPS Growth", result.earnings_growth, criteria.min_earnings_growth, None)
    _check("Net Margin", result.profit_margin, criteria.min_profit_margin, None)
    _check("ROE", result.roe, criteria.min_roe, None)
    _check(
        "Div Yield",
        result.dividend_yield_pct / 100 if result.dividend_yield_pct else None,
        criteria.min_dividend_yield,
        None,
    )
    _check(
        "Payout Ratio",
        result.payout_ratio,
        None,
        criteria.max_payout_ratio,
    )
    _check("Market Cap", result.market_cap, criteria.min_market_cap, criteria.max_market_cap)
    _check("D/E", result.debt_to_equity, None, criteria.max_debt_to_equity)
    _check("Beta", result.beta, criteria.min_beta, criteria.max_beta)

    if violated:
        return []
    return passed


def _fetch_result(ticker: str) -> ScreenResult:
    """Fetch fundamental data for one ticker and return a :class:`ScreenResult`."""
    info: dict[str, Any] = get_ticker_info(ticker.upper())

    div_yield = info.get("dividendYield")
    if div_yield is not None:
        div_yield = div_yield * 100  # 0.04 → 4.0

    return ScreenResult(
        ticker=ticker.upper(),
        company_name=info.get("longName") or info.get("shortName") or ticker,
        sector=info.get("sector") or "",
        industry=info.get("industry") or "",
        market_cap=info.get("marketCap"),
        pe_ratio=info.get("trailingPE"),
        pb_ratio=info.get("priceToBook"),
        ev_ebitda=info.get("enterpriseToEbitda"),
        revenue_growth=info.get("revenueGrowth"),
        earnings_growth=info.get("earningsGrowth"),
        profit_margin=info.get("profitMargins"),
        roe=info.get("returnOnEquity"),
        dividend_yield_pct=div_yield,
        payout_ratio=info.get("payoutRatio"),
        debt_to_equity=info.get("debtToEquity"),
        beta=info.get("beta"),
    )


# ---------------------------------------------------------------------------
# Pre-built screener presets
# ---------------------------------------------------------------------------

# A broad universe of well-known, liquid tickers used when no custom list
# is provided.  Intentionally diverse across sectors.
DEFAULT_UNIVERSE: list[str] = [
    # Technology
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "INTC", "AMD", "ORCL", "CRM", "ADBE",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "AXP", "V", "MA",
    # Healthcare
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "BMY", "ABT",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY",
    # Consumer
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "WMT", "COST",
    # Industrials
    "BA", "CAT", "GE", "HON", "MMM", "RTX", "LMT",
    # REITs / Income
    "O", "MPW", "AMT", "PLD",
    # Telecom / Utilities
    "T", "VZ", "NEE", "DUK",
    # International / ADR
    "BABA", "TSM", "ASML", "SAP",
]

PRESETS: dict[str, ScreenCriteria] = {
    "value": ScreenCriteria(
        max_pe=15.0,
        max_pb=2.0,
        min_profit_margin=0.05,
        max_debt_to_equity=150.0,
    ),
    "growth": ScreenCriteria(
        min_revenue_growth=0.15,
        min_earnings_growth=0.15,
        min_profit_margin=0.08,
    ),
    "dividend": ScreenCriteria(
        min_dividend_yield=0.03,
        max_payout_ratio=0.75,
        min_profit_margin=0.05,
    ),
    "quality": ScreenCriteria(
        min_profit_margin=0.15,
        min_roe=0.15,
        max_debt_to_equity=100.0,
        min_revenue_growth=0.05,
    ),
    "low_volatility": ScreenCriteria(
        max_beta=0.8,
        min_profit_margin=0.05,
        max_debt_to_equity=100.0,
    ),
}


def screen_equities(
    criteria: ScreenCriteria,
    universe: list[str] | None = None,
    limit: int = 10,
) -> list[ScreenResult]:
    """
    Screen *universe* against *criteria* and return up to *limit* results.

    Parameters
    ----------
    criteria:
        Screening filters.
    universe:
        Tickers to evaluate.  Defaults to :data:`DEFAULT_UNIVERSE`.
    limit:
        Maximum number of matching results to return.
    """
    if universe is None:
        universe = DEFAULT_UNIVERSE

    results: list[ScreenResult] = []
    for ticker in universe:
        if len(results) >= limit:
            break
        try:
            r = _fetch_result(ticker)
            passed = _passes(criteria, r)
            if passed:
                r.passed_criteria = passed
                results.append(r)
        except Exception:  # noqa: BLE001
            pass
    return results
