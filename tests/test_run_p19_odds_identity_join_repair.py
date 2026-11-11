"""
tests/test_run_p19_odds_identity_join_repair.py

Integration tests for the P19 CLI script.
"""
from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "run_p19_odds_identity_join_repair.py"
PYTHON = sys.executable


def _make_joined_oof(n: int = 15, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "game_id": [f"G{i:04d}" for i in range(n)],
        "game_date": ["2026-05-01"] * n,
        "home_team": ["TeamA"] * n,
        "away_team": ["TeamB"] * n,
        "p_oof": rng.uniform(0.3, 0.7, n),
        "p_model": rng.uniform(0.3, 0.7, n),
        "p_market": rng.uniform(0.3, 0.7, n),
        "y_true": rng.integers(0, 2, n),
        "fold_id": rng.integers(0, 5, n),
        "odds_decimal_home": rng.uniform(1.5, 3.0, n),
        "odds_decimal_away": rng.uniform(1.5, 3.0, n),
    })
    return df.sort_values("p_oof", ascending=False).reset_index(drop=True)


def _make_simulation_ledger(jof: pd.DataFrame, n_policies: int = 4) -> pd.DataFrame:
    rows = []
    for idx, row in jof.iterrows():
        for i in range(n_policies):
            rows.append({
                "row_idx": idx,
                "y_true": row["y_true"],
                "fold_id": row["fold_id"],
                "p_model": row["p_oof"],  # P15 stores p_oof as p_model
                "p_market": row["p_market"],
                "p_oof": row["p_oof"],
                "policy": f"policy_{i}",
                "should_bet": 1,
                "stake_fraction": 0.05,
            })
    return pd.DataFrame(rows)


def _make_rec_rows(jof: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "game_id": jof["game_id"].tolist(),
        "gate_decision": ["P16_6_ELIGIBLE_PAPER_RECOMMENDATION"] * len(jof),
        "side": ["HOME"] * len(jof),
        "edge": [0.05] * len(jof),
        "stake_fraction": [0.05] * len(jof),
        "p_model": jof["p_model"].tolist(),
        "p_market": jof["p_market"].tolist(),
        "odds_decimal": jof.get("odds_decimal_home", pd.Series([2.0] * len(jof))).tolist(),
        "y_true": jof["y_true"].tolist(),
    })


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


# ── Tests ────────────────────────────────────────────────────────────────────

def test_cli_happy_path(tmp_path):
    jof = _make_joined_oof(n=15, seed=1)
    sim = _make_simulation_ledger(jof)
    rec = _make_rec_rows(jof)

    sim_path = str(tmp_path / "simulation_ledger.csv")
    jof_path = str(tmp_path / "joined_oof.csv")
    rec_path = str(tmp_path / "recommendation_rows.csv")
    out_dir = str(tmp_path / "output")

    sim.to_csv(sim_path, index=False)
    jof.to_csv(jof_path, index=False)
    rec.to_csv(rec_path, index=False)

    result = _run_cli([
        "--p15-ledger", sim_path,
        "--p15-joined", jof_path,
        "--p16-6-recommendation-rows", rec_path,
        "--output-dir", out_dir,
        "--paper-only", "true",
    ])

    assert result.returncode == 0, f"CLI failed:\n{result.stdout}\n{result.stderr}"

    out = Path(out_dir)
    assert (out / "identity_field_audit.json").exists()
    assert (out / "identity_field_audit.md").exists()
    assert (out / "enriched_simulation_ledger.csv").exists()
    assert (out / "identity_enrichment_summary.json").exists()
    assert (out / "identity_enrichment_summary.md").exists()
    assert (out / "settlement_join_repair_audit.json").exists()
    assert (out / "settlement_join_repair_audit.md").exists()
    assert (out / "p19_gate_result.json").exists()

    gate = json.loads((out / "p19_gate_result.json").read_text())
    assert gate["gate_decision"] == "P19_IDENTITY_JOIN_REPAIR_READY"
    assert gate["paper_only"] is True
    assert gate["production_ready"] is False


def test_cli_8_output_files(tmp_path):
    """All 8 expected output files are produced."""
    jof = _make_joined_oof(n=10, seed=2)
    sim = _make_simulation_ledger(jof)
    rec = _make_rec_rows(jof)

    sim_path = str(tmp_path / "simulation_ledger.csv")
    jof_path = str(tmp_path / "joined_oof.csv")
    rec_path = str(tmp_path / "recommendation_rows.csv")
    out_dir = str(tmp_path / "output")

    sim.to_csv(sim_path, index=False)
    jof.to_csv(jof_path, index=False)
    rec.to_csv(rec_path, index=False)

    _run_cli([
        "--p15-ledger", sim_path,
        "--p15-joined", jof_path,
        "--p16-6-recommendation-rows", rec_path,
        "--output-dir", out_dir,
        "--paper-only", "true",
    ])

    out = Path(out_dir)
    expected_files = [
        "identity_field_audit.json",
        "identity_field_audit.md",
        "enriched_simulation_ledger.csv",
        "identity_enrichment_summary.json",
        "identity_enrichment_summary.md",
        "settlement_join_repair_audit.json",
        "settlement_join_repair_audit.md",
        "p19_gate_result.json",
    ]
    for fname in expected_files:
        assert (out / fname).exists(), f"Missing output: {fname}"


def test_cli_deterministic(tmp_path):
    """Two runs must produce identical gate decisions and enriched ledger hashes."""
    jof = _make_joined_oof(n=12, seed=3)
    sim = _make_simulation_ledger(jof)
    rec = _make_rec_rows(jof)

    sim_path = str(tmp_path / "simulation_ledger.csv")
    jof_path = str(tmp_path / "joined_oof.csv")
    rec_path = str(tmp_path / "recommendation_rows.csv")

    sim.to_csv(sim_path, index=False)
    jof.to_csv(jof_path, index=False)
    rec.to_csv(rec_path, index=False)

    results = []
    for i in range(2):
        out_dir = str(tmp_path / f"output_run{i}")
        _run_cli([
            "--p15-ledger", sim_path,
            "--p15-joined", jof_path,
            "--p16-6-recommendation-rows", rec_path,
            "--output-dir", out_dir,
            "--paper-only", "true",
        ])
        gate = json.loads((Path(out_dir) / "p19_gate_result.json").read_text())
        enriched = pd.read_csv(Path(out_dir) / "enriched_simulation_ledger.csv")
        results.append((gate["gate_decision"], enriched["game_id"].tolist()))

    assert results[0][0] == results[1][0], "Gate decisions differ between runs"
    assert results[0][1] == results[1][1], "Enriched game_ids differ between runs"


def test_cli_missing_input_exits_2(tmp_path):
    result = _run_cli([
        "--p15-ledger", str(tmp_path / "nonexistent.csv"),
        "--p15-joined", str(tmp_path / "nonexistent2.csv"),
        "--p16-6-recommendation-rows", str(tmp_path / "nonexistent3.csv"),
        "--output-dir", str(tmp_path / "output"),
        "--paper-only", "true",
    ])
    assert result.returncode == 2


def test_cli_paper_only_guard(tmp_path):
    result = _run_cli([
        "--p15-ledger", str(tmp_path / "x.csv"),
        "--p15-joined", str(tmp_path / "y.csv"),
        "--p16-6-recommendation-rows", str(tmp_path / "z.csv"),
        "--output-dir", str(tmp_path / "output"),
        "--paper-only", "false",
    ])
    assert result.returncode == 2


def test_cli_blocked_when_no_game_id_in_joined(tmp_path):
    """If joined_oof has no game_id, P19 must block."""
    jof = _make_joined_oof(n=10, seed=5)
    jof_no_id = jof.drop(columns=["game_id"])
    sim = _make_simulation_ledger(jof)
    rec = _make_rec_rows(jof)

    sim_path = str(tmp_path / "simulation_ledger.csv")
    jof_path = str(tmp_path / "joined_oof.csv")
    rec_path = str(tmp_path / "recommendation_rows.csv")
    out_dir = str(tmp_path / "output")

    sim.to_csv(sim_path, index=False)
    jof_no_id.to_csv(jof_path, index=False)
    rec.to_csv(rec_path, index=False)

    result = _run_cli([
        "--p15-ledger", sim_path,
        "--p15-joined", jof_path,
        "--p16-6-recommendation-rows", rec_path,
        "--output-dir", out_dir,
        "--paper-only", "true",
    ])

    assert result.returncode == 1
    gate = json.loads((Path(out_dir) / "p19_gate_result.json").read_text())
    assert "BLOCKED" in gate["gate_decision"]
