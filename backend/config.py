"""
Configuration for the AI Stock Market Scanner.
All settings are centralized here. Override with environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# ─── Database Fallback (SQLite for local dev) ─────────────────────────────────
USE_SQLITE = os.getenv("USE_SQLITE", "true").lower() == "true"
SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "scanner.db")

# ─── Market Universe ──────────────────────────────────────────────────────────
NSE_SYMBOL_LIST_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

# ─── Smart Filters ───────────────────────────────────────────────────────────
FILTER_MIN_VOLUME = 500_000       # average daily volume
FILTER_MIN_PRICE = 50             # ₹50 minimum price
FILTER_MIN_VOLATILITY = 0.015    # 1.5% daily volatility
FILTER_MIN_MARKET_CAP = 0        # 0 = no cap filter (yfinance market cap)

# ─── Technical Indicators ─────────────────────────────────────────────────────
MA_WINDOWS = [20, 50, 200]
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2
VOLATILITY_WINDOW = 20

# ─── AI Models ────────────────────────────────────────────────────────────────
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
PREDICTION_HORIZON = 1
TRAIN_TEST_SPLIT = 0.8
MIN_TRAINING_SAMPLES = 200

# ─── Opportunity Scoring Weights ──────────────────────────────────────────────
WEIGHT_AI_PREDICTION = 0.45
WEIGHT_MOMENTUM = 0.25
WEIGHT_BREAKOUT = 0.15
WEIGHT_VOLUME_SPIKE = 0.15

# ─── Meta-Strategy Default Weights ────────────────────────────────────────────
META_WEIGHT_ML = 0.25
META_WEIGHT_RL = 0.20
META_WEIGHT_MOMENTUM = 0.20
META_WEIGHT_MEAN_REVERSION = 0.10
META_WEIGHT_VOLUME = 0.15
META_WEIGHT_SENTIMENT = 0.10

# ─── RL Agent ─────────────────────────────────────────────────────────────────
RL_LEARNING_RATE = 0.1
RL_DISCOUNT_FACTOR = 0.95
RL_EPSILON = 0.1
RL_TRAIN_EPOCHS = 3

# ─── Risk Management ─────────────────────────────────────────────────────────
DEFAULT_CAPITAL = 1_000_000
RISK_PER_TRADE_PCT = 0.02
MAX_POSITIONS = 10
MAX_POSITION_SIZE_PCT = 0.10
STOP_LOSS_METHOD = "atr"
RISK_REWARD_RATIO = 2.0
TRAILING_STOP_TRIGGER_ATR = 1.5
TRAILING_STOP_DISTANCE_ATR = 1.0
VOLATILITY_SCALING = True
VOLATILITY_SCALE_BASE = 0.02
MAX_DAILY_LOSS_PCT = 0.03
MAX_SECTOR_POSITIONS = 3

# ─── Ranking ──────────────────────────────────────────────────────────────────
TOP_BUY_COUNT = 20
TOP_SELL_COUNT = 10
TOP_BREAKOUT_COUNT = 10
TOP_VOLUME_MOVERS_COUNT = 10

# ─── Scheduler ────────────────────────────────────────────────────────────────
SCAN_INTERVAL_MINUTES = 15
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

# ─── API ──────────────────────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = int(os.getenv("PORT", "8000"))
_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
CORS_ALLOW_ORIGIN_REGEX = os.getenv("CORS_ALLOW_ORIGIN_REGEX", r"https://.*\.vercel\.app")

# ─── Intraday Trading ──────────────────────────────────────────────────────────
INTRADAY_INTERVALS = ["5m", "15m"]         # candle intervals to fetch
INTRADAY_LOOKBACK = "5d"                    # yfinance period for intraday data
INTRADAY_HORIZONS = ["15m", "30m", "1h"]    # prediction forward horizons
INTRADAY_MIN_CONFIDENCE = 0.30              # minimum confidence to surface a signal
INTRADAY_BUY_THRESHOLD = 0.62              # probability ≥ this → BUY
INTRADAY_SELL_THRESHOLD = 0.38             # probability ≤ this → SELL
INTRADAY_STOP_ATR_MULT = 1.5               # stop-loss = price ± ATR × this
INTRADAY_TARGET_ATR_MULT = 2.5             # target   = price ± ATR × this
INTRADAY_SCAN_BATCH_SIZE = 15              # stocks per batch during intraday scan
INTRADAY_TRAIN_SAMPLE = 30                 # # stocks sampled for model training

# ─── Data ──────────────────────────────────────────────────────────────────────
DATA_LOOKBACK_DAYS = 365
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# ─── Major NSE Stock Symbols (fallback if download fails) ─────────────────────
FALLBACK_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "AXISBANK",
    "WIPRO", "ASIANPAINT", "MARUTI", "TITAN", "SUNPHARMA", "NESTLEIND",
    "ULTRACEMCO", "BAJFINANCE", "BAJAJFINSV", "HCLTECH", "TECHM",
    "POWERGRID", "NTPC", "ONGC", "TATAMOTORS", "ADANIENT", "ADANIPORTS",
    "JSWSTEEL", "TATASTEEL", "HINDALCO", "COALINDIA", "GRASIM",
    "CIPLA", "DRREDDY", "DIVISLAB", "EICHERMOT", "HEROMOTOCO",
    "BAJAJ-AUTO", "M&M", "BPCL", "IOC", "INDUSINDBK", "HDFCLIFE",
    "SBILIFE", "BRITANNIA", "APOLLOHOSP", "TATACONSUM", "UPL",
    "DABUR", "PIDILITIND", "GODREJCP", "HAVELLS", "SIEMENS",
    "BERGEPAINT", "TORNTPHARM", "AUROPHARMA", "LUPIN", "BIOCON",
    "ACC", "AMBUJACEM", "SHREECEM", "DALBHARAT", "RAMCOCEM",
    "BANKBARODA", "PNB", "CANBK", "IDFCFIRSTB", "FEDERALBNK",
    "BANDHANBNK", "RBLBANK", "LICHSGFIN", "MANAPPURAM", "MUTHOOTFIN",
    "CHOLAFIN", "BAJAJHLDNG", "PGHH", "COLPAL", "MARICO",
    "TRENT", "PAGEIND", "JUBLFOOD", "MCDOWELL-N", "UBL",
    "ZOMATO", "NYKAA", "PAYTM", "POLICYBZR", "DELHIVERY",
    "IRCTC", "INDIANHOTEL", "LEMONTTREE", "TATAELXSI", "PERSISTENT",
    "COFORGE", "MPHASIS", "LTIM", "LTTS", "HAPPSTMNDS",
    "DEEPAKNI", "ATUL", "PIIND", "SRF", "AARTI",
    "TATAPOWER", "ADANIGREEN", "NHPC", "SJVN", "IREDA",
    "HAL", "BEL", "BDL", "MAZAGON", "COCHINSHIP",
    "SOLARINDS", "CUMMINSIND", "THERMAX", "GRINDWELL", "ELGIEQUIP",
    "DIXON", "VOLTAS", "PHOENIXLTD", "OBEROIRLTY", "GODREJPROP",
    "DLF", "PRESTIGE", "BRIGADE", "SOBHA", "SUNTV",
    "PVR", "ZEEL", "NETWORK18", "TV18BRDCST", "RECLTD",
    "PFC", "IRFC", "HUDCO", "CANFINHOME", "ABCAPITAL",
    "TATACHEM", "NAVINFLUOR", "CLEAN", "FLUOROCHEM", "ASTRAL",
    "POLYCAB", "KEI", "APLAPOLLO", "RATNAMANI", "SUPREMEIND",
    "LALPATHLAB", "METROPOLIS", "MAXHEALTH", "FORTIS", "MEDANTA",
    "DMART", "TATACOMM", "IDEA", "MTNL", "SAIL",
    "NMDC", "VEDL", "NATIONALUM", "HINDZINC", "MOIL",
    "GAIL", "MGL", "IGL", "GSPL", "PETRONET",
    "CONCOR", "CESC", "TATAPOWER", "TORNTPOWER", "NHPC",
]
