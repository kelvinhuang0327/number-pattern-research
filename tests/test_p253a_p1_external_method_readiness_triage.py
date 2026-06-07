"""Tests for P253A — P1 External Method Readiness Triage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
EXPECTED_METHODS = {"M1", "M7", "M8"}
VALID_READINESS = {"READY_FOR_NEXT_TASK", "NEEDS_READONLY_INVENTORY", "BLOCKED_BY_DATA_SCHEMA", "DEFER"}


def _find() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p253a_p1_external_method_readiness_triage_*.json"))
    assert candidates, "No p253a JSON artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find().read_text(encoding="utf-8"))


# ── Artifact ──────────────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_task_id():
    assert _load()["task_id"] == "P253A"


def test_classification():
    assert _load()["classification"] == "P1_EXTERNAL_METHOD_READINESS_TRIAGE_COMPLETE"


# ── All three P1 candidates present ──────────────────────────────────────────

def test_all_three_candidates_present():
    ids = {m["method_id"] for m in _load()["p1_candidate_matrix"]}
    assert EXPECTED_METHODS <= ids


def test_each_candidate_has_required_fields():
    for m in _load()["p1_candidate_matrix"]:
        for field in ["method_id", "method_name", "readiness_status", "rationale",
                       "implementation_risk", "evidence"]:
            assert field in m, f"{m.get('method_id')} missing {field!r}"


def test_each_candidate_has_valid_readiness():
    for m in _load()["p1_candidate_matrix"]:
        assert m["readiness_status"] in VALID_READINESS, (
            f"{m['method_id']} has invalid readiness: {m['readiness_status']!r}"
        )


def test_each_candidate_has_nonempty_rationale():
    for m in _load()["p1_candidate_matrix"]:
        assert len(m["rationale"]) > 20, f"{m['method_id']} has empty rationale"


# ── Readiness decision ────────────────────────────────────────────────────────

def test_readiness_decision_exists():
    rd = _load()["readiness_decision"]
    assert isinstance(rd, dict)
    assert "winner" in rd
    assert "rationale" in rd


def test_winner_is_valid_method():
    winner = _load()["readiness_decision"]["winner"]
    assert winner in EXPECTED_METHODS


# ── Exactly one recommended next task or HOLD ─────────────────────────────────

def test_recommended_next_task_exists():
    rnt = _load()["recommended_next_task"]
    assert isinstance(rnt, dict)
    # Must have either a task proposal or a HOLD indicator
    has_task = "task_id_proposal" in rnt or "title" in rnt
    is_hold = rnt.get("task_id_proposal") == "HOLD" or "hold" in str(rnt).lower()
    assert has_task or is_hold


def test_recommended_next_task_has_scope():
    rnt = _load()["recommended_next_task"]
    # Should have scope or a rationale for HOLD
    assert "scope" in rnt or "rationale" in rnt or "hold" in str(rnt).lower()


def test_rejected_or_deferred_exists():
    rd = _load()["rejected_or_deferred_options"]
    assert isinstance(rd, list) and len(rd) > 0


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

def test_final_decision_no_predictive_edge():
    fd = _load()["final_decision"].lower()
    # Must not claim edge without negation
    if "prediction edge" in fd or "predictive edge" in fd:
        assert "no " in fd or "null" in fd or "not" in fd


def test_final_decision_mentions_waiting():
    fd = _load()["final_decision"]
    assert "WAITING_FOR_USER_AUTHORIZATION" in fd or "authorization" in fd.lower()


# ── P252I dependency verified ─────────────────────────────────────────────────

def test_p252i_dependency_found():
    dep = _load()["p252i_dependency_verified"]
    assert dep["found"] is True


def test_p252i_all_modules_ok():
    dep = _load()["p252i_dependency_verified"]
    assert dep.get("all_modules_ok") is True


# ── Markdown ──────────────────────────────────────────────────────────────────

def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p253a_p1_external_method_readiness_triage_*.md"))
    assert candidates
    text = candidates[-1].read_text()
    assert "no db write" in text.lower()
    assert "M7" in text and "M1" in text and "M8" in text


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p253a_p1_external_method_readiness_triage as p253a
    r = p253a.main()
    assert r["task_id"] == "P253A"
    assert r["classification"] == "P1_EXTERNAL_METHOD_READINESS_TRIAGE_COMPLETE"
    assert r["no_db_write_confirmed"] is True
    assert {m["method_id"] for m in r["p1_candidate_matrix"]} == {"M1", "M7", "M8"}
