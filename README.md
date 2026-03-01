# Global Economic Intelligence Agent v2.0

An enterprise-grade, AI-powered market intelligence platform that collects data from 9 sources, runs quantitative/risk/sentiment analysis, generates alerts, and produces professional reports across all major asset classes.

```
Collect (9 sources) → Store (SQLite) → Analyze (Quant + Risk + Sentiment + LLM) → Alert → Report (MD/HTML/JSON)
```

## What It Does

- Pulls live data from **9 sources** — crypto, equities, bonds, forex, commodities, economic indicators, news, Reddit, and GDELT
- Stores everything in **SQLite** with WAL mode for concurrent read/write
- Runs **quantitative analysis** — RSI, MACD, Bollinger Bands, yield curve, regime detection
- Computes **risk metrics** — VaR, drawdown, Sharpe/Sortino, stress tests (GFC 2008, COVID, rate shock)
- Analyzes **sentiment** — VADER NLP on news, source-weighted scores, Reddit crowd sentiment, Fear/Greed index
- Sends data to an **LLM** (Claude, GPT, Ollama) for macro analysis and trade ideas
- Evaluates **7 alert types** — price thresholds, technical signals, volatility spikes, correlation breakdowns, economic calendar, anomalies, sentiment shifts
- Generates reports in **Markdown, HTML, or JSON** with ASCII sparklines and historical comparison

## Quick Start

```bash
# Clone and install
git clone https://github.com/beepboop2025/economic-intelligence-agent.git
cd economic-intelligence-agent
pip install -r requirements.txt

# Run with demo data (no API keys needed)
cd src
python main.py --demo
```

That's it. The demo runs the full 9-step pipeline with realistic mock data and produces a report in `reports/`.

## Demo Output

```
 GLOBAL ECONOMIC INTELLIGENCE AGENT v2.0

[1/9] Collecting market data...
  Crypto: 10 | Equities: 7 | Bonds: 9 | News: 8
[2/9] Persisting to database...
  Stored 31 price records
[3/9] Running quantitative analysis...
  Yield curve 2Y-10Y spread: -0.2% (INVERTED)
[4/9] Analyzing sentiment...
  Fear/Greed Index: 59/100 (neutral)
[5/9] Computing risk metrics...
  Overall risk level: HIGH
[6/9] LLM macro analysis...
  Market Tone: MIXED
[7/9] Evaluating alert rules...
  🟠 [HIGH] DOGE surged 12.5% in 24h
  🟡 [MEDIUM] BTC: bullish technical signal
  🟡 [MEDIUM] Upcoming high-impact event: US Non-Farm Payrolls
  9 new alerts triggered
[8/9] Generating markdown report...
  Report saved: reports/economic_report_20260302_0123.md
[9/9] Archiving analysis...
  Analysis archived to database

 ANALYSIS COMPLETE
```

## API Keys

**No keys required** for demo mode or these free data sources: CoinGecko, ExchangeRate, yfinance, Reddit, GDELT.

For live LLM analysis, set one of these:

```bash
# Option 1: OpenRouter (recommended — free tier, access to multiple models)
export OPENROUTER_KEY="your_key"    # https://openrouter.ai/

# Option 2: OpenAI
export OPENAI_API_KEY="your_key"    # https://platform.openai.com/

# Option 3: Anthropic
export ANTHROPIC_API_KEY="your_key" # https://console.anthropic.com/
```

Optional data source keys (all have free tiers):

```bash
export FRED_API_KEY="your_key"      # https://fred.stlouisfed.org/docs/api/api_key.html
export FINNHUB_KEY="your_key"       # https://finnhub.io/register
export NEWSAPI_KEY="your_key"       # https://newsapi.org/register
export ALPHA_VANTAGE_KEY="your_key" # https://www.alphavantage.co/support/#api-key
```

Or copy `.env.example` to `.env` and fill in your keys.

## CLI Usage

```bash
cd src

# Full analysis with live data
python main.py

# Demo mode (no API keys)
python main.py --demo

# HTML report
python main.py --demo --format html

# JSON report (machine-readable)
python main.py --demo --format json

# Show alerts
python main.py --demo --alerts

# Quant analysis only (skip LLM/sentiment/risk)
python main.py --demo --quant

# Risk analysis only
python main.py --demo --risk

# Skip LLM, use mock analysis
python main.py --no-llm

# Compare with previous run
python main.py --demo --compare

# Continuous monitoring every 6 hours
python main.py --monitor --interval 6

# Check API key status
python main.py --api-keys

# Save raw collected data
python main.py --save-data
```

## Architecture

```
src/
├── main.py                 # CLI orchestrator — 9-step pipeline
├── config_loader.py        # YAML + .env config with validation
├── data_collectors.py      # 9 data collectors
│   ├── CryptoCollector          CoinGecko (free)
│   ├── EquityCollector          yfinance — 10 indices + 11 sector ETFs
│   ├── ForexCollector           ExchangeRate API (free)
│   ├── FREDCollector            GDP, CPI, unemployment, fed funds, M2, yields
│   ├── TreasuryYieldCollector   Full yield curve (3M→30Y, 10 maturities)
│   ├── CommodityCollector       Gold, WTI, Brent, Nat Gas, Copper via FRED
│   ├── FinnhubCollector         Market news + economic calendar
│   ├── RedditSentimentCollector Hot posts from WSB, crypto, stocks, investing
│   ├── GDELTCollector           Global news articles + tone timeline
│   ├── AlphaVantageCollector    Stock quotes, top gainers/losers
│   ├── EconomicCalendarCollector Finnhub + manual high-impact events
│   └── NewsCollector            NewsAPI with keyword categorization
├── analysis_engine.py      # LLM client (OpenRouter/OpenAI/Anthropic/Ollama)
├── quant_engine.py         # Technical analysis + yield curve + regime detection
│   ├── TechnicalAnalysis        RSI, MACD, Bollinger, SMA, EMA, ATR
│   ├── CorrelationAnalyzer      Pairwise correlations, divergence detection
│   ├── MarketRegimeDetector     Bull/bear/sideways/transition
│   └── YieldCurveAnalyzer       Spread, inversion, steepness, term premium
├── risk_engine.py          # Risk analytics
│   ├── ValueAtRisk              Parametric, historical, conditional VaR
│   ├── DrawdownAnalyzer         Max drawdown, current drawdown, series
│   ├── PerformanceMetrics       Sharpe, Sortino, Calmar, Information ratio
│   └── StressTest               GFC 2008, COVID 2020, rate shock, oil shock
├── sentiment_engine.py     # NLP sentiment
│   ├── VADERAnalyzer            VADER + financial term boosting
│   ├── SourceWeighter           Reuters/Bloomberg > CNBC > Reddit
│   ├── CrowdSentiment           Reddit engagement-weighted sentiment
│   └── FearGreedIndex           5-component composite (0–100)
├── alert_engine.py         # Alerting system
│   ├── AlertRuleEngine          7 alert types
│   └── AlertNotifier            Console, file log, webhook, email
├── report_generator.py     # Multi-format reports
│   └── EnhancedReportGenerator  MD/HTML/JSON, sparklines, heatmaps
├── storage.py              # SQLite persistence (WAL mode)
│   └── DataStore                6 tables, schema versioning, retention cleanup
├── resilience.py           # Infrastructure
│   ├── TTLCache                 LRU + per-key TTL
│   ├── RateLimiter              Token bucket (tuned per API)
│   ├── CircuitBreaker           3-state with single probe in half-open
│   └── ResilientFetcher         Facade: cache → rate limit → circuit breaker → retry
├── utils.py                # Formatting, JSON extraction, logging
├── demo.py                 # Demo runner (no API keys)
└── demo_data.py            # Mock data generators for all asset classes
```

## Data Sources

| Source | Data | API Key | Free Tier |
|--------|------|---------|-----------|
| CoinGecko | 50 cryptos, global metrics, trending | No | Unlimited |
| yfinance | 10 global indices, 11 sector ETFs | No | Unlimited |
| ExchangeRate API | Forex rates (USD, EUR bases) | No | Unlimited |
| FRED | GDP, CPI, unemployment, fed funds, M2, PCE, yields | Yes | 120 req/min |
| Finnhub | Market news, economic calendar | Yes | 60 req/min |
| Reddit | Hot posts from WSB, crypto, stocks, investing | No | Public JSON |
| GDELT | Global news articles, tone analysis | No | Unlimited |
| Alpha Vantage | Stock quotes, top movers | Yes | 25 req/day |
| NewsAPI | Financial news with categorization | Yes | 100 req/day |

## Report Sections

Each report includes:

1. **Executive Summary** — Market tone, key theme, risks, opportunities
2. **Market Overview** — Equities, bonds, crypto, forex conditions
3. **Quantitative Metrics** — Yield curve (with sparkline), technical signals, market regime
4. **Risk Metrics** — VaR, stress test table, overall risk level
5. **Sentiment Analysis** — Fear/Greed gauge, news sentiment, Reddit crowd sentiment
6. **Key Events & Catalysts** — Upcoming market movers with impact assessment
7. **Cross-Asset Analysis** — Correlations, divergences, historical context
8. **Risk Assessment** — Systemic risks, tail risks, hedging considerations
9. **Active Alerts** — Color-coded by severity
10. **Outlook** — Immediate, short-term, medium-term forecasts with key levels
11. **Trade Setups** — Actionable ideas with rationale and risk/reward
12. **Raw Data Snapshot** — Price tables for crypto and indices
13. **Historical Comparison** — Diff vs previous analysis (with `--compare`)

## SQLite Database

The agent persists all data to `data/economic_intelligence.db`:

| Table | Contents |
|-------|----------|
| `assets` | Symbol registry (UNIQUE on symbol + asset_class) |
| `price_history` | Price, volume, change, market cap (indexed by asset + timestamp) |
| `economic_indicators` | FRED series values over time |
| `news` | Articles with sentiment scores and categories |
| `alerts` | Triggered alerts with dedup key (UNIQUE) |
| `analysis_history` | Past analyses with market tone, theme, full summary JSON |

Automatic cleanup removes data older than 90 days (configurable via `storage.retention_days`).

## Configuration

Edit `config/settings.yaml` to enable/disable sources, change thresholds, or switch LLM providers:

```yaml
data_sources:
  coingecko:
    enabled: true
  fred:
    enabled: true
  reddit:
    enabled: true

llm:
  provider: "openrouter"           # openrouter, openai, anthropic, ollama
  model: "anthropic/claude-3.5-sonnet"

alerts:
  channels: ["console"]            # console, file, webhook, email
  thresholds:
    price_change_pct: 5.0          # alert on >5% daily moves
    volatility_spike: 3.0          # z-score threshold
    rsi_overbought: 70
    rsi_oversold: 30

storage:
  db_path: "data/economic_intelligence.db"
  retention_days: 90
```

## Local Models (Ollama)

For privacy or offline use:

```bash
# Install Ollama: https://ollama.ai/
ollama pull llama2:13b

# Edit config/settings.yaml:
# llm:
#   provider: "ollama"
#   model: "llama2:13b"

python src/main.py
```

## Requirements

- Python 3.9+
- Core: `aiohttp`, `requests`, `pyyaml`, `python-dateutil`
- Data: `yfinance`
- Analysis: `numpy`, `vaderSentiment`
- UI: `rich`

## Disclaimer

This tool is for **informational and educational purposes only**. It does not constitute financial advice. Always do your own research and consult with financial advisors before making investment decisions.

## License

MIT License — free to use and modify.
