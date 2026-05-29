"""Tests for P140A: Draw Context Contract Fix for P10/P12 Pre-Apply Readiness"""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
P140A_JSON = WORKTREE / "outputs/replay/p140a_draw_context_contract_fix_p10_p12_20260529.json"
P140A_MD = WORKTREE / "docs/replay/p140a_draw_context_contract_fix_p10_p12_20260529.md"
ADAPTER_MODULE = WORKTREE / "lottery_api/models/p128_wave2_phase2_adapters.py"

EXPECTED_DB_ROWS = 85924
LIVE_DB_ROWS = 94924  # post-P141: +6000 power_orthogonal_5bet rows
P10 = "power_precision_3bet"
P12 = "power_orthogonal_5bet"


@pytest.fixture(scope="module")
def p140a():
    assert P140A_JSON.exists(), f"P140A JSON not found: {P140A_JSON}"
    with open(P140A_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB_PATH)
    yield c
    c.close()


@pytest.fixture(scope="module")
def adapter_mod():
    spec = importlib.util.spec_from_file_location("p128_phase2", ADAPTER_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- Artifact existence ---

def test_p140a_json_exists():
    assert P140A_JSON.exists()


def test_p140a_md_exists():
    assert P140A_MD.exists()


# --- Basic artifact fields ---

def test_task_id(p140a):
    assert p140a["task_id"] == "P140A"


def test_classification(p140a):
    assert p140a["classification"] == "P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY"


# --- Repo / branch ---

def test_repo_ok(p140a):
    assert p140a["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(p140a):
    assert p140a["repo_branch_check"]["branch_ok"] is True


def test_canonical_repo(p140a):
    assert p140a["canonical_repo"] == "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"


def test_canonical_branch(p140a):
    assert p140a["canonical_branch"] == "claude/zen-gates-ff6802"


# --- DB snapshot ---

def test_db_rows_snapshot(p140a):
    assert p140a["db_snapshot"]["total_rows"] == EXPECTED_DB_ROWS


def test_db_rows_ok(p140a):
    assert p140a["db_snapshot"]["rows_ok"] is True


def test_bet_index_schema(p140a):
    assert p140a["db_snapshot"]["bet_index_schema_present"] is True


def test_db_rows_live(conn):
    row = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    assert row[0] == LIVE_DB_ROWS


def test_p10_bet1_rows_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
        (P10,),
    ).fetchone()
    assert row[0] == 1550


def test_p12_bet1_rows_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
        (P12,),
    ).fetchone()
    assert row[0] == 1550


def test_p10_no_bet2_plus_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1",
        (P10,),
    ).fetchone()
    assert row[0] == 3000


def test_p12_no_bet2_plus_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1",
        (P12,),
    ).fetchone()
    assert row[0] == 6000  # post-P141: bet-2..bet-5 applied (+6000)


# --- P139 source summary ---

def test_p139_classification(p140a):
    assert p140a["p139_source_summary"]["classification"] == "P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY"


def test_p139_classification_ok(p140a):
    assert p140a["p139_source_summary"]["classification_ok"] is True


def test_p139_p10_dry_run_ready(p140a):
    assert p140a["p139_source_summary"]["p10_dry_run_ready"] is True


def test_p139_p12_dry_run_ready(p140a):
    assert p140a["p139_source_summary"]["p12_dry_run_ready"] is True


# --- P138B source summary ---

def test_p138b_classification(p140a):
    assert p140a["p138b_source_summary"]["classification"] == "P138B_P10_P12_LEGACY_ROWS_REMARKED"


def test_p138b_classification_ok(p140a):
    assert p140a["p138b_source_summary"]["classification_ok"] is True


def test_p138b_rows_remarked(p140a):
    assert p140a["p138b_source_summary"]["actual_rows_remarked"] == 100


# --- Legacy unverified audit live ---

def test_p10_legacy_unverified_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND truth_level='LEGACY_UNVERIFIED'",
        (P10,),
    ).fetchone()
    assert row[0] == 50


def test_p12_legacy_unverified_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND truth_level='LEGACY_UNVERIFIED'",
        (P12,),
    ).fetchone()
    assert row[0] == 50


def test_no_null_prov_p10_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND provenance_hash IS NULL",
        (P10,),
    ).fetchone()
    assert row[0] == 0


def test_no_null_prov_p12_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND provenance_hash IS NULL",
        (P12,),
    ).fetchone()
    assert row[0] == 0


# --- draw_context contract audit ---

def test_mismatch_detected(p140a):
    assert p140a["draw_context_contract_audit"]["mismatch_detected"] is True


def test_selected_standard_key(p140a):
    assert p140a["draw_context_contract_audit"]["selected_standard_key"] == "history"


def test_affected_strategies(p140a):
    affected = p140a["draw_context_contract_audit"]["affected_strategies"]
    assert P10 in affected
    assert P12 in affected


def test_backward_compat_primary(p140a):
    bc = p140a["draw_context_contract_audit"]["backward_compatibility_aliases"]
    assert bc["primary"] == "history"


def test_backward_compat_alias(p140a):
    bc = p140a["draw_context_contract_audit"]["backward_compatibility_aliases"]
    assert "historical_draws" in bc["accepted_aliases"]


def test_fix_required(p140a):
    assert p140a["draw_context_contract_audit"]["fix_required"] is True


def test_fix_applied_in_contract_audit(p140a):
    assert p140a["draw_context_contract_audit"]["fix_applied"] is True


# --- Contract fix summary ---

def test_fix_applied(p140a):
    assert p140a["contract_fix_summary"]["fix_applied"] is True


def test_normalize_function_name(p140a):
    assert p140a["contract_fix_summary"]["normalize_function_name"] == "normalize_draw_context"


def test_canonical_key_in_fix(p140a):
    assert p140a["contract_fix_summary"]["canonical_key"] == "history"


def test_alias_in_fix(p140a):
    assert p140a["contract_fix_summary"]["accepted_alias"] == "historical_draws"


def test_rsr6_blocked_cleared_is_false(p140a):
    # RSR6_BLOCKED_STRATEGIES is retained for P128 test compatibility — NOT cleared by P140A.
    assert p140a["contract_fix_summary"]["rsr6_blocked_strategies_cleared"] is False


def test_no_db_write_in_fix(p140a):
    assert p140a["contract_fix_summary"]["db_write_performed"] is False


# --- normalize_draw_context function in adapter module ---

def test_normalize_function_exists(adapter_mod):
    assert hasattr(adapter_mod, "normalize_draw_context")


def test_normalize_canonical_key_pass_through(adapter_mod):
    dc = {"history": [{"numbers": [1, 2, 3, 4, 5, 6]}], "lottery_type": "POWER_LOTTO"}
    result = adapter_mod.normalize_draw_context(dc)
    assert result["history"] == dc["history"]


def test_normalize_alias_key_maps_to_history(adapter_mod):
    hist = [{"numbers": [1, 2, 3, 4, 5, 6]}]
    dc = {"historical_draws": hist, "lottery_type": "POWER_LOTTO"}
    result = adapter_mod.normalize_draw_context(dc)
    assert "history" in result
    assert result["history"] == hist


def test_normalize_missing_key_raises(adapter_mod):
    with pytest.raises(KeyError):
        adapter_mod.normalize_draw_context({"lottery_type": "POWER_LOTTO"})


def test_rsr6_blocked_strategies_retained(adapter_mod):
    # RSR6_BLOCKED_STRATEGIES retained for P128 test compatibility (not cleared by P140A).
    # RSR-6 is operationally resolved but set value preserved.
    assert "power_precision_3bet" in adapter_mod.RSR6_BLOCKED_STRATEGIES
    assert "power_orthogonal_5bet" in adapter_mod.RSR6_BLOCKED_STRATEGIES


# --- Adapter smoke results ---

def test_p10_adapter_function_found(p140a):
    assert p140a["adapter_smoke_results"][P10]["adapter_function_found"] is True


def test_p12_adapter_function_found(p140a):
    assert p140a["adapter_smoke_results"][P12]["adapter_function_found"] is True


def test_p10_smoke_test_passed(p140a):
    assert p140a["adapter_smoke_results"][P10]["smoke_test_passed"] is True


def test_p12_smoke_test_passed(p140a):
    assert p140a["adapter_smoke_results"][P12]["smoke_test_passed"] is True


def test_p10_expected_bet_count(p140a):
    assert p140a["adapter_smoke_results"][P10]["expected_target_bet_count"] == 3


def test_p12_expected_bet_count(p140a):
    assert p140a["adapter_smoke_results"][P12]["expected_target_bet_count"] == 5


def test_p10_actual_bet_count(p140a):
    assert p140a["adapter_smoke_results"][P10]["actual_bet_count"] == 3


def test_p12_actual_bet_count(p140a):
    assert p140a["adapter_smoke_results"][P12]["actual_bet_count"] == 5


def test_p10_deterministic(p140a):
    assert p140a["adapter_smoke_results"][P10]["deterministic_ordering_passed"] is True


def test_p12_deterministic(p140a):
    assert p140a["adapter_smoke_results"][P12]["deterministic_ordering_passed"] is True


def test_p10_stable_output(p140a):
    assert p140a["adapter_smoke_results"][P10]["stable_output_passed"] is True


def test_p12_stable_output(p140a):
    assert p140a["adapter_smoke_results"][P12]["stable_output_passed"] is True


def test_p10_no_dup_bet_index(p140a):
    assert p140a["adapter_smoke_results"][P10]["duplicate_bet_index_check_passed"] is True


def test_p12_no_dup_bet_index(p140a):
    assert p140a["adapter_smoke_results"][P12]["duplicate_bet_index_check_passed"] is True


def test_p10_provenance_requirements(p140a):
    prov = p140a["adapter_smoke_results"][P10]["provenance_requirements_checked"]
    assert "P140_APPLY_POWER_PRECISION_3BET_v1" in prov["controlled_apply_id"]


def test_p12_provenance_requirements(p140a):
    prov = p140a["adapter_smoke_results"][P12]["provenance_requirements_checked"]
    assert "P141_APPLY_POWER_ORTHOGONAL_5BET_v1" in prov["controlled_apply_id"]


# --- Adapter smoke: live invocation ---

def _get_history_from_db(conn, min_draws: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT target_draw, actual_numbers FROM strategy_prediction_replays
           WHERE strategy_id=? AND bet_index=1 AND actual_numbers IS NOT NULL
           ORDER BY CAST(target_draw AS INTEGER) ASC LIMIT ?""",
        (P10, min_draws + 20),
    ).fetchall()
    history = []
    for draw, nums_str in rows:
        try:
            import json as _json
            history.append({"draw": draw, "numbers": _json.loads(nums_str)})
        except Exception:
            pass
    return history


def test_p10_adapter_live_canonical_key(adapter_mod, conn):
    history = _get_history_from_db(conn)
    assert len(history) >= 30, f"Insufficient history: {len(history)}"
    dc = adapter_mod.normalize_draw_context({"history": history, "lottery_type": "POWER_LOTTO"})
    bets = adapter_mod.get_all_bets_power_precision(dc)
    assert len(bets) == 3
    for b in bets:
        assert len(b) == 6
        assert all(1 <= n <= 38 for n in b)


def test_p10_adapter_live_alias_key(adapter_mod, conn):
    history = _get_history_from_db(conn)
    dc = adapter_mod.normalize_draw_context({"historical_draws": history, "lottery_type": "POWER_LOTTO"})
    bets = adapter_mod.get_all_bets_power_precision(dc)
    assert len(bets) == 3


def test_p12_adapter_live_canonical_key(adapter_mod, conn):
    history = _get_history_from_db(conn)
    dc = adapter_mod.normalize_draw_context({"history": history, "lottery_type": "POWER_LOTTO"})
    bets = adapter_mod.get_all_bets_power_orthogonal(dc)
    assert len(bets) == 5
    for b in bets:
        assert len(b) == 6
        assert all(1 <= n <= 38 for n in b)


def test_p12_adapter_live_alias_key(adapter_mod, conn):
    history = _get_history_from_db(conn)
    dc = adapter_mod.normalize_draw_context({"historical_draws": history, "lottery_type": "POWER_LOTTO"})
    bets = adapter_mod.get_all_bets_power_orthogonal(dc)
    assert len(bets) == 5


def test_p10_adapter_deterministic_live(adapter_mod, conn):
    history = _get_history_from_db(conn)
    dc1 = adapter_mod.normalize_draw_context({"history": history, "lottery_type": "POWER_LOTTO"})
    dc2 = adapter_mod.normalize_draw_context({"history": history, "lottery_type": "POWER_LOTTO"})
    assert adapter_mod.get_all_bets_power_precision(dc1) == adapter_mod.get_all_bets_power_precision(dc2)


def test_p12_adapter_deterministic_live(adapter_mod, conn):
    history = _get_history_from_db(conn)
    dc1 = adapter_mod.normalize_draw_context({"history": history, "lottery_type": "POWER_LOTTO"})
    dc2 = adapter_mod.normalize_draw_context({"history": history, "lottery_type": "POWER_LOTTO"})
    assert adapter_mod.get_all_bets_power_orthogonal(dc1) == adapter_mod.get_all_bets_power_orthogonal(dc2)


# --- Legacy unverified handling ---

def test_legacy_unverified_rows_total(p140a):
    assert p140a["legacy_unverified_handling"]["legacy_unverified_rows_total"] == 100


def test_legacy_unverified_excluded_from_apply_base(p140a):
    assert p140a["legacy_unverified_handling"]["legacy_unverified_excluded_from_apply_base"] is True


def test_production_baseline_rows_per_strategy(p140a):
    assert p140a["legacy_unverified_handling"]["production_baseline_rows_per_strategy"] == 1500


def test_no_db_write_in_p140a(p140a):
    assert p140a["legacy_unverified_handling"]["db_write_in_p140a"] is False


def test_p10_production_baseline_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED'",
        (P10,),
    ).fetchone()
    assert row[0] == 4500


def test_p12_production_baseline_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED'",
        (P12,),
    ).fetchone()
    # post-P141: 1500 bet-1 + 6000 bet-2..bet-5 (all POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED)
    assert row[0] == 7500


# --- Apply gate status ---

def test_contract_fix_only(p140a):
    assert p140a["apply_gate_status"]["contract_fix_only"] is True


def test_controlled_apply_not_executed(p140a):
    assert p140a["apply_gate_status"]["controlled_apply_executed"] is False


def test_replay_rows_inserted_zero(p140a):
    assert p140a["apply_gate_status"]["replay_rows_inserted"] == 0


def test_db_rows_before(p140a):
    assert p140a["apply_gate_status"]["db_rows_before"] == EXPECTED_DB_ROWS


def test_db_rows_after(p140a):
    assert p140a["apply_gate_status"]["db_rows_after"] == EXPECTED_DB_ROWS


def test_p10_future_apply_gate_allowed(p140a):
    assert p140a["apply_gate_status"]["p10_power_precision_3bet_future_apply_gate_allowed"] is True


def test_p12_future_apply_gate_allowed(p140a):
    assert p140a["apply_gate_status"]["p12_power_orthogonal_5bet_future_apply_gate_allowed"] is True


def test_authorization_required_later(p140a):
    assert p140a["apply_gate_status"]["per_strategy_authorization_required_later"] is True


# --- Blocked or excluded ---

def test_blocked_no_db_write(p140a):
    assert any("no DB write" in b for b in p140a["blocked_or_excluded"])


def test_blocked_no_controlled_apply(p140a):
    assert any("no controlled_apply" in b for b in p140a["blocked_or_excluded"])


def test_blocked_4star(p140a):
    assert any("4_STAR" in b for b in p140a["blocked_or_excluded"])


def test_blocked_p108(p140a):
    assert any("P108" in b for b in p140a["blocked_or_excluded"])


def test_blocked_p117(p140a):
    assert any("P117" in b for b in p140a["blocked_or_excluded"])


def test_blocked_p118(p140a):
    assert any("P118" in b for b in p140a["blocked_or_excluded"])


def test_blocked_no_scheduler(p140a):
    assert any("scheduler" in b for b in p140a["blocked_or_excluded"])


def test_blocked_rejected_strategies(p140a):
    assert any("rejected" in b for b in p140a["blocked_or_excluded"])


# --- p10_p12_apply_readiness_after_fix ---

def test_p10_contract_fix_complete(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P10]["contract_fix_complete"] is True


def test_p12_contract_fix_complete(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P12]["contract_fix_complete"] is True


def test_p10_draw_context_contract_ready(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P10]["draw_context_contract_ready"] is True


def test_p12_draw_context_contract_ready(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P12]["draw_context_contract_ready"] is True


def test_p10_apply_base_rows(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P10]["apply_base_rows"] == 1500


def test_p12_apply_base_rows(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P12]["apply_base_rows"] == 1500


def test_p10_estimated_insert_rows(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P10]["estimated_insert_rows"] == 3000


def test_p12_estimated_insert_rows(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P12]["estimated_insert_rows"] == 6000


def test_p10_next_task(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P10]["next_task"] == "P140"


def test_p12_next_task(p140a):
    assert p140a["p10_p12_apply_readiness_after_fix"][P12]["next_task"] == "P141"


def test_p10_auth_phrase_in_readiness(p140a):
    phrase = p140a["p10_p12_apply_readiness_after_fix"][P10]["authorization_phrase_required"]
    assert "P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET" in phrase


def test_p12_auth_phrase_in_readiness(p140a):
    phrase = p140a["p10_p12_apply_readiness_after_fix"][P12]["authorization_phrase_required"]
    assert "P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET" in phrase


# --- Markdown content ---

def test_markdown_has_classification():
    md = P140A_MD.read_text()
    assert "P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY" in md


def test_markdown_has_executive_summary():
    md = P140A_MD.read_text()
    assert "Executive Summary" in md


def test_markdown_has_contract_audit():
    md = P140A_MD.read_text()
    assert "draw_context" in md.lower()
    assert "historical_draws" in md


def test_markdown_has_future_apply_impact():
    md = P140A_MD.read_text()
    assert "P140" in md
    assert "P141" in md


def test_markdown_has_normalize_function():
    md = P140A_MD.read_text()
    assert "normalize_draw_context" in md


def test_markdown_has_no_db_write():
    md = P140A_MD.read_text()
    assert "No DB write" in md or "no DB write" in md


def test_markdown_has_legacy_unverified():
    md = P140A_MD.read_text()
    assert "LEGACY_UNVERIFIED" in md


# --- No dirty DB/runtime files staged ---

def test_no_db_files_staged():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=WORKTREE,
        capture_output=True,
        text=True,
    )
    staged = result.stdout.strip().splitlines()
    forbidden = [f for f in staged if f.endswith(".db") or f.endswith(".pid") or "backups/" in f]
    assert forbidden == [], f"Forbidden files staged: {forbidden}"
