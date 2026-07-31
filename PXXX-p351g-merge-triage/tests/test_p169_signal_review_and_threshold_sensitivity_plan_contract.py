"""P169 Signal Review and Threshold Sensitivity Plan — contract tests."""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = ROOT / "outputs/research/power_lotto/p169_signal_review_and_threshold_sensitivity_plan_20260531.json"
ARTIFACT_MD = ROOT / "outputs/research/power_lotto/p169_signal_review_and_threshold_sensitivity_plan_20260531.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"
ROADMAP = ROOT / "00-Plan/roadmap/roadmap.md"
CTO = ROOT / "00-Plan/roadmap/CTO-Analysis.md"

REQUIRED_AUTHORIZATION_PHRASE = (
    "YES produce P169 signal review and threshold sensitivity plan only, "
    "no rerun, no verdict change"
)

FORBIDDEN_STRINGS = [
    "success-rate method found",
    "confirmed edge",
    "guaranteed win",
    "champion promoted",
    "db migrated",
    "reconcile complete",
    "controlled_apply authorized",
    "split resolved",
    "main reconciled",
    "strategy deployed",
    "real-money advice",
    "p167 passed",
    "window 2 passed",
]


@pytest.fixture
def artifact():
    assert ARTIFACT_JSON.exists(), f"P169 JSON artifact not found: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture
def md_text():
    assert ARTIFACT_MD.exists(), f"P169 MD artifact not found: {ARTIFACT_MD}"
    return ARTIFACT_MD.read_text(encoding="utf-8")


@pytest.fixture
def active_task_text():
    assert ACTIVE_TASK.exists()
    return ACTIVE_TASK.read_text(encoding="utf-8")


@pytest.fixture
def roadmap_text():
    assert ROADMAP.exists()
    return ROADMAP.read_text(encoding="utf-8")


@pytest.fixture
def cto_text():
    assert CTO.exists()
    return CTO.read_text(encoding="utf-8")


# ── Existence ─────────────────────────────────────────────────────────────────

def test_p169_json_artifact_exists():
    assert ARTIFACT_JSON.exists()


def test_p169_md_artifact_exists():
    assert ARTIFACT_MD.exists()


# ── Final classification ──────────────────────────────────────────────────────

def test_p169_final_classification(artifact):
    assert artifact["final_classification"] == "P169_POWER_LOTTO_SIGNAL_REVIEW_AND_THRESHOLD_SENSITIVITY_PLAN_READY"


def test_p169_task_field(artifact):
    assert artifact["task"] == "P169_POWER_LOTTO_SIGNAL_REVIEW_AND_THRESHOLD_SENSITIVITY_PLAN_ONLY"


def test_p169_plan_only_flag(artifact):
    assert artifact["plan_only"] is True


# ── Authorization phrase ──────────────────────────────────────────────────────

def test_p169_authorization_phrase_detected(artifact):
    assert artifact["authorization_phrase_detected"] == REQUIRED_AUTHORIZATION_PHRASE


def test_p169_authorization_phrase_in_md(md_text):
    assert REQUIRED_AUTHORIZATION_PHRASE in md_text or "no rerun, no verdict change" in md_text


# ── Phase 0 verification ──────────────────────────────────────────────────────

def test_p169_phase0_all_checks_passed(artifact):
    assert artifact["phase_0_verification"]["all_checks_passed"] is True


def test_p169_phase0_authorization_phrase_present(artifact):
    assert artifact["phase_0_verification"]["authorization_phrase_present"] is True


def test_p169_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["db_rows_before"] == 94924
    assert artifact["phase_0_verification"]["db_rows_after"] == 94924
    assert artifact["phase_0_verification"]["db_unchanged"] is True


def test_p169_phase0_all_tests_pass(artifact):
    ph0 = artifact["phase_0_verification"]
    for key in ["p161_test","p162_test","p163_test","p164_test","p165b_test",
                "p166_test","p167_test","p168_test"]:
        assert ph0[key] == "PASS", f"{key} not PASS"


# ── P167 NULL conclusion preserved ───────────────────────────────────────────

def test_p169_p167_null_classification_preserved(artifact):
    assert artifact["p167_summary"]["final_classification"] == "P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND"
    assert artifact["p167_summary"]["null_result"] is True


def test_p169_p167_module_f_not_passed(artifact):
    assert artifact["p167_summary"]["module_f_pass_final_gate"] is False
    assert artifact["p167_summary"]["module_f_oos_window_2_status"] == "INSUFFICIENT_OOS_DATA"
    assert artifact["p167_summary"]["module_f_oos_window_2_draws"] < 500


def test_p169_null_conclusion_preserved_field(artifact):
    nc = artifact["p167_null_conclusion_preserved"]
    assert nc["no_retroactive_reclassification"] is True
    assert nc["no_rerun_of_p167"] is True
    assert nc["no_verdict_change"] is True


# ── Threshold sensitivity plan ────────────────────────────────────────────────

def test_p169_threshold_sensitivity_plan_present(artifact):
    assert "threshold_sensitivity_plan" in artifact
    plan = artifact["threshold_sensitivity_plan"]
    assert "objective" in plan
    assert "allowed_scenarios" in plan
    assert "forbidden_future_interpretations" in plan


def test_p169_threshold_scenarios_pre_declared(artifact):
    scenarios = artifact["threshold_sensitivity_plan"]["allowed_scenarios"]
    thresholds = [s["threshold"] for s in scenarios]
    # Must include the reference 500 and at least some sensitivity thresholds
    assert 500 in thresholds
    assert len(thresholds) >= 3


def test_p169_threshold_scenarios_labeled_correctly(artifact):
    scenarios = artifact["threshold_sensitivity_plan"]["allowed_scenarios"]
    for s in scenarios:
        if s["threshold"] != 500:
            assert "SENSITIVITY" in s["label"].upper() or "SENSITIVITY" in s.get("label","").upper()


def test_p169_threshold_original_protocol_labeled(artifact):
    scenarios = artifact["threshold_sensitivity_plan"]["allowed_scenarios"]
    original = [s for s in scenarios if s["threshold"] == 500]
    assert len(original) == 1
    assert "ORIGINAL" in original[0]["label"].upper() or "REFERENCE" in original[0]["label"].upper()


def test_p169_threshold_forbidden_interpretations_present(artifact):
    forbidden = artifact["threshold_sensitivity_plan"]["forbidden_future_interpretations"]
    combined = " ".join(forbidden).lower()
    assert "cannot" in combined or "may not" in combined
    assert "p167" in combined or "final gate" in combined.replace("_"," ")


# ── Signal tracking plan ──────────────────────────────────────────────────────

def test_p169_signal_tracking_plan_present(artifact):
    assert "signal_tracking_plan" in artifact
    plan = artifact["signal_tracking_plan"]
    assert "objective" in plan
    assert "target_signals" in plan
    assert "tracking_method" in plan
    assert "pre_registration_rules" in plan


def test_p169_signal_tracking_has_module_a_and_e(artifact):
    signals = artifact["signal_tracking_plan"]["target_signals"]
    signal_ids = [s["signal_id"] for s in signals]
    assert any("consensus" in sid.lower() or "_a" in sid.lower() for sid in signal_ids)
    assert any("main" in sid.lower() or "_e" in sid.lower() for sid in signal_ids)


def test_p169_signal_tracking_prospective_only(artifact):
    tm = artifact["signal_tracking_plan"]["tracking_method"]
    window_type = tm.get("window_type", "").lower()
    assert "prospective" in window_type


def test_p169_signal_tracking_minimum_draws(artifact):
    tm = artifact["signal_tracking_plan"]["tracking_method"]
    assert tm.get("minimum_prospective_draws_for_evaluation", 0) >= 100


def test_p169_signal_tracking_statistical_unit_per_draw(artifact):
    tm = artifact["signal_tracking_plan"]["tracking_method"]
    unit = tm.get("statistical_unit", "").lower()
    assert "draw" in unit
    assert "not per bet" in unit or "not" in unit


def test_p169_signal_tracking_pre_registration_rules(artifact):
    rules = artifact["signal_tracking_plan"]["pre_registration_rules"]
    combined = " ".join(rules).lower()
    assert "before" in combined or "pre" in combined
    assert "prospective" in combined or "future" in combined


# ── P170 implementation boundary ─────────────────────────────────────────────

def test_p169_p170_boundary_present(artifact):
    assert "p170_implementation_boundary" in artifact
    boundary = artifact["p170_implementation_boundary"]
    assert "allowed" in boundary
    assert "forbidden" in boundary
    assert "what_p170_cannot_claim" in boundary


def test_p169_p170_forbidden_includes_no_db_write(artifact):
    forbidden = " ".join(artifact["p170_implementation_boundary"]["forbidden"]).lower()
    assert "db write" in forbidden or "new row" in forbidden


def test_p169_p170_forbidden_includes_no_verdict_change(artifact):
    forbidden = " ".join(artifact["p170_implementation_boundary"]["forbidden"]).lower()
    assert "p167" in forbidden or "verdict" in forbidden or "classification" in forbidden


def test_p169_p170_cannot_claim_without_oos(artifact):
    cannot = " ".join(artifact["p170_implementation_boundary"]["what_p170_cannot_claim"]).lower()
    assert "sensitivity" in cannot or "prospective" in cannot
    assert "not" in cannot or "may not" in cannot or "cannot" in cannot


# ── No-action confirmations ───────────────────────────────────────────────────

def test_p169_no_db_write(artifact):
    assert artifact["no_action_confirmations"]["no_db_write"] is True


def test_p169_no_rerun_of_p167(artifact):
    assert artifact["no_action_confirmations"]["no_rerun_of_p167"] is True


def test_p169_no_verdict_change(artifact):
    assert artifact["no_action_confirmations"]["no_verdict_change"] is True


def test_p169_no_retroactive_499(artifact):
    assert artifact["no_action_confirmations"]["no_retroactive_499_reclassification"] is True


def test_p169_no_champion(artifact):
    assert artifact["no_action_confirmations"]["no_champion_promotion"] is True


def test_p169_no_commit(artifact):
    assert artifact["no_action_confirmations"]["no_commit"] is True


def test_p169_no_betting(artifact):
    assert artifact["no_action_confirmations"]["no_betting_advice"] is True


def test_p169_no_win_guarantee(artifact):
    assert artifact["no_action_confirmations"]["no_win_guarantee"] is True


# ── Next task and state ───────────────────────────────────────────────────────

def test_p169_next_task_is_p170(artifact):
    assert artifact["next_task"] == "P170_POWER_LOTTO_THRESHOLD_SENSITIVITY_AND_SIGNAL_TRACKING_READ_ONLY"


def test_p169_next_state_waiting(artifact):
    assert artifact["next_task_state"] == "WAITING_FOR_USER_AUTHORIZATION"


def test_p169_md_contains_waiting_state(md_text):
    assert "WAITING_FOR_USER_AUTHORIZATION" in md_text


# ── Governance invariants ─────────────────────────────────────────────────────

def test_p169_null_result_stands(artifact):
    gov = artifact["governance_invariants"]
    assert gov["p167_null_result_stands"] is True
    assert gov["no_success_rate_method_found"] is True


# ── active_task / roadmap / CTO content ──────────────────────────────────────

def test_p169_active_task_mentions_p170(active_task_text):
    assert "P170" in active_task_text


def test_p169_active_task_p170_blocked(active_task_text):
    lower = active_task_text.lower()
    assert "blocked" in lower or "authorization" in lower


def test_p169_active_task_p169_present(active_task_text):
    assert "P169" in active_task_text


def test_p169_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    assert "success-rate method found" not in lower
    assert "success rate found" not in lower


def test_p169_roadmap_mentions_p169(roadmap_text):
    assert "P169" in roadmap_text


def test_p169_cto_mentions_p169(cto_text):
    lower = cto_text.lower()
    assert "p169" in lower


def test_p169_cto_no_confirmed_edge(cto_text):
    lower = cto_text.lower()
    assert "confirmed edge" not in lower


# ── DB rows unchanged ─────────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p169_db_rows_unchanged():
    import sqlite3
    db_path = ROOT / "lottery_api/data/lottery_v2.db"
    con = sqlite3.connect(str(db_path))
    count = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    con.close()
    assert count == 94924


# ── Forbidden strings ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p169_no_forbidden_strings_json(artifact, forbidden):
    artifact_str = json.dumps(artifact).lower()
    assert forbidden.lower() not in artifact_str, (
        f"Forbidden string found in P169 JSON: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p169_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P169 MD: {forbidden!r}"
    )
