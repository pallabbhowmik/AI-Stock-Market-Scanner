"use client";

import { useEffect, useState, useCallback } from "react";
import {
  api,
  PaperPortfolio,
  PaperTrade,
  PaperPerformance,
} from "../../lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

/* ── Formatting helpers ─────────────────────────────────────────────────── */

function fmt(n: number, decimals = 2) {
  return n.toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
function fmtPct(n: number) {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}
function clr(n: number) {
  return n > 0 ? "text-green-400" : n < 0 ? "text-red-400" : "text-slate-300";
}

/* ── Stat Card ──────────────────────────────────────────────────────────── */

function Stat({ label, value, sub, color }: {
  label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <div className="card flex flex-col gap-1">
      <span className="text-xs text-slate-400">{label}</span>
      <span className={`text-xl font-bold ${color || "text-white"}`}>{value}</span>
      {sub && <span className={`text-xs ${color || "text-slate-400"}`}>{sub}</span>}
    </div>
  );
}

/* ── Order Form ─────────────────────────────────────────────────────────── */

function OrderForm({ onSuccess }: { onSuccess: () => void }) {
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState("BUY");
  const [qty, setQty] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const submit = async () => {
    if (!symbol.trim()) return;
    setBusy(true);
    setMsg("");
    try {
      const res = await api.placePaperOrder({
        symbol: symbol.trim().toUpperCase(),
        side,
        quantity: qty || undefined,
      });
      if (res.status === "filled") {
        setMsg(`✓ ${res.side} ${res.quantity} × ${res.symbol} @ ₹${fmt(res.price)}`);
        setSymbol("");
        setQty(0);
        onSuccess();
      } else {
        setMsg(`${res.status}: ${(res as any).reason || "Order not filled"}`);
      }
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h3 className="mb-3 text-sm font-semibold text-slate-300">Place Paper Order</h3>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs text-slate-400">Symbol</label>
          <input
            className="w-32 rounded bg-slate-800 px-2 py-1.5 text-sm text-white outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="RELIANCE"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Side</label>
          <select
            className="rounded bg-slate-800 px-2 py-1.5 text-sm text-white outline-none"
            value={side}
            onChange={(e) => setSide(e.target.value)}
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Qty (0=auto)</label>
          <input
            className="w-20 rounded bg-slate-800 px-2 py-1.5 text-sm text-white outline-none focus:ring-1 focus:ring-blue-500"
            type="number"
            min={0}
            value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
          />
        </div>
        <button
          onClick={submit}
          disabled={busy}
          className={`rounded px-4 py-1.5 text-sm font-medium transition ${
            side === "BUY"
              ? "bg-green-600 hover:bg-green-500"
              : "bg-red-600 hover:bg-red-500"
          } text-white disabled:opacity-50`}
        >
          {busy ? "Placing…" : side}
        </button>
      </div>
      {msg && <p className="mt-2 text-xs text-slate-300">{msg}</p>}
    </div>
  );
}

/* ── Main Page ──────────────────────────────────────────────────────────── */

export default function PaperTradingPage() {
  const [portfolio, setPortfolio] = useState<PaperPortfolio | null>(null);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [perf, setPerf] = useState<PaperPerformance | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoMsg, setAutoMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const [p, t, s] = await Promise.all([
        api.getPaperPortfolio(),
        api.getPaperTrades(100),
        api.getPaperPerformance(),
      ]);
      setPortfolio(p);
      setTrades(t.trades);
      setPerf(s);
    } catch {
      // first load may fail if no portfolio yet
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAutoExecute = async () => {
    setAutoMsg("Running…");
    try {
      const res = await api.autoExecutePaper();
      setAutoMsg(`Executed ${res.executed} trade(s)`);
      await load();
    } catch (e: any) {
      setAutoMsg(`Error: ${e.message}`);
    }
  };

  const handleReset = async () => {
    if (!confirm("Reset paper portfolio? All trades will be cleared.")) return;
    await api.resetPaperPortfolio();
    await load();
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-slate-400">
        Loading paper trading dashboard…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Paper Trading</h1>
          <p className="mt-1 text-sm text-slate-400">
            Simulate trades with virtual money (₹1,00,000). No real money at risk.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleAutoExecute}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 transition"
          >
            Auto-Execute Signals
          </button>
          <button
            onClick={handleReset}
            className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-slate-300 hover:bg-slate-600 transition"
          >
            Reset Portfolio
          </button>
        </div>
      </div>
      {autoMsg && <p className="text-xs text-slate-300">{autoMsg}</p>}

      {/* Portfolio Stats */}
      {portfolio && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Portfolio Value" value={`₹${fmt(portfolio.portfolio_value)}`} />
          <Stat label="Cash" value={`₹${fmt(portfolio.cash)}`} />
          <Stat label="Invested" value={`₹${fmt(portfolio.invested)}`} />
          <Stat
            label="Total Return"
            value={`₹${fmt(portfolio.total_return)}`}
            sub={fmtPct(portfolio.total_return_pct)}
            color={clr(portfolio.total_return)}
          />
          <Stat label="Open Positions" value={String(portfolio.open_positions)} />
          <Stat label="Mode" value={portfolio.mode} color="text-yellow-400" />
        </div>
      )}

      {/* Order Form */}
      <OrderForm onSuccess={load} />

      {/* Open Positions */}
      {portfolio && portfolio.positions.length > 0 && (
        <div className="card overflow-x-auto">
          <h3 className="mb-3 text-sm font-semibold text-slate-300">Open Positions</h3>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-400">
              <tr>
                <th className="pb-2">Symbol</th>
                <th className="pb-2 text-right">Qty</th>
                <th className="pb-2 text-right">Avg Price</th>
                <th className="pb-2 text-right">Live Price</th>
                <th className="pb-2 text-right">Invested</th>
                <th className="pb-2 text-right">Current</th>
                <th className="pb-2 text-right">P&L</th>
                <th className="pb-2 text-right">%</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.positions.map((p) => (
                <tr key={p.symbol} className="border-t border-slate-700/50">
                  <td className="py-2 font-medium">{p.symbol}</td>
                  <td className="py-2 text-right">{p.qty}</td>
                  <td className="py-2 text-right">₹{fmt(p.avg_price)}</td>
                  <td className="py-2 text-right">₹{fmt(p.live_price)}</td>
                  <td className="py-2 text-right">₹{fmt(p.invested)}</td>
                  <td className="py-2 text-right">₹{fmt(p.current_value)}</td>
                  <td className={`py-2 text-right font-medium ${clr(p.unrealised_pnl)}`}>
                    ₹{fmt(p.unrealised_pnl)}
                  </td>
                  <td className={`py-2 text-right ${clr(p.unrealised_pct)}`}>
                    {fmtPct(p.unrealised_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Performance Stats + PnL Chart */}
      {perf && perf.total_trades > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card">
            <h3 className="mb-3 text-sm font-semibold text-slate-300">Performance Stats</h3>
            <div className="grid grid-cols-2 gap-y-2 text-sm">
              <span className="text-slate-400">Total Trades</span>
              <span className="text-right">{perf.total_trades}</span>
              <span className="text-slate-400">Wins / Losses</span>
              <span className="text-right">
                <span className="text-green-400">{perf.wins}</span>
                {" / "}
                <span className="text-red-400">{perf.losses}</span>
              </span>
              <span className="text-slate-400">Win Rate</span>
              <span className="text-right">{(perf.win_rate * 100).toFixed(1)}%</span>
              <span className="text-slate-400">Total P&L</span>
              <span className={`text-right font-medium ${clr(perf.total_pnl)}`}>
                ₹{fmt(perf.total_pnl)}
              </span>
              <span className="text-slate-400">Avg Profit</span>
              <span className="text-right text-green-400">₹{fmt(perf.avg_profit)}</span>
              <span className="text-slate-400">Avg Loss</span>
              <span className="text-right text-red-400">₹{fmt(perf.avg_loss)}</span>
              <span className="text-slate-400">Profit Factor</span>
              <span className="text-right">{perf.profit_factor}</span>
              <span className="text-slate-400">Sharpe Ratio</span>
              <span className="text-right">{perf.sharpe_ratio}</span>
              <span className="text-slate-400">Max Drawdown</span>
              <span className="text-right text-red-400">₹{fmt(perf.max_drawdown)}</span>
              <span className="text-slate-400">Best Trade</span>
              <span className="text-right text-green-400">₹{fmt(perf.best_trade)}</span>
              <span className="text-slate-400">Worst Trade</span>
              <span className="text-right text-red-400">₹{fmt(perf.worst_trade)}</span>
            </div>
          </div>

          {perf.daily_pnl.length > 0 && (
            <div className="card">
              <h3 className="mb-3 text-sm font-semibold text-slate-300">Daily P&L</h3>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={perf.daily_pnl}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                  <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} />
                  <Tooltip
                    contentStyle={{ background: "#1e293b", border: "1px solid #334155", fontSize: 12 }}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="pnl"
                    stroke="#60a5fa"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Trade History */}
      {trades.length > 0 && (
        <div className="card overflow-x-auto">
          <h3 className="mb-3 text-sm font-semibold text-slate-300">Trade History</h3>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-400">
              <tr>
                <th className="pb-2">Time</th>
                <th className="pb-2">Symbol</th>
                <th className="pb-2">Side</th>
                <th className="pb-2 text-right">Qty</th>
                <th className="pb-2 text-right">Price</th>
                <th className="pb-2 text-right">Value</th>
                <th className="pb-2 text-right">Costs</th>
                <th className="pb-2 text-right">P&L</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id} className="border-t border-slate-700/50">
                  <td className="py-1.5 text-xs text-slate-400">
                    {t.timestamp?.slice(0, 16).replace("T", " ")}
                  </td>
                  <td className="py-1.5 font-medium">{t.symbol}</td>
                  <td className={`py-1.5 font-medium ${t.side === "BUY" ? "text-green-400" : "text-red-400"}`}>
                    {t.side}
                  </td>
                  <td className="py-1.5 text-right">{t.quantity}</td>
                  <td className="py-1.5 text-right">₹{fmt(t.price)}</td>
                  <td className="py-1.5 text-right">₹{fmt(t.value)}</td>
                  <td className="py-1.5 text-right text-slate-400">
                    ₹{fmt(t.costs?.total || 0)}
                  </td>
                  <td className={`py-1.5 text-right font-medium ${t.pnl != null ? clr(t.pnl) : "text-slate-500"}`}>
                    {t.pnl != null ? `₹${fmt(t.pnl)}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {(!trades || trades.length === 0) && (
        <div className="card text-center text-slate-400">
          <p className="text-lg font-medium">No trades yet</p>
          <p className="mt-1 text-sm">
            Place a manual order above, or click &quot;Auto-Execute Signals&quot; to trade
            based on the AI&apos;s BUY/SELL recommendations.
          </p>
        </div>
      )}
    </div>
  );
}
