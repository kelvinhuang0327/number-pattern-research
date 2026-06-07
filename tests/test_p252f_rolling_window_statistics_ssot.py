"""Tests for P252F — Rolling Window Statistics SSOT."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.utils import rolling_window as rw

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
ITEMS10 = list(range(10))  # [0..9]


def _find_artifact() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p252f_rolling_window_statistics_ssot_*.json"))
    assert candidates, "No p252f JSON artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find_artifact().read_text(encoding="utf-8"))


# ── Module isolation ──────────────────────────────────────────────────────────

def test_no_forbidden_imports():
    source = (REPO_ROOT / "lottery_api" / "utils" / "rolling_window.py").read_text()
    import_lines = [l.strip() for l in source.splitlines()
                    if l.strip().startswith(("import ", "from ")) and not l.strip().startswith("#")]
    text = "\n".join(import_lines)
    for mod in ["sqlite3", "database", "registry", "routes", "numpy", "scipy", "statsmodels"]:
        assert mod not in text, f"rolling_window must not import {mod!r}"


def test_no_db_at_import():
    if "lottery_api.utils.rolling_window" in sys.modules:
        importlib.reload(sys.modules["lottery_api.utils.rolling_window"])
    from lottery_api.utils import rolling_window  # noqa: F401


# ── Window constants ──────────────────────────────────────────────────────────

def test_p221f_short_contains_150():
    assert 150 in rw.P221F_WINDOWS["short"]


def test_p221f_short_contains_100_and_125():
    assert 100 in rw.P221F_WINDOWS["short"]
    assert 125 in rw.P221F_WINDOWS["short"]


def test_p221f_mid_contains_500_750_1000():
    for w in (500, 750, 1000):
        assert w in rw.P221F_WINDOWS["mid"], f"P221F mid missing {w}"


def test_rsm_windows_short_is_30():
    assert rw.RSM_WINDOWS["short"] == 30


def test_rsm_windows_has_medium_long():
    assert "medium" in rw.RSM_WINDOWS
    assert "long" in rw.RSM_WINDOWS


# ── validate_window_config ────────────────────────────────────────────────────

def test_validate_ok():
    r = rw.validate_window_config(200, 150, 1)
    assert r["valid"] is True
    assert r["underpowered"] is False


def test_validate_window_count_formula():
    # (total_count - window_size + 1) / step_size = (10-3+1)/1 = 8
    r = rw.validate_window_config(10, 3, 1)
    assert r["window_count"] == 8


def test_validate_underpowered():
    r = rw.validate_window_config(50, 150, 1)
    assert r["underpowered"] is True
    assert r["valid"] is True  # underpowered is a warning, not an error


def test_validate_invalid_window_size_zero():
    r = rw.validate_window_config(100, 0, 1)
    assert r["valid"] is False


def test_validate_invalid_step_size_zero():
    r = rw.validate_window_config(100, 10, 0)
    assert r["valid"] is False


def test_validate_never_raises():
    for args in [(-1, 10, 1), (100, -5, 1), (100, 10, -1)]:
        result = rw.validate_window_config(*args)
        assert isinstance(result, dict)


# ── rolling_slices ────────────────────────────────────────────────────────────

def test_slices_count_step1():
    # n=10, ws=3, step=1 → 10-3+1=8 windows
    slices = rw.rolling_slices(ITEMS10, 3, 1)
    assert len(slices) == 8


def test_slices_first_window():
    slices = rw.rolling_slices(ITEMS10, 3)
    assert slices[0] == [0, 1, 2]


def test_slices_last_window():
    slices = rw.rolling_slices(ITEMS10, 3)
    assert slices[-1] == [7, 8, 9]


def test_slices_step2():
    # n=10, ws=3, step=2 → starts at 0,2,4,6 → 4 windows
    slices = rw.rolling_slices(ITEMS10, 3, step_size=2)
    assert len(slices) == 4
    assert slices[0] == [0, 1, 2]
    assert slices[1] == [2, 3, 4]


def test_slices_include_partial_false():
    # n=5, ws=3, step=2 → starts 0,2; [0,1,2] full; [2,3,4] full; [4] partial not included
    slices = rw.rolling_slices(list(range(5)), 3, step_size=2, include_partial=False)
    assert all(len(s) == 3 for s in slices)


def test_slices_include_partial_true():
    # n=5, ws=4, step=3 → [0,1,2,3] full; [3,4] partial
    slices = rw.rolling_slices(list(range(5)), 4, step_size=3, include_partial=True)
    assert len(slices) == 2
    assert slices[-1] == [3, 4]


def test_slices_invalid_window_size_raises():
    with pytest.raises(ValueError):
        rw.rolling_slices(ITEMS10, 0)


def test_slices_invalid_step_raises():
    with pytest.raises(ValueError):
        rw.rolling_slices(ITEMS10, 3, step_size=0)


def test_slices_larger_than_items():
    # window larger than sequence → no full windows
    slices = rw.rolling_slices([1, 2], 5, include_partial=False)
    assert slices == []


def test_slices_deterministic():
    s1 = rw.rolling_slices(ITEMS10, 3)
    s2 = rw.rolling_slices(ITEMS10, 3)
    assert s1 == s2


# ── tail_window ───────────────────────────────────────────────────────────────

def test_tail_window_full():
    assert rw.tail_window(ITEMS10, 3) == [7, 8, 9]


def test_tail_window_partial():
    assert rw.tail_window([1, 2], 5) == [1, 2]


def test_tail_window_exact():
    assert rw.tail_window([1, 2, 3], 3) == [1, 2, 3]


def test_tail_window_empty_input():
    assert rw.tail_window([], 5) == []


# ── rolling_window_labels ─────────────────────────────────────────────────────

def test_labels_count():
    labels = rw.rolling_window_labels(10, 3, 1)
    assert len(labels) == 8  # same as slices


def test_labels_first():
    assert rw.rolling_window_labels(10, 3)[0] == "w3[0:3]"


def test_labels_last():
    assert rw.rolling_window_labels(10, 3)[-1] == "w3[7:10]"


def test_labels_stable_format():
    labels = rw.rolling_window_labels(200, 150, 50)
    for lbl in labels:
        assert lbl.startswith("w150[")
        assert ":" in lbl


def test_labels_invalid_window_raises():
    with pytest.raises(ValueError):
        rw.rolling_window_labels(10, 0)


# ── tail_window_label ─────────────────────────────────────────────────────────

def test_tail_label_full():
    assert rw.tail_window_label(200, 150) == "tail_150"


def test_tail_label_partial():
    assert rw.tail_window_label(80, 150) == "partial_80_of_150"


def test_tail_label_exact():
    assert rw.tail_window_label(150, 150) == "tail_150"


# ── summarize_window ──────────────────────────────────────────────────────────

def test_summarize_numeric():
    sw = rw.summarize_window([1.0, 2.0, 3.0, 4.0, 5.0])
    assert sw["count"] == 5
    assert abs(sw["mean"] - 3.0) < 1e-10
    assert sw["min"] == 1.0
    assert sw["max"] == 5.0


def test_summarize_label_propagated():
    sw = rw.summarize_window([1, 2, 3], label="MY_LABEL")
    assert sw["label"] == "MY_LABEL"


def test_summarize_start_index():
    sw = rw.summarize_window([1, 2, 3], start_index=5)
    assert sw["start_index"] == 5
    assert sw["end_index"] == 8


def test_summarize_non_numeric_returns_none():
    sw = rw.summarize_window(["a", "b", "c"])
    assert sw["mean"] is None
    assert sw["min"] is None
    assert sw["max"] is None


def test_summarize_single_value():
    sw = rw.summarize_window([42.0])
    assert sw["mean"] == pytest.approx(42.0)
    assert sw["std"] == 0.0


# ── rolling_summary ───────────────────────────────────────────────────────────

def test_rolling_summary_no_edge_claim():
    r = rw.rolling_summary(list(range(200)), 150)
    assert r["no_edge_claim"] is True


def test_rolling_summary_no_betting_advice():
    r = rw.rolling_summary(list(range(200)), 150)
    assert r["no_betting_advice"] is True


def test_rolling_summary_schema_version():
    r = rw.rolling_summary(list(range(200)), 150)
    assert r["schema_version"] == "1.0"


def test_rolling_summary_summary_type():
    r = rw.rolling_summary(list(range(200)), 150)
    assert r["summary_type"] == "rolling_window_statistics"


def test_rolling_summary_family_label():
    r = rw.rolling_summary(list(range(200)), 150, family_label="MY_FAMILY")
    assert r["family_label"] == "MY_FAMILY"


def test_rolling_summary_single_window_size():
    r = rw.rolling_summary(list(range(200)), 150)
    assert len(r["window_series"]) == 1
    assert r["window_series"][0]["window_size"] == 150


def test_rolling_summary_multiple_window_sizes():
    r = rw.rolling_summary(list(range(500)), (100, 150, 500))
    assert len(r["window_series"]) == 3


def test_rolling_summary_numeric_mean_correct():
    items = [float(i) for i in range(10)]  # 0..9
    r = rw.rolling_summary(items, 5, step_size=5)
    # windows: [0-4] mean=2.0, [5-9] mean=7.0
    series = r["window_series"][0]
    assert len(series["windows"]) == 2
    assert abs(series["windows"][0]["mean"] - 2.0) < 1e-10
    assert abs(series["windows"][1]["mean"] - 7.0) < 1e-10


def test_rolling_summary_required_fields():
    r = rw.rolling_summary(list(range(200)), 150)
    for field in ["schema_version", "summary_type", "family_label", "total_count",
                   "step_size", "include_partial", "min_count", "window_series",
                   "window_sizes_requested", "no_edge_claim", "no_betting_advice",
                   "assumptions", "limitations"]:
        assert field in r, f"Missing field: {field!r}"


def test_rolling_summary_deterministic():
    r1 = rw.rolling_summary(list(range(500)), (150, 500), 50, family_label="T")
    r2 = rw.rolling_summary(list(range(500)), (150, 500), 50, family_label="T")
    assert r1["window_series"][0]["window_count"] == r2["window_series"][0]["window_count"]


def test_rolling_summary_invalid_step_raises():
    with pytest.raises(ValueError):
        rw.rolling_summary(list(range(100)), 50, step_size=0)


def test_rolling_summary_empty_window_sizes_raises():
    with pytest.raises(ValueError):
        rw.rolling_summary(list(range(100)), ())


def test_rolling_summary_assumptions_nonempty():
    r = rw.rolling_summary(list(range(100)), 50)
    assert isinstance(r["assumptions"], list) and len(r["assumptions"]) >= 1


def test_rolling_summary_limitations_nonempty():
    r = rw.rolling_summary(list(range(100)), 50)
    assert isinstance(r["limitations"], list) and len(r["limitations"]) >= 1


# ── Artifact checks ───────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_artifact_task_id():
    assert _load()["task_id"] == "P252F"


def test_artifact_classification():
    assert _load()["classification"] == "ROLLING_WINDOW_STATISTICS_SSOT_IMPLEMENTED"


def test_artifact_no_db_write():
    assert _load()["no_db_write_confirmed"] is True


def test_artifact_no_registry_mutation():
    assert _load()["no_registry_mutation_confirmed"] is True


def test_artifact_no_strategy_promotion():
    assert _load()["no_strategy_promotion_confirmed"] is True


def test_artifact_no_betting_advice():
    assert _load()["no_betting_advice_confirmed"] is True


def test_artifact_p252b_m3_p0():
    dep = _load()["p252b_dependency_verified"]
    assert dep["found"] is True
    assert dep["m_id_priority"] == "P0"


def test_artifact_module_safe():
    safety = _load()["module_safety"]
    assert safety["exists"] is True
    assert safety["safe"] is True
    assert safety["forbidden_imports_found"] == []


def test_artifact_exercise_checks():
    ex = _load()["exercise_results"]
    assert ex["p221f_short_contains_150"] is True
    assert ex["slices_3_count_ok"] is True
    assert ex["slices_3_first_ok"] is True
    assert ex["tail_3_ok"] is True
    assert ex["labels_first_ok"] is True
    assert ex["tail_label_full_ok"] is True
    assert ex["sw_mean_ok"] is True
    assert ex["rs_no_edge_claim"] is True
    assert ex["rs_deterministic"] is True


def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p252f_rolling_window_statistics_ssot_*.md"))
    assert candidates
    text = candidates[-1].read_text()
    assert "no db write" in text.lower()
    assert "betting" in text.lower()


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p252f_rolling_window_statistics_ssot as p252f
    r = p252f.main()
    assert r["task_id"] == "P252F"
    assert r["classification"] == "ROLLING_WINDOW_STATISTICS_SSOT_IMPLEMENTED"
    assert r["no_db_write_confirmed"] is True
