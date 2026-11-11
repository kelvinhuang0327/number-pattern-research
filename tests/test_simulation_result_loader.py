"""
tests/test_simulation_result_loader.py

Tests for simulation_result_loader.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wbc_backend.simulation.simulation_result_loader import (
    load_latest_simulation_result,
    load_simulation_result_from_jsonl,
)
from wbc_backend.simulation.strategy_simulation_result import StrategySimulationResult

# ── Helpers ───────────────────────────────────────────────────────────────────

def _minimal_sim_dict(
    strategy_name: str = "test_strat",
    gate_status: str = "PASS",
    sample_size: int = 100,
    generated_at: str = "2026-05-11T12:00:00+00:00",
    paper_only: bool = True,
) -> dict:
    return {
        "simulation_id": f"sim-{strategy_name}-abcd1234",
        "strategy_name": strategy_name,
        "date_start": "2025-01-01",
        "date_end": "2025-12-31",
        "sample_size": sample_size,
        "bet_count": 10,
        "skipped_count": 0,
        "gate_status": gate_status,
        "generated_at_utc": generated_at,
        "paper_only": paper_only,
        "gate_reasons": [],
        "source_trace": {},
    }


def _write_jsonl(tmp_path: Path, data: dict, subdir: str = "outputs/simulation/PAPER/test") -> Path:
    """Write a simulation dict as JSONL under a PAPER path in tmp_path."""
    paper_dir = tmp_path / subdir
    paper_dir.mkdir(parents=True, exist_ok=True)
    out_file = paper_dir / f"{data['strategy_name']}_test.jsonl"
    out_file.write_text(json.dumps(data), encoding="utf-8")
    return out_file


# ── Tests: load_simulation_result_from_jsonl ─────────────────────────────────

class TestLoadFromJsonl:
    def test_loads_valid_paper_jsonl(self, tmp_path):
        data = _minimal_sim_dict()
        path = _write_jsonl(tmp_path, data)
        result = load_simulation_result_from_jsonl(path)
        assert isinstance(result, StrategySimulationResult)
        assert result.strategy_name == "test_strat"
        assert result.gate_status == "PASS"
        assert result.paper_only is True

    def test_rejects_paper_only_false(self, tmp_path):
        data = _minimal_sim_dict(paper_only=False)
        path = _write_jsonl(tmp_path, data)
        with pytest.raises(ValueError, match="paper_only=False"):
            load_simulation_result_from_jsonl(path)

    def test_rejects_malformed_json(self, tmp_path):
        paper_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "bad"
        paper_dir.mkdir(parents=True, exist_ok=True)
        bad_file = paper_dir / "bad.jsonl"
        bad_file.write_text("not valid json {{", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed JSON"):
            load_simulation_result_from_jsonl(bad_file)

    def test_rejects_non_paper_path(self, tmp_path):
        # Write to a path that doesn't contain 'outputs/simulation/PAPER'
        bad_dir = tmp_path / "outputs" / "production" / "bets"
        bad_dir.mkdir(parents=True, exist_ok=True)
        bad_file = bad_dir / "test.jsonl"
        bad_file.write_text(json.dumps(_minimal_sim_dict()), encoding="utf-8")
        with pytest.raises(ValueError, match="non-PAPER path"):
            load_simulation_result_from_jsonl(bad_file)

    def test_rejects_missing_file(self, tmp_path):
        paper_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "missing"
        paper_dir.mkdir(parents=True, exist_ok=True)
        missing = paper_dir / "does_not_exist.jsonl"
        with pytest.raises(FileNotFoundError):
            load_simulation_result_from_jsonl(missing)

    def test_loads_float_fields(self, tmp_path):
        data = _minimal_sim_dict()
        data["brier_model"] = 0.241
        data["brier_market"] = 0.241
        data["brier_skill_score"] = 0.0
        data["ece"] = 0.019
        path = _write_jsonl(tmp_path, data)
        result = load_simulation_result_from_jsonl(path)
        assert result.brier_model == pytest.approx(0.241)
        assert result.ece == pytest.approx(0.019)

    def test_null_float_fields_return_none(self, tmp_path):
        data = _minimal_sim_dict()
        data["roi_pct"] = None
        data["sharpe_proxy"] = None
        path = _write_jsonl(tmp_path, data)
        result = load_simulation_result_from_jsonl(path)
        assert result.roi_pct is None
        assert result.sharpe_proxy is None

    def test_generated_at_utc_is_timezone_aware(self, tmp_path):
        data = _minimal_sim_dict(generated_at="2026-05-11T12:00:00+00:00")
        path = _write_jsonl(tmp_path, data)
        result = load_simulation_result_from_jsonl(path)
        assert result.generated_at_utc.tzinfo is not None


# ── Tests: load_latest_simulation_result ─────────────────────────────────────

class TestLoadLatest:
    def test_returns_none_when_no_results(self, tmp_path):
        paper_dir = tmp_path / "outputs" / "simulation" / "PAPER"
        paper_dir.mkdir(parents=True, exist_ok=True)
        result = load_latest_simulation_result(simulation_dir=paper_dir)
        assert result is None

    def test_loads_single_result(self, tmp_path):
        data = _minimal_sim_dict(strategy_name="strat_a")
        path = _write_jsonl(tmp_path, data, subdir="outputs/simulation/PAPER/2026-05-11")
        paper_dir = tmp_path / "outputs" / "simulation" / "PAPER"
        result = load_latest_simulation_result(simulation_dir=paper_dir)
        assert result is not None
        assert result.strategy_name == "strat_a"

    def test_loads_latest_by_generated_at(self, tmp_path):
        paper_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "2026-05-11"
        paper_dir.mkdir(parents=True, exist_ok=True)

        older = _minimal_sim_dict(strategy_name="strat_b", generated_at="2026-05-11T10:00:00+00:00")
        newer = _minimal_sim_dict(strategy_name="strat_b", generated_at="2026-05-11T12:00:00+00:00")

        (paper_dir / "older.jsonl").write_text(json.dumps(older), encoding="utf-8")
        (paper_dir / "newer.jsonl").write_text(json.dumps(newer), encoding="utf-8")

        sim_root = tmp_path / "outputs" / "simulation" / "PAPER"
        result = load_latest_simulation_result(simulation_dir=sim_root)
        assert result is not None
        assert result.generated_at_utc.hour == 12

    def test_filters_by_strategy_name(self, tmp_path):
        paper_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "2026-05-11"
        paper_dir.mkdir(parents=True, exist_ok=True)

        # File for strategy_alpha
        data_alpha = _minimal_sim_dict(strategy_name="strategy_alpha")
        (paper_dir / "strategy_alpha_test.jsonl").write_text(
            json.dumps(data_alpha), encoding="utf-8"
        )
        # File for strategy_beta
        data_beta = _minimal_sim_dict(strategy_name="strategy_beta")
        (paper_dir / "strategy_beta_test.jsonl").write_text(
            json.dumps(data_beta), encoding="utf-8"
        )

        sim_root = tmp_path / "outputs" / "simulation" / "PAPER"
        result = load_latest_simulation_result(
            simulation_dir=sim_root, strategy_name="strategy_alpha"
        )
        assert result is not None
        assert result.strategy_name == "strategy_alpha"

    def test_returns_none_for_non_paper_path(self, tmp_path):
        # Pass a non-PAPER path
        bad_dir = tmp_path / "outputs" / "production"
        bad_dir.mkdir(parents=True, exist_ok=True)
        result = load_latest_simulation_result(simulation_dir=bad_dir)
        assert result is None

    def test_returns_none_when_directory_missing(self, tmp_path):
        missing = tmp_path / "outputs" / "simulation" / "PAPER" / "nonexistent"
        result = load_latest_simulation_result(simulation_dir=missing)
        assert result is None

    def test_skips_malformed_files(self, tmp_path):
        paper_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "2026-05-11"
        paper_dir.mkdir(parents=True, exist_ok=True)
        # One valid, one malformed
        data = _minimal_sim_dict(strategy_name="good_strat")
        (paper_dir / "good.jsonl").write_text(json.dumps(data), encoding="utf-8")
        (paper_dir / "bad.jsonl").write_text("{{bad json", encoding="utf-8")
        sim_root = tmp_path / "outputs" / "simulation" / "PAPER"
        result = load_latest_simulation_result(simulation_dir=sim_root)
        assert result is not None
        assert result.strategy_name == "good_strat"

    def test_skips_paper_only_false_files(self, tmp_path):
        paper_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "2026-05-11"
        paper_dir.mkdir(parents=True, exist_ok=True)
        bad_data = _minimal_sim_dict(strategy_name="bad_strat", paper_only=False)
        (paper_dir / "bad_paper.jsonl").write_text(json.dumps(bad_data), encoding="utf-8")
        sim_root = tmp_path / "outputs" / "simulation" / "PAPER"
        result = load_latest_simulation_result(simulation_dir=sim_root)
        assert result is None
