"""
wbc_backend/prediction/mlb_feature_context_keys.py

P11: Context key reconciliation for MLB independent feature builder.

The bullpen/rest/weather context JSONL files use a different game_id format than
the P9 prediction CSV:

  Context files:  MLB-2025_03_18-6_10_AM-LOS_ANGELES_DODGERS-AT-CHICAGO_CUBS
  P9 CSV:         2025-03-18_CHC_LAD  (DATE_HOME_AWAY, canonical canonical format)

This module bridges that gap by:
1. Parsing context file game_ids via parse_context_game_id()
2. Building canonical keys (YYYY-MM-DD_HOME_AWAY) from both formats
3. Trying multiple candidate key formats for robust lookup
4. Indexing context rows by all candidate keys

No fake matches. If no candidate key matches, returns None.
paper_only = True — no production side effects.
"""
from __future__ import annotations

import re
from typing import Any

from wbc_backend.prediction.mlb_game_key import (
    normalize_mlb_team,
    parse_context_game_id,
)

__all__ = [
    "normalize_context_team",
    "build_context_key_candidates",
    "index_context_rows",
    "lookup_context_for_game",
]

# ---------------------------------------------------------------------------
# § 1  Team normalisation (thin wrapper for consistent imports)
# ---------------------------------------------------------------------------

def normalize_context_team(value: str) -> str:
    """
    Normalise a team name or code to canonical MLB abbreviation.

    Delegates to normalize_mlb_team() which handles:
    - Full names: "Los Angeles Dodgers" → "LAD"
    - Underscored uppercase: "LOS_ANGELES_DODGERS" → "LAD"
    - Abbreviations: "LAD" → "LAD"

    Returns "UNK" for empty / unrecognised input.
    """
    return normalize_mlb_team(value)


# ---------------------------------------------------------------------------
# § 2  Candidate key builder
# ---------------------------------------------------------------------------

def build_context_key_candidates(
    date: str,
    home_team: str,
    away_team: str,
    game_id: str | None = None,
) -> list[str]:
    """
    Build a list of candidate lookup keys for a game, in priority order.

    The canonical format is ``YYYY-MM-DD_HOME_AWAY`` (abbreviations).
    Multiple variants are included to maximise hit rate across different
    context file key conventions.

    Parameters
    ----------
    date : str
        Game date in YYYY-MM-DD format (or partial / empty).
    home_team : str
        Home team name, abbreviation, or underscored uppercase.
    away_team : str
        Away team name, abbreviation, or underscored uppercase.
    game_id : str | None
        Raw game_id from the prediction CSV row (e.g. "2025-03-18_CHC_LAD").
        If provided, this is added as a priority candidate.

    Returns
    -------
    list[str]
        Candidate keys to try, in priority order (no duplicates).
    """
    home_abbr = normalize_context_team(home_team)
    away_abbr = normalize_context_team(away_team)
    d = _clean_date(date)

    seen: set[str] = set()
    candidates: list[str] = []

    def _add(k: str) -> None:
        if k and k not in seen:
            seen.add(k)
            candidates.append(k)

    # 1. Provided game_id (highest priority — already in canonical format)
    if game_id:
        _add(str(game_id).strip())

    # 2. Canonical: DATE_HOME_AWAY (abbreviations)
    if d and home_abbr != "UNK" and away_abbr != "UNK":
        _add(f"{d}_{home_abbr}_{away_abbr}")

    # 3. DATE_AWAY_HOME  variant
    if d and home_abbr != "UNK" and away_abbr != "UNK":
        _add(f"{d}_{away_abbr}_{home_abbr}")

    # 4. Lowercase canonical
    if d and home_abbr != "UNK" and away_abbr != "UNK":
        _add(f"{d}_{home_abbr}_{away_abbr}".lower())
        _add(f"{d}_{away_abbr}_{home_abbr}".lower())

    # 5. Hyphen separator variant
    if d and home_abbr != "UNK" and away_abbr != "UNK":
        _add(f"{d}-{home_abbr}-{away_abbr}")
        _add(f"{d}-{away_abbr}-{home_abbr}")

    # 6. date::home::away
    if d and home_abbr != "UNK" and away_abbr != "UNK":
        _add(f"{d}::{home_abbr}::{away_abbr}")
        _add(f"{d}::{away_abbr}::{home_abbr}")

    # 7. date|home|away
    if d and home_abbr != "UNK" and away_abbr != "UNK":
        _add(f"{d}|{home_abbr}|{away_abbr}")
        _add(f"{d}|{away_abbr}|{home_abbr}")

    return candidates


def _clean_date(date: str) -> str:
    """Normalise a date string to YYYY-MM-DD."""
    if not date:
        return ""
    raw = str(date).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    # M/D/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return raw[:10] if len(raw) >= 10 else raw


# ---------------------------------------------------------------------------
# § 3  Context row indexer
# ---------------------------------------------------------------------------

def index_context_rows(
    context_rows: list[dict],
    key_columns: list[str] | None = None,
) -> dict[str, dict]:
    """
    Build a lookup index from a list of context rows.

    For each row, generates all candidate keys (via parse_context_game_id for
    MLB-format keys and direct key columns) and stores the row under all of
    them. If multiple rows share a candidate key, the last one wins.

    Parameters
    ----------
    context_rows : list[dict]
        Raw context rows (from a JSONL / CSV / JSON context file).
    key_columns : list[str] | None
        Additional columns to use as direct lookup keys beyond ``game_id``.
        Defaults to ``["game_id"]``.

    Returns
    -------
    dict[str, dict]
        Index mapping every candidate key string → context row.
    """
    if key_columns is None:
        key_columns = ["game_id"]

    index: dict[str, dict] = {}

    for row in context_rows:
        # Collect raw key values from the nominated key columns
        raw_keys: list[str] = []
        for col in key_columns:
            v = row.get(col)
            if v:
                raw_keys.append(str(v).strip())

        # Also try the game_id if not already in key_columns
        gid_raw = str(row.get("game_id") or "").strip()
        if gid_raw and gid_raw not in raw_keys:
            raw_keys.append(gid_raw)

        for raw_key in raw_keys:
            # Always store the raw key directly
            if raw_key:
                index[raw_key] = row
                index[raw_key.lower()] = row

            # If this looks like an MLB context key, parse and index all candidates
            if raw_key.startswith("MLB-"):
                parsed = parse_context_game_id(raw_key)
                if parsed:
                    date_iso, home_code, away_code = parsed
                    # Canonical key (DATE_HOME_AWAY)
                    canon = f"{date_iso}_{home_code}_{away_code}"
                    index[canon] = row
                    index[canon.lower()] = row
                    # DATE_AWAY_HOME variant
                    swapped = f"{date_iso}_{away_code}_{home_code}"
                    index[swapped] = row
                    index[swapped.lower()] = row
                    # Hyphen variants
                    index[f"{date_iso}-{home_code}-{away_code}"] = row
                    index[f"{date_iso}-{away_code}-{home_code}"] = row

    return index


# ---------------------------------------------------------------------------
# § 4  Context lookup
# ---------------------------------------------------------------------------

def lookup_context_for_game(
    context_index: dict[str, dict],
    date: str,
    home_team: str,
    away_team: str,
    game_id: str | None = None,
) -> tuple[dict | None, dict]:
    """
    Look up a context row for a game, trying multiple key strategies.

    Parameters
    ----------
    context_index : dict[str, dict]
        Index built by ``index_context_rows()``.
    date : str
        Game date in YYYY-MM-DD or other parseable format.
    home_team : str
        Home team name, abbreviation, or underscored uppercase.
    away_team : str
        Away team name, abbreviation, or underscored uppercase.
    game_id : str | None
        Raw game_id from the prediction row (highest priority).

    Returns
    -------
    tuple[dict | None, dict]
        (matched_row_or_None, match_metadata)

        match_metadata keys:
        - ``matched``: bool — True if a row was found
        - ``match_key``: str | None — the key that matched
        - ``match_strategy``: str | None — human-readable strategy name
        - ``candidates_tried``: list[str] — all keys attempted
    """
    candidates = build_context_key_candidates(date, home_team, away_team, game_id)

    for key in candidates:
        row = context_index.get(key)
        if row is not None:
            return row, {
                "matched": True,
                "match_key": key,
                "match_strategy": _strategy_name(key, game_id),
                "candidates_tried": candidates,
            }

    return None, {
        "matched": False,
        "match_key": None,
        "match_strategy": None,
        "candidates_tried": candidates,
    }


def _strategy_name(matched_key: str, game_id: str | None) -> str:
    """Human-readable label for the matched key strategy."""
    if game_id and matched_key == game_id:
        return "game_id_direct"
    if re.match(r"^\d{4}-\d{2}-\d{2}_[A-Z]+_[A-Z]+$", matched_key):
        return "canonical_DATE_HOME_AWAY"
    if re.match(r"^\d{4}-\d{2}-\d{2}_[a-z]+_[a-z]+$", matched_key):
        return "canonical_DATE_HOME_AWAY_lower"
    if re.match(r"^\d{4}-\d{2}-\d{2}-[A-Z]+-[A-Z]+$", matched_key):
        return "hyphen_DATE_HOME_AWAY"
    if matched_key.startswith("MLB-"):
        return "raw_context_key"
    return "other"
