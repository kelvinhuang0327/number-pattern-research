"""
tests/test_p21_daily_artifact_discovery.py

Unit tests for P21 daily artifact discovery.
"""
import json
import tempfile
from pathlib import Path

import pytest

from wbc_backend.recommendation.p21_daily_artifact_discovery import (
    REQUIRED_DAILY_ARTIFACTS,
    discover_p20_daily_artifacts,
    load_daily_gate,
    load_daily_summary,
    summarize_missing_artifacts,
    validate_daily_artifact_set,
)
from wbc_backend.recommendation.p21_multi_day_backfill_contract import (
    P21BackfillDateResult,
    P21MissingArtifactReport,
    P21_BLOCKED_DAILY_GATE_NOT_READY,
    P21_BLOCKED_MISSING_REQUIRED_ARTIFACTS,
    P21_MULTI_DAY_PAPER_BACKFILL_READY,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_valid_p20_dir(base: Path, run_date: str) -> Path:
    """Create a fully valid P20 date directory."""
    date_dir = base / run_date / "p20_daily_paper_orchestrator"
    date_dir.mkdir(parents=True, exist_ok=True)

    gate = {
        "run_date": run_date,
        "p20_gate": "P20_DAILY_PAPER_ORCHESTRATOR_READY",
        "paper_only": True,
        "production_ready": False,
    }
    (date_dir / "p20_gate_result.json").write_text(json.dumps(gate), encoding="utf-8")

    summary = {
        "p20_gate": "P20_DAILY_PAPER_ORCHESTRATOR_READY",
        "n_recommended_rows": 324,
        "n_active_paper_entries": 324,
        "n_settled_win": 171,
        "n_settled_loss": 153,
        "n_unsettled": 0,
        "total_stake_units": 324.0,
        "total_pnl_units": 34.93,
        "roi_units": 0.10778278086419754,
        "hit_rate": 0.5277777777777778,
        "game_id_coverage": 1.0,
        "settlement_join_method": "JOIN_BY_GAME_ID",
        "paper_only": True,
        "production_ready": False,
    }
    (date_dir / "daily_paper_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    manifest = {"run_date": run_date, "artifacts": []}
    (date_dir / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    return date_dir


def _write_bad_gate_p20_dir(base: Path, run_date: str) -> Path:
    """Create a P20 date dir with gate NOT READY."""
    date_dir = base / run_date / "p20_daily_paper_orchestrator"
    date_dir.mkdir(parents=True, exist_ok=True)

    gate = {"p20_gate": "P20_BLOCKED_P16_6_NOT_READY", "paper_only": True, "production_ready": False}
    (date_dir / "p20_gate_result.json").write_text(json.dumps(gate), encoding="utf-8")

    summary = {
        "p20_gate": "P20_BLOCKED_P16_6_NOT_READY",
        "n_active_paper_entries": 0,
        "n_settled_win": 0,
        "n_settled_loss": 0,
        "n_unsettled": 0,
        "roi_units": 0.0,
        "hit_rate": 0.0,
        "game_id_coverage": 0.0,
        "settlement_join_method": "NONE",
        "paper_only": True,
        "production_ready": False,
    }
    (date_dir / "daily_paper_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (date_dir / "artifact_manifest.json").write_text("{}", encoding="utf-8")

    return date_dir


# ---------------------------------------------------------------------------
# Tests: validate_daily_artifact_set
# ---------------------------------------------------------------------------


def test_validate_full_set_valid():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        date_dir = _write_valid_p20_dir(base, "2026-05-12") 
        result = validate_daily_artifact_set(date_dir)
        assert result.valid is True


def test_validate_missing_one_artifact():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        date_dir = _write_valid_p20_dir(base, "2026-05-12")
        (date_dir / "p20_gate_result.json").unlink()
        result = validate_daily_artifact_set(date_dir)
        assert result.valid is False
        assert result.error_code == P21_BLOCKED_MISSING_REQUIRED_ARTIFACTS


def test_validate_all_missing():
    with tempfile.TemporaryDirectory() as tmp:
        date_dir = Path(tmp) / "p20_daily_paper_orchestrator"
        date_dir.mkdir()
        result = validate_daily_artifact_set(date_dir)
        assert result.valid is False


# ---------------------------------------------------------------------------
# Tests: load_daily_gate / load_daily_summary
# ---------------------------------------------------------------------------


def test_load_daily_gate_returns_dict():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        date_dir = _write_valid_p20_dir(base, "2026-05-12")
        gate = load_daily_gate(date_dir)
        assert gate["p20_gate"] == "P20_DAILY_PAPER_ORCHESTRATOR_READY"


def test_load_daily_summary_returns_dict():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        date_dir = _write_valid_p20_dir(base, "2026-05-12")
        summary = load_daily_summary(date_dir)
        assert summary["n_active_paper_entries"] == 324


# ---------------------------------------------------------------------------
# Tests: discover_p20_daily_artifacts
# ---------------------------------------------------------------------------


def test_discover_finds_valid_date():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _write_valid_p20_dir(base, "2026-05-12")
        results = discover_p20_daily_artifacts(base, ("2026-05-12", "2026-05-12"))
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, P21BackfillDateResult)
        assert r.run_date == "2026-05-12"
        assert r.daily_gate == P21_MULTI_DAY_PAPER_BACKFILL_READY


def test_discover_reports_missing_date():
    """Missing dates must NOT be fabricated — they must appear as P21MissingArtifactReport."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        # Only 2026-05-12 exists; 2026-05-11 does not
        _write_valid_p20_dir(base, "2026-05-12")
        results = discover_p20_daily_artifacts(base, ("2026-05-11", "2026-05-12"))
        assert len(results) == 2

        missing = [r for r in results if isinstance(r, P21MissingArtifactReport)]
        ready = [r for r in results if isinstance(r, P21BackfillDateResult)]

        assert len(missing) == 1
        assert missing[0].run_date == "2026-05-11"
        assert len(ready) == 1
        assert ready[0].run_date == "2026-05-12"


def test_discover_blocked_date_when_gate_not_ready():
    """A date whose p20_gate != READY is returned as P21BackfillDateResult but with BLOCKED daily_gate."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _write_bad_gate_p20_dir(base, "2026-05-12")
        results = discover_p20_daily_artifacts(base, ("2026-05-12", "2026-05-12"))
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, P21BackfillDateResult)
        assert r.daily_gate == P21_BLOCKED_DAILY_GATE_NOT_READY


def test_discover_multiple_dates():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _write_valid_p20_dir(base, "2026-05-10")
        _write_valid_p20_dir(base, "2026-05-11")
        _write_valid_p20_dir(base, "2026-05-12")
        results = discover_p20_daily_artifacts(base, ("2026-05-10", "2026-05-12"))
        assert len(results) == 3
        assert all(isinstance(r, P21BackfillDateResult) for r in results)


def test_discover_returns_all_requested_dates():
    """Total results must equal n_dates_requested, regardless of ready/missing status."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _write_valid_p20_dir(base, "2026-05-12")
        # Request 3 dates but only 1 exists
        results = discover_p20_daily_artifacts(base, ("2026-05-10", "2026-05-12"))
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Tests: summarize_missing_artifacts
# ---------------------------------------------------------------------------


def test_summarize_missing_artifacts_empty_when_all_ready():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _write_valid_p20_dir(base, "2026-05-12")
        results = discover_p20_daily_artifacts(base, ("2026-05-12", "2026-05-12"))
        missing = summarize_missing_artifacts(("2026-05-12", "2026-05-12"), results)
        assert missing == []


def test_summarize_missing_artifacts_returns_missing_dates():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        results = discover_p20_daily_artifacts(base, ("2026-05-11", "2026-05-12"))
        missing = summarize_missing_artifacts(("2026-05-11", "2026-05-12"), results)
        assert len(missing) == 2
        dates = [m["run_date"] for m in missing]
        assert "2026-05-11" in dates
        assert "2026-05-12" in dates
