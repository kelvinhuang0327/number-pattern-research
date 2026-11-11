"""
tests/test_p29_source_coverage_expansion_scanner.py

Unit tests for P29 source coverage expansion scanner.
"""
import textwrap
from pathlib import Path
from typing import List

import pandas as pd
import pytest

from wbc_backend.recommendation.p29_density_expansion_contract import P29SourceCoverageCandidate
from wbc_backend.recommendation.p29_source_coverage_expansion_scanner import (
    _has_game_id,
    _has_odds,
    _has_required_columns,
    _has_y_true,
    build_source_coverage_candidates,
    detect_other_seasons_or_ranges,
    estimate_sample_gain_from_source_expansion,
    scan_additional_true_date_sources,
    summarize_source_expansion_options,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_P25_CSV = textwrap.dedent("""\
    edge,odds_decimal,y_true,gate_reason,paper_stake_units,game_id,date
    0.07,2.10,1.0,P16_6_ELIGIBLE_PAPER_RECOMMENDATION,0.007,g1,2025-05-08
    0.02,2.20,0.0,P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD,0.0,g2,2025-05-08
""")

_INCOMPLETE_CSV = textwrap.dedent("""\
    Date,Away,Home,Away Score,Home Score,Away ML,Home ML
    2025-05-08,NYY,BOS,3,2,1.90,2.10
""")


@pytest.fixture
def tmp_p25_with_extra_ranges(tmp_path: Path) -> tuple[Path, Path]:
    """Create a main p25 dir and an additional p25 range."""
    backfill = tmp_path / "outputs" / "predictions" / "PAPER" / "backfill"
    backfill.mkdir(parents=True)

    # Primary p25 dir (same range as main)
    main_p25 = backfill / "p25_true_date_source_separation_2025-05-08_2025-09-28"
    slices_main = main_p25 / "true_date_slices" / "2025-05-08"
    slices_main.mkdir(parents=True)
    (slices_main / "p15_true_date_input.csv").write_text(_REQUIRED_P25_CSV)

    # Additional p25 with shorter range (subset)
    other_p25 = backfill / "p25_true_date_source_separation_2025-05-08_2025-05-14"
    slices_other = other_p25 / "true_date_slices" / "2025-05-08"
    slices_other.mkdir(parents=True)
    (slices_other / "p15_true_date_input.csv").write_text(_REQUIRED_P25_CSV)

    return main_p25, tmp_path / "outputs"


# ---------------------------------------------------------------------------
# Column detection helpers
# ---------------------------------------------------------------------------


def test_has_required_columns_positive() -> None:
    cols = ["edge", "odds_decimal", "y_true", "gate_reason", "paper_stake_units"]
    assert _has_required_columns(cols) is True


def test_has_required_columns_negative() -> None:
    cols = ["Date", "Away", "Home", "Away ML"]
    assert _has_required_columns(cols) is False


def test_has_y_true() -> None:
    assert _has_y_true(["y_true", "edge"]) is True
    assert _has_y_true(["outcome", "edge"]) is False


def test_has_game_id() -> None:
    assert _has_game_id(["game_id", "date"]) is True
    assert _has_game_id(["Date", "Away"]) is True  # alternate column name
    assert _has_game_id(["foo", "bar"]) is False


def test_has_odds() -> None:
    assert _has_odds(["odds_decimal"]) is True
    assert _has_odds(["Away ML"]) is True
    assert _has_odds(["foo"]) is False


# ---------------------------------------------------------------------------
# scan_additional_true_date_sources
# ---------------------------------------------------------------------------


def test_scan_finds_alternative_p25(tmp_p25_with_extra_ranges: tuple[Path, Path]) -> None:
    main_p25, outputs_dir = tmp_p25_with_extra_ranges
    candidates = scan_additional_true_date_sources(
        [outputs_dir], current_p25_dir=main_p25
    )
    # Should find the other p25 range (not the main one)
    source_paths = [c["source_path"] for c in candidates]
    assert any("2025-05-08_2025-05-14" in p for p in source_paths)
    # Should NOT include the main p25
    assert not any("2025-05-08_2025-09-28" in p for p in source_paths)


def test_scan_empty_base_paths() -> None:
    candidates = scan_additional_true_date_sources([], current_p25_dir=None)
    assert candidates == []


def test_scan_nonexistent_base() -> None:
    candidates = scan_additional_true_date_sources(
        [Path("/nonexistent/path/xyz")], current_p25_dir=None
    )
    assert candidates == []


def test_scan_data_dir_with_csv(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "mlb_odds.csv").write_text(_INCOMPLETE_CSV)
    candidates = scan_additional_true_date_sources([data_dir])
    assert any(c["source_path"].endswith("mlb_odds.csv") for c in candidates)


# ---------------------------------------------------------------------------
# detect_other_seasons_or_ranges
# ---------------------------------------------------------------------------


def test_detect_other_seasons_empty() -> None:
    result = detect_other_seasons_or_ranges([])
    assert result == []


def test_detect_other_seasons_filters_correctly() -> None:
    candidates = [
        {
            "source_path": "/data/mlb_2024.csv",
            "source_type": "additional_season",
            "estimated_new_rows": 500,
        },
        {
            "source_path": "/outputs/p25_old",
            "source_type": "wider_date_range",
            "estimated_new_rows": 0,
        },
    ]
    result = detect_other_seasons_or_ranges(candidates)
    assert len(result) == 1
    assert result[0]["source_type"] == "additional_season"


# ---------------------------------------------------------------------------
# summarize_source_expansion_options
# ---------------------------------------------------------------------------


def test_summarize_empty_candidates() -> None:
    summary = summarize_source_expansion_options([])
    assert summary["n_candidates_scanned"] == 0
    assert summary["n_candidates_safe"] == 0
    assert summary["source_expansion_feasible"] is False


def test_summarize_unsafe_candidates() -> None:
    candidates = [
        {
            "source_path": "/some/path",
            "source_type": "additional_season",
            "estimated_new_rows": 0,
            "has_required_columns": False,
            "is_safe_to_use": False,
        }
    ]
    summary = summarize_source_expansion_options(candidates)
    assert summary["n_candidates_safe"] == 0
    assert summary["source_expansion_feasible"] is False
    assert "recommendation" in summary


# ---------------------------------------------------------------------------
# estimate_sample_gain_from_source_expansion
# ---------------------------------------------------------------------------


def test_estimate_sample_gain_empty() -> None:
    result = estimate_sample_gain_from_source_expansion([])
    assert result["estimated_new_rows_safe"] == 0
    assert result["estimated_new_active_entries_safe"] == 0


def test_estimate_sample_gain_with_safe_source() -> None:
    candidates = [
        {
            "source_path": "/data/safe.csv",
            "source_type": "additional_season",
            "estimated_new_rows": 1000,
            "is_safe_to_use": True,
            "has_required_columns": True,
        }
    ]
    result = estimate_sample_gain_from_source_expansion(candidates)
    assert result["estimated_new_rows_safe"] == 1000
    assert result["estimated_new_active_entries_safe"] == int(1000 * 0.205)


# ---------------------------------------------------------------------------
# build_source_coverage_candidates
# ---------------------------------------------------------------------------


def test_build_source_coverage_candidates_empty() -> None:
    result = build_source_coverage_candidates([])
    assert result == []


def test_build_source_coverage_candidates_basic() -> None:
    raw = [
        {
            "source_path": "/some/path.csv",
            "source_type": "alternate_odds",
            "date_range_start": "",
            "date_range_end": "",
            "estimated_new_rows": 0,
            "has_required_columns": False,
            "has_y_true": False,
            "has_game_id": False,
            "has_odds": True,
            "coverage_note": "Test",
            "is_safe_to_use": False,
        }
    ]
    result = build_source_coverage_candidates(raw)
    assert len(result) == 1
    assert isinstance(result[0], P29SourceCoverageCandidate)
    assert result[0].paper_only is True
    assert result[0].production_ready is False
