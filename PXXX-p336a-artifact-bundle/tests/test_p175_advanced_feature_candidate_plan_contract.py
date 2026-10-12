"""
Tests for P175: POWER_LOTTO R2 Advanced Feature Candidate Plan (Plan-Only).
============================================================================
All tests are READ-ONLY. No DB writes, no staging checks.

Verifies:
  - Artifact existence (JSON + MD)
  - final_classification = P175_POWER_LOTTO_R2_ADVANCED_FEATURE_CANDIDATE_PLAN_READY
  - Authorization phrase detected
  - Phase 0 PASS
  - p174_summary: P174 READY, P173 NULL unchanged
  - candidate_plan: exactly C03/C05/C06/C07
  - C03: co-occurrence pair graph, pair-space=703, high overfitting
  - C06: causal CUSUM, no future labels, high overfitting
  - multiple_testing_plan: family_size=4, bonferroni_threshold=0.0125
  - C03 pair-space burden documented
  - oos_protocol_plan: read-only, no bet-row replication
  - leakage_prevention_plan present
  - risk_assessment present
  - p176_scope_boundary present, P176 blocked
  - governance: no DB write, no prototype, no wagering recommendations
  - next_task = P176_POWER_LOTTO_R2_ADVANCED_FEATURE_MINIMAL_PROTOTYPE_READ_ONLY
  - P176 blocked by user authorization
  - active_task.md: P176 BLOCKED
  - No forbidden strings
  - DB rows unchanged at 94924
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p175_advanced_feature_candidate_plan_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p175_advanced_feature_candidate_plan_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_FINAL_CLASSIFICATION = "P175_POWER_LOTTO_R2_ADVANCED_FEATURE_CANDIDATE_PLAN_READY"
EXPECTED_DB_ROWS = 94924
EXPECTED_NEXT_TASK = "P176_POWER_LOTTO_R2_ADVANCED_FEATURE_MINIMAL_PROTOTYPE_READ_ONLY"
EXPECTED_AUTHORIZATION_PHRASE = "YES start P175 POWER_LOTTO R2 advanced feature candidate plan"
EXPECTED_CANDIDATES = {"C03", "C05", "C06", "C07"}
EXPECTED_FAMILY_SIZE = 4
EXPECTED_BONFERRONI_THRESHOLD = 0.0125

FORBIDDEN_STRINGS = [
    "guaranteed win",
    "betting advice",
    "champion promoted",
    "controlled_apply authorized",
    "db migrated",
    "production deployment",
    "method found",
    "edge confirmed",
    "r2 confirms edge",
    "split resolved",
]


@pytest.fixture(scope="module")
def artifact():
    assert JSON_OUT.exists(), f"P175 JSON artifact missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P175 MD artifact missing: {MD_OUT}"
    return MD_OUT.read_text()


@pytest.fixture(scope="module")
def active_task_text():
    assert ACTIVE_TASK.exists(), f"active_task.md missing: {ACTIVE_TASK}"
    return ACTIVE_TASK.read_text()


@pytest.fixture(scope="module")
def roadmap_text():
    assert ROADMAP.exists(), f"roadmap.md missing: {ROADMAP}"
    return ROADMAP.read_text()


@pytest.fixture(scope="module")
def cto_text():
    assert CTO_ANALYSIS.exists(), f"CTO-Analysis.md missing: {CTO_ANALYSIS}"
    return CTO_ANALYSIS.read_text()


# ── Artifact existence ─────────────────────────────────────────────────────

def test_p175_json_exists():
    assert JSON_OUT.exists(), f"P175 JSON missing: {JSON_OUT}"


def test_p175_md_exists():
    assert MD_OUT.exists(), f"P175 MD missing: {MD_OUT}"


# ── Classification and authorization ──────────────────────────────────────

def test_p175_final_classification(artifact):
    assert artifact.get("final_classification") == EXPECTED_FINAL_CLASSIFICATION, (
        f"Expected {EXPECTED_FINAL_CLASSIFICATION}, got {artifact.get('final_classification')}"
    )


def test_p175_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase, (
        f"Authorization phrase not detected. Got: {phrase!r}"
    )


def test_p175_phase0_pass(artifact):
    assert artifact.get("phase_0_verification", {}).get("result") == "PASS"


def test_p175_phase0_db_rows(artifact):
    assert artifact.get("phase_0_verification", {}).get("db_rows") == EXPECTED_DB_ROWS


# ── P174 summary ───────────────────────────────────────────────────────────

def test_p175_p174_summary_present(artifact):
    assert "p174_summary" in artifact, "p174_summary missing"


def test_p175_p174_summary_classification(artifact):
    summary = artifact.get("p174_summary", {})
    assert "P174_POWER_LOTTO_R2_DECISION_REVIEW_READY" in summary.get("classification", ""), (
        "p174_summary must reference P174 classification"
    )


def test_p175_p174_summary_p173_null_unchanged(artifact):
    summary = artifact.get("p174_summary", {})
    assert summary.get("p173_null_unchanged") is True, (
        "p174_summary.p173_null_unchanged must be True"
    )


def test_p175_p174_summary_no_edge_found(artifact):
    summary = artifact.get("p174_summary", {})
    assert summary.get("no_edge_found_as_of_p174") is True, (
        "p174_summary.no_edge_found_as_of_p174 must be True"
    )


# ── Candidate plan ─────────────────────────────────────────────────────────

def test_p175_candidate_plan_present(artifact):
    assert "candidate_plan" in artifact, "candidate_plan missing"


def test_p175_exactly_four_candidates(artifact):
    plan = artifact.get("candidate_plan", {})
    assert plan.get("total_candidates") == 4, (
        f"candidate_plan.total_candidates must be 4. Got {plan.get('total_candidates')}"
    )
    candidates = plan.get("candidates", [])
    assert len(candidates) == 4, (
        f"candidate_plan.candidates must have 4 items. Got {len(candidates)}"
    )


def test_p175_candidate_ids_are_c03_c05_c06_c07(artifact):
    plan = artifact.get("candidate_plan", {})
    candidates = plan.get("candidates", [])
    ids = {c.get("candidate_id") for c in candidates}
    assert ids == EXPECTED_CANDIDATES, (
        f"candidate IDs must be {EXPECTED_CANDIDATES}. Got {ids}"
    )


def test_p175_each_candidate_has_causal_rule(artifact):
    plan = artifact.get("candidate_plan", {})
    for c in plan.get("candidates", []):
        assert "causal_feature_extraction_rule" in c, (
            f"Candidate {c.get('candidate_id')} missing causal_feature_extraction_rule"
        )


def test_p175_each_candidate_has_leakage_rule(artifact):
    plan = artifact.get("candidate_plan", {})
    for c in plan.get("candidates", []):
        assert "leakage_prevention_rule" in c, (
            f"Candidate {c.get('candidate_id')} missing leakage_prevention_rule"
        )


def test_p175_each_candidate_has_frozen_config(artifact):
    plan = artifact.get("candidate_plan", {})
    for c in plan.get("candidates", []):
        assert "frozen_config_candidates" in c, (
            f"Candidate {c.get('candidate_id')} missing frozen_config_candidates"
        )


def test_p175_each_candidate_has_overfitting_risk(artifact):
    plan = artifact.get("candidate_plan", {})
    for c in plan.get("candidates", []):
        assert "overfitting_risk" in c, (
            f"Candidate {c.get('candidate_id')} missing overfitting_risk"
        )


def test_p175_each_candidate_has_min_oos(artifact):
    plan = artifact.get("candidate_plan", {})
    for c in plan.get("candidates", []):
        assert "minimum_oos_requirement" in c, (
            f"Candidate {c.get('candidate_id')} missing minimum_oos_requirement"
        )


def test_p175_each_candidate_has_failure_condition(artifact):
    plan = artifact.get("candidate_plan", {})
    for c in plan.get("candidates", []):
        assert "failure_condition" in c, (
            f"Candidate {c.get('candidate_id')} missing failure_condition"
        )


def test_p175_each_candidate_has_null_reporting(artifact):
    plan = artifact.get("candidate_plan", {})
    for c in plan.get("candidates", []):
        assert "expected_null_reporting_behavior" in c, (
            f"Candidate {c.get('candidate_id')} missing expected_null_reporting_behavior"
        )


# ── C03-specific checks ───────────────────────────────────────────────────

def test_p175_c03_pair_space_documented(artifact):
    plan = artifact.get("candidate_plan", {})
    c03 = next((c for c in plan.get("candidates", []) if c.get("candidate_id") == "C03"), None)
    assert c03 is not None, "C03 not found in candidate_plan"
    pair_space = c03.get("pair_space", "")
    assert "703" in str(pair_space), (
        f"C03 must document pair_space C(38,2)=703. Got: {pair_space!r}"
    )


def test_p175_c03_high_overfitting(artifact):
    plan = artifact.get("candidate_plan", {})
    c03 = next((c for c in plan.get("candidates", []) if c.get("candidate_id") == "C03"), None)
    assert c03 is not None
    assert "HIGH" in c03.get("overfitting_risk", ""), (
        "C03 overfitting_risk must be HIGH"
    )


def test_p175_c03_internal_pair_burden_documented(artifact):
    plan = artifact.get("candidate_plan", {})
    c03 = next((c for c in plan.get("candidates", []) if c.get("candidate_id") == "C03"), None)
    assert c03 is not None
    burden = c03.get("internal_pair_space_burden", "")
    assert "703" in burden, (
        f"C03 internal_pair_space_burden must mention 703. Got: {burden!r}"
    )


# ── C06-specific checks ───────────────────────────────────────────────────

def test_p175_c06_causal_rule_present(artifact):
    plan = artifact.get("candidate_plan", {})
    c06 = next((c for c in plan.get("candidates", []) if c.get("candidate_id") == "C06"), None)
    assert c06 is not None, "C06 not found in candidate_plan"
    rule = c06.get("causal_feature_extraction_rule", "").lower()
    assert "one-sided" in rule or "causal" in rule or "prior draws" in rule, (
        "C06 causal_feature_extraction_rule must mention one-sided/causal CUSUM"
    )


def test_p175_c06_no_future_labels_rule(artifact):
    plan = artifact.get("candidate_plan", {})
    c06 = next((c for c in plan.get("candidates", []) if c.get("candidate_id") == "C06"), None)
    assert c06 is not None
    assert "no_future_labels_rule" in c06 or "future" in str(c06.get("leakage_prevention_rule", "")).lower(), (
        "C06 must document no-future-labels rule"
    )


def test_p175_c06_high_overfitting(artifact):
    plan = artifact.get("candidate_plan", {})
    c06 = next((c for c in plan.get("candidates", []) if c.get("candidate_id") == "C06"), None)
    assert c06 is not None
    assert "HIGH" in c06.get("overfitting_risk", ""), "C06 overfitting_risk must be HIGH"


# ── Multiple testing plan ─────────────────────────────────────────────────

def test_p175_multiple_testing_plan_present(artifact):
    assert "multiple_testing_plan" in artifact, "multiple_testing_plan missing"


def test_p175_family_size_is_4(artifact):
    mtp = artifact.get("multiple_testing_plan", {})
    assert mtp.get("candidate_family_size") == EXPECTED_FAMILY_SIZE, (
        f"family_size must be {EXPECTED_FAMILY_SIZE}. Got {mtp.get('candidate_family_size')}"
    )


def test_p175_bonferroni_threshold_0125(artifact):
    mtp = artifact.get("multiple_testing_plan", {})
    threshold = mtp.get("bonferroni_threshold", 0)
    assert abs(threshold - EXPECTED_BONFERRONI_THRESHOLD) < 0.0001, (
        f"bonferroni_threshold must be ~{EXPECTED_BONFERRONI_THRESHOLD}. Got {threshold}"
    )


def test_p175_bonferroni_consistent(artifact):
    mtp = artifact.get("multiple_testing_plan", {})
    alpha = mtp.get("alpha", 0.05)
    family = mtp.get("candidate_family_size", 4)
    threshold = mtp.get("bonferroni_threshold", 0)
    assert abs(threshold - alpha / family) < 0.0001, (
        f"bonferroni_threshold ({threshold}) must equal alpha/family ({alpha/family})"
    )


def test_p175_c03_pair_burden_in_mtp(artifact):
    mtp = artifact.get("multiple_testing_plan", {})
    burden = mtp.get("c03_internal_pair_space_burden", "")
    assert "703" in burden, (
        "multiple_testing_plan must document C03 pair-space burden of 703"
    )


# ── OOS protocol plan ─────────────────────────────────────────────────────

def test_p175_oos_protocol_present(artifact):
    assert "oos_protocol_plan" in artifact, "oos_protocol_plan missing"


def test_p175_oos_read_only(artifact):
    oos = artifact.get("oos_protocol_plan", {})
    assert oos.get("read_only") is True, "oos_protocol_plan.read_only must be True"


def test_p175_oos_no_shuffling(artifact):
    oos = artifact.get("oos_protocol_plan", {})
    assert oos.get("no_shuffling") is True, "oos_protocol_plan.no_shuffling must be True"


def test_p175_oos_no_bet_row_replication(artifact):
    oos = artifact.get("oos_protocol_plan", {})
    unit = oos.get("statistical_unit", "").lower()
    anti_rep = oos.get("no_bet_row_pseudo_replication", "")
    assert "per draw" in unit or "bet-row" in str(anti_rep).lower() or "bet_row" in str(anti_rep).lower(), (
        "oos_protocol_plan must prohibit bet-row pseudo-replication"
    )


def test_p175_oos_initial_training_size(artifact):
    oos = artifact.get("oos_protocol_plan", {})
    size = oos.get("initial_training_size", 0)
    assert size >= 500, f"oos_protocol_plan.initial_training_size must be >= 500. Got {size}"


# ── Leakage prevention plan ───────────────────────────────────────────────

def test_p175_leakage_prevention_present(artifact):
    assert "leakage_prevention_plan" in artifact, "leakage_prevention_plan missing"


def test_p175_leakage_general_rule(artifact):
    lpp = artifact.get("leakage_prevention_plan", {})
    rule = lpp.get("general_rule", "")
    assert len(rule) > 20 and ("prior" in rule.lower() or "draws[0" in rule or "i-1" in rule or "before" in rule.lower()), (
        "leakage_prevention_plan.general_rule must state prior-draws-only rule"
    )


# ── Risk assessment ────────────────────────────────────────────────────────

def test_p175_risk_assessment_present(artifact):
    assert "risk_assessment" in artifact, "risk_assessment missing"


def test_p175_risk_prior_probability_low(artifact):
    ra = artifact.get("risk_assessment", {})
    prior = ra.get("overall_prior_probability", "").lower()
    assert "low" in prior, "risk_assessment.overall_prior_probability must state LOW"


def test_p175_risk_recommendation_if_all_null(artifact):
    ra = artifact.get("risk_assessment", {})
    rec = ra.get("recommendation_if_all_p176_null", "")
    assert len(rec) > 20, "risk_assessment.recommendation_if_all_p176_null must be present"


# ── P176 scope boundary ───────────────────────────────────────────────────

def test_p175_p176_scope_present(artifact):
    assert "p176_scope_boundary" in artifact, "p176_scope_boundary missing"


def test_p175_p176_task_name(artifact):
    boundary = artifact.get("p176_scope_boundary", {})
    task = boundary.get("task_name", "")
    assert EXPECTED_NEXT_TASK in task, (
        f"p176_scope_boundary.task_name must be {EXPECTED_NEXT_TASK}. Got: {task!r}"
    )


def test_p175_p176_read_only(artifact):
    boundary = artifact.get("p176_scope_boundary", {})
    allowed = " ".join(boundary.get("allowed_in_p176", [])).lower()
    assert "read-only" in allowed or "read_only" in allowed, (
        "p176_scope_boundary must include read-only in allowed"
    )


def test_p175_p176_forbidden_db_write(artifact):
    boundary = artifact.get("p176_scope_boundary", {})
    forbidden = " ".join(boundary.get("forbidden_in_p176", [])).lower()
    assert "db write" in forbidden or "registry" in forbidden, (
        "p176_scope_boundary.forbidden_in_p176 must include DB write or registry"
    )


def test_p175_p176_authorization_required(artifact):
    boundary = artifact.get("p176_scope_boundary", {})
    assert boundary.get("p176_authorization_required") is True
    assert boundary.get("p176_blocked_by_user_authorization") is True


def test_p175_p176_must_report_null(artifact):
    boundary = artifact.get("p176_scope_boundary", {})
    assert boundary.get("p176_must_report_null_if_all_fail") is True, (
        "p176_scope_boundary.p176_must_report_null_if_all_fail must be True"
    )


# ── Governance ─────────────────────────────────────────────────────────────

def test_p175_no_db_write(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True


def test_p175_no_prototype_script(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_prototype_script_in_p175") is True, (
        "no_prototype_script_in_p175 must be True"
    )


def test_p175_no_registry_mutation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_registry_mutation") is True


def test_p175_no_controlled_apply(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_controlled_apply") is True


def test_p175_no_champion_promotion(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_champion_promotion") is True


def test_p175_no_wagering(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_wagering_recommendations") is True


def test_p175_p173_null_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p173_null_unchanged") is True


def test_p175_db_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("db_unchanged") is True
    assert gov.get("db_rows_before") == EXPECTED_DB_ROWS
    assert gov.get("db_rows_after") == EXPECTED_DB_ROWS


# ── Next task ──────────────────────────────────────────────────────────────

def test_p175_next_task_is_p176(artifact):
    assert artifact.get("next_task") == EXPECTED_NEXT_TASK, (
        f"next_task must be {EXPECTED_NEXT_TASK}. Got {artifact.get('next_task')}"
    )


def test_p175_p176_blocked(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


def test_p175_p176_auth_phrase(artifact):
    phrase = artifact.get("next_task_authorization_required_phrase", "")
    assert "P176" in phrase and len(phrase) > 10


# ── Forbidden strings ─────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p175_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, (
        f"Forbidden string in P175 JSON: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p175_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string in P175 MD: {forbidden!r}"
    )


# ── MD content ────────────────────────────────────────────────────────────

def test_p175_md_has_classification(md_text):
    assert EXPECTED_FINAL_CLASSIFICATION in md_text


def test_p175_md_has_four_candidates(md_text):
    for cid in ["C03", "C05", "C06", "C07"]:
        assert cid in md_text, f"MD must mention candidate {cid}"


def test_p175_md_has_703_pairs(md_text):
    assert "703" in md_text, "MD must document C(38,2)=703 pair space"


def test_p175_md_has_p176(md_text):
    assert EXPECTED_NEXT_TASK in md_text or "P176" in md_text


def test_p175_md_has_blocked(md_text):
    assert "BLOCKED" in md_text and "authorization" in md_text.lower()


def test_p175_md_no_false_edge(md_text):
    lower = md_text.lower()
    for s in ["method found", "success-rate method found", "edge confirmed"]:
        assert s not in lower, f"MD must not contain: {s!r}"


# ── Active task ────────────────────────────────────────────────────────────

def test_p175_active_task_p175_present(active_task_text):
    assert "P175" in active_task_text


def test_p175_active_task_p176_blocked(active_task_text):
    assert "P176" in active_task_text
    assert "blocked" in active_task_text.lower() or "BLOCKED" in active_task_text


def test_p175_active_task_no_false_success(active_task_text):
    lower = active_task_text.lower()
    for s in ["success-rate method found", "proven method"]:
        assert s not in lower, f"active_task.md must not contain: {s!r}"


# ── Roadmap ────────────────────────────────────────────────────────────────

def test_p175_roadmap_p175_present(roadmap_text):
    assert "P175" in roadmap_text


def test_p175_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method", "method found"]:
        assert s not in lower, f"roadmap.md must not contain: {s!r}"


# ── CTO Analysis ──────────────────────────────────────────────────────────

def test_p175_cto_mentions_p175(cto_text):
    assert "P175" in cto_text


def test_p175_cto_mentions_p176(cto_text):
    assert "P176" in cto_text


def test_p175_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge", "r2 edge confirmed"]:
        assert s not in lower, f"CTO-Analysis.md must not contain: {s!r}"


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p175_db_rows_unchanged():
    assert DB_PATH.exists()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS, f"DB rows changed: expected {EXPECTED_DB_ROWS}, got {n}"
