"""
Hedge Designer
==============
Design an efficient portfolio hedge using options or inverse ETFs.

Free data sources used
----------------------
* yfinance – options chains, implied volatility, historical prices
* CBOE VIX (via yfinance ticker ^VIX)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from hedge_terminal.utils.data_fetcher import (
    get_options_chain,
    get_price_history,
    get_ticker_info,
)

# Map broad sector/market exposures to candidate inverse ETFs.
INVERSE_ETF_MAP: dict[str, list[dict]] = {
    "technology": [
        {"ticker": "SQQQ", "name": "ProShares UltraPro Short QQQ", "leverage": -3},
        {"ticker": "REW", "name": "ProShares UltraShort Technology", "leverage": -2},
    ],
    "financials": [
        {"ticker": "SKF", "name": "ProShares UltraShort Financials", "leverage": -2},
        {"ticker": "FAZ", "name": "Direxion Daily Financial Bear 3x", "leverage": -3},
    ],
    "energy": [
        {"ticker": "ERY", "name": "Direxion Daily Energy Bear 2x", "leverage": -2},
        {"ticker": "DRIP", "name": "Direxion Daily S&P Oil & Gas E&P Bear 2x", "leverage": -2},
    ],
    "healthcare": [
        {"ticker": "RXD", "name": "ProShares UltraShort Health Care", "leverage": -2},
    ],
    "real estate": [
        {"ticker": "SRS", "name": "ProShares UltraShort Real Estate", "leverage": -2},
        {"ticker": "DRV", "name": "Direxion Daily Real Estate Bear 3x", "leverage": -3},
    ],
    "broad market": [
        {"ticker": "SH", "name": "ProShares Short S&P500", "leverage": -1},
        {"ticker": "SDS", "name": "ProShares UltraShort S&P500", "leverage": -2},
        {"ticker": "SPXS", "name": "Direxion Daily S&P 500 Bear 3x", "leverage": -3},
    ],
    "bonds": [
        {"ticker": "TBF", "name": "ProShares Short 20+ Year Treasury", "leverage": -1},
        {"ticker": "TBT", "name": "ProShares UltraShort 20+ Year Treasury", "leverage": -2},
    ],
    "emerging markets": [
        {"ticker": "EEV", "name": "ProShares UltraShort MSCI Emerging Mkts", "leverage": -2},
        {"ticker": "EDZ", "name": "Direxion Daily MSCI Emerging Mkts Bear 3x", "leverage": -3},
    ],
}


@dataclass
class HedgeRecommendation:
    sector: str
    recommended_instrument: str
    instrument_name: str
    hedge_size_pct: float  # as a % of portfolio
    annualized_cost_pct: float
    activation_scenario: str
    current_vix: float
    implied_volatility: Optional[float]
    data_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "Sector / Market": self.sector,
            "Recommended Instrument": self.recommended_instrument,
            "Instrument Name": self.instrument_name,
            "Hedge Size (% of Portfolio)": f"{self.hedge_size_pct:.1f}%",
            "Annualized Cost (est.)": f"{self.annualized_cost_pct:.2f}%",
            "Activation Scenario": self.activation_scenario,
            "Current VIX": f"{self.current_vix:.2f}",
            "Near-ATM IV (portfolio proxy)": (
                f"{self.implied_volatility:.1f}%" if self.implied_volatility else "N/A"
            ),
            "Data Sources": self.data_sources,
        }


def _get_vix() -> float:
    """Return the latest VIX close."""
    try:
        df = get_price_history("^VIX", period="5d")
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except Exception:  # noqa: BLE001
        pass
    return 20.0  # sensible default


def _nearest_atm_iv(ticker: str) -> Optional[float]:
    """Return near-ATM implied volatility for the nearest expiry (as %)."""
    try:
        chain = get_options_chain(ticker)
        puts = chain.get("puts", pd.DataFrame())
        if puts.empty:
            return None
        info = get_ticker_info(ticker)
        spot = info.get("regularMarketPrice") or info.get("currentPrice")
        if not spot:
            return None
        puts = puts.copy()
        puts["dist"] = (puts["strike"] - spot).abs()
        atm_row = puts.loc[puts["dist"].idxmin()]
        iv = atm_row.get("impliedVolatility")
        if iv is not None:
            return float(iv) * 100
    except Exception:  # noqa: BLE001
        pass
    return None


def _estimate_put_cost(iv_pct: float, vix: float, days: int = 90) -> float:
    """
    Rough annualized cost of an at-the-money put option as a % of notional,
    using Black-Scholes approximation: cost ≈ IV * sqrt(T/252) * (0.4).
    Multiplied by (252/days) to annualize.
    """
    iv = (iv_pct if iv_pct else vix) / 100
    t = days / 252
    premium_pct = iv * np.sqrt(t) * 0.4 * 100
    annualized = premium_pct * (252 / days)
    return round(annualized, 2)


def _hedge_size(vix: float) -> float:
    """
    Return recommended hedge size as a fraction of portfolio based on VIX regime.

    VIX < 15  → low vol, 5–8% hedge
    VIX 15-25 → moderate, 8–12% hedge
    VIX > 25  → elevated, 12–20% hedge
    """
    if vix < 15:
        return 6.0
    elif vix < 25:
        return 10.0
    else:
        return 15.0


def _activation_scenario(sector: str, vix: float) -> str:
    base = (
        "Activate hedge if VIX closes above {threshold} for two consecutive days "
        "OR if the {sector} sector ETF drops more than {drop}% in a single week."
    )
    if vix < 15:
        return base.format(
            threshold=20, sector=sector.title(), drop=5
        )
    elif vix < 25:
        return base.format(
            threshold=30, sector=sector.title(), drop=7
        )
    else:
        return base.format(
            threshold=35, sector=sector.title(), drop=10
        )


def design_hedge(
    sector: str,
    portfolio_ticker: str = "SPY",
    prefer_puts: bool = False,
) -> HedgeRecommendation:
    """
    Design a hedge for the given sector/market exposure.

    Parameters
    ----------
    sector:
        The sector or market the portfolio is exposed to (e.g. "technology").
    portfolio_ticker:
        A representative ETF for the portfolio exposure used to pull IV.
    prefer_puts:
        If True, skips inverse ETFs and recommends put options directly.

    Returns
    -------
    HedgeRecommendation
    """
    sector_lower = sector.strip().lower()
    vix = _get_vix()
    iv = _nearest_atm_iv(portfolio_ticker)

    candidates = INVERSE_ETF_MAP.get(
        sector_lower, INVERSE_ETF_MAP["broad market"]
    )

    # Prefer 1× or 2× leverage when vol is already elevated to avoid decay drag
    preferred_leverage = -2 if vix < 25 else -1
    chosen = candidates[0]
    for c in candidates:
        if c["leverage"] == preferred_leverage:
            chosen = c
            break

    hedge_size = _hedge_size(vix)
    cost_pct = _estimate_put_cost(iv or vix, vix)
    activation = _activation_scenario(sector_lower, vix)

    sources = [
        "CBOE VIX (^VIX via yfinance) – volatility regime",
        "yfinance options chain – near-ATM implied volatility",
        "ETF provider prospectuses (ProShares / Direxion) – instrument specs",
        "https://www.cboe.com/tradable_products/vix/ – VIX methodology",
    ]

    if prefer_puts:
        return HedgeRecommendation(
            sector=sector,
            recommended_instrument=f"ATM put on {portfolio_ticker}",
            instrument_name=f"At-the-money put option on {portfolio_ticker} (~90-day expiry)",
            hedge_size_pct=hedge_size,
            annualized_cost_pct=cost_pct,
            activation_scenario=activation,
            current_vix=vix,
            implied_volatility=iv,
            data_sources=sources,
        )

    return HedgeRecommendation(
        sector=sector,
        recommended_instrument=chosen["ticker"],
        instrument_name=chosen["name"],
        hedge_size_pct=hedge_size,
        annualized_cost_pct=cost_pct,
        activation_scenario=activation,
        current_vix=vix,
        implied_volatility=iv,
        data_sources=sources,
    )
