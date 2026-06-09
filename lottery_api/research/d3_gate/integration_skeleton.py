"""D3 gate read-only contract-validation integration skeleton (P258I).

SKELETON / PLANNING ARTIFACT ONLY.

This module exposes:
  - Static metadata objects describing the validator invocation order,
    allowed input contract boundaries, fail-closed policy, and forbidden
    import/path constraints defined in the P258H integration plan.
  - ``build_contract_validation_plan()`` — returns a static planning-only
    dict; performs no evaluation.
  - ``run_contract_validation_flow()`` — raises NotImplementedError.
    Executable flow is NOT authorized in P258I.

What this module does NOT do (and must never do without separate
explicit authorization):
  - Execute real candidate methods
  - Evaluate the D3 gate against any artifact
  - Generate adversarial nulls
  - Compute p-values or paired statistics
  - Run backtests
  - Load, query, or write the DB
  - Import or call recommendation, production, registry, controlled_apply,
    deployment, backtest, null_factory, gate_statistics, gate_orchestrator,
    random, numpy, or scipy code

D3 is not a prediction model.
Contract validation is not strategy evaluation.
NOT_YET_REJECTED is not approval.
Passing validators does not allow production or recommendation use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Tuple

# Only these two local imports are permitted by the P258H import boundary plan.
from .gate_validation import (
    ContractValidationError,  # noqa: F401  (re-exported for downstream typing)
    validate_correction_family_contract,
    validate_matched_null_family_contract,
    validate_no_approval_status_contract,
    validate_candidate_provenance_contract,
    validate_p257a_baseline_contract,
    validate_timestamp_cutoff_contract,
)
from .schemas import (
    CandidateInput,  # noqa: F401
    GateOutput,      # noqa: F401
    GateStatus,      # noqa: F401
    MatchedNullFamily,  # noqa: F401
    P257ABaselineInput,  # noqa: F401
)

# ---------------------------------------------------------------------------
# Validator invocation order (metadata — not executed here)
# ---------------------------------------------------------------------------

VALIDATOR_INVOCATION_ORDER: Tuple[Dict[str, Any], ...] = (
    {
        "step": 1,
        "name": "validate_no_approval_status_contract",
        "callable": validate_no_approval_status_contract,
        "input_type": "GateOutput",
        "purpose": (
            "Block forbidden approval tokens (APPROVED/PROMOTED/PRODUCTION_READY/"
            "RECOMMENDED) before any candidate data is examined."
        ),
        "fail_behavior": "raise ContractValidationError — blocks all further validation",
    },
    {
        "step": 2,
        "name": "validate_candidate_provenance_contract",
        "callable": validate_candidate_provenance_contract,
        "input_type": "CandidateInput",
        "purpose": "Confirm all required CandidateInput fields are present and non-empty.",
        "fail_behavior": "raise ContractValidationError — blocks all further validation",
    },
    {
        "step": 3,
        "name": "validate_timestamp_cutoff_contract",
        "callable": validate_timestamp_cutoff_contract,
        "input_type": "CandidateInput",
        "purpose": (
            "Confirm available_information_cutoff < target_draw_date "
            "AND <= generated_at."
        ),
        "fail_behavior": "raise ContractValidationError — blocks all further validation",
    },
    {
        "step": 4,
        "name": "validate_p257a_baseline_contract",
        "callable": validate_p257a_baseline_contract,
        "input_type": "CandidateInput + P257ABaselineInput",
        "purpose": (
            "Confirm baseline lottery_type, target_draw_id, and n_bet_count "
            "match the candidate."
        ),
        "fail_behavior": "raise ContractValidationError — blocks all further validation",
    },
    {
        "step": 5,
        "name": "validate_matched_null_family_contract",
        "callable": validate_matched_null_family_contract,
        "input_type": "CandidateInput + MatchedNullFamily",
        "purpose": (
            "Confirm matched-null metadata aligns with candidate on 6 dimensions. "
            "No nulls are generated."
        ),
        "fail_behavior": "raise ContractValidationError — blocks all further validation",
    },
    {
        "step": 6,
        "name": "validate_correction_family_contract",
        "callable": validate_correction_family_contract,
        "input_type": "correction_family object",
        "purpose": "Confirm all 6 correction-family collection fields are non-empty.",
        "fail_behavior": "raise ContractValidationError — blocks all further validation",
    },
)


# ---------------------------------------------------------------------------
# Allowed input contract boundaries (metadata)
# ---------------------------------------------------------------------------

ALLOWED_INPUT_CONTRACT_BOUNDARIES: Tuple[Dict[str, Any], ...] = (
    {
        "name": "candidate_provenance_contract",
        "schema_class": "CandidateInput",
        "source": (
            "Frozen OOS artifact — must not be derived from live DB at validation time."
        ),
    },
    {
        "name": "p257a_baseline_contract",
        "schema_class": "P257ABaselineInput",
        "alignment": "lottery_type, target_draw_id, n_bet_count must match candidate",
    },
    {
        "name": "matched_null_metadata_contract",
        "schema_class": "MatchedNullFamily",
        "note": "Validates metadata alignment ONLY — does not generate or execute nulls.",
    },
    {
        "name": "correction_family_declaration_contract",
        "schema_class": "dict or dataclass with 6 required collection fields",
        "note": "Declares correction family membership — does not compute corrections.",
    },
    {
        "name": "status_result_contract",
        "schema_class": "GateOutput",
        "allowed_gate_status_values": ("REJECTED", "NOT_YET_REJECTED"),
        "forbidden_gate_status_values": (
            "APPROVED",
            "PROMOTED",
            "PRODUCTION_READY",
            "RECOMMENDED",
        ),
    },
)


# ---------------------------------------------------------------------------
# Fail-closed policy metadata
# ---------------------------------------------------------------------------

FAIL_CLOSED_POLICY: Dict[str, Any] = {
    "any_contract_validation_error_blocks_further_validation": True,
    "failure_cannot_be_converted_to_warning_only": True,
    "not_yet_rejected_remains_not_approval": True,
    "forbidden_patterns": (
        "try/except ContractValidationError: pass",
        "try/except ContractValidationError: warnings.warn(...) and continue",
        "treating NOT_YET_REJECTED as equivalent to APPROVED",
        "treating validation success as authorization for production/recommendation use",
    ),
}


# ---------------------------------------------------------------------------
# Forbidden import / path metadata
# ---------------------------------------------------------------------------

FORBIDDEN_IMPORTS_AND_PATHS: Tuple[str, ...] = (
    "DB (any database module)",
    "recommendation (any module)",
    "production (any code path)",
    "registry mutation (any module)",
    "controlled_apply (any module)",
    "deployment (any path)",
    "backtest (any module)",
    "null_factory (not created in P258I)",
    "gate_statistics (not created in P258I)",
    "gate_orchestrator (not created in P258I)",
    "random (stdlib — no randomness in contract validation)",
    "numpy (no statistical computation)",
    "scipy (no statistical computation)",
)


# ---------------------------------------------------------------------------
# Safety semantics constants
# ---------------------------------------------------------------------------

D3_IS_NOT_A_PREDICTION_MODEL: bool = True
CONTRACT_VALIDATION_IS_NOT_STRATEGY_EVALUATION: bool = True
NOT_YET_REJECTED_IS_NOT_APPROVAL: bool = True
PASSING_VALIDATORS_DOES_NOT_ALLOW_PRODUCTION_USE: bool = True
PASSING_VALIDATORS_DOES_NOT_IMPLY_IMPROVED_PREDICTION_ACCURACY: bool = True
NO_LOTTERY_EDGE_CLAIMED: bool = True


# ---------------------------------------------------------------------------
# Skeleton stubs
# ---------------------------------------------------------------------------

def build_contract_validation_plan() -> Dict[str, Any]:
    """Return a static planning-only metadata dict.

    This function performs NO evaluation, NO candidate lookup, NO DB access,
    and NO statistical computation.  It is a planning artifact only.
    """
    return {
        "plan_id": "P258I_CONTRACT_VALIDATION_SKELETON",
        "description": (
            "Read-only D3 contract-validation integration skeleton. "
            "Returns static planning metadata only. "
            "Does not execute any candidate validation."
        ),
        "validator_invocation_order": [
            {k: v for k, v in step.items() if k != "callable"}
            for step in VALIDATOR_INVOCATION_ORDER
        ],
        "allowed_input_contract_boundaries": list(ALLOWED_INPUT_CONTRACT_BOUNDARIES),
        "fail_closed_policy": FAIL_CLOSED_POLICY,
        "forbidden_imports_and_paths": list(FORBIDDEN_IMPORTS_AND_PATHS),
        "safety_semantics": {
            "d3_is_not_a_prediction_model": D3_IS_NOT_A_PREDICTION_MODEL,
            "contract_validation_is_not_strategy_evaluation": (
                CONTRACT_VALIDATION_IS_NOT_STRATEGY_EVALUATION
            ),
            "not_yet_rejected_is_not_approval": NOT_YET_REJECTED_IS_NOT_APPROVAL,
            "passing_validators_does_not_allow_production_use": (
                PASSING_VALIDATORS_DOES_NOT_ALLOW_PRODUCTION_USE
            ),
            "passing_validators_does_not_imply_improved_prediction_accuracy": (
                PASSING_VALIDATORS_DOES_NOT_IMPLY_IMPROVED_PREDICTION_ACCURACY
            ),
            "no_lottery_edge_claimed": NO_LOTTERY_EDGE_CLAIMED,
        },
        "executable_flow_status": "NOT_IMPLEMENTED — requires separate future authorization",
        "next_authorized_task": (
            "P258J — read-only synthetic integration skeleton tests / "
            "dry-contract fixtures only (requires separate explicit authorization)"
        ),
    }


def run_contract_validation_flow(*args: Any, **kwargs: Any) -> None:
    """Placeholder for a future executable integration flow.

    Raises NotImplementedError unconditionally.  Executable contract-validation
    flow is NOT authorized in P258I.  A separate future task with explicit
    authorization is required before this function may have a real body.
    """
    raise NotImplementedError(
        "run_contract_validation_flow: executable contract-validation flow is NOT "
        "authorized in P258I.  This stub exists only as a skeleton placeholder.  "
        "A separate future task (post-P258J) with explicit authorization is required "
        "before any real implementation may be added here.  "
        "D3 is not a prediction model.  NOT_YET_REJECTED is not approval."
    )
