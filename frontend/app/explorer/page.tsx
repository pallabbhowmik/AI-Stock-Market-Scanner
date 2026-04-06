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
    BUY: { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", icon: TrendingUp },
    SELL: { cls: "bg-red-500/10 text-red-400 border-red-500/20", icon: TrendingDown },
    HOLD: { cls: "bg-amber-500/10 text-amber-400 border-amber-500/20", icon: Minus },
  }[signal] || { cls: "bg-white/[0.04] text-slate-400 border-white/[0.08]", icon: Minus };
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold ${config.cls}`}>
      <Icon size={11} /> {signal}
    </span>
  );
}

function ScoreMeter({ label, score, tip, icon: Icon }: { label: string; score: number; tip: string; icon?: React.ElementType }) {
  const pct = Math.round(score * 100);
  const barColor = pct >= 70 ? "bg-buy" : pct >= 40 ? "bg-hold" : "bg-sell";
  return (
    <div className="tooltip-trigger">
      <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
        <span className="flex items-center gap-1.5 font-medium">
          {Icon && <Icon size={12} className="text-slate-500" />}
          {label}
        </span>
        <span className="font-bold text-slate-200 number-display">{pct}%</span>
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
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${days === d ? "bg-indigo-500/15 text-indigo-400 border border-indigo-500/25" : "bg-white/[0.03] text-slate-400 border border-white/[0.06] hover:bg-white/[0.06] hover:text-white"}`}
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
            contentStyle={{ background: "linear-gradient(135deg, #0f1629, #151d33)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12 }}
          />
          <Line type="monotone" dataKey="close" stroke="#6366f1" dot={false} strokeWidth={2} />
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
        <div className="space-y-1.5">
          <h2 className="text-xl font-bold text-white tracking-tight">{prediction.symbol}</h2>
          <SignalBadge signal={prediction.signal} />
        </div>
        <button onClick={onClose} className="rounded-xl p-1.5 text-slate-400 hover:bg-white/[0.06] hover:text-white transition">
          <X size={18} />
        </button>
      </div>

      <StockChart symbol={prediction.symbol} />

      {/* Score Meters */}
      <div>
        <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
          <Activity size={12} className="text-indigo-400" /> Strategy Scores
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
      <div className="rounded-xl bg-white/[0.02] border border-white/[0.05] p-4">
        <h3 className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">AI Analysis</h3>
        <p className="text-sm leading-relaxed text-slate-300">{prediction.explanation}</p>
      </div>

      {/* Overall Score */}
      <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/[0.06] p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-bold text-indigo-400">
            Overall Score: {Math.round(prediction.opportunity_score * 100)}%
          </span>
          <Tip text="Weighted combination: 40% AI + 25% Momentum + 20% Breakout + 15% Volume" />
        </div>
        <div className="mt-2 score-bar">
          <div className="score-bar-fill bg-indigo-500" style={{ width: `${Math.round(prediction.opportunity_score * 100)}%` }} />
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
          <Loader2 size={28} className="animate-spin text-indigo-400 mx-auto" />
          <p className="text-slate-500 text-sm">Loading stocks...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stock Explorer</h1>
        <p className="mt-0.5 text-sm text-slate-500">
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
            className="rounded-xl border border-white/[0.08] bg-white/[0.03] py-2 pl-9 pr-4 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/20 w-48 transition"
          />
        </div>
        {search && (
          <button
            onClick={() => setSearch("")}
            className="btn-secondary text-xs px-3 py-2"
          >
            Clear search
          </button>
        )}
        <div className="flex gap-1">
          {["ALL", "BUY", "SELL", "HOLD"].map((s) => (
            <button
              key={s}
              onClick={() => setFilterSignal(s)}
              className={`rounded-xl px-3.5 py-2 text-xs font-medium transition-all ${
                filterSignal === s ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/25" : "bg-white/[0.03] text-slate-400 border border-white/[0.06] hover:bg-white/[0.05] hover:text-white"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-indigo-500/40 transition"
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
        <div className="card text-center py-14">
          <div className="mb-4 text-5xl">🔍</div>
          <h2 className="text-lg font-bold text-white mb-2">No stocks to explore yet</h2>
          <p className="text-sm text-slate-400 mb-5">Run a Full Scan from the Dashboard to analyze stocks.</p>
          <Link href="/" className="btn-primary">
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
                  className={`flex w-full items-center gap-4 rounded-xl border px-4 py-3 text-left transition-all duration-200 ${
                    selected?.symbol === p.symbol
                      ? "border-indigo-500/25 bg-indigo-500/[0.08]"
                      : "border-white/[0.05] bg-white/[0.02] hover:border-white/[0.1] hover:bg-white/[0.04]"
                  }`}
                >
                  <span className="w-20 font-semibold text-white">{p.symbol}</span>
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
                <Search size={36} className="mb-3 text-slate-700" />
                <p className="text-slate-500 mb-1 font-medium">Select a stock from the list</p>
                <p className="text-xs text-slate-600">Click any stock to see its price chart, AI scores, and analysis</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
