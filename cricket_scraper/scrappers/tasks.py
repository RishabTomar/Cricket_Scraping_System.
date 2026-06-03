

import logging
import os

from celery import Celery
from celery.schedules import crontab

from .db import get_pending_matches
from .match_list_scraper import scrape_match_list
from .match_detail_scraper import scrape_match_info, scrape_squads
from .live_scraper import scrape_live, scrape_scorecard
from .browser import get_driver

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

app = Celery("cricket_scraper", broker=REDIS_URL, backend=REDIS_URL)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


app.conf.beat_schedule = {
    # Refresh the fixture list every 30 minutes
    "refresh-match-list": {
        "task": "scrappers.tasks.task_scrape_match_list",
        "schedule": 30 * 60,  # seconds
    },
    # Scrape info + squads for all pending matches every 30 minutes
    "scrape-match-details": {
        "task": "scrappers.tasks.task_scrape_all_match_details",
        "schedule": 30 * 60,
    },
    # Poll live matches every 60 seconds
    "scrape-live-scores": {
        "task": "scrappers.tasks.task_scrape_live_matches",
        "schedule": 60,
    },
}



@app.task(name="scrappers.tasks.task_scrape_match_list", bind=True, max_retries=3)
def task_scrape_match_list(self):
    """Refresh the schedule / fixture list."""
    try:
        matches = scrape_match_list()
        logger.info("task_scrape_match_list: saved %d matches", len(matches))
        return {"saved": len(matches)}
    except Exception as exc:
        logger.error("task_scrape_match_list failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scrappers.tasks.task_scrape_match_details", bind=True, max_retries=3)
def task_scrape_match_details(self, match_id: str, match_url: str):
    """Scrape Match Info + Squads for a single match."""
    try:
        with get_driver() as driver:
            scrape_match_info(driver, match_id, match_url)
            scrape_squads(driver, match_id, match_url)
        return {"match_id": match_id, "status": "ok"}
    except Exception as exc:
        logger.error("task_scrape_match_details[%s] failed: %s", match_id, exc)
        raise self.retry(exc=exc, countdown=120)


@app.task(name="scrappers.tasks.task_scrape_all_match_details")
def task_scrape_all_match_details():
    """Fan-out: queue a detail scrape task for every pending match."""
    pending = get_pending_matches()
    dispatched = 0
    for match in pending:
        mid = match.get("match_id")
        url = match.get("match_url", "")
        if mid and url:
            task_scrape_match_details.delay(mid, url)
            dispatched += 1
    logger.info("task_scrape_all_match_details: dispatched %d tasks", dispatched)
    return {"dispatched": dispatched}


@app.task(name="scrappers.tasks.task_scrape_live", bind=True, max_retries=5)
def task_scrape_live(self, match_id: str, match_url: str):
    """Scrape Live tab + Scorecard tab for a single live match."""
    try:
        with get_driver() as driver:
            scrape_live(driver, match_id, match_url)
            scrape_scorecard(driver, match_id, match_url)
        return {"match_id": match_id, "status": "ok"}
    except Exception as exc:
        logger.error("task_scrape_live[%s] failed: %s", match_id, exc)
        raise self.retry(exc=exc, countdown=30)


@app.task(name="scrappers.tasks.task_scrape_live_matches")
def task_scrape_live_matches():
    """Fan-out: queue a live scrape task for every currently live match."""
    pending = get_pending_matches()
    live = [m for m in pending if m.get("status") == "live"]
    dispatched = 0
    for match in live:
        mid = match.get("match_id")
        url = match.get("match_url", "")
        if mid and url:
            task_scrape_live.delay(mid, url)
            dispatched += 1
    logger.info("task_scrape_live_matches: dispatched %d live tasks", dispatched)
    return {"dispatched": dispatched}
