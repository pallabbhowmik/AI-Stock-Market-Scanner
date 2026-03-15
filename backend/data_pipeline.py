"""
Data Pipeline
Fetches historical OHLCV data for filtered stocks using yfinance.
Supports multi-timeframe data (daily, hourly, 5-min).
"""
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pandas as pd
import numpy as np
import yfinance as yf

from backend import config

logger = logging.getLogger(__name__)


def fetch_daily_data(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Fetch daily OHLCV data for a single symbol."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval="1d")
        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        df = df.rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
        })
        df["symbol"] = symbol
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        return df[["symbol", "date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.debug("Error fetching daily data for %s: %s", symbol, e)
        return pd.DataFrame()


def fetch_intraday_data(symbol: str, interval: str = "1h", period: str = "5d") -> pd.DataFrame:
    """Fetch intraday data for multi-timeframe analysis."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        rename_map = {"Datetime": "date", "Date": "date", "Open": "open",
                       "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        df = df.rename(columns=rename_map)
        if "date" not in df.columns:
            df = df.reset_index()
            for col in df.columns:
                if "date" in col.lower() or "time" in col.lower():
                    df = df.rename(columns={col: "date"})
                    break

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
                      max_workers: int = 8) -> dict[str, pd.DataFrame]:
    """Fetch daily data for a batch of symbols using threading."""
    results = {}

    def _fetch(sym):
        df = fetch_daily_data(sym, period=period)
        return sym, df

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_fetch, s) for s in symbols]
        for future in as_completed(futures):
            sym, df = future.result()
            if not df.empty:
                results[sym] = df

    logger.info("Fetched daily data for %d / %d symbols", len(results), len(symbols))
    return results


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean OHLCV data: fill gaps, remove outliers."""
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

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = fetch_daily_data("RELIANCE.NS")
    print(f"Fetched {len(df)} rows for RELIANCE.NS")
    print(df.tail())
