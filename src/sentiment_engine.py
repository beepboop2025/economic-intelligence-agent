"""
Sentiment Engine for Economic Intelligence Agent
VADER analysis, source weighting, crowd sentiment, Fear/Greed composite index
"""

import math
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    HAS_VADER = True
except ImportError:
    HAS_VADER = False
    logger.warning("vaderSentiment not installed — using keyword-based fallback")


# ── VADER Analyzer ───────────────────────────────────────────────

class VADERAnalyzer:
    """VADER sentiment analysis with financial domain adjustment"""

    # Financial terms that VADER underweights
    FINANCIAL_BOOST = {
        "rally": 0.3, "surge": 0.4, "soar": 0.4, "bullish": 0.3, "breakout": 0.3,
        "record high": 0.4, "beat expectations": 0.3, "strong earnings": 0.3,
        "crash": -0.4, "plunge": -0.4, "bearish": -0.3, "selloff": -0.3,
        "recession": -0.3, "default": -0.3, "crisis": -0.4, "collapse": -0.4,
        "downgrade": -0.3, "miss expectations": -0.3, "weak guidance": -0.3,
    }

    def __init__(self):
        self._analyzer = SentimentIntensityAnalyzer() if HAS_VADER else None

    def analyze_text(self, text: str) -> Dict:
        """Analyze text and return sentiment scores"""
        if not text:
            return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0, "label": "neutral"}

        if self._analyzer:
            scores = self._analyzer.polarity_scores(text)
        else:
            scores = self._keyword_fallback(text)

        # Apply financial domain adjustments
        adjusted = self.financial_adjustment(scores, text)
        label = self._label(adjusted["compound"])
        adjusted["label"] = label
        return adjusted

    def analyze_batch(self, texts: List[str]) -> Dict:
        """Analyze multiple texts and return aggregate"""
        if not texts:
            return {"compound": 0.0, "count": 0, "label": "neutral"}

        scores = [self.analyze_text(t) for t in texts]
        compounds = [s["compound"] for s in scores]
        avg = sum(compounds) / len(compounds)

        return {
            "compound": round(avg, 4),
            "count": len(texts),
            "positive_pct": round(sum(1 for c in compounds if c > 0.05) / len(compounds) * 100, 1),
            "negative_pct": round(sum(1 for c in compounds if c < -0.05) / len(compounds) * 100, 1),
            "neutral_pct": round(sum(1 for c in compounds if -0.05 <= c <= 0.05) / len(compounds) * 100, 1),
            "label": self._label(avg),
        }

    def financial_adjustment(self, scores: Dict, text: str) -> Dict:
        """Boost compound score for financial-specific terms"""
        text_lower = text.lower()
        boost = 0.0
        for term, weight in self.FINANCIAL_BOOST.items():
            if term in text_lower:
                boost += weight

        adjusted = dict(scores)
        compound = scores.get("compound", 0)
        # Clamp to [-1, 1]
        adjusted["compound"] = max(-1.0, min(1.0, round(compound + boost * 0.3, 4)))
        return adjusted

    @staticmethod
    def _label(compound: float) -> str:
        if compound >= 0.3:
            return "very_bullish"
        elif compound >= 0.05:
            return "bullish"
        elif compound <= -0.3:
            return "very_bearish"
        elif compound <= -0.05:
            return "bearish"
        return "neutral"

    @staticmethod
    def _keyword_fallback(text: str) -> Dict:
        """Simple keyword-based fallback when VADER is not installed"""
        text_lower = text.lower()
        positive = ["rally", "surge", "gain", "bullish", "rise", "growth", "strong", "record", "beat", "up"]
        negative = ["crash", "plunge", "loss", "bearish", "fall", "weak", "crisis", "fear", "miss", "down"]

        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)
        total = pos_count + neg_count

        if total == 0:
            return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}

        compound = (pos_count - neg_count) / total
        return {
            "compound": round(compound, 4),
            "pos": round(pos_count / total, 3),
            "neg": round(neg_count / total, 3),
            "neu": round(1 - (pos_count + neg_count) / max(len(text_lower.split()), 1), 3),
        }


# ── Source Weighter ──────────────────────────────────────────────

class SourceWeighter:
    """Weight sentiment by source reliability"""

    WEIGHTS = {
        # Tier 1 — institutional/wire services
        "reuters": 1.0, "bloomberg": 1.0, "financial times": 0.95,
        "wall street journal": 0.95, "wsj": 0.95,
        # Tier 2 — major financial media
        "cnbc": 0.8, "marketwatch": 0.75, "yahoo finance": 0.7,
        "barron's": 0.85, "the economist": 0.9,
        # Tier 3 — crypto/niche
        "coindesk": 0.65, "cointelegraph": 0.6, "decrypt": 0.55,
        # Tier 4 — social/aggregators
        "reddit": 0.3, "twitter": 0.25, "seeking alpha": 0.5,
    }

    @classmethod
    def get_weight(cls, source: str) -> float:
        source_lower = source.lower().strip()
        for key, weight in cls.WEIGHTS.items():
            if key in source_lower:
                return weight
        return 0.5  # default for unknown sources

    @classmethod
    def weighted_sentiment(cls, items: List[Dict]) -> float:
        """Compute weighted average sentiment from [{source, compound}, ...]"""
        if not items:
            return 0.0
        total_weight = 0.0
        weighted_sum = 0.0
        for item in items:
            w = cls.get_weight(item.get("source", ""))
            weighted_sum += item.get("compound", 0) * w
            total_weight += w
        return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0


# ── Crowd Sentiment Analyzer ────────────────────────────────────

class CrowdSentiment:
    """Analyze Reddit/social media crowd sentiment"""

    def __init__(self):
        self.vader = VADERAnalyzer()

    def analyze_posts(self, posts: List[Dict]) -> Dict:
        """Analyze list of social posts (Reddit format)"""
        if not posts:
            return {"score": 0.0, "volume": 0, "label": "neutral"}

        sentiments = []
        total_engagement = 0

        for post in posts:
            title = post.get("title", "")
            score = post.get("score", 0) or post.get("ups", 0)
            comments = post.get("num_comments", 0)
            engagement = score + comments * 2

            sentiment = self.vader.analyze_text(title)
            sentiments.append({
                "compound": sentiment["compound"],
                "engagement": engagement,
            })
            total_engagement += engagement

        if total_engagement == 0:
            avg = sum(s["compound"] for s in sentiments) / len(sentiments)
        else:
            avg = sum(s["compound"] * s["engagement"] for s in sentiments) / total_engagement

        return {
            "score": round(avg, 4),
            "volume": len(posts),
            "total_engagement": total_engagement,
            "label": VADERAnalyzer._label(avg),
        }


# ── Fear & Greed Index ───────────────────────────────────────────

class FearGreedIndex:
    """Composite Fear/Greed index (0=extreme fear, 100=extreme greed)

    5 components, each mapped to 0-100:
    1. Momentum (price vs moving avg proxy)
    2. Volatility (inverse — high vol = fear)
    3. Safe-haven demand (gold/bonds performance)
    4. News sentiment
    5. Crowd sentiment
    """

    @staticmethod
    def compute(
        momentum: Optional[float] = None,      # e.g. SPX change_pct
        volatility: Optional[float] = None,     # e.g. daily vol %
        safe_haven: Optional[float] = None,     # e.g. gold change_pct
        news_sentiment: Optional[float] = None, # compound [-1,1]
        crowd_sentiment: Optional[float] = None,# compound [-1,1]
    ) -> Dict:
        components = {}
        scores = []

        # 1. Momentum: map -5%..+5% to 0..100
        if momentum is not None:
            score = max(0, min(100, (momentum + 5) / 10 * 100))
            components["momentum"] = round(score, 1)
            scores.append(score)

        # 2. Volatility: inverse — high vol = fear. Map 0..5% vol to 100..0
        if volatility is not None:
            score = max(0, min(100, (1 - volatility / 5) * 100))
            components["volatility"] = round(score, 1)
            scores.append(score)

        # 3. Safe haven: strong gold/bonds = fear. Map -3%..+3% to 100..0
        if safe_haven is not None:
            score = max(0, min(100, (1 - safe_haven / 3) * 50 + 50))
            components["safe_haven_demand"] = round(score, 1)
            scores.append(score)

        # 4. News sentiment: map [-1,1] to [0,100]
        if news_sentiment is not None:
            score = (news_sentiment + 1) / 2 * 100
            components["news_sentiment"] = round(score, 1)
            scores.append(score)

        # 5. Crowd sentiment: map [-1,1] to [0,100]
        if crowd_sentiment is not None:
            score = (crowd_sentiment + 1) / 2 * 100
            components["crowd_sentiment"] = round(score, 1)
            scores.append(score)

        composite = sum(scores) / len(scores) if scores else 50
        label = (
            "extreme_fear" if composite < 20 else
            "fear" if composite < 40 else
            "neutral" if composite < 60 else
            "greed" if composite < 80 else
            "extreme_greed"
        )

        return {
            "value": round(composite, 1),
            "label": label,
            "components": components,
        }


# ── Sentiment Engine (Facade) ───────────────────────────────────

class SentimentEngine:
    """Facade: generates complete sentiment summary from collected data"""

    def __init__(self):
        self.vader = VADERAnalyzer()
        self.crowd = CrowdSentiment()
        self.fg = FearGreedIndex()

    def generate_sentiment_summary(self, data: Dict) -> Dict:
        """Generate sentiment summary from collected data"""
        summary = {
            "news_sentiment": {},
            "crowd_sentiment": {},
            "fear_greed": {},
        }

        # News sentiment
        news = data.get("news", [])
        if news:
            texts = []
            items_for_weighting = []
            for n in news:
                title = n.title if hasattr(n, "title") else n.get("title", "")
                desc = n.description if hasattr(n, "description") else n.get("description", "")
                source = n.source if hasattr(n, "source") else n.get("source", "")
                full_text = f"{title}. {desc}"
                texts.append(full_text)
                sentiment = self.vader.analyze_text(full_text)
                items_for_weighting.append({"source": source, "compound": sentiment["compound"]})

            summary["news_sentiment"] = self.vader.analyze_batch(texts)
            summary["news_sentiment"]["weighted_score"] = SourceWeighter.weighted_sentiment(items_for_weighting)

        # Crowd sentiment (Reddit posts)
        reddit_data = data.get("reddit", {})
        all_posts = []
        for sub, posts in reddit_data.items():
            if isinstance(posts, list):
                all_posts.extend(posts)
        if all_posts:
            summary["crowd_sentiment"] = self.crowd.analyze_posts(all_posts)

        # Fear/Greed Index
        news_compound = summary.get("news_sentiment", {}).get("compound", 0)
        crowd_score = summary.get("crowd_sentiment", {}).get("score")

        # Get market momentum from equities
        momentum = None
        indices = data.get("equities", {}).get("indices", [])
        if indices:
            changes = []
            for idx in indices:
                c = idx.change_percent_24h if hasattr(idx, "change_percent_24h") else idx.get("change_percent_24h", 0)
                changes.append(c or 0)
            momentum = sum(changes) / len(changes) if changes else None

        # Get safe haven movement (gold)
        safe_haven = None
        commodities = data.get("commodities", {}).get("prices", [])
        for c in commodities:
            sym = c.symbol if hasattr(c, "symbol") else c.get("symbol", "")
            if sym in ("XAU", "GOLD"):
                safe_haven = c.change_percent_24h if hasattr(c, "change_percent_24h") else c.get("change_percent_24h", 0)
                break

        summary["fear_greed"] = self.fg.compute(
            momentum=momentum,
            news_sentiment=news_compound,
            crowd_sentiment=crowd_score,
            safe_haven=safe_haven,
        )

        return summary
