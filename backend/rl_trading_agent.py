"""
Reinforcement Learning Trading Agent
Uses a tabular Q-learning approach to learn optimal trading actions
(BUY / SELL / HOLD) from discretized market state features.
"""
import logging
import os
import pickle
from collections import defaultdict
from typing import Optional

import numpy as np
import pandas as pd

from backend import config

logger = logging.getLogger(__name__)

# ─── State Discretization ────────────────────────────────────────────────────

def _discretize(value: float, bins: list[float]) -> int:
    """Map a continuous value into a discrete bin index."""
    for i, b in enumerate(bins):
        if value <= b:
            return i
    return len(bins)


RSI_BINS = [30, 45, 55, 70]          # oversold → neutral → overbought
MACD_BINS = [-0.02, -0.005, 0.005, 0.02]
TREND_BINS = [-0.03, -0.01, 0.01, 0.03]  # price vs SMA ratio
VOL_BINS = [0.5, 0.8, 1.2, 2.0]      # volume ratio bins

ACTIONS = ["BUY", "HOLD", "SELL"]
N_ACTIONS = len(ACTIONS)

RL_MODEL_PATH = os.path.join(config.MODEL_DIR, "rl_agent.pkl")


def _build_state(row: pd.Series) -> tuple:
    """Build a discretized state tuple from a feature row."""
    rsi = _discretize(row.get("rsi", 50), RSI_BINS)
    macd = _discretize(row.get("macd_histogram", 0), MACD_BINS)

    sma50 = row.get("sma_50", 0)
    price = row.get("close", 0)
    trend = _discretize(
        (price / sma50 - 1) if sma50 > 0 else 0,
        TREND_BINS,
    )
    vol = _discretize(row.get("volume_ratio", 1.0), VOL_BINS)

    return (rsi, macd, trend, vol)


class RLTradingAgent:
    """
    Tabular Q-learning trading agent.

    State: (RSI_bin, MACD_bin, Trend_bin, Volume_bin)
    Actions: BUY, HOLD, SELL
    Reward: next-day return (positive for correct direction, negative otherwise)
    """

    def __init__(
        self,
        alpha: float = 0.1,
        gamma: float = 0.95,
        epsilon: float = 0.1,
    ):
        self.alpha = alpha    # learning rate
        self.gamma = gamma    # discount factor
        self.epsilon = epsilon  # exploration rate
        self.q_table: dict[tuple, np.ndarray] = defaultdict(lambda: np.zeros(N_ACTIONS))
        self.training_episodes = 0

    def choose_action(self, state: tuple, explore: bool = False) -> int:
        """ε-greedy action selection."""
        if explore and np.random.random() < self.epsilon:
            return np.random.randint(N_ACTIONS)
        return int(np.argmax(self.q_table[state]))

    def update(self, state: tuple, action: int, reward: float, next_state: tuple):
        """Q-learning update."""
        best_next = np.max(self.q_table[next_state])
        td_target = reward + self.gamma * best_next
        td_error = td_target - self.q_table[state][action]
        self.q_table[state][action] += self.alpha * td_error

    def train(self, featured_data: dict[str, pd.DataFrame], epochs: int = 3):
        """
        Train the RL agent on historical data from multiple stocks.

        For each stock's history, simulate trading episodes:
        - BUY: reward = next-day return
        - SELL: reward = negative next-day return
        - HOLD: reward = small penalty for inaction when opportunity exists
        """
        total_steps = 0

        for epoch in range(epochs):
            for sym, df in featured_data.items():
                if len(df) < 50:
                    continue

                for i in range(len(df) - 2):
                    row = df.iloc[i]
                    next_row = df.iloc[i + 1]

                    state = _build_state(row)
                    next_state = _build_state(next_row)

                    # Calculate next-day return
                    ret = (next_row["close"] / row["close"] - 1) if row["close"] > 0 else 0

                    action = self.choose_action(state, explore=True)

                    # Reward shaping
                    if ACTIONS[action] == "BUY":
                        reward = ret * 100  # amplify for learning
                    elif ACTIONS[action] == "SELL":
                        reward = -ret * 100  # profit from falling prices
                    else:  # HOLD
                        reward = -abs(ret) * 20  # small penalty for missing moves

                    self.update(state, action, reward, next_state)
                    total_steps += 1

            # Decay exploration
            self.epsilon = max(self.epsilon * 0.95, 0.01)

        self.training_episodes += epochs
        logger.info("RL agent trained: %d epochs, %d steps, ε=%.3f",
                     epochs, total_steps, self.epsilon)

    def predict(self, df: pd.DataFrame) -> dict:
        """
        Get the RL agent's trading signal for the latest state.

        Returns:
            dict with: signal (BUY/SELL/HOLD), confidence, q_values, state
        """
        if df.empty:
            return {"signal": "HOLD", "confidence": 0.0, "rl_score": 0.5}

        latest = df.iloc[-1]
        state = _build_state(latest)
        q_vals = self.q_table[state].copy()

        action_idx = int(np.argmax(q_vals))
        signal = ACTIONS[action_idx]

        # Confidence from Q-value margin
        q_range = q_vals.max() - q_vals.min()
        confidence = min(q_range / 10.0, 1.0) if q_range > 0 else 0.0

        # RL score: 0-1 scale (0 = strong SELL, 1 = strong BUY)
        buy_q = q_vals[0]
        sell_q = q_vals[2]
        total = abs(buy_q) + abs(sell_q)
        rl_score = (buy_q / total + 1) / 2 if total > 0 else 0.5

        return {
            "signal": signal,
            "confidence": round(confidence, 4),
            "rl_score": round(rl_score, 4),
            "q_values": {a: round(float(q), 4) for a, q in zip(ACTIONS, q_vals)},
            "state": state,
        }

    def save(self, path: str = RL_MODEL_PATH):
        """Save the Q-table to disk."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "q_table": dict(self.q_table),
            "alpha": self.alpha,
            "gamma": self.gamma,
            "epsilon": self.epsilon,
            "training_episodes": self.training_episodes,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info("RL agent saved to %s (%d states)", path, len(self.q_table))

    @classmethod
    def load(cls, path: str = RL_MODEL_PATH) -> "RLTradingAgent":
        """Load a trained agent from disk."""
        if not os.path.exists(path):
            logger.info("No saved RL agent found, creating new one")
            return cls()

        with open(path, "rb") as f:
            data = pickle.load(f)

        agent = cls(
            alpha=data["alpha"],
            gamma=data["gamma"],
            epsilon=data["epsilon"],
        )
        agent.q_table = defaultdict(lambda: np.zeros(N_ACTIONS), data["q_table"])
        agent.training_episodes = data["training_episodes"]
        logger.info("RL agent loaded: %d states, %d episodes",
                     len(agent.q_table), agent.training_episodes)
        return agent


# ─── Module-level convenience functions ──────────────────────────────────────

_agent: Optional[RLTradingAgent] = None


def get_agent() -> RLTradingAgent:
    """Get or load the global RL agent."""
    global _agent
    if _agent is None:
        _agent = RLTradingAgent.load()
    return _agent


def train_rl_agent(featured_data: dict[str, pd.DataFrame], epochs: int = 3):
    """Train and save the global RL agent."""
    global _agent
    agent = get_agent()
    agent.train(featured_data, epochs=epochs)
    agent.save()
    _agent = agent


def predict_with_rl(df: pd.DataFrame) -> dict:
    """Get RL agent prediction for a stock."""
    agent = get_agent()
    return agent.predict(df)
