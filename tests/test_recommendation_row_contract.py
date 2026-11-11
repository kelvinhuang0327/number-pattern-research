"""Tests for MlbTslRecommendationRow dataclass contract."""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

import pytest

from wbc_backend.recommendation.recommendation_row import (
    MlbTslRecommendationRow,
    VALID_GATE_STATUSES,
)

# ── Shared fixture ─────────────────────────────────────────────────────────────

def _make_row(**overrides) -> MlbTslRecommendationRow:
    defaults = dict(
        game_id="2026-05-11-LAA-CLE-824441",
        game_start_utc=datetime(2026, 5, 11, 22, 10, 0, tzinfo=timezone.utc),
        model_prob_home=0.535,
        model_prob_away=0.465,
        model_ensemble_version="v1-paper",
        tsl_market="moneyline",
        tsl_line=None,
        tsl_side="home",
        tsl_decimal_odds=1.90,
        edge_pct=0.008,
        kelly_fraction=0.01,
        stake_units_paper=1.0,
        gate_status="BLOCKED_PAPER_ONLY",
        gate_reasons=["MLB P38 gate not cleared"],
        paper_only=True,
        generated_at_utc=datetime(2026, 5, 11, 14, 0, 0, tzinfo=timezone.utc),
        source_trace={"mlb": "statsapi.mlb.com"},
    )
    defaults.update(overrides)
    return MlbTslRecommendationRow(**defaults)


# ── Field presence ─────────────────────────────────────────────────────────────

class TestFieldPresence:
    REQUIRED_FIELDS = [
        "game_id",
        "game_start_utc",
        "model_prob_home",
        "model_prob_away",
        "model_ensemble_version",
        "tsl_market",
        "tsl_line",
        "tsl_side",
        "tsl_decimal_odds",
        "edge_pct",
        "kelly_fraction",
        "stake_units_paper",
        "gate_status",
        "gate_reasons",
        "paper_only",
        "generated_at_utc",
        "source_trace",
    ]

    def test_all_required_fields_exist(self):
        row = _make_row()
        field_names = {f.name for f in dataclasses.fields(row)}
        for name in self.REQUIRED_FIELDS:
            assert name in field_names, f"Missing required field: {name}"


# ── Defaults ───────────────────────────────────────────────────────────────────

class TestDefaults:
    def test_paper_only_default_is_true(self):
        row = _make_row()
        assert row.paper_only is True

    def test_paper_only_cannot_be_false(self):
        with pytest.raises(ValueError, match="paper_only must be True"):
            _make_row(paper_only=False)

    def test_gate_reasons_defaults_empty_list(self):
        # Create without gate_reasons to test default
        row = MlbTslRecommendationRow(
            game_id="TEST",
            game_start_utc=datetime(2026, 5, 11, tzinfo=timezone.utc),
            model_prob_home=0.5,
            model_prob_away=0.5,
            model_ensemble_version="v1",
            tsl_market="moneyline",
            tsl_line=None,
            tsl_side="home",
            tsl_decimal_odds=2.0,
            edge_pct=0.0,
            kelly_fraction=0.0,
            stake_units_paper=0.0,
            gate_status="BLOCKED_PAPER_ONLY",
            generated_at_utc=datetime(2026, 5, 11, tzinfo=timezone.utc),
        )
        assert row.gate_reasons == []

    def test_source_trace_defaults_empty_dict(self):
        row = MlbTslRecommendationRow(
            game_id="TEST",
            game_start_utc=datetime(2026, 5, 11, tzinfo=timezone.utc),
            model_prob_home=0.5,
            model_prob_away=0.5,
            model_ensemble_version="v1",
            tsl_market="moneyline",
            tsl_line=None,
            tsl_side="home",
            tsl_decimal_odds=2.0,
            edge_pct=0.0,
            kelly_fraction=0.0,
            stake_units_paper=0.0,
            gate_status="BLOCKED_PAPER_ONLY",
            generated_at_utc=datetime(2026, 5, 11, tzinfo=timezone.utc),
        )
        assert row.source_trace == {}


# ── to_dict round-trip ─────────────────────────────────────────────────────────

class TestToDict:
    def test_to_dict_returns_dict(self):
        row = _make_row()
        d = row.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_game_id(self):
        row = _make_row()
        assert row.to_dict()["game_id"] == "2026-05-11-LAA-CLE-824441"

    def test_to_dict_datetimes_are_strings(self):
        row = _make_row()
        d = row.to_dict()
        assert isinstance(d["game_start_utc"], str)
        assert isinstance(d["generated_at_utc"], str)

    def test_to_dict_model_probs(self):
        row = _make_row()
        d = row.to_dict()
        assert abs(d["model_prob_home"] - 0.535) < 1e-6
        assert abs(d["model_prob_away"] - 0.465) < 1e-6

    def test_to_dict_paper_only_true(self):
        row = _make_row()
        assert row.to_dict()["paper_only"] is True

    def test_to_dict_all_required_fields_present(self):
        row = _make_row()
        d = row.to_dict()
        required = [
            "game_id", "game_start_utc", "model_prob_home", "model_prob_away",
            "model_ensemble_version", "tsl_market", "tsl_line", "tsl_side",
            "tsl_decimal_odds", "edge_pct", "kelly_fraction", "stake_units_paper",
            "gate_status", "gate_reasons", "paper_only", "generated_at_utc",
            "source_trace",
        ]
        for key in required:
            assert key in d, f"Missing key in to_dict(): {key}"


# ── to_jsonl_line ──────────────────────────────────────────────────────────────

class TestToJsonlLine:
    def test_to_jsonl_line_is_valid_json(self):
        row = _make_row()
        line = row.to_jsonl_line()
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

    def test_to_jsonl_line_no_trailing_newline(self):
        row = _make_row()
        line = row.to_jsonl_line()
        assert not line.endswith("\n")

    def test_to_jsonl_roundtrip_game_id(self):
        row = _make_row()
        parsed = json.loads(row.to_jsonl_line())
        assert parsed["game_id"] == row.game_id


# ── gate_status enum validity ──────────────────────────────────────────────────

class TestGateStatus:
    def test_all_valid_gate_statuses_accepted(self):
        for status in VALID_GATE_STATUSES:
            row = _make_row(gate_status=status)
            assert row.gate_status == status

    def test_invalid_gate_status_raises(self):
        with pytest.raises(ValueError, match="gate_status"):
            _make_row(gate_status="TOTALLY_MADE_UP_STATUS")

    def test_blocked_paper_only_is_valid(self):
        row = _make_row(gate_status="BLOCKED_PAPER_ONLY")
        assert row.gate_status == "BLOCKED_PAPER_ONLY"

    def test_pass_is_valid(self):
        row = _make_row(gate_status="PASS")
        assert row.gate_status == "PASS"


# ── Probability validation ─────────────────────────────────────────────────────

class TestProbabilityValidation:
    def test_home_prob_out_of_range_raises(self):
        with pytest.raises(ValueError, match="model_prob_home"):
            _make_row(model_prob_home=1.5)

    def test_away_prob_out_of_range_raises(self):
        with pytest.raises(ValueError, match="model_prob_away"):
            _make_row(model_prob_away=-0.1)

    def test_boundary_probabilities_accepted(self):
        row = _make_row(model_prob_home=0.0, model_prob_away=0.0)
        assert row.model_prob_home == 0.0
