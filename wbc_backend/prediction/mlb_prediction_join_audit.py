"""
wbc_backend/prediction/mlb_prediction_join_audit.py

P8: Join integrity audit for MLB prediction rows.

Implements:
  audit_prediction_join_integrity()  — inspect game_id / date / team keys
  normalize_mlb_team_name()          — stable team name normalization

Design rules:
  - No external API calls.
  - No modification to input rows.
  - Paper-only; never writes to production.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

__all__ = [
    "audit_prediction_join_integrity",
    "normalize_mlb_team_name",
]


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Team name normalization
# ─────────────────────────────────────────────────────────────────────────────

# Canonical full-name → 3-letter abbreviation
_FULL_NAME_TO_CODE: dict[str, str] = {
    "arizona diamondbacks": "ARI",
    "diamondbacks": "ARI",
    "athletics": "ATH",
    "oakland athletics": "ATH",
    "sacramento athletics": "ATH",
    "atlanta braves": "ATL",
    "braves": "ATL",
    "baltimore orioles": "BAL",
    "orioles": "BAL",
    "boston red sox": "BOS",
    "red sox": "BOS",
    "chicago cubs": "CHC",
    "cubs": "CHC",
    "chicago white sox": "CWS",
    "white sox": "CWS",
    "cincinnati reds": "CIN",
    "reds": "CIN",
    "cleveland guardians": "CLE",
    "guardians": "CLE",
    "colorado rockies": "COL",
    "rockies": "COL",
    "detroit tigers": "DET",
    "tigers": "DET",
    "houston astros": "HOU",
    "astros": "HOU",
    "kansas city royals": "KC",
    "royals": "KC",
    "los angeles angels": "LAA",
    "angels": "LAA",
    "l.a. angels": "LAA",
    "los angeles dodgers": "LAD",
    "dodgers": "LAD",
    "l.a. dodgers": "LAD",
    "miami marlins": "MIA",
    "marlins": "MIA",
    "milwaukee brewers": "MIL",
    "brewers": "MIL",
    "minnesota twins": "MIN",
    "twins": "MIN",
    "new york mets": "NYM",
    "mets": "NYM",
    "new york yankees": "NYY",
    "yankees": "NYY",
    "ny yankees": "NYY",
    "ny mets": "NYM",
    "philadelphia phillies": "PHI",
    "phillies": "PHI",
    "pittsburgh pirates": "PIT",
    "pirates": "PIT",
    "san diego padres": "SD",
    "padres": "SD",
    "san francisco giants": "SF",
    "giants": "SF",
    "seattle mariners": "SEA",
    "mariners": "SEA",
    "st. louis cardinals": "STL",
    "st louis cardinals": "STL",
    "cardinals": "STL",
    "tampa bay rays": "TB",
    "rays": "TB",
    "texas rangers": "TEX",
    "rangers": "TEX",
    "toronto blue jays": "TOR",
    "blue jays": "TOR",
    "washington nationals": "WSH",
    "nationals": "WSH",
}

# Known 2-letter/special codes that map directly
_CODE_DIRECT: dict[str, str] = {
    "ARI": "ARI", "ATH": "ATH", "ATL": "ATL", "BAL": "BAL",
    "BOS": "BOS", "CHC": "CHC", "CWS": "CWS", "CIN": "CIN",
    "CLE": "CLE", "COL": "COL", "DET": "DET", "HOU": "HOU",
    "KC": "KC",   "LAA": "LAA", "LAD": "LAD", "MIA": "MIA",
    "MIL": "MIL", "MIN": "MIN", "NYM": "NYM", "NYY": "NYY",
    "PHI": "PHI", "PIT": "PIT", "SD":  "SD",  "SF":  "SF",
    "SEA": "SEA", "STL": "STL", "TB":  "TB",  "TEX": "TEX",
    "TOR": "TOR", "WSH": "WSH",
    # Common alternative codes
    "OAK": "ATH", "NYM2": "NYM",
}


def normalize_mlb_team_name(value: str) -> str:
    """
    Normalize an MLB team name to a canonical abbreviation.

    Parameters
    ----------
    value:
        Any form of team name: full name, nickname, abbreviation, or empty string.

    Returns
    -------
    Canonical 3-letter (or 2-letter for KC/SD/SF/TB) abbreviation when
    recognized, or an uppercased token otherwise.
    Empty string returns empty string.

    Examples
    --------
    >>> normalize_mlb_team_name("Los Angeles Dodgers")
    'LAD'
    >>> normalize_mlb_team_name("dodgers")
    'LAD'
    >>> normalize_mlb_team_name("LAD")
    'LAD'
    >>> normalize_mlb_team_name("")
    ''
    >>> normalize_mlb_team_name("UnknownTeam")
    'UNKNOWNTEAM'
    """
    if not value or not str(value).strip():
        return ""

    token = str(value).strip()

    # Direct code hit (case-insensitive)
    upper = token.upper()
    if upper in _CODE_DIRECT:
        return _CODE_DIRECT[upper]

    # Full-name lookup (case-insensitive)
    lower = token.lower()
    if lower in _FULL_NAME_TO_CODE:
        return _FULL_NAME_TO_CODE[lower]

    # Partial suffix match: "Cleveland Guardians" → try last word
    words = re.split(r"\s+", lower)
    if words:
        for w in reversed(words):
            if w in _FULL_NAME_TO_CODE:
                return _FULL_NAME_TO_CODE[w]

    # Unknown: return normalized uppercase token
    return upper


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Join integrity audit
# ─────────────────────────────────────────────────────────────────────────────

def audit_prediction_join_integrity(
    rows: list[dict],
    *,
    date_col: str = "date",
    home_team_col: str = "home_team",
    away_team_col: str = "away_team",
    game_id_col: str = "game_id",
) -> dict:
    """
    Audit the join integrity of prediction rows.

    Checks for:
    - Missing game_id values
    - Duplicate game_id values
    - Missing / duplicate date+team keys
    - Missing home / away team names
    - Same home and away team (data error)
    - Normalization examples for inspection

    Parameters
    ----------
    rows:
        List of row dicts from the prediction CSV.
    date_col, home_team_col, away_team_col, game_id_col:
        Column names — falls back to common alternatives (Home, Away, Date).

    Returns
    -------
    dict with keys: row_count, unique_game_id_count, duplicate_game_id_count,
        unique_date_team_key_count, duplicate_date_team_key_count,
        missing_game_id_count, missing_date_count, missing_home_team_count,
        missing_away_team_count, same_home_away_count, normalization_examples,
        risk_level, risk_reasons.
    """
    row_count = len(rows)

    game_ids: list[str] = []
    date_team_keys: list[str] = []
    missing_game_id = 0
    missing_date = 0
    missing_home = 0
    missing_away = 0
    same_team_count = 0
    normalization_examples: list[dict] = []

    for row in rows:
        # ── game_id ──────────────────────────────────────────────────────────
        gid = (
            row.get(game_id_col)
            or row.get("game_id")
            or row.get("Game ID")
            or ""
        )
        gid = str(gid).strip()
        if gid:
            game_ids.append(gid)
        else:
            missing_game_id += 1

        # ── date ─────────────────────────────────────────────────────────────
        date_val = (
            row.get(date_col)
            or row.get("Date")
            or row.get("date")
            or ""
        )
        date_val = str(date_val).strip()
        if not date_val:
            missing_date += 1

        # ── home / away teams ─────────────────────────────────────────────────
        home_raw = (
            row.get(home_team_col)
            or row.get("Home")
            or row.get("home_team")
            or ""
        )
        away_raw = (
            row.get(away_team_col)
            or row.get("Away")
            or row.get("away_team")
            or ""
        )
        home_raw = str(home_raw).strip()
        away_raw = str(away_raw).strip()

        if not home_raw:
            missing_home += 1
        if not away_raw:
            missing_away += 1

        # Normalize and check same-team
        home_norm = normalize_mlb_team_name(home_raw) if home_raw else ""
        away_norm = normalize_mlb_team_name(away_raw) if away_raw else ""

        if home_norm and away_norm and home_norm == away_norm:
            same_team_count += 1

        # Build date+team key using normalized codes
        if date_val and home_norm and away_norm:
            date_team_keys.append(f"{date_val}|{home_norm}|{away_norm}")

        # Collect normalization examples (up to 5)
        if len(normalization_examples) < 5 and home_raw and away_raw:
            normalization_examples.append({
                "home_raw": home_raw,
                "away_raw": away_raw,
                "home_norm": home_norm,
                "away_norm": away_norm,
                "date": date_val,
            })

    # ── Deduplication counts ─────────────────────────────────────────────────
    gid_counter = Counter(game_ids)
    dupe_game_id = sum(1 for c in gid_counter.values() if c > 1)

    dtk_counter = Counter(date_team_keys)
    dupe_date_team = sum(1 for c in dtk_counter.values() if c > 1)

    unique_game_ids = len(gid_counter)
    unique_date_team_keys = len(dtk_counter)

    # ── Risk assessment ──────────────────────────────────────────────────────
    risk_reasons: list[str] = []

    if same_team_count > 0:
        risk_reasons.append(f"same_home_away_team in {same_team_count} rows")
    if dupe_date_team > 0:
        risk_reasons.append(f"duplicate date+team key in {dupe_date_team} groups")
    if dupe_game_id > 0:
        risk_reasons.append(f"duplicate game_id in {dupe_game_id} groups")
    if missing_home > row_count * 0.05:
        risk_reasons.append(f"missing home team in {missing_home}/{row_count} rows")
    if missing_away > row_count * 0.05:
        risk_reasons.append(f"missing away team in {missing_away}/{row_count} rows")

    if same_team_count > 0 or dupe_date_team > 0:
        risk_level = "HIGH"
    elif dupe_game_id > 0 or missing_home > 0 or missing_away > 0:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "row_count": row_count,
        "unique_game_id_count": unique_game_ids,
        "duplicate_game_id_count": dupe_game_id,
        "unique_date_team_key_count": unique_date_team_keys,
        "duplicate_date_team_key_count": dupe_date_team,
        "missing_game_id_count": missing_game_id,
        "missing_date_count": missing_date,
        "missing_home_team_count": missing_home,
        "missing_away_team_count": missing_away,
        "same_home_away_count": same_team_count,
        "normalization_examples": normalization_examples,
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
    }
