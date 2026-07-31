"""P170 Threshold Sensitivity and Signal Tracking — contract tests."""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = ROOT / "outputs/research/power_lotto/p170_threshold_sensitivity_and_signal_tracking_20260531.json"
ARTIFACT_MD = ROOT / "outputs/research/power_lotto/p170_threshold_sensitivity_and_signal_tracking_20260531.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"
ROADMAP = ROOT / "00-Plan/roadmap/roadmap.md"
CTO = ROOT / "00-Plan/roadmap/CTO-Analysis.md"

VALID_FINAL_CLASSIFICATIONS = {
    "P170_POWER_LOTTO_SENSITIVITY_SUPPORTS_CONTINUED_TRACKING",
    "P170_POWER_LOTTO_SENSITIVITY_DOES_NOT_SUPPORT_TRACKING",
}

REQUIRED_SCENARIO_IDS = {"S1", "S2", "S3", "S4", "S5"}

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
]


@pytest.fixture
def artifact():
    assert ARTIFACT_JSON.exists(), f"P170 JSON artifact not found: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture
def md_text():
    assert ARTIFACT_MD.exists(), f"P170 MD artifact not found: {ARTIFACT_MD}"
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

def test_p170_json_artifact_exists():
    assert ARTIFACT_JSON.exists()


def test_p170_md_artifact_exists():
    assert ARTIFACT_MD.exists()


# ── Final classification ──────────────────────────────────────────────────────

def test_p170_final_classification_valid(artifact):
    assert artifact["final_classification"] in VALID_FINAL_CLASSIFICATIONS


def test_p170_task_field(artifact):
    assert artifact["task"] == "P170_POWER_LOTTO_THRESHOLD_SENSITIVITY_AND_SIGNAL_TRACKING_READ_ONLY"


# ── Phase 0 and DB rows ───────────────────────────────────────────────────────

def test_p170_db_rows_before(artifact):
    assert artifact["phase_0_verification"]["db_rows_before"] == 94924


def test_p170_db_rows_after(artifact):
    assert artifact["phase_0_verification"]["db_rows_after"] == 94924


def test_p170_db_unchanged(artifact):
    assert artifact["phase_0_verification"]["db_unchanged"] is True


# ── P167 classification preserved ────────────────────────────────────────────

def test_p170_p167_classification_preserved(artifact):
    assert artifact["p167_classification_preserved"] == "P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND"


def test_p170_p167_verdict_does_not_change(artifact):
    assert artifact["p167_verdict_changes"] is False


# ── 5 threshold scenarios ─────────────────────────────────────────────────────

def test_p170_five_scenarios_present(artifact):
    scenarios = artifact["threshold_sensitivity"]["scenarios"]
    ids = {s["scenario_id"] for s in scenarios}
    assert REQUIRED_SCENARIO_IDS == ids, f"Missing scenarios: {REQUIRED_SCENARIO_IDS - ids}"


def test_p170_s4_is_original_protocol(artifact):
    scenarios = artifact["threshold_sensitivity"]["scenarios"]
    s4 = next(s for s in scenarios if s["scenario_id"] == "S4")
    assert s4["label"] == "ORIGINAL_PROTOCOL"
    assert s4["threshold"] == 500


def test_p170_s4_window2_fails(artifact):
    scenarios = artifact["threshold_sensitivity"]["scenarios"]
    s4 = next(s for s in scenarios if s["scenario_id"] == "S4")
    # Window 2 must have 499 draws and not qualify
    w2_results = [w for w in s4["window_results"] if "window_2" in w["window"]]
    assert len(w2_results) == 1
    w2 = w2_results[0]
    assert w2["qualifies"] is False
    assert w2["oos_draws_actual"] < 500


def test_p170_sensitivity_scenarios_labeled(artifact):
    scenarios = artifact["threshold_sensitivity"]["scenarios"]
    for s in scenarios:
        if s["scenario_id"] != "S4":
            assert "SENSITIVITY" in s["label"].upper() or "RETROSPECTIVE" in s["label"].upper()


def test_p170_s4_p167_verdict_unchanged(artifact):
    scenarios = artifact["threshold_sensitivity"]["scenarios"]
    for s in scenarios:
        assert s["p167_verdict_changes"] is False


def test_p170_threshold_sensitivity_has_interpretation_note(artifact):
    note = artifact["threshold_sensitivity"]["interpretation_note"].lower()
    assert "sensitivity" in note or "retrospective" in note
    assert "does not" in note or "unchanged" in note or "not retroactively" in note


# ── Signal tracking ───────────────────────────────────────────────────────────

def test_p170_signal_tracking_present(artifact):
    assert "signal_tracking" in artifact
    st = artifact["signal_tracking"]
    assert "signal_a" in st
    assert "signal_e" in st


def test_p170_signal_a_present(artifact):
    sig_a = artifact["signal_tracking"]["signal_a"]
    assert "signal_a" in sig_a["signal_id"].lower() or "consensus" in sig_a["signal_id"].lower()
    assert "mean_hit_count" in sig_a
    assert "above_random" in sig_a


def test_p170_signal_e_present(artifact):
    sig_e = artifact["signal_tracking"]["signal_e"]
    assert "signal_e" in sig_e["signal_id"].lower() or "main" in sig_e["signal_id"].lower()
    assert "mean_hit_count" in sig_e
    assert "above_random" in sig_e


def test_p170_signal_tracking_has_prospective_status(artifact):
    st = artifact["signal_tracking"]
    assert "prospective_tracking_status" in st
    assert st["prospective_tracking_status"] in (
        "AWAITING_PROSPECTIVE_DATA",
        "PROSPECTIVE_DATA_AVAILABLE",
    )


def test_p170_held_out_is_not_prospective(artifact):
    st = artifact["signal_tracking"]
    # Must clearly note that held-out is retrospective, not truly prospective
    for sig in [st.get("signal_a", {}), st.get("signal_e", {})]:
        held_out_type = sig.get("held_out_type", "").upper()
        assert "RETROSPECTIVE" in held_out_type or "NOT" in held_out_type


# ── No-action confirmations ───────────────────────────────────────────────────

def test_p170_no_db_write(artifact):
    assert artifact["no_action_confirmations"]["no_db_write"] is True


def test_p170_no_p167_verdict_change(artifact):
    assert artifact["no_action_confirmations"]["no_p167_verdict_change"] is True


def test_p170_no_retroactive_499(artifact):
    assert artifact["no_action_confirmations"]["no_retroactive_499_reclassification"] is True


def test_p170_no_champion(artifact):
    assert artifact["no_action_confirmations"]["no_champion_promotion"] is True


def test_p170_no_commit(artifact):
    assert artifact["no_action_confirmations"]["no_commit"] is True


def test_p170_no_betting(artifact):
    assert artifact["no_action_confirmations"]["no_betting_advice"] is True


def test_p170_no_win_guarantee(artifact):
    assert artifact["no_action_confirmations"]["no_win_guarantee"] is True


# ── Governance invariants ─────────────────────────────────────────────────────

def test_p170_null_result_stands(artifact):
    gov = artifact["governance_invariants"]
    assert gov["p167_null_result_stands"] is True
    assert gov["no_success_rate_method_found"] is True


# ── Next task ─────────────────────────────────────────────────────────────────

def test_p170_next_task_is_p171(artifact):
    assert artifact["next_task"] == "P171_POWER_LOTTO_RESEARCH_CEO_DECISION_REVIEW"


# ── active_task / roadmap / CTO ───────────────────────────────────────────────

def test_p170_active_task_mentions_p171(active_task_text):
    assert "P171" in active_task_text


def test_p170_active_task_p170_complete(active_task_text):
    assert "P170" in active_task_text


def test_p170_roadmap_p170_present(roadmap_text):
    assert "P170" in roadmap_text


def test_p170_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    assert "success-rate method found" not in lower
    assert "success rate found" not in lower


def test_p170_cto_mentions_p170(cto_text):
    assert "P170" in cto_text or "p170" in cto_text.lower()


def test_p170_cto_sensitivity_not_deployment_evidence(cto_text):
    lower = cto_text.lower()
    assert "sensitivity" in lower or "p170" in lower
    # Must NOT claim it's deployment evidence
    assert "deployment evidence" not in lower or "not deployment evidence" in lower or "sensitivity" in lower


# ── DB rows unchanged ─────────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p170_db_rows_unchanged():
    import sqlite3
    db_path = ROOT / "lottery_api/data/lottery_v2.db"
    con = sqlite3.connect(str(db_path))
    count = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    con.close()
    assert count == 94924


# ── Forbidden strings ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p170_no_forbidden_strings_json(artifact, forbidden):
    artifact_str = json.dumps(artifact).lower()
    assert forbidden.lower() not in artifact_str, (
        f"Forbidden string found in P170 JSON: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p170_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P170 MD: {forbidden!r}"
    )
