# Cricket Scraping System

## Overview

This project is a Python-based scraping system that monitors cricket match schedules and data from [CREX](https://crex.com). It scrapes the match list page, tracks upcoming matches, and collects detailed match data including Match Info, Squads, Live scores, and Scorecards — all saved to MongoDB.

---

## Tech Stack

- **Python** — scraping logic and data schemas
- **MongoDB** — storing all scraped data
- **Selenium** — headless Chrome browser for JavaScript-rendered pages
- **Pydantic** — Python data schemas / models
- **Celery + Redis** — automated task scheduling *(optional bonus)*

---

## Project Structure

```
cricket_scraper/
│
├── scrappers/
│   ├── __init__.py
│   ├── schemas.py              # Python data schemas for all scraped data
│   ├── db.py                   # MongoDB connection and save helpers
│   ├── browser.py              # Selenium headless Chrome setup
│   ├── match_list_scraper.py   # Scrapes match list from crex.com/fixtures/match-list
│   ├── match_detail_scraper.py # Scrapes Match Info and Squads tabs
│   ├── live_scraper.py         # Scrapes Live and Scorecard tabs once match starts
│   └── tasks.py                # Celery tasks for automated scheduling (bonus)
│
├── main.py                     # CLI entry point to run scrapers
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
└── README.md
```

---

## Objectives Covered

| Objective | File |
|---|---|
| Python schemas for all data points | `scrappers/schemas.py` |
| Scraper for match list page | `scrappers/match_list_scraper.py` |
| Scraper for Match Info tab | `scrappers/match_detail_scraper.py` |
| Scraper for Squads tab | `scrappers/match_detail_scraper.py` |
| Scraper for Live tab (once match starts) | `scrappers/live_scraper.py` |
| Scraper for Scorecard tab (once match starts) | `scrappers/live_scraper.py` |
| Save all data to MongoDB | `scrappers/db.py` |
| Celery scheduling (bonus) | `scrappers/tasks.py` |

---

## Prerequisites

Before running the project, make sure you have the following installed:

- **Python 3.11+** → https://www.python.org/downloads/
- **Google Chrome** → https://www.google.com/chrome/
- **MongoDB** → https://www.mongodb.com/try/download/community
  - During install, check **"Install MongoDB as a Service"** so it runs automatically
- **Redis** *(only needed for Celery bonus)* → https://redis.io/download

---

## Setup Instructions

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/cricket_scraper.git
cd cricket_scraper
```

### Step 2 — Create and activate virtual environment

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure environment variables

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Open the `.env` file and set your values:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=cricket_scraper
CELERY_BROKER_URL=redis://localhost:6379/0
```

### Step 5 — Make sure MongoDB is running

**If installed as a service** (recommended), MongoDB starts automatically. To verify:
```bash
mongosh
```
If it connects, MongoDB is running. Type `exit` to close.

**If not running as a service:**
```bash
mongod
```

---

## Running the Scrapers

### Run everything at once

```bash
python main.py --scraper all
```

### Run individual scrapers

```bash
# Step 1: Scrape the match list / schedule page
python main.py --scraper matches

# Step 2: Scrape Match Info + Squads for all pending matches
python main.py --scraper details

# Step 3: Poll Live scores + Scorecards (loops every 60 seconds)
python main.py --scraper live

# Step 3 (single pass, no loop):
python main.py --scraper live --once

# Custom poll interval (e.g. every 30 seconds):
python main.py --scraper live --poll-interval 30
```

---



## MongoDB Collections

After running the scrapers, data is saved in these collections:

| Collection | Description |
|---|---|
| `match_summaries` | All matches from the schedule/fixtures page |
| `match_info` | Detailed info per match (venue, toss, umpires, result) |
| `squads` | Team player lists per match |
| `scorecards` | Full batting and bowling scorecards |
| `live_scores` | Live score snapshots (time-series, one document per poll) |

### Verify data in MongoDB

```bash
mongosh
use cricket_scraper
db.match_summaries.find().pretty()
db.match_info.find().pretty()
db.squads.find().pretty()
db.scorecards.find().pretty()
db.live_scores.find().pretty()
```

---

## How It Works

1. **Match List Scraper** opens `crex.com/fixtures/match-list`, collects all match links, and saves each match to the `match_summaries` collection.

2. **Match Detail Scraper** reads pending matches from MongoDB and scrapes two pages per match:
   - `<match_url>/match-details` → Match Info
   - `<match_url>/match-squads` → Squads

3. **Live Scraper** reads only matches marked as `live` from MongoDB and scrapes:
   - `<match_url>` → Live score and commentary
   - `<match_url>/match-scorecard` → Full scorecard
   
   Live scores are stored as time-series (a new document is inserted every poll).

4. **Celery Tasks** wrap all scrapers as background tasks with an automatic schedule using Redis as the broker.

---

## Data Schemas

All schemas are defined in `scrappers/schemas.py` using Pydantic v2:

| Schema | Key Fields |
|---|---|
| `MatchSummary` | match_id, team_a, team_b, series_name, status, match_url |
| `MatchInfo` | venue, toss_winner, toss_decision, umpires, referee, result |
| `Squad` | team_name, players (name, role, is_captain, is_keeper) |
| `Scorecard` | innings list → batting rows, bowling rows, fall of wickets |
| `LiveScore` | score, overs, run_rate, recent_balls, batsmen, commentary |

---

## Source

Data source: [https://crex.com](https://crex.com)
