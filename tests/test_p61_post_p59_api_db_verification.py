"""tests/test_p61_post_p59_api_db_verification.py

Validates P61 evidence: post-P59 DB/API verification output JSON and DB state.
READ-ONLY: zero production writes.
"""
import json
import os
import sqlite3
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(ROOT, "lottery_api", "data", "lottery_v2.db")
P61_JSON = os.path.join(ROOT, "outputs", "replay", "p61_post_p59_api_db_verification_20260525.json")
P59_CAID = "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"


@pytest.fixture(scope="module")
def p61_json():
    with open(P61_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ── P61 JSON structure ────────────────────────────────────────────────────────
class TestP61JSONStructure:
    def test_phase(self, p61_json):
        assert p61_json["phase"] == "P61"

    def test_classification(self, p61_json):
        assert p61_json["classification"] == "P61_DB_LAYER_API_VERIFICATION_PASS"

    def test_marker(self, p61_json):
        assert p61_json["marker"] == "P61_POST_P59_API_DB_VERIFICATION_PASS_20260525"

    def test_overall_status(self, p61_json):
        assert p61_json["overall_status"] == "PASS"

    def test_branch(self, p61_json):
        assert p61_json["branch"] == "p61-post-p59-api-db-verification"

    def test_governance_no_db_write(self, p61_json):
        assert p61_json["governance"]["no_db_write"] is True

    def test_governance_no_online_promotion(self, p61_json):
        assert p61_json["governance"]["no_online_promotion"] is True

    def test_governance_production_rows(self, p61_json):
        assert p61_json["governance"]["production_rows"] == 43960


# ── P61 DB verification section ───────────────────────────────────────────────
class TestP61DBSection:
    def test_total_rows(self, p61_json):
        assert p61_json["db_verification"]["total_rows"] == 43960

    def test_p59_rows(self, p61_json):
        assert p61_json["db_verification"]["p59_rows"] == 1500

    def test_fourier30_rows(self, p61_json):
        assert p61_json["db_verification"]["fourier30_markov30_2bet_rows"] == 1500

    def test_p59_caid(self, p61_json):
        assert p61_json["db_verification"]["p59_caid"] == P59_CAID

    def test_db_status(self, p61_json):
        assert p61_json["db_verification"]["status"] == "PASS"


# ── P61 semantic checks section ───────────────────────────────────────────────
class TestP61SemanticSection:
    def test_bad_numbers_zero(self, p61_json):
        assert p61_json["semantic_checks"]["bad_predicted_numbers"] == 0

    def test_bad_special_zero(self, p61_json):
        assert p61_json["semantic_checks"]["bad_predicted_special"] == 0

    def test_bad_dry_run_zero(self, p61_json):
        assert p61_json["semantic_checks"]["bad_dry_run"] == 0

    def test_semantic_status(self, p61_json):
        assert p61_json["semantic_checks"]["status"] == "PASS"


# ── P61 DB-layer API verification section ────────────────────────────────────
class TestP61APISection:
    def test_mode_is_db_layer(self, p61_json):
        assert p61_json["db_layer_api_verification"]["mode"] == "DB_LAYER"

    def test_summary_fourier30_present(self, p61_json):
        assert p61_json["db_layer_api_verification"]["summary_query"]["fourier30_markov30_2bet_present"] is True

    def test_summary_fourier30_draws(self, p61_json):
        assert p61_json["db_layer_api_verification"]["summary_query"]["fourier30_total_draws"] == 1500

    def test_summary_status(self, p61_json):
        assert p61_json["db_layer_api_verification"]["summary_query"]["status"] == "PASS"

    def test_history_rows_returned(self, p61_json):
        assert p61_json["db_layer_api_verification"]["history_query"]["rows_returned_limit5"] == 5

    def test_history_dry_run_zero(self, p61_json):
        assert p61_json["db_layer_api_verification"]["history_query"]["sample_dry_run"] == 0

    def test_history_status(self, p61_json):
        assert p61_json["db_layer_api_verification"]["history_query"]["status"] == "PASS"

    def test_strategies_fourier30_visible(self, p61_json):
        assert p61_json["db_layer_api_verification"]["strategies_query"]["fourier30_markov30_2bet_visible"] is True

    def test_strategies_status(self, p61_json):
        assert p61_json["db_layer_api_verification"]["strategies_query"]["status"] == "PASS"

    def test_p59_slice_count(self, p61_json):
        assert p61_json["db_layer_api_verification"]["p59_slice_query"]["count"] == 1500

    def test_p59_slice_status(self, p61_json):
        assert p61_json["db_layer_api_verification"]["p59_slice_query"]["status"] == "PASS"


# ── P61 watchlist section ─────────────────────────────────────────────────────
class TestP61WatchlistSection:
    def test_cold_complement_zero(self, p61_json):
        assert p61_json["watchlist_not_applied"]["cold_complement_2bet"] == 0

    def test_zonal_entropy_zero(self, p61_json):
        assert p61_json["watchlist_not_applied"]["zonal_entropy_2bet"] == 0

    def test_watchlist_status(self, p61_json):
        assert p61_json["watchlist_not_applied"]["status"] == "PASS"


# ── Live DB cross-checks ──────────────────────────────────────────────────────
class TestP61LiveDB:
    def test_total_rows_live(self, db):
        cnt = db.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        assert cnt == 43960

    def test_p59_rows_live(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (P59_CAID,)
        ).fetchone()[0]
        assert cnt == 1500

    def test_fourier30_rows_live(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id LIKE '%fourier30_markov30%' AND lottery_type='POWER_LOTTO'"
        ).fetchone()[0]
        assert cnt == 1500

    def test_p59_all_dry_run_zero(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND dry_run != 0",
            (P59_CAID,)
        ).fetchone()[0]
        assert cnt == 0, f"Found {cnt} P59 rows with dry_run != 0"

    def test_p59_all_power_lotto(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND lottery_type != 'POWER_LOTTO'",
            (P59_CAID,)
        ).fetchone()[0]
        assert cnt == 0, f"Found {cnt} P59 rows with wrong lottery_type"

    def test_fourier30_in_summary_query(self, db):
        rows = db.execute("""
            SELECT strategy_id, COUNT(*) as n
            FROM strategy_prediction_replays
            WHERE lottery_type = 'POWER_LOTTO'
              AND replay_status = 'PREDICTED'
              AND strategy_id = 'fourier30_markov30_2bet'
            GROUP BY strategy_id
        """).fetchall()
        assert len(rows) == 1
        assert rows[0]["n"] == 1500

    def test_watchlist_not_in_db(self, db):
        for strat in ("cold_complement_2bet", "zonal_entropy_2bet"):
            cnt = db.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id LIKE ?",
                (f"%{strat}%",)
            ).fetchone()[0]
            assert cnt == 0, f"{strat}: expected 0 rows, got {cnt}"
