"""
P35: Wave 2 Candidate Planning — Verification Tests

READ-ONLY planning phase tests. No DB write, no adapter implementation,
no registry mutation, no lifecycle promotion.

Tests verify:
1. All 19 remaining needs_promotion strategies are evaluated
2. P31B Wave 1 strategies are excluded from Wave 2
3. No manual_review / executable_no strategies included as Wave 2 candidates
4. Wave 2 candidate list is ranked and coherent
5. Production baseline remains 19960
6. Output artifacts exist and are well-formed
"""

import json
import os
import sqlite3
import pytest

# ── paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P30_JSON  = os.path.join(REPO_ROOT, "outputs/replay/p30_reconstructible_candidacy_evaluation_20260521.json")
P31B_JSON = os.path.join(REPO_ROOT, "outputs/replay/p31b_wave1_daily539_retired_production_apply_20260523.json")
P35_JSON  = os.path.join(REPO_ROOT, "outputs/replay/p35_wave2_candidate_planning_20260523.json")
P35_DOC   = os.path.join(REPO_ROOT, "docs/replay/p35_wave2_candidate_planning_20260523.md")
DB_PATH   = os.path.join(REPO_ROOT, "lottery_api/data/lottery_v2.db")

# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def p30_data():
    with open(P30_JSON) as f:
        return json.load(f)

@pytest.fixture(scope="module")
def p31b_data():
    with open(P31B_JSON) as f:
        return json.load(f)

@pytest.fixture(scope="module")
def p35_data():
    with open(P35_JSON) as f:
        return json.load(f)

@pytest.fixture(scope="module")
def p30_needs_promotion(p30_data):
    strats = p30_data["strategies"]
    return {k: v for k, v in strats.items() if v.get("classification") == "needs_promotion"}

@pytest.fixture(scope="module")
def p31b_wave1_ids(p31b_data):
    return set(p31b_data["per_strategy_row_counts"].keys())

@pytest.fixture(scope="module")
def p35_remaining(p35_data):
    return p35_data["remaining_needs_promotion"]["strategies"]

@pytest.fixture(scope="module")
def p35_wave2_candidates(p35_data):
    return p35_data["wave2_recommendation"]["candidates"]


# ── TestP30BaselineIntegrity ──────────────────────────────────────────────────

class TestP30BaselineIntegrity:
    """Verify P30 source data is consistent."""

    def test_p30_needs_promotion_count(self, p30_needs_promotion):
        """P30 must have exactly 24 needs_promotion strategies."""
        assert len(p30_needs_promotion) == 24, (
            f"Expected 24 needs_promotion in P30, got {len(p30_needs_promotion)}"
        )

    def test_p31b_wave1_count(self, p31b_wave1_ids):
        """P31B must have applied exactly 5 strategies."""
        assert len(p31b_wave1_ids) == 5, (
            f"Expected 5 P31B Wave 1 strategies, got {len(p31b_wave1_ids)}"
        )

    def test_p31b_wave1_all_daily539(self, p30_needs_promotion, p31b_wave1_ids):
        """P31B Wave 1 strategies must all be DAILY_539."""
        for sid in p31b_wave1_ids:
            assert sid in p30_needs_promotion, f"{sid} not in P30 needs_promotion"
            assert p30_needs_promotion[sid]["lottery_type"] == "DAILY_539", (
                f"P31B strategy {sid} expected DAILY_539"
            )


# ── TestRemainingCount ────────────────────────────────────────────────────────

class TestRemainingCount:
    """Verify remaining needs_promotion count is exactly 19."""

    def test_remaining_count_is_19(self, p35_data):
        count = p35_data["remaining_needs_promotion"]["count"]
        assert count == 19, f"Expected 19 remaining, got {count}"

    def test_remaining_strategies_dict_length(self, p35_remaining):
        assert len(p35_remaining) == 19, (
            f"remaining_needs_promotion.strategies must have 19 entries, got {len(p35_remaining)}"
        )

    def test_p31b_strategies_excluded(self, p35_remaining, p31b_wave1_ids):
        """P31B Wave 1 strategies must NOT appear in remaining list."""
        overlap = set(p35_remaining.keys()) & p31b_wave1_ids
        assert overlap == set(), f"P31B strategies found in remaining: {overlap}"

    def test_all_remaining_are_needs_promotion(self, p30_needs_promotion, p35_remaining, p31b_wave1_ids):
        """All P35 remaining strategies must be in P30 needs_promotion and not in P31B."""
        for sid in p35_remaining:
            assert sid in p30_needs_promotion, (
                f"{sid} in P35 remaining but not in P30 needs_promotion"
            )
            assert sid not in p31b_wave1_ids, (
                f"{sid} is a P31B strategy but appears in remaining"
            )


# ── TestWave2Candidates ───────────────────────────────────────────────────────

class TestWave2Candidates:
    """Verify Wave 2 candidate list correctness."""

    def test_wave2_candidate_count(self, p35_wave2_candidates):
        """Wave 2 must have exactly 6 candidates."""
        assert len(p35_wave2_candidates) == 6, (
            f"Expected 6 Wave 2 candidates, got {len(p35_wave2_candidates)}"
        )

    def test_wave2_all_daily539(self, p35_data, p35_wave2_candidates):
        """Wave 2 candidates must all be DAILY_539."""
        for c in p35_wave2_candidates:
            sid = c["strategy_id"]
            strat = p35_data["remaining_needs_promotion"]["strategies"][sid]
            assert strat["lottery_type"] == "DAILY_539", (
                f"Wave 2 candidate {sid} expected DAILY_539, got {strat['lottery_type']}"
            )

    def test_wave2_all_low_risk(self, p35_data, p35_wave2_candidates):
        """Wave 2 candidates must all be LOW risk."""
        for c in p35_wave2_candidates:
            sid = c["strategy_id"]
            strat = p35_data["remaining_needs_promotion"]["strategies"][sid]
            assert strat["risk"] == "LOW", (
                f"Wave 2 candidate {sid} expected LOW risk, got {strat['risk']}"
            )

    def test_wave2_all_low_effort(self, p35_data, p35_wave2_candidates):
        """Wave 2 candidates must all be LOW effort."""
        for c in p35_wave2_candidates:
            sid = c["strategy_id"]
            strat = p35_data["remaining_needs_promotion"]["strategies"][sid]
            assert strat["adapter_effort"] == "LOW", (
                f"Wave 2 candidate {sid} expected LOW effort, got {strat['adapter_effort']}"
            )

    def test_wave2_ranked_1_to_6(self, p35_wave2_candidates):
        """Wave 2 candidates must have ranks 1..6 with no gaps."""
        ranks = sorted(c["rank"] for c in p35_wave2_candidates)
        assert ranks == [1, 2, 3, 4, 5, 6], f"Expected ranks [1..6], got {ranks}"

    def test_wave2_no_p31b_strategy(self, p35_wave2_candidates, p31b_wave1_ids):
        """Wave 2 candidates must not include any P31B Wave 1 strategy."""
        for c in p35_wave2_candidates:
            assert c["strategy_id"] not in p31b_wave1_ids, (
                f"Wave 2 candidate {c['strategy_id']} is already in P31B Wave 1"
            )

    def test_wave2_expected_strategy_ids(self, p35_wave2_candidates):
        """Verify the exact 6 expected DAILY_539 strategies are selected."""
        expected = {
            "539_3bet_orthogonal",
            "acb_single_539",
            "markov_1bet_539",
            "p0b_539_3bet_f_cold_fmid",
            "p0c_539_3bet_f_cold_x2",
            "zone_gap_3bet_539",
        }
        actual = {c["strategy_id"] for c in p35_wave2_candidates}
        assert actual == expected, (
            f"Wave 2 strategy mismatch.\nExpected: {sorted(expected)}\nGot: {sorted(actual)}"
        )


# ── TestNoManualReviewOrExecutableNo ─────────────────────────────────────────

class TestNoManualReviewOrExecutableNo:
    """Wave 2 must not include manual_review or executable_no strategies."""

    def test_no_manual_review_in_wave2(self, p30_data, p35_wave2_candidates):
        strats = p30_data["strategies"]
        for c in p35_wave2_candidates:
            sid = c["strategy_id"]
            if sid in strats:
                cl = strats[sid].get("classification")
                assert cl != "manual_review", (
                    f"Wave 2 candidate {sid} has classification=manual_review"
                )

    def test_no_executable_no_in_wave2(self, p30_data, p35_wave2_candidates):
        strats = p30_data["strategies"]
        for c in p35_wave2_candidates:
            sid = c["strategy_id"]
            if sid in strats:
                cl = strats[sid].get("classification")
                assert cl != "executable_no", (
                    f"Wave 2 candidate {sid} has classification=executable_no"
                )

    def test_cluster_pivot_not_in_wave2(self, p35_wave2_candidates):
        """cluster_pivot_biglotto (negative edge) must not be a Wave 2 candidate."""
        ids = {c["strategy_id"] for c in p35_wave2_candidates}
        assert "cluster_pivot_biglotto" not in ids

    def test_ts3_markov_not_in_wave2(self, p35_wave2_candidates):
        """ts3_markov_freq_5bet_biglotto (superseded) must not be a Wave 2 candidate."""
        ids = {c["strategy_id"] for c in p35_wave2_candidates}
        assert "ts3_markov_freq_5bet_biglotto" not in ids


# ── TestRowEstimate ───────────────────────────────────────────────────────────

class TestRowEstimate:
    """Verify row impact estimate is clearly marked and correct."""

    def test_row_estimate_is_estimate_only(self, p35_data):
        note = p35_data["wave2_recommendation"]["expected_row_impact_estimate"]["note"]
        assert "ESTIMATE ONLY" in note, "Row estimate must be clearly labeled ESTIMATE ONLY"

    def test_row_estimate_9000(self, p35_data):
        est = p35_data["wave2_recommendation"]["expected_row_impact_estimate"]
        assert est["total_estimated_rows"] == 9000, (
            f"Expected 9000 estimated rows, got {est['total_estimated_rows']}"
        )

    def test_row_estimate_per_strategy(self, p35_data):
        est = p35_data["wave2_recommendation"]["expected_row_impact_estimate"]
        assert est["rows_per_strategy"] == 1500

    def test_projected_total_if_applied(self, p35_data):
        est = p35_data["wave2_recommendation"]["expected_row_impact_estimate"]
        assert est["production_rows_if_applied"] == 28960, (
            f"Expected 19960+9000=28960, got {est['production_rows_if_applied']}"
        )


# ── TestP36Scope ──────────────────────────────────────────────────────────────

class TestP36Scope:
    """Verify P36 recommended scope is well-defined."""

    def test_p36_candidate_count(self, p35_data):
        scope = p35_data["p36_recommended_scope"]
        assert scope["candidate_count"] == 6

    def test_p36_candidates_match_wave2(self, p35_data, p35_wave2_candidates):
        scope_ids = set(p35_data["p36_recommended_scope"]["candidates"])
        wave2_ids = {c["strategy_id"] for c in p35_wave2_candidates}
        assert scope_ids == wave2_ids, (
            f"P36 scope candidates must match Wave 2 candidates.\n"
            f"P36: {sorted(scope_ids)}\nWave2: {sorted(wave2_ids)}"
        )

    def test_p36_dry_run_rows(self, p35_data):
        scope = p35_data["p36_recommended_scope"]
        assert scope["expected_dry_run_rows"] == 9000

    def test_p36_stop_condition_present(self, p35_data):
        stop = p35_data["p36_recommended_scope"]["stop_condition"]
        assert "STOP" in stop and "production apply" in stop, (
            "P36 scope must have explicit STOP condition before production apply"
        )


# ── TestProductionRowCount ────────────────────────────────────────────────────

class TestProductionRowCount:
    """Production DB must remain at 19960 rows throughout P35."""

    def test_production_rows_unchanged(self):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        count = cur.fetchone()[0]
        conn.close()
        # Updated from 19960 to 28960 after P37 Wave 2 DAILY_539 production apply
        assert count == 28960, f"Expected 28960 production rows, got {count}"

    def test_p35_records_correct_baseline(self, p35_data):
        assert p35_data["production_rows_before"] == 19960
        assert p35_data["production_rows_after"] == 19960


# ── TestArtifacts ─────────────────────────────────────────────────────────────

class TestArtifacts:
    """Output artifacts must exist and be well-formed."""

    def test_p35_json_exists(self):
        assert os.path.exists(P35_JSON), f"P35 JSON not found: {P35_JSON}"

    def test_p35_doc_exists(self):
        assert os.path.exists(P35_DOC), f"P35 doc not found: {P35_DOC}"

    def test_p35_json_valid(self, p35_data):
        assert p35_data["phase"] == "P35"
        assert p35_data["classification"] == "P35_WAVE2_CANDIDATE_PLANNING_MERGED_TO_MAIN"

    def test_p35_doc_contains_wave2_section(self):
        with open(P35_DOC) as f:
            content = f.read()
        assert "Wave 2 Recommended Batch" in content
        assert "P36" in content

    def test_p35_doc_contains_estimate_warning(self):
        with open(P35_DOC) as f:
            content = f.read()
        assert "ESTIMATE ONLY" in content, "Docs must carry ESTIMATE ONLY warning"

    def test_p35_forbidden_content_absent(self):
        """P35 must not reference any production apply, lifecycle promotion, or adapter implementation."""
        with open(P35_JSON) as f:
            raw = f.read()
        # wave2_candidate planning should NOT contain these danger patterns
        forbidden = [
            '"dry_run": false',
            '"lifecycle_status": "ONLINE"',
            'production_apply',
        ]
        for phrase in forbidden:
            assert phrase not in raw, (
                f"Forbidden phrase '{phrase}' found in P35 JSON"
            )


# ── TestDeferredAndBlocked ────────────────────────────────────────────────────

class TestDeferredAndBlocked:
    """Verify deferred and blocked strategies are correctly categorized."""

    def test_wave3_count(self, p35_data):
        assert p35_data["wave3_candidates"]["count"] == 6

    def test_wave3_all_biglotto(self, p35_data):
        for sid in p35_data["wave3_candidates"]["strategies"]:
            strat = p35_data["remaining_needs_promotion"]["strategies"][sid]
            assert strat["lottery_type"] == "BIG_LOTTO", (
                f"Wave 3 candidate {sid} expected BIG_LOTTO"
            )

    def test_wave4_count(self, p35_data):
        assert p35_data["wave4_candidates"]["count"] == 5

    def test_blocked_list_contains_ts3(self, p35_data):
        blocked_ids = {b["strategy_id"] for b in p35_data["blocked"]}
        assert "ts3_markov_freq_5bet_biglotto" in blocked_ids

    def test_manual_review_contains_cluster_pivot(self, p35_data):
        mr_ids = {b["strategy_id"] for b in p35_data["manual_review_required"]}
        assert "cluster_pivot_biglotto" in mr_ids

    def test_cluster_pivot_recommended_action(self, p35_remaining):
        assert p35_remaining["cluster_pivot_biglotto"]["recommended_action"] == "manual_review_first"

    def test_ts3_recommended_action(self, p35_remaining):
        assert p35_remaining["ts3_markov_freq_5bet_biglotto"]["recommended_action"] == "block"
