"""
OpenSource Hedge Terminal – CLI
================================
A free, open-source quant analyst toolkit for portfolio hedging, macro
analysis, sentiment divergence, and more — no paid subscriptions required.

Usage
-----
    python main.py --help
    python main.py hedge --sector technology
    python main.py whales
    python main.py dividends
    python main.py correlations
    python main.py sentiment
    python main.py macro
    python main.py squeeze
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
[bold yellow]  T E R M I N A L[/bold yellow]  [dim]– Free, Open-Source Quant Analyst[/dim]
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
    """OpenSource Hedge Terminal – your free private quant analyst."""
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


if __name__ == "__main__":
    cli()
