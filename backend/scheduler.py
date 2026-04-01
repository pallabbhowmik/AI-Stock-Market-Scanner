"""
Scheduler
Runs the market scanner every 15 minutes during market hours and
triggers automatic model retraining daily after market close.
"""
import logging
import time
import threading
from datetime import datetime, timedelta, timezone

from backend import config, database
from backend.watchlist_generator import run_full_scan, run_quick_scan
from backend.training_pipeline import run_training_pipeline, get_pipeline_status

logger = logging.getLogger(__name__)

_scheduler_running = False
_scheduler_thread = None
_last_training_date: str | None = None  # tracks which day we already retrained


def _ist_now() -> datetime:
    """Return current time in IST."""
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)


def is_market_hours() -> bool:
    """Check if current time (IST) is within Indian market hours."""
    ist_now = _ist_now()

    market_open = ist_now.replace(
        hour=config.MARKET_OPEN_HOUR, minute=config.MARKET_OPEN_MINUTE, second=0
    )
    market_close = ist_now.replace(
        hour=config.MARKET_CLOSE_HOUR, minute=config.MARKET_CLOSE_MINUTE, second=0
    )

    if ist_now.weekday() >= 5:
        return False

    return market_open <= ist_now <= market_close


def _is_after_market_close() -> bool:
    """Check if we are in the post-market training window (15:35 – 23:59 IST, weekdays)."""
    ist_now = _ist_now()
    if ist_now.weekday() >= 5:
        return False
    after_close = ist_now.replace(
        hour=config.MARKET_CLOSE_HOUR, minute=config.MARKET_CLOSE_MINUTE + 5, second=0
    )
    return ist_now >= after_close


def _should_retrain_today() -> bool:
    """Return True if we haven't run the daily retraining yet today."""
    global _last_training_date
    today = _ist_now().strftime("%Y-%m-%d")
    return _last_training_date != today


def _scheduler_loop():
    """
    Background loop:
    • Every 15 min during market hours → quick scan (data refresh + predictions)
    • Once after market close each day → full model retraining pipeline
    """
    global _scheduler_running, _last_training_date

    logger.info("Scheduler started. Scan interval: %d min", config.SCAN_INTERVAL_MINUTES)

    # Run initial full scan on startup
    try:
        database.init_db()
        logger.info("Running initial full scan...")
        run_full_scan(retrain=False)
    except Exception as e:
        logger.error("Initial scan failed: %s", e)

    while _scheduler_running:
        try:
            if is_market_hours():
                logger.info("Market open — running quick scan...")
                run_quick_scan()

            elif _is_after_market_close() and _should_retrain_today():
                # Daily auto-retraining after market close
                logger.info("Market closed — starting daily model retraining...")
                _last_training_date = _ist_now().strftime("%Y-%m-%d")
                try:
                    result = run_training_pipeline()
                    logger.info("Daily retraining result: %s", result.get("status"))
                except Exception as e:
                    logger.error("Daily retraining failed: %s", e)

            else:
                logger.debug("Outside market / training window. Sleeping...")

        except Exception as e:
            logger.error("Scheduler cycle error: %s", e)

        # Sleep for the configured interval
        for _ in range(config.SCAN_INTERVAL_MINUTES * 60):
            if not _scheduler_running:
                break
            time.sleep(1)

    logger.info("Scheduler stopped.")


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler_running, _scheduler_thread

    if _scheduler_running:
        logger.warning("Scheduler is already running")
        return

    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("Scheduler thread started")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running
    _scheduler_running = False
    logger.info("Scheduler stop requested")


def get_scheduler_status() -> dict:
    """Get the current scheduler status."""
    pipeline = get_pipeline_status()
    return {
        "running": _scheduler_running,
        "market_open": is_market_hours(),
        "interval_minutes": config.SCAN_INTERVAL_MINUTES,
        "training_status": pipeline.get("status", "idle"),
        "last_training": pipeline.get("last_training"),
        "model_version": pipeline.get("model_version", "–"),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    database.init_db()
    start_scheduler()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_scheduler()
