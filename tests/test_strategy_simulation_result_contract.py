"""
tests/test_strategy_simulation_result_contract.py

Unit tests for StrategySimulationResult dataclass contract.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from wbc_backend.simulation.strategy_simulation_result import (
    VALID_GATE_STATUSES,
    StrategySimulationResult,
)

# ── Fixture factory ───────────────────────────────────────────────────────────

def _make_result(**kwargs) -> StrategySimulationResult:
    defaults = dict(
        simulation_id="sim-test-abc12345",
        strategy_name="test_strategy",
        date_start="2025-01-01",
        date_end="2025-12-31",
        sample_size=50,
        bet_count=20,
        skipped_count=5,
        gate_status="PASS",
        generated_at_utc=datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return StrategySimulationResult(**defaults)


# ── TestFieldPresence ─────────────────────────────────────────────────────────

class TestFieldPresence:
    def test_all_required_fields_exist(self):
        r = _make_result()
        required = [
            "simulation_id", "strategy_name", "date_start", "date_end",
            "sample_size", "bet_count", "skipped_count", "avg_model_prob",
            "avg_market_prob", "brier_model", "brier_market", "brier_skill_score",
            "ece", "roi_pct", "max_drawdown_pct", "sharpe_proxy",
            "avg_edge_pct", "avg_kelly_fraction", "gate_status", "gate_reasons",
            "paper_only", "generated_at_utc", "source_trace",
        ]
        for field in required:
            assert hasattr(r, field), f"Missing field: {field}"

    def test_all_valid_gate_statuses_present(self):
        expected = {
            "PASS", "BLOCKED_NEGATIVE_BSS", "BLOCKED_HIGH_ECE",
            "BLOCKED_LOW_SAMPLE", "BLOCKED_NO_MARKET_DATA",
            "BLOCKED_NO_RESULTS", "PAPER_ONLY",
        }
        assert expected == VALID_GATE_STATUSES


# ── TestDefaults ──────────────────────────────────────────────────────────────

class TestDefaults:
    def test_paper_only_default_is_true(self):
        r = _make_result()
        assert r.paper_only is True

    def test_paper_only_cannot_be_false(self):
        with pytest.raises(ValueError, match="paper_only must remain True"):
            _make_result(paper_only=False)

    def test_gate_reasons_defaults_empty_list(self):
        r = _make_result()
        assert r.gate_reasons == []

    def test_source_trace_defaults_empty_dict(self):
        r = _make_result()
        assert r.source_trace == {}

    def test_optional_float_fields_default_to_none(self):
        r = _make_result()
        for field in [
            "avg_model_prob", "avg_market_prob", "brier_model", "brier_market",
            "brier_skill_score", "ece", "roi_pct", "max_drawdown_pct",
            "sharpe_proxy", "avg_edge_pct", "avg_kelly_fraction",
        ]:
            assert getattr(r, field) is None, f"{field} should default to None"


# ── TestGateStatus ────────────────────────────────────────────────────────────

class TestGateStatus:
    def test_all_valid_gate_statuses_accepted(self):
        for status in VALID_GATE_STATUSES:
            # Low sample must not use PASS
            sample = 50 if status == "PASS" else 0
            r = _make_result(gate_status=status, sample_size=sample)
            assert r.gate_status == status

    def test_invalid_gate_status_raises(self):
        with pytest.raises(ValueError, match="gate_status"):
            _make_result(gate_status="INVALID_STATUS")

    def test_pass_is_valid(self):
        r = _make_result(gate_status="PASS", sample_size=50)
        assert r.gate_status == "PASS"

    def test_low_sample_cannot_pass(self):
        """sample_size < 30 must not have gate_status=PASS."""
        with pytest.raises(ValueError, match="gate_status cannot be PASS"):
            _make_result(gate_status="PASS", sample_size=10)

    def test_low_sample_can_be_blocked(self):
        r = _make_result(gate_status="BLOCKED_LOW_SAMPLE", sample_size=5)
        assert r.gate_status == "BLOCKED_LOW_SAMPLE"

    def test_zero_sample_with_no_results(self):
        r = _make_result(gate_status="BLOCKED_NO_RESULTS", sample_size=0)
        assert r.sample_size == 0


# ── TestCountValidation ───────────────────────────────────────────────────────

class TestCountValidation:
    def test_negative_sample_size_raises(self):
        with pytest.raises(ValueError, match="sample_size must be >= 0"):
            _make_result(sample_size=-1)

    def test_negative_bet_count_raises(self):
        with pytest.raises(ValueError, match="bet_count must be >= 0"):
            _make_result(bet_count=-1)

    def test_negative_skipped_count_raises(self):
        with pytest.raises(ValueError, match="skipped_count must be >= 0"):
            _make_result(skipped_count=-1)

    def test_zero_counts_are_valid(self):
        r = _make_result(
            sample_size=0,
            bet_count=0,
            skipped_count=0,
            gate_status="BLOCKED_NO_RESULTS",
        )
        assert r.sample_size == 0
        assert r.bet_count == 0
        assert r.skipped_count == 0


# ── TestToDict ────────────────────────────────────────────────────────────────

class TestToDict:
    def test_to_dict_returns_dict(self):
        r = _make_result()
        assert isinstance(r.to_dict(), dict)

    def test_to_dict_all_required_fields_present(self):
        r = _make_result()
        d = r.to_dict()
        required = [
            "simulation_id", "strategy_name", "date_start", "date_end",
            "sample_size", "bet_count", "skipped_count", "gate_status",
            "gate_reasons", "paper_only", "generated_at_utc", "source_trace",
        ]
        for field in required:
            assert field in d, f"to_dict() missing: {field}"

    def test_to_dict_paper_only_is_true(self):
        r = _make_result()
        assert r.to_dict()["paper_only"] is True

    def test_to_dict_datetime_is_string(self):
        r = _make_result()
        d = r.to_dict()
        assert isinstance(d["generated_at_utc"], str)
        # Should be ISO-8601
        assert "T" in d["generated_at_utc"]

    def test_to_dict_simulation_id(self):
        r = _make_result(simulation_id="sim-xyz-00000001")
        assert r.to_dict()["simulation_id"] == "sim-xyz-00000001"


# ── TestToJsonlLine ───────────────────────────────────────────────────────────

class TestToJsonlLine:
    def test_to_jsonl_line_is_valid_json(self):
        r = _make_result()
        line = r.to_jsonl_line()
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

    def test_to_jsonl_line_no_trailing_newline(self):
        r = _make_result()
        line = r.to_jsonl_line()
        assert not line.endswith("\n")

    def test_to_jsonl_roundtrip_simulation_id(self):
        r = _make_result(simulation_id="sim-roundtrip-12345678")
        parsed = json.loads(r.to_jsonl_line())
        assert parsed["simulation_id"] == "sim-roundtrip-12345678"

    def test_to_jsonl_roundtrip_gate_status(self):
        r = _make_result(gate_status="BLOCKED_LOW_SAMPLE", sample_size=5)
        parsed = json.loads(r.to_jsonl_line())
        assert parsed["gate_status"] == "BLOCKED_LOW_SAMPLE"
