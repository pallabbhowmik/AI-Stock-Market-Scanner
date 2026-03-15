"""
Market Regime Detection
Identifies whether the broad market is in a Bull, Bear, or Sideways regime
using NIFTY50 index data and multiple technical signals.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

NIFTY_SYMBOL = "^NSEI"  # Yahoo Finance symbol for NIFTY 50


def _fetch_index_data(period: str = "1y") -> pd.DataFrame:
    """Fetch NIFTY 50 index data with retry."""
    import time
    try:
        import yfinance as yf
        for attempt in range(1, 4):
            try:
                df = yf.download(NIFTY_SYMBOL, period=period, progress=False, auto_adjust=True)
                if df is not None and not df.empty:
                    df = df.reset_index()
                    df.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower()
                                  for c in df.columns]
                    if "date" not in df.columns and "datetime" in df.columns:
                        df = df.rename(columns={"datetime": "date"})
                    return df
            except Exception as e:
                logger.warning("NIFTY download attempt %d failed: %s", attempt, e)
            if attempt < 3:
                time.sleep(3 * attempt)
        logger.warning("All NIFTY download attempts failed")
        return pd.DataFrame()
    except Exception as e:
        logger.error("Failed to fetch NIFTY data: %s", e)
        return pd.DataFrame()


def detect_regime(df: Optional[pd.DataFrame] = None) -> dict:
    """
    Detect the current market regime using multiple signals.

    Signals used:
    1. Price vs SMA200 — Long-term trend
    2. SMA50 vs SMA200 — Golden/death cross zone
    3. ADX-style trend strength — Trending or range-bound
    4. Slope of SMA50 — Momentum direction
    5. Volatility regime — High/low volatility

    Returns:
        dict with: regime (BULL/BEAR/SIDEWAYS), confidence, signals, description
    """
    if df is None:
        df = _fetch_index_data("1y")

    if df.empty or len(df) < 210:
        logger.warning("Not enough data for regime detection")
        return {
            "regime": "UNKNOWN",
            "confidence": 0.0,
            "description": "Insufficient data for regime detection",
            "signals": {},
        }

    close = df["close"].values.astype(float)

    # 1. SMA calculations
    sma_50 = pd.Series(close).rolling(50).mean().values
    sma_200 = pd.Series(close).rolling(200).mean().values

    current_price = close[-1]
    current_sma50 = sma_50[-1]
    current_sma200 = sma_200[-1]

    # Signal 1: Price vs SMA200
    price_above_200 = current_price > current_sma200

    # Signal 2: SMA50 vs SMA200 (golden / death cross zone)
    golden_cross = current_sma50 > current_sma200

    # Signal 3: Trend strength via directional movement
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1])))
    atr_14 = pd.Series(tr).rolling(14).mean().iloc[-1]
    atr_pct = atr_14 / current_price

    trending = atr_pct > 0.012  # >1.2% ATR signals trending market

    # Signal 4: Slope of SMA50 (momentum direction)
    sma50_slope = (sma_50[-1] - sma_50[-20]) / sma_50[-20] if sma_50[-20] > 0 else 0

    # Signal 5: Recent returns
    return_1m = (close[-1] / close[-22] - 1) if len(close) > 22 else 0
    return_3m = (close[-1] / close[-66] - 1) if len(close) > 66 else 0

    # Volatility
    daily_returns = pd.Series(close).pct_change().dropna()
    volatility_20d = daily_returns.tail(20).std() * np.sqrt(252)
    volatility_60d = daily_returns.tail(60).std() * np.sqrt(252)
    high_volatility = volatility_20d > 0.25  # annualized vol > 25%

    # ─── Regime Classification ───────────────────────────────────────────────
    bull_score = 0
    bear_score = 0
    sideways_score = 0

    # Price above/below SMA200
    if price_above_200:
        bull_score += 2
    else:
        bear_score += 2

    # Golden/Death cross
    if golden_cross:
        bull_score += 2
    else:
        bear_score += 2

    # SMA50 slope
    if sma50_slope > 0.02:
        bull_score += 1.5
    elif sma50_slope < -0.02:
        bear_score += 1.5
    else:
        sideways_score += 1.5

    # Recent returns
    if return_1m > 0.03:
        bull_score += 1
    elif return_1m < -0.03:
        bear_score += 1
    else:
        sideways_score += 1

    if return_3m > 0.08:
        bull_score += 1
    elif return_3m < -0.08:
        bear_score += 1
    else:
        sideways_score += 1

    # Not trending = sideways
    if not trending:
        sideways_score += 2

    # High volatility with no direction = choppy sideways
    if high_volatility and abs(return_1m) < 0.03:
        sideways_score += 1

    total = bull_score + bear_score + sideways_score
    if total == 0:
        total = 1

    scores = {"bull": bull_score, "bear": bear_score, "sideways": sideways_score}
    regime = max(scores, key=scores.get).upper()

    confidence = round(scores[regime.lower()] / total, 4)

    # Description
    descriptions = {
        "BULL": "Market is in an uptrend — NIFTY above key moving averages with positive momentum",
        "BEAR": "Market is in a downtrend — NIFTY below key moving averages with negative momentum",
        "SIDEWAYS": "Market is range-bound — no clear trend direction, choppy price action",
    }

    return {
        "regime": regime,
        "confidence": confidence,
        "description": descriptions.get(regime, ""),
        "signals": {
            "price_above_sma200": price_above_200,
            "golden_cross": golden_cross,
            "trending": trending,
            "sma50_slope": round(sma50_slope * 100, 2),
            "return_1m_pct": round(return_1m * 100, 2),
            "return_3m_pct": round(return_3m * 100, 2),
            "volatility_20d": round(volatility_20d * 100, 2),
            "high_volatility": high_volatility,
            "bull_score": bull_score,
            "bear_score": bear_score,
            "sideways_score": sideways_score,
        },
    }


def get_regime_strategy_bias(regime: str) -> dict:
    """
    Get strategy weight adjustments based on market regime.

    Returns recommended weight biases for different strategy types.
    """
    biases = {
        "BULL": {
            "ml_prediction": 0.0,         # neutral
            "rl_agent": 0.05,             # slight boost
            "momentum_breakout": 0.15,    # strong boost
            "mean_reversion": -0.10,      # reduce
            "volume_breakout": 0.05,      # slight boost
            "sentiment": 0.0,             # neutral
        },
        "BEAR": {
            "ml_prediction": 0.05,
            "rl_agent": 0.05,
            "momentum_breakout": -0.10,
            "mean_reversion": 0.05,
            "volume_breakout": -0.05,
            "sentiment": 0.10,            # sentiment matters more in bear
        },
        "SIDEWAYS": {
            "ml_prediction": 0.0,
            "rl_agent": 0.0,
            "momentum_breakout": -0.10,
            "mean_reversion": 0.15,       # strong boost
            "volume_breakout": 0.0,
            "sentiment": 0.05,
        },
    }

    return biases.get(regime, biases["SIDEWAYS"])
