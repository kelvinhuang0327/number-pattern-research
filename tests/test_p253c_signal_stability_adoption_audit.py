"""Tests for P253C — Signal Stability SSOT Adoption Audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"

REQUIRED_CLASSIFICATIONS = {
    "ALREADY_USING_SSOT",
    "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
    "SEPARATE_PRODUCTION_DOMAIN",
    "ARCHIVED_OR_EXPLORATORY_DEFER",
}

REQUIRED_JSON_KEYS = [
    "schema_version", "task_id", "classification", "phase0_summary",
    "p253b_dependency_verified", "stability_module_verified",
    "repository_scan_summary", "adoption_matrix",
    "active_duplicate_logic", "historical_artifacts_do_not_edit",
    "archived_or_deferred_logic", "recommended_next_task",
    "no_db_write_confirmed", "no_registry_mutation_confirmed",
    "no_strategy_promotion_confirmed", "no_betting_advice_confirmed",
    "final_decision",
]

MUTATING_WORDS = ["betting advice", "deployable edge", "strategy promotion", "prediction edge"]


def _find() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p253c_signal_stability_adoption_audit_*.json"))
    assert candidates, "No p253c artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find().read_text(encoding="utf-8"))


# ── Artifact structure ────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_artifact_task_id():
    assert _load()["task_id"] == "P253C"


def test_artifact_classification():
    assert _load()["classification"] == "SIGNAL_STABILITY_ADOPTION_AUDIT_COMPLETE"


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


# ── P253B dependency ──────────────────────────────────────────────────────────

def test_p253b_dependency_verified():
    dep = _load()["p253b_dependency_verified"]
    assert dep["module_exists"] is True
    assert dep["module_pure_safe"] is True
    assert dep["artifact_classification_match"] is True
    assert dep["test_exists"] is True


def test_stability_module_verified_exists():
    smv = _load()["stability_module_verified"]
    assert smv["exists"] is True
    assert smv["pure_safe"] is True


def test_stability_module_has_constants():
    consts = _load()["stability_module_verified"]["constants"]
    assert "STABILITY_DIMENSIONS" in consts
    assert "STABILITY_STATUS" in consts
    assert "DEFAULT_STABILITY_THRESHOLDS" in consts


def test_stability_module_has_functions():
    fns = _load()["stability_module_verified"]["functions"]
    for fn in ["classify_stability", "block_stability", "subset_exclusion_stability", "stability_summary"]:
        assert fn in fns, f"Missing function: {fn!r}"


# ── Adoption matrix ───────────────────────────────────────────────────────────

def test_adoption_matrix_non_empty():
    matrix = _load()["adoption_matrix"]
    assert isinstance(matrix, list) and len(matrix) > 0


def test_adoption_matrix_each_has_classification():
    for entry in _load()["adoption_matrix"]:
        assert "classification" in entry, f"Missing classification in {entry.get('path')}"
        assert entry["classification"] in (
            "ALREADY_USING_SSOT",
            "ACTIVE_DUPLICATE_NEEDS_MIGRATION",
            "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
            "ARCHIVED_OR_EXPLORATORY_DEFER",
            "SEPARATE_PRODUCTION_DOMAIN",
            "UNKNOWN_NEEDS_SCOPE",
        ), f"Unknown classification: {entry['classification']!r}"


def test_adoption_matrix_each_has_recommended_action():
    for entry in _load()["adoption_matrix"]:
        assert "recommended_action" in entry, f"Missing recommended_action in {entry.get('path')}"
        assert isinstance(entry["recommended_action"], str) and len(entry["recommended_action"]) > 0


def test_adoption_matrix_has_ssot_entry():
    paths = [e["path"] for e in _load()["adoption_matrix"]]
    assert any("stability_diagnostics" in p for p in paths), "SSOT module not in adoption matrix"


def test_adoption_matrix_classifications_cover_expected():
    found = {e["classification"] for e in _load()["adoption_matrix"]}
    for expected in REQUIRED_CLASSIFICATIONS:
        assert expected in found, f"Classification {expected!r} not found in matrix"


# ── Historical artifacts ──────────────────────────────────────────────────────

def test_historical_artifacts_list_non_empty():
    hist = _load()["historical_artifacts_do_not_edit"]
    assert isinstance(hist, list) and len(hist) > 0


def test_historical_artifacts_not_recommended_for_mutation():
    data = _load()
    hist_paths = set(data["historical_artifacts_do_not_edit"])
    for entry in data["adoption_matrix"]:
        if entry["path"] in hist_paths:
            action = entry["recommended_action"].upper()
            # Must say FREEZE or DO NOT EDIT, not MIGRATE
            assert "MIGRATE" not in action, (
                f"Historical artifact {entry['path']!r} has MIGRATE in recommended_action"
            )


def test_historical_p227c_is_frozen():
    hist = _load()["historical_artifacts_do_not_edit"]
    assert any("p227c" in p for p in hist), "p227c not in frozen list"


def test_historical_p230b1_is_frozen():
    hist = _load()["historical_artifacts_do_not_edit"]
    assert any("p230b1" in p for p in hist)


def test_historical_p231b_is_frozen():
    hist = _load()["historical_artifacts_do_not_edit"]
    assert any("p231b" in p for p in hist)


def test_historical_p246k_is_frozen():
    hist = _load()["historical_artifacts_do_not_edit"]
    assert any("p246k" in p for p in hist)


# ── Active duplicates ─────────────────────────────────────────────────────────

def test_active_duplicate_count_is_zero():
    dup = _load()["active_duplicate_logic"]
    assert dup["count"] == 0, (
        f"Expected 0 active duplicates requiring migration, got {dup['count']}"
    )


def test_active_duplicate_findings_empty():
    assert _load()["active_duplicate_logic"]["findings"] == []


# ── No edge claim ─────────────────────────────────────────────────────────────

def test_final_decision_no_edge_claim():
    fd = _load()["final_decision"].lower()
    for phrase in ["deployable edge", "prediction edge claim", "betting advice is provided"]:
        assert phrase not in fd, f"final_decision must not claim edge: {phrase!r}"


def test_final_decision_references_no_edge():
    fd = _load()["final_decision"].lower()
    assert "no deployable prediction edge" in fd or "no betting advice" in fd, (
        "final_decision should reference no-edge or no-betting-advice"
    )


def test_recommended_next_no_strategy_promotion():
    rec = json.dumps(_load()["recommended_next_task"]).lower()
    assert "strategy promotion" not in rec
    assert "betting advice" not in rec


# ── MD artifact ───────────────────────────────────────────────────────────────

def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p253c_signal_stability_adoption_audit_*.md"))
    assert candidates, "No p253c MD artifact"


def test_md_contains_required_sections():
    candidates = sorted(OUTPUTS_DIR.glob("p253c_signal_stability_adoption_audit_*.md"))
    text = candidates[-1].read_text(encoding="utf-8").lower()
    for phrase in ["no db write", "no betting advice", "ssot", "historical"]:
        assert phrase in text, f"MD missing phrase: {phrase!r}"


# ── Module isolation (belt-and-suspenders) ────────────────────────────────────

def test_stability_diagnostics_no_forbidden_imports():
    src = (REPO_ROOT / "lottery_api" / "utils" / "stability_diagnostics.py").read_text()
    import_lines = [l.strip() for l in src.splitlines()
                    if l.strip().startswith(("import ", "from ")) and not l.strip().startswith("#")]
    text = "\n".join(import_lines)
    for mod in ["sqlite3", "database", "registry", "routes", "numpy", "scipy"]:
        assert mod not in text, f"stability_diagnostics must not import {mod!r}"


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p253c_signal_stability_adoption_audit as p253c
    r = p253c.main()
    assert r["task_id"] == "P253C"
    assert r["classification"] == "SIGNAL_STABILITY_ADOPTION_AUDIT_COMPLETE"
    assert r["no_db_write_confirmed"] is True
    assert r["active_duplicate_logic"]["count"] == 0
