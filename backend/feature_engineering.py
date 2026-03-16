"""
Feature Engineering
Computes technical indicators for scanned stocks.
"""
import logging

import numpy as np
import pandas as pd

from backend import config

logger = logging.getLogger(__name__)


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical indicators on a daily OHLCV DataFrame."""
    import ta
    if df.empty or len(df) < 30:
        return df

    df = df.copy().sort_values("date").reset_index(drop=True)

    # ── Moving Averages ──────────────────────────────────────────────────
    for w in config.MA_WINDOWS:
        df[f"sma_{w}"] = df["close"].rolling(w).mean()
        df[f"ema_{w}"] = df["close"].ewm(span=w, adjust=False).mean()

    # ── RSI ──────────────────────────────────────────────────────────────
    df["rsi"] = ta.momentum.RSIIndicator(
        close=df["close"], window=config.RSI_PERIOD
    ).rsi()

    # ── MACD ─────────────────────────────────────────────────────────────
    macd = ta.trend.MACD(
        close=df["close"],
        window_fast=config.MACD_FAST,
        window_slow=config.MACD_SLOW,
        window_sign=config.MACD_SIGNAL,
    )
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_histogram"] = macd.macd_diff()

    # ── Bollinger Bands ──────────────────────────────────────────────────
    bb = ta.volatility.BollingerBands(
        close=df["close"],
        window=config.BOLLINGER_WINDOW,
        window_dev=config.BOLLINGER_STD,
    )
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_middle"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    # ── ATR ──────────────────────────────────────────────────────────────
    df["atr"] = ta.volatility.AverageTrueRange(
        high=df["high"], low=df["low"], close=df["close"], window=14
    ).average_true_range()

    # ── Volume Indicators ────────────────────────────────────────────────
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(
        close=df["close"], volume=df["volume"]
    ).on_balance_volume()

    df["volume_sma_20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"].replace(0, np.nan)

    # ── Returns & Volatility ─────────────────────────────────────────────
    df["daily_return"] = df["close"].pct_change()
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))
    df["volatility"] = df["daily_return"].rolling(config.VOLATILITY_WINDOW).std() * np.sqrt(252)

    # ── Momentum ─────────────────────────────────────────────────────────
    for p in [5, 10, 20]:
        df[f"roc_{p}"] = df["close"].pct_change(periods=p)

    stoch = ta.momentum.StochasticOscillator(
        high=df["high"], low=df["low"], close=df["close"], window=14, smooth_window=3
    )
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    df["williams_r"] = ta.momentum.WilliamsRIndicator(
        high=df["high"], low=df["low"], close=df["close"], lbp=14
    ).williams_r()

    # ── Price Features ───────────────────────────────────────────────────
    for w in config.MA_WINDOWS:
        col = f"sma_{w}"
        if col in df.columns:
            df[f"price_to_sma_{w}"] = df["close"] / df[col]

    df["hl_range"] = (df["high"] - df["low"]) / df["close"]
    df["gap"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)

    # ── Targets ──────────────────────────────────────────────────────────
    df["future_return"] = df["close"].shift(-config.PREDICTION_HORIZON) / df["close"] - 1
    df["direction"] = (df["future_return"] > 0).astype(int)

    return df


def get_feature_columns() -> list[str]:
    """Return the list of ML feature column names."""
    features = []
    for w in config.MA_WINDOWS:
        features += [f"sma_{w}", f"ema_{w}", f"price_to_sma_{w}"]
    features += [
        "rsi", "macd", "macd_signal", "macd_histogram",
        "bb_upper", "bb_middle", "bb_lower", "bb_pct",
        "atr", "obv", "volume_sma_20", "volume_ratio",
        "daily_return", "log_return", "volatility",
        "roc_5", "roc_10", "roc_20",
        "stoch_k", "stoch_d", "williams_r",
        "hl_range", "gap",
    ]
    return features


def compute_momentum_score(df: pd.DataFrame) -> float:
    """Calculate a 0-1 momentum score from the latest row."""
    if df.empty:
        return 0.0

    row = df.iloc[-1]
    score = 0.0
    count = 0

    # RSI momentum (40-70 is positive momentum)
    rsi = row.get("rsi", 50)
    if 40 <= rsi <= 70:
        score += (rsi - 30) / 40
        count += 1
    elif rsi > 70:
        score += 0.5  # overbought, slightly positive
        count += 1

    # MACD above signal
    if row.get("macd", 0) > row.get("macd_signal", 0):
        score += 1.0
        count += 1

    # Price above SMAs
    for w in [20, 50, 200]:
        col = f"price_to_sma_{w}"
        if col in row and not pd.isna(row[col]):
            if row[col] > 1.0:
                score += 1.0
            count += 1

    # Positive ROC
    for p in [5, 10, 20]:
        roc_val = row.get(f"roc_{p}", 0)
        if not pd.isna(roc_val) and roc_val > 0:
            score += 1.0
        count += 1

    return min(score / max(count, 1), 1.0)


def compute_volume_spike_score(df: pd.DataFrame) -> float:
    """Calculate a 0-1 volume spike score."""
    if df.empty or "volume_ratio" not in df.columns:
        return 0.0

    ratio = df["volume_ratio"].iloc[-1]
    if pd.isna(ratio):
        return 0.0

    # volume_ratio > 2 is a spike, > 3 is a big spike
    return min(max((ratio - 1) / 3, 0), 1.0)
