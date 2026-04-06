"""
Watchlist Generator
Orchestrates the full 13-module AI trading pipeline and generates the daily watchlist.
"""
import gc
import logging
import os
from datetime import datetime

from backend import config, database
from backend.market_scanner import scan_market
from backend.data_pipeline import fetch_daily_data, clean_data
from backend.feature_engineering import compute_features, compute_momentum_score, compute_volume_spike_score
from backend.prediction_engine import predict_stock, train_models
from backend.breakout_detector import detect_all_breakouts
from backend.ranking_engine import compute_opportunity_score, generate_explanation, rank_stocks
from backend.sentiment_analysis import get_stock_sentiment, compute_sentiment_score
from backend.institutional_activity import detect_institutional_activity
from backend.market_regime import detect_regime
from backend.risk_management import generate_risk_recommendation
from backend.rl_trading_agent import train_rl_agent, predict_with_rl
from backend.meta_strategy import (
    run_meta_strategy, get_strategy_status, get_tracker, STRATEGIES,
)

logger = logging.getLogger(__name__)

# ── Configurable limits for low-memory hosts ────────────────────────────────
_MAX_SCAN_STOCKS = int(os.getenv("MAX_SCAN_STOCKS", "50"))
_MAX_TRAIN_STOCKS = int(os.getenv("FULL_SCAN_TRAIN_SAMPLE", "20"))
_FETCH_PERIOD = os.getenv("SCAN_FETCH_PERIOD", "6mo")  # shorter = less memory


def _update_progress(progress, step: str, pct: int, total_steps: int = 13,
                      stocks_processed: int = 0, stocks_total: int = 0):
    """Update the shared progress dict (if provided)."""
    if progress is None:
        return
    progress["current_step"] = step
    progress["progress"] = pct
    progress["total_steps"] = total_steps
    progress["stocks_processed"] = stocks_processed
    progress["stocks_total"] = stocks_total


def run_full_scan(max_symbols: int = 0, retrain: bool = False,
                  progress: dict = None) -> dict:
    """
    Run the complete 13-module scanning pipeline:
    1-2. Scan market & filter  →  3. Fetch data  →  4. Technical indicators
    5. ML predictions  →  6. Breakout detection  →  7. RL agent
    8. Sentiment analysis  →  9. Institutional activity  →  10. Market regime
    11. Meta-AI strategy selection  →  12. Risk management
    13. Rank & generate watchlist
    """
    started_at = datetime.now().isoformat()
    logger.info("═" * 60)
    logger.info("  STARTING FULL 13-MODULE MARKET SCAN")
    logger.info("═" * 60)

    # ── Step 1-2: Scan and filter ──
    _update_progress(progress, "Scanning market & applying filters…", 5)
    logger.info("Step 1-2: Scanning market and applying filters...")
    all_stocks, filtered_stocks = scan_market(max_symbols=max_symbols)
    database.upsert_scanned_stocks(all_stocks)
    symbols = [s["symbol"] for s in filtered_stocks]
    # Cap to configurable limit so Render free tier doesn't OOM
    if len(symbols) > _MAX_SCAN_STOCKS:
        logger.info("Capping scan from %d to %d stocks (MAX_SCAN_STOCKS)", len(symbols), _MAX_SCAN_STOCKS)
        symbols = symbols[:_MAX_SCAN_STOCKS]
    logger.info("Filtered to %d stocks", len(symbols))

    if not symbols:
        logger.warning("No stocks passed filters!")
        database.save_scan_log(started_at, datetime.now().isoformat(), len(all_stocks), 0, "no_stocks")
        return {"status": "no_stocks", "rankings": {}}

    # ── Step 3: Fetch data ──
    _update_progress(progress, "Downloading price history…", 15, stocks_total=len(symbols))
    logger.info("Step 3: Fetching historical data for %d stocks (period=%s)...", len(symbols), _FETCH_PERIOD)
    stock_data = {}
    for i, sym in enumerate(symbols):
        try:
            df = fetch_daily_data(sym, period=_FETCH_PERIOD)
            if not df.empty:
                df = clean_data(df)
                database.save_stock_data(df, sym)
                stock_data[sym] = df
        except Exception as e:
            logger.debug("Data fetch failed for %s: %s", sym, e)
        _update_progress(progress, "Downloading price history…",
                         15 + int(15 * (i + 1) / len(symbols)),
                         stocks_processed=i + 1, stocks_total=len(symbols))
    logger.info("Got data for %d stocks", len(stock_data))
    gc.collect()

    # ── Step 4: Technical indicators ──
    _update_progress(progress, "Computing technical indicators…", 32)
    logger.info("Step 4: Computing technical indicators...")
    featured_data = {}
    for sym, df in stock_data.items():
        featured = compute_features(df)
        if not featured.empty:
            featured_data[sym] = featured
    # Free raw data — we only need featured from here
    del stock_data
    gc.collect()

    # ── Step 5a: Train ML models if needed ──
    if retrain or not _models_exist():
        _update_progress(progress, "Training ML models…", 38)
        logger.info("Step 5a: Training ML models...")
        # Use a subset for training to save memory
        train_subset = dict(list(featured_data.items())[:_MAX_TRAIN_STOCKS])
        train_models(train_subset)
        del train_subset
        gc.collect()

    # ── Step 7: Train RL agent ──
    _update_progress(progress, "Training RL agent…", 45)
    logger.info("Step 7: Training RL agent...")
    try:
        rl_subset = dict(list(featured_data.items())[:_MAX_TRAIN_STOCKS])
        train_rl_agent(rl_subset)
        del rl_subset
        gc.collect()
    except Exception as e:
        logger.warning("RL training skipped: %s", e)

    # ── Step 10: Market regime detection ──
    _update_progress(progress, "Detecting market regime…", 50)
    logger.info("Step 10: Detecting market regime...")
    regime_info = {"regime": "SIDEWAYS", "confidence": 0.5}
    try:
        regime_info = detect_regime()
    except Exception as e:
        logger.warning("Regime detection failed, defaulting to SIDEWAYS: %s", e)

    # ── Steps 5b-9,11-12: Per-stock analysis ──
    _update_progress(progress, "Analyzing stocks…", 55,
                     stocks_processed=0, stocks_total=len(featured_data))
    logger.info("Steps 5-12: Running per-stock 13-module pipeline...")
    all_predictions = []
    _total_stocks = len(featured_data)

    for _idx, (sym, df) in enumerate(featured_data.items()):
        try:
            # Step 5b: ML prediction
            pred = predict_stock(df)

            # Step 4 extras: momentum & volume
            momentum = compute_momentum_score(df)
            vol_spike = compute_volume_spike_score(df)

            # Step 6: Breakout detection
            breakout = detect_all_breakouts(df)

            # Step 7b: RL prediction
            rl_pred = {"signal": "HOLD", "rl_score": 0.5, "confidence": 0}
            try:
                rl_pred = predict_with_rl(df)
            except Exception as e:
                logger.debug("RL prediction skipped for %s: %s", sym, e)

            # Step 8: Sentiment analysis
            sentiment_result = {"sentiment_score": 0.0, "signal": "NEUTRAL"}
            try:
                sentiment_result = get_stock_sentiment(sym)
            except Exception as e:
                logger.debug("Sentiment skipped for %s: %s", sym, e)

            # Step 11: Meta-AI strategy — combines ML, RL, momentum, mean-rev, volume, sentiment
            meta_result = run_meta_strategy(
                symbol=sym,
                df=df,
                ml_prediction=pred,
                rl_prediction=rl_pred,
                momentum_score=momentum,
                breakout_result=breakout,
                volume_spike_score=vol_spike,
                sentiment_result=sentiment_result,
                regime=regime_info.get("regime", "SIDEWAYS"),
            )

            # Step 12: Risk management
            risk_rec = {}
            try:
                last_price = float(df["close"].iloc[-1])
                risk_rec = generate_risk_recommendation(sym, last_price, df)
            except Exception as e:
                logger.debug("Risk calc skipped for %s: %s", sym, e)

            # Use meta-strategy score as the primary opportunity score
            opp_score = meta_result.get("final_score", 0.0)

            # Build combined explanation
            explanation_parts = []
            explanation_parts.append(
                generate_explanation(
                    symbol=sym, signal=pred["signal"],
                    ai_probability=pred["ai_probability"],
                    momentum_score=momentum, breakout_score=breakout["score"],
                    volume_spike_score=vol_spike,
                    breakout_desc=breakout["description"],
                )
            )
            if meta_result.get("explanation"):
                explanation_parts.append(meta_result["explanation"])
            explanation = " | ".join(explanation_parts)

            contributions = meta_result.get("strategy_contributions", {})
            # Use meta-strategy confidence when ML models unavailable
            raw_confidence = pred["confidence"]
            if raw_confidence == 0 and meta_result.get("final_score", 0) > 0:
                raw_confidence = round(min(meta_result["final_score"], 1.0), 4)
            all_predictions.append({
                "symbol": sym,
                "signal": meta_result.get("final_signal", pred["signal"]),
                "confidence": raw_confidence,
                "ai_probability": pred["ai_probability"],
                "momentum_score": momentum,
                "breakout_score": breakout["score"],
                "volume_spike_score": vol_spike,
                "opportunity_score": opp_score,
                "meta_score": meta_result.get("final_score", 0),
                "meta_signal": meta_result.get("final_signal", "HOLD"),
                "regime": regime_info.get("regime", "SIDEWAYS"),
                "sentiment_score": contributions.get("sentiment", {}).get("score", 0),
                "rl_score": contributions.get("rl_agent", {}).get("score", 0),
                "explanation": explanation,
                "last_price": df["close"].iloc[-1] if not df.empty else 0,
                "risk": risk_rec,
            })
        except Exception as e:
            logger.warning("Pipeline failed for %s: %s", sym, e)
        _update_progress(progress, f"Analyzing stocks… ({_idx+1}/{_total_stocks})",
                         55 + int(30 * (_idx + 1) / _total_stocks),
                         stocks_processed=_idx + 1, stocks_total=_total_stocks)

    # ── Step 13a: Save predictions ──
    _update_progress(progress, "Saving predictions…", 88)
    logger.info("Step 13a: Saving predictions...")
    database.save_predictions(all_predictions)

    # ── Step 13b: Save meta-strategy state ──
    try:
        status = get_strategy_status(regime_info.get("regime", "SIDEWAYS"))
        database.save_meta_strategy_state(
            regime=regime_info.get("regime", "SIDEWAYS"),
            weights=status.get("weights", {}),
            explanation=status.get("explanation", ""),
        )
    except Exception as e:
        logger.warning("Failed to save meta-strategy state: %s", e)

    # ── Step 13c: Rank and create watchlist ──
    _update_progress(progress, "Ranking & generating watchlist…", 92)
    logger.info("Step 13c: Ranking stocks...")
    rankings = rank_stocks(all_predictions)

    logger.info("Step 13d: Generating watchlist...")
    watchlist_items = []
    for category, items in rankings.items():
        for item in items:
            watchlist_items.append({
                "category": category,
                "symbol": item["symbol"],
                "signal": item.get("meta_signal", item.get("signal", "HOLD")),
                "confidence": item.get("confidence", 0),
                "opportunity_score": item.get("opportunity_score", 0),
                "explanation": item.get("explanation", ""),
                "rank": item.get("rank", 0),
            })
    database.save_watchlist(watchlist_items)

    finished_at = datetime.now().isoformat()
    database.save_scan_log(
        started_at, finished_at,
        stocks_scanned=len(all_stocks),
        stocks_passed=len(filtered_stocks),
        status="success",
    )

    _update_progress(progress, "Complete", 100)
    logger.info("═" * 60)
    logger.info("  SCAN COMPLETE - %d predictions  |  regime: %s",
                len(all_predictions), regime_info.get("regime"))
    logger.info("═" * 60)

    return {
        "status": "success",
        "stocks_scanned": len(all_stocks),
        "stocks_passed_filter": len(filtered_stocks),
        "predictions": len(all_predictions),
        "rankings": {k: len(v) for k, v in rankings.items()},
        "regime": regime_info,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _models_exist() -> bool:
    """Check if trained models exist."""
    import os
    scaler_path = os.path.join(config.MODEL_DIR, "scaler.pkl")
    return os.path.exists(scaler_path)


def run_quick_scan(symbols: list[str] = None, progress: dict = None) -> dict:
    """
    Run a quick scan on specific symbols (no market download / filtering).
    Useful for updating predictions during the day.
    """
    import time
    _update_progress(progress, "Loading stocks…", 5)
    if symbols is None:
        # Use previously filtered stocks from DB
        stocks = database.get_all_scanned_stocks()
        symbols = [s["symbol"] for s in stocks if s.get("avg_volume", 0) >= config.FILTER_MIN_VOLUME]

    # Cap to prevent OOM on Render free tier
    if len(symbols) > _MAX_SCAN_STOCKS:
        symbols = symbols[:_MAX_SCAN_STOCKS]

    if not symbols:
        return {"status": "no_symbols"}

    logger.info("Quick scan: %d symbols", len(symbols))

    _update_progress(progress, "Downloading price data…", 10, stocks_total=len(symbols))
    stock_data = {}
    for i, sym in enumerate(symbols):
        try:
            df = fetch_daily_data(sym, period="3mo")
            if not df.empty:
                df = clean_data(df)
                stock_data[sym] = df
        except Exception as e:
            logger.warning("Data fetch failed for %s: %s", sym, e)
        # Small delay to avoid yfinance rate-limiting
        if (i + 1) % 5 == 0:
            time.sleep(1)
        _update_progress(progress, "Downloading price data…",
                         10 + int(30 * (i + 1) / len(symbols)),
                         stocks_processed=i + 1, stocks_total=len(symbols))

    _update_progress(progress, "Computing indicators…", 42)
    featured_data = {sym: compute_features(df) for sym, df in stock_data.items()}
    featured_data = {sym: df for sym, df in featured_data.items() if not df.empty}
    del stock_data
    gc.collect()

    _update_progress(progress, "Generating predictions…", 50,
                     stocks_total=len(featured_data))
    all_predictions = []
    _total = len(featured_data)
    for _idx, (sym, df) in enumerate(featured_data.items()):
        pred = predict_stock(df)
        momentum = compute_momentum_score(df)
        vol_spike = compute_volume_spike_score(df)
        breakout = detect_all_breakouts(df)

        opp_score = compute_opportunity_score(
            pred["ai_probability"], momentum, breakout["score"], vol_spike
        )
        explanation = generate_explanation(
            sym, pred["signal"], pred["ai_probability"],
            momentum, breakout["score"], vol_spike, breakout["description"],
        )

        all_predictions.append({
            "symbol": sym,
            "signal": pred["signal"],
            "confidence": pred["confidence"],
            "ai_probability": pred["ai_probability"],
            "momentum_score": momentum,
            "breakout_score": breakout["score"],
            "volume_spike_score": vol_spike,
            "opportunity_score": opp_score,
            "explanation": explanation,
            "last_price": df["close"].iloc[-1] if not df.empty else 0,
        })
        _update_progress(progress, f"Analyzing stocks… ({_idx+1}/{_total})",
                         50 + int(35 * (_idx + 1) / _total),
                         stocks_processed=_idx + 1, stocks_total=_total)

    _update_progress(progress, "Saving & ranking…", 90)
    database.save_predictions(all_predictions)
    rankings = rank_stocks(all_predictions)

    watchlist_items = []
    for category, items in rankings.items():
        for item in items:
            watchlist_items.append({
                "category": category,
                "symbol": item["symbol"],
                "signal": item.get("signal", "HOLD"),
                "confidence": item.get("confidence", 0),
                "opportunity_score": item.get("opportunity_score", 0),
                "explanation": item.get("explanation", ""),
                "rank": item.get("rank", 0),
            })
    database.save_watchlist(watchlist_items)

    _update_progress(progress, "Complete", 100)
    return {
        "status": "success",
        "predictions": len(all_predictions),
        "rankings": {k: len(v) for k, v in rankings.items()},
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    database.init_db()
    result = run_full_scan(max_symbols=30, retrain=True)
    print(result)
