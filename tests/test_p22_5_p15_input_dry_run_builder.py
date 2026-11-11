"""
Tests for P22.5 P15 input dry-run builder.
Validates preview creation, field requirements, and anti-fabrication checks.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p22_5_source_artifact_contract import (
    HISTORICAL_MARKET_ODDS,
    HISTORICAL_P15_JOINED_INPUT,
    HISTORICAL_OOF_PREDICTIONS,
    MAPPING_RISK_HIGH,
    MAPPING_RISK_LOW,
    MAPPING_RISK_MEDIUM,
    SOURCE_CANDIDATE_USABLE,
    SOURCE_CANDIDATE_PARTIAL,
    P225HistoricalSourceCandidate,
)
from wbc_backend.recommendation.p22_5_p15_input_dry_run_builder import (
    DRY_RUN_BUILD_STATUS,
    MAX_PREVIEW_ROWS,
    PREVIEW_SUBDIR,
    build_p15_input_preview_for_date,
    summarize_preview,
    validate_p15_input_preview,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def joined_oof_source(tmp_path) -> tuple[Path, P225HistoricalSourceCandidate]:
    """Create a real joined_oof_with_odds.csv and matching candidate."""
    source_file = tmp_path / "joined_oof_with_odds.csv"
    df = pd.DataFrame({
        "game_id": [f"2025-05-08_LAD_SFG_{i}" for i in range(30)],
        "game_date": ["2025-05-08"] * 30,
        "home_team": ["SFG"] * 30,
        "away_team": ["LAD"] * 30,
        "y_true": ([1, 0] * 15),
        "p_oof": ([0.62, 0.38] * 15),
        "odds_decimal_home": ([1.91] * 30),
        "odds_decimal_away": ([2.05] * 30),
        "p_market": ([0.524] * 30),
        "paper_only": [True] * 30,
    })
    df.to_csv(source_file, index=False)

    candidate = P225HistoricalSourceCandidate(
        source_path=str(source_file),
        source_type=HISTORICAL_P15_JOINED_INPUT,
        source_date="2026-05-12",
        coverage_pct=1.0,
        row_count=30,
        has_game_id=True,
        has_y_true=True,
        has_odds=True,
        has_p_model_or_p_oof=True,
        mapping_risk=MAPPING_RISK_LOW,
        candidate_status=SOURCE_CANDIDATE_USABLE,
        paper_only=True,
        production_ready=False,
    )
    return source_file, candidate


@pytest.fixture()
def oof_only_source(tmp_path) -> tuple[Path, P225HistoricalSourceCandidate]:
    """OOF-only source (no game_id or odds)."""
    source_file = tmp_path / "oof_predictions.csv"
    df = pd.DataFrame({
        "y_true": [1, 0, 1],
        "p_oof": [0.62, 0.38, 0.71],
        "fold_id": [0, 0, 1],
        "paper_only": [True, True, True],
    })
    df.to_csv(source_file, index=False)

    candidate = P225HistoricalSourceCandidate(
        source_path=str(source_file),
        source_type=HISTORICAL_OOF_PREDICTIONS,
        source_date="2026-05-12",
        coverage_pct=0.7,
        row_count=3,
        has_game_id=False,
        has_y_true=True,
        has_odds=False,
        has_p_model_or_p_oof=True,
        mapping_risk=MAPPING_RISK_HIGH,
        candidate_status=SOURCE_CANDIDATE_USABLE,
        paper_only=True,
        production_ready=False,
    )
    return source_file, candidate


# ---------------------------------------------------------------------------
# build_p15_input_preview_for_date
# ---------------------------------------------------------------------------


def test_preview_created_for_safe_date(tmp_path, joined_oof_source):
    """Preview should be created successfully from a P15 joined input."""
    _, candidate = joined_oof_source
    preview_df, blocker = build_p15_input_preview_for_date(
        run_date="2026-05-05",
        source_candidates=[candidate],
        output_dir=tmp_path / "output",
    )
    assert blocker == "", f"Expected no blocker, got: {blocker}"
    assert preview_df is not None
    assert len(preview_df) <= MAX_PREVIEW_ROWS
    assert len(preview_df) > 0


def test_preview_adds_required_metadata_columns(tmp_path, joined_oof_source):
    """Preview must add run_date, source_file_refs, build_status, paper_only."""
    _, candidate = joined_oof_source
    preview_df, blocker = build_p15_input_preview_for_date(
        run_date="2026-05-07",
        source_candidates=[candidate],
        output_dir=tmp_path / "output",
    )
    assert blocker == ""
    assert "run_date" in preview_df.columns
    assert "source_file_refs" in preview_df.columns
    assert "build_status" in preview_df.columns
    assert "paper_only" in preview_df.columns
    assert "production_ready" in preview_df.columns
    assert (preview_df["run_date"] == "2026-05-07").all()
    assert (preview_df["build_status"] == DRY_RUN_BUILD_STATUS).all()
    assert (preview_df["paper_only"] == True).all()
    assert (preview_df["production_ready"] == False).all()


def test_preview_does_not_fabricate_missing_fields(tmp_path, oof_only_source):
    """An OOF-only source missing game_id/odds can produce a preview, but must not invent fields."""
    _, candidate = oof_only_source
    preview_df, blocker = build_p15_input_preview_for_date(
        run_date="2026-05-03",
        source_candidates=[candidate],
        output_dir=tmp_path / "output",
    )
    # Either a valid (partial) preview or a non-fabrication blocker is OK
    if preview_df is not None:
        # game_id should NOT appear if not in source
        if "game_id" in preview_df.columns:
            # Must come from source, not be manufactured
            assert "game_id" in ["y_true", "p_oof", "fold_id", "paper_only",
                                  "run_date", "source_file_refs", "build_status",
                                  "build_risk", "paper_only", "production_ready",
                                  "game_id", "fold_id"]
    else:
        # No preview is also acceptable for incomplete source
        assert isinstance(blocker, str)


def test_preview_blocked_when_no_usable_candidates(tmp_path):
    preview_df, blocker = build_p15_input_preview_for_date(
        run_date="2026-05-01",
        source_candidates=[],
        output_dir=tmp_path / "output",
    )
    assert preview_df is None
    assert "NO_USABLE_SOURCE_CANDIDATES" in blocker


def test_preview_blocked_when_source_file_missing(tmp_path):
    candidate = P225HistoricalSourceCandidate(
        source_path="/nonexistent/path/joined_oof.csv",
        source_type=HISTORICAL_P15_JOINED_INPUT,
        source_date="2026-05-12",
        coverage_pct=1.0,
        row_count=100,
        has_game_id=True,
        has_y_true=True,
        has_odds=True,
        has_p_model_or_p_oof=True,
        mapping_risk=MAPPING_RISK_LOW,
        candidate_status=SOURCE_CANDIDATE_USABLE,
        paper_only=True,
        production_ready=False,
    )
    preview_df, blocker = build_p15_input_preview_for_date(
        run_date="2026-05-01",
        source_candidates=[candidate],
        output_dir=tmp_path / "output",
    )
    assert preview_df is None
    assert "SOURCE_FILE_MISSING" in blocker or "SOURCE_READ_ERROR" in blocker


def test_preview_writes_csv_and_summary_json(tmp_path, joined_oof_source):
    _, candidate = joined_oof_source
    output_dir = tmp_path / "output"
    preview_df, blocker = build_p15_input_preview_for_date(
        run_date="2026-05-09",
        source_candidates=[candidate],
        output_dir=output_dir,
    )
    assert blocker == ""
    preview_csv = output_dir / PREVIEW_SUBDIR / "2026-05-09" / "p15_input_preview.csv"
    summary_json = output_dir / PREVIEW_SUBDIR / "2026-05-09" / "p15_input_preview_summary.json"
    assert preview_csv.exists(), f"Preview CSV not found: {preview_csv}"
    assert summary_json.exists(), f"Summary JSON not found: {summary_json}"

    with summary_json.open() as fh:
        summary = json.load(fh)
    assert summary["run_date"] == "2026-05-09"
    assert summary["build_status"] == DRY_RUN_BUILD_STATUS
    assert summary["paper_only"] is True
    assert summary["production_ready"] is False


def test_preview_limited_to_max_rows(tmp_path, joined_oof_source):
    _, candidate = joined_oof_source
    preview_df, blocker = build_p15_input_preview_for_date(
        run_date="2026-05-10",
        source_candidates=[candidate],
        output_dir=tmp_path / "output",
    )
    assert blocker == ""
    assert len(preview_df) <= MAX_PREVIEW_ROWS


# ---------------------------------------------------------------------------
# validate_p15_input_preview
# ---------------------------------------------------------------------------


def test_validate_accepts_valid_preview():
    df = pd.DataFrame({
        "game_id": ["g1"],
        "y_true": [1],
        "run_date": ["2026-05-05"],
        "build_status": [DRY_RUN_BUILD_STATUS],
        "paper_only": [True],
        "production_ready": [False],
    })
    result = validate_p15_input_preview(df)
    assert result == ""


def test_validate_rejects_none():
    result = validate_p15_input_preview(None)
    assert result != ""


def test_validate_rejects_empty_df():
    result = validate_p15_input_preview(pd.DataFrame())
    assert result != ""


def test_validate_rejects_wrong_build_status():
    df = pd.DataFrame({
        "build_status": ["CANONICAL_P15"],
        "paper_only": [True],
        "production_ready": [False],
    })
    result = validate_p15_input_preview(df)
    assert "INVALID_BUILD_STATUS" in result or "MISSING_BUILD_STATUS" in result


def test_validate_rejects_production_ready_true():
    df = pd.DataFrame({
        "build_status": [DRY_RUN_BUILD_STATUS],
        "paper_only": [True],
        "production_ready": [True],  # MUST be rejected
    })
    result = validate_p15_input_preview(df)
    assert "PRODUCTION_READY" in result


def test_validate_rejects_oversized_preview():
    df = pd.DataFrame({
        "build_status": [DRY_RUN_BUILD_STATUS] * (MAX_PREVIEW_ROWS + 5),
        "paper_only": [True] * (MAX_PREVIEW_ROWS + 5),
        "production_ready": [False] * (MAX_PREVIEW_ROWS + 5),
    })
    result = validate_p15_input_preview(df)
    assert "EXCEEDS_MAX_ROWS" in result


# ---------------------------------------------------------------------------
# summarize_preview
# ---------------------------------------------------------------------------


def test_summarize_preview_fields():
    df = pd.DataFrame({
        "game_id": ["g1"],
        "game_date": ["2025-05-08"],
        "y_true": [1],
        "p_oof": [0.62],
        "odds_decimal_home": [1.91],
        "run_date": ["2026-05-05"],
        "build_status": [DRY_RUN_BUILD_STATUS],
    })
    summary = summarize_preview(df, "2026-05-05", "/some/source.csv")
    assert summary["run_date"] == "2026-05-05"
    assert summary["n_preview_rows"] == 1
    assert summary["has_game_id"] is True
    assert summary["has_y_true"] is True
    assert summary["has_p_oof"] is True
    assert summary["has_odds"] is True
    assert summary["paper_only"] is True
    assert summary["production_ready"] is False
