-- Supabase PostgreSQL Schema for AI Stock Market Scanner
-- Run this in Supabase SQL Editor to create all required tables.

-- ─── Scanned Stocks ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scanned_stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    last_price NUMERIC,
    market_cap NUMERIC,
    avg_volume NUMERIC,
    daily_volatility NUMERIC,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- ─── OHLCV Data ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stock_data (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume BIGINT,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_stock_data_symbol ON stock_data(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_data_date ON stock_data(date);

-- ─── AI Predictions ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    signal TEXT CHECK (signal IN ('BUY', 'SELL', 'HOLD')),
    confidence NUMERIC,
    ai_probability NUMERIC,
    momentum_score NUMERIC,
    breakout_score NUMERIC,
    volume_spike_score NUMERIC,
    opportunity_score NUMERIC,
    explanation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON predictions(symbol);
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(date);
CREATE INDEX IF NOT EXISTS idx_predictions_score ON predictions(opportunity_score DESC);

-- ─── Watchlist ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchlist (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    category TEXT,
    symbol TEXT NOT NULL,
    signal TEXT,
    confidence NUMERIC,
    opportunity_score NUMERIC,
    explanation TEXT,
    rank INTEGER
);

CREATE INDEX IF NOT EXISTS idx_watchlist_date ON watchlist(date);
CREATE INDEX IF NOT EXISTS idx_watchlist_category ON watchlist(category);

-- ─── Scan Log ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scan_log (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    stocks_scanned INTEGER,
    stocks_passed_filter INTEGER,
    status TEXT
);

-- ─── Strategy Performance ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategy_performance (
    id BIGSERIAL PRIMARY KEY,
    strategy TEXT NOT NULL,
    symbol TEXT,
    signal TEXT,
    actual_return NUMERIC,
    won BOOLEAN,
    date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strat_perf_strategy ON strategy_performance(strategy);

-- ─── Meta Strategy State ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meta_strategy_state (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    regime TEXT,
    weights JSONB,
    explanation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Intraday Predictions ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS intraday_predictions (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    horizon TEXT NOT NULL,
    signal TEXT CHECK (signal IN ('BUY', 'SELL', 'HOLD')),
    confidence NUMERIC,
    probability NUMERIC,
    entry_price NUMERIC,
    stop_loss NUMERIC,
    target_price NUMERIC,
    risk_reward NUMERIC,
    model_votes JSONB,
    consensus_direction TEXT,
    consensus_agreement NUMERIC,
    explanation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intraday_symbol ON intraday_predictions(symbol);
CREATE INDEX IF NOT EXISTS idx_intraday_horizon ON intraday_predictions(horizon);
CREATE INDEX IF NOT EXISTS idx_intraday_created ON intraday_predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intraday_signal ON intraday_predictions(signal);

CREATE INDEX IF NOT EXISTS idx_meta_state_date ON meta_strategy_state(date);

-- ─── Training Log ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS training_log (
    id BIGSERIAL PRIMARY KEY,
    version_id TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    status TEXT,
    accuracy NUMERIC,
    auc NUMERIC,
    sharpe_ratio NUMERIC,
    max_drawdown NUMERIC,
    profit_factor NUMERIC,
    dataset_size INTEGER,
    stocks_trained INTEGER,
    duration_seconds NUMERIC,
    deployed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_log_date ON training_log(started_at);

-- ─── Paper Trading Portfolio ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS paper_portfolio (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Paper Trades ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS paper_trades (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT,
    quantity INTEGER,
    price NUMERIC,
    value NUMERIC,
    costs_json JSONB,
    pnl NUMERIC,
    pnl_pct NUMERIC,
    entry_price NUMERIC,
    status TEXT,
    mode TEXT DEFAULT 'PAPER',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trades_ts ON paper_trades(timestamp);

-- ─── Row Level Security (optional, for multi-user) ──────────────────────────
-- ALTER TABLE scanned_stocks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE watchlist ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scan_log ENABLE ROW LEVEL SECURITY;

-- Allow anonymous reads for all tables (public dashboard)
-- CREATE POLICY "Allow anonymous read" ON scanned_stocks FOR SELECT USING (true);
-- CREATE POLICY "Allow anonymous read" ON predictions FOR SELECT USING (true);
-- CREATE POLICY "Allow anonymous read" ON watchlist FOR SELECT USING (true);
-- CREATE POLICY "Allow anonymous read" ON scan_log FOR SELECT USING (true);
