"""
Tests for P171: POWER_LOTTO New Strategy Feature Engineering Discovery Plan.
============================================================================
All tests are READ-ONLY. No DB writes, no staging checks.

Verifies the P171 discovery plan artifact and governance contracts:
  - Artifact existence (JSON + MD)
  - Final classification
  - Authorization phrase detected
  - Phase 0 verification result = PASS
  - R1 no defensible edge summary present
  - Feature engineering inventory >= 10 families
  - Strategy candidates >= 8 types
  - R2 validation protocol present (>= 8 steps)
  - Governance confirmations: no DB write, no strategy implementation, no betting advice
  - Next task is P172_POWER_LOTTO_NEW_STRATEGY_PROTOTYPE_PLAN_ONLY
  - P172 blocked by user authorization
  - No forbidden strings in JSON or MD
  - active_task.md marks P171 PLAN_READY and P172 blocked
  - roadmap.md marks R2 started and R1 closed/deprioritized
  - CTO-Analysis.md mentions P171 as pivot, not edge-found
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
    / "p171_new_strategy_feature_engineering_discovery_plan_20260531.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p171_new_strategy_feature_engineering_discovery_plan_20260531.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_FINAL_CLASSIFICATION = "P171_POWER_LOTTO_NEW_STRATEGY_FEATURE_ENGINEERING_DISCOVERY_PLAN_READY"
EXPECTED_DB_ROWS = 94924
EXPECTED_NEXT_TASK = "P172_POWER_LOTTO_NEW_STRATEGY_PROTOTYPE_PLAN_ONLY"
EXPECTED_AUTHORIZATION_PHRASE = "YES start R2 new POWER_LOTTO strategy discovery from feature engineering"

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
    "p167 passed",
    "window 2 passed",
    "499 qualifies as original",
    "edge found in r2",
    "r2 confirms edge",
]


@pytest.fixture(scope="module")
def artifact():
    assert JSON_OUT.exists(), f"P171 JSON artifact missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P171 MD artifact missing: {MD_OUT}"
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

def test_p171_json_artifact_exists():
    assert JSON_OUT.exists(), f"P171 JSON artifact missing: {JSON_OUT}"


def test_p171_md_artifact_exists():
    assert MD_OUT.exists(), f"P171 MD artifact missing: {MD_OUT}"


# ── Classification and authorization ──────────────────────────────────────

def test_p171_final_classification(artifact):
    assert artifact.get("final_classification") == EXPECTED_FINAL_CLASSIFICATION, (
        f"Expected {EXPECTED_FINAL_CLASSIFICATION}, got {artifact.get('final_classification')}"
    )


def test_p171_authorization_phrase_detected(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase, (
        f"Authorization phrase not detected. Got: {phrase!r}"
    )


def test_p171_phase0_pass(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("result") == "PASS", f"Phase 0 result not PASS: {phase0.get('result')}"


def test_p171_phase0_db_rows(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("db_rows") == EXPECTED_DB_ROWS, (
        f"Phase 0 DB rows: expected {EXPECTED_DB_ROWS}, got {phase0.get('db_rows')}"
    )


def test_p171_phase0_drift_guard_pass(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("drift_guard") == "PASS", (
        f"Phase 0 drift guard: {phase0.get('drift_guard')}"
    )


def test_p171_phase0_p167_script_pass(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("p167_script") == "PASS", (
        f"Phase 0 P167 script: {phase0.get('p167_script')}"
    )


def test_p171_phase0_p170_script_pass(artifact):
    phase0 = artifact.get("phase_0_verification", {})
    assert phase0.get("p170_script") == "PASS", (
        f"Phase 0 P170 script: {phase0.get('p170_script')}"
    )


# ── R1 summary ─────────────────────────────────────────────────────────────

def test_p171_r1_summary_present(artifact):
    assert "r1_summary" in artifact, "r1_summary key missing from artifact"


def test_p171_r1_no_defensible_edge(artifact):
    r1 = artifact.get("r1_summary", {})
    classification = r1.get("r1_classification", "")
    assert "NO_DEFENSIBLE_EDGE" in classification, (
        f"R1 summary must state NO_DEFENSIBLE_EDGE_FOUND. Got: {classification!r}"
    )


def test_p171_r1_completed_tasks(artifact):
    r1 = artifact.get("r1_summary", {})
    completed = r1.get("tasks_completed", [])
    required = ["P161", "P167", "P170"]
    for task in required:
        assert task in completed, f"R1 summary missing task {task} in completed list"


def test_p171_r1_conclusion_present(artifact):
    r1 = artifact.get("r1_summary", {})
    conclusion = r1.get("conclusion", "")
    assert len(conclusion) > 20, "R1 summary conclusion is too short or missing"
    # Must not claim edge was found
    assert "edge found" not in conclusion.lower() or "no" in conclusion.lower(), (
        "R1 conclusion must not claim edge was found"
    )


# ── Feature engineering inventory ─────────────────────────────────────────

def test_p171_feature_families_present(artifact):
    inv = artifact.get("feature_engineering_inventory", {})
    assert "families" in inv, "feature_engineering_inventory.families missing"


def test_p171_feature_families_count(artifact):
    inv = artifact.get("feature_engineering_inventory", {})
    families = inv.get("families", [])
    assert len(families) >= 10, (
        f"Feature families count must be >= 10. Got {len(families)}"
    )


def test_p171_feature_families_total_field(artifact):
    inv = artifact.get("feature_engineering_inventory", {})
    total = inv.get("total_families", 0)
    families = inv.get("families", [])
    assert total >= 10, f"total_families field must be >= 10. Got {total}"
    assert total == len(families), (
        f"total_families ({total}) must match len(families) ({len(families)})"
    )


def test_p171_required_feature_family_names(artifact):
    inv = artifact.get("feature_engineering_inventory", {})
    families = inv.get("families", [])
    names = [f.get("name", "") for f in families]
    required_substrings = [
        "recency_frequency",
        "hot_cold",
        "positional",
        "pair",
        "gap",
        "parity",
        "zone",
        "sum",
        "modulo",
        "regime",
    ]
    for substr in required_substrings:
        assert any(substr in n for n in names), (
            f"No feature family name contains '{substr}'. Names: {names}"
        )


def test_p171_each_family_has_leakage_risk(artifact):
    inv = artifact.get("feature_engineering_inventory", {})
    families = inv.get("families", [])
    for f in families:
        assert "leakage_risk" in f, f"Family {f.get('name')} missing leakage_risk"


def test_p171_each_family_has_signals(artifact):
    inv = artifact.get("feature_engineering_inventory", {})
    families = inv.get("families", [])
    for f in families:
        assert "signals" in f and len(f["signals"]) > 0, (
            f"Family {f.get('name')} missing signals"
        )


# ── Strategy candidates ────────────────────────────────────────────────────

def test_p171_strategy_candidates_present(artifact):
    assert "strategy_candidates" in artifact, "strategy_candidates missing from artifact"


def test_p171_strategy_candidates_count(artifact):
    candidates = artifact.get("strategy_candidates", [])
    assert len(candidates) >= 8, (
        f"Strategy candidates must be >= 8. Got {len(candidates)}"
    )


def test_p171_required_strategy_candidate_names(artifact):
    candidates = artifact.get("strategy_candidates", [])
    names = [c.get("name", "") for c in candidates]
    required_substrings = [
        "recency_frequency",
        "gap_adjusted",
        "co_occurrence",
        "zone_balanced",
        "entropy",
        "regime",
        "rank_aggregation",
        "baseline_challenger",
    ]
    for substr in required_substrings:
        assert any(substr in n for n in names), (
            f"No strategy candidate name contains '{substr}'. Names: {names}"
        )


def test_p171_each_candidate_has_hypothesis(artifact):
    candidates = artifact.get("strategy_candidates", [])
    for c in candidates:
        assert "hypothesis" in c and len(c["hypothesis"]) > 20, (
            f"Candidate {c.get('name')} missing or too-short hypothesis"
        )


def test_p171_each_candidate_has_leakage_risk(artifact):
    candidates = artifact.get("strategy_candidates", [])
    for c in candidates:
        assert "leakage_risk" in c, f"Candidate {c.get('name')} missing leakage_risk"


def test_p171_each_candidate_has_overfitting_risk(artifact):
    candidates = artifact.get("strategy_candidates", [])
    for c in candidates:
        assert "overfitting_risk" in c, f"Candidate {c.get('name')} missing overfitting_risk"


def test_p171_each_candidate_has_validation_method(artifact):
    candidates = artifact.get("strategy_candidates", [])
    for c in candidates:
        assert "validation_method" in c and len(c["validation_method"]) > 10, (
            f"Candidate {c.get('name')} missing or too-short validation_method"
        )


def test_p171_each_candidate_has_min_oos_requirement(artifact):
    candidates = artifact.get("strategy_candidates", [])
    for c in candidates:
        assert "minimum_oos_requirement" in c, (
            f"Candidate {c.get('name')} missing minimum_oos_requirement"
        )


def test_p171_each_candidate_has_reason_not_recombining(artifact):
    candidates = artifact.get("strategy_candidates", [])
    for c in candidates:
        assert "reason_not_recombining_old_strategies" in c and len(
            c["reason_not_recombining_old_strategies"]
        ) > 20, (
            f"Candidate {c.get('name')} missing or too-short reason_not_recombining_old_strategies"
        )


def test_p171_each_candidate_has_required_features(artifact):
    candidates = artifact.get("strategy_candidates", [])
    for c in candidates:
        assert "required_features" in c and len(c["required_features"]) > 0, (
            f"Candidate {c.get('name')} missing required_features"
        )


# ── R2 validation protocol ────────────────────────────────────────────────

def test_p171_r2_validation_protocol_present(artifact):
    assert "r2_validation_protocol" in artifact, "r2_validation_protocol missing"


def test_p171_r2_validation_protocol_steps_count(artifact):
    protocol = artifact.get("r2_validation_protocol", {})
    steps = protocol.get("steps", [])
    assert len(steps) >= 8, (
        f"R2 validation protocol must have >= 8 steps. Got {len(steps)}"
    )


def test_p171_r2_validation_protocol_has_honest_null(artifact):
    protocol = artifact.get("r2_validation_protocol", {})
    steps = protocol.get("steps", [])
    step_names = [s.get("name", "") for s in steps]
    assert any("null" in n.lower() or "honest" in n.lower() for n in step_names), (
        f"R2 protocol must include honest NULL reporting step. Step names: {step_names}"
    )


def test_p171_r2_validation_protocol_has_bonferroni(artifact):
    protocol = artifact.get("r2_validation_protocol", {})
    text = json.dumps(protocol).lower()
    assert "bonferroni" in text or "bh" in text or "multiple_testing" in text, (
        "R2 validation protocol must mention multiple testing correction"
    )


def test_p171_r2_validation_protocol_has_walk_forward(artifact):
    protocol = artifact.get("r2_validation_protocol", {})
    text = json.dumps(protocol).lower()
    assert "walk" in text or "walk_forward" in text, (
        "R2 validation protocol must mention walk-forward evaluation"
    )


def test_p171_r2_validation_protocol_has_time_ordered_split(artifact):
    protocol = artifact.get("r2_validation_protocol", {})
    text = json.dumps(protocol).lower()
    assert "time" in text and ("split" in text or "order" in text), (
        "R2 validation protocol must mention time-ordered train/test split"
    )


def test_p171_r2_validation_protocol_compares_p161(artifact):
    protocol = artifact.get("r2_validation_protocol", {})
    text = json.dumps(protocol).lower()
    assert "p161" in text, (
        "R2 validation protocol must include comparison against P161 best strategy"
    )


def test_p171_r2_validation_protocol_compares_p167(artifact):
    protocol = artifact.get("r2_validation_protocol", {})
    text = json.dumps(protocol).lower()
    assert "p167" in text, (
        "R2 validation protocol must include comparison against P167 ensemble"
    )


# ── Governance confirmations ───────────────────────────────────────────────

def test_p171_no_db_write_confirmation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True, "no_db_write not confirmed"


def test_p171_no_strategy_implementation_confirmation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_strategy_implementation") is True, (
        "no_strategy_implementation not confirmed"
    )


def test_p171_no_betting_advice_confirmation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_betting_advice") is True, "no_betting_advice not confirmed"


def test_p171_no_controlled_apply(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_controlled_apply") is True, "no_controlled_apply not confirmed"


def test_p171_no_champion_promotion(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_champion_promotion") is True, "no_champion_promotion not confirmed"


def test_p171_r2_no_edge_found_yet(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("r2_no_edge_found_yet") is True, (
        "r2_no_edge_found_yet must be True — R2 just started"
    )


def test_p171_p161_to_p170_null_results_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p161_to_p170_null_results_stand") is True, (
        "p161_to_p170_null_results_stand must be True"
    )


# ── Next task and P172 authorization ──────────────────────────────────────

def test_p171_next_task_is_p172(artifact):
    assert artifact.get("next_task") == EXPECTED_NEXT_TASK, (
        f"next_task must be {EXPECTED_NEXT_TASK}. Got {artifact.get('next_task')}"
    )


def test_p171_p172_blocked_by_user_authorization(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True, (
        "next_task_blocked_by_user_authorization must be True"
    )


def test_p171_p172_authorization_phrase_present(artifact):
    phrase = artifact.get("next_task_authorization_required_phrase", "")
    assert "P172" in phrase and len(phrase) > 10, (
        f"next_task_authorization_required_phrase must mention P172. Got: {phrase!r}"
    )


# ── P172 prototype boundary ───────────────────────────────────────────────

def test_p171_p172_boundary_present(artifact):
    assert "p172_prototype_boundary" in artifact, "p172_prototype_boundary missing"


def test_p171_p172_boundary_read_only_db(artifact):
    boundary = artifact.get("p172_prototype_boundary", {})
    allowed = " ".join(boundary.get("allowed_in_p172", [])).lower()
    forbidden = " ".join(boundary.get("forbidden_in_p172", [])).lower()
    assert "read-only" in allowed or "read_only" in allowed, (
        "P172 boundary must include read-only DB in allowed"
    )
    assert "db write" in forbidden or "registry mutation" in forbidden, (
        "P172 boundary must include DB write or registry mutation in forbidden"
    )


# ── Forbidden strings (JSON) ──────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p171_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, (
        f"Forbidden string found in P171 JSON: {forbidden!r}"
    )


# ── Forbidden strings (MD) ────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p171_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P171 MD: {forbidden!r}"
    )


# ── MD content checks ────────────────────────────────────────────────────

def test_p171_md_has_classification(md_text):
    assert EXPECTED_FINAL_CLASSIFICATION in md_text, (
        f"MD must contain final classification {EXPECTED_FINAL_CLASSIFICATION}"
    )


def test_p171_md_has_r1_summary(md_text):
    assert "R1 Summary" in md_text or "r1_summary" in md_text.lower(), (
        "MD must contain R1 summary section"
    )


def test_p171_md_has_no_defensible_edge(md_text):
    assert "No Defensible Edge" in md_text or "no defensible edge" in md_text.lower(), (
        "MD must state no defensible edge was found in R1"
    )


def test_p171_md_has_next_task(md_text):
    assert EXPECTED_NEXT_TASK in md_text, (
        f"MD must mention next task {EXPECTED_NEXT_TASK}"
    )


def test_p171_md_has_blocked_authorization(md_text):
    assert "BLOCKED" in md_text and "authorization" in md_text.lower(), (
        "MD must state P172 is BLOCKED pending user authorization"
    )


# ── Active task ────────────────────────────────────────────────────────────

def test_p171_active_task_p171_present(active_task_text):
    assert "P171" in active_task_text, "active_task.md must mention P171"


def test_p171_active_task_p172_blocked(active_task_text):
    # Must indicate P172 requires authorization
    assert "P172" in active_task_text, "active_task.md must mention P172"
    assert (
        "blocked" in active_task_text.lower()
        or "authorization" in active_task_text.lower()
        or "BLOCKED" in active_task_text
    ), "active_task.md must indicate P172 is blocked pending authorization"


def test_p171_active_task_no_false_success(active_task_text):
    lower = active_task_text.lower()
    for s in ["success-rate method found", "proven method", "guaranteed win"]:
        assert s not in lower, f"active_task.md must not contain: {s!r}"


# ── Roadmap ────────────────────────────────────────────────────────────────

def test_p171_roadmap_p171_present(roadmap_text):
    assert "P171" in roadmap_text, "roadmap.md must mention P171"


def test_p171_roadmap_r2_mentioned(roadmap_text):
    assert "R2" in roadmap_text, "roadmap.md must mention R2 new strategy discovery"


def test_p171_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method", "guaranteed win"]:
        assert s not in lower, f"roadmap.md must not contain: {s!r}"


def test_p171_roadmap_r1_closed_or_deprioritized(roadmap_text):
    lower = roadmap_text.lower()
    assert (
        "r1" in lower
        and (
            "closed" in lower
            or "deprioritized" in lower
            or "no defensible edge" in lower
            or "null" in lower
        )
    ), "roadmap.md must indicate R1 is closed or deprioritized due to null result"


# ── CTO Analysis ──────────────────────────────────────────────────────────

def test_p171_cto_mentions_p171(cto_text):
    assert "P171" in cto_text, "CTO-Analysis.md must mention P171"


def test_p171_cto_pivot_not_edge_found(cto_text):
    lower = cto_text.lower()
    # Must say pivot / new strategy discovery
    assert "pivot" in lower or "new strategy" in lower or "r2" in lower, (
        "CTO-Analysis.md must indicate P171 is a pivot to new strategy discovery"
    )
    # Must NOT contain unambiguous positive-claim strings
    # Note: "edge found" and "guaranteed win" are intentionally excluded here because they
    # appear legitimately in null-result statements ("no defensible edge found",
    # "no guaranteed win claim") throughout the historical CTO document.
    for s in ["success-rate method found", "proven method", "r2 edge confirmed", "r2 confirms edge"]:
        assert s not in lower, f"CTO-Analysis.md must not contain: {s!r}"


def test_p171_cto_p172_recommendation(cto_text):
    assert "P172" in cto_text, (
        "CTO-Analysis.md must mention P172 as the recommended next step"
    )


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p171_db_rows_unchanged():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays;"
    ).fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS, (
        f"DB rows changed: expected {EXPECTED_DB_ROWS}, got {n}"
    )
