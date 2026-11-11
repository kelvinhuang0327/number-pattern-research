"""
tests/test_recommendation_gate_policy.py

Tests for build_recommendation_gate_from_simulation().
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from wbc_backend.simulation.strategy_simulation_result import StrategySimulationResult
from wbc_backend.recommendation.recommendation_gate_policy import (
    build_recommendation_gate_from_simulation,
)

# ── Fixture factory ───────────────────────────────────────────────────────────

def _make_sim(gate_status: str = "PASS", sample_size: int = 100) -> StrategySimulationResult:
    return StrategySimulationResult(
        simulation_id="sim-gate-test-abcd1234",
        strategy_name="gate_test",
        date_start="2025-01-01",
        date_end="2025-12-31",
        sample_size=sample_size,
        bet_count=40,
        skipped_count=5,
        gate_status=gate_status,
        generated_at_utc=datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc),
        brier_skill_score=-0.14 if "NEGATIVE_BSS" in gate_status else 0.02,
        ece=0.15 if "HIGH_ECE" in gate_status else 0.05,
    )


# ── Tests: missing simulation ─────────────────────────────────────────────────

class TestMissingSimulation:
    def test_none_simulation_blocks_recommendation(self):
        gate = build_recommendation_gate_from_simulation(None)
        assert gate["allow_recommendation"] is False

    def test_none_simulation_paper_only_true(self):
        gate = build_recommendation_gate_from_simulation(None)
        assert gate["paper_only"] is True

    def test_none_simulation_gate_status(self):
        gate = build_recommendation_gate_from_simulation(None)
        assert gate["gate_status"] == "BLOCKED_NO_SIMULATION"

    def test_none_simulation_id_is_none(self):
        gate = build_recommendation_gate_from_simulation(None)
        assert gate["simulation_id"] is None


# ── Tests: blocked statuses ───────────────────────────────────────────────────

class TestBlockedStatuses:
    def test_negative_bss_blocks_recommendation(self):
        sim = _make_sim(gate_status="BLOCKED_NEGATIVE_BSS")
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["allow_recommendation"] is False

    def test_high_ece_blocks_recommendation(self):
        sim = _make_sim(gate_status="BLOCKED_HIGH_ECE")
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["allow_recommendation"] is False

    def test_low_sample_blocks_recommendation(self):
        sim = _make_sim(gate_status="BLOCKED_LOW_SAMPLE", sample_size=10)
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["allow_recommendation"] is False

    def test_no_market_data_blocks_recommendation(self):
        sim = _make_sim(gate_status="BLOCKED_NO_MARKET_DATA", sample_size=0)
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["allow_recommendation"] is False

    def test_no_results_blocks_recommendation(self):
        sim = _make_sim(gate_status="BLOCKED_NO_RESULTS", sample_size=0)
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["allow_recommendation"] is False


# ── Tests: PASS gate ──────────────────────────────────────────────────────────

class TestPassGate:
    def test_pass_allows_paper_recommendation(self):
        sim = _make_sim(gate_status="PASS", sample_size=100)
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["allow_recommendation"] is True

    def test_pass_gate_status_is_pass(self):
        sim = _make_sim(gate_status="PASS", sample_size=100)
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["gate_status"] == "PASS"

    def test_pass_simulation_id_propagated(self):
        sim = _make_sim(gate_status="PASS", sample_size=100)
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["simulation_id"] == sim.simulation_id

    def test_pass_has_governance_note_in_reasons(self):
        sim = _make_sim(gate_status="PASS", sample_size=100)
        gate = build_recommendation_gate_from_simulation(sim)
        reasons_text = " ".join(gate["gate_reasons"])
        # Should mention paper-only / governance
        assert "paper" in reasons_text.lower() or "governance" in reasons_text.lower()


# ── Tests: paper_only invariant ───────────────────────────────────────────────

class TestPaperOnlyInvariant:
    def test_gate_paper_only_always_true_for_pass(self):
        sim = _make_sim(gate_status="PASS", sample_size=100)
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["paper_only"] is True

    def test_gate_paper_only_always_true_for_blocked(self):
        sim = _make_sim(gate_status="BLOCKED_NEGATIVE_BSS")
        gate = build_recommendation_gate_from_simulation(sim)
        assert gate["paper_only"] is True

    def test_gate_paper_only_always_true_for_none(self):
        gate = build_recommendation_gate_from_simulation(None)
        assert gate["paper_only"] is True

    def test_gate_output_has_paper_only_key(self):
        """The paper_only key must always be present in output dict."""
        for status in ["PASS", "BLOCKED_NEGATIVE_BSS", "BLOCKED_HIGH_ECE", "BLOCKED_LOW_SAMPLE"]:
            sample = 100 if status == "PASS" else 10
            sim = _make_sim(gate_status=status, sample_size=sample)
            gate = build_recommendation_gate_from_simulation(sim)
            assert "paper_only" in gate, f"paper_only missing for gate_status={status}"
            assert gate["paper_only"] is True, f"paper_only must be True for gate_status={status}"


# ── Tests: gate output structure ──────────────────────────────────────────────

class TestGateOutputStructure:
    def test_output_has_required_keys(self):
        sim = _make_sim(gate_status="PASS", sample_size=100)
        gate = build_recommendation_gate_from_simulation(sim)
        required = ["allow_recommendation", "gate_status", "gate_reasons",
                    "simulation_id", "paper_only"]
        for key in required:
            assert key in gate, f"Missing key: {key}"

    def test_gate_reasons_is_list(self):
        sim = _make_sim(gate_status="PASS", sample_size=100)
        gate = build_recommendation_gate_from_simulation(sim)
        assert isinstance(gate["gate_reasons"], list)

    def test_allow_recommendation_is_bool(self):
        sim = _make_sim(gate_status="PASS", sample_size=100)
        gate = build_recommendation_gate_from_simulation(sim)
        assert isinstance(gate["allow_recommendation"], bool)


# ── Tests: P7 OOF calibration evidence in source_trace ───────────────────────

def _make_sim_with_oof_trace(
    gate_status: str = "PASS",
    sample_size: int = 100,
    oof_count: int = 100,
    leakage_safe: bool = True,
    cal_mode: str = "walk_forward_oof",
) -> "StrategySimulationResult":
    return StrategySimulationResult(
        simulation_id="sim-oof-test-abcd1234",
        strategy_name="oof_test",
        date_start="2025-01-01",
        date_end="2025-12-31",
        sample_size=sample_size,
        bet_count=40,
        skipped_count=5,
        gate_status=gate_status,
        generated_at_utc=datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc),
        brier_skill_score=0.02,
        ece=0.05,
        source_trace={
            "probability_source_mode": "calibrated_model",
            "calibration_mode": cal_mode,
            "oof_calibration_count": oof_count,
            "leakage_safe": leakage_safe,
            "calibration_warning": (
                "walk-forward OOF calibration candidate; production still requires human approval"
                if leakage_safe else
                "in-sample calibration candidate; not production deployable unless OOF validated"
            ),
        },
    )


class TestOOFCalibrationEvidenceInGateP7:
    def test_gate_source_trace_has_simulation_calibration_mode(self):
        """source_trace must include simulation_calibration_mode."""
        sim = _make_sim_with_oof_trace(gate_status="PASS", oof_count=100, leakage_safe=True)
        gate = build_recommendation_gate_from_simulation(sim)
        assert "simulation_calibration_mode" in gate["source_trace"], (
            f"Missing simulation_calibration_mode. source_trace={gate['source_trace']}"
        )
        assert gate["source_trace"]["simulation_calibration_mode"] == "walk_forward_oof"

    def test_gate_source_trace_has_oof_calibration_count(self):
        """source_trace must include simulation_oof_calibration_count."""
        sim = _make_sim_with_oof_trace(gate_status="PASS", oof_count=100, leakage_safe=True)
        gate = build_recommendation_gate_from_simulation(sim)
        assert "simulation_oof_calibration_count" in gate["source_trace"], (
            f"Missing simulation_oof_calibration_count. source_trace={gate['source_trace']}"
        )
        assert gate["source_trace"]["simulation_oof_calibration_count"] == 100

    def test_gate_source_trace_has_leakage_safe(self):
        """source_trace must include simulation_leakage_safe."""
        sim = _make_sim_with_oof_trace(gate_status="PASS", oof_count=100, leakage_safe=True)
        gate = build_recommendation_gate_from_simulation(sim)
        assert "simulation_leakage_safe" in gate["source_trace"], (
            f"Missing simulation_leakage_safe. source_trace={gate['source_trace']}"
        )
        assert gate["source_trace"]["simulation_leakage_safe"] is True

    def test_in_sample_calibration_adds_non_deployable_reason(self):
        """In-sample calibration (cal_mode != walk_forward_oof) must add non-deployable note."""
        sim = _make_sim_with_oof_trace(
            gate_status="PASS",
            oof_count=100,
            leakage_safe=False,
            cal_mode="in_sample",
        )
        gate = build_recommendation_gate_from_simulation(sim)
        reasons_text = " ".join(gate["gate_reasons"])
        assert "in-sample" in reasons_text.lower() or "not production" in reasons_text.lower(), (
            f"Expected in-sample non-deployable warning in gate_reasons.\n"
            f"gate_reasons={gate['gate_reasons']}"
        )

    def test_oof_calibration_gate_reasons_include_oof_warning(self):
        """OOF calibration gate_reasons must mention OOF warning from calibration_warning."""
        sim = _make_sim_with_oof_trace(gate_status="PASS", oof_count=100, leakage_safe=True)
        gate = build_recommendation_gate_from_simulation(sim)
        reasons_text = " ".join(gate["gate_reasons"]).lower()
        assert "oof" in reasons_text or "walk-forward" in reasons_text, (
            f"Expected OOF warning in gate_reasons. gate_reasons={gate['gate_reasons']}"
        )
