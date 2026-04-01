"""
Market Scanner
Downloads stock universe from NSE, applies smart filters, and selects quality stocks.
"""
import logging
import io
import time
from typing import Optional

import pandas as pd
import numpy as np
import requests

from backend import config

logger = logging.getLogger(__name__)

# ── Batch download chunk size & throttle ────────────────────────────────
_DOWNLOAD_CHUNK = 30          # symbols per yf.download() call (keep small for memory)
_CHUNK_DELAY    = 2           # seconds between chunks (rate-limit guard)
_MAX_RETRIES    = 3           # retries per chunk on failure
_RETRY_BACKOFF  = 5           # base seconds for exponential back-off


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


def get_stock_info_batch(symbols: list[str], max_workers: int = 5) -> list[dict]:
    """
    Fetch basic info (price, volume, volatility) for a batch of symbols.
    Uses yf.download() in chunks instead of individual Ticker calls to
    minimise HTTP requests and avoid Yahoo rate-limiting / crumb errors.
    """
    import gc as _gc
    ticker_symbols = [f"{s}.NS" for s in symbols]
    results = []

    for chunk_start in range(0, len(ticker_symbols), _DOWNLOAD_CHUNK):
        chunk = ticker_symbols[chunk_start : chunk_start + _DOWNLOAD_CHUNK]

        # 1mo is enough for volume/volatility filtering (need ~20 days)
        hist_data = _download_chunk_with_retry(chunk, period="1mo", interval="1d")
        if hist_data is None:
            continue

        for sym in chunk:
            try:
                # Extract per-symbol DataFrame from the batch result
                if len(chunk) == 1:
                    hist = hist_data
                else:
                    # yf.download with multiple tickers returns MultiIndex columns
                    try:
                        hist = hist_data.xs(sym, level="Ticker", axis=1)
                    except (KeyError, TypeError):
                        # Fallback for older column formats
                        try:
                            hist = hist_data[sym]
                        except (KeyError, TypeError):
                            continue

                if hist.empty or len(hist) < 20:
                    continue

                # Normalise column names to title-case
                hist.columns = [c.title() if isinstance(c, str) else str(c).title()
                                for c in hist.columns]

                close = hist.get("Close")
                volume = hist.get("Volume")
                if close is None or volume is None:
                    continue

                last_price = float(close.iloc[-1])
                avg_volume = float(volume.tail(20).mean())
                daily_returns = close.pct_change(fill_method=None).dropna()
                daily_vol = float(daily_returns.std())

                results.append({
                    "symbol": sym,
                    "name": sym.replace(".NS", ""),
                    "sector": "Unknown",
                    "last_price": round(last_price, 2),
                    "market_cap": 0,
                    "avg_volume": round(avg_volume, 0),
                    "daily_volatility": round(daily_vol, 4),
                })
            except Exception as e:
                logger.debug("Error processing %s: %s", sym, e)

        # Free the large chunk DataFrame and throttle between chunks
        del hist_data
        _gc.collect()
        if chunk_start + _DOWNLOAD_CHUNK < len(ticker_symbols):
            time.sleep(_CHUNK_DELAY)

    logger.info("Fetched info for %d / %d symbols", len(results), len(symbols))
    return results


def _download_chunk_with_retry(symbols: list[str], **kwargs) -> Optional[pd.DataFrame]:
    """Download a chunk of symbols with retry + exponential back-off."""
    import yfinance as yf
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            data = yf.download(
                symbols,
                progress=False,
                threads=True,
                **kwargs,
            )
            if data is not None and not data.empty:
                return data
        except RuntimeError as e:
            # yfinance threads=True can hit "dictionary changed size during
            # iteration"; retry with threads=False as fallback.
            if "dictionary changed size" in str(e) and attempt < _MAX_RETRIES:
                logger.warning("Download attempt %d/%d hit dict-size bug, retrying single-threaded", attempt, _MAX_RETRIES)
                try:
                    data = yf.download(symbols, progress=False, threads=False, **kwargs)
                    if data is not None and not data.empty:
                        return data
                except Exception:
                    pass
            else:
                logger.warning("Download attempt %d/%d failed: %s", attempt, _MAX_RETRIES, e)
        except Exception as e:
            logger.warning("Download attempt %d/%d failed: %s", attempt, _MAX_RETRIES, e)

        if attempt < _MAX_RETRIES:
            wait = _RETRY_BACKOFF * (2 ** (attempt - 1))
            logger.info("Retrying in %ds…", wait)
            time.sleep(wait)

    logger.warning("All %d download attempts failed for %d symbols",
                    _MAX_RETRIES, len(symbols))
    return None


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
