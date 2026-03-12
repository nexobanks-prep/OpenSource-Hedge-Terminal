"""
OpenSource Hedge Terminal – CLI
================================
A free, open-source quant analyst toolkit that replicates the core
workflows of Bloomberg Terminal and OpenBB Terminal — no paid subscriptions.

Equivalent Bloomberg / OpenBB commands
---------------------------------------
  quote        ← Bloomberg BQ/DES     | OpenBB stocks quote
  news         ← Bloomberg NEWS       | OpenBB news
  chart        ← Bloomberg GP         | OpenBB stocks candle
  screen       ← Bloomberg EQSRCH    | OpenBB stocks screener
  hedge        ← Bloomberg MARS/DLIB  | custom quant module
  whales       ← Bloomberg 13F data   | OpenBB alternative data
  dividends    ← Bloomberg DVD        | OpenBB stocks dps
  correlations ← Bloomberg CORR       | custom quant module
  sentiment    ← Bloomberg SRCH/NEWS  | OpenBB stocks ba
  macro        ← Bloomberg ECOW/WECO  | OpenBB economy
  squeeze      ← Bloomberg SI/FSHO   | OpenBB stocks sia
  heatmap      ← Bloomberg VWAP/Vol   | Sierra Chart Volume by Price
  footprint    ← Bookmap/NinjaTrader  | Sierra Chart Footprint bars

Usage
-----
    python main.py --help
    python main.py quote AAPL MSFT TSLA
    python main.py news --ticker AAPL
    python main.py chart --ticker SPY --period 1y
    python main.py screen --preset value
    python main.py hedge --sector technology
    python main.py whales
    python main.py dividends
    python main.py correlations
    python main.py sentiment
    python main.py macro
    python main.py squeeze
    python main.py heatmap --ticker SPY
    python main.py footprint --ticker AAPL
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

console = Console()

BANNER = """
[bold cyan]
  ██████  ██████  ███████ ███    ██       ██   ██ ███████ ██████   ██████  ███████
 ██    ██ ██   ██ ██      ████   ██       ██   ██ ██      ██   ██ ██       ██
 ██    ██ ██████  █████   ██ ██  ██       ███████ █████   ██   ██ ██   ███ █████
 ██    ██ ██      ██      ██  ██ ██       ██   ██ ██      ██   ██ ██    ██ ██
  ██████  ██      ███████ ██   ████       ██   ██ ███████ ██████   ██████  ███████
[/bold cyan]
[bold yellow]  T E R M I N A L[/bold yellow]  [dim]– Free, Open-Source Alternative to Bloomberg & OpenBB[/dim]
[dim]  No more $24,000/year subscriptions.[/dim]
"""


def print_banner() -> None:
    console.print(BANNER)


def make_table(title: str, rows: list[dict]) -> Table:
    """Build a Rich table from a list of dicts (first dict defines columns)."""
    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
        expand=True,
    )
    if not rows:
        table.add_column("Result")
        table.add_row("[dim]No results found[/dim]")
        return table

    for col in rows[0].keys():
        table.add_column(str(col), overflow="fold")

    for row in rows:
        cells = []
        for v in row.values():
            if isinstance(v, list):
                cells.append("\n".join(f"• {i}" for i in v))
            elif isinstance(v, dict):
                cells.append(
                    "\n".join(f"{k}: {val}" for k, val in v.items())
                )
            else:
                cells.append(str(v) if v is not None else "N/A")
        table.add_row(*cells)

    return table


@click.group()
def cli() -> None:
    """OpenSource Hedge Terminal – free alternative to Bloomberg & OpenBB."""
    print_banner()


@cli.command()
@click.option(
    "--sector",
    default="broad market",
    show_default=True,
    help="Sector or market exposure to hedge (e.g. technology, energy, financials).",
)
@click.option(
    "--ticker",
    default="SPY",
    show_default=True,
    help="Representative ETF ticker for IV calculation.",
)
@click.option(
    "--puts",
    is_flag=True,
    default=False,
    help="Recommend put options instead of inverse ETFs.",
)
def hedge(sector: str, ticker: str, puts: bool) -> None:
    """Design an efficient portfolio hedge using options or inverse ETFs."""
    from hedge_terminal.modules.hedge_designer import design_hedge

    console.print(
        Panel(
            f"[bold]Designing hedge for:[/bold] [cyan]{sector.title()}[/cyan] exposure",
            style="blue",
        )
    )
    with console.status("[bold green]Fetching volatility data..."):
        rec = design_hedge(sector, portfolio_ticker=ticker, prefer_puts=puts)

    table = make_table("Hedge Recommendation", [rec.to_dict()])
    console.print(table)


@cli.command()
@click.option(
    "--filter",
    "change_type",
    type=click.Choice(["new", "exited", "increased", "decreased", "all"]),
    default="all",
    show_default=True,
    help="Filter by position change type.",
)
def whales(change_type: str) -> None:
    """Analyze top hedge fund 13F filings for position changes."""
    from hedge_terminal.modules.whale_tracker import get_whale_activity

    console.print(
        Panel("[bold]Scanning 13F filings from top hedge funds...[/bold]", style="blue")
    )
    with console.status("[bold green]Fetching 13F data..."):
        positions, sources = get_whale_activity(
            change_type_filter=None if change_type == "all" else change_type
        )

    if not positions:
        console.print("[yellow]No position changes found matching your filter.[/yellow]")
        return

    rows = [p.to_dict() for p in positions]
    table = make_table("Top Hedge Fund 13F Position Changes", rows)
    console.print(table)
    console.print("\n[bold]Sources:[/bold]")
    for s in sources:
        console.print(f"  • {s}")


@cli.command()
@click.option(
    "--tickers",
    default=None,
    help="Comma-separated list of tickers to screen (default: built-in watch list).",
)
@click.option(
    "--limit",
    default=5,
    show_default=True,
    help="Maximum number of results to return.",
)
def dividends(tickers: str | None, limit: int) -> None:
    """Find high-yield stocks with dividend cut warning signs."""
    from hedge_terminal.modules.dividend_analyzer import screen_dividend_warnings

    ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    console.print(
        Panel(
            "[bold]Screening for risky high-yield dividend stocks...[/bold]",
            style="blue",
        )
    )
    with console.status("[bold green]Fetching fundamental data..."):
        warnings = screen_dividend_warnings(ticker_list, limit=limit)

    if not warnings:
        console.print("[green]No warning signs found in the screened universe.[/green]")
        return

    rows = [w.to_dict() for w in warnings]
    table = make_table(f"Dividend Warning Signs (Top {len(rows)})", rows)
    console.print(table)


@cli.command()
def correlations() -> None:
    """Detect unusual cross-asset correlations and suggest normalization trades."""
    from hedge_terminal.modules.correlation_scanner import scan_correlations

    console.print(
        Panel("[bold]Scanning for unusual cross-asset correlations...[/bold]", style="blue")
    )
    with console.status("[bold green]Downloading price history..."):
        anomalies, sources = scan_correlations()

    if not anomalies:
        console.print("[green]No significant correlation anomalies detected.[/green]")
        return

    for a in anomalies:
        table = make_table(
            f"Anomaly: {a.asset_a} / {a.asset_b}", [a.to_dict()]
        )
        console.print(table)

    console.print("\n[bold]Sources:[/bold]")
    for s in sources:
        console.print(f"  • {s}")


@cli.command()
@click.option(
    "--tickers",
    default=None,
    help="Comma-separated list of tickers to analyze (default: built-in candidates).",
)
@click.option(
    "--limit",
    default=6,
    show_default=True,
    help="Maximum number of ideas to return.",
)
def sentiment(tickers: str | None, limit: int) -> None:
    """Find stocks where negative sentiment diverges from strong fundamentals."""
    from hedge_terminal.modules.sentiment_analyzer import find_sentiment_divergences

    ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    console.print(
        Panel(
            "[bold]Searching for sentiment vs. fundamentals divergences...[/bold]",
            style="blue",
        )
    )
    with console.status("[bold green]Analyzing fundamental data..."):
        results = find_sentiment_divergences(ticker_list, limit=limit)

    if not results:
        console.print("[yellow]No significant divergences found.[/yellow]")
        return

    rows = [r.to_dict() for r in results]
    table = make_table(f"Sentiment / Fundamentals Divergence (Top {len(rows)})", rows)
    console.print(table)


@cli.command()
def macro() -> None:
    """Analyze the current macroeconomic environment and sector outperformance."""
    from hedge_terminal.modules.macro_analyzer import get_macro_context

    console.print(
        Panel(
            "[bold]Fetching macro data from FRED and sector performance...[/bold]",
            style="blue",
        )
    )
    with console.status("[bold green]Downloading macro indicators..."):
        ctx = get_macro_context()

    data = ctx.to_dict()

    # Separate sector returns from the main table
    sector_returns = data.pop("Sector YTD Returns", {})

    table = make_table("Macroeconomic Context & Regime Analysis", [data])
    console.print(table)

    if sector_returns:
        ret_table = Table(
            title="Sector YTD Returns",
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold cyan",
        )
        ret_table.add_column("Sector")
        ret_table.add_column("YTD Return", justify="right")
        for sec, ret in sorted(sector_returns.items(), key=lambda x: x[1], reverse=True):
            color = "green" if ret > 0 else "red"
            ret_table.add_row(sec, f"[{color}]{ret}[/{color}]")
        console.print(ret_table)


@cli.command()
@click.option(
    "--tickers",
    default=None,
    help="Comma-separated list of tickers to analyze (default: curated watch list).",
)
@click.option(
    "--min-short",
    default=20.0,
    show_default=True,
    help="Minimum short float % to qualify.",
)
@click.option(
    "--limit",
    default=5,
    show_default=True,
    help="Maximum number of candidates to return.",
)
def squeeze(tickers: str | None, min_short: float, limit: int) -> None:
    """Find short squeeze candidates with high short interest and upcoming catalysts."""
    from hedge_terminal.modules.short_squeeze import find_short_squeezes

    ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    console.print(
        Panel(
            "[bold]Scanning for short squeeze opportunities...[/bold]", style="blue"
        )
    )
    with console.status("[bold green]Fetching short interest data..."):
        candidates, sources = find_short_squeezes(
            ticker_list, min_short_float_pct=min_short, limit=limit
        )

    if not candidates:
        console.print("[yellow]No squeeze candidates found matching criteria.[/yellow]")
        return

    rows = [c.to_dict() for c in candidates]
    table = make_table(f"Short Squeeze Candidates (Top {len(rows)})", rows)
    console.print(table)

    console.print("\n[bold]Sources:[/bold]")
    for s in sources:
        console.print(f"  • {s}")


# ---------------------------------------------------------------------------
# New Bloomberg / OpenBB parity commands
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("tickers", nargs=-1, required=True)
def quote(tickers: tuple[str, ...]) -> None:
    """
    Live stock quote for one or more tickers.

    \b
    Bloomberg equivalent : BQ / DES
    OpenBB equivalent    : stocks quote
    \b
    Examples:
      python main.py quote AAPL
      python main.py quote AAPL MSFT TSLA SPY
    """
    from hedge_terminal.modules.quote import get_quotes

    console.print(
        Panel(
            "[bold]Fetching live quotes...[/bold]",
            style="blue",
        )
    )
    with console.status("[bold green]Downloading quote data..."):
        quotes = get_quotes(list(tickers))

    if not quotes:
        console.print("[yellow]No quote data returned for the supplied tickers.[/yellow]")
        return

    for q in quotes:
        table = make_table(f"Quote: {q.ticker}", [q.to_dict()])
        console.print(table)


@cli.command()
@click.option(
    "--ticker",
    default=None,
    help="Ticker symbol to fetch news for (omit for broad market headlines).",
)
@click.option(
    "--limit",
    default=10,
    show_default=True,
    help="Maximum number of headlines to return.",
)
def news(ticker: str | None, limit: int) -> None:
    """
    Latest financial news headlines for a ticker or the broad market.

    \b
    Bloomberg equivalent : NEWS / NI
    OpenBB equivalent    : news
    \b
    Examples:
      python main.py news
      python main.py news --ticker AAPL
      python main.py news --ticker NVDA --limit 5
    """
    from hedge_terminal.modules.news import get_ticker_news, get_market_news

    if ticker:
        console.print(
            Panel(
                f"[bold]Fetching news for:[/bold] [cyan]{ticker.upper()}[/cyan]",
                style="blue",
            )
        )
        with console.status("[bold green]Fetching headlines..."):
            items = get_ticker_news(ticker, limit=limit)
    else:
        console.print(
            Panel("[bold]Fetching broad market headlines...[/bold]", style="blue")
        )
        with console.status("[bold green]Fetching market news..."):
            items = get_market_news(limit=limit)

    if not items:
        console.print("[yellow]No news items found.[/yellow]")
        return

    rows = [item.to_dict() for item in items]
    label = ticker.upper() if ticker else "Market"
    table = make_table(f"News: {label}", rows)
    console.print(table)


@cli.command()
@click.option(
    "--ticker",
    default="SPY",
    show_default=True,
    help="Ticker symbol to chart.",
)
@click.option(
    "--period",
    default="6mo",
    show_default=True,
    type=click.Choice(["1mo", "3mo", "6mo", "ytd", "1y", "2y", "5y"]),
    help="Time period for the chart.",
)
@click.option(
    "--interval",
    default="1d",
    show_default=True,
    type=click.Choice(["1d", "1wk", "1mo"]),
    help="Candlestick interval.",
)
@click.option(
    "--compare",
    default=None,
    help="Comma-separated additional tickers to compare (summary table only).",
)
def chart(ticker: str, period: str, interval: str, compare: str | None) -> None:
    """
    ASCII price chart in the terminal.

    \b
    Bloomberg equivalent : GP (Graph Price)
    OpenBB equivalent    : stocks candle
    \b
    Examples:
      python main.py chart --ticker AAPL
      python main.py chart --ticker SPY --period 1y
      python main.py chart --ticker NVDA --period 3mo --interval 1wk
      python main.py chart --ticker AAPL --compare MSFT,GOOGL,META
    """
    from hedge_terminal.modules.chart import get_chart, compare_charts

    console.print(
        Panel(
            f"[bold]Charting:[/bold] [cyan]{ticker.upper()}[/cyan]  "
            f"[dim]Period: {period}  Interval: {interval}[/dim]",
            style="blue",
        )
    )

    with console.status("[bold green]Downloading price data..."):
        cd = get_chart(ticker, period=period, interval=interval)

    # Render ASCII chart
    console.print(cd.render())

    # Optional comparison table
    if compare:
        extra = [t.strip().upper() for t in compare.split(",")]
        all_tickers = [ticker.upper()] + extra
        console.print(
            Panel(
                f"[bold]Comparing:[/bold] [cyan]{', '.join(all_tickers)}[/cyan]",
                style="blue",
            )
        )
        with console.status("[bold green]Downloading comparison data..."):
            charts = compare_charts(all_tickers, period=period, interval=interval)

        rows = [c.summary() for c in charts.values()]
        table = make_table("Relative Performance Comparison", rows)
        console.print(table)


@cli.command()
@click.option(
    "--preset",
    default="value",
    show_default=True,
    type=click.Choice(["value", "growth", "dividend", "quality", "low_volatility", "custom"]),
    help="Built-in screening preset.",
)
@click.option("--max-pe", default=None, type=float, help="Maximum trailing P/E ratio.")
@click.option("--min-rev-growth", default=None, type=float, help="Minimum revenue growth (e.g. 0.10 for 10%).")
@click.option("--min-margin", default=None, type=float, help="Minimum net profit margin (e.g. 0.05 for 5%).")
@click.option("--min-yield", default=None, type=float, help="Minimum dividend yield (e.g. 0.03 for 3%).")
@click.option("--max-de", default=None, type=float, help="Maximum debt-to-equity ratio.")
@click.option(
    "--tickers",
    default=None,
    help="Comma-separated custom universe to screen (default: built-in 60-ticker universe).",
)
@click.option(
    "--limit",
    default=10,
    show_default=True,
    help="Maximum number of results to return.",
)
def screen(
    preset: str,
    max_pe: float | None,
    min_rev_growth: float | None,
    min_margin: float | None,
    min_yield: float | None,
    max_de: float | None,
    tickers: str | None,
    limit: int,
) -> None:
    """
    Screen stocks by fundamental criteria.

    \b
    Bloomberg equivalent : EQSRCH / EQS
    OpenBB equivalent    : stocks screener
    \b
    Built-in presets: value | growth | dividend | quality | low_volatility
    \b
    Examples:
      python main.py screen --preset value
      python main.py screen --preset growth --limit 5
      python main.py screen --preset custom --max-pe 20 --min-margin 0.10
      python main.py screen --preset value --tickers "AAPL,MSFT,GOOGL,META,AMZN"
    """
    from hedge_terminal.modules.screener import (
        ScreenCriteria,
        PRESETS,
        screen_equities,
    )

    if preset == "custom":
        criteria = ScreenCriteria(
            max_pe=max_pe,
            min_revenue_growth=min_rev_growth,
            min_profit_margin=min_margin,
            min_dividend_yield=min_yield,
            max_debt_to_equity=max_de,
        )
    else:
        criteria = PRESETS[preset]
        # Allow CLI overrides on top of the preset
        if max_pe is not None:
            criteria.max_pe = max_pe
        if min_rev_growth is not None:
            criteria.min_revenue_growth = min_rev_growth
        if min_margin is not None:
            criteria.min_profit_margin = min_margin
        if min_yield is not None:
            criteria.min_dividend_yield = min_yield
        if max_de is not None:
            criteria.max_debt_to_equity = max_de

    universe = (
        [t.strip().upper() for t in tickers.split(",")] if tickers else None
    )

    console.print(
        Panel(
            f"[bold]Equity Screener[/bold] — preset: [cyan]{preset}[/cyan]  "
            f"limit: {limit}",
            style="blue",
        )
    )
    with console.status("[bold green]Screening equities..."):
        results = screen_equities(criteria, universe=universe, limit=limit)

    if not results:
        console.print(
            "[yellow]No stocks matched the screening criteria.[/yellow]\n"
            "[dim]Try relaxing the filters or using a different preset.[/dim]"
        )
        return

    rows = [r.to_dict() for r in results]
    table = make_table(f"Screen Results: {preset.title()} (Top {len(rows)})", rows)
    console.print(table)


# ---------------------------------------------------------------------------
# Volume Heatmap command
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--ticker",
    default="SPY",
    show_default=True,
    help="Ticker symbol to analyse.",
)
@click.option(
    "--period",
    default="3mo",
    show_default=True,
    type=click.Choice(["1mo", "3mo", "6mo", "ytd", "1y"]),
    help="Historical period.",
)
@click.option(
    "--interval",
    default="1d",
    show_default=True,
    type=click.Choice(["1d", "1wk"]),
    help="Bar interval.",
)
@click.option(
    "--bins",
    default=30,
    show_default=True,
    help="Number of price buckets on the Y-axis (10–60).",
)
@click.option(
    "--compare",
    default=None,
    help="Comma-separated extra tickers for a side-by-side summary table.",
)
def heatmap(ticker: str, period: str, interval: str, bins: int, compare: str | None) -> None:
    """
    Volume heatmap: price × time matrix coloured by traded volume.

    \b
    Brighter / denser cells = more volume at that price level.
    Key volume profile levels are annotated on the right edge:
      POC = Point of Control (highest-volume price)
      VAH = Value Area High  (upper bound of 70% volume zone)
      VAL = Value Area Low   (lower bound of 70% volume zone)
    \b
    Bloomberg equivalent : GP volume overlay / VWAP band view
    Sierra Chart         : Volume by Price / TPO Profile
    Bookmap              : Heatmap layer
    \b
    Examples:
      python main.py heatmap --ticker SPY
      python main.py heatmap --ticker AAPL --period 6mo
      python main.py heatmap --ticker NVDA --period 1mo --bins 20
      python main.py heatmap --ticker SPY --compare QQQ,IWM,DIA
    """
    from hedge_terminal.modules.heatmap import get_volume_heatmap

    bins = max(10, min(bins, 60))  # clamp to sensible range

    console.print(
        Panel(
            f"[bold]Volume Heatmap:[/bold] [cyan]{ticker.upper()}[/cyan]  "
            f"[dim]Period: {period}  Interval: {interval}  Bins: {bins}[/dim]",
            style="blue",
        )
    )

    with console.status("[bold green]Building volume heatmap..."):
        hm = get_volume_heatmap(ticker, period=period, interval=interval, price_bins=bins)

    console.print(hm.render())

    if compare:
        extra = [t.strip().upper() for t in compare.split(",")]
        all_tickers = [ticker.upper()] + extra
        console.print(
            Panel(
                f"[bold]Comparing:[/bold] [cyan]{', '.join(all_tickers)}[/cyan]",
                style="blue",
            )
        )
        rows = [hm.summary()]
        with console.status("[bold green]Fetching comparison data..."):
            for t in extra:
                try:
                    hm_t = get_volume_heatmap(t, period=period, interval=interval, price_bins=bins)
                    rows.append(hm_t.summary())
                except Exception:  # noqa: BLE001
                    pass
        table = make_table("Volume Profile Comparison", rows)
        console.print(table)
    else:
        # Always show the summary table for the primary ticker
        table = make_table(f"Volume Profile: {ticker.upper()}", [hm.summary()])
        console.print(table)


# ---------------------------------------------------------------------------
# Footprint Chart command
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--ticker",
    default="SPY",
    show_default=True,
    help="Ticker symbol to analyse.",
)
@click.option(
    "--period",
    default="1mo",
    show_default=True,
    type=click.Choice(["5d", "1mo", "3mo", "6mo", "ytd", "1y"]),
    help="Historical period.",
)
@click.option(
    "--interval",
    default="1d",
    show_default=True,
    type=click.Choice(["1d", "1wk"]),
    help="Bar interval.",
)
@click.option(
    "--last",
    default=20,
    show_default=True,
    help="Number of most-recent bars to display in the delta chart.",
)
@click.option(
    "--table",
    "show_table",
    is_flag=True,
    default=False,
    help="Also print a detailed bid/ask/delta table for each bar.",
)
def footprint(ticker: str, period: str, interval: str, last: int, show_table: bool) -> None:
    """
    Footprint chart: estimated bid vs. ask volume and delta per bar.

    \b
    Delta = Ask Volume − Bid Volume
      Positive delta → net buying pressure (ask side dominant)
      Negative delta → net selling pressure (bid side dominant)
    Bid/ask volumes are estimated from OHLCV using the candle
    body-to-range ratio method (approximation, not real tick data).
    \b
    Bloomberg equivalent : Order-flow analytics (premium add-on)
    Bookmap              : Footprint / delta layer
    Sierra Chart         : Bid/Ask footprint bars
    NinjaTrader          : Volumetric bars
    \b
    Examples:
      python main.py footprint --ticker SPY
      python main.py footprint --ticker AAPL --period 3mo --last 30
      python main.py footprint --ticker NVDA --interval 1wk --table
      python main.py footprint --ticker SPY --period 5d
    """
    from hedge_terminal.modules.footprint import get_footprint

    console.print(
        Panel(
            f"[bold]Footprint Chart:[/bold] [cyan]{ticker.upper()}[/cyan]  "
            f"[dim]Period: {period}  Interval: {interval}  Last {last} bars[/dim]",
            style="blue",
        )
    )

    with console.status("[bold green]Calculating bid/ask delta..."):
        fp = get_footprint(ticker, period=period, interval=interval)

    if not fp.bars:
        console.print("[yellow]No footprint data returned.[/yellow]")
        return

    # Delta bar chart (always shown)
    console.print(fp.render(last_n=last))

    # Summary row
    table = make_table(f"Footprint Summary: {ticker.upper()}", [fp.summary()])
    console.print(table)

    # Optional detailed bar table
    if show_table:
        rows = fp.to_table_rows(last_n=last)
        detail_table = make_table(
            f"Bid/Ask Detail (last {min(last, len(fp.bars))} bars)", rows
        )
        console.print(detail_table)


if __name__ == "__main__":
    cli()
