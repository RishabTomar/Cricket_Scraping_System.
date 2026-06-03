

import os
from datetime import datetime

from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection


MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME: str = os.getenv("MONGO_DB", "cricket_scraper")

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_db():
    return get_client()[DB_NAME]


def get_collection(name: str) -> Collection:
    return get_db()[name]


def upsert_one(collection_name: str, filter_: dict, document: dict) -> None:
    """Insert or replace a single document."""
    col = get_collection(collection_name)
    document["updated_at"] = datetime.utcnow()
    col.update_one(filter_, {"$set": document}, upsert=True)


def upsert_many(collection_name: str, documents: list[dict], key_field: str) -> None:
    
    if not documents:
        return
    col = get_collection(collection_name)
    now = datetime.utcnow()
    ops = [
        UpdateOne(
            {key_field: doc[key_field]},
            {"$set": {**doc, "updated_at": now}},
            upsert=True,
        )
        for doc in documents
    ]
    col.bulk_write(ops, ordered=False)


def save_match_summary(data: dict) -> None:
    upsert_one("match_summaries", {"match_id": data["match_id"]}, data)


def save_match_info(data: dict) -> None:
    upsert_one("match_info", {"match_id": data["match_id"]}, data)


def save_squad(data: dict) -> None:
    upsert_one(
        "squads",
        {"match_id": data["match_id"], "team_name": data["team_name"]},
        data,
    )


def save_scorecard(data: dict) -> None:
    upsert_one("scorecards", {"match_id": data["match_id"]}, data)


def save_live_score(data: dict) -> None:
    
    col = get_collection("live_scores")
    data["created_at"] = datetime.utcnow()
    col.insert_one(data)


def get_pending_matches() -> list[dict]:
    
    col = get_collection("match_summaries")
    return list(col.find({"status": {"$in": ["upcoming", "live"]}}, {"_id": 0}))
