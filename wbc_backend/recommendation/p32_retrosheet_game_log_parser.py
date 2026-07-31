"""
P32 Retrosheet Game Log Parser.

Parses Retrosheet fixed-position game log files (GL2024.TXT or gl2024.txt).
Produces canonical game identity and outcome records.

Reference: https://www.retrosheet.org/gamelogs/index.html
Field positions (1-indexed columns in the fixed-format CSV):

The Retrosheet game log is a CSV (no header) with 161 fields.
Key fields (0-indexed in Python):
  0  = date          (YYYYMMDD)
  1  = game_number   (0=single, 1=first game of DH, 2=second game of DH)
  2  = day_of_week
  3  = visiting_team (3-letter Retrosheet team ID)
  4  = visiting_league
  5  = visiting_game_number_in_season
  6  = home_team     (3-letter Retrosheet team ID)
  7  = home_league
  8  = home_game_number_in_season
  9  = visiting_score
  10 = home_score

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from wbc_backend.recommendation.p32_raw_game_log_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    P32_BLOCKED_SCHEMA_INVALID,
    P32_BLOCKED_NO_2024_GAMES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retrosheet positional column mapping (0-indexed)
# ---------------------------------------------------------------------------

# Total fields in a complete Retrosheet game log row
RETROSHEET_MIN_FIELD_COUNT = 11  # We need at least fields 0-10

# Column-index mapping for the fields we need
_COL_DATE = 0
_COL_GAME_NUMBER = 1
_COL_VISITING_TEAM = 3
_COL_HOME_TEAM = 6
_COL_VISITING_SCORE = 9
_COL_HOME_SCORE = 10

# Required output columns for P32 (no odds, no predictions)
REQUIRED_OUTPUT_COLUMNS: list[str] = [
    "game_id",
    "game_date",
    "away_team",
    "home_team",
    "away_score",
    "home_score",
    "y_true_home_win",
    "season",
    "source_name",
    "source_row_number",
]

SOURCE_NAME = "Retrosheet"


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def validate_retrosheet_schema(raw_df: pd.DataFrame) -> tuple[bool, str]:
    """
    Validate that the raw DataFrame has enough columns for our field positions.

    Returns:
        (is_valid, reason_if_invalid)
    """
    if raw_df is None or raw_df.empty:
        return False, "Empty DataFrame — no rows to validate."
    if raw_df.shape[1] < RETROSHEET_MIN_FIELD_COUNT:
        return (
            False,
            f"Schema invalid: expected at least {RETROSHEET_MIN_FIELD_COUNT} columns, "
            f"got {raw_df.shape[1]}.",
        )
    # Check date column is parseable
    sample = raw_df.iloc[0, _COL_DATE]
    if not _is_valid_retrosheet_date(str(sample)):
        return (
            False,
            f"Schema invalid: column 0 (date) value {sample!r} is not a valid "
            f"YYYYMMDD date.",
        )
    return True, ""


def load_retrosheet_game_log(path: str | Path) -> pd.DataFrame:
    """
    Load a Retrosheet game log file as a raw DataFrame (no header).

    Returns a DataFrame with integer column indices.
    Raises FileNotFoundError if path does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Retrosheet source file not found: {p}")
    raw = pd.read_csv(
        p,
        header=None,
        dtype=str,
        encoding="latin-1",
        on_bad_lines="skip",
    )
    logger.info("Loaded %d raw rows from %s", len(raw), p)
    return raw


def parse_retrosheet_game_log_rows(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse raw Retrosheet rows into the canonical P32 schema.

    Returns a DataFrame with REQUIRED_OUTPUT_COLUMNS.
    Does NOT fabricate missing scores or outcomes.
    """
    is_valid, reason = validate_retrosheet_schema(raw_df)
    if not is_valid:
        raise ValueError(f"{P32_BLOCKED_SCHEMA_INVALID}: {reason}")

    rows = []
    for idx, row in raw_df.iterrows():
        source_row_number = int(idx) + 1  # 1-based
        game_date = normalize_game_date(row)
        if not game_date:
            logger.debug("Row %d: unparseable date, skipping.", source_row_number)
            continue

        away_team = normalize_team_fields(row, team_col=_COL_VISITING_TEAM)
        home_team = normalize_team_fields(row, team_col=_COL_HOME_TEAM)
        game_number = str(row.iloc[_COL_GAME_NUMBER]).strip()
        game_id = build_game_id(game_date, home_team, game_number)

        away_score, home_score = derive_home_away_scores(row)
        y_true = derive_y_true_home_win(away_score, home_score)

        rows.append(
            {
                "game_id": game_id,
                "game_date": game_date,
                "away_team": away_team,
                "home_team": home_team,
                "away_score": away_score,
                "home_score": home_score,
                "y_true_home_win": y_true,
                "season": _infer_season(game_date),
                "source_name": SOURCE_NAME,
                "source_row_number": source_row_number,
            }
        )

    if not rows:
        raise ValueError(f"{P32_BLOCKED_NO_2024_GAMES}: No parseable rows found.")

    result = pd.DataFrame(rows, columns=REQUIRED_OUTPUT_COLUMNS)
    # Ensure correct dtypes
    result["away_score"] = pd.to_numeric(result["away_score"], errors="coerce").astype("Int64")
    result["home_score"] = pd.to_numeric(result["home_score"], errors="coerce").astype("Int64")
    result["y_true_home_win"] = pd.to_numeric(
        result["y_true_home_win"], errors="coerce"
    ).astype("Int64")
    result["source_row_number"] = result["source_row_number"].astype(int)
    result["season"] = result["season"].astype(int)

    logger.info("Parsed %d rows into canonical P32 schema.", len(result))
    return result


# ---------------------------------------------------------------------------
# Field derivation helpers
# ---------------------------------------------------------------------------


def build_game_id(game_date: str, home_team: str, game_number: str) -> str:
    """
    Construct a stable, deterministic game_id from date + home team + game_number.
    Format: <HOME>-<YYYYMMDD>-<G> where G=0,1,2 for single/DH.
    """
    safe_date = game_date.replace("-", "")
    gn = game_number.strip() if game_number.strip() in ("0", "1", "2") else "0"
    return f"{home_team.upper()}-{safe_date}-{gn}"


def normalize_game_date(row: pd.Series) -> str:
    """
    Extract and normalize the game date from column 0.
    Retrosheet format: YYYYMMDD → ISO YYYY-MM-DD.
    Returns "" if date cannot be parsed.
    """
    raw_date = str(row.iloc[_COL_DATE]).strip()
    return _parse_retrosheet_date(raw_date)


def normalize_team_fields(row: pd.Series, team_col: int) -> str:
    """
    Extract and normalize a team ID from the given column index.
    Returns an uppercase 3-letter team code, or "UNK" if missing.
    """
    raw = str(row.iloc[team_col]).strip().upper()
    if not raw or raw in ("NAN", "NONE", ""):
        return "UNK"
    return raw[:3]  # Retrosheet uses 3-letter codes


def derive_home_away_scores(row: pd.Series) -> tuple[Optional[int], Optional[int]]:
    """
    Extract visiting (away) and home scores from columns 9 and 10.
    Returns (None, None) if scores are missing or non-numeric.
    """
    away = _safe_int(row.iloc[_COL_VISITING_SCORE])
    home = _safe_int(row.iloc[_COL_HOME_SCORE])
    return away, home


def derive_y_true_home_win(
    away_score: Optional[int], home_score: Optional[int]
) -> Optional[int]:
    """
    Derive binary home-win label (1=home win, 0=away win).
    Returns None if scores are missing or tied (unexpected in MLB regular season).
    Does NOT fabricate the outcome.
    """
    if away_score is None or home_score is None:
        return None
    if home_score > away_score:
        return 1
    if away_score > home_score:
        return 0
    # Tied — should not occur in MLB regular season
    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_retrosheet_date(raw: str) -> str:
    """Parse YYYYMMDD → YYYY-MM-DD. Returns "" on failure."""
    raw = raw.strip()
    if len(raw) != 8 or not raw.isdigit():
        return ""
    try:
        year = int(raw[:4])
        month = int(raw[4:6])
        day = int(raw[6:8])
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return ""
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return ""


def _is_valid_retrosheet_date(raw: str) -> bool:
    return bool(_parse_retrosheet_date(raw))


def _safe_int(val) -> Optional[int]:
    """Convert value to int, returning None if not possible."""
    try:
        v = str(val).strip()
        if not v or v.lower() in ("nan", "none", ""):
            return None
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _infer_season(game_date: str) -> int:
    """Infer season year from ISO date string."""
    try:
        return int(game_date[:4])
    except (ValueError, IndexError):
        return 0


def filter_to_season(df: pd.DataFrame, season: int) -> pd.DataFrame:
    """
    Filter parsed DataFrame to rows matching the specified season.
    Used to ensure we only process 2024 data in P32.
    """
    return df[df["season"] == season].reset_index(drop=True)


def compute_outcome_coverage(df: pd.DataFrame) -> float:
    """Fraction of rows with a non-null y_true_home_win outcome."""
    if len(df) == 0:
        return 0.0
    non_null = df["y_true_home_win"].notna().sum()
    return float(non_null) / len(df)
