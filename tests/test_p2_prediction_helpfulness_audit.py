"""
test_p2_prediction_helpfulness_audit.py

P2 Prediction-Helpfulness Audit Tests

Governance:
- No DB write
- No lifecycle promotion
- No champion replacement
- Production rows must remain 46960
- This audit is read-only
"""
import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P2_JSON = REPO_ROOT / "outputs" / "replay" / "p2_prediction_helpfulness_audit_20260526.json"
P2_MD = REPO_ROOT / "docs" / "replay" / "p2_prediction_helpfulness_audit_20260526.md"
PRODUCTION_ROWS = 46960


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def p2_json():
    assert P2_JSON.exists(), f"P2 JSON not found: {P2_JSON}"
    with open(P2_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Artifact existence
# ---------------------------------------------------------------------------
class TestP2Artifacts:
    def test_json_exists(self):
        assert P2_JSON.exists()

    def test_md_exists(self):
        assert P2_MD.exists()

    def test_json_task_is_p2(self, p2_json):
        assert p2_json["task"] == "P2"

    def test_json_classification(self, p2_json):
        assert p2_json["final_classification"] == "P2_PREDICTION_HELPFULNESS_AUDIT_COMPLETE"

    def test_project_context_lock(self, p2_json):
        assert p2_json["project_context_lock"] == "LotteryNew"


# ---------------------------------------------------------------------------
# 2. Governance
# ---------------------------------------------------------------------------
class TestP2Governance:
    def test_no_db_write(self, p2_json):
        assert p2_json["governance"]["no_db_write"] is True

    def test_no_lifecycle_promotion(self, p2_json):
        assert p2_json["governance"]["no_lifecycle_promotion"] is True

    def test_no_online_promotion(self, p2_json):
        assert p2_json["governance"]["no_online_promotion"] is True

    def test_no_champion_replacement(self, p2_json):
        assert p2_json["governance"]["no_champion_replacement"] is True

    def test_no_registry_mutation(self, p2_json):
        assert p2_json["governance"]["no_registry_mutation"] is True

    def test_no_production_row_apply(self, p2_json):
        assert p2_json["governance"]["no_production_row_apply"] is True

    def test_production_rows_before_unchanged(self, p2_json):
        assert p2_json["governance"]["production_rows_before"] == PRODUCTION_ROWS

    def test_production_rows_after_unchanged(self, p2_json):
        assert p2_json["governance"]["production_rows_after"] == PRODUCTION_ROWS


# ---------------------------------------------------------------------------
# 3. Production rows in DB unchanged
# ---------------------------------------------------------------------------
class TestP2ProductionRows:
    def test_production_rows_in_db(self, db):
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert cur.fetchone()[0] == PRODUCTION_ROWS

    def test_p58_apply_rows_in_db(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id='P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525'"
        )
        assert cur.fetchone()[0] == 1500

    def test_p66_cold_complement_rows_in_db(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id='P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525'"
        )
        assert cur.fetchone()[0] == 1500

    def test_p66_zonal_entropy_rows_in_db(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id='P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525'"
        )
        assert cur.fetchone()[0] == 1500


# ---------------------------------------------------------------------------
# 4. Theoretical baselines present and correct
# ---------------------------------------------------------------------------
class TestTheoreticalBaselines:
    def test_power_lotto_mean_baseline(self, p2_json):
        bl = p2_json["theoretical_baselines"]["POWER_LOTTO"]
        assert abs(bl["mean_hit_theoretical"] - 0.9474) < 0.001

    def test_power_lotto_m3_baseline(self, p2_json):
        bl = p2_json["theoretical_baselines"]["POWER_LOTTO"]
        assert abs(bl["m3_plus_theoretical"] - 0.0387) < 0.001

    def test_big_lotto_mean_baseline(self, p2_json):
        bl = p2_json["theoretical_baselines"]["BIG_LOTTO"]
        assert abs(bl["mean_hit_theoretical"] - 0.7347) < 0.001

    def test_big_lotto_m3_baseline(self, p2_json):
        bl = p2_json["theoretical_baselines"]["BIG_LOTTO"]
        assert abs(bl["m3_plus_theoretical"] - 0.0186) < 0.001

    def test_daily_539_mean_baseline(self, p2_json):
        bl = p2_json["theoretical_baselines"]["DAILY_539"]
        assert abs(bl["mean_hit_theoretical"] - 0.6410) < 0.001

    def test_daily_539_m3_baseline(self, p2_json):
        bl = p2_json["theoretical_baselines"]["DAILY_539"]
        assert abs(bl["m3_plus_theoretical"] - 0.0100) < 0.001


# ---------------------------------------------------------------------------
# 5. Strategy count and coverage
# ---------------------------------------------------------------------------
class TestStrategyCoverage:
    def test_total_strategies_audited(self, p2_json):
        assert p2_json["summary"]["total_strategies_audited"] == 31

    def test_power_lotto_strategies_count(self, p2_json):
        assert len(p2_json["strategies"]["POWER_LOTTO"]) == 9

    def test_big_lotto_strategies_count(self, p2_json):
        assert len(p2_json["strategies"]["BIG_LOTTO"]) == 9

    def test_daily_539_strategies_count(self, p2_json):
        assert len(p2_json["strategies"]["DAILY_539"]) == 13

    def test_total_production_rows(self, p2_json):
        assert p2_json["summary"]["total_production_rows"] == PRODUCTION_ROWS


# ---------------------------------------------------------------------------
# 6. Label counts and totals
# ---------------------------------------------------------------------------
class TestLabelCounts:
    def test_prediction_helpful_count(self, p2_json):
        counts = p2_json["summary"]["label_counts"]
        assert counts["prediction-helpful"] == 10

    def test_sub_baseline_count(self, p2_json):
        counts = p2_json["summary"]["label_counts"]
        assert counts["sub-baseline"] == 9

    def test_baseline_equivalent_count(self, p2_json):
        counts = p2_json["summary"]["label_counts"]
        assert counts["baseline-equivalent"] == 5

    def test_fallback_equivalent_count(self, p2_json):
        counts = p2_json["summary"]["label_counts"]
        assert counts["fallback-equivalent"] == 1

    def test_insufficient_evidence_count(self, p2_json):
        counts = p2_json["summary"]["label_counts"]
        assert counts["insufficient-evidence"] == 6

    def test_label_counts_sum_to_31(self, p2_json):
        counts = p2_json["summary"]["label_counts"]
        total = sum(counts.values())
        assert total == 31

    def test_recommendation_counts_sum_to_31(self, p2_json):
        counts = p2_json["summary"]["recommendation_counts"]
        total = sum(counts.values())
        assert total == 31


# ---------------------------------------------------------------------------
# 7. Key POWER_LOTTO strategy classifications
# ---------------------------------------------------------------------------
class TestPowerLottoClassifications:
    def _get_strategy(self, p2_json, strategy_id):
        for s in p2_json["strategies"]["POWER_LOTTO"]:
            if s["strategy_id"] == strategy_id:
                return s
        raise KeyError(f"Strategy {strategy_id} not found in POWER_LOTTO")

    def test_champion_prediction_helpful(self, p2_json):
        s = self._get_strategy(p2_json, "fourier_rhythm_3bet")
        assert s["prediction_helpfulness_label"] == "prediction-helpful"
        assert s["recommendation_class"] == "prioritize-for-expansion"

    def test_wave5_prediction_helpful(self, p2_json):
        s = self._get_strategy(p2_json, "fourier30_markov30_2bet")
        assert s["prediction_helpfulness_label"] == "prediction-helpful"
        assert s["recommendation_class"] == "prioritize-for-expansion"

    def test_watchlist_defer_expansion(self, p2_json):
        s = self._get_strategy(p2_json, "midfreq_fourier_mk_3bet")
        assert s["prediction_helpfulness_label"] == "prediction-helpful"
        assert s["recommendation_class"] == "defer-expansion"

    def test_cold_complement_sub_baseline(self, p2_json):
        s = self._get_strategy(p2_json, "cold_complement_2bet")
        assert s["prediction_helpfulness_label"] == "sub-baseline"
        assert s["recommendation_class"] == "block-expansion"
        assert s["m3_plus_vs_baseline"] < 0

    def test_zonal_entropy_fallback_equivalent(self, p2_json):
        s = self._get_strategy(p2_json, "zonal_entropy_2bet")
        assert s["prediction_helpfulness_label"] == "fallback-equivalent"
        assert s["recommendation_class"] == "block-expansion"

    def test_pp3_insufficient_evidence(self, p2_json):
        s = self._get_strategy(p2_json, "pp3_freqort_4bet")
        assert s["prediction_helpfulness_label"] == "insufficient-evidence"
        assert s["recommendation_class"] == "requires-more-evidence"

    def test_midfreq_fourier_2bet_pl_insufficient(self, p2_json):
        s = self._get_strategy(p2_json, "midfreq_fourier_2bet")
        assert s["prediction_helpfulness_label"] == "insufficient-evidence"

    def test_power_orthogonal_insufficient(self, p2_json):
        s = self._get_strategy(p2_json, "power_orthogonal_5bet")
        assert s["prediction_helpfulness_label"] == "insufficient-evidence"
        assert s["recommendation_class"] == "requires-more-evidence"


# ---------------------------------------------------------------------------
# 8. BIG_LOTTO classifications
# ---------------------------------------------------------------------------
class TestBigLottoClassifications:
    def _get_strategy(self, p2_json, strategy_id):
        for s in p2_json["strategies"]["BIG_LOTTO"]:
            if s["strategy_id"] == strategy_id:
                return s
        raise KeyError(f"Strategy {strategy_id} not found in BIG_LOTTO")

    def test_ts3_regime_baseline_equivalent(self, p2_json):
        s = self._get_strategy(p2_json, "ts3_regime_3bet")
        assert s["prediction_helpfulness_label"] == "baseline-equivalent"
        assert s["recommendation_class"] == "keep-row-backed-only"

    def test_fourier30_markov30_biglotto_sub_baseline(self, p2_json):
        s = self._get_strategy(p2_json, "fourier30_markov30_biglotto")
        assert s["prediction_helpfulness_label"] == "sub-baseline"
        assert s["recommendation_class"] == "block-expansion"
        assert s["m3_plus_vs_baseline"] < 0

    def test_cold_complement_biglotto_sub_baseline(self, p2_json):
        s = self._get_strategy(p2_json, "cold_complement_biglotto")
        assert s["prediction_helpfulness_label"] == "sub-baseline"
        assert s["m3_plus_vs_baseline"] < 0

    def test_biglotto_deviation_keep_row_backed(self, p2_json):
        # Prediction-helpful metrics but game exhausted → keep-row-backed-only
        s = self._get_strategy(p2_json, "biglotto_deviation_2bet")
        assert s["prediction_helpfulness_label"] == "prediction-helpful"
        assert s["recommendation_class"] == "keep-row-backed-only"

    def test_no_big_lotto_prioritize_for_expansion(self, p2_json):
        # L90/L91: no BIG_LOTTO strategy should be marked prioritize-for-expansion
        for s in p2_json["strategies"]["BIG_LOTTO"]:
            assert s["recommendation_class"] != "prioritize-for-expansion", (
                f"{s['strategy_id']} incorrectly marked for expansion despite L90/L91 exhaustion"
            )


# ---------------------------------------------------------------------------
# 9. DAILY_539 classifications
# ---------------------------------------------------------------------------
class TestDaily539Classifications:
    def _get_strategy(self, p2_json, strategy_id):
        for s in p2_json["strategies"]["DAILY_539"]:
            if s["strategy_id"] == strategy_id:
                return s
        raise KeyError(f"Strategy {strategy_id} not found in DAILY_539")

    def test_acb_markov_midfreq_3bet_prediction_helpful(self, p2_json):
        s = self._get_strategy(p2_json, "acb_markov_midfreq_3bet")
        assert s["prediction_helpfulness_label"] == "prediction-helpful"
        assert s["recommendation_class"] == "prioritize-for-expansion"

    def test_midfreq_acb_2bet_prediction_helpful(self, p2_json):
        s = self._get_strategy(p2_json, "midfreq_acb_2bet")
        assert s["prediction_helpfulness_label"] == "prediction-helpful"
        assert s["recommendation_class"] == "prioritize-for-expansion"

    def test_acb_1bet_prediction_helpful(self, p2_json):
        s = self._get_strategy(p2_json, "acb_1bet")
        assert s["prediction_helpfulness_label"] == "prediction-helpful"
        assert s["recommendation_class"] == "prioritize-for-expansion"

    def test_zone_gap_sub_baseline(self, p2_json):
        s = self._get_strategy(p2_json, "zone_gap_3bet_539")
        assert s["prediction_helpfulness_label"] == "sub-baseline"
        assert s["recommendation_class"] == "block-expansion"
        assert s["m3_plus_vs_baseline"] < 0

    def test_daily539_f4cold_insufficient_evidence(self, p2_json):
        s = self._get_strategy(p2_json, "daily539_f4cold")
        assert s["prediction_helpfulness_label"] == "insufficient-evidence"
        assert s["recommendation_class"] == "manual-review"
        assert s["replay_status"] == "REPLAY_ERROR"

    def test_daily539_markov_cold_manual_review(self, p2_json):
        s = self._get_strategy(p2_json, "daily539_markov_cold")
        assert s["recommendation_class"] == "manual-review"
        assert s["replay_status"] == "REPLAY_ERROR"

    def test_p0b_sub_baseline(self, p2_json):
        s = self._get_strategy(p2_json, "p0b_539_3bet_f_cold_fmid")
        assert s["prediction_helpfulness_label"] == "sub-baseline"
        assert s["m3_plus_vs_baseline"] < 0

    def test_p0c_sub_baseline(self, p2_json):
        s = self._get_strategy(p2_json, "p0c_539_3bet_f_cold_x2")
        assert s["prediction_helpfulness_label"] == "sub-baseline"


# ---------------------------------------------------------------------------
# 10. P69 input constraints
# ---------------------------------------------------------------------------
class TestP69InputConstraints:
    def test_p69_candidate_list_not_empty(self, p2_json):
        candidates = p2_json["p69_input_constraints"]["candidate_strategies_for_p69"]
        assert len(candidates) >= 8

    def test_biglotto_excluded_from_p69(self, p2_json):
        excluded = p2_json["p69_input_constraints"]["exclude_games_reason"]
        assert "BIG_LOTTO" in excluded

    def test_include_games_correct(self, p2_json):
        games = p2_json["p69_input_constraints"]["include_games"]
        assert "POWER_LOTTO" in games
        assert "DAILY_539" in games
        assert "BIG_LOTTO" not in games

    def test_watchlist_deferred(self, p2_json):
        deferred = p2_json["p69_input_constraints"]["deferred_pending_oos"]
        assert any("midfreq_fourier_mk_3bet" in d for d in deferred)

    def test_prioritize_for_expansion_count(self, p2_json):
        counts = p2_json["summary"]["recommendation_counts"]
        assert counts["prioritize-for-expansion"] == 8

    def test_block_expansion_count(self, p2_json):
        counts = p2_json["summary"]["recommendation_counts"]
        assert counts["block-expansion"] == 10


# ---------------------------------------------------------------------------
# 11. MD content checks
# ---------------------------------------------------------------------------
class TestMDContent:
    def test_md_contains_classification(self):
        content = P2_MD.read_text()
        assert "P2_PREDICTION_HELPFULNESS_AUDIT_COMPLETE" in content

    def test_md_contains_prediction_helpful(self):
        content = P2_MD.read_text()
        assert "prediction-helpful" in content

    def test_md_contains_sub_baseline(self):
        content = P2_MD.read_text()
        assert "sub-baseline" in content

    def test_md_contains_l90_l91_reference(self):
        content = P2_MD.read_text()
        assert "L90" in content and "L91" in content

    def test_md_contains_theoretical_baselines(self):
        content = P2_MD.read_text()
        assert "3.87%" in content
        assert "1.86%" in content
        assert "1.00%" in content

    def test_md_no_production_apply_claim(self):
        content = P2_MD.read_text().lower()
        # Must not claim rows WERE applied (only "No rows were applied" is acceptable)
        assert "applied to production" not in content
        assert "promoted to online" not in content
        assert "lifecycle: online" not in content

    def test_md_contains_p69_section(self):
        content = P2_MD.read_text()
        assert "P69" in content
