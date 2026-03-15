"""
Portfolio Optimizer
Optimizes portfolio allocation across selected stocks using mean-variance optimization
and risk-parity approaches.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_CAPITAL = 1_000_000
MAX_WEIGHT = 0.15  # Max 15% in a single stock
MIN_WEIGHT = 0.02  # Min 2% to be included


def _compute_returns(prices_dict: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build a DataFrame of daily returns from multiple stock DataFrames."""
    close_prices = {}
    for sym, df in prices_dict.items():
        if not df.empty and "close" in df.columns and len(df) > 30:
            series = df.set_index("date")["close"] if "date" in df.columns else df["close"]
            close_prices[sym] = series

    if not close_prices:
        return pd.DataFrame()

    combined = pd.DataFrame(close_prices)
    combined = combined.dropna(axis=1, thresh=int(len(combined) * 0.7))
    returns = combined.pct_change().dropna()
    return returns


def equal_weight_allocation(symbols: list[str], capital: float = DEFAULT_CAPITAL) -> dict:
    """Simple equal-weight allocation across all symbols."""
    if not symbols:
        return {"allocations": {}, "method": "equal_weight"}

    n = len(symbols)
    weight = 1.0 / n
    allocations = {sym: round(weight, 4) for sym in symbols}

    return {
        "allocations": allocations,
        "method": "equal_weight",
        "capital": capital,
        "per_stock": round(capital / n, 2),
    }


def score_weighted_allocation(
    predictions: list[dict],
    capital: float = DEFAULT_CAPITAL,
) -> dict:
    """
    Allocate capital based on opportunity scores.
    Higher-scoring stocks get proportionally more capital.
    """
    buy_preds = [p for p in predictions if p.get("signal") == "BUY" and p.get("opportunity_score", 0) > 0]

    if not buy_preds:
        return {"allocations": {}, "method": "score_weighted"}

    total_score = sum(p["opportunity_score"] for p in buy_preds)
    if total_score <= 0:
        return equal_weight_allocation([p["symbol"] for p in buy_preds], capital)

    allocations = {}
    for p in buy_preds:
        raw_weight = p["opportunity_score"] / total_score
        weight = min(max(raw_weight, MIN_WEIGHT), MAX_WEIGHT)
        allocations[p["symbol"]] = round(weight, 4)

    # Renormalize so weights sum to 1
    total_w = sum(allocations.values())
    if total_w > 0:
        allocations = {k: round(v / total_w, 4) for k, v in allocations.items()}

    return {
        "allocations": allocations,
        "method": "score_weighted",
        "capital": capital,
    }


def risk_parity_allocation(
    prices_dict: dict[str, pd.DataFrame],
    capital: float = DEFAULT_CAPITAL,
) -> dict:
    """
    Risk-parity allocation: each stock contributes equal risk to the portfolio.
    Stocks with lower volatility get higher allocations.
    """
    returns = _compute_returns(prices_dict)
    if returns.empty or returns.shape[1] < 2:
        symbols = list(prices_dict.keys())
        return equal_weight_allocation(symbols, capital)

    # Inverse-volatility weighting (simplified risk parity)
    vols = returns.std()
    if (vols == 0).any():
        vols = vols.replace(0, vols.mean())

    inv_vol = 1.0 / vols
    weights = inv_vol / inv_vol.sum()

    # Apply caps
    weights = weights.clip(lower=MIN_WEIGHT, upper=MAX_WEIGHT)
    weights = weights / weights.sum()

    allocations = {sym: round(w, 4) for sym, w in weights.items()}

    return {
        "allocations": allocations,
        "method": "risk_parity",
        "capital": capital,
        "volatilities": {sym: round(v * np.sqrt(252) * 100, 2) for sym, v in vols.items()},
    }


def mean_variance_optimization(
    prices_dict: dict[str, pd.DataFrame],
    capital: float = DEFAULT_CAPITAL,
    target: str = "sharpe",
) -> dict:
    """
    Mean-variance portfolio optimization.
    Maximizes Sharpe ratio (or minimizes variance) using analytical approach.
    """
    returns = _compute_returns(prices_dict)
    if returns.empty or returns.shape[1] < 2:
        symbols = list(prices_dict.keys())
        return equal_weight_allocation(symbols, capital)

    n = returns.shape[1]
    mean_ret = returns.mean().values * 252  # annualized
    cov = returns.cov().values * 252

    # Add small regularization for numerical stability
    cov += np.eye(n) * 1e-6

    try:
        cov_inv = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        symbols = list(returns.columns)
        return equal_weight_allocation(symbols, capital)

    if target == "sharpe":
        # Max Sharpe: w = cov_inv @ mean_ret (tangency portfolio)
        raw_weights = cov_inv @ mean_ret
    else:
        # Min variance: w = cov_inv @ ones
        raw_weights = cov_inv @ np.ones(n)

    # Handle negative weights by taking absolute values (long-only constraint)
    raw_weights = np.abs(raw_weights)
    total = raw_weights.sum()
    if total <= 0:
        raw_weights = np.ones(n) / n
    else:
        raw_weights = raw_weights / total

    # Apply caps
    raw_weights = np.clip(raw_weights, MIN_WEIGHT, MAX_WEIGHT)
    raw_weights = raw_weights / raw_weights.sum()

    symbols = list(returns.columns)
    allocations = {sym: round(w, 4) for sym, w in zip(symbols, raw_weights)}

    # Compute portfolio stats
    port_return = float(raw_weights @ mean_ret)
    port_vol = float(np.sqrt(raw_weights @ cov @ raw_weights))
    sharpe = port_return / port_vol if port_vol > 0 else 0

    return {
        "allocations": allocations,
        "method": f"mean_variance_{target}",
        "capital": capital,
        "expected_annual_return_pct": round(port_return * 100, 2),
        "expected_annual_vol_pct": round(port_vol * 100, 2),
        "sharpe_ratio": round(sharpe, 4),
    }


def optimize_portfolio(
    predictions: list[dict],
    prices_dict: dict[str, pd.DataFrame],
    method: str = "score_weighted",
    capital: float = DEFAULT_CAPITAL,
) -> dict:
    """
    Main entry point: optimize portfolio allocation.

    Methods: equal_weight, score_weighted, risk_parity, mean_variance
    """
    buy_preds = [p for p in predictions if p.get("signal") == "BUY"]
    buy_symbols = [p["symbol"] for p in buy_preds]
    buy_prices = {sym: df for sym, df in prices_dict.items() if sym in buy_symbols}

    if method == "equal_weight":
        return equal_weight_allocation(buy_symbols, capital)
    elif method == "score_weighted":
        return score_weighted_allocation(buy_preds, capital)
    elif method == "risk_parity":
        return risk_parity_allocation(buy_prices, capital)
    elif method == "mean_variance":
        return mean_variance_optimization(buy_prices, capital)
    else:
        return score_weighted_allocation(buy_preds, capital)
