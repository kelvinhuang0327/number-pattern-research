"""P166 POWER_LOTTO Ensemble / Voting Research Plan — contract tests."""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = ROOT / "outputs/research/power_lotto/p166_ensemble_voting_research_plan_20260531.json"
ARTIFACT_MD = ROOT / "outputs/research/power_lotto/p166_ensemble_voting_research_plan_20260531.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"
ROADMAP = ROOT / "00-Plan/roadmap/roadmap.md"
CTO = ROOT / "00-Plan/roadmap/CTO-Analysis.md"

REQUIRED_MODULES = {"A", "B", "C", "D", "E", "F"}

FORBIDDEN_STRINGS = [
    "implementation complete",
    "success-rate method found",
    "guaranteed win",
    "betting advice",
    "champion promoted",
    "db migrated",
    "reconcile complete",
    "split resolved",
    "main reconciled",
    "success rate found",
    "wagering recommendation",
    "real-money advice",
]


@pytest.fixture
def artifact():
    assert ARTIFACT_JSON.exists(), f"P166 JSON artifact not found: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture
def md_text():
    assert ARTIFACT_MD.exists(), f"P166 MD artifact not found: {ARTIFACT_MD}"
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


# ── Existence ────────────────────────────────────────────────────────────────

def test_p166_json_artifact_exists():
    assert ARTIFACT_JSON.exists()


def test_p166_md_artifact_exists():
    assert ARTIFACT_MD.exists()


# ── Final classification ─────────────────────────────────────────────────────

def test_p166_final_classification(artifact):
    assert artifact["final_classification"] == "P166_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_PLAN_READY"


def test_p166_task_field(artifact):
    assert artifact["task"] == "P166_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_PLAN_ONLY"


def test_p166_plan_only_flag(artifact):
    assert artifact["plan_only"] is True


# ── Phase 0 verification ─────────────────────────────────────────────────────

def test_p166_phase0_all_checks_passed(artifact):
    assert artifact["phase_0_verification"]["all_checks_passed"] is True


def test_p166_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["db_rows"] == 94924


def test_p166_phase0_drift_guard(artifact):
    assert artifact["phase_0_verification"]["drift_guard"] == "PASS"


def test_p166_phase0_all_tests_pass(artifact):
    ph0 = artifact["phase_0_verification"]
    for key in ["p161_test", "p162_test", "p163_test", "p164_test", "p165b_test"]:
        assert ph0[key] == "PASS", f"{key} not PASS"


# ── Canonical dataset confirmation ────────────────────────────────────────────

def test_p166_canonical_dataset_confirmed(artifact):
    canon = artifact["canonical_research_dataset"]
    assert canon["db_rows"] == 94924
    assert canon["power_lotto_rows"] == 36104
    assert canon["bet_index_present"] is True
    assert "zen-gates-ff6802" in canon["worktree_path"]


# ── P161 baseline summary ─────────────────────────────────────────────────────

def test_p166_p161_baseline_summary_present(artifact):
    assert "p161_baseline_summary" in artifact
    summary = artifact["p161_baseline_summary"]
    assert summary["null_result_confirmed"] is True
    assert summary["strategies_surviving_bonferroni"] == 0
    assert summary["strategies_surviving_bh"] == 0


def test_p166_null_baseline_caveat_present(artifact):
    assert "null_baseline_caveat" in artifact
    caveat = artifact["null_baseline_caveat"].lower()
    assert "null" in caveat
    assert "zero" in caveat or "no" in caveat


# ── 6 research modules ────────────────────────────────────────────────────────

def test_p166_research_modules_present(artifact):
    assert "research_modules" in artifact
    modules = artifact["research_modules"]
    module_ids = {v["id"] for v in modules.values()}
    for req in REQUIRED_MODULES:
        assert req in module_ids, f"Module {req} not found in research_modules"


def test_p166_module_a_consensus_voting(artifact):
    modules = artifact["research_modules"]
    mod_a = next(v for v in modules.values() if v["id"] == "A")
    assert "voting" in mod_a["name"].lower() or "consensus" in mod_a["name"].lower()
    assert "research_question" in mod_a
    assert "metric" in mod_a
    assert "baseline" in mod_a
    assert "leakage_risk" in mod_a
    assert "statistical_guard" in mod_a
    assert "pass_fail_criterion" in mod_a


def test_p166_module_b_bet_index_slot(artifact):
    modules = artifact["research_modules"]
    mod_b = next(v for v in modules.values() if v["id"] == "B")
    assert "bet_index" in mod_b["name"].lower() or "slot" in mod_b["name"].lower()
    assert "research_question" in mod_b


def test_p166_module_c_recent_window(artifact):
    modules = artifact["research_modules"]
    mod_c = next(v for v in modules.values() if v["id"] == "C")
    assert "recent" in mod_c["name"].lower() or "window" in mod_c["name"].lower()
    assert "research_question" in mod_c


def test_p166_module_d_lifecycle_descriptive(artifact):
    modules = artifact["research_modules"]
    mod_d = next(v for v in modules.values() if v["id"] == "D")
    assert "lifecycle" in mod_d["name"].lower() or "descriptive" in mod_d["name"].lower()
    assert mod_d["type"] == "descriptive"
    assert "survivorship" in mod_d.get("survivorship_caveat", "").lower() or \
           "survivorship" in mod_d.get("statistical_guard", "").lower()


def test_p166_module_e_main_special_separated(artifact):
    modules = artifact["research_modules"]
    mod_e = next(v for v in modules.values() if v["id"] == "E")
    assert "special" in mod_e["name"].lower() or "main" in mod_e["name"].lower()
    assert "research_question" in mod_e


def test_p166_module_f_walk_forward_oos(artifact):
    modules = artifact["research_modules"]
    mod_f = next(v for v in modules.values() if v["id"] == "F")
    assert "walk" in mod_f["name"].lower() or "oos" in mod_f["name"].lower()
    assert "predictive" in mod_f["type"].lower()
    # Module F must require OOS >= 500 draws
    assert "500" in mod_f["statistical_guard"] or "500" in mod_f["metric"]


def test_p166_each_module_has_required_fields(artifact):
    required_fields = {
        "research_question", "input_data", "metric", "baseline",
        "leakage_risk", "statistical_guard", "pass_fail_criterion", "type"
    }
    modules = artifact["research_modules"]
    for key, mod in modules.items():
        for field in required_fields:
            assert field in mod, f"Module {key} missing field: {field}"


# ── No-action confirmations ───────────────────────────────────────────────────

def test_p166_no_db_write_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_db_write"] is True


def test_p166_no_strategy_implementation_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_strategy_implementation"] is True


def test_p166_no_betting_advice_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_betting_advice"] is True


def test_p166_no_win_guarantee_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_win_guarantee"] is True


def test_p166_no_registry_mutation_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_registry_mutation"] is True


def test_p166_no_commit_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_commit"] is True


def test_p166_no_push_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_push"] is True


# ── P167 boundary ─────────────────────────────────────────────────────────────

def test_p166_next_task_is_p167(artifact):
    assert artifact["next_task"] == "P167_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_IMPLEMENTATION"


def test_p166_p167_blocked_waiting_authorization(artifact):
    state = artifact["next_task_state"]
    assert "BLOCKED" in state or "WAITING" in state


def test_p166_p167_implementation_boundary_present(artifact):
    assert "p167_implementation_boundary" in artifact
    boundary = artifact["p167_implementation_boundary"]
    assert "success_criteria" in boundary
    assert "failure_criteria" in boundary
    assert len(boundary["success_criteria"]) >= 4


def test_p166_p167_success_criteria_includes_null_report(artifact):
    criteria = artifact["p167_implementation_boundary"]["failure_criteria"]
    combined = " ".join(criteria).lower()
    assert "null" in combined


# ── Governance invariants ─────────────────────────────────────────────────────

def test_p166_null_result_still_current(artifact):
    assert artifact["governance_invariants"]["null_result_still_current"] is True
    assert artifact["governance_invariants"]["no_success_rate_method_found"] is True


def test_p166_main_split_unresolved(artifact):
    assert "UNRESOLVED" in artifact["governance_invariants"]["main_zen_gates_split"]


# ── active_task / roadmap content ────────────────────────────────────────────

def test_p166_active_task_contains_plan_ready(active_task_text):
    lower = active_task_text.lower()
    assert "p166" in lower
    assert "plan" in lower or "plan_ready" in lower.replace("_", " ")


def test_p166_active_task_p167_blocked(active_task_text):
    assert "P167" in active_task_text
    lower = active_task_text.lower()
    assert "blocked" in lower or "authorization" in lower


def test_p166_roadmap_does_not_claim_success_rate_found(roadmap_text):
    lower = roadmap_text.lower()
    assert "success-rate method found" not in lower
    assert "success rate found" not in lower


def test_p166_roadmap_main_split_unresolved(roadmap_text):
    lower = roadmap_text.lower()
    assert "unresolved" in lower or "stale" in lower


def test_p166_cto_says_no_success_rate_method_yet(cto_text):
    lower = cto_text.lower()
    # CTO must NOT claim a success rate method was found
    assert "success-rate method found" not in lower
    assert "success rate found" not in lower
    # CTO must acknowledge P166 is plan only
    assert "p166" in lower


# ── DB rows unchanged ────────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p166_db_rows_unchanged():
    import sqlite3
    db_path = ROOT / "lottery_api/data/lottery_v2.db"
    con = sqlite3.connect(str(db_path))
    count = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    con.close()
    assert count == 94924, f"DB rows changed from 94924 to {count}"


# ── Forbidden strings ────────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p166_no_forbidden_strings_json(artifact, forbidden):
    artifact_str = json.dumps(artifact).lower()
    assert forbidden.lower() not in artifact_str, (
        f"Forbidden string found in P166 JSON: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p166_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P166 MD: {forbidden!r}"
    )
