"""Tests for src/risk_engine.py — VaR, drawdown, performance ratios, stress tests."""

import pytest

from risk_engine import (
    ValueAtRisk,
    DrawdownAnalyzer,
    PerformanceMetrics,
    StressTest,
    RiskEngine,
    _percentile,
)


# ── percentile helper ────────────────────────────────────────────

class TestPercentile:
    def test_median(self):
        assert _percentile([1, 2, 3, 4, 5], 0.5) == 3

    def test_min_and_max(self):
        assert _percentile([10, 20, 30], 0.0) == 10
        assert _percentile([10, 20, 30], 1.0) == 30

    def test_linear_interpolation(self):
        # Between index 0 (=0) and index 1 (=10) at p=0.25 of a 5-elem list.
        assert _percentile([0, 10, 20, 30, 40], 0.25) == 10

    def test_empty_returns_zero(self):
        assert _percentile([], 0.5) == 0.0


# ── Value at Risk ────────────────────────────────────────────────

class TestValueAtRisk:
    returns = [-0.02, 0.01, -0.015, 0.03, -0.04, 0.02, -0.01, 0.005, -0.025, 0.015, -0.03, 0.01]

    def test_parametric_var_is_positive_loss(self):
        var = ValueAtRisk.parametric_var(self.returns, confidence=0.95)
        assert var is not None
        # VaR is reported as a positive loss magnitude (percent).
        assert var > 0

    def test_parametric_higher_confidence_means_larger_var(self):
        v95 = ValueAtRisk.parametric_var(self.returns, confidence=0.95)
        v99 = ValueAtRisk.parametric_var(self.returns, confidence=0.99)
        assert v99 > v95

    def test_historical_var_matches_distribution_tail(self):
        var = ValueAtRisk.historical_var(self.returns, confidence=0.95)
        assert var is not None
        assert var > 0

    def test_conditional_var_at_least_historical(self):
        # Expected shortfall (CVaR) is the mean of the worst losses, so it is
        # never milder than the VaR threshold itself.
        hist = ValueAtRisk.historical_var(self.returns, confidence=0.95)
        cvar = ValueAtRisk.conditional_var(self.returns, confidence=0.95)
        assert cvar is not None
        assert cvar >= hist

    def test_insufficient_data_returns_none(self):
        assert ValueAtRisk.parametric_var([0.01, 0.02], confidence=0.95) is None
        assert ValueAtRisk.historical_var([0.01], confidence=0.95) is None
        assert ValueAtRisk.conditional_var([0.01], confidence=0.95) is None


# ── Drawdown ─────────────────────────────────────────────────────

class TestDrawdown:
    def test_max_drawdown_simple(self):
        # Peak 100 -> trough 50 => 50% drawdown.
        out = DrawdownAnalyzer.max_drawdown([100, 80, 50, 70, 90])
        assert out["max_drawdown_pct"] == pytest.approx(50.0)
        assert out["peak_index"] == 0
        assert out["trough_index"] == 2
        assert out["severity"] == "severe"

    def test_max_drawdown_mild_severity(self):
        out = DrawdownAnalyzer.max_drawdown([100, 95, 98, 100, 105])
        assert out["severity"] == "mild"

    def test_max_drawdown_after_new_peak(self):
        # New peak at 200, then drop to 150 => 25% from the later peak.
        out = DrawdownAnalyzer.max_drawdown([100, 90, 200, 150])
        assert out["max_drawdown_pct"] == pytest.approx(25.0)
        assert out["peak_index"] == 2
        assert out["trough_index"] == 3

    def test_max_drawdown_too_short_returns_none(self):
        assert DrawdownAnalyzer.max_drawdown([100]) is None

    def test_current_drawdown_from_peak(self):
        assert DrawdownAnalyzer.current_drawdown([100, 120, 90]) == pytest.approx(25.0)

    def test_current_drawdown_at_peak_is_zero(self):
        assert DrawdownAnalyzer.current_drawdown([90, 100, 120]) == 0.0

    def test_current_drawdown_empty_returns_none(self):
        assert DrawdownAnalyzer.current_drawdown([]) is None

    def test_drawdown_series_length_and_nonnegative(self):
        prices = [100, 110, 90, 95, 130]
        series = DrawdownAnalyzer.drawdown_series(prices)
        assert len(series) == len(prices)
        assert all(d >= 0 for d in series)
        # At every new running high the drawdown resets to zero.
        assert series[0] == 0
        assert series[-1] == 0


# ── Performance Metrics ──────────────────────────────────────────

class TestPerformanceMetrics:
    def test_sharpe_none_when_zero_variance(self):
        # Use a value that is exactly representable in binary floating point so
        # the sample std is truly 0 on every platform => undefined Sharpe => None.
        returns = [0.5] * 30
        sharpe = PerformanceMetrics.sharpe_ratio(returns)
        assert sharpe is None

    def test_sharpe_defined_with_variance(self):
        returns = [0.01, 0.02, -0.005, 0.015, 0.0, 0.03, -0.01, 0.02, 0.01, -0.002, 0.018, 0.005]
        sharpe = PerformanceMetrics.sharpe_ratio(returns)
        assert sharpe is not None
        assert isinstance(sharpe, float)

    def test_sortino_none_when_no_downside(self):
        # No negative excess returns => downside deviation 0 => None.
        returns = [0.05] * 15
        assert PerformanceMetrics.sortino_ratio(returns) is None

    def test_sortino_defined_with_downside(self):
        returns = [0.02, -0.03, 0.01, -0.04, 0.05, -0.02, 0.03, -0.01, 0.02, -0.05, 0.01, 0.0]
        assert PerformanceMetrics.sortino_ratio(returns) is not None

    def test_calmar_ratio(self):
        returns = [0.001] * 20
        calmar = PerformanceMetrics.calmar_ratio(returns, max_dd=0.10)
        # annual_return = mean(0.001)*252 = 0.252; /0.10 = 2.52.
        assert calmar == pytest.approx(2.52, abs=1e-2)

    def test_calmar_zero_drawdown_returns_none(self):
        assert PerformanceMetrics.calmar_ratio([0.01, 0.02], max_dd=0) is None

    def test_information_ratio_zero_when_tracking_benchmark(self):
        returns = [0.01, 0.02, -0.01, 0.03, 0.0, 0.02, -0.02, 0.01, 0.01, 0.0, 0.015, -0.005]
        # Identical to benchmark => zero active return std => None.
        assert PerformanceMetrics.information_ratio(returns, list(returns)) is None

    def test_information_ratio_defined_vs_different_benchmark(self):
        returns = [0.01, 0.02, -0.01, 0.03, 0.0, 0.02, -0.02, 0.01, 0.01, 0.0, 0.015, -0.005]
        bench = [0.0, 0.01, -0.02, 0.01, 0.01, 0.0, -0.01, 0.02, 0.0, 0.01, 0.005, 0.0]
        assert PerformanceMetrics.information_ratio(returns, bench) is not None


# ── Stress Testing ───────────────────────────────────────────────

class TestStressTest:
    portfolio = {"equities": 60000, "bonds": 30000, "crypto": 10000}

    def test_scenario_analysis_returns_all_scenarios(self):
        results = StressTest.scenario_analysis(self.portfolio)
        names = {r["scenario"] for r in results}
        assert names == set(StressTest.SCENARIOS.keys())

    def test_results_sorted_worst_first(self):
        results = StressTest.scenario_analysis(self.portfolio)
        pnls = [r["total_pnl"] for r in results]
        assert pnls == sorted(pnls)

    def test_gfc_pnl_matches_manual_calc(self):
        results = StressTest.scenario_analysis(self.portfolio)
        gfc = next(r for r in results if r["scenario"] == "GFC_2008")
        # 60000*-0.45 + 30000*0.15 + 10000*-0.70 = -27000 + 4500 - 7000 = -29500
        assert gfc["total_pnl"] == pytest.approx(-29500.0)

    def test_pnl_pct_relative_to_total(self):
        results = StressTest.scenario_analysis(self.portfolio)
        gfc = next(r for r in results if r["scenario"] == "GFC_2008")
        # -29500 / 100000 * 100 = -29.5%
        assert gfc["pnl_pct"] == pytest.approx(-29.5)

    def test_details_include_per_asset_pnl(self):
        results = StressTest.scenario_analysis(self.portfolio)
        gfc = next(r for r in results if r["scenario"] == "GFC_2008")
        assert gfc["details"]["equities"]["pnl"] == pytest.approx(-27000.0)
        assert gfc["details"]["equities"]["shock"] == "-45.0%"


# ── RiskEngine facade ────────────────────────────────────────────

class TestRiskEngine:
    def test_generate_risk_summary_structure(self):
        engine = RiskEngine()
        data = {
            "crypto": {
                "top_coins": [
                    {"symbol": "BTC", "change_percent_24h": -5.0},
                    {"symbol": "ETH", "change_percent_24h": 3.0},
                    {"symbol": "SOL", "change_percent_24h": -8.0},
                ]
            }
        }
        summary = engine.generate_risk_summary(data)
        assert "stress_tests" in summary
        assert summary["stress_tests"], "stress tests should always be populated"
        assert summary["overall_risk_level"] in ("low", "moderate", "high")

    def test_overall_risk_level_high_on_severe_worst_case(self):
        engine = RiskEngine()
        # Default portfolio fed through GFC scenario yields < -30% pnl => high.
        summary = engine.generate_risk_summary({})
        worst = summary["stress_tests"][0]
        if worst["pnl_pct"] < -30:
            assert summary["overall_risk_level"] == "high"
