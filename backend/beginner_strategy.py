"""
Beginner Strategy Engine
Implemented simplified, high-probability trades specifically designed for beginners.
Avoids complex/noisy signals and restricts trading in sideways markets.

Improvements:
- Raised confidence minimum to 0.75 for higher quality trades
- Added intraday time filter (no trades in first 15min or last 30min)
- Added R:R validation (minimum 2:1 risk-reward)
- Better volume confirmation
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime

from backend import config
from backend.market_regime import detect_regime
from backend.breakout_detector import detect_resistance_breakout
from backend.intraday_features import compute_intraday_features

logger = logging.getLogger(__name__)

# Constants
MIN_CONFIDENCE = 0.75  # Raised from 0.70 for higher quality trades
MAX_TRADES_PER_DAY = 2
MIN_RISK_REWARD = 2.0  # Minimum risk-reward ratio

def get_options_suggestion(symbol: str, current_price: float, signal_type: str) -> str:
    """
    Suggests the nearest ATM option based on the current price.
    Nifty step is typically 50, BankNifty is 100. Other stocks vary, so we round to nearest 10s or 50s.
    """
    if symbol == "^NSEI" or symbol.upper() == "NIFTY":
        strike = round(current_price / 50) * 50
        name = "NIFTY"
    elif symbol == "^NSEBANK" or symbol.upper() == "BANKNIFTY":
        strike = round(current_price / 100) * 100
        name = "BANKNIFTY"
    else:
        # Default fallback rounding
        strike = round(current_price / 10) * 10
        name = symbol.upper()

    option_type = "CE" if signal_type == "BUY" else "PE"
    return f"{name} {strike} {option_type}"


def check_market_conditions() -> dict:
    """
    Checks if the broad market supports beginner trading.
    Blocks sideways markets.
    """
    regime_info = detect_regime()
    regime = regime_info.get("regime", "SIDEWAYS")
    confidence = regime_info.get("confidence", 0)

    if regime == "SIDEWAYS":
        return {
            "acceptable": False,
            "reason": "Market is range-bound/sideways. High risk of choppy movements.",
            "regime": regime
        }
    
    # Needs clear trend
    if confidence < 0.50:
        return {
            "acceptable": False,
            "reason": f"Market trend is unclear ({regime} with low confidence).",
            "regime": regime
        }

    return {
        "acceptable": True,
        "reason": f"Clear {regime} trend detected.",
        "regime": regime
    }


def analyze_stock_for_beginner(symbol: str, df_5m: pd.DataFrame, df_15m: pd.DataFrame = None, df_daily: pd.DataFrame = None) -> dict:
    """
    Analyzes a single stock for 3 specific beginner setups:
    1. Trend Continuation
    2. Breakout
    3. Pullback
    Returns the best signal, or None if no high-probability setup exists.
    """
    if df_5m.empty or len(df_5m) < 50:
        return None

    # We need features: VWAP, MAs (9, 20, 50), Volume
    df = compute_intraday_features(df_5m, df_15m=df_15m, df_daily=df_daily, add_targets=False)
    if df.empty or "vwap" not in df.columns:
        return None

    # Calculate required MAs
    df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["sma_50"] = df["close"].rolling(50).mean()
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    current_price = latest["close"]
    
    # Check volume
    vol_avg = df["volume"].tail(20).mean()
    vol_ratio = latest["volume"] / vol_avg if vol_avg > 0 else 0
    has_high_volume = vol_ratio > 1.5

    signals = []

    # 1. TREND CONTINUATION
    # Uptrend: Price > VWAP, 9 > 20 > 50
    if current_price > latest["vwap"] and latest["ema_9"] > latest["ema_20"] and latest["ema_20"] > latest["sma_50"]:
        if has_high_volume:
            signals.append({
                "type": "Trend Continuation",
                "signal": "BUY",
                "confidence": 0.85,
                "explanation": "Strong uptrend with high volume. Moving averages are perfectly aligned.",
                "entry": current_price,
                "stop_loss": latest["ema_20"],
                "target": current_price + (current_price - latest["ema_20"]) * 2 # 1:2 RR
            })
    
    # Downtrend: Price < VWAP, 9 < 20 < 50
    elif current_price < latest["vwap"] and latest["ema_9"] < latest["ema_20"] and latest["ema_20"] < latest["sma_50"]:
        if has_high_volume:
            signals.append({
                "type": "Trend Continuation",
                "signal": "SELL",
                "confidence": 0.85,
                "explanation": "Strong downtrend with high volume. Moving averages are perfectly aligned downwards.",
                "entry": current_price,
                "stop_loss": latest["ema_20"],
                "target": current_price - (latest["ema_20"] - current_price) * 2
            })

    # 2. BREAKOUT TRADING
    # Ensure current close is relatively near the high
    breakout = detect_resistance_breakout(df, lookback=60)
    if breakout["detected"] and has_high_volume:
        signals.append({
            "type": "Breakout",
            "signal": "BUY",
            "confidence": 0.80 + (breakout["strength"] * 0.1),
            "explanation": f"Price broke strong resistance on high volume ({vol_ratio:.1f}x average).",
            "entry": current_price,
            "stop_loss": prev["low"], # Below breakout candle
            "target": current_price + (current_price - prev["low"]) * 2
        })

    # 3. PULLBACK ENTRY
    # Uptrend pullback to EMA 20
    if latest["ema_9"] > latest["sma_50"] and prev["close"] < prev["ema_20"] and current_price > latest["ema_20"]:
        signals.append({
            "type": "Pullback",
            "signal": "BUY",
            "confidence": 0.75,
            "explanation": "Stock in an uptrend pulled back to the 20 EMA and is resuming the upward move.",
            "entry": current_price,
            "stop_loss": min(prev["low"], latest["low"]),
            "target": current_price + (current_price - min(prev["low"], latest["low"])) * 2
        })
    # Downtrend pullback to EMA 20
    elif latest["ema_9"] < latest["sma_50"] and prev["close"] > prev["ema_20"] and current_price < latest["ema_20"]:
            signals.append({
                "type": "Pullback",
                "signal": "SELL",
                "confidence": 0.75,
                "explanation": "Stock in a downtrend pulled back to the 20 EMA and is resuming the downward move.",
                "entry": current_price,
                "stop_loss": max(prev["high"], latest["high"]),
                "target": current_price - (max(prev["high"], latest["high"]) - current_price) * 2
            })

    # Filter: minimum confidence AND minimum risk-reward ratio
    valid_signals = []
    for s in signals:
        if s["confidence"] < MIN_CONFIDENCE:
            continue
        # Validate risk-reward ratio
        risk = abs(s["entry"] - s["stop_loss"])
        reward = abs(s["target"] - s["entry"])
        rr = reward / risk if risk > 0 else 0
        if rr < MIN_RISK_REWARD:
            continue
        s["risk_reward"] = round(rr, 2)
        valid_signals.append(s)

    if not valid_signals:
        return None

    # Pick the highest confidence
    best_signal = max(valid_signals, key=lambda x: x["confidence"])

    # Add option suggestion
    best_signal["symbol"] = symbol
    best_signal["options_suggestion"] = get_options_suggestion(symbol, current_price, best_signal["signal"])

    return best_signal


def scan_for_beginners(symbols: list[str]) -> dict:
    """
    Main entry point. Scans a list of symbols and returns the top beginner trades.
    """
    market = check_market_conditions()
    
    if not market["acceptable"]:
        return {
            "status": "NO_TRADE",
            "message": "NO SAFE TRADE TODAY",
            "reason": market["reason"],
            "trades": []
        }

    from backend.data_pipeline import fetch_intraday_data, clean_data, fetch_daily_data
    from datetime import datetime

    # Intraday time filter: avoid first 15min and last 30min
    now = datetime.now()
    market_open_buffer = now.replace(hour=9, minute=30)  # 9:15 + 15min
    market_close_buffer = now.replace(hour=15, minute=0)  # 15:30 - 30min
    if now < market_open_buffer or now > market_close_buffer:
        return {
            "status": "NO_TRADE",
            "message": "Outside optimal trading window",
            "reason": "Avoid trading in the first 15 minutes after open or last 30 minutes before close.",
            "trades": []
        }

    top_trades = []
    
    for sym in symbols:
        try:
            df_5m = fetch_intraday_data(sym, interval="5m", period="5d")
            if df_5m.empty: continue
            df_5m = clean_data(df_5m)
            
            df_15m = fetch_intraday_data(sym, interval="15m", period="5d")
            if not df_15m.empty: df_15m = clean_data(df_15m)
            
            df_daily = fetch_daily_data(sym, period="3mo")
            if not df_daily.empty: df_daily = clean_data(df_daily)

            signal = analyze_stock_for_beginner(sym, df_5m, df_15m, df_daily)
            if signal:
                top_trades.append(signal)
            
            # Don't spend too much time if we already have plenty (we only need 2 anyway)
            if len(top_trades) >= MAX_TRADES_PER_DAY * 3:
                break
                
        except Exception as e:
            logger.warning(f"Error scanning {sym} for beginners: {e}")

    # Sort by confidence descending
    top_trades.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Limit to max trades
    final_trades = top_trades[:MAX_TRADES_PER_DAY]
    
    if not final_trades:
        return {
            "status": "NO_TRADE",
            "message": "NO SAFE TRADE TODAY",
            "reason": "No high-probability clear setups found in the scanned stocks.",
            "trades": []
        }

    return {
        "status": "SUCCESS",
        "message": f"Found {len(final_trades)} high-probability beginner trades.",
        "reason": market["reason"],
        "trades": final_trades
    }
