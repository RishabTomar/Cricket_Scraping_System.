

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field



class MatchSummary(BaseModel):

    match_id: str = Field(..., description="Unique match identifier from CREX URL slug")
    series_name: str = Field(default="", description="Tournament / series name")
    match_title: str = Field(default="", description="Short title, e.g. 'IND vs AUS, 1st Test'")
    team_a: str = Field(default="", description="Home / first-listed team")
    team_b: str = Field(default="", description="Away / second-listed team")
    match_type: str = Field(default="", description="Test | ODI | T20I | T20 | etc.")
    venue: str = Field(default="", description="Stadium and city")
    scheduled_time: Optional[datetime] = Field(None, description="Match start datetime (UTC)")
    status: str = Field(
        default="upcoming",
        description="upcoming | live | completed | abandoned",
    )
    match_url: str = Field(default="", description="Full URL to the match detail page")

    class Config:
        collection = "match_summaries"



class MatchInfo(BaseModel):
  
    match_id: str
    series_name: str = ""
    match_number: str = ""
    match_type: str = ""
    venue: str = ""
    city: str = ""
    country: str = ""
    scheduled_time: Optional[datetime] = None
    toss_winner: str = ""
    toss_decision: str = ""          # bat / bowl
    umpire_1: str = ""
    umpire_2: str = ""
    third_umpire: str = ""
    match_referee: str = ""
    home_team: str = ""
    away_team: str = ""
    result: str = ""
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        collection = "match_info"




class Player(BaseModel):
    name: str
    role: str = ""          # Batsman | Bowler | All-Rounder | Wicket-Keeper
    is_captain: bool = False
    is_keeper: bool = False


class Squad(BaseModel):
    """Squad data from the 'Squads' tab."""

    match_id: str
    team_name: str
    players: list[Player] = []
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        collection = "squads"


class BattingEntry(BaseModel):
    batsman: str
    dismissal: str = ""     # "c Smith b Jones", "not out", etc.
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    strike_rate: float = 0.0


class BowlingEntry(BaseModel):
    bowler: str
    overs: float = 0.0
    maidens: int = 0
    runs: int = 0
    wickets: int = 0
    economy: float = 0.0
    wides: int = 0
    no_balls: int = 0


class InningsScorecard(BaseModel):
    innings_number: int
    batting_team: str
    bowling_team: str
    total_runs: int = 0
    wickets: int = 0
    overs: float = 0.0
    extras: int = 0
    batting: list[BattingEntry] = []
    bowling: list[BowlingEntry] = []
    fall_of_wickets: list[str] = []   # e.g. ["1-24 (Smith, 5.3 ov)", ...]


class Scorecard(BaseModel):
   

    match_id: str
    innings: list[InningsScorecard] = []
    result: str = ""
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        collection = "scorecards"




class LiveBallEvent(BaseModel):
    over: str           # e.g. "12.3"
    batsman: str = ""
    bowler: str = ""
    runs: int = 0
    extras: int = 0
    wicket: bool = False
    commentary: str = ""


class LiveScore(BaseModel):
    
    match_id: str
    status: str = ""                  # "live" | "innings break" | etc.
    current_innings: int = 1
    batting_team: str = ""
    bowling_team: str = ""
    score: str = ""                   # e.g. "142/3"
    overs: str = ""                   # e.g. "18.4"
    run_rate: float = 0.0
    required_run_rate: Optional[float] = None
    target: Optional[int] = None
    last_wicket: str = ""
    recent_balls: list[str] = []      # e.g. ["1","0","W","4","6","1"]
    batsmen_on_crease: list[BattingEntry] = []
    current_bowler: Optional[BowlingEntry] = None
    ball_by_ball: list[LiveBallEvent] = []
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        collection = "live_scores"
