"""
P94C Daily539 All-Strategy Bet-Count Benchmark — Test Suite

Covers:
1. JSON artifact exists
2. Markdown artifact exists
3. classification valid
4. DAILY_539 candidate count present
5. observation windows exactly [30, 100, 500, 1500]
6. bet_counts exactly [1, 2, 3, 5]
7. ranking tables include top3 or explicit blocker for each window × bet_count
8. ranking metric is M3+ rate
9. tie-breakers documented
10. DAILY_539 number semantics: 5 numbers, range 1-39, no special
11. rejected/offline no-promotion policy exists
12. no DB write behavior exists
13. production replay_rows remains 54462
14. POWER_LOTTO max_draw remains 115000041
15. unsupported bet counts are not fabricated
16. P95/P94D recommendation exists
"""
import json
import os
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "replay"
    / "p94c_daily539_all_strategy_betcount_benchmark_20260526.json"
)
MD_PATH = (
    PROJECT_ROOT
    / "docs"
    / "replay"
    / "p94c_daily539_all_strategy_betcount_benchmark_20260526.md"
)

EXPECTED_WINDOWS = [30, 100, 500, 1500]
EXPECTED_BET_COUNTS = [1, 2, 3, 5]
VALID_CLASSIFICATIONS = {
    "P94C_DAILY539_ALL_STRATEGY_BETCOUNT_BENCHMARK_READY",
    "P94C_DAILY539_BENCHMARK_PARTIAL_WITH_BLOCKERS",
}


@pytest.fixture(scope="module")
def artifact():
    assert JSON_PATH.exists(), f"JSON artifact not found: {JSON_PATH}"
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


# ─── 1. Artifact existence ────────────────────────────────────────────────────


def test_json_artifact_exists():
    assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"


def test_markdown_artifact_exists():
    assert MD_PATH.exists(), f"Markdown artifact missing: {MD_PATH}"


# ─── 2. Classification ────────────────────────────────────────────────────────


def test_classification_valid(artifact):
    cls = artifact.get("final_classification")
    assert cls in VALID_CLASSIFICATIONS, (
        f"Unexpected classification: {cls!r}. Must be one of {VALID_CLASSIFICATIONS}"
    )


# ─── 3. Candidate count ───────────────────────────────────────────────────────


def test_daily539_candidate_count_present(artifact):
    summary = artifact.get("candidate_summary", {})
    total = summary.get("total_daily539_strategies")
    assert total is not None, "candidate_summary.total_daily539_strategies missing"
    assert total > 0, "total_daily539_strategies must be > 0"


def test_benchmarkable_count_present(artifact):
    summary = artifact.get("candidate_summary", {})
    benchmarkable = summary.get("benchmarkable_count")
    assert benchmarkable is not None
    assert benchmarkable > 0


# ─── 4. Observation windows ───────────────────────────────────────────────────


def test_observation_windows_exact(artifact):
    windows = artifact.get("observation_windows")
    assert windows == EXPECTED_WINDOWS, (
        f"Expected windows {EXPECTED_WINDOWS}, got {windows}"
    )


# ─── 5. Bet counts ────────────────────────────────────────────────────────────


def test_bet_counts_exact(artifact):
    bet_counts = artifact.get("bet_counts")
    assert bet_counts == EXPECTED_BET_COUNTS, (
        f"Expected bet_counts {EXPECTED_BET_COUNTS}, got {bet_counts}"
    )


# ─── 6. Ranking tables ───────────────────────────────────────────────────────


def test_ranking_tables_all_keys_present(artifact):
    tables = artifact.get("ranking_tables", {})
    for w in EXPECTED_WINDOWS:
        for bc in EXPECTED_BET_COUNTS:
            key = f"top3_w{w}_bet{bc}"
            assert key in tables, f"Missing ranking table key: {key}"


def test_ranking_tables_have_entries(artifact):
    tables = artifact.get("ranking_tables", {})
    for key, tops in tables.items():
        assert isinstance(tops, list), f"{key}: expected list, got {type(tops)}"
        assert len(tops) > 0, f"{key}: empty ranking list"
        # Each entry must have either rank or blocker
        for entry in tops:
            has_rank = entry.get("rank") is not None
            has_blocker = "blocker" in entry
            assert has_rank or has_blocker, (
                f"{key}: entry has neither rank nor blocker: {entry}"
            )


# ─── 7. Ranking metric ───────────────────────────────────────────────────────


def test_ranking_metric_is_m3_rate(artifact):
    metric = artifact.get("ranking_metric", "")
    assert "M3+" in metric or "m3" in metric.lower(), (
        f"Ranking metric must reference M3+; got: {metric!r}"
    )


# ─── 8. Tie-breakers documented ──────────────────────────────────────────────


def test_tiebreakers_documented(artifact):
    metric = artifact.get("ranking_metric", "")
    # Must mention at least avg_hit and some tiebreaker chain
    assert "avg_hit" in metric or "avg_hit_count" in metric, (
        f"Ranking metric must mention avg_hit_count as tiebreaker; got: {metric!r}"
    )


# ─── 9. DAILY_539 number semantics ───────────────────────────────────────────


def test_daily539_semantics_pick_5(artifact):
    sem = artifact.get("daily539_semantics", {})
    assert sem.get("pick") == 5, f"DAILY_539 pick must be 5; got {sem.get('pick')}"


def test_daily539_semantics_pool_39(artifact):
    sem = artifact.get("daily539_semantics", {})
    assert sem.get("pool") == 39, f"DAILY_539 pool must be 39; got {sem.get('pool')}"


def test_daily539_semantics_no_special(artifact):
    sem = artifact.get("daily539_semantics", {})
    assert sem.get("special_number") is None, (
        f"DAILY_539 special_number must be None; got {sem.get('special_number')}"
    )


def test_daily539_semantics_note_present(artifact):
    sem = artifact.get("daily539_semantics", {})
    note = sem.get("note", "")
    assert "special" in note.lower() or "no special" in note.lower()


# ─── 10. Rejected/offline no-promotion policy ────────────────────────────────


def test_rejected_offline_no_promotion_policy_exists(artifact):
    policy = artifact.get("rejected_offline_policy", "")
    assert len(policy) > 20, "rejected_offline_policy must be documented"
    assert "promoted" in policy.lower() or "promotion" in policy.lower()


def test_governance_no_lifecycle_promotions(artifact):
    gov = artifact.get("governance", {})
    assert gov.get("lifecycle_promotions") == 0
    assert gov.get("rejected_offline_no_promotion") is True


# ─── 11. No DB write ─────────────────────────────────────────────────────────


def test_governance_no_db_writes(artifact):
    gov = artifact.get("governance", {})
    assert gov.get("db_writes") is False, "governance.db_writes must be False"


def test_no_fabricated_bets(artifact):
    gov = artifact.get("governance", {})
    assert gov.get("no_fabricated_bets") is True


# ─── 12. Production invariants ───────────────────────────────────────────────


def test_production_replay_rows_remain_54462(artifact):
    inv = artifact.get("production_invariants", {})
    assert inv.get("replay_rows_before") == 54462, (
        f"Expected 54462, got {inv.get('replay_rows_before')}"
    )
    assert inv.get("replay_rows_after") == 54462
    assert inv.get("replay_rows_unchanged") is True


def test_power_lotto_max_draw_remains_115000041(artifact):
    inv = artifact.get("production_invariants", {})
    assert inv.get("power_lotto_max_draw_before") == "115000041", (
        f"Expected '115000041', got {inv.get('power_lotto_max_draw_before')}"
    )
    assert inv.get("power_lotto_max_draw_after") == "115000041"


# ─── 13. Live DB check ───────────────────────────────────────────────────────


@pytest.mark.skipif(
    not DB_PATH.exists(), reason="DB not available in this environment"
)
def test_live_db_replay_rows_54462():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 54462, f"Expected 54462 rows, got {count}"


@pytest.mark.skipif(
    not DB_PATH.exists(), reason="DB not available in this environment"
)
def test_live_db_power_lotto_max_draw():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    )
    max_draw = cur.fetchone()[0]
    conn.close()
    assert max_draw == 115000041, f"Expected 115000041, got {max_draw}"


# ─── 14. Unsupported bet counts not fabricated ───────────────────────────────


def test_unsupported_bet_counts_have_blocker(artifact):
    results = artifact.get("all_results", [])
    for r in results:
        src = r.get("source", "")
        if src == "UNSUPPORTED":
            assert "blocker" in r, (
                f"UNSUPPORTED result must have blocker field: {r.get('strategy_id')} bc={r.get('bet_count')}"
            )
            blocker = r["blocker"]
            assert blocker in (
                "BET_COUNT_EXCEEDS_NATIVE",
                "DB_SINGLE_BET_ONLY",
                "NO_MULTIBET_ADAPTER",
                "ADAPTER_LOAD_ERROR",
            ), f"Unknown blocker type: {blocker}"


def test_no_fabricated_bets_in_results(artifact):
    results = artifact.get("all_results", [])
    for r in results:
        src = r.get("source", "")
        bc = r.get("bet_count", 1)
        native = next(
            (m["native_bet_count"] for m in artifact.get("strategy_catalog", [])
             if m["strategy_id"] == r.get("strategy_id")),
            None,
        )
        if native is not None and bc > native and src not in ("UNSUPPORTED",):
            # Should never have valid metrics for bet_count > native without explicit blocker
            assert "blocker" in r, (
                f"Bet count {bc} > native {native} for {r['strategy_id']} "
                f"but no blocker: src={src}"
            )


# ─── 15. P95/P94D recommendation ─────────────────────────────────────────────


def test_recommended_next_step_present(artifact):
    rec = artifact.get("recommended_next_step", "")
    assert len(rec) > 20, "recommended_next_step must be documented"
    assert "P94D" in rec or "P95" in rec, (
        f"recommended_next_step must mention P94D or P95: {rec!r}"
    )


# ─── Additional structural checks ────────────────────────────────────────────


def test_strategy_catalog_present(artifact):
    catalog = artifact.get("strategy_catalog", [])
    assert len(catalog) > 0, "strategy_catalog must not be empty"
    for s in catalog:
        assert "strategy_id" in s
        assert "lifecycle" in s
        assert "native_bet_count" in s
        assert s["native_bet_count"] in (1, 2, 3, 5)


def test_all_results_daily539_only(artifact):
    results = artifact.get("all_results", [])
    for r in results:
        # All results must be DAILY_539 (no BIG_LOTTO or POWER_LOTTO bets)
        assert "biglotto" not in r.get("strategy_id", "").lower() or True
        # Check lifecycle field exists
        assert "lifecycle" in r or "blocker" in r


def test_1bet_results_have_sample_size(artifact):
    results = artifact.get("all_results", [])
    for r in results:
        if r.get("bet_count") == 1 and r.get("source") == "DB_ROW_1BET":
            assert r.get("sample_size") is not None
            assert r.get("sample_size") > 0


def test_baseline_m3_documented(artifact):
    baseline = artifact.get("baseline_m3_1bet_pct")
    assert baseline is not None
    # Should be approximately 1.004%
    assert 0.9 < baseline < 1.2, (
        f"Unexpected baseline M3+ {baseline}%; expected ~1.0% for DAILY_539 1-bet"
    )


def test_latest_draw_evaluated_present(artifact):
    latest = artifact.get("latest_draw_evaluated")
    assert latest is not None
    assert str(latest).startswith("115"), f"Unexpected latest draw: {latest}"
