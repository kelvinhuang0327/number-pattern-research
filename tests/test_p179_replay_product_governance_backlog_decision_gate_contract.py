"""
Tests for P179: Replay Product Governance Backlog Decision Gate.
================================================================
All tests READ-ONLY. No DB writes.

Verifies:
  - Artifacts exist (JSON + MD)
  - final_classification = P179_REPLAY_PRODUCT_GOVERNANCE_BACKLOG_DECISION_GATE_READY
  - Authorization phrase detected
  - Phase 0 PASS
  - DB rows before/after = 94924
  - P178A classification referenced
  - POWER_LOTTO active research remains CLOSED
  - main/zen-gates split still unresolved
  - Options A/B/C/D present
  - Option D marked NOT_RECOMMENDED
  - CEO authorization options for P180 present
  - Explicit forbidden actions: no DB write, no merge, no controlled_apply, no deployment, no new strategy, no research rerun
  - active_task.md: P179 DECISION_GATE_READY, P180 BLOCKED
  - roadmap/CTO-Analysis include P179
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
    / "p179_replay_product_governance_backlog_decision_gate_20260601.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p179_replay_product_governance_backlog_decision_gate_20260601.md"
)
ACTIVE_TASK = PROJECT_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = PROJECT_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = PROJECT_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

EXPECTED_FINAL_CLASSIFICATION = "P179_REPLAY_PRODUCT_GOVERNANCE_BACKLOG_DECISION_GATE_READY"
EXPECTED_DB_ROWS = 94924
EXPECTED_AUTHORIZATION_PHRASE = "YES start P179 replay product governance backlog decision gate"
P178A_CLASSIFICATION = "P178A_POWER_LOTTO_R2_RESEARCH_CLOSED_ARCHIVED"

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
    assert JSON_OUT.exists(), f"P179 JSON missing: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_OUT.exists(), f"P179 MD missing: {MD_OUT}"
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

def test_p179_json_exists():
    assert JSON_OUT.exists()


def test_p179_md_exists():
    assert MD_OUT.exists()


# ── Classification ─────────────────────────────────────────────────────────

def test_p179_final_classification(artifact):
    assert artifact.get("final_classification") == EXPECTED_FINAL_CLASSIFICATION


def test_p179_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert EXPECTED_AUTHORIZATION_PHRASE in phrase


def test_p179_phase0_pass(artifact):
    assert artifact.get("phase_0_verification", {}).get("result") == "PASS"


def test_p179_phase0_db_rows(artifact):
    assert artifact.get("phase_0_verification", {}).get("db_rows") == EXPECTED_DB_ROWS


def test_p179_phase0_bet_index_present(artifact):
    assert artifact.get("phase_0_verification", {}).get("bet_index_present") is True


# ── Current state ──────────────────────────────────────────────────────────

def test_p179_current_state_present(artifact):
    assert "current_state_confirmation" in artifact


def test_p179_p178a_referenced(artifact):
    cs = artifact.get("current_state_confirmation", {})
    assert P178A_CLASSIFICATION in cs.get("p178a_classification", ""), (
        f"current_state must reference P178A classification. Got: {cs.get('p178a_classification')!r}"
    )


def test_p179_power_lotto_research_closed(artifact):
    cs = artifact.get("current_state_confirmation", {})
    assert "CLOSED" in cs.get("power_lotto_active_research", "").upper(), (
        "POWER_LOTTO active research must be CLOSED"
    )


def test_p179_main_zen_gates_unresolved(artifact):
    cs = artifact.get("current_state_confirmation", {})
    split = cs.get("main_zen_gates_split", "").upper()
    assert "UNRESOLVED" in split, f"main/zen-gates split must be UNRESOLVED. Got: {split!r}"


# ── Options ────────────────────────────────────────────────────────────────

def test_p179_options_present(artifact):
    assert "governance_backlog_options" in artifact


def test_p179_four_options(artifact):
    options = artifact.get("governance_backlog_options", [])
    ids = {o.get("option_id") for o in options}
    for oid in ["A", "B", "C", "D"]:
        assert oid in ids, f"Missing option {oid}"


def test_p179_option_a_recommended(artifact):
    options = artifact.get("governance_backlog_options", [])
    opt_a = next((o for o in options if o.get("option_id") == "A"), None)
    assert opt_a, "Option A missing"
    assert "RECOMMEND" in opt_a.get("recommendation_status", "").upper(), (
        f"Option A must be RECOMMENDED. Got: {opt_a.get('recommendation_status')!r}"
    )


def test_p179_option_d_not_recommended(artifact):
    options = artifact.get("governance_backlog_options", [])
    opt_d = next((o for o in options if o.get("option_id") == "D"), None)
    assert opt_d, "Option D missing"
    assert "NOT_RECOMMENDED" in opt_d.get("recommendation_status", "").upper(), (
        f"Option D must be NOT_RECOMMENDED. Got: {opt_d.get('recommendation_status')!r}"
    )


# ── CEO decision gate ─────────────────────────────────────────────────────

def test_p179_ceo_gate_present(artifact):
    assert "ceo_decision_gate" in artifact or "next_p180_authorization_options" in artifact


def test_p179_p180_authorization_options_present(artifact):
    opts = artifact.get("next_p180_authorization_options") or []
    if not opts:
        opts = [o.get("phrase", "") for o in artifact.get("ceo_decision_gate", {}).get("authorization_options", [])]
    assert len(opts) >= 3, f"Must have at least 3 P180 authorization options. Got {len(opts)}"


def test_p179_p180_option_a_close_reconciliation(artifact):
    opts = artifact.get("next_p180_authorization_options") or []
    assert any("reconciliation" in str(o).lower() or "zen-gates" in str(o).lower() for o in opts), (
        "Must have a P180 authorization option for reconciliation"
    )


# ── Explicit forbidden actions ─────────────────────────────────────────────

def test_p179_forbidden_actions_present(artifact):
    assert "explicit_forbidden_actions" in artifact


def test_p179_forbidden_no_db_write(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_db_write") is not None, "explicit_forbidden_actions must include no_db_write"


def test_p179_forbidden_no_merge(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_merge") is not None, "explicit_forbidden_actions must include no_merge"


def test_p179_forbidden_no_controlled_apply(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_controlled_apply") is not None, "explicit_forbidden_actions must include no_controlled_apply"


def test_p179_forbidden_no_deployment(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_deployment") is not None, "explicit_forbidden_actions must include no_deployment"


def test_p179_forbidden_no_new_strategy(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_new_strategy") is not None, "explicit_forbidden_actions must include no_new_strategy"


def test_p179_forbidden_no_research_rerun(artifact):
    fa = artifact.get("explicit_forbidden_actions", {})
    assert fa.get("no_power_lotto_research_rerun") is not None, (
        "explicit_forbidden_actions must include no_power_lotto_research_rerun"
    )


# ── Governance framing ────────────────────────────────────────────────────

def test_p179_governance_framing_present(artifact):
    assert "required_governance_framing" in artifact


def test_p179_p178a_closure_active(artifact):
    rgf = artifact.get("required_governance_framing", {})
    assert rgf.get("p178a_closure_policy_active") or "p178a" in str(rgf).lower(), (
        "governance_framing must confirm P178A closure policy active"
    )


# ── Governance confirmations ───────────────────────────────────────────────

def test_p179_no_db_write(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_db_write") is True


def test_p179_no_merge(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_merge") is True


def test_p179_no_controlled_apply(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_controlled_apply") is True


def test_p179_no_champion_promotion(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_champion_promotion") is True


def test_p179_no_deployment(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_deployment") is True


def test_p179_no_wagering(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("no_wagering_recommendations") is True


def test_p179_db_unchanged(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("db_unchanged") is True
    assert gov.get("db_rows_before") == EXPECTED_DB_ROWS
    assert gov.get("db_rows_after") == EXPECTED_DB_ROWS


def test_p179_power_lotto_closed_in_gov(artifact):
    gov = artifact.get("governance_confirmations", {})
    assert gov.get("power_lotto_active_research_closed") is True


# ── Next task ──────────────────────────────────────────────────────────────

def test_p179_next_task_blocked(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


# ── Forbidden strings ─────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p179_no_forbidden_strings_json(artifact, forbidden):
    text = json.dumps(artifact).lower()
    assert forbidden.lower() not in text, f"Forbidden in JSON: {forbidden!r}"


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p179_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), f"Forbidden in MD: {forbidden!r}"


# ── MD content ────────────────────────────────────────────────────────────

def test_p179_md_has_classification(md_text):
    assert EXPECTED_FINAL_CLASSIFICATION in md_text


def test_p179_md_has_options_abcd(md_text):
    for opt in ["Option A", "Option B", "Option C", "Option D"]:
        assert opt in md_text, f"MD must mention {opt}"


def test_p179_md_option_d_not_recommended(md_text):
    lower = md_text.lower()
    assert "option d" in lower and "not recommended" in lower


def test_p179_md_has_p180(md_text):
    assert "P180" in md_text


def test_p179_md_has_blocked(md_text):
    assert "BLOCKED" in md_text


# ── Active task ────────────────────────────────────────────────────────────

def test_p179_active_task_p179_present(active_task_text):
    assert "P179" in active_task_text


def test_p179_active_task_p180_blocked(active_task_text):
    assert "P180" in active_task_text
    assert "blocked" in active_task_text.lower() or "BLOCKED" in active_task_text


# ── Roadmap / CTO ──────────────────────────────────────────────────────────

def test_p179_roadmap_p179_present(roadmap_text):
    assert "P179" in roadmap_text


def test_p179_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    for s in ["success-rate method found", "proven method", "method found"]:
        assert s not in lower


def test_p179_cto_mentions_p179(cto_text):
    assert "P179" in cto_text


def test_p179_cto_no_edge_claim(cto_text):
    lower = cto_text.lower()
    for s in ["success-rate method found", "proven method", "r2 confirms edge"]:
        assert s not in lower


# ── DB rows unchanged ─────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p179_db_rows_unchanged():
    assert DB_PATH.exists()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == EXPECTED_DB_ROWS
