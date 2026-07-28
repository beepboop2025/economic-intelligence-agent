"""Tests for src/sentiment_engine.py — pure-logic sentiment scoring.

These tests target the deterministic, dependency-free parts of the engine:
label thresholds, financial-term adjustment, source weighting, engagement-
weighted crowd scoring, and the Fear/Greed composite index. The VADER backend
is optional; the engine ships a keyword fallback, so everything here is
deterministic regardless of whether vaderSentiment is installed.
"""

import pytest

from sentiment_engine import (
    VADERAnalyzer,
    SourceWeighter,
    CrowdSentiment,
    FearGreedIndex,
)


# ── label thresholds ─────────────────────────────────────────────

class TestLabel:
    def test_very_bullish(self):
        assert VADERAnalyzer._label(0.5) == "very_bullish"

    def test_bullish(self):
        assert VADERAnalyzer._label(0.1) == "bullish"

    def test_neutral(self):
        assert VADERAnalyzer._label(0.0) == "neutral"

    def test_bearish(self):
        assert VADERAnalyzer._label(-0.1) == "bearish"

    def test_very_bearish(self):
        assert VADERAnalyzer._label(-0.5) == "very_bearish"

    def test_boundary_005_is_bullish(self):
        assert VADERAnalyzer._label(0.05) == "bullish"

    def test_boundary_03_is_very_bullish(self):
        assert VADERAnalyzer._label(0.3) == "very_bullish"


# ── financial adjustment ─────────────────────────────────────────

class TestFinancialAdjustment:
    def setup_method(self):
        self.va = VADERAnalyzer()

    def test_positive_term_boosts_compound(self):
        base = {"compound": 0.0}
        out = self.va.financial_adjustment(base, "stocks rally hard today")
        assert out["compound"] > 0.0

    def test_negative_term_lowers_compound(self):
        base = {"compound": 0.0}
        out = self.va.financial_adjustment(base, "market crash incoming")
        assert out["compound"] < 0.0

    def test_compound_clamped_to_one(self):
        base = {"compound": 0.9}
        # Many positive terms must not push compound past 1.0.
        out = self.va.financial_adjustment(
            base, "rally surge soar bullish breakout record high beat expectations"
        )
        assert out["compound"] <= 1.0

    def test_compound_clamped_to_negative_one(self):
        base = {"compound": -0.9}
        out = self.va.financial_adjustment(
            base, "crash plunge bearish selloff recession crisis collapse"
        )
        assert out["compound"] >= -1.0

    def test_neutral_text_unchanged(self):
        base = {"compound": 0.2}
        out = self.va.financial_adjustment(base, "the meeting is scheduled for tomorrow")
        assert out["compound"] == pytest.approx(0.2)


# ── empty / batch handling ───────────────────────────────────────

class TestAnalyzeText:
    def test_empty_text_is_neutral(self):
        out = VADERAnalyzer().analyze_text("")
        assert out["label"] == "neutral"
        assert out["compound"] == 0.0

    def test_analyze_text_carries_label(self):
        out = VADERAnalyzer().analyze_text("massive rally and surge")
        assert out["label"] in {"bullish", "very_bullish"}

    def test_batch_empty_returns_zero_count(self):
        out = VADERAnalyzer().analyze_batch([])
        assert out["count"] == 0
        assert out["label"] == "neutral"

    def test_batch_percentages_sum_to_100(self):
        texts = ["huge rally surge", "terrible crash plunge", "meeting tomorrow"]
        out = VADERAnalyzer().analyze_batch(texts)
        assert out["count"] == 3
        total = out["positive_pct"] + out["negative_pct"] + out["neutral_pct"]
        assert total == pytest.approx(100.0, abs=0.2)


# ── source weighting ─────────────────────────────────────────────

class TestSourceWeighter:
    def test_tier1_source_full_weight(self):
        assert SourceWeighter.get_weight("Reuters") == 1.0

    def test_substring_match_case_insensitive(self):
        assert SourceWeighter.get_weight("CNBC Markets Desk") == 0.8

    def test_unknown_source_default_weight(self):
        assert SourceWeighter.get_weight("Some Random Blog") == 0.5

    def test_social_source_low_weight(self):
        assert SourceWeighter.get_weight("reddit") == 0.3

    def test_weighted_sentiment_favors_trusted_source(self):
        # Reuters (1.0) bullish vs twitter (0.25) bearish => net positive.
        items = [
            {"source": "reuters", "compound": 0.8},
            {"source": "twitter", "compound": -0.8},
        ]
        score = SourceWeighter.weighted_sentiment(items)
        assert score > 0

    def test_weighted_sentiment_empty_is_zero(self):
        assert SourceWeighter.weighted_sentiment([]) == 0.0

    def test_weighted_sentiment_manual_value(self):
        items = [
            {"source": "reuters", "compound": 1.0},   # weight 1.0
            {"source": "reddit", "compound": 0.0},     # weight 0.3
        ]
        # (1.0*1.0 + 0.0*0.3) / (1.0 + 0.3) = 0.7692...
        assert SourceWeighter.weighted_sentiment(items) == pytest.approx(0.7692, abs=1e-3)


# ── crowd sentiment ──────────────────────────────────────────────

class TestCrowdSentiment:
    def test_empty_posts_neutral(self):
        out = CrowdSentiment().analyze_posts([])
        assert out["volume"] == 0
        assert out["label"] == "neutral"

    def test_volume_counts_posts(self):
        posts = [
            {"title": "rally surge", "score": 10, "num_comments": 2},
            {"title": "crash plunge", "score": 5, "num_comments": 1},
        ]
        out = CrowdSentiment().analyze_posts(posts)
        assert out["volume"] == 2

    def test_engagement_weighting_dominated_by_high_engagement(self):
        # A heavily-upvoted bullish post should pull the aggregate positive even
        # though a low-engagement bearish post exists.
        posts = [
            {"title": "massive rally surge bullish breakout", "score": 5000, "num_comments": 1000},
            {"title": "crash plunge bearish", "score": 1, "num_comments": 0},
        ]
        out = CrowdSentiment().analyze_posts(posts)
        assert out["score"] > 0
        assert out["total_engagement"] > 0

    def test_zero_engagement_falls_back_to_plain_average(self):
        posts = [
            {"title": "rally surge bullish", "score": 0, "num_comments": 0},
            {"title": "crash plunge bearish", "score": 0, "num_comments": 0},
        ]
        out = CrowdSentiment().analyze_posts(posts)
        assert out["total_engagement"] == 0
        # Mixed bull/bear with equal weight => roughly neutral.
        assert -0.5 <= out["score"] <= 0.5


# ── Fear & Greed Index ───────────────────────────────────────────

class TestFearGreed:
    def test_no_inputs_defaults_to_neutral_50(self):
        out = FearGreedIndex.compute()
        assert out["value"] == 50
        assert out["label"] == "neutral"

    def test_strong_momentum_maps_to_greed(self):
        out = FearGreedIndex.compute(momentum=5.0)
        # +5% momentum maps to the top of the 0..100 range.
        assert out["value"] == pytest.approx(100.0)
        assert out["label"] == "extreme_greed"

    def test_crash_momentum_maps_to_extreme_fear(self):
        out = FearGreedIndex.compute(momentum=-5.0)
        assert out["value"] == pytest.approx(0.0)
        assert out["label"] == "extreme_fear"

    def test_high_volatility_lowers_score(self):
        calm = FearGreedIndex.compute(volatility=0.0)["value"]
        wild = FearGreedIndex.compute(volatility=5.0)["value"]
        # High volatility => fear => lower score than a calm tape.
        assert wild < calm

    def test_news_sentiment_maps_neutral_compound_to_midpoint(self):
        out = FearGreedIndex.compute(news_sentiment=0.0)
        assert out["value"] == pytest.approx(50.0)

    def test_components_only_include_provided_inputs(self):
        out = FearGreedIndex.compute(momentum=1.0, news_sentiment=0.5)
        assert set(out["components"]) == {"momentum", "news_sentiment"}

    def test_composite_is_mean_of_components(self):
        # momentum=0 -> 50, news_sentiment=1.0 -> 100; mean = 75 (greed).
        out = FearGreedIndex.compute(momentum=0.0, news_sentiment=1.0)
        assert out["value"] == pytest.approx(75.0)
        assert out["label"] == "greed"

    def test_label_bands(self):
        assert FearGreedIndex.compute(momentum=-4.5)["label"] == "extreme_fear"
        assert FearGreedIndex.compute(momentum=4.5)["label"] == "extreme_greed"
