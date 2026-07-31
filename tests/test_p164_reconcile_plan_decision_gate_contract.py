"""P164 Reconcile Plan Decision Gate — contract tests."""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = ROOT / "outputs/research/power_lotto/p164_reconcile_plan_decision_gate_20260531.json"
ARTIFACT_MD = ROOT / "outputs/research/power_lotto/p164_reconcile_plan_decision_gate_20260531.md"

FORBIDDEN_STRINGS = [
    "reconcile complete",
    "db migrated",
    "champion promoted",
    "betting advice",
    "guaranteed win",
    "already authorized",
    "merge executed",
    "migration applied",
    "rows inserted",
    "schema migrated",
    "option c applied",
    "option a executed",
    "option b executed",
]

REQUIRED_AUTHORIZATION_PHRASES = [
    "YES proceed with Option A code/docs/tests-only reconcile, no DB write",
    "YES designate zen-gates as canonical research dataset",
    "YES prepare controlled DB/data migration plan only, no apply",
]


@pytest.fixture
def artifact():
    assert ARTIFACT_JSON.exists(), f"P164 JSON artifact not found: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture
def md_text():
    assert ARTIFACT_MD.exists(), f"P164 MD artifact not found: {ARTIFACT_MD}"
    return ARTIFACT_MD.read_text(encoding="utf-8")


# ── Existence ────────────────────────────────────────────────────────────────

def test_p164_json_artifact_exists():
    assert ARTIFACT_JSON.exists()


def test_p164_md_artifact_exists():
    assert ARTIFACT_MD.exists()


# ── Final classification ─────────────────────────────────────────────────────

def test_p164_final_classification(artifact):
    assert artifact["final_classification"] == "P164_RECONCILE_PLAN_DECISION_GATE_READY"


def test_p164_task_field(artifact):
    assert artifact["task"] == "P164_RECONCILE_PLAN_DECISION_GATE"


# ── Phase 0 verification ─────────────────────────────────────────────────────

def test_p164_phase0_all_checks_passed(artifact):
    ph0 = artifact["phase_0_verification"]
    assert ph0["all_checks_passed"] is True


def test_p164_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["db_rows"] == 94924


def test_p164_phase0_drift_guard_pass(artifact):
    assert artifact["phase_0_verification"]["drift_guard"] == "PASS"


def test_p164_phase0_p161_p162_p163_pass(artifact):
    ph0 = artifact["phase_0_verification"]
    assert ph0["p161_test"] == "PASS"
    assert ph0["p162_test"] == "PASS"
    assert ph0["p163_test"] == "PASS"


# ── P163 audit summary ────────────────────────────────────────────────────────

def test_p164_p163_audit_summary_present(artifact):
    assert "p163_audit_summary" in artifact
    summary = artifact["p163_audit_summary"]
    assert summary["zen_gates_db_rows"] == 94924
    assert summary["main_db_rows"] == 54462
    assert summary["row_delta"] == 40462


def test_p164_p163_schema_diff_documented(artifact):
    summary = artifact["p163_audit_summary"]
    assert summary["zen_gates_bet_index_present"] is True
    assert summary["main_bet_index_present"] is False


# ── Option A/B/C comparison ──────────────────────────────────────────────────

def test_p164_option_comparison_present(artifact):
    assert "option_comparison_table" in artifact
    options = artifact["option_comparison_table"]
    option_labels = {o["option"] for o in options}
    assert "A" in option_labels
    assert "B" in option_labels
    assert "C" in option_labels


def test_p164_option_a_risk_low(artifact):
    option_a = next(o for o in artifact["option_comparison_table"] if o["option"] == "A")
    assert option_a["risk_level"] == "LOW"
    assert option_a["db_impact"] == "NONE — main DB remains at 54462 rows, no bet_index column added"


def test_p164_option_b_risk_medium(artifact):
    option_b = next(o for o in artifact["option_comparison_table"] if o["option"] == "B")
    assert option_b["risk_level"] == "MEDIUM"


def test_p164_option_c_risk_high(artifact):
    option_c = next(o for o in artifact["option_comparison_table"] if o["option"] == "C")
    assert option_c["risk_level"] == "HIGH"
    assert "warning" in option_c
    assert "plan" in option_c["warning"].lower() or "PLAN" in option_c["warning"]


# ── Authorization phrases ────────────────────────────────────────────────────

def test_p164_authorization_phrases_present(artifact):
    assert "authorization_phrases" in artifact
    phrases = artifact["authorization_phrases"]
    assert phrases["option_a"] == "YES proceed with Option A code/docs/tests-only reconcile, no DB write"
    assert phrases["option_b"] == "YES designate zen-gates as canonical research dataset"
    assert phrases["option_c_plan_only"] == "YES prepare controlled DB/data migration plan only, no apply"


def test_p164_authorization_phrases_in_md(md_text):
    for phrase in REQUIRED_AUTHORIZATION_PHRASES:
        assert phrase in md_text, f"Authorization phrase not found in MD: {phrase!r}"


# ── Next state WAITING_FOR_USER_AUTHORIZATION ────────────────────────────────

def test_p164_next_step_waiting(artifact):
    assert artifact["next_step_state"] == "WAITING_FOR_USER_AUTHORIZATION"


def test_p164_md_contains_waiting_state(md_text):
    assert "WAITING_FOR_USER_AUTHORIZATION" in md_text


# ── No-action confirmations ──────────────────────────────────────────────────

def test_p164_no_db_write_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_db_write"] is True


def test_p164_no_merge_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_merge"] is True


def test_p164_no_commit_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_commit"] is True


def test_p164_no_push_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_push"] is True


def test_p164_no_champion_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_champion_promotion"] is True


def test_p164_no_controlled_apply_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_controlled_apply"] is True


def test_p164_no_betting_advice_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_betting_advice"] is True


def test_p164_no_win_guarantee_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_win_guarantee"] is True


# ── Recommended option present ────────────────────────────────────────────────

def test_p164_recommended_option_present(artifact):
    assert "recommended_option" in artifact
    rec = artifact["recommended_option"]
    assert rec["primary"] in ("A", "B")
    assert "reasoning" in rec


def test_p164_recommended_option_not_c_immediate(artifact):
    rec = artifact["recommended_option"]
    assert rec["primary"] != "C", "Immediate Option C is not recommended — must be deferred to P165"


# ── Rejected/deferred options ────────────────────────────────────────────────

def test_p164_rejected_deferred_options_present(artifact):
    assert "rejected_or_deferred_options" in artifact
    assert len(artifact["rejected_or_deferred_options"]) >= 1


# ── DB rows unchanged ────────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p164_db_rows_unchanged():
    import sqlite3
    db_path = ROOT / "lottery_api/data/lottery_v2.db"
    con = sqlite3.connect(str(db_path))
    count = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    con.close()
    assert count == 94924, f"DB rows changed from 94924 to {count}"


# ── Forbidden strings ────────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p164_no_forbidden_strings_json(artifact, forbidden):
    artifact_str = json.dumps(artifact).lower()
    assert forbidden.lower() not in artifact_str, (
        f"Forbidden string found in P164 JSON artifact: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p164_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P164 MD artifact: {forbidden!r}"
    )
