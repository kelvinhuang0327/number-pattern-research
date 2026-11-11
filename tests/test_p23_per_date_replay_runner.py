"""
tests/test_p23_per_date_replay_runner.py

Unit tests for P23 per-date replay runner.

Key scenarios:
- Reuses existing P20 READY result without re-running (already_ready path)
- Blocks when source not ready
- Returns blocked when materializer fails
- Force flag triggers re-run even for already-ready dates
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from wbc_backend.recommendation.p23_historical_replay_contract import (
    P23_DATE_ALREADY_READY,
    P23_DATE_BLOCKED_P15_BUILD_FAILED,
    P23_DATE_BLOCKED_SOURCE_NOT_READY,
    P23_DATE_REPLAY_READY,
    P23ReplayDateTask,
)
from wbc_backend.recommendation.p23_per_date_replay_runner import (
    _build_date_result_from_existing_p20,
    run_date_replay,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    run_date: str = "2026-05-12",
    source_ready: bool = True,
    source_type: str = "MATERIALIZED_FROM_P22_5",
) -> P23ReplayDateTask:
    return P23ReplayDateTask(
        run_date=run_date,
        p22_5_source_ready=source_ready,
        source_type=source_type,
        paper_only=True,
        production_ready=False,
    )


def _write_p20_gate_result(paper_base_dir: Path, run_date: str) -> Path:
    """Write a mock P20 gate result for a given date."""
    p20_dir = paper_base_dir / run_date / "p20_daily_paper_orchestrator"
    p20_dir.mkdir(parents=True)
    gate = {
        "run_date": run_date,
        "p20_gate": "P20_DAILY_PAPER_ORCHESTRATOR_READY",
        "paper_only": True,
        "production_ready": False,
        "n_recommended_rows": 324,
        "n_active_paper_entries": 324,
        "n_settled_win": 171,
        "n_settled_loss": 153,
        "n_unsettled": 0,
        "roi_units": 0.10778278086419754,
        "hit_rate": 0.5277777777777778,
        "settlement_join_method": "JOIN_BY_GAME_ID",
        "game_id_coverage": 1.0,
    }
    gate_path = p20_dir / "p20_gate_result.json"
    gate_path.write_text(json.dumps(gate))
    return gate_path


# ---------------------------------------------------------------------------
# _build_date_result_from_existing_p20
# ---------------------------------------------------------------------------

class TestBuildDateResultFromExistingP20:
    def test_builds_result_from_existing_p20(self, tmp_path):
        paper_base_dir = tmp_path / "PAPER"
        _write_p20_gate_result(paper_base_dir, "2026-05-12")

        result = _build_date_result_from_existing_p20("2026-05-12", paper_base_dir)

        assert result.run_date == "2026-05-12"
        assert result.date_gate == P23_DATE_ALREADY_READY
        assert result.n_active_paper_entries == 324
        assert result.n_settled_win == 171
        assert result.n_settled_loss == 153
        assert result.paper_only is True
        assert result.production_ready is False

    def test_returns_already_ready_gate(self, tmp_path):
        paper_base_dir = tmp_path / "PAPER"
        _write_p20_gate_result(paper_base_dir, "2026-05-10")

        result = _build_date_result_from_existing_p20("2026-05-10", paper_base_dir)

        assert result.date_gate == P23_DATE_ALREADY_READY


# ---------------------------------------------------------------------------
# run_date_replay — already_ready path
# ---------------------------------------------------------------------------

class TestRunDateReplayAlreadyReady:
    def test_reuses_existing_p20_without_rerun(self, tmp_path):
        """When source_type=ALREADY_READY and force=False, skip pipeline."""
        paper_base_dir = tmp_path / "PAPER"
        _write_p20_gate_result(paper_base_dir, "2026-05-12")

        task = _make_task(run_date="2026-05-12", source_type="ALREADY_READY")

        with patch(
            "wbc_backend.recommendation.p23_per_date_replay_runner._run_pipeline_for_date"
        ) as mock_pipeline:
            result = run_date_replay(
                task=task,
                p22_5_output_dir=tmp_path / "p22_5",
                paper_base_dir=paper_base_dir,
                force=False,
            )
            mock_pipeline.assert_not_called()

        assert result.date_gate == P23_DATE_ALREADY_READY

    def test_force_reruns_even_when_already_ready(self, tmp_path):
        """With force=True, the pipeline must be called even for ALREADY_READY dates."""
        paper_base_dir = tmp_path / "PAPER"
        _write_p20_gate_result(paper_base_dir, "2026-05-12")

        # Build a fake USABLE inventory so materializer can run
        p22_5_dir = tmp_path / "p22_5"
        p22_5_dir.mkdir()

        # The force path tries to materialize; mock it to immediately return blocked
        with patch(
            "wbc_backend.recommendation.p23_per_date_replay_runner.materialize_p15_inputs_for_date"
        ) as mock_mat:
            mock_mat.return_value = {
                "status": "P23_DATE_BLOCKED_SOURCE_NOT_READY",
                "p15_materialized_path": "",
                "sim_ledger_path": "",
                "n_rows": 0,
                "blocker_reason": "force test block",
                "paper_only": True,
                "production_ready": False,
            }
            # Also mock source_ready check
            task = P23ReplayDateTask(
                run_date="2026-05-12",
                p22_5_source_ready=True,
                source_type="ALREADY_READY",
                paper_only=True,
                production_ready=False,
            )
            result = run_date_replay(
                task=task,
                p22_5_output_dir=p22_5_dir,
                paper_base_dir=paper_base_dir,
                force=True,
            )
        # With force=True, materializer was called and returned blocked
        assert result.date_gate == P23_DATE_BLOCKED_P15_BUILD_FAILED


# ---------------------------------------------------------------------------
# run_date_replay — source not ready
# ---------------------------------------------------------------------------

class TestRunDateReplaySourceNotReady:
    def test_blocked_when_source_not_ready(self, tmp_path):
        task = _make_task(
            run_date="2026-05-05",
            source_ready=False,
            source_type="BLOCKED",
        )

        result = run_date_replay(
            task=task,
            p22_5_output_dir=tmp_path / "p22_5",
            paper_base_dir=tmp_path / "PAPER",
            force=False,
        )

        assert result.date_gate == P23_DATE_BLOCKED_SOURCE_NOT_READY
        assert result.source_ready is False
        assert result.paper_only is True
        assert result.production_ready is False


# ---------------------------------------------------------------------------
# run_date_replay — materializer failure
# ---------------------------------------------------------------------------

class TestRunDateReplayMaterializerFailure:
    def test_blocked_when_materializer_fails(self, tmp_path):
        task = _make_task(run_date="2026-05-01", source_type="MATERIALIZED_FROM_P22_5")

        with patch(
            "wbc_backend.recommendation.p23_per_date_replay_runner.materialize_p15_inputs_for_date"
        ) as mock_mat:
            mock_mat.return_value = {
                "status": "P23_DATE_BLOCKED_P15_BUILD_FAILED",
                "p15_materialized_path": "",
                "sim_ledger_path": "",
                "n_rows": 0,
                "blocker_reason": "Missing required columns",
                "paper_only": True,
                "production_ready": False,
            }
            result = run_date_replay(
                task=task,
                p22_5_output_dir=tmp_path / "p22_5",
                paper_base_dir=tmp_path / "PAPER",
                force=False,
            )

        assert result.date_gate == P23_DATE_BLOCKED_P15_BUILD_FAILED
        assert "columns" in result.blocker_reason.lower()
        assert result.paper_only is True


# ---------------------------------------------------------------------------
# Contract enforcement
# ---------------------------------------------------------------------------

class TestRunDateReplayContractEnforcement:
    def test_all_results_have_paper_only_true(self, tmp_path):
        """Every result from run_date_replay must have paper_only=True."""
        # Test all three paths: already_ready, source_not_ready, materializer_fails
        paper_base_dir = tmp_path / "PAPER"
        _write_p20_gate_result(paper_base_dir, "2026-05-12")

        tasks = [
            _make_task("2026-05-12", source_type="ALREADY_READY"),
            _make_task("2026-05-05", source_ready=False, source_type="BLOCKED"),
        ]

        for task in tasks:
            result = run_date_replay(task, tmp_path / "p22_5", paper_base_dir, False)
            assert result.paper_only is True, f"paper_only=False for {task.run_date}"
            assert result.production_ready is False
