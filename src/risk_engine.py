"""
Risk Analytics Engine for Economic Intelligence Agent
VaR, drawdown, performance metrics, stress testing
"""

import math
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0

def _std(vals: List[float], ddof: int = 1) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - ddof))

def _percentile(vals: List[float], pct: float) -> float:
    """Simple percentile (linear interpolation)"""
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * pct
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


# ── Value at Risk ────────────────────────────────────────────────

class ValueAtRisk:
    """Value at Risk calculations"""

    @staticmethod
    def parametric_var(returns: List[float], confidence: float = 0.95, horizon: int = 1) -> Optional[float]:
        """Parametric (Gaussian) VaR"""
        if len(returns) < 10:
            return None
        mu = _mean(returns)
        sigma = _std(returns)
        # z-score for confidence level
        z_scores = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
        z = z_scores.get(confidence, 1.645)
        var = -(mu - z * sigma) * math.sqrt(horizon)
        return round(var * 100, 3)  # as percentage

    @staticmethod
    def historical_var(returns: List[float], confidence: float = 0.95) -> Optional[float]:
        """Historical VaR — direct percentile of return distribution"""
        if len(returns) < 10:
            return None
        var = -_percentile(returns, 1 - confidence)
        return round(var * 100, 3)

    @staticmethod
    def conditional_var(returns: List[float], confidence: float = 0.95) -> Optional[float]:
        """Conditional VaR (Expected Shortfall) — average of losses beyond VaR"""
        if len(returns) < 10:
            return None
        threshold = _percentile(returns, 1 - confidence)
        tail = [r for r in returns if r <= threshold]
        if not tail:
            return None
        return round(-_mean(tail) * 100, 3)


# ── Drawdown Analyzer ────────────────────────────────────────────

class DrawdownAnalyzer:
    """Drawdown calculations from price series"""

    @staticmethod
    def max_drawdown(prices: List[float]) -> Optional[Dict]:
        """Maximum drawdown from peak"""
        if len(prices) < 2:
            return None

        peak = prices[0]
        max_dd = 0
        peak_idx = 0
        trough_idx = 0
        current_peak_idx = 0

        for i, price in enumerate(prices):
            if price > peak:
                peak = price
                current_peak_idx = i
            dd = (peak - price) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                peak_idx = current_peak_idx
                trough_idx = i

        return {
            "max_drawdown_pct": round(max_dd * 100, 2),
            "peak_index": peak_idx,
            "trough_index": trough_idx,
            "severity": "severe" if max_dd > 0.20 else ("moderate" if max_dd > 0.10 else "mild"),
        }

    @staticmethod
    def current_drawdown(prices: List[float]) -> Optional[float]:
        """Current drawdown from all-time high"""
        if not prices:
            return None
        peak = max(prices)
        if peak == 0:
            return 0.0
        return round((peak - prices[-1]) / peak * 100, 2)

    @staticmethod
    def drawdown_series(prices: List[float]) -> List[float]:
        """Full drawdown series from running peak"""
        if not prices:
            return []
        peak = prices[0]
        dd_series = []
        for p in prices:
            peak = max(peak, p)
            dd_series.append((peak - p) / peak * 100 if peak > 0 else 0)
        return dd_series


# ── Performance Metrics ──────────────────────────────────────────

class PerformanceMetrics:
    """Risk-adjusted performance ratios"""

    @staticmethod
    def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.05, periods_per_year: int = 252) -> Optional[float]:
        """Annualized Sharpe ratio"""
        if len(returns) < 10:
            return None
        rf_per_period = risk_free_rate / periods_per_year
        excess = [r - rf_per_period for r in returns]
        mu = _mean(excess)
        sigma = _std(excess)
        if sigma == 0:
            return None
        return round(mu / sigma * math.sqrt(periods_per_year), 3)

    @staticmethod
    def sortino_ratio(returns: List[float], risk_free_rate: float = 0.05, periods_per_year: int = 252) -> Optional[float]:
        """Sortino ratio — penalizes downside deviation only"""
        if len(returns) < 10:
            return None
        rf_per_period = risk_free_rate / periods_per_year
        excess = [r - rf_per_period for r in returns]
        mu = _mean(excess)
        downside = [min(r, 0) for r in excess]
        downside_std = _std(downside) if any(d < 0 for d in downside) else 0
        if downside_std == 0:
            return None
        return round(mu / downside_std * math.sqrt(periods_per_year), 3)

    @staticmethod
    def calmar_ratio(returns: List[float], max_dd: float) -> Optional[float]:
        """Calmar ratio: annualized return / max drawdown"""
        if not returns or max_dd == 0:
            return None
        annual_return = _mean(returns) * 252
        return round(annual_return / max_dd, 3)

    @staticmethod
    def information_ratio(returns: List[float], benchmark: List[float], periods_per_year: int = 252) -> Optional[float]:
        """Information ratio vs benchmark"""
        n = min(len(returns), len(benchmark))
        if n < 10:
            return None
        active = [returns[i] - benchmark[i] for i in range(n)]
        mu = _mean(active)
        sigma = _std(active)
        if sigma == 0:
            return None
        return round(mu / sigma * math.sqrt(periods_per_year), 3)


# ── Stress Testing ───────────────────────────────────────────────

class StressTest:
    """Scenario-based stress testing"""

    # Predefined scenario shocks (pct moves)
    SCENARIOS = {
        "GFC_2008": {
            "description": "2008 Global Financial Crisis",
            "equities": -0.45,
            "bonds": 0.15,
            "crypto": -0.70,
            "commodities": -0.35,
            "forex_usd": 0.10,
        },
        "COVID_2020": {
            "description": "COVID-19 March 2020 crash",
            "equities": -0.34,
            "bonds": 0.08,
            "crypto": -0.50,
            "commodities": -0.25,
            "forex_usd": 0.08,
        },
        "RATE_SHOCK_200BP": {
            "description": "Sudden +200bp rate increase",
            "equities": -0.15,
            "bonds": -0.10,
            "crypto": -0.25,
            "commodities": -0.05,
            "forex_usd": 0.05,
        },
        "OIL_SHOCK": {
            "description": "Oil price doubles (supply disruption)",
            "equities": -0.10,
            "bonds": -0.03,
            "crypto": -0.15,
            "commodities": 0.40,
            "forex_usd": 0.03,
        },
    }

    @staticmethod
    def scenario_analysis(portfolio: Dict[str, float], scenarios: Optional[Dict] = None) -> List[Dict]:
        """Run portfolio through stress scenarios.

        portfolio: {asset_class: value} e.g. {"equities": 60000, "bonds": 30000, "crypto": 10000}
        """
        if scenarios is None:
            scenarios = StressTest.SCENARIOS

        results = []
        total_value = sum(portfolio.values())

        for name, scenario in scenarios.items():
            impact = 0.0
            details = {}
            for asset_class, value in portfolio.items():
                shock = scenario.get(asset_class, 0)
                loss = value * shock
                impact += loss
                details[asset_class] = {
                    "shock": f"{shock * 100:+.1f}%",
                    "pnl": round(loss, 2),
                }

            results.append({
                "scenario": name,
                "description": scenario.get("description", ""),
                "total_pnl": round(impact, 2),
                "pnl_pct": round(impact / total_value * 100, 2) if total_value else 0,
                "details": details,
            })

        return sorted(results, key=lambda x: x["total_pnl"])


# ── Risk Engine (Facade) ────────────────────────────────────────

class RiskEngine:
    """Facade: generates complete risk summary from collected data"""

    def __init__(self):
        self.var = ValueAtRisk()
        self.dd = DrawdownAnalyzer()
        self.perf = PerformanceMetrics()
        self.stress = StressTest()

    def generate_risk_summary(self, data: Dict) -> Dict:
        """Generate risk summary from market data"""
        summary = {
            "value_at_risk": {},
            "drawdowns": {},
            "performance": {},
            "stress_tests": [],
        }

        # Extract price changes as proxy returns
        crypto_coins = data.get("crypto", {}).get("top_coins", [])
        crypto_returns = []
        for coin in crypto_coins:
            change = coin.change_percent_24h if hasattr(coin, "change_percent_24h") else coin.get("change_percent_24h", 0)
            crypto_returns.append((change or 0) / 100)

        if crypto_returns:
            summary["value_at_risk"]["crypto_portfolio"] = {
                "parametric_95": self.var.parametric_var(crypto_returns, 0.95),
                "historical_95": self.var.historical_var(crypto_returns, 0.95),
                "cvar_95": self.var.conditional_var(crypto_returns, 0.95),
            }

        # Stress tests with default portfolio
        default_portfolio = {"equities": 50000, "bonds": 30000, "crypto": 15000, "commodities": 5000}
        summary["stress_tests"] = self.stress.scenario_analysis(default_portfolio)

        # Aggregate risk level
        worst_stress = summary["stress_tests"][0] if summary["stress_tests"] else None
        if worst_stress and worst_stress["pnl_pct"] < -30:
            risk_level = "high"
        elif worst_stress and worst_stress["pnl_pct"] < -15:
            risk_level = "moderate"
        else:
            risk_level = "low"

        summary["overall_risk_level"] = risk_level

        return summary
