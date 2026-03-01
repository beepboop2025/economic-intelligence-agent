"""
Economic Intelligence Agent - Main Orchestrator (v2.0)
9-step pipeline: Collect → Store → Quant → Sentiment → Risk → LLM → Alert → Report → Archive
"""

import os
import sys
import asyncio
import argparse
import yaml
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# Local imports
from data_collectors import DataAggregator
from analysis_engine import AnalysisEngine, ReportGenerator
from report_generator import EnhancedReportGenerator
from config_loader import setup_environment, check_api_keys, validate_config
from storage import DataStore
from quant_engine import QuantEngine
from risk_engine import RiskEngine
from sentiment_engine import SentimentEngine
from alert_engine import AlertEngine
from utils import setup_logging, extract_json_from_text

# Optional Rich imports (graceful fallback)
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ── Configuration ────────────────────────────────────────────────

def load_config(config_path: str = "config/settings.yaml") -> dict:
    """Load configuration from YAML file with .env support"""
    setup_environment()

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        def expand_env_vars(obj):
            if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                env_var = obj[2:-1]
                return os.getenv(env_var, obj)
            elif isinstance(obj, dict):
                return {k: expand_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [expand_env_vars(item) for item in obj]
            return obj

        return expand_env_vars(config)
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        print("Using default configuration...")
        return create_default_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        return create_default_config()


def create_default_config() -> dict:
    return {
        "data_sources": {
            "coingecko": {"enabled": True},
            "exchangerate": {"enabled": True},
            "yfinance": {"enabled": True},
            "fred": {"enabled": True},
            "finnhub": {"enabled": True},
            "newsapi": {"enabled": False},
            "alpha_vantage": {"enabled": False},
            "reddit": {"enabled": True},
            "gdelt": {"enabled": True},
            "economic_calendar": {"enabled": True},
        },
        "llm": {
            "provider": "openrouter",
            "model": "anthropic/claude-3.5-sonnet",
            "api_key": os.getenv("OPENROUTER_KEY", ""),
            "temperature": 0.3,
            "max_tokens": 4000,
        },
        "analysis": {
            "markets": ["equities", "bonds", "crypto", "forex", "commodities"],
            "regions": ["global", "us", "europe", "asia"],
            "timeframes": ["immediate", "short_term", "medium_term"],
        },
        "report": {"format": "markdown", "auto_save": True, "output_dir": "reports"},
        "storage": {"db_path": "data/economic_intelligence.db", "retention_days": 90},
        "resilience": {"cache_ttl": 300, "max_retries": 3},
        "alerts": {
            "enabled": True,
            "channels": ["console"],
            "thresholds": {"price_change_pct": 5.0, "volatility_spike": 3.0},
        },
    }


# ── Mock Analysis Fallback ───────────────────────────────────────

def generate_mock_analysis(data: dict) -> dict:
    """Generate analysis when LLM is unavailable"""
    from demo import generate_mock_analysis as _mock
    return _mock(data)


# ── Printing Helpers ─────────────────────────────────────────────

console = Console() if HAS_RICH else None


def _print(msg: str) -> None:
    if console:
        console.print(msg)
    else:
        print(msg)


def _print_table(title: str, rows: list, columns: list) -> None:
    if HAS_RICH:
        table = Table(title=title)
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*[str(c) for c in row])
        console.print(table)
    else:
        print(f"\n{title}")
        print("-" * 50)
        header = " | ".join(columns)
        print(header)
        print("-" * len(header))
        for row in rows:
            print(" | ".join(str(c) for c in row))


def _print_panel(title: str, content: str) -> None:
    if HAS_RICH:
        console.print(Panel(content, title=title, border_style="blue"))
    else:
        print(f"\n{'=' * 50}")
        print(f" {title}")
        print(f"{'=' * 50}")
        print(content)


# ── Main Agent ───────────────────────────────────────────────────

class EconomicIntelligenceAgent:
    """Main agent: 9-step pipeline orchestrator"""

    def __init__(self, config: dict):
        self.config = config
        self.aggregator = DataAggregator(config)
        self.analyzer = AnalysisEngine(config.get("llm", {}))
        self.old_reporter = ReportGenerator(config.get("report", {}).get("output_dir", "reports"))
        self.reporter = EnhancedReportGenerator(config.get("report", {}).get("output_dir", "reports"))
        self.store = DataStore(config.get("storage", {}).get("db_path", "data/economic_intelligence.db"))
        self.quant = QuantEngine()
        self.risk = RiskEngine()
        self.sentiment = SentimentEngine()
        self.alerts = AlertEngine(config.get("alerts", {}), store=self.store)

    async def run_analysis(
        self,
        save_data: bool = False,
        report_format: str = "markdown",
        enable_alerts: bool = False,
        no_llm: bool = False,
        quant_only: bool = False,
        risk_only: bool = False,
        compare: bool = False,
        demo_mode: bool = False,
    ) -> dict:
        """Run the complete 9-step pipeline"""

        _print("\n" + "=" * 60)
        _print(" GLOBAL ECONOMIC INTELLIGENCE AGENT v2.0")
        _print("=" * 60 + "\n")

        result = {
            "status": "success",
            "data": {},
            "analysis": {},
            "quant": {},
            "sentiment": {},
            "risk": {},
            "alerts": [],
            "report_path": None,
        }

        # ── Step 1: COLLECT ──────────────────────────────────────
        _print("[1/9] Collecting market data...")

        if demo_mode:
            from demo_data import generate_all_demo_data
            data = generate_all_demo_data()
            _print("  Using demo data")
        else:
            try:
                data = await self.aggregator.collect_all()
            except Exception as e:
                _print(f"  Collection error: {e}")
                data = {"timestamp": datetime.now().isoformat(), "error": str(e)}

        result["data"] = data

        if save_data:
            raw_path = self._save_raw_data(data)
            _print(f"  Raw data saved: {raw_path}")

        # Print collection summary
        crypto_count = len(data.get("crypto", {}).get("top_coins", []))
        news_count = len(data.get("news", []))
        equity_count = len(data.get("equities", {}).get("indices", []))
        bond_count = len(data.get("bonds", {}).get("yields", []))
        _print(f"  Crypto: {crypto_count} | Equities: {equity_count} | Bonds: {bond_count} | News: {news_count}")

        # ── Step 2: STORE ────────────────────────────────────────
        _print("[2/9] Persisting to database...")
        try:
            stored = 0
            for key in ("top_coins", "indices", "prices", "sectors"):
                for group in ("crypto", "equities", "commodities"):
                    items = data.get(group, {}).get(key, [])
                    if items:
                        stored += self.store.store_market_data_batch(items)
            bonds = data.get("bonds", {}).get("yields", [])
            if bonds:
                stored += self.store.store_market_data_batch(bonds)
            _print(f"  Stored {stored} price records")
        except Exception as e:
            _print(f"  Storage error: {e}")

        # ── Step 3: QUANT ────────────────────────────────────────
        _print("[3/9] Running quantitative analysis...")
        try:
            quant_summary = self.quant.generate_quant_summary(data)
            result["quant"] = quant_summary
            yc = quant_summary.get("yield_curve", {})
            if yc.get("spread_2y10y") is not None:
                _print(f"  Yield curve 2Y-10Y spread: {yc['spread_2y10y']}% {'(INVERTED)' if yc.get('inverted') else ''}")
        except Exception as e:
            _print(f"  Quant error: {e}")

        if quant_only:
            _print("\n[Quant-only mode — skipping remaining steps]")
            return result

        # ── Step 4: SENTIMENT ────────────────────────────────────
        _print("[4/9] Analyzing sentiment...")
        try:
            sent_summary = self.sentiment.generate_sentiment_summary(data)
            result["sentiment"] = sent_summary
            fg = sent_summary.get("fear_greed", {})
            _print(f"  Fear/Greed Index: {fg.get('value', 50):.0f}/100 ({fg.get('label', 'neutral')})")
        except Exception as e:
            _print(f"  Sentiment error: {e}")

        # ── Step 5: RISK ─────────────────────────────────────────
        _print("[5/9] Computing risk metrics...")
        try:
            risk_summary = self.risk.generate_risk_summary(data)
            result["risk"] = risk_summary
            _print(f"  Overall risk level: {risk_summary.get('overall_risk_level', 'N/A').upper()}")
        except Exception as e:
            _print(f"  Risk error: {e}")

        if risk_only:
            _print("\n[Risk-only mode — skipping remaining steps]")
            return result

        # ── Step 6: LLM ANALYSIS ─────────────────────────────────
        _print("[6/9] LLM macro analysis...")
        if no_llm:
            _print("  LLM disabled — using mock analysis")
            analysis = generate_mock_analysis(data)
        else:
            try:
                analysis = self.analyzer.analyze_market_data(data)
                if "error" in analysis:
                    _print(f"  LLM error: {analysis['error']}")
                    _print("  Falling back to mock analysis...")
                    analysis = generate_mock_analysis(data)
                else:
                    tone = analysis.get("executive_summary", {}).get("market_tone", "N/A")
                    _print(f"  Market Tone: {tone.upper()}")
            except Exception as e:
                _print(f"  LLM error: {e}")
                _print("  Falling back to mock analysis...")
                analysis = generate_mock_analysis(data)

        result["analysis"] = analysis

        # ── Step 7: ALERTS ───────────────────────────────────────
        _print("[7/9] Evaluating alert rules...")
        new_alerts = []
        try:
            new_alerts = self.alerts.evaluate_and_notify(
                data, quant_summary, sent_summary, risk_summary
            )
            result["alerts"] = new_alerts
            _print(f"  {len(new_alerts)} new alerts triggered")
        except Exception as e:
            _print(f"  Alert error: {e}")

        # ── Step 8: REPORT ───────────────────────────────────────
        _print(f"[8/9] Generating {report_format} report...")
        report_path = None
        try:
            previous = self.store.get_last_analysis() if compare else None

            if report_format == "html":
                report = self.reporter.generate_html(
                    analysis, data, quant=quant_summary, risk=risk_summary,
                    sentiment=sent_summary, alerts=new_alerts, previous=previous,
                )
            elif report_format == "json":
                report = self.reporter.generate_json(
                    analysis, data, quant=quant_summary, risk=risk_summary,
                    sentiment=sent_summary, alerts=new_alerts,
                )
            else:
                report = self.reporter.generate_markdown(
                    analysis, data, quant=quant_summary, risk=risk_summary,
                    sentiment=sent_summary, alerts=new_alerts, previous=previous,
                )

            if self.config.get("report", {}).get("auto_save", True):
                report_path = self.reporter.save_report(report, fmt=report_format)
                _print(f"  Report saved: {report_path}")
            result["report_path"] = report_path
            result["report"] = report
        except Exception as e:
            _print(f"  Report error: {e}")

        # ── Step 9: ARCHIVE ──────────────────────────────────────
        _print("[9/9] Archiving analysis...")
        try:
            es = analysis.get("executive_summary", {})
            self.store.store_analysis(
                market_tone=es.get("market_tone", "unknown"),
                key_theme=es.get("key_theme", ""),
                summary=analysis,
                report_path=report_path,
                report_format=report_format,
            )
            _print("  Analysis archived to database")
        except Exception as e:
            _print(f"  Archive error: {e}")

        # ── Summary ──────────────────────────────────────────────
        _print("\n" + "=" * 60)
        _print(" ANALYSIS COMPLETE")
        _print("=" * 60)

        es = analysis.get("executive_summary", {})
        _print_panel("Executive Summary", (
            f"Market Tone: {es.get('market_tone', 'N/A').upper()}\n"
            f"Key Theme: {es.get('key_theme', 'N/A')}\n"
            f"Risk Level: {risk_summary.get('overall_risk_level', 'N/A').upper()}\n"
            f"Fear/Greed: {fg.get('value', 50):.0f}/100 ({fg.get('label', 'neutral')})\n"
            f"Alerts: {len(new_alerts)} new"
        ))

        if report_path:
            _print(f"\nFull report: {report_path}")

        return result

    def _save_raw_data(self, data: dict) -> str:
        os.makedirs("data", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        filepath = f"data/raw_data_{ts}.json"
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return filepath

    async def continuous_monitoring(self, interval_hours: int = 6, **kwargs):
        _print(f"\nStarting continuous monitoring (interval: {interval_hours}h)")
        _print("Press Ctrl+C to stop\n")

        while True:
            try:
                result = await self.run_analysis(save_data=True, **kwargs)
                status = result.get("status", "error")
                _print(f"\nCompleted at {datetime.now().strftime('%Y-%m-%d %H:%M')} — {status}")
                _print(f"Next update in {interval_hours} hours...")
                await asyncio.sleep(interval_hours * 3600)
            except KeyboardInterrupt:
                _print("\nMonitoring stopped by user")
                break
            except Exception as e:
                _print(f"\nError in monitoring loop: {e}")
                await asyncio.sleep(60)


# ── Banner + API Key Status ──────────────────────────────────────

def print_banner():
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║      GLOBAL ECONOMIC INTELLIGENCE AGENT v2.0              ║
    ║                                                           ║
    ║      Multi-Asset Analysis & Intelligence Platform         ║
    ║      Equities • Bonds • Crypto • Forex • Commodities     ║
    ║      Quant • Risk • Sentiment • Alerts • Reports         ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def check_api_keys_status(config: dict) -> list:
    keys_status = []
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "")

    # LLM provider key
    env_map = {"openrouter": "OPENROUTER_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    env_key = env_map.get(provider)
    if env_key:
        key = os.getenv(env_key, "")
        keys_status.append((provider.title(), bool(key)))

    # Data source keys
    ds_checks = [
        ("FRED", "FRED_API_KEY"),
        ("Finnhub", "FINNHUB_KEY"),
        ("NewsAPI", "NEWSAPI_KEY"),
        ("Alpha Vantage", "ALPHA_VANTAGE_KEY"),
    ]
    for name, env_var in ds_checks:
        keys_status.append((name, bool(os.getenv(env_var, ""))))

    # No-key sources
    for name in ("CoinGecko", "ExchangeRate", "yfinance", "Reddit", "GDELT"):
        keys_status.append((name, True))

    return keys_status


# ── Entry Point ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Global Economic Intelligence Agent v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                  # Full analysis
  python main.py --demo                           # Demo mode (no API keys)
  python main.py --demo --format html             # HTML report
  python main.py --demo --alerts                  # Show alerts
  python main.py --demo --quant                   # Quant analysis only
  python main.py --no-llm                         # Skip LLM, use mock
  python main.py --monitor --interval 6           # Continuous monitoring
  python main.py --api-keys                       # Show API key status
  python main.py --compare                        # Compare with last run
        """,
    )

    parser.add_argument("--config", "-c", default="config/settings.yaml", help="Config file path")
    parser.add_argument("--monitor", "-m", action="store_true", help="Continuous monitoring mode")
    parser.add_argument("--interval", "-i", type=int, default=6, help="Monitor interval (hours)")
    parser.add_argument("--save-data", "-s", action="store_true", help="Save raw data")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--api-keys", action="store_true", help="Show API key status")
    parser.add_argument("--demo", action="store_true", help="Run with demo data")
    parser.add_argument("--format", choices=["markdown", "html", "json"], default="markdown", help="Report format")
    parser.add_argument("--alerts", action="store_true", help="Enable alert evaluation")
    parser.add_argument("--compare", action="store_true", help="Compare with previous analysis")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM, use mock analysis")
    parser.add_argument("--quant", action="store_true", help="Quant analysis only")
    parser.add_argument("--risk", action="store_true", help="Risk analysis only")
    parser.add_argument("--assets", nargs="+", help="Specific assets to analyze")

    args = parser.parse_args()

    print_banner()

    config = load_config(args.config)

    # Validate config
    warnings = validate_config(config)
    for w in warnings:
        print(f"  [WARN] {w}")

    keys_status = check_api_keys_status(config)

    if args.api_keys:
        print("\nAPI Key Status:")
        print("-" * 40)
        for name, status in keys_status:
            icon = "[OK]" if status else "[--]"
            print(f"  {icon} {name}")
        print()
        return

    # Print key status
    print("\nData Sources:")
    print("-" * 40)
    for name, status in keys_status:
        icon = "[OK]" if status else "[--]"
        print(f"  {icon} {name}")

    # LLM check
    llm_configured = any(
        status for name, status in keys_status
        if name.lower() in ("openrouter", "openai", "anthropic")
    )

    if not llm_configured and not args.demo and not args.no_llm:
        print("\nNo LLM API key configured.")
        print("Use --demo for demo mode, or --no-llm to skip LLM analysis.")
        print("\nGet your free API key from:")
        print("  - OpenRouter: https://openrouter.ai/")
        print("  - OpenAI: https://platform.openai.com/")
        print("\nOr use Ollama for local models (no API key needed)")
        args.no_llm = True  # Auto-fallback instead of exiting

    # Initialize and run
    agent = EconomicIntelligenceAgent(config)

    try:
        run_kwargs = dict(
            save_data=args.save_data,
            report_format=args.format,
            enable_alerts=args.alerts,
            no_llm=args.no_llm,
            quant_only=args.quant,
            risk_only=args.risk,
            compare=args.compare,
            demo_mode=args.demo,
        )

        if args.monitor:
            asyncio.run(agent.continuous_monitoring(args.interval, **run_kwargs))
        else:
            result = asyncio.run(agent.run_analysis(**run_kwargs))

            if result["status"] == "success" and result.get("report"):
                # Print preview
                print("\n" + "=" * 60)
                print(" REPORT PREVIEW:")
                print("=" * 60)
                preview = result["report"][:2000]
                print(preview + "\n..." if len(result["report"]) > 2000 else preview)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
