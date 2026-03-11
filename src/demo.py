#!/usr/bin/env python3
"""
Demo runner for Economic Intelligence Agent v2.0
Runs a full 9-step pipeline using mock data (no API keys needed)
"""

import os
import sys
import json
from datetime import datetime

from demo_data import generate_all_demo_data
from analysis_engine import AnalysisEngine, ReportGenerator
from report_generator import EnhancedReportGenerator
from quant_engine import QuantEngine
from risk_engine import RiskEngine
from sentiment_engine import SentimentEngine
from alert_engine import AlertEngine
from storage import DataStore


def run_demo(report_format: str = "markdown"):
    """Run a full demo analysis with the v2.0 pipeline"""

    print("\n" + "=" * 60)
    print(" ECONOMIC INTELLIGENCE AGENT v2.0 - DEMO MODE")
    print("=" * 60 + "\n")
    print("Using simulated market data for demonstration\n")

    # Step 1: Generate Demo Data
    print("[1/9] Generating demo market data...")
    print("-" * 40)

    data = generate_all_demo_data()

    crypto_count = len(data["crypto"]["top_coins"])
    news_count = len(data["news"])
    equity_count = len(data["equities"]["indices"])
    bond_count = len(data["bonds"]["yields"])
    commodity_count = len(data["commodities"]["prices"])
    reddit_count = sum(len(v) for v in data.get("reddit", {}).values())

    print(f"   Crypto: {crypto_count} coins")
    print(f"   Equities: {equity_count} indices")
    print(f"   Bonds: {bond_count} yields")
    print(f"   Commodities: {commodity_count} items")
    print(f"   Forex: USD + EUR rates")
    print(f"   News: {news_count} articles")
    print(f"   Reddit: {reddit_count} posts")
    print(f"   GDELT: {len(data.get('gdelt', []))} articles")
    print(f"   Events: {len(data['economic_events'])} upcoming")

    # Save raw data
    os.makedirs("data", exist_ok=True)
    raw_data_path = f"data/demo_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(raw_data_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"   Raw data saved: {raw_data_path}")

    # Step 2: Store
    print("\n[2/9] Persisting to database...")
    store = DataStore("data/economic_intelligence.db")
    stored = 0
    for key in ("top_coins",):
        items = data.get("crypto", {}).get(key, [])
        if items:
            stored += store.store_market_data_batch(items)
    for key in ("indices",):
        items = data.get("equities", {}).get(key, [])
        if items:
            stored += store.store_market_data_batch(items)
    stored += store.store_market_data_batch(data.get("bonds", {}).get("yields", []))
    stored += store.store_market_data_batch(data.get("commodities", {}).get("prices", []))
    print(f"   Stored {stored} records")

    # Step 3: Quant
    print("\n[3/9] Running quantitative analysis...")
    quant_engine = QuantEngine()
    quant_summary = quant_engine.generate_quant_summary(data)
    yc = quant_summary.get("yield_curve", {})
    print(f"   Yield curve 2Y-10Y spread: {yc.get('spread_2y10y', 'N/A')}%")
    print(f"   Inverted: {'Yes' if yc.get('inverted') else 'No'}")

    # Step 4: Sentiment
    print("\n[4/9] Analyzing sentiment...")
    sent_engine = SentimentEngine()
    sent_summary = sent_engine.generate_sentiment_summary(data)
    fg = sent_summary.get("fear_greed", {})
    print(f"   Fear/Greed: {fg.get('value', 50):.0f}/100 ({fg.get('label', 'neutral')})")
    ns = sent_summary.get("news_sentiment", {})
    print(f"   News sentiment: {ns.get('label', 'N/A')} (score: {ns.get('compound', 0):.3f})")

    # Step 5: Risk
    print("\n[5/9] Computing risk metrics...")
    risk_engine = RiskEngine()
    risk_summary = risk_engine.generate_risk_summary(data)
    print(f"   Overall risk: {risk_summary.get('overall_risk_level', 'N/A').upper()}")
    stress = risk_summary.get("stress_tests", [])
    if stress:
        worst = stress[0]
        print(f"   Worst scenario: {worst['description']} ({worst['pnl_pct']:+.1f}%)")

    # Step 6: LLM Analysis
    print("\n[6/9] AI analysis...")
    api_key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("   No LLM key — using mock analysis")
        analysis = generate_mock_analysis(data)
    else:
        llm_config = {
            "provider": "openrouter" if os.getenv("OPENROUTER_KEY") else ("openai" if os.getenv("OPENAI_API_KEY") else "anthropic"),
            "model": "anthropic/claude-3.5-sonnet" if os.getenv("OPENROUTER_KEY") else "gpt-4",
            "api_key": api_key,
            "temperature": 0.3,
            "max_tokens": 4000,
        }
        try:
            analyzer = AnalysisEngine(llm_config)
            analysis = analyzer.analyze_market_data(data)
            if "error" in analysis:
                print(f"   LLM failed: {analysis['error']}")
                analysis = generate_mock_analysis(data)
            else:
                print(f"   Tone: {analysis.get('executive_summary', {}).get('market_tone', 'N/A').upper()}")
        except Exception as e:
            print(f"   Analysis error: {e}")
            analysis = generate_mock_analysis(data)

    # Step 7: Alerts
    print("\n[7/9] Evaluating alerts...")
    alert_engine = AlertEngine({"channels": ["console"]}, store=store)
    new_alerts = alert_engine.evaluate_and_notify(data, quant_summary, sent_summary, risk_summary)
    print(f"   {len(new_alerts)} alerts triggered")

    # Step 8: Report
    print(f"\n[8/9] Generating {report_format} report...")
    reporter = EnhancedReportGenerator("reports")
    previous = store.get_last_analysis()

    if report_format == "html":
        report = reporter.generate_html(analysis, data, quant=quant_summary, risk=risk_summary, sentiment=sent_summary, alerts=new_alerts, previous=previous)
    elif report_format == "json":
        report = reporter.generate_json(analysis, data, quant=quant_summary, risk=risk_summary, sentiment=sent_summary, alerts=new_alerts)
    else:
        report = reporter.generate_markdown(analysis, data, quant=quant_summary, risk=risk_summary, sentiment=sent_summary, alerts=new_alerts, previous=previous)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    ext = {"markdown": "md", "html": "html", "json": "json"}.get(report_format, "md")
    report_path = reporter.save_report(report, f"demo_report_{ts}.{ext}", fmt=report_format)
    print(f"   Report saved: {report_path}")

    # Step 9: Archive
    print("\n[9/9] Archiving analysis...")
    es = analysis.get("executive_summary", {})
    store.store_analysis(
        market_tone=es.get("market_tone", "unknown"),
        key_theme=es.get("key_theme", ""),
        summary=analysis,
        report_path=report_path,
        report_format=report_format,
    )
    print("   Archived to database")

    # Summary
    print("\n" + "=" * 60)
    print(" DEMO ANALYSIS COMPLETE")
    print("=" * 60)

    print(f"\nMarket Tone: {es.get('market_tone', 'N/A').upper()}")
    print(f"Key Theme: {es.get('key_theme', 'N/A')}")
    print(f"Risk Level: {risk_summary.get('overall_risk_level', 'N/A').upper()}")
    print(f"Fear/Greed: {fg.get('value', 50):.0f}/100 ({fg.get('label', 'neutral')})")
    print(f"Alerts: {len(new_alerts)}")

    # DB stats
    stats = store.get_stats()
    print(f"\nDatabase: {stats}")

    # Report preview
    print("\n" + "=" * 60)
    print(" REPORT PREVIEW:")
    print("=" * 60)
    lines = report.split("\n")
    preview = "\n".join(lines[:50])
    print(preview + "\n... [Report continues — see full file]\n")

    store.close()
    return report_path


def generate_mock_analysis(data: dict) -> dict:
    """Generate a mock analysis when LLM is unavailable"""

    btc_data = next((c for c in data["crypto"]["top_coins"] if c.symbol == "BTC"), None)
    btc_price = btc_data.price if btc_data else 85000

    return {
        "executive_summary": {
            "market_tone": "mixed",
            "key_theme": "Central bank divergence and crypto institutional adoption driving cross-asset volatility, with inflation concerns moderating but growth worries emerging.",
            "primary_risk_factors": [
                "Commercial real estate refinancing cliff with $1.5T debt maturing 2024-2025",
                "Persistent inflation forcing central banks to maintain restrictive policy longer",
                "Geopolitical tensions in Middle East threatening energy supply stability",
                "China property sector stress with potential global contagion",
            ],
            "primary_opportunities": [
                "Bitcoin ETF inflows creating structural demand floor",
                "Gold benefiting from fiscal dominance and de-dollarization trends",
                "Energy sector on supply constraints and infrastructure investment",
                "AI productivity boom driving technology sector earnings",
            ],
        },
        "market_overview": {
            "equities": {
                "trend": "Consolidation with rotation from mega-cap tech to value and small-caps",
                "key_levels": "S&P 500 support at 5750/5650, resistance at 5900/6000",
                "sentiment": "neutral",
            },
            "bonds": {
                "yield_trend": "Range-bound with 10Y Treasury 4.1-4.4%, curve steepening beginning",
                "curve_shape": "inverted",
                "implications": "Historical recession indicator, but soft landing still possible",
            },
            "crypto": {
                "market_phase": "accumulation",
                "dominance_trends": "BTC dominance elevated at 58% on institutional flows",
                "risk_appetite": "moderate",
            },
            "forex": {
                "dollar_strength": "strong",
                "major_moves": "USD/JPY near 150 intervention watch, EUR/USD testing 0.92 support",
                "carry_trade_activity": "Reduced as BoJ normalizes, unwind risk elevated",
            },
        },
        "key_events": [
            {"event": "Fed Chair Powell Congressional testimony", "impact": "immediate", "affected_assets": ["USD", "Treasuries", "Gold", "Bitcoin"], "market_implication": "Dovish tone bullish for risk assets"},
            {"event": "US Non-Farm Payrolls release", "impact": "immediate", "affected_assets": ["USD", "Treasuries", "Equities"], "market_implication": "Strong data delays rate cut expectations"},
            {"event": "ECB Rate Decision with updated projections", "impact": "delayed", "affected_assets": ["EUR", "European equities"], "market_implication": "Easing signals bearish for EUR"},
        ],
        "cross_asset_analysis": [
            {"observation": "Bitcoin and Gold decoupling from traditional risk assets", "assets_involved": ["Bitcoin", "Gold", "USD"], "historical_context": "Similar to 2020-2021 inflation hedge phase", "implications": "Treat both as distinct inflation/uncertainty hedges"},
            {"observation": "Equity-bond correlation normalizing to negative", "assets_involved": ["S&P 500", "10Y Treasury"], "historical_context": "Positive correlation during 2022 was anomaly", "implications": "Traditional 60/40 diversification working again"},
        ],
        "risk_assessment": {
            "systemic_risks": [
                {"risk": "CRE refinancing crisis as $1.5T debt matures into higher rates", "severity": "high", "probability": "medium", "trigger_events": ["Regional bank failures", "Office vacancy >25%"]},
                {"risk": "Treasury market liquidity stress amid QT", "severity": "medium", "probability": "medium", "trigger_events": ["Auction tail risks", "Foreign selling"]},
            ],
            "tail_risks": [
                "Middle East conflict disrupting oil above $120/bbl",
                "Major crypto exchange failure triggering DeFi contagion",
                "AI bubble burst with concentrated tech valuations",
            ],
            "hedging_considerations": "Long volatility via VIX calls, increase gold to 10-15%, maintain USD cash buffer",
        },
        "sector_rotation": {
            "current_flows": "Rotation from mega-cap tech to small-cap value and energy",
            "leading_sectors": ["Energy", "Financials", "Materials", "Utilities"],
            "lagging_sectors": ["Technology", "Communication Services", "Real Estate"],
            "rotation_stage": "mid",
        },
        "outlook": {
            "immediate_1_7_days": f"Range-bound. BTC consolidating ${btc_price - 3000:.0f}-${btc_price + 3000:.0f}. Dollar strong but overbought.",
            "short_term_1_4_weeks": "Directional catalyst from NFP and CPI data. Soft landing = risk-on rally.",
            "medium_term_1_6_months": "Baseline: soft landing, Fed cuts 2-3 times mid-year. Bear case: credit event.",
            "key_levels_to_watch": {
                "equities": "S&P 5650 support, 6000 breakout, VIX 20 fear threshold",
                "bonds": "10Y 3.8% bullish, 4.5% bearish, 2s10s flattening",
                "crypto": f"BTC ${btc_price - 5000:.0f} support, $100k psychological",
                "forex": "DXY 108 resistance, USD/JPY 150 intervention",
            },
            "catalysts_to_monitor": [
                "Fed policy pivot signals",
                "Inflation trajectory (CPI/PCE)",
                "Corporate earnings guidance",
                "China stimulus effectiveness",
                "Geopolitical escalations",
            ],
        },
        "trade_setups": [
            {"idea": f"Long BTC in ${btc_price - 5000:.0f}-${btc_price - 2000:.0f} accumulation zone", "rationale": "ETF inflows + halving catalyst", "risk_reward": "3:1", "timeframe": "medium"},
            {"idea": "Yield curve steepener: Long 2Y, Short 10Y", "rationale": "Curve normalization as Fed cuts", "risk_reward": "2.5:1", "timeframe": "short"},
            {"idea": "Gold long on dips to $2800-$2825", "rationale": "Fiscal dominance hedge + central bank buying", "risk_reward": "2:1", "timeframe": "short"},
        ],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EconAgent Demo")
    parser.add_argument("--format", choices=["markdown", "html", "json"], default="markdown")
    args = parser.parse_args()

    try:
        report_path = run_demo(args.format)
        print(f"\nFull report: {report_path}")
        print("\nTo run with live data:")
        print("  1. Get API keys from OpenRouter (free): https://openrouter.ai/")
        print("  2. export OPENROUTER_KEY='your_key'")
        print("  3. python src/main.py")
    except KeyboardInterrupt:
        print("\n\nDemo interrupted")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
