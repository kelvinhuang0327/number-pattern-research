"""
test_p53_powerlotto_watchlist_waiver.py

P53 POWER_LOTTO midfreq_fourier_mk_3bet WATCHLIST Waiver Staging Tests

Governance:
- No DB write
- No lifecycle promotion
- No champion replacement
- Production rows must remain 42460
- WATCHLIST staging via docs-only declaration
"""
import json
import math
import sqlite3
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P53_JSON = REPO_ROOT / "outputs" / "replay" / "p53_powerlotto_midfreq_fourier_mk_3bet_watchlist_waiver_20260525.json"
P53_MD = REPO_ROOT / "docs" / "replay" / "p53_powerlotto_midfreq_fourier_mk_3bet_watchlist_waiver_20260525.md"

CANDIDATE = "midfreq_fourier_mk_3bet"
CHAMPION = "fourier_rhythm_3bet"
LOTTERY_TYPE = "POWER_LOTTO"
EXPECTED_ROWS = 1500
PRODUCTION_ROWS = 42460


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def p53_json():
    assert P53_JSON.exists(), f"P53 JSON not found: {P53_JSON}"
    with open(P53_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------
class TestP53Artifacts:
    def test_json_exists(self):
        assert P53_JSON.exists(), f"P53 JSON missing: {P53_JSON}"

    def test_md_exists(self):
        assert P53_MD.exists(), f"P53 MD missing: {P53_MD}"

    def test_json_task_is_p53(self, p53_json):
        assert p53_json["task"] == "P53"

    def test_json_classification(self, p53_json):
        assert p53_json["overall_p53_classification"] == "P53_WATCHLIST_STAGED_WITH_G4_WAIVER"

    def test_md_contains_classification(self):
        content = P53_MD.read_text()
        assert "P53_WATCHLIST_STAGED_WITH_G4_WAIVER" in content

    def test_md_contains_watchlist_declaration(self):
        content = P53_MD.read_text()
        assert "WATCHLIST Declaration" in content or "watchlist_status" in content.lower() or "WATCHLIST" in content


# ---------------------------------------------------------------------------
# 2. Governance constraints
# ---------------------------------------------------------------------------
class TestP53Governance:
    def test_no_db_write(self, p53_json):
        assert p53_json["governance"]["no_db_write"] is True

    def test_no_lifecycle_promotion(self, p53_json):
        assert p53_json["governance"]["no_lifecycle_promotion"] is True

    def test_no_registry_mutation(self, p53_json):
        assert p53_json["governance"]["no_registry_mutation"] is True

    def test_no_online_promotion(self, p53_json):
        assert p53_json["governance"]["no_online_promotion"] is True

    def test_no_champion_replacement(self, p53_json):
        assert p53_json["governance"]["no_champion_replacement"] is True

    def test_production_rows_unchanged(self, p53_json):
        assert p53_json["governance"]["production_rows_before"] == PRODUCTION_ROWS
        assert p53_json["governance"]["production_rows_after"] == PRODUCTION_ROWS

    def test_production_rows_in_db(self, db):
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        total = cur.fetchone()[0]
        assert total == PRODUCTION_ROWS, f"Expected {PRODUCTION_ROWS} rows, got {total}"

    def test_watchlist_staging_method_docs_only(self, p53_json):
        method = p53_json["watchlist_declaration"]["staging_method"]
        assert "docs-only" in method.lower() or "no db write" in method.lower()

    def test_online_promotion_not_authorized(self, p53_json):
        assert p53_json["watchlist_declaration"]["online_promotion_authorized"] is False

    def test_champion_active_not_replaced(self, p53_json):
        decl = p53_json["watchlist_declaration"]
        assert "NOT replaced" in decl["champion_status"]


# ---------------------------------------------------------------------------
# 3. Waiver
# ---------------------------------------------------------------------------
class TestP53Waiver:
    def test_waiver_granted(self, p53_json):
        assert p53_json["waiver"]["waiver_granted"] is True

    def test_waiver_phrase_present(self, p53_json):
        phrase = p53_json["waiver"]["waiver_phrase_received"]
        assert "YES waive G4" in phrase
        assert "WATCHLIST" in phrase
        assert "hit_count>=3" in phrase or "hit_count >= 3" in phrase.replace(">=", " >= ")

    def test_waiver_id_format(self, p53_json):
        wid = p53_json["waiver"]["waiver_id"]
        assert wid.startswith("P53_G4_WAIVER")


# ---------------------------------------------------------------------------
# 4. Strategy row counts
# ---------------------------------------------------------------------------
class TestP53RowCounts:
    def test_candidate_row_count(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND lottery_type=?",
            (CANDIDATE, LOTTERY_TYPE),
        )
        count = cur.fetchone()[0]
        assert count == EXPECTED_ROWS, f"Expected {EXPECTED_ROWS} rows for {CANDIDATE}, got {count}"

    def test_candidate_replay_status(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT DISTINCT replay_status FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND lottery_type=?",
            (CANDIDATE, LOTTERY_TYPE),
        )
        statuses = {row[0] for row in cur.fetchall()}
        # Must NOT be ONLINE — lifecycle not promoted
        assert "ONLINE" not in statuses, f"Candidate was promoted to ONLINE: {statuses}"

    def test_candidate_controlled_apply_id(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT DISTINCT controlled_apply_id FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND lottery_type=?",
            (CANDIDATE, LOTTERY_TYPE),
        )
        apply_ids = {row[0] for row in cur.fetchall()}
        assert "P48_POWERLOTTO_WAVE4_4500_PROD_20260524" in apply_ids


# ---------------------------------------------------------------------------
# 5. G4 restatement: McNemar at hit_count >= 3
# ---------------------------------------------------------------------------
class TestG4Restatement:
    def test_g4_direction_champion_favored(self, p53_json):
        g4 = p53_json["g4_restatement"]
        assert g4["direction"] == "CHAMPION_FAVORED"

    def test_g4_b_c_values(self, p53_json):
        g4 = p53_json["g4_restatement"]
        assert g4["b_candidate_wins"] == 42
        assert g4["c_champion_wins"] == 50

    def test_g4_policy_waiver_required(self, p53_json):
        g4 = p53_json["g4_restatement"]
        assert g4["policy"] == "G4_REQUIRES_WAIVER"
        assert g4["waiver_granted"] is True

    def test_g4_p_value_range(self, p53_json):
        g4 = p53_json["g4_restatement"]
        # p should be close to 0.466 (not significant)
        assert 0.40 < g4["p_value"] < 0.55

    def test_g4_from_db(self, db):
        """Recompute G4 from DB to confirm p53 artifact matches reality."""
        cur = db.cursor()
        cur.execute(
            """
            SELECT
              SUM(CASE WHEN c.hit_count >= 3 AND ch.hit_count < 3 THEN 1 ELSE 0 END) as b,
              SUM(CASE WHEN c.hit_count < 3  AND ch.hit_count >= 3 THEN 1 ELSE 0 END) as c_val
            FROM strategy_prediction_replays c
            JOIN strategy_prediction_replays ch
              ON c.target_draw = ch.target_draw AND c.lottery_type = ch.lottery_type
            WHERE c.lottery_type = 'POWER_LOTTO'
              AND c.strategy_id = 'midfreq_fourier_mk_3bet'
              AND ch.strategy_id = 'fourier_rhythm_3bet'
            """,
        )
        row = cur.fetchone()
        b, c = row[0], row[1]
        assert b == 42, f"G4 b mismatch: expected 42, got {b}"
        assert c == 50, f"G4 c mismatch: expected 50, got {c}"
        assert c > b, "G4 must be champion-favored (c > b)"


# ---------------------------------------------------------------------------
# 6. Supplementary McNemar at hit_count >= 2 (G5a)
# ---------------------------------------------------------------------------
class TestSupplementaryMcNemar:
    def test_g5a_direction_candidate_favored(self, p53_json):
        g5a = p53_json["supplementary_mcnemar_g5a"]
        assert g5a["direction"] == "CANDIDATE_FAVORED"

    def test_g5a_b_greater_than_c(self, p53_json):
        g5a = p53_json["supplementary_mcnemar_g5a"]
        assert g5a["b_candidate_wins"] > g5a["c_champion_wins"]

    def test_g5a_b_c_values(self, p53_json):
        g5a = p53_json["supplementary_mcnemar_g5a"]
        assert g5a["b_candidate_wins"] == 184
        assert g5a["c_champion_wins"] == 157

    def test_g5a_p_value_range(self, p53_json):
        g5a = p53_json["supplementary_mcnemar_g5a"]
        # Should be around 0.159 — not significant but candidate-favored
        assert 0.10 < g5a["p_value"] < 0.25

    def test_g5a_from_db(self, db):
        """Recompute G5a from DB."""
        cur = db.cursor()
        cur.execute(
            """
            SELECT
              SUM(CASE WHEN c.hit_count >= 2 AND ch.hit_count < 2 THEN 1 ELSE 0 END) as b,
              SUM(CASE WHEN c.hit_count < 2  AND ch.hit_count >= 2 THEN 1 ELSE 0 END) as c_val
            FROM strategy_prediction_replays c
            JOIN strategy_prediction_replays ch
              ON c.target_draw = ch.target_draw AND c.lottery_type = ch.lottery_type
            WHERE c.lottery_type = 'POWER_LOTTO'
              AND c.strategy_id = 'midfreq_fourier_mk_3bet'
              AND ch.strategy_id = 'fourier_rhythm_3bet'
            """,
        )
        row = cur.fetchone()
        b, c = row[0], row[1]
        assert b == 184, f"G5a b mismatch: expected 184, got {b}"
        assert c == 157, f"G5a c mismatch: expected 157, got {c}"
        assert b > c, "G5a must be candidate-favored (b > c)"

    def test_g5a_p53_conclusion(self, p53_json):
        g5a = p53_json["supplementary_mcnemar_g5a"]
        assert "DIRECTION_PASS" in g5a["p53_conclusion"] or "not rejected" in g5a["p53_conclusion"].lower()


# ---------------------------------------------------------------------------
# 7. Hit distributions
# ---------------------------------------------------------------------------
class TestHitDistributions:
    def test_candidate_total_rows(self, p53_json):
        dist = p53_json["hit_distributions"]["candidate_midfreq_fourier_mk_3bet"]
        total = sum(dist[f"hit_{i}"]["count"] for i in range(5))
        assert total == EXPECTED_ROWS

    def test_champion_total_rows(self, p53_json):
        dist = p53_json["hit_distributions"]["champion_fourier_rhythm_3bet"]
        total = sum(dist[f"hit_{i}"]["count"] for i in range(5))
        assert total == EXPECTED_ROWS

    def test_candidate_mean_hit(self, p53_json):
        dist = p53_json["hit_distributions"]["candidate_midfreq_fourier_mk_3bet"]
        assert abs(dist["mean_hit"] - 1.027333) < 0.001

    def test_candidate_more_2hit_than_champion(self, p53_json):
        cand = p53_json["hit_distributions"]["candidate_midfreq_fourier_mk_3bet"]
        champ = p53_json["hit_distributions"]["champion_fourier_rhythm_3bet"]
        assert cand["hit_2"]["count"] > champ["hit_2"]["count"]

    def test_champion_more_3hit_than_candidate(self, p53_json):
        cand = p53_json["hit_distributions"]["candidate_midfreq_fourier_mk_3bet"]
        champ = p53_json["hit_distributions"]["champion_fourier_rhythm_3bet"]
        assert champ["hit_3"]["count"] > cand["hit_3"]["count"]


# ---------------------------------------------------------------------------
# 8. Special hit policy
# ---------------------------------------------------------------------------
class TestSpecialHit:
    def test_special_not_folded_into_hit_count(self, p53_json):
        """Confirm special_hit is kept separate from hit_count per POWER_LOTTO semantics."""
        semantic = p53_json["special_hit"]["semantic_note"]
        assert "NOT folded" in semantic or "separate" in semantic.lower()

    def test_candidate_special_hit_rate_in_range(self, p53_json):
        rate = p53_json["special_hit"]["candidate_midfreq_fourier_mk_3bet"]["special_hit_rate"]
        # Should be close to 12.5% theoretical baseline
        assert 0.08 <= rate <= 0.16, f"Special hit rate {rate} outside expected range [0.08, 0.16]"

    def test_candidate_special_hit_from_db(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT SUM(special_hit), COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND lottery_type=?",
            (CANDIDATE, LOTTERY_TYPE),
        )
        row = cur.fetchone()
        special_total, total = row[0], row[1]
        rate = special_total / total
        assert 0.08 <= rate <= 0.16

    def test_comparability_caveat_present(self, p53_json):
        caveat = p53_json["special_hit"]["comparability_caveat"]
        assert len(caveat) > 20


# ---------------------------------------------------------------------------
# 9. WATCHLIST declaration
# ---------------------------------------------------------------------------
class TestWatchlistDeclaration:
    def test_watchlist_status(self, p53_json):
        decl = p53_json["watchlist_declaration"]
        assert decl["watchlist_status"] == "WATCHLIST"

    def test_watchlist_strategy(self, p53_json):
        decl = p53_json["watchlist_declaration"]
        assert decl["strategy_id"] == CANDIDATE

    def test_watchlist_lottery(self, p53_json):
        decl = p53_json["watchlist_declaration"]
        assert decl["lottery_type"] == LOTTERY_TYPE

    def test_champion_not_replaced(self, p53_json):
        decl = p53_json["watchlist_declaration"]
        assert decl["champion_active"] == CHAMPION


# ---------------------------------------------------------------------------
# 10. OOS holdout plan
# ---------------------------------------------------------------------------
class TestOOSHoldoutPlan:
    def test_oos_plan_exists(self, p53_json):
        assert "oos_holdout_plan" in p53_json

    def test_oos_target_draws(self, p53_json):
        plan = p53_json["oos_holdout_plan"]
        assert plan["target_oos_draws"] == 500

    def test_oos_interim_gates(self, p53_json):
        plan = p53_json["oos_holdout_plan"]
        gates = plan["interim_gates"]
        gate_draws = [g["draws"] for g in gates]
        assert 150 in gate_draws
        assert 300 in gate_draws
        assert 500 in gate_draws

    def test_oos_no_fake_rows(self, p53_json):
        plan = p53_json["oos_holdout_plan"]
        assert plan["no_fake_rows"] is True

    def test_oos_promotion_requires_300_plus_draws(self, p53_json):
        plan = p53_json["oos_holdout_plan"]
        triggers = plan["online_promotion_triggers"]
        has_300 = any("300" in str(t) for t in triggers)
        assert has_300, "Promotion should require 300+ additional draws"

    def test_oos_promotion_requires_separate_authorization(self, p53_json):
        plan = p53_json["oos_holdout_plan"]
        triggers = plan["online_promotion_triggers"]
        has_auth = any("authorization" in str(t).lower() or "P54" in str(t) for t in triggers)
        assert has_auth


# ---------------------------------------------------------------------------
# 11. Per-strategy classifications
# ---------------------------------------------------------------------------
class TestPerStrategyClassifications:
    def test_candidate_watchlist(self, p53_json):
        classifications = p53_json["per_strategy_classifications"]
        assert classifications["midfreq_fourier_mk_3bet"] == "WATCHLIST_STAGED_WITH_G4_WAIVER"

    def test_pp3_inconclusive(self, p53_json):
        classifications = p53_json["per_strategy_classifications"]
        assert classifications["pp3_freqort_4bet"] == "INCONCLUSIVE"

    def test_midfreq_fourier_2bet_inconclusive(self, p53_json):
        classifications = p53_json["per_strategy_classifications"]
        assert classifications["midfreq_fourier_2bet"] == "INCONCLUSIVE"


# ---------------------------------------------------------------------------
# 12. Coverage denominator
# ---------------------------------------------------------------------------
class TestCoverageDenominator:
    def test_coverage_denominator(self, p53_json):
        cov = p53_json["coverage_denominator"]
        assert cov["strategy_groups_row_backed"] == "28 / 59"

    def test_gap_to_target(self, p53_json):
        cov = p53_json["coverage_denominator"]
        assert cov["gap_to_target_rows"] == 46500
