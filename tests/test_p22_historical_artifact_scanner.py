"""
Tests for P22 historical artifact scanner.

Covers:
- scan_single_paper_date with various fixture structures
- scan_paper_date_range returns exact count of dates
- inspect_phase_artifacts detects existing and missing files
- classify_date_availability logic
- summarize_scan_results counts and gate
- No fabrication of missing artifacts
- P20-ready detection
- Missing directory detection
- Partial source availability
- Replayable detection
- Non-replayable when P20 exists (already ready)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from wbc_backend.recommendation.p22_historical_availability_contract import (
    DATE_BLOCKED_INVALID_ARTIFACTS,
    DATE_MISSING_REQUIRED_SOURCE,
    DATE_PARTIAL_SOURCE_AVAILABLE,
    DATE_READY_P20_EXISTS,
    DATE_READY_REPLAYABLE_FROM_P15_P16_P19,
    EXPECTED_P20_GATE,
    P15_DIR,
    P15_JOINED_OOF_WITH_ODDS,
    P15_SIMULATION_LEDGER,
    P16_6_DIR,
    P16_6_RECOMMENDATION_ROWS,
    P16_6_RECOMMENDATION_SUMMARY,
    P19_DIR,
    P19_ENRICHED_LEDGER,
    P19_GATE_RESULT,
    P20_DIR,
    P22_BLOCKED_NO_AVAILABLE_DATES,
    P22_HISTORICAL_BACKFILL_AVAILABILITY_READY,
)
from wbc_backend.recommendation.p22_historical_artifact_scanner import (
    classify_date_availability,
    inspect_phase_artifacts,
    scan_paper_date_range,
    scan_single_paper_date,
    summarize_scan_results,
)


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


def _write_p20(date_dir: Path, gate_value: str = EXPECTED_P20_GATE) -> None:
    p20_dir = date_dir / P20_DIR
    p20_dir.mkdir(parents=True, exist_ok=True)
    (p20_dir / "daily_paper_summary.json").write_text(
        json.dumps({"n_active": 324}), encoding="utf-8"
    )
    (p20_dir / "p20_gate_result.json").write_text(
        json.dumps({"p20_gate": gate_value}), encoding="utf-8"
    )
    (p20_dir / "artifact_manifest.json").write_text(
        json.dumps({}), encoding="utf-8"
    )


def _write_replay_sources(date_dir: Path) -> None:
    """Write all artifacts needed for a replayable date (no P20)."""
    p15_dir = date_dir / P15_DIR
    p15_dir.mkdir(parents=True, exist_ok=True)
    (p15_dir / "joined_oof_with_odds.csv").write_text("game_id\n1", encoding="utf-8")
    (p15_dir / "simulation_ledger.csv").write_text("game_id\n1", encoding="utf-8")

    p16_dir = date_dir / P16_6_DIR
    p16_dir.mkdir(parents=True, exist_ok=True)
    (p16_dir / "recommendation_rows.csv").write_text("game_id\n1", encoding="utf-8")
    (p16_dir / "recommendation_summary.json").write_text(
        json.dumps({"n_rows": 1}), encoding="utf-8"
    )

    p19_dir = date_dir / P19_DIR
    p19_dir.mkdir(parents=True, exist_ok=True)
    (p19_dir / "enriched_simulation_ledger.csv").write_text(
        "game_id\n1", encoding="utf-8"
    )
    (p19_dir / "p19_gate_result.json").write_text(
        json.dumps({"p19_gate": "P19_ODDS_IDENTITY_JOIN_REPAIR_READY"}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# scan_single_paper_date
# ---------------------------------------------------------------------------


def test_scan_missing_directory(tmp_path: Path) -> None:
    """A nonexistent date dir → DATE_MISSING_REQUIRED_SOURCE."""
    base = tmp_path / "PAPER"
    base.mkdir()
    result = scan_single_paper_date(base, "2026-05-01")
    assert result.run_date == "2026-05-01"
    assert result.availability_status == DATE_MISSING_REQUIRED_SOURCE
    assert result.n_artifacts_found == 0
    assert "not found" in result.error_message.lower() or result.error_message != ""


def test_scan_p20_ready_date(tmp_path: Path) -> None:
    """A date with valid P20 artifacts → DATE_READY_P20_EXISTS."""
    base = tmp_path / "PAPER"
    date_dir = base / "2026-05-12"
    _write_p20(date_dir)

    result = scan_single_paper_date(base, "2026-05-12")
    assert result.run_date == "2026-05-12"
    assert result.availability_status == DATE_READY_P20_EXISTS
    assert result.p20_gate == EXPECTED_P20_GATE
    assert result.paper_only is True
    assert result.production_ready is False


def test_scan_p20_bad_gate_is_blocked(tmp_path: Path) -> None:
    """P20 files present but gate mismatch → DATE_BLOCKED_INVALID_ARTIFACTS."""
    base = tmp_path / "PAPER"
    date_dir = base / "2026-05-12"
    _write_p20(date_dir, gate_value="SOME_OTHER_GATE")

    result = scan_single_paper_date(base, "2026-05-12")
    assert result.availability_status == DATE_BLOCKED_INVALID_ARTIFACTS


def test_scan_replayable_date(tmp_path: Path) -> None:
    """P15+P16.6+P19 all present, P20 absent → DATE_READY_REPLAYABLE_FROM_P15_P16_P19."""
    base = tmp_path / "PAPER"
    date_dir = base / "2026-05-10"
    _write_replay_sources(date_dir)

    result = scan_single_paper_date(base, "2026-05-10")
    assert result.availability_status == DATE_READY_REPLAYABLE_FROM_P15_P16_P19


def test_scan_missing_not_marked_replayable(tmp_path: Path) -> None:
    """Date with NO artifacts → DATE_MISSING_REQUIRED_SOURCE, never replayable."""
    base = tmp_path / "PAPER"
    date_dir = base / "2026-05-05"
    date_dir.mkdir(parents=True)  # empty dir

    result = scan_single_paper_date(base, "2026-05-05")
    assert result.availability_status not in (
        DATE_READY_REPLAYABLE_FROM_P15_P16_P19,
        DATE_READY_P20_EXISTS,
    )


def test_scan_partial_source_available(tmp_path: Path) -> None:
    """Only P15 present (not P16, P19) → DATE_PARTIAL_SOURCE_AVAILABLE."""
    base = tmp_path / "PAPER"
    date_dir = base / "2026-05-08"
    # Write only P15 (missing P16.6, P19)
    p15_dir = date_dir / P15_DIR
    p15_dir.mkdir(parents=True, exist_ok=True)
    (p15_dir / "joined_oof_with_odds.csv").write_text("game_id\n1", encoding="utf-8")

    result = scan_single_paper_date(base, "2026-05-08")
    assert result.availability_status == DATE_PARTIAL_SOURCE_AVAILABLE


def test_scan_does_not_fabricate_artifacts(tmp_path: Path) -> None:
    """When directory doesn't exist, phase_statuses must all have exists=False."""
    base = tmp_path / "PAPER"
    base.mkdir()
    result = scan_single_paper_date(base, "2026-04-01")
    # No phase_statuses should be fabricated for a missing directory
    assert result.phase_statuses == ()
    assert result.availability_status == DATE_MISSING_REQUIRED_SOURCE


# ---------------------------------------------------------------------------
# inspect_phase_artifacts
# ---------------------------------------------------------------------------


def test_inspect_phase_artifacts_all_missing(tmp_path: Path) -> None:
    """An empty date dir → all artifacts marked exists=False."""
    date_dir = tmp_path / "empty_date"
    date_dir.mkdir()
    statuses = inspect_phase_artifacts(date_dir)
    assert len(statuses) == 10
    assert all(not s.exists for s in statuses)


def test_inspect_phase_artifacts_p20_present(tmp_path: Path) -> None:
    """With P20 files written, those artifact keys should be exists=True."""
    date_dir = tmp_path / "date"
    _write_p20(date_dir)
    statuses = inspect_phase_artifacts(date_dir)
    by_key = {s.artifact_key: s for s in statuses}
    from wbc_backend.recommendation.p22_historical_availability_contract import (
        P20_DAILY_SUMMARY,
        P20_GATE_RESULT,
    )
    assert by_key[P20_DAILY_SUMMARY].exists is True
    assert by_key[P20_GATE_RESULT].exists is True


# ---------------------------------------------------------------------------
# scan_paper_date_range
# ---------------------------------------------------------------------------


def test_scan_date_range_exact_count(tmp_path: Path) -> None:
    """scan_paper_date_range returns exactly n dates even when all missing."""
    base = tmp_path / "PAPER"
    base.mkdir()
    results = scan_paper_date_range(base, "2026-05-01", "2026-05-12")
    assert len(results) == 12
    assert results[0].run_date == "2026-05-01"
    assert results[-1].run_date == "2026-05-12"


def test_scan_date_range_single_date(tmp_path: Path) -> None:
    """Single-date range returns 1 result."""
    base = tmp_path / "PAPER"
    date_dir = base / "2026-05-12"
    _write_p20(date_dir)
    results = scan_paper_date_range(base, "2026-05-12", "2026-05-12")
    assert len(results) == 1
    assert results[0].availability_status == DATE_READY_P20_EXISTS


def test_scan_date_range_no_fabrication(tmp_path: Path) -> None:
    """All missing dates must have DATE_MISSING_REQUIRED_SOURCE."""
    base = tmp_path / "PAPER"
    base.mkdir()
    results = scan_paper_date_range(base, "2026-05-01", "2026-05-03")
    assert all(r.availability_status == DATE_MISSING_REQUIRED_SOURCE for r in results)


# ---------------------------------------------------------------------------
# summarize_scan_results
# ---------------------------------------------------------------------------


def test_summarize_counts_p20_ready(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    date_dir = base / "2026-05-12"
    _write_p20(date_dir)
    results = scan_paper_date_range(base, "2026-05-12", "2026-05-12")
    summary = summarize_scan_results(results, "2026-05-12", "2026-05-12")

    assert summary.n_dates_scanned == 1
    assert summary.n_dates_p20_ready == 1
    assert summary.n_dates_missing == 0
    assert summary.n_backfill_candidate_dates == 1
    assert "2026-05-12" in summary.backfill_candidate_dates
    assert summary.p22_gate == P22_HISTORICAL_BACKFILL_AVAILABILITY_READY


def test_summarize_blocked_when_all_missing(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    base.mkdir()
    results = scan_paper_date_range(base, "2026-05-01", "2026-05-03")
    summary = summarize_scan_results(results, "2026-05-01", "2026-05-03")

    assert summary.n_dates_missing == 3
    assert summary.n_backfill_candidate_dates == 0
    assert summary.p22_gate == P22_BLOCKED_NO_AVAILABLE_DATES


def test_summarize_mixed_dates(tmp_path: Path) -> None:
    """1 P20-ready + 1 missing = READY gate, 1 missing reported."""
    base = tmp_path / "PAPER"
    date_dir = base / "2026-05-12"
    _write_p20(date_dir)
    results = scan_paper_date_range(base, "2026-05-11", "2026-05-12")
    summary = summarize_scan_results(results, "2026-05-11", "2026-05-12")

    assert summary.n_dates_scanned == 2
    assert summary.n_dates_p20_ready == 1
    assert summary.n_dates_missing == 1
    assert "2026-05-11" in summary.missing_dates
    assert "2026-05-12" in summary.backfill_candidate_dates
    assert summary.p22_gate == P22_HISTORICAL_BACKFILL_AVAILABILITY_READY


def test_summarize_replayable_date(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    date_dir = base / "2026-05-10"
    _write_replay_sources(date_dir)
    results = scan_paper_date_range(base, "2026-05-10", "2026-05-10")
    summary = summarize_scan_results(results, "2026-05-10", "2026-05-10")

    assert summary.n_dates_replayable == 1
    assert "2026-05-10" in summary.backfill_candidate_dates
    assert summary.p22_gate == P22_HISTORICAL_BACKFILL_AVAILABILITY_READY


def test_summary_safety_invariants(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    base.mkdir()
    results = scan_paper_date_range(base, "2026-05-01", "2026-05-01")
    summary = summarize_scan_results(results, "2026-05-01", "2026-05-01")
    assert summary.paper_only is True
    assert summary.production_ready is False
