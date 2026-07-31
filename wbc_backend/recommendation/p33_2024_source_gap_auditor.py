"""
P33 2024 Source Gap Auditor
============================
Scans known data directories for 2024 prediction and odds source candidates.
Classifies each candidate by season, schema coverage, license safety, and
leakage risk. Produces a P33SourceGapSummary.

PAPER_ONLY — never fabricates data, never imports from live TSL/Odds APIs.
No 2025 or 2026 data is treated as a valid 2024 source.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import List, Optional

import pandas as pd

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    SOURCE_BLOCKED_LICENSE,
    SOURCE_BLOCKED_SCHEMA,
    SOURCE_MISSING,
    SOURCE_PARTIAL,
    SOURCE_READY,
    SOURCE_UNKNOWN,
    P33OddsSourceCandidate,
    P33PredictionSourceCandidate,
    P33SourceGapSummary,
)

# ---------------------------------------------------------------------------
# Paths scanned by the auditor (in priority order)
# ---------------------------------------------------------------------------
DEFAULT_SCAN_PATHS: List[str] = [
    "data/mlb_2024",
    "data/mlb_2024/processed",
    "data/mlb_2024/raw",
    "data/mlb_2025",
    "data/derived",
    "outputs/predictions",
    "outputs/predictions/PAPER",
    "outputs",
    "data",
]

# Column name aliases recognised as prediction probability columns
PREDICTION_COLUMN_ALIASES: List[str] = [
    "p_model",
    "p_oof",
    "model_probability",
    "predicted_probability",
    "home_win_prob",
    "win_probability",
    "prob_home",
]

# Column name aliases recognised as market odds columns
ODDS_COLUMN_ALIASES: List[str] = [
    "p_market",
    "odds_decimal",
    "home_ml",
    "away_ml",
    "moneyline",
    "closing_odds",
    "ml_home",
    "ml_away",
    "closing_line",
    "open_odds",
]

# Column names that indicate a game identity is present
GAME_ID_ALIASES: List[str] = [
    "game_id",
    "game_key",
    "match_id",
    "canonical_match_id",
]

# Year tokens that indicate a non-2024 season in the file path or content
NON_2024_YEAR_TOKENS: List[str] = [
    "2025",
    "2026",
    "dry_run_2026",
    "2026-04-29",
    "2026-05",
]

# Path fragments that indicate a file is a P33-generated artifact (not a raw source).
# These must never be treated as candidate sources in the auditor scan.
P33_OUTPUT_PATH_FRAGMENTS: List[str] = [
    "p33_joined_input_gap",
    "p33_source_gap",
    "p33_gate_result",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_csv_columns(file_path: str) -> tuple:
    """Return column names from the first row of a CSV; empty tuple on error."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
        return tuple(col.strip() for col in header)
    except Exception:
        return ()


def _read_jsonl_keys(file_path: str) -> tuple:
    """Return keys from the first line of a JSONL file; empty tuple on error."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            first_line = fh.readline().strip()
        if not first_line:
            return ()
        obj = json.loads(first_line)
        return tuple(obj.keys())
    except Exception:
        return ()


def _read_json_keys(file_path: str) -> tuple:
    """Return top-level keys of a JSON file; empty tuple on error."""
    try:
        with open(file_path, encoding="utf-8") as fh:
            obj = json.load(fh)
        if isinstance(obj, dict):
            return tuple(obj.keys())
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return tuple(obj[0].keys())
        return ()
    except Exception:
        return ()


def _get_file_columns(file_path: str) -> tuple:
    """Dispatch column/key extraction by file extension."""
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        return _read_csv_columns(file_path)
    if ext == ".jsonl":
        return _read_jsonl_keys(file_path)
    if ext == ".json":
        return _read_json_keys(file_path)
    return ()


def _count_rows(file_path: str) -> int:
    """Return approximate row count (line count - 1 for CSV, line count for JSONL)."""
    try:
        ext = Path(file_path).suffix.lower()
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            lines = sum(1 for _ in fh)
        if ext == ".csv":
            return max(0, lines - 1)
        return lines
    except Exception:
        return 0


def _path_contains_non_2024_year(file_path: str) -> Optional[str]:
    """
    Return the year token found if the path or filename contains a non-2024
    year indicator; None otherwise.
    """
    normalized = file_path.replace("\\", "/")
    for token in NON_2024_YEAR_TOKENS:
        if token in normalized:
            return token
    return None


def _detect_season_from_path(file_path: str) -> Optional[int]:
    """Best-effort season detection from file path tokens."""
    for year in [2024, 2025, 2026, 2023, 2022]:
        if str(year) in file_path:
            return year
    return None


def _columns_intersect(columns: tuple, aliases: List[str]) -> bool:
    lower_cols = {c.lower() for c in columns}
    return any(alias.lower() in lower_cols for alias in aliases)


def _has_game_id(columns: tuple) -> bool:
    return _columns_intersect(columns, GAME_ID_ALIASES)


def _is_dry_run(file_path: str, columns: tuple) -> bool:
    lower_path = file_path.lower()
    if "dry_run" in lower_path or "dry-run" in lower_path:
        return True
    lower_cols = {c.lower() for c in columns}
    if "dry_run" in lower_cols or "is_dry_run" in lower_cols:
        return True
    return False


# ---------------------------------------------------------------------------
# Candidate classification
# ---------------------------------------------------------------------------


def classify_prediction_candidate(
    candidate_id: str, file_path: str
) -> P33PredictionSourceCandidate:
    """
    Inspect a single file and return a P33PredictionSourceCandidate with
    a status classification.
    """
    cols = _get_file_columns(file_path)
    row_count = _count_rows(file_path)
    season = _detect_season_from_path(file_path)
    non_2024_token = _path_contains_non_2024_year(file_path)
    dry_run = _is_dry_run(file_path, cols)

    has_game_id = _has_game_id(cols)
    has_p_model = _columns_intersect(cols, ["p_model", "model_probability", "home_win_prob", "prob_home"])
    has_p_oof = _columns_intersect(cols, ["p_oof", "oof_probability", "fold_prob", "predicted_probability"])

    # Determine status
    blocker_reason = ""

    if non_2024_token is not None:
        status = SOURCE_BLOCKED_SCHEMA
        blocker_reason = (
            f"File path contains non-2024 year token '{non_2024_token}'. "
            "Cross-year data cannot be used as a 2024 source."
        )
    elif season is not None and season != 2024:
        status = SOURCE_BLOCKED_SCHEMA
        blocker_reason = (
            f"Detected season={season} in path; only 2024 is valid for P33."
        )
    elif dry_run:
        status = SOURCE_BLOCKED_SCHEMA
        blocker_reason = (
            "File is a dry-run artifact (future/forward-looking). "
            "Dry-run predictions are NOT valid 2024 historical sources."
        )
    elif not has_game_id:
        status = SOURCE_BLOCKED_SCHEMA
        blocker_reason = "No game_id column detected; cannot join to 2024 game log."
    elif not has_p_model and not has_p_oof:
        status = SOURCE_BLOCKED_SCHEMA
        blocker_reason = (
            "No prediction probability column detected "
            "(expected p_model, p_oof, model_probability, etc.)."
        )
    elif has_p_model or has_p_oof:
        status = SOURCE_PARTIAL if not (has_p_model and has_p_oof) else SOURCE_READY
    else:
        status = SOURCE_UNKNOWN
        blocker_reason = "Insufficient schema evidence to classify source."

    year_verified = season == 2024 and non_2024_token is None and not dry_run

    return P33PredictionSourceCandidate(
        candidate_id=candidate_id,
        file_path=file_path,
        detected_season=season,
        has_game_id_column=has_game_id,
        has_p_model_column=has_p_model,
        has_p_oof_column=has_p_oof,
        detected_columns=cols,
        row_count=row_count,
        status=status,
        blocker_reason=blocker_reason,
        is_dry_run=dry_run,
        is_paper_only=PAPER_ONLY,
        year_verified=year_verified,
    )


def classify_odds_candidate(
    candidate_id: str, file_path: str
) -> P33OddsSourceCandidate:
    """
    Inspect a single file and return a P33OddsSourceCandidate with a
    status classification.
    """
    cols = _get_file_columns(file_path)
    row_count = _count_rows(file_path)
    season = _detect_season_from_path(file_path)
    non_2024_token = _path_contains_non_2024_year(file_path)

    has_game_id = _has_game_id(cols)
    has_moneyline = _columns_intersect(
        cols, ["home_ml", "away_ml", "moneyline", "ml_home", "ml_away"]
    )
    has_closing = _columns_intersect(
        cols, ["p_market", "odds_decimal", "closing_odds", "closing_line", "open_odds"]
    )

    # Detect sportsbook reference
    lower_path = file_path.lower()
    if "tsl" in lower_path or "taiwan" in lower_path:
        sportsbook_reference = "TSL (台灣運彩)"
    elif "pinnacle" in lower_path or "pin_" in lower_path:
        sportsbook_reference = "Pinnacle"
    elif "draftkings" in lower_path:
        sportsbook_reference = "DraftKings"
    elif "fanduel" in lower_path:
        sportsbook_reference = "FanDuel"
    else:
        sportsbook_reference = "UNKNOWN"

    blocker_reason = ""

    if non_2024_token is not None:
        status = SOURCE_BLOCKED_SCHEMA
        blocker_reason = (
            f"File path contains non-2024 year token '{non_2024_token}'. "
            "Cross-year odds cannot be used as a 2024 source."
        )
    elif season is not None and season != 2024:
        status = SOURCE_BLOCKED_SCHEMA
        blocker_reason = (
            f"Detected season={season}; only 2024 odds valid for P33."
        )
    elif not has_game_id:
        status = SOURCE_BLOCKED_SCHEMA
        blocker_reason = "No game_id column; cannot join to 2024 game log."
    elif not has_moneyline and not has_closing:
        status = SOURCE_BLOCKED_SCHEMA
        blocker_reason = (
            "No moneyline or closing-odds column found "
            "(expected home_ml, away_ml, odds_decimal, p_market, etc.)."
        )
    elif has_moneyline or has_closing:
        status = (
            SOURCE_PARTIAL
            if not (has_moneyline and has_closing)
            else SOURCE_READY
        )
    else:
        status = SOURCE_UNKNOWN
        blocker_reason = "Insufficient schema evidence."

    year_verified = season == 2024 and non_2024_token is None

    return P33OddsSourceCandidate(
        candidate_id=candidate_id,
        file_path=file_path,
        detected_season=season,
        has_game_id_column=has_game_id,
        has_moneyline_column=has_moneyline,
        has_closing_odds_column=has_closing,
        detected_columns=cols,
        row_count=row_count,
        status=status,
        blocker_reason=blocker_reason,
        sportsbook_reference=sportsbook_reference,
        year_verified=year_verified,
    )


# ---------------------------------------------------------------------------
# Directory scanner
# ---------------------------------------------------------------------------


def _enumerate_candidate_files(scan_paths: List[str], repo_root: str) -> List[str]:
    """
    Walk the given directories (relative to repo_root) and collect all
    CSV, JSON, and JSONL files that might be source candidates.
    """
    candidates: List[str] = []
    seen: set = set()

    for rel_path in scan_paths:
        abs_path = os.path.join(repo_root, rel_path)
        if not os.path.isdir(abs_path):
            continue
        for root, _dirs, files in os.walk(abs_path):
            for fname in files:
                ext = Path(fname).suffix.lower()
                if ext not in (".csv", ".json", ".jsonl"):
                    continue
                full = os.path.join(root, fname)
                if full in seen:
                    continue
                seen.add(full)
                candidates.append(full)

    return sorted(candidates)


def scan_all_source_candidates(
    repo_root: str,
    scan_paths: Optional[List[str]] = None,
) -> P33SourceGapSummary:
    """
    Main entry point. Scans all candidate paths and returns a fully
    populated P33SourceGapSummary.
    """
    if not PAPER_ONLY:
        raise RuntimeError("P33 auditor must run with PAPER_ONLY=True.")

    paths = scan_paths if scan_paths is not None else DEFAULT_SCAN_PATHS
    all_files = _enumerate_candidate_files(paths, repo_root)

    prediction_candidates: List[P33PredictionSourceCandidate] = []
    odds_candidates: List[P33OddsSourceCandidate] = []

    # P32 processed CSVs we know contain outcomes, not predictions
    KNOWN_OUTCOME_FILES = {
        "mlb_2024_game_identity.csv",
        "mlb_2024_game_outcomes.csv",
        "mlb_2024_game_identity_outcomes_joined.csv",
    }

    pred_ctr = 0
    odds_ctr = 0

    for fpath in all_files:
        fname = Path(fpath).name

        # Skip known output/marker files
        if fname.endswith("_gate_result.json") or fname.endswith("_manifest.json"):
            continue
        if fname in KNOWN_OUTCOME_FILES:
            continue
        # Skip P33-generated skeleton artifacts — they have required headers
        # but contain no real 2024 prediction/odds data.
        if any(frag in fpath for frag in P33_OUTPUT_PATH_FRAGMENTS):
            continue

        cols = _get_file_columns(fpath)

        # Route to prediction or odds classifier based on column evidence
        has_pred_col = _columns_intersect(cols, PREDICTION_COLUMN_ALIASES)
        has_odds_col = _columns_intersect(cols, ODDS_COLUMN_ALIASES)

        if has_pred_col:
            pred_ctr += 1
            cand = classify_prediction_candidate(f"pred_{pred_ctr:03d}", fpath)
            prediction_candidates.append(cand)

        if has_odds_col:
            odds_ctr += 1
            cand = classify_odds_candidate(f"odds_{odds_ctr:03d}", fpath)
            odds_candidates.append(cand)

    # Aggregate counts
    pred_ready = sum(1 for c in prediction_candidates if c.status == SOURCE_READY)
    pred_blocked = sum(
        1 for c in prediction_candidates if c.status != SOURCE_READY
    )
    odds_ready = sum(1 for c in odds_candidates if c.status == SOURCE_READY)
    odds_blocked = sum(1 for c in odds_candidates if c.status != SOURCE_READY)

    pred_missing = pred_ready == 0
    odds_missing = odds_ready == 0

    pred_gap_reason = ""
    if pred_missing:
        if prediction_candidates:
            reasons = list({c.blocker_reason for c in prediction_candidates if c.blocker_reason})
            pred_gap_reason = "; ".join(reasons[:3]) or "All candidates blocked."
        else:
            pred_gap_reason = (
                "No prediction source files found in scanned paths. "
                "2024 model predictions have never been generated or persisted."
            )

    odds_gap_reason = ""
    if odds_missing:
        if odds_candidates:
            reasons = list({c.blocker_reason for c in odds_candidates if c.blocker_reason})
            odds_gap_reason = "; ".join(reasons[:3]) or "All candidates blocked."
        else:
            odds_gap_reason = (
                "No odds source files found in scanned paths. "
                "2024 market odds (moneylines/closing) have never been acquired."
            )

    return P33SourceGapSummary(
        season=2024,
        prediction_candidates_found=len(prediction_candidates),
        odds_candidates_found=len(odds_candidates),
        prediction_ready_count=pred_ready,
        odds_ready_count=odds_ready,
        prediction_blocked_count=pred_blocked,
        odds_blocked_count=odds_blocked,
        prediction_missing=pred_missing,
        odds_missing=odds_missing,
        prediction_gap_reason=pred_gap_reason,
        odds_gap_reason=odds_gap_reason,
        prediction_candidates=prediction_candidates,
        odds_candidates=odds_candidates,
        scanned_paths=[os.path.join(repo_root, p) for p in paths],
        paper_only=PAPER_ONLY,
        production_ready=PRODUCTION_READY,
    )
