"""Focused tests for the read-only P542A descriptive scoreboard."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import analysis.p542a_strategy_pick_combination_scoreboard as scoreboard

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMITTED_JSON = (
    REPO_ROOT / "outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json"
)
COMMITTED_MD = (
    REPO_ROOT / "outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.md"
)


def _insert_row(
    conn: sqlite3.Connection,
    lottery_type: str,
    strategy_id: str,
    target_draw: int,
    predicted: list[int],
    actual: list[int],
    predicted_special: int | None = None,
    actual_special: int | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO strategy_prediction_replays (
            lottery_type, strategy_id, target_draw, bet_index,
            predicted_numbers, predicted_special, actual_numbers, actual_special,
            history_cutoff_draw, replay_status, dry_run
        ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, 'PREDICTED', 0)
        """,
        (
            lottery_type,
            strategy_id,
            str(target_draw),
            json.dumps(predicted),
            predicted_special,
            json.dumps(actual),
            actual_special,
            str(target_draw - 1),
        ),
    )


def _build_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE strategy_prediction_replays (
            lottery_type TEXT,
            strategy_id TEXT,
            target_draw TEXT,
            bet_index INTEGER,
            predicted_numbers TEXT,
            predicted_special INTEGER,
            actual_numbers TEXT,
            actual_special INTEGER,
            history_cutoff_draw TEXT,
            replay_status TEXT,
            dry_run INTEGER
        )
        """
    )
    for draw in range(1000, 1060):
        _insert_row(
            conn,
            "BIG_LOTTO",
            "big_good",
            draw,
            [1, 2, 7, 30, 31, 32],
            [1, 2, 3, 4, 5, 6],
            actual_special=7,
        )
        _insert_row(
            conn,
            "BIG_LOTTO",
            "big_cold",
            draw,
            [30, 31, 32, 33, 34, 35],
            [1, 2, 3, 4, 5, 6],
            actual_special=7,
        )
        _insert_row(
            conn,
            "DAILY_539",
            "daily_good",
            draw,
            [1, 2, 20, 21, 22],
            [1, 2, 3, 4, 5],
        )
        _insert_row(
            conn,
            "DAILY_539",
            "daily_cold",
            draw,
            [20, 21, 22, 23, 24],
            [1, 2, 3, 4, 5],
        )
        _insert_row(
            conn,
            "POWER_LOTTO",
            "power_zone2_good",
            draw,
            [1, 20, 21, 22, 23, 24],
            [1, 2, 3, 4, 5, 6],
            predicted_special=4,
            actual_special=4,
        )
        _insert_row(
            conn,
            "POWER_LOTTO",
            "power_zone2_cold",
            draw,
            [30, 31, 32, 33, 34, 35],
            [1, 2, 3, 4, 5, 6],
            predicted_special=5,
            actual_special=4,
        )
    conn.commit()
    conn.close()


def test_analysis_is_deterministic_and_has_all_requested_dimensions(tmp_path: Path) -> None:
    db = tmp_path / "replays.db"
    _build_db(db)

    first = scoreboard.run_analysis(db)
    second = scoreboard.run_analysis(db)

    assert first == second
    assert first["task_id"] == "P542A"
    assert first["deterministic_output"] is True
    assert first["historical_replay_only"] is True
    assert first["no_prediction_claim"] is True
    assert first["window_policy"]["draw_windows"] == [50, 300, 750]
    assert first["summary"]["strategy_pick_records"] > 0
    assert first["summary"]["combination_leaderboard_records"] > 0
    assert first["power_lotto_zone2_metrics"]
    assert "strategy_window_decisions" not in first


def test_power_lotto_zone2_uses_matched_random_baseline(tmp_path: Path) -> None:
    db = tmp_path / "replays.db"
    _build_db(db)
    artifact = scoreboard.run_analysis(db)

    record = next(
        row
        for row in artifact["power_lotto_zone2_metrics"]
        if row["scope"] == "strategy_pick"
        and row["identifier"] == "power_zone2_good"
        and row["window"] == 50
    )
    assert record["zone2_hit_rate"] == 1.0
    assert record["avg_zone2_candidates"] == 1.0
    assert record["random_zone2_hit_rate"] == 0.125
    assert record["zone2_hit_edge_pp"] == 87.5
    assert record["prize_aware_hit_rate"] == 1.0


def test_read_only_connection_rejects_insert(tmp_path: Path) -> None:
    db = tmp_path / "replays.db"
    _build_db(db)

    conn = scoreboard._open_read_only(db)
    try:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO strategy_prediction_replays VALUES (NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)")
    finally:
        conn.close()


def test_committed_replay_artifact_fallback_does_not_open_a_db(tmp_path: Path) -> None:
    artifact = scoreboard.run_analysis(
        tmp_path / "missing.db",
        REPO_ROOT / "outputs/research/p333_strategy_pick_combination_scoreboard_20260702.json",
    )

    assert artifact["source"]["source_kind"] == "committed_P333_replay_scoreboard"
    assert artifact["source"]["db_opened"] is False
    assert artifact["safety_flags"]["db_opened"] is False


def test_artifact_writes_are_byte_stable(tmp_path: Path) -> None:
    db = tmp_path / "replays.db"
    _build_db(db)
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    scoreboard.write_artifacts(scoreboard.run_analysis(db), json_path, md_path)
    first_json = json_path.read_text(encoding="utf-8")
    first_md = md_path.read_text(encoding="utf-8")
    scoreboard.write_artifacts(scoreboard.run_analysis(db), json_path, md_path)

    assert json_path.read_text(encoding="utf-8") == first_json
    assert md_path.read_text(encoding="utf-8") == first_md
    assert "不預測未來" in first_md


def test_committed_artifacts_have_the_expected_contract() -> None:
    assert COMMITTED_JSON.exists()
    assert COMMITTED_MD.exists()
    payload = json.loads(COMMITTED_JSON.read_text(encoding="utf-8"))
    assert payload["task_id"] == "P542A"
    assert payload["classification"] == scoreboard.CLASSIFICATION
    assert payload["safety_flags"]["db_read_only"] is True
    assert payload["safety_flags"]["db_write"] is False
    assert payload["window_policy"]["draw_windows"] == [50, 300, 750]
    assert payload["power_lotto_zone2_metrics"]
    assert payload["deterministic_payload_sha256"]
