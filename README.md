# AI Stock Market Scanner — Indian Market

AI-powered stock market scanning and prediction platform for the Indian stock market. Scans **2000+ NSE stocks**, applies smart filters, runs ML models, and generates a ranked watchlist — automatically every 15 minutes during market hours.

> **Disclaimer:** For personal educational/research use only. Not financial advice. Always do your own research.

---

## Features

- **Market Scanner** — Downloads full NSE equity list, scans 2000+ stocks automatically
- **Smart Filters** — Volume > 500K, Price > ₹50, Volatility > 1.5%
- **25+ Technical Indicators** — RSI, MACD, Bollinger Bands, SMA/EMA, ATR, OBV, Stochastic, etc.
- **AI Prediction Engine** — Ensemble of RandomForest + XGBoost + GradientBoosting
- **Breakout Detection** — Resistance breaks, volume surges, golden cross, momentum spikes
- **Meta-AI Strategy** — Blends ML, RL, Momentum, Mean Reversion, Volume, and Sentiment signals
- **Market Regime Detection** — Auto-identifies Bull / Bear / Sideways conditions
- **Sentiment Analysis** — News headline sentiment scoring per stock
- **Institutional Activity Detection** — Volume & price anomaly detection
- **Risk Management** — ATR-based stop loss, position sizing, risk/reward ratios
- **Portfolio Optimization** — Equal-weight, score-weighted, risk-parity, mean-variance methods
- **RL Trading Agent** — Tabular Q-learning agent that learns from market data
- **Automated Training Pipeline** — Daily model retraining with version management & rollback
- **Paper Trading** — Virtual portfolio (₹1,00,000) with realistic transaction costs
- **Auto Scheduler** — Scans every 15 min during IST market hours (9:15 AM – 3:30 PM)
- **FastAPI Backend** — REST API with 30+ endpoints
- **Next.js Frontend** — Dark-themed dashboard with charts, watchlist, paper trading, explorer
- **Dual Database** — Supabase PostgreSQL (production) or SQLite (local dev)

---

## Project Structure

```
StockPrediction/
├── backend/
│   ├── __init__.py
│   ├── config.py               # Configuration & stock universe
│   ├── database.py             # Supabase + SQLite dual-mode
│   ├── market_scanner.py       # NSE stock downloader & filters
│   ├── data_pipeline.py        # OHLCV data fetching
│   ├── feature_engineering.py  # 25+ technical indicators
│   ├── prediction_engine.py    # ML ensemble training & prediction
│   ├── breakout_detector.py    # Breakout pattern detection
│   ├── ranking_engine.py       # Opportunity scoring & ranking
│   ├── watchlist_generator.py  # Full & quick scan pipeline
│   ├── scheduler.py            # Auto-scan scheduler
│   ├── api_server.py           # FastAPI REST API
│   ├── sentiment_analysis.py   # News sentiment scoring
│   ├── institutional_activity.py # Institutional flow detection
│   ├── market_regime.py        # Bull/Bear/Sideways detection
│   ├── risk_management.py      # Stop loss & position sizing
│   ├── portfolio_optimizer.py  # Portfolio allocation methods
│   ├── rl_trading_agent.py     # Reinforcement learning agent
│   ├── meta_strategy.py        # Multi-strategy meta-AI blender
│   ├── model_versioning.py     # Model snapshot & rollback
│   ├── model_evaluation.py     # Backtest-based model scoring
│   ├── training_pipeline.py    # Automated retrain pipeline
│   └── paper_trading.py        # Paper trading engine
├── frontend/
│   ├── app/
│   │   ├── layout.tsx          # Root layout with navbar
│   │   ├── page.tsx            # Dashboard / Market Overview
│   │   ├── globals.css         # Styles
│   │   ├── watchlist/page.tsx  # AI-curated watchlist
│   │   ├── paper-trading/page.tsx # Paper trading simulator
│   │   ├── explorer/page.tsx   # Stock explorer with charts
│   │   ├── help/page.tsx       # How-to guide
│   │   └── login/page.tsx      # Login page
│   ├── lib/
│   │   ├── api.ts              # Backend API client + types
│   │   └── supabase.ts         # Supabase client
│   ├── package.json
│   ├── tailwind.config.js
│   └── tsconfig.json
├── database/
│   └── schema.sql              # Supabase PostgreSQL schema
├── data/                       # SQLite DB & cached data (gitignored)
├── models/                     # Trained model files (gitignored)
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
└── README.md
```

---

## Quick Start (Local Development)

### Prerequisites

- **Python 3.11+** (recommended: install via [uv](https://docs.astral.sh/uv/))
- **Node.js 18+** and **npm**
- **Git**

### 1. Clone & configure

```bash
git clone https://github.com/YOUR_USERNAME/StockPrediction.git
cd StockPrediction
cp .env.example .env
```

Edit `.env` — for local dev you can leave Supabase fields blank (SQLite is used by default).

### 2. Backend setup

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Start the API server
python -m backend.api_server
```

The FastAPI server starts at **http://localhost:8000**.
Interactive API docs at **http://localhost:8000/docs**.

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The Next.js dashboard opens at **http://localhost:3000**.

### 4. Run your first scan

Open the dashboard and click **Full Scan**, or use the API:

```bash
curl -X POST http://localhost:8000/api/scan/full
```

This downloads 2000+ NSE stocks, applies filters, fetches data, computes indicators, trains models, and generates a ranked watchlist.

---

## Deployment Guide

### Architecture Overview

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│   Vercel     │──────▶│   Render     │──────▶│  Supabase   │
│  (Frontend)  │ API   │  (Backend)   │  SQL  │ (Database)  │
│  Next.js     │ calls │  FastAPI     │       │ PostgreSQL  │
└─────────────┘       └──────────────┘       └─────────────┘
```

The recommended free-tier stack:
- **Frontend** → Vercel (free for hobby projects)
- **Backend** → Render (free Web Service tier)
- **Database** → Supabase (free tier: 500 MB, 2 projects)

---

### Step 1: Database → Supabase

#### 1.1 Create a Supabase project

1. Go to [supabase.com](https://supabase.com) and sign in with GitHub.
2. Click **New Project**.
3. Choose an organization, give the project a name (e.g. `stock-scanner`), set a DB password, and pick a region close to you (e.g. `ap-south-1` Mumbai).
4. Click **Create new project** and wait ~2 minutes for provisioning.

#### 1.2 Run the schema

1. In the Supabase dashboard, go to **SQL Editor** (left sidebar).
2. Click **New query**.
3. Open `database/schema.sql` from this repo, copy the full contents, and paste it into the editor.
4. Click **Run** (or press Ctrl+Enter). You should see "Success. No rows returned."
5. Verify: go to **Table Editor** — you should see `scanned_stocks`, `stock_data`, `predictions`, `watchlist`, and `scan_log` tables.

#### 1.3 Copy your credentials

1. Go to **Settings → API** in the Supabase dashboard.
2. Copy these two values — you'll need them for the backend:

| Setting | Where to find it |
|---------|-----------------|
| **Project URL** | `Settings → API → Project URL` (looks like `https://xxxxx.supabase.co`) |
| **anon / public key** | `Settings → API → Project API keys → anon public` |
| **service_role key** | `Settings → API → Project API keys → service_role` (keep secret!) |

#### 1.4 (Optional) Enable Row Level Security

If you want to restrict table access:

```sql
-- In Supabase SQL Editor:
ALTER TABLE scanned_stocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_log ENABLE ROW LEVEL SECURITY;

-- Allow anonymous reads (for public dashboard):
CREATE POLICY "anon_read" ON scanned_stocks FOR SELECT USING (true);
CREATE POLICY "anon_read" ON predictions FOR SELECT USING (true);
CREATE POLICY "anon_read" ON watchlist FOR SELECT USING (true);
CREATE POLICY "anon_read" ON scan_log FOR SELECT USING (true);
```

---

### Step 2: Backend → Render

#### 2.1 Prepare the repo

Make sure these files exist in your repo root:

**`requirements.txt`** — already included. Verify it has `fastapi`, `uvicorn`, `supabase`, etc.

**`Procfile`** (create if missing):
```
web: python -m backend.api_server
```

> Render also supports the start command via dashboard, so the Procfile is optional.

#### 2.2 Push to GitHub

```bash
git add -A
git commit -m "Prepare for deployment"
git push origin main
```

#### 2.3 Create the Render Web Service

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. Click **New +** → **Web Service**.
3. Connect your GitHub repo (`StockPrediction`).
4. Configure:

| Field | Value |
|-------|-------|
| **Name** | `stock-scanner-api` (or any name) |
| **Region** | Closest to your Supabase region |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python -m backend.api_server` |
| **Instance Type** | `Free` |

5. Click **Advanced** → **Add Environment Variables**:

| Key | Value |
|-----|-------|
| `USE_SQLITE` | `false` |
| `SUPABASE_URL` | Your Supabase Project URL |
| `SUPABASE_KEY` | Your Supabase `anon` key |
| `SUPABASE_SERVICE_KEY` | Your Supabase `service_role` key |
| `CORS_ORIGINS` | `https://your-app.vercel.app` (set after Vercel deploy) |
| `PORT` | `8000` |

6. Click **Create Web Service**.
7. Wait for the build to finish (~3-5 minutes). Once live, note the URL: `https://stock-scanner-api.onrender.com`.

#### 2.4 Verify the backend

```bash
curl https://stock-scanner-api.onrender.com/api/health
# Should return: {"status":"ok","timestamp":"..."}
```

> **Note:** Render free tier spins down after 15 minutes of inactivity. The first request after idle takes ~30-60 seconds. Upgrade to the Starter plan ($7/mo) for always-on.

#### 2.5 (Optional) Render cron job for auto-scanning

Render supports **Cron Jobs** for scheduled scans:

1. **New +** → **Cron Job**
2. Connect the same repo
3. **Schedule**: `*/15 9-15 * * 1-5` (every 15 min, Mon-Fri, 9 AM – 3 PM IST)
4. **Command**: `python -c "from backend.watchlist_generator import run_quick_scan; run_quick_scan()"`
5. Set the same environment variables as the Web Service

---

### Step 3: Frontend → Vercel

#### 3.1 Create the Vercel project

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub.
2. Click **Add New… → Project**.
3. Import your `StockPrediction` repository.
4. Configure:

| Field | Value |
|-------|-------|
| **Framework Preset** | `Next.js` (auto-detected) |
| **Root Directory** | Click **Edit** → type `frontend` → click **Continue** |
| **Build Command** | `npm run build` (default) |
| **Output Directory** | `.next` (default) |
| **Install Command** | `npm install` (default) |

5. Expand **Environment Variables** and add:

| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_API_URL` | `https://stock-scanner-api.onrender.com` |
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase Project URL (optional, for client-side auth) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Your Supabase anon key (optional) |

6. Click **Deploy**.
7. Wait ~1-2 minutes. Vercel gives you a URL: `https://your-app.vercel.app`.

#### 3.2 Update Render CORS

Go back to your Render Web Service → **Environment** and update:

```
CORS_ORIGINS=https://your-app.vercel.app
```

Click **Save Changes**. Render will redeploy automatically.

#### 3.3 Verify end-to-end

1. Open `https://your-app.vercel.app`
2. The dashboard should load and show the health status
3. Click **Full Scan** to trigger your first market scan

#### 3.4 Custom domain (optional)

1. In Vercel: **Settings → Domains → Add** your domain (e.g. `scanner.yourdomain.com`)
2. Add the CNAME record in your DNS provider:
   - **Type**: CNAME
   - **Name**: `scanner` (or `@` for root)
   - **Value**: `cname.vercel-dns.com`
3. Vercel auto-provisions SSL

---

### Alternative: Deploy everything on Railway

[Railway](https://railway.app) can host both frontend and backend in one project:

1. Sign in at [railway.app](https://railway.app) with GitHub.
2. **New Project → Deploy from GitHub repo**.
3. Railway auto-detects the Python backend. Configure:
   - **Start Command**: `python -m backend.api_server`
   - Add the same env vars as Render above
4. **Add New Service → Database → PostgreSQL** for the database (instead of Supabase).
   - Run `schema.sql` via Railway's psql connection
5. **Add New Service → GitHub repo** again, but set Root Directory to `frontend` for the Next.js frontend.
   - Add `NEXT_PUBLIC_API_URL` pointing to the backend service URL

Railway's free tier gives you $5/month of usage.

---

### Alternative: Deploy with Docker

#### Dockerfile for backend

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY .env .env
EXPOSE 8000
CMD ["python", "-m", "backend.api_server"]
```

#### Dockerfile for frontend

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

> For the standalone output, add `output: 'standalone'` to `next.config.js`.

#### docker-compose.yml

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - USE_SQLITE=true
    volumes:
      - ./data:/app/data
      - ./models:/app/models

  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
      args:
        NEXT_PUBLIC_API_URL: http://localhost:8000
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

```bash
docker compose up --build
```

---

## Environment Variables Reference

### Backend (`.env` or host config)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `USE_SQLITE` | No | `true` | `true` = SQLite local, `false` = Supabase |
| `SUPABASE_URL` | If Supabase | — | Supabase project URL |
| `SUPABASE_KEY` | If Supabase | — | Supabase anon/public API key |
| `SUPABASE_SERVICE_KEY` | If Supabase | — | Supabase service role key |
| `PORT` | No | `8000` | Backend port |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Comma-separated allowed origins |

### Frontend (`frontend/.env.local` or Vercel config)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | `http://localhost:8000` | Backend API URL |
| `NEXT_PUBLIC_SUPABASE_URL` | No | — | For client-side Supabase auth |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | No | — | Supabase anon key for frontend |

---

## API Endpoints

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/overview` | Market overview stats |
| GET | `/api/predictions` | All predictions (filter: `?signal=BUY`) |
| GET | `/api/watchlist` | Today's watchlist |
| GET | `/api/watchlist/categories` | Available categories |
| GET | `/api/stocks` | All scanned stocks |
| GET | `/api/stocks/{symbol}` | Stock detail + prediction |
| GET | `/api/stocks/{symbol}/chart` | OHLCV chart data |
| GET | `/api/stocks/{symbol}/indicators` | Technical indicators |

### Scanner & Scheduler

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/scan/full` | Full scan (filter + retrain + predict) |
| POST | `/api/scan/quick` | Quick scan (predict only) |
| GET | `/api/scan/logs` | Scan history |
| POST | `/api/scheduler/start` | Start auto-scheduler |
| POST | `/api/scheduler/stop` | Stop auto-scheduler |
| GET | `/api/scheduler/status` | Scheduler status |

### Meta-AI Strategy & Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/meta-strategy` | Meta-AI strategy weights & status |
| GET | `/api/regime` | Market regime (Bull/Bear/Sideways) |
| GET | `/api/strategies/performance` | All strategy performance stats |
| GET | `/api/risk/{symbol}` | Risk recommendation for a stock |
| GET | `/api/portfolio` | Portfolio optimization (`?method=...`) |
| GET | `/api/stocks/{symbol}/sentiment` | Sentiment analysis |
| GET | `/api/stocks/{symbol}/institutional` | Institutional activity |

### Training Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/training/status` | Training pipeline status |
| POST | `/api/training/start` | Trigger model retraining |
| GET | `/api/training/logs` | Training run history |
| GET | `/api/training/versions` | All model versions |
| POST | `/api/training/rollback` | Rollback model (`?steps=1`) |

### Paper Trading

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/paper/portfolio` | Virtual portfolio summary |
| GET | `/api/paper/positions` | Open positions |
| POST | `/api/paper/order` | Place paper order (`?symbol=RELIANCE&side=BUY`) |
| GET | `/api/paper/trades` | Trade history |
| GET | `/api/paper/performance` | Performance stats (win rate, Sharpe, etc.) |
| POST | `/api/paper/auto-execute` | Auto-trade from AI signals |
| POST | `/api/paper/reset` | Reset to ₹1,00,000 |

---

## Opportunity Score

Each stock receives a score from 0–100%:

```
Score = 40% × AI Probability + 25% × Momentum + 20% × Breakout + 15% × Volume
```

| Component | Weight | What it measures |
|-----------|--------|------------------|
| AI Probability | 40% | ML ensemble prediction confidence |
| Momentum | 25% | RSI, MACD, ROC, price vs moving averages |
| Breakout | 20% | Resistance break, volume surge, golden cross |
| Volume Spike | 15% | Current volume vs 20-day average |

---

## Configuration

All settings are in `backend/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `FILTER_MIN_VOLUME` | 500,000 | Minimum average daily volume |
| `FILTER_MIN_PRICE` | ₹50 | Minimum stock price |
| `FILTER_MIN_VOLATILITY` | 1.5% | Minimum daily volatility |
| `SCAN_INTERVAL_MINUTES` | 15 | Auto-scan frequency |
| `MARKET_OPEN_HOUR/MINUTE` | 9:15 IST | Market open time |
| `MARKET_CLOSE_HOUR/MINUTE` | 15:30 IST | Market close time |
| `DEFAULT_CAPITAL` | ₹10,00,000 | Default capital for risk calc |
| `RISK_PER_TRADE_PCT` | 2% | Max risk per trade |
| `MAX_POSITIONS` | 10 | Max simultaneous positions |
| `TOP_BUY_COUNT` | 20 | Top buy picks in watchlist |
| `TOP_SELL_COUNT` | 10 | Top sell picks in watchlist |

---

## Troubleshooting

### Backend won't start

```bash
# Check Python version (need 3.11+)
python --version

# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Test imports
python -c "from backend import api_server; print('OK')"
```

### Frontend build fails

```bash
cd frontend
rm -rf node_modules .next
npm install
npm run build
```

### Render deploy fails

- Check **Logs** in Render dashboard for the exact error
- Ensure `requirements.txt` is in the repo root (not inside `backend/`)
- Verify all env vars are set correctly
- Try setting **Python Version** to `3.12` in Render Environment settings

### CORS errors in browser

- Ensure `CORS_ORIGINS` on Render includes your Vercel URL (with `https://`, no trailing slash)
- Multiple origins: `https://app1.vercel.app,https://app2.vercel.app`

### Supabase connection fails

- Verify `SUPABASE_URL` starts with `https://` and ends with `.supabase.co`
- Verify the `anon` key is correct (not the `service_role` key)
- Check that tables exist: go to Supabase **Table Editor**

### Render free tier cold starts

The free Render instance spins down after 15 min of inactivity. First request after idle takes 30–60s.
- Add a health-check ping service (e.g. [UptimeRobot](https://uptimerobot.com), free) to keep it warm
- Or upgrade to Render Starter ($7/mo) for always-on

---

## License

For personal use only.
