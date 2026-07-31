"""Tests for P252I — P0 External Method SSOT Governance Closure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
EXPECTED_ARC_TASKS = {"P252B", "P252C", "P252D", "P252E", "P252F", "P252G", "P252H"}
EXPECTED_P0_METHODS = {"M3", "M4", "M5", "M6"}


def _find() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p252i_p0_ssot_governance_closure_*.json"))
    assert candidates, "No p252i JSON artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find().read_text(encoding="utf-8"))


# ── Artifact ──────────────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_task_id():
    assert _load()["task_id"] == "P252I"


def test_classification():
    assert _load()["classification"] == "P0_EXTERNAL_METHOD_SSOT_GOVERNANCE_CLOSURE_COMPLETE"


# ── All P252B-H tasks listed ──────────────────────────────────────────────────

def test_all_arc_tasks_listed():
    report = _load()
    found = {a["task_id"] for a in report["verified_artifacts"]}
    assert EXPECTED_ARC_TASKS <= found, f"Missing: {EXPECTED_ARC_TASKS - found}"


def test_all_arc_artifacts_found():
    for a in _load()["verified_artifacts"]:
        assert a["artifact_found"] is True, f"{a['task_id']} artifact not found"


def test_all_arc_classifications_match():
    for a in _load()["verified_artifacts"]:
        assert a["classification_match"] is True, (
            f"{a['task_id']} classification mismatch"
        )


# ── All four P0 SSOT modules listed ──────────────────────────────────────────

def test_all_p0_modules_listed():
    report = _load()
    found = {m["method_id"] for m in report["verified_modules"]}
    assert EXPECTED_P0_METHODS <= found


def test_all_p0_modules_exist():
    for m in _load()["verified_modules"]:
        assert m["exists"] is True, f"{m['method_id']} module not found"


def test_all_p0_modules_safe():
    for m in _load()["verified_modules"]:
        assert m["safe_no_db"] is True, f"{m['method_id']} has forbidden imports"


# ── completed_p0_methods covers M3/M4/M5/M6 ──────────────────────────────────

def test_completed_p0_methods_covers_all():
    ids = {m["method_id"] for m in _load()["completed_p0_methods"]}
    assert EXPECTED_P0_METHODS <= ids


# ── P252H migration confirmed ─────────────────────────────────────────────────

def test_p252h_migration_found():
    p252h = _load()["p252h_migration_confirmed"]
    assert p252h["found"] is True


def test_p252h_all_6_findings():
    p252h = _load()["p252h_migration_confirmed"]
    assert p252h["all_6_findings_addressed"] is True


def test_p252h_no_behavior_changes():
    p252h = _load()["p252h_migration_confirmed"]
    assert p252h["no_behavior_changes"] is True


# ── Remaining deferred items ──────────────────────────────────────────────────

def test_remaining_deferred_exists_and_nonempty():
    rd = _load()["remaining_deferred_items"]
    assert isinstance(rd, list) and len(rd) > 0


def test_deferred_items_have_required_fields():
    for item in _load()["remaining_deferred_items"]:
        for field in ["item", "category", "rationale", "trigger"]:
            assert field in item, f"Deferred item missing {field!r}"


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

def test_final_decision_no_edge_claim():
    fd = _load()["final_decision"].lower()
    # Must not claim edge OR must negate it
    assert "no deployable" in fd or "null" in fd or "rejected" in fd or "no" in fd


def test_final_decision_mentions_waiting():
    fd = _load()["final_decision"]
    assert "WAITING_FOR_USER_AUTHORIZATION" in fd or "HOLD" in fd or "WAITING" in fd


# ── Governance files updated ──────────────────────────────────────────────────

def test_governance_updates_recorded():
    gu = _load()["governance_updates"]
    assert isinstance(gu, dict)
    assert "active_task_updated" in gu
    assert "current_state_updated" in gu


def test_active_task_contains_p252i():
    path = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        assert "P252I" in text or "P252B-H" in text, (
            "active_task.md should contain P252I closure marker"
        )


def test_current_state_contains_p252i():
    path = REPO_ROOT / "00-Plan" / "roadmap" / "agent_bootstrap" / "CURRENT_STATE.md"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        assert "P252I" in text or "P252B-H" in text, (
            "CURRENT_STATE.md should contain P252I closure marker"
        )


# ── Markdown ──────────────────────────────────────────────────────────────────

def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p252i_p0_ssot_governance_closure_*.md"))
    assert candidates
    text = candidates[-1].read_text()
    assert "no db write" in text.lower()
    assert "betting" in text.lower()
    assert "P252B" in text and "P252H" in text


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p252i_p0_ssot_governance_closure as p252i
    r = p252i.main()
    assert r["task_id"] == "P252I"
    assert r["classification"] == "P0_EXTERNAL_METHOD_SSOT_GOVERNANCE_CLOSURE_COMPLETE"
    assert r["no_db_write_confirmed"] is True
    assert r["all_artifacts_ok"] is True
    assert r["all_modules_ok"] is True
