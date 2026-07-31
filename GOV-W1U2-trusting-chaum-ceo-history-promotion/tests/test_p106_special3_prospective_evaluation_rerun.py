"""
tests/test_p106_special3_prospective_evaluation_rerun.py
==========================================================
Focused test suite for P106 walk-forward evaluation artifact.

Covers:
 - Artifact existence and structure
 - Classification validity
 - Governance invariants (replay rows, no DB writes, no lookahead)
 - Per-strategy results completeness
 - P100 criteria presence and types
 - Statistical coherence
 - MD report spot-checks
 - Live DB invariants
"""

import json
import math
import pathlib
import sqlite3

import pytest

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT     = pathlib.Path(__file__).parent.parent
DB_PATH  = ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_PATH = ROOT / "outputs" / "replay" / \
            "p106_special3_prospective_evaluation_rerun_20260527.json"
MD_PATH  = ROOT / "docs" / "replay" / \
           "p106_special3_prospective_evaluation_rerun_20260527.md"
SCRIPT_PATH = ROOT / "scripts" / \
              "p106_special3_prospective_evaluation_rerun.py"

EXPECTED_REPLAY_ROWS = 54462
EXPECTED_3STAR_COUNT = 4179
EXPECTED_3STAR_MAX   = 115000106
EXPECTED_4STAR_COUNT = 2922
EXPECTED_4STAR_MAX   = 115000103
EXPECTED_POWER_MAX   = 115000041

VALID_CLASSIFICATIONS = {
    "P106_SPECIAL3_PROSPECTIVE_EVALUATION_PASS",
    "P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL",
    "P106_SPECIAL3_PROSPECTIVE_EVALUATION_FAIL",
    "P106_SPECIAL3_PROSPECTIVE_EVALUATION_INSUFFICIENT_DATA",
}

P99_CANDIDATES = [
    "position_frequency_topk",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
    "ensemble_rank_v1",
]

ENSEMBLE_V2_MEMBERS = [
    "position_frequency_topk",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
]

TOP_NS = [10, 20, 50, 100]

P100_CRITERION_NAMES = {
    "minimum_10_prospective_draws",
    "hit_rate_top20_gt_15pct",
    "p_value_lt_005",
    "ensemble_v2_edge_gt_0_at_top20",
    "no_regime_change",
    "sharpe_ratio_gt_0",
}

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def artifact():
    """Load P106 JSON artifact once for all tests."""
    assert JSON_PATH.exists(), f"P106 JSON artifact missing: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text():
    """Load P106 MD report text."""
    assert MD_PATH.exists(), f"P106 MD report missing: {MD_PATH}"
    return MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def db():
    """Open DB read-only connection."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield conn
    conn.close()


# ── 1. File existence ─────────────────────────────────────────────────────────

def test_json_artifact_exists():
    assert JSON_PATH.exists()


def test_md_report_exists():
    assert MD_PATH.exists()


def test_script_exists():
    assert SCRIPT_PATH.exists()


# ── 2. Classification ─────────────────────────────────────────────────────────

def test_classification_is_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_classification_is_not_insufficient(artifact):
    """63 draws are available; must not be INSUFFICIENT_DATA."""
    assert artifact["classification"] != "P106_SPECIAL3_PROSPECTIVE_EVALUATION_INSUFFICIENT_DATA"


def test_classification_is_partial_or_better(artifact):
    """With 5/6 criteria passed, must be PARTIAL or PASS."""
    assert artifact["classification"] in {
        "P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL",
        "P106_SPECIAL3_PROSPECTIVE_EVALUATION_PASS",
    }


# ── 3. Top-level governance fields ───────────────────────────────────────────

def test_source_unknown_caveat_is_true(artifact):
    assert artifact["source_unknown_caveat"] is True


def test_history_end_draw(artifact):
    assert artifact["history_end_draw"] == "115000024"


def test_db_writes_is_false(artifact):
    assert artifact["db_writes"] is False


def test_no_lookahead_verified_is_true(artifact):
    assert artifact["no_lookahead_verified"] is True


def test_dry_run_only_is_true(artifact):
    assert artifact["dry_run_only"] is True


def test_no_production_promotion(artifact):
    assert artifact["no_production_promotion"] is True


def test_star4_backtest_is_false(artifact):
    assert artifact["star4_backtest"] is False


def test_replay_rows_before(artifact):
    assert artifact["replay_rows_before"] == EXPECTED_REPLAY_ROWS


def test_replay_rows_after(artifact):
    assert artifact["replay_rows_after"] == EXPECTED_REPLAY_ROWS


def test_replay_rows_unchanged(artifact):
    assert artifact["replay_rows_before"] == artifact["replay_rows_after"]


# ── 4. Prospective draws ──────────────────────────────────────────────────────

def test_prospective_draws_evaluated_ge_10(artifact):
    assert artifact["prospective_draws_evaluated"] >= 10


def test_prospective_draws_evaluated_equals_63(artifact):
    """Exactly 63 draws available in the 115000025–115000106 range."""
    assert artifact["prospective_draws_evaluated"] == 63


def test_prospective_draw_range_min(artifact):
    assert artifact["prospective_draw_range"]["min"] == "115000025"


def test_prospective_draw_range_max(artifact):
    assert artifact["prospective_draw_range"]["max"] == "115000106"


def test_per_draw_results_count(artifact):
    assert len(artifact["per_draw_results"]) == artifact["prospective_draws_evaluated"]


# ── 5. P99 candidates present ────────────────────────────────────────────────

def test_all_p99_candidates_in_per_strategy_results(artifact):
    present = set(artifact["per_strategy_results"].keys())
    for c in P99_CANDIDATES:
        assert c in present, f"Missing P99 candidate: {c}"


def test_no_extra_strategies_in_per_strategy_results(artifact):
    expected = set(P99_CANDIDATES)
    actual = set(artifact["per_strategy_results"].keys())
    extras = actual - expected
    assert not extras, f"Unexpected strategies: {extras}"


def test_each_strategy_has_all_top_n_variants(artifact):
    for strat in P99_CANDIDATES:
        for top_n in TOP_NS:
            key = f"top{top_n}"
            assert key in artifact["per_strategy_results"][strat], \
                f"{strat} missing {key}"


# ── 6. Ensemble_v2 ──────────────────────────────────────────────────────────

def test_ensemble_v2_members_correct(artifact):
    assert artifact["ensemble_v2_members"] == ENSEMBLE_V2_MEMBERS


def test_ensemble_v2_results_has_all_top_n(artifact):
    for top_n in TOP_NS:
        key = f"top{top_n}"
        assert key in artifact["ensemble_v2_results"], f"ensemble_v2 missing {key}"


def test_ensemble_v2_top20_positive_edge(artifact):
    t20 = artifact["ensemble_v2_results"]["top20"]
    assert t20["hit_rate"] > t20["p_null"]


def test_ensemble_v2_top20_significant_pvalue(artifact):
    t20 = artifact["ensemble_v2_results"]["top20"]
    assert t20["p_value"] < 0.05


def test_ensemble_v2_positive_sharpe(artifact):
    t20 = artifact["ensemble_v2_results"]["top20"]
    assert t20["sharpe_ratio"] > 0.0


# ── 7. P100 criteria ─────────────────────────────────────────────────────────

def test_p100_all_criteria_present(artifact):
    keys = set(artifact["p100_criteria_evaluation"].keys())
    assert keys == P100_CRITERION_NAMES, \
        f"Criteria mismatch: {keys.symmetric_difference(P100_CRITERION_NAMES)}"


def test_p100_criteria_total_is_6(artifact):
    assert artifact["p100_criteria_total"] == 6


def test_p100_criteria_passed_is_int_in_range(artifact):
    n = artifact["p100_criteria_passed"]
    assert isinstance(n, int) and 0 <= n <= 6


def test_p100_minimum_draws_passed(artifact):
    c = artifact["p100_criteria_evaluation"]["minimum_10_prospective_draws"]
    assert c["passed"] is True


def test_p100_pvalue_criterion_passed(artifact):
    c = artifact["p100_criteria_evaluation"]["p_value_lt_005"]
    assert c["passed"] is True


def test_p100_edge_criterion_passed(artifact):
    c = artifact["p100_criteria_evaluation"]["ensemble_v2_edge_gt_0_at_top20"]
    assert c["passed"] is True


def test_p100_sharpe_criterion_passed(artifact):
    c = artifact["p100_criteria_evaluation"]["sharpe_ratio_gt_0"]
    assert c["passed"] is True


def test_p100_criteria_passed_matches_count(artifact):
    """p100_criteria_passed must equal the number of criteria with passed=True."""
    actual_passed = sum(
        1 for c in artifact["p100_criteria_evaluation"].values() if c["passed"]
    )
    assert artifact["p100_criteria_passed"] == actual_passed


# ── 8. Statistical coherence ─────────────────────────────────────────────────

def test_hit_counts_non_negative(artifact):
    for strat, data in artifact["per_strategy_results"].items():
        for key, vals in data.items():
            assert vals["hit_count"] >= 0, f"{strat} {key} hit_count < 0"


def test_hit_rates_coherent(artifact):
    n = artifact["prospective_draws_evaluated"]
    for strat, data in artifact["per_strategy_results"].items():
        for key, vals in data.items():
            expected_rate = vals["hit_count"] / n
            assert abs(vals["hit_rate"] - expected_rate) < 1e-4, \
                f"{strat} {key} hit_rate mismatch"


def test_p_values_in_0_1(artifact):
    for strat, data in artifact["per_strategy_results"].items():
        for key, vals in data.items():
            assert 0.0 <= vals["p_value"] <= 1.0, \
                f"{strat} {key} p_value={vals['p_value']} out of range"


def test_per_draw_train_size_increases_monotonically(artifact):
    """Training window must never shrink across successive prospective draws."""
    sizes = [d["train_size"] for d in artifact["per_draw_results"]]
    for i in range(1, len(sizes)):
        assert sizes[i] >= sizes[i - 1], \
            f"Training size decreased at index {i}: {sizes[i-1]} → {sizes[i]}"


def test_per_draw_draws_sorted_ascending(artifact):
    draws = [int(d["draw"]) for d in artifact["per_draw_results"]]
    assert draws == sorted(draws), "per_draw_results draws not in ascending order"


# ── 9. Live DB invariants ─────────────────────────────────────────────────────

def test_db_replay_rows(db):
    count = db.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert count == EXPECTED_REPLAY_ROWS


def test_db_3star_count(db):
    count = db.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'"
    ).fetchone()[0]
    assert count == EXPECTED_3STAR_COUNT


def test_db_3star_max_draw(db):
    max_draw = db.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='3_STAR'"
    ).fetchone()[0]
    assert max_draw == EXPECTED_3STAR_MAX


def test_db_4star_count(db):
    count = db.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    assert count == EXPECTED_4STAR_COUNT


def test_db_4star_max_draw(db):
    max_draw = db.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    assert max_draw == EXPECTED_4STAR_MAX


def test_db_power_lotto_max_draw(db):
    max_draw = db.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()[0]
    assert max_draw == EXPECTED_POWER_MAX


# ── 10. MD report spot-checks ────────────────────────────────────────────────

def test_md_contains_classification(md_text):
    assert "P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL" in md_text


def test_md_contains_source_unknown_caveat(md_text):
    assert "SOURCE_UNKNOWN" in md_text


def test_md_contains_63_draws(md_text):
    assert "63" in md_text


def test_md_contains_replay_rows(md_text):
    assert "54,462" in md_text or "54462" in md_text


def test_md_contains_no_db_writes(md_text):
    assert "read-only" in md_text.lower() or "no db writes" in md_text.lower() or \
           "DB writes" in md_text


def test_md_contains_p100_section(md_text):
    assert "P100" in md_text


def test_md_contains_ensemble_v2(md_text):
    assert "ensemble_v2" in md_text or "ensemble_rank_v2" in md_text


def test_md_contains_history_end_draw(md_text):
    assert "115000024" in md_text
