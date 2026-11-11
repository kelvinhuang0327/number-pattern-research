"""
tests/test_run_p16_recommendation_gate_reevaluation.py

Integration tests for scripts/run_p16_recommendation_gate_reevaluation.py

Test cases:
- CLI emits all 7 required output files
- CLI is deterministic across two runs
- recommendation_rows.csv has required columns including risk profile fields
- gate_reason_counts.json is valid JSON
- strategy_risk_profile.json has required fields
- edge_threshold_sweep.json has per_threshold entries
- paper_only=true enforced / production_ready=false
- failed rows have stake 0
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from scripts.run_p16_recommendation_gate_reevaluation import main as cli_main


# ── Fixtures ──────────────────────────────────────────────────────────────────

P15_DIR = Path("outputs/predictions/PAPER/2026-05-12/p15_market_odds_simulation")
JOINED_OOF = P15_DIR / "joined_oof_with_odds.csv"
P15_SUMMARY = P15_DIR / "simulation_summary.json"
P15_LEDGER = P15_DIR / "simulation_ledger.csv"


def _skip_if_missing():
    if not JOINED_OOF.exists() or not P15_SUMMARY.exists() or not P15_LEDGER.exists():
        pytest.skip("P15 artifacts not present — integration test skipped")


REQUIRED_OUTPUT_FILES = [
    "recommendation_rows.csv",
    "recommendation_summary.json",
    "recommendation_summary.md",
    "gate_reason_counts.json",
    "strategy_risk_profile.json",
    "edge_threshold_sweep.json",
    "edge_threshold_sweep.md",
]

REQUIRED_ROW_COLUMNS = [
    "recommendation_id",
    "game_id",
    "date",
    "side",
    "p_model",
    "p_market",
    "edge",
    "odds_decimal",
    "paper_stake_fraction",
    "strategy_policy",
    "gate_decision",
    "gate_reason",
    "source_model",
    "source_bss_oof",
    "odds_join_status",
    "paper_only",
    "production_ready",
    "created_from",
    "strategy_risk_profile_roi_ci_low_95",
    "strategy_risk_profile_roi_ci_high_95",
    "strategy_risk_profile_max_drawdown",
    "strategy_risk_profile_sharpe",
    "strategy_risk_profile_n_bets",
    "selected_edge_threshold",
]


def _run_cli(output_dir: str) -> int:
    return cli_main([
        "--joined-oof", str(JOINED_OOF),
        "--p15-summary", str(P15_SUMMARY),
        "--p15-ledger", str(P15_LEDGER),
        "--output-dir", output_dir,
        "--paper-only", "true",
        "--edge-threshold-grid", "0.01,0.02,0.03,0.05,0.08",
        "--min-bets-floor", "50",
        "--max-drawdown-limit", "0.25",
        "--sharpe-floor", "0.0",
    ])


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_cli_exits_zero():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        rc = _run_cli(tmpdir)
        assert rc == 0


def test_cli_emits_all_required_files():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        outdir = Path(tmpdir)
        for fname in REQUIRED_OUTPUT_FILES:
            assert (outdir / fname).exists(), f"Missing output: {fname}"


def test_recommendation_rows_has_required_columns():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        df = pd.read_csv(Path(tmpdir) / "recommendation_rows.csv")
        for col in REQUIRED_ROW_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"


def test_paper_only_true_in_all_rows():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        df = pd.read_csv(Path(tmpdir) / "recommendation_rows.csv")
        assert df["paper_only"].all(), "paper_only must be True for all rows"


def test_production_ready_false_in_all_rows():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        df = pd.read_csv(Path(tmpdir) / "recommendation_rows.csv")
        assert not df["production_ready"].any(), "production_ready must be False"


def test_failed_rows_have_zero_stake():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        df = pd.read_csv(Path(tmpdir) / "recommendation_rows.csv")
        eligible_mask = df["gate_decision"] == "P16_ELIGIBLE_PAPER_RECOMMENDATION"
        blocked = df[~eligible_mask]
        assert (blocked["paper_stake_fraction"] == 0.0).all(), \
            "All blocked rows must have stake=0"


def test_passed_rows_carry_risk_profile_fields():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        df = pd.read_csv(Path(tmpdir) / "recommendation_rows.csv")
        eligible = df[df["gate_decision"] == "P16_ELIGIBLE_PAPER_RECOMMENDATION"]
        if len(eligible) > 0:
            assert eligible["strategy_risk_profile_n_bets"].notna().all()
            assert eligible["strategy_risk_profile_sharpe"].notna().all()
            assert eligible["strategy_risk_profile_max_drawdown"].notna().all()


def test_gate_reason_counts_valid_json():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        path = Path(tmpdir) / "gate_reason_counts.json"
        data = json.loads(path.read_text())
        assert isinstance(data, dict)
        assert len(data) > 0


def test_strategy_risk_profile_has_required_fields():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        data = json.loads((Path(tmpdir) / "strategy_risk_profile.json").read_text())
        for field in [
            "roi_mean", "roi_ci_low_95", "roi_ci_high_95",
            "max_drawdown_pct", "sharpe_ratio", "n_bets",
            "paper_only", "production_ready", "selected_edge_threshold",
        ]:
            assert field in data, f"Missing field: {field}"
        assert data["paper_only"] is True
        assert data["production_ready"] is False


def test_edge_threshold_sweep_has_per_threshold():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        data = json.loads((Path(tmpdir) / "edge_threshold_sweep.json").read_text())
        assert "per_threshold" in data
        assert len(data["per_threshold"]) == 5  # 5 thresholds in grid
        for entry in data["per_threshold"]:
            assert "threshold" in entry
            assert "n_bets" in entry
            assert "sharpe_ratio" in entry


def test_summary_json_has_required_fields():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        _run_cli(tmpdir)
        data = json.loads((Path(tmpdir) / "recommendation_summary.json").read_text())
        for field in [
            "p16_gate", "n_input_rows", "n_joined_rows", "n_eligible_rows",
            "n_recommended_rows", "n_blocked_rows", "selected_edge_threshold",
            "strategy_roi_mean", "strategy_roi_ci_low_95", "strategy_roi_ci_high_95",
            "strategy_max_drawdown", "strategy_sharpe", "strategy_n_bets",
            "source_bss_oof", "production_ready", "paper_only",
        ]:
            assert field in data, f"Missing summary field: {field}"
        assert data["production_ready"] is False
        assert data["paper_only"] is True


def test_cli_deterministic_two_runs():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        _run_cli(tmp1)
        _run_cli(tmp2)

        # Compare recommendation_summary.json (excluding generated_at)
        s1 = json.loads((Path(tmp1) / "recommendation_summary.json").read_text())
        s2 = json.loads((Path(tmp2) / "recommendation_summary.json").read_text())
        # Remove generated_at before comparing
        s1.pop("generated_at_utc", None)
        s2.pop("generated_at_utc", None)
        assert s1 == s2, "recommendation_summary.json not deterministic"

        # Compare gate_reason_counts.json
        g1 = json.loads((Path(tmp1) / "gate_reason_counts.json").read_text())
        g2 = json.loads((Path(tmp2) / "gate_reason_counts.json").read_text())
        assert g1 == g2, "gate_reason_counts.json not deterministic"

        # Compare strategy_risk_profile.json (excluding generated_at if present)
        r1 = json.loads((Path(tmp1) / "strategy_risk_profile.json").read_text())
        r2 = json.loads((Path(tmp2) / "strategy_risk_profile.json").read_text())
        assert r1 == r2, "strategy_risk_profile.json not deterministic"

        # Compare edge_threshold_sweep.json
        e1 = json.loads((Path(tmp1) / "edge_threshold_sweep.json").read_text())
        e2 = json.loads((Path(tmp2) / "edge_threshold_sweep.json").read_text())
        assert e1 == e2, "edge_threshold_sweep.json not deterministic"

        # Compare recommendation_rows.csv row count and gate decisions
        df1 = pd.read_csv(Path(tmp1) / "recommendation_rows.csv")
        df2 = pd.read_csv(Path(tmp2) / "recommendation_rows.csv")
        assert len(df1) == len(df2), "recommendation_rows.csv row count differs"
        assert (df1["gate_decision"] == df2["gate_decision"]).all(), \
            "recommendation_rows.csv gate decisions not deterministic"


def test_paper_only_false_arg_returns_error():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmpdir:
        rc = cli_main([
            "--joined-oof", str(JOINED_OOF),
            "--p15-summary", str(P15_SUMMARY),
            "--p15-ledger", str(P15_LEDGER),
            "--output-dir", tmpdir,
            "--paper-only", "false",
        ])
        assert rc != 0
