"""
Main Runner
Orchestrates the full pipeline: data → features → training → signals → alerts.
"""
import logging
import argparse
import sys

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_data_pipeline(tickers=None):
    """Step 1: Fetch and store data."""
    from data_pipeline import run_full_pipeline
    logger.info("=" * 60)
    logger.info("STEP 1: Data Pipeline")
    logger.info("=" * 60)
    df = run_full_pipeline(tickers)
    logger.info("Data pipeline complete. Rows: %d", len(df))
    return df


def run_feature_engineering(tickers=None):
    """Step 2: Compute features for all tickers."""
    from data_pipeline import load_data
    from feature_engineering import compute_all_features

    logger.info("=" * 60)
    logger.info("STEP 2: Feature Engineering")
    logger.info("=" * 60)

    if tickers is None:
        tickers = config.STOCK_UNIVERSE

    results = {}
    for ticker in tickers:
        df = load_data(ticker)
        if not df.empty:
            featured = compute_all_features(df)
            results[ticker] = featured
            logger.info("%s: %d rows, %d features", ticker, len(featured), featured.shape[1])

    return results


def run_model_training(tickers=None):
    """Step 3: Train ML models for each ticker."""
    from data_pipeline import load_data
    from feature_engineering import compute_all_features, prepare_ml_dataset
    from model_training import train_all_models

    logger.info("=" * 60)
    logger.info("STEP 3: Model Training")
    logger.info("=" * 60)

    if tickers is None:
        tickers = config.STOCK_UNIVERSE

    all_results = {}
    for ticker in tickers:
        logger.info("Training models for %s...", ticker)
        df = load_data(ticker)
        if df.empty:
            continue

        featured = compute_all_features(df)
        X, y_dir, y_ret, dates, feat_cols = prepare_ml_dataset(featured)

        if len(X) < 100:
            logger.warning("Insufficient data for %s (%d samples), skipping", ticker, len(X))
            continue

        results = train_all_models(X, y_dir, feat_cols, ticker=ticker)
        all_results[ticker] = results

        # Print comparison
        print(f"\n{'─' * 50}")
        print(f"  {ticker} Model Results")
        print(f"{'─' * 50}")
        for name, res in results.items():
            print(f"  {name:20s} | Acc: {res['accuracy']:.4f} | AUC: {res.get('auc_roc', 0):.4f}")

    return all_results


def run_backtesting(tickers=None):
    """Step 4: Backtest strategies."""
    from data_pipeline import load_data
    from feature_engineering import compute_all_features
    from strategy_engine import MomentumStrategy, MACrossoverStrategy, RSIStrategy
    from backtesting import run_backtest

    logger.info("=" * 60)
    logger.info("STEP 4: Backtesting")
    logger.info("=" * 60)

    if tickers is None:
        tickers = config.STOCK_UNIVERSE[:5]  # Top 5 for speed

    strategies = {
        "Momentum": MomentumStrategy(),
        "MA Crossover": MACrossoverStrategy(),
        "RSI": RSIStrategy(),
    }

    for ticker in tickers:
        df = load_data(ticker)
        if df.empty:
            continue

        featured = compute_all_features(df, add_targets=False)
        clean = featured.dropna(subset=["close", "open", "high", "low"]).reset_index(drop=True)

        print(f"\n{'═' * 60}")
        print(f"  Backtest Results: {ticker}")
        print(f"{'═' * 60}")

        for name, strategy in strategies.items():
            signals = strategy.generate_signals(clean)
            result = run_backtest(clean, signals, ticker)
            summary = result.summary()
            print(f"\n  {name}:")
            for k, v in summary.items():
                print(f"    {k:25s}: {v}")


def run_signals(tickers=None):
    """Step 5: Generate current signals."""
    from data_pipeline import load_data
    from feature_engineering import compute_all_features
    from strategy_engine import get_all_signals

    logger.info("=" * 60)
    logger.info("STEP 5: Signal Generation")
    logger.info("=" * 60)

    if tickers is None:
        tickers = config.STOCK_UNIVERSE

    print(f"\n{'═' * 70}")
    print(f"  {'Ticker':15s} | {'Price':>10s} | {'Momentum':>10s} | {'RSI':>10s} | {'Overall':>10s}")
    print(f"{'═' * 70}")

    for ticker in tickers:
        df = load_data(ticker)
        if df.empty:
            continue

        featured = compute_all_features(df, add_targets=False)
        clean = featured.dropna(subset=["close"]).reset_index(drop=True)
        if len(clean) < 50:
            continue

        signal_df = get_all_signals(clean)
        latest = signal_df.iloc[-1]
        price = latest["close"]

        def sig_label(v):
            return "BUY " if v > 0 else "SELL" if v < 0 else "HOLD"

        print(
            f"  {ticker:15s} | ₹{price:>9,.2f} | "
            f"{sig_label(latest.get('Momentum', 0)):>10s} | "
            f"{sig_label(latest.get('RSI', 0)):>10s} | "
            f"{sig_label(latest.get('signal', 0)):>10s}"
        )

    print(f"{'═' * 70}")


def run_alerts(tickers=None):
    """Step 6: Check and send alerts."""
    from data_pipeline import load_data
    from feature_engineering import compute_all_features
    from strategy_engine import get_all_signals
    from alerts import check_and_send_alerts
    import pandas as pd

    logger.info("=" * 60)
    logger.info("STEP 6: Alert Check")
    logger.info("=" * 60)

    if tickers is None:
        tickers = config.STOCK_UNIVERSE

    all_signal_rows = []
    for ticker in tickers:
        df = load_data(ticker)
        if df.empty:
            continue

        featured = compute_all_features(df, add_targets=False)
        clean = featured.dropna(subset=["close"]).reset_index(drop=True)
        if len(clean) < 50:
            continue

        signal_df = get_all_signals(clean)
        latest = signal_df.iloc[-1]
        all_signal_rows.append({
            "ticker": ticker,
            "date": latest["date"],
            "close": latest["close"],
            "signal": latest.get("signal", 0),
            "strategy": "Combined",
        })

    if all_signal_rows:
        signals_df = pd.DataFrame(all_signal_rows)
        alerts = check_and_send_alerts(signals_df)
        logger.info("Sent %d alerts", len(alerts))
    else:
        logger.info("No signals to alert on")


def main():
    parser = argparse.ArgumentParser(description="AI Stock Trading System")
    parser.add_argument(
        "command",
        choices=["pipeline", "features", "train", "backtest", "signals", "alerts", "dashboard", "all"],
        help="Command to run",
    )
    parser.add_argument(
        "--tickers",
        nargs="*",
        default=None,
        help="Specific tickers to process (default: all in STOCK_UNIVERSE)",
    )

    args = parser.parse_args()

    if args.command == "pipeline":
        run_data_pipeline(args.tickers)

    elif args.command == "features":
        run_feature_engineering(args.tickers)

    elif args.command == "train":
        run_model_training(args.tickers)

    elif args.command == "backtest":
        run_backtesting(args.tickers)

    elif args.command == "signals":
        run_signals(args.tickers)

    elif args.command == "alerts":
        run_alerts(args.tickers)

    elif args.command == "dashboard":
        import subprocess
        logger.info("Starting Streamlit dashboard...")
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "dashboard.py",
            "--server.port", str(config.DASHBOARD_PORT),
        ])

    elif args.command == "all":
        run_data_pipeline(args.tickers)
        run_feature_engineering(args.tickers)
        run_model_training(args.tickers)
        run_backtesting(args.tickers)
        run_signals(args.tickers)
        logger.info("All steps complete!")


if __name__ == "__main__":
    main()
