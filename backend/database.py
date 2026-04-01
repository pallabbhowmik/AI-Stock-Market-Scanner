"""
Database Layer
Supports both Supabase (production) and SQLite (local development).
"""
import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional

import math

import pandas as pd

from backend import config

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 15
_query_cache: dict[tuple, tuple[float, object]] = {}


def _make_cache_key(namespace: str, *parts) -> tuple:
    return (namespace,) + parts


def _cache_get(namespace: str, *parts):
    key = _make_cache_key(namespace, *parts)
    entry = _query_cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if expires_at <= datetime.now().timestamp():
        _query_cache.pop(key, None)
        return None
    return value


def _cache_set(namespace: str, value, *parts):
    key = _make_cache_key(namespace, *parts)
    _query_cache[key] = (datetime.now().timestamp() + _CACHE_TTL_SECONDS, value)
    return value


def _cache_invalidate(prefixes: set[str]):
    for key in list(_query_cache.keys()):
        if key and key[0] in prefixes:
            _query_cache.pop(key, None)


def _sanitize(obj):
    """Replace NaN / Inf with None so JSON serialisation succeeds."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return _sanitize_value(obj)


def _sanitize_value(obj):
    """Convert numpy/non-standard types to native Python types for JSON."""
    if isinstance(obj, dict):
        return {k: _sanitize_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_value(v) for v in obj]
    # Convert numpy scalars to native Python
    try:
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            v = float(obj)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj

# ─── SQLite Implementation ───────────────────────────────────────────────────

def _get_sqlite_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.SQLITE_PATH), exist_ok=True)
    return sqlite3.connect(config.SQLITE_PATH)


def init_sqlite():
    """Create SQLite tables."""
    conn = _get_sqlite_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS scanned_stocks (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT,
            last_price REAL,
            market_cap REAL,
            avg_volume REAL,
            daily_volatility REAL,
            last_updated TEXT
        );
        CREATE TABLE IF NOT EXISTS stock_data (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER,
            PRIMARY KEY (symbol, date)
        );
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            signal TEXT,
            confidence REAL,
            ai_probability REAL,
            momentum_score REAL,
            breakout_score REAL,
            volume_spike_score REAL,
            opportunity_score REAL,
            explanation TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT,
            symbol TEXT NOT NULL,
            signal TEXT,
            confidence REAL,
            opportunity_score REAL,
            explanation TEXT,
            rank INTEGER
        );
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            finished_at TEXT,
            stocks_scanned INTEGER,
            stocks_passed_filter INTEGER,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS strategy_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            symbol TEXT,
            signal TEXT,
            actual_return REAL,
            won INTEGER,
            date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS meta_strategy_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            regime TEXT,
            weights TEXT,
            explanation TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS training_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id TEXT,
            started_at TEXT,
            finished_at TEXT,
            status TEXT,
            accuracy REAL,
            auc REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            profit_factor REAL,
            dataset_size INTEGER,
            stocks_trained INTEGER,
            duration_seconds REAL,
            deployed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_pred_symbol ON predictions(symbol);
        CREATE INDEX IF NOT EXISTS idx_pred_date ON predictions(date);
        CREATE INDEX IF NOT EXISTS idx_watchlist_date ON watchlist(date);
        CREATE INDEX IF NOT EXISTS idx_strat_perf_strategy ON strategy_performance(strategy);
        CREATE INDEX IF NOT EXISTS idx_meta_state_date ON meta_strategy_state(date);
        CREATE INDEX IF NOT EXISTS idx_training_log_date ON training_log(started_at);

        CREATE TABLE IF NOT EXISTS paper_portfolio (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT,
            quantity INTEGER,
            price REAL,
            value REAL,
            costs_json TEXT,
            pnl REAL,
            pnl_pct REAL,
            entry_price REAL,
            status TEXT,
            mode TEXT DEFAULT 'PAPER',
            timestamp TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_paper_trades_ts ON paper_trades(timestamp);

        CREATE TABLE IF NOT EXISTS intraday_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            horizon TEXT NOT NULL,
            signal TEXT,
            confidence REAL,
            probability REAL,
            entry_price REAL,
            stop_loss REAL,
            target_price REAL,
            risk_reward REAL,
            model_votes TEXT,
            consensus_direction TEXT,
            consensus_agreement REAL,
            explanation TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_intra_pred_symbol ON intraday_predictions(symbol);
        CREATE INDEX IF NOT EXISTS idx_intra_pred_ts ON intraday_predictions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_intra_pred_horizon ON intraday_predictions(horizon);
    """)
    conn.commit()
    conn.close()
    logger.info("SQLite database initialized at %s", config.SQLITE_PATH)


# ─── Supabase Implementation ─────────────────────────────────────────────────

def _get_supabase():
    from supabase import create_client
    return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)


# ─── Unified Interface ───────────────────────────────────────────────────────

def init_db():
    """Initialize the database (SQLite or Supabase tables)."""
    if config.USE_SQLITE:
        init_sqlite()
    else:
        logger.info("Using Supabase. Ensure tables are created via schema.sql")


def upsert_scanned_stocks(stocks: list[dict]):
    """Insert or update the scanned stocks list."""
    if not stocks:
        return
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        for s in stocks:
            conn.execute("""
                INSERT OR REPLACE INTO scanned_stocks
                (symbol, name, sector, last_price, market_cap, avg_volume, daily_volatility, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s.get("symbol"), s.get("name", ""), s.get("sector", ""),
                s.get("last_price", 0), s.get("market_cap", 0),
                s.get("avg_volume", 0), s.get("daily_volatility", 0),
                datetime.now().isoformat(),
            ))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        for s in stocks:
            s["last_updated"] = datetime.now().isoformat()
        sb.table("scanned_stocks").upsert(_sanitize(stocks)).execute()
    _cache_invalidate({"scanned_stocks"})


def save_stock_data(df: pd.DataFrame, symbol: str):
    """Save OHLCV data for a symbol."""
    if df.empty:
        return
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        for _, row in df.iterrows():
            conn.execute("""
                INSERT OR REPLACE INTO stock_data (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
                row["open"], row["high"], row["low"], row["close"], int(row["volume"]),
            ))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        records = df.to_dict("records")
        for r in records:
            r["symbol"] = symbol
            r["date"] = str(r["date"])
        sb.table("stock_data").upsert(_sanitize(records)).execute()
    _cache_invalidate({"stock_data"})


def save_predictions(predictions: list[dict]):
    """Save prediction results."""
    if not predictions:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        # Clear today's predictions first
        conn.execute("DELETE FROM predictions WHERE date = ?", (today,))
        for p in predictions:
            conn.execute("""
                INSERT INTO predictions
                (symbol, date, signal, confidence, ai_probability, momentum_score,
                 breakout_score, volume_spike_score, opportunity_score, explanation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["symbol"], today, p.get("signal", "HOLD"),
                p.get("confidence", 0), p.get("ai_probability", 0.5),
                p.get("momentum_score", 0), p.get("breakout_score", 0),
                p.get("volume_spike_score", 0), p.get("opportunity_score", 0),
                p.get("explanation", ""),
            ))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        sb.table("predictions").delete().eq("date", today).execute()
        rows = []
        for p in predictions:
            rows.append({
                "symbol": p["symbol"],
                "date": today,
                "signal": p.get("signal", "HOLD"),
                "confidence": p.get("confidence", 0),
                "ai_probability": p.get("ai_probability", 0.5),
                "momentum_score": p.get("momentum_score", 0),
                "breakout_score": p.get("breakout_score", 0),
                "volume_spike_score": p.get("volume_spike_score", 0),
                "opportunity_score": p.get("opportunity_score", 0),
                "explanation": p.get("explanation", ""),
            })
        sb.table("predictions").insert(_sanitize(rows)).execute()
    _cache_invalidate({"predictions"})


def clear_predictions(date: Optional[str] = None):
    """Delete predictions for a specific date."""
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.execute("DELETE FROM predictions WHERE date = ?", (target_date,))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        sb.table("predictions").delete().eq("date", target_date).execute()
    _cache_invalidate({"predictions"})


def save_predictions_chunk(predictions: list[dict], date: Optional[str] = None):
    """Upsert a subset of predictions for the given date without clearing the whole day."""
    if not predictions:
        return
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    symbols = [p["symbol"] for p in predictions if p.get("symbol")]
    if not symbols:
        return

    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        placeholders = ",".join("?" for _ in symbols)
        conn.execute(
            f"DELETE FROM predictions WHERE date = ? AND symbol IN ({placeholders})",
            (target_date, *symbols),
        )
        for p in predictions:
            conn.execute("""
                INSERT INTO predictions
                (symbol, date, signal, confidence, ai_probability, momentum_score,
                 breakout_score, volume_spike_score, opportunity_score, explanation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["symbol"], target_date, p.get("signal", "HOLD"),
                p.get("confidence", 0), p.get("ai_probability", 0.5),
                p.get("momentum_score", 0), p.get("breakout_score", 0),
                p.get("volume_spike_score", 0), p.get("opportunity_score", 0),
                p.get("explanation", ""),
            ))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        sb.table("predictions").delete().eq("date", target_date).in_("symbol", symbols).execute()
        rows = []
        for p in predictions:
            rows.append({
                "symbol": p["symbol"],
                "date": target_date,
                "signal": p.get("signal", "HOLD"),
                "confidence": p.get("confidence", 0),
                "ai_probability": p.get("ai_probability", 0.5),
                "momentum_score": p.get("momentum_score", 0),
                "breakout_score": p.get("breakout_score", 0),
                "volume_spike_score": p.get("volume_spike_score", 0),
                "opportunity_score": p.get("opportunity_score", 0),
                "explanation": p.get("explanation", ""),
            })
        sb.table("predictions").insert(_sanitize(rows)).execute()
    _cache_invalidate({"predictions"})


def save_watchlist(watchlist: list[dict]):
    """Save today's watchlist."""
    if not watchlist:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.execute("DELETE FROM watchlist WHERE date = ?", (today,))
        for w in watchlist:
            conn.execute("""
                INSERT INTO watchlist
                (date, category, symbol, signal, confidence, opportunity_score, explanation, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today, w.get("category", ""), w["symbol"],
                w.get("signal", "HOLD"), w.get("confidence", 0),
                w.get("opportunity_score", 0), w.get("explanation", ""),
                w.get("rank", 0),
            ))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        sb.table("watchlist").delete().eq("date", today).execute()
        rows = []
        for w in watchlist:
            rows.append({
                "date": today,
                "category": w.get("category", ""),
                "symbol": w["symbol"],
                "signal": w.get("signal", "HOLD"),
                "confidence": w.get("confidence", 0),
                "opportunity_score": w.get("opportunity_score", 0),
                "explanation": w.get("explanation", ""),
                "rank": w.get("rank", 0),
            })
        sb.table("watchlist").insert(_sanitize(rows)).execute()
    _cache_invalidate({"watchlist"})


def replace_watchlist(date: str, watchlist: list[dict]):
    """Replace the watchlist for a specific date."""
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.execute("DELETE FROM watchlist WHERE date = ?", (date,))
        for w in watchlist:
            conn.execute("""
                INSERT INTO watchlist
                (date, category, symbol, signal, confidence, opportunity_score, explanation, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date, w.get("category", ""), w["symbol"],
                w.get("signal", "HOLD"), w.get("confidence", 0),
                w.get("opportunity_score", 0), w.get("explanation", ""),
                w.get("rank", 0),
            ))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        sb.table("watchlist").delete().eq("date", date).execute()
        rows = []
        for w in watchlist:
            rows.append({
                "date": date,
                "category": w.get("category", ""),
                "symbol": w["symbol"],
                "signal": w.get("signal", "HOLD"),
                "confidence": w.get("confidence", 0),
                "opportunity_score": w.get("opportunity_score", 0),
                "explanation": w.get("explanation", ""),
                "rank": w.get("rank", 0),
            })
        if rows:
            sb.table("watchlist").insert(_sanitize(rows)).execute()
    _cache_invalidate({"watchlist"})


def save_scan_log(started_at: str, finished_at: str, stocks_scanned: int,
                  stocks_passed: int, status: str):
    """Log a scan event."""
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.execute("""
            INSERT INTO scan_log (started_at, finished_at, stocks_scanned, stocks_passed_filter, status)
            VALUES (?, ?, ?, ?, ?)
        """, (started_at, finished_at, stocks_scanned, stocks_passed, status))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        sb.table("scan_log").insert({
            "started_at": started_at, "finished_at": finished_at,
            "stocks_scanned": stocks_scanned, "stocks_passed_filter": stocks_passed,
            "status": status,
        }).execute()
    _cache_invalidate({"scan_logs"})


def get_predictions(date: Optional[str] = None) -> list[dict]:
    """Get predictions for a date (default: today, falls back to most recent)."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    cached = _cache_get("predictions", date)
    if cached is not None:
        return cached
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM predictions WHERE date = ? ORDER BY opportunity_score DESC", (date,)
        ).fetchall()
        if not rows:
            # Fallback: get most recent date with predictions
            row = conn.execute(
                "SELECT date FROM predictions ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if row:
                rows = conn.execute(
                    "SELECT * FROM predictions WHERE date = ? ORDER BY opportunity_score DESC",
                    (row["date"],)
                ).fetchall()
        conn.close()
        return _cache_set("predictions", [dict(r) for r in rows], date)
    else:
        sb = _get_supabase()
        res = sb.table("predictions").select("*").eq("date", date).order("opportunity_score", desc=True).execute()
        if not res.data:
            # Fallback: get most recent date with predictions
            latest = sb.table("predictions").select("date").order("date", desc=True).limit(1).execute()
            if latest.data:
                latest_date = latest.data[0]["date"]
                res = sb.table("predictions").select("*").eq("date", latest_date).order("opportunity_score", desc=True).execute()
        return _cache_set("predictions", res.data, date)


def get_watchlist(date: Optional[str] = None, category: Optional[str] = None) -> list[dict]:
    """Get watchlist for a date (falls back to most recent)."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    cached = _cache_get("watchlist", date, category or "")
    if cached is not None:
        return cached
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        if category:
            rows = conn.execute(
                "SELECT * FROM watchlist WHERE date = ? AND category = ? ORDER BY rank",
                (date, category)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM watchlist WHERE date = ? ORDER BY category, rank", (date,)
            ).fetchall()
        if not rows:
            # Fallback: most recent date
            row = conn.execute(
                "SELECT date FROM watchlist ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if row:
                fallback_date = row["date"]
                if category:
                    rows = conn.execute(
                        "SELECT * FROM watchlist WHERE date = ? AND category = ? ORDER BY rank",
                        (fallback_date, category)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM watchlist WHERE date = ? ORDER BY category, rank",
                        (fallback_date,)
                    ).fetchall()
        conn.close()
        return _cache_set("watchlist", [dict(r) for r in rows], date, category or "")
    else:
        sb = _get_supabase()
        q = sb.table("watchlist").select("*").eq("date", date)
        if category:
            q = q.eq("category", category)
        result = q.order("rank").execute()
        if not result.data:
            # Fallback: most recent date
            latest = sb.table("watchlist").select("date").order("date", desc=True).limit(1).execute()
            if latest.data:
                q = sb.table("watchlist").select("*").eq("date", latest.data[0]["date"])
                if category:
                    q = q.eq("category", category)
                result = q.order("rank").execute()
        return _cache_set("watchlist", result.data, date, category or "")


def get_stock_data(symbol: str, limit: int = 365) -> pd.DataFrame:
    """Get stored OHLCV data for a symbol."""
    cached = _cache_get("stock_data", symbol, limit)
    if cached is not None:
        return cached.copy()
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        df = pd.read_sql_query(
            "SELECT * FROM stock_data WHERE symbol = ? ORDER BY date DESC LIMIT ?",
            conn, params=(symbol, limit)
        )
        conn.close()
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
        return _cache_set("stock_data", df.copy(), symbol, limit).copy()
    else:
        sb = _get_supabase()
        res = sb.table("stock_data").select("*").eq("symbol", symbol).order("date", desc=True).limit(limit).execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
        return _cache_set("stock_data", df.copy(), symbol, limit).copy()


def get_scan_logs(limit: int = 10) -> list[dict]:
    """Get recent scan logs."""
    cached = _cache_get("scan_logs", limit)
    if cached is not None:
        return cached
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM scan_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return _cache_set("scan_logs", [dict(r) for r in rows], limit)
    else:
        sb = _get_supabase()
        data = sb.table("scan_log").select("*").order("id", desc=True).limit(limit).execute().data
        return _cache_set("scan_logs", data, limit)


def get_all_scanned_stocks() -> list[dict]:
    """Get the full scanned stocks list."""
    cached = _cache_get("scanned_stocks", "all")
    if cached is not None:
        return cached
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM scanned_stocks ORDER BY symbol").fetchall()
        conn.close()
        return _cache_set("scanned_stocks", [dict(r) for r in rows], "all")
    else:
        sb = _get_supabase()
        data = sb.table("scanned_stocks").select("*").order("symbol").execute().data
        return _cache_set("scanned_stocks", data, "all")


def save_meta_strategy_state(regime: str, weights: dict, explanation: str):
    """Save the current meta-strategy state."""
    today = datetime.now().strftime("%Y-%m-%d")
    weights_json = json.dumps(weights)
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.execute("DELETE FROM meta_strategy_state WHERE date = ?", (today,))
        conn.execute("""
            INSERT INTO meta_strategy_state (date, regime, weights, explanation)
            VALUES (?, ?, ?, ?)
        """, (today, regime, weights_json, explanation))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        sb.table("meta_strategy_state").delete().eq("date", today).execute()
        sb.table("meta_strategy_state").insert(_sanitize({
            "date": today, "regime": regime,
            "weights": weights_json, "explanation": explanation,
        })).execute()


def get_meta_strategy_state() -> Optional[dict]:
    """Get the latest meta-strategy state."""
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM meta_strategy_state ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            d = dict(row)
            d["weights"] = json.loads(d["weights"]) if d.get("weights") else {}
            return d
        return None
    else:
        sb = _get_supabase()
        res = sb.table("meta_strategy_state").select("*").order("id", desc=True).limit(1).execute()
        if res.data:
            d = res.data[0]
            d["weights"] = json.loads(d["weights"]) if d.get("weights") else {}
            return d
        return None


def save_training_log(result: dict):
    """Persist a training pipeline result."""
    metrics = result.get("metrics", {})
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.execute("""
            INSERT INTO training_log
            (version_id, started_at, finished_at, status,
             accuracy, auc, sharpe_ratio, max_drawdown, profit_factor,
             dataset_size, stocks_trained, duration_seconds, deployed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.get("version_id", ""),
            result.get("started_at", ""),
            result.get("finished_at", ""),
            result.get("status", ""),
            metrics.get("accuracy", 0),
            metrics.get("auc", 0),
            metrics.get("sharpe_ratio", 0),
            metrics.get("max_drawdown", 0),
            metrics.get("profit_factor", 0),
            result.get("dataset_size", 0),
            result.get("stocks_trained", 0),
            result.get("duration_seconds", 0),
            1 if result.get("deployed") else 0,
        ))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        sb.table("training_log").insert(_sanitize({
            "version_id": result.get("version_id", ""),
            "started_at": result.get("started_at", ""),
            "finished_at": result.get("finished_at", ""),
            "status": result.get("status", ""),
            "accuracy": metrics.get("accuracy", 0),
            "auc": metrics.get("auc", 0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0),
            "max_drawdown": metrics.get("max_drawdown", 0),
            "profit_factor": metrics.get("profit_factor", 0),
            "dataset_size": result.get("dataset_size", 0),
            "stocks_trained": result.get("stocks_trained", 0),
            "duration_seconds": result.get("duration_seconds", 0),
            "deployed": 1 if result.get("deployed") else 0,
        })).execute()


def get_training_logs(limit: int = 20) -> list[dict]:
    """Get recent training pipeline logs."""
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM training_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    else:
        sb = _get_supabase()
        return sb.table("training_log").select("*").order("id", desc=True).limit(limit).execute().data


# ─── Paper Trading ───────────────────────────────────────────────────────────

def save_paper_portfolio(port: dict):
    """Persist paper portfolio state (single row, id=1)."""
    data_json = json.dumps(port)
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.execute("""
            INSERT OR REPLACE INTO paper_portfolio (id, data, updated_at)
            VALUES (1, ?, datetime('now'))
        """, (data_json,))
        conn.commit()
        conn.close()


def get_paper_portfolio() -> Optional[dict]:
    """Load paper portfolio state."""
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT data FROM paper_portfolio WHERE id = 1").fetchone()
        conn.close()
        if row:
            return json.loads(row["data"])
    return None


def save_paper_trade(trade: dict):
    """Record a single paper trade."""
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.execute("""
            INSERT INTO paper_trades
            (symbol, side, order_type, quantity, price, value,
             costs_json, pnl, pnl_pct, entry_price, status, mode, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.get("symbol"), trade.get("side"), trade.get("order_type"),
            trade.get("quantity"), trade.get("price"), trade.get("value"),
            json.dumps(trade.get("costs", {})),
            trade.get("pnl"), trade.get("pnl_pct"),
            trade.get("entry_price"), trade.get("status", "filled"),
            trade.get("mode", "PAPER"),
            trade.get("timestamp", datetime.now().isoformat()),
        ))
        conn.commit()
        conn.close()


def get_paper_trades(limit: int = 50) -> list[dict]:
    """Get recent paper trades."""
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM paper_trades ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        trades = []
        for r in rows:
            d = dict(r)
            d["costs"] = json.loads(d.pop("costs_json", "{}") or "{}")
            trades.append(d)
        return trades
    return []


def clear_paper_trades():
    """Delete all paper trades (used on portfolio reset)."""
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.execute("DELETE FROM paper_trades")
        conn.commit()
        conn.close()


# ─── Intraday Predictions ───────────────────────────────────────────────────

def save_intraday_predictions(predictions: list[dict]):
    """Save intraday prediction results."""
    if not predictions:
        return
    now = datetime.now().isoformat()
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        for p in predictions:
            conn.execute("""
                INSERT INTO intraday_predictions
                (symbol, timestamp, horizon, signal, confidence, probability,
                 entry_price, stop_loss, target_price, risk_reward,
                 model_votes, consensus_direction, consensus_agreement, explanation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["symbol"], now, p.get("horizon", "15m"),
                p.get("signal", "HOLD"), p.get("confidence", 0),
                p.get("probability", 0.5),
                p.get("entry_price", 0), p.get("stop_loss", 0),
                p.get("target_price", 0), p.get("risk_reward", 0),
                json.dumps(_sanitize_value(p.get("model_votes", {}))),
                p.get("consensus_direction", ""),
                p.get("consensus_agreement", 0),
                p.get("explanation", ""),
            ))
        conn.commit()
        conn.close()
    else:
        sb = _get_supabase()
        rows = []
        for p in predictions:
            rows.append({
                "symbol": p["symbol"],
                "timestamp": now,
                "horizon": p.get("horizon", "15m"),
                "signal": p.get("signal", "HOLD"),
                "confidence": p.get("confidence", 0),
                "probability": p.get("probability", 0.5),
                "entry_price": p.get("entry_price", 0),
                "stop_loss": p.get("stop_loss", 0),
                "target_price": p.get("target_price", 0),
                "risk_reward": p.get("risk_reward", 0),
                "model_votes": json.dumps(_sanitize_value(p.get("model_votes", {}))),
                "consensus_direction": p.get("consensus_direction", ""),
                "consensus_agreement": p.get("consensus_agreement", 0),
                "explanation": p.get("explanation", ""),
            })
        sb.table("intraday_predictions").insert(_sanitize(rows)).execute()


def get_intraday_predictions(
    symbol: Optional[str] = None,
    horizon: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Get recent intraday predictions."""
    if config.USE_SQLITE:
        conn = _get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM intraday_predictions WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if horizon:
            query += " AND horizon = ?"
            params.append(horizon)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        results = []
        for r in rows:
            d = dict(r)
            d["model_votes"] = json.loads(d.get("model_votes", "{}") or "{}")
            results.append(d)
        return results
    else:
        sb = _get_supabase()
        q = sb.table("intraday_predictions").select("*")
        if symbol:
            q = q.eq("symbol", symbol)
        if horizon:
            q = q.eq("horizon", horizon)
        result = q.order("id", desc=True).limit(limit).execute()
        return result.data
