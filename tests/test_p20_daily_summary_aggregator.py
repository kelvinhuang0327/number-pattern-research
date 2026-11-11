"""
tests/test_p20_daily_summary_aggregator.py

Unit tests for p20_daily_summary_aggregator module.
"""
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p20_daily_paper_orchestrator_contract import (
    EXPECTED_P16_6_GATE,
    EXPECTED_P17_REPLAY_GATE,
    EXPECTED_P19_GATE,
    P20_BLOCKED_CONTRACT_VIOLATION,
    P20_BLOCKED_P16_6_NOT_READY,
    P20_BLOCKED_P17_REPLAY_NOT_READY,
    P20_BLOCKED_P19_NOT_READY,
    P20_DAILY_PAPER_ORCHESTRATOR_READY,
    P20DailyPaperRunSummary,
)
from wbc_backend.recommendation.p20_daily_summary_aggregator import (
    aggregate_daily_paper_summary,
    load_phase_outputs,
    validate_daily_summary_contract,
    write_daily_summary_outputs,
)
from wbc_backend.recommendation.p20_artifact_manifest import ValidationResult


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_phase_outputs(
    *,
    p16_6_gate: str = EXPECTED_P16_6_GATE,
    p19_gate: str = EXPECTED_P19_GATE,
    p17_gate: str = EXPECTED_P17_REPLAY_GATE,
    n_recommendation_rows: int = 1577,
    n_active: int = 324,
    n_win: int = 171,
    n_loss: int = 153,
    n_unsettled: int = 0,
    paper_only: bool = True,
    production_ready: bool = False,
) -> dict:
    """Build minimal phase_outputs dict matching loader output."""
    ledger_df = pd.DataFrame({
        "game_id": [f"G{i}" for i in range(n_active)],
        "outcome": ["win"] * n_win + ["loss"] * n_loss + ["unsettled"] * n_unsettled,
    })

    p17_replay_summary = {
        "p17_gate": p17_gate,
        "source_p16_6_gate": p16_6_gate,
        "n_recommendation_rows": n_recommendation_rows,
        "n_active_paper_entries": n_active,
        "n_settled_win": n_win,
        "n_settled_loss": n_loss,
        "n_unsettled": n_unsettled,
        "total_stake_units": 81.0,
        "total_pnl_units": 8.73,
        "roi_units": 0.1078,
        "hit_rate": 0.5278,
        "avg_edge": 0.094,
        "avg_odds_decimal": 2.115,
        "max_drawdown_pct": 1.85,
        "sharpe_ratio": 0.10,
        "bankroll_units": 100.0,
        "settlement_join_method": "JOIN_BY_GAME_ID",
        "paper_only": paper_only,
        "production_ready": production_ready,
    }

    p19_gate_data = {
        "gate_decision": p19_gate,
        "game_id_coverage_after": 1.0,
    }

    return {
        "p16_6_summary": {"gate": p16_6_gate},
        "p19_gate": p19_gate_data,
        "p17_replay_summary": p17_replay_summary,
        "p17_replay_ledger_df": ledger_df,
    }


# ---------------------------------------------------------------------------
# aggregate_daily_paper_summary
# ---------------------------------------------------------------------------

class TestAggregateDailyPaperSummary:
    def test_returns_ready_gate_on_happy_path(self):
        outputs = _make_phase_outputs()
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert summary.p20_gate == P20_DAILY_PAPER_ORCHESTRATOR_READY

    def test_blocked_when_p16_6_gate_wrong(self):
        outputs = _make_phase_outputs(p16_6_gate="WRONG_GATE")
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert summary.p20_gate == P20_BLOCKED_P16_6_NOT_READY

    def test_blocked_when_p19_gate_wrong(self):
        outputs = _make_phase_outputs(p19_gate="WRONG_GATE")
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert summary.p20_gate == P20_BLOCKED_P19_NOT_READY

    def test_blocked_when_p17_gate_wrong(self):
        outputs = _make_phase_outputs(p17_gate="WRONG_GATE")
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert summary.p20_gate == P20_BLOCKED_P17_REPLAY_NOT_READY

    def test_blocked_when_unsettled_nonzero(self):
        outputs = _make_phase_outputs(n_win=100, n_loss=100, n_unsettled=5, n_active=205)
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert summary.p20_gate == P20_BLOCKED_CONTRACT_VIOLATION

    def test_blocked_when_production_ready_true(self):
        outputs = _make_phase_outputs(production_ready=True)
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert summary.p20_gate == P20_BLOCKED_CONTRACT_VIOLATION

    def test_safety_invariants_always_set(self):
        outputs = _make_phase_outputs()
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert summary.paper_only is True
        assert summary.production_ready is False

    def test_counts_propagated(self):
        outputs = _make_phase_outputs(n_win=100, n_loss=80, n_unsettled=0, n_active=180, n_recommendation_rows=500)
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert summary.n_settled_win == 100
        assert summary.n_settled_loss == 80
        assert summary.n_unsettled == 0
        assert summary.n_active_paper_entries == 180

    def test_run_date_propagated(self):
        outputs = _make_phase_outputs()
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert summary.run_date == "2026-05-12"

    def test_returns_p20_daily_paper_run_summary_type(self):
        outputs = _make_phase_outputs()
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        assert isinstance(summary, P20DailyPaperRunSummary)


# ---------------------------------------------------------------------------
# validate_daily_summary_contract
# ---------------------------------------------------------------------------

def _make_summary_from_phases(**kwargs) -> P20DailyPaperRunSummary:
    outputs = _make_phase_outputs(**kwargs)
    return aggregate_daily_paper_summary("2026-05-12", outputs)


class TestValidateDailySummaryContract:
    def test_valid_on_happy_path(self):
        summary = _make_summary_from_phases()
        result = validate_daily_summary_contract(summary)
        assert result.valid is True

    def test_invalid_when_p16_6_gate_not_ready(self):
        summary = _make_summary_from_phases(p16_6_gate="WRONG")
        result = validate_daily_summary_contract(summary)
        assert result.valid is False
        assert result.error_code == P20_BLOCKED_P16_6_NOT_READY

    def test_invalid_when_p19_gate_not_ready(self):
        summary = _make_summary_from_phases(p19_gate="WRONG")
        result = validate_daily_summary_contract(summary)
        assert result.valid is False
        assert result.error_code == P20_BLOCKED_P19_NOT_READY

    def test_invalid_when_p17_gate_not_ready(self):
        summary = _make_summary_from_phases(p17_gate="WRONG")
        result = validate_daily_summary_contract(summary)
        assert result.valid is False
        assert result.error_code == P20_BLOCKED_P17_REPLAY_NOT_READY

    def test_invalid_when_unsettled_nonzero(self):
        summary = _make_summary_from_phases(n_win=100, n_loss=100, n_unsettled=5, n_active=205)
        result = validate_daily_summary_contract(summary)
        assert result.valid is False
        assert result.error_code == P20_BLOCKED_CONTRACT_VIOLATION

    def test_returns_validation_result_type(self):
        summary = _make_summary_from_phases()
        result = validate_daily_summary_contract(summary)
        assert isinstance(result, ValidationResult)


# ---------------------------------------------------------------------------
# write_daily_summary_outputs
# ---------------------------------------------------------------------------

class TestWriteDailySummaryOutputs:
    def test_writes_four_files(self, tmp_path):
        outputs = _make_phase_outputs()
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        manifest_summary = {"run_date": "2026-05-12", "total_artifacts": 12,
                            "required_artifacts_present": 8, "required_artifacts_missing": 4,
                            "manifest_sha256": "", "paper_only": True, "production_ready": False,
                            "artifacts": []}

        written = write_daily_summary_outputs(summary, manifest_summary, str(tmp_path))
        assert len(written) == 4

    def test_daily_paper_summary_json_exists(self, tmp_path):
        outputs = _make_phase_outputs()
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        manifest_summary = {"run_date": "2026-05-12", "total_artifacts": 0,
                            "required_artifacts_present": 0, "required_artifacts_missing": 0,
                            "manifest_sha256": "", "paper_only": True, "production_ready": False,
                            "artifacts": []}

        write_daily_summary_outputs(summary, manifest_summary, str(tmp_path))
        assert (tmp_path / "daily_paper_summary.json").exists()

    def test_p20_gate_result_json_has_gate_field(self, tmp_path):
        outputs = _make_phase_outputs()
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        manifest_summary = {"run_date": "2026-05-12", "total_artifacts": 0,
                            "required_artifacts_present": 0, "required_artifacts_missing": 0,
                            "manifest_sha256": "", "paper_only": True, "production_ready": False,
                            "artifacts": []}

        write_daily_summary_outputs(summary, manifest_summary, str(tmp_path))
        gate_data = json.loads((tmp_path / "p20_gate_result.json").read_text())
        assert gate_data["p20_gate"] == P20_DAILY_PAPER_ORCHESTRATOR_READY
        assert gate_data["paper_only"] is True
        assert gate_data["production_ready"] is False

    def test_markdown_file_exists_and_non_empty(self, tmp_path):
        outputs = _make_phase_outputs()
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        manifest_summary = {"run_date": "2026-05-12", "total_artifacts": 0,
                            "required_artifacts_present": 0, "required_artifacts_missing": 0,
                            "manifest_sha256": "", "paper_only": True, "production_ready": False,
                            "artifacts": []}

        write_daily_summary_outputs(summary, manifest_summary, str(tmp_path))
        md = (tmp_path / "daily_paper_summary.md").read_text()
        assert len(md) > 100
        assert "P20_DAILY_PAPER_ORCHESTRATOR_READY" in md

    def test_creates_output_dir_if_missing(self, tmp_path):
        out_dir = tmp_path / "new_subdir" / "p20_out"
        assert not out_dir.exists()

        outputs = _make_phase_outputs()
        summary = aggregate_daily_paper_summary("2026-05-12", outputs)
        manifest_summary = {"run_date": "2026-05-12", "total_artifacts": 0,
                            "required_artifacts_present": 0, "required_artifacts_missing": 0,
                            "manifest_sha256": "", "paper_only": True, "production_ready": False,
                            "artifacts": []}

        write_daily_summary_outputs(summary, manifest_summary, str(out_dir))
        assert out_dir.exists()


# ---------------------------------------------------------------------------
# load_phase_outputs — error cases
# ---------------------------------------------------------------------------

class TestLoadPhaseOutputs:
    def test_raises_file_not_found_when_p17_summary_missing(self, tmp_path):
        p16 = tmp_path / "p16"
        p16.mkdir()
        (p16 / "recommendation_rows.csv").write_text("game_id\n1\n")
        (p16 / "recommendation_summary.json").write_text("{}")

        p19 = tmp_path / "p19"
        p19.mkdir()
        (p19 / "p19_gate_result.json").write_text("{}")
        (p19 / "enriched_simulation_ledger.csv").write_text("game_id\n1\n")
        (p19 / "identity_enrichment_summary.json").write_text("{}")

        p17 = tmp_path / "p17"
        p17.mkdir()  # empty — no required files

        with pytest.raises(FileNotFoundError):
            load_phase_outputs(str(p16), str(p19), str(p17))
