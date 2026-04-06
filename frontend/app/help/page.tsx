"use client";

import { useState } from "react";
import {
  Search,
  BookOpen,
  Brain,
  BarChart3,
  TrendingUp,
  Zap,
  Shield,
  HelpCircle,
  ChevronDown,
  ChevronRight,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";

/* ── Glossary data ──────────────────────────────────────────────────────── */

const GLOSSARY: { term: string; def: string }[] = [
  { term: "RSI (Relative Strength Index)", def: "A momentum number from 0-100. Above 70 = overbought (might fall). Below 30 = oversold (might rise). We use 14-period RSI." },
  { term: "MACD", def: "Moving Average Convergence Divergence. When the MACD line crosses above its signal line = bullish. Below = bearish." },
  { term: "Bollinger Bands", def: "An envelope around the price showing typical volatility. Price touching the lower band can mean oversold; upper band = overbought." },
  { term: "SMA / EMA", def: "Simple / Exponential Moving Average. Smooths out price data. The 50-day and 200-day are most watched." },
  { term: "Golden Cross", def: "When the 50-day moving average crosses above the 200-day — a classic bullish signal." },
  { term: "Death Cross", def: "When the 50-day crosses below the 200-day — a bearish signal." },
  { term: "Volume Spike", def: "A day with unusually high trading volume. Often signals institutional activity or news." },
  { term: "Breakout", def: "When price moves above a resistance level with strong volume, suggesting upward momentum." },
  { term: "ATR (Average True Range)", def: "Measures daily price volatility. Higher ATR = more volatile stock." },
  { term: "Sharpe Ratio", def: "Risk-adjusted return. Higher = better returns for the risk taken. Above 1.0 is good; above 2.0 is excellent." },
  { term: "Win Rate", def: "Percentage of trades that ended in profit. 50%+ combined with high reward:risk ratio is profitable." },
  { term: "Drawdown", def: "The peak-to-trough decline in portfolio value. Measures worst-case loss." },
  { term: "Paper Trading", def: "Simulated trading with virtual money. Lets you test strategies without risking real capital." },
  { term: "Profit Factor", def: "Total gross profit / total gross loss. Above 1.5 is considered good." },
  { term: "Market Regime", def: "Current market state: BULL (uptrend), BEAR (downtrend), or SIDEWAYS (range-bound). Detected automatically using Nifty 50 data." },
  { term: "Meta-AI Strategy", def: "Our master AI that combines signals from ML models, momentum, breakout, volume, and sentiment — dynamically adjusting weights based on market regime." },
];

/* ── FAQ data ───────────────────────────────────────────────────────────── */

const FAQ: { q: string; a: string }[] = [
  { q: "How do I get started?", a: "Go to the Dashboard and click 'Full Scan'. The AI will download data for 2000+ NSE stocks, filter for quality, run ML models, and generate predictions. This takes a few minutes the first time." },
  { q: "Is this real trading?", a: "No! This is an educational tool. The Paper Trading feature uses virtual money (₹1,00,000). No real money is ever at risk. Always consult a SEBI-registered financial advisor before trading with real money." },
  { q: "How often should I scan?", a: "Turn on the Auto Scheduler from the Dashboard — it runs scans every 30 minutes during market hours (9:15 AM – 3:30 PM IST, Mon-Fri). Or run manual scans whenever you want." },
  { q: "What does 'Quick Scan' vs 'Full Scan' mean?", a: "Full Scan retrains the ML models with latest data AND re-analyzes all stocks. Quick Scan only re-analyzes stocks using existing models — much faster." },
  { q: "How accurate are the predictions?", a: "Model accuracy varies (typically 50-65%). The AI combines 6 different strategies to improve reliability. Never invest based solely on any prediction tool. Past performance doesn't guarantee future results." },
  { q: "What stocks are covered?", a: "All NSE-listed stocks (2000+). After filtering for liquidity (volume > 500K), price > ₹50, and market cap > ₹500 Cr, typically 30-100 stocks pass quality filters and get full AI analysis." },
  { q: "Why are some stocks missing?", a: "Stocks are filtered out if they have: low volume (< 500K daily avg), price below ₹50 (penny stocks), low volatility (< 1.5% daily), or insufficient data history." },
  { q: "What is the Meta-AI?", a: "The Meta-AI is a master strategy that dynamically combines 6 sub-strategies (ML, RL Agent, Momentum, Mean Reversion, Volume, Sentiment). In bull markets, it increases momentum weight. In bear markets, it shifts to mean reversion. The weights adapt automatically." },
];

/* ── Components ─────────────────────────────────────────────────────────── */

function Section({ title, icon: Icon, children }: { title: string; icon?: React.ElementType; children: React.ReactNode }) {
  return (
    <section className="card animate-in space-y-4">
      <h2 className="text-lg font-bold text-white flex items-center gap-2.5">
        {Icon && <div className="h-8 w-8 rounded-xl bg-indigo-500/10 flex items-center justify-center"><Icon size={16} className="text-indigo-400" /></div>}
        {title}
      </h2>
      <div className="text-sm leading-relaxed text-slate-300">{children}</div>
    </section>
  );
}

function FAQItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-white/[0.04] last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between py-3.5 text-left text-sm font-medium text-white hover:text-indigo-400 transition"
      >
        {q}
        {open ? <ChevronDown size={16} className="text-slate-500 shrink-0" /> : <ChevronRight size={16} className="text-slate-500 shrink-0" />}
      </button>
      {open && (
        <p className="pb-3 text-sm text-slate-400 animate-in">{a}</p>
      )}
    </div>
  );
}

/* ── Main Page ──────────────────────────────────────────────────────────── */

export default function HelpPage() {
  const [glossarySearch, setGlossarySearch] = useState("");
  const [faqSearch, setFaqSearch] = useState("");

  const filteredGlossary = GLOSSARY.filter(
    (g) =>
      !glossarySearch ||
      g.term.toLowerCase().includes(glossarySearch.toLowerCase()) ||
      g.def.toLowerCase().includes(glossarySearch.toLowerCase())
  );

  const filteredFaq = FAQ.filter(
    (f) =>
      !faqSearch ||
      f.q.toLowerCase().includes(faqSearch.toLowerCase()) ||
      f.a.toLowerCase().includes(faqSearch.toLowerCase())
  );

  return (
    <div className="mx-auto max-w-3xl space-y-8 animate-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Help &amp; Guide</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Everything you need to understand and use the AI Stock Scanner
        </p>
      </div>

      {/* Quick Start */}
      <div className="gradient-border rounded-2xl bg-gradient-to-r from-indigo-900/10 via-purple-900/10 to-surface p-6 animate-in">
        <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-xl bg-yellow-500/10 flex items-center justify-center"><Zap size={16} className="text-yellow-400" /></div> Quick Start Guide
        </h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 font-bold text-sm">1</div>
            <div>
              <p className="font-medium text-white text-sm">Scan the Market</p>
              <p className="text-xs text-slate-400">Go to <Link href="/" className="text-indigo-400 hover:underline">Dashboard</Link> → Full Scan</p>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 font-bold text-sm">2</div>
            <div>
              <p className="font-medium text-white text-sm">Review Picks</p>
              <p className="text-xs text-slate-400">Check <Link href="/watchlist" className="text-indigo-400 hover:underline">Watchlist</Link> & <Link href="/explorer" className="text-indigo-400 hover:underline">Explorer</Link></p>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 font-bold text-sm">3</div>
            <div>
              <p className="font-medium text-white text-sm">Practice Trading</p>
              <p className="text-xs text-slate-400">Test in <Link href="/paper-trading" className="text-indigo-400 hover:underline">Paper Trading</Link> risk-free</p>
            </div>
          </div>
        </div>
      </div>

      {/* FAQ */}
      <Section title="Frequently Asked Questions" icon={HelpCircle}>
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search questions..."
            value={faqSearch}
            onChange={(e) => setFaqSearch(e.target.value)}
            className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] py-2 pl-9 pr-4 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/20 focus:outline-none transition"
          />
        </div>
        <div>
          {filteredFaq.length === 0 ? (
            <p className="py-4 text-center text-slate-500 text-sm">No matching questions found.</p>
          ) : (
            filteredFaq.map((f, i) => <FAQItem key={i} q={f.q} a={f.a} />)
          )}
        </div>
      </Section>

      {/* How scoring works */}
      <Section title="How are stocks scored?" icon={Brain}>
        <p>Each stock gets an <strong>Opportunity Score</strong> from 0-100%, calculated as:</p>
        <div className="my-4 rounded-xl bg-white/[0.03] border border-white/[0.06] p-4 font-mono text-sm text-indigo-400">
          Score = 40% × AI + 25% × Momentum + 20% × Breakout + 15% × Volume
        </div>
        <ul className="list-inside list-disc space-y-2 text-sm text-slate-300">
          <li>
            <strong className="text-white">AI Probability (40%)</strong> — ML ensemble (RandomForest + XGBoost + GradientBoosting) predicts probability the stock goes up.
          </li>
          <li>
            <strong className="text-white">Momentum (25%)</strong> — RSI, MACD, rate of change, and relative position to moving averages.
          </li>
          <li>
            <strong className="text-white">Breakout (20%)</strong> — Detects price breaking resistance levels, volume surges, and MA crossovers.
          </li>
          <li>
            <strong className="text-white">Volume Spike (15%)</strong> — Today&apos;s volume vs 20-day average. Spikes often indicate institutional buying.
          </li>
        </ul>
      </Section>

      {/* Signals */}
      <Section title="What do BUY / SELL / HOLD mean?" icon={TrendingUp}>
        <div className="space-y-3 text-sm">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex items-center rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-400">BUY</span>
            <p className="text-slate-300">
              AI and technical indicators agree the stock has high probability of going up. Strongest opportunities.
            </p>
          </div>
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex items-center rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-1 text-xs font-semibold text-red-400">SELL</span>
            <p className="text-slate-300">
              Bearish signals — downtrend, negative momentum. Consider avoiding or exiting.
            </p>
          </div>
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex items-center rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-1 text-xs font-semibold text-amber-400">HOLD</span>
            <p className="text-slate-300">
              Mixed signals — not clearly bullish or bearish. Neither a strong buy nor sell right now.
            </p>
          </div>
        </div>
      </Section>

      {/* Smart Filters */}
      <Section title="Smart Filters" icon={Shield}>
        <p>Before analysis, stocks must pass quality filters:</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Volume</span>
            <p className="text-sm text-white font-medium">&gt; 500,000 / day</p>
            <p className="text-xs text-slate-400">Ensures you can buy/sell easily</p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Price</span>
            <p className="text-sm text-white font-medium">&gt; ₹50</p>
            <p className="text-xs text-slate-400">Avoids penny stocks</p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Volatility</span>
            <p className="text-sm text-white font-medium">&gt; 1.5% daily</p>
            <p className="text-xs text-slate-400">Enough movement to trade</p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Market Cap</span>
            <p className="text-sm text-white font-medium">&gt; ₹500 Cr</p>
            <p className="text-xs text-slate-400">Only mid/large caps</p>
          </div>
        </div>
      </Section>

      {/* Technical Indicators Glossary */}
      <Section title="Glossary" icon={BookOpen}>
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search terms..."
            value={glossarySearch}
            onChange={(e) => setGlossarySearch(e.target.value)}
            className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] py-2 pl-9 pr-4 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/20 focus:outline-none transition"
          />
        </div>
        <div className="space-y-2">
          {filteredGlossary.length === 0 ? (
            <p className="py-4 text-center text-slate-500 text-sm">No matching terms found.</p>
          ) : (
            filteredGlossary.map((g, i) => (
              <div key={i} className="rounded-xl border border-white/[0.05] bg-white/[0.02] px-4 py-3">
                <span className="font-medium text-white text-sm">{g.term}</span>
                <p className="text-xs text-slate-400 mt-0.5">{g.def}</p>
              </div>
            ))
          )}
        </div>
      </Section>

      {/* Technical Indicators */}
      <Section title="Technical Indicators Used" icon={BarChart3}>
        <div className="grid gap-2 sm:grid-cols-2 text-sm text-slate-400">
          <div><strong className="text-slate-200">SMA/EMA</strong> — 20, 50, 200-day moving averages</div>
          <div><strong className="text-slate-200">RSI</strong> — Relative Strength Index (14-period)</div>
          <div><strong className="text-slate-200">MACD</strong> — Trend and momentum</div>
          <div><strong className="text-slate-200">Bollinger Bands</strong> — Volatility envelope</div>
          <div><strong className="text-slate-200">ATR</strong> — Average True Range</div>
          <div><strong className="text-slate-200">OBV</strong> — On-Balance Volume</div>
          <div><strong className="text-slate-200">Stochastic</strong> — %K and %D oscillator</div>
          <div><strong className="text-slate-200">Williams %R</strong> — Overbought/oversold</div>
          <div><strong className="text-slate-200">ROC</strong> — Rate of Change (5, 10, 20)</div>
          <div><strong className="text-slate-200">Volume Ratio</strong> — Current vs 20-day avg</div>
        </div>
      </Section>

      {/* Disclaimer */}
      <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-5 text-sm text-amber-200/80">
        <strong className="text-amber-400">⚠️ Important Disclaimer</strong>
        <p className="mt-2">
          This tool is for <strong>personal educational purposes only</strong>. It is
          NOT financial advice. Never invest solely based on AI predictions. Always
          do your own research, use stop losses, and consult a SEBI-registered
          financial advisor before trading.
        </p>
      </div>
    </div>
  );
}
