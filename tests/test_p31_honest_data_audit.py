"""
Tests for P31 Honest Data Audit — source classification module.

Coverage:
1. outputs/ source is always DERIVED_OUTPUT
2. data/ raw-looking CSV is RAW_PRIMARY only when canonical fields exist
3. raw-looking file missing odds is still RAW_PRIMARY (odds not required for class)
4. missing game_date → SCHEMA_PARTIAL
5. derived signal columns → DERIVED_OUTPUT regardless of path
6. no double-counting: derived outputs not in usable_2024_raw_count
7. counters sum correctly
8. PAPER_ONLY=True and production_ready=False
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

import pytest

from wbc_backend.recommendation.p31_honest_data_audit import (
    AuditCounters,
    SourceClass,
    SourceEntry,
    _classify_file,
    _is_derived_by_path,
    _is_raw_secondary_by_path,
    determine_p31_gate,
    run_honest_data_audit,
    write_classification_csv,
    PAPER_ONLY,
    PRODUCTION_READY,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal fake repo structure for testing."""
    (tmp_path / "data").mkdir()
    (tmp_path / "outputs" / "predictions" / "PAPER").mkdir(parents=True)
    return tmp_path


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


# ---------------------------------------------------------------------------
# Test: _is_derived_by_path
# ---------------------------------------------------------------------------


class TestIsDerivedByPath:
    def test_outputs_prefix(self) -> None:
        assert _is_derived_by_path("outputs/predictions/PAPER/some.csv")

    def test_model_output_name(self) -> None:
        assert _is_derived_by_path("data/model_output_something.csv")

    def test_learning_state(self) -> None:
        assert _is_derived_by_path("data/learning_state.json")

    def test_data_raw_csv_not_derived(self) -> None:
        assert not _is_derived_by_path("data/mlb_2025/mlb_odds_2025_real.csv")

    def test_oof_model(self) -> None:
        assert _is_derived_by_path("outputs/predictions/PAPER/oof_model.csv")


# ---------------------------------------------------------------------------
# Test: _is_raw_secondary_by_path
# ---------------------------------------------------------------------------


class TestIsRawSecondaryByPath:
    def test_gl2024_in_name(self) -> None:
        assert _is_raw_secondary_by_path("data/gl2024.zip")

    def test_retrosheet_in_name(self) -> None:
        assert _is_raw_secondary_by_path("data/retrosheet_2024.txt")

    def test_gl2025(self) -> None:
        assert _is_raw_secondary_by_path("data/mlb_2025/gl2025.zip")

    def test_ordinary_file(self) -> None:
        assert not _is_raw_secondary_by_path("data/mlb_2025/mlb_odds_2025_real.csv")


# ---------------------------------------------------------------------------
# Test: _classify_file — DERIVED_OUTPUT
# ---------------------------------------------------------------------------


class TestClassifyDerivedOutput:
    def test_outputs_path_is_derived(self, tmp_repo: Path) -> None:
        """Test 1: outputs/ source is always DERIVED_OUTPUT."""
        p = tmp_repo / "outputs" / "predictions" / "PAPER" / "raw_model.csv"
        _write_csv(p, ["game_date", "home_team", "away_team"], [["2024-04-01", "NYY", "BOS"]])
        entry = _classify_file(p, tmp_repo)
        assert entry.source_class == SourceClass.DERIVED_OUTPUT

    def test_derived_signal_column_triggers_derived(self, tmp_repo: Path) -> None:
        """Derived signal columns → DERIVED_OUTPUT regardless of path."""
        p = tmp_repo / "data" / "something.csv"
        _write_csv(
            p,
            ["game_date", "home_team", "away_team", "predicted_probability"],
            [["2025-04-01", "NYY", "BOS", "0.62"]],
        )
        entry = _classify_file(p, tmp_repo)
        assert entry.source_class == SourceClass.DERIVED_OUTPUT
        assert entry.has_derived_signals

    def test_paper_recommendation_is_derived(self, tmp_repo: Path) -> None:
        p = tmp_repo / "data" / "paper_recommendation_2025.json"
        _write_json(p, {"game_date": "2025-01-01", "recommendation": "BET", "edge": 0.06})
        entry = _classify_file(p, tmp_repo)
        assert entry.source_class == SourceClass.DERIVED_OUTPUT

    def test_dry_run_file_is_derived(self, tmp_repo: Path) -> None:
        p = tmp_repo / "data" / "derived" / "future_model_predictions_dry_run_2026.jsonl"
        _write_json(p, {"dry_run": True, "game_date": "2026-01-01"})
        entry = _classify_file(p, tmp_repo)
        assert entry.source_class == SourceClass.DERIVED_OUTPUT


# ---------------------------------------------------------------------------
# Test: _classify_file — RAW_PRIMARY
# ---------------------------------------------------------------------------


class TestClassifyRawPrimary:
    def test_full_canonical_csv_is_raw_primary(self, tmp_repo: Path) -> None:
        """Test 2: data/ raw CSV with canonical fields is RAW_PRIMARY."""
        p = tmp_repo / "data" / "mlb_2025" / "mlb_odds_2025.csv"
        _write_csv(
            p,
            ["Date", "Away", "Away Score", "Home", "Home Score", "Away ML", "Home ML"],
            [["2025-04-01", "BOS", "4", "NYY", "3", "+110", "-130"]],
        )
        entry = _classify_file(p, tmp_repo)
        assert entry.source_class == SourceClass.RAW_PRIMARY

    def test_raw_csv_without_odds_is_still_raw_primary(self, tmp_repo: Path) -> None:
        """Test 3: raw CSV missing odds columns is RAW_PRIMARY (odds not required for class)."""
        p = tmp_repo / "data" / "mlb_2025" / "games_no_odds.csv"
        _write_csv(
            p,
            ["Date", "Away", "Away Score", "Home", "Home Score"],
            [["2025-04-01", "BOS", "4", "NYY", "3"]],
        )
        entry = _classify_file(p, tmp_repo)
        assert entry.source_class == SourceClass.RAW_PRIMARY
        assert not entry.has_odds

    def test_raw_primary_has_no_derived_signals(self, tmp_repo: Path) -> None:
        p = tmp_repo / "data" / "mlb_2025" / "clean.csv"
        _write_csv(
            p,
            ["Date", "Away", "Away Score", "Home", "Home Score"],
            [["2025-05-01", "LAD", "6", "SF", "2"]],
        )
        entry = _classify_file(p, tmp_repo)
        assert not entry.has_derived_signals


# ---------------------------------------------------------------------------
# Test: _classify_file — SCHEMA_PARTIAL
# ---------------------------------------------------------------------------


class TestClassifySchemaPartial:
    def test_missing_game_date_is_schema_partial(self, tmp_repo: Path) -> None:
        """Test 4: file missing game_date is SCHEMA_PARTIAL."""
        p = tmp_repo / "data" / "no_date.csv"
        _write_csv(
            p,
            ["Away", "Away Score", "Home", "Home Score"],
            [["BOS", "4", "NYY", "3"]],
        )
        entry = _classify_file(p, tmp_repo)
        assert entry.source_class == SourceClass.SCHEMA_PARTIAL
        assert "game_date" in entry.missing_canonical_columns

    def test_missing_teams_is_schema_partial(self, tmp_repo: Path) -> None:
        p = tmp_repo / "data" / "only_scores.csv"
        _write_csv(
            p,
            ["Date", "Home Score", "Away Score"],
            [["2025-04-01", "3", "4"]],
        )
        entry = _classify_file(p, tmp_repo)
        assert entry.source_class == SourceClass.SCHEMA_PARTIAL


# ---------------------------------------------------------------------------
# Test: _classify_file — RAW_SECONDARY
# ---------------------------------------------------------------------------


class TestClassifyRawSecondary:
    def test_gl2025_zip_is_raw_secondary(self, tmp_repo: Path) -> None:
        """Retrosheet game log archive is RAW_SECONDARY."""
        p = tmp_repo / "data" / "mlb_2025" / "gl2025.zip"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"PK")  # fake zip
        entry = _classify_file(p, tmp_repo)
        # .zip is not in the extension list — won't be scanned;
        # but if classified, it should be RAW_SECONDARY by path.
        # Direct classification test:
        from wbc_backend.recommendation.p31_honest_data_audit import _is_raw_secondary_by_path
        assert _is_raw_secondary_by_path(str(p.relative_to(tmp_repo)))


# ---------------------------------------------------------------------------
# Test: run_honest_data_audit — counters
# ---------------------------------------------------------------------------


class TestAuditCounters:
    def test_derived_not_counted_as_usable_2024(self, tmp_repo: Path) -> None:
        """Test 10: Derived outputs are not counted as usable 2024 raw sources."""
        # Create a derived output under outputs/ with "2024" in path
        p = tmp_repo / "outputs" / "predictions" / "PAPER" / "2024_raw_model.csv"
        _write_csv(
            p,
            ["game_date", "home_team", "away_team", "predicted_probability"],
            [["2024-04-01", "NYY", "BOS", "0.61"]],
        )
        result = run_honest_data_audit(tmp_repo)
        assert result.counters.usable_2024_raw_count == 0
        assert result.counters.derived_output_count >= 1

    def test_counters_sum_to_total(self, tmp_repo: Path) -> None:
        """Sum of all class counts equals total_sources."""
        # Add a raw primary
        p = tmp_repo / "data" / "game.csv"
        _write_csv(
            p,
            ["Date", "Away", "Away Score", "Home", "Home Score"],
            [["2025-04-01", "BOS", "4", "NYY", "3"]],
        )
        result = run_honest_data_audit(tmp_repo)
        c = result.counters
        total = (
            c.raw_primary_count
            + c.raw_secondary_count
            + c.derived_output_count
            + c.schema_partial_count
        )
        assert total == c.total_sources

    def test_misleading_ready_equals_derived_count(self, tmp_repo: Path) -> None:
        """misleading_ready_source_count == derived_output_count."""
        result = run_honest_data_audit(tmp_repo)
        c = result.counters
        assert c.misleading_ready_source_count == c.derived_output_count


# ---------------------------------------------------------------------------
# Test: Paper-only safety
# ---------------------------------------------------------------------------


class TestPaperOnlySafety:
    def test_paper_only_true(self) -> None:
        """Test 9: production_ready must never be True."""
        assert PAPER_ONLY is True
        assert PRODUCTION_READY is False


# ---------------------------------------------------------------------------
# Test: determine_p31_gate
# ---------------------------------------------------------------------------


class TestDetermineP31Gate:
    def _make_result(
        self,
        raw_primary: int = 0,
        raw_secondary: int = 0,
        derived: int = 0,
        partial: int = 0,
    ):
        from wbc_backend.recommendation.p31_honest_data_audit import HonestDataAuditResult

        result = HonestDataAuditResult()
        result.counters.total_sources = raw_primary + raw_secondary + derived + partial
        result.counters.raw_primary_count = raw_primary
        result.counters.raw_secondary_count = raw_secondary
        result.counters.derived_output_count = derived
        result.counters.schema_partial_count = partial
        result.counters.misleading_ready_source_count = derived
        return result

    def test_no_sources_returns_fail(self) -> None:
        result = self._make_result()
        gate = determine_p31_gate(result, provenance_safe=False)
        assert gate == "P31_FAIL_INPUT_MISSING"

    def test_only_derived_returns_blocked(self) -> None:
        result = self._make_result(derived=10)
        gate = determine_p31_gate(result, provenance_safe=False)
        assert gate == "P31_BLOCKED_NO_RAW_HISTORICAL_INCREMENT"

    def test_raw_primary_returns_ready(self) -> None:
        result = self._make_result(raw_primary=5)
        gate = determine_p31_gate(result, provenance_safe=True)
        assert gate == "P31_HONEST_DATA_AUDIT_READY"

    def test_raw_without_odds_still_ready(self) -> None:
        """Even without odds resolved, gate is READY if game logs exist."""
        result = self._make_result(raw_secondary=3)
        gate = determine_p31_gate(result, provenance_safe=False)
        assert gate == "P31_HONEST_DATA_AUDIT_READY"


# ---------------------------------------------------------------------------
# Test: write_classification_csv
# ---------------------------------------------------------------------------


class TestWriteClassificationCsv:
    def test_writes_csv_with_correct_headers(self, tmp_path: Path) -> None:
        from wbc_backend.recommendation.p31_honest_data_audit import (
            HonestDataAuditResult,
        )

        result = HonestDataAuditResult()
        result.entries.append(
            SourceEntry(
                path="data/test.csv",
                source_class=SourceClass.RAW_PRIMARY,
                has_game_date=True,
                has_scores=True,
                has_odds=True,
                has_derived_signals=False,
                missing_canonical_columns=[],
                year_coverage=[2025],
                notes="test",
            )
        )
        out = tmp_path / "out.csv"
        write_classification_csv(result, out)
        assert out.exists()
        rows = list(csv.DictReader(out.open()))
        assert len(rows) == 1
        assert rows[0]["source_class"] == "RAW_PRIMARY"
