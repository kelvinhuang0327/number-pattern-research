"""Tests for P252G — P0 External Method SSOT Adoption Audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"

VALID_CLASSIFICATIONS = {
    "ALREADY_USING_SSOT",
    "ACTIVE_DUPLICATE_NEEDS_MIGRATION",
    "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
    "ARCHIVED_OR_EXPLORATORY_DEFER",
    "UNKNOWN_NEEDS_SCOPE",
}


def _find() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p252g_p0_external_method_ssot_adoption_audit_*.json"))
    assert candidates, "No p252g JSON artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find().read_text(encoding="utf-8"))


# ── Artifact existence ────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p252g_p0_external_method_ssot_adoption_audit_*.md"))
    assert candidates
    text = candidates[-1].read_text()
    assert len(text) > 300


# ── Schema fields ─────────────────────────────────────────────────────────────

def test_required_fields():
    report = _load()
    for field in [
        "schema_version", "task_id", "classification", "phase0_summary",
        "ssot_modules_verified", "ssot_artifacts_verified", "repository_scan_summary",
        "adoption_matrix", "active_duplicate_logic", "archived_or_deferred_logic",
        "historical_artifacts_do_not_edit", "recommended_next_task",
        "no_db_write_confirmed", "no_registry_mutation_confirmed",
        "no_strategy_promotion_confirmed", "no_betting_advice_confirmed",
        "final_decision",
    ]:
        assert field in report, f"Missing field: {field!r}"


def test_task_id():
    assert _load()["task_id"] == "P252G"


def test_classification():
    assert _load()["classification"] == "P0_EXTERNAL_METHOD_SSOT_ADOPTION_AUDIT"


# ── SSOT modules verified (all four P252C-F) ─────────────────────────────────

def test_all_four_ssot_modules_listed():
    modules = _load()["ssot_modules_verified"]
    tasks = {m["task"] for m in modules}
    assert {"P252C", "P252D", "P252E", "P252F"} <= tasks


def test_all_ssot_modules_exist():
    for m in _load()["ssot_modules_verified"]:
        assert m["module_exists"] is True, f"{m['task']} module not found"


def test_all_ssot_modules_safe():
    for m in _load()["ssot_modules_verified"]:
        assert m["module_safe_no_db"] is True, f"{m['task']} has forbidden imports"


def test_all_ssot_classifications_match():
    for m in _load()["ssot_modules_verified"]:
        assert m["classification_match"] is True, (
            f"{m['task']} classification mismatch: "
            f"expected={m['expected_classification']}, got={m['artifact_classification']}"
        )


def test_expected_classifications():
    expected = {
        "P252C": "BASELINE_CALCULATOR_SSOT_IMPLEMENTED",
        "P252D": "CORRECTION_GATE_SSOT_IMPLEMENTED",
        "P252E": "PERMUTATION_TEST_SSOT_IMPLEMENTED",
        "P252F": "ROLLING_WINDOW_STATISTICS_SSOT_IMPLEMENTED",
    }
    for m in _load()["ssot_modules_verified"]:
        if m["task"] in expected:
            assert m["artifact_classification"] == expected[m["task"]], (
                f"{m['task']}: got {m['artifact_classification']!r}"
            )


# ── Adoption matrix ───────────────────────────────────────────────────────────

def test_adoption_matrix_nonempty():
    assert len(_load()["adoption_matrix"]) > 0


def test_every_finding_has_required_fields():
    for finding in _load()["adoption_matrix"]:
        for field in ["file", "domain", "classification", "recommended_action"]:
            assert field in finding, f"Finding missing {field!r}: {finding.get('file')}"


def test_every_classification_is_valid():
    for finding in _load()["adoption_matrix"]:
        cls = finding["classification"]
        assert cls in VALID_CLASSIFICATIONS, (
            f"Invalid classification {cls!r} in {finding['file']}"
        )


def test_repository_scan_summary_fields():
    summary = _load()["repository_scan_summary"]
    for field in ["total_findings", "already_using_ssot",
                   "active_duplicate_needs_migration",
                   "historical_artifact_do_not_edit",
                   "archived_or_exploratory_defer"]:
        assert field in summary, f"Missing summary field: {field!r}"


# ── Active duplicate logic ────────────────────────────────────────────────────

def test_active_duplicates_nonempty():
    """Some active duplicate logic must be found — SSOT adoption is not complete."""
    dup = _load()["active_duplicate_logic"]
    assert len(dup) > 0, "Expected at least one active duplicate — SSOT adoption is not yet complete"


def test_active_duplicates_not_silently_complete():
    """No active duplicate should claim it's done without a recommended action."""
    for dup in _load()["active_duplicate_logic"]:
        assert dup["classification"] == "ACTIVE_DUPLICATE_NEEDS_MIGRATION"
        assert len(dup.get("recommended_action", "")) > 5, (
            f"Active duplicate {dup['file']} has no recommended action"
        )


def test_rsm_rolling_strategy_monitor_in_active_duplicates():
    """The production RSM must be flagged for rolling window migration."""
    files = [d["file"] for d in _load()["active_duplicate_logic"]]
    assert any("rolling_strategy_monitor" in f for f in files), (
        "RSM must be in active_duplicate_logic (uses own WINDOWS dict)"
    )


# ── Historical artifacts ──────────────────────────────────────────────────────

def test_historical_artifacts_not_recommended_for_mutation():
    for artifact in _load()["historical_artifacts_do_not_edit"]:
        action = artifact.get("recommended_action", "").lower()
        assert "modify" not in action and "rewrite" not in action and "migrate body" not in action, (
            f"Historical artifact {artifact['file']} incorrectly recommended for mutation"
        )


# ── No-claim flags ────────────────────────────────────────────────────────────

def test_no_db_write():
    assert _load()["no_db_write_confirmed"] is True


def test_no_registry_mutation():
    assert _load()["no_registry_mutation_confirmed"] is True


def test_no_strategy_promotion():
    assert _load()["no_strategy_promotion_confirmed"] is True


def test_no_betting_advice():
    assert _load()["no_betting_advice_confirmed"] is True


# ── Final decision no overclaim ───────────────────────────────────────────────

def test_final_decision_no_predictive_edge_claim():
    fd = _load()["final_decision"].lower()
    assert "prediction edge" not in fd or "no" in fd or "null" in fd or "not" in fd, (
        "final_decision must not claim a deployable prediction edge"
    )


def test_final_decision_mentions_next_task():
    fd = _load()["final_decision"]
    assert "P252H" in fd or "next" in fd.lower()


# ── Recommended next task ─────────────────────────────────────────────────────

def test_recommended_next_task_exists():
    rnt = _load()["recommended_next_task"]
    assert isinstance(rnt, dict)
    assert "task_id" in rnt
    assert "scope" in rnt
    assert "non_scope" in rnt


def test_recommended_next_task_not_db_write():
    rnt = _load()["recommended_next_task"]
    non_scope = " ".join(rnt.get("non_scope", []))
    assert "DB" in non_scope or "db" in non_scope.lower() or "database" in non_scope.lower(), (
        "recommended non_scope must explicitly exclude DB write"
    )


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p252g_p0_external_method_ssot_adoption_audit as p252g
    r = p252g.main()
    assert r["task_id"] == "P252G"
    assert r["classification"] == "P0_EXTERNAL_METHOD_SSOT_ADOPTION_AUDIT"
    assert r["no_db_write_confirmed"] is True
    assert r["all_ssot_modules_ok"] is True
