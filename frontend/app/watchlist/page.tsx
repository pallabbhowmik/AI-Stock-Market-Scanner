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

const CATEGORY_META: Record<string, { icon: React.ElementType; color: string; title: string; desc: string }> = {
  top_buys: { icon: TrendingUp, color: "text-green-400", title: "Top Buy Picks", desc: "Highest-scoring buy opportunities from AI + technicals" },
  top_sells: { icon: TrendingDown, color: "text-red-400", title: "Top Sell / Avoid", desc: "Stocks showing bearish signals — consider avoiding" },
  top_breakouts: { icon: Rocket, color: "text-cyan-400", title: "Breakout Candidates", desc: "Stocks breaking resistance, volume surges, or MA crossovers" },
  volume_movers: { icon: BarChart3, color: "text-purple-400", title: "Volume Movers", desc: "Unusual volume activity — indicates institutional interest" },
};

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
    <div className="card-hover flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <Link href={`/explorer?stock=${item.symbol}`} className="text-lg font-bold text-white hover:text-accent transition">
          {item.symbol}
        </Link>
        <SignalBadge signal={item.signal} />
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-slate-500 w-14">Score</span>
        <div className="score-bar flex-1">
          <div className={`score-bar-fill ${barColor}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-sm font-semibold text-slate-300">{pct}%</span>
      </div>
      <p className="text-xs leading-relaxed text-slate-400 line-clamp-2">{item.explanation}</p>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>Confidence: {Math.round(item.confidence * 100)}%</span>
        <span>Rank #{item.rank}</span>
      </div>
      <Link href={`/explorer?stock=${item.symbol}`} className="flex items-center gap-1 text-xs text-accent hover:underline self-end">
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

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center animate-in">
        <div className="text-center space-y-3">
          <Loader2 size={32} className="animate-spin text-accent mx-auto" />
          <p className="text-slate-400">Loading watchlist...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center animate-in">
        <div className="card max-w-md text-center">
          <div className="mb-3 text-4xl">⚠️</div>
          <h2 className="text-lg font-semibold text-red-400 mb-2">Couldn&apos;t load watchlist</h2>
          <p className="text-sm text-slate-400 mb-4">{error}</p>
          <p className="text-xs text-slate-500 mb-4">
            The watchlist is generated after a market scan. Head to the Dashboard and run a Full Scan first.
          </p>
          <Link href="/" className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-blue-600 transition">
            Go to Dashboard <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    );
  }

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

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Today&apos;s Watchlist</h1>
          <p className="text-sm text-slate-400">
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
            className="rounded-lg border border-slate-700 bg-slate-800 py-2 pl-9 pr-4 text-sm text-white placeholder:text-slate-500 focus:border-accent focus:outline-none w-48"
          />
        </div>
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-300 transition hover:bg-slate-700"
          >
            Clear search
          </button>
        )}
      </div>

      {/* Empty state */}
      {totalStocks === 0 && (
        <div className="card text-center py-12">
          <div className="mb-3 text-5xl">📋</div>
          <h2 className="text-lg font-semibold text-white mb-2">No watchlist yet</h2>
          <p className="text-sm text-slate-400 mb-4">Run a Full Scan from the Dashboard to generate today&apos;s picks.</p>
          <Link href="/" className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-600 transition">
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
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition ${
                    activeTab === cat
                      ? "bg-accent/15 text-accent border border-accent/30"
                      : "bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700"
                  }`}
                >
                  <Icon size={14} className={activeTab === cat ? "text-accent" : meta.color} />
                  {meta.title}
                  <span className="rounded-full bg-slate-600/60 px-2 py-0.5 text-xs">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Category Description */}
          {CATEGORY_META[activeTab] && (
            <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 px-4 py-2.5 text-sm text-slate-400">
              {CATEGORY_META[activeTab].desc}
            </div>
          )}

          {/* Cards Grid */}
          {currentItems.length === 0 ? (
            <div className="card text-center text-slate-400 py-8">
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
