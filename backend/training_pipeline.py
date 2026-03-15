"""
Automated Training Pipeline
Orchestrates the full model lifecycle: data collection → feature engineering
→ ML training → RL training → evaluation → versioning → deployment.

Runs entirely in background threads so the dashboard stays responsive.
"""
import os
import time
import logging
import threading
from datetime import datetime, timedelta

from backend import config, database
from backend.data_pipeline import fetch_daily_data, clean_data
from backend.feature_engineering import compute_features
from backend.prediction_engine import train_models, predict_stock, _load
from backend.rl_trading_agent import train_rl_agent
from backend.model_evaluation import evaluate_predictions, evaluate_model_on_validation
from backend.model_versioning import (
    save_version, deploy_version, should_deploy,
    get_current_version, get_all_versions,
)

logger = logging.getLogger(__name__)

# ─── Pipeline State ──────────────────────────────────────────────────────────

_pipeline_state = {
    "status": "idle",            # idle | collecting_data | training | evaluating | deploying | completed | error
    "last_training": None,       # ISO timestamp
    "last_result": None,         # summary dict
    "training_in_progress": False,
    "error": None,
}
_pipeline_lock = threading.Lock()


def get_pipeline_status() -> dict:
    """Return current pipeline state (thread-safe read)."""
    with _pipeline_lock:
        status = dict(_pipeline_state)

    # Attach current model version info
    current = get_current_version()
    if current:
        status["model_version"] = current.get("version_id", "–")
        status["model_accuracy"] = current.get("accuracy", 0)
        status["model_auc"] = current.get("auc", 0)
        status["model_sharpe"] = current.get("sharpe_ratio", 0)
        status["model_training_date"] = current.get("training_date", "")
        status["model_dataset_size"] = current.get("dataset_size", 0)
    else:
        status["model_version"] = "–"
        status["model_accuracy"] = 0
        status["model_auc"] = 0

    status["all_versions"] = get_all_versions()
    return status


def _set_state(**kwargs):
    with _pipeline_lock:
        _pipeline_state.update(kwargs)


# ─── Data Collection ─────────────────────────────────────────────────────────

def collect_latest_data(max_symbols: int = 0) -> dict[str, any]:
    """
    Fetch fresh market data for all tracked stocks.
    Returns {symbol: DataFrame}.
    """
    _set_state(status="collecting_data")
    logger.info("Collecting latest market data...")

    stocks = database.get_all_scanned_stocks()
    if not stocks:
        # Use fallback symbols
        from backend.market_scanner import scan_market
        all_stocks, filtered = scan_market(max_symbols=max_symbols)
        database.upsert_scanned_stocks(all_stocks)
        stocks = filtered if filtered else all_stocks

    symbols = [s["symbol"] if isinstance(s, dict) else s for s in stocks]
    if max_symbols > 0:
        symbols = symbols[:max_symbols]

    stock_data = {}
    for sym in symbols:
        try:
            df = fetch_daily_data(sym, period="1y")
            if not df.empty:
                df = clean_data(df)
                database.save_stock_data(df, sym)
                stock_data[sym] = df
        except Exception as e:
            logger.debug("Data fetch failed for %s: %s", sym, e)

    logger.info("Collected data for %d / %d stocks", len(stock_data), len(symbols))
    return stock_data


# ─── Feature Engineering ─────────────────────────────────────────────────────

def compute_all_features(stock_data: dict) -> dict:
    """Compute technical indicators for all stocks."""
    featured = {}
    for sym, df in stock_data.items():
        try:
            ft = compute_features(df)
            if not ft.empty and len(ft) >= 50:
                featured[sym] = ft
        except Exception as e:
            logger.debug("Feature computation failed for %s: %s", sym, e)
    logger.info("Computed features for %d stocks", len(featured))
    return featured


# ─── Full Training Pipeline ──────────────────────────────────────────────────

def run_training_pipeline(max_symbols: int = 0) -> dict:
    """
    Execute the full training pipeline synchronously.
    Steps: data → features → ML train → RL train → evaluate → version → deploy.
    Returns a summary dict.
    """
    with _pipeline_lock:
        if _pipeline_state["training_in_progress"]:
            return {"status": "already_running"}
        _pipeline_state["training_in_progress"] = True
        _pipeline_state["error"] = None

    started_at = datetime.now()
    logger.info("=" * 60)
    logger.info("  AUTOMATED TRAINING PIPELINE STARTED")
    logger.info("=" * 60)

    try:
        # 1. Collect data
        stock_data = collect_latest_data(max_symbols)
        if not stock_data:
            _set_state(status="error", error="No stock data available")
            return {"status": "error", "error": "No stock data"}

        # 2. Feature engineering
        _set_state(status="training")
        featured_data = compute_all_features(stock_data)
        if not featured_data:
            _set_state(status="error", error="Feature computation failed")
            return {"status": "error", "error": "No features computed"}

        dataset_size = sum(len(df) for df in featured_data.values())

        # 3. Train ML models
        logger.info("Training ML ensemble models...")
        ml_results = train_models(featured_data)

        # 4. Train RL agent
        logger.info("Training RL agent...")
        try:
            train_rl_agent(featured_data)
        except Exception as e:
            logger.warning("RL training failed (non-fatal): %s", e)

        # 5. Evaluate
        _set_state(status="evaluating")
        logger.info("Evaluating model performance...")

        # Compute aggregate metrics from ML training results
        if ml_results:
            avg_acc = sum(r["accuracy"] for r in ml_results.values()) / len(ml_results)
            avg_auc = sum(r["auc"] for r in ml_results.values()) / len(ml_results)
        else:
            avg_acc = 0
            avg_auc = 0

        # Run predictions on a validation subset to get trading metrics
        val_metrics = _evaluate_on_validation(featured_data)

        metrics = {
            "accuracy": round(avg_acc, 4),
            "auc": round(avg_auc, 4),
            "sharpe_ratio": val_metrics.get("sharpe_ratio", 0),
            "max_drawdown": val_metrics.get("max_drawdown", 0),
            "profit_factor": val_metrics.get("profit_factor", 0),
            "per_model": {
                name: {"accuracy": r["accuracy"], "auc": r["auc"]}
                for name, r in ml_results.items()
            } if ml_results else {},
        }

        # 6. Version the model
        _set_state(status="deploying")
        version_id = save_version(metrics, dataset_size=dataset_size)

        # 7. Auto-deploy if better than current
        deployed = False
        if should_deploy(metrics):
            deploy_version(version_id)
            deployed = True
            logger.info("New model %s deployed to production", version_id)
        else:
            logger.info("Current production model retained (new model did not improve)")

        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()

        result = {
            "status": "success",
            "version_id": version_id,
            "deployed": deployed,
            "metrics": metrics,
            "dataset_size": dataset_size,
            "stocks_trained": len(featured_data),
            "duration_seconds": round(duration, 1),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }

        _set_state(
            status="completed",
            last_training=finished_at.isoformat(),
            last_result=result,
        )

        # Save training log to database
        _save_training_log(result)

        logger.info("=" * 60)
        logger.info("  TRAINING COMPLETE — %s | acc=%.2f%% | deployed=%s",
                     version_id, avg_acc * 100, deployed)
        logger.info("=" * 60)

        return result

    except Exception as e:
        logger.error("Training pipeline failed: %s", e, exc_info=True)
        _set_state(status="error", error=str(e))
        return {"status": "error", "error": str(e)}

    finally:
        with _pipeline_lock:
            _pipeline_state["training_in_progress"] = False


def run_training_pipeline_async(max_symbols: int = 0):
    """Start the training pipeline in a background thread."""
    with _pipeline_lock:
        if _pipeline_state["training_in_progress"]:
            logger.warning("Training already in progress")
            return False

    thread = threading.Thread(
        target=run_training_pipeline,
        args=(max_symbols,),
        daemon=True,
    )
    thread.start()
    logger.info("Training pipeline started in background thread")
    return True


# ─── Validation Evaluation ───────────────────────────────────────────────────

def _evaluate_on_validation(featured_data: dict) -> dict:
    """Run predictions on the last 20% of data as validation."""
    predictions = []
    val_data = {}

    for sym, df in featured_data.items():
        try:
            # Use last 20% as validation
            split_idx = int(len(df) * 0.8)
            val_df = df.iloc[split_idx:]
            if len(val_df) < 5:
                continue

            pred = predict_stock(val_df)
            predictions.append({"symbol": sym, **pred})
            val_data[sym] = val_df
        except Exception:
            continue

    if not predictions:
        return {"sharpe_ratio": 0, "max_drawdown": 0, "profit_factor": 1.0}

    return evaluate_predictions(predictions, val_data)


def _save_training_log(result: dict):
    """Persist training result to the database."""
    try:
        database.save_training_log(result)
    except Exception as e:
        logger.debug("Could not save training log: %s", e)


# ─── Rollback ────────────────────────────────────────────────────────────────

def rollback_model(steps: int = 1) -> dict:
    """Roll back the production model to a previous version."""
    from backend.model_versioning import rollback
    vid = rollback(steps)
    if vid:
        return {"status": "rolled_back", "version_id": vid}
    return {"status": "error", "error": "No version to roll back to"}
