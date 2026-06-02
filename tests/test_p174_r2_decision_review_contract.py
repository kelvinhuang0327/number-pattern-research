"""
Tests for P174: POWER_LOTTO R2 Decision Review.
================================================
All tests are READ-ONLY. No DB writes, no staging checks.

Verifies:
  - Artifact existence (JSON + MD)
  - final_classification = P174_POWER_LOTTO_R2_DECISION_REVIEW_READY
  - Authorization phrase detected
  - Phase 0 PASS
  - p173_summary: P173 NULL, C01/C02/C04 all FAIL_CORRECTED
  - options_reviewed: at least 5 options (A/B/C/D/E)
  - recommended_option = Option B plan-only (or equivalent conservative recommendation)
  - next_task = P175_POWER_LOTTO_R2_ADVANCED_FEATURE_CANDIDATE_PLAN_ONLY
  - P175 blocked by user authorization
  - governance: no DB write, no registry, no controlled_apply, no champion, no wagering
  - active_task.md: P175 BLOCKED
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
    / "p174_r2_decision_review_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p174_r2_decision_review_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_FINAL_CLASSIFICATION = "P174_POWER_LOTTO_R2_DECISION_REVIEW_READY"
EXPECTED_DB_ROWS = 94924
EXPECTED_NEXT_TASK = "P175_POWER_LOTTO_R2_ADVANCED_FEATURE_CANDIDATE_PLAN_ONLY"
EXPECTED_AUTHORIZATION_PHRASE = "YES start P174 POWER_LOTTO R2 decision review"
MIN_OPTIONS = 5

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
    assert JSON_OUT.exists(), f"P174 JSON artifact missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P174 MD artifact missing: {MD_OUT}"
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

def test_p174_json_exists():
    assert JSON_OUT.exists(), f"P174 JSON artifact missing: {JSON_OUT}"


def test_p174_md_exists():
    assert MD_OUT.exists(), f"P174 MD artifact missing: {MD_OUT}"


# ── Classification and authorization ──────────────────────────────────────

def test_p174_final_classification(artifact):
    assert artifact.get("final_classification") == EXPECTED_FINAL_CLASSIFICATION, (
        f"Expected {EXPECTED_FINAL_CLASSIFICATION}, got {artifact.get('final_classification')}"
    )


def test_p174_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase, (
        f"Authorization phrase not detected. Got: {phrase!r}"
    )


def test_p174_phase0_pass(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("result") == "PASS", f"Phase 0: {phase0.get('result')}"


def test_p174_phase0_db_rows(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("db_rows") == EXPECTED_DB_ROWS, (
        f"Phase 0 DB rows: expected {EXPECTED_DB_ROWS}, got {phase0.get('db_rows')}"
    )


# ── P173 summary ───────────────────────────────────────────────────────────

def test_p174_p173_summary_present(artifact):
    assert "p173_summary" in artifact, "p173_summary missing"


def test_p174_p173_summary_null_classification(artifact):
    summary = artifact.get("p173_summary", {})
    cls = summary.get("classification", "")
    assert "P173_POWER_LOTTO_R2_MINIMAL_PROTOTYPE_NULL_RESULT" in cls, (
        f"p173_summary must show NULL classification. Got: {cls!r}"
    )


def test_p174_p173_summary_all_fail_corrected(artifact):
    summary = artifact.get("p173_summary", {})
    assert summary.get("all_fail_corrected") is True, (
        "p173_summary.all_fail_corrected must be True"
    )


def test_p174_p173_summary_has_c01_c02_c04(artifact):
    summary = artifact.get("p173_summary", {})
    results = summary.get("results", {})
    keys_str = " ".join(results.keys())
    for cid in ["C01", "C02", "C04"]:
        assert cid in keys_str, f"p173_summary.results missing {cid}: {list(results.keys())}"


def test_p174_p173_summary_each_fail_corrected(artifact):
    summary = artifact.get("p173_summary", {})
    results = summary.get("results", {})
    for name, res in results.items():
        assert res.get("result_status") == "FAIL_CORRECTED", (
            f"p173_summary result {name} must be FAIL_CORRECTED. Got: {res.get('result_status')}"
        )


def test_p174_p173_summary_n_oos(artifact):
    summary = artifact.get("p173_summary", {})
    n_oos = summary.get("n_oos", 0)
    assert n_oos > 0, f"p173_summary.n_oos must be > 0. Got {n_oos}"


def test_p174_p173_no_edge_found(artifact):
    summary = artifact.get("p173_summary", {})
    assert summary.get("no_edge_found") is True, "p173_summary.no_edge_found must be True"


def test_p174_p173_not_process_failure(artifact):
    summary = artifact.get("p173_summary", {})
    assert summary.get("is_process_failure") is False, (
        "p173_summary.is_process_failure must be False"
    )


# ── Options reviewed ───────────────────────────────────────────────────────

def test_p174_options_reviewed_present(artifact):
    assert "options_reviewed" in artifact, "options_reviewed missing"


def test_p174_options_reviewed_minimum_count(artifact):
    options = artifact.get("options_reviewed", [])
    assert len(options) >= MIN_OPTIONS, (
        f"options_reviewed must have >= {MIN_OPTIONS} options. Got {len(options)}"
    )


def test_p174_options_include_a_b_c_d_e(artifact):
    options = artifact.get("options_reviewed", [])
    ids = [o.get("option_id", "") for o in options]
    for oid in ["A", "B", "C", "D", "E"]:
        assert oid in ids, f"options_reviewed missing option {oid}. Present: {ids}"


def test_p174_each_option_has_name(artifact):
    options = artifact.get("options_reviewed", [])
    for o in options:
        assert "name" in o and len(o["name"]) > 5, (
            f"Option {o.get('option_id')} missing or too-short name"
        )


def test_p174_each_option_has_pros_cons(artifact):
    options = artifact.get("options_reviewed", [])
    for o in options:
        assert "pros" in o or "cons" in o, (
            f"Option {o.get('option_id')} must have pros or cons"
        )


def test_p174_each_option_has_recommendation_status(artifact):
    options = artifact.get("options_reviewed", [])
    for o in options:
        assert "recommendation_status" in o, (
            f"Option {o.get('option_id')} missing recommendation_status"
        )


# ── Recommended option ────────────────────────────────────────────────────

def test_p174_recommended_option_present(artifact):
    assert "recommended_option" in artifact, "recommended_option missing"


def test_p174_recommended_option_is_b_plan_only(artifact):
    rec = artifact.get("recommended_option", {})
    primary = rec.get("primary", "")
    label = rec.get("label", "").lower()
    rationale = rec.get("rationale", "").lower()
    assert primary == "B" or "plan-only" in label or "plan only" in label or "plan" in rationale, (
        f"recommended_option must be Option B plan-only or equivalent. Got primary={primary!r}"
    )


def test_p174_recommended_option_has_conservative_caveat(artifact):
    rec = artifact.get("recommended_option", {})
    caveat = rec.get("conservative_caveat", "")
    assert len(caveat) > 20, "recommended_option must have a conservative_caveat"
    lower = caveat.lower()
    assert (
        "low" in lower or "null" in lower or "prior probability" in lower or "does not" in lower
    ), "conservative_caveat must acknowledge low prior probability or null evidence"


# ── P175 scope boundary ───────────────────────────────────────────────────

def test_p174_p175_scope_present(artifact):
    assert "p175_scope_boundary" in artifact, "p175_scope_boundary missing"


def test_p174_p175_task_name(artifact):
    boundary = artifact.get("p175_scope_boundary", {})
    task = boundary.get("task_name", "")
    assert EXPECTED_NEXT_TASK in task, (
        f"p175_scope_boundary.task_name must be {EXPECTED_NEXT_TASK}. Got: {task!r}"
    )


def test_p174_p175_candidate_set_has_four(artifact):
    boundary = artifact.get("p175_scope_boundary", {})
    candidates = boundary.get("candidate_set", [])
    assert len(candidates) == 4, (
        f"p175_scope_boundary.candidate_set must have 4 items. Got {len(candidates)}"
    )


def test_p174_p175_scope_plan_only(artifact):
    boundary = artifact.get("p175_scope_boundary", {})
    scope = boundary.get("scope", "").lower()
    assert "plan" in scope and ("no prototype" in scope or "no db" in scope or "no training" in scope), (
        f"p175_scope_boundary.scope must indicate plan-only. Got: {scope!r}"
    )


def test_p174_p175_boundary_forbidden_prototype(artifact):
    boundary = artifact.get("p175_scope_boundary", {})
    forbidden = " ".join(boundary.get("forbidden_in_p175", [])).lower()
    assert "prototype" in forbidden or "db write" in forbidden or "training" in forbidden, (
        "p175_scope_boundary.forbidden_in_p175 must prohibit prototype/DB write/training"
    )


def test_p174_p175_authorization_required(artifact):
    boundary = artifact.get("p175_scope_boundary", {})
    assert boundary.get("p175_authorization_required") is True, (
        "p175_scope_boundary.p175_authorization_required must be True"
    )
    assert boundary.get("p175_blocked_by_user_authorization") is True, (
        "p175_scope_boundary.p175_blocked_by_user_authorization must be True"
    )


# ── Governance ─────────────────────────────────────────────────────────────

def test_p174_no_db_write(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True, "no_db_write not confirmed"


def test_p174_no_registry_mutation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_registry_mutation") is True, "no_registry_mutation not confirmed"


def test_p174_no_strategy_implementation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_strategy_implementation") is True, (
        "no_strategy_implementation not confirmed"
    )


def test_p174_no_controlled_apply(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_controlled_apply") is True, "no_controlled_apply not confirmed"


def test_p174_no_champion_promotion(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_champion_promotion") is True, "no_champion_promotion not confirmed"


def test_p174_no_wagering(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_wagering_recommendations") is True, (
        "no_wagering_recommendations not confirmed"
    )


def test_p174_db_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("db_unchanged") is True, "db_unchanged must be True"
    assert gov.get("db_rows_before") == EXPECTED_DB_ROWS
    assert gov.get("db_rows_after") == EXPECTED_DB_ROWS


def test_p174_p173_null_stands(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p173_null_result_stands") is True, (
        "p173_null_result_stands must be True"
    )


def test_p174_all_null_results_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p161_to_p173_null_results_unchanged") is True, (
        "p161_to_p173_null_results_unchanged must be True"
    )


# ── Next task ──────────────────────────────────────────────────────────────

def test_p174_next_task_is_p175(artifact):
    assert artifact.get("next_task") == EXPECTED_NEXT_TASK, (
        f"next_task must be {EXPECTED_NEXT_TASK}. Got {artifact.get('next_task')}"
    )


def test_p174_p175_blocked(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True, (
        "next_task_blocked_by_user_authorization must be True"
    )


def test_p174_p175_auth_phrase(artifact):
    phrase = artifact.get("next_task_authorization_required_phrase", "")
    assert "P175" in phrase and len(phrase) > 10, (
        f"next_task_authorization_required_phrase must mention P175. Got: {phrase!r}"
    )


# ── Forbidden strings ─────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p174_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, (
        f"Forbidden string found in P174 JSON: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p174_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P174 MD: {forbidden!r}"
    )


# ── MD content checks ─────────────────────────────────────────────────────

def test_p174_md_has_classification(md_text):
    assert EXPECTED_FINAL_CLASSIFICATION in md_text, (
        f"MD must contain {EXPECTED_FINAL_CLASSIFICATION}"
    )


def test_p174_md_has_five_options(md_text):
    for opt in ["Option A", "Option B", "Option C", "Option D", "Option E"]:
        assert opt in md_text, f"MD must mention {opt}"


def test_p174_md_has_p175(md_text):
    assert EXPECTED_NEXT_TASK in md_text or "P175" in md_text, (
        "MD must mention P175"
    )


def test_p174_md_has_blocked(md_text):
    assert "BLOCKED" in md_text and "authorization" in md_text.lower(), (
        "MD must state P175 is BLOCKED"
    )


def test_p174_md_no_false_edge_claim(md_text):
    lower = md_text.lower()
    for s in ["method found", "success-rate method found", "edge confirmed"]:
        assert s not in lower, f"MD must not contain: {s!r}"


# ── Active task ────────────────────────────────────────────────────────────

def test_p174_active_task_p174_present(active_task_text):
    assert "P174" in active_task_text, "active_task.md must mention P174"


def test_p174_active_task_p175_blocked(active_task_text):
    assert "P175" in active_task_text, "active_task.md must mention P175"
    assert (
        "blocked" in active_task_text.lower()
        or "BLOCKED" in active_task_text
        or "authorization" in active_task_text.lower()
    ), "active_task.md must indicate P175 is blocked"


def test_p174_active_task_no_false_success(active_task_text):
    lower = active_task_text.lower()
    for s in ["success-rate method found", "proven method"]:
        assert s not in lower, f"active_task.md must not contain: {s!r}"


# ── Roadmap ────────────────────────────────────────────────────────────────

def test_p174_roadmap_p174_present(roadmap_text):
    assert "P174" in roadmap_text, "roadmap.md must mention P174"


def test_p174_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method", "method found"]:
        assert s not in lower, f"roadmap.md must not contain: {s!r}"


# ── CTO Analysis ──────────────────────────────────────────────────────────

def test_p174_cto_mentions_p174(cto_text):
    assert "P174" in cto_text, "CTO-Analysis.md must mention P174"


def test_p174_cto_mentions_p175(cto_text):
    assert "P175" in cto_text, "CTO-Analysis.md must mention P175"


def test_p174_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge", "r2 edge confirmed"]:
        assert s not in lower, f"CTO-Analysis.md must not contain: {s!r}"


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p174_db_rows_unchanged():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays;"
    ).fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS, f"DB rows changed: expected {EXPECTED_DB_ROWS}, got {n}"
