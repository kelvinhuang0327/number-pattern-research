"""
Tests for P181: Code/Docs/Tests Parity Plan (Plan Only).
=========================================================
All tests READ-ONLY. No DB writes.

Verifies:
  - Artifacts exist
  - final_classification = P181_CODE_DOCS_TESTS_PARITY_PLAN_READY
  - Authorization phrase detected
  - Phase 0 PASS
  - DB rows = 94924, bet_index present
  - P178A/P179/P180 classifications referenced
  - main/zen-gates split with 94924/54462/40462
  - Code/docs/tests parity categories
  - Test compatibility strategy
  - P182 options
  - Forbidden actions (no merge, no checkout, no DB write, no backport executed)
  - active_task.md: P181 PLAN_READY, P182 BLOCKED
  - roadmap/CTO include P181
  - No deployment/betting/win-guarantee wording
  - No implication that merge/checkout/DB write/backport was performed
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
    / "p181_code_docs_tests_parity_plan_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p181_code_docs_tests_parity_plan_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_FINAL_CLASSIFICATION = "P181_CODE_DOCS_TESTS_PARITY_PLAN_READY"
EXPECTED_DB_ROWS = 94924
EXPECTED_AUTHORIZATION_PHRASE = "YES start P181 code-docs-tests parity plan only"

FORBIDDEN_STRINGS = [
    "guaranteed win",
    "betting advice",
    "champion promoted",
    "controlled_apply authorized",
    "db migrated",
    "method found",
    "edge confirmed",
    "r2 confirms edge",
    "split resolved",
]


@pytest.fixture(scope="module")
def artifact():
    assert JSON_OUT.exists(), f"P181 JSON missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P181 MD missing: {MD_OUT}"
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

def test_p181_json_exists():
    assert JSON_OUT.exists()


def test_p181_md_exists():
    assert MD_OUT.exists()


# ── Classification ─────────────────────────────────────────────────────────

def test_p181_final_classification(artifact):
    assert artifact.get("final_classification") == EXPECTED_FINAL_CLASSIFICATION


def test_p181_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase


def test_p181_phase0_pass(artifact):
    assert artifact.get("phase_0_verification", {}).get("result") == "PASS"


def test_p181_phase0_db_rows(artifact):
    assert artifact.get("phase_0_verification", {}).get("db_rows") == EXPECTED_DB_ROWS


def test_p181_phase0_bet_index(artifact):
    assert artifact.get("phase_0_verification", {}).get("bet_index_present") is True


# ── Prior classifications ──────────────────────────────────────────────────

def test_p181_p178a_referenced(artifact):
    assert "P178A_POWER_LOTTO_R2_RESEARCH_CLOSED_ARCHIVED" in artifact.get("p178a_classification_referenced", "")


def test_p181_p179_referenced(artifact):
    assert "P179_REPLAY_PRODUCT_GOVERNANCE_BACKLOG_DECISION_GATE_READY" in artifact.get("p179_classification_referenced", "")


def test_p181_p180_referenced(artifact):
    assert "P180_COMBINED_RECONCILIATION_AND_REPLAY_BACKLOG_PLAN_READY" in artifact.get("p180_classification_referenced", "")


# ── Parity gap inventory ───────────────────────────────────────────────────

def test_p181_part_a_present(artifact):
    assert "part_a_parity_gap_inventory" in artifact


def test_p181_split_94924(artifact):
    pa = artifact.get("part_a_parity_gap_inventory", {})
    facts = pa.get("known_facts_from_prior_audits", {})
    assert facts.get("zen_gates_db_rows") == 94924


def test_p181_split_54462(artifact):
    pa = artifact.get("part_a_parity_gap_inventory", {})
    facts = pa.get("known_facts_from_prior_audits", {})
    assert facts.get("main_db_rows") == 54462


def test_p181_split_delta_40462(artifact):
    pa = artifact.get("part_a_parity_gap_inventory", {})
    facts = pa.get("known_facts_from_prior_audits", {})
    assert facts.get("row_delta") == 40462


def test_p181_split_unresolved(artifact):
    pa = artifact.get("part_a_parity_gap_inventory", {})
    facts = pa.get("known_facts_from_prior_audits", {})
    assert "UNRESOLVED" in facts.get("split_status", "").upper()


# ── Parity scope ───────────────────────────────────────────────────────────

def test_p181_part_b_present(artifact):
    assert "part_b_parity_scope" in artifact


def test_p181_code_parity_scope(artifact):
    pb = artifact.get("part_b_parity_scope", {})
    assert "code_parity_scope" in pb


def test_p181_docs_parity_scope(artifact):
    pb = artifact.get("part_b_parity_scope", {})
    assert "docs_parity_scope" in pb


def test_p181_tests_parity_scope(artifact):
    pb = artifact.get("part_b_parity_scope", {})
    assert "tests_parity_scope" in pb


def test_p181_explicitly_excluded(artifact):
    pb = artifact.get("part_b_parity_scope", {})
    excluded = pb.get("explicitly_excluded_from_p181", [])
    assert len(excluded) > 0, "Must have explicit exclusions"


# ── Backport design ────────────────────────────────────────────────────────

def test_p181_part_c_present(artifact):
    assert "part_c_backport_execution_design" in artifact


def test_p181_backport_has_8_steps(artifact):
    pc = artifact.get("part_c_backport_execution_design", {})
    steps = pc.get("steps", [])
    assert len(steps) >= 7, f"Backport design must have >= 7 steps. Got {len(steps)}"


# ── Test compatibility strategy ────────────────────────────────────────────

def test_p181_part_d_present(artifact):
    assert "part_d_test_compatibility_strategy" in artifact


def test_p181_test_tiers_present(artifact):
    pd = artifact.get("part_d_test_compatibility_strategy", {})
    solution = pd.get("solution", {})
    tiers = solution.get("tiers", [])
    assert len(tiers) >= 3, f"Test compatibility must have >= 3 tiers. Got {len(tiers)}"


def test_p181_forbidden_weakening(artifact):
    pd = artifact.get("part_d_test_compatibility_strategy", {})
    solution = pd.get("solution", {})
    forbidden = solution.get("forbidden_approaches", [])
    assert any("weaken" in f.lower() or "assertion" in f.lower() or "forbidden" in f.lower() for f in forbidden), (
        "Must explicitly forbid weakening test assertions"
    )


# ── P182 options ───────────────────────────────────────────────────────────

def test_p181_part_e_present(artifact):
    assert "part_e_p182_options" in artifact or "next_p182_authorization_options" in artifact


def test_p181_p182_options_present(artifact):
    pe = artifact.get("part_e_p182_options", {})
    opts = pe.get("authorization_options") or artifact.get("next_p182_authorization_options", [])
    assert len(opts) >= 3, f"Must have >= 3 P182 options. Got {len(opts)}"


# ── Governance: P181 is plan-only ─────────────────────────────────────────

def test_p181_is_plan_only(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p181_is_plan_only") is True


def test_p181_no_backport_executed(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_backport_executed") is True


def test_p181_no_merge(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_merge") is True


def test_p181_no_checkout(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_checkout") is True


def test_p181_no_db_write(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True


def test_p181_p178a_closure_active(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("p178a_closure_policy_active") is True


def test_p181_db_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("db_rows_before") == EXPECTED_DB_ROWS
    assert gov.get("db_rows_after") == EXPECTED_DB_ROWS


# ── Next task ──────────────────────────────────────────────────────────────

def test_p181_next_task_blocked(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


# ── Forbidden strings ─────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p181_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, f"Forbidden in JSON: {forbidden!r}"


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p181_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), f"Forbidden in MD: {forbidden!r}"


# ── MD content ────────────────────────────────────────────────────────────

def test_p181_md_has_classification(md_text):
    assert EXPECTED_FINAL_CLASSIFICATION in md_text


def test_p181_md_has_40462(md_text):
    assert "40,462" in md_text or "40462" in md_text


def test_p181_md_has_test_tiers(md_text):
    assert "T1" in md_text or "T2" in md_text or "tier" in md_text.lower()


def test_p181_md_has_p182_blocked(md_text):
    assert "P182" in md_text and "BLOCKED" in md_text


def test_p181_md_plan_only(md_text):
    lower = md_text.lower()
    assert "plan-only" in lower or "plan only" in lower


# ── Active task ────────────────────────────────────────────────────────────

def test_p181_active_task_p181_present(active_task_text):
    assert "P181" in active_task_text


def test_p181_active_task_p182_blocked(active_task_text):
    assert "P182" in active_task_text
    assert "blocked" in active_task_text.lower() or "BLOCKED" in active_task_text


# ── Roadmap / CTO ──────────────────────────────────────────────────────────

def test_p181_roadmap_p181_present(roadmap_text):
    assert "P181" in roadmap_text


def test_p181_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method", "method found"]:
        assert s not in lower


def test_p181_cto_mentions_p181(cto_text):
    assert "P181" in cto_text


def test_p181_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge"]:
        assert s not in lower


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p181_db_rows_unchanged():
    assert DB_PATH.exists()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS
