"""
Tests for the OpenSource Hedge Terminal modules.

All tests are designed to run offline (no network required) by patching
the data fetching utilities.
"""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_price_df(prices: list[float], ticker: str = "SPY") -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame from a list of close prices."""
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="B")
    return pd.DataFrame(
        {
            "Open": prices,
            "High": [p * 1.01 for p in prices],
            "Low": [p * 0.99 for p in prices],
            "Close": prices,
            "Volume": [1_000_000] * len(prices),
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# hedge_designer tests
# ---------------------------------------------------------------------------

class TestHedgeDesigner:
    def _make_info(self, price: float = 450.0) -> dict:
        return {
            "regularMarketPrice": price,
            "currentPrice": price,
        }

    def _make_options_chain(self) -> dict:
        calls = pd.DataFrame(
            {"strike": [440, 450, 460], "impliedVolatility": [0.20, 0.22, 0.24]}
        )
        puts = pd.DataFrame(
            {"strike": [440, 450, 460], "impliedVolatility": [0.21, 0.23, 0.25]}
        )
        return {"calls": calls, "puts": puts, "expiry": "2024-03-15"}

    @patch("hedge_terminal.modules.hedge_designer.get_price_history")
    @patch("hedge_terminal.modules.hedge_designer.get_options_chain")
    @patch("hedge_terminal.modules.hedge_designer.get_ticker_info")
    def test_design_hedge_returns_recommendation(
        self, mock_info, mock_chain, mock_hist
    ):
        from hedge_terminal.modules.hedge_designer import design_hedge, HedgeRecommendation

        mock_hist.return_value = _make_price_df([18.0, 19.0, 20.0], "^VIX")
        mock_chain.return_value = self._make_options_chain()
        mock_info.return_value = self._make_info()

        rec = design_hedge("technology")

        assert isinstance(rec, HedgeRecommendation)
        assert rec.sector == "technology"
        assert rec.recommended_instrument != ""
        assert 0 < rec.hedge_size_pct <= 20
        assert rec.annualized_cost_pct > 0
        assert len(rec.activation_scenario) > 20

    @patch("hedge_terminal.modules.hedge_designer.get_price_history")
    @patch("hedge_terminal.modules.hedge_designer.get_options_chain")
    @patch("hedge_terminal.modules.hedge_designer.get_ticker_info")
    def test_design_hedge_puts_option(self, mock_info, mock_chain, mock_hist):
        from hedge_terminal.modules.hedge_designer import design_hedge

        mock_hist.return_value = _make_price_df([20.0] * 5, "^VIX")
        mock_chain.return_value = self._make_options_chain()
        mock_info.return_value = self._make_info()

        rec = design_hedge("technology", prefer_puts=True)
        assert "put" in rec.recommended_instrument.lower()

    @patch("hedge_terminal.modules.hedge_designer.get_price_history")
    @patch("hedge_terminal.modules.hedge_designer.get_options_chain")
    @patch("hedge_terminal.modules.hedge_designer.get_ticker_info")
    def test_design_hedge_unknown_sector_defaults_to_broad(
        self, mock_info, mock_chain, mock_hist
    ):
        from hedge_terminal.modules.hedge_designer import design_hedge, INVERSE_ETF_MAP

        mock_hist.return_value = _make_price_df([20.0] * 5, "^VIX")
        mock_chain.return_value = self._make_options_chain()
        mock_info.return_value = self._make_info()

        rec = design_hedge("exotic derivatives market")
        broad_tickers = {e["ticker"] for e in INVERSE_ETF_MAP["broad market"]}
        assert rec.recommended_instrument in broad_tickers

    def test_hedge_size_increases_with_vix(self):
        from hedge_terminal.modules.hedge_designer import _hedge_size

        assert _hedge_size(10) < _hedge_size(20) < _hedge_size(30)

    def test_activation_scenario_contains_sector(self):
        from hedge_terminal.modules.hedge_designer import _activation_scenario

        scenario = _activation_scenario("technology", 18)
        assert "Technology" in scenario

    def test_to_dict_has_expected_keys(self):
        from hedge_terminal.modules.hedge_designer import HedgeRecommendation

        rec = HedgeRecommendation(
            sector="energy",
            recommended_instrument="ERY",
            instrument_name="Test ETF",
            hedge_size_pct=10.0,
            annualized_cost_pct=3.5,
            activation_scenario="Test scenario",
            current_vix=20.0,
            implied_volatility=25.0,
            data_sources=["source1"],
        )
        d = rec.to_dict()
        assert "Recommended Instrument" in d
        assert "Hedge Size (% of Portfolio)" in d
        assert "Activation Scenario" in d


# ---------------------------------------------------------------------------
# whale_tracker tests
# ---------------------------------------------------------------------------

class TestWhaleTracker:
    def test_fallback_positions_returned_on_network_error(self):
        from hedge_terminal.modules.whale_tracker import get_whale_activity

        with patch("hedge_terminal.modules.whale_tracker._fetch_dataroma") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame()
            positions, sources = get_whale_activity()

        assert len(positions) > 0
        assert len(sources) > 0

    def test_filter_new_positions(self):
        from hedge_terminal.modules.whale_tracker import get_whale_activity

        with patch("hedge_terminal.modules.whale_tracker._fetch_dataroma") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame()
            positions, _ = get_whale_activity(change_type_filter="new")

        for p in positions:
            assert p.change_type == "new"

    def test_filter_exited_positions(self):
        from hedge_terminal.modules.whale_tracker import get_whale_activity

        with patch("hedge_terminal.modules.whale_tracker._fetch_dataroma") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame()
            positions, _ = get_whale_activity(change_type_filter="exited")

        for p in positions:
            assert p.change_type == "exited"

    def test_position_change_to_dict(self):
        from hedge_terminal.modules.whale_tracker import PositionChange

        pc = PositionChange(
            fund="Test Fund",
            ticker="AAPL",
            company="Apple Inc",
            change_type="new",
            shares_current=1_000_000,
            shares_previous=None,
            pct_change=None,
            sector="Technology",
        )
        d = pc.to_dict()
        assert d["Fund"] == "Test Fund"
        assert d["Change"] == "NEW"
        assert d["Ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# dividend_analyzer tests
# ---------------------------------------------------------------------------

class TestDividendAnalyzer:
    def _make_info(
        self,
        yield_val: float = 0.07,
        payout: float = 1.20,
        fcf: float = -1e9,
        debt: float = 50e9,
        net_income: float = 5e9,
        sector: str = "Utilities",
    ) -> dict:
        return {
            "dividendYield": yield_val,
            "payoutRatio": payout,
            "freeCashflow": fcf,
            "totalDebt": debt,
            "netIncomeToCommon": net_income,
            "sector": sector,
            "longName": "Test Company",
        }

    @patch("hedge_terminal.modules.dividend_analyzer.get_ticker_info")
    def test_warning_returned_for_risky_stock(self, mock_info):
        from hedge_terminal.modules.dividend_analyzer import analyze_dividend_stock

        mock_info.return_value = self._make_info()
        result = analyze_dividend_stock("TEST")

        assert result is not None
        assert result.current_yield_pct > 5
        assert len(result.warning_flags) > 0

    @patch("hedge_terminal.modules.dividend_analyzer.get_ticker_info")
    def test_no_warning_for_low_yield(self, mock_info):
        from hedge_terminal.modules.dividend_analyzer import analyze_dividend_stock

        info = self._make_info(yield_val=0.02)  # 2% yield
        mock_info.return_value = info
        result = analyze_dividend_stock("TEST")

        assert result is None

    def test_cut_probability_high_for_negative_fcf_and_high_payout(self):
        from hedge_terminal.modules.dividend_analyzer import _score_cut_probability

        score = _score_cut_probability(
            payout_ratio=150, fcf=-5e9, debt=50e9, earnings=5e9
        )
        assert score >= 50

    def test_cut_probability_low_for_healthy_stock(self):
        from hedge_terminal.modules.dividend_analyzer import _score_cut_probability

        score = _score_cut_probability(
            payout_ratio=40, fcf=5e9, debt=10e9, earnings=20e9
        )
        assert score < 20

    def test_warning_flags_payout_ratio(self):
        from hedge_terminal.modules.dividend_analyzer import _build_warning_flags

        flags = _build_warning_flags(
            payout_ratio=110, fcf=1e9, debt=10e9, earnings=5e9, yield_pct=6.0
        )
        assert any("Payout ratio" in f for f in flags)

    def test_warning_flags_negative_fcf(self):
        from hedge_terminal.modules.dividend_analyzer import _build_warning_flags

        flags = _build_warning_flags(
            payout_ratio=40, fcf=-1e9, debt=10e9, earnings=5e9, yield_pct=6.0
        )
        assert any("free cash flow" in f.lower() for f in flags)

    @patch("hedge_terminal.modules.dividend_analyzer.get_ticker_info")
    def test_screen_returns_up_to_limit(self, mock_info):
        from hedge_terminal.modules.dividend_analyzer import screen_dividend_warnings

        mock_info.return_value = self._make_info()
        results = screen_dividend_warnings(limit=3)
        assert len(results) <= 3

    def test_sector_safe_alternatives_populated(self):
        from hedge_terminal.modules.dividend_analyzer import SECTOR_SAFE_ALTERNATIVES

        assert "Utilities" in SECTOR_SAFE_ALTERNATIVES
        assert len(SECTOR_SAFE_ALTERNATIVES["Utilities"]) >= 2


# ---------------------------------------------------------------------------
# correlation_scanner tests
# ---------------------------------------------------------------------------

class TestCorrelationScanner:
    def _make_multi_price_df(self) -> dict[str, pd.Series]:
        """Create synthetic price series with known correlation."""
        np.random.seed(42)
        n = 200
        dates = pd.date_range("2023-06-01", periods=n, freq="B")
        base = np.cumprod(1 + np.random.normal(0.0005, 0.01, n))
        sp500 = pd.Series(base * 400, index=dates, name="S&P 500")
        gold = pd.Series(base * 180 + np.random.normal(0, 2, n), index=dates, name="Gold")
        tlt = pd.Series(np.cumprod(1 + np.random.normal(-0.0003, 0.008, n)) * 90, index=dates, name="Long-Term Treasuries")
        return {"S&P 500": sp500, "Gold": gold, "Long-Term Treasuries": tlt}

    def test_rolling_corr_returns_float(self):
        from hedge_terminal.modules.correlation_scanner import _rolling_corr

        prices = self._make_multi_price_df()
        df = pd.DataFrame(prices)
        corr = _rolling_corr(df, "S&P 500", "Gold")
        assert corr is not None
        assert -1 <= corr <= 1

    def test_rolling_corr_insufficient_data(self):
        from hedge_terminal.modules.correlation_scanner import _rolling_corr

        df = pd.DataFrame(
            {"A": [1, 2, 3], "B": [3, 2, 1]},
            index=pd.date_range("2024-01-01", periods=3),
        )
        result = _rolling_corr(df, "A", "B", window=60)
        assert result is None

    @patch("hedge_terminal.modules.correlation_scanner.get_price_history")
    def test_scan_correlations_falls_back_to_static(self, mock_hist):
        from hedge_terminal.modules.correlation_scanner import scan_correlations

        mock_hist.return_value = pd.DataFrame()  # simulate network failure
        anomalies, sources = scan_correlations()

        assert len(anomalies) > 0
        assert len(sources) > 0

    def test_anomaly_to_dict_keys(self):
        from hedge_terminal.modules.correlation_scanner import CorrelationAnomaly

        a = CorrelationAnomaly(
            asset_a="S&P 500",
            asset_b="Gold",
            current_corr=0.5,
            historical_norm=0.0,
            deviation=0.5,
            signal_description="Test signal",
            normalization_trades=["Trade A", "Trade B", "Trade C"],
            historical_examples=["Example 1", "Example 2"],
            data_sources=["source"],
        )
        d = a.to_dict()
        assert "Pair" in d
        assert "Normalization Trades" in d
        assert "Historical Examples" in d
        assert len(a.normalization_trades) >= 1


# ---------------------------------------------------------------------------
# sentiment_analyzer tests
# ---------------------------------------------------------------------------

class TestSentimentAnalyzer:
    def _make_info(
        self,
        pe: float = 12.0,
        revenue_growth: float = 0.15,
        margin: float = 0.25,
        pb: float = 2.0,
    ) -> dict:
        return {
            "trailingPE": pe,
            "revenueGrowth": revenue_growth,
            "profitMargins": margin,
            "priceToBook": pb,
            "sector": "Technology",
            "longName": "Test Corp",
        }

    @patch("hedge_terminal.modules.sentiment_analyzer._calculate_ytd_return")
    @patch("hedge_terminal.modules.sentiment_analyzer.get_ticker_info")
    def test_analyze_returns_result_for_known_ticker(
        self, mock_info, mock_ytd
    ):
        from hedge_terminal.modules.sentiment_analyzer import analyze_sentiment_divergence

        mock_info.return_value = self._make_info()
        mock_ytd.return_value = -25.0

        result = analyze_sentiment_divergence("META")
        assert result is not None
        assert result.ticker == "META"
        assert result.negative_sentiment_reason != ""
        assert result.fundamental_bull_case != ""

    @patch("hedge_terminal.modules.sentiment_analyzer._calculate_ytd_return")
    @patch("hedge_terminal.modules.sentiment_analyzer.get_ticker_info")
    def test_find_sentiment_divergences_respects_limit(
        self, mock_info, mock_ytd
    ):
        from hedge_terminal.modules.sentiment_analyzer import find_sentiment_divergences

        mock_info.return_value = self._make_info()
        mock_ytd.return_value = -20.0

        results = find_sentiment_divergences(limit=3)
        assert len(results) <= 3

    @patch("hedge_terminal.modules.sentiment_analyzer._calculate_ytd_return")
    @patch("hedge_terminal.modules.sentiment_analyzer.get_ticker_info")
    def test_to_dict_has_expected_keys(self, mock_info, mock_ytd):
        from hedge_terminal.modules.sentiment_analyzer import analyze_sentiment_divergence

        mock_info.return_value = self._make_info()
        mock_ytd.return_value = -15.0

        result = analyze_sentiment_divergence("META")
        assert result is not None
        d = result.to_dict()
        assert "Ticker" in d
        assert "⚠ Negative Sentiment Reason" in d
        assert "✓ Why Fundamentals Contradict" in d
        assert "Technical Entry Level" in d

    @patch("hedge_terminal.modules.sentiment_analyzer.get_price_history")
    def test_ytd_return_calculation(self, mock_hist):
        from hedge_terminal.modules.sentiment_analyzer import _calculate_ytd_return

        mock_hist.return_value = _make_price_df([100.0, 110.0, 120.0])
        result = _calculate_ytd_return("AAPL")
        assert result is not None
        assert abs(result - 20.0) < 0.1


# ---------------------------------------------------------------------------
# macro_analyzer tests
# ---------------------------------------------------------------------------

class TestMacroAnalyzer:
    def test_classify_inflation(self):
        from hedge_terminal.modules.macro_analyzer import _classify_inflation

        assert _classify_inflation(1.0) == "low"
        assert _classify_inflation(3.0) == "moderate"
        assert _classify_inflation(6.0) == "high"
        assert _classify_inflation(None) == "moderate"

    def test_classify_growth(self):
        from hedge_terminal.modules.macro_analyzer import _classify_growth

        assert _classify_growth(-1.0) == "recession"
        assert _classify_growth(1.0) == "slow"
        assert _classify_growth(3.0) == "moderate"
        assert _classify_growth(5.0) == "strong"
        assert _classify_growth(None) == "moderate"

    def test_classify_rate_regime(self):
        from hedge_terminal.modules.macro_analyzer import _classify_rate_regime

        assert _classify_rate_regime(5.5, 4.0) == "rising"
        assert _classify_rate_regime(4.0, 5.5) == "falling"
        assert _classify_rate_regime(5.0, 5.0) == "stable"
        assert _classify_rate_regime(None, 5.0) == "stable"

    @patch("hedge_terminal.modules.macro_analyzer.get_price_history")
    @patch("hedge_terminal.modules.macro_analyzer.fetch_fred_series")
    def test_get_macro_context_returns_context(
        self, mock_fred, mock_hist
    ):
        from hedge_terminal.modules.macro_analyzer import get_macro_context, MacroContext

        cpi_series = pd.Series(
            [296 + i * 0.5 for i in range(14)],
            index=pd.date_range("2023-01-01", periods=14, freq="ME"),
            name="CPIAUCSL",
        )
        fed_series = pd.Series(
            [5.25, 5.25, 5.25, 5.25, 5.25, 5.25, 5.0],
            index=pd.date_range("2023-07-01", periods=7, freq="ME"),
            name="FEDFUNDS",
        )
        gdp_series = pd.Series([2.1], index=pd.date_range("2023-10-01", periods=1, freq="QE"))
        unemp_series = pd.Series([3.9], index=pd.date_range("2024-01-01", periods=1, freq="ME"))

        def fred_side_effect(series_id):
            mapping = {
                "CPIAUCSL": cpi_series,
                "FEDFUNDS": fed_series,
                "A191RL1Q225SBEA": gdp_series,
                "UNRATE": unemp_series,
            }
            return mapping.get(series_id, pd.Series(dtype=float))

        mock_fred.side_effect = fred_side_effect
        mock_hist.return_value = _make_price_df([100 + i for i in range(5)])

        ctx = get_macro_context()
        assert isinstance(ctx, MacroContext)
        assert ctx.regime_label != ""
        assert len(ctx.outperforming_sectors) > 0
        assert len(ctx.historical_examples) > 0

    def test_regime_playbook_has_all_required_keys(self):
        from hedge_terminal.modules.macro_analyzer import REGIME_PLAYBOOK

        for key, val in REGIME_PLAYBOOK.items():
            assert "label" in val
            assert "outperformers" in val
            assert "underperformers" in val
            assert "rationale" in val
            assert "examples" in val
            assert len(val["examples"]) >= 3


# ---------------------------------------------------------------------------
# short_squeeze tests
# ---------------------------------------------------------------------------

class TestShortSqueeze:
    def _make_info(
        self,
        short_pct: float = 0.25,
        shares_short: int = 5_000_000,
        avg_vol: int = 1_000_000,
        price: float = 15.0,
        market_cap: float = 1e9,
    ) -> dict:
        return {
            "shortPercentOfFloat": short_pct,
            "sharesShort": shares_short,
            "averageVolume": avg_vol,
            "regularMarketPrice": price,
            "marketCap": market_cap,
            "sector": "Consumer Discretionary",
            "longName": "Test Corp",
        }

    def test_squeeze_score_increases_with_short_float(self):
        from hedge_terminal.modules.short_squeeze import SqueezeCandidate

        low = SqueezeCandidate(
            ticker="A", company="A", sector="Tech",
            short_float_pct=20, days_to_cover=2,
            borrow_rate_pct=5, catalyst="test",
            entry_strategy="test", squeeze_risk_factors=[],
            current_price=10, market_cap_usd=1e9, data_sources=[],
        )
        high = SqueezeCandidate(
            ticker="B", company="B", sector="Tech",
            short_float_pct=40, days_to_cover=2,
            borrow_rate_pct=5, catalyst="test",
            entry_strategy="test", squeeze_risk_factors=[],
            current_price=10, market_cap_usd=1e9, data_sources=[],
        )
        assert high.squeeze_score > low.squeeze_score

    def test_squeeze_score_increases_with_borrow_rate(self):
        from hedge_terminal.modules.short_squeeze import SqueezeCandidate

        low = SqueezeCandidate(
            ticker="A", company="A", sector="Tech",
            short_float_pct=25, days_to_cover=3,
            borrow_rate_pct=5, catalyst="test",
            entry_strategy="test", squeeze_risk_factors=[],
            current_price=10, market_cap_usd=1e9, data_sources=[],
        )
        high = SqueezeCandidate(
            ticker="B", company="B", sector="Tech",
            short_float_pct=25, days_to_cover=3,
            borrow_rate_pct=25, catalyst="test",
            entry_strategy="test", squeeze_risk_factors=[],
            current_price=10, market_cap_usd=1e9, data_sources=[],
        )
        assert high.squeeze_score > low.squeeze_score

    @patch("hedge_terminal.modules.short_squeeze.get_ticker_info")
    def test_find_short_squeezes_uses_fallback(self, mock_info):
        from hedge_terminal.modules.short_squeeze import find_short_squeezes

        mock_info.return_value = self._make_info()
        candidates, sources = find_short_squeezes()

        assert len(candidates) > 0
        assert len(sources) > 0

    @patch("hedge_terminal.modules.short_squeeze.get_ticker_info")
    def test_find_short_squeezes_respects_limit(self, mock_info):
        from hedge_terminal.modules.short_squeeze import find_short_squeezes

        mock_info.return_value = self._make_info()
        candidates, _ = find_short_squeezes(limit=2)

        assert len(candidates) <= 2

    def test_entry_strategy_aggressive_for_high_values(self):
        from hedge_terminal.modules.short_squeeze import _entry_strategy

        strategy = _entry_strategy(35, 4)
        assert "aggressive" in strategy.lower() or "scale" in strategy.lower()

    def test_entry_strategy_conservative_for_low_values(self):
        from hedge_terminal.modules.short_squeeze import _entry_strategy

        strategy = _entry_strategy(15, 1)
        assert "conservative" in strategy.lower() or "wait" in strategy.lower()

    def test_to_dict_has_expected_keys(self):
        from hedge_terminal.modules.short_squeeze import SqueezeCandidate

        c = SqueezeCandidate(
            ticker="GME", company="GameStop", sector="Consumer Discretionary",
            short_float_pct=25.0, days_to_cover=3.0,
            borrow_rate_pct=15.0, catalyst="Earnings",
            entry_strategy="Buy on breakout",
            squeeze_risk_factors=["Risk A"],
            current_price=20.0, market_cap_usd=1e9, data_sources=["source"],
        )
        d = c.to_dict()
        assert "Ticker" in d
        assert "Short Float %" in d
        assert "Days to Cover" in d
        assert "Upcoming Catalyst" in d
        assert "⚠ Failed Squeeze Risks" in d
        assert "Squeeze Score" in d


# ---------------------------------------------------------------------------
# data_fetcher tests
# ---------------------------------------------------------------------------

class TestDataFetcher:
    def test_safe_get_nested(self):
        from hedge_terminal.utils.data_fetcher import safe_get

        d = {"a": {"b": {"c": 42}}}
        assert safe_get(d, "a", "b", "c") == 42

    def test_safe_get_missing_key(self):
        from hedge_terminal.utils.data_fetcher import safe_get

        d = {"a": 1}
        assert safe_get(d, "b", default="fallback") == "fallback"

    def test_safe_get_non_dict(self):
        from hedge_terminal.utils.data_fetcher import safe_get

        result = safe_get("not a dict", "key", default=99)
        assert result == 99

    @patch("hedge_terminal.utils.data_fetcher.requests.get")
    def test_fetch_html_table_returns_empty_on_error(self, mock_get):
        from hedge_terminal.utils.data_fetcher import fetch_html_table

        mock_get.side_effect = Exception("Network error")
        result = fetch_html_table("https://example.com")
        assert result.empty

    @patch("hedge_terminal.utils.data_fetcher.requests.get")
    def test_fetch_fred_series_returns_empty_on_error(self, mock_get):
        from hedge_terminal.utils.data_fetcher import fetch_fred_series

        mock_get.side_effect = Exception("Network error")
        result = fetch_fred_series("CPIAUCSL")
        assert isinstance(result, pd.Series)
        assert result.empty


# ---------------------------------------------------------------------------
# quote tests
# ---------------------------------------------------------------------------

class TestQuote:
    def _make_info(self) -> dict:
        return {
            "longName": "Apple Inc.",
            "shortName": "Apple",
            "exchange": "NMS",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "regularMarketPrice": 185.0,
            "regularMarketPreviousClose": 180.0,
            "regularMarketOpen": 181.0,
            "regularMarketDayHigh": 187.0,
            "regularMarketDayLow": 179.5,
            "regularMarketVolume": 55_000_000,
            "averageVolume": 60_000_000,
            "marketCap": 2_900_000_000_000,
            "trailingPE": 28.5,
            "trailingEps": 6.49,
            "dividendYield": 0.005,
            "fiftyTwoWeekHigh": 199.0,
            "fiftyTwoWeekLow": 140.0,
            "beta": 1.25,
            "currency": "USD",
        }

    @patch("hedge_terminal.modules.quote.get_ticker_info")
    def test_get_quote_returns_stock_quote(self, mock_info):
        from hedge_terminal.modules.quote import get_quote, StockQuote

        mock_info.return_value = self._make_info()
        q = get_quote("AAPL")

        assert isinstance(q, StockQuote)
        assert q.ticker == "AAPL"
        assert q.company_name == "Apple Inc."
        assert q.price == 185.0
        assert q.sector == "Technology"

    @patch("hedge_terminal.modules.quote.get_ticker_info")
    def test_get_quote_computes_change_pct(self, mock_info):
        from hedge_terminal.modules.quote import get_quote

        mock_info.return_value = self._make_info()
        q = get_quote("AAPL")

        # (185 - 180) / 180 * 100 ≈ 2.78 %
        assert q.change_pct is not None
        assert abs(q.change_pct - (5 / 180 * 100)) < 0.01

    @patch("hedge_terminal.modules.quote.get_ticker_info")
    def test_get_quote_scales_dividend_yield(self, mock_info):
        from hedge_terminal.modules.quote import get_quote

        mock_info.return_value = self._make_info()  # dividendYield = 0.005
        q = get_quote("AAPL")

        assert q.dividend_yield_pct is not None
        assert abs(q.dividend_yield_pct - 0.5) < 0.001  # 0.5 %

    @patch("hedge_terminal.modules.quote.get_ticker_info")
    def test_to_dict_has_expected_keys(self, mock_info):
        from hedge_terminal.modules.quote import get_quote

        mock_info.return_value = self._make_info()
        d = get_quote("AAPL").to_dict()

        for key in ("Ticker", "Company", "Price", "Day Change", "Market Cap",
                    "P/E (TTM)", "Beta", "52-Week High", "52-Week Low"):
            assert key in d, f"Missing key: {key}"

    @patch("hedge_terminal.modules.quote.get_ticker_info")
    def test_get_quotes_skips_errors(self, mock_info):
        from hedge_terminal.modules.quote import get_quotes

        mock_info.side_effect = [self._make_info(), Exception("boom")]
        quotes = get_quotes(["AAPL", "BAD"])

        assert len(quotes) == 1
        assert quotes[0].ticker == "AAPL"

    @patch("hedge_terminal.modules.quote.get_ticker_info")
    def test_market_cap_formatted_in_trillions(self, mock_info):
        from hedge_terminal.modules.quote import get_quote

        info = self._make_info()
        info["marketCap"] = 3_000_000_000_000  # 3T
        mock_info.return_value = info
        d = get_quote("AAPL").to_dict()

        assert "T" in d["Market Cap"]


# ---------------------------------------------------------------------------
# news tests
# ---------------------------------------------------------------------------

class TestNews:
    @patch("hedge_terminal.modules.news.requests.get")
    def test_fetch_yahoo_rss_returns_items_on_success(self, mock_get):
        from hedge_terminal.modules.news import _fetch_yahoo_rss

        xml = """<?xml version="1.0"?>
<rss><channel>
  <title><![CDATA[Feed]]></title>
  <title><![CDATA[AAPL soars on earnings]]></title>
  <link>https://example.com/1</link>
  <pubDate>N/A</pubDate>
  <pubDate>2024-01-15</pubDate>
  <description><![CDATA[Feed desc]]></description>
  <description><![CDATA[Apple beats estimates by wide margin.]]></description>
</channel></rss>"""
        mock_response = MagicMock()
        mock_response.text = xml
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        items = _fetch_yahoo_rss("AAPL", limit=5)
        assert len(items) >= 1
        assert items[0].title == "AAPL soars on earnings"

    @patch("hedge_terminal.modules.news.requests.get")
    def test_fetch_yahoo_rss_returns_empty_on_error(self, mock_get):
        from hedge_terminal.modules.news import _fetch_yahoo_rss

        mock_get.side_effect = Exception("Network error")
        items = _fetch_yahoo_rss("AAPL", limit=5)
        assert items == []

    @patch("hedge_terminal.modules.news._fetch_sec_filings")
    @patch("hedge_terminal.modules.news._fetch_yahoo_rss")
    @patch("hedge_terminal.modules.news._fetch_yfinance_news")
    def test_get_ticker_news_deduplicates(self, mock_yf, mock_rss, mock_sec):
        from hedge_terminal.modules.news import get_ticker_news, NewsItem

        item = NewsItem(
            title="Duplicate headline",
            publisher="Test",
            published_at="2024-01-01",
            url="https://example.com",
            summary="Summary",
            ticker="AAPL",
            source_feed="yfinance",
        )
        mock_yf.return_value = [item]
        mock_rss.return_value = [item]  # same title → should be deduped
        mock_sec.return_value = []

        items = get_ticker_news("AAPL", limit=10)
        assert len(items) == 1

    @patch("hedge_terminal.modules.news._fetch_sec_filings")
    @patch("hedge_terminal.modules.news._fetch_yahoo_rss")
    @patch("hedge_terminal.modules.news._fetch_yfinance_news")
    def test_get_ticker_news_respects_limit(self, mock_yf, mock_rss, mock_sec):
        from hedge_terminal.modules.news import get_ticker_news, NewsItem

        def _make_item(n: int) -> NewsItem:
            return NewsItem(
                title=f"Headline {n}",
                publisher="Test",
                published_at="2024-01-01",
                url="https://example.com",
                summary="",
                ticker="AAPL",
                source_feed="yfinance",
            )

        mock_yf.return_value = [_make_item(i) for i in range(8)]
        mock_rss.return_value = []
        mock_sec.return_value = []

        items = get_ticker_news("AAPL", limit=5)
        assert len(items) <= 5

    def test_news_item_to_dict_truncates_long_summary(self):
        from hedge_terminal.modules.news import NewsItem

        item = NewsItem(
            title="Title",
            publisher="Pub",
            published_at="2024-01-01",
            url="https://example.com",
            summary="A" * 300,  # > 200 chars
            ticker="AAPL",
            source_feed="yfinance",
        )
        d = item.to_dict()
        assert len(d["Summary"]) <= 201 + 1  # 200 chars + "…"


# ---------------------------------------------------------------------------
# screener tests
# ---------------------------------------------------------------------------

class TestScreener:
    def _make_info(self, **kwargs) -> dict:
        defaults = {
            "longName": "Test Corp",
            "sector": "Technology",
            "industry": "Software",
            "marketCap": 50_000_000_000,
            "trailingPE": 12.0,
            "priceToBook": 1.5,
            "enterpriseToEbitda": 8.0,
            "revenueGrowth": 0.20,
            "earningsGrowth": 0.22,
            "profitMargins": 0.18,
            "returnOnEquity": 0.20,
            "dividendYield": 0.04,
            "payoutRatio": 0.40,
            "debtToEquity": 50.0,
            "beta": 0.75,
        }
        defaults.update(kwargs)
        return defaults

    @patch("hedge_terminal.modules.screener.get_ticker_info")
    def test_screen_equities_returns_results(self, mock_info):
        from hedge_terminal.modules.screener import screen_equities, ScreenCriteria

        mock_info.return_value = self._make_info()
        criteria = ScreenCriteria(max_pe=20.0, min_profit_margin=0.05)

        results = screen_equities(criteria, universe=["AAPL", "MSFT"], limit=5)
        assert len(results) <= 5

    @patch("hedge_terminal.modules.screener.get_ticker_info")
    def test_screen_rejects_violated_constraint(self, mock_info):
        from hedge_terminal.modules.screener import screen_equities, ScreenCriteria

        # PE = 30 violates max_pe=15
        mock_info.return_value = self._make_info(trailingPE=30.0)
        criteria = ScreenCriteria(max_pe=15.0)

        results = screen_equities(criteria, universe=["AAPL"], limit=5)
        assert results == []

    @patch("hedge_terminal.modules.screener.get_ticker_info")
    def test_passed_criteria_populated(self, mock_info):
        from hedge_terminal.modules.screener import screen_equities, ScreenCriteria

        mock_info.return_value = self._make_info()
        criteria = ScreenCriteria(max_pe=20.0, min_profit_margin=0.05, min_roe=0.10)

        results = screen_equities(criteria, universe=["AAPL"], limit=5)
        if results:
            assert len(results[0].passed_criteria) > 0

    @patch("hedge_terminal.modules.screener.get_ticker_info")
    def test_screen_respects_limit(self, mock_info):
        from hedge_terminal.modules.screener import screen_equities, ScreenCriteria

        mock_info.return_value = self._make_info()
        criteria = ScreenCriteria()  # no constraints → all pass

        results = screen_equities(
            criteria,
            universe=["AAPL", "MSFT", "GOOGL", "META", "AMZN"],
            limit=3,
        )
        assert len(results) <= 3

    def test_presets_defined(self):
        from hedge_terminal.modules.screener import PRESETS

        for name in ("value", "growth", "dividend", "quality", "low_volatility"):
            assert name in PRESETS, f"Missing preset: {name}"

    @patch("hedge_terminal.modules.screener.get_ticker_info")
    def test_to_dict_has_required_columns(self, mock_info):
        from hedge_terminal.modules.screener import _fetch_result

        mock_info.return_value = self._make_info()
        r = _fetch_result("AAPL")
        d = r.to_dict()

        for col in ("Ticker", "Company", "Sector", "Market Cap", "P/E",
                    "Net Margin", "ROE", "Beta"):
            assert col in d, f"Missing column: {col}"


# ---------------------------------------------------------------------------
# chart tests
# ---------------------------------------------------------------------------

class TestChart:
    @patch("hedge_terminal.modules.chart.get_price_history")
    def test_get_chart_returns_chart_data(self, mock_hist):
        from hedge_terminal.modules.chart import get_chart, ChartData

        mock_hist.return_value = _make_price_df([100, 105, 110, 108, 115])
        cd = get_chart("AAPL", period="1mo")

        assert isinstance(cd, ChartData)
        assert cd.ticker == "AAPL"
        assert not cd.prices.empty

    @patch("hedge_terminal.modules.chart.get_price_history")
    def test_chart_computes_change_pct(self, mock_hist):
        from hedge_terminal.modules.chart import get_chart

        mock_hist.return_value = _make_price_df([100.0, 105.0, 110.0])
        cd = get_chart("SPY")

        assert cd.change_pct is not None
        assert abs(cd.change_pct - 10.0) < 0.01  # (110-100)/100*100 = 10%

    @patch("hedge_terminal.modules.chart.get_price_history")
    def test_render_returns_non_empty_string(self, mock_hist):
        from hedge_terminal.modules.chart import get_chart

        mock_hist.return_value = _make_price_df(
            [float(i) + 100 for i in range(30)]
        )
        cd = get_chart("AAPL")
        rendered = cd.render(width=40, height=10)

        assert isinstance(rendered, str)
        assert len(rendered) > 50
        assert "AAPL" in rendered

    @patch("hedge_terminal.modules.chart.get_price_history")
    def test_render_empty_data_returns_no_data(self, mock_hist):
        import pandas as pd
        from hedge_terminal.modules.chart import get_chart

        mock_hist.return_value = pd.DataFrame()
        cd = get_chart("AAPL")

        assert cd.render() == "(no data)"

    @patch("hedge_terminal.modules.chart.get_price_history")
    def test_chart_high_low_correct(self, mock_hist):
        from hedge_terminal.modules.chart import get_chart

        prices = [90.0, 95.0, 110.0, 85.0, 100.0]
        mock_hist.return_value = _make_price_df(prices)
        cd = get_chart("AAPL")

        assert abs(cd.high - 110.0) < 0.01
        assert abs(cd.low - 85.0) < 0.01

    @patch("hedge_terminal.modules.chart.get_price_history")
    def test_summary_dict_keys(self, mock_hist):
        from hedge_terminal.modules.chart import get_chart

        mock_hist.return_value = _make_price_df([100.0, 110.0])
        cd = get_chart("SPY")
        s = cd.summary()

        for key in ("Ticker", "Period", "Current Price", "Period High",
                    "Period Low", "Period Change"):
            assert key in s, f"Missing key: {key}"

    @patch("hedge_terminal.modules.chart.get_price_history")
    def test_compare_charts_returns_dict_per_ticker(self, mock_hist):
        from hedge_terminal.modules.chart import compare_charts

        mock_hist.return_value = _make_price_df([100.0, 105.0, 110.0])
        result = compare_charts(["SPY", "QQQ"], period="1mo")

        assert "SPY" in result
        assert "QQQ" in result
