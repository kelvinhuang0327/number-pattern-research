"""
tests/test_actual_outcome_join.py
P7 — 至少 12 個測試覆蓋 OutcomeJoin 所有主要路徑
"""
import pytest
from wbc_backend.recommendation.actual_outcome_join import (
    derive_actual_home_win,
    derive_selected_side_win,
    normalize_team_name,
    build_join_key,
    join_outcomes_to_artifact,
)


# ── derive_actual_home_win ────────────────────────────────────────────────────

def test_home_score_greater_home_wins():
    assert derive_actual_home_win(5.0, 3.0) == 1


def test_away_score_greater_away_wins():
    assert derive_actual_home_win(2.0, 4.0) == 0


def test_tie_returns_none():
    assert derive_actual_home_win(3.0, 3.0) is None


def test_none_score_returns_none():
    assert derive_actual_home_win(None, 4.0) is None
    assert derive_actual_home_win(3.0, None) is None
    assert derive_actual_home_win(None, None) is None


# ── derive_selected_side_win ──────────────────────────────────────────────────

def test_side_home_win():
    assert derive_selected_side_win("home", 1) == 1


def test_side_home_lose():
    assert derive_selected_side_win("home", 0) == 0


def test_side_away_win():
    # away 下注，home 輸 → away 贏
    assert derive_selected_side_win("away", 0) == 1


def test_side_away_lose():
    # away 下注，home 贏 → away 輸
    assert derive_selected_side_win("away", 1) == 0


def test_side_none_actual_home_win_none():
    assert derive_selected_side_win("home", None) is None


# ── fallback join key ─────────────────────────────────────────────────────────

def test_fallback_key_structure():
    row = {"game_date": "2025-04-01", "home_team": "Chicago Cubs", "away_team": "Los Angeles Dodgers"}
    key = build_join_key(row, key_type="fallback")
    assert key is not None
    assert "2025-04-01" in key
    assert "chicago cubs" in key
    assert "los angeles dodgers" in key


def test_missing_field_returns_none():
    row = {"game_date": "2025-04-01", "home_team": "Chicago Cubs"}  # away_team 缺失
    key = build_join_key(row, key_type="fallback")
    assert key is None


# ── join_outcomes_to_artifact ─────────────────────────────────────────────────

def _make_artifact_row(game_id, date, home, away, side="home"):
    return {
        "game_id": game_id,
        "game_date": date,
        "home_team": home,
        "away_team": away,
        "side": side,
        "bet_side": side.upper() if side else "NO_BET",
        "stake_unit": 0.01,
        "edge": 0.05,
        "model_prob": 0.55,
        "implied_prob": 0.50,
    }


def _make_odds_row(date, home, away, home_score, away_score):
    return {
        "Date": date,
        "Home": home,
        "Away": away,
        "Home Score": home_score,
        "Away Score": away_score,
        "Status": "Final",
    }


def test_join_coverage_rate_correct():
    artifact = [
        _make_artifact_row("G1", "2025-04-01", "Chicago Cubs", "Los Angeles Dodgers"),
        _make_artifact_row("G2", "2025-04-02", "New York Yankees", "Boston Red Sox"),
    ]
    odds = [
        _make_odds_row("2025-04-01", "Chicago Cubs", "Los Angeles Dodgers", 5, 3),
        _make_odds_row("2025-04-02", "New York Yankees", "Boston Red Sox", 2, 4),
    ]
    enriched, summary = join_outcomes_to_artifact(artifact, odds)
    assert summary["join_coverage_rate"] == 1.0
    assert summary["joined_rows"] == 2


def test_no_match_when_date_differs():
    artifact = [_make_artifact_row("G1", "2025-04-01", "Chicago Cubs", "Los Angeles Dodgers")]
    odds = [_make_odds_row("2025-04-02", "Chicago Cubs", "Los Angeles Dodgers", 5, 3)]
    enriched, summary = join_outcomes_to_artifact(artifact, odds)
    assert summary["no_match_rows"] == 1
    assert enriched[0]["actual_home_win"] is None
    assert enriched[0]["outcome_join_status"] == "NO_MATCH"


def test_duplicate_key_counted():
    artifact = [_make_artifact_row("G1", "2025-04-01", "Chicago Cubs", "Los Angeles Dodgers")]
    # 兩筆相同 key 的 odds row
    odds = [
        _make_odds_row("2025-04-01", "Chicago Cubs", "Los Angeles Dodgers", 5, 3),
        _make_odds_row("2025-04-01", "Chicago Cubs", "Los Angeles Dodgers", 3, 5),
    ]
    enriched, summary = join_outcomes_to_artifact(artifact, odds)
    assert summary["duplicate_key_rows"] == 1


def test_paper_only_always_true():
    artifact = [_make_artifact_row("G1", "2025-04-01", "Chicago Cubs", "Los Angeles Dodgers")]
    odds = [_make_odds_row("2025-04-01", "Chicago Cubs", "Los Angeles Dodgers", 5, 3)]
    enriched, _ = join_outcomes_to_artifact(artifact, odds)
    assert enriched[0]["paper_only"] is True


def test_outcome_join_status_joined():
    artifact = [_make_artifact_row("G1", "2025-04-01", "Chicago Cubs", "Los Angeles Dodgers")]
    odds = [_make_odds_row("2025-04-01", "Chicago Cubs", "Los Angeles Dodgers", 5, 3)]
    enriched, _ = join_outcomes_to_artifact(artifact, odds)
    assert enriched[0]["outcome_join_status"] == "JOINED"
    assert enriched[0]["actual_home_win"] == 1


def test_missing_score_status():
    artifact = [_make_artifact_row("G1", "2025-04-01", "Chicago Cubs", "Los Angeles Dodgers")]
    odds = [_make_odds_row("2025-04-01", "Chicago Cubs", "Los Angeles Dodgers", None, None)]
    enriched, summary = join_outcomes_to_artifact(artifact, odds)
    assert enriched[0]["outcome_join_status"] == "MISSING_SCORE"
    assert summary["missing_outcome_rows"] == 1


def test_total_rows_matches_artifact():
    artifact = [_make_artifact_row(f"G{i}", "2025-04-01", "Chicago Cubs", "Los Angeles Dodgers") for i in range(5)]
    odds = []
    enriched, summary = join_outcomes_to_artifact(artifact, odds)
    assert summary["total_rows"] == 5
    assert len(enriched) == 5
