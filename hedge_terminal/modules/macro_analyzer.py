"""
Macro Analyzer
==============
Fetch current macroeconomic context (inflation, rates, GDP, employment) and
identify sectors/assets that historically outperform in this regime.

Free data sources used
----------------------
* FRED (St. Louis Fed) – CPI, Fed Funds Rate, GDP, unemployment
* yfinance – sector ETF performance
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from hedge_terminal.utils.data_fetcher import fetch_fred_series, get_price_history

SOURCES = [
    "https://fred.stlouisfed.org – CPI (CPIAUCSL), Fed Funds (FEDFUNDS), GDP (GDP), Unemployment (UNRATE)",
    "https://www.bls.gov – Bureau of Labor Statistics (CPI, employment)",
    "https://www.bea.gov – Bureau of Economic Analysis (GDP, PCE)",
    "https://www.federalreserve.gov – FOMC statements and policy rate",
    "https://www.ecb.europa.eu – ECB monetary policy",
]

# Sector ETFs for performance analysis
SECTOR_ETFS: dict[str, str] = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Utilities": "XLU",
    "Materials": "XLB",
    "Industrials": "XLI",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Gold": "GLD",
    "Commodities": "DJP",
    "Short-Term Bonds": "SHY",
    "Long-Term Bonds": "TLT",
    "TIPS (Inflation-Protected)": "TIP",
    "International Developed": "EFA",
    "Emerging Markets": "EEM",
}

# Regime-based outperformance lookup
# Key: (inflation_regime, rate_regime, growth_regime)
# inflation: "low" (<2%), "moderate" (2-4%), "high" (>4%)
# rate: "falling", "stable", "rising"
# growth: "recession" (<0%), "slow" (0-2%), "moderate" (2-4%), "strong" (>4%)
REGIME_PLAYBOOK: dict[tuple[str, str, str], dict] = {
    ("high", "rising", "slow"): {
        "label": "Stagflation",
        "outperformers": ["Energy", "Gold", "Commodities", "Consumer Staples", "TIPS (Inflation-Protected)"],
        "underperformers": ["Technology", "Real Estate", "Long-Term Bonds", "Consumer Discretionary"],
        "rationale": "Hard assets and inflation hedges outperform when growth disappoints but inflation persists.",
        "examples": [
            "1970s OPEC oil shock stagflation (1973–1975): gold +200%, bonds crushed",
            "2022 Fed tightening: commodities +40%, QQQ -35%",
            "Early 1980s: energy/materials outperformed until Volcker pivot",
        ],
        "timeframe": "Typically lasts 1–3 years; watch for Fed pivot as normalization signal",
    },
    ("high", "rising", "moderate"): {
        "label": "Inflationary Growth (Boom with Rising Rates)",
        "outperformers": ["Energy", "Financials", "Materials", "Industrials"],
        "underperformers": ["Long-Term Bonds", "Utilities", "Real Estate", "Technology"],
        "rationale": "Cyclicals and commodities benefit from strong demand; rate-sensitive sectors lag.",
        "examples": [
            "2004–2006: Fed rate hike cycle with strong growth — banks and energy led",
            "1994–1995: Surprise Fed hikes, cyclicals outperformed defensive bonds",
            "2021: Reopening trade with rising inflation — energy/materials surged",
        ],
        "timeframe": "Typically 1–2 years until rates bite growth",
    },
    ("low", "falling", "recession"): {
        "label": "Deflationary Recession / Risk-Off",
        "outperformers": ["Long-Term Bonds", "Gold", "Consumer Staples", "Utilities", "Healthcare"],
        "underperformers": ["Energy", "Financials", "Materials", "Consumer Discretionary"],
        "rationale": "Flight to safety; bonds rally as rates are cut; defensive sectors preserve capital.",
        "examples": [
            "2008–2009 GFC: TLT +25%, SPY -55%; gold held value",
            "2020 COVID crash: initial bond/gold flight before equity V-recovery",
            "2001–2002 dot-com bust: defensives and bonds significantly outperformed",
        ],
        "timeframe": "Bear markets average 14 months; recovery phase begins 6 months before economic trough",
    },
    ("moderate", "stable", "moderate"): {
        "label": "Goldilocks (Moderate Growth, Controlled Inflation)",
        "outperformers": ["Technology", "Consumer Discretionary", "Communication Services", "Financials"],
        "underperformers": ["Utilities", "Consumer Staples", "Gold", "Short-Term Bonds"],
        "rationale": "Risk-on environment favors growth and cyclicals; safe havens underperform on relative basis.",
        "examples": [
            "2017: Low volatility, moderate growth — tech/discretionary surged",
            "1995–1999: Goldilocks era — tech boom, minimal inflation",
            "2013 tapering scare recovery — broad equity rally into 2014",
        ],
        "timeframe": "Can persist 2–5 years; ends when inflation or recession materializes",
    },
    ("low", "rising", "moderate"): {
        "label": "Tightening Cycle with Low Inflation",
        "outperformers": ["Financials", "Technology", "Healthcare", "Consumer Discretionary"],
        "underperformers": ["Utilities", "Real Estate", "Long-Term Bonds", "Emerging Markets"],
        "rationale": "Rising rates with contained inflation allows sustained equity expansion; rate-sensitive sectors lag.",
        "examples": [
            "2015–2018 gradual Fed hikes: equities broadly positive, REIT/utilities lagged",
            "2004–2006: Slow tightening, equities positive overall",
            "1994 surprise hike: short-term pain then recovery through 1995–1999 boom",
        ],
        "timeframe": "Equities positive for 1–2 years into cycle; watch for credit spreads widening",
    },
    ("moderate", "falling", "slow"): {
        "label": "Soft Landing / Fed Pivot",
        "outperformers": ["Technology", "Real Estate", "Long-Term Bonds", "Consumer Discretionary", "Emerging Markets"],
        "underperformers": ["Energy", "Commodities", "Short-Term Bonds"],
        "rationale": "Rate cuts boost duration assets, growth stocks, and rate-sensitive sectors.",
        "examples": [
            "1995 Greenspan soft landing: S&P 500 +34%, bonds rallied",
            "1998 LTCM/Asia crisis rate cuts: tech stocks surged into dot-com peak",
            "2019 mid-cycle rate cuts: growth/tech led broad rally",
        ],
        "timeframe": "Initial equity rally of 6–18 months post-pivot, especially in rate-sensitive sectors",
    },
}


@dataclass
class MacroContext:
    cpi_yoy: Optional[float]
    fed_funds_rate: Optional[float]
    gdp_growth_qoq: Optional[float]
    unemployment_rate: Optional[float]
    inflation_regime: str
    rate_regime: str
    growth_regime: str
    regime_label: str
    outperforming_sectors: list[str]
    underperforming_sectors: list[str]
    rationale: str
    historical_examples: list[str]
    timeframe: str
    sector_ytd_returns: dict[str, float]
    data_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "CPI (YoY %)": f"{self.cpi_yoy:.1f}%" if self.cpi_yoy else "N/A",
            "Fed Funds Rate": f"{self.fed_funds_rate:.2f}%" if self.fed_funds_rate else "N/A",
            "GDP Growth (QoQ ann.)": f"{self.gdp_growth_qoq:.1f}%" if self.gdp_growth_qoq else "N/A",
            "Unemployment Rate": f"{self.unemployment_rate:.1f}%" if self.unemployment_rate else "N/A",
            "Macro Regime": self.regime_label,
            "Historically Outperforming": self.outperforming_sectors,
            "Historically Underperforming": self.underperforming_sectors,
            "Rationale": self.rationale,
            "Historical Examples": self.historical_examples,
            "Expected Timeframe": self.timeframe,
            "Sector YTD Returns": {
                k: f"{v:+.1f}%" for k, v in self.sector_ytd_returns.items()
            },
            "Sources": self.data_sources,
        }


def _classify_inflation(cpi: Optional[float]) -> str:
    if cpi is None:
        return "moderate"
    if cpi < 2:
        return "low"
    if cpi <= 4:
        return "moderate"
    return "high"


def _classify_rate_regime(
    current: Optional[float], prev_6m: Optional[float]
) -> str:
    if current is None:
        return "stable"
    if prev_6m is None:
        return "stable"
    delta = current - prev_6m
    if delta > 0.25:
        return "rising"
    if delta < -0.25:
        return "falling"
    return "stable"


def _classify_growth(gdp: Optional[float]) -> str:
    if gdp is None:
        return "moderate"
    if gdp < 0:
        return "recession"
    if gdp < 2:
        return "slow"
    if gdp <= 4:
        return "moderate"
    return "strong"


def _fetch_macro_data() -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Fetch CPI, Fed Funds Rate, GDP growth, and unemployment from FRED.

    Returns (cpi_yoy, fed_funds_rate, gdp_growth_qoq, unemployment_rate).
    """
    cpi_series = fetch_fred_series("CPIAUCSL")
    fed_series = fetch_fred_series("FEDFUNDS")
    gdp_series = fetch_fred_series("A191RL1Q225SBEA")  # Real GDP growth rate
    unemp_series = fetch_fred_series("UNRATE")

    def latest(s: pd.Series) -> Optional[float]:
        if s.empty:
            return None
        return float(s.iloc[-1])

    def yoy(s: pd.Series) -> Optional[float]:
        """Year-over-year % change."""
        if len(s) < 12:
            return None
        try:
            recent = float(s.iloc[-1])
            year_ago = float(s.iloc[-13])
            return (recent / year_ago - 1) * 100
        except Exception:  # noqa: BLE001
            return None

    cpi = yoy(cpi_series)
    ffr = latest(fed_series)
    gdp = latest(gdp_series)
    unemp = latest(unemp_series)

    return cpi, ffr, gdp, unemp


def _get_sector_ytd_returns() -> dict[str, float]:
    """Download YTD returns for all sector ETFs."""
    returns: dict[str, float] = {}
    for name, ticker in SECTOR_ETFS.items():
        try:
            df = get_price_history(ticker, period="ytd")
            if not df.empty and len(df) >= 2:
                start = float(df["Close"].iloc[0])
                end = float(df["Close"].iloc[-1])
                if start:
                    returns[name] = round((end / start - 1) * 100, 1)
        except Exception:  # noqa: BLE001
            pass
    return returns


def get_macro_context() -> MacroContext:
    """
    Fetch current macro data, classify the regime, and return sector
    outperformance recommendations with historical examples.
    """
    cpi, ffr, gdp, unemp = _fetch_macro_data()

    inflation_regime = _classify_inflation(cpi)
    gdp_regime = _classify_growth(gdp)

    # Need previous Fed Funds Rate to determine rate direction
    ffr_series = fetch_fred_series("FEDFUNDS")
    if len(ffr_series) >= 7:
        prev_6m = float(ffr_series.iloc[-7])
    else:
        prev_6m = ffr
    rate_regime = _classify_rate_regime(ffr, prev_6m)

    key = (inflation_regime, rate_regime, gdp_regime)
    playbook = REGIME_PLAYBOOK.get(
        key,
        # Default to goldilocks if key not found
        REGIME_PLAYBOOK[("moderate", "stable", "moderate")],
    )

    sector_returns = _get_sector_ytd_returns()

    return MacroContext(
        cpi_yoy=cpi,
        fed_funds_rate=ffr,
        gdp_growth_qoq=gdp,
        unemployment_rate=unemp,
        inflation_regime=inflation_regime,
        rate_regime=rate_regime,
        growth_regime=gdp_regime,
        regime_label=playbook["label"],
        outperforming_sectors=playbook["outperformers"],
        underperforming_sectors=playbook["underperformers"],
        rationale=playbook["rationale"],
        historical_examples=playbook["examples"],
        timeframe=playbook["timeframe"],
        sector_ytd_returns=sector_returns,
        data_sources=SOURCES,
    )
