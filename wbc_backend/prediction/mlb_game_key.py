"""
wbc_backend/prediction/mlb_game_key.py

P9: Stable game_id utility and row deduplication for MLB prediction rows.

Key exports:
    normalize_mlb_team(value: str) -> str
    build_mlb_game_id(date: str, home_team: str, away_team: str) -> str
    build_mlb_date_team_key(date: str, home_team: str, away_team: str) -> str
    dedupe_mlb_rows(rows: list[dict]) -> tuple[list[dict], dict]
    parse_context_game_id(context_game_id: str) -> tuple[str, str, str] | None

Design notes:
  - No external API calls.
  - Builds on normalize_mlb_team_name() from mlb_prediction_join_audit.py
    for consistent behavior; adds underscored-uppercase passthrough.
  - paper_only = True always.
"""
from __future__ import annotations

import re
from typing import Any

from wbc_backend.prediction.mlb_prediction_join_audit import normalize_mlb_team_name

__all__ = [
    "normalize_mlb_team",
    "build_mlb_game_id",
    "build_mlb_date_team_key",
    "dedupe_mlb_rows",
    "parse_context_game_id",
]


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Team normalization (wraps P8 function + underscored-uppercase support)
# ─────────────────────────────────────────────────────────────────────────────

def normalize_mlb_team(value: str) -> str:
    """
    Normalize an MLB team name to a canonical abbreviation.

    Extends normalize_mlb_team_name() with:
    - Underscored uppercase passthrough (from context file game_id segments):
        "LOS_ANGELES_DODGERS" → "LAD"
    - Empty strings or None → "UNK"

    Parameters
    ----------
    value : str
        Any form of team name: full name, nickname, abbreviation,
        or underscored uppercase (as found in context file game_ids).

    Returns
    -------
    str
        Canonical abbreviation (e.g. "LAD", "NYY", "STL"),
        or "UNK" when the input is empty/None.

    Examples
    --------
    >>> normalize_mlb_team("Los Angeles Dodgers")
    'LAD'
    >>> normalize_mlb_team("LOS_ANGELES_DODGERS")
    'LAD'
    >>> normalize_mlb_team("LAD")
    'LAD'
    >>> normalize_mlb_team("")
    'UNK'
    """
    if not value or not str(value).strip():
        return "UNK"

    raw = str(value).strip()

    # First try the base normalizer
    result = normalize_mlb_team_name(raw)
    if result and result != raw.upper():
        # Recognized by base normalizer
        return result

    # Underscored uppercase variant: "LOS_ANGELES_DODGERS"
    if "_" in raw and raw == raw.upper():
        readable = raw.replace("_", " ")
        alt = normalize_mlb_team_name(readable)
        if alt and alt != readable.upper():
            return alt
        # Partial suffix match on readable form
        words = readable.lower().split()
        if words:
            for attempt in (words[-1], " ".join(words[-2:])):
                alt2 = normalize_mlb_team_name(attempt)
                if alt2 and alt2 != attempt.upper():
                    return alt2

    # Final fallback: return whatever the base normalizer produced
    return result if result else raw.upper()


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Game ID builders
# ─────────────────────────────────────────────────────────────────────────────

def build_mlb_game_id(date: str, home_team: str, away_team: str) -> str:
    """
    Build a stable game_id string in the canonical format.

    Format: ``YYYY-MM-DD_<HOME_CODE>_<AWAY_CODE>``

    Example::

        build_mlb_game_id("2025-03-18", "Chicago Cubs", "Los Angeles Dodgers")
        # → "2025-03-18_CHC_LAD"

    Parameters
    ----------
    date : str
        Game date, either ISO format (YYYY-MM-DD) or M/D/YYYY.
        Only the first 10 characters are used.
    home_team : str
        Home team name or code.
    away_team : str
        Away team name or code.

    Returns
    -------
    str
        Stable game_id.
    """
    d = _normalize_date(date)
    home_code = normalize_mlb_team(home_team)
    away_code = normalize_mlb_team(away_team)
    return f"{d}_{home_code}_{away_code}"


def build_mlb_date_team_key(date: str, home_team: str, away_team: str) -> str:
    """
    Build a date+team deduplication key.

    Format: ``YYYY-MM-DD_<HOME_CODE>_vs_<AWAY_CODE>``

    Parameters
    ----------
    date : str
        Game date in ISO format.
    home_team : str
        Home team name or code.
    away_team : str
        Away team name or code.

    Returns
    -------
    str
        Deduplication key.
    """
    d = _normalize_date(date)
    home_code = normalize_mlb_team(home_team)
    away_code = normalize_mlb_team(away_team)
    return f"{d}_{home_code}_vs_{away_code}"


def _normalize_date(date: str) -> str:
    """Normalize a date string to YYYY-MM-DD (ISO 8601)."""
    if not date or not str(date).strip():
        return "UNKNOWN"
    raw = str(date).strip()
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    # M/D/YYYY or MM/DD/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        mo, dy, yr = m.group(1), m.group(2), m.group(3)
        return f"{yr}-{int(mo):02d}-{int(dy):02d}"
    # YYYYMMDD
    m2 = re.match(r"^(\d{4})(\d{2})(\d{2})$", raw)
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    return raw[:10]


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Context-file game_id parser
# ─────────────────────────────────────────────────────────────────────────────

# Pattern for context file game_ids:
#   MLB-{YYYY}_{MM}_{DD}-{HH}_{MM}_{AM|PM}-{AWAY_TEAM_UPPER}-AT-{HOME_TEAM_UPPER}
#   e.g.: MLB-2025_03_18-6_10_AM-LOS_ANGELES_DODGERS-AT-CHICAGO_CUBS
_CONTEXT_GID_RE = re.compile(
    r"^MLB-"                              # prefix
    r"(\d{4})_(\d{2})_(\d{2})"           # date: YYYY_MM_DD
    r"-[^-]+-[^-]+-[AP]M"                # time segment (e.g. 6_10_AM)
    r"-(.+?)-AT-(.+)$"                   # away-AT-home
)

# Simpler pattern that handles variations
_CONTEXT_GID_SIMPLE = re.compile(
    r"^MLB-"
    r"(\d{4})_(\d{1,2})_(\d{1,2})"      # date: YYYY_M_D
    r"-.+?-[AP]M"                         # time block (anything ending in AM/PM)
    r"-(.+?)-AT-(.+)$"                   # away-AT-home
)


def parse_context_game_id(
    context_game_id: str,
) -> tuple[str, str, str] | None:
    """
    Parse a context-file game_id into (date_iso, home_code, away_code).

    Handles the format used by bullpen_usage_3d.jsonl and injury_rest.jsonl:
    ``MLB-2025_03_18-6_10_AM-LOS_ANGELES_DODGERS-AT-CHICAGO_CUBS``

    Parameters
    ----------
    context_game_id : str
        Raw game_id from a context JSONL file.

    Returns
    -------
    tuple[str, str, str] | None
        (date_iso, home_code, away_code) or None if parsing fails.

    Examples
    --------
    >>> parse_context_game_id(
    ...     "MLB-2025_03_18-6_10_AM-LOS_ANGELES_DODGERS-AT-CHICAGO_CUBS"
    ... )
    ('2025-03-18', 'CHC', 'LAD')
    """
    if not context_game_id:
        return None

    # Try both patterns
    for pattern in (_CONTEXT_GID_RE, _CONTEXT_GID_SIMPLE):
        m = pattern.match(context_game_id)
        if m:
            yr, mo, dy = m.group(1), m.group(2), m.group(3)
            away_raw = m.group(4)
            home_raw = m.group(5)
            date_iso = f"{yr}-{int(mo):02d}-{int(dy):02d}"
            away_code = normalize_mlb_team(away_raw)
            home_code = normalize_mlb_team(home_raw)
            return date_iso, home_code, away_code

    # Fallback: try to extract date + last two team segments
    parts = context_game_id.split("-")
    # Find the -AT- separator
    try:
        at_idx = parts.index("AT")
        home_raw = "_".join(parts[at_idx + 1:])
        # Reconstruct away from segments after the time block
        # Date is always in parts[1]: YYYY_MM_DD
        date_part = parts[1] if len(parts) > 1 else ""
        dm = re.match(r"(\d{4})_(\d{1,2})_(\d{1,2})", date_part)
        if not dm:
            return None
        yr, mo, dy = dm.group(1), dm.group(2), dm.group(3)
        date_iso = f"{yr}-{int(mo):02d}-{int(dy):02d}"

        # Away is everything between time block and AT
        # Find time block index (the one ending with AM or PM)
        time_idx = next(
            (i for i, p in enumerate(parts) if p.endswith(("AM", "PM"))),
            None,
        )
        if time_idx is None:
            return None
        away_raw = "_".join(parts[time_idx + 1 : at_idx])
        away_code = normalize_mlb_team(away_raw)
        home_code = normalize_mlb_team(home_raw)
        return date_iso, home_code, away_code
    except (ValueError, IndexError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Deduplication
# ─────────────────────────────────────────────────────────────────────────────

def dedupe_mlb_rows(rows: list[dict]) -> tuple[list[dict], dict]:
    """
    Deduplicate MLB prediction rows by game_id.

    If a row already has a ``game_id`` key, it is used directly.
    Otherwise the id is derived from ``Date`` + ``Home`` + ``Away``.

    Preference order when multiple rows share a game_id:
    1. Prefer the row that has ``model_prob_home`` (non-null, non-NaN).
    2. Then prefer the row that has ``market_prob_home``.
    3. Otherwise keep the first occurrence.

    Parameters
    ----------
    rows : list[dict]
        Input rows. May include any extra columns.

    Returns
    -------
    tuple[list[dict], dict]
        ``(deduped_rows, metadata)``

        ``deduped_rows`` — list of dicts each guaranteed to have a ``game_id``
        key (added if not already present).

        ``metadata`` — dict with keys:
            - ``input_count``
            - ``output_count``
            - ``duplicate_game_id_count``
            - ``duplicate_date_team_key_count``
            - ``dropped_count``
            - ``risk_reasons`` — list of human-readable risk strings
    """
    input_count = len(rows)
    seen: dict[str, dict] = {}            # game_id → best row
    date_team_key_counts: dict[str, int] = {}
    duplicate_game_id_count = 0

    for row in rows:
        gid = _extract_game_id(row)
        dtk = gid  # same key (YYYY-MM-DD_HOME_AWAY)

        date_team_key_counts[dtk] = date_team_key_counts.get(dtk, 0) + 1

        if gid in seen:
            duplicate_game_id_count += 1
            existing = seen[gid]
            if _row_has_value(row, "model_prob_home") and not _row_has_value(
                existing, "model_prob_home"
            ):
                seen[gid] = dict(row, game_id=gid)
            elif not _row_has_value(row, "model_prob_home") and _row_has_value(
                existing, "model_prob_home"
            ):
                pass  # keep existing
            elif _row_has_value(row, "market_prob_home") and not _row_has_value(
                existing, "market_prob_home"
            ):
                seen[gid] = dict(row, game_id=gid)
            # else: keep first occurrence
        else:
            seen[gid] = dict(row, game_id=gid)

    duplicate_date_team_key_count = sum(
        1 for cnt in date_team_key_counts.values() if cnt > 1
    )
    deduped_rows = list(seen.values())
    output_count = len(deduped_rows)
    dropped_count = input_count - output_count

    risk_reasons: list[str] = []
    if duplicate_game_id_count > 0:
        risk_reasons.append(
            f"{duplicate_game_id_count} duplicate game_id rows encountered"
        )
    if duplicate_date_team_key_count > 0:
        risk_reasons.append(
            f"{duplicate_date_team_key_count} date+team key groups have duplicates"
        )

    metadata: dict[str, Any] = {
        "input_count": input_count,
        "output_count": output_count,
        "duplicate_game_id_count": duplicate_game_id_count,
        "duplicate_date_team_key_count": duplicate_date_team_key_count,
        "dropped_count": dropped_count,
        "risk_reasons": risk_reasons,
    }
    return deduped_rows, metadata


def _extract_game_id(row: dict) -> str:
    """Extract or derive game_id from a row dict."""
    existing = str(row.get("game_id") or "").strip()
    if existing:
        return existing
    date = str(row.get("Date") or row.get("date") or row.get("game_date") or "").strip()
    home = str(row.get("Home") or row.get("home_team") or "").strip()
    away = str(row.get("Away") or row.get("away_team") or "").strip()
    return build_mlb_game_id(date, home, away)


def _row_has_value(row: dict, key: str) -> bool:
    """Return True if row[key] is a non-null, non-NaN, non-empty value."""
    v = row.get(key)
    if v is None:
        return False
    s = str(v).strip().lower()
    return s not in ("", "nan", "none", "null", "nat")
