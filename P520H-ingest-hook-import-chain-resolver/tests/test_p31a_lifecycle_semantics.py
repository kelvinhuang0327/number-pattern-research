"""
test_p31a_lifecycle_semantics.py
==================================
P31A Lifecycle Semantics Tests

Verifies that the lifecycle semantics decision (Option A) is correctly
reflected in the catalog label system:
  - RETIRED strategies never get 'row-backed' or 'reconstructible' labels.
  - assign_label(RETIRED) always returns 'retired'.
  - Wave 1 strategies remain 'retired' even when row_count > 0 (temp DB).
  - 'reconstructible' population stays at 0 under Option A.
  - P26 label precedence table is respected for RETIRED state.
"""
from __future__ import annotations

import pytest


# ── P26 label assignment logic tests ─────────────────────────────────────────

def test_assign_label_retired_returns_retired():
    from lottery_api.models.replay_strategy_state_labels import assign_label
    result = assign_label(
        replay_visibility_state="RETIRED",
        row_count=0,
        reconstructible_candidate=False,
    )
    assert result == "retired"


def test_assign_label_retired_ignores_row_count():
    """RETIRED state → 'retired' even if row_count is nonzero (temp rows don't change label)."""
    from lottery_api.models.replay_strategy_state_labels import assign_label
    result = assign_label(
        replay_visibility_state="RETIRED",
        row_count=1500,  # simulate temp-DB row count
        reconstructible_candidate=False,
    )
    assert result == "retired", (
        "RETIRED strategies must remain 'retired' even when temp row_count > 0"
    )


def test_assign_label_retired_ignores_reconstructible_flag():
    """RETIRED state takes precedence over reconstructible_candidate=True."""
    from lottery_api.models.replay_strategy_state_labels import assign_label
    result = assign_label(
        replay_visibility_state="RETIRED",
        row_count=0,
        reconstructible_candidate=True,
    )
    assert result == "retired", (
        "RETIRED state overrides reconstructible_candidate=True per P26 label precedence"
    )


def test_assign_label_artifact_only_reconstructible():
    """ARTIFACT_ONLY + reconstructible=True → 'reconstructible' (not RETIRED)."""
    from lottery_api.models.replay_strategy_state_labels import assign_label
    result = assign_label(
        replay_visibility_state="ARTIFACT_ONLY",
        row_count=0,
        reconstructible_candidate=True,
    )
    assert result == "reconstructible"


def test_assign_label_retired_not_row_backed():
    """RETIRED strategies are never row-backed."""
    from lottery_api.models.replay_strategy_state_labels import is_row_backed
    assert is_row_backed("RETIRED", row_count=1500) is False


def test_assign_label_retired_not_queryable():
    """RETIRED strategies are never queryable via catalog."""
    from lottery_api.models.replay_strategy_state_labels import LABEL_DEFINITIONS
    assert LABEL_DEFINITIONS["retired"]["queryable"] is False


# ── Wave 1 strategy label assertions ─────────────────────────────────────────

WAVE1_STRATEGY_IDS = [
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
]


def test_wave1_strategies_have_retired_label_in_catalog():
    """
    Each Wave 1 strategy must have primary_label='retired' in the P26 full catalog.
    """
    from lottery_api.models.replay_strategy_state_labels import get_full_label_catalog
    catalog = get_full_label_catalog()
    catalog_by_id = {e["strategy_id"]: e for e in catalog}

    for sid in WAVE1_STRATEGY_IDS:
        assert sid in catalog_by_id, f"{sid} not found in P26 catalog"
        entry = catalog_by_id[sid]
        assert entry["primary_label"] == "retired", (
            f"{sid}: expected primary_label='retired', got '{entry['primary_label']}'"
        )


def test_wave1_strategies_not_queryable_in_catalog():
    """Wave 1 strategies must have queryable=False in catalog."""
    from lottery_api.models.replay_strategy_state_labels import get_full_label_catalog
    catalog = get_full_label_catalog()
    catalog_by_id = {e["strategy_id"]: e for e in catalog}

    for sid in WAVE1_STRATEGY_IDS:
        if sid not in catalog_by_id:
            continue
        entry = catalog_by_id[sid]
        assert entry["queryable"] is False, (
            f"{sid}: expected queryable=False, got {entry['queryable']}"
        )


def test_wave1_strategies_not_row_backed_in_catalog():
    """Wave 1 strategies must have is_row_backed=False (no production DB rows)."""
    from lottery_api.models.replay_strategy_state_labels import get_full_label_catalog
    catalog = get_full_label_catalog()
    catalog_by_id = {e["strategy_id"]: e for e in catalog}

    for sid in WAVE1_STRATEGY_IDS:
        if sid not in catalog_by_id:
            continue
        entry = catalog_by_id[sid]
        assert entry["is_row_backed"] is False, (
            f"{sid}: expected is_row_backed=False (no production rows in P31A)"
        )


# ── Option A reconstructible population spec ─────────────────────────────────

def test_option_a_reconstructible_count_zero():
    """
    Under Option A (lifecycle stays 'retired'), no Wave 1 strategy should be
    classified as 'reconstructible'. reconstructible count must be 0.
    """
    from lottery_api.models.replay_strategy_state_labels import get_full_label_catalog
    catalog = get_full_label_catalog()
    wave1_ids = set(WAVE1_STRATEGY_IDS)
    reconstructible_wave1 = [
        e for e in catalog
        if e["strategy_id"] in wave1_ids and e["primary_label"] == "reconstructible"
    ]
    assert len(reconstructible_wave1) == 0, (
        f"Under Option A, 0 Wave 1 strategies should be 'reconstructible'. "
        f"Got: {[e['strategy_id'] for e in reconstructible_wave1]}"
    )


# ── Option A replay_available flag semantics ──────────────────────────────────

def test_option_a_retired_label_retained():
    """
    Option A: Lifecycle status stays RETIRED.
    replay_available_flag=True is an additive catalog field, not a label change.
    """
    from lottery_api.models.replay_strategy_state_labels import assign_label
    # Simulated: a retired strategy with temp rows should still get 'retired' label
    label = assign_label(
        replay_visibility_state="RETIRED",
        row_count=1500,
        reconstructible_candidate=False,
    )
    assert label == "retired", (
        "Option A: RETIRED + temp rows → label must remain 'retired' (not 'row-backed')"
    )


def test_option_b_not_adopted_no_reconstructible_relabel():
    """
    Option B (re-label as 'reconstructible') was NOT adopted.
    Verify that RETIRED state is not mapped to 'reconstructible' anywhere.
    """
    from lottery_api.models.replay_strategy_state_labels import assign_label
    # 'reconstructible' only applies to ARTIFACT_ONLY state
    for state in ("RETIRED", "REJECTED_REGISTERED", "OBSERVATION"):
        label = assign_label(
            replay_visibility_state=state,
            row_count=0,
            reconstructible_candidate=True,  # even with flag=True
        )
        assert label != "reconstructible", (
            f"State {state} must NEVER produce 'reconstructible' label (Option B not adopted)"
        )
