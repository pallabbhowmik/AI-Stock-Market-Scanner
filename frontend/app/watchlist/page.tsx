"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { api, WatchlistItem } from "@/lib/api";
import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Rocket,
  BarChart3,
  Info,
  Loader2,
  ArrowRight,
  Search,
} from "lucide-react";

const CATEGORY_META: Record<string, { icon: React.ElementType; color: string; bg: string; title: string; desc: string }> = {
  top_buys: { icon: TrendingUp, color: "text-emerald-400", bg: "bg-emerald-500/10", title: "Top Buy Picks", desc: "Highest-scoring buy opportunities from AI + technicals" },
  top_sells: { icon: TrendingDown, color: "text-red-400", bg: "bg-red-500/10", title: "Top Sell / Avoid", desc: "Stocks showing bearish signals — consider avoiding" },
  top_breakouts: { icon: Rocket, color: "text-cyan-400", bg: "bg-cyan-500/10", title: "Breakout Candidates", desc: "Stocks breaking resistance, volume surges, or MA crossovers" },
  volume_movers: { icon: BarChart3, color: "text-purple-400", bg: "bg-purple-500/10", title: "Volume Movers", desc: "Unusual volume activity — indicates institutional interest" },
  top_analyzed: { icon: BarChart3, color: "text-indigo-400", bg: "bg-indigo-500/10", title: "Top Analyzed", desc: "Highest-scoring stocks across all signals — best overall opportunities" },
};

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

function Tip({ text }: { text: string }) {
  return (
    <span className="tooltip-trigger ml-1 inline-flex">
      <Info size={13} className="text-slate-500" />
      <span className="tooltip-content">{text}</span>
    </span>
  );
}

function WatchlistCard({ item }: { item: WatchlistItem }) {
  const pct = Math.round(item.opportunity_score * 100);
  const barColor = pct >= 70 ? "bg-buy" : pct >= 40 ? "bg-hold" : "bg-sell";

  return (
    <div className="card-hover flex flex-col gap-3.5">
      <div className="flex items-center justify-between">
        <Link href={`/explorer?stock=${item.symbol}`} className="text-lg font-bold text-white hover:text-indigo-400 transition">
          {item.symbol}
        </Link>
        <SignalBadge signal={item.signal} />
      </div>
      <div className="flex items-center gap-3">
        <span className="text-[10px] uppercase tracking-wider text-slate-500 font-medium w-12">Score</span>
        <div className="score-bar flex-1">
          <div className={`score-bar-fill ${barColor}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-sm font-bold text-slate-200 number-display">{pct}%</span>
      </div>
      <p className="text-xs leading-relaxed text-slate-400 line-clamp-2">{item.explanation}</p>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span className="number-display">Confidence: {Math.round(item.confidence * 100)}%</span>
        <span className="text-[10px] font-medium uppercase tracking-wider bg-white/[0.04] rounded-md px-2 py-0.5">#{item.rank}</span>
      </div>
      <Link href={`/explorer?stock=${item.symbol}`} className="flex items-center gap-1.5 text-xs font-medium text-indigo-400 hover:text-indigo-300 transition self-end">
        View details <ArrowRight size={12} />
      </Link>
    </div>
  );
}

export default function WatchlistPage() {
  const [allItems, setAllItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("top_buys");
  const [searchQuery, setSearchQuery] = useState("");
  const deferredSearch = useDeferredValue(searchQuery);

  useEffect(() => {
    (async () => {
      try {
        const items = await api.getWatchlist();
        setAllItems(items);
        // Auto-select first non-empty category
        const grouped = groupByCategory(items);
        const first = Object.keys(grouped).find(k => grouped[k].length > 0);
        if (first) setActiveTab(first);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load watchlist");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const groupByCategory = (items: WatchlistItem[]) => {
    const groups: Record<string, WatchlistItem[]> = {};
    for (const item of items) {
      const cat = item.category || "top_buys";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(item);
    }
    return groups;
  };

  const categories = groupByCategory(allItems);
  const cats = Object.keys(CATEGORY_META).filter(k => categories[k]?.length);
  // Also include any extra categories not in our predefined list
  Object.keys(categories).forEach(k => { if (!cats.includes(k)) cats.push(k); });

  const currentItems = useMemo(() => {
    return (categories[activeTab] || []).filter((item) =>
      !deferredSearch || item.symbol.toLowerCase().includes(deferredSearch.toLowerCase())
    );
  }, [activeTab, categories, deferredSearch]);

  const totalStocks = allItems.length;

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center animate-in">
        <div className="text-center space-y-3">
          <Loader2 size={28} className="animate-spin text-indigo-400 mx-auto" />
          <p className="text-slate-500 text-sm">Loading watchlist...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center animate-in">
        <div className="card max-w-md text-center gradient-border">
          <div className="mb-4 text-4xl">⚠️</div>
          <h2 className="text-lg font-bold text-red-400 mb-2">Couldn&apos;t load watchlist</h2>
          <p className="text-sm text-slate-400 mb-4">{error}</p>
          <p className="text-xs text-slate-500 mb-5">
            The watchlist is generated after a market scan. Head to the Dashboard and run a Full Scan first.
          </p>
          <Link href="/" className="btn-primary">
            Go to Dashboard <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Today&apos;s Watchlist</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {totalStocks} AI-curated picks across {cats.length} categories
            <Tip text="These stocks are automatically selected by the AI after each scan. They represent the best opportunities found in the market today." />
          </p>
        </div>
        {/* Search */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search symbol..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="rounded-xl border border-white/[0.08] bg-white/[0.03] py-2 pl-9 pr-4 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500/40 focus:outline-none focus:ring-1 focus:ring-indigo-500/20 w-48 transition"
          />
        </div>
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="btn-secondary text-xs px-3 py-2"
          >
            Clear search
          </button>
        )}
      </div>

      {/* Empty state */}
      {totalStocks === 0 && (
        <div className="card text-center py-14">
          <div className="mb-4 text-5xl">📋</div>
          <h2 className="text-lg font-bold text-white mb-2">No watchlist yet</h2>
          <p className="text-sm text-slate-400 mb-5">Run a Full Scan from the Dashboard to generate today&apos;s picks.</p>
          <Link href="/" className="btn-primary">
            Go to Dashboard <ArrowRight size={14} />
          </Link>
        </div>
      )}

      {/* Category Tabs */}
      {totalStocks > 0 && (
        <>
          <div className="flex flex-wrap gap-2">
            {cats.map((cat) => {
              const meta = CATEGORY_META[cat] || { icon: BarChart3, color: "text-slate-400", title: cat, desc: "" };
              const Icon = meta.icon;
              const count = categories[cat]?.length || 0;
              return (
                <button
                  key={cat}
                  onClick={() => setActiveTab(cat)}
                  className={`relative flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all duration-200 ${
                    activeTab === cat
                      ? "text-white border border-indigo-500/25 bg-indigo-500/10"
                      : "text-slate-400 border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05] hover:text-white"
                  }`}
                >
                  <Icon size={14} className={activeTab === cat ? "text-indigo-400" : meta.color} />
                  {meta.title}
                  <span className="rounded-lg bg-white/[0.06] px-2 py-0.5 text-[10px] font-semibold">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Category Description */}
          {CATEGORY_META[activeTab] && (
            <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] px-4 py-3 text-sm text-slate-400">
              {CATEGORY_META[activeTab].desc}
            </div>
          )}

          {/* Cards Grid */}
          {currentItems.length === 0 ? (
            <div className="card text-center text-slate-500 py-10">
              {searchQuery
                ? `No stocks matching "${searchQuery}" in this category.`
                : "No stocks in this category yet. Run a scan first."}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {currentItems.map((item) => (
                <WatchlistCard key={`${item.category}-${item.symbol}`} item={item} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
