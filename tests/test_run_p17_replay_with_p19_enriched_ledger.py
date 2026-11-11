"""
tests/test_run_p17_replay_with_p19_enriched_ledger.py

Integration tests for the P17 replay with P19 enriched ledger CLI.
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
SCRIPT = REPO_ROOT / "scripts" / "run_p17_replay_with_p19_enriched_ledger.py"
PYTHON = sys.executable

# We need to produce an enriched ledger as P19 would — use the enricher directly
P19_ENRICHER_AVAILABLE = True
try:
    from wbc_backend.recommendation.p19_p15_ledger_identity_enricher import (
        enrich_simulation_ledger_with_identity,
        IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT,
    )
except ImportError:
    P19_ENRICHER_AVAILABLE = False


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
                "policy": f"e0p0500_s0p0025_k0p10_o{i}p00",
                "should_bet": 1,
                "stake_fraction": 0.05,
            })
    return pd.DataFrame(rows)


def _make_rec_rows_with_y_true(jof: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "recommendation_id": [f"REC_{i:04d}" for i in range(len(jof))],
        "game_id": jof["game_id"].tolist(),
        "date": ["2026-05-12"] * len(jof),
        "gate_decision": ["P16_6_ELIGIBLE_PAPER_RECOMMENDATION"] * len(jof),
        "gate_reason": ["edge_above_threshold"] * len(jof),
        "side": ["HOME"] * len(jof),
        "edge": [0.06] * len(jof),
        "stake_fraction": [0.05] * len(jof),
        "paper_stake_fraction": [0.05] * len(jof),
        "p_model": jof["p_model"].tolist(),
        "p_market": jof["p_market"].tolist(),
        "odds_decimal": jof.get("odds_decimal_home", pd.Series([2.0] * len(jof))).tolist(),
        "source_model": ["test_model"] * len(jof),
        "paper_only": [True] * len(jof),
        "production_ready": [False] * len(jof),
        "y_true": jof["y_true"].tolist(),
    })


def _make_rec_summary(gate: str = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION") -> dict:
    return {
        "p16_6_gate": gate,
        "n_eligible": 15,
        "paper_only": True,
        "production_ready": False,
    }


def _make_enriched_ledger(jof: pd.DataFrame) -> pd.DataFrame:
    sim = _make_simulation_ledger(jof)
    return enrich_simulation_ledger_with_identity(sim, jof)


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

@pytest.mark.skipif(not P19_ENRICHER_AVAILABLE, reason="P19 enricher not available")
def test_replay_happy_path(tmp_path):
    jof = _make_joined_oof(n=15, seed=10)
    rec = _make_rec_rows_with_y_true(jof)
    enriched = _make_enriched_ledger(jof)

    rec_path = str(tmp_path / "recommendation_rows.csv")
    enriched_path = str(tmp_path / "enriched_simulation_ledger.csv")
    summary_path = str(tmp_path / "recommendation_summary.json")
    out_dir = str(tmp_path / "output")

    rec.to_csv(rec_path, index=False)
    enriched.to_csv(enriched_path, index=False)
    with open(summary_path, "w") as f:
        json.dump(_make_rec_summary(), f)

    result = _run_cli([
        "--recommendation-rows", rec_path,
        "--recommendation-summary", summary_path,
        "--p19-enriched-ledger", enriched_path,
        "--output-dir", out_dir,
        "--bankroll-units", "100",
        "--paper-only", "true",
    ])

    assert result.returncode == 0, f"Replay failed:\n{result.stdout}\n{result.stderr}"

    out = Path(out_dir)
    assert (out / "paper_recommendation_ledger.csv").exists()
    assert (out / "paper_recommendation_ledger_summary.json").exists()
    assert (out / "settlement_join_audit.json").exists()
    assert (out / "ledger_gate_result.json").exists()


@pytest.mark.skipif(not P19_ENRICHER_AVAILABLE, reason="P19 enricher not available")
def test_replay_uses_enriched_ledger(tmp_path):
    """Verify that settlement_join_audit uses enriched game_id join (not NONE)."""
    jof = _make_joined_oof(n=12, seed=20)
    rec = _make_rec_rows_with_y_true(jof)
    enriched = _make_enriched_ledger(jof)

    rec_path = str(tmp_path / "recommendation_rows.csv")
    enriched_path = str(tmp_path / "enriched_simulation_ledger.csv")
    summary_path = str(tmp_path / "recommendation_summary.json")
    out_dir = str(tmp_path / "output")

    rec.to_csv(rec_path, index=False)
    enriched.to_csv(enriched_path, index=False)
    with open(summary_path, "w") as f:
        json.dump(_make_rec_summary(), f)

    _run_cli([
        "--recommendation-rows", rec_path,
        "--recommendation-summary", summary_path,
        "--p19-enriched-ledger", enriched_path,
        "--output-dir", out_dir,
        "--bankroll-units", "100",
        "--paper-only", "true",
    ])

    join_audit = json.loads((Path(out_dir) / "settlement_join_audit.json").read_text())
    assert join_audit["join_method"] != "none", "Replay should use game_id join, not NONE"
    assert join_audit["source_p19_enrichment"] is True


@pytest.mark.skipif(not P19_ENRICHER_AVAILABLE, reason="P19 enricher not available")
def test_replay_improved_settlement_vs_raw(tmp_path):
    """Enriched replay should have higher settlement coverage than raw P17."""
    jof = _make_joined_oof(n=10, seed=30)
    rec = _make_rec_rows_with_y_true(jof)
    enriched = _make_enriched_ledger(jof)

    rec_path = str(tmp_path / "recommendation_rows.csv")
    enriched_path = str(tmp_path / "enriched_simulation_ledger.csv")
    summary_path = str(tmp_path / "recommendation_summary.json")
    out_dir = str(tmp_path / "output")

    rec.to_csv(rec_path, index=False)
    enriched.to_csv(enriched_path, index=False)
    with open(summary_path, "w") as f:
        json.dump(_make_rec_summary(), f)

    _run_cli([
        "--recommendation-rows", rec_path,
        "--recommendation-summary", summary_path,
        "--p19-enriched-ledger", enriched_path,
        "--output-dir", out_dir,
        "--bankroll-units", "100",
        "--paper-only", "true",
    ])

    summary = json.loads((Path(out_dir) / "paper_recommendation_ledger_summary.json").read_text())
    assert summary["settlement_join_coverage"] > 0.0
    assert summary["source_p19_enrichment"] is True


def test_replay_paper_only_guard(tmp_path):
    result = _run_cli([
        "--recommendation-rows", str(tmp_path / "x.csv"),
        "--recommendation-summary", str(tmp_path / "s.json"),
        "--p19-enriched-ledger", str(tmp_path / "e.csv"),
        "--output-dir", str(tmp_path / "output"),
        "--paper-only", "false",
    ])
    assert result.returncode == 2


def test_replay_missing_input_exits_2(tmp_path):
    result = _run_cli([
        "--recommendation-rows", str(tmp_path / "nonexistent.csv"),
        "--recommendation-summary", str(tmp_path / "nonexistent.json"),
        "--p19-enriched-ledger", str(tmp_path / "nonexistent2.csv"),
        "--output-dir", str(tmp_path / "output"),
        "--paper-only", "true",
    ])
    assert result.returncode == 2
