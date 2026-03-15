"""
Backtesting Engine Module
Simulates trading with position sizing, stop loss, take profit, and transaction costs.
"""
import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single trade."""
    ticker: str
    entry_date: str
    entry_price: float
    direction: int  # 1=long, -1=short
    shares: int
    exit_date: str = ""
    exit_price: float = 0.0
    pnl: float = 0.0
    return_pct: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestResult:
    """Container for backtesting results."""
    equity_curve: pd.Series = None
    trades: list = field(default_factory=list)
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_trade_return: float = 0.0
    max_consecutive_losses: int = 0

    def summary(self) -> dict:
        return {
            "Total Return": f"{self.total_return:.2%}",
            "Annualized Return": f"{self.annualized_return:.2%}",
            "Sharpe Ratio": f"{self.sharpe_ratio:.4f}",
            "Max Drawdown": f"{self.max_drawdown:.2%}",
            "Win Rate": f"{self.win_rate:.2%}",
            "Profit Factor": f"{self.profit_factor:.4f}",
            "Total Trades": self.total_trades,
            "Avg Trade Return": f"{self.avg_trade_return:.2%}",
            "Max Consecutive Losses": self.max_consecutive_losses,
        }


class BacktestEngine:
    """Event-driven backtesting engine with realistic trade simulation."""

    def __init__(
        self,
        initial_capital: float = config.INITIAL_CAPITAL,
        transaction_cost: float = config.TRANSACTION_COST_PCT,
        slippage: float = config.SLIPPAGE_PCT,
        stop_loss: float = config.STOP_LOSS_PCT,
        take_profit: float = config.TAKE_PROFIT_PCT,
        risk_per_trade: float = config.RISK_PER_TRADE_PCT,
    ):
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.slippage = slippage
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.risk_per_trade = risk_per_trade

    def run(self, df: pd.DataFrame, signals: pd.Series, ticker: str = "STOCK") -> BacktestResult:
        """
        Run a backtest on a single stock.

        Args:
            df: DataFrame with at least 'date', 'open', 'high', 'low', 'close' columns.
            signals: Series of signals (1=buy, -1=sell, 0=hold), aligned with df index.
            ticker: Stock ticker for labeling.

        Returns:
            BacktestResult with all performance metrics.
        """
        cash = self.initial_capital
        position = 0  # number of shares held
        entry_price = 0.0
        entry_date = ""
        trades = []
        equity = []

        for i in range(len(df)):
            date = df.iloc[i]["date"] if isinstance(df.iloc[i]["date"], str) else str(df.iloc[i]["date"])
            close = df.iloc[i]["close"]
            high = df.iloc[i]["high"]
            low = df.iloc[i]["low"]
            signal = signals.iloc[i] if i < len(signals) else 0

            # Check stop loss / take profit for open positions
            if position > 0:
                # Check stop loss
                if low <= entry_price * (1 - self.stop_loss):
                    exit_price = entry_price * (1 - self.stop_loss)
                    exit_price *= (1 - self.slippage)
                    pnl = (exit_price - entry_price) * position
                    cost = exit_price * position * self.transaction_cost
                    cash += exit_price * position - cost
                    trades.append(Trade(
                        ticker=ticker, entry_date=entry_date, entry_price=entry_price,
                        direction=1, shares=position, exit_date=date,
                        exit_price=exit_price, pnl=pnl - cost,
                        return_pct=(exit_price / entry_price) - 1,
                        exit_reason="stop_loss",
                    ))
                    position = 0

                # Check take profit
                elif high >= entry_price * (1 + self.take_profit):
                    exit_price = entry_price * (1 + self.take_profit)
                    exit_price *= (1 - self.slippage)
                    pnl = (exit_price - entry_price) * position
                    cost = exit_price * position * self.transaction_cost
                    cash += exit_price * position - cost
                    trades.append(Trade(
                        ticker=ticker, entry_date=entry_date, entry_price=entry_price,
                        direction=1, shares=position, exit_date=date,
                        exit_price=exit_price, pnl=pnl - cost,
                        return_pct=(exit_price / entry_price) - 1,
                        exit_reason="take_profit",
                    ))
                    position = 0

            # Process signals
            if signal == 1 and position == 0:
                # Buy signal
                risk_amount = cash * self.risk_per_trade
                adjusted_price = close * (1 + self.slippage)
                shares = int(risk_amount / (adjusted_price * self.stop_loss))
                shares = max(1, min(shares, int(cash / adjusted_price)))

                cost_total = adjusted_price * shares * (1 + self.transaction_cost)
                if cost_total <= cash:
                    cash -= cost_total
                    position = shares
                    entry_price = adjusted_price
                    entry_date = date

            elif signal == -1 and position > 0:
                # Sell signal
                exit_price = close * (1 - self.slippage)
                pnl = (exit_price - entry_price) * position
                cost = exit_price * position * self.transaction_cost
                cash += exit_price * position - cost
                trades.append(Trade(
                    ticker=ticker, entry_date=entry_date, entry_price=entry_price,
                    direction=1, shares=position, exit_date=date,
                    exit_price=exit_price, pnl=pnl - cost,
                    return_pct=(exit_price / entry_price) - 1,
                    exit_reason="signal",
                ))
                position = 0

            # Record equity
            portfolio_value = cash + (position * close)
            equity.append({"date": date, "equity": portfolio_value})

        # Close any remaining position at last close
        if position > 0:
            close = df.iloc[-1]["close"]
            date = str(df.iloc[-1]["date"])
            exit_price = close * (1 - self.slippage)
            pnl = (exit_price - entry_price) * position
            cost = exit_price * position * self.transaction_cost
            cash += exit_price * position - cost
            trades.append(Trade(
                ticker=ticker, entry_date=entry_date, entry_price=entry_price,
                direction=1, shares=position, exit_date=date,
                exit_price=exit_price, pnl=pnl - cost,
                return_pct=(exit_price / entry_price) - 1,
                exit_reason="end_of_test",
            ))

        # Build results
        equity_df = pd.DataFrame(equity)
        equity_series = equity_df.set_index("date")["equity"]

        result = BacktestResult()
        result.equity_curve = equity_series
        result.trades = trades
        result.total_trades = len(trades)

        if trades:
            returns = [t.return_pct for t in trades]
            result.total_return = (equity_series.iloc[-1] / self.initial_capital) - 1
            result.win_rate = sum(1 for r in returns if r > 0) / len(returns)
            result.avg_trade_return = np.mean(returns)

            # Profit factor
            gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
            gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
            result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

            # Max consecutive losses
            consecutive = 0
            max_consecutive = 0
            for r in returns:
                if r < 0:
                    consecutive += 1
                    max_consecutive = max(max_consecutive, consecutive)
                else:
                    consecutive = 0
            result.max_consecutive_losses = max_consecutive

        # Annualized return
        n_days = len(equity_series)
        if n_days > 1 and result.total_return > -1:
            result.annualized_return = (1 + result.total_return) ** (252 / n_days) - 1

        # Sharpe ratio (daily returns)
        daily_returns = equity_series.pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            result.sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)

        # Max drawdown
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        result.max_drawdown = drawdown.min()

        return result


def run_backtest(df: pd.DataFrame, signals: pd.Series, ticker: str = "STOCK", **kwargs) -> BacktestResult:
    """Convenience function to run a backtest."""
    engine = BacktestEngine(**kwargs)
    return engine.run(df, signals, ticker)


def compare_strategies(df: pd.DataFrame, strategy_signals: dict, ticker: str = "STOCK") -> pd.DataFrame:
    """
    Compare multiple strategies on the same data.

    Args:
        df: Stock data with OHLCV.
        strategy_signals: dict of {strategy_name: signals_series}.

    Returns:
        DataFrame comparing strategy performance.
    """
    results = []
    for name, signals in strategy_signals.items():
        bt = run_backtest(df, signals, ticker)
        summary = bt.summary()
        summary["Strategy"] = name
        results.append(summary)

    comparison = pd.DataFrame(results)
    comparison = comparison.set_index("Strategy")
    return comparison


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data_pipeline import load_data
    from feature_engineering import compute_all_features
    from strategy_engine import get_all_signals, MomentumStrategy, MACrossoverStrategy

    df = load_data("RELIANCE.NS")
    if not df.empty:
        featured = compute_all_features(df, add_targets=False)
        featured = featured.dropna().reset_index(drop=True)

        momentum = MomentumStrategy()
        ma_cross = MACrossoverStrategy()

        strat_signals = {
            "Momentum": momentum.generate_signals(featured),
            "MACrossover": ma_cross.generate_signals(featured),
        }

        comparison = compare_strategies(featured, strat_signals, "RELIANCE.NS")
        print("\n=== Strategy Comparison ===")
        print(comparison.to_string())
