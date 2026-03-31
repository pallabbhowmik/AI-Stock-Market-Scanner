"""
Risk Management & Position Sizing
Calculates position sizes, stop losses, and risk metrics for trading recommendations.

Improvements:
- Trailing stop logic: trigger at 1.5×ATR profit, trail at 1×ATR
- Sector correlation check: max 3 positions per sector
- Volatility-scaled position sizing: reduce size in high-vol, increase in low-vol
- Daily loss limit: stop trading if portfolio down > 2% intraday
- Pre-trade validation with comprehensive checks
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

from backend import config

logger = logging.getLogger(__name__)


# ─── Position Sizing ─────────────────────────────────────────────────────────

def calculate_position_size(
    capital: float,
    entry_price: float,
    stop_loss_price: float,
    risk_pct: float = config.RISK_PER_TRADE_PCT,
    max_position_pct: float = config.MAX_POSITION_SIZE_PCT,
    volatility: float = None,
) -> dict:
    """
    Calculate position size using fixed-risk model with volatility scaling.

    If volatility is provided and VOLATILITY_SCALING is enabled, position
    size is reduced when volatility is high and increased when it's low.
    """
    risk_amount = capital * risk_pct
    risk_per_share = abs(entry_price - stop_loss_price)

    if risk_per_share <= 0:
        risk_per_share = entry_price * 0.03  # default 3% stop

    shares = int(risk_amount / risk_per_share)

    # Volatility scaling: adjust position size inversely with volatility
    if volatility and config.VOLATILITY_SCALING and volatility > 0:
        vol_scale = config.VOLATILITY_SCALE_BASE / volatility
        vol_scale = max(0.3, min(vol_scale, 2.0))  # Clamp between 0.3x and 2x
        shares = int(shares * vol_scale)
        logger.debug("Volatility scaling: vol=%.4f, scale=%.2f", volatility, vol_scale)

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


# ─── Stop Loss Calculation ──────────────────────────────────────────────────

def calculate_stop_loss(df: pd.DataFrame, method: str = "atr") -> dict:
    """Calculate stop loss levels using ATR, support, or percentage methods."""
    if df.empty or len(df) < 20:
        price = df["close"].iloc[-1] if not df.empty else 0
        return {"stop_loss": round(price * 0.97, 2), "method": "default_3pct", "risk_pct": 3.0}

    price = float(df["close"].iloc[-1])

    if method == "atr":
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        close = df["close"].values.astype(float)
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - close[:-1]),
                       np.abs(low[1:] - close[:-1]))
        )
        atr = float(np.mean(tr[-14:]))
        stop = price - 2.0 * atr
        risk_pct = ((price - stop) / price) * 100

    elif method == "support":
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
    risk_reward_ratio: float = config.RISK_REWARD_RATIO,
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


# ─── Trailing Stop Logic ────────────────────────────────────────────────────

def compute_trailing_stop(
    entry_price: float,
    current_price: float,
    current_stop: float,
    atr: float,
    trigger_atr_mult: float = config.TRAILING_STOP_TRIGGER_ATR,
    trail_atr_mult: float = config.TRAILING_STOP_DISTANCE_ATR,
) -> dict:
    """
    Compute trailing stop for a long position.

    Logic: Once price moves trigger_atr_mult × ATR above entry, start trailing
    the stop at trail_atr_mult × ATR below the highest price seen.

    Returns:
        dict with: new_stop, triggered, profit_atr (how many ATRs in profit)
    """
    if atr <= 0:
        return {"new_stop": current_stop, "triggered": False, "profit_atr": 0}

    profit = current_price - entry_price
    profit_atr = profit / atr

    trail_stop = current_price - trail_atr_mult * atr

    if profit_atr >= trigger_atr_mult:
        # Trailing stop is active: only ratchet upward
        new_stop = max(current_stop, trail_stop)
        return {
            "new_stop": round(new_stop, 2),
            "triggered": True,
            "profit_atr": round(profit_atr, 2),
        }

    return {
        "new_stop": current_stop,
        "triggered": False,
        "profit_atr": round(profit_atr, 2),
    }


# ─── Pre-Trade Validation ───────────────────────────────────────────────────

def validate_trade(
    symbol: str,
    signal: str,
    current_positions: list[dict],
    daily_pnl_pct: float = 0.0,
    capital: float = config.DEFAULT_CAPITAL,
) -> dict:
    """
    Validate whether a new trade should be allowed.

    Checks:
    1. Max positions limit
    2. Sector concentration
    3. Daily loss limit
    4. Duplicate position
    """
    reasons = []
    allowed = True

    # Check 1: Max positions
    if len(current_positions) >= config.MAX_POSITIONS:
        allowed = False
        reasons.append(f"Max positions ({config.MAX_POSITIONS}) reached")

    # Check 2: Daily loss limit
    if abs(daily_pnl_pct) > config.MAX_DAILY_LOSS_PCT and daily_pnl_pct < 0:
        allowed = False
        reasons.append(f"Daily loss limit ({config.MAX_DAILY_LOSS_PCT:.0%}) exceeded: {daily_pnl_pct:.2%}")

    # Check 3: Duplicate position
    held_symbols = [p.get("symbol", "") for p in current_positions]
    if symbol in held_symbols:
        allowed = False
        reasons.append(f"Already holding {symbol}")

    # Check 4: Sector concentration
    # (Requires sector info in positions — skip if not available)
    sector_counts = {}
    for p in current_positions:
        sector = p.get("sector", "Unknown")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    # We don't know the new symbol's sector here, but we can
    # flag if any sector is already at max
    for sector, count in sector_counts.items():
        if count >= config.MAX_SECTOR_POSITIONS:
            reasons.append(f"Sector '{sector}' already at max ({config.MAX_SECTOR_POSITIONS} positions)")

    return {
        "allowed": allowed,
        "reasons": reasons,
        "checks_passed": len(reasons) == 0,
    }


# ─── Portfolio Risk ──────────────────────────────────────────────────────────

def compute_portfolio_risk(positions: list[dict]) -> dict:
    """
    Compute aggregate portfolio risk metrics.
    Each position dict should have: symbol, shares, entry_price, stop_loss, sector
    """
    if not positions:
        return {"total_exposure": 0, "total_risk": 0, "position_count": 0, "diversification_score": 1.0}

    total_value = sum(p.get("shares", 0) * p.get("entry_price", 0) for p in positions)
    total_risk = sum(p.get("shares", 0) * abs(p.get("entry_price", 0) - p.get("stop_loss", 0))
                     for p in positions)

    # Sector concentration
    sector_exposure = {}
    for p in positions:
        sector = p.get("sector", "Unknown")
        val = p.get("shares", 0) * p.get("entry_price", 0)
        sector_exposure[sector] = sector_exposure.get(sector, 0) + val

    max_sector_pct = max(sector_exposure.values()) / total_value if total_value > 0 else 0

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


# ─── Complete Risk Recommendation ───────────────────────────────────────────

def generate_risk_recommendation(
    symbol: str,
    last_price: float,
    df: pd.DataFrame,
    signal: str = "HOLD",
    confidence: float = 0.5,
    capital: float = config.DEFAULT_CAPITAL,
) -> dict:
    """
    Generate a complete risk management recommendation for a stock.
    Includes trailing stop info, volatility-adjusted sizing, and validation.
    """
    if df.empty:
        return {"error": "No data available"}

    price = float(last_price) if last_price > 0 else float(df["close"].iloc[-1])

    # Get current volatility for scaling
    volatility = None
    if "volatility" in df.columns:
        vol_val = df["volatility"].iloc[-1]
        if not pd.isna(vol_val):
            volatility = float(vol_val)
    if volatility is None:
        returns = df["close"].pct_change().dropna()
        if len(returns) >= 10:
            volatility = float(returns.tail(20).std() * np.sqrt(252))

    # Risk scales with confidence
    risk_pct = config.RISK_PER_TRADE_PCT * min(confidence + 0.5, 1.0)

    stop = calculate_stop_loss(df, method=config.STOP_LOSS_METHOD)
    tp = calculate_take_profit(price, stop["stop_loss"])
    pos = calculate_position_size(
        capital, price, stop["stop_loss"],
        risk_pct=risk_pct, volatility=volatility,
    )

    # ATR for trailing stop info
    atr = None
    if "atr" in df.columns:
        atr_val = df["atr"].iloc[-1]
        if not pd.isna(atr_val):
            atr = float(atr_val)

    result = {
        "symbol": symbol,
        "signal": signal,
        "entry_price": round(price, 2),
        "stop_loss": stop["stop_loss"],
        "take_profit": tp["take_profit"],
        "risk_reward_ratio": tp["risk_reward_ratio"],
        "shares": pos["shares"],
        "position_value": pos["position_value"],
        "risk_amount": pos["risk_amount"],
        "position_pct": pos["position_pct"],
        "volatility": round(volatility, 4) if volatility else None,
    }

    if atr:
        result["trailing_stop_trigger"] = round(price + atr * config.TRAILING_STOP_TRIGGER_ATR, 2)
        result["trailing_stop_info"] = (
            f"Once price moves ₹{atr * config.TRAILING_STOP_TRIGGER_ATR:.0f} in profit, "
            f"trail stop at ₹{atr * config.TRAILING_STOP_DISTANCE_ATR:.0f} below high"
        )

    return result
