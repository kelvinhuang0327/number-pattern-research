"""Tests for P253F — Historical Draw Parser SSOT Adoption Audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"

REQUIRED_JSON_KEYS = [
    "schema_version", "task_id", "classification", "phase0_summary",
    "p253e_dependency_verified", "parser_module_verified",
    "repository_scan_summary", "adoption_matrix",
    "active_duplicate_logic", "controlled_apply_do_not_edit",
    "historical_import_scripts_defer", "archived_or_deferred_logic",
    "recommended_next_task",
    "no_db_write_confirmed", "no_registry_mutation_confirmed",
    "no_strategy_promotion_confirmed", "no_betting_advice_confirmed",
    "final_decision",
]

VALID_CLASSIFICATIONS = {
    "ALREADY_USING_SSOT",
    "ACTIVE_DUPLICATE_NEEDS_MIGRATION",
    "SEPARATE_PRODUCTION_DOMAIN",
    "CONTROLLED_APPLY_DO_NOT_EDIT",
    "HISTORICAL_IMPORT_SCRIPT_DEFER",
    "ARCHIVED_OR_EXPLORATORY_DEFER",
    "UNKNOWN_NEEDS_SCOPE",
}


def _find() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p253f_historical_draw_parser_adoption_audit_*.json"))
    assert candidates, "No p253f artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find().read_text(encoding="utf-8"))


# ── Artifact structure ────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_artifact_task_id():
    assert _load()["task_id"] == "P253F"


def test_artifact_classification():
    assert _load()["classification"] == "HISTORICAL_DRAW_PARSER_ADOPTION_AUDIT_COMPLETE"


def test_artifact_required_keys():
    data = _load()
    for key in REQUIRED_JSON_KEYS:
        assert key in data, f"Missing key: {key!r}"


# ── Compliance flags ──────────────────────────────────────────────────────────

def test_no_db_write():
    assert _load()["no_db_write_confirmed"] is True


def test_no_registry_mutation():
    assert _load()["no_registry_mutation_confirmed"] is True


def test_no_strategy_promotion():
    assert _load()["no_strategy_promotion_confirmed"] is True


def test_no_betting_advice():
    assert _load()["no_betting_advice_confirmed"] is True


# ── P253E dependency ──────────────────────────────────────────────────────────

def test_p253e_dependency_verified():
    dep = _load()["p253e_dependency_verified"]
    assert dep["module_exists"] is True
    assert dep["module_pure_safe"] is True
    assert dep["artifact_classification_match"] is True
    assert dep["test_exists"] is True


def test_parser_module_verified_exists():
    pmv = _load()["parser_module_verified"]
    assert pmv["exists"] is True
    assert pmv["pure_safe"] is True


def test_parser_module_has_constants():
    consts = _load()["parser_module_verified"]["constants"]
    for c in ["PARSER_SOURCE_TYPES", "POSITIONAL_STATUS", "SORTING_SEMANTICS"]:
        assert c in consts, f"Missing constant: {c!r}"


def test_parser_module_has_functions():
    fns = _load()["parser_module_verified"]["functions"]
    for fn in ["normalize_lottery_type", "validate_numbers_payload",
               "compare_sorted_vs_positional", "classify_positional_coverage",
               "parser_summary"]:
        assert fn in fns, f"Missing function: {fn!r}"


# ── Adoption matrix ───────────────────────────────────────────────────────────

def test_adoption_matrix_non_empty():
    matrix = _load()["adoption_matrix"]
    assert isinstance(matrix, list) and len(matrix) > 0


def test_adoption_matrix_each_has_classification():
    for entry in _load()["adoption_matrix"]:
        assert "classification" in entry, f"Missing classification in {entry.get('path')}"
        assert entry["classification"] in VALID_CLASSIFICATIONS, (
            f"Unknown classification: {entry['classification']!r}"
        )


def test_adoption_matrix_each_has_recommended_action():
    for entry in _load()["adoption_matrix"]:
        assert "recommended_action" in entry
        assert isinstance(entry["recommended_action"], str) and len(entry["recommended_action"]) > 0


def test_adoption_matrix_has_ssot_entry():
    paths = [e["path"] for e in _load()["adoption_matrix"]]
    assert any("historical_draw_parser" in p for p in paths)


def test_adoption_matrix_has_already_using_ssot():
    clss = [e["classification"] for e in _load()["adoption_matrix"]]
    assert "ALREADY_USING_SSOT" in clss


# ── Active duplicates ─────────────────────────────────────────────────────────

def test_active_duplicate_count_is_zero():
    dup = _load()["active_duplicate_logic"]
    assert dup["count"] == 0


def test_active_duplicate_findings_empty():
    assert _load()["active_duplicate_logic"]["findings"] == []


# ── Controlled-apply — do not edit ───────────────────────────────────────────

def test_controlled_apply_list_non_empty():
    controlled = _load()["controlled_apply_do_not_edit"]
    assert isinstance(controlled, list) and len(controlled) > 0


def test_controlled_apply_not_recommended_for_mutation():
    data = _load()
    controlled_paths = set(data["controlled_apply_do_not_edit"])
    for entry in data["adoption_matrix"]:
        if entry["path"] in controlled_paths:
            action = entry["recommended_action"].upper()
            assert "MIGRATE" not in action, (
                f"Controlled-apply {entry['path']!r} should not have MIGRATE action"
            )


def test_controlled_apply_has_p213h():
    controlled = _load()["controlled_apply_do_not_edit"]
    assert any("p213h" in p for p in controlled)


def test_controlled_apply_has_p213l():
    controlled = _load()["controlled_apply_do_not_edit"]
    assert any("p213l" in p for p in controlled)


def test_controlled_apply_has_p213i():
    controlled = _load()["controlled_apply_do_not_edit"]
    assert any("p213i" in p for p in controlled)


# ── Historical import scripts ─────────────────────────────────────────────────

def test_historical_import_scripts_list():
    hist = _load()["historical_import_scripts_defer"]
    assert isinstance(hist, list)


def test_historical_import_scripts_not_auto_modified():
    data = _load()
    hist_paths = {e["path"] for e in data["historical_import_scripts_defer"]}
    for entry in data["adoption_matrix"]:
        if entry["path"] in hist_paths:
            action = entry["recommended_action"].upper()
            assert "MIGRATE" not in action and "AUTO" not in action, (
                f"Historical import {entry['path']!r} should not be auto-modified"
            )


# ── No edge claim ─────────────────────────────────────────────────────────────

def test_final_decision_no_edge_claim():
    fd = _load()["final_decision"].lower()
    assert "no deployable prediction edge" in fd or "no betting advice" in fd


def test_recommended_next_no_strategy_promotion():
    rec = json.dumps(_load()["recommended_next_task"]).lower()
    assert "strategy promotion" not in rec
    assert "betting advice" not in rec


# ── MD artifact ───────────────────────────────────────────────────────────────

def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p253f_historical_draw_parser_adoption_audit_*.md"))
    assert candidates, "No p253f MD artifact"


def test_md_contains_required_sections():
    candidates = sorted(OUTPUTS_DIR.glob("p253f_historical_draw_parser_adoption_audit_*.md"))
    text = candidates[-1].read_text(encoding="utf-8").lower()
    for phrase in ["no db write", "no betting advice", "ssot", "controlled", "historical"]:
        assert phrase in text, f"MD missing phrase: {phrase!r}"


# ── Module isolation (belt-and-suspenders) ────────────────────────────────────

def test_historical_draw_parser_no_forbidden_imports():
    src = (REPO_ROOT / "lottery_api" / "utils" / "historical_draw_parser.py").read_text()
    import_lines = [l.strip() for l in src.splitlines()
                    if l.strip().startswith(("import ", "from ")) and not l.strip().startswith("#")]
    text = "\n".join(import_lines)
    for mod in ["sqlite3", "database", "registry", "routes", "numpy", "scipy"]:
        assert mod not in text, f"historical_draw_parser must not import {mod!r}"


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p253f_historical_draw_parser_adoption_audit as p253f
    r = p253f.main()
    assert r["task_id"] == "P253F"
    assert r["classification"] == "HISTORICAL_DRAW_PARSER_ADOPTION_AUDIT_COMPLETE"
    assert r["no_db_write_confirmed"] is True
    assert r["active_duplicate_logic"]["count"] == 0
