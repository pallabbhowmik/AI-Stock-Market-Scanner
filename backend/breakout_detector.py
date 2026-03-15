"""
Breakout Detector
Detects resistance breakouts, volume breakouts, MA crossovers, and momentum spikes.
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def detect_resistance_breakout(df: pd.DataFrame, lookback: int = 60) -> dict:
    """
    Detect if price broke above recent resistance (highest high in lookback).
    Returns {detected: bool, strength: 0-1, description}.
    """
    if len(df) < lookback + 1:
        return {"detected": False, "strength": 0, "description": ""}

    recent_high = df["high"].iloc[-(lookback + 1):-1].max()
    current_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-2]

    if current_close > recent_high and prev_close <= recent_high:
        pct_above = (current_close - recent_high) / recent_high
        strength = min(pct_above / 0.03, 1.0)  # 3% above = full strength
        return {
            "detected": True,
            "strength": round(strength, 4),
            "description": f"Price broke above {lookback}-day resistance at ₹{recent_high:.2f}",
        }

    return {"detected": False, "strength": 0, "description": ""}


def detect_volume_breakout(df: pd.DataFrame, threshold: float = 2.0) -> dict:
    """
    Detect if current volume is significantly above average.
    threshold=2.0 means 2x average volume.
    """
    if len(df) < 21 or "volume_ratio" not in df.columns:
        if len(df) < 21:
            return {"detected": False, "strength": 0, "description": ""}
        vol_avg = df["volume"].tail(20).mean()
        if vol_avg == 0:
            return {"detected": False, "strength": 0, "description": ""}
        ratio = df["volume"].iloc[-1] / vol_avg
    else:
        ratio = df["volume_ratio"].iloc[-1]

    if pd.isna(ratio):
        return {"detected": False, "strength": 0, "description": ""}

    if ratio >= threshold:
        strength = min((ratio - 1) / 4, 1.0)
        return {
            "detected": True,
            "strength": round(strength, 4),
            "description": f"Volume is {ratio:.1f}x the 20-day average",
        }

    return {"detected": False, "strength": 0, "description": ""}


def detect_ma_crossover(df: pd.DataFrame) -> dict:
    """
    Detect moving average crossovers:
    - Golden Cross: 50 SMA crosses above 200 SMA
    - Short-term: 20 EMA crosses above 50 SMA
    """
    results = {"detected": False, "strength": 0, "description": "", "type": ""}

    if len(df) < 201:
        return results

    sma_20 = df["close"].rolling(20).mean()
    sma_50 = df["close"].rolling(50).mean()
    sma_200 = df["close"].rolling(200).mean()

    # Golden cross (50 above 200)
    if (sma_50.iloc[-1] > sma_200.iloc[-1] and sma_50.iloc[-2] <= sma_200.iloc[-2]):
        return {
            "detected": True,
            "strength": 1.0,
            "description": "Golden Cross: 50-day SMA crossed above 200-day SMA",
            "type": "golden_cross",
        }

    # Short-term bullish crossover
    if (sma_20.iloc[-1] > sma_50.iloc[-1] and sma_20.iloc[-2] <= sma_50.iloc[-2]):
        return {
            "detected": True,
            "strength": 0.7,
            "description": "Short-term bullish crossover: 20-day crossed above 50-day",
            "type": "short_cross",
        }

    # Death cross (50 below 200)
    if (sma_50.iloc[-1] < sma_200.iloc[-1] and sma_50.iloc[-2] >= sma_200.iloc[-2]):
        return {
            "detected": True,
            "strength": 0.9,
            "description": "Death Cross: 50-day SMA crossed below 200-day SMA (bearish)",
            "type": "death_cross",
        }

    return results


def detect_momentum_spike(df: pd.DataFrame) -> dict:
    """Detect sudden momentum changes using RSI and rate of change."""
    if len(df) < 20:
        return {"detected": False, "strength": 0, "description": ""}

    rsi = df.get("rsi", pd.Series(dtype=float))
    roc_5 = df.get("roc_5", pd.Series(dtype=float))

    if rsi.empty or roc_5.empty:
        return {"detected": False, "strength": 0, "description": ""}

    current_rsi = rsi.iloc[-1]
    prev_rsi = rsi.iloc[-2]
    current_roc = roc_5.iloc[-1]

    # Strong momentum spike: RSI jumping + positive ROC
    if not pd.isna(current_rsi) and not pd.isna(prev_rsi) and not pd.isna(current_roc):
        rsi_jump = current_rsi - prev_rsi
        if rsi_jump > 10 and current_roc > 0.03:
            strength = min(rsi_jump / 20, 1.0)
            return {
                "detected": True,
                "strength": round(strength, 4),
                "description": f"Momentum spike: RSI jumped {rsi_jump:.1f} points, 5-day ROC = {current_roc:.1%}",
            }

    return {"detected": False, "strength": 0, "description": ""}


def detect_all_breakouts(df: pd.DataFrame) -> dict:
    """
    Run all breakout detectors and compute an overall breakout score.
    Returns {score: 0-1, breakouts: list, description}.
    """
    detectors = [
        ("Resistance Breakout", detect_resistance_breakout(df)),
        ("Volume Breakout", detect_volume_breakout(df)),
        ("MA Crossover", detect_ma_crossover(df)),
        ("Momentum Spike", detect_momentum_spike(df)),
    ]

    active = []
    total_strength = 0

    for name, result in detectors:
        if result["detected"]:
            active.append({
                "type": name,
                "strength": result["strength"],
                "description": result["description"],
            })
            total_strength += result["strength"]

    # Normalize score to 0-1
    score = min(total_strength / len(detectors), 1.0)

    # Combined description
    descriptions = [b["description"] for b in active]
    combined_desc = "; ".join(descriptions) if descriptions else "No breakout detected"

    return {
        "score": round(score, 4),
        "breakouts": active,
        "description": combined_desc,
        "count": len(active),
    }
