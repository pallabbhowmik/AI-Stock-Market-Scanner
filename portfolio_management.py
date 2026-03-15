"""
Portfolio Management Module
Handles position sizing, risk management, and multi-stock diversification.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

import config

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position."""
    ticker: str
    shares: int
    entry_price: float
    entry_date: str
    current_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.shares * self.entry_price

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def return_pct(self) -> float:
        if self.entry_price == 0:
            return 0
        return (self.current_price / self.entry_price) - 1


class PortfolioManager:
    """Manages a multi-stock portfolio with risk controls."""

    def __init__(
        self,
        capital: float = config.INITIAL_CAPITAL,
        risk_per_trade: float = config.RISK_PER_TRADE_PCT,
        max_positions: int = config.MAX_POSITIONS,
        max_allocation: float = config.MAX_ALLOCATION_PER_STOCK,
    ):
        self.initial_capital = capital
        self.cash = capital
        self.risk_per_trade = risk_per_trade
        self.max_positions = max_positions
        self.max_allocation = max_allocation
        self.positions: dict[str, Position] = {}
        self.closed_trades: list = []
        self.equity_history: list = []

    @property
    def total_equity(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    @property
    def invested_pct(self) -> float:
        if self.total_equity == 0:
            return 0
        return sum(p.market_value for p in self.positions.values()) / self.total_equity

    def calculate_position_size(
        self, price: float, stop_loss_pct: float = config.STOP_LOSS_PCT
    ) -> int:
        """
        Calculate position size based on risk-per-trade and stop loss distance.
        Uses the formula: shares = (capital * risk%) / (price * stop_loss%)
        """
        equity = self.total_equity
        risk_amount = equity * self.risk_per_trade
        stop_distance = price * stop_loss_pct

        if stop_distance <= 0:
            return 0

        shares = int(risk_amount / stop_distance)

        # Enforce max allocation per stock
        max_shares_by_allocation = int((equity * self.max_allocation) / price)
        shares = min(shares, max_shares_by_allocation)

        # Can't spend more cash than available
        max_shares_by_cash = int(self.cash / (price * (1 + config.TRANSACTION_COST_PCT)))
        shares = min(shares, max_shares_by_cash)

        return max(0, shares)

    def can_open_position(self, ticker: str) -> bool:
        """Check if we can open a new position."""
        if ticker in self.positions:
            return False
        if len(self.positions) >= self.max_positions:
            return False
        return True

    def open_position(self, ticker: str, price: float, date: str) -> Optional[Position]:
        """Open a new position if risk limits allow."""
        if not self.can_open_position(ticker):
            logger.info("Cannot open position for %s (limit reached or already held)", ticker)
            return None

        shares = self.calculate_position_size(price)
        if shares <= 0:
            logger.info("Position size is 0 for %s at %.2f", ticker, price)
            return None

        cost = shares * price * (1 + config.TRANSACTION_COST_PCT)
        if cost > self.cash:
            return None

        self.cash -= cost
        pos = Position(
            ticker=ticker,
            shares=shares,
            entry_price=price,
            entry_date=date,
            current_price=price,
            stop_loss_price=price * (1 - config.STOP_LOSS_PCT),
            take_profit_price=price * (1 + config.TAKE_PROFIT_PCT),
        )
        self.positions[ticker] = pos
        logger.info("Opened %d shares of %s at %.2f", shares, ticker, price)
        return pos

    def close_position(self, ticker: str, price: float, date: str, reason: str = "signal") -> Optional[dict]:
        """Close an existing position."""
        if ticker not in self.positions:
            return None

        pos = self.positions[ticker]
        proceeds = pos.shares * price * (1 - config.TRANSACTION_COST_PCT)
        self.cash += proceeds
        pnl = proceeds - pos.cost_basis

        trade_record = {
            "ticker": ticker,
            "entry_date": pos.entry_date,
            "exit_date": date,
            "entry_price": pos.entry_price,
            "exit_price": price,
            "shares": pos.shares,
            "pnl": pnl,
            "return_pct": (price / pos.entry_price) - 1,
            "reason": reason,
        }
        self.closed_trades.append(trade_record)
        del self.positions[ticker]
        logger.info("Closed %s at %.2f, PnL: %.2f (%s)", ticker, price, pnl, reason)
        return trade_record

    def update_prices(self, current_prices: dict) -> list:
        """
        Update current prices and check stop loss / take profit for all positions.
        Returns list of tickers that were auto-closed.
        """
        auto_closed = []
        tickers = list(self.positions.keys())

        for ticker in tickers:
            if ticker not in current_prices:
                continue

            price = current_prices[ticker]
            pos = self.positions[ticker]
            pos.current_price = price

            # Check stop loss
            if price <= pos.stop_loss_price:
                self.close_position(ticker, pos.stop_loss_price, "auto", reason="stop_loss")
                auto_closed.append(ticker)
            # Check take profit
            elif price >= pos.take_profit_price:
                self.close_position(ticker, pos.take_profit_price, "auto", reason="take_profit")
                auto_closed.append(ticker)

        # Record equity snapshot
        self.equity_history.append(self.total_equity)
        return auto_closed

    def get_portfolio_summary(self) -> dict:
        """Get a summary of current portfolio state."""
        positions_summary = []
        for ticker, pos in self.positions.items():
            positions_summary.append({
                "ticker": ticker,
                "shares": pos.shares,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "pnl": pos.unrealized_pnl,
                "return_pct": pos.return_pct,
            })

        return {
            "cash": self.cash,
            "total_equity": self.total_equity,
            "invested_pct": self.invested_pct,
            "num_positions": len(self.positions),
            "positions": positions_summary,
            "total_return": (self.total_equity / self.initial_capital) - 1,
            "closed_trades": len(self.closed_trades),
        }

    def get_performance_metrics(self) -> dict:
        """Compute portfolio-level performance metrics from closed trades."""
        if not self.closed_trades:
            return {"message": "No closed trades yet"}

        returns = [t["return_pct"] for t in self.closed_trades]
        pnls = [t["pnl"] for t in self.closed_trades]

        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]

        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))

        # Equity curve metrics
        equity = np.array(self.equity_history) if self.equity_history else np.array([self.initial_capital])
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak

        return {
            "total_return": (self.total_equity / self.initial_capital) - 1,
            "total_trades": len(self.closed_trades),
            "win_rate": len(wins) / len(returns) if returns else 0,
            "avg_win": np.mean(wins) if wins else 0,
            "avg_loss": np.mean(losses) if losses else 0,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float("inf"),
            "max_drawdown": drawdown.min() if len(drawdown) > 0 else 0,
            "sharpe_ratio": _compute_sharpe(equity),
        }


def _compute_sharpe(equity: np.ndarray) -> float:
    """Compute annualized Sharpe ratio from equity curve."""
    if len(equity) < 2:
        return 0
    returns = np.diff(equity) / equity[:-1]
    if returns.std() == 0:
        return 0
    return (returns.mean() / returns.std()) * np.sqrt(252)


def run_portfolio_backtest(
    stock_data: dict, stock_signals: dict, capital: float = config.INITIAL_CAPITAL
) -> dict:
    """
    Run a multi-stock portfolio backtest.

    Args:
        stock_data: dict of {ticker: DataFrame} with OHLCV data.
        stock_signals: dict of {ticker: signals_series}.
        capital: Starting capital.

    Returns:
        Portfolio performance metrics and equity curve.
    """
    pm = PortfolioManager(capital=capital)

    # Collect all unique dates
    all_dates = set()
    for df in stock_data.values():
        all_dates.update(df["date"].dt.strftime("%Y-%m-%d").tolist())
    all_dates = sorted(all_dates)

    for date in all_dates:
        current_prices = {}
        for ticker, df in stock_data.items():
            row = df[df["date"].dt.strftime("%Y-%m-%d") == date]
            if not row.empty:
                current_prices[ticker] = row.iloc[0]["close"]

        # Update prices and check SL/TP
        pm.update_prices(current_prices)

        # Process signals
        for ticker, signals in stock_signals.items():
            df = stock_data[ticker]
            date_mask = df["date"].dt.strftime("%Y-%m-%d") == date
            if not date_mask.any():
                continue

            idx = df.index[date_mask][0]
            if idx >= len(signals):
                continue

            signal = signals.iloc[idx]
            price = current_prices.get(ticker, 0)

            if signal == 1 and price > 0:
                pm.open_position(ticker, price, date)
            elif signal == -1:
                pm.close_position(ticker, price, date)

    # Close remaining positions at last known prices
    for ticker in list(pm.positions.keys()):
        df = stock_data[ticker]
        last_price = df.iloc[-1]["close"]
        last_date = str(df.iloc[-1]["date"])
        pm.close_position(ticker, last_price, last_date, reason="end_of_test")

    return {
        "summary": pm.get_portfolio_summary(),
        "metrics": pm.get_performance_metrics(),
        "equity_history": pm.equity_history,
        "trades": pm.closed_trades,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pm = PortfolioManager()
    print("Portfolio Manager initialized")
    print(f"Capital: {pm.initial_capital:,.0f}")
    print(f"Max positions: {pm.max_positions}")
    print(f"Risk per trade: {pm.risk_per_trade:.1%}")
