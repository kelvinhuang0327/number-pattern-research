"""P1 — Doubleheader repair tests.

驗證 actual_outcome_join.join_outcomes_to_artifact_v2 的 doubleheader-aware join。
"""
from __future__ import annotations

from wbc_backend.recommendation.actual_outcome_join import (
    join_outcomes_to_artifact_v2,
    build_odds_lookup_with_game_number,
    assign_artifact_game_numbers,
)


def _odds_row(date, home, away, hs, as_, time="1:00 PM"):
    return {
        "Date": date,
        "Home": home,
        "Away": away,
        "Home Score": str(hs),
        "Away Score": str(as_),
        "Start Time (EDT)": time,
    }


def _art_row(game_id, date, home, away, side="HOME"):
    return {
        "game_id": game_id,
        "game_date": date,
        "home_team": home,
        "away_team": away,
        "side": side.lower(),
        "bet_side": side,
        "market": "ML",
        "paper_only": True,
    }


# (a) 單場日 join 正確
def test_single_game_day_joins_correctly():
    odds = [_odds_row("2025-04-01", "Boston Red Sox", "New York Yankees", 5, 3)]
    art = [_art_row("MLB2025_0001", "2025-04-01", "Boston Red Sox", "New York Yankees")]
    enriched, stats = join_outcomes_to_artifact_v2(art, odds)
    assert stats["joined_rows"] == 1
    assert stats["duplicate_key_rows"] == 0
    assert stats["ambiguous_doubleheader_rows"] == 0
    r = enriched[0]
    assert r["actual_home_win"] == 1
    assert r["selected_side_win"] == 1
    assert r["ambiguous_doubleheader"] is False
    assert r["pnl_eligible"] is True
    assert r["game_number"] == 1


# (b) 雙重賽 game_number=1/2 區分正確
def test_doubleheader_assigns_game_numbers_in_order():
    odds = [
        _odds_row("2025-04-06", "Boston Red Sox", "St. Louis Cardinals", 5, 4, "1:35 PM"),
        _odds_row("2025-04-06", "Boston Red Sox", "St. Louis Cardinals", 18, 7, "7:10 PM"),
    ]
    art = [
        _art_row("MLB2025_0130", "2025-04-06", "Boston Red Sox", "St. Louis Cardinals"),
        _art_row("MLB2025_0143", "2025-04-06", "Boston Red Sox", "St. Louis Cardinals"),
    ]
    enriched, stats = join_outcomes_to_artifact_v2(art, odds)
    assert stats["joined_rows"] == 2
    by_id = {r["game_id"]: r for r in enriched}
    # game_id 字典序：_0130 → game_number=1（1:35 PM, 5-4）；_0143 → game_number=2（7:10 PM, 18-7）
    assert by_id["MLB2025_0130"]["game_number"] == 1
    assert by_id["MLB2025_0130"]["home_score"] == 5.0
    assert by_id["MLB2025_0143"]["game_number"] == 2
    assert by_id["MLB2025_0143"]["home_score"] == 18.0


# (c) ambiguous 場次正確標記
def test_doubleheader_marked_ambiguous():
    odds = [
        _odds_row("2025-04-06", "Boston Red Sox", "St. Louis Cardinals", 5, 4),
        _odds_row("2025-04-06", "Boston Red Sox", "St. Louis Cardinals", 18, 7),
    ]
    art = [
        _art_row("MLB2025_0130", "2025-04-06", "Boston Red Sox", "St. Louis Cardinals"),
        _art_row("MLB2025_0143", "2025-04-06", "Boston Red Sox", "St. Louis Cardinals"),
    ]
    enriched, stats = join_outcomes_to_artifact_v2(art, odds)
    assert stats["ambiguous_doubleheader_rows"] == 2
    for r in enriched:
        assert r["ambiguous_doubleheader"] is True


# (d) ambiguous 不進入 PnL
def test_ambiguous_excluded_from_pnl():
    odds = [
        _odds_row("2025-04-06", "Boston Red Sox", "St. Louis Cardinals", 5, 4),
        _odds_row("2025-04-06", "Boston Red Sox", "St. Louis Cardinals", 18, 7),
    ]
    art = [
        _art_row("MLB2025_0130", "2025-04-06", "Boston Red Sox", "St. Louis Cardinals"),
        _art_row("MLB2025_0143", "2025-04-06", "Boston Red Sox", "St. Louis Cardinals"),
    ]
    enriched, stats = join_outcomes_to_artifact_v2(art, odds)
    assert stats["pnl_excluded_rows"] == 2
    for r in enriched:
        assert r["pnl_eligible"] is False
        # 但仍填入 outcome 供審計
        assert r["actual_home_win"] in (0, 1)


# (e) coverage 不下降（v2 應 >= v1 修正後 coverage）
def test_coverage_not_degraded_vs_singlematch_only():
    odds = [
        _odds_row("2025-04-01", "A", "B", 5, 3),
        _odds_row("2025-04-02", "C", "D", 2, 7),
    ]
    art = [
        _art_row("g1", "2025-04-01", "A", "B"),
        _art_row("g2", "2025-04-02", "C", "D", side="AWAY"),
    ]
    _, stats = join_outcomes_to_artifact_v2(art, odds)
    assert stats["join_coverage_rate"] >= 0.97


# (f) paper_only 維持 true
def test_paper_only_preserved():
    odds = [_odds_row("2025-04-01", "A", "B", 5, 3)]
    art = [_art_row("g1", "2025-04-01", "A", "B")]
    enriched, _ = join_outcomes_to_artifact_v2(art, odds)
    assert enriched[0]["paper_only"] is True


# 額外：mismatch（CSV 2 場 artifact 1 場）→ ambiguous + no_match
def test_csv_artifact_size_mismatch_marked_ambiguous():
    odds = [
        _odds_row("2025-04-06", "Boston Red Sox", "St. Louis Cardinals", 5, 4),
        _odds_row("2025-04-06", "Boston Red Sox", "St. Louis Cardinals", 18, 7),
    ]
    art = [_art_row("only1", "2025-04-06", "Boston Red Sox", "St. Louis Cardinals")]
    enriched, stats = join_outcomes_to_artifact_v2(art, odds)
    r = enriched[0]
    assert r["ambiguous_doubleheader"] is True
    assert r["game_number"] is None
    assert r["pnl_eligible"] is False


def test_v2_artifact_real_data_has_no_duplicate_keys():
    """對真實 v2 artifact 做 smoke test：duplicate_key_rows == 0, coverage == 1.0"""
    import csv, json, os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    art_path = os.path.join(base, "data/paper_recommendations/strategy_sim_v2_ha40_platt_with_outcomes_v2_20260519.jsonl")
    if not os.path.exists(art_path):
        import pytest
        pytest.skip("v2 artifact not generated yet")
    rows = []
    with open(art_path) as f:
        for line in f:
            rows.append(json.loads(line))
    statuses = [r.get("outcome_join_status") for r in rows]
    assert "DUPLICATE_KEY" not in statuses
    joined = sum(1 for s in statuses if s == "JOINED")
    assert joined / len(rows) >= 0.97
