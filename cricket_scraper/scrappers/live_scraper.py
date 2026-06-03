

import logging
import re
import time
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from .browser import get_driver, wait_for, BASE_URL
from .db import save_live_score, save_scorecard, get_pending_matches
from .schemas import (
    LiveScore, LiveBallEvent, BattingEntry, BowlingEntry,
    Scorecard, InningsScorecard,
)

logger = logging.getLogger(__name__)




def scrape_live(driver, match_id: str, match_url: str) -> dict | None:
    try:
        logger.info("[%s] Live → %s", match_id, match_url)
        driver.get(match_url)
        time.sleep(3)

        def _t(css: str) -> str:
            try:
                return driver.find_element(By.CSS_SELECTOR, css).text.strip()
            except NoSuchElementException:
                return ""

        # Score: CREX shows e.g. "102-7" or "93/7(20.0)"
        score = _t("[class*='score'], [class*='Score']")
        overs = _t("[class*='over'], [class*='Over']")
        status = _t("[class*='status'], [class*='Status'], [class*='result'], [class*='Result']")

        # Teams
        team_els = driver.find_elements(By.CSS_SELECTOR, "[class*='team-name'], [class*='teamName']")
        batting_team = team_els[0].text.strip() if len(team_els) > 0 else ""
        bowling_team = team_els[1].text.strip() if len(team_els) > 1 else ""

        # Recent balls  (shown as over summary like "1 1 1 0 wd 1")
        recent_balls = [
            el.text.strip()
            for el in driver.find_elements(By.CSS_SELECTOR, "[class*='ball'], [class*='Ball']")
            if el.text.strip()
        ]

        # Ball-by-ball commentary rows
        ball_events: list[LiveBallEvent] = []
        for row in driver.find_elements(By.CSS_SELECTOR, "[class*='commentary'], [class*='Commentary']"):
            text = row.text.strip()
            if not text:
                continue
            over_match = re.search(r"(\d+\.\d+)", text)
            over = over_match.group(1) if over_match else ""
            runs_match = re.search(r"\b([0-9W])\b", text)
            run_val = 0
            if runs_match and runs_match.group(1).isdigit():
                run_val = int(runs_match.group(1))
            is_wicket = any(w in text.lower() for w in ["out", "wicket", "caught", "bowled", "lbw", "run out"])
            ball_events.append(LiveBallEvent(over=over, commentary=text[:200], runs=run_val, wicket=is_wicket))

        # Current batsmen
        batsmen: list[BattingEntry] = []
        for row in driver.find_elements(By.CSS_SELECTOR, "table tr")[1:3]:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 4:
                try:
                    batsmen.append(BattingEntry(
                        batsman=cells[0].text.strip(),
                        runs=int(re.sub(r"\D", "", cells[1].text) or "0"),
                        balls=int(re.sub(r"\D", "", cells[2].text) or "0"),
                    ))
                except Exception:
                    pass

        live = LiveScore(
            match_id=match_id,
            status=status,
            batting_team=batting_team,
            bowling_team=bowling_team,
            score=score,
            overs=overs,
            recent_balls=recent_balls[:12],
            batsmen_on_crease=batsmen,
            ball_by_ball=ball_events[:50],
            scraped_at=datetime.utcnow(),
        )
        doc = live.model_dump()
        save_live_score(doc)
        logger.info("[%s] Live saved. Score: %s", match_id, score)
        return doc

    except Exception as exc:
        logger.error("[%s] Live failed: %s", match_id, exc)
        return None


def _parse_batting_row(cells) -> BattingEntry | None:
    try:
        return BattingEntry(
            batsman=cells[0].text.strip(),
            dismissal=cells[1].text.strip() if len(cells) > 5 else "",
            runs=int(re.sub(r"\D", "", cells[-5].text) or "0"),
            balls=int(re.sub(r"\D", "", cells[-4].text) or "0"),
            fours=int(re.sub(r"\D", "", cells[-3].text) or "0"),
            sixes=int(re.sub(r"\D", "", cells[-2].text) or "0"),
            strike_rate=float(re.sub(r"[^\d.]", "", cells[-1].text) or "0"),
        )
    except Exception:
        return None


def _parse_bowling_row(cells) -> BowlingEntry | None:
    try:
        return BowlingEntry(
            bowler=cells[0].text.strip(),
            overs=float(re.sub(r"[^\d.]", "", cells[1].text) or "0"),
            maidens=int(re.sub(r"\D", "", cells[2].text) or "0"),
            runs=int(re.sub(r"\D", "", cells[3].text) or "0"),
            wickets=int(re.sub(r"\D", "", cells[4].text) or "0") if len(cells) > 4 else 0,
            economy=float(re.sub(r"[^\d.]", "", cells[5].text) or "0") if len(cells) > 5 else 0.0,
        )
    except Exception:
        return None


def scrape_scorecard(driver, match_id: str, match_url: str) -> dict | None:
    url = match_url.rstrip("/") + "/match-scorecard"
    try:
        logger.info("[%s] Scorecard → %s", match_id, url)
        driver.get(url)
        time.sleep(3)

        innings_list: list[InningsScorecard] = []

        # CREX renders each innings as a separate block/section
        innings_blocks = driver.find_elements(
            By.CSS_SELECTOR,
            "[class*='innings'], [class*='Innings'], [class*='scorecard-block']"
        )

        if not innings_blocks:
            # fallback: all tables on page
            innings_blocks = driver.find_elements(By.TAG_NAME, "table")

        for idx, block in enumerate(innings_blocks[:4]):  # max 4 innings
            try:
                batting: list[BattingEntry] = []
                bowling: list[BowlingEntry] = []
                total_runs = wickets = 0
                overs_f = extras = 0.0

                tables = block.find_elements(By.TAG_NAME, "table")
                for table in tables:
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    if not rows:
                        continue

                    header = rows[0].text.lower()
                    if any(h in header for h in ["batsman", "batter", "runs", "r"]):
                        for row in rows[1:]:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) < 4:
                                continue
                            row_text = row.text.lower()
                            if "total" in row_text:
                                nums = re.findall(r"\d+\.?\d*", row.text)
                                if nums:
                                    total_runs = int(nums[0])
                                    wickets = int(nums[1]) if len(nums) > 1 else 0
                                    overs_f = float(nums[2]) if len(nums) > 2 else 0.0
                            elif "extras" in row_text:
                                nums = re.findall(r"\d+", row.text)
                                extras = int(nums[-1]) if nums else 0
                            else:
                                entry = _parse_batting_row(cells)
                                if entry and entry.batsman:
                                    batting.append(entry)

                    elif any(h in header for h in ["bowler", "overs", "o", "economy"]):
                        for row in rows[1:]:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) < 4:
                                continue
                            entry = _parse_bowling_row(cells)
                            if entry and entry.bowler:
                                bowling.append(entry)

                # Fall of wickets
                fow = [
                    el.text.strip()
                    for el in block.find_elements(By.CSS_SELECTOR, "[class*='fow'], [class*='fall']")
                    if el.text.strip()
                ]

                # Team name from block heading
                bat_team = ""
                try:
                    bat_team = block.find_element(By.CSS_SELECTOR, "h2, h3, h4, [class*='heading']").text.strip()
                except NoSuchElementException:
                    pass

                if batting or bowling:
                    innings_list.append(InningsScorecard(
                        innings_number=idx + 1,
                        batting_team=bat_team,
                        bowling_team="",
                        total_runs=total_runs,
                        wickets=wickets,
                        overs=overs_f,
                        extras=int(extras),
                        batting=batting,
                        bowling=bowling,
                        fall_of_wickets=fow,
                    ))
            except Exception as exc:
                logger.warning("[%s] innings %d parse error: %s", match_id, idx, exc)

        result_text = ""
        try:
            result_text = driver.find_element(
                By.CSS_SELECTOR, "[class*='result'], [class*='Result'], [class*='status']"
            ).text.strip()
        except NoSuchElementException:
            pass

        scorecard = Scorecard(
            match_id=match_id,
            innings=innings_list,
            result=result_text,
            scraped_at=datetime.utcnow(),
        )
        doc = scorecard.model_dump()
        save_scorecard(doc)
        logger.info("[%s] Scorecard saved (%d innings).", match_id, len(innings_list))
        return doc

    except Exception as exc:
        logger.error("[%s] Scorecard failed: %s", match_id, exc)
        return None



def run_live_scraper(poll_interval: int = 60) -> None:
    logger.info("Live scraper started. Poll every %ds. Ctrl+C to stop.", poll_interval)
    with get_driver() as driver:
        while True:
            matches = get_pending_matches()
            live = [m for m in matches if m.get("status") == "live"]
            logger.info("%d live matches.", len(live))
            for match in live:
                mid = match["match_id"]
                url = match.get("match_url", "")
                if url and "unknown" not in mid:
                    scrape_live(driver, mid, url)
                    scrape_scorecard(driver, mid, url)
            logger.info("Sleeping %ds...", poll_interval)
            time.sleep(poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_live_scraper()
