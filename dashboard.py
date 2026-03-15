"""
Streamlit Dashboard
Interactive UI for predictions, signals, charts, and performance metrics.
"""
import logging
import sys
import os

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

import config
from data_pipeline import load_data, run_full_pipeline, update_data
from feature_engineering import compute_all_features, prepare_ml_dataset, get_feature_columns
from model_training import train_all_models, predict, load_model
from strategy_engine import (
    get_all_signals, MomentumStrategy, MeanReversionStrategy,
    MACrossoverStrategy, RSIStrategy,
)
from backtesting import run_backtest, BacktestEngine
from portfolio_management import PortfolioManager

logger = logging.getLogger(__name__)

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Stock Trading System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.title("📈 AI Stock Trader")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Stock Analysis", "Model Training", "Backtesting", "Portfolio", "Signals & Alerts"],
)

st.sidebar.markdown("---")
selected_ticker = st.sidebar.selectbox("Select Stock", config.STOCK_UNIVERSE)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Update Data"):
    with st.spinner("Fetching latest data..."):
        update_data()
    st.sidebar.success("Data updated!")

if st.sidebar.button("📥 Full Data Download"):
    with st.spinner("Downloading all historical data..."):
        run_full_pipeline()
    st.sidebar.success("Full download complete!")


# ─── Helper Functions ─────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_stock_data(ticker):
    df = load_data(ticker)
    if df.empty:
        return pd.DataFrame()
    return compute_all_features(df)


def plot_candlestick_simple(df, title="Price Chart", n_days=120):
    """Plot a simplified price chart with MAs."""
    df_plot = df.tail(n_days).copy()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), height_ratios=[3, 1], sharex=True)

    ax1.plot(df_plot["date"], df_plot["close"], label="Close", linewidth=1.5, color="#2196F3")

    for window in config.MA_WINDOWS:
        col = f"sma_{window}"
        if col in df_plot.columns:
            ax1.plot(df_plot["date"], df_plot[col], label=f"SMA {window}", linewidth=0.8, alpha=0.7)

    # Bollinger Bands
    if "bb_upper" in df_plot.columns:
        ax1.fill_between(
            df_plot["date"], df_plot["bb_lower"], df_plot["bb_upper"],
            alpha=0.1, color="gray", label="BB"
        )

    ax1.set_title(title, fontsize=14, fontweight="bold")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylabel("Price (₹)")

    # Volume
    colors = ["#4CAF50" if c >= o else "#F44336"
              for c, o in zip(df_plot["close"], df_plot["open"])]
    ax2.bar(df_plot["date"], df_plot["volume"], color=colors, alpha=0.7)
    ax2.set_ylabel("Volume")
    ax2.grid(True, alpha=0.3)

    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig


def plot_rsi(df, n_days=120):
    """Plot RSI indicator."""
    df_plot = df.tail(n_days)
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.plot(df_plot["date"], df_plot["rsi"], color="#9C27B0", linewidth=1)
    ax.axhline(y=70, color="red", linestyle="--", alpha=0.5, label="Overbought (70)")
    ax.axhline(y=30, color="green", linestyle="--", alpha=0.5, label="Oversold (30)")
    ax.fill_between(df_plot["date"], 30, 70, alpha=0.05, color="gray")
    ax.set_title("RSI (14)", fontsize=12)
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig


def plot_macd(df, n_days=120):
    """Plot MACD indicator."""
    df_plot = df.tail(n_days)
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.plot(df_plot["date"], df_plot["macd"], label="MACD", color="#2196F3", linewidth=1)
    ax.plot(df_plot["date"], df_plot["macd_signal"], label="Signal", color="#FF9800", linewidth=1)

    colors = ["#4CAF50" if v >= 0 else "#F44336" for v in df_plot["macd_histogram"]]
    ax.bar(df_plot["date"], df_plot["macd_histogram"], color=colors, alpha=0.5)
    ax.set_title("MACD", fontsize=12)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig


def plot_equity_curve(result):
    """Plot equity curve from backtest result."""
    fig, ax = plt.subplots(figsize=(12, 5))
    result.equity_curve.plot(ax=ax, color="#2196F3", linewidth=1.5)
    ax.axhline(y=config.INITIAL_CAPITAL, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Equity Curve", fontsize=14, fontweight="bold")
    ax.set_ylabel("Portfolio Value (₹)")
    ax.grid(True, alpha=0.3)
    ax.fill_between(result.equity_curve.index, config.INITIAL_CAPITAL,
                     result.equity_curve.values, alpha=0.1, color="#2196F3")
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig


# ─── Pages ────────────────────────────────────────────────────────────────────

if page == "Dashboard":
    st.title("📈 AI Stock Trading Dashboard")
    st.markdown("---")

    df = get_stock_data(selected_ticker)
    if df.empty:
        st.warning("No data available. Click 'Full Data Download' in the sidebar to fetch data.")
    else:
        # Key metrics row
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        daily_change = ((latest["close"] - prev["close"]) / prev["close"])

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Close Price", f"₹{latest['close']:,.2f}", f"{daily_change:.2%}")
        col2.metric("Volume", f"{latest['volume']:,.0f}")
        col3.metric("RSI", f"{latest.get('rsi', 0):.1f}")
        col4.metric("Volatility", f"{latest.get('volatility', 0):.2%}")
        col5.metric("Daily Return", f"{latest.get('daily_return', 0):.2%}")

        st.markdown("---")

        # Price chart
        n_days = st.slider("Chart Period (days)", 30, 500, 120)
        st.pyplot(plot_candlestick_simple(df, f"{selected_ticker} Price Chart", n_days))

        # Indicators
        col_rsi, col_macd = st.columns(2)
        with col_rsi:
            if "rsi" in df.columns:
                st.pyplot(plot_rsi(df, n_days))
        with col_macd:
            if "macd" in df.columns:
                st.pyplot(plot_macd(df, n_days))

        # Signals summary
        st.markdown("### Trading Signals")
        signal_df = get_all_signals(df)
        latest_signals = signal_df.iloc[-1]
        sig_cols = st.columns(5)
        for i, strat in enumerate(["Momentum", "MeanReversion", "MACrossover", "RSI", "signal"]):
            if strat in signal_df.columns:
                val = latest_signals[strat]
                label = "BUY 🟢" if val > 0 else "SELL 🔴" if val < 0 else "HOLD ⚪"
                sig_cols[i].metric(strat, label)


elif page == "Stock Analysis":
    st.title(f"📊 Stock Analysis: {selected_ticker}")
    st.markdown("---")

    df = get_stock_data(selected_ticker)
    if df.empty:
        st.warning("No data available.")
    else:
        tab1, tab2, tab3 = st.tabs(["Technical Indicators", "Returns Analysis", "Raw Data"])

        with tab1:
            n_days = st.slider("Period", 30, 500, 120, key="analysis_period")
            st.pyplot(plot_candlestick_simple(df, f"{selected_ticker}", n_days))

            col1, col2 = st.columns(2)
            with col1:
                if "rsi" in df.columns:
                    st.pyplot(plot_rsi(df, n_days))
            with col2:
                if "macd" in df.columns:
                    st.pyplot(plot_macd(df, n_days))

            # Bollinger Band %B
            if "bb_pct" in df.columns:
                fig, ax = plt.subplots(figsize=(12, 3))
                df_tail = df.tail(n_days)
                ax.plot(df_tail["date"], df_tail["bb_pct"], color="#FF5722", linewidth=1)
                ax.axhline(y=1, color="red", linestyle="--", alpha=0.5)
                ax.axhline(y=0, color="green", linestyle="--", alpha=0.5)
                ax.set_title("Bollinger Band %B", fontsize=12)
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig)

        with tab2:
            df_recent = df.tail(252)

            col1, col2 = st.columns(2)
            with col1:
                # Return distribution
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.hist(df_recent["daily_return"].dropna(), bins=50, color="#2196F3", alpha=0.7, edgecolor="white")
                ax.axvline(x=0, color="red", linestyle="--")
                ax.set_title("Daily Return Distribution (1Y)")
                ax.set_xlabel("Return")
                ax.grid(True, alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig)

            with col2:
                # Cumulative returns
                if "cumulative_return" in df_recent.columns:
                    fig, ax = plt.subplots(figsize=(6, 4))
                    ax.plot(df_recent["date"], df_recent["cumulative_return"], color="#4CAF50", linewidth=1.5)
                    ax.set_title("Cumulative Return (1Y)")
                    ax.grid(True, alpha=0.3)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)

            # Stats table
            st.markdown("### Return Statistics")
            returns = df_recent["daily_return"].dropna()
            stats = {
                "Mean Daily Return": f"{returns.mean():.4%}",
                "Std Daily Return": f"{returns.std():.4%}",
                "Annualized Return": f"{returns.mean() * 252:.2%}",
                "Annualized Volatility": f"{returns.std() * np.sqrt(252):.2%}",
                "Sharpe Ratio": f"{(returns.mean() / returns.std()) * np.sqrt(252):.4f}" if returns.std() > 0 else "N/A",
                "Skewness": f"{returns.skew():.4f}",
                "Kurtosis": f"{returns.kurtosis():.4f}",
                "Max Daily Gain": f"{returns.max():.2%}",
                "Max Daily Loss": f"{returns.min():.2%}",
            }
            st.table(pd.DataFrame.from_dict(stats, orient="index", columns=["Value"]))

        with tab3:
            st.dataframe(df.tail(100).sort_values("date", ascending=False), use_container_width=True)


elif page == "Model Training":
    st.title("🤖 Model Training & Evaluation")
    st.markdown("---")

    df = get_stock_data(selected_ticker)
    if df.empty:
        st.warning("No data available.")
    else:
        st.markdown(f"**Training on:** {selected_ticker} | **Samples:** {len(df)}")

        if st.button("🚀 Train All Models"):
            with st.spinner("Preparing dataset..."):
                X, y_dir, y_ret, dates, feat_cols = prepare_ml_dataset(df)
                st.info(f"Dataset: {X.shape[0]} samples, {X.shape[1]} features")

            progress = st.progress(0)
            with st.spinner("Training models..."):
                results = train_all_models(X, y_dir, feat_cols, ticker=selected_ticker)
            progress.progress(100)

            st.success("Training complete!")

            # Results table
            st.markdown("### Model Comparison")
            comparison = []
            for name, res in results.items():
                comparison.append({
                    "Model": name,
                    "Accuracy": f"{res['accuracy']:.4f}",
                    "Precision": f"{res.get('precision', 0):.4f}",
                    "Recall": f"{res.get('recall', 0):.4f}",
                    "F1 Score": f"{res.get('f1', 0):.4f}",
                    "AUC-ROC": f"{res.get('auc_roc', 0):.4f}",
                })
            st.table(pd.DataFrame(comparison).set_index("Model"))

            # Feature importance (for tree models)
            best_name = max(
                [k for k in results if results[k].get("model") is not None and k != "LSTM"],
                key=lambda k: results[k].get("auc_roc", 0),
                default=None,
            )
            if best_name and hasattr(results[best_name]["model"], "feature_importances_"):
                st.markdown(f"### Feature Importance ({best_name})")
                importances = results[best_name]["model"].feature_importances_
                feat_imp = pd.Series(importances, index=feat_cols).sort_values(ascending=True).tail(20)
                fig, ax = plt.subplots(figsize=(10, 6))
                feat_imp.plot(kind="barh", ax=ax, color="#2196F3")
                ax.set_title(f"Top 20 Features - {best_name}")
                ax.grid(True, alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig)

        # Load saved model predictions
        st.markdown("---")
        st.markdown("### Predictions")
        try:
            model, scaler, features = load_model(f"{selected_ticker}_XGBoost")
            feat_cols = get_feature_columns(df)
            X_latest = df[feat_cols].dropna()
            if not X_latest.empty:
                X_scaled = scaler.transform(X_latest.tail(10).values)
                probs = model.predict_proba(X_scaled)[:, 1]
                pred_df = pd.DataFrame({
                    "Date": df.loc[X_latest.tail(10).index, "date"].values,
                    "Close": df.loc[X_latest.tail(10).index, "close"].values,
                    "Up Probability": probs,
                    "Signal": ["BUY" if p > 0.5 else "SELL" for p in probs],
                })
                st.dataframe(pred_df, use_container_width=True)
        except FileNotFoundError:
            st.info("No saved model found. Train models first.")


elif page == "Backtesting":
    st.title("🔬 Backtesting Engine")
    st.markdown("---")

    df = get_stock_data(selected_ticker)
    if df.empty:
        st.warning("No data available.")
    else:
        clean_df = df.dropna(subset=["close", "open", "high", "low"]).reset_index(drop=True)

        col1, col2 = st.columns(2)
        with col1:
            strategy_name = st.selectbox(
                "Strategy",
                ["Momentum", "Mean Reversion", "MA Crossover", "RSI", "All Strategies"],
            )
        with col2:
            initial_cap = st.number_input("Initial Capital (₹)", value=config.INITIAL_CAPITAL, step=100000)

        col3, col4, col5 = st.columns(3)
        with col3:
            stop_loss = st.slider("Stop Loss %", 1.0, 10.0, config.STOP_LOSS_PCT * 100) / 100
        with col4:
            take_profit = st.slider("Take Profit %", 2.0, 20.0, config.TAKE_PROFIT_PCT * 100) / 100
        with col5:
            tx_cost = st.slider("Transaction Cost %", 0.0, 1.0, config.TRANSACTION_COST_PCT * 100) / 100

        if st.button("▶️ Run Backtest"):
            strategies = {
                "Momentum": MomentumStrategy(),
                "Mean Reversion": MeanReversionStrategy(),
                "MA Crossover": MACrossoverStrategy(),
                "RSI": RSIStrategy(),
            }

            if strategy_name == "All Strategies":
                selected_strategies = strategies
            else:
                selected_strategies = {strategy_name: strategies[strategy_name]}

            for name, strategy in selected_strategies.items():
                with st.spinner(f"Backtesting {name}..."):
                    signals = strategy.generate_signals(clean_df)
                    result = run_backtest(
                        clean_df, signals, selected_ticker,
                        initial_capital=initial_cap,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        transaction_cost=tx_cost,
                    )

                st.markdown(f"### {name} Strategy Results")

                # Metrics
                summary = result.summary()
                metric_cols = st.columns(4)
                metrics_list = list(summary.items())
                for i, (key, val) in enumerate(metrics_list[:4]):
                    metric_cols[i].metric(key, val)

                metric_cols2 = st.columns(4)
                for i, (key, val) in enumerate(metrics_list[4:8]):
                    metric_cols2[i].metric(key, val)

                # Equity curve
                if result.equity_curve is not None and len(result.equity_curve) > 0:
                    st.pyplot(plot_equity_curve(result))

                # Trade log
                if result.trades:
                    st.markdown("#### Recent Trades")
                    trade_data = [{
                        "Entry Date": t.entry_date,
                        "Exit Date": t.exit_date,
                        "Entry Price": f"₹{t.entry_price:,.2f}",
                        "Exit Price": f"₹{t.exit_price:,.2f}",
                        "Shares": t.shares,
                        "PnL": f"₹{t.pnl:,.2f}",
                        "Return": f"{t.return_pct:.2%}",
                        "Exit Reason": t.exit_reason,
                    } for t in result.trades[-20:]]
                    st.dataframe(pd.DataFrame(trade_data), use_container_width=True)

                st.markdown("---")


elif page == "Portfolio":
    st.title("💼 Portfolio Management")
    st.markdown("---")

    st.markdown("### Portfolio Configuration")
    col1, col2, col3 = st.columns(3)
    with col1:
        capital = st.number_input("Capital (₹)", value=config.INITIAL_CAPITAL, step=100000)
    with col2:
        risk_pct = st.slider("Risk per Trade %", 0.5, 5.0, config.RISK_PER_TRADE_PCT * 100) / 100
    with col3:
        max_pos = st.slider("Max Positions", 1, 20, config.MAX_POSITIONS)

    selected_stocks = st.multiselect(
        "Select Stocks for Portfolio",
        config.STOCK_UNIVERSE,
        default=config.STOCK_UNIVERSE[:5],
    )

    if st.button("🏃 Run Portfolio Backtest") and selected_stocks:
        from portfolio_management import run_portfolio_backtest

        with st.spinner("Running multi-stock portfolio backtest..."):
            stock_data = {}
            stock_signals = {}

            for ticker in selected_stocks:
                df = get_stock_data(ticker)
                if not df.empty:
                    clean = df.dropna(subset=["close"]).reset_index(drop=True)
                    stock_data[ticker] = clean
                    strategy = MomentumStrategy()
                    stock_signals[ticker] = strategy.generate_signals(clean)

            if stock_data:
                result = run_portfolio_backtest(stock_data, stock_signals, capital)

                # Summary metrics
                metrics = result["metrics"]
                st.markdown("### Portfolio Performance")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Return", f"{metrics.get('total_return', 0):.2%}")
                col2.metric("Win Rate", f"{metrics.get('win_rate', 0):.1%}")
                col3.metric("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}")
                col4.metric("Max Drawdown", f"{metrics.get('max_drawdown', 0):.1%}")

                # Equity curve
                if result["equity_history"]:
                    fig, ax = plt.subplots(figsize=(12, 5))
                    ax.plot(result["equity_history"], color="#2196F3", linewidth=1.5)
                    ax.axhline(y=capital, color="gray", linestyle="--", alpha=0.5)
                    ax.set_title("Portfolio Equity Curve")
                    ax.set_ylabel("Value (₹)")
                    ax.grid(True, alpha=0.3)
                    plt.tight_layout()
                    st.pyplot(fig)

                # Trades
                if result["trades"]:
                    st.markdown("### Trade Log")
                    trades_df = pd.DataFrame(result["trades"])
                    st.dataframe(trades_df, use_container_width=True)
            else:
                st.warning("No data available for selected stocks.")


elif page == "Signals & Alerts":
    st.title("🔔 Signals & Alerts")
    st.markdown("---")

    st.markdown("### Current Signals Across All Stocks")

    all_signals = []
    for ticker in config.STOCK_UNIVERSE:
        df = get_stock_data(ticker)
        if df.empty:
            continue

        clean = df.dropna(subset=["close"]).reset_index(drop=True)
        if len(clean) < 50:
            continue

        signal_df = get_all_signals(clean)
        latest = signal_df.iloc[-1]

        signal_val = latest.get("signal", 0)
        all_signals.append({
            "Ticker": ticker,
            "Price": f"₹{latest['close']:,.2f}",
            "Momentum": "BUY" if latest.get("Momentum", 0) > 0 else "SELL" if latest.get("Momentum", 0) < 0 else "HOLD",
            "Mean Reversion": "BUY" if latest.get("MeanReversion", 0) > 0 else "SELL" if latest.get("MeanReversion", 0) < 0 else "HOLD",
            "MA Cross": "BUY" if latest.get("MACrossover", 0) > 0 else "SELL" if latest.get("MACrossover", 0) < 0 else "HOLD",
            "RSI": "BUY" if latest.get("RSI", 0) > 0 else "SELL" if latest.get("RSI", 0) < 0 else "HOLD",
            "Overall": "🟢 BUY" if signal_val > 0 else "🔴 SELL" if signal_val < 0 else "⚪ HOLD",
        })

    if all_signals:
        st.dataframe(pd.DataFrame(all_signals).set_index("Ticker"), use_container_width=True)
    else:
        st.info("No data available. Download data first.")

    # Alert configuration
    st.markdown("---")
    st.markdown("### Alert Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Telegram Bot Token", value="Set via TELEGRAM_BOT_TOKEN env var", disabled=True)
        st.text_input("Telegram Chat ID", value="Set via TELEGRAM_CHAT_ID env var", disabled=True)
    with col2:
        st.text_input("Email Sender", value="Set via EMAIL_SENDER env var", disabled=True)
        st.text_input("Email Receiver", value="Set via EMAIL_RECEIVER env var", disabled=True)

    st.info("Configure alerts by setting environment variables. See README for details.")

# ─── Footer ──────────────────────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.caption("AI Stock Trading System v1.0")
st.sidebar.caption("For personal use only. Not financial advice.")
