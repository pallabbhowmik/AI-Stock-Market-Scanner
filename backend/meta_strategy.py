"""
Meta-AI Strategy Selector
Dynamically selects and weights the best trading strategy mix based on
current market regime, recent strategy performance, and market conditions.

Improvements:
  - Confidence-weighted consensus: weight by strategy's own confidence
  - Minimum agreement filter: require 3/6 strategies to agree for BUY/SELL
  - Regime-filtered signals: suppress bad signal types per regime
  - Performance decay: exponentially decay records older than 30 days
"""
import logging
import os
import json
from datetime import datetime
from typing import Optional
from collections import defaultdict

import numpy as np

from backend import config

logger = logging.getLogger(__name__)

# ─── Strategy Identifiers ────────────────────────────────────────────────────

STRATEGIES = [
    "ml_prediction",
    "rl_agent",
    "momentum_breakout",
    "mean_reversion",
    "volume_breakout",
    "sentiment",
]

# ─── Default Base Weights ─────────────────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "ml_prediction": 0.25,
    "rl_agent": 0.20,
    "momentum_breakout": 0.20,
    "mean_reversion": 0.10,
    "volume_breakout": 0.15,
    "sentiment": 0.10,
}

STRATEGY_LABELS = {
    "ml_prediction": "Machine Learning Model",
    "rl_agent": "Reinforcement Learning",
    "momentum_breakout": "Momentum Breakout",
    "mean_reversion": "Mean Reversion",
    "volume_breakout": "Volume Breakout",
    "sentiment": "Sentiment Signals",
}

PERFORMANCE_FILE = os.path.join(config.DATA_DIR, "strategy_performance.json")


# ─── Strategy Performance Tracking ──────────────────────────────────────────

class StrategyPerformanceTracker:
    """Tracks win rate, average return, Sharpe ratio, and max drawdown per strategy."""

    def __init__(self):
        self.records: dict[str, list[dict]] = {s: [] for s in STRATEGIES}
        self._load()

    def _load(self):
        """Load performance history from disk."""
        if os.path.exists(PERFORMANCE_FILE):
            try:
                with open(PERFORMANCE_FILE, "r") as f:
                    data = json.load(f)
                for s in STRATEGIES:
                    self.records[s] = data.get(s, [])
            except Exception:
                logger.warning("Could not load strategy performance, starting fresh")

    def _save(self):
        """Persist performance history to disk."""
        os.makedirs(os.path.dirname(PERFORMANCE_FILE), exist_ok=True)
        # Keep only last 200 records per strategy
        trimmed = {s: recs[-200:] for s, recs in self.records.items()}
        with open(PERFORMANCE_FILE, "w") as f:
            json.dump(trimmed, f)

    def record_outcome(self, strategy: str, symbol: str, signal: str,
                       actual_return: float, date: str = ""):
        """Record the outcome of a strategy signal."""
        if strategy not in self.records:
            return

        won = (signal == "BUY" and actual_return > 0) or (signal == "SELL" and actual_return < 0)

        self.records[strategy].append({
            "symbol": symbol,
            "signal": signal,
            "actual_return": round(actual_return, 6),
            "won": won,
            "date": date or datetime.now().strftime("%Y-%m-%d"),
        })
        self._save()

    def get_metrics(self, strategy: str, lookback: int = 50) -> dict:
        """
        Compute performance metrics for a strategy over recent trades.
        Uses exponential decay: records older than 30 days get reduced weight.

        Returns:
            dict with: win_rate, avg_return, sharpe_ratio, max_drawdown, trade_count
        """
        recs = self.records.get(strategy, [])[-lookback:]

        if not recs:
            return {
                "win_rate": 0.5,
                "avg_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "trade_count": 0,
            }

        # Apply exponential decay based on age
        from datetime import datetime, timedelta
        today = datetime.now()
        weighted_returns = []
        weighted_wins = []
        total_weight = 0

        for r in recs:
            try:
                rec_date = datetime.strptime(r.get("date", ""), "%Y-%m-%d")
                age_days = (today - rec_date).days
            except (ValueError, TypeError):
                age_days = 15  # default
            # Half-life of 30 days
            decay = 0.5 ** (age_days / 30.0)
            decay = max(decay, 0.1)  # floor at 10%

            weighted_returns.append(r["actual_return"] * decay)
            weighted_wins.append(decay if r["won"] else 0)
            total_weight += decay

        if total_weight == 0:
            total_weight = 1

        avg_ret = sum(weighted_returns) / total_weight
        win_rate = sum(weighted_wins) / total_weight

        returns = [r["actual_return"] for r in recs]
        std_ret = float(np.std(returns)) if len(returns) > 1 else 1.0
        sharpe = avg_ret / std_ret if std_ret > 0 else 0.0

        # Max drawdown from cumulative returns
        cum = np.cumsum(returns)
        peak = np.maximum.accumulate(cum)
        drawdowns = peak - cum
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        return {
            "win_rate": round(win_rate, 4),
            "avg_return": round(avg_ret, 6),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 6),
            "trade_count": len(recs),
        }

    def get_all_metrics(self, lookback: int = 50) -> dict[str, dict]:
        """Get metrics for all strategies."""
        return {s: self.get_metrics(s, lookback) for s in STRATEGIES}


# ─── Module-level tracker instance ──────────────────────────────────────────

_tracker: Optional[StrategyPerformanceTracker] = None


def get_tracker() -> StrategyPerformanceTracker:
    global _tracker
    if _tracker is None:
        _tracker = StrategyPerformanceTracker()
    return _tracker


# ─── Weight Computation ─────────────────────────────────────────────────────

def compute_dynamic_weights(
    regime: str = "SIDEWAYS",
    performance_metrics: Optional[dict[str, dict]] = None,
) -> dict[str, float]:
    """
    Compute dynamic strategy weights based on:
    1. Base weights (prior)
    2. Market regime bias
    3. Recent strategy performance (Sharpe-based adjustment)

    Returns:
        dict mapping strategy name → weight (sums to 1.0)
    """
    # Start with base weights
    weights = dict(DEFAULT_WEIGHTS)

    # ── Step 1: Market Regime Adjustment ──────────────────────────────────
    from backend.market_regime import get_regime_strategy_bias
    regime_bias = get_regime_strategy_bias(regime)

    for strategy, bias in regime_bias.items():
        if strategy in weights:
            weights[strategy] = max(weights[strategy] + bias, 0.02)

    # ── Step 2: Performance-Based Adjustment ─────────────────────────────
    if performance_metrics:
        sharpe_scores = {}
        for s in STRATEGIES:
            m = performance_metrics.get(s, {})
            # Combine Sharpe with win rate for robustness
            sharpe = m.get("sharpe_ratio", 0)
            win_rate = m.get("win_rate", 0.5)
            count = m.get("trade_count", 0)

            if count >= 5:
                # Strategies with track record get adjusted
                perf_score = sharpe * 0.6 + (win_rate - 0.5) * 2 * 0.4
                sharpe_scores[s] = perf_score
            else:
                sharpe_scores[s] = 0  # no adjustment for untested strategies

        # Adjust weights based on relative performance
        if sharpe_scores:
            max_score = max(sharpe_scores.values())
            min_score = min(sharpe_scores.values())
            score_range = max_score - min_score

            if score_range > 0.01:
                for s in STRATEGIES:
                    normalized = (sharpe_scores[s] - min_score) / score_range
                    # Shift weight by up to ±0.10 based on performance
                    adjustment = (normalized - 0.5) * 0.20
                    weights[s] = max(weights[s] + adjustment, 0.02)

    # ── Step 3: Normalize to sum to 1.0 ──────────────────────────────────
    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}

    return weights


# ─── Signal Combination ─────────────────────────────────────────────────────

def compute_meta_signal(
    symbol: str,
    strategy_signals: dict[str, dict],
    weights: dict[str, float],
    regime: str = "SIDEWAYS",
) -> dict:
    """
    Combine signals from all strategies into a final weighted signal.

    Improvements:
    - Confidence-weighted: each strategy's contribution is scaled by its own confidence
    - Minimum agreement filter: require ≥3 strategies to agree for BUY/SELL
    - Regime filtering: suppress contradictory signals per regime
    """
    weighted_score = 0.0
    total_weight = 0.0
    contributions = {}

    for strategy in STRATEGIES:
        sig = strategy_signals.get(strategy, {})
        weight = weights.get(strategy, 0)
        score = sig.get("score", 0.5)
        sig_confidence = sig.get("confidence", 0.5)

        # Confidence-weighted: scale contribution by strategy's own confidence
        effective_weight = weight * (0.5 + sig_confidence * 0.5)
        contribution = effective_weight * score
        weighted_score += contribution
        total_weight += effective_weight

        contributions[strategy] = {
            "weight_pct": round(weight * 100, 1),
            "score": round(score, 4),
            "contribution": round(contribution, 4),
            "signal": sig.get("signal", "HOLD"),
            "confidence": round(sig_confidence, 4),
            "label": STRATEGY_LABELS.get(strategy, strategy),
        }

    final_score = weighted_score / total_weight if total_weight > 0 else 0.5

    # ── Minimum Agreement Filter ──
    signals = [s.get("signal", "HOLD") for s in strategy_signals.values() if s]
    buy_count = signals.count("BUY")
    sell_count = signals.count("SELL")
    hold_count = signals.count("HOLD")
    total_strategies = len(signals)
    min_agreement = 3  # Require at least 3/6 strategies to agree

    # Initial signal from score
    if final_score >= 0.60:
        raw_signal = "BUY"
    elif final_score <= 0.40:
        raw_signal = "SELL"
    else:
        raw_signal = "HOLD"

    # Override to HOLD if not enough strategies agree
    if raw_signal == "BUY" and buy_count < min_agreement:
        raw_signal = "HOLD"
    elif raw_signal == "SELL" and sell_count < min_agreement:
        raw_signal = "HOLD"

    # ── Regime Filtering ──
    # Suppress contradictory signals based on market regime
    final_signal = raw_signal
    if regime == "BEAR" and final_signal == "BUY" and final_score < 0.70:
        # In bear markets, require very strong conviction for buy
        final_signal = "HOLD"
    elif regime == "BULL" and final_signal == "SELL" and final_score > 0.30:
        # In bull markets, require very strong conviction for sell
        final_signal = "HOLD"

    # Confidence from agreement
    agreement = max(buy_count, sell_count, hold_count) / max(total_strategies, 1)
    confidence = round(agreement * min(abs(final_score - 0.5) * 4, 1.0), 4)

    # Beginner-friendly explanation
    explanation = _generate_meta_explanation(final_signal, final_score, contributions, weights)

    return {
        "symbol": symbol,
        "final_signal": final_signal,
        "final_score": round(final_score, 4),
        "confidence": confidence,
        "strategy_contributions": contributions,
        "explanation": explanation,
        "agreement": {"buy": buy_count, "sell": sell_count, "hold": hold_count},
    }


def _generate_meta_explanation(
    signal: str,
    score: float,
    contributions: dict,
    weights: dict,
) -> str:
    """Generate a beginner-friendly explanation of the meta-strategy decision."""
    # Find the top contributing strategy
    top_strategy = max(contributions, key=lambda s: contributions[s]["contribution"])
    top_label = contributions[top_strategy]["label"]
    top_weight = contributions[top_strategy]["weight_pct"]

    parts = []

    if signal == "BUY":
        parts.append(f"The system is recommending BUY because multiple strategies agree on upward potential")
    elif signal == "SELL":
        parts.append(f"The system is recommending SELL as strategies detect downside risk")
    else:
        parts.append(f"The signal is HOLD due to mixed signals across strategies")

    parts.append(f"The strongest influence is {top_label} ({top_weight}% weight)")

    # Count agreeing strategies
    buy_count = sum(1 for c in contributions.values() if c["signal"] == "BUY")
    sell_count = sum(1 for c in contributions.values() if c["signal"] == "SELL")
    total = len(contributions)

    if buy_count > total / 2:
        parts.append(f"{buy_count} of {total} strategies are bullish")
    elif sell_count > total / 2:
        parts.append(f"{sell_count} of {total} strategies are bearish")

    return ". ".join(parts) + "."


# ─── Strategy Signal Extraction ─────────────────────────────────────────────

def extract_strategy_signals(
    df,
    ml_prediction: dict,
    rl_prediction: dict,
    momentum_score: float,
    breakout_result: dict,
    volume_spike_score: float,
    sentiment_result: dict,
) -> dict[str, dict]:
    """
    Extract normalized signals from all strategy modules.

    Each strategy returns: {signal: BUY/SELL/HOLD, score: 0-1, confidence: 0-1}
    """
    signals = {}

    # 1. ML Prediction
    ai_prob = ml_prediction.get("ai_probability", 0.5)
    signals["ml_prediction"] = {
        "signal": ml_prediction.get("signal", "HOLD"),
        "score": ai_prob,
        "confidence": ml_prediction.get("confidence", 0),
    }

    # 2. RL Agent
    signals["rl_agent"] = {
        "signal": rl_prediction.get("signal", "HOLD"),
        "score": rl_prediction.get("rl_score", 0.5),
        "confidence": rl_prediction.get("confidence", 0),
    }

    # 3. Momentum / Breakout
    breakout_score = breakout_result.get("score", 0)
    combined_momentum = (momentum_score * 0.6 + breakout_score * 0.4)
    mom_signal = "BUY" if combined_momentum > 0.6 else ("SELL" if combined_momentum < 0.3 else "HOLD")
    signals["momentum_breakout"] = {
        "signal": mom_signal,
        "score": combined_momentum,
        "confidence": min(abs(combined_momentum - 0.5) * 3, 1.0),
    }

    # 4. Mean Reversion (RSI + Bollinger)
    if df is not None and not df.empty:
        latest = df.iloc[-1]
        rsi = latest.get("rsi", 50)
        bb_pct = latest.get("bb_pct", 0.5)

        # Oversold + near lower BB = buy signal for mean reversion
        mr_score = 0.5
        if rsi < 30 and bb_pct < 0.2:
            mr_score = 0.80
        elif rsi < 40 and bb_pct < 0.3:
            mr_score = 0.65
        elif rsi > 70 and bb_pct > 0.8:
            mr_score = 0.20
        elif rsi > 60 and bb_pct > 0.7:
            mr_score = 0.35

        mr_signal = "BUY" if mr_score > 0.6 else ("SELL" if mr_score < 0.4 else "HOLD")
        signals["mean_reversion"] = {
            "signal": mr_signal,
            "score": round(mr_score, 4),
            "confidence": round(abs(mr_score - 0.5) * 2, 4),
        }
    else:
        signals["mean_reversion"] = {"signal": "HOLD", "score": 0.5, "confidence": 0.0}

    # 5. Volume Breakout
    vol_signal = "BUY" if volume_spike_score > 0.7 else ("SELL" if volume_spike_score < 0.2 else "HOLD")
    signals["volume_breakout"] = {
        "signal": vol_signal,
        "score": volume_spike_score,
        "confidence": min(abs(volume_spike_score - 0.5) * 3, 1.0),
    }

    # 6. Sentiment
    sent_score = sentiment_result.get("sentiment_score", 0)
    sent_norm = round(0.5 + sent_score * 0.5, 4)  # map [-1,1] → [0,1]
    sent_signal_raw = sentiment_result.get("signal", "NEUTRAL")
    sent_signal = "BUY" if sent_signal_raw == "BULLISH" else ("SELL" if sent_signal_raw == "BEARISH" else "HOLD")
    signals["sentiment"] = {
        "signal": sent_signal,
        "score": sent_norm,
        "confidence": round(abs(sent_score), 4),
    }

    return signals


# ─── Full Meta-Strategy Pipeline ────────────────────────────────────────────

def run_meta_strategy(
    symbol: str,
    df,
    ml_prediction: dict,
    rl_prediction: dict,
    momentum_score: float,
    breakout_result: dict,
    volume_spike_score: float,
    sentiment_result: dict,
    regime: str = "SIDEWAYS",
    performance_metrics: Optional[dict] = None,
) -> dict:
    """
    Full meta-strategy pipeline for a single stock:
    1. Extract signals from all strategies
    2. Compute dynamic weights (regime + performance)
    3. Combine into a final weighted signal

    Returns:
        dict with: final_signal, final_score, confidence, weights, contributions, explanation
    """
    # Get performance metrics if not provided
    if performance_metrics is None:
        tracker = get_tracker()
        performance_metrics = tracker.get_all_metrics()

    # Compute dynamic weights
    weights = compute_dynamic_weights(regime, performance_metrics)

    # Extract signals
    strategy_signals = extract_strategy_signals(
        df, ml_prediction, rl_prediction,
        momentum_score, breakout_result,
        volume_spike_score, sentiment_result,
    )

    # Combine with regime awareness
    result = compute_meta_signal(symbol, strategy_signals, weights, regime=regime)
    result["active_weights"] = weights
    result["regime"] = regime

    return result


def get_strategy_status(regime: str = "SIDEWAYS") -> dict:
    """
    Get current strategy status for dashboard display.
    Shows active weights, performance, and regime info.
    """
    tracker = get_tracker()
    performance = tracker.get_all_metrics()
    weights = compute_dynamic_weights(regime, performance)

    strategies = []
    for s in STRATEGIES:
        perf = performance.get(s, {})
        strategies.append({
            "id": s,
            "label": STRATEGY_LABELS[s],
            "weight_pct": round(weights[s] * 100, 1),
            "win_rate": round(perf.get("win_rate", 0.5) * 100, 1),
            "avg_return_pct": round(perf.get("avg_return", 0) * 100, 4),
            "sharpe_ratio": perf.get("sharpe_ratio", 0),
            "trade_count": perf.get("trade_count", 0),
        })

    # Sort by weight descending
    strategies.sort(key=lambda x: x["weight_pct"], reverse=True)

    # Beginner explanation
    top = strategies[0]
    regime_label = {"BULL": "trending upward", "BEAR": "trending downward", "SIDEWAYS": "range-bound"}.get(regime, "uncertain")

    explanation = (
        f"The system is currently prioritizing {top['label']} ({top['weight_pct']}%) "
        f"because the market is {regime_label}."
    )

    return {
        "regime": regime,
        "strategies": strategies,
        "explanation": explanation,
        "last_updated": datetime.now().isoformat(),
    }
