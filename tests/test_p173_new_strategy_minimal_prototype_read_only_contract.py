"""
Tests for P173: POWER_LOTTO New Strategy Minimal Prototype — Read-Only.
========================================================================
All tests are READ-ONLY. No DB writes, no staging checks.

Verifies:
  - Artifact existence (JSON + MD)
  - Final classification (NULL or SIGNAL_REVIEW)
  - Authorization phrase detected
  - Phase 0 PASS
  - Exactly 3 candidates (C01, C02, C04) with required stats fields
  - Multiple-testing correction: family_size=3, Bonferroni threshold=0.016667
  - Governance: no DB write, no registry, no controlled_apply, no champion, no betting advice
  - Next task is P174_POWER_LOTTO_R2_DECISION_REVIEW
  - P174 blocked by user authorization
  - active_task.md marks P174 blocked
  - No forbidden strings in JSON or MD
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
    / "p173_new_strategy_minimal_prototype_read_only_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p173_new_strategy_minimal_prototype_read_only_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_DB_ROWS = 94924
EXPECTED_NEXT_TASK = "P174_POWER_LOTTO_R2_DECISION_REVIEW"
EXPECTED_AUTHORIZATION_PHRASE = "YES start P173 POWER_LOTTO minimal prototype read-only"
VALID_FINAL_CLASSIFICATIONS = {
    "P173_POWER_LOTTO_R2_MINIMAL_PROTOTYPE_NULL_RESULT",
    "P173_POWER_LOTTO_R2_MINIMAL_PROTOTYPE_SIGNAL_REVIEW_REQUIRED",
}
EXPECTED_CANDIDATES = {"C01", "C02", "C04"}
EXPECTED_FAMILY_SIZE = 3
EXPECTED_BONFERRONI_THRESHOLD = 0.016667

FORBIDDEN_STRINGS = [
    "guaranteed win",
    "betting advice",
    "champion promoted",
    "controlled_apply authorized",
    "db migrated",
    "production deployment",
    "success-rate method found",
    "proven method",
    "edge found in r2",
    "r2 confirms edge",
    "r2 edge confirmed",
    "split resolved",
]


@pytest.fixture(scope="module")
def artifact():
    assert JSON_OUT.exists(), f"P173 JSON artifact missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P173 MD artifact missing: {MD_OUT}"
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

def test_p173_json_exists():
    assert JSON_OUT.exists(), f"P173 JSON artifact missing: {JSON_OUT}"


def test_p173_md_exists():
    assert MD_OUT.exists(), f"P173 MD artifact missing: {MD_OUT}"


# ── Classification and authorization ──────────────────────────────────────

def test_p173_final_classification_valid(artifact):
    cls = artifact.get("final_classification", "")
    assert cls in VALID_FINAL_CLASSIFICATIONS, (
        f"final_classification must be one of {VALID_FINAL_CLASSIFICATIONS}. Got: {cls!r}"
    )


def test_p173_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase, (
        f"Authorization phrase not detected. Got: {phrase!r}"
    )


def test_p173_phase0_pass(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("result") == "PASS", f"Phase 0 result: {phase0.get('result')}"


def test_p173_phase0_db_rows(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("db_rows") == EXPECTED_DB_ROWS, (
        f"Phase 0 DB rows: expected {EXPECTED_DB_ROWS}, got {phase0.get('db_rows')}"
    )


def test_p173_phase0_draws_present(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    n = phase0.get("draws_table_power_lotto_rows", 0)
    assert n > 0, f"Phase 0 draws table must have > 0 rows. Got {n}"


# ── P172 summary ───────────────────────────────────────────────────────────

def test_p173_p172_summary_present(artifact):
    assert "p172_summary" in artifact, "p172_summary missing"


def test_p173_p172_summary_classification(artifact):
    summary = artifact.get("p172_summary", {})
    assert "P172_POWER_LOTTO_NEW_STRATEGY_PROTOTYPE_PLAN_READY" in summary.get("classification", ""), (
        "p172_summary must reference P172 classification"
    )


# ── Candidate results ──────────────────────────────────────────────────────

def test_p173_candidate_results_present(artifact):
    assert "candidate_results" in artifact, "candidate_results missing"


def test_p173_exactly_three_candidates(artifact):
    results = artifact.get("candidate_results", {})
    # Check that exactly 3 candidates present
    c_keys = list(results.keys())
    assert len(c_keys) == 3, (
        f"candidate_results must have exactly 3 entries. Got {len(c_keys)}: {c_keys}"
    )


def test_p173_candidate_ids_correct(artifact):
    results = artifact.get("candidate_results", {})
    keys_str = " ".join(results.keys())
    for cid in ["C01", "C02", "C04"]:
        assert cid in keys_str, f"Candidate {cid} not found in candidate_results keys: {list(results.keys())}"


def test_p173_each_candidate_has_p_raw(artifact):
    results = artifact.get("candidate_results", {})
    for name, res in results.items():
        assert "p_raw" in res, f"Candidate {name} missing p_raw"
        assert 0.0 <= res["p_raw"] <= 1.0, f"Candidate {name} p_raw out of range: {res['p_raw']}"


def test_p173_each_candidate_has_p_bonferroni(artifact):
    results = artifact.get("candidate_results", {})
    for name, res in results.items():
        assert "p_bonferroni" in res, f"Candidate {name} missing p_bonferroni"
        assert 0.0 <= res["p_bonferroni"] <= 1.0, (
            f"Candidate {name} p_bonferroni out of range: {res['p_bonferroni']}"
        )


def test_p173_each_candidate_has_p_bh(artifact):
    results = artifact.get("candidate_results", {})
    for name, res in results.items():
        assert "p_bh" in res, f"Candidate {name} missing p_bh"


def test_p173_each_candidate_has_mean_hit_count(artifact):
    results = artifact.get("candidate_results", {})
    for name, res in results.items():
        assert "mean_hit_count" in res, f"Candidate {name} missing mean_hit_count"
        assert 0.0 <= res["mean_hit_count"] <= 6.0, (
            f"Candidate {name} mean_hit_count out of range: {res['mean_hit_count']}"
        )


def test_p173_each_candidate_has_result_status(artifact):
    results = artifact.get("candidate_results", {})
    valid_statuses = {"PASS_CORRECTED", "FAIL_CORRECTED", "INSUFFICIENT_DATA", "ERROR"}
    for name, res in results.items():
        status = res.get("result_status", "")
        assert status in valid_statuses, (
            f"Candidate {name} result_status must be one of {valid_statuses}. Got: {status!r}"
        )


def test_p173_each_candidate_has_n_oos_draws(artifact):
    results = artifact.get("candidate_results", {})
    for name, res in results.items():
        n = res.get("n_oos_draws", 0)
        assert n > 0, f"Candidate {name} n_oos_draws must be > 0. Got {n}"


# ── Multiple testing correction ───────────────────────────────────────────

def test_p173_multiple_testing_correction_present(artifact):
    assert "multiple_testing_correction" in artifact, "multiple_testing_correction missing"


def test_p173_family_size_is_3(artifact):
    mtc = artifact.get("multiple_testing_correction", {})
    assert mtc.get("family_size") == EXPECTED_FAMILY_SIZE, (
        f"family_size must be {EXPECTED_FAMILY_SIZE}. Got {mtc.get('family_size')}"
    )


def test_p173_bonferroni_threshold_correct(artifact):
    mtc = artifact.get("multiple_testing_correction", {})
    threshold = mtc.get("bonferroni_threshold", 0)
    assert abs(threshold - EXPECTED_BONFERRONI_THRESHOLD) < 0.0001, (
        f"bonferroni_threshold must be ~{EXPECTED_BONFERRONI_THRESHOLD}. Got {threshold}"
    )


def test_p173_bonferroni_consistent_with_family_size(artifact):
    mtc = artifact.get("multiple_testing_correction", {})
    alpha = mtc.get("alpha", 0.05)
    family = mtc.get("family_size", 3)
    threshold = mtc.get("bonferroni_threshold", 0)
    expected = alpha / family
    assert abs(threshold - expected) < 0.0001, (
        f"bonferroni_threshold ({threshold}) must equal alpha/family ({expected})"
    )


# ── Null reporting ────────────────────────────────────────────────────────

def test_p173_null_reporting_present(artifact):
    assert "null_reporting" in artifact, "null_reporting missing"


def test_p173_null_reporting_consistent_with_classification(artifact):
    cls = artifact.get("final_classification", "")
    null_rep = artifact.get("null_reporting", {})
    if "NULL_RESULT" in cls:
        assert null_rep.get("null_result") is True, (
            "null_reporting.null_result must be True when classification is NULL_RESULT"
        )
        assert null_rep.get("any_candidate_pass_corrected") is False, (
            "null_reporting.any_candidate_pass_corrected must be False for NULL_RESULT"
        )
    elif "SIGNAL_REVIEW" in cls:
        assert null_rep.get("any_candidate_pass_corrected") is True, (
            "null_reporting.any_candidate_pass_corrected must be True for SIGNAL_REVIEW"
        )


def test_p173_null_honest_statement_present(artifact):
    null_rep = artifact.get("null_reporting", {})
    stmt = null_rep.get("null_honest_statement", "")
    assert len(stmt) > 20, "null_reporting.null_honest_statement must be present and substantive"


# ── Governance confirmations ───────────────────────────────────────────────

def test_p173_no_db_write(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True, "no_db_write not confirmed"


def test_p173_no_registry_mutation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_registry_mutation") is True, "no_registry_mutation not confirmed"


def test_p173_no_strategy_implementation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_strategy_implementation") is True, (
        "no_strategy_implementation not confirmed"
    )


def test_p173_no_controlled_apply(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_controlled_apply") is True, "no_controlled_apply not confirmed"


def test_p173_no_champion_promotion(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_champion_promotion") is True, "no_champion_promotion not confirmed"


def test_p173_no_betting_advice(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_betting_advice") is True, "no_betting_advice not confirmed"


def test_p173_db_unchanged_in_governance(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("db_unchanged") is True, "governance_confirmations.db_unchanged must be True"
    assert gov.get("db_rows_before") == EXPECTED_DB_ROWS, (
        f"db_rows_before must be {EXPECTED_DB_ROWS}"
    )
    assert gov.get("db_rows_after") == EXPECTED_DB_ROWS, (
        f"db_rows_after must be {EXPECTED_DB_ROWS}"
    )


def test_p173_r1_null_results_stand(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p161_to_p172_null_results_stand") is True, (
        "p161_to_p172_null_results_stand must be True"
    )


# ── Next task ──────────────────────────────────────────────────────────────

def test_p173_next_task_is_p174(artifact):
    assert artifact.get("next_task") == EXPECTED_NEXT_TASK, (
        f"next_task must be {EXPECTED_NEXT_TASK}. Got {artifact.get('next_task')}"
    )


def test_p173_p174_blocked(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True, (
        "next_task_blocked_by_user_authorization must be True"
    )


def test_p173_p174_auth_phrase(artifact):
    phrase = artifact.get("next_task_authorization_required_phrase", "")
    assert "P174" in phrase and len(phrase) > 10, (
        f"next_task_authorization_required_phrase must mention P174. Got: {phrase!r}"
    )


# ── Forbidden strings ─────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p173_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, (
        f"Forbidden string found in P173 JSON: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p173_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P173 MD: {forbidden!r}"
    )


# ── MD content checks ─────────────────────────────────────────────────────

def test_p173_md_has_classification(md_text):
    has_null = "P173_POWER_LOTTO_R2_MINIMAL_PROTOTYPE_NULL_RESULT" in md_text
    has_signal = "P173_POWER_LOTTO_R2_MINIMAL_PROTOTYPE_SIGNAL_REVIEW_REQUIRED" in md_text
    assert has_null or has_signal, "MD must contain the final classification"


def test_p173_md_has_results_table(md_text):
    assert "FAIL_CORRECTED" in md_text or "PASS_CORRECTED" in md_text, (
        "MD must show candidate result statuses"
    )


def test_p173_md_has_null_statement(md_text):
    lower = md_text.lower()
    assert "null" in lower or "no candidate" in lower, (
        "MD must include NULL result statement"
    )


def test_p173_md_has_p174(md_text):
    assert "P174" in md_text, "MD must mention P174 as next task"


def test_p173_md_has_blocked(md_text):
    assert "BLOCKED" in md_text and "authorization" in md_text.lower(), (
        "MD must state P174 is BLOCKED pending user authorization"
    )


# ── Active task ────────────────────────────────────────────────────────────

def test_p173_active_task_p173_present(active_task_text):
    assert "P173" in active_task_text, "active_task.md must mention P173"


def test_p173_active_task_p174_blocked(active_task_text):
    assert "P174" in active_task_text, "active_task.md must mention P174"
    assert (
        "blocked" in active_task_text.lower()
        or "BLOCKED" in active_task_text
        or "authorization" in active_task_text.lower()
    ), "active_task.md must indicate P174 is blocked"


def test_p173_active_task_no_false_success(active_task_text):
    lower = active_task_text.lower()
    for s in ["success-rate method found", "proven method"]:
        assert s not in lower, f"active_task.md must not contain: {s!r}"


# ── Roadmap ────────────────────────────────────────────────────────────────

def test_p173_roadmap_p173_present(roadmap_text):
    assert "P173" in roadmap_text, "roadmap.md must mention P173"


def test_p173_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method"]:
        assert s not in lower, f"roadmap.md must not contain: {s!r}"


# ── CTO Analysis ──────────────────────────────────────────────────────────

def test_p173_cto_mentions_p173(cto_text):
    assert "P173" in cto_text, "CTO-Analysis.md must mention P173"


def test_p173_cto_mentions_p174(cto_text):
    assert "P174" in cto_text, "CTO-Analysis.md must mention P174"


def test_p173_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge", "r2 edge confirmed"]:
        assert s not in lower, f"CTO-Analysis.md must not contain: {s!r}"


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p173_db_rows_unchanged():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays;"
    ).fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS, f"DB rows changed: expected {EXPECTED_DB_ROWS}, got {n}"
