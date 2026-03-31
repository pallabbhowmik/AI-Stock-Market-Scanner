"""
Strategy Engine Module
Implements trading strategies and AI-optimized parameter selection.
"""
import logging

import numpy as np
import pandas as pd
from scipy.optimize import minimize

import config

logger = logging.getLogger(__name__)


class Strategy:
    """Base class for trading strategies."""

    def __init__(self, name: str):
        self.name = name

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Return a Series of signals: 1=buy, -1=sell, 0=hold."""
        raise NotImplementedError


class MomentumStrategy(Strategy):
    """Buy when price momentum is positive, sell when negative."""

    def __init__(self, lookback: int = config.MOMENTUM_LOOKBACK):
        super().__init__("Momentum")
        self.lookback = lookback

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        momentum = df["close"].pct_change(periods=self.lookback)
        signals = pd.Series(0, index=df.index)
        signals[momentum > 0] = 1
        signals[momentum < 0] = -1
        return signals


class MeanReversionStrategy(Strategy):
    """Buy when price is below mean, sell when above (z-score based)."""

    def __init__(
        self,
        lookback: int = config.MEAN_REVERSION_LOOKBACK,
        threshold: float = config.MEAN_REVERSION_THRESHOLD,
    ):
        super().__init__("MeanReversion")
        self.lookback = lookback
        self.threshold = threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        rolling_mean = df["close"].rolling(window=self.lookback).mean()
        rolling_std = df["close"].rolling(window=self.lookback).std()
        z_score = (df["close"] - rolling_mean) / rolling_std

        signals = pd.Series(0, index=df.index)
        signals[z_score < -self.threshold] = 1   # oversold → buy
        signals[z_score > self.threshold] = -1    # overbought → sell
        return signals


class MACrossoverStrategy(Strategy):
    """Buy when short MA crosses above long MA, sell on cross below."""

    def __init__(
        self,
        short_window: int = config.MA_CROSS_SHORT,
        long_window: int = config.MA_CROSS_LONG,
    ):
        super().__init__("MACrossover")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        short_ma = df["close"].rolling(window=self.short_window).mean()
        long_ma = df["close"].rolling(window=self.long_window).mean()

        signals = pd.Series(0, index=df.index)
        signals[short_ma > long_ma] = 1
        signals[short_ma <= long_ma] = -1

        # Only signal on crossover points
        signals = signals.diff().fillna(0)
        signals = signals.clip(-1, 1).astype(int)
        return signals


class RSIStrategy(Strategy):
    """Buy when RSI is oversold, sell when overbought."""

    def __init__(
        self,
        oversold: int = config.RSI_OVERSOLD,
        overbought: int = config.RSI_OVERBOUGHT,
    ):
        super().__init__("RSI")
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        if "rsi" not in df.columns:
            raise ValueError("RSI column not found. Run feature engineering first.")

        signals = pd.Series(0, index=df.index)
        signals[df["rsi"] < self.oversold] = 1    # oversold → buy
        signals[df["rsi"] > self.overbought] = -1  # overbought → sell
        return signals


class MLStrategy(Strategy):
    """Use ML model predictions as buy/sell signals."""

    def __init__(self, probabilities: np.ndarray, threshold: float = 0.5):
        super().__init__("ML")
        self.probabilities = probabilities
        self.threshold = threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        n = min(len(self.probabilities), len(df))
        # Align predictions to the end of the DataFrame (test set)
        offset = len(df) - n
        probs = self.probabilities[:n]
        signals.iloc[offset : offset + n] = np.where(probs >= self.threshold, 1, 0)
        return signals


class CombinedStrategy(Strategy):
    """Combine multiple strategies with weighted voting."""

    def __init__(self, strategies: list, weights: list = None):
        super().__init__("Combined")
        self.strategies = strategies
        if weights is None:
            weights = [1.0 / len(strategies)] * len(strategies)
        self.weights = weights

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        combined = pd.Series(0.0, index=df.index)
        for strategy, weight in zip(self.strategies, self.weights):
            signals = strategy.generate_signals(df)
            if config.LONG_ONLY:
                signals = signals.clip(lower=0)
            combined += signals * weight

        # Threshold the combined signal for fewer, higher-conviction entries.
        final = pd.Series(0, index=df.index)
        final[combined >= config.COMBINED_BUY_THRESHOLD] = 1
        if not config.LONG_ONLY:
            final[combined < -config.COMBINED_BUY_THRESHOLD] = -1
        return final


# ─── Strategy Optimizer ──────────────────────────────────────────────────────

def _strategy_objective(params, df, strategy_class, metric="sharpe"):
    """Objective function for strategy optimization (negative Sharpe for minimization)."""
    try:
        strategy = strategy_class(*params)
        signals = strategy.generate_signals(df)

        # Simple return calculation
        returns = df["close"].pct_change().fillna(0)
        strategy_returns = signals.shift(1).fillna(0) * returns

        if strategy_returns.std() == 0:
            return 0  # No trades

        sharpe = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)
        return -sharpe  # Minimize negative sharpe
    except Exception:
        return 0


def optimize_strategy(df: pd.DataFrame, strategy_class, param_bounds: list) -> dict:
    """Optimize strategy parameters using scipy minimize."""
    initial_params = [(b[0] + b[1]) / 2 for b in param_bounds]

    result = minimize(
        _strategy_objective,
        x0=initial_params,
        args=(df, strategy_class),
        bounds=param_bounds,
        method="L-BFGS-B",
    )

    optimal_params = result.x
    optimal_sharpe = -result.fun

    logger.info(
        "Optimized %s: params=%s, Sharpe=%.4f",
        strategy_class.__name__, optimal_params, optimal_sharpe,
    )
    return {
        "strategy": strategy_class.__name__,
        "params": optimal_params,
        "sharpe": optimal_sharpe,
    }


def get_all_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Generate signals from all built-in strategies and return as a DataFrame."""
    strategies = [
        MomentumStrategy(),
        MeanReversionStrategy(),
        MACrossoverStrategy(),
        RSIStrategy(),
    ]

    signal_df = pd.DataFrame(index=df.index)
    signal_df["date"] = df["date"]
    signal_df["close"] = df["close"]

    for strategy in strategies:
        try:
            strategy_signals = strategy.generate_signals(df)
            if config.LONG_ONLY:
                strategy_signals = strategy_signals.clip(lower=0)
            signal_df[strategy.name] = strategy_signals
        except Exception as e:
            logger.warning("Strategy %s failed: %s", strategy.name, e)
            signal_df[strategy.name] = 0

    # Supertrend signal (if available)
    if "supertrend_dir" in df.columns:
        signal_df["Supertrend"] = df["supertrend_dir"].fillna(0).astype(int)
        strategies.append(type("FakeStrategy", (), {"name": "Supertrend"})())

    # Overall consensus with a higher threshold to reduce false positives.
    strategy_cols = [s.name for s in strategies]
    signal_df["consensus"] = signal_df[strategy_cols].mean(axis=1)
    signal_df["signal"] = 0
    signal_df.loc[signal_df["consensus"] >= config.COMBINED_BUY_THRESHOLD, "signal"] = 1
    if not config.LONG_ONLY:
        signal_df.loc[signal_df["consensus"] <= -config.COMBINED_BUY_THRESHOLD, "signal"] = -1

    return signal_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data_pipeline import load_data
    from feature_engineering import compute_all_features

    df = load_data("RELIANCE.NS")
    if not df.empty:
        featured = compute_all_features(df, add_targets=False)
        signals = get_all_signals(featured)
        print(signals.tail(20))
