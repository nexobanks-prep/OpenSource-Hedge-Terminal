# OpenSource Hedge Terminal

> **No more $24,000/year subscriptions.** Turn your laptop into a private quant analyst — completely free, open-source, and powered by public data.
>
> **Yes — this is the free, open-source alternative to both Bloomberg Terminal and OpenBB Terminal.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## How It Compares

| Feature | Bloomberg Terminal | OpenBB Terminal | **OpenSource Hedge Terminal** |
|---|:---:|:---:|:---:|
| **Cost** | ~$24,000 / year | Free (open-source) | **Free (open-source)** |
| **Live Quotes** (`BQ` / `stocks quote`) | ✅ | ✅ | ✅ `quote` |
| **News Feed** (`NEWS` / `news`) | ✅ | ✅ | ✅ `news` |
| **Price Charts** (`GP` / `stocks candle`) | ✅ | ✅ | ✅ `chart` |
| **Equity Screener** (`EQSRCH` / screener) | ✅ | ✅ | ✅ `screen` |
| **Macro Data** (`ECOW` / economy) | ✅ | ✅ | ✅ `macro` |
| **Portfolio Hedge Designer** (`MARS`) | ✅ | ❌ | ✅ `hedge` |
| **13F Whale Tracker** (institutional) | ✅ (premium) | ✅ | ✅ `whales` |
| **Dividend Warning Screener** (`DVD`) | ✅ | ✅ | ✅ `dividends` |
| **Cross-Asset Correlations** (`CORR`) | ✅ | ✅ | ✅ `correlations` |
| **Sentiment vs. Fundamentals** | ✅ (premium) | ✅ | ✅ `sentiment` |
| **Short Squeeze Finder** (`SI` / `sia`) | ✅ | ✅ | ✅ `squeeze` |
| **Volume Heatmap** (Volume Profile) | ✅ (premium) | ✅ | ✅ `heatmap` |
| **Footprint Chart** (Order Flow Delta) | ✅ (premium) | ❌ | ✅ `footprint` |
| **Runs offline / no API key required** | ❌ | partial | ✅ |

---

## Overview

**OpenSource Hedge Terminal** is a Python CLI toolkit that replicates the core analytical workflows of Bloomberg Terminal and OpenBB Terminal, using only **free and public data sources**:

| Module | Bloomberg Equivalent | OpenBB Equivalent | Free data sources |
|---|---|---|---|
| `quote` | BQ / DES | `stocks quote` | yfinance |
| `news` | NEWS / NI | `news` | yfinance, Yahoo Finance RSS, SEC EDGAR |
| `chart` | GP (Graph Price) | `stocks candle` | yfinance |
| `screen` | EQSRCH / EQS | `stocks screener` | yfinance fundamentals |
| `hedge` | MARS / DLIB | custom | yfinance options chains, CBOE VIX |
| `whales` | 13F data (premium) | alternative data | Dataroma, WhaleWisdom, SEC EDGAR |
| `dividends` | DVD | `stocks dps` | yfinance fundamentals |
| `correlations` | CORR | custom | yfinance price history |
| `sentiment` | SRCH / NEWS (premium) | `stocks ba` | yfinance, Yahoo Finance news |
| `macro` | ECOW / WECO | `economy` | FRED (St. Louis Fed), yfinance |
| `squeeze` | SI / FSHO | `stocks sia` | yfinance, Finviz, SEC EDGAR |
| `heatmap` | GP volume overlay / VWAP bands | Sierra Chart Vol-by-Price | yfinance |
| `footprint` | Order-flow analytics (premium) | custom | yfinance OHLCV (approx.) |

---

## Installation

```bash
git clone https://github.com/nexobanks-prep/OpenSource-Hedge-Terminal.git
cd OpenSource-Hedge-Terminal
pip install -r requirements.txt
```

### Requirements

- Python 3.10+
- See [`requirements.txt`](requirements.txt) for all dependencies (all free/open-source)

---

## Usage

```
python main.py --help
```

### 1. Live Stock Quote  *(Bloomberg BQ / OpenBB `stocks quote`)*

Fetch live/delayed price, fundamentals, and key statistics for any ticker:

```bash
python main.py quote AAPL
python main.py quote AAPL MSFT TSLA SPY
python main.py quote ^GSPC ^VIX GLD
```

**Output includes:** price, day change %, open/close, 52-week range, market cap, P/E, EPS, dividend yield, beta, sector/industry.

---

### 2. Financial News Feed  *(Bloomberg NEWS / OpenBB `news`)*

Fetch the latest headlines for a specific ticker or the broad market:

```bash
# Broad market headlines
python main.py news

# Ticker-specific news
python main.py news --ticker AAPL
python main.py news --ticker NVDA --limit 5
```

**Sources:** yfinance news, Yahoo Finance RSS, SEC EDGAR 8-K/10-K/10-Q filings.

---

### 3. ASCII Price Chart  *(Bloomberg GP / OpenBB `stocks candle`)*

Render a price chart directly in the terminal using Unicode block characters:

```bash
python main.py chart --ticker AAPL
python main.py chart --ticker SPY --period 1y
python main.py chart --ticker NVDA --period 3mo --interval 1wk
python main.py chart --ticker AAPL --compare MSFT,GOOGL,META
```

**Options:** `--period` (1mo / 3mo / 6mo / ytd / 1y / 2y / 5y), `--interval` (1d / 1wk / 1mo), `--compare` (relative performance table).

---

### 4. Equity Screener  *(Bloomberg EQSRCH / OpenBB screener)*

Screen stocks against fundamental criteria using built-in presets or fully custom filters:

```bash
# Built-in presets
python main.py screen --preset value
python main.py screen --preset growth --limit 5
python main.py screen --preset dividend
python main.py screen --preset quality
python main.py screen --preset low_volatility

# Custom filters
python main.py screen --preset custom --max-pe 20 --min-margin 0.10
python main.py screen --preset value --tickers "AAPL,MSFT,GOOGL,META,AMZN"
```

**Built-in presets:**

| Preset | Criteria |
|---|---|
| `value` | P/E ≤ 15, P/B ≤ 2, margin ≥ 5%, D/E ≤ 150 |
| `growth` | Revenue growth ≥ 15%, EPS growth ≥ 15%, margin ≥ 8% |
| `dividend` | Yield ≥ 3%, payout ratio ≤ 75%, margin ≥ 5% |
| `quality` | Margin ≥ 15%, ROE ≥ 15%, D/E ≤ 100, growth ≥ 5% |
| `low_volatility` | Beta ≤ 0.8, margin ≥ 5%, D/E ≤ 100 |

---

### 5. Portfolio Hedge Designer  *(Bloomberg MARS/DLIB)*

Design a hedge for a specific sector/market exposure using options or inverse ETFs:

```bash
# Hedge technology sector exposure
python main.py hedge --sector technology

# Hedge energy exposure using put options
python main.py hedge --sector energy --puts

# Hedge broad market with a custom portfolio ETF
python main.py hedge --sector "broad market" --ticker QQQ
```

**Output includes:** recommended instrument, hedge size (% of portfolio), annualized cost estimate, activation scenario, current VIX level, and near-ATM implied volatility.

---

### 6. Whale / 13F Tracker  *(Bloomberg institutional data / OpenBB alternative data)*

Identify what top hedge funds are accumulating, trimming, and exiting:

```bash
# All position changes
python main.py whales

# Filter by type
python main.py whales --filter new
python main.py whales --filter exited
python main.py whales --filter increased
python main.py whales --filter decreased
```

**Data sources:** Dataroma, WhaleWisdom, SEC EDGAR 13F-HR filings

---

### 7. Dividend Warning Screener  *(Bloomberg DVD / OpenBB `stocks dps`)*

Screen for stocks with attractive yields (>5%) but with dangerous warning signs:

```bash
# Screen built-in watch list
python main.py dividends

# Screen custom tickers
python main.py dividends --tickers "T,MO,WBA,INTC,MPW"

# Limit results
python main.py dividends --limit 3
```

**Output includes:** current yield, payout ratio, free cash flow, debt metrics, dividend cut probability, and safer alternatives in the same sector.

---

### 8. Correlation Scanner  *(Bloomberg CORR)*

Detect unusual cross-asset correlations and generate normalization trades:

```bash
python main.py correlations
```

**Monitored pairs:** S&P 500 / Gold, Equities / Bonds, Gold / USD, VIX / Equities, and more.
**Output includes:** current vs. historical correlation, signal description, 3 normalization trades, historical analogues.

---

### 9. Sentiment vs. Fundamentals Analyzer  *(Bloomberg SRCH/NEWS)*

Find stocks where negative market sentiment contradicts strong underlying fundamentals:

```bash
# Default candidates
python main.py sentiment

# Custom tickers
python main.py sentiment --tickers "META,BABA,PYPL,DIS"

# Limit results
python main.py sentiment --limit 4
```

**Output includes:** ticker, negative sentiment reason, fundamental bull case, technical entry level, P/E, revenue growth, profit margins.

---

### 10. Macro Context Analyzer  *(Bloomberg ECOW/WECO / OpenBB `economy`)*

Fetch current macro data and identify which sectors historically outperform in this regime:

```bash
python main.py macro
```

**Data sources:** FRED (Fed Funds Rate, CPI, GDP, Unemployment), yfinance sector ETFs
**Output includes:** inflation regime, rate cycle, growth phase, historically outperforming/underperforming sectors, 3 comparable historical examples, expected timeframe, and live sector YTD returns.

---

### 11. Short Squeeze Finder  *(Bloomberg SI/FSHO / OpenBB `stocks sia`)*

Find stocks with high short interest (>20% of float), elevated borrow rates, and upcoming catalysts:

```bash
# Default curated list
python main.py squeeze

# Custom tickers
python main.py squeeze --tickers "GME,BYND,UPST"

# Minimum short float threshold
python main.py squeeze --min-short 25

# Limit results
python main.py squeeze --limit 3
```

**Output includes:** % short float, days to cover, borrow rate, catalyst, entry strategy, failed squeeze risk factors, squeeze score.

---

### 12. Volume Heatmap  *(Bloomberg GP volume overlay / Sierra Chart Volume by Price)*

Visualise where the most trading volume has accumulated at each price level — revealing key support/resistance zones and areas of high liquidity.  The terminal renders a **price × time** intensity matrix where brighter cells = more traded volume.

```bash
# Default: SPY, last 3 months, daily bars, 30 price bins
python main.py heatmap

# Custom ticker and period
python main.py heatmap --ticker AAPL
python main.py heatmap --ticker NVDA --period 6mo

# Finer price resolution
python main.py heatmap --ticker SPY --bins 40

# Side-by-side summary for multiple tickers
python main.py heatmap --ticker SPY --compare QQQ,IWM,DIA
```

**Output includes:**
- ASCII intensity grid (Unicode shade characters `░ ▒ ▓ █` coloured cool → hot)
- **Point of Control (POC)** — price level with the highest cumulative volume
- **Value Area High (VAH)** — upper bound of the 70 % value zone
- **Value Area Low (VAL)** — lower bound of the 70 % value zone
- Price vs. POC: how far current price is from the highest-volume level

---

### 13. Footprint Chart  *(Bookmap / Sierra Chart / NinjaTrader Volumetric Bars)*

Shows the estimated **bid (sell) vs. ask (buy) volume** for each bar, along with the **delta** (Ask − Bid).  Positive delta signals net buying pressure; negative signals distribution.

Since yfinance provides OHLCV data only (not tick data), bid/ask volumes are approximated using the **candle body-to-range ratio method** — a widely-used technique when tick data is unavailable.

```bash
# Default: SPY, last 1 month, daily bars, last 20 bars shown
python main.py footprint

# Custom ticker and period
python main.py footprint --ticker AAPL
python main.py footprint --ticker NVDA --period 3mo --last 30

# Weekly bars
python main.py footprint --ticker SPY --interval 1wk

# Full bid/ask detail table in addition to the delta chart
python main.py footprint --ticker AAPL --table
```

**Output includes:**
- Delta bar chart for the last N bars (green = net buying, red = net selling)
- Cumulative delta trend
- Imbalance signals when one side dominates by 3× or more (e.g. `⚡ BUY 4.2×`)
- Optional detailed table: Date | Dir | Open | High | Low | Close | Volume | Bid Vol | Ask Vol | Delta | Delta % | Cum. Δ

---

## Free Data Sources

All data is sourced from **free, public APIs**:

| Source | Data | URL |
|---|---|---|
| **yfinance** | Prices, options chains, fundamentals, short interest | https://github.com/ranaroussi/yfinance |
| **FRED** | CPI, Fed Funds Rate, GDP, Unemployment | https://fred.stlouisfed.org |
| **CBOE** | VIX index | https://www.cboe.com/tradable_products/vix/ |
| **Dataroma** | 13F super-investor holdings aggregator | https://www.dataroma.com |
| **WhaleWisdom** | Hedge fund 13F tracker | https://whalewisdom.com |
| **SEC EDGAR** | 13F-HR filings, 8-K filings | https://efts.sec.gov |
| **Finviz** | Short interest screener | https://finviz.com/screener.ashx |
| **ShortQuote** | Borrow rates, short volume | https://shortquote.com |

---

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

All 97 tests run offline (network calls are mocked).

---

## Disclaimer

This tool is for **educational and informational purposes only**. Nothing in this repository constitutes financial advice. Always do your own research before making investment decisions. Past performance of historical analogues does not guarantee future results.

---

## License

MIT License – see [LICENSE](LICENSE).