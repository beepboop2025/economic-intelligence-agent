"""
Analysis Engine for Economic Intelligence Agent
Uses LLM to analyze market data and generate insights
"""

import os
import json
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MarketInsight:
    """Structured market insight"""
    category: str
    title: str
    description: str
    impact: str  # bullish, bearish, neutral
    confidence: str  # high, medium, low
    timeframe: str  # immediate, short_term, medium_term
    related_assets: List[str]
    key_drivers: List[str]
    risks: List[str]


@dataclass
class RiskAssessment:
    """Risk assessment structure"""
    risk_type: str
    severity: str  # critical, high, medium, low
    probability: str  # high, medium, low
    description: str
    affected_markets: List[str]
    mitigation_factors: List[str]


@dataclass
class CrossAssetAnalysis:
    """Cross-asset correlation analysis"""
    observation: str
    assets_involved: List[str]
    correlation_type: str  # positive, negative, decoupling, converging
    historical_context: str
    implications: str


class LLMClient:
    """LLM client for analysis - supports multiple providers"""
    
    # Map provider to environment variable name
    PROVIDER_ENV_KEYS = {
        "openrouter": "OPENROUTER_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "ollama": None,
    }

    def __init__(self, config: Dict):
        self.config = config
        self.provider = config.get("provider", "openrouter")
        self.model = config.get("model", "anthropic/claude-3.5-sonnet")
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 4000)

        # Resolve API key: env var for provider > config value (skip templates)
        env_key_name = self.PROVIDER_ENV_KEYS.get(self.provider)
        api_key = ""
        if env_key_name:
            api_key = os.getenv(env_key_name, "")
        if not api_key:
            cfg_key = config.get("api_key", "")
            if cfg_key and not cfg_key.startswith("${"):
                api_key = cfg_key
        self.api_key = api_key
        
    def create_chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Create chat completion with configured provider"""
        
        if self.provider == "openrouter":
            return self._openrouter_call(system_prompt, user_prompt)
        elif self.provider == "openai":
            return self._openai_call(system_prompt, user_prompt)
        elif self.provider == "anthropic":
            return self._anthropic_call(system_prompt, user_prompt)
        elif self.provider == "ollama":
            return self._ollama_call(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def _openrouter_call(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenRouter API"""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=120
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            return f"Error: {e}"
    
    def _openai_call(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenAI API"""
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return f"Error: {e}"
    
    def _anthropic_call(self, system_prompt: str, user_prompt: str) -> str:
        """Call Anthropic API"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            return resp.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return f"Error: {e}"
    
    def _ollama_call(self, system_prompt: str, user_prompt: str) -> str:
        """Call local Ollama instance"""
        import requests
        
        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "stream": False
                },
                timeout=120
            )
            return resp.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return f"Error: {e}"


class AnalysisEngine:
    """Main analysis engine"""
    
    SYSTEM_PROMPT = """You are an elite macroeconomic analyst and financial markets expert with decades of experience across all asset classes.

Your role is to:
1. Analyze current market conditions across equities, bonds, crypto, forex, and commodities
2. Identify key macro trends, correlations, and divergences
3. Assess risks and opportunities with specific timeframes
4. Provide actionable insights backed by data

Analysis principles:
- Be specific and data-driven, not vague
- Consider cross-asset implications
- Identify non-obvious connections
- Assess both upside and downside scenarios
- Use professional financial terminology appropriately

Respond in structured JSON format as specified in the user prompt."""

    def __init__(self, llm_config: Dict):
        self.llm = LLMClient(llm_config)
        
    def analyze_market_data(self, data: Dict) -> Dict[str, Any]:
        """Generate comprehensive market analysis"""
        
        # Serialize data for LLM
        data_json = json.dumps(data, indent=2, default=str)[:15000]  # Limit context
        
        # JSON template for the analysis response
        json_template = '''{
    "executive_summary": {
        "market_tone": "bullish/bearish/neutral/mixed",
        "key_theme": "single sentence describing dominant theme",
        "primary_risk_factors": ["risk1", "risk2"],
        "primary_opportunities": ["opp1", "opp2"]
    },
    "market_overview": {
        "equities": {
            "trend": "description",
            "key_levels": "support/resistance",
            "sentiment": "bullish/bearish/neutral"
        },
        "bonds": {
            "yield_trend": "description",
            "curve_shape": "normal/flat/inverted",
            "implications": "text"
        },
        "crypto": {
            "market_phase": "accumulation/distribution/unknown",
            "dominance_trends": "BTC/ETH/alt behavior",
            "risk_appetite": "high/medium/low"
        },
        "forex": {
            "dollar_strength": "strong/weak/neutral",
            "major_moves": "description",
            "carry_trade_activity": "description"
        }
    },
    "key_events": [
        {
            "event": "description",
            "impact": "immediate/delayed",
            "affected_assets": ["asset1", "asset2"],
            "market_implication": "bullish/bearish for X"
        }
    ],
    "cross_asset_analysis": [
        {
            "observation": "description of correlation/divergence",
            "assets_involved": ["asset1", "asset2"],
            "historical_context": "how this compared to past",
            "implications": "what it means going forward"
        }
    ],
    "risk_assessment": {
        "systemic_risks": [
            {
                "risk": "description",
                "severity": "critical/high/medium/low",
                "probability": "high/medium/low",
                "trigger_events": ["event1", "event2"]
            }
        ],
        "tail_risks": ["description1", "description2"],
        "hedging_considerations": "text"
    },
    "sector_rotation": {
        "current_flows": "where money is moving",
        "leading_sectors": ["sector1", "sector2"],
        "lagging_sectors": ["sector1", "sector2"],
        "rotation_stage": "early/mid/late"
    },
    "outlook": {
        "immediate_1_7_days": "specific forecast",
        "short_term_1_4_weeks": "specific forecast",
        "medium_term_1_6_months": "specific forecast",
        "key_levels_to_watch": {
            "equities": "levels",
            "bonds": "yield levels",
            "crypto": "price levels",
            "forex": "rate levels"
        },
        "catalysts_to_monitor": ["event1", "event2", "event3"]
    },
    "trade_setups": [
        {
            "idea": "description",
            "rationale": "why",
            "risk_reward": "assessment",
            "timeframe": "immediate/short/medium"
        }
    ]
}'''
        
        analysis_prompt = f"""Analyze the following market data and provide a comprehensive macro analysis.

DATA:
{data_json}

Provide your analysis in the following JSON structure:
{json_template}

Ensure all fields are populated with substantive, data-driven analysis. Be specific about levels, percentages, and concrete implications."""

        logger.info("Sending data to LLM for analysis...")
        response = self.llm.create_chat_completion(self.SYSTEM_PROMPT, analysis_prompt)
        
        # Extract JSON from response using robust balanced-brace parser
        from utils import extract_json_from_text
        analysis = extract_json_from_text(response)
        if analysis is None:
            logger.error("Failed to extract JSON from LLM response")
            analysis = {"error": "No valid JSON found", "raw_response": response[:500]}
        
        return analysis
    
    def generate_sentiment_analysis(self, news_items: List[Dict]) -> Dict:
        """Analyze sentiment from news items"""
        
        if not news_items:
            return {"overall": "neutral", "details": {}}
        
        news_text = "\n".join([
            f"- {n.get('title', '')}: {n.get('description', '')}"
            for n in news_items[:30]  # Limit to 30 items
        ])
        
        prompt = f"""Analyze the sentiment of these financial news headlines:

{news_text}

Provide JSON response:
{{
    "overall_sentiment": "very_bullish/bullish/neutral/bearish/very_bearish",
    "sentiment_score": "-10 to +10",
    "key_themes": ["theme1", "theme2"],
    "emerging_concerns": ["concern1", "concern2"],
    "positive_developments": ["dev1", "dev2"],
    "media_bias": "risk-on/risk-off/neutral",
    "fear_greed_assessment": "extreme_fear/fear/neutral/greed/extreme_greed"
}}"""

        response = self.llm.create_chat_completion(self.SYSTEM_PROMPT, prompt)
        
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0:
                return json.loads(response[json_start:json_end])
        except:
            pass
        
        return {"overall": "neutral", "raw": response}


class ReportGenerator:
    """Generate formatted reports from analysis"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        
    def generate_markdown_report(self, analysis: Dict, data: Dict) -> str:
        """Generate a comprehensive markdown report"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        
        report = f"""# 🌍 Global Economic Intelligence Report

**Generated:** {timestamp}

---

## 📋 Executive Summary

**Market Tone:** {analysis.get('executive_summary', {}).get('market_tone', 'N/A').upper()}

**Key Theme:** {analysis.get('executive_summary', {}).get('key_theme', 'N/A')}

### Primary Risk Factors
{self._list_to_bullets(analysis.get('executive_summary', {}).get('primary_risk_factors', []))}

### Primary Opportunities
{self._list_to_bullets(analysis.get('executive_summary', {}).get('primary_opportunities', []))}

---

## 📊 Market Overview

### Equities
{self._dict_to_markdown(analysis.get('market_overview', {}).get('equities', {}))}

### Bonds & Fixed Income
{self._dict_to_markdown(analysis.get('market_overview', {}).get('bonds', {}))}

### Cryptocurrency
{self._dict_to_markdown(analysis.get('market_overview', {}).get('crypto', {}))}

### Foreign Exchange
{self._dict_to_markdown(analysis.get('market_overview', {}).get('forex', {}))}

---

## 🔥 Key Events & Catalysts

{self._format_key_events(analysis.get('key_events', []))}

---

## 🔗 Cross-Asset Analysis

{self._format_cross_asset(analysis.get('cross_asset_analysis', []))}

---

## ⚠️ Risk Assessment

### Systemic Risks
{self._format_systemic_risks(analysis.get('risk_assessment', {}).get('systemic_risks', []))}

### Tail Risks
{self._list_to_bullets(analysis.get('risk_assessment', {}).get('tail_risks', []))}

**Hedging Considerations:** {analysis.get('risk_assessment', {}).get('hedging_considerations', 'N/A')}

---

## 🔄 Sector Rotation & Flows

**Current Flows:** {analysis.get('sector_rotation', {}).get('current_flows', 'N/A')}

**Rotation Stage:** {analysis.get('sector_rotation', {}).get('rotation_stage', 'N/A')}

**Leading Sectors:** {', '.join(analysis.get('sector_rotation', {}).get('leading_sectors', []))}

**Lagging Sectors:** {', '.join(analysis.get('sector_rotation', {}).get('lagging_sectors', []))}

---

## 🔮 Outlook & Forecasts

### Immediate (1-7 Days)
{analysis.get('outlook', {}).get('immediate_1_7_days', 'N/A')}

### Short-Term (1-4 Weeks)
{analysis.get('outlook', {}).get('short_term_1_4_weeks', 'N/A')}

### Medium-Term (1-6 Months)
{analysis.get('outlook', {}).get('medium_term_1_6_months', 'N/A')}

### Key Levels to Watch
{self._dict_to_markdown(analysis.get('outlook', {}).get('key_levels_to_watch', {}))}

### Catalysts to Monitor
{self._list_to_bullets(analysis.get('outlook', {}).get('catalysts_to_monitor', []))}

---

## 💡 Trade Setups & Ideas

{self._format_trade_setups(analysis.get('trade_setups', []))}

---

## 📈 Raw Market Data Snapshot

### Top Cryptocurrencies
| Symbol | Price | 24h Change | Market Cap |
|--------|-------|------------|------------|
{self._format_crypto_table(data.get('crypto', {}).get('top_coins', [])[:10])}

### Global Crypto Metrics
{self._format_crypto_global(data.get('crypto', {}).get('global', {}))}

---

*This report is generated by AI and should not be considered financial advice. Always conduct your own research.*
"""
        
        return report
    
    def _list_to_bullets(self, items: List[str]) -> str:
        if not items:
            return "- None identified"
        return "\n".join(f"- {item}" for item in items)
    
    def _dict_to_markdown(self, d: Dict) -> str:
        if not d:
            return "N/A"
        return "\n".join(f"- **{k.replace('_', ' ').title()}:** {v}" for k, v in d.items())
    
    def _format_key_events(self, events: List[Dict]) -> str:
        if not events:
            return "No major events identified."
        
        lines = []
        for i, event in enumerate(events, 1):
            lines.append(f"### {i}. {event.get('event', 'Unknown')}")
            lines.append(f"- **Impact:** {event.get('impact', 'N/A')}")
            lines.append(f"- **Affected Assets:** {', '.join(event.get('affected_assets', []))}")
            lines.append(f"- **Implication:** {event.get('market_implication', 'N/A')}")
            lines.append("")
        return "\n".join(lines)
    
    def _format_cross_asset(self, analyses: List[Dict]) -> str:
        if not analyses:
            return "No significant cross-asset patterns identified."
        
        lines = []
        for analysis in analyses:
            lines.append(f"### {analysis.get('observation', 'Observation')}")
            lines.append(f"- **Assets:** {', '.join(analysis.get('assets_involved', []))}")
            lines.append(f"- **Historical Context:** {analysis.get('historical_context', 'N/A')}")
            lines.append(f"- **Implications:** {analysis.get('implications', 'N/A')}")
            lines.append("")
        return "\n".join(lines)
    
    def _format_systemic_risks(self, risks: List[Dict]) -> str:
        if not risks:
            return "- No systemic risks identified."
        
        lines = []
        for risk in risks:
            lines.append(f"#### {risk.get('risk', 'Risk')}")
            lines.append(f"- **Severity:** {risk.get('severity', 'N/A')}")
            lines.append(f"- **Probability:** {risk.get('probability', 'N/A')}")
            lines.append(f"- **Potential Triggers:** {', '.join(risk.get('trigger_events', []))}")
            lines.append("")
        return "\n".join(lines)
    
    def _format_trade_setups(self, setups: List[Dict]) -> str:
        if not setups:
            return "No specific setups identified at this time."
        
        lines = []
        for i, setup in enumerate(setups, 1):
            lines.append(f"### Setup {i}: {setup.get('idea', 'Idea')}")
            lines.append(f"- **Rationale:** {setup.get('rationale', 'N/A')}")
            lines.append(f"- **Risk/Reward:** {setup.get('risk_reward', 'N/A')}")
            lines.append(f"- **Timeframe:** {setup.get('timeframe', 'N/A')}")
            lines.append("")
        return "\n".join(lines)
    
    def _format_crypto_table(self, coins: List) -> str:
        from utils import format_number, format_price, format_percent
        lines = []
        for coin in coins:
            if hasattr(coin, '__dict__'):
                symbol = coin.symbol
                price = format_price(coin.price)
                change = format_percent(coin.change_percent_24h)
                mcap = f"${format_number(coin.market_cap)}" if coin.market_cap and coin.market_cap > 0 else "N/A"
            else:
                symbol = coin.get('symbol', 'N/A')
                price = format_price(coin.get('price', 0))
                change = format_percent(coin.get('change_percent_24h', 0))
                raw_mcap = coin.get('market_cap', 0)
                mcap = f"${format_number(raw_mcap)}" if raw_mcap and raw_mcap > 0 else "N/A"
            lines.append(f"| {symbol} | {price} | {change} | {mcap} |")
        return "\n".join(lines)
    
    def _format_crypto_global(self, global_data: Dict) -> str:
        if not global_data or 'data' not in global_data:
            return "Global data unavailable"
        
        data = global_data.get('data', {})
        mcap = data.get('total_market_cap', {}).get('usd', 0)
        volume = data.get('total_volume', {}).get('usd', 0)
        btc_dominance = data.get('market_cap_percentage', {}).get('btc', 0)
        
        return f"""- **Total Market Cap:** ${mcap/1e12:.2f}T
- **24h Volume:** ${volume/1e9:.1f}B
- **BTC Dominance:** {btc_dominance:.1f}%"""
    
    def save_report(self, report: str, filename: Optional[str] = None) -> str:
        """Save report to file"""
        import os
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"economic_report_{timestamp}.md"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return filepath


if __name__ == "__main__":
    # Test the analysis engine
    engine = AnalysisEngine({
        "provider": "openrouter",
        "model": "anthropic/claude-3.5-sonnet",
        "api_key": "test"
    })
    
    print("Analysis engine initialized successfully")
