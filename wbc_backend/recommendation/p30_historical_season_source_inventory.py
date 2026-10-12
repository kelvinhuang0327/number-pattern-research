"""
wbc_backend/recommendation/p30_historical_season_source_inventory.py

P30 Historical Season Source Inventory Scanner.

Scans existing data directories and outputs directories for historical season
source files. Classifies each source by schema coverage and provenance.

Rules:
- Do not mutate any files.
- Do not assume a file is safe without provenance/schema coverage.
- Classify partial sources correctly.
- Do not fabricate missing columns or outcomes.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p30_source_acquisition_contract import (
    P30HistoricalSeasonSourceCandidate,
    SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
    SOURCE_PLAN_BLOCKED_PROVENANCE,
    SOURCE_PLAN_BLOCKED_SCHEMA_GAP,
    SOURCE_PLAN_PARTIAL,
    SOURCE_PLAN_READY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column detection sets
# ---------------------------------------------------------------------------

_GAME_ID_COLS = frozenset({"game_id", "gameid", "game_pk", "gamepk"})
_GAME_DATE_COLS = frozenset({"game_date", "date", "Date", "game_dt"})
_Y_TRUE_COLS = frozenset({"y_true", "outcome", "result", "winner"})
_HOME_TEAM_COLS = frozenset({"home_team", "Home", "home", "home_name"})
_AWAY_TEAM_COLS = frozenset({"away_team", "Away", "away", "away_name"})
_P_MODEL_COLS = frozenset({"p_model", "p_oof", "model_prob", "pred_prob", "win_prob"})
_P_MARKET_COLS = frozenset({"p_market", "market_prob", "implied_prob"})
_ODDS_COLS = frozenset({"odds_decimal", "decimal_odds", "Away ML", "Home ML", "ml_away", "ml_home"})

# Minimum readable row count to classify a source as non-empty
_MIN_ROWS_NONEMPTY = 10

# Supported file extensions
_SUPPORTED_EXTENSIONS = frozenset({".csv", ".parquet", ".xlsx"})


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _probe_columns(path: Path, nrows: int = 5) -> Optional[List[str]]:
    """Return column names from a file, or None if unreadable."""
    try:
        if path.suffix == ".csv":
            df = pd.read_csv(path, nrows=nrows)
            return list(df.columns)
        elif path.suffix == ".parquet":
            df = pd.read_parquet(path)
            return list(df.columns)
        elif path.suffix == ".xlsx":
            df = pd.read_excel(path, nrows=nrows)
            return list(df.columns)
    except Exception as exc:
        logger.debug("Cannot probe columns for %s: %s", path, exc)
    return None


def _probe_row_count(path: Path) -> int:
    """Return approximate row count; -1 if unreadable."""
    try:
        if path.suffix == ".csv":
            df = pd.read_csv(path, usecols=[0])
            return len(df)
        elif path.suffix == ".parquet":
            df = pd.read_parquet(path, columns=[pd.read_parquet(path).columns[0]])
            return len(df)
        elif path.suffix == ".xlsx":
            df = pd.read_excel(path, usecols=[0])
            return len(df)
    except Exception as exc:
        logger.debug("Cannot probe row count for %s: %s", path, exc)
    return -1


def _col_intersect(cols: List[str], target_set: frozenset) -> bool:
    """Return True if any column name (case-insensitive) matches target_set."""
    cols_lower = {c.lower().strip() for c in cols}
    target_lower = {t.lower().strip() for t in target_set}
    return bool(cols_lower & target_lower)


def _infer_season(path: Path) -> str:
    """Attempt to infer season year from path name."""
    name = str(path)
    for year in ["2024", "2025", "2026", "2023"]:
        if year in name:
            return year
    return "UNKNOWN"


def _infer_date_range(path: Path, columns: List[str]) -> Tuple[str, str]:
    """Attempt to read min/max date from a date column."""
    date_col = None
    for col in columns:
        if col.lower() in {c.lower() for c in _GAME_DATE_COLS}:
            date_col = col
            break
    if date_col is None:
        return ("", "")
    try:
        if path.suffix == ".csv":
            df = pd.read_csv(path, usecols=[date_col], parse_dates=[date_col])
        elif path.suffix == ".parquet":
            df = pd.read_parquet(path, columns=[date_col])
        elif path.suffix == ".xlsx":
            df = pd.read_excel(path, usecols=[date_col])
        else:
            return ("", "")
        series = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if series.empty:
            return ("", "")
        return (str(series.min().date()), str(series.max().date()))
    except Exception as exc:
        logger.debug("Cannot infer date range for %s: %s", path, exc)
        return ("", "")


def _classify_schema_coverage(
    has_game_id: bool,
    has_game_date: bool,
    has_y_true: bool,
    has_home_away: bool,
    has_p_model: bool,
    has_p_market: bool,
    has_odds: bool,
) -> str:
    score = sum([has_game_id, has_game_date, has_y_true, has_home_away, has_p_model, has_p_market, has_odds])
    if score >= 6:
        return "FULL"
    elif score >= 3:
        return "PARTIAL"
    else:
        return "MINIMAL"


def _determine_source_status(
    columns: Optional[List[str]],
    row_count: int,
    has_game_date: bool,
    has_y_true: bool,
    has_p_model: bool,
    has_p_market: bool,
    has_odds: bool,
    schema_coverage: str,
) -> Tuple[str, str]:
    """Return (source_status, coverage_note)."""
    if columns is None or row_count < _MIN_ROWS_NONEMPTY:
        return (
            SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
            "File unreadable or fewer than 10 rows.",
        )
    if schema_coverage == "FULL":
        return (SOURCE_PLAN_READY, "All required schema fields present.")

    missing = []
    if not has_y_true:
        missing.append("y_true/outcome")
    if not has_p_model:
        missing.append("p_model/p_oof")
    if not has_p_market:
        missing.append("p_market")
    if not has_odds:
        missing.append("odds_decimal")

    note = f"Partial schema: missing {', '.join(missing)}." if missing else "Partial schema."
    return (SOURCE_PLAN_PARTIAL, note)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def inspect_schema_coverage(path: Path) -> Dict[str, Any]:
    """
    Read a file and return a schema coverage dict.
    Does not mutate any files.
    """
    columns = _probe_columns(path)
    row_count = _probe_row_count(path) if columns is not None else -1

    if columns is None:
        return {
            "path": str(path),
            "readable": False,
            "columns": [],
            "row_count": row_count,
            "has_game_id": False,
            "has_game_date": False,
            "has_y_true": False,
            "has_home_away_teams": False,
            "has_p_model": False,
            "has_p_market": False,
            "has_odds_decimal": False,
            "schema_coverage": "MINIMAL",
            "date_start": "",
            "date_end": "",
        }

    has_game_id = _col_intersect(columns, _GAME_ID_COLS)
    has_game_date = _col_intersect(columns, _GAME_DATE_COLS)
    has_y_true = _col_intersect(columns, _Y_TRUE_COLS)
    has_home_away = _col_intersect(columns, _HOME_TEAM_COLS) and _col_intersect(columns, _AWAY_TEAM_COLS)
    has_p_model = _col_intersect(columns, _P_MODEL_COLS)
    has_p_market = _col_intersect(columns, _P_MARKET_COLS)
    has_odds = _col_intersect(columns, _ODDS_COLS)

    schema_coverage = _classify_schema_coverage(
        has_game_id, has_game_date, has_y_true, has_home_away,
        has_p_model, has_p_market, has_odds,
    )
    date_start, date_end = _infer_date_range(path, columns)

    return {
        "path": str(path),
        "readable": True,
        "columns": sorted(columns),
        "row_count": row_count,
        "has_game_id": has_game_id,
        "has_game_date": has_game_date,
        "has_y_true": has_y_true,
        "has_home_away_teams": has_home_away,
        "has_p_model": has_p_model,
        "has_p_market": has_p_market,
        "has_odds_decimal": has_odds,
        "schema_coverage": schema_coverage,
        "date_start": date_start,
        "date_end": date_end,
    }


def estimate_games_and_dates(path: Path) -> Dict[str, Any]:
    """Return estimated game count and date range from a file."""
    schema = inspect_schema_coverage(path)
    return {
        "estimated_rows": schema["row_count"],
        "estimated_games": max(0, schema["row_count"]),  # 1 row ≈ 1 game for raw odds files
        "date_start": schema["date_start"],
        "date_end": schema["date_end"],
    }


def classify_source_by_season(candidate: Dict[str, Any]) -> str:
    """Return target season string inferred from candidate metadata."""
    path = Path(candidate.get("path", ""))
    explicit = candidate.get("target_season", "")
    if explicit and explicit != "UNKNOWN":
        return explicit
    return _infer_season(path)


def scan_existing_season_sources(base_paths: List[Path]) -> List[Dict[str, Any]]:
    """
    Scan provided base paths for historical season source files.
    Returns a list of raw candidate dicts (not frozen dataclasses).
    Does NOT mutate any files.
    """
    candidates: List[Dict[str, Any]] = []
    seen_paths: set = set()

    for base in base_paths:
        base = Path(base)
        if not base.exists():
            logger.debug("Skipping non-existent base path: %s", base)
            continue

        # Walk recursively up to 4 levels deep
        for path in sorted(base.rglob("*")):
            if path.suffix not in _SUPPORTED_EXTENSIONS:
                continue
            if path in seen_paths:
                continue
            seen_paths.add(path)

            # Skip obviously non-data paths
            path_str = str(path)
            if any(skip in path_str for skip in [".venv", "__pycache__", "node_modules"]):
                continue

            schema = inspect_schema_coverage(path)
            row_count = schema["row_count"]
            season = _infer_season(path)

            # Determine provenance
            provenance_status = "UNKNOWN"
            license_risk = "UNKNOWN"
            if "mlb_2025" in path_str or "mlb_2024" in path_str:
                provenance_status = "KNOWN_HISTORICAL"
                license_risk = "LOW"
            elif "derived" in path_str:
                provenance_status = "DERIVED_INTERNAL"
                license_risk = "LOW"
            elif "outputs" in path_str and "predictions" in path_str:
                provenance_status = "INTERNAL_PIPELINE_OUTPUT"
                license_risk = "LOW"

            status, note = _determine_source_status(
                schema["columns"] if schema["readable"] else None,
                row_count,
                schema["has_game_date"],
                schema["has_y_true"],
                schema["has_p_model"],
                schema["has_p_market"],
                schema["has_odds_decimal"],
                schema["schema_coverage"],
            )

            candidates.append(
                {
                    "path": str(path),
                    "source_type": path.suffix.lstrip("."),
                    "target_season": season,
                    "date_start": schema["date_start"],
                    "date_end": schema["date_end"],
                    "estimated_games": max(0, row_count),
                    "estimated_rows": row_count,
                    "has_game_id": schema["has_game_id"],
                    "has_game_date": schema["has_game_date"],
                    "has_y_true": schema["has_y_true"],
                    "has_home_away_teams": schema["has_home_away_teams"],
                    "has_p_model": schema["has_p_model"],
                    "has_p_market": schema["has_p_market"],
                    "has_odds_decimal": schema["has_odds_decimal"],
                    "provenance_status": provenance_status,
                    "license_risk": license_risk,
                    "schema_coverage": schema["schema_coverage"],
                    "source_status": status,
                    "coverage_note": note,
                    "paper_only": True,
                    "production_ready": False,
                }
            )

    # Sort by season desc, then path for determinism
    candidates.sort(key=lambda c: (c["target_season"], c["path"]), reverse=True)
    return candidates


def summarize_existing_source_inventory(
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Summarize the source inventory scan results."""
    n_total = len(candidates)
    n_ready = sum(1 for c in candidates if c["source_status"] == SOURCE_PLAN_READY)
    n_partial = sum(1 for c in candidates if c["source_status"] == SOURCE_PLAN_PARTIAL)
    n_blocked_schema = sum(1 for c in candidates if c["source_status"] == SOURCE_PLAN_BLOCKED_SCHEMA_GAP)
    n_blocked_prov = sum(1 for c in candidates if c["source_status"] == SOURCE_PLAN_BLOCKED_PROVENANCE)
    n_not_available = sum(1 for c in candidates if c["source_status"] == SOURCE_PLAN_BLOCKED_NOT_AVAILABLE)

    seasons_found = sorted({c["target_season"] for c in candidates})
    has_2024 = any(c["target_season"] == "2024" for c in candidates)
    has_2025 = any(c["target_season"] == "2025" for c in candidates)
    has_2026 = any(c["target_season"] == "2026" for c in candidates)

    best_candidate = None
    ready_candidates = [c for c in candidates if c["source_status"] == SOURCE_PLAN_READY]
    partial_candidates = [c for c in candidates if c["source_status"] == SOURCE_PLAN_PARTIAL]
    if ready_candidates:
        best_candidate = ready_candidates[0]["path"]
    elif partial_candidates:
        best_candidate = partial_candidates[0]["path"]

    return {
        "n_candidates_scanned": n_total,
        "n_ready": n_ready,
        "n_partial": n_partial,
        "n_blocked_schema": n_blocked_schema,
        "n_blocked_provenance": n_blocked_prov,
        "n_not_available": n_not_available,
        "seasons_found": seasons_found,
        "has_2024_source": has_2024,
        "has_2025_source": has_2025,
        "has_2026_source": has_2026,
        "best_candidate_path": best_candidate,
        "acquisition_feasible": n_ready > 0,
        "note": (
            "At least one ready source found."
            if n_ready > 0
            else "No fully ready source found; partial sources require schema gap filling."
            if n_partial > 0
            else "No usable sources found."
        ),
    }


def build_source_candidates(
    raw_candidates: List[Dict[str, Any]],
) -> List[P30HistoricalSeasonSourceCandidate]:
    """Convert raw candidate dicts to frozen P30HistoricalSeasonSourceCandidate objects."""
    result = []
    for c in raw_candidates:
        try:
            obj = P30HistoricalSeasonSourceCandidate(
                source_path=c["path"],
                source_type=c["source_type"],
                target_season=c["target_season"],
                date_start=c["date_start"],
                date_end=c["date_end"],
                estimated_games=c["estimated_games"],
                estimated_rows=c["estimated_rows"],
                has_game_id=c["has_game_id"],
                has_game_date=c["has_game_date"],
                has_y_true=c["has_y_true"],
                has_home_away_teams=c["has_home_away_teams"],
                has_p_model=c["has_p_model"],
                has_p_market=c["has_p_market"],
                has_odds_decimal=c["has_odds_decimal"],
                provenance_status=c["provenance_status"],
                license_risk=c["license_risk"],
                schema_coverage=c["schema_coverage"],
                source_status=c["source_status"],
                coverage_note=c["coverage_note"],
                paper_only=True,
                production_ready=False,
            )
            result.append(obj)
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping candidate %s: %s", c.get("path", "?"), exc)
    return result
