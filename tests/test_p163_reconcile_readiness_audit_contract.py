"""
P163 Reconcile Readiness Audit Contract Tests

Verifies that the P163 artifacts exist, are correctly structured, contain required
governance confirmations, and that roadmap files reflect audit-only status with
no unauthorized reconcile actions.
"""
import json
import os
import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

P163_JSON_PATH = os.path.join(BASE, "outputs", "research", "power_lotto",
                               "p163_reconcile_readiness_audit_20260531.json")
P163_MD_PATH = os.path.join(BASE, "outputs", "research", "power_lotto",
                              "p163_reconcile_readiness_audit_20260531.md")
ACTIVE_TASK_PATH = os.path.join(BASE, "00-Plan", "roadmap", "active_task.md")
ROADMAP_PATH = os.path.join(BASE, "00-Plan", "roadmap", "roadmap.md")


@pytest.fixture(scope="module")
def p163_json():
    assert os.path.exists(P163_JSON_PATH), f"P163 JSON artifact not found at {P163_JSON_PATH}"
    with open(P163_JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p163_md():
    assert os.path.exists(P163_MD_PATH), f"P163 MD artifact not found at {P163_MD_PATH}"
    with open(P163_MD_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def active_task_text():
    assert os.path.exists(ACTIVE_TASK_PATH), f"active_task.md not found at {ACTIVE_TASK_PATH}"
    with open(ACTIVE_TASK_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def roadmap_text():
    assert os.path.exists(ROADMAP_PATH), f"roadmap.md not found at {ROADMAP_PATH}"
    with open(ROADMAP_PATH) as f:
        return f.read()


# Test 1: P163 JSON artifact exists
def test_p163_json_artifact_exists():
    assert os.path.exists(P163_JSON_PATH), f"P163 JSON artifact missing: {P163_JSON_PATH}"
    assert os.path.getsize(P163_JSON_PATH) > 0, "P163 JSON artifact is empty"


# Test 2: P163 final_classification
def test_p163_final_classification(p163_json):
    assert p163_json.get("final_classification") == "P163_RECONCILE_READINESS_AUDIT_READY", (
        f"Expected P163_RECONCILE_READINESS_AUDIT_READY, got {p163_json.get('final_classification')}"
    )


# Test 3: no_db_write_confirmation
def test_p163_no_db_write_confirmation(p163_json):
    assert p163_json.get("no_db_write_confirmation") is True, (
        "P163 JSON must have no_db_write_confirmation == true"
    )


# Test 4: no_merge_confirmation
def test_p163_no_merge_confirmation(p163_json):
    assert p163_json.get("no_merge_confirmation") is True, (
        "P163 JSON must have no_merge_confirmation == true"
    )


# Test 5: no_commit_confirmation
def test_p163_no_commit_confirmation(p163_json):
    assert p163_json.get("no_commit_confirmation") is True, (
        "P163 JSON must have no_commit_confirmation == true"
    )


# Test 6: no_push_confirmation
def test_p163_no_push_confirmation(p163_json):
    assert p163_json.get("no_push_confirmation") is True, (
        "P163 JSON must have no_push_confirmation == true"
    )


# Test 7: next_task is P164
def test_p163_next_task(p163_json):
    assert p163_json.get("next_task") == "P164_RECONCILE_PLAN_DECISION_GATE", (
        f"Expected next_task == P164_RECONCILE_PLAN_DECISION_GATE, got {p163_json.get('next_task')}"
    )


# Test 8: P163 MD artifact exists
def test_p163_md_artifact_exists():
    assert os.path.exists(P163_MD_PATH), f"P163 MD artifact missing: {P163_MD_PATH}"
    assert os.path.getsize(P163_MD_PATH) > 0, "P163 MD artifact is empty"


# Test 9: active_task.md contains P164 and "decision gate" (case-insensitive)
def test_active_task_contains_p164_and_decision_gate(active_task_text):
    assert "P164" in active_task_text, "active_task.md must reference P164"
    assert "decision gate" in active_task_text.lower(), (
        "active_task.md must contain 'decision gate' (case-insensitive)"
    )


# Test 10: roadmap.md does NOT contain "reconcile complete" or "governance risk resolved"
def test_roadmap_does_not_claim_reconcile_complete(roadmap_text):
    forbidden = ["reconcile complete", "governance risk resolved"]
    for phrase in forbidden:
        assert phrase.lower() not in roadmap_text.lower(), (
            f"roadmap.md must NOT contain '{phrase}' — reconcile is not complete and governance risk is unresolved"
        )


# Test 11: No forbidden strings in P163 JSON or MD
@pytest.mark.parametrize("artifact_path,artifact_type", [
    (P163_JSON_PATH, "json"),
    (P163_MD_PATH, "md"),
])
def test_no_forbidden_strings_in_p163(artifact_path, artifact_type):
    # These are completion-claim phrases — describing future options is allowed,
    # but claiming the action was completed is not.
    forbidden_strings = [
        "reconcile complete",
        "db migration applied",
        "champion has been promoted",
        "guaranteed win",
        "betting advice",
    ]
    with open(artifact_path) as f:
        content = f.read().lower()
    for phrase in forbidden_strings:
        assert phrase not in content, (
            f"Forbidden string '{phrase}' found in P163 {artifact_type} artifact"
        )


# Test 12: P163 JSON contains recommended_options with option_a, option_b, option_c
def test_p163_recommended_options_present(p163_json):
    assert "recommended_options" in p163_json, "P163 JSON must contain 'recommended_options'"
    options = p163_json["recommended_options"]
    assert "option_a" in options, "recommended_options must contain 'option_a'"
    assert "option_b" in options, "recommended_options must contain 'option_b'"
    assert "option_c" in options, "recommended_options must contain 'option_c'"
    # Each option must have description, pros, cons, required_authorization, stop_guard
    for opt_key in ["option_a", "option_b", "option_c"]:
        opt = options[opt_key]
        assert "description" in opt, f"{opt_key} must have 'description'"
        assert "pros" in opt, f"{opt_key} must have 'pros'"
        assert "cons" in opt, f"{opt_key} must have 'cons'"
        assert "required_authorization" in opt, f"{opt_key} must have 'required_authorization'"
        assert "stop_guard" in opt, f"{opt_key} must have 'stop_guard'"


# Test 13: Phase 0 verification shows all checks passed
def test_p163_phase0_all_checks_passed(p163_json):
    p0 = p163_json.get("phase_0_verification", {})
    assert p0.get("all_checks_passed") is True, "phase_0_verification.all_checks_passed must be true"
    assert p0.get("db_rows") == 94924, f"Expected db_rows=94924, got {p0.get('db_rows')}"
    assert p0.get("drift_guard") == "PASS", f"Expected drift_guard=PASS, got {p0.get('drift_guard')}"
    assert p0.get("p161_test") == "PASS", f"Expected p161_test=PASS, got {p0.get('p161_test')}"
    assert p0.get("p162_test") == "PASS", f"Expected p162_test=PASS, got {p0.get('p162_test')}"


# Test 14: Diff summary documents DB row delta
def test_p163_diff_summary_documents_delta(p163_json):
    diff = p163_json.get("diff_summary", {})
    assert "db_row_count_difference" in diff, "diff_summary must contain db_row_count_difference"
    db_diff = diff["db_row_count_difference"]
    assert db_diff.get("zen_gates") == 94924, f"Expected zen_gates=94924, got {db_diff.get('zen_gates')}"
    assert db_diff.get("main") == 54462, f"Expected main=54462, got {db_diff.get('main')}"
    assert db_diff.get("delta") == 40462, f"Expected delta=40462, got {db_diff.get('delta')}"


# Test 15: Risk classification includes HIGH items for DB schema/rows
def test_p163_risk_classification_has_high_items(p163_json):
    risk = p163_json.get("risk_classification", {})
    assert "HIGH" in risk, "risk_classification must contain HIGH category"
    high_items = risk["HIGH"]
    assert len(high_items) >= 2, f"Expected at least 2 HIGH items, got {len(high_items)}"
    # At least one HIGH item must mention bet_index
    assert any("bet_index" in item.lower() for item in high_items), (
        "At least one HIGH item must mention 'bet_index' schema difference"
    )


# Test 16: Governance risk still flagged as unresolved in roadmap
def test_roadmap_contains_unresolved_governance_risk(roadmap_text):
    # roadmap must mention the unresolved split
    assert "UNRESOLVED" in roadmap_text, (
        "roadmap.md must contain 'UNRESOLVED' to flag governance risk as unresolved"
    )
    assert "P164" in roadmap_text, "roadmap.md must reference P164 decision gate"
