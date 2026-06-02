"""
Tests for P172: POWER_LOTTO New Strategy Prototype Plan.
=========================================================
All tests are READ-ONLY. No DB writes, no staging checks.

Verifies the P172 prototype plan artifact and governance contracts:
  - Artifact existence (JSON + MD)
  - Final classification
  - Authorization phrase detected
  - Phase 0 verification result = PASS
  - P171 summary present
  - Exactly 3 top prototype candidates
  - Exactly 5 deferred candidates
  - P173 boundary present
  - R2 validation protocol inherited
  - Governance confirmations: no DB write, no strategy implementation, no betting advice
  - Next task is P173_POWER_LOTTO_NEW_STRATEGY_MINIMAL_PROTOTYPE_READ_ONLY
  - P173 blocked by user authorization
  - No forbidden strings in JSON or MD
  - active_task.md marks P172 PLAN_READY and P173 blocked
  - roadmap.md marks R2 planning advanced and no method found yet
  - CTO-Analysis.md mentions P172 candidates selected, no edge found
  - DB row count unchanged at 94924
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
    / "p172_new_strategy_prototype_plan_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p172_new_strategy_prototype_plan_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_FINAL_CLASSIFICATION = "P172_POWER_LOTTO_NEW_STRATEGY_PROTOTYPE_PLAN_READY"
EXPECTED_DB_ROWS = 94924
EXPECTED_NEXT_TASK = "P173_POWER_LOTTO_NEW_STRATEGY_MINIMAL_PROTOTYPE_READ_ONLY"
EXPECTED_AUTHORIZATION_PHRASE = "YES start P172 POWER_LOTTO new strategy prototype plan"
EXPECTED_TOP_3_COUNT = 3
EXPECTED_DEFERRED_COUNT = 5

FORBIDDEN_STRINGS = [
    "success-rate method found",
    "proven method",
    "guaranteed win",
    "champion promoted",
    "db migrated",
    "reconcile complete",
    "controlled_apply authorized",
    "split resolved",
    "real-money advice",
    "strategy deployed",
    "edge found in r2",
    "r2 confirms edge",
    "r2 edge confirmed",
]


@pytest.fixture(scope="module")
def artifact():
    assert JSON_OUT.exists(), f"P172 JSON artifact missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P172 MD artifact missing: {MD_OUT}"
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

def test_p172_json_artifact_exists():
    assert JSON_OUT.exists(), f"P172 JSON artifact missing: {JSON_OUT}"


def test_p172_md_artifact_exists():
    assert MD_OUT.exists(), f"P172 MD artifact missing: {MD_OUT}"


# ── Classification and authorization ──────────────────────────────────────

def test_p172_final_classification(artifact):
    assert artifact.get("final_classification") == EXPECTED_FINAL_CLASSIFICATION, (
        f"Expected {EXPECTED_FINAL_CLASSIFICATION}, got {artifact.get('final_classification')}"
    )


def test_p172_authorization_phrase_detected(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase, (
        f"Authorization phrase not detected. Got: {phrase!r}"
    )


def test_p172_phase0_pass(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("result") == "PASS", f"Phase 0 result not PASS: {phase0.get('result')}"


def test_p172_phase0_db_rows(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("db_rows") == EXPECTED_DB_ROWS, (
        f"Phase 0 DB rows: expected {EXPECTED_DB_ROWS}, got {phase0.get('db_rows')}"
    )


# ── P171 summary ───────────────────────────────────────────────────────────

def test_p172_p171_summary_present(artifact):
    assert "p171_summary" in artifact, "p171_summary key missing from artifact"


def test_p172_p171_summary_classification(artifact):
    summary = artifact.get("p171_summary", {})
    classification = summary.get("classification", "")
    assert "P171_POWER_LOTTO_NEW_STRATEGY_FEATURE_ENGINEERING_DISCOVERY_PLAN_READY" in classification, (
        f"P171 summary classification mismatch: {classification!r}"
    )


def test_p172_p171_summary_r1_conclusion(artifact):
    summary = artifact.get("p171_summary", {})
    conclusion = summary.get("r1_conclusion", "")
    assert "NO_DEFENSIBLE_EDGE" in conclusion or "null" in conclusion.lower(), (
        f"P171 summary must state NO_DEFENSIBLE_EDGE in R1 conclusion. Got: {conclusion!r}"
    )


def test_p172_p171_summary_edge_not_found(artifact):
    summary = artifact.get("p171_summary", {})
    assert summary.get("edge_found_in_p171") is False, (
        "p171_summary.edge_found_in_p171 must be False"
    )


# ── Top 3 prototype candidates ─────────────────────────────────────────────

def test_p172_top3_present(artifact):
    assert "top_3_prototype_candidates" in artifact, "top_3_prototype_candidates missing"


def test_p172_top3_exact_count(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    assert len(top3) == EXPECTED_TOP_3_COUNT, (
        f"top_3_prototype_candidates must have exactly 3 items. Got {len(top3)}"
    )


def test_p172_top3_has_ranks(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    ranks = sorted([c.get("rank") for c in top3])
    assert ranks == [1, 2, 3], f"Top 3 must have ranks 1, 2, 3. Got {ranks}"


def test_p172_top3_each_has_why(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    for c in top3:
        assert "why_top_3" in c and len(c["why_top_3"]) > 30, (
            f"Candidate rank {c.get('rank')} missing or too-short why_top_3"
        )


def test_p172_top3_each_has_data_requirements(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    for c in top3:
        assert "data_requirements" in c, (
            f"Candidate rank {c.get('rank')} missing data_requirements"
        )


def test_p172_top3_each_has_leakage_risk(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    for c in top3:
        assert "leakage_risk" in c, f"Candidate rank {c.get('rank')} missing leakage_risk"


def test_p172_top3_each_has_overfitting_risk(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    for c in top3:
        assert "overfitting_risk" in c, (
            f"Candidate rank {c.get('rank')} missing overfitting_risk"
        )


def test_p172_top3_each_has_min_oos(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    for c in top3:
        assert "minimum_oos_draws" in c, (
            f"Candidate rank {c.get('rank')} missing minimum_oos_draws"
        )


def test_p172_top3_each_has_p173_config(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    for c in top3:
        assert "p173_pre_declared_config" in c, (
            f"Candidate rank {c.get('rank')} missing p173_pre_declared_config"
        )


def test_p172_top3_each_has_p173_scope(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    for c in top3:
        assert "p173_prototype_scope" in c and len(c["p173_prototype_scope"]) > 20, (
            f"Candidate rank {c.get('rank')} missing or too-short p173_prototype_scope"
        )


# ── Deferred candidates ────────────────────────────────────────────────────

def test_p172_deferred_present(artifact):
    assert "deferred_candidates" in artifact, "deferred_candidates missing"


def test_p172_deferred_exact_count(artifact):
    deferred = artifact.get("deferred_candidates", [])
    assert len(deferred) == EXPECTED_DEFERRED_COUNT, (
        f"deferred_candidates must have exactly 5 items. Got {len(deferred)}"
    )


def test_p172_deferred_each_has_reason(artifact):
    deferred = artifact.get("deferred_candidates", [])
    for c in deferred:
        assert "reason_deferred" in c and len(c["reason_deferred"]) > 20, (
            f"Deferred candidate {c.get('candidate_id')} missing or too-short reason_deferred"
        )


def test_p172_deferred_each_has_reactivation_condition(artifact):
    deferred = artifact.get("deferred_candidates", [])
    for c in deferred:
        assert "reactivation_condition" in c, (
            f"Deferred candidate {c.get('candidate_id')} missing reactivation_condition"
        )


def test_p172_top3_plus_deferred_equals_8(artifact):
    top3 = artifact.get("top_3_prototype_candidates", [])
    deferred = artifact.get("deferred_candidates", [])
    assert len(top3) + len(deferred) == 8, (
        f"Top 3 + Deferred must total 8 candidates. Got {len(top3)}+{len(deferred)}"
    )


# ── P173 prototype plan ───────────────────────────────────────────────────

def test_p172_p173_plan_present(artifact):
    assert "p173_minimal_prototype_plan" in artifact, "p173_minimal_prototype_plan missing"


def test_p172_p173_plan_has_input_contract(artifact):
    plan = artifact.get("p173_minimal_prototype_plan", {})
    assert "feature_extraction_input_contract" in plan, (
        "p173_minimal_prototype_plan.feature_extraction_input_contract missing"
    )


def test_p172_p173_plan_has_pre_declared_configs(artifact):
    plan = artifact.get("p173_minimal_prototype_plan", {})
    assert "pre_declared_candidate_configs" in plan, (
        "p173_minimal_prototype_plan.pre_declared_candidate_configs missing"
    )
    configs = plan["pre_declared_candidate_configs"]
    assert len(configs) == 3, (
        f"pre_declared_candidate_configs must have 3 entries. Got {len(configs)}"
    )


def test_p172_p173_plan_has_train_test_split(artifact):
    plan = artifact.get("p173_minimal_prototype_plan", {})
    assert "train_test_time_split" in plan, (
        "p173_minimal_prototype_plan.train_test_time_split missing"
    )
    split = plan["train_test_time_split"]
    assert split.get("no_shuffling") is True, "train_test_time_split must require no shuffling"


def test_p172_p173_plan_has_walk_forward(artifact):
    plan = artifact.get("p173_minimal_prototype_plan", {})
    assert "walk_forward_oos_protocol" in plan, (
        "p173_minimal_prototype_plan.walk_forward_oos_protocol missing"
    )


def test_p172_p173_plan_has_baselines(artifact):
    plan = artifact.get("p173_minimal_prototype_plan", {})
    baselines = plan.get("baseline_comparisons", [])
    assert len(baselines) >= 2, (
        f"p173 plan must have >= 2 baseline comparisons. Got {len(baselines)}"
    )


def test_p172_p173_plan_has_bonferroni(artifact):
    plan = artifact.get("p173_minimal_prototype_plan", {})
    correction = plan.get("multiple_testing_correction", {})
    assert correction.get("primary") == "Bonferroni" or "bonferroni" in str(correction).lower(), (
        "p173 plan must include Bonferroni correction"
    )
    assert correction.get("family_size") == 3, (
        f"Bonferroni family size must be 3 (one per top candidate). Got {correction.get('family_size')}"
    )


def test_p172_p173_plan_has_null_reporting_rule(artifact):
    plan = artifact.get("p173_minimal_prototype_plan", {})
    null_rule = plan.get("null_reporting_rule", "")
    assert "null" in null_rule.lower() and len(null_rule) > 30, (
        "p173 plan must include explicit NULL reporting rule"
    )


# ── P173 boundary ─────────────────────────────────────────────────────────

def test_p172_p173_boundary_present(artifact):
    assert "p173_boundary" in artifact, "p173_boundary missing"


def test_p172_p173_boundary_read_only(artifact):
    boundary = artifact.get("p173_boundary", {})
    allowed = " ".join(boundary.get("allowed_in_p173", [])).lower()
    forbidden = " ".join(boundary.get("forbidden_in_p173", [])).lower()
    assert "read-only" in allowed or "read_only" in allowed, (
        "P173 boundary must include read-only in allowed"
    )
    assert "db write" in forbidden or "registry" in forbidden, (
        "P173 boundary must include DB write or registry mutation in forbidden"
    )


def test_p172_p173_boundary_blocked(artifact):
    boundary = artifact.get("p173_boundary", {})
    assert boundary.get("p173_authorization_required") is True, (
        "p173_boundary.p173_authorization_required must be True"
    )
    assert boundary.get("p173_blocked_by_user_authorization") is True, (
        "p173_boundary.p173_blocked_by_user_authorization must be True"
    )


# ── Governance confirmations ───────────────────────────────────────────────

def test_p172_no_db_write_confirmation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True, "no_db_write not confirmed"


def test_p172_no_strategy_implementation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_strategy_implementation") is True, (
        "no_strategy_implementation not confirmed"
    )


def test_p172_no_betting_advice(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_betting_advice") is True, "no_betting_advice not confirmed"


def test_p172_no_controlled_apply(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_controlled_apply") is True, "no_controlled_apply not confirmed"


def test_p172_no_champion_promotion(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_champion_promotion") is True, "no_champion_promotion not confirmed"


def test_p172_r2_no_edge_found_yet(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("r2_no_edge_found_yet") is True, (
        "r2_no_edge_found_yet must be True"
    )


def test_p172_null_results_stand(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p161_to_p171_null_results_stand") is True, (
        "p161_to_p171_null_results_stand must be True"
    )


# ── Next task and P173 authorization ──────────────────────────────────────

def test_p172_next_task_is_p173(artifact):
    assert artifact.get("next_task") == EXPECTED_NEXT_TASK, (
        f"next_task must be {EXPECTED_NEXT_TASK}. Got {artifact.get('next_task')}"
    )


def test_p172_p173_blocked_by_user_authorization(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True, (
        "next_task_blocked_by_user_authorization must be True"
    )


def test_p172_p173_authorization_phrase_present(artifact):
    phrase = artifact.get("next_task_authorization_required_phrase", "")
    assert "P173" in phrase and len(phrase) > 10, (
        f"next_task_authorization_required_phrase must mention P173. Got: {phrase!r}"
    )


# ── Forbidden strings (JSON) ──────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p172_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, (
        f"Forbidden string found in P172 JSON: {forbidden!r}"
    )


# ── Forbidden strings (MD) ────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p172_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P172 MD: {forbidden!r}"
    )


# ── MD content checks ─────────────────────────────────────────────────────

def test_p172_md_has_classification(md_text):
    assert EXPECTED_FINAL_CLASSIFICATION in md_text, (
        f"MD must contain final classification {EXPECTED_FINAL_CLASSIFICATION}"
    )


def test_p172_md_has_top3(md_text):
    assert "Top 3" in md_text or "Rank 1" in md_text, (
        "MD must contain Top 3 prototype candidates section"
    )


def test_p172_md_has_deferred(md_text):
    assert "Deferred" in md_text or "deferred" in md_text.lower(), (
        "MD must contain deferred candidates section"
    )


def test_p172_md_has_next_task(md_text):
    assert EXPECTED_NEXT_TASK in md_text, (
        f"MD must mention next task {EXPECTED_NEXT_TASK}"
    )


def test_p172_md_has_blocked(md_text):
    assert "BLOCKED" in md_text and "authorization" in md_text.lower(), (
        "MD must state P173 is BLOCKED pending user authorization"
    )


def test_p172_md_no_method_found(md_text):
    lower = md_text.lower()
    assert "no edge" in lower or "no method" in lower or "null" in lower, (
        "MD must state no edge/method has been found"
    )


# ── Active task ────────────────────────────────────────────────────────────

def test_p172_active_task_p172_present(active_task_text):
    assert "P172" in active_task_text, "active_task.md must mention P172"


def test_p172_active_task_p172_plan_ready(active_task_text):
    assert "P172" in active_task_text and (
        "PLAN_READY" in active_task_text or "plan_ready" in active_task_text.lower()
    ), "active_task.md must mark P172 PLAN_READY"


def test_p172_active_task_p173_blocked(active_task_text):
    assert "P173" in active_task_text, "active_task.md must mention P173"
    assert (
        "blocked" in active_task_text.lower()
        or "authorization" in active_task_text.lower()
        or "BLOCKED" in active_task_text
    ), "active_task.md must indicate P173 is blocked pending authorization"


def test_p172_active_task_no_false_success(active_task_text):
    lower = active_task_text.lower()
    for s in ["success-rate method found", "proven method"]:
        assert s not in lower, f"active_task.md must not contain: {s!r}"


# ── Roadmap ────────────────────────────────────────────────────────────────

def test_p172_roadmap_p172_present(roadmap_text):
    assert "P172" in roadmap_text, "roadmap.md must mention P172"


def test_p172_roadmap_r2_advanced(roadmap_text):
    lower = roadmap_text.lower()
    assert "r2" in lower, "roadmap.md must mention R2 planning"


def test_p172_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method"]:
        assert s not in lower, f"roadmap.md must not contain: {s!r}"


# ── CTO Analysis ──────────────────────────────────────────────────────────

def test_p172_cto_mentions_p172(cto_text):
    assert "P172" in cto_text, "CTO-Analysis.md must mention P172"


def test_p172_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge", "r2 edge confirmed"]:
        assert s not in lower, f"CTO-Analysis.md must not contain: {s!r}"


def test_p172_cto_p173_recommendation(cto_text):
    assert "P173" in cto_text, (
        "CTO-Analysis.md must mention P173 as the next step"
    )


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p172_db_rows_unchanged():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays;"
    ).fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS, (
        f"DB rows changed: expected {EXPECTED_DB_ROWS}, got {n}"
    )
