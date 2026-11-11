"""
tests/test_p19_identity_field_audit.py

Unit tests for P19 identity field audit module.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from wbc_backend.recommendation.p19_identity_field_audit import (
    detect_available_join_keys,
    detect_game_id_coverage,
    detect_duplicate_identity_keys,
    compare_p15_joined_vs_simulation_ledger,
    audit_identity_columns,
    CoverageReport,
    IdentityComparison,
    IdentityFieldAudit,
    COVERAGE_HIGH,
    COVERAGE_MEDIUM,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_joined_oof(n: int = 10, seed: int = 42) -> pd.DataFrame:
    """Create a minimal joined_oof_with_odds DataFrame with game_id."""
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
    # Sort by p_oof descending to simulate P15 behavior
    df = df.sort_values("p_oof", ascending=False).reset_index(drop=True)
    return df


def _make_simulation_ledger(joined_oof_df: pd.DataFrame, n_policies: int = 4) -> pd.DataFrame:
    """Build a simulation_ledger with n_policies per row_idx, matching joined_oof."""
    rows = []
    policies = [f"policy_{i}" for i in range(n_policies)]
    for row_idx, row in joined_oof_df.iterrows():
        for policy in policies:
            rows.append({
                "row_idx": row_idx,
                "y_true": row["y_true"],
                "fold_id": row["fold_id"],
                "p_model": row["p_oof"],  # P15 stores p_oof as p_model in ledger
                "p_market": row["p_market"],
                "policy": policy,
                "should_bet": 1,
                "stake_fraction": 0.05,
            })
    return pd.DataFrame(rows)


# ── Tests: detect_available_join_keys ────────────────────────────────────────

def test_detect_join_keys_empty():
    df = pd.DataFrame({"foo": [1, 2]})
    keys = detect_available_join_keys(df)
    assert keys == []


def test_detect_join_keys_present():
    df = pd.DataFrame({
        "game_id": ["G001"],
        "y_true": [1],
        "unrelated_col": [99],
    })
    keys = detect_available_join_keys(df)
    assert "game_id" in keys
    assert "y_true" in keys
    assert "unrelated_col" not in keys


# ── Tests: detect_game_id_coverage ──────────────────────────────────────────

def test_game_id_coverage_full():
    df = pd.DataFrame({"game_id": [f"G{i}" for i in range(20)]})
    report = detect_game_id_coverage(df)
    assert report.coverage == 1.0
    assert report.quality == "HIGH"
    assert report.n_non_null == 20
    assert report.unique_count == 20


def test_game_id_coverage_missing_column():
    df = pd.DataFrame({"other": [1, 2, 3]})
    report = detect_game_id_coverage(df)
    assert report.coverage == 0.0
    assert report.quality == "NONE"
    assert report.n_non_null == 0


def test_game_id_coverage_partial():
    df = pd.DataFrame({"game_id": ["G001", None, None, None]})
    report = detect_game_id_coverage(df)
    assert report.n_non_null == 1
    assert report.coverage == pytest.approx(0.25)
    assert report.quality == "LOW"


# ── Tests: detect_duplicate_identity_keys ───────────────────────────────────

def test_no_duplicates():
    df = pd.DataFrame({"game_id": [f"G{i}" for i in range(5)]})
    report = detect_duplicate_identity_keys(df, ["game_id"])
    assert not report.has_duplicates
    assert report.n_duplicates == 0


def test_has_duplicates():
    df = pd.DataFrame({"game_id": ["G001", "G001", "G002"]})
    report = detect_duplicate_identity_keys(df, ["game_id"])
    assert report.has_duplicates
    assert report.n_duplicates >= 1


# ── Tests: compare_p15_joined_vs_simulation_ledger ───────────────────────────

def test_alignment_safe_after_p_oof_sort():
    """After sorting joined_oof by p_oof descending, alignment must be safe."""
    jof = _make_joined_oof(n=20, seed=7)
    sim = _make_simulation_ledger(jof)
    comp = compare_p15_joined_vs_simulation_ledger(jof, sim)
    assert comp.alignment_safe is True
    assert comp.ytrue_match is True
    assert comp.fold_id_match is True
    assert comp.p_model_max_diff < 1e-6
    assert comp.sort_key_used == "p_oof_descending"


def test_alignment_unsafe_without_sort():
    """Mismatched y_true in simulation_ledger should fail alignment."""
    jof = _make_joined_oof(n=20, seed=7)
    sim = _make_simulation_ledger(jof)
    # Corrupt y_true so alignment check will fail
    sim["y_true"] = 1 - sim["y_true"]
    comp = compare_p15_joined_vs_simulation_ledger(jof, sim)
    assert comp.alignment_safe is False


def test_alignment_mismatched_length():
    """Different row counts between joined and simulation must not raise, must report unsafe."""
    jof = _make_joined_oof(n=10, seed=3)
    sim = _make_simulation_ledger(jof)
    jof_short = jof.iloc[:8].reset_index(drop=True)
    comp = compare_p15_joined_vs_simulation_ledger(jof_short, sim)
    assert comp.alignment_safe is False


# ── Tests: audit_identity_columns ───────────────────────────────────────────

def test_audit_full_with_game_id(tmp_path):
    jof = _make_joined_oof(n=15, seed=11)
    sim = _make_simulation_ledger(jof)
    rec = pd.DataFrame({
        "game_id": [f"G{i:04d}" for i in range(5)],
        "gate_decision": ["P16_6_ELIGIBLE_PAPER_RECOMMENDATION"] * 5,
    })

    sim_path = str(tmp_path / "simulation_ledger.csv")
    jof_path = str(tmp_path / "joined_oof.csv")
    rec_path = str(tmp_path / "recommendation_rows.csv")
    sim.to_csv(sim_path, index=False)
    jof.to_csv(jof_path, index=False)
    rec.to_csv(rec_path, index=False)

    audit = audit_identity_columns({
        "simulation_ledger": sim_path,
        "joined_oof": jof_path,
        "recommendation_rows": rec_path,
    })

    assert "joined_oof" in audit.files_with_game_id
    assert "recommendation_rows" in audit.files_with_game_id
    assert audit.enrichment_feasible is True
    assert audit.comparison is not None
    assert audit.comparison.alignment_safe is True


def test_audit_without_game_id_in_joined(tmp_path):
    jof = _make_joined_oof(n=10, seed=5)
    jof_no_id = jof.drop(columns=["game_id"])
    sim = _make_simulation_ledger(jof)

    sim_path = str(tmp_path / "simulation_ledger.csv")
    jof_path = str(tmp_path / "joined_oof.csv")
    sim.to_csv(sim_path, index=False)
    jof_no_id.to_csv(jof_path, index=False)

    audit = audit_identity_columns({
        "simulation_ledger": sim_path,
        "joined_oof": jof_path,
    })

    assert "joined_oof" in audit.files_without_game_id
    assert audit.enrichment_feasible is False
    assert audit.enrichment_blocker is not None
