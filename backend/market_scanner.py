"""
Market Scanner
Downloads stock universe from NSE, applies smart filters, and selects quality stocks.
"""
import logging
import io
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
import yfinance as yf
import requests

from backend import config

logger = logging.getLogger(__name__)


def download_nse_symbols() -> list[str]:
    """
    Download the full list of NSE equity symbols.
    Falls back to a curated list if the download fails.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(config.NSE_SYMBOL_LIST_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))

        # NSE CSV has a 'SYMBOL' column
        symbol_col = None
        for col in df.columns:
            if "symbol" in col.strip().lower():
                symbol_col = col
                break

        if symbol_col is None:
            logger.warning("Could not find SYMBOL column in NSE CSV. Using fallback.")
            return config.FALLBACK_SYMBOLS

        symbols = df[symbol_col].dropna().str.strip().tolist()
        # Filter out weird entries
        symbols = [s for s in symbols if s.isalpha() or "-" in s or "&" in s]
        logger.info("Downloaded %d NSE symbols", len(symbols))
        return symbols

    except Exception as e:
        logger.warning("Failed to download NSE symbol list: %s. Using fallback.", e)
        return config.FALLBACK_SYMBOLS


def get_stock_info_batch(symbols: list[str], max_workers: int = 10) -> list[dict]:
    """
    Fetch basic info (price, volume, market cap) for a batch of symbols.
    Uses threading for speed.
    """
    results = []

    def _fetch_one(symbol: str) -> Optional[dict]:
        ticker_str = f"{symbol}.NS"
        try:
            ticker = yf.Ticker(ticker_str)
            hist = ticker.history(period="3mo", interval="1d")
            if hist.empty or len(hist) < 20:
                return None

            last_price = hist["Close"].iloc[-1]
            avg_volume = hist["Volume"].tail(20).mean()
            daily_returns = hist["Close"].pct_change().dropna()
            daily_vol = daily_returns.std()

            info = ticker.info or {}
            market_cap = info.get("marketCap", 0) or 0
            name = info.get("shortName", symbol)
            sector = info.get("sector", "Unknown")

            return {
                "symbol": ticker_str,
                "name": name,
                "sector": sector,
                "last_price": round(last_price, 2),
                "market_cap": market_cap,
                "avg_volume": round(avg_volume, 0),
                "daily_volatility": round(daily_vol, 4),
            }
        except Exception as e:
            logger.debug("Error fetching %s: %s", symbol, e)
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, s): s for s in symbols}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    logger.info("Fetched info for %d / %d symbols", len(results), len(symbols))
    return results


def apply_smart_filters(stocks: list[dict]) -> list[dict]:
    """
    Apply quality filters to reduce the universe to high-quality stocks.
    Filters: liquidity, price, volatility, market cap.
    """
    filtered = []
    for s in stocks:
        # Liquidity filter
        if s.get("avg_volume", 0) < config.FILTER_MIN_VOLUME:
            continue

        # Price filter
        if s.get("last_price", 0) < config.FILTER_MIN_PRICE:
            continue

        # Volatility filter
        if s.get("daily_volatility", 0) < config.FILTER_MIN_VOLATILITY:
            continue

        # Market cap filter (if set)
        if config.FILTER_MIN_MARKET_CAP > 0:
            if s.get("market_cap", 0) < config.FILTER_MIN_MARKET_CAP:
                continue

        filtered.append(s)

    logger.info("Smart filter: %d → %d stocks", len(stocks), len(filtered))
    return filtered


def apply_trend_filter(symbol: str, hist: pd.DataFrame) -> bool:
    """Check if price is above 50-day and 200-day moving averages."""
    if len(hist) < 200:
        return True  # Not enough data, include anyway

    sma_50 = hist["Close"].rolling(50).mean().iloc[-1]
    sma_200 = hist["Close"].rolling(200).mean().iloc[-1]
    price = hist["Close"].iloc[-1]

    return price > sma_50 and price > sma_200


def scan_market(max_symbols: int = 0) -> tuple[list[dict], list[dict]]:
    """
    Full market scan pipeline:
    1. Download symbols
    2. Fetch stock info
    3. Apply smart filters
    Returns (all_stocks, filtered_stocks)
    """
    logger.info("Starting market scan...")

    # Step 1: Get symbols
    symbols = download_nse_symbols()
    if max_symbols > 0:
        symbols = symbols[:max_symbols]

    logger.info("Scanning %d symbols...", len(symbols))

    # Step 2: Fetch info in parallel
    all_stocks = get_stock_info_batch(symbols)

    # Step 3: Apply filters
    filtered = apply_smart_filters(all_stocks)

    logger.info("Market scan complete: %d total, %d passed filters",
                len(all_stocks), len(filtered))
    return all_stocks, filtered


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    all_s, filtered_s = scan_market(max_symbols=50)
    print(f"\nTotal: {len(all_s)}, Filtered: {len(filtered_s)}")
    for s in filtered_s[:10]:
        print(f"  {s['symbol']:20s} ₹{s['last_price']:>10,.2f}  Vol: {s['avg_volume']:>12,.0f}")
