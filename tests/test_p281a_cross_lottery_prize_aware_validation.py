"""Focused tests for P281A cross-lottery prize-aware success-definition
verification and inferential validation (read-only research / replay).

Pure tests run without a DB. The end-to-end tests are gated on the environment
variable ``P281A_DB`` pointing to a readable canonical SQLite DB (the canonical
DB is gitignored and not present in a fresh worktree); they skip if unset.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.p281a_cross_lottery_prize_aware_validation as P281  # noqa: E402
from lottery_api.prize_aware_replay_adapter import (  # noqa: E402
    EXCLUSION_CAUSALITY_FAILURE,
    EXCLUSION_MISSING_PREDICTED_SECOND_ZONE,
    _check_eligibility,
)
from lottery_api.prize_aware_scorer import score_replay_row  # noqa: E402
from analysis.p273a_prize_aware_inferential_validation import (  # noqa: E402
    benjamini_hochberg,
    bonferroni_pvalue,
    exact_distinct_draw_baseline,
    ticket_universe,
    upper_tail_pvalue,
)

TOOL_FILE = REPO_ROOT / "tools/p281a_cross_lottery_prize_aware_validation.py"
_ALLOWED_FINAL = {
    "P281A_CROSS_LOTTERY_PRIZE_AWARE_VALIDATION_PR_OPEN_NULL_NO_PUBLICATION",
    "P281A_CROSS_LOTTERY_PRIZE_AWARE_VALIDATION_PR_OPEN_OBSERVATION_CANDIDATES_NO_PUBLICATION",
    "P281A_CROSS_LOTTERY_PRIZE_AWARE_VALIDATION_PR_OPEN_SUPPORT_BLOCKED_NO_PUBLICATION",
}


# --------------------------------------------------------------------------- #
# Task G #1-#3 — prize-aware truth tables (verified via the real P271C scorer) #
# --------------------------------------------------------------------------- #

def test_big_truth_table_rule():
    # M3 wins; M2+special wins; M2 without special loses.
    assert score_replay_row("BIG_LOTTO", 3, 0)["any_prize_aware_win"] is True
    assert score_replay_row("BIG_LOTTO", 2, 1)["any_prize_aware_win"] is True
    assert score_replay_row("BIG_LOTTO", 2, 0)["any_prize_aware_win"] is False
    assert score_replay_row("BIG_LOTTO", 2, 1)["tier_class"] == "BIG_CONSOLATION_PRIZE"


def test_power_truth_table_rule():
    # M3 wins; M1+second wins; M1 without second loses; M2 without second loses.
    assert score_replay_row("POWER_LOTTO", 3, 0)["any_prize_aware_win"] is True
    assert score_replay_row("POWER_LOTTO", 1, 1)["any_prize_aware_win"] is True
    assert score_replay_row("POWER_LOTTO", 1, 0)["any_prize_aware_win"] is False
    assert score_replay_row("POWER_LOTTO", 2, 0)["any_prize_aware_win"] is False
    assert score_replay_row("POWER_LOTTO", 1, 1)["tier_class"] == "POWER_CONSOLATION_PRIZE"


def test_daily539_truth_table_rule():
    # M2 wins; M1 loses.
    assert score_replay_row("DAILY_539", 2, 0)["any_prize_aware_win"] is True
    assert score_replay_row("DAILY_539", 1, 0)["any_prize_aware_win"] is False


def test_tool_truth_table_fixtures_match_scorer():
    out = P281.verify_prize_rules_and_truth_tables()
    assert set(out) == {"DAILY_539", "BIG_LOTTO", "POWER_LOTTO"}
    for lt, block in out.items():
        for fx in block["truth_table"]:
            row = score_replay_row(lt, fx["main_hit_count"], fx["special_hit"])
            assert bool(row["any_prize_aware_win"]) == fx["any_prize_aware_win"]
            assert row["tier_class"] == fx["tier_class"]


# --------------------------------------------------------------------------- #
# Task G #4 — tier exclusivity + exhaustiveness                                #
# --------------------------------------------------------------------------- #

def test_tier_exclusivity_and_exhaustiveness():
    out = P281.verify_tier_exclusivity_exhaustiveness()
    assert out["DAILY_539"]["distinct_prize_tiers"] == 4
    assert out["BIG_LOTTO"]["distinct_prize_tiers"] == 8
    assert out["POWER_LOTTO"]["distinct_prize_tiers"] == 10
    for lt in out:
        assert out[lt]["mutually_exclusive"] is True
        assert out[lt]["exhaustive_over_integer_grid"] is True
        # every combination has exactly one win/no-prize classification
        assert out[lt]["distinct_prize_tiers"] == out[lt]["expected_prize_tiers"]


# --------------------------------------------------------------------------- #
# Task G #5 — missing predicted special / second-zone excluded, not backfilled #
# --------------------------------------------------------------------------- #

def _power_row(pred_special, target="1551", cutoff="1550"):
    return {
        "lottery_type": "POWER_LOTTO",
        "target_draw": target, "strategy_id": "s", "bet_index": 0,
        "history_cutoff_draw": cutoff,
        "predicted_numbers": "[1,2,3,4,5,6]",
        "predicted_special": pred_special,
        "actual_numbers": "[1,2,3,7,8,9]",
        "actual_special": 4,
        "_join_count": 1,
    }


def test_missing_second_zone_excluded_never_backfilled():
    eligible, reason = _check_eligibility(_power_row(None))
    assert eligible is False
    assert reason == EXCLUSION_MISSING_PREDICTED_SECOND_ZONE
    # process_cell_rows must leave it ineligible with no scored ticket content
    raw = (
        "POWER_LOTTO", "1551", "s", 0, "1550",
        "[1,2,3,4,5,6]", None, "[1,2,3,7,8,9]", 4, 1,
    )
    processed, draws = P281.process_cell_rows([raw])
    assert processed[0]["eligible"] is False
    assert processed[0]["win"] is False
    assert processed[0]["ticket_key"] is None  # actual second-zone NEVER substituted
    # aggregation counts it as an excluded missing-second-zone row, 0 support
    agg = P281.aggregate_prize_aware_window(processed, draws, 100, "POWER_LOTTO", "s")
    assert agg["support_draws"] == 0
    assert agg["excluded_missing_second_zone_rows"] == 1


# --------------------------------------------------------------------------- #
# Task G #6 — support-status classification + verdict mapping                  #
# --------------------------------------------------------------------------- #

def _win(evaluable, support=1500):
    return {"support_draws": support, "inference": {"evaluable": evaluable}}


def _all_window(scoreable, miss2z=0, support=1500):
    excl = {}
    if miss2z:
        excl[EXCLUSION_MISSING_PREDICTED_SECOND_ZONE] = miss2z
    return {"scoreable_rows": scoreable, "support_draws": support,
            "exclusion_by_reason": excl}


def test_support_classification_enough_and_candidate():
    wbl = {"SHORT": _win(True), "MID": _win(True), "LONG": _win(True)}
    sup = P281.classify_support("DAILY_539", wbl, _all_window(7500))
    assert sup["cell_support_status"] == P281.SUPPORT_ENOUGH
    assert sup["family_windows_evaluable"] == 3
    assert P281.cell_verdict(sup["cell_support_status"], 3,
                             "GO_CANDIDATE_RESEARCH_ONLY") == P281.VERDICT_OBSERVATION_CANDIDATE


def test_support_classification_low_short_underpowered_is_null():
    # SHORT under-powered (not evaluable), MID/LONG evaluable, overall frozen rule
    # returns INSUFFICIENT_SUPPORT but P281A verdict is NULL (testable, no edge).
    wbl = {"SHORT": _win(False, 100), "MID": _win(True), "LONG": _win(True)}
    sup = P281.classify_support("BIG_LOTTO", wbl, _all_window(24000))
    assert sup["cell_support_status"] == P281.SUPPORT_LOW
    assert sup["family_windows_evaluable"] == 2
    assert P281.cell_verdict(sup["cell_support_status"], 2,
                             "INSUFFICIENT_SUPPORT") == P281.VERDICT_NULL


def test_support_classification_no_second_zone_blocked():
    wbl = {"SHORT": _win(False, 0), "MID": _win(False, 0), "LONG": _win(False, 0)}
    sup = P281.classify_support("POWER_LOTTO", wbl,
                                _all_window(0, miss2z=7550, support=0))
    assert sup["cell_support_status"] == P281.SUPPORT_NO_SECOND_ZONE
    assert P281.cell_verdict(sup["cell_support_status"], 0,
                             "INSUFFICIENT_SUPPORT") == P281.VERDICT_BLOCKED_SUPPORT


# --------------------------------------------------------------------------- #
# Task G #7 — analytic random baseline deterministic + correct                 #
# --------------------------------------------------------------------------- #

def test_analytic_baseline_deterministic_and_monotone():
    total, winning = ticket_universe("DAILY_539")
    q1a = exact_distinct_draw_baseline(total, winning, 1)
    q1b = exact_distinct_draw_baseline(total, winning, 1)
    assert q1a == q1b == winning / total          # deterministic, exact for n=1
    q3 = exact_distinct_draw_baseline(total, winning, 3)
    q5 = exact_distinct_draw_baseline(total, winning, 5)
    assert q1a < q3 < q5 < 1.0                     # strictly increasing in budget


# --------------------------------------------------------------------------- #
# Task G #8 — Monte-Carlo deterministic + matches analytic                     #
# --------------------------------------------------------------------------- #

def test_monte_carlo_deterministic_seed():
    total, winning = ticket_universe("DAILY_539")
    a = P281.monte_carlo_draw_baseline(total, winning, 5, 3000, seed=42)
    b = P281.monte_carlo_draw_baseline(total, winning, 5, 3000, seed=42)
    assert a == b                                  # bit-for-bit reproducible
    c = P281.monte_carlo_draw_baseline(total, winning, 5, 3000, seed=7)
    # different seed generally differs (not asserted equal); both near analytic
    analytic = exact_distinct_draw_baseline(total, winning, 5)
    assert abs(a - analytic) < 0.05 and abs(c - analytic) < 0.05


def test_monte_carlo_crosscheck_within_tolerance():
    mc = P281.monte_carlo_crosscheck()
    assert mc["monte_carlo_used_for_inference"] is False
    assert mc["all_within_tolerance"] is True


# --------------------------------------------------------------------------- #
# Task G #9 — p-value / correction behaviour                                   #
# --------------------------------------------------------------------------- #

def test_pvalue_and_correction_behaviour():
    # upper-tail p at observed 0 is 1.0; Bonferroni multiplies by family size.
    assert upper_tail_pvalue(0, [0.3] * 50)[0] == 1.0
    assert bonferroni_pvalue(0.0005, 108) == pytest.approx(0.054)
    assert bonferroni_pvalue(0.9, 108) == 1.0     # clamped at 1.0
    # BH-FDR flags: all-tiny -> all True; all-large -> all False.
    assert all(benjamini_hochberg([1e-9] * 5))
    assert not any(benjamini_hochberg([0.99] * 5))
    assert P281.CORRECTION_FAMILY_M == 36 * 3


# --------------------------------------------------------------------------- #
# Task G #10 — no outcome leakage in the join / scoring loop                   #
# --------------------------------------------------------------------------- #

def test_no_leakage_causality_enforced():
    # history_cutoff_draw must be strictly < target_draw; otherwise excluded.
    leaky = {
        "lottery_type": "DAILY_539", "target_draw": "100", "strategy_id": "s",
        "bet_index": 0, "history_cutoff_draw": "100",  # == target -> leakage
        "predicted_numbers": "[1,2,3,4,5]", "predicted_special": None,
        "actual_numbers": "[1,2,3,4,5]", "actual_special": None, "_join_count": 1,
    }
    eligible, reason = _check_eligibility(leaky)
    assert eligible is False and reason == EXCLUSION_CAUSALITY_FAILURE


def test_ineligible_rows_carry_no_score():
    raw = (  # cutoff >= target -> causality failure -> never scored
        "DAILY_539", "100", "s", 0, "100",
        "[1,2,3,4,5]", None, "[1,2,3,4,5]", None, 1,
    )
    processed, _ = P281.process_cell_rows([raw])
    assert processed[0]["eligible"] is False
    assert processed[0]["tier"] is None and processed[0]["main_hit_count"] is None


# --------------------------------------------------------------------------- #
# Task G #11-#16 — artifact schema, no-claim flags, no publication, db policy  #
# --------------------------------------------------------------------------- #

def test_final_classification_helper():
    null_cells = [{"p281a_verdict": "NULL"}]
    cand_cells = [{"p281a_verdict": "OBSERVATION_CANDIDATE"},
                  {"p281a_verdict": "NULL"}]
    blocked_cells = [{"p281a_verdict": "BLOCKED_SUPPORT"}]
    assert P281._final_classification(null_cells)[1] in _ALLOWED_FINAL
    assert "OBSERVATION_CANDIDATES" in P281._final_classification(cand_cells)[1]
    assert "SUPPORT_BLOCKED" in P281._final_classification(blocked_cells)[1]


def test_tool_source_has_no_publication_or_network_or_db_write():
    src = TOOL_FILE.read_text(encoding="utf-8")
    # no real publication / pre-draw manifest / official lookup capability
    low = src.lower()
    for forbidden in ("import requests", "import urllib", "import httpx",
                      "import socket", "webfetch", "websearch"):
        assert forbidden not in low, f"forbidden capability: {forbidden}"
    # no DB write / copy / migration
    for sql in ("insert into", "update ", "delete from", "drop table",
                "create table", "shutil.copy", "shutil.copyfile"):
        assert sql not in low, f"forbidden DB/write op: {sql}"
    # opens DB read-only via the reused helper only
    assert "open_readonly_connection" in src


def test_db_write_forbidden_when_opened(p281a_db):
    # opening the canonical DB read-only must reject any write attempt.
    conn, evidence = P281.open_readonly_connection(p281a_db)
    try:
        assert evidence["query_only_enabled"] is True
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "CREATE TABLE _p281a_should_not_exist (x INTEGER)")
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# End-to-end (DB-gated): full validation result schema + safety flags          #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def p281a_db():
    db = os.environ.get("P281A_DB")
    if not db or not Path(db).exists():
        pytest.skip("P281A_DB env not set to a readable canonical DB")
    return db


@pytest.fixture(scope="session")
def result(p281a_db):
    return P281.build_result(
        db_path=p281a_db,
        p267c_path=str(REPO_ROOT / P281.P267C_JSON_PATH),
        p271a_path=str(REPO_ROOT / P281.P271A_JSON_PATH),
        scorer_path=str(REPO_ROOT / P281.P271C_SOURCE_PATH),
        adapter_path=str(REPO_ROOT / P281.P271E_SOURCE_PATH),
    )


def test_result_schema_and_final_classification(result):
    assert result["meta"]["task_id"] == P281.TASK_ID
    assert result["final_classification"] in _ALLOWED_FINAL
    assert result["meta"]["frozen_strategy_cell_count"] == 36
    assert result["meta"]["inferential_windows"] == [100, 500, 1500]
    assert "canonical_payload_digest" in result
    # markdown renders and references the classification
    md = P281.render_markdown(result)
    assert "final_classification" in md and result["final_classification"] in md


def test_safety_flags_no_claim_no_promotion_no_activation(result):
    f = result["safety_flags"]
    assert f["prediction_success_claim"] is False
    assert f["strategy_promoted"] is False
    assert f["activation"] is False
    assert f["real_publication"] is False
    assert f["official_target_lookup"] is False
    assert f["official_deadline_lookup"] is False
    assert f["pre_draw_manifest_created"] is False
    assert f["publication_pr_created"] is False
    assert f["db_copied"] is False and f["db_written"] is False
    assert f["scorer_source_changed"] is False
    assert f["registry_mutation"] is False


def test_verdict_counts_consistent_and_candidates_are_daily539(result):
    cells = result["cells"]
    assert len(cells) == 36
    counts = result["verdict_counts"]
    assert (counts["observation_candidate"] + counts["null"]
            + counts["blocked_support"]) == 36
    # any observation candidate must be a research-only, support-sufficient,
    # stability-pass cell beating the corrected baseline (no promotion).
    for c in cells:
        if c["p281a_verdict"] == "OBSERVATION_CANDIDATE":
            assert c["stability"]["status"] == "STABILITY_PASS"
            assert c["overall_group_decision"] == "GO_CANDIDATE_RESEARCH_ONLY"


def test_determinism_same_digest(result, p281a_db):
    again = P281.build_result(
        db_path=p281a_db,
        p267c_path=str(REPO_ROOT / P281.P267C_JSON_PATH),
        p271a_path=str(REPO_ROOT / P281.P271A_JSON_PATH),
        scorer_path=str(REPO_ROOT / P281.P271C_SOURCE_PATH),
        adapter_path=str(REPO_ROOT / P281.P271E_SOURCE_PATH),
    )
    assert again["canonical_payload_digest"] == result["canonical_payload_digest"]


def test_committed_artifact_matches_recompute(result):
    artifact = REPO_ROOT / P281.DEFAULT_OUT_JSON
    if not artifact.exists():
        pytest.skip("artifact not generated in this checkout")
    on_disk = json.loads(artifact.read_text(encoding="utf-8"))
    assert on_disk["canonical_payload_digest"] == result["canonical_payload_digest"]
    assert on_disk["final_classification"] == result["final_classification"]


# --------------------------------------------------------------------------- #
# Semantic ranking-change tests (P281C remediation)                           #
# --------------------------------------------------------------------------- #

def _make_rank_summary(order_prize, order_legacy):
    """Simulate the per_lottery block produced by cross_lottery_summary for one
    lottery, given pre-sorted strategy-id lists. Calls the actual production
    function logic rather than duplicating it, so we test the real field names."""
    # Build minimal cell + long-window stubs that reproduce the ranking lists.
    cells = []
    all_strategies = list(dict.fromkeys(order_prize + order_legacy))
    prize_rank = {s: i for i, s in enumerate(order_prize)}
    legacy_rank = {s: i for i, s in enumerate(order_legacy)}
    for s in all_strategies:
        # obs_rate drives prize-aware rank; legacy_m3plus_rate drives legacy rank.
        # Higher index -> lower rank (farther from 0); we invert to get a rate.
        n = len(all_strategies)
        obs = (n - prize_rank.get(s, n)) / n
        leg = (n - legacy_rank.get(s, n)) / n
        cells.append({
            "lottery_type": "DAILY_539",
            "strategy_id": s,
            "support": {"missing_second_zone_rows": 0},
            "windows": [{
                "window_label": "LONG",
                "observed_success_rate": obs,
                "legacy_m3plus_success_rate": leg,
                "prize_aware_minus_legacy_delta": obs - leg,
            }],
        })
    summary = P281.cross_lottery_summary(cells)
    return summary["per_lottery"]["DAILY_539"]


def test_ranking_top_unchanged_full_order_changed():
    """Same top strategy but lower positions differ:
    top_change must be False; full_order_change must be True."""
    prize_order = ["A", "B", "C"]
    legacy_order = ["A", "C", "B"]   # A is still top, B and C swap
    p = _make_rank_summary(prize_order, legacy_order)
    assert p["ranking_top_strategy_prize_aware"] == "A"
    assert p["ranking_top_strategy_legacy_m3plus"] == "A"
    assert p["ranking_top_changes_prize_vs_legacy"] is False
    assert p["ranking_full_order_changes_prize_vs_legacy"] is True


def test_ranking_top_changed():
    """Different top strategy: both top_change and full_order_change must be True."""
    prize_order = ["B", "A", "C"]
    legacy_order = ["A", "B", "C"]   # A leads in legacy, B leads in prize-aware
    p = _make_rank_summary(prize_order, legacy_order)
    assert p["ranking_top_strategy_prize_aware"] == "B"
    assert p["ranking_top_strategy_legacy_m3plus"] == "A"
    assert p["ranking_top_changes_prize_vs_legacy"] is True
    assert p["ranking_full_order_changes_prize_vs_legacy"] is True


def test_ranking_identical():
    """Identical rankings: both top_change and full_order_change must be False."""
    same_order = ["A", "B", "C"]
    p = _make_rank_summary(same_order, same_order)
    assert p["ranking_top_strategy_prize_aware"] == "A"
    assert p["ranking_top_strategy_legacy_m3plus"] == "A"
    assert p["ranking_top_changes_prize_vs_legacy"] is False
    assert p["ranking_full_order_changes_prize_vs_legacy"] is False


def test_ranking_top_flag_equals_top_strategy_field_comparison(result):
    """Invariant: for every lottery in the artifact, ranking_top_changes_prize_vs_legacy
    must equal (ranking_top_strategy_prize_aware != ranking_top_strategy_legacy_m3plus).
    This test is DB-gated (runs with the full computed result)."""
    for lt, p in result["cross_lottery_summary"]["per_lottery"].items():
        top_p = p["ranking_top_strategy_prize_aware"]
        top_l = p["ranking_top_strategy_legacy_m3plus"]
        if top_p is not None and top_l is not None:
            expected = top_p != top_l
        else:
            expected = False
        assert p["ranking_top_changes_prize_vs_legacy"] == expected, (
            f"{lt}: top_change flag {p['ranking_top_changes_prize_vs_legacy']!r} "
            f"!= ({top_p!r} != {top_l!r}) = {expected!r}"
        )
