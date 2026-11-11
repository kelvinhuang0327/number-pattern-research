"""
tests/test_p39f_p38a_bridge_enrichment.py

P39F unit tests for enrich_p38a_with_identity_bridge.py

All tests use synthetic fixture DataFrames — no raw data files required.

Acceptance marker: P39F_BRIDGE_ENRICHMENT_TESTS_PASS_20260515
"""

from __future__ import annotations

import pytest
import pandas as pd

from scripts.enrich_p38a_with_identity_bridge import (
    BRIDGE_ENRICHMENT_MARKER,
    PAPER_ONLY,
    SCRIPT_VERSION,
    assert_no_odds_columns,
    enrich_p38a_with_bridge,
    summarize_bridge_enrichment,
    validate_bridge_schema,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_p38a(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a minimal synthetic P38A OOF DataFrame."""
    if rows is None:
        rows = [
            {"game_id": "NYA-20240415-0", "fold_id": 0, "p_oof": 0.55, "model_version": "p38a_v1",
             "source_prediction_ref": "fold0", "generated_without_y_true": True},
            {"game_id": "BOS-20240416-0", "fold_id": 1, "p_oof": 0.42, "model_version": "p38a_v1",
             "source_prediction_ref": "fold1", "generated_without_y_true": True},
            {"game_id": "CHA-20240417-0", "fold_id": 2, "p_oof": 0.61, "model_version": "p38a_v1",
             "source_prediction_ref": "fold2", "generated_without_y_true": True},
        ]
    return pd.DataFrame(rows)


def _make_bridge(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a minimal synthetic identity bridge DataFrame."""
    if rows is None:
        rows = [
            {"game_id": "NYA-20240415-0", "game_date": "2024-04-15", "home_team": "NYA", "away_team": "BAL",
             "season": 2024, "source_name": "Retrosheet", "source_row_number": 1,
             "away_score": 3, "home_score": 5, "y_true_home_win": 1},
            {"game_id": "BOS-20240416-0", "game_date": "2024-04-16", "home_team": "BOS", "away_team": "TBA",
             "season": 2024, "source_name": "Retrosheet", "source_row_number": 2,
             "away_score": 2, "home_score": 4, "y_true_home_win": 1},
            {"game_id": "CHA-20240417-0", "game_date": "2024-04-17", "home_team": "CHA", "away_team": "KCA",
             "season": 2024, "source_name": "Retrosheet", "source_row_number": 3,
             "away_score": 7, "home_score": 1, "y_true_home_win": 0},
        ]
    return pd.DataFrame(rows)


# ── Test 1: Enriches away_team by game_id ─────────────────────────────────────


def test_enriches_away_team_by_game_id() -> None:
    p38a = _make_p38a()
    bridge = _make_bridge()
    result = enrich_p38a_with_bridge(p38a, bridge)
    assert result.loc[result.game_id == "NYA-20240415-0", "away_team"].iloc[0] == "BAL"
    assert result.loc[result.game_id == "CHA-20240417-0", "away_team"].iloc[0] == "KCA"


# ── Test 2: Preserves p_oof unchanged ────────────────────────────────────────


def test_preserves_p_oof_unchanged() -> None:
    p38a = _make_p38a()
    bridge = _make_bridge()
    result = enrich_p38a_with_bridge(p38a, bridge)
    for _, row in p38a.iterrows():
        orig = row["p_oof"]
        enriched_val = result.loc[result.game_id == row["game_id"], "p_oof"].iloc[0]
        assert enriched_val == pytest.approx(orig, abs=1e-10), (
            f"p_oof changed for {row['game_id']}: {orig} → {enriched_val}"
        )


# ── Test 3: Preserves fold_id and model_version ───────────────────────────────


def test_preserves_fold_id_and_model_version() -> None:
    p38a = _make_p38a()
    bridge = _make_bridge()
    result = enrich_p38a_with_bridge(p38a, bridge)
    assert list(result["fold_id"]) == list(p38a["fold_id"])
    assert list(result["model_version"]) == list(p38a["model_version"])


# ── Test 4: Reports matched rows ──────────────────────────────────────────────


def test_reports_matched_rows(capsys: pytest.CaptureFixture) -> None:
    p38a = _make_p38a()
    bridge = _make_bridge()
    result = enrich_p38a_with_bridge(p38a, bridge)
    summary = summarize_bridge_enrichment(result)
    assert summary["matched_rows"] == 3
    assert summary["match_rate"] == pytest.approx(1.0, abs=1e-6)


# ── Test 5: Reports unmatched rows ────────────────────────────────────────────


def test_reports_unmatched_rows(capsys: pytest.CaptureFixture) -> None:
    # One P38A row with no bridge entry
    p38a = _make_p38a([
        {"game_id": "NYA-20240415-0", "fold_id": 0, "p_oof": 0.55, "model_version": "p38a_v1",
         "source_prediction_ref": "fold0", "generated_without_y_true": True},
        {"game_id": "ZZZ-20240999-0", "fold_id": 1, "p_oof": 0.5, "model_version": "p38a_v1",
         "source_prediction_ref": "fold1", "generated_without_y_true": True},  # no bridge match
    ])
    bridge = _make_bridge()
    result = enrich_p38a_with_bridge(p38a, bridge)
    summary = summarize_bridge_enrichment(result)
    assert summary["matched_rows"] == 1
    assert summary["unmatched_rows"] == 1
    unmatched_row = result[result.game_id == "ZZZ-20240999-0"]
    assert unmatched_row["bridge_match_status"].iloc[0] == "UNMATCHED"
    assert pd.isna(unmatched_row["away_team"].iloc[0])


# ── Test 6: Rejects duplicate bridge game_id ──────────────────────────────────


def test_rejects_duplicate_bridge_game_id() -> None:
    bridge_rows = [
        {"game_id": "NYA-20240415-0", "game_date": "2024-04-15", "home_team": "NYA", "away_team": "BAL",
         "season": 2024, "source_name": "Retrosheet", "source_row_number": 1,
         "away_score": 3, "home_score": 5, "y_true_home_win": 1},
        {"game_id": "NYA-20240415-0", "game_date": "2024-04-15", "home_team": "NYA", "away_team": "TBA",  # dup!
         "season": 2024, "source_name": "Retrosheet", "source_row_number": 2,
         "away_score": 2, "home_score": 4, "y_true_home_win": 1},
    ]
    bridge = pd.DataFrame(bridge_rows)
    p38a = _make_p38a()
    with pytest.raises(ValueError, match="duplicate game_id"):
        enrich_p38a_with_bridge(p38a, bridge)


# ── Test 7: Flags missing away_team ───────────────────────────────────────────


def test_rejects_bridge_with_missing_away_team() -> None:
    bridge = _make_bridge()
    bridge.loc[0, "away_team"] = None  # introduce null
    p38a = _make_p38a()
    with pytest.raises(ValueError, match="missing away_team"):
        enrich_p38a_with_bridge(p38a, bridge)


# ── Test 8: Rejects odds columns in p38a input ────────────────────────────────


def test_rejects_odds_columns_in_p38a() -> None:
    p38a = _make_p38a()
    p38a["moneyline"] = -150  # forbidden
    bridge = _make_bridge()
    with pytest.raises(ValueError, match="[Oo]dds columns"):
        enrich_p38a_with_bridge(p38a, bridge)


# ── Test 9: Deterministic output ──────────────────────────────────────────────


def test_deterministic_output_for_same_inputs() -> None:
    p38a = _make_p38a()
    bridge = _make_bridge()
    result1 = enrich_p38a_with_bridge(p38a, bridge)
    result2 = enrich_p38a_with_bridge(p38a, bridge)
    s1 = summarize_bridge_enrichment(result1)
    s2 = summarize_bridge_enrichment(result2)
    assert s1["deterministic_hash"] == s2["deterministic_hash"]


# ── Test 10: Handles doubleheader-like game_id variants ──────────────────────


def test_handles_doubleheader_game_id_variants() -> None:
    """Game-1 of a doubleheader (-0) and game-2 (-1) should be matched independently."""
    p38a_rows = [
        {"game_id": "NYA-20240415-0", "fold_id": 0, "p_oof": 0.55, "model_version": "p38a_v1",
         "source_prediction_ref": "fold0", "generated_without_y_true": True},
        {"game_id": "NYA-20240415-1", "fold_id": 1, "p_oof": 0.48, "model_version": "p38a_v1",
         "source_prediction_ref": "fold1", "generated_without_y_true": True},
    ]
    bridge_rows = [
        {"game_id": "NYA-20240415-0", "game_date": "2024-04-15", "home_team": "NYA", "away_team": "BAL",
         "season": 2024, "source_name": "Retrosheet", "source_row_number": 1,
         "away_score": 3, "home_score": 5, "y_true_home_win": 1},
        {"game_id": "NYA-20240415-1", "game_date": "2024-04-15", "home_team": "NYA", "away_team": "BAL",
         "season": 2024, "source_name": "Retrosheet", "source_row_number": 2,
         "away_score": 1, "home_score": 2, "y_true_home_win": 1},
    ]
    p38a = pd.DataFrame(p38a_rows)
    bridge = pd.DataFrame(bridge_rows)
    result = enrich_p38a_with_bridge(p38a, bridge)
    assert result.loc[result.game_id == "NYA-20240415-0", "away_team"].iloc[0] == "BAL"
    assert result.loc[result.game_id == "NYA-20240415-1", "away_team"].iloc[0] == "BAL"
    assert (result["bridge_match_status"] == "MATCHED").all()


# ── Test 11: bridge_match_status column present ───────────────────────────────


def test_bridge_match_status_column_present() -> None:
    p38a = _make_p38a()
    bridge = _make_bridge()
    result = enrich_p38a_with_bridge(p38a, bridge)
    assert "bridge_match_status" in result.columns
    assert set(result["bridge_match_status"].unique()).issubset({"MATCHED", "UNMATCHED"})


# ── Test 12: All original P38A columns preserved ─────────────────────────────


def test_all_original_p38a_columns_preserved() -> None:
    p38a = _make_p38a()
    bridge = _make_bridge()
    result = enrich_p38a_with_bridge(p38a, bridge)
    for col in p38a.columns:
        assert col in result.columns, f"Column '{col}' dropped from enriched output"


# ── Test 13: Row count preserved (left join) ──────────────────────────────────


def test_row_count_preserved_left_join() -> None:
    p38a = _make_p38a()
    bridge = _make_bridge()
    result = enrich_p38a_with_bridge(p38a, bridge)
    # Left join: all P38A rows preserved regardless of bridge match
    assert len(result) == len(p38a)


# ── Test 14: validate_bridge_schema raises on missing columns ────────────────


def test_validate_bridge_schema_raises_on_missing_columns() -> None:
    incomplete = pd.DataFrame({"game_id": ["NYA-20240415-0"], "game_date": ["2024-04-15"]})
    with pytest.raises(ValueError, match="missing required columns"):
        validate_bridge_schema(incomplete)


# ── Test 15: assert_no_odds_columns raises correctly ─────────────────────────


def test_assert_no_odds_columns_raises() -> None:
    df = pd.DataFrame({"game_id": ["X"], "clv": [0.05]})
    with pytest.raises(ValueError, match="[Oo]dds columns"):
        assert_no_odds_columns(df, "test_df")


# ── Test 16: Acceptance marker ────────────────────────────────────────────────


def test_acceptance_marker() -> None:
    assert BRIDGE_ENRICHMENT_MARKER == "P39F_P38A_BRIDGE_ENRICHMENT_UTILITY_READY_20260515"
    assert PAPER_ONLY is True
    assert SCRIPT_VERSION == "p39f_p38a_bridge_enrichment_v1"
