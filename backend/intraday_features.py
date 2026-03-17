"""
Intraday Feature Engineering
Computes advanced features on 5-min / 15-min candle data for intraday prediction.

Features include:
  - VWAP and VWAP bands
  - Intraday momentum (multi-period ROC, RSI on short frames)
  - Order-flow proxies (buy/sell volume estimation, OBV micro)
  - Microstructure features (spread proxy, candle body ratio, wick analysis)
  - Multi-timeframe confluence (15m, 1h, daily alignment)
  - Time-of-day encoding (market open rush, mid-day lull, closing push)
  - Volatility regime (expanding/contracting)
  - Support / Resistance proximity from pivot points
"""
import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── VWAP ────────────────────────────────────────────────────────────────────

def _session_groups(df: pd.DataFrame) -> pd.Series:
    """Return a grouping key for each trading session (date)."""
    return df["date"].dt.date


def compute_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Add VWAP and VWAP deviation bands (±1σ, ±2σ) to an intraday DataFrame."""
    df = df.copy()
    typical = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["volume"].replace(0, np.nan)
    tp_vol = typical * vol

    groups = _session_groups(df)
    cum_tp_vol = tp_vol.groupby(groups).cumsum()
    cum_vol = vol.groupby(groups).cumsum()

    df["vwap"] = cum_tp_vol / cum_vol
    df["vwap_dev"] = df["close"] - df["vwap"]
    # Rolling std of deviation for bands
    df["vwap_std"] = df["vwap_dev"].rolling(20, min_periods=5).std()
    df["vwap_upper1"] = df["vwap"] + df["vwap_std"]
    df["vwap_upper2"] = df["vwap"] + 2 * df["vwap_std"]
    df["vwap_lower1"] = df["vwap"] - df["vwap_std"]
    df["vwap_lower2"] = df["vwap"] - 2 * df["vwap_std"]
    # Normalized distance from VWAP (useful ML feature)
    df["vwap_dist"] = df["vwap_dev"] / df["vwap"].replace(0, np.nan)
    return df


# ─── Microstructure & Candle Analysis ────────────────────────────────────────

def compute_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    body = (df["close"] - df["open"]).abs()
    full_range = (df["high"] - df["low"]).replace(0, np.nan)

    df["body_ratio"] = body / full_range          # 0 = doji, 1 = marubozu
    df["upper_wick"] = (df["high"] - df[["open", "close"]].max(axis=1)) / full_range
    df["lower_wick"] = (df[["open", "close"]].min(axis=1) - df["low"]) / full_range
    df["is_bullish"] = (df["close"] > df["open"]).astype(int)

    # Rolling candle patterns
    df["bullish_streak"] = df["is_bullish"].rolling(5, min_periods=1).sum()
    df["avg_body_5"] = body.rolling(5, min_periods=1).mean()
    df["body_expansion"] = body / df["avg_body_5"].replace(0, np.nan)  # > 1 = expanding
    return df


# ─── Order-Flow Proxies ─────────────────────────────────────────────────────

def compute_order_flow(df: pd.DataFrame) -> pd.DataFrame:
    """
    Estimate buy/sell volume using close position within the bar (BPV method).
    buy_volume ≈ volume × (close - low) / (high - low)
    """
    df = df.copy()
    hl_range = (df["high"] - df["low"]).replace(0, np.nan)
    buy_frac = (df["close"] - df["low"]) / hl_range
    buy_frac = buy_frac.clip(0, 1)

    df["buy_volume"] = (df["volume"] * buy_frac).fillna(0)
    df["sell_volume"] = (df["volume"] * (1 - buy_frac)).fillna(0)
    df["buy_sell_ratio"] = df["buy_volume"] / df["sell_volume"].replace(0, np.nan)
    df["net_flow"] = df["buy_volume"] - df["sell_volume"]

    # Cumulative order flow (micro-OBV)
    groups = _session_groups(df)
    df["cum_net_flow"] = df["net_flow"].groupby(groups).cumsum()

    # Smoothed flow momentum
    df["flow_sma_10"] = df["net_flow"].rolling(10, min_periods=3).mean()
    df["flow_acceleration"] = df["flow_sma_10"] - df["flow_sma_10"].shift(5)
    return df


# ─── Intraday Momentum ──────────────────────────────────────────────────────

def compute_intraday_momentum(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Short-period ROC
    for p in [3, 6, 12, 24]:
        df[f"roc_{p}"] = df["close"].pct_change(periods=p)

    # RSI on short frame (6-period and 14-period)
    for period in [6, 14]:
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
        loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
        rs = gain / loss.replace(0, np.nan)
        df[f"rsi_{period}"] = 100 - 100 / (1 + rs)

    # EMA crossovers
    df["ema_5"] = df["close"].ewm(span=5, adjust=False).mean()
    df["ema_13"] = df["close"].ewm(span=13, adjust=False).mean()
    df["ema_34"] = df["close"].ewm(span=34, adjust=False).mean()
    df["ema_5_13_cross"] = (df["ema_5"] - df["ema_13"]) / df["close"]
    df["ema_13_34_cross"] = (df["ema_13"] - df["ema_34"]) / df["close"]

    # MACD on intraday (8, 21, 5)
    ema_fast = df["close"].ewm(span=8, adjust=False).mean()
    ema_slow = df["close"].ewm(span=21, adjust=False).mean()
    df["macd_intra"] = ema_fast - ema_slow
    df["macd_signal_intra"] = df["macd_intra"].ewm(span=5, adjust=False).mean()
    df["macd_hist_intra"] = df["macd_intra"] - df["macd_signal_intra"]

    # Stochastic RSI
    rsi = df["rsi_14"]
    rsi_min = rsi.rolling(14, min_periods=5).min()
    rsi_max = rsi.rolling(14, min_periods=5).max()
    rsi_range = (rsi_max - rsi_min).replace(0, np.nan)
    df["stoch_rsi"] = (rsi - rsi_min) / rsi_range
    df["stoch_rsi_k"] = df["stoch_rsi"].rolling(3, min_periods=1).mean()
    return df


# ─── Volatility Features ────────────────────────────────────────────────────

def compute_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # ATR on intraday
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)

    df["atr_14"] = tr.rolling(14, min_periods=5).mean()
    df["atr_5"] = tr.rolling(5, min_periods=3).mean()
    df["atr_ratio"] = df["atr_5"] / df["atr_14"].replace(0, np.nan)  # expanding/contracting

    # Bollinger bandwidth
    sma_20 = df["close"].rolling(20, min_periods=10).mean()
    std_20 = df["close"].rolling(20, min_periods=10).std()
    bb_upper = sma_20 + 2 * std_20
    bb_lower = sma_20 - 2 * std_20
    df["bb_width"] = (bb_upper - bb_lower) / sma_20.replace(0, np.nan)
    df["bb_pct"] = (df["close"] - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)

    # Keltner channel
    ema_20 = df["close"].ewm(span=20, adjust=False).mean()
    kc_upper = ema_20 + 1.5 * df["atr_14"]
    kc_lower = ema_20 - 1.5 * df["atr_14"]
    # Squeeze: BB inside KC
    df["squeeze"] = ((bb_lower > kc_lower) & (bb_upper < kc_upper)).astype(int)

    # Realized volatility (last 20 bars annualized to trading session)
    df["rvol_20"] = df["close"].pct_change().rolling(20, min_periods=5).std()
    return df


# ─── Time-of-Day Encoding ───────────────────────────────────────────────────

def compute_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hour"] = df["date"].dt.hour
    df["minute"] = df["date"].dt.minute
    minutes_since_open = (df["hour"] - 9) * 60 + (df["minute"] - 15)
    minutes_since_open = minutes_since_open.clip(lower=0)
    total_minutes = 375  # 9:15 to 15:30

    # Normalized time position (0 = open, 1 = close)
    df["time_position"] = minutes_since_open / total_minutes

    # Cyclical encoding
    df["time_sin"] = np.sin(2 * math.pi * df["time_position"])
    df["time_cos"] = np.cos(2 * math.pi * df["time_position"])

    # Market session buckets
    df["is_opening_15m"] = (minutes_since_open <= 15).astype(int)
    df["is_first_hour"] = (minutes_since_open <= 60).astype(int)
    df["is_last_hour"] = (minutes_since_open >= 315).astype(int)
    df["is_last_15m"] = (minutes_since_open >= 360).astype(int)

    # Day of week
    df["day_of_week"] = df["date"].dt.dayofweek   # 0=Monday, 4=Friday
    return df


# ─── Support / Resistance via Pivot Points ───────────────────────────────────

def compute_pivot_points(df: pd.DataFrame, daily_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Add classic pivot points (support/resistance) from previous day's OHLC.
    If daily_df is not supplied, calculates from intraday data (previous session).
    """
    df = df.copy()
    groups = _session_groups(df)

    if daily_df is not None and not daily_df.empty:
        daily = daily_df.copy()
        daily["_date"] = pd.to_datetime(daily["date"]).dt.date
        prev_day = daily.set_index("_date")[["high", "low", "close"]].shift(1)
        prev_map = prev_day.to_dict("index")

        pivots = []
        for _, row in df.iterrows():
            d = row["date"].date()
            p = prev_map.get(d, {})
            if p:
                pp = (p.get("high", 0) + p.get("low", 0) + p.get("close", 0)) / 3
                r1 = 2 * pp - p.get("low", 0)
                s1 = 2 * pp - p.get("high", 0)
                r2 = pp + (p.get("high", 0) - p.get("low", 0))
                s2 = pp - (p.get("high", 0) - p.get("low", 0))
                pivots.append({"pp": pp, "r1": r1, "r2": r2, "s1": s1, "s2": s2})
            else:
                pivots.append({"pp": np.nan, "r1": np.nan, "r2": np.nan,
                               "s1": np.nan, "s2": np.nan})
        pivot_df = pd.DataFrame(pivots, index=df.index)
    else:
        # Compute from intraday sessions
        session_stats = df.groupby(groups).agg(
            h=("high", "max"), l=("low", "min"), c=("close", "last")
        )
        session_stats["pp"] = (session_stats["h"] + session_stats["l"] + session_stats["c"]) / 3
        session_stats["r1"] = 2 * session_stats["pp"] - session_stats["l"]
        session_stats["s1"] = 2 * session_stats["pp"] - session_stats["h"]
        session_stats["r2"] = session_stats["pp"] + (session_stats["h"] - session_stats["l"])
        session_stats["s2"] = session_stats["pp"] - (session_stats["h"] - session_stats["l"])
        # Shift so today gets yesterday's pivots
        session_stats = session_stats.shift(1)
        pivot_map = session_stats[["pp", "r1", "r2", "s1", "s2"]].to_dict("index")
        pivots = []
        for _, row in df.iterrows():
            d = row["date"].date()
            p = pivot_map.get(d, {})
            pivots.append({
                "pp": p.get("pp", np.nan), "r1": p.get("r1", np.nan),
                "r2": p.get("r2", np.nan), "s1": p.get("s1", np.nan),
                "s2": p.get("s2", np.nan),
            })
        pivot_df = pd.DataFrame(pivots, index=df.index)

    for col in ["pp", "r1", "r2", "s1", "s2"]:
        df[f"pivot_{col}"] = pivot_df[col]

    # Distance to nearest support/resistance (normalized)
    close = df["close"]
    df["dist_to_r1"] = (df["pivot_r1"] - close) / close.replace(0, np.nan)
    df["dist_to_s1"] = (close - df["pivot_s1"]) / close.replace(0, np.nan)
    df["dist_to_pp"] = (close - df["pivot_pp"]) / close.replace(0, np.nan)
    return df


# ─── Multi-Timeframe Alignment ──────────────────────────────────────────────

def compute_mtf_features(df_5m: pd.DataFrame, df_15m: pd.DataFrame = None,
                         df_daily: pd.DataFrame = None) -> pd.DataFrame:
    """
    Add higher-timeframe trend alignment features to 5-minute data.
    Alignment = how many timeframes agree on direction.
    """
    df = df_5m.copy()

    # 5m trend (already in df)
    df["trend_5m"] = np.sign(df["close"] - df["ema_34"]) if "ema_34" in df.columns else 0

    # 15m trend
    if df_15m is not None and not df_15m.empty and len(df_15m) >= 34:
        ema34_15m = df_15m["close"].ewm(span=34, adjust=False).mean()
        trend_15m = np.sign(df_15m["close"] - ema34_15m)
        # Map 15m trend to 5m rows via asof merge
        t15 = df_15m[["date"]].copy()
        t15["trend_15m"] = trend_15m.values
        df = pd.merge_asof(df.sort_values("date"), t15.sort_values("date"),
                           on="date", direction="backward")
    else:
        df["trend_15m"] = 0

    # Daily trend
    if df_daily is not None and not df_daily.empty and len(df_daily) >= 50:
        sma50_d = df_daily["close"].rolling(50).mean()
        trend_d = np.sign(df_daily["close"] - sma50_d)
        td = df_daily[["date"]].copy()
        td["trend_daily"] = trend_d.values
        td["date"] = pd.to_datetime(td["date"])
        df = pd.merge_asof(df.sort_values("date"), td.sort_values("date"),
                           on="date", direction="backward")
    else:
        df["trend_daily"] = 0

    df["trend_5m"] = df["trend_5m"].fillna(0)
    df["trend_15m"] = df["trend_15m"].fillna(0)
    df["trend_daily"] = df["trend_daily"].fillna(0)

    # Alignment score: -3 (all bearish) to +3 (all bullish)
    df["mtf_alignment"] = df["trend_5m"] + df["trend_15m"] + df["trend_daily"]
    df["mtf_agreement"] = (
        (df["trend_5m"] == df["trend_15m"]) &
        (df["trend_15m"] == df["trend_daily"])
    ).astype(int)
    return df


# ─── Intraday Targets ───────────────────────────────────────────────────────

def compute_intraday_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Add forward-looking return targets for multiple horizons."""
    df = df.copy()
    for bars, label in [(3, "15m"), (6, "30m"), (12, "1h")]:
        df[f"fwd_return_{label}"] = df["close"].shift(-bars) / df["close"] - 1
        df[f"direction_{label}"] = (df[f"fwd_return_{label}"] > 0).astype(int)

        # Sharper target: must beat transaction cost (0.1%)
        df[f"strong_buy_{label}"] = (df[f"fwd_return_{label}"] > 0.002).astype(int)
        df[f"strong_sell_{label}"] = (df[f"fwd_return_{label}"] < -0.002).astype(int)
    return df


# ─── Master Feature Pipeline ────────────────────────────────────────────────

def compute_intraday_features(
    df_5m: pd.DataFrame,
    df_15m: pd.DataFrame = None,
    df_daily: pd.DataFrame = None,
    add_targets: bool = True,
) -> pd.DataFrame:
    """
    Full intraday feature computation pipeline.
    Expects a 5-minute OHLCV DataFrame with columns: date, open, high, low, close, volume.
    """
    if df_5m.empty or len(df_5m) < 40:
        return pd.DataFrame()

    df = df_5m.copy().sort_values("date").reset_index(drop=True)

    # Core feature blocks
    df = compute_vwap(df)
    df = compute_candle_features(df)
    df = compute_order_flow(df)
    df = compute_intraday_momentum(df)
    df = compute_volatility_features(df)
    df = compute_time_features(df)
    df = compute_pivot_points(df, daily_df=df_daily)
    df = compute_mtf_features(df, df_15m=df_15m, df_daily=df_daily)

    if add_targets:
        df = compute_intraday_targets(df)

    return df


def get_intraday_feature_columns() -> list[str]:
    """Return the list of ML feature columns for intraday prediction."""
    return [
        # VWAP
        "vwap_dist", "vwap_dev",
        # Candle
        "body_ratio", "upper_wick", "lower_wick", "is_bullish",
        "bullish_streak", "body_expansion",
        # Order flow
        "buy_sell_ratio", "flow_sma_10", "flow_acceleration",
        # Momentum
        "roc_3", "roc_6", "roc_12", "roc_24",
        "rsi_6", "rsi_14",
        "ema_5_13_cross", "ema_13_34_cross",
        "macd_intra", "macd_signal_intra", "macd_hist_intra",
        "stoch_rsi_k",
        # Volatility
        "atr_ratio", "bb_width", "bb_pct", "squeeze", "rvol_20",
        # Time
        "time_position", "time_sin", "time_cos",
        "is_opening_15m", "is_first_hour", "is_last_hour",
        "day_of_week",
        # Pivots
        "dist_to_r1", "dist_to_s1", "dist_to_pp",
        # Multi-timeframe
        "mtf_alignment", "mtf_agreement",
    ]
