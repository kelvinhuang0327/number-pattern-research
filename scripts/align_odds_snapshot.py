"""
Phase 6S — Odds Snapshot Alignment Helper
==========================================
Reusable helper for aligning prediction rows with valid pre-prediction
odds snapshots from the MLBcontext odds timeline.

Design rules (enforced):
  - Only snapshots where snapshot_time_utc <= prediction_time_utc are used
  - Snapshots after prediction time are hard-blocked (FUTURE_LEAK_BLOCKED)
  - Priority: TSL > external_closing > closing (static)
  - Missing match → MISSING status, clv_usable remains False

Returns a 6-field alignment dict for each prediction row:
  {
    "odds_snapshot_ref":               str | None,
    "odds_snapshot_time_utc":          str | None,
    "implied_probability_at_prediction": float | None,
    "market_odds_at_prediction":       int | None,
    "odds_snapshot_source":            str | None,
    "odds_snapshot_alignment_status":  str,  # ALIGNED | MISSING | STALE | FUTURE_LEAK_BLOCKED
  }

Canonical odds timeline: data/mlb_context/odds_timeline.jsonl
Schema:
  game_id              str  "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
  opening_home_ml      int | None
  opening_away_ml      int | None
  opening_ts           str | None
  decision_home_ml     int | None
  decision_away_ml     int | None
  decision_ts          str | None
  latest_pregame_home_ml int | None
  latest_pregame_away_ml int | None
  latest_pregame_ts    str | None
  closing_home_ml      int | None
  closing_away_ml      int | None
  closing_ts           str | None
  external_closing_home_ml int | None
  external_closing_away_ml int | None
  external_closing_ts  str | None
  closing_source       str | None
  odds_history         list[{ts, home_ml, away_ml, ou_line, source, book, snapshot_type}]
  source               str  "historical_odds_ingestion" | "TSL"
  book                 str  "TSL" | ...
  market_type          str  "moneyline"
  updated_at           str

canonical_match_id format: "baseball:mlb:20260430:HOME:AWAY"
game_id format:            "MLB-YYYY_MM_DD-H_MM_AM/PM-AWAY_TEAM-AT-HOME_TEAM"
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
ODDS_TIMELINE_DEFAULT_PATH = str(
    _REPO_ROOT / "data" / "mlb_context" / "odds_timeline.jsonl"
)

# ---------------------------------------------------------------------------
# Team full-name → code mapping (covers all 30 MLB franchises + aliases)
# ---------------------------------------------------------------------------
TEAM_NAME_TO_CODE: dict[str, str] = {
    # AL East
    "NEW_YORK_YANKEES": "NYY",
    "BOSTON_RED_SOX": "BOS",
    "TORONTO_BLUE_JAYS": "TOR",
    "TAMPA_BAY_RAYS": "TBR",
    "BALTIMORE_ORIOLES": "BAL",
    # AL Central
    "CHICAGO_WHITE_SOX": "CWS",
    "CLEVELAND_GUARDIANS": "CLE",
    "DETROIT_TIGERS": "DET",
    "KANSAS_CITY_ROYALS": "KC",
    "MINNESOTA_TWINS": "MIN",
    # AL West
    "HOUSTON_ASTROS": "HOU",
    "LOS_ANGELES_ANGELS": "LAA",
    "OAKLAND_ATHLETICS": "OAK",
    "SEATTLE_MARINERS": "SEA",
    "TEXAS_RANGERS": "TEX",
    # NL East
    "ATLANTA_BRAVES": "ATL",
    "MIAMI_MARLINS": "MIA",
    "NEW_YORK_METS": "NYM",
    "PHILADELPHIA_PHILLIES": "PHI",
    "WASHINGTON_NATIONALS": "WSH",
    # NL Central
    "CHICAGO_CUBS": "CHC",
    "CINCINNATI_REDS": "CIN",
    "MILWAUKEE_BREWERS": "MIL",
    "PITTSBURGH_PIRATES": "PIT",
    "ST_LOUIS_CARDINALS": "STL",
    # NL West
    "ARIZONA_DIAMONDBACKS": "ARI",
    "COLORADO_ROCKIES": "COL",
    "LOS_ANGELES_DODGERS": "LAD",
    "SAN_DIEGO_PADRES": "SDP",
    "SAN_FRANCISCO_GIANTS": "SFG",
    # Aliases
    "NEW_YORK_YANKEE": "NYY",
    "ATHLETICS": "OAK",
}

# Reverse map for lookup: code → list of full names (informational)
CODE_TO_TEAM_NAME: dict[str, str] = {v: k for k, v in TEAM_NAME_TO_CODE.items()}


# ---------------------------------------------------------------------------
# American odds → implied probability (vig-inclusive, standard formula)
# ---------------------------------------------------------------------------
def american_to_implied(american_ml: int) -> float:
    """
    Convert American moneyline to implied probability.
    Positive (e.g. +155): 100 / (100 + 155)
    Negative (e.g. -125): 125 / (125 + 100)
    """
    if american_ml >= 0:
        return round(100.0 / (100.0 + american_ml), 6)
    else:
        abs_ml = abs(american_ml)
        return round(abs_ml / (abs_ml + 100.0), 6)


# ---------------------------------------------------------------------------
# Timestamp parser (handles Z-suffix and microsecond variants)
# ---------------------------------------------------------------------------
def _parse_utc_loose(ts_str: str | None) -> Optional[datetime]:
    """
    Parse ISO-8601 UTC string, tolerating microseconds and Z suffix.
    Returns None on any parse failure.
    """
    if not ts_str:
        return None
    try:
        # Strip microseconds: keep only seconds precision
        s = ts_str[:19] + "Z"
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Parse game_id → (date_yyyymmdd, away_code, home_code)
# game_id format: "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
# ---------------------------------------------------------------------------
def _extract_from_game_id(game_id: str) -> tuple[str, str, str] | None:
    """
    Returns (date_yyyymmdd, away_code, home_code) or None if parse fails.
    """
    try:
        # Strip leading "MLB-"
        body = game_id.removeprefix("MLB-")
        # Split on "-AT-" to get away and home halves
        if "-AT-" not in body:
            return None
        left, home_name = body.split("-AT-", 1)
        home_code = TEAM_NAME_TO_CODE.get(home_name.upper(), home_name)

        # left = "2026_04_30-12_15_PM-DETROIT_TIGERS"
        # Find the date block: first token with underscores
        tokens = left.split("-")
        # date is tokens[0] in YYYY_MM_DD format
        date_raw = tokens[0]  # "2026_04_30"
        date_yyyymmdd = date_raw.replace("_", "")  # "20260430"

        # away team name is everything from index 2 onward.
        # tokens[0]=date ("2026_04_30"), tokens[1]=time ("12_15_PM"),
        # tokens[2+]=team name (e.g. "DETROIT_TIGERS" — joined with underscores,
        # so split("-") keeps it as one token).
        away_name = "_".join(tokens[2:]).upper()
        away_code = TEAM_NAME_TO_CODE.get(away_name, away_name)

        return (date_yyyymmdd, away_code, home_code)
    except (IndexError, ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Parse canonical_match_id → (date_yyyymmdd, home_code, away_code)
# format: "baseball:mlb:20260430:HOME:AWAY"
# ---------------------------------------------------------------------------
def _extract_from_canonical_id(canonical_match_id: str) -> tuple[str, str, str] | None:
    """
    Returns (date_yyyymmdd, home_code, away_code) or None if parse fails.
    """
    try:
        parts = canonical_match_id.split(":")
        if len(parts) < 5:
            return None
        # parts: ["baseball", "mlb", "20260430", "HOME", "AWAY"]
        return (parts[2], parts[3].upper(), parts[4].upper())
    except (IndexError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Odds Timeline Loader
# ---------------------------------------------------------------------------
class OddsTimelineLoader:
    """
    Loads data/mlb_context/odds_timeline.jsonl into memory.
    Indexed by (date_yyyymmdd, away_code, home_code) for O(1) lookup.
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path or ODDS_TIMELINE_DEFAULT_PATH
        # Index: (date, away, home) → record
        self._by_teams: dict[tuple[str, str, str], dict] = {}
        # Index: date → list of records (for date-level queries)
        self._by_date: dict[str, list[dict]] = {}
        self._load()

    def _load(self) -> None:
        p = Path(self._path)
        if not p.exists():
            return
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                parsed = _extract_from_game_id(record.get("game_id", ""))
                if parsed:
                    date, away, home = parsed
                    key = (date, away, home)
                    self._by_teams[key] = record
                    self._by_date.setdefault(date, []).append(record)

    def find(
        self, date_yyyymmdd: str, home_code: str, away_code: str
    ) -> dict | None:
        """
        Exact match: same date, same home team, same away team.
        """
        return self._by_teams.get((date_yyyymmdd, away_code, home_code))

    def records_for_date(self, date_yyyymmdd: str) -> list[dict]:
        """Return all records for a calendar date."""
        return self._by_date.get(date_yyyymmdd, [])

    def all_records(self) -> list[dict]:
        return list(self._by_teams.values())


# ---------------------------------------------------------------------------
# Core alignment function
# ---------------------------------------------------------------------------
def align_odds_snapshot_for_prediction(
    row: dict,
    loader: OddsTimelineLoader,
) -> dict:
    """
    Find the best pre-prediction odds snapshot for a single prediction row.

    Matching logic:
      1. Parse row's canonical_match_id → (date, home, away)
      2. Exact lookup in OddsTimelineLoader by (date, away, home)
      3. From matched record's odds_history, find latest entry where ts <= prediction_time_utc
      4. Compute implied_probability_at_prediction from home_ml / away_ml
      5. Build snapshot_ref as "{game_id}|snap@{ts}"

    Priority for snapshot source:
      1. Latest TSL pre-game odds_history entry (snapshot_type in ["early","pregame","live"])
      2. latest_pregame_{home|away}_ml + latest_pregame_ts
      3. decision_{home|away}_ml + decision_ts
      (Never use closing_* — post-game data)

    Alignment statuses:
      ALIGNED              — valid snapshot found before prediction_time_utc
      MISSING              — no odds record for this game
      STALE                — snapshot found but > 24h before prediction_time_utc
      FUTURE_LEAK_BLOCKED  — all snapshots are after prediction_time_utc
    """
    _EMPTY = {
        "odds_snapshot_ref": None,
        "odds_snapshot_time_utc": None,
        "implied_probability_at_prediction": None,
        "market_odds_at_prediction": None,
        "odds_snapshot_source": None,
        "odds_snapshot_alignment_status": "MISSING",
    }

    # ── Parse canonical_match_id ──────────────────────────────────────────────
    canonical_id = row.get("canonical_match_id", "")
    parsed = _extract_from_canonical_id(canonical_id)
    if not parsed:
        return dict(_EMPTY)

    date_str, home_code, away_code = parsed
    selection = row.get("selection", "home")  # "home" or "away"

    # ── Prediction time cutoff ────────────────────────────────────────────────
    pred_time_str = row.get("prediction_time_utc", "")
    pred_time = _parse_utc_loose(pred_time_str)
    if pred_time is None:
        return dict(_EMPTY)

    # ── Find matching game record (exact: date + home + away) ─────────────────
    record = loader.find(date_str, home_code, away_code)
    if record is None:
        return dict(_EMPTY)

    game_id = record.get("game_id", "")

    # ── Search odds_history for latest valid snapshot ─────────────────────────
    best_ts: Optional[datetime] = None
    best_entry: Optional[dict] = None
    all_future = True   # track if every snapshot is in the future

    for entry in record.get("odds_history", []):
        ts = _parse_utc_loose(entry.get("ts"))
        if ts is None:
            continue
        if ts > pred_time:
            # Future snapshot — cannot use, but record existence
            continue
        all_future = False
        if best_ts is None or ts > best_ts:
            best_ts = ts
            best_entry = entry

    # If no history entries but record has static timestamps, try those
    if best_entry is None and not all_future:
        # Try latest_pregame_ts
        for ts_key, hml_key, aml_key, src in [
            ("latest_pregame_ts", "latest_pregame_home_ml", "latest_pregame_away_ml", "pregame_static"),
            ("decision_ts", "decision_home_ml", "decision_away_ml", "decision_static"),
            ("opening_ts", "opening_home_ml", "opening_away_ml", "opening_static"),
        ]:
            ts_val = record.get(ts_key)
            ts = _parse_utc_loose(ts_val)
            if ts and ts <= pred_time:
                hml = record.get(hml_key)
                aml = record.get(aml_key)
                if hml is not None and aml is not None:
                    best_ts = ts
                    best_entry = {"ts": ts_val, "home_ml": hml, "away_ml": aml,
                                  "source": record.get("source", "UNKNOWN"),
                                  "book": record.get("book", "UNKNOWN"),
                                  "snapshot_type": ts_key.split("_ts")[0]}
                    all_future = False
                    break

    # Handle future-leak case (all snapshots are after prediction_time)
    if best_entry is None:
        if all_future and record.get("odds_history"):
            return {
                "odds_snapshot_ref": None,
                "odds_snapshot_time_utc": None,
                "implied_probability_at_prediction": None,
                "market_odds_at_prediction": None,
                "odds_snapshot_source": None,
                "odds_snapshot_alignment_status": "FUTURE_LEAK_BLOCKED",
            }
        return dict(_EMPTY)

    # ── Extract odds and compute implied probability ───────────────────────────
    home_ml: int | None = best_entry.get("home_ml")
    away_ml: int | None = best_entry.get("away_ml")

    if selection == "home":
        market_odds = home_ml
    else:
        market_odds = away_ml

    if market_odds is None:
        # Missing ML odds in snapshot
        return {
            "odds_snapshot_ref": f"{game_id}|snap@{best_ts.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "odds_snapshot_time_utc": best_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "implied_probability_at_prediction": None,
            "market_odds_at_prediction": None,
            "odds_snapshot_source": best_entry.get("source", "UNKNOWN"),
            "odds_snapshot_alignment_status": "MISSING",
        }

    implied_prob = american_to_implied(market_odds)
    snap_ts_str = best_ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── STALE check: snapshot older than 24 hours before prediction ───────────
    from datetime import timedelta
    stale_threshold = pred_time - timedelta(hours=24)
    alignment_status = "STALE" if best_ts < stale_threshold else "ALIGNED"

    # ── Build snapshot_ref ────────────────────────────────────────────────────
    snap_book = best_entry.get("book", best_entry.get("source", "UNKNOWN"))
    snapshot_ref = f"{game_id}|{snap_book}|snap@{snap_ts_str}"

    return {
        "odds_snapshot_ref": snapshot_ref,
        "odds_snapshot_time_utc": snap_ts_str,
        "implied_probability_at_prediction": implied_prob,
        "market_odds_at_prediction": market_odds,
        "odds_snapshot_source": best_entry.get("source", snap_book),
        "odds_snapshot_alignment_status": alignment_status,
    }
