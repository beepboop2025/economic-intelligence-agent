# Economic Intelligence Agent

**Automated economic data collection, quantitative analysis, and risk assessment -- delivered as actionable intelligence reports.**

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Data Sources](https://img.shields.io/badge/Data_Sources-9-orange.svg)

---

## Features

- **Multi-source data collection** -- Async ingestion from 9 economic and financial data APIs with built-in caching and token-bucket rate limiting
- **Quantitative analysis engine** -- RSI, MACD, Bollinger Bands, yield curve analysis (3M-30Y), and market regime detection (bull/bear/sideways/transition)
- **Risk assessment** -- Value at Risk (parametric, historical, CVaR), max drawdown tracking, Sharpe/Sortino/Calmar ratios, and four stress-test scenarios (GFC 2008, COVID 2020, rate shock, oil shock)
- **Sentiment analysis** -- VADER NLP with 24+ financial domain terms, source-weighted scoring, and a five-component Fear and Greed Index
- **Alert engine** -- Seven alert types (price threshold, RSI signal, volatility spike, correlation breakdown, economic calendar, anomaly, sentiment shift) with SHA-256 deduplication
- **Report generation** -- 13-section intelligence reports in Markdown, HTML, or JSON with ASCII sparklines and heatmaps
- **Resilient architecture** -- Circuit breaker, retry with exponential backoff, TTL cache, and graceful degradation across all data sources
- **SQLite storage** -- WAL-mode database with parameterized queries, six normalized tables, and 90-day automatic retention cleanup

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.9+ |
| Async HTTP | aiohttp, requests |
| Market Data | yfinance |
| Sentiment | vaderSentiment (VADER NLP) |
| Numerical | NumPy |
| Storage | SQLite (WAL mode, parameterized queries) |
| LLM Integration | OpenRouter / OpenAI / Anthropic / Ollama |
| Terminal UI | Rich |
| Resilience | TTL cache, token-bucket rate limiter, circuit breaker |

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip

### Installation

```bash
git clone https://github.com/beepboop2025/economic-intelligence-agent.git
cd economic-intelligence-agent
pip install -r requirements.txt
```

### Configuration

API keys can be configured via a `.env` file in the project root or through the interactive setup script:

```bash
python setup_keys.py
```

| Variable | Service | Required |
|----------|---------|:--------:|
| `FRED_API_KEY` | FRED economic indicators | No |
| `FINNHUB_KEY` | Market news and economic calendar | No |
| `NEWSAPI_KEY` | Financial news articles | No |
| `ALPHA_VANTAGE_KEY` | Stock quotes, top gainers/losers | No |
| `OPENROUTER_KEY` | LLM-powered macro analysis | No |
| `OPENAI_API_KEY` | Alternative LLM provider | No |
| `ANTHROPIC_API_KEY` | Alternative LLM provider | No |

All data sources function in demo mode without API keys. Keys are optional and enhance data quality and coverage.

Additional settings (LLM model, alert thresholds, retention period) are managed in `config/settings.yaml`.

### Usage

```bash
cd src

# Full analysis with live data
python main.py

# Demo mode (no API keys required)
python main.py --demo

# Output formats
python main.py --demo --format html
python main.py --demo --format json

# Selective analysis
python main.py --demo --quant
python main.py --demo --risk

# Compare with previous run
python main.py --demo --compare

# Continuous monitoring
python main.py --monitor --interval 6

# Check API key status
python main.py --api-keys
```

---

## Data Sources

| Source | Data Provided | Auth Required | Rate Limit |
|--------|---------------|:-------------:|------------|
| FRED | GDP, CPI, unemployment, federal funds rate, yield curve (3M-30Y) | Optional | 120 req/min |
| Finnhub | Market news, economic calendar events | Optional | 60 req/min |
| Alpha Vantage | Stock quotes, top gainers/losers | Optional | 25 req/day |
| NewsAPI | Financial news articles | Optional | 100 req/day |
| CoinGecko | 50+ cryptocurrency prices, global market metrics | No | Unlimited |
| yfinance | 10 global indices, 11 sector ETFs | No | Unlimited |
| ExchangeRate-API | 160+ currency pairs | No | Unlimited |
| Reddit | Sentiment from r/wallstreetbets, r/cryptocurrency, r/stocks, r/investing | No | Unlimited |
| GDELT | Global news event data with tone analysis | No | Unlimited |

---

## Architecture

```
Data Sources (9)
    |
    v
Async Collectors (aiohttp + rate limiting + circuit breaker)
    |
    v
SQLite Storage (WAL mode, parameterized queries, 6 tables)
    |
    +---> Quantitative Engine (RSI, MACD, Bollinger, yield curve, regime)
    +---> Sentiment Engine (VADER NLP, Fear & Greed Index)
    +---> Risk Engine (VaR, stress tests, drawdown, ratios)
    |
    v
Alert Engine (7 types, SHA-256 dedup)
    |
    v
Report Generator (Markdown / HTML / JSON)
```

---

## License

This project is licensed under the MIT License.

---

*For informational and educational purposes only. Not financial advice.*
