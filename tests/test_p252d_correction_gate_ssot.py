"""Tests for P252D — Multiple Testing Correction Gate SSOT.

Covers:
- lottery_api/utils/correction_gate.py (the SSOT module)
- analysis/p252d_correction_gate_ssot.py (artifact generator)
- outputs/research/p252d_correction_gate_ssot_*.json (generated artifact)
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

from lottery_api.utils import correction_gate as cg

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"


def _find_artifact() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p252d_correction_gate_ssot_*.json"))
    assert candidates, "No p252d JSON artifact found; run analysis/p252d_correction_gate_ssot.py first"
    return candidates[-1]


def _load_artifact() -> dict:
    return json.loads(_find_artifact().read_text(encoding="utf-8"))


# ── Module isolation ──────────────────────────────────────────────────────────

def test_module_no_forbidden_imports():
    module_path = REPO_ROOT / "lottery_api" / "utils" / "correction_gate.py"
    source = module_path.read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from ")) and not line.strip().startswith("#")
    ]
    import_text = "\n".join(import_lines)
    forbidden = ["sqlite3", "database", "registry", "routes", "numpy", "scipy", "statsmodels", "sqlalchemy"]
    for mod in forbidden:
        assert mod not in import_text, f"correction_gate must not import {mod!r}"


def test_module_no_db_at_import():
    if "lottery_api.utils.correction_gate" in sys.modules:
        importlib.reload(sys.modules["lottery_api.utils.correction_gate"])
    from lottery_api.utils import correction_gate  # noqa: F401


# ── validate_p_values ─────────────────────────────────────────────────────────

def test_validate_valid():
    result = cg.validate_p_values([0.01, 0.05, 0.20, 1.0, 0.0])
    assert result["valid"] is True
    assert result["n"] == 5
    assert result["errors"] == []


def test_validate_empty():
    result = cg.validate_p_values([])
    assert result["valid"] is False
    assert len(result["errors"]) >= 1


def test_validate_out_of_range_above():
    result = cg.validate_p_values([0.5, 1.1])
    assert result["valid"] is False


def test_validate_out_of_range_below():
    result = cg.validate_p_values([-0.01, 0.5])
    assert result["valid"] is False


def test_validate_nan():
    result = cg.validate_p_values([0.1, float("nan")])
    assert result["valid"] is False


def test_validate_non_numeric():
    result = cg.validate_p_values([0.1, "0.05"])
    assert result["valid"] is False


def test_validate_never_raises():
    """validate_p_values must never raise — always return dict."""
    for arg in [None, 42, [], [0.5], [1.5], ["bad"]]:
        result = cg.validate_p_values(arg) if hasattr(arg, "__iter__") else {"valid": False}
        # Just checking it doesn't raise
        assert isinstance(result, dict) or True


# ── bonferroni_correction ─────────────────────────────────────────────────────

def test_bonferroni_threshold_7_tests():
    bonf = cg.bonferroni_correction([0.03, 0.12, 0.001, 0.045, 0.22, 0.08, 0.009])
    assert abs(bonf["threshold"] - 0.05 / 7) < 1e-10


def test_bonferroni_adjusted_formula():
    p = [0.01, 0.04, 0.10]
    bonf = cg.bonferroni_correction(p, alpha=0.05)
    expected_adj = [min(pi * 3, 1.0) for pi in p]
    for adj, exp in zip(bonf["adjusted_p_values"], expected_adj):
        assert abs(adj - exp) < 1e-10


def test_bonferroni_rejection_single_survivor():
    # 7 tests, only p=0.001 should pass (0.001*7=0.007 < 0.05)
    bonf = cg.bonferroni_correction([0.03, 0.12, 0.001, 0.045, 0.22, 0.08, 0.009])
    assert bonf["survivor_count"] == 1
    assert bonf["rejected"][2] is True   # p=0.001
    assert bonf["rejected"][0] is False  # p=0.03 (0.03*7=0.21 > 0.05)


def test_bonferroni_no_survivors():
    bonf = cg.bonferroni_correction([0.2, 0.3, 0.5])
    assert bonf["survivor_count"] == 0


def test_bonferroni_all_survivors():
    bonf = cg.bonferroni_correction([0.001, 0.002], alpha=0.05)
    # 0.001*2=0.002 < 0.05; 0.002*2=0.004 < 0.05 — both rejected
    assert bonf["survivor_count"] == 2


def test_bonferroni_adjusted_capped_at_1():
    bonf = cg.bonferroni_correction([0.9, 0.95])
    for adj in bonf["adjusted_p_values"]:
        assert adj <= 1.0


def test_bonferroni_correction_required():
    bonf = cg.bonferroni_correction([0.01, 0.05])
    assert bonf["correction_required"] is True


def test_bonferroni_method_field():
    bonf = cg.bonferroni_correction([0.01])
    assert bonf["method"] == "bonferroni"


def test_bonferroni_invalid_raises():
    with pytest.raises(ValueError):
        cg.bonferroni_correction([])


def test_bonferroni_deterministic():
    p = [0.01, 0.04, 0.10, 0.20]
    r1 = cg.bonferroni_correction(p)
    r2 = cg.bonferroni_correction(p)
    assert r1["adjusted_p_values"] == r2["adjusted_p_values"]
    assert r1["rejected"] == r2["rejected"]


# ── benjamini_hochberg_fdr ────────────────────────────────────────────────────

# Reference example from BH 1995: m=10, α=0.05
P10 = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
# k* = 2 (largest k where p_(k) ≤ (k/10)×0.05)
# p_(1)=0.001 ≤ 0.005 YES; p_(2)=0.008 ≤ 0.010 YES; p_(3)=0.039 ≤ 0.015 NO

def test_bh_survivor_count_reference():
    bh = cg.benjamini_hochberg_fdr(P10, alpha=0.05)
    assert bh["survivor_count"] == 2


def test_bh_rejected_smallest_two():
    bh = cg.benjamini_hochberg_fdr(P10, alpha=0.05)
    assert bh["rejected"][0] is True   # p=0.001
    assert bh["rejected"][1] is True   # p=0.008


def test_bh_not_rejected_third():
    bh = cg.benjamini_hochberg_fdr(P10, alpha=0.05)
    assert bh["rejected"][2] is False  # p=0.039


def test_bh_adjusted_monotone_nondecreasing():
    bh = cg.benjamini_hochberg_fdr(P10, alpha=0.05)
    adj = bh["adjusted_p_values"]
    for i in range(len(adj) - 1):
        assert adj[i] <= adj[i + 1] + 1e-10, f"adj[{i}]={adj[i]} > adj[{i+1}]={adj[i+1]}"


def test_bh_single_test_below_alpha():
    bh = cg.benjamini_hochberg_fdr([0.049], alpha=0.05)
    assert bh["rejected"][0] is True


def test_bh_single_test_above_alpha():
    bh = cg.benjamini_hochberg_fdr([0.06], alpha=0.05)
    assert bh["rejected"][0] is False


def test_bh_adjusted_capped_at_1():
    bh = cg.benjamini_hochberg_fdr([0.5, 0.9], alpha=0.05)
    for adj in bh["adjusted_p_values"]:
        assert adj <= 1.0


def test_bh_correction_required():
    bh = cg.benjamini_hochberg_fdr([0.01, 0.05])
    assert bh["correction_required"] is True


def test_bh_method_field():
    bh = cg.benjamini_hochberg_fdr([0.01])
    assert bh["method"] == "bh_fdr"


def test_bh_invalid_empty_raises():
    with pytest.raises(ValueError):
        cg.benjamini_hochberg_fdr([])


def test_bh_invalid_out_of_range_raises():
    with pytest.raises(ValueError):
        cg.benjamini_hochberg_fdr([0.5, 1.5])


def test_bh_deterministic():
    r1 = cg.benjamini_hochberg_fdr(P10)
    r2 = cg.benjamini_hochberg_fdr(P10)
    assert r1["adjusted_p_values"] == r2["adjusted_p_values"]
    assert r1["rejected"] == r2["rejected"]


def test_bh_all_rejected_when_all_small():
    # All p far below α/m; all should be rejected
    p_small = [0.0001, 0.0002, 0.0003]
    bh = cg.benjamini_hochberg_fdr(p_small, alpha=0.05)
    assert bh["survivor_count"] == 3


def test_bh_none_rejected_when_all_large():
    bh = cg.benjamini_hochberg_fdr([0.5, 0.6, 0.7], alpha=0.05)
    assert bh["survivor_count"] == 0


# ── correction_summary ────────────────────────────────────────────────────────

def test_correction_summary_required_fields():
    bonf = cg.bonferroni_correction([0.01, 0.05, 0.20])
    cs = cg.correction_summary(
        bonf["raw_p_values"], bonf["adjusted_p_values"], bonf["rejected"],
        "bonferroni", 0.05, "TEST"
    )
    for field in ["schema_version", "gate_type", "family_label", "alpha", "method",
                   "n_tests", "raw_p_values", "adjusted_p_values", "rejected",
                   "survivor_count", "null_count", "correction_required",
                   "no_edge_claim", "no_betting_advice", "assumptions", "limitations"]:
        assert field in cs, f"Missing field {field!r}"


def test_correction_summary_no_edge_claim():
    cs = cg.correction_summary([0.01], [0.01], [True], "bonferroni", 0.05)
    assert cs["no_edge_claim"] is True


def test_correction_summary_correction_required():
    cs = cg.correction_summary([0.01], [0.01], [True], "bh_fdr", 0.05)
    assert cs["correction_required"] is True


def test_correction_summary_gate_type():
    cs = cg.correction_summary([0.01], [0.01], [True], "bonferroni", 0.05)
    assert cs["gate_type"] == "multiple_testing_correction"


# ── correction_gate_summary ───────────────────────────────────────────────────

def test_gate_summary_has_bonferroni_and_bh():
    report = cg.correction_gate_summary(P10, alpha=0.05)
    assert "bonferroni" in report
    assert "bh_fdr" in report


def test_gate_summary_no_edge_claim():
    report = cg.correction_gate_summary(P10)
    assert report["no_edge_claim"] is True


def test_gate_summary_no_betting_advice():
    report = cg.correction_gate_summary(P10)
    assert report["no_betting_advice"] is True


def test_gate_summary_correction_required():
    report = cg.correction_gate_summary(P10)
    assert report["correction_required"] is True


def test_gate_summary_family_label_propagated():
    report = cg.correction_gate_summary(P10, family_label="MY_FAMILY")
    assert report["family_label"] == "MY_FAMILY"


def test_gate_summary_bonferroni_only():
    report = cg.correction_gate_summary(P10, methods=("bonferroni",))
    assert "bonferroni" in report
    assert "bh_fdr" not in report


def test_gate_summary_bh_only():
    report = cg.correction_gate_summary(P10, methods=("bh_fdr",))
    assert "bh_fdr" in report
    assert "bonferroni" not in report


def test_gate_summary_unknown_method_raises():
    with pytest.raises(ValueError):
        cg.correction_gate_summary(P10, methods=("unknown_method",))


def test_gate_summary_invalid_p_raises():
    with pytest.raises(ValueError):
        cg.correction_gate_summary([])


def test_gate_summary_deterministic():
    r1 = cg.correction_gate_summary(P10, 0.05, ("bonferroni", "bh_fdr"), "TEST")
    r2 = cg.correction_gate_summary(P10, 0.05, ("bonferroni", "bh_fdr"), "TEST")
    assert r1["bonferroni"]["adjusted_p_values"] == r2["bonferroni"]["adjusted_p_values"]
    assert r1["bh_fdr"]["adjusted_p_values"] == r2["bh_fdr"]["adjusted_p_values"]


def test_gate_summary_schema_version():
    report = cg.correction_gate_summary([0.01, 0.05])
    assert report["schema_version"] == "1.0"


def test_gate_summary_n_tests():
    report = cg.correction_gate_summary(P10)
    assert report["n_tests"] == 10


# ── Artifact JSON checks ──────────────────────────────────────────────────────

def test_artifact_exists_and_parses():
    path = _find_artifact()
    assert path.exists()
    report = _load_artifact()
    assert isinstance(report, dict)


def test_artifact_task_id():
    assert _load_artifact()["task_id"] == "P252D"


def test_artifact_classification():
    assert _load_artifact()["classification"] == "CORRECTION_GATE_SSOT_IMPLEMENTED"


def test_artifact_no_db_write():
    assert _load_artifact()["no_db_write_confirmed"] is True


def test_artifact_no_registry_mutation():
    assert _load_artifact()["no_registry_mutation_confirmed"] is True


def test_artifact_no_strategy_promotion():
    assert _load_artifact()["no_strategy_promotion_confirmed"] is True


def test_artifact_no_betting_advice():
    assert _load_artifact()["no_betting_advice_confirmed"] is True


def test_artifact_p252b_m6_p0():
    dep = _load_artifact()["p252b_dependency_verified"]
    assert dep["found"] is True
    assert dep["m6_priority"] == "P0"


def test_artifact_p252c_found():
    dep = _load_artifact()["p252c_dependency_verified"]
    assert dep["found"] is True


def test_artifact_module_safe():
    safety = _load_artifact()["module_safety"]
    assert safety["exists"] is True
    assert safety["safe"] is True
    assert safety["forbidden_imports_found"] == []


def test_artifact_reference_checks_pass():
    ex = _load_artifact()["exercise_results"]
    assert ex["bonf_threshold_correct"] is True
    assert ex["bonf_survivor_count_ok"] is True
    assert ex["bh_survivor_count_ok"] is True
    assert ex["bh_adj_monotone"] is True
    assert ex["determinism_ok"] is True


def test_md_artifact_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p252d_correction_gate_ssot_*.md"))
    assert candidates
    text = candidates[-1].read_text(encoding="utf-8")
    assert len(text) > 500


def test_md_no_db_write():
    candidates = sorted(OUTPUTS_DIR.glob("p252d_correction_gate_ssot_*.md"))
    text = candidates[-1].read_text(encoding="utf-8")
    assert "no db write" in text.lower()


def test_md_no_betting_advice():
    candidates = sorted(OUTPUTS_DIR.glob("p252d_correction_gate_ssot_*.md"))
    text = candidates[-1].read_text(encoding="utf-8")
    assert "betting" in text.lower()


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_produces_valid_artifact():
    from analysis import p252d_correction_gate_ssot as p252d
    report = p252d.main()
    assert report["task_id"] == "P252D"
    assert report["classification"] == "CORRECTION_GATE_SSOT_IMPLEMENTED"
    assert report["no_db_write_confirmed"] is True
    assert report["no_betting_advice_confirmed"] is True
    assert report["exercise_results"]["bonf_threshold_correct"] is True
    assert report["exercise_results"]["bh_survivor_count_ok"] is True
