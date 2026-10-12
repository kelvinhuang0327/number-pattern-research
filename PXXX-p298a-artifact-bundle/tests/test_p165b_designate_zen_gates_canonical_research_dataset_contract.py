"""P165B Designate zen-gates as Canonical Research Dataset — contract tests."""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = ROOT / "outputs/research/power_lotto/p165b_designate_zen_gates_canonical_research_dataset_20260531.json"
ARTIFACT_MD = ROOT / "outputs/research/power_lotto/p165b_designate_zen_gates_canonical_research_dataset_20260531.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"
ROADMAP = ROOT / "00-Plan/roadmap/roadmap.md"

FORBIDDEN_STRINGS = [
    "db migrated",
    "reconcile complete",
    "champion promoted",
    "betting advice",
    "guaranteed win",
    "real-money advice",
    "already authorized",
    "merge executed",
    "migration applied",
    "split resolved",
    "main reconciled",
    "option c applied",
    "option a executed",
]

REQUIRED_AUTHORIZATION_PHRASE = "YES designate zen-gates as canonical research dataset"


@pytest.fixture
def artifact():
    assert ARTIFACT_JSON.exists(), f"P165B JSON artifact not found: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture
def md_text():
    assert ARTIFACT_MD.exists(), f"P165B MD artifact not found: {ARTIFACT_MD}"
    return ARTIFACT_MD.read_text(encoding="utf-8")


@pytest.fixture
def active_task_text():
    assert ACTIVE_TASK.exists(), f"active_task.md not found: {ACTIVE_TASK}"
    return ACTIVE_TASK.read_text(encoding="utf-8")


@pytest.fixture
def roadmap_text():
    assert ROADMAP.exists(), f"roadmap.md not found: {ROADMAP}"
    return ROADMAP.read_text(encoding="utf-8")


# ── Existence ────────────────────────────────────────────────────────────────

def test_p165b_json_artifact_exists():
    assert ARTIFACT_JSON.exists()


def test_p165b_md_artifact_exists():
    assert ARTIFACT_MD.exists()


# ── Final classification ─────────────────────────────────────────────────────

def test_p165b_final_classification(artifact):
    assert artifact["final_classification"] == "P165B_ZEN_GATES_CANONICAL_RESEARCH_DATASET_DESIGNATED"


def test_p165b_task_field(artifact):
    assert artifact["task"] == "P165B_DESIGNATE_ZEN_GATES_AS_CANONICAL_RESEARCH_DATASET"


# ── Authorization phrase ─────────────────────────────────────────────────────

def test_p165b_authorization_phrase_detected(artifact):
    assert artifact["authorization_phrase_detected"] == REQUIRED_AUTHORIZATION_PHRASE


def test_p165b_authorized_option_b(artifact):
    assert artifact["authorized_option"] == "B"


def test_p165b_authorization_phrase_in_md(md_text):
    assert REQUIRED_AUTHORIZATION_PHRASE in md_text


# ── Phase 0 verification ─────────────────────────────────────────────────────

def test_p165b_phase0_all_checks_passed(artifact):
    assert artifact["phase_0_verification"]["all_checks_passed"] is True


def test_p165b_phase0_authorization_phrase_present(artifact):
    assert artifact["phase_0_verification"]["authorization_phrase_present"] is True


def test_p165b_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["db_rows"] == 94924


def test_p165b_phase0_drift_guard_pass(artifact):
    assert artifact["phase_0_verification"]["drift_guard"] == "PASS"


def test_p165b_phase0_all_tests_pass(artifact):
    ph0 = artifact["phase_0_verification"]
    assert ph0["p161_test"] == "PASS"
    assert ph0["p162_test"] == "PASS"
    assert ph0["p163_test"] == "PASS"
    assert ph0["p164_test"] == "PASS"


# ── Canonical research repo/branch ───────────────────────────────────────────

def test_p165b_canonical_worktree_path(artifact):
    canon = artifact["canonical_research_dataset"]
    assert "zen-gates-ff6802" in canon["worktree_path"]


def test_p165b_canonical_branch(artifact):
    canon = artifact["canonical_research_dataset"]
    assert canon["branch"] == "claude/zen-gates-ff6802"


def test_p165b_canonical_db_rows(artifact):
    canon = artifact["canonical_research_dataset"]
    assert canon["db_rows"] == 94924


def test_p165b_canonical_bet_index_present(artifact):
    canon = artifact["canonical_research_dataset"]
    assert canon["bet_index_column_present"] is True


def test_p165b_canonical_power_lotto_rows(artifact):
    canon = artifact["canonical_research_dataset"]
    assert canon["power_lotto_rows"] == 36104


# ── No-action confirmations ──────────────────────────────────────────────────

def test_p165b_no_db_write_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_db_write"] is True


def test_p165b_no_merge_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_merge"] is True


def test_p165b_no_registry_mutation_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_registry_mutation"] is True


def test_p165b_no_controlled_apply_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_controlled_apply"] is True


def test_p165b_no_champion_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_champion_promotion"] is True


def test_p165b_no_commit_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_commit"] is True


def test_p165b_no_push_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_push"] is True


def test_p165b_no_betting_advice_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_betting_advice"] is True


def test_p165b_no_win_guarantee_confirmation(artifact):
    assert artifact["no_action_confirmations"]["no_win_guarantee"] is True


# ── main stale / split unresolved ────────────────────────────────────────────

def test_p165b_main_stale_warning_present(artifact):
    assert "main_remains_stale_warning" in artifact
    warn = artifact["main_remains_stale_warning"]
    assert warn["split_status"] == "UNRESOLVED"
    assert warn["main_db_rows"] == 54462
    assert warn["main_bet_index_present"] is False


def test_p165b_db_split_unresolved(artifact):
    split = artifact["db_split_unresolved_warning"]
    assert split["status"] == "UNRESOLVED"
    assert split["no_merge_performed"] is True
    assert split["no_db_migration_performed"] is True


def test_p165b_governance_split_unresolved(artifact):
    gov = artifact["governance_invariants"]
    assert "UNRESOLVED" in gov["main_zen_gates_split"]


# ── Next task P166 plan-only ──────────────────────────────────────────────────

def test_p165b_next_task_is_p166_plan_only(artifact):
    assert artifact["next_task"] == "P166_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_PLAN_ONLY"


def test_p165b_next_task_scope_plan_only(artifact):
    scope = artifact["next_task_scope"].lower()
    assert "plan only" in scope or "plan" in scope
    assert "no implementation" in scope or "no db write" in scope


# ── roadmap / active_task content ────────────────────────────────────────────

def test_p165b_roadmap_does_not_claim_reconcile_complete(roadmap_text):
    lower = roadmap_text.lower()
    assert "reconcile complete" not in lower
    assert "split resolved" not in lower


def test_p165b_roadmap_labels_main_stale_or_split_unresolved(roadmap_text):
    lower = roadmap_text.lower()
    assert "unresolved" in lower or "stale" in lower or "split" in lower


def test_p165b_active_task_labels_zen_gates_canonical(active_task_text):
    lower = active_task_text.lower()
    assert "canonical" in lower or "zen-gates" in lower


def test_p165b_active_task_mentions_p166(active_task_text):
    assert "P166" in active_task_text


def test_p165b_active_task_no_split_resolved(active_task_text):
    lower = active_task_text.lower()
    assert "split resolved" not in lower
    assert "reconcile complete" not in lower


# ── DB rows unchanged ────────────────────────────────────────────────────────

@pytest.mark.requires_zen_gates_db
def test_p165b_db_rows_unchanged():
    import sqlite3
    db_path = ROOT / "lottery_api/data/lottery_v2.db"
    con = sqlite3.connect(str(db_path))
    count = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    con.close()
    assert count == 94924, f"DB rows changed from 94924 to {count}"


# ── Forbidden strings ────────────────────────────────────────────────────────

@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p165b_no_forbidden_strings_json(artifact, forbidden):
    artifact_str = json.dumps(artifact).lower()
    assert forbidden.lower() not in artifact_str, (
        f"Forbidden string found in P165B JSON artifact: {forbidden!r}"
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_p165b_no_forbidden_strings_md(md_text, forbidden):
    assert forbidden.lower() not in md_text.lower(), (
        f"Forbidden string found in P165B MD artifact: {forbidden!r}"
    )
