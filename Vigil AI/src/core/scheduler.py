"""
scheduler.py - Background task scheduler for Vigil AI.

Uses APScheduler to run the two engines at configured intervals.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
from datetime import datetime, timedelta

from config.config import POETRY_INTERVAL_HOURS, DEALS_INTERVAL_HOURS

# Import the real engine functions
from src.engines.engine_1_urdu_poetry import run_engine_1
from src.engines.engine_2_deals import run_engine_2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# 1. Wrapper functions to add logging
# ----------------------------------------------------------------------
def engine_1_job():
    logger.info("🔄 [Engine 1] Running Urdu Poetry job")
    try:
        run_engine_1()
    except Exception as e:
        logger.error(f"❌ [Engine 1] Error: {e}")
    logger.info("✅ [Engine 1] Job finished")

def engine_2_job():
    logger.info("🔄 [Engine 2] Running Deals job")
    try:
        run_engine_2()
    except Exception as e:
        logger.error(f"❌ [Engine 2] Error: {e}")
    logger.info("✅ [Engine 2] Job finished")

# ----------------------------------------------------------------------
# 2. Create and start scheduler
# ----------------------------------------------------------------------
def start_scheduler():
    scheduler = BackgroundScheduler()
    
    # Engine 1: every POETRY_INTERVAL_HOURS
    scheduler.add_job(
        engine_1_job,
        trigger=IntervalTrigger(hours=POETRY_INTERVAL_HOURS),
        id="engine_1_urdu",
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(seconds=10)
    )
    
    # Engine 2: every DEALS_INTERVAL_HOURS
    scheduler.add_job(
        engine_2_job,
        trigger=IntervalTrigger(hours=DEALS_INTERVAL_HOURS),
        id="engine_2_deals",
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(seconds=15)
    )
    
    scheduler.start()
    logger.info("🚀 Scheduler started. Jobs will run every %s and %s hours.",
                POETRY_INTERVAL_HOURS, DEALS_INTERVAL_HOURS)
    return scheduler

def stop_scheduler(scheduler):
    scheduler.shutdown()
    logger.info("🛑 Scheduler stopped.")
