

import logging
import re
import time
from datetime import datetime, timezone

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from .browser import get_driver, wait_for, BASE_URL, scroll_to_bottom
from .db import save_match_summary
from .schemas import MatchSummary

logger = logging.getLogger(__name__)

SCHEDULE_URL = f"{BASE_URL}/fixtures/match-list"


def _extract_match_id(url: str) -> str:
    
    parts = url.rstrip("/").split("-")
    return parts[-1] if parts else url.split("/")[-1]


def _parse_status(text: str) -> str:
    t = text.lower()
    if "live" in t or "yet to bat" in t or "toss" in t:
        return "live"
    if any(w in t for w in ["won", "lost", "draw", "tie", "result", "abandoned"]):
        return "completed"
    return "upcoming"


def scrape_match_list() -> list[dict]:
    results: list[dict] = []

    with get_driver() as driver:
        logger.info("Opening %s", SCHEDULE_URL)
        driver.get(SCHEDULE_URL)
        time.sleep(5)
        scroll_to_bottom(driver, pause=2)

        # Every match on CREX fixtures links to /cricket-live-score/...
        anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='cricket-live-score']")
        logger.info("Found %d match links", len(anchors))

        seen = set()
        for anchor in anchors:
            try:
                href = anchor.get_attribute("href") or ""
                if not href or href in seen:
                    continue
                seen.add(href)

                match_url = href if href.startswith("http") else BASE_URL + href
                match_id = _extract_match_id(match_url)
                full_text = anchor.text.strip()

                # Status comes from text clues in the card
                status = _parse_status(full_text)

                # Teams: CREX puts both team names in the anchor text
                # e.g. "Malaysia Women MAS-W 102/7 20.0 ... Kuwait Women KUW-W 93-7 20.0"
                # Try to grab team name spans
                team_els = anchor.find_elements(
                    By.CSS_SELECTOR,
                    "[class*='team-name'], [class*='teamName'], [class*='team_name']"
                )
                team_a = team_els[0].text.strip() if len(team_els) > 0 else ""
                team_b = team_els[1].text.strip() if len(team_els) > 1 else ""

                # Series / match type from card
                series_el = ""
                try:
                    series_el = anchor.find_element(
                        By.CSS_SELECTOR,
                        "[class*='series'], [class*='tournament'], [class*='match-type']"
                    ).text.strip()
                except NoSuchElementException:
                    pass

                summary = MatchSummary(
                    match_id=match_id,
                    series_name=series_el,
                    match_title=full_text[:120],
                    team_a=team_a,
                    team_b=team_b,
                    match_url=match_url,
                    status=status,
                )
                doc = summary.model_dump()
                save_match_summary(doc)
                results.append(doc)

            except Exception as exc:
                logger.warning("Error parsing anchor: %s", exc)

    logger.info("Scraped and saved %d matches.", len(results))
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    scrape_match_list()
