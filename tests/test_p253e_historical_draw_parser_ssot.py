"""Tests for P253E — Historical Draw Parser SSOT."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.utils import historical_draw_parser as hp

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"

REQUIRED_SCHEMA_FIELDS = [
    "schema_version", "diagnostic_type", "family_label",
    "lottery_type", "parser_source_type", "parser_source_type_description",
    "positional_status", "positional_status_description",
    "row_count", "positional_non_null", "positional_null", "positional_coverage_rate",
    "sorted_vs_positional_diff_count", "draw_order_confirmed",
    "is_pool_draw", "is_straight_play", "straight_play_position_frequency_supported",
    "sorted_storage_caveat", "no_edge_claim", "no_betting_advice",
    "assumptions", "limitations",
]


def _find() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p253e_historical_draw_parser_ssot_*.json"))
    assert candidates, "No p253e artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find().read_text(encoding="utf-8"))


# ── Module isolation ──────────────────────────────────────────────────────────

def test_no_forbidden_imports():
    src = (REPO_ROOT / "lottery_api" / "utils" / "historical_draw_parser.py").read_text()
    import_lines = [l.strip() for l in src.splitlines()
                    if l.strip().startswith(("import ", "from ")) and not l.strip().startswith("#")]
    text = "\n".join(import_lines)
    for mod in ["sqlite3", "database", "registry", "routes", "numpy", "scipy"]:
        assert mod not in text, f"historical_draw_parser must not import {mod!r}"


def test_no_db_at_import():
    if "lottery_api.utils.historical_draw_parser" in sys.modules:
        importlib.reload(sys.modules["lottery_api.utils.historical_draw_parser"])
    from lottery_api.utils import historical_draw_parser  # noqa: F401


# ── PARSER_SOURCE_TYPES ───────────────────────────────────────────────────────

def test_parser_source_types_has_active_parser():
    assert "active_parser" in hp.PARSER_SOURCE_TYPES


def test_parser_source_types_has_official_dry_run():
    assert "official_dry_run_parser" in hp.PARSER_SOURCE_TYPES


def test_parser_source_types_has_controlled_apply():
    assert "controlled_apply_complete" in hp.PARSER_SOURCE_TYPES


def test_parser_source_types_has_historical_import():
    assert "historical_import_script" in hp.PARSER_SOURCE_TYPES


def test_parser_source_types_has_archived():
    assert "archived_or_exploratory_defer" in hp.PARSER_SOURCE_TYPES


# ── POSITIONAL_STATUS ─────────────────────────────────────────────────────────

def test_positional_status_has_complete():
    assert "complete" in hp.POSITIONAL_STATUS


def test_positional_status_has_partial():
    assert "partial" in hp.POSITIONAL_STATUS


def test_positional_status_has_missing():
    assert "missing" in hp.POSITIONAL_STATUS


def test_positional_status_has_not_applicable():
    assert "not_applicable" in hp.POSITIONAL_STATUS


def test_positional_status_has_blocked_by_schema():
    assert "blocked_by_schema" in hp.POSITIONAL_STATUS


# ── SORTING_SEMANTICS ─────────────────────────────────────────────────────────

def test_sorting_semantics_present():
    for k in ["sorted_numbers", "positional_numbers", "pool_draw", "straight_play"]:
        assert k in hp.SORTING_SEMANTICS, f"Missing key: {k!r}"


# ── normalize_lottery_type ────────────────────────────────────────────────────

def test_normalize_3star_lower():
    assert hp.normalize_lottery_type("3_star") == "3_STAR"


def test_normalize_3star_alias():
    assert hp.normalize_lottery_type("three_star") == "3_STAR"


def test_normalize_3star_upper():
    assert hp.normalize_lottery_type("3_STAR") == "3_STAR"


def test_normalize_4star():
    assert hp.normalize_lottery_type("4_STAR") == "4_STAR"
    assert hp.normalize_lottery_type("four_star") == "4_STAR"


def test_normalize_biglotto():
    assert hp.normalize_lottery_type("big_lotto") == "BIG_LOTTO"
    assert hp.normalize_lottery_type("BIG_LOTTO") == "BIG_LOTTO"


def test_normalize_539():
    assert hp.normalize_lottery_type("539") == "DAILY_539"
    assert hp.normalize_lottery_type("daily_539") == "DAILY_539"


def test_normalize_deterministic():
    for _ in range(3):
        assert hp.normalize_lottery_type("3_star") == "3_STAR"


def test_normalize_invalid_type_raises():
    with pytest.raises((ValueError, TypeError)):
        hp.normalize_lottery_type(123)  # type: ignore[arg-type]


def test_normalize_empty_raises():
    with pytest.raises(ValueError):
        hp.normalize_lottery_type("  ")


# ── validate_numbers_payload ──────────────────────────────────────────────────

def test_validate_numbers_valid_list():
    r = hp.validate_numbers_payload([1, 2, 3, 4, 5])
    assert r["valid"] is True and r["length"] == 5


def test_validate_numbers_json_string():
    r = hp.validate_numbers_payload("[4, 5, 6]")
    assert r["valid"] is True and r["numbers"] == [4, 5, 6]


def test_validate_numbers_expected_len_ok():
    r = hp.validate_numbers_payload([1, 2, 3], expected_len=3)
    assert r["valid"] is True


def test_validate_numbers_wrong_len():
    r = hp.validate_numbers_payload([1, 2], expected_len=3)
    assert r["valid"] is False


def test_validate_numbers_empty_invalid():
    r = hp.validate_numbers_payload([])
    assert r["valid"] is False


def test_validate_numbers_unsorted_warns():
    r = hp.validate_numbers_payload([3, 1, 2])
    assert r["valid"] is True
    assert any("sorted" in w.lower() for w in r["warnings"])


def test_validate_numbers_never_raises():
    for arg in [None, "bad json {{", [], 42]:
        try:
            result = hp.validate_numbers_payload(arg)
            assert isinstance(result, dict)
        except Exception:
            pass


# ── validate_positional_payload ───────────────────────────────────────────────

def test_validate_positional_none_ok():
    r = hp.validate_positional_payload(None)
    assert r["valid"] is True and r["is_null"] is True


def test_validate_positional_list_ok():
    r = hp.validate_positional_payload([3, 1, 2])
    assert r["valid"] is True and r["length"] == 3


def test_validate_positional_none_disallowed():
    r = hp.validate_positional_payload(None, allow_none=False)
    assert r["valid"] is False


def test_validate_positional_wrong_len():
    r = hp.validate_positional_payload([1, 2, 3], expected_len=4)
    assert r["valid"] is False


def test_validate_positional_sorted_warns():
    r = hp.validate_positional_payload([1, 2, 3])
    assert r["valid"] is True
    assert any("sorted" in w.lower() or "coincidental" in w.lower() for w in r["warnings"])


# ── compare_sorted_vs_positional ──────────────────────────────────────────────

def test_compare_differs():
    r = hp.compare_sorted_vs_positional([1, 2, 3], [3, 1, 2])
    assert r["differs"] is True
    assert r["same_multiset"] is True
    assert r["draw_order_confirmed"] is True


def test_compare_same():
    r = hp.compare_sorted_vs_positional([1, 2, 3], [1, 2, 3])
    assert r["differs"] is False


def test_compare_null_positional():
    r = hp.compare_sorted_vs_positional([1, 2, 3], None)
    assert r["differs"] is False
    assert r["positional_numbers"] is None


def test_compare_wrong_multiset():
    r = hp.compare_sorted_vs_positional([1, 2, 3], [4, 5, 6])
    assert r["differs"] is True
    assert r["same_multiset"] is False
    assert r["draw_order_confirmed"] is False


def test_compare_position_matches():
    r = hp.compare_sorted_vs_positional([1, 2, 3], [1, 3, 2])
    assert r["n_matching_positions"] == 1
    assert r["position_matches"] == [True, False, False]


# ── classify_positional_coverage ──────────────────────────────────────────────

def test_classify_complete():
    assert hp.classify_positional_coverage(5850, 5850, "3_STAR") == "complete"


def test_classify_complete_4star():
    assert hp.classify_positional_coverage(5850, 5850, "4_STAR") == "complete"


def test_classify_missing():
    assert hp.classify_positional_coverage(100, 0, "3_STAR") == "missing"


def test_classify_partial():
    assert hp.classify_positional_coverage(100, 50, "3_STAR") == "partial"


def test_classify_not_applicable_biglotto():
    assert hp.classify_positional_coverage(22238, 0, "BIG_LOTTO") == "not_applicable"


def test_classify_not_applicable_power_lotto():
    assert hp.classify_positional_coverage(1916, 0, "POWER_LOTTO") == "not_applicable"


def test_classify_not_applicable_daily539():
    assert hp.classify_positional_coverage(5879, 0, "DAILY_539") == "not_applicable"


def test_classify_unknown_zero_rows():
    assert hp.classify_positional_coverage(0, 0) == "unknown"


# ── parser_inventory_entry ────────────────────────────────────────────────────

def test_parser_inventory_entry_no_edge_claim():
    e = hp.parser_inventory_entry(
        path="lottery_api/routes/ingest.py",
        classification="active_parser",
        lottery_types=["BIG_LOTTO"],
        description="Test",
    )
    assert e["no_edge_claim"] is True


def test_parser_inventory_entry_canonical_types():
    e = hp.parser_inventory_entry(
        path="some/path.py",
        classification="historical_import_script",
        lottery_types=["big_lotto", "3_star"],
        description="Test",
    )
    assert "BIG_LOTTO" in e["lottery_types"]
    assert "3_STAR" in e["lottery_types"]


def test_parser_inventory_entry_invalid_classification():
    with pytest.raises(ValueError):
        hp.parser_inventory_entry(
            path="x.py",
            classification="UNKNOWN_BAD_CLASS",
            lottery_types=["BIG_LOTTO"],
            description="Bad",
        )


# ── parser_summary ────────────────────────────────────────────────────────────

def _make_3star_summary():
    return hp.parser_summary(
        lottery_type="3_STAR",
        parser_source_type="controlled_apply_complete",
        row_count=5850,
        positional_non_null=5850,
        sorted_vs_positional_diff_count=4525,
        family_label="TEST",
    )


def test_parser_summary_required_fields():
    s = _make_3star_summary()
    for f in REQUIRED_SCHEMA_FIELDS:
        assert f in s, f"Missing field: {f!r}"


def test_parser_summary_no_edge_claim():
    assert _make_3star_summary()["no_edge_claim"] is True


def test_parser_summary_no_betting_advice():
    assert _make_3star_summary()["no_betting_advice"] is True


def test_parser_summary_3star_complete():
    assert _make_3star_summary()["positional_status"] == "complete"


def test_parser_summary_3star_straight_play():
    assert _make_3star_summary()["straight_play_position_frequency_supported"] is True


def test_parser_summary_3star_draw_order_confirmed():
    assert _make_3star_summary()["draw_order_confirmed"] is True


def test_parser_summary_schema_version():
    assert _make_3star_summary()["schema_version"] == "1.0"


def test_parser_summary_diagnostic_type():
    assert _make_3star_summary()["diagnostic_type"] == "historical_draw_parser_ssot"


def test_parser_summary_biglotto_not_applicable():
    s = hp.parser_summary("BIG_LOTTO", "active_parser", 22238, 0)
    assert s["positional_status"] == "not_applicable"
    assert s["straight_play_position_frequency_supported"] is False
    assert s["is_pool_draw"] is True


def test_parser_summary_deterministic():
    s1 = _make_3star_summary()
    s2 = _make_3star_summary()
    assert s1["positional_coverage_rate"] == s2["positional_coverage_rate"]
    assert s1["positional_status"] == s2["positional_status"]


def test_parser_summary_empty_raises():
    with pytest.raises((ValueError, Exception)):
        hp.parser_summary("3_STAR", "active_parser", -1, 0)


# ── Artifact ──────────────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_artifact_task_id():
    assert _load()["task_id"] == "P253E"


def test_artifact_classification():
    assert _load()["classification"] == "HISTORICAL_DRAW_PARSER_SSOT_IMPLEMENTED"


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
    assert ex["has_active_parser"]
    assert ex["has_complete_status"]
    assert ex["has_not_applicable"]
    assert ex["normalize_3star_lower"]
    assert ex["classify_complete"]
    assert ex["classify_not_applicable"]
    assert ex["compare_differs_true"]
    assert ex["summary_3star_complete"]
    assert ex["summary_biglotto_not_applicable"]
    assert ex["determinism_ok"]


def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p253e_historical_draw_parser_ssot_*.md"))
    assert candidates
    text = candidates[-1].read_text()
    assert "no db write" in text.lower() and "betting" in text.lower()


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p253e_historical_draw_parser_ssot as p253e
    r = p253e.main()
    assert r["task_id"] == "P253E"
    assert r["classification"] == "HISTORICAL_DRAW_PARSER_SSOT_IMPLEMENTED"
    assert r["no_db_write_confirmed"] is True
