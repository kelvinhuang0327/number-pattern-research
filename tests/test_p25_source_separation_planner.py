"""
tests/test_p25_source_separation_planner.py

Tests for the P25 source separation planner.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p25_true_date_source_contract import (
    TRUE_DATE_SLICE_EMPTY,
    TRUE_DATE_SLICE_READY,
    P25SourceSeparationSummary,
)
from wbc_backend.recommendation.p25_source_separation_planner import (
    _date_range,
    build_true_date_separation_plan,
    classify_date_slice_availability,
    generate_next_backfill_commands,
    summarize_true_date_separation_results,
    validate_source_separation_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _full_row(game_id: str = "G001", game_date: str = "2025-05-08") -> dict:
    return {
        "game_id": game_id,
        "game_date": game_date,
        "y_true": 1,
        "p_oof": 0.62,
        "p_market": 0.55,
        "odds_decimal_home": 1.85,
        "odds_decimal_away": 2.10,
        "edge": 0.07,
    }


def _make_source_csv(tmp_path: Path, name: str, rows: list[dict]) -> Path:
    p = tmp_path / name
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


# ---------------------------------------------------------------------------
# _date_range
# ---------------------------------------------------------------------------


def test_date_range_inclusive():
    result = _date_range("2025-05-08", "2025-05-10")
    assert result == ["2025-05-08", "2025-05-09", "2025-05-10"]


def test_date_range_single():
    result = _date_range("2025-05-08", "2025-05-08")
    assert result == ["2025-05-08"]


def test_date_range_empty_when_end_before_start():
    result = _date_range("2025-05-10", "2025-05-08")
    assert result == []


# ---------------------------------------------------------------------------
# build_true_date_separation_plan
# ---------------------------------------------------------------------------


def test_plan_returns_ready_for_matching_date(tmp_path):
    rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-08")]
    src = _make_source_csv(tmp_path, "source.csv", rows)

    results = build_true_date_separation_plan("2025-05-08", "2025-05-08", [src])
    assert len(results) == 1
    assert results[0]["run_date"] == "2025-05-08"
    assert results[0]["status"] == TRUE_DATE_SLICE_READY
    assert results[0]["n_rows"] == 2


def test_plan_returns_empty_for_no_rows_on_date(tmp_path):
    rows = [_full_row("G001", "2025-05-08")]
    src = _make_source_csv(tmp_path, "source.csv", rows)

    results = build_true_date_separation_plan("2026-05-01", "2026-05-01", [src])
    assert len(results) == 1
    assert results[0]["status"] == TRUE_DATE_SLICE_EMPTY
    assert results[0]["n_rows"] == 0


def test_plan_does_not_use_run_date_to_match(tmp_path):
    """Requesting 2026-05-01 should not match rows with game_date=2025-05-08."""
    rows = [
        {
            "game_id": "G001",
            "game_date": "2025-05-08",
            "run_date": "2026-05-01",
            "y_true": 1,
            "p_oof": 0.6,
            "p_market": 0.5,
            "odds_decimal_home": 1.9,
        }
    ]
    src = _make_source_csv(tmp_path, "source.csv", rows)

    results = build_true_date_separation_plan("2026-05-01", "2026-05-01", [src])
    assert results[0]["status"] == TRUE_DATE_SLICE_EMPTY, (
        "run_date column must not be used to match — game_date is 2025, not 2026"
    )


def test_plan_handles_multiple_dates(tmp_path):
    rows = [
        _full_row("G001", "2025-05-08"),
        _full_row("G002", "2025-05-09"),
        _full_row("G003", "2025-05-10"),
    ]
    src = _make_source_csv(tmp_path, "source.csv", rows)

    results = build_true_date_separation_plan("2025-05-08", "2025-05-10", [src])
    assert len(results) == 3
    ready = [r for r in results if r["status"] == TRUE_DATE_SLICE_READY]
    assert len(ready) == 3


def test_plan_handles_no_candidates():
    results = build_true_date_separation_plan("2026-05-01", "2026-05-01", [])
    assert len(results) == 1
    assert results[0]["status"] == TRUE_DATE_SLICE_EMPTY


# ---------------------------------------------------------------------------
# classify_date_slice_availability
# ---------------------------------------------------------------------------


def test_classify_ready():
    assert classify_date_slice_availability({"status": TRUE_DATE_SLICE_READY}) == "READY"


def test_classify_empty():
    assert classify_date_slice_availability({"status": TRUE_DATE_SLICE_EMPTY}) == "EMPTY"


def test_classify_blocked_missing_cols():
    from wbc_backend.recommendation.p25_true_date_source_contract import (
        TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
    )
    r = {"status": TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS}
    assert classify_date_slice_availability(r) == "BLOCKED"


# ---------------------------------------------------------------------------
# summarize_true_date_separation_results
# ---------------------------------------------------------------------------


def test_summary_all_empty(tmp_path):
    """If requested range has no true rows, n_true_date_ready == 0."""
    rows = [_full_row("G001", "2025-05-08")]
    src = _make_source_csv(tmp_path, "source.csv", rows)

    results = build_true_date_separation_plan("2026-05-01", "2026-05-03", [src])
    summary = summarize_true_date_separation_results(
        results, "2026-05-01", "2026-05-03", [src]
    )
    assert summary.n_true_date_ready == 0
    assert summary.n_empty_dates == 3
    assert summary.paper_only is True
    assert summary.production_ready is False


def test_summary_some_ready(tmp_path):
    rows = [
        _full_row("G001", "2025-05-08"),
        _full_row("G002", "2025-05-09"),
    ]
    src = _make_source_csv(tmp_path, "source.csv", rows)

    results = build_true_date_separation_plan("2025-05-08", "2025-05-09", [src])
    summary = summarize_true_date_separation_results(
        results, "2025-05-08", "2025-05-09", [src]
    )
    assert summary.n_true_date_ready == 2
    assert summary.n_empty_dates == 0


def test_summary_detects_source_game_date_range(tmp_path):
    """Even when requested range yields empty, detected source range should be reported."""
    rows = [_full_row("G001", "2025-05-08")]
    src = _make_source_csv(tmp_path, "source.csv", rows)

    results = build_true_date_separation_plan("2026-05-01", "2026-05-01", [src])
    summary = summarize_true_date_separation_results(
        results, "2026-05-01", "2026-05-01", [src]
    )
    assert summary.detected_source_game_date_min == "2025-05-08"
    assert summary.detected_source_game_date_max == "2025-05-08"


def test_summary_recommends_true_source_range_when_requested_is_empty(tmp_path):
    """When requested range returns no ready rows, recommend detected source range."""
    rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-09")]
    src = _make_source_csv(tmp_path, "source.csv", rows)

    results = build_true_date_separation_plan("2026-05-01", "2026-05-02", [src])
    summary = summarize_true_date_separation_results(
        results, "2026-05-01", "2026-05-02", [src]
    )
    assert summary.recommended_backfill_date_start == "2025-05-08"
    assert summary.recommended_backfill_date_end == "2025-05-09"


# ---------------------------------------------------------------------------
# validate_source_separation_summary
# ---------------------------------------------------------------------------


def test_validate_summary_valid():
    s = P25SourceSeparationSummary(
        date_start="2026-05-01",
        date_end="2026-05-03",
        n_dates_requested=3,
        n_true_date_ready=0,
        n_empty_dates=3,
        n_partial_dates=0,
        n_blocked_dates=0,
        detected_source_game_date_min="2025-05-08",
        detected_source_game_date_max="2025-09-28",
        recommended_backfill_date_start="2025-05-08",
        recommended_backfill_date_end="2025-09-28",
        source_files_scanned=1,
        paper_only=True,
        production_ready=False,
    )
    assert validate_source_separation_summary(s) is True


def test_validate_summary_fails_count_mismatch():
    s = P25SourceSeparationSummary(
        date_start="2026-05-01",
        date_end="2026-05-03",
        n_dates_requested=3,
        n_true_date_ready=1,  # total = 1+1+0+0 = 2, but requested = 3
        n_empty_dates=1,
        n_partial_dates=0,
        n_blocked_dates=0,
        detected_source_game_date_min="",
        detected_source_game_date_max="",
        recommended_backfill_date_start="",
        recommended_backfill_date_end="",
        source_files_scanned=0,
        paper_only=True,
        production_ready=False,
    )
    assert validate_source_separation_summary(s) is False


# ---------------------------------------------------------------------------
# generate_next_backfill_commands
# ---------------------------------------------------------------------------


def test_generate_commands_when_empty_range_recommends_true_range():
    s = P25SourceSeparationSummary(
        date_start="2026-05-01",
        date_end="2026-05-12",
        n_dates_requested=12,
        n_true_date_ready=0,
        n_empty_dates=12,
        n_partial_dates=0,
        n_blocked_dates=0,
        detected_source_game_date_min="2025-05-08",
        detected_source_game_date_max="2025-09-28",
        recommended_backfill_date_start="2025-05-08",
        recommended_backfill_date_end="2025-09-28",
        source_files_scanned=1,
        paper_only=True,
        production_ready=False,
    )
    cmds = generate_next_backfill_commands(s)
    assert len(cmds) > 0
    joined = "\n".join(cmds)
    assert "2025-05-08" in joined
    assert "2025-09-28" in joined


def test_generate_commands_when_ready_recommends_p26():
    s = P25SourceSeparationSummary(
        date_start="2025-05-08",
        date_end="2025-05-14",
        n_dates_requested=7,
        n_true_date_ready=7,
        n_empty_dates=0,
        n_partial_dates=0,
        n_blocked_dates=0,
        detected_source_game_date_min="2025-05-08",
        detected_source_game_date_max="2025-05-14",
        recommended_backfill_date_start="2025-05-08",
        recommended_backfill_date_end="2025-05-14",
        source_files_scanned=1,
        paper_only=True,
        production_ready=False,
    )
    cmds = generate_next_backfill_commands(s)
    joined = "\n".join(cmds)
    assert "P26" in joined or "run_p26" in joined or "p26" in joined.lower()
