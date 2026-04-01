"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
    <div className="card-hover flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wider text-slate-400">
          {label}
          {tip && <Tip text={tip} />}
        </span>
        <Icon size={16} className={color || "text-slate-500"} />
      </div>
      <span className={`text-2xl font-bold ${color || "text-white"}`}>{value}</span>
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
      <span className="w-10 text-right text-xs font-medium text-slate-300">{pct}%</span>
    </div>
  );
}

// ─── Signal Badge ───────────────────────────────────────────────────────────
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

// ─── Regime Badge ───────────────────────────────────────────────────────────
function RegimeBadge({ regime }: { regime: string }) {
  const config = {
    BULL: { cls: "bg-green-900/60 text-green-400 border-green-700", icon: "📈", desc: "Uptrend" },
    BEAR: { cls: "bg-red-900/60 text-red-400 border-red-700", icon: "📉", desc: "Downtrend" },
    SIDEWAYS: { cls: "bg-yellow-900/60 text-yellow-400 border-yellow-700", icon: "➡️", desc: "Range-bound" },
  }[regime] || { cls: "bg-slate-800 text-slate-400 border-slate-600", icon: "❓", desc: "" };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold ${config.cls}`}>
      {config.icon} {regime}
      {config.desc && <span className="text-xs font-normal opacity-70">({config.desc})</span>}
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
    <div className="flex items-center gap-4">
      <div className="relative h-20 w-20">
        <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
          <circle cx="18" cy="18" r="14" fill="none" stroke="#16a34a" strokeWidth="4"
            strokeDasharray={`${buyPct * 0.88} ${88 - buyPct * 0.88}`} strokeDashoffset="0" />
          <circle cx="18" cy="18" r="14" fill="none" stroke="#dc2626" strokeWidth="4"
            strokeDasharray={`${sellPct * 0.88} ${88 - sellPct * 0.88}`} strokeDashoffset={`${-buyPct * 0.88}`} />
          <circle cx="18" cy="18" r="14" fill="none" stroke="#eab308" strokeWidth="4"
            strokeDasharray={`${holdPct * 0.88} ${88 - holdPct * 0.88}`} strokeDashoffset={`${-(buyPct + sellPct) * 0.88}`} />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold text-white">{total}</span>
        </div>
      </div>
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 text-sm">
          <span className="h-2.5 w-2.5 rounded-full bg-buy" />
          <span className="text-slate-400">Buy</span>
          <span className="font-semibold text-green-400">{buy} ({Math.round(buyPct)}%)</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="h-2.5 w-2.5 rounded-full bg-sell" />
          <span className="text-slate-400">Sell</span>
          <span className="font-semibold text-red-400">{sell} ({Math.round(sellPct)}%)</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="h-2.5 w-2.5 rounded-full bg-hold" />
          <span className="text-slate-400">Hold</span>
          <span className="font-semibold text-yellow-400">{hold} ({Math.round(holdPct)}%)</span>
        </div>
      </div>
    </div>
  );
}

// ─── Strategy Weight Bar ────────────────────────────────────────────────────
const STRATEGY_COLORS: Record<string, string> = {
  ml_prediction: "bg-blue-500",
  rl_agent: "bg-purple-500",
  momentum_breakout: "bg-green-500",
  mean_reversion: "bg-yellow-500",
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
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Brain size={20} className="text-purple-400" />
          <h2 className="text-lg font-semibold">Meta-AI Strategy Mix</h2>
          <Tip text="The Meta-AI automatically adjusts how much weight each strategy gets based on current market conditions." />
        </div>
        <RegimeBadge regime={meta.regime || "SIDEWAYS"} />
      </div>

      {/* Stacked bar */}
      <div className="mb-4 flex h-8 w-full overflow-hidden rounded-full">
        {sorted.map(([name, w]) => (
          <div
            key={name}
            className={`${STRATEGY_COLORS[name] || "bg-slate-500"} transition-all duration-500 flex items-center justify-center`}
            style={{ width: `${Math.round(w * 100)}%` }}
            title={`${STRATEGY_LABELS[name] || name}: ${Math.round(w * 100)}%`}
          >
            {w > 0.12 && <span className="text-[10px] font-bold text-white/90">{Math.round(w * 100)}%</span>}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {sorted.map(([name, w]) => (
          <div key={name} className="tooltip-trigger flex items-center gap-2">
            <span className={`inline-block h-3 w-3 rounded-full ${STRATEGY_COLORS[name] || "bg-slate-500"}`} />
            <span className="text-xs text-slate-400">
              {STRATEGY_LABELS[name] || name}{" "}
              <span className="font-semibold text-slate-200">{Math.round(w * 100)}%</span>
            </span>
            <span className="tooltip-content">{STRATEGY_TIPS[name] || ""}</span>
          </div>
        ))}
      </div>

      {/* Explanation */}
      {meta.explanation && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 text-sm text-slate-300">
          <Sparkles size={14} className="mr-1.5 inline text-yellow-400" />
          {meta.explanation}
        </div>
      )}

      {/* Performance table */}
      {meta.performance && Object.keys(meta.performance).length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-left uppercase text-slate-500">
                <th className="pb-2 pr-3">Strategy</th>
                <th className="pb-2 pr-3">Trades</th>
                <th className="pb-2 pr-3">Win Rate</th>
                <th className="pb-2 pr-3">Avg Return</th>
                <th className="pb-2">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(meta.performance).map(([name, perf]) => (
                <tr key={name} className="border-b border-slate-800">
                  <td className="py-2 pr-3 font-medium text-slate-300">
                    {STRATEGY_LABELS[name] || name}
                  </td>
                  <td className="py-2 pr-3 text-slate-400">{perf.trades}</td>
                  <td className="py-2 pr-3">
                    <span className={perf.win_rate >= 0.5 ? "text-green-400" : "text-red-400"}>
                      {Math.round(perf.win_rate * 100)}%
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    <span className={perf.avg_return >= 0 ? "text-green-400" : "text-red-400"}>
                      {(perf.avg_return * 100).toFixed(2)}%
                    </span>
                  </td>
                  <td className="py-2 text-slate-300">{perf.sharpe_ratio.toFixed(2)}</td>
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
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Activity size={20} className="text-cyan-400" />
          <h2 className="text-lg font-semibold">AI Model Status</h2>
          <Tip text="The AI model retrains using latest market data. Higher accuracy = better predictions, but past performance doesn&apos;t guarantee future results." />
        </div>
        <button
          onClick={onRetrain}
          disabled={retraining || training.training_in_progress}
          className="flex items-center gap-1.5 rounded-lg bg-purple-700 px-4 py-1.5 text-xs font-medium text-white transition hover:bg-purple-600 disabled:opacity-50"
        >
          {training.training_in_progress ? (
            <><Loader2 size={12} className="animate-spin" /> Training...</>
          ) : (
            <><RefreshCw size={12} /> Retrain Now</>
          )}
        </button>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2">
          <span className="block text-xs text-slate-500">Version</span>
          <span className="text-lg font-bold text-white">{training.model_version || "–"}</span>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2">
          <span className="block text-xs text-slate-500">Accuracy <Tip text="How often the model correctly predicts if a stock will go up or down" /></span>
          <span className={`text-lg font-bold ${accuracyPct >= 55 ? "text-green-400" : "text-yellow-400"}`}>
            {accuracyPct}%
          </span>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2">
          <span className="block text-xs text-slate-500">Status</span>
          <span className={`text-sm font-semibold capitalize ${
            training.status === "completed" ? "text-green-400" :
            training.status === "error" ? "text-red-400" :
            training.status === "training" ? "text-yellow-400" : "text-slate-400"
          }`}>
            {training.status}
          </span>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2">
          <span className="block text-xs text-slate-500">Data Points</span>
          <span className="text-sm text-slate-300">
            {training.model_dataset_size > 0 ? training.model_dataset_size.toLocaleString() : "–"}
          </span>
        </div>
      </div>

      {/* Version history (last 5) */}
      {training.all_versions && training.all_versions.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-left uppercase text-slate-500">
                <th className="pb-2 pr-3">Version</th>
                <th className="pb-2 pr-3">Date</th>
                <th className="pb-2 pr-3">Accuracy</th>
                <th className="pb-2 pr-3">AUC</th>
                <th className="pb-2 pr-3">Sharpe</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {training.all_versions.slice(-5).reverse().map((v) => (
                <tr key={v.version_id} className="border-b border-slate-800">
                  <td className="py-2 pr-3 font-medium text-slate-300">{v.version_id}</td>
                  <td className="py-2 pr-3 text-slate-400">
                    {new Date(v.training_date).toLocaleDateString("en-IN", {
                      day: "numeric", month: "short",
                    })}
                  </td>
                  <td className="py-2 pr-3">
                    <span className={v.accuracy >= 0.55 ? "text-green-400" : "text-yellow-400"}>
                      {Math.round(v.accuracy * 100)}%
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-slate-300">{v.auc.toFixed(3)}</td>
                  <td className="py-2 pr-3 text-slate-300">{v.sharpe_ratio.toFixed(2)}</td>
                  <td className="py-2">
                    {v.deployed ? (
                      <span className="rounded-full bg-green-900/60 px-2 py-0.5 text-green-400 border border-green-700 text-[10px]">
                        LIVE
                      </span>
                    ) : (
                      <span className="text-slate-500">archived</span>
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
        <h2 className="mb-3 text-lg font-semibold">{title}</h2>
        <p className="text-sm text-slate-500">{emptyMsg}</p>
      </div>
    );
  }
  return (
    <div className="card animate-in">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">{title}</h2>
        <Link href="/explorer" className="flex items-center gap-1 text-xs text-accent hover:underline">
          View all <ArrowRight size={12} />
        </Link>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-left text-xs uppercase text-slate-400">
              <th className="pb-2 pr-4">#</th>
              <th className="pb-2 pr-4">Symbol</th>
              <th className="pb-2 pr-4">Signal</th>
              <th className="pb-2 pr-4">
                Confidence
                <Tip text="How sure the AI is about this prediction (0-100%)" />
              </th>
              <th className="pb-2 pr-4">
                Score
                <Tip text="Overall opportunity score combining AI, momentum, breakout, and volume signals" />
              </th>
              <th className="hidden pb-2 lg:table-cell">What the AI sees</th>
            </tr>
          </thead>
          <tbody>
            {predictions.map((p, i) => (
              <tr key={p.symbol} className="border-b border-slate-800 transition hover:bg-slate-700/30">
                <td className="py-2.5 pr-4 text-slate-500">{i + 1}</td>
                <td className="py-2.5 pr-4">
                  <Link href={`/explorer?stock=${p.symbol}`} className="font-medium text-white hover:text-accent transition">
                    {p.symbol}
                  </Link>
                </td>
                <td className="py-2.5 pr-4"><SignalBadge signal={p.signal} /></td>
                <td className="py-2.5 pr-4 text-slate-300">{Math.round(p.confidence * 100)}%</td>
                <td className="py-2.5 pr-4 w-32"><ScoreBar score={p.opportunity_score} label="" /></td>
                <td className="hidden py-2.5 text-xs text-slate-400 lg:table-cell max-w-xs truncate">{p.explanation}</td>
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
    <div className="animate-in rounded-xl border border-blue-700/30 bg-gradient-to-r from-blue-900/30 via-purple-900/20 to-slate-900 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <h2 className="text-xl font-bold text-white">Welcome! Let&apos;s scan the market</h2>
          <p className="text-sm text-slate-300">
            Click <strong>Lite Scan</strong> to start fast with 50 large-cap stocks, or <strong>Full Scan</strong> to analyze 2000+ NSE stocks.
          </p>
          <div className="flex flex-wrap gap-3 text-xs text-slate-400">
            <span className="flex items-center gap-1"><Target size={12} className="text-blue-400" /> Filter quality stocks</span>
            <span className="flex items-center gap-1"><Brain size={12} className="text-purple-400" /> Run ML models</span>
            <span className="flex items-center gap-1"><Zap size={12} className="text-yellow-400" /> Detect breakouts</span>
            <span className="flex items-center gap-1"><Shield size={12} className="text-green-400" /> Calculate risk</span>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <button
            onClick={onLiteScan}
            disabled={scanning}
            className="flex items-center gap-2 whitespace-nowrap rounded-lg bg-gradient-to-r from-green-600 to-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-green-900/30 transition hover:from-green-500 hover:to-emerald-500 disabled:opacity-50"
          >
            {scanning ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {scanning ? "Scanning..." : "Lite Scan (Fast)"}
          </button>
          <button
            onClick={onFullScan}
            disabled={scanning}
            className="flex items-center gap-2 whitespace-nowrap rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-900/30 transition hover:from-blue-500 hover:to-purple-500 disabled:opacity-50"
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
    <div className={`animate-in rounded-lg border px-4 py-3 text-sm ${
      isError
        ? "border-red-800 bg-red-900/30 text-red-300"
        : isRunning
        ? "border-blue-800 bg-blue-900/30 text-blue-300"
        : "border-green-800 bg-green-900/30 text-green-300"
    }`}>
      <div className="flex items-center gap-3">
        {isRunning && <Loader2 size={16} className="shrink-0 animate-spin" />}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-medium">{currentStep || message}</span>
            {isRunning && <span className="shrink-0 tabular-nums font-semibold">{pct}%</span>}
          </div>
          {isRunning && (
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-700/60">
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
          )}
          {isRunning && stocksTotal !== undefined && stocksTotal > 0 && (
            <p className="mt-1 text-xs text-slate-400">
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
  return (
    <div className="card animate-in">
      <h2 className="mb-3 text-sm font-semibold text-slate-400 uppercase tracking-wider">Quick Links</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Link href="/watchlist" className="flex flex-col items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-center transition hover:border-green-600/50 hover:bg-green-900/10">
          <TrendingUp size={24} className="text-green-400" />
          <span className="text-xs font-medium text-slate-300">Today&apos;s Picks</span>
          <span className="text-[10px] text-slate-500">AI-curated watchlist</span>
        </Link>
        <Link href="/explorer" className="flex flex-col items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-center transition hover:border-blue-600/50 hover:bg-blue-900/10">
          <BarChart3 size={24} className="text-blue-400" />
          <span className="text-xs font-medium text-slate-300">Explore Stocks</span>
          <span className="text-[10px] text-slate-500">Charts & indicators</span>
        </Link>
        <Link href="/paper-trading" className="flex flex-col items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-center transition hover:border-purple-600/50 hover:bg-purple-900/10">
          <Sparkles size={24} className="text-purple-400" />
          <span className="text-xs font-medium text-slate-300">Paper Trade</span>
          <span className="text-[10px] text-slate-500">Practice risk-free</span>
        </Link>
        <Link href="/help" className="flex flex-col items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-center transition hover:border-yellow-600/50 hover:bg-yellow-900/10">
          <Info size={24} className="text-yellow-400" />
          <span className="text-xs font-medium text-slate-300">Learn More</span>
          <span className="text-[10px] text-slate-500">How it works</span>
        </Link>
      </div>
    </div>
  );
}

// ─── Dashboard Page ─────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [buys, setBuys] = useState<Prediction[]>([]);
  const [sells, setSells] = useState<Prediction[]>([]);
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
  const scanPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const trainingPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopScanPoll = useCallback(() => {
    if (scanPollRef.current) {
      clearInterval(scanPollRef.current);
      scanPollRef.current = null;
    }
  }, []);

  const stopTrainingPoll = useCallback(() => {
    if (trainingPollRef.current) {
      clearInterval(trainingPollRef.current);
      trainingPollRef.current = null;
    }
  }, []);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const dashboard = await api.getDashboard();
      setOverview(dashboard.overview);
      setBuys(dashboard.buys);
      setSells(dashboard.sells);
      setMeta(dashboard.meta);
      setTraining(dashboard.training);
      setSchedulerOn(dashboard.overview.scheduler?.running ?? false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load data. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

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
    return () => {
      stopScanPoll();
      stopTrainingPoll();
    };
  }, [load, stopScanPoll, stopTrainingPoll]);

  const startScanPoll = useCallback((label: string) => {
    stopScanPoll();
    scanPollRef.current = setInterval(async () => {
      try {
        const status = await api.getScanStatus();
        setScanProgress(status.progress ?? 0);
        setScanStep(status.current_step ?? "");
        setScanStocksProcessed(status.stocks_processed ?? 0);
        setScanStocksTotal(status.stocks_total ?? 0);
        if (!status.running) {
          stopScanPoll();
          if (status.error) {
            setScanMsg(`${label} failed: ${status.error}`);
            setScanProgress(0);
            setScanStep("");
          } else {
            setScanMsg(`${label} complete! Refreshing...`);
            setScanProgress(100);
            setScanStep("Complete");
            api.clearCache();
            await load();
            setTimeout(() => { setScanMsg(""); setScanProgress(0); setScanStep(""); }, 3000);
          }
          setScanning(false);
        } else {
          setScanMsg(status.current_step || `${label} in progress…`);
        }
      } catch {
        // If API is unreachable, stop polling
        stopScanPoll();
        setScanning(false);
        setScanMsg("");
      }
    }, 3000);
  }, [load, stopScanPoll]);

  const handleFullScan = async () => {
    setScanning(true);
    setScanMsg("Full scan started — analyzing market, training AI models... this takes a few minutes.");
    try {
      await api.triggerFullScan();
      setScanMsg("Full scan started - analyzing the market with existing models and saving results chunk by chunk.");
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
      api.clearCache();
      load();
    } catch { /* ignore */ }
  };

  const handleRetrain = async () => {
    setRetraining(true);
    try {
      await api.triggerTraining();
      stopTrainingPoll();
      trainingPollRef.current = setInterval(async () => {
        try {
          const st = await api.getTrainingStatus();
          setTraining(st);
          if (!st.training_in_progress) {
            stopTrainingPoll();
            setRetraining(false);
            api.clearCache();
            load();
          }
        } catch { /* ignore */ }
      }, 5000);
    } catch { setRetraining(false); }
  };

  // Loading skeleton
  if (loading) {
    return (
      <div className="space-y-6 animate-in">
        <div className="skeleton h-8 w-48" />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="skeleton h-20 rounded-xl" />)}
        </div>
        <div className="skeleton h-48 rounded-xl" />
        <div className="skeleton h-64 rounded-xl" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center animate-in">
        <div className="card max-w-lg text-center">
          <div className="mb-4 text-4xl">⚠️</div>
          <h2 className="mb-2 text-lg font-semibold text-red-400">Connection Error</h2>
          <p className="mb-4 text-sm text-slate-400">{error}</p>
          <p className="text-xs text-slate-500">
            Make sure the backend is running:{" "}
            <code className="rounded bg-slate-700 px-2 py-0.5 text-accent">python -m backend.api_server</code>
          </p>
          <button onClick={load} className="mt-4 rounded-lg bg-accent px-6 py-2 text-sm font-medium text-white transition hover:bg-blue-600">
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const hasData = overview && overview.analyzed_today > 0;

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Market Overview</h1>
          <p className="text-sm text-slate-400">
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
            className="flex items-center gap-1.5 rounded-lg border border-green-700 bg-green-900/40 px-4 py-2 text-sm text-green-400 transition hover:bg-green-900/60 disabled:opacity-50"
          >
            <Sparkles size={14} /> Lite Scan
          </button>
          <button
            onClick={handleQuickScan}
            disabled={scanning}
            className="flex items-center gap-1.5 rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-sm text-white transition hover:bg-slate-600 disabled:opacity-50"
          >
            <Zap size={14} /> Quick Scan
          </button>
          <button
            onClick={handleFullScan}
            disabled={scanning}
            className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-600 disabled:opacity-50"
          >
            {scanning ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Full Scan
          </button>
          <button
            onClick={toggleScheduler}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition ${
              schedulerOn
                ? "bg-green-900/40 text-green-400 border border-green-700 hover:bg-green-900/60"
                : "bg-slate-700 text-slate-300 border border-slate-600 hover:bg-slate-600"
            }`}
            title={schedulerOn ? "Auto-scan every 30 min during market hours" : "Turn on automatic scanning"}
          >
            {schedulerOn ? <Pause size={14} /> : <Play size={14} />}
            <span className={`inline-block h-2 w-2 rounded-full ${schedulerOn ? "bg-green-400 pulse-dot" : "bg-slate-500"}`} />
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
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
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
            <div className="flex items-center gap-2 mb-4">
              <h2 className="text-lg font-semibold">Signal Distribution</h2>
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
    </div>
  );
}
