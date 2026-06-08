"""D3 gate validation stubs (P258E skeleton).

NON-EXECUTING. Every function below is a planning-only stub that raises
``NotImplementedError``. No real validation, scoring, null generation, paired
testing, or p-value computation is performed here. No DB access. No production/
registry/recommendation/controlled_apply/deployment imports.

Real validator implementation is deferred to a separately authorized task
(P258F read-only contract validator implementation only).
"""

from __future__ import annotations

from .schemas import (
    CandidateInput,
    GateOutput,
    MatchedNullFamily,
    P257ABaselineInput,
)

_PLANNING_ONLY = (
    "P258E skeleton: validation is planning-only and not implemented. "
    "Real implementation requires separate explicit authorization (P258F+)."
)


def validate_candidate_provenance_contract(candidate: CandidateInput) -> None:
    """Stub: assert 100% provenance completeness. Not implemented in P258E."""
    raise NotImplementedError(_PLANNING_ONLY)


def validate_timestamp_cutoff_contract(candidate: CandidateInput) -> None:
    """Stub: assert all feature times < cutoff < target draw. Not implemented."""
    raise NotImplementedError(_PLANNING_ONLY)


def validate_p257a_baseline_contract(
    candidate: CandidateInput, baseline: P257ABaselineInput
) -> None:
    """Stub: assert baseline alignment by (lottery, N, draw). Not implemented."""
    raise NotImplementedError(_PLANNING_ONLY)


def validate_matched_null_family_contract(
    candidate: CandidateInput, null_family: MatchedNullFamily
) -> None:
    """Stub: assert null mirrors candidate degrees of freedom. Not implemented."""
    raise NotImplementedError(_PLANNING_ONLY)


def validate_correction_family_contract(correction_family: object) -> None:
    """Stub: assert full correction family pre-declared. Not implemented."""
    raise NotImplementedError(_PLANNING_ONLY)


def validate_no_approval_status_contract(output: GateOutput) -> None:
    """Stub: assert gate_decision is never an approval status. Not implemented."""
    raise NotImplementedError(_PLANNING_ONLY)
