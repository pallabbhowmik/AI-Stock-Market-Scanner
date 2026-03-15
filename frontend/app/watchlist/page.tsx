"use client";

import { useEffect, useState } from "react";
import { api, WatchlistItem } from "@/lib/api";

const CATEGORY_META: Record<string, { icon: string; title: string; desc: string }> = {
  top_buys: { icon: "🟢", title: "Top Buy Picks", desc: "Highest-scoring buy opportunities from AI + technicals" },
  top_sells: { icon: "🔴", title: "Top Sell / Avoid", desc: "Stocks showing bearish signals — consider avoiding" },
  top_breakouts: { icon: "🚀", title: "Breakout Candidates", desc: "Stocks breaking resistance, volume surges, or MA crossovers" },
  volume_movers: { icon: "📊", title: "Volume Movers", desc: "Unusual volume activity — indicates institutional interest" },
};

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

function WatchlistCard({ item }: { item: WatchlistItem }) {
  const pct = Math.round(item.opportunity_score * 100);
  const barColor = pct >= 70 ? "bg-buy" : pct >= 40 ? "bg-hold" : "bg-sell";

  return (
    <div className="card flex flex-col gap-3 transition hover:border-slate-500">
      <div className="flex items-center justify-between">
        <span className="text-lg font-bold text-white">{item.symbol}</span>
        <SignalBadge signal={item.signal} />
      </div>
      <div className="flex items-center gap-3">
        <div className="score-bar flex-1">
          <div className={`score-bar-fill ${barColor}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-sm font-semibold text-slate-300">{pct}%</span>
      </div>
      <p className="text-xs leading-relaxed text-slate-400">{item.explanation}</p>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>Confidence: {Math.round(item.confidence * 100)}%</span>
        <span>Rank #{item.rank}</span>
      </div>
    </div>
  );
}

export default function WatchlistPage() {
  const [categories, setCategories] = useState<Record<string, WatchlistItem[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("top_buys");

  useEffect(() => {
    (async () => {
      try {
        const data = await api.getWatchlistByCategory();
        setCategories(data);
        const first = Object.keys(data)[0];
        if (first) setActiveTab(first);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load watchlist");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-slate-400">Loading watchlist...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="card text-center">
          <p className="text-red-400">⚠️ {error}</p>
          <p className="mt-2 text-xs text-slate-500">Run a scan from the Dashboard first.</p>
        </div>
      </div>
    );
  }

  const cats = Object.keys(categories);
  const items = categories[activeTab] || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Today&apos;s Watchlist</h1>
        <p className="text-sm text-slate-400">AI-curated picks across categories</p>
      </div>

      {/* Category Tabs */}
      <div className="flex flex-wrap gap-2">
        {cats.map((cat) => {
          const meta = CATEGORY_META[cat] || { icon: "📌", title: cat };
          return (
            <button
              key={cat}
              onClick={() => setActiveTab(cat)}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition ${
                activeTab === cat
                  ? "bg-accent text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              <span>{meta.icon}</span> {meta.title}
              <span className="ml-1 rounded-full bg-slate-600/60 px-2 py-0.5 text-xs">
                {categories[cat]?.length || 0}
              </span>
            </button>
          );
        })}
      </div>

      {/* Description */}
      {CATEGORY_META[activeTab] && (
        <p className="text-sm text-slate-400">{CATEGORY_META[activeTab].desc}</p>
      )}

      {/* Cards Grid */}
      {items.length === 0 ? (
        <div className="card text-center text-slate-400">
          No stocks in this category yet. Run a scan first.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <WatchlistCard key={`${item.category}-${item.symbol}`} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
