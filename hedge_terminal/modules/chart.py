"""
Chart Module
============
Render an ASCII/Unicode price chart in the terminal.

Replicates Bloomberg Terminal's **GP (Graph Price)** function and
OpenBB Terminal's ``stocks candle`` command — no GUI required, runs
entirely in a terminal using Unicode block characters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from hedge_terminal.utils.data_fetcher import get_price_history


# ---------------------------------------------------------------------------
# Chart configuration
# ---------------------------------------------------------------------------

_BARS = " ▁▂▃▄▅▆▇█"  # Unicode block elements (index 0 = empty, 8 = full)
_UP_COLOR = "green"
_DOWN_COLOR = "red"
_WIDTH = 80   # characters wide
_HEIGHT = 20  # rows tall


@dataclass
class ChartData:
    ticker: str
    period: str
    prices: pd.Series          # DatetimeIndex → float (Close prices)
    volumes: pd.Series         # DatetimeIndex → float
    change_pct: float | None   # full-period % change
    high: float
    low: float
    current: float

    # -----------------------------------------------------------------------
    # ASCII rendering
    # -----------------------------------------------------------------------

    def render(self, width: int = _WIDTH, height: int = _HEIGHT) -> str:
        """
        Return a multi-line ASCII string representing the price chart.

        Uses Unicode block characters for a clean terminal look.
        Rich markup colour codes are embedded (works with ``rich.print``).
        """
        closes = self.prices.dropna()
        if closes.empty:
            return "(no data)"

        n = len(closes)
        w = min(width, n)

        # Downsample / upsample to exactly *w* data points
        indices = [int(i * (n - 1) / max(w - 1, 1)) for i in range(w)]
        sampled = [float(closes.iloc[i]) for i in indices]

        lo = min(sampled)
        hi = max(sampled)
        price_range = hi - lo or 1.0

        # Build a 2-D grid: grid[row][col] = True if bar should be drawn
        grid = [[False] * w for _ in range(height)]
        for col, price in enumerate(sampled):
            bar_height = int((price - lo) / price_range * (height - 1))
            for row in range(bar_height + 1):
                grid[row][col] = True

        # Determine coloring: up (green) or down (red) vs first bar
        colors = []
        for i, price in enumerate(sampled):
            if i == 0:
                colors.append(_UP_COLOR)
            else:
                colors.append(_UP_COLOR if price >= sampled[0] else _DOWN_COLOR)

        # Render rows from top to bottom
        lines: list[str] = []

        # Y-axis label width
        label_w = 10
        price_step = price_range / (height - 1)

        for row in reversed(range(height)):
            level = lo + row * price_step
            label = f"{level:>{label_w}.2f} │"
            bar_line = ""
            for col in range(w):
                char = "█" if grid[row][col] else " "
                color = colors[col]
                if grid[row][col]:
                    bar_line += f"[{color}]{char}[/{color}]"
                else:
                    bar_line += char
            lines.append(label + bar_line)

        # X-axis
        x_axis = " " * (label_w + 1) + "└" + "─" * w
        lines.append(x_axis)

        # Date labels on x-axis
        dates = closes.index
        first_date = str(dates[0])[:10]
        last_date = str(dates[-1])[:10]
        date_line = " " * (label_w + 2) + first_date
        pad = w - len(first_date) - len(last_date)
        if pad > 0:
            date_line += " " * pad + last_date
        lines.append(date_line)

        # Header
        change_str = "N/A"
        if self.change_pct is not None:
            sign = "+" if self.change_pct >= 0 else ""
            color = _UP_COLOR if self.change_pct >= 0 else _DOWN_COLOR
            change_str = f"[{color}]{sign}{self.change_pct:.2f}%[/{color}]"

        header = (
            f"\n[bold]{self.ticker}[/bold]  "
            f"Period: {self.period}  "
            f"Current: [bold]{self.current:.2f}[/bold]  "
            f"High: {self.high:.2f}  Low: {self.low:.2f}  "
            f"Change: {change_str}\n"
        )

        return header + "\n".join(lines)

    # -----------------------------------------------------------------------
    def summary(self) -> dict[str, str]:
        """Return a compact dict for use in a Rich table."""
        sign = "+" if (self.change_pct or 0) >= 0 else ""
        return {
            "Ticker": self.ticker,
            "Period": self.period,
            "Current Price": f"{self.current:.2f}",
            "Period High": f"{self.high:.2f}",
            "Period Low": f"{self.low:.2f}",
            "Period Change": (
                f"{sign}{self.change_pct:.2f}%"
                if self.change_pct is not None
                else "N/A"
            ),
            "Data Points": str(len(self.prices.dropna())),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_chart(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
) -> ChartData:
    """
    Fetch price history and return a :class:`ChartData` ready to render.

    Parameters
    ----------
    ticker:
        Stock / ETF / index symbol (e.g. ``"AAPL"``, ``"SPY"``, ``"^GSPC"``).
    period:
        yfinance period string: ``"1mo"``, ``"3mo"``, ``"6mo"``, ``"1y"``,
        ``"2y"``, ``"5y"``, ``"ytd"``.
    interval:
        yfinance interval string: ``"1d"``, ``"1wk"``, ``"1mo"``.
    """
    df = get_price_history(ticker.upper(), period=period, interval=interval)

    if df.empty or "Close" not in df.columns:
        # Return an empty chart rather than raising
        empty = pd.Series(dtype=float)
        return ChartData(
            ticker=ticker.upper(),
            period=period,
            prices=empty,
            volumes=empty,
            change_pct=None,
            high=float("nan"),
            low=float("nan"),
            current=float("nan"),
        )

    closes = df["Close"].dropna()
    volumes = df.get("Volume", pd.Series(dtype=float))

    first = float(closes.iloc[0]) if not closes.empty else None
    last = float(closes.iloc[-1]) if not closes.empty else None

    change_pct: float | None = None
    if first and last and first != 0:
        change_pct = (last - first) / first * 100

    return ChartData(
        ticker=ticker.upper(),
        period=period,
        prices=closes,
        volumes=volumes,
        change_pct=change_pct,
        high=float(closes.max()),
        low=float(closes.min()),
        current=last if last is not None else float("nan"),
    )


def compare_charts(
    tickers: list[str],
    period: str = "6mo",
    interval: str = "1d",
) -> dict[str, ChartData]:
    """Fetch chart data for multiple tickers (for relative-performance view)."""
    result: dict[str, ChartData] = {}
    for t in tickers:
        try:
            result[t.upper()] = get_chart(t, period=period, interval=interval)
        except Exception:  # noqa: BLE001
            pass
    return result
