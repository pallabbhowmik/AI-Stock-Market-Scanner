"""
Model Training Module
Trains, evaluates and compares multiple ML models for stock prediction.
Supports: Random Forest, XGBoost, Gradient Boosting, LSTM.
"""
import os
import logging
import pickle
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, roc_auc_score,
)
import xgboost as xgb

import config

logger = logging.getLogger(__name__)

# ─── Utility ──────────────────────────────────────────────────────────────────

def _ensure_model_dir():
    os.makedirs(config.MODEL_SAVE_DIR, exist_ok=True)


def save_model(model, scaler, name: str, feature_cols: list) -> str:
    """Persist a trained model, its scaler, and feature columns."""
    _ensure_model_dir()
    path = os.path.join(config.MODEL_SAVE_DIR, f"{name}.pkl")
    with open(path, "wb") as f:
        pickle.dump({"model": model, "scaler": scaler, "features": feature_cols}, f)
    logger.info("Saved model to %s", path)
    return path


def load_model(name: str):
    """Load a previously saved model bundle."""
    path = os.path.join(config.MODEL_SAVE_DIR, f"{name}.pkl")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model not found: {path}")
    with open(path, "rb") as f:
        bundle = pickle.load(f)
    return bundle["model"], bundle["scaler"], bundle["features"]


# ─── Sklearn-based Models ────────────────────────────────────────────────────

def train_random_forest(X_train, y_train, X_test, y_test) -> dict:
    """Train a Random Forest classifier and return metrics."""
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    metrics = _compute_metrics(y_test, y_pred, y_prob)
    metrics["model"] = model
    metrics["name"] = "RandomForest"
    return metrics


def train_gradient_boosting(X_train, y_train, X_test, y_test) -> dict:
    """Train a Gradient Boosting classifier and return metrics."""
    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    metrics = _compute_metrics(y_test, y_pred, y_prob)
    metrics["model"] = model
    metrics["name"] = "GradientBoosting"
    return metrics


def train_xgboost(X_train, y_train, X_test, y_test) -> dict:
    """Train an XGBoost classifier and return metrics."""
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    metrics = _compute_metrics(y_test, y_pred, y_prob)
    metrics["model"] = model
    metrics["name"] = "XGBoost"
    return metrics


# ─── LSTM Model ───────────────────────────────────────────────────────────────

def _build_lstm_model(n_features: int):
    """Build a Keras LSTM model for binary classification."""
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization

    model = Sequential([
        LSTM(64, return_sequences=True,
             input_shape=(config.LSTM_SEQUENCE_LENGTH, n_features)),
        Dropout(0.3),
        BatchNormalization(),
        LSTM(32, return_sequences=False),
        Dropout(0.3),
        Dense(16, activation="relu"),
        Dense(1, activation="sigmoid"),
    ])
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    return model


def _create_sequences(X, y, seq_len: int):
    """Create sliding-window sequences for LSTM."""
    Xs, ys = [], []
    for i in range(len(X) - seq_len):
        Xs.append(X[i : i + seq_len])
        ys.append(y[i + seq_len])
    return np.array(Xs), np.array(ys)


def train_lstm(X_train, y_train, X_test, y_test) -> dict:
    """Train an LSTM model and return metrics."""
    from tensorflow.keras.callbacks import EarlyStopping
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning)

    seq_len = config.LSTM_SEQUENCE_LENGTH
    if len(X_train) <= seq_len or len(X_test) <= seq_len:
        logger.warning("Not enough data for LSTM sequences")
        return {"name": "LSTM", "accuracy": 0, "model": None}

    X_train_seq, y_train_seq = _create_sequences(X_train, y_train, seq_len)
    X_test_seq, y_test_seq = _create_sequences(X_test, y_test, seq_len)

    model = _build_lstm_model(X_train.shape[1])
    early_stop = EarlyStopping(
        monitor="val_loss", patience=3, restore_best_weights=True
    )
    model.fit(
        X_train_seq, y_train_seq,
        epochs=min(getattr(config, 'LSTM_EPOCHS', 30), 30),
        batch_size=config.LSTM_BATCH_SIZE,
        validation_data=(X_test_seq, y_test_seq),
        callbacks=[early_stop],
        verbose=0,
    )

    y_prob = model.predict(X_test_seq, verbose=0).flatten()
    y_pred = (y_prob > 0.5).astype(int)
    metrics = _compute_metrics(y_test_seq, y_pred, y_prob)
    metrics["model"] = model
    metrics["name"] = "LSTM"
    return metrics


# ─── Evaluation ───────────────────────────────────────────────────────────────

def _compute_metrics(y_true, y_pred, y_prob) -> dict:
    """Compute classification metrics."""
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "auc_roc": roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0,
        "predictions": y_pred,
        "probabilities": y_prob,
    }


def cross_validate_model(model_fn, X, y, n_splits: int = 5) -> dict:
    """Time-series cross-validation for a model training function."""
    tscv = TimeSeriesSplit(n_splits=n_splits)
    results = []

    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]

        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X_tr)
        X_te = scaler.transform(X_te)

        metrics = model_fn(X_tr, y_tr, X_te, y_te)
        results.append(metrics)
        logger.info("Fold %d - %s: Accuracy=%.4f AUC=%.4f",
                     fold + 1, metrics.get("name", ""), metrics["accuracy"], metrics.get("auc_roc", 0))

    # Average metrics
    avg = {
        "name": results[0].get("name", ""),
        "accuracy": np.mean([r["accuracy"] for r in results]),
        "precision": np.mean([r["precision"] for r in results]),
        "recall": np.mean([r["recall"] for r in results]),
        "f1": np.mean([r["f1"] for r in results]),
        "auc_roc": np.mean([r.get("auc_roc", 0) for r in results]),
        "folds": results,
    }
    return avg


def walk_forward_test(model_fn, X, y, train_size: int, test_size: int) -> dict:
    """Walk-forward validation: train on a rolling window, test on next block."""
    all_preds, all_true, all_probs = [], [], []
    n = len(X)
    start = 0

    while start + train_size + test_size <= n:
        train_end = start + train_size
        test_end = train_end + test_size

        X_tr, y_tr = X[start:train_end], y[start:train_end]
        X_te, y_te = X[train_end:test_end], y[train_end:test_end]

        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X_tr)
        X_te = scaler.transform(X_te)

        metrics = model_fn(X_tr, y_tr, X_te, y_te)
        all_preds.extend(metrics["predictions"])
        all_true.extend(y_te)
        all_probs.extend(metrics["probabilities"])

        start += test_size  # slide forward

    all_preds = np.array(all_preds)
    all_true = np.array(all_true)
    all_probs = np.array(all_probs)
    overall = _compute_metrics(all_true, all_preds, all_probs)
    overall["name"] = f"WalkForward_{model_fn.__name__}"
    return overall


# ─── Train All Models ─────────────────────────────────────────────────────────

def train_all_models(X, y_direction, feature_cols, ticker: str = "ALL") -> dict:
    """Train all models, evaluate, and save the best one."""
    split = int(len(X) * config.TRAIN_TEST_SPLIT)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y_direction[:split], y_direction[split:]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    results = {}
    model_fns = {
        "RandomForest": train_random_forest,
        "GradientBoosting": train_gradient_boosting,
        "XGBoost": train_xgboost,
    }

    for name, fn in model_fns.items():
        logger.info("Training %s...", name)
        res = fn(X_train_scaled, y_train, X_test_scaled, y_test)
        results[name] = res
        logger.info("%s - Accuracy: %.4f, AUC: %.4f", name, res["accuracy"], res.get("auc_roc", 0))

    # LSTM
    try:
        logger.info("Training LSTM...")
        lstm_res = train_lstm(X_train_scaled, y_train, X_test_scaled, y_test)
        results["LSTM"] = lstm_res
        logger.info("LSTM - Accuracy: %.4f, AUC: %.4f", lstm_res["accuracy"], lstm_res.get("auc_roc", 0))
    except Exception as e:
        logger.warning("LSTM training failed: %s", e)

    # Find best model by AUC
    best_name = max(
        [k for k in results if results[k].get("model") is not None],
        key=lambda k: results[k].get("auc_roc", 0),
    )
    best = results[best_name]
    logger.info("Best model: %s (AUC: %.4f)", best_name, best.get("auc_roc", 0))

    # Save the best sklearn-type model
    if best_name != "LSTM":
        save_model(best["model"], scaler, f"{ticker}_{best_name}", feature_cols)

    return results


def predict(ticker: str, X_new: np.ndarray, model_name: Optional[str] = None) -> dict:
    """Generate predictions using a saved model."""
    if model_name is None:
        # Try to find any saved model for this ticker
        _ensure_model_dir()
        candidates = [f for f in os.listdir(config.MODEL_SAVE_DIR) if f.startswith(ticker)]
        if not candidates:
            raise FileNotFoundError(f"No saved models found for {ticker}")
        model_name = candidates[0].replace(".pkl", "")

    model, scaler, features = load_model(model_name)
    X_scaled = scaler.transform(X_new)
    probabilities = model.predict_proba(X_scaled)[:, 1]
    directions = (probabilities > 0.5).astype(int)

    return {
        "direction": directions,
        "probability": probabilities,
        "model_name": model_name,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data_pipeline import load_data
    from feature_engineering import compute_all_features, prepare_ml_dataset

    df = load_data("RELIANCE.NS")
    if not df.empty:
        featured = compute_all_features(df)
        X, y_dir, y_ret, dates, feat_cols = prepare_ml_dataset(featured)
        results = train_all_models(X, y_dir, feat_cols, ticker="RELIANCE.NS")

        print("\n=== Model Comparison ===")
        for name, res in results.items():
            print(f"{name}: Accuracy={res['accuracy']:.4f}, "
                  f"Precision={res.get('precision', 0):.4f}, "
                  f"AUC={res.get('auc_roc', 0):.4f}")
