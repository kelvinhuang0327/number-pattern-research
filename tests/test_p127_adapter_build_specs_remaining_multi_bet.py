"""
Tests for P127 — Adapter Build Specs for Remaining Multi-Bet Strategies.

These tests validate:
- P127 JSON artifact correctness
- DB state (rows = 72422 post RSR-6 cleanup, bet_index schema)
- P126G source artifact validation
- Adapter spec structure and governance fields
- Apply gate status
- Blocked/excluded governance
- Markdown content

No DB writes. No controlled_apply. Read-only assertions only.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
ARTIFACT_DATE = "20260528"

P127_JSON = REPO_ROOT / "outputs" / "replay" / f"p127_adapter_build_specs_remaining_multi_bet_{ARTIFACT_DATE}.json"
P127_MD   = REPO_ROOT / "docs" / "replay" / f"p127_adapter_build_specs_remaining_multi_bet_{ARTIFACT_DATE}.md"
P126G_JSON = REPO_ROOT / "outputs" / "replay" / f"p126g_all_tier_b_apply_closure_audit_{ARTIFACT_DATE}.json"

EXPECTED_TOTAL_ROWS = 72462          # Historical: DB state when P127 artifact was generated
EXPECTED_TOTAL_ROWS_CURRENT = 88924  # Post P140 apply (power_precision_3bet +3000 over P134 state)
EXPECTED_STRATEGY_COUNT = 12

REQUIRED_SPEC_FIELDS = [
    "strategy_id",
    "lottery_type",
    "target_bet_count",
    "current_replay_rows",
    "current_bet_index_distribution",
    "missing_adapter_component",
    "proposed_adapter_contract",
    "deterministic_ordering_rule",
    "duplicate_guard",
    "provenance_requirements",
    "tests_required",
    "risk_level",
    "implementation_priority",
    "apply_authorization_required_later",
    "db_write_in_p127",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def artifact() -> dict:
    assert P127_JSON.exists(), f"P127 JSON not found: {P127_JSON}"
    return json.loads(P127_JSON.read_text())


@pytest.fixture(scope="module")
def p126g() -> dict:
    assert P126G_JSON.exists(), f"P126G JSON not found: {P126G_JSON}"
    return json.loads(P126G_JSON.read_text())


@pytest.fixture(scope="module")
def db_conn():
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON")
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def specs(artifact) -> list[dict]:
    return artifact.get("adapter_build_specs", [])


@pytest.fixture(scope="module")
def md_content() -> str:
    assert P127_MD.exists(), f"P127 Markdown not found: {P127_MD}"
    return P127_MD.read_text()


# ---------------------------------------------------------------------------
# Artifact existence and identity
# ---------------------------------------------------------------------------

def test_p127_json_exists():
    assert P127_JSON.exists()


def test_p127_md_exists():
    assert P127_MD.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P127"


def test_classification(artifact):
    assert artifact["classification"] == "P127_ADAPTER_BUILD_SPECS_READY"


def test_generated_at_present(artifact):
    assert "generated_at" in artifact
    assert artifact["generated_at"]


# ---------------------------------------------------------------------------
# DB state validation (read-only)
# ---------------------------------------------------------------------------

def test_live_db_total_rows(db_conn):
    count = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert count == EXPECTED_TOTAL_ROWS_CURRENT, f"DB has {count} rows, expected {EXPECTED_TOTAL_ROWS_CURRENT}"


def test_live_db_bet_index_column_exists(db_conn):
    cols = db_conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    names = [c[1] for c in cols]
    assert "bet_index" in names


def test_live_db_bet_index_not_null(db_conn):
    cols = db_conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    col = next(c for c in cols if c[1] == "bet_index")
    assert col[3] == 1  # not_null flag


def test_live_db_bet_index_default_1(db_conn):
    cols = db_conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    col = next(c for c in cols if c[1] == "bet_index")
    assert col[4] == "1"


def test_db_snapshot_in_artifact(artifact):
    snap = artifact["db_snapshot"]
    assert snap["total_rows_before"] == EXPECTED_TOTAL_ROWS
    assert snap["total_rows_after"] == EXPECTED_TOTAL_ROWS
    assert snap["pass"] is True


def test_schema_check_in_artifact(artifact):
    schema = artifact["schema_check"]
    assert schema["pass"] is True
    assert schema["present"] is True


# ---------------------------------------------------------------------------
# P126G source validation
# ---------------------------------------------------------------------------

def test_p126g_artifact_classification(p126g):
    assert p126g["classification"] == "P126G_ALL_TIER_B_MULTI_BET_APPLY_CLOSED"


def test_p126g_source_summary_in_artifact(artifact):
    src = artifact["p126g_source_summary"]
    assert src["pass"] is True
    assert src["classification"] == "P126G_ALL_TIER_B_MULTI_BET_APPLY_CLOSED"


def test_p126g_candidates_applied(artifact):
    src = artifact["p126g_source_summary"]
    assert src["applied_candidates"] == 5


def test_p126g_total_inserted_rows(artifact):
    src = artifact["p126g_source_summary"]
    assert src["total_inserted_rows"] == 18000


# ---------------------------------------------------------------------------
# Adapter spec count and structure
# ---------------------------------------------------------------------------

def test_adapter_build_strategy_count(artifact):
    assert artifact["adapter_build_strategy_count"] == EXPECTED_STRATEGY_COUNT


def test_adapter_build_specs_non_empty(specs):
    assert len(specs) == EXPECTED_STRATEGY_COUNT


def test_each_spec_has_required_fields(specs):
    for spec in specs:
        for field in REQUIRED_SPEC_FIELDS:
            assert field in spec, f"spec for {spec.get('strategy_id')} missing field: {field}"


def test_every_spec_db_write_false(specs):
    for spec in specs:
        assert spec["db_write_in_p127"] is False, \
            f"{spec['strategy_id']}: db_write_in_p127 must be False"


def test_every_spec_apply_auth_required(specs):
    for spec in specs:
        assert spec["apply_authorization_required_later"] is True, \
            f"{spec['strategy_id']}: apply_authorization_required_later must be True"


def test_every_spec_has_strategy_id(specs):
    for spec in specs:
        assert spec["strategy_id"] and isinstance(spec["strategy_id"], str)


def test_every_spec_has_lottery_type(specs):
    for spec in specs:
        assert spec["lottery_type"] in {"POWER_LOTTO", "DAILY_539", "BIG_LOTTO"}


def test_every_spec_has_target_bet_count(specs):
    for spec in specs:
        assert isinstance(spec["target_bet_count"], int)
        assert spec["target_bet_count"] >= 2


def test_every_spec_has_proposed_adapter_contract(specs):
    for spec in specs:
        contract = spec["proposed_adapter_contract"]
        assert "method_signature" in contract
        assert "expected_output_count" in contract
        assert contract["must_not_fabricate"] is True
        assert contract["must_use_historical_draw_context_only"] is True


def test_every_spec_has_duplicate_guard(specs):
    for spec in specs:
        dg = spec["duplicate_guard"]
        assert "strategy" in dg
        assert "abort_on_conflict" in dg
        assert dg["abort_on_conflict"] is True


def test_every_spec_has_provenance_requirements(specs):
    for spec in specs:
        prov = spec["provenance_requirements"]
        assert "provenance_hash" in prov
        assert "dry_run_required_before_apply" in prov
        assert prov["dry_run_required_before_apply"] is True


def test_every_spec_has_tests_required(specs):
    for spec in specs:
        tests = spec["tests_required"]
        assert isinstance(tests, list)
        assert len(tests) >= 6


def test_every_spec_has_implementation_priority(specs):
    for spec in specs:
        assert isinstance(spec["implementation_priority"], int)
        assert 1 <= spec["implementation_priority"] <= EXPECTED_STRATEGY_COUNT


def test_implementation_priorities_unique(specs):
    priorities = [s["implementation_priority"] for s in specs]
    assert len(set(priorities)) == EXPECTED_STRATEGY_COUNT, \
        "Implementation priorities must be unique 1..12"


# ---------------------------------------------------------------------------
# Apply gate status
# ---------------------------------------------------------------------------

def test_apply_gate_controlled_apply_not_executed(artifact):
    gate = artifact["apply_gate_status"]
    assert gate["controlled_apply_executed"] is False


def test_apply_gate_replay_rows_inserted_zero(artifact):
    gate = artifact["apply_gate_status"]
    assert gate["replay_rows_inserted"] == 0


def test_apply_gate_adapter_implementation_not_done(artifact):
    gate = artifact["apply_gate_status"]
    assert gate["adapter_implementation_done"] is False


def test_apply_gate_db_rows_expected_unchanged(artifact):
    gate = artifact["apply_gate_status"]
    assert gate["production_db_rows_expected"] == EXPECTED_TOTAL_ROWS
    assert gate["production_db_rows_after"] == EXPECTED_TOTAL_ROWS


# ---------------------------------------------------------------------------
# Blocked / excluded governance
# ---------------------------------------------------------------------------

def test_blocked_4_star_excluded(artifact):
    assert artifact["blocked_or_excluded"]["4_STAR_excluded"] is True


def test_blocked_p108_not_run(artifact):
    assert artifact["blocked_or_excluded"]["P108_not_run"] is True


def test_blocked_p117_not_run(artifact):
    assert artifact["blocked_or_excluded"]["P117_not_run"] is True


def test_blocked_p118_not_run(artifact):
    assert artifact["blocked_or_excluded"]["P118_not_run"] is True


def test_blocked_rejected_strategies_no_action(artifact):
    assert artifact["blocked_or_excluded"]["rejected_strategies_no_action"] is True


def test_blocked_no_scheduler_install(artifact):
    assert artifact["blocked_or_excluded"]["no_scheduler_install"] is True


def test_blocked_no_db_write(artifact):
    assert artifact["blocked_or_excluded"]["no_db_write_in_P127"] is True


def test_blocked_no_controlled_apply(artifact):
    assert artifact["blocked_or_excluded"]["no_controlled_apply_in_P127"] is True


def test_blocked_no_lifecycle_mutation(artifact):
    assert artifact["blocked_or_excluded"]["no_lifecycle_mutation"] is True


# ---------------------------------------------------------------------------
# Recommended implementation order
# ---------------------------------------------------------------------------

def test_recommended_implementation_order_present(artifact):
    order = artifact["recommended_implementation_order"]
    assert len(order) == EXPECTED_STRATEGY_COUNT


def test_implementation_order_starts_with_2bet(artifact):
    order = artifact["recommended_implementation_order"]
    first = order[0]
    assert first["target_bet_count"] == 2, \
        "First implementation priority should be a 2-bet strategy"


def test_implementation_order_ends_with_highest_bet(artifact):
    order = artifact["recommended_implementation_order"]
    last = order[-1]
    assert last["target_bet_count"] == 5, \
        "Last implementation priority should be the 5-bet strategy"


# ---------------------------------------------------------------------------
# Remaining risks
# ---------------------------------------------------------------------------

def test_remaining_risks_present(artifact):
    risks = artifact["remaining_risks"]
    assert len(risks) >= 5


def test_rsr4_present(artifact):
    risk_ids = [r["id"] for r in artifact["remaining_risks"]]
    assert "RSR-4" in risk_ids


def test_rsr5_present(artifact):
    risk_ids = [r["id"] for r in artifact["remaining_risks"]]
    assert "RSR-5" in risk_ids


def test_rsr6_orphan_rows_noted(artifact):
    risk_ids = [r["id"] for r in artifact["remaining_risks"]]
    assert "RSR-6" in risk_ids, "RSR-6 (orphan bet_index=2 rows) must be noted"


# ---------------------------------------------------------------------------
# Markdown content
# ---------------------------------------------------------------------------

def test_markdown_contains_get_all_bets_contract(md_content):
    assert "get_all_bets" in md_content


def test_markdown_contains_implementation_order(md_content):
    assert "Recommended Implementation Order" in md_content


def test_markdown_contains_executive_summary(md_content):
    assert "Executive Summary" in md_content


def test_markdown_contains_non_actions(md_content):
    assert "Non-Action" in md_content or "Non-Actions" in md_content


def test_markdown_contains_apply_gate(md_content):
    assert "Apply Gate" in md_content


def test_markdown_contains_test_plan(md_content):
    assert "Test Plan" in md_content


def test_markdown_contains_classification(md_content):
    assert "P127_ADAPTER_BUILD_SPECS_READY" in md_content


def test_markdown_contains_roadmap_marker(md_content):
    assert "CTO_ROADMAP_UPDATED_AFTER_P127_ADAPTER_BUILD_SPECS_20260528" in md_content


def test_markdown_contains_p126g_closure_recap(md_content):
    assert "P126G Closure Recap" in md_content


def test_markdown_contains_remaining_risks(md_content):
    assert "Remaining Risks" in md_content


# ---------------------------------------------------------------------------
# Roadmap update status
# ---------------------------------------------------------------------------

def test_roadmap_update_status(artifact):
    rmap = artifact["roadmap_update_status"]
    assert rmap["cto_analysis_updated"] is True
    assert rmap["roadmap_updated"] is True
    assert "CTO_ROADMAP_UPDATED_AFTER_P127_ADAPTER_BUILD_SPECS_20260528" in rmap["marker"]


# ---------------------------------------------------------------------------
# Next recommended task
# ---------------------------------------------------------------------------

def test_next_task_present(artifact):
    nxt = artifact["next_recommended_task"]
    assert "task_id" in nxt
    assert "description" in nxt
    assert "prerequisite_gate" in nxt


# ---------------------------------------------------------------------------
# Live DB — adapter strategy rows are unchanged (all bet_index=1)
# ---------------------------------------------------------------------------

ADAPTER_STRATEGY_IDS = [
    "pp3_freqort_4bet",
    "midfreq_fourier_mk_3bet",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
    "zonal_entropy_2bet",
    "cold_complement_2bet",
    "power_orthogonal_5bet",
    "power_precision_3bet",
    "fourier_rhythm_3bet",
    "fourier30_markov30_2bet",
]


def test_live_db_adapter_strategies_no_new_bets_added(db_conn):
    """Confirm no new bet_index>1 rows were added for adapter strategies in P127."""
    ids_placeholder = ",".join(["?"] * len(ADAPTER_STRATEGY_IDS))
    rows = db_conn.execute(
        f"""
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id IN ({ids_placeholder})
        AND bet_index > 1
        """,
        ADAPTER_STRATEGY_IDS
    ).fetchone()[0]
    # power_precision_3bet gained 3000 rows in P140 (bet-2 + bet-3); power_orthogonal_5bet remains bet-1 only.
    # P131 applied acb_markov_midfreq_3bet bet-2+bet-3 = 3000 rows (authorized Wave 2 apply).
    # P132 applied midfreq_fourier_mk_3bet bet-2+bet-3 = 3000 rows (authorized Wave 2 apply).
    # P133 applied pp3_freqort_4bet bet-2+bet-3+bet-4 = 4500 rows (authorized Wave 2 apply).
    # P134 applied fourier_rhythm_3bet bet-2+bet-3 = 3002 rows (authorized Wave 2 apply, P9 anomaly).
    assert rows == 16502, \
        f"Expected 16502 bet_index>1 rows (P131 acb +3000, P132 midfreq_mk +3000, P133 pp3 +4500, P134 fourier +3002, P140 power_precision +3000), found {rows}"


def test_live_db_acb_markov_midfreq_3bet_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ? AND lottery_type = ?",
        ("acb_markov_midfreq_3bet", "DAILY_539")
    ).fetchone()[0]
    # P131 applied bet-2 and bet-3 rows (1500 each) → 4500 total
    assert count == 4500


def test_live_db_midfreq_acb_2bet_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ? AND lottery_type = ?",
        ("midfreq_acb_2bet", "DAILY_539")
    ).fetchone()[0]
    assert count == 1500


def test_live_db_zonal_entropy_2bet_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ? AND lottery_type = ?",
        ("zonal_entropy_2bet", "POWER_LOTTO")
    ).fetchone()[0]
    assert count == 1500


def test_live_db_cold_complement_2bet_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ? AND lottery_type = ?",
        ("cold_complement_2bet", "POWER_LOTTO")
    ).fetchone()[0]
    assert count == 1500


def test_live_db_pp3_freqort_4bet_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ? AND lottery_type = ?",
        ("pp3_freqort_4bet", "POWER_LOTTO")
    ).fetchone()[0]
    # P133 applied pp3_freqort_4bet bet-2/bet-3/bet-4 → 6000 total (4 bets × 1500)
    assert count == 6000


def test_live_db_power_orthogonal_5bet_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ? AND lottery_type = ?",
        ("power_orthogonal_5bet", "POWER_LOTTO")
    ).fetchone()[0]
    # 1550 bet_index=1 only (RSR-6 cleanup deleted the 20 orphan bet_index=2 rows)
    assert count == 1550


def test_live_db_power_precision_3bet_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ? AND lottery_type = ?",
        ("power_precision_3bet", "POWER_LOTTO")
    ).fetchone()[0]
    # P140 applied power_precision_3bet bet-2 and bet-3 (+3000) on top of bet-1 baseline.
    assert count == 4550


def test_live_db_fourier_rhythm_3bet_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ? AND lottery_type = ?",
        ("fourier_rhythm_3bet", "POWER_LOTTO")
    ).fetchone()[0]
    # P134 applied bet-2 and bet-3 rows (1501 each) → 4503 total (1501×3, P9 anomaly)
    assert count == 4503


def test_live_db_fourier30_markov30_2bet_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ? AND lottery_type = ?",
        ("fourier30_markov30_2bet", "POWER_LOTTO")
    ).fetchone()[0]
    # 1501 (1 extra row, RSR-7)
    assert count == 1501
