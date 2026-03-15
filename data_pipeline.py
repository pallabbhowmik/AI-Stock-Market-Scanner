"""
Data Pipeline Module
Fetches historical stock data from Yahoo Finance, cleans it, and stores in SQLite.
"""
import os
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

import config

logger = logging.getLogger(__name__)


def init_database() -> None:
    """Create the SQLite database and tables if they don't exist."""
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            adj_close REAL,
            volume INTEGER,
            PRIMARY KEY (ticker, date)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ticker ON stock_data (ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_date ON stock_data (date)
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", config.DATABASE_PATH)


def fetch_stock_data(
    ticker: str,
    start_date: str = config.DATA_START_DATE,
    end_date: Optional[str] = config.DATA_END_DATE,
    interval: str = config.DATA_INTERVAL,
) -> pd.DataFrame:
    """Fetch historical OHLCV data for a single ticker from Yahoo Finance."""
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    logger.info("Fetching %s from %s to %s", ticker, start_date, end_date)
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date, interval=interval)

    if df.empty:
        logger.warning("No data returned for %s", ticker)
        return pd.DataFrame()

    df = df.reset_index()
    df = df.rename(columns={
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    # Use 'close' as adj_close if Adj Close not present
    if "Adj Close" in df.columns:
        df = df.rename(columns={"Adj Close": "adj_close"})
    else:
        df["adj_close"] = df["close"]

    df["ticker"] = ticker
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    df = df[["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]]
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean raw stock data: handle missing values, remove duplicates, sort."""
    if df.empty:
        return df

    df = df.drop_duplicates(subset=["ticker", "date"], keep="last")
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # Forward-fill price columns within each ticker, then back-fill any leading NaNs
    price_cols = ["open", "high", "low", "close", "adj_close"]
    df[price_cols] = df.groupby("ticker")[price_cols].transform(
        lambda x: x.ffill().bfill()
    )

    # Fill missing volume with 0
    df["volume"] = df["volume"].fillna(0).astype(int)

    # Drop rows where price is still NaN (shouldn't happen after ffill/bfill)
    df = df.dropna(subset=["close"])
    return df


def store_data(df: pd.DataFrame) -> None:
    """Store cleaned data into SQLite, replacing existing records."""
    if df.empty:
        return

    init_database()
    conn = sqlite3.connect(config.DATABASE_PATH)
    df.to_sql("stock_data", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    logger.info("Stored %d rows in database", len(df))


def load_data(ticker: Optional[str] = None) -> pd.DataFrame:
    """Load stock data from the SQLite database."""
    if not os.path.exists(config.DATABASE_PATH):
        logger.warning("Database not found. Run the data pipeline first.")
        return pd.DataFrame()

    conn = sqlite3.connect(config.DATABASE_PATH)
    if ticker:
        query = "SELECT * FROM stock_data WHERE ticker = ?"
        df = pd.read_sql_query(query, conn, params=(ticker,))
    else:
        df = pd.read_sql_query("SELECT * FROM stock_data", conn)
    conn.close()

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_latest_date(ticker: str) -> Optional[str]:
    """Get the latest date available in the database for a ticker."""
    if not os.path.exists(config.DATABASE_PATH):
        return None
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(date) FROM stock_data WHERE ticker = ?", (ticker,)
    )
    result = cursor.fetchone()[0]
    conn.close()
    return result


def update_data(tickers: Optional[list] = None) -> pd.DataFrame:
    """Fetch, clean and store data for all tickers. Incremental if data exists."""
    if tickers is None:
        tickers = config.STOCK_UNIVERSE

    all_data = []
    for ticker in tickers:
        latest = get_latest_date(ticker)
        if latest:
            start = (datetime.strptime(latest, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start = config.DATA_START_DATE

        df = fetch_stock_data(ticker, start_date=start)
        if not df.empty:
            df = clean_data(df)
            all_data.append(df)
            logger.info("Fetched %d new rows for %s", len(df), ticker)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        store_data(combined)
        return combined

    logger.info("No new data to update")
    return pd.DataFrame()


def run_full_pipeline(tickers: Optional[list] = None) -> pd.DataFrame:
    """Run the complete data pipeline: fetch, clean, store for all tickers."""
    if tickers is None:
        tickers = config.STOCK_UNIVERSE

    init_database()
    all_data = []

    for ticker in tickers:
        df = fetch_stock_data(ticker)
        if not df.empty:
            df = clean_data(df)
            all_data.append(df)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        store_data(combined)
        logger.info("Pipeline complete. Total rows: %d", len(combined))
        return combined

    logger.warning("Pipeline completed with no data")
    return pd.DataFrame()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_full_pipeline()
