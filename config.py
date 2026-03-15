"""
Configuration for the AI Stock Trading System.
All tunable parameters are centralized here.
"""
import os

# ─── Stock Universe ───────────────────────────────────────────────────────────
STOCK_UNIVERSE = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "HINDUNILVR.NS",
    "ITC.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "KOTAKBANK.NS",
    "LT.NS",
    "AXISBANK.NS",
    "WIPRO.NS",
    "ASIANPAINT.NS",
    "MARUTI.NS",
]

# ─── Data Pipeline ────────────────────────────────────────────────────────────
DATA_START_DATE = "2018-01-01"
DATA_END_DATE = None  # None = today
DATA_INTERVAL = "1d"
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "stocks.db")

# ─── Feature Engineering ──────────────────────────────────────────────────────
MA_WINDOWS = [20, 50, 200]
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2
VOLATILITY_WINDOW = 20

# ─── Model Training ──────────────────────────────────────────────────────────
TRAIN_TEST_SPLIT = 0.8
PREDICTION_HORIZON = 1  # days ahead
WALK_FORWARD_TRAIN_SIZE = 252 * 2  # ~2 years
WALK_FORWARD_TEST_SIZE = 63  # ~3 months
LSTM_SEQUENCE_LENGTH = 30
LSTM_EPOCHS = 50
LSTM_BATCH_SIZE = 32
MODEL_SAVE_DIR = os.path.join(os.path.dirname(__file__), "models")

# ─── Strategy Engine ─────────────────────────────────────────────────────────
MOMENTUM_LOOKBACK = 20
MEAN_REVERSION_LOOKBACK = 20
MEAN_REVERSION_THRESHOLD = 1.5  # z-score
MA_CROSS_SHORT = 20
MA_CROSS_LONG = 50
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# ─── Backtesting ──────────────────────────────────────────────────────────────
INITIAL_CAPITAL = 1_000_000  # INR
TRANSACTION_COST_PCT = 0.001  # 0.1% (brokerage + taxes)
SLIPPAGE_PCT = 0.0005
STOP_LOSS_PCT = 0.03  # 3%
TAKE_PROFIT_PCT = 0.06  # 6%

# ─── Portfolio Management ─────────────────────────────────────────────────────
RISK_PER_TRADE_PCT = 0.02  # 2% max risk per trade
MAX_POSITIONS = 10
MAX_ALLOCATION_PER_STOCK = 0.20  # 20% max in single stock

# ─── Alert System ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
ALERT_CONFIDENCE_THRESHOLD = 0.65  # min probability to trigger alert

# ─── Dashboard ────────────────────────────────────────────────────────────────
DASHBOARD_PORT = 8501
