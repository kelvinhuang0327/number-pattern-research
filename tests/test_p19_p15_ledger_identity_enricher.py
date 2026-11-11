"""
tests/test_p19_p15_ledger_identity_enricher.py

Unit tests for P19 P15 ledger identity enricher module.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from wbc_backend.recommendation.p19_p15_ledger_identity_enricher import (
    enrich_simulation_ledger_with_identity,
    validate_enriched_ledger,
    summarize_identity_enrichment,
    IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT,
    IDENTITY_ENRICHED_BY_ROW_IDX,
    IDENTITY_BLOCKED_UNSAFE_ALIGNMENT,
    IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE,
    IDENTITY_BLOCKED_DUPLICATE_GAME_ID,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_joined_oof(n: int = 10, seed: int = 42, include_game_id: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "p_oof": rng.uniform(0.3, 0.7, n),
        "p_model": rng.uniform(0.3, 0.7, n),
        "p_market": rng.uniform(0.3, 0.7, n),
        "y_true": rng.integers(0, 2, n),
        "fold_id": rng.integers(0, 5, n),
        "game_date": ["2026-05-01"] * n,
        "home_team": ["TeamA"] * n,
        "away_team": ["TeamB"] * n,
    })
    if include_game_id:
        df["game_id"] = [f"G{i:04d}" for i in range(n)]
    # Sort by p_oof descending (as P15 does)
    df = df.sort_values("p_oof", ascending=False).reset_index(drop=True)
    return df


def _make_simulation_ledger(joined_oof_df: pd.DataFrame, n_policies: int = 4) -> pd.DataFrame:
    rows = []
    for row_idx, row in joined_oof_df.iterrows():
        for i in range(n_policies):
            rows.append({
                "row_idx": row_idx,
                "y_true": row["y_true"],
                "fold_id": row["fold_id"],
                "p_model": row["p_oof"],  # P15 stores p_oof as p_model
                "p_market": row["p_market"],
                "policy": f"policy_{i}",
                "should_bet": 1,
                "stake_fraction": 0.05,
            })
    return pd.DataFrame(rows)


# ── Tests: enrich_simulation_ledger_with_identity ────────────────────────────

def test_enrichment_adds_game_id():
    jof = _make_joined_oof(n=10, seed=1)
    sim = _make_simulation_ledger(jof)
    assert "game_id" not in sim.columns
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    assert "game_id" in enriched.columns


def test_enrichment_covers_all_rows():
    jof = _make_joined_oof(n=10, seed=2)
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    n_with = enriched["game_id"].notna().sum()
    assert n_with == len(enriched)


def test_enrichment_correct_game_ids():
    """Enriched game_ids must come from joined_oof — no fabrication."""
    jof = _make_joined_oof(n=8, seed=3)
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    expected_ids = set(jof["game_id"].unique())
    actual_ids = set(enriched["game_id"].dropna().unique())
    assert actual_ids <= expected_ids, "Enriched contains fabricated game_ids!"


def test_enrichment_method_set():
    jof = _make_joined_oof(n=10, seed=4)
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    methods = enriched["identity_enrichment_method"].unique()
    assert len(methods) == 1
    assert methods[0] == IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT


def test_enrichment_status_set():
    jof = _make_joined_oof(n=10, seed=5)
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    statuses = enriched["identity_enrichment_status"].unique()
    assert len(statuses) == 1
    assert statuses[0] == IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT


def test_enrichment_risk_low():
    jof = _make_joined_oof(n=10, seed=6)
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    assert "LOW" in enriched["identity_enrichment_risk"].iloc[0]


def test_enrichment_row_count_preserved():
    n = 12
    jof = _make_joined_oof(n=n, seed=7)
    sim = _make_simulation_ledger(jof, n_policies=4)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    assert len(enriched) == len(sim)


# ── Tests: blocked cases ─────────────────────────────────────────────────────

def test_blocked_missing_game_id_source():
    jof = _make_joined_oof(n=10, seed=8, include_game_id=False)
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    assert enriched["identity_enrichment_status"].iloc[0] == IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE
    assert enriched["game_id"].isna().all()


def test_blocked_duplicate_game_id():
    jof = _make_joined_oof(n=10, seed=9)
    # Force duplicates
    jof["game_id"] = "DUPLICATE_ID"
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    assert enriched["identity_enrichment_status"].iloc[0] == IDENTITY_BLOCKED_DUPLICATE_GAME_ID


def test_blocked_unsafe_alignment_y_true_mismatch():
    """Corrupted y_true in sim_ledger breaks alignment → blocked."""
    jof = _make_joined_oof(n=20, seed=10)
    sim = _make_simulation_ledger(jof)
    # Corrupt y_true so alignment check fails
    sim["y_true"] = 1 - sim["y_true"]
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    assert enriched["identity_enrichment_status"].iloc[0] == IDENTITY_BLOCKED_UNSAFE_ALIGNMENT


def test_already_has_game_id_passthrough():
    """If simulation_ledger already has game_id, enrichment is a no-op."""
    jof = _make_joined_oof(n=10, seed=11)
    sim = _make_simulation_ledger(jof)
    sim["game_id"] = [f"PRE{i:04d}" for i in range(len(sim))]
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    assert enriched["identity_enrichment_status"].iloc[0] == IDENTITY_ENRICHED_BY_ROW_IDX
    # Must NOT overwrite existing game_ids
    assert all(g.startswith("PRE") for g in enriched["game_id"])


# ── Tests: validate_enriched_ledger ─────────────────────────────────────────

def test_validate_valid_enriched():
    jof = _make_joined_oof(n=10, seed=20)
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    result = validate_enriched_ledger(enriched)
    assert result.valid is True
    assert result.error_code is None


def test_validate_missing_status_column():
    df = pd.DataFrame({"game_id": ["G001"], "y_true": [1]})
    result = validate_enriched_ledger(df)
    assert result.valid is False
    assert result.error_code == "MISSING_STATUS_COLUMN"


def test_validate_unknown_status():
    df = pd.DataFrame({
        "game_id": ["G001"],
        "identity_enrichment_status": ["MADE_UP_STATUS"],
    })
    result = validate_enriched_ledger(df)
    assert result.valid is False
    assert result.error_code == "UNKNOWN_STATUS"


def test_validate_paper_only_violation():
    jof = _make_joined_oof(n=5, seed=21)
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    enriched["paper_only"] = False
    result = validate_enriched_ledger(enriched)
    assert result.valid is False
    assert result.error_code == "PAPER_ONLY_VIOLATION"


# ── Tests: summarize_identity_enrichment ────────────────────────────────────

def test_summarize_coverage():
    jof = _make_joined_oof(n=10, seed=30)
    sim = _make_simulation_ledger(jof)
    enriched = enrich_simulation_ledger_with_identity(sim, jof)
    summary = summarize_identity_enrichment(enriched)
    assert summary["n_total"] == len(sim)
    assert summary["game_id_coverage"] == pytest.approx(1.0)
    assert summary["n_with_game_id"] == len(sim)
    assert summary["paper_only"] is True
    assert summary["production_ready"] is False
