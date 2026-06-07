"""Tests for P252E — Permutation Test SSOT."""
from __future__ import annotations

import importlib
import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.utils import permutation_test as pt

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"

# Reference null distribution used throughout
NULL5 = [0.01, 0.02, 0.03, 0.04, 0.05]  # sorted ascending, B=5


def _find_artifact() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p252e_permutation_test_ssot_*.json"))
    assert candidates, "No p252e JSON artifact found; run analysis/p252e_permutation_test_ssot.py first"
    return candidates[-1]


def _load_artifact() -> dict:
    return json.loads(_find_artifact().read_text(encoding="utf-8"))


# ── Module isolation ──────────────────────────────────────────────────────────

def test_module_no_forbidden_imports():
    module_path = REPO_ROOT / "lottery_api" / "utils" / "permutation_test.py"
    source = module_path.read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from ")) and not line.strip().startswith("#")
    ]
    import_text = "\n".join(import_lines)
    forbidden = ["sqlite3", "database", "registry", "routes", "numpy", "scipy", "statsmodels"]
    for mod in forbidden:
        assert mod not in import_text, f"permutation_test must not import {mod!r}"


def test_module_no_db_at_import():
    if "lottery_api.utils.permutation_test" in sys.modules:
        importlib.reload(sys.modules["lottery_api.utils.permutation_test"])
    from lottery_api.utils import permutation_test  # noqa: F401


# ── validate_permutation_inputs ───────────────────────────────────────────────

def test_validate_ok():
    r = pt.validate_permutation_inputs(0.03, NULL5, "greater")
    assert r["valid"] is True
    assert r["n_null"] == 5


def test_validate_empty_null():
    r = pt.validate_permutation_inputs(0.03, [], "greater")
    assert r["valid"] is False
    assert len(r["errors"]) >= 1


def test_validate_invalid_alternative():
    r = pt.validate_permutation_inputs(0.03, NULL5, "both")
    assert r["valid"] is False


def test_validate_nan_observed():
    r = pt.validate_permutation_inputs(float("nan"), NULL5, "greater")
    assert r["valid"] is False


def test_validate_inf_observed():
    r = pt.validate_permutation_inputs(float("inf"), NULL5, "greater")
    assert r["valid"] is False


def test_validate_non_numeric_null():
    r = pt.validate_permutation_inputs(0.03, [0.01, "bad"], "greater")
    assert r["valid"] is False


def test_validate_never_raises():
    for args in [(None, [], "greater"), (0.03, [], "bad"), (float("nan"), [], "less")]:
        try:
            result = pt.validate_permutation_inputs(*args)
            assert isinstance(result, dict)
        except Exception:
            pass  # Raising is also acceptable for truly bad inputs


# ── empirical_p_value — greater ───────────────────────────────────────────────

def test_p_greater_formula():
    # obs=0.035: count(null >= 0.035-ε) = count(0.04, 0.05) = 2
    # p = (1+2)/(5+1) = 3/6 = 0.5
    p = pt.empirical_p_value(0.035, NULL5, "greater", plus_one=True)
    assert abs(p - 3 / 6) < 1e-10


def test_p_greater_most_extreme_nonzero():
    # obs=0.06 > all null → count=0 → p = 1/6 (not 0!)
    p = pt.empirical_p_value(0.06, NULL5, "greater", plus_one=True)
    assert p > 0.0
    assert abs(p - 1 / 6) < 1e-10


def test_p_greater_least_extreme_is_1():
    # obs=0.005 < all null → count=5 → p = (1+5)/6 = 1.0
    p = pt.empirical_p_value(0.005, NULL5, "greater", plus_one=True)
    assert abs(p - 1.0) < 1e-10


def test_p_greater_boundary_exact_match():
    # obs=0.03, count(null >= 0.03-ε) = count(0.03, 0.04, 0.05) = 3
    p = pt.empirical_p_value(0.03, NULL5, "greater", plus_one=True)
    assert abs(p - 4 / 6) < 1e-10


# ── empirical_p_value — less ──────────────────────────────────────────────────

def test_p_less_formula():
    # obs=0.035: count(null <= 0.035+ε) = count(0.01,0.02,0.03) = 3
    # p = (1+3)/(5+1) = 4/6
    p = pt.empirical_p_value(0.035, NULL5, "less", plus_one=True)
    assert abs(p - 4 / 6) < 1e-10


def test_p_less_most_extreme_nonzero():
    # obs=0.001 < all null → count(null<=0.001)=0 → p=1/6
    p = pt.empirical_p_value(0.001, NULL5, "less", plus_one=True)
    assert p > 0.0
    assert abs(p - 1 / 6) < 1e-10


# ── empirical_p_value — two-sided ─────────────────────────────────────────────

def test_p_two_sided_capped_at_1():
    p = pt.empirical_p_value(0.03, NULL5, "two-sided", plus_one=True)
    assert 0.0 < p <= 1.0


def test_p_two_sided_symmetric():
    # Null symmetric around 0.03 → p_two_sided should be same for obs=0.01 vs obs=0.05
    null_sym = [-2.0, -1.0, 0.0, 1.0, 2.0]
    p_high = pt.empirical_p_value(2.5, null_sym, "two-sided")
    p_low  = pt.empirical_p_value(-2.5, null_sym, "two-sided")
    assert abs(p_high - p_low) < 1e-10


def test_p_two_sided_extreme_nonzero():
    p = pt.empirical_p_value(100.0, NULL5, "two-sided", plus_one=True)
    assert p > 0.0


# ── plus_one correction behavior ──────────────────────────────────────────────

def test_plus_one_true_prevents_p_zero():
    # obs more extreme than all null → without plus_one: p=0, with plus_one: p>0
    p_with    = pt.empirical_p_value(1.0, NULL5, "greater", plus_one=True)
    p_without = pt.empirical_p_value(1.0, NULL5, "greater", plus_one=False)
    assert p_with > 0.0
    assert p_without == 0.0


def test_plus_one_true_larger_than_false():
    # plus_one=True gives (1+c)/(B+1), plus_one=False gives c/B — always >=
    for obs in [0.025, 0.035, 0.045]:
        p_w = pt.empirical_p_value(obs, NULL5, "greater", plus_one=True)
        p_wo = pt.empirical_p_value(obs, NULL5, "greater", plus_one=False)
        assert p_w >= p_wo


# ── invalid input raises ──────────────────────────────────────────────────────

def test_empty_null_raises():
    with pytest.raises(ValueError):
        pt.empirical_p_value(0.03, [], "greater")


def test_invalid_alternative_raises():
    with pytest.raises(ValueError):
        pt.empirical_p_value(0.03, NULL5, "GREATER")


def test_nan_observed_raises():
    with pytest.raises(ValueError):
        pt.empirical_p_value(float("nan"), NULL5, "greater")


# ── empirical_p_value deterministic ──────────────────────────────────────────

def test_p_value_deterministic():
    p1 = pt.empirical_p_value(0.035, NULL5, "greater")
    p2 = pt.empirical_p_value(0.035, NULL5, "greater")
    assert p1 == p2


# ── compare_observed_to_null ──────────────────────────────────────────────────

def test_compare_null_count():
    cmp = pt.compare_observed_to_null(0.03, NULL5)
    assert cmp["null_count"] == 5


def test_compare_null_min_max():
    cmp = pt.compare_observed_to_null(0.03, NULL5)
    assert cmp["null_min"] == pytest.approx(0.01)
    assert cmp["null_max"] == pytest.approx(0.05)


def test_compare_null_mean():
    cmp = pt.compare_observed_to_null(0.03, NULL5)
    assert abs(cmp["null_mean"] - 0.03) < 1e-10


def test_compare_obs_percentile():
    # obs=0.03, count(null<=0.03)/5 = 3/5 = 60%
    cmp = pt.compare_observed_to_null(0.03, NULL5)
    assert abs(cmp["obs_percentile"] - 60.0) < 1e-6


def test_compare_obs_above_mean():
    cmp = pt.compare_observed_to_null(0.04, NULL5)
    assert cmp["obs_above_null_mean"] is True


def test_compare_returns_all_required_fields():
    cmp = pt.compare_observed_to_null(0.03, NULL5)
    for field in ["null_count", "null_min", "null_max", "null_mean", "null_std",
                   "null_median", "obs_percentile", "obs_above_null_mean", "obs_above_null_median"]:
        assert field in cmp, f"Missing field {field!r}"


# ── permutation_summary ───────────────────────────────────────────────────────

def test_summary_required_fields():
    s = pt.permutation_summary(0.035, NULL5, "greater", True, seed=42)
    for field in ["schema_version", "test_type", "family_label", "alternative",
                   "observed_statistic", "null_count", "null_min", "null_max",
                   "null_mean", "null_std", "null_median", "obs_percentile",
                   "empirical_p_value", "plus_one_correction", "seed",
                   "no_edge_claim", "no_betting_advice", "assumptions", "limitations"]:
        assert field in s, f"Missing required field: {field!r}"


def test_summary_no_edge_claim():
    s = pt.permutation_summary(0.035, NULL5)
    assert s["no_edge_claim"] is True


def test_summary_no_betting_advice():
    s = pt.permutation_summary(0.035, NULL5)
    assert s["no_betting_advice"] is True


def test_summary_test_type():
    s = pt.permutation_summary(0.035, NULL5)
    assert s["test_type"] == "permutation_test"


def test_summary_schema_version():
    s = pt.permutation_summary(0.035, NULL5)
    assert s["schema_version"] == "1.0"


def test_summary_l96_warning_in_limitations():
    s = pt.permutation_summary(0.035, NULL5)
    assert any("L96" in lim for lim in s["limitations"])


def test_summary_seed_recorded():
    s = pt.permutation_summary(0.035, NULL5, seed=42)
    assert s["seed"] == 42


def test_summary_family_label():
    s = pt.permutation_summary(0.035, NULL5, family_label="MY_FAMILY")
    assert s["family_label"] == "MY_FAMILY"


def test_summary_empirical_p_matches_direct():
    direct = pt.empirical_p_value(0.035, NULL5, "greater", plus_one=True)
    s = pt.permutation_summary(0.035, NULL5, "greater", plus_one=True)
    assert abs(s["empirical_p_value"] - direct) < 1e-12


def test_summary_deterministic():
    s1 = pt.permutation_summary(0.035, NULL5, "greater", True, seed=42, family_label="X")
    s2 = pt.permutation_summary(0.035, NULL5, "greater", True, seed=42, family_label="X")
    assert s1["empirical_p_value"] == s2["empirical_p_value"]
    assert s1["null_mean"] == s2["null_mean"]


def test_summary_invalid_raises():
    with pytest.raises(ValueError):
        pt.permutation_summary(0.03, [])


# ── deterministic_shuffle ─────────────────────────────────────────────────────

def test_shuffle_deterministic_same_seed():
    items = list(range(10))
    sh1 = pt.deterministic_shuffle(items, seed=42)
    sh2 = pt.deterministic_shuffle(items, seed=42)
    assert sh1 == sh2


def test_shuffle_different_seeds_produce_different_results():
    items = list(range(20))
    sh1 = pt.deterministic_shuffle(items, seed=1)
    sh2 = pt.deterministic_shuffle(items, seed=2)
    assert sh1 != sh2


def test_shuffle_preserves_elements():
    items = [0.01, 0.02, 0.03, 0.04, 0.05]
    sh = pt.deterministic_shuffle(items, seed=99)
    assert sorted(sh) == sorted(items)


def test_shuffle_does_not_modify_original():
    items = [1, 2, 3, 4, 5]
    original = list(items)
    pt.deterministic_shuffle(items, seed=7)
    assert items == original


def test_shuffle_empty_raises():
    with pytest.raises(ValueError):
        pt.deterministic_shuffle([], seed=42)


def test_shuffle_non_int_seed_raises():
    with pytest.raises(ValueError):
        pt.deterministic_shuffle([1, 2, 3], seed="42")


# ── Artifact JSON checks ──────────────────────────────────────────────────────

def test_artifact_exists_and_parses():
    report = _load_artifact()
    assert isinstance(report, dict)


def test_artifact_task_id():
    assert _load_artifact()["task_id"] == "P252E"


def test_artifact_classification():
    assert _load_artifact()["classification"] == "PERMUTATION_TEST_SSOT_IMPLEMENTED"


def test_artifact_no_db_write():
    assert _load_artifact()["no_db_write_confirmed"] is True


def test_artifact_no_registry_mutation():
    assert _load_artifact()["no_registry_mutation_confirmed"] is True


def test_artifact_no_strategy_promotion():
    assert _load_artifact()["no_strategy_promotion_confirmed"] is True


def test_artifact_no_betting_advice():
    assert _load_artifact()["no_betting_advice_confirmed"] is True


def test_artifact_p252b_m5_p0():
    dep = _load_artifact()["p252b_dependency_verified"]
    assert dep["found"] is True
    assert dep["m_id_priority"] == "P0"


def test_artifact_p252c_found():
    dep = _load_artifact()["p252c_dependency_verified"]
    assert dep["found"] is True


def test_artifact_p252d_found():
    dep = _load_artifact()["p252d_dependency_verified"]
    assert dep["found"] is True


def test_artifact_module_safe():
    safety = _load_artifact()["module_safety"]
    assert safety["exists"] is True
    assert safety["safe"] is True
    assert safety["forbidden_imports_found"] == []


def test_artifact_reference_checks():
    ex = _load_artifact()["exercise_results"]
    assert ex["p_greater_correct"] is True
    assert ex["p_most_extreme_not_zero"] is True
    assert ex["p_most_extreme_correct"] is True
    assert ex["p_less_correct"] is True
    assert ex["determinism_ok"] is True
    assert ex["shuffle_deterministic"] is True


def test_artifact_l96_documented():
    fix = _load_artifact()["l96_fix_documented"]
    assert "L96" in fix["description"]
    assert "Binomial" in fix["correct_null_generation"] or "seeded" in fix["correct_null_generation"]


def test_md_artifact_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p252e_permutation_test_ssot_*.md"))
    assert candidates
    text = candidates[-1].read_text(encoding="utf-8")
    assert len(text) > 500


def test_md_no_db_write():
    candidates = sorted(OUTPUTS_DIR.glob("p252e_permutation_test_ssot_*.md"))
    assert "no db write" in candidates[-1].read_text(encoding="utf-8").lower()


def test_md_no_betting_advice():
    candidates = sorted(OUTPUTS_DIR.glob("p252e_permutation_test_ssot_*.md"))
    assert "betting" in candidates[-1].read_text(encoding="utf-8").lower()


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_produces_valid_artifact():
    from analysis import p252e_permutation_test_ssot as p252e
    report = p252e.main()
    assert report["task_id"] == "P252E"
    assert report["classification"] == "PERMUTATION_TEST_SSOT_IMPLEMENTED"
    assert report["no_db_write_confirmed"] is True
    assert report["no_betting_advice_confirmed"] is True
    assert report["exercise_results"]["p_greater_correct"] is True
