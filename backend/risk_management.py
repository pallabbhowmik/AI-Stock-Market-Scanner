"""
Risk Management & Position Sizing
Calculates position sizes, stop losses, and risk metrics for trading recommendations.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Default Parameters ──────────────────────────────────────────────────────
DEFAULT_CAPITAL = 1_000_000       # ₹10 lakh
DEFAULT_RISK_PER_TRADE = 0.02    # 2% of capital per trade
DEFAULT_MAX_POSITIONS = 10
DEFAULT_MAX_SECTOR_EXPOSURE = 0.30  # 30% max in one sector


def calculate_position_size(
    capital: float,
    entry_price: float,
    stop_loss_price: float,
    risk_pct: float = DEFAULT_RISK_PER_TRADE,
    max_position_pct: float = 0.10,
) -> dict:
    """
    Calculate position size using fixed-risk model.

    Args:
        capital: Total portfolio capital
        entry_price: Stock entry price
        stop_loss_price: Stop loss price
        risk_pct: Max risk per trade as fraction of capital
        max_position_pct: Max size of a single position as fraction of capital

    Returns:
        dict with: shares, position_value, risk_amount, risk_reward_info
    """
    risk_amount = capital * risk_pct
    risk_per_share = abs(entry_price - stop_loss_price)

    if risk_per_share <= 0:
        risk_per_share = entry_price * 0.03  # default 3% stop

    shares = int(risk_amount / risk_per_share)

    # Cap by max position size
    max_shares = int((capital * max_position_pct) / entry_price)
    shares = min(shares, max_shares)
    shares = max(shares, 0)

    position_value = shares * entry_price

    return {
        "shares": shares,
        "position_value": round(position_value, 2),
        "risk_amount": round(risk_amount, 2),
        "risk_per_share": round(risk_per_share, 2),
        "position_pct": round(position_value / capital * 100, 2) if capital > 0 else 0,
    }


def calculate_stop_loss(df: pd.DataFrame, method: str = "atr") -> dict:
    """
    Calculate stop loss levels using different methods.

    Methods: atr, percentage, support
    """
    if df.empty or len(df) < 20:
        price = df["close"].iloc[-1] if not df.empty else 0
        return {"stop_loss": round(price * 0.97, 2), "method": "default_3pct", "risk_pct": 3.0}

    price = df["close"].iloc[-1]

    if method == "atr":
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - close[:-1]),
                       np.abs(low[1:] - close[:-1]))
        )
        atr = float(np.mean(tr[-14:]))
        stop = price - 2.0 * atr  # 2x ATR trailing stop
        risk_pct = ((price - stop) / price) * 100

    elif method == "support":
        # Recent swing low
        lows = df["low"].tail(20).values
        stop = float(np.min(lows))
        risk_pct = ((price - stop) / price) * 100

    else:  # percentage
        stop = price * 0.97
        risk_pct = 3.0

    return {
        "stop_loss": round(stop, 2),
        "method": method,
        "risk_pct": round(risk_pct, 2),
        "entry_price": round(price, 2),
    }


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    risk_reward_ratio: float = 2.0,
) -> dict:
    """Calculate take-profit level based on risk-reward ratio."""
    risk = abs(entry_price - stop_loss)
    target = entry_price + risk * risk_reward_ratio

    return {
        "take_profit": round(target, 2),
        "risk": round(risk, 2),
        "reward": round(risk * risk_reward_ratio, 2),
        "risk_reward_ratio": risk_reward_ratio,
    }


def compute_portfolio_risk(positions: list[dict]) -> dict:
    """
    Compute aggregate portfolio risk metrics.

    Each position dict should have: symbol, shares, entry_price, stop_loss, sector
    """
    if not positions:
        return {"total_exposure": 0, "total_risk": 0, "position_count": 0, "diversification_score": 1.0}

    total_value = sum(p["shares"] * p["entry_price"] for p in positions)
    total_risk = sum(p["shares"] * abs(p["entry_price"] - p["stop_loss"]) for p in positions)

    # Sector concentration
    sector_exposure = {}
    for p in positions:
        sector = p.get("sector", "Unknown")
        val = p["shares"] * p["entry_price"]
        sector_exposure[sector] = sector_exposure.get(sector, 0) + val

    max_sector_pct = max(sector_exposure.values()) / total_value if total_value > 0 else 0

    # Diversification score: 1.0 = perfectly diversified, 0 = concentrated
    n_sectors = len(sector_exposure)
    diversification = min(n_sectors / 5.0, 1.0) * (1.0 - max_sector_pct + 0.2)
    diversification = round(min(max(diversification, 0), 1), 4)

    return {
        "total_exposure": round(total_value, 2),
        "total_risk": round(total_risk, 2),
        "risk_pct": round((total_risk / total_value * 100) if total_value > 0 else 0, 2),
        "position_count": len(positions),
        "sector_exposure": {k: round(v / total_value * 100, 2) for k, v in sector_exposure.items()},
        "max_sector_pct": round(max_sector_pct * 100, 2),
        "diversification_score": diversification,
    }


def generate_risk_recommendation(
    df: pd.DataFrame,
    signal: str,
    confidence: float,
    capital: float = DEFAULT_CAPITAL,
) -> dict:
    """
    Generate a complete risk management recommendation for a stock.
    """
    if df.empty:
        return {"error": "No data available"}

    price = float(df["close"].iloc[-1])

    # Position sizing scales with confidence
    risk_pct = DEFAULT_RISK_PER_TRADE * min(confidence + 0.5, 1.0)

    stop = calculate_stop_loss(df, method="atr")
    tp = calculate_take_profit(price, stop["stop_loss"])
    pos = calculate_position_size(capital, price, stop["stop_loss"], risk_pct=risk_pct)

    return {
        "signal": signal,
        "entry_price": round(price, 2),
        "stop_loss": stop["stop_loss"],
        "take_profit": tp["take_profit"],
        "risk_reward_ratio": tp["risk_reward_ratio"],
        "shares": pos["shares"],
        "position_value": pos["position_value"],
        "risk_amount": pos["risk_amount"],
        "position_pct": pos["position_pct"],
    }
