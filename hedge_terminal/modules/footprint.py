"""
Footprint Chart Module
======================
Show estimated **bid vs. ask volume** at each price level within every bar,
revealing order-flow imbalance (delta) and potential institutional activity.

What the footprint chart shows
-------------------------------
For each time bar, the module splits the bar's total OHLCV volume into:

  * **Bid volume**  — estimated selling (market sell orders hitting the bid).
  * **Ask volume**  — estimated buying  (market buy orders lifting the ask).
  * **Delta**       = Ask − Bid.  Positive → net buying; negative → net selling.
  * **Delta %**     = Delta / Total Volume × 100.
  * **Cumulative Δ** — running sum of delta; sustained positive trend signals
                       accumulation; sustained negative signals distribution.
  * **Imbalance**   — flagged when Ask/Bid or Bid/Ask ratio exceeds 3× at the
                      bar level (strong one-sided order flow).

Since free data sources (yfinance) provide OHLCV bars only (not tick data),
the bid/ask split uses the **candle body-to-range ratio method**:

  * Bullish bar (Close ≥ Open):
      - Ask fraction = 0.5 + body_ratio × 0.4   (max 90 %)
      - Bid fraction = 1 − Ask fraction
  * Bearish bar (Close < Open):
      - Bid fraction = 0.5 + body_ratio × 0.4
      - Ask fraction = 1 − Bid fraction

  Where ``body_ratio = |Close − Open| / (High − Low)``.  A doji bar with no
  body gives a 50/50 split; a strong marubozu gives up to 90/10.

Platform equivalents
--------------------
  Bookmap            : Footprint / delta view
  Sierra Chart       : Bid/Ask footprint bars
  NinjaTrader        : Volumetric bars
  Bloomberg Terminal : Order-flow (premium add-on); this module is an approx.
  OpenBB             : custom (not built-in)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from hedge_terminal.utils.data_fetcher import get_price_history


# ---------------------------------------------------------------------------
# Volume estimation helpers
# ---------------------------------------------------------------------------

def _estimate_bid_ask(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> tuple[float, float]:
    """
    Estimate bid (sell) and ask (buy) volume from OHLCV data using the
    candle body-to-range ratio method.

    Returns ``(bid_volume, ask_volume)``.
    """
    bar_range = high - low
    if bar_range == 0 or volume == 0:
        return volume / 2.0, volume / 2.0

    # Body as a fraction of the total bar range (0 = doji, 1 = marubozu)
    body_ratio = abs(close - open_) / bar_range

    # The dominant side takes 50 % base + up to 40 % from body skew (max 90 %)
    dominant_fraction = min(0.5 + body_ratio * 0.4, 0.90)
    recessive_fraction = 1.0 - dominant_fraction

    if close >= open_:  # bullish bar → more ask (buying) volume
        ask_vol = volume * dominant_fraction
        bid_vol = volume * recessive_fraction
    else:               # bearish bar → more bid (selling) volume
        bid_vol = volume * dominant_fraction
        ask_vol = volume * recessive_fraction

    return bid_vol, ask_vol


def _imbalance_signal(bid: float, ask: float, threshold: float = 3.0) -> str:
    """
    Return an imbalance label when ask/bid or bid/ask exceeds ``threshold``.
    """
    if bid == 0 and ask > 0:
        return "⚡ ALL BUY"
    if ask == 0 and bid > 0:
        return "⚡ ALL SELL"
    if bid == 0 and ask == 0:
        return "—"
    ratio_buy = ask / bid if bid > 0 else 0
    ratio_sell = bid / ask if ask > 0 else 0
    if ratio_buy >= threshold:
        return f"⚡ BUY {ratio_buy:.1f}×"
    if ratio_sell >= threshold:
        return f"⚡ SELL {ratio_sell:.1f}×"
    return "—"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FootprintBar:
    """Bid/ask analysis for one OHLCV bar."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    bid_volume: float
    ask_volume: float

    @property
    def delta(self) -> float:
        """Ask − Bid.  Positive = net buying."""
        return self.ask_volume - self.bid_volume

    @property
    def delta_pct(self) -> float:
        """Delta as a percentage of total volume."""
        if self.volume == 0:
            return 0.0
        return self.delta / self.volume * 100.0

    @property
    def bullish(self) -> bool:
        return self.close >= self.open

    def imbalance(self, threshold: float = 3.0) -> str:
        return _imbalance_signal(self.bid_volume, self.ask_volume, threshold)

    def to_dict(self, cumulative_delta: float = 0.0) -> dict[str, str]:
        direction = "▲" if self.bullish else "▼"
        delta_color_tag = "green" if self.delta >= 0 else "red"
        return {
            "Date": self.date,
            "Dir": direction,
            "Open": f"{self.open:.2f}",
            "High": f"{self.high:.2f}",
            "Low": f"{self.low:.2f}",
            "Close": f"{self.close:.2f}",
            "Volume": f"{self.volume:,.0f}",
            "Bid Vol": f"{self.bid_volume:,.0f}",
            "Ask Vol": f"{self.ask_volume:,.0f}",
            f"Delta ({delta_color_tag})": f"{self.delta:+,.0f}",
            "Delta %": f"{self.delta_pct:+.1f}%",
            "Cum. Δ": f"{cumulative_delta:+,.0f}",
            "Imbalance": self.imbalance(),
        }


@dataclass
class FootprintData:
    """
    Collection of :class:`FootprintBar` objects with summary statistics.

    Attributes
    ----------
    ticker : str
    period : str
    bars : list[FootprintBar]
        Ordered oldest → newest.
    total_delta : float
        Cumulative delta over the entire period.
    max_single_delta : float
        Largest single-bar delta (magnitude).
    bullish_bars : int
    bearish_bars : int
    """

    ticker: str
    period: str
    bars: list[FootprintBar] = field(default_factory=list)

    @property
    def total_delta(self) -> float:
        return sum(b.delta for b in self.bars)

    @property
    def max_single_delta(self) -> float:
        if not self.bars:
            return 0.0
        return max(abs(b.delta) for b in self.bars)

    @property
    def bullish_bars(self) -> int:
        return sum(1 for b in self.bars if b.bullish)

    @property
    def bearish_bars(self) -> int:
        return sum(1 for b in self.bars if not b.bullish)

    # -----------------------------------------------------------------------
    # ASCII rendering
    # -----------------------------------------------------------------------

    def render(self, last_n: int = 20) -> str:
        """
        Return a multi-line ASCII string showing the footprint table for the
        most recent ``last_n`` bars plus a delta bar chart.

        Rich markup colour codes are embedded.
        """
        if not self.bars:
            return "(no data)"

        display_bars = self.bars[-last_n:]

        # Build the delta bar chart (sparkline style)
        max_delta = max(abs(b.delta) for b in display_bars) or 1.0
        bar_width = 20

        lines: list[str] = []

        # Header
        direction_str = "▲ Buying" if self.total_delta >= 0 else "▼ Selling"
        delta_color = "green" if self.total_delta >= 0 else "red"
        lines.append(
            f"\n[bold]{self.ticker}[/bold] Footprint Chart  "
            f"Period: {self.period}  "
            f"Bars: {len(self.bars)}\n"
            f"  Total Δ: [{delta_color}]{self.total_delta:+,.0f}[/{delta_color}] "
            f"({direction_str})  "
            f"Bull bars: [green]{self.bullish_bars}[/green]  "
            f"Bear bars: [red]{self.bearish_bars}[/red]\n"
        )

        # Delta bar chart (most recent N bars)
        lines.append("  [bold]Delta bar chart[/bold] (+ = buying, − = selling)\n")

        cumulative = sum(b.delta for b in self.bars[: len(self.bars) - len(display_bars)])
        for bar in display_bars:
            cumulative += bar.delta
            delta_norm = bar.delta / max_delta  # -1.0 → +1.0
            filled = int(abs(delta_norm) * bar_width)

            if bar.delta >= 0:
                bar_str = "█" * filled + "░" * (bar_width - filled)
                color = "green"
                side = "+"
            else:
                bar_str = "░" * (bar_width - filled) + "█" * filled
                color = "red"
                side = "−"

            imb = bar.imbalance()
            imb_str = f"  {imb}" if imb != "—" else ""

            lines.append(
                f"  {bar.date[:10]}  [{color}]{bar_str}[/{color}]  "
                f"[{color}]{side}{abs(bar.delta):>10,.0f}[/{color}]"
                f"  Cum Δ: {cumulative:+,.0f}"
                f"{imb_str}"
            )

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    def to_table_rows(self, last_n: int = 20) -> list[dict[str, str]]:
        """Return list of row-dicts for the most recent ``last_n`` bars."""
        display_bars = self.bars[-last_n:]
        cumulative = sum(b.delta for b in self.bars[: len(self.bars) - len(display_bars)])
        rows = []
        for bar in display_bars:
            cumulative += bar.delta
            rows.append(bar.to_dict(cumulative_delta=cumulative))
        return rows

    def summary(self) -> dict[str, str]:
        """Return a compact dict for use in a Rich table row."""
        delta_color = "green" if self.total_delta >= 0 else "red"
        bull_pct = (
            self.bullish_bars / len(self.bars) * 100 if self.bars else 0
        )
        return {
            "Ticker": self.ticker,
            "Period": self.period,
            "Total Bars": str(len(self.bars)),
            "Total Delta": f"{self.total_delta:+,.0f}",
            "Direction": "▲ Buying" if self.total_delta >= 0 else "▼ Selling",
            "Bull Bars %": f"{bull_pct:.1f}%",
            "Max |Δ| Bar": f"{self.max_single_delta:,.0f}",
            "Data source": "OHLCV (approx.)",
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_footprint(
    ticker: str,
    period: str = "1mo",
    interval: str = "1d",
) -> FootprintData:
    """
    Fetch OHLCV data and return a :class:`FootprintData` ready to render.

    Parameters
    ----------
    ticker:
        Stock / ETF / index symbol (e.g. ``"AAPL"``, ``"SPY"``).
    period:
        yfinance period string: ``"5d"``, ``"1mo"``, ``"3mo"``, ``"6mo"``,
        ``"1y"``, ``"ytd"``.
    interval:
        yfinance interval: ``"1d"`` (daily), ``"1h"`` (hourly — last 60 days),
        ``"1wk"`` (weekly).
    """
    t = ticker.upper()
    df = get_price_history(t, period=period, interval=interval)

    fp = FootprintData(ticker=t, period=period)

    required = {"Open", "High", "Low", "Close", "Volume"}
    if df.empty or not required.issubset(df.columns):
        return fp

    df = df.dropna(subset=list(required))

    for ts, row in df.iterrows():
        open_ = float(row["Open"])
        high = float(row["High"])
        low = float(row["Low"])
        close = float(row["Close"])
        volume = float(row["Volume"])

        bid_vol, ask_vol = _estimate_bid_ask(open_, high, low, close, volume)

        fp.bars.append(
            FootprintBar(
                date=str(ts)[:10],
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                bid_volume=bid_vol,
                ask_volume=ask_vol,
            )
        )

    return fp
