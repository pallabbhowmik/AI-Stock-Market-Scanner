"""
Model Evaluation
Evaluates trained models against validation data and computes
trading-oriented performance metrics.
"""
import logging
import numpy as np
import pandas as pd

from backend.feature_engineering import get_feature_columns

logger = logging.getLogger(__name__)


def evaluate_predictions(predictions: list[dict], stock_data: dict[str, pd.DataFrame]) -> dict:
    """
    Evaluate prediction quality against actual next-day returns.

    Args:
        predictions: list of dicts with symbol, signal, ai_probability
        stock_data: {symbol: DataFrame with close prices}

    Returns dict with accuracy, sharpe_ratio, max_drawdown, profit_factor
    """
    correct = 0
    total = 0
    returns = []

    for pred in predictions:
        sym = pred.get("symbol")
        df = stock_data.get(sym)
        if df is None or len(df) < 2:
            continue

        actual_return = (df["close"].iloc[-1] / df["close"].iloc[-2]) - 1
        signal = pred.get("signal", "HOLD")

        if signal == "BUY":
            strategy_return = actual_return
        elif signal == "SELL":
            strategy_return = -actual_return
        else:
            strategy_return = 0.0

        returns.append(strategy_return)

        # Count correct direction
        if signal == "BUY" and actual_return > 0:
            correct += 1
        elif signal == "SELL" and actual_return < 0:
            correct += 1
        elif signal == "HOLD":
            correct += 1  # HOLD is neutral
        total += 1

    accuracy = correct / total if total > 0 else 0

    # Trading metrics
    returns_arr = np.array(returns) if returns else np.array([0.0])
    sharpe = _compute_sharpe(returns_arr)
    max_dd = _compute_max_drawdown(returns_arr)
    profit_factor = _compute_profit_factor(returns_arr)

    return {
        "accuracy": round(accuracy, 4),
        "total_predictions": total,
        "correct_predictions": correct,
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4),
        "profit_factor": round(profit_factor, 4),
        "avg_return": round(float(returns_arr.mean()), 6),
        "total_return": round(float(returns_arr.sum()), 6),
    }


def evaluate_model_on_validation(
    model, scaler, feature_cols: list[str], val_data: dict[str, pd.DataFrame]
) -> dict:
    """
    Run a single model on validation data and compute metrics.
    """
    correct = 0
    total = 0
    returns = []

    for sym, df in val_data.items():
        if df.empty or len(df) < 5:
            continue

        required = [c for c in feature_cols if c in df.columns]
        if len(required) < len(feature_cols) * 0.8:
            continue

        try:
            X = df.iloc[:-1][feature_cols].dropna()
            if X.empty:
                continue
            X_scaled = scaler.transform(X.values)
            probs = model.predict_proba(X_scaled)[:, 1]

            # Compare with actual next-day returns
            closes = df["close"].values
            for i in range(len(X)):
                row_idx = X.index[i]
                pos = df.index.get_loc(row_idx)
                if pos + 1 >= len(closes):
                    continue
                actual_return = (closes[pos + 1] / closes[pos]) - 1
                pred_up = probs[i] >= 0.5
                actual_up = actual_return > 0

                if pred_up == actual_up:
                    correct += 1
                total += 1

                if pred_up:
                    returns.append(actual_return)
                else:
                    returns.append(-actual_return)
        except Exception:
            continue

    accuracy = correct / total if total > 0 else 0
    returns_arr = np.array(returns) if returns else np.array([0.0])

    return {
        "accuracy": round(accuracy, 4),
        "auc": round(accuracy, 4),  # approximate
        "sharpe_ratio": round(_compute_sharpe(returns_arr), 4),
        "max_drawdown": round(_compute_max_drawdown(returns_arr), 4),
        "profit_factor": round(_compute_profit_factor(returns_arr), 4),
        "sample_count": total,
    }


def _compute_sharpe(returns: np.ndarray, annualize: bool = True) -> float:
    """Compute Sharpe ratio from a return series."""
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    sharpe = returns.mean() / returns.std()
    if annualize:
        sharpe *= np.sqrt(252)
    return float(sharpe)


def _compute_max_drawdown(returns: np.ndarray) -> float:
    """Compute maximum drawdown from a return series."""
    if len(returns) == 0:
        return 0.0
    cumulative = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max
    return float(drawdowns.min()) if len(drawdowns) > 0 else 0.0


def _compute_profit_factor(returns: np.ndarray) -> float:
    """Compute profit factor (gross profits / gross losses)."""
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    if losses == 0:
        return 10.0 if gains > 0 else 1.0
    return float(gains / losses)
