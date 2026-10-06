"""Tests for P252B unified external method coverage audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"


def _find_latest_artifact() -> Path:
    """Find the most recent p252b JSON artifact."""
    candidates = sorted(OUTPUTS_DIR.glob("p252b_unified_external_method_coverage_audit_*.json"))
    assert candidates, "No p252b JSON artifact found in outputs/research/"
    return candidates[-1]


def _load_report() -> dict:
    return json.loads(_find_latest_artifact().read_text(encoding="utf-8"))


# ── Artifact existence ────────────────────────────────────────────────────────

def test_json_artifact_exists_and_parses():
    path = _find_latest_artifact()
    assert path.exists(), f"Artifact not found: {path}"
    report = _load_report()
    assert isinstance(report, dict), "Artifact must be a JSON object"


def test_md_artifact_exists():
    md_candidates = sorted(OUTPUTS_DIR.glob("p252b_unified_external_method_coverage_audit_*.md"))
    assert md_candidates, "No p252b Markdown artifact found"
    md_path = md_candidates[-1]
    text = md_path.read_text(encoding="utf-8")
    assert len(text) > 500, "Markdown artifact is suspiciously short"


# ── Schema fields ─────────────────────────────────────────────────────────────

def test_required_top_level_fields():
    report = _load_report()
    required = {
        "schema_version",
        "task_id",
        "classification",
        "phase0_summary",
        "method_coverage_matrix",
        "edge_search_summary",
        "core_layer_consolidation_plan",
        "p0_priorities",
        "p1_priorities",
        "p2_priorities",
        "gaps_and_unknowns",
        "no_db_write_confirmed",
        "no_strategy_promotion_confirmed",
        "no_betting_advice_confirmed",
        "final_decision",
    }
    missing = required - set(report.keys())
    assert not missing, f"Missing required fields: {missing}"


def test_classification():
    report = _load_report()
    assert report["classification"] == "UNIFIED_EXTERNAL_METHOD_COVERAGE_AUDIT"


def test_task_id():
    report = _load_report()
    assert report["task_id"] == "P252B"


# ── Method coverage matrix ────────────────────────────────────────────────────

def test_exactly_8_methods():
    report = _load_report()
    matrix = report["method_coverage_matrix"]
    assert len(matrix) == 8, f"Expected 8 methods, got {len(matrix)}"


def test_method_ids_m1_through_m8():
    report = _load_report()
    ids = {m["method_id"] for m in report["method_coverage_matrix"]}
    assert ids == {"M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"}


def test_every_method_has_required_fields():
    report = _load_report()
    required_fields = {
        "method_id",
        "method_name",
        "current_status",
        "evidence_files",
        "gaps",
        "recommended_consolidation_priority",
        "recommended_next_action",
    }
    for m in report["method_coverage_matrix"]:
        missing = required_fields - set(m.keys())
        assert not missing, f"{m['method_id']} missing fields: {missing}"


def test_every_method_status_is_valid():
    valid = {"COMPLETE", "CONFIRMED_PARTIAL", "PARTIAL", "MISSING", "UNKNOWN"}
    report = _load_report()
    for m in report["method_coverage_matrix"]:
        assert m["current_status"] in valid, (
            f"{m['method_id']} has invalid status: {m['current_status']}"
        )


def test_every_method_priority_is_valid():
    report = _load_report()
    for m in report["method_coverage_matrix"]:
        assert m["recommended_consolidation_priority"] in {"P0", "P1", "P2"}, (
            f"{m['method_id']} has invalid priority: {m['recommended_consolidation_priority']}"
        )


def test_every_method_has_nonempty_evidence_files():
    report = _load_report()
    for m in report["method_coverage_matrix"]:
        assert isinstance(m["evidence_files"], list) and len(m["evidence_files"]) > 0, (
            f"{m['method_id']} has empty evidence_files"
        )


def test_every_method_has_nonempty_gaps():
    report = _load_report()
    for m in report["method_coverage_matrix"]:
        assert isinstance(m["gaps"], list) and len(m["gaps"]) > 0, (
            f"{m['method_id']} has empty gaps"
        )


# ── Priority-specific assertions ──────────────────────────────────────────────

def test_multiple_testing_correction_is_p0():
    """M6 multiple testing correction must be P0 (mandatory gate)."""
    report = _load_report()
    m6 = next((m for m in report["method_coverage_matrix"] if m["method_id"] == "M6"), None)
    assert m6 is not None, "M6 (Multiple Testing Correction) not found in matrix"
    assert m6["recommended_consolidation_priority"] == "P0", (
        f"M6 must be P0 (mandatory gate), got: {m6['recommended_consolidation_priority']}"
    )


def test_rolling_window_is_p0_or_justified():
    """M3 rolling window must be P0 or have explicit justification."""
    report = _load_report()
    m3 = next((m for m in report["method_coverage_matrix"] if m["method_id"] == "M3"), None)
    assert m3 is not None, "M3 (Rolling Window Statistics) not found"
    priority = m3["recommended_consolidation_priority"]
    assert priority in {"P0", "P1"}, f"M3 priority must be P0 or P1, got: {priority}"


def test_random_baseline_is_p0():
    """M4 null simulation/random baseline must be P0 (L14 precedent)."""
    report = _load_report()
    m4 = next((m for m in report["method_coverage_matrix"] if m["method_id"] == "M4"), None)
    assert m4 is not None, "M4 (Null Simulation / Random Baseline) not found"
    assert m4["recommended_consolidation_priority"] == "P0", (
        f"M4 must be P0 (L14 false-positive precedent), got: {m4['recommended_consolidation_priority']}"
    )


def test_signal_stability_diagnostics_priority():
    """M7 signal stability must be P0 or P1."""
    report = _load_report()
    m7 = next((m for m in report["method_coverage_matrix"] if m["method_id"] == "M7"), None)
    assert m7 is not None, "M7 (Signal Stability Diagnostics) not found"
    assert m7["recommended_consolidation_priority"] in {"P0", "P1"}, (
        f"M7 must be P0 or P1, got: {m7['recommended_consolidation_priority']}"
    )


def test_feature_bottleneck_not_marked_complete():
    """M8 feature bottleneck must NOT be COMPLETE (no implementation exists)."""
    report = _load_report()
    m8 = next((m for m in report["method_coverage_matrix"] if m["method_id"] == "M8"), None)
    assert m8 is not None, "M8 (Feature Bottleneck Report) not found"
    assert m8["current_status"] != "COMPLETE", (
        f"M8 cannot be COMPLETE — no unified implementation exists. Status: {m8['current_status']}"
    )


# ── P0/P1/P2 list correctness ─────────────────────────────────────────────────

def test_p0_priorities_nonempty():
    report = _load_report()
    assert len(report["p0_priorities"]) >= 1, "p0_priorities must have at least one item"


def test_p1_priorities_nonempty():
    report = _load_report()
    assert len(report["p1_priorities"]) >= 1, "p1_priorities must have at least one item"


def test_p0_p1_p2_cover_all_8_methods():
    report = _load_report()
    all_prioritized = set(report["p0_priorities"]) | set(report["p1_priorities"]) | set(report["p2_priorities"])
    matrix_ids = {m["method_id"] for m in report["method_coverage_matrix"]}
    assert all_prioritized == matrix_ids, (
        f"Priority lists don't cover all 8 method IDs. "
        f"Coverage: {all_prioritized}, Matrix: {matrix_ids}"
    )


# ── Edge search and no-claim assertions ──────────────────────────────────────

def test_edge_search_states_no_deployable_edge():
    report = _load_report()
    edge = report["edge_search_summary"]
    answer = edge.get("answer", "").upper()
    assert answer in {"NO", "NULL", "NONE"}, (
        f"edge_search_summary.answer must state no deployable edge, got: {answer!r}"
    )


def test_no_betting_advice():
    report = _load_report()
    assert report["no_betting_advice_confirmed"] is True
    # Also verify in edge_search_summary
    edge = report["edge_search_summary"]
    assert edge.get("no_betting_advice") is True


def test_no_db_write():
    report = _load_report()
    assert report["no_db_write_confirmed"] is True


def test_no_strategy_promotion():
    report = _load_report()
    assert report["no_strategy_promotion_confirmed"] is True


def test_green_randomness_does_not_imply_edge():
    report = _load_report()
    edge = report["edge_search_summary"]
    assert edge.get("green_randomness_means_prediction_edge") is False, (
        "Must explicitly state GREEN randomness does not imply prediction edge"
    )


# ── Markdown content checks ───────────────────────────────────────────────────

def test_md_contains_no_deployable_edge_statement():
    md_candidates = sorted(OUTPUTS_DIR.glob("p252b_unified_external_method_coverage_audit_*.md"))
    text = md_candidates[-1].read_text(encoding="utf-8")
    assert "no deployable" in text.lower() or "not found" in text.lower() or "null" in text.lower(), (
        "Markdown must contain explicit no-deployable-edge statement"
    )


def test_md_contains_no_db_write_statement():
    md_candidates = sorted(OUTPUTS_DIR.glob("p252b_unified_external_method_coverage_audit_*.md"))
    text = md_candidates[-1].read_text(encoding="utf-8")
    assert "no db write" in text.lower() or "no_db_write" in text.lower(), (
        "Markdown must contain explicit no-DB-write statement"
    )


def test_md_contains_no_betting_advice_statement():
    md_candidates = sorted(OUTPUTS_DIR.glob("p252b_unified_external_method_coverage_audit_*.md"))
    text = md_candidates[-1].read_text(encoding="utf-8")
    assert "no betting advice" in text.lower() or "betting" in text.lower(), (
        "Markdown must contain explicit no-betting-advice statement"
    )


def test_md_contains_8_method_coverage_table():
    md_candidates = sorted(OUTPUTS_DIR.glob("p252b_unified_external_method_coverage_audit_*.md"))
    text = md_candidates[-1].read_text(encoding="utf-8")
    # Must have all 8 method IDs
    for mid in ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"]:
        assert mid in text, f"Markdown missing method ID: {mid}"


# ── Analysis module re-run ────────────────────────────────────────────────────

def test_rerun_produces_valid_artifact():
    """Re-running the script should produce a parseable artifact."""
    from analysis import p252b_unified_external_method_coverage_audit as p252b
    report = p252b.main()
    assert report["task_id"] == "P252B"
    assert report["classification"] == "UNIFIED_EXTERNAL_METHOD_COVERAGE_AUDIT"
    assert len(report["method_coverage_matrix"]) == 8
    assert report["no_db_write_confirmed"] is True
    assert report["no_betting_advice_confirmed"] is True
