"""
Tests for P177: POWER_LOTTO R2 Closure Decision Review.
========================================================
All tests READ-ONLY. No DB writes.

Verifies:
  - Artifacts exist (JSON + MD)
  - final_classification = P177_POWER_LOTTO_R2_CLOSURE_DECISION_REVIEW_READY
  - authorization phrase detected
  - Phase 0 PASS
  - P176 classification referenced
  - cumulative strategies evaluated = 17
  - corrected-significant count = 0
  - evidence_summary covers P161/P167/P170/P173/P176
  - decision options A/B/C/D present
  - Option A recommended, Option D NOT_RECOMMENDED
  - Honest language requirements present
  - Authorization options / CEO gate present
  - Governance: no DB write, no registry, no controlled_apply, no champion, no wagering
  - active_task.md: next task BLOCKED
  - roadmap/CTO-Analysis include P177
  - No forbidden strings
  - DB rows unchanged = 94924
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
    / "p177_r2_closure_decision_review_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p177_r2_closure_decision_review_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_FINAL_CLASSIFICATION = "P177_POWER_LOTTO_R2_CLOSURE_DECISION_REVIEW_READY"
EXPECTED_DB_ROWS = 94924
EXPECTED_AUTHORIZATION_PHRASE = "YES start P177 POWER_LOTTO R2 closure decision review"
EXPECTED_CUMULATIVE_STRATEGIES = 17
EXPECTED_PASS_CORRECTED = 0

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
    assert JSON_OUT.exists(), f"P177 JSON missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P177 MD missing: {MD_OUT}"
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

def test_p177_json_exists():
    assert JSON_OUT.exists()


def test_p177_md_exists():
    assert MD_OUT.exists()


# ── Classification and authorization ──────────────────────────────────────

def test_p177_final_classification(artifact):
    assert artifact.get("final_classification") == EXPECTED_FINAL_CLASSIFICATION, (
        f"Expected {EXPECTED_FINAL_CLASSIFICATION}, got {artifact.get('final_classification')}"
    )


def test_p177_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase


def test_p177_phase0_pass(artifact):
    assert artifact.get("phase_0_verification", {}).get("result") == "PASS"


def test_p177_phase0_db_rows(artifact):
    assert artifact.get("phase_0_verification", {}).get("db_rows") == EXPECTED_DB_ROWS


# ── P176 reference ─────────────────────────────────────────────────────────

def test_p177_p176_summary_present(artifact):
    assert "p176_summary" in artifact, "p176_summary missing"


def test_p177_p176_classification_referenced(artifact):
    summary = artifact.get("p176_summary", {})
    assert "P176_POWER_LOTTO_R2_ADVANCED_FEATURE_NULL_RESULT" in summary.get("classification", ""), (
        "p176_summary must reference P176 exact classification"
    )


# ── Executive summary ──────────────────────────────────────────────────────

def test_p177_executive_summary_present(artifact):
    assert "executive_summary" in artifact


def test_p177_cumulative_strategies_17(artifact):
    es = artifact.get("executive_summary", {})
    count = es.get("cumulative_strategies_evaluated", 0)
    assert count == EXPECTED_CUMULATIVE_STRATEGIES, (
        f"cumulative_strategies_evaluated must be {EXPECTED_CUMULATIVE_STRATEGIES}. Got {count}"
    )


def test_p177_corrected_significant_zero(artifact):
    es = artifact.get("executive_summary", {})
    count = es.get("corrected_significant_oos_edge_count", -1)
    assert count == EXPECTED_PASS_CORRECTED, (
        f"corrected_significant_oos_edge_count must be {EXPECTED_PASS_CORRECTED}. Got {count}"
    )


def test_p177_r1_result_no_edge(artifact):
    es = artifact.get("executive_summary", {})
    assert "NO_DEFENSIBLE_EDGE" in es.get("r1_result", ""), "r1_result must state NO_DEFENSIBLE_EDGE"


def test_p177_r2_result_null(artifact):
    es = artifact.get("executive_summary", {})
    assert "NULL" in es.get("r2_result", ""), "r2_result must state NULL"


def test_p177_null_is_not_process_failure(artifact):
    es = artifact.get("executive_summary", {})
    assert es.get("null_is_process_failure") is False, (
        "executive_summary.null_is_process_failure must be False"
    )


# ── Evidence summary ───────────────────────────────────────────────────────

def test_p177_evidence_summary_present(artifact):
    assert "evidence_summary" in artifact


def test_p177_evidence_summary_has_p161(artifact):
    ev = artifact.get("evidence_summary", [])
    tasks = [e.get("task", "") for e in ev]
    assert any("P161" in t for t in tasks), "evidence_summary must include P161"


def test_p177_evidence_summary_has_p167(artifact):
    ev = artifact.get("evidence_summary", [])
    tasks = [e.get("task", "") for e in ev]
    assert any("P167" in t for t in tasks), "evidence_summary must include P167"


def test_p177_evidence_summary_has_p170(artifact):
    ev = artifact.get("evidence_summary", [])
    tasks = [e.get("task", "") for e in ev]
    assert any("P170" in t for t in tasks), "evidence_summary must include P170"


def test_p177_evidence_summary_has_p173(artifact):
    ev = artifact.get("evidence_summary", [])
    tasks = [e.get("task", "") for e in ev]
    assert any("P173" in t for t in tasks), "evidence_summary must include P173"


def test_p177_evidence_summary_has_p176(artifact):
    ev = artifact.get("evidence_summary", [])
    tasks = [e.get("task", "") for e in ev]
    assert any("P176" in t for t in tasks), "evidence_summary must include P176"


def test_p177_evidence_cumulative_total_17(artifact):
    ev = artifact.get("evidence_summary", [])
    cumulative_entries = [e for e in ev if "cumulative" in e.get("research_phase", "").lower() or
                          "total" in e.get("research_phase", "").lower() or
                          e.get("strategies_or_candidates", 0) == EXPECTED_CUMULATIVE_STRATEGIES]
    assert any(e.get("strategies_or_candidates") == EXPECTED_CUMULATIVE_STRATEGIES for e in ev), (
        "evidence_summary must include a cumulative entry with 17 strategies"
    )


# ── Decision options ───────────────────────────────────────────────────────

def test_p177_decision_options_present(artifact):
    assert "decision_options" in artifact


def test_p177_four_decision_options(artifact):
    options = artifact.get("decision_options", [])
    ids = {o.get("option_id") for o in options}
    for oid in ["A", "B", "C", "D"]:
        assert oid in ids, f"decision_options must include Option {oid}"


def test_p177_option_a_recommended(artifact):
    options = artifact.get("decision_options", [])
    opt_a = next((o for o in options if o.get("option_id") == "A"), None)
    assert opt_a is not None, "Option A missing"
    status = opt_a.get("recommendation_status", "").upper()
    assert "RECOMMEND" in status, f"Option A must be RECOMMENDED. Got: {status!r}"


def test_p177_option_d_not_recommended(artifact):
    options = artifact.get("decision_options", [])
    opt_d = next((o for o in options if o.get("option_id") == "D"), None)
    assert opt_d is not None, "Option D missing"
    status = opt_d.get("recommendation_status", "").upper()
    assert "NOT_RECOMMENDED" in status or "NOT RECOMMENDED" in status, (
        f"Option D must be NOT_RECOMMENDED. Got: {status!r}"
    )


def test_p177_option_a_has_rationale(artifact):
    options = artifact.get("decision_options", [])
    opt_a = next((o for o in options if o.get("option_id") == "A"), None)
    assert opt_a and len(opt_a.get("rationale", "")) > 20


def test_p177_option_a_formally_close(artifact):
    options = artifact.get("decision_options", [])
    opt_a = next((o for o in options if o.get("option_id") == "A"), None)
    assert opt_a
    label = opt_a.get("label", "").upper()
    desc = opt_a.get("description", "").lower()
    assert "close" in label or "close" in desc or "formally" in desc, (
        "Option A must involve formally closing research"
    )


# ── CTO recommendation ────────────────────────────────────────────────────

def test_p177_cto_recommendation_present(artifact):
    assert "cto_recommendation" in artifact


def test_p177_cto_recommends_close(artifact):
    cto = artifact.get("cto_recommendation", {})
    primary = cto.get("primary", "").lower()
    assert "close" in primary or "a" in primary.lower(), (
        "CTO primary recommendation must favor Option A (close)"
    )


# ── CEO decision gate ─────────────────────────────────────────────────────

def test_p177_ceo_gate_present(artifact):
    assert "ceo_decision_gate" in artifact or "authorization_options" in artifact


def test_p177_authorization_options_present(artifact):
    opts = artifact.get("authorization_options") or artifact.get("ceo_decision_gate", {}).get("authorization_options", [])
    assert len(opts) >= 3, "Must have at least 3 authorization options"


def test_p177_authorization_option_a_close(artifact):
    opts = artifact.get("authorization_options") or []
    if not opts:
        opts = [o.get("phrase", "") for o in artifact.get("ceo_decision_gate", {}).get("authorization_options", [])]
    close_opts = [o for o in opts if "close" in str(o).lower() or "archive" in str(o).lower()]
    assert close_opts, "Must have an authorization option for closing R2"


# ── Honest language ────────────────────────────────────────────────────────

def test_p177_honest_language_present(artifact):
    assert "honest_language_requirements" in artifact


def test_p177_honest_language_null_not_failure(artifact):
    hl = artifact.get("honest_language_requirements", {})
    stmt = hl.get("null_is_not_process_failure", "")
    assert len(stmt) > 10, "honest_language_requirements.null_is_not_process_failure must be present"


def test_p177_honest_language_no_win_guarantee(artifact):
    hl = artifact.get("honest_language_requirements", {})
    stmt = hl.get("no_win_guarantee", "")
    assert len(stmt) > 10, "honest_language_requirements.no_win_guarantee must be present"


# ── Governance ─────────────────────────────────────────────────────────────

def test_p177_no_db_write(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True


def test_p177_no_registry_mutation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_registry_mutation") is True


def test_p177_no_controlled_apply(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_controlled_apply") is True


def test_p177_no_champion_promotion(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_champion_promotion") is True


def test_p177_no_wagering(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_wagering_recommendations") is True


def test_p177_db_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("db_unchanged") is True
    assert gov.get("db_rows_before") == EXPECTED_DB_ROWS
    assert gov.get("db_rows_after") == EXPECTED_DB_ROWS


def test_p177_p176_null_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p176_null_unchanged") is True


# ── Forbidden strings ─────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p177_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, f"Forbidden in JSON: {forbidden!r}"


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p177_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), f"Forbidden in MD: {forbidden!r}"


# ── MD content ────────────────────────────────────────────────────────────

def test_p177_md_has_classification(md_text):
    assert EXPECTED_FINAL_CLASSIFICATION in md_text


def test_p177_md_has_17_strategies(md_text):
    assert "17" in md_text, "MD must mention cumulative 17 strategies"


def test_p177_md_has_option_a_recommended(md_text):
    lower = md_text.lower()
    assert "option a" in lower and "recommend" in lower


def test_p177_md_has_option_d_not_recommended(md_text):
    lower = md_text.lower()
    assert "option d" in lower and "not recommended" in lower


def test_p177_md_has_ceo_gate(md_text):
    assert "CEO" in md_text or "authorization" in md_text.lower()


# ── Active task ────────────────────────────────────────────────────────────

def test_p177_active_task_p177_present(active_task_text):
    assert "P177" in active_task_text


def test_p177_active_task_next_blocked(active_task_text):
    lower = active_task_text.lower()
    assert "blocked" in lower or "authorization" in lower


# ── Roadmap / CTO ──────────────────────────────────────────────────────────

def test_p177_roadmap_p177_present(roadmap_text):
    assert "P177" in roadmap_text


def test_p177_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method", "method found"]:
        assert s not in lower, f"roadmap.md must not contain: {s!r}"


def test_p177_cto_mentions_p177(cto_text):
    assert "P177" in cto_text


def test_p177_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge"]:
        assert s not in lower, f"CTO must not contain: {s!r}"


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p177_db_rows_unchanged():
    assert DB_PATH.exists()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS
