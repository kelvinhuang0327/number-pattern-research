"""
P94A BIG_LOTTO All-Strategy Betcount Benchmark — Contract Tests

Governance:
  - DB writes to lottery_v2.db = false
  - Replay row changes in production = 0
  - replay_rows remains 54462  (post-P94 baseline)
  - POWER_LOTTO max_draw remains 115000041
  - Lifecycle promotions = 0
  - No unsupported bet counts fabricated
  - P95/P94B recommendation exists
"""

import json
import sqlite3
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_PATH = PROJECT_ROOT / "outputs" / "replay" / "p94a_biglotto_all_strategy_betcount_benchmark_20260526.json"
MD_PATH   = PROJECT_ROOT / "docs"    / "replay" / "p94a_biglotto_all_strategy_betcount_benchmark_20260526.md"

EXPECTED_REPLAY_ROWS = 54462
EXPECTED_PL_MAX_DRAW = 115000041
EXPECTED_WINDOWS     = [30, 100, 500, 1500]
EXPECTED_BET_COUNTS  = [1, 2, 3, 5]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def artifact():
    assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ── 1. Artifact existence ─────────────────────────────────────────────────────

def test_json_artifact_exists():
    assert JSON_PATH.exists(), "P94A JSON artifact not found"


def test_markdown_artifact_exists():
    assert MD_PATH.exists(), "P94A Markdown artifact not found"


# ── 2. Classification ─────────────────────────────────────────────────────────

def test_classification_valid(artifact):
    valid = {
        "P94A_BIG_LOTTO_ALL_STRATEGY_BETCOUNT_BENCHMARK_READY",
        "P94A_BIG_LOTTO_BENCHMARK_PARTIAL_WITH_BLOCKERS",
    }
    assert artifact["final_classification"] in valid, \
        f"Invalid classification: {artifact['final_classification']}"


# ── 3. Candidate counts ───────────────────────────────────────────────────────

def test_biglotto_candidate_count_present(artifact):
    cs = artifact["candidate_summary"]
    assert cs["total_biglotto_strategies"] > 0
    assert cs["benchmarkable_count"] > 0


def test_unsupported_count_present(artifact):
    cs = artifact["candidate_summary"]
    assert "unsupported_blocked_count" in cs
    assert cs["unsupported_blocked_count"] >= 0


def test_row_backed_count(artifact):
    cs = artifact["candidate_summary"]
    assert cs["row_backed_count"] >= 1


def test_adapter_backed_count(artifact):
    cs = artifact["candidate_summary"]
    assert cs["adapter_backed_count"] >= 1


# ── 4. Observation windows ───────────────────────────────────────────────────

def test_observation_windows_exactly(artifact):
    assert artifact["observation_windows"] == EXPECTED_WINDOWS, \
        f"Expected {EXPECTED_WINDOWS}, got {artifact['observation_windows']}"


# ── 5. Bet counts ────────────────────────────────────────────────────────────

def test_bet_counts_exactly(artifact):
    assert artifact["bet_counts"] == EXPECTED_BET_COUNTS, \
        f"Expected {EXPECTED_BET_COUNTS}, got {artifact['bet_counts']}"


# ── 6. Ranking tables complete ───────────────────────────────────────────────

def test_ranking_tables_all_combinations(artifact):
    rt = artifact["ranking_tables"]
    for w in EXPECTED_WINDOWS:
        assert str(w) in rt, f"Missing window {w} in ranking_tables"
        for bc in EXPECTED_BET_COUNTS:
            assert str(bc) in rt[str(w)], f"Missing bet_count {bc} for window {w}"
            # Either has entries OR is explicitly empty list (all blocked)
            assert isinstance(rt[str(w)][str(bc)], list), \
                f"ranking_tables[{w}][{bc}] must be a list"


def test_ranking_tables_have_top3_or_explicit_empty(artifact):
    rt = artifact["ranking_tables"]
    for w in EXPECTED_WINDOWS:
        for bc in EXPECTED_BET_COUNTS:
            entries = rt[str(w)][str(bc)]
            assert len(entries) <= 3, f"More than 3 entries for w={w} bc={bc}"
            for e in entries:
                assert "strategy_id" in e
                assert "m3_plus_rate" in e
                assert "lifecycle" in e
                assert "source_category" in e


# ── 7. Ranking metric ────────────────────────────────────────────────────────

def test_ranking_metric_is_m3_plus(artifact):
    assert artifact["ranking_metric"] == "m3_plus_rate"


# ── 8. Tie-breakers documented ───────────────────────────────────────────────

def test_tiebreakers_documented(artifact):
    tbs = artifact["tie_breakers"]
    assert "avg_hit_count" in tbs
    assert any("zero" in t.lower() for t in tbs)
    assert any("sample" in t.lower() for t in tbs)


# ── 9. No-promotion policy ────────────────────────────────────────────────────

def test_no_promotion_policy_exists(artifact):
    assert "no_promotion_policy" in artifact
    policy = artifact["no_promotion_policy"]
    assert "Rejected" in policy or "rejected" in policy


def test_lifecycle_promotions_zero(artifact):
    assert artifact["lifecycle_promotions"] == 0


# ── 10. DB write behavior ─────────────────────────────────────────────────────

def test_db_writes_false(artifact):
    assert artifact["db_writes"] is False


def test_replay_row_changes_zero(artifact):
    assert artifact["replay_row_changes"] == 0


# ── 11. Production row count (post-P94 baseline) ─────────────────────────────

def test_production_replay_rows_54462(db_conn):
    c = db_conn.cursor()
    c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = c.fetchone()[0]
    assert count == EXPECTED_REPLAY_ROWS, \
        f"Expected {EXPECTED_REPLAY_ROWS} rows, got {count}"


def test_artifact_rows_match_54462(artifact):
    """Artifact must record the post-P94 baseline."""
    assert artifact["production_rows_before"] == EXPECTED_REPLAY_ROWS
    assert artifact["production_rows_after"]  == EXPECTED_REPLAY_ROWS


# ── 12. POWER_LOTTO max draw unchanged ───────────────────────────────────────

def test_power_lotto_max_draw_115000041(db_conn):
    c = db_conn.cursor()
    c.execute("SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'")
    max_draw = c.fetchone()[0]
    assert max_draw == EXPECTED_PL_MAX_DRAW, \
        f"Expected PL max draw {EXPECTED_PL_MAX_DRAW}, got {max_draw}"


# ── 13. Unsupported bet counts not fabricated ────────────────────────────────

def test_unsupported_bet_counts_not_fabricated(artifact):
    """1-bet strategies must not have valid data for 2/3/5-bet variants."""
    results = artifact["strategy_results"]
    for sid, meta in results.items():
        if meta["native_bets"] == 1:
            for w in EXPECTED_WINDOWS:
                for bc in [2, 3, 5]:
                    entry = meta["windows"][str(w)][str(bc)]
                    assert entry["blocker"] is not None, \
                        f"Strategy {sid} native_bets=1 but has valid {bc}-bet data for w={w}"
                    assert entry["data_source"] == "unsupported", \
                        f"Strategy {sid} native_bets=1 should have data_source=unsupported for {bc}-bet"


# ── 14. P95/P94B recommendation present ─────────────────────────────────────

def test_recommendation_exists(artifact):
    rec = artifact.get("recommended_next_step", "")
    assert rec in ("P94B_CONTROLLED_BENCHMARK_REVIEW", "P95_SELECTED_STRATEGY_DRY_RUN"), \
        f"Unexpected recommendation: {rec}"


def test_recommendation_note_mentions_p94b_or_p95(artifact):
    note = artifact.get("recommended_next_step_note", "")
    assert "P94B" in note or "P95" in note


# ── 15. Baseline note acknowledges P94 adjustment ───────────────────────────

def test_baseline_note_acknowledges_p94_adjustment(artifact):
    note = artifact.get("baseline_note", "")
    assert "54462" in note or "P94" in note


# ── 16. Baselines sane ──────────────────────────────────────────────────────

def test_baselines_present_and_sane(artifact):
    bs = artifact["baselines"]
    for bc in EXPECTED_BET_COUNTS:
        b = bs[str(bc)]
        assert 0 < b["m3_plus_rate_random"] < 1.0
        assert b["m3_plus_rate_random"] > artifact["baselines"]["1"]["m3_plus_rate_random"] or bc == 1


# ── 17. BIG_LOTTO draws count reasonable ─────────────────────────────────────

def test_biglotto_draws_count(artifact):
    assert artifact["biglotto_draws_total"] >= 1500


# ── 18. Rejected caveat present ─────────────────────────────────────────────

def test_rejected_caveat_exists(artifact):
    caveat = artifact.get("rejected_offline_caveat", "")
    assert len(caveat) > 50


# ── 19. Blocked strategies listed ───────────────────────────────────────────

def test_blocked_strategies_listed(artifact):
    blocked = artifact.get("blocked_strategies", [])
    assert len(blocked) >= 1
    for b in blocked:
        assert "strategy_id" in b
        assert "blocker" in b


# ── 20. No-data policy documented ───────────────────────────────────────────

def test_markdown_has_unsupported_policy(artifact):
    """Markdown artifact must exist and mention unsupported policy."""
    assert MD_PATH.exists()
    content = MD_PATH.read_text()
    assert "UNSUPPORTED" in content or "unsupported" in content
    assert "fabricated" in content.lower() or "duplicated" in content.lower() or "No bet counts are fabricated" in content


# ── 21. 5-bet universally unsupported for BIG_LOTTO ─────────────────────────

def test_5bet_unsupported_for_all_biglotto(artifact):
    """No BIG_LOTTO strategy has a native 5-bet adapter (max is 4-bet)."""
    results = artifact["strategy_results"]
    for sid, meta in results.items():
        if meta["native_bets"] < 5:
            for w in EXPECTED_WINDOWS:
                entry = meta["windows"][str(w)]["5"]
                assert entry["blocker"] is not None, \
                    f"Strategy {sid} native_bets={meta['native_bets']} should block 5-bet"


# ── 22. Strategy results cover all combinations ──────────────────────────────

def test_strategy_results_cover_all_windows_and_bets(artifact):
    results = artifact["strategy_results"]
    assert len(results) >= 11  # at least 11 row-backed strategies
    for sid, meta in results.items():
        for w in EXPECTED_WINDOWS:
            assert str(w) in meta["windows"], f"{sid} missing window {w}"
            for bc in EXPECTED_BET_COUNTS:
                assert str(bc) in meta["windows"][str(w)], \
                    f"{sid} missing bet_count {bc} for window {w}"


# ── P93 regression guard ─────────────────────────────────────────────────────

def test_p93_artifacts_intact():
    p93 = PROJECT_ROOT / "outputs" / "replay" / "p93_tier_b_replay_adapter_bootstrap_dryrun_20260526.json"
    assert p93.exists(), "P93 artifact missing"


# ── P92 regression guard ─────────────────────────────────────────────────────

def test_p92_artifacts_intact():
    p92 = PROJECT_ROOT / "outputs" / "replay" / "p92_tier_b_adapter_audit_dry_run_plan_20260526.json"
    assert p92.exists(), "P92 artifact missing"


# ── P91 regression guard ─────────────────────────────────────────────────────

def test_p91_artifacts_intact():
    p91 = PROJECT_ROOT / "outputs" / "replay" / "p91_all_strategy_replay_expansion_inventory_20260526.json"
    assert p91.exists(), "P91 artifact missing"


# ── P79 production rows unchanged ────────────────────────────────────────────

def test_p79_production_rows_intact(db_conn):
    c = db_conn.cursor()
    c.execute("SELECT id, strategy_id, dry_run, truth_level FROM strategy_prediction_replays WHERE id IN (46961, 46962)")
    rows = {r[0]: r for r in c.fetchall()}
    assert 46961 in rows, "P79 row id=46961 missing"
    assert 46962 in rows, "P79 row id=46962 missing"
    assert rows[46961][1] == "fourier_rhythm_3bet"
    assert rows[46962][1] == "fourier30_markov30_2bet"
    assert rows[46961][2] == 0  # dry_run=0
    assert rows[46962][2] == 0  # dry_run=0
