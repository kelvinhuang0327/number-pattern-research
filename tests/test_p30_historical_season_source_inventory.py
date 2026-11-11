"""
tests/test_p30_historical_season_source_inventory.py

Unit tests for P30 historical season source inventory scanner.
"""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from typing import List

import pandas as pd
import pytest

from wbc_backend.recommendation.p30_historical_season_source_inventory import (
    classify_source_by_season,
    estimate_games_and_dates,
    inspect_schema_coverage,
    scan_existing_season_sources,
    summarize_existing_source_inventory,
)
from wbc_backend.recommendation.p30_source_acquisition_contract import (
    SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
    SOURCE_PLAN_PARTIAL,
    SOURCE_PLAN_READY,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_csv(path: Path, columns: List[str], rows: int = 20) -> None:
    """Write a dummy CSV with given columns and N rows."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for i in range(rows):
            writer.writerow({col: f"val_{i}" for col in columns})


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temp dir with various CSV files."""
    return tmp_path


@pytest.fixture
def complete_source_csv(tmp_data_dir):
    """CSV with all required columns."""
    path = tmp_data_dir / "mlb_2024_complete.csv"
    _write_csv(
        path,
        columns=["game_id", "game_date", "home_team", "away_team", "y_true",
                 "p_model", "p_market", "odds_decimal"],
        rows=50,
    )
    return path


@pytest.fixture
def partial_source_csv_no_predictions(tmp_data_dir):
    """CSV missing model predictions."""
    path = tmp_data_dir / "mlb_2024_no_preds.csv"
    _write_csv(
        path,
        columns=["Date", "Away", "Home", "Away Score", "Home Score",
                 "Away ML", "Home ML"],
        rows=30,
    )
    return path


@pytest.fixture
def partial_source_csv_no_odds(tmp_data_dir):
    """CSV missing odds columns."""
    path = tmp_data_dir / "mlb_2025_no_odds.csv"
    _write_csv(
        path,
        columns=["game_id", "game_date", "home_team", "away_team", "y_true", "p_model"],
        rows=25,
    )
    return path


# ---------------------------------------------------------------------------
# scan_existing_season_sources
# ---------------------------------------------------------------------------


def test_scan_finds_csv_files(tmp_data_dir, complete_source_csv):
    results = scan_existing_season_sources([tmp_data_dir])
    paths = [r["path"] for r in results]
    assert str(complete_source_csv) in paths


def test_scan_returns_list(tmp_data_dir, complete_source_csv):
    results = scan_existing_season_sources([tmp_data_dir])
    assert isinstance(results, list)


def test_scan_returns_empty_for_nonexistent_path():
    results = scan_existing_season_sources([Path("/nonexistent_path_xyz_abc")])
    assert results == []


def test_scan_finds_multiple_files(tmp_data_dir, complete_source_csv, partial_source_csv_no_predictions):
    results = scan_existing_season_sources([tmp_data_dir])
    assert len(results) >= 2


def test_scan_result_has_required_fields(tmp_data_dir, complete_source_csv):
    results = scan_existing_season_sources([tmp_data_dir])
    r = results[0]
    assert "path" in r
    assert "source_status" in r
    assert "schema_coverage" in r
    assert "paper_only" in r
    assert r["paper_only"] is True
    assert r["production_ready"] is False


# ---------------------------------------------------------------------------
# classify_source_by_season
# ---------------------------------------------------------------------------


def test_classify_season_2024():
    c = {"path": "/data/mlb_2024/odds.csv", "target_season": "UNKNOWN"}
    assert classify_source_by_season(c) == "2024"


def test_classify_season_2025():
    c = {"path": "/data/mlb_2025/odds.csv", "target_season": "UNKNOWN"}
    assert classify_source_by_season(c) == "2025"


def test_classify_season_2026():
    c = {"path": "/data/mlb_2026_draft.csv", "target_season": "UNKNOWN"}
    assert classify_source_by_season(c) == "2026"


def test_classify_season_unknown():
    c = {"path": "/data/some_file.csv", "target_season": "UNKNOWN"}
    assert classify_source_by_season(c) == "UNKNOWN"


def test_classify_season_uses_explicit_if_set():
    c = {"path": "/data/mlb_2024/odds.csv", "target_season": "2025"}
    assert classify_source_by_season(c) == "2025"


# ---------------------------------------------------------------------------
# inspect_schema_coverage
# ---------------------------------------------------------------------------


def test_inspect_schema_complete_source(complete_source_csv):
    result = inspect_schema_coverage(complete_source_csv)
    assert result["readable"] is True
    assert result["has_game_id"] is True
    assert result["has_game_date"] is True
    assert result["has_y_true"] is True
    assert result["has_p_model"] is True
    assert result["has_p_market"] is True
    assert result["has_odds_decimal"] is True
    assert result["schema_coverage"] == "FULL"


def test_inspect_schema_partial_no_predictions(partial_source_csv_no_predictions):
    result = inspect_schema_coverage(partial_source_csv_no_predictions)
    assert result["readable"] is True
    assert result["has_p_model"] is False
    assert result["schema_coverage"] in ("PARTIAL", "MINIMAL")


def test_inspect_schema_no_odds(partial_source_csv_no_odds):
    result = inspect_schema_coverage(partial_source_csv_no_odds)
    assert result["readable"] is True
    assert result["has_odds_decimal"] is False


def test_inspect_schema_nonexistent_file():
    result = inspect_schema_coverage(Path("/nonexistent/file.csv"))
    assert result["readable"] is False
    assert result["has_game_id"] is False


def test_inspect_schema_returns_row_count(complete_source_csv):
    result = inspect_schema_coverage(complete_source_csv)
    assert result["row_count"] == 50


# ---------------------------------------------------------------------------
# estimate_games_and_dates
# ---------------------------------------------------------------------------


def test_estimate_games_complete_source(complete_source_csv):
    result = estimate_games_and_dates(complete_source_csv)
    assert result["estimated_rows"] == 50
    assert result["estimated_games"] == 50


def test_estimate_games_returns_dict(complete_source_csv):
    result = estimate_games_and_dates(complete_source_csv)
    assert "estimated_rows" in result
    assert "estimated_games" in result
    assert "date_start" in result
    assert "date_end" in result


# ---------------------------------------------------------------------------
# summarize_existing_source_inventory
# ---------------------------------------------------------------------------


def test_summarize_empty_inventory():
    result = summarize_existing_source_inventory([])
    assert result["n_candidates_scanned"] == 0
    assert result["n_ready"] == 0
    assert result["n_partial"] == 0
    assert result["acquisition_feasible"] is False


def test_summarize_with_candidates(tmp_data_dir, complete_source_csv, partial_source_csv_no_predictions):
    inventory = scan_existing_season_sources([tmp_data_dir])
    result = summarize_existing_source_inventory(inventory)
    assert result["n_candidates_scanned"] >= 2
    assert isinstance(result["seasons_found"], list)


def test_summarize_detects_2025(tmp_data_dir, partial_source_csv_no_odds):
    inventory = scan_existing_season_sources([tmp_data_dir])
    result = summarize_existing_source_inventory(inventory)
    assert result["has_2025_source"] is True


# ---------------------------------------------------------------------------
# Source status classification
# ---------------------------------------------------------------------------


def test_complete_source_classified_as_ready(complete_source_csv):
    result = inspect_schema_coverage(complete_source_csv)
    assert result["schema_coverage"] == "FULL"
    # scan should produce READY status for full coverage
    from wbc_backend.recommendation.p30_historical_season_source_inventory import (
        _determine_source_status,
    )
    status, _ = _determine_source_status(
        columns=result["columns"],
        row_count=50,
        has_game_date=result["has_game_date"],
        has_y_true=result["has_y_true"],
        has_p_model=result["has_p_model"],
        has_p_market=result["has_p_market"],
        has_odds=result["has_odds_decimal"],
        schema_coverage=result["schema_coverage"],
    )
    assert status == SOURCE_PLAN_READY


def test_missing_odds_classified_as_partial(partial_source_csv_no_odds):
    result = inspect_schema_coverage(partial_source_csv_no_odds)
    from wbc_backend.recommendation.p30_historical_season_source_inventory import (
        _determine_source_status,
    )
    status, note = _determine_source_status(
        columns=result["columns"],
        row_count=25,
        has_game_date=result["has_game_date"],
        has_y_true=result["has_y_true"],
        has_p_model=result["has_p_model"],
        has_p_market=result["has_p_market"],
        has_odds=result["has_odds_decimal"],
        schema_coverage=result["schema_coverage"],
    )
    assert status == SOURCE_PLAN_PARTIAL
    assert "odds_decimal" in note.lower() or "partial" in note.lower()


def test_missing_predictions_classified_as_partial(partial_source_csv_no_predictions):
    result = inspect_schema_coverage(partial_source_csv_no_predictions)
    from wbc_backend.recommendation.p30_historical_season_source_inventory import (
        _determine_source_status,
    )
    status, note = _determine_source_status(
        columns=result["columns"],
        row_count=30,
        has_game_date=result["has_game_date"],
        has_y_true=result["has_y_true"],
        has_p_model=result["has_p_model"],
        has_p_market=result["has_p_market"],
        has_odds=result["has_odds_decimal"],
        schema_coverage=result["schema_coverage"],
    )
    assert status == SOURCE_PLAN_PARTIAL
