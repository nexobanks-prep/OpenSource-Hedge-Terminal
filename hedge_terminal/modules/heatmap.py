"""
Volume Heatmap Module
=====================
Visualise where trading volume has clustered across price levels and time.

Renders a **price (Y-axis) × time (X-axis)** intensity matrix using Unicode
shade characters coloured by volume.  The brighter/denser the cell, the more
volume traded at that price level during that session.

Also computes the classic **Volume Profile** metrics derived from the
full-period aggregate:

  * **Point of Control (POC)** — price level with the highest cumulative
    traded volume across the whole period.
  * **Value Area High (VAH)** — upper bound of the price range containing
    70 % of total volume.
  * **Value Area Low (VAL)** — lower bound of the same range.

Volume is distributed within each bar's [Low, High] range using a triangular
distribution peaked at the bar's VWAP proxy ((Open + High + Low + Close) / 4),
which is a well-established approximation when tick data is unavailable.

Platform equivalents
--------------------
  Bloomberg Terminal : Volume Profile / VWAP-band view (GP with volume overlay)
  Sierra Chart       : Volume by Price / TPO Profile
  Bookmap            : Heatmap layer
  OpenBB             : custom (not built-in)
  NinjaTrader        : Volume Profile indicator
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from hedge_terminal.utils.data_fetcher import get_price_history


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Unicode shading characters ordered from least to most dense
_SHADES = " ░▒▓█"

# Rich colour gradient: cool (low volume) → hot (high volume)
_HEAT_COLORS = [
    "dim blue",
    "blue",
    "cyan",
    "green",
    "yellow",
    "bright_yellow",
    "red",
    "bright_red",
]

_DEFAULT_PRICE_BINS = 30   # rows in the heatmap
_DEFAULT_WIDTH = 60        # columns (time periods) shown
_DEFAULT_HEIGHT = 24       # rows (price bins) shown
_VALUE_AREA_PCT = 0.70     # fraction of total volume that defines the value area


# ---------------------------------------------------------------------------
# Volume distribution helpers
# ---------------------------------------------------------------------------

def _distribute_volume(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    price_edges: np.ndarray,
) -> np.ndarray:
    """
    Distribute ``volume`` across ``price_edges`` bins using a triangular
    distribution peaked at the bar's VWAP proxy.

    Returns a 1-D array of length ``len(price_edges) - 1``.
    """
    n_bins = len(price_edges) - 1
    bin_volumes = np.zeros(n_bins)

    bar_range = high - low
    if bar_range == 0 or volume == 0:
        return bin_volumes

    vwap_proxy = (open_ + high + low + close) / 4.0
    half_range = bar_range / 2.0

    weights = np.zeros(n_bins)
    for i in range(n_bins):
        bin_lo = price_edges[i]
        bin_hi = price_edges[i + 1]

        # Skip bins outside the bar's range
        if bin_hi <= low or bin_lo >= high:
            continue

        # Overlap of this bin with the bar's [Low, High] range
        overlap = min(bin_hi, high) - max(bin_lo, low)
        bin_center = (bin_lo + bin_hi) / 2.0

        # Triangular weight: 1.0 at VWAP proxy, 0.0 at the extreme edges
        dist_ratio = abs(bin_center - vwap_proxy) / half_range
        weights[i] = max(0.0, 1.0 - dist_ratio) * overlap

    total_weight = weights.sum()
    if total_weight > 0:
        bin_volumes = weights / total_weight * volume

    return bin_volumes


def _compute_volume_profile(
    price_edges: np.ndarray,
    profile: np.ndarray,
) -> tuple[float, float, float]:
    """
    Compute Point of Control, Value Area High, and Value Area Low from a
    1-D volume profile array (len = n_bins) and its price_edges (len = n_bins+1).

    Returns (poc_price, vah_price, val_price).
    """
    if profile.sum() == 0:
        mid = (price_edges[0] + price_edges[-1]) / 2
        return mid, mid, mid

    # POC: bin with maximum volume
    poc_idx = int(np.argmax(profile))
    poc_price = (price_edges[poc_idx] + price_edges[poc_idx + 1]) / 2.0

    # Value Area: expand outward from POC until 70 % of total volume is captured
    target = profile.sum() * _VALUE_AREA_PCT
    accumulated = profile[poc_idx]
    lo_idx = poc_idx
    hi_idx = poc_idx

    while accumulated < target:
        can_go_up = hi_idx + 1 < len(profile)
        can_go_down = lo_idx - 1 >= 0

        if not can_go_up and not can_go_down:
            break

        vol_up = profile[hi_idx + 1] if can_go_up else -1
        vol_down = profile[lo_idx - 1] if can_go_down else -1

        if vol_up >= vol_down:
            hi_idx += 1
            accumulated += profile[hi_idx]
        else:
            lo_idx -= 1
            accumulated += profile[lo_idx]

    vah_price = (price_edges[hi_idx] + price_edges[hi_idx + 1]) / 2.0
    val_price = (price_edges[lo_idx] + price_edges[lo_idx + 1]) / 2.0
    return poc_price, vah_price, val_price


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class VolumeHeatmapData:
    """
    Holds the volume heatmap matrix and derived metrics for one ticker.

    Attributes
    ----------
    ticker : str
    period : str
        yfinance period string (e.g. ``"6mo"``).
    matrix : np.ndarray
        Shape ``(n_price_bins, n_time_periods)``.  Each cell contains the
        estimated volume traded in that price range during that session.
    price_edges : np.ndarray
        Length ``n_price_bins + 1``.  Defines bin boundaries on the Y-axis.
    dates : pd.DatetimeIndex
        One label per column of ``matrix``.
    total_volume : float
    point_of_control : float
        Price level with the highest cumulative volume.
    value_area_high : float
        Upper bound of the 70 % value area.
    value_area_low : float
        Lower bound of the 70 % value area.
    current_price : float | None
    """

    ticker: str
    period: str
    matrix: np.ndarray
    price_edges: np.ndarray
    dates: pd.DatetimeIndex
    total_volume: float
    point_of_control: float
    value_area_high: float
    value_area_low: float
    current_price: float | None

    # -----------------------------------------------------------------------
    # ASCII rendering
    # -----------------------------------------------------------------------

    def render(
        self,
        width: int = _DEFAULT_WIDTH,
        height: int = _DEFAULT_HEIGHT,
    ) -> str:
        """
        Return a multi-line ASCII string representing the volume heatmap.

        Rows   = price levels (highest → lowest)
        Columns = time periods (oldest → newest)
        Cell shade intensity ∝ volume at that price × time cell.

        Rich markup colour codes are embedded for use with ``rich.print``.
        """
        if self.matrix.size == 0:
            return "(no data)"

        n_price, n_time = self.matrix.shape

        # Sub-sample the time axis to fit display width
        t_count = min(width, n_time)
        t_indices = [int(i * (n_time - 1) / max(t_count - 1, 1)) for i in range(t_count)]

        # Sub-sample the price axis to fit display height
        p_count = min(height, n_price)
        p_indices = [int(i * (n_price - 1) / max(p_count - 1, 1)) for i in range(p_count)]

        # Extract sub-matrix
        sub = self.matrix[np.ix_(p_indices, t_indices)]
        max_vol = sub.max() if sub.max() > 0 else 1.0

        label_w = 9  # width for the price label column
        lines: list[str] = []

        # Render price rows from highest to lowest price
        for pi, p_idx in enumerate(reversed(p_indices)):
            price = (self.price_edges[p_idx] + self.price_edges[p_idx + 1]) / 2.0

            # Marker for POC, VAH, VAL
            if abs(price - self.point_of_control) <= (self.price_edges[1] - self.price_edges[0]) * 1.5:
                marker = "[bold yellow]◄ POC[/bold yellow]"
            elif abs(price - self.value_area_high) <= (self.price_edges[1] - self.price_edges[0]) * 1.5:
                marker = "[green]▲ VAH[/green]"
            elif abs(price - self.value_area_low) <= (self.price_edges[1] - self.price_edges[0]) * 1.5:
                marker = "[red]▼ VAL[/red]"
            else:
                marker = ""

            label = f"{price:>{label_w}.2f} │"
            row_str = ""

            # Column index in sub corresponds to reversed p_idx
            sub_row_idx = p_count - 1 - pi
            for ti in range(t_count):
                v = sub[sub_row_idx, ti]
                intensity = v / max_vol  # 0.0 → 1.0
                shade_idx = int(intensity * (len(_SHADES) - 1))
                color_idx = int(intensity * (len(_HEAT_COLORS) - 1))
                char = _SHADES[shade_idx]
                color = _HEAT_COLORS[color_idx]
                if char.strip():
                    row_str += f"[{color}]{char}[/{color}]"
                else:
                    row_str += char

            lines.append(label + row_str + ("  " + marker if marker else ""))

        # X-axis
        x_axis = " " * (label_w + 1) + "└" + "─" * t_count
        lines.append(x_axis)

        # Date labels
        if len(self.dates) > 0:
            first = str(self.dates[0])[:10]
            last = str(self.dates[-1])[:10]
            pad = t_count - len(first) - len(last)
            date_line = " " * (label_w + 2) + first
            if pad > 0:
                date_line += " " * pad + last
            lines.append(date_line)

        header = (
            f"\n[bold]{self.ticker}[/bold] Volume Heatmap  "
            f"Period: {self.period}\n"
            f"  [bold yellow]◄ POC[/bold yellow] {self.point_of_control:.2f}  "
            f"[green]▲ VAH[/green] {self.value_area_high:.2f}  "
            f"[red]▼ VAL[/red] {self.value_area_low:.2f}  "
            f"Total Vol: [cyan]{self.total_volume:,.0f}[/cyan]\n"
            f"  [dim]Legend: █ high volume  ▒ medium  ░ low  (brighter = hotter)[/dim]\n"
        )

        return header + "\n".join(lines)

    # -----------------------------------------------------------------------
    def summary(self) -> dict[str, str]:
        """Return a compact dict for use in a Rich table row."""
        poc_vs_current = "N/A"
        if self.current_price and self.point_of_control:
            pct = (self.current_price - self.point_of_control) / self.point_of_control * 100
            poc_vs_current = f"{pct:+.2f}%"

        inside_va = "—"
        if self.current_price:
            if self.value_area_low <= self.current_price <= self.value_area_high:
                inside_va = "✓ Inside VA"
            elif self.current_price > self.value_area_high:
                inside_va = "↑ Above VAH"
            else:
                inside_va = "↓ Below VAL"

        return {
            "Ticker": self.ticker,
            "Period": self.period,
            "Point of Control": f"{self.point_of_control:.2f}",
            "Value Area High": f"{self.value_area_high:.2f}",
            "Value Area Low": f"{self.value_area_low:.2f}",
            "Current Price": f"{self.current_price:.2f}" if self.current_price else "N/A",
            "Price vs POC": poc_vs_current,
            "VA Position": inside_va,
            "Total Volume": f"{self.total_volume:,.0f}",
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_volume_heatmap(
    ticker: str,
    period: str = "3mo",
    interval: str = "1d",
    price_bins: int = _DEFAULT_PRICE_BINS,
) -> VolumeHeatmapData:
    """
    Fetch OHLCV data and build a :class:`VolumeHeatmapData` ready to render.

    Parameters
    ----------
    ticker:
        Stock / ETF / index symbol (e.g. ``"AAPL"``, ``"SPY"``).
    period:
        yfinance period string: ``"1mo"``, ``"3mo"``, ``"6mo"``, ``"1y"``.
    interval:
        yfinance interval: ``"1d"`` (daily), ``"1wk"`` (weekly).
    price_bins:
        Number of price levels on the Y-axis (default 30).
    """
    t = ticker.upper()
    df = get_price_history(t, period=period, interval=interval)

    _empty = VolumeHeatmapData(
        ticker=t,
        period=period,
        matrix=np.empty((0, 0)),
        price_edges=np.array([]),
        dates=pd.DatetimeIndex([]),
        total_volume=0.0,
        point_of_control=float("nan"),
        value_area_high=float("nan"),
        value_area_low=float("nan"),
        current_price=None,
    )

    required = {"Open", "High", "Low", "Close", "Volume"}
    if df.empty or not required.issubset(df.columns):
        return _empty

    df = df.dropna(subset=list(required))
    if len(df) < 2:
        return _empty

    # Price range across the entire period
    global_low = float(df["Low"].min())
    global_high = float(df["High"].max())
    if global_high == global_low:
        global_high += 1.0

    price_edges = np.linspace(global_low, global_high, price_bins + 1)
    n_bars = len(df)

    # Build the (price_bins × n_bars) matrix
    matrix = np.zeros((price_bins, n_bars), dtype=float)

    for col_idx, (_, row) in enumerate(df.iterrows()):
        bar_vol = _distribute_volume(
            open_=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row["Volume"]),
            price_edges=price_edges,
        )
        matrix[:, col_idx] = bar_vol

    # Aggregate volume profile (sum across all time periods)
    volume_profile = matrix.sum(axis=1)
    poc, vah, val = _compute_volume_profile(price_edges, volume_profile)

    current_price: float | None = None
    if not df.empty:
        current_price = float(df["Close"].iloc[-1])

    return VolumeHeatmapData(
        ticker=t,
        period=period,
        matrix=matrix,
        price_edges=price_edges,
        dates=pd.DatetimeIndex(df.index),
        total_volume=float(df["Volume"].sum()),
        point_of_control=poc,
        value_area_high=vah,
        value_area_low=val,
        current_price=current_price,
    )
