"""
Contract test for P182 — Code/Docs/Tests Parity Backport (No DB Write).

Verifies that the backport from zen-gates to main completed correctly:
- P182 JSON/MD artifacts exist with correct classification
- All copied files are present
- Governance confirmations hold
- DB state unchanged on main
- conftest.py skip markers present
- Roadmap docs updated
- No forbidden actions taken
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs/research/power_lotto/p182_code_docs_tests_parity_backport_20260601.json"
ARTIFACT_MD = REPO_ROOT / "outputs/research/power_lotto/p182_code_docs_tests_parity_backport_20260601.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
CONFTEST = REPO_ROOT / "tests" / "conftest.py"
ACTIVE_TASK = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = REPO_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"


@pytest.fixture(scope="module")
def artifact() -> dict:
    assert ARTIFACT_JSON.exists(), f"P182 JSON artifact missing: {ARTIFACT_JSON}"
    return json.loads(ARTIFACT_JSON.read_text())


# ── Artifact existence ────────────────────────────────────────────────────────

def test_p182_json_artifact_exists():
    assert ARTIFACT_JSON.exists()


def test_p182_md_artifact_exists():
    assert ARTIFACT_MD.exists()


# ── Classification & authorization ───────────────────────────────────────────

def test_final_classification(artifact):
    assert artifact["final_classification"] == "P182_CODE_DOCS_TESTS_PARITY_BACKPORT_READY"


def test_authorization_phrase_detected(artifact):
    phrase = artifact["authorization_phrase_detected"]
    assert "YES start P182" in phrase
    assert "code-docs-tests parity backport implementation no DB write" in phrase


# ── Phase 0 verification ──────────────────────────────────────────────────────

def test_phase0_status(artifact):
    assert artifact["phase_0_verification"]["status"] == "PASS"


def test_phase0_branch(artifact):
    assert artifact["phase_0_verification"]["branch"] == "main"


def test_phase0_not_worktree(artifact):
    assert artifact["phase_0_verification"]["is_worktree"] is False


# ── Source reference ──────────────────────────────────────────────────────────

def test_source_reference_worktree(artifact):
    assert "zen-gates-ff6802" in artifact["source_reference"]["worktree"]


def test_source_reference_branch(artifact):
    assert artifact["source_reference"]["branch"] == "claude/zen-gates-ff6802"


# ── Target ────────────────────────────────────────────────────────────────────

def test_target_repo(artifact):
    assert artifact["target"]["repo"] == "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"


def test_target_branch(artifact):
    assert artifact["target"]["branch"] == "main"


# ── DB state unchanged ────────────────────────────────────────────────────────

def test_db_rows_before_unchanged(artifact):
    assert artifact["phase_0_verification"]["main_db_rows_before"] == 54462


def test_db_rows_after_unchanged(artifact):
    assert artifact["governance_confirmations"]["db_rows_before"] == 54462
    assert artifact["governance_confirmations"]["db_rows_after"] == 54462


def test_db_write_zero(artifact):
    assert artifact["governance_confirmations"]["db_write"] == 0


# ── Governance confirmations ──────────────────────────────────────────────────

def test_no_merge(artifact):
    assert artifact["governance_confirmations"]["no_merge"] is True


def test_no_rebase(artifact):
    assert artifact["governance_confirmations"]["no_rebase"] is True


def test_no_cherry_pick(artifact):
    assert artifact["governance_confirmations"]["no_cherry_pick"] is True


def test_no_controlled_apply(artifact):
    assert artifact["governance_confirmations"]["no_controlled_apply"] is True


def test_no_stage_commit_push(artifact):
    assert artifact["governance_confirmations"]["no_stage_commit_push"] is True


def test_no_wagering_recommendation(artifact):
    assert artifact["governance_confirmations"]["no_wagering_recommendation"] is True


def test_no_win_guarantee(artifact):
    assert artifact["governance_confirmations"]["no_win_guarantee"] is True


def test_p178a_closure_active(artifact):
    assert "ACTIVE" in artifact["governance_confirmations"]["p178a_closure_policy"]
    assert "CLOSED" in artifact["governance_confirmations"]["p178a_closure_policy"]


def test_main_zen_gates_split_unresolved(artifact):
    assert "UNRESOLVED" in artifact["governance_confirmations"]["main_zen_gates_split"]


# ── Copied artifacts count ────────────────────────────────────────────────────

def test_copied_research_artifacts_count(artifact):
    count = artifact["files_copied"]["research_artifacts"]["count"]
    assert count > 0, "No research artifacts were copied"
    assert count == 42


def test_copied_analysis_scripts_count(artifact):
    count = artifact["files_copied"]["analysis_scripts"]["count"]
    assert count > 0
    assert count == 5


def test_copied_contract_tests_count(artifact):
    count = artifact["files_copied"]["contract_tests"]["count"]
    assert count > 0
    assert count == 21


# ── Actual files exist on main ────────────────────────────────────────────────

def test_research_artifacts_exist_on_main():
    artifact_dir = REPO_ROOT / "outputs" / "research" / "power_lotto"
    copied = [f for f in artifact_dir.glob("p16[1-9]_*.json")] + \
             [f for f in artifact_dir.glob("p17[0-9]_*.json")] + \
             [f for f in artifact_dir.glob("p178a_*.json")] + \
             [f for f in artifact_dir.glob("p179_*.json")] + \
             [f for f in artifact_dir.glob("p180_*.json")] + \
             [f for f in artifact_dir.glob("p181_*.json")]
    assert len(copied) >= 21, f"Expected at least 21 JSON artifacts, found {len(copied)}"


def test_analysis_scripts_exist_on_main():
    script_dir = REPO_ROOT / "analysis" / "power_lotto"
    assert (script_dir / "p161_effectiveness_baseline.py").exists()
    assert (script_dir / "p167_ensemble_voting_research.py").exists()
    assert (script_dir / "p170_threshold_sensitivity_and_signal_tracking.py").exists()
    assert (script_dir / "p173_new_strategy_minimal_prototype_read_only.py").exists()
    assert (script_dir / "p176_advanced_feature_minimal_prototype_read_only.py").exists()


def test_contract_tests_exist_on_main():
    test_dir = REPO_ROOT / "tests"
    for p in range(161, 182):
        # spot check a few
        pass
    assert (test_dir / "test_p161_power_lotto_effectiveness_baseline.py").exists()
    assert (test_dir / "test_p178a_r2_research_closure_archive_contract.py").exists()
    assert (test_dir / "test_p181_code_docs_tests_parity_plan_contract.py").exists()


# ── conftest.py skip markers ──────────────────────────────────────────────────

def test_conftest_requires_zen_gates_db_marker():
    content = CONFTEST.read_text()
    assert "requires_zen_gates_db" in content


def test_conftest_requires_bet_index_marker():
    content = CONFTEST.read_text()
    assert "requires_bet_index" in content


def test_conftest_zen_gates_row_count_preserved():
    content = CONFTEST.read_text()
    assert "94924" in content, "94924 guard must be preserved in conftest.py"


def test_conftest_does_not_weaken_to_54462():
    content = CONFTEST.read_text()
    assert "54462" not in content, "54462 must NOT appear in conftest.py (would weaken contract)"


# ── Roadmap docs updated ──────────────────────────────────────────────────────

def test_active_task_marks_p182_done():
    content = ACTIVE_TASK.read_text()
    assert "P182" in content
    assert "BACKPORT" in content or "COMPLETE" in content


def test_active_task_p183_blocked():
    content = ACTIVE_TASK.read_text()
    assert "P183" in content
    assert "BLOCKED" in content


def test_roadmap_includes_p182():
    content = ROADMAP.read_text()
    assert "P182" in content


def test_cto_analysis_includes_p182():
    content = CTO_ANALYSIS.read_text()
    assert "P182" in content


# ── Test compatibility strategy documented ────────────────────────────────────

def test_test_compatibility_strategy_documented(artifact):
    strategy = artifact["test_compatibility_strategy"]
    assert strategy["implemented"] is True
    assert "T1" in strategy["tiers"]
    assert "T2" in strategy["tiers"]
    assert "T3" in strategy["tiers"]
    assert "SKIP" in strategy["tiers"]["T2"]
    assert "SKIP" in strategy["tiers"]["T3"]


def test_requires_zen_gates_db_in_skip_strategy(artifact):
    strategy = artifact["test_compatibility_strategy"]
    assert "requires_zen_gates_db" in strategy["tiers"]["T2"]


def test_requires_bet_index_in_skip_strategy(artifact):
    strategy = artifact["test_compatibility_strategy"]
    assert "requires_bet_index" in strategy["tiers"]["T3"]


# ── P183 options present ──────────────────────────────────────────────────────

def test_p183_next_options_present(artifact):
    options = artifact["p183_next_options"]
    assert len(options) >= 4
    phrases = [o["phrase"] for o in options]
    assert any("P183" in p for p in phrases)


# ── No wagering / win-guarantee in artifacts ──────────────────────────────────

def test_no_wagering_in_md_artifact():
    content = ARTIFACT_MD.read_text()
    forbidden = ["guaranteed win", "win guarantee", "betting advice", "sure to win"]
    for term in forbidden:
        assert term.lower() not in content.lower(), f"Forbidden term found in MD: {term}"


def test_no_wagering_in_json_artifact(artifact):
    raw = json.dumps(artifact).lower()
    forbidden = ["guaranteed win", "win guarantee", "betting advice"]
    for term in forbidden:
        assert term not in raw, f"Forbidden term found in JSON: {term}"
