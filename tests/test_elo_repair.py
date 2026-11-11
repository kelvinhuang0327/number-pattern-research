"""
tests/test_elo_repair.py — P4 Elo 修復模組單元測試（12 項）
"""
import math
import pytest
from wbc_backend.recommendation.elo_repair import (
    is_spring_training_game,
    filter_regular_season_games,
    elo_prob,
    initialize_elo_from_win_rate,
    check_2024_data_availability,
    run_elo_walk_forward_with_repair,
    compare_elo_variants,
    SPRING_TRAINING_END_DATE,
)


# ---------- 1 ----------
def test_is_spring_training_true():
    assert is_spring_training_game("2025-03-20") is True


# ---------- 2 ----------
def test_is_spring_training_false_opening_day():
    assert is_spring_training_game("2025-03-28") is False


# ---------- 3 ----------
def test_filter_regular_season_games():
    rows = [
        {"game_date": "2025-03-18", "home_team": "A", "away_team": "B", "brier_score": 0.2},
        {"game_date": "2025-03-27", "home_team": "A", "away_team": "B", "brier_score": 0.2},
        {"game_date": "2025-03-28", "home_team": "A", "away_team": "B", "brier_score": 0.2},
        {"game_date": "2025-04-01", "home_team": "A", "away_team": "B", "brier_score": 0.2},
    ]
    filtered, n_excluded = filter_regular_season_games(rows)
    assert n_excluded == 2
    assert len(filtered) == 2
    for r in filtered:
        assert r["game_date"] >= "2025-03-28"


# ---------- 4 ----------
def test_elo_prob_equal_elos():
    assert abs(elo_prob(1500, 1500) - 0.5) < 1e-9


# ---------- 5 ----------
def test_elo_prob_home_advantage():
    assert elo_prob(1600, 1400) > 0.5


# ---------- 6 ----------
def test_initialize_elo_winner_above_base():
    win_rates = {"LAD": 0.617, "CWS": 0.253}
    elos = initialize_elo_from_win_rate(win_rates, base_elo=1500)
    assert elos["LAD"] > 1500


# ---------- 7 ----------
def test_initialize_elo_loser_below_base():
    win_rates = {"LAD": 0.617, "CWS": 0.253}
    elos = initialize_elo_from_win_rate(win_rates, base_elo=1500)
    assert elos["CWS"] < 1500


# ---------- 8 ----------
def test_check_2024_data_unavailable(tmp_path):
    result = check_2024_data_availability(data_dir=str(tmp_path))
    assert result["available"] is False
    assert result["blocking_reason"] is not None
    assert result["source"] is None


# ---------- 9 ----------
def test_repaired_model_source_contains_variant():
    rows = [
        {
            "game_date": "2025-04-01",
            "home_team": "LAD",
            "away_team": "SD",
            "model_prob": 0.55,
            "brier_score": 0.2025,
            "walk_forward_fold": 1,
        }
    ]
    repaired = run_elo_walk_forward_with_repair(rows, repair_mode="exclude_spring")
    assert "exclude_spring" in repaired[0]["model_source"]


# ---------- 10 ----------
def test_paper_only_preserved():
    rows = [
        {
            "game_date": "2025-04-01",
            "home_team": "LAD",
            "away_team": "SD",
            "model_prob": 0.55,
            "brier_score": 0.2025,
            "paper_only": True,
        }
    ]
    repaired = run_elo_walk_forward_with_repair(rows, repair_mode="exclude_spring")
    assert repaired[0].get("paper_only") is True


# ---------- 11 ----------
def test_exclude_spring_marks_excluded():
    rows = [
        {
            "game_date": "2025-03-20",
            "home_team": "LAD",
            "away_team": "SD",
            "model_prob": 0.55,
            "brier_score": 0.2025,
        },
        {
            "game_date": "2025-04-01",
            "home_team": "LAD",
            "away_team": "SD",
            "model_prob": 0.55,
            "brier_score": 0.2025,
        },
    ]
    repaired = run_elo_walk_forward_with_repair(rows, repair_mode="exclude_spring")
    spring_rows = [r for r in repaired if r["game_date"] == "2025-03-20"]
    regular_rows = [r for r in repaired if r["game_date"] == "2025-04-01"]
    assert spring_rows[0]["excluded"] is True
    assert regular_rows[0]["excluded"] is False


# ---------- 12 ----------
def test_no_prior_uses_base_elo():
    """prior_win_rates=None 且 repair_mode=exclude_spring，第一場應用 base_elo=1500"""
    rows = [
        {
            "game_date": "2025-04-01",
            "home_team": "NEWTEAM_X",
            "away_team": "NEWTEAM_Y",
            "model_prob": 0.5,
            "brier_score": 0.25,
        }
    ]
    repaired = run_elo_walk_forward_with_repair(
        rows, repair_mode="exclude_spring", prior_win_rates=None, base_elo=1500
    )
    # 兩隊都是新隊，應使用 1500
    assert repaired[0]["home_elo"] == 1500.0
    assert repaired[0]["away_elo"] == 1500.0


# ---------- 13 (bonus) ----------
def test_compare_elo_variants_returns_both_keys():
    rows = [
        {
            "game_date": "2025-04-01",
            "home_team": "LAD",
            "away_team": "SD",
            "model_prob": 0.6,
            "brier_score": 0.16,
        }
    ]
    result = compare_elo_variants(rows, rows)
    assert "baseline" in result
    assert "repaired" in result
