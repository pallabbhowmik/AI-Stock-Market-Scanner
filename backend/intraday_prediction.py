"""
Intraday Prediction Engine
Multi-horizon prediction for intraday trading using:
  - HistGradientBoosting (handles NaN natively)
  - LightGBM (fast, handles NaN)
  - XGBoost (with NaN passthrough)
  - Calibrated ensemble with time-decay weighting

Predicts 15m, 30m, and 1h forward returns with probability outputs.
"""
import gc
import logging
import os
import pickle
from typing import Optional

import numpy as np
import pandas as pd

from backend import config
from backend.intraday_features import get_intraday_feature_columns

logger = logging.getLogger(__name__)

# ─── Paths ───────────────────────────────────────────────────────────────────

INTRADAY_MODEL_DIR = os.path.join(config.MODEL_DIR, "intraday")

HORIZONS = ["15m", "30m", "1h"]   # prediction horizons
TARGET_COLS = {h: f"direction_{h}" for h in HORIZONS}

_model_cache: dict = {}


def _path(name: str) -> str:
    os.makedirs(INTRADAY_MODEL_DIR, exist_ok=True)
    return os.path.join(INTRADAY_MODEL_DIR, f"{name}.pkl")


def _save(obj, name: str):
    with open(_path(name), "wb") as f:
        pickle.dump(obj, f)


def _load(name: str):
    p = _path(name)
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def _load_cached(name: str):
    if name not in _model_cache:
        _model_cache[name] = _load(name)
    return _model_cache[name]


def clear_intraday_cache():
    _model_cache.clear()


# ─── Model Definitions ──────────────────────────────────────────────────────

def _create_models() -> dict:
    """Create models that handle NaN natively for robust intraday data."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    import xgboost as xgb

    models = {
        "HistGB": HistGradientBoostingClassifier(
            max_iter=200, max_depth=6, learning_rate=0.05,
            min_samples_leaf=20, max_bins=128,
            l2_regularization=1.0, early_stopping=True,
            n_iter_no_change=15, validation_fraction=0.15,
            random_state=42,
        ),
        "XGB": xgb.XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.7,
            reg_alpha=0.5, reg_lambda=1.0,
            use_label_encoder=False, eval_metric="logloss",
            random_state=42,
        ),
    }

    # Try LightGBM (optional, may not be installed)
    try:
        import lightgbm as lgb
        models["LGBM"] = lgb.LGBMClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.7,
            reg_alpha=0.3, reg_lambda=1.0,
            min_child_samples=20, num_leaves=31,
            random_state=42, verbose=-1,
        )
    except ImportError:
        logger.info("LightGBM not available, using HistGB + XGB only")

    return models


# ─── Training ────────────────────────────────────────────────────────────────

def train_intraday_models(all_data: dict[str, pd.DataFrame]) -> dict:
    """
    Train intraday models on combined 5-minute data from multiple stocks.

    Args:
        all_data: {symbol: featured_5m_df} with targets already computed

    Returns:
        {horizon: {model_name: {accuracy, auc}}}
    """
    from sklearn.metrics import accuracy_score, roc_auc_score

    feature_cols = get_intraday_feature_columns()
    results = {}

    # Combine data
    dfs = []
    for sym, df in all_data.items():
        if df.empty:
            continue
        # Ensure targets exist
        has_targets = all(f"direction_{h}" in df.columns for h in HORIZONS)
        if not has_targets:
            continue
        avail_cols = [c for c in feature_cols if c in df.columns]
        if len(avail_cols) < len(feature_cols) * 0.7:
            continue
        dfs.append(df)

    if not dfs:
        logger.warning("No intraday training data available")
        return {}

    combined = pd.concat(dfs, ignore_index=True)
    del dfs
    gc.collect()

    # Cap samples
    _MAX_ROWS = 50_000
    if len(combined) > _MAX_ROWS:
        combined = combined.sample(n=_MAX_ROWS, random_state=42).sort_index()

    logger.info("Intraday training: %d samples, %d features",
                len(combined), len(feature_cols))

    # Ensure all feature columns exist (fill missing with NaN)
    for col in feature_cols:
        if col not in combined.columns:
            combined[col] = np.nan

    X = combined[feature_cols].values

    # Train a model ensemble per horizon
    for horizon in HORIZONS:
        target_col = TARGET_COLS[horizon]
        if target_col not in combined.columns:
            continue

        y = combined[target_col].values
        mask = ~np.isnan(y)
        X_h, y_h = X[mask], y[mask].astype(int)

        if len(X_h) < 200:
            logger.warning("Insufficient data for %s horizon (%d samples)", horizon, len(X_h))
            continue

        # Time-based split (last 20% for validation)
        split = int(len(X_h) * 0.8)
        X_train, X_test = X_h[:split], X_h[split:]
        y_train, y_test = y_h[:split], y_h[split:]

        models = _create_models()
        horizon_results = {}

        for name, model in models.items():
            try:
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                y_prob = model.predict_proba(X_test)[:, 1]

                acc = accuracy_score(y_test, y_pred)
                auc = roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else 0.5

                horizon_results[name] = {"accuracy": acc, "auc": auc}
                _save(model, f"{horizon}_{name}")
                logger.info("%s/%s → Accuracy: %.4f, AUC: %.4f", horizon, name, acc, auc)
            except Exception as e:
                logger.warning("Failed to train %s/%s: %s", horizon, name, e)

        results[horizon] = horizon_results

    # Save feature columns and metadata
    _save(feature_cols, "feature_cols")
    _save(results, "ensemble_meta")

    del combined, X
    gc.collect()
    clear_intraday_cache()

    return results


# ─── Prediction ──────────────────────────────────────────────────────────────

def predict_intraday(df: pd.DataFrame, horizon: str = "15m") -> dict:
    """
    Predict intraday direction for a single stock at the given horizon.

    Returns:
        {signal, confidence, probability, horizon, model_votes,
         entry_price, stop_loss, target_price}
    """
    feature_cols = _load_cached("feature_cols")
    meta = _load_cached("ensemble_meta")

    if feature_cols is None or meta is None:
        return _default_result(horizon)

    horizon_meta = meta.get(horizon, {})
    if not horizon_meta:
        return _default_result(horizon)

    # Prepare latest row
    for col in feature_cols:
        if col not in df.columns:
            df[col] = np.nan

    latest = df.iloc[-1:][feature_cols].copy()
    X = latest.values

    # Ensemble prediction weighted by AUC
    probabilities = []
    weights = []
    model_votes = {}

    for name in horizon_meta:
        model = _load_cached(f"{horizon}_{name}")
        if model is None:
            continue
        try:
            prob = model.predict_proba(X)[0, 1]
            auc_w = horizon_meta[name].get("auc", 0.5)
            probabilities.append(prob)
            weights.append(auc_w)
            model_votes[name] = round(prob, 4)
        except Exception as e:
            logger.debug("Predict failed for %s/%s: %s", horizon, name, e)

    if not probabilities:
        return _default_result(horizon)

    # Weighted average
    w = np.array(weights)
    w = w / w.sum()
    ensemble_prob = float(np.average(probabilities, weights=w))

    # Signal with stricter thresholds for intraday (need higher conviction)
    if ensemble_prob >= 0.62:
        signal = "BUY"
    elif ensemble_prob <= 0.38:
        signal = "SELL"
    else:
        signal = "HOLD"

    confidence = abs(ensemble_prob - 0.5) * 2

    # Compute stop-loss and target from ATR
    last_row = df.iloc[-1]
    entry_price = float(last_row.get("close", 0))
    atr = float(last_row.get("atr_14", entry_price * 0.01))

    if signal == "BUY":
        stop_loss = round(entry_price - 1.5 * atr, 2)
        target_price = round(entry_price + 2.5 * atr, 2)
    elif signal == "SELL":
        stop_loss = round(entry_price + 1.5 * atr, 2)
        target_price = round(entry_price - 2.5 * atr, 2)
    else:
        stop_loss = 0
        target_price = 0

    return {
        "signal": signal,
        "confidence": round(confidence, 4),
        "probability": round(ensemble_prob, 4),
        "horizon": horizon,
        "model_votes": model_votes,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "target_price": target_price,
        "risk_reward": round(2.5 / 1.5, 2) if signal != "HOLD" else 0,
    }


def predict_all_horizons(df: pd.DataFrame) -> dict:
    """Run prediction across all horizons and pick the strongest signal."""
    results = {}
    best_signal = None
    best_confidence = 0

    for h in HORIZONS:
        pred = predict_intraday(df, horizon=h)
        results[h] = pred
        if pred["confidence"] > best_confidence and pred["signal"] != "HOLD":
            best_confidence = pred["confidence"]
            best_signal = pred

    # Primary recommendation
    primary = best_signal or results.get("15m", _default_result("15m"))

    return {
        "primary": primary,
        "horizons": results,
        "consensus": _compute_consensus(results),
    }


def _compute_consensus(results: dict) -> dict:
    """Check if all horizons agree on direction."""
    signals = [r["signal"] for r in results.values()]
    buy_count = signals.count("BUY")
    sell_count = signals.count("SELL")
    total = len(signals)

    if buy_count == total:
        return {"direction": "STRONG_BUY", "agreement": 1.0}
    elif sell_count == total:
        return {"direction": "STRONG_SELL", "agreement": 1.0}
    elif buy_count > sell_count:
        return {"direction": "BUY", "agreement": buy_count / total}
    elif sell_count > buy_count:
        return {"direction": "SELL", "agreement": sell_count / total}
    else:
        return {"direction": "NEUTRAL", "agreement": 0.0}


def _default_result(horizon: str) -> dict:
    return {
        "signal": "HOLD", "confidence": 0, "probability": 0.5,
        "horizon": horizon, "model_votes": {},
        "entry_price": 0, "stop_loss": 0, "target_price": 0,
        "risk_reward": 0,
    }
