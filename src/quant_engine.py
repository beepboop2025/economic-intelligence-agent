"""
Quantitative Analysis Engine for Economic Intelligence Agent
RSI, MACD, Bollinger Bands, correlations, yield curve, regime detection
All implementations use numpy only (no heavy ML deps).
"""

import math
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not installed — quant engine will use pure-Python fallbacks")


# ── Pure-Python helpers (used when numpy is unavailable) ──────────

def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0

def _std(vals: List[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))


# ── Technical Analysis ───────────────────────────────────────────

class TechnicalAnalysis:
    """Core technical indicators"""

    @staticmethod
    def sma(prices: List[float], period: int) -> List[float]:
        """Simple Moving Average"""
        if len(prices) < period:
            return []
        result = []
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1 : i + 1]
            result.append(_mean(window))
        return result

    @staticmethod
    def ema(prices: List[float], period: int) -> List[float]:
        """Exponential Moving Average"""
        if len(prices) < period:
            return []
        k = 2.0 / (period + 1)
        ema_vals = [_mean(prices[:period])]
        for price in prices[period:]:
            ema_vals.append(price * k + ema_vals[-1] * (1 - k))
        return ema_vals

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """Relative Strength Index (Wilder's smoothing)"""
        if len(prices) < period + 1:
            return None

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]

        avg_gain = _mean(gains[:period])
        avg_loss = _mean(losses[:period])

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[Dict]:
        """MACD with signal line and histogram"""
        if len(prices) < slow + signal:
            return None

        ta = TechnicalAnalysis
        fast_ema = ta.ema(prices, fast)
        slow_ema = ta.ema(prices, slow)

        # Align: fast_ema is longer, trim to match slow_ema length
        offset = len(fast_ema) - len(slow_ema)
        fast_aligned = fast_ema[offset:]

        macd_line = [f - s for f, s in zip(fast_aligned, slow_ema)]
        signal_line = ta.ema(macd_line, signal) if len(macd_line) >= signal else []
        histogram = []
        if signal_line:
            offset2 = len(macd_line) - len(signal_line)
            histogram = [m - s for m, s in zip(macd_line[offset2:], signal_line)]

        return {
            "macd": macd_line[-1] if macd_line else 0,
            "signal": signal_line[-1] if signal_line else 0,
            "histogram": histogram[-1] if histogram else 0,
            "trend": "bullish" if (histogram and histogram[-1] > 0) else "bearish",
        }

    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2.0) -> Optional[Dict]:
        """Bollinger Bands"""
        if len(prices) < period:
            return None

        sma_val = _mean(prices[-period:])
        std_val = _std(prices[-period:])
        upper = sma_val + num_std * std_val
        lower = sma_val - num_std * std_val
        current = prices[-1]

        # %B indicator: 0 = at lower, 1 = at upper
        bandwidth = upper - lower
        pct_b = (current - lower) / bandwidth if bandwidth > 0 else 0.5

        return {
            "upper": round(upper, 4),
            "middle": round(sma_val, 4),
            "lower": round(lower, 4),
            "bandwidth": round(bandwidth / sma_val * 100, 2) if sma_val else 0,
            "percent_b": round(pct_b, 3),
            "signal": "overbought" if pct_b > 1 else ("oversold" if pct_b < 0 else "neutral"),
        }

    @staticmethod
    def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> Optional[float]:
        """Average True Range"""
        if len(close) < period + 1:
            return None

        true_ranges = []
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
            true_ranges.append(tr)

        # Wilder's smoothing
        atr_val = _mean(true_ranges[:period])
        for tr in true_ranges[period:]:
            atr_val = (atr_val * (period - 1) + tr) / period
        return round(atr_val, 4)


# ── Correlation Analyzer ─────────────────────────────────────────

class CorrelationAnalyzer:
    """Compute correlation matrix and detect regime changes"""

    @staticmethod
    def _returns(prices: List[float]) -> List[float]:
        if len(prices) < 2:
            return []
        return [(prices[i] - prices[i - 1]) / prices[i - 1]
                for i in range(1, len(prices)) if prices[i - 1] != 0]

    @staticmethod
    def pearson(x: List[float], y: List[float]) -> float:
        """Pearson correlation coefficient"""
        n = min(len(x), len(y))
        if n < 3:
            return 0.0
        x, y = x[:n], y[:n]
        mx, my = _mean(x), _mean(y)
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if dx == 0 or dy == 0:
            return 0.0
        return num / (dx * dy)

    def compute_matrix(self, price_series: Dict[str, List[float]]) -> Dict[str, Dict[str, float]]:
        """Compute pairwise correlation matrix from price series"""
        symbols = list(price_series.keys())
        returns = {s: self._returns(p) for s, p in price_series.items()}
        matrix = {}
        for s1 in symbols:
            matrix[s1] = {}
            for s2 in symbols:
                matrix[s1][s2] = round(self.pearson(returns[s1], returns[s2]), 3)
        return matrix

    def find_divergences(self, matrix: Dict[str, Dict[str, float]], threshold: float = -0.5) -> List[Dict]:
        """Find negatively correlated pairs (divergences)"""
        seen = set()
        results = []
        for s1 in matrix:
            for s2 in matrix[s1]:
                if s1 == s2:
                    continue
                pair = tuple(sorted([s1, s2]))
                if pair in seen:
                    continue
                seen.add(pair)
                corr = matrix[s1][s2]
                if corr <= threshold:
                    results.append({"pair": list(pair), "correlation": corr, "type": "divergence"})
        return results


# ── Market Regime Detector ───────────────────────────────────────

class MarketRegimeDetector:
    """Detect market regime: bull, bear, sideways, transition"""

    @staticmethod
    def detect(prices: List[float], window: int = 20) -> Dict:
        if len(prices) < window * 2:
            return {"regime": "unknown", "confidence": 0}

        recent = prices[-window:]
        prior = prices[-window * 2 : -window]

        recent_return = (recent[-1] - recent[0]) / recent[0] if recent[0] != 0 else 0
        prior_return = (prior[-1] - prior[0]) / prior[0] if prior[0] != 0 else 0
        volatility = _std([(prices[i] - prices[i - 1]) / prices[i - 1]
                           for i in range(1, len(recent)) if prices[i - 1] != 0])

        if recent_return > 0.05 and prior_return > 0.02:
            regime = "bull"
            confidence = min(recent_return * 10, 1.0)
        elif recent_return < -0.05 and prior_return < -0.02:
            regime = "bear"
            confidence = min(abs(recent_return) * 10, 1.0)
        elif abs(recent_return) < 0.02 and volatility < 0.015:
            regime = "sideways"
            confidence = 0.6
        else:
            regime = "transition"
            confidence = 0.4

        return {
            "regime": regime,
            "confidence": round(confidence, 2),
            "recent_return": round(recent_return * 100, 2),
            "volatility": round(volatility * 100, 2) if volatility else 0,
        }


# ── Yield Curve Analyzer ────────────────────────────────────────

class YieldCurveAnalyzer:
    """Analyze yield curve shape and derive signals"""

    TENORS = ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]

    @staticmethod
    def spread(curve: Dict[str, float], short: str = "2Y", long: str = "10Y") -> Optional[float]:
        """Compute yield spread (long minus short)"""
        if short in curve and long in curve:
            return round(curve[long] - curve[short], 3)
        return None

    @staticmethod
    def is_inverted(curve: Dict[str, float]) -> bool:
        """Check if 2Y-10Y spread is negative"""
        if "2Y" in curve and "10Y" in curve:
            return curve["10Y"] < curve["2Y"]
        return False

    @staticmethod
    def steepness(curve: Dict[str, float]) -> Optional[float]:
        """3M to 10Y spread as overall steepness measure"""
        if "3M" in curve and "10Y" in curve:
            return round(curve["10Y"] - curve["3M"], 3)
        return None

    @staticmethod
    def term_premium(curve: Dict[str, float]) -> Optional[Dict]:
        """Estimate term premium from curve shape"""
        if not ("2Y" in curve and "5Y" in curve and "10Y" in curve):
            return None
        short_mid = curve["5Y"] - curve["2Y"]
        mid_long = curve["10Y"] - curve["5Y"]
        return {
            "front_end": round(short_mid, 3),
            "back_end": round(mid_long, 3),
            "assessment": "positive" if mid_long > 0 else "negative",
        }


# ── Quant Engine (Facade) ───────────────────────────────────────

class QuantEngine:
    """Facade that generates a complete quantitative summary from collected data"""

    def __init__(self):
        self.ta = TechnicalAnalysis()
        self.corr = CorrelationAnalyzer()
        self.regime = MarketRegimeDetector()
        self.yc = YieldCurveAnalyzer()

    def generate_quant_summary(self, data: Dict) -> Dict:
        """Generate comprehensive quant summary from collected data"""
        summary = {
            "technical_signals": {},
            "correlations": {},
            "market_regime": {},
            "yield_curve": {},
        }

        # Technical signals on crypto
        crypto_coins = data.get("crypto", {}).get("top_coins", [])
        for coin in crypto_coins[:5]:
            sym = coin.symbol if hasattr(coin, "symbol") else coin.get("symbol", "?")
            price = coin.price if hasattr(coin, "price") else coin.get("price", 0)
            change = coin.change_percent_24h if hasattr(coin, "change_percent_24h") else coin.get("change_percent_24h", 0)

            # Single-point signals (we only have current price; simulate a short series)
            summary["technical_signals"][sym] = {
                "price": price,
                "change_24h": change,
                "signal": "bullish" if change > 2 else ("bearish" if change < -2 else "neutral"),
            }

        # Yield curve analysis
        bonds = data.get("bonds", {}).get("yields", [])
        if bonds:
            curve = {}
            for bond in bonds:
                sym = bond.symbol if hasattr(bond, "symbol") else bond.get("symbol", "")
                p = bond.price if hasattr(bond, "price") else bond.get("price", 0)
                # Map symbol to tenor
                mapping = {"US2Y": "2Y", "US10Y": "10Y", "US30Y": "30Y", "US3M": "3M",
                           "US6M": "6M", "US1Y": "1Y", "US5Y": "5Y", "US7Y": "7Y", "US20Y": "20Y"}
                tenor = mapping.get(sym)
                if tenor:
                    curve[tenor] = p
            if curve:
                summary["yield_curve"] = {
                    "curve": curve,
                    "spread_2y10y": self.yc.spread(curve),
                    "inverted": self.yc.is_inverted(curve),
                    "steepness": self.yc.steepness(curve),
                    "term_premium": self.yc.term_premium(curve),
                }

        # Market regime (use index data if available)
        indices = data.get("equities", {}).get("indices", [])
        for idx in indices[:3]:
            sym = idx.symbol if hasattr(idx, "symbol") else idx.get("symbol", "?")
            change = idx.change_percent_24h if hasattr(idx, "change_percent_24h") else idx.get("change_percent_24h", 0)
            summary["market_regime"][sym] = {
                "daily_change": change,
                "signal": "bullish" if change > 0.5 else ("bearish" if change < -0.5 else "neutral"),
            }

        return summary
