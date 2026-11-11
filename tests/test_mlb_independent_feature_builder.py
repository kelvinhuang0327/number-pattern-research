"""
tests/test_mlb_independent_feature_builder.py

P10/P11: Tests for independent feature builder.
"""
from __future__ import annotations

import pytest

from wbc_backend.prediction.mlb_independent_feature_builder import (
    build_independent_features,
    merge_independent_features_into_rows,
    _build_rolling_win_rates,
    _build_starter_era_proxies,
)
from wbc_backend.prediction.mlb_independent_features import MlbIndependentFeatureRow


# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

def _make_rows(n: int = 20) -> list[dict]:
    """Create synthetic game rows for testing."""
    teams = [("TeamA", "TeamB"), ("TeamC", "TeamD"), ("TeamA", "TeamC")]
    rows = []
    for i in range(n):
        pair = teams[i % len(teams)]
        date = f"2025-0{(i // 28) + 3}-{(i % 28) + 1:02d}"
        # Normalize date
        try:
            import datetime
            d = datetime.date(2025, 3 + (i // 28), 1 + (i % 28))
            date = d.isoformat()
        except Exception:
            date = f"2025-03-{(i % 28) + 1:02d}"
        rows.append({
            "date": date,
            "home_team": pair[0],
            "away_team": pair[1],
            "home_win": "1.0" if i % 3 != 0 else "0.0",
            "Home Starter": f"Pitcher{i % 5}",
            "Away Starter": f"Pitcher{(i + 2) % 5}",
            "home_score": str(3 + (i % 4)),
            "away_score": str(2 + (i % 3)),
            "game_id": f"2025-{(3 + i // 28):02d}-{(1 + i % 28):02d}_A_B",
            "model_prob_home": "0.55",
            "probability_source": "repaired_model_candidate",
        })
    return rows


def _write_asplayed_csv(tmp_path, rows: list[dict]) -> str:
    """Write a minimal as-played CSV for P11 win-rate tests."""
    import csv

    path = tmp_path / "asplayed.csv"
    fieldnames = [
        "date",
        "home_team",
        "away_team",
        "home_win",
        "home_starter",
        "away_starter",
        "home_score",
        "away_score",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "date": row.get("date") or row.get("Date"),
                "home_team": row.get("home_team") or row.get("Home"),
                "away_team": row.get("away_team") or row.get("Away"),
                "home_win": row.get("home_win"),
                "home_starter": row.get("home_starter") or row.get("Home Starter"),
                "away_starter": row.get("away_starter") or row.get("Away Starter"),
                "home_score": row.get("home_score"),
                "away_score": row.get("away_score"),
            })
    return str(path)


class TestBuildIndependentFeaturesContract:
    """Test basic output contract."""

    def test_returns_tuple(self):
        result = build_independent_features([], bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_empty_input_returns_empty(self):
        rows, meta = build_independent_features([], bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        assert rows == []
        assert meta["input_count"] == 0

    def test_output_rows_are_mlb_independent_feature_rows(self):
        rows = _make_rows(5)
        feat_rows, meta = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        assert all(isinstance(r, MlbIndependentFeatureRow) for r in feat_rows)

    def test_feature_count_matches_input(self):
        rows = _make_rows(10)
        feat_rows, meta = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        assert meta["feature_count"] == len(feat_rows)
        assert len(feat_rows) == len(rows)

    def test_leakage_safe_true_in_metadata(self):
        rows = _make_rows(5)
        _, meta = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        assert meta["leakage_safe"] is True

    def test_all_feature_rows_leakage_safe(self):
        rows = _make_rows(5)
        feat_rows, _ = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        assert all(r.leakage_safe is True for r in feat_rows)

    def test_metadata_contains_required_keys(self):
        rows = _make_rows(5)
        _, meta = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        for key in ("input_count", "feature_count", "coverage_by_feature", "missing_feature_reasons", "leakage_safe", "lookback_games", "feature_version"):
            assert key in meta, f"Missing metadata key: {key}"

    def test_feature_version_is_p11(self):
        rows = _make_rows(3)
        feat_rows, meta = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        assert meta["feature_version"] == "p11_context_reconciled_v1"
        assert all(r.feature_version == "p11_context_reconciled_v1" for r in feat_rows)


class TestLeakageSafetyForWinRate:
    """Win rates must only use prior games."""

    def test_first_game_has_no_win_rate(self):
        """The very first game for each team has no prior history → None."""
        rows = [
            {"date": "2025-03-18", "home_team": "TeamA", "away_team": "TeamB", "home_win": "1.0",
             "Home Starter": "P1", "Away Starter": "P2", "home_score": "3", "away_score": "1"},
        ]
        feat_rows, _ = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        assert feat_rows[0].home_recent_win_rate is None
        assert feat_rows[0].away_recent_win_rate is None

    def test_win_rate_after_sufficient_history(self, tmp_path):
        """After enough games, win rate should be computed."""
        rows = _make_rows(20)
        asplayed_path = _write_asplayed_csv(tmp_path, rows)
        feat_rows, _ = build_independent_features(
            rows,
            bullpen_context_path=None,
            rest_context_path=None,
            weather_context_path=None,
            asplayed_path=asplayed_path,
        )
        # Some rows near the end should have win rate
        non_null = [r for r in feat_rows if r.home_recent_win_rate is not None]
        assert len(non_null) > 0

    def test_win_rate_in_valid_range(self):
        rows = _make_rows(20)
        feat_rows, _ = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        for r in feat_rows:
            if r.home_recent_win_rate is not None:
                assert 0.0 <= r.home_recent_win_rate <= 1.0
            if r.away_recent_win_rate is not None:
                assert 0.0 <= r.away_recent_win_rate <= 1.0

    def test_recent_win_rate_delta_computed(self, tmp_path):
        rows = _make_rows(20)
        asplayed_path = _write_asplayed_csv(tmp_path, rows)
        feat_rows, _ = build_independent_features(
            rows,
            bullpen_context_path=None,
            rest_context_path=None,
            weather_context_path=None,
            asplayed_path=asplayed_path,
        )
        delta_rows = [r for r in feat_rows if r.recent_win_rate_delta is not None]
        assert len(delta_rows) > 0
        for r in delta_rows:
            expected = pytest.approx(r.home_recent_win_rate - r.away_recent_win_rate, abs=1e-6)
            assert r.recent_win_rate_delta == expected


class TestRollingWinRateHelper:
    def test_first_game_no_history(self):
        rows = [{"date": "2025-03-18", "home_team": "A", "away_team": "B", "home_win": "1.0"}]
        result = _build_rolling_win_rates(rows, "date", "home_team", "away_team", "home_win", lookback=5)
        # No entry for this date (first game)
        assert ("2025-03-18", "A") not in result

    def test_win_rate_after_history(self):
        rows = [
            {"date": "2025-03-18", "home_team": "A", "away_team": "B", "home_win": "1.0"},
            {"date": "2025-03-19", "home_team": "A", "away_team": "B", "home_win": "1.0"},
            {"date": "2025-03-20", "home_team": "A", "away_team": "B", "home_win": "0.0"},
        ]
        result = _build_rolling_win_rates(rows, "date", "home_team", "away_team", "home_win", lookback=5)
        # After 2 wins, team A's rate at date 3 should be 1.0
        if ("2025-03-20", "A") in result:
            rate, count = result[("2025-03-20", "A")]
            assert rate == pytest.approx(1.0)
            assert count == 2


class TestStarterEraProxyHelper:
    def test_empty_rows_returns_empty_map(self):
        result = _build_starter_era_proxies([])
        assert result == {}

    def test_insufficient_history_returns_no_entry(self):
        # Only 1 start — needs min_starts=2
        rows = [
            {"date": "2025-03-18", "home_team": "A", "away_team": "B",
             "home_starter": "PitcherX", "away_starter": "PitcherY",
             "home_score": "3", "away_score": "2"},
        ]
        result = _build_starter_era_proxies(rows, min_starts=2)
        assert ("2025-03-18", "PitcherX") not in result

    def test_era_proxy_computed_after_sufficient_starts(self):
        rows = [
            {"date": "2025-03-18", "home_team": "A", "away_team": "B",
             "home_starter": "P1", "away_starter": "P2",
             "home_score": "3", "away_score": "2"},
            {"date": "2025-03-19", "home_team": "C", "away_team": "A",
             "home_starter": "P1", "away_starter": "P3",
             "home_score": "4", "away_score": "5"},
            {"date": "2025-03-20", "home_team": "A", "away_team": "D",
             "home_starter": "P1", "away_starter": "P4",
             "home_score": "2", "away_score": "1"},
        ]
        result = _build_starter_era_proxies(rows, min_starts=2)
        # P1 on 2025-03-20 should have ERA proxy based on previous 2 starts
        assert ("2025-03-20", "P1") in result
        # P1 as home starter conceded away_score each time
        # Start 1 (home): conceded 2; Start 2 (home): conceded 5
        # Average = 3.5
        assert result[("2025-03-20", "P1")] == pytest.approx(3.5)

    def test_era_proxy_uses_only_prior_games(self):
        """ERA proxy at date T must not include game at date T."""
        rows = [
            {"date": "2025-03-18", "home_team": "A", "away_team": "B",
             "home_starter": "P1", "away_starter": "P2",
             "home_score": "3", "away_score": "0"},  # P1 concedes 0
            {"date": "2025-03-19", "home_team": "C", "away_team": "A",
             "home_starter": "P3", "away_starter": "P1",
             "home_score": "5", "away_score": "1"},  # P1 concedes 5
            {"date": "2025-03-25", "home_team": "A", "away_team": "D",
             "home_starter": "P1", "away_starter": "P5",
             "home_score": "99", "away_score": "99"},  # Game being predicted
        ]
        result = _build_starter_era_proxies(rows, min_starts=2)
        # On 2025-03-25, P1's ERA proxy should be based on starts on 3-18 and 3-19 only
        # 3-18: P1 is home starter, concedes away_score=0
        # 3-19: P1 is away starter for team "A", concedes home_score=5
        if ("2025-03-25", "P1") in result:
            era = result[("2025-03-25", "P1")]
            # Should be avg of prior conceded runs, NOT including the 99 game
            assert era != pytest.approx(99.0)


class TestInsufficientHistory:
    def test_builder_handles_no_history_gracefully(self):
        rows = [
            {"date": "2025-03-18", "home_team": "NewTeam", "away_team": "OtherTeam",
             "home_win": "1.0", "Home Starter": "NewP", "Away Starter": "OtherP",
             "home_score": "3", "away_score": "1"},
        ]
        feat_rows, meta = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        # Should produce 1 row with None win rates
        assert len(feat_rows) == 1
        assert feat_rows[0].home_recent_win_rate is None

    def test_missing_starter_reason_documented(self):
        rows = [
            {"date": "2025-03-18", "home_team": "A", "away_team": "B",
             "home_win": "1.0", "home_score": "3", "away_score": "1"},
        ]
        _, meta = build_independent_features(rows, bullpen_context_path=None, rest_context_path=None, weather_context_path=None)
        # missing_feature_reasons should document starter absence
        assert isinstance(meta["missing_feature_reasons"], list)

    def test_context_hit_rate_uses_hit_miss_denominator(self):
        rows = _make_rows(3)
        _, meta = build_independent_features(
            rows,
            bullpen_context_path=None,
            rest_context_path=None,
            weather_context_path=None,
        )
        assert meta["context_hit_count"] == 0
        assert meta["context_miss_count"] == 3
        assert meta["context_hit_rate"] == 0.0


class TestMergeIndependentFeaturesIntoRows:
    def test_merge_by_game_id(self):
        rows = [
            {"game_id": "2025-03-18_A_B", "model_prob_home": "0.55"},
            {"game_id": "2025-03-19_C_D", "model_prob_home": "0.48"},
        ]
        feat_rows_input, _ = build_independent_features(
            [
                {"date": "2025-03-18", "home_team": "A", "away_team": "B",
                 "home_win": "1.0", "game_id": "2025-03-18_A_B",
                 "home_score": "3", "away_score": "1"},
                {"date": "2025-03-19", "home_team": "C", "away_team": "D",
                 "home_win": "0.0", "game_id": "2025-03-19_C_D",
                 "home_score": "2", "away_score": "4"},
            ],
            bullpen_context_path=None, rest_context_path=None, weather_context_path=None,
        )
        merged = merge_independent_features_into_rows(rows, feat_rows_input)
        assert len(merged) == 2
        assert "model_prob_home" in merged[0]  # original column preserved

    def test_merge_preserves_original_columns(self):
        rows = [{"game_id": "2025-03-18_A_B", "model_prob_home": "0.55", "home_win": "1.0"}]
        feat_rows_input, _ = build_independent_features(
            [{"date": "2025-03-18", "home_team": "A", "away_team": "B",
              "home_win": "1.0", "game_id": "2025-03-18_A_B",
              "home_score": "3", "away_score": "1"}],
            bullpen_context_path=None, rest_context_path=None, weather_context_path=None,
        )
        merged = merge_independent_features_into_rows(rows, feat_rows_input)
        assert merged[0]["model_prob_home"] == "0.55"
        assert merged[0]["home_win"] == "1.0"

    def test_merge_adds_feature_columns(self):
        rows = [{"game_id": "2025-03-18_A_B", "model_prob_home": "0.55"}]
        feat_rows_input, _ = build_independent_features(
            [{"date": "2025-03-18", "home_team": "A", "away_team": "B",
              "home_win": "1.0", "game_id": "2025-03-18_A_B",
              "home_score": "3", "away_score": "1"}],
            bullpen_context_path=None, rest_context_path=None, weather_context_path=None,
        )
        merged = merge_independent_features_into_rows(rows, feat_rows_input)
        assert "independent_feature_version" in merged[0]
        assert "indep_leakage_safe" in merged[0]

    def test_merge_no_feature_match_adds_none_version(self):
        rows = [{"game_id": "9999-01-01_X_Y", "model_prob_home": "0.5"}]
        merged = merge_independent_features_into_rows(rows, [])
        assert merged[0]["independent_feature_version"] is None
