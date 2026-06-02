"""P167 POWER_LOTTO Ensemble/Voting Research — contract tests."""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = ROOT / "outputs/research/power_lotto/p167_ensemble_voting_research_20260531.json"
ARTIFACT_MD = ROOT / "outputs/research/power_lotto/p167_ensemble_voting_research_20260531.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"
ROADMAP = ROOT / "00-Plan/roadmap/roadmap.md"
CTO = ROOT / "00-Plan/roadmap/CTO-Analysis.md"

REQUIRED_MODULES = {"A", "B", "C", "D", "E", "F"}

VALID_FINAL_CLASSIFICATIONS = {
    "P167_POWER_LOTTO_DEFENSIBLE_EDGE_FOUND",
    "P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND",
}

FORBIDDEN_STRINGS = [
    "guaranteed win",
    "champion promoted",
    "db migrated",
    "reconcile complete",
    "controlled_apply authorized",
    "split resolved",
    "main reconciled",
    "strategy deployed",
    "real-money advice",
]


@pytest.fixture
def artifact():
    assert ARTIFACT_JSON.exists(), f"P167 JSON artifact not found: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture
def md_text():
    assert ARTIFACT_MD.exists(), f"P167 MD artifact not found: {ARTIFACT_MD}"
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

def test_p167_json_artifact_exists():
    assert ARTIFACT_JSON.exists()


def test_p167_md_artifact_exists():
    assert ARTIFACT_MD.exists()


# ── Final classification ──────────────────────────────────────────────────────

def test_p167_final_classification_valid(artifact):
    assert artifact["final_classification"] in VALID_FINAL_CLASSIFICATIONS


def test_p167_task_field(artifact):
    assert artifact["task"] == "P167_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_IMPLEMENTATION"


# ── Phase 0 verification ──────────────────────────────────────────────────────

def test_p167_db_rows_before(artifact):
    assert artifact["phase_0_verification"]["db_rows_before"] == 94924


def test_p167_db_rows_after(artifact):
    assert artifact["phase_0_verification"]["db_rows_after"] == 94924


def test_p167_db_unchanged(artifact):
    assert artifact["phase_0_verification"]["db_unchanged"] is True


# ── 6 module results ──────────────────────────────────────────────────────────

def test_p167_all_6_modules_present(artifact):
    mods = artifact["module_results"]
    for key in ["module_a", "module_b", "module_c", "module_d", "module_e", "module_f"]:
        assert key in mods, f"Missing {key} in module_results"


def test_p167_module_ids(artifact):
    mods = artifact["module_results"]
    ids = {v["module"] for v in mods.values()}
    assert REQUIRED_MODULES == ids


def test_p167_module_a_has_required_fields(artifact):
    a = artifact["module_results"]["module_a"]
    for field in ["mean_hit_count", "random_baseline", "z_vs_random", "p_raw_vs_random",
                  "above_random", "above_best_single", "leakage_caveat"]:
        assert field in a, f"Module A missing field: {field}"


def test_p167_module_f_has_walk_forward_results(artifact):
    f = artifact["module_results"]["module_f"]
    assert "window_results" in f
    assert "pass_final_gate" in f
    assert isinstance(f["window_results"], list)
    assert len(f["window_results"]) >= 1


def test_p167_module_f_oos_minimum_declared(artifact):
    f = artifact["module_results"]["module_f"]
    assert f.get("oos_minimum_draws_required", 0) >= 500


def test_p167_module_d_has_survivorship_caveat(artifact):
    d = artifact["module_results"]["module_d"]
    caveat_text = json.dumps(d).lower()
    assert "survivorship" in caveat_text or "selection bias" in caveat_text


def test_p167_module_b_is_descriptive(artifact):
    b = artifact["module_results"]["module_b"]
    assert "descriptive" in b.get("type", "").lower() or \
           "descriptive" in b.get("statistical_unit", "").lower()


# ── Statistical unit ──────────────────────────────────────────────────────────

def test_p167_statistical_unit_is_per_draw(artifact):
    unit = artifact["statistical_unit_declaration"].lower()
    assert "draw" in unit
    assert "not bet" in unit or "not per bet" in unit or "not" in unit


# ── Multiple-testing correction ───────────────────────────────────────────────

def test_p167_multiple_testing_correction_present(artifact):
    mt = artifact["multiple_testing_correction"]
    assert "method" in mt
    assert "bonferroni" in mt["method"].lower() or "bh" in mt["method"].lower()
    assert "family_size" in mt
    assert mt["family_size"] >= 1
    assert "corrections" in mt
    assert isinstance(mt["corrections"], list)


def test_p167_multiple_testing_family_declared_before_run(artifact):
    mt = artifact["multiple_testing_correction"]
    # Family must be > 0 (pre-declared)
    assert mt["family_size"] > 0


# ── No-action confirmations ───────────────────────────────────────────────────

def test_p167_no_db_write_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_db_write"] is True


def test_p167_no_champion_promotion(artifact):
    assert artifact["no_action_confirmations"]["no_champion_promotion"] is True


def test_p167_no_controlled_apply(artifact):
    assert artifact["no_action_confirmations"]["no_controlled_apply"] is True


def test_p167_no_commit(artifact):
    assert artifact["no_action_confirmations"]["no_commit"] is True


def test_p167_no_push(artifact):
    assert artifact["no_action_confirmations"]["no_push"] is True


def test_p167_no_win_guarantee(artifact):
    assert artifact["no_action_confirmations"]["no_win_guarantee"] is True


def test_p167_no_real_money(artifact):
    assert artifact["no_action_confirmations"]["no_real_money_wording"] is True


# ── success_rate_method_found ─────────────────────────────────────────────────

def test_p167_success_rate_method_found_is_boolean(artifact):
    assert isinstance(artifact["success_rate_method_found"], bool)


def test_p167_classification_consistent_with_edge_found(artifact):
    edge = artifact["success_rate_method_found"]
    cls = artifact["final_classification"]
    if edge:
        assert cls == "P167_POWER_LOTTO_DEFENSIBLE_EDGE_FOUND"
    else:
        assert cls == "P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND"


def test_p167_null_result_has_reasons(artifact):
    if not artifact["success_rate_method_found"]:
        summary = artifact.get("edge_summary", {})
        assert summary.get("null_result") is True or "reasons" in summary


# ── Next task ─────────────────────────────────────────────────────────────────

def test_p167_next_task_is_p168(artifact):
    assert artifact["next_task"] == "P168_POWER_LOTTO_RESEARCH_DECISION_REVIEW"


# ── active_task / roadmap content ─────────────────────────────────────────────

def test_p167_active_task_mentions_p168(active_task_text):
    assert "P168" in active_task_text


def test_p167_active_task_p167_complete(active_task_text):
    lower = active_task_text.lower()
    assert "p167" in lower


def test_p167_roadmap_p167_present(roadmap_text):
    assert "P167" in roadmap_text


def test_p167_roadmap_no_false_success(roadmap_text):
    lower = roadmap_text.lower()
    assert "success-rate method found" not in lower
    assert "success rate found" not in lower


def test_p167_cto_mentions_p167(cto_text):
    lower = cto_text.lower()
    assert "p167" in lower


def test_p167_cto_no_false_success(cto_text):
    lower = cto_text.lower()
    assert "success-rate method found" not in lower
    assert "success rate found" not in lower


# ── DB rows unchanged ─────────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p167_db_rows_unchanged():
    import sqlite3
    db_path = ROOT / "lottery_api/data/lottery_v2.db"
    con = sqlite3.connect(str(db_path))
    count = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    con.close()
    assert count == 94924, f"DB rows changed from 94924 to {count}"


# ── Forbidden strings ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p167_no_forbidden_strings_json(artifact, forbidden):
    artifact_str = json.dumps(artifact).lower()
    assert forbidden.lower() not in artifact_str, (
        f"Forbidden string found in P167 JSON: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p167_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P167 MD: {forbidden!r}"
    )
