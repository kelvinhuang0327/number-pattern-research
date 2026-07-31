from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts import p238b_nist_randomness_audit_artifact_build as audit


REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _make_tiny_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE draws ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, draw TEXT, date TEXT, lottery_type TEXT, "
            "numbers TEXT, special INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "jackpot_amount REAL DEFAULT NULL, sell_amount REAL DEFAULT NULL, total_amount REAL DEFAULT NULL, "
            "UNIQUE(draw, lottery_type))"
        )
        conn.execute(
            "CREATE TABLE strategy_prediction_replays ("
            "lottery_type TEXT, target_draw TEXT, strategy_id TEXT, bet_index INTEGER)"
        )
        for i in range(1, 11):
            conn.execute(
                "INSERT INTO draws(draw,date,lottery_type,numbers,special) VALUES (?,?,?,?,?)",
                (f"B{i:03d}", f"2026-01-{i:02d}", "BIG_LOTTO", json.dumps([1, 2, 3, 4, 5, 6]), 7),
            )
            conn.execute(
                "INSERT INTO draws(draw,date,lottery_type,numbers,special) VALUES (?,?,?,?,?)",
                (f"D{i:03d}", f"2026-01-{i:02d}", "DAILY_539", json.dumps([1, 2, 3, 4, 5]), 0),
            )
            conn.execute(
                "INSERT INTO draws(draw,date,lottery_type,numbers,special) VALUES (?,?,?,?,?)",
                (f"P{i:03d}", f"2026-01-{i:02d}", "POWER_LOTTO", json.dumps([1, 2, 3, 4, 5, 6]), 1),
            )
            conn.execute(
                "INSERT INTO draws(draw,date,lottery_type,numbers,special) VALUES (?,?,?,?,?)",
                (f"S3{i:03d}", f"2026-01-{i:02d}", "3_STAR", json.dumps([0, 1, 2]), 0),
            )
            conn.execute(
                "INSERT INTO draws(draw,date,lottery_type,numbers,special) VALUES (?,?,?,?,?)",
                (f"S4{i:03d}", f"2026-01-{i:02d}", "4_STAR", json.dumps([0, 1, 2, 3]), 0),
            )
        conn.commit()
    finally:
        conn.close()


def test_active_universe_is_explicit_and_fixed():
    assert audit.ACTIVE_LOTTERIES == ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO", "3_STAR", "4_STAR")
    assert set(audit.ACTIVE_LOTTERIES) == set(audit.LOTTERY_RULES)


def test_connect_ro_blocks_write_on_temp_db(tmp_path: Path):
    db = tmp_path / "tiny.db"
    _make_tiny_db(db)
    conn = audit._connect_ro(db)
    try:
        conn.execute("SELECT COUNT(*) FROM draws").fetchone()
        with pytest.raises(sqlite3.OperationalError) as exc:
            conn.execute("INSERT INTO strategy_prediction_replays(lottery_type,target_draw,strategy_id) VALUES ('x','y','z')")
        assert "readonly" in str(exc.value).lower() or "read-only" in str(exc.value).lower()
    finally:
        conn.close()


def test_build_artifact_contract_on_tiny_db(tmp_path: Path):
    db = tmp_path / "tiny.db"
    _make_tiny_db(db)
    result = audit.build_artifact(db_path=db, windows=("all-history",))

    assert result["diagnostics_only"] is True
    assert result["predictability_claim"] is False
    assert result["win_rate_claim"] is False
    assert result["betting_advice"] is False
    assert result["strategy_authorized"] is False
    assert result["production_change_authorized"] is False
    assert result["monitoring_job_authorized"] is False
    assert result["db_write_performed"] is False
    assert result["registry_write_performed"] is False
    assert result["data_snapshot"]["replay_rows_used_as_unit"] is False
    assert result["data_snapshot"]["db_rows_before"] == result["data_snapshot"]["db_rows_after"]
    assert result["pre_registration"]["family_size_declared_before_run"] > 0
    assert result["alert_summary"]["red_authorizes_strategy"] is False
    assert result["alert_summary"]["red_authorizes_human_review_only"] is True
    assert result["alert_summary"]["orange_count"] == 0
    assert result["alert_summary"]["red_count"] == 0
    assert result["final_recommendation"] == "HOLD"
    assert result["final_classification"] == "P238B_NIST_RANDOMNESS_AUDIT_ARTIFACT_ONLY_BUILD_COMPLETE"


def test_rejects_implicit_or_changed_universe(tmp_path: Path):
    db = tmp_path / "tiny.db"
    _make_tiny_db(db)
    with pytest.raises(ValueError):
        audit.build_artifact(db_path=db, lotteries=("BIG_LOTTO",), windows=("all-history",))


def test_write_artifacts_json_and_markdown(tmp_path: Path):
    db = tmp_path / "tiny.db"
    _make_tiny_db(db)
    json_path = tmp_path / "artifact.json"
    md_path = tmp_path / "artifact.md"
    result = audit.run(db_path=db, json_path=json_path, md_path=md_path, windows=("all-history",))

    loaded = json.loads(json_path.read_text())
    md = md_path.read_text()
    assert loaded["task_id"] == "P238B"
    assert loaded["classification"] == result["classification"]
    assert "This artifact is diagnostics-only." in md
    assert "This artifact does not predict lottery numbers." in md
    assert "This artifact does not improve win rate." in md
    assert "This artifact is not betting advice." in md
    assert "RED alert authorizes human review only." in md
    assert "NULL / GREEN is success." in md


@pytest.mark.skipif(not DB_PATH.exists(), reason="production DB absent")
def test_real_db_no_write_and_core_schema():
    try:
        before_conn = audit._connect_ro(DB_PATH)
        try:
            before = before_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        finally:
            before_conn.close()
        result = audit.build_artifact(DB_PATH)
        after_conn = audit._connect_ro(DB_PATH)
        try:
            after = after_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        finally:
            after_conn.close()
    except sqlite3.OperationalError as exc:
        pytest.skip(f"production DB not openable read-only right now: {exc}")

    assert before == after == 94924
    assert result["data_snapshot"]["db_open_mode"] == "read-only"
    assert result["active_audit_inventory"]
    active = {item["lottery_type"]: item["draw_rows"] for item in result["active_audit_inventory"]}
    # P246I NOTE: BIG_LOTTO raw total = 22,238 (includes 19,100 ADD_ON_PRIZE_EXCLUDED add-on/special
    # prize records). These are valid lottery-related records preserved in the DB. They are excluded
    # from canonical 6/49 main-draw research (canonical count ~2,113) by get_canonical_draws().
    # The P238B NIST audit ran on all raw rows (mixed population). A canonical-only re-audit is
    # recommended after P247 Type D segregation. This assertion tests raw DB row count, NOT the
    # canonical research population. See P246B/P246C/P246I for taxonomy and isolation details.
    assert active["BIG_LOTTO"] >= 22238  # raw total (including add-on rows); canonical ~2,113
    assert active["DAILY_539"] >= 5879
    assert active["POWER_LOTTO"] >= 1916
    assert active["3_STAR"] >= 4179
    assert active["4_STAR"] >= 2922
    assert all(r["replay_rows_used_as_unit"] is False for r in result["test_results"])
