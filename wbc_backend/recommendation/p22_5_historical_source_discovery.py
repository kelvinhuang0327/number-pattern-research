"""
P22.5 Historical Source Discovery Scanner.

Safely scans directories for CSV/JSONL files that may serve as
historical source artifacts. Never mutates scanned files.
Never fabricates missing data.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

from wbc_backend.recommendation.p22_5_source_artifact_contract import (
    HISTORICAL_GAME_IDENTITY,
    HISTORICAL_GAME_OUTCOMES,
    HISTORICAL_MARKET_ODDS,
    HISTORICAL_OOF_PREDICTIONS,
    HISTORICAL_P15_JOINED_INPUT,
    HISTORICAL_P15_SIMULATION_INPUT,
    MAPPING_RISK_HIGH,
    MAPPING_RISK_LOW,
    MAPPING_RISK_MEDIUM,
    MAPPING_RISK_UNKNOWN,
    SOURCE_CANDIDATE_MISSING,
    SOURCE_CANDIDATE_PARTIAL,
    SOURCE_CANDIDATE_UNKNOWN,
    SOURCE_CANDIDATE_UNSAFE_MAPPING,
    SOURCE_CANDIDATE_USABLE,
    P225HistoricalSourceCandidate,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_SCAN_ROWS = 500  # rows to read for coverage estimation
MAX_SAMPLE_ROWS = 5  # rows for quick classification

# Directories to always skip during scan
_SKIP_DIR_PATTERNS = {
    ".venv",
    "runtime",
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
}

# Skip our own backfill outputs to avoid circular detection
_SKIP_PATH_SUBSTRINGS = [
    "backfill/p22_",
    "backfill/p21_",
    "backfill/p23_",
]

# Column sets for detection
_GAME_ID_COLS = {"game_id"}
_Y_TRUE_COLS = {"y_true"}
_Y_TRUE_DERIVED_COLS = {"Away Score", "Home Score"}  # can derive y_true
_ODDS_COLS = {
    "odds_decimal",
    "odds_decimal_home",
    "odds_decimal_away",
    "decimal_odds",
    "Away ML",
    "Home ML",
    "away_ml",
    "home_ml",
}
_PRED_COLS = {"p_oof", "p_model", "predicted_probability", "p_market"}
_TEAM_COLS = {"home_team", "away_team", "Away", "Home", "home_team_raw", "away_team_raw"}
_DATE_COLS = {
    "game_date",
    "Date",
    "predict_window_start",
    "match_time_utc",
    "date",
    "run_date",
}

_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_historical_source_candidates(
    base_paths: Sequence[str],
    date_start: str,
    date_end: str,
) -> List[P225HistoricalSourceCandidate]:
    """Scan base_paths for CSV/JSONL files that may be historical sources.

    Returns a list of P225HistoricalSourceCandidate, one per discovered file.
    Does NOT mutate any scanned file.
    """
    candidates: List[P225HistoricalSourceCandidate] = []
    seen: set[str] = set()

    for base_path_str in base_paths:
        base_path = Path(base_path_str)
        if not base_path.exists():
            continue
        if not base_path.is_dir():
            continue

        for fpath in _walk_files(base_path):
            abs_str = str(fpath.resolve())
            if abs_str in seen:
                continue
            seen.add(abs_str)

            candidate = scan_candidate_file(fpath)
            if candidate is not None:
                candidates.append(candidate)

    # Sort by source_path for determinism
    candidates.sort(key=lambda c: c.source_path)
    return candidates


def scan_candidate_file(path: Path) -> Optional[P225HistoricalSourceCandidate]:
    """Scan a single file and return a candidate, or None if irrelevant.

    Reads only headers and a small sample. Never mutates the file.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in {".csv", ".jsonl", ".json"}:
        return None

    try:
        size = path.stat().st_size
    except OSError:
        return None

    if size == 0:
        return None
    if size > MAX_FILE_SIZE_BYTES:
        return _make_candidate(
            path,
            source_type=SOURCE_CANDIDATE_UNKNOWN,
            has_game_id=False,
            has_y_true=False,
            has_odds=False,
            has_p_model_or_p_oof=False,
            coverage_pct=0.0,
            row_count=-1,
            mapping_risk=MAPPING_RISK_UNKNOWN,
            candidate_status=SOURCE_CANDIDATE_UNKNOWN,
            source_date="",
            error_message="FILE_TOO_LARGE",
        )

    try:
        if suffix == ".csv":
            return _scan_csv(path)
        elif suffix == ".jsonl":
            return _scan_jsonl(path)
        elif suffix == ".json":
            return _scan_json(path)
    except Exception as exc:  # noqa: BLE001
        return _make_candidate(
            path,
            source_type=SOURCE_CANDIDATE_UNKNOWN,
            has_game_id=False,
            has_y_true=False,
            has_odds=False,
            has_p_model_or_p_oof=False,
            coverage_pct=0.0,
            row_count=-1,
            mapping_risk=MAPPING_RISK_UNKNOWN,
            candidate_status=SOURCE_CANDIDATE_MISSING,
            source_date="",
            error_message=f"READ_ERROR:{exc}",
        )
    return None


def infer_candidate_date(
    path: Path,
    columns: Optional[List[str]] = None,
    content_sample: Optional[pd.DataFrame] = None,
) -> str:
    """Infer the source date for a candidate file.

    Tries path components first, then content columns.
    Returns YYYY-MM-DD string or "" if ambiguous/missing.
    """
    # 1. Check path components for YYYY-MM-DD
    for part in reversed(path.parts):
        m = _DATE_PATTERN.search(part)
        if m:
            return m.group(0)

    # 2. Check column values in sample
    if content_sample is not None and not content_sample.empty:
        for col in _DATE_COLS:
            if col in content_sample.columns:
                vals = content_sample[col].dropna().astype(str)
                dates = [_DATE_PATTERN.search(v) for v in vals]
                found = [m.group(0) for m in dates if m]
                if len(set(found)) == 1:
                    return found[0]
                if found:
                    # Multiple distinct dates — ambiguous but return first
                    return found[0]

    return ""


def classify_source_candidate(
    has_game_id: bool,
    has_y_true: bool,
    has_odds: bool,
    has_p_model_or_p_oof: bool,
    has_team_fields: bool,
    source_date: str,
    mapping_risk: str,
) -> str:
    """Classify a source candidate based on its detected fields.

    Returns a SOURCE_CANDIDATE_* constant.
    """
    # Count key data fields first
    n_key = sum([has_y_true, has_odds, has_p_model_or_p_oof, has_game_id or has_team_fields])

    # No relevant fields at all → missing
    if n_key == 0:
        return SOURCE_CANDIDATE_MISSING

    # A fully-joined P15 input (has everything) → usable
    if has_game_id and has_y_true and has_odds and has_p_model_or_p_oof:
        return SOURCE_CANDIDATE_USABLE

    # Missing date with no game_id → unsafe identity mapping
    if not source_date and not has_game_id:
        return SOURCE_CANDIDATE_UNSAFE_MAPPING

    # HIGH mapping risk with no game_id → unsafe
    if mapping_risk == MAPPING_RISK_HIGH and not has_game_id:
        return SOURCE_CANDIDATE_UNSAFE_MAPPING

    # Useful if at least 3 of 4 key fields present → usable
    if n_key >= 3:
        return SOURCE_CANDIDATE_USABLE

    # 2 key fields → partial
    if n_key >= 2:
        return SOURCE_CANDIDATE_PARTIAL

    # 1 key field → partial
    return SOURCE_CANDIDATE_PARTIAL


def summarize_source_candidates(
    candidates: List[P225HistoricalSourceCandidate],
) -> Dict[str, int]:
    """Return a count summary of candidate statuses."""
    from collections import Counter

    counts = Counter(c.candidate_status for c in candidates)
    return {
        "n_total": len(candidates),
        "n_usable": counts.get(SOURCE_CANDIDATE_USABLE, 0),
        "n_partial": counts.get(SOURCE_CANDIDATE_PARTIAL, 0),
        "n_missing": counts.get(SOURCE_CANDIDATE_MISSING, 0),
        "n_unsafe": counts.get(SOURCE_CANDIDATE_UNSAFE_MAPPING, 0),
        "n_unknown": counts.get(SOURCE_CANDIDATE_UNKNOWN, 0),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _walk_files(base_path: Path) -> List[Path]:
    """Yield files under base_path, skipping forbidden directories."""
    result: List[Path] = []
    try:
        for item in base_path.rglob("*"):
            # Skip forbidden dir patterns
            if any(skip in item.parts for skip in _SKIP_DIR_PATTERNS):
                continue
            # Skip backfill output subdirs
            item_str = str(item)
            if any(sub in item_str for sub in _SKIP_PATH_SUBSTRINGS):
                continue
            if item.is_file():
                result.append(item)
    except PermissionError:
        pass
    return result


def _detect_columns(columns: List[str]) -> Dict[str, bool]:
    col_set = set(columns)
    has_game_id = bool(col_set & _GAME_ID_COLS)
    has_y_true = bool(col_set & _Y_TRUE_COLS) or bool(col_set & _Y_TRUE_DERIVED_COLS)
    has_odds = bool(col_set & _ODDS_COLS)
    has_p_model_or_p_oof = bool(col_set & _PRED_COLS)
    has_team_fields = bool(col_set & _TEAM_COLS)
    has_date = bool(col_set & _DATE_COLS)
    return {
        "has_game_id": has_game_id,
        "has_y_true": has_y_true,
        "has_odds": has_odds,
        "has_p_model_or_p_oof": has_p_model_or_p_oof,
        "has_team_fields": has_team_fields,
        "has_date": has_date,
    }


def _infer_mapping_risk(
    has_game_id: bool,
    has_team_fields: bool,
    has_date: bool,
    source_date: str,
) -> str:
    if has_game_id:
        return MAPPING_RISK_LOW
    if has_team_fields and (has_date or source_date):
        return MAPPING_RISK_MEDIUM
    if has_team_fields:
        return MAPPING_RISK_HIGH
    return MAPPING_RISK_HIGH


def _infer_source_type(
    has_game_id: bool,
    has_y_true: bool,
    has_odds: bool,
    has_p_model_or_p_oof: bool,
) -> str:
    if has_game_id and has_y_true and has_odds and has_p_model_or_p_oof:
        return HISTORICAL_P15_JOINED_INPUT
    if has_y_true and has_p_model_or_p_oof and has_odds:
        return HISTORICAL_P15_SIMULATION_INPUT
    if has_p_model_or_p_oof:
        return HISTORICAL_OOF_PREDICTIONS
    if has_odds and (has_y_true or has_game_id):
        return HISTORICAL_MARKET_ODDS
    if has_y_true:
        return HISTORICAL_GAME_OUTCOMES
    if has_game_id:
        return HISTORICAL_GAME_IDENTITY
    return SOURCE_CANDIDATE_UNKNOWN


def _estimate_coverage(df: pd.DataFrame, detected: Dict[str, bool]) -> float:
    """Estimate coverage ratio of key columns in sample."""
    key_cols_present = []
    for col in ["game_id", "y_true", "Away Score", "Home Score",
                "odds_decimal", "Away ML", "Home ML", "p_oof", "p_model"]:
        if col in df.columns:
            key_cols_present.append(col)
    if not key_cols_present:
        return 0.0
    non_null = sum(df[c].notna().mean() for c in key_cols_present)
    return round(non_null / len(key_cols_present), 4)


def _scan_csv(path: Path) -> Optional[P225HistoricalSourceCandidate]:
    """Scan a CSV file by reading headers and a small sample."""
    # Read just headers first
    try:
        header_df = pd.read_csv(path, nrows=0)
    except Exception:
        return None

    columns = list(header_df.columns)
    detected = _detect_columns(columns)

    # Check if file has any relevant columns
    if not any([detected["has_game_id"], detected["has_y_true"], detected["has_odds"],
                detected["has_p_model_or_p_oof"], detected["has_team_fields"]]):
        return None  # Not a relevant file

    # Read small sample for date inference and coverage
    try:
        sample_df = pd.read_csv(path, nrows=MAX_SAMPLE_ROWS)
    except Exception:
        sample_df = header_df

    source_date = infer_candidate_date(path, columns, sample_df)
    mapping_risk = _infer_mapping_risk(
        detected["has_game_id"],
        detected["has_team_fields"],
        detected["has_date"],
        source_date,
    )
    source_type = _infer_source_type(
        detected["has_game_id"],
        detected["has_y_true"],
        detected["has_odds"],
        detected["has_p_model_or_p_oof"],
    )
    candidate_status = classify_source_candidate(
        has_game_id=detected["has_game_id"],
        has_y_true=detected["has_y_true"],
        has_odds=detected["has_odds"],
        has_p_model_or_p_oof=detected["has_p_model_or_p_oof"],
        has_team_fields=detected["has_team_fields"],
        source_date=source_date,
        mapping_risk=mapping_risk,
    )
    coverage_pct = _estimate_coverage(sample_df, detected)

    # Estimate row count from file size
    size = path.stat().st_size
    avg_row_bytes = max(size // max(len(sample_df), 1), 1) if not sample_df.empty else 100
    row_count_est = max(size // avg_row_bytes, 1)

    return _make_candidate(
        path=path,
        source_type=source_type,
        has_game_id=detected["has_game_id"],
        has_y_true=detected["has_y_true"],
        has_odds=detected["has_odds"],
        has_p_model_or_p_oof=detected["has_p_model_or_p_oof"],
        coverage_pct=coverage_pct,
        row_count=row_count_est,
        mapping_risk=mapping_risk,
        candidate_status=candidate_status,
        source_date=source_date,
        error_message="",
    )


def _scan_jsonl(path: Path) -> Optional[P225HistoricalSourceCandidate]:
    """Scan a JSONL file by reading the first line."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            first_line = fh.readline().strip()
    except OSError:
        return None

    if not first_line:
        return None

    try:
        record = json.loads(first_line)
    except json.JSONDecodeError:
        return None

    if not isinstance(record, dict):
        return None

    columns = list(record.keys())
    detected = _detect_columns(columns)

    # Also check for nested fields common in TSL data
    if "decimal_odds" in record:
        detected["has_odds"] = True

    if not any([detected["has_game_id"], detected["has_y_true"], detected["has_odds"],
                detected["has_p_model_or_p_oof"], detected["has_team_fields"]]):
        return None

    source_date = infer_candidate_date(path)
    if not source_date and "match_time_utc" in record:
        m = _DATE_PATTERN.search(str(record.get("match_time_utc", "")))
        if m:
            source_date = m.group(0)

    mapping_risk = _infer_mapping_risk(
        detected["has_game_id"],
        detected["has_team_fields"],
        detected["has_date"],
        source_date,
    )
    source_type = _infer_source_type(
        detected["has_game_id"],
        detected["has_y_true"],
        detected["has_odds"],
        detected["has_p_model_or_p_oof"],
    )
    candidate_status = classify_source_candidate(
        has_game_id=detected["has_game_id"],
        has_y_true=detected["has_y_true"],
        has_odds=detected["has_odds"],
        has_p_model_or_p_oof=detected["has_p_model_or_p_oof"],
        has_team_fields=detected["has_team_fields"],
        source_date=source_date,
        mapping_risk=mapping_risk,
    )

    return _make_candidate(
        path=path,
        source_type=source_type,
        has_game_id=detected["has_game_id"],
        has_y_true=detected["has_y_true"],
        has_odds=detected["has_odds"],
        has_p_model_or_p_oof=detected["has_p_model_or_p_oof"],
        coverage_pct=1.0 if candidate_status == SOURCE_CANDIDATE_USABLE else 0.5,
        row_count=-1,  # JSONL row count not estimated
        mapping_risk=mapping_risk,
        candidate_status=candidate_status,
        source_date=source_date,
        error_message="",
    )


def _scan_json(path: Path) -> Optional[P225HistoricalSourceCandidate]:
    """Scan a JSON file for relevant top-level keys."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            content = fh.read(4096)  # Only first 4KB
        data = json.loads(content)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    columns = list(data.keys())
    detected = _detect_columns(columns)
    if not any([detected["has_game_id"], detected["has_y_true"], detected["has_odds"],
                detected["has_p_model_or_p_oof"]]):
        return None

    source_date = infer_candidate_date(path)
    mapping_risk = _infer_mapping_risk(
        detected["has_game_id"],
        detected["has_team_fields"],
        detected["has_date"],
        source_date,
    )
    source_type = _infer_source_type(
        detected["has_game_id"],
        detected["has_y_true"],
        detected["has_odds"],
        detected["has_p_model_or_p_oof"],
    )
    candidate_status = classify_source_candidate(
        has_game_id=detected["has_game_id"],
        has_y_true=detected["has_y_true"],
        has_odds=detected["has_odds"],
        has_p_model_or_p_oof=detected["has_p_model_or_p_oof"],
        has_team_fields=detected["has_team_fields"],
        source_date=source_date,
        mapping_risk=mapping_risk,
    )
    return _make_candidate(
        path=path,
        source_type=source_type,
        has_game_id=detected["has_game_id"],
        has_y_true=detected["has_y_true"],
        has_odds=detected["has_odds"],
        has_p_model_or_p_oof=detected["has_p_model_or_p_oof"],
        coverage_pct=0.5,
        row_count=1,
        mapping_risk=mapping_risk,
        candidate_status=candidate_status,
        source_date=source_date,
        error_message="",
    )


def _make_candidate(
    path: Path,
    source_type: str,
    has_game_id: bool,
    has_y_true: bool,
    has_odds: bool,
    has_p_model_or_p_oof: bool,
    coverage_pct: float,
    row_count: int,
    mapping_risk: str,
    candidate_status: str,
    source_date: str,
    error_message: str,
) -> P225HistoricalSourceCandidate:
    return P225HistoricalSourceCandidate(
        source_path=str(path),
        source_type=source_type,
        source_date=source_date,
        coverage_pct=coverage_pct,
        row_count=row_count,
        has_game_id=has_game_id,
        has_y_true=has_y_true,
        has_odds=has_odds,
        has_p_model_or_p_oof=has_p_model_or_p_oof,
        mapping_risk=mapping_risk,
        candidate_status=candidate_status,
        paper_only=True,
        production_ready=False,
        error_message=error_message,
    )
