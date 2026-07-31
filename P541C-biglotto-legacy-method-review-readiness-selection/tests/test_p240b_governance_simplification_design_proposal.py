"""Targeted tests for P240B governance simplification design proposal artifacts."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MD_PATH = ROOT / "outputs/research/p240b_governance_simplification_design_proposal_20260604.md"
JSON_PATH = ROOT / "outputs/research/p240b_governance_simplification_design_proposal_20260604.json"


def _load_json():
    with open(JSON_PATH) as f:
        return json.load(f)


def _load_md():
    return MD_PATH.read_text()


def test_json_exists_and_parses():
    assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"
    d = _load_json()
    assert isinstance(d, dict)


def test_markdown_exists():
    assert MD_PATH.exists(), f"Markdown artifact missing: {MD_PATH}"
    assert MD_PATH.stat().st_size > 0


def test_json_no_db_write():
    d = _load_json()
    assert d["db_write_performed"] is False
    assert d["registry_write_performed"] is False


def test_json_no_production_monitoring_strategy():
    d = _load_json()
    assert d["production_change_authorized"] is False
    assert d["monitoring_job_authorized"] is False
    assert d["strategy_authorized"] is False
    assert d["betting_advice"] is False


def test_json_no_adoption_authorized():
    d = _load_json()
    assert d["adoption_authorized"] is False
    assert d["proposal_only"] is True


def test_json_p238b_yellow_observation_only():
    d = _load_json()
    assert d["p238b_yellow_remains_observation_only"] is True
    assert d.get("current_state", {}).get("p238b_classification") == "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY"


def test_json_p211_held_by_user():
    d = _load_json()
    assert d["p211_remains_held_by_user"] is True
    assert d["p211_restart_authorized"] is False
    assert d.get("current_state", {}).get("p211_status") == "HELD_BY_USER"


def test_json_safety_principles_preserved():
    d = _load_json()
    principles = d.get("safety_principles_preserved", [])
    required = [
        "phase_0_actual_state_verification",
        "stop_on_mismatch",
        "allowed_file_whitelist",
        "explicit_authorization_for_db_write",
        "required_completion_check",
    ]
    for p in required:
        assert p in principles, f"Safety principle missing: {p}"


def test_json_type_d_e_no_simplification():
    d = _load_json()
    types = d.get("task_types", {})
    assert types["D"]["simplification"] == "none"
    assert types["E"]["simplification"] == "none"


def test_markdown_contains_stop_conditions():
    md = _load_md()
    assert "STOP" in md, "Markdown must reference STOP conditions"


def test_markdown_contains_phase_0():
    md = _load_md()
    assert "Phase 0" in md, "Markdown must reference Phase 0 actual-state verification"


def test_markdown_contains_required_completion_check():
    md = _load_md()
    assert "Required Completion Check" in md


def test_markdown_p238b_observation_only():
    md = _load_md()
    assert "YELLOW" in md and "observation-only" in md.lower(), \
        "Markdown must state YELLOW is observation-only"
    assert "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY" in md


def test_markdown_p211_held_by_user():
    md = _load_md()
    assert "HELD_BY_USER" in md, "Markdown must state P211 remains HELD_BY_USER"
    assert "P211" in md


def test_markdown_no_op_hold_rule_present():
    md = _load_md()
    assert "No-op HOLD" in md or "no-op HOLD" in md or "no_op_hold" in md.lower()


def test_markdown_proposal_only():
    md = _load_md()
    assert "proposal only" in md.lower() or "Proposal only" in md or "proposal_only" in md


def test_json_final_classification():
    d = _load_json()
    assert d["final_classification"] == "P240B_GOVERNANCE_SIMPLIFICATION_DESIGN_PROPOSAL_COMPLETE"
