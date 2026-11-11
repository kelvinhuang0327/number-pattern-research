"""
tests/test_run_p18_strategy_policy_risk_repair.py

Integration tests for scripts/run_p18_strategy_policy_risk_repair.py
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# Ensure project root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.run_p18_strategy_policy_risk_repair import main


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_minimal_ledger(n: int = 300) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "row_idx": i,
            "fold_id": i % 5,
            "y_true": 1 if i % 5 != 0 else 0,
            "p_model": 0.70,
            "p_market": 0.55,
            "decimal_odds": 1.80,
            "confidence_rank": 1,
            "policy": "capped_kelly",
            "should_bet": True,
            "stake_fraction": 0.02,
            "reason": "POLICY_SELECTED",
            "paper_only": True,
        })
    return pd.DataFrame(rows)


def _make_p16_summary(edge_threshold: float = 0.08) -> dict:
    return {
        "p16_gate": "P16_BLOCKED_RISK_PROFILE_VIOLATION",
        "strategy_max_drawdown": 44.80,
        "strategy_sharpe": 0.0937,
        "strategy_n_bets": 247,
        "selected_edge_threshold": edge_threshold,
        "paper_only": True,
        "production_ready": False,
    }


@pytest.fixture
def tmp_dirs(tmp_path: Path):
    ledger_df = _make_minimal_ledger(300)
    ledger_path = tmp_path / "simulation_ledger.csv"
    ledger_df.to_csv(ledger_path, index=False)

    p16_summary = _make_p16_summary()
    p16_path = tmp_path / "recommendation_summary.json"
    p16_path.write_text(json.dumps(p16_summary))

    out_dir = tmp_path / "p18_out"
    return ledger_path, p16_path, out_dir


# ── Output file presence ───────────────────────────────────────────────────────

def test_cli_emits_all_required_files(tmp_dirs):
    ledger_path, p16_path, out_dir = tmp_dirs
    rc = main([
        "--p15-ledger", str(ledger_path),
        "--p16-summary", str(p16_path),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--min-bets-floor", "10",
        "--bootstrap-n-iter", "50",
    ])
    assert rc == 0
    expected_files = [
        "strategy_policy_grid.csv",
        "strategy_policy_grid_summary.json",
        "strategy_policy_grid_summary.md",
        "selected_strategy_policy.json",
        "drawdown_diagnostics.json",
        "drawdown_diagnostics.md",
    ]
    for fname in expected_files:
        assert (out_dir / fname).exists(), f"Missing: {fname}"


# ── Determinism ────────────────────────────────────────────────────────────────

def test_cli_deterministic(tmp_path: Path):
    ledger_df = _make_minimal_ledger(300)
    ledger_path = tmp_path / "simulation_ledger.csv"
    ledger_df.to_csv(ledger_path, index=False)
    p16_path = tmp_path / "recommendation_summary.json"
    p16_path.write_text(json.dumps(_make_p16_summary()))

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    main([
        "--p15-ledger", str(ledger_path),
        "--p16-summary", str(p16_path),
        "--output-dir", str(out1),
        "--paper-only", "true",
        "--min-bets-floor", "10",
        "--bootstrap-n-iter", "50",
    ])
    main([
        "--p15-ledger", str(ledger_path),
        "--p16-summary", str(p16_path),
        "--output-dir", str(out2),
        "--paper-only", "true",
        "--min-bets-floor", "10",
        "--bootstrap-n-iter", "50",
    ])

    # Compare files excluding generated_at_utc
    for fname in ["strategy_policy_grid_summary.json", "selected_strategy_policy.json",
                  "drawdown_diagnostics.json"]:
        j1 = json.loads((out1 / fname).read_text())
        j2 = json.loads((out2 / fname).read_text())
        # Remove generated_at_utc before comparing
        j1.pop("generated_at_utc", None)
        j2.pop("generated_at_utc", None)
        assert j1 == j2, f"Determinism failure in {fname}"

    # Compare CSV
    text1 = (out1 / "strategy_policy_grid.csv").read_text()
    text2 = (out2 / "strategy_policy_grid.csv").read_text()
    assert text1 == text2, "Determinism failure in strategy_policy_grid.csv"


# ── paper_only invariants ──────────────────────────────────────────────────────

def test_paper_only_true_in_summary(tmp_dirs):
    ledger_path, p16_path, out_dir = tmp_dirs
    main([
        "--p15-ledger", str(ledger_path),
        "--p16-summary", str(p16_path),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--min-bets-floor", "10",
        "--bootstrap-n-iter", "50",
    ])
    summary = json.loads((out_dir / "strategy_policy_grid_summary.json").read_text())
    assert summary["paper_only"] is True
    selected = json.loads((out_dir / "selected_strategy_policy.json").read_text())
    assert selected["paper_only"] is True
    diag = json.loads((out_dir / "drawdown_diagnostics.json").read_text())
    assert diag["paper_only"] is True


def test_production_ready_false_in_all_outputs(tmp_dirs):
    ledger_path, p16_path, out_dir = tmp_dirs
    main([
        "--p15-ledger", str(ledger_path),
        "--p16-summary", str(p16_path),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--min-bets-floor", "10",
        "--bootstrap-n-iter", "50",
    ])
    summary = json.loads((out_dir / "strategy_policy_grid_summary.json").read_text())
    assert summary["production_ready"] is False
    selected = json.loads((out_dir / "selected_strategy_policy.json").read_text())
    assert selected["production_ready"] is False
    diag = json.loads((out_dir / "drawdown_diagnostics.json").read_text())
    assert diag["production_ready"] is False


# ── Safety guards ──────────────────────────────────────────────────────────────

def test_paper_only_false_returns_nonzero(tmp_dirs):
    ledger_path, p16_path, out_dir = tmp_dirs
    rc = main([
        "--p15-ledger", str(ledger_path),
        "--p16-summary", str(p16_path),
        "--output-dir", str(out_dir),
        "--paper-only", "false",   # <-- forbidden
        "--min-bets-floor", "10",
    ])
    assert rc != 0


def test_missing_ledger_returns_nonzero(tmp_path: Path):
    p16_path = tmp_path / "recommendation_summary.json"
    p16_path.write_text(json.dumps(_make_p16_summary()))
    out_dir = tmp_path / "out"
    rc = main([
        "--p15-ledger", str(tmp_path / "DOES_NOT_EXIST.csv"),
        "--p16-summary", str(p16_path),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--min-bets-floor", "10",
    ])
    assert rc != 0


def test_missing_p16_summary_returns_nonzero(tmp_path: Path):
    ledger_df = _make_minimal_ledger(100)
    ledger_path = tmp_path / "simulation_ledger.csv"
    ledger_df.to_csv(ledger_path, index=False)
    out_dir = tmp_path / "out"
    rc = main([
        "--p15-ledger", str(ledger_path),
        "--p16-summary", str(tmp_path / "DOES_NOT_EXIST.json"),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--min-bets-floor", "10",
    ])
    assert rc != 0


# ── CSV column check ───────────────────────────────────────────────────────────

def test_grid_csv_has_required_columns(tmp_dirs):
    ledger_path, p16_path, out_dir = tmp_dirs
    main([
        "--p15-ledger", str(ledger_path),
        "--p16-summary", str(p16_path),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--min-bets-floor", "10",
        "--bootstrap-n-iter", "50",
    ])
    csv_path = out_dir / "strategy_policy_grid.csv"
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
    required = [
        "policy_id", "edge_threshold", "max_stake_cap", "kelly_fraction",
        "odds_decimal_max", "n_bets", "roi_mean", "roi_ci_low_95",
        "roi_ci_high_95", "max_drawdown_pct", "sharpe_ratio", "hit_rate",
        "policy_pass", "fail_reasons",
    ]
    for col in required:
        assert col in fieldnames, f"Missing CSV column: {col}"


# ── Selected policy JSON ───────────────────────────────────────────────────────

def test_selected_policy_json_has_required_fields(tmp_dirs):
    ledger_path, p16_path, out_dir = tmp_dirs
    main([
        "--p15-ledger", str(ledger_path),
        "--p16-summary", str(p16_path),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--min-bets-floor", "10",
        "--bootstrap-n-iter", "50",
    ])
    selected = json.loads((out_dir / "selected_strategy_policy.json").read_text())
    required_keys = {
        "selected_policy_id", "edge_threshold", "max_stake_cap",
        "kelly_fraction", "odds_decimal_max", "n_bets",
        "roi_mean", "roi_ci_low_95", "roi_ci_high_95",
        "max_drawdown_pct", "sharpe_ratio", "hit_rate",
        "selection_reason", "gate_decision",
        "paper_only", "production_ready",
    }
    for key in required_keys:
        assert key in selected, f"Missing key in selected_strategy_policy.json: {key}"
