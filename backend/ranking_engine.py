"""
Ranking Engine
Computes opportunity scores and ranks stocks for the watchlist.
"""
import logging

import numpy as np
import pandas as pd

from backend import config

logger = logging.getLogger(__name__)


def compute_opportunity_score(
    ai_probability: float,
    momentum_score: float,
    breakout_score: float,
    volume_spike_score: float,
) -> float:
    """
    Calculate the final opportunity score using weighted formula:
    Score = w1*AI + w2*Momentum + w3*Breakout + w4*Volume
    """
    score = (
        config.WEIGHT_AI_PREDICTION * ai_probability
        + config.WEIGHT_MOMENTUM * momentum_score
        + config.WEIGHT_BREAKOUT * breakout_score
        + config.WEIGHT_VOLUME_SPIKE * volume_spike_score
    )
    return round(min(max(score, 0), 1), 4)


def generate_explanation(
    symbol: str,
    signal: str,
    ai_probability: float,
    momentum_score: float,
    breakout_score: float,
    volume_spike_score: float,
    breakout_desc: str = "",
) -> str:
    """Generate a beginner-friendly explanation for the signal."""
    parts = []

    # AI prediction
    if ai_probability >= 0.65:
        parts.append("The AI model predicts a high probability of upward movement")
    elif ai_probability >= 0.55:
        parts.append("The AI model shows a moderate bullish signal")
    elif ai_probability <= 0.35:
        parts.append("The AI model predicts a high probability of downward movement")
    elif ai_probability <= 0.45:
        parts.append("The AI model shows a moderate bearish signal")
    else:
        parts.append("The AI model is neutral on direction")

    # Momentum
    if momentum_score >= 0.7:
        parts.append("strong upward momentum")
    elif momentum_score >= 0.4:
        parts.append("moderate positive momentum")
    elif momentum_score <= 0.2:
        parts.append("weak or negative momentum")

    # Volume
    if volume_spike_score >= 0.5:
        parts.append("with significantly increased trading volume")
    elif volume_spike_score >= 0.2:
        parts.append("with above-average trading volume")

    # Breakout
    if breakout_desc:
        parts.append(breakout_desc.lower())

    if signal == "BUY":
        intro = "This stock shows a buying opportunity."
    elif signal == "SELL":
        intro = "This stock shows selling pressure."
    else:
        intro = "This stock is in a neutral zone."

    explanation = f"{intro} {'. '.join(parts)}."
    # Capitalize start
    return explanation[0].upper() + explanation[1:]


def rank_stocks(predictions: list[dict]) -> dict:
    """
    Rank stocks into categories:
    - Top Buy Opportunities
    - Top Sell Opportunities
    - Top Breakout Stocks
    - High Volume Movers

    Input: list of prediction dicts with keys:
        symbol, signal, confidence, ai_probability, momentum_score,
        breakout_score, volume_spike_score, opportunity_score, explanation
    """
    if not predictions:
        return {"top_buys": [], "top_sells": [], "top_breakouts": [], "volume_movers": []}

    df = pd.DataFrame(predictions)

    # Top Buy Opportunities: highest opportunity score with BUY signal
    buys = df[df["signal"] == "BUY"].nlargest(config.TOP_BUY_COUNT, "opportunity_score")
    top_buys = []
    for rank, (_, row) in enumerate(buys.iterrows(), 1):
        top_buys.append({**row.to_dict(), "rank": rank, "category": "top_buys"})

    # Top Sell Opportunities: highest opportunity score with SELL signal
    sells = df[df["signal"] == "SELL"].nlargest(config.TOP_SELL_COUNT, "opportunity_score")
    top_sells = []
    for rank, (_, row) in enumerate(sells.iterrows(), 1):
        top_sells.append({**row.to_dict(), "rank": rank, "category": "top_sells"})

    # Top Breakout Stocks: highest breakout score
    breakouts = df[df["breakout_score"] > 0].nlargest(config.TOP_BREAKOUT_COUNT, "breakout_score")
    top_breakouts = []
    for rank, (_, row) in enumerate(breakouts.iterrows(), 1):
        top_breakouts.append({**row.to_dict(), "rank": rank, "category": "top_breakouts"})

    # High Volume Movers: highest volume spike score
    vol_movers = df[df["volume_spike_score"] > 0.2].nlargest(config.TOP_VOLUME_MOVERS_COUNT, "volume_spike_score")
    volume_movers = []
    for rank, (_, row) in enumerate(vol_movers.iterrows(), 1):
        volume_movers.append({**row.to_dict(), "rank": rank, "category": "volume_movers"})

    logger.info("Rankings: %d buys, %d sells, %d breakouts, %d vol movers",
                len(top_buys), len(top_sells), len(top_breakouts), len(volume_movers))

    return {
        "top_buys": top_buys,
        "top_sells": top_sells,
        "top_breakouts": top_breakouts,
        "volume_movers": volume_movers,
    }
