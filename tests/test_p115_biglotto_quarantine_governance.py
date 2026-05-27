"""
tests/test_p115_biglotto_quarantine_governance.py

Test suite for P115: BIG_LOTTO Quarantine Governance Design.
All tests are read-only. No DB writes. No lifecycle mutations.
"""

import json
import sys
from pathlib import Path

import pytest

# ── Path setup ───────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

ARTIFACT_PATH = REPO_ROOT / "outputs" / "replay" / "p115_biglotto_quarantine_governance_20260527.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "p115_biglotto_quarantine_governance.py"
DOC_PATH = REPO_ROOT / "docs" / "replay" / "p115_biglotto_quarantine_governance_20260527.md"

P112_PATH = REPO_ROOT / "outputs" / "replay" / "p112_cross_lottery_prediction_helpfulness_audit_20260527.json"
P113_PATH = REPO_ROOT / "outputs" / "replay" / "p113_p112_action_decision_matrix_20260527.json"
P114_PATH = REPO_ROOT / "outputs" / "replay" / "p114_temporal_stability_audit_20260527.json"
P116_PATH = REPO_ROOT / "outputs" / "replay" / "p116_powerlotto_oos_monitoring_design_20260527.json"

TARGET_STRATEGY_ID = "fourier30_markov30_biglotto"
TARGET_LOTTERY_TYPE = "BIG_LOTTO"
EXPECTED_REPLAY_ROWS = 54462


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists(), f"Artifact not found: {ARTIFACT_PATH}"
    with open(ARTIFACT_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p112():
    assert P112_PATH.exists(), f"P112 artifact not found: {P112_PATH}"
    with open(P112_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p113():
    assert P113_PATH.exists(), f"P113 artifact not found: {P113_PATH}"
    with open(P113_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p114():
    assert P114_PATH.exists(), f"P114 artifact not found: {P114_PATH}"
    with open(P114_PATH) as f:
        return json.load(f)


# ── File existence tests ──────────────────────────────────────────────────────
class TestFileExistence:
    def test_artifact_exists(self):
        assert ARTIFACT_PATH.exists()

    def test_script_exists(self):
        assert SCRIPT_PATH.exists()

    def test_doc_exists(self):
        assert DOC_PATH.exists()

    def test_p112_artifact_exists(self):
        assert P112_PATH.exists()

    def test_p113_artifact_exists(self):
        assert P113_PATH.exists()

    def test_p114_artifact_exists(self):
        assert P114_PATH.exists()

    def test_p116_artifact_exists(self):
        assert P116_PATH.exists()


# ── Classification tests ──────────────────────────────────────────────────────
class TestClassification:
    def test_classification_is_ready(self, artifact):
        assert artifact["classification"] == "P115_BIGLOTTO_QUARANTINE_GOVERNANCE_READY"

    def test_final_classification_matches(self, artifact):
        assert artifact["classification"] == artifact["final_classification"]

    def test_task_id_correct(self, artifact):
        assert artifact["task_id"] == "P115_BIGLOTTO_QUARANTINE_GOVERNANCE"

    def test_target_strategy_correct(self, artifact):
        assert artifact["target_strategy_id"] == TARGET_STRATEGY_ID

    def test_target_lottery_correct(self, artifact):
        assert artifact["target_lottery_type"] == TARGET_LOTTERY_TYPE

    def test_generated_date_present(self, artifact):
        assert "generated_date" in artifact
        assert artifact["generated_date"] == "2026-05-27"


# ── Governance flags tests ────────────────────────────────────────────────────
class TestGovernanceFlags:
    def test_no_db_writes(self, artifact):
        assert artifact["db_writes"] is False

    def test_no_strategy_promotion(self, artifact):
        assert artifact["no_strategy_promotion"] is True

    def test_no_lifecycle_mutation(self, artifact):
        assert artifact["no_lifecycle_mutation"] is True

    def test_no_registry_mutation(self, artifact):
        assert artifact["no_registry_mutation"] is True

    def test_no_actual_quarantine_applied(self, artifact):
        assert artifact["no_actual_quarantine_applied"] is True

    def test_no_replay_row_delete(self, artifact):
        assert artifact["no_replay_row_delete"] is True

    def test_no_4star_backtest(self, artifact):
        assert artifact["no_4star_backtest"] is True

    def test_no_special3_p108_rerun(self, artifact):
        assert artifact["no_special3_p108_rerun"] is True

    def test_no_powerlotto_p117_execution(self, artifact):
        assert artifact["no_powerlotto_p117_execution"] is True

    def test_source_unknown_caveat_preserved(self, artifact):
        assert artifact["source_unknown_caveat_preserved"] is True

    def test_replay_rows_before_unchanged(self, artifact):
        assert artifact["replay_rows_before"] == EXPECTED_REPLAY_ROWS

    def test_replay_rows_after_unchanged(self, artifact):
        assert artifact["replay_rows_after"] == EXPECTED_REPLAY_ROWS

    def test_replay_rows_consistent(self, artifact):
        assert artifact["replay_rows_before"] == artifact["replay_rows_after"]


# ── Evidence summary tests ────────────────────────────────────────────────────
class TestNegativeEvidenceSummary:
    def test_evidence_summary_present(self, artifact):
        assert "negative_evidence_summary" in artifact

    def test_p112_classification_sub_baseline(self, artifact):
        ev = artifact["negative_evidence_summary"]
        assert ev["p112_classification"] == "SUB_BASELINE"

    def test_p112_edge_negative(self, artifact):
        ev = artifact["negative_evidence_summary"]
        assert ev["p112_edge_vs_baseline"] < 0

    def test_p112_edge_value(self, artifact):
        ev = artifact["negative_evidence_summary"]
        assert abs(ev["p112_edge_vs_baseline"] - (-0.013361)) < 0.000001

    def test_p113_action_demote_or_quarantine(self, artifact):
        ev = artifact["negative_evidence_summary"]
        assert ev["p113_action"] == "DEMOTE_OR_QUARANTINE_CANDIDATE"

    def test_p114_stability_label(self, artifact):
        ev = artifact["negative_evidence_summary"]
        assert ev["p114_stability_label"] == "STABLE_NEGATIVE"

    def test_p114_decision(self, artifact):
        ev = artifact["negative_evidence_summary"]
        assert ev["p114_decision"] == "READY_FOR_QUARANTINE_GOVERNANCE"

    def test_negative_windows_count_five(self, artifact):
        ev = artifact["negative_evidence_summary"]
        assert ev["temporal_window_negative_count"] == 5

    def test_total_windows_count_five(self, artifact):
        ev = artifact["negative_evidence_summary"]
        assert ev["temporal_window_total_count"] == 5

    def test_all_windows_negative(self, artifact):
        ev = artifact["negative_evidence_summary"]
        assert ev["all_windows_negative"] is True

    def test_all_temporal_windows_have_negative_edge(self, artifact):
        ev = artifact["negative_evidence_summary"]
        windows = ev["temporal_windows"]
        for wname, wdata in windows.items():
            assert isinstance(wdata, dict), f"Window {wname} should be a dict"
            assert wdata.get("positive_edge") is False, f"Window {wname} should have negative edge"
            assert wdata.get("edge_vs_baseline") < 0, f"Window {wname} edge should be < 0"

    def test_first_third_edge(self, artifact):
        ev = artifact["negative_evidence_summary"]
        w = ev["temporal_windows"]["first_third"]
        assert abs(w["edge_vs_baseline"] - (-0.016694)) < 0.000001

    def test_middle_third_edge(self, artifact):
        ev = artifact["negative_evidence_summary"]
        w = ev["temporal_windows"]["middle_third"]
        assert abs(w["edge_vs_baseline"] - (-0.018694)) < 0.000001

    def test_last_third_edge(self, artifact):
        ev = artifact["negative_evidence_summary"]
        w = ev["temporal_windows"]["last_third"]
        assert abs(w["edge_vs_baseline"] - (-0.004694)) < 0.000001


# ── Quarantine design tests ───────────────────────────────────────────────────
class TestQuarantineGovernanceDesign:
    def test_design_present(self, artifact):
        assert "quarantine_governance_design" in artifact

    def test_quarantine_status_governance_ready(self, artifact):
        design = artifact["quarantine_governance_design"]
        assert design["quarantine_status"] == "GOVERNANCE_READY"

    def test_production_quarantine_not_applied(self, artifact):
        design = artifact["quarantine_governance_design"]
        assert design["production_quarantine_applied"] is False

    def test_recommended_operator_label(self, artifact):
        design = artifact["quarantine_governance_design"]
        assert design["recommended_operator_label"] == "STABLE_NEGATIVE_QUARANTINE_CANDIDATE"

    def test_future_auth_required(self, artifact):
        design = artifact["quarantine_governance_design"]
        assert design["future_quarantine_authorization_required"] is True

    def test_evidence_satisfied(self, artifact):
        design = artifact["quarantine_governance_design"]
        assert design["evidence_satisfied"] is True

    def test_authorization_phrase_present(self, artifact):
        design = artifact["quarantine_governance_design"]
        phrase = design.get("future_authorization_phrase", "")
        assert "fourier30_markov30_biglotto" in phrase
        assert "quarantine" in phrase.lower()

    def test_catalog_disclosure_present(self, artifact):
        design = artifact["quarantine_governance_design"]
        disclosure = design.get("recommended_catalog_disclosure", "")
        assert len(disclosure) > 50
        assert "fourier30_markov30_biglotto" in disclosure or "SUB_BASELINE" in disclosure

    def test_minimum_evidence_list_present(self, artifact):
        design = artifact["quarantine_governance_design"]
        items = design.get("minimum_evidence_required_before_actual_quarantine", [])
        assert len(items) >= 5

    def test_future_action_requirements_present(self, artifact):
        design = artifact["quarantine_governance_design"]
        reqs = design.get("future_quarantine_action_requirements", [])
        assert len(reqs) >= 5

    def test_no_delete_requirement_present(self, artifact):
        design = artifact["quarantine_governance_design"]
        reqs = design.get("future_quarantine_action_requirements", [])
        joined = " ".join(reqs).lower()
        assert "not delete" in joined or "must not delete" in joined


# ── Reference tests ───────────────────────────────────────────────────────────
class TestArtifactReferences:
    def test_p112_reference_present(self, artifact):
        assert "p112_reference" in artifact
        ref = artifact["p112_reference"]
        assert ref["classification"] == "P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY"

    def test_p113_reference_present(self, artifact):
        assert "p113_reference" in artifact
        ref = artifact["p113_reference"]
        assert ref["classification"] == "P113_P112_ACTION_DECISION_MATRIX_READY"

    def test_p114_reference_present(self, artifact):
        assert "p114_reference" in artifact
        ref = artifact["p114_reference"]
        assert ref["classification"] == "P114_TEMPORAL_STABILITY_AUDIT_READY"

    def test_p116_reference_present(self, artifact):
        assert "p116_reference" in artifact
        ref = artifact["p116_reference"]
        assert ref["classification"] == "P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY"


# ── Upstream artifact consistency ─────────────────────────────────────────────
class TestUpstreamConsistency:
    def test_p114_confirms_quarantine_candidate(self, p114):
        candidates = p114.get("quarantine_governance_candidates", [])
        assert TARGET_STRATEGY_ID in candidates

    def test_p114_has_target_strategy_entry(self, p114):
        found = any(
            e.get("strategy_id") == TARGET_STRATEGY_ID
            for e in p114.get("per_strategy_temporal_results", [])
        )
        assert found

    def test_p113_has_demote_action_for_target(self, p113):
        found = None
        for e in p113.get("per_strategy_action_matrix", []):
            if e.get("strategy_id") == TARGET_STRATEGY_ID:
                found = e
                break
        assert found is not None
        assert found["p113_action"] == "DEMOTE_OR_QUARANTINE_CANDIDATE"

    def test_p112_has_sub_baseline_for_target(self, p112):
        found = None
        for e in p112.get("per_strategy_results", []):
            if e.get("strategy_id") == TARGET_STRATEGY_ID:
                found = e
                break
        assert found is not None
        assert found["classification"] == "SUB_BASELINE"


# ── Script no SQL write tests ─────────────────────────────────────────────────
class TestScriptNoSQLWrites:
    def _get_execute_lines(self):
        """Return only lines that contain a SQL execute call."""
        src = SCRIPT_PATH.read_text()
        return [line for line in src.splitlines() if ".execute(" in line]

    def test_script_has_no_insert(self):
        for line in self._get_execute_lines():
            assert "INSERT" not in line.upper(), f"SQL INSERT found in execute call: {line}"

    def test_script_has_no_update(self):
        for line in self._get_execute_lines():
            assert "UPDATE" not in line.upper(), f"SQL UPDATE found in execute call: {line}"

    def test_script_has_no_delete(self):
        for line in self._get_execute_lines():
            assert "DELETE" not in line.upper(), f"SQL DELETE found in execute call: {line}"

    def test_script_opens_db_readonly(self):
        src = SCRIPT_PATH.read_text()
        assert "mode=ro" in src

    def test_script_has_json_out_arg(self):
        src = SCRIPT_PATH.read_text()
        assert "--json-out" in src

    def test_script_defines_target_strategy(self):
        src = SCRIPT_PATH.read_text()
        assert "fourier30_markov30_biglotto" in src

    def test_script_defines_expected_replay_rows(self):
        src = SCRIPT_PATH.read_text()
        assert "54462" in src


# ── Criteria tests ────────────────────────────────────────────────────────────
class TestPassHoldCriteria:
    def test_criteria_present(self, artifact):
        assert "pass_hold_quarantine_candidate_criteria" in artifact

    def test_pass_criteria_present(self, artifact):
        criteria = artifact["pass_hold_quarantine_candidate_criteria"]
        assert "pass" in criteria

    def test_hold_criteria_present(self, artifact):
        criteria = artifact["pass_hold_quarantine_candidate_criteria"]
        assert "hold" in criteria

    def test_quarantine_candidate_criteria_present(self, artifact):
        criteria = artifact["pass_hold_quarantine_candidate_criteria"]
        assert "quarantine_candidate" in criteria

    def test_quarantine_candidate_current_assessment_mentions_target(self, artifact):
        criteria = artifact["pass_hold_quarantine_candidate_criteria"]
        assessment = criteria.get("quarantine_candidate", {}).get("current_assessment", "")
        assert TARGET_STRATEGY_ID in assessment


# ── Limitations and invariants ────────────────────────────────────────────────
class TestLimitationsAndInvariants:
    def test_limitations_present(self, artifact):
        assert "limitations" in artifact
        assert len(artifact["limitations"]) >= 5

    def test_global_invariants_present(self, artifact):
        assert "global_invariants" in artifact
        assert len(artifact["global_invariants"]) >= 5

    def test_limitations_mention_no_quarantine_applied(self, artifact):
        joined = " ".join(artifact["limitations"]).lower()
        assert "no actual quarantine" in joined or "not applied" in joined

    def test_global_invariants_mention_no_db_writes(self, artifact):
        joined = " ".join(artifact["global_invariants"]).lower()
        assert "no db write" in joined or "db_writes=false" in joined


# ── Next task recommendations ─────────────────────────────────────────────────
class TestNextTaskRecommendations:
    def test_recommendations_present(self, artifact):
        assert "next_task_recommendations" in artifact
        assert len(artifact["next_task_recommendations"]) >= 2

    def test_p108_is_blocked(self, artifact):
        blocked = [t for t in artifact["next_task_recommendations"] if t.get("task_id") == "P108"]
        assert len(blocked) >= 1
        assert blocked[0]["blocked"] is True

    def test_p117_is_not_blocked(self, artifact):
        p117 = [t for t in artifact["next_task_recommendations"] if t.get("task_id") == "P117"]
        assert len(p117) >= 1
        assert p117[0]["blocked"] is False
