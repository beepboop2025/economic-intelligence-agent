"""
Data Collection Module for Economic Intelligence Agent
Fetches data from multiple financial and economic sources
"""

import os
import json
import asyncio
import aiohttp
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from functools import lru_cache
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from resilience import RateLimiter


@dataclass
class MarketData:
    """Unified market data structure"""
    asset_class: str
    symbol: str
    name: str
    price: float
    change_24h: float
    change_percent_24h: float
    volume: Optional[float] = None
    market_cap: Optional[float] = None
    timestamp: datetime = None
    additional_data: Dict = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.additional_data is None:
            self.additional_data = {}


@dataclass
class EconomicEvent:
    """Economic event data structure"""
    title: str
    description: str
    source: str
    timestamp: datetime
    region: str
    impact: str  # high, medium, low
    categories: List[str]
    related_assets: List[str]
    url: Optional[str] = None


@dataclass
class NewsItem:
    """News article structure"""
    title: str
    description: str
    source: str
    published_at: datetime
    url: str
    sentiment: Optional[str] = None
    categories: List[str] = None
    
    def __post_init__(self):
        if self.categories is None:
            self.categories = []


class BaseCollector:
    """Base class for data collectors"""

    # Shared rate limiter: 10 requests per 60 seconds (conservative default)
    _rate_limiter = RateLimiter(max_tokens=10, refill_period=60, name="base_collector")
    _last_request_time = 0.0
    _min_request_interval = 1.0  # minimum seconds between requests

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            try:
                await self.session.close()
            except Exception:
                pass
        return False

    async def fetch(self, url: str, params: Dict = None, headers: Dict = None) -> Dict:
        """Async fetch with error handling and rate limiting"""
        # Simple sleep-based rate limit to avoid hammering APIs
        now = time.monotonic()
        elapsed = now - BaseCollector._last_request_time
        if elapsed < BaseCollector._min_request_interval:
            await asyncio.sleep(BaseCollector._min_request_interval - elapsed)
        BaseCollector._last_request_time = time.monotonic()

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.get(url, params=params, headers=headers, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(f"HTTP {resp.status} from {url}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return {}


class CryptoCollector(BaseCollector):
    """Collects cryptocurrency market data from CoinGecko"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    async def get_global_data(self) -> Dict:
        """Get global crypto market metrics"""
        url = f"{self.BASE_URL}/global"
        return await self.fetch(url)
    
    async def get_top_coins(self, limit: int = 50) -> List[MarketData]:
        """Get top cryptocurrencies by market cap"""
        url = f"{self.BASE_URL}/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h"
        }
        data = await self.fetch(url, params)

        coins = []
        if not isinstance(data, list):
            return coins
        for coin in data:
            coins.append(MarketData(
                asset_class="crypto",
                symbol=coin["symbol"].upper(),
                name=coin["name"],
                price=coin.get("current_price") or 0,
                change_24h=coin.get("price_change_24h") or 0,
                change_percent_24h=coin.get("price_change_percentage_24h") or 0,
                volume=coin.get("total_volume") or 0,
                market_cap=coin.get("market_cap") or 0,
                additional_data={
                    "ath": coin.get("ath"),
                    "ath_change_percent": coin.get("ath_change_percentage"),
                    "circulating_supply": coin.get("circulating_supply")
                }
            ))
        return coins
    
    async def get_trending(self) -> List[Dict]:
        """Get trending search coins"""
        url = f"{self.BASE_URL}/search/trending"
        return await self.fetch(url)


class EquityCollector(BaseCollector):
    """Collects equity market data — now uses yfinance"""

    INDICES = {
        "^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "NASDAQ",
        "^FTSE": "FTSE 100", "^GDAXI": "DAX 40", "^N225": "Nikkei 225",
        "^HSI": "Hang Seng", "000001.SS": "Shanghai Composite",
        "^NSEI": "NIFTY 50", "^BVSP": "Bovespa",
    }

    SECTOR_ETFS = {
        "XLE": "Energy", "XLF": "Financials", "XLK": "Technology",
        "XLV": "Healthcare", "XLY": "Consumer Discretionary",
        "XLP": "Consumer Staples", "XLI": "Industrials",
        "XLB": "Materials", "XLU": "Utilities", "XLRE": "Real Estate",
        "XLC": "Communication Services",
    }

    def get_market_summary(self) -> List[MarketData]:
        """Get major indices and sector ETFs via yfinance"""
        results = []
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed — equity data unavailable")
            return results

        symbols = list(self.INDICES.keys()) + list(self.SECTOR_ETFS.keys())
        name_map = {**self.INDICES, **self.SECTOR_ETFS}

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info if hasattr(ticker, 'fast_info') else {}
                price = getattr(info, 'last_price', None) or 0
                prev_close = getattr(info, 'previous_close', None) or price
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0
                mcap = getattr(info, 'market_cap', None)

                results.append(MarketData(
                    asset_class="equities",
                    symbol=symbol.replace("^", ""),
                    name=name_map.get(symbol, symbol),
                    price=float(price),
                    change_24h=float(change),
                    change_percent_24h=float(change_pct),
                    market_cap=float(mcap) if mcap else None,
                ))
            except Exception as e:
                logger.debug(f"yfinance error for {symbol}: {e}")
        return results


class YahooFinanceCollector(BaseCollector):
    """Dedicated Yahoo Finance collector for indices and sector ETFs"""

    def get_data(self, symbols: List[str]) -> List[MarketData]:
        """Fetch price data for a list of ticker symbols"""
        results = []
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed")
            return results

        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                info = t.fast_info if hasattr(t, 'fast_info') else {}
                price = getattr(info, 'last_price', 0) or 0
                prev = getattr(info, 'previous_close', price) or price
                results.append(MarketData(
                    asset_class="equities",
                    symbol=sym,
                    name=sym,
                    price=float(price),
                    change_24h=float(price - prev),
                    change_percent_24h=float((price - prev) / prev * 100) if prev else 0,
                ))
            except Exception as e:
                logger.debug(f"yfinance {sym}: {e}")
        return results


class ForexCollector(BaseCollector):
    """Collects foreign exchange data"""

    MAJOR_PAIRS = ["EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]

    async def get_rates(self, base: str = "USD") -> Dict:
        url = f"https://api.exchangerate-api.com/v4/latest/{base}"
        return await self.fetch(url)


class FREDCollector(BaseCollector):
    """Federal Reserve Economic Data (FRED) collector

    Series: GDP, CPI, unemployment, fed funds rate, M2 money supply, PCE, treasury yields
    """

    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    SERIES = {
        "GDP": "Gross Domestic Product",
        "CPIAUCSL": "Consumer Price Index",
        "UNRATE": "Unemployment Rate",
        "FEDFUNDS": "Federal Funds Rate",
        "M2SL": "M2 Money Supply",
        "PCEPI": "PCE Price Index",
        "GS10": "10-Year Treasury Yield",
        "GS2": "2-Year Treasury Yield",
        "GS30": "30-Year Treasury Yield",
        "GS5": "5-Year Treasury Yield",
        "DGS3MO": "3-Month Treasury Yield",
    }

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key or os.getenv("FRED_API_KEY", ""))

    async def get_series(self, series_id: str, limit: int = 5) -> List[Dict]:
        if not self.api_key:
            logger.warning("FRED API key not set")
            return []
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        data = await self.fetch(self.BASE_URL, params)
        return data.get("observations", [])

    async def get_all_indicators(self) -> Dict[str, Any]:
        """Fetch latest values for all tracked FRED series"""
        results = {}
        for series_id, name in self.SERIES.items():
            try:
                obs = await self.get_series(series_id, limit=1)
                if obs:
                    val = obs[0].get("value", ".")
                    results[series_id] = {
                        "name": name,
                        "value": float(val) if val != "." else None,
                        "date": obs[0].get("date", ""),
                    }
            except Exception as e:
                logger.debug(f"FRED {series_id}: {e}")
        return results


class TreasuryYieldCollector(BaseCollector):
    """Full US Treasury yield curve via FRED"""

    MATURITIES = {
        "DGS3MO": ("3M", "3-Month"), "DGS6MO": ("6M", "6-Month"),
        "DGS1": ("1Y", "1-Year"), "DGS2": ("2Y", "2-Year"),
        "DGS3": ("3Y", "3-Year"), "DGS5": ("5Y", "5-Year"),
        "DGS7": ("7Y", "7-Year"), "DGS10": ("10Y", "10-Year"),
        "DGS20": ("20Y", "20-Year"), "DGS30": ("30Y", "30-Year"),
    }

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key or os.getenv("FRED_API_KEY", ""))

    async def get_yield_curve(self) -> List[MarketData]:
        if not self.api_key:
            return []
        results = []
        fred = FREDCollector(self.api_key)
        fred.session = self.session
        for series_id, (tenor, name) in self.MATURITIES.items():
            try:
                obs = await fred.get_series(series_id, limit=2)
                if obs and obs[0].get("value", ".") != ".":
                    current = float(obs[0]["value"])
                    prev = float(obs[1]["value"]) if len(obs) > 1 and obs[1].get("value", ".") != "." else current
                    results.append(MarketData(
                        asset_class="bonds",
                        symbol=f"US{tenor}",
                        name=f"US {name} Treasury",
                        price=current,
                        change_24h=round(current - prev, 3),
                        change_percent_24h=round((current - prev) / prev * 100, 2) if prev else 0,
                    ))
            except Exception as e:
                logger.debug(f"Treasury {series_id}: {e}")
        return results


class CommodityCollector(BaseCollector):
    """Commodity prices via FRED series"""

    COMMODITIES = {
        "GOLDAMGBD228NLBM": ("XAU", "Gold (London Fix)"),
        "DCOILWTICO": ("CL", "WTI Crude Oil"),
        "DCOILBRENTEU": ("BZ", "Brent Crude Oil"),
        "DHHNGSP": ("NG", "Natural Gas (Henry Hub)"),
        "PCOPPUSDM": ("HG", "Copper"),
    }

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key or os.getenv("FRED_API_KEY", ""))

    async def get_prices(self) -> List[MarketData]:
        if not self.api_key:
            return []
        results = []
        fred = FREDCollector(self.api_key)
        fred.session = self.session
        for series_id, (symbol, name) in self.COMMODITIES.items():
            try:
                obs = await fred.get_series(series_id, limit=2)
                if obs and obs[0].get("value", ".") != ".":
                    current = float(obs[0]["value"])
                    prev = float(obs[1]["value"]) if len(obs) > 1 and obs[1].get("value", ".") != "." else current
                    results.append(MarketData(
                        asset_class="commodities",
                        symbol=symbol,
                        name=name,
                        price=current,
                        change_24h=round(current - prev, 4),
                        change_percent_24h=round((current - prev) / prev * 100, 2) if prev else 0,
                    ))
            except Exception as e:
                logger.debug(f"Commodity {series_id}: {e}")
        return results


class AlphaVantageCollector(BaseCollector):
    """Alpha Vantage: stock quotes, top gainers/losers (25 calls/day free)"""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key or os.getenv("ALPHA_VANTAGE_KEY", ""))

    async def get_quote(self, symbol: str) -> Optional[MarketData]:
        if not self.api_key:
            return None
        params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": self.api_key}
        data = await self.fetch(self.BASE_URL, params)
        q = data.get("Global Quote", {})
        if not q:
            return None
        price = float(q.get("05. price", 0) or 0)
        change = float(q.get("09. change", 0) or 0)
        change_pct_str = q.get("10. change percent", "0%").replace("%", "")
        change_pct = float(change_pct_str) if change_pct_str else 0
        volume = float(q.get("06. volume", 0) or 0)
        return MarketData(
            asset_class="equities",
            symbol=symbol,
            name=symbol,
            price=price,
            change_24h=change,
            change_percent_24h=change_pct,
            volume=volume,
        )

    async def get_top_movers(self) -> Dict:
        if not self.api_key:
            return {}
        params = {"function": "TOP_GAINERS_LOSERS", "apikey": self.api_key}
        return await self.fetch(self.BASE_URL, params)


class FinnhubCollector(BaseCollector):
    """Finnhub: market news and economic calendar"""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key or os.getenv("FINNHUB_KEY", ""))

    async def get_market_news(self, category: str = "general") -> List[NewsItem]:
        if not self.api_key:
            return []
        url = f"{self.BASE_URL}/news"
        params = {"category": category, "token": self.api_key}
        data = await self.fetch(url, params)
        items = []
        if isinstance(data, list):
            for article in data[:30]:
                try:
                    items.append(NewsItem(
                        title=article.get("headline", ""),
                        description=article.get("summary", ""),
                        source=article.get("source", "Finnhub"),
                        published_at=datetime.fromtimestamp(article.get("datetime", 0)),
                        url=article.get("url", ""),
                        categories=article.get("category", "general").split(","),
                    ))
                except Exception:
                    pass
        return items

    async def get_economic_calendar(self) -> List[Dict]:
        if not self.api_key:
            return []
        url = f"{self.BASE_URL}/calendar/economic"
        now = datetime.now()
        params = {
            "from": now.strftime("%Y-%m-%d"),
            "to": (now + timedelta(days=7)).strftime("%Y-%m-%d"),
            "token": self.api_key,
        }
        data = await self.fetch(url, params)
        return data.get("economicCalendar", []) if isinstance(data, dict) else []


class RedditSentimentCollector(BaseCollector):
    """Reddit public JSON API: hot posts from finance subreddits"""

    SUBREDDITS = ["wallstreetbets", "CryptoCurrency", "stocks", "investing"]

    async def get_posts(self, subreddit: str, limit: int = 15) -> List[Dict]:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json"
        params = {"limit": limit, "raw_json": 1}
        headers = {"User-Agent": "EconIntelAgent/2.0"}
        data = await self.fetch(url, params, headers)
        posts = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            posts.append({
                "title": d.get("title", ""),
                "score": d.get("score", 0),
                "ups": d.get("ups", 0),
                "num_comments": d.get("num_comments", 0),
                "subreddit": subreddit,
                "created_utc": d.get("created_utc", 0),
                "upvote_ratio": d.get("upvote_ratio", 0),
            })
        return posts

    async def get_all_posts(self) -> Dict[str, List[Dict]]:
        results = {}
        for sub in self.SUBREDDITS:
            try:
                results[sub] = await self.get_posts(sub)
            except Exception as e:
                logger.debug(f"Reddit r/{sub}: {e}")
                results[sub] = []
        return results


class GDELTCollector(BaseCollector):
    """GDELT Project: global news articles and tone analysis (no API key)"""

    BASE_URL = "https://api.gdeltproject.org/api/v2"

    async def get_articles(self, query: str = "economy finance market", limit: int = 25) -> List[Dict]:
        url = f"{self.BASE_URL}/doc/doc"
        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": limit,
            "format": "json",
            "sort": "datedesc",
        }
        data = await self.fetch(url, params)
        articles = data.get("articles", [])
        return [{
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source": a.get("domain", ""),
            "published_at": a.get("seendate", ""),
            "tone": a.get("tone", 0),
            "language": a.get("language", "English"),
        } for a in articles]

    async def get_tone_timeline(self, query: str = "economy", hours: int = 24) -> List[Dict]:
        url = f"{self.BASE_URL}/doc/doc"
        params = {
            "query": query,
            "mode": "timelinetone",
            "format": "json",
            "timespan": f"{hours}h",
        }
        data = await self.fetch(url, params)
        return data.get("timeline", []) if isinstance(data, dict) else []


class EconomicCalendarCollector(BaseCollector):
    """Economic calendar events from Finnhub + manual high-impact events"""

    MANUAL_HIGH_IMPACT = [
        {"event": "FOMC Rate Decision", "frequency": "6 weeks", "impact": "high"},
        {"event": "US CPI Release", "frequency": "monthly", "impact": "high"},
        {"event": "US Non-Farm Payrolls", "frequency": "monthly", "impact": "high"},
        {"event": "ECB Rate Decision", "frequency": "6 weeks", "impact": "high"},
        {"event": "US GDP (Advance)", "frequency": "quarterly", "impact": "high"},
    ]

    async def get_events(self, finnhub_key: Optional[str] = None) -> List[Dict]:
        events = []
        # Try Finnhub first
        if finnhub_key:
            try:
                fh = FinnhubCollector(finnhub_key)
                fh.session = self.session
                events = await fh.get_economic_calendar()
            except Exception as e:
                logger.debug(f"Finnhub calendar: {e}")

        # Always include manual high-impact event types as reference
        if not events:
            events = [{"event": e["event"], "impact": e["impact"], "source": "manual"}
                      for e in self.MANUAL_HIGH_IMPACT]
        return events


class NewsCollector(BaseCollector):
    """Collects financial news from multiple sources"""

    FINANCE_KEYWORDS = [
        "federal reserve", "ecb", "interest rates", "inflation",
        "gdp", "unemployment", "trade war", "tariff", "sanctions",
        "bankruptcy", "merger", "acquisition", "earnings",
        "oil", "gold", "bitcoin", "crypto", "bond yields"
    ]

    async def get_newsapi_news(self, api_key: str, query: str = "finance") -> List[NewsItem]:
        if not api_key:
            return []
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f"({query}) AND ({' OR '.join(self.FINANCE_KEYWORDS)})",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 50,
            "apiKey": api_key,
        }
        data = await self.fetch(url, params)
        items = []
        for article in data.get("articles", []):
            try:
                items.append(NewsItem(
                    title=article.get("title", ""),
                    description=article.get("description", ""),
                    source=article.get("source", {}).get("name", "Unknown"),
                    published_at=datetime.fromisoformat(
                        article.get("publishedAt", "").replace("Z", "+00:00")
                    ),
                    url=article.get("url", ""),
                    categories=self._categorize_news(
                        (article.get("title", "") or "") + " " + (article.get("description", "") or "")
                    ),
                ))
            except Exception as e:
                logger.debug(f"NewsAPI parse error: {e}")
        return items

    def _categorize_news(self, text: str) -> List[str]:
        text_lower = text.lower()
        categories = []
        category_keywords = {
            "monetary_policy": ["fed", "federal reserve", "ecb", "interest rate", "rates"],
            "inflation": ["inflation", "cpi", "ppi", "consumer price"],
            "employment": ["unemployment", "jobs", "nfp", "payroll", "labor"],
            "trade": ["trade", "tariff", "export", "import"],
            "crypto": ["bitcoin", "crypto", "cryptocurrency", "blockchain"],
            "equities": ["stock", "equity", "shares", "market", "s&p", "nasdaq"],
            "bonds": ["bond", "treasury", "yield", "debt"],
            "commodities": ["oil", "gold", "commodity", "crude", "gas"],
            "geopolitics": ["war", "sanctions", "election", "brexit", "tension"],
        }
        for category, keywords in category_keywords.items():
            if any(kw in text_lower for kw in keywords):
                categories.append(category)
        return categories if categories else ["general"]


# ── Data Aggregator ──────────────────────────────────────────────

class DataAggregator:
    """Aggregates data from all collectors, config-driven enable/disable"""

    def __init__(self, config: Dict):
        self.config = config
        self.data_sources = config.get("data_sources", {})

    def _is_enabled(self, source: str, default: bool = False) -> bool:
        return self.data_sources.get(source, {}).get("enabled", default)

    def _get_key(self, env_var: str, config_key: str = "") -> str:
        key = os.getenv(env_var, "")
        if not key and config_key:
            key = self.data_sources.get(config_key, {}).get("api_key", "")
            if key and key.startswith("${"):
                key = ""
        return key

    async def collect_all(self) -> Dict[str, Any]:
        """Collect all market data from configured sources"""
        logger.info("Starting comprehensive data collection...")

        collected = {
            "timestamp": datetime.now().isoformat(),
            "crypto": {},
            "equities": {"indices": [], "sectors": []},
            "forex": {},
            "bonds": {"yields": []},
            "commodities": {"prices": []},
            "economic_indicators": {},
            "news": [],
            "reddit": {},
            "gdelt": [],
            "economic_events": [],
        }

        # 1. Crypto (CoinGecko — no key needed)
        if self._is_enabled("coingecko", True):
            try:
                async with CryptoCollector() as col:
                    collected["crypto"]["top_coins"] = await col.get_top_coins(50)
                    collected["crypto"]["global"] = await col.get_global_data()
                    collected["crypto"]["trending"] = await col.get_trending()
                logger.info(f"  Crypto: {len(collected['crypto'].get('top_coins', []))} coins")
            except Exception as e:
                logger.error(f"  Crypto collection failed: {e}")

        # 2. Forex (ExchangeRate — no key needed for v4)
        if self._is_enabled("exchangerate", True):
            try:
                async with ForexCollector() as col:
                    collected["forex"]["usd_rates"] = await col.get_rates("USD")
                    collected["forex"]["eur_rates"] = await col.get_rates("EUR")
                logger.info("  Forex: USD + EUR rates")
            except Exception as e:
                logger.error(f"  Forex collection failed: {e}")

        # 3. Equities (yfinance — no key needed)
        if self._is_enabled("yfinance", True):
            try:
                col = EquityCollector()
                collected["equities"]["indices"] = col.get_market_summary()
                logger.info(f"  Equities: {len(collected['equities']['indices'])} symbols")
            except Exception as e:
                logger.error(f"  Equities collection failed: {e}")

        # 4. FRED indicators + Treasury yields + Commodities
        fred_key = self._get_key("FRED_API_KEY")
        if fred_key and self._is_enabled("fred", True):
            try:
                async with FREDCollector(fred_key) as col:
                    collected["economic_indicators"] = await col.get_all_indicators()
                logger.info(f"  FRED: {len(collected['economic_indicators'])} indicators")
            except Exception as e:
                logger.error(f"  FRED collection failed: {e}")

            try:
                async with TreasuryYieldCollector(fred_key) as col:
                    collected["bonds"]["yields"] = await col.get_yield_curve()
                logger.info(f"  Yields: {len(collected['bonds']['yields'])} maturities")
            except Exception as e:
                logger.error(f"  Treasury yields failed: {e}")

            try:
                async with CommodityCollector(fred_key) as col:
                    collected["commodities"]["prices"] = await col.get_prices()
                logger.info(f"  Commodities: {len(collected['commodities']['prices'])} items")
            except Exception as e:
                logger.error(f"  Commodities failed: {e}")

        # 5. Alpha Vantage (stock quotes)
        av_key = self._get_key("ALPHA_VANTAGE_KEY", "alpha_vantage")
        if av_key and self._is_enabled("alpha_vantage", False):
            try:
                async with AlphaVantageCollector(av_key) as col:
                    movers = await col.get_top_movers()
                    collected["equities"]["top_movers"] = movers
                logger.info("  Alpha Vantage: top movers")
            except Exception as e:
                logger.error(f"  Alpha Vantage failed: {e}")

        # 6. Finnhub (news + calendar)
        fh_key = self._get_key("FINNHUB_KEY")
        if fh_key and self._is_enabled("finnhub", True):
            try:
                async with FinnhubCollector(fh_key) as col:
                    fh_news = await col.get_market_news()
                    collected["news"].extend(fh_news)
                    cal = await col.get_economic_calendar()
                    collected["economic_events"].extend(cal)
                logger.info(f"  Finnhub: {len(fh_news)} news, {len(cal)} calendar events")
            except Exception as e:
                logger.error(f"  Finnhub failed: {e}")

        # 7. NewsAPI
        newsapi_key = self._get_key("NEWSAPI_KEY", "newsapi")
        if newsapi_key and self._is_enabled("newsapi", False):
            try:
                async with NewsCollector() as col:
                    na_news = await col.get_newsapi_news(newsapi_key)
                    collected["news"].extend(na_news)
                logger.info(f"  NewsAPI: {len(na_news)} articles")
            except Exception as e:
                logger.error(f"  NewsAPI failed: {e}")

        # 8. Reddit (no key needed)
        if self._is_enabled("reddit", True):
            try:
                async with RedditSentimentCollector() as col:
                    collected["reddit"] = await col.get_all_posts()
                total = sum(len(v) for v in collected["reddit"].values())
                logger.info(f"  Reddit: {total} posts from {len(collected['reddit'])} subs")
            except Exception as e:
                logger.error(f"  Reddit failed: {e}")

        # 9. GDELT (no key needed)
        if self._is_enabled("gdelt", True):
            try:
                async with GDELTCollector() as col:
                    collected["gdelt"] = await col.get_articles()
                logger.info(f"  GDELT: {len(collected['gdelt'])} articles")
            except Exception as e:
                logger.error(f"  GDELT failed: {e}")

        # 10. Economic Calendar
        if self._is_enabled("economic_calendar", True):
            try:
                async with EconomicCalendarCollector() as col:
                    cal = await col.get_events(fh_key)
                    collected["economic_events"].extend(cal)
                logger.info(f"  Calendar: {len(collected['economic_events'])} events total")
            except Exception as e:
                logger.error(f"  Calendar failed: {e}")

        logger.info("Data collection complete")
        return collected

    def serialize_for_analysis(self, data: Dict) -> str:
        """Convert collected data to JSON string for LLM analysis"""
        def convert(obj):
            if isinstance(obj, (MarketData, NewsItem, EconomicEvent)):
                result = {}
                for key, value in obj.__dict__.items():
                    result[key] = value.isoformat() if isinstance(value, datetime) else value
                return result
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            return obj

        return json.dumps(convert(data), indent=2, default=str)


if __name__ == "__main__":
    async def test():
        aggregator = DataAggregator({
            "data_sources": {
                "coingecko": {"enabled": True},
                "exchangerate": {"enabled": True},
                "yfinance": {"enabled": True},
                "reddit": {"enabled": True},
                "gdelt": {"enabled": True},
            }
        })
        data = await aggregator.collect_all()
        print(f"Crypto: {len(data.get('crypto', {}).get('top_coins', []))}")
        print(f"News: {len(data.get('news', []))}")
        print(f"Reddit: {sum(len(v) for v in data.get('reddit', {}).values())}")
        print(f"GDELT: {len(data.get('gdelt', []))}")

    asyncio.run(test())
