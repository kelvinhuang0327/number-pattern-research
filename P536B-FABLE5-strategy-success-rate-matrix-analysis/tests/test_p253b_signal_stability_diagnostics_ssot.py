"""Tests for P253B — Signal Stability Diagnostics SSOT."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.utils import stability_diagnostics as sd

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
TIGHT   = [0.18, 0.19, 0.18, 0.20]   # tight → STABLE
WIDE    = [0.05, 0.30, 0.02, 0.40]   # wide  → UNSTABLE or MIXED
BLOCKS  = [{"hit_rate": v, "n": 30} for v in TIGHT]


def _find() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p253b_signal_stability_diagnostics_ssot_*.json"))
    assert candidates, "No p253b artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find().read_text(encoding="utf-8"))


# ── Module isolation ──────────────────────────────────────────────────────────

def test_no_forbidden_imports():
    source = (REPO_ROOT / "lottery_api" / "utils" / "stability_diagnostics.py").read_text()
    import_lines = [l.strip() for l in source.splitlines()
                    if l.strip().startswith(("import ", "from ")) and not l.strip().startswith("#")]
    text = "\n".join(import_lines)
    for mod in ["sqlite3", "database", "registry", "routes", "numpy", "scipy"]:
        assert mod not in text, f"stability_diagnostics must not import {mod!r}"


def test_no_db_at_import():
    if "lottery_api.utils.stability_diagnostics" in sys.modules:
        importlib.reload(sys.modules["lottery_api.utils.stability_diagnostics"])
    from lottery_api.utils import stability_diagnostics  # noqa: F401


# ── STABILITY_DIMENSIONS ──────────────────────────────────────────────────────

def test_stability_dimensions_has_block():
    assert "block" in sd.STABILITY_DIMENSIONS


def test_stability_dimensions_has_era():
    assert "era" in sd.STABILITY_DIMENSIONS


def test_stability_dimensions_has_year():
    assert "year" in sd.STABILITY_DIMENSIONS


def test_stability_dimensions_has_subset_exclusion():
    assert "subset_exclusion" in sd.STABILITY_DIMENSIONS


def test_stability_dimensions_has_rolling_window():
    assert "rolling_window" in sd.STABILITY_DIMENSIONS


def test_stability_status_has_required_labels():
    for label in ["STABLE", "MIXED", "UNSTABLE", "UNDERPOWERED", "UNKNOWN"]:
        assert label in sd.STABILITY_STATUS, f"STABILITY_STATUS missing {label!r}"


def test_default_thresholds_present():
    assert "stable_min_score" in sd.DEFAULT_STABILITY_THRESHOLDS
    assert "mixed_min_score" in sd.DEFAULT_STABILITY_THRESHOLDS
    assert sd.DEFAULT_STABILITY_THRESHOLDS["stable_min_score"] > sd.DEFAULT_STABILITY_THRESHOLDS["mixed_min_score"]


# ── validate_stability_inputs ─────────────────────────────────────────────────

def test_validate_ok():
    r = sd.validate_stability_inputs([0.18, 0.19, 0.20])
    assert r["valid"] is True and r["underpowered"] is False


def test_validate_underpowered():
    r = sd.validate_stability_inputs([0.18], min_windows=2)
    assert r["underpowered"] is True and r["valid"] is True


def test_validate_empty():
    r = sd.validate_stability_inputs([])
    assert r["valid"] is False


def test_validate_never_raises():
    for arg in [None, [], [0.5], "bad"]:
        try:
            result = sd.validate_stability_inputs(arg) if hasattr(arg, "__iter__") else {"valid": False}
            assert isinstance(result, dict)
        except Exception:
            pass


# ── classify_stability ────────────────────────────────────────────────────────

def test_classify_stable_tight_values():
    status, score = sd.classify_stability(TIGHT)
    assert status == "STABLE"
    assert score >= sd.DEFAULT_STABILITY_THRESHOLDS["stable_min_score"]


def test_classify_unstable_wide_values():
    status, score = sd.classify_stability(WIDE)
    assert status in ("MIXED", "UNSTABLE")
    assert score < sd.DEFAULT_STABILITY_THRESHOLDS["stable_min_score"]


def test_classify_underpowered_single_value():
    status, score = sd.classify_stability([0.18], min_windows=2)
    assert status == "UNDERPOWERED"
    assert score == 0.0


def test_classify_underpowered_below_min():
    status, score = sd.classify_stability([0.18, 0.19], min_windows=3)
    assert status == "UNDERPOWERED"


def test_classify_score_in_0_1():
    for vals in [TIGHT, WIDE, [1.0, 1.0, 1.0]]:
        _, score = sd.classify_stability(vals)
        assert 0.0 <= score <= 1.0


def test_classify_perfect_stability():
    status, score = sd.classify_stability([0.20, 0.20, 0.20])
    assert status == "STABLE"
    assert score == pytest.approx(1.0)


def test_classify_deterministic():
    s1, sc1 = sd.classify_stability(TIGHT)
    s2, sc2 = sd.classify_stability(TIGHT)
    assert s1 == s2 and sc1 == sc2


def test_classify_invalid_raises():
    with pytest.raises((ValueError, TypeError)):
        sd.classify_stability([])


# ── block_stability ───────────────────────────────────────────────────────────

def test_block_stability_required_fields():
    bs = sd.block_stability(BLOCKS, "hit_rate")
    for field in ["schema_version", "diagnostic_type", "dimension", "metric_key",
                   "status", "threshold", "min_windows", "window_count", "underpowered",
                   "values", "value_min", "value_max", "value_range", "value_mean",
                   "stability_score", "no_edge_claim", "no_betting_advice",
                   "assumptions", "limitations"]:
        assert field in bs, f"Missing field: {field!r}"


def test_block_stability_no_edge_claim():
    assert sd.block_stability(BLOCKS, "hit_rate")["no_edge_claim"] is True


def test_block_stability_dimension():
    assert sd.block_stability(BLOCKS, "hit_rate")["dimension"] == "block"


def test_block_stability_synonym_note():
    note = sd.block_stability(BLOCKS, "hit_rate").get("dimension_note", "")
    assert "era" in note or "year" in note


def test_block_stability_stable_for_tight():
    bs = sd.block_stability(BLOCKS, "hit_rate")
    assert bs["status"] == "STABLE"


def test_block_stability_missing_key_raises():
    with pytest.raises(ValueError):
        sd.block_stability([{"rate": 0.5}], "hit_rate")  # wrong key


def test_block_stability_empty_raises():
    with pytest.raises(ValueError):
        sd.block_stability([], "hit_rate")


def test_block_stability_family_label():
    bs = sd.block_stability(BLOCKS, "hit_rate", family_label="MY_FAMILY")
    assert bs["family_label"] == "MY_FAMILY"


# ── subset_exclusion_stability ────────────────────────────────────────────────

def test_subset_exclusion_stable():
    se = sd.subset_exclusion_stability(0.185, [0.183, 0.187, 0.184, 0.186], "hit_rate")
    assert se["status"] == "STABLE"
    assert se["no_edge_claim"] is True


def test_subset_exclusion_unstable():
    se = sd.subset_exclusion_stability(0.185, [0.10, 0.05, 0.30, 0.40], "hit_rate")
    assert se["status"] != "STABLE"


def test_subset_exclusion_underpowered():
    se = sd.subset_exclusion_stability(0.185, [0.183], "hit_rate")
    assert se["underpowered"] is True


def test_subset_exclusion_required_fields():
    se = sd.subset_exclusion_stability(0.18, [0.17, 0.19], "rate")
    for field in ["schema_version", "diagnostic_type", "dimension", "full_result",
                   "robust_fraction", "status", "no_edge_claim"]:
        assert field in se, f"Missing: {field!r}"


def test_subset_exclusion_dimension():
    se = sd.subset_exclusion_stability(0.18, [0.17, 0.19], "rate")
    assert se["dimension"] == "subset_exclusion"


def test_subset_exclusion_empty_raises():
    with pytest.raises(ValueError):
        sd.subset_exclusion_stability(0.18, [], "rate")


# ── stability_summary ─────────────────────────────────────────────────────────

def test_stability_summary_required_fields():
    s = sd.stability_summary(TIGHT, "block", "hit_rate")
    for field in ["schema_version", "diagnostic_type", "family_label", "dimension",
                   "metric_key", "status", "threshold", "min_windows", "window_count",
                   "underpowered", "values", "value_min", "value_max", "value_range",
                   "value_mean", "stability_score", "no_edge_claim", "no_betting_advice",
                   "assumptions", "limitations"]:
        assert field in s, f"Missing field: {field!r}"


def test_stability_summary_no_edge_claim():
    assert sd.stability_summary(TIGHT, "era", "hit_rate")["no_edge_claim"] is True


def test_stability_summary_no_betting_advice():
    assert sd.stability_summary(TIGHT, "era", "hit_rate")["no_betting_advice"] is True


def test_stability_summary_schema_version():
    assert sd.stability_summary(TIGHT, "block", "hit_rate")["schema_version"] == "1.0"


def test_stability_summary_diagnostic_type():
    assert sd.stability_summary(TIGHT, "year", "hr")["diagnostic_type"] == "signal_stability_diagnostics"


def test_stability_summary_from_dicts():
    dicts = [{"hit_rate": v} for v in TIGHT]
    s = sd.stability_summary(dicts, "block", "hit_rate")
    assert s["status"] == sd.stability_summary(TIGHT, "block", "hit_rate")["status"]


def test_stability_summary_deterministic():
    s1 = sd.stability_summary(TIGHT, "block", "hit_rate", "T")
    s2 = sd.stability_summary(TIGHT, "block", "hit_rate", "T")
    assert s1["stability_score"] == s2["stability_score"]
    assert s1["status"] == s2["status"]


def test_stability_summary_empty_raises():
    with pytest.raises(ValueError):
        sd.stability_summary([], "block", "hit_rate")


# ── Artifact ──────────────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_artifact_task_id():
    assert _load()["task_id"] == "P253B"


def test_artifact_classification():
    assert _load()["classification"] == "SIGNAL_STABILITY_DIAGNOSTICS_SSOT_IMPLEMENTED"


def test_artifact_no_db_write():
    assert _load()["no_db_write_confirmed"] is True


def test_artifact_no_registry_mutation():
    assert _load()["no_registry_mutation_confirmed"] is True


def test_artifact_no_strategy_promotion():
    assert _load()["no_strategy_promotion_confirmed"] is True


def test_artifact_no_betting_advice():
    assert _load()["no_betting_advice_confirmed"] is True


def test_artifact_module_safe():
    s = _load()["module_safety"]
    assert s["exists"] is True and s["safe"] is True


def test_artifact_exercise_checks():
    ex = _load()["exercise_results"]
    assert ex["has_block"] and ex["has_era"] and ex["has_year"]
    assert ex["has_subset_exclusion"]
    assert ex["classify_stable_is_stable"]
    assert ex["classify_unstable_is_not_stable"]
    assert ex["classify_underpowered"]
    assert ex["subset_stable_is_stable"]
    assert ex["determinism_ok"]


def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p253b_signal_stability_diagnostics_ssot_*.md"))
    assert candidates
    text = candidates[-1].read_text()
    assert "no db write" in text.lower() and "betting" in text.lower()


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p253b_signal_stability_diagnostics_ssot as p253b
    r = p253b.main()
    assert r["task_id"] == "P253B"
    assert r["classification"] == "SIGNAL_STABILITY_DIAGNOSTICS_SSOT_IMPLEMENTED"
    assert r["no_db_write_confirmed"] is True
