"""
SQLite Storage Layer for Economic Intelligence Agent
WAL mode, 6 tables, schema versioning, data retention
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

VALID_TABLES = frozenset([
    "assets", "price_history", "economic_indicators",
    "news", "alerts", "analysis_history", "schema_version",
])

SCHEMA_SQL = """
-- Assets master table
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(symbol, asset_class)
);

-- Price history
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    price REAL NOT NULL,
    volume REAL,
    change_percent REAL,
    market_cap REAL,
    additional_data TEXT,
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);
CREATE INDEX IF NOT EXISTS idx_price_history_asset_ts ON price_history(asset_id, timestamp);

-- Economic indicators
CREATE TABLE IF NOT EXISTS economic_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id TEXT NOT NULL,
    name TEXT NOT NULL,
    value REAL NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    metadata TEXT
);
CREATE INDEX IF NOT EXISTS idx_econ_series_ts ON economic_indicators(series_id, timestamp);

-- News
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    source TEXT NOT NULL,
    published_at TEXT NOT NULL,
    url TEXT,
    sentiment_score REAL,
    categories TEXT,
    stored_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    triggered_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'active',
    dedup_key TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status, triggered_at);

-- Analysis history
CREATE TABLE IF NOT EXISTS analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    market_tone TEXT,
    key_theme TEXT,
    summary_json TEXT,
    report_path TEXT,
    report_format TEXT DEFAULT 'markdown'
);

-- Schema version
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class DataStore:
    """SQLite persistence layer with WAL mode"""

    def __init__(self, db_path: str = "data/economic_intelligence.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database with WAL mode and schema"""
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA_SQL)

        # Check and update schema version
        cur = self.conn.execute("SELECT MAX(version) FROM schema_version")
        row = cur.fetchone()
        current = row[0] if row[0] is not None else 0

        if current < SCHEMA_VERSION:
            self.conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            self.conn.commit()
            logger.info(f"Database schema at version {SCHEMA_VERSION}")

    # ── Asset CRUD ────────────────────────────────────────────────

    def upsert_asset(self, symbol: str, name: str, asset_class: str) -> int:
        """Insert or get existing asset, return asset_id"""
        cur = self.conn.execute(
            "SELECT id FROM assets WHERE symbol = ? AND asset_class = ?",
            (symbol, asset_class),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        cur = self.conn.execute(
            "INSERT INTO assets (symbol, name, asset_class) VALUES (?, ?, ?)",
            (symbol, name, asset_class),
        )
        self.conn.commit()
        return cur.lastrowid

    # ── Price History ─────────────────────────────────────────────

    def store_price(
        self,
        asset_id: int,
        price: float,
        volume: Optional[float] = None,
        change_percent: Optional[float] = None,
        market_cap: Optional[float] = None,
        additional_data: Optional[Dict] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        ts = timestamp or datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO price_history
               (asset_id, timestamp, price, volume, change_percent, market_cap, additional_data)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, ts, price, volume, change_percent, market_cap,
             json.dumps(additional_data) if additional_data else None),
        )

    def get_price_history(
        self, symbol: str, asset_class: str, days: int = 30
    ) -> List[Dict]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT ph.timestamp, ph.price, ph.volume, ph.change_percent, ph.market_cap
               FROM price_history ph
               JOIN assets a ON a.id = ph.asset_id
               WHERE a.symbol = ? AND a.asset_class = ? AND ph.timestamp >= ?
               ORDER BY ph.timestamp""",
            (symbol, asset_class, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Economic Indicators ──────────────────────────────────────

    def store_indicator(
        self, series_id: str, name: str, value: float, source: str,
        timestamp: Optional[str] = None, metadata: Optional[Dict] = None,
    ) -> None:
        ts = timestamp or datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO economic_indicators
               (series_id, name, value, timestamp, source, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (series_id, name, value, ts, source,
             json.dumps(metadata) if metadata else None),
        )
        self.conn.commit()

    def get_latest_indicator(self, series_id: str) -> Optional[Dict]:
        row = self.conn.execute(
            """SELECT * FROM economic_indicators
               WHERE series_id = ? ORDER BY timestamp DESC LIMIT 1""",
            (series_id,),
        ).fetchone()
        return dict(row) if row else None

    # ── News ─────────────────────────────────────────────────────

    def store_news(
        self, title: str, source: str, published_at: str,
        description: Optional[str] = None, url: Optional[str] = None,
        sentiment_score: Optional[float] = None, categories: Optional[List[str]] = None,
    ) -> None:
        self.conn.execute(
            """INSERT INTO news
               (title, description, source, published_at, url, sentiment_score, categories)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, description, source, published_at, url, sentiment_score,
             json.dumps(categories) if categories else None),
        )
        self.conn.commit()

    def get_recent_news(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        rows = self.conn.execute(
            """SELECT * FROM news WHERE published_at >= ?
               ORDER BY published_at DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Alerts ───────────────────────────────────────────────────

    def store_alert(
        self, alert_type: str, severity: str, message: str,
        details: Optional[str] = None, dedup_key: Optional[str] = None,
    ) -> bool:
        """Store alert, return False if duplicate"""
        try:
            self.conn.execute(
                """INSERT INTO alerts (type, severity, message, details, dedup_key)
                   VALUES (?, ?, ?, ?, ?)""",
                (alert_type, severity, message, details, dedup_key),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Duplicate dedup_key
            return False

    def get_active_alerts(self, limit: int = 50) -> List[Dict]:
        rows = self.conn.execute(
            """SELECT * FROM alerts WHERE status = 'active'
               ORDER BY triggered_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def resolve_alert(self, alert_id: int) -> None:
        self.conn.execute(
            "UPDATE alerts SET status = 'resolved' WHERE id = ?",
            (alert_id,),
        )
        self.conn.commit()

    # ── Analysis History ─────────────────────────────────────────

    def store_analysis(
        self, market_tone: str, key_theme: str,
        summary: Dict, report_path: Optional[str] = None,
        report_format: str = "markdown",
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO analysis_history
               (market_tone, key_theme, summary_json, report_path, report_format)
               VALUES (?, ?, ?, ?, ?)""",
            (market_tone, key_theme, json.dumps(summary), report_path, report_format),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_last_analysis(self) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM analysis_history ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if row:
            result = dict(row)
            if result.get("summary_json"):
                try:
                    result["summary"] = json.loads(result["summary_json"])
                except json.JSONDecodeError:
                    result["summary"] = {}
            return result
        return None

    # ── Bulk Operations ──────────────────────────────────────────

    def store_market_data_batch(self, market_data_list: list) -> int:
        """Store a batch of MarketData objects. Returns count stored."""
        count = 0
        for md in market_data_list:
            if hasattr(md, "symbol"):
                asset_id = self.upsert_asset(md.symbol, md.name, md.asset_class)
                self.store_price(
                    asset_id=asset_id,
                    price=md.price,
                    volume=md.volume,
                    change_percent=md.change_percent_24h,
                    market_cap=md.market_cap,
                    additional_data=md.additional_data,
                    timestamp=md.timestamp.isoformat() if hasattr(md.timestamp, 'isoformat') else str(md.timestamp),
                )
                count += 1
            elif isinstance(md, dict):
                symbol = md.get("symbol", "UNKNOWN")
                asset_id = self.upsert_asset(symbol, md.get("name", symbol), md.get("asset_class", "unknown"))
                self.store_price(
                    asset_id=asset_id,
                    price=md.get("price", 0),
                    volume=md.get("volume"),
                    change_percent=md.get("change_percent_24h"),
                    market_cap=md.get("market_cap"),
                    timestamp=md.get("timestamp", datetime.now().isoformat()),
                )
                count += 1
        self.conn.commit()
        return count

    # ── Maintenance ──────────────────────────────────────────────

    def cleanup(self, retention_days: int = 90) -> Dict[str, int]:
        """Delete data older than retention_days. Returns counts per table."""
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        counts = {}

        for table, col in [
            ("price_history", "timestamp"),
            ("economic_indicators", "timestamp"),
            ("news", "published_at"),
            ("alerts", "triggered_at"),
            ("analysis_history", "timestamp"),
        ]:
            if table not in VALID_TABLES:
                raise ValueError(f"Invalid table name: {table}")
            cur = self.conn.execute(
                f"DELETE FROM {table} WHERE {col} < ?", (cutoff,)
            )
            counts[table] = cur.rowcount

        self.conn.commit()
        logger.info(f"Cleanup (>{retention_days}d): {counts}")
        return counts

    def get_stats(self) -> Dict[str, int]:
        """Get row counts for all tables"""
        stats = {}
        for table in ["assets", "price_history", "economic_indicators", "news", "alerts", "analysis_history"]:
            if table not in VALID_TABLES:
                raise ValueError(f"Invalid table name: {table}")
            cur = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cur.fetchone()[0]
        return stats

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
