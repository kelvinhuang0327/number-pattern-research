"""
test_p54_replay_roadmap_update.py

P54 Replay Roadmap Update After P53 WATCHLIST Staging Tests

Governance:
- No DB write
- No lifecycle promotion
- No champion replacement
- Production rows must remain 42460
"""
import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P54_JSON = REPO_ROOT / "outputs" / "replay" / "p54_replay_roadmap_update_after_p53_watchlist_20260525.json"
P54_MD = REPO_ROOT / "docs" / "replay" / "p54_replay_roadmap_update_after_p53_watchlist_20260525.md"
ROADMAP_MD = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_MD = REPO_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"
PRODUCTION_ROWS = 42460


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def p54_json():
    assert P54_JSON.exists(), f"P54 JSON not found: {P54_JSON}"
    with open(P54_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Artifact existence
# ---------------------------------------------------------------------------
class TestP54Artifacts:
    def test_json_exists(self):
        assert P54_JSON.exists()

    def test_md_exists(self):
        assert P54_MD.exists()

    def test_roadmap_md_exists(self):
        assert ROADMAP_MD.exists()

    def test_cto_analysis_exists(self):
        assert CTO_MD.exists()

    def test_json_task_is_p54(self, p54_json):
        assert p54_json["task"] == "P54"

    def test_json_option_a(self, p54_json):
        assert p54_json["option"] == "OPTION_A"

    def test_json_classification(self, p54_json):
        assert p54_json["overall_p54_classification"] == "P54_REPLAY_ROADMAP_UPDATED_AFTER_P53_WATCHLIST"


# ---------------------------------------------------------------------------
# 2. Governance
# ---------------------------------------------------------------------------
class TestP54Governance:
    def test_no_db_write(self, p54_json):
        assert p54_json["governance"]["no_db_write"] is True

    def test_no_lifecycle_promotion(self, p54_json):
        assert p54_json["governance"]["no_lifecycle_promotion"] is True

    def test_no_online_promotion(self, p54_json):
        assert p54_json["governance"]["no_online_promotion"] is True

    def test_no_champion_replacement(self, p54_json):
        assert p54_json["governance"]["no_champion_replacement"] is True

    def test_production_rows_unchanged(self, p54_json):
        assert p54_json["governance"]["production_rows_before"] == PRODUCTION_ROWS
        assert p54_json["governance"]["production_rows_after"] == PRODUCTION_ROWS

    def test_production_rows_in_db(self, db):
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert cur.fetchone()[0] == PRODUCTION_ROWS

    def test_candidate_not_online_in_db(self, db):
        cur = db.cursor()
        cur.execute(
            "SELECT DISTINCT replay_status FROM strategy_prediction_replays "
            "WHERE strategy_id='midfreq_fourier_mk_3bet' AND lottery_type='POWER_LOTTO'"
        )
        statuses = {row[0] for row in cur.fetchall()}
        assert "ONLINE" not in statuses


# ---------------------------------------------------------------------------
# 3. P53 chain confirmed in JSON
# ---------------------------------------------------------------------------
class TestP53ChainConfirmed:
    def test_p49hyg_commit(self, p54_json):
        assert p54_json["p53_chain_summary"]["p49hyg"]["commit"] == "79ab784"

    def test_p51_commit(self, p54_json):
        assert p54_json["p53_chain_summary"]["p51"]["commit"] == "0415cc8"

    def test_p52_commit(self, p54_json):
        assert p54_json["p53_chain_summary"]["p52"]["commit"] == "1b32e6a"

    def test_p53_commit(self, p54_json):
        assert p54_json["p53_chain_summary"]["p53"]["commit"] == "5992b27"

    def test_p53_source_commit(self, p54_json):
        assert p54_json["p53_source_commit"] == "5992b27"


# ---------------------------------------------------------------------------
# 4. Wave 4 strategy status
# ---------------------------------------------------------------------------
class TestWave4StrategyStatus:
    def test_candidate_watchlist(self, p54_json):
        strat = p54_json["wave4_strategy_status"]["midfreq_fourier_mk_3bet"]
        assert strat["classification"] == "WATCHLIST_STAGED_WITH_G4_WAIVER"
        assert strat["watchlist_status"] == "WATCHLIST"
        assert strat["online_promotion_authorized"] is False
        assert strat["champion_active"] == "fourier_rhythm_3bet"

    def test_candidate_metrics(self, p54_json):
        strat = p54_json["wave4_strategy_status"]["midfreq_fourier_mk_3bet"]
        assert strat["mean_hit"] == pytest.approx(1.027333, abs=0.001)
        assert strat["permutation_p"] == 0.0003

    def test_g4_restatement(self, p54_json):
        g4 = p54_json["wave4_strategy_status"]["midfreq_fourier_mk_3bet"]["g4_mcnemar_hit_ge3"]
        assert g4["b"] == 42
        assert g4["c"] == 50
        assert g4["direction"] == "CHAMPION_FAVORED"
        assert g4["waiver_granted"] is True

    def test_g5a_supplementary(self, p54_json):
        g5a = p54_json["wave4_strategy_status"]["midfreq_fourier_mk_3bet"]["g5a_mcnemar_hit_ge2"]
        assert g5a["b"] == 184
        assert g5a["c"] == 157
        assert g5a["direction"] == "CANDIDATE_FAVORED"

    def test_pp3_inconclusive(self, p54_json):
        assert p54_json["wave4_strategy_status"]["pp3_freqort_4bet"]["classification"] == "INCONCLUSIVE"

    def test_2bet_inconclusive(self, p54_json):
        assert p54_json["wave4_strategy_status"]["midfreq_fourier_2bet"]["classification"] == "INCONCLUSIVE"

    def test_oos_plan_gate_300(self, p54_json):
        plan = p54_json["wave4_strategy_status"]["midfreq_fourier_mk_3bet"]["oos_holdout_plan"]
        assert plan["promotion_requires_draws"] == 300


# ---------------------------------------------------------------------------
# 5. Roadmap content checks
# ---------------------------------------------------------------------------
class TestRoadmapContent:
    def test_roadmap_contains_p53_entry(self):
        content = ROADMAP_MD.read_text()
        assert "P53" in content
        assert "WATCHLIST" in content

    def test_roadmap_contains_p54_entry(self):
        content = ROADMAP_MD.read_text()
        assert "P54" in content

    def test_roadmap_contains_p49hyg(self):
        content = ROADMAP_MD.read_text()
        assert "P49HYG" in content or "79ab784" in content

    def test_roadmap_marker_updated(self):
        content = ROADMAP_MD.read_text()
        assert "CTO_ROADMAP_AFTER_P53_POWERLOTTO_WATCHLIST_20260525" in content

    def test_roadmap_champion_active(self):
        content = ROADMAP_MD.read_text()
        assert "fourier_rhythm_3bet" in content

    def test_roadmap_no_online_promotion_claimed(self):
        content = ROADMAP_MD.read_text().lower()
        # Should not claim ONLINE promotion was performed
        assert "promoted to online" not in content
        assert "lifecycle: online" not in content

    def test_roadmap_oos_plan_present(self):
        content = ROADMAP_MD.read_text()
        assert "150" in content and "300" in content and "500" in content

    def test_roadmap_p55_options_present(self):
        content = ROADMAP_MD.read_text()
        assert "P55" in content or "Wave 5" in content or "Next Session" in content


# ---------------------------------------------------------------------------
# 6. CTO Analysis content checks
# ---------------------------------------------------------------------------
class TestCTOAnalysisContent:
    def test_cto_contains_p53_complete(self):
        content = CTO_MD.read_text()
        assert "P53" in content
        assert "5992b27" in content

    def test_cto_final_classification(self):
        content = CTO_MD.read_text()
        assert "CTO_ROADMAP_AFTER_P53_POWERLOTTO_WATCHLIST_20260525" in content

    def test_cto_production_rows_42460(self):
        content = CTO_MD.read_text()
        assert "42460" in content

    def test_cto_champion_not_replaced(self):
        content = CTO_MD.read_text()
        assert "NOT replaced" in content or "not replaced" in content.lower()

    def test_cto_g4_waiver_mentioned(self):
        content = CTO_MD.read_text()
        assert "waiver" in content.lower() and ("b=42" in content or "b=42" in content or "42" in content)

    def test_cto_g5a_finding_mentioned(self):
        content = CTO_MD.read_text()
        assert "184" in content and "157" in content

    def test_cto_wave5_next_mentioned(self):
        content = CTO_MD.read_text()
        assert "Wave 5" in content or "wave 5" in content.lower()


# ---------------------------------------------------------------------------
# 7. Coverage denominator
# ---------------------------------------------------------------------------
class TestCoverageDenominator:
    def test_coverage_denominator(self, p54_json):
        assert p54_json["coverage_denominator"]["strategy_groups_row_backed"] == "28 / 59"

    def test_gap_to_target(self, p54_json):
        assert p54_json["coverage_denominator"]["gap_to_target_rows"] == 46500


# ---------------------------------------------------------------------------
# 8. P55 options present
# ---------------------------------------------------------------------------
class TestP55Options:
    def test_p55_options_present(self, p54_json):
        options = p54_json["p55_options"]
        assert len(options) >= 4

    def test_wave5_option_present(self, p54_json):
        options = p54_json["p55_options"]
        labels = [o["option"] for o in options]
        assert "P55-A" in labels

    def test_browser_visual_option_present(self, p54_json):
        options = p54_json["p55_options"]
        labels = [o["option"] for o in options]
        assert "P55-B" in labels
