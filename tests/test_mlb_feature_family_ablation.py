"""
tests/test_mlb_feature_family_ablation.py

P12: Tests for mlb_feature_family_ablation module.
"""
from __future__ import annotations

import json
import math

import pytest

from wbc_backend.prediction.mlb_feature_family_ablation import (
    FEATURE_FAMILIES,
    build_ablation_variant_rows,
    classify_feature_columns,
    generate_ablation_plan,
)


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Feature family classification
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_recent_form_columns():
    cols = [
        "indep_home_recent_win_rate",
        "indep_away_recent_win_rate",
        "indep_recent_win_rate_delta",
    ]
    result = classify_feature_columns(cols)
    assert "indep_home_recent_win_rate" in result["family_to_cols"]["recent_form"]
    assert "indep_away_recent_win_rate" in result["family_to_cols"]["recent_form"]
    assert "indep_recent_win_rate_delta" in result["family_to_cols"]["recent_form"]


def test_classify_rest_columns():
    cols = ["indep_home_rest_days", "indep_away_rest_days", "indep_rest_days_delta"]
    result = classify_feature_columns(cols)
    assert "indep_home_rest_days" in result["family_to_cols"]["rest"]
    assert "indep_rest_days_delta" in result["family_to_cols"]["rest"]


def test_classify_bullpen_columns():
    cols = [
        "indep_home_bullpen_usage_3d",
        "indep_away_bullpen_usage_3d",
        "indep_bullpen_proxy_delta",
    ]
    result = classify_feature_columns(cols)
    for c in cols:
        assert c in result["family_to_cols"]["bullpen"]


def test_classify_starter_columns():
    cols = ["indep_home_starter_era_proxy", "indep_away_starter_era_proxy", "indep_starter_era_delta"]
    result = classify_feature_columns(cols)
    for c in cols:
        assert c in result["family_to_cols"]["starter"]


def test_classify_weather_columns():
    cols = ["indep_wind_kmh", "indep_temp_c", "indep_park_roof_type"]
    result = classify_feature_columns(cols)
    for c in cols:
        assert c in result["family_to_cols"]["weather"]


def test_unknown_columns_reported():
    cols = ["my_mystery_col", "another_unknown", "indep_home_rest_days"]
    result = classify_feature_columns(cols)
    assert "my_mystery_col" in result["unknown_columns"]
    assert "another_unknown" in result["unknown_columns"]
    # known column should NOT be in unknown
    assert "indep_home_rest_days" not in result["unknown_columns"]


def test_classify_all_families_present():
    all_cols = [c for fam_cols in FEATURE_FAMILIES.values() for c in fam_cols]
    result = classify_feature_columns(all_cols)
    for fam in FEATURE_FAMILIES:
        assert result["feature_count_by_family"][fam] > 0


def test_feature_count_by_family_is_correct():
    cols = ["indep_wind_kmh", "indep_temp_c"]
    result = classify_feature_columns(cols)
    assert result["feature_count_by_family"]["weather"] == 2
    # All others should be 0
    for fam in result["feature_count_by_family"]:
        if fam != "weather":
            assert result["feature_count_by_family"][fam] == 0


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Ablation plan
# ─────────────────────────────────────────────────────────────────────────────

_REQUIRED_VARIANTS = [
    "all_features",
    "recent_only",
    "rest_only",
    "bullpen_only",
    "starter_only",
    "weather_only",
    "no_recent",
    "no_rest",
    "no_bullpen",
    "no_starter",
    "no_weather",
    "no_context_features",
    "recent_plus_rest",
    "starter_plus_bullpen",
    "recent_rest_starter",
    "market_or_base_only_baseline",
]


def test_ablation_plan_has_all_required_variants():
    plan = generate_ablation_plan()
    names = {v["variant_name"] for v in plan}
    for required in _REQUIRED_VARIANTS:
        assert required in names, f"Missing variant: {required}"


def test_ablation_plan_count():
    plan = generate_ablation_plan()
    assert len(plan) >= 16


def test_ablation_plan_variants_have_required_keys():
    plan = generate_ablation_plan()
    for spec in plan:
        assert "variant_name" in spec
        assert "enabled_families" in spec
        assert "description" in spec


def test_ablation_plan_no_context_features_disables_all_context():
    plan = generate_ablation_plan()
    spec = next(s for s in plan if s["variant_name"] == "no_context_features")
    context_families = {"recent_form", "rest", "bullpen", "starter", "weather"}
    enabled = set(spec["enabled_families"])
    assert not (enabled & context_families), (
        f"no_context_features should disable all context families but got: "
        f"{enabled & context_families}"
    )


def test_ablation_plan_recent_only_has_only_recent_and_base():
    plan = generate_ablation_plan()
    spec = next(s for s in plan if s["variant_name"] == "recent_only")
    enabled = set(spec["enabled_families"])
    context_others = {"rest", "bullpen", "starter", "weather"}
    assert not (enabled & context_others)
    assert "recent_form" in enabled


def test_ablation_plan_all_features_includes_all():
    plan = generate_ablation_plan()
    spec = next(s for s in plan if s["variant_name"] == "all_features")
    enabled = set(spec["enabled_families"])
    for fam in FEATURE_FAMILIES:
        assert fam in enabled


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Ablation variant row builder
# ─────────────────────────────────────────────────────────────────────────────

def _make_rows(n: int = 5) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "Date": f"2025-04-{i+1:02d}",
            "Home": "TeamA",
            "Away": "TeamB",
            "game_id": f"2025-04-{i+1:02d}_A_B",
            "paper_only": "True",
            "leakage_safe": "True",
            "model_prob_home": str(0.5 + i * 0.01),
            "raw_model_prob_home": str(0.5),
            "raw_model_prob_before_p10": str(0.5),
            "model_prob_away": str(0.5 - i * 0.01),
            "indep_recent_win_rate_delta": str(0.1 * i),
            "indep_rest_days_delta": str(2.0),
            "indep_bullpen_proxy_delta": str(1.0),
            "indep_starter_era_delta": str(0.5),
            "indep_home_recent_win_rate": str(0.6),
            "indep_away_recent_win_rate": str(0.5),
            "indep_wind_kmh": str(15.0),
            "indep_temp_c": str(20.0),
            "indep_park_roof_type": "open",
            "Home ML": "-150",
            "Away ML": "+130",
        })
    return rows


def test_build_ablation_variant_rows_returns_correct_count():
    rows = _make_rows(10)
    variant_rows, meta = build_ablation_variant_rows(
        rows, enabled_families=["recent_form", "base_model"], variant_name="test_v"
    )
    assert len(variant_rows) == 10


def test_build_ablation_variant_rows_disables_family_cols():
    rows = _make_rows(3)
    variant_rows, meta = build_ablation_variant_rows(
        rows,
        enabled_families=["base_model"],
        variant_name="base_only",
    )
    # indep_recent_win_rate_delta should be None (recent_form disabled)
    for row in variant_rows:
        assert row.get("indep_recent_win_rate_delta") is None
        assert row.get("indep_rest_days_delta") is None
        assert row.get("indep_bullpen_proxy_delta") is None


def test_build_ablation_variant_rows_preserves_identity_cols():
    rows = _make_rows(3)
    variant_rows, _ = build_ablation_variant_rows(
        rows, enabled_families=["base_model"], variant_name="id_test"
    )
    for orig, out in zip(rows, variant_rows):
        assert out["Date"] == orig["Date"]
        assert out["Home"] == orig["Home"]
        assert out["Away"] == orig["Away"]
        assert out["game_id"] == orig["game_id"]
        assert out["paper_only"] == orig["paper_only"]


def test_build_ablation_variant_rows_sets_metadata():
    rows = _make_rows(2)
    variant_rows, _ = build_ablation_variant_rows(
        rows,
        enabled_families=["recent_form", "base_model"],
        variant_name="meta_test",
    )
    for row in variant_rows:
        assert row["ablation_variant_name"] == "meta_test"
        assert row["probability_source"] == "feature_ablation_candidate"
        enabled = json.loads(row["ablation_enabled_families"])
        assert "recent_form" in enabled


def test_build_ablation_variant_rows_recomputes_probability():
    rows = _make_rows(3)
    # All families enabled should produce prob different from base_only
    all_rows, _ = build_ablation_variant_rows(
        rows, enabled_families=list(FEATURE_FAMILIES.keys()), variant_name="all"
    )
    base_rows, _ = build_ablation_variant_rows(
        rows, enabled_families=["base_model"], variant_name="base"
    )
    # With features, probability should differ from pure base
    # (row with nonzero deltas)
    all_probs = [float(r["model_prob_home"]) for r in all_rows]
    base_probs = [float(r["model_prob_home"]) for r in base_rows]
    # At least some rows should differ
    diffs = [abs(a - b) for a, b in zip(all_probs, base_probs)]
    assert any(d > 1e-6 for d in diffs), "Ablation should change probabilities"


def test_build_ablation_variant_rows_probability_in_range():
    rows = _make_rows(10)
    variant_rows, _ = build_ablation_variant_rows(
        rows, enabled_families=list(FEATURE_FAMILIES.keys()), variant_name="range_test"
    )
    for row in variant_rows:
        prob = float(row["model_prob_home"])
        assert 0.01 <= prob <= 0.99, f"Probability {prob} out of range"


def test_build_ablation_variant_rows_metadata_dict():
    rows = _make_rows(5)
    _, meta = build_ablation_variant_rows(
        rows, enabled_families=["rest", "base_model"], variant_name="meta_check"
    )
    assert meta["variant_name"] == "meta_check"
    assert "rest" in meta["enabled_families"]
    assert meta["total_input_rows"] == 5


def test_no_context_features_variant_uses_base_prob():
    """With no context features and base_model enabled, prob should equal base."""
    rows = _make_rows(3)
    variant_rows, _ = build_ablation_variant_rows(
        rows, enabled_families=["base_model"], variant_name="base_only"
    )
    for orig, out in zip(rows, variant_rows):
        base = float(orig.get("raw_model_prob_before_p10") or 0.5)
        out_prob = float(out["model_prob_home"])
        # Should be close to base (within clamp adjustments)
        assert abs(out_prob - base) < 0.02, (
            f"Expected ~{base}, got {out_prob}"
        )
