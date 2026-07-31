"""Tests for P333 strategy pick / combination scoreboard."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import analysis.p333_strategy_pick_combination_scoreboard as P

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = REPO_ROOT / "outputs/research/p333_strategy_pick_combination_scoreboard_20260702.json"


def _insert_row(
    conn,
    lottery_type,
    strategy_id,
    target_draw,
    bet_index,
    predicted,
    actual,
    predicted_special=None,
    actual_special=None,
):
    conn.execute(
        """
        INSERT INTO strategy_prediction_replays (
            lottery_type, strategy_id, target_draw, bet_index,
            predicted_numbers, predicted_special,
            actual_numbers, actual_special,
            history_cutoff_draw, replay_status, dry_run
        ) VALUES (?,?,?,?,?,?,?,?,?,'PREDICTED',0)
        """,
        (
            lottery_type,
            strategy_id,
            str(target_draw),
            bet_index,
            json.dumps(predicted),
            predicted_special,
            json.dumps(actual),
            actual_special,
            str(int(target_draw) - 1),
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
        # BIG_LOTTO: strategy A has M2+special when first three selected are [1,2,7].
        _insert_row(
            conn,
            "BIG_LOTTO",
            "fourier_big",
            draw,
            1,
            [1, 2, 7, 10, 11, 12],
            [1, 2, 3, 4, 5, 6],
            None,
            7,
        )
        _insert_row(
            conn,
            "BIG_LOTTO",
            "cold_big",
            draw,
            1,
            [30, 31, 32, 33, 34, 35],
            [1, 2, 3, 4, 5, 6],
            None,
            7,
        )

        # POWER_LOTTO: M1+second-zone should count as a prize signal.
        _insert_row(
            conn,
            "POWER_LOTTO",
            "fourier_power",
            draw,
            1,
            [1, 20, 21, 22, 23, 24],
            [1, 2, 3, 4, 5, 6],
            4,
            4,
        )
        _insert_row(
            conn,
            "POWER_LOTTO",
            "cold_power",
            draw,
            1,
            [30, 31, 32, 33, 34, 35],
            [1, 2, 3, 4, 5, 6],
            5,
            4,
        )

        # DAILY_539: simple M2+ endpoint.
        _insert_row(
            conn,
            "DAILY_539",
            "markov_539",
            draw,
            1,
            [1, 2, 30, 31, 32],
            [1, 2, 3, 4, 5],
        )
    conn.commit()
    conn.close()


def test_big_lotto_m2_plus_special_signal():
    result = P.score_selection(
        "BIG_LOTTO",
        selected_numbers=[1, 2, 7],
        second_zone_candidates=[],
        actual_numbers=[1, 2, 3, 4, 5, 6],
        actual_special=7,
    )
    assert result["main_hits"] == 2
    assert result["special_hit"] is True
    assert result["prize_signal"] is True


def test_power_lotto_m1_plus_second_zone_signal():
    result = P.score_selection(
        "POWER_LOTTO",
        selected_numbers=[1],
        second_zone_candidates=[4],
        actual_numbers=[1, 2, 3, 4, 5, 6],
        actual_special=4,
    )
    assert result["main_hits"] == 1
    assert result["second_zone_hit"] is True
    assert result["prize_signal"] is True


def test_synthetic_run_builds_pick_matrix_and_combo_leaderboard(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    artifact = P.run_analysis(db)

    assert artifact["safety_flags"]["db_write"] is False
    assert artifact["safety_flags"]["model_training"] is False
    assert artifact["summary"]["strategy_pick_records"] > 0
    assert artifact["summary"]["combination_leaderboard_records"] > 0

    top_big_k3 = artifact["top_strategy_pick_by_lottery_window_pick"]["BIG_LOTTO|50|3"]
    assert top_big_k3["strategy_id"] == "fourier_big"
    assert top_big_k3["prize_signal_rate"] == 1.0

    top_power_k1 = artifact["top_strategy_pick_by_lottery_window_pick"]["POWER_LOTTO|50|1"]
    assert top_power_k1["strategy_id"] == "fourier_power"
    assert top_power_k1["prize_signal_rate"] == 1.0


def test_committed_artifact_shape_after_generation():
    assert ARTIFACT.exists(), f"missing generated artifact: {ARTIFACT}"
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert data["task_id"] == "P333"
    assert data["classification"] == "P333_STRATEGY_PICK_COMBINATION_SCOREBOARD_READY"
    assert data["window_policy"]["primary_windows"] == [50, 300, 750]
    assert data["safety_flags"]["db_read_only"] is True
    assert "BIG_LOTTO|750|6" in data["best_combination_by_lottery_window_budget"]


def test_replay_api_serves_p333_artifact():
    from lottery_api.routes import replay

    app = FastAPI()
    app.include_router(replay.router)
    client = TestClient(app)
    response = client.get("/api/replay/strategy-pick-scoreboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "P333"
    assert payload["historical_replay_only"] is True
    assert payload["no_betting_advice"] is True
