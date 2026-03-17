"""
Intraday Scanner
Orchestrates the intraday trading pipeline:
  1. Fetch 5m + 15m + daily data for filtered stocks
  2. Compute advanced intraday features (VWAP, order flow, microstructure, MTF)
  3. Train / load intraday ML models (HistGB, LightGBM, XGBoost)
  4. Predict 15m, 30m, 1h forward returns
  5. Rank and filter for high-confidence intraday signals
  6. Persist to database
"""
import gc
import logging
import time
from datetime import datetime

from backend import config, database
from backend.data_pipeline import fetch_daily_data, fetch_intraday_data, clean_data
from backend.intraday_features import (
    compute_intraday_features, get_intraday_feature_columns,
)
from backend.intraday_prediction import (
    train_intraday_models, predict_all_horizons, clear_intraday_cache,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 15   # smaller batches for intraday (more data per stock)
_TRAIN_SAMPLE = 30


def _models_exist() -> bool:
    import os
    return os.path.exists(
        os.path.join(config.MODEL_DIR, "intraday", "feature_cols.pkl")
    )


def run_intraday_scan(
    symbols: list[str] = None,
    retrain: bool = False,
    progress: dict = None,
) -> dict:
    """
    Full intraday scanning pipeline.

    Args:
        symbols: List of stock symbols to scan (default: use filtered stocks from DB)
        retrain: Whether to retrain intraday models
        progress: Optional dict for progress updates

    Returns:
        {status, predictions, signals_count, ...}
    """
    started_at = datetime.now().isoformat()
    logger.info("═" * 60)
    logger.info("  STARTING INTRADAY SCAN")
    logger.info("═" * 60)

    # Get symbols
    if symbols is None:
        stocks = database.get_all_scanned_stocks()
        symbols = [s["symbol"] for s in stocks
               if (s.get("avg_volume") or 0) >= config.FILTER_MIN_VOLUME]

    if not symbols:
        logger.warning("No symbols for intraday scan")
        return {"status": "no_symbols", "predictions": 0}

    total = len(symbols)
    logger.info("Scanning %d symbols for intraday signals", total)

    if progress:
        progress["current_step"] = "Fetching intraday data…"
        progress["progress"] = 5

    # ── Step 1: Train models if needed ──
    if retrain or not _models_exist():
        logger.info("Training intraday models on sample of %d stocks…", _TRAIN_SAMPLE)
        if progress:
            progress["current_step"] = "Training intraday models…"
            progress["progress"] = 10

        import random
        train_syms = random.sample(symbols, min(_TRAIN_SAMPLE, len(symbols)))
        train_data = {}

        for sym in train_syms:
            try:
                df_5m = fetch_intraday_data(sym, interval="5m", period="5d")
                if df_5m.empty or len(df_5m) < 100:
                    continue
                df_5m = clean_data(df_5m)
                df_15m = fetch_intraday_data(sym, interval="15m", period="5d")
                if not df_15m.empty:
                    df_15m = clean_data(df_15m)
                df_daily = fetch_daily_data(sym, period="3mo")
                if not df_daily.empty:
                    df_daily = clean_data(df_daily)

                featured = compute_intraday_features(
                    df_5m, df_15m=df_15m, df_daily=df_daily, add_targets=True
                )
                if not featured.empty and len(featured) >= 50:
                    train_data[sym] = featured
                del df_5m, df_15m, df_daily
            except Exception as e:
                logger.debug("Train data fetch failed for %s: %s", sym, e)
            time.sleep(0.3)

        gc.collect()
        if train_data:
            train_intraday_models(train_data)
            logger.info("Intraday models trained on %d stocks", len(train_data))
        else:
            logger.warning("No training data available for intraday models")
        del train_data
        gc.collect()

    # ── Step 2: Generate predictions for all symbols ──
    all_predictions = []
    processed = 0

    for batch_start in range(0, total, _BATCH_SIZE):
        batch = symbols[batch_start: batch_start + _BATCH_SIZE]

        if progress:
            progress["current_step"] = f"Analyzing batch ({processed}/{total})…"
            progress["progress"] = 25 + int(65 * processed / total)
            progress["stocks_processed"] = processed
            progress["stocks_total"] = total

        for sym in batch:
            try:
                # Fetch multi-timeframe data
                df_5m = fetch_intraday_data(sym, interval="5m", period="5d")
                if df_5m.empty or len(df_5m) < 40:
                    processed += 1
                    continue
                df_5m = clean_data(df_5m)

                df_15m = fetch_intraday_data(sym, interval="15m", period="5d")
                df_15m = clean_data(df_15m) if not df_15m.empty else df_15m

                df_daily = fetch_daily_data(sym, period="3mo")
                df_daily = clean_data(df_daily) if not df_daily.empty else df_daily

                # Compute features
                featured = compute_intraday_features(
                    df_5m, df_15m=df_15m, df_daily=df_daily, add_targets=False
                )
                del df_5m, df_15m, df_daily

                if featured.empty:
                    processed += 1
                    continue

                # Predict all horizons
                result = predict_all_horizons(featured)
                primary = result["primary"]
                consensus = result["consensus"]

                # Generate explanation
                explanation = _generate_intraday_explanation(sym, result)

                # Store one entry per horizon
                for horizon, pred in result["horizons"].items():
                    all_predictions.append({
                        "symbol": sym,
                        "horizon": horizon,
                        "signal": pred["signal"],
                        "confidence": pred["confidence"],
                        "probability": pred["probability"],
                        "entry_price": pred["entry_price"],
                        "stop_loss": pred["stop_loss"],
                        "target_price": pred["target_price"],
                        "risk_reward": pred["risk_reward"],
                        "model_votes": pred["model_votes"],
                        "consensus_direction": consensus["direction"],
                        "consensus_agreement": consensus["agreement"],
                        "explanation": explanation,
                    })

                del featured
            except Exception as e:
                logger.warning("Intraday pipeline failed for %s: %s", sym, e)

            processed += 1
            if processed % 5 == 0:
                time.sleep(0.5)

        gc.collect()

    # ── Step 3: Save to database ──
    if progress:
        progress["current_step"] = "Saving predictions…"
        progress["progress"] = 92

    database.save_intraday_predictions(all_predictions)

    # Count actionable signals
    actionable = [p for p in all_predictions
                  if p["signal"] != "HOLD" and p["confidence"] >= 0.3]

    finished_at = datetime.now().isoformat()
    logger.info("═" * 60)
    logger.info("  INTRADAY SCAN COMPLETE - %d predictions, %d actionable signals",
                len(all_predictions), len(actionable))
    logger.info("═" * 60)

    if progress:
        progress["current_step"] = "Complete"
        progress["progress"] = 100

    return {
        "status": "success",
        "symbols_scanned": total,
        "predictions": len(all_predictions),
        "actionable_signals": len(actionable),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def get_intraday_signals(
    min_confidence: float = 0.3,
    horizon: str = None,
    signal_type: str = None,
    limit: int = 50,
) -> list[dict]:
    """
    Get the latest high-confidence intraday signals.
    Filters by confidence threshold, horizon, and signal type.
    """
    preds = database.get_intraday_predictions(horizon=horizon, limit=500)

    # Filter
    filtered = []
    for p in preds:
        if p.get("confidence", 0) < min_confidence:
            continue
        if signal_type and p.get("signal") != signal_type.upper():
            continue
        filtered.append(p)

    # Sort by confidence descending
    filtered.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return filtered[:limit]


def _generate_intraday_explanation(symbol: str, result: dict) -> str:
    """Generate a trader-friendly explanation for intraday signals."""
    primary = result["primary"]
    consensus = result["consensus"]
    horizons = result["horizons"]

    sig = primary["signal"]
    conf = primary["confidence"]
    prob = primary["probability"]
    horizon = primary["horizon"]

    parts = []

    # Primary signal
    if sig == "BUY":
        parts.append(f"{symbol}: BUY signal ({horizon}) with {conf:.0%} confidence")
    elif sig == "SELL":
        parts.append(f"{symbol}: SELL signal ({horizon}) with {conf:.0%} confidence")
    else:
        parts.append(f"{symbol}: No clear direction, HOLD recommended")
        return parts[0]

    # Consensus
    if consensus["agreement"] >= 0.8:
        parts.append(f"All timeframes agree ({consensus['direction']})")
    elif consensus["agreement"] >= 0.5:
        parts.append("Partial timeframe agreement")

    # Entry/exit levels
    if primary["entry_price"] > 0:
        parts.append(
            f"Entry: ₹{primary['entry_price']:.2f}, "
            f"SL: ₹{primary['stop_loss']:.2f}, "
            f"Target: ₹{primary['target_price']:.2f} "
            f"(R:R {primary['risk_reward']:.1f})"
        )

    # Model agreement
    votes = primary.get("model_votes", {})
    if votes:
        bull_models = sum(1 for v in votes.values() if v > 0.55)
        total_models = len(votes)
        if bull_models == total_models:
            parts.append("All AI models agree on bullish direction")
        elif bull_models == 0:
            parts.append("All AI models agree on bearish direction")

    return " | ".join(parts)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    database.init_db()
    result = run_intraday_scan(
        symbols=config.FALLBACK_SYMBOLS[:10],
        retrain=True,
    )
    print(result)
