# CREX Cricket Scraper

A Python-based web scraper that collects cricket match data from [crex.com](https://crex.com) and stores it in MongoDB. Built with Selenium for JavaScript-rendered pages, Pydantic for data validation, and optional Celery for automated scheduling.

---

## 📁 Project Structure

```
cricket_scraper/
├── scrappers/
│   ├── __init__.py
│   ├── schemas.py            # Pydantic data models for all scraped data
│   ├── db.py                 # MongoDB connection and upsert helpers
│   ├── browser.py            # Shared Selenium / headless-Chrome utilities
│   ├── match_list_scraper.py # Scrapes the schedule / fixtures listing page
│   ├── match_detail_scraper.py # Scrapes Match Info + Squads tabs
│   ├── live_scraper.py       # Scrapes Live score + Scorecard tabs
│   └── tasks.py              # Celery tasks + beat schedule (optional)
├── main.py                   # CLI entry point (no Celery required)
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚙️ Setup

### 1. Prerequisites

- Python 3.11+
- Google Chrome installed
- MongoDB running (locally or via Atlas)
- Redis running — **only needed for Celery** (optional)

### 2. Clone and install dependencies

```bash
git clone <your-repo-url>
cd cricket_scraper

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

ChromeDriver is managed automatically by `webdriver-manager` — no manual download needed.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=cricket_scraper
CELERY_BROKER_URL=redis://localhost:6379/0   # only if using Celery
```

---

## 🚀 Running the Scrapers

### Option A — Simple CLI (no Celery)

```bash
# Run all scrapers once
python main.py --scraper all

# Refresh fixture / schedule list only
python main.py --scraper matches

# Scrape Match Info + Squads for all pending matches
python main.py --scraper details

# Poll live matches forever (updates every 60 seconds)
python main.py --scraper live

# Poll live matches with a custom interval (e.g. every 30 seconds)
python main.py --scraper live --poll-interval 30

# Single pass of live matches (useful for cron jobs)
python main.py --scraper live --once
```

### Option B — Celery (recommended for production)

Make sure Redis is running, then open **two terminals**:

**Terminal 1 — Worker**
```bash
celery -A scrappers.tasks worker --loglevel=info
```

**Terminal 2 — Beat Scheduler**
```bash
celery -A scrappers.tasks beat --loglevel=info
```

The beat schedule runs automatically:

| Task | Interval |
|------|----------|
| Refresh match list | Every 30 minutes |
| Scrape Match Info + Squads | Every 30 minutes |
| Poll live scores + scorecard | Every 60 seconds |

---

## 🗄️ MongoDB Collections

| Collection | Description |
|---|---|
| `match_summaries` | All matches from the schedule page |
| `match_info` | Detailed match metadata (toss, umpires, venue, etc.) |
| `squads` | Team player lineups per match |
| `scorecards` | Full batting + bowling scorecards |
| `live_scores` | Time-series live score snapshots |

---

## 📐 Data Schemas

All data models are defined in `scrappers/schemas.py` using **Pydantic v2**.

| Schema | Fields |
|---|---|
| `MatchSummary` | match_id, teams, series, venue, scheduled_time, status, match_url |
| `MatchInfo` | toss, umpires, referee, venue, result, format |
| `Squad` | team_name, list of `Player` (name, role, captain, keeper flags) |
| `Scorecard` | list of `InningsScorecard` → batting rows, bowling rows, fall of wickets |
| `LiveScore` | score, overs, run rate, recent balls, batsmen on crease, ball-by-ball |

---

## 🔧 How It Works

1. **`match_list_scraper.py`** opens `crex.com/fixtures/match-list`, scrolls to load all cards, extracts match metadata, and upserts each into `match_summaries`.

2. **`match_detail_scraper.py`** reads pending matches from MongoDB, opens each match URL, clicks the **Match Info** and **Squads** tabs, and saves structured data.

3. **`live_scraper.py`** reads only **live** matches from MongoDB, clicks the **Live** and **Scorecard** tabs, and saves data. Live scores are **time-series** (each poll inserts a new document). Designed to be polled repeatedly.

4. **`tasks.py`** wraps all scrapers as Celery tasks with a beat schedule for fully automated, production-ready operation.

---

## 📝 Notes

- CREX renders content via JavaScript — Selenium with headless Chrome is required.
- The scraper uses multiple CSS selector fallbacks since CREX's class names may change.
- All upserts use `match_id` as the unique key to avoid duplicate documents.
- Live scores use `insert_one` (not upsert) to preserve the full time-series history.
