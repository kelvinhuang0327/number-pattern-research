"""
Tests for P180: Combined Reconciliation and Replay Backlog Plan (Plan Only).
=============================================================================
All tests READ-ONLY. No DB writes.

Verifies:
  - Artifacts exist (JSON + MD)
  - final_classification = P180_COMBINED_RECONCILIATION_AND_REPLAY_BACKLOG_PLAN_READY
  - Authorization phrase detected
  - Phase 0 PASS
  - DB rows before/after = 94924
  - bet_index_present = true
  - P178A classification referenced
  - P179 classification referenced
  - main/zen-gates split with 94924 / 54462 / 40462
  - Reconciliation options A1/A2/A3/A4 present
  - Replay product backlog categories present
  - P181 authorization options present
  - Forbidden actions present
  - active_task.md: P180 PLAN_READY, P181 BLOCKED
  - roadmap/CTO-Analysis include P180
  - No positive deployment / betting advice / win guarantee
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
    / "p180_combined_reconciliation_and_replay_backlog_plan_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p180_combined_reconciliation_and_replay_backlog_plan_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_FINAL_CLASSIFICATION = "P180_COMBINED_RECONCILIATION_AND_REPLAY_BACKLOG_PLAN_READY"
EXPECTED_DB_ROWS = 94924
EXPECTED_AUTHORIZATION_PHRASE = "YES start P180 combined reconciliation and replay backlog plan only"
P178A_CLASSIFICATION = "P178A_POWER_LOTTO_R2_RESEARCH_CLOSED_ARCHIVED"
P179_CLASSIFICATION = "P179_REPLAY_PRODUCT_GOVERNANCE_BACKLOG_DECISION_GATE_READY"

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
    assert JSON_OUT.exists(), f"P180 JSON missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P180 MD missing: {MD_OUT}"
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

def test_p180_json_exists():
    assert JSON_OUT.exists()


def test_p180_md_exists():
    assert MD_OUT.exists()


# ── Classification ─────────────────────────────────────────────────────────

def test_p180_final_classification(artifact):
    assert artifact.get("final_classification") == EXPECTED_FINAL_CLASSIFICATION


def test_p180_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase


def test_p180_phase0_pass(artifact):
    assert artifact.get("phase_0_verification", {}).get("result") == "PASS"


def test_p180_phase0_db_rows(artifact):
    assert artifact.get("phase_0_verification", {}).get("db_rows") == EXPECTED_DB_ROWS


def test_p180_phase0_bet_index_present(artifact):
    assert artifact.get("phase_0_verification", {}).get("bet_index_present") is True


# ── References ─────────────────────────────────────────────────────────────

def test_p180_p178a_referenced(artifact):
    assert P178A_CLASSIFICATION in artifact.get("p178a_classification_referenced", "")


def test_p180_p179_referenced(artifact):
    assert P179_CLASSIFICATION in artifact.get("p179_classification_referenced", "")


# ── Part A: reconciliation ─────────────────────────────────────────────────

def test_p180_part_a_present(artifact):
    assert "part_a_reconciliation_plan" in artifact


def test_p180_split_summary_94924(artifact):
    cs = artifact.get("part_a_reconciliation_plan", {}).get("current_split_summary", {})
    assert cs.get("zen_gates_db_rows") == 94924


def test_p180_split_summary_54462(artifact):
    cs = artifact.get("part_a_reconciliation_plan", {}).get("current_split_summary", {})
    assert cs.get("main_db_rows") == 54462


def test_p180_split_summary_delta_40462(artifact):
    cs = artifact.get("part_a_reconciliation_plan", {}).get("current_split_summary", {})
    assert cs.get("row_delta") == 40462


def test_p180_split_unresolved(artifact):
    cs = artifact.get("part_a_reconciliation_plan", {}).get("current_split_summary", {})
    assert "UNRESOLVED" in cs.get("split_status", "").upper()


def test_p180_reconciliation_options_a1_a2_a3_a4(artifact):
    pa = artifact.get("part_a_reconciliation_plan", {})
    options = pa.get("reconciliation_options", [])
    ids = {o.get("option_id") for o in options}
    for oid in ["A1", "A2", "A3", "A4"]:
        assert oid in ids, f"Reconciliation option {oid} missing"


def test_p180_each_option_has_risk_level(artifact):
    pa = artifact.get("part_a_reconciliation_plan", {})
    for opt in pa.get("reconciliation_options", []):
        assert "risk_level" in opt, f"Option {opt.get('option_id')} missing risk_level"


def test_p180_acceptance_criteria_present(artifact):
    pa = artifact.get("part_a_reconciliation_plan", {})
    assert "acceptance_criteria_for_reconciled_state" in pa


def test_p180_acceptance_target_94924(artifact):
    pa = artifact.get("part_a_reconciliation_plan", {})
    ac = pa.get("acceptance_criteria_for_reconciled_state", {})
    assert ac.get("db_row_count_target") == 94924


# ── Part B: replay backlog ─────────────────────────────────────────────────

def test_p180_part_b_present(artifact):
    assert "part_b_replay_backlog_plan" in artifact


def test_p180_backlog_categories_present(artifact):
    pb = artifact.get("part_b_replay_backlog_plan", {})
    categories = pb.get("backlog_categories", [])
    assert len(categories) >= 3, f"Must have >= 3 backlog categories. Got {len(categories)}"


def test_p180_backlog_has_p0_production_sync(artifact):
    pb = artifact.get("part_b_replay_backlog_plan", {})
    cats = [c.get("category", "") for c in pb.get("backlog_categories", [])]
    assert any("production" in c.lower() or "sync" in c.lower() or "governance" in c.lower() for c in cats), (
        "Backlog must include production governance / main sync category"
    )


def test_p180_prioritized_backlog_present(artifact):
    pb = artifact.get("part_b_replay_backlog_plan", {})
    backlog = pb.get("prioritized_backlog", [])
    assert len(backlog) >= 3, f"Must have >= 3 prioritized backlog items. Got {len(backlog)}"


# ── Part C: P181 options ───────────────────────────────────────────────────

def test_p180_part_c_present(artifact):
    assert "part_c_p181_decision_gate" in artifact or "next_p181_authorization_options" in artifact


def test_p180_p181_options_present(artifact):
    pc = artifact.get("part_c_p181_decision_gate", {})
    opts = pc.get("p181_authorization_options") or artifact.get("next_p181_authorization_options", [])
    assert len(opts) >= 3, f"Must have >= 3 P181 authorization options. Got {len(opts)}"


# ── Forbidden actions ─────────────────────────────────────────────────────

def test_p180_forbidden_actions_present(artifact):
    assert "explicit_forbidden_actions" in artifact


def test_p180_forbidden_no_db_write(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_db_write") is not None


def test_p180_forbidden_no_merge(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_merge") is not None


def test_p180_forbidden_no_migration(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_db_migration") is not None


def test_p180_forbidden_no_deployment(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_deployment") is not None


def test_p180_forbidden_no_power_lotto_rerun(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_power_lotto_research_rerun") is not None


# ── Governance ─────────────────────────────────────────────────────────────

def test_p180_no_db_write(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True


def test_p180_no_merge(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_merge") is True


def test_p180_no_controlled_apply(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_controlled_apply") is True


def test_p180_no_deployment(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_deployment") is True


def test_p180_no_wagering(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_wagering_recommendations") is True


def test_p180_db_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("db_unchanged") is True
    assert gov.get("db_rows_before") == EXPECTED_DB_ROWS
    assert gov.get("db_rows_after") == EXPECTED_DB_ROWS


def test_p180_p178a_closure_active(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p178a_closure_policy_active") is True


# ── Next task ──────────────────────────────────────────────────────────────

def test_p180_next_task_blocked(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


# ── Forbidden strings ─────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p180_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, f"Forbidden in JSON: {forbidden!r}"


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p180_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), f"Forbidden in MD: {forbidden!r}"


# ── MD content ────────────────────────────────────────────────────────────

def test_p180_md_has_classification(md_text):
    assert EXPECTED_FINAL_CLASSIFICATION in md_text


def test_p180_md_has_40462_delta(md_text):
    assert "40,462" in md_text or "40462" in md_text


def test_p180_md_has_options_a1_a2_a3_a4(md_text):
    for opt in ["A1", "A2", "A3", "A4"]:
        assert opt in md_text, f"MD must mention option {opt}"


def test_p180_md_has_p181_blocked(md_text):
    assert "P181" in md_text and "BLOCKED" in md_text


# ── Active task ────────────────────────────────────────────────────────────

def test_p180_active_task_p180_present(active_task_text):
    assert "P180" in active_task_text


def test_p180_active_task_p181_blocked(active_task_text):
    assert "P181" in active_task_text
    assert "blocked" in active_task_text.lower() or "BLOCKED" in active_task_text


# ── Roadmap / CTO ──────────────────────────────────────────────────────────

def test_p180_roadmap_p180_present(roadmap_text):
    assert "P180" in roadmap_text


def test_p180_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method", "method found"]:
        assert s not in lower


def test_p180_cto_mentions_p180(cto_text):
    assert "P180" in cto_text


def test_p180_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge"]:
        assert s not in lower


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p180_db_rows_unchanged():
    assert DB_PATH.exists()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS
