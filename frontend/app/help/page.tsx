"use client";

export default function HelpPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Help &amp; Guide</h1>
        <p className="text-sm text-slate-400">
          Everything you need to understand the AI Stock Scanner
        </p>
      </div>

      {/* What is this */}
      <Section title="What is AI Stock Scanner?">
        <p>
          AI Stock Scanner is a personal tool that <strong>automatically scans 2000+
          NSE stocks</strong> every 30 minutes during market hours. It applies smart
          filters, computes technical indicators, runs machine learning models, and
          generates a ranked watchlist of the best opportunities — all without you
          having to check charts manually.
        </p>
      </Section>

      {/* How scoring works */}
      <Section title="How are stocks scored?">
        <p>Each stock gets an <strong>Opportunity Score</strong> from 0-100%, calculated as:</p>
        <div className="my-4 rounded-lg bg-slate-700/40 p-4 font-mono text-sm text-accent">
          Score = 40% × AI + 25% × Momentum + 20% × Breakout + 15% × Volume
        </div>
        <ul className="list-inside list-disc space-y-2 text-sm text-slate-300">
          <li>
            <strong className="text-white">AI Probability (40%)</strong> — Machine
            learning ensemble (RandomForest + XGBoost + GradientBoosting) trained on
            historical data of all stocks. Predicts the probability that the stock
            will go up.
          </li>
          <li>
            <strong className="text-white">Momentum (25%)</strong> — Based on RSI,
            MACD, rate of change, and price position relative to moving averages.
            High momentum = stock is trending strongly.
          </li>
          <li>
            <strong className="text-white">Breakout (20%)</strong> — Detects price
            breaking above resistance levels, unusual volume surges, and moving
            average crossovers (like the golden cross).
          </li>
          <li>
            <strong className="text-white">Volume Spike (15%)</strong> — Compares
            today&apos;s volume to the 20-day average. A spike often indicates
            institutional buying or news.
          </li>
        </ul>
      </Section>

      {/* Signals */}
      <Section title="What do BUY / SELL / HOLD mean?">
        <div className="space-y-3 text-sm">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-block rounded-full bg-green-900/60 border border-green-700 px-3 py-0.5 text-xs font-semibold text-green-400">BUY</span>
            <p className="text-slate-300">
              The AI and technical indicators agree that this stock has a high probability of going up.
              These are the strongest opportunities.
            </p>
          </div>
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-block rounded-full bg-red-900/60 border border-red-700 px-3 py-0.5 text-xs font-semibold text-red-400">SELL</span>
            <p className="text-slate-300">
              The stock is showing bearish signals — downtrend, negative momentum. Consider avoiding
              or exiting if you hold it.
            </p>
          </div>
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-block rounded-full bg-yellow-900/60 border border-yellow-700 px-3 py-0.5 text-xs font-semibold text-yellow-400">HOLD</span>
            <p className="text-slate-300">
              Mixed signals — the stock isn&apos;t clearly bullish or bearish. Neither a strong buy
              nor a strong sell right now.
            </p>
          </div>
        </div>
      </Section>

      {/* Watchlist categories */}
      <Section title="Watchlist Categories">
        <ul className="list-inside list-disc space-y-2 text-sm text-slate-300">
          <li>
            <strong className="text-white">🟢 Top Buy Picks</strong> — Top 20
            highest-scoring BUY signals across all scanned stocks.
          </li>
          <li>
            <strong className="text-white">🔴 Top Sell / Avoid</strong> — Top 10
            strongest bearish signals.
          </li>
          <li>
            <strong className="text-white">🚀 Breakout Candidates</strong> — Stocks
            breaking resistance or showing golden cross, sorted by breakout score.
          </li>
          <li>
            <strong className="text-white">📊 Volume Movers</strong> — Stocks with
            unusual volume spikes, often an early sign of big moves.
          </li>
        </ul>
      </Section>

      {/* Smart Filters */}
      <Section title="Smart Filters">
        <p className="text-sm text-slate-300">
          Before analysis, stocks must pass these filters to ensure quality:
        </p>
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-400">
          <li>Average daily volume &gt; 500,000 shares (liquidity)</li>
          <li>Stock price &gt; ₹50 (avoids penny stocks)</li>
          <li>Daily volatility &gt; 1.5% (enough movement to trade)</li>
          <li>Market cap &gt; ₹500 Cr (only mid/large caps)</li>
        </ul>
      </Section>

      {/* Auto scanning */}
      <Section title="Automated Scanning">
        <p className="text-sm text-slate-300">
          When the Auto Scheduler is ON, the system runs a fresh scan every 30
          minutes during IST market hours (9:15 AM – 3:30 PM, Monday-Friday). The
          first scan of the day retrains the ML models with the latest data.
        </p>
        <p className="mt-2 text-sm text-slate-300">
          You can also manually trigger a <strong>Full Scan</strong> (retrain models +
          rescan all) or a <strong>Quick Scan</strong> (rescan without retraining)
          from the Dashboard.
        </p>
      </Section>

      {/* Technical indicators */}
      <Section title="Technical Indicators Used">
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
      <div className="rounded-lg border border-yellow-800/50 bg-yellow-900/20 p-5 text-sm text-yellow-200/80">
        <strong className="text-yellow-400">⚠️ Important Disclaimer</strong>
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card space-y-3">
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <div className="text-sm leading-relaxed text-slate-300">{children}</div>
    </section>
  );
}
