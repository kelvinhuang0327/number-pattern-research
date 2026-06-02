"""
Tests for P178A: POWER_LOTTO R2 Research Closure Archive.
==========================================================
All tests READ-ONLY. No DB writes.

Verifies:
  - Artifacts exist (JSON + MD)
  - final_classification = P178A_POWER_LOTTO_R2_RESEARCH_CLOSED_ARCHIVED
  - Authorization phrase detected
  - Phase 0 PASS
  - DB rows before/after = 94924
  - P177 classification referenced
  - Cumulative strategies = 17, corrected-significant = 0
  - R1 status CLOSED, R2 status CLOSED
  - Active POWER_LOTTO feature engineering CLOSED
  - Archived evidence index includes P161-P177 (all json_exists + md_exists = True)
  - Closure policy: no DB write, no controlled_apply, no champion, no deployment, no wagering, no win guarantee
  - Reopen conditions include >=500 new draws
  - next_task = P179_... BLOCKED
  - active_task.md marks P179 or equivalent BLOCKED
  - roadmap/CTO-Analysis include P178A
  - No forbidden strings
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
    / "p178a_r2_research_closure_archive_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p178a_r2_research_closure_archive_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_FINAL_CLASSIFICATION = "P178A_POWER_LOTTO_R2_RESEARCH_CLOSED_ARCHIVED"
EXPECTED_DB_ROWS = 94924
EXPECTED_AUTHORIZATION_PHRASE = "YES close R2 POWER_LOTTO research and archive findings"
EXPECTED_CUMULATIVE = 17
EXPECTED_PASS_CORRECTED = 0
P177_CLASSIFICATION = "P177_POWER_LOTTO_R2_CLOSURE_DECISION_REVIEW_READY"

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
    assert JSON_OUT.exists(), f"P178A JSON missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P178A MD missing: {MD_OUT}"
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

def test_p178a_json_exists():
    assert JSON_OUT.exists()


def test_p178a_md_exists():
    assert MD_OUT.exists()


# ── Classification ─────────────────────────────────────────────────────────

def test_p178a_final_classification(artifact):
    assert artifact.get("final_classification") == EXPECTED_FINAL_CLASSIFICATION


def test_p178a_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase


def test_p178a_phase0_pass(artifact):
    assert artifact.get("phase_0_verification", {}).get("result") == "PASS"


def test_p178a_phase0_db_rows(artifact):
    assert artifact.get("phase_0_verification", {}).get("db_rows") == EXPECTED_DB_ROWS


# ── Closure decision ───────────────────────────────────────────────────────

def test_p178a_closure_decision_present(artifact):
    assert "closure_decision" in artifact


def test_p178a_p177_classification_referenced(artifact):
    cd = artifact.get("closure_decision", {})
    assert P177_CLASSIFICATION in cd.get("p177_classification_confirmed", ""), (
        f"closure_decision must reference P177 classification. Got: {cd.get('p177_classification_confirmed')!r}"
    )


def test_p178a_r1_closed(artifact):
    cd = artifact.get("closure_decision", {})
    r1 = cd.get("r1_status", "").upper()
    assert "CLOSED" in r1, f"R1 status must be CLOSED. Got: {r1!r}"


def test_p178a_r2_closed(artifact):
    cd = artifact.get("closure_decision", {})
    r2 = cd.get("r2_status", "").upper()
    assert "CLOSED" in r2, f"R2 status must be CLOSED. Got: {r2!r}"


def test_p178a_active_feature_engineering_closed(artifact):
    cd = artifact.get("closure_decision", {})
    afe = cd.get("active_power_lotto_feature_engineering", "").upper()
    assert "CLOSED" in afe, f"active_power_lotto_feature_engineering must be CLOSED. Got: {afe!r}"


# ── Archived evidence index ────────────────────────────────────────────────

def test_p178a_archive_index_present(artifact):
    assert "archived_evidence_index" in artifact


def test_p178a_archive_has_17_entries(artifact):
    idx = artifact.get("archived_evidence_index", [])
    assert len(idx) == 17, f"archived_evidence_index must have 17 entries. Got {len(idx)}"


def test_p178a_archive_p161_to_p177_present(artifact):
    idx = artifact.get("archived_evidence_index", [])
    tasks = [e.get("task") for e in idx]
    required = ["P161", "P162", "P163", "P164", "P165B", "P166", "P167",
                "P168", "P169", "P170", "P171", "P172", "P173", "P174",
                "P175", "P176", "P177"]
    for t in required:
        assert t in tasks, f"archived_evidence_index missing task {t}"


def test_p178a_archive_all_json_exist(artifact):
    idx = artifact.get("archived_evidence_index", [])
    for entry in idx:
        assert entry.get("json_exists") is True, (
            f"Task {entry.get('task')} json_exists must be True"
        )


def test_p178a_archive_all_md_exist(artifact):
    idx = artifact.get("archived_evidence_index", [])
    for entry in idx:
        assert entry.get("md_exists") is True, (
            f"Task {entry.get('task')} md_exists must be True"
        )


def test_p178a_archive_no_missing(artifact):
    ac = artifact.get("archive_completeness", {})
    assert ac.get("missing_artifacts") == [] or ac.get("all_json_present") is True


# ── Closure evidence summary ───────────────────────────────────────────────

def test_p178a_closure_evidence_present(artifact):
    assert "closure_evidence_summary" in artifact


def test_p178a_cumulative_strategies_17(artifact):
    ces = artifact.get("closure_evidence_summary", {})
    count = ces.get("cumulative_strategies_evaluated", 0)
    assert count == EXPECTED_CUMULATIVE, (
        f"cumulative_strategies_evaluated must be {EXPECTED_CUMULATIVE}. Got {count}"
    )


def test_p178a_corrected_significant_zero(artifact):
    ces = artifact.get("closure_evidence_summary", {})
    count = ces.get("corrected_significant_oos_edge_count", -1)
    assert count == EXPECTED_PASS_CORRECTED, (
        f"corrected_significant_oos_edge_count must be {EXPECTED_PASS_CORRECTED}. Got {count}"
    )


# ── Closure policy ─────────────────────────────────────────────────────────

def test_p178a_closure_policy_present(artifact):
    assert "closure_policy" in artifact


def test_p178a_policy_no_wagering(artifact):
    cp = artifact.get("closure_policy", {})
    assert "no_wagering_recommendation" in cp or "no_wagering" in str(cp).lower(), (
        "closure_policy must include no wagering recommendation"
    )


def test_p178a_policy_no_win_guarantee(artifact):
    cp = artifact.get("closure_policy", {})
    assert "no_win_guarantee" in cp, "closure_policy must include no_win_guarantee"


def test_p178a_policy_no_controlled_apply(artifact):
    cp = artifact.get("closure_policy", {})
    policy_text = str(cp)
    assert "controlled_apply" in policy_text.lower() or "no_controlled_apply" in policy_text.lower(), (
        "closure_policy must address controlled_apply"
    )


def test_p178a_policy_no_champion_promotion(artifact):
    cp = artifact.get("closure_policy", {})
    policy_text = str(cp)
    assert "champion" in policy_text.lower(), "closure_policy must address champion promotion"


def test_p178a_policy_no_deployment(artifact):
    cp = artifact.get("closure_policy", {})
    policy_text = str(cp)
    assert "deployment" in policy_text.lower() or "deploy" in policy_text.lower(), (
        "closure_policy must address deployment"
    )


# ── Reopen conditions ─────────────────────────────────────────────────────

def test_p178a_reopen_conditions_present(artifact):
    assert "reopen_conditions" in artifact


def test_p178a_reopen_requires_new_draws(artifact):
    rc = artifact.get("reopen_conditions", {})
    conditions_text = str(rc)
    assert "500" in conditions_text or "draws" in conditions_text.lower(), (
        "reopen_conditions must mention >=500 new draws"
    )


# ── Next task ──────────────────────────────────────────────────────────────

def test_p178a_next_task_present(artifact):
    next_task = artifact.get("next_task", "")
    assert "P179" in next_task or "GOVERNANCE" in next_task or "BACKLOG" in next_task, (
        f"next_task must point to P179 or governance backlog. Got: {next_task!r}"
    )


def test_p178a_next_task_blocked(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


# ── Governance ─────────────────────────────────────────────────────────────

def test_p178a_no_db_write(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True


def test_p178a_no_registry_mutation(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_registry_mutation") is True


def test_p178a_no_controlled_apply(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_controlled_apply") is True


def test_p178a_no_champion_promotion(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_champion_promotion") is True


def test_p178a_no_wagering(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_wagering_recommendations") is True


def test_p178a_db_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("db_unchanged") is True
    assert gov.get("db_rows_before") == EXPECTED_DB_ROWS
    assert gov.get("db_rows_after") == EXPECTED_DB_ROWS


# ── Forbidden strings ─────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p178a_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, f"Forbidden in JSON: {forbidden!r}"


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p178a_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), f"Forbidden in MD: {forbidden!r}"


# ── MD content ────────────────────────────────────────────────────────────

def test_p178a_md_has_classification(md_text):
    assert EXPECTED_FINAL_CLASSIFICATION in md_text


def test_p178a_md_has_17_archived(md_text):
    assert "17" in md_text


def test_p178a_md_has_closed_policy(md_text):
    assert "CLOSED" in md_text or "closed" in md_text.lower()


def test_p178a_md_has_p179(md_text):
    assert "P179" in md_text


def test_p178a_md_has_blocked(md_text):
    assert "BLOCKED" in md_text


# ── Active task ────────────────────────────────────────────────────────────

def test_p178a_active_task_p178a_present(active_task_text):
    assert "P178A" in active_task_text or "P178" in active_task_text


def test_p178a_active_task_next_blocked(active_task_text):
    lower = active_task_text.lower()
    assert "blocked" in lower or "authorization" in lower


# ── Roadmap / CTO ──────────────────────────────────────────────────────────

def test_p178a_roadmap_present(roadmap_text):
    assert "P178A" in roadmap_text or "P178" in roadmap_text or "closure" in roadmap_text.lower()


def test_p178a_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method", "method found"]:
        assert s not in lower, f"roadmap.md must not contain: {s!r}"


def test_p178a_cto_mentions_p178(cto_text):
    assert "P178A" in cto_text or "P178" in cto_text


def test_p178a_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge"]:
        assert s not in lower, f"CTO must not contain: {s!r}"


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p178a_db_rows_unchanged():
    assert DB_PATH.exists()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS
