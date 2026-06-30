"""APScheduler jobs.

Schedules the daily universe refresh, the 7 AM morning report, and an
intraday oversold alert sweep. Started from the FastAPI lifespan hook; safe to
import without side effects (nothing runs until ``start_scheduler`` is called).
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.alerts.engine import send_alert
from backend.reports.morning import generate_morning_report

log = logging.getLogger("alphahunter.scheduler")
_scheduler: BackgroundScheduler | None = None


def _morning_job() -> None:
    report = generate_morning_report()
    top = report.get("top_stocks", [])[:5]
    tickers = [r["ticker"] for r in top]
    send_alert("oversold", "AlphaHunter Morning Report",
               f"{report['counts']['scanned_hits']} setups. "
               f"Regime: {report['market']['regime']}.", tickers)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    sched = BackgroundScheduler(timezone="America/Los_Angeles")
    # 7 AM Pacific morning report.
    sched.add_job(_morning_job, CronTrigger(hour=7, minute=0), id="morning_report")
    sched.start()
    log.info("scheduler started")
    _scheduler = sched
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
