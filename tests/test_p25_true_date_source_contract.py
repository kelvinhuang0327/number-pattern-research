"""
tests/test_p25_true_date_source_contract.py

Tests for the P25 true-date source separation contract module.
"""
from __future__ import annotations

import pytest

from wbc_backend.recommendation.p25_true_date_source_contract import (
    P25_BLOCKED_CONTRACT_VIOLATION,
    P25_BLOCKED_DATE_MISMATCH,
    P25_BLOCKED_INSUFFICIENT_ROWS,
    P25_BLOCKED_NO_TRUE_DATE_SOURCE,
    P25_FAIL_INPUT_MISSING,
    P25_FAIL_NON_DETERMINISTIC,
    P25_TRUE_DATE_SOURCE_SEPARATION_READY,
    TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH,
    TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID,
    TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
    TRUE_DATE_SLICE_EMPTY,
    TRUE_DATE_SLICE_PARTIAL,
    TRUE_DATE_SLICE_READY,
    P25DateSeparationResult,
    P25SourceSeparationGateResult,
    P25SourceSeparationSummary,
    P25TrueDateArtifactManifest,
    P25TrueDateSourceSlice,
)


# ---------------------------------------------------------------------------
# Gate constant smoke tests
# ---------------------------------------------------------------------------


def test_gate_constants_exist():
    assert P25_TRUE_DATE_SOURCE_SEPARATION_READY == "P25_TRUE_DATE_SOURCE_SEPARATION_READY"
    assert P25_BLOCKED_NO_TRUE_DATE_SOURCE == "P25_BLOCKED_NO_TRUE_DATE_SOURCE"
    assert P25_BLOCKED_DATE_MISMATCH == "P25_BLOCKED_DATE_MISMATCH"
    assert P25_BLOCKED_INSUFFICIENT_ROWS == "P25_BLOCKED_INSUFFICIENT_ROWS"
    assert P25_BLOCKED_CONTRACT_VIOLATION == "P25_BLOCKED_CONTRACT_VIOLATION"
    assert P25_FAIL_INPUT_MISSING == "P25_FAIL_INPUT_MISSING"
    assert P25_FAIL_NON_DETERMINISTIC == "P25_FAIL_NON_DETERMINISTIC"


def test_status_constants_exist():
    assert TRUE_DATE_SLICE_READY == "TRUE_DATE_SLICE_READY"
    assert TRUE_DATE_SLICE_EMPTY == "TRUE_DATE_SLICE_EMPTY"
    assert TRUE_DATE_SLICE_PARTIAL == "TRUE_DATE_SLICE_PARTIAL"
    assert TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH == "TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH"
    assert TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS == "TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS"
    assert TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID == "TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID"


# ---------------------------------------------------------------------------
# P25TrueDateSourceSlice
# ---------------------------------------------------------------------------


def _make_slice(**overrides):
    defaults = dict(
        run_date="2025-05-08",
        source_game_date="2025-05-08",
        source_path="data/some_source.csv",
        source_hash="abc123",
        n_rows=4,
        n_unique_game_ids=4,
        game_date_min="2025-05-08",
        game_date_max="2025-05-08",
        has_required_columns=True,
        date_matches_requested=True,
        paper_only=True,
        production_ready=False,
        blocker_reason="",
    )
    defaults.update(overrides)
    return P25TrueDateSourceSlice(**defaults)


def test_slice_valid():
    s = _make_slice()
    assert s.run_date == "2025-05-08"
    assert s.n_rows == 4
    assert s.paper_only is True
    assert s.production_ready is False


def test_slice_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready must be False"):
        _make_slice(production_ready=True)


def test_slice_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only must be True"):
        _make_slice(paper_only=False)


def test_slice_is_frozen():
    s = _make_slice()
    with pytest.raises(Exception):  # FrozenInstanceError
        s.n_rows = 99  # type: ignore


# ---------------------------------------------------------------------------
# P25DateSeparationResult
# ---------------------------------------------------------------------------


def _make_date_result(**overrides):
    defaults = dict(
        run_date="2025-05-08",
        status=TRUE_DATE_SLICE_READY,
        source_path="data/some_source.csv",
        n_rows=4,
        n_unique_game_ids=4,
        game_date_min="2025-05-08",
        game_date_max="2025-05-08",
        has_required_columns=True,
        blocker_reason="",
        paper_only=True,
        production_ready=False,
    )
    defaults.update(overrides)
    return P25DateSeparationResult(**defaults)


def test_date_result_valid():
    r = _make_date_result()
    assert r.status == TRUE_DATE_SLICE_READY
    assert r.paper_only is True
    assert r.production_ready is False


def test_date_result_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready must be False"):
        _make_date_result(production_ready=True)


def test_date_result_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only must be True"):
        _make_date_result(paper_only=False)


def test_date_result_rejects_invalid_status():
    with pytest.raises(ValueError, match="invalid status"):
        _make_date_result(status="INVENTED_STATUS")


def test_date_result_all_valid_statuses():
    for status in [
        TRUE_DATE_SLICE_READY,
        TRUE_DATE_SLICE_EMPTY,
        TRUE_DATE_SLICE_PARTIAL,
        TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH,
        TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
        TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID,
    ]:
        r = _make_date_result(status=status)
        assert r.status == status


def test_date_result_is_frozen():
    r = _make_date_result()
    with pytest.raises(Exception):
        r.n_rows = 99  # type: ignore


# ---------------------------------------------------------------------------
# P25SourceSeparationSummary
# ---------------------------------------------------------------------------


def _make_summary(**overrides):
    defaults = dict(
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
        source_files_scanned=2,
        paper_only=True,
        production_ready=False,
    )
    defaults.update(overrides)
    return P25SourceSeparationSummary(**defaults)


def test_summary_valid():
    s = _make_summary()
    assert s.n_dates_requested == 12
    assert s.paper_only is True
    assert s.production_ready is False


def test_summary_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready must be False"):
        _make_summary(production_ready=True)


def test_summary_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only must be True"):
        _make_summary(paper_only=False)


def test_summary_rejects_negative_n_dates():
    with pytest.raises(ValueError, match="n_dates_requested must be >= 0"):
        _make_summary(n_dates_requested=-1)


def test_summary_is_frozen():
    s = _make_summary()
    with pytest.raises(Exception):
        s.n_true_date_ready = 5  # type: ignore


# ---------------------------------------------------------------------------
# P25SourceSeparationGateResult
# ---------------------------------------------------------------------------


def _make_gate_result(**overrides):
    defaults = dict(
        p25_gate=P25_BLOCKED_NO_TRUE_DATE_SOURCE,
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
        blocker_reason="No 2026 rows.",
        paper_only=True,
        production_ready=False,
        generated_at="2026-05-12T00:00:00+00:00",
    )
    defaults.update(overrides)
    return P25SourceSeparationGateResult(**defaults)


def test_gate_result_valid():
    g = _make_gate_result()
    assert g.p25_gate == P25_BLOCKED_NO_TRUE_DATE_SOURCE
    assert g.paper_only is True
    assert g.production_ready is False


def test_gate_result_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready must be False"):
        _make_gate_result(production_ready=True)


def test_gate_result_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only must be True"):
        _make_gate_result(paper_only=False)


def test_gate_result_rejects_invalid_gate():
    with pytest.raises(ValueError, match="invalid p25_gate"):
        _make_gate_result(p25_gate="P25_MADE_UP_GATE")


def test_gate_result_all_valid_gates():
    for gate in [
        P25_TRUE_DATE_SOURCE_SEPARATION_READY,
        P25_BLOCKED_NO_TRUE_DATE_SOURCE,
        P25_BLOCKED_DATE_MISMATCH,
        P25_BLOCKED_INSUFFICIENT_ROWS,
        P25_BLOCKED_CONTRACT_VIOLATION,
        P25_FAIL_INPUT_MISSING,
        P25_FAIL_NON_DETERMINISTIC,
    ]:
        g = _make_gate_result(p25_gate=gate)
        assert g.p25_gate == gate


def test_gate_result_is_frozen():
    g = _make_gate_result()
    with pytest.raises(Exception):
        g.p25_gate = "CHANGED"  # type: ignore


# ---------------------------------------------------------------------------
# P25TrueDateArtifactManifest
# ---------------------------------------------------------------------------


def _make_manifest(**overrides):
    defaults = dict(
        output_dir="outputs/predictions/PAPER/backfill/p25_run",
        date_start="2025-05-08",
        date_end="2025-05-14",
        written_dates=("2025-05-08", "2025-05-09"),
        skipped_dates=("2025-05-10",),
        total_rows_written=19,
        total_unique_game_ids_written=19,
        paper_only=True,
        production_ready=False,
        generated_at="2026-05-12T00:00:00+00:00",
    )
    defaults.update(overrides)
    return P25TrueDateArtifactManifest(**defaults)


def test_manifest_valid():
    m = _make_manifest()
    assert len(m.written_dates) == 2
    assert m.total_rows_written == 19
    assert m.paper_only is True
    assert m.production_ready is False


def test_manifest_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready must be False"):
        _make_manifest(production_ready=True)


def test_manifest_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only must be True"):
        _make_manifest(paper_only=False)


def test_manifest_is_frozen():
    m = _make_manifest()
    with pytest.raises(Exception):
        m.total_rows_written = 999  # type: ignore
