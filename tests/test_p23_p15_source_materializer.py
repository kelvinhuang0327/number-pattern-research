"""
tests/test_p23_p15_source_materializer.py

Unit tests for P23 P15 source materializer.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p23_p15_source_materializer import (
    REQUIRED_MATERIALIZED_COLUMNS,
    build_replay_date_tasks,
    list_replayable_dates,
    load_p22_5_readiness_plan,
    materialize_p15_inputs_for_date,
    validate_materialized_p15_inputs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source_df(n_rows: int = 50) -> pd.DataFrame:
    """Create a minimal source DataFrame matching the P15 schema."""
    return pd.DataFrame({
        "y_true": ([1, 0] * ((n_rows + 1) // 2))[:n_rows],
        "p_oof": [0.6] * n_rows,
        "fold_id": [1] * n_rows,
        "game_id": [f"2025-05-01_NYY_BOS_{i}" for i in range(n_rows)],
        "game_date": ["2025-05-01"] * n_rows,
        "home_team": ["NYY"] * n_rows,
        "away_team": ["BOS"] * n_rows,
        "odds_decimal_home": [1.9] * n_rows,
        "odds_decimal_away": [2.1] * n_rows,
        "p_market": [0.52] * n_rows,
        "edge": [0.08] * n_rows,
        "run_date": ["2026-05-12"] * n_rows,
    })


def _write_source_csv(tmp_path: Path, df: pd.DataFrame) -> Path:
    """Write a source CSV and a simulation_ledger.csv to a p15_market_odds_simulation dir."""
    p15_dir = tmp_path / "p15_market_odds_simulation"
    p15_dir.mkdir(parents=True)
    joined_path = p15_dir / "joined_oof_with_odds.csv"
    df.to_csv(joined_path, index=False)
    # Write minimal simulation_ledger.csv
    ledger_df = pd.DataFrame({
        "row_idx": range(len(df)),
        "y_true": df["y_true"],
        "paper_only": True,
    })
    ledger_df.to_csv(p15_dir / "simulation_ledger.csv", index=False)
    return joined_path


def _write_inventory(tmp_path: Path, source_path: str) -> Path:
    """Write a P22.5 source_candidate_inventory.json with one USABLE candidate."""
    inventory = {
        "candidates": [
            {
                "file_path": source_path,
                "candidate_status": "SOURCE_CANDIDATE_USABLE",
                "source_type": "HISTORICAL_P15_JOINED_INPUT",
            }
        ]
    }
    inv_path = tmp_path / "source_candidate_inventory.json"
    inv_path.write_text(json.dumps(inventory))
    return inv_path


def _write_plan(tmp_path: Path, dates: list[str]) -> Path:
    """Write a P22.5 readiness plan JSON."""
    plan = {"dates_ready_to_build_p15_inputs": dates}
    plan_path = tmp_path / "p15_readiness_plan.json"
    plan_path.write_text(json.dumps(plan))
    return plan_path


# ---------------------------------------------------------------------------
# load_p22_5_readiness_plan
# ---------------------------------------------------------------------------

class TestLoadReadinessPlan:
    def test_loads_valid_plan(self, tmp_path):
        plan_path = _write_plan(tmp_path, ["2026-05-01", "2026-05-02"])
        plan = load_p22_5_readiness_plan(plan_path)
        assert "dates_ready_to_build_p15_inputs" in plan
        assert len(plan["dates_ready_to_build_p15_inputs"]) == 2

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_p22_5_readiness_plan(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# list_replayable_dates
# ---------------------------------------------------------------------------

class TestListReplayableDates:
    def test_returns_sorted_dates(self):
        plan = {"dates_ready_to_build_p15_inputs": ["2026-05-03", "2026-05-01", "2026-05-02"]}
        dates = list_replayable_dates(plan)
        assert dates == ["2026-05-01", "2026-05-02", "2026-05-03"]

    def test_returns_empty_for_missing_key(self):
        dates = list_replayable_dates({})
        assert dates == []


# ---------------------------------------------------------------------------
# materialize_p15_inputs_for_date
# ---------------------------------------------------------------------------

class TestMaterializeP15InputsForDate:
    def test_materializes_full_source_rows(self, tmp_path):
        """Materializer must use ALL source rows, not just 20."""
        n_rows = 100
        df = _make_source_df(n_rows)
        src_path = _write_source_csv(tmp_path, df)
        p22_5_dir = tmp_path / "p22_5_out"
        p22_5_dir.mkdir()
        _write_inventory(p22_5_dir, str(src_path))

        result = materialize_p15_inputs_for_date(
            run_date="2026-05-01",
            p22_5_output_dir=p22_5_dir,
            output_base_dir=tmp_path / "PAPER",
        )

        assert result["status"] == "P23_MATERIALIZED"
        assert result["n_rows"] == n_rows

        out_df = pd.read_csv(result["p15_materialized_path"])
        assert len(out_df) == n_rows

    def test_updates_run_date_column(self, tmp_path):
        """run_date column must be updated to the target date."""
        df = _make_source_df(20)
        src_path = _write_source_csv(tmp_path, df)
        p22_5_dir = tmp_path / "p22_5_out"
        p22_5_dir.mkdir()
        _write_inventory(p22_5_dir, str(src_path))

        result = materialize_p15_inputs_for_date(
            run_date="2026-05-05",
            p22_5_output_dir=p22_5_dir,
            output_base_dir=tmp_path / "PAPER",
        )

        assert result["status"] == "P23_MATERIALIZED"
        out_df = pd.read_csv(result["p15_materialized_path"])
        assert (out_df["run_date"] == "2026-05-05").all()

    def test_does_not_fabricate_rows(self, tmp_path):
        """Row count must exactly match source — no extra rows."""
        n_rows = 37
        df = _make_source_df(n_rows)
        src_path = _write_source_csv(tmp_path, df)
        p22_5_dir = tmp_path / "p22_5_out"
        p22_5_dir.mkdir()
        _write_inventory(p22_5_dir, str(src_path))

        result = materialize_p15_inputs_for_date(
            run_date="2026-05-07",
            p22_5_output_dir=p22_5_dir,
            output_base_dir=tmp_path / "PAPER",
        )

        out_df = pd.read_csv(result["p15_materialized_path"])
        assert len(out_df) == n_rows, f"Expected {n_rows} rows, got {len(out_df)}"

    def test_blocked_when_no_usable_source(self, tmp_path):
        """Returns blocked status when no USABLE candidate found."""
        p22_5_dir = tmp_path / "p22_5_out"
        p22_5_dir.mkdir()
        # Empty inventory
        (p22_5_dir / "source_candidate_inventory.json").write_text(
            json.dumps({"candidates": []})
        )

        result = materialize_p15_inputs_for_date(
            run_date="2026-05-01",
            p22_5_output_dir=p22_5_dir,
            output_base_dir=tmp_path / "PAPER",
        )

        assert result["status"] != "P23_MATERIALIZED"
        assert result["n_rows"] == 0

    def test_blocked_when_missing_required_columns(self, tmp_path):
        """Returns blocked status when source file is missing required columns."""
        bad_df = pd.DataFrame({"col_a": [1, 2], "col_b": [3, 4]})
        p15_dir = tmp_path / "p15_market_odds_simulation"
        p15_dir.mkdir(parents=True)
        src_path = p15_dir / "joined_oof_with_odds.csv"
        bad_df.to_csv(src_path, index=False)

        p22_5_dir = tmp_path / "p22_5_out"
        p22_5_dir.mkdir()
        _write_inventory(p22_5_dir, str(src_path))

        result = materialize_p15_inputs_for_date(
            run_date="2026-05-01",
            p22_5_output_dir=p22_5_dir,
            output_base_dir=tmp_path / "PAPER",
        )

        assert result["status"] != "P23_MATERIALIZED"

    def test_paper_only_set_true_in_output(self, tmp_path):
        """Materialized CSV must have paper_only=True on all rows."""
        df = _make_source_df(10)
        src_path = _write_source_csv(tmp_path, df)
        p22_5_dir = tmp_path / "p22_5_out"
        p22_5_dir.mkdir()
        _write_inventory(p22_5_dir, str(src_path))

        result = materialize_p15_inputs_for_date(
            run_date="2026-05-03",
            p22_5_output_dir=p22_5_dir,
            output_base_dir=tmp_path / "PAPER",
        )

        out_df = pd.read_csv(result["p15_materialized_path"])
        assert "paper_only" in out_df.columns
        assert out_df["paper_only"].astype(bool).all()


# ---------------------------------------------------------------------------
# validate_materialized_p15_inputs
# ---------------------------------------------------------------------------

class TestValidateMaterializedP15Inputs:
    def test_valid_df_returns_no_violations(self):
        df = _make_source_df(20)
        violations = validate_materialized_p15_inputs(df)
        assert violations == []

    def test_detects_missing_required_columns(self):
        df = pd.DataFrame({"y_true": [1, 0]})
        violations = validate_materialized_p15_inputs(df)
        assert any("Missing" in v for v in violations)

    def test_detects_all_null_y_true(self):
        df = _make_source_df(5)
        df["y_true"] = None
        violations = validate_materialized_p15_inputs(df)
        assert any("y_true" in v for v in violations)


# ---------------------------------------------------------------------------
# build_replay_date_tasks
# ---------------------------------------------------------------------------

class TestBuildReplayDateTasks:
    def test_builds_task_for_each_date(self, tmp_path):
        df = _make_source_df(10)
        src_path = _write_source_csv(tmp_path, df)
        p22_5_dir = tmp_path / "p22_5_out"
        p22_5_dir.mkdir()
        _write_inventory(p22_5_dir, str(src_path))

        tasks = build_replay_date_tasks(
            dates=["2026-05-01", "2026-05-02"],
            p22_5_output_dir=p22_5_dir,
            paper_base_dir=tmp_path / "PAPER",
        )

        assert len(tasks) == 2
        assert all(t.paper_only for t in tasks)
        assert all(not t.production_ready for t in tasks)
