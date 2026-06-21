"""Tests for src/alert_engine.py — alert construction, dedup keys, and rule logic.

Only the pure in-memory rule evaluation is exercised. Notification dispatch
(console/file/webhook/email) and SQLite-backed dedup are intentionally not
touched, so these tests perform no I/O.
"""

import pytest

from alert_engine import Alert, AlertRuleEngine


# ── Alert ────────────────────────────────────────────────────────

class TestAlert:
    def test_to_dict_round_trip_fields(self):
        a = Alert("price_threshold", "high", "BTC surged 9%", details={"symbol": "BTC"})
        d = a.to_dict()
        assert d["type"] == "price_threshold"
        assert d["severity"] == "high"
        assert d["message"] == "BTC surged 9%"
        assert d["details"] == {"symbol": "BTC"}
        assert "dedup_key" in d
        assert "triggered_at" in d

    def test_auto_dedup_key_is_deterministic_for_same_inputs(self):
        a1 = Alert("price_threshold", "high", "same msg", details={"symbol": "BTC"})
        a2 = Alert("price_threshold", "high", "same msg", details={"symbol": "BTC"})
        # Same type/symbol/message on the same calendar day => identical key.
        assert a1.dedup_key == a2.dedup_key

    def test_auto_dedup_key_differs_by_symbol(self):
        a1 = Alert("price_threshold", "high", "moved", details={"symbol": "BTC"})
        a2 = Alert("price_threshold", "high", "moved", details={"symbol": "ETH"})
        assert a1.dedup_key != a2.dedup_key

    def test_explicit_dedup_key_preserved(self):
        a = Alert("price_threshold", "high", "msg", dedup_key="custom-key")
        assert a.dedup_key == "custom-key"


# ── price threshold rule ─────────────────────────────────────────

class TestPriceThresholdRule:
    def setup_method(self):
        self.engine = AlertRuleEngine()  # default 5% threshold

    def test_large_move_triggers_alert(self):
        data = {"crypto": {"top_coins": [{"symbol": "BTC", "change_percent_24h": 9.0}]}}
        alerts = self.engine._check_price_thresholds(data)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "price_threshold"
        assert "BTC" in alerts[0].message

    def test_small_move_does_not_trigger(self):
        data = {"crypto": {"top_coins": [{"symbol": "BTC", "change_percent_24h": 1.5}]}}
        assert self.engine._check_price_thresholds(data) == []

    def test_severity_escalates_at_double_threshold(self):
        # 12% is > 2x the 5% threshold => high severity; 6% => medium.
        big = {"crypto": {"top_coins": [{"symbol": "BTC", "change_percent_24h": 12.0}]}}
        small = {"crypto": {"top_coins": [{"symbol": "ETH", "change_percent_24h": 6.0}]}}
        assert self.engine._check_price_thresholds(big)[0].severity == "high"
        assert self.engine._check_price_thresholds(small)[0].severity == "medium"

    def test_negative_move_says_dropped(self):
        data = {"crypto": {"top_coins": [{"symbol": "BTC", "change_percent_24h": -7.0}]}}
        alert = self.engine._check_price_thresholds(data)[0]
        assert "dropped" in alert.message

    def test_none_change_is_ignored(self):
        data = {"crypto": {"top_coins": [{"symbol": "BTC", "change_percent_24h": None}]}}
        assert self.engine._check_price_thresholds(data) == []

    def test_custom_threshold_respected(self):
        engine = AlertRuleEngine({"price_change_pct": 10.0})
        data = {"crypto": {"top_coins": [{"symbol": "BTC", "change_percent_24h": 7.0}]}}
        # 7% is below the custom 10% threshold => no alert.
        assert engine._check_price_thresholds(data) == []


# ── technical signal rule ────────────────────────────────────────

class TestTechnicalSignalRule:
    def setup_method(self):
        self.engine = AlertRuleEngine()

    def test_bullish_signal_alerts(self):
        quant = {"technical_signals": {"BTC": {"signal": "bullish"}}}
        alerts = self.engine._check_technical_signals(quant)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "technical_signal"

    def test_neutral_signal_ignored(self):
        quant = {"technical_signals": {"BTC": {"signal": "neutral"}}}
        assert self.engine._check_technical_signals(quant) == []


# ── volatility spike rule ────────────────────────────────────────

class TestVolatilitySpikeRule:
    def test_outlier_triggers_spike(self):
        engine = AlertRuleEngine({"volatility_spike": 2.0})
        coins = [{"symbol": f"C{i}", "change_percent_24h": 1.0} for i in range(6)]
        coins.append({"symbol": "OUT", "change_percent_24h": 40.0})  # huge outlier
        alerts = engine._check_volatility_spikes({"crypto": {"top_coins": coins}})
        assert any(a.details["symbol"] == "OUT" for a in alerts)

    def test_no_spike_when_too_few_coins(self):
        engine = AlertRuleEngine()
        coins = [{"symbol": "A", "change_percent_24h": 50.0}]
        assert engine._check_volatility_spikes({"crypto": {"top_coins": coins}}) == []

    def test_uniform_changes_produce_no_spike(self):
        engine = AlertRuleEngine({"volatility_spike": 2.0})
        coins = [{"symbol": f"C{i}", "change_percent_24h": 3.0} for i in range(8)]
        # Zero dispersion => z-scores are 0 => nothing triggers.
        assert engine._check_volatility_spikes({"crypto": {"top_coins": coins}}) == []


# ── economic calendar rule ───────────────────────────────────────

class TestEconomicCalendarRule:
    def setup_method(self):
        self.engine = AlertRuleEngine()

    def test_high_impact_event_alerts(self):
        data = {"economic_events": [{"event": "FOMC Decision", "impact": "high"}]}
        alerts = self.engine._check_economic_calendar(data)
        assert len(alerts) == 1
        assert "FOMC Decision" in alerts[0].message

    def test_low_impact_event_ignored(self):
        data = {"economic_events": [{"event": "Minor Print", "impact": "low"}]}
        assert self.engine._check_economic_calendar(data) == []


# ── sentiment shift rule ─────────────────────────────────────────

class TestSentimentShiftRule:
    def setup_method(self):
        self.engine = AlertRuleEngine()

    def test_extreme_fear_triggers(self):
        sentiment = {"fear_greed": {"value": 8, "label": "extreme_fear"}}
        alerts = self.engine._check_sentiment_shifts(sentiment)
        assert any(a.alert_type == "sentiment_shift" for a in alerts)
        # value < 10 => high severity.
        assert alerts[0].severity == "high"

    def test_neutral_fear_greed_does_not_trigger(self):
        sentiment = {"fear_greed": {"value": 50, "label": "neutral"}}
        assert self.engine._check_sentiment_shifts(sentiment) == []

    def test_strong_news_sentiment_triggers(self):
        sentiment = {"news_sentiment": {"compound": 0.6}}
        alerts = self.engine._check_sentiment_shifts(sentiment)
        assert any("strongly bullish" in a.message for a in alerts)

    def test_mild_news_sentiment_ignored(self):
        sentiment = {"news_sentiment": {"compound": 0.1}}
        assert self.engine._check_sentiment_shifts(sentiment) == []


# ── full evaluate() integration ──────────────────────────────────

class TestEvaluateAll:
    def test_evaluate_collects_from_all_rule_groups(self):
        engine = AlertRuleEngine()
        data = {
            "crypto": {"top_coins": [{"symbol": "BTC", "change_percent_24h": 11.0}]},
            "economic_events": [{"event": "CPI Release", "impact": "high"}],
        }
        quant = {"technical_signals": {"ETH": {"signal": "bearish"}}}
        sentiment = {"fear_greed": {"value": 5, "label": "extreme_fear"}}
        alerts = engine.evaluate(data, quant, sentiment, {})
        types = {a.alert_type for a in alerts}
        assert "price_threshold" in types
        assert "technical_signal" in types
        assert "economic_calendar" in types
        assert "sentiment_shift" in types

    def test_evaluate_quiet_market_yields_no_alerts(self):
        engine = AlertRuleEngine()
        data = {"crypto": {"top_coins": [{"symbol": "BTC", "change_percent_24h": 0.5}]}}
        quant = {"technical_signals": {"BTC": {"signal": "neutral"}}}
        sentiment = {"fear_greed": {"value": 50, "label": "neutral"}}
        assert engine.evaluate(data, quant, sentiment, {}) == []
