# OpenSource Hedge Terminal

> **No more $24,000/year subscriptions.** Turn your laptop into a private quant analyst — completely free, open-source, and powered by public data.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

**OpenSource Hedge Terminal** is a Python CLI toolkit that replicates the core analytical workflows of expensive institutional quant platforms, using only **free and public data sources**:

| Module | What it does | Free data sources |
|---|---|---|
| `hedge` | Design efficient portfolio hedges with options or inverse ETFs | yfinance options chains, CBOE VIX |
| `whales` | Track top 10 hedge fund 13F position changes | Dataroma, WhaleWisdom, SEC EDGAR |
| `dividends` | Screen for risky high-yield dividend stocks | yfinance fundamentals |
| `correlations` | Detect unusual cross-asset correlations & normalization trades | yfinance price history |
| `sentiment` | Find sentiment vs. fundamentals divergence opportunities | yfinance, Yahoo Finance news |
| `macro` | Analyze macro regime + sector outperformance history | FRED (St. Louis Fed), yfinance |
| `squeeze` | Find short squeeze candidates with catalysts | yfinance, Finviz, SEC EDGAR |

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

### 1. Portfolio Hedge Designer

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

### 2. Whale / 13F Tracker

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

### 3. Dividend Warning Screener

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

### 4. Correlation Scanner

Detect unusual cross-asset correlations and generate normalization trades:

```bash
python main.py correlations
```

**Monitored pairs:** S&P 500 / Gold, Equities / Bonds, Gold / USD, VIX / Equities, and more.
**Output includes:** current vs. historical correlation, signal description, 3 normalization trades, historical analogues.

---

### 5. Sentiment vs. Fundamentals Analyzer

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

### 6. Macro Context Analyzer

Fetch current macro data and identify which sectors historically outperform in this regime:

```bash
python main.py macro
```

**Data sources:** FRED (Fed Funds Rate, CPI, GDP, Unemployment), yfinance sector ETFs
**Output includes:** inflation regime, rate cycle, growth phase, historically outperforming/underperforming sectors, 3 comparable historical examples, expected timeframe, and live sector YTD returns.

---

### 7. Short Squeeze Finder

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

All 43 tests run offline (network calls are mocked).

---

## Disclaimer

This tool is for **educational and informational purposes only**. Nothing in this repository constitutes financial advice. Always do your own research before making investment decisions. Past performance of historical analogues does not guarantee future results.

---

## License

MIT License – see [LICENSE](LICENSE).