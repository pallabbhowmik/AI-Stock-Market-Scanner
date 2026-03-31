"""
Data Pipeline
Fetches historical OHLCV data for filtered stocks using yfinance.
Supports multi-timeframe data (daily, hourly, 5-min).

Improvements:
- Batch multi-ticker download for 3-5x faster fetching
- Outlier detection in clean_data
- Better error handling and retry logic
"""
import logging
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pandas as pd
import numpy as np

from backend import config

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF = 3   # seconds, doubles each attempt


def _download_with_retry(symbol: str, **kwargs) -> pd.DataFrame:
    """Download data for a single symbol with retry + exponential back-off."""
    import yfinance as yf
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            data = yf.download(symbol, progress=False, **kwargs)
            if data is not None and not data.empty:
                return data
        except Exception as e:
            logger.debug("Attempt %d for %s failed: %s", attempt, symbol, e)
        if attempt < _MAX_RETRIES:
            time.sleep(_RETRY_BACKOFF * (2 ** (attempt - 1)))
    return pd.DataFrame()


def fetch_daily_data(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Fetch daily OHLCV data for a single symbol."""
    try:
        # Append .NS suffix for NSE stocks if not already present
        ticker = symbol if "." in symbol else f"{symbol}.NS"
        df = _download_with_retry(ticker, period=period, interval="1d")
        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        col_map = {}
        for c in df.columns:
            cl = str(c).lower()
            if cl in ("date", "datetime"):
                col_map[c] = "date"
            elif cl == "open":
                col_map[c] = "open"
            elif cl == "high":
                col_map[c] = "high"
            elif cl == "low":
                col_map[c] = "low"
            elif cl == "close":
                col_map[c] = "close"
            elif cl == "volume":
                col_map[c] = "volume"
        df = df.rename(columns=col_map)
        df["symbol"] = symbol
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        return df[["symbol", "date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.debug("Error fetching daily data for %s: %s", symbol, e)
        return pd.DataFrame()


def fetch_intraday_data(symbol: str, interval: str = "1h", period: str = "5d") -> pd.DataFrame:
    """Fetch intraday data for multi-timeframe analysis."""
    try:
        ticker = symbol if "." in symbol else f"{symbol}.NS"
        df = _download_with_retry(ticker, period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        col_map = {}
        for c in df.columns:
            cl = str(c).lower()
            if "date" in cl or "time" in cl:
                col_map[c] = "date"
            elif cl == "open":
                col_map[c] = "open"
            elif cl == "high":
                col_map[c] = "high"
            elif cl == "low":
                col_map[c] = "low"
            elif cl == "close":
                col_map[c] = "close"
            elif cl == "volume":
                col_map[c] = "volume"
        df = df.rename(columns=col_map)
        df["symbol"] = symbol
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        return df[["symbol", "date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.debug("Error fetching %s data for %s: %s", interval, symbol, e)
        return pd.DataFrame()


def fetch_multi_timeframe(symbol: str) -> dict:
    """
    Fetch data across multiple timeframes for a symbol.
    Returns dict with keys: 'daily', '1h', '5m'
    """
    result = {}

    result["daily"] = fetch_daily_data(symbol, period="1y")
    result["1h"] = fetch_intraday_data(symbol, interval="1h", period="5d")
    result["5m"] = fetch_intraday_data(symbol, interval="5m", period="5d")

    return result


def fetch_batch_daily(symbols: list[str], period: str = "1y",
                      max_workers: int = 5) -> dict[str, pd.DataFrame]:
    """Fetch daily data for a batch of symbols using threading with rate-limit delay."""
    results = {}

    def _fetch(sym):
        df = fetch_daily_data(sym, period=period)
        time.sleep(0.3)
        return sym, df

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_fetch, s) for s in symbols]
        for future in as_completed(futures):
            try:
                sym, df = future.result()
                if not df.empty:
                    results[sym] = df
            except Exception as e:
                logger.debug("Batch fetch error: %s", e)

    logger.info("Fetched daily data for %d / %d symbols", len(results), len(symbols))
    return results


def batch_download_daily(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """
    Download daily data for multiple symbols in one yfinance call.
    This is 3-5x faster than downloading one by one.
    """
    import yfinance as yf

    tickers = [s if "." in s else f"{s}.NS" for s in symbols]
    symbol_map = {t: s for t, s in zip(tickers, symbols)}

    try:
        raw = yf.download(tickers, period=period, interval="1d",
                          group_by="ticker", progress=False, threads=True)
    except Exception as e:
        logger.warning("Batch download failed, falling back to individual: %s", e)
        return fetch_batch_daily(symbols, period=period)

    results = {}
    for ticker, symbol in symbol_map.items():
        try:
            if len(tickers) == 1:
                df = raw.copy()
            else:
                if ticker not in raw.columns.get_level_values(0):
                    continue
                df = raw[ticker].copy()

            df = df.reset_index()
            df.columns = [str(c).lower() for c in df.columns]
            if "date" not in df.columns and "datetime" in df.columns:
                df = df.rename(columns={"datetime": "date"})
            df["symbol"] = symbol
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            df = df.dropna(subset=["close"])
            if not df.empty:
                results[symbol] = df[["symbol", "date", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            logger.debug("Error processing batch data for %s: %s", symbol, e)

    logger.info("Batch downloaded %d / %d symbols", len(results), len(symbols))
    return results


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean OHLCV data: fill gaps, remove outliers, validate."""
    if df.empty:
        return df

    df = df.copy()
    df = df.drop_duplicates(subset=["date"], keep="last")
    df = df.sort_values("date").reset_index(drop=True)

    # Forward fill, then backfill price columns
    price_cols = ["open", "high", "low", "close"]
    df[price_cols] = df[price_cols].ffill().bfill()
    df["volume"] = df["volume"].fillna(0).astype(int)
    df = df.dropna(subset=["close"])

    # Remove price outliers: filter rows where close changed > 50% in one day
    if len(df) > 5:
        pct_change = df["close"].pct_change().abs()
        df = df[pct_change.fillna(0) < 0.50].reset_index(drop=True)

    # Ensure OHLC consistency: high >= close >= low
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = fetch_daily_data("RELIANCE.NS")
    print(f"Fetched {len(df)} rows for RELIANCE.NS")
    print(df.tail())
