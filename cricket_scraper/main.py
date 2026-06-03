
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="CREX Cricket Scraper")
    parser.add_argument(
        "--scraper",
        choices=["all", "matches", "details", "live"],
        default="all",
        help="Which scraper to run (default: all)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="For live scraper: run a single pass instead of looping",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=60,
        help="Seconds between live-scraper polls (default: 60)",
    )
    args = parser.parse_args()

    if args.scraper in ("all", "matches"):
        logger.info("=== Running Match List Scraper ===")
        from scrappers.match_list_scraper import scrape_match_list
        scrape_match_list()

    if args.scraper in ("all", "details"):
        logger.info("=== Running Match Detail Scraper ===")
        from scrappers.match_detail_scraper import run_match_detail_scraper
        run_match_detail_scraper()

    if args.scraper in ("all", "live"):
        logger.info("=== Running Live Scraper ===")
        from scrappers.live_scraper import run_live_scraper, scrape_live, scrape_scorecard
        from scrappers.db import get_pending_matches
        from scrappers.browser import get_driver

        if args.once or args.scraper == "all":
            # Single pass
            matches = get_pending_matches()
            live_matches = [m for m in matches if m.get("status") == "live"]
            logger.info("Single-pass: %d live matches", len(live_matches))
            with get_driver() as driver:
                for match in live_matches:
                    mid = match["match_id"]
                    url = match.get("match_url", "")
                    if url:
                        scrape_live(driver, mid, url)
                        scrape_scorecard(driver, mid, url)
        else:
            run_live_scraper(poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
