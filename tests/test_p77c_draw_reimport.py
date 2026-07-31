"""
P77C: Verify POWER_LOTTO draw 115000041 re-import into canonical draws table.
"""
import json
import sqlite3
import pytest

DB_PATH = "lottery_api/data/lottery_v2.db"
ARTIFACT_PATH = "outputs/replay/p77c_draw_reimport_20260526.json"

TARGET_DRAW = "115000041"
TARGET_LOTTERY_TYPE = "POWER_LOTTO"
TARGET_DATE = "2026/05/21"
TARGET_NUMBERS = "[6, 14, 22, 28, 35, 38]"
TARGET_SPECIAL = 1
EXPECTED_REPLAY_ROWS = 46960


@pytest.fixture
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


@pytest.fixture
def artifact():
    with open(ARTIFACT_PATH) as f:
        return json.load(f)


class TestP77CDrawExists:
    def test_draw_115000041_exists_exactly_once(self, db):
        c = db.cursor()
        c.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type=? AND draw=?",
            (TARGET_LOTTERY_TYPE, TARGET_DRAW),
        )
        assert c.fetchone()[0] == 1

    def test_draw_date(self, db):
        c = db.cursor()
        c.execute(
            "SELECT date FROM draws WHERE lottery_type=? AND draw=?",
            (TARGET_LOTTERY_TYPE, TARGET_DRAW),
        )
        assert c.fetchone()[0] == TARGET_DATE

    def test_draw_numbers(self, db):
        c = db.cursor()
        c.execute(
            "SELECT numbers FROM draws WHERE lottery_type=? AND draw=?",
            (TARGET_LOTTERY_TYPE, TARGET_DRAW),
        )
        assert c.fetchone()[0] == TARGET_NUMBERS

    def test_draw_special(self, db):
        c = db.cursor()
        c.execute(
            "SELECT special FROM draws WHERE lottery_type=? AND draw=?",
            (TARGET_LOTTERY_TYPE, TARGET_DRAW),
        )
        assert c.fetchone()[0] == TARGET_SPECIAL

    def test_power_lotto_max_draw_is_115000041(self, db):
        c = db.cursor()
        c.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type=?",
            (TARGET_LOTTERY_TYPE,),
        )
        assert c.fetchone()[0] == 115000041


class TestP77CReplayRowsUntouched:
    def test_replay_rows_unchanged(self, db):
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert c.fetchone()[0] == EXPECTED_REPLAY_ROWS


class TestP77CArtifact:
    def test_artifact_exists(self, artifact):
        assert artifact is not None

    def test_artifact_classification(self, artifact):
        assert artifact["final_classification"] == "P77C_DRAW_REIMPORT_SUCCESS"

    def test_artifact_p79_can_proceed(self, artifact):
        assert artifact["p79_readiness"]["can_proceed"] is True

    def test_artifact_p79_blocker_is_null(self, artifact):
        assert artifact["p79_readiness"]["blocker"] is None

    def test_artifact_p78_still_ready(self, artifact):
        assert artifact["p79_readiness"]["p78_status"] == "PLAN_READY_FOR_P79_APPLY"

    def test_artifact_verification_all_passed(self, artifact):
        assert artifact["verification"]["all_assertions_passed"] is True

    def test_artifact_replay_rows_delta_zero(self, artifact):
        assert artifact["verification"]["replay_rows_delta"] == 0

    def test_artifact_max_draw_after(self, artifact):
        assert artifact["verification"]["power_lotto_max_draw_after"] == 115000041
