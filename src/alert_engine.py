"""
Alert Engine for Economic Intelligence Agent
7 alert types, 4 notification channels, deduplication via SQLite
"""

import os
import json
import hashlib
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ── Alert Data ───────────────────────────────────────────────────

class Alert:
    """Single alert instance"""

    def __init__(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: Optional[Dict] = None,
        dedup_key: Optional[str] = None,
    ):
        self.alert_type = alert_type  # price_threshold, technical_signal, etc.
        self.severity = severity      # critical, high, medium, low
        self.message = message
        self.details = details or {}
        self.dedup_key = dedup_key or self._generate_dedup_key()
        self.triggered_at = datetime.now()

    def _generate_dedup_key(self) -> str:
        raw = f"{self.alert_type}:{self.message[:100]}"
        return hashlib.md5(raw.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "dedup_key": self.dedup_key,
            "triggered_at": self.triggered_at.isoformat(),
        }


# ── Alert Rule Engine ────────────────────────────────────────────

class AlertRuleEngine:
    """Evaluate 7 types of alert rules against market data"""

    def __init__(self, thresholds: Optional[Dict] = None):
        self.thresholds = thresholds or self._default_thresholds()

    @staticmethod
    def _default_thresholds() -> Dict:
        return {
            "price_change_pct": 5.0,      # trigger if >5% daily move
            "volatility_spike": 3.0,       # z-score threshold
            "correlation_breakdown": 0.3,  # correlation change threshold
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "sentiment_shift": 0.4,        # compound sentiment change
        }

    def evaluate(self, data: Dict, quant: Dict, sentiment: Dict, risk: Dict) -> List[Alert]:
        """Run all rules and return triggered alerts"""
        alerts = []
        alerts.extend(self._check_price_thresholds(data))
        alerts.extend(self._check_technical_signals(quant))
        alerts.extend(self._check_volatility_spikes(data))
        alerts.extend(self._check_correlation_breakdowns(quant))
        alerts.extend(self._check_economic_calendar(data))
        alerts.extend(self._check_anomalies(data))
        alerts.extend(self._check_sentiment_shifts(sentiment))
        return alerts

    def _check_price_thresholds(self, data: Dict) -> List[Alert]:
        """Alert on large daily price moves"""
        alerts = []
        threshold = self.thresholds.get("price_change_pct", 5.0)

        for asset_group in ["crypto", "equities", "commodities"]:
            items = []
            group = data.get(asset_group, {})
            if isinstance(group, dict):
                for key in ("top_coins", "indices", "prices", "sectors"):
                    items.extend(group.get(key, []))

            for item in items:
                change = item.change_percent_24h if hasattr(item, "change_percent_24h") else item.get("change_percent_24h", 0)
                symbol = item.symbol if hasattr(item, "symbol") else item.get("symbol", "?")
                change = change or 0

                if abs(change) >= threshold:
                    direction = "surged" if change > 0 else "dropped"
                    severity = "high" if abs(change) >= threshold * 2 else "medium"
                    alerts.append(Alert(
                        alert_type="price_threshold",
                        severity=severity,
                        message=f"{symbol} {direction} {abs(change):.1f}% in 24h",
                        details={"symbol": symbol, "change_pct": change, "asset_group": asset_group},
                        dedup_key=f"price:{symbol}:{datetime.now().strftime('%Y%m%d')}",
                    ))
        return alerts

    def _check_technical_signals(self, quant: Dict) -> List[Alert]:
        """Alert on extreme RSI, MACD crossovers"""
        alerts = []
        signals = quant.get("technical_signals", {})
        for symbol, sig in signals.items():
            signal = sig.get("signal", "neutral")
            if signal in ("bullish", "bearish"):
                alerts.append(Alert(
                    alert_type="technical_signal",
                    severity="medium",
                    message=f"{symbol}: {signal} technical signal",
                    details=sig,
                    dedup_key=f"tech:{symbol}:{signal}:{datetime.now().strftime('%Y%m%d')}",
                ))
        return alerts

    def _check_volatility_spikes(self, data: Dict) -> List[Alert]:
        """Alert on unusual volatility (z-score > threshold)"""
        alerts = []
        crypto = data.get("crypto", {}).get("top_coins", [])
        changes = []
        for c in crypto:
            ch = c.change_percent_24h if hasattr(c, "change_percent_24h") else c.get("change_percent_24h", 0)
            changes.append(abs(ch or 0))

        if len(changes) > 5:
            mean = sum(changes) / len(changes)
            import math
            std = math.sqrt(sum((x - mean) ** 2 for x in changes) / len(changes)) if changes else 1
            threshold = self.thresholds.get("volatility_spike", 3.0)

            for c in crypto:
                ch = abs(c.change_percent_24h if hasattr(c, "change_percent_24h") else c.get("change_percent_24h", 0) or 0)
                sym = c.symbol if hasattr(c, "symbol") else c.get("symbol", "?")
                z = (ch - mean) / std if std > 0 else 0
                if z > threshold:
                    alerts.append(Alert(
                        alert_type="volatility_spike",
                        severity="high",
                        message=f"{sym}: volatility spike (z={z:.1f})",
                        details={"symbol": sym, "z_score": round(z, 2), "change_pct": ch},
                        dedup_key=f"vol:{sym}:{datetime.now().strftime('%Y%m%d')}",
                    ))
        return alerts

    def _check_correlation_breakdowns(self, quant: Dict) -> List[Alert]:
        """Alert on significant correlation divergences"""
        alerts = []
        divs = quant.get("correlations", {}).get("divergences", [])
        for div in divs:
            alerts.append(Alert(
                alert_type="correlation_breakdown",
                severity="medium",
                message=f"Correlation breakdown: {div['pair'][0]} vs {div['pair'][1]} (r={div['correlation']:.2f})",
                details=div,
            ))
        return alerts

    def _check_economic_calendar(self, data: Dict) -> List[Alert]:
        """Alert on upcoming high-impact economic events"""
        alerts = []
        events = data.get("economic_events", [])
        for event in events:
            impact = event.get("impact", "low")
            if impact == "high":
                title = event.get("event", event.get("title", "Unknown event"))
                alerts.append(Alert(
                    alert_type="economic_calendar",
                    severity="medium",
                    message=f"Upcoming high-impact event: {title}",
                    details=event,
                    dedup_key=f"cal:{title}",
                ))
        return alerts

    def _check_anomalies(self, data: Dict) -> List[Alert]:
        """Alert on statistical anomalies using z-scores"""
        # Already covered by volatility spikes; this is a placeholder for future ml-based anomalies
        return []

    def _check_sentiment_shifts(self, sentiment: Dict) -> List[Alert]:
        """Alert on significant sentiment shifts"""
        alerts = []
        fg = sentiment.get("fear_greed", {})
        value = fg.get("value", 50)
        label = fg.get("label", "neutral")

        if value < 20 or value > 80:
            severity = "high" if (value < 10 or value > 90) else "medium"
            alerts.append(Alert(
                alert_type="sentiment_shift",
                severity=severity,
                message=f"Fear/Greed Index at {value:.0f} ({label})",
                details=fg,
                dedup_key=f"fg:{label}:{datetime.now().strftime('%Y%m%d')}",
            ))

        news = sentiment.get("news_sentiment", {})
        compound = news.get("compound", 0)
        threshold = self.thresholds.get("sentiment_shift", 0.4)
        if abs(compound) >= threshold:
            direction = "strongly bullish" if compound > 0 else "strongly bearish"
            alerts.append(Alert(
                alert_type="sentiment_shift",
                severity="medium",
                message=f"News sentiment is {direction} (score={compound:.2f})",
                details=news,
                dedup_key=f"sent:{direction}:{datetime.now().strftime('%Y%m%d')}",
            ))

        return alerts


# ── Alert Notifier ───────────────────────────────────────────────

class AlertNotifier:
    """Dispatch alerts to 4 channels: console, file, webhook, email"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def notify(self, alert: Alert, channels: Optional[List[str]] = None) -> None:
        channels = channels or ["console"]
        for ch in channels:
            try:
                if ch == "console":
                    self._console(alert)
                elif ch == "file":
                    self._file_log(alert)
                elif ch == "webhook":
                    self._webhook(alert)
                elif ch == "email":
                    self._email(alert)
            except Exception as e:
                logger.error(f"Notification failed ({ch}): {e}")

    def _console(self, alert: Alert) -> None:
        icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        icon = icons.get(alert.severity, "⚪")
        print(f"  {icon} [{alert.severity.upper()}] {alert.message}")

    def _file_log(self, alert: Alert) -> None:
        log_path = self.config.get("alert_log", "data/alerts.log")
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(alert.to_dict()) + "\n")

    def _webhook(self, alert: Alert) -> None:
        if not HAS_REQUESTS:
            return
        url = self.config.get("webhook_url", "")
        if not url:
            return
        # Supports both Slack and Discord webhook format
        payload = {
            "text": f"[{alert.severity.upper()}] {alert.message}",
            "content": f"**[{alert.severity.upper()}]** {alert.message}",
        }
        try:
            _requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Webhook failed: {e}")

    def _email(self, alert: Alert) -> None:
        smtp_host = self.config.get("smtp_host", "")
        smtp_port = self.config.get("smtp_port", 587)
        smtp_user = self.config.get("smtp_user", "")
        smtp_pass = self.config.get("smtp_pass", "")
        to_addr = self.config.get("email_to", "")

        if not all([smtp_host, smtp_user, smtp_pass, to_addr]):
            return

        msg = MIMEText(f"Alert: {alert.message}\n\nDetails: {json.dumps(alert.details, indent=2)}")
        msg["Subject"] = f"[{alert.severity.upper()}] EconAgent Alert: {alert.alert_type}"
        msg["From"] = smtp_user
        msg["To"] = to_addr

        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        except Exception as e:
            logger.error(f"Email failed: {e}")


# ── Alert Engine (Facade) ───────────────────────────────────────

class AlertEngine:
    """Facade: evaluate rules, deduplicate, persist, notify"""

    def __init__(self, config: Optional[Dict] = None, store=None):
        self.config = config or {}
        self.rules = AlertRuleEngine(self.config.get("thresholds"))
        self.notifier = AlertNotifier(self.config.get("notifications", {}))
        self.store = store  # DataStore instance (optional)
        self.channels = self.config.get("channels", ["console"])

    def evaluate_and_notify(
        self, data: Dict, quant: Dict, sentiment: Dict, risk: Dict
    ) -> List[Dict]:
        """Run all rules, persist new alerts, send notifications. Returns list of new alert dicts."""
        raw_alerts = self.rules.evaluate(data, quant, sentiment, risk)
        new_alerts = []

        for alert in raw_alerts:
            # Deduplicate via storage
            is_new = True
            if self.store:
                is_new = self.store.store_alert(
                    alert_type=alert.alert_type,
                    severity=alert.severity,
                    message=alert.message,
                    details=json.dumps(alert.details),
                    dedup_key=alert.dedup_key,
                )

            if is_new:
                self.notifier.notify(alert, self.channels)
                new_alerts.append(alert.to_dict())

        logger.info(f"Alerts: {len(raw_alerts)} evaluated, {len(new_alerts)} new")
        return new_alerts
