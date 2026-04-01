"""
Watchlist Generator
Orchestrates the full 13-module AI trading pipeline and generates the daily watchlist.

Memory-optimised for Render free tier (512 MB).  Stocks are processed in
small batches so that at most ~25 DataFrames are in memory at once.
Training uses a capped random sample.  All heavy sub-module imports are
deferred until first use.
"""
import gc
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from backend import config, database

logger = logging.getLogger(__name__)

# ── Tunables for memory-constrained environments ───────────────────────────────────
_BATCH_SIZE = config.FULL_SCAN_CHUNK_SIZE
_TRAIN_SAMPLE_STOCKS = config.FULL_SCAN_TRAIN_SAMPLE
_FETCH_WORKERS = config.FULL_SCAN_FETCH_WORKERS
_ANALYSIS_WORKERS = config.FULL_SCAN_ANALYSIS_WORKERS
_MEMORY_LIMIT_MB = 460          # soft RSS ceiling (abort before 512 MB)


# ── Memory guard ────────────────────────────────────────────────────────
def _rss_mb() -> float:
    """Return current process RSS in MB (Linux / fallback)."""
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB→MB
    except ImportError:
        pass
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def _check_memory(label: str = "") -> None:
    """Log RSS and raise if approaching the hard limit."""
    mb = _rss_mb()
    if mb > 0:
        logger.info("RSS after %s: %.0f MB", label or "checkpoint", mb)
    if mb > _MEMORY_LIMIT_MB:
        raise MemoryError(
            f"RSS {mb:.0f} MB exceeds soft limit {_MEMORY_LIMIT_MB} MB "
            f"at {label}. Aborting to avoid OOM kill."
        )


def _update_progress(progress, step: str, pct: int, total_steps: int = 13,
                      stocks_processed: int = 0, stocks_total: int = 0):
    if progress is None:
        return
    progress["current_step"] = step
    progress["progress"] = pct
    progress["total_steps"] = total_steps
    progress["stocks_processed"] = stocks_processed
    progress["stocks_total"] = stocks_total


def _build_watchlist_items(rankings: dict) -> list[dict]:
    items = []
    for category, rows in rankings.items():
        for row in rows:
            items.append({
                "category": category,
                "symbol": row["symbol"],
                "signal": row.get("meta_signal", row.get("signal", "HOLD")),
                "confidence": row.get("confidence", 0),
                "opportunity_score": row.get("opportunity_score", 0),
                "explanation": row.get("explanation", ""),
                "rank": row.get("rank", 0),
            })
    return items


# ── Lazy imports (called once, then cached by Python) ───────────────────
def _imp_data():
    from backend.data_pipeline import fetch_daily_data, clean_data
    return fetch_daily_data, clean_data

def _imp_features():
    from backend.feature_engineering import (
        compute_features, compute_momentum_score, compute_volume_spike_score,
    )
    return compute_features, compute_momentum_score, compute_volume_spike_score

def _imp_predict():
    from backend.prediction_engine import predict_stock, train_models
    from backend.data_pipeline import batch_download_daily
    return predict_stock, train_models, batch_download_daily

def _imp_breakout():
    from backend.breakout_detector import detect_all_breakouts
    return detect_all_breakouts

def _imp_ranking():
    from backend.ranking_engine import (
        compute_opportunity_score, generate_explanation, rank_stocks,
    )
    return compute_opportunity_score, generate_explanation, rank_stocks

def _imp_sentiment():
    from backend.sentiment_analysis import get_stock_sentiment
    return get_stock_sentiment

def _imp_regime():
    from backend.market_regime import detect_regime
    return detect_regime

def _imp_risk():
    from backend.risk_management import generate_risk_recommendation
    return generate_risk_recommendation

def _imp_rl():
    from backend.rl_trading_agent import train_rl_agent, predict_with_rl
    return train_rl_agent, predict_with_rl

def _imp_meta():
    from backend.meta_strategy import run_meta_strategy, get_strategy_status
    return run_meta_strategy, get_strategy_status

def _imp_scanner():
    from backend.market_scanner import scan_market
    return scan_market


def _models_exist() -> bool:
    scaler_path = os.path.join(config.MODEL_DIR, "scaler.pkl")
    return os.path.exists(scaler_path)


# ─────────────────────────────────────────────────────────────────────────
#  FULL SCAN — streaming batch approach
# ─────────────────────────────────────────────────────────────────────────

def run_full_scan(max_symbols: int = 0, retrain: bool = False,
                  progress: dict = None) -> dict:
    """
    13-module scanning pipeline, redesigned to stay under 512 MB:
    • Stocks are fetched, featurised, predicted, and freed in batches.
    • ML training uses a random sample of ≤ _TRAIN_SAMPLE_STOCKS.
    • Memory is monitored and the scan aborts before the OOM killer.
    """
    started_at = datetime.now().isoformat()
    logger.info("═" * 60)
    logger.info("  STARTING FULL SCAN  (batch=%d, train-sample=%d)",
                _BATCH_SIZE, _TRAIN_SAMPLE_STOCKS)
    logger.info("═" * 60)

    scan_market = _imp_scanner()
    fetch_daily_data, clean_data = _imp_data()
    compute_features, compute_momentum_score, compute_volume_spike_score = _imp_features()
    predict_stock, train_models_fn, batch_download = _imp_predict()
    detect_all_breakouts = _imp_breakout()
    compute_opportunity_score, generate_explanation, rank_stocks = _imp_ranking()
    get_stock_sentiment = _imp_sentiment()
    detect_regime = _imp_regime()
    generate_risk_recommendation = _imp_risk()
    run_meta_strategy, get_strategy_status = _imp_meta()

    gc.collect()
    _check_memory("imports")

    # ── Step 1-2: Scan and filter ──
    _update_progress(progress, "Scanning market & applying filters…", 5)
    logger.info("Step 1-2: Scanning market and applying filters...")
    all_stocks, filtered_stocks = scan_market(max_symbols=max_symbols)
    database.upsert_scanned_stocks(all_stocks)
    symbols = [s["symbol"] for s in filtered_stocks]
    # Free scanner results — we only need the symbol list going forward
    all_stocks_count = len(all_stocks)
    filtered_count = len(filtered_stocks)
    del all_stocks, filtered_stocks
    gc.collect()
    logger.info("Filtered to %d stocks", len(symbols))

    if not symbols:
        logger.warning("No stocks passed filters!")
        database.save_scan_log(started_at, datetime.now().isoformat(),
                               all_stocks_count, 0, "no_stocks")
        return {"status": "no_stocks", "rankings": {}}

    _check_memory("filter")

    # ── Step 5a: Train ML models (on a SAMPLE, not all stocks) ──
    if retrain or not _models_exist():
        _update_progress(progress, "Training ML models…", 10)
        logger.info("Step 5a: Training ML models on sample of %d stocks…",
                     _TRAIN_SAMPLE_STOCKS)
        import random
        train_syms = random.sample(symbols,
                                   min(_TRAIN_SAMPLE_STOCKS, len(symbols)))
        train_data = {}
        for sym in train_syms:
            df = fetch_daily_data(sym, period="1y")
            if not df.empty:
                df = clean_data(df)
                feat = compute_features(df)
                if not feat.empty:
                    train_data[sym] = feat
            del df
        gc.collect()
        if train_data:
            train_models_fn(train_data)
        del train_data
        gc.collect()
        _check_memory("training")

    # ── Step 10: Market regime detection ──
    _update_progress(progress, "Detecting market regime…", 20)
    regime_info = {"regime": "SIDEWAYS", "confidence": 0.5}
    try:
        regime_info = detect_regime()
    except Exception as e:
        logger.warning("Regime detection failed, defaulting to SIDEWAYS: %s", e)
    gc.collect()

    # ── Process stocks in batches ──
    total_sym = len(symbols)
    all_predictions = []
    processed = 0

    for batch_start in range(0, total_sym, _BATCH_SIZE):
        batch_syms = symbols[batch_start : batch_start + _BATCH_SIZE]
        batch_label = f"batch {batch_start // _BATCH_SIZE + 1}"
        _update_progress(progress,
                         f"Processing {batch_label} ({processed}/{total_sym})…",
                         25 + int(60 * processed / total_sym),
                         stocks_processed=processed, stocks_total=total_sym)

        # 3. Fetch + clean + featurise this batch only
        batch_featured = {}
        for sym in batch_syms:
            try:
                df = fetch_daily_data(sym, period="1y")
                if df.empty:
                    continue
                df = clean_data(df)
                database.save_stock_data(df, sym)
                feat = compute_features(df)
                del df
                if not feat.empty:
                    batch_featured[sym] = feat
                del feat
            except Exception as e:
                logger.debug("Fetch/feature failed for %s: %s", sym, e)
            # Rate-limit guard
            if (processed + 1) % 5 == 0:
                time.sleep(0.5)
            processed += 1

        gc.collect()

        # 5b-12. Per-stock analysis for this batch
        for sym, feat_df in batch_featured.items():
            try:
                pred = predict_stock(feat_df, regime=regime_info.get("regime", "SIDEWAYS"))
                momentum = compute_momentum_score(feat_df)
                vol_spike = compute_volume_spike_score(feat_df)
                breakout = detect_all_breakouts(feat_df)

                # RL prediction (skip on memory pressure)
                rl_pred = {"signal": "HOLD", "rl_score": 0.5, "confidence": 0}
                try:
                    from backend.rl_trading_agent import predict_with_rl
                    rl_pred = predict_with_rl(feat_df)
                except Exception:
                    pass

                sentiment_result = {"sentiment_score": 0.0, "signal": "NEUTRAL"}
                try:
                    sentiment_result = get_stock_sentiment(sym)
                except Exception:
                    pass

                meta_result = run_meta_strategy(
                    symbol=sym, df=feat_df,
                    ml_prediction=pred, rl_prediction=rl_pred,
                    momentum_score=momentum, breakout_result=breakout,
                    volume_spike_score=vol_spike,
                    sentiment_result=sentiment_result,
                    regime=regime_info.get("regime", "SIDEWAYS"),
                )

                risk_rec = {}
                try:
                    last_price = float(feat_df["close"].iloc[-1])
                    risk_rec = generate_risk_recommendation(sym, last_price, feat_df)
                except Exception:
                    pass

                opp_score = meta_result.get("final_score", 0.0)
                explanation_parts = [generate_explanation(
                    symbol=sym, signal=pred["signal"],
                    ai_probability=pred["ai_probability"],
                    momentum_score=momentum, breakout_score=breakout["score"],
                    volume_spike_score=vol_spike,
                    breakout_desc=breakout["description"],
                )]
                if meta_result.get("explanation"):
                    explanation_parts.append(meta_result["explanation"])

                contributions = meta_result.get("strategy_contributions", {})
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
                    "explanation": " | ".join(explanation_parts),
                    "last_price": feat_df["close"].iloc[-1] if not feat_df.empty else 0,
                    "risk": risk_rec,
                })
            except Exception as e:
                logger.warning("Pipeline failed for %s: %s", sym, e)

            _update_progress(progress,
                             f"Analyzing… ({processed}/{total_sym})",
                             25 + int(60 * processed / total_sym),
                             stocks_processed=processed, stocks_total=total_sym)

        # Free this batch
        del batch_featured
        gc.collect()
        _check_memory(batch_label)

    # ── Step 13: Save, rank, watchlist ──
    _update_progress(progress, "Saving predictions…", 88)
    database.save_predictions(all_predictions)

    try:
        status = get_strategy_status(regime_info.get("regime", "SIDEWAYS"))
        database.save_meta_strategy_state(
            regime=regime_info.get("regime", "SIDEWAYS"),
            weights=status.get("weights", {}),
            explanation=status.get("explanation", ""),
        )
    except Exception as e:
        logger.warning("Failed to save meta-strategy state: %s", e)

    _update_progress(progress, "Ranking & generating watchlist…", 92)
    rankings = rank_stocks(all_predictions)

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
    database.save_scan_log(started_at, finished_at,
                           stocks_scanned=all_stocks_count,
                           stocks_passed=filtered_count,
                           status="success")

    _update_progress(progress, "Complete", 100)
    logger.info("═" * 60)
    logger.info("  SCAN COMPLETE - %d predictions  |  regime: %s",
                len(all_predictions), regime_info.get("regime"))
    logger.info("═" * 60)

    return {
        "status": "success",
        "stocks_scanned": all_stocks_count,
        "stocks_passed_filter": filtered_count,
        "predictions": len(all_predictions),
        "rankings": {k: len(v) for k, v in rankings.items()},
        "regime": regime_info,
        "started_at": started_at,
        "finished_at": finished_at,
    }


# ─────────────────────────────────────────────────────────────────────────
#  QUICK / LITE SCAN — also batched
# ─────────────────────────────────────────────────────────────────────────

def run_quick_scan(symbols: list[str] = None, progress: dict = None) -> dict:
    """
    Quick scan on specific symbols (no market download / filtering).
    Also batched to stay under memory limits.
    """
    fetch_daily_data, clean_data = _imp_data()
    compute_features, compute_momentum_score, compute_volume_spike_score = _imp_features()
    predict_stock, _, _ = _imp_predict()
    detect_all_breakouts = _imp_breakout()
    compute_opportunity_score, generate_explanation, rank_stocks = _imp_ranking()

    _update_progress(progress, "Loading stocks…", 5)
    if symbols is None:
        stocks = database.get_all_scanned_stocks()
        symbols = [s["symbol"] for s in stocks
                   if s.get("avg_volume", 0) >= config.FILTER_MIN_VOLUME]

    if not symbols:
        return {"status": "no_symbols"}

    total = len(symbols)
    all_predictions = []
    processed = 0

    for batch_start in range(0, total, _BATCH_SIZE):
        batch_syms = symbols[batch_start : batch_start + _BATCH_SIZE]
        _update_progress(progress, f"Processing batch ({processed}/{total})…",
                         10 + int(75 * processed / total),
                         stocks_processed=processed, stocks_total=total)

        for sym in batch_syms:
            try:
                df = fetch_daily_data(sym, period="3mo")
                if df.empty:
                    processed += 1
                    continue
                df = clean_data(df)
                feat = compute_features(df)
                del df
                if feat.empty:
                    processed += 1
                    continue

                pred = predict_stock(feat)  # Uses default SIDEWAYS regime
                momentum = compute_momentum_score(feat)
                vol_spike = compute_volume_spike_score(feat)
                breakout = detect_all_breakouts(feat)

                opp_score = compute_opportunity_score(
                    pred["ai_probability"], momentum, breakout["score"], vol_spike,
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
                    "last_price": feat["close"].iloc[-1] if not feat.empty else 0,
                })
                del feat
            except Exception as e:
                logger.warning("Data fetch failed for %s: %s", sym, e)

            processed += 1
            if processed % 5 == 0:
                time.sleep(1)
            _update_progress(progress, f"Analyzing… ({processed}/{total})",
                             10 + int(75 * processed / total),
                             stocks_processed=processed, stocks_total=total)

        gc.collect()

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


def run_full_scan_chunked(max_symbols: int = 0, retrain: bool = False,
                          progress: dict = None) -> dict:
    started_at = datetime.now().isoformat()
    scan_date = datetime.now().strftime("%Y-%m-%d")

    scan_market = _imp_scanner()
    _, clean_data = _imp_data()
    compute_features, compute_momentum_score, compute_volume_spike_score = _imp_features()
    predict_stock, train_models_fn, batch_download = _imp_predict()
    detect_all_breakouts = _imp_breakout()
    _, generate_explanation, rank_stocks = _imp_ranking()
    get_stock_sentiment = _imp_sentiment()
    detect_regime = _imp_regime()
    generate_risk_recommendation = _imp_risk()
    run_meta_strategy, get_strategy_status = _imp_meta()

    def _persist_partial(predictions: list[dict]) -> dict:
        rankings_local = rank_stocks(predictions) if predictions else {
            "top_buys": [], "top_sells": [], "top_breakouts": [], "volume_movers": []
        }
        database.replace_watchlist(scan_date, _build_watchlist_items(rankings_local))
        return rankings_local

    def _analyse_symbol(sym: str, feat_df, regime_name: str):
        try:
            pred = predict_stock(feat_df, regime=regime_name)
            momentum = compute_momentum_score(feat_df)
            vol_spike = compute_volume_spike_score(feat_df)
            breakout = detect_all_breakouts(feat_df)

            rl_pred = {"signal": "HOLD", "rl_score": 0.5, "confidence": 0}
            try:
                from backend.rl_trading_agent import predict_with_rl
                rl_pred = predict_with_rl(feat_df)
            except Exception:
                pass

            sentiment_result = {"sentiment_score": 0.0, "signal": "NEUTRAL"}
            try:
                sentiment_result = get_stock_sentiment(sym)
            except Exception:
                pass

            meta_result = run_meta_strategy(
                symbol=sym,
                df=feat_df,
                ml_prediction=pred,
                rl_prediction=rl_pred,
                momentum_score=momentum,
                breakout_result=breakout,
                volume_spike_score=vol_spike,
                sentiment_result=sentiment_result,
                regime=regime_name,
            )

            risk_rec = {}
            try:
                risk_rec = generate_risk_recommendation(sym, float(feat_df["close"].iloc[-1]), feat_df)
            except Exception:
                pass

            explanation_parts = [generate_explanation(
                symbol=sym,
                signal=pred["signal"],
                ai_probability=pred["ai_probability"],
                momentum_score=momentum,
                breakout_score=breakout["score"],
                volume_spike_score=vol_spike,
                breakout_desc=breakout["description"],
            )]
            if meta_result.get("explanation"):
                explanation_parts.append(meta_result["explanation"])

            contributions = meta_result.get("strategy_contributions", {})
            raw_confidence = pred["confidence"]
            if raw_confidence == 0 and meta_result.get("final_score", 0) > 0:
                raw_confidence = round(min(meta_result["final_score"], 1.0), 4)

            return {
                "symbol": sym,
                "signal": meta_result.get("final_signal", pred["signal"]),
                "confidence": raw_confidence,
                "ai_probability": pred["ai_probability"],
                "momentum_score": momentum,
                "breakout_score": breakout["score"],
                "volume_spike_score": vol_spike,
                "opportunity_score": meta_result.get("final_score", 0.0),
                "meta_score": meta_result.get("final_score", 0),
                "meta_signal": meta_result.get("final_signal", "HOLD"),
                "regime": regime_name,
                "sentiment_score": contributions.get("sentiment", {}).get("score", 0),
                "rl_score": contributions.get("rl_agent", {}).get("score", 0),
                "explanation": " | ".join(explanation_parts),
                "last_price": feat_df["close"].iloc[-1] if not feat_df.empty else 0,
                "risk": risk_rec,
            }
        except Exception as e:
            logger.warning("Pipeline failed for %s: %s", sym, e)
            return None

    logger.info(
        "Starting chunked full scan (chunk=%d, train-sample=%d, fetch-workers=%d, analysis-workers=%d)",
        _BATCH_SIZE,
        _TRAIN_SAMPLE_STOCKS,
        _FETCH_WORKERS,
        _ANALYSIS_WORKERS,
    )
    gc.collect()
    _check_memory("imports")

    _update_progress(progress, "Scanning market & applying filters...", 5)
    all_stocks, filtered_stocks = scan_market(max_symbols=max_symbols)
    database.upsert_scanned_stocks(all_stocks)
    symbols = [stock["symbol"] for stock in filtered_stocks]
    all_stocks_count = len(all_stocks)
    filtered_count = len(filtered_stocks)
    del all_stocks, filtered_stocks
    gc.collect()

    if not symbols:
        database.save_scan_log(started_at, datetime.now().isoformat(), all_stocks_count, 0, "no_stocks")
        return {"status": "no_stocks", "rankings": {}}

    try:
        database.clear_predictions(scan_date)
        database.replace_watchlist(scan_date, [])
    except Exception:
        pass

    if retrain or not _models_exist():
        _update_progress(progress, "Training ML models...", 10)
        import random
        train_syms = random.sample(symbols, min(_TRAIN_SAMPLE_STOCKS, len(symbols)))
        train_data = {}
        train_downloads = batch_download(train_syms, period="1y", max_workers=max(1, _FETCH_WORKERS))
        for sym, df in train_downloads.items():
            clean_df = clean_data(df)
            feat_df = compute_features(clean_df)
            if not feat_df.empty:
                train_data[sym] = feat_df
        if train_data:
            train_models_fn(train_data)
        del train_data, train_downloads
        gc.collect()
        _check_memory("training")

    _update_progress(progress, "Detecting market regime...", 20)
    regime_info = {"regime": "SIDEWAYS", "confidence": 0.5}
    try:
        regime_info = detect_regime()
    except Exception as e:
        logger.warning("Regime detection failed, defaulting to SIDEWAYS: %s", e)

    total_sym = len(symbols)
    processed = 0
    all_predictions = []
    rankings = {"top_buys": [], "top_sells": [], "top_breakouts": [], "volume_movers": []}

    for batch_start in range(0, total_sym, _BATCH_SIZE):
        chunk_no = batch_start // _BATCH_SIZE + 1
        batch_syms = symbols[batch_start : batch_start + _BATCH_SIZE]

        _update_progress(
            progress,
            f"Downloading chunk {chunk_no} ({processed}/{total_sym})...",
            25 + int(50 * processed / total_sym),
            stocks_processed=processed,
            stocks_total=total_sym,
        )

        batch_featured = {}
        downloaded = batch_download(batch_syms, period="1y", max_workers=max(1, _FETCH_WORKERS))
        for sym in batch_syms:
            try:
                df = downloaded.get(sym)
                if df is None or df.empty:
                    continue
                clean_df = clean_data(df)
                if clean_df.empty:
                    continue
                database.save_stock_data(clean_df, sym)
                feat_df = compute_features(clean_df)
                if not feat_df.empty:
                    batch_featured[sym] = feat_df
            except Exception as e:
                logger.debug("Fetch/feature failed for %s: %s", sym, e)
            finally:
                processed += 1

        _update_progress(
            progress,
            f"Analyzing chunk {chunk_no} ({processed}/{total_sym})...",
            30 + int(50 * processed / total_sym),
            stocks_processed=min(processed, total_sym),
            stocks_total=total_sym,
        )

        chunk_predictions = []
        if batch_featured:
            with ThreadPoolExecutor(max_workers=max(1, _ANALYSIS_WORKERS)) as executor:
                futures = {
                    executor.submit(
                        _analyse_symbol, sym, feat_df, regime_info.get("regime", "SIDEWAYS")
                    ): sym
                    for sym, feat_df in batch_featured.items()
                }
                for future in as_completed(futures):
                    try:
                        result = future.result()
                    except Exception as e:
                        logger.warning("Analysis worker failed for %s: %s", futures[future], e)
                        continue
                    if result:
                        chunk_predictions.append(result)

        if chunk_predictions:
            all_predictions.extend(chunk_predictions)
            database.save_predictions_chunk(chunk_predictions, date=scan_date)
            rankings = _persist_partial(all_predictions)

        del batch_featured, downloaded, chunk_predictions
        gc.collect()
        _check_memory(f"chunk {chunk_no}")

    _update_progress(progress, "Saving final scan state...", 88, stocks_processed=processed, stocks_total=total_sym)
    try:
        status = get_strategy_status(regime_info.get("regime", "SIDEWAYS"))
        database.save_meta_strategy_state(
            regime=regime_info.get("regime", "SIDEWAYS"),
            weights=status.get("weights", {}),
            explanation=status.get("explanation", ""),
        )
    except Exception as e:
        logger.warning("Failed to save meta-strategy state: %s", e)

    rankings = _persist_partial(all_predictions)
    finished_at = datetime.now().isoformat()
    database.save_scan_log(
        started_at,
        finished_at,
        stocks_scanned=all_stocks_count,
        stocks_passed=filtered_count,
        status="success",
    )

    _update_progress(progress, "Complete", 100, stocks_processed=processed, stocks_total=total_sym)
    return {
        "status": "success",
        "stocks_scanned": all_stocks_count,
        "stocks_passed_filter": filtered_count,
        "predictions": len(all_predictions),
        "rankings": {k: len(v) for k, v in rankings.items()},
        "regime": regime_info,
        "started_at": started_at,
        "finished_at": finished_at,
        "chunks_processed": (total_sym + _BATCH_SIZE - 1) // _BATCH_SIZE,
    }


run_full_scan = run_full_scan_chunked


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    database.init_db()
    result = run_full_scan_chunked(max_symbols=30, retrain=True)
    print(result)
