"""
tests/test_mlb_independent_features.py

P10: Tests for MlbIndependentFeatureRow contract.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from wbc_backend.prediction.mlb_independent_features import MlbIndependentFeatureRow


def _make_row(**kwargs) -> MlbIndependentFeatureRow:
    defaults = dict(
        game_id="2025-03-18_CHC_LAD",
        date="2025-03-18",
        home_team="Chicago Cubs",
        away_team="Los Angeles Dodgers",
        feature_version="p10_independent_features_v1",
        feature_source="p10_baseball_stats",
        leakage_safe=True,
    )
    defaults.update(kwargs)
    return MlbIndependentFeatureRow(**defaults)


class TestLeakageSafeInvariant:
    def test_leakage_safe_must_be_true(self):
        with pytest.raises(ValueError, match="leakage_safe"):
            _make_row(leakage_safe=False)

    def test_leakage_safe_true_is_valid(self):
        row = _make_row(leakage_safe=True)
        assert row.leakage_safe is True


class TestFeatureSourceInvariant:
    def test_market_source_rejected(self):
        with pytest.raises(ValueError, match="market"):
            _make_row(feature_source="market")

    def test_valid_source_accepted(self):
        row = _make_row(feature_source="p10_baseball_stats")
        assert row.feature_source == "p10_baseball_stats"


class TestFeatureVersionInvariant:
    def test_empty_feature_version_rejected(self):
        with pytest.raises(ValueError, match="feature_version"):
            _make_row(feature_version="")

    def test_valid_version_accepted(self):
        row = _make_row(feature_version="p10_independent_features_v1")
        assert row.feature_version == "p10_independent_features_v1"


class TestWinRateBounds:
    def test_home_win_rate_below_zero_rejected(self):
        with pytest.raises(ValueError, match="home_recent_win_rate"):
            _make_row(home_recent_win_rate=-0.01)

    def test_home_win_rate_above_one_rejected(self):
        with pytest.raises(ValueError, match="home_recent_win_rate"):
            _make_row(home_recent_win_rate=1.01)

    def test_away_win_rate_below_zero_rejected(self):
        with pytest.raises(ValueError, match="away_recent_win_rate"):
            _make_row(away_recent_win_rate=-0.5)

    def test_away_win_rate_above_one_rejected(self):
        with pytest.raises(ValueError, match="away_recent_win_rate"):
            _make_row(away_recent_win_rate=1.001)

    def test_valid_win_rates_accepted(self):
        row = _make_row(home_recent_win_rate=0.6, away_recent_win_rate=0.4)
        assert row.home_recent_win_rate == pytest.approx(0.6)
        assert row.away_recent_win_rate == pytest.approx(0.4)

    def test_zero_and_one_boundaries_accepted(self):
        row = _make_row(home_recent_win_rate=0.0, away_recent_win_rate=1.0)
        assert row.home_recent_win_rate == 0.0
        assert row.away_recent_win_rate == 1.0

    def test_none_win_rate_accepted(self):
        row = _make_row(home_recent_win_rate=None, away_recent_win_rate=None)
        assert row.home_recent_win_rate is None


class TestRestDaysBounds:
    def test_negative_home_rest_rejected(self):
        with pytest.raises(ValueError, match="home_rest_days"):
            _make_row(home_rest_days=-1.0)

    def test_negative_away_rest_rejected(self):
        with pytest.raises(ValueError, match="away_rest_days"):
            _make_row(away_rest_days=-0.5)

    def test_zero_rest_days_accepted(self):
        row = _make_row(home_rest_days=0.0, away_rest_days=0.0)
        assert row.home_rest_days == 0.0

    def test_positive_rest_days_accepted(self):
        row = _make_row(home_rest_days=3.0, away_rest_days=1.0)
        assert row.home_rest_days == 3.0
        assert row.away_rest_days == 1.0

    def test_none_rest_days_accepted(self):
        row = _make_row(home_rest_days=None, away_rest_days=None)
        assert row.home_rest_days is None


class TestToDict:
    def test_to_dict_returns_dict(self):
        row = _make_row()
        d = row.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_has_game_id(self):
        row = _make_row()
        assert row.to_dict()["game_id"] == "2025-03-18_CHC_LAD"

    def test_to_dict_datetime_is_string(self):
        row = _make_row()
        d = row.to_dict()
        assert isinstance(d["generated_at_utc"], str)

    def test_to_dict_json_serialisable(self):
        row = _make_row(home_recent_win_rate=0.5, away_recent_win_rate=0.4)
        d = row.to_dict()
        json_str = json.dumps(d)
        assert "game_id" in json_str

    def test_to_jsonl_line_is_string(self):
        row = _make_row()
        line = row.to_jsonl_line()
        assert isinstance(line, str)
        parsed = json.loads(line)
        assert parsed["game_id"] == "2025-03-18_CHC_LAD"


class TestOptionalFields:
    def test_all_optional_fields_none(self):
        row = _make_row()
        assert row.starter_era_delta is None
        assert row.bullpen_proxy_delta is None
        assert row.wind_kmh is None
        assert row.temp_c is None
        assert row.park_roof_type is None

    def test_all_optional_fields_set(self):
        row = _make_row(
            starter_era_delta=0.5,
            bullpen_proxy_delta=-0.2,
            wind_kmh=15.0,
            temp_c=20.0,
            park_roof_type="open",
        )
        assert row.starter_era_delta == pytest.approx(0.5)
        assert row.bullpen_proxy_delta == pytest.approx(-0.2)
        assert row.wind_kmh == pytest.approx(15.0)
        assert row.temp_c == pytest.approx(20.0)
        assert row.park_roof_type == "open"
