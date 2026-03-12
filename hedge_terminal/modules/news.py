"""
News Module
===========
Fetch the latest financial news headlines for a ticker or topic.

Replicates Bloomberg Terminal's **NEWS** function and
OpenBB Terminal's ``news`` command — for free, using Yahoo Finance RSS,
yfinance news, and the SEC EDGAR full-text search.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

try:
    import yfinance as yf  # type: ignore
except ImportError:  # pragma: no cover
    yf = None  # type: ignore


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class NewsItem:
    title: str
    publisher: str
    published_at: str  # human-readable ISO datetime string
    url: str
    summary: str
    ticker: str  # associated ticker, empty for global/market news
    source_feed: str  # "yfinance" | "yahoo_rss" | "sec_edgar"

    def to_dict(self) -> dict[str, str]:
        return {
            "Ticker": self.ticker or "Market",
            "Published": self.published_at,
            "Publisher": self.publisher,
            "Title": self.title,
            "Summary": self.summary[:200] + "…" if len(self.summary) > 200 else self.summary,
            "URL": self.url,
            "Source": self.source_feed,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_to_str(ts: int | float | None) -> str:
    """Convert a Unix timestamp to a readable UTC datetime string."""
    if ts is None:
        return "N/A"
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    except Exception:  # noqa: BLE001
        return str(ts)


def _clean_html(raw: str) -> str:
    """Strip HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", raw).strip()


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def _fetch_yfinance_news(ticker: str, limit: int) -> list[NewsItem]:
    """Pull news items attached to a specific ticker via yfinance."""
    items: list[NewsItem] = []
    if yf is None:
        return items
    try:
        t = yf.Ticker(ticker.upper())
        raw_news = t.news or []
        for art in raw_news[:limit]:
            content = art.get("content", {})
            title = content.get("title") or art.get("title", "")
            pub = (
                content.get("provider", {}).get("displayName")
                or art.get("publisher", "")
            )
            ts = (
                content.get("pubDate")
                or art.get("providerPublishTime")
            )
            # ts may be ISO string or unix int
            if isinstance(ts, (int, float)):
                ts_str = _ts_to_str(ts)
            else:
                ts_str = str(ts) if ts else "N/A"

            url = (
                content.get("canonicalUrl", {}).get("url")
                or art.get("link", "")
            )
            summary_raw = (
                content.get("summary")
                or art.get("summary", "")
                or ""
            )
            summary = _clean_html(summary_raw)

            if title:
                items.append(
                    NewsItem(
                        title=title,
                        publisher=pub,
                        published_at=ts_str,
                        url=url,
                        summary=summary,
                        ticker=ticker.upper(),
                        source_feed="yfinance",
                    )
                )
    except Exception:  # noqa: BLE001
        pass
    return items


def _fetch_yahoo_rss(query: str, limit: int) -> list[NewsItem]:
    """
    Fetch headlines from Yahoo Finance RSS for a search query.
    Works for both ticker symbols and topics (e.g. "Federal Reserve").
    """
    items: list[NewsItem] = []
    url = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={requests.utils.quote(query)}&region=US&lang=en-US"
    )
    headers = {"User-Agent": "Mozilla/5.0 (compatible; OpenSource-Hedge-Terminal/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        # Simple XML parsing without external deps
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", resp.text)
        links = re.findall(r"<link>(https?://[^<]+)</link>", resp.text)
        pub_dates = re.findall(r"<pubDate>(.*?)</pubDate>", resp.text)
        descriptions = re.findall(
            r"<description><!\[CDATA\[(.*?)\]\]></description>", resp.text
        )
        # The first <title> element in an RSS feed is the channel name (feed title),
        # not a news item — skip it so we only process article titles.
        titles = titles[1:] if len(titles) > 1 else titles
        for i, title in enumerate(titles[:limit]):
            items.append(
                NewsItem(
                    title=title,
                    publisher="Yahoo Finance",
                    published_at=pub_dates[i + 1] if i + 1 < len(pub_dates) else "N/A",
                    url=links[i] if i < len(links) else "",
                    summary=_clean_html(descriptions[i + 1]) if i + 1 < len(descriptions) else "",
                    ticker=query,
                    source_feed="yahoo_rss",
                )
            )
    except Exception:  # noqa: BLE001
        pass
    return items


def _fetch_sec_filings(ticker: str, limit: int) -> list[NewsItem]:
    """
    Pull the most recent 8-K / 10-Q / 10-K filings from SEC EDGAR
    as a news-style feed for a ticker.
    """
    items: list[NewsItem] = []
    url = (
        "https://efts.sec.gov/LATEST/search-index?q=%22"
        f"{requests.utils.quote(ticker.upper())}"
        "%22&dateRange=custom&startdt=2024-01-01"
        "&forms=8-K,10-K,10-Q&hits.hits.total.value=true"
        f"&hits.hits._source=file_date,period_of_report,entity_name,file_num"
        f"&hits.hits.highlight=false&_source=file_date,period_of_report"
        f",entity_name,form_type,file_num,period_of_report"
        f"&dateRange=custom&hits.hits.total.value=true"
    )
    # Simpler EDGAR full-text search
    url = (
        f"https://efts.sec.gov/LATEST/search-index?q=%22{requests.utils.quote(ticker.upper())}%22"
        f"&forms=8-K,10-K,10-Q&hits.hits.total.value=true"
    )
    try:
        headers = {"User-Agent": "OpenSource-Hedge-Terminal research@example.com"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        for hit in hits[:limit]:
            src = hit.get("_source", {})
            entity = src.get("entity_name", ticker.upper())
            form_type = src.get("form_type", "Filing")
            file_date = src.get("file_date", "N/A")
            accession = hit.get("_id", "").replace(":", "-")
            filing_url = (
                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                f"&CIK={ticker.upper()}&type={form_type}&dateb=&owner=include&count=10"
            )
            items.append(
                NewsItem(
                    title=f"SEC {form_type} Filing — {entity}",
                    publisher="SEC EDGAR",
                    published_at=file_date,
                    url=filing_url,
                    summary=f"{form_type} filed on {file_date} by {entity}.",
                    ticker=ticker.upper(),
                    source_feed="sec_edgar",
                )
            )
    except Exception:  # noqa: BLE001
        pass
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_ticker_news(ticker: str, limit: int = 10) -> list[NewsItem]:
    """
    Return the latest news items for *ticker*.

    Sources tried in order: yfinance → Yahoo Finance RSS → SEC EDGAR filings.
    Results are deduplicated by title and capped at *limit*.
    """
    items: list[NewsItem] = []

    # 1. yfinance news (most recent, structured)
    items.extend(_fetch_yfinance_news(ticker, limit))

    # 2. Yahoo Finance RSS (broader coverage)
    if len(items) < limit:
        items.extend(_fetch_yahoo_rss(ticker, limit - len(items)))

    # 3. SEC filings as news
    if len(items) < limit:
        items.extend(_fetch_sec_filings(ticker, limit - len(items)))

    # Deduplicate by title
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        key = item.title.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique[:limit]


def get_market_news(limit: int = 10) -> list[NewsItem]:
    """
    Return broad market / macro news from Yahoo Finance RSS.
    Equivalent to Bloomberg's top-of-screen news ticker.
    """
    topics = ["markets", "economy", "federal+reserve", "stocks"]
    items: list[NewsItem] = []
    per_topic = max(2, limit // len(topics))
    for topic in topics:
        items.extend(_fetch_yahoo_rss(topic, per_topic))
        if len(items) >= limit:
            break
    # deduplicate
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        key = item.title.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:limit]
