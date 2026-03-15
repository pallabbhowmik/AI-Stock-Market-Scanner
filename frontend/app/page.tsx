"use client";

import { useEffect, useState } from "react";
import { api, Overview, Prediction, MetaStrategyStatus, TrainingStatus } from "@/lib/api";

// ─── Stat Card ──────────────────────────────────────────────────────────────
function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="card flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wider text-slate-400">{label}</span>
      <span className={`text-2xl font-bold ${color || "text-white"}`}>{value}</span>
    </div>
  );
}

// ─── Score Bar ──────────────────────────────────────────────────────────────
function ScoreBar({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  const barColor =
    pct >= 70 ? "bg-buy" : pct >= 40 ? "bg-hold" : "bg-sell";
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-xs text-slate-400">{label}</span>
      <div className="score-bar flex-1">
        <div className={`score-bar-fill ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-xs font-medium text-slate-300">{pct}%</span>
    </div>
  );
}

// ─── Signal Badge ───────────────────────────────────────────────────────────
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

// ─── Regime Badge ───────────────────────────────────────────────────────────
function RegimeBadge({ regime }: { regime: string }) {
  const cls =
    regime === "BULL"
      ? "bg-green-900/60 text-green-400 border-green-700"
      : regime === "BEAR"
      ? "bg-red-900/60 text-red-400 border-red-700"
      : "bg-yellow-900/60 text-yellow-400 border-yellow-700";
  const icon = regime === "BULL" ? "📈" : regime === "BEAR" ? "📉" : "➡️";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold ${cls}`}>
      {icon} {regime}
    </span>
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

function StrategyMixPanel({ meta }: { meta: MetaStrategyStatus }) {
  const weights = meta.weights || {};
  const sorted = Object.entries(weights).sort(([, a], [, b]) => b - a);

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">🧠 Meta-AI Strategy Mix</h2>
        <RegimeBadge regime={meta.regime || "SIDEWAYS"} />
      </div>

      {/* Stacked bar */}
      <div className="mb-4 flex h-6 w-full overflow-hidden rounded-full">
        {sorted.map(([name, w]) => (
          <div
            key={name}
            className={`${STRATEGY_COLORS[name] || "bg-slate-500"} transition-all`}
            style={{ width: `${Math.round(w * 100)}%` }}
            title={`${STRATEGY_LABELS[name] || name}: ${Math.round(w * 100)}%`}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {sorted.map(([name, w]) => (
          <div key={name} className="flex items-center gap-2">
            <span className={`inline-block h-3 w-3 rounded-full ${STRATEGY_COLORS[name] || "bg-slate-500"}`} />
            <span className="text-xs text-slate-400">
              {STRATEGY_LABELS[name] || name}{" "}
              <span className="font-semibold text-slate-200">{Math.round(w * 100)}%</span>
            </span>
          </div>
        ))}
      </div>

      {/* Explanation */}
      {meta.explanation && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 text-sm text-slate-300">
          💡 {meta.explanation}
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
  const STATUS_COLORS: Record<string, string> = {
    idle: "text-slate-400",
    collecting_data: "text-blue-400",
    training: "text-yellow-400",
    evaluating: "text-purple-400",
    deploying: "text-cyan-400",
    completed: "text-green-400",
    error: "text-red-400",
  };

  const accuracyPct = Math.round((training.model_accuracy || 0) * 100);

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">🤖 Model Training Status</h2>
        <button
          onClick={onRetrain}
          disabled={retraining || training.training_in_progress}
          className="rounded-lg bg-purple-700 px-4 py-1.5 text-xs font-medium text-white transition hover:bg-purple-600 disabled:opacity-50"
        >
          {training.training_in_progress ? "Training..." : "Retrain Now"}
        </button>
      </div>

      {/* Key metrics */}
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2">
          <span className="block text-xs text-slate-500">Version</span>
          <span className="text-lg font-bold text-white">{training.model_version || "–"}</span>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2">
          <span className="block text-xs text-slate-500">Accuracy</span>
          <span className={`text-lg font-bold ${accuracyPct >= 55 ? "text-green-400" : "text-yellow-400"}`}>
            {accuracyPct}%
          </span>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2">
          <span className="block text-xs text-slate-500">Status</span>
          <span className={`text-sm font-semibold capitalize ${STATUS_COLORS[training.status] || "text-slate-400"}`}>
            {training.status}
          </span>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2">
          <span className="block text-xs text-slate-500">Last Training</span>
          <span className="text-sm text-slate-300">
            {training.last_training
              ? new Date(training.last_training).toLocaleString("en-IN", {
                  day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
                })
              : "–"}
          </span>
        </div>
      </div>

      {/* Explanation */}
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 text-sm text-slate-300">
        💡 The AI model retrains itself automatically every day using the latest market data.
        {training.model_dataset_size > 0 && (
          <span className="text-slate-400">
            {" "}Currently trained on {training.model_dataset_size.toLocaleString()} data points.
          </span>
        )}
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
function PredictionTable({ predictions, title }: { predictions: Prediction[]; title: string }) {
  if (!predictions.length) return null;
  return (
    <div className="card">
      <h2 className="mb-4 text-lg font-semibold">{title}</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-left text-xs uppercase text-slate-400">
              <th className="pb-2 pr-4">#</th>
              <th className="pb-2 pr-4">Symbol</th>
              <th className="pb-2 pr-4">Signal</th>
              <th className="pb-2 pr-4">Confidence</th>
              <th className="pb-2 pr-4">Score</th>
              <th className="pb-2">Explanation</th>
            </tr>
          </thead>
          <tbody>
            {predictions.map((p, i) => (
              <tr key={p.symbol} className="border-b border-slate-800 transition hover:bg-slate-700/30">
                <td className="py-2.5 pr-4 text-slate-500">{i + 1}</td>
                <td className="py-2.5 pr-4 font-medium text-white">{p.symbol}</td>
                <td className="py-2.5 pr-4">
                  <SignalBadge signal={p.signal} />
                </td>
                <td className="py-2.5 pr-4 text-slate-300">{Math.round(p.confidence * 100)}%</td>
                <td className="py-2.5 pr-4">
                  <ScoreBar score={p.opportunity_score} label="" />
                </td>
                <td className="py-2.5 text-xs text-slate-400">{p.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
  const [schedulerOn, setSchedulerOn] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [ov, buyList, sellList] = await Promise.all([
        api.getOverview(),
        api.getPredictions("BUY"),
        api.getPredictions("SELL"),
      ]);
      setOverview(ov);
      setBuys(buyList.slice(0, 20));
      setSells(sellList.slice(0, 10));
      setSchedulerOn(ov.scheduler?.running ?? false);

      // Load meta-strategy and training status (non-blocking)
      api.getMetaStrategy().then(setMeta).catch(() => {});
      api.getTrainingStatus().then(setTraining).catch(() => {});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load data. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleFullScan = async () => {
    setScanning(true);
    setScanMsg("Full scan started... this takes a few minutes.");
    try {
      await api.triggerFullScan();
      setScanMsg("Scan complete! Refreshing...");
      await load();
      setScanMsg("");
    } catch {
      setScanMsg("Scan failed. Check backend logs.");
    }
    setScanning(false);
  };

  const handleQuickScan = async () => {
    setScanning(true);
    setScanMsg("Quick scan started...");
    try {
      await api.triggerQuickScan();
      setScanMsg("Quick scan complete! Refreshing...");
      await load();
      setScanMsg("");
    } catch {
      setScanMsg("Quick scan failed.");
    }
    setScanning(false);
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
      // Poll for completion
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
    } catch {
      setRetraining(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="mb-4 text-4xl">📊</div>
          <p className="text-slate-400">Loading market data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="card max-w-lg text-center">
          <div className="mb-4 text-4xl">⚠️</div>
          <h2 className="mb-2 text-lg font-semibold text-red-400">Connection Error</h2>
          <p className="mb-4 text-sm text-slate-400">{error}</p>
          <p className="text-xs text-slate-500">
            Make sure the backend is running: <code className="rounded bg-slate-700 px-2 py-0.5">python -m backend.api_server</code>
          </p>
          <button onClick={load} className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm text-white transition hover:bg-blue-600">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
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
        <div className="flex items-center gap-3">
          <button
            onClick={handleQuickScan}
            disabled={scanning}
            className="rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-sm text-white transition hover:bg-slate-600 disabled:opacity-50"
          >
            Quick Scan
          </button>
          <button
            onClick={handleFullScan}
            disabled={scanning}
            className="rounded-lg bg-accent px-4 py-2 text-sm text-white transition hover:bg-blue-600 disabled:opacity-50"
          >
            Full Scan
          </button>
          <button
            onClick={toggleScheduler}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition ${
              schedulerOn
                ? "bg-green-900/40 text-green-400 border border-green-700 hover:bg-green-900/60"
                : "bg-slate-700 text-slate-300 border border-slate-600 hover:bg-slate-600"
            }`}
          >
            <span className={`inline-block h-2 w-2 rounded-full ${schedulerOn ? "bg-green-400 pulse-dot" : "bg-slate-500"}`} />
            Auto {schedulerOn ? "ON" : "OFF"}
          </button>
        </div>
      </div>

      {scanMsg && (
        <div className="rounded-lg border border-blue-800 bg-blue-900/30 px-4 py-3 text-sm text-blue-300">
          {scanMsg}
        </div>
      )}

      {/* Stats Grid */}
      {overview && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Stocks Scanned" value={overview.total_stocks} />
          <StatCard label="Analyzed Today" value={overview.analyzed_today} />
          <StatCard label="Buy Signals" value={overview.buy_signals} color="text-green-400" />
          <StatCard label="Sell Signals" value={overview.sell_signals} color="text-red-400" />
          <StatCard label="Hold Signals" value={overview.hold_signals} color="text-yellow-400" />
        </div>
      )}

      {/* Meta-AI Strategy Mix */}
      {meta && <StrategyMixPanel meta={meta} />}

      {/* Model Training Status */}
      {training && (
        <TrainingStatusPanel
          training={training}
          onRetrain={handleRetrain}
          retraining={retraining}
        />
      )}

      {/* Top Buys */}
      <PredictionTable predictions={buys} title="🟢 Top Buy Opportunities" />

      {/* Top Sells */}
      <PredictionTable predictions={sells} title="🔴 Top Sell / Avoid" />
    </div>
  );
}
