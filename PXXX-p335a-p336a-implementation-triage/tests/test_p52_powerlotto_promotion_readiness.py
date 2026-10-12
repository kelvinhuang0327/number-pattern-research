"""
P52 Test Suite: POWER_LOTTO midfreq_fourier_mk_3bet Promotion Readiness

Tests verify that:
1. P51 evidence is correctly loaded and classified
2. G4 McNemar policy is correctly applied (G4_REQUIRES_WAIVER)
3. midfreq_fourier_mk_3bet is classified PROMOTION_WITH_WAIVER_REQUIRED
4. Other strategies remain INCONCLUSIVE
5. Overall P52 classification is P52_PROMOTION_READINESS_WAIVER_REQUIRED
6. No DB write, no lifecycle promotion, no registry mutation occurred
7. Production rows remain 42460
8. P52 JSON artifact has correct structure
9. Decision matrix correctness
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANDIDATE_STRATEGY = "midfreq_fourier_mk_3bet"
BASELINE_STRATEGY = "fourier_rhythm_3bet"
THEORETICAL_BASELINE = 0.9474
CHAMPION_MEAN_HIT = 0.9927
EXPECTED_ROWS = 42460
P51_COMMIT = "0415cc8"

P51_JSON = PROJECT_ROOT / "outputs/replay/p51_powerlotto_wave4_rolling_window_mcnemar_gate_20260525.json"
P52_JSON = PROJECT_ROOT / "outputs/replay/p52_powerlotto_midfreq_fourier_mk_3bet_promotion_readiness_20260525.json"
DB_PATH = PROJECT_ROOT / "lottery_api/data/lottery_v2.db"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p51():
    """Load P51 JSON artifact."""
    assert P51_JSON.exists(), f"P51 JSON not found: {P51_JSON}"
    with open(P51_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p52():
    """Load P52 JSON artifact."""
    assert P52_JSON.exists(), f"P52 JSON not found: {P52_JSON}"
    with open(P52_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def conn():
    """Read-only DB connection."""
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# P51 Evidence Verification
# ---------------------------------------------------------------------------

class TestP51EvidenceReview:
    """Verify P51 evidence is correctly represented."""

    def test_p51_json_exists(self):
        assert P51_JSON.exists()

    def test_p51_task_field(self, p51):
        assert p51["task"] == "P51"

    def test_p51_no_db_write(self, p51):
        assert p51["no_db_write"] is True

    def test_p51_no_lifecycle_promotion(self, p51):
        assert p51["no_lifecycle_promotion"] is True

    def test_p51_no_registry_mutation(self, p51):
        assert p51["no_registry_mutation"] is True

    def test_p51_candidate_classification(self, p51):
        """midfreq_fourier_mk_3bet must be P52_PROMOTION_CANDIDATE in P51."""
        assert p51["strategies"][CANDIDATE_STRATEGY]["classification"] == "P52_PROMOTION_CANDIDATE"

    def test_p51_g1_pass(self, p51):
        gates = p51["strategies"][CANDIDATE_STRATEGY]["gates"]
        assert gates["G1_sample_size"]["pass"] is True
        assert gates["G1_sample_size"]["actual"] == 1500

    def test_p51_g2_pass(self, p51):
        gates = p51["strategies"][CANDIDATE_STRATEGY]["gates"]
        assert gates["G2_three_window_mean_hit"]["pass"] is True
        rw = p51["strategies"][CANDIDATE_STRATEGY]["rolling_windows"]
        assert rw["W150"]["mean_hit"] > THEORETICAL_BASELINE
        assert rw["W500"]["mean_hit"] > THEORETICAL_BASELINE
        assert rw["W1500"]["mean_hit"] > THEORETICAL_BASELINE

    def test_p51_g3_pass(self, p51):
        gates = p51["strategies"][CANDIDATE_STRATEGY]["gates"]
        assert gates["G3_permutation_test"]["pass"] is True
        assert gates["G3_permutation_test"]["p_value"] < 0.001  # highly significant

    def test_p51_g4_fail(self, p51):
        """G4 must fail AND direction must favor champion (b < c)."""
        gates = p51["strategies"][CANDIDATE_STRATEGY]["gates"]
        assert gates["G4_mcnemar_vs_champion"]["pass"] is False
        mc = p51["strategies"][CANDIDATE_STRATEGY]["mcnemar_test"]
        assert mc["b_strategy_wins"] < mc["c_baseline_wins"], (
            f"Expected b < c (champion direction), got b={mc['b_strategy_wins']}, c={mc['c_baseline_wins']}"
        )
        assert mc["p_value"] > 0.05

    def test_p51_g5_pass(self, p51):
        gates = p51["strategies"][CANDIDATE_STRATEGY]["gates"]
        assert gates["G5_special_hit_ci"]["pass"] is True

    def test_p51_g6_pass(self, p51):
        gates = p51["strategies"][CANDIDATE_STRATEGY]["gates"]
        assert gates["G6_rolling_stability"]["pass"] is True
        assert gates["G6_rolling_stability"]["W150_delta"] > 0
        assert gates["G6_rolling_stability"]["W500_delta"] > 0
        assert gates["G6_rolling_stability"]["W1500_delta"] > 0

    def test_p51_g7_pass(self, p51):
        gates = p51["strategies"][CANDIDATE_STRATEGY]["gates"]
        assert gates["G7_governance"]["pass"] is True

    def test_p51_special_hit_not_in_hit_count(self, p51):
        """special_hit and hit_count are separate (semantic check)."""
        strategy = p51["strategies"][CANDIDATE_STRATEGY]
        # mean_hit is first-zone only; special_hit_count is separate
        assert "mean_hit_overall" in strategy
        assert "special_hit_count" in strategy
        assert "special_hit_rate" in strategy
        # special_hit_rate != 0 confirms they are tracked separately
        assert strategy["special_hit_rate"] > 0

    def test_p51_overall_classification(self, p51):
        assert p51["overall_classification"] == "P51_POWERLOTTO_PROMOTION_GATE_COMPLETED"

    def test_p51_has_p52_candidates(self, p51):
        assert p51["has_p52_candidates"] is True


# ---------------------------------------------------------------------------
# G4 McNemar Policy Tests
# ---------------------------------------------------------------------------

class TestG4McNemarPolicy:
    """Verify G4 policy decision is correctly applied."""

    def test_p52_g4_policy_is_requires_waiver(self, p52):
        """P52 must select G4_REQUIRES_WAIVER given b < c."""
        assert p52["g4_mcnemar_policy"]["policy"] == "G4_REQUIRES_WAIVER"

    def test_g4_direction_favors_champion(self, p52):
        g4 = p52["g4_mcnemar_policy"]
        assert g4["direction_favors"] == "CHAMPION"
        assert g4["c_champion_wins"] > g4["b_strategy_wins"]

    def test_g4_policy_not_not_blocking(self, p52):
        """G4_NOT_BLOCKING_FOR_RARE_EVENT must NOT be chosen given b < c."""
        assert p52["g4_mcnemar_policy"]["policy"] != "G4_NOT_BLOCKING_FOR_RARE_EVENT"

    def test_g4_policy_not_hard_blocks(self, p52):
        """G4_BLOCKS_PROMOTION is too strict given strong G3 evidence."""
        assert p52["g4_mcnemar_policy"]["policy"] != "G4_BLOCKS_PROMOTION"

    def test_g4_rationale_present(self, p52):
        assert len(p52["g4_mcnemar_policy"]["rationale"]) > 50

    def test_g4_discordant_counts_correct(self, p52, p51):
        """b and c must match P51 values."""
        g4 = p52["g4_mcnemar_policy"]
        mc = p51["strategies"][CANDIDATE_STRATEGY]["mcnemar_test"]
        assert g4["b_strategy_wins"] == mc["b_strategy_wins"]
        assert g4["c_champion_wins"] == mc["c_baseline_wins"]


# ---------------------------------------------------------------------------
# Decision Matrix Tests
# ---------------------------------------------------------------------------

class TestDecisionMatrix:
    """Verify decision matrix fields and correctness."""

    def test_matrix_strategy_name(self, p52):
        assert p52["candidate_decision"]["decision_matrix"]["strategy"] == CANDIDATE_STRATEGY

    def test_matrix_mean_hit(self, p52, p51):
        """Decision matrix mean_hit must match P51."""
        matrix = p52["candidate_decision"]["decision_matrix"]
        p51_mean = p51["strategies"][CANDIDATE_STRATEGY]["mean_hit_overall"]
        assert abs(matrix["mean_hit_overall"] - p51_mean) < 0.0001

    def test_matrix_candidate_leads_champion(self, p52):
        matrix = p52["candidate_decision"]["decision_matrix"]
        assert matrix["mean_hit_vs_champion_delta"] > 0

    def test_matrix_rolling_stability(self, p52):
        rw = p52["candidate_decision"]["decision_matrix"]["rolling_windows"]
        assert rw["all_above_theoretical_baseline"] is True
        assert rw["monotonic_improvement"] is True

    def test_matrix_effect_size_present(self, p52):
        matrix = p52["candidate_decision"]["decision_matrix"]
        assert "effect_sizes" in matrix
        assert "vs_theoretical_baseline" in matrix["effect_sizes"]
        assert "vs_champion" in matrix["effect_sizes"]

    def test_matrix_online_promotion_not_justified(self, p52):
        matrix = p52["candidate_decision"]["decision_matrix"]
        assert matrix["online_promotion_justified_now"] is False

    def test_matrix_p53_recommendation_present(self, p52):
        matrix = p52["candidate_decision"]["decision_matrix"]
        assert "p53_recommendation" in matrix
        assert len(matrix["p53_recommendation"]) > 20

    def test_matrix_high_variance_caveat(self, p52):
        matrix = p52["candidate_decision"]["decision_matrix"]
        assert "high_variance_caveat" in matrix

    def test_matrix_watchlist_recommendation(self, p52):
        matrix = p52["candidate_decision"]["decision_matrix"]
        assert "watchlist_recommendation" in matrix


# ---------------------------------------------------------------------------
# Strategy Classification Tests
# ---------------------------------------------------------------------------

class TestStrategyClassification:
    """Verify per-strategy P52 classifications."""

    def test_candidate_classification(self, p52):
        assert (
            p52["candidate_decision"]["p52_classification"]
            == "PROMOTION_WITH_WAIVER_REQUIRED"
        )

    def test_pp3_freqort_classification(self, p52):
        assert p52["other_strategies"]["pp3_freqort_4bet"]["p52_classification"] == "INCONCLUSIVE"

    def test_midfreq_fourier_2bet_classification(self, p52):
        assert p52["other_strategies"]["midfreq_fourier_2bet"]["p52_classification"] == "INCONCLUSIVE"

    def test_overall_p52_classification(self, p52):
        assert p52["overall_p52_classification"] == "P52_PROMOTION_READINESS_WAIVER_REQUIRED"

    def test_candidate_p51_classification_preserved(self, p52):
        assert p52["candidate_decision"]["p51_classification"] == "P52_PROMOTION_CANDIDATE"


# ---------------------------------------------------------------------------
# Governance / Safety Tests
# ---------------------------------------------------------------------------

class TestGovernance:
    """Verify P52 governance constraints."""

    def test_p52_no_db_write(self, p52):
        assert p52["no_db_write"] is True

    def test_p52_no_lifecycle_promotion(self, p52):
        assert p52["no_lifecycle_promotion"] is True

    def test_p52_no_registry_mutation(self, p52):
        assert p52["no_registry_mutation"] is True

    def test_p52_production_rows_field(self, p52):
        assert p52["production_rows"] == EXPECTED_ROWS

    def test_p52_task_field(self, p52):
        assert p52["task"] == "P52"

    def test_p52_json_exists(self):
        assert P52_JSON.exists()

    def test_p52_p51_commit_reference(self, p52):
        assert p52["p51_commit"] == P51_COMMIT

    def test_p52_governance_note_present(self, p52):
        assert "P53 requires separate explicit authorization" in p52["p52_governance_note"]

    def test_production_rows_unchanged(self, conn):
        cur = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;")
        actual = cur.fetchone()[0]
        assert actual == EXPECTED_ROWS, f"Production rows changed: expected {EXPECTED_ROWS}, got {actual}"

    def test_no_strategy_promoted_to_online(self, conn):
        """No Wave 4 strategy must be in ONLINE status."""
        cur = conn.execute(
            """
            SELECT strategy_id, replay_status
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'pp3_freqort_4bet',
                'midfreq_fourier_mk_3bet',
                'midfreq_fourier_2bet'
            )
            AND replay_status = 'ONLINE'
            LIMIT 5
            """,
        )
        online_rows = cur.fetchall()
        assert len(online_rows) == 0, (
            f"Found unexpected ONLINE rows for Wave 4 strategies: {online_rows}"
        )

    def test_wave4_strategies_not_online(self, conn):
        """No Wave 4 strategy row must be in ONLINE status (key governance check).
        Rows may be DRY_RUN or PREDICTED from the P48 apply — neither is ONLINE.
        """
        cur = conn.execute(
            """
            SELECT strategy_id, replay_status, COUNT(*) as cnt
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'pp3_freqort_4bet',
                'midfreq_fourier_mk_3bet',
                'midfreq_fourier_2bet'
            )
            GROUP BY strategy_id, replay_status
            """,
        )
        rows = cur.fetchall()
        for sid, status, cnt in rows:
            assert status != "ONLINE", (
                f"Strategy {sid} illegally promoted to ONLINE ({cnt} rows)"
            )
