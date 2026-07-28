"""Tests for src/quant_engine.py — technical indicators, correlation, regime, yield curve."""

import math

import pytest

from quant_engine import (
    TechnicalAnalysis,
    CorrelationAnalyzer,
    MarketRegimeDetector,
    YieldCurveAnalyzer,
    _mean,
    _std,
)


# ── helpers ──────────────────────────────────────────────────────

class TestHelpers:
    def test_mean(self):
        assert _mean([1, 2, 3, 4]) == 2.5

    def test_mean_empty_is_zero(self):
        assert _mean([]) == 0.0

    def test_std_sample(self):
        # Sample std (ddof=1) of [2,4,4,4,5,5,7,9] is 2.138...
        assert _std([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(2.1381, abs=1e-3)

    def test_std_single_value_is_zero(self):
        assert _std([5]) == 0.0


# ── SMA / EMA ────────────────────────────────────────────────────

class TestMovingAverages:
    def test_sma_basic(self):
        # 3-period SMA of [1,2,3,4,5] -> means of [1,2,3],[2,3,4],[3,4,5]
        assert TechnicalAnalysis.sma([1, 2, 3, 4, 5], 3) == [2.0, 3.0, 4.0]

    def test_sma_too_short_returns_empty(self):
        assert TechnicalAnalysis.sma([1, 2], 5) == []

    def test_sma_flat_series_is_flat(self):
        assert TechnicalAnalysis.sma([7, 7, 7, 7], 2) == [7.0, 7.0, 7.0]

    def test_ema_first_value_is_seed_sma(self):
        ema = TechnicalAnalysis.ema([1, 2, 3, 4, 5], 3)
        # First EMA value is the SMA seed of the first `period` prices.
        assert ema[0] == pytest.approx(2.0)

    def test_ema_reacts_to_trend(self):
        ema = TechnicalAnalysis.ema(list(range(1, 21)), 5)
        # On a rising series each EMA point should be >= the previous one.
        assert all(b >= a for a, b in zip(ema, ema[1:]))

    def test_ema_too_short_returns_empty(self):
        assert TechnicalAnalysis.ema([1, 2], 10) == []


# ── RSI ──────────────────────────────────────────────────────────

class TestRSI:
    def test_all_gains_gives_rsi_100(self):
        # Monotonic increase => no losses => avg_loss 0 => RSI pinned at 100.
        assert TechnicalAnalysis.rsi(list(range(1, 30)), period=14) == 100.0

    def test_all_losses_gives_low_rsi(self):
        rsi = TechnicalAnalysis.rsi(list(range(30, 1, -1)), period=14)
        assert rsi == pytest.approx(0.0, abs=1e-6)

    def test_rsi_in_bounds(self):
        prices = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
                  45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.0, 46.03]
        rsi = TechnicalAnalysis.rsi(prices, period=14)
        assert rsi is not None
        assert 0.0 <= rsi <= 100.0

    def test_rsi_insufficient_data_returns_none(self):
        assert TechnicalAnalysis.rsi([1, 2, 3], period=14) is None


# ── MACD ─────────────────────────────────────────────────────────

class TestMACD:
    def test_macd_insufficient_data_returns_none(self):
        assert TechnicalAnalysis.macd(list(range(10))) is None

    def test_macd_line_positive_on_uptrend(self):
        result = TechnicalAnalysis.macd(list(range(1, 80)))
        assert result is not None
        assert set(result) == {"macd", "signal", "histogram", "trend"}
        # Fast EMA leads slow EMA on a rising series => MACD line is positive.
        assert result["macd"] > 0

    def test_macd_line_negative_on_downtrend(self):
        result = TechnicalAnalysis.macd(list(range(80, 1, -1)))
        assert result is not None
        # Fast EMA trails slow EMA on a falling series => MACD line is negative.
        assert result["macd"] < 0

    def test_macd_histogram_equals_macd_minus_signal(self):
        # Use a series with a momentum shift so the histogram is non-trivial.
        prices = list(range(1, 50)) + [49 - i for i in range(1, 30)]
        result = TechnicalAnalysis.macd(prices)
        assert result is not None
        # Histogram is, by definition, the gap between MACD and its signal line;
        # its sign is exactly what drives the bullish/bearish label.
        expected_trend = "bullish" if result["histogram"] > 0 else "bearish"
        assert result["trend"] == expected_trend


# ── Bollinger Bands ──────────────────────────────────────────────

class TestBollinger:
    def test_bands_ordered_upper_middle_lower(self):
        prices = [10, 11, 9, 12, 8, 13, 7, 14, 10, 11,
                  9, 12, 8, 13, 7, 14, 10, 11, 9, 12]
        bb = TechnicalAnalysis.bollinger_bands(prices, period=20)
        assert bb["lower"] <= bb["middle"] <= bb["upper"]

    def test_percent_b_at_upper_band_flags_overbought(self):
        # Flat history then a spike pushes the last price above the upper band.
        prices = [10.0] * 19 + [20.0]
        bb = TechnicalAnalysis.bollinger_bands(prices, period=20)
        assert bb["percent_b"] > 1
        assert bb["signal"] == "overbought"

    def test_insufficient_data_returns_none(self):
        assert TechnicalAnalysis.bollinger_bands([1, 2, 3], period=20) is None


# ── ATR ──────────────────────────────────────────────────────────

class TestATR:
    def test_atr_constant_range(self):
        # Every bar has the same 2-point high/low spread and no gaps,
        # so the true range — and therefore the ATR — is exactly 2.
        n = 20
        high = [12.0] * n
        low = [10.0] * n
        close = [11.0] * n
        assert TechnicalAnalysis.atr(high, low, close, period=14) == pytest.approx(2.0)

    def test_atr_insufficient_data_returns_none(self):
        assert TechnicalAnalysis.atr([1], [1], [1], period=14) is None


# ── Correlation ──────────────────────────────────────────────────

class TestCorrelation:
    def test_perfect_positive_correlation(self):
        ca = CorrelationAnalyzer()
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]
        assert ca.pearson(x, y) == pytest.approx(1.0)

    def test_perfect_negative_correlation(self):
        ca = CorrelationAnalyzer()
        x = [1, 2, 3, 4, 5]
        y = [10, 8, 6, 4, 2]
        assert ca.pearson(x, y) == pytest.approx(-1.0)

    def test_constant_series_returns_zero(self):
        ca = CorrelationAnalyzer()
        assert ca.pearson([5, 5, 5, 5], [1, 2, 3, 4]) == 0.0

    def test_too_few_points_returns_zero(self):
        ca = CorrelationAnalyzer()
        assert ca.pearson([1, 2], [1, 2]) == 0.0

    def test_matrix_is_symmetric_with_unit_diagonal(self):
        ca = CorrelationAnalyzer()
        series = {
            "A": [100, 101, 102, 103, 104, 105],
            "B": [105, 104, 103, 102, 101, 100],
        }
        m = ca.compute_matrix(series)
        assert m["A"]["A"] == pytest.approx(1.0)
        assert m["B"]["B"] == pytest.approx(1.0)
        assert m["A"]["B"] == m["B"]["A"]

    def test_find_divergences_detects_negative_pair(self):
        ca = CorrelationAnalyzer()
        matrix = {
            "A": {"A": 1.0, "B": -0.8},
            "B": {"A": -0.8, "B": 1.0},
        }
        div = ca.find_divergences(matrix, threshold=-0.5)
        assert len(div) == 1
        assert sorted(div[0]["pair"]) == ["A", "B"]
        assert div[0]["correlation"] == -0.8

    def test_find_divergences_deduplicates_pairs(self):
        ca = CorrelationAnalyzer()
        matrix = {
            "A": {"A": 1.0, "B": -0.9},
            "B": {"A": -0.9, "B": 1.0},
        }
        # A-B and B-A must collapse to a single divergence entry.
        assert len(ca.find_divergences(matrix, threshold=-0.5)) == 1


# ── Market Regime ────────────────────────────────────────────────

class TestRegime:
    def test_unknown_when_too_short(self):
        out = MarketRegimeDetector.detect([1, 2, 3], window=20)
        assert out["regime"] == "unknown"
        assert out["confidence"] == 0

    def test_strong_uptrend_is_bull(self):
        prices = [100 * (1.01 ** i) for i in range(60)]
        out = MarketRegimeDetector.detect(prices, window=20)
        assert out["regime"] == "bull"
        assert out["confidence"] > 0

    def test_strong_downtrend_is_bear(self):
        prices = [100 * (0.99 ** i) for i in range(60)]
        out = MarketRegimeDetector.detect(prices, window=20)
        assert out["regime"] == "bear"

    def test_flat_low_vol_is_sideways(self):
        prices = [100.0] * 60
        out = MarketRegimeDetector.detect(prices, window=20)
        assert out["regime"] == "sideways"


# ── Yield Curve ──────────────────────────────────────────────────

class TestYieldCurve:
    def test_spread_long_minus_short(self):
        curve = {"2Y": 4.0, "10Y": 4.5}
        assert YieldCurveAnalyzer.spread(curve) == 0.5

    def test_spread_missing_tenor_returns_none(self):
        assert YieldCurveAnalyzer.spread({"2Y": 4.0}) is None

    def test_inverted_curve_detected(self):
        assert YieldCurveAnalyzer.is_inverted({"2Y": 5.0, "10Y": 4.0}) is True

    def test_normal_curve_not_inverted(self):
        assert YieldCurveAnalyzer.is_inverted({"2Y": 4.0, "10Y": 4.5}) is False

    def test_is_inverted_missing_tenors_is_false(self):
        assert YieldCurveAnalyzer.is_inverted({"5Y": 4.0}) is False

    def test_steepness_3m_to_10y(self):
        assert YieldCurveAnalyzer.steepness({"3M": 4.0, "10Y": 4.8}) == pytest.approx(0.8)

    def test_term_premium_positive_back_end(self):
        tp = YieldCurveAnalyzer.term_premium({"2Y": 4.0, "5Y": 4.3, "10Y": 4.6})
        assert tp["front_end"] == pytest.approx(0.3)
        assert tp["back_end"] == pytest.approx(0.3)
        assert tp["assessment"] == "positive"

    def test_term_premium_negative_back_end(self):
        tp = YieldCurveAnalyzer.term_premium({"2Y": 4.0, "5Y": 4.5, "10Y": 4.2})
        assert tp["assessment"] == "negative"

    def test_term_premium_missing_tenor_returns_none(self):
        assert YieldCurveAnalyzer.term_premium({"2Y": 4.0, "10Y": 4.6}) is None
