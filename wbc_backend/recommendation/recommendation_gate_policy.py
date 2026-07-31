"""
wbc_backend/recommendation/recommendation_gate_policy.py

Bridge between StrategySimulationResult and recommendation gate decisions.

Public API:
    build_recommendation_gate_from_simulation(simulation) -> dict

Rules:
- PASS simulation → allow_recommendation=True (paper-only only).
- BLOCKED_NEGATIVE_BSS → blocks recommendation.
- BLOCKED_HIGH_ECE → blocks recommendation.
- BLOCKED_LOW_SAMPLE → blocks recommendation.
- Missing simulation → blocks recommendation.
- paper_only always remains True in the output.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wbc_backend.simulation.strategy_simulation_result import StrategySimulationResult

# Gate statuses that block all recommendations
_BLOCKING_STATUSES = frozenset({
    "BLOCKED_NEGATIVE_BSS",
    "BLOCKED_HIGH_ECE",
    "BLOCKED_LOW_SAMPLE",
    "BLOCKED_NO_MARKET_DATA",
    "BLOCKED_NO_RESULTS",
})


def _build_gate_source_trace(sim_trace: dict) -> dict:
    """
    Build the recommendation source_trace from the simulation source_trace.
    Surfaces OOF calibration evidence for downstream auditing.
    """
    gate_trace: dict = dict(sim_trace)
    # P7: surface OOF calibration fields explicitly
    gate_trace["simulation_calibration_mode"] = sim_trace.get("calibration_mode", "none")
    gate_trace["simulation_oof_calibration_count"] = sim_trace.get("oof_calibration_count", 0)
    gate_trace["simulation_leakage_safe"] = sim_trace.get("leakage_safe", False)
    return gate_trace


def _annotate_calibration_gate_reasons(sim_trace: dict, gate_reasons: list[str]) -> None:
    """
    Add calibration-specific gate reasons if applicable.
    Called for all gate return paths.
    """
    cal_mode = sim_trace.get("calibration_mode")
    leakage_safe = sim_trace.get("leakage_safe", False)
    cal_warning = sim_trace.get("calibration_warning")
    oof_count = sim_trace.get("oof_calibration_count", 0)

    if cal_warning:
        gate_reasons.append(f"Calibration note: {cal_warning}")

    # In-sample calibration warning
    if cal_mode and cal_mode not in ("walk_forward_oof", "none"):
        gate_reasons.append(
            f"Simulation used in-sample calibration (mode={cal_mode!r}). "
            "In-sample calibration is not production deployable."
        )

    # Leakage safety check
    if oof_count and oof_count > 0 and not leakage_safe:
        gate_reasons.append(
            "WARNING: OOF calibration detected but leakage_safe=False — "
            "gate cannot PASS for this calibration mode."
        )


def build_recommendation_gate_from_simulation(
    simulation: "StrategySimulationResult | None",
) -> dict:
    """
    Build a recommendation gate policy dict from a simulation result.

    Parameters
    ----------
    simulation : StrategySimulationResult | None
        The simulation result to evaluate. Pass None to produce a
        BLOCKED (missing simulation) gate.

    Returns
    -------
    dict with keys:
        allow_recommendation : bool
        gate_status          : str
        gate_reasons         : list[str]
        simulation_id        : str | None
        paper_only           : True (always)
    """
    if simulation is None:
        return {
            "allow_recommendation": False,
            "gate_status": "BLOCKED_NO_SIMULATION",
            "gate_reasons": [
                "No simulation result provided. "
                "A valid StrategySimulationResult is required before recommendations can be issued."
            ],
            "simulation_id": None,
            "paper_only": True,
        }

    gate_reasons: list[str] = list(simulation.gate_reasons)
    sim_status = simulation.gate_status

    # Hard invariant: must never propagate paper_only=False
    if not simulation.paper_only:
        return {
            "allow_recommendation": False,
            "gate_status": "BLOCKED_PAPER_ONLY_VIOLATION",
            "gate_reasons": [
                "Simulation paper_only flag is False — this is a critical invariant violation. "
                "All recommendations are blocked until paper_only is restored."
            ],
            "simulation_id": simulation.simulation_id,
            "paper_only": True,
        }

    if sim_status in _BLOCKING_STATUSES:
        gate_reasons.insert(
            0,
            f"Simulation gate_status={sim_status!r} blocks recommendation issuance.",
        )
        # P7: annotate calibration evidence from source_trace
        sim_trace = simulation.source_trace or {}
        _annotate_calibration_gate_reasons(sim_trace, gate_reasons)
        return {
            "allow_recommendation": False,
            "gate_status": sim_status,
            "gate_reasons": gate_reasons,
            "simulation_id": simulation.simulation_id,
            "paper_only": True,
            "source_trace": _build_gate_source_trace(sim_trace),
        }

    if sim_status == "PASS":
        sim_trace = simulation.source_trace or {}
        _annotate_calibration_gate_reasons(sim_trace, gate_reasons)
        gate_reasons.append(
            "Simulation gate PASS — paper-only recommendation allowed. "
            "Production enablement requires separate P38 governance clearance."
        )
        return {
            "allow_recommendation": True,
            "gate_status": "PASS",
            "gate_reasons": gate_reasons,
            "simulation_id": simulation.simulation_id,
            "source_trace": _build_gate_source_trace(sim_trace),
            "paper_only": True,
        }

    # PAPER_ONLY or any other status → allow paper recommendation but flag
    sim_trace = simulation.source_trace or {}
    _annotate_calibration_gate_reasons(sim_trace, gate_reasons)
    gate_reasons.append(
        f"Simulation gate_status={sim_status!r} — paper-only recommendation allowed with caution."
    )
    return {
        "allow_recommendation": True,
        "gate_status": sim_status,
        "gate_reasons": gate_reasons,
        "simulation_id": simulation.simulation_id,
        "paper_only": True,
        "source_trace": _build_gate_source_trace(sim_trace),
    }
