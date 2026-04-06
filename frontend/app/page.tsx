"use client";

import { useEffect, useState } from "react";
import { api, Overview, Prediction, MetaStrategyStatus, TrainingStatus } from "@/lib/api";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  BarChart3,
  Brain,
  Zap,
  RefreshCw,
  Play,
  Pause,
  Info,
  Loader2,
  ArrowRight,
  Sparkles,
  Shield,
  Target,
  Activity,
} from "lucide-react";
import Link from "next/link";

// ─── Tooltip ────────────────────────────────────────────────────────────────
function Tip({ text }: { text: string }) {
  return (
    <span className="tooltip-trigger ml-1 inline-flex">
      <Info size={13} className="text-slate-500" />
      <span className="tooltip-content">{text}</span>
    </span>
  );
}

// ─── Stat Card ──────────────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  icon: Icon,
  color,
  tip,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color?: string;
  tip?: string;
}) {
  return (
    <div className="card-hover flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wider text-slate-500 font-medium">
          {label}
          {tip && <Tip text={tip} />}
        </span>
        <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${
          color === "text-green-400" ? "bg-emerald-500/10" :
          color === "text-red-400" ? "bg-red-500/10" :
          color === "text-blue-400" ? "bg-indigo-500/10" :
          "bg-white/[0.04]"
        }`}>
          <Icon size={15} className={color || "text-slate-400"} />
        </div>
      </div>
      <span className={`text-2xl font-bold tracking-tight number-display ${color || "text-white"}`}>{value}</span>
    </div>
  );
}

// ─── Score Bar ──────────────────────────────────────────────────────────────
function ScoreBar({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  const barColor = pct >= 70 ? "bg-buy" : pct >= 40 ? "bg-hold" : "bg-sell";
  return (
    <div className="flex items-center gap-3">
      {label && <span className="w-24 text-xs text-slate-400">{label}</span>}
      <div className="score-bar flex-1">
        <div className={`score-bar-fill ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-xs font-semibold text-slate-300 number-display">{pct}%</span>
    </div>
  );
}

// ─── Signal Badge ───────────────────────────────────────────────────────────
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

// ─── Regime Badge ───────────────────────────────────────────────────────────
function RegimeBadge({ regime }: { regime: string }) {
  const config = {
    BULL: { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", icon: "📈", desc: "Uptrend" },
    BEAR: { cls: "bg-red-500/10 text-red-400 border-red-500/20", icon: "📉", desc: "Downtrend" },
    SIDEWAYS: { cls: "bg-amber-500/10 text-amber-400 border-amber-500/20", icon: "➡️", desc: "Range-bound" },
  }[regime] || { cls: "bg-white/[0.04] text-slate-400 border-white/[0.08]", icon: "❓", desc: "" };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm font-semibold ${config.cls}`}>
      {config.icon} {regime}
      {config.desc && <span className="text-xs font-normal opacity-60">({config.desc})</span>}
    </span>
  );
}

// ─── Signal Distribution Ring ───────────────────────────────────────────────
function SignalRing({ buy, sell, hold }: { buy: number; sell: number; hold: number }) {
  const total = buy + sell + hold;
  if (total === 0) return null;

  const buyPct = (buy / total) * 100;
  const sellPct = (sell / total) * 100;
  const holdPct = (hold / total) * 100;

  return (
    <div className="flex items-center gap-6">
      <div className="relative h-24 w-24">
        <svg viewBox="0 0 36 36" className="h-24 w-24 -rotate-90 drop-shadow-lg">
          <circle cx="18" cy="18" r="14" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="3.5" />
          <circle cx="18" cy="18" r="14" fill="none" stroke="#22c55e" strokeWidth="3.5"
            strokeDasharray={`${buyPct * 0.88} ${88 - buyPct * 0.88}`} strokeDashoffset="0"
            strokeLinecap="round" className="drop-shadow-[0_0_6px_rgba(34,197,94,0.3)]" />
          <circle cx="18" cy="18" r="14" fill="none" stroke="#ef4444" strokeWidth="3.5"
            strokeDasharray={`${sellPct * 0.88} ${88 - sellPct * 0.88}`} strokeDashoffset={`${-buyPct * 0.88}`}
            strokeLinecap="round" />
          <circle cx="18" cy="18" r="14" fill="none" stroke="#f59e0b" strokeWidth="3.5"
            strokeDasharray={`${holdPct * 0.88} ${88 - holdPct * 0.88}`} strokeDashoffset={`${-(buyPct + sellPct) * 0.88}`}
            strokeLinecap="round" />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold text-white">{total}</span>
          <span className="text-[9px] text-slate-500 uppercase tracking-wider">stocks</span>
        </div>
      </div>
      <div className="space-y-2.5">
        <div className="flex items-center gap-3 text-sm">
          <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(34,197,94,0.4)]" />
          <span className="text-slate-400 w-8">Buy</span>
          <span className="font-bold text-emerald-400 number-display">{buy}</span>
          <span className="text-xs text-slate-600">({Math.round(buyPct)}%)</span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="h-2 w-2 rounded-full bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.4)]" />
          <span className="text-slate-400 w-8">Sell</span>
          <span className="font-bold text-red-400 number-display">{sell}</span>
          <span className="text-xs text-slate-600">({Math.round(sellPct)}%)</span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="h-2 w-2 rounded-full bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.4)]" />
          <span className="text-slate-400 w-8">Hold</span>
          <span className="font-bold text-amber-400 number-display">{hold}</span>
          <span className="text-xs text-slate-600">({Math.round(holdPct)}%)</span>
        </div>
      </div>
    </div>
  );
}

// ─── Strategy Weight Bar ────────────────────────────────────────────────────
const STRATEGY_COLORS: Record<string, string> = {
  ml_prediction: "bg-indigo-500",
  rl_agent: "bg-purple-500",
  momentum_breakout: "bg-emerald-500",
  mean_reversion: "bg-amber-500",
  volume_breakout: "bg-cyan-500",
  sentiment: "bg-pink-500",
};
const STRATEGY_LABELS: Record<string, string> = {
  ml_prediction: "ML Prediction",
  rl_agent: "RL Agent",
  momentum_breakout: "Momentum",
  mean_reversion: "Mean Reversion",
  volume_breakout: "Volume",
  sentiment: "Sentiment",
};
const STRATEGY_TIPS: Record<string, string> = {
  ml_prediction: "Machine learning models predict price direction",
  rl_agent: "Reinforcement learning agent learns optimal trading actions",
  momentum_breakout: "Detects strong trends using RSI, MACD, moving average crossovers",
  mean_reversion: "Finds oversold/overbought stocks likely to reverse",
  volume_breakout: "Spots unusual volume spikes that often precede big price moves",
  sentiment: "Analyzes news headlines to gauge market mood",
};

function StrategyMixPanel({ meta }: { meta: MetaStrategyStatus }) {
  const weights = meta.weights || {};
  const sorted = Object.entries(weights).sort(([, a], [, b]) => b - a);

  return (
    <div className="card animate-in">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-500/10">
            <Brain size={18} className="text-purple-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Meta-AI Strategy Mix</h2>
            <p className="text-xs text-slate-500">Auto-adjusting weights based on market conditions</p>
          </div>
        </div>
        <RegimeBadge regime={meta.regime || "SIDEWAYS"} />
      </div>

      {/* Stacked bar */}
      <div className="mb-5 flex h-6 w-full overflow-hidden rounded-full bg-white/[0.03]">
        {sorted.map(([name, w]) => (
          <div
            key={name}
            className={`${STRATEGY_COLORS[name] || "bg-slate-500"} transition-all duration-700 flex items-center justify-center first:rounded-l-full last:rounded-r-full`}
            style={{ width: `${Math.round(w * 100)}%` }}
            title={`${STRATEGY_LABELS[name] || name}: ${Math.round(w * 100)}%`}
          >
            {w > 0.12 && <span className="text-[10px] font-bold text-white/90">{Math.round(w * 100)}%</span>}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="mb-5 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
        {sorted.map(([name, w]) => (
          <div key={name} className="tooltip-trigger flex items-center gap-2">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${STRATEGY_COLORS[name] || "bg-slate-500"}`} />
            <span className="text-xs text-slate-400">
              {STRATEGY_LABELS[name] || name}{" "}
              <span className="font-bold text-slate-200">{Math.round(w * 100)}%</span>
            </span>
            <span className="tooltip-content">{STRATEGY_TIPS[name] || ""}</span>
          </div>
        ))}
      </div>

      {/* Explanation */}
      {meta.explanation && (
        <div className="rounded-xl bg-white/[0.02] border border-white/[0.05] px-4 py-3 text-sm text-slate-300">
          <Sparkles size={13} className="mr-1.5 inline text-amber-400" />
          {meta.explanation}
        </div>
      )}

      {/* Performance table */}
      {meta.performance && Object.keys(meta.performance).length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/[0.05] text-left uppercase text-slate-500">
                <th className="pb-3 pr-3 font-medium">Strategy</th>
                <th className="pb-3 pr-3 font-medium">Trades</th>
                <th className="pb-3 pr-3 font-medium">Win Rate</th>
                <th className="pb-3 pr-3 font-medium">Avg Return</th>
                <th className="pb-3 font-medium">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(meta.performance).map(([name, perf]) => (
                <tr key={name} className="border-b border-white/[0.03] table-row-hover">
                  <td className="py-2.5 pr-3 font-medium text-slate-300">
                    {STRATEGY_LABELS[name] || name}
                  </td>
                  <td className="py-2.5 pr-3 text-slate-400 number-display">{perf.trades}</td>
                  <td className="py-2.5 pr-3">
                    <span className={`number-display ${perf.win_rate >= 0.5 ? "text-emerald-400" : "text-red-400"}`}>
                      {Math.round(perf.win_rate * 100)}%
                    </span>
                  </td>
                  <td className="py-2.5 pr-3">
                    <span className={`number-display ${perf.avg_return >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {(perf.avg_return * 100).toFixed(2)}%
                    </span>
                  </td>
                  <td className="py-2.5 text-slate-300 number-display">{perf.sharpe_ratio.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Model Training Status Panel ────────────────────────────────────────────
function TrainingStatusPanel({
  training,
  onRetrain,
  retraining,
}: {
  training: TrainingStatus;
  onRetrain: () => void;
  retraining: boolean;
}) {
  const accuracyPct = Math.round((training.model_accuracy || 0) * 100);

  return (
    <div className="card animate-in">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-500/10">
            <Activity size={18} className="text-cyan-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">AI Model Status</h2>
            <p className="text-xs text-slate-500">Training history and accuracy metrics</p>
          </div>
        </div>
        <button
          onClick={onRetrain}
          disabled={retraining || training.training_in_progress}
          className="btn-secondary text-xs px-4 py-2 disabled:opacity-50"
        >
          {training.training_in_progress ? (
            <><Loader2 size={12} className="animate-spin" /> Training...</>
          ) : (
            <><RefreshCw size={12} /> Retrain Now</>
          )}
        </button>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4 stagger-in">
        <div className="rounded-xl bg-white/[0.02] border border-white/[0.05] px-3.5 py-3">
          <span className="block text-[10px] uppercase tracking-wider text-slate-500 font-medium">Version</span>
          <span className="text-lg font-bold text-white mt-1">{training.model_version || "–"}</span>
        </div>
        <div className="rounded-xl bg-white/[0.02] border border-white/[0.05] px-3.5 py-3">
          <span className="block text-[10px] uppercase tracking-wider text-slate-500 font-medium">Accuracy</span>
          <span className={`text-lg font-bold mt-1 number-display ${accuracyPct >= 55 ? "text-emerald-400" : "text-amber-400"}`}>
            {accuracyPct}%
          </span>
        </div>
        <div className="rounded-xl bg-white/[0.02] border border-white/[0.05] px-3.5 py-3">
          <span className="block text-[10px] uppercase tracking-wider text-slate-500 font-medium">Status</span>
          <span className={`text-sm font-semibold capitalize mt-1 ${
            training.status === "completed" ? "text-emerald-400" :
            training.status === "error" ? "text-red-400" :
            training.status === "training" ? "text-amber-400" : "text-slate-400"
          }`}>
            {training.status}
          </span>
        </div>
        <div className="rounded-xl bg-white/[0.02] border border-white/[0.05] px-3.5 py-3">
          <span className="block text-[10px] uppercase tracking-wider text-slate-500 font-medium">Data Points</span>
          <span className="text-sm font-semibold text-slate-300 mt-1 number-display">
            {training.model_dataset_size > 0 ? training.model_dataset_size.toLocaleString() : "–"}
          </span>
        </div>
      </div>

      {/* Version history */}
      {training.all_versions && training.all_versions.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/[0.05] text-left uppercase text-slate-500">
                <th className="pb-3 pr-3 font-medium">Version</th>
                <th className="pb-3 pr-3 font-medium">Date</th>
                <th className="pb-3 pr-3 font-medium">Accuracy</th>
                <th className="pb-3 pr-3 font-medium">AUC</th>
                <th className="pb-3 pr-3 font-medium">Sharpe</th>
                <th className="pb-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {training.all_versions.slice(-5).reverse().map((v) => (
                <tr key={v.version_id} className="border-b border-white/[0.03] table-row-hover">
                  <td className="py-2.5 pr-3 font-medium text-slate-300">{v.version_id}</td>
                  <td className="py-2.5 pr-3 text-slate-400">
                    {new Date(v.training_date).toLocaleDateString("en-IN", {
                      day: "numeric", month: "short",
                    })}
                  </td>
                  <td className="py-2.5 pr-3">
                    <span className={`number-display ${v.accuracy >= 0.55 ? "text-emerald-400" : "text-amber-400"}`}>
                      {Math.round(v.accuracy * 100)}%
                    </span>
                  </td>
                  <td className="py-2.5 pr-3 text-slate-300 number-display">{v.auc.toFixed(3)}</td>
                  <td className="py-2.5 pr-3 text-slate-300 number-display">{v.sharpe_ratio.toFixed(2)}</td>
                  <td className="py-2.5">
                    {v.deployed ? (
                      <span className="rounded-lg bg-emerald-500/10 px-2.5 py-0.5 text-emerald-400 border border-emerald-500/20 text-[10px] font-semibold">
                        LIVE
                      </span>
                    ) : (
                      <span className="text-slate-500 text-[10px]">archived</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Top Predictions Table ──────────────────────────────────────────────────
function PredictionTable({ predictions, title, emptyMsg }: { predictions: Prediction[]; title: string; emptyMsg: string }) {
  if (!predictions.length) {
    return (
      <div className="card animate-in">
        <h2 className="mb-3 text-base font-bold">{title}</h2>
        <p className="text-sm text-slate-500">{emptyMsg}</p>
      </div>
    );
  }
  return (
    <div className="card animate-in">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-base font-bold">{title}</h2>
        <Link href="/explorer" className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition font-medium">
          View all <ArrowRight size={12} />
        </Link>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.05] text-left text-[11px] uppercase text-slate-500 font-medium">
              <th className="pb-3 pr-4">#</th>
              <th className="pb-3 pr-4">Symbol</th>
              <th className="pb-3 pr-4">Signal</th>
              <th className="pb-3 pr-4">
                Confidence
                <Tip text="How sure the AI is about this prediction (0-100%)" />
              </th>
              <th className="pb-3 pr-4">
                Score
                <Tip text="Overall opportunity score combining AI, momentum, breakout, and volume signals" />
              </th>
              <th className="hidden pb-3 lg:table-cell">What the AI sees</th>
            </tr>
          </thead>
          <tbody>
            {predictions.map((p, i) => (
              <tr key={p.symbol} className="border-b border-white/[0.03] table-row-hover">
                <td className="py-3 pr-4 text-slate-600 text-xs">{i + 1}</td>
                <td className="py-3 pr-4">
                  <Link href={`/explorer?stock=${p.symbol}`} className="font-semibold text-white hover:text-indigo-400 transition">
                    {p.symbol}
                  </Link>
                </td>
                <td className="py-3 pr-4"><SignalBadge signal={p.signal} /></td>
                <td className="py-3 pr-4 text-slate-300 number-display">{Math.round(p.confidence * 100)}%</td>
                <td className="py-3 pr-4 w-32"><ScoreBar score={p.opportunity_score} label="" /></td>
                <td className="hidden py-3 text-xs text-slate-500 lg:table-cell max-w-xs truncate">{p.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Getting Started Banner ─────────────────────────────────────────────────
function GettingStartedBanner({ onFullScan, onLiteScan, scanning }: { onFullScan: () => void; onLiteScan: () => void; scanning: boolean }) {
  return (
    <div className="animate-in rounded-2xl border border-indigo-500/15 p-7 gradient-border"
      style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.08), rgba(139,92,246,0.05), rgba(6,8,15,0.9))" }}>
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-3">
          <h2 className="text-xl font-bold text-white">Welcome! Let&apos;s scan the market</h2>
          <p className="text-sm text-slate-300/80">
            Click <strong className="text-white">Lite Scan</strong> to start fast with 50 large-cap stocks, or <strong className="text-white">Full Scan</strong> to analyze 2000+ NSE stocks.
          </p>
          <div className="flex flex-wrap gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1.5"><Target size={11} className="text-indigo-400" /> Filter quality stocks</span>
            <span className="flex items-center gap-1.5"><Brain size={11} className="text-purple-400" /> Run ML models</span>
            <span className="flex items-center gap-1.5"><Zap size={11} className="text-amber-400" /> Detect breakouts</span>
            <span className="flex items-center gap-1.5"><Shield size={11} className="text-emerald-400" /> Calculate risk</span>
          </div>
        </div>
        <div className="flex flex-col gap-2.5">
          <button
            onClick={onLiteScan}
            disabled={scanning}
            className="flex items-center justify-center gap-2 whitespace-nowrap rounded-xl px-6 py-3 text-sm font-semibold text-white shadow-lg transition disabled:opacity-50"
            style={{ background: "linear-gradient(135deg, #22c55e, #10b981)", boxShadow: "0 4px 16px rgba(34,197,94,0.25)" }}
          >
            {scanning ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {scanning ? "Scanning..." : "Lite Scan (Fast)"}
          </button>
          <button
            onClick={onFullScan}
            disabled={scanning}
            className="btn-primary py-3 px-6 disabled:opacity-50"
          >
            {scanning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {scanning ? "Scanning..." : "Full Scan (2000+ stocks)"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Scan Progress Banner ───────────────────────────────────────────────────
function ScanProgressBanner({ message, isError, progress, currentStep, stocksProcessed, stocksTotal }: {
  message: string;
  isError?: boolean;
  progress?: number;
  currentStep?: string;
  stocksProcessed?: number;
  stocksTotal?: number;
}) {
  if (!message) return null;
  const isRunning = !isError && (progress !== undefined && progress < 100);
  const pct = progress ?? 0;
  return (
    <div className={`animate-in rounded-2xl border px-5 py-4 text-sm ${
      isError
        ? "border-red-500/20 bg-red-500/[0.06] text-red-300"
        : isRunning
        ? "border-indigo-500/20 bg-indigo-500/[0.06] text-indigo-300"
        : "border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-300"
    }`}>
      <div className="flex items-center gap-3">
        {isRunning && <Loader2 size={16} className="shrink-0 animate-spin" />}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-medium">{currentStep || message}</span>
            {isRunning && <span className="shrink-0 tabular-nums font-bold">{pct}%</span>}
          </div>
          {isRunning && (
            <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                className="h-full rounded-full transition-all duration-500 ease-out"
                style={{
                  width: `${pct}%`,
                  background: "linear-gradient(90deg, #6366f1, #8b5cf6, #a78bfa)",
                  boxShadow: "0 0 12px rgba(99,102,241,0.4)",
                }}
              />
            </div>
          )}
          {isRunning && stocksTotal !== undefined && stocksTotal > 0 && (
            <p className="mt-1.5 text-xs text-slate-500">
              {stocksProcessed ?? 0} / {stocksTotal} stocks processed
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Quick Actions Panel ─────────────────────────────────────────────────────
function QuickActions() {
  const actions = [
    { href: "/watchlist", icon: TrendingUp, color: "text-emerald-400", bg: "bg-emerald-500/10", hoverBorder: "hover:border-emerald-500/25", title: "Today's Picks", desc: "AI-curated watchlist" },
    { href: "/explorer", icon: BarChart3, color: "text-indigo-400", bg: "bg-indigo-500/10", hoverBorder: "hover:border-indigo-500/25", title: "Explore Stocks", desc: "Charts & indicators" },
    { href: "/paper-trading", icon: Sparkles, color: "text-purple-400", bg: "bg-purple-500/10", hoverBorder: "hover:border-purple-500/25", title: "Paper Trade", desc: "Practice risk-free" },
    { href: "/help", icon: Info, color: "text-amber-400", bg: "bg-amber-500/10", hoverBorder: "hover:border-amber-500/25", title: "Learn More", desc: "How it works" },
  ];

  return (
    <div className="card animate-in">
      <h2 className="mb-4 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Quick Links</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {actions.map((a) => (
          <Link key={a.href} href={a.href}
            className={`flex flex-col items-center gap-2.5 rounded-xl border border-white/[0.05] bg-white/[0.02] p-4 text-center transition-all duration-200 ${a.hoverBorder} hover:bg-white/[0.04]`}>
            <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${a.bg}`}>
              <a.icon size={20} className={a.color} />
            </div>
            <span className="text-xs font-semibold text-slate-200">{a.title}</span>
            <span className="text-[10px] text-slate-500">{a.desc}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

// ─── Dashboard Page ─────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [buys, setBuys] = useState<Prediction[]>([]);
  const [sells, setSells] = useState<Prediction[]>([]);
  const [topAnalyzed, setTopAnalyzed] = useState<Prediction[]>([]);
  const [meta, setMeta] = useState<MetaStrategyStatus | null>(null);
  const [training, setTraining] = useState<TrainingStatus | null>(null);
  const [retraining, setRetraining] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState("");
  const [scanProgress, setScanProgress] = useState(0);
  const [scanStep, setScanStep] = useState("");
  const [scanStocksProcessed, setScanStocksProcessed] = useState(0);
  const [scanStocksTotal, setScanStocksTotal] = useState(0);
  const [schedulerOn, setSchedulerOn] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [ov, buyList, sellList, allList] = await Promise.all([
        api.getOverview(),
        api.getPredictions("BUY"),
        api.getPredictions("SELL"),
        api.getPredictions(),
      ]);
      setOverview(ov);
      setBuys(buyList.slice(0, 20));
      setSells(sellList.slice(0, 10));
      setTopAnalyzed(allList.slice(0, 20));
      setSchedulerOn(ov.scheduler?.running ?? false);

      api.getMetaStrategy().then(setMeta).catch(() => {});
      api.getTrainingStatus().then(setTraining).catch(() => {});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load data. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    api.getScanStatus().then((status) => {
      if (status.running) {
        setScanning(true);
        setScanMsg(status.current_step || "Scan in progress…");
        setScanProgress(status.progress ?? 0);
        setScanStep(status.current_step ?? "");
        setScanStocksProcessed(status.stocks_processed ?? 0);
        setScanStocksTotal(status.stocks_total ?? 0);
        startScanPoll("Scan");
      }
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startScanPoll = (label: string) => {
    const poll = setInterval(async () => {
      try {
        const status = await api.getScanStatus();
        setScanProgress(status.progress ?? 0);
        setScanStep(status.current_step ?? "");
        setScanStocksProcessed(status.stocks_processed ?? 0);
        setScanStocksTotal(status.stocks_total ?? 0);
        if (!status.running) {
          clearInterval(poll);
          if (status.error) {
            setScanMsg(`${label} failed: ${status.error}`);
            setScanProgress(0);
            setScanStep("");
          } else {
            setScanMsg(`${label} complete! Refreshing...`);
            setScanProgress(100);
            setScanStep("Complete");
            await load();
            setTimeout(() => { setScanMsg(""); setScanProgress(0); setScanStep(""); }, 3000);
          }
          setScanning(false);
        } else {
          setScanMsg(status.current_step || `${label} in progress…`);
        }
      } catch {
        clearInterval(poll);
        setScanning(false);
        setScanMsg("");
      }
    }, 3000);
  };

  const handleFullScan = async () => {
    setScanning(true);
    setScanMsg("Full scan started — analyzing market, training AI models... this takes a few minutes.");
    try {
      await api.triggerFullScan();
      startScanPoll("Full scan");
    } catch {
      setScanMsg("Failed to start scan. Is the backend running?");
      setScanning(false);
    }
  };

  const handleQuickScan = async () => {
    setScanning(true);
    setScanMsg("Quick scan started — updating predictions for filtered stocks...");
    try {
      await api.triggerQuickScan();
      startScanPoll("Quick scan");
    } catch {
      setScanMsg("Failed to start quick scan.");
      setScanning(false);
    }
  };

  const handleLiteScan = async () => {
    setScanning(true);
    setScanMsg("Lite scan started — analyzing 30 large-cap stocks...");
    try {
      await api.triggerLiteScan();
      startScanPoll("Lite scan");
    } catch {
      setScanMsg("Failed to start lite scan.");
      setScanning(false);
    }
  };

  const toggleScheduler = async () => {
    try {
      if (schedulerOn) {
        await api.stopScheduler();
        setSchedulerOn(false);
      } else {
        await api.startScheduler();
        setSchedulerOn(true);
      }
    } catch { /* ignore */ }
  };

  const handleRetrain = async () => {
    setRetraining(true);
    try {
      await api.triggerTraining();
      const poll = setInterval(async () => {
        try {
          const st = await api.getTrainingStatus();
          setTraining(st);
          if (!st.training_in_progress) {
            clearInterval(poll);
            setRetraining(false);
          }
        } catch { /* ignore */ }
      }, 5000);
    } catch { setRetraining(false); }
  };

  // Loading skeleton
  if (loading) {
    return (
      <div className="space-y-6 animate-in">
        <div className="skeleton h-8 w-56" />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5 stagger-in">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="skeleton h-24 rounded-2xl" />)}
        </div>
        <div className="skeleton h-48 rounded-2xl" />
        <div className="skeleton h-64 rounded-2xl" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center animate-in">
        <div className="card max-w-lg text-center gradient-border">
          <div className="mb-4 text-4xl">⚠️</div>
          <h2 className="mb-2 text-lg font-bold text-red-400">Connection Error</h2>
          <p className="mb-4 text-sm text-slate-400">{error}</p>
          <p className="text-xs text-slate-500">
            Make sure the backend is running:{" "}
            <code className="rounded-lg bg-white/[0.05] px-2.5 py-1 text-indigo-400 text-xs">python -m backend.api_server</code>
          </p>
          <button onClick={load} className="btn-primary mt-5">
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const hasData = overview && overview.analyzed_today > 0;

  return (
    <div className="space-y-7 animate-in">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Market Overview</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            AI-powered scanning of 2000+ NSE stocks
            {overview?.last_scan && (
              <> &middot; Last scan: {new Date(String(overview.last_scan.finished_at || overview.last_scan.started_at)).toLocaleString("en-IN")}</>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleLiteScan}
            disabled={scanning}
            className="btn-secondary text-xs px-3.5 py-2 text-emerald-400 border-emerald-500/20 hover:border-emerald-500/30 hover:bg-emerald-500/[0.06] disabled:opacity-50"
          >
            <Sparkles size={13} /> Lite
          </button>
          <button
            onClick={handleQuickScan}
            disabled={scanning}
            className="btn-secondary text-xs px-3.5 py-2 disabled:opacity-50"
          >
            <Zap size={13} /> Quick
          </button>
          <button
            onClick={handleFullScan}
            disabled={scanning}
            className="btn-primary text-xs px-4 py-2 disabled:opacity-50"
          >
            {scanning ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            Full Scan
          </button>
          <button
            onClick={toggleScheduler}
            className={`btn-secondary text-xs px-3.5 py-2 ${
              schedulerOn
                ? "text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/[0.06]"
                : ""
            }`}
            title={schedulerOn ? "Auto-scan every 30 min during market hours" : "Turn on automatic scanning"}
          >
            {schedulerOn ? <Pause size={13} /> : <Play size={13} />}
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${schedulerOn ? "bg-emerald-400 pulse-dot" : "bg-slate-600"}`} />
            Auto {schedulerOn ? "ON" : "OFF"}
          </button>
        </div>
      </div>

      {/* Scan progress */}
      <ScanProgressBanner
        message={scanMsg}
        isError={scanMsg.includes("failed") || scanMsg.includes("Error")}
        progress={scanProgress}
        currentStep={scanStep}
        stocksProcessed={scanStocksProcessed}
        stocksTotal={scanStocksTotal}
      />

      {/* Getting started banner when no data */}
      {!hasData && !scanning && <GettingStartedBanner onFullScan={handleFullScan} onLiteScan={handleLiteScan} scanning={scanning} />}

      {/* Stats Grid */}
      {overview && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 stagger-in">
          <StatCard label="Stocks Scanned" value={overview.total_stocks} icon={BarChart3}
            tip="Total NSE stocks that were downloaded and checked for quality" />
          <StatCard label="Analyzed Today" value={overview.analyzed_today} icon={Brain}
            tip="Stocks that passed quality filters and received AI predictions" />
          <StatCard label="Buy Signals" value={overview.buy_signals} icon={TrendingUp} color="text-green-400"
            tip="Stocks where AI recommends buying — multiple strategies agree on upward potential" />
          <StatCard label="Sell Signals" value={overview.sell_signals} icon={TrendingDown} color="text-red-400"
            tip="Stocks showing bearish signals — consider avoiding or exiting" />
          <StatCard label="Avg Confidence" value={`${Math.round((overview.avg_confidence || 0) * 100)}%`} icon={Target} color="text-blue-400"
            tip="Average confidence across all predictions. Higher = the AI is more sure of its calls" />
        </div>
      )}

      {/* Signal Distribution + Quick Actions */}
      {hasData && overview && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card animate-in">
            <div className="flex items-center gap-2.5 mb-5">
              <h2 className="text-base font-bold">Signal Distribution</h2>
              <Tip text="Shows how many stocks the AI recommends to Buy, Sell, or Hold. Mostly Buy signals = bullish market." />
            </div>
            <SignalRing buy={overview.buy_signals} sell={overview.sell_signals} hold={overview.hold_signals} />
          </div>
          <QuickActions />
        </div>
      )}

      {/* Quick Actions when no data */}
      {!hasData && <QuickActions />}

      {/* Meta-AI Strategy Mix */}
      {meta && <StrategyMixPanel meta={meta} />}

      {/* Model Training Status */}
      {training && (
        <TrainingStatusPanel training={training} onRetrain={handleRetrain} retraining={retraining} />
      )}

      {/* Top Buys */}
      <PredictionTable
        predictions={buys}
        title="🟢 Top Buy Opportunities"
        emptyMsg="No buy signals yet. Run a Full Scan to analyze the market."
      />

      {/* Top Sells */}
      <PredictionTable
        predictions={sells}
        title="🔴 Top Sell / Avoid"
        emptyMsg="No sell signals yet. Run a Full Scan first."
      />

      {/* Top Analyzed — always shown when buys & sells are empty */}
      {buys.length === 0 && sells.length === 0 && topAnalyzed.length > 0 && (
        <PredictionTable
          predictions={topAnalyzed}
          title="📊 Top Analyzed Stocks"
          emptyMsg=""
        />
      )}
    </div>
  );
}
