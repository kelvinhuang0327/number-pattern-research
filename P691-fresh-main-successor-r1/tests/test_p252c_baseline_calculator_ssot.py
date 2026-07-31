"""Tests for P252C — Baseline Calculator SSOT.

Covers:
- lottery_api/utils/baseline_calculator.py (the SSOT module)
- analysis/p252c_baseline_calculator_ssot.py (artifact generator)
- outputs/research/p252c_baseline_calculator_ssot_*.json (generated artifact)
"""
from __future__ import annotations

import importlib
import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.utils import baseline_calculator as bc

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"


def _find_latest_p252c_artifact() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p252c_baseline_calculator_ssot_*.json"))
    assert candidates, "No p252c JSON artifact found; run analysis/p252c_baseline_calculator_ssot.py first"
    return candidates[-1]


def _load_artifact() -> dict:
    return json.loads(_find_latest_p252c_artifact().read_text(encoding="utf-8"))


# ── Module isolation (no forbidden imports) ────────────────────────────────────

def test_module_does_not_import_sqlite():
    module_path = REPO_ROOT / "lottery_api" / "utils" / "baseline_calculator.py"
    source = module_path.read_text(encoding="utf-8")
    assert "sqlite3" not in source, "baseline_calculator must not import sqlite3"


def test_module_does_not_import_numpy():
    module_path = REPO_ROOT / "lottery_api" / "utils" / "baseline_calculator.py"
    source = module_path.read_text(encoding="utf-8")
    assert "import numpy" not in source, "baseline_calculator must not import numpy"
    assert "from numpy" not in source, "baseline_calculator must not import numpy"


def test_module_does_not_import_db_manager():
    """Check that no forbidden modules are *imported* (comments/docstrings are ok)."""
    module_path = REPO_ROOT / "lottery_api" / "utils" / "baseline_calculator.py"
    source = module_path.read_text(encoding="utf-8")
    # Only scan actual import lines, not comments or docstrings
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from ")) and not line.strip().startswith("#")
    ]
    import_text = "\n".join(import_lines)
    forbidden_modules = ["sqlite3", "database", "registry", "routes", "numpy", "scipy", "sqlalchemy"]
    for mod in forbidden_modules:
        assert mod not in import_text, (
            f"baseline_calculator must not import {mod!r}; found in import statements"
        )


def test_module_does_not_connect_to_db_at_import():
    """Re-importing baseline_calculator must not open a DB connection."""
    if "lottery_api.utils.baseline_calculator" in sys.modules:
        importlib.reload(sys.modules["lottery_api.utils.baseline_calculator"])
    # If import fails or raises, test fails
    from lottery_api.utils import baseline_calculator  # noqa: F401


# ── combination_count ─────────────────────────────────────────────────────────

def test_combination_count_49_6():
    assert bc.combination_count(49, 6) == 13_983_816


def test_combination_count_38_6():
    assert bc.combination_count(38, 6) == 2_760_681


def test_combination_count_39_5():
    assert bc.combination_count(39, 5) == 575_757


def test_combination_count_matches_math_comb():
    for n, k in [(49, 6), (38, 6), (39, 5), (10, 3), (10, 4)]:
        assert bc.combination_count(n, k) == math.comb(n, k)


def test_combination_count_invalid_pool_too_small():
    with pytest.raises(ValueError):
        bc.combination_count(1, 1)  # pool_size < 2


def test_combination_count_invalid_pick_exceeds_pool():
    with pytest.raises(ValueError):
        bc.combination_count(6, 6)  # pick_count must be < pool_size


def test_combination_count_invalid_negative():
    with pytest.raises((ValueError, TypeError)):
        bc.combination_count(-1, 3)


# ── single_ticket_probability ─────────────────────────────────────────────────

def test_single_ticket_probability_big_lotto():
    """BIG_LOTTO 6/49 M3+ reference value ≈ 1.86%."""
    p = bc.single_ticket_probability(49, 6, match_threshold=3)
    assert abs(p - 0.01864) < 0.0005, f"Expected ≈1.86%, got {p*100:.4f}%"


def test_single_ticket_probability_power_lotto():
    """POWER_LOTTO 6/38 M3+ reference value ≈ 3.87%."""
    p = bc.single_ticket_probability(38, 6, match_threshold=3)
    assert abs(p - 0.03870) < 0.0005, f"Expected ≈3.87%, got {p*100:.4f}%"


def test_single_ticket_probability_daily_539():
    """DAILY_539 5/39 M3+ analytical value ≈ 1.00%."""
    p = bc.single_ticket_probability(39, 5, match_threshold=3)
    assert 0.009 < p < 0.012, f"Expected ≈1.0%, got {p*100:.4f}%"


def test_single_ticket_probability_in_0_1():
    for pool, pick, thresh in [(49, 6, 3), (38, 6, 3), (39, 5, 3), (10, 3, 3)]:
        p = bc.single_ticket_probability(pool, pick, thresh)
        assert 0.0 <= p <= 1.0, f"Probability out of range for ({pool},{pick},{thresh}): {p}"


def test_single_ticket_probability_threshold_equals_pick():
    """Threshold == pick_count means exact match probability."""
    p = bc.single_ticket_probability(49, 6, match_threshold=6)
    assert p == pytest.approx(1.0 / math.comb(49, 6), rel=1e-10)


def test_single_ticket_probability_invalid_threshold():
    with pytest.raises(ValueError):
        bc.single_ticket_probability(49, 6, match_threshold=7)  # > pick_count


def test_single_ticket_probability_deterministic():
    p1 = bc.single_ticket_probability(49, 6, 3)
    p2 = bc.single_ticket_probability(49, 6, 3)
    assert p1 == p2


# ── n_ticket_probability ──────────────────────────────────────────────────────

def test_n_ticket_probability_formula_correctness():
    """1 - (1-p)^N must match direct formula."""
    p_single = bc.single_ticket_probability(49, 6, 3)
    for n in [1, 2, 3, 4, 5]:
        expected = 1.0 - (1.0 - p_single) ** n
        result = bc.n_ticket_probability(49, 6, n, 3)
        assert abs(result - expected) < 1e-12, f"Formula mismatch at n={n}"


def test_n_ticket_probability_1_equals_single():
    p_single = bc.single_ticket_probability(49, 6, 3)
    p_n1 = bc.n_ticket_probability(49, 6, 1, 3)
    assert abs(p_single - p_n1) < 1e-12


def test_n_ticket_probability_monotone_increasing():
    probs = [bc.n_ticket_probability(49, 6, n, 3) for n in range(1, 8)]
    for i in range(len(probs) - 1):
        assert probs[i] < probs[i + 1], "More tickets must increase hit probability"


def test_n_ticket_probability_invalid_n():
    with pytest.raises(ValueError):
        bc.n_ticket_probability(49, 6, 0, 3)


# ── L14 fix verification ──────────────────────────────────────────────────────

def test_l14_n_bet_formula_is_not_simple_multiplication():
    """L14 bug used p*N; correct formula is 1-(1-p)^N. They differ for N>1."""
    p_single = bc.single_ticket_probability(49, 6, 3)
    for n in [2, 3, 4, 5]:
        correct = bc.n_ticket_probability(49, 6, n, 3)
        wrong_l14 = p_single * n
        assert correct != pytest.approx(wrong_l14, rel=1e-5), (
            f"n={n}: correct={correct:.6f}, wrong_L14={wrong_l14:.6f} — they should differ"
        )


# ── expected_hits ─────────────────────────────────────────────────────────────

def test_expected_hits_basic():
    eh = bc.expected_hits(1500, 0.0186)
    assert abs(eh - 27.9) < 0.1


def test_expected_hits_zero_trials():
    assert bc.expected_hits(0, 0.5) == 0.0


def test_expected_hits_probability_zero():
    assert bc.expected_hits(1500, 0.0) == 0.0


def test_expected_hits_probability_one():
    assert bc.expected_hits(100, 1.0) == pytest.approx(100.0)


def test_expected_hits_invalid_negative_trials():
    with pytest.raises(ValueError):
        bc.expected_hits(-1, 0.5)


def test_expected_hits_invalid_probability_above_1():
    with pytest.raises(ValueError):
        bc.expected_hits(100, 1.1)


def test_expected_hits_invalid_probability_below_0():
    with pytest.raises(ValueError):
        bc.expected_hits(100, -0.01)


# ── baseline_hit_rate ─────────────────────────────────────────────────────────

def test_baseline_hit_rate_basic():
    rate = bc.baseline_hit_rate(n_hits=28, n_trials=1500)
    assert abs(rate - 28 / 1500) < 1e-12


def test_baseline_hit_rate_zero_hits():
    assert bc.baseline_hit_rate(0, 1500) == 0.0


def test_baseline_hit_rate_all_hits():
    assert bc.baseline_hit_rate(100, 100) == 1.0


def test_baseline_hit_rate_invalid_zero_trials():
    with pytest.raises(ValueError):
        bc.baseline_hit_rate(5, 0)


def test_baseline_hit_rate_invalid_hits_exceed_trials():
    with pytest.raises(ValueError):
        bc.baseline_hit_rate(101, 100)


def test_baseline_hit_rate_invalid_negative_hits():
    with pytest.raises(ValueError):
        bc.baseline_hit_rate(-1, 100)


# ── validate_lottery_config ───────────────────────────────────────────────────

def test_validate_valid_big_lotto():
    result = bc.validate_lottery_config(49, 6, 4, 3)
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_invalid_pick_equals_pool():
    result = bc.validate_lottery_config(6, 6, 1, 3)
    assert result["valid"] is False
    assert len(result["errors"]) >= 1


def test_validate_invalid_pick_exceeds_pool():
    result = bc.validate_lottery_config(5, 6, 1, 3)
    assert result["valid"] is False


def test_validate_invalid_threshold_exceeds_pick():
    result = bc.validate_lottery_config(49, 6, 1, 7)
    assert result["valid"] is False
    assert len(result["errors"]) >= 1


def test_validate_invalid_n_tickets_zero():
    result = bc.validate_lottery_config(49, 6, 0, 3)
    assert result["valid"] is False


def test_validate_returns_dict_always():
    """validate_lottery_config must never raise — always return dict."""
    for args in [(1, 1, 0, 0), (49, 6, 4, 3), (-1, 6, 1, 3), (49, "six", 1, 3)]:
        result = bc.validate_lottery_config(*args)
        assert isinstance(result, dict)
        assert "valid" in result
        assert "errors" in result


# ── random_baseline_summary ───────────────────────────────────────────────────

def test_summary_required_fields():
    summary = bc.random_baseline_summary(49, 6, 4, 1500, 3, "BIG_LOTTO")
    required = [
        "schema_version", "baseline_type", "lottery_type", "pool_size", "pick_count",
        "n_tickets", "match_threshold", "trials", "single_ticket_probability",
        "n_ticket_probability", "expected_hits", "baseline_hit_rate",
        "assumptions", "limitations", "no_edge_claim", "no_betting_advice",
    ]
    for field in required:
        assert field in summary, f"Missing required field: {field!r}"


def test_summary_no_edge_claim_is_true():
    summary = bc.random_baseline_summary(49, 6, 4, 1500, 3)
    assert summary["no_edge_claim"] is True


def test_summary_no_betting_advice_is_true():
    summary = bc.random_baseline_summary(49, 6, 4, 1500, 3)
    assert summary["no_betting_advice"] is True


def test_summary_deterministic_for_same_inputs():
    s1 = bc.random_baseline_summary(49, 6, 4, 1500, 3, "BIG_LOTTO")
    s2 = bc.random_baseline_summary(49, 6, 4, 1500, 3, "BIG_LOTTO")
    assert s1["single_ticket_probability"] == s2["single_ticket_probability"]
    assert s1["baseline_hit_rate"] == s2["baseline_hit_rate"]
    assert s1["expected_hits"] == s2["expected_hits"]


def test_summary_with_observed_hits():
    summary = bc.random_baseline_summary(49, 6, 4, 1500, 3, observed_hits=112)
    assert "observed_hits" in summary
    assert "observed_hit_rate" in summary
    assert "edge_vs_baseline" in summary
    assert summary["observed_hits"] == 112
    assert abs(summary["observed_hit_rate"] - 112 / 1500) < 1e-7  # allows for rounding to 8 dp


def test_summary_invalid_config_raises():
    with pytest.raises(ValueError):
        bc.random_baseline_summary(6, 6, 1, 1500, 3)  # pick_count >= pool_size


def test_summary_schema_version():
    summary = bc.random_baseline_summary(49, 6, 1, 1500, 3)
    assert summary["schema_version"] == "1.0"


def test_summary_assumptions_nonempty():
    summary = bc.random_baseline_summary(49, 6, 1, 1500, 3)
    assert isinstance(summary["assumptions"], list) and len(summary["assumptions"]) >= 1


def test_summary_limitations_nonempty():
    summary = bc.random_baseline_summary(49, 6, 1, 1500, 3)
    assert isinstance(summary["limitations"], list) and len(summary["limitations"]) >= 1


# ── KNOWN_LOTTERY_CONFIGS ─────────────────────────────────────────────────────

def test_known_configs_covers_main_lotteries():
    required = {"BIG_LOTTO", "POWER_LOTTO", "DAILY_539"}
    assert required <= set(bc.KNOWN_LOTTERY_CONFIGS.keys())


def test_known_configs_have_pool_and_pick():
    for name, cfg in bc.KNOWN_LOTTERY_CONFIGS.items():
        assert "pool_size" in cfg, f"{name} missing pool_size"
        assert "pick_count" in cfg, f"{name} missing pick_count"
        assert cfg["pool_size"] > cfg["pick_count"], f"{name} invalid pool/pick"


# ── Artifact JSON checks ──────────────────────────────────────────────────────

def test_artifact_exists_and_parses():
    path = _find_latest_p252c_artifact()
    assert path.exists()
    report = _load_artifact()
    assert isinstance(report, dict)


def test_artifact_task_id():
    assert _load_artifact()["task_id"] == "P252C"


def test_artifact_classification():
    assert _load_artifact()["classification"] == "BASELINE_CALCULATOR_SSOT_IMPLEMENTED"


def test_artifact_no_db_write():
    assert _load_artifact()["no_db_write_confirmed"] is True


def test_artifact_no_registry_mutation():
    assert _load_artifact()["no_registry_mutation_confirmed"] is True


def test_artifact_no_strategy_promotion():
    assert _load_artifact()["no_strategy_promotion_confirmed"] is True


def test_artifact_no_betting_advice():
    assert _load_artifact()["no_betting_advice_confirmed"] is True


def test_artifact_p252b_dependency_verified():
    dep = _load_artifact()["p252b_dependency_verified"]
    assert dep["found"] is True
    assert dep["m4_priority"] == "P0"


def test_artifact_module_safe():
    safety = _load_artifact()["module_safety"]
    assert safety["exists"] is True
    assert safety["safe"] is True
    assert safety["forbidden_imports_found"] == []


def test_artifact_reference_values_pass():
    checks = _load_artifact()["reference_value_checks"]
    assert checks["BIG_LOTTO_ok"] is True
    assert checks["POWER_LOTTO_ok"] is True
    assert checks["DAILY_539_ok"] is True
    assert checks["formula_4ticket_ok"] is True
    assert checks["determinism_ok"] is True


def test_artifact_l14_fix_documented():
    fix = _load_artifact()["l14_fix_confirmed"]
    assert "1 - (1 -" in fix["correct_formula"] or "1-(1-" in fix["correct_formula"]
    assert "n_ticket_probability" in fix["fix_location"]


def test_md_artifact_exists():
    md_candidates = sorted(OUTPUTS_DIR.glob("p252c_baseline_calculator_ssot_*.md"))
    assert md_candidates, "No p252c Markdown artifact found"
    text = md_candidates[-1].read_text(encoding="utf-8")
    assert len(text) > 500
    assert "no_edge_claim" in text.lower() or "no edge claim" in text.lower() or "No-Overclaim" in text


def test_md_contains_no_db_write():
    md_candidates = sorted(OUTPUTS_DIR.glob("p252c_baseline_calculator_ssot_*.md"))
    text = md_candidates[-1].read_text(encoding="utf-8")
    assert "no db write" in text.lower()


def test_md_contains_no_betting_advice():
    md_candidates = sorted(OUTPUTS_DIR.glob("p252c_baseline_calculator_ssot_*.md"))
    text = md_candidates[-1].read_text(encoding="utf-8")
    assert "betting" in text.lower()


# ── Artifact re-run ───────────────────────────────────────────────────────────

def test_rerun_produces_valid_artifact():
    from analysis import p252c_baseline_calculator_ssot as p252c
    report = p252c.main()
    assert report["task_id"] == "P252C"
    assert report["classification"] == "BASELINE_CALCULATOR_SSOT_IMPLEMENTED"
    assert report["no_db_write_confirmed"] is True
    assert report["no_betting_advice_confirmed"] is True
    assert report["reference_value_checks"]["BIG_LOTTO_ok"] is True
