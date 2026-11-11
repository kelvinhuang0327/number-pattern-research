"""
tests/test_mlb_model_probability_contract.py

Unit tests for the MlbModelProbability dataclass contract.

P5: Validates prob range, sum-to-one invariant, probability_source enum,
and serialisation round-trips.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from wbc_backend.prediction.mlb_model_probability import (
    VALID_PROBABILITY_SOURCES,
    MlbModelProbability,
)


def _make_prob(**kwargs) -> MlbModelProbability:
    defaults: dict = {
        "game_id": "baseball:mlb:20250501:LAD:NYY",
        "game_date": "2025-05-01",
        "home_team": "LAD",
        "away_team": "NYY",
        "model_prob_home": 0.55,
        "model_prob_away": 0.45,
        "model_version": "v1-mlb-moneyline-trained",
        "probability_source": "calibrated_model",
        "generated_at_utc": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return MlbModelProbability(**defaults)


class TestMlbModelProbabilityContract:
    def test_valid_instance_created(self):
        p = _make_prob()
        assert p.model_prob_home == 0.55
        assert p.model_prob_away == 0.45

    def test_prob_home_below_zero_raises(self):
        with pytest.raises(ValueError, match="model_prob_home"):
            _make_prob(model_prob_home=-0.01, model_prob_away=0.01)

    def test_prob_home_above_one_raises(self):
        with pytest.raises(ValueError, match="model_prob_home"):
            _make_prob(model_prob_home=1.01, model_prob_away=-0.01)

    def test_prob_away_below_zero_raises(self):
        with pytest.raises(ValueError, match="model_prob_away"):
            _make_prob(model_prob_home=0.55, model_prob_away=-0.01)

    def test_prob_away_above_one_raises(self):
        with pytest.raises(ValueError, match="model_prob_away"):
            _make_prob(model_prob_home=0.55, model_prob_away=1.01)

    def test_sum_to_one_enforced(self):
        """Probabilities that sum to 1.02 (> 0.01 tolerance) must raise."""
        with pytest.raises(ValueError, match="sum"):
            _make_prob(model_prob_home=0.60, model_prob_away=0.60)

    def test_sum_slightly_off_ok(self):
        """Probabilities within 0.01 of 1.0 are accepted."""
        # 0.55 + 0.449 = 0.999, delta=0.001 → clearly within tolerance
        p = _make_prob(model_prob_home=0.55, model_prob_away=0.449)
        assert p.model_prob_home == 0.55

    def test_invalid_probability_source_raises(self):
        with pytest.raises(ValueError, match="probability_source"):
            _make_prob(probability_source="made_up_source")

    def test_all_valid_sources_accepted(self):
        for src in VALID_PROBABILITY_SOURCES:
            p = _make_prob(probability_source=src)
            assert p.probability_source == src

    def test_market_proxy_is_not_real_model(self):
        """market_proxy source must not be labelled as real_model."""
        p = _make_prob(probability_source="market_proxy")
        assert p.probability_source == "market_proxy"
        assert p.probability_source != "real_model"

    def test_to_dict_contains_all_fields(self):
        p = _make_prob()
        d = p.to_dict()
        assert "game_id" in d
        assert "model_prob_home" in d
        assert "probability_source" in d
        assert "model_version" in d
        assert "generated_at_utc" in d

    def test_to_jsonl_line_is_valid_json(self):
        p = _make_prob()
        line = p.to_jsonl_line()
        parsed = json.loads(line)
        assert parsed["model_prob_home"] == 0.55
        assert parsed["probability_source"] == "calibrated_model"

    def test_game_id_can_be_none(self):
        """game_id is optional (market proxy rows may not have it)."""
        p = _make_prob(game_id=None)
        assert p.game_id is None

    def test_source_trace_defaults_to_empty_dict(self):
        p = _make_prob()
        assert isinstance(p.source_trace, dict)
