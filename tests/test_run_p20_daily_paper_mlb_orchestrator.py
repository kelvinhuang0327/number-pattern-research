"""
tests/test_run_p20_daily_paper_mlb_orchestrator.py

Integration tests for scripts/run_p20_daily_paper_mlb_orchestrator.py CLI.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "run_p20_daily_paper_mlb_orchestrator.py"
PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [PYTHON, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_p16_6_dir(root: Path) -> Path:
    d = root / "p16_6"
    d.mkdir()
    (d / "recommendation_rows.csv").write_text(
        "game_id,model_p,y_true\nG001,0.6,1\nG002,0.55,0\n"
    )
    (d / "recommendation_summary.json").write_text(json.dumps({
        "gate": "P16_6_PAPER_RECOMMENDATION_GATE_READY",
        "paper_only": True,
        "production_ready": False,
    }))
    return d


def _make_p19_dir(root: Path) -> Path:
    d = root / "p19"
    d.mkdir()
    (d / "enriched_simulation_ledger.csv").write_text(
        "game_id,p_model,y_true\nG001,0.6,1\nG002,0.55,0\n"
    )
    (d / "identity_enrichment_summary.json").write_text(json.dumps({
        "enrichment_method": "IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT",
    }))
    (d / "p19_gate_result.json").write_text(json.dumps({
        "gate_decision": "P19_IDENTITY_JOIN_REPAIR_READY",
        "paper_only": True,
        "production_ready": False,
        "game_id_coverage_after": 1.0,
    }))
    return d


def _make_p17_replay_dir(root: Path) -> Path:
    d = root / "p17_replay"
    d.mkdir()
    (d / "paper_recommendation_ledger.csv").write_text(
        "game_id,pnl_units,outcome\nG001,1.0,win\nG002,-1.0,loss\n"
    )
    (d / "paper_recommendation_ledger_summary.json").write_text(json.dumps({
        "p17_gate": "P17_PAPER_LEDGER_READY",
        "source_p16_6_gate": "P16_6_PAPER_RECOMMENDATION_GATE_READY",
        "source_p19_enrichment": True,
        "n_recommendation_rows": 2,
        "n_active_paper_entries": 2,
        "n_settled_win": 1,
        "n_settled_loss": 1,
        "n_settled_push": 0,
        "n_unsettled": 0,
        "total_stake_units": 2.0,
        "total_pnl_units": 0.0,
        "roi_units": 0.0,
        "hit_rate": 0.5,
        "avg_edge": 0.05,
        "avg_odds_decimal": 2.0,
        "max_drawdown_pct": 1.0,
        "sharpe_ratio": 0.0,
        "settlement_join_method": "JOIN_BY_GAME_ID",
        "duplicate_game_id_count": 0,
        "unmatched_recommendation_count": 0,
        "paper_only": True,
        "production_ready": False,
        "bankroll_units": 100.0,
    }))
    (d / "ledger_gate_result.json").write_text(json.dumps({
        "p17_gate": "P17_PAPER_LEDGER_READY",
        "paper_only": True,
        "production_ready": False,
    }))
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestP20OrchestratorCLI:
    def test_exit_0_on_happy_path(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        result = _run_cli([
            "--run-date", "2026-05-12",
            "--p16-6-dir", str(p16),
            "--p19-dir", str(p19),
            "--p17-replay-dir", str(p17),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])

        assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
        assert "P20_DAILY_PAPER_ORCHESTRATOR_READY" in result.stdout

    def test_four_output_files_created(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        _run_cli([
            "--run-date", "2026-05-12",
            "--p16-6-dir", str(p16),
            "--p19-dir", str(p19),
            "--p17-replay-dir", str(p17),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])

        assert (out / "daily_paper_summary.json").exists()
        assert (out / "daily_paper_summary.md").exists()
        assert (out / "artifact_manifest.json").exists()
        assert (out / "p20_gate_result.json").exists()

    def test_gate_result_json_has_correct_fields(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        _run_cli([
            "--run-date", "2026-05-12",
            "--p16-6-dir", str(p16),
            "--p19-dir", str(p19),
            "--p17-replay-dir", str(p17),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])

        gate_data = json.loads((out / "p20_gate_result.json").read_text())
        assert gate_data["p20_gate"] == "P20_DAILY_PAPER_ORCHESTRATOR_READY"
        assert gate_data["paper_only"] is True
        assert gate_data["production_ready"] is False
        assert gate_data["n_unsettled"] == 0

    def test_exit_1_when_p17_gate_wrong(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        # Corrupt P17 gate
        (p17 / "paper_recommendation_ledger_summary.json").write_text(json.dumps({
            "p17_gate": "WRONG_GATE",
            "source_p16_6_gate": "P16_6_PAPER_RECOMMENDATION_GATE_READY",
            "n_recommendation_rows": 2,
            "n_active_paper_entries": 2,
            "n_settled_win": 1,
            "n_settled_loss": 1,
            "n_unsettled": 0,
            "total_stake_units": 2.0,
            "total_pnl_units": 0.0,
            "roi_units": 0.0,
            "hit_rate": 0.5,
            "avg_edge": 0.05,
            "avg_odds_decimal": 2.0,
            "max_drawdown_pct": 1.0,
            "sharpe_ratio": 0.0,
            "settlement_join_method": "JOIN_BY_GAME_ID",
            "paper_only": True,
            "production_ready": False,
            "bankroll_units": 100.0,
        }))
        out = tmp_path / "p20_out"

        result = _run_cli([
            "--run-date", "2026-05-12",
            "--p16-6-dir", str(p16),
            "--p19-dir", str(p19),
            "--p17-replay-dir", str(p17),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])

        assert result.returncode == 1

    def test_exit_2_when_paper_only_false(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        result = _run_cli([
            "--run-date", "2026-05-12",
            "--p16-6-dir", str(p16),
            "--p19-dir", str(p19),
            "--p17-replay-dir", str(p17),
            "--output-dir", str(out),
            "--paper-only", "false",
        ])

        assert result.returncode == 2

    def test_exit_2_when_p17_dir_missing(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        out = tmp_path / "p20_out"

        result = _run_cli([
            "--run-date", "2026-05-12",
            "--p16-6-dir", str(p16),
            "--p19-dir", str(p19),
            "--p17-replay-dir", str(tmp_path / "nonexistent"),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])

        assert result.returncode in (1, 2)

    def test_determinism_gate_json(self, tmp_path):
        """Running twice produces identical gate results (excluding generated_at)."""
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        args = [
            "--run-date", "2026-05-12",
            "--p16-6-dir", str(p16),
            "--p19-dir", str(p19),
            "--p17-replay-dir", str(p17),
            "--paper-only", "true",
        ]

        _run_cli(args + ["--output-dir", str(out1)])
        _run_cli(args + ["--output-dir", str(out2)])

        g1 = json.loads((out1 / "p20_gate_result.json").read_text())
        g2 = json.loads((out2 / "p20_gate_result.json").read_text())

        for key in g1:
            if key == "generated_at":
                continue
            assert g1[key] == g2[key], f"Non-deterministic key: {key}"
