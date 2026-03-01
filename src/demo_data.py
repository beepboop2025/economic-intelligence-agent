"""
Demo data generator for Economic Intelligence Agent v2.0
Provides realistic market data across all asset classes when APIs are unavailable
"""

from datetime import datetime, timedelta
from typing import Dict, List
from data_collectors import MarketData, NewsItem


def generate_demo_crypto_data() -> List[MarketData]:
    """Generate realistic cryptocurrency market data"""
    coins = [
        ("BTC", "Bitcoin", 85000.50, 2.3, 1680000000000),
        ("ETH", "Ethereum", 2350.75, 1.8, 282000000000),
        ("BNB", "BNB", 625.30, -0.5, 92000000000),
        ("SOL", "Solana", 145.20, 5.2, 68000000000),
        ("XRP", "XRP", 2.85, -1.2, 165000000000),
        ("ADA", "Cardano", 0.95, 0.8, 33000000000),
        ("DOGE", "Dogecoin", 0.28, 12.5, 41000000000),
        ("AVAX", "Avalanche", 26.40, 3.1, 10700000000),
        ("DOT", "Polkadot", 4.85, -2.1, 7500000000),
        ("MATIC", "Polygon", 0.42, 1.5, 4200000000),
    ]

    market_data = []
    for symbol, name, price, change_24h, mcap in coins:
        volume = mcap * 0.02
        market_data.append(MarketData(
            asset_class="crypto",
            symbol=symbol,
            name=name,
            price=price,
            change_24h=price * change_24h / 100,
            change_percent_24h=change_24h,
            volume=volume,
            market_cap=mcap,
            timestamp=datetime.now(),
            additional_data={
                "ath": price * 1.4 if change_24h > 0 else price * 1.2,
                "ath_change_percent": -12.5,
                "circulating_supply": mcap / price if price > 0 else 0,
            },
        ))
    return market_data


def generate_demo_global_crypto() -> Dict:
    return {
        "data": {
            "active_cryptocurrencies": 10250,
            "markets": 42000,
            "total_market_cap": {"usd": 2850000000000},
            "total_volume": {"usd": 98000000000},
            "market_cap_percentage": {"btc": 58.5, "eth": 9.8, "bnb": 3.2, "sol": 2.4, "xrp": 5.8},
            "market_cap_change_percentage_24h_usd": 2.1,
        }
    }


def generate_demo_forex_data() -> Dict:
    return {
        "base": "USD",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "rates": {
            "EUR": 0.9235, "JPY": 149.85, "GBP": 0.7850, "AUD": 1.5420,
            "CAD": 1.3580, "CHF": 0.8820, "CNY": 7.1850, "INR": 86.75,
            "BRL": 5.1250, "MXN": 17.35,
        },
    }


def generate_demo_news() -> List[NewsItem]:
    return [
        NewsItem(
            title="Fed Chair Powell Signals Patience on Rate Cuts Amid Inflation Concerns",
            description="Federal Reserve Chairman Jerome Powell indicated the central bank will remain cautious about cutting interest rates, citing persistent inflation pressures and a strong labor market.",
            source="Reuters",
            published_at=datetime.now() - timedelta(hours=2),
            url="https://example.com/news/1",
            categories=["monetary_policy", "inflation"],
        ),
        NewsItem(
            title="Bitcoin ETF Inflows Reach Record $2.5B in February",
            description="Spot Bitcoin ETFs have seen unprecedented inflows, with BlackRock's IBIT leading the pack.",
            source="CoinDesk",
            published_at=datetime.now() - timedelta(hours=4),
            url="https://example.com/news/2",
            categories=["crypto"],
        ),
        NewsItem(
            title="ECB Hints at June Rate Cut as Eurozone Inflation Cools",
            description="European Central Bank officials have signaled growing confidence that inflation is returning to target.",
            source="Financial Times",
            published_at=datetime.now() - timedelta(hours=6),
            url="https://example.com/news/3",
            categories=["monetary_policy", "inflation"],
        ),
        NewsItem(
            title="Commercial Real Estate Concerns Mount as $1.5T Debt Looms",
            description="Analysts warn of potential stress in the commercial real estate sector.",
            source="Bloomberg",
            published_at=datetime.now() - timedelta(hours=8),
            url="https://example.com/news/4",
            categories=["debt", "real_estate"],
        ),
        NewsItem(
            title="NVIDIA Earnings Beat Expectations, AI Demand Remains Strong",
            description="NVIDIA reported quarterly earnings that exceeded Wall Street expectations.",
            source="CNBC",
            published_at=datetime.now() - timedelta(hours=10),
            url="https://example.com/news/5",
            categories=["equities", "technology"],
        ),
        NewsItem(
            title="Oil Prices Surge on Geopolitical Tensions in Middle East",
            description="Crude oil prices rose more than 3% as renewed tensions raised supply concerns.",
            source="Bloomberg",
            published_at=datetime.now() - timedelta(hours=12),
            url="https://example.com/news/6",
            categories=["commodities", "geopolitics"],
        ),
        NewsItem(
            title="Treasury Yields Climb as Investors Reassess Rate Cut Timeline",
            description="The 10-year Treasury yield rose to 4.25% as stronger-than-expected data pushed back cut expectations.",
            source="WSJ",
            published_at=datetime.now() - timedelta(hours=14),
            url="https://example.com/news/7",
            categories=["bonds", "monetary_policy"],
        ),
        NewsItem(
            title="China Announces New Stimulus Measures to Support Property Sector",
            description="Chinese authorities unveiled fresh measures to support the struggling real estate sector.",
            source="Reuters",
            published_at=datetime.now() - timedelta(hours=16),
            url="https://example.com/news/8",
            categories=["geopolitics", "real_estate"],
        ),
    ]


def generate_demo_equity_indices() -> List[MarketData]:
    indices = [
        ("SPX", "S&P 500", 5850.25, 0.45),
        ("DJI", "Dow Jones", 43850.75, 0.32),
        ("IXIC", "NASDAQ", 18350.50, 0.78),
        ("FTSE", "FTSE 100", 7680.25, -0.15),
        ("DAX", "DAX 40", 17350.80, 0.62),
        ("N225", "Nikkei 225", 39250.30, 1.15),
        ("HSI", "Hang Seng", 16850.45, -0.85),
    ]
    return [
        MarketData(
            asset_class="equities", symbol=sym, name=name, price=price,
            change_24h=price * change / 100, change_percent_24h=change, timestamp=datetime.now(),
        )
        for sym, name, price, change in indices
    ]


def generate_demo_bond_yields() -> List[MarketData]:
    bonds = [
        ("US3M", "US 3-Month Treasury", 5.25, -0.01),
        ("US6M", "US 6-Month Treasury", 5.10, -0.02),
        ("US1Y", "US 1-Year Treasury", 4.85, 0.02),
        ("US2Y", "US 2-Year Treasury", 4.45, 0.05),
        ("US5Y", "US 5-Year Treasury", 4.15, 0.04),
        ("US7Y", "US 7-Year Treasury", 4.20, 0.05),
        ("US10Y", "US 10-Year Treasury", 4.25, 0.08),
        ("US20Y", "US 20-Year Treasury", 4.45, 0.06),
        ("US30Y", "US 30-Year Treasury", 4.45, 0.06),
    ]
    return [
        MarketData(
            asset_class="bonds", symbol=sym, name=name, price=price,
            change_24h=change, change_percent_24h=change * 20, timestamp=datetime.now(),
        )
        for sym, name, price, change in bonds
    ]


def generate_demo_commodities() -> List[MarketData]:
    commodities = [
        ("XAU", "Gold", 2850.50, 0.85),
        ("XAG", "Silver", 32.25, 1.45),
        ("CL", "WTI Crude Oil", 78.50, 2.35),
        ("NG", "Natural Gas", 2.85, -1.25),
        ("HG", "Copper", 4.25, 0.65),
    ]
    return [
        MarketData(
            asset_class="commodities", symbol=sym, name=name, price=price,
            change_24h=price * change / 100, change_percent_24h=change, timestamp=datetime.now(),
        )
        for sym, name, price, change in commodities
    ]


def generate_demo_economic_indicators() -> Dict:
    """Generate demo FRED-style economic indicators"""
    return {
        "GDP": {"name": "Gross Domestic Product", "value": 27.96, "date": "2024-Q4"},
        "CPIAUCSL": {"name": "Consumer Price Index", "value": 314.2, "date": "2024-12"},
        "UNRATE": {"name": "Unemployment Rate", "value": 3.7, "date": "2024-12"},
        "FEDFUNDS": {"name": "Federal Funds Rate", "value": 5.33, "date": "2024-12"},
        "M2SL": {"name": "M2 Money Supply", "value": 21050.2, "date": "2024-11"},
        "PCEPI": {"name": "PCE Price Index", "value": 123.8, "date": "2024-11"},
    }


def generate_demo_reddit_posts() -> Dict[str, List[Dict]]:
    """Generate demo Reddit posts for sentiment analysis"""
    return {
        "wallstreetbets": [
            {"title": "NVDA to the moon! AI demand unstoppable 🚀", "score": 4500, "num_comments": 890, "upvote_ratio": 0.92},
            {"title": "Rate cuts delayed again... market is overvalued", "score": 2100, "num_comments": 550, "upvote_ratio": 0.78},
            {"title": "CRE collapse incoming, short regional banks", "score": 1800, "num_comments": 430, "upvote_ratio": 0.71},
            {"title": "SPY calls printing, bears in shambles", "score": 3200, "num_comments": 670, "upvote_ratio": 0.85},
        ],
        "CryptoCurrency": [
            {"title": "BTC ETF inflows massive, institutions are loading", "score": 5200, "num_comments": 1200, "upvote_ratio": 0.94},
            {"title": "ETH looking weak, BTC dominance crushing alts", "score": 1500, "num_comments": 380, "upvote_ratio": 0.65},
            {"title": "Halving approaching - historical data says rally coming", "score": 3800, "num_comments": 920, "upvote_ratio": 0.88},
        ],
        "stocks": [
            {"title": "Magnificent 7 carrying the entire market", "score": 2800, "num_comments": 510, "upvote_ratio": 0.80},
            {"title": "Small caps finally getting a bid, rotation underway", "score": 1200, "num_comments": 290, "upvote_ratio": 0.75},
        ],
        "investing": [
            {"title": "60/40 portfolio working again as bond-equity correlation normalizes", "score": 900, "num_comments": 180, "upvote_ratio": 0.82},
            {"title": "Gold and BTC both up - inflation hedge thesis alive", "score": 1100, "num_comments": 220, "upvote_ratio": 0.79},
        ],
    }


def generate_demo_gdelt_articles() -> List[Dict]:
    """Generate demo GDELT-style articles"""
    return [
        {"title": "Global Markets Rally on Rate Cut Hopes", "source": "reuters.com", "tone": 2.5, "published_at": datetime.now().isoformat()},
        {"title": "Oil Prices Surge Amid Middle East Tensions", "source": "bloomberg.com", "tone": -1.8, "published_at": datetime.now().isoformat()},
        {"title": "China Economy Shows Signs of Stabilization", "source": "ft.com", "tone": 1.2, "published_at": datetime.now().isoformat()},
        {"title": "European Banks Face CRE Exposure Concerns", "source": "wsj.com", "tone": -2.1, "published_at": datetime.now().isoformat()},
        {"title": "Tech Sector Earnings Beat Expectations", "source": "cnbc.com", "tone": 3.0, "published_at": datetime.now().isoformat()},
    ]


def generate_all_demo_data() -> Dict:
    """Generate complete demo dataset across all asset classes"""
    return {
        "timestamp": datetime.now().isoformat(),
        "demo_mode": True,
        "crypto": {
            "top_coins": generate_demo_crypto_data(),
            "global": generate_demo_global_crypto(),
            "trending": {
                "coins": [
                    {"item": {"name": "Dogecoin", "symbol": "DOGE"}},
                    {"item": {"name": "Pepe", "symbol": "PEPE"}},
                    {"item": {"name": "Bonk", "symbol": "BONK"}},
                ]
            },
        },
        "equities": {
            "indices": generate_demo_equity_indices(),
            "sectors": [],
        },
        "forex": {
            "usd_rates": generate_demo_forex_data(),
            "eur_rates": {"base": "EUR", "rates": {"USD": 1.0830}},
        },
        "bonds": {
            "yields": generate_demo_bond_yields(),
        },
        "commodities": {
            "prices": generate_demo_commodities(),
        },
        "economic_indicators": generate_demo_economic_indicators(),
        "news": generate_demo_news(),
        "reddit": generate_demo_reddit_posts(),
        "gdelt": generate_demo_gdelt_articles(),
        "economic_events": [
            {
                "title": "US Non-Farm Payrolls",
                "date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
                "impact": "high",
                "forecast": "185K",
                "previous": "353K",
            },
            {
                "title": "Fed Chair Powell Testimony",
                "date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                "impact": "high",
            },
            {
                "title": "ECB Interest Rate Decision",
                "date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
                "impact": "high",
                "forecast": "4.00%",
                "previous": "4.00%",
            },
            {
                "title": "US CPI (YoY)",
                "date": (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%d"),
                "impact": "high",
                "forecast": "3.1%",
                "previous": "3.4%",
            },
            {
                "event": "BOJ Rate Decision",
                "date": (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d"),
                "impact": "high",
            },
        ],
    }
