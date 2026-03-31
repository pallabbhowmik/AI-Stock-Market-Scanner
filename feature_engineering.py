"""
Feature Engineering Module
Computes technical indicators and derived features for ML models.
"""
import logging

import numpy as np
import pandas as pd
import ta

import config

logger = logging.getLogger(__name__)


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Add Simple and Exponential Moving Averages."""
    for window in config.MA_WINDOWS:
        df[f"sma_{window}"] = df["close"].rolling(window=window).mean()
        df[f"ema_{window}"] = df["close"].ewm(span=window, adjust=False).mean()
    return df


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """Add Relative Strength Index."""
    df["rsi"] = ta.momentum.RSIIndicator(
        close=df["close"], window=config.RSI_PERIOD
    ).rsi()
    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Add MACD, signal line, and histogram."""
    macd_indicator = ta.trend.MACD(
        close=df["close"],
        window_fast=config.MACD_FAST,
        window_slow=config.MACD_SLOW,
        window_sign=config.MACD_SIGNAL,
    )
    df["macd"] = macd_indicator.macd()
    df["macd_signal"] = macd_indicator.macd_signal()
    df["macd_histogram"] = macd_indicator.macd_diff()
    return df


def add_bollinger_bands(df: pd.DataFrame) -> pd.DataFrame:
    """Add Bollinger Bands (upper, middle, lower) and bandwidth."""
    bb = ta.volatility.BollingerBands(
        close=df["close"],
        window=config.BOLLINGER_WINDOW,
        window_dev=config.BOLLINGER_STD,
    )
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_middle"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_bandwidth"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
    return df


def add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add volume-based indicators."""
    # On-Balance Volume
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(
        close=df["close"], volume=df["volume"]
    ).on_balance_volume()

    # Volume Moving Average
    df["volume_sma_20"] = df["volume"].rolling(window=20).mean()

    # Volume ratio (current vs average)
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"].replace(0, np.nan)

    # VWAP approximation (cumulative)
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()

    return df


def add_returns_and_volatility(df: pd.DataFrame) -> pd.DataFrame:
    """Add daily returns and rolling volatility."""
    df["daily_return"] = df["close"].pct_change()
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))

    # Rolling volatility
    df["volatility"] = df["daily_return"].rolling(
        window=config.VOLATILITY_WINDOW
    ).std() * np.sqrt(252)  # Annualized

    # Cumulative return
    df["cumulative_return"] = (1 + df["daily_return"]).cumprod() - 1

    return df


def add_price_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add price-derived features."""
    # Price relative to moving averages
    for window in config.MA_WINDOWS:
        sma_col = f"sma_{window}"
        if sma_col in df.columns:
            df[f"price_to_sma_{window}"] = df["close"] / df[sma_col]

    # High-low range
    df["hl_range"] = (df["high"] - df["low"]) / df["close"]

    # Gap (open relative to previous close)
    df["gap"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)

    # Average True Range
    df["atr"] = ta.volatility.AverageTrueRange(
        high=df["high"], low=df["low"], close=df["close"], window=14
    ).average_true_range()

    return df


def add_momentum_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add momentum-based features."""
    # Rate of change
    for period in [5, 10, 20]:
        df[f"roc_{period}"] = df["close"].pct_change(periods=period)

    # Stochastic Oscillator
    stoch = ta.momentum.StochasticOscillator(
        high=df["high"], low=df["low"], close=df["close"], window=14, smooth_window=3
    )
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    # Williams %R
    df["williams_r"] = ta.momentum.WilliamsRIndicator(
        high=df["high"], low=df["low"], close=df["close"], lbp=14
    ).williams_r()

    # ADX — trend strength indicator
    try:
        adx_ind = ta.trend.ADXIndicator(
            high=df["high"], low=df["low"], close=df["close"], window=14
        )
        df["adx"] = adx_ind.adx()
        df["adx_pos"] = adx_ind.adx_pos()
        df["adx_neg"] = adx_ind.adx_neg()
    except Exception:
        df["adx"] = 25.0
        df["adx_pos"] = 0
        df["adx_neg"] = 0

    return df


def add_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Add Supertrend indicator — highly effective trend-following signal."""
    if "atr" not in df.columns:
        return df

    hl2 = (df["high"] + df["low"]) / 2
    atr = df["atr"]
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(np.nan, index=df.index)
    direction = pd.Series(1, index=df.index)

    for i in range(1, len(df)):
        if df["close"].iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        if direction.iloc[i] == 1:
            lb = lower_band.iloc[i]
            if direction.iloc[i - 1] == 1:
                lb = max(lb, lower_band.iloc[i - 1])
            lower_band.iloc[i] = lb
            supertrend.iloc[i] = lb
        else:
            ub = upper_band.iloc[i]
            if direction.iloc[i - 1] == -1:
                ub = min(ub, upper_band.iloc[i - 1])
            upper_band.iloc[i] = ub
            supertrend.iloc[i] = ub

    df["supertrend"] = supertrend
    df["supertrend_dir"] = direction
    return df


def add_target_variables(df: pd.DataFrame, horizon: int = config.PREDICTION_HORIZON) -> pd.DataFrame:
    """Add target variables for ML models."""
    # Next-day return
    df["future_return"] = df["close"].shift(-horizon) / df["close"] - 1

    # Binary direction (1 = up, 0 = down)
    df["direction"] = (df["future_return"] > 0).astype(int)

    # Future close price
    df["future_close"] = df["close"].shift(-horizon)

    return df


def compute_all_features(df: pd.DataFrame, add_targets: bool = True) -> pd.DataFrame:
    """Apply all feature engineering steps to a DataFrame for a single ticker."""
    if df.empty:
        return df

    df = df.copy()
    df = df.sort_values("date").reset_index(drop=True)

    # Technical indicators
    df = add_moving_averages(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_bands(df)
    df = add_volume_indicators(df)
    df = add_returns_and_volatility(df)
    df = add_price_features(df)
    df = add_momentum_features(df)
    df = add_supertrend(df)

    if add_targets:
        df = add_target_variables(df)

    logger.info("Computed features. Shape: %s", df.shape)
    return df


def get_feature_columns(df: pd.DataFrame) -> list:
    """Return the list of feature columns (excluding metadata and targets)."""
    exclude = [
        "ticker", "date", "open", "high", "low", "close", "adj_close", "volume",
        "future_return", "direction", "future_close",
    ]
    return [col for col in df.columns if col not in exclude]


def prepare_ml_dataset(df: pd.DataFrame) -> tuple:
    """
    Prepare feature matrix X and target arrays from a fully-featured DataFrame.
    Returns (X, y_direction, y_return, dates) after dropping NaN rows.
    """
    feature_cols = get_feature_columns(df)

    # Drop rows with NaN in features or targets
    required_cols = feature_cols + ["direction", "future_return"]
    clean = df.dropna(subset=required_cols).copy()

    X = clean[feature_cols].values
    y_direction = clean["direction"].values
    y_return = clean["future_return"].values
    dates = clean["date"].values

    logger.info("ML dataset: %d samples, %d features", X.shape[0], X.shape[1])
    return X, y_direction, y_return, dates, feature_cols


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data_pipeline import load_data

    df = load_data("RELIANCE.NS")
    if not df.empty:
        featured = compute_all_features(df)
        print(featured.tail())
        print(f"\nFeature columns ({len(get_feature_columns(featured))}):")
        print(get_feature_columns(featured))
