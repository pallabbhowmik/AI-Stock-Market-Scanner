"""
Feature Engineering
Computes technical indicators for scanned stocks.

Improvements:
- Added Supertrend indicator (highly effective for Indian market)
- Added ADX (trend strength) to prevent trading in trendless conditions
- Added Keltner Channels for squeeze detection
- Added 3-day forward return as alternative target
- Added VWAP deviation bands
- Better momentum score with ADX integration
"""
import logging

import numpy as np
import pandas as pd

from backend import config

logger = logging.getLogger(__name__)


def _compute_supertrend(df: pd.DataFrame, period: int = 10,
                        multiplier: float = 3.0) -> pd.DataFrame:
    """
    Compute Supertrend indicator — extremely popular and effective
    for trend-following in Indian markets (used by most intraday traders).
    Returns the DataFrame with 'supertrend' and 'supertrend_dir' columns.
    """
    hl2 = (df["high"] + df["low"]) / 2
    atr = df["atr"] if "atr" in df.columns else (
        pd.Series(np.maximum(
            df["high"] - df["low"],
            np.maximum(
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"] - df["close"].shift(1))
            )
        )).rolling(period).mean()
    )

    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(np.nan, index=df.index)
    direction = pd.Series(1, index=df.index)  # 1 = up, -1 = down

    for i in range(1, len(df)):
        if df["close"].iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        if direction.iloc[i] == 1:
            lower_band.iloc[i] = max(lower_band.iloc[i],
                                      lower_band.iloc[i - 1]) if direction.iloc[i - 1] == 1 else lower_band.iloc[i]
            supertrend.iloc[i] = lower_band.iloc[i]
        else:
            upper_band.iloc[i] = min(upper_band.iloc[i],
                                      upper_band.iloc[i - 1]) if direction.iloc[i - 1] == -1 else upper_band.iloc[i]
            supertrend.iloc[i] = upper_band.iloc[i]

    df["supertrend"] = supertrend
    df["supertrend_dir"] = direction
    return df


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
    df["bb_bandwidth"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

    # ── ATR ──────────────────────────────────────────────────────────────
    df["atr"] = ta.volatility.AverageTrueRange(
        high=df["high"], low=df["low"], close=df["close"], window=14
    ).average_true_range()

    # ── ADX (Average Directional Index) — trend strength ─────────────────
    try:
        adx_indicator = ta.trend.ADXIndicator(
            high=df["high"], low=df["low"], close=df["close"], window=14
        )
        df["adx"] = adx_indicator.adx()
        df["adx_pos"] = adx_indicator.adx_pos()
        df["adx_neg"] = adx_indicator.adx_neg()
    except Exception:
        df["adx"] = 25.0
        df["adx_pos"] = 0
        df["adx_neg"] = 0

    # ── Supertrend ───────────────────────────────────────────────────────
    try:
        df = _compute_supertrend(df, period=10, multiplier=3.0)
    except Exception:
        df["supertrend"] = df["close"]
        df["supertrend_dir"] = 1

    # ── Keltner Channels ─────────────────────────────────────────────────
    try:
        kc = ta.volatility.KeltnerChannel(
            high=df["high"], low=df["low"], close=df["close"], window=20
        )
        df["kc_upper"] = kc.keltner_channel_hband()
        df["kc_lower"] = kc.keltner_channel_lband()
        df["kc_middle"] = kc.keltner_channel_mband()
        # Squeeze detection: BB inside KC = low volatility squeeze
        df["squeeze"] = ((df["bb_upper"] < df["kc_upper"]) &
                         (df["bb_lower"] > df["kc_lower"])).astype(int)
    except Exception:
        df["kc_upper"] = df["bb_upper"]
        df["kc_lower"] = df["bb_lower"]
        df["kc_middle"] = df["bb_middle"]
        df["squeeze"] = 0

    # ── Volume Indicators ────────────────────────────────────────────────
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(
        close=df["close"], volume=df["volume"]
    ).on_balance_volume()

    df["volume_sma_20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"].replace(0, np.nan)

    # VWAP approximation (daily cumulative reset would be ideal, but daily
    # data doesn't have intraday granularity — so we use rolling VWAP)
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap_20"] = (typical_price * df["volume"]).rolling(20).sum() / df["volume"].rolling(20).sum()
    df["vwap_deviation"] = (df["close"] - df["vwap_20"]) / df["vwap_20"]

    # ── Returns & Volatility ─────────────────────────────────────────────
    df["daily_return"] = df["close"].pct_change()
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))
    df["volatility"] = df["daily_return"].rolling(config.VOLATILITY_WINDOW).std() * np.sqrt(252)

    # Realized volatility ratio (short vs long) — detects volatility expansion
    vol_5 = df["daily_return"].rolling(5).std()
    vol_20 = df["daily_return"].rolling(20).std()
    df["vol_ratio"] = vol_5 / vol_20.replace(0, np.nan)

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

    # Distance from 52-week high/low (if enough data)
    if len(df) >= 252:
        df["dist_52w_high"] = df["close"] / df["high"].rolling(252).max()
        df["dist_52w_low"] = df["close"] / df["low"].rolling(252).min()
    elif len(df) >= 60:
        df["dist_52w_high"] = df["close"] / df["high"].rolling(len(df)).max()
        df["dist_52w_low"] = df["close"] / df["low"].rolling(len(df)).min()

    # ── Targets ──────────────────────────────────────────────────────────
    df["future_return"] = df["close"].shift(-config.PREDICTION_HORIZON) / df["close"] - 1
    df["direction"] = (df["future_return"] > 0).astype(int)

    # 3-day forward return (less noisy than 1-day)
    df["future_return_3d"] = df["close"].shift(-3) / df["close"] - 1
    df["direction_3d"] = (df["future_return_3d"] > 0).astype(int)

    return df


def get_feature_columns() -> list[str]:
    """Return the list of ML feature column names."""
    features = []
    for w in config.MA_WINDOWS:
        features += [f"sma_{w}", f"ema_{w}", f"price_to_sma_{w}"]
    features += [
        "rsi", "macd", "macd_signal", "macd_histogram",
        "bb_upper", "bb_middle", "bb_lower", "bb_pct", "bb_bandwidth",
        "atr", "obv", "volume_sma_20", "volume_ratio",
        "daily_return", "log_return", "volatility", "vol_ratio",
        "roc_5", "roc_10", "roc_20",
        "stoch_k", "stoch_d", "williams_r",
        "hl_range", "gap",
        # New indicators
        "adx", "adx_pos", "adx_neg",
        "supertrend_dir",
        "squeeze",
        "vwap_deviation",
    ]
    return features


def compute_momentum_score(df: pd.DataFrame) -> float:
    """Calculate a 0-1 momentum score from the latest row, now ADX-aware."""
    if df.empty:
        return 0.0

    row = df.iloc[-1]
    score = 0.0
    count = 0

    # ADX check: if ADX < 20, trend is weak → reduce momentum score
    adx = row.get("adx", 25)
    adx_penalty = 1.0
    if not pd.isna(adx):
        if adx < 15:
            adx_penalty = 0.3  # Very weak trend
        elif adx < 20:
            adx_penalty = 0.6  # Weak trend
        elif adx > 40:
            adx_penalty = 1.2  # Very strong trend (bonus)

    # RSI momentum (40-70 is positive momentum)
    rsi = row.get("rsi", 50)
    if not pd.isna(rsi):
        if 40 <= rsi <= 70:
            score += (rsi - 30) / 40
            count += 1
        elif rsi > 70:
            score += 0.5
            count += 1

    # MACD above signal
    macd_val = row.get("macd", 0)
    macd_sig = row.get("macd_signal", 0)
    if not pd.isna(macd_val) and not pd.isna(macd_sig):
        if macd_val > macd_sig:
            score += 1.0
            count += 1

    # Supertrend direction
    st_dir = row.get("supertrend_dir", 0)
    if not pd.isna(st_dir) and st_dir == 1:
        score += 1.0
        count += 1

    # Price above SMAs
    for w in [20, 50, 200]:
        col = f"price_to_sma_{w}"
        if col in row.index and not pd.isna(row[col]):
            if row[col] > 1.0:
                score += 1.0
            count += 1

    # Positive ROC
    for p in [5, 10, 20]:
        roc_val = row.get(f"roc_{p}", 0)
        if not pd.isna(roc_val) and roc_val > 0:
            score += 1.0
        count += 1

    raw_score = score / max(count, 1)
    return min(max(raw_score * adx_penalty, 0), 1.0)


def compute_volume_spike_score(df: pd.DataFrame) -> float:
    """Calculate a 0-1 volume spike score."""
    if df.empty or "volume_ratio" not in df.columns:
        return 0.0

    ratio = df["volume_ratio"].iloc[-1]
    if pd.isna(ratio):
        return 0.0

    # volume_ratio > 2 is a spike, > 3 is a big spike
    return min(max((ratio - 1) / 3, 0), 1.0)
