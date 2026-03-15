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
import {
  Info,
  Loader2,
  Wallet,
  TrendingUp,
  TrendingDown,
  RotateCcw,
  Zap,
  Trophy,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";

/* ── Helpers ────────────────────────────────────────────────────────────── */

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

function Tip({ text }: { text: string }) {
  return (
    <span className="tooltip-trigger ml-1 inline-flex">
      <Info size={13} className="text-slate-500" />
      <span className="tooltip-content">{text}</span>
    </span>
  );
}

/* ── Stat Card ──────────────────────────────────────────────────────────── */

function Stat({ label, value, sub, color, tip, icon: Icon }: {
  label: string; value: string; sub?: string; color?: string; tip?: string; icon?: React.ElementType;
}) {
  return (
    <div className="card-hover flex flex-col gap-1">
      <span className="text-xs text-slate-400 flex items-center gap-1">
        {Icon && <Icon size={12} />}
        {label}
        {tip && <Tip text={tip} />}
      </span>
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
    <div className="card animate-in">
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold text-slate-300">Place Paper Order</h3>
        <Tip text="Paper orders use virtual money. Enter a stock symbol (e.g., RELIANCE), choose BUY or SELL, and set quantity (0 = auto-size based on your available cash)." />
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs text-slate-400">Symbol</label>
          <input
            className="w-32 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white outline-none focus:border-accent"
            placeholder="RELIANCE"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Side</label>
          <div className="flex gap-1">
            <button
              onClick={() => setSide("BUY")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                side === "BUY" ? "bg-green-600 text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"
              }`}
            >
              <TrendingUp size={14} className="inline mr-1" /> BUY
            </button>
            <button
              onClick={() => setSide("SELL")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                side === "SELL" ? "bg-red-600 text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"
              }`}
            >
              <TrendingDown size={14} className="inline mr-1" /> SELL
            </button>
          </div>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">
            Qty <span className="text-slate-600">(0 = auto)</span>
          </label>
          <input
            className="w-20 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white outline-none focus:border-accent"
            type="number"
            min={0}
            value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
          />
        </div>
        <button
          onClick={submit}
          disabled={busy || !symbol.trim()}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-600 disabled:opacity-50"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
          {busy ? "Placing…" : "Place Order"}
        </button>
      </div>
      {msg && (
        <p className={`mt-2 text-xs ${msg.startsWith("✓") ? "text-green-400" : msg.startsWith("Error") ? "text-red-400" : "text-slate-300"}`}>
          {msg}
        </p>
      )}
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
      setAutoMsg(`✓ Executed ${res.executed} trade(s) based on AI signals`);
      await load();
    } catch (e: any) {
      setAutoMsg(`Error: ${e.message}`);
    }
  };

  const handleReset = async () => {
    if (!confirm("Reset paper portfolio? All trades will be cleared.")) return;
    await api.resetPaperPortfolio();
    setAutoMsg("");
    await load();
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center animate-in">
        <div className="text-center space-y-3">
          <Loader2 size={32} className="animate-spin text-accent mx-auto" />
          <p className="text-slate-400">Loading paper trading dashboard…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Paper Trading</h1>
          <p className="text-sm text-slate-400">
            Practice trading with ₹1,00,000 virtual cash — no real money at risk
            <Tip text="Paper trading lets you test strategies without risking real money. It simulates buy and sell orders at real market prices." />
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleAutoExecute}
            className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition"
          >
            <Zap size={14} /> Auto-Execute Signals
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 rounded-lg bg-slate-700 px-4 py-2 text-sm text-slate-300 border border-slate-600 hover:bg-slate-600 transition"
          >
            <RotateCcw size={14} /> Reset
          </button>
        </div>
      </div>

      {autoMsg && (
        <div className={`rounded-lg border px-4 py-2.5 text-sm ${
          autoMsg.startsWith("✓") ? "border-green-800 bg-green-900/30 text-green-300"
          : autoMsg.startsWith("Error") ? "border-red-800 bg-red-900/30 text-red-300"
          : "border-blue-800 bg-blue-900/30 text-blue-300"
        }`}>
          {autoMsg}
        </div>
      )}

      {/* Getting Started (show when no trades) */}
      {(!trades || trades.length === 0) && !portfolio?.open_positions && (
        <div className="rounded-xl border border-purple-700/30 bg-gradient-to-r from-purple-900/20 via-blue-900/20 to-slate-900 p-6 animate-in">
          <h2 className="text-lg font-bold text-white mb-2">Getting Started with Paper Trading</h2>
          <div className="grid gap-4 sm:grid-cols-3 text-sm text-slate-300">
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-900/50 text-blue-400 font-bold text-sm">1</div>
              <div>
                <p className="font-medium text-white">Run a scan</p>
                <p className="text-xs text-slate-400">Get AI predictions from the <Link href="/" className="text-accent hover:underline">Dashboard</Link></p>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-purple-900/50 text-purple-400 font-bold text-sm">2</div>
              <div>
                <p className="font-medium text-white">Auto-execute or manual</p>
                <p className="text-xs text-slate-400">Click &quot;Auto-Execute&quot; or place orders manually below</p>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-900/50 text-green-400 font-bold text-sm">3</div>
              <div>
                <p className="font-medium text-white">Track performance</p>
                <p className="text-xs text-slate-400">Watch your P&L, win rate, and Sharpe ratio</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Portfolio Stats */}
      {portfolio && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat icon={Wallet} label="Portfolio Value" value={`₹${fmt(portfolio.portfolio_value)}`}
            tip="Total value of your portfolio: cash + value of all open positions" />
          <Stat label="Cash" value={`₹${fmt(portfolio.cash)}`}
            tip="Available cash to buy new stocks" />
          <Stat label="Invested" value={`₹${fmt(portfolio.invested)}`}
            tip="Total amount currently invested in stocks" />
          <Stat
            label="Total Return"
            value={`₹${fmt(portfolio.total_return)}`}
            sub={fmtPct(portfolio.total_return_pct)}
            color={clr(portfolio.total_return)}
            tip="How much money you've made (or lost) since starting"
          />
          <Stat label="Open Positions" value={String(portfolio.open_positions)}
            tip="Number of stocks you currently hold" />
          <Stat label="Mode" value={portfolio.mode} color="text-yellow-400"
            tip="PAPER = virtual money only, no real trades" />
        </div>
      )}

      {/* Order Form */}
      <OrderForm onSuccess={load} />

      {/* Open Positions */}
      {portfolio && portfolio.positions.length > 0 && (
        <div className="card animate-in overflow-x-auto">
          <div className="flex items-center gap-2 mb-3">
            <h3 className="text-sm font-semibold text-slate-300">Open Positions</h3>
            <Tip text="Stocks you currently hold. Unrealised P&L shows profit/loss if you sold now." />
          </div>
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
                <tr key={p.symbol} className="border-t border-slate-700/50 hover:bg-slate-700/20 transition">
                  <td className="py-2 font-medium">
                    <Link href={`/explorer?stock=${p.symbol}`} className="text-white hover:text-accent transition">
                      {p.symbol}
                    </Link>
                  </td>
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
          <div className="card animate-in">
            <div className="flex items-center gap-2 mb-3">
              <Trophy size={16} className="text-yellow-400" />
              <h3 className="text-sm font-semibold text-slate-300">Performance Stats</h3>
              <Tip text="Key metrics to evaluate how well your trading strategy is performing." />
            </div>
            <div className="grid grid-cols-2 gap-y-2 text-sm">
              <span className="text-slate-400">Total Trades</span>
              <span className="text-right">{perf.total_trades}</span>
              <span className="text-slate-400">Wins / Losses</span>
              <span className="text-right">
                <span className="text-green-400">{perf.wins}</span>
                {" / "}
                <span className="text-red-400">{perf.losses}</span>
              </span>
              <span className="text-slate-400">Win Rate <Tip text="Percentage of profitable trades" /></span>
              <span className="text-right">{(perf.win_rate * 100).toFixed(1)}%</span>
              <span className="text-slate-400">Total P&L</span>
              <span className={`text-right font-medium ${clr(perf.total_pnl)}`}>
                ₹{fmt(perf.total_pnl)}
              </span>
              <span className="text-slate-400">Avg Profit</span>
              <span className="text-right text-green-400">₹{fmt(perf.avg_profit)}</span>
              <span className="text-slate-400">Avg Loss</span>
              <span className="text-right text-red-400">₹{fmt(perf.avg_loss)}</span>
              <span className="text-slate-400">Profit Factor <Tip text="Total profits / total losses. Above 1.5 is good." /></span>
              <span className="text-right">{perf.profit_factor}</span>
              <span className="text-slate-400">Sharpe Ratio <Tip text="Risk-adjusted return. Higher = better returns per unit of risk. Above 1.0 is decent." /></span>
              <span className="text-right">{perf.sharpe_ratio}</span>
              <span className="text-slate-400">Max Drawdown <Tip text="Largest peak-to-trough drop — measures worst case scenario" /></span>
              <span className="text-right text-red-400">₹{fmt(perf.max_drawdown)}</span>
              <span className="text-slate-400">Best Trade</span>
              <span className="text-right text-green-400">₹{fmt(perf.best_trade)}</span>
              <span className="text-slate-400">Worst Trade</span>
              <span className="text-right text-red-400">₹{fmt(perf.worst_trade)}</span>
            </div>
          </div>

          {perf.daily_pnl.length > 0 && (
            <div className="card animate-in">
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
                  <Line type="monotone" dataKey="pnl" stroke="#60a5fa" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Trade History */}
      {trades.length > 0 && (
        <div className="card animate-in overflow-x-auto">
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
                <tr key={t.id} className="border-t border-slate-700/50 hover:bg-slate-700/20 transition">
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
    </div>
  );
}
