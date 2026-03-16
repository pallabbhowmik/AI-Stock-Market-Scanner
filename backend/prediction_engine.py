"""
Prediction Engine
Trains and runs AI models (RandomForest, XGBoost, GradientBoosting)
to predict next-day price direction.
"""
import os
import logging
import pickle

import numpy as np
import pandas as pd

from backend import config
from backend.feature_engineering import get_feature_columns

logger = logging.getLogger(__name__)


def _model_path(name: str) -> str:
    os.makedirs(config.MODEL_DIR, exist_ok=True)
    return os.path.join(config.MODEL_DIR, f"{name}.pkl")


def _save(obj, name: str):
    with open(_model_path(name), "wb") as f:
        pickle.dump(obj, f)


def _load(name: str):
    path = _model_path(name)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


# ─── Model Cache (avoid re-loading pickles on every predict call) ────────
_model_cache: dict = {}


def _load_cached(name: str):
    """Load a pickle file, returning cached version if available."""
    if name not in _model_cache:
        _model_cache[name] = _load(name)
    return _model_cache[name]


def clear_model_cache():
    """Clear the model cache (call after retraining)."""
    _model_cache.clear()


# ─── Model Definitions ──────────────────────────────────────────────────────

def _create_models() -> dict:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    import xgboost as xgb
    return {
        "RandomForest": RandomForestClassifier(
            n_estimators=200, max_depth=10, min_samples_split=10,
            min_samples_leaf=5, random_state=42, n_jobs=-1,
        ),
        "XGBoost": xgb.XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            use_label_encoder=False, eval_metric="logloss", random_state=42,
        ),
        "GradientBoosting": GradientBoostingClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            subsample=0.8, random_state=42,
        ),
    }


# ─── Training ────────────────────────────────────────────────────────────────

def train_models(all_data: dict[str, pd.DataFrame]) -> dict:
    """
    Train ensemble models on combined data from multiple stocks.
    Returns {model_name: {model, scaler, accuracy, auc}}.
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score, roc_auc_score
    # Combine data from all stocks
    dfs = []
    feature_cols = get_feature_columns()

    for symbol, df in all_data.items():
        if df.empty or "direction" not in df.columns:
            continue
        required = feature_cols + ["direction"]
        clean = df.dropna(subset=required)
        if len(clean) >= 30:
            dfs.append(clean)

    if not dfs:
        logger.warning("No training data available")
        return {}

    combined = pd.concat(dfs, ignore_index=True)
    X = combined[feature_cols].values
    y = combined["direction"].values

    logger.info("Training on %d samples, %d features", len(X), len(feature_cols))

    # Train/test split (time-based)
    split = int(len(X) * config.TRAIN_TEST_SPLIT)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    results = {}
    models = _create_models()

    for name, model in models.items():
        logger.info("Training %s...", name)
        if name == "XGBoost":
            model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)
        else:
            model.fit(X_train_s, y_train)

        y_pred = model.predict(X_test_s)
        y_prob = model.predict_proba(X_test_s)[:, 1]

        acc = accuracy_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else 0.5

        results[name] = {"model": model, "accuracy": acc, "auc": auc}
        logger.info("%s → Accuracy: %.4f, AUC: %.4f", name, acc, auc)

    # Save models and scaler
    _save(scaler, "scaler")
    _save(feature_cols, "feature_cols")
    for name, res in results.items():
        _save(res["model"], name)

    # Save ensemble metadata
    _save({n: {"accuracy": r["accuracy"], "auc": r["auc"]} for n, r in results.items()}, "ensemble_meta")

    # Invalidate cache so next predict uses new models
    clear_model_cache()

    return results


def predict_stock(df: pd.DataFrame) -> dict:
    """
    Predict direction for a single stock using the ensemble.
    Returns {signal, confidence, ai_probability, model_votes}.
    """
    feature_cols = _load_cached("feature_cols")
    scaler = _load_cached("scaler")
    meta = _load_cached("ensemble_meta")

    if feature_cols is None or scaler is None or meta is None:
        return {"signal": "HOLD", "confidence": 0, "ai_probability": 0.5}

    # Prepare latest row
    required = [c for c in feature_cols if c in df.columns]
    if len(required) < len(feature_cols) * 0.8:
        return {"signal": "HOLD", "confidence": 0, "ai_probability": 0.5}

    latest = df.iloc[-1:][feature_cols]
    if latest.isna().any(axis=1).values[0]:
        # Fill missing with column median
        for col in latest.columns:
            if latest[col].isna().values[0]:
                latest[col] = df[col].median()

    X = scaler.transform(latest.values)

    # Ensemble prediction (weighted by AUC)
    probabilities = []
    weights = []
    model_votes = {}

    for name in meta:
        model = _load_cached(name)
        if model is None:
            continue
        prob = model.predict_proba(X)[0, 1]
        auc_w = meta[name]["auc"]
        probabilities.append(prob)
        weights.append(auc_w)
        model_votes[name] = round(prob, 4)

    if not probabilities:
        return {"signal": "HOLD", "confidence": 0, "ai_probability": 0.5}

    # Weighted average probability
    weights = np.array(weights)
    weights = weights / weights.sum()
    ensemble_prob = np.average(probabilities, weights=weights)

    # Generate signal
    if ensemble_prob >= 0.60:
        signal = "BUY"
    elif ensemble_prob <= 0.40:
        signal = "SELL"
    else:
        signal = "HOLD"

    # Confidence is how far from 0.5
    confidence = abs(ensemble_prob - 0.5) * 2  # 0 to 1 scale

    return {
        "signal": signal,
        "confidence": round(confidence, 4),
        "ai_probability": round(ensemble_prob, 4),
        "model_votes": model_votes,
    }


def predict_batch(stock_data: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """Run predictions on a batch of stocks."""
    results = {}
    for symbol, df in stock_data.items():
        results[symbol] = predict_stock(df)
    logger.info("Predicted %d stocks", len(results))
    return results
