"""
Alert System Module
Sends alerts via Telegram and Email when strong buy/sell signals appear.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import requests
import pandas as pd

import config

logger = logging.getLogger(__name__)


def send_telegram_alert(message: str) -> bool:
    """Send an alert message via Telegram bot."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Telegram alert sent successfully")
        return True
    except requests.RequestException as e:
        logger.error("Failed to send Telegram alert: %s", e)
        return False


def send_email_alert(subject: str, body: str) -> bool:
    """Send an alert via email (Gmail SMTP)."""
    if not config.EMAIL_SENDER or not config.EMAIL_PASSWORD or not config.EMAIL_RECEIVER:
        logger.warning("Email credentials not configured. Set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER env vars.")
        return False

    msg = MIMEMultipart()
    msg["From"] = config.EMAIL_SENDER
    msg["To"] = config.EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        server = smtplib.SMTP(config.EMAIL_SMTP_SERVER, config.EMAIL_SMTP_PORT)
        server.starttls()
        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_SENDER, config.EMAIL_RECEIVER, msg.as_string())
        server.quit()
        logger.info("Email alert sent to %s", config.EMAIL_RECEIVER)
        return True
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False


def format_signal_alert(ticker: str, signal: int, probability: float, price: float, strategy: str = "AI") -> str:
    """Format a trading signal into a readable alert message."""
    direction = "BUY" if signal == 1 else "SELL" if signal == -1 else "HOLD"
    emoji = "🟢" if signal == 1 else "🔴" if signal == -1 else "⚪"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    message = (
        f"{emoji} <b>Stock Signal Alert</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Ticker:</b> {ticker}\n"
        f"📈 <b>Signal:</b> {direction}\n"
        f"💰 <b>Price:</b> ₹{price:,.2f}\n"
        f"🎯 <b>Confidence:</b> {probability:.1%}\n"
        f"🔧 <b>Strategy:</b> {strategy}\n"
        f"🕐 <b>Time:</b> {timestamp}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    return message


def check_and_send_alerts(
    signals_df: pd.DataFrame,
    probabilities: dict = None,
    via_telegram: bool = True,
    via_email: bool = True,
) -> list:
    """
    Check for strong signals and send alerts.

    Args:
        signals_df: DataFrame with columns: ticker, date, close, signal, strategy.
        probabilities: Optional dict of {ticker: probability}.
        via_telegram: Whether to send Telegram alerts.
        via_email: Whether to send email alerts.

    Returns:
        List of alert messages that were sent.
    """
    alerts_sent = []

    if signals_df.empty:
        return alerts_sent

    # Filter for latest date and strong signals
    latest_date = signals_df["date"].max()
    latest = signals_df[signals_df["date"] == latest_date]

    for _, row in latest.iterrows():
        ticker = row.get("ticker", "UNKNOWN")
        signal = row.get("signal", 0)
        price = row.get("close", 0)
        strategy = row.get("strategy", "Combined")

        if signal != 1:
            continue

        prob = probabilities.get(ticker, 0.5) if probabilities else 0.5
        if prob >= config.ALERT_CONFIDENCE_THRESHOLD:
            message = format_signal_alert(ticker, signal, prob, price, strategy)

            if via_telegram:
                send_telegram_alert(message)
            if via_email:
                subject = f"Stock Alert: {ticker} - BUY"
                send_email_alert(subject, message)

            alerts_sent.append(message)
            logger.info("Alert sent for %s: signal=%d, prob=%.2f", ticker, signal, prob)

    return alerts_sent


def generate_daily_report(portfolio_summary: dict, signals: dict, metrics: dict) -> str:
    """Generate a daily summary report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    report = (
        f"📋 <b>Daily Trading Report</b>\n"
        f"🕐 {timestamp}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💼 <b>Portfolio</b>\n"
        f"  Cash: ₹{portfolio_summary.get('cash', 0):,.0f}\n"
        f"  Equity: ₹{portfolio_summary.get('total_equity', 0):,.0f}\n"
        f"  Return: {portfolio_summary.get('total_return', 0):.2%}\n"
        f"  Positions: {portfolio_summary.get('num_positions', 0)}\n\n"
    )

    if signals:
        report += f"📊 <b>Today's Signals</b>\n"
        for ticker, signal in signals.items():
            direction = "BUY" if signal > 0 else "SELL" if signal < 0 else "HOLD"
            report += f"  {ticker}: {direction}\n"
        report += "\n"

    if metrics:
        report += (
            f"📈 <b>Performance</b>\n"
            f"  Win Rate: {metrics.get('win_rate', 0):.1%}\n"
            f"  Sharpe: {metrics.get('sharpe_ratio', 0):.2f}\n"
            f"  Max DD: {metrics.get('max_drawdown', 0):.1%}\n"
        )

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test formatting
    msg = format_signal_alert("RELIANCE.NS", 1, 0.78, 2450.50, "XGBoost")
    print(msg)
    print("\n--- Daily Report ---")
    report = generate_daily_report(
        {"cash": 800000, "total_equity": 1050000, "total_return": 0.05, "num_positions": 3},
        {"RELIANCE.NS": 1, "TCS.NS": -1, "INFY.NS": 0},
        {"win_rate": 0.62, "sharpe_ratio": 1.45, "max_drawdown": -0.08},
    )
    print(report)
