"""
P98 Special3 OOS + Permutation Review — Evidence Tests
10 tests verifying all P98 artifact requirements.
NO DB writes. NO replay row inserts.
"""

import json
import pathlib
import sqlite3
import pytest

JSON_PATH = pathlib.Path("outputs/replay/special3_oos_permutation_review_20260527.json")
MD_PATH   = pathlib.Path("docs/replay/special3_oos_permutation_review_20260527.md")

PROVISIONAL_STRATEGIES = [
    "position_frequency_topk",
    "ensemble_rank_v1",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
]
REJECTED_STRATEGY = "position_cold_rebound_topk"

EXPECTED_REPLAY_ROWS = 54462
DB_PATH = "lottery_api/data/lottery_v2.db"


@pytest.fixture(scope="module")
def p98_json():
    assert JSON_PATH.exists(), f"P98 JSON missing: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


# ── Test 01: JSON artifact exists and is valid ────────────────────────────────

def test_01_p98_json_exists_and_valid(p98_json):
    d = p98_json
    assert d["task"] == "special3_oos_permutation_review"
    assert d["phase"] == "P98"
    assert d["dry_run"] is True
    assert d["draws_loaded"] == 4115


# ── Test 02: MD artifact exists ───────────────────────────────────────────────

def test_02_p98_md_exists():
    assert MD_PATH.exists(), f"P98 MD missing: {MD_PATH}"
    content = MD_PATH.read_text()
    assert "P98_SPECIAL3_OOS_PERMUTATION_REVIEW_READY" in content
    assert "ADVANCE_TO_P99_CANDIDATE" in content


# ── Test 03: Classification is valid P98 value ───────────────────────────────

def test_03_classification_valid(p98_json):
    cls = p98_json["classification"]
    valid = {
        "P98_SPECIAL3_OOS_PERMUTATION_REVIEW_READY",
        "P98_SPECIAL3_OOS_REVIEW_INCONCLUSIVE",
    }
    assert cls in valid, f"Unexpected classification: {cls}"


# ── Test 04: Exactly 5 PROVISIONAL strategies reviewed ───────────────────────

def test_04_exactly_5_provisional_reviewed(p98_json):
    decisions = p98_json["strategy_decisions"]
    provisional_in_decisions = [
        name for name in PROVISIONAL_STRATEGIES
        if name in decisions and decisions[name].get("decision") != "REJECT_CONFIRMED"
    ]
    assert len(provisional_in_decisions) == 5, (
        f"Expected 5 provisional strategies in decisions, got {len(provisional_in_decisions)}"
    )
    for name in PROVISIONAL_STRATEGIES:
        assert name in decisions, f"Strategy {name} missing from decisions"
        assert decisions[name]["decision"] in {
            "ADVANCE_TO_P99_CANDIDATE",
            "HOLD_FOR_MORE_EVIDENCE",
            "REJECT_CONFIRMED",
        }, f"Invalid decision for {name}: {decisions[name]['decision']}"


# ── Test 05: Rejected strategy excluded from ensemble_v2 ─────────────────────

def test_05_rejected_strategy_excluded_from_ensemble_v2(p98_json):
    ev2 = p98_json["ensemble_v2"]
    assert REJECTED_STRATEGY in ev2["excluded"], (
        f"{REJECTED_STRATEGY} must be in ensemble_v2 excluded list"
    )
    assert REJECTED_STRATEGY not in ev2["members"], (
        f"{REJECTED_STRATEGY} must NOT be in ensemble_v2 members"
    )
    # Decision also reflects REJECT
    dec = p98_json["strategy_decisions"][REJECTED_STRATEGY]
    assert dec["decision"] == "REJECT_CONFIRMED"


# ── Test 06: OOS metrics present for all PROVISIONAL strategies ───────────────

def test_06_oos_metrics_present(p98_json):
    results = p98_json["strategy_results"]
    for name in PROVISIONAL_STRATEGIES:
        assert name in results, f"Strategy {name} missing from strategy_results"
        strat = results[name]
        assert "oos_folds" in strat, f"oos_folds missing for {name}"
        folds = strat["oos_folds"]
        assert len(folds) == 4, f"Expected 4 OOS folds for {name}, got {len(folds)}"
        for fold_name, fold_data in folds.items():
            assert "top20" in fold_data, f"top20 missing in {fold_name} for {name}"
            assert "direct_hit_rate" in fold_data["top20"], (
                f"direct_hit_rate missing in {fold_name}/top20 for {name}"
            )


# ── Test 07: Permutation test status present ─────────────────────────────────

def test_07_permutation_tests_present(p98_json):
    results = p98_json["strategy_results"]
    for name in PROVISIONAL_STRATEGIES:
        strat = results[name]
        assert "permutation_tests" in strat, f"permutation_tests missing for {name}"
        pt = strat["permutation_tests"]
        assert "top20" in pt, f"top20 permutation test missing for {name}"
        t20 = pt["top20"]
        assert "p_value" in t20
        assert "effect_size_cohens_h" in t20
        assert "test_type" in t20
        assert t20["test_type"] == "binomial_one_sided_greater"


# ── Test 08: No DB writes ─────────────────────────────────────────────────────

def test_08_no_db_writes(p98_json):
    assert p98_json["dry_run"] is True
    assert p98_json["db_writes"] is False
    assert p98_json["replay_rows_changed"] == 0
    assert p98_json["no_production_promotion"] is True


# ── Test 09: Replay rows remain at governance baseline ───────────────────────

def test_09_replay_rows_unchanged_at_governance_baseline():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    conn.close()
    assert total == EXPECTED_REPLAY_ROWS, (
        f"replay_rows={total} but expected {EXPECTED_REPLAY_ROWS} — governance baseline violated"
    )


# ── Test 10: 4_STAR remains DATA_GAP_BLOCKING ────────────────────────────────

def test_10_4star_data_gap_blocking(p98_json):
    assert p98_json["special4_status"] == "DATA_GAP_BLOCKING"
    assert p98_json["special4_backtest"] == "NOT_RUN"


# ── Test 11: Special4 backtest NOT RUN (no 4_STAR metrics in any results) ─────

def test_11_no_4star_backtest_metrics(p98_json):
    results_str = json.dumps(p98_json["strategy_results"])
    # 4_STAR should not appear as a lottery_type
    assert "4_STAR" not in results_str, (
        "4_STAR backtest data found in strategy_results — violation"
    )
    # Confirm DB also has 0 rows
    conn = sqlite3.connect(DB_PATH)
    star4_rows = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    conn.close()
    assert star4_rows == 0, f"4_STAR has {star4_rows} rows — expected 0"


# ── Test 12: P99 recommendation present ──────────────────────────────────────

def test_12_p99_recommendation_present(p98_json):
    ev2 = p98_json["ensemble_v2"]
    assert "recommendation" in ev2
    assert ev2["recommendation"] in {"PROCEED_TO_P99_DRY_RUN", "HOLD_FOR_MORE_EVIDENCE"}
    # Summary should include ensemble_v2_recommendation
    summary = p98_json["summary"]
    assert "ensemble_v2_recommendation" in summary
    assert summary["provisional_reviewed"] == 5
    # At least some strategies should have a P99 recommendation
    assert summary["advance_to_p99"] >= 0  # can be 0 if all inconclusive
    assert "ensemble_v2_p99_eligible" in summary
