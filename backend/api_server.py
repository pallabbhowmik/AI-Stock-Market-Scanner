"""
FastAPI Server
REST API for the AI Stock Market Scanner.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend import config, database
from backend.scheduler import start_scheduler, stop_scheduler, get_scheduler_status

# Heavy modules are imported lazily inside route handlers to keep
# idle memory under Render's 512 MB free-tier limit.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Track background scan status
_scan_status = {
    "running": False,
    "error": None,
    "result": None,
    "started_at": None,
    "current_step": "",
    "progress": 0,
    "total_steps": 0,
    "stocks_processed": 0,
    "stocks_total": 0,
}

app = FastAPI(
    title="AI Stock Market Scanner",
    description="AI-powered stock scanning and prediction platform for the Indian market",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    database.init_db()
    logger.info("API server started")


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ─── Market Overview ─────────────────────────────────────────────────────────

@app.get("/api/overview")
async def market_overview():
    """Get market overview: counts, latest scan info, summary stats."""
    stocks = database.get_all_scanned_stocks()
    predictions = database.get_predictions()
    logs = database.get_scan_logs(limit=1)

    buy_count = sum(1 for p in predictions if p.get("signal") == "BUY")
    sell_count = sum(1 for p in predictions if p.get("signal") == "SELL")
    hold_count = sum(1 for p in predictions if p.get("signal") == "HOLD")

    avg_confidence = 0
    if predictions:
        avg_confidence = sum(p.get("confidence", 0) for p in predictions) / len(predictions)

    return {
        "total_stocks": len(stocks),
        "analyzed_today": len(predictions),
        "buy_signals": buy_count,
        "sell_signals": sell_count,
        "hold_signals": hold_count,
        "avg_confidence": round(avg_confidence, 4),
        "last_scan": logs[0] if logs else None,
        "scheduler": get_scheduler_status(),
    }


# ─── Predictions ─────────────────────────────────────────────────────────────

@app.get("/api/predictions")
async def get_predictions(
    date: Optional[str] = None,
    signal: Optional[str] = None,
    limit: int = Query(default=50, le=500),
):
    """Get AI predictions for a date, optionally filtered by signal."""
    preds = database.get_predictions(date)
    if signal:
        preds = [p for p in preds if p.get("signal") == signal.upper()]
    return {"predictions": preds[:limit], "total": len(preds)}


# ─── Watchlist ───────────────────────────────────────────────────────────────

@app.get("/api/watchlist")
async def get_watchlist(
    date: Optional[str] = None,
    category: Optional[str] = None,
):
    """Get the daily AI watchlist."""
    items = database.get_watchlist(date, category)
    return {"watchlist": items, "date": date or datetime.now().strftime("%Y-%m-%d")}


@app.get("/api/watchlist/categories")
async def watchlist_categories():
    """Get available watchlist categories."""
    return {
        "categories": [
            {"id": "top_buys", "name": "Top Buy Opportunities", "color": "green"},
            {"id": "top_sells", "name": "Top Sell Opportunities", "color": "red"},
            {"id": "top_breakouts", "name": "Top Breakout Stocks", "color": "blue"},
            {"id": "volume_movers", "name": "High Volume Movers", "color": "purple"},
        ]
    }


# ─── Stock Explorer ──────────────────────────────────────────────────────────

@app.get("/api/stocks")
async def list_stocks(
    search: Optional[str] = None,
    sector: Optional[str] = None,
):
    """List all scanned stocks with optional search/filter."""
    stocks = database.get_all_scanned_stocks()
    if search:
        search = search.upper()
        stocks = [s for s in stocks if search in s.get("symbol", "").upper()
                  or search in s.get("name", "").upper()]
    if sector:
        stocks = [s for s in stocks if sector.lower() in s.get("sector", "").lower()]
    return {"stocks": stocks, "total": len(stocks)}


@app.get("/api/stocks/{symbol}")
async def stock_detail(symbol: str):
    """Get detailed info and latest prediction for a stock."""
    # Get stored data
    df = database.get_stock_data(symbol, limit=365)

    # Get today's prediction
    preds = database.get_predictions()
    pred = next((p for p in preds if p.get("symbol") == symbol), None)

    # Basic stats from data
    stats = {}
    if not df.empty:
        stats = {
            "last_price": round(df["close"].iloc[-1], 2),
            "daily_change": round(
                (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100, 2
            ) if len(df) > 1 else 0,
            "week_high": round(df["high"].tail(5).max(), 2),
            "week_low": round(df["low"].tail(5).min(), 2),
            "month_high": round(df["high"].tail(22).max(), 2),
            "month_low": round(df["low"].tail(22).min(), 2),
            "avg_volume": int(df["volume"].tail(20).mean()),
            "data_points": len(df),
        }

    return {"symbol": symbol, "prediction": pred, "stats": stats}


@app.get("/api/stocks/{symbol}/chart")
async def stock_chart(symbol: str, period: int = Query(default=90, le=365)):
    """Get OHLCV chart data for a stock."""
    from backend.data_pipeline import fetch_daily_data, clean_data
    df = database.get_stock_data(symbol, limit=period)
    if df.empty:
        # Try fetching live
        df = fetch_daily_data(symbol, period="6mo")
        if df.empty:
            raise HTTPException(status_code=404, detail="No data found")
        df = clean_data(df)

    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
            "open": round(row["open"], 2),
            "high": round(row["high"], 2),
            "low": round(row["low"], 2),
            "close": round(row["close"], 2),
            "volume": int(row["volume"]),
        })

    return {"symbol": symbol, "data": records}


@app.get("/api/stocks/{symbol}/indicators")
async def stock_indicators(symbol: str):
    """Get technical indicators for a stock."""
    from backend.data_pipeline import fetch_daily_data, clean_data
    from backend.feature_engineering import compute_features
    df = database.get_stock_data(symbol, limit=365)
    if df.empty:
        df = fetch_daily_data(symbol, period="1y")
        if df.empty:
            raise HTTPException(status_code=404, detail="No data found")
        df = clean_data(df)

    featured = compute_features(df)
    if featured.empty:
        raise HTTPException(status_code=404, detail="Could not compute indicators")

    latest = featured.iloc[-1]
    indicators = {}
    for col in ["rsi", "macd", "macd_signal", "macd_histogram",
                "bb_upper", "bb_middle", "bb_lower", "bb_pct",
                "atr", "volume_ratio", "volatility",
                "stoch_k", "stoch_d", "williams_r",
                "roc_5", "roc_10", "roc_20",
                "sma_20", "sma_50", "sma_200",
                "ema_20", "ema_50"]:
        val = latest.get(col)
        if val is not None and not (isinstance(val, float) and val != val):
            indicators[col] = round(float(val), 4)

    return {"symbol": symbol, "indicators": indicators}


# ─── Scanner Control ─────────────────────────────────────────────────────────

@app.post("/api/scan/full")
async def trigger_full_scan(max_symbols: int = Query(default=0)):
    """Trigger a full market scan (runs in background)."""
    import threading
    if _scan_status["running"]:
        return {"status": "already_running", "message": "A scan is already in progress"}

    _scan_status["running"] = True
    _scan_status["error"] = None
    _scan_status["result"] = None
    _scan_status["started_at"] = datetime.now().isoformat()
    _scan_status["current_step"] = "Starting…"
    _scan_status["progress"] = 0
    _scan_status["total_steps"] = 0
    _scan_status["stocks_processed"] = 0
    _scan_status["stocks_total"] = 0

    def _run():
        try:
            from backend.watchlist_generator import run_full_scan
            result = run_full_scan(max_symbols=max_symbols, retrain=True,
                                   progress=_scan_status)
            _scan_status["result"] = result
        except Exception as e:
            logger.error("Full scan error: %s", e, exc_info=True)
            _scan_status["error"] = str(e)
        finally:
            _scan_status["running"] = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "scan_started", "message": "Full scan started in background"}


@app.post("/api/scan/quick")
async def trigger_quick_scan():
    """Trigger a quick scan on filtered stocks."""
    import threading
    if _scan_status["running"]:
        return {"status": "already_running", "message": "A scan is already in progress"}

    _scan_status["running"] = True
    _scan_status["error"] = None
    _scan_status["result"] = None
    _scan_status["started_at"] = datetime.now().isoformat()
    _scan_status["current_step"] = "Starting…"
    _scan_status["progress"] = 0
    _scan_status["total_steps"] = 0
    _scan_status["stocks_processed"] = 0
    _scan_status["stocks_total"] = 0

    def _run():
        try:
            from backend.watchlist_generator import run_quick_scan
            result = run_quick_scan(progress=_scan_status)
            _scan_status["result"] = result
        except Exception as e:
            logger.error("Quick scan error: %s", e, exc_info=True)
            _scan_status["error"] = str(e)
        finally:
            _scan_status["running"] = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "scan_started", "message": "Quick scan started in background"}


@app.post("/api/scan/lite")
async def trigger_lite_scan():
    """Trigger a lightweight scan using only major large-cap stocks.
    Designed for resource-constrained environments like Render free tier."""
    import threading
    if _scan_status["running"]:
        return {"status": "already_running", "message": "A scan is already in progress"}

    _scan_status["running"] = True
    _scan_status["error"] = None
    _scan_status["result"] = None
    _scan_status["started_at"] = datetime.now().isoformat()
    _scan_status["current_step"] = "Starting lite scan…"
    _scan_status["progress"] = 0
    _scan_status["total_steps"] = 0
    _scan_status["stocks_processed"] = 0
    _scan_status["stocks_total"] = 0

    def _run():
        try:
            from backend.watchlist_generator import run_quick_scan
            # Use only the top 30 large-cap symbols for minimal memory usage
            result = run_quick_scan(
                symbols=config.FALLBACK_SYMBOLS[:30],
                progress=_scan_status,
            )
            _scan_status["result"] = result
        except Exception as e:
            logger.error("Lite scan error: %s", e, exc_info=True)
            _scan_status["error"] = str(e)
        finally:
            _scan_status["running"] = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "scan_started", "message": "Lite scan started (30 large-cap stocks)"}


@app.get("/api/scan/status")
async def scan_status():
    """Get current scan status."""
    import numpy as np

    def _sanitize(obj):
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_sanitize(v) for v in obj]
        if isinstance(obj, (np.bool_, np.integer)):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    return _sanitize(_scan_status)


@app.get("/api/scan/logs")
async def scan_logs(limit: int = Query(default=10, le=50)):
    """Get recent scan logs."""
    logs = database.get_scan_logs(limit=limit)
    return {"logs": logs}


# ─── Scheduler Control ──────────────────────────────────────────────────────

@app.post("/api/scheduler/start")
async def start_auto_scanner():
    """Start the automatic scanner."""
    start_scheduler()
    return {"status": "started"}


@app.post("/api/scheduler/stop")
async def stop_auto_scanner():
    """Stop the automatic scanner."""
    stop_scheduler()
    return {"status": "stopped"}


@app.get("/api/scheduler/status")
async def scheduler_status():
    return get_scheduler_status()


# ─── Meta-AI Strategy ───────────────────────────────────────────────────────

@app.get("/api/meta-strategy")
async def meta_strategy_status():
    """Get current Meta-AI strategy status: weights, regime, explanation."""
    from backend.market_regime import detect_regime
    from backend.meta_strategy import get_strategy_status
    try:
        regime_info = detect_regime()
    except Exception:
        regime_info = {"regime": "SIDEWAYS", "confidence": 0.5}

    status = get_strategy_status(regime_info.get("regime", "SIDEWAYS"))
    status["regime_confidence"] = regime_info.get("confidence", 0.5)

    # Also try to load persisted state from DB
    saved = database.get_meta_strategy_state()
    if saved:
        status["last_updated"] = saved.get("date")

    return status


@app.get("/api/regime")
async def market_regime():
    """Get current market regime (BULL / BEAR / SIDEWAYS)."""
    from backend.market_regime import detect_regime
    try:
        info = detect_regime()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Regime detection failed: {e}")
    return info


@app.get("/api/strategies/performance")
async def strategies_performance():
    """Get performance metrics for all trading strategies."""
    from backend.meta_strategy import get_tracker
    tracker = get_tracker()
    return {"strategies": tracker.get_all_stats()}


# ─── Risk Management ────────────────────────────────────────────────────────

@app.get("/api/risk/{symbol}")
async def stock_risk(symbol: str):
    """Get risk management recommendation for a stock."""
    from backend.data_pipeline import fetch_daily_data, clean_data
    from backend.risk_management import generate_risk_recommendation
    df = database.get_stock_data(symbol, limit=365)
    if df.empty:
        df = fetch_daily_data(symbol, period="1y")
        if df.empty:
            raise HTTPException(status_code=404, detail="No data found")
        df = clean_data(df)

    last_price = float(df["close"].iloc[-1])
    rec = generate_risk_recommendation(symbol, last_price, df)
    return rec


# ─── Portfolio Optimization ─────────────────────────────────────────────────

@app.get("/api/portfolio")
async def portfolio_optimization(
    method: str = Query(default="score_weighted",
                        description="equal_weight | score_weighted | risk_parity | mean_variance"),
):
    """Optimize portfolio allocation from current BUY-signal watchlist."""
    preds = database.get_predictions()
    buy_preds = [p for p in preds if p.get("signal") == "BUY"]

    if not buy_preds:
        return {"allocation": [], "message": "No BUY signals to optimize"}

    from backend.data_pipeline import fetch_daily_data, clean_data
    from backend.portfolio_optimizer import optimize_portfolio
    symbols = [p["symbol"] for p in buy_preds]
    scores = {p["symbol"]: p.get("opportunity_score", 0.5) for p in buy_preds}

    # Fetch price data for volatility estimation
    stock_data = {}
    for sym in symbols:
        df = database.get_stock_data(sym, limit=90)
        if df.empty:
            df = fetch_daily_data(sym, period="3mo")
            if not df.empty:
                df = clean_data(df)
        if not df.empty:
            stock_data[sym] = df

    result = optimize_portfolio(stock_data, scores=scores, method=method)
    return result


# ─── Sentiment & Institutional ───────────────────────────────────────────────

@app.get("/api/stocks/{symbol}/sentiment")
async def stock_sentiment(symbol: str):
    """Get sentiment analysis for a stock."""
    from backend.sentiment_analysis import get_stock_sentiment
    result = get_stock_sentiment(symbol)
    return result


@app.get("/api/stocks/{symbol}/institutional")
async def stock_institutional(symbol: str):
    """Detect institutional activity for a stock."""
    from backend.data_pipeline import fetch_daily_data, clean_data
    from backend.institutional_activity import detect_institutional_activity
    df = database.get_stock_data(symbol, limit=90)
    if df.empty:
        df = fetch_daily_data(symbol, period="3mo")
        if df.empty:
            raise HTTPException(status_code=404, detail="No data found")
        df = clean_data(df)

    result = detect_institutional_activity(df)
    return result


# ─── Training Pipeline ──────────────────────────────────────────────────────

@app.get("/api/training/status")
async def training_status():
    """Get full training pipeline status including model version info."""
    from backend.training_pipeline import get_pipeline_status
    return get_pipeline_status()


@app.post("/api/training/start")
async def trigger_training():
    """Start a model retraining cycle in the background."""
    from backend.training_pipeline import run_training_pipeline_async
    started = run_training_pipeline_async()
    if started:
        return {"status": "training_started", "message": "Model retraining started in background"}
    return {"status": "already_running", "message": "Training is already in progress"}


@app.get("/api/training/logs")
async def training_logs(limit: int = Query(default=10, le=50)):
    """Get recent training pipeline logs."""
    logs = database.get_training_logs(limit=limit)
    return {"logs": logs}


@app.get("/api/training/versions")
async def model_versions():
    """Get all stored model versions with metadata."""
    from backend.model_versioning import get_all_versions, get_current_version
    versions = get_all_versions()
    current = get_current_version()
    return {
        "versions": versions,
        "current_version": current.get("version_id") if current else None,
    }


@app.post("/api/training/rollback")
async def rollback(steps: int = Query(default=1, ge=1, le=10)):
    """Roll back the production model to a previous version."""
    from backend.training_pipeline import rollback_model
    result = rollback_model(steps)
    return result


# ─── Paper Trading ───────────────────────────────────────────────────────────

@app.get("/api/paper/portfolio")
async def paper_portfolio():
    """Get current paper trading portfolio: cash, positions, value."""
    from backend.paper_trading import get_portfolio_summary
    return get_portfolio_summary()


@app.get("/api/paper/positions")
async def paper_positions():
    """Get open paper trading positions."""
    from backend.paper_trading import get_portfolio_summary
    summary = get_portfolio_summary()
    return {"positions": summary.get("positions", []), "count": summary.get("open_positions", 0)}


@app.post("/api/paper/order")
async def paper_order(
    symbol: str = Query(..., description="NSE stock symbol"),
    side: str = Query(..., description="BUY or SELL"),
    order_type: str = Query(default="MARKET"),
    quantity: int = Query(default=0, ge=0),
    limit_price: float = Query(default=0),
    stop_price: float = Query(default=0),
    take_profit_price: float = Query(default=0),
):
    """Place a paper trading order."""
    from backend.paper_trading import execute_order
    result = execute_order(
        symbol=symbol.upper(),
        side=side.upper(),
        order_type=order_type.upper(),
        quantity=quantity,
        limit_price=limit_price,
        stop_price=stop_price,
        take_profit_price=take_profit_price,
    )
    return result


@app.get("/api/paper/trades")
async def paper_trades(limit: int = Query(default=50, le=500)):
    """Get paper trade history."""
    from backend.paper_trading import get_trade_history
    trades = get_trade_history(limit=limit)
    return {"trades": trades, "total": len(trades)}


@app.get("/api/paper/performance")
async def paper_performance():
    """Get paper trading performance statistics."""
    from backend.paper_trading import get_performance_stats
    return get_performance_stats()


@app.post("/api/paper/auto-execute")
async def paper_auto_execute():
    """Auto-execute paper trades based on current AI signals."""
    from backend.paper_trading import auto_execute_signals
    results = auto_execute_signals()
    return {"executed": len(results), "trades": results}


@app.post("/api/paper/reset")
async def paper_reset():
    """Reset paper trading portfolio to initial balance."""
    from backend.paper_trading import reset_portfolio
    return reset_portfolio()


# ─── Run Server ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
