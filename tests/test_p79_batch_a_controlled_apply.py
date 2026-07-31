"""
P79: Verify Batch A controlled apply — POWER_LOTTO draw 115000041.
"""
import json
import sqlite3
import pytest

DB_PATH = "lottery_api/data/lottery_v2.db"
ARTIFACT_PATH = "outputs/replay/p79_batch_a_controlled_apply_20260526.json"

TARGET_DRAW = "115000041"
TARGET_LOTTERY_TYPE = "POWER_LOTTO"
TARGET_DATE = "2026/05/21"
TARGET_STRATEGIES = ["fourier_rhythm_3bet", "fourier30_markov30_2bet"]
EXPECTED_REPLAY_ROWS_AFTER = 46962
EXPECTED_IDS = {46961, 46962}


@pytest.fixture
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


@pytest.fixture
def artifact():
    with open(ARTIFACT_PATH) as f:
        return json.load(f)


class TestP79RowsInserted:
    def test_exactly_two_rows_for_target_draw(self, db):
        c = db.cursor()
        c.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE lottery_type=? AND target_draw=?
                 AND strategy_id IN ('fourier_rhythm_3bet','fourier30_markov30_2bet')""",
            (TARGET_LOTTERY_TYPE, TARGET_DRAW),
        )
        assert c.fetchone()[0] == 2

    def test_fourier_rhythm_3bet_row(self, db):
        c = db.cursor()
        c.execute(
            """SELECT target_date, predicted_numbers, actual_numbers,
                      actual_special, hit_numbers, hit_count, special_hit, dry_run
               FROM strategy_prediction_replays
               WHERE lottery_type=? AND target_draw=? AND strategy_id='fourier_rhythm_3bet'""",
            (TARGET_LOTTERY_TYPE, TARGET_DRAW),
        )
        row = c.fetchone()
        assert row is not None
        assert row[0] == TARGET_DATE
        assert row[1] == "[3, 23, 24, 28, 30, 36]"
        assert row[2] == "[6, 14, 22, 28, 35, 38]"
        assert row[3] == 1
        assert row[4] == "[28]"
        assert row[5] == 1
        assert row[6] == 0
        assert row[7] == 0  # dry_run=0 (production)

    def test_fourier30_markov30_2bet_row(self, db):
        c = db.cursor()
        c.execute(
            """SELECT target_date, predicted_numbers, actual_numbers,
                      actual_special, hit_numbers, hit_count, special_hit, dry_run
               FROM strategy_prediction_replays
               WHERE lottery_type=? AND target_draw=? AND strategy_id='fourier30_markov30_2bet'""",
            (TARGET_LOTTERY_TYPE, TARGET_DRAW),
        )
        row = c.fetchone()
        assert row is not None
        assert row[0] == TARGET_DATE
        assert row[1] == "[13, 14, 27, 29, 34, 38]"
        assert row[2] == "[6, 14, 22, 28, 35, 38]"
        assert row[3] == 1
        assert row[4] == "[14, 38]"
        assert row[5] == 2
        assert row[6] == 0
        assert row[7] == 0  # dry_run=0 (production)

    def test_both_rows_not_dry_run(self, db):
        c = db.cursor()
        c.execute(
            """SELECT SUM(dry_run) FROM strategy_prediction_replays
               WHERE lottery_type=? AND target_draw=?
                 AND strategy_id IN ('fourier_rhythm_3bet','fourier30_markov30_2bet')""",
            (TARGET_LOTTERY_TYPE, TARGET_DRAW),
        )
        assert c.fetchone()[0] == 0

    def test_no_duplicates(self, db):
        c = db.cursor()
        for strat in TARGET_STRATEGIES:
            c.execute(
                """SELECT COUNT(*) FROM strategy_prediction_replays
                   WHERE lottery_type=? AND target_draw=? AND strategy_id=?""",
                (TARGET_LOTTERY_TYPE, TARGET_DRAW, strat),
            )
            assert c.fetchone()[0] == 1, f"Duplicate for {strat}"

    def test_truth_level_verified(self, db):
        c = db.cursor()
        c.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE lottery_type=? AND target_draw=?
                 AND strategy_id IN ('fourier_rhythm_3bet','fourier30_markov30_2bet')
                 AND truth_level='POWERLOTTO_DRAW_EXT_VERIFIED'""",
            (TARGET_LOTTERY_TYPE, TARGET_DRAW),
        )
        assert c.fetchone()[0] == 2


class TestP79RowCount:
    def test_total_replay_rows_is_46962(self, db):
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert c.fetchone()[0] == EXPECTED_REPLAY_ROWS_AFTER

    def test_draws_table_max_unchanged(self, db):
        c = db.cursor()
        c.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type=?",
            (TARGET_LOTTERY_TYPE,),
        )
        assert c.fetchone()[0] == 115000041


class TestP79Artifact:
    def test_artifact_exists(self, artifact):
        assert artifact is not None

    def test_classification(self, artifact):
        assert artifact["final_classification"] == "P79_BATCH_A_CONTROLLED_APPLY_SUCCESS"

    def test_not_dry_run(self, artifact):
        assert artifact["dry_run"] is False

    def test_delta(self, artifact):
        assert artifact["verification"]["replay_rows_delta"] == 2

    def test_rows_after(self, artifact):
        assert artifact["verification"]["replay_rows_after"] == 46962

    def test_duplicate_guard_pass(self, artifact):
        assert "PASS" in artifact["verification"]["duplicate_guard_pre"]
        assert "PASS" in artifact["verification"]["duplicate_guard_post"]

    def test_all_assertions_passed(self, artifact):
        assert artifact["verification"]["all_assertions_passed"] is True

    def test_rollback_sql_present(self, artifact):
        assert "DELETE FROM strategy_prediction_replays" in artifact["rollback_sql"]
        assert "46961" in artifact["rollback_sql"]
        assert "46962" in artifact["rollback_sql"]
