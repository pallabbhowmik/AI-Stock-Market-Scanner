"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { api, Prediction, ChartPoint } from "@/lib/api";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar,
} from "recharts";

function SignalBadge({ signal }: { signal: string }) {
  const cls =
    signal === "BUY"
      ? "bg-green-900/60 text-green-400 border-green-700"
      : signal === "SELL"
      ? "bg-red-900/60 text-red-400 border-red-700"
      : "bg-yellow-900/60 text-yellow-400 border-yellow-700";
  return (
    <span className={`inline-block rounded-full border px-3 py-0.5 text-xs font-semibold ${cls}`}>
      {signal}
    </span>
  );
}

function ScoreMeter({ label, score, tip }: { label: string; score: number; tip: string }) {
  const pct = Math.round(score * 100);
  const barColor = pct >= 70 ? "bg-buy" : pct >= 40 ? "bg-hold" : "bg-sell";
  return (
    <div className="tooltip-trigger">
      <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
        <span>{label}</span>
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

  useEffect(() => {
    api.getChart(symbol, days).then(setChart).catch(() => setChart([]));
  }, [symbol, days]);

  if (!chart.length) return <p className="text-xs text-slate-500">No chart data</p>;

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        {[30, 90, 180, 365].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`rounded px-3 py-1 text-xs ${days === d ? "bg-accent text-white" : "bg-slate-700 text-slate-300"}`}
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
    <div className="card space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">{prediction.symbol}</h2>
          <SignalBadge signal={prediction.signal} />
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-white text-lg">&times;</button>
      </div>

      <StockChart symbol={prediction.symbol} />

      <div className="grid gap-3 sm:grid-cols-2">
        <ScoreMeter label="AI Probability" score={prediction.ai_probability} tip="Machine learning model confidence in the predicted direction" />
        <ScoreMeter label="Momentum" score={prediction.momentum_score} tip="RSI, MACD, and rate-of-change based momentum" />
        <ScoreMeter label="Breakout" score={prediction.breakout_score} tip="Resistance break, volume surge, or moving average crossover" />
        <ScoreMeter label="Volume Spike" score={prediction.volume_spike_score} tip="Recent volume vs 20-day average — high means institutional interest" />
      </div>

      <div className="rounded-lg bg-slate-700/30 p-4">
        <h3 className="mb-1 text-xs font-semibold uppercase text-slate-400">Analysis Summary</h3>
        <p className="text-sm leading-relaxed text-slate-300">{prediction.explanation}</p>
      </div>

      <div className="rounded-lg border border-accent/30 bg-accent/10 p-4 text-xs text-slate-400">
        <strong className="text-accent">Opportunity Score: {Math.round(prediction.opportunity_score * 100)}%</strong>
        <span className="ml-2">= 40% AI + 25% Momentum + 20% Breakout + 15% Volume</span>
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

  useEffect(() => {
    api.getPredictions().then((d) => { setPredictions(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

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
        if (search && !p.symbol.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
      })
      .sort(sortFn);
  }, [predictions, filterSignal, search, sortFn]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-slate-400">Loading stocks...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Stock Explorer</h1>
        <p className="text-sm text-slate-400">Search, filter, and drill into any scanned stock</p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search symbol..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-accent"
        />
        <div className="flex gap-1">
          {["ALL", "BUY", "SELL", "HOLD"].map((s) => (
            <button
              key={s}
              onClick={() => setFilterSignal(s)}
              className={`rounded-lg px-3 py-2 text-xs font-medium transition ${
                filterSignal === s ? "bg-accent text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white outline-none"
        >
          <option value="opportunity_score">Score</option>
          <option value="confidence">Confidence</option>
          <option value="ai_probability">AI Prob</option>
          <option value="momentum_score">Momentum</option>
          <option value="breakout_score">Breakout</option>
        </select>
        <span className="text-xs text-slate-500">{filtered.length} stocks</span>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* List */}
        <div className="space-y-1 max-h-[70vh] overflow-y-auto pr-2">
          {filtered.length === 0 && (
            <p className="text-sm text-slate-500">No stocks found. Run a scan from the Dashboard first.</p>
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
            <div className="card flex min-h-[300px] items-center justify-center text-slate-500">
              Select a stock from the list to see details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
