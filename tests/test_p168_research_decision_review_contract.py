"""P168 POWER_LOTTO Research Decision Review — contract tests."""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = ROOT / "outputs/research/power_lotto/p168_research_decision_review_20260531.json"
ARTIFACT_MD = ROOT / "outputs/research/power_lotto/p168_research_decision_review_20260531.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"
ROADMAP = ROOT / "00-Plan/roadmap/roadmap.md"
CTO = ROOT / "00-Plan/roadmap/CTO-Analysis.md"

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
    "499.*pass",
]

REQUIRED_OPTIONS = {"A", "B", "C", "D"}


@pytest.fixture
def artifact():
    assert ARTIFACT_JSON.exists(), f"P168 JSON artifact not found: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture
def md_text():
    assert ARTIFACT_MD.exists(), f"P168 MD artifact not found: {ARTIFACT_MD}"
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

def test_p168_json_artifact_exists():
    assert ARTIFACT_JSON.exists()


def test_p168_md_artifact_exists():
    assert ARTIFACT_MD.exists()


# ── Final classification ──────────────────────────────────────────────────────

def test_p168_final_classification(artifact):
    assert artifact["final_classification"] == "P168_POWER_LOTTO_RESEARCH_DECISION_REVIEW_READY"


def test_p168_task_field(artifact):
    assert artifact["task"] == "P168_POWER_LOTTO_RESEARCH_DECISION_REVIEW"


# ── Phase 0 verification ──────────────────────────────────────────────────────

def test_p168_phase0_all_checks_passed(artifact):
    assert artifact["phase_0_verification"]["all_checks_passed"] is True


def test_p168_db_rows_before(artifact):
    assert artifact["phase_0_verification"]["db_rows_before"] == 94924


def test_p168_db_rows_after(artifact):
    assert artifact["phase_0_verification"]["db_rows_after"] == 94924


def test_p168_db_unchanged(artifact):
    assert artifact["phase_0_verification"]["db_unchanged"] is True


def test_p168_p167_script_reruns(artifact):
    assert artifact["phase_0_verification"]["p167_script_reruns_successfully"] is True


# ── P167 classification preserved ────────────────────────────────────────────

def test_p168_p167_classification_documented(artifact):
    p167_cls = artifact["p167_summary"]["p167_final_classification"]
    assert p167_cls == "P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND"


def test_p168_p167_null_result_stands(artifact):
    assert artifact["p167_summary"]["null_result"] is True
    assert artifact["p167_summary"]["defensible_edge_found"] is False


def test_p168_module_f_failure_reason_documented(artifact):
    f_summary = artifact["p167_summary"]["module_results_summary"]["module_f"]
    assert "reason_failed" in f_summary
    reason = f_summary["reason_failed"].lower()
    assert "499" in reason or "window 2" in reason.replace("_", " ")
    assert f_summary["pass_final_gate"] is False


def test_p168_oos_window_2_insufficient(artifact):
    f = artifact["p167_summary"]["module_results_summary"]["module_f"]
    assert f["oos_window_2"]["status"] == "INSUFFICIENT_OOS_DATA"
    assert f["oos_window_2"]["draws"] < f["oos_window_2"]["required_minimum"]


# ── Decision section ──────────────────────────────────────────────────────────

def test_p168_decision_null_result_stands(artifact):
    assert artifact["decision"]["p167_null_result_stands"] is True
    assert artifact["decision"]["defensible_edge_found"] is False


def test_p168_decision_no_retroactive_reclassification(artifact):
    dec = artifact["decision"]
    # Must note that 499-draw window cannot be reclassified
    caveat = dec.get("interpretation_caveat", "").lower()
    assert "499" in caveat or "retroactive" in caveat or "threshold" in caveat


# ── Four options ─────────────────────────────────────────────────────────────

def test_p168_four_options_present(artifact):
    options = artifact["options_evaluation"]
    labels = {o["option"] for o in options}
    assert REQUIRED_OPTIONS == labels, f"Missing options: {REQUIRED_OPTIONS - labels}"


def test_p168_option_a_wait_for_draws(artifact):
    opt_a = next(o for o in artifact["options_evaluation"] if o["option"] == "A")
    assert "WAIT" in opt_a["label"].upper() or "DRAW" in opt_a["label"].upper()
    assert "pros" in opt_a and "cons" in opt_a and "risk" in opt_a


def test_p168_option_b_threshold_review(artifact):
    opt_b = next(o for o in artifact["options_evaluation"] if o["option"] == "B")
    assert "THRESHOLD" in opt_b["label"].upper() or "PLAN" in opt_b["label"].upper()
    assert "pros" in opt_b


def test_p168_option_c_signal_tracking(artifact):
    opt_c = next(o for o in artifact["options_evaluation"] if o["option"] == "C")
    assert "NARROW" in opt_c["label"].upper() or "TRACK" in opt_c["label"].upper() or "SIGNAL" in opt_c["label"].upper()
    assert "pros" in opt_c


def test_p168_option_d_pause(artifact):
    opt_d = next(o for o in artifact["options_evaluation"] if o["option"] == "D")
    assert "PAUSE" in opt_d["label"].upper() or "HALT" in opt_d["label"].upper()
    assert "pros" in opt_d


# ── Recommended option ────────────────────────────────────────────────────────

def test_p168_recommended_option_present(artifact):
    assert "recommended_option" in artifact
    rec = artifact["recommended_option"]
    assert "recommendation" in rec
    assert "proposed_next_task" in rec
    assert "reasoning" in rec


def test_p168_recommended_next_task_is_p169(artifact):
    rec = artifact["recommended_option"]
    assert rec["proposed_next_task"] == "P169_POWER_LOTTO_SIGNAL_REVIEW_AND_THRESHOLD_SENSITIVITY_PLAN_ONLY"


def test_p168_p169_scope_constraints_present(artifact):
    rec = artifact["recommended_option"]
    assert "p169_scope_constraints" in rec
    constraints = " ".join(rec["p169_scope_constraints"]).lower()
    assert "plan" in constraints
    assert "not" in constraints or "must not" in constraints or "no" in constraints


# ── Next state WAITING_FOR_USER_AUTHORIZATION ─────────────────────────────────

def test_p168_next_task_is_p169(artifact):
    assert artifact["next_task"] == "P169_POWER_LOTTO_SIGNAL_REVIEW_AND_THRESHOLD_SENSITIVITY_PLAN_ONLY"


def test_p168_next_state_waiting(artifact):
    assert artifact["next_task_state"] == "WAITING_FOR_USER_AUTHORIZATION"


def test_p168_md_contains_waiting_state(md_text):
    assert "WAITING_FOR_USER_AUTHORIZATION" in md_text


# ── No-action confirmations ───────────────────────────────────────────────────

def test_p168_no_db_write(artifact):
    assert artifact["no_action_confirmations"]["no_db_write"] is True


def test_p168_no_p167_rerun_different_verdict(artifact):
    assert artifact["no_action_confirmations"]["no_p167_rerun_with_different_verdict"] is True


def test_p168_no_499_reclassified(artifact):
    assert artifact["no_action_confirmations"]["no_499_draw_window_reclassified_as_pass"] is True


def test_p168_no_champion(artifact):
    assert artifact["no_action_confirmations"]["no_champion_promotion"] is True


def test_p168_no_commit(artifact):
    assert artifact["no_action_confirmations"]["no_commit"] is True


def test_p168_no_betting(artifact):
    assert artifact["no_action_confirmations"]["no_betting_advice"] is True


def test_p168_no_win_guarantee(artifact):
    assert artifact["no_action_confirmations"]["no_win_guarantee"] is True


# ── Governance invariants ─────────────────────────────────────────────────────

def test_p168_null_result_still_current(artifact):
    gov = artifact["governance_invariants"]
    assert gov["p167_null_result_stands"] is True
    assert gov["no_success_rate_method_found"] is True


def test_p168_governance_split_unresolved(artifact):
    assert "UNRESOLVED" in artifact["governance_invariants"]["main_zen_gates_split"]


# ── active_task / roadmap / CTO content ──────────────────────────────────────

def test_p168_active_task_mentions_p169(active_task_text):
    assert "P169" in active_task_text


def test_p168_active_task_p169_blocked(active_task_text):
    lower = active_task_text.lower()
    assert "blocked" in lower or "authorization" in lower


def test_p168_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    assert "success-rate method found" not in lower
    assert "success rate found" not in lower


def test_p168_roadmap_mentions_p168(roadmap_text):
    assert "P168" in roadmap_text


def test_p168_cto_positive_signal_not_confirmed(cto_text):
    lower = cto_text.lower()
    assert "p168" in lower
    # Must not claim confirmed edge
    assert "confirmed edge" not in lower
    assert "success-rate method found" not in lower


# ── DB rows unchanged ─────────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p168_db_rows_unchanged():
    import sqlite3
    db_path = ROOT / "lottery_api/data/lottery_v2.db"
    con = sqlite3.connect(str(db_path))
    count = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    con.close()
    assert count == 94924


# ── Forbidden strings ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", [s for s in FORBIDDEN_STRINGS if ".*" not in s])
def test_p168_no_forbidden_strings_json(artifact, forbidden):
    artifact_str = json.dumps(artifact).lower()
    assert forbidden.lower() not in artifact_str, (
        f"Forbidden string found in P168 JSON: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", [s for s in FORBIDDEN_STRINGS if ".*" not in s])
def test_p168_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P168 MD: {forbidden!r}"
    )
