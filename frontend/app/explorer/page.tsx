"use client";

import { useDeferredValue, useEffect, useState, useMemo, useCallback } from "react";
import { api, Prediction, ChartPoint } from "@/lib/api";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Info,
  Loader2,
  Search,
  X,
  ArrowRight,
  Brain,
  Activity,
  Zap,
  BarChart3,
} from "lucide-react";
import Link from "next/link";

function Tip({ text }: { text: string }) {
  return (
    <span className="tooltip-trigger ml-1 inline-flex">
      <Info size={13} className="text-slate-500" />
      <span className="tooltip-content">{text}</span>
    </span>
  );
}

function SignalBadge({ signal }: { signal: string }) {
  const config = {
    BUY: { cls: "bg-green-900/60 text-green-400 border-green-700", icon: TrendingUp },
    SELL: { cls: "bg-red-900/60 text-red-400 border-red-700", icon: TrendingDown },
    HOLD: { cls: "bg-yellow-900/60 text-yellow-400 border-yellow-700", icon: Minus },
  }[signal] || { cls: "bg-slate-800 text-slate-400 border-slate-600", icon: Minus };
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${config.cls}`}>
      <Icon size={12} /> {signal}
    </span>
  );
}

function ScoreMeter({ label, score, tip, icon: Icon }: { label: string; score: number; tip: string; icon?: React.ElementType }) {
  const pct = Math.round(score * 100);
  const barColor = pct >= 70 ? "bg-buy" : pct >= 40 ? "bg-hold" : "bg-sell";
  return (
    <div className="tooltip-trigger">
      <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
        <span className="flex items-center gap-1.5">
          {Icon && <Icon size={12} />}
          {label}
        </span>
        <span className="font-medium text-slate-300">{pct}%</span>
      </div>
      <div className="score-bar">
        <div className={`score-bar-fill ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="tooltip-content">{tip}</div>
    </div>
  );
}

function StockChart({ symbol }: { symbol: string }) {
  const [chart, setChart] = useState<ChartPoint[]>([]);
  const [days, setDays] = useState(90);
  const [chartLoading, setChartLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setChartLoading(true);
    api.getChart(symbol, days)
      .then((data) => { if (active) setChart(data); })
      .catch(() => { if (active) setChart([]); })
      .finally(() => { if (active) setChartLoading(false); });
    return () => { active = false; };
  }, [symbol, days]);

  if (chartLoading) {
    return <div className="flex h-[300px] items-center justify-center"><Loader2 size={24} className="animate-spin text-slate-500" /></div>;
  }
  if (!chart.length) return <p className="text-sm text-slate-500 py-8 text-center">No chart data available for {symbol}</p>;

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        {[30, 90, 180, 365].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`rounded-lg px-3 py-1 text-xs transition ${days === d ? "bg-accent text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"}`}
          >
            {d}D
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chart}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 10 }} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} domain={["auto", "auto"]} />
          <Tooltip
            contentStyle={{ background: "#1e293b", border: "1px solid #475569", borderRadius: 8, fontSize: 12 }}
          />
          <Line type="monotone" dataKey="close" stroke="#3b82f6" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
      <ResponsiveContainer width="100%" height={80}>
        <BarChart data={chart}>
          <XAxis dataKey="date" tick={false} />
          <Bar dataKey="volume" fill="#475569" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function StockDetail({ prediction, onClose }: { prediction: Prediction; onClose: () => void }) {
  return (
    <div className="card animate-in space-y-5 sticky top-4">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h2 className="text-xl font-bold text-white">{prediction.symbol}</h2>
          <SignalBadge signal={prediction.signal} />
        </div>
        <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-700 hover:text-white transition">
          <X size={18} />
        </button>
      </div>

      <StockChart symbol={prediction.symbol} />

      {/* Score Meters */}
      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
          <Activity size={12} /> Strategy Scores
          <Tip text="Each score represents how a specific trading strategy rates this stock. Higher = stronger signal." />
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <ScoreMeter icon={Brain} label="AI Probability" score={prediction.ai_probability} tip="Machine learning model confidence — how sure the ML models are about the predicted direction" />
          <ScoreMeter icon={TrendingUp} label="Momentum" score={prediction.momentum_score} tip="RSI + MACD + rate-of-change: measures the speed and strength of the stock's trend" />
          <ScoreMeter icon={Zap} label="Breakout" score={prediction.breakout_score} tip="Detects if the stock is breaking through resistance levels, with volume confirmation" />
          <ScoreMeter icon={BarChart3} label="Volume Spike" score={prediction.volume_spike_score} tip="Recent trading volume vs 20-day average — high values often signal institutional buying" />
        </div>
      </div>

      {/* Analysis */}
      <div className="rounded-lg bg-slate-700/30 p-4">
        <h3 className="mb-1 text-xs font-semibold uppercase text-slate-400">AI Analysis</h3>
        <p className="text-sm leading-relaxed text-slate-300">{prediction.explanation}</p>
      </div>

      {/* Overall Score */}
      <div className="rounded-lg border border-accent/30 bg-accent/10 p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-accent">
            Overall Score: {Math.round(prediction.opportunity_score * 100)}%
          </span>
          <Tip text="Weighted combination: 40% AI + 25% Momentum + 20% Breakout + 15% Volume" />
        </div>
        <div className="mt-2 score-bar">
          <div className="score-bar-fill bg-accent" style={{ width: `${Math.round(prediction.opportunity_score * 100)}%` }} />
        </div>
      </div>
    </div>
  );
}

export default function ExplorerPage() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterSignal, setFilterSignal] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<string>("opportunity_score");
  const [selected, setSelected] = useState<Prediction | null>(null);
  const deferredSearch = useDeferredValue(search);

  useEffect(() => {
    api.getPredictions().then((d) => { setPredictions(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  // Check URL for ?stock= parameter
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const stock = params.get("stock");
    if (stock && predictions.length > 0) {
      const found = predictions.find(p => p.symbol === stock);
      if (found) setSelected(found);
    }
  }, [predictions]);

  const sortFn = useCallback(
    (a: Prediction, b: Prediction) => {
      const key = sortBy as keyof Prediction;
      return (b[key] as number) - (a[key] as number);
    },
    [sortBy]
  );

  const filtered = useMemo(() => {
    return predictions
      .filter((p) => {
        if (filterSignal !== "ALL" && p.signal !== filterSignal) return false;
        if (deferredSearch && !p.symbol.toLowerCase().includes(deferredSearch.toLowerCase())) return false;
        return true;
      })
      .sort(sortFn);
  }, [predictions, filterSignal, deferredSearch, sortFn]);

  useEffect(() => {
    if (!filtered.length) {
      setSelected(null);
      return;
    }
    if (!selected || !filtered.some((item) => item.symbol === selected.symbol)) {
      setSelected(filtered[0]);
    }
  }, [filtered, selected]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center animate-in">
        <div className="text-center space-y-3">
          <Loader2 size={32} className="animate-spin text-accent mx-auto" />
          <p className="text-slate-400">Loading stocks...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      <div>
        <h1 className="text-2xl font-bold">Stock Explorer</h1>
        <p className="text-sm text-slate-400">
          Search, filter, and drill into any scanned stock
          <Tip text="Click any stock to see its price chart, AI scores, and detailed analysis." />
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search symbol..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg border border-slate-600 bg-slate-800 py-2 pl-9 pr-4 text-sm text-white placeholder-slate-500 outline-none focus:border-accent w-48"
          />
        </div>
        {search && (
          <button
            onClick={() => setSearch("")}
            className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-300 transition hover:bg-slate-700"
          >
            Clear search
          </button>
        )}
        <div className="flex gap-1">
          {["ALL", "BUY", "SELL", "HOLD"].map((s) => (
            <button
              key={s}
              onClick={() => setFilterSignal(s)}
              className={`rounded-lg px-3 py-2 text-xs font-medium transition ${
                filterSignal === s ? "bg-accent/15 text-accent border border-accent/30" : "bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white outline-none focus:border-accent"
        >
          <option value="opportunity_score">Sort: Score</option>
          <option value="confidence">Sort: Confidence</option>
          <option value="ai_probability">Sort: AI Prob</option>
          <option value="momentum_score">Sort: Momentum</option>
          <option value="breakout_score">Sort: Breakout</option>
        </select>
        <span className="text-xs text-slate-500">{filtered.length} stocks</span>
      </div>

      {/* No data state */}
      {predictions.length === 0 && (
        <div className="card text-center py-12">
          <div className="mb-3 text-5xl">🔍</div>
          <h2 className="text-lg font-semibold text-white mb-2">No stocks to explore yet</h2>
          <p className="text-sm text-slate-400 mb-4">Run a Full Scan from the Dashboard to analyze stocks.</p>
          <Link href="/" className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-600 transition">
            Go to Dashboard <ArrowRight size={14} />
          </Link>
        </div>
      )}

      {predictions.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* List */}
          <div className="space-y-1 max-h-[70vh] overflow-y-auto pr-2">
            {filtered.length === 0 && (
              <p className="text-sm text-slate-500 py-8 text-center">No stocks match your filters.</p>
            )}
            {filtered.map((p) => {
              const pct = Math.round(p.opportunity_score * 100);
              return (
                <button
                  key={p.symbol}
                  onClick={() => setSelected(p)}
                  className={`flex w-full items-center gap-4 rounded-lg border px-4 py-3 text-left transition ${
                    selected?.symbol === p.symbol
                      ? "border-accent bg-accent/10"
                      : "border-slate-700 bg-slate-800 hover:border-slate-500"
                  }`}
                >
                  <span className="w-20 font-medium text-white">{p.symbol}</span>
                  <SignalBadge signal={p.signal} />
                  <div className="score-bar flex-1">
                    <div
                      className={`score-bar-fill ${pct >= 70 ? "bg-buy" : pct >= 40 ? "bg-hold" : "bg-sell"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-xs text-slate-400">{pct}%</span>
                </button>
              );
            })}
          </div>

          {/* Detail Panel */}
          <div>
            {selected ? (
              <StockDetail prediction={selected} onClose={() => setSelected(null)} />
            ) : (
              <div className="card flex min-h-[300px] flex-col items-center justify-center text-center animate-in">
                <Search size={40} className="mb-3 text-slate-600" />
                <p className="text-slate-500 mb-1">Select a stock from the list</p>
                <p className="text-xs text-slate-600">Click any stock to see its price chart, AI scores, and analysis</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
