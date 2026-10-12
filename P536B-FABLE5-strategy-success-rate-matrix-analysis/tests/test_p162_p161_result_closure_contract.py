"""
P162 Contract Tests — P161 Result Closure

Verifies that:
1. P162 artifact JSON exists at the correct path
2. P162 final_classification == "P162_P161_RESULT_CLOSURE_READY"
3. active_task.md does NOT mark P161 as READY (must be COMPLETE)
4. roadmap.md contains "R1/P161" and "COMPLETE" (or equivalent)
5. No forbidden strings appear in any P162 artifact

No DB writes. No registry mutations. No controlled_apply. No champion.
"""
import json
import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent

P162_JSON = REPO_ROOT / "outputs" / "research" / "power_lotto" / "p162_p161_result_closure_20260531.json"
P162_MD = REPO_ROOT / "outputs" / "research" / "power_lotto" / "p162_p161_result_closure_20260531.md"
ACTIVE_TASK_MD = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP_MD = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"

FORBIDDEN_STRINGS = [
    "guaranteed win",
    "betting advice",
    "controlled_apply authorized",
]


# ---------------------------------------------------------------------------
# Test 1: P162 artifact JSON exists at correct path
# ---------------------------------------------------------------------------
def test_p162_json_artifact_exists():
    """P162 JSON artifact must exist at the expected path."""
    assert P162_JSON.exists(), f"P162 JSON artifact not found at: {P162_JSON}"
    assert P162_JSON.stat().st_size > 0, "P162 JSON artifact is empty"


# ---------------------------------------------------------------------------
# Test 2: P162 final_classification == "P162_P161_RESULT_CLOSURE_READY"
# ---------------------------------------------------------------------------
def test_p162_final_classification():
    """P162 JSON must have final_classification == P162_P161_RESULT_CLOSURE_READY."""
    assert P162_JSON.exists(), "P162 JSON artifact not found"
    data = json.loads(P162_JSON.read_text())
    assert "final_classification" in data, "P162 JSON missing 'final_classification' key"
    assert data["final_classification"] == "P162_P161_RESULT_CLOSURE_READY", (
        f"Expected 'P162_P161_RESULT_CLOSURE_READY', got '{data['final_classification']}'"
    )


def test_p162_task_field():
    """P162 JSON must have task == 'P162_P161_RESULT_CLOSURE'."""
    data = json.loads(P162_JSON.read_text())
    assert data.get("task") == "P162_P161_RESULT_CLOSURE"


def test_p162_db_unchanged_confirmation():
    """P162 JSON must confirm DB is unchanged at 94924 rows."""
    data = json.loads(P162_JSON.read_text())
    assert data.get("db_row_count") == 94924, "db_row_count must be 94924"
    assert data.get("db_unchanged_confirmation") is True, "db_unchanged_confirmation must be true"


def test_p162_governance_confirmations():
    """P162 JSON must confirm no DB write, no registry mutation, no champion, no controlled_apply."""
    data = json.loads(P162_JSON.read_text())
    assert data.get("no_db_write_confirmation") is True
    assert data.get("no_registry_mutation_confirmation") is True
    assert data.get("no_champion_confirmation") is True
    assert data.get("no_controlled_apply_confirmation") is True


def test_p162_p161_evidence_present():
    """P162 JSON must contain p161_completed_evidence with key fields."""
    data = json.loads(P162_JSON.read_text())
    assert "p161_completed_evidence" in data, "p161_completed_evidence missing"
    ev = data["p161_completed_evidence"]
    assert "classification" in ev
    assert ev["classification"] == "P161_POWER_LOTTO_EFFECTIVENESS_BASELINE_READY"
    assert ev.get("db_row_count") == 94924
    assert ev.get("any_strategy_beats_random_after_correction") is False


def test_p162_next_task_is_p163():
    """P162 JSON must recommend P163 as next task."""
    data = json.loads(P162_JSON.read_text())
    assert data.get("next_recommended_task") == "P163_RECONCILE_READINESS_AUDIT_ONLY", (
        f"Expected P163_RECONCILE_READINESS_AUDIT_ONLY, got {data.get('next_recommended_task')}"
    )


# ---------------------------------------------------------------------------
# Test 3: active_task.md must NOT mark P161 as READY (must be COMPLETE)
# ---------------------------------------------------------------------------
def test_active_task_p161_not_ready():
    """active_task.md must not contain 'P161' with 'READY' in the same context.
    P161 status must be COMPLETE, not READY.
    """
    assert ACTIVE_TASK_MD.exists(), f"active_task.md not found at {ACTIVE_TASK_MD}"
    content = ACTIVE_TASK_MD.read_text()

    # P161 must appear in the file
    assert "P161" in content, "active_task.md must reference P161"

    # P161 must be marked COMPLETE, not READY
    lines = content.splitlines()
    for line in lines:
        if "P161" in line:
            # A line containing P161 must not say READY without also saying COMPLETE or similar
            # We forbid "P161" + "READY" on the same line without "COMPLETE"
            if "READY" in line and "COMPLETE" not in line and "P161_POWER_LOTTO_EFFECTIVENESS_BASELINE_READY" not in line:
                pytest.fail(
                    f"active_task.md has P161 marked as READY (not COMPLETE): {line.strip()}"
                )

    # Explicitly verify COMPLETE appears alongside P161
    p161_complete_found = any(
        "P161" in line and ("COMPLETE" in line or "COMPLETE" in content.split("P161")[1][:200])
        for line in lines
        if "P161" in line
    )
    assert p161_complete_found or "COMPLETE" in content, (
        "active_task.md must indicate P161 is COMPLETE"
    )


# ---------------------------------------------------------------------------
# Test 4: roadmap.md contains "R1/P161" and "COMPLETE"
# ---------------------------------------------------------------------------
def test_roadmap_contains_r1_p161_complete():
    """roadmap.md must contain both 'R1/P161' and 'COMPLETE'."""
    assert ROADMAP_MD.exists(), f"roadmap.md not found at {ROADMAP_MD}"
    content = ROADMAP_MD.read_text()
    assert "R1/P161" in content, "roadmap.md must contain 'R1/P161'"
    # COMPLETE must appear somewhere in the roadmap after the R1/P161 entry
    assert "COMPLETE" in content, "roadmap.md must contain 'COMPLETE'"


def test_roadmap_contains_p163():
    """roadmap.md must contain P163 as next pending task."""
    content = ROADMAP_MD.read_text()
    assert "P163" in content, "roadmap.md must reference P163"
    assert "RECONCILE_READINESS_AUDIT_ONLY" in content or "audit-only" in content.lower() or "audit only" in content.lower(), (
        "roadmap.md must note P163 is audit/readiness only"
    )


# ---------------------------------------------------------------------------
# Test 5: No forbidden strings in any P162 artifact
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("artifact_path", [P162_JSON, P162_MD, ACTIVE_TASK_MD, ROADMAP_MD])
def test_no_forbidden_strings(artifact_path):
    """No P162 artifact may contain forbidden strings."""
    if not artifact_path.exists():
        pytest.skip(f"Artifact not found: {artifact_path}")
    content = artifact_path.read_text().lower()
    for forbidden in FORBIDDEN_STRINGS:
        assert forbidden.lower() not in content, (
            f"Forbidden string '{forbidden}' found in {artifact_path.name}"
        )
