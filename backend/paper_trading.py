"""
Paper Trading Engine
Simulates trading with virtual money using AI signals.
Handles order execution, position tracking, portfolio management,
and performance analytics — all without risking real capital.

Safety: The system runs in PAPER TRADING mode by default.
"""
import json
import logging
import math
import threading
from datetime import datetime
from typing import Optional

from backend import config, database
from backend.data_pipeline import fetch_daily_data, clean_data

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

INITIAL_CAPITAL = 100_000.0   # ₹1,00,000 starting balance
BROKERAGE_PCT = 0.0003        # 0.03% brokerage per side (discount broker)
STT_PCT = 0.001               # 0.1% STT on sell side
GST_PCT = 0.18                # 18% GST on brokerage
STAMP_DUTY_PCT = 0.00015      # 0.015% stamp duty on buy side
SLIPPAGE_PCT = 0.001          # 0.1% simulated slippage
MODE = "PAPER"                # Always paper — safety default

_lock = threading.Lock()


# ─── Transaction Cost Model ─────────────────────────────────────────────────

def _compute_transaction_costs(price: float, qty: int, side: str) -> dict:
    """
    Compute realistic Indian equity transaction costs.
    Returns breakdown dict and total cost.
    """
    turnover = price * qty
    brokerage = turnover * BROKERAGE_PCT
    brokerage = min(brokerage, 20.0)  # ₹20 flat cap per order (discount broker)
    gst = brokerage * GST_PCT
    stt = turnover * STT_PCT if side == "SELL" else 0.0
    stamp = turnover * STAMP_DUTY_PCT if side == "BUY" else 0.0
    slippage = turnover * SLIPPAGE_PCT
    total = brokerage + gst + stt + stamp + slippage
    return {
        "brokerage": round(brokerage, 2),
        "gst": round(gst, 2),
        "stt": round(stt, 2),
        "stamp_duty": round(stamp, 2),
        "slippage": round(slippage, 2),
        "total": round(total, 2),
    }


# ─── Portfolio State ─────────────────────────────────────────────────────────

def _load_portfolio() -> dict:
    """Load portfolio state from DB, or create fresh one."""
    state = database.get_paper_portfolio()
    if state:
        return state
    # Fresh portfolio
    port = {
        "cash": INITIAL_CAPITAL,
        "initial_capital": INITIAL_CAPITAL,
        "positions": {},     # {symbol: {qty, avg_price, opened_at}}
        "created_at": datetime.now().isoformat(),
    }
    database.save_paper_portfolio(port)
    return port


def _save_portfolio(port: dict):
    database.save_paper_portfolio(port)


# ─── Live Price Helper ───────────────────────────────────────────────────────

def _get_live_price(symbol: str) -> Optional[float]:
    """Get the latest available price for a symbol."""
    df = database.get_stock_data(symbol, limit=5)
    if not df.empty:
        return float(df["close"].iloc[-1])
    # Fallback: fetch live
    df = fetch_daily_data(symbol, period="5d")
    if not df.empty:
        df = clean_data(df)
        return float(df["close"].iloc[-1])
    return None


# ─── Order Execution ─────────────────────────────────────────────────────────

def execute_order(
    symbol: str,
    side: str,
    order_type: str = "MARKET",
    quantity: int = 0,
    limit_price: float = 0.0,
    stop_price: float = 0.0,
    take_profit_price: float = 0.0,
) -> dict:
    """
    Execute a simulated order.

    Args:
        symbol: NSE stock symbol
        side: "BUY" or "SELL"
        order_type: "MARKET", "LIMIT", "STOP_LOSS", "TAKE_PROFIT"
        quantity: number of shares (0 = auto-size using risk rules)
        limit_price: price for LIMIT orders
        stop_price: trigger price for STOP_LOSS
        take_profit_price: target price for TAKE_PROFIT
    """
    side = side.upper()
    if side not in ("BUY", "SELL"):
        return {"status": "rejected", "reason": "Invalid side"}

    with _lock:
        port = _load_portfolio()
        market_price = _get_live_price(symbol)
        if market_price is None:
            return {"status": "rejected", "reason": f"No price data for {symbol}"}

        # Determine execution price based on order type
        exec_price = market_price
        if order_type == "LIMIT":
            if side == "BUY" and limit_price > 0 and limit_price < market_price:
                return {"status": "pending", "reason": "Limit price below market, order pending"}
            if side == "SELL" and limit_price > 0 and limit_price > market_price:
                return {"status": "pending", "reason": "Limit price above market, order pending"}
            exec_price = limit_price if limit_price > 0 else market_price

        elif order_type == "STOP_LOSS":
            if side == "SELL" and stop_price > 0 and market_price > stop_price:
                return {"status": "pending", "reason": "Stop not triggered yet"}
            exec_price = stop_price if stop_price > 0 else market_price

        elif order_type == "TAKE_PROFIT":
            if side == "SELL" and take_profit_price > 0 and market_price < take_profit_price:
                return {"status": "pending", "reason": "Take profit not reached yet"}
            exec_price = take_profit_price if take_profit_price > 0 else market_price

        # Apply slippage
        if side == "BUY":
            exec_price *= (1 + SLIPPAGE_PCT)
        else:
            exec_price *= (1 - SLIPPAGE_PCT)
        exec_price = round(exec_price, 2)

        # Auto-size if quantity not specified
        if quantity <= 0 and side == "BUY":
            risk_amount = port["cash"] * config.RISK_PER_TRADE_PCT
            max_position = port["cash"] * config.MAX_POSITION_SIZE_PCT
            use_amount = min(risk_amount * 10, max_position, port["cash"] * 0.95)
            quantity = max(1, int(use_amount / exec_price))

        if quantity <= 0:
            return {"status": "rejected", "reason": "Invalid quantity"}

        costs = _compute_transaction_costs(exec_price, quantity, side)
        order_value = exec_price * quantity

        # ── BUY ──
        if side == "BUY":
            total_cost = order_value + costs["total"]
            if total_cost > port["cash"]:
                # Reduce quantity to fit
                affordable = int((port["cash"] - costs["total"]) / exec_price)
                if affordable <= 0:
                    return {"status": "rejected", "reason": "Insufficient funds"}
                quantity = affordable
                order_value = exec_price * quantity
                costs = _compute_transaction_costs(exec_price, quantity, side)
                total_cost = order_value + costs["total"]

            port["cash"] -= total_cost

            pos = port["positions"].get(symbol)
            if pos:
                # Average up/down
                total_qty = pos["qty"] + quantity
                pos["avg_price"] = round(
                    (pos["avg_price"] * pos["qty"] + exec_price * quantity) / total_qty, 2
                )
                pos["qty"] = total_qty
            else:
                port["positions"][symbol] = {
                    "qty": quantity,
                    "avg_price": exec_price,
                    "opened_at": datetime.now().isoformat(),
                }

            _save_portfolio(port)

            trade = {
                "symbol": symbol,
                "side": "BUY",
                "order_type": order_type,
                "quantity": quantity,
                "price": exec_price,
                "value": round(order_value, 2),
                "costs": costs,
                "status": "filled",
                "timestamp": datetime.now().isoformat(),
                "mode": MODE,
            }
            database.save_paper_trade(trade)
            return trade

        # ── SELL ──
        pos = port["positions"].get(symbol)
        if not pos or pos["qty"] <= 0:
            return {"status": "rejected", "reason": f"No open position in {symbol}"}

        sell_qty = min(quantity, pos["qty"])
        costs = _compute_transaction_costs(exec_price, sell_qty, "SELL")
        proceeds = exec_price * sell_qty - costs["total"]

        pnl = round((exec_price - pos["avg_price"]) * sell_qty - costs["total"], 2)
        pnl_pct = round((exec_price / pos["avg_price"] - 1) * 100, 2) if pos["avg_price"] else 0

        port["cash"] += proceeds

        if sell_qty >= pos["qty"]:
            del port["positions"][symbol]
        else:
            pos["qty"] -= sell_qty

        _save_portfolio(port)

        trade = {
            "symbol": symbol,
            "side": "SELL",
            "order_type": order_type,
            "quantity": sell_qty,
            "price": exec_price,
            "value": round(exec_price * sell_qty, 2),
            "costs": costs,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "entry_price": pos["avg_price"],
            "status": "filled",
            "timestamp": datetime.now().isoformat(),
            "mode": MODE,
        }
        database.save_paper_trade(trade)
        return trade


# ─── Auto-Execute AI Signals ────────────────────────────────────────────────

def auto_execute_signals():
    """
    Read today's AI predictions and auto-execute paper trades:
    - BUY signals → open positions (if not already held)
    - SELL signals → close existing positions
    """
    preds = database.get_predictions()
    port = _load_portfolio()
    results = []

    for pred in preds:
        symbol = pred.get("symbol", "")
        signal = pred.get("signal", "HOLD")
        confidence = pred.get("confidence", 0)

        if signal == "BUY" and confidence >= 0.5:
            if symbol not in port["positions"]:
                # Check position limit
                if len(port["positions"]) >= config.MAX_POSITIONS:
                    continue
                res = execute_order(symbol, "BUY")
                results.append(res)
                port = _load_portfolio()  # reload after trade

        elif signal == "SELL":
            if symbol in port["positions"]:
                res = execute_order(symbol, "SELL", quantity=port["positions"][symbol]["qty"])
                results.append(res)
                port = _load_portfolio()

    logger.info("Auto-executed %d paper trades", len(results))
    return results


# ─── Portfolio Analytics ─────────────────────────────────────────────────────

def get_portfolio_summary() -> dict:
    """Return current portfolio state with live valuations."""
    port = _load_portfolio()
    positions = []
    total_invested = 0.0
    total_current = 0.0

    for symbol, pos in port["positions"].items():
        live_price = _get_live_price(symbol) or pos["avg_price"]
        market_value = live_price * pos["qty"]
        invested_value = pos["avg_price"] * pos["qty"]
        unrealised_pnl = round(market_value - invested_value, 2)
        unrealised_pct = round((live_price / pos["avg_price"] - 1) * 100, 2) if pos["avg_price"] else 0

        positions.append({
            "symbol": symbol,
            "qty": pos["qty"],
            "avg_price": pos["avg_price"],
            "live_price": round(live_price, 2),
            "invested": round(invested_value, 2),
            "current_value": round(market_value, 2),
            "unrealised_pnl": unrealised_pnl,
            "unrealised_pct": unrealised_pct,
            "opened_at": pos.get("opened_at", ""),
        })

        total_invested += invested_value
        total_current += market_value

    portfolio_value = port["cash"] + total_current
    total_return = portfolio_value - port["initial_capital"]
    total_return_pct = round((portfolio_value / port["initial_capital"] - 1) * 100, 2)

    return {
        "mode": MODE,
        "cash": round(port["cash"], 2),
        "initial_capital": port["initial_capital"],
        "invested": round(total_invested, 2),
        "current_value": round(total_current, 2),
        "portfolio_value": round(portfolio_value, 2),
        "total_return": round(total_return, 2),
        "total_return_pct": total_return_pct,
        "open_positions": len(positions),
        "positions": sorted(positions, key=lambda x: x["unrealised_pnl"], reverse=True),
    }


def get_performance_stats() -> dict:
    """Compute trading performance statistics from closed trades."""
    trades = database.get_paper_trades(limit=5000)
    sells = [t for t in trades if t.get("side") == "SELL" and t.get("pnl") is not None]

    if not sells:
        return {
            "total_trades": 0, "wins": 0, "losses": 0,
            "win_rate": 0, "avg_profit": 0, "avg_loss": 0,
            "total_pnl": 0, "max_drawdown": 0, "sharpe_ratio": 0,
            "profit_factor": 0, "best_trade": 0, "worst_trade": 0,
        }

    pnls = [t["pnl"] for t in sells]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_pnl = sum(pnls)
    win_rate = len(wins) / len(pnls) if pnls else 0

    avg_profit = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (10.0 if gross_profit > 0 else 0)

    # Sharpe from trade PnLs
    import numpy as np
    pnl_arr = np.array(pnls)
    sharpe = 0.0
    if len(pnl_arr) > 1 and pnl_arr.std() > 0:
        sharpe = round(float(pnl_arr.mean() / pnl_arr.std() * math.sqrt(252)), 2)

    # Max drawdown from cumulative PnL
    cum = np.cumsum(pnl_arr)
    running_max = np.maximum.accumulate(cum)
    drawdowns = cum - running_max
    max_dd = round(float(drawdowns.min()), 2) if len(drawdowns) > 0 else 0

    # Daily PnL series (for chart)
    daily_pnl = {}
    for t in sells:
        day = t.get("timestamp", "")[:10]
        if day:
            daily_pnl[day] = daily_pnl.get(day, 0) + t["pnl"]

    daily_series = [{"date": d, "pnl": round(v, 2)} for d, v in sorted(daily_pnl.items())]

    return {
        "total_trades": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 4),
        "avg_profit": round(avg_profit, 2),
        "avg_loss": round(avg_loss, 2),
        "total_pnl": round(total_pnl, 2),
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe,
        "profit_factor": profit_factor,
        "best_trade": round(max(pnls), 2) if pnls else 0,
        "worst_trade": round(min(pnls), 2) if pnls else 0,
        "daily_pnl": daily_series,
    }


def get_trade_history(limit: int = 50) -> list[dict]:
    """Return recent paper trades."""
    return database.get_paper_trades(limit=limit)


# ─── Reset ───────────────────────────────────────────────────────────────────

def reset_portfolio() -> dict:
    """Reset paper trading portfolio to initial state."""
    port = {
        "cash": INITIAL_CAPITAL,
        "initial_capital": INITIAL_CAPITAL,
        "positions": {},
        "created_at": datetime.now().isoformat(),
    }
    database.save_paper_portfolio(port)
    database.clear_paper_trades()
    return {"status": "reset", "cash": INITIAL_CAPITAL}
