
import logging
import time
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from .browser import get_driver, wait_for, BASE_URL
from .db import save_match_info, save_squad, get_pending_matches
from .schemas import MatchInfo, Squad, Player

logger = logging.getLogger(__name__)




def scrape_match_info(driver, match_id: str, match_url: str) -> dict | None:
    url = match_url.rstrip("/") + "/match-details"
    try:
        logger.info("[%s] Match Info → %s", match_id, url)
        driver.get(url)
        time.sleep(3)

        page = driver.page_source

        def _find(labels: list[str]) -> str:
            
            for label in labels:
                try:
                    # Try rows that contain the label
                    els = driver.find_elements(By.XPATH, f"//*[contains(text(), '{label}')]")
                    for el in els:
                        try:
                            # value is usually the next sibling span/div/td
                            sibling = el.find_element(
                                By.XPATH,
                                "following-sibling::*[1] | ../following-sibling::*[1]//*"
                            )
                            val = sibling.text.strip()
                            if val and val.lower() != label.lower():
                                return val
                        except Exception:
                            pass
                        # fallback: parent text minus the label
                        parent_text = el.find_element(By.XPATH, "..").text.strip()
                        val = parent_text.replace(label, "").strip(" :\n")
                        if val:
                            return val
                except Exception:
                    pass
            return ""

        info = MatchInfo(
            match_id=match_id,
            series_name=_find(["Series", "Tournament", "Competition"]),
            match_number=_find(["Match", "Match No", "Match Number"]),
            match_type=_find(["Format", "Type", "Match Type"]),
            venue=_find(["Venue", "Stadium", "Ground"]),
            city=_find(["City", "Location"]),
            country=_find(["Country"]),
            toss_winner=_find(["Toss", "Toss Won"]),
            toss_decision=_find(["Decision", "Elected", "Chose to"]),
            umpire_1=_find(["Umpire 1", "1st Umpire", "On-field Umpire"]),
            umpire_2=_find(["Umpire 2", "2nd Umpire"]),
            third_umpire=_find(["Third Umpire", "TV Umpire"]),
            match_referee=_find(["Match Referee", "Referee"]),
            result=_find(["Result", "Match Result"]),
            scraped_at=datetime.utcnow(),
        )
        doc = info.model_dump()
        save_match_info(doc)
        logger.info("[%s] Match Info saved.", match_id)
        return doc

    except Exception as exc:
        logger.error("[%s] Match Info failed: %s", match_id, exc)
        return None



def scrape_squads(driver, match_id: str, match_url: str) -> list[dict]:
    url = match_url.rstrip("/") + "/match-squads"
    results = []
    try:
        logger.info("[%s] Squads → %s", match_id, url)
        driver.get(url)
        time.sleep(3)

        # Each team section has a heading then a list of players
        # Try multiple selectors CREX may use
        team_sections = driver.find_elements(
            By.CSS_SELECTOR,
            "[class*='squad'], [class*='playing-xi'], [class*='playingXI'], [class*='team-squad']"
        )

        if not team_sections:
            # Fallback: find all headings with team names and collect sibling player lists
            team_sections = driver.find_elements(By.CSS_SELECTOR, "h2, h3, h4")

        teams_data: dict[str, list[Player]] = {}
        current_team = ""

        # Walk all meaningful elements on the page
        all_els = driver.find_elements(By.CSS_SELECTOR, "h2, h3, h4, li, [class*='player']")
        for el in all_els:
            tag = el.tag_name.lower()
            text = el.text.strip()
            if not text:
                continue

            # Detect team heading
            if tag in ("h2", "h3", "h4") and len(text) < 60:
                current_team = text
                if current_team not in teams_data:
                    teams_data[current_team] = []
                continue

            # Detect player entries
            if current_team and tag in ("li", "div", "span") or "player" in el.get_attribute("class").lower() if el.get_attribute("class") else False:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if lines:
                    name = lines[0]
                    role = lines[1] if len(lines) > 1 else ""
                    is_captain = "(c)" in text.lower() or "captain" in text.lower()
                    is_keeper  = "(wk)" in text.lower() or "keeper" in text.lower()
                    if len(name) > 2 and len(name) < 60:
                        teams_data[current_team].append(
                            Player(name=name, role=role, is_captain=is_captain, is_keeper=is_keeper)
                        )

        for team_name, players in teams_data.items():
            if not players:
                continue
            from .db import save_squad
            squad = Squad(
                match_id=match_id,
                team_name=team_name,
                players=players,
                scraped_at=datetime.utcnow(),
            )
            doc = squad.model_dump()
            save_squad(doc)
            results.append(doc)
            logger.info("[%s] Squad saved: %s (%d players)", match_id, team_name, len(players))

        if not results:
            logger.warning("[%s] No squad data found at %s", match_id, url)

    except Exception as exc:
        logger.error("[%s] Squads failed: %s", match_id, exc)

    return results


def run_match_detail_scraper() -> None:
    pending = get_pending_matches()
    logger.info("Found %d pending matches.", len(pending))

    with get_driver() as driver:
        for match in pending:
            match_id  = match.get("match_id", "")
            match_url = match.get("match_url", "")
            if not match_url or "unknown" in match_id:
                logger.warning("Skipping match with no URL: %s", match_id)
                continue
            scrape_match_info(driver, match_id, match_url)
            scrape_squads(driver, match_id, match_url)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_match_detail_scraper()
