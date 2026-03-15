"""
News Sentiment Analysis
Extracts sentiment signals from news headlines for Indian market stocks.
Uses a keyword/rule-based approach for zero-dependency analysis.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ─── Sentiment Lexicon (financial terms) ──────────────────────────────────────

POSITIVE_WORDS = {
    "upgrade", "buy", "bullish", "outperform", "growth", "profit", "surge",
    "rally", "breakout", "record", "strong", "beat", "exceeded", "positive",
    "optimistic", "expansion", "boost", "gain", "recovery", "momentum",
    "dividend", "bonus", "acquisition", "partnership", "innovative",
    "approval", "launched", "awarded", "deal", "contract", "order",
    "overweight", "accumulate", "rebound", "uptick", "soar", "jump",
}

NEGATIVE_WORDS = {
    "downgrade", "sell", "bearish", "underperform", "loss", "decline",
    "crash", "plunge", "weak", "miss", "below", "negative", "pessimistic",
    "contraction", "cut", "drop", "fall", "trouble", "risk", "warning",
    "fraud", "default", "bankruptcy", "lawsuit", "penalty", "ban",
    "underweight", "reduce", "slump", "tumble", "sink", "plummet",
    "investigation", "probe", "violation", "debt", "layoff",
}

STRONG_POSITIVE = {"surge", "soar", "record", "breakout", "rally", "beat"}
STRONG_NEGATIVE = {"crash", "plunge", "fraud", "default", "bankruptcy", "ban"}


def _score_text(text: str) -> float:
    """Score a text string for sentiment. Returns -1 to +1."""
    words = set(re.findall(r'\b[a-z]+\b', text.lower()))

    pos_count = len(words & POSITIVE_WORDS)
    neg_count = len(words & NEGATIVE_WORDS)
    strong_pos = len(words & STRONG_POSITIVE)
    strong_neg = len(words & STRONG_NEGATIVE)

    # Strong words count double
    pos_score = pos_count + strong_pos
    neg_score = neg_count + strong_neg

    total = pos_score + neg_score
    if total == 0:
        return 0.0

    return round((pos_score - neg_score) / total, 4)


def analyze_headlines(headlines: list[str]) -> dict:
    """
    Analyze a list of news headlines and return sentiment summary.

    Returns:
        dict with: sentiment_score (-1 to +1), signal (BULLISH/BEARISH/NEUTRAL),
                   positive_count, negative_count, headline_count
    """
    if not headlines:
        return {
            "sentiment_score": 0.0,
            "signal": "NEUTRAL",
            "positive_count": 0,
            "negative_count": 0,
            "headline_count": 0,
        }

    scores = [_score_text(h) for h in headlines]
    avg_score = float(np.mean(scores))

    positive_count = sum(1 for s in scores if s > 0.1)
    negative_count = sum(1 for s in scores if s < -0.1)

    if avg_score > 0.15:
        signal = "BULLISH"
    elif avg_score < -0.15:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    return {
        "sentiment_score": round(avg_score, 4),
        "signal": signal,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "headline_count": len(headlines),
    }


def get_stock_sentiment(symbol: str) -> dict:
    """
    Get sentiment for a stock using yfinance news feed.
    Falls back to neutral if no news available.
    """
    try:
        import yfinance as yf
        import time
        ticker = yf.Ticker(symbol)
        for attempt in range(1, 3):
            try:
                news = ticker.news or []
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2)
                news = []

        headlines = []
        for item in news[:20]:
            title = item.get("title", "")
            if title:
                headlines.append(title)

        result = analyze_headlines(headlines)
        result["symbol"] = symbol
        return result

    except Exception as e:
        logger.debug("Sentiment fetch failed for %s: %s", symbol, e)
        return {
            "symbol": symbol,
            "sentiment_score": 0.0,
            "signal": "NEUTRAL",
            "positive_count": 0,
            "negative_count": 0,
            "headline_count": 0,
        }


def compute_sentiment_score(symbol: str) -> float:
    """
    Compute a normalized sentiment score (0-1 scale) for use in meta-strategy.
    0.5 = neutral, >0.5 = bullish, <0.5 = bearish
    """
    result = get_stock_sentiment(symbol)
    # Map from [-1, +1] to [0, 1]
    return round(0.5 + result["sentiment_score"] * 0.5, 4)


def get_batch_sentiment(symbols: list[str]) -> dict[str, dict]:
    """Get sentiment for multiple symbols."""
    results = {}
    for sym in symbols:
        results[sym] = get_stock_sentiment(sym)
    return results
