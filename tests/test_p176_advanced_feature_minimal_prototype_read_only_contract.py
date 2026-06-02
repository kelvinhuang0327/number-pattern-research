"""
Tests for P176: POWER_LOTTO R2 Advanced Feature Minimal Prototype — Read-Only.
===============================================================================
All tests READ-ONLY. No DB writes.

Verifies:
  - Artifact existence (JSON + MD)
  - final_classification valid (NULL or SIGNAL_REVIEW)
  - Authorization phrase detected
  - Phase 0 PASS
  - candidate_results exactly C03/C05/C06/C07
  - Each candidate has n_oos, mean_hit_count, p_raw, p_bonferroni, corrected_status, leakage_check
  - family_size=4 and bonferroni_threshold=0.0125
  - leakage_audit covers C03/C05/C06/C07
  - Governance: no DB write, no registry, no controlled_apply, no champion, no wagering
  - next_task = P177_...
  - P177 blocked by user authorization
  - active_task.md marks P177 BLOCKED
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
    / "p176_advanced_feature_minimal_prototype_read_only_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p176_advanced_feature_minimal_prototype_read_only_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_DB_ROWS = 94924
EXPECTED_AUTHORIZATION_PHRASE = "YES start P176 POWER_LOTTO R2 advanced feature minimal prototype read-only"
VALID_FINAL_CLASSIFICATIONS = {
    "P176_POWER_LOTTO_R2_ADVANCED_FEATURE_NULL_RESULT",
    "P176_POWER_LOTTO_R2_ADVANCED_FEATURE_SIGNAL_REQUIRES_REVIEW",
}
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
    assert JSON_OUT.exists(), f"P176 JSON missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P176 MD missing: {MD_OUT}"
    return MD_OUT.read_text()


@pytest.fixture(scope="module")
def active_task_text():
    assert ACTIVE_TASK.exists()
    return ACTIVE_TASK.read_text()


@pytest.fixture(scope="module")
def roadmap_text():
    assert ROADMAP.exists()
    return ROADMAP.read_text()


@pytest.fixture(scope="module")
def cto_text():
    assert CTO_ANALYSIS.exists()
    return CTO_ANALYSIS.read_text()


# ── Artifact existence ─────────────────────────────────────────────────────

def test_p176_json_exists():
    assert JSON_OUT.exists()


def test_p176_md_exists():
    assert MD_OUT.exists()


# ── Classification ─────────────────────────────────────────────────────────

def test_p176_final_classification_valid(artifact):
    cls = artifact.get("final_classification", "")
    assert cls in VALID_FINAL_CLASSIFICATIONS, (
        f"final_classification must be one of {VALID_FINAL_CLASSIFICATIONS}. Got: {cls!r}"
    )


def test_p176_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase


def test_p176_phase0_pass(artifact):
    assert artifact.get("phase_0_verification", {}).get("result") == "PASS"


def test_p176_phase0_db_rows(artifact):
    assert artifact.get("phase_0_verification", {}).get("db_rows") == EXPECTED_DB_ROWS


# ── Candidate results ──────────────────────────────────────────────────────

def test_p176_candidate_results_present(artifact):
    assert "candidate_results" in artifact


def test_p176_exactly_four_candidates(artifact):
    results = artifact.get("candidate_results", {})
    assert len(results) == 4, f"Must have 4 candidates. Got {len(results)}"


def test_p176_candidate_ids_correct(artifact):
    results = artifact.get("candidate_results", {})
    keys = set(results.keys())
    assert keys == EXPECTED_CANDIDATES, (
        f"Candidate IDs must be {EXPECTED_CANDIDATES}. Got {keys}"
    )


def test_p176_each_candidate_has_n_oos(artifact):
    for name, res in artifact.get("candidate_results", {}).items():
        assert "n_oos" in res and res["n_oos"] > 0, f"{name} missing n_oos"


def test_p176_each_candidate_has_mean_hit_count(artifact):
    for name, res in artifact.get("candidate_results", {}).items():
        assert "mean_hit_count" in res, f"{name} missing mean_hit_count"
        assert 0.0 <= res["mean_hit_count"] <= 6.0, f"{name} mean_hit_count out of range"


def test_p176_each_candidate_has_p_raw(artifact):
    for name, res in artifact.get("candidate_results", {}).items():
        assert "p_raw" in res and 0.0 <= res["p_raw"] <= 1.0, f"{name} p_raw invalid"


def test_p176_each_candidate_has_p_bonferroni(artifact):
    for name, res in artifact.get("candidate_results", {}).items():
        assert "p_bonferroni" in res and 0.0 <= res["p_bonferroni"] <= 1.0, (
            f"{name} p_bonferroni invalid"
        )


def test_p176_each_candidate_has_corrected_status(artifact):
    valid = {"PASS_CORRECTED", "FAIL_CORRECTED", "INSUFFICIENT_DATA", "ERROR"}
    for name, res in artifact.get("candidate_results", {}).items():
        assert res.get("corrected_status") in valid, (
            f"{name} corrected_status must be one of {valid}"
        )


def test_p176_each_candidate_has_leakage_check(artifact):
    for name, res in artifact.get("candidate_results", {}).items():
        assert "leakage_check" in res, f"{name} missing leakage_check"


def test_p176_c03_has_pair_space_note(artifact):
    c03 = artifact.get("candidate_results", {}).get("C03", {})
    note = c03.get("pair_space_burden_note", "")
    assert "703" in note, f"C03 must document 703 pair-space burden. Got: {note!r}"


def test_p176_c06_has_no_future_labels(artifact):
    c06 = artifact.get("candidate_results", {}).get("C06", {})
    assert c06.get("no_future_labels") or "causal" in c06.get("leakage_check", "").lower(), (
        "C06 must confirm no future labels"
    )


# ── Multiple testing ───────────────────────────────────────────────────────

def test_p176_multiple_testing_result_present(artifact):
    assert "multiple_testing_result" in artifact


def test_p176_family_size_4(artifact):
    mtr = artifact.get("multiple_testing_result", {})
    assert mtr.get("family_size") == EXPECTED_FAMILY_SIZE


def test_p176_bonferroni_threshold_0125(artifact):
    mtr = artifact.get("multiple_testing_result", {})
    threshold = mtr.get("bonferroni_threshold", 0)
    assert abs(threshold - EXPECTED_BONFERRONI_THRESHOLD) < 0.0001


def test_p176_bonferroni_consistent(artifact):
    mtr = artifact.get("multiple_testing_result", {})
    assert abs(mtr.get("bonferroni_threshold", 0) - mtr.get("alpha", 0.05) / mtr.get("family_size", 4)) < 0.0001


def test_p176_null_consistent_with_classification(artifact):
    cls = artifact.get("final_classification", "")
    mtr = artifact.get("multiple_testing_result", {})
    if "NULL" in cls:
        assert mtr.get("any_pass_corrected") is False
    elif "SIGNAL" in cls:
        assert mtr.get("any_pass_corrected") is True


# ── Leakage audit ─────────────────────────────────────────────────────────

def test_p176_leakage_audit_present(artifact):
    assert "leakage_audit" in artifact


def test_p176_leakage_audit_covers_all_candidates(artifact):
    la = artifact.get("leakage_audit", {})
    for cid in EXPECTED_CANDIDATES:
        assert cid in la, f"leakage_audit missing {cid}"


# ── Governance ─────────────────────────────────────────────────────────────

def test_p176_no_db_write(artifact):
    assert artifact.get("governance_confirmations", {}).get("no_db_write") is True


def test_p176_no_registry_mutation(artifact):
    assert artifact.get("governance_confirmations", {}).get("no_registry_mutation") is True


def test_p176_no_controlled_apply(artifact):
    assert artifact.get("governance_confirmations", {}).get("no_controlled_apply") is True


def test_p176_no_champion_promotion(artifact):
    assert artifact.get("governance_confirmations", {}).get("no_champion_promotion") is True


def test_p176_no_wagering(artifact):
    assert artifact.get("governance_confirmations", {}).get("no_wagering_recommendations") is True


def test_p176_db_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("db_unchanged") is True
    assert gov.get("db_rows_before") == EXPECTED_DB_ROWS
    assert gov.get("db_rows_after") == EXPECTED_DB_ROWS


def test_p176_null_results_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p173_null_unchanged") is True
    assert gov.get("p161_to_p175_null_results_unchanged") is True


# ── Next task ──────────────────────────────────────────────────────────────

def test_p176_next_task_is_p177(artifact):
    next_task = artifact.get("next_task", "")
    assert "P177" in next_task, f"next_task must mention P177. Got: {next_task!r}"


def test_p176_p177_blocked(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


def test_p176_p177_auth_phrase(artifact):
    phrase = artifact.get("next_task_authorization_required_phrase", "")
    assert "P177" in phrase and len(phrase) > 10


# ── Forbidden strings ─────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p176_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, f"Forbidden in JSON: {forbidden!r}"


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p176_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), f"Forbidden in MD: {forbidden!r}"


# ── MD content ────────────────────────────────────────────────────────────

def test_p176_md_has_classification(md_text):
    has_null = "P176_POWER_LOTTO_R2_ADVANCED_FEATURE_NULL_RESULT" in md_text
    has_signal = "P176_POWER_LOTTO_R2_ADVANCED_FEATURE_SIGNAL_REQUIRES_REVIEW" in md_text
    assert has_null or has_signal


def test_p176_md_has_all_candidates(md_text):
    for cid in EXPECTED_CANDIDATES:
        assert cid in md_text, f"MD must mention {cid}"


def test_p176_md_has_p177(md_text):
    assert "P177" in md_text


def test_p176_md_has_blocked(md_text):
    assert "BLOCKED" in md_text


# ── Active task ────────────────────────────────────────────────────────────

def test_p176_active_task_p176_present(active_task_text):
    assert "P176" in active_task_text


def test_p176_active_task_p177_blocked(active_task_text):
    assert "P177" in active_task_text
    assert "blocked" in active_task_text.lower() or "BLOCKED" in active_task_text


# ── Roadmap / CTO ──────────────────────────────────────────────────────────

def test_p176_roadmap_p176_present(roadmap_text):
    assert "P176" in roadmap_text


def test_p176_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method", "method found"]:
        assert s not in lower, f"roadmap.md must not contain: {s!r}"


def test_p176_cto_mentions_p176(cto_text):
    assert "P176" in cto_text


def test_p176_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge"]:
        assert s not in lower, f"CTO must not contain: {s!r}"


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p176_db_rows_unchanged():
    assert DB_PATH.exists()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS
