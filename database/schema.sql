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
