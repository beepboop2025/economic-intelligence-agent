# 🌍 Global Economic Intelligence Agent

An AI-powered market intelligence system that monitors and analyzes global economic events across all major asset classes: **equities, bonds, cryptocurrencies, forex, commodities, and debt markets**.

## ✨ Features

- **📊 Multi-Asset Coverage**: Tracks equities, bonds, crypto, forex, commodities, and debt
- **🔍 Real-time Data**: Aggregates data from multiple financial data sources
- **🧠 AI-Powered Analysis**: Uses LLMs (Claude, GPT, etc.) for sophisticated market analysis
- **📈 Cross-Asset Insights**: Identifies correlations, divergences, and rotation patterns
- **⚠️ Risk Assessment**: Detects systemic and tail risks across markets
- **📄 Professional Reports**: Generates comprehensive markdown reports
- **🔄 Continuous Monitoring**: Can run in scheduled monitoring mode

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ECONOMIC INTELLIGENCE AGENT              │
├─────────────────────────────────────────────────────────────┤
│  Data Collection          Analysis Engine      Report Gen   │
│  ├─ Crypto (CoinGecko)    ├─ LLM Analysis     ├─ Markdown  │
│  ├─ Forex (ExchangeRate)  ├─ Sentiment        ├─ JSON      │
│  ├─ News (NewsAPI)        ├─ Risk Assessment  └─ Console   │
│  ├─ Equities              └─ Cross-Asset                    │
│  └─ Economic Calendar                                       │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Installation

```bash
cd economic-intelligence-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. API Key Setup

You need at least one LLM provider API key:

#### Option A: OpenRouter (Recommended - Free tier available)
```bash
export OPENROUTER_KEY="your_openrouter_key"
```
Get free key: https://openrouter.ai/

#### Option B: OpenAI
```bash
export OPENAI_API_KEY="your_openai_key"
```

#### Option C: Anthropic
```bash
export ANTHROPIC_API_KEY="your_anthropic_key"
```

#### Optional: NewsAPI (for more news sources)
```bash
export NEWSAPI_KEY="your_newsapi_key"
```
Get free key: https://newsapi.org/

### 3. Run Your First Analysis

```bash
python src/main.py
```

## 📖 Usage

### Single Analysis Run
```bash
python src/main.py
```

### Continuous Monitoring (updates every 6 hours)
```bash
python src/main.py --monitor --interval 6
```

### Save Raw Data
```bash
python src/main.py --save-data
```

### Check API Key Status
```bash
python src/main.py --api-keys
```

### Custom Config
```bash
python src/main.py --config my_config.yaml
```

## ⚙️ Configuration

Edit `config/settings.yaml` to customize:

```yaml
# LLM Provider
llm:
  provider: "openrouter"  # Options: openrouter, openai, anthropic, ollama
  model: "anthropic/claude-3.5-sonnet"
  temperature: 0.3

# Markets to analyze
analysis:
  markets:
    - equities
    - bonds
    - crypto
    - forex
    - commodities
    - debt

# Data sources
data_sources:
  coingecko:
    enabled: true  # Free, no API key needed
  newsapi:
    enabled: true  # Requires API key
```

## 📊 Sample Output

```
╔═══════════════════════════════════════════════════════════╗
║              🌍 ECONOMIC INTELLIGENCE AGENT               ║
╚═══════════════════════════════════════════════════════════╝

📡 Phase 1: Collecting Market Data...
   ✅ Cryptocurrencies: 50 coins
   ✅ Forex pairs: Multiple USD/EUR rates
   ✅ News articles: 25 items

🧠 Phase 2: AI Analysis...
   ✅ Market Tone: MIXED
   ✅ Key Theme: Central bank divergence driving volatility...
   ✅ Risks identified: 4
   ✅ Trade setups: 3

📄 Phase 3: Generating Report...
   ✅ Report saved: reports/economic_report_20240301_1430.md

📊 EXECUTIVE SUMMARY:
Market Tone: MIXED

Key Theme:
  Fed's hawkish stance contrasts with ECB dovish signals...

⚠️  Key Risks:
  • Commercial real estate refinancing cliff
  • Treasury market liquidity concerns
```

## 📁 Project Structure

```
economic-intelligence-agent/
├── config/
│   └── settings.yaml          # Configuration
├── src/
│   ├── __init__.py
│   ├── main.py                # CLI and orchestrator
│   ├── data_collectors.py     # Market data collection
│   └── analysis_engine.py     # LLM analysis & reports
├── data/                      # Raw data storage
├── reports/                   # Generated reports
├── requirements.txt
└── README.md
```

## 🔌 Data Sources

| Source | Data Type | Cost | API Key |
|--------|-----------|------|---------|
| CoinGecko | Crypto prices | Free | No |
| ExchangeRate-API | Forex rates | Free tier | Optional |
| NewsAPI | Financial news | Free tier | Yes |
| Alpha Vantage | Stocks | Free tier | Yes |
| OpenRouter | LLM access | Free tier | Yes |

## 🧪 Using Local Models (Ollama)

For privacy or offline use, run with local models:

1. Install Ollama: https://ollama.ai/
2. Pull a model: `ollama pull llama2:13b`
3. Edit config:
   ```yaml
   llm:
     provider: "ollama"
     model: "llama2:13b"
   ```

## 📝 Report Sections

Each generated report includes:

1. **Executive Summary** - Market tone and key theme
2. **Market Overview** - By asset class (equities, bonds, crypto, forex)
3. **Key Events** - Major catalysts and market movers
4. **Cross-Asset Analysis** - Correlations and divergences
5. **Risk Assessment** - Systemic and tail risks
6. **Sector Rotation** - Money flows and leadership
7. **Outlook** - Forecasts for multiple timeframes
8. **Trade Setups** - Actionable ideas with rationale

## 🛠️ Extending the Agent

### Adding a New Data Source

```python
# In src/data_collectors.py
class MyDataCollector(BaseCollector):
    async def get_data(self):
        # Your implementation
        pass
```

### Custom Analysis Prompts

Edit the `SYSTEM_PROMPT` in `src/analysis_engine.py` to customize the AI's analysis style.

## ⚠️ Disclaimer

This tool is for **informational and educational purposes only**. It does not constitute financial advice. Always:

- Do your own research
- Consult with financial advisors
- Never trade based solely on AI-generated analysis
- Be aware of AI limitations and hallucinations

## 📜 License

MIT License - Free to use and modify.

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- Additional data sources
- More sophisticated technical analysis
- Interactive visualizations
- Backtesting capabilities
- Alert system for significant events

---

Built with ❤️ for the global macro community.
