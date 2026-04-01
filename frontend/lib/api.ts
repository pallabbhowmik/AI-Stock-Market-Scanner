const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const GET_CACHE_TTL_MS = 10_000;
const REQUEST_TIMEOUT_MS = 15_000;
const responseCache = new Map<string, { expiresAt: number; value: unknown }>();
const inflightRequests = new Map<string, Promise<unknown>>();

function clearApiCache(prefix?: string) {
  if (!prefix) {
    responseCache.clear();
    inflightRequests.clear();
    return;
  }
  for (const key of Array.from(responseCache.keys())) {
    if (key.startsWith(prefix)) responseCache.delete(key);
  }
  for (const key of Array.from(inflightRequests.keys())) {
    if (key.startsWith(prefix)) inflightRequests.delete(key);
  }
}

async function fetchAPI<T>(endpoint: string, options?: { cacheMs?: number; force?: boolean }): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const cacheMs = options?.cacheMs ?? GET_CACHE_TTL_MS;
  const cached = responseCache.get(url);
  if (!options?.force && cached && cached.expiresAt > Date.now()) {
    return cached.value as T;
  }
  if (!options?.force) {
    const inflight = inflightRequests.get(url);
    if (inflight) return inflight as Promise<T>;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  const request = fetch(url, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const payload = (await res.json()) as T;
      if (cacheMs > 0) {
        responseCache.set(url, { expiresAt: Date.now() + cacheMs, value: payload });
      }
      return payload;
    })
    .finally(() => {
      clearTimeout(timeout);
      inflightRequests.delete(url);
    });

  inflightRequests.set(url, request);
  return request;
}

async function postAPI<T>(endpoint: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    signal: controller.signal,
  });
  clearTimeout(timeout);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  clearApiCache(`${API_BASE}/api/`);
  return res.json() as Promise<T>;
}

// ─── Types ──────────────────────────────────────────────────────────────────

export interface Overview {
  total_stocks: number;
  analyzed_today: number;
  buy_signals: number;
  sell_signals: number;
  hold_signals: number;
  avg_confidence: number;
  last_scan: Record<string, unknown> | null;
  scheduler: { running: boolean; last_run: string | null; next_run: string | null; market_open: boolean };
}

export interface DashboardPayload {
  overview: Overview;
  buys: Prediction[];
  sells: Prediction[];
  meta: MetaStrategyStatus | null;
  training: TrainingStatus | null;
}

export interface Prediction {
  symbol: string;
  signal: string;
  confidence: number;
  ai_probability: number;
  momentum_score: number;
  breakout_score: number;
  volume_spike_score: number;
  opportunity_score: number;
  explanation: string;
}

export interface WatchlistItem {
  category: string;
  symbol: string;
  signal: string;
  confidence: number;
  opportunity_score: number;
  explanation: string;
  rank: number;
}

export interface StockDetail {
  symbol: string;
  name: string;
  last_price: number;
  market_cap: number;
  avg_volume: number;
  daily_volatility: number;
}

export interface ChartPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ScanLog {
  started_at: string;
  finished_at: string;
  stocks_scanned: number;
  stocks_passed_filter: number;
  status: string;
}

export interface SchedulerStatus {
  running: boolean;
  last_run: string | null;
  next_run: string | null;
  market_open: boolean;
}

export interface MetaStrategyStatus {
  strategies: Record<string, number>;
  weights: Record<string, number>;
  regime: string;
  regime_confidence: number;
  explanation: string;
  performance: Record<string, StrategyPerformance>;
  last_updated?: string;
}

export interface StrategyPerformance {
  trades: number;
  wins: number;
  win_rate: number;
  avg_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
}

export interface RegimeInfo {
  regime: string;
  confidence: number;
  signals: Record<string, unknown>;
}

export interface RiskRecommendation {
  symbol: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  position_size: number;
  position_value: number;
  risk_amount: number;
  risk_reward_ratio: number;
}

export interface PortfolioAllocation {
  allocation: Array<{ symbol: string; weight: number; shares?: number }>;
  method: string;
  message?: string;
}

export interface SentimentResult {
  symbol: string;
  score: number;
  signal: string;
  headlines_analyzed: number;
}

export interface InstitutionalResult {
  score: number;
  signal: string;
  details: Record<string, unknown>;
}

export interface TrainingStatus {
  status: string;
  last_training: string | null;
  last_result: Record<string, unknown> | null;
  training_in_progress: boolean;
  error: string | null;
  model_version: string;
  model_accuracy: number;
  model_auc: number;
  model_sharpe: number;
  model_training_date: string;
  model_dataset_size: number;
  all_versions: ModelVersion[];
}

export interface ModelVersion {
  version_id: string;
  training_date: string;
  accuracy: number;
  auc: number;
  sharpe_ratio: number;
  max_drawdown: number;
  profit_factor: number;
  dataset_size: number;
  deployed: boolean;
}

export interface TrainingLog {
  version_id: string;
  started_at: string;
  finished_at: string;
  status: string;
  accuracy: number;
  auc: number;
  sharpe_ratio: number;
  max_drawdown: number;
  profit_factor: number;
  dataset_size: number;
  stocks_trained: number;
  duration_seconds: number;
  deployed: number;
}

// ─── Intraday Types ─────────────────────────────────────────────────────────

export interface IntradayPrediction {
  symbol: string;
  horizon: string;
  signal: string;
  confidence: number;
  probability: number;
  entry_price: number;
  stop_loss: number;
  target_price: number;
  risk_reward: number;
  model_votes: Record<string, number>;
  consensus_direction: string;
  consensus_agreement: number;
  explanation: string;
  timestamp?: string;
}

export interface IntradayScanStatus {
  running: boolean;
  error: string | null;
  result: Record<string, unknown> | null;
  started_at: string | null;
  current_step: string;
  progress: number;
  stocks_processed: number;
  stocks_total: number;
}

// ─── Paper Trading Types ────────────────────────────────────────────────────

export interface PaperPosition {
  symbol: string;
  qty: number;
  avg_price: number;
  live_price: number;
  invested: number;
  current_value: number;
  unrealised_pnl: number;
  unrealised_pct: number;
  opened_at: string;
}

export interface PaperPortfolio {
  mode: string;
  cash: number;
  initial_capital: number;
  invested: number;
  current_value: number;
  portfolio_value: number;
  total_return: number;
  total_return_pct: number;
  open_positions: number;
  positions: PaperPosition[];
}

export interface PaperTrade {
  id: number;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  price: number;
  value: number;
  costs: Record<string, number>;
  pnl: number | null;
  pnl_pct: number | null;
  entry_price: number | null;
  status: string;
  mode: string;
  timestamp: string;
}

export interface PaperPerformance {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_profit: number;
  avg_loss: number;
  total_pnl: number;
  max_drawdown: number;
  sharpe_ratio: number;
  profit_factor: number;
  best_trade: number;
  worst_trade: number;
  daily_pnl: Array<{ date: string; pnl: number }>;
}

// ─── API Functions ──────────────────────────────────────────────────────────

export const api = {
  clearCache: () => clearApiCache(`${API_BASE}/api/`),
  getDashboard: () => fetchAPI<DashboardPayload>("/api/dashboard"),
  getOverview: () => fetchAPI<Overview>("/api/overview"),
  getPredictions: (signal?: string) =>
    fetchAPI<{ predictions: Prediction[]; total: number }>(
      `/api/predictions${signal ? `?signal=${signal}` : ""}`
    ).then((r) => r.predictions),
  getWatchlist: () =>
    fetchAPI<{ watchlist: WatchlistItem[] }>("/api/watchlist").then((r) => r.watchlist),
  getWatchlistByCategory: () =>
    fetchAPI<{ categories: Array<{ id: string; name: string; color: string }> }>("/api/watchlist/categories").then((r) => r.categories as any),
  getStocks: () =>
    fetchAPI<{ stocks: StockDetail[]; total: number }>("/api/stocks").then((r) => r.stocks),
  getStock: (symbol: string) =>
    fetchAPI<StockDetail>(`/api/stocks/${encodeURIComponent(symbol)}`),
  getChart: (symbol: string, days?: number) =>
    fetchAPI<{ symbol: string; data: ChartPoint[] }>(
      `/api/stocks/${encodeURIComponent(symbol)}/chart${days ? `?period=${days}` : ""}`
    ).then((r) => r.data),
  getIndicators: (symbol: string) =>
    fetchAPI<Record<string, number>>(
      `/api/stocks/${encodeURIComponent(symbol)}/indicators`
    ),
  triggerFullScan: (options?: { retrain?: boolean; maxSymbols?: number }) => {
    const params = new URLSearchParams();
    if (options?.retrain) params.set("retrain", "true");
    if (typeof options?.maxSymbols === "number" && options.maxSymbols > 0) {
      params.set("max_symbols", String(options.maxSymbols));
    }
    const query = params.toString();
    return postAPI<{ status: string }>(`/api/scan/full${query ? `?${query}` : ""}`);
  },
  triggerQuickScan: () => postAPI<{ status: string }>("/api/scan/quick"),
  triggerLiteScan: () => postAPI<{ status: string }>("/api/scan/lite"),
  getScanStatus: () => fetchAPI<{
    running: boolean;
    error: string | null;
    result: Record<string, unknown> | null;
    started_at: string | null;
    current_step: string;
    progress: number;
    total_steps: number;
    stocks_processed: number;
    stocks_total: number;
  }>("/api/scan/status"),
  getScanLogs: () => fetchAPI<ScanLog[]>("/api/scan/logs"),
  startScheduler: () => postAPI<{ status: string }>("/api/scheduler/start"),
  stopScheduler: () => postAPI<{ status: string }>("/api/scheduler/stop"),
  getSchedulerStatus: () =>
    fetchAPI<SchedulerStatus>("/api/scheduler/status"),
  getHealth: () => fetchAPI<{ status: string }>("/api/health"),

  // Meta-AI Strategy
  getMetaStrategy: () =>
    fetchAPI<MetaStrategyStatus>("/api/meta-strategy"),
  getRegime: () => fetchAPI<RegimeInfo>("/api/regime"),
  getStrategyPerformance: () =>
    fetchAPI<{ strategies: Record<string, StrategyPerformance> }>(
      "/api/strategies/performance"
    ),

  // Risk & Portfolio
  getRisk: (symbol: string) =>
    fetchAPI<RiskRecommendation>(
      `/api/risk/${encodeURIComponent(symbol)}`
    ),
  getPortfolio: (method?: string) =>
    fetchAPI<PortfolioAllocation>(
      `/api/portfolio${method ? `?method=${method}` : ""}`
    ),

  // Sentiment & Institutional
  getSentiment: (symbol: string) =>
    fetchAPI<SentimentResult>(
      `/api/stocks/${encodeURIComponent(symbol)}/sentiment`
    ),
  getInstitutional: (symbol: string) =>
    fetchAPI<InstitutionalResult>(
      `/api/stocks/${encodeURIComponent(symbol)}/institutional`
    ),

  // Training Pipeline
  getTrainingStatus: () =>
    fetchAPI<TrainingStatus>("/api/training/status"),
  triggerTraining: () =>
    postAPI<{ status: string; message: string }>("/api/training/start"),
  getTrainingLogs: () =>
    fetchAPI<{ logs: TrainingLog[] }>("/api/training/logs"),
  getModelVersions: () =>
    fetchAPI<{ versions: ModelVersion[]; current_version: string | null }>(
      "/api/training/versions"
    ),
  rollbackModel: (steps?: number) =>
    postAPI<{ status: string; version_id?: string }>(
      `/api/training/rollback${steps ? `?steps=${steps}` : ""}`
    ),

  // Paper Trading
  getPaperPortfolio: () =>
    fetchAPI<PaperPortfolio>("/api/paper/portfolio"),
  getPaperPositions: () =>
    fetchAPI<{ positions: PaperPosition[]; count: number }>("/api/paper/positions"),
  placePaperOrder: (params: {
    symbol: string;
    side: string;
    order_type?: string;
    quantity?: number;
    limit_price?: number;
    stop_price?: number;
    take_profit_price?: number;
  }) => {
    const q = new URLSearchParams({ symbol: params.symbol, side: params.side });
    if (params.order_type) q.set("order_type", params.order_type);
    if (params.quantity) q.set("quantity", String(params.quantity));
    if (params.limit_price) q.set("limit_price", String(params.limit_price));
    if (params.stop_price) q.set("stop_price", String(params.stop_price));
    if (params.take_profit_price) q.set("take_profit_price", String(params.take_profit_price));
    return postAPI<PaperTrade>(`/api/paper/order?${q.toString()}`);
  },
  getPaperTrades: (limit?: number) =>
    fetchAPI<{ trades: PaperTrade[]; total: number }>(
      `/api/paper/trades${limit ? `?limit=${limit}` : ""}`
    ),
  getPaperPerformance: () =>
    fetchAPI<PaperPerformance>("/api/paper/performance"),
  autoExecutePaper: () =>
    postAPI<{ executed: number; trades: PaperTrade[] }>("/api/paper/auto-execute"),
  resetPaperPortfolio: () =>
    postAPI<{ status: string; cash: number }>("/api/paper/reset"),

  // Intraday Trading
  triggerIntradayScan: (retrain?: boolean) =>
    postAPI<{ status: string; message?: string }>(
      `/api/intraday/scan${retrain ? "?retrain=true" : ""}`
    ),
  getIntradayScanStatus: () =>
    fetchAPI<IntradayScanStatus>("/api/intraday/status"),
  getIntradayPredictions: (params?: { signal?: string; horizon?: string; min_confidence?: number }) => {
    const q = new URLSearchParams();
    if (params?.signal) q.set("signal", params.signal);
    if (params?.horizon) q.set("horizon", params.horizon);
    if (params?.min_confidence) q.set("min_confidence", String(params.min_confidence));
    const qs = q.toString();
    return fetchAPI<{ predictions: IntradayPrediction[]; total: number }>(
      `/api/intraday/predictions${qs ? `?${qs}` : ""}`
    ).then((r) => r.predictions);
  },
};
