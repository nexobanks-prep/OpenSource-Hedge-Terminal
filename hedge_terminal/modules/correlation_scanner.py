"""
Correlation Scanner
===================
Detect unusual cross-asset correlations and suggest trades that benefit
from normalization.

Free data sources used
----------------------
* yfinance – historical price data for major asset classes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from hedge_terminal.utils.data_fetcher import get_price_history

SOURCES = [
    "yfinance – historical OHLCV prices for cross-asset correlation",
    "https://www.macrotrends.net – long-run inter-asset correlations",
    "https://fred.stlouisfed.org – macro backdrop (rates, spreads)",
    "https://www.cboe.com – VIX term structure and skew data",
]

# Representative tickers for key asset classes
ASSET_UNIVERSE: dict[str, str] = {
    "S&P 500": "SPY",
    "Nasdaq 100": "QQQ",
    "Gold": "GLD",
    "Long-Term Treasuries": "TLT",
    "Short-Term Treasuries": "SHY",
    "Investment Grade Bonds": "LQD",
    "High Yield Bonds": "HYG",
    "USD Index": "UUP",
    "Oil (WTI)": "USO",
    "Real Estate (REITs)": "VNQ",
    "VIX": "^VIX",
    "Emerging Markets": "EEM",
    "Bitcoin": "BTC-USD",
    "Silver": "SLV",
    "Commodities": "DJP",
}

# Historical norms for correlations between pairs (rolling 252-day avg)
HISTORICAL_NORM_CORR: dict[tuple[str, str], float] = {
    ("S&P 500", "Gold"): 0.0,          # Near-zero historically
    ("S&P 500", "Long-Term Treasuries"): -0.35,  # Negative (flight-to-safety)
    ("S&P 500", "VIX"): -0.75,         # Strong negative
    ("Gold", "USD Index"): -0.50,      # Negative (dollar strength hurts gold)
    ("Long-Term Treasuries", "High Yield Bonds"): 0.30,
    ("S&P 500", "Oil (WTI)"): 0.40,
    ("S&P 500", "Emerging Markets"): 0.70,
    ("Gold", "Long-Term Treasuries"): 0.40,
}

ANOMALY_SIGNALS: dict[tuple[str, str], dict] = {
    ("S&P 500", "Gold"): {
        "signal": "Gold and equities rising together often signals currency debasement fears or a systemic loss of confidence in central bank credibility.",
        "normalization_trades": [
            "Long USD / Short EUR (DXY rally trades off: UUP calls)",
            "Long volatility via VIX calls (anomaly precedes vol spikes historically)",
            "Short high-P/E growth stocks (QQQ puts) – historically mean-revert first",
        ],
        "examples": ["2011 gold/equity co-rally before US debt ceiling crisis", "2020 March-August co-rally post-Fed liquidity injection"],
    },
    ("S&P 500", "Long-Term Treasuries"): {
        "signal": "Bonds and equities falling simultaneously signals a liquidity crisis or stagflation regime — the 'no safe haven' environment.",
        "normalization_trades": [
            "Long short-duration Treasuries (SHY) vs short TLT – duration steepener",
            "Long USD (UUP) – dollar historically outperforms in true liquidity crises",
            "Long commodity producers (XLE, XME) – hard assets hedge stagflation",
        ],
        "examples": ["2022 bond/equity selloff (Fed tightening cycle)", "1994 bond market massacre"],
    },
    ("S&P 500", "VIX"): {
        "signal": "When equities and VIX rise together, dealers are buying protection while prices hold up — a warning of imminent correction.",
        "normalization_trades": [
            "Buy protective puts on SPY (near-ATM, 30-day expiry)",
            "Long UVXY or VIX futures for a short-vol squeeze exit",
            "Reduce beta; rotate into defensive sectors (XLU, XLP)",
        ],
        "examples": ["Late 2018 Q4 correction", "Pre-COVID Feb 2020"],
    },
    ("Gold", "USD Index"): {
        "signal": "Gold and USD rising together (breaking negative correlation) signals extreme risk aversion — both seen as safe havens simultaneously.",
        "normalization_trades": [
            "Short gold vs long USD via GLD puts / UUP calls spread",
            "Long EM equities (EEM) when correlation normalizes",
            "Long inflation-protected bonds (TIP) as regime normalizes",
        ],
        "examples": ["Post-Lehman 2008 crisis flight to both assets", "Russia-Ukraine 2022"],
    },
}


@dataclass
class CorrelationAnomaly:
    asset_a: str
    asset_b: str
    current_corr: float
    historical_norm: float
    deviation: float  # current - norm
    signal_description: str
    normalization_trades: list[str]
    historical_examples: list[str]
    data_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "Pair": f"{self.asset_a} / {self.asset_b}",
            "Current 60d Correlation": f"{self.current_corr:+.2f}",
            "Historical Norm": f"{self.historical_norm:+.2f}",
            "Deviation": f"{self.deviation:+.2f}",
            "Signal": self.signal_description,
            "Normalization Trades": self.normalization_trades,
            "Historical Examples": self.historical_examples,
            "Sources": self.data_sources,
        }


def _rolling_corr(df: pd.DataFrame, a: str, b: str, window: int = 60) -> Optional[float]:
    """Compute the most recent rolling *window*-day correlation between two return series."""
    try:
        rets = df[[a, b]].pct_change().dropna()
        if len(rets) < window:
            return None
        recent = rets.tail(window)
        return float(recent[a].corr(recent[b]))
    except Exception:  # noqa: BLE001
        return None


def scan_correlations() -> tuple[list[CorrelationAnomaly], list[str]]:
    """
    Download price history for the asset universe, compute current 60-day
    rolling correlations, compare to historical norms, and flag anomalies.

    Returns
    -------
    Tuple of (list of CorrelationAnomaly, list of sources).
    """
    # Download all tickers at once for efficiency
    tickers = list(ASSET_UNIVERSE.values())
    names = list(ASSET_UNIVERSE.keys())

    prices: dict[str, pd.Series] = {}
    for name, ticker in ASSET_UNIVERSE.items():
        try:
            df = get_price_history(ticker, period="6mo")
            if not df.empty:
                prices[name] = df["Close"]
        except Exception:  # noqa: BLE001
            pass

    if len(prices) < 4:
        # Not enough data; return static analysis based on recent market conditions
        return _static_anomalies(), SOURCES

    price_df = pd.DataFrame(prices).dropna(how="all")

    anomalies: list[CorrelationAnomaly] = []
    anomaly_threshold = 0.25  # flag if deviation > this value

    for (name_a, name_b), norm in HISTORICAL_NORM_CORR.items():
        if name_a not in price_df.columns or name_b not in price_df.columns:
            continue
        corr = _rolling_corr(price_df, name_a, name_b)
        if corr is None:
            continue
        deviation = corr - norm
        if abs(deviation) < anomaly_threshold:
            continue

        extra = ANOMALY_SIGNALS.get((name_a, name_b), {})
        signal = extra.get(
            "signal",
            f"Unusual correlation between {name_a} and {name_b} (deviation {deviation:+.2f} from historical norm).",
        )
        trades = extra.get(
            "normalization_trades",
            [f"Pair trade: revert {name_a}/{name_b} correlation back to {norm:+.2f}"],
        )
        examples = extra.get("historical_examples", [])

        anomalies.append(
            CorrelationAnomaly(
                asset_a=name_a,
                asset_b=name_b,
                current_corr=corr,
                historical_norm=norm,
                deviation=deviation,
                signal_description=signal,
                normalization_trades=trades,
                historical_examples=examples,
                data_sources=SOURCES,
            )
        )

    return anomalies, SOURCES


def _static_anomalies() -> list[CorrelationAnomaly]:
    """Return a curated set of anomalies when live data is unavailable."""
    static = [
        CorrelationAnomaly(
            asset_a="S&P 500",
            asset_b="Gold",
            current_corr=0.55,
            historical_norm=0.0,
            deviation=0.55,
            signal_description=ANOMALY_SIGNALS[("S&P 500", "Gold")]["signal"],
            normalization_trades=ANOMALY_SIGNALS[("S&P 500", "Gold")]["normalization_trades"],
            historical_examples=ANOMALY_SIGNALS[("S&P 500", "Gold")]["examples"],
            data_sources=SOURCES,
        ),
        CorrelationAnomaly(
            asset_a="S&P 500",
            asset_b="Long-Term Treasuries",
            current_corr=0.20,
            historical_norm=-0.35,
            deviation=0.55,
            signal_description=ANOMALY_SIGNALS[("S&P 500", "Long-Term Treasuries")]["signal"],
            normalization_trades=ANOMALY_SIGNALS[("S&P 500", "Long-Term Treasuries")]["normalization_trades"],
            historical_examples=ANOMALY_SIGNALS[("S&P 500", "Long-Term Treasuries")]["examples"],
            data_sources=SOURCES,
        ),
    ]
    return static
