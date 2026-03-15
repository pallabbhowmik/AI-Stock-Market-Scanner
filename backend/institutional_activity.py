"""
Institutional Activity Detection
Detects signs of institutional buying/selling through volume and price patterns.
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def detect_bulk_deals(df: pd.DataFrame) -> dict:
    """
    Detect bulk deal patterns:
    Volume exceeds 3x the 20-day average with significant price movement.
    """
    if len(df) < 25:
        return {"detected": False, "score": 0.0, "type": "none"}

    avg_vol = df["volume"].rolling(20).mean().iloc[-1]
    latest_vol = df["volume"].iloc[-1]
    price_change = (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) if len(df) > 1 else 0

    ratio = latest_vol / avg_vol if avg_vol > 0 else 0

    if ratio >= 3.0:
        deal_type = "institutional_buy" if price_change > 0 else "institutional_sell"
        score = min(ratio / 5.0, 1.0)
        return {"detected": True, "score": round(score, 4), "type": deal_type, "volume_ratio": round(ratio, 2)}

    return {"detected": False, "score": 0.0, "type": "none", "volume_ratio": round(ratio, 2)}


def detect_accumulation(df: pd.DataFrame, window: int = 20) -> dict:
    """
    Detect accumulation pattern:
    Price relatively stable while volume is consistently above average.
    Suggests institutions are quietly building positions.
    """
    if len(df) < window + 5:
        return {"detected": False, "score": 0.0}

    recent = df.tail(window)
    prior = df.iloc[-(window * 2):-window] if len(df) >= window * 2 else df.head(window)

    # Price stability (low volatility)
    price_range = (recent["high"].max() - recent["low"].min()) / recent["close"].mean()

    # Volume trend (increasing)
    avg_vol_recent = recent["volume"].mean()
    avg_vol_prior = prior["volume"].mean()
    vol_ratio = avg_vol_recent / avg_vol_prior if avg_vol_prior > 0 else 1.0

    is_accumulating = price_range < 0.10 and vol_ratio > 1.2

    score = 0.0
    if is_accumulating:
        score = min((vol_ratio - 1.0) * 2.0, 1.0) * (1.0 - price_range * 5)
        score = max(score, 0.0)

    return {
        "detected": is_accumulating,
        "score": round(score, 4),
        "price_range_pct": round(price_range * 100, 2),
        "volume_increase_pct": round((vol_ratio - 1) * 100, 2),
    }


def detect_distribution(df: pd.DataFrame, window: int = 20) -> dict:
    """
    Detect distribution pattern:
    Price near highs but volume declining — suggests smart money selling to retail.
    """
    if len(df) < window + 5:
        return {"detected": False, "score": 0.0}

    recent = df.tail(window)

    # Price near recent highs
    price_near_high = recent["close"].iloc[-1] / recent["high"].max()

    # Declining volume
    first_half_vol = recent["volume"].iloc[:window // 2].mean()
    second_half_vol = recent["volume"].iloc[window // 2:].mean()
    vol_declining = second_half_vol < first_half_vol * 0.85

    # Check for down days on high volume
    daily_returns = recent["close"].pct_change()
    down_vol = recent.loc[daily_returns < 0, "volume"].mean()
    up_vol = recent.loc[daily_returns > 0, "volume"].mean()
    down_heavy = (down_vol / up_vol) > 1.3 if up_vol > 0 else False

    is_distributing = price_near_high > 0.95 and (vol_declining or down_heavy)

    score = 0.0
    if is_distributing:
        score = 0.5
        if vol_declining:
            score += 0.25
        if down_heavy:
            score += 0.25

    return {
        "detected": is_distributing,
        "score": round(score, 4),
        "price_to_high_pct": round(price_near_high * 100, 2),
        "volume_declining": vol_declining,
        "heavy_selling": down_heavy,
    }


def detect_smart_money_flow(df: pd.DataFrame) -> dict:
    """
    Smart money flow indicator:
    Compare first half-hour vs last half-hour price action (daily proxy).
    Smart money tends to act at close, retail at open.
    Using daily data: gap up but close weak = distribution, gap down but close strong = accumulation.
    """
    if len(df) < 10:
        return {"flow": "neutral", "score": 0.5}

    recent = df.tail(10)

    # Gap direction vs close direction
    accumulation_days = 0
    distribution_days = 0

    for i in range(1, len(recent)):
        gap = recent["open"].iloc[i] - recent["close"].iloc[i - 1]
        body = recent["close"].iloc[i] - recent["open"].iloc[i]

        if gap < 0 and body > 0:
            accumulation_days += 1
        elif gap > 0 and body < 0:
            distribution_days += 1

    if accumulation_days > distribution_days + 2:
        return {"flow": "accumulation", "score": round(0.5 + accumulation_days * 0.05, 4)}
    elif distribution_days > accumulation_days + 2:
        return {"flow": "distribution", "score": round(0.5 - distribution_days * 0.05, 4)}

    return {"flow": "neutral", "score": 0.5}


def detect_institutional_activity(df: pd.DataFrame) -> dict:
    """
    Run all institutional activity detectors and return a composite score.

    Returns:
        dict with: institutional_score (0-1), activity_type, details
    """
    bulk = detect_bulk_deals(df)
    accum = detect_accumulation(df)
    distro = detect_distribution(df)
    smart = detect_smart_money_flow(df)

    # Composite score: higher = more bullish institutional activity
    # Accumulation and bulk buys are positive, distribution is negative
    score = 0.5  # neutral baseline

    if bulk["detected"]:
        if bulk["type"] == "institutional_buy":
            score += bulk["score"] * 0.3
        else:
            score -= bulk["score"] * 0.3

    if accum["detected"]:
        score += accum["score"] * 0.25

    if distro["detected"]:
        score -= distro["score"] * 0.25

    # Smart money flow adjusts by up to ±0.15
    score += (smart["score"] - 0.5) * 0.3

    score = round(min(max(score, 0), 1), 4)

    # Determine activity type
    if score >= 0.65:
        activity_type = "institutional_buying"
    elif score <= 0.35:
        activity_type = "institutional_selling"
    else:
        activity_type = "neutral"

    description_parts = []
    if bulk["detected"]:
        description_parts.append(f"Bulk deal ({bulk['type']})")
    if accum["detected"]:
        description_parts.append("Accumulation pattern")
    if distro["detected"]:
        description_parts.append("Distribution pattern")
    if smart["flow"] != "neutral":
        description_parts.append(f"Smart money: {smart['flow']}")

    return {
        "institutional_score": score,
        "activity_type": activity_type,
        "description": "; ".join(description_parts) if description_parts else "No significant institutional activity",
        "bulk_deal": bulk,
        "accumulation": accum,
        "distribution": distro,
        "smart_money": smart,
    }
