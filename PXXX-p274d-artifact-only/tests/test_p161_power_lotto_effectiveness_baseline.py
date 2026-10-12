"""
Tests for P161: POWER_LOTTO Replay Strategy Effectiveness Baseline.
===================================================================
All tests are READ-ONLY. No DB writes, no staging checks.

Asserts the key invariants:
  - Phase-0 row counts (total 94924, POWER_LOTTO 36104/10/1551)
  - Statistical unit handling: per-strategy n_draws is distinct target_draw,
    and the primary main test uses the per-draw mean (NOT per-bet rows)
  - The report numbers match FRESH read-only queries against the DB
  - Random baselines are exact (36/38 main, 1/8 special)
  - Special uses predicted_special IS NOT NULL only (9000 rows), not the
    diluted all-row avg
  - Multiple-testing correction present; honest NULL on the primary headline
  - Leakage labels present; lifecycle survivorship caveat present
  - DB row count is unchanged by running the analysis (no writes)
"""
from __future__ import annotations

import json
import math
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p161_effectiveness_baseline_20260531.json"
)
MD_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p161_effectiveness_baseline_20260531.md"
)
SCRIPT = PROJECT_ROOT / "analysis" / "power_lotto" / "p161_effectiveness_baseline.py"

LOTTERY = "POWER_LOTTO"
EXPECTED_TOTAL_ROWS = 94924
EXPECTED_PL_ROWS = 36104
EXPECTED_PL_STRATEGIES = 10
EXPECTED_PL_DRAWS = 1551
MAIN_RANDOM = 36.0 / 38.0          # 0.9473684210526315
SPECIAL_RANDOM = 1.0 / 8.0          # 0.125
EXPECTED_SPECIAL_ROWS = 9000        # predicted_special IS NOT NULL
TOL = 1e-6

pytestmark = [pytest.mark.requires_db, pytest.mark.requires_zen_gates_db]


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def report():
    """Run the analysis (idempotent, read-only) then load the JSON report."""
    if DB_PATH.exists():
        # Generate fresh artifacts from the read-only analysis.
        res = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert res.returncode == 0, f"analysis script failed:\n{res.stderr}"
    assert JSON_OUT.exists(), f"missing report JSON: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.execute("PRAGMA query_only=ON;")
    yield c
    c.close()


# ── Phase-0 invariants ─────────────────────────────────────────────────────
def test_db_total_rows(conn):
    n = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays;"
    ).fetchone()[0]
    assert n == EXPECTED_TOTAL_ROWS


def test_power_lotto_counts(conn):
    rows, strats, draws = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT strategy_id), COUNT(DISTINCT target_draw) "
        "FROM strategy_prediction_replays WHERE lottery_type=?;",
        (LOTTERY,),
    ).fetchone()
    assert rows == EXPECTED_PL_ROWS
    assert strats == EXPECTED_PL_STRATEGIES
    assert draws == EXPECTED_PL_DRAWS


def test_bet_index_column_present(conn):
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(strategy_prediction_replays);"
    ).fetchall()]
    assert "bet_index" in cols, (
        "bet_index missing — wrong checkout (likely main @P128). STOP."
    )


# ── Report structure ──────────────────────────────────────────────────────
def test_classification_ready(report):
    assert report["classification"] == "P161_POWER_LOTTO_EFFECTIVENESS_BASELINE_READY"


def test_report_has_all_seven_sections(report):
    for key in (
        "section_1_3_per_strategy",
        "section_2_main_vs_special_separated",
        "section_4_lifecycle_groups",
        "section_5_multi_bet_slots",
        "section_6_multiple_testing",
        "section_7_leakage_labeling",
    ):
        assert key in report, f"missing {key}"
    # §3 strategy-vs-random verdicts live inside per-strategy rows
    assert all("main_verdict_vs_random" in s
               for s in report["section_1_3_per_strategy"])


def test_md_artifact_exists_and_nonempty():
    assert MD_OUT.exists()
    assert len(MD_OUT.read_text()) > 1000


# ── Random baselines exact ─────────────────────────────────────────────────
def test_random_baselines_exact(report):
    b = report["baselines"]
    assert abs(b["main_random_E_hit_count"] - MAIN_RANDOM) < 1e-12
    assert abs(b["special_random"] - SPECIAL_RANDOM) < 1e-12


# ── Statistical unit handling ──────────────────────────────────────────────
def test_statistical_unit_is_distinct_draw(report, conn):
    ds = report["db_snapshot"]
    assert ds["statistical_unit"] == "distinct target_draw"
    assert ds["statistical_unit_n"] == EXPECTED_PL_DRAWS
    # per-strategy n_draws must equal distinct target_draw per strategy
    fresh = dict(conn.execute(
        "SELECT strategy_id, COUNT(DISTINCT target_draw) "
        "FROM strategy_prediction_replays WHERE lottery_type=? GROUP BY strategy_id;",
        (LOTTERY,),
    ).fetchall())
    for s in report["section_1_3_per_strategy"]:
        assert s["n_draws"] == fresh[s["strategy_id"]], s["strategy_id"]
        # primary main test must declare per-draw unit (NOT per-bet rows)
        assert s["statistical_unit"] == "per_draw_mean_hit_count"
        # Panel may be UNBALANCED (some draws have fewer bet slots, e.g.
        # power_orthogonal_5bet has 1550 bet1 draws but 1500 for bets 2-5).
        # Therefore n_bet_rows <= n_draws * n_bet_slots, and the per-draw mean
        # correctly averages whatever bets exist for each draw.
        assert s["n_bet_rows"] <= s["n_draws"] * s["n_bet_slots"], s["strategy_id"]
        assert s["n_bet_rows"] >= s["n_draws"], s["strategy_id"]


def test_per_strategy_mean_matches_fresh_per_draw_query(report, conn):
    """The reported per-strategy mean_hit_count must equal a fresh per-draw-mean
    query (statistical unit = draw), proving numbers are not fabricated."""
    for s in report["section_1_3_per_strategy"]:
        sid = s["strategy_id"]
        draw_means = [r[0] for r in conn.execute(
            "SELECT AVG(hit_count*1.0) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? GROUP BY target_draw;",
            (LOTTERY, sid),
        ).fetchall()]
        fresh_mean = sum(draw_means) / len(draw_means)
        assert abs(s["mean_hit_count"] - fresh_mean) < 1e-4, sid
        # secondary pseudo-replicated bet-row mean must equal raw AVG(hit_count)
        bet_row_mean = conn.execute(
            "SELECT AVG(hit_count*1.0) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?;",
            (LOTTERY, sid),
        ).fetchone()[0]
        assert abs(s["bet_row_mean_hit_count_pseudo_replicated"] - bet_row_mean) < 1e-4, sid


def test_pool_main_avg_matches_fresh(report, conn):
    fresh = conn.execute(
        "SELECT AVG(hit_count*1.0) FROM strategy_prediction_replays WHERE lottery_type=?;",
        (LOTTERY,),
    ).fetchone()[0]
    reported = report["section_2_main_vs_special_separated"]["pool_main_avg_hit_count"]
    assert abs(reported - fresh) < 1e-4
    # honest prior: ~0.9674, essentially at-random vs 0.9474
    assert abs(reported - 0.967427) < 1e-3


# ── Main vs special separation ─────────────────────────────────────────────
def test_special_uses_predicted_special_not_null_only(report, conn):
    s2 = report["section_2_main_vs_special_separated"]
    sp_n, sp_hits = conn.execute(
        "SELECT COUNT(*), SUM(special_hit) FROM strategy_prediction_replays "
        "WHERE lottery_type=? AND predicted_special IS NOT NULL;",
        (LOTTERY,),
    ).fetchone()
    assert sp_n == EXPECTED_SPECIAL_ROWS
    assert s2["special_predicted_special_not_null_n"] == sp_n
    assert s2["special_hits"] == sp_hits
    fresh_rate = sp_hits / sp_n
    assert abs(s2["special_hit_rate"] - fresh_rate) < 1e-4
    # must NOT equal the diluted all-row avg
    diluted = conn.execute(
        "SELECT AVG(special_hit*1.0) FROM strategy_prediction_replays WHERE lottery_type=?;",
        (LOTTERY,),
    ).fetchone()[0]
    assert abs(s2["special_diluted_all_row_avg_DO_NOT_USE"] - diluted) < 1e-4
    assert abs(s2["special_hit_rate"] - diluted) > 0.05  # clearly different
    # special is at/below 1/8 (honest prior)
    assert s2["special_verdict"] in ("BELOW", "AT")


# ── §5 multi-bet slots, coverage-normalized ─────────────────────────────────
def test_bet_slot_coverage_normalized_one_row_per_draw(report, conn):
    """Each (strategy, bet_index) slot must have exactly one row per draw, so the
    per-slot mean is over 6-number bets (coverage normalized, not inflated)."""
    for sl in report["section_5_multi_bet_slots"]["per_strategy_slot"]:
        n_rows, n_draws = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT target_draw) "
            "FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? AND bet_index=?;",
            (LOTTERY, sl["strategy_id"], sl["bet_index"]),
        ).fetchone()
        assert n_rows == n_draws == sl["n_rows"] == sl["n_draws"], (
            sl["strategy_id"], sl["bet_index"]
        )


def test_bet_position_aggregate_matches_fresh(report, conn):
    for p in report["section_5_multi_bet_slots"]["by_bet_position_aggregate"]:
        fresh = conn.execute(
            "SELECT AVG(hit_count*1.0) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND bet_index=?;",
            (LOTTERY, p["bet_index"]),
        ).fetchone()[0]
        assert abs(p["mean_hit_count"] - fresh) < 1e-4, p["bet_index"]


# ── §6 multiple-testing correction ──────────────────────────────────────────
def test_multiple_testing_present_and_honest_null(report):
    mt = report["section_6_multiple_testing"]
    assert set(mt["correction_methods"]) == {"bonferroni", "benjamini_hochberg"}
    assert mt["family_size_finite_p"] >= 10
    # every finite raw p must have a corrected p >= raw p (correction never lowers)
    for f in mt["family"]:
        if f["p_raw"] is not None and f["p_bonferroni"] is not None:
            assert f["p_bonferroni"] + TOL >= f["p_raw"]
        if f["p_raw"] is not None and f["p_bh"] is not None:
            assert f["p_bh"] + TOL >= f["p_raw"]
    # PRIMARY headline = honest NULL: no per-strategy main mean beats random
    assert mt["any_strategy_beats_random_after_correction"] is False
    assert mt["survivors_after_bonferroni_above_random"] == []


def test_min_ndraws_gate_enforced(report):
    mt = report["section_6_multiple_testing"]
    assert mt["min_ndraws_gate_for_ranking"] >= 500
    # every strategy meets the gate (all have ~1500 draws) — no naked ranking risk
    assert all(s["meets_min_ndraws_for_ranking"]
               for s in report["section_1_3_per_strategy"])


def test_best_single_strategy_does_not_beat_random_after_correction(report):
    bs = report["best_single_strategy"]
    assert bs is not None
    # best by mean is midfreq_fourier_mk_3bet but it does NOT survive correction
    assert bs["beats_random_after_correction"] is False
    assert bs["p_bonferroni"] >= 0.05


def test_secondary_slot_survivor_flagged_with_caveat(report):
    """The one bet slot that survives correction must be reported AND carry the
    descriptive / no-walk-forward caveat (honest treatment, not buried)."""
    mt = report["section_6_multiple_testing"]
    survivors = mt["secondary_bet_slot_survivors_after_bonferroni_above_random"]
    assert "slot::midfreq_fourier_mk_3bet#bet1" in survivors
    caveat = mt["secondary_slot_survivor_caveat"].lower()
    assert "descriptive" in caveat
    assert "walk-forward" in caveat or "oos" in caveat


# ── §4 lifecycle survivorship caveat + §7 leakage labels ────────────────────
def test_lifecycle_groups_descriptive_with_survivorship_caveat(report):
    s4 = report["section_4_lifecycle_groups"]
    assert s4["label"] == "DESCRIPTIVE_ONLY"
    caveat = s4["survivorship_bias_caveat"].lower()
    assert "survivorship" in caveat or "selection bias" in caveat
    assert "after the label was assigned" in caveat
    # lifecycle resolved from registry JOIN (ONLINE + RETIRED present)
    lcs = {g["lifecycle"] for g in s4["groups"]}
    assert "ONLINE" in lcs


def test_leakage_labels_present(report):
    lk = report["section_7_leakage_labeling"]
    assert lk["all_in_sample_comparisons_are"] == "DESCRIPTIVE"
    assert lk["predictive_label"] == "NOT_ESTABLISHED_NO_WALK_FORWARD"
    assert "500" in lk["predictive_claim_requirement"]


def test_lifecycle_resolution_and_cross_lottery_mismatch(report):
    # No silent drops: any unresolved id must be explicitly listed.
    per = report["section_1_3_per_strategy"]
    for s in per:
        assert s["lifecycle"] in (
            "ONLINE", "OFFLINE", "REJECTED", "OBSERVATION", "RETIRED",
            "DB_ONLY_MISSING_LIFECYCLE", "LIFECYCLE_UNRESOLVED",
        )
    # midfreq_fourier_2bet is a known cross-lottery registry mismatch
    mismatch_ids = {m["strategy_id"]
                    for m in report["cross_lottery_registry_mismatch"]}
    assert "midfreq_fourier_2bet" in mismatch_ids


# ── Governance / no-write proof ─────────────────────────────────────────────
def test_no_db_write_governance(report):
    g = report["governance"]
    assert g["db_writes"] == 0
    assert g["controlled_apply"] is False
    ds = report["db_snapshot"]
    assert ds["total_rows_before"] == ds["total_rows_after"] == EXPECTED_TOTAL_ROWS
    assert ds["total_rows_unchanged"] is True
    assert report["pragma_query_only"] is True


def test_honest_null_statement_no_betting_advice(report):
    stmt = report["honest_null_statement"].lower()
    # honest NULL framing present
    assert "at-random" in stmt or "indistinguishable" in stmt
    # NO betting advice / guaranteed-win language
    for banned in ("guaranteed", "guarantee", "sure win", "betting advice"):
        # 'no ... guaranteed-win' is allowed (it's a disclaimer), so check it's
        # only present in the disclaimer sense
        if banned in stmt:
            assert "no " in stmt and ("guaranteed-win" in stmt or "betting advice" in stmt)


def test_db_unchanged_after_full_run(conn):
    """Final proof: the DB row count is still 94924 after generating the report."""
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    assert n == EXPECTED_TOTAL_ROWS
